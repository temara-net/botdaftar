"""Klien Telegram Bot API minimal (requests). Alamat API bisa dioverride
lewat TG_API_BASE untuk pengujian lokal dengan server tiruan."""
import os
import requests


class Telegram:
    def __init__(self, token: str, api_base: str | None = None):
        self.base = api_base or f"https://api.telegram.org/bot{token}/"
        self.session = requests.Session()

    def call(self, method: str, **params):
        r = self.session.post(self.base + method, json=params, timeout=40)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data["result"]

    def get_updates(self, offset: int = 0):
        try:
            return self.call("getUpdates", offset=offset, timeout=10,
                             allowed_updates=["message"])
        except Exception as e:  # jaringan Telegram sesekali lambat; jangan jatuhkan run
            print(f"[telegram] getUpdates gagal: {e}")
            return []

    def send_message(self, chat_id, text: str):
        # Telegram membatasi 4096 karakter per pesan
        for i in range(0, len(text), 4000):
            self.call("sendMessage", chat_id=chat_id, text=text[i:i + 4000])

    def send_photo(self, chat_id, path: str, caption: str = ""):
        url = self.base + "sendPhoto"
        with open(path, "rb") as f:
            r = self.session.post(url, data={"chat_id": chat_id, "caption": caption[:1000]},
                                  files={"photo": f}, timeout=60)
        r.raise_for_status()
        return r.json()
