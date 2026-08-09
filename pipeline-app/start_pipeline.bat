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
  echo [start_pipeline] ERROR: a process is already listening on 127.0.0.1:8420.
  echo [start_pipeline] netstat cannot tell whether that is this app -- it may be a
  echo [start_pipeline] leftover instance, or it may be something unrelated that has
  echo [start_pipeline] taken the port. Run "netstat -ano" and look for port 8420 to
  echo [start_pipeline] find the PID, then check Task Manager for what it is before
  echo [start_pipeline] assuming it is safe to close.
  exit /b 1
)

rem Preflight-only mode is an EXPLICIT CLI FLAG, never an ambient environment
rem variable. An env var can leak: left set from a prior test run in the same
rem shell, inherited from a parent process, or set globally. A leaked
rem PIPELINE_APP_LAUNCH_DRYRUN would make a normal launch run the gates, print
rem one line and exit 0 with nothing started -- and on a double-click launch
rem (how an operator actually runs a .bat) the console closes before that line
rem can be read, so there is no signal at all. That is F-78 exactly: a success
rem exit code emitted without success, just relocated from a missing venv to a
rem leaked variable. A flag is visible on the invocation and cannot leak.
if /i "%~1"=="--check-only" (
  echo [start_pipeline] --check-only: preflight passed. OPENING BROWSER would follow.
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
