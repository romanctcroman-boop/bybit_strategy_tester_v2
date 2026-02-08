"""
📍 HTF Index Mapping Module

Creates mapping from LTF (Lower Timeframe) bars to HTF (Higher Timeframe) bars.
Critical for preventing lookahead bias in multi-timeframe backtesting.

Key Concept:
- On LTF bar i, we can only see the LAST CLOSED HTF bar
- This prevents using future HTF information (lookahead bias)
- Matches TradingView's `barmerge.lookahead_off` behavior

Example:
    HTF (1H):  |----Bar 0----|----Bar 1----|----Bar 2----|
    LTF (5m):  |0|1|2|3|4|5|6|7|8|9|10|11|12|13|14|...

    At LTF bar 6 (still within HTF Bar 1):
    - lookahead_mode="none": sees HTF Bar 0 (last CLOSED)
    - lookahead_mode="allow": sees HTF Bar 1 (current, incomplete)
"""


import numpy as np


def interval_to_minutes(interval: str) -> int | None:
    """
    Convert interval string to minutes.

    Args:
        interval: Interval string (e.g., '1', '5', '15', '60', '240', 'D', 'W')

    Returns:
        Number of minutes, or None if unable to parse

    Examples:
        >>> interval_to_minutes('5')
        5
        >>> interval_to_minutes('60')
        60
        >>> interval_to_minutes('D')
        1440
    """
    try:
        # Handle numeric intervals (assume minutes)
        if interval.isdigit():
            return int(interval)

        # Handle special intervals
        interval_map = {
            "D": 1440,  # 1 day = 1440 minutes
            "W": 10080,  # 1 week = 10080 minutes
            "M": 43200,  # 1 month ≈ 30 days
        }
        return interval_map.get(interval.upper())
    except Exception:
        return None


def calculate_bars_ratio(ltf_interval: str, htf_interval: str) -> int:
    """
    Calculate how many LTF bars fit in one HTF bar.

    Args:
        ltf_interval: Lower timeframe interval string
        htf_interval: Higher timeframe interval string

    Returns:
        Number of LTF bars per HTF bar

    Raises:
        ValueError: If intervals cannot be parsed or HTF < LTF

    Examples:
        >>> calculate_bars_ratio('5', '60')
        12
        >>> calculate_bars_ratio('15', '240')
        16
    """
    ltf_minutes = interval_to_minutes(ltf_interval)
    htf_minutes = interval_to_minutes(htf_interval)

    if ltf_minutes is None or htf_minutes is None:
        raise ValueError(
            f"Cannot parse intervals: LTF={ltf_interval}, HTF={htf_interval}"
        )

    if htf_minutes < ltf_minutes:
        raise ValueError(f"HTF ({htf_interval}) must be >= LTF ({ltf_interval})")

    return htf_minutes // ltf_minutes


def _extract_timestamps(data) -> np.ndarray:
    """
    Extract timestamps from various input types.

    Args:
        data: Can be:
            - np.ndarray of timestamps (int64 or datetime64)
            - pd.DataFrame with 'time' column
            - pd.Series of timestamps

    Returns:
        np.ndarray of int64 timestamps (milliseconds)
    """
    import pandas as pd

    # If DataFrame, extract 'time' column
    if isinstance(data, pd.DataFrame):
        if "time" not in data.columns:
            # If no time column, use index as synthetic timestamps
            return np.arange(len(data), dtype=np.int64)
        data = data["time"].values

    # If Series, convert to array
    if isinstance(data, pd.Series):
        data = data.values

    # Now we have an array, convert to int64
    if hasattr(data, "dtype"):
        if data.dtype.kind == "M":  # datetime64
            return data.astype("datetime64[ms]").astype(np.int64)
        elif data.dtype == np.int64:
            return data
        else:
            return data.astype(np.int64)

    # Fallback: try to convert
    return np.asarray(data, dtype=np.int64)


def create_htf_index_map(
    ltf_timestamps, htf_timestamps, lookahead_mode: str = "none"
) -> np.ndarray:
    """
    Create mapping from LTF bars to HTF bars with lookahead prevention.

    This is the core function for MTF backtesting. It ensures that at each
    LTF bar, we only have access to HTF data that was already available
    at that point in time (no future peeking).

    Args:
        ltf_timestamps: LTF bar open times - can be:
            - np.ndarray of timestamps (milliseconds or datetime64)
            - pd.DataFrame with 'time' column
            - pd.Series of timestamps
        htf_timestamps: HTF bar open times (same formats supported)
        lookahead_mode: "none" (default, safe) or "allow" (research only)

    Returns:
        Array where htf_index_map[i] = index of HTF bar visible at LTF bar i
        Returns -1 if no HTF bar is available yet

    Example:
        # 5m LTF bars: [09:00, 09:05, 09:10, 09:15, ...]
        # 1H HTF bars: [09:00, 10:00, 11:00, ...]
        #
        # With lookahead_mode="none":
        # LTF 09:00-09:55 (12 bars) → HTF index -1 (no closed HTF bar yet)
        # LTF 10:00-10:55 (12 bars) → HTF index 0 (09:00 bar closed)
        # LTF 11:00-11:55 (12 bars) → HTF index 1 (10:00 bar closed)
    """
    # Extract timestamps from various input types
    ltf_ts = _extract_timestamps(ltf_timestamps)
    htf_ts = _extract_timestamps(htf_timestamps)

    n_ltf = len(ltf_ts)
    n_htf = len(htf_ts)

    if n_ltf == 0 or n_htf == 0:
        return np.full(n_ltf, -1, dtype=np.int32)

    # Result array: -1 means no HTF bar available yet
    htf_index_map = np.full(n_ltf, -1, dtype=np.int32)

    # For each LTF bar, find the visible HTF bar
    htf_idx = -1  # Start before any HTF bar

    for i in range(n_ltf):
        ltf_time = ltf_ts[i]

        if lookahead_mode == "none":
            # STRICT MODE: Only see CLOSED HTF bars
            # HTF bar N is visible only after its close time (= HTF bar N+1 open time)
            while htf_idx + 1 < n_htf:
                # Check if HTF bar (htf_idx + 1) has STARTED
                # (meaning HTF bar htf_idx has CLOSED)
                next_htf_open = htf_ts[htf_idx + 1]
                if ltf_time >= next_htf_open:
                    htf_idx += 1
                else:
                    break
        else:
            # PERMISSIVE MODE: Can see current forming HTF bar
            # Used for research/comparison only
            while htf_idx + 1 < n_htf:
                next_htf_open = htf_ts[htf_idx + 1]
                if ltf_time >= next_htf_open:
                    htf_idx += 1
                else:
                    break

        # In strict mode, we need to subtract 1 because htf_idx points to
        # the current forming bar, but we want the last CLOSED bar
        if lookahead_mode == "none":
            htf_index_map[i] = htf_idx - 1 if htf_idx >= 0 else -1
        else:
            htf_index_map[i] = htf_idx

    return htf_index_map


def get_htf_bar_at_ltf(
    ltf_bar_idx: int,
    htf_index_map: np.ndarray,
    htf_candles_close: np.ndarray,
    htf_candles_high: np.ndarray | None = None,
    htf_candles_low: np.ndarray | None = None,
    htf_candles_open: np.ndarray | None = None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Get HTF OHLC values visible at a specific LTF bar.

    Args:
        ltf_bar_idx: Index of the LTF bar
        htf_index_map: Mapping array from create_htf_index_map()
        htf_candles_close: HTF close prices
        htf_candles_high: HTF high prices (optional)
        htf_candles_low: HTF low prices (optional)
        htf_candles_open: HTF open prices (optional)

    Returns:
        Tuple of (open, high, low, close) or None values if HTF not available

    Example:
        >>> htf_ohlc = get_htf_bar_at_ltf(100, htf_map, htf_close, htf_high, htf_low, htf_open)
        >>> htf_open, htf_high, htf_low, htf_close = htf_ohlc
    """
    if ltf_bar_idx >= len(htf_index_map):
        return None, None, None, None

    htf_idx = htf_index_map[ltf_bar_idx]
    if htf_idx < 0 or htf_idx >= len(htf_candles_close):
        return None, None, None, None

    htf_close = htf_candles_close[htf_idx]
    htf_high = htf_candles_high[htf_idx] if htf_candles_high is not None else None
    htf_low = htf_candles_low[htf_idx] if htf_candles_low is not None else None
    htf_open = htf_candles_open[htf_idx] if htf_candles_open is not None else None

    return htf_open, htf_high, htf_low, htf_close


def validate_htf_index_map(
    htf_index_map: np.ndarray, n_htf: int, ltf_interval: str, htf_interval: str
) -> tuple[bool, str]:
    """
    Validate HTF index map for correctness.

    Args:
        htf_index_map: The index mapping array
        n_htf: Number of HTF bars
        ltf_interval: LTF interval string
        htf_interval: HTF interval string

    Returns:
        Tuple of (is_valid, message)
    """
    if len(htf_index_map) == 0:
        return False, "Empty index map"

    # Check for invalid indices (except -1 which is valid)
    max_idx = htf_index_map.max()
    if max_idx >= n_htf:
        return False, f"HTF index {max_idx} exceeds HTF bar count {n_htf}"

    # Check monotonicity (index should never decrease)
    for i in range(1, len(htf_index_map)):
        if htf_index_map[i] < htf_index_map[i - 1] and htf_index_map[i] != -1:
            return (
                False,
                f"Non-monotonic at LTF bar {i}: {htf_index_map[i]} < {htf_index_map[i - 1]}",
            )

    # Check expected ratio
    expected_ratio = calculate_bars_ratio(ltf_interval, htf_interval)
    valid_indices = htf_index_map[htf_index_map >= 0]
    if len(valid_indices) > 0:
        # Count transitions
        transitions = np.sum(np.diff(valid_indices) > 0)
        expected_transitions = len(valid_indices) // expected_ratio
        # Allow 10% tolerance
        if transitions < expected_transitions * 0.9 - 1:
            return (
                False,
                f"Unexpected transition count: {transitions} vs expected ~{expected_transitions}",
            )

    return True, "Valid"
