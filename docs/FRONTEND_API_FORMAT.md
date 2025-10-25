# Frontend API Format Documentation

**Date**: October 25, 2025  
**Status**: ✅ Implemented & Tested

---

## Overview

This document describes the transformation of `BacktestEngine` results to the format expected by the Frontend (`BacktestDetailPage.tsx`).

### Problem

- **BacktestEngine** returns results in a flat structure optimized for backend processing
- **Frontend** (`BacktestDetailPage.tsx`) expects a hierarchical structure with specific sections

### Solution

Added `_transform_results_for_frontend()` function in `backend/tasks/backtest_tasks.py` that transforms BacktestEngine output to Frontend-compatible format.

---

## Data Flow

```
BacktestEngine.run()
    ↓
    returns: {
        final_capital, total_return, total_trades,
        winning_trades, losing_trades, win_rate,
        sharpe_ratio, max_drawdown, profit_factor,
        metrics: {...},
        trades: [...],
        equity_curve: [...]
    }
    ↓
_transform_results_for_frontend()
    ↓
    returns: {
        overview: {...},
        by_side: {all, long, short},
        dynamics: {all, long, short},
        risk: {...},
        equity: [...],
        pnl_bars: [...]
    }
    ↓
BacktestOut.results (JSON in database)
    ↓
GET /api/backtests/{id}
    ↓
Frontend BacktestDetailPage
```

---

## Frontend Expected Format

### Structure

```typescript
type BacktestResults = {
  overview?: {
    net_pnl?: number;           // USDT
    net_pct?: number;           // %
    total_trades?: number;
    wins?: number;
    losses?: number;
    max_drawdown_abs?: number;  // USDT
    max_drawdown_pct?: number;  // %
    profit_factor?: number;
  };
  
  by_side?: {
    all: SideStats;
    long: SideStats;
    short: SideStats;
  };
  
  dynamics?: {
    all: DynamicsStats;
    long: DynamicsStats;
    short: DynamicsStats;
  };
  
  risk?: {
    sharpe?: number;
    sortino?: number;
    profit_factor?: number;
  };
  
  equity?: Array<{
    time: string | number;  // ISO timestamp or ms
    equity: number;
  }>;
  
  pnl_bars?: Array<{
    time: string | number;
    pnl: number;
  }>;
};
```

### SideStats

```typescript
type SideStats = {
  total_trades?: number;
  open_trades?: number;
  wins?: number;
  losses?: number;
  win_rate?: number;         // %
  avg_pl?: number;           // USDT
  avg_pl_pct?: number;       // %
  avg_win?: number;
  avg_win_pct?: number;
  avg_loss?: number;
  avg_loss_pct?: number;
  max_win?: number;
  max_win_pct?: number;
  max_loss?: number;
  max_loss_pct?: number;
  profit_factor?: number;
  avg_bars?: number;
  avg_bars_win?: number;
  avg_bars_loss?: number;
};
```

### DynamicsStats

```typescript
type DynamicsStats = {
  unrealized_abs?: number;
  unrealized_pct?: number;
  net_abs?: number;
  net_pct?: number;
  gross_profit_abs?: number;
  gross_profit_pct?: number;
  gross_loss_abs?: number;
  gross_loss_pct?: number;
  fees_abs?: number;
  fees_pct?: number;
  max_runup_abs?: number;
  max_runup_pct?: number;
  max_drawdown_abs?: number;
  max_drawdown_pct?: number;
  buyhold_abs?: number;
  buyhold_pct?: number;
  max_contracts?: number;
};
```

---

## Implementation

### Backend Changes

**File**: `backend/tasks/backtest_tasks.py`

**Added**:
- `_transform_results_for_frontend(engine_results: dict, initial_capital: float) -> dict`

**Key Features**:
1. Splits trades by side (LONG/SHORT)
2. Calculates per-side statistics
3. Calculates dynamics (unrealized, net, fees, runup, drawdown)
4. Formats equity curve for charts
5. Generates PnL bars for visualization

**Usage**:
```python
results = engine.run(data=candles, strategy_config=strategy_config)
frontend_results = _transform_results_for_frontend(results, initial_capital)

ds.update_backtest_results(
    backtest_id=backtest_id,
    results=frontend_results,  # Frontend-compatible format
)
```

---

## Testing

**File**: `tests/test_frontend_results_format.py`

**Coverage**:
- ✅ Basic transformation with mixed LONG/SHORT trades
- ✅ Empty results (no trades)
- ✅ Only LONG trades
- ✅ Only SHORT trades

**Test Results**:
```bash
tests/test_frontend_results_format.py ....                [100%]
4 passed in 5.33s
```

**Full Suite**:
```bash
50 passed, 4 deselected in 22.46s
```

---

## Example Output

### Input (BacktestEngine)

```json
{
  "final_capital": 10500.0,
  "total_return": 0.05,
  "total_trades": 10,
  "winning_trades": 6,
  "losing_trades": 4,
  "win_rate": 60.0,
  "sharpe_ratio": 1.5,
  "max_drawdown": 0.03,
  "profit_factor": 1.8,
  "metrics": {
    "net_profit": 500.0,
    "gross_profit": 800.0,
    "gross_loss": 300.0,
    "total_commission": 15.0,
    "max_drawdown_abs": 300.0,
    "buy_hold_return": 200.0
  },
  "trades": [
    {
      "side": "LONG",
      "pnl": 50.0,
      "commission": 1.5,
      ...
    }
  ],
  "equity_curve": [
    {"timestamp": "2024-01-01T10:00:00", "equity": 10000.0},
    {"timestamp": "2024-01-01T11:00:00", "equity": 10050.0}
  ]
}
```

### Output (Frontend Format)

```json
{
  "overview": {
    "net_pnl": 500.0,
    "net_pct": 5.0,
    "total_trades": 10,
    "wins": 6,
    "losses": 4,
    "max_drawdown_abs": 300.0,
    "max_drawdown_pct": 3.0,
    "profit_factor": 1.8
  },
  "by_side": {
    "all": {
      "total_trades": 10,
      "wins": 6,
      "losses": 4,
      "win_rate": 60.0,
      "avg_pl": 50.0,
      "profit_factor": 2.67
    },
    "long": { ... },
    "short": { ... }
  },
  "dynamics": {
    "all": {
      "net_abs": 500.0,
      "net_pct": 5.0,
      "gross_profit_abs": 800.0,
      "gross_loss_abs": 300.0,
      "fees_abs": 15.0,
      "buyhold_abs": 200.0,
      "buyhold_pct": 2.0
    },
    "long": { ... },
    "short": { ... }
  },
  "risk": {
    "sharpe": 1.5,
    "sortino": 2.0,
    "profit_factor": 1.8
  },
  "equity": [
    {"time": "2024-01-01T10:00:00", "equity": 10000.0},
    {"time": "2024-01-01T11:00:00", "equity": 10050.0}
  ],
  "pnl_bars": [
    {"time": "2024-01-01T10:00:00", "pnl": 0.0},
    {"time": "2024-01-01T11:00:00", "pnl": 50.0}
  ]
}
```

---

## Next Steps

1. **✅ DONE**: Transform results format
2. **✅ DONE**: Add tests
3. **TODO**: Run full cycle test via API
4. **TODO**: Verify in browser with real backtest

---

## Related Files

- `backend/tasks/backtest_tasks.py` - Transformation function
- `backend/core/backtest_engine.py` - Source data generator
- `frontend/src/pages/BacktestDetailPage.tsx` - Consumer
- `frontend/src/components/BacktestEquityChart.tsx` - Chart component
- `tests/test_frontend_results_format.py` - Unit tests
- `tests/integration/test_backtest_full_cycle.py` - Integration tests

---

**Status**: ✅ Ready for production testing
