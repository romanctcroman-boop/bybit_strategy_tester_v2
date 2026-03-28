---
applyTo: "**/strategies/**/*.py"
---

# Strategy Implementation Rules

## IMPORTANT: File Location

ALL strategies live in **`backend/backtesting/strategies.py`** (single file, NOT a directory/sub-package).
`BaseStrategy` and `SignalResult` are defined in this same file.

```python
# CORRECT import
from backend.backtesting.strategies import BaseStrategy, SignalResult

# WRONG — this path does not exist
# from backend.backtesting.strategies.base import BaseStrategy
```

## SignalResult (Return Type)

`generate_signals()` MUST return a `SignalResult` dataclass — NOT a DataFrame with a `'signal'` column.

```python
@dataclass
class SignalResult:
    entries: pd.Series            # bool — long entry signals
    exits: pd.Series              # bool — long exit signals
    short_entries: pd.Series | None = None   # bool — short entry signals
    short_exits: pd.Series | None = None     # bool — short exit signals
    entry_sizes: pd.Series | None = None     # float — position size per long entry (DCA Volume Scale)
    short_entry_sizes: pd.Series | None = None  # float — position size per short entry
    extra_data: dict | None = None           # e.g. {'atr': pd.Series} for ATR-based exits
```

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
        """Validate required parameters. Raise ValueError on missing/invalid."""
        required = ['period', 'threshold']
        for key in required:
            if key not in self.params:
                raise ValueError(f"Missing required param: {key}")
        if self.params['period'] < 2:
            raise ValueError("period must be >= 2")

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """Generate trading signals from OHLCV data."""
        rsi = ta.rsi(ohlcv['close'], length=self.params['period'])

        entries       = rsi < self.params['threshold']                # Long entry
        exits         = rsi > (100 - self.params['threshold'])        # Long exit
        short_entries = rsi > (100 - self.params['threshold'])        # Short entry
        short_exits   = rsi < self.params['threshold']                # Short exit

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

## Required Interface

Every strategy MUST:

1. Inherit from `BaseStrategy`
2. Set class attributes `name: str` and `description: str`
3. Implement `_validate_params(self) -> None` — raise `ValueError` on bad params
4. Implement `generate_signals(ohlcv: pd.DataFrame) -> SignalResult`
5. Implement `get_default_params(cls) -> dict` (classmethod)
6. All boolean Series must have `.fillna(False)` applied before returning

## Registration

After adding a new strategy class, register it in `STRATEGY_REGISTRY` (same file, near end):

```python
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMAStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    # ... existing entries ...
    "my_strategy": MyStrategy,   # ← add here
}
```

## Input DataFrame Columns

| Column    | Type     | Description   |
| --------- | -------- | ------------- |
| open      | float    | Open price    |
| high      | float    | High price    |
| low       | float    | Low price     |
| close     | float    | Close price   |
| volume    | float    | Volume        |
| timestamp | datetime | Bar timestamp (index) |

## TradingView Parity (CRITICAL)

- Use `pandas_ta` for ALL indicators — no custom implementations
- Document Pine Script equivalents in comments:

```python
# Pine: ta.rsi(close, 14) → Python: ta.rsi(ohlcv['close'], length=14)
# Pine: ta.ema(close, 12) → Python: ta.ema(ohlcv['close'], length=12)
```

- **Commission MUST be 0.07% (0.0007) for parity — NEVER change**

## Testing Requirements

```python
from backend.backtesting.strategies import MyStrategy, SignalResult
import pytest

def test_my_strategy_generates_valid_signals(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert isinstance(result, SignalResult)
    assert hasattr(result, "entries")
    assert hasattr(result, "exits")
    assert result.entries.dtype == bool
    # ✅ Use len(result.entries), NOT len(result) — SignalResult has no __len__
    assert len(result.entries) == len(sample_ohlcv)

def test_my_strategy_with_missing_params():
    with pytest.raises(ValueError):
        MyStrategy({})

def test_my_strategy_no_nan_in_signals(sample_ohlcv):
    strategy = MyStrategy({"period": 14, "threshold": 30})
    result = strategy.generate_signals(sample_ohlcv)
    assert not result.entries.isna().any()
    assert not result.exits.isna().any()
```

- Minimum 80% coverage
- Tests: initialization, signals valid, edge cases, missing params

## DO NOT

- Return `pd.DataFrame` with `'signal'` column — use `SignalResult`
- Import from `backend.backtesting.strategies.base` — path does not exist
- Use `len(signal_result)` — use `len(signal_result.entries)` instead
- Use custom indicator math — use `pandas_ta`
- Skip `fillna(False)` on boolean Series
- Change commission rate from `0.0007`
