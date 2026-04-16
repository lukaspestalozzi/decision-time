.PHONY: dev-backend dev-frontend dev test test-backend test-frontend test-e2e lint typecheck ci build run clean

# Development
dev-backend:
	cd backend && DATA_DIR=./data uv run uvicorn app.main:app --reload --port 8010

dev-frontend:
	cd frontend && npx ng serve --proxy-config proxy.conf.json --port 8009

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest || test $$? -eq 5

test-frontend:
	cd frontend && npx ng test --watch=false

test-e2e:
	rm -rf backend/data-e2e
	cd e2e && npx playwright test ; status=$$? ; rm -rf ../backend/data-e2e ; exit $$status

# Code quality
lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npx ng lint

typecheck:
	cd backend && uv run mypy app

# CI
ci: lint typecheck test

# Docker
build:
	docker build -t decision-time .

run:
	docker run --rm -p 8009:8009 -v decision_time_data:/data decision-time

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/.angular
	rm -rf backend/*.egg-info
	rm -rf backend/data-e2e
