#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

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

if [[ -n "${DATABASE_URL:-}" ]]; then
  psql "$DATABASE_URL" -c "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
  psql "$DATABASE_URL" < "$BACKUP_FILE"
else
  DB_USER="${DB_USER:-}"
  DB_NAME="${DB_NAME:-}"

  if [[ -z "$DB_USER" || -z "$DB_NAME" ]]; then
    echo "Error: set DATABASE_URL or DB_USER and DB_NAME in .env" >&2
    exit 1
  fi

  docker-compose stop web
  docker-compose exec -T db psql \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -c "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
  cat "$BACKUP_FILE" | docker-compose exec -T db psql \
    -U "$DB_USER" \
    -d "$DB_NAME"
  docker-compose start web
fi

echo "Defaults restore completed from: $BACKUP_FILE"
