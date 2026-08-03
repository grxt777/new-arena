#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ not found"; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data/incoming data/archive data/rejected logs
chmod +x run.sh install.sh
echo "Installation complete. Run ./run.sh"
