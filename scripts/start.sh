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
  echo "  → Set WEB_ADMIN_PASSWORD in .env before production use."
fi

mkdir -p data/downloads data/cookies

echo "Building and starting migrate, api, worker (SQLite DB in ./data/)..."
docker compose up -d --build

WEB_PORT="${WEB_PORT:-8765}"
if [ -f .env ]; then
  val="$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
  [ -n "$val" ] && WEB_PORT="$val"
fi

echo ""
echo "iCloud Photo Downloader is running (Docker)."
echo "  Web UI:  http://localhost:${WEB_PORT}"
echo "  Login:   password from WEB_ADMIN_PASSWORD in .env"
echo "  Data:    ./data/iclouddownloader.db"
echo "           ./data/downloads/ (photos)"
echo "           ./data/cookies/ (iCloud sessions)"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f api worker"
echo "  docker compose down"
echo "  ./scripts/start-local.sh   # run without Docker"
