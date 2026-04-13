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

Cloud hosting

The app is now production-ready enough for a managed platform such as Render or Railway:

1. Provision a managed Postgres database.
2. Set `DATABASE_URL`, `SECRET_KEY`, and `SESSION_COOKIE_SECURE=true` in the platform environment.
3. Deploy the container from this repository.
4. Run migrations with `flask db upgrade`.
5. Create the first authorized user with `flask create-user you@example.com`.
6. Visit the service URL over HTTPS and sign in.

The Docker image now serves the app with Gunicorn, which is appropriate for cloud deployment.

Database migrations

Run migrations from the `web` container:

```bash
# generate a migration after model changes
docker-compose run --rm web flask db migrate -m "message"

# apply migrations to the database
docker-compose run --rm web flask db upgrade
```
