"""Pracek situs tujuan: cari formulir daftar, petakan kolomnya, deteksi
CAPTCHA & jenis verifikasi, lalu klasifikasikan sesuai konsep:
  A = bisa diproses penuh (formulir biasa, tanpa CAPTCHA)
  B = semi-otomatis (ada CAPTCHA — di MVP belum dieksekusi, dilaporkan)
  C = ditolak (tidak ada formulir daftar / butuh OTP HP / pembayaran / KTP)
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124 Safari/537.36"}
_CAPTCHA = ["recaptcha", "hcaptcha", "turnstile", "g-recaptcha", "cf-challenge",
            "captcha"]
_C_KUAT = ["kode otp", "otp sms", "verifikasi sms", "nomor ktp", "e-ktp",
           "kartu kredit", "credit card", "cvv", "biaya pendaftaran",
           "payment required"]
_B_KATA = ["verifikasi email", "email verification", "cek email anda",
           "check your email"]


def _teks_kolom(tag) -> str:
    bagian = [tag.get("name", ""), tag.get("id", ""), tag.get("placeholder", ""),
              tag.get("aria-label", ""), tag.get("type", "")]
    form = tag.find_parent("form")
    if form is not None:
        lab = form.find("label", attrs={"for": tag.get("id")}) if tag.get("id") else None
        if lab:
            bagian.append(lab.get_text(" ", strip=True))
    return " ".join(b for b in bagian if b).lower()


def _skor_form(form) -> int:
    teks = (form.get("action", "") + " " + form.get("id", "") + " "
            + form.get("class", [""])[0] if isinstance(form.get("class"), list)
            else form.get("action", "") + " " + str(form.get("id", "")))
    teks = teks.lower()
    skor = 0
    if form.find("input", attrs={"type": "password"}):
        skor += 5
    for kata in ["daftar", "register", "signup", "sign-up", "registrasi", "join"]:
        if kata in teks:
            skor += 3
    skor += len(form.find_all("input"))
    return skor


def pracek(url: str, session: requests.Session | None = None) -> dict:
    """Kembalikan dict: kategori, alasan, url_form, method, kolom[], action."""
    s = session or requests.Session()
    try:
        r = s.get(url, headers=_UA, timeout=25)
        r.raise_for_status()
    except Exception as e:
        return {"kategori": "C", "alasan": f"Situs tidak bisa dibuka: {e}"}

    html = r.text
    rendah = html.lower()
    soup = BeautifulSoup(html, "html.parser")

    forms = soup.find_all("form")
    kandidat = [f for f in forms if f.find("input", attrs={"type": "password"})]
    if not kandidat:
        return {"kategori": "C",
                "alasan": "Tidak ditemukan formulir daftar (halaman ini tidak punya "
                          "kolom password). Mungkin pendaftaran ada di halaman lain, "
                          "atau situs hanya menerima pendaftaran lewat aplikasi/undangan."}
    form = max(kandidat, key=_skor_form)

    teks_halaman = soup.get_text(" ", strip=True).lower()
    for kata in _C_KUAT:
        if kata in teks_halaman:
            return {"kategori": "C",
                    "alasan": f"Situs terdeteksi membutuhkan '{kata}' — di luar batas "
                              "bot sesuai konsep (kategori C)."}

    kolom = []
    for tag in form.find_all(["input", "select", "textarea"]):
        tipe = (tag.get("type") or tag.name or "text").lower()
        if tipe in ("submit", "button", "image", "reset"):
            continue
        kolom.append({
            "name": tag.get("name", ""),
            "type": tipe,
            "required": tag.has_attr("required"),
            "teks": _teks_kolom(tag),
        })

    ada_captcha = any(c in rendah for c in _CAPTCHA)
    hasil = {
        "url_form": r.url,
        "action": urljoin(r.url, form.get("action") or r.url),
        "method": (form.get("method") or "get").lower(),
        "kolom": kolom,
        "verifikasi_email": any(k in teks_halaman for k in _B_KATA),
    }
    if ada_captcha:
        hasil.update({"kategori": "B",
                      "alasan": "Formulir memakai CAPTCHA — kategori B (semi-otomatis) "
                                "belum dieksekusi di tahap MVP ini."})
    else:
        hasil.update({"kategori": "A", "alasan": "Formulir biasa tanpa CAPTCHA."})
    return hasil
