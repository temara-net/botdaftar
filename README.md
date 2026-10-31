# Bot Telegram + AI (PHP)

Bot Telegram yang menjawab pesan memakai AI, dengan ingatan percakapan per pengguna.
Provider AI dipilih sendiri oleh pemilik bot di `config.php` — tidak ada provider bawaan/default.

Provider yang didukung:

- **Gemini** (Google AI Studio)
- **OpenAI**
- **OpenRouter**

## Fitur

- Perintah `/start`, `/help`, `/reset` (hapus ingatan percakapan), `/info` (provider & model aktif)
- Pesan biasa dijawab AI, dengan riwayat percakapan sebagai konteks (bawaan: 20 pesan terakhir)
- Indikator *typing* saat AI berpikir
- Pesan jawaban panjang otomatis dipecah mengikuti batas 4096 karakter Telegram
- Dua mode jalan: **webhook** (hosting HTTPS) atau **long polling** (lokal/VPS, tanpa hosting)
- Bila AI belum dikonfigurasi atau provider gagal dihubungi, bot menjawab jujur dengan pesan sopan — detail error hanya masuk log server, tidak bocor ke pengguna

## Syarat

- PHP 8.1+ dengan ekstensi `curl` dan `mbstring`
- Token bot dari [@BotFather](https://t.me/BotFather)
- API key salah satu provider AI di atas

## Langkah Pasang

### 1. Buat bot & ambil token

1. Chat ke **@BotFather** di Telegram → `/newbot`
2. Ikuti langkahnya, simpan token yang diberikan

### 2. Isi konfigurasi

Edit `config.php`:

```php
'telegram_token' => 'TOKEN_DARI_BOTFATHER',
'ai_provider'    => 'gemini',          // atau 'openai' / 'openrouter' — pilih sendiri
'ai_api_key'     => 'API_KEY_KAMU',
'ai_model'       => 'gemini-2.5-flash', // sesuaikan dengan provider
'webhook_url'    => 'https://domainkamu.com/path/bot.php', // hanya untuk mode webhook
```

Contoh model: Gemini `gemini-2.5-flash`, OpenAI `gpt-4o-mini`, OpenRouter `openai/gpt-4o-mini`.

Token & API key juga bisa diisi lewat environment variable: `TG_TOKEN`, `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`.

### 3a. Mode Webhook (hosting)

1. Upload semua file ke hosting (HTTPS wajib)
2. Pastikan folder `data/` bisa ditulis server
3. Buka `set_webhook.php` di browser untuk mendaftarkan webhook
4. Cek dengan `set_webhook.php?action=info`, lepas dengan `set_webhook.php?action=delete`
5. **Hapus `set_webhook.php` dari hosting sesudah selesai**
6. Chat bot kamu: `/start`

Opsional: isi `webhook_secret` di `config.php` dengan teks acak — Telegram akan menandatangani setiap request dan `bot.php` menolak yang tanda tangannya tidak cocok.

### 3b. Mode Long Polling (lokal / VPS)

```bash
php poll.php
```

Tidak butuh hosting/HTTPS. Webhook harus dalam keadaan terlepas (lihat langkah 3a poin 4). Berhenti dengan `Ctrl+C`.

## Uji Lokal

Harness uji memakai server tiruan Telegram & AI di localhost — tidak menyentuh layanan asli:

```bash
php test/simulate.php
```

Menguji: balasan `/start`, jawaban AI untuk 3 provider, penyimpanan & `/reset` riwayat, `/info`, kasus AI belum dikonfigurasi, kasus provider tidak terjangkau, dan pemecahan pesan panjang.

## Struktur

```
bot.php            titik masuk webhook
poll.php           mode long polling (CLI)
set_webhook.php    alat pasang/lepas/cek webhook
config.php         semua pengaturan (token, provider, model, prompt)
includes/
  telegram.php     klien Telegram Bot API
  ai.php           klien AI multi-provider
  store.php        riwayat percakapan per chat (file JSON)
  handle.php       logika utama: update -> balasan
data/              riwayat percakapan (tidak ikut Git)
test/simulate.php  harness uji lokal
```

## Keamanan

- Jangan pernah commit token / API key asli ke Git
- Jangan bagikan token BotFather ke siapa pun; bila bocor, cabut lewat @BotFather → `/revoke`
- Untuk skala besar, ganti `ChatStore` (file JSON) dengan database — antarmukanya (`get`/`append`/`clear`) memang dibuat untuk itu
