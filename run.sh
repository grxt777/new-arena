#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

LOCK_DIR=".run.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "ATM Forecast is already running, or a stale lock exists."
  echo "If it is not running, delete .run.lock and start again."
  exit 0
fi
cleanup_lock() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup_lock EXIT INT TERM

if [ ! -x ".venv/bin/python" ]; then
  command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ not found"; exit 1; }
  echo "First start: creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

mkdir -p logs data/incoming data/archive data/rejected
.venv/bin/python server.py >> logs/server.log 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  cleanup_lock
}
trap cleanup EXIT INT TERM

echo "ATM Forecast is running."
echo "Web panel: http://127.0.0.1:8000"
echo "Reports folder: data/incoming"
echo "Import interval: 10 minutes"
echo "Press Ctrl+C to stop."

while true; do
  .venv/bin/python importer.py >> logs/importer.log 2>&1
  sleep 600
done
