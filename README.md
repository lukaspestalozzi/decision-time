# decision-time

A self-hosted decision-making tool. Create options, organize them with tags, run tournament-style voting (Bracket,
Score, Multivoting, Condorcet), and get ranked results. Runs as a single Docker container with a web frontend and JSON
file persistence.

See [SPEC.md](SPEC.md) for the full specification.

## Architecture

- **Backend**: Python 3.12, FastAPI, Pydantic v2 for validation and serialization
- **Frontend**: Angular 19 with Angular Material, standalone components
- **Persistence**: JSON files on disk, one file per entity (options, tags, tournaments)
- **Deployment**: Single Docker container serving both API and static frontend

## Tournament Modes

| Mode          | Description                                                             |
|---------------|-------------------------------------------------------------------------|
| **Bracket**   | Single-elimination head-to-head matchups. Winner advances each round.   |
| **Score**     | Rate each option on a numeric scale. Highest average score wins.        |
| **Multivote** | Distribute a fixed budget of votes across options. Most votes wins.     |
| **Condorcet** | Pairwise round-robin comparison. Ties resolved with the Schulze method. |

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

### Makefile Targets

| Target          | Description                       |
|-----------------|-----------------------------------|
| `dev-backend`   | uvicorn with reload               |
| `dev-frontend`  | ng serve with proxy               |
| `dev`           | both in parallel                  |
| `test`          | all tests (backend + frontend)    |
| `test-backend`  | pytest only                       |
| `test-frontend` | jest only                         |
| `test-e2e`      | playwright (requires running app) |
| `lint`          | ruff + eslint                     |
| `typecheck`     | mypy                              |
| `ci`            | lint + typecheck + all tests      |
| `build`         | docker build                      |
| `run`           | docker run with volume mount      |
| `clean`         | remove build artifacts            |

## API Documentation

When the app is running, interactive API docs are available:

- **Swagger UI**: [http://localhost:8009/docs](http://localhost:8009/docs)
- **OpenAPI spec**: [http://localhost:8009/api/v1/openapi.json](http://localhost:8009/api/v1/openapi.json)

## Docker Deployment

```bash
docker build -t decision-time .
docker run -p 8009:8009 -v decision_time_data:/data decision-time
```

Or with docker-compose:

```bash
docker compose up
```

## Testing

| Suite    | Command              | Details                            |
|----------|----------------------|------------------------------------|
| Backend  | `make test-backend`  | pytest -- 188 tests                |
| Frontend | `make test-frontend` | Jest                               |
| E2E      | `make test-e2e`      | Playwright -- requires running app |
| Full CI  | `make ci`            | lint + typecheck + all tests       |

## Environment Variables

| Variable       | Default | Description                                 |
|----------------|---------|---------------------------------------------|
| `DATA_DIR`     | `/data` | Directory for JSON file storage             |
| `PORT`         | `8009`  | HTTP server port                            |
| `CORS_ORIGINS` | `*`     | Allowed CORS origins (comma-separated)      |
| `LOG_LEVEL`    | `info`  | Logging level (debug, info, warning, error) |

## Project Structure

```
decision-time/
  backend/          # FastAPI application (app/, tests/)
  frontend/         # Angular 19 application (src/)
  e2e/              # Playwright end-to-end tests
  Dockerfile        # Single-container build
  docker-compose.yml
  Makefile          # Development and CI commands
  SPEC.md           # Full project specification
```
