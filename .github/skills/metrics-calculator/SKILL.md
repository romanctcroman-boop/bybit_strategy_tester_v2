---
name: Metrics Calculator
description: "Work with the 166-metric TradingView-parity metrics calculator. Understand metric categories, calculation methods, and parity rules."
---

# Metrics Calculator Skill

## Overview

The project maintains TradingView metric parity through a centralized calculator at `backend/core/metrics_calculator.py` (1483 lines). All metric calculations MUST go through this module.

## Usage

```python
from backend.core.metrics_calculator import MetricsCalculator, TimeFrequency

# Full calculation (all 166 metrics)
result = MetricsCalculator.calculate_all(
    trades=trades_list,        # List[dict] with pnl, pnl_pct, fees, bars_in_trade
    equity=equity_array,       # np.ndarray of equity curve
    initial_capital=10000.0,
    frequency=TimeFrequency.HOURLY  # For 15m/60m candles
)

# Individual metric functions (importable standalone)
from backend.core.metrics_calculator import (
    calculate_sharpe,
    calculate_sortino,
    calculate_calmar,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_cagr,
    calculate_expectancy,
    calculate_sqn,
    calculate_stability_r2,
    calculate_ulcer_index,
    calculate_margin_efficiency,
    safe_divide,
)
```

## Metric Categories

### TradeMetrics (dataclass)

| Metric                   | Formula                   | Notes                      |
| ------------------------ | ------------------------- | -------------------------- |
| `win_rate`               | winning / total × 100     | Percentage [0-100]         |
| `profit_factor`          | gross_profit / gross_loss | Capped at 100.0 (TV limit) |
| `avg_trade`              | net_profit / total_trades | In currency units          |
| `payoff_ratio`           | avg_win / abs(avg_loss)   | Risk/reward ratio          |
| `max_consec_wins/losses` | Streak counting           | Breakeven resets streaks   |

### RiskMetrics (dataclass)

| Metric          | Formula                                | Notes                                |
| --------------- | -------------------------------------- | ------------------------------------ |
| `sharpe_ratio`  | (mean - rfr) / std × √periods          | Uses monthly returns (TV mode)       |
| `sortino_ratio` | (mean - MAR) / downside_dev × √periods | Downside deviation uses ALL N        |
| `calmar_ratio`  | CAGR / max_drawdown                    | For periods < 30d uses simple return |
| `max_drawdown`  | peak-to-trough                         | As percentage                        |
| `cagr`          | (final/initial)^(1/years) - 1          | Simple annualization for < 30 days   |
| `sqn`           | √N × (mean_pnl / std_pnl)              | System Quality Number                |
| `stability`     | R² of equity curve                     | Linear regression fit [0-1]          |
| `ulcer_index`   | √(mean(dd²)) × 100                     | Pain measure                         |

### LongShortMetrics (dataclass)

All TradeMetrics are split into `long_*` and `short_*` prefixed versions.

## Time Frequency

```python
class TimeFrequency(str, Enum):
    MINUTELY = "minutely"   # 525600 periods/year
    HOURLY = "hourly"       # 8766 periods/year (default for crypto)
    DAILY = "daily"         # 365.25 periods/year
    WEEKLY = "weekly"       # 52.18 periods/year
    MONTHLY = "monthly"     # 12 periods/year
```

## Numba-Optimized Path

For optimizers (fast_optimizer, gpu_optimizer), use the Numba JIT version:

```python
from backend.core.metrics_calculator import calculate_metrics_numba

total_return, sharpe, max_dd, win_rate, n_trades, pf, calmar = \
    calculate_metrics_numba(pnl_array, equity_array, daily_returns, initial_capital)
```

## CRITICAL Rules

1. **Commission = 0.0007** — NEVER change, breaks TradingView parity
2. **All metrics go through MetricsCalculator** — no custom implementations
3. **safe_divide()** — always use for division to avoid ZeroDivisionError
4. **Sharpe uses MONTHLY returns** in TradingView mode
5. **Max drawdown is percentage** (0-100), not fraction (0-1)
6. **Profit factor capped at 100.0** — TradingView display limit

## Testing Parity

```python
# Verify against TradingView values within tolerance:
assert abs(calculated_net_profit - tv_net_profit) / abs(tv_net_profit) < 0.001  # 0.1%
assert abs(calculated_trades - tv_trades) == 0  # Exact match
assert abs(calculated_entry_price - tv_entry_price) / tv_entry_price < 0.0001  # 0.01%
```
