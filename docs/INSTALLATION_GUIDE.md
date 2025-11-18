# INSTALLATION_GUIDE

This guide describes how to run the backend stack (API, Celery worker/beat, Redis, Postgres) with Docker Compose and how to develop locally.

## Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine (Linux)
- Docker Compose v2
- Git
- Optional for local dev without Docker: Python 3.13 and Node.js (for frontend)
  - Note: The codebase uses PEP 695 generics (enabled by Ruff UP046), which requires Python 3.12+; we target 3.13.

## 1) Configure environment

1. Copy `.env.example` to `.env` at the repo root.
2. For Docker Compose, uncomment the section "Docker Compose defaults" at the bottom of `.env` (service-based URLs):
   - `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/bybit`
   - `REDIS_URL=redis://redis:6379/0`
   - `CELERY_BROKER_URL=redis://redis:6379/0`
   - `CELERY_RESULT_BACKEND=redis://redis:6379/1`
   - `BYBIT_WS_ENABLED=0` (enable to auto-start Bybit ingest worker on API startup)

## 2) Start the stack (Docker Compose)

From the repository root:

```powershell
# Windows PowerShell
docker compose up -d --build
```

Services started:
- `postgres` (port 5432)
- `redis` (port 6379)
- `api` (FastAPI on port 8000)
- `celery-worker` (default, optimizations.* queues)
- `celery-beat` (optional scheduler; no periodic tasks by default)

The API service runs migrations on startup:
- `alembic -c alembic.ini upgrade head` then starts `uvicorn`.

Health checks:
- API: `http://localhost:8000/healthz`, `readyz` and `/metrics` for Prometheus text format
- Postgres: `pg_isready`
- Redis: `redis-cli ping`

To view logs:
```powershell
docker compose logs -f api
# or
docker compose logs -f celery-worker
```

To stop:
```powershell
docker compose down
```

To remove volumes (including DB data):
```powershell
docker compose down -v
```

## 3) Running database migrations manually

Normally API applies migrations on start. To run manually inside the API container:

```powershell
docker compose exec api alembic upgrade head
```

## 4) Local development (without Docker)

- Backend
  ```powershell
  # Python 3.13 venv
  py -3.13 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install -r backend/requirements.txt
  pip install -r requirements-dev.txt
  pip install -r backend/requirements-archival.txt  # optional (pyarrow on 3.13, polars on 3.14)

  # Required for multipart/form-data endpoints (e.g., market data upload)
  pip install python-multipart

  # Set DATABASE_URL and REDIS_URL to your local services
  $env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/bybit"
  $env:REDIS_URL = "redis://127.0.0.1:6379/0"

  alembic -c alembic.ini upgrade head
  uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
  ```

- Frontend (dev server)
  ```powershell
  cd frontend
  npm install
  npm run dev
  # Open http://localhost:5173
  ```

### Developer hygiene: pre-commit hooks (Ruff + Black)

To keep the codebase consistently formatted and linted before every commit, enable the local hooks:

```powershell
# Install dev tools (already included above)
pip install -r requirements-dev.txt

# Install git hooks
pre-commit install

# Optional: run on all files once (first pass may modify files)
pre-commit run --all-files
```

Notes (Windows):
- Hooks use local system binaries (ruff, black), so no Git submodule cloning is needed.
- If you see cache write warnings from Ruff on Windows, they are harmless; the hooks will still pass.
- The hooks are staged by rule groups: E/F/I, UP (pyupgrade), B (bugbear), SIM (simplify). Some rules are intentionally ignored in pre-commit to avoid churn on long strings or import positioning in tests/scripts.
- UP specifics: UP046 (PEP 695 generics) and UP035 (prefer builtins over typing.*/PEP 585) are enforced. Target Python 3.13.

### Quick OpenAPI sanity check (PEP 695 generics)

We use PEP 695 generics (enabled by UP046). You can sanity-check FastAPI/Pydantic schema generation locally:

```powershell
python scripts/check_openapi.py
```

If you prefer a one-liner, PowerShell quoting can get tricky. Use a here-string to avoid quote mangling:

```powershell
$code = @'
from backend.api.app import app
d = app.openapi()
print("OPENAPI_OK", bool(d and "components" in d and "schemas" in d["components"]))
'@
python -c $code
```

If the one-liner still misbehaves in your shell profile, stick to the helper script above.

### File uploads (market data)

- Endpoint: `POST /api/v1/marketdata/upload`
- Requires dependency `python-multipart` (see install step above).
- Form fields:
  - `file` (required): CSV/JSONL or any file (stored as-is)
  - `symbol` (required): e.g., `BTCUSDT`
  - `interval` (required): e.g., `1,3,5,15,60,240,D,W`
- Server stores files under `UPLOAD_DIR` (env; defaults to `./uploads/<uuid>/filename`).
- The endpoint currently stores files only; parsing/ingestion can be triggered later via admin archive/restore tools.

## 5) Celery tasks (queues)

- The worker is configured via environment variables (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).
- Default queues used by optimization endpoints:
  - `optimizations.grid`
  - `optimizations.walk`
  - `optimizations.bayes`

You can target a queue explicitly from the UI/API payload or rely on defaults.

## 6) WebSocket ingest and live relay

- Set `BYBIT_WS_ENABLED=1` to run background Bybit ingest on API startup.
- WebSocket relay endpoints:
  - `ws://localhost:8000/api/v1/live`
  - `ws://localhost:8000/ws/live`
- Redis channels (defaults): `bybit:ticks`, `bybit:klines`.

## 7) Troubleshooting

- API not starting / 500 at startup:
  - Check `DATABASE_URL` and DB connectivity: `docker compose logs api postgres`.
- Alembic fails with "duplicate key value violates unique constraint pg_type_typname_nsp_index" on alembic_version:
  This usually means a stale `alembic_version` table/type exists from a previous run. Either reset the DB volume (recommended in dev) or drop the objects manually:
  - Reset volume (destroys data):
    ```powershell
    docker compose down -v
    docker compose up -d --build
    ```
  - Or drop inside the Postgres container and let Alembic recreate:
    ```powershell
    docker compose exec -it postgres bash
    psql -U postgres -d bybit -c "DROP TABLE IF EXISTS alembic_version CASCADE;"
    exit
    ```
  - Run migrations manually as in section (3).
- Celery not consuming:
  - Verify Redis is healthy and broker URLs are correct.
  - Check worker logs: `docker compose logs -f celery-worker`.
- WebSocket not streaming:
  - Ensure Redis is reachable and `BYBIT_WS_ENABLED=1` if using background ingest.
  - Use `/api/v1/live` with appropriate filters to relay messages from Redis.

## 8) Security notes

- `.env` may contain secrets; do not commit it.
- For production, set strong passwords and restrict CORS, and consider running behind a reverse proxy.

## 9) Environment variables and startup order

Common variables (see `.env.example` for full list):

- Database/Redis
  - `DATABASE_URL` — SQLAlchemy URL to Postgres
  - `REDIS_URL` — Redis URL used by WS relay and Celery
- Celery
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — enable distributed tasks
  - `CELERY_EAGER=1` — run tasks in-process (useful for tests)
  - Optional queues: `CELERY_QUEUE_GRID`, `CELERY_QUEUE_WALK`, `CELERY_QUEUE_BAYES`
- Bybit WS ingest
  - `BYBIT_WS_ENABLED=0|1` — start background WS worker on API startup
  - `BYBIT_WS_SYMBOLS=BTCUSDT,ETHUSDT` — comma-separated symbols
  - `BYBIT_WS_INTERVALS=1,5,15` — intervals to subscribe for klines
- CORS
  - `CORS_ORIGINS=http://localhost:5173`

Startup order (compose handles this automatically):

1. Postgres and Redis (wait for health)
2. API (runs Alembic migrations on start)
3. Celery worker/beat (optional)

Reconnect strategies (summary):

- WS ingest: exponential backoff with cap, resubscribe on reconnect, responds to ping/pong
- Redis: live relay endpoints degrade gracefully (return JSON error) if Redis is unavailable
- Celery: tasks have conservative retry policies; you can tune via CELERY_* envs
