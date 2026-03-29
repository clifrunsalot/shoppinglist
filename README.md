# Shopping List

This is a small Flask app for managing a grocery list with Postgres, Flask-SQLAlchemy, and Flask-Migrate. Local development runs through Docker Compose.

Quick start

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Build and run with Docker Compose:

```bash
docker-compose up --build
```

3. Open http://localhost:8000 to see the items.

Notes
- The Postgres seed SQL lives in `db/init/init.sql` and runs only the first time the `db_data` volume is created.
- Changes to `db/init/init.sql` do not update an existing database volume. To reinitialize from seed data, run `docker-compose down -v` and then `docker-compose up --build`.
- The app expects DB env vars from `.env`.

Testing

The repository includes a small pytest suite for the Flask API and price parsing helpers. The tests create a temporary SQLite database through the app factory, so they do not require Docker Compose or a running Postgres container.

Install dependencies and run the unit tests with:

```bash
pip install -r requirements.txt
python -m pytest
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
- `/api/items` create, list, update, and delete flows
- validation for missing item names
- `/api/stores` duplicate-name protection
- clearing `store_id` references when a store is deleted

Database migrations

Run migrations from the `web` container:

```bash
# generate a migration after model changes
docker-compose run --rm web flask db migrate -m "message"

# apply migrations to the database
docker-compose run --rm web flask db upgrade
```
