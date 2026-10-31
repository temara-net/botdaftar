"""Petakan kolom formulir asing ke data pendaftaran yang tersedia.
Kunci data: name, username, email, password. Kolom lain dikembalikan
sebagai 'unknown' — bot tidak mengarang isian (aturan konsep)."""

_PETA = [
    ("email", ["email", "e-mail", "surel", "mail"]),
    ("password", ["password", "kata sandi", "sandi", "passcode", "pwd"]),
    ("username", ["username", "nama pengguna", "user name", "pengguna", "userid",
                  "user_id", "login"]),
    ("name", ["full name", "nama lengkap", "display name", "nama", "name",
              "first name", "nama depan"]),
]


def kunci_untuk(kolom: dict) -> str | None:
    tipe = kolom.get("type", "")
    if tipe == "email":
        return "email"
    if tipe == "password":
        return "password"
    if tipe in ("hidden", "checkbox", "radio", "file", "date"):
        return None  # hidden dibiarkan dari nilai bawaan form; sisanya tak ditebak
    teks = kolom.get("teks", "")
    nama = kolom.get("name", "").lower()
    for kunci, kata_list in _PETA:
        for kata in kata_list:
            if kata in teks or kata == nama:
                # 'name' paling akhir & paling umum — hindari menelan 'username'
                if kunci == "name" and ("user" in teks or "pengguna" in teks):
                    continue
                return kunci
    return None


def petakan(kolom_list: list[dict]) -> dict[str, dict]:
    """{kunci_data: kolom} untuk kolom yang dikenali."""
    hasil = {}
    for k in kolom_list:
        kunci = kunci_untuk(k)
        if kunci and kunci not in hasil and k.get("name"):
            hasil[kunci] = k
    return hasil
