<?php
// Mode LONG POLLING — jalan dari terminal/CLI, TANPA hosting & tanpa HTTPS.
// Cocok untuk tes lokal dan untuk VPS. Jalankan:  php poll.php
// Berhenti: Ctrl+C.
// PENTING: mode ini dan webhook tidak boleh jalan bersamaan.
// Kalau webhook pernah dipasang, hapus dulu: buka set_webhook.php?action=delete
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit('poll.php hanya untuk CLI.');
}

$cfg = require __DIR__ . '/config.php';
require __DIR__ . '/includes/telegram.php';
require __DIR__ . '/includes/ai.php';
require __DIR__ . '/includes/store.php';
require __DIR__ . '/includes/handle.php';

$tg = new TelegramBot($cfg['telegram_token'], $cfg['telegram_api_base'] ?? null);
$ai = new AIClient($cfg);
$store = new ChatStore(__DIR__ . '/data', (int)($cfg['history_limit'] ?? 20));

$me = $tg->call('getMe');
if (empty($me['ok'])) {
    fwrite(STDERR, "Token Telegram tidak diterima. Cek telegram_token di config.php\n");
    exit(1);
}
echo "Bot @" . ($me['result']['username'] ?? '?') . " aktif (polling). Ctrl+C untuk berhenti.\n";
if (!$ai->configured()) {
    echo "CATATAN: AI belum dikonfigurasi — pesan biasa akan dijawab pemberitahuan konfigurasi.\n";
}

$offset = 0;
while (true) {
    $res = $tg->call('getUpdates', [
        'offset' => $offset,
        'timeout' => 25,
        'allowed_updates' => ['message', 'edited_message'],
    ]);
    if ($res === null || empty($res['ok'])) {
        sleep(2);
        continue;
    }
    foreach ($res['result'] as $update) {
        $offset = ((int)$update['update_id']) + 1;
        try {
            handle_update($update, $tg, $ai, $store);
        } catch (Throwable $e) {
            error_log('[poll] ' . $e->getMessage());
        }
    }
}
