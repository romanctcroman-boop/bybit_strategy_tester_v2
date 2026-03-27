# CLAUDE_CODE.md — Полный Контекст для Claude Code

> **Версия:** 2.1 | **Создан:** 2026-03-26 | **Обновлён:** 2026-03-27
> **Назначение:** Единый документ для Claude Code — структура, переменные, связи, роутинг, хранение, потоки
> **Обновляй:** после каждого структурного изменения
> **Покрытие:** ~100% систем проекта (31 секция, ~2700 строк)

---

## 📑 Навигация

| Раздел                                   | Содержание                                          |
| ---------------------------------------- | --------------------------------------------------- |
| [§1](#1-окружение)                       | Окружение, запуск, команды                          |
| [§2](#2-архитектура-слои)                | 6-слойная архитектура                               |
| [§3](#3-полная-библиотека-переменных)    | Все переменные, типы, диапазоны, файлы              |
| [§4](#4-граф-зависимостей-переменных)    | Логические связи, глубина проникновения             |
| [§5](#5-кросс-системные-переменные)      | 7 high-risk параметров, 12+ файлов каждый           |
| [§6](#6-блоки-strategy-builder)          | 40+ блоков, порты, расширения                       |
| [§7](#7-роутинг-данных)                  | 70+ роутеров, маршрутизация запросов                |
| [§8](#8-хранение-данных)                 | SQLite, Redis, кэши, ORM модели                     |
| [§9](#9-чтение-данных)                   | KlineDataManager, DataService, adapters             |
| [§10](#10-преобразование-данных)         | Pipeline: raw OHLCV → signals → trades → metrics    |
| [§11](#11-потоковая-обработка)           | WebSocket, SSE, Redis pub/sub                       |
| [§12](#12-middleware-pipeline)           | 10 middleware в фиксированном порядке               |
| [§13](#13-движки-бэктестинга)            | V4, Numba, DCA — выбор и паритет                    |
| [§14](#14-метрики)                       | MetricsCalculator — 166 метрик, TV-parity           |
| [§15](#15-ai-agent-system)               | LangGraph pipeline, LLM providers, memory           |
| [§16](#16-инфраструктура-claude-code)    | Hooks, slash commands, memory-bank                  |
| [§17](#17-критические-инварианты)        | НИКОГДА не нарушай                                  |
| [§18](#18-рефакторинг-чеклист)           | Pre-flight → Post-flight                            |
| [§19](#19-live-trading-subsystem)        | Live trading, WebSocket, order execution            |
| [§20](#20-risk-management)               | RiskEngine, position sizing, stop loss, exposure    |
| [§21](#21-agent-memory-system)           | 4-tier memory, vector store, BM25, SQLite backend   |
| [§22](#22-agent-consensus--debate)       | ConsensusEngine, deliberation, RiskVetoGuard        |
| [§23](#23-agent-self-improvement)        | FeedbackLoop, evolution, RLHF, pattern extraction   |
| [§24](#24-security-layer)                | Prompt guards, AES-256-GCM, Shamir, HSM             |
| [§25](#25-mlrl-subsystem)                | Regime detection, RL agents, Gymnasium env          |
| [§26](#26-monte-carlo--walk-forward)     | Monte Carlo simulation, walk-forward validation     |
| [§27](#27-monitoring--observability)     | Prometheus, health checks, cost tracking, alerts    |
| [§28](#28-optimization-system-deep-dive) | Ray optimizer, advanced engine, filters             |
| [§29](#29-frontend-architecture)         | StateManager, EventBus, 25 components, core modules |
| [§30](#30-services-layer-deep-dive)      | 60+ services, LLM clients, event bus, reliability   |
| [§31](#31-auxiliary--experimental-modules)| Celery, reports, social, research, L2 LOB, benchmark |

---

## 1. Окружение

```yaml
OS: Windows 11
Shell: PowerShell 5.1 + Git Bash (через wsl-bash.bat)
Python: 3.11-3.14 (.venv/)
Project: D:\bybit_strategy_tester_v2
DB: SQLite (data.sqlite3, bybit_klines_15m.db) + PostgreSQL (prod)
Cache: Redis (localhost:6379)
Server: http://localhost:8000
Frontend: http://localhost:8000/frontend/strategy-builder.html
Swagger: http://localhost:8000/docs
```

### Команды

```bash
# Сервер
python main.py server                          # или: uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
python main.py health --detailed               # Проверка здоровья
python main.py migrate                         # Alembic миграции

# Тесты
pytest tests/ -x -q                            # Все
pytest tests/ -x -q -m "not slow"              # Быстрые
pytest tests/backend/backtesting/test_engine.py -v  # Движок

# Линтинг (ВСЕГДА перед коммитом)
ruff check . --fix
ruff format .
```

---

## 2. Архитектура (слои)

```
┌─────────────────────────────────────────────────────────────────┐
│ EXTERNAL:  Bybit API v5  │  TradingView (metrics parity)       │
│            DeepSeek V3.2  │  Perplexity  │  Qwen (DashScope)   │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ ADAPTER:   BybitAdapter (1710 строк)                            │
│            REST + WebSocket, rate limit 120 req/min             │
│            Tickers cache (30s TTL), CircuitBreaker              │
│            Файл: backend/services/adapters/bybit.py             │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ SERVICE:   KlineDataManager (Singleton)                         │
│            DataService (Repository CRUD)                        │
│            KlineDBService (FROZEN — не менять)                  │
│            Per-(symbol, interval, market_type) asyncio.Lock     │
│            Файлы: backend/services/                             │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ ENGINE:    FallbackEngineV4 (gold standard, 3204 строк)         │
│            NumbaEngineV2 (JIT, 20-40x, для оптимизации)         │
│            DCAEngine (auto if dca_enabled=True)                 │
│            engine_selector.py → ENGINE_MAP[engine_type]         │
│            Файлы: backend/backtesting/engines/                  │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ METRICS:   MetricsCalculator.calculate_all() — 166 метрик       │
│            formulas.py — чистая математика (единый источник)     │
│            Файл: backend/core/metrics_calculator.py             │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ API:       FastAPI (753+ маршрутов, 70+ router файлов)          │
│            10 middleware (ordered pipeline)                      │
│            WebSocket streaming (AI, charts, ticks)              │
│            Файл: backend/api/app.py (1070 строк)               │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│ FRONTEND:  Vanilla HTML/JS/CSS — НЕТ BUILD STEP                 │
│            strategy-builder.html (13378 строк JS)               │
│            ES modules, no npm/webpack                           │
│            Файлы: frontend/                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые директории

```
backend/
├── api/                    # FastAPI app, 70+ routers, middleware, schemas
│   ├── app.py              # App factory, mount routers (1070 строк)
│   ├── lifespan.py         # startup: DB init, Redis, warmup; shutdown: cleanup
│   ├── middleware_setup.py # 10 middleware в фиксированном порядке
│   ├── streaming.py        # WebSocket: AI streaming, live charts, ticks
│   └── routers/            # 55+ router files (backtests, strategies, optimizations...)
├── backtesting/
│   ├── engine.py           # BacktestEngine — entry point (~2000 строк)
│   ├── engine_selector.py  # ENGINE_MAP routing (~200 строк)
│   ├── models.py           # BacktestConfig (100+ полей), BacktestResult (~1300 строк)
│   ├── interfaces.py       # BacktestInput dataclass (100+ полей)
│   ├── strategies/         # BaseStrategy, SMA, RSI, MACD, Bollinger, Grid
│   ├── indicator_handlers.py  # INDICATOR_DISPATCH + 40+ handlers (2217 строк)
│   ├── strategy_builder/   # Graph-based strategy execution
│   │   ├── adapter.py      # Graph → BaseStrategy (1399 строк, Phase 3)
│   │   ├── block_executor.py
│   │   ├── graph_parser.py
│   │   ├── signal_router.py
│   │   └── topology.py
│   └── engines/
│       ├── fallback_engine_v4.py  # Gold standard (3204 строк)
│       ├── dca_engine.py          # DCA-специализированный
│       └── (v2, v3 — deprecated)
├── core/
│   ├── metrics_calculator.py  # 166 TV-parity метрик
│   └── formulas.py            # Чистая математика
├── config/
│   ├── constants.py        # COMMISSION_TV=0.0007, DEFAULT_CAPITAL=10000
│   └── database_policy.py  # DATA_START_DATE=2025-01-01, RETENTION_YEARS=2
├── services/
│   ├── adapters/bybit.py   # BybitAdapter (1710 строк)
│   ├── data_service.py     # DataService (Repository CRUD)
│   ├── kline_manager.py    # KlineDataManager (Singleton)
│   └── kline_db_service.py # FROZEN DB service
├── database/
│   ├── __init__.py         # SQLAlchemy engine, SessionLocal, Base
│   └── models/             # ORM: Strategy, Backtest, Trade, Optimization...
├── optimization/
│   ├── optuna_optimizer.py # Bayesian TPE/CMA-ES — ОСНОВНОЙ
│   ├── builder_optimizer.py# Strategy Builder optimization
│   ├── scoring.py          # 20 scoring metrics
│   └── models.py           # OptimizationConfig
├── agents/                 # LangGraph AI pipeline
│   ├── trading_strategy_graph.py  # Main agent graph
│   ├── llm_clients/        # DeepSeek, Qwen, Perplexity
│   └── mcp/tools/          # Agent tools (backtest, analyze)
└── ml/                     # Optional ML (RL, AutoML, regime detection)

frontend/
├── strategy-builder.html   # ОСНОВНАЯ страница
├── js/pages/strategy_builder.js  # 13378 строк
├── js/shared/              # leverageManager.js, instrumentService.js
├── js/core/                # EventBus, StateManager, ApiClient
└── css/                    # Стили

tests/                      # 214 файлов, 179+ тестов проходят
├── backend/backtesting/    # test_engine.py, test_strategy_builder_parity.py
├── backend/api/            # test_strategies_crud.py, test_strategy_builder.py
├── ai_agents/              # 56+ divergence + agent tests
└── e2e/                    # test_strategy_builder_full_flow.py
```

---

## 3. Полная библиотека переменных

### 3.1 Критические константы (NEVER CHANGE)

| Переменная        | Значение                                     | Файл                                | Глубина проникновения                                            |
| ----------------- | -------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------- |
| `COMMISSION_TV`   | `0.0007` (0.07%)                             | `backend/config/constants.py`       | 12+ файлов — engine, bridges, optimization, agents, ML, frontend |
| `DEFAULT_CAPITAL` | `10000.0`                                    | `backend/config/constants.py`       | engine, metrics, optimization, frontend tests                    |
| `DATA_START_DATE` | `datetime(2025,1,1, tzinfo=utc)`             | `backend/config/database_policy.py` | adapter, kline_manager, API validators                           |
| `RETENTION_YEARS` | `2`                                          | `backend/config/database_policy.py` | kline cleanup, API date validators                               |
| `ALL_TIMEFRAMES`  | `["1","5","15","30","60","240","D","W","M"]` | `backend/config/constants.py`       | adapter, validators, frontend dropdown                           |

### 3.2 BacktestConfig (100+ полей)

**Файл:** `backend/backtesting/models.py` — Pydantic BaseModel

#### Основные параметры

| Параметр               | Тип      | Диапазон                                 | Default    | Подсистемы                                            |
| ---------------------- | -------- | ---------------------------------------- | ---------- | ----------------------------------------------------- |
| `initial_capital`      | float    | 100 – 100M                               | 10000.0    | engine, metrics, optimization, frontend               |
| `position_size`        | float    | 0.01 – 1.0                               | 1.0        | engine, optimization, live trading (⚠️ unit mismatch) |
| `leverage`             | float    | 1.0 – 125.0                              | 1.0        | engine, optimization (default 10!), frontend, live    |
| `direction`            | enum str | long/short/both                          | "both"     | API (default "long"!), engine, frontend               |
| `commission_value`     | float    | ≥0.0                                     | **0.0007** | EVERYWHERE — NEVER CHANGE                             |
| `commission_type`      | enum str | percent/cash_per_contract/cash_per_order | "percent"  | engine                                                |
| `commission_on_margin` | bool     | —                                        | True       | engine (TV-style: on margin, NOT on leveraged value)  |
| `maker_fee`            | float    | 0 – 0.01                                 | 0.0002     | engine                                                |
| `taker_fee`            | float    | 0 – 0.01                                 | 0.0004     | engine                                                |
| `slippage`             | float    | 0 – 0.05                                 | 0.0005     | engine                                                |
| `market_type`          | enum str | spot/linear                              | "linear"   | adapter, kline_manager, engine                        |
| `pyramiding`           | int      | 0 – 99                                   | 1          | engine, engine_selector, optimization                 |

#### Risk Management

| Параметр                   | Тип         | Диапазон                 | Default          | Назначение               |
| -------------------------- | ----------- | ------------------------ | ---------------- | ------------------------ |
| `stop_loss`                | float\|None | 0.001 – 0.5              | None             | SL (decimal от entry)    |
| `take_profit`              | float\|None | 0.001 – 1.0              | None             | TP (decimal от entry)    |
| `max_drawdown`             | float\|None | 0.01 – 1.0               | None             | Лимит просадки           |
| `trailing_stop_activation` | float\|None | 0.001 – 0.5              | None             | Активация trailing       |
| `trailing_stop_offset`     | float\|None | 0.001 – 0.2              | None             | Отступ от пика           |
| `breakeven_enabled`        | bool        | —                        | False            | Двигать SL на breakeven  |
| `breakeven_activation_pct` | float       | 0 – 0.5                  | 0.005            | Порог активации          |
| `sl_type`                  | enum str    | average_price/last_order | "average_price"  | Референс цена для SL     |
| `risk_free_rate`           | float       | 0 – 0.20                 | 0.02             | Sharpe/Sortino           |
| `close_rule`               | enum str    | ALL/FIFO/LIFO            | "ALL"            | Порядок закрытия позиций |
| `partial_exit_percent`     | float\|None | 0.1 – 0.99               | None             | Частичный выход на TP    |
| `close_only_in_profit`     | bool        | —                        | False            | Закрывать только в плюсе |
| `use_bar_magnifier`        | bool        | —                        | True             | Точное SL/TP внутри бара |
| `intrabar_ohlc_path`       | enum str    | see models.py            | "O-HL-heuristic" | OHLC path модель         |

#### DCA/Grid параметры

| Параметр                      | Тип       | Диапазон                                 | Default         |
| ----------------------------- | --------- | ---------------------------------------- | --------------- |
| `dca_enabled`                 | bool      | —                                        | False           |
| `dca_order_count`             | int       | 2 – 15                                   | 5               |
| `dca_grid_size_percent`       | float (%) | 0.1 – 50.0                               | 1.0             |
| `dca_martingale_coef`         | float     | 1.0 – 5.0                                | 1.5             |
| `dca_martingale_mode`         | enum str  | multiply_each/multiply_total/progressive | "multiply_each" |
| `dca_drawdown_threshold`      | float (%) | 5 – 90                                   | 30.0            |
| `dca_tp1/2/3/4_percent`       | float (%) | 0 – 100                                  | 0.5/1.0/2.0/3.0 |
| `dca_tp1/2/3/4_close_percent` | float (%) | 0 – 100                                  | 25.0 each       |

### 3.3 Strategy Parameters (built-in strategies)

| Strategy               | Parameter                         | Type            | Range/Default      | Constraint               |
| ---------------------- | --------------------------------- | --------------- | ------------------ | ------------------------ |
| `sma_crossover`        | `fast_period`                     | int             | ≥2; default 10     | < slow_period            |
| `sma_crossover`        | `slow_period`                     | int             | > fast; default 30 |                          |
| `rsi` (**deprecated**) | `period`                          | int             | ≥2; default 14     | Use universal RSI block  |
| `rsi`                  | `oversold/overbought`             | float           | 0-100; 30/70       |                          |
| `macd`                 | `fast/slow/signal`                | int             | 12/26/9            | fast < slow              |
| `bollinger_bands`      | `period/std_dev`                  | int/float       | 20/2.0             |                          |
| `grid`                 | `grid_levels/spacing/take_profit` | int/float/float | 5/1.0%/1.5%        | pyramiding = grid_levels |

### 3.4 Strategy Builder Indicator Parameters

Все периоды зажаты в **[1, 500]** через `_clamp_period()`.

| Индикатор                                           | Ключевые параметры                         | Примечания                           |
| --------------------------------------------------- | ------------------------------------------ | ------------------------------------ |
| SMA, EMA, WMA, DEMA, TEMA, HullMA                   | `period` int                               |                                      |
| RSI (universal)                                     | `period`, `oversold`, `overbought`, `mode` | Используй вместо built-in            |
| MACD                                                | `fast`, `slow`, `signal`                   |                                      |
| Bollinger Bands                                     | `period`, `std_dev`                        |                                      |
| Stochastic                                          | `k_period`, `d_period`, `smooth`           |                                      |
| Stoch RSI                                           | `rsi_period`, `stoch_period`, `k`, `d`     |                                      |
| ADX, ATR, CCI, CMF, MFI, ROC, Williams %R, RVI, CMO | `period`                                   |                                      |
| Supertrend                                          | `period`, `multiplier`                     |                                      |
| Ichimoku                                            | `tenkan`, `kijun`, `senkou_b`              |                                      |
| Donchian, Keltner                                   | `period` + specific                        |                                      |
| Parabolic SAR                                       | `acceleration`, `max_acceleration`         |                                      |
| OBV, PVT, A/D Line                                  | —                                          | volume-based, no period              |
| VWAP                                                | —                                          | built-in                             |
| QQE                                                 | `rsi_period`, `sf`, `q`                    |                                      |
| Divergence                                          | —                                          | returns long/short + bullish/bearish |
| Pivot Points                                        | `type`, `lookback`                         |                                      |

### 3.5 Frontend-specific переменные

```javascript
// Commission conversion: UI → Backend
// UI показывает:  0.07 (процент)
// Backend ждёт:   0.0007 (decimal)

// Leverage slider: max 125, color-coded (зелёный→жёлтый→красный)
// Direction: 'both' / 'long' / 'short' — frontend default = 'both'

// Canvas zoom: все координаты делятся на zoom (исправлено 2026-02-21)
// Block IDs: `block_${Date.now()}_${random}` (суффикс добавлен 2026-02-21)
```

### 3.6 Environment Variables

| Variable                             | Purpose                                     |
| ------------------------------------ | ------------------------------------------- |
| `DATABASE_URL`                       | PostgreSQL connection (prod)                |
| `REDIS_URL`                          | Redis URL                                   |
| `DEEPSEEK_API_KEY`                   | DeepSeek AI                                 |
| `QWEN_API_KEY`                       | Alibaba DashScope                           |
| `PERPLEXITY_API_KEY`                 | Perplexity AI                               |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Live endpoints (optional)                   |
| `CORS_ALLOW_ALL`                     | `true` in dev only                          |
| `FORCE_DIRECT_AGENT_API`             | Keep `1` (MCP disabled)                     |
| `AGENT_MEMORY_BACKEND`               | SQLite path (default: data/agent_memory.db) |

---

## 4. Граф зависимостей переменных

### 4.1 Цепочка вычислений PnL

```
initial_capital × position_size = trade_value
trade_value × leverage = leveraged_position_value

# Commission (TradingView style, commission_on_margin=True):
commission = trade_value × commission_value   # НЕ leveraged × commission

# Entry: на open СЛЕДУЮЩЕГО бара (не бар сигнала!)
entry_price = next_bar.open

# PnL для long:
pnl = (exit_price - entry_price) / entry_price × leveraged_position_value - 2×commission

# SL check (long):
if bar.low ≤ entry_price × (1 - stop_loss):
    exit at SL level

# TP check (long):
if bar.high ≥ entry_price × (1 + take_profit):
    exit at TP level

# Trailing:
if unrealized_pnl% > trailing_stop_activation:
    trail_active = True
    trail_price = max(trail_price, current_high × (1 - trailing_stop_offset))
    if bar.low ≤ trail_price: exit
```

### 4.2 Направление сигнала: граф проникновения

```
Strategy Builder Frontend
    ↓ direction (default: "both")
POST /api/strategy-builder/run
    ↓ direction (⚠️ POST /api/backtests/ default: "long"!)
BacktestConfig.direction (default: "both")
    ↓
FallbackEngineV4._apply_direction_filter()
    ↓ Фильтрует сигналы: если direction="long" → short signals = 0
SignalResult → entries/exits (оставшиеся)
    ↓
Trades → MetricsCalculator.calculate_all()
    ↓
API response.warnings: ["[DIRECTION_MISMATCH]..."]
    ↓
Frontend: red dashed wire (.direction-mismatch, stroke: #ef4444)
```

### 4.3 Commission: полный путь (12+ файлов)

```
constants.py: COMMISSION_TV = 0.0007
    ↓
models.py: BacktestConfig.commission_value = 0.0007
    ├→ engine.py: self.config.commission_value
    ├→ fallback_engine_v4.py: commission = trade_value × 0.0007
    ├→ backtest_bridge.py: config.commission_value (строка 50)
    ├→ walk_forward_bridge.py: config.commission_value (строка 54)
    ├→ optimization/models.py: commission_value (строки 32, 189)
    ├→ agents/mcp/tools/backtest.py: commission (строка 160)
    ├→ ml/rl/trading_env.py: commission (строка 58)
    ├→ api/routers/agents.py: commission (строка 902)
    ├→ mlflow_tracking.py: commission (строка 188)
    ├→ metrics_calculator.py: commission_paid
    ├→ strategy_builder.js: commission (строка 912)
    └→ live_trading.py: commission_rate (строка 263) — FIXED to 0.0007

# Оставшиеся 0.001 (НЕ баги — legacy/experimental):
# optimize_tasks.py:309,470 — fallback для missing key
# ai_backtest_executor.py:170 — ML experimental path
# backtests.py:1533 — param default для legacy DB records
```

### 4.4 Position Size: unit mismatch (ADR-006)

```
Engine / Optimization:
    position_size = 1.0  → fraction (1.0 = 100% of capital)
    position_size = 0.5  → 50% of capital

Live Trading (strategy_runner.py:72):
    position_size_percent = 100  → percent (100 = 100% of capital)

⚠️ Конвертация: position_size_percent / 100 = position_size (fraction)
```

### 4.5 Leverage: default mismatch

```
BacktestConfig:           leverage = 1.0  (conservative)
optimization/models.py:   leverage = 10   (aggressive optimization default)
Frontend leverageManager:  leverage = 10   (UI slider default)
Live trading:             leverage = 1.0  (safe default)

⚠️ Всегда проверяй, откуда берётся leverage в конкретном контексте
```

---

## 5. Кросс-системные переменные (HIGH RISK)

**Правило:** Перед изменением ЛЮБОГО параметра из этой таблицы →
`grep -rn <param_name> backend/ frontend/` и обнови ВСЕ файлы.

| Параметр                | Risk        | Файлы                                   | Default          | Ловушки                |
| ----------------------- | ----------- | --------------------------------------- | ---------------- | ---------------------- |
| `commission_value/rate` | 🔴 HIGHEST  | 12+ файлов                              | 0.0007           | 6+ hardcoded sites     |
| `initial_capital`       | 🔴 HIGH     | engine, metrics, optimization, frontend | 10000.0          | equity, CAGR, drawdown |
| `position_size`         | 🔴 HIGH     | engine, API, optimization, live         | 1.0              | fraction vs percent    |
| `leverage`              | 🟡 MODERATE | engine, optimization, frontend, live    | 1.0/10 varies    | default mismatch       |
| `pyramiding`            | 🟡 MODERATE | engine, engine_selector, optimization   | 1                |                        |
| `direction`             | 🟡 MODERATE | API, engine, frontend                   | varies!          | default mismatch       |
| `strategy_params`       | 🟢 LOW      | all layers                              | dict passthrough |                        |

### Commission parity check (запускай перед любым коммитом с commission)

```bash
grep -rn commission backend/ | grep -v 0.0007 | grep -v .pyc | grep -v __pycache__ | grep -v "0.001.*tolerance\|0.001.*qty\|optimize_tasks\|ai_backtest_executor.*0.001\|_commission.*0.001"
```

---

## 6. Блоки Strategy Builder

### 6.1 Архитектура блоков

```
Frontend (strategy-builder.html)
    ↓ JSON graph: { blocks: [...], connections: [...], properties: {...} }
POST /api/strategy-builder/run
    ↓
StrategyBuilderAdapter.__init__()
    ├→ graph_parser.parse() → normalized blocks + connections
    ├→ topology.topological_sort() → execution order (deque + popleft)
    ├→ _normalize_connections() → canonical format (once)
    └→ block_executor.execute() → per-block computation
        ├→ INDICATOR_DISPATCH[block_type](block, data) → indicator_handlers.py
        └→ signal_router.route() → port aliases → SignalResult
```

### 6.2 Типы блоков (40+)

| Категория      | Блоки                                                                   |
| -------------- | ----------------------------------------------------------------------- |
| **Trend**      | sma, ema, wma, dema, tema, hull_ma, supertrend, ichimoku, parabolic_sar |
| **Oscillator** | rsi, macd, stochastic, stoch_rsi, cci, williams_r, rvi, cmo, roc        |
| **Volume**     | obv, pvt, ad_line, cmf, mfi, vwap                                       |
| **Volatility** | bollinger_bands, atr, keltner, donchian                                 |
| **Filter**     | adx (trend strength filter)                                             |
| **Advanced**   | qqe, divergence, pivot_points                                           |
| **Logic**      | and_gate, or_gate, not_gate, signal_merger                              |
| **Control**    | strategy (entry/exit routing), properties (config)                      |

### 6.3 Port Aliases (КРИТИЧНО для сигналов)

```python
# StrategyBuilderAdapter class constants
_PORT_ALIASES = {
    "long":   ["bullish", "signal", "output", "value", "result"],
    "short":  ["bearish", "signal", "output", "value", "result"],
    "output": ["value", "signal", "result"],
    "result": ["signal", "output", "value"],
}
_SIGNAL_PORT_ALIASES = {
    "long":  ["bullish"],
    "short": ["bearish"],
}

# Каноничные aliases:
#   "long"    ↔ "bullish"
#   "short"   ↔ "bearish"
#   "output"  ↔ "value"
#   "result"  ↔ "signal"
```

**⚠️ Если port alias не найден — сигнал ТИХО теряется!**

### 6.4 Timeframe resolution

Параметры с value `"Chart"` → резолвятся в `main_interval` из Properties panel.

```
Ключи: timeframe, two_mas_timeframe, channel_timeframe, rvi_timeframe,
        mfi_timeframe, cci_timeframe, momentum_timeframe, channel_close_timeframe,
        rsi_close_timeframe, stoch_close_timeframe
```

### 6.5 Graph JSON format

```json
{
    "blocks": [
        { "id": "block_1711000000_abc", "type": "rsi", "params": { "period": 14 }, "x": 100, "y": 200 },
        { "id": "block_1711000001_def", "type": "strategy", "params": {}, "x": 400, "y": 200 }
    ],
    "connections": [{ "source_id": "block_1711000000_abc", "target_id": "block_1711000001_def", "source_port": "long", "target_port": "long_entry" }],
    "properties": {
        "symbol": "BTCUSDT",
        "interval": "15",
        "direction": "both",
        "initial_capital": 10000,
        "commission": 0.07,
        "leverage": 1
    }
}
```

---

## 7. Роутинг данных

### 7.1 Главные маршруты API

| Endpoint                         | Router file                  | Data flow                                              |
| -------------------------------- | ---------------------------- | ------------------------------------------------------ |
| `POST /api/backtests/`           | `backtests.py`               | Request → BacktestConfig → Engine → Metrics → Response |
| `POST /api/strategy-builder/run` | `strategy_builder/router.py` | Graph JSON → Adapter → Engine → Metrics → Response     |
| `POST /api/optimizations/`       | `optimizations.py`           | Config → Optuna → N×Engine → Scoring → Results         |
| `GET /api/marketdata/ohlcv`      | `marketdata.py`              | Symbol+TF → KlineDataManager → DataFrame → JSON        |
| `GET /api/strategies/`           | `strategies.py`              | DB → Strategy list                                     |
| `POST /api/agents/generate`      | `agents.py`                  | Prompt → LangGraph → Strategy JSON                     |
| `WS /api/ws/streaming`           | `streaming.py`               | Bidirectional: commands ↔ updates                      |

### 7.2 Backtest data flow (детальный)

```
1. POST /api/backtests/ (JSON body)
   ↓
2. Pydantic validation → BacktestConfig
   ├─ validate_dates(): max 730 days
   ├─ commission_value → 0.0007 (default)
   └─ direction → "long" (API default!) или из request body
   ↓
3. DataService.load_ohlcv(symbol, interval, start, end, market_type)
   ├─ KlineDataManager.get_klines() → check cache
   │   ├─ Cache hit → return DataFrame
   │   └─ Cache miss → BybitAdapter.get_historical_klines()
   │       ├─ REST API → paginated (max 200 candles/request)
   │       ├─ retCode != 0 → retry with exponential backoff
   │       └─ Rate limit 120 req/min → CircuitBreaker
   ├─ Coverage check → fill gaps if needed
   └─ Legacy TF mapping: 3→5, 120→60, 360→240, 720→D
   ↓
4. Strategy.generate_signals(df) → DataFrame with 'signal' column
   ├─ For Strategy Builder: StrategyBuilderAdapter(graph_json)
   │   ├─ topology.topological_sort() → deque
   │   ├─ block_executor → INDICATOR_DISPATCH[block_type]
   │   ├─ signal_router → port aliases → SignalResult
   │   └─ _clamp_period() → [1, 500]
   ├─ For built-in: RSIStrategy/MACDStrategy/etc
   └─ Returns: SignalResult(entries, exits, short_entries, short_exits, ...)
   ↓
5. engine_selector.select_engine(config) → ENGINE_MAP
   ├─ "fallback" / "auto" → FallbackEngineV4
   ├─ "numba" → NumbaEngineV2
   ├─ dca_enabled=True → DCAEngine (override)
   └─ pyramiding > 1 AND gpu_requested → fallback to V4
   ↓
6. Engine.run(data, signals, config) → trades[]
   ├─ Direction filter → drop forbidden signals
   ├─ Entry at NEXT BAR open (not signal bar!)
   ├─ SL/TP/Trailing checks (intrabar if use_bar_magnifier)
   ├─ Commission: trade_value × 0.0007 (on margin)
   ├─ Pyramiding: max concurrent entries = config.pyramiding
   └─ Close rule: ALL/FIFO/LIFO
   ↓
7. MetricsCalculator.calculate_all(trades, config)
   ├─ 166 metrics computed
   ├─ Long/Short breakdown
   ├─ Duration metrics
   └─ TV-parity formulas
   ↓
8. Response JSON:
   {
     "metrics": {166 метрик},
     "trades": [{entry_time, exit_time, pnl, ...}],
     "equity_curve": [...],
     "warnings": ["[DIRECTION_MISMATCH]...", "[NO_TRADES]..."]
   }
```

### 7.3 Engine Selection Matrix

| Условие                                | Engine           | Причина                        |
| -------------------------------------- | ---------------- | ------------------------------ |
| `engine_type="fallback"` или `"auto"`  | FallbackEngineV4 | Gold standard                  |
| `engine_type="numba"`                  | NumbaEngineV2    | 20-40x, для optimization loops |
| `dca_enabled=True` (любой engine_type) | DCAEngine        | Override — DCA специфика       |
| `pyramiding > 1` + GPU requested       | FallbackEngineV4 | GPU не поддерживает pyramiding |
| `engine_type="gpu"`                    | GPUEngineV2      | **DEPRECATED**                 |

---

## 8. Хранение данных

### 8.1 SQLite databases

```
data.sqlite3          — Основная БД (strategies, backtests, trades, optimizations, agent_memory)
bybit_klines_15m.db   — Kline data (OHLCV candles по символам)
data/agent_memory.db  — Agent memory (configurable via AGENT_MEMORY_BACKEND)
```

### 8.2 ORM Models (backend/database/models/)

```python
# Основные модели:
Strategy        # name, type, params, graph_json (for builder), created_at
Backtest        # strategy_id, symbol, interval, config_json, metrics_json, trades_json
Trade           # backtest_id, entry_time, exit_time, direction, pnl, commission
Optimization    # strategy_id, config, results, status (pending/running/completed/failed)
KlineData       # symbol, interval, timestamp, open, high, low, close, volume
AgentMemory     # key, value, metadata, created_at

# Relationships:
Strategy 1→N Backtest 1→N Trade
Strategy 1→N Optimization
```

### 8.3 4-уровневый кэш

```
L1: In-process dict (KlineDataManager._cache)
    ├─ Key: (symbol, interval, market_type)
    ├─ TTL: session lifetime
    └─ Per-key asyncio.Lock (concurrent access safe)

L2: Redis (если REDIS_URL настроен)
    ├─ Key: f"kline:{symbol}:{interval}:{market_type}"
    ├─ TTL: 5 min (hot data) / 1 hour (historical)
    └─ Pub/sub: invalidation events

L3: SQLite (bybit_klines_15m.db)
    ├─ KlineData table
    ├─ Indexed: (symbol, interval, timestamp)
    └─ Coverage tracking (gap detection)

L4: Bybit REST API
    ├─ Last resort — remote fetch
    ├─ Max 200 candles per request
    ├─ Paginated with cursor
    └─ Rate limited: 120 req/min
```

### 8.4 Паттерн записи

```python
# DataService (Repository pattern)
class DataService:
    def save_strategy(self, strategy_data: dict) -> Strategy:
        with SessionLocal() as session:
            strategy = Strategy(**strategy_data)
            session.add(strategy)
            session.commit()
            session.refresh(strategy)
            return strategy

# Async wrapper в роутерах:
result = await asyncio.to_thread(data_service.save_strategy, data)
```

### 8.5 Alembic миграции

```
backend/migrations/versions/  — 13 миграций
Команда: alembic upgrade head  (или: python main.py migrate)
```

---

## 9. Чтение данных

### 9.1 KlineDataManager (Singleton)

```python
# backend/services/kline_manager.py
class KlineDataManager:
    _instance = None  # Singleton
    _cache: dict[tuple[str, str, str], pd.DataFrame]  # (symbol, interval, market_type) → df
    _locks: dict[tuple[str, str, str], asyncio.Lock]   # Per-key locks

    async def get_klines(self, symbol, interval, start, end, market_type="linear"):
        key = (symbol, interval, market_type)
        async with self._locks[key]:
            if key in self._cache and self._covers(key, start, end):
                return self._slice(self._cache[key], start, end)
            # Fetch from DB or API, update cache
            df = await self._fetch_and_cache(key, start, end)
            return df
```

### 9.2 BybitAdapter (REST + WebSocket)

```python
# backend/services/adapters/bybit.py (1710 строк)
class BybitAdapter:
    # REST endpoints:
    async def get_historical_klines(symbol, interval, start, end) → dict
    async def get_tickers(category) → list[dict]  # cached 30s
    async def get_server_time() → int
    async def get_instruments_info(category) → list[dict]

    # WebSocket:
    async def subscribe_kline(symbol, interval, callback)
    async def subscribe_ticker(symbol, callback)
    async def subscribe_orderbook(symbol, depth, callback)

    # Safety:
    # retCode != 0 → retry with exponential backoff
    # 429 → CircuitBreaker → wait
    # Rate limit: 120 req/min
```

### 9.3 DataService (Repository CRUD)

```python
# backend/services/data_service.py
class DataService:
    def load_ohlcv(symbol, interval, start, end, market_type) → pd.DataFrame
    def save_strategy(data) → Strategy
    def get_strategy(id) → Strategy | None
    def list_strategies(filters) → list[Strategy]
    def save_backtest(data) → Backtest
    def get_backtest(id) → Backtest
    def save_trades(trades) → list[Trade]
    # ... CRUD for all ORM models
```

---

## 10. Преобразование данных

### 10.1 Pipeline: Raw OHLCV → Metrics

```
Stage 1: Raw OHLCV (from API/DB)
    │ columns: timestamp, open, high, low, close, volume
    │ dtype: float64 (prices), int64 (volume), datetime64 (timestamp)
    ↓

Stage 2: Preprocessing
    │ ├─ Timezone normalization → UTC
    │ ├─ Gap filling (forward fill, max 5 bars)
    │ ├─ Duplicate removal (keep last)
    │ └─ Legacy TF mapping: 3→5, 120→60, 360→240, 720→D
    ↓

Stage 3: Indicator Computation
    │ ├─ INDICATOR_DISPATCH[block_type](block, df)
    │ │   ├─ pandas_ta library (primary)
    │ │   ├─ Custom implementations (divergence, pivot_points)
    │ │   └─ period clamping: [1, 500]
    │ ├─ Multi-timeframe: resample + merge back
    │ └─ Output: df with indicator columns added
    ↓

Stage 4: Signal Generation
    │ ├─ Strategy.generate_signals(df) → 'signal' column (1/-1/0)
    │ ├─ Strategy Builder: block_executor → signal_router → port aliases
    │ └─ SignalResult: entries, exits, short_entries, short_exits
    ↓

Stage 5: Trade Execution (Engine)
    │ ├─ Direction filter (drop forbidden signals)
    │ ├─ Entry at next_bar.open
    │ ├─ SL/TP/Trailing per bar (bar magnifier)
    │ ├─ Commission: trade_value × 0.0007
    │ ├─ Pyramiding control (max concurrent entries)
    │ └─ Output: list[Trade] with pnl, commission, timestamps
    ↓

Stage 6: Metrics Calculation
    │ ├─ MetricsCalculator.calculate_all(trades, config)
    │ ├─ 166 metrics (TV-parity)
    │ ├─ Long/short breakdown
    │ ├─ Equity curve computation
    │ └─ Output: dict[str, float] + equity_curve: list[float]
    ↓

Stage 7: Response Assembly
    │ ├─ metrics + trades + equity_curve + warnings
    │ ├─ Warning codes: DIRECTION_MISMATCH, NO_TRADES, LOW_TRADE_COUNT
    │ └─ JSON serialization → API response
```

### 10.2 Ключевые трансформации

```python
# Commission (TradingView parity):
commission = trade_value * config.commission_value  # На margin, НЕ на leveraged
# Correct:  10000 * 1.0 * 0.0007 = 7.0
# Wrong:    10000 * 1.0 * 10 * 0.0007 = 70.0 (leverage НЕ включается)

# Max Drawdown (percent, не decimal):
max_drawdown = 17.29  # Означает 17.29%, НЕ 0.1729

# Sharpe Ratio:
sharpe = (mean(monthly_returns) - risk_free_rate/12) / std(monthly_returns) * sqrt(12)

# Win Rate (percent):
win_rate = winning_trades / total_trades * 100

# Profit Factor:
profit_factor = gross_profit / gross_loss  # inf if gross_loss == 0
```

---

## 11. Потоковая обработка

### 11.1 WebSocket Streaming

```python
# backend/api/streaming.py
# Endpoint: WS /api/ws/streaming

# Capabilities:
# 1. AI agent response streaming (token-by-token)
# 2. Live chart data (kline updates)
# 3. Tick data (real-time price feeds)
# 4. Backtest progress updates (% complete)
# 5. Optimization progress (trial N/M, best score)

# Protocol:
# Client → Server:  {"action": "subscribe", "channel": "kline", "symbol": "BTCUSDT", "interval": "15"}
# Server → Client:  {"channel": "kline", "data": {"t": 1711000000, "o": 50000, ...}}
# Server → Client:  {"channel": "ai_stream", "data": {"token": "Based on", "done": false}}
# Server → Client:  {"channel": "backtest_progress", "data": {"percent": 45, "current_bar": 1000}}
```

### 11.2 Server-Sent Events (SSE)

```python
# Frontend JS uses EventSource for:
# 1. Kline DB sync progress (SymbolSyncModule)
# 2. Agent pipeline updates
# Endpoint: GET /api/v1/events/stream (text/event-stream)
```

### 11.3 Redis Pub/Sub

```python
# Channels:
# "backtest:progress:{task_id}" — backtest progress updates
# "optimization:progress:{task_id}" — optimization progress
# "kline:update:{symbol}:{interval}" — real-time kline updates
# "agent:event:{session_id}" — AI agent events

# Pattern:
# Publisher: engine/optimizer pushes progress
# Subscriber: API WebSocket handler relays to client
```

### 11.4 Bybit WebSocket (Live Data)

```python
# backend/services/adapters/bybit.py
# Streams:
#   kline.{interval}.{symbol}   — candle updates
#   tickers.{symbol}            — price ticker
#   orderbook.{depth}.{symbol}  — order book

# Auto-reconnect with exponential backoff
# Ping/pong heartbeat (30s interval)
# Max subscriptions per connection: 10
```

---

## 12. Middleware Pipeline

**Файл:** `backend/api/middleware_setup.py`
**Порядок ФИКСИРОВАН** — менять только с пониманием последствий:

```python
# Порядок применения (outer → inner):
1. RequestIDMiddleware         # X-Request-ID header для трейсинга
2. TimingMiddleware            # Логирует время обработки запроса
3. GZipMiddleware(min_size=500)# Сжатие ответов > 500 bytes
4. TrustedHostMiddleware       # Проверка Host header
5. HTTPSRedirectMiddleware     # HTTP → HTTPS (prod only)
6. CORSMiddleware              # CORS headers (allow_all in dev)
7. RateLimitMiddleware         # 120 req/min per IP
8. CSRFMiddleware              # CSRF protection (POST/PUT/DELETE)
9. SecurityHeadersMiddleware   # X-Frame-Options, CSP, etc.
10. ErrorHandlerMiddleware     # Global exception → JSON error response
```

---

## 13. Движки бэктестинга

### 13.1 FallbackEngineV4 (Gold Standard)

```
Файл: backend/backtesting/engines/fallback_engine_v4.py (3204 строк)
Статус: ЭТАЛОН — все остальные движки проверяются по нему

Возможности:
├─ Multi-level TP (TP1-TP4) с partial exits
├─ ATR-based dynamic SL/TP
├─ Trailing Stop (activation + offset)
├─ DCA Safety Orders (martingale modes)
├─ Breakeven movement
├─ Time-based exits
├─ Market type filters (spot/linear)
├─ Bar magnifier (intrabar SL/TP detection)
├─ Pyramiding (max concurrent entries, close rules)
├─ Direction filtering (long/short/both)
└─ Commission: trade_value × 0.0007 (on margin, NOT on leveraged)
```

### 13.2 NumbaEngineV2 (JIT Optimized)

```
Файл: backend/backtesting/numba_engine.py (~1000 строк)
Статус: 100% parity с V4, 20-40x быстрее
Используется: ТОЛЬКО для optimization loops (Optuna n_trials)
Ограничения: не поддерживает все advanced features V4
```

### 13.3 DCAEngine

```
Файл: backend/backtesting/engines/dca_engine.py
Статус: автоматически выбирается если dca_enabled=True
Override: перехватывает engine_type, даже если запрошен другой
```

### 13.4 SignalResult контракт

```python
@dataclass
class SignalResult:
    entries: pd.Series         # bool — long entry signals
    exits: pd.Series           # bool — long exit signals
    short_entries: pd.Series | None  # bool — short entries
    short_exits: pd.Series | None    # bool — short exits
    entry_sizes: pd.Series | None    # float — DCA order sizes
    short_entry_sizes: pd.Series | None
    extra_data: dict | None

# ВСЕ Series должны иметь тот же index что и input DataFrame
```

---

## 14. Метрики

### MetricsCalculator — единый источник истины

```
Файл: backend/core/metrics_calculator.py
Количество: 166 метрик (TV-parity)
Правило: ВСЕ движки делегируют метрики сюда — НИКОГДА не реализовывать отдельно
```

### Key Metrics

| Метрика           | Формула                                 | Direction | Формат                |
| ----------------- | --------------------------------------- | --------- | --------------------- |
| `net_profit`      | sum(trade_pnl)                          | higher ↑  | $                     |
| `total_return`    | net_profit / initial_capital × 100      | higher ↑  | %                     |
| `max_drawdown`    | max peak-to-trough                      | lower ↓   | % (17.29 = 17.29%)    |
| `sharpe_ratio`    | (mean_ret - rf/12) / std_ret × √12      | higher ↑  | ratio                 |
| `sortino_ratio`   | (mean_ret - rf/12) / downside_std × √12 | higher ↑  | ratio                 |
| `calmar_ratio`    | total_return / max_drawdown             | higher ↑  | ratio                 |
| `win_rate`        | wins / total × 100                      | higher ↑  | %                     |
| `profit_factor`   | gross_profit / gross_loss               | higher ↑  | ratio (inf if loss=0) |
| `expectancy`      | avg expected profit per trade           | higher ↑  | $                     |
| `recovery_factor` | net_profit / max_drawdown               | higher ↑  | ratio                 |
| `commission_paid` | sum of all commissions                  | —         | $                     |

### Известные TV-дивергенции (НЕ баги — документированы)

- RSI Wilder smoothing: ±4 trades из-за 500-bar warmup limit
- Bar magnifier: O-HL heuristic path vs TV's exact tick replay
- Funding rate: linear vs spot price difference

---

## 15. AI Agent System

### 15.1 LangGraph Pipeline

```
analyze_market → [debate] → generate_strategies → parse_responses
                      ↑                                  │
                      │                            select_best
               refine_strategy ←               build_graph
               (iter < 3, fails)                    │
                                               backtest
                                                  ├── fails, iter < 3 → refine_strategy
                                                  └── passes / max iter → memory_update → report
```

### 15.2 LLM Providers

| Provider   | Model             | Usage                         | Key                  |
| ---------- | ----------------- | ----------------------------- | -------------------- |
| DeepSeek   | V3.2              | Strategy generation, analysis | `DEEPSEEK_API_KEY`   |
| Qwen       | Alibaba DashScope | Alternative generation        | `QWEN_API_KEY`       |
| Perplexity | —                 | Market research               | `PERPLEXITY_API_KEY` |

### 15.3 Refinement Loop

```python
# Критерии прохода (backtest_passes):
# - trades ≥ 5
# - sharpe_ratio > 0
# - max_drawdown < 30%

# Guard (should_refine):
# - iteration < MAX_REFINEMENTS (3)
# - backtest failed criteria

# RefinementNode:
# - Создаёт feedback prompt с диагнозом
# - Очищает устаревшие результаты
# - Инкрементирует iteration counter
```

### 15.4 MCP Status

```
MCP отключён — все агенты в direct API mode:
FORCE_DIRECT_AGENT_API=1
MCP_DISABLED=1
```

---

## 16. Инфраструктура Claude Code

### 16.1 Hooks (`.claude/hooks/`)

| Hook                       | Event                     | Trigger                | Action                            |
| -------------------------- | ------------------------- | ---------------------- | --------------------------------- |
| `protect_files.py`         | PreToolUse (Edit\|Write)  | Before any edit        | Защита критических файлов         |
| `ruff_format.py`           | PostToolUse (Edit\|Write) | After edit             | Auto-format ruff                  |
| `post_edit_tests.py`       | PostToolUse (Edit\|Write) | After Python edit      | Run targeted pytest               |
| `post_tool_failure.py`     | PostToolUseFailure        | Any tool failure       | Error analysis                    |
| `post_compact_context.py`  | PostCompact               | Mid-session compaction | Re-inject constants + Memory Bank |
| `session_start_context.py` | SessionStart              | Session start          | Load Memory Bank                  |
| `stop_reminder.py`         | Stop                      | Session end            | Remind to update docs             |

### 16.2 Slash Commands (`.claude/commands/`)

| Command          | Description                   |
| ---------------- | ----------------------------- |
| `/backtest`      | Run backtest with parsed args |
| `/parity-check`  | Verify TradingView parity     |
| `/debug`         | Structured debug session      |
| `/new-strategy`  | Create new strategy           |
| `/optimize`      | Run optimization              |
| `/changelog`     | Update CHANGELOG.md           |
| `/review`        | Code review                   |
| `/tdd`           | Test-driven development       |
| `/update-memory` | Update memory-bank            |
| `/profile`       | Performance profiling         |

### 16.3 Memory Bank (`memory-bank/`)

| File                | Update freq      | Contents                     |
| ------------------- | ---------------- | ---------------------------- |
| `projectBrief.md`   | Rarely           | Goals, invariants            |
| `productContext.md` | Rarely           | Problem, users, constraints  |
| `systemPatterns.md` | On arch changes  | Data flow, patterns, traps   |
| `techContext.md`    | On stack changes | Stack, environment, commands |
| `activeContext.md`  | **Often**        | Current work, next steps     |
| `progress.md`       | **Often**        | What works, bugs, debt       |

**Правило:** После значительной задачи обнови `activeContext.md` и `progress.md`.

### 16.4 Sub-directory CLAUDE.md

```
backend/backtesting/CLAUDE.md    — Engine hierarchy, adapter, SignalResult
backend/api/CLAUDE.md            — Router patterns, direction trap, async rules
backend/optimization/CLAUDE.md   — Optimizer details, scoring, known issues
frontend/CLAUDE.md               — No-build rule, commission conversion, CSS
```

**Ограничение:** Sub-dir CLAUDE.md загружаются ТОЛЬКО при чтении файлов из директории (не при старте сессии).

### 16.5 Permissions (`.claude/settings.json`)

```json
// ALLOW:
git status/diff/log/add/commit/branch/checkout/stash/show
pytest, python main.py, ruff check/format, alembic, npx
Read/Glob/Grep/Edit/Write (all files)

// DENY:
rm, del, git push --force, git reset --hard
DROP, curl | bash
```

---

## 17. Критические инварианты

### ❌ НИКОГДА:

1. **commission_value ≠ 0.0007** — ломает TradingView parity, 12+ файлов
2. **Метрики вне MetricsCalculator** — реализация метрик в движке → рассинхрон
3. **Entry на баре сигнала** — вход ТОЛЬКО на open СЛЕДУЮЩЕГО бара
4. **Commission на leveraged value** — commission = trade_value × 0.0007, НЕ × leverage
5. **Hardcode DATA_START_DATE** — всегда import из `database_policy.py`
6. **Real API в unit tests** — всегда mock через `mock_adapter`
7. **Удалять high-risk переменные** без grep по всем файлам

### ⚠️ Ловушки:

1. **Direction default:** API = "long", Engine = "both", Frontend = "both" → пропущенные short сигналы
2. **Position size units:** engine = fraction (0.0-1.0), live = percent (0-100)
3. **Leverage default:** optimization/UI = 10, live/engine = 1.0
4. **DCA percents:** `dca_grid_size_percent` в ПРОЦЕНТАХ (1.0 = 1%), остальные risk params в DECIMAL (0.0007 = 0.07%)
5. **Port aliases:** если alias не найден → сигнал ТИХО теряется
6. **Max backtest:** 730 дней (2 года) — Pydantic validator

### ✅ ВСЕГДА:

1. `ruff check . --fix && ruff format .` перед коммитом
2. `pytest tests/ -v -m "not slow"` перед коммитом
3. Commission parity grep перед коммитом с commission
4. Обнови `CHANGELOG.md` при notable changes
5. Обнови `memory-bank/activeContext.md` после значительной работы

---

## 18. Рефакторинг Чеклист

### Pre-flight

- [ ] Read §5 (Кросс-системные переменные)
- [ ] `grep -rn <symbol> backend/ frontend/` — count ALL usages
- [ ] Check if symbol is in cross-cutting table → plan multi-file update
- [ ] Read `docs/DECISIONS.md` for prior ADRs

### High-risk parameter changes

If touching `commission_rate`, `initial_capital`, `position_size`, `leverage`, `pyramiding`, `direction`:

- [ ] Update `BacktestConfig` (`models.py`)
- [ ] Update bridges (`backtest_bridge.py`, `walk_forward_bridge.py`)
- [ ] Update optimization (`optimization/models.py`, `optimization/utils.py`)
- [ ] Update engine (`engine.py`) if default/semantics change
- [ ] Update `MetricsCalculator` if dependent
- [ ] Update frontend (`strategy_builder.js`, `leverageManager.js`)
- [ ] Update agent tools (`agents/mcp/tools/backtest.py`, `api/routers/agents.py`)
- [ ] Run commission parity check
- [ ] Run: `pytest tests/backend/backtesting/test_engine.py tests/backend/backtesting/test_strategy_builder_parity.py -v`

### Engine changes

- [ ] `engine_selector.py` routing still correct
- [ ] All metrics via `MetricsCalculator.calculate_all()` — never reimplement
- [ ] If new engine type → update `ENGINE_MAP` + `EngineType` enum
- [ ] Run: `pytest tests/backend/backtesting/test_engine.py -v`

### Strategy / Adapter changes

- [ ] `generate_signals()` returns DataFrame with `signal` column (1/-1/0)
- [ ] `SignalResult` contract: entries, exits, short_entries, short_exits
- [ ] Indicator periods clamped [1, 500] via `_clamp_period()`
- [ ] Port alias fallback works (`long↔bullish`, `short↔bearish`)
- [ ] Run: `pytest tests/backend/backtesting/ -v -m "not slow"`

### API / Router changes

- [ ] Direction default caveat: "long" in BacktestCreateRequest vs "both" in BacktestConfig
- [ ] Date range ≤ 730 days
- [ ] Async DB: `asyncio.to_thread()` for SQLite
- [ ] Swagger renders: `http://localhost:8000/docs`

### Frontend changes

- [ ] No build step — pure ES modules
- [ ] Commission UI (percent 0.07) → backend (decimal 0.0007)
- [ ] Leverage slider ≤ 125, color-coded
- [ ] All params through Properties panel → `strategy_params` dict

### Post-flight

- [ ] `ruff check . --fix && ruff format .`
- [ ] `pytest tests/ -v -m "not slow"` — all green
- [ ] Update `CHANGELOG.md`
- [ ] Update `CLAUDE.md` / `CLAUDE_CODE.md` if structural change
- [ ] Update `memory-bank/activeContext.md`
- [ ] Commit with descriptive message

---

## 19. Live Trading Subsystem

### 19.1 Архитектура

```
backend/services/live_trading/          # Production live trading
├── strategy_runner.py   (821 строк)   # Main orchestrator
├── order_executor.py                   # Bybit order placement
├── position_manager.py                 # Open position tracking
├── bybit_websocket.py                  # Real-time market data
├── graceful_shutdown.py                # Safe shutdown with open positions

backend/trading/                        # Lower-level trading primitives
├── order_executor.py    (354 строк)   # Order dataclass + execution logic
├── paper_trading.py                    # Simulated execution (no real orders)
├── position_tracker.py                 # Position state machine
├── risk_limits.py                      # Pre-trade risk checks
├── circuit_breakers.py                 # Emergency halt
└── websocket_client.py                 # Generic WS client
```

### 19.2 Ключевые классы

| Класс                  | Файл                               | Описание                                                            |
| ---------------------- | ---------------------------------- | ------------------------------------------------------------------- |
| `StrategyRunner`       | `live_trading/strategy_runner.py`  | Главный оркестратор: WebSocket → signal → order → position tracking |
| `OrderExecutor`        | `live_trading/order_executor.py`   | Bybit REST API execution, retry, partial fill handling              |
| `PositionManager`      | `live_trading/position_manager.py` | Tracks open positions, calculates unrealized PnL                    |
| `BybitWebSocketClient` | `live_trading/bybit_websocket.py`  | Real-time klines + trades stream                                    |
| `TradingSignal`        | `strategy_runner.py`               | Signal dataclass: type, symbol, price, qty, SL/TP, confidence       |
| `Order`                | `trading/order_executor.py`        | Order dataclass: Market/Limit, Buy/Sell, status tracking            |

### 19.3 Signal Flow

```
WebSocket (kline/trade) → parse_kline_message()
    → Strategy.generate_signals(df) → TradingSignal
        → RiskEngine.assess_trade() → approved?
            → OrderExecutor.place_order(Order)
                → PositionManager.track()
                    → StopLossManager.monitor()
```

### 19.4 ⚠️ Ловушки

- **commission_rate** = 0.0007 в `TradingConfig` — НЕ менять
- **position_size units:** live = absolute qty, engine = fraction 0-1 — конвертировать!
- **GracefulShutdown**: при SIGTERM закрывает все открытые позиции перед выходом
- **Paper trading** (`paper_trading.py`) НЕ отправляет реальные ордера — проверь mode перед деплоем

---

## 20. Risk Management

### 20.1 Архитектура

```
backend/services/risk_management/
├── risk_engine.py          (768 строк)  # Unified risk management
├── exposure_controller.py  (669 строк)  # Position/portfolio limits
├── position_sizing.py      (525 строк)  # Sizing methods
├── stop_loss_manager.py    (548 строк)  # SL strategies
└── trade_validator.py      (688 строк)  # Pre-trade validation
```

### 20.2 RiskEngine — центральный координатор

```python
RiskEngine(config: RiskEngineConfig)
    ├── ExposureController    # Лимиты экспозиции
    ├── PositionSizer         # Размер позиции
    ├── StopLossManager       # Управление стоп-лоссами
    └── TradeValidator        # Пре-trade проверки
```

### 20.3 Position Sizing Methods

| Метод            | Enum               | Описание                               |
| ---------------- | ------------------ | -------------------------------------- |
| Fixed Percentage | `FIXED_PERCENTAGE` | Фиксированный % equity per trade       |
| Kelly Criterion  | `KELLY_CRITERION`  | Оптимальный по win rate + payoff ratio |
| Half Kelly       | `HALF_KELLY`       | 50% Kelly — консервативнее             |
| Volatility (ATR) | `VOLATILITY_BASED` | Размер по волатильности                |
| Fixed Fractional | `FIXED_FRACTIONAL` | Фиксированная доля equity              |
| Optimal f        | `OPTIMAL_F`        | Максимизация geometric growth          |

### 20.4 Stop Loss Types

| Тип        | Enum               | Описание                    |
| ---------- | ------------------ | --------------------------- |
| Fixed      | `FIXED`            | Фиксированный % от entry    |
| Trailing   | `TRAILING`         | Следует за ценой            |
| Trailing % | `TRAILING_PERCENT` | Trailing по процентам       |
| Breakeven  | `BREAKEVEN`        | Переход в безубыток при +X% |
| ATR-based  | `ATR_BASED`        | По ATR × multiplier         |
| Chandelier | `CHANDELIER`       | Chandelier exit             |
| Time-based | `TIME_BASED`       | Закрытие по времени         |

### 20.5 Exposure Limits (defaults)

```python
max_position_size_pct = 20.0     # Max 20% equity per position
max_total_exposure_pct = 200.0   # Max 200% total (allows 2x leverage)
max_leverage = 10.0              # Max 10x per position
max_portfolio_leverage = 3.0     # Max 3x portfolio
max_correlated_positions = 3     # Max positions with >0.7 correlation
max_drawdown_pct = 20.0          # Auto-stop at 20% drawdown
daily_loss_limit_pct = 5.0       # Daily loss cap
```

### 20.6 Trade Rejection Reasons

`RejectionReason` enum (18 причин): `INSUFFICIENT_BALANCE`, `POSITION_SIZE_EXCEEDED`, `EXPOSURE_LIMIT_EXCEEDED`, `LEVERAGE_LIMIT_EXCEEDED`, `DAILY_LOSS_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_LIMIT`, `SYMBOL_BLOCKED`, `TRADING_PAUSED`, `INVALID_ORDER_PARAMS`, `MIN_ORDER_SIZE`, `MAX_ORDER_SIZE`, `PRICE_OUT_OF_RANGE`, `MARGIN_REQUIREMENT`, `RISK_REWARD_RATIO`, `STRATEGY_LIMIT`, `COOLDOWN_ACTIVE`, `MAX_TRADES_REACHED`

---

## 21. Agent Memory System

### 21.1 Архитектура

```
backend/agents/memory/
├── hierarchical_memory.py  (997 строк)  # 4-tier cognitive memory
├── sqlite_backend.py       (462 строк)  # Persistent storage (WAL mode)
├── vector_store.py         (602 строк)  # ChromaDB semantic search
├── bm25_ranker.py          (203 строк)  # BM25 keyword ranking
├── auto_tagger.py          (292 строк)  # Auto-tag generation
├── tag_normalizer.py                     # Tag dedup + normalization
├── shared_memory.py                      # Cross-agent shared store
└── backend_interface.py                  # Abstract storage interface
```

### 21.2 4-Tier Memory Model (inspired by ACT-R / LIDA)

| Tier | Type         | Max Items | TTL       | Use Case                         |
| ---- | ------------ | --------- | --------- | -------------------------------- |
| 1    | `WORKING`    | 10        | Short     | Current context, active analysis |
| 2    | `EPISODIC`   | 1,000     | Medium    | Session-specific experiences     |
| 3    | `SEMANTIC`   | 10,000    | Long      | Generalized knowledge, facts     |
| 4    | `PROCEDURAL` | 500       | Very long | Learned skills, patterns         |

### 21.3 MemoryItem (unified dataclass)

```python
@dataclass
class MemoryItem:
    id: str                          # content hash + timestamp
    content: str                     # Text content
    memory_type: MemoryType          # WORKING/EPISODIC/SEMANTIC/PROCEDURAL
    agent_namespace: str = "shared"  # Per-agent isolation
    importance: float = 0.5          # 0.0-1.0 relevance
    embedding: list[float] | None    # 384-dim MiniLM vector
    tags: list[str]                  # Normalized tags
    source: str | None               # Origin (agent name, etc.)
    related_ids: list[str]           # Cross-references
```

### 21.4 Retrieval Pipeline

```
Query → BM25Ranker (keyword) ─┐
                                ├→ Hybrid score → Rank → Top-K
Query → VectorStore (semantic) ┘
          ChromaDB + MiniLM-L6-v2 (384-dim)
```

### 21.5 SQLite Backend

- **WAL mode** for concurrent reads
- **Schema v2** — unified MemoryItem fields
- Auto-migration from v1 (float timestamps → ISO-8601)
- Indexes: `memory_type`, `(namespace, type)`, `importance`
- TTL-based expiration + LRU eviction

### 21.6 ⚠️ Ловушки

- `agent_namespace = "shared"` — доступно ВСЕМ агентам; для изоляции указывай имя агента
- `embedding` = None при отсутствии ChromaDB/sentence-transformers — fallback на BM25
- `_SQLITE_TS_FMT = "%Y-%m-%d %H:%M:%S"` — ОБЯЗАТЕЛЬНО space separator (не 'T')

---

## 22. Agent Consensus & Debate

### 22.1 Архитектура

```
backend/agents/consensus/
├── consensus_engine.py       (896 строк)  # Strategy-level aggregation
├── deliberation.py           (1411 строк) # Multi-agent text debate
├── domain_agents.py                        # Specialized domain perspectives
├── real_llm_deliberation.py                # LLM-backed debate rounds
├── risk_veto_guard.py        (297 строк)  # Post-consensus safety override
└── perplexity_integration.py               # External market research
```

### 22.2 ConsensusEngine — strategy aggregation

3 метода:

| Метод                  | Описание                                                       |
| ---------------------- | -------------------------------------------------------------- |
| `weighted_voting`      | Signal-level aggregation by agent weight (performance history) |
| `bayesian_aggregation` | Prior × likelihood update based on historical accuracy         |
| `best_of`              | Pick single best strategy by heuristic score                   |

```python
engine = ConsensusEngine()
engine.update_performance("deepseek", sharpe=1.8, win_rate=0.55)
result = engine.aggregate({"deepseek": s1, "qwen": s2}, method="weighted_voting")
# result.agreement_score → 0.85 (Jaccard similarity)
```

### 22.3 Deliberation — multi-agent text debate

4 фазы:

1. **Initial Opinion** — каждый агент формулирует позицию
2. **Cross-Examination** — агенты критикуют друг друга
3. **Refinement** — обновление позиций на основе feedback
4. **Final Vote** — consensus decision с confidence scoring

Voting strategies: `MAJORITY`, `WEIGHTED`, `UNANIMOUS`, `RANKED_CHOICE`, `SUPERMAJORITY`

### 22.4 RiskVetoGuard — last line of defense

```python
# Veto conditions (ANY triggers block):
max_drawdown_pct = 5.0       # Block if drawdown > 5%
max_open_positions = 5        # Block if too many positions
daily_loss_limit_pct = 3.0    # Block if daily loss exceeded
emergency_stop = False        # Manual kill switch
min_agreement_score = 0.3     # Block if agents strongly disagree
```

**КРИТИЧНО:** VetoGuard работает ПОСЛЕ consensus — это mandatory post-filter, не soft recommendation.

---

## 23. Agent Self-Improvement

### 23.1 Архитектура

```
backend/agents/self_improvement/
├── feedback_loop.py         (687 строк)  # Backtest → reflect → improve cycle
├── strategy_evolution.py    (772 строк)  # Autonomous evolution pipeline
├── self_reflection.py                     # Heuristic-based analysis
├── llm_reflection.py        (471 строк)  # LLM-backed deep reflection
├── pattern_extractor.py     (413 строк)  # Discover winning patterns from history
├── rlhf_module.py           (782 строк)  # RLHF/RLAIF preference learning
├── performance_evaluator.py               # Fitness scoring
└── agent_tracker.py                       # Agent performance tracking
```

### 23.2 Evolution Pipeline

```
Generate Strategy (LLM)
    → Backtest (FallbackEngineV4)
        → Reflect (LLM analysis)
            → Extract Patterns
                → RLHF Rank (A vs B)
                    → Improve Prompt
                        → Generate New Strategy ↺
                            (until convergence or max iterations)
```

### 23.3 FeedbackLoop

```python
class FeedbackLoop:
    """Cycle: backtest → analysis → prompt improvement"""
    async def run(self, strategy, data, max_iterations=5):
        for i in range(max_iterations):
            metrics = await self.backtest(strategy)
            reflection = await self.reflect(metrics)
            improvements = self.extract_improvements(reflection)
            strategy = await self.improve(strategy, improvements)
            if self.converged(metrics):
                break
```

### 23.4 RLHF Module

- **Preference types:** `HUMAN`, `AI` (RLAIF), `SELF`, `CONSENSUS`
- **Response quality:** 1-5 scale (UNACCEPTABLE → EXCELLENT)
- Collects A/B preference pairs, trains reward model
- References: Ouyang et al. 2022, Constitutional AI (Anthropic 2023)

### 23.5 PatternExtractor

Анализирует backtest history → извлекает паттерны:

- Лучшие стратегии по символам/таймфреймам
- Оптимальные parameter ranges
- Market-regime корреляции
- Win-rate/Sharpe distribution по конфигурациям

---

## 24. Security Layer

### 24.1 Agent Security (prompt injection protection)

```
backend/agents/security/
├── security_orchestrator.py  (214 строк)  # Fusion of all guards
├── prompt_guard.py           (235 строк)  # Regex-based detection
├── semantic_guard.py         (258 строк)  # Semantic analysis
├── strategy_validator.py                    # Strategy output validation
├── output_validator.py                      # LLM output sanitization
└── rate_limiter.py                          # Per-agent rate limiting
```

### 24.2 SecurityOrchestrator — fusion policy

3 policy:

- `BLOCK_ANY` — block if ANY guard flags (strictest)
- `BLOCK_ALL` — block only if ALL guards agree
- `WEIGHTED` — block based on weighted score threshold (default)

### 24.3 PromptGuard — regex layer

Детектирует 5 категорий угроз:

- `DIRECT_INJECTION` — "ignore all previous instructions"
- `ROLE_MANIPULATION` — "you are now a..."
- `DATA_EXFILTRATION` — "print your system prompt"
- `JAILBREAK` — known jailbreak patterns
- `ENCODING_ATTACK` — base64, hex, unicode tricks

### 24.4 SemanticGuard — 3-layer analysis

1. **Layer 1:** Fast regex patterns (existing)
2. **Layer 2:** Keyword density + role confusion heuristics
3. **Layer 3:** Structure analysis (suspicious formatting)

### 24.5 Backend Security (key management)

```
backend/security/
├── crypto.py                (322 строк)  # AES-256-GCM encryption
├── hsm_provider.py                        # HSM integration
├── shamir_sharing.py                      # Shamir's Secret Sharing
├── master_key_manager.py                  # Master key lifecycle
├── key_manager.py                         # API key CRUD
├── memory_protection.py                   # Secure memory handling
└── api_key_rotation.py                    # Auto-rotation
```

### 24.6 Crypto Module

- **AES-256-GCM** authenticated encryption (NIST recommended)
- **Argon2id** key derivation for password-based keys
- `SecureBytes` — auto-zeroing secure container (prevents accidental logging)
- Backward compatible with legacy `ENCRYPTED:` format

---

## 25. ML/RL Subsystem

### 25.1 Архитектура

```
backend/ml/
├── regime_detection.py       (501 строк)  # Market regime detection
├── rl_trading_agent.py       (820 строк)  # DQN/PPO trading agents
├── ai_backtest_executor.py                 # ML-driven backtest
├── ai_feature_engineer.py                  # Feature extraction
├── mlflow_adapter.py                       # MLflow experiment tracking
├── news_nlp_analyzer.py                    # News sentiment NLP
├── enhanced/                               # Enhanced ML models
└── rl/
    ├── trading_env.py        (597 строк)  # Gymnasium RL environment
    ├── rewards.py                          # Reward functions
    └── wrapper.py                          # Env wrappers

backend/rl/                               # Standalone RL module
├── trading_env.py
└── rewards.py, wrapper.py
```

### 25.2 Regime Detection

3 алгоритма:

- **KMeans** — быстрый, simple clustering
- **Gaussian Mixture Model** (GMM) — probabilistic clustering
- **Hidden Markov Model** (HMM) — temporal transitions

6 режимов: `BULL_LOW_VOL`, `BULL_HIGH_VOL`, `BEAR_LOW_VOL`, `BEAR_HIGH_VOL`, `SIDEWAYS`, `UNKNOWN`

### 25.3 RL Trading Agent

| Agent | Алгоритм                     | Описание                            |
| ----- | ---------------------------- | ----------------------------------- |
| DQN   | Deep Q-Network               | Experience replay + target networks |
| PPO   | Proximal Policy Optimization | Policy gradient с clipping          |

Actions: `HOLD(0)`, `BUY(1)`, `SELL(2)`, `CLOSE(3)`

### 25.4 Trading Environment (Gymnasium-compatible)

```python
TradingConfig:
    initial_balance = 10000.0
    commission_rate = 0.0007    # ⚠️ MUST match TradingView parity
    max_position_size = 1.0
    leverage = 1.0
    slippage = 0.0001

# Register: gymnasium.make("TradingEnv-v1")
```

Reward functions: `pnl`, `log_return`, `sharpe`, `sortino`, `calmar`, `drawdown_penalty`

### 25.5 Зависимости (опциональные)

```python
SKLEARN_AVAILABLE   # sklearn — regime detection
HMM_AVAILABLE       # hmmlearn — HMM regime detection
GYM_AVAILABLE       # gymnasium/gym — RL environment
RAY_AVAILABLE       # ray — distributed computing
```

**⚠️ Все ML зависимости опциональны** — graceful fallback при ImportError.

---

## 26. Monte Carlo & Walk-Forward

### 26.1 Monte Carlo Simulation

```python
# backend/services/monte_carlo.py (561 строк)
class MonteCarloSimulator:
    """Statistical robustness analysis via:
    - Trade sequence shuffling (permutation tests)
    - Return distribution bootstrapping
    - Drawdown probability estimation
    - Confidence intervals (VaR, CVaR)
    - Worst-case scenario analysis"""

    def __init__(self, n_simulations=10000):
        ...

    def analyze_strategy(self, backtest_results) -> MonteCarloResult:
        ...

    # Methods:
    # - probability_of_return(target) → float
    # - drawdown_confidence_interval(level) → (lower, upper)
    # - value_at_risk(confidence) → float
    # - conditional_var(confidence) → float
```

### 26.2 Walk-Forward Optimization

```python
# backend/services/walk_forward.py (525 строк)
class WalkForwardOptimizer:
    """Rolling window validation:
    - Train on N bars → test on M bars → slide forward
    - Detects overfitting via out-of-sample degradation
    - Stability metrics for parameter robustness"""

    def __init__(self, n_splits=5, train_ratio=0.7):
        ...

    def optimize(self, data, strategy_class, param_grid, initial_capital=10000):
        ...

    # Key output:
    # - per-window train vs test metrics
    # - stability_score (lower std = more stable)
    # - overfitting_ratio (train_sharpe / test_sharpe)
```

### 26.3 ⚠️ Ловушки

- Walk-forward использует `initial_capital=10000` — должен совпадать с engine default
- Monte Carlo `n_simulations=10000` — на больших trade sets может быть медленным

---

## 27. Monitoring & Observability

### 27.1 Backend Monitoring

```
backend/monitoring/
├── prometheus_exporter.py   (322 строк)  # Prometheus text format export
├── prometheus_metrics.py                   # Metric definitions
├── extended_metrics.py                     # Additional metrics
├── health_checks.py                        # Readiness/liveness probes
├── db_monitor.py                           # SQLite stats monitoring
├── agent_metrics.py                        # AI agent performance metrics
├── cost_tracker.py                         # LLM API cost tracking
├── cost_alerts.py                          # Cost budget alerts
├── alerts/                                 # Alert definitions
├── ab_testing.py                           # A/B test metrics
├── breaker_telemetry.py                    # Circuit breaker telemetry
├── redis_cache.py                          # Redis cache stats
├── self_learning_signal_service.py         # Signal quality feedback
├── prompts_monitor.py                      # Prompt versioning metrics
└── prompt_versioning.py                    # Prompt A/B tracking
```

### 27.2 Agent Monitoring

```
backend/agents/monitoring/
├── metrics_collector.py     # Agent-level metrics
├── system_monitor.py        # System health (CPU, mem, disk)
├── alerting.py              # Alert rule engine
├── dashboard.py             # Real-time dashboard data
├── ml_anomaly.py            # Anomaly detection in metrics
├── prometheus_grafana.py    # Grafana integration
└── tracing.py               # Distributed tracing
```

### 27.3 Prometheus Metrics

| Metric                                       | Type      | Description                  |
| -------------------------------------------- | --------- | ---------------------------- |
| `http_requests_total`                        | counter   | HTTP request count by status |
| `http_request_duration_seconds`              | histogram | Request latency              |
| `ai_agent_requests_total`                    | counter   | LLM API calls by provider    |
| `ai_agent_request_duration_seconds`          | histogram | LLM latency                  |
| `cache_hits_total` / `cache_misses_total`    | counter   | Cache effectiveness          |
| `backtest_total` / `backtest_failures_total` | counter   | Backtest throughput          |
| `cost_usd_total`                             | counter   | LLM API cost accumulation    |

---

## 28. Optimization System (Deep Dive)

### 28.1 Полная структура

```
backend/optimization/
├── optuna_optimizer.py      # Bayesian TPE/CMA-ES (ОСНОВНОЙ)
├── builder_optimizer.py     # Strategy Builder-specific optimization
├── ray_optimizer.py   (464 строк)  # Ray distributed + multiprocessing fallback
├── advanced_engine.py (386 строк)  # Unified interface (regime + walk-forward + optimize)
├── scoring.py               # 20 scoring metrics
├── filters.py         (104 строк)  # Static + dynamic constraint filters
├── recommendations.py       # Auto-recommendations based on results
├── models.py                # OptimizationConfig, result models
├── workers.py               # Background optimization workers
├── utils.py                 # Shared utilities
└── CLAUDE.md                # Sub-directory context
```

### 28.2 Optimizer Hierarchy

```
AdvancedOptimizationEngine (advanced_engine.py)
    ├── OptunaOptimizer        # Bayesian (TPE, CMA-ES)
    ├── RayParallelOptimizer   # Distributed (Ray cluster)
    ├── MultiprocessingOptimizer  # Local multiprocessing fallback
    ├── WalkForwardValidator   # OOS validation
    └── RegimeDetector         # Market context
```

### 28.3 RayParallelOptimizer

- Использует Ray для distributed computing across cores/nodes
- GPU support для hybrid workloads
- Fault tolerance для long-running optimizations
- **Fallback:** `MultiprocessingOptimizer` если Ray недоступен (`RAY_AVAILABLE = False`)

### 28.4 Filters (pre/post optimization)

```python
passes_filters(result, request_params) → bool
# Checks: min_trades, max_drawdown_limit, min_profit_factor, min_win_rate
# + dynamic constraints from frontend EvaluationCriteriaPanel
```

**⚠️ Unit mismatch:** `max_drawdown_limit` в request = fraction (0-1), в result = percentage (0-100)

---

## 29. Frontend Architecture

### 29.1 Модульная структура

```
frontend/js/
├── core/                       # Framework-level modules
│   ├── StateManager.js  (565 строк)  # Redux-like state (subscribe, persist, undo/redo)
│   ├── EventBus.js      (382 строк)  # Pub/sub (namespaced, wildcards, history)
│   ├── Router.js                      # SPA routing (hash-based)
│   ├── ApiClient.js                   # Fetch wrapper + interceptors
│   ├── WebSocketClient.js             # WS reconnect, heartbeat
│   ├── LazyLoader.js                  # Dynamic module loading
│   ├── Logger.js                      # Structured logging
│   ├── SafeDOM.js                     # XSS-safe DOM manipulation
│   ├── Sanitizer.js                   # Input sanitization
│   ├── ServiceLayer.js                # DI container
│   └── PerformanceMonitor.js          # Core Web Vitals

├── components/                 # Reusable UI components
│   ├── AiBuildModule.js               # AI strategy builder widget
│   ├── BacktestModule.js              # Backtest results display
│   ├── ChartManager.js                # TradingView chart integration
│   ├── MetricsPanels.js               # Metric display panels
│   ├── OptimizationHeatmap.js         # Parameter optimization heatmap
│   ├── MonteCarloChart.js             # Monte Carlo distribution chart
│   ├── ParameterSensitivityChart.js   # Param sensitivity visualization
│   ├── TradingViewEquityChart.js      # Equity curve chart
│   ├── TradesTable.js                 # Trade list table
│   ├── SaveLoadModule.js              # Strategy save/load
│   ├── ValidateModule.js              # Strategy validation
│   ├── UndoRedoModule.js              # Undo/redo for graph edits
│   ├── DataTable.js, Form.js, Modal.js, Toast.js, Card.js, Loader.js
│   ├── MLBlocksModule.js             # ML block types
│   ├── OrderFlowBlocksModule.js      # Order flow block types
│   ├── SentimentBlocksModule.js      # Sentiment block types
│   ├── ConnectionsModule.js          # Graph connection management
│   └── MyStrategiesModule.js         # Strategy portfolio view

├── pages/                      # Page-level modules
│   └── strategy_builder.js  (3000+ строк)  # Main strategy builder page

├── strategy_builder/           # Strategy builder sub-modules

├── services/
│   └── liveTrading.js         # Live trading frontend service

├── shared/                    # Shared utilities
├── utils/                     # Helper functions
├── testing/                   # Test infrastructure
└── tests/                     # Frontend tests
```

### 29.2 StateManager (Redux-like)

```javascript
const store = new StateManager({
    user: null, theme: 'dark', settings: {}
}, { persist: true, maxHistory: 50 });

store.subscribe('user', (user) => ...);   // Per-key subscription
store.set('user', { name: 'John' });      // Update state
store.undo();                              // Undo last change
```

### 29.3 EventBus (Pub/Sub)

```javascript
const bus = new EventBus();
bus.on('user:*', (data, event) => ...);   // Wildcard
bus.once('app:ready', () => ...);          // One-time
bus.emit('user:login', { name: 'John' }); // Emit
```

### 29.4 ⚠️ Ловушки

- **Commission conversion:** UI показывает 0.07 (percent) → backend получает 0.0007 (decimal)
- **No build step** — pure ES modules, no webpack/vite
- **Leverage slider** ≤ 125, color-coded по уровню risk
- Все strategy params проходят через Properties panel → `strategy_params` dict

---

## 30. Services Layer (Deep Dive)

### 30.1 Core Services

| Service                | File                     | Lines | Description                     |
| ---------------------- | ------------------------ | ----- | ------------------------------- |
| `DataService`          | `data_service.py`        | —     | Repository pattern for CRUD     |
| `KlineDataManager`     | `kline_manager.py`       | —     | Singleton kline data provider   |
| `SmartKlineService`    | `smart_kline_service.py` | —     | Intelligent kline aggregation   |
| `EventBus`             | `event_bus.py`           | 643   | Redis + local pub/sub messaging |
| `MonteCarloSimulator`  | `monte_carlo.py`         | 561   | Statistical robustness analysis |
| `WalkForwardOptimizer` | `walk_forward.py`        | 525   | Rolling window validation       |

### 30.2 Trading Services

| Service                  | File                         | Description                             |
| ------------------------ | ---------------------------- | --------------------------------------- |
| `PaperTrading`           | `paper_trading.py`           | Simulated execution without real orders |
| `UnifiedTrading`         | `unified_trading/`           | Abstraction over live/paper/backtest    |
| `TradingHalt`            | `trading_halt.py`            | Emergency trading halt                  |
| `TournamentOrchestrator` | `tournament_orchestrator.py` | Strategy tournament/competition         |

### 30.3 Data Quality & Integrity

| Service              | File                      | Description                       |
| -------------------- | ------------------------- | --------------------------------- |
| `DataQualityService` | `data_quality_service.py` | OHLCV quality checks              |
| `DataIntegrity`      | `data_integrity.py`       | Hash-based integrity verification |
| `DataGapRepair`      | `data_gap_repair.py`      | Auto-fill missing candles         |
| `ArchivalService`    | `archival_service.py`     | Data archiving/cleanup            |

### 30.4 Infrastructure Services

| Service               | File                      | Description                     |
| --------------------- | ------------------------- | ------------------------------- |
| `CacheWarming`        | `cache_warming.py`        | Pre-populate caches on startup  |
| `MultiLevelCache`     | `multi_level_cache.py`    | L1 (memory) + L2 (Redis) cache  |
| `RateLimiter`         | `rate_limiter.py`         | API rate limiting               |
| `ServiceRegistry`     | `service_registry.py`     | Service discovery/DI            |
| `GracefulDegradation` | `graceful_degradation.py` | Fallback when services fail     |
| `DistributedLock`     | `distributed_lock.py`     | Redis-based distributed locking |

### 30.5 Reliability & Testing

| Service               | File                      | Description                    |
| --------------------- | ------------------------- | ------------------------------ |
| `ChaosEngineering`    | `chaos_engineering.py`    | Fault injection testing        |
| `SyntheticMonitoring` | `synthetic_monitoring.py` | Synthetic health probes        |
| `PropertyTesting`     | `property_testing.py`     | Property-based test generation |
| `SLOErrorBudget`      | `slo_error_budget.py`     | SLO compliance tracking        |
| `ABTesting`           | `ab_testing.py`           | A/B test framework             |

### 30.6 Security Services

| Service             | File                     | Description                  |
| ------------------- | ------------------------ | ---------------------------- |
| `APIKeyRotation`    | `api_key_rotation.py`    | Auto-rotation of API keys    |
| `GitSecretsScanner` | `git_secrets_scanner.py` | Scan repo for leaked secrets |
| `IPWhitelist`       | `ip_whitelist.py`        | IP allowlist enforcement     |
| `KMSIntegration`    | `kms_integration.py`     | Key Management Service       |
| `SecureConfig`      | `secure_config.py`       | Encrypted configuration      |

### 30.7 LLM Client Architecture

```
backend/agents/llm/
├── base_client.py    (551 строк)  # Abstract base + session management
├── rate_limiter.py   (197 строк)  # Token-aware rate limiting
├── prompt_optimizer.py              # Prompt compression/optimization
├── connections.py                   # Connection pool management
└── clients/
    ├── deepseek.py                  # DeepSeek V3.2
    ├── qwen.py                      # Alibaba DashScope
    ├── perplexity.py                # Market research
    └── ollama.py                    # Local LLM (offline)
```

### 30.8 BaseLLMClient Features

```python
class BaseLLMClient(ABC):
    """All LLM clients inherit from this:
    - aiohttp persistent sessions
    - Token bucket rate limiting (per-provider budgets)
    - Retry with exponential backoff
    - Circuit breaker integration (optional)
    - Usage statistics (tokens, cost, latency)"""

# Supported providers: DEEPSEEK, PERPLEXITY, OPENAI, ANTHROPIC, OLLAMA, QWEN, CUSTOM

# Rate limits:
TokenBudget:
    max_tokens_per_minute = 100_000
    max_tokens_per_hour = 2_000_000
    max_tokens_per_day = 20_000_000
    max_cost_per_hour_usd = 5.0
    max_cost_per_day_usd = 50.0
```

---

## 31. Auxiliary & Experimental Modules

> Вспомогательные модули, не входящие в core-пайплайн, но присутствующие в кодовой базе.
> Большинство — research/experimental стадии или инфраструктурные утилиты.

### 31.1 Celery Task Queue

```
backend/celery_app.py                      (81 строк)   # Конфигурация Celery
backend/tasks/
├── backtest_tasks.py                      (199 строк)  # Celery tasks для бэктестов
├── optimize_tasks.py                      (558 строк)  # Grid search, walk-forward, Bayesian tasks
└── __init__.py
```

**Архитектура:**

```python
celery_app = Celery("backend", broker="redis://127.0.0.1:6379/1", backend="redis://127.0.0.1:6379/2")

# Очереди:
# optimizations.grid  — Grid search tasks
# optimizations.walk  — Walk-forward tasks
# optimizations.bayes — Bayesian optimization tasks
# backtests           — Backtest tasks

# Лимиты:
task_time_limit     = 3600   # 1 час max
task_soft_time_limit = 3300  # 55 мин soft limit
result_expires      = 86400  # Результаты истекают через 24ч

# Reliability:
task_acks_late = True              # Acknowledge после выполнения
task_reject_on_worker_lost = True  # Reject при потере worker
```

**Задачи:**

| Task                           | Queue                | Retries | Описание                          |
| ------------------------------ | -------------------- | ------- | --------------------------------- |
| `run_backtest_task`            | `backtests`          | 3       | Одиночный бэктест с atomic claim  |
| `bulk_backtest_task`           | `backtests`          | 0       | Celery `group()` для параллельных |
| `grid_search_task`             | `optimizations.grid` | 2       | Grid search + progress tracking   |
| `walk_forward_task`            | `optimizations.walk` | 2       | IS/OOS rolling window             |
| `bayesian_optimization_task`   | `optimizations.bayes`| 2       | Optuna-based Bayesian             |

**⚠️ Зависимости:** Требует Redis-брокер. `CELERY_EAGER=1` — синхронный режим для тестов.

### 31.2 Reports & Email

```
backend/reports/
├── generator.py       (317 строк)  # ReportGenerator: HTML/PDF/Email
├── pdf_generator.py   (277 строк)  # PDFGenerator: ReportLab-based PDF
├── email_sender.py    (177 строк)  # EmailSender: SMTP с TLS
└── __init__.py
```

**ReportGenerator** — центральный класс:

```python
class ReportGenerator:
    """Генерирует отчёты по результатам бэктестов"""

    def generate_html(data: ReportData) -> str       # HTML с метриками и графиками
    def generate_pdf(data: ReportData) -> bytes       # Через PDFGenerator (ReportLab)
    async def send_email(data, recipient) -> bool     # Через EmailSender (SMTP)

# ReportData:
#   backtest_id, strategy_name, symbol, timeframe,
#   start_date, end_date, metrics, equity_curve,
#   trades, monthly_returns, optimization_results

# Категории метрик в отчёте:
#   Performance: total_return, annual_return, sharpe_ratio, sortino_ratio, calmar, profit_factor
#   Risk: volatility, max_drawdown, avg_drawdown, VaR 95%, CVaR 95%
#   Trades: total_trades, win_rate, avg_win, avg_loss
#   Timing: avg_trade_duration, market_exposure, turnover
```

**PDFGenerator** — A4/Letter, 3 секции (Summary, Performance Metrics, Risk Metrics, Trade History).
Fallback на простой PDF если ReportLab не установлен.

**EmailSender** — SMTP (по умолчанию Gmail:587), TLS, HTML + PDF attachment. Mock-режим без SMTP credentials.

### 31.3 Social Trading

```
backend/social/
├── copy_trading.py   (200 строк)  # CopyTradingEngine
├── leaderboard.py    (140 строк)  # Leaderboard
├── models.py         (126 строк)  # PublicStrategy, StrategyRating, CopyTrade
└── __init__.py
```

**CopyTradingEngine:**

```python
class CopyTradingEngine:
    """Copy trading — in-memory, NOT production-ready"""

    def start_copy(follower_id, strategy_id, allocation, copy_ratio=1.0, max_positions=10) -> bool
    def stop_copy(follower_id, strategy_id) -> bool
    def copy_trade(strategy_id, trade_data) -> list[CopyPosition]
    def get_follower_positions(follower_id) -> list[CopyPosition]
    def get_copy_stats(follower_id) -> dict

# CopyPosition: original_trade_id, strategy_id, follower_id, symbol, side, quantity, entry_price, copy_ratio, pnl
```

**Leaderboard:**

```python
class Leaderboard:
    """Рейтинги стратегий и трейдеров — in-memory storage"""

    def get_top_traders(by="return"|"sharpe"|"followers", limit=10) -> list[dict]
    def get_top_strategies(by="sharpe"|"return"|"copies"|"rating", limit=10) -> list[dict]
```

**Модели:** `PublicStrategy` (dataclass с followers/copies/rating), `StrategyRating` (1-5 stars + comment), `CopyTrade`.

**⚠️ Статус:** Proof-of-concept. In-memory storage, не персистентный. Нет интеграции с live trading.

### 31.4 Research & Experimental

```
backend/research/
├── explainable_ai.py          (259 строк)  # SHAPExplainer, LIMEExplainer
├── blockchain_verification.py (178 строк)  # BacktestVerifier: SHA-256 proof chain
├── federated_learning.py      (196 строк)  # FederatedLearning: privacy-preserving
├── multi_agent_simulation.py  (253 строк)  # MarketSimulator: multi-agent ABM
├── parameter_adaptation.py    (172 строк)  # ParameterAdapter: regime-based tuning
└── __init__.py
```

| Модуль                     | Класс              | Описание                                                            |
| -------------------------- | ------------------- | ------------------------------------------------------------------ |
| `explainable_ai`           | `SHAPExplainer`     | Simplified SHAP for ML signal interpretation (no real SHAP lib)    |
|                            | `LIMEExplainer`     | LIME-style local linear explanations                               |
| `blockchain_verification`  | `BacktestVerifier`  | SHA-256 hashes → cryptographic proof of backtest integrity         |
| `federated_learning`       | `FederatedLearning` | FedAvg aggregation, N клиентов, global/local weights               |
| `multi_agent_simulation`   | `MarketSimulator`   | ABM: momentum/mean_reversion/market_maker/random/RL agents         |
| `parameter_adaptation`     | `ParameterAdapter`  | Regime-based param tuning (trending/ranging/volatile/calm presets) |

**⚠️ Статус:** Research stubs. Используют simplified алгоритмы (не production SHAP/LIME). Не интегрированы в основной пайплайн.

### 31.5 Experimental: L2 Order Book

```
backend/experimental/l2_lob/
├── models.py                  (74 строки)  # L2Level, L2Snapshot
├── collector.py               (263 строки) # L2OrderBookCollector (WebSocket)
├── websocket_collector.py                  # Alternative WS collector
├── bybit_client.py                         # REST API client for L2
├── replay.py                               # Replay saved snapshots in simulator
├── generative_cgan.py                      # CGAN для синтеза стакана
├── generative_research.py                  # Research: LOB generation
└── README.md                               # Документация модуля
```

**Функционал:**
- **Сбор:** Bybit REST + WebSocket → L2 snapshots (NDJSON)
- **Replay:** `load_snapshots_ndjson()` → `OrderBookSimulator` для бэктеста с L2
- **Generative:** CGAN research для синтеза реалистичного стакана
- **Модели:** `L2Snapshot` (bids/asks, mid_price, spread_bps), совместим с `OrderBookLevel`

**⚠️ Статус:** Experimental. WebSocket к `wss://stream.bybit.com/v5/public/linear`.

### 31.6 Benchmarking

```
backend/benchmarking/
├── performance.py   (511 строк)  # BenchmarkSuite
└── __pycache__/
```

**BenchmarkSuite:**

```python
class BenchmarkSuite:
    """Полный benchmark suite для AI agent system"""

    async def run_benchmark(name, func, iterations=100, warmup=10) -> BenchmarkResult
    async def run_load_test(func, concurrent_users=10, duration=60) -> LoadTestResult
    def set_baseline(name, result) -> None
    def check_regression(name, current, threshold=0.2) -> (is_regression, msg)
    def detect_bottlenecks() -> list[str]
    def generate_recommendations() -> list[str]
    def generate_report() -> BenchmarkReport

# BenchmarkResult: avg_time, min/max, median, std_dev, p95, p99, success_rate
# LoadTestResult: concurrent_users, rps, avg/p95/p99 response, error_rate
# Bottleneck detection: high variance (>50%), tail latency (p99>3×avg), low success (<95%)
```

**Singleton:** `get_benchmark_suite()` — глобальный экземпляр.

### 31.7 Unified API (Backtest ↔ Live)

```
backend/unified_api/
├── interface.py   (243 строки)  # Abstract interfaces
└── __init__.py
```

**Абстракции для переключения backtest ↔ live:**

```python
# DataProvider (ABC)
#   ├── HistoricalDataProvider  — dict[str, DataFrame], для бэктеста
#   └── LiveDataProvider        — WebSocket + current_prices dict

# OrderExecutor (ABC)
#   ├── SimulatedExecutor       — Paper trading (in-memory positions/balance)
#   └── LiveExecutor            — Exchange client (stub)

# TradingSystem (facade):
#   data_provider + order_executor + strategy → run()
```

**⚠️ Статус:** Interface layer. SimulatedExecutor работает, LiveExecutor — stub.

---

## Deprecated (НЕ использовать в новом коде)

| Item                            | Replacement                             |
| ------------------------------- | --------------------------------------- |
| `fast_optimizer.py`             | `optimization/optuna_optimizer.py`      |
| `RSIStrategy` (built-in)        | Universal RSI block in Strategy Builder |
| `BacktestConfig.force_fallback` | `engine_type="fallback"`                |
| `StrategyType.ADVANCED`         | Not implemented — placeholder           |
| `FallbackEngineV2/V3`           | FallbackEngineV4                        |
| `GPUEngineV2`                   | NumbaEngineV2                           |

---

## Приоритет чтения файлов

### Читать ПЕРВЫМ

```
backend/backtesting/models.py           — BacktestConfig (100+ полей)
backend/backtesting/engine.py           — Entry point
backend/core/metrics_calculator.py      — 166 метрик
backend/config/constants.py             — Критические константы
backend/config/database_policy.py       — Даты, retention
```

### Читать ПО НЕОБХОДИМОСТИ

```
backend/backtesting/engines/fallback_engine_v4.py  — Если меняешь engine
backend/backtesting/indicator_handlers.py          — Если добавляешь индикатор
backend/backtesting/strategy_builder/adapter.py    — Если меняешь Builder
backend/services/adapters/bybit.py                 — Если меняешь API
frontend/js/pages/strategy_builder.js              — Если меняешь UI
backend/services/live_trading/strategy_runner.py   — Если меняешь live trading
backend/services/risk_management/risk_engine.py    — Если меняешь risk management
backend/agents/memory/hierarchical_memory.py       — Если меняешь agent memory
backend/agents/consensus/consensus_engine.py       — Если меняешь consensus
backend/agents/self_improvement/feedback_loop.py   — Если меняешь self-improvement
backend/agents/security/security_orchestrator.py   — Если меняешь agent security
backend/optimization/advanced_engine.py            — Если меняешь optimization
backend/ml/regime_detection.py                     — Если меняешь ML pipeline
frontend/js/core/StateManager.js                   — Если меняешь frontend state
```

### Обычно ИГНОРИРОВАТЬ

```
mcp-server/                            — MCP disabled
frontend/dist/                         — Build artifacts
data/archive/                          — Logs
deployment/                            — DevOps (k8s, helm, docker)
backend/research/                      — Research stubs (XAI, federated, blockchain)
backend/social/                        — Copy trading PoC (in-memory)
backend/experimental/                  — L2 LOB (experimental)
```
