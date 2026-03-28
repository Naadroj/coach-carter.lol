"""
Routes FastAPI — API locale sur http://127.0.0.1:8000
Réplique de l'API locale du backend AMOKK
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.cache import cache
from core.game_state import game_tracker
from core.objectives import objectives_tracker
from core.computer_vision import cv_module
from core.assistant import assistant

logger = logging.getLogger("amokk.api")

router = APIRouter()

# Login local — plus de dépendance à api.amokk.fr
LOCAL_LOGIN = "admin"
LOCAL_PASSWORD = "admin"


# ── Schémas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class VolumeRequest(BaseModel):
    volume: int   # 0-100


class RoleRequest(BaseModel):
    role: str     # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def status():
    return {"status": "ok", "version": "2.1.2"}


@router.post("/login")
async def login(req: LoginRequest):
    """Authentification locale — plus de dépendance à api.amokk.fr"""
    if req.email != LOCAL_LOGIN or req.password != LOCAL_PASSWORD:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    token = "local-token-amokk"
    cache.set_token(token)
    cache.set_email(req.email)
    cache.set_remaining_games(9999)   # illimité en local
    cache.mark_launched()
    logger.info(f"Login local OK: {req.email}")
    return {"token": token, "remaining_games": 9999}


@router.get("/get_local_data")
async def get_local_data():
    """Retourne les données locales (cache) — appelé par l'Electron au démarrage"""
    return {
        "remaining_games": cache.get_remaining_games(),
        "first_launch": cache.is_first_launch(),
        "game_timer": cache.get_game_timer(),
        "email": cache.get_email(),
        "volume": cache.get_volume(),
    }


@router.post("/volume")
async def set_volume(req: VolumeRequest):
    cache.set_volume(req.volume)
    assistant.set_volume(req.volume)
    logger.info(f"Volume set to {req.volume}")
    return {"ok": True, "volume": req.volume}


@router.get("/volume")
async def get_volume():
    return {"volume": cache.get_volume()}


@router.post("/coaching/start")
async def start_coaching(req: RoleRequest):
    """Démarre le coaching pour le rôle donné"""
    from core.triggerer import triggerer
    # Forcer le rôle sur le state courant
    game_tracker.state.player.role = req.role.upper()
    logger.info(f"Coaching started for role: {req.role}")
    return {"ok": True, "role": req.role}


@router.post("/coaching/stop")
async def stop_coaching():
    assistant.interrupt()
    logger.info("Coaching stopped")
    return {"ok": True}


@router.get("/game/state")
async def game_state():
    """État complet de la partie en cours"""
    state = game_tracker.get_state()
    if not state.active:
        return {"active": False}

    zone_name, zone_desc = cv_module.get_current_zone()
    obj = objectives_tracker.get_summary(state.game_time)

    return {
        "active": True,
        "game_time": state.game_time,
        "player": {
            "name": state.player.name,
            "champion": state.player.champion,
            "role": state.player.role,
            "team": state.player.team,
            "cs": state.player.cs,
            "kills": state.player.kills,
            "deaths": state.player.deaths,
            "assists": state.player.assists,
            "ward_score": state.player.ward_score,
            "is_dead": state.player.is_dead,
        },
        "position": {
            "zone": zone_name,
            "description": zone_desc,
            "uv": cv_module.get_player_uv(),
        },
        "objectives": obj,
        "flags": {
            "is_in_teamfight": state.is_in_teamfight,
            "is_late_game": state.is_late_game,
        },
    }


@router.get("/game/events")
async def game_events():
    state = game_tracker.get_state()
    return {"events": state.events[-50:], "last_event_id": state.last_event_id}


@router.post("/tts/test")
async def tts_test():
    """Joue un message de test TTS"""
    await assistant.say("AMOKK est prêt. Bonne chance sur la Faille de l'Invocateur !")
    return {"ok": True}


@router.get("/triggers/config")
async def get_triggers_config():
    """Retourne la config de tous les triggers"""
    from core.triggerer import triggerer
    return {"triggers": triggerer.get_config()}


class TriggerUpdateRequest(BaseModel):
    name: str
    enabled: bool | None = None
    cooldown: int | None = None
    spawn_phases: list[int] | None = None


@router.post("/triggers/config")
async def update_trigger_config(req: TriggerUpdateRequest):
    """Met à jour un trigger (enabled / cooldown / spawn_phases)"""
    from core.triggerer import triggerer
    triggerer.update_config(req.name, enabled=req.enabled, cooldown=req.cooldown, spawn_phases=req.spawn_phases)
    return {"ok": True}


@router.get("/triggers/spawn-phases")
async def get_spawn_phases():
    """Retourne les phases d'alerte spawn (en secondes avant le spawn)"""
    from core.triggerer import triggerer
    return {"phases": triggerer.get_spawn_phases()}


@router.get("/ptt/status")
async def ptt_status():
    """Statut du Push-to-Talk"""
    from core.push_to_talk import push_to_talk, PTT_KEY
    return {"enabled": push_to_talk._enabled, "key": PTT_KEY.upper()}


@router.post("/ptt/key")
async def set_ptt_key(req: dict):
    """Change la touche PTT (ex: {"key": "f9"})"""
    from core.push_to_talk import push_to_talk
    import core.push_to_talk as ptt_module
    new_key = req.get("key", "f9").lower()
    ptt_module.PTT_KEY = new_key
    # Redémarrer le listener avec la nouvelle touche
    push_to_talk.stop()
    import asyncio
    push_to_talk.start(asyncio.get_event_loop())
    logger.info(f"PTT key changed to: {new_key.upper()}")
    return {"ok": True, "key": new_key.upper()}


@router.get("/usage")
async def get_usage():
    """Retourne les statistiques de consommation des APIs"""
    return assistant.get_usage()
