#!/usr/bin/env bash
# Start iCloud Photo Downloader — Docker if available, otherwise local Python.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

use_docker() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

if ! use_docker; then
  echo "Docker not found — starting locally (Python + SQLite in ./data/)..."
  echo ""
  exec "$ROOT/scripts/start-local.sh"
fi

if [ ! -f .env ]; then
  cp .env.docker.example .env
  echo "Created .env from .env.docker.example"
  echo "  → On first open, create the admin account in the web UI."
fi

mkdir -p data/downloads data/cookies

echo "Building image (web UI + app), running migrations, starting api + worker..."
echo "  (migrate container applies alembic upgrade head; api/worker wait until it finishes)"
docker compose up -d --build

WEB_PORT="${WEB_PORT:-8765}"
if [ -f .env ]; then
  val="$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
  [ -n "$val" ] && WEB_PORT="$val"
fi

echo ""
echo "iCloud Photo Downloader is running (Docker)."
echo "  Web UI:  http://localhost:${WEB_PORT}"
echo "  Login:   create admin on first visit (stored in database)"
echo "  Data:    ./data/iclouddownloader.db"
echo "           ./data/downloads/ (photos)"
echo "           ./data/cookies/ (iCloud sessions)"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f api worker"
echo "  docker compose down"
echo "  docker compose run --rm migrate alembic upgrade head   # migrations only"
echo "  ./scripts/start-local.sh   # run without Docker (venv, db-upgrade, npm build)"
