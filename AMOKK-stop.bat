@echo off
echo Arret d'AMOKK...

:: Tuer le backend Python sur port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /PID %%a /F > nul 2>&1
)

:: Tuer les fenêtres cmd nommées AMOKK
taskkill /FI "WINDOWTITLE eq AMOKK Backend" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq AMOKK Frontend" /F > nul 2>&1

echo AMOKK arrete.
timeout /t 2 > nul
exit
