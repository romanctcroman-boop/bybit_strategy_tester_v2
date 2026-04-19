# TradingView Parity Rules

## CRITICAL: Commission Rate

```python
# Commission MUST be 0.07% for TradingView parity
commission_rate = 0.0007  # 0.07%

# Use FallbackEngineV2 as gold standard
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
```

## Indicator Parity

- Preserve EXACT indicator behavior (periods, multipliers)
- Match TradingView output (compare first 100 values)
- Document conversions:

```python
# Pine: ta.rsi(close, 14) → Python: ta.rsi(df['close'], length=14)
# Pine: ta.ema(close, 12) → Python: ta.ema(df['close'], length=12)
```

## Backtester Data Flow

```
DataService (loads OHLCV from SQLite/Bybit)
    ↓
Strategy (generates signals from indicators)
    ↓ (depends on: strategy_params dict)
BacktestEngine/FallbackEngineV2 (executes trades)
    ↓ (depends on: initial_capital, commission=0.0007)
MetricsCalculator (calculates 166 metrics)
```

**NEVER lose:** `strategy_params`, `initial_capital`, `commission_rate`

## Validation Requirements

After ANY change to backtesting:

1. Run benchmark: `python benchmarks/backtest_speed.py`
2. Compare results: must match previous version within 0.01%
3. Check memory usage on 1M+ candles
4. Compare with TradingView on same dataset
