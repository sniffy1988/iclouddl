#!/bin/sh
set -e

mkdir -p /data/downloads /data/cookies

# Wait for PostgreSQL only when using the postgres compose overlay
if [ -n "${DATABASE_URL}" ]; then
  case "${DATABASE_URL}" in
    *@postgres:*|*@postgres/*)
      echo "Waiting for PostgreSQL..."
      until python -c "
import sys
from sqlalchemy import create_engine, text
url = sys.argv[1]
e = create_engine(url, pool_pre_ping=True)
with e.connect() as c:
    c.execute(text('SELECT 1'))
" "${DATABASE_URL}" 2>/dev/null; do
        sleep 2
      done
      echo "PostgreSQL is ready."
      ;;
    sqlite:*)
      echo "Using SQLite file database: ${DATABASE_URL}"
      ;;
  esac
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

exec "$@"
