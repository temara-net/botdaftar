<?php
// Titik masuk WEBHOOK — file inilah yang didaftarkan ke Telegram
// lewat set_webhook.php. Telegram mengirim setiap pesan ke sini.
declare(strict_types=1);

$cfg = require __DIR__ . '/config.php';
require __DIR__ . '/includes/telegram.php';
require __DIR__ . '/includes/ai.php';
require __DIR__ . '/includes/store.php';
require __DIR__ . '/includes/handle.php';

// Jaga-jaga: token belum diisi -> jangan proses apa pun.
if (($cfg['telegram_token'] ?? '') === '' || $cfg['telegram_token'] === 'ISI_TOKEN_DARI_BOTFATHER') {
    http_response_code(500);
    echo 'telegram_token belum diisi di config.php';
    exit;
}

// Verifikasi rahasia webhook bila diatur di config.
$secret = (string)($cfg['webhook_secret'] ?? '');
if ($secret !== '') {
    $given = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';
    if (!hash_equals($secret, (string)$given)) {
        http_response_code(403);
        echo 'secret tidak cocok';
        exit;
    }
}

$raw = file_get_contents('php://input');
$update = json_decode((string)$raw, true);
if (!is_array($update)) {
    http_response_code(200); // request kosong/bukan JSON — abaikan diam-diam
    exit;
}

$tg = new TelegramBot($cfg['telegram_token'], $cfg['telegram_api_base'] ?? null);
$ai = new AIClient($cfg);
$store = new ChatStore(__DIR__ . '/data', (int)($cfg['history_limit'] ?? 20));

handle_update($update, $tg, $ai, $store);
http_response_code(200);
echo 'ok';
