#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

LOCK_DIR=".run.lock"

# При повторном запуске корректно завершаем предыдущий экземпляр.
if [ -f "$LOCK_DIR/pid" ]; then
  OLD_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    OLD_CMD=$(ps -p "$OLD_PID" -o command= 2>/dev/null || true)
    if [[ "$OLD_CMD" == *"run.sh"* ]]; then
      echo "Stopping previous ATM Forecast instance (PID $OLD_PID)..."
      kill -TERM "$OLD_PID" 2>/dev/null || true
      for i in {1..10}; do
        kill -0 "$OLD_PID" 2>/dev/null || break
        sleep 0.2
      done
      kill -KILL "$OLD_PID" 2>/dev/null || true
    fi
  fi
  rm -rf "$LOCK_DIR"
elif [ -d "$LOCK_DIR" ]; then
  rm -rf "$LOCK_DIR"
fi

mkdir "$LOCK_DIR" || exit 1
echo $$ > "$LOCK_DIR/pid"
cleanup_lock() { rm -rf "$LOCK_DIR" 2>/dev/null || true; }
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
echo "Import interval: 5 seconds"
echo "A repeated ./run.sh automatically restarts the previous instance."
echo "Press Ctrl+C to stop."

while true; do
  .venv/bin/python importer.py >> logs/importer.log 2>&1
  sleep 5
done
