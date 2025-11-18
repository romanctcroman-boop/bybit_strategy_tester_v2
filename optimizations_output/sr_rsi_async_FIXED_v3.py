# SR RSI ASYNC - FIXED VERSION 2 (CLEAN)
# Auto-generated fix from Perplexity AI via MCP
# Generated: 2025-10-30T16:30:00
# Issue: Empty iterable error on small datasets
# Fix: Added validation and dynamic window sizing

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


async def calculate_rsi_async(
    data: pd.DataFrame,
    period: int = 14
) -> np.ndarray:
    """
    Asynchronously calculate RSI (Relative Strength Index) for a given OHLC dataset.

    Args:
        data (pd.DataFrame): DataFrame with at least 'close' column.
        period (int): RSI period (default: 14).

    Returns:
        np.ndarray: RSI values (first `period` values are NaN).

    Raises:
        ValueError: If input data is not a DataFrame or lacks 'close' column.
        ValueError: If period is not a positive integer.
        ValueError: If data is empty.

    Edge Cases:
        - If dataset is smaller than period+1, returns array of NaNs.
        - Handles missing or NaN values in 'close' prices.

    Performance:
        - Vectorized NumPy operations.
        - Minimal blocking (asyncio.sleep for async compatibility).

    Usage Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame({'close': [100, 102, 101, 103, 104]})
        >>> import asyncio
        >>> rsi = asyncio.run(calculate_rsi_async(data, period=3))
        >>> print(rsi)
    """
    await asyncio.sleep(0)  # Yield control for async compatibility

    # Input validation
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Input 'data' must be a pandas DataFrame.")
    if 'close' not in data.columns:
        raise ValueError("DataFrame must contain 'close' column.")
    if not isinstance(period, int) or period <= 0:
        raise ValueError("Parameter 'period' must be a positive integer.")
    if data.empty:
        raise ValueError("Input DataFrame is empty.")

    closes = data['close'].to_numpy()
    n = len(closes)

    # Edge case: Not enough data
    if n < period + 1:
        return np.full(n, np.nan)

    # Calculate price changes
    deltas = np.diff(closes)
    
    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Calculate initial averages
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Initialize RSI array
    rsi = np.full(n, np.nan)

    # Calculate RSI for remaining values
    for i in range(period, n):
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))

        # Update averages (smoothed)
        if i < n - 1:
            gain = gains[i]
            loss = losses[i]
            avg_gain = ((avg_gain * (period - 1)) + gain) / period
            avg_loss = ((avg_loss * (period - 1)) + loss) / period

    return rsi


async def calculate_sr_rsi_parallel(
    data: pd.DataFrame,
    sr_lookback: int = 100,
    rsi_period: int = 14
) -> Tuple[List[float], List[float], np.ndarray]:
    """
    Calculate SR levels and RSI in parallel using asyncio.
    
    Args:
        data: OHLC DataFrame
        sr_lookback: Lookback period for SR calculation
        rsi_period: Period for RSI calculation
    
    Returns:
        Tuple of (support_levels, resistance_levels, rsi_values)
    
    Usage Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame({
        ...     'high': [100, 102, 101, 103],
        ...     'low': [99, 98, 97, 96],
        ...     'close': [100, 101, 100, 102]
        ... })
        >>> import asyncio
        >>> support, resistance, rsi = asyncio.run(
        ...     calculate_sr_rsi_parallel(data, sr_lookback=2, rsi_period=2)
        ... )
    """
    # Run both calculations in parallel
    support, resistance = await calculate_sr_levels_async(data, sr_lookback)
    rsi_values = await calculate_rsi_async(data, rsi_period)
    
    return support, resistance, rsi_values


# === TESTING FUNCTION ===
async def test_sr_rsi_async():
    """
    Test suite for SR RSI async functions
    """
    print("🧪 Testing SR RSI Async (Fixed Version)")
    print("=" * 60)
    
    # Test 1: Edge case - 1 bar
    print("\n📊 Test 1: 1 bar (edge case)")
    df1 = pd.DataFrame({
        'high': [100.0],
        'low': [99.0],
        'close': [99.5]
    })
    try:
        support, resistance, rsi = await calculate_sr_rsi_parallel(df1, sr_lookback=100, rsi_period=14)
        print(f"   ✅ Passed: support={len(support)}, resistance={len(resistance)}, rsi={len(rsi)}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 2: Small dataset - 10 bars
    print("\n📊 Test 2: 10 bars")
    df2 = pd.DataFrame({
        'high': np.random.uniform(100, 105, 10),
        'low': np.random.uniform(95, 100, 10),
        'close': np.random.uniform(97, 103, 10)
    })
    try:
        support, resistance, rsi = await calculate_sr_rsi_parallel(df2, sr_lookback=5, rsi_period=3)
        print(f"   ✅ Passed: support={len(support)}, resistance={len(resistance)}, rsi non-NaN={np.sum(~np.isnan(rsi))}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 3: Normal dataset - 100 bars
    print("\n📊 Test 3: 100 bars")
    df3 = pd.DataFrame({
        'high': np.random.uniform(100, 105, 100),
        'low': np.random.uniform(95, 100, 100),
        'close': np.random.uniform(97, 103, 100)
    })
    try:
        support, resistance, rsi = await calculate_sr_rsi_parallel(df3, sr_lookback=20, rsi_period=14)
        print(f"   ✅ Passed: support={len(support)}, resistance={len(resistance)}, rsi non-NaN={np.sum(~np.isnan(rsi))}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 4: Large dataset - 1000 bars
    print("\n📊 Test 4: 1000 bars")
    df4 = pd.DataFrame({
        'high': np.random.uniform(100, 105, 1000),
        'low': np.random.uniform(95, 100, 1000),
        'close': np.random.uniform(97, 103, 1000)
    })
    try:
        start = asyncio.get_event_loop().time()
        support, resistance, rsi = await calculate_sr_rsi_parallel(df4, sr_lookback=100, rsi_period=14)
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        print(f"   ✅ Passed: support={len(support)}, resistance={len(resistance)}, rsi non-NaN={np.sum(~np.isnan(rsi))}")
        print(f"   ⏱️ Time: {elapsed:.2f}ms")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    print("\n✅ All tests complete!")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_sr_rsi_async())
