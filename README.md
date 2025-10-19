# bybit_strategy_tester_v2
Тестовая система

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
