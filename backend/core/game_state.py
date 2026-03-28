"""
Game State - Suivi de l'état de la partie via la Live Game API (port 2999)
et la LCU API (port dynamique)
"""
import asyncio
import aiohttp
import ssl
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("amokk.game_state")

# Live Game Data API - pas d'auth requise, port fixe
LIVE_API_BASE = "https://127.0.0.1:2999"


@dataclass
class PlayerStats:
    name: str = ""
    champion: str = ""
    team: str = "ORDER"          # ORDER (blue/SW) ou CHAOS (red/NE)
    role: str = "MIDDLE"
    level: int = 1
    cs: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    ward_score: float = 0.0
    current_gold: float = 0.0
    is_dead: bool = False
    respawn_timer: float = 0.0
    items: list = field(default_factory=list)
    # Scores calculés
    kill_participation: float = 0.0


@dataclass
class ObjectiveState:
    dragon_kills: int = 0
    baron_kills: int = 0
    herald_kills: int = 0
    dragon_next_spawn: float = 0.0   # timestamp in-game
    baron_next_spawn: float = 0.0
    herald_next_spawn: float = 0.0
    elder_dragon_spawned: bool = False
    game_mode: str = "CLASSIC"
    enemy_jungler_champion: str = ""
    enemy_jungler_kills: int = 0
    enemy_jungler_cs: int = 0


@dataclass
class FullGameState:
    active: bool = False
    game_time: float = 0.0
    player: PlayerStats = field(default_factory=PlayerStats)
    objectives: ObjectiveState = field(default_factory=ObjectiveState)
    all_players: list = field(default_factory=list)
    events: list = field(default_factory=list)
    last_event_id: int = -1
    # Flags calculés
    is_in_teamfight: bool = False
    is_late_game: bool = False
    is_allied_base_collapsing: bool = False
    any_build_completed: bool = False
    last_death_time: float = -9999.0
    last_objective_advice_time: float = -9999.0


class LiveGameClient:
    """Client pour la Live Game Data API de LoL (port 2999)"""

    def __init__(self):
        self._ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=self._ssl_ctx)
            )
        return self._session

    async def get(self, path: str) -> Optional[dict | list]:
        session = await self._get_session()
        try:
            async with session.get(f"{LIVE_API_BASE}{path}", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return None

    async def is_game_active(self) -> bool:
        result = await self.get("/liveclientdata/gamestats")
        return result is not None

    async def get_game_stats(self) -> Optional[dict]:
        return await self.get("/liveclientdata/gamestats")

    async def get_active_player(self) -> Optional[dict]:
        return await self.get("/liveclientdata/activeplayer")

    async def get_all_players(self) -> Optional[list]:
        return await self.get("/liveclientdata/playerlist")

    async def get_events(self) -> Optional[dict]:
        return await self.get("/liveclientdata/eventdata")

    async def close(self):
        if self._session:
            await self._session.close()


class GameStateTracker:
    """
    Construit et maintient un FullGameState à jour en interrogeant la Live API.
    Tourne dans un thread asyncio dédié.
    """

    def __init__(self):
        self.state = FullGameState()
        self._client = LiveGameClient()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("GameStateTracker started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        await self._client.close()

    async def _loop(self):
        while self._running:
            try:
                await self._update()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"GameState update error: {e}")
            await asyncio.sleep(1.0)

    async def _update(self):
        game_stats = await self._client.get_game_stats()
        if not game_stats:
            self.state.active = False
            return

        self.state.active = True
        self.state.game_time = game_stats.get("gameTime", 0.0)
        self.state.is_late_game = self.state.game_time > 1800  # 30 min

        # Joueur actif
        active = await self._client.get_active_player()
        if active:
            self._parse_active_player(active)

        # Tous les joueurs
        all_players = await self._client.get_all_players()
        if all_players:
            self.state.all_players = all_players
            self._parse_all_players(all_players)

        # Évènements
        events_data = await self._client.get_events()
        if events_data:
            self._process_events(events_data.get("Events", []))

        # Flags
        self._update_flags()

    def _parse_active_player(self, data: dict):
        """activeplayer contient summonerName, level et currentGold."""
        p = self.state.player
        name = data.get("summonerName") or data.get("riotIdGameName", "")
        if name:
            p.name = name
        p.level = data.get("level", p.level)
        p.current_gold = float(data.get("currentGold", p.current_gold))

    def _parse_all_players(self, players: list):
        """
        isActivePlayer est souvent False dans certaines versions du client.
        On matche via summonerName récupéré depuis activeplayer.
        """
        active_name = self.state.player.name

        # Trouver le joueur actif : d'abord via isActivePlayer, sinon via summonerName
        active = None
        for p in players:
            if p.get("isActivePlayer"):
                active = p
                break
        if active is None and active_name:
            for p in players:
                if p.get("summonerName") == active_name:
                    active = p
                    break

        if not active:
            logger.warning("Joueur actif introuvable dans playerlist (name=%r)", active_name)
            return

        logger.debug("ActivePlayer trouvé — champion: %s, position: %r, scores: %r",
                     active.get("championName"), active.get("position"), active.get("scores"))

        self.state.player.champion = active.get("championName", "")
        self.state.player.team = active.get("team", "ORDER")
        self.state.player.is_dead = active.get("isDead", False)
        self.state.player.respawn_timer = active.get("respawnTimer", 0.0)
        self.state.player.items = active.get("items", [])

        # ── Scores (CS, kills, etc.) ──
        scores = active.get("scores", {})
        self.state.player.cs = scores.get("creepScore", self.state.player.cs)
        self.state.player.kills = scores.get("kills", self.state.player.kills)
        self.state.player.deaths = scores.get("deaths", self.state.player.deaths)
        self.state.player.assists = scores.get("assists", self.state.player.assists)
        self.state.player.ward_score = scores.get("wardScore", self.state.player.ward_score)

        # ── Rôle ──
        position = active.get("position", "")
        if position and position.strip():
            self.state.player.role = _normalize_role(position)

        # Jungler adverse
        enemy_team = "CHAOS" if self.state.player.team == "ORDER" else "ORDER"
        for p_data in players:
            if p_data.get("team") == enemy_team and p_data.get("position") == "JUNGLE":
                scores = p_data.get("scores", {})
                self.state.objectives.enemy_jungler_champion = p_data.get("championName", "")
                self.state.objectives.enemy_jungler_kills = scores.get("kills", 0)
                self.state.objectives.enemy_jungler_cs = scores.get("creepScore", 0)
                break

        # Teamfight heuristique : >= 3 champions morts récemment ou >= 2 kills en < 10s
        team = self.state.player.team
        team_total_kills = sum(
            p.get("scores", {}).get("kills", 0)
            for p in players if p.get("team") == team
        )
        self.state.objectives.dragon_kills = sum(
            1 for p in players
            if p.get("team") == team
            for item in p.get("items", [])
            if "Dragon" in item.get("displayName", "")
        )

    def _process_events(self, events: list):
        new_events = [e for e in events if e.get("EventID", 0) > self.state.last_event_id]
        if not new_events:
            return
        self.state.last_event_id = max(e.get("EventID", 0) for e in events)
        self.state.events.extend(new_events)
        # Garder les 100 derniers
        self.state.events = self.state.events[-100:]

        obj = self.state.objectives
        t = self.state.game_time

        for event in new_events:
            etype = event.get("EventName", "")
            if etype == "DragonKill":
                obj.dragon_kills += 1
                obj.dragon_next_spawn = t + (360 if "Elder" in event.get("DragonType", "") else 300)
            elif etype == "BaronKill":
                obj.baron_kills += 1
                obj.baron_next_spawn = t + 360
            elif etype == "HeraldKill":
                obj.herald_kills += 1
            elif etype == "ChampionKill":
                victim = event.get("VictimName", "")
                if victim == self.state.player.name:
                    self.state.last_death_time = t

    def _update_flags(self):
        p = self.state.player
        t = self.state.game_time
        # Teamfight: simple heuristique (peut être affiné par CV)
        recent_kills = [
            e for e in self.state.events[-20:]
            if e.get("EventName") == "ChampionKill"
            and t - e.get("EventTime", 0) < 15
        ]
        self.state.is_in_teamfight = len(recent_kills) >= 2
        # Base collapsing: >= 2 inhibiteurs détruits
        inhib_kills = [e for e in self.state.events if e.get("EventName") == "InhibKilled"]
        self.state.is_allied_base_collapsing = len(inhib_kills) >= 2
        # Build completed: item légendaire dans l'inventaire
        self.state.any_build_completed = any(
            item.get("price", 0) >= 3000 for item in p.items
        )

    def get_state(self) -> FullGameState:
        return self.state


def _normalize_role(position: str) -> str:
    mapping = {
        "TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MIDDLE", "MID": "MIDDLE",
        "BOTTOM": "BOTTOM", "BOT": "BOTTOM", "ADC": "BOTTOM",
        "UTILITY": "UTILITY", "SUPPORT": "UTILITY", "SUP": "UTILITY",
    }
    return mapping.get(position.upper(), "MIDDLE")


# Singleton
game_tracker = GameStateTracker()
