<?php
// ============================================================
// KONFIGURASI BOT TELEGRAM + AI
// Isi file ini sebelum bot dijalankan.
// Token & API key juga bisa diisi lewat environment variable
// (TG_TOKEN, AI_PROVIDER, AI_API_KEY, AI_MODEL) — env menang.
// ============================================================
return [
    // 1) Token dari @BotFather (wajib)
    'telegram_token'  => getenv('TG_TOKEN') ?: 'ISI_TOKEN_DARI_BOTFATHER',

    // 2) Rahasia webhook (opsional, disarankan): teks acak bebas.
    //    Kalau diisi, set_webhook.php mendaftarkannya ke Telegram dan
    //    bot.php menolak request yang header rahasianya tidak cocok.
    'webhook_secret'  => '',

    // 3) URL publik file bot.php — dipakai set_webhook.php
    //    Contoh: 'https://domainkamu.com/bot-telegram/bot.php'
    'webhook_url'     => '',

    // 4) Provider AI — PILIH SENDIRI salah satu: 'gemini' | 'openai' | 'openrouter'
    //    Sengaja TIDAK ada default: bot tidak akan menjawab AI sebelum ini diisi.
    'ai_provider'     => getenv('AI_PROVIDER') ?: '',

    // 5) API key provider yang dipilih di atas (wajib untuk fitur AI)
    'ai_api_key'      => getenv('AI_API_KEY') ?: '',

    // 6) Nama model — isi sesuai provider. Contoh:
    //    gemini     : gemini-2.5-flash
    //    openai     : gpt-4o-mini
    //    openrouter : openai/gpt-4o-mini
    'ai_model'        => getenv('AI_MODEL') ?: '',

    // Kepribadian / batasan bot. Edit bebas.
    'system_prompt'   => 'Kamu adalah asisten AI yang ramah dan membantu. '
        . 'Jawablah dalam Bahasa Indonesia kecuali pengguna memakai bahasa lain. '
        . 'Jawablah singkat dan jelas, kecuali pengguna meminta penjelasan panjang. '
        . 'Jika kamu tidak tahu sesuatu, katakan tidak tahu — jangan mengarang.',

    // Berapa pesan terakhir per pengguna yang diingat sebagai konteks AI.
    'history_limit'   => 20,

    // Override alamat API (hanya untuk pengujian lokal; kosongkan untuk normal)
    'telegram_api_base' => getenv('TG_API_BASE') ?: null,
    'ai_base_url'       => getenv('AI_BASE_URL') ?: null,
];
