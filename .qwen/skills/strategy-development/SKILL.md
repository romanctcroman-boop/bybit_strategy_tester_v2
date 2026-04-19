---
name: Strategy Development
description: "Create new trading strategies following the BaseStrategy pattern with signal generation and parameter validation."
---

# Strategy Development Skill for Qwen

## Overview

Create and modify trading strategies that generate buy/sell signals using technical indicators.

## 📋 Strategy Template

```python
"""
[Strategy Name] Strategy

[Brief description of strategy logic and signals].

Signals:
    1 = Long entry
    -1 = Short entry
    0 = No action / Hold

Example:
    >>> strategy = [StrategyName]Strategy({"period": 14, "threshold": 30})
    >>> signals = strategy.generate_signals(ohlcv_data)
    >>> print(signals['signal'].value_counts())
"""

from backend.backtesting.strategies.base import BaseStrategy
import pandas as pd
import pandas_ta as ta
from loguru import logger


class [StrategyName]Strategy(BaseStrategy):
    """
    [Strategy description].
    
    This strategy [what it does] by [how it works].
    
    Entry Conditions (Long):
        1. [Condition 1]
        2. [Condition 2]
    
    Entry Conditions (Short):
        1. [Condition 1]
        2. [Condition 2]
    
    Exit Conditions:
        - [Exit rule]
    """
    
    def __init__(self, params: dict):
        """
        Initialize strategy with parameters.
        
        Args:
            params: Dictionary containing:
                - period: Indicator period (e.g., 14 for RSI)
                - threshold: Signal threshold (e.g., 30 for oversold)
                - additional_param: Description
        
        Raises:
            ValueError: If required parameters are missing
        """
        super().__init__(params)
        self.required_params = ['period', 'threshold']
        self._validate_params()
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals from OHLCV data.
        
        Args:
            data: DataFrame with columns:
                - open, high, low, close, volume
                - timestamp (index)
        
        Returns:
            DataFrame with added 'signal' column:
                - 1 = Long entry
                - -1 = Short entry
                - 0 = No action
        
        Example:
            >>> df = pd.DataFrame({...})  # OHLCV data
            >>> result = strategy.generate_signals(df)
            >>> assert 'signal' in result.columns
        """
        signals = data.copy()
        signals['signal'] = 0  # Default: no action
        
        # Calculate indicator
        indicator = ta.[indicator](
            signals['close'],
            length=self.params['period']
        )
        
        # Generate long signals
        long_condition = indicator < self.params['threshold']
        signals.loc[long_condition, 'signal'] = 1
        
        # Generate short signals
        short_condition = indicator > (100 - self.params['threshold'])
        signals.loc[short_condition, 'signal'] = -1
        
        logger.info(
            f"Generated {signals['signal'].sum()} signals "
            f"({(signals['signal'] == 1).sum()} long, "
            f"{(signals['signal'] == -1).sum()} short)"
        )
        
        return signals
```

## 📁 File Location

All strategies go in: `backend/backtesting/strategies/`

**Naming convention:**
- File: `snake_case.py` (e.g., `rsi_divergence.py`)
- Class: `PascalCaseStrategy` (e.g., `RsiDivergenceStrategy`)

## ✅ Required Interface

Every strategy MUST:

1. **Inherit from `BaseStrategy`**
   ```python
   from backend.backtesting.strategies.base import BaseStrategy
   ```

2. **Define `required_params`**
   ```python
   self.required_params = ['period', 'threshold']
   ```

3. **Validate parameters**
   ```python
   self._validate_params()
   ```

4. **Implement `generate_signals`**
   ```python
   def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
       # Must return DataFrame with 'signal' column
   ```

5. **Return valid signals**
   - `1` = Long entry
   - `-1` = Short entry
   - `0` = No action

## 📊 Input DataFrame

```python
# Standard OHLCV format
data = pd.DataFrame({
    'open': [42000.0, 42100.0, ...],
    'high': [42500.0, 42600.0, ...],
    'low': [41800.0, 41900.0, ...],
    'close': [42300.0, 42400.0, ...],
    'volume': [1000.0, 1200.0, ...],
}, index=pd.date_range('2025-01-01', periods=100, freq='15min'))
```

## 🔧 pandas_ta Indicators

### Common Indicators

```python
import pandas_ta as ta

# Momentum
ta.rsi(close, length=14)           # RSI
ta.macd(close, fast=12, slow=26, signal=9)  # MACD
ta.stoch(high, low, close, k=14, d=3)  # Stochastic
ta.cci(high, low, close, length=20)  # CCI

# Trend
ta.ema(close, length=20)           # EMA
ta.sma(close, length=50)           # SMA
ta.supertrend(high, low, close, length=10, multiplier=3.0)

# Volatility
ta.bbands(close, length=20, std=2.0)  # Bollinger Bands
ta.atr(high, low, close, length=14)   # ATR
ta.keltner(high, low, close, length=20)  # Keltner

# Volume
ta.obv(close, volume)              # OBV
ta.cmf(high, low, close, volume, length=20)  # CMF
ta.mfi(high, low, close, volume, length=14)  # MFI
```

## 📝 Registration

Register new strategy in `backend/backtesting/strategies/__init__.py`:

```python
from .[strategy_file] import [StrategyName]Strategy

STRATEGY_REGISTRY = {
    # Existing strategies
    'rsi': RSIStrategy,
    'macd': MACDStrategy,
    
    # Add your strategy
    '[strategy_name]': [StrategyName]Strategy,
}
```

## 🧪 Testing Requirements

```python
"""Tests for [Strategy Name] strategy."""

import pytest
import pandas as pd
import numpy as np
from backend.backtesting.strategies.[strategy_file] import [StrategyName]Strategy


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range('2025-01-01', periods=100, freq='15min')
    return pd.DataFrame({
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 120, 100),
        'low': np.random.uniform(90, 100, 100),
        'close': np.random.uniform(100, 110, 100),
        'volume': np.random.uniform(1000, 5000, 100),
    }).set_index('timestamp')


def test_strategy_generates_valid_signals(sample_ohlcv):
    """Strategy should generate valid signals (-1, 0, 1)."""
    strategy = [StrategyName]Strategy({
        'period': 14,
        'threshold': 30
    })
    result = strategy.generate_signals(sample_ohlcv)
    
    assert 'signal' in result.columns
    assert set(result['signal'].unique()).issubset({-1, 0, 1})
    assert len(result) == len(sample_ohlcv)


def test_strategy_with_missing_params():
    """Strategy should raise error with missing required params."""
    with pytest.raises(ValueError):
        [StrategyName]Strategy({})


def test_strategy_preserves_data_length(sample_ohlcv):
    """Strategy output should have same length as input."""
    strategy = [StrategyName]Strategy({
        'period': 14,
        'threshold': 30
    })
    result = strategy.generate_signals(sample_ohlcv)
    assert len(result) == len(sample_ohlcv)


def test_strategy_with_extreme_values():
    """Strategy should handle extreme market conditions."""
    extreme_data = pd.DataFrame({
        'open': [1000000.0] * 100,
        'high': [1000000.0] * 100,
        'low': [0.001] * 100,
        'close': [500000.0] * 100,
        'volume': [0.0] * 100,
    })
    
    strategy = [StrategyName]Strategy({
        'period': 14,
        'threshold': 30
    })
    result = strategy.generate_signals(extreme_data)
    
    # Should not crash, should generate valid signals
    assert 'signal' in result.columns
    assert result['signal'].notna().all()
```

## 📋 Strategy Checklist

Before committing:

- [ ] Inherits from `BaseStrategy`
- [ ] `required_params` defined
- [ ] `_validate_params()` called
- [ ] `generate_signals()` implemented
- [ ] Returns DataFrame with 'signal' column
- [ ] Signal values are -1, 0, 1
- [ ] Docstrings complete
- [ ] Tests written and passing
- [ ] Registered in `__init__.py`
- [ ] CHANGELOG.md updated

## 🚀 Example: RSI Strategy

```python
"""
RSI Strategy

Classic RSI oversold/overbought strategy.

Signals:
    1 = Long when RSI < oversold
    -1 = Short when RSI > overbought
    0 = Hold
"""

from backend.backtesting.strategies.base import BaseStrategy
import pandas as pd
import pandas_ta as ta


class RSIStrategy(BaseStrategy):
    """RSI oversold/overbought strategy."""
    
    def __init__(self, params: dict):
        super().__init__(params)
        self.required_params = ['period', 'oversold', 'overbought']
        self._validate_params()
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate RSI signals."""
        signals = data.copy()
        signals['signal'] = 0
        
        # Calculate RSI
        rsi = ta.rsi(signals['close'], length=self.params['period'])
        
        # Long: RSI below oversold
        signals.loc[rsi < self.params['oversold'], 'signal'] = 1
        
        # Short: RSI above overbought
        signals.loc[rsi > self.params['overbought'], 'signal'] = -1
        
        return signals
```

## 🔗 Related

- [BaseStrategy](../../backend/backtesting/strategies/base.py) — Base class
- [Backtest Execution](../backtest-execution/) — Test strategies
- [pandas_ta Documentation](https://pandas-ta.readthedocs.io/) — Indicator reference
