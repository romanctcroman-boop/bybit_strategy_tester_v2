# Migrations audit (2025-10-22)

This note summarizes the state of Alembic migrations and database setup after bringing up a local Postgres and applying migrations.

## Current state

- Single Alembic head: `20251022_consolidate_heads`
- Consolidated previous orphaned heads:
  - `0001_timestamptz` (tests shim for timestamp→timestamptz helpers)
  - `20251020_merge_heads` (previous merge of `2f4e6a7b8c9d` and `20251020_add_bybit_kline_audit`)
  - `20251021_add_backfill_runs` (added `backfill_runs` table)
- Key objects present in DB:
  - Table `bybit_kline_audit` with unique constraint `uix_symbol_open_time` (matches model `backend/models/bybit_kline_audit.py`).
  - Table `backfill_runs` with indexes on `(task_id)`, `(symbol)`, `(interval)`.

## How to reproduce locally

- Start Postgres and run migrations (PowerShell):

  ```powershell
  # default: port 5543, DB bybit, user postgres/postgres
  .\scripts\start_postgres_and_migrate.ps1 -Port 5543
  ```

- Start backend API (background):

  ```powershell
  .\scripts\start_uvicorn.ps1 start -AppModule 'backend.api.app:app' -BindHost '127.0.0.1' -Port 8000
  ```

- Frontend dev server:

  ```powershell
  cd frontend
  npm ci
  npm run dev
  ```

## Notes and recommendations

- The file `backend/migrations/versions/0001_convert_timestamps_to_timestamptz.py` is a tests compatibility shim. It can create an extra head if left unmerged; we've consolidated it via a merge revision. Options to reduce future merges:
  - Move the shim outside the `versions/` folder (e.g., under `backend/migrations/helpers/`) and adjust tests to import by dotted path; OR
  - Keep it under `versions/` but ensure subsequent real revisions continue from the consolidated head to avoid new branches.
- Consider adjusting `20251021_add_backfill_runs` to set `down_revision = '20251020_merge_heads'` for a cleaner historical chain. Not required functionally after the merge.
- Docker Compose warns about the obsolete `version` key; safe to remove for clarity.

## Next steps (optional)

- Add a lightweight migration that backfills `open_time_dt` in `bybit_kline_audit` from `open_time` (ms) where NULL:
  ```sql
  UPDATE bybit_kline_audit
  SET open_time_dt = to_timestamp(open_time / 1000.0) AT TIME ZONE 'UTC'
  WHERE open_time_dt IS NULL;
  ```
  This can be part of a reversible Alembic migration if needed.
- If you plan to ingest large volumes, add a composite index on `(symbol, open_time)` in addition to the unique constraint for range scans. The unique constraint implicitly creates a btree index; if you need different index type/order, add explicitly.
