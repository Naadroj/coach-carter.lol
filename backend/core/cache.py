"""
Cache - persistance locale des données utilisateur
Réplique de la classe Cache d'AMOKK
"""
import json
import os
from pathlib import Path

CACHE_PATH = Path(os.environ.get("AMOKK_CACHE_PATH", Path.home() / ".amokk-local" / "cache.json"))


class Cache:
    def __init__(self):
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self):
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def get_all(self) -> dict:
        return dict(self._data)

    # Helpers métier
    def get_token(self) -> str | None:
        return self._data.get("token")

    def set_token(self, token: str):
        self.set("token", token)

    def get_email(self) -> str | None:
        return self._data.get("email")

    def set_email(self, email: str):
        self.set("email", email)

    def get_remaining_games(self) -> int:
        return self._data.get("remaining_games", 0)

    def set_remaining_games(self, n: int):
        self.set("remaining_games", n)

    def get_volume(self) -> int:
        return self._data.get("tts_volume", 67)

    def set_volume(self, volume: int):
        self.set("tts_volume", max(0, min(100, volume)))

    def is_first_launch(self) -> bool:
        return self._data.get("first_launch", True)

    def mark_launched(self):
        self.set("first_launch", False)

    def get_game_timer(self) -> float:
        return self._data.get("game_timer", 0.0)

    def set_game_timer(self, t: float):
        self.set("game_timer", t)


# Singleton
cache = Cache()
