# 🤖 Agent Tools & API Reference

> **Last updated:** 2026-02-11  
> **Purpose:** Complete reference for AI agent tools, API endpoints, and integration points

---

## 📋 Table of Contents

1. [MCP Tools](#-mcp-tools)
2. [API Endpoints](#-api-endpoints)
3. [Memory System](#-memory-system)
4. [Security & Validation](#-security--validation)
5. [Sandbox & Resource Limits](#-sandbox--resource-limits)
6. [Usage Examples](#usage-examples)
7. [Constraints & Safety](#%EF%B8%8F-constraints--safety)

---

## 🔧 MCP Tools

Registered in `backend/agents/mcp/trading_tools.py` via `@registry.register()`.

### Backtesting Tools

| Tool                   | Category    | Description                                             |
| ---------------------- | ----------- | ------------------------------------------------------- |
| `run_backtest`         | backtesting | Execute a strategy backtest with full parameter control |
| `get_backtest_metrics` | backtesting | Retrieve metrics for completed backtests from DB        |
| `list_strategies`      | backtesting | List all available strategies with default parameters   |
| `validate_strategy`    | backtesting | Validate strategy params before running                 |
| `evolve_strategy`      | backtesting | AI-powered iterative strategy evolution via LLM         |

### Technical Indicator Tools

| Tool                        | Category   | Description                     |
| --------------------------- | ---------- | ------------------------------- |
| `calculate_rsi`             | indicators | Calculate RSI for a symbol      |
| `calculate_macd`            | indicators | Calculate MACD with signal line |
| `calculate_bollinger_bands` | indicators | Calculate Bollinger Bands       |
| `calculate_atr`             | indicators | Calculate Average True Range    |
| `calculate_stochastic`      | indicators | Calculate Stochastic Oscillator |

### Analysis Tools

| Tool                         | Category | Description                                        |
| ---------------------------- | -------- | -------------------------------------------------- |
| `analyze_support_resistance` | analysis | Find support/resistance levels                     |
| `calculate_risk_reward`      | risk     | Calculate risk/reward ratio                        |
| `generate_backtest_report`   | analysis | Generate structured markdown/JSON backtest reports |

### Monitoring Tools

| Tool                  | Category   | Description                                     |
| --------------------- | ---------- | ----------------------------------------------- |
| `check_system_health` | monitoring | Check database, disk, memory, data availability |
| `log_agent_action`    | monitoring | Log agent activity for audit trail              |

---

### Tool Details

#### `run_backtest`

```python
result = await run_backtest(
    symbol="BTCUSDT",           # Trading pair
    interval="15",              # Timeframe: 1,5,15,30,60,240,D,W,M
    strategy_type="rsi",        # Strategy name
    strategy_params={           # Strategy-specific params
        "period": 14,
        "overbought": 70,
        "oversold": 30
    },
    start_date="2025-06-01",    # YYYY-MM-DD (not before 2025-01-01)
    end_date="2025-07-01",      # YYYY-MM-DD
    initial_capital=10000.0,    # 100 — 100M USDT
    leverage=10.0,              # 1 — 125x
    direction="both",           # long, short, both
    stop_loss=0.02,             # fraction (2%)
    take_profit=0.03,           # fraction (3%)
)
# Returns: {status, total_trades, win_rate, total_return_pct, sharpe_ratio, ...}
```

#### `get_backtest_metrics`

```python
# Get specific backtest
result = await get_backtest_metrics(backtest_id=42)
# Returns: {id, symbol, strategy_type, win_rate, total_return, sharpe_ratio, ...}

# List recent backtests
result = await get_backtest_metrics(backtest_id=None, limit=10)
# Returns: {count, backtests: [{id, symbol, strategy_type, ...}, ...]}
```

#### `validate_strategy`

```python
result = await validate_strategy(
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    leverage=50.0,
    stop_loss=0.01,
    take_profit=0.03,
)
# Returns: {is_valid, errors: [], warnings: [], strategy_type, params_checked}
```

#### `check_system_health`

```python
result = await check_system_health()
# Returns: {
#     overall: "healthy"|"degraded",
#     components: {database, disk, memory, data_db},
#     warnings: [...]
# }
```

---

## 🌐 API Endpoints

All endpoints are under the `/api/v1/agents/` prefix.

### Agent Action Endpoints (NEW)

| Method | Path                                | Description                           |
| ------ | ----------------------------------- | ------------------------------------- |
| `POST` | `/agents/actions/run-backtest`      | Execute a backtest via agent pipeline |
| `GET`  | `/agents/actions/backtest-history`  | Get recent backtest results           |
| `GET`  | `/agents/actions/strategies`        | List available strategies             |
| `POST` | `/agents/actions/validate-strategy` | Validate strategy parameters          |
| `GET`  | `/agents/actions/system-health`     | System health check                   |
| `GET`  | `/agents/actions/tools`             | List all registered MCP tools         |

### Existing Agent Endpoints

| Method | Path                          | Description                               |
| ------ | ----------------------------- | ----------------------------------------- |
| `GET`  | `/agents/stats`               | Agent statistics (keys, requests, errors) |
| `POST` | `/agents/query/deepseek`      | Query DeepSeek AI                         |
| `POST` | `/agents/query/perplexity`    | Query Perplexity AI                       |
| `POST` | `/agents/backtest/ai-design`  | AI-designed strategy backtest             |
| `POST` | `/agents/backtest/ai-series`  | AI backtest series execution              |
| `POST` | `/agents/backtest/ai-analyze` | AI analysis of backtest results           |

### Example: Run Backtest via API

```bash
curl -X POST http://localhost:8000/api/v1/agents/actions/run-backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "interval": "15",
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
    "start_date": "2025-06-01",
    "end_date": "2025-07-01",
    "initial_capital": 10000,
    "leverage": 10,
    "direction": "both"
  }'
```

---

## 🧠 Memory System

Located in `backend/agents/memory/vector_store.py`.

### Backtest Memory Methods

#### `save_backtest_result()`

Stores backtest results as searchable vector embeddings:

```python
store = VectorMemoryStore()
await store.initialize()

await store.save_backtest_result(
    backtest_id="abc-123",
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70},
    metrics={"win_rate": 65.0, "total_return": 12.5, "sharpe_ratio": 1.8},
    symbol="BTCUSDT",
    interval="15",
)
```

#### `find_similar_results()`

Semantic search across past backtest results:

```python
results = await store.find_similar_results(
    query="RSI strategy with high win rate on BTC",
    top_k=5,
    strategy_type="rsi",        # optional filter
    profitable_only=True,       # optional filter
)
for r in results:
    print(f"Score: {r.score:.3f} — {r.content}")
    print(f"  Win rate: {r.metadata['win_rate']}%")
```

---

## 🔒 Security & Validation

### StrategyValidator

Located in `backend/agents/security/strategy_validator.py`.

Validates strategy configurations before execution:

```python
from backend.agents.security.strategy_validator import StrategyValidator

validator = StrategyValidator()
result = validator.validate(
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    leverage=50,
    initial_capital=10000,
    start_date="2025-06-01",
    end_date="2025-07-01",
    stop_loss=0.02,
    take_profit=0.03,
)

if result.is_valid:
    print(f"✅ Valid — Risk level: {result.risk_level}")
else:
    print(f"❌ Invalid — Errors: {result.errors}")
print(f"⚠️ Warnings: {result.warnings}")
```

### Risk Levels

| Level      | Description                                  |
| ---------- | -------------------------------------------- |
| `SAFE`     | Low leverage, proper stops, validated params |
| `MODERATE` | Leverage 20-50x, or missing stops            |
| `HIGH`     | Leverage 50-100x                             |
| `EXTREME`  | Leverage > 100x                              |
| `REJECTED` | Validation errors — cannot run               |

### Existing Security Components

| Component         | File                    | Purpose                          |
| ----------------- | ----------------------- | -------------------------------- |
| PromptGuard       | `prompt_guard.py`       | Detects prompt injection attacks |
| OutputValidator   | `output_validator.py`   | Validates LLM output safety      |
| RateLimiter       | `rate_limiter.py`       | API call rate limiting           |
| StrategyValidator | `strategy_validator.py` | Strategy parameter validation    |

---

## ⚠️ Constraints & Safety

### Hard Limits (NEVER violate)

| Constraint          | Value                  | Reason                |
| ------------------- | ---------------------- | --------------------- |
| Commission rate     | 0.0007 (0.07%)         | TradingView parity    |
| Max leverage        | 125x                   | Bybit platform limit  |
| Data start date     | 2025-01-01             | Data retention policy |
| Engine              | FallbackEngineV4       | Gold standard         |
| Supported intervals | 1,5,15,30,60,240,D,W,M | Only these 9          |

### Soft Limits (warnings)

| Constraint  | Threshold                  | Warning                |
| ----------- | -------------------------- | ---------------------- |
| Leverage    | > 50x                      | Liquidation risk       |
| Stop loss   | < 0.5% with leverage > 20x | Frequent stop-outs     |
| Risk-reward | < 1.0                      | Reward less than risk  |
| Date range  | > 730 days                 | Long computation       |
| Capital     | > 10M USDT                 | Unrealistic simulation |

### Available Strategies

| Strategy          | Key Parameters                          |
| ----------------- | --------------------------------------- |
| `rsi`             | period, overbought, oversold            |
| `macd`            | fast_period, slow_period, signal_period |
| `sma_crossover`   | fast_period, slow_period                |
| `bollinger_bands` | period, std_dev                         |
| `grid`            | grid_count, upper_price, lower_price    |
| `dca`             | dca_count, dca_step_pct                 |
| `martingale`      | multiplier, max_trades                  |
| `custom`          | (user-defined)                          |
| `advanced`        | (user-defined)                          |

---

## 🛡️ Sandbox & Resource Limits

### `run_backtest` Safety Guards

| Guard       | Value                | Behavior                  |
| ----------- | -------------------- | ------------------------- |
| **Timeout** | 300 seconds (5 min)  | Returns timeout error     |
| **Memory**  | 512 MB minimum free  | Returns memory error      |
| **Wrapper** | `asyncio.wait_for()` | Prevents indefinite hangs |

### Implementation Details

```python
# Memory guard — aborts if < 512MB free
mem = psutil.virtual_memory()
if mem.available / (1024*1024) < 512:
    return {"error": "Insufficient memory..."}

# Timeout — 5 minutes max per backtest
result = await asyncio.wait_for(
    service.run_backtest(config),
    timeout=300
)
```

---

## 🔄 Autonomous Workflow Coordinator

**File:** `backend/agents/workflows/autonomous_backtesting.py`

End-to-end pipeline that chains fetch → evolve → backtest → report → learn steps.

| Class                           | Purpose                                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| `AutonomousBacktestingWorkflow` | Orchestrates the full pipeline                                                           |
| `WorkflowConfig`                | Symbol, interval, dates, evolution toggle                                                |
| `WorkflowStatus`                | Live stage tracking with progress percentage                                             |
| `WorkflowResult`                | Final output with backtest results + timing                                              |
| `PipelineStage`                 | Enum: idle → fetching → evolving → backtesting → reporting → learning → completed/failed |

### Pipeline Steps

1. **Fetch** — `SmartKlineService.get_klines_for_backtest()`
2. **Evolve** — `evolve_strategy` MCP tool (if `evolution_enabled`)
3. **Backtest** — `run_backtest` MCP tool
4. **Report** — `generate_backtest_report` MCP tool
5. **Learn** — `VectorMemoryStore.save_backtest_result()`

### API Endpoints

| Method | Path                              | Description               |
| ------ | --------------------------------- | ------------------------- |
| POST   | `/dashboard/workflow/start`       | Start autonomous workflow |
| GET    | `/dashboard/workflow/status/{id}` | Poll workflow progress    |
| GET    | `/dashboard/workflow/active`      | List active workflows     |

---

## 🔍 Pattern Extractor

**File:** `backend/agents/self_improvement/pattern_extractor.py`

Discovers winning strategy patterns from backtest history.

| Class               | Purpose                                                         |
| ------------------- | --------------------------------------------------------------- |
| `PatternExtractor`  | Fetches backtests, groups by strategy type, computes aggregates |
| `StrategyPattern`   | Per-strategy statistics (win rate, Sharpe, best config)         |
| `TimeframeAffinity` | Per-timeframe analysis (best intervals for each strategy)       |
| `ExtractionResult`  | Output: patterns + timeframe affinities + human insights        |

### Key Metrics Computed

- Average win rate, Sharpe, return %, drawdown per strategy
- Best individual configuration (by Sharpe)
- Timeframe affinity rankings
- Auto-generated text insights

### API Endpoints

| Method | Path                  | Description                                                         |
| ------ | --------------------- | ------------------------------------------------------------------- |
| GET    | `/dashboard/patterns` | Extract and return patterns (accepts `?min_samples=` and `?limit=`) |

---

## ⏰ Task Scheduler

**File:** `backend/agents/scheduler/task_scheduler.py`

Asyncio-native periodic job scheduler (no external dependencies).

| Class              | Purpose                                          |
| ------------------ | ------------------------------------------------ |
| `TaskScheduler`    | Manages task lifecycle: add, remove, start, stop |
| `ScheduledTask`    | Task definition with type, interval, retries     |
| `TaskHistoryEntry` | Execution log: start time, duration, success     |
| `TaskType`         | Enum: interval, daily, one_shot                  |
| `TaskState`        | Enum: pending, running, idle, stopped, failed    |

### Pre-Built Tasks

| Factory                      | Default Interval | Purpose                     |
| ---------------------------- | ---------------- | --------------------------- |
| `health_check_task()`        | Used in default  | System health via MCP tool  |
| `pattern_extraction_task()`  | Used in default  | Pattern mining from history |
| `create_default_scheduler()` | —                | Returns scheduler with both |

### Features

- Exponential backoff on retry (`max_retries`, `backoff_factor`)
- Semaphore-based concurrency limiting
- Full execution history with duration tracking

### API Endpoints

| Method | Path                         | Description              |
| ------ | ---------------------------- | ------------------------ |
| GET    | `/dashboard/scheduler/tasks` | List all tasks + history |

---

## 📊 Paper Trader

**File:** `backend/agents/trading/paper_trader.py`

Simulated live trading for AI agents — no real orders, real prices.

| Class              | Purpose                                 |
| ------------------ | --------------------------------------- |
| `AgentPaperTrader` | Manages paper trading sessions          |
| `PaperSession`     | Session state: balance, trades, P&L     |
| `PaperTrade`       | Individual trade: entry/exit, side, P&L |

### Session Lifecycle

1. `start_session(symbol, strategy, balance, duration)` → creates background task
2. Session polls price via `KlineRepositoryAdapter` (fallback: `BybitAdapter`)
3. Signals: `_generate_signal()` decides buy/sell/close/hold
4. `stop_session(id)` → closes open trades, saves to vector memory
5. Results viewable via API or `list_sessions()`

### API Endpoints

| Method | Path                                 | Description               |
| ------ | ------------------------------------ | ------------------------- |
| GET    | `/dashboard/paper-trading/sessions`  | List all sessions         |
| POST   | `/dashboard/paper-trading/start`     | Start paper trading       |
| POST   | `/dashboard/paper-trading/stop/{id}` | Stop and finalize session |

---

## 📜 Activity Log

### API Endpoints

| Method | Path                      | Description                     |
| ------ | ------------------------- | ------------------------------- |
| GET    | `/dashboard/activity-log` | Recent agent action log (JSONL) |

Reads from `logs/agent_actions.jsonl` (written by `log_agent_action` tool).

---

_Generated by Agent Ecosystem Audit — 2026-02-11_
_Updated with Phase 2 modules — 2026-02-12_
