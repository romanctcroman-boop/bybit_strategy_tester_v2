# Unified Indicators Library

## Overview

The `backend.core.indicators` package provides a **single source of truth** for all technical indicator calculations in the project.

**Location**: `backend/core/indicators/`

## Why This Library Exists

Before this library, the project had **15-20 duplicate implementations** of RSI alone, scattered across:

- `signal_generators.py`
- `fast_optimizer.py`
- `gpu_optimizer.py`
- `strategy_builder/indicators.py`
- `mtf/signals.py`
- And more...

This library consolidates all indicator calculations into one place.

## Quick Start

```python
from backend.core.indicators import (
    calculate_rsi,
    calculate_sma,
    calculate_ema,
    calculate_macd,
    calculate_bollinger,
    calculate_atr,
    calculate_stochastic,
)
import numpy as np

# All functions accept numpy arrays
close = np.array([100, 101, 99, 102, 103, ...])

# Momentum indicators
rsi = calculate_rsi(close, period=14)

# Trend indicators
sma = calculate_sma(close, period=20)
ema = calculate_ema(close, period=20)
macd_line, signal_line, histogram = calculate_macd(close)

# Volatility indicators
middle, upper, lower = calculate_bollinger(close, period=20, std_dev=2.0)
atr = calculate_atr(high, low, close, period=14)

# Stochastic
k, d = calculate_stochastic(high, low, close, k_period=14, d_period=3)
```

## Available Indicators

### Momentum (`momentum.py`)

| Function                 | Description                 | Default Parameters             |
| ------------------------ | --------------------------- | ------------------------------ |
| `calculate_rsi()`        | Relative Strength Index     | period=14                      |
| `calculate_rsi_fast()`   | RSI with Numba optimization | period=14                      |
| `calculate_stochastic()` | Stochastic Oscillator       | k_period=14, d_period=3        |
| `calculate_stoch_rsi()`  | Stochastic RSI              | rsi_period=14, stoch_period=14 |
| `calculate_williams_r()` | Williams %R                 | period=14                      |
| `calculate_roc()`        | Rate of Change              | period=12                      |
| `calculate_cmo()`        | Chande Momentum Oscillator  | period=14                      |
| `calculate_mfi()`        | Money Flow Index            | period=14                      |

### Trend (`trend.py`)

| Function                 | Description                | Default Parameters         |
| ------------------------ | -------------------------- | -------------------------- |
| `calculate_sma()`        | Simple Moving Average      | period=20                  |
| `calculate_ema()`        | Exponential Moving Average | period=20                  |
| `calculate_wma()`        | Weighted Moving Average    | period=20                  |
| `calculate_dema()`       | Double EMA                 | period=20                  |
| `calculate_tema()`       | Triple EMA                 | period=20                  |
| `calculate_hull_ma()`    | Hull Moving Average        | period=20                  |
| `calculate_macd()`       | MACD                       | fast=12, slow=26, signal=9 |
| `calculate_supertrend()` | Supertrend                 | period=10, multiplier=3.0  |

### Volatility (`volatility.py`)

| Function                | Description                | Default Parameters                 |
| ----------------------- | -------------------------- | ---------------------------------- |
| `calculate_atr()`       | Average True Range         | period=14                          |
| `calculate_bollinger()` | Bollinger Bands            | period=20, std_dev=2.0             |
| `calculate_keltner()`   | Keltner Channels           | period=20, atr_period=10, mult=2.0 |
| `calculate_donchian()`  | Donchian Channels          | period=20                          |
| `calculate_stddev()`    | Rolling Standard Deviation | period=20                          |

### Volume (`volume.py`)

| Function              | Description        | Default Parameters |
| --------------------- | ------------------ | ------------------ |
| `calculate_obv()`     | On-Balance Volume  | -                  |
| `calculate_vwap()`    | VWAP               | -                  |
| `calculate_pvt()`     | Price Volume Trend | -                  |
| `calculate_ad_line()` | A/D Line           | -                  |
| `calculate_cmf()`     | Chaikin Money Flow | period=20          |

## Performance Optimization

### Numba JIT Compilation

The library includes Numba-optimized versions for performance-critical indicators:

```python
from backend.core.indicators import calculate_rsi_fast

# Uses Numba JIT if available, falls back to pure Python otherwise
rsi = calculate_rsi_fast(close, period=14)
```

### Note on GPU (CuPy)

GPU optimization via CuPy has been **removed** from this library because:

1. The project uses two universal engines that don't require GPU
2. CuPy adds complexity and dependencies
3. Numba provides sufficient optimization for CPU

If GPU optimization is needed in the future, it should be added as a separate optional module.

## Integration Guide

### For Signal Generators

```python
# Before (duplicate code)
def _calculate_rsi(close, period):
    # ... 30 lines of duplicate code ...

# After (use library)
from backend.core.indicators import calculate_rsi

def generate_rsi_signals(candles, period=14):
    rsi = calculate_rsi(candles["close"].values, period)
    # ... generate signals ...
```

### For Strategy Builder

The `strategy_builder/indicators.py` still maintains its own methods for historical reasons, but internally it can delegate to this library.

### For Backtesting Engines

```python
from backend.core.indicators import calculate_rsi, calculate_macd, calculate_atr

# Use in any engine
rsi = calculate_rsi(close, 14)
macd, signal, hist = calculate_macd(close)
atr = calculate_atr(high, low, close, 14)
```

## Return Value Conventions

1. **Single indicator**: Returns `np.ndarray`
2. **Multiple outputs**: Returns `tuple[np.ndarray, ...]`
3. **NaN handling**: First N values (warmup period) are `np.nan`

```python
# Single output
rsi = calculate_rsi(close, 14)  # Returns np.ndarray

# Multiple outputs
k, d = calculate_stochastic(high, low, close)  # Returns tuple
middle, upper, lower = calculate_bollinger(close)  # Returns tuple
macd, signal, hist = calculate_macd(close)  # Returns tuple
```

## Testing

```python
# Quick validation
from backend.core.indicators import calculate_rsi, calculate_sma
import numpy as np

close = np.random.randn(100).cumsum() + 100
rsi = calculate_rsi(close, 14)
sma = calculate_sma(close, 20)

assert len(rsi) == len(close)
assert len(sma) == len(close)
assert np.all(rsi[14:] >= 0) and np.all(rsi[14:] <= 100)
print("OK!")
```

## Migration Checklist

When migrating code to use this library:

- [x] `backend/backtesting/signal_generators.py` - Migrated
- [x] `backend/backtesting/mtf/signals.py` - Migrated (removed 60+ lines)
- [x] `backend/backtesting/mtf/filters.py` - Migrated (removed 90+ lines)
- [x] `backend/ml/rl_trading_agent.py` - Migrated
- [~] `backend/services/strategy_builder/indicators.py` - Class-based API, kept separate
- [~] `backend/backtesting/fast_optimizer.py` - Numba JIT optimized, kept separate
- [~] `backend/backtesting/universal_engine/signal_generator.py` - Numba JIT, kept separate

**Note**: Files marked `[~]` have specialized implementations for performance or API reasons.

## File Structure

```
backend/core/indicators/
├── __init__.py      # Public API exports
├── momentum.py      # RSI, Stochastic, Williams %R, ROC, CMO, MFI
├── trend.py         # SMA, EMA, WMA, DEMA, TEMA, Hull MA, MACD, Supertrend
├── volatility.py    # ATR, Bollinger, Keltner, Donchian, StdDev
├── volume.py        # OBV, VWAP, PVT, A/D Line, CMF
└── rsi_advanced.py  # Advanced RSI Filter (TradingView parity)
```

---

## 🎯 Advanced RSI Filter (TradingView Parity)

The `rsi_advanced.py` module implements the full **RSI - [IN RANGE FILTER OR CROSS SIGNAL]** functionality from TradingView.

### Features

| Feature             | Description                                               |
| ------------------- | --------------------------------------------------------- |
| **Range Filter**    | RSI must be within specified bounds (e.g., 1-50 for long) |
| **Cross Signal**    | RSI must cross specified level (crossover/crossunder)     |
| **Signal Memory**   | Keep signal active for N bars after cross event           |
| **Opposite Signal** | Invert cross logic (long on short cross)                  |
| **BTC Source**      | Use BTC RSI for altcoin trading decisions                 |

### Quick Start

```python
from backend.core.indicators import (
    RSIAdvancedFilter,
    RSIAdvancedConfig,
    apply_rsi_range_filter,
    apply_rsi_cross_filter,
    apply_rsi_combined_filter,
)

# Simple range filter
rsi, long_ok, short_ok = apply_rsi_range_filter(
    close,
    long_lower=1,
    long_upper=50
)

# Cross filter with memory
rsi, long_ok, short_ok = apply_rsi_cross_filter(
    close,
    long_cross_level=30,
    short_cross_level=70,
    memory_bars=5,
)

# Full combined filter
result = apply_rsi_combined_filter(
    close,
    rsi_period=14,
    long_range_lower=20,
    long_range_upper=60,
    long_cross_level=30,
    memory_bars=5,
)
print(f"Long signals: {np.sum(result.long_signals)}")
```

### Filter Modes

#### 1. Pure Range Filter

```python
config = RSIAdvancedConfig(
    use_long_range=True,
    long_range_lower=1,
    long_range_upper=50,
)
# Signal active while RSI is in [1, 50]
```

#### 2. Pure Cross Signal

```python
config = RSIAdvancedConfig(
    use_cross_level=True,
    long_cross_level=30,
)
# Signal only on bar where RSI crosses above 30
```

#### 3. Cross + Memory Window

```python
config = RSIAdvancedConfig(
    use_cross_level=True,
    long_cross_level=30,
    activate_memory=True,
    memory_bars=5,
)
# Signal active for 5 bars after RSI crosses above 30
```

#### 4. Range + Cross (Combined)

```python
config = RSIAdvancedConfig(
    use_long_range=True,
    long_range_lower=20,
    long_range_upper=60,
    use_cross_level=True,
    long_cross_level=30,
    activate_memory=True,
    memory_bars=10,
)
# RSI crossed 30 AND is in range 20-60 AND within 10 bars of cross
```

#### 5. Opposite Logic (Exit Zones)

```python
config = RSIAdvancedConfig(
    use_cross_level=True,
    long_cross_level=30,
    short_cross_level=70,
    opposite_signal=True,
)
# LONG when RSI crosses BELOW 70 (exit overbought)
# SHORT when RSI crosses ABOVE 30 (exit oversold)
```

#### 6. BTC Source for Altcoins

```python
from backend.core.indicators import create_btc_rsi_filter

# When 4H BTC RSI crosses above 40, allow longs on alts for 3 bars
btc_filter = create_btc_rsi_filter(
    btc_close,
    long_cross_level=40,
    memory_bars=3,
)
# Use btc_filter.long_signals to filter altcoin entries
```

### RSIFilterResult Fields

```python
result = filter.apply(close)

result.rsi_values            # RSI array
result.long_signals          # Boolean: when long is allowed
result.short_signals         # Boolean: when short is allowed
result.long_cross_events     # Boolean: actual crossover events
result.short_cross_events    # Boolean: actual crossunder events
result.long_memory_active    # Boolean: memory window active
result.short_memory_active
result.bars_since_long_signal   # Bars since last long cross
result.bars_since_short_signal  # Bars since last short cross
```

---

_Created: 2025-01-29_
_Version: 1.1.0 (Added Advanced RSI Filter)_
