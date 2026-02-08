---
name: Strategy Development
description: "Create new trading strategies following the BaseStrategy pattern with signal generation, parameter validation, and indicator computation."
---

# Strategy Development Skill

## Overview

Create and modify trading strategies that generate buy/sell signals using technical indicators.

## Strategy Template

```python
from backend.backtesting.strategies.base import BaseStrategy
import pandas as pd
import pandas_ta as ta

class MyStrategy(BaseStrategy):
    """
    Brief description of the strategy.

    Signals:
        1 = Long entry
        -1 = Short entry
        0 = No action
    """

    def __init__(self, params: dict):
        super().__init__(params)
        self.required_params = ['period', 'threshold']
        self._validate_params()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals from OHLCV data."""
        signals = data.copy()
        signals['signal'] = 0

        # Calculate indicator
        indicator = ta.rsi(signals['close'], length=self.params['period'])

        # Generate signals
        signals.loc[indicator < self.params['threshold'], 'signal'] = 1   # Long
        signals.loc[indicator > (100 - self.params['threshold']), 'signal'] = -1  # Short

        return signals
```

## File Location

All strategies go in `backend/backtesting/strategies/`.

## Required Interface

Every strategy MUST:

1. Inherit from `BaseStrategy`
2. Define `self.required_params` list
3. Call `self._validate_params()` in `__init__`
4. Implement `generate_signals(data: pd.DataFrame) -> pd.DataFrame`
5. Return DataFrame with a `signal` column containing only -1, 0, 1

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

Register new strategies in the strategy registry:

```python
# backend/backtesting/strategies/__init__.py
from .my_strategy import MyStrategy

STRATEGY_REGISTRY = {
    # ... existing strategies ...
    'my_strategy': MyStrategy,
}
```

## Testing Requirements

Every strategy needs:

```python
def test_my_strategy_generates_valid_signals(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})

def test_my_strategy_with_missing_params():
    with pytest.raises(ValueError):
        MyStrategy({})

def test_my_strategy_preserves_data_length(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert len(result) == len(sample_ohlcv)
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
