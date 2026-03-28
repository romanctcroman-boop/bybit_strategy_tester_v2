---
applyTo: "**/backtesting/**/*.py"
---

# Backtester Engine Rules

## Data Flow — PRESERVE THIS (CRITICAL)

```
DataService.get_market_data(symbol, timeframe, start_time, end_time)
    ↓ returns: pd.DataFrame[open, high, low, close, volume, timestamp]

Strategy.generate_signals(ohlcv: pd.DataFrame) -> SignalResult
    ↓ returns: SignalResult(entries=bool Series, exits=bool Series,
    ↓                       short_entries=bool|None, short_exits=bool|None)
    ↓ NOT a DataFrame with 'signal' column — that API is DEPRECATED

BacktestEngine.run(data, strategy_config, ...)
    ↓ entry on NEXT bar open after signal (not signal bar!)
    ↓ commission=0.0007 on margin (NOT on leveraged value)
    ↓ returns: dict with metrics + trades

MetricsCalculator.calculate_all(trades, equity, config)
    ↓ returns: dict with 166 TV-parity metrics
```

## Gold Standard Engine: FallbackEngineV4

```python
# ✅ CORRECT
from backend.backtesting.engines.fallback_engine_v4 import FallbackEngine

# ❌ WRONG — deprecated, do not use for new code
# from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
```

**Engine selection via `engine_selector.py`:**

```python
from backend.core.engine_adapter import get_engine

engine = get_engine(
    engine_type=None,          # None → auto-selects FallbackEngineV4
    initial_capital=10000.0,
    commission=0.0007,
    slippage=0.0001,
)
results = engine.run(data=candles, strategy_config=strategy_config)
```

## Critical Parameters — NEVER LOSE

```python
# From backend/backtesting/models.py — BacktestConfig (100+ fields)
commission_value: float = 0.0007   # 0.07% — MUST match TradingView — NEVER CHANGE
initial_capital: float = 10000.0
position_size: float = 1.0         # fraction (1.0 = 100% capital)
leverage: float = 1.0              # ⚠️ optimizer default = 10, frontend = 10
direction: str = "both"            # ⚠️ POST /api/backtests/ default = "long"!
pyramiding: int = 1                # ⚠️ hardcoded to 1 in optimizer

# Commission is calculated on MARGIN (not leveraged value) — TradingView style:
# commission = trade_value × commission_value  (NOT leveraged_value × commission_value)
```

## Trade Execution Logic

```python
# Entry: on OPEN of bar AFTER signal bar
entry_price = next_bar.open

# PnL for long:
pnl = (exit_price - entry_price) / entry_price * leveraged_position_value - 2 * commission

# SL check (long): bar.low ≤ entry_price * (1 - stop_loss)
# TP check (long): bar.high ≥ entry_price * (1 + take_profit)
```

## Performance Optimization

Use vectorized operations (NumPy/Pandas), avoid Python loops:

```python
# GOOD — Vectorized
data['position'] = data['signal'].shift(1).fillna(0)
data['returns'] = data['close'].pct_change()
data['strategy_returns'] = data['position'] * data['returns']

# BAD — avoid loops over price data
for i in range(1, len(prices)):
    ...  # DON'T DO THIS
```

## Metrics Requirements

MetricsCalculator must produce all 166 metrics:

| Category    | Examples                                      |
| ----------- | --------------------------------------------- |
| Returns     | Total return, CAGR, Daily returns             |
| Risk        | Max drawdown, VaR, Sharpe, Sortino            |
| Trade stats | Win rate, Profit factor, Avg trade            |
| Position    | Avg holding time, Max consecutive wins/losses |

## DO NOT

- Change `commission_value` from `0.0007`
- Use loops for price calculations
- Skip MFE/MAE calculation
- Use or reference `FallbackEngineV2/V3` for new code
- Return `pd.DataFrame` with `'signal'` column from `generate_signals`
- Lose `initial_capital` or `strategy_params` variables
