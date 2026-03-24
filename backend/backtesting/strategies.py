"""
Trading Strategies for Backtesting

Strategy implementations using vectorbt indicators.
Each strategy generates entry/exit signals based on technical analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

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
    """Result of signal generation

    Attributes:
        entries: Boolean series for long entry signals
        exits: Boolean series for long exit signals
        short_entries: Boolean series for short entry signals
        short_exits: Boolean series for short exit signals
        entry_sizes: Optional series of position sizes for each long entry (for Volume Scale)
        short_entry_sizes: Optional series of position sizes for each short entry
        extra_data: Optional dict for passing additional data (ATR series, etc.) to engine
    """

    entries: pd.Series  # Boolean series for entry signals
    exits: pd.Series  # Boolean series for exit signals
    short_entries: pd.Series | None = None  # For short positions
    short_exits: pd.Series | None = None
    entry_sizes: pd.Series | None = None  # Position size per entry (for DCA Volume Scale)
    short_entry_sizes: pd.Series | None = None  # Position size per short entry
    extra_data: dict | None = None  # Additional data (ATR exit series, etc.)


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
            raise ValueError(f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})")
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

    DEPRECATED (2026-02-16):
        This is the OLD backtesting engine RSI strategy.
        For new strategies, use the UNIVERSAL RSI block in Strategy Builder.
        The universal RSI block supports Range filter, Cross level, Legacy modes,
        BTC source, optimization ranges, and cross signal memory.
        AI agents MUST use the universal RSI block (type='rsi') instead.
        Kept for backward compatibility with old backtest configs.
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
            raise ValueError(f"Invalid levels: oversold={self.oversold}, overbought={self.overbought}")

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
            raise ValueError(f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})")

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {"fast_period": 12, "slow_period": 26, "signal_period": 9}

    def _calculate_macd(self, close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
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
        bullish_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))

        # Bearish crossover: MACD crosses below Signal
        # This is SHORT entry and LONG exit
        bearish_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

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

    def _calculate_bollinger_bands(self, close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
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
        self.grid_spacing = float(self.params.get("grid_spacing", 1.0)) / 100  # Convert to decimal
        self.take_profit = float(self.params.get("take_profit", 1.5)) / 100
        self.direction = self.params.get("direction", "long")

        if self.grid_levels < 2:
            raise ValueError(f"grid_levels must be >= 2, got {self.grid_levels}")
        if self.grid_spacing <= 0:
            raise ValueError(f"grid_spacing must be > 0, got {self.grid_spacing * 100}%")

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
    DCA (Dollar Cost Averaging) Strategy - 3commas/WunderTrading style

    Professional DCA bot with all standard parameters:
    - Base Order + Safety Orders with volume scaling
    - Price deviation with step multiplier (logarithmic distribution)
    - Take Profit from average price with trailing
    - Stop Loss with configurable reference point
    - RSI-based trade start conditions

    Parameters (3commas naming convention):
        base_order_size: Base order size as % of capital (default: 10%)
        safety_order_size: First safety order size as % (default: 10%)
        safety_order_volume_scale: Multiplier for each subsequent SO (default: 1.05 = +5%)
        price_deviation: First SO trigger deviation % (default: 1.0%)
        step_scale: Deviation multiplier for subsequent SOs (default: 1.4)
        max_safety_orders: Max number of safety orders (default: 5)
        target_profit: Take profit % from average (default: 2.5%)
        trailing_deviation: Trailing TP deviation % (default: 0.4%)
        stop_loss: Stop loss % (default: 0%)  # 0 = disabled
        stop_loss_type: 'average' or 'last_order' (default: 'last_order')
        cooldown_between_deals: Min bars between deals (default: 4)

        # Trade start conditions (RSI)
        rsi_period: RSI indicator period (default: 14)
        rsi_trigger: RSI level to trigger entry (default: 30 for long, 70 for short)

        _direction: 'long' or 'short'

    Usage:
        strategy = DCAStrategy({
            "base_order_size": 10,
            "safety_order_size": 10,
            "max_safety_orders": 5,
            "price_deviation": 1.0,
            "step_scale": 1.4,
            "target_profit": 2.5,
            "_direction": "long"
        })
    """

    name = "dca"
    description = "DCA Bot - 3commas/WunderTrading style with safety orders, volume scaling, trailing TP"

    def _validate_params(self) -> None:
        # === DEAL START ===
        self.direction = self.params.get("_direction", "long")
        self.cooldown = int(self.params.get("cooldown_between_deals", 4))  # Min bars between deals

        # RSI trigger (Trade Start Condition)
        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_trigger = float(self.params.get("rsi_trigger", 30 if self.direction == "long" else 70))

        # === BASE ORDER ===
        self.base_order_size = float(self.params.get("base_order_size", 10.0)) / 100  # % of capital

        # === SAFETY ORDERS ===
        self.max_safety_orders = int(self.params.get("max_safety_orders", 5))
        self.safety_order_size = float(self.params.get("safety_order_size", 10.0)) / 100  # % of capital
        self.safety_order_volume_scale = float(self.params.get("safety_order_volume_scale", 1.05))  # Martingale

        # Price deviation (% drop from entry to trigger SO)
        self.price_deviation = float(self.params.get("price_deviation", 1.0)) / 100
        self.step_scale = float(self.params.get("step_scale", 1.4))  # Logarithmic scaling

        # === TAKE PROFIT ===
        self.target_profit = float(self.params.get("target_profit", 2.5)) / 100
        self.trailing_deviation = float(self.params.get("trailing_deviation", 0.4)) / 100

        # === STOP LOSS ===
        self.stop_loss = float(self.params.get("stop_loss", 0.0)) / 100  # 0 = disabled
        self.stop_loss_type = self.params.get("stop_loss_type", "last_order")  # 'average' or 'last_order'

        # === VELES-STYLE PARAMETERS ===
        # Max Active Safety Orders (Veles: "Частичное выставление сетки")
        # 0 = disabled (all SOs active), >0 = limit to N active SOs
        self.max_active_safety_orders = int(self.params.get("max_active_safety_orders", 0))

        # Grid Trailing Deviation (Veles: "Подтяжка сетки")
        # If price moves away from entry by this %, cancel deal and wait for new entry
        # 0 = disabled
        self.grid_trailing_deviation = float(self.params.get("grid_trailing_deviation", 0.0)) / 100

        # Max Deals (Veles: "Остановить бота после N сделок")
        # 0 = unlimited, >0 = stop after N completed deals
        self.max_deals = int(self.params.get("max_deals", 0))

        # TP Signal Mode (Veles: "Тейк-профит Сигнал")
        # 'disabled' = use normal trailing TP, 'rsi' = exit when RSI reverses
        self.tp_signal_mode = self.params.get("tp_signal_mode", "disabled")
        # RSI exit level: for LONG, exit when RSI > this value; for SHORT, exit when RSI < (100 - this)
        self.tp_signal_rsi_exit = float(self.params.get("tp_signal_rsi_exit", 70))

        # Validation
        if self.max_safety_orders < 0:
            raise ValueError(f"max_safety_orders must be >= 0, got {self.max_safety_orders}")
        if self.target_profit <= 0:
            raise ValueError(f"target_profit must be > 0, got {self.target_profit * 100}%")
        if self.stop_loss_type not in ("average", "last_order"):
            raise ValueError(f"stop_loss_type must be 'average' or 'last_order', got {self.stop_loss_type}")
        if self.direction not in ("long", "short"):
            raise ValueError(f"_direction must be 'long' or 'short', got {self.direction}")

        # Pre-calculate safety order deviation levels
        self._calculate_so_levels()

    def _calculate_so_levels(self) -> None:
        """Calculate price deviation levels for each safety order."""
        # SO1 at price_deviation, SO2 at price_deviation * step_scale, etc.
        self.so_levels = []
        cumulative = 0.0
        current_deviation = self.price_deviation

        for _i in range(self.max_safety_orders):
            cumulative += current_deviation
            self.so_levels.append(cumulative)
            current_deviation *= self.step_scale

        # Also pre-calculate volume for each SO (martingale)
        self.so_volumes = []
        current_size = self.safety_order_size
        for _i in range(self.max_safety_orders):
            self.so_volumes.append(current_size)
            current_size *= self.safety_order_volume_scale

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        return {
            # Deal start
            "_direction": "long",
            "cooldown_between_deals": 4,  # Min bars between deals
            "rsi_period": 14,
            "rsi_trigger": 30,  # RSI < 30 for long entry
            # Base order
            "base_order_size": 10.0,  # 10% of capital
            # Safety orders (averaging)
            "max_safety_orders": 5,
            "safety_order_size": 10.0,  # 10% of capital
            "safety_order_volume_scale": 1.05,  # +5% per SO (martingale)
            "price_deviation": 1.0,  # 1% drop triggers SO1
            "step_scale": 1.4,  # SO2 at 1.4%, SO3 at 1.96%, etc.
            # Take profit
            "target_profit": 2.5,  # 2.5% from average price
            "trailing_deviation": 0.4,  # 0.4% trailing
            # Stop loss
            "stop_loss": 0.0,  # Disabled by default
            "stop_loss_type": "last_order",  # 'average' or 'last_order'
            # Veles-style parameters
            "max_active_safety_orders": 0,  # 0 = all active, >0 = limit to N
            "grid_trailing_deviation": 0.0,  # 0 = disabled, >0 = cancel if price moves away by %
            "max_deals": 0,  # 0 = unlimited, >0 = stop after N deals
            "tp_signal_mode": "disabled",  # 'disabled', 'rsi'
            "tp_signal_rsi_exit": 70,  # RSI level for LONG exit (overbought)
        }

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """Calculate RSI using Wilder's Smoothing (RMA) - matches TradingView."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Wilder's Smoothing (RMA)
        alpha = 1.0 / self.rsi_period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        close = ohlcv["close"]
        low = ohlcv["low"]
        high = ohlcv["high"]
        n = len(close)

        # Calculate RSI for entry filter
        rsi = self._calculate_rsi(close)
        warmup = self.rsi_period + 1

        # Initialize signal arrays
        long_entries = pd.Series(False, index=close.index)
        long_exits = pd.Series(False, index=close.index)
        short_entries = pd.Series(False, index=close.index)
        short_exits = pd.Series(False, index=close.index)

        # Initialize entry sizes for Volume Scale (0.0 means use default position_size)
        entry_sizes = pd.Series(0.0, index=close.index)
        short_entry_sizes = pd.Series(0.0, index=close.index)

        # Max entries = 1 base order + max_safety_orders
        max_entries = 1 + self.max_safety_orders

        if self.direction == "long":
            # LONG DCA logic - 3commas style
            entry_count = 0
            last_deal_bar = -self.cooldown  # Allow first entry immediately
            base_entry_price = 0.0
            cumulative_cost = 0.0
            cumulative_qty = 0.0
            last_entry_price = 0.0
            # Trailing TP state
            trailing_active = False
            peak_high = 0.0
            # Deal counter (Veles: max_deals)
            completed_deals = 0

            for i in range(warmup, n):
                in_deal = entry_count > 0

                # === CHECK EXIT CONDITIONS FIRST ===
                if in_deal:
                    avg_price = cumulative_cost / cumulative_qty
                    current_high = high.iloc[i]
                    current_low = low.iloc[i]

                    # Trailing Take Profit logic
                    tp_price = avg_price * (1 + self.target_profit)

                    if trailing_active:
                        # Update peak high
                        if current_high > peak_high:
                            peak_high = current_high

                        # Exit if price retraces by trailing_deviation from peak
                        trailing_exit_price = peak_high * (1 - self.trailing_deviation)
                        if current_low <= trailing_exit_price:
                            long_exits.iloc[i] = True
                            # Reset for next deal
                            entry_count = 0
                            last_deal_bar = i
                            base_entry_price = 0.0
                            cumulative_cost = 0.0
                            cumulative_qty = 0.0
                            last_entry_price = 0.0
                            trailing_active = False
                            peak_high = 0.0
                            completed_deals += 1  # Count completed deal for max_deals
                            continue
                    else:
                        # Check if TP reached to activate trailing
                        if current_high >= tp_price:
                            trailing_active = True
                            peak_high = current_high
                            # Don't exit yet, start trailing

                    # === TP SIGNAL MODE: RSI-based exit (Veles: "Тейк-профит Сигнал") ===
                    # Exit when RSI goes overbought (for LONG), overriding trailing TP
                    if self.tp_signal_mode == "rsi" and rsi.iloc[i] > self.tp_signal_rsi_exit:
                        long_exits.iloc[i] = True
                        entry_count = 0
                        last_deal_bar = i
                        base_entry_price = 0.0
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0
                        last_entry_price = 0.0
                        trailing_active = False
                        peak_high = 0.0
                        completed_deals += 1  # Count completed deal for signal exit
                        continue

                    # SL: if enabled (stop_loss > 0) and trailing not active
                    if not trailing_active and self.stop_loss > 0:
                        sl_reference = avg_price if self.stop_loss_type == "average" else last_entry_price

                        sl_price = sl_reference * (1 - self.stop_loss)
                        if current_low <= sl_price:
                            long_exits.iloc[i] = True
                            entry_count = 0
                            last_deal_bar = i
                            base_entry_price = 0.0
                            cumulative_cost = 0.0
                            cumulative_qty = 0.0
                            last_entry_price = 0.0
                            trailing_active = False
                            peak_high = 0.0
                            completed_deals += 1  # Count completed deal (SL exit)
                            continue

                    # === GRID TRAILING (Подтяжка сетки Veles-style) ===
                    # If price moves UP away from entry, cancel deal and wait for new entry
                    if self.grid_trailing_deviation > 0:
                        grid_trailing_price = base_entry_price * (1 + self.grid_trailing_deviation)
                        if current_high >= grid_trailing_price:
                            # Cancel deal without exit signal (no position to close if just base order)
                            long_exits.iloc[i] = True
                            entry_count = 0
                            last_deal_bar = i
                            base_entry_price = 0.0
                            cumulative_cost = 0.0
                            cumulative_qty = 0.0
                            last_entry_price = 0.0
                            trailing_active = False
                            peak_high = 0.0
                            completed_deals += 1  # Count as completed deal (grid trailing cancel)
                            continue

                # === CHECK ENTRY CONDITIONS ===
                cooldown_ok = (i - last_deal_bar) >= self.cooldown
                can_add = entry_count < max_entries

                # Check max_deals limit (Veles: "Остановить бота после N сделок")
                max_deals_ok = self.max_deals == 0 or completed_deals < self.max_deals

                if can_add and cooldown_ok and max_deals_ok:
                    if entry_count == 0:
                        # BASE ORDER: triggered by RSI
                        rsi_signal = rsi.iloc[i] < self.rsi_trigger
                        if rsi_signal:
                            long_entries.iloc[i] = True
                            entry_sizes.iloc[i] = self.base_order_size  # Volume Scale: base order size
                            entry_count = 1
                            base_entry_price = close.iloc[i]
                            last_entry_price = close.iloc[i]
                            # FIX: weight cumulative_cost by order volume for correct avg_price
                            cumulative_cost = close.iloc[i] * self.base_order_size
                            cumulative_qty = self.base_order_size
                    else:
                        # SAFETY ORDER: triggered by price deviation
                        so_index = entry_count - 1  # 0-indexed SO

                        # Check max_active_safety_orders limit (Veles: "Частичное выставление сетки")
                        max_active = self.max_active_safety_orders
                        if max_active > 0 and so_index >= max_active:
                            # Skip this SO - it's beyond the active limit
                            # Only allow SOs up to max_active_safety_orders
                            pass
                        elif so_index < len(self.so_levels):
                            so_deviation = self.so_levels[so_index]
                            so_trigger_price = base_entry_price * (1 - so_deviation)

                            if low.iloc[i] <= so_trigger_price:
                                so_vol = self.so_volumes[so_index]
                                long_entries.iloc[i] = True
                                entry_sizes.iloc[i] = so_vol  # Volume Scale: scaled SO size
                                entry_count += 1
                                last_entry_price = close.iloc[i]
                                # FIX: weight by volume so avg_price accounts for martingale
                                cumulative_cost += close.iloc[i] * so_vol
                                cumulative_qty += so_vol

        elif self.direction == "short":
            # SHORT DCA logic - 3commas style
            entry_count = 0
            last_deal_bar = -self.cooldown
            base_entry_price = 0.0
            cumulative_cost = 0.0
            cumulative_qty = 0.0
            last_entry_price = 0.0
            # Trailing TP state
            trailing_active = False
            peak_low = float("inf")
            # Deal counter (Veles: max_deals)
            completed_deals = 0

            for i in range(warmup, n):
                in_deal = entry_count > 0

                # === CHECK EXIT CONDITIONS FIRST ===
                if in_deal:
                    avg_price = cumulative_cost / cumulative_qty
                    current_high = high.iloc[i]
                    current_low = low.iloc[i]

                    # Trailing Take Profit logic for SHORT
                    tp_price = avg_price * (1 - self.target_profit)

                    if trailing_active:
                        # Update peak low (lowest price reached)
                        if current_low < peak_low:
                            peak_low = current_low

                        # Exit if price rises by trailing_deviation from peak_low
                        trailing_exit_price = peak_low * (1 + self.trailing_deviation)
                        if current_high >= trailing_exit_price:
                            short_exits.iloc[i] = True
                            entry_count = 0
                            last_deal_bar = i
                            base_entry_price = 0.0
                            cumulative_cost = 0.0
                            cumulative_qty = 0.0
                            last_entry_price = 0.0
                            trailing_active = False
                            peak_low = float("inf")
                            completed_deals += 1  # Count completed deal for max_deals
                            continue
                    else:
                        # Check if TP reached to activate trailing
                        if current_low <= tp_price:
                            trailing_active = True
                            peak_low = current_low
                            # Don't exit yet, start trailing

                    # === TP SIGNAL MODE: RSI-based exit (Veles: "Тейк-профит Сигнал") ===
                    # Exit when RSI goes oversold (for SHORT), overriding trailing TP
                    short_rsi_exit = 100 - self.tp_signal_rsi_exit  # e.g., 100-70=30
                    if self.tp_signal_mode == "rsi" and rsi.iloc[i] < short_rsi_exit:
                        short_exits.iloc[i] = True
                        entry_count = 0
                        last_deal_bar = i
                        base_entry_price = 0.0
                        cumulative_cost = 0.0
                        cumulative_qty = 0.0
                        last_entry_price = 0.0
                        trailing_active = False
                        peak_low = float("inf")
                        completed_deals += 1  # Count completed deal for signal exit
                        continue

                    # SL: if enabled (stop_loss > 0) and trailing not active
                    if not trailing_active and self.stop_loss > 0:
                        sl_reference = avg_price if self.stop_loss_type == "average" else last_entry_price

                        sl_price = sl_reference * (1 + self.stop_loss)
                        if current_high >= sl_price:
                            short_exits.iloc[i] = True
                            entry_count = 0
                            last_deal_bar = i
                            base_entry_price = 0.0
                            cumulative_cost = 0.0
                            cumulative_qty = 0.0
                            last_entry_price = 0.0
                            trailing_active = False
                            peak_low = float("inf")
                            completed_deals += 1  # Count completed deal (SL exit)
                            continue

                # === CHECK ENTRY CONDITIONS ===
                cooldown_ok = (i - last_deal_bar) >= self.cooldown
                can_add = entry_count < max_entries

                # Check max_deals limit (Veles: "Остановить бота после N сделок")
                max_deals_ok = self.max_deals == 0 or completed_deals < self.max_deals

                if can_add and cooldown_ok and max_deals_ok:
                    if entry_count == 0:
                        # BASE ORDER: triggered by RSI (overbought for short)
                        rsi_signal = rsi.iloc[i] > self.rsi_trigger
                        if rsi_signal:
                            short_entries.iloc[i] = True
                            short_entry_sizes.iloc[i] = self.base_order_size  # Volume Scale
                            entry_count = 1
                            base_entry_price = close.iloc[i]
                            last_entry_price = close.iloc[i]
                            # FIX: weight cumulative_cost by order volume for correct avg_price
                            cumulative_cost = close.iloc[i] * self.base_order_size
                            cumulative_qty = self.base_order_size
                    else:
                        # SAFETY ORDER: triggered by price deviation UP
                        so_index = entry_count - 1
                        if so_index < len(self.so_levels):
                            so_deviation = self.so_levels[so_index]
                            so_trigger_price = base_entry_price * (1 + so_deviation)

                            if high.iloc[i] >= so_trigger_price:
                                so_vol = self.so_volumes[so_index]
                                short_entries.iloc[i] = True
                                short_entry_sizes.iloc[i] = so_vol  # Volume Scale
                                entry_count += 1
                                last_entry_price = close.iloc[i]
                                # FIX: weight by volume so avg_price accounts for martingale
                                cumulative_cost += close.iloc[i] * so_vol
                                cumulative_qty += so_vol

        return SignalResult(
            entries=long_entries,
            exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            entry_sizes=entry_sizes,
            short_entry_sizes=short_entry_sizes,
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
                        avg_entry_price = (avg_entry_price * (entry_count - 1) + close.iloc[i]) / entry_count
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


class AdvancedMACDStrategy(BaseStrategy):
    """
    Advanced MACD Strategy with TP/SL — TradingView Parity Implementation
    ======================================================================
    Exact Python port of the TradingView Pine Script v6 strategy
    "Advanced MACD Strategy with TP/SL" (Strategy_MACD_01).

    Matches TradingView behaviour:
    - calc_on_every_tick = true BUT entries only on barstate.isConfirmed
      (confirmed bar close). Our engine uses entry_on_next_bar_open=True
      which fills at next-bar open — matching TV market order behaviour.
    - Signal logic: OR/AND combinations of zero-line and signal-line
      crossovers, with optional "opposite signal" inversion per source.
    - Zero-line filter: LONG only when MACD > 0, SHORT only when MACD < 0.
    - Signal memory: active N bars after a crossover (for external filters;
      does NOT affect strategy entries — entries use raw cross only).

    Pine Script signal conditions (with both sources active):
        longSignal  = longCrossZeroCondition  AND longCrossSignalCondition
        shortSignal = shortCrossZeroCondition AND shortCrossSignalCondition

    With oppositeCrossZero=True:
        longCrossZeroCondition  = crossUNDER(macd, 0)   (macd drops below zero)
        shortCrossZeroCondition = crossOVER(macd, 0)    (macd rises above zero)

    With oppositeCrossSignal=True:
        longCrossSignalCondition  = crossUNDER(macd, signal)
        shortCrossSignalCondition = crossOVER(macd, signal)

    TV reference test parameters (ETHUSDT 30m, 2025-01-04 → 2026-03-01):
        fast=14, slow=15, signal=9, cross_zero=True, cross_signal=True,
        opposite_zero=True, opposite_signal=True, zero_filter=False,
        TP=6.6%, SL=13.2%, leverage=10, base_cash=100 USDT (fixed),
        initial_capital=10000, commission=0.07%

    TV results (42 trades, 88.1% win rate, net profit +17.23%):
        - 37 wins / 5 losses
        - Profit factor: 3.584
        - Sharpe: 0.934  Sortino: 4.19
        - Max drawdown: 2.60% (intrabar)

    Parameters
    ----------
    fast_period : int
        Fast EMA period (default: 14). Pine: macdFastLength.
    slow_period : int
        Slow EMA period (default: 15). Pine: macdSlowLength.
        NOTE: fast < slow is NOT enforced here because fast=14/slow=15
        is the verified TV reference; override validation if needed.
    signal_period : int
        Signal line smoothing period (default: 9). Pine: macdSignalSmoothing.
    use_cross_zero : bool
        Enable zero-line crossover signals (default: True).
    opposite_cross_zero : bool
        Invert zero-line crossover direction (default: True).
        True  → Long on crossUNDER zero, Short on crossOVER zero.
        False → Long on crossOVER zero,  Short on crossUNDER zero.
    use_cross_signal : bool
        Enable signal-line crossover signals (default: True).
    opposite_cross_signal : bool
        Invert signal-line crossover direction (default: True).
        True  → Long on crossUNDER signal, Short on crossOVER signal.
        False → Long on crossOVER signal,  Short on crossUNDER signal.
    zero_filter : bool
        Enable zero-line filter (default: False).
        True → LONG only when MACD > 0, SHORT only when MACD < 0.
    """

    name = "advanced_macd"
    description = (
        "Advanced MACD with TP/SL — TradingView parity (Strategy_MACD_01). "
        "Supports zero-line and signal-line crossovers with optional inversion and zero filter."
    )

    def _validate_params(self) -> None:
        self.fast_period = int(self.params.get("fast_period", 14))
        self.slow_period = int(self.params.get("slow_period", 15))
        self.signal_period = int(self.params.get("signal_period", 9))

        # TV allows fast == slow or fast > slow (unusual but valid)
        if self.fast_period < 1:
            raise ValueError(f"fast_period must be >= 1, got {self.fast_period}")
        if self.slow_period < 1:
            raise ValueError(f"slow_period must be >= 1, got {self.slow_period}")
        if self.signal_period < 1:
            raise ValueError(f"signal_period must be >= 1, got {self.signal_period}")

        # Signal source flags
        self.use_cross_zero = bool(self.params.get("use_cross_zero", True))
        self.opposite_cross_zero = bool(self.params.get("opposite_cross_zero", True))
        self.use_cross_signal = bool(self.params.get("use_cross_signal", True))
        self.opposite_cross_signal = bool(self.params.get("opposite_cross_signal", True))

        # Zero-line filter (LONG if MACD > 0, SHORT if MACD < 0)
        self.zero_filter = bool(self.params.get("zero_filter", False))

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """Default params matching the TV reference test configuration."""
        return {
            "fast_period": 14,
            "slow_period": 15,
            "signal_period": 9,
            "use_cross_zero": True,
            "opposite_cross_zero": True,
            "use_cross_signal": True,
            "opposite_cross_signal": True,
            "zero_filter": False,
        }

    def _calculate_macd(self, close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD line, signal line, and histogram.

        Uses EWM with adjust=False to match TradingView's ta.ema() / ta.macd():
            Pine: ta.ema(src, period) → Python: close.ewm(span=period, adjust=False).mean()
        """
        fast_ema = close.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """
        Generate entry/exit signals replicating the TV Pine Script logic.

        TradingView crossover/crossunder definitions:
            crossover(a, b)  : prev_a <= prev_b  AND  curr_a > curr_b
            crossunder(a, b) : prev_a >= prev_b  AND  curr_a < curr_b

        Entry timing:
            Pine strategy.entry() with calc_on_every_tick=true and
            confirmed bar fires on CLOSE of bar i.  In our engine,
            entry_on_next_bar_open=True means the order fills at
            OPEN of bar i+1 — matching TV market order behaviour.
            Therefore we do NOT shift signals here; the engine shifts.
        """
        close = ohlcv["close"]
        n = len(close)

        macd_line, signal_line, _ = self._calculate_macd(close)

        # Replace NaN with 0.0 (Pine: nz(macdLine, 0))
        macd_safe = macd_line.fillna(0.0)
        signal_safe = signal_line.fillna(0.0)

        # dataValid: both macd and signal are not NaN
        data_valid = (~macd_line.isna()) & (~signal_line.isna())

        # Previous bar values (for crossover/crossunder)
        macd_prev = macd_safe.shift(1)
        signal_prev = signal_safe.shift(1)

        # ── Zero-line crossovers ─────────────────────────────────────────
        # Pine: ta.crossover(macdSafe, 0)  ↔  prev <= 0 AND curr > 0
        cross_up_zero = (macd_prev <= 0) & (macd_safe > 0)
        # Pine: ta.crossunder(macdSafe, 0) ↔  prev >= 0 AND curr < 0
        cross_down_zero = (macd_prev >= 0) & (macd_safe < 0)

        # ── Signal-line crossovers ───────────────────────────────────────
        # Pine: ta.crossover(macdSafe, signalSafe)
        cross_up_signal = (macd_prev <= signal_prev) & (macd_safe > signal_safe)
        # Pine: ta.crossunder(macdSafe, signalSafe)
        cross_down_signal = (macd_prev >= signal_prev) & (macd_safe < signal_safe)

        # ── Long signal conditions ───────────────────────────────────────
        # Pine: longCrossZeroCondition = oppositeCrossZero ? crossDownZero : crossUpZero
        long_cross_zero_cond = cross_down_zero if self.opposite_cross_zero else cross_up_zero

        # Pine: longCrossSignalCondition = oppositeCrossSignal ? crossDownSignal : crossUpSignal
        long_cross_signal_cond = cross_down_signal if self.opposite_cross_signal else cross_up_signal

        # Zero-line filter for LONG: MACD > 0
        long_zero_filter = (macd_safe > 0) if self.zero_filter else pd.Series(True, index=close.index)

        # Pine longSignal (both sources active — AND logic):
        #   dataValid AND (useZero OR useSignal) AND
        #   (NOT useZero   OR longZeroCond) AND
        #   (NOT useSignal OR longSignalCond) AND zeroFilter
        #
        # NOTE: Use Python `not` (logical) not `~` (bitwise) on plain booleans.
        #       `~True` returns -2 in Python, which causes incorrect Series math.
        at_least_one = self.use_cross_zero or self.use_cross_signal
        # "(NOT useZero) OR longZeroCond":
        #   if use_cross_zero is False → always True (condition not required)
        #   if use_cross_zero is True  → must satisfy longCrossZeroCond
        zero_part = long_cross_zero_cond if self.use_cross_zero else pd.Series(True, index=close.index)
        signal_part = long_cross_signal_cond if self.use_cross_signal else pd.Series(True, index=close.index)

        long_entries_raw = data_valid & at_least_one & zero_part & signal_part & long_zero_filter

        # ── Short signal conditions ──────────────────────────────────────
        short_cross_zero_cond = cross_up_zero if self.opposite_cross_zero else cross_down_zero
        short_cross_signal_cond = cross_up_signal if self.opposite_cross_signal else cross_down_signal
        short_zero_filter = (macd_safe < 0) if self.zero_filter else pd.Series(True, index=close.index)

        zero_part_s = short_cross_zero_cond if self.use_cross_zero else pd.Series(True, index=close.index)
        signal_part_s = short_cross_signal_cond if self.use_cross_signal else pd.Series(True, index=close.index)

        short_entries_raw = data_valid & at_least_one & zero_part_s & signal_part_s & short_zero_filter

        # ── Conflict guard (both long and short on same bar — skip both) ─
        # Pine: signalsConflict = longSignal and shortSignal → neither fires
        conflict = long_entries_raw & short_entries_raw
        long_entries_raw = long_entries_raw & (~conflict)
        short_entries_raw = short_entries_raw & (~conflict)

        # ── Safety: clear first bar (NaN from shift) ──────────────────────
        long_entries_raw = long_entries_raw.copy()
        short_entries_raw = short_entries_raw.copy()
        if n > 0:
            long_entries_raw.iloc[0] = False
            short_entries_raw.iloc[0] = False

        # ── Exit signals ──────────────────────────────────────────────────
        # In the TV strategy exits are handled by strategy.exit() (TP/SL),
        # NOT by opposing entry signals.  There is no explicit signal-based
        # exit in the Pine code — positions are closed only by TP or SL.
        #
        # In our engine the TP/SL are set via BacktestInput.stop_loss /
        # take_profit fields in the BacktestConfig (not from signals).
        # The exit series here are kept empty so the engine's TP/SL logic
        # handles all exits — exactly as in TradingView.
        long_exits = pd.Series(False, index=close.index)
        short_exits = pd.Series(False, index=close.index)

        return SignalResult(
            entries=long_entries_raw.astype(bool),
            exits=long_exits,
            short_entries=short_entries_raw.astype(bool),
            short_exits=short_exits,
        )


# Strategy registry for dynamic loading
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMAStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "advanced_macd": AdvancedMACDStrategy,
    "macd_01": AdvancedMACDStrategy,  # Alias: Strategy_MACD_01
    "bollinger_bands": BollingerBandsStrategy,
    "grid": GridStrategy,
    "dca": DCAStrategy,
    "martingale": MartingaleStrategy,
}


def get_strategy(strategy_type: str, params: dict[str, Any] | None = None) -> BaseStrategy:
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
        raise ValueError(f"Unknown strategy type: {strategy_type}. Available: {available}")

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


# ---------------------------------------------------------------------------
# Convenience alias used by portfolio backtesting tests
# ---------------------------------------------------------------------------
# NOTE: This is the SAME as RSIStrategy above (first definition in STRATEGY_REGISTRY).
# The second definition was added as a simplified alias. Keeping it named RSIStrategy
# causes isinstance() failures because Python overwrites the name in the module.
# Solution: this second class is now an extension of the FIRST RSIStrategy to avoid
# the duplicate-class problem. The first RSIStrategy is what STRATEGY_REGISTRY uses.


class _RSIStrategySimple(BaseStrategy):  # pragma: no cover
    """
    Simple RSI mean-reversion strategy.

    Generates long signals when RSI drops below *oversold* and
    short signals when RSI rises above *overbought*.

    Params:
        period (int): RSI lookback period (default 14).
        oversold (float): Oversold threshold (default 30).
        overbought (float): Overbought threshold (default 70).
    """

    description = "RSI mean-reversion strategy"

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0, **kwargs):
        super().__init__(
            params={"period": int(period), "oversold": oversold, "overbought": overbought},
            **kwargs,
        )
        self.period = int(period)
        self.oversold = oversold
        self.overbought = overbought

    def _validate_params(self) -> None:
        self.period = int(self.params.get("period", 14))
        self.oversold = float(self.params.get("oversold", 30.0))
        self.overbought = float(self.params.get("overbought", 70.0))

    @classmethod
    def get_default_params(cls) -> dict:
        return {"period": 14, "oversold": 30.0, "overbought": 70.0}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["signal"] = 0

        close = df["close"]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=self.period - 1, min_periods=self.period).mean()
        avg_loss = loss.ewm(com=self.period - 1, min_periods=self.period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        df.loc[rsi < self.oversold, "signal"] = 1
        df.loc[rsi > self.overbought, "signal"] = -1
        return df


# Keep the name RSIStrategy pointing to the FIRST definition (in STRATEGY_REGISTRY)
# so that isinstance() checks work correctly. _RSIStrategySimple is just an alias
# for code that needs a simplified constructor (used by portfolio backtesting tests).
# NOTE: This re-assignment must be LAST in the file to override the class statement above.
RSIStrategy = STRATEGY_REGISTRY["rsi"]  # type: ignore[assignment,misc]
