---
applyTo: "**/backtesting/**/*.py"
---

# Backtester Engine Rules


## Data Flow - PRESERVE THIS (CRITICAL)

```
DataService.load_ohlcv(symbol, timeframe, start, end)
    ↓ returns: pd.DataFrame[open, high, low, close, volume, timestamp]

Strategy.generate_signals(data)
    ↓ returns: pd.DataFrame with 'signal' column (1, -1, 0)

BacktestEngine.run(data, signals, config)
    ↓ uses: initial_capital, commission_rate=0.0007
    ↓ returns: BacktestResults

MetricsCalculator.calculate(results)
    ↓ returns: Dict with 166 metrics
```

## Critical Parameters - NEVER LOSE

```python
from dataclasses import dataclass

@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission_rate: float = 0.0007  # 0.07% - MUST match TradingView
    slippage: float = 0.0005         # 0.05%
    position_size: float = 1.0       # fraction of capital
    leverage: int = 1                # leverage multiplier
```

## FallbackEngineV2 - Gold Standard

```python
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2

# This is the reference implementation
# All other engines must produce identical results
engine = FallbackEngineV2(config)
results = engine.run(data, strategy_params)

# Validate against TradingView:
# - Same number of trades
# - Same entry/exit prices (within 0.01%)
# - Same PnL (within 0.1%)
```

## Trade Execution Logic

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    entry_price: float
    exit_price: Optional[float]
    direction: int  # 1=long, -1=short
    quantity: float
    pnl: Optional[float]
    pnl_percent: Optional[float]
    commission: float
    mfe: float  # Maximum Favorable Excursion
    mae: float  # Maximum Adverse Excursion

def calculate_pnl(trade: Trade, commission_rate: float = 0.0007) -> float:
    """Calculate trade PnL with commission"""
    if trade.direction == 1:  # Long
        gross_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
    else:  # Short
        gross_pnl = (trade.entry_price - trade.exit_price) * trade.quantity

    # Commission on both entry and exit
    commission = trade.entry_price * trade.quantity * commission_rate * 2
    return gross_pnl - commission
```

## Performance Optimization

Use vectorized operations (NumPy/Pandas), avoid Python loops:

```python
import numpy as np
import pandas as pd

# GOOD - Vectorized
def calculate_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change()

def apply_signals(data: pd.DataFrame) -> pd.DataFrame:
    data['position'] = data['signal'].shift(1).fillna(0)
    data['returns'] = data['close'].pct_change()
    data['strategy_returns'] = data['position'] * data['returns']
    return data

# BAD - Avoid loops
def calculate_returns_slow(prices: pd.Series) -> list:
    returns = []
    for i in range(1, len(prices)):
        returns.append((prices[i] - prices[i-1]) / prices[i-1])
    return returns  # DON'T DO THIS
```

## Caching

```python
import functools
import hashlib

@functools.lru_cache(maxsize=128)
def calculate_indicator(close_tuple: tuple, period: int, indicator: str) -> tuple:
    """Cache indicator calculations for performance"""
    close = pd.Series(close_tuple)
    if indicator == 'rsi':
        result = ta.rsi(close, length=period)
    elif indicator == 'ema':
        result = ta.ema(close, length=period)
    return tuple(result.values)

# Convert Series to tuple for caching
close_tuple = tuple(df['close'].values)
rsi_values = calculate_indicator(close_tuple, 14, 'rsi')
```

## Walk-Forward Optimization

```python
from backend.backtesting.walk_forward import WalkForwardOptimizer

optimizer = WalkForwardOptimizer(
    in_sample_size=252,   # 1 year training
    out_of_sample_size=63, # 3 months testing
    step_size=21           # 1 month steps
)

results = optimizer.run(
    data=data,
    strategy_class=RSIStrategy,
    param_grid={
        'rsi_period': [10, 14, 21],
        'overbought': [65, 70, 75],
        'oversold': [25, 30, 35]
    }
)
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

- Change commission_rate from 0.0007
- Use loops for price calculations
- Skip MFE/MAE calculation
- Modify FallbackEngineV2 without approval
- Lose initial_capital or strategy_params variables
