"""
Objectives Tracker - Suivi des timers d'objectifs (Dragon, Baron, Herald)
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("amokk.objectives")

TIMINGS_PATH = Path(__file__).parent.parent / "assets" / "objectives_spawn_timings.json"


class ObjectivesTracker:
    """
    Suit les timers de spawn des objectifs à partir des évènements de jeu.
    """

    def __init__(self):
        self._timings: dict = {}
        self._mode: str = "default"
        self._load_timings()

        # Timestamps in-game du prochain spawn
        self.dragon_next_spawn: Optional[float] = None
        self.baron_next_spawn: Optional[float] = None
        self.herald_next_spawn: Optional[float] = None
        self.elder_active: bool = False

        self._dragon_kills: int = 0
        self._baron_kills: int = 0
        self._herald_kills: int = 0

    def _load_timings(self):
        with open(TIMINGS_PATH, "r", encoding="utf-8") as f:
            self._timings = json.load(f)
        logger.info("Objectives timings loaded.")

    def _get(self, key: str) -> float:
        mode = self._timings.get(self._mode, self._timings["default"])
        return mode.get(key, self._timings["default"].get(key, -1))

    def set_game_mode(self, mode: str):
        mode_upper = mode.upper()
        self._mode = mode_upper if mode_upper in self._timings else "default"

    def on_game_start(self):
        """Réinitialise les timers en début de partie"""
        t = self._timings.get(self._mode, self._timings["default"])
        self.dragon_next_spawn = t.get("dragon_first_spawn", 300)
        self.herald_next_spawn = t.get("herald_first_spawn", 900)
        self.baron_next_spawn = t.get("baron_first_spawn", 1200)
        self._dragon_kills = 0
        self._baron_kills = 0
        self._herald_kills = 0
        self.elder_active = False

    def on_dragon_killed(self, game_time: float, dragon_type: str = ""):
        self._dragon_kills += 1
        is_elder = "elder" in dragon_type.lower()
        if is_elder:
            self.elder_active = True
            self.dragon_next_spawn = game_time + self._get("elder_respawn")
        else:
            respawn = self._get("dragon_respawn")
            self.dragon_next_spawn = game_time + respawn
        logger.debug(f"Dragon killed ({dragon_type}), next spawn at {self.dragon_next_spawn:.0f}s")

    def on_baron_killed(self, game_time: float):
        self._baron_kills += 1
        self.baron_next_spawn = game_time + self._get("baron_respawn")
        logger.debug(f"Baron killed, next spawn at {self.baron_next_spawn:.0f}s")

    def on_herald_killed(self, game_time: float):
        self._herald_kills += 1
        # Herald disparaît après grubs_disappearance, ne respawn pas après 1 kill
        self.herald_next_spawn = None
        logger.debug("Herald killed (no respawn)")

    def time_until_dragon(self, game_time: float) -> Optional[float]:
        if self.dragon_next_spawn is None:
            return None
        return max(0, self.dragon_next_spawn - game_time)

    def time_until_baron(self, game_time: float) -> Optional[float]:
        if self.baron_next_spawn is None:
            return None
        remaining = self.baron_next_spawn - game_time
        if remaining < 0:
            return None
        return remaining

    def time_until_herald(self, game_time: float) -> Optional[float]:
        if self.herald_next_spawn is None:
            return None
        # Herald disparaît à grubs_disappearance
        disappearance = self._get("grubs_disappearance")
        if disappearance > 0 and game_time > disappearance:
            return None
        return max(0, self.herald_next_spawn - game_time)

    def is_dragon_spawning_soon(self, game_time: float, window: float = 60) -> bool:
        t = self.time_until_dragon(game_time)
        return t is not None and t <= window

    def is_baron_spawning_soon(self, game_time: float, window: float = 60) -> bool:
        t = self.time_until_baron(game_time)
        return t is not None and t <= window

    def get_summary(self, game_time: float) -> dict:
        return {
            "dragon": {
                "kills": self._dragon_kills,
                "time_until_spawn": self.time_until_dragon(game_time),
                "elder_active": self.elder_active,
            },
            "baron": {
                "kills": self._baron_kills,
                "time_until_spawn": self.time_until_baron(game_time),
            },
            "herald": {
                "kills": self._herald_kills,
                "time_until_spawn": self.time_until_herald(game_time),
            },
        }


# Singleton
objectives_tracker = ObjectivesTracker()
