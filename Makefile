# ==============================================================================
# Bybit Strategy Tester v2 - Makefile
# ==============================================================================
# Quick commands for development, testing, and deployment

.PHONY: help install dev test lint format clean docker run

# Default target
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║           Bybit Strategy Tester v2 - Available Commands          ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  DEVELOPMENT                                                      ║"
	@echo "║    make install     - Install production dependencies            ║"
	@echo "║    make dev         - Install development dependencies           ║"
	@echo "║    make run         - Start the application locally              ║"
	@echo "║                                                                   ║"
	@echo "║  CODE QUALITY                                                     ║"
	@echo "║    make lint        - Run ruff linter                            ║"
	@echo "║    make format      - Format code with ruff                      ║"
	@echo "║    make check       - Run all pre-commit hooks                   ║"
	@echo "║    make type        - Run mypy type checker                      ║"
	@echo "║                                                                   ║"
	@echo "║  TESTING                                                          ║"
	@echo "║    make test        - Run all tests                              ║"
	@echo "║    make test-fast   - Run tests (skip slow)                      ║"
	@echo "║    make test-cov    - Run tests with coverage                    ║"
	@echo "║                                                                   ║"
	@echo "║  DOCKER                                                           ║"
	@echo "║    make docker      - Build Docker image                         ║"
	@echo "║    make docker-run  - Run in Docker container                    ║"
	@echo "║    make compose     - Start with docker-compose                  ║"
	@echo "║                                                                   ║"
	@echo "║  MAINTENANCE                                                      ║"
	@echo "║    make clean       - Remove cache and temp files                ║"
	@echo "║    make clean-all   - Deep clean (including node_modules)        ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# ==============================================================================
# DEVELOPMENT
# ==============================================================================

install:
	pip install --upgrade pip
	pip install -r deployment/requirements-prod.txt

dev: install
	pip install -r requirements-dev.txt
	pip install pre-commit
	pre-commit install

run:
	@if command -v powershell >/dev/null 2>&1 && [ -f start_all.ps1 ]; then \
		powershell -ExecutionPolicy Bypass -File start_all.ps1; \
	else \
		python main.py server; \
	fi

run-simple:
	uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload

# ==============================================================================
# CODE QUALITY
# ==============================================================================

lint:
	ruff check backend/ --fix

format:
	ruff format backend/

check:
	pre-commit run --all-files

type:
	mypy backend/ --ignore-missing-imports

security:
	bandit -r backend/ -c pyproject.toml

# ==============================================================================
# TESTING
# ==============================================================================

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -m "not slow"

test-cov:
	pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing

test-integration:
	pytest tests/ -v -m integration

test-e2e:
	pytest tests/ -v -m e2e

# ==============================================================================
# DOCKER
# ==============================================================================

docker:
	docker build -t bybit-strategy-tester:latest .

docker-dev:
	docker build -t bybit-strategy-tester:dev --target development .

docker-run:
	docker run -p 8000:8000 --env-file .env bybit-strategy-tester:latest

compose:
	docker-compose -f deployment/docker-compose.yml up -d

compose-prod:
	docker-compose -f deployment/docker-compose-prod.yml up -d

compose-down:
	docker-compose -f deployment/docker-compose.yml down

# ==============================================================================
# MAINTENANCE
# ==============================================================================

clean:
	@echo "Cleaning Python cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "Done!"

clean-all: clean
	@echo "Deep cleaning..."
	rm -rf node_modules/ 2>/dev/null || true
	rm -rf .venv/ .venv314/ .venv_tmp/ 2>/dev/null || true
	@echo "Done!"

# ==============================================================================
# DATABASE
# ==============================================================================

db-backup:
	python scripts/backup_database.py

db-migrate:
	alembic upgrade head

db-clean:
	python scripts/cleanup_db.py

# ==============================================================================
# DOCUMENTATION
# ==============================================================================

docs:
	@echo "Opening API documentation..."
	python -c "import webbrowser; webbrowser.open('http://localhost:8000/docs')"
