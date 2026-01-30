"""
Universal Signal Generator - Генерация сигналов для ВСЕХ типов стратегий.

Поддерживаемые стратегии:
- RSI (period, overbought, oversold)
- MACD (fast, slow, signal)
- Bollinger Bands (period, std_dev)
- Stochastic (k_period, d_period, smooth)
- Moving Average Crossover (fast_ma, slow_ma)
- SuperTrend (atr_period, multiplier)
- Ichimoku (tenkan, kijun, senkou_span_b)
- Custom (через callback)

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Fallback decorators
    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

    prange = range


# =============================================================================
# NUMBA-ACCELERATED INDICATOR CALCULATIONS
# =============================================================================


@njit(cache=True)
def calculate_rsi_numba(close: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate RSI using Numba acceleration.

    Args:
        close: Close prices array
        period: RSI period

    Returns:
        RSI values array (0-100)
    """
    n = len(close)
    rsi = np.full(n, 50.0, dtype=np.float64)

    if n < period + 1:
        return rsi

    # Calculate price changes
    deltas = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        deltas[i] = close[i] - close[i - 1]

    # Calculate initial average gain/loss
    avg_gain = 0.0
    avg_loss = 0.0

    for i in range(1, period + 1):
        if deltas[i] > 0:
            avg_gain += deltas[i]
        else:
            avg_loss -= deltas[i]

    avg_gain /= period
    avg_loss /= period

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Calculate RSI for remaining bars using Wilder smoothing
    for i in range(period + 1, n):
        delta = deltas[i]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


@njit(cache=True)
def calculate_ema_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate EMA using Numba."""
    n = len(data)
    ema = np.zeros(n, dtype=np.float64)

    if n == 0:
        return ema

    multiplier = 2.0 / (period + 1)

    # Initialize with SMA
    if n < period:
        ema[:] = np.mean(data)
        return ema

    ema[period - 1] = np.mean(data[:period])

    for i in range(period, n):
        ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]

    # Backfill
    for i in range(period - 1):
        ema[i] = ema[period - 1]

    return ema


@njit(cache=True)
def calculate_sma_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate SMA using Numba."""
    n = len(data)
    sma = np.zeros(n, dtype=np.float64)

    if n < period:
        return sma

    # Calculate first SMA
    cumsum = 0.0
    for i in range(period):
        cumsum += data[i]
    sma[period - 1] = cumsum / period

    # Rolling calculation
    for i in range(period, n):
        cumsum = cumsum - data[i - period] + data[i]
        sma[i] = cumsum / period

    # Backfill
    for i in range(period - 1):
        sma[i] = sma[period - 1]

    return sma


@njit(cache=True)
def calculate_atr_numba(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> np.ndarray:
    """Calculate ATR using Numba."""
    n = len(close)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)

    if n < 2:
        return atr

    # True Range calculation
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    if n < period:
        return tr  # Return TR if not enough data

    # Initial ATR (SMA of TR)
    atr_sum = 0.0
    for i in range(period):
        atr_sum += tr[i]
    atr[period - 1] = atr_sum / period

    # Wilder smoothing for subsequent ATR
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    # Backfill
    for i in range(period - 1):
        atr[i] = atr[period - 1]

    return atr


@njit(cache=True)
def calculate_macd_numba(
    close: np.ndarray, fast: int, slow: int, signal: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate MACD using Numba."""
    ema_fast = calculate_ema_numba(close, fast)
    ema_slow = calculate_ema_numba(close, slow)

    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema_numba(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


@njit(cache=True)
def calculate_bollinger_numba(
    close: np.ndarray, period: int, std_dev: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate Bollinger Bands using Numba."""
    n = len(close)
    middle = calculate_sma_numba(close, period)
    upper = np.zeros(n, dtype=np.float64)
    lower = np.zeros(n, dtype=np.float64)

    for i in range(period - 1, n):
        # Calculate standard deviation
        mean = middle[i]
        variance = 0.0
        for j in range(i - period + 1, i + 1):
            variance += (close[j] - mean) ** 2
        std = np.sqrt(variance / period)

        upper[i] = mean + std_dev * std
        lower[i] = mean - std_dev * std

    # Backfill
    for i in range(period - 1):
        upper[i] = upper[period - 1]
        lower[i] = lower[period - 1]

    return upper, middle, lower


@njit(cache=True)
def calculate_stochastic_numba(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int,
    d_period: int,
    smooth: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate Stochastic Oscillator using Numba."""
    n = len(close)
    k_raw = np.zeros(n, dtype=np.float64)

    for i in range(k_period - 1, n):
        highest = high[i]
        lowest = low[i]
        for j in range(i - k_period + 1, i + 1):
            if high[j] > highest:
                highest = high[j]
            if low[j] < lowest:
                lowest = low[j]

        if highest - lowest > 0:
            k_raw[i] = ((close[i] - lowest) / (highest - lowest)) * 100
        else:
            k_raw[i] = 50.0

    # Smooth %K
    k = calculate_sma_numba(k_raw, smooth) if smooth > 1 else k_raw

    # %D is SMA of %K
    d = calculate_sma_numba(k, d_period)

    return k, d


@njit(cache=True)
def calculate_supertrend_numba(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int,
    multiplier: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate SuperTrend indicator using Numba.

    Returns:
        supertrend: SuperTrend line values
        direction: 1 for uptrend, -1 for downtrend
    """
    n = len(close)
    atr = calculate_atr_numba(high, low, close, atr_period)

    supertrend = np.zeros(n, dtype=np.float64)
    direction = np.ones(n, dtype=np.float64)  # 1 = uptrend, -1 = downtrend

    upper_band = np.zeros(n, dtype=np.float64)
    lower_band = np.zeros(n, dtype=np.float64)

    for i in range(n):
        hl2 = (high[i] + low[i]) / 2
        upper_band[i] = hl2 + multiplier * atr[i]
        lower_band[i] = hl2 - multiplier * atr[i]

    for i in range(1, n):
        # Adjust bands
        if lower_band[i] > lower_band[i - 1] or close[i - 1] < lower_band[i - 1]:
            pass  # Keep current lower_band
        else:
            lower_band[i] = lower_band[i - 1]

        if upper_band[i] < upper_band[i - 1] or close[i - 1] > upper_band[i - 1]:
            pass  # Keep current upper_band
        else:
            upper_band[i] = upper_band[i - 1]

        # Determine trend
        if direction[i - 1] == 1:  # Was uptrend
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

    supertrend[0] = lower_band[0]

    return supertrend, direction


# =============================================================================
# RSI SIGNAL GENERATION
# =============================================================================


@njit(cache=True)
def generate_rsi_signals_numba(
    rsi: np.ndarray,
    oversold: float,
    overbought: float,
    direction: int,  # 0=long, 1=short, 2=both
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate RSI signals using Numba.

    Args:
        rsi: RSI values
        oversold: Oversold threshold (e.g., 30)
        overbought: Overbought threshold (e.g., 70)
        direction: 0=long only, 1=short only, 2=both

    Returns:
        long_entries, long_exits, short_entries, short_exits
    """
    n = len(rsi)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Long signals
        if direction == 0 or direction == 2:
            # Long entry: RSI crosses above oversold
            if rsi[i - 1] <= oversold < rsi[i]:
                long_entries[i] = True
            # Long exit: RSI crosses above overbought
            if rsi[i - 1] <= overbought < rsi[i]:
                long_exits[i] = True

        # Short signals
        if direction == 1 or direction == 2:
            # Short entry: RSI crosses below overbought
            if rsi[i - 1] >= overbought > rsi[i]:
                short_entries[i] = True
            # Short exit: RSI crosses below oversold
            if rsi[i - 1] >= oversold > rsi[i]:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


@njit(cache=True)
def generate_macd_signals_numba(
    macd_line: np.ndarray,
    signal_line: np.ndarray,
    histogram: np.ndarray,
    direction: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate MACD crossover signals."""
    n = len(macd_line)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Bullish crossover: MACD crosses above signal
        bullish_cross = (
            macd_line[i - 1] <= signal_line[i - 1] and macd_line[i] > signal_line[i]
        )
        # Bearish crossover: MACD crosses below signal
        bearish_cross = (
            macd_line[i - 1] >= signal_line[i - 1] and macd_line[i] < signal_line[i]
        )

        if direction == 0 or direction == 2:
            if bullish_cross:
                long_entries[i] = True
            if bearish_cross:
                long_exits[i] = True

        if direction == 1 or direction == 2:
            if bearish_cross:
                short_entries[i] = True
            if bullish_cross:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


@njit(cache=True)
def generate_bb_signals_numba(
    close: np.ndarray, upper: np.ndarray, lower: np.ndarray, direction: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate Bollinger Bands mean reversion signals."""
    n = len(close)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Long: price touches lower band
        if direction == 0 or direction == 2:
            if close[i - 1] >= lower[i - 1] and close[i] < lower[i]:
                long_entries[i] = True
            if close[i - 1] <= upper[i - 1] and close[i] > upper[i]:
                long_exits[i] = True

        # Short: price touches upper band
        if direction == 1 or direction == 2:
            if close[i - 1] <= upper[i - 1] and close[i] > upper[i]:
                short_entries[i] = True
            if close[i - 1] >= lower[i - 1] and close[i] < lower[i]:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


@njit(cache=True)
def generate_stoch_signals_numba(
    k: np.ndarray, d: np.ndarray, oversold: float, overbought: float, direction: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate Stochastic signals."""
    n = len(k)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # K crosses above D in oversold zone = bullish
        bullish = k[i] > d[i] and k[i - 1] <= d[i - 1] and k[i] < oversold + 10
        # K crosses below D in overbought zone = bearish
        bearish = k[i] < d[i] and k[i - 1] >= d[i - 1] and k[i] > overbought - 10

        if direction == 0 or direction == 2:
            if bullish:
                long_entries[i] = True
            if bearish:
                long_exits[i] = True

        if direction == 1 or direction == 2:
            if bearish:
                short_entries[i] = True
            if bullish:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


@njit(cache=True)
def generate_supertrend_signals_numba(
    direction_arr: np.ndarray,  # 1 = uptrend, -1 = downtrend
    signal_direction: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate SuperTrend signals."""
    n = len(direction_arr)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Trend change: downtrend to uptrend
        bullish_flip = direction_arr[i - 1] == -1 and direction_arr[i] == 1
        # Trend change: uptrend to downtrend
        bearish_flip = direction_arr[i - 1] == 1 and direction_arr[i] == -1

        if signal_direction == 0 or signal_direction == 2:
            if bullish_flip:
                long_entries[i] = True
            if bearish_flip:
                long_exits[i] = True

        if signal_direction == 1 or signal_direction == 2:
            if bearish_flip:
                short_entries[i] = True
            if bullish_flip:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


@njit(cache=True)
def generate_ma_crossover_signals_numba(
    fast_ma: np.ndarray, slow_ma: np.ndarray, direction: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate Moving Average crossover signals."""
    n = len(fast_ma)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Golden cross: fast crosses above slow
        golden = fast_ma[i - 1] <= slow_ma[i - 1] and fast_ma[i] > slow_ma[i]
        # Death cross: fast crosses below slow
        death = fast_ma[i - 1] >= slow_ma[i - 1] and fast_ma[i] < slow_ma[i]

        if direction == 0 or direction == 2:
            if golden:
                long_entries[i] = True
            if death:
                long_exits[i] = True

        if direction == 1 or direction == 2:
            if death:
                short_entries[i] = True
            if golden:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


# =============================================================================
# MAIN SIGNAL GENERATOR CLASS
# =============================================================================


@dataclass
class SignalOutput:
    """Output from signal generator."""

    long_entries: np.ndarray
    long_exits: np.ndarray
    short_entries: np.ndarray
    short_exits: np.ndarray
    indicator_values: Dict[str, np.ndarray]


class UniversalSignalGenerator:
    """
    Universal signal generator for ALL strategy types.

    Supports:
    - RSI (period, overbought, oversold)
    - MACD (fast, slow, signal)
    - Bollinger Bands (period, std_dev)
    - Stochastic (k_period, d_period, smooth)
    - Moving Average Crossover (fast_period, slow_period, ma_type)
    - SuperTrend (atr_period, multiplier)
    - Custom (via callback function)
    """

    STRATEGY_TYPES = {
        "rsi": ["period", "overbought", "oversold"],
        "macd": ["fast_period", "slow_period", "signal_period"],
        "bollinger": ["period", "std_dev"],
        "stochastic": ["k_period", "d_period", "smooth", "overbought", "oversold"],
        "ma_crossover": ["fast_period", "slow_period", "ma_type"],
        "supertrend": ["atr_period", "multiplier"],
        "custom": [],
    }

    DEFAULT_PARAMS = {
        "rsi": {"period": 14, "overbought": 70, "oversold": 30},
        "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "bollinger": {"period": 20, "std_dev": 2.0},
        "stochastic": {
            "k_period": 14,
            "d_period": 3,
            "smooth": 3,
            "overbought": 80,
            "oversold": 20,
        },
        "ma_crossover": {"fast_period": 10, "slow_period": 50, "ma_type": "ema"},
        "supertrend": {"atr_period": 10, "multiplier": 3.0},
    }

    def __init__(self, use_numba: bool = True):
        """
        Initialize signal generator.

        Args:
            use_numba: Use Numba acceleration if available
        """
        self.use_numba = use_numba and NUMBA_AVAILABLE
        self._custom_generators: Dict[str, Callable] = {}

        if self.use_numba:
            logger.debug("UniversalSignalGenerator: Numba acceleration enabled")
        else:
            logger.debug("UniversalSignalGenerator: Using pure Python")

    def register_custom_strategy(self, name: str, generator_func: Callable):
        """
        Register a custom signal generator.

        Args:
            name: Strategy name
            generator_func: Function(candles, params, direction) -> SignalOutput
        """
        self._custom_generators[name] = generator_func
        logger.info(f"Registered custom strategy: {name}")

    def generate(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        strategy_params: Dict[str, Any],
        direction: str = "both",  # "long", "short", "both"
    ) -> SignalOutput:
        """
        Generate trading signals.

        Args:
            candles: OHLCV DataFrame with columns: open, high, low, close, volume
            strategy_type: One of STRATEGY_TYPES keys or custom registered name
            strategy_params: Strategy-specific parameters
            direction: Trading direction

        Returns:
            SignalOutput with entry/exit signals and indicator values
        """
        # Convert direction to int for Numba
        dir_map = {"long": 0, "short": 1, "both": 2}
        dir_int = dir_map.get(direction.lower(), 2)

        # Extract OHLCV
        close = candles["close"].values.astype(np.float64)
        high = candles["high"].values.astype(np.float64) if "high" in candles else close
        low = candles["low"].values.astype(np.float64) if "low" in candles else close

        # Merge with defaults
        defaults = self.DEFAULT_PARAMS.get(strategy_type, {})
        params = {**defaults, **strategy_params}

        # Generate signals based on strategy type
        if strategy_type == "rsi":
            return self._generate_rsi(close, params, dir_int)
        elif strategy_type == "macd":
            return self._generate_macd(close, params, dir_int)
        elif strategy_type == "bollinger":
            return self._generate_bollinger(close, params, dir_int)
        elif strategy_type == "stochastic":
            return self._generate_stochastic(high, low, close, params, dir_int)
        elif strategy_type == "ma_crossover":
            return self._generate_ma_crossover(close, params, dir_int)
        elif strategy_type == "supertrend":
            return self._generate_supertrend(high, low, close, params, dir_int)
        elif strategy_type in self._custom_generators:
            return self._custom_generators[strategy_type](candles, params, direction)
        else:
            raise ValueError(
                f"Unknown strategy type: {strategy_type}. "
                f"Available: {list(self.STRATEGY_TYPES.keys())} + {list(self._custom_generators.keys())}"
            )

    def _generate_rsi(
        self, close: np.ndarray, params: Dict, direction: int
    ) -> SignalOutput:
        """Generate RSI signals."""
        period = int(params.get("period", 14))
        overbought = float(params.get("overbought", 70))
        oversold = float(params.get("oversold", 30))

        rsi = calculate_rsi_numba(close, period)
        long_entries, long_exits, short_entries, short_exits = (
            generate_rsi_signals_numba(rsi, oversold, overbought, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={"rsi": rsi},
        )

    def _generate_macd(
        self, close: np.ndarray, params: Dict, direction: int
    ) -> SignalOutput:
        """Generate MACD signals."""
        fast = int(params.get("fast_period", 12))
        slow = int(params.get("slow_period", 26))
        signal = int(params.get("signal_period", 9))

        macd_line, signal_line, histogram = calculate_macd_numba(
            close, fast, slow, signal
        )
        long_entries, long_exits, short_entries, short_exits = (
            generate_macd_signals_numba(macd_line, signal_line, histogram, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={
                "macd": macd_line,
                "signal": signal_line,
                "histogram": histogram,
            },
        )

    def _generate_bollinger(
        self, close: np.ndarray, params: Dict, direction: int
    ) -> SignalOutput:
        """Generate Bollinger Bands signals."""
        period = int(params.get("period", 20))
        std_dev = float(params.get("std_dev", 2.0))

        upper, middle, lower = calculate_bollinger_numba(close, period, std_dev)
        long_entries, long_exits, short_entries, short_exits = (
            generate_bb_signals_numba(close, upper, lower, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={
                "bb_upper": upper,
                "bb_middle": middle,
                "bb_lower": lower,
            },
        )

    def _generate_stochastic(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        params: Dict,
        direction: int,
    ) -> SignalOutput:
        """Generate Stochastic signals."""
        k_period = int(params.get("k_period", 14))
        d_period = int(params.get("d_period", 3))
        smooth = int(params.get("smooth", 3))
        overbought = float(params.get("overbought", 80))
        oversold = float(params.get("oversold", 20))

        k, d = calculate_stochastic_numba(high, low, close, k_period, d_period, smooth)
        long_entries, long_exits, short_entries, short_exits = (
            generate_stoch_signals_numba(k, d, oversold, overbought, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={"stoch_k": k, "stoch_d": d},
        )

    def _generate_ma_crossover(
        self, close: np.ndarray, params: Dict, direction: int
    ) -> SignalOutput:
        """Generate MA crossover signals."""
        fast_period = int(params.get("fast_period", 10))
        slow_period = int(params.get("slow_period", 50))
        ma_type = params.get("ma_type", "ema").lower()

        if ma_type == "ema":
            fast_ma = calculate_ema_numba(close, fast_period)
            slow_ma = calculate_ema_numba(close, slow_period)
        else:  # SMA
            fast_ma = calculate_sma_numba(close, fast_period)
            slow_ma = calculate_sma_numba(close, slow_period)

        long_entries, long_exits, short_entries, short_exits = (
            generate_ma_crossover_signals_numba(fast_ma, slow_ma, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={"fast_ma": fast_ma, "slow_ma": slow_ma},
        )

    def _generate_supertrend(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        params: Dict,
        direction: int,
    ) -> SignalOutput:
        """Generate SuperTrend signals."""
        atr_period = int(params.get("atr_period", 10))
        multiplier = float(params.get("multiplier", 3.0))

        supertrend, trend_direction = calculate_supertrend_numba(
            high, low, close, atr_period, multiplier
        )
        long_entries, long_exits, short_entries, short_exits = (
            generate_supertrend_signals_numba(trend_direction, direction)
        )

        return SignalOutput(
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            indicator_values={
                "supertrend": supertrend,
                "trend_direction": trend_direction,
            },
        )

    def get_indicator_values(
        self, candles: pd.DataFrame, strategy_type: str, strategy_params: Dict[str, Any]
    ) -> Dict[str, np.ndarray]:
        """
        Get indicator values without generating signals.
        Useful for visualization and debugging.
        """
        output = self.generate(candles, strategy_type, strategy_params, "both")
        return output.indicator_values
