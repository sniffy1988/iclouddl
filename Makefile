.PHONY: help start start-local build up down logs migrate shell-api shell-worker test

# Default: one command to run everything
.DEFAULT_GOAL := start

help:
	@echo "One command:"
	@echo "  make start     - Start app (Docker if installed, else local Python)"
	@echo "  make start-local - Force local start without Docker"
	@echo ""
	@echo "Same via ./start.sh:"
	@echo "  ./start.sh logs | down | migrate | help"
	@echo ""
	@echo "Other targets:"
	@echo "  make build     - Build application image only"
	@echo "  make up        - Start without rebuild"
	@echo "  make down      - Stop and remove containers"
	@echo "  make logs      - Follow logs (api + worker)"
	@echo "  make migrate   - Run Alembic migrations only"
	@echo "  make db-viewer - Open DB viewer URL hint (port 8766)"
	@echo "  make shell-api - Open shell in api container"
	@echo "  make test      - Run pytest locally"

start:
	@chmod +x scripts/start.sh scripts/start-local.sh scripts/compose.sh start.sh 2>/dev/null || true
	@./scripts/start.sh

start-local:
	@chmod +x scripts/start-local.sh 2>/dev/null || true
	@./scripts/start-local.sh

build:
	@chmod +x scripts/compose.sh 2>/dev/null || true
	./scripts/compose.sh build

up:
	@test -f .env || cp .env.docker.example .env
	./scripts/compose.sh up -d

down:
	./start.sh down

logs:
	./start.sh logs

migrate:
	./start.sh migrate

db-viewer:
	@echo "DB viewer: http://127.0.0.1:$${DB_VIEWER_PORT:-8766}"
	@echo "Start stack with ./start.sh (profile dbviewer). Set DB_VIEWER_ENABLED=0 to disable."

shell-api:
	./scripts/compose.sh exec api bash

shell-worker:
	./scripts/compose.sh exec worker bash

test:
	pytest -q
