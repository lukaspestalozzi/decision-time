---
name: ci
description: Run the full CI pipeline (lint + typecheck + tests) and report results
user_invocable: true
---

# CI Check

Run the full CI pipeline and report results.

1. Change to the project root: `/home/lu/gitrepos/decision-time`
2. Run `make ci` which executes:
   - `make lint` — ruff check + ruff format check (backend) + ng lint (frontend)
   - `make typecheck` — mypy strict (backend)
   - `make test` — pytest (backend) + jest (frontend)
3. Report the results clearly:
   - If all pass: confirm green build
   - If any fail: show the failing step and the error output
   - If the failure is probably caused by recent changes, provide a plan to fix it and ask the user for guidance.
   - If it is not caused by recent changes, ask the user what to do.
