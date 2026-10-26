@echo off
title 3DGarage - Backend Sunucusu
color 0A
echo ========================================================
echo   3DGarage Backend (FastAPI) Baslatiliyor...
echo ========================================================
cd /d "D:\3DGarage\Backend"
set PYTHONPATH=D:\3DGarage;D:\3DGarage\Backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
