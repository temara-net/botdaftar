"""Uji penemuan halaman daftar dari NAMA DOMAIN (aturan pemilik 1 Nov 2026).

Menjalankan testserver lokal lalu menguji:
 1. temukan('host:port') menemukan /daftar lewat tautan beranda -> kategori A
 2. temukan() di domain yang tidak bisa dibuka -> kategori C jujur
 3. temukan() input bukan domain -> kategori C
 4. Percakapan bot: /daftar lalu ketik domain saja -> lanjut wait_email
 5. URL lengkap ke halaman daftar tetap dipracek langsung (perilaku lama)
Jalankan: .venv-daftar/bin/python tests/run_discovery_test.py
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PORT = 18079
HOST = f"127.0.0.1:{PORT}"
SITE = f"http://{HOST}"

lulus = gagal = 0


def cek(nama, ok, detail=""):
    global lulus, gagal
    if ok:
        lulus += 1
        print(f"  LULUS  {nama}")
    else:
        gagal += 1
        print(f"  GAGAL  {nama} :: {detail}")


class TGStub:
    def __init__(self):
        self.pesan = []

    def send_message(self, chat_id, text):
        self.pesan.append(text)

    def send_photo(self, chat_id, path, caption=""):
        self.pesan.append(f"[foto] {caption}")


def main():
    env = dict(os.environ, TESTSERVER_REGS=os.path.join(tempfile.mkdtemp(), "r.jsonl"))
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "testserver", "app.py"),
                            str(PORT)], env=env)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(SITE + "/", timeout=1)
                break
            except Exception:
                time.sleep(0.1)

        from daftar.precheck import temukan
        from daftar.state import State
        from daftar import bot as botmod

        print("1) Penemuan dari nama domain")
        info = temukan(HOST)
        cek("domain saja -> kategori A", info["kategori"] == "A", info.get("alasan", ""))
        cek("halaman yang ditemukan = /daftar",
            info.get("url_form", "").endswith("/daftar"), info.get("url_form", ""))
        cek("sumber pilih tercatat (penelusuran)",
            info.get("sumber_pilih") == "penelusuran", str(info.get("sumber_pilih")))

        print("2) Kasus gagal jujur")
        mati = temukan("127.0.0.1:9")
        cek("domain tidak bisa dibuka -> C", mati["kategori"] == "C", mati.get("alasan", ""))
        aneh = temukan("bukan domain sama sekali")
        cek("input bukan domain -> C", aneh["kategori"] == "C", aneh.get("alasan", ""))

        print("3) Percakapan: ketik domain saja")
        st = State(os.path.join(tempfile.mkdtemp(), "s.json"))
        tg = TGStub()
        botmod.handle(tg, st, 111, "/daftar")
        botmod.handle(tg, st, 111, HOST)
        cek("stage lanjut ke wait_email",
            st.conv(111).get("stage") == "wait_email", str(st.conv(111)))
        cek("bot menyebut halaman yang ditemukan",
            any("/daftar" in p for p in tg.pesan), " | ".join(tg.pesan)[:200])

        print("4) URL lengkap tetap langsung")
        st2 = State(os.path.join(tempfile.mkdtemp(), "s2.json"))
        tg2 = TGStub()
        botmod.handle(tg2, st2, 222, "/daftar")
        botmod.handle(tg2, st2, 222, SITE + "/daftar")
        cek("URL lengkap -> wait_email juga",
            st2.conv(222).get("stage") == "wait_email", str(st2.conv(222)))
    finally:
        srv.terminate()

    print(f"\nHASIL: {lulus} lulus, {gagal} gagal")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
