"""
AMOKK Tray Launcher
Icône dans la barre système pour démarrer/arrêter AMOKK d'un clic.
"""
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# Log fichier (debug si l'icône n'apparaît pas)
LOG_FILE = Path(__file__).parent / "amokk_tray.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("amokk_tray")
log.info("=== Démarrage AMOKK Tray ===")

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    log.info("imports pystray + PIL OK")
except Exception as _ie:
    log.error("CRASH import: %s", _ie, exc_info=True)
    raise

# ── Chemins ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL  = "http://localhost:8000"

# ── État global ─────────────────────────────────────────────────────────────────
_backend_proc  = None
_frontend_proc = None
_lock = threading.Lock()


# ── Icône générée dynamiquement ────────────────────────────────────────────────
def _make_icon(status: str = "off") -> Image.Image:
    """Crée une icône 64×64 avec la lettre A, couleur selon statut."""
    size = 64
    bg_color   = (26, 26, 46)          # fond sombre
    ring_color = (212, 160, 23) if status == "on" else (100, 100, 120)  # or / gris
    text_color = (255, 255, 255)

    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Cercle de fond
    draw.ellipse([2, 2, size - 3, size - 3], fill=bg_color, outline=ring_color, width=3)

    # Lettre "A"
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "A", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - 2), "A", font=font, fill=text_color)

    return img


# ── Backend ────────────────────────────────────────────────────────────────────
def _start_backend():
    global _backend_proc
    if _backend_proc and _backend_proc.poll() is None:
        return  # déjà lancé
    env = os.environ.copy()
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        from dotenv import dotenv_values
        env.update(dotenv_values(env_file))
    _backend_proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(BACKEND_DIR),
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _start_frontend():
    global _frontend_proc
    if _frontend_proc and _frontend_proc.poll() is None:
        return
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    _frontend_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _stop_all():
    global _backend_proc, _frontend_proc
    for proc in (_frontend_proc, _backend_proc):
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    _backend_proc = None
    _frontend_proc = None


def _is_running() -> bool:
    return (
        _backend_proc is not None and _backend_proc.poll() is None
    )


# ── Actions menu ───────────────────────────────────────────────────────────────
def action_start(icon, item):
    with _lock:
        log.info("action_start appelé")
        if _is_running():
            log.info("Déjà en cours, skip.")
            return
        try:
            icon.notify("Démarrage d'AMOKK...", "AMOKK")
        except Exception as e:
            log.warning("notify error: %s", e)
        log.info("Démarrage backend...")
        _start_backend()
        log.info("Démarrage frontend...")
        _start_frontend()
        # Attendre que le backend soit prêt (max 10s)
        for _ in range(20):
            time.sleep(0.5)
            try:
                import urllib.request
                urllib.request.urlopen(f"{BACKEND_URL}/status", timeout=1)
                break
            except Exception:
                continue
        icon.icon = _make_icon("on")
        icon.title = "AMOKK — En cours"
        icon.notify("AMOKK est prêt !", "AMOKK")
        webbrowser.open(FRONTEND_URL)


def action_open(icon, item):
    webbrowser.open(FRONTEND_URL)


def action_stop(icon, item):
    with _lock:
        _stop_all()
        icon.icon = _make_icon("off")
        icon.title = "AMOKK — Arrêté"
        icon.notify("AMOKK arrêté.", "AMOKK")


def action_quit(icon, item):
    _stop_all()
    icon.stop()


# ── Menu ────────────────────────────────────────────────────────────────────────
def _build_menu():
    return pystray.Menu(
        pystray.MenuItem("▶  Démarrer",  action_start),
        pystray.MenuItem("🌐  Ouvrir",   action_open),
        pystray.MenuItem("⏹  Arrêter",   action_stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✕  Quitter",   action_quit),
    )


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    try:
        log.info("Création de l'icône...")
        icon = pystray.Icon(
            name="AMOKK",
            icon=_make_icon("off"),
            title="AMOKK — Arrêté",
            menu=_build_menu(),
        )
        log.info("Icône créée, démarrage automatique...")
        # Démarrage automatique au lancement (après que l'icône est prête)
        def auto_start():
            time.sleep(1)  # laisser le temps à l'icône d'apparaître
            action_start(icon, None)
        threading.Thread(target=auto_start, daemon=True).start()
        log.info("Lancement de icon.run()...")
        icon.run()
        log.info("icon.run() terminé.")
    except Exception:
        log.error("ERREUR FATALE:\n" + traceback.format_exc())


if __name__ == "__main__":
    main()
