# Backend image for API and Celery services
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy project
COPY . /app

# Install Python deps
RUN python -m pip install --upgrade pip \
    && pip install -r backend/requirements.txt \
    && pip install -r requirements-dev.txt \
    && pip install -r backend/requirements-archival.txt \
    && pip install alembic

EXPOSE 8000

# Default command is defined in docker-compose for each service
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
