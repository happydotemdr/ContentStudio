@echo off
setlocal
cd /d "%~dp0"

rem Finding F-78: this script used to `call activate.bat`, sleep 3s, and open the
rem browser unconditionally. A missing venv, a bound port, or a uvicorn crash all
rem still opened a browser, so the operator's foreground signal was a connection
rem error while the real message sat in a background window -- and a second launch
rem opened the browser onto the FIRST instance, possibly against another database.

if not exist ".venv\Scripts\activate.bat" (
  echo [start_pipeline] ERROR: no virtualenv at .venv\Scripts\activate.bat
  echo [start_pipeline] Create it:  python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [start_pipeline] ERROR: activating .venv failed with errorlevel %errorlevel%
  exit /b 1
)

netstat -ano -p tcp | findstr /c:"LISTENING" | findstr /c:":8420 " >nul
if not errorlevel 1 (
  echo [start_pipeline] ERROR: port 8420 is already in use.
  echo [start_pipeline] An instance is already running -- refusing to launch a second
  echo [start_pipeline] one that would die silently while the browser opens onto the first.
  exit /b 1
)

if "%PIPELINE_APP_LAUNCH_DRYRUN%"=="1" (
  echo [start_pipeline] DRYRUN: preflight passed. OPENING BROWSER would follow.
  exit /b 0
)

start "ContentStudio Pipeline" cmd /k uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420

rem Poll instead of sleeping a fixed 3 seconds: a slow start opened the browser
rem before the server answered, a crashed start opened it anyway.
set /a _tries=0
:waitloop
set /a _tries+=1
curl -s -o nul --max-time 1 http://127.0.0.1:8420/ && goto ready
if %_tries% GEQ 30 (
  echo [start_pipeline] ERROR: server did not answer on 127.0.0.1:8420 after 30s.
  echo [start_pipeline] Read the traceback in the "ContentStudio Pipeline" window.
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo [start_pipeline] OPENING BROWSER http://127.0.0.1:8420
start "" http://127.0.0.1:8420
exit /b 0
