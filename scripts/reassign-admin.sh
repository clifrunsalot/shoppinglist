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
  scripts/reassign-admin.sh --from <old_admin_email> --to <new_admin_email> [--actor-email <operator_email>] [--approve-target] [--activate-target] [--dry-run] [--yes]

Examples:
  scripts/reassign-admin.sh --from you@example.com --to clifrunsalot@yahoo.com
  scripts/reassign-admin.sh --from you@example.com --to clifrunsalot@yahoo.com --actor-email admin@example.com --approve-target --activate-target --yes

Behavior:
  - Default mode is dry-run (no changes committed).
  - Use --yes to apply changes.
  - --actor-email is required when applying changes and is recorded in the audit log.
  - --approve-target and --activate-target are explicit opt-ins.
  - Commits directly to the database through Flask's app context.
EOF
}

FROM_EMAIL=""
TO_EMAIL=""
ACTOR_EMAIL=""
ASSUME_YES="false"
APPROVE_TARGET="false"
ACTIVATE_TARGET="false"
DRY_RUN="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM_EMAIL="${2:-}"
      shift 2
      ;;
    --to)
      TO_EMAIL="${2:-}"
      shift 2
      ;;
    --actor-email)
      ACTOR_EMAIL="${2:-}"
      shift 2
      ;;
    --yes)
      ASSUME_YES="true"
      shift
      ;;
    --approve-target)
      APPROVE_TARGET="true"
      shift
      ;;
    --activate-target)
      ACTIVATE_TARGET="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
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

if [[ -z "$FROM_EMAIL" || -z "$TO_EMAIL" ]]; then
  usage
  exit 1
fi

if [[ "$ASSUME_YES" == "true" ]]; then
  DRY_RUN="false"
fi

if [[ "$DRY_RUN" == "false" && -z "$ACTOR_EMAIL" ]]; then
  echo "Error: --actor-email is required when applying changes." >&2
  exit 1
fi

if [[ "$DRY_RUN" == "false" && "$ASSUME_YES" != "true" ]]; then
  echo "This will apply admin reassignment changes:"
  echo "  from: $FROM_EMAIL"
  echo "  to:   $TO_EMAIL"
  read -r -p "Continue? [y/N] " REPLY
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

PYTHON_SNIPPET=$(cat <<'PY'
from app.main import create_app
from app.db import db
from app.models import AuditLog, User
import json
import os
import re

app = create_app()

with app.app_context():

  from_email = os.environ['FROM_EMAIL'].strip().lower()
  to_email = os.environ['TO_EMAIL'].strip().lower()
  actor_email = os.environ.get('ACTOR_EMAIL', '').strip().lower()
  dry_run = os.environ['DRY_RUN'].strip().lower() == 'true'
  approve_target = os.environ['APPROVE_TARGET'].strip().lower() == 'true'
  activate_target = os.environ['ACTIVATE_TARGET'].strip().lower() == 'true'

  email_pattern = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
  if not email_pattern.match(from_email):
    raise SystemExit(f'Error: invalid source email: {from_email}')
  if not email_pattern.match(to_email):
    raise SystemExit(f'Error: invalid target email: {to_email}')
  if actor_email and not email_pattern.match(actor_email):
    raise SystemExit(f'Error: invalid actor email: {actor_email}')

  if from_email == to_email:
      raise SystemExit('Error: --from and --to must be different emails.')

  admins_before = User.query.filter_by(is_admin=True).order_by(User.created_at.asc(), User.id.asc()).all()

  from_user = User.query.filter_by(email=from_email).first()
  if from_user is None:
      raise SystemExit(f'Error: source user not found: {from_email}')

  to_user = User.query.filter_by(email=to_email).first()
  if to_user is None:
      raise SystemExit(f'Error: target user not found: {to_email}')

  actor_user = None
  if actor_email:
    actor_user = User.query.filter_by(email=actor_email).first()
    if actor_user is None:
      raise SystemExit(f'Error: actor user not found: {actor_email}')
    if not actor_user.is_admin:
      raise SystemExit(f'Error: actor user is not an admin: {actor_email}')
    if not actor_user.is_active:
      raise SystemExit(f'Error: actor user is inactive: {actor_email}')
    if not actor_user.is_approved:
      raise SystemExit(f'Error: actor user is not approved: {actor_email}')

  if not from_user.is_admin:
      raise SystemExit(f'Error: source user is not an admin: {from_email}')

  if not to_user.is_approved and not approve_target:
    raise SystemExit('Error: target user is not approved. Re-run with --approve-target to allow this change.')
  if not to_user.is_active and not activate_target:
    raise SystemExit('Error: target user is inactive. Re-run with --activate-target to allow this change.')

  admin_ids_after = {user.id for user in admins_before}
  admin_ids_after.discard(from_user.id)
  admin_ids_after.add(to_user.id)
  if not admin_ids_after:
    raise SystemExit('Error: this operation would leave zero admins.')

  users_by_id = {user.id: user for user in User.query.filter(User.id.in_(admin_ids_after)).all()}
  admins_after = [users_by_id[user_id] for user_id in sorted(users_by_id.keys())]

  print('Preflight summary:')
  print(f'  source: {from_email} (id={from_user.id})')
  print(f'  target: {to_email} (id={to_user.id})')
  print(f'  target approved now: {to_user.is_approved}')
  print(f'  target active now:   {to_user.is_active}')
  print(f'  actor email:         {actor_email or "(none)"}')
  print(f'  approve target flag: {approve_target}')
  print(f'  activate target flag:{activate_target}')
  print('  admins before:')
  for admin in admins_before:
    print(f'    - {admin.email} (id={admin.id})')
  print('  admins after:')
  for admin in admins_after:
    print(f'    - {admin.email} (id={admin.id})')

  if dry_run:
    print('Dry run only. No changes committed.')
    raise SystemExit(0)

  from_user.is_admin = False
  to_user.is_admin = True
  if approve_target:
    to_user.is_approved = True
  if activate_target:
    to_user.is_active = True

  audit_details = {
    'from_user_id': from_user.id,
    'from_email': from_email,
    'to_user_id': to_user.id,
    'to_email': to_email,
    'actor_user_id': actor_user.id if actor_user is not None else None,
    'actor_email': actor_email or None,
    'approved_target': approve_target,
    'activated_target': activate_target,
  }
  db.session.add(
    AuditLog(
        actor_user_id=actor_user.id if actor_user is not None else None,
      action='user.admin_reassigned_script',
      target_type='user',
      target_id=to_user.id,
      summary=f'Admin reassigned from {from_email} to {to_email} via script.',
      details=json.dumps(audit_details, sort_keys=True),
    )
  )

  db.session.commit()

  print('Admin reassignment complete:')
  print(f'  removed admin from: {from_email} (id={from_user.id})')
  print(f'  granted admin to:   {to_email} (id={to_user.id})')
PY
)

if [[ -n "${DATABASE_URL:-}" ]]; then
  FLASK_APP=app.main \
  FROM_EMAIL="$FROM_EMAIL" \
  TO_EMAIL="$TO_EMAIL" \
  ACTOR_EMAIL="$ACTOR_EMAIL" \
  DRY_RUN="$DRY_RUN" \
  APPROVE_TARGET="$APPROVE_TARGET" \
  ACTIVATE_TARGET="$ACTIVATE_TARGET" \
  python -c "$PYTHON_SNIPPET"
else
  FROM_EMAIL="$FROM_EMAIL" \
  TO_EMAIL="$TO_EMAIL" \
  ACTOR_EMAIL="$ACTOR_EMAIL" \
  DRY_RUN="$DRY_RUN" \
  APPROVE_TARGET="$APPROVE_TARGET" \
  ACTIVATE_TARGET="$ACTIVATE_TARGET" \
  docker-compose run --rm \
  -e FROM_EMAIL \
  -e TO_EMAIL \
  -e ACTOR_EMAIL \
  -e DRY_RUN \
  -e APPROVE_TARGET \
  -e ACTIVATE_TARGET \
  web python -c "$PYTHON_SNIPPET"
fi
