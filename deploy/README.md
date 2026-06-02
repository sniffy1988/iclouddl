# Pull image on your server

GitHub Actions builds and pushes the image to **GHCR** on every push to `main`. You pull and run it on each server yourself.

## Image

```
ghcr.io/sniffy1988/iclouddl:latest
ghcr.io/sniffy1988/iclouddl:<git-sha>
```

Published as a **multi-architecture** manifest. Docker pulls the matching image automatically:

| Platform | Typical hardware |
|----------|------------------|
| `linux/amd64` | Intel/AMD PCs and VPS |
| `linux/arm64` | Apple Silicon Macs, AWS Graviton, Raspberry Pi 4/5 (64-bit OS) |

Check after pull: `docker image inspect ghcr.io/sniffy1988/iclouddl:latest --format '{{.Os}}/{{.Architecture}}'`

Repository: https://github.com/sniffy1988/iclouddl

## One-time server setup

```bash
mkdir -p ~/iclouddownloader/data/downloads ~/iclouddownloader/data/cookies
cd ~/iclouddownloader

# Copy from the repo (clone or scp):
#   docker-compose.yml
#   docker-compose.prod.yml
#   scripts/docker-entrypoint.sh
cp .env.docker.example .env   # edit passwords and tokens
```

Install Docker and Docker Compose v2. Open port **8765** (or your `WEB_PORT`).

### Log in to GHCR (if the package is private)

```bash
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u sniffy1988 --password-stdin
```

Use a PAT with `read:packages`. Or make the package public under **GitHub → Packages → iclouddl → Package settings**.

## Pull and run

```bash
cd ~/iclouddownloader
export DOCKER_IMAGE=ghcr.io/sniffy1988/iclouddl:latest

docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build --remove-orphans
```

After a new release:

```bash
export DOCKER_IMAGE=ghcr.io/sniffy1988/iclouddl:latest
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build
```

Keep `.env` and `./data/` on the server — they are not touched by CI.

Configure Immich in **Settings** (URL, API key, test connection). Per Apple ID, link an external library on **Users → user → Immich external library**.

## GitHub Actions

| Workflow | Trigger | What it does |
|----------|---------|----------------|
| [CI](../.github/workflows/ci.yml) | Push / PR | Tests + local Docker smoke test |
| [Docker image](../.github/workflows/docker-image.yml) | Push to `main` | Multi-arch build (`amd64` + `arm64`) and push to GHCR |

No SSH deploy from GitHub — you control when each server updates.
