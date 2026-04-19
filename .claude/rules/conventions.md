# Conventions — Bybit Strategy Tester v2

## Naming

- Strategy type IDs: snake_case enum (`sma_crossover`, `bollinger_bands`, `dca`)
- Strategy Builder block types: lowercase (`rsi`, `macd`, `supertrend`, `strategy`, `divergence`)
- Test files: `test_<module_name>.py` in mirrored directory structure under `tests/`
- Router files: plural nouns (`backtests.py`, `strategies.py`, `optimizations.py`)

## Parameter Conventions

- All `strategy_params` are `dict[str, Any]` passed through to strategy class
- Indicator periods: always int, clamped [1, 500] in adapter
- Risk params (SL/TP/commissions): always **decimal** (0.07% = 0.0007), not percent
- Exception — DCA: `dca_grid_size_percent` and `dca_tp*_percent` are in **percent** (1.0 = 1%)
- Frontend commission UI: shown in **percent** (0.07) → backend converts to decimal (0.0007)

## Code Patterns

1. **No shell commands in tests** — mock subprocess calls; Bash unreliable on this machine (Cygwin fork errors)
2. **Async everywhere** — FastAPI routes are `async def`; use `asyncio.run()` only at CLI level
3. **Async SQLite** — use `asyncio.to_thread()` for blocking SQLite calls inside async routes
4. **Type hints required** — mypy configured (`warn_return_any=false`, `ignore_missing_imports=true`)
5. **Logging** — use `structlog` / `structured_logging.py`, not bare `print()`
6. **Frontend** — no build step; pure ES modules, no npm/webpack; test by reloading browser
7. **ORM only** — no raw string SQL queries (SQL injection risk)
8. **No subprocess with user input** — command injection risk

## Environment Variables (from .env.example)

| Variable                             | Purpose                                   |
| ------------------------------------ | ----------------------------------------- |
| `DATABASE_URL`                       | PostgreSQL connection string              |
| `REDIS_URL`                          | Redis URL for pub/sub and cache           |
| `DEEPSEEK_API_KEY`                   | DeepSeek AI key                           |
| `QWEN_API_KEY`                       | Alibaba DashScope key                     |
| `PERPLEXITY_API_KEY`                 | Perplexity AI key                         |
| `ANTHROPIC_API_KEY`                  | Claude API key (4th agent)                |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Optional, only for live private endpoints |
| `CORS_ALLOW_ALL`                     | `true` in dev only                        |
| `FORCE_DIRECT_AGENT_API`             | Keep `1` (MCP disabled)                   |

Copy `.env.example` → `.env` and fill API keys before first run.

## Deprecated Items (do NOT use in new code)

| Item                            | Location                            | Replacement                                             |
| ------------------------------- | ----------------------------------- | ------------------------------------------------------- |
| `fast_optimizer.py`             | `backend/backtesting/`              | Use `backend/optimization/optuna_optimizer.py` (Optuna) |
| `RSIStrategy` (built-in)        | `backend/backtesting/strategies/`   | Use universal RSI block in Strategy Builder             |
| `BacktestConfig.force_fallback` | `backend/backtesting/models.py`     | Use `engine_type="fallback"` instead                    |
| `StrategyType.ADVANCED`         | `backend/backtesting/models.py`     | Not implemented — placeholder enum value                |
| `FallbackEngineV2`              | `backend/backtesting/engines/`      | Use FallbackEngineV4 (gold standard)                    |
| `FallbackEngineV3`              | `backend/backtesting/engines/`      | Use FallbackEngineV4                                    |
| `GPUEngineV2`                   | `backend/backtesting/engines/`      | Use NumbaEngineV2 for optimization speed                |

## Auxiliary Modules Status

| Module | Status |
|--------|--------|
| `backend/celery_app.py` + `backend/tasks/` | Active — async tasks; `CELERY_EAGER=1` for tests |
| `backend/reports/` | Active — HTML/PDF/Email (ReportLab + SMTP) |
| `backend/social/` | PoC — copy trading in-memory, not production |
| `backend/research/` | Research stubs — XAI, federated, blockchain, ABM — not in main flow |
| `backend/experimental/l2_lob/` | Experimental — L2 WebSocket + CGAN |
| `backend/benchmarking/` | Active — latency + load testing + regression detection |
| `backend/unified_api/` | Interface layer — `SimulatedExecutor` works, `LiveExecutor` stub |
