"""State percakapan antar-run GitHub Actions (berkas JSON).

ATURAN KERAS sesuai konsep: password TIDAK PERNAH masuk state.
save() membuang kunci 'password' di semua level sebelum menulis.
"""
import json
import os


def _tanpa_password(obj):
    if isinstance(obj, dict):
        return {k: _tanpa_password(v) for k, v in obj.items() if k != "password"}
    if isinstance(obj, list):
        return [_tanpa_password(v) for v in obj]
    return obj


class State:
    def __init__(self, path: str):
        self.path = path
        self.data = {"offset": 0, "conv": {}}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        bersih = _tanpa_password(self.data)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(bersih, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self.data = bersih

    def conv(self, chat_id) -> dict:
        return self.data.setdefault("conv", {}).setdefault(str(chat_id), {"stage": "idle"})

    def reset_conv(self, chat_id):
        self.data.setdefault("conv", {})[str(chat_id)] = {"stage": "idle"}
