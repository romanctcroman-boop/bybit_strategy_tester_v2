# Strategy Implementation Rules

**Applies to:** `**/strategies/**/*.py`

## Structure

- ALL strategies inherit from `BaseStrategy`
- File naming: `snake_case.py` (e.g., `ema_crossover.py`)
- Class naming: `PascalCase` (e.g., `EMACrossover`)

## Required Methods

```python
from backend.backtesting.strategies.base import BaseStrategy
from typing import Dict, Optional
import pandas as pd
import pandas_ta as ta

class NewStrategy(BaseStrategy):
    """
    Strategy description

    Indicators:
        - Indicator 1: description
        - Indicator 2: description

    Entry Signals:
        - Long: condition
        - Short: condition

    Exit Signals:
        - condition

    Parameters:
        - param1 (float): description (default: X)
    """

    def __init__(self, params: Dict[str, float]):
        super().__init__(params)
        self.required_params = ['param1', 'param2']
        self._validate_params()

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate required technical indicators"""
        df = data.copy()
        # Add indicator calculations using pandas_ta
        df['rsi'] = ta.rsi(df['close'], length=self.params.get('rsi_period', 14))
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate entry/exit signals. Returns DataFrame with 'signal' column."""
        df = self.calculate_indicators(data)
        df['signal'] = 0  # 1=long, -1=short, 0=neutral
        # Signal logic here
        return df
```

## Parameter Validation

```python
def _validate_params(self) -> None:
    """Validate all required parameters present and valid"""
    for param in self.required_params:
        if param not in self.params:
            raise ValueError(f"Missing required parameter: {param}")
        if self.params[param] <= 0:
            raise ValueError(f"Parameter {param} must be positive")
```

## TradingView Parity (CRITICAL)

- Use pandas_ta library for indicators
- Document Pine Script equivalents in comments:

```python
# Pine: ta.rsi(close, 14) → Python: ta.rsi(df['close'], length=14)
# Pine: ta.ema(close, 12) → Python: ta.ema(df['close'], length=12)
```

- Validate: first 100 values must match TradingView output
- **Commission MUST be 0.07% (0.0007) for parity**

## Signal Format

Signals DataFrame must include:

| Column        | Description                             |
| ------------- | --------------------------------------- |
| `signal`      | 1 (long), -1 (short), 0 (neutral)       |
| `entry_price` | price at signal generation (optional)   |
| `stop_loss`   | calculated stop loss level (optional)   |
| `take_profit` | calculated take profit level (optional) |

## Testing Requirements

Each strategy needs:

- `tests/test_strategies/test_[strategy_name].py`
- Minimum 80% code coverage
- Tests: initialization, signal generation, edge cases, TradingView parity

## DO NOT

- Use custom indicator implementations (use pandas_ta)
- Skip parameter validation
- Forget to document Pine Script equivalents
- Change commission rate from 0.0007
