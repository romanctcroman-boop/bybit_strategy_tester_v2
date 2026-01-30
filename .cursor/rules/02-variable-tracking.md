# Variable Tracking Rules

## Variable Safety - CRITICAL

Before modifying ANY code:

1. **Search first:** Find ALL usages of variables you'll touch
2. **Track in plan:** Document every variable (name, type, file:line)
3. **After changes:** Verify no variables lost
4. **Update imports:** Immediately after any refactoring

## Variable Tracking Format

```markdown
| Variable        | File                  | Line | Type  | Status      | Notes       |
| --------------- | --------------------- | ---- | ----- | ----------- | ----------- |
| strategy_params | engine.py             | 45   | Dict  | ✅ Active   | Core config |
| commission_rate | fallback_engine_v2.py | 50   | float | ⚠️ CRITICAL | 0.0007      |
```

## High-Risk Variables (NEVER DELETE)

These are used in 10+ files. Extra caution required:

### `commission_rate`

- **Value:** 0.0007 (0.07%)
- **Location:** `backend/backtesting/engines/fallback_engine_v2.py`
- **Impact:** ALL backtest results, TradingView parity
- **Rule:** NEVER change without approval

### `strategy_params`

- **Type:** Dict[str, Any]
- **Location:** `backend/backtesting/engine.py`
- **Impact:** All strategy classes, optimizer, UI
- **Rule:** Update ALL strategy classes when modified

### `initial_capital`

- **Type:** float
- **Default:** 10000.0
- **Location:** `backend/backtesting/engine.py`
- **Impact:** Engine, metrics calculator, UI

## Naming Conventions

```python
# Strategy Parameters: [indicator]_[param_type]
rsi_period: int = 14
ema_fast: int = 12

# Configuration: [component]_[setting]
backtest_initial_capital: float
api_rate_limit: int

# Data Containers: [content]_[container_type]
trade_log: List[Trade]
signal_series: pd.Series
results_df: pd.DataFrame
```
