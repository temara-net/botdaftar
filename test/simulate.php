<?php
// HARNESS UJI LOKAL — menjalankan server tiruan Telegram + AI di localhost,
// lalu mengirim update palsu ke handle_update() dan memeriksa balasannya.
// Tidak menyentuh Telegram / provider AI asli sama sekali.
// Jalankan:  php test/simulate.php
declare(strict_types=1);

// --- Server tiruan (satu proses php -S dipakai untuk Telegram & AI) ---
$mockPhp = <<<'PHP'
<?php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$body = json_decode((string)file_get_contents('php://input'), true) ?: [];
file_put_contents(__DIR__ . '/mock_log.jsonl', json_encode(['path'=>$path,'body'=>$body]) . "\n", FILE_APPEND);
header('Content-Type: application/json');
if (str_ends_with($path, '/sendMessage') || str_ends_with($path, '/sendChatAction') || str_ends_with($path, '/getMe')) {
    echo json_encode(['ok'=>true,'result'=>['id'=>1,'is_bot'=>true,'username'=>'mockbot']]);
    return;
}
if (str_contains($path, ':generateContent')) { // Gemini
    $last = end($body['contents']);
    $q = $last['parts'][0]['text'] ?? '';
    echo json_encode(['candidates'=>[['content'=>['parts'=>[['text'=>'Jawaban AI tiruan untuk: '.$q]]]]]]);
    return;
}
if (str_ends_with($path, '/chat/completions')) { // OpenAI / OpenRouter
    $msgs = $body['messages'] ?? [];
    $last = end($msgs);
    $q = $last['content'] ?? '';
    echo json_encode(['choices'=>[['message'=>['role'=>'assistant','content'=>'Jawaban AI tiruan untuk: '.$q]]]]);
    return;
}
http_response_code(404);
echo json_encode(['ok'=>false,'description'=>'mock: path tak dikenal '.$path]);
PHP;

$testDir = __DIR__;
file_put_contents($testDir . '/mock_server.php', $mockPhp);
@unlink($testDir . '/mock_log.jsonl');

$port = 18099;
$proc = proc_open(
    [PHP_BINARY, '-S', "127.0.0.1:$port", $testDir . '/mock_server.php'],
    [0 => ['pipe', 'r'], 1 => ['file', $testDir . '/mock_out.log', 'a'], 2 => ['file', $testDir . '/mock_out.log', 'a']],
    $pipes
);
if (!is_resource($proc)) { fwrite(STDERR, "Gagal menyalakan server tiruan\n"); exit(1); }
// tunggu server siap
for ($i = 0; $i < 50; $i++) {
    $c = @file_get_contents("http://127.0.0.1:$port/getMe");
    if ($c !== false) break;
    usleep(100000);
}

require dirname(__DIR__) . '/includes/telegram.php';
require dirname(__DIR__) . '/includes/ai.php';
require dirname(__DIR__) . '/includes/store.php';
require dirname(__DIR__) . '/includes/handle.php';

$tmpData = sys_get_temp_dir() . '/tgbot_test_' . getmypid();
$pass = 0; $fail = 0;
function check(string $name, bool $ok, string $detail = '') {
    global $pass, $fail;
    if ($ok) { $pass++; echo "  LULUS  $name\n"; }
    else { $fail++; echo "  GAGAL  $name  $detail\n"; }
}
function sentTexts(string $logFile): array {
    $out = [];
    foreach (file($logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
        $r = json_decode($line, true);
        if (str_ends_with($r['path'], '/sendMessage')) $out[] = $r['body']['text'] ?? '';
    }
    return $out;
}
function makeUpdate(int $chatId, string $text): array {
    return ['update_id' => 1, 'message' => ['message_id' => 1, 'chat' => ['id' => $chatId, 'type' => 'private'], 'text' => $text]];
}
$log = $testDir . '/mock_log.jsonl';
$apiBase = "http://127.0.0.1:$port/";

foreach (['openai', 'gemini', 'openrouter'] as $provider) {
    echo "Provider: $provider\n";
    @unlink($log);
    $cfg = [
        'ai_provider' => $provider, 'ai_api_key' => 'kunci-tiruan', 'ai_model' => 'model-tiruan',
        'system_prompt' => 'Kamu asisten uji.', 'telegram_api_base' => $apiBase,
        'ai_base_url' => $apiBase, 'history_limit' => 20,
    ];
    $tg = new TelegramBot('token-tiruan', $apiBase);
    $ai = new AIClient($cfg);
    $store = new ChatStore($tmpData . '_' . $provider, 20);

    handle_update(makeUpdate(111, '/start'), $tg, $ai, $store);
    handle_update(makeUpdate(111, 'halo apa kabar'), $tg, $ai, $store);
    handle_update(makeUpdate(111, 'pertanyaan kedua'), $tg, $ai, $store);
    $texts = sentTexts($log);
    check('/start dibalas sambutan', isset($texts[0]) && str_contains($texts[0], '/help'));
    check('pesan biasa dijawab AI tiruan', isset($texts[1]) && str_contains($texts[1], 'Jawaban AI tiruan untuk: halo apa kabar'), json_encode($texts));
    check('pesan kedua dijawab AI tiruan', isset($texts[2]) && str_contains($texts[2], 'pertanyaan kedua'));
    $hist = $store->get(111);
    check('riwayat tersimpan 4 entri (2 user + 2 assistant)', count($hist) === 4, 'isi=' . count($hist));

    handle_update(makeUpdate(111, '/reset'), $tg, $ai, $store);
    check('/reset mengosongkan riwayat', $store->get(111) === []);
    handle_update(makeUpdate(111, '/info'), $tg, $ai, $store);
    $texts = sentTexts($log);
    $lastText = end($texts);
    check('/info menyebut provider & model', str_contains($lastText, $provider) && str_contains($lastText, 'model-tiruan'), $lastText);
}

// Kasus gagal: AI belum dikonfigurasi
echo "Kasus: AI belum dikonfigurasi\n";
@unlink($log);
$cfg = ['ai_provider' => '', 'ai_api_key' => '', 'ai_model' => '', 'system_prompt' => '', 'telegram_api_base' => $apiBase, 'ai_base_url' => $apiBase, 'history_limit' => 20];
$tg = new TelegramBot('token-tiruan', $apiBase);
$ai = new AIClient($cfg);
$store = new ChatStore($tmpData . '_kosong', 20);
handle_update(makeUpdate(222, 'halo'), $tg, $ai, $store);
$texts = sentTexts($log);
check('balasan jujur belum dikonfigurasi', isset($texts[0]) && str_contains($texts[0], 'belum dikonfigurasi'), json_encode($texts));
check('riwayat TIDAK tersimpan saat AI mati', $store->get(222) === []);

// Kasus gagal: provider AI menolak (API key salah -> mock balas 404 untuk path asing tidak dipakai; pakai base mati)
echo "Kasus: provider AI tidak terjangkau\n";
@unlink($log);
$cfg = ['ai_provider' => 'openai', 'ai_api_key' => 'x', 'ai_model' => 'm', 'system_prompt' => '', 'telegram_api_base' => $apiBase, 'ai_base_url' => 'http://127.0.0.1:1/mati', 'history_limit' => 20];
$tg = new TelegramBot('token-tiruan', $apiBase);
$ai = new AIClient($cfg);
$store = new ChatStore($tmpData . '_mati', 20);
handle_update(makeUpdate(333, 'halo'), $tg, $ai, $store);
$texts = sentTexts($log);
check('balasan gagal sopan, tanpa bocor error', isset($texts[0]) && str_contains($texts[0], 'tidak bisa dihubungi'), json_encode($texts));

// Pecah pesan panjang
$tg2 = new TelegramBot('t', $apiBase);
$chunks = $tg2->split(str_repeat('kata ', 2000));
check('pesan panjang dipecah <=4096', count($chunks) > 1 && max(array_map('mb_strlen', $chunks)) <= 4096);

proc_terminate($proc); proc_close($proc);
echo "\nHASIL: $pass lulus, $fail gagal\n";
exit($fail > 0 ? 1 : 0);
