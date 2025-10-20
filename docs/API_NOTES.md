API Notes / Best practices

- Date/time: always use timezone-aware ISO8601 strings in UTC (e.g. 2025-10-20T12:34:56Z).
- Errors: return structured JSON: { error: { code: 'string_code', message: 'Human readable', details?: { ... } } }
- Pagination: use query params `limit` and `offset` and return `items` and optional `total`.
- Idempotency: endpoints that start long-running tasks (e.g., start backtest) should be idempotent or accept an idempotency key in headers.
- Types: frontend uses `frontend/src/types/api.d.ts` for shared types; keep it in sync with backend models.
