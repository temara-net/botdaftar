<?php
// Alat pasang / lepas / cek webhook Telegram.
// Pakai dari browser:
//   set_webhook.php            -> pasang webhook ke webhook_url di config.php
//   set_webhook.php?action=info   -> lihat status webhook saat ini
//   set_webhook.php?action=delete -> lepas webhook (perlu sebelum pakai poll.php)
// HAPUS file ini dari hosting sesudah selesai dipakai, supaya tidak
// dipakai orang lain untuk mengutak-atik webhook bot kamu.
declare(strict_types=1);

$cfg = require __DIR__ . '/config.php';
require __DIR__ . '/includes/telegram.php';

header('Content-Type: text/plain; charset=utf-8');
$tg = new TelegramBot($cfg['telegram_token'], $cfg['telegram_api_base'] ?? null);
$action = $_GET['action'] ?? 'set';

if ($action === 'info') {
    $r = $tg->call('getWebhookInfo');
    echo json_encode($r, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($action === 'delete') {
    $r = $tg->call('deleteWebhook', ['drop_pending_updates' => false]);
    echo ($r['ok'] ?? false) ? "Webhook terlepas.\n" : ('Gagal: ' . json_encode($r) . "\n");
    exit;
}

// action=set (bawaan)
$url = trim((string)($cfg['webhook_url'] ?? ''));
if ($url === '') {
    echo "webhook_url masih kosong di config.php. Isi dulu URL publik bot.php.\n";
    exit;
}
$params = ['url' => $url, 'allowed_updates' => ['message', 'edited_message']];
$secret = (string)($cfg['webhook_secret'] ?? '');
if ($secret !== '') {
    $params['secret_token'] = $secret;
}
$r = $tg->call('setWebhook', $params);
echo ($r['ok'] ?? false)
    ? "Webhook terpasang ke: $url\nBalasan Telegram: " . ($r['description'] ?? 'Webhook was set') . "\n"
    : ('Gagal pasang webhook: ' . json_encode($r) . "\n");
