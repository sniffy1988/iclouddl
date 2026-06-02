#!/usr/bin/env bash
# Shared docker compose file list for this project.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

compose_files() {
  printf '%s\n' "$ROOT/docker-compose.yml"
  if [ -f "$ROOT/.env" ] && grep -qE '^DATABASE_URL=postgresql' "$ROOT/.env" 2>/dev/null; then
    printf '%s\n' "$ROOT/docker-compose.postgres.yml"
  fi
}

compose_args() {
  local f
  while IFS= read -r f; do
    printf -- '-f\n%s\n' "$f"
  done < <(compose_files)
}

env_var_from_dotenv() {
  local key="$1" default="${2:-}"
  local line val
  if [ -n "${!key+x}" ]; then
    printf '%s' "${!key}"
    return
  fi
  if [ -f "$ROOT/.env" ]; then
    line="$(grep -E "^${key}=" "$ROOT/.env" 2>/dev/null | tail -1 || true)"
    if [ -n "$line" ]; then
      val="${line#*=}"
      val="${val//$'\r'/}"
      val="${val#"${val%%[![:space:]]*}"}"
      val="${val%"${val##*[![:space:]]}"}"
      printf '%s' "$val"
      return
    fi
  fi
  printf '%s' "$default"
}

compose_profiles() {
  local enabled
  enabled="$(env_var_from_dotenv DB_VIEWER_ENABLED 1)"
  case "$enabled" in
    0|false|no|off|FALSE|NO|OFF) return ;;
  esac
  printf '%s' "dbviewer"
}

# Usage: ./scripts/compose.sh up -d --build
main() {
  local -a args=()
  local f profile
  while IFS= read -r f; do
    args+=(-f "$f")
  done < <(compose_files)
  profile="$(compose_profiles)"
  if [ -n "$profile" ]; then
    args+=(--profile "$profile")
  fi
  exec docker compose "${args[@]}" "$@"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
