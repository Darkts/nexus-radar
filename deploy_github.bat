@echo off
title Nexus Radar - Deploiement GitHub
color 0a
echo ===================================================
echo   NEXUS RADAR - DEPLOIEMENT VERS VOTRE GITHUB
echo ===================================================
echo.
set /p REPO_URL="Entrez l'URL HTTPS de votre depot GitHub : "

if "%REPO_URL%"=="" (
    echo Erreur : Aucune URL saisie.
    pause
    exit /b
)

echo.
echo Configuration de la liaison vers %REPO_URL%...
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main

echo.
echo Envoi des fichiers vers GitHub...
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================================
    echo   SUCCES ! Votre projet est en ligne sur GitHub.
    echo ===================================================
    echo.
    echo DERNIERE ETAPE (sur le site GitHub) :
    echo 1. Allez dans Settings ^> Actions ^> General
    echo    Sous "Workflow permissions", cochez "Read and write permissions" ^> Save.
    echo 2. Allez dans Settings ^> Pages
    echo    Sous "Branch", choisissez "main" et "/ (root)" ^> Save.
    echo.
) else (
    echo.
    echo Une erreur est survenue lors du git push. Verifiez vos identifiants GitHub.
)

pause
