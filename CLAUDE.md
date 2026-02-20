# Bybit Strategy Tester v2 — Claude Code Configuration

## Project Overview

AI-powered trading strategy backtesting platform for Bybit exchange.
Visual block-based strategy builder with multi-agent AI pipeline.

**Stack:** FastAPI · PostgreSQL · Redis · VectorBT · Numba · LangGraph
**AI agents:** DeepSeek · Qwen (Alibaba DashScope) · Perplexity
**Frontend:** Vanilla HTML/CSS/JS (no framework)
**Python:** 3.11+
**Entry point:** `python main.py server` → http://localhost:8000

## Environment (Windows 11)

- **Working directory:** `D:\bybit_strategy_tester_v2`
- **Shell:** Bash via Cygwin — **fork errors are common**, avoid relying on Bash
- **Workaround:** Use Read / Glob / Grep tools instead of shell commands
- **Git branches:** `main` (working), `fresh-main` (PR target base)

## Key Directory Structure

```
backend/
  api/
    app.py                    # FastAPI app factory
    lifespan.py               # startup/shutdown hooks
    routers/                  # API route handlers
  agents/
    unified_agent_interface.py  # single entry point for all AI agents
    agent_memory.py             # SQLite memory backend
    config_validator.py         # env config validation
  backtesting/
    engine.py                   # main backtest runner
    strategy_builder_adapter.py # translates frontend blocks → signals
    vectorbt_sltp.py            # VectorBT SL/TP integration
    numba_engine.py             # Numba-accelerated engine
    fast_optimizer.py           # grid/walk/bayes optimization
frontend/
  strategy-builder.html       # PRIMARY strategy UI (replaced strategies.html)
  js/pages/strategy_builder.js
  css/strategy_builder.css
  js/shared/                  # shared utilities (leverageManager, instrumentService)
tests/
  ai_agents/                  # AI agent behaviour tests
  backend/                    # unit tests
  integration/                # end-to-end tests
main.py                       # CLI entry point
```

## Critical Constants — NEVER CHANGE WITHOUT EXPLICIT APPROVAL

| Constant | Value | Reason |
|---|---|---|
| `commission_rate` | `0.0007` | TradingView parity — 10+ files depend on this |
| Engine | `FallbackEngineV4` | Gold standard; V2 kept for parity tests only, V3 deprecated |
| `DATA_START_DATE` | `2025-01-01` | Import from `backend/config/database_policy.py` — never hardcode |
| Timeframes | `["1","5","15","30","60","240","D","W","M"]` | Legacy mapping on load: 3→5, 120→60, 360→240, 720→D |
| `initial_capital` | `10000.0` (default) | User-configurable; referenced in engine, metrics, UI |

## High-Risk Variables (grep before any refactor)
- `commission_rate` — breaks TradingView parity if changed
- `strategy_params` — used in all strategies, optimizer, and UI
- `initial_capital` — engine, metrics, UI
- Port aliases in adapter — silent signal drops if broken

## Data Flow (preserve this)

```
DataService.load_ohlcv(symbol, timeframe, start, end)  → pd.DataFrame[OHLCV]
    ↓
Strategy.generate_signals(data)                         → pd.DataFrame[signal: 1/-1/0]
    ↓
BacktestEngine.run(data, signals, config)               → BacktestResults
    ↓ commission=0.0007, engine=FallbackEngineV4
MetricsCalculator.calculate(results)                    → Dict[166 metrics]
    ↓
FastAPI router                                          → JSON response + warnings[]
```


## Critical Domain Knowledge

### Port Alias Mapping
When a frontend port name doesn't match backend output key, the adapter applies:
```
"long"    ↔ "bullish"
"short"   ↔ "bearish"
"output"  ↔ "value"
"result"  ↔ "signal"
```
File: [backend/backtesting/strategy_builder_adapter.py](backend/backtesting/strategy_builder_adapter.py)

### Direction Mismatch
- Frontend CSS class `.direction-mismatch` = red dashed wire (stroke: #ef4444)
- Backend engine logs `[DIRECTION_MISMATCH]` when direction filter drops all signals
- API router returns `"warnings": [...]` in backtest response
- Frontend shows each warning as a notification

### MCP Status
MCP bridge is **disabled** — all AI agents run in direct API mode:
```
FORCE_DIRECT_AGENT_API=1
MCP_DISABLED=1
```

### Agent Memory
SQLite backend at `data/agent_memory.db` (configurable via `AGENT_MEMORY_BACKEND`).

### Divergence Block
`_execute_divergence()` returns **both** `"long"`/`"short"` (frontend port IDs)
and `"bullish"`/`"bearish"` (backward compat). The `"signal"` key = `long | short`.

## Common Commands

```bash
# Start server
python main.py server

# Run migrations
python main.py migrate

# Generate AI strategy
python main.py generate-strategy --prompt "RSI momentum for BTCUSDT"

# Run backtest (CLI stub — full via API)
python main.py backtest --strategy-id 1 --symbol BTCUSDT

# Health check
python main.py health --detailed

# Run tests (use pytest directly, not via main.py)
pytest tests/ai_agents/test_divergence_block_ai_agents.py -v
pytest tests/ -x -q
```

## Environment Variables (from .env.example)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL for pub/sub and cache |
| `DEEPSEEK_API_KEY` | DeepSeek AI key |
| `QWEN_API_KEY` | Alibaba DashScope key |
| `PERPLEXITY_API_KEY` | Perplexity AI key |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Optional, only for live private endpoints |
| `CORS_ALLOW_ALL` | `true` in dev only |
| `FORCE_DIRECT_AGENT_API` | Keep `1` (MCP disabled) |

Copy `.env.example` → `.env` and fill API keys before first run.

## Code Patterns to Follow

1. **No shell commands in tests** — mock subprocess calls; Bash unreliable on this machine
2. **Async everywhere** — FastAPI routes are `async def`; use `asyncio.run()` only at CLI level
3. **Type hints required** — mypy configured (`warn_return_any=false`, `ignore_missing_imports=true`)
4. **Logging** — use `structlog` / `structured_logging.py`, not bare `print()`
5. **Frontend** — no build step; pure ES modules, no npm/webpack

## Recent Major Changes (2026-02-19)

- `strategies.html` **removed** — all strategy functionality on `strategy-builder.html`
- Shared utilities moved to `frontend/js/shared/`
- 13 nav links updated across 10 HTML files
- Divergence block critical fix: now returns `long`/`short` keys alongside `bullish`/`bearish`
- Direction mismatch wire highlighting (frontend) + engine warning + API warnings field
- Port alias fallback added to Case 2 signal routing in adapter
- `main.py` Unicode fix for cp1251 Windows terminals
- 56 divergence tests passing (6 handler + 50 AI agent)
