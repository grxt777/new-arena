@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 was not found. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist "data\incoming" mkdir data\incoming
if not exist "data\archive" mkdir data\archive
if not exist "data\rejected" mkdir data\rejected
if not exist "logs" mkdir logs

echo Installation complete. Run run.bat
pause
