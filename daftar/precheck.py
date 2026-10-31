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


def pracek(url: str, session: requests.Session | None = None,
           timeout: int = 25) -> dict:
    """Kembalikan dict: kategori, alasan, url_form, method, kolom[], action."""
    s = session or requests.Session()
    try:
        r = s.get(url, headers=_UA, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        # Pesan untuk PENGGUNA harus bersih — jangan tampilkan teks error
        # teknis mentah dari library (koreksi dari tangkapan layar pemilik
        # 1 Nov 2026: balasan bot memuat tumpukan teks HTTPSConnectionPool).
        detail = f"{type(e).__name__}: {e}"
        if "Failed to resolve" in detail or "NameResolution" in detail:
            alasan = ("Situs tidak bisa dibuka: alamat domainnya tidak "
                      "ditemukan — periksa lagi ejaan domainnya.")
        elif "timeout" in detail.lower() or "timed out" in detail.lower():
            alasan = "Situs tidak bisa dibuka: koneksi ke situsnya kehabisan waktu (timeout)."
        elif "403" in detail:
            alasan = "Situs tidak bisa dibuka: akses ditolak oleh situsnya (HTTP 403)."
        elif "404" in detail:
            alasan = "Halaman itu tidak ditemukan di situsnya (HTTP 404)."
        else:
            alasan = "Situs tidak bisa dibuka dari sini (koneksi gagal)."
        return {"kategori": "C", "alasan": alasan}

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


# ---------- Penemuan halaman daftar dari NAMA DOMAIN saja ----------
# Aturan pemilik (1 Nov 2026): pengguna cukup mengetik nama domain; bot yang
# mencarikan link halaman daftarnya di domain itu.
_JALUR_UMUM = ["/register", "/signup", "/sign-up", "/daftar", "/registrasi",
               "/join", "/create-account", "/auth/register", "/user/register",
               "/account/register", "/pendaftaran", "/members/register"]
_KATA_LINK = ["daftar", "register", "signup", "sign-up", "sign up", "registrasi",
              "join", "gabung", "buat akun", "create account", "buka akun",
              "registration"]


def _normalisasi_domain(teks: str):
    """'contoh.com' / 'https://contoh.com/path' -> (skema|None, host[:port])."""
    t = teks.strip().lower()
    skema = None
    if t.startswith("http://"):
        skema, t = "http", t[7:]
    elif t.startswith("https://"):
        skema, t = "https", t[8:]
    host = t.split("/")[0].split("?")[0].split("#")[0]
    if not host or " " in host or (".." in host):
        return None
    if not re.match(r"^[a-z0-9.-]+(:\d{1,5})?$", host):
        return None
    if "." not in host and not host.startswith("localhost"):
        return None
    return skema, host


def _peringkat_ai(urls: list[str], domain: str) -> list[str] | None:
    """Bila kunci AI terisi, AI memilih urutan kandidat halaman daftar.
    Pilihan AI divalidasi terhadap daftar yang ada; gagal -> None (heuristik)."""
    import os
    key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "")
    base = os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1")
    if not (key and model) or len(urls) < 2:
        return None
    try:
        daftar_teks = "\n".join(f"{i}. {u}" for i, u in enumerate(urls))
        r = requests.post(base.rstrip("/") + "/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": [
                              {"role": "user", "content":
                               f"Di domain {domain}, dari daftar URL berikut, mana yang "
                               f"paling mungkin halaman PENDAFTARAN akun baru? Balas HANYA "
                               f"nomornya.\n{daftar_teks}"}]},
                          timeout=30)
        r.raise_for_status()
        teks = r.json()["choices"][0]["message"]["content"].strip()
        idx = int(re.search(r"\d+", teks).group())
        if 0 <= idx < len(urls):
            pilihan = urls[idx]
            return [pilihan] + [u for u in urls if u != pilihan]
    except Exception as e:
        print(f"[precheck] peringkat AI gagal, pakai penelusuran biasa: {e}")
    return None


def temukan(teks: str, session: requests.Session | None = None) -> dict:
    """Cari halaman daftar dari nama domain (atau URL beranda).

    Strategi: buka beranda -> kumpulkan tautan yang berbau daftar ->
    (AI memilih bila tersedia) -> tambahkan jalur umum -> pracek satu per
    satu sampai ketemu formulir. Hasil dict sama seperti pracek(), plus
    'sumber_pilih': 'ai' | 'penelusuran'.
    """
    norm = _normalisasi_domain(teks)
    if not norm:
        return {"kategori": "C",
                "alasan": "Itu belum berbentuk nama domain. Contoh format: contoh.com"}
    skema, host = norm
    s = session or requests.Session()
    skemas = [skema] if skema else ["https", "http"]
    beranda_url, beranda_html = None, ""
    for sk in skemas:
        try:
            r = s.get(f"{sk}://{host}/", headers=_UA, timeout=15)
            if r.status_code < 500:
                beranda_url, beranda_html = r.url, r.text
                break
        except Exception:
            continue
    if not beranda_url:
        return {"kategori": "C",
                "alasan": f"Domain {host} tidak bisa dibuka dari sini (koneksi gagal "
                          "di https maupun http). Periksa lagi ejaan domainnya."}
    basis = beranda_url.split("?")[0]
    if not basis.endswith("/"):
        basis = basis.rsplit("/", 1)[0] + "/"

    kandidat: list[str] = []
    soup = BeautifulSoup(beranda_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        teks_link = a.get_text(" ", strip=True).lower()
        gab = (href + " " + teks_link).lower()
        if any(k in gab for k in _KATA_LINK):
            u = urljoin(beranda_url, href)
            nu = _normalisasi_domain(u)
            if nu:
                host_k = nu[1].split(":")[0]
                akar = ".".join(host.split(":")[0].split(".")[-2:])
                if (host_k == host.split(":")[0] or host_k.endswith("." + akar)) \
                        and u not in kandidat:
                    kandidat.append(u)
    sumber = "penelusuran"
    urutan_ai = _peringkat_ai(list(kandidat), host)
    if urutan_ai:
        kandidat, sumber = urutan_ai, "ai"
    for jalur in _JALUR_UMUM:
        u = urljoin(basis, jalur.lstrip("/"))
        if u not in kandidat:
            kandidat.append(u)
    kandidat = kandidat[:8]

    terbaik_b = None
    for u in kandidat:
        info = pracek(u, session=s, timeout=12)
        if info["kategori"] == "A":
            info["sumber_pilih"] = sumber
            return info
        if info["kategori"] == "B" and terbaik_b is None:
            terbaik_b = info
    if terbaik_b:
        terbaik_b["sumber_pilih"] = sumber
        return terbaik_b
    return {"kategori": "C", "sumber_pilih": sumber,
            "alasan": f"Sudah ditelusuri di {host} (beranda + {len(kandidat)} kandidat "
                      "tautan/jalur umum), tapi tidak ditemukan halaman pendaftaran "
                      "dengan formulir. Mungkin pendaftaran hanya lewat aplikasi, "
                      "undangan, atau subdomain lain."}
