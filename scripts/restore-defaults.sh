#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

load_env_key() {
  local key="$1"
  local env_file=".env"
  local line=""
  local value=""

  [[ -f "$env_file" ]] || return 0

  line="$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" "$env_file" | tail -n1 || true)"
  [[ -n "$line" ]] || return 0

  line="${line#"${line%%[![:space:]]*}"}"
  line="${line#export }"
  value="${line#*=}"
  value="${value%$'\r'}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"

  if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi

  export "$key=$value"
}

for key in DATABASE_URL DB_USER DB_PASSWORD DB_HOST DB_PORT DB_NAME; do
  load_env_key "$key"
done

WEB_STOPPED="false"
restore_web_on_exit() {
  if [[ "$WEB_STOPPED" == "true" ]]; then
    docker-compose start web >/dev/null 2>&1 || true
  fi
}
trap restore_web_on_exit EXIT

usage() {
  cat <<'EOF'
Usage:
  scripts/restore-defaults.sh <backup.sql> [--yes]

Examples:
  scripts/restore-defaults.sh backups/defaults/default-templates-20260509-120000.sql
  scripts/restore-defaults.sh backups/defaults/default-templates-20260509-120000.sql --yes

Behavior:
  - Truncates default template tables and reloads data from the provided SQL file.
  - Stops the web service before restore and starts it again afterwards when using docker-compose mode.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

BACKUP_FILE="$1"
ASSUME_YES="${2:-}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Error: backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ "$ASSUME_YES" != "--yes" ]]; then
  echo "This will replace all default templates using: $BACKUP_FILE"
  read -r -p "Continue? [y/N] " REPLY
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

BACKUP_ABS="$(cd "$(dirname "$BACKUP_FILE")" && pwd)/$(basename "$BACKUP_FILE")"

if [[ -n "${DATABASE_URL:-}" ]]; then
  {
    echo "BEGIN;"
    echo "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
    cat "$BACKUP_ABS"
    echo "COMMIT;"
  } | psql "$DATABASE_URL" -v ON_ERROR_STOP=1
else
  DB_USER="${DB_USER:-}"
  DB_NAME="${DB_NAME:-}"

  if [[ -z "$DB_USER" || -z "$DB_NAME" ]]; then
    echo "Error: set DATABASE_URL or DB_USER and DB_NAME in .env" >&2
    exit 1
  fi

  docker-compose stop web
  WEB_STOPPED="true"
  {
    echo "BEGIN;"
    echo "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
    cat "$BACKUP_ABS"
    echo "COMMIT;"
  } | docker-compose exec -T db psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -v ON_ERROR_STOP=1
  docker-compose start web
  WEB_STOPPED="false"
fi

echo "Defaults restore completed from: $BACKUP_FILE"
