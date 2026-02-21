# Bybit Strategy Tester v2 — Claude Code Configuration

## TL;DR

- Purpose: fast, reproducible backtesting for Bybit-compatible strategies with a block-based Strategy Builder and AI helpers.
- Key invariant: Commission = 0.0007 (0.07%) — do not change without explicit approval.
- Quick start (PowerShell): run `python main.py server` from repository root, then open http://localhost:8000.

## Quick navigation

-   1. Overview
-   2. Environment
-   3. Architecture (+ Graph Format, SignalResult, Engine Selection, Direction Defaults, Warning Codes, market_type)
-   4. Directory Structure
-   5. Critical Constants (+ 730-day limit)
-   6. Strategy Parameters
-   7. Risk & Money Management (+ Key Optimization Metrics)
-   8. Domain Knowledge
-   9. How to Work with Claude Code
-   10. Conventions
-   11. Environment Variables
-   12. Deprecated Items
-   13. Test Infrastructure
-   14. Recent Major Changes

## 1. Overview

AI-powered trading strategy backtesting platform for Bybit exchange. Visual block-based strategy builder with multi-agent AI pipeline.

**Stack:** FastAPI · PostgreSQL · Redis · VectorBT · Numba · LangGraph
**AI agents:** DeepSeek · Qwen (Alibaba DashScope) · Perplexity — direct API mode (MCP disabled)
**Frontend:** Vanilla HTML/CSS/ES modules (no build step, no npm/webpack)
**Python:** 3.11+
**Entry point:** `python main.py server` → http://localhost:8000

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

| Module                   | Path                                              | Responsibility                                  |
| ------------------------ | ------------------------------------------------- | ----------------------------------------------- |
| `BacktestConfig`         | `backend/backtesting/models.py`                   | All backtest parameters (single Pydantic model) |
| `BacktestEngine`         | `backend/backtesting/engine.py`                   | FallbackEngineV4 — gold standard engine         |
| `StrategyBuilderAdapter` | `backend/backtesting/strategy_builder_adapter.py` | Graph → BaseStrategy                            |
| `MetricsCalculator`      | `backend/core/metrics_calculator.py`              | Single source of truth for 166 metrics          |
| `DataService`            | `backend/services/data_service.py`                | OHLCV loading                                   |
| `UnifiedAgentInterface`  | `backend/agents/unified_agent_interface.py`       | All AI agent calls                              |
| `database_policy`        | `backend/config/database_policy.py`               | DATA_START_DATE, retention constants            |
| Strategies (built-in)    | `backend/backtesting/strategies.py`               | SMA, RSI, MACD, BB, Grid, DCA                   |
| Indicators               | `backend/core/indicators/`                        | 30+ technical indicators                        |
| Optimization             | `backend/optimization/`                           | Optuna (TPE/CMA-ES), Ray, grid                  |

### API entry points

| Endpoint                         | Router                             | Action                           |
| -------------------------------- | ---------------------------------- | -------------------------------- |
| `POST /api/backtests/`           | `routers/backtests.py`             | Run backtest (built-in strategy) |
| `POST /api/strategy-builder/run` | `routers/strategy_builder.py`      | Run builder strategy             |
| `POST /api/optimizations/`       | `routers/optimizations.py`         | Start optimization               |
| `GET /api/marketdata/ohlcv`      | `routers/marketdata.py`            | Load OHLCV                       |
| `POST /api/ai/generate-strategy` | `routers/ai_strategy_generator.py` | AI strategy generation           |

### Strategy Builder graph format

The adapter (`StrategyBuilderAdapter`) accepts a `strategy_graph: dict` with this shape:

```jsonc
{
    "name": "My RSI Strategy", // optional, default "Builder Strategy"
    "description": "...", // optional
    "interval": "15", // main chart timeframe (resolves "Chart" in blocks)
    "blocks": [
        {
            "id": "block_1",
            "type": "rsi", // indicator / condition / filter / exit block type
            "params": {
                "period": 14,
                "oversold": 30,
                "overbought": 70,
                "timeframe": "Chart", // resolved to "interval" above
            },
            "isMain": false,
        },
        {
            "id": "strategy_node",
            "type": "strategy", // the main collector node
            "params": {},
            "isMain": true, // exactly ONE block must be isMain
        },
    ],
    "connections": [
        {
            "from": "block_1",
            "fromPort": "long", // output port of source block
            "to": "strategy_node",
            "toPort": "longEntry", // input port of target block
        },
    ],
    // optional shortcut — auto-merged into blocks[] with isMain=True:
    "main_strategy": { "id": "strategy_node", "isMain": true },
}
```

**Block types:** `rsi`, `macd`, `stochastic`, `stoch_rsi`, `bollinger`, `ema`, `sma`, `wma`, `dema`, `tema`, `hull_ma`, `supertrend`, `ichimoku`, `atr`, `adx`, `cci`, `cmf`, `mfi`, `roc`, `williams_r`, `rvi`, `cmo`, `qqe`, `obv`, `pvt`, `ad_line`, `vwap`, `donchian`, `keltner`, `parabolic_sar`, `aroon`, `atrp`, `stddev`, `pivot_points`, `divergence`, `highest_lowest_bar`, `two_mas`, `channel`, `momentum`, `price_action`, `strategy`, `condition`, `filter`, `exit`.

**Strategy node input ports:** `longEntry`, `shortEntry`, `longExit`, `shortExit`.

### SignalResult contract

`generate_signals()` returns a `SignalResult` dataclass (defined in `backend/backtesting/strategies.py`):

```python
@dataclass
class SignalResult:
    entries: pd.Series               # bool — long entry signals
    exits: pd.Series                 # bool — long exit signals
    short_entries: pd.Series | None  # bool — short entry signals
    short_exits: pd.Series | None    # bool — short exit signals
    entry_sizes: pd.Series | None    # float — per-entry position size (DCA Volume Scale)
    short_entry_sizes: pd.Series | None
    extra_data: dict | None          # additional data (ATR series, etc.) passed to engine
```

All series must have the same index as the input OHLCV DataFrame. The engine iterates bar-by-bar using these boolean masks.

### Engine selection

| `engine_type` value                                         | Engine class         | Use case                                         |
| ----------------------------------------------------------- | -------------------- | ------------------------------------------------ |
| `"auto"`, `"single"`, `"fallback"`, `"fallback_v4"`, `"v4"` | **FallbackEngineV4** | Default for all single backtests — gold standard |
| `"optimization"`, `"numba"`                                 | NumbaEngineV2        | Optimization loops (20–40× faster, 100% parity)  |
| `"dca"`, `"grid"`, `"dca_grid"`                             | DCAEngine            | DCA / Grid / Martingale strategies               |
| `"gpu"`                                                     | GPUEngineV2          | CUDA-accelerated (deprecated, use Numba)         |
| `"fallback_v3"`                                             | FallbackEngineV3     | Deprecated — backward compat only                |
| `"fallback_v2"`                                             | FallbackEngineV2     | Deprecated — backward compat only                |

> When `dca_enabled=True` in config, DCAEngine is **always** used regardless of `engine_type`.
> VectorBT is used **only** inside the optimization pipeline, never for standalone backtests.

### `direction` default — API vs Engine ⚠️

| Model                         | Default  | File                                      |
| ----------------------------- | -------- | ----------------------------------------- |
| `BacktestConfig` (engine)     | `"both"` | `backend/backtesting/models.py`           |
| `BacktestCreateRequest` (API) | `"long"` | `backend/backtesting/models.py:1269`      |
| Strategy Builder API          | `"both"` | `backend/api/routers/strategy_builder.py` |

**Trap:** If you call `POST /api/backtests/` without specifying `direction`, it defaults to `"long"` — short signals will be silently dropped. The Strategy Builder API defaults to `"both"`.

### Warning codes in API response

The `warnings[]` field in backtest responses may contain:

| Tag                         | Meaning                                                                                      |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| `[DIRECTION_MISMATCH]`      | Direction filter dropped all signals (e.g., `direction="long"` but only short entries exist) |
| `[NO_TRADES]`               | Strategy generated signals but no trades were executed (SL/TP/filters eliminated all)        |
| `[INVALID_OHLC]`            | Bars with invalid OHLC data were removed before backtest                                     |
| `[UNIVERSAL_BAR_MAGNIFIER]` | Bar magnifier initialization failed; falling back to standard mode                           |

### `market_type`: spot vs linear

| Value                | Data source       | Purpose                                                        |
| -------------------- | ----------------- | -------------------------------------------------------------- |
| `"spot"`             | Bybit spot market | Matches TradingView candles exactly — use for **parity tests** |
| `"linear"` (default) | Perpetual futures | For live trading and real strategy development                 |

Prices may differ slightly between spot and linear due to funding rate influence. Use `spot` when validating against TradingView screenshots/results.

---

## 4. Directory Structure

```
d:/bybit_strategy_tester_v2/
│
├── main.py                          # CLI: server / migrate / generate-strategy / backtest / health / audit
├── pyproject.toml                   # mypy + ruff config
├── pytest.ini                       # pytest settings
├── alembic.ini                      # Alembic migrations
├── requirements-dev.txt / requirements-ml.txt
├── .env / .env.example / .env.production
│
├── backend/
│   ├── api/
│   │   ├── app.py                   # FastAPI app factory, mounts all routers
│   │   ├── lifespan.py              # startup/shutdown (DB, Redis, warmup)
│   │   ├── middleware_setup.py      # CORS, rate-limit, Prometheus, CSRF
│   │   ├── schemas.py               # Shared Pydantic schemas
│   │   ├── deepseek_client.py       # HTTP client DeepSeek (direct API)
│   │   ├── perplexity_client.py     # HTTP client Perplexity
│   │   ├── orchestrator.py          # MCP/agent coordinator (disabled)
│   │   ├── routers/                 # 55+ FastAPI route handlers
│   │   │   ├── backtests.py         # POST/GET /api/backtests/ — MAIN backtest router
│   │   │   ├── strategies.py        # Strategy CRUD
│   │   │   ├── strategy_builder.py  # POST /api/strategy-builder/run
│   │   │   ├── optimizations.py     # Parameter optimization
│   │   │   ├── marketdata.py        # OHLCV, symbols, timeframes
│   │   │   ├── agents.py            # AI agents (DeepSeek, Qwen, Perplexity)
│   │   │   └── ai_strategy_generator.py
│   │   └── mcp/tools/               # MCP tools (disabled in prod)
│   │
│   ├── agents/
│   │   ├── unified_agent_interface.py  # SINGLE entry point for all AI agents
│   │   ├── agent_memory.py             # SQLite agent memory (data/agent_memory.db)
│   │   ├── config_validator.py         # Env config validation
│   │   ├── langgraph_orchestrator.py   # LangGraph agent pipeline
│   │   ├── trading_strategy_graph.py   # Strategy generation graph
│   │   └── structured_logging.py       # structlog wrapper
│   │
│   ├── backtesting/                 # CORE backtesting
│   │   ├── engine.py                # BacktestEngine — FallbackEngineV4 (gold standard)
│   │   ├── engine_selector.py       # Engine selection: auto / fallback / numba / gpu
│   │   ├── models.py                # BacktestConfig, BacktestResult, PerformanceMetrics
│   │   ├── strategies.py            # Built-in: SMA, RSI, MACD, Bollinger, Grid, DCA
│   │   ├── strategy_builder_adapter.py  # Builder graph → BaseStrategy (key adapter)
│   │   ├── numba_engine.py          # JIT engine (Numba)
│   │   ├── vectorbt_sltp.py         # VectorBT SL/TP (for optimization only)
│   │   ├── fast_optimizer.py        # [DEPRECATED] RSI-only Numba optimizer
│   │   ├── optimizer.py             # Main optimizer (grid/walk/bayes)
│   │   ├── walk_forward.py          # Walk-forward analysis
│   │   ├── monte_carlo.py           # Monte Carlo simulation
│   │   ├── position_sizing.py       # Position sizing
│   │   ├── service.py               # BacktestService (service layer)
│   │   ├── mtf/                     # Multi-timeframe module
│   │   └── universal_engine/        # Extended engine (28 sub-modules, experimental)
│   │
│   ├── config/
│   │   └── database_policy.py       # DATA_START_DATE=2025-01-01, RETENTION_YEARS=2
│   │
│   ├── core/
│   │   ├── config.py                # App settings (Pydantic Settings)
│   │   ├── metrics_calculator.py    # MetricsCalculator — single source of 166 metrics
│   │   ├── metrics.py               # Prometheus metrics
│   │   └── indicators/              # Technical indicators (RSI, MACD, BB, ATR, ADX, …)
│   │
│   ├── database/
│   │   ├── session.py               # SQLAlchemy async session
│   │   ├── models/                  # ORM models: strategy, backtest, trade, optimization
│   │   └── repository/              # BaseRepository, KlineRepository
│   │
│   ├── optimization/
│   │   ├── optuna_optimizer.py      # Bayesian (TPE/CMA-ES) via Optuna
│   │   ├── ray_optimizer.py         # Ray-distributed optimization
│   │   ├── builder_optimizer.py     # Strategy Builder parameter optimization
│   │   └── scoring.py               # Scoring functions (Sharpe, SQN, Calmar, …)
│   │
│   ├── services/
│   │   ├── data_service.py          # DataService.load_ohlcv() — OHLCV loading
│   │   ├── kline_db_service.py      # Candle storage (PostgreSQL)
│   │   ├── strategies/              # Service-level strategies: momentum, breakout, dca, grid
│   │   ├── risk_management/         # RiskEngine, PositionSizing, StopLossManager
│   │   ├── live_trading/            # Live trading: Bybit WS, OrderExecutor, PositionManager
│   │   └── adapters/                # Bybit, Binance data adapters
│   │
│   ├── ml/                          # ML modules (optional)
│   │   ├── ai_backtest_executor.py  # AI-driven backtest
│   │   ├── regime_detection.py      # Market regime detection
│   │   └── enhanced/                # AutoML, Feature Store, Model Registry
│   │
│   ├── monitoring/                  # Prometheus, health checks, cost tracking
│   ├── middleware/                  # CORS, CSRF, rate limiting, request-id
│   ├── security/                    # API key rotation, HSM, Shamir sharing
│   └── migrations/versions/         # 13 Alembic migrations
│
├── frontend/
│   ├── strategy-builder.html        # PRIMARY strategy page (Builder UI)
│   ├── backtest-results.html        # Backtest results viewer
│   ├── optimizations.html           # Parameter optimization
│   ├── dashboard.html               # Main dashboard
│   ├── css/strategy_builder.css
│   └── js/
│       ├── pages/strategy_builder.js   # Builder logic (blocks, connections, run)
│       ├── pages/backtest_results.js   # Tables and charts
│       ├── pages/optimization.js       # Optimization management
│       ├── shared/leverageManager.js   # Shared leverage module
│       ├── shared/instrumentService.js # Symbols service
│       └── core/ / components/         # EventBus, StateManager, ApiClient, UI components
│
├── tests/
│   ├── conftest.py
│   ├── backend/
│   │   ├── backtesting/             # test_engine.py, test_strategy_builder_parity.py
│   │   ├── api/                     # test_strategies_crud.py, test_strategy_builder.py
│   │   └── services/                # test_walk_forward.py, test_monte_carlo.py
│   ├── integration/                 # Postgres upsert, Redis streams
│   ├── ai_agents/                   # 56 divergence + agent tests
│   └── e2e/                         # test_strategy_builder_full_flow.py
│
├── mcp-server/                      # MCP orchestrator (disabled in prod)
├── documentation/                   # PRODUCTION_DEPLOYMENT_CHECKLIST, specs
└── data/archive/                    # Logs, JSON result dumps
```

---

## 5. Critical Constants — NEVER CHANGE WITHOUT EXPLICIT APPROVAL

| Constant              | Value                                        | Location                            | Reason                                                      |
| --------------------- | -------------------------------------------- | ----------------------------------- | ----------------------------------------------------------- |
| `commission_value`    | **0.0007** (0.07%)                           | `BacktestConfig.commission_value`   | TradingView parity — 10+ files depend on this               |
| Engine                | **FallbackEngineV4**                         | `backend/backtesting/engine.py`     | Gold standard; V2 kept for parity tests only, V3 deprecated |
| `DATA_START_DATE`     | **2025-01-01**                               | `backend/config/database_policy.py` | Never hardcode — always import                              |
| Timeframes            | `["1","5","15","30","60","240","D","W","M"]` | adapter + validator                 | Legacy mapping on load: 3→5, 120→60, 360→240, 720→D         |
| `initial_capital`     | **10000.0** (default)                        | `BacktestConfig.initial_capital`    | User-configurable; referenced in engine, metrics, UI        |
| Max backtest duration | **730 days** (2 years)                       | `BacktestConfig.validate_dates()`   | Pydantic validator; raises `ValueError` if exceeded         |

## High-Risk Variables (grep before any refactor)

- `commission_rate` / `commission_value` — breaks TradingView parity if changed
- `strategy_params` — used in all strategies, optimizer, and UI
- `initial_capital` — engine, metrics, UI
- Port aliases in adapter — silent signal drops if broken

---

## 6. Strategy Parameters

### Built-in strategies (`backend/backtesting/strategies.py`)

| Strategy               | Parameter       | Type      | Range / Default                       | Constraint                      |
| ---------------------- | --------------- | --------- | ------------------------------------- | ------------------------------- |
| `sma_crossover`        | `fast_period`   | int       | ≥2; default 10                        | must be < slow_period           |
| `sma_crossover`        | `slow_period`   | int       | > fast_period; default 30             |                                 |
| `rsi` (**deprecated**) | `period`        | int       | ≥2; default 14                        | Use universal RSI block instead |
| `rsi`                  | `oversold`      | float     | 0 < x < overbought; default 30        |                                 |
| `rsi`                  | `overbought`    | float     | < 100; default 70                     |                                 |
| `macd`                 | `fast_period`   | int       | < slow_period; default 12             |                                 |
| `macd`                 | `slow_period`   | int       | > fast_period; default 26             |                                 |
| `macd`                 | `signal_period` | int       | default 9                             |                                 |
| `bollinger_bands`      | `period`        | int       | ≥2; default 20                        |                                 |
| `bollinger_bands`      | `std_dev`       | float     | >0; default 2.0                       |                                 |
| `grid`                 | `grid_levels`   | int       | ≥2; default 5                         | set pyramiding = grid_levels    |
| `grid`                 | `grid_spacing`  | float (%) | >0; default 1.0%                      |                                 |
| `grid`                 | `take_profit`   | float (%) | default 1.5%                          |                                 |
| `grid`                 | `direction`     | enum str  | `"long"` / `"both"`; default `"long"` |                                 |

### Strategy Builder blocks (`backend/backtesting/strategy_builder_adapter.py`)

All indicator periods clamped to **[1, 500]** via `_clamp_period()`.

| Indicator                                 | Key params                                 | Notes                                        |
| ----------------------------------------- | ------------------------------------------ | -------------------------------------------- |
| SMA, EMA, WMA, DEMA, TEMA, HullMA         | `period` int                               |                                              |
| RSI (universal)                           | `period`, `oversold`, `overbought`, `mode` | Use this, not built-in RSI                   |
| MACD                                      | `fast`, `slow`, `signal`                   |                                              |
| Bollinger Bands                           | `period`, `std_dev`                        |                                              |
| Stochastic                                | `k_period`, `d_period`, `smooth`           |                                              |
| Stoch RSI                                 | `rsi_period`, `stoch_period`, `k`, `d`     |                                              |
| ADX                                       | `period`                                   |                                              |
| ATR                                       | `period`                                   |                                              |
| Supertrend                                | `period`, `multiplier`                     |                                              |
| Ichimoku                                  | `tenkan`, `kijun`, `senkou_b`              |                                              |
| Donchian                                  | `period`                                   |                                              |
| Keltner                                   | `ema_period`, `atr_period`, `multiplier`   |                                              |
| Parabolic SAR                             | `acceleration`, `max_acceleration`         |                                              |
| CCI, CMF, MFI, ROC, Williams %R, RVI, CMO | `period`                                   |                                              |
| OBV, PVT, A/D Line                        | —                                          | volume-based, no period                      |
| VWAP                                      | —                                          | built-in                                     |
| QQE                                       | `rsi_period`, `sf`, `q`                    |                                              |
| Divergence                                | —                                          | returns `long`/`short` + `bullish`/`bearish` |
| Pivot Points                              | `type`, `lookback`                         |                                              |

Timeframe params with value `"Chart"` → resolved to `main_interval` from Properties panel.
Keys: `timeframe`, `two_mas_timeframe`, `channel_timeframe`, `rvi_timeframe`,
`mfi_timeframe`, `cci_timeframe`, `momentum_timeframe`, `channel_close_timeframe`,
`rsi_close_timeframe`, `stoch_close_timeframe`.

### Port alias mapping (adapter)

When a frontend port name doesn't match backend output key, the adapter applies:

```
"long"    ↔ "bullish"
"short"   ↔ "bearish"
"output"  ↔ "value"
"result"  ↔ "signal"
```

File: [backend/backtesting/strategy_builder_adapter.py](backend/backtesting/strategy_builder_adapter.py)

---

## 7. Risk & Money Management

### Global parameters (`BacktestConfig` in `backend/backtesting/models.py`)

| Parameter                  | Type        | Range                                              | Default            | Purpose                                        |
| -------------------------- | ----------- | -------------------------------------------------- | ------------------ | ---------------------------------------------- |
| `initial_capital`          | float       | 100 – 100 000 000                                  | 10 000.0           | Starting capital                               |
| `position_size`            | float       | 0.01 – 1.0                                         | 1.0                | Fraction of capital per trade                  |
| `leverage`                 | float       | 1.0 – 125.0                                        | 1.0                | Leverage (Bybit max)                           |
| `direction`                | enum str    | `long` / `short` / `both`                          | `"both"`           | Trading direction                              |
| `commission_value`         | float       | ≥0.0                                               | **0.0007**         | Commission — NEVER change                      |
| `commission_type`          | enum str    | `percent` / `cash_per_contract` / `cash_per_order` | `"percent"`        | Commission type                                |
| `commission_on_margin`     | bool        | —                                                  | True               | TV-style: commission on margin, not full value |
| `maker_fee`                | float       | 0 – 0.01                                           | 0.0002             | Maker fee                                      |
| `taker_fee`                | float       | 0 – 0.01                                           | 0.0004             | Taker fee                                      |
| `slippage`                 | float       | 0 – 0.05                                           | 0.0005             | Slippage (decimal)                             |
| `slippage_ticks`           | int         | 0 – 100                                            | 0                  | Slippage in ticks                              |
| `stop_loss`                | float\|None | 0.001 – 0.5                                        | None               | SL (decimal from entry price)                  |
| `take_profit`              | float\|None | 0.001 – 1.0                                        | None               | TP (decimal from entry price)                  |
| `max_drawdown`             | float\|None | 0.01 – 1.0                                         | None               | Drawdown limit                                 |
| `trailing_stop_activation` | float\|None | 0.001 – 0.5                                        | None               | Trailing stop activation                       |
| `trailing_stop_offset`     | float\|None | 0.001 – 0.2                                        | None               | Trailing stop offset from peak                 |
| `breakeven_enabled`        | bool        | —                                                  | False              | Move SL to breakeven after TP                  |
| `breakeven_activation_pct` | float       | 0 – 0.5                                            | 0.005              | Breakeven activation threshold                 |
| `breakeven_offset`         | float       | 0 – 0.1                                            | 0.0                | Breakeven offset from entry                    |
| `sl_type`                  | enum str    | `average_price` / `last_order`                     | `"average_price"`  | SL reference price                             |
| `risk_free_rate`           | float       | 0 – 0.20                                           | 0.02               | Risk-free rate (Sharpe/Sortino)                |
| `pyramiding`               | int         | 0 – 99                                             | 1                  | Max concurrent entries (TV compatible)         |
| `close_rule`               | enum str    | `ALL` / `FIFO` / `LIFO`                            | `"ALL"`            | Position close order                           |
| `partial_exit_percent`     | float\|None | 0.1 – 0.99                                         | None               | Partial exit at TP                             |
| `close_only_in_profit`     | bool        | —                                                  | False              | Close via signal only if trade is profitable   |
| `no_trade_days`            | tuple[int]  | 0–6 (Mon–Sun)                                      | ()                 | Days to block trading                          |
| `market_type`              | enum str    | `spot` / `linear`                                  | `"linear"`         | Market data source                             |
| `use_bar_magnifier`        | bool        | —                                                  | True               | Precise SL/TP intrabar detection               |
| `intrabar_ohlc_path`       | enum str    | see models.py                                      | `"O-HL-heuristic"` | OHLC path model                                |

### DCA Grid parameters

| Parameter                     | Type      | Range                                              | Default               |
| ----------------------------- | --------- | -------------------------------------------------- | --------------------- |
| `dca_enabled`                 | bool      | —                                                  | False                 |
| `dca_order_count`             | int       | 2 – 15                                             | 5                     |
| `dca_grid_size_percent`       | float (%) | 0.1 – 50.0                                         | 1.0                   |
| `dca_martingale_coef`         | float     | 1.0 – 5.0                                          | 1.5                   |
| `dca_martingale_mode`         | enum str  | `multiply_each` / `multiply_total` / `progressive` | `"multiply_each"`     |
| `dca_drawdown_threshold`      | float (%) | 5 – 90                                             | 30.0                  |
| `dca_safety_close_enabled`    | bool      | —                                                  | True                  |
| `dca_tp1/2/3/4_percent`       | float (%) | 0 – 100                                            | 0.5 / 1.0 / 2.0 / 3.0 |
| `dca_tp1/2/3/4_close_percent` | float (%) | 0 – 100                                            | 25.0 each             |

### MM parameter dependencies

```
initial_capital × position_size          → trade_value (capital per entry)
trade_value × leverage                   → leveraged_position_value
leveraged_position_value × commission_value  → commission (if commission_on_margin=False)
trade_value × commission_value           → commission (TradingView style, commission_on_margin=True)

stop_loss (decimal) → closes long at entry_price × (1 - stop_loss)
take_profit (decimal)→ closes long at entry_price × (1 + take_profit)
sl_type = 'average_price' → SL from avg entry (DCA standard)
sl_type = 'last_order'    → SL from last DCA order price

trailing_stop_activation → trailing starts when PnL > activation%
trailing_stop_offset     → SL set at peak_price × (1 - offset%)

pyramiding ≥ 2
    → allows multiple concurrent entries
    → close_rule = ALL/FIFO/LIFO determines close order

dca_martingale_coef × position_size per level → size of each DCA order
dca_drawdown_threshold → triggers safety close when account_drawdown > threshold%
```

### Key optimization metrics (scoring targets)

The optimizer (`backend/optimization/scoring.py`) supports 20 metrics as objective functions. The most commonly used:

| Metric            | Direction | Notes                                                                |
| ----------------- | --------- | -------------------------------------------------------------------- |
| `net_profit`      | higher ↑  | Absolute profit in capital currency                                  |
| `total_return`    | higher ↑  | Return as percentage                                                 |
| `sharpe_ratio`    | higher ↑  | Risk-adjusted return (uses `risk_free_rate`)                         |
| `sortino_ratio`   | higher ↑  | Like Sharpe but penalizes only downside volatility                   |
| `calmar_ratio`    | higher ↑  | `total_return / max_drawdown` — computed in scorer                   |
| `max_drawdown`    | lower ↓   | Reported in **percent** (17.29 = 17.29%); scorer negates for sorting |
| `win_rate`        | higher ↑  | Winning trades / total trades × 100                                  |
| `profit_factor`   | higher ↑  | Gross profit / gross loss                                            |
| `expectancy`      | higher ↑  | Average expected profit per trade                                    |
| `recovery_factor` | higher ↑  | Net profit / max drawdown                                            |

> `rank_by_multi_criteria()` ranks results across multiple criteria simultaneously using average-rank method.

---

## 8. Domain Knowledge

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

### MetricsCalculator is the single source of truth

All engines (Fallback, Numba, GPU, fast_optimizer) MUST use `MetricsCalculator.calculate_all()`.
Do NOT reimplement metric formulas elsewhere — sync issues have caused bugs before.

---

## 9. How to Work with Claude Code

### Directories to prioritize first

```
backend/backtesting/            # Engine, adapter, strategies, models — core
backend/core/metrics_calculator.py  # 166 metrics — read before any metrics change
backend/config/database_policy.py   # Date/retention constants
backend/api/routers/backtests.py    # Main backtest API
backend/api/routers/strategy_builder.py
frontend/js/pages/strategy_builder.js
frontend/js/pages/backtest_results.js
CLAUDE.md                           # This file
```

### Directories to usually ignore

```
mcp-server/                     # MCP disabled, not active in prod
frontend/dist/                  # Build artifacts
data/archive/                   # Logs and result dumps
backend/backtesting/universal_engine/  # Experimental, not in main flow
backend/ml/                     # ML optional, not core to backtest
deployment/                     # DevOps, not code
```

### Commands

```bash
# Start server
python main.py server

# Run migrations
python main.py migrate

# Generate AI strategy
python main.py generate-strategy --prompt "RSI momentum for BTCUSDT"

# Run backtest (CLI stub — full backtest via API)
python main.py backtest --strategy-id 1 --symbol BTCUSDT

# Health check
python main.py health --detailed

# Run tests (use pytest directly, not via main.py)
pytest tests/ -x -q
pytest tests/ai_agents/test_divergence_block_ai_agents.py -v
pytest tests/backend/backtesting/test_engine.py -v
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v
pytest tests/e2e/test_strategy_builder_full_flow.py -v
```

---

## 10. Conventions

### Naming

- Strategy type IDs: snake_case enum (`sma_crossover`, `bollinger_bands`, `dca`)
- Strategy Builder block types: lowercase (`rsi`, `macd`, `supertrend`, `strategy`, `divergence`)
- Test files: `test_<module_name>.py` in mirrored directory structure under `tests/`
- Router files: plural nouns (`backtests.py`, `strategies.py`, `optimizations.py`)

### Parameter conventions

- All `strategy_params` are `dict[str, Any]` passed through to strategy class
- Indicator periods: always int, clamped [1, 500] in adapter
- Risk params (SL/TP/commissions): always **decimal** (0.07% = 0.0007), not percent
- Exception — DCA: `dca_grid_size_percent` and `dca_tp*_percent` are in **percent** (1.0 = 1%)

### Code patterns

1. **No shell commands in tests** — mock subprocess calls; Bash unreliable on this machine
2. **Async everywhere** — FastAPI routes are `async def`; use `asyncio.run()` only at CLI level
3. **Type hints required** — mypy configured (`warn_return_any=false`, `ignore_missing_imports=true`)
4. **Logging** — use `structlog` / `structured_logging.py`, not bare `print()`
5. **Frontend** — no build step; pure ES modules, no npm/webpack

---

## 11. Environment Variables (from .env.example)

| Variable                             | Purpose                                   |
| ------------------------------------ | ----------------------------------------- |
| `DATABASE_URL`                       | PostgreSQL connection string              |
| `REDIS_URL`                          | Redis URL for pub/sub and cache           |
| `DEEPSEEK_API_KEY`                   | DeepSeek AI key                           |
| `QWEN_API_KEY`                       | Alibaba DashScope key                     |
| `PERPLEXITY_API_KEY`                 | Perplexity AI key                         |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Optional, only for live private endpoints |
| `CORS_ALLOW_ALL`                     | `true` in dev only                        |
| `FORCE_DIRECT_AGENT_API`             | Keep `1` (MCP disabled)                   |

Copy `.env.example` → `.env` and fill API keys before first run.

---

## 12. Deprecated Items

Collected here for clarity — do **not** use in new code:

| Item                            | Location                            | Replacement                                             |
| ------------------------------- | ----------------------------------- | ------------------------------------------------------- |
| `fast_optimizer.py`             | `backend/backtesting/`              | Use `backend/optimization/optuna_optimizer.py` (Optuna) |
| `RSIStrategy` (built-in)        | `backend/backtesting/strategies.py` | Use universal RSI block in Strategy Builder             |
| `BacktestConfig.force_fallback` | `backend/backtesting/models.py`     | Use `engine_type="fallback"` instead                    |
| `StrategyType.ADVANCED`         | `backend/backtesting/models.py`     | Not implemented — placeholder enum value                |
| `FallbackEngineV2`              | `backend/backtesting/engines/`      | Use FallbackEngineV4 (gold standard)                    |
| `FallbackEngineV3`              | `backend/backtesting/engines/`      | Use FallbackEngineV4                                    |
| `GPUEngineV2`                   | `backend/backtesting/engines/`      | Use NumbaEngineV2 for optimization speed                |

---

## 13. Test Infrastructure

### conftest.py layout

| File                 | Purpose                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `conftest.py` (root) | Adds project root to `sys.path`; pre-imports `backend` package       |
| `tests/conftest.py`  | Fixes import resolution between `tests/backend/` and real `backend/` |

### Key fixtures (defined in test files / conftest)

- `sample_ohlcv` — standard OHLCV DataFrame with 100+ bars for indicator/engine tests
- `mock_adapter` — mocked Bybit adapter (never calls real API in unit tests)
- `db_session` — in-memory SQLite session for repository tests
- `backtest_config` — pre-configured `BacktestConfig` with safe defaults

> **Rule:** Never call real Bybit API in unit tests — always mock via `mock_adapter`.

---

## 14. Recent Major Changes

### 2026-02-21

- Full project map added to CLAUDE.md (directory structure, parameter tables, MM dependencies)
- Added: Strategy Builder graph JSON format, SignalResult contract, Engine Selection table
- Added: direction default caveat (API vs Engine vs Builder), warning codes, market_type docs
- Added: 730-day backtest limit, key optimization metrics, deprecated items list, test infrastructure

### 2026-02-19

- `strategies.html` **removed** — all strategy functionality on `strategy-builder.html`
- Shared utilities moved to `frontend/js/shared/`
- 13 nav links updated across 10 HTML files
- Divergence block critical fix: now returns `long`/`short` keys alongside `bullish`/`bearish`
- Direction mismatch wire highlighting (frontend) + engine warning + API warnings field
- Port alias fallback added to Case 2 signal routing in adapter
- `main.py` Unicode fix for cp1251 Windows terminals
- 56 divergence tests passing (6 handler + 50 AI agent)
