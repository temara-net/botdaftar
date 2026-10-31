"""Harness uji lokal MVP bot daftar — semua tiruan/lokal, TANPA Telegram asli,
TANPA situs luar. Jalankan dari root repo:
    .venv-daftar/bin/python tests/run_local_test.py   (atau python3 dengan deps)

Menguji:
 1. pracek: /daftar = A, /daftar-captcha = B, /daftar-otp = C, / = C (tak ada form)
 2. mapping kolom situs uji -> name/username/email/password semua terpetakan
 3. eksekutor browser (Playwright): daftar ke situs uji -> berhasil + tersimpan di server uji
 4. eksekutor browser: username 'terpakai' -> gagal dengan alasan penolakan
 5. eksekutor http: daftar -> berhasil juga
 6. state machine penuh lewat Telegram tiruan: /daftar -> URL -> email -> GANTI -> OK
    -> password -> hasil BERHASIL; state tersimpan TIDAK mengandung password;
    pesan dari non-pemilik diabaikan
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SITE_PORT = 18077
TG_PORT = 18078
SITE = f"http://127.0.0.1:{SITE_PORT}"
TG_BASE = f"http://127.0.0.1:{TG_PORT}/"
OWNER = 424242
LAIN = 999

lulus = gagal = 0


def cek(nama, ok, detail=""):
    global lulus, gagal
    if ok:
        lulus += 1
        print(f"  LULUS  {nama}")
    else:
        gagal += 1
        print(f"  GAGAL  {nama}  {detail}")


# ---------- server Telegram tiruan ----------
class TGH(BaseHTTPRequestHandler):
    antre = []       # update masuk (dict)
    terkirim = []    # (method, payload)

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        method = self.path.strip("/")
        if method == "sendPhoto":
            TGH.terkirim.append(("sendPhoto", b"<multipart>"))
            body = json.dumps({"ok": True, "result": {}}).encode()
        else:
            payload = json.loads(raw or b"{}")
            if method == "getUpdates":
                off = payload.get("offset", 0)
                hasil = [u for u in TGH.antre if u["update_id"] >= off]
                body = json.dumps({"ok": True, "result": hasil}).encode()
            else:
                TGH.terkirim.append((method, payload))
                body = json.dumps({"ok": True, "result": {}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def kirim_update(chat_id, teks, uid):
    TGH.antre.append({"update_id": uid, "message": {
        "message_id": uid, "chat": {"id": chat_id, "type": "private"}, "text": teks}})


def teks_terkirim():
    return [p.get("text", "") for m, p in TGH.terkirim if m == "sendMessage"]


# ---------- mulai server-server ----------
tmp = tempfile.mkdtemp(prefix="botdaftar-test-")
regs = os.path.join(tmp, "regs.jsonl")
env_site = dict(os.environ, TESTSERVER_REGS=regs)
proc_site = subprocess.Popen([sys.executable, "testserver/app.py", str(SITE_PORT)],
                             env=env_site, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
tg_srv = ThreadingHTTPServer(("127.0.0.1", TG_PORT), TGH)
threading.Thread(target=tg_srv.serve_forever, daemon=True).start()
for _ in range(50):
    try:
        import urllib.request
        urllib.request.urlopen(SITE + "/", timeout=1)
        break
    except Exception:
        time.sleep(0.1)

try:
    from daftar.precheck import pracek
    from daftar.mapping import petakan
    from daftar.executor import execute_browser, execute_http
    from daftar.state import State
    from daftar.telegram import Telegram
    from daftar import bot as botmod

    print("1) Pracek & klasifikasi")
    a = pracek(SITE + "/daftar")
    cek("situs uji /daftar = kategori A", a["kategori"] == "A", a.get("alasan", ""))
    b = pracek(SITE + "/daftar-captcha")
    cek("situs uji /daftar-captcha = kategori B", b["kategori"] == "B", b.get("alasan", ""))
    c = pracek(SITE + "/daftar-otp")
    cek("situs uji /daftar-otp = kategori C (OTP SMS)", c["kategori"] == "C", c.get("alasan", ""))
    d = pracek(SITE + "/")
    cek("beranda tanpa form = kategori C", d["kategori"] == "C", d.get("alasan", ""))

    print("2) Pemetaan kolom")
    peta = petakan(a["kolom"])
    cek("4 kunci terpetakan (name/username/email/password)",
        set(peta) == {"name", "username", "email", "password"}, str(set(peta)))

    print("3) Eksekutor browser (Playwright)")
    data = {"name": "Uji Browser", "username": "ujibrowser1",
            "email": "uji@contoh.id", "password": "PasswordUji#123"}
    h = execute_browser(a, data)
    cek("daftar via browser berhasil", h["ok"], h.get("alasan", ""))
    cek("screenshot sesudah daftar ada", bool(h.get("screenshot")) and os.path.exists(h["screenshot"]))
    isi = open(regs, encoding="utf-8").read() if os.path.exists(regs) else ""
    cek("server uji menyimpan pendaftaran browser", "ujibrowser1" in isi, isi[:120])

    print("4) Eksekutor browser — kasus ditolak")
    data2 = dict(data, username="terpakai", email="uji2@contoh.id")
    h2 = execute_browser(a, data2)
    cek("username terpakai -> gagal jujur", not h2["ok"] and "sudah digunakan" in h2.get("alasan", "") + h2.get("kutipan", ""),
        h2.get("alasan", ""))

    print("5) Eksekutor HTTP (cadangan)")
    data3 = {"name": "Uji Http", "username": "ujihttp1",
             "email": "uji3@contoh.id", "password": "PasswordUji#123"}
    h3 = execute_http(a, data3)
    cek("daftar via http berhasil", h3["ok"], h3.get("alasan", ""))
    isi = open(regs, encoding="utf-8").read()
    cek("server uji menyimpan pendaftaran http", "ujihttp1" in isi)

    print("6) State machine lewat Telegram tiruan")
    os.environ["TG_BOT_TOKEN"] = "token-tiruan"
    os.environ["OWNER_ID"] = str(OWNER)
    os.environ["TG_API_BASE"] = TG_BASE
    os.environ["EXECUTOR"] = "browser"
    state_path = os.path.join(tmp, "state.json")
    os.environ["STATE_PATH"] = state_path
    PW = "RahasiaUji#987"
    kirim_update(LAIN, "/daftar", 1)                       # non-pemilik: diabaikan
    kirim_update(OWNER, "/daftar", 2)
    kirim_update(OWNER, SITE + "/daftar", 3)
    kirim_update(OWNER, "pemilik@contoh.id", 4)
    kirim_update(OWNER, "GANTI", 5)
    kirim_update(OWNER, "OK", 6)
    kirim_update(OWNER, PW, 7)
    rc = botmod.main()
    cek("main() selesai rc=0", rc == 0)
    semua = "\n".join(teks_terkirim())
    cek("non-pemilik tidak dilayani", semua.count("Kirim NAMA DOMAIN") == 1, semua[:200])
    cek("alur mencapai minta email", "kategori A" in semua and "EMAIL" in semua)
    cek("nama acak ditawarkan + ganti bekerja", semua.count("Nama:") >= 2, semua[:300])
    cek("hasil akhir BERHASIL terkirim", "PENDAFTARAN BERHASIL" in semua, semua[-400:])
    cek("ada kiriman foto screenshot", any(m == "sendPhoto" for m, _ in TGH.terkirim))
    isi_state = open(state_path, encoding="utf-8").read() if os.path.exists(state_path) else ""
    cek("state TIDAK mengandung password", PW not in isi_state)
    cek("state TIDAK mengandung isi chat password di mana pun", "RahasiaUji" not in isi_state)
    isi = open(regs, encoding="utf-8").read()
    cek("pendaftaran dari alur bot tersimpan di server uji", "pemilik@contoh.id" in isi)
finally:
    proc_site.terminate()
    tg_srv.shutdown()

print(f"\nHASIL: {lulus} lulus, {gagal} gagal")
sys.exit(1 if gagal else 0)
