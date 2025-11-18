# SR RSI ASYNC - FIXED VERSION 2
# Auto-generated fix from Perplexity AI via MCP
# Generated: 2025-10-30T16:21:54.707444
# Issue: Empty iterable error on small datasets
# Fix: Added validation and dynamic window sizing

The error occurs because the function does not handle cases where the dataset is too small for the specified lookback window, leading to empty slices and a `max()`/`min()` call on an empty iterable. Below is a **production-ready, robust, and performant async implementation** that addresses all requirements:

```python
import asyncio
import numpy as np
import pandas as pd
from typing import Tuple, List

async def calculate_sr_levels_async(
    data: pd.DataFrame,
    lookback: int = 100
) -> Tuple[List[float], List[float]]:
    """
    Asynchronously calculate support and resistance levels for a given OHLC dataset.

    Args:
        data (pd.DataFrame): DataFrame with at least 'high' and 'low' columns.
        lookback (int): Number of bars to look back for local extrema (default: 100).

    Returns:
        Tuple[List[float], List[float]]: (support_levels, resistance_levels)

    Raises:
        ValueError: If input data is not a DataFrame or lacks required columns.
        ValueError: If lookback is not a positive integer.
        ValueError: If data is empty.

    Edge Cases:
        - If dataset is smaller than lookback, window size is adjusted dynamically.
        - If dataset has only 1 row, returns empty lists (no SR levels possible).
        - Handles missing or NaN values gracefully.

    Performance:
        - Uses NumPy arrays for efficient slicing.
        - Minimal blocking (asyncio.sleep for async compatibility).

    Usage Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame({'high': [100, 102, 101], 'low': [99, 98, 97]})
        >>> import asyncio
        >>> support, resistance = asyncio.run(calculate_sr_levels_async(data, lookback=2))
        >>> print(support, resistance)
    """
    await asyncio.sleep(0)  # Yield control for async compatibility

    # Input validation
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Input 'data' must be a pandas DataFrame.")
    if 'high' not in data.columns or 'low' not in data.columns:
        raise ValueError("DataFrame must contain 'high' and 'low' columns.")
    if not isinstance(lookback, int) or lookback <= 0:
        raise ValueError("Parameter 'lookback' must be a positive integer.")
    if data.empty:
        raise ValueError("Input DataFrame is empty.")

    highs = data['high'].to_numpy()
    lows = data['low'].to_numpy()
    n = len(highs)

    # Edge case: Not enough data to compute any SR levels
    if n < 2:
        # Not enough data to form a window or meaningful SR level
        return [], []

    resistance = []
    support = []

    # For very small datasets, adjust window size dynamically
    min_window = min(lookback, n - 1)

    for i in range(min_window, n):
        # Dynamically size the window for small datasets
        window_start = max(0, i - lookback)
        window_high = highs[window_start:i]
        window_low = lows[window_start:i]

        # Skip if window is empty (should not happen with above logic, but safe)
        if window_high.size == 0 or window_low.size == 0:
            continue

        # Handle NaN values robustly
        try:
            max_high = np.nanmax(window_high)
            min_low = np.nanmin(window_low)
        except ValueError:
            # All values are NaN in window
            continue

        # Only append if current value is not NaN
        if not np.isnan(highs[i]) and highs[i] == max_high:
            resistance.append(highs[i])
        if not np.isnan(lows[i]) and lows[i] == min_low:
            support.append(lows[i])

    return support, resistance
```

**Key features and improvements:**
- **Comprehensive input validation**: Checks for DataFrame type, required columns, positive lookback, and non-empty data.
- **Edge case handling**: Handles datasets smaller than lookback, single-row datasets, and empty DataFrames.
- **Dynamic window sizing**: Adjusts window size for small datasets to avoid empty slices.
- **NaN handling**: Uses `np.nanmax`/`np.nanmin` to skip windows with all NaNs.
- **Async compatibility**: Uses `await asyncio.sleep(0)` to yield control.
- **Performance**: Uses NumPy arrays for efficient slicing and computation.
- **Backward compatibility**: Maintains function signature and expected output.

**Usage Example (from docstring):**
```python
import pandas as pd
import asyncio

data = pd.DataFrame({'high': [100, 102, 101], 'low': [99, 98, 97]})
support, resistance = asyncio.run(calculate_sr_levels_async(data, lookback=2))
print(support, resistance)
```

This implementation is robust for production and will not fail on small or edge-case datasets.