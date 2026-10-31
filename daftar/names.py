"""Generator nama + username ACAK untuk akun baru.

Aturan pemilik: nama TIDAK diidentikkan dengan nama pemilik/brand.
Sumber nama: AI bila kunci AI tersedia (env AI_API_KEY + AI_MODEL),
selain itu generator lokal dari daftar kata. Keduanya acak.
"""
import os
import random
import re

import requests

_DEPAN = ["Andini", "Bagas", "Citra", "Dimas", "Eka", "Fajar", "Gita", "Hadi",
          "Intan", "Joko", "Kartika", "Lukman", "Maya", "Nanda", "Oscar",
          "Putri", "Rian", "Sari", "Teguh", "Utami", "Vina", "Wahyu",
          "Yusuf", "Zahra", "Rama", "Sinta", "Bima", "Laras", "Galih", "Nadia"]
_BELAKANG = ["Pratama", "Saputra", "Wulandari", "Nugroho", "Anggraini",
             "Firmansyah", "Maharani", "Setiawan", "Handayani", "Prabowo",
             "Lestari", "Ramadhan", "Fitriani", "Gunawan", "Puspita",
             "Hakim", "Nugraha", "Salim", "Maulana", "Pertiwi"]


def _lokal(rng: random.Random) -> tuple[str, str]:
    nama = f"{rng.choice(_DEPAN)} {rng.choice(_BELAKANG)}"
    user = re.sub(r"[^a-z0-9]", "", nama.lower().replace(" ", rng.choice(["", ".", "_"])))
    user = user[:18] + str(rng.randint(10, 999))
    return nama, user


def _ai(rng: random.Random) -> tuple[str, str] | None:
    key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "")
    base = os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1")
    if not (key and model):
        return None
    try:
        r = requests.post(base.rstrip("/") + "/chat/completions",
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": [
                              {"role": "user", "content":
                               "Buat SATU nama orang Indonesia fiktif yang acak dan umum "
                               "(bukan nama tokoh terkenal) beserta username huruf kecil "
                               "tanpa spasi. Balas HANYA dengan format: Nama Lengkap|username"}]},
                          timeout=30)
        r.raise_for_status()
        teks = r.json()["choices"][0]["message"]["content"].strip()
        nama, user = teks.split("|", 1)
        nama = nama.strip().title()
        user = re.sub(r"[^a-z0-9._]", "", user.strip().lower())[:24]
        if len(nama) >= 3 and len(user) >= 3:
            return nama, user
    except Exception as e:
        print(f"[names] AI gagal, pakai generator lokal: {e}")
    return None


def buat_nama() -> tuple[str, str, str]:
    """Kembalikan (nama, username, sumber) — sumber: 'ai' atau 'lokal'."""
    rng = random.SystemRandom()
    hasil = _ai(rng)
    if hasil:
        return hasil[0], hasil[1], "ai"
    nama, user = _lokal(rng)
    return nama, user, "lokal"
