#!/usr/bin/env bash
# Ensure local Redis for dev (default redis://127.0.0.1:6379/0).
# Usage: ./scripts/redis-dev.sh [ensure|start|stop|status]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONTAINER_NAME="${ICLOUDDL_REDIS_CONTAINER:-iclouddl-redis}"
REDIS_IMAGE="${ICLOUDDL_REDIS_IMAGE:-redis:7-alpine}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

if [ -f .env ]; then
  val="$(grep -E '^REDIS_URL=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \r' || true)"
  [ -n "$val" ] && REDIS_URL="$val"
fi
export REDIS_URL

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -u "$REDIS_URL" ping 2>/dev/null | grep -q PONG && return 0
  fi
  if [ -d "$ROOT/.venv" ]; then
    # shellcheck source=/dev/null
    source "$ROOT/.venv/bin/activate" 2>/dev/null || true
  fi
  python3 -c "import redis; redis.from_url('${REDIS_URL}').ping()" 2>/dev/null
}

docker_redis_start() {
  command -v docker >/dev/null 2>&1 || return 1
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
    docker start "$CONTAINER_NAME" >/dev/null
  else
    docker run -d --name "$CONTAINER_NAME" -p 6379:6379 "$REDIS_IMAGE" >/dev/null
  fi
}

wait_for_redis() {
  local i
  for i in $(seq 1 30); do
    if redis_ping; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

cmd="${1:-ensure}"

case "$cmd" in
  status)
    if redis_ping; then
      echo "Redis OK at $REDIS_URL"
      exit 0
    fi
    echo "Redis not reachable at $REDIS_URL"
    exit 1
    ;;
  start)
    if redis_ping; then
      echo "Redis already running at $REDIS_URL"
      exit 0
    fi
    if docker_redis_start; then
      echo "Starting Redis container $CONTAINER_NAME..."
      wait_for_redis && echo "Redis ready at $REDIS_URL" && exit 0
    fi
    echo "Could not start Redis. Install Redis or Docker." >&2
    exit 1
    ;;
  stop)
    if command -v docker >/dev/null 2>&1; then
      if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
        docker stop "$CONTAINER_NAME" >/dev/null
        echo "Stopped $CONTAINER_NAME"
        exit 0
      fi
    fi
    echo "No dev Redis container to stop ($CONTAINER_NAME)"
    exit 0
    ;;
  ensure)
    if redis_ping; then
      exit 0
    fi
    echo "Redis not reachable at $REDIS_URL — trying to start it..."
    if docker_redis_start; then
      if wait_for_redis; then
        echo "Redis ready (container: $CONTAINER_NAME)"
        exit 0
      fi
      echo "Redis container started but not responding yet." >&2
      exit 1
    fi
    if command -v redis-server >/dev/null 2>&1 && [[ "$REDIS_URL" == redis://127.0.0.1:6379/* || "$REDIS_URL" == redis://localhost:6379/* ]]; then
      echo "Starting redis-server in the background..."
      redis-server --daemonize yes --port 6379 2>/dev/null || true
      if wait_for_redis; then
        echo "Redis ready (local redis-server)"
        exit 0
      fi
    fi
    echo "Error: Redis is required but not reachable at $REDIS_URL" >&2
    echo "  With Docker:  ./scripts/redis-dev.sh start" >&2
    echo "  Or manually:  docker run -d --name $CONTAINER_NAME -p 6379:6379 $REDIS_IMAGE" >&2
    echo "  Or install:   brew install redis && redis-server" >&2
    exit 1
    ;;
  -h|--help|help)
    cat <<EOF
Usage: ./scripts/redis-dev.sh [command]

Commands:
  ensure   Start Redis if needed (used by start-local.sh)
  start    Start Docker dev Redis container
  stop     Stop Docker dev Redis container
  status   Check connectivity

Environment:
  REDIS_URL (from .env or redis://127.0.0.1:6379/0)
  ICLOUDDL_REDIS_CONTAINER (default: iclouddl-redis)
EOF
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    exit 1
    ;;
esac
