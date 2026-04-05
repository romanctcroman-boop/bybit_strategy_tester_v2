# Add New Strategy Prompt

Step-by-step guide for implementing a new trading strategy.

## Prerequisites

- [ ] Strategy concept documented
- [ ] Pine Script reference (if TradingView parity needed)
- [ ] Test data available

## Implementation Steps

### 1. Add Strategy to strategies.py

Path: `backend/backtesting/strategies.py` (single file — NOT a directory/package)

```python
from backend.backtesting.strategies import BaseStrategy, SignalResult
from typing import Any
import pandas as pd
import pandas_ta as ta


class NewStrategy(BaseStrategy):
    """
    [Strategy Name] Strategy

    Indicators:
        - [Indicator 1]: [description]

    Entry Signals:
        - Long: [condition]
        - Short: [condition]

    Exit Signals:
        - [condition]

    Parameters:
        - param1 (int): [description] (default: 14)

    TradingView Parity:
        # Pine: ta.rsi(close, 14) → Python: ta.rsi(ohlcv['close'], length=14)
    """

    name: str = "new_strategy"
    description: str = "Brief description"

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)  # calls _validate_params() internally

    def _validate_params(self) -> None:
        """Validate required parameters. Raise ValueError on missing/invalid."""
        if 'param1' not in self.params:
            raise ValueError("Missing required param: param1")
        if self.params['param1'] < 2:
            raise ValueError("param1 must be >= 2")

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """Generate trading signals from OHLCV data."""
        # Example with RSI — replace with your indicator logic
        rsi = ta.rsi(ohlcv['close'], length=self.params['param1'])

        entries = (rsi < 30)        # Long entry
        exits   = (rsi > 70)        # Long exit
        short_entries = (rsi > 70)  # Short entry
        short_exits   = (rsi < 30)  # Short exit

        return SignalResult(
            entries=entries.fillna(False),
            exits=exits.fillna(False),
            short_entries=short_entries.fillna(False),
            short_exits=short_exits.fillna(False),
        )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {'param1': 14}
```

### 2. Register Strategy

In `backend/backtesting/strategies.py`, find `STRATEGY_REGISTRY` (near end of file) and add:

```python
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    # ... existing entries ...
    "new_strategy": NewStrategy,   # ← add here
}
```

### 3. Create Tests

Path: `tests/backend/backtesting/test_new_strategy.py`

```python
import pytest
from backend.backtesting.strategies import NewStrategy, SignalResult


class TestNewStrategy:
    def test_init_valid_params(self):
        strategy = NewStrategy({'param1': 14})
        assert strategy.params['param1'] == 14

    def test_init_missing_params_raises(self):
        with pytest.raises(ValueError):
            NewStrategy({})

    def test_generate_signals_returns_signal_result(self, sample_ohlcv):
        strategy = NewStrategy({'param1': 14})
        result = strategy.generate_signals(sample_ohlcv)

        # ✅ SignalResult, NOT DataFrame
        assert isinstance(result, SignalResult)
        assert result.entries.dtype == bool
        # ✅ len(result.entries), NOT len(result) — no __len__
        assert len(result.entries) == len(sample_ohlcv)
        assert not result.entries.isna().any()
        assert not result.exits.isna().any()
```

### 4. TradingView Parity Check (if applicable)

```python
def test_tradingview_parity():
    # Load TradingView exported data (create tv_reference.csv manually by exporting from TradingView)
    # tests/fixtures/ does not exist by default; adjust path as needed
    tv_data = pd.read_csv('tv_reference.csv')

    # Calculate with our implementation
    strategy = NewStrategy(params)
    result = strategy.generate_signals(tv_data)

    # Compare indicator values (use entries/exits from SignalResult, not signal column)
    np.testing.assert_array_almost_equal(
        result.entries[warmup:].values.astype(int),
        tv_data['expected_entries'][warmup:].values,
        decimal=0
    )
```

### 5. Run Validation

```bash
# Tests
pytest tests/backend/backtesting/test_new_strategy.py -v

# Lint
ruff check backend/backtesting/strategies.py

# Coverage
pytest tests/backend/backtesting/test_new_strategy.py --cov=backend/backtesting/strategies
```

## Checklist

- [ ] Strategy inherits from `BaseStrategy`
- [ ] All required params validated
- [ ] Indicators use pandas_ta
- [ ] Pine Script equivalents documented
- [ ] Commission = 0.0007 used in tests
- [ ] Unit tests pass (80%+ coverage)
- [ ] TradingView parity verified (if applicable)
- [ ] Strategy registered in `STRATEGY_REGISTRY` in `backend/backtesting/strategies.py`
