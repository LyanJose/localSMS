@echo off
rem Lance la compilation Windows sans devoir modifier la stratégie d'exécution PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
if errorlevel 1 (echo. & echo ECHEC de la compilation. & pause & exit /b 1)
pause
