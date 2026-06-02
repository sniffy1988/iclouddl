# Deploy with GitHub Actions

Pushes to `main` build a Docker image, push it to **GitHub Container Registry (GHCR)**, and deploy to your server over SSH.

## 1. GitHub repository

Remote: https://github.com/sniffy1988/iclouddl.git

```bash
git push -u origin main
```

Container image: `ghcr.io/sniffy1988/iclouddl:latest`

## 2. Server setup (one time)

On the VPS or home server:

```bash
mkdir -p ~/iclouddownloader/data/downloads ~/iclouddownloader/data/cookies
cd ~/iclouddownloader
cp .env.docker.example .env   # edit passwords and tokens
```

Install Docker and Docker Compose v2. Open firewall port `WEB_PORT` (default **8765**).

Make the GHCR package **public** or log in on the server so `docker pull` works:

```bash
echo "$GITHUB_PAT" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
```

Use a PAT with `read:packages` if the image is private.

## 3. GitHub repository secrets

In **Settings → Secrets and variables → Actions**, add:

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Server hostname or IP |
| `DEPLOY_USER` | SSH user (e.g. `deploy`, `ubuntu`) |
| `DEPLOY_SSH_KEY` | Private key (PEM) for that user |
| `DEPLOY_PATH` | Deploy directory (e.g. `/home/deploy/iclouddownloader`) |
| `DEPLOY_PORT` | Optional SSH port (default `22`) |

## 4. GitHub Environment (optional)

Create environment **production** with required reviewers if you want approval before deploy.

## 5. First deploy

Push to `main` or run workflow **Deploy** manually from the Actions tab.

The workflow copies `docker-compose.yml`, `docker-compose.prod.yml`, and the entrypoint script, then runs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Keep `.env` and `./data/` only on the server — they are not overwritten by CI.

## Manual deploy on the server

```bash
export DOCKER_IMAGE=ghcr.io/sniffy1988/iclouddl:latest
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```
