# iCloud Photo Downloader

Multi-user iCloud Photos backup service with a file-based SQLite database, scheduled sync daemon, Telegram alerts, and a web admin UI.

## Features

- **Unlimited users** — each Apple ID has its own download directory and sync schedule
- **Download only** — one-way backup; never deletes local files or modifies iCloud
- **SQLite file database** — all state stored in `./data/iclouddownloader.db` (survives restarts; easy to back up)
- **Daemon** — polls for users due for sync on a configurable interval (default 6 hours)
- **Telegram** — sync notifications, 2FA code relay (`/code 123456`), admin ops messages
- **Web UI** — manage users, monitor syncs, submit 2FA codes, live SSE event feed

## Apple account requirements

1. Enable **Settings → Apple ID → iCloud → Access iCloud Data on the Web** on your iPhone/iPad
2. **Disable Advanced Data Protection** — it blocks server-side photo API access
3. Use an app-specific password or account password with 2FA for initial login

## Quick start (one command)

```bash
./start.sh
# or: make start
```

- **With Docker**: builds containers and runs API + worker.
- **Without Docker** (your case): automatically runs locally with Python — SQLite DB in `./data/`.

Force local mode (no Docker):

```bash
./scripts/start-local.sh
# or: make start-local
```

Requires **Python 3.12+** and **Node.js** (to build the web UI on first run).

Then open **http://localhost:8765** and log in with `WEB_ADMIN_PASSWORD` from `.env` (default in the example file — change it for production).

This starts:

| Service | Role |
|---------|------|
| `migrate` | Runs `alembic upgrade head` once, then exits |
| `api` | Web UI + REST API on port **8765** (configurable via `WEB_PORT`) |
| `worker` | Sync scheduler + Telegram bot |

No separate database server — SQLite file lives in **`./data/`** on your machine.

### Other commands

```bash
make start          # Same as ./start.sh (default make target)
make build          # Build image only
make up             # Start without rebuild
make down           # Stop stack
make logs           # Follow api + worker logs
make migrate        # Re-run migrations manually
make shell-api      # Shell inside api container

# Auth for an Apple ID (interactive 2FA — run once per user)
docker compose exec api iclouddownloader auth login --apple-id user@icloud.com

# Add user via CLI
docker compose exec api iclouddownloader user add --apple-id user@icloud.com
```

### Development with Docker

Mount local Python source without rebuilding:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Persistent data (`./data/`)

| Path | Contents |
|------|----------|
| `./data/iclouddownloader.db` | SQLite database (users, photos, sync history) |
| `./data/downloads/` | Downloaded photos |
| `./data/cookies/` | iCloud session cookies |

Back up the whole `data/` folder to keep everything. `docker compose down` does **not** delete it.

### Optional PostgreSQL

For a server DB instead of a file:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

### Environment

Default in [`.env.docker.example`](.env.docker.example):

```
DATABASE_URL=sqlite:////data/iclouddownloader.db
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
mkdir -p data/downloads data/cookies

iclouddownloader db-upgrade

# Terminal 1 — API + Web UI
cd web && npm install && npm run build && cd ..
iclouddownloader web start

# Terminal 2 — Worker daemon
iclouddownloader daemon start
```

Web dev with hot reload:

```bash
# API on :8765 (or WEB_PORT from .env)
iclouddownloader web start

# UI on :5173 (proxies /api to WEB_PORT)
cd web && npm run dev
```

## CLI usage

```bash
# Add a user
iclouddownloader user add --apple-id user@icloud.com

# Authenticate (interactive 2FA)
iclouddownloader auth login --apple-id user@icloud.com

# Manual sync
iclouddownloader sync --user-id 1

# List users and status
iclouddownloader user list
iclouddownloader status

# Test Telegram
iclouddownloader telegram test
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite file URL (default) or PostgreSQL connection string |
| `BASE_DOWNLOAD_DIR` | Root directory for photo downloads |
| `COOKIE_DIR` | Per-user pyicloud session cookies |
| `DEFAULT_SYNC_INTERVAL_SECONDS` | Default interval (21600 = 6h) |
| `WEB_PORT` | Web UI and API port (default `8765`) |
| `WEB_ADMIN_PASSWORD` | Web UI admin password |
| `TELEGRAM_ENABLED` | Enable Telegram bot |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Chat ID for ops notifications |

## Architecture

- **api** service — FastAPI REST + static React UI (port `WEB_PORT`, default 8765)
- **worker** service — APScheduler daemon + Telegram bot polling
- Shared **services** layer used by CLI, API, and worker

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## GitHub Actions

| Workflow | Trigger | What it does |
|----------|---------|----------------|
| [CI](.github/workflows/ci.yml) | Push / PR to `main` | `pytest`, web build, Docker build + health check |
| [Deploy](.github/workflows/deploy.yml) | Push to `main`, manual | Build image → **GHCR** → SSH `docker compose` on your server |

Setup: create the repo, add deploy secrets, and follow [deploy/README.md](deploy/README.md).

```bash
gh repo create iclouddownloader --private --source=. --remote=origin --push
```

## License

MIT
