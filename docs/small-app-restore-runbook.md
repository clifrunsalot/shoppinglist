# Small App Restore Runbook

Purpose
- Restore service quickly for a small owner-operated app (about 10 users).
- Keep process simple, repeatable, and safe.

Scope
- Uses Docker Compose with the existing db and web services.
- Covers two scenarios:
  1. Full database restore
  2. Defaults-only restore (default stores, categories, and items)

Environment Setup For Commands
1. Run from the repository root.
2. Load app variables from .env:
   set -a
   source .env
   set +a
3. These commands assume compose service names db and web from docker-compose.yml.

Decide Restore Type
1. Use full restore when user data is broadly damaged or missing.
2. Use defaults-only restore when only admin-managed default templates are wrong.

Pre-Flight Checklist
1. Confirm you have a recent backup file.
2. Put the app in a maintenance window (announce brief downtime).
3. Take a safety backup of current state before modifying anything.

Safety Backup Commands
1. Make backup folders if needed:
   mkdir -p backups/full backups/defaults
2. Full DB snapshot (safety):
   docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > backups/full/pre-restore-$(date +%Y%m%d-%H%M%S).dump
3. Defaults snapshot (safety):
   docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --data-only --inserts --column-inserts --table default_store_templates --table default_category_templates --table default_item_templates > backups/defaults/pre-restore-defaults-$(date +%Y%m%d-%H%M%S).sql

Routine Backup Commands
- Run these nightly or before risky admin edits.

Script shortcuts
1. Backup defaults quickly:
   ./scripts/backup-defaults.sh
2. Restore defaults from a backup file:
   ./scripts/restore-defaults.sh backups/defaults/default-templates-YYYYMMDD-HHMMSS.sql
3. Non-interactive restore:
   ./scripts/restore-defaults.sh backups/defaults/default-templates-YYYYMMDD-HHMMSS.sql --yes

1. Full DB backup:
   docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > backups/full/appdb-$(date +%Y%m%d-%H%M%S).dump
2. Defaults-only export:
   docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --data-only --inserts --column-inserts --table default_store_templates --table default_category_templates --table default_item_templates > backups/defaults/default-templates-$(date +%Y%m%d-%H%M%S).sql

Full Database Restore
- Use this when broad app data recovery is needed.

1. Stop app writes:
   docker-compose stop web
2. Restore dump file (replace with your filename):
   cat backups/full/appdb-YYYYMMDD-HHMMSS.dump | docker-compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --no-privileges
3. Start app:
   docker-compose start web
4. Apply migrations (safe to run after restore):
   docker-compose run --rm web flask db upgrade

Defaults-Only Restore
- Use this when only default templates are corrupted.

1. Stop app writes:
   docker-compose stop web
2. Clear defaults tables in FK-safe way:
   docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
3. Import defaults snapshot (replace filename):
   cat backups/defaults/default-templates-YYYYMMDD-HHMMSS.sql | docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
4. Start app:
   docker-compose start web
5. Apply migrations (safe to run):
   docker-compose run --rm web flask db upgrade

Post-Restore Verification
1. Sign in with an admin account.
2. Open admin page and verify defaults load:
   - Default Stores
   - Default Categories
   - Default Grocery List
3. Test create, update, and delete for one default item.
4. Test create and delete for one default store.
5. Test normal user flow:
   - Sign in as regular user
   - Load list
   - Add and update one item
6. Check logs for errors:
   docker-compose logs --tail=200 web

Rollback Plan
1. If verification fails, stop web:
   docker-compose stop web
2. Restore the pre-restore safety full backup:
   cat backups/full/pre-restore-YYYYMMDD-HHMMSS.dump | docker-compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --no-privileges
3. Start web and re-run verification:
   docker-compose start web

Operational Cadence (Small App)
1. Nightly full backup.
2. Weekly defaults-only export.
3. Quarterly restore drill in non-production or local clone.

Cloud-Hosted Variant (When Using DATABASE_URL)
- If production uses a managed Postgres URL, run equivalent commands from a secure operator environment that has DATABASE_URL set.

1. Full backup:
   pg_dump "$DATABASE_URL" -Fc > backups/full/appdb-$(date +%Y%m%d-%H%M%S).dump
2. Defaults-only export:
   pg_dump "$DATABASE_URL" --data-only --inserts --column-inserts --table default_store_templates --table default_category_templates --table default_item_templates > backups/defaults/default-templates-$(date +%Y%m%d-%H%M%S).sql
3. Full restore:
   pg_restore "$DATABASE_URL" --clean --if-exists --no-owner --no-privileges backups/full/appdb-YYYYMMDD-HHMMSS.dump
4. Defaults-only restore:
   psql "$DATABASE_URL" -c "TRUNCATE TABLE default_item_templates, default_store_templates, default_category_templates RESTART IDENTITY CASCADE;"
   psql "$DATABASE_URL" < backups/defaults/default-templates-YYYYMMDD-HHMMSS.sql

Notes
- Seed SQL in db/init/init.sql only runs when the db_data volume is first created.
- .env.example defaults are DB_USER=devuser and DB_NAME=appdb, but this runbook intentionally reads real values from .env each time.
- Forcing re-seed from init.sql requires volume recreation:
  docker-compose down -v
  docker-compose up --build
- Use that only when you intentionally want a fresh database, not targeted recovery.
