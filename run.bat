@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".run.lock" (
    echo ATM Forecast is already running, or a stale lock exists.
    echo If it is not running, delete .run.lock and start again.
    pause
    exit /b 0
)
mkdir ".run.lock" >nul 2>&1
if errorlevel 1 exit /b 0

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.10+ was not found. Install Python and start run.bat again.
        rmdir /s /q ".run.lock"
        pause
        exit /b 1
    )
    echo First start: creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
    set "PY=.venv\Scripts\python.exe"
    echo Installing dependencies...
    "%PY%" -m pip install --upgrade pip
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

if not exist "logs" mkdir logs
if not exist "data\incoming" mkdir data\incoming
if not exist "data\archive" mkdir data\archive
if not exist "data\rejected" mkdir data\rejected

start "ATM Forecast Web" /min cmd /c "cd /d %~dp0 && %PY% server.py >> logs\server.log 2>&1"

echo ATM Forecast is running.
echo Web panel: http://127.0.0.1:8080
echo Reports folder: data\incoming
echo Import interval: 10 minutes
echo Close this window to stop importing.

:loop
"%PY%" importer.py >> logs\importer.log 2>&1
timeout /t 600 /nobreak >nul
goto loop

:error
if exist ".run.lock" rmdir /s /q ".run.lock"
echo Startup failed. Check the messages above.
pause
exit /b 1
