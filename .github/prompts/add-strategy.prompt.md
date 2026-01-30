# Add New Strategy Prompt

Step-by-step guide for implementing a new trading strategy.

## Prerequisites

- [ ] Strategy concept documented
- [ ] Pine Script reference (if TradingView parity needed)
- [ ] Test data available

## Implementation Steps

### 1. Create Strategy File

Path: `backend/backtesting/strategies/[strategy_name].py`

```python
from backend.backtesting.strategies.base import BaseStrategy
from typing import Dict
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
        - param1 (float): [description] (default: X)

    TradingView Parity:
        # Pine: [pine code] → Python: [python code]
    """

    def __init__(self, params: Dict[str, float]):
        super().__init__(params)
        self.required_params = ['param1', 'param2']
        self._validate_params()

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        df = data.copy()
        # Add calculations
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals."""
        df = self.calculate_indicators(data)
        df['signal'] = 0

        # Signal logic
        # df.loc[long_condition, 'signal'] = 1
        # df.loc[short_condition, 'signal'] = -1

        return df
```

### 2. Register Strategy

Path: `backend/backtesting/strategies/__init__.py`

```python
from .new_strategy import NewStrategy

STRATEGY_MAP = {
    # ... existing
    'new_strategy': NewStrategy,
}
```

### 3. Create Tests

Path: `tests/test_strategies/test_new_strategy.py`

```python
import pytest
from backend.backtesting.strategies.new_strategy import NewStrategy


class TestNewStrategy:
    def test_init_valid_params(self):
        params = {'param1': 14, 'param2': 70}
        strategy = NewStrategy(params)
        assert strategy.params == params

    def test_generate_signals(self, sample_ohlcv):
        params = {'param1': 14, 'param2': 70}
        strategy = NewStrategy(params)
        result = strategy.generate_signals(sample_ohlcv)

        assert 'signal' in result.columns
        assert set(result['signal'].unique()).issubset({-1, 0, 1})
```

### 4. TradingView Parity Check (if applicable)

```python
def test_tradingview_parity():
    # Load TradingView exported data
    tv_data = pd.read_csv('tests/fixtures/tv_reference.csv')

    # Calculate with our implementation
    strategy = NewStrategy(params)
    result = strategy.calculate_indicators(tv_data)

    # Compare values
    np.testing.assert_array_almost_equal(
        result['indicator'][warmup:].values,
        tv_data['tv_indicator'][warmup:].values,
        decimal=2
    )
```

### 5. Run Validation

```bash
# Tests
pytest tests/test_strategies/test_new_strategy.py -v

# Lint
ruff check backend/backtesting/strategies/new_strategy.py

# Coverage
pytest tests/test_strategies/test_new_strategy.py --cov=backend/backtesting/strategies/new_strategy
```

## Checklist

- [ ] Strategy inherits from `BaseStrategy`
- [ ] All required params validated
- [ ] Indicators use pandas_ta
- [ ] Pine Script equivalents documented
- [ ] Commission = 0.0007 used in tests
- [ ] Unit tests pass (80%+ coverage)
- [ ] TradingView parity verified (if applicable)
- [ ] Strategy registered in `__init__.py`
