#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Virtual environment not found. Run ./install.sh first."
  exit 1
fi

mkdir -p logs data/incoming data/archive data/rejected

.venv/bin/python server.py >> logs/server.log 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "ATM Forecast started."
echo "Web panel: http://127.0.0.1:8080"
echo "Put CSV/XLSX reports into data/incoming"
echo "Importer checks the folder every 10 minutes."

while true; do
  .venv/bin/python importer.py >> logs/importer.log 2>&1
  sleep 600
done
