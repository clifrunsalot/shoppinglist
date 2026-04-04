---
name: "Testing Guidelines"
description: "Use when writing or updating pytest tests, Flask test fixtures, API assertions, authentication coverage, or regression tests in this shopping list app."
applyTo: "tests/**/*.py"
---

# Testing Guidelines

- Prefer extending existing fixtures in [../../tests/conftest.py](../../tests/conftest.py) before adding new setup patterns.
- Keep tests app-factory based: create the app with config overrides and use SQLite, not Docker Compose Postgres.
- Use the Flask test client for route coverage and assert both status codes and JSON or redirect behavior.
- For authenticated flows, create users through fixtures and log in through the real `/login` route unless a narrower setup is clearly better.
- Preserve user ownership expectations: items and stores are isolated per authenticated user, and cross-user access should usually assert `404` or empty results based on current behavior.
- When covering JSON routes, verify the exact error payloads and response shapes the frontend depends on, especially for `/api/items` and `/api/stores`.
- Prefer one focused success-path test plus the most important validation or regression case rather than broad scenario piles.
- If a production change affects auth, serialization, or store-item relationships, update or add tests in [../../tests/test_main.py](../../tests/test_main.py).