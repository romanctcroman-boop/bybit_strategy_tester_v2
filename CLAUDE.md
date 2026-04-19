# Bybit Strategy Tester v2 — Claude Code Configuration

## TL;DR

- Purpose: fast, reproducible backtesting for Bybit-compatible strategies with a block-based Strategy Builder and AI helpers.
- Key invariant: Commission = **0.0007** (0.07%) — do not change without explicit approval.
- Quick start: `python main.py server` → http://localhost:8000

---

## 1. Overview

AI-powered trading strategy backtesting platform for Bybit exchange. Visual block-based strategy builder with multi-agent AI pipeline.

**Stack:** FastAPI · SQLite (local dev) / PostgreSQL (prod) · Redis · VectorBT · Numba · LangGraph
**AI agents:** DeepSeek · Qwen · Perplexity · Claude — direct API mode (MCP disabled)
**Frontend:** Vanilla HTML/CSS/ES modules (no build step, no npm/webpack)
**Python:** 3.11+ (3.14 recommended on this machine — use `py -3.14`)

---

## 2. Environment (Windows 11)

- **Working directory:** `D:\bybit_strategy_tester_v2`
- **Shell:** Bash via Cygwin — **fork errors are common**, avoid relying on Bash
- **Workaround:** Use Read / Glob / Grep tools instead of shell commands
- **Git branches:** `main` (working), `fresh-main` (PR target base)

---

## 3. Architecture

### Core data flow (preserve this)

```
DataService.load_ohlcv(symbol, timeframe, start, end)  → pd.DataFrame[OHLCV]
    ↓
Strategy.generate_signals(data)                         → SignalResult(entries, exits, ...)
    ↓  (or StrategyBuilderAdapter: graph → BaseStrategy)
BacktestEngine.run(data, signals, config)               → BacktestResult
    ↓  commission=0.0007, engine=FallbackEngineV4
MetricsCalculator.calculate_all(results)                → Dict[166 metrics]
    ↓
FastAPI router                                          → JSON response + warnings[]
```

### Key modules

| Module | Path | Responsibility |
|--------|------|----------------|
| `BacktestConfig` | `backend/backtesting/models.py` | All backtest parameters (single Pydantic model) |
| `BacktestEngine` | `backend/backtesting/engine.py` | FallbackEngineV4 — gold standard |
| `StrategyBuilderAdapter` | `backend/backtesting/strategy_builder/adapter.py` | Graph → BaseStrategy (1399 lines) |
| `indicator_handlers` | `backend/backtesting/indicators/` | 40+ handlers + INDICATOR_DISPATCH |
| `MetricsCalculator` | `backend/core/metrics_calculator.py` | Single source of truth for 166 metrics |
| `DataService` | `backend/services/data_service.py` | OHLCV loading |
| Strategies | `backend/backtesting/strategies/` | SMA, RSI, MACD, BB, Grid, DCA |
| Optimization | `backend/optimization/` | Optuna (TPE/CMA-ES), Ray, grid |

### API entry points

| Endpoint | Router | Action |
|----------|--------|--------|
| `POST /api/backtests/` | `routers/backtests.py` | Run backtest |
| `POST /api/strategy-builder/run` | `routers/strategy_builder.py` | Run builder strategy |
| `POST /api/optimizations/` | `routers/optimizations.py` | Start optimization |
| `GET /api/marketdata/ohlcv` | `routers/marketdata.py` | Load OHLCV |
| `POST /api/ai/generate-strategy` | `routers/ai_strategy_generator.py` | AI strategy generation |

### Engine selection

| `engine_type` | Engine | Use case |
|---------------|--------|----------|
| `"auto"`, `"single"`, `"fallback"`, `"v4"` | **FallbackEngineV4** | Default — gold standard |
| `"optimization"`, `"numba"` | NumbaEngineV2 | Optimization loops (20–40× faster) |
| `"dca"`, `"grid"`, `"dca_grid"` | DCAEngine | DCA / Grid / Martingale |

> When `dca_enabled=True`, DCAEngine is **always** used. VectorBT only inside optimization pipeline.
> **Details:** `backend/backtesting/CLAUDE.md` (graph format, SignalResult, BacktestConfig, port aliases)
> **API traps:** `backend/api/CLAUDE.md` (direction default, warning codes, cross-cutting params)

---

## 4. Directory Structure

```
d:/bybit_strategy_tester_v2/
├── main.py                    # CLI: server/migrate/health/audit/generate-strategy
├── backend/
│   ├── api/app.py             # FastAPI factory (mounts all routers)
│   ├── api/routers/           # backtests.py, strategy_builder.py, optimizations.py, agents.py
│   ├── agents/                # AI pipeline: unified_agent_interface.py, trading_strategy_graph.py
│   ├── backtesting/           # CORE — engine.py, models.py, strategies/, engines/
│   │   ├── strategy_builder/  #   adapter.py (1399L), block_executor, graph_parser, signal_router
│   │   └── indicators/        #   trend.py, oscillators.py, volatility.py, volume.py, other.py
│   ├── config/database_policy.py  # DATA_START_DATE, retention constants
│   ├── core/metrics_calculator.py # 166 metrics — single source of truth
│   ├── optimization/          # optuna_optimizer.py, builder_optimizer.py, scoring.py
│   ├── services/              # data_service.py, live_trading/, risk_management/, adapters/
│   └── trading/               # order_executor.py, position_manager.py
├── frontend/
│   ├── strategy-builder.html  # PRIMARY UI
│   └── js/pages/strategy_builder.js  # Builder logic (~7154 lines)
├── tests/                     # 214 files — см. tests/CLAUDE.md
└── data/                      # data.sqlite3, bybit_klines_15m.db, agent_memory.db
```

---

## 5. Critical Constants — NEVER CHANGE WITHOUT EXPLICIT APPROVAL

| Constant | Value | Location |
|----------|-------|----------|
| `COMMISSION_TV` | **0.0007** (0.07%) | `backend/config/constants.py` → `BacktestConfig.commission_value` |
| Engine | **FallbackEngineV4** | `backend/backtesting/engine.py` |
| `DATA_START_DATE` | **2025-01-01** | `backend/config/database_policy.py` — never hardcode |
| `DEFAULT_CAPITAL` | **10000.0** | `backend/config/constants.py` |
| Timeframes | `["1","5","15","30","60","240","D","W","M"]` | Legacy mapping: 3→5, 120→60, 360→240, 720→D |
| Max backtest | **730 days** | `BacktestConfig.validate_dates()` — raises ValueError |

> **Additional context in `.claude/rules/`:** domain-knowledge · workflow · conventions · session-infrastructure · subsystems · backtesting · api · agents · frontend · optimization
