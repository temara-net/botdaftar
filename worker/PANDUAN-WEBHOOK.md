# Panduan Aktivasi Webhook botdaftar (Cloudflare Workers)

Model baru (keputusan pemilik 1 Nov 2026): percakapan Telegram dijawab Worker
yang selalu-nyala di Cloudflare (instan, tanpa VPS, gratis). Eksekusi
pendaftaran (browser) tetap di GitHub Actions, tetapi dipicu SAAT ITU JUGA
oleh Worker — bukan jadwal. Sesudah aktivasi ini selesai, workflow polling
`bot.yml` dihapus (jadwalnya terbukti tidak jalan sendiri).

## Gambaran alir

Telegram → (webhook) → Worker (KV: state percakapan + job sesaat)
  → password dikirim pengguna → Worker menulis job:<id> di KV (TTL 15 mnt)
  → Worker memicu workflow `execute.yml` (input: job_id saja)
  → Actions: ambil job dari KV → hapus job → daftar via browser
  → hasil + screenshot dikirim Actions langsung ke Telegram.

## Langkah aktivasi (sekali saja)

### 1. Akun Cloudflare (pemilik, via Google)
Daftar di https://dash.cloudflare.com/sign-up (bisa "Continue with Google"
memakai akun yang sama dengan GitHub).

### 2. Buat KV namespace
Dashboard Cloudflare → Storage & Databases → KV → Create namespace,
nama: `botdaftar`. Catat **Namespace ID**-nya.

### 3. Buat GitHub token khusus dispatch (pemilik, di GitHub)
GitHub → Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate:
- Resource owner: temara-net; Repository access: hanya `botdaftar`
- Permissions → Actions: **Read and write**
Token ini hanya bisa memicu workflow repo botdaftar. Catat nilainya
(jangan kirim lewat chat — ditempel langsung di langkah 5).

### 4. Buat Worker
Dashboard Cloudflare → Workers & Pages → Create → Worker, nama `botdaftar`
→ Deploy → Edit code → ganti isinya dengan `worker/worker.js` dari repo ini
→ Save and deploy. Catat URL-nya (bentuk: https://botdaftar.<subdomain>.workers.dev).

Di Settings → Variables and Secrets, tambahkan:
| Nama | Jenis | Isi |
|---|---|---|
| `TG_BOT_TOKEN` | Secret | token BotFather bot daftarwebot |
| `OWNER_ID` | Secret | ID Telegram pemilik |
| `WEBHOOK_SECRET` | Secret | kata acak panjang (bebas, ciptakan baru) |
| `GH_TOKEN` | Secret | token GitHub dari langkah 3 |

Di Settings → Bindings → Add → KV namespace: variable name `BOTKV`,
namespace = `botdaftar` (langkah 2).

### 5. Arahkan webhook Telegram ke Worker
Sekali, dari browser/terminal (ganti isinya):
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL_WORKER>&secret_token=<WEBHOOK_SECRET>
```
Balasan `{"ok":true,"description":"Webhook was set"}` = berhasil.
Catatan: begitu webhook terpasang, metode getUpdates (dipakai model
polling lama) otomatis tidak bekerja — itu memang tujuannya.

### 6. Secret GitHub untuk eksekutor (repo botdaftar → Settings → Secrets → Actions)
Tambahkan 3 secret baru (selain TG_BOT_TOKEN & OWNER_ID yang sudah ada):
| Nama | Isi |
|---|---|
| `CF_ACCOUNT_ID` | ID akun Cloudflare (di dashboard, kolom kanan beranda Workers) |
| `CF_KV_NS_ID` | Namespace ID dari langkah 2 |
| `CF_API_TOKEN` | API token Cloudflare: My Profile → API Tokens → Create Token → pakai template "Edit Cloudflare Workers"? Tidak — buat Custom token: Permissions: Account → Workers KV Storage → Edit; Account Resources: akun pemilik. |

### 7. Matikan model polling lama
Commit yang menghapus `.github/workflows/bot.yml` (atau beri tahu Ara —
Ara yang push). `execute.yml` adalah satu-satunya workflow aktif sesudah ini.

### 8. Uji
Chat ke bot: `/start` harus dibalas DALAM HITUNGAN DETIK tanpa siapa pun
memicu apa pun. Lalu `/daftar` → ketik domain → lanjutkan alur sampai
password → hasil eksekusi tiba ±1–3 menit kemudian.

## Yang sengaja TIDAK berubah dari konsep
- Khusus pemilik (OWNER_ID). Nama acak, bukan nama pemilik.
- Pengguna cukup mengetik nama domain; bot mencarikan halaman daftarnya.
- Kategori A/B/C tetap: B (CAPTCHA) berhenti & dilaporkan; C ditolak.
- Password: tidak di Git, tidak di state, tidak di log, tidak jadi input
  workflow. Ia hanya hidup di pesan Telegram pengguna, job KV (TTL 15
  menit, dihapus eksekutor sebelum bekerja), dan memori proses eksekusi.
