@echo off
title Coach Carter LoL - Lancement

echo ========================================
echo  Coach Carter LoL - Demarrage
echo ========================================
echo.

:: Lancer le backend Python dans une fenetre separee
echo [1/2] Demarrage du backend Python...
start "Coach Carter Backend" cmd /k "cd /d "%~dp0backend" && python main.py"

:: Attendre que le backend soit pret
echo [2/2] Attente du backend (5s)...
timeout /t 5 /nobreak > nul

:: Lancer l'app Electron
echo [3/3] Lancement de l'application...
start "" "%~dp0electron\dist\win-unpacked\Coach Carter LoL.exe"

echo.
echo Coach Carter LoL demarre !
echo   Backend : http://127.0.0.1:8000
echo.
echo Laisse cette fenetre ouverte pour garder le backend actif.
echo Ferme-la pour arreter le backend.
echo.
pause
