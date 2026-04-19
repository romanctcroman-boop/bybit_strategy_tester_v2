# Variable Tracker - Bybit Strategy Tester v2

**Purpose:** Track critical variables to prevent loss during refactoring
**Update:** Whenever you modify/add/remove important variables

---

## Active Variables

### Backtesting Engine (backend/backtesting/)

#### FallbackEngineV2 (engines/fallback_engine_v2.py)

| Line | Variable        | Type        | Status      | Notes                                   |
| ---- | --------------- | ----------- | ----------- | --------------------------------------- |
| ~50  | commission_rate | float       | ⚠️ CRITICAL | **0.0007 (0.07%)** - TradingView parity |
| ~45  | initial_capital | float       | ✅ Active   | Default 10000.0                         |
| ~60  | leverage        | int         | ✅ Active   | Default 1                               |
| ~70  | position        | Position    | ✅ Active   | Current open position                   |
| ~80  | trades          | List[Trade] | ✅ Active   | Executed trades log                     |
| ~90  | equity_curve    | List[float] | ✅ Active   | Equity over time                        |

#### Engine (engine.py)

| Line | Variable        | Type           | Status      | Notes                    |
| ---- | --------------- | -------------- | ----------- | ------------------------ |
| ~40  | strategy_params | Dict[str, Any] | ⚠️ CRITICAL | Passed to all strategies |
| ~50  | config          | BacktestConfig | ✅ Active   | Backtest configuration   |
| ~60  | data            | pd.DataFrame   | ✅ Active   | OHLCV data               |

### Strategies (backend/backtesting/strategies/)

#### Base Strategy (base.py)

| Line | Variable        | Type             | Status      | Notes                    |
| ---- | --------------- | ---------------- | ----------- | ------------------------ |
| ~20  | params          | Dict[str, float] | ⚠️ CRITICAL | Strategy parameters      |
| ~30  | required_params | List[str]        | ✅ Active   | Required parameter names |

### API Layer (backend/api/)

#### Schemas (schemas.py)

| Line | Variable         | Type     | Status    | Notes                   |
| ---- | ---------------- | -------- | --------- | ----------------------- |
| ~100 | BacktestRequest  | Pydantic | ✅ Active | Backtest request model  |
| ~150 | BacktestResponse | Pydantic | ✅ Active | Backtest response model |

### Services (backend/services/)

#### Data Service (data_service.py)

| Line | Variable | Type | Status    | Notes                |
| ---- | -------- | ---- | --------- | -------------------- |
| ~30  | db_path  | str  | ✅ Active | SQLite database path |
| ~40  | cache    | Dict | ✅ Active | In-memory cache      |

#### Bybit Adapter (adapters/bybit.py)

| Line | Variable     | Type        | Status    | Notes            |
| ---- | ------------ | ----------- | --------- | ---------------- |
| ~20  | api_key      | str         | 🔒 Secret | From environment |
| ~21  | api_secret   | str         | 🔒 Secret | From environment |
| ~30  | rate_limiter | RateLimiter | ✅ Active | 120 req/min      |

---

## Recently Changed Variables

### Changed on [DATE]

**Variable:** `[name]`
**File:** `[path]:[line]`
**Change:** [Description of change]
**Reason:** [Why it was changed]
**Impact:** [Files affected]

---

## High-Risk Variables (NEVER DELETE)

These variables are used in many places. Extra care when modifying:

### commission_rate

- **Location:** `backend/backtesting/engines/fallback_engine_v2.py`
- **Value:** 0.0007 (0.07%)
- **Used in:** 10+ files
- **Impact:** ALL backtest results, TradingView parity
- **Change protocol:** NEVER change without approval

### strategy_params

- **Location:** `backend/backtesting/engine.py`
- **Type:** Dict[str, Any]
- **Used in:** All strategy classes, optimizer, UI
- **Change protocol:** Update ALL strategy classes first

### initial_capital

- **Location:** `backend/backtesting/engine.py`
- **Type:** float
- **Default:** 10000.0
- **Used in:** Engine, metrics calculator, UI
- **Change protocol:** Update config defaults first

---

## Variable Naming Conventions

### Strategy Parameters

```python
# Format: [indicator]_[param_type]
rsi_period: int = 14
rsi_overbought: float = 70.0
ema_fast: int = 12
ema_slow: int = 26
```

### Configuration

```python
# Format: [component]_[setting]
backtest_initial_capital: float
api_rate_limit: int
optimizer_max_iterations: int
```

### Data Containers

```python
# Format: [content]_[container_type]
trade_log: List[Trade]
signal_series: pd.Series
results_df: pd.DataFrame
params_dict: Dict[str, float]
```

---

## Deprecated Variables

Keep reference for 30 days after removal:

### Removed on [DATE]

**Variable:** `[name]`
**File:** `[path]` (deleted/refactored)
**Reason:** [Why removed]
**Migration:** [What to use instead]
**Commit:** [hash]
