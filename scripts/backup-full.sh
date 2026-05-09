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

usage() {
  cat <<'EOF'
Usage:
  scripts/backup-full.sh [--gpg-recipient <recipient>]

Examples:
  scripts/backup-full.sh
  scripts/backup-full.sh --gpg-recipient ops@example.com

Behavior:
  - Creates a full schema+data backup under backups/full.
  - Applies umask 077 so backup files are owner-readable/writable only.
  - Optionally encrypts output with GPG when --gpg-recipient is provided.
EOF
}

GPG_RECIPIENT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpg-recipient)
      GPG_RECIPIENT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$GPG_RECIPIENT" ]] && ! command -v gpg >/dev/null 2>&1; then
  echo "Error: gpg is required when --gpg-recipient is used." >&2
  exit 1
fi

umask 077

mkdir -p backups/full
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="backups/full/full-backup-${TIMESTAMP}.sql"
if [[ -n "$GPG_RECIPIENT" ]]; then
  OUT_FILE="${OUT_FILE}.gpg"
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  if [[ -n "$GPG_RECIPIENT" ]]; then
    pg_dump "$DATABASE_URL" \
      --clean \
      --if-exists \
      | gpg --batch --yes --encrypt --recipient "$GPG_RECIPIENT" --output "$OUT_FILE"
  else
    pg_dump "$DATABASE_URL" \
      --clean \
      --if-exists \
      > "$OUT_FILE"
  fi
else
  DB_USER="${DB_USER:-}"
  DB_NAME="${DB_NAME:-}"

  if [[ -z "$DB_USER" || -z "$DB_NAME" ]]; then
    echo "Error: set DATABASE_URL or DB_USER and DB_NAME in .env" >&2
    exit 1
  fi

  if [[ -n "$GPG_RECIPIENT" ]]; then
    docker-compose exec -T db pg_dump \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      --clean \
      --if-exists \
      | gpg --batch --yes --encrypt --recipient "$GPG_RECIPIENT" --output "$OUT_FILE"
  else
    docker-compose exec -T db pg_dump \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      --clean \
      --if-exists \
      > "$OUT_FILE"
  fi
fi

echo "Full backup written: $OUT_FILE"
