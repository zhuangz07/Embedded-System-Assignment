@echo off
chcp 65001 >nul

echo ================================================
echo   PC Host - Clock System
echo ================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] venv not found, creating...
    python -m venv .venv
    echo.
    echo [INFO] Installing dependencies...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
)

echo [START] Launching main.py ...
echo.

.venv\Scripts\python.exe main.py

pause
