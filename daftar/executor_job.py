"""Eksekutor job pendaftaran — dijalankan GitHub Actions (execute.yml)
saat dipicu Worker webhook lewat workflow_dispatch (input: job_id SAJA).

Alur: ambil job dari Cloudflare KV -> HAPUS job-nya lebih dulu (password
tidak berlama-lama di KV) -> jalankan pendaftaran (daftar.executor) ->
kirim hasil + screenshot langsung ke Telegram pemilik.

Env wajib: JOB_ID, TG_BOT_TOKEN, CF_ACCOUNT_ID, CF_KV_NS_ID, CF_API_TOKEN.
Env opsional: TG_API_BASE (uji lokal), EXECUTOR (browser/http).
"""
import os
import sys

from . import kvjob
from .executor import execute
from .telegram import Telegram


def main() -> int:
    job_id = os.environ.get("JOB_ID", "")
    token = os.environ.get("TG_BOT_TOKEN", "")
    if not job_id or not token:
        print("ENV BELUM LENGKAP: JOB_ID / TG_BOT_TOKEN kosong. Berhenti.")
        return 0
    tg = Telegram(token, os.environ.get("TG_API_BASE") or None)

    job = kvjob.ambil_job(job_id)
    if job is None:
        print(f"[executor_job] job {job_id} tidak ditemukan / sudah kedaluwarsa.")
        return 0
    kvjob.hapus_job(job_id)  # hapus SEBELUM eksekusi: satu kali pakai

    chat_id = job["chat_id"]
    info = job.get("info", {})
    data = job.get("data", {})
    try:
        hasil = execute(info, data)
    except Exception as e:
        hasil = {"ok": False, "alasan": f"eksekutor error: {e}"}

    if hasil.get("ok"):
        pesan = ("PENDAFTARAN BERHASIL (ada bukti dari halaman tujuan).\n\n"
                 f"Situs: {info.get('url_form', '')}\n"
                 f"Nama: {data.get('name', '')}\nUsername: {data.get('username', '')}\n"
                 f"Email: {data.get('email', '')}\n"
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
            print(f"[executor_job] kirim foto gagal: {e}")
    print(f"[executor_job] selesai ok={hasil.get('ok')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
