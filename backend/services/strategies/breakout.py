"""
Breakout Strategies.

Strategies that trade price breakouts:
- ATR Breakout: Trade volatility breakouts
- Donchian Channel: Trade channel breakouts
"""

import logging
from dataclasses import dataclass

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
    calculate_take_profit,
    register_strategy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ATR Breakout Strategy
# =============================================================================


@dataclass
class ATRBreakoutParams:
    """Parameters for ATR Breakout strategy."""

    atr_period: int = 14
    atr_multiplier: float = 1.5
    lookback_period: int = 20
    stop_atr_mult: float = 2.0
    risk_reward: float = 2.0
    require_volume_confirmation: bool = True
    volume_threshold: float = 1.5


ATR_BREAKOUT_INFO = StrategyInfo(
    id="atr_breakout",
    name="ATR Breakout",
    description="""
    Volatility breakout strategy using ATR.

    BUY: When price breaks above (close + ATR * multiplier).
    SELL: When price breaks below (close - ATR * multiplier).

    Uses ATR as a measure of "normal" volatility. A breakout occurs
    when price moves more than ATR * multiplier from recent average.

    Optional: Confirm with volume spike.

    Best for: Trending markets with volatility expansion.
    """,
    category=StrategyCategory.BREAKOUT,
    version="1.0.0",
    author="System",
    min_candles=30,
    recommended_timeframes=["60", "240", "D"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=1.0,
    expected_win_rate=0.40,
    expected_risk_reward=3.0,
    typical_holding_period="hours",
    risk_level="aggressive",
    max_drawdown_expected=0.20,
    parameters=[
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
            default=1.5,
            description="ATR multiplier for breakout detection",
            min_value=1.0,
            max_value=3.0,
            step=0.25,
        ),
        ParameterSpec(
            name="lookback_period",
            param_type=ParameterType.INT,
            default=20,
            description="Period to calculate average price",
            min_value=10,
            max_value=50,
            step=5,
        ),
        ParameterSpec(
            name="stop_atr_mult",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="ATR multiplier for stop loss",
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="risk_reward",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Risk/reward ratio",
            min_value=2.0,
            max_value=5.0,
            step=0.5,
        ),
        ParameterSpec(
            name="require_volume_confirmation",
            param_type=ParameterType.BOOL,
            default=True,
            description="Require volume spike confirmation",
        ),
        ParameterSpec(
            name="volume_threshold",
            param_type=ParameterType.FLOAT,
            default=1.5,
            description="Volume must be this times above average",
            min_value=1.2,
            max_value=3.0,
            step=0.1,
        ),
    ],
    tags=["atr", "breakout", "volatility", "trend"],
)


@register_strategy
class ATRBreakoutStrategy(LibraryStrategy):
    """
    ATR Breakout Strategy.

    Trade volatility breakouts using ATR.
    """

    STRATEGY_INFO = ATR_BREAKOUT_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        self._in_position: str = ""
        self._prev_breakout_level_up: float | None = None
        self._prev_breakout_level_down: float | None = None

    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate breakout signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Parameters
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 1.5)
        lookback = self.get_param("lookback_period", 20)
        stop_mult = self.get_param("stop_atr_mult", 2.0)
        rr = self.get_param("risk_reward", 2.0)
        use_volume = self.get_param("require_volume_confirmation", True)
        vol_threshold = self.get_param("volume_threshold", 1.5)

        # Calculate indicators
        current_atr = self.atr(atr_period)
        avg_close = self.sma(lookback)

        # Volume check
        volumes = self.get_volumes(lookback)
        if volumes and use_volume:
            avg_volume = sum(volumes) / len(volumes)
            current_volume = candle.get("volume", 0)
            volume_ok = current_volume >= avg_volume * vol_threshold
        else:
            volume_ok = True

        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        # Calculate breakout levels
        breakout_up = avg_close + (current_atr * atr_mult)
        breakout_down = avg_close - (current_atr * atr_mult)

        signal = None

        # Entry signals
        if not self._in_position:
            # Bullish breakout
            if high >= breakout_up and volume_ok:
                # Check it's a fresh breakout
                if (
                    self._prev_breakout_level_up is None
                    or self._prev_breakout_level_up < breakout_up * 0.99
                ):
                    stop_loss = close - (current_atr * stop_mult)
                    take_profit = calculate_take_profit(close, stop_loss, rr)

                    signal = self.create_signal(
                        signal_type=SignalType.BUY,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"ATR breakout UP (Price: {close:.2f} > Level: {breakout_up:.2f})",
                        confidence=0.7 if volume_ok else 0.55,
                        breakout_level=breakout_up,
                        atr=current_atr,
                    )
                    self._in_position = "long"

            # Bearish breakout
            elif low <= breakout_down and volume_ok:
                if (
                    self._prev_breakout_level_down is None
                    or self._prev_breakout_level_down > breakout_down * 1.01
                ):
                    stop_loss = close + (current_atr * stop_mult)
                    take_profit = calculate_take_profit(close, stop_loss, rr)

                    signal = self.create_signal(
                        signal_type=SignalType.SELL,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"ATR breakout DOWN (Price: {close:.2f} < Level: {breakout_down:.2f})",
                        confidence=0.7 if volume_ok else 0.55,
                        breakout_level=breakout_down,
                        atr=current_atr,
                    )
                    self._in_position = "short"

        # Exit on opposite breakout
        elif self._in_position == "long" and low <= breakout_down:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"Price broke down ({close:.2f} < {breakout_down:.2f})",
                confidence=0.6,
            )
            self._in_position = ""

        elif self._in_position == "short" and high >= breakout_up:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"Price broke up ({close:.2f} > {breakout_up:.2f})",
                confidence=0.6,
            )
            self._in_position = ""

        # Update breakout levels
        self._prev_breakout_level_up = breakout_up
        self._prev_breakout_level_down = breakout_down

        return signal


# =============================================================================
# Donchian Channel Breakout Strategy
# =============================================================================


@dataclass
class DonchianBreakoutParams:
    """Parameters for Donchian Channel strategy."""

    channel_period: int = 20
    exit_period: int = 10
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0


DONCHIAN_INFO = StrategyInfo(
    id="donchian_breakout",
    name="Donchian Channel Breakout",
    description="""
    Classic turtle trading breakout strategy.

    BUY: When price breaks above the N-period high (channel upper).
    SELL: When price breaks below the N-period low (channel lower).
    EXIT: When price crosses the M-period opposite channel.

    Originally used by Richard Dennis's "Turtle Traders".

    Best for: Strong trending markets.
    """,
    category=StrategyCategory.BREAKOUT,
    version="1.0.0",
    author="System",
    min_candles=30,
    recommended_timeframes=["240", "D"],
    suitable_markets=["crypto", "forex", "commodities"],
    avg_trades_per_day=0.5,
    expected_win_rate=0.38,
    expected_risk_reward=4.0,
    typical_holding_period="days",
    risk_level="aggressive",
    max_drawdown_expected=0.25,
    parameters=[
        ParameterSpec(
            name="channel_period",
            param_type=ParameterType.INT,
            default=20,
            description="Donchian channel period (entry)",
            min_value=10,
            max_value=55,
            step=5,
        ),
        ParameterSpec(
            name="exit_period",
            param_type=ParameterType.INT,
            default=10,
            description="Donchian channel period (exit)",
            min_value=5,
            max_value=20,
            step=5,
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
            min_value=1.5,
            max_value=4.0,
            step=0.5,
        ),
        ParameterSpec(
            name="risk_reward",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Risk/reward ratio",
            min_value=2.0,
            max_value=5.0,
            step=0.5,
        ),
    ],
    tags=["donchian", "breakout", "turtle", "trend"],
)


@register_strategy
class DonchianBreakoutStrategy(LibraryStrategy):
    """
    Donchian Channel Breakout Strategy (Turtle Trading).

    Trade breakouts of N-period high/low.
    """

    STRATEGY_INFO = DONCHIAN_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        self._in_position: str = ""
        self._entry_price: float | None = None

    def _donchian_channel(self, period: int) -> tuple[float, float]:
        """Calculate Donchian channel (highest high, lowest low)."""
        highs = self.get_highs(period)
        lows = self.get_lows(period)

        if not highs or not lows:
            return (0.0, 0.0)

        return (max(highs), min(lows))

    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate Donchian breakout signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Parameters
        entry_period = self.get_param("channel_period", 20)
        exit_period = self.get_param("exit_period", 10)
        atr_period = self.get_param("atr_period", 14)
        # atr_multiplier reserved for future volatility-based stops
        _ = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)

        # Calculate channels
        entry_high, entry_low = self._donchian_channel(entry_period)
        exit_high, exit_low = self._donchian_channel(exit_period)
        # ATR calculated for potential future use
        _ = self.atr(atr_period)

        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        signal = None

        # Entry signals
        if not self._in_position:
            # Long breakout
            if high >= entry_high and entry_high > 0:
                stop_loss = entry_low  # Classic: stop at channel low
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.BUY,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Donchian breakout UP ({high:.2f} >= {entry_high:.2f})",
                    confidence=0.6,
                    channel_high=entry_high,
                    channel_low=entry_low,
                )
                self._in_position = "long"
                self._entry_price = close

            # Short breakout
            elif low <= entry_low and entry_low > 0:
                stop_loss = entry_high  # Classic: stop at channel high
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Donchian breakout DOWN ({low:.2f} <= {entry_low:.2f})",
                    confidence=0.6,
                    channel_high=entry_high,
                    channel_low=entry_low,
                )
                self._in_position = "short"
                self._entry_price = close

        # Exit signals (using shorter channel)
        elif self._in_position == "long" and low <= exit_low:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"Exit long at Donchian low ({low:.2f} <= {exit_low:.2f})",
                confidence=0.7,
            )
            self._in_position = ""
            self._entry_price = None

        elif self._in_position == "short" and high >= exit_high:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"Exit short at Donchian high ({high:.2f} >= {exit_high:.2f})",
                confidence=0.7,
            )
            self._in_position = ""
            self._entry_price = None

        return signal
