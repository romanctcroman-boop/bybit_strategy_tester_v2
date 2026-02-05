"""
Multi-Timeframe (MTF) Utilities for Strategy Builder.

Provides functions to resample OHLCV data to higher timeframes
and calculate indicators across multiple timeframes.

Session 5.5 Implementation.
"""


import numpy as np
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """
    Resample OHLCV data to a higher timeframe.
    
    Args:
        df: DataFrame with OHLCV columns and datetime index or 'timestamp' column
        target_tf: Target timeframe (e.g., '1h', '4h', '1D')
    
    Returns:
        Resampled DataFrame with OHLCV data
    """
    # Ensure we have a datetime index
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')

    # Convert target_tf to pandas resample rule
    tf_map = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1h',
        '4h': '4h',
        '1D': '1D',
        '1W': '1W',
        'Chart': None,  # No resampling needed
    }

    rule = tf_map.get(target_tf)
    if rule is None:
        return df

    # Resample OHLCV
    resampled = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    return resampled


def map_higher_tf_to_base(base_df: pd.DataFrame, higher_tf_df: pd.DataFrame,
                          values: np.ndarray) -> np.ndarray:
    """
    Map values from higher timeframe back to base timeframe.
    
    Each bar in base timeframe gets the value from the corresponding
    (or most recent) higher timeframe bar.
    
    Args:
        base_df: Base timeframe DataFrame with datetime index
        higher_tf_df: Higher timeframe DataFrame with datetime index
        values: Values calculated on higher timeframe
    
    Returns:
        Values mapped to base timeframe length
    """
    result = np.zeros(len(base_df))

    higher_times = higher_tf_df.index.values
    base_times = base_df.index.values

    j = 0
    for i, base_time in enumerate(base_times):
        # Find the most recent higher TF bar
        while j < len(higher_times) - 1 and higher_times[j + 1] <= base_time:
            j += 1

        if j < len(values):
            result[i] = values[j]

    return result


def calculate_supertrend_mtf(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                              period: int = 10, multiplier: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate SuperTrend indicator.
    
    Returns:
        Tuple of (supertrend_values, direction) where direction is 1 for uptrend, -1 for downtrend
    """
    length = len(close)

    # Calculate ATR
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - np.roll(close, 1)),
                              np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]

    atr = np.zeros(length)
    atr[0] = tr[0]
    for i in range(1, length):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    # Calculate bands
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    # Calculate SuperTrend
    supertrend = np.zeros(length)
    direction = np.ones(length)  # 1 = uptrend, -1 = downtrend

    supertrend[0] = upper_band[0]
    direction[0] = -1

    for i in range(1, length):
        # Update bands
        if lower_band[i] > lower_band[i-1] or close[i-1] < lower_band[i-1]:
            pass  # Keep current lower band
        else:
            lower_band[i] = lower_band[i-1]

        if upper_band[i] < upper_band[i-1] or close[i-1] > upper_band[i-1]:
            pass  # Keep current upper band
        else:
            upper_band[i] = upper_band[i-1]

        # Determine direction
        if direction[i-1] == 1:  # Was uptrend
            if close[i] < lower_band[i]:
                direction[i] = -1
                supertrend[i] = upper_band[i]
            else:
                direction[i] = 1
                supertrend[i] = lower_band[i]
        else:  # Was downtrend
            if close[i] > upper_band[i]:
                direction[i] = 1
                supertrend[i] = lower_band[i]
            else:
                direction[i] = -1
                supertrend[i] = upper_band[i]

    return supertrend, direction


def calculate_rsi_mtf(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate RSI indicator."""
    delta = np.diff(close, prepend=close[0])
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)

    avg_gain = np.zeros_like(close)
    avg_loss = np.zeros_like(close)

    if len(close) > period:
        avg_gain[period] = np.mean(gains[1:period + 1])
        avg_loss[period] = np.mean(losses[1:period + 1])

        for i in range(period + 1, len(close)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
    rsi = 100 - (100 / (1 + rs))
    return rsi


class MTFIndicatorCalculator:
    """
    Calculator for multi-timeframe indicators.
    
    Usage:
        calc = MTFIndicatorCalculator(base_df)
        calc.add_timeframe('1h')
        calc.add_timeframe('4h')
        
        st_1h = calc.supertrend('1h', period=10, multiplier=3.0)
        rsi_4h = calc.rsi('4h', period=14)
    """

    def __init__(self, base_df: pd.DataFrame):
        """Initialize with base timeframe data."""
        self.base_df = base_df
        self.timeframes: dict[str, pd.DataFrame] = {'Chart': base_df}
        self._cache: dict[str, np.ndarray] = {}

    def add_timeframe(self, tf: str) -> None:
        """Add a higher timeframe."""
        if tf not in self.timeframes and tf != 'Chart':
            self.timeframes[tf] = resample_ohlcv(self.base_df.copy(), tf)

    def supertrend(self, tf: str, period: int = 10, multiplier: float = 3.0,
                   return_direction: bool = False) -> np.ndarray:
        """
        Calculate SuperTrend on specified timeframe, mapped to base TF.
        
        Args:
            tf: Timeframe to calculate on
            period: ATR period
            multiplier: ATR multiplier
            return_direction: If True, return direction instead of ST value
        
        Returns:
            SuperTrend values or direction mapped to base timeframe
        """
        cache_key = f"supertrend_{tf}_{period}_{multiplier}"
        dir_cache_key = f"supertrend_dir_{tf}_{period}_{multiplier}"

        if cache_key not in self._cache:
            self.add_timeframe(tf)
            df = self.timeframes[tf]

            st, direction = calculate_supertrend_mtf(
                df['high'].values, df['low'].values, df['close'].values,
                period, multiplier
            )

            if tf == 'Chart':
                self._cache[cache_key] = st
                self._cache[dir_cache_key] = direction
            else:
                self._cache[cache_key] = map_higher_tf_to_base(self.base_df, df, st)
                self._cache[dir_cache_key] = map_higher_tf_to_base(self.base_df, df, direction)

        return self._cache[dir_cache_key] if return_direction else self._cache[cache_key]

    def rsi(self, tf: str, period: int = 14) -> np.ndarray:
        """
        Calculate RSI on specified timeframe, mapped to base TF.
        """
        cache_key = f"rsi_{tf}_{period}"

        if cache_key not in self._cache:
            self.add_timeframe(tf)
            df = self.timeframes[tf]

            rsi = calculate_rsi_mtf(df['close'].values, period)

            if tf == 'Chart':
                self._cache[cache_key] = rsi
            else:
                self._cache[cache_key] = map_higher_tf_to_base(self.base_df, df, rsi)

        return self._cache[cache_key]

    def clear_cache(self) -> None:
        """Clear indicator cache."""
        self._cache.clear()


def apply_mtf_filters(base_df: pd.DataFrame, config: dict) -> np.ndarray:
    """
    Apply MTF filters based on configuration.
    
    Args:
        base_df: Base timeframe OHLCV data
        config: Configuration dictionary with MTF settings
    
    Returns:
        Boolean array where True means all MTF filters pass
    """
    calc = MTFIndicatorCalculator(base_df)
    result = np.ones(len(base_df), dtype=bool)

    # SuperTrend TF2
    if config.get('use_supertrend_tf2', False):
        tf = config.get('supertrend_tf2_timeframe', '1h')
        period = config.get('supertrend_tf2_period', 10)
        mult = config.get('supertrend_tf2_multiplier', 3.0)
        opposite = config.get('supertrend_tf2_opposite', False)

        direction = calc.supertrend(tf, period, mult, return_direction=True)

        # direction: 1 = uptrend (bullish), -1 = downtrend (bearish)
        if opposite:
            direction = -direction

        # For long signals, require uptrend; for short, require downtrend
        # This returns the direction which can be used as a filter
        result = result & (direction == 1)  # Simplified: only allow longs in uptrend

    # SuperTrend TF3
    if config.get('use_supertrend_tf3', False):
        tf = config.get('supertrend_tf3_timeframe', '4h')
        period = config.get('supertrend_tf3_period', 10)
        mult = config.get('supertrend_tf3_multiplier', 3.0)
        opposite = config.get('supertrend_tf3_opposite', False)

        direction = calc.supertrend(tf, period, mult, return_direction=True)

        if opposite:
            direction = -direction

        result = result & (direction == 1)

    # RSI TF2
    if config.get('use_rsi_tf2', False):
        tf = config.get('rsi_tf2_timeframe', '1h')
        period = config.get('rsi_tf2_period', 14)
        rsi = calc.rsi(tf, period)

        long_more = config.get('rsi_tf2_long_more', 1)
        long_less = config.get('rsi_tf2_long_less', 50)

        result = result & (rsi > long_more) & (rsi < long_less)

    # RSI TF3
    if config.get('use_rsi_tf3', False):
        tf = config.get('rsi_tf3_timeframe', '4h')
        period = config.get('rsi_tf3_period', 14)
        rsi = calc.rsi(tf, period)

        long_more = config.get('rsi_tf3_long_more', 1)
        long_less = config.get('rsi_tf3_long_less', 50)

        result = result & (rsi > long_more) & (rsi < long_less)

    return result
