"""
LCU (League Client Update) API
Connexion au client LoL via le port local sécurisé
"""
import asyncio
import base64
import json
import ssl
import subprocess
import re
import aiohttp
from dataclasses import dataclass, field
from typing import Any, Optional
import logging

logger = logging.getLogger("amokk.lcu")

# Endpoints LCU utilisés
LCU_ENDPOINTS = {
    "summoner":          "/lol-summoner/v1/current-summoner",
    "game_flow":         "/lol-gameflow/v1/gameflow-phase",
    "active_game":       "/lol-gameflow/v1/session",
    "champion_mastery":  "/lol-champion-mastery/v1/local-player/champion-mastery",
    "items":             "/lol-inventory/v1/player-items",
    "ranked":            "/lol-ranked/v1/current-ranked-stats",
}


@dataclass
class LCUCredentials:
    port: int
    password: str
    pid: int


@dataclass
class GameState:
    phase: str = "None"          # None, Lobby, ChampSelect, InProgress, EndOfGame, ...
    game_time: float = 0.0
    summoner_name: str = ""
    champion: str = ""
    team_side: str = "SW"        # SW (blue) ou NE (red)
    role: str = "MIDDLE"
    items: list = field(default_factory=list)
    cs: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    ward_score: float = 0.0
    is_dead: bool = False
    team_kills: int = 0
    enemy_kills: int = 0
    # Objectifs
    dragon_count: int = 0
    baron_count: int = 0
    herald_count: int = 0


def _find_lcu_credentials() -> Optional[LCUCredentials]:
    """Trouve le port et mot de passe du client LoL via le processus Windows."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='LeagueClientUx.exe'", "get", "commandline"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        port_match = re.search(r"--app-port=(\d+)", output)
        token_match = re.search(r"--remoting-auth-token=([a-zA-Z0-9_-]+)", output)
        pid_match = re.search(r"--ux-helper-pid=(\d+)", output)
        if port_match and token_match:
            return LCUCredentials(
                port=int(port_match.group(1)),
                password=token_match.group(1),
                pid=int(pid_match.group(1)) if pid_match else 0,
            )
    except Exception as e:
        logger.debug(f"LCU process not found: {e}")
    return None


class LCUClient:
    def __init__(self):
        self._creds: Optional[LCUCredentials] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self.connected = False

    async def connect(self) -> bool:
        self._creds = _find_lcu_credentials()
        if not self._creds:
            self.connected = False
            return False
        auth = base64.b64encode(f"riot:{self._creds.password}".encode()).decode()
        self._session = aiohttp.ClientSession(
            base_url=f"https://127.0.0.1:{self._creds.port}",
            headers={"Authorization": f"Basic {auth}"},
            connector=aiohttp.TCPConnector(ssl=self._ssl_ctx),
        )
        try:
            async with self._session.get("/lol-summoner/v1/current-summoner") as resp:
                self.connected = resp.status == 200
        except Exception:
            self.connected = False
        return self.connected

    async def get(self, endpoint: str) -> Optional[dict]:
        if not self._session:
            return None
        try:
            async with self._session.get(endpoint) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"LCU GET {endpoint} failed: {e}")
        return None

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def get_game_phase(self) -> str:
        data = await self.get("/lol-gameflow/v1/gameflow-phase")
        if isinstance(data, str):
            return data
        return "None"

    async def get_current_summoner(self) -> Optional[dict]:
        return await self.get("/lol-summoner/v1/current-summoner")

    async def get_ranked_stats(self) -> Optional[dict]:
        return await self.get("/lol-ranked/v1/current-ranked-stats")


# Client singleton
lcu_client = LCUClient()
