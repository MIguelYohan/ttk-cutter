@echo off
title TKK Subtitles (Modo Dev - React + FastAPI)
echo ========================================================
echo   Iniciando em Modo Desenvolvimento (Hot Reload)
echo ========================================================
echo.

REM Inicia o backend FastAPI
start "Backend FastAPI" cmd /k ".\venv\Scripts\python.exe main.py"

REM Inicia o frontend Vite
cd frontend
start "Frontend Vite" cmd /k "npm run dev"

REM Abre o navegador na porta do Vite
timeout /t 3 /nobreak >nul
start http://localhost:5173
