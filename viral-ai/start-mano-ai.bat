@echo off
title Mano Clip Tool - Free Viral AI
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.10-3.12 is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Starting free local AI service at http://127.0.0.1:8765
python -m uvicorn app:app --host 127.0.0.1 --port 8765
pause
