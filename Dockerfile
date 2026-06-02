# syntax=docker/dockerfile:1

# --- Web UI build stage ---
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Python application stage ---
FROM python:3.12-slim AS app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN pip install --no-cache-dir -e . \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

COPY --from=web-builder /web/dist ./web/dist

ENV PYTHONUNBUFFERED=1 \
    BASE_DOWNLOAD_DIR=/data/downloads \
    COOKIE_DIR=/data/cookies \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8765

RUN mkdir -p /data/downloads /data/cookies

VOLUME ["/data/downloads", "/data/cookies"]

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('WEB_PORT','8765'))" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["iclouddownloader", "web", "start"]
