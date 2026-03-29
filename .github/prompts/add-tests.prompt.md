---
name: "Add Tests"
description: "Add or extend pytest coverage for a route, model, or workflow in this Flask app"
argument-hint: "Target area to test, for example: api items, Item model, or grocery UI workflow"
agent: "agent"
---

Use the workspace guidance in [../copilot-instructions.md](../copilot-instructions.md).

Add or extend automated tests for the target described by the slash-command arguments and the current chat context.

Requirements:
- Treat this as a single task: produce the smallest useful test-focused change set for the requested target.
- Prefer `pytest` with Flask app fixtures and the Flask test client.
- If the repository has no test harness yet, scaffold only the minimum needed test setup for the requested coverage.
- Keep changes aligned with the existing app factory in [../../app/main.py](../../app/main.py), shared database objects in [../../app/db.py](../../app/db.py), and model patterns in [../../app/models.py](../../app/models.py).
- For API coverage, preserve the current `/api/items` response shape used by the frontend in [../../app/templates/index.html](../../app/templates/index.html).
- Cover the main success path plus the most important validation or regression case for the requested target.
- Avoid broad refactors, unrelated production changes, or claiming test coverage that was not actually added and run.

When needed:
- Add test dependencies and minimal configuration.
- Create focused fixtures for app, database, and client setup.
- Choose the narrowest realistic test command and run it if the environment allows.

Finish with a concise summary that states:
- what tests were added
- what command was run, or why tests could not be run
- any remaining coverage gap or setup follow-up