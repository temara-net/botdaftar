"""Situs daftar UJI lokal (stdlib saja) — sasaran tes bot, bukan untuk publik.
Jalankan: python3 testserver/app.py [port]   (bawaan 18077)
Halaman:
  /daftar          formulir kategori A (nama, username, email, password, csrf)
  /daftar-captcha  formulir + penanda recaptcha -> kategori B
  /daftar-otp      formulir + syarat kode OTP SMS -> kategori C
POST /daftar menyimpan ke berkas JSONL (env TESTSERVER_REGS, bawaan /tmp/regs.jsonl)
dan menampilkan halaman sukses. Username 'terpakai' selalu ditolak (uji gagal).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

REGS = os.environ.get("TESTSERVER_REGS", "/tmp/regs.jsonl")

FORM = """<!doctype html><html><head><title>Daftar - Situs Uji</title></head>
<body><h1>Buat Akun</h1>
<form method="post" action="/daftar">
<input type="hidden" name="csrf" value="tok123">
<label>Nama Lengkap <input type="text" name="nama_lengkap" required></label>
<label>Username <input type="text" name="username" required></label>
<label>Email <input type="email" name="email" required></label>
<label>Password <input type="password" name="password" required></label>
<button type="submit">Daftar</button>
</form>{extra}</body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _kirim(self, html, kode=200):
        b = html.encode()
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/daftar":
            self._kirim(FORM.format(extra=""))
        elif self.path == "/daftar-captcha":
            self._kirim(FORM.format(
                extra='<div class="g-recaptcha" data-sitekey="uji"></div>'))
        elif self.path == "/daftar-otp":
            self._kirim(FORM.format(
                extra="<p>Kami akan mengirim kode OTP SMS ke nomor Anda untuk verifikasi.</p>"))
        elif self.path == "/":
            self._kirim("<html><body><h1>Beranda Situs Uji</h1></body></html>")
        else:
            self._kirim("<html><body>404</body></html>", 404)

    def do_POST(self):
        if self.path != "/daftar":
            self._kirim("<html><body>404</body></html>", 404)
            return
        n = int(self.headers.get("Content-Length", 0))
        data = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
        if data.get("username") == "terpakai":
            self._kirim("<html><body><p>Maaf, username sudah digunakan. "
                        "Silakan pilih username lain.</p></body></html>")
            return
        wajib = ["nama_lengkap", "username", "email", "password"]
        if any(not data.get(k) for k in wajib) or data.get("csrf") != "tok123":
            self._kirim("<html><body><p>Error: semua kolom wajib diisi dengan benar.</p></body></html>")
            return
        with open(REGS, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
        self._kirim(f"<html><body><h1>Pendaftaran Berhasil</h1>"
                    f"<p>Selamat datang, {data['nama_lengkap']}! Akun anda telah dibuat.</p>"
                    f"</body></html>")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18077
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
