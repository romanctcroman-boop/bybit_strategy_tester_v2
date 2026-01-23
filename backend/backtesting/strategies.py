"""
Trading Strategies for Backtesting

Strategy implementations using vectorbt indicators.
Each strategy generates entry/exit signals based on technical analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger

try:
    import vectorbt as vbt
except ImportError:
    vbt = None
    logger.warning("vectorbt not installed. Some features will be unavailable.")


@dataclass
class SignalResult:
    """Result of signal generation"""

    entries: pd.Series  # Boolean series for entry signals
    exits: pd.Series  # Boolean series for exit signals
    short_entries: Optional[pd.Series] = None  # For short positions
    short_exits: Optional[pd.Series] = None


class BaseStrategy(ABC):
    """Base class for all trading strategies"""

    name: str = "base"
    description: str = "Base strategy class"

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = params or {}
        self._validate_params()

    @abstractmethod
    def _validate_params(self) -> None:
        """Validate strategy parameters"""
        pass

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """
        Generate trading signals from OHLCV data.

        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume
                   Index should be datetime

        Returns:
            SignalResult with entry/exit signals
        """
        pass

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """Get default parameters for this strategy"""
        return {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(params={self.params})"


class SMAStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy

    Long entry: Fast SMA crosses above Slow SMA
    Long exit: Fast SMA crosses below Slow SMA

    Parameters:
        fast_period: Period for fast SMA (default: 10)
        slow_period: Period for slow SMA (default: 30)
    """

    name = "sma_crossover"
    description = "SMA Crossover - Buy when fast SMA crosses above slow SMA"

    def _validate_params(self) -> None:
        self.fast_period = int(self.params.get("fast_period", 10))
        self.slow_period = int(self.params.get("slow_period", 30))

        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})"
            )
        if self.fast_period < 2:
            raise ValueError(f"fast_period must be >= 2, got {self.fast_period}")

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {"fast_period": 10, "slow_period": 30}

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]

        # Calculate SMAs
        fast_sma = close.rolling(window=self.fast_period).mean()
        slow_sma = close.rolling(window=self.slow_period).mean()

        # Generate crossover signals
        # Long entry: fast crosses above slow (bullish)
        long_entries = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))

        # Long exit: fast crosses below slow (bearish)
        long_exits = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))

        # Short entry: fast crosses below slow (bearish)
        short_entries = long_exits.copy()

        # Short exit: fast crosses above slow (bullish)
        short_exits = long_entries.copy()

        # Явно устанавливаем False для периода прогрева индикатора
        # (DeepSeek рекомендация: явная обработка NaN вместо fillna)
        warmup_period = self.slow_period
        long_entries = long_entries.copy()
        long_exits = long_exits.copy()
        short_entries = short_entries.copy()
        short_exits = short_exits.copy()
        long_entries.iloc[:warmup_period] = False
        long_exits.iloc[:warmup_period] = False
        short_entries.iloc[:warmup_period] = False
        short_exits.iloc[:warmup_period] = False

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
        )


class RSIStrategy(BaseStrategy):
    """
    RSI (Relative Strength Index) Strategy

    Long entry: RSI crosses below oversold level (buy the dip)
    Long exit: RSI crosses above overbought level (sell the peak)

    Parameters:
        period: RSI period (default: 14)
        oversold: Oversold level (default: 30)
        overbought: Overbought level (default: 70)
    """

    name = "rsi"
    description = "RSI Strategy - Buy oversold, Sell overbought"

    def _validate_params(self) -> None:
        self.period = int(self.params.get("period", 14))
        self.oversold = float(self.params.get("oversold", 30))
        self.overbought = float(self.params.get("overbought", 70))

        if self.period < 2:
            raise ValueError(f"period must be >= 2, got {self.period}")
        if not (0 < self.oversold < self.overbought < 100):
            raise ValueError(
                f"Invalid levels: oversold={self.oversold}, overbought={self.overbought}"
            )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {"period": 14, "oversold": 30, "overbought": 70}

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate RSI using Wilder's Smoothing (RMA) - matches TradingView ta.rsi()

        TradingView uses RMA (Wilder's Moving Average) which is equivalent to:
        EWM with alpha = 1/period (or span = 2*period - 1)

        Formula: RMA = alpha * current + (1 - alpha) * previous
        where alpha = 1 / period
        """
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Wilder's Smoothing (RMA) - equivalent to EWM with alpha = 1/period
        # This matches TradingView's ta.rma() function
        alpha = 1.0 / self.period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]

        rsi = self._calculate_rsi(close)

        # TradingView crossover/crossunder logic:
        # - crossover(source, level): prev <= level AND curr > level
        # - crossunder(source, level): prev >= level AND curr < level

        rsi_prev = rsi.shift(1)

        # Long entry: crossover(RSI, oversold) - RSI crosses oversold FROM BELOW
        # This signals recovery from oversold - BUY signal
        long_entries = (rsi_prev <= self.oversold) & (rsi > self.oversold)

        # Long exit: crossunder(RSI, overbought) - RSI crosses overbought FROM ABOVE
        # This signals reversal from overbought - SELL signal
        long_exits = (rsi_prev >= self.overbought) & (rsi < self.overbought)

        # Short entry: crossunder(RSI, overbought) - RSI crosses overbought FROM ABOVE
        # This signals reversal from overbought - SHORT signal
        short_entries = (rsi_prev >= self.overbought) & (rsi < self.overbought)

        # Short exit: crossover(RSI, oversold) - RSI crosses oversold FROM BELOW
        # This signals recovery from oversold - COVER signal
        short_exits = (rsi_prev <= self.oversold) & (rsi > self.oversold)

        # TradingView Entry Timing: strategy.entry() enters on NEXT bar's OPEN
        # Signal detected on bar [i] -> entry happens on bar [i+1]
        # We shift signals forward by 1 bar to match this behavior
        long_entries = long_entries.shift(1).fillna(False).astype(bool)
        long_exits = long_exits.shift(1).fillna(False).astype(bool)
        short_entries = short_entries.shift(1).fillna(False).astype(bool)
        short_exits = short_exits.shift(1).fillna(False).astype(bool)

        # Warmup period for RSI stabilization
        # TV Trade #1 enters at Oct 01 12:45 UTC = ~51 bars from Oct 01 00:00
        # So warmup should be ~50 bars
        warmup_period = 50  # ~12.5 hours for 15m bars
        long_entries = long_entries.copy()
        long_exits = long_exits.copy()
        short_entries = short_entries.copy()
        short_exits = short_exits.copy()
        long_entries.iloc[:warmup_period] = False
        long_exits.iloc[:warmup_period] = False
        short_entries.iloc[:warmup_period] = False
        short_exits.iloc[:warmup_period] = False

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
        )


class MACDStrategy(BaseStrategy):
    """
    MACD (Moving Average Convergence Divergence) Strategy

    TradingView-compatible signals:
    - Long entry: MACD line crosses above Signal line
    - Long exit: MACD line crosses below Signal line (or short entry)
    - Short entry: MACD line crosses below Signal line
    - Short exit: MACD line crosses above Signal line (or long entry)

    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line period (default: 9)
    """

    name = "macd"
    description = "MACD Strategy - Trade MACD/Signal crossovers"

    def _validate_params(self) -> None:
        self.fast_period = int(self.params.get("fast_period", 12))
        self.slow_period = int(self.params.get("slow_period", 26))
        self.signal_period = int(self.params.get("signal_period", 9))

        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})"
            )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {"fast_period": 12, "slow_period": 26, "signal_period": 9}

    def _calculate_macd(
        self, close: pd.Series
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD, Signal, and Histogram"""
        fast_ema = close.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close.ewm(span=self.slow_period, adjust=False).mean()

        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]

        macd_line, signal_line, _ = self._calculate_macd(close)

        # Bullish crossover: MACD crosses above Signal
        # This is LONG entry and SHORT exit
        bullish_cross = (macd_line > signal_line) & (
            macd_line.shift(1) <= signal_line.shift(1)
        )

        # Bearish crossover: MACD crosses below Signal
        # This is SHORT entry and LONG exit
        bearish_cross = (macd_line < signal_line) & (
            macd_line.shift(1) >= signal_line.shift(1)
        )

        # TradingView-compatible: NO artificial warmup period
        # TradingView starts trading immediately when crossover occurs
        # The EMA calculation itself provides natural stabilization
        # Previous code blocked first 35 bars - this was incorrect
        bullish_cross = bullish_cross.copy()
        bearish_cross = bearish_cross.copy()
        # Only skip first bar (NaN from shift)
        bullish_cross.iloc[0] = False
        bearish_cross.iloc[0] = False

        # TradingView style:
        # - Long entry on bullish crossover
        # - Long exit on bearish crossover (reversed by short entry)
        # - Short entry on bearish crossover
        # - Short exit on bullish crossover (reversed by long entry)
        return SignalResult(
            entries=bullish_cross,  # Long entries
            exits=bearish_cross,  # Long exits
            short_entries=bearish_cross,  # Short entries
            short_exits=bullish_cross,  # Short exits
        )


class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands Mean Reversion Strategy

    Long entry: Price touches lower band (oversold)
    Long exit: Price touches upper band (overbought)

    Parameters:
        period: Moving average period (default: 20)
        std_dev: Number of standard deviations (default: 2.0)
    """

    name = "bollinger_bands"
    description = "Bollinger Bands - Mean reversion strategy"

    def _validate_params(self) -> None:
        self.period = int(self.params.get("period", 20))
        self.std_dev = float(self.params.get("std_dev", 2.0))

        if self.period < 2:
            raise ValueError(f"period must be >= 2, got {self.period}")
        if self.std_dev <= 0:
            raise ValueError(f"std_dev must be > 0, got {self.std_dev}")

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {"period": 20, "std_dev": 2.0}

    def _calculate_bollinger_bands(
        self, close: pd.Series
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands: middle, upper, lower"""
        middle = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()

        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)

        return middle, upper, lower

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]

        _, upper, lower = self._calculate_bollinger_bands(close)

        # Long entry: Price touches/crosses below lower band (oversold)
        long_entries = (close <= lower) & (close.shift(1) > lower.shift(1))

        # Long exit: Price touches/crosses above upper band (overbought)
        long_exits = (close >= upper) & (close.shift(1) < upper.shift(1))

        # Short entry: Price touches/crosses above upper band (overbought)
        short_entries = long_exits.copy()

        # Short exit: Price touches/crosses below lower band (oversold)
        short_exits = long_entries.copy()

        # Явно устанавливаем False для периода прогрева Bollinger Bands
        # (DeepSeek рекомендация: явная обработка NaN вместо fillna)
        warmup_period = self.period
        long_entries = long_entries.copy()
        long_exits = long_exits.copy()
        short_entries = short_entries.copy()
        short_exits = short_exits.copy()
        long_entries.iloc[:warmup_period] = False
        long_exits.iloc[:warmup_period] = False
        short_entries.iloc[:warmup_period] = False
        short_exits.iloc[:warmup_period] = False

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
        )


class GridStrategy(BaseStrategy):
    """
    Grid Trading Strategy - for pyramiding testing

    Generates BUY signals at regular price intervals below current price.
    Ideal for DCA-like accumulation in ranging or falling markets.

    Logic:
    - Divides price range into grid levels
    - Generates LONG entry when price drops to each grid level
    - Generates exit when price rises above entry + profit target

    Parameters:
        grid_levels: Number of grid levels (default: 5, requires pyramiding >= grid_levels)
        grid_spacing: Spacing between levels in % (default: 1.0%)
        take_profit: Profit target per grid in % (default: 1.5%)
        direction: "long" or "both" (default: "long")

    Usage with pyramiding:
        config.pyramiding = 5  # Match grid_levels
        strategy = GridStrategy({"grid_levels": 5, "grid_spacing": 1.0})
    """

    name = "grid"
    description = "Grid Strategy - Buy at price intervals, sell at profit target"

    def _validate_params(self) -> None:
        self.grid_levels = int(self.params.get("grid_levels", 5))
        self.grid_spacing = (
            float(self.params.get("grid_spacing", 1.0)) / 100
        )  # Convert to decimal
        self.take_profit = float(self.params.get("take_profit", 1.5)) / 100
        self.direction = self.params.get("direction", "long")

        if self.grid_levels < 2:
            raise ValueError(f"grid_levels must be >= 2, got {self.grid_levels}")
        if self.grid_spacing <= 0:
            raise ValueError(
                f"grid_spacing must be > 0, got {self.grid_spacing * 100}%"
            )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {
            "grid_levels": 5,
            "grid_spacing": 1.0,  # 1% spacing
            "take_profit": 1.5,  # 1.5% TP per grid
            "direction": "long",
        }

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]
        low = ohlcv["low"]
        high = ohlcv["high"]
        n = len(close)

        # Initialize signal arrays
        long_entries = pd.Series(False, index=close.index)
        long_exits = pd.Series(False, index=close.index)

        # Track grid levels relative to recent high
        # Rolling high over lookback period (baseline for grid)
        lookback = 20  # 20 bars to establish baseline
        rolling_high = high.rolling(window=lookback).max()

        # For each bar, check if price dropped to any grid level
        for i in range(lookback, n):
            baseline = rolling_high.iloc[i]

            # Check each grid level
            for level in range(1, self.grid_levels + 1):
                grid_price = baseline * (1 - level * self.grid_spacing)

                # Entry signal: price touches grid level from above
                if low.iloc[i] <= grid_price < low.iloc[i - 1]:
                    long_entries.iloc[i] = True
                    break  # One signal per bar

        # Exit signal: price rises significantly (TP relative to grid average)
        # Simplified: exit when price rises above recent low + profit margin
        rolling_low = low.rolling(window=lookback).min()
        for i in range(lookback, n):
            if high.iloc[i] >= rolling_low.iloc[i] * (1 + self.take_profit * 2):
                long_exits.iloc[i] = True

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=pd.Series(False, index=close.index),
            short_exits=pd.Series(False, index=close.index),
        )


class DCAStrategy(BaseStrategy):
    """
    Dollar Cost Averaging (DCA) Strategy - for pyramiding testing

    Generates BUY/SELL signals at regular TIME intervals.
    Ideal for systematic accumulation regardless of price.

    Logic for LONG:
    - Generates LONG entry every N bars
    - Continues adding positions up to pyramiding limit
    - Exits when profit target is reached or after holding period

    Logic for SHORT:
    - Generates SHORT entry every N bars
    - Continues adding positions up to pyramiding limit
    - Exits when price drops by profit target % or after holding period

    Parameters:
        entry_interval: Bars between each buy (default: 10)
        max_entries: Maximum entries (should match pyramiding setting)
        take_profit: Profit target from average price in % (default: 3.0%)
        holding_period: Max bars to hold before exit (default: 100)
        _direction: "long", "short", or "both" (default: "long")

    Usage with pyramiding:
        config.pyramiding = 5
        strategy = DCAStrategy({"entry_interval": 10, "max_entries": 5, "_direction": "long"})
    """

    name = "dca"
    description = (
        "DCA Strategy - Buy/Sell at regular intervals, pyramiding accumulation"
    )

    def _validate_params(self) -> None:
        self.entry_interval = int(self.params.get("entry_interval", 10))
        self.max_entries = int(self.params.get("max_entries", 5))
        self.take_profit = float(self.params.get("take_profit", 3.0)) / 100
        self.holding_period = int(self.params.get("holding_period", 100))
        self.direction = self.params.get("_direction", "long")

        if self.entry_interval < 1:
            raise ValueError(f"entry_interval must be >= 1, got {self.entry_interval}")
        if self.max_entries < 1:
            raise ValueError(f"max_entries must be >= 1, got {self.max_entries}")

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {
            "entry_interval": 10,  # Buy every 10 bars
            "max_entries": 5,  # Up to 5 entries
            "take_profit": 3.0,  # 3% TP from average
            "holding_period": 100,  # Max 100 bars hold
            "_direction": "long",  # Direction: long, short, or both
        }

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]
        n = len(close)

        # Initialize signal arrays
        long_entries = pd.Series(False, index=close.index)
        long_exits = pd.Series(False, index=close.index)
        short_entries = pd.Series(False, index=close.index)
        short_exits = pd.Series(False, index=close.index)

        # Determine if we should generate long and/or short signals
        generate_long = self.direction in ("long", "both")
        generate_short = self.direction in ("short", "both")

        if generate_long:
            # LONG DCA logic
            entry_count = 0
            first_entry_bar = None
            cumulative_cost = 0.0
            cumulative_qty = 0.0

            for i in range(1, n):
                # Entry signal every N bars (up to max_entries)
                if i % self.entry_interval == 0 and entry_count < self.max_entries:
                    long_entries.iloc[i] = True
                    entry_count += 1
                    if first_entry_bar is None:
                        first_entry_bar = i

                    # Track average cost
                    cumulative_cost += close.iloc[i]
                    cumulative_qty += 1

                # Check for exit conditions
                if first_entry_bar is not None and cumulative_qty > 0:
                    avg_price = cumulative_cost / cumulative_qty

                    # Exit on profit target (price rises above average + TP)
                    if close.iloc[i] >= avg_price * (1 + self.take_profit):
                        long_exits.iloc[i] = True
                        # Reset tracking
                        entry_count = 0
                        first_entry_bar = None
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0

                    # Exit on max holding period
                    elif i - first_entry_bar >= self.holding_period:
                        long_exits.iloc[i] = True
                        # Reset tracking
                        entry_count = 0
                        first_entry_bar = None
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0

        if generate_short:
            # SHORT DCA logic - opposite of long
            entry_count = 0
            first_entry_bar = None
            cumulative_cost = 0.0
            cumulative_qty = 0.0

            for i in range(1, n):
                # Entry signal every N bars (up to max_entries)
                if i % self.entry_interval == 0 and entry_count < self.max_entries:
                    short_entries.iloc[i] = True
                    entry_count += 1
                    if first_entry_bar is None:
                        first_entry_bar = i

                    # Track average cost
                    cumulative_cost += close.iloc[i]
                    cumulative_qty += 1

                # Check for exit conditions
                if first_entry_bar is not None and cumulative_qty > 0:
                    avg_price = cumulative_cost / cumulative_qty

                    # Exit on profit target (price drops below average - TP for short)
                    if close.iloc[i] <= avg_price * (1 - self.take_profit):
                        short_exits.iloc[i] = True
                        # Reset tracking
                        entry_count = 0
                        first_entry_bar = None
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0

                    # Exit on max holding period
                    elif i - first_entry_bar >= self.holding_period:
                        short_exits.iloc[i] = True
                        # Reset tracking
                        entry_count = 0
                        first_entry_bar = None
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
        )


class MartingaleStrategy(BaseStrategy):
    """
    Martingale Strategy - Double down on losses

    Generates BUY signals when price drops by a threshold from entry.
    Each subsequent entry should use larger position size (handled by engine).

    Logic:
    - Initial entry on RSI signal
    - Additional entries when price drops by threshold %
    - Exit when price recovers to breakeven + profit

    Parameters:
        rsi_oversold: RSI level for initial entry (default: 35)
        drop_threshold: Price drop % to trigger next entry (default: 2.0%)
        recovery_target: Recovery % from average for exit (default: 1.5%)
        max_entries: Maximum martingale entries (default: 4)

    Warning: Martingale can lead to significant losses!
    """

    name = "martingale"
    description = "Martingale Strategy - Double down on losses (high risk!)"

    def _validate_params(self) -> None:
        self.rsi_oversold = float(self.params.get("rsi_oversold", 35))
        self.drop_threshold = float(self.params.get("drop_threshold", 2.0)) / 100
        self.recovery_target = float(self.params.get("recovery_target", 1.5)) / 100
        self.max_entries = int(self.params.get("max_entries", 4))
        self.rsi_period = int(self.params.get("rsi_period", 14))

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {
            "rsi_oversold": 35,
            "drop_threshold": 2.0,
            "recovery_target": 1.5,
            "max_entries": 4,
            "rsi_period": 14,
        }

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate RSI"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        alpha = 1.0 / self.rsi_period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]
        low = ohlcv["low"]
        n = len(close)

        rsi = self._calculate_rsi(close)

        # Initialize
        long_entries = pd.Series(False, index=close.index)
        long_exits = pd.Series(False, index=close.index)

        in_position = False
        entry_count = 0
        avg_entry_price = 0.0
        last_entry_price = 0.0

        warmup = self.rsi_period + 1

        for i in range(warmup, n):
            if not in_position:
                # Initial entry on RSI oversold
                if rsi.iloc[i] < self.rsi_oversold:
                    long_entries.iloc[i] = True
                    in_position = True
                    entry_count = 1
                    last_entry_price = close.iloc[i]
                    avg_entry_price = close.iloc[i]
            else:
                # Check for additional martingale entries
                if entry_count < self.max_entries:
                    drop_from_last = (last_entry_price - low.iloc[i]) / last_entry_price
                    if drop_from_last >= self.drop_threshold:
                        long_entries.iloc[i] = True
                        entry_count += 1
                        # Update average (simplified - actual is weighted)
                        avg_entry_price = (
                            avg_entry_price * (entry_count - 1) + close.iloc[i]
                        ) / entry_count
                        last_entry_price = close.iloc[i]

                # Check for exit on recovery
                if close.iloc[i] >= avg_entry_price * (1 + self.recovery_target):
                    long_exits.iloc[i] = True
                    in_position = False
                    entry_count = 0

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=pd.Series(False, index=close.index),
            short_exits=pd.Series(False, index=close.index),
        )


# Strategy registry for dynamic loading
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMAStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "grid": GridStrategy,
    "dca": DCAStrategy,
    "martingale": MartingaleStrategy,
}


def get_strategy(
    strategy_type: str, params: dict[str, Any] | None = None
) -> BaseStrategy:
    """
    Factory function to get a strategy instance.

    Args:
        strategy_type: Strategy type from StrategyType enum
        params: Strategy-specific parameters

    Returns:
        Configured strategy instance

    Raises:
        ValueError: If strategy type is not found
    """
    strategy_class = STRATEGY_REGISTRY.get(strategy_type)
    if strategy_class is None:
        available = list(STRATEGY_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy type: {strategy_type}. Available: {available}"
        )

    return strategy_class(params)


def list_available_strategies() -> list[dict[str, Any]]:
    """
    List all available strategies with their default parameters.

    Returns:
        List of strategy info dicts
    """
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        result.append(
            {
                "name": name,
                "description": cls.description,
                "default_params": cls.get_default_params(),
                "supports_pyramiding": name in ("grid", "dca", "martingale"),
            }
        )
    return result
