# decision-time

A self-hosted decision-making tool. Create options, organize them with tags, run tournament-style voting (Bracket, Score, Multivoting, Condorcet), and get ranked results. Runs as a single Docker container with a web frontend and JSON file persistence.

See [SPEC.md](SPEC.md) for the full specification.

## Prerequisites

- Python 3.12+
- Node 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Setup

### Backend

```bash
cd backend
uv sync --all-extras
```

### Frontend

```bash
cd frontend
npm install
```

## Development

```bash
make dev-backend     # uvicorn with reload (port 8009)
make dev-frontend    # ng serve with proxy (port 4200)
make dev             # both in parallel
```

## Makefile Targets

| Target           | Description                          |
|------------------|--------------------------------------|
| `dev-backend`    | uvicorn with reload                  |
| `dev-frontend`   | ng serve with proxy                  |
| `dev`            | both in parallel                     |
| `test`           | all tests (backend + frontend)       |
| `test-backend`   | pytest only                          |
| `test-frontend`  | jest only                            |
| `lint`           | ruff + eslint                        |
| `typecheck`      | mypy                                 |
| `ci`             | lint + typecheck + all tests         |
| `build`          | docker build                         |
| `run`            | docker run with volume mount         |
| `clean`          | remove build artifacts               |

## Docker

```bash
make build
make run
# App available at http://localhost:8009
```
