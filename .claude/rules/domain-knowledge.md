# Domain Knowledge — Bybit Strategy Tester v2

## Direction Mismatch

- Frontend CSS class `.direction-mismatch` = red dashed wire (stroke: #ef4444)
- Backend engine logs `[DIRECTION_MISMATCH]` warning when direction filter drops all signals
- API router returns `"warnings": [...]` in backtest response
- Frontend shows each warning as a notification banner
- **Trap:** `BacktestCreateRequest` default = `"long"`, `BacktestConfig` default = `"both"` — short signals silently dropped if direction not specified in API call

## MCP Status

MCP bridge is **disabled** — all AI agents run in direct API mode:
```
FORCE_DIRECT_AGENT_API=1
MCP_DISABLED=1
```

Agent memory SQLite backend at `data/agent_memory.db` (configurable via `AGENT_MEMORY_BACKEND`).

## Divergence Block

`_execute_divergence()` returns **both** `"long"`/`"short"` (frontend port IDs) and `"bullish"`/`"bearish"` (backward compat). The `"signal"` key = `long | short`.

## MetricsCalculator — single source of truth

All engines (Fallback, Numba, GPU, fast_optimizer) MUST use `MetricsCalculator.calculate_all()`.
Do NOT reimplement metric formulas elsewhere — sync issues caused bugs before.
Location: `backend/core/metrics_calculator.py` — 166 metrics.

## Engine Execution Invariants (TradingView parity)

- **Entry always on open of the NEXT bar after signal** — never on the signal bar itself
- **Commission formula:** `commission = trade_value × 0.0007` where `trade_value = initial_capital × position_size` — NOT `leveraged_value × 0.0007`
- **Commission on margin** (`commission_on_margin=True`): Bybit/TV style — applied before leverage multiplier
- `use_bar_magnifier=True` is a **stub** — intrabar SL/TP loop does not exist; SL/TP still checked at bar close only

## Middleware Pipeline Order (FIXED — do NOT reorder)

`backend/api/middleware_setup.py` — 10 middleware outer→inner:
RequestID → Timing → GZip(500b) → TrustedHost → HTTPS(prod) → CORS → RateLimit(120/min) → CSRF(POST/PUT/DELETE) → SecurityHeaders → ErrorHandler

## Optimization Filter Unit Mismatch

`passes_filters()` in `backend/optimization/filters.py`:
- `max_drawdown_limit` in **request** = fraction (0.0–1.0)
- `max_drawdown` in **result** = percentage (0–100)

## Data Storage

**SQLite databases:** `data.sqlite3` (main ORM), `bybit_klines_15m.db` (candles), `data/agent_memory.db` (agents)
**ORM relationships:** `Strategy 1→N Backtest 1→N Trade` · `Strategy 1→N Optimization`
**4-tier kline cache:** L1 in-process dict → L2 Redis (5min/1h TTL) → L3 SQLite → L4 Bybit REST (120 req/min)

## Agent Memory Pitfalls

- `agent_namespace = "shared"` — accessible to ALL agents; use agent name for isolation
- SQLite timestamp format: `"%Y-%m-%d %H:%M:%S"` (space separator, NOT 'T') — breaks queries if wrong
- `embedding = None` when ChromaDB/sentence-transformers unavailable — fallback to BM25-only

## Live Trading Pitfalls

- `paper_trading.py` does NOT send real orders — verify mode before deploy
- `position_size` units: engine/optimization = fraction (0.0–1.0); live trading = absolute quantity
- `GracefulShutdown`: SIGTERM → closes all open positions before exit
