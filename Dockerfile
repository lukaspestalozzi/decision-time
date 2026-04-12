# Stage 1: Build frontend
FROM node:20-alpine AS build-frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx ng build --configuration=production

# Stage 2: Production
FROM python:3.12-slim AS production
WORKDIR /app

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install backend dependencies
COPY backend/pyproject.toml ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Copy backend code
COPY backend/app ./app

# Copy frontend build
COPY --from=build-frontend /app/frontend/dist/frontend/browser ./static

# Create data directory
RUN mkdir -p /data

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8009/api/v1/health')" || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
