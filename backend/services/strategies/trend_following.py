"""
Trend Following Strategies.

Strategies that identify and follow market trends:
- EMA Crossover: Fast/slow EMA crossing signals
- MACD Trend: MACD line and signal line crossings
- Triple EMA: Three EMAs for trend confirmation
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from backend.services.live_trading.strategy_runner import (
    SignalType,
    StrategyConfig,
    TradingSignal,
)
from backend.services.strategies.base import (
    LibraryStrategy,
    ParameterSpec,
    ParameterType,
    StrategyCategory,
    StrategyInfo,
    calculate_stop_loss,
    calculate_take_profit,
    register_strategy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# EMA Crossover Strategy
# =============================================================================


@dataclass
class EMACrossoverParams:
    """Parameters for EMA Crossover strategy."""

    fast_period: int = 9
    slow_period: int = 21
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0
    require_trend_confirmation: bool = True
    trend_ema_period: int = 50


EMA_CROSSOVER_INFO = StrategyInfo(
    id="ema_crossover",
    name="EMA Crossover",
    description="""
    Classic trend-following strategy using two Exponential Moving Averages.

    Generates BUY when fast EMA crosses above slow EMA.
    Generates SELL when fast EMA crosses below slow EMA.

    Optional: Requires price above/below 50 EMA for trend confirmation.

    Best for: Trending markets with clear directional moves.
    Avoid in: Choppy, sideways markets.
    """,
    category=StrategyCategory.TREND_FOLLOWING,
    version="1.0.0",
    author="System",
    min_candles=60,
    recommended_timeframes=["15", "60", "240"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=2.0,
    expected_win_rate=0.45,
    expected_risk_reward=2.0,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.15,
    parameters=[
        ParameterSpec(
            name="fast_period",
            param_type=ParameterType.INT,
            default=9,
            description="Fast EMA period",
            min_value=3,
            max_value=20,
            step=1,
        ),
        ParameterSpec(
            name="slow_period",
            param_type=ParameterType.INT,
            default=21,
            description="Slow EMA period",
            min_value=15,
            max_value=50,
            step=1,
        ),
        ParameterSpec(
            name="atr_period",
            param_type=ParameterType.INT,
            default=14,
            description="ATR period for stop loss",
            min_value=7,
            max_value=21,
            step=1,
        ),
        ParameterSpec(
            name="atr_multiplier",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="ATR multiplier for stop loss",
            min_value=1.0,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="risk_reward",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Risk/reward ratio",
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="require_trend_confirmation",
            param_type=ParameterType.BOOL,
            default=True,
            description="Require trend EMA confirmation",
        ),
        ParameterSpec(
            name="trend_ema_period",
            param_type=ParameterType.INT,
            default=50,
            description="Trend EMA period for confirmation",
            min_value=30,
            max_value=100,
            step=10,
        ),
    ],
    tags=["ema", "crossover", "trend", "beginner-friendly"],
)


@register_strategy
class EMACrossoverStrategy(LibraryStrategy):
    """
    EMA Crossover Trend Following Strategy.

    Buy when fast EMA crosses above slow EMA.
    Sell when fast EMA crosses below slow EMA.
    """

    STRATEGY_INFO = EMA_CROSSOVER_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # State tracking
        self._prev_fast_ema: Optional[float] = None
        self._prev_slow_ema: Optional[float] = None
        self._in_position: str = ""  # "long", "short", or ""

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate crossover signals."""
        # Add candle to history
        self.add_candle(candle)

        # Check warmup
        if not self.warmup_complete():
            return None

        # Get parameters
        fast_period = self.get_param("fast_period", 9)
        slow_period = self.get_param("slow_period", 21)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)
        require_trend = self.get_param("require_trend_confirmation", True)
        trend_period = self.get_param("trend_ema_period", 50)

        # Calculate indicators
        fast_ema = self.ema(fast_period)
        slow_ema = self.ema(slow_period)
        trend_ema = self.ema(trend_period) if require_trend else None
        current_atr = self.atr(atr_period)

        close = candle["close"]

        # Need previous values for crossover detection
        if self._prev_fast_ema is None or self._prev_slow_ema is None:
            self._prev_fast_ema = fast_ema
            self._prev_slow_ema = slow_ema
            return None

        signal = None

        # Bullish crossover: fast crosses above slow
        if self._prev_fast_ema <= self._prev_slow_ema and fast_ema > slow_ema:
            # Check trend confirmation
            if not require_trend or (trend_ema and close > trend_ema):
                stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.BUY,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Bullish EMA crossover (Fast: {fast_ema:.2f} > Slow: {slow_ema:.2f})",
                    confidence=0.7 if require_trend else 0.6,
                    fast_ema=fast_ema,
                    slow_ema=slow_ema,
                )
                self._in_position = "long"

        # Bearish crossover: fast crosses below slow
        elif self._prev_fast_ema >= self._prev_slow_ema and fast_ema < slow_ema:
            # Check trend confirmation
            if not require_trend or (trend_ema and close < trend_ema):
                stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Bearish EMA crossover (Fast: {fast_ema:.2f} < Slow: {slow_ema:.2f})",
                    confidence=0.7 if require_trend else 0.6,
                    fast_ema=fast_ema,
                    slow_ema=slow_ema,
                )
                self._in_position = "short"

        # Update previous values
        self._prev_fast_ema = fast_ema
        self._prev_slow_ema = slow_ema

        return signal


# Factory functions for EMA Crossover
def create_conservative_ema_strategy(config: StrategyConfig) -> EMACrossoverStrategy:
    """Create conservative EMA strategy (wider stops, fewer trades)."""
    return EMACrossoverStrategy(
        config,
        fast_period=12,
        slow_period=26,
        atr_multiplier=2.5,
        risk_reward=2.5,
        require_trend_confirmation=True,
        trend_ema_period=50,
    )


def create_moderate_ema_strategy(config: StrategyConfig) -> EMACrossoverStrategy:
    """Create moderate EMA strategy (balanced settings)."""
    return EMACrossoverStrategy(
        config,
        fast_period=9,
        slow_period=21,
        atr_multiplier=2.0,
        risk_reward=2.0,
        require_trend_confirmation=True,
        trend_ema_period=50,
    )


def create_aggressive_ema_strategy(config: StrategyConfig) -> EMACrossoverStrategy:
    """Create aggressive EMA strategy (tighter stops, more trades)."""
    return EMACrossoverStrategy(
        config,
        fast_period=5,
        slow_period=13,
        atr_multiplier=1.5,
        risk_reward=1.5,
        require_trend_confirmation=False,
    )


# =============================================================================
# MACD Trend Strategy
# =============================================================================


@dataclass
class MACDTrendParams:
    """Parameters for MACD Trend strategy."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0
    require_histogram_confirmation: bool = True
    min_histogram_size: float = 0.0


MACD_TREND_INFO = StrategyInfo(
    id="macd_trend",
    name="MACD Trend",
    description="""
    Trend following strategy using MACD indicator.

    Generates BUY when MACD line crosses above signal line.
    Generates SELL when MACD line crosses below signal line.

    Optional: Confirms with histogram direction/size.

    Best for: Medium-term trend trades.
    Avoid in: Very low volatility or ranging markets.
    """,
    category=StrategyCategory.TREND_FOLLOWING,
    version="1.0.0",
    author="System",
    min_candles=50,
    recommended_timeframes=["60", "240", "D"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=1.5,
    expected_win_rate=0.48,
    expected_risk_reward=2.0,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.12,
    parameters=[
        ParameterSpec(
            name="fast_period",
            param_type=ParameterType.INT,
            default=12,
            description="MACD fast EMA period",
            min_value=8,
            max_value=20,
            step=1,
        ),
        ParameterSpec(
            name="slow_period",
            param_type=ParameterType.INT,
            default=26,
            description="MACD slow EMA period",
            min_value=20,
            max_value=40,
            step=2,
        ),
        ParameterSpec(
            name="signal_period",
            param_type=ParameterType.INT,
            default=9,
            description="MACD signal line period",
            min_value=5,
            max_value=15,
            step=1,
        ),
        ParameterSpec(
            name="atr_period",
            param_type=ParameterType.INT,
            default=14,
            description="ATR period for stop loss",
            min_value=7,
            max_value=21,
            step=1,
        ),
        ParameterSpec(
            name="atr_multiplier",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="ATR multiplier for stop loss",
            min_value=1.0,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="risk_reward",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Risk/reward ratio",
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="require_histogram_confirmation",
            param_type=ParameterType.BOOL,
            default=True,
            description="Require histogram confirmation",
        ),
    ],
    tags=["macd", "trend", "momentum", "classic"],
)


@register_strategy
class MACDTrendStrategy(LibraryStrategy):
    """
    MACD Trend Following Strategy.

    Buy on bullish MACD crossover, sell on bearish crossover.
    """

    STRATEGY_INFO = MACD_TREND_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # State tracking
        self._prev_macd: Optional[float] = None
        self._prev_signal: Optional[float] = None
        self._prev_histogram: Optional[float] = None

        # MACD history for proper calculation
        self._macd_values: List[float] = []

    def _calculate_macd_proper(
        self, fast: int, slow: int, signal_period: int
    ) -> tuple[float, float, float]:
        """Calculate MACD with proper signal line."""
        prices = self.get_closes()
        if len(prices) < slow + signal_period:
            return (0.0, 0.0, 0.0)

        # Calculate MACD line
        fast_ema = self.ema(fast, prices)
        slow_ema = self.ema(slow, prices)
        macd_line = fast_ema - slow_ema

        # Store MACD value
        self._macd_values.append(macd_line)
        if len(self._macd_values) > 100:
            self._macd_values = self._macd_values[-100:]

        # Calculate signal line (EMA of MACD)
        if len(self._macd_values) >= signal_period:
            multiplier = 2 / (signal_period + 1)
            signal_line = self._macd_values[0]
            for val in self._macd_values[1:]:
                signal_line = (val * multiplier) + (signal_line * (1 - multiplier))
        else:
            signal_line = macd_line * 0.9  # Approximation

        histogram = macd_line - signal_line

        return (macd_line, signal_line, histogram)

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate MACD signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Get parameters
        fast = self.get_param("fast_period", 12)
        slow = self.get_param("slow_period", 26)
        signal_period = self.get_param("signal_period", 9)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)
        require_hist = self.get_param("require_histogram_confirmation", True)

        # Calculate indicators
        macd_line, signal_line, histogram = self._calculate_macd_proper(
            fast, slow, signal_period
        )
        current_atr = self.atr(atr_period)
        close = candle["close"]

        # Need previous values
        if self._prev_macd is None:
            self._prev_macd = macd_line
            self._prev_signal = signal_line
            self._prev_histogram = histogram
            return None

        signal = None

        # Bullish crossover
        if self._prev_macd <= self._prev_signal and macd_line > signal_line:
            # Check histogram confirmation
            if not require_hist or histogram > 0:
                stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.BUY,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Bullish MACD crossover (MACD: {macd_line:.4f} > Signal: {signal_line:.4f})",
                    confidence=0.7,
                    macd=macd_line,
                    signal=signal_line,
                    histogram=histogram,
                )

        # Bearish crossover
        elif self._prev_macd >= self._prev_signal and macd_line < signal_line:
            if not require_hist or histogram < 0:
                stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Bearish MACD crossover (MACD: {macd_line:.4f} < Signal: {signal_line:.4f})",
                    confidence=0.7,
                    macd=macd_line,
                    signal=signal_line,
                    histogram=histogram,
                )

        # Update previous values
        self._prev_macd = macd_line
        self._prev_signal = signal_line
        self._prev_histogram = histogram

        return signal


# Factory functions for MACD
def create_conservative_macd_strategy(config: StrategyConfig) -> MACDTrendStrategy:
    """Create conservative MACD strategy."""
    return MACDTrendStrategy(
        config,
        fast_period=12,
        slow_period=26,
        signal_period=9,
        atr_multiplier=2.5,
        risk_reward=2.5,
        require_histogram_confirmation=True,
    )


def create_moderate_macd_strategy(config: StrategyConfig) -> MACDTrendStrategy:
    """Create moderate MACD strategy."""
    return MACDTrendStrategy(
        config,
        fast_period=12,
        slow_period=26,
        signal_period=9,
        atr_multiplier=2.0,
        risk_reward=2.0,
        require_histogram_confirmation=True,
    )


def create_aggressive_macd_strategy(config: StrategyConfig) -> MACDTrendStrategy:
    """Create aggressive MACD strategy."""
    return MACDTrendStrategy(
        config,
        fast_period=8,
        slow_period=21,
        signal_period=5,
        atr_multiplier=1.5,
        risk_reward=1.5,
        require_histogram_confirmation=False,
    )


# =============================================================================
# Triple EMA Strategy
# =============================================================================


@dataclass
class TripleEMAParams:
    """Parameters for Triple EMA strategy."""

    fast_period: int = 5
    medium_period: int = 13
    slow_period: int = 34
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0


TRIPLE_EMA_INFO = StrategyInfo(
    id="triple_ema",
    name="Triple EMA",
    description="""
    Advanced trend following using three EMAs.

    Uses fast, medium, and slow EMAs for trend confirmation.

    BUY: All EMAs aligned bullish (fast > medium > slow) and price above all.
    SELL: All EMAs aligned bearish (fast < medium < slow) and price below all.

    Best for: Strong trending markets.
    """,
    category=StrategyCategory.TREND_FOLLOWING,
    version="1.0.0",
    author="System",
    min_candles=50,
    recommended_timeframes=["60", "240"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=1.0,
    expected_win_rate=0.50,
    expected_risk_reward=2.5,
    typical_holding_period="hours",
    risk_level="conservative",
    max_drawdown_expected=0.10,
    parameters=[
        ParameterSpec(
            name="fast_period",
            param_type=ParameterType.INT,
            default=5,
            description="Fast EMA period",
            min_value=3,
            max_value=10,
            step=1,
        ),
        ParameterSpec(
            name="medium_period",
            param_type=ParameterType.INT,
            default=13,
            description="Medium EMA period",
            min_value=10,
            max_value=20,
            step=1,
        ),
        ParameterSpec(
            name="slow_period",
            param_type=ParameterType.INT,
            default=34,
            description="Slow EMA period",
            min_value=25,
            max_value=55,
            step=3,
        ),
        ParameterSpec(
            name="atr_period",
            param_type=ParameterType.INT,
            default=14,
            description="ATR period",
            min_value=7,
            max_value=21,
            step=1,
        ),
        ParameterSpec(
            name="atr_multiplier",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="ATR multiplier",
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="risk_reward",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Risk/reward ratio",
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
    ],
    tags=["ema", "triple", "trend", "confirmation"],
)


@register_strategy
class TripleEMAStrategy(LibraryStrategy):
    """
    Triple EMA Trend Strategy.

    Uses three EMAs for strong trend confirmation.
    """

    STRATEGY_INFO = TRIPLE_EMA_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # State tracking
        self._prev_aligned: Optional[str] = None  # "bullish", "bearish", None

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate signals on EMA alignment."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Get parameters
        fast_p = self.get_param("fast_period", 5)
        med_p = self.get_param("medium_period", 13)
        slow_p = self.get_param("slow_period", 34)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)

        # Calculate EMAs
        fast = self.ema(fast_p)
        medium = self.ema(med_p)
        slow = self.ema(slow_p)
        current_atr = self.atr(atr_period)

        close = candle["close"]

        # Determine current alignment
        current_aligned = None
        if fast > medium > slow and close > fast:
            current_aligned = "bullish"
        elif fast < medium < slow and close < fast:
            current_aligned = "bearish"

        signal = None

        # Generate signal on alignment change
        if current_aligned == "bullish" and self._prev_aligned != "bullish":
            stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
            take_profit = calculate_take_profit(close, stop_loss, rr)

            signal = self.create_signal(
                signal_type=SignalType.BUY,
                price=close,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=f"Triple EMA bullish alignment (Fast: {fast:.2f} > Med: {medium:.2f} > Slow: {slow:.2f})",
                confidence=0.75,
                fast_ema=fast,
                medium_ema=medium,
                slow_ema=slow,
            )

        elif current_aligned == "bearish" and self._prev_aligned != "bearish":
            stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
            take_profit = calculate_take_profit(close, stop_loss, rr)

            signal = self.create_signal(
                signal_type=SignalType.SELL,
                price=close,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=f"Triple EMA bearish alignment (Fast: {fast:.2f} < Med: {medium:.2f} < Slow: {slow:.2f})",
                confidence=0.75,
                fast_ema=fast,
                medium_ema=medium,
                slow_ema=slow,
            )

        self._prev_aligned = current_aligned

        return signal
