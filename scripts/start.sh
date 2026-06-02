#!/usr/bin/env bash
# Start iCloud Photo Downloader — Docker if available, otherwise local Python.
# Usage: ./start.sh [up|logs|down|migrate|help]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=compose.sh
source "$ROOT/scripts/compose.sh"

export FORCE_COLOR="${FORCE_COLOR:-1}"

usage() {
  cat <<'EOF'
Usage: ./start.sh [command]

Commands:
  up, start     Build, migrate, and start api + worker (default)
  logs          Follow api, worker, and db-viewer logs (colorful when FORCE_COLOR=1)
  down          Stop containers
  migrate       Run Alembic migrations only (Docker)
  help          Show this help

Without Docker: any command runs the local launcher (./scripts/start-local.sh).

DB viewer (Docker, profile dbviewer): http://127.0.0.1:8766 by default.
  Set DB_VIEWER_ENABLED=0 in .env to disable. Optional DB_VIEWER_PASSWORD for SQLite.
EOF
}

use_docker() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

ensure_env() {
  if [ ! -f .env ]; then
    cp .env.docker.example .env
    echo "Created .env from .env.docker.example"
    echo "  → On first open, create the admin account in the web UI."
  fi
  if ! grep -qE '^FORCE_COLOR=' .env 2>/dev/null; then
    echo "FORCE_COLOR=1" >> .env
    echo "  → Added FORCE_COLOR=1 to .env (ANSI logs in docker compose logs)"
  fi
}

read_ports() {
  WEB_PORT="${WEB_PORT:-8765}"
  DB_VIEWER_PORT="${DB_VIEWER_PORT:-8766}"
  if [ -f .env ]; then
    val="$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
    [ -n "$val" ] && WEB_PORT="$val"
    val="$(grep -E '^DB_VIEWER_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
    [ -n "$val" ] && DB_VIEWER_PORT="$val"
  fi
}

db_viewer_hint() {
  local enabled
  enabled="$(env_var_from_dotenv DB_VIEWER_ENABLED 1)"
  case "$enabled" in
    0|false|no|off|FALSE|NO|OFF) return ;;
  esac
  if [ -f .env ] && grep -qE '^DATABASE_URL=postgresql' .env 2>/dev/null; then
    echo "  DB view: http://127.0.0.1:${DB_VIEWER_PORT} (Adminer → postgres, password from .env)"
  else
    echo "  DB view: http://127.0.0.1:${DB_VIEWER_PORT} (sqlite-web, read-only)"
  fi
}

cmd="${1:-up}"
case "$cmd" in
  -h|--help|help)
    usage
    exit 0
    ;;
esac

if ! use_docker; then
  case "$cmd" in
    up|start|"")
      echo "Docker not found — starting locally (Python + SQLite in ./data/)..."
      echo ""
      exec "$ROOT/scripts/start-local.sh"
      ;;
    logs|down|migrate)
      echo "Error: '$cmd' requires Docker. Install Docker or use local commands." >&2
      echo "  Local: iclouddownloader db-upgrade | iclouddownloader web start" >&2
      exit 1
      ;;
    *)
      echo "Error: unknown command '$cmd'" >&2
      usage >&2
      exit 1
      ;;
  esac
fi

ensure_env
mkdir -p data/downloads data/cookies

case "$cmd" in
  logs)
    services=(api worker)
    enabled="$(env_var_from_dotenv DB_VIEWER_ENABLED 1)"
    case "$enabled" in
      0|false|no|off|FALSE|NO|OFF) ;;
      *) services+=(db-viewer) ;;
    esac
    exec "$ROOT/scripts/compose.sh" logs -f "${services[@]}"
    ;;
  down)
    exec "$ROOT/scripts/compose.sh" down
    ;;
  migrate)
    echo "Running database migrations..."
    exec "$ROOT/scripts/compose.sh" run --rm migrate
    ;;
  up|start|"")
    echo "Building image (web UI + app), running migrations, starting api + worker..."
    echo "  (migrate service runs alembic upgrade head; api/worker start after it succeeds)"
    "$ROOT/scripts/compose.sh" up -d --build

    read_ports

    enabled="$(env_var_from_dotenv DB_VIEWER_ENABLED 1)"
    case "$enabled" in
      0|false|no|off|FALSE|NO|OFF) ;;
      *)
        sleep 1
        if [ -n "$("$ROOT/scripts/compose.sh" ps -q db-viewer 2>/dev/null || true)" ]; then
          echo ""
          echo "DB viewer startup:"
          "$ROOT/scripts/compose.sh" logs --no-color db-viewer 2>/dev/null | tail -5 || true
        fi
        ;;
    esac

    echo ""
    echo "iCloud Photo Downloader is running (Docker)."
    echo "  Web UI:  http://localhost:${WEB_PORT}"
    echo "  Login:   create admin on first visit (stored in database)"
    echo "  Data:    ./data/iclouddownloader.db"
    echo "           ./data/downloads/<user>/icloud/ and .../google_photo/"
    echo "           ./data/cookies/ (iCloud sessions)"
    db_viewer_hint
    echo "  Logs:    Settings → Logging level; console colors via FORCE_COLOR in .env"
    echo ""
    echo "Useful commands:"
    echo "  ./start.sh logs              # follow api, worker, and db-viewer logs"
    echo "  ./start.sh down              # stop containers"
    echo "  ./start.sh migrate           # migrations only"
    echo "  ./scripts/start-local.sh     # run without Docker (venv, db-upgrade, npm build)"
    ;;
  *)
    echo "Error: unknown command '$cmd'" >&2
    usage >&2
    exit 1
    ;;
esac
