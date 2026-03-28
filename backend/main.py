"""
AMOKK Backend — Point d'entrée principal
Lance le serveur FastAPI + toutes les boucles de jeu
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ajouter le dossier backend au path pour les imports relatifs
sys.path.insert(0, str(Path(__file__).parent))

# Charger le .env AVANT tous les autres imports (override=True force le rechargement)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=False)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.cache import cache
from core.game_state import game_tracker
from core.objectives import objectives_tracker
from core.computer_vision import cv_module
from core.assistant import assistant
from core.triggerer import triggerer
from core.push_to_talk import push_to_talk

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_DIR = Path.home() / ".amokk-local" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "backend.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("amokk.main")

# ── Application FastAPI ───────────────────────────────────────────────────────

app = FastAPI(title="AMOKK Backend", version="2.1.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Electron sur localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    logger.info("========== STARTING AMOKK's UI API ==========")

    # Initialiser le volume depuis le cache
    assistant.set_volume(cache.get_volume())

    # Injecter les dépendances dans le triggerer
    triggerer.inject_dependencies(assistant, game_tracker, objectives_tracker, cv_module)

    # Démarrer les modules asynchrones
    await assistant.start()
    await game_tracker.start()
    await triggerer.start()

    # Démarrer le CV dans un thread dédié
    cv_module.start()

    # Push-to-talk
    push_to_talk.inject(assistant, assistant._openai_client)
    push_to_talk.start(asyncio.get_event_loop())

    # Watcher: surveille le lancement de LoL
    asyncio.create_task(_watch_for_game())

    logger.info("========== AMOKK BACKEND READY ==========")
    logger.info(f"Volume: {cache.get_volume()}, Email: {cache.get_email()}")


@app.on_event("shutdown")
async def on_shutdown():
    push_to_talk.stop()
    await triggerer.stop()
    await game_tracker.stop()
    await assistant.stop()
    cv_module.stop()
    logger.info("AMOKK Backend stopped.")


async def _watch_for_game():
    """Surveille le lancement de LoL et initialise les objectifs au démarrage de partie"""
    was_active = False
    while True:
        state = game_tracker.get_state()
        if state.active and not was_active:
            logger.info("Game detected — initializing objectives tracker")
            objectives_tracker.on_game_start()
            was_active = True
        elif not state.active and was_active:
            logger.info("Game ended")
            was_active = False
        await asyncio.sleep(2.0)


# ── Entrée ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", 8000))
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    logger.info(f"Starting AMOKK backend on {host}:{port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )
