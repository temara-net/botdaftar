# Panduan Aktivasi Bot Daftar (GitHub Actions)

Bot berjalan sebagai workflow terjadwal di repo ini (`.github/workflows/bot.yml`,
tiap 10 menit + bisa dipicu manual). Supaya hidup, isi 2 rahasia ini —
tanpa keduanya workflow hanya mencetak "SECRETS BELUM DIISI" dan berhenti wajar.

## 1. Buat bot Telegram di BotFather
1. Chat ke **@BotFather** → `/newbot` → ikuti langkahnya → simpan **token** bot.
2. Chat ke **@userinfobot** untuk melihat **ID Telegram kamu** (angka). Catat.

## 2. Isi Secrets repo
Di repo ini: **Settings → Secrets and variables → Actions → New repository secret**

| Nama | Isi |
|---|---|
| `TG_BOT_TOKEN` | Token dari BotFather |
| `OWNER_ID` | ID Telegram kamu (hanya ID ini yang dilayani bot) |
| `AI_API_KEY` | (opsional) kunci AI untuk nama acak dari AI; kosong = generator lokal |
| `AI_MODEL` | (opsional) nama model untuk AI_API_KEY |
| `AI_BASE_URL` | (opsional) bawaan https://openrouter.ai/api/v1 |

## 3. Picu run pertama
Tab **Actions** → workflow **botdaftar** → **Run workflow**. Sesudah itu jadwal
10-menit berjalan sendiri. Chat bot kamu: `/start`, lalu `/daftar`.

## Cara pakai (alur sesuai konsep)
`/daftar` → kirim URL halaman pendaftaran → bot memeriksa & mengklasifikasikan
situs (A diproses, B/C berhenti dengan alasan) → kirim email kamu → bot menawarkan
nama+username acak (balas OK / GANTI) → kirim password akun baru (tidak disimpan
bot, tidak muncul di laporan) → bot memproses → hasil + tangkapan layar dikirim.

## Uji lokal (tanpa Telegram asli)
```
python3 -m venv .venv-daftar && .venv-daftar/bin/pip install -r daftar/requirements.txt playwright
.venv-daftar/bin/playwright install chromium
.venv-daftar/bin/python tests/run_local_test.py
```
Menguji pracek/klasifikasi, pemetaan kolom, eksekutor browser & HTTP, dan alur
percakapan penuh lewat server Telegram tiruan + situs daftar uji (`testserver/`).
