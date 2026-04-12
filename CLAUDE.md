# CLAUDE.md — Development Guidelines for decision-time

## Project Overview

decision-time is a self-hosted decision-making tool. See SPEC.md for full specification.

## Architecture

- Backend: Python 3.12+ / FastAPI / Pydantic v2
- Frontend: Angular 19 / Angular Material
- Persistence: JSON files on disk
- Layers: Router → Service → (Engine + Repository)

## Development Commands

- `make ci` — run all checks (lint + typecheck + tests)
- `make test-backend` — run backend tests only
- `make test-frontend` — run frontend tests only
- `make lint` — ruff + eslint
- `make typecheck` — mypy strict
- `make dev-backend` — uvicorn with reload (port 8009)
- `make dev-frontend` — ng serve with proxy (port 4200)

## Coding Rules

### General

- ALWAYS run `make ci` after making changes to verify nothing is broken
- Follow test-driven development: write tests BEFORE implementation
- Keep functions small and focused
- Follow the 'Zen of Python' design philosophy

### Git

- **NEVER run `git commit` or `git push`** — the user manages all git operations

### Python / Backend

- Type hints on ALL function signatures (mypy strict enforced)
- Use Pydantic v2 models for all data structures, not dataclasses or dicts
- Use absolute imports (`from app.schemas.option import Option`), never relative
- Use f-strings for string formatting
- Line length: 120 characters
- Follow architecture layers strictly:
  - **Routers**: HTTP concerns only, no business logic
  - **Services**: orchestration and validation
  - **Engines**: pure logic, no I/O, stateless
  - **Repositories**: file I/O only, no business logic
- Raise custom exceptions (`NotFoundError`, `ValidationError`, `InvalidStateError`, `ConflictError`), never return error codes
- All API endpoints under `/api/v1/`
- UUIDs: use uuid4, serialize as strings
- Datetimes: always UTC, ISO 8601 with Z suffix

### Angular / Frontend

- Use standalone components exclusively — no NgModules
- Use signals for reactive state (not RxJS Subjects for component state)
- Use new control flow syntax (`@if`, `@for`, `@switch`) — not `*ngIf`, `*ngFor`
- Use Angular Material components where available
- Organize by feature: `options/`, `tournaments/`, `shared/`
- Services for all API communication — components never call HttpClient directly
- Use environment files for API base URL

### Testing

- Backend tests use pytest. Test files named `test_*.py`
- Use pytest fixtures for shared setup, especially tmpdir for file repos
- API tests use httpx AsyncClient with FastAPI TestClient
- Frontend tests use Jest
- E2E tests use Playwright (in `e2e/` directory)
- Test names should describe behavior: `test_bracket_with_3_options_creates_bye()`

### Naming Conventions

- Python: snake_case for files and functions, PascalCase for classes
- TypeScript: kebab-case for files, PascalCase for classes/components
- Test files: `test_<module>.py` (Python), `<component>.spec.ts` (Angular)
