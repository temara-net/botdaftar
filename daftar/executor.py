"""Eksekutor pendaftaran: mengisi & mengirim formulir di situs tujuan.

Dua backend dengan antarmuka sama:
- browser (Playwright): untuk situs modern/JS. Menghasilkan tangkapan layar.
- http (requests): cadangan untuk formulir HTML klasik bila browser gagal jalan.

Penilaian hasil bersifat jujur: 'ok' hanya bila ada bukti halaman sesudah
daftar (kata sukses / berpindah ke area anggota). Selain itu 'gagal'
dengan alasan + kutipan teks halaman, bukan klaim berhasil.
"""
import os
import re
import tempfile
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .mapping import petakan
from .precheck import _UA

_SUKSES = ["pendaftaran berhasil", "registration successful", "sign up successful",
           "berhasil dibuat", "akun anda telah", "account created", "welcome",
           "selamat datang", "terima kasih telah mendaftar", "thanks for signing up",
           "akun berhasil", "registration complete", "verify your email",
           "verifikasi email anda"]
_GAGAL = ["already taken", "sudah digunakan", "sudah terdaftar", "already exists",
          "invalid", "tidak valid", "error", "gagal", "failed", "wajib diisi",
          "required", "doesn't match", "tidak cocok", "terlalu pendek", "too short"]


def _nilai(data: dict, peta: dict) -> dict[str, str]:
    return {peta[k]["name"]: data[k] for k in peta if k in data and data[k]}


def _nilai_hasil(teks: str, url_awal: str, url_akhir: str) -> tuple[bool, str]:
    t = teks.lower()
    for k in _SUKSES:
        if k in t:
            return True, f"halaman sesudah daftar memuat tanda sukses ('{k}')"
    for k in _GAGAL:
        if k in t:
            return False, f"halaman menampilkan penolakan ('{k}')"
    if url_akhir != url_awal:
        return True, "berpindah halaman sesudah kirim tanpa pesan penolakan"
    return False, "tidak ada bukti keberhasilan di halaman hasil (URL tidak berubah, tidak ada tanda sukses)"


# ---------------- backend HTTP ----------------
def execute_http(info: dict, data: dict) -> dict:
    s = requests.Session()
    r = s.get(info["url_form"], headers=_UA, timeout=25)
    soup = BeautifulSoup(r.text, "html.parser")
    form = None
    for f in soup.find_all("form"):
        if f.find("input", attrs={"type": "password"}):
            form = f
            break
    if form is None:
        return {"ok": False, "alasan": "formulir tidak ditemukan lagi saat eksekusi"}

    payload = {}
    for tag in form.find_all(["input", "select", "textarea"]):
        nama = tag.get("name")
        if not nama:
            continue
        tipe = (tag.get("type") or "text").lower()
        if tipe in ("submit", "button", "image", "reset", "file"):
            continue
        if tipe in ("checkbox", "radio"):
            if tag.has_attr("checked"):
                payload[nama] = tag.get("value", "on")
            continue
        payload[nama] = tag.get("value", "")
    peta = petakan(info["kolom"])
    kurang = [k for k in ("email", "password") if k not in peta]
    if kurang:
        return {"ok": False, "alasan": f"kolom wajib tidak terpetakan: {', '.join(kurang)}"}
    payload.update(_nilai(data, peta))

    action = urljoin(r.url, form.get("action") or r.url)
    method = (form.get("method") or "get").lower()
    try:
        if method == "post":
            resp = s.post(action, data=payload, headers=_UA, timeout=30)
        else:
            resp = s.get(action, params=payload, headers=_UA, timeout=30)
    except Exception as e:
        return {"ok": False, "alasan": f"pengiriman formulir gagal: {e}"}
    teks = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)
    ok, alasan = _nilai_hasil(teks, info["url_form"], resp.url)
    return {"ok": ok, "alasan": alasan, "url_akhir": resp.url,
            "kutipan": teks[:300], "screenshot": None, "backend": "http"}


# ---------------- backend Browser (Playwright) ----------------
def execute_browser(info: dict, data: dict) -> dict:
    from playwright.sync_api import sync_playwright

    peta = petakan(info["kolom"])
    kurang = [k for k in ("email", "password") if k not in peta]
    if kurang:
        return {"ok": False, "alasan": f"kolom wajib tidak terpetakan: {', '.join(kurang)}"}
    nilai = _nilai(data, peta)
    tmp = tempfile.mkdtemp(prefix="botdaftar-")
    shot_akhir = os.path.join(tmp, "sesudah.png")
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        try:
            page.goto(info["url_form"], timeout=45000, wait_until="domcontentloaded")
            for nama_kolom, isi in nilai.items():
                loc = page.locator(f"[name=\"{nama_kolom}\"]").first
                loc.fill(str(isi), timeout=10000)
            tombol = page.locator(
                "button[type=submit], input[type=submit], button:has-text('Daftar'), "
                "button:has-text('Register'), button:has-text('Sign up'), "
                "button:has-text('Sign Up'), button:has-text('Buat Akun')").first
            with page.expect_navigation(timeout=20000, wait_until="domcontentloaded"):
                tombol.click(timeout=10000)
        except Exception as e:
            try:
                page.screenshot(path=shot_akhir)
            except Exception:
                shot_akhir = None
            b.close()
            return {"ok": False, "alasan": f"langkah browser gagal: {str(e)[:200]}",
                    "screenshot": shot_akhir, "backend": "browser"}
        try:
            page.wait_for_timeout(1500)
            teks = page.inner_text("body")
        except Exception:
            teks = ""
        try:
            page.screenshot(path=shot_akhir)
        except Exception:
            shot_akhir = None
        url_akhir = page.url
        b.close()
    ok, alasan = _nilai_hasil(teks, info["url_form"], url_akhir)
    return {"ok": ok, "alasan": alasan, "url_akhir": url_akhir,
            "kutipan": teks[:300], "screenshot": shot_akhir, "backend": "browser"}


def execute(info: dict, data: dict) -> dict:
    """Pilih backend: EXECUTOR env ('browser'/'http'), bawaan browser dengan
    cadangan http bila browser tidak bisa jalan sama sekali."""
    pilihan = os.environ.get("EXECUTOR", "browser").lower()
    if pilihan == "http":
        return execute_http(info, data)
    try:
        return execute_browser(info, data)
    except Exception as e:
        print(f"[executor] browser tidak jalan ({e}); cadangan http")
        hasil = execute_http(info, data)
        hasil["catatan_backend"] = "browser gagal jalan; hasil dari backend http"
        return hasil
