#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

mkdir -p backups/defaults
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="backups/defaults/default-templates-${TIMESTAMP}.sql"

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump "$DATABASE_URL" \
    --data-only \
    --inserts \
    --column-inserts \
    --table default_store_templates \
    --table default_category_templates \
    --table default_item_templates \
    > "$OUT_FILE"
else
  DB_USER="${DB_USER:-}"
  DB_NAME="${DB_NAME:-}"

  if [[ -z "$DB_USER" || -z "$DB_NAME" ]]; then
    echo "Error: set DATABASE_URL or DB_USER and DB_NAME in .env" >&2
    exit 1
  fi

  docker-compose exec -T db pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --data-only \
    --inserts \
    --column-inserts \
    --table default_store_templates \
    --table default_category_templates \
    --table default_item_templates \
    > "$OUT_FILE"
fi

echo "Defaults backup written: $OUT_FILE"
