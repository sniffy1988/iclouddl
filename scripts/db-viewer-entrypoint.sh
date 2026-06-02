#!/bin/sh
# Print uvicorn-style startup lines, then run sqlite-web or Adminer.
set -e

MODE="${DB_VIEWER_MODE:-sqlite}"
HOST_PORT="${DB_VIEWER_PORT:-8766}"
CONTAINER_PORT="${DB_VIEWER_CONTAINER_PORT:-8080}"

log_info() {
  # Match uvicorn log style: "INFO:     ..."
  printf 'INFO:     %s\n' "$1"
}

case "$MODE" in
  sqlite)
    DB_FILE="${SQLITE_DATABASE:-iclouddownloader.db}"
    log_info "DB viewer (sqlite-web, read-only) running on http://0.0.0.0:${CONTAINER_PORT}"
    log_info "Open on host: http://127.0.0.1:${HOST_PORT} (Press CTRL+C in this container to quit)"
    SQLITE_ARGS="-H 0.0.0.0 ${DB_FILE} --read-only --no-browser"
    if [ -n "${SQLITE_WEB_PASSWORD:-}" ]; then
      SQLITE_ARGS="${SQLITE_ARGS} -P ${SQLITE_WEB_PASSWORD}"
    fi
    # shellcheck disable=SC2086
    exec sqlite_wsgi ${SQLITE_ARGS}
    ;;
  adminer)
    log_info "DB viewer (Adminer) running on http://0.0.0.0:${CONTAINER_PORT}"
    log_info "Open on host: http://127.0.0.1:${HOST_PORT} — server: postgres (Press CTRL+C in this container to quit)"
    exec php -d variables_order=EGPCS -S "[::]:8080" -t /var/www/html
    ;;
  *)
    log_info "ERROR: unknown DB_VIEWER_MODE=${MODE}"
    exit 1
    ;;
esac
