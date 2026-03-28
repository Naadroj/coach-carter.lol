@echo off
title AMOKK Local - Electron

echo ========================================
echo  AMOKK - Lancement Electron (complet)
echo ========================================
echo.

:: Verifier .env
if not exist "backend\.env" (
    echo [WARN] backend\.env manquant - copier .env.example et remplir OPENAI_API_KEY
    echo.
)

:: Installer les dependances si besoin
if not exist "frontend\node_modules" (
    echo Installation des dependances frontend...
    cd frontend && npm install && cd ..
)
if not exist "electron\node_modules" (
    echo Installation des dependances electron...
    cd electron && npm install && cd ..
)

:: Build frontend
echo Build du frontend...
cd frontend && npm run build && cd ..

:: Lancer Electron (qui lance le backend automatiquement)
echo Lancement d'Electron...
cd electron && npx electron .
