"""
Advanced RSI Filter Module - TradingView Parity

Implements the full RSI - [IN RANGE FILTER OR CROSS SIGNAL] functionality:
- Range Filters (Long/Short with upper/lower bounds)
- Cross Level Signals (crossover/crossunder detection)
- Signal Memory (keep signal active for N bars)
- Opposite Signal Logic (inverted entries)
- BTC as Source option (use BTC RSI for altcoin trading)

This module provides TradingView-compatible RSI filtering logic for the
Bybit Strategy Tester backtesting engine.

Example Usage:
    from backend.core.indicators.rsi_advanced import RSIAdvancedFilter

    # Create filter
    rsi_filter = RSIAdvancedFilter(
        rsi_period=14,
        use_long_range=True,
        long_range_lower=1,
        long_range_upper=50,
        use_cross_level=True,
        long_cross_level=30,
        activate_memory=True,
        memory_bars=5,
    )

    # Apply to price data
    long_signals, short_signals = rsi_filter.generate_signals(close_prices)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import numpy as np

from backend.core.indicators.momentum import calculate_rsi


class RSIFilterMode(Enum):
    """RSI filter operation modes."""

    RANGE_ONLY = "range_only"  # Pure range filter
    CROSS_ONLY = "cross_only"  # Pure cross signal
    CROSS_WITH_MEMORY = "cross_memory"  # Cross + memory window
    RANGE_AND_CROSS = "range_cross"  # Combined mode
    OPPOSITE_CROSS = "opposite_cross"  # Inverted cross logic


@dataclass
class RSIAdvancedConfig:
    """
    Configuration for Advanced RSI Filter.

    Matches TradingView RSI - [IN RANGE FILTER OR CROSS SIGNAL] settings.
    """

    # Basic RSI settings
    rsi_period: int = 14

    # Long Range Filter
    use_long_range: bool = False
    long_range_lower: int = 1  # "(LONG) RSI is More"
    long_range_upper: int = 50  # "& RSI Less"

    # Short Range Filter
    use_short_range: bool = False
    short_range_lower: int = 50  # "(SHORT) RSI More" (lower bound)
    short_range_upper: int = 100  # "(SHORT) RSI is Less" (upper bound)

    # Cross Level Filter
    use_cross_level: bool = False
    long_cross_level: int = 30  # "Level to Cross RSI for LONG"
    short_cross_level: int = 70  # "Level to Cross RSI for SHORT"

    # Opposite Signal (invert cross logic)
    opposite_signal: bool = False

    # Signal Memory
    activate_memory: bool = False
    memory_bars: int = 5  # "Keep RSI Cross Signal Memory for XX bars"

    def get_mode(self) -> RSIFilterMode:
        """Determine the active filter mode based on settings."""
        if self.use_cross_level and self.opposite_signal:
            return RSIFilterMode.OPPOSITE_CROSS
        elif self.use_long_range and self.use_cross_level:
            return RSIFilterMode.RANGE_AND_CROSS
        elif self.use_cross_level and self.activate_memory:
            return RSIFilterMode.CROSS_WITH_MEMORY
        elif self.use_cross_level:
            return RSIFilterMode.CROSS_ONLY
        else:
            return RSIFilterMode.RANGE_ONLY


@dataclass
class RSIFilterResult:
    """Result container for RSI filter signals."""

    rsi_values: np.ndarray
    long_signals: np.ndarray  # Boolean array - when long is allowed
    short_signals: np.ndarray  # Boolean array - when short is allowed
    long_cross_events: np.ndarray  # Actual crossover events
    short_cross_events: np.ndarray  # Actual crossunder events
    long_memory_active: np.ndarray  # Memory window active
    short_memory_active: np.ndarray
    bars_since_long_signal: np.ndarray
    bars_since_short_signal: np.ndarray


class RSIAdvancedFilter:
    """
    Advanced RSI Filter with TradingView parity.

    Implements multi-mode RSI filtering:
    1. Range Filter: RSI must be within specified bounds
    2. Cross Signal: RSI must cross specified level
    3. Signal Memory: Keep signal active for N bars after cross
    4. Opposite Logic: Invert cross direction
    5. BTC Source: Use external symbol RSI (handled externally)

    Example:
        >>> config = RSIAdvancedConfig(
        ...     rsi_period=14,
        ...     use_long_range=True,
        ...     long_range_lower=20,
        ...     long_range_upper=60,
        ...     use_cross_level=True,
        ...     long_cross_level=30,
        ...     activate_memory=True,
        ...     memory_bars=5,
        ... )
        >>> filter = RSIAdvancedFilter(config)
        >>> result = filter.apply(close_prices)
        >>> long_entries = result.long_signals
    """

    def __init__(self, config: RSIAdvancedConfig | None = None, **kwargs):
        """
        Initialize RSI Advanced Filter.

        Args:
            config: RSIAdvancedConfig instance
            **kwargs: Alternative way to pass config parameters
        """
        if config is not None:
            self.config = config
        else:
            self.config = RSIAdvancedConfig(**kwargs)

    def apply(
        self,
        close: np.ndarray,
        external_rsi: np.ndarray | None = None,
    ) -> RSIFilterResult:
        """
        Apply the RSI filter to price data.

        Args:
            close: Close prices array
            external_rsi: Pre-calculated RSI (e.g., from BTC or different timeframe)

        Returns:
            RSIFilterResult with all signal arrays
        """
        n = len(close)

        # Calculate RSI (or use external)
        if external_rsi is not None:
            rsi = external_rsi
        else:
            rsi = calculate_rsi(close, self.config.rsi_period)

        # Initialize result arrays
        long_signals = np.ones(n, dtype=bool)  # Start with all True
        short_signals = np.ones(n, dtype=bool)
        long_cross_events = np.zeros(n, dtype=bool)
        short_cross_events = np.zeros(n, dtype=bool)
        long_memory_active = np.zeros(n, dtype=bool)
        short_memory_active = np.zeros(n, dtype=bool)
        bars_since_long = np.full(n, np.inf)
        bars_since_short = np.full(n, np.inf)

        # === RANGE FILTER ===
        long_range_condition = self._apply_range_filter(
            rsi, self.config.use_long_range, self.config.long_range_lower, self.config.long_range_upper, is_long=True
        )

        short_range_condition = self._apply_range_filter(
            rsi,
            self.config.use_short_range,
            self.config.short_range_lower,
            self.config.short_range_upper,
            is_long=False,
        )

        # === CROSS LEVEL FILTER ===
        if self.config.use_cross_level:
            # Detect crossover/crossunder events
            long_cross_raw, short_cross_raw = self._detect_crosses(rsi)

            # Apply opposite logic if enabled
            if self.config.opposite_signal:
                long_cross_events = short_cross_raw  # Long on SHORT cross (exit overbought)
                short_cross_events = long_cross_raw  # Short on LONG cross (exit oversold)
            else:
                long_cross_events = long_cross_raw
                short_cross_events = short_cross_raw

            # Apply signal memory
            if self.config.activate_memory:
                long_memory_active, bars_since_long = self._apply_memory(long_cross_events, self.config.memory_bars)
                short_memory_active, bars_since_short = self._apply_memory(short_cross_events, self.config.memory_bars)

                # With memory: signal active during memory window
                long_cross_condition = long_memory_active
                short_cross_condition = short_memory_active
            else:
                # Without memory: signal only on cross event
                long_cross_condition = long_cross_events
                short_cross_condition = short_cross_events
        else:
            # Cross filter disabled - always True
            long_cross_condition = np.ones(n, dtype=bool)
            short_cross_condition = np.ones(n, dtype=bool)

        # === COMBINE CONDITIONS ===
        # Final signal = Range AND Cross (both must be True)
        long_signals = long_range_condition & long_cross_condition
        short_signals = short_range_condition & short_cross_condition

        return RSIFilterResult(
            rsi_values=rsi,
            long_signals=long_signals,
            short_signals=short_signals,
            long_cross_events=long_cross_events,
            short_cross_events=short_cross_events,
            long_memory_active=long_memory_active,
            short_memory_active=short_memory_active,
            bars_since_long_signal=bars_since_long,
            bars_since_short_signal=bars_since_short,
        )

    def _apply_range_filter(
        self,
        rsi: np.ndarray,
        use_range: bool,
        lower_bound: int,
        upper_bound: int,
        is_long: bool,
    ) -> np.ndarray:
        """
        Apply range filter to RSI values.

        For LONG: RSI > lower AND RSI < upper
        For SHORT: RSI < upper AND RSI > lower

        Args:
            rsi: RSI values array
            use_range: Whether to apply range filter
            lower_bound: Lower RSI boundary
            upper_bound: Upper RSI boundary
            is_long: True for long range, False for short range

        Returns:
            Boolean array where True = condition met
        """
        if not use_range:
            return np.ones(len(rsi), dtype=bool)

        # Handle NaN values
        valid_mask = ~np.isnan(rsi)
        result = np.zeros(len(rsi), dtype=bool)

        if is_long:
            # LONG: RSI must be MORE than lower AND LESS than upper
            # Example: RSI > 1 AND RSI < 50
            result[valid_mask] = (rsi[valid_mask] > lower_bound) & (rsi[valid_mask] < upper_bound)
        else:
            # SHORT: RSI must be LESS than upper AND MORE than lower
            # Example: RSI < 100 AND RSI > 50
            result[valid_mask] = (rsi[valid_mask] < upper_bound) & (rsi[valid_mask] > lower_bound)

        return result

    def _detect_crosses(
        self,
        rsi: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect RSI crossover and crossunder events.

        Crossover (for LONG): RSI crosses above long_cross_level
        Crossunder (for SHORT): RSI crosses below short_cross_level

        Args:
            rsi: RSI values array

        Returns:
            Tuple of (long_cross_events, short_cross_events) boolean arrays
        """
        n = len(rsi)
        long_cross = np.zeros(n, dtype=bool)
        short_cross = np.zeros(n, dtype=bool)

        long_level = self.config.long_cross_level
        short_level = self.config.short_cross_level

        for i in range(1, n):
            prev_rsi = rsi[i - 1]
            curr_rsi = rsi[i]

            if np.isnan(prev_rsi) or np.isnan(curr_rsi):
                continue

            # Crossover: previous <= level AND current > level
            if prev_rsi <= long_level and curr_rsi > long_level:
                long_cross[i] = True

            # Crossunder: previous >= level AND current < level
            if prev_rsi >= short_level and curr_rsi < short_level:
                short_cross[i] = True

        return long_cross, short_cross

    def _apply_memory(
        self,
        cross_events: np.ndarray,
        memory_bars: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply signal memory - keep signal active for N bars after cross.

        Args:
            cross_events: Boolean array of cross events
            memory_bars: Number of bars to keep signal active

        Returns:
            Tuple of (memory_active, bars_since_signal) arrays
        """
        n = len(cross_events)
        memory_active = np.zeros(n, dtype=bool)
        bars_since = np.full(n, np.inf)

        last_signal_bar = -np.inf

        for i in range(n):
            if cross_events[i]:
                last_signal_bar = i

            bars_since[i] = i - last_signal_bar

            # Memory is active if within memory_bars of last signal
            if bars_since[i] <= memory_bars:
                memory_active[i] = True

        return memory_active, bars_since


# =============================================================================
# Convenience Functions
# =============================================================================


def apply_rsi_range_filter(
    close: np.ndarray,
    rsi_period: int = 14,
    long_lower: int = 1,
    long_upper: int = 50,
    short_lower: int = 50,
    short_upper: int = 100,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply simple RSI range filter.

    Args:
        close: Close prices
        rsi_period: RSI period
        long_lower: Lower bound for long (RSI > this)
        long_upper: Upper bound for long (RSI < this)
        short_lower: Lower bound for short (RSI > this)
        short_upper: Upper bound for short (RSI < this)

    Returns:
        Tuple of (rsi_values, long_allowed, short_allowed)
    """
    config = RSIAdvancedConfig(
        rsi_period=rsi_period,
        use_long_range=True,
        long_range_lower=long_lower,
        long_range_upper=long_upper,
        use_short_range=True,
        short_range_lower=short_lower,
        short_range_upper=short_upper,
        use_cross_level=False,
    )

    filter_obj = RSIAdvancedFilter(config)
    result = filter_obj.apply(close)

    return result.rsi_values, result.long_signals, result.short_signals


def apply_rsi_cross_filter(
    close: np.ndarray,
    rsi_period: int = 14,
    long_cross_level: int = 30,
    short_cross_level: int = 70,
    opposite_signal: bool = False,
    memory_bars: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Apply RSI cross level filter with optional memory.

    Args:
        close: Close prices
        rsi_period: RSI period
        long_cross_level: Level for long crossover
        short_cross_level: Level for short crossunder
        opposite_signal: Invert cross logic
        memory_bars: Keep signal active for N bars (0 = no memory)

    Returns:
        Tuple of (rsi_values, long_signals, short_signals)
    """
    config = RSIAdvancedConfig(
        rsi_period=rsi_period,
        use_long_range=False,
        use_short_range=False,
        use_cross_level=True,
        long_cross_level=long_cross_level,
        short_cross_level=short_cross_level,
        opposite_signal=opposite_signal,
        activate_memory=memory_bars > 0,
        memory_bars=memory_bars if memory_bars > 0 else 5,
    )

    filter_obj = RSIAdvancedFilter(config)
    result = filter_obj.apply(close)

    return result.rsi_values, result.long_signals, result.short_signals


def apply_rsi_combined_filter(
    close: np.ndarray,
    rsi_period: int = 14,
    # Range settings
    long_range_lower: int = 20,
    long_range_upper: int = 60,
    short_range_lower: int = 40,
    short_range_upper: int = 80,
    # Cross settings
    long_cross_level: int = 30,
    short_cross_level: int = 70,
    # Options
    opposite_signal: bool = False,
    memory_bars: int = 5,
) -> RSIFilterResult:
    """
    Apply full combined RSI filter (Range + Cross + Memory).

    This is the most powerful mode combining all features.

    Args:
        close: Close prices
        rsi_period: RSI period
        long_range_lower/upper: Long range bounds
        short_range_lower/upper: Short range bounds
        long_cross_level: Level for long crossover
        short_cross_level: Level for short crossunder
        opposite_signal: Invert cross logic
        memory_bars: Keep signal active for N bars

    Returns:
        Full RSIFilterResult with all signal arrays
    """
    config = RSIAdvancedConfig(
        rsi_period=rsi_period,
        use_long_range=True,
        long_range_lower=long_range_lower,
        long_range_upper=long_range_upper,
        use_short_range=True,
        short_range_lower=short_range_lower,
        short_range_upper=short_range_upper,
        use_cross_level=True,
        long_cross_level=long_cross_level,
        short_cross_level=short_cross_level,
        opposite_signal=opposite_signal,
        activate_memory=True,
        memory_bars=memory_bars,
    )

    filter_obj = RSIAdvancedFilter(config)
    return filter_obj.apply(close)


# =============================================================================
# BTC Source Helper
# =============================================================================


def create_btc_rsi_filter(
    btc_close: np.ndarray,
    rsi_period: int = 14,
    long_cross_level: int = 40,
    short_cross_level: int = 60,
    memory_bars: int = 3,
) -> RSIFilterResult:
    """
    Create RSI filter using BTC as source for altcoin trading.

    Use BTC's RSI to determine market sentiment for altcoin entries.

    Example:
        When 4H BTC RSI crosses above 40, allow long entries on altcoins
        for the next 3 bars (12 hours on 4H timeframe).

    Args:
        btc_close: BTC close prices (must match altcoin timeframe)
        rsi_period: RSI period for BTC
        long_cross_level: BTC RSI level for bullish signal
        short_cross_level: BTC RSI level for bearish signal
        memory_bars: How long to keep signal active

    Returns:
        RSIFilterResult - use long_signals/short_signals for altcoin filtering
    """
    config = RSIAdvancedConfig(
        rsi_period=rsi_period,
        use_long_range=False,
        use_short_range=False,
        use_cross_level=True,
        long_cross_level=long_cross_level,
        short_cross_level=short_cross_level,
        opposite_signal=False,
        activate_memory=True,
        memory_bars=memory_bars,
    )

    filter_obj = RSIAdvancedFilter(config)
    return filter_obj.apply(btc_close)
