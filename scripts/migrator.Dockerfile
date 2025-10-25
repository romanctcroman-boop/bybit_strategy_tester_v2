# Minimal prebuilt image for fast Alembic runs
# Usage: docker build -f scripts/migrator.Dockerfile --build-arg PYTHON_IMAGE=python:3.12-slim -t bybit-migrator:3.12-slim .

ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

# Install runtime deps and alembic toolchain.
# Keep image small: no cache, no dev headers.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir alembic sqlalchemy "psycopg[binary]"

# Default workdir will be mounted by the runner; no entrypoint necessary.
WORKDIR /app
