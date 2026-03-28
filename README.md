# AMOKK Local — Reconstruction from scratch

Réplique locale complète d'AMOKK v2.1.2, coach IA vocal pour League of Legends.

## Stack

| Couche | Technologie |
|---|---|
| Desktop | Electron 31 |
| Frontend | React 18 + Vite 5 + TypeScript |
| Backend | Python 3.11 + FastAPI |
| Computer Vision | PyTorch + OpenCV + dxcam |
| TTS & Coach IA | OpenAI TTS (tts-1) + GPT-4o-mini |
| Auth | JWT via api.amokk.fr (ton compte existant) |

## Structure

```
amokk-local/
├── backend/              # Python FastAPI sur :8000
│   ├── main.py           # Point d'entrée
│   ├── api/routes.py     # Routes HTTP
│   ├── core/
│   │   ├── cache.py           # Persistance locale
│   │   ├── game_state.py      # Live Game API (port 2999)
│   │   ├── computer_vision.py # Détection minimap (PyTorch + OpenCV)
│   │   ├── objectives.py      # Timers Dragon/Baron/Herald
│   │   ├── triggerer.py       # Système d'alertes coaching
│   │   └── assistant.py       # TTS vocal (OpenAI)
│   └── assets/
│       ├── triggers.json                  # Config alertes par rôle
│       ├── objectives_spawn_timings.json  # Timers objectifs
│       ├── minimap_zones_descriptions.json
│       ├── minimap_zones/                 # 72 polygones UV
│       └── minimap_detector.pt            # Modèle PyTorch (copié d'AMOKK)
├── frontend/             # React + Vite
│   └── src/
│       ├── pages/Login.tsx
│       ├── pages/Dashboard.tsx
│       └── api.ts
├── electron/             # App desktop
│   └── src/
│       ├── main.ts       # Fenêtre + lancement backend
│       └── preload.ts    # IPC bridge
├── start.bat             # Lancement mode dev (sans Electron)
└── start-electron.bat    # Lancement Electron complet
```

## Installation

### 1. Prérequis
- Python 3.11
- Node.js 20+

### 2. Backend Python

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Éditer .env et renseigner OPENAI_API_KEY
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. Electron (optionnel)

```bash
cd electron
npm install
```

## Lancement

### Mode dev (recommandé pour commencer)

Double-cliquer sur `start.bat` — lance le backend Python + le frontend Vite.
Ouvrir http://localhost:5173 dans un navigateur.

### Mode Electron complet

Double-cliquer sur `start-electron.bat`.

## Configuration

Le fichier `backend/.env` :

```env
OPENAI_API_KEY=sk-...    # Requis pour TTS + conseils IA
BACKEND_PORT=8000
BACKEND_HOST=127.0.0.1
```

Sans `OPENAI_API_KEY`, l'appli fonctionne mais utilise des conseils statiques (fallback).

## API Backend

| Méthode | Route | Description |
|---|---|---|
| GET | /status | Santé du backend |
| POST | /login | Auth via api.amokk.fr |
| GET | /get_local_data | Données locales (cache) |
| POST | /volume | Régler le volume TTS |
| POST | /coaching/start | Activer le coaching |
| POST | /coaching/stop | Désactiver |
| GET | /game/state | État complet de la partie |
| POST | /tts/test | Test audio |

## Assets réutilisés d'AMOKK

- `minimap_detector.pt` — modèle ML de détection de position (copiés de `E:\Amokk\assets\models\`)
- `triggers.json` — configuration complète des alertes par rôle
- `minimap_zones/*.json` — 72 polygones UV définissant les zones de la carte
- `objectives_spawn_timings.json` — timers des objectifs (Classic + Swiftplay)
