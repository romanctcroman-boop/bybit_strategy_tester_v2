# Variable Tracker

> Track critical variables during refactoring to prevent loss

## Status Legend

- ✅ Active - Variable exists and is used
- ⚠️ Modified - Variable changed in current session
- ❌ Removed - Variable deleted (verify intended)
- 🔄 Renamed - Variable renamed (update all usages)

## Critical Variables (NEVER LOSE)

### Backtest Configuration

| Variable          | Type    | File                            | Line | Status |
| ----------------- | ------- | ------------------------------- | ---- | ------ |
| `commission_rate` | `float` | `backend/backtesting/config.py` | -    | ✅     |
| `initial_capital` | `float` | `backend/backtesting/config.py` | -    | ✅     |
| `slippage`        | `float` | `backend/backtesting/config.py` | -    | ✅     |
| `leverage`        | `int`   | `backend/backtesting/config.py` | -    | ✅     |

### Strategy Parameters

| Variable          | Type   | File                 | Line | Status |
| ----------------- | ------ | -------------------- | ---- | ------ |
| `strategy_params` | `Dict` | All strategy classes | -    | ✅     |
| `required_params` | `List` | All strategy classes | -    | ✅     |

### Engine State

| Variable       | Type          | File             | Line | Status |
| -------------- | ------------- | ---------------- | ---- | ------ |
| `equity_curve` | `List[float]` | FallbackEngineV2 | -    | ✅     |
| `trades`       | `List[Trade]` | FallbackEngineV2 | -    | ✅     |

## Current Session Changes

_No active session_

---

## Usage

Before modifying code:

1. Search: `@workspace "variable_name"` to find all usages
2. Add to tracker with current location
3. After changes, verify status

After modifying code:

1. Update status (✅/⚠️/❌/🔄)
2. Update file/line if moved
3. Document reason for change

---

_Last updated: 2025-01-30_
