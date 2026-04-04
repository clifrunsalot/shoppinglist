---
name: "Add Migration"
description: "Create a model-backed schema change with an Alembic migration for this Flask app"
argument-hint: "Describe the schema change, for example: add item notes field"
agent: "agent"
---

Use the workspace guidance in [../copilot-instructions.md](../copilot-instructions.md) and testing guidance in [../instructions/tests.instructions.md](../instructions/tests.instructions.md).

Implement the migration-related change described by the slash-command arguments and the current chat context.

Requirements:
- Treat this as one focused task: make the smallest complete model plus schema change needed.
- Keep shared database usage aligned with [../../app/db.py](../../app/db.py), [../../app/main.py](../../app/main.py), and [../../app/models.py](../../app/models.py).
- Use [../../migrations/versions](../../migrations/versions) as the durable schema history. Do not rely on [../../db/init/init.sql](../../db/init/init.sql) for existing environments.
- Preserve the current API contract used by [../../app/templates/index.html](../../app/templates/index.html) when changing item or store fields, unless the user explicitly asks to change that contract.
- When the change affects request parsing, serialization, ownership rules, or template output, update the related route logic and tests together.
- Prefer generating a real Alembic migration when the environment allows. If migration generation cannot be run here, create the migration file manually in the existing style and say so.
- Add or update focused pytest coverage for the behavior introduced by the schema change.

When needed:
- Update validation helpers, serializers, and template usage that depend on the new field.
- Keep migrations reversible and narrowly scoped to the requested schema change.
- Use commands from [../../README.md](../../README.md) when running migration or test steps.

Finish with a concise summary that states:
- what model, route, template, and migration changes were made
- what commands were run, or why they could not be run
- any follow-up needed for existing data or deployment