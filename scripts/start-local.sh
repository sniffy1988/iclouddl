#!/usr/bin/env bash
# Start API + worker locally without Docker (SQLite file DB in ./data/).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export FORCE_COLOR="${FORCE_COLOR:-1}"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: Python 3 is required. Install Python 3.12+ or set PYTHON=..." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo "Installing dependencies..."
pip install -e ".[dev]" -q

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

mkdir -p data/downloads data/cookies

echo "Applying database migrations (alembic upgrade head)..."
iclouddownloader db-upgrade

if command -v npm >/dev/null 2>&1; then
  echo "Building web UI..."
  (
    cd web
    if [ -f package-lock.json ]; then
      npm ci
    else
      npm install
    fi
    npm run build
  )
else
  if [ ! -f web/dist/index.html ]; then
    echo "Warning: npm not found — Web UI will not load until you run:"
    echo "  cd web && npm install && npm run build"
  fi
fi

WEB_PORT="${WEB_PORT:-8765}"
DB_VIEWER_PORT="${DB_VIEWER_PORT:-8766}"
if [ -f .env ]; then
  val="$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
  [ -n "$val" ] && WEB_PORT="$val"
  val="$(grep -E '^DB_VIEWER_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
  [ -n "$val" ] && DB_VIEWER_PORT="$val"
fi

echo ""
echo "Starting worker (background) and web API (foreground)..."
echo "  Web UI:  http://localhost:${WEB_PORT}"
echo "  Login:   create admin on first visit (stored in database)"
echo "  Data:    ./data/iclouddownloader.db"
echo "           ./data/downloads/<user>/icloud/ and .../google_photo/"
if command -v sqlite_web >/dev/null 2>&1; then
  echo "  DB view: http://127.0.0.1:${DB_VIEWER_PORT} (starting sqlite-web read-only)"
else
  echo "  DB view: pip install sqlite-web && sqlite_web -r -p ${DB_VIEWER_PORT} ./data/iclouddownloader.db"
fi
echo "  Stop:    Ctrl+C"
echo ""

DB_VIEWER_PID=""
if command -v sqlite_web >/dev/null 2>&1 && [ -f "$ROOT/data/iclouddownloader.db" ]; then
  enabled="$(grep -E '^DB_VIEWER_ENABLED=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' \r' || true)"
  enabled="${enabled:-1}"
  case "$enabled" in
    0|false|no|off|FALSE|NO|OFF) ;;
    *)
      sqlite_web -r -H 127.0.0.1 -p "$DB_VIEWER_PORT" -x "$ROOT/data/iclouddownloader.db" &
      DB_VIEWER_PID=$!
      ;;
  esac
fi

iclouddownloader daemon start &
DAEMON_PID=$!

cleanup() {
  echo ""
  echo "Stopping worker..."
  kill "$DAEMON_PID" 2>/dev/null || true
  wait "$DAEMON_PID" 2>/dev/null || true
  if [ -n "$DB_VIEWER_PID" ]; then
    kill "$DB_VIEWER_PID" 2>/dev/null || true
    wait "$DB_VIEWER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

iclouddownloader web start
