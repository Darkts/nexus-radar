@echo off
title Nexus Radar - Hub Personnel
color 0b
echo ===================================================
echo   NEXUS RADAR - AUTONOMOUS HUNTING HUB
echo ===================================================
echo [1/2] Demarrage du serveur local sur le port 8080...
echo [2/2] Ouverture de votre navigateur...
echo.
start http://localhost:8080/index.html
python -m http.server 8080
pause

