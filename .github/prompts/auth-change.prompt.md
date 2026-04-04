---
name: "Auth Change"
description: "Change login, logout, session, unauthorized response, or user-ownership behavior in this Flask app"
argument-hint: "Describe the auth change, for example: add remember-me test coverage or tighten next redirect handling"
agent: "agent"
---

Use the workspace guidance in [../copilot-instructions.md](../copilot-instructions.md) and testing guidance in [../instructions/tests.instructions.md](../instructions/tests.instructions.md).

Implement the authentication or authorization change described by the slash-command arguments and the current chat context.

Requirements:
- Treat this as one focused task: make the smallest complete auth-related change set.
- Preserve the app-factory structure in [../../app/main.py](../../app/main.py) and current shared model usage in [../../app/models.py](../../app/models.py).
- Keep HTML and JSON unauthorized behavior distinct: HTML routes redirect to `/login`, while JSON API routes return `401` with the established error payload unless the request explicitly changes that contract.
- Preserve current user ownership rules for items and stores unless the request is specifically about access policy.
- Be careful with redirect targets: keep next-target handling relative and safe.
- If the change touches login, logout, `create-user`, or ownership checks, update focused pytest coverage in [../../tests/test_main.py](../../tests/test_main.py).
- Avoid introducing new auth frameworks or broad architectural refactors unless explicitly requested.

When needed:
- Update login form handling in [../../app/templates/login.html](../../app/templates/login.html) or index behavior in [../../app/templates/index.html](../../app/templates/index.html).
- Keep CLI behavior, session cookie settings, and remember-me behavior consistent with the current Flask-Login setup unless the task calls for changing them.
- Use [../../README.md](../../README.md) for operational commands and deployment-related auth settings such as `SECRET_KEY` and `SESSION_COOKIE_SECURE`.

Finish with a concise summary that states:
- what auth behavior changed
- what tests were added or updated
- what command was run, or why verification could not be run