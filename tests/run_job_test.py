"""Uji eksekutor job (daftar/executor_job.py): ambil job dari KV tiruan,
hapus job, daftarkan ke situs uji, kirim hasil ke Telegram tiruan.
Jalankan: .venv-daftar/bin/python tests/run_job_test.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SITE_PORT, KV_PORT, TG_PORT = 18083, 18084, 18085
SITE = f"http://127.0.0.1:{SITE_PORT}"
OWNER = 5150
PW = "RahasiaJob#456"

lulus = gagal = 0


def cek(nama, ok, detail=""):
    global lulus, gagal
    if ok:
        lulus += 1
        print(f"  LULUS  {nama}")
    else:
        gagal += 1
        print(f"  GAGAL  {nama} :: {str(detail)[:220]}")


# ---- KV tiruan (bentuk API Cloudflare) ----
KV = {}
KV_HAPUS = []


class KVH(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _key(self):
        return self.path.split("/values/", 1)[-1]

    def do_GET(self):
        k = self._key()
        if k in KV:
            b = KV[k].encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        KV_HAPUS.append(self._key())
        KV.pop(self._key(), None)
        self.send_response(200)
        self.end_headers()


# ---- Telegram tiruan ----
TG = []


class TGH(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8", "replace")
        TG.append((self.path, body))
        b = json.dumps({"ok": True, "result": {}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def main():
    tmp = tempfile.mkdtemp()
    regs = os.path.join(tmp, "regs.jsonl")
    env = dict(os.environ, TESTSERVER_REGS=regs)
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "testserver", "app.py"),
                            str(SITE_PORT)], env=env)
    kv_srv = ThreadingHTTPServer(("127.0.0.1", KV_PORT), KVH)
    tg_srv = ThreadingHTTPServer(("127.0.0.1", TG_PORT), TGH)
    threading.Thread(target=kv_srv.serve_forever, daemon=True).start()
    threading.Thread(target=tg_srv.serve_forever, daemon=True).start()
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(SITE + "/", timeout=1)
                break
            except Exception:
                time.sleep(0.1)

        from daftar.precheck import pracek
        info = pracek(SITE + "/daftar")
        assert info["kategori"] == "A", info

        job = {"chat_id": OWNER, "info": info,
               "data": {"name": "Uji Job", "username": "ujijob1",
                        "email": "job@contoh.id", "password": PW}}
        KV["job:uji123"] = json.dumps(job)

        os.environ.update({
            "JOB_ID": "uji123", "TG_BOT_TOKEN": "token-tiruan",
            "TG_API_BASE": f"http://127.0.0.1:{TG_PORT}/bot-token/",
            "CF_API_BASE": f"http://127.0.0.1:{KV_PORT}/client/v4",
            "CF_ACCOUNT_ID": "ACC", "CF_KV_NS_ID": "NS", "CF_API_TOKEN": "tok",
            "EXECUTOR": "http",
        })
        from daftar import executor_job
        rc = executor_job.main()
        cek("main() rc=0", rc == 0)
        cek("job DIHAPUS dari KV sesudah diambil", "job:uji123" in KV_HAPUS
            and "job:uji123" not in KV, str(KV_HAPUS))
        isi = open(regs, encoding="utf-8").read() if os.path.exists(regs) else ""
        cek("pendaftaran tersimpan di situs uji", "ujijob1" in isi, isi[:120])
        teks = "\n".join(b for _, b in TG)
        cek("hasil BERHASIL dikirim ke pemilik", "PENDAFTARAN BERHASIL" in teks, teks[:200])
        cek("password TIDAK muncul di pesan Telegram mana pun", PW not in teks)
        cek("job kedua (tidak ada) ditangani tenang",
            executor_job.main() == 0)
    finally:
        srv.terminate()
    print(f"\nHASIL: {lulus} lulus, {gagal} gagal")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
