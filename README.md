# Shopping List

This is a small Flask app for managing a grocery list with Postgres, Flask-SQLAlchemy, Flask-Migrate, and Flask-Login. Local development runs through Docker Compose.

Quick start

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Build and run with Docker Compose:

```bash
docker-compose up --build
```

3. Create the first administrator from the web container:

```bash
docker-compose run --rm web flask create-user you@example.com --admin
```

4. Open http://localhost:8000 and sign in.

Notes
- The Postgres seed SQL lives in `db/init/init.sql` and runs only the first time the `db_data` volume is created.
- Changes to `db/init/init.sql` do not update an existing database volume. To reinitialize from seed data, run `docker-compose down -v` and then `docker-compose up --build`.
- The app expects DB env vars from `.env`.
- The app requires a real `SECRET_KEY` in every environment. Set `SESSION_COOKIE_SECURE=true` when running behind HTTPS.
- If your cloud provider gives you a single `DATABASE_URL`, the app prefers that over the individual `DB_*` variables.

Testing

The repository includes a small pytest suite for the Flask API and price parsing helpers. The tests create a temporary SQLite database through the app factory, so they do not require Docker Compose or a running Postgres container.

Install dependencies and run the unit tests with:

```bash
pip install -r requirements.txt
python -m pytest
```

To install the browser runtime for UI regressions, run:

```bash
python -m playwright install chromium
```

To run the Playwright regression for the item store-selection persistence bug, run:

```bash
python -m pytest tests/test_ui_store_persistence.py
```

To generate coverage output, run:

```bash
python -m pytest --cov=app --cov-report=term --cov-report=xml --cov-report=html
```

That command writes:
- terminal coverage output
- `coverage.xml` for CI tooling
- `htmlcov/index.html` for a browsable HTML report

The current tests cover:
- `parse_price()` normalization and rounding behavior
- login and unauthorized access handling
- `/api/items` create, list, update, and delete flows
- validation for missing item names
- per-user data isolation for items and stores
- `/api/stores` duplicate-name protection
- clearing `store_id` references when a store is deleted
- browser-level persistence of store selection when switching between items

Authentication

- The login page now includes a self-signup request form.
- Pending users cannot sign in until an administrator approves the request.
- Administrators can approve users from the in-app admin dashboard and generate a temporary password.
- The first administrator can be created with `flask create-user EMAIL --admin`.
- The login page is served at `/login`.
- HTML routes redirect unauthenticated users to the login page.
- JSON API routes return `401` with `{"error": "authentication required"}` when the session is missing.
- Items and stores are user-owned, so each authenticated user sees only their own data.

Administration and defaults

- Administrators can open `/admin` to approve users, deactivate/reactivate accounts, generate temporary passwords, edit the default grocery list, and review the audit log.
- The default grocery list is stored as editable templates in the database, not as live user items.
- New users receive a copied personal grocery list and default stores when their account is approved or created by the CLI.
- Users can edit their copied items and stores freely after approval.
- Users can choose their own theme from the main grocery list UI. Administrators set only the default theme for new accounts.
- Any signed-in user can select an item in the shopping view and choose **Add to default list**.
  The app reports existing defaults by name, ignoring case, punctuation, and word order.
  Close spelling matches are offered for review: choose an existing default, cancel, or explicitly add a distinct item.
  Shared words allow broader spelling suggestions, such as **ice brick** versus **ice block**;
  these still require your choice and are not automatically treated as duplicates.
  This is spelling matching, not synonym detection. Choosing an existing default renames
  and links your selected item while retaining its other details. If that default is already
  in your household list, confirmation is required to remove the selected duplicate;
  the existing item's details are kept unchanged. Other households are not modified.
- Use **Settings > View Default Items** or **Add Item > From Defaults** to browse the
  shared catalog. The catalog refreshes each time it opens, including additions from other users.
- New contributions copy the saved name, quantity, unit, category, and associated default store
  (when available), including the item's photo, but not price or checked state. As with admin-created defaults,
  they are distributed to active, approved accounts and recorded in the audit log.
- Default photos appear in the default catalog and are inherited when creating or importing
  items from defaults. Existing personal photos are not overwritten on import. Removing or
  replacing the original item's photo does not remove the saved default photo.
  Adding an existing default again can fill its missing photo, but never replaces an existing default photo.
- Photos are local files under `app/static/uploads/items`; database backups preserve their URLs,
  not image contents. Back up and restore that directory alongside the database.
- Tap an item's photo icon to select an image from your device's photo library or files.
  To change an existing image, tap it and choose **Replace**. The picker does not force
  camera capture; available library/camera options depend on the device and browser.
  Supported images are JPG, PNG, and WebP, up to 5 MB.

Cloud hosting

The app is now production-ready enough for a managed platform such as Render or Railway:

1. Provision a managed Postgres database.
2. Set `DATABASE_URL`, `SECRET_KEY`, and `SESSION_COOKIE_SECURE=true` in the platform environment.
3. Deploy the container from this repository.
4. Run migrations with `flask db upgrade`.
5. Create the first authorized user with `flask create-user you@example.com`.
6. Visit the service URL over HTTPS and sign in.

The Docker image now serves the app with Gunicorn, which is appropriate for cloud deployment.

Restore runbook

- For a lightweight owner-operated backup and restore process, see docs/small-app-restore-runbook.md.
- Helper scripts for default-template backup and restore are in scripts/backup-defaults.sh and scripts/restore-defaults.sh.

Database migrations

Run migrations from the `web` container:

```bash
# generate a migration after model changes
docker-compose run --rm web flask db migrate -m "message"

# apply migrations to the database
docker-compose run --rm web flask db upgrade
```
