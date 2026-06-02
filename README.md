# iCloud Photo Downloader

Multi-user photo backup service for **iCloud Photos** and **Google Photos** with a SQLite database, scheduled sync daemon, Telegram alerts, and a web admin UI.

## Features

- **Dual sources** — one user profile can link iCloud and Google Photos into the same download folder
- **Per-provider actions** — separate Count / Sync iCloud and Count / Sync Google; optional **Sync all** (parallel)
- **Unlimited users** — each profile has its own download directory and sync schedule
- **Download only** — one-way backup; never deletes local files or modifies cloud libraries
- **SQLite file database** — all state stored in `./data/iclouddownloader.db` (survives restarts; easy to back up)
- **Daemon** — polls for users due for sync on a configurable interval (default 6 hours)
- **Telegram** — optional bot for iCloud 2FA: message your bot with `/code 123456` when prompted
- **Web UI** — manage users, monitor syncs, submit 2FA codes, live SSE event feed

## Apple account requirements

1. Enable **Settings → Apple ID → iCloud → Access iCloud Data on the Web** on your iPhone/iPad
2. **Disable Advanced Data Protection** — it blocks server-side photo API access
3. Use an app-specific password or account password with 2FA for initial login

## Google Photos setup

1. Create a [Google Cloud](https://console.cloud.google.com/) project and enable **Photos Library API**
2. Create an **OAuth 2.0 Web client** with redirect URI: `{WEB_PUBLIC_BASE_URL}/api/auth/google/callback` (e.g. `http://localhost:8765/api/auth/google/callback`)
3. Set in **Settings → Google Photos OAuth** (stored in DB): client ID and client secret
4. Set in `.env`:
   - `WEB_PUBLIC_BASE_URL` — must match the host users open in the browser
   - `TOKEN_ENCRYPTION_KEY` — Fernet key for refresh tokens at rest (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
5. On a user page, click **Connect Google Photos** and complete OAuth
6. For users with **both** sources, use a path template with `{source}` (e.g. `{source}/YYYY/MM/DD/{filename}`) in Settings

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

Then open **http://localhost:8765** — on first visit you will **create the admin account** (password stored in the database). Change it later under **Settings → Admin login**.

This starts:

| Service | Role |
|---------|------|
| `migrate` | Runs `alembic upgrade head` once, then exits |
| `api` | Web UI + REST API on port **8765** (configurable via `WEB_PORT`) |
| `worker` | Sync scheduler + Telegram bot |
| `db-viewer` | SQLite/Postgres browser on **8766** (localhost only; optional profile) |

No separate database server — SQLite file lives in **`./data/`** on your machine.

### Database viewer (dev)

After `./start.sh`, open **http://127.0.0.1:8766** (port `DB_VIEWER_PORT` in `.env`):

- **SQLite (default)** — [sqlite-web](https://github.com/coleifer/sqlite-web), read-only browse of `data/iclouddownloader.db`
- **PostgreSQL overlay** — [Adminer](https://www.adminer.org/) pre-filled for host `postgres` (password from `POSTGRES_PASSWORD` in `.env`)

Disable with `DB_VIEWER_ENABLED=0`. Optional `DB_VIEWER_PASSWORD` protects sqlite-web. The viewer binds to **127.0.0.1** only (not exposed on your LAN).

Local (no Docker): `pip install sqlite-web && sqlite_web -r -p 8766 ./data/iclouddownloader.db`

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

### Multi-architecture image (GHCR)

CI builds and pushes one manifest tag for **amd64** and **arm64**. On any server or Mac:

```bash
docker pull ghcr.io/sniffy1988/iclouddl:latest
```

Local multi-arch build (optional):

```bash
docker buildx create --use --name multi 2>/dev/null || docker buildx use multi
docker buildx build --platform linux/amd64,linux/arm64 -t iclouddownloader:local --load .
# --load only works for a single platform; omit --load and use --push to publish both.
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
| `DB_VIEWER_PORT` | DB browser port on localhost only (default `8766`) |
| `DB_VIEWER_ENABLED` | Set `0` to skip the db-viewer container (default `1`) |
| `DB_VIEWER_PASSWORD` | Optional password for sqlite-web (Docker SQLite mode) |
| Admin login | Created on first web visit (database only; not `.env`) |
| Telegram | **Settings** in the web UI only (stored in the database, not `.env`) |
| `IMMICH_SCAN_DEBOUNCE_SECONDS` | Global min seconds between Immich scans (default 120) |

Immich server URL and API key are configured in **Settings** (with test connection). On each **User** page, link that Apple ID to an Immich external library ID so scans run after sync.

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
| [Docker image](.github/workflows/docker-image.yml) | Push to `main` | Multi-arch image (`linux/amd64`, `linux/arm64`) pushed to **GHCR** |

Pull and run: [deploy/README.md](deploy/README.md).

```bash
git remote add origin https://github.com/sniffy1988/iclouddl.git
git push -u origin main
```

## License

MIT
