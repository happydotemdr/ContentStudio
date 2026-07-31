@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "ContentStudio Pipeline" cmd /k uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8420
