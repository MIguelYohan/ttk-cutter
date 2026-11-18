@echo off
title TKK Subtitles - Gerador de Legendas Whisper
echo ========================================================
echo   Iniciando TKK Subtitles (Whisper + React)
echo ========================================================
echo.

REM Inicia o navegador apos 2 segundos
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"

REM Executa o servidor FastAPI com o Python do venv
.\venv\Scripts\python.exe main.py

pause
