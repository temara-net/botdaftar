"""Bot Telegram Daftar Website — titik masuk untuk GitHub Actions.

Model jalan: batch per run (bukan siaga). Tiap run:
ambil update Telegram sejak offset tersimpan -> proses pesan pemilik ->
simpan state (TANPA password) -> selesai.

Env wajib: TG_BOT_TOKEN, OWNER_ID (ID Telegram pemilik).
Env opsional: TG_API_BASE (uji lokal), STATE_PATH, EXECUTOR,
AI_API_KEY + AI_MODEL + AI_BASE_URL (nama acak dari AI; tanpa ini generator lokal).
"""
import os
import re
import sys

from . import names
from .executor import execute
from .precheck import pracek, temukan, _normalisasi_domain
from .state import State
from .telegram import Telegram

_URL = re.compile(r"^https?://\S+$", re.I)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _sapa(nama: str = "") -> str:
    """Sapaan memakai nama profil Telegram pengirim (bukan nama yang
    ditulis permanen di kode) — koreksi pemilik 1 Nov 2026."""
    awal = f"Halo, {nama}. " if nama else "Halo. "
    return (awal + "Bot daftar website siap.\n\n"
            "Kirim /daftar untuk mulai mendaftar ke sebuah website.\n"
            "Kirim /batal kapan saja untuk membatalkan proses yang berjalan.")


def _ringkas_form(info: dict) -> str:
    baris = [f"Kategori: {info['kategori']} — {info['alasan']}",
             f"Halaman: {info['url_form']}", "Kolom formulir:"]
    for k in info["kolom"]:
        wajib = " (wajib)" if k["required"] else ""
        baris.append(f"- {k['name'] or '(tanpa nama)'} [{k['type']}]{wajib}")
    return "\n".join(baris)


def handle(tg: Telegram, st: State, chat_id: int, text: str, nama_pengirim: str = ""):
    c = st.conv(chat_id)
    stage = c.get("stage", "idle")
    t = text.strip()

    if t.lower() in ("/start", "/help"):
        tg.send_message(chat_id, _sapa(nama_pengirim))
        return
    if t.lower() == "/batal":
        st.reset_conv(chat_id)
        tg.send_message(chat_id, "Proses dibatalkan. Kirim /daftar untuk mulai lagi.")
        return
    if t.lower() == "/daftar":
        c.update({"stage": "wait_url"})
        tg.send_message(chat_id, "Kirim NAMA DOMAIN website tujuannya saja "
                                 "(contoh: contoh.com) — bot yang mencarikan halaman "
                                 "daftarnya. Kalau sudah tahu alamat pastinya, URL "
                                 "lengkap halaman daftar juga boleh.")
        return

    if stage == "wait_url":
        norm = _normalisasi_domain(t)
        if not norm:
            tg.send_message(chat_id, "Itu belum berbentuk nama domain. Cukup ketik "
                                     "domainnya saja, contoh: contoh.com — atau /batal.")
            return
        # URL lengkap yang menunjuk langsung ke sebuah halaman -> pracek langsung.
        # Nama domain / URL beranda -> bot menelusuri halaman daftarnya.
        path = ""
        if "://" in t:
            sisa = t.split("://", 1)[1]
            path = sisa.split("/", 1)[1] if "/" in sisa else ""
        langsung = bool(_URL.match(t)) and bool(path.strip("/"))
        if langsung:
            tg.send_message(chat_id, "Memeriksa halaman itu dulu...")
            info = pracek(t)
        else:
            tg.send_message(chat_id, "Mencari halaman daftar di domain itu...")
            info = temukan(t)
        if info["kategori"] == "C":
            st.reset_conv(chat_id)
            tg.send_message(chat_id, f"Tidak bisa diproses.\n\n{info['alasan']}\n\n"
                                     "Kirim /daftar untuk mencoba website lain.")
            return
        if info["kategori"] == "B":
            st.reset_conv(chat_id)
            tg.send_message(chat_id, _ringkas_form(info) + "\n\nKategori B (ada CAPTCHA) "
                                     "belum dieksekusi di tahap ini — sesuai konsep, itu "
                                     "tahap berikutnya. Proses berhenti di sini.")
            return
        c.update({"stage": "wait_email", "info": info})
        ketemu = ""
        if info.get("sumber_pilih"):
            ketemu = (f"Halaman daftarnya ketemu — dicari oleh "
                      f"{'AI' if info['sumber_pilih'] == 'ai' else 'penelusuran bot'}.\n\n")
        tg.send_message(chat_id, ketemu + _ringkas_form(info) + "\n\nSitusnya kategori A dan bisa "
                                                       "diproses. Sekarang kirim EMAIL "
                                                       "yang mau dipakai untuk akun ini "
                                                       "(email kamu sendiri — verifikasi "
                                                       "masuk ke sana).")
        return

    if stage == "wait_email":
        if not _EMAIL.match(t):
            tg.send_message(chat_id, "Format emailnya belum benar. Kirim ulang emailnya, atau /batal.")
            return
        nama, user, sumber = names.buat_nama()
        c.update({"stage": "wait_name", "email": t, "name": nama,
                  "username": user, "ganti": 0})
        tg.send_message(chat_id, f"Nama + username acak (dari {sumber}):\n\n"
                                 f"Nama: {nama}\nUsername: {user}\n\n"
                                 "Balas OK untuk memakai ini, atau GANTI untuk acakan lain "
                                 "(maks 3x).")
        return

    if stage == "wait_name":
        if t.lower() == "ganti":
            if c.get("ganti", 0) >= 3:
                tg.send_message(chat_id, "Batas ganti acakan (3x) habis. Balas OK untuk "
                                         "memakai yang terakhir ini, atau /batal.")
                return
            nama, user, sumber = names.buat_nama()
            c.update({"name": nama, "username": user, "ganti": c.get("ganti", 0) + 1})
            tg.send_message(chat_id, f"Acakan baru (dari {sumber}):\n\nNama: {nama}\n"
                                     f"Username: {user}\n\nBalas OK atau GANTI.")
            return
        if t.lower() == "ok":
            c.update({"stage": "wait_password"})
            tg.send_message(chat_id, "Terakhir: kirim PASSWORD untuk akun baru ini.\n\n"
                                     "Pakai password khusus yang tidak dipakai di tempat "
                                     "lain. Password hanya dipakai selama proses ini "
                                     "berjalan — tidak disimpan bot dan tidak muncul di "
                                     "laporan hasil. Sesudah proses selesai, hapus pesan "
                                     "password ini dari chat.")
            return
        tg.send_message(chat_id, "Balas OK untuk memakai nama itu, atau GANTI untuk acakan lain.")
        return

    if stage == "wait_password":
        password = t  # hanya di memori run ini; TIDAK masuk state
        data = {"name": c.get("name", ""), "username": c.get("username", ""),
                "email": c.get("email", ""), "password": password}
        info = c.get("info", {})
        tg.send_message(chat_id, "Memproses pendaftarannya sekarang...")
        try:
            hasil = execute(info, data)
        except Exception as e:
            hasil = {"ok": False, "alasan": f"eksekutor error: {e}"}
        st.reset_conv(chat_id)  # bersihkan konteks; password tidak pernah ditulis
        if hasil.get("ok"):
            pesan = ("PENDAFTARAN BERHASIL (ada bukti dari halaman tujuan).\n\n"
                     f"Situs: {info.get('url_form', '')}\n"
                     f"Nama: {data['name']}\nUsername: {data['username']}\n"
                     f"Email: {data['email']}\n"
                     f"Dasar: {hasil.get('alasan', '')}\n"
                     f"Halaman akhir: {hasil.get('url_akhir', '')}")
        else:
            pesan = ("PENDAFTARAN TIDAK BERHASIL.\n\n"
                     f"Situs: {info.get('url_form', '')}\n"
                     f"Alasan: {hasil.get('alasan', 'tidak diketahui')}\n"
                     f"Kutipan halaman: {hasil.get('kutipan', '')[:250]}")
        tg.send_message(chat_id, pesan)
        if hasil.get("screenshot"):
            try:
                tg.send_photo(chat_id, hasil["screenshot"],
                              caption="Tangkapan layar halaman terakhir di situs tujuan")
            except Exception as e:
                print(f"[bot] kirim foto gagal: {e}")
        return

    tg.send_message(chat_id, "Kirim /daftar untuk mulai mendaftar ke website.")


def main() -> int:
    token = os.environ.get("TG_BOT_TOKEN", "")
    owner = os.environ.get("OWNER_ID", "")
    if not token or not owner:
        print("SECRETS BELUM DIISI: TG_BOT_TOKEN / OWNER_ID kosong. "
              "Isi di Settings > Secrets and variables > Actions pada repo. Run dilewati.")
        return 0
    tg = Telegram(token, os.environ.get("TG_API_BASE") or None)
    st = State(os.environ.get("STATE_PATH", "state/state.json"))
    updates = tg.get_updates(st.data.get("offset", 0))
    for u in updates:
        st.data["offset"] = int(u["update_id"]) + 1
        msg = u.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        text = msg.get("text") or ""
        if chat_id is None:
            continue
        if str(chat_id) != str(owner):
            print(f"[bot] pesan dari non-pemilik {chat_id} diabaikan")
            continue
        pengirim = msg.get("from") or {}
        nama_pengirim = pengirim.get("first_name") or pengirim.get("username") or ""
        try:
            handle(tg, st, chat_id, text, nama_pengirim)
        except Exception as e:
            print(f"[bot] error memproses pesan: {e}")
            try:
                tg.send_message(chat_id, f"Maaf, ada error saat memproses: {e}")
            except Exception:
                pass
    st.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
