@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

if not exist "logs" mkdir logs
if not exist "data\incoming" mkdir data\incoming
if not exist "data\archive" mkdir data\archive
if not exist "data\rejected" mkdir data\rejected

start "ATM Forecast Web" cmd /c "call .venv\Scripts\activate.bat && python server.py"

echo ATM Forecast started.
echo Web panel: http://127.0.0.1:8080
echo Put CSV/XLSX reports into data\incoming

echo Importer checks the folder every 10 minutes.

:loop
.venv\Scripts\python.exe importer.py >> logs\importer.log 2>&1
timeout /t 600 /nobreak >nul
goto loop
