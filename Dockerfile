# ==============================================================================
# Bybit Strategy Tester - Multi-Stage Production Dockerfile
# ==============================================================================
# Build: docker build -t bybit-strategy-tester:latest .
# Run: docker run -p 8000:8000 --env-file .env bybit-strategy-tester:latest
# ==============================================================================

# Stage 1: Builder - Install dependencies and prepare wheels
FROM python:3.14-slim AS builder

# Set build arguments
ARG TARGETARCH=amd64

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Copy requirements first for better caching
COPY deployment/requirements-prod.txt /tmp/requirements-prod.txt
COPY backend/requirements.txt /tmp/requirements-backend.txt

# Install production dependencies
RUN pip install --no-cache-dir -r /tmp/requirements-prod.txt
RUN pip install --no-cache-dir -r /tmp/requirements-backend.txt

# ==============================================================================
# Stage 2: Runtime - Minimal production image
# ==============================================================================
FROM python:3.14-slim AS runtime

# Labels for container metadata
LABEL maintainer="Bybit Strategy Tester Team"
LABEL version="2.0.0"
LABEL description="Production container for Bybit Strategy Tester API"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/cache /app/data \
    && chown -R appuser:appgroup /app

# Copy application code
COPY --chown=appuser:appgroup . /app

# Remove unnecessary files for smaller image
RUN rm -rf \
    .git \
    .github \
    .venv \
    __pycache__ \
    *.pyc \
    .pytest_cache \
    .ruff_cache \
    .mypy_cache \
    tests \
    docs \
    *.md \
    Dockerfile* \
    docker-compose*.yml \
    .env* \
    .gitignore \
    .pre-commit-config.yaml

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command: run uvicorn
CMD ["uvicorn", "backend.api.app:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--loop", "uvloop", \
    "--http", "httptools", \
    "--access-log", \
    "--log-level", "info"]

# ==============================================================================
# Stage 3 (Optional): Development image with dev dependencies
# ==============================================================================
FROM runtime AS development

# Switch back to root to install dev dependencies
USER root

# Install development tools
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt || true

# Copy test files back
COPY --chown=appuser:appgroup tests /app/tests

# Switch back to non-root user
USER appuser

# Override command for development (with auto-reload)
CMD ["uvicorn", "backend.api.app:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--reload", \
    "--log-level", "debug"]
