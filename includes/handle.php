<?php
// Logika utama: satu update Telegram -> balasan.
// Dipakai bersama oleh bot.php (webhook) dan poll.php (long polling),
// dan oleh test/simulate.php untuk pengujian lokal.

function handle_update(array $update, TelegramBot $tg, AIClient $ai, ChatStore $store): void
{
    $msg = $update['message'] ?? $update['edited_message'] ?? null;
    if (!is_array($msg)) {
        return; // bukan update pesan (join, pin, dll) — abaikan
    }
    $chatId = $msg['chat']['id'] ?? null;
    if ($chatId === null) {
        return;
    }
    $text = trim((string)($msg['text'] ?? ''));

    if ($text === '') {
        $tg->sendMessage($chatId, 'Maaf, aku hanya bisa membaca pesan teks untuk sekarang.');
        return;
    }

    // Pisahkan perintah dari argumennya: "/reset" , "/tanya apa kabar"
    $parts = preg_split('/\s+/', $text, 2);
    $cmd = strtolower($parts[0]);
    // Perintah di grup bisa berbentuk "/start@namabot"
    $cmd = explode('@', $cmd)[0];

    switch ($cmd) {
        case '/start':
            $tg->sendMessage($chatId,
                "Halo! 👋 Aku bot AI.\n\n" .
                "Kirim saja pertanyaan atau ajakan ngobrol, nanti aku jawab pakai AI.\n\n" .
                "Perintah:\n/help — bantuan\n/reset — hapus ingatan percakapan\n/info — provider & model AI yang dipakai");
            return;

        case '/help':
            $tg->sendMessage($chatId,
                "Cara pakai: kirim pesan teks apa saja, aku jawab pakai AI dengan mengingat konteks percakapan.\n\n" .
                "/reset — mulai percakapan baru dari nol\n/info — lihat konfigurasi AI");
            return;

        case '/reset':
            $store->clear($chatId);
            $tg->sendMessage($chatId, 'Ingatan percakapan sudah dihapus. Kita mulai dari awal ya.');
            return;

        case '/info':
            if ($ai->configured()) {
                $tg->sendMessage($chatId, 'Provider: ' . $ai->provider() . "\nModel: " . $ai->model());
            } else {
                $tg->sendMessage($chatId, 'AI belum dikonfigurasi di server (provider / API key / model masih kosong).');
            }
            return;
    }

    // ----- Pesan biasa -> tanya AI -----
    if (!$ai->configured()) {
        $tg->sendMessage($chatId,
            'Maaf, fitur AI belum dikonfigurasi di server. Pemilik bot perlu mengisi ai_provider, ai_api_key, dan ai_model di config.php.');
        return;
    }

    $tg->sendTyping($chatId);
    $history = $store->get($chatId);
    try {
        $answer = $ai->chat($history, $text);
    } catch (AIException $e) {
        error_log('[ai] ' . $e->getMessage());
        // Jangan bocorkan detail error/API key ke pengguna.
        $tg->sendMessage($chatId, 'Maaf, AI sedang tidak bisa dihubungi. Coba lagi sebentar lagi ya.');
        return;
    }

    $store->append($chatId, 'user', $text);
    $store->append($chatId, 'assistant', $answer);
    $tg->sendMessage($chatId, $answer);
}
