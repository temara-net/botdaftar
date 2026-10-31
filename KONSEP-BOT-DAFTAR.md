# KONSEP — Bot Telegram untuk Daftar ke Website Tujuan
Status: KONSEP, menunggu persetujuan pemilik sebelum dibangun (31 Okt 2026)

## Keputusan pemilik yang sudah tetap (bukan tebakan Ara)
1. VPN: SKIP — dibatalkan, tidak dipakai sama sekali. Bot berjalan dari IP asli server/komputer pelaksana.
2. Website tujuan: diketik sendiri oleh pengguna bot (klien) — bot tidak punya daftar website bawaan.
3. Nama akun / username: ACAK, dibuat oleh AI/generator — TIDAK diidentikkan dengan nama pemilik, nama pemilik, atau brand. Pengguna boleh minta ganti acakan sebelum proses jalan.
4. Email: dimasukkan sendiri oleh pengguna bot (email miliknya, karena verifikasi masuk ke email itu).
5. Password akun baru: DIISI SENDIRI OLEH KLIEN/pengguna bot (keputusan pemilik 31 Okt 23:18). Bot TIDAK membuatkan password dan TIDAK menyimpannya.
6. Pemakai bot: HANYA PEMILIK SENDIRI DULU (keputusan pemilik 31 Okt 23:19). Klien/publik tidak bisa memakai bot ini; membuka untuk klien = tahap terpisah yang menunggu perintah pemilik sendiri.
7. Tempat eksekusi: GITHUB (GitHub Actions) — BUKAN VPS (keputusan pemilik 31 Okt 23:19: "yang penting bisa dijalankan via github", "bukan via vps").
8. Konsep ini diselesaikan & disetujui dulu; koding dimulai hanya sesudah pemilik menyetujui.

## Konsekuensi jujur dari jalan di GitHub Actions (bukan server menyala terus)
GitHub Actions bukan server 24 jam. Bot bisa jalan di sana dengan model **batch per pemicu**, bukan siaga real-time:
- Setiap tugas daftar = satu workflow run: runner GitHub menyala, menjalankan browser otomatis (Playwright), memproses pendaftaran, mengirim hasil ke Telegram pemilik, lalu mati. Ini pas untuk pola pakai pribadi (daftar sesekali, dipicu saat dibutuhkan).
- Percakapan Telegram ditangani dengan pemicu terjadwal/dispatch: balasan bisa tertunda beberapa menit mengikuti jadwal run (jadwal tercepat Actions ±5 menit dan bisa molor) — BUKAN obrolan instan detik itu juga. Untuk pola "perintah → tunggu → hasil", ini masih masuk akal; untuk chat interaktif cepat, tidak.
- Semua rahasia (token bot Telegram, kunci AI, ID Telegram pemilik) disimpan di **GitHub Secrets** — tidak tertulis di kode/repo.
- Keadaan percakapan & antrean tugas disimpan sebagai berkas state terenkripsi di repo state terpisah/artefak run, karena runner dibuang sesudah tiap run.
- Kuota menit Actions: repo **publik** = menit runner standar gratis tanpa batas kuota bulanan; repo **privat** = kuota gratis terbatas (2.000 menit/bulan di paket Free) sehingga jadwal pemicu tidak boleh terlalu rapat. Pilihan public/private ini = keputusan deploy repo yang masih menunggu pemilik (sekaligus untuk push perdana bot dasar).

## Keputusan deploy repo (pemilik 31 Okt 23:20)
- Visibilitas repo: **PUBLIC** — alasan pemilik: menit GitHub Actions gratis tanpa batas. Kode boleh terlihat publik; semua rahasia tetap di GitHub Secrets, tidak di kode.
- Nama repo: **botdaftar** (pilihan pemilik 31 Okt 23:22 — nama pendek, menggantikan usulan panjang telegram-bot-ai / bot-telegram-daftar).

## Status keputusan
Semua keputusan konsep utama DAN deploy SUDAH diputuskan pemilik. Yang tersisa hanya persetujuan pemilik atas konsep ini sebagai keseluruhan sebelum koding dimulai.

## Pemeriksaan kenyataan (kenapa konsepnya berbentuk begini)
Tidak ada bot yang bisa daftar ke SEMUA website secara buta — tiap situs beda formulir, beda token keamanan, beda verifikasi. Karena itu bot WAJIB mengklasifikasi situs dulu sebelum mengumpulkan data:

- **Kategori A — bisa diproses penuh:** formulir HTML/JS biasa, tanpa CAPTCHA, verifikasi tidak ada atau via tautan/kode email yang bisa diteruskan pengguna ke bot.
- **Kategori B — semi-otomatis:** ada CAPTCHA / verifikasi yang harus diselesaikan manusia. Bot mengisi semua kolom, lalu BERHENTI dan menyerahkan langkah itu ke pengguna (kirim tangkapan layar + instruksi), lanjut lagi sesudah pengguna konfirmasi selesai.
- **Kategori C — tidak bisa / ditolak bot:** butuh OTP SMS ke nomor tak dikenal, verifikasi identitas/KTP, pembayaran, CAPTCHA yang mengunci otomatisasi, atau syarat layanan situs yang melarang pendaftaran otomatis. Bot menolak dengan alasan jelas — bukan memaksa.

Bot TIDAK memecahkan CAPTCHA, TIDAK mengakali anti-bot, TIDAK membuat akun massal — satu proses = satu akun untuk satu pengguna. Ini batas desain, bukan kekurangan sementara.

## Alur percakapan di Telegram (mesin status per pengguna)
1. `/daftar` — pengguna cukup mengetik **nama domain** website tujuan (perintah pemilik 1 Nov 2026; URL lengkap tetap diterima). Bot/AI mencarikan link halaman daftarnya di domain itu: menelusuri tautan berbau daftar di beranda + jalur umum (/register, /daftar, /signup, ...); bila kunci AI tersedia, AI yang memilih kandidat terbaiknya.
2. **Pracek situs:** bot membuka halaman daftar yang ditemukan, memetakan kolomnya, mendeteksi CAPTCHA & jenis verifikasi → bot mengumumkan kategori (A/B/C) + kolom apa saja yang akan diisi. Kategori C berhenti di sini (termasuk bila halaman daftar tidak ditemukan sama sekali).
3. Bot minta **email** dari pengguna (validasi format; email tidak disimpan sesudah proses selesai kecuali di laporan hasil milik pengguna itu sendiri).
4. Bot **menghasilkan nama/username acak via AI** (nama tampilan + username turunan), ditampilkan ke pengguna → pengguna bisa `OK` atau `Ganti` (maks 3x ganti, sesudah itu ketik sendiri).
5. Bot minta **password dari klien sendiri**, dengan peringatan sebelum mengetik: pakai password khusus untuk akun ini, jangan password email/password utama yang dipakai di tempat lain. Password hanya hidup di memori proses selama pendaftaran berjalan — tidak ditulis ke log, tidak disimpan sesudah proses selesai, dan TIDAK tampil di laporan hasil (klien sudah tahu passwordnya sendiri).
6. Bila formulir punya kolom lain (tanggal lahir, negara, dsb.): bot memetakan otomatis dari konteks; yang tidak bisa ditebak ditanyakan satu per satu. Kolom yang situs tandai wajib tapi tidak dikenal → proses berhenti jujur, bukan dikarang.
7. Ringkasan akhir ditampilkan → pengguna tekan **Proses** / **Batal**. Tidak ada pengiriman tanpa konfirmasi ini.
8. **Eksekusi:** pekerja browser otomatis membuka formulir, mengisi, mengirim. Tangkapan layar diambil di titik penting.
9. Verifikasi (bila ada): Kategori B — bot berhenti, pengguna menyelesaikan CAPTCHA / klik tautan email / kirim kode yang masuk ke emailnya ke bot; bot lanjut.
10. **Hasil akhir** dikirim ke pengguna: BERHASIL (situs, username, email, waktu, tangkapan layar halaman sesudah daftar) atau GAGAL (tahap ke berapa + alasan dalam bahasa sederhana + tangkapan layar titik gagalnya).

## Peran AI (tiga, tidak lebih)
1. Membuat nama/username acak yang wajar (bukan nama pemilik/brand).
2. Memetakan kolom formulir asing ke data yang tersedia (mis. kolom "Full Name", "Nama Lengkap", "Display name" semuanya dikenali sebagai nama).
3. Menerjemahkan pesan hasil/error dari situs menjadi penjelasan sederhana berbahasa Indonesia untuk pengguna.

## Arsitektur
- **Muka Telegram (PHP, dari bot dasar yang sudah dibangun):** percakapan, mesin status, antrean tugas. Jalan webhook (hosting) atau polling.
- **Pekerja eksekusi (browser otomatis, mis. Playwright):** membuka situs tujuan & mengisi formulir. Jalan sebagai job **GitHub Actions** per tugas (keputusan pemilik: via GitHub, bukan VPS) — runner sementara, mati sesudah tugas selesai.
- **Muka Telegram di model GitHub:** tidak ada proses siaga; update Telegram diambil saat workflow berjalan (terjadwal/dispatch), diproses, dibalas, lalu run selesai.
- **Penyimpanan sesi:** status langkah per pengguna. Password klien hanya di memori proses selama pendaftaran berjalan — tidak masuk log, tidak masuk laporan hasil, hilang sesudah proses selesai.
- **Daftar putih pengguna:** hanya ID Telegram milik pemilik yang bisa memicu proses (kunci pemilik). ID itu dicatat saat pemasangan pertama (pemilik membuka bot, bot mencatat ID pengirim pertama yang mengklaim kepemilikan dengan kode sekali pakai dari file konfigurasi). Selain ID itu bot menolak semua orang. Tidak ada sistem klien/publik di tahap ini.
- **Catatan proses (log):** waktu, situs, kategori, hasil — TANPA kredensial.

## Keamanan & kejujuran hasil
- Pesan berisi password di Telegram diminta dihapus pengguna sesudah proses; bot tidak menulis password ke log.
- Setiap kegagalan dilaporkan apa adanya dengan tahap + bukti tangkapan layar; bot tidak pernah melaporkan "berhasil" tanpa bukti halaman sesudah-daftar.
- Satu pengguna = satu proses berjalan pada satu waktu (antre bila bersamaan).

## Tahap pembangunan (sesudah konsep disetujui)
1. MVP: kategori A saja + alur percakapan penuh + halaman daftar uji milik sendiri sebagai sasaran tes pertama.
2. Kategori B: serah-terima CAPTCHA/verifikasi ke pengguna.
3. Uji penerimaan: halaman uji sendiri + 2–3 situs nyata sederhana yang pemilik tunjuk, diuji dari HP pemilik.

## Bukti konsep bot dasar (sudah ada, bukan bagian konsep ini)
Bot Telegram + AI generik sudah dibangun lokal & lolos harness simulasi 22/22 (server tiruan, belum uji layanan asli); repo Git lokal commit 88395de siap push — push menunggu akun GitHub aktif.
