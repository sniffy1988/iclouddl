.PHONY: help start start-local build up down logs migrate shell-api shell-worker test

# Default: one command to run everything
.DEFAULT_GOAL := start

help:
	@echo "One command:"
	@echo "  make start     - Start app (Docker if installed, else local Python)"
	@echo "  make start-local - Force local start without Docker"
	@echo ""
	@echo "Other targets:"
	@echo "  make build     - Build application image only"
	@echo "  make up        - Start without rebuild"
	@echo "  make down      - Stop and remove containers"
	@echo "  make logs      - Follow logs (api + worker)"
	@echo "  make migrate   - Run Alembic migrations only"
	@echo "  make shell-api - Open shell in api container"
	@echo "  make test      - Run pytest locally"

start:
	@chmod +x scripts/start.sh scripts/start-local.sh start.sh 2>/dev/null || true
	@./scripts/start.sh

start-local:
	@chmod +x scripts/start-local.sh 2>/dev/null || true
	@./scripts/start-local.sh

build:
	docker compose build

up:
	@test -f .env || cp .env.docker.example .env
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

migrate:
	docker compose run --rm migrate alembic upgrade head

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

test:
	pytest -q
