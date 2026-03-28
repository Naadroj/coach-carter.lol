@echo off
cd /d "%~dp0"

:: Vérifier si déjà en cours
curl -s http://localhost:8000/status > nul 2>&1
if not errorlevel 1 (
    echo AMOKK est deja en cours. Ouverture du navigateur...
    start "" "http://localhost:5173"
    exit
)

:: Démarrer le backend (fenêtre minimisée)
start /min "AMOKK Backend" cmd /c "cd /d "%~dp0backend" && python main.py"

:: Attendre que le backend soit prêt (max 15s)
echo Demarrage du backend...
set /a attempts=0
:wait_backend
timeout /t 1 /nobreak > nul
set /a attempts+=1
curl -s http://localhost:8000/status > nul 2>&1
if errorlevel 1 (
    if %attempts% lss 15 goto wait_backend
    echo [WARN] Backend lent a demarrer, on continue...
)

:: Démarrer le frontend (fenêtre minimisée)
start /min "AMOKK Frontend" cmd /c "cd /d "%~dp0frontend" && npm run dev"

:: Attendre que le frontend soit prêt
echo Demarrage du frontend...
set /a attempts=0
:wait_frontend
timeout /t 1 /nobreak > nul
set /a attempts+=1
curl -s http://localhost:5173 > nul 2>&1
if errorlevel 1 (
    if %attempts% lss 20 goto wait_frontend
)

:: Ouvrir le navigateur sur localhost (pas 127.0.0.1)
start "" "http://localhost:5173"
exit
