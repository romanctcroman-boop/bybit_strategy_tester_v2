# bybit_strategy_tester_v2
Тестовая система

## Quick start — Live WebSocket

Stream real-time messages via the Redis → /api/v1/live relay.

1) Start API locally (PowerShell):

```powershell
D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

2) Connect a WebSocket client to:

```
ws://127.0.0.1:8000/api/v1/live?channel=bybit:ticks
```

3) Publish a test message into Redis (PowerShell one-liner):

```powershell
$env:REDIS_URL = "redis://127.0.0.1:6379/0"; D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -c "import asyncio,os,json; from redis.asyncio import Redis; async def m(): r=Redis.from_url(os.environ.get('REDIS_URL','redis://127.0.0.1:6379/0'), encoding='utf-8', decode_responses=True); await r.publish('bybit:ticks', json.dumps({'v':1,'type':'test','payload':42})); await r.close();
asyncio.run(m())"
```

Docs: see Live WebSocket section in `docs/api.md`:
- ./docs/api.md#live-market-stream-websocket

To stream real Bybit data in the background (optional):

```powershell
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:BYBIT_WS_ENABLED = "1"
$env:BYBIT_WS_SYMBOLS = "BTCUSDT,ETHUSDT"
$env:BYBIT_WS_INTERVALS = "1,5"
D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

## Database migrations (Alembic)

This project uses Alembic for schema migrations. A minimal Alembic scaffold lives in `backend/migrations` and the migration to convert timestamp columns to timestamptz is in `backend/migrations/versions/1a2b3c4d5e6f_convert_timestamps_to_timestamptz.py`.

Local usage

- Set the `DATABASE_URL` environment variable to point at your Postgres instance. Example (PowerShell):

```powershell
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/postgres'
```

- Apply migrations:

```powershell
D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -m alembic upgrade head
```

- If you don't have Postgres locally, you can run a temporary container and point `DATABASE_URL` to it. See the CI job for an example of starting Postgres in CI.

Diagnostics

- A small diagnostic script is available at `scripts/check_db_connect.py` to validate `DATABASE_URL` and attempt a `psycopg2` connection.

CI / Integration test

- We provide a GitHub Actions workflow `integration-migrations.yml` (manual trigger) that starts a Postgres service, installs dependencies, runs `alembic upgrade head`, and executes the integration migration tests. Use that in CI to verify migrations on a clean runner.
# bybit_strategy_tester_v2
Тестовая система

## Market Data: Working Set and MTF endpoints

Two new endpoints expose a standardized candle working set and multi-timeframe (MTF) views.

- GET `/api/v1/marketdata/bybit/klines/working`
	- Params:
		- `symbol` (string, required) e.g. `BTCUSDT`
		- `interval` (string, default `15`) One of: `1,5,15,30,60,240,D,W`
		- `load_limit` (int, default `1000`, max `1000`) Initial load size if cache is empty
	- Behavior:
		- On first access per (symbol, interval) key, loads up to `load_limit` candles, keeps last 500 in RAM, returns working set.
		- Subsequent calls return the in-memory working set.
	- Response (JSON):
		- Array of candles: `{ time: number (seconds, UTC), open, high, low, close, volume? }[]`

- GET `/api/v1/marketdata/bybit/mtf`
	- Params:
		- `symbol` (string, required)
		- `intervals` (string, default `1,15,60`) Comma-separated list; supports minute values and `D`,`W`
		- `base` (string, optional) Base timeframe to align/resample from; defaults to smallest interval
		- `aligned` (int, default `1`) If `1`, returns higher TFs resampled from `base`; if `0`, returns raw working sets per requested interval
		- `load_limit` (int, default `1000`, max `1000`)
	- Responses (JSON):
		- `{ symbol: string, intervals: string[], data: Record<interval, Candle[]> }`
		- Candle: `{ time: number (seconds, UTC), open, high, low, close, volume? }`
	- Alignment rules:
		- Minute-based: buckets align to UTC minutes; e.g., 3m windows start at times divisible by 180 (seconds)
		- Daily (`D`): bucket starts at 00:00:00 UTC
		- Weekly (`W`): bucket starts at ISO-week Monday 00:00:00 UTC

### Examples

Working set (15m):

```http
GET /api/v1/marketdata/bybit/klines/working?symbol=BTCUSDT&interval=15
```

Response (truncated):

```json
[
	{ "time": 1729479900, "open": 64430.5, "high": 64480.0, "low": 64310.0, "close": 64420.0, "volume": 153.21 },
	{ "time": 1729480800, "open": 64420.0, "high": 64510.0, "low": 64400.0, "close": 64500.0, "volume": 98.77 }
]
```

MTF aligned from 1m to 1m and 3m:

```http
GET /api/v1/marketdata/bybit/mtf?symbol=BTCUSDT&intervals=1,3&aligned=1&base=1
```

Response (shape):

```json
{
	"symbol": "BTCUSDT",
	"intervals": ["1", "3"],
	"data": {
		"1": [ { "time": 1729480800, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10 } ],
		"3": [ { "time": 1729480800, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10 } ]
	}
}
```

Notes:
- All times are seconds (UTC) suitable for Lightweight Charts.
- Duplicates by time are deduplicated (latest wins) and data is returned ascending by time per interval.

## Historical Backfill

Fetch historical candles from Bybit and persist into `bybit_kline_audit` with idempotent upsert.

### CLI

```powershell
# optional: use file-backed sqlite to persist across processes
$env:DATABASE_URL = 'sqlite:///D:/bybit_strategy_tester_v2/data.sqlite3'

D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe scripts/backfill_cli.py BTCUSDT --interval 1 --days 7 --page 1000
```

### Celery (eager mode)

```powershell
$env:DATABASE_URL = 'sqlite:///D:/bybit_strategy_tester_v2/data.sqlite3'
$env:CELERY_EAGER = '1'

D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe -c "from backend.tasks.backfill_tasks import backfill_symbol_task; print(backfill_symbol_task.delay('BTCUSDT','1',lookback_minutes=60).get())"
```

### Admin API

- POST `/api/v1/admin/backfill`
	- Body (JSON):
		- `symbol`: string, required
		- `interval`: string (default `1`)
		- `lookback_minutes`: int (optional)
		- `start_at_iso` / `end_at_iso`: ISO datetimes (optional)
		- `page_limit`: int (default 1000)
		- `max_pages`: int (default 500)
		- `mode`: `sync` | `async` (default `sync`)
	- Response (sync): `{ mode, symbol, interval, upserts, pages, elapsed_sec, rows_per_sec }`
	- Response (async): `{ mode, task_id }`

Optional allowlists via env:

```powershell
$env:ADMIN_BACKFILL_ALLOWED_SYMBOLS = 'BTCUSDT,ETHUSDT'
$env:ADMIN_BACKFILL_ALLOWED_INTERVALS = '1,5,15,60,240,D,W'
```

Admin auth (HTTP Basic):

- По умолчанию логин/пароль: `admin` / `admin`
- Переопределить через переменные окружения:

```powershell
$env:ADMIN_USER = 'myadmin'
$env:ADMIN_PASS = 's3cr3t'
```

## Celery workers, queues, retries

Background tasks (backfill, backtests, optimizations) are executed by Celery workers. By default, the project runs in "eager" mode for tests/dev unless you configure a broker and start workers.

Configuration (via environment variables — see `.env.example`):
- CELERY_BROKER_URL: e.g. `redis://127.0.0.1:6379/1` or RabbitMQ `amqp://guest:guest@127.0.0.1:5672//`
- CELERY_RESULT_BACKEND: e.g. `redis://127.0.0.1:6379/2`
- CELERY_TASK_DEFAULT_QUEUE: default queue name (default `default`)
- CELERY_PREFETCH_MULTIPLIER: flow control per worker (default `4`)
- CELERY_ACKS_LATE: require ack after execution for at-least-once delivery (default `1`)
- CELERY_TASK_DEFAULT_RETRY_DELAY, CELERY_TASK_MAX_RETRIES: global retry policy defaults

Start a worker (PowerShell):

```powershell
$env:CELERY_BROKER_URL = 'redis://127.0.0.1:6379/1'
$env:CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/2'
Remove-Item Env:CELERY_EAGER -ErrorAction SilentlyContinue  # ensure not eager

# In repo root
D:/bybit_strategy_tester_v2/.venv/Scripts/celery.exe -A backend.celery_app:celery_app worker -l info -Q default
```

Optional: run a separate queue (e.g., `optimizations`) with different prefetch:

```powershell
$env:CELERY_PREFETCH_MULTIPLIER = '1'
D:/bybit_strategy_tester_v2/.venv/Scripts/celery.exe -A backend.celery_app:celery_app worker -l info -Q optimizations -n optim-1@%COMPUTERNAME%
```

Notes
- Retries: tasks can call `self.retry(...)`; global defaults are set from env. Prefer idempotent tasks with `acks_late=1` and persistence in DB.
- Redis reconnect/WS backoff: see `docs/api.md` (Live market stream) for reconnection tunables affecting background WS producer.

Default queue mapping for optimizations (can be overridden via env or request payload):
- grid_search → `optimizations.grid`
- walk_forward → `optimizations.walk`
- bayesian → `optimizations.bayes`

Override via env (see `.env.example`):
- `CELERY_QUEUE_GRID`, `CELERY_QUEUE_WALK`, `CELERY_QUEUE_BAYES`

## Configuration (pydantic-settings)

This backend prefers `pydantic-settings` for typed, validated configuration. A compatibility fallback keeps old imports working.

Sources:
- Environment variables and optional `.env` in repo root.
- `backend/settings.py` defines models for Database, Redis, WebSocket (Bybit), and Celery.
- `backend/config.py` exposes a compatibility `CONFIG` used by routers and app lifespan.

Key variables (common):
- DATABASE_URL — SQLAlchemy URL (Postgres or SQLite)
- REDIS_URL — Redis connection (or REDIS_HOST/REDIS_PORT/REDIS_DB)
- BYBIT_WS_ENABLED — `1` to enable background Bybit WS manager
- BYBIT_WS_SYMBOLS — e.g. `BTCUSDT,ETHUSDT`
- BYBIT_WS_INTERVALS — e.g. `1,5,15`
- WS_RECONNECT_DELAY_SEC / WS_RECONNECT_DELAY_MAX_SEC

Celery:
- CELERY_BROKER_URL / CELERY_RESULT_BACKEND
- CELERY_TASK_DEFAULT_QUEUE, CELERY_PREFETCH_MULTIPLIER, CELERY_ACKS_LATE
- CELERY_TASK_DEFAULT_RETRY_DELAY, CELERY_TASK_MAX_RETRIES
- CELERY_QUEUE_GRID, CELERY_QUEUE_WALK, CELERY_QUEUE_BAYES (override default mapping)

Notes
- All timestamps in the API are ISO 8601 UTC. See the Timezones section in `docs/api.md`.
