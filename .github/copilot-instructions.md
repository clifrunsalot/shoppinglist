<!-- GitHub Copilot / AI agent instructions for this repo -->
# Project Guidelines

## Architecture

- This is a small Flask app backed by Postgres via Flask-SQLAlchemy and Flask-Migrate.
- Keep application setup, configuration, and route registration inside `create_app()` in [../app/main.py](../app/main.py).
- Import shared database objects from [../app/db.py](../app/db.py); models should subclass `db.Model` in [../app/models.py](../app/models.py).
- The UI is a server-rendered Jinja template in [../app/templates/index.html](../app/templates/index.html) with Alpine.js state and Tailwind loaded from CDNs. Preserve that lightweight structure unless the task requires a broader refactor.
- Treat [../migrations/versions](../migrations/versions) as the durable schema history. [../db/init/init.sql](../db/init/init.sql) is only for first-time database bootstrapping.

## Build And Run

- Use the Docker Compose workflow in [../README.md](../README.md) for normal local development.
- The main app entry is `FLASK_APP=app.main`; if you run Flask commands outside Docker, export `FLASK_APP=app.main` and the expected `DB_*` variables first.
- Run schema changes from the `web` container with `docker-compose run --rm web flask db migrate -m "message"` and `docker-compose run --rm web flask db upgrade`.
- There is no test suite in the repository today, so do not claim test coverage that was not actually added and run.

## Conventions

- Prefer extending the existing `app/` package over adding new top-level modules.
- Keep database access consistent: import `db` from [../app/db.py](../app/db.py) instead of creating new SQLAlchemy instances.
- Preserve the current API shape from [../app/main.py](../app/main.py); the frontend in [../app/templates/index.html](../app/templates/index.html) depends on the `/api/items` JSON fields matching the `serialize()` helper.
- Follow the existing style of simple function-based routes and minimal indirection unless the requested change clearly needs more structure.

## Gotchas

- Changes to [../db/init/init.sql](../db/init/init.sql) do not affect an existing Postgres volume; the seed scripts run only when the `db_data` volume is created for the first time.
- Compose sets database host and port values for the app container. Keep `.env` aligned with [../docker-compose.yml](../docker-compose.yml) when changing connection settings.
