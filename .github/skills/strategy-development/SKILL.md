---
name: Strategy Development
description: "Create new trading strategies following the BaseStrategy pattern with signal generation, parameter validation, and indicator computation."
---

# Strategy Development Skill

## Overview

Create and modify trading strategies that generate buy/sell signals using technical indicators.

## Strategy Template

```python
from backend.backtesting.strategies import BaseStrategy, SignalResult
import pandas as pd
import pandas_ta as ta
from typing import Any

class MyStrategy(BaseStrategy):
    """
    Brief description of the strategy.

    Signals (via SignalResult):
        entries       = Boolean Series — long entry
        exits         = Boolean Series — long exit
        short_entries = Boolean Series — short entry (optional)
        short_exits   = Boolean Series — short exit (optional)
    """

    name: str = "my_strategy"
    description: str = "Brief description"

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)  # calls _validate_params() internally

    def _validate_params(self) -> None:
        """Validate required parameters."""
        required = ['period', 'threshold']
        for key in required:
            if key not in self.params:
                raise ValueError(f"Missing required param: {key}")

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """Generate trading signals from OHLCV data."""
        rsi = ta.rsi(ohlcv['close'], length=self.params['period'])

        entries = rsi < self.params['threshold']               # Long entry
        exits   = rsi > (100 - self.params['threshold'])       # Long exit
        short_entries = rsi > (100 - self.params['threshold']) # Short entry
        short_exits   = rsi < self.params['threshold']         # Short exit

        return SignalResult(
            entries=entries.fillna(False),
            exits=exits.fillna(False),
            short_entries=short_entries.fillna(False),
            short_exits=short_exits.fillna(False),
        )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {'period': 14, 'threshold': 30}
```

## File Location

All strategies go in **`backend/backtesting/strategies.py`** (single file, not a directory).
`BaseStrategy` and `SignalResult` are defined in this file.

```python
# Correct import — from the module, NOT from a sub-package
from backend.backtesting.strategies import BaseStrategy, SignalResult
```

## Required Interface

Every strategy MUST:

1. Inherit from `BaseStrategy` (defined in `backend/backtesting/strategies.py`)
2. Implement `_validate_params(self) -> None` — raise `ValueError` on bad params
3. Implement `generate_signals(ohlcv: pd.DataFrame) -> SignalResult`
4. Return a `SignalResult` with boolean `entries`/`exits` Series (not a signal column)

## Input DataFrame Columns

| Column    | Type     | Description   |
| --------- | -------- | ------------- |
| open      | float    | Open price    |
| high      | float    | High price    |
| low       | float    | Low price     |
| close     | float    | Close price   |
| volume    | float    | Volume        |
| timestamp | datetime | Bar timestamp |

## Registration

Add new strategies to `backend/backtesting/strategies.py` directly (no sub-package):

```python
# In backend/backtesting/strategies.py — add class at the bottom
class MyStrategy(BaseStrategy):
    ...

# Then register in STRATEGY_REGISTRY (near end of same file):
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

## Testing Requirements

Every strategy needs:

```python
from backend.backtesting.strategies import MyStrategy, SignalResult

def test_my_strategy_generates_valid_signals(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert isinstance(result, SignalResult)
    assert hasattr(result, "entries")
    assert hasattr(result, "exits")
    assert result.entries.dtype == bool

def test_my_strategy_with_missing_params():
    with pytest.raises(ValueError):
        MyStrategy({})

def test_my_strategy_preserves_data_length(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert len(result.entries) == len(sample_ohlcv)  # len(result.entries), NOT len(result)
```

## pandas_ta Indicators

Common indicators available via `pandas_ta`:

| Function                             | Usage                      |
| ------------------------------------ | -------------------------- |
| `ta.rsi(close, length)`              | Relative Strength Index    |
| `ta.macd(close, fast, slow, signal)` | MACD                       |
| `ta.bbands(close, length, std)`      | Bollinger Bands            |
| `ta.ema(close, length)`              | Exponential Moving Average |
| `ta.sma(close, length)`              | Simple Moving Average      |
| `ta.stoch(high, low, close, k, d)`   | Stochastic                 |
| `ta.atr(high, low, close, length)`   | Average True Range         |
