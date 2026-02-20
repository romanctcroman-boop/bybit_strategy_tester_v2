Scaffold a new trading strategy class for the Bybit Strategy Tester v2 platform.

Usage: /new-strategy [strategy_name] [description]

Example: /new-strategy BollingerSqueeze "Enter when Bollinger Band width is minimal"

Steps:
1. Ask for the strategy name and brief description if not provided
2. Ask what indicators it uses (e.g., RSI, MACD, Bollinger Bands, EMA, custom)
3. Ask for the required parameters and their default values
4. Create the strategy file at `backend/backtesting/strategies/[snake_case_name].py` following this template:

```python
from __future__ import annotations
import pandas as pd
import pandas_ta as ta
from backend.backtesting.strategies.base import BaseStrategy


class [ClassName](BaseStrategy):
    """[Description]"""

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.required_params = [list of required param names]
        self._validate_params()

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = data.copy()
        signals['signal'] = 0  # 1=long, -1=short, 0=hold

        # --- indicator calculations ---

        # --- signal logic ---

        return signals
```

5. Create a corresponding test file at `tests/backend/backtesting/test_[snake_case_name].py`
6. Remind the user to register the strategy in the strategy registry (grep for where existing strategies are registered)
7. Update CHANGELOG.md under [Unreleased] → Added

Rules:
- Use pandas_ta (ta.*) for all indicator calculations — no manual loops
- signal column must contain only 1, -1, or 0
- Never hardcode commission_rate or timeframes inside strategy
- Never call Bybit API inside strategy
