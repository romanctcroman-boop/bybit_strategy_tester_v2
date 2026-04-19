---
name: new-strategy
description: Scaffold a new trading strategy class for the Bybit Strategy Tester v2 platform. Use when the user wants to create a new built-in strategy.
argument-hint: "[strategy_name] [description]"
effort: high
---

Scaffold a new trading strategy class for the Bybit Strategy Tester v2 platform.

Usage: /new-strategy [strategy_name] [description]

Example: /new-strategy BollingerSqueeze "Enter when Bollinger Band width is minimal"

Steps:
1. Ask for the strategy name and brief description if not provided
2. Ask what indicators it uses (e.g., RSI, MACD, Bollinger Bands, EMA, custom)
3. Ask for the required parameters and their default values
4. Add the strategy class to `backend/backtesting/strategies.py` (single file — NOT a separate file) following this template:

```python
from backend.backtesting.strategies import BaseStrategy, SignalResult
import pandas as pd
import pandas_ta as ta
from typing import Any


class [ClassName](BaseStrategy):
    """[Description]"""

    name: str = "[snake_case_name]"
    description: str = "[brief description]"

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)  # calls _validate_params() internally

    def _validate_params(self) -> None:
        """Validate required parameters."""
        if 'param1' not in self.params:
            raise ValueError("Missing required param: param1")
        if self.params['param1'] < 2:
            raise ValueError("param1 must be >= 2")

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """Generate trading signals. Returns SignalResult — NOT a DataFrame."""
        # --- indicator calculations ---

        # --- signal logic ---
        entries = pd.Series(False, index=ohlcv.index)       # long entries
        exits = pd.Series(False, index=ohlcv.index)         # long exits
        short_entries = pd.Series(False, index=ohlcv.index) # short entries
        short_exits = pd.Series(False, index=ohlcv.index)   # short exits

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

5. Register the strategy in `STRATEGY_REGISTRY` near the end of `backend/backtesting/strategies.py`:
   ```python
   STRATEGY_REGISTRY["[snake_case_name]"] = [ClassName]
   ```

6. Create a test file at `tests/backend/backtesting/test_[snake_case_name].py`:
   ```python
   import pytest
   from backend.backtesting.strategies import [ClassName], SignalResult

   class Test[ClassName]:
       def test_init_valid_params(self):
           strategy = [ClassName]({'param1': 14})
           assert strategy.params['param1'] == 14

       def test_init_missing_params_raises(self):
           with pytest.raises(ValueError):
               [ClassName]({})

       def test_generate_signals_returns_signal_result(self, sample_ohlcv):
           strategy = [ClassName]({'param1': 14})
           result = strategy.generate_signals(sample_ohlcv)
           assert isinstance(result, SignalResult)          # NOT DataFrame
           assert result.entries.dtype == bool
           assert len(result.entries) == len(sample_ohlcv) # len(result.entries), NOT len(result)
           assert not result.entries.isna().any()
           assert not result.exits.isna().any()
   ```

7. Update CHANGELOG.md under [Unreleased] → Added

Rules:
- `generate_signals()` MUST return `SignalResult` — NOT a DataFrame
- Use pandas_ta (ta.*) for all indicator calculations — no manual loops
- Use `.fillna(False)` on all boolean Series before returning
- Never hardcode commission_rate or timeframes inside strategy
- Never call Bybit API inside strategy
- Add strategy to `STRATEGY_REGISTRY` in `strategies.py` (not `STRATEGY_MAP`)
