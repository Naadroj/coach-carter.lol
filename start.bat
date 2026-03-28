@echo off
title AMOKK Local - Lancement

echo ========================================
echo  AMOKK - AI Voice Coach for LoL (Local)
echo ========================================
echo.

:: Verifier .env
if not exist "backend\.env" (
    echo [WARN] Fichier backend\.env manquant
    echo        Copie backend\.env.example vers backend\.env et remplis OPENAI_API_KEY
    echo.
)

:: Lancer le backend Python dans une fenetre separee
echo [1/2] Demarrage du backend Python...
start "AMOKK Backend" cmd /k "cd backend && python main.py"

:: Attendre que le backend soit pret
timeout /t 3 /nobreak > nul

:: Lancer le frontend Vite (mode dev)
echo [2/2] Demarrage du frontend...
start "AMOKK Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo AMOKK demarre !
echo   Backend : http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo.
echo (Ferme les fenetres pour tout arreter)
pause
