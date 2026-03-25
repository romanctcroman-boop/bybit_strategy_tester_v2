"""
Mean Reversion Strategies.

Strategies that trade price returning to average/mean:
- RSI Mean Reversion: Trade oversold/overbought RSI levels
- Bollinger Bands: Trade price touching bands

DEPRECATION NOTE (2026-02-16):
    RSIMeanReversionStrategy is part of the OLD Library system.
    For new strategies, use the UNIVERSAL RSI block in Strategy Builder instead.
    The universal RSI block (type='rsi') supports:
      - Range filter mode (use_long_range/use_short_range)
      - Cross level mode (use_cross_level)
      - Legacy fallback mode
      - BTC source, optimization ranges, cross signal memory
    AI agents (DeepSeek, Qwen, Perplexity) MUST use the universal RSI block.
    This file is kept for backward compatibility with existing saved strategies.
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
    calculate_stop_loss,
    calculate_take_profit,
    register_strategy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RSI Mean Reversion Strategy
# =============================================================================


@dataclass
class RSIMeanReversionParams:
    """Parameters for RSI Mean Reversion strategy."""

    rsi_period: int = 14
    oversold_level: float = 30.0
    overbought_level: float = 70.0
    exit_level: float = 50.0
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0
    require_trend_filter: bool = False
    trend_ema_period: int = 200


RSI_MEAN_REVERSION_INFO = StrategyInfo(
    id="rsi_mean_reversion",
    name="RSI Mean Reversion",
    description="""
    Mean reversion strategy using RSI oscillator.

    BUY: When RSI crosses below oversold level (default 30).
    SELL: When RSI crosses above overbought level (default 70).
    EXIT: When RSI returns to neutral zone (default 50).

    Optional: Only trade in direction of 200 EMA trend.

    Best for: Ranging/sideways markets.
    Avoid in: Strong trending markets.
    """,
    category=StrategyCategory.MEAN_REVERSION,
    version="1.0.0",
    author="System",
    min_candles=50,
    recommended_timeframes=["15", "60"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=3.0,
    expected_win_rate=0.55,
    expected_risk_reward=1.5,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.15,
    parameters=[
        ParameterSpec(
            name="rsi_period",
            param_type=ParameterType.INT,
            default=14,
            description="RSI period",
            min_value=7,
            max_value=21,
            step=1,
        ),
        ParameterSpec(
            name="oversold_level",
            param_type=ParameterType.FLOAT,
            default=30.0,
            description="RSI oversold level (buy zone)",
            min_value=20.0,
            max_value=40.0,
            step=5.0,
        ),
        ParameterSpec(
            name="overbought_level",
            param_type=ParameterType.FLOAT,
            default=70.0,
            description="RSI overbought level (sell zone)",
            min_value=60.0,
            max_value=80.0,
            step=5.0,
        ),
        ParameterSpec(
            name="exit_level",
            param_type=ParameterType.FLOAT,
            default=50.0,
            description="RSI neutral exit level",
            min_value=45.0,
            max_value=55.0,
            step=5.0,
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
            min_value=1.0,
            max_value=3.0,
            step=0.5,
        ),
        ParameterSpec(
            name="require_trend_filter",
            param_type=ParameterType.BOOL,
            default=False,
            description="Only trade with trend",
        ),
        ParameterSpec(
            name="trend_ema_period",
            param_type=ParameterType.INT,
            default=200,
            description="Trend EMA period",
            min_value=100,
            max_value=200,
            step=50,
            optimize=False,
        ),
    ],
    tags=["rsi", "mean-reversion", "oscillator", "beginner-friendly"],
)


@register_strategy
class RSIMeanReversionStrategy(LibraryStrategy):
    """
    RSI Mean Reversion Strategy.

    Buy on oversold, sell on overbought RSI levels.
    """

    STRATEGY_INFO = RSI_MEAN_REVERSION_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        # State
        self._prev_rsi: float | None = None
        self._in_position: str = ""  # "long", "short", ""

    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate RSI signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Get parameters
        rsi_period = self.get_param("rsi_period", 14)
        oversold = self.get_param("oversold_level", 30.0)
        overbought = self.get_param("overbought_level", 70.0)
        exit_level = self.get_param("exit_level", 50.0)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)
        use_trend = self.get_param("require_trend_filter", False)
        trend_period = self.get_param("trend_ema_period", 200)

        # Calculate indicators
        current_rsi = self.rsi(rsi_period)
        current_atr = self.atr(atr_period)
        trend_ema = self.ema(trend_period) if use_trend else None

        close = candle["close"]

        if self._prev_rsi is None:
            self._prev_rsi = current_rsi
            return None

        signal = None

        # Entry signals
        if not self._in_position:
            # Buy on oversold
            if self._prev_rsi > oversold and current_rsi <= oversold:
                # Trend filter check
                if not use_trend or (trend_ema and close > trend_ema):
                    stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                    take_profit = calculate_take_profit(close, stop_loss, rr)

                    signal = self.create_signal(
                        signal_type=SignalType.BUY,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"RSI oversold ({current_rsi:.1f} <= {oversold})",
                        confidence=0.65,
                        rsi=current_rsi,
                    )
                    self._in_position = "long"

            # Sell on overbought (with trend filter check)
            elif (
                self._prev_rsi < overbought
                and current_rsi >= overbought
                and (not use_trend or (trend_ema and close < trend_ema))
            ):
                stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI overbought ({current_rsi:.1f} >= {overbought})",
                    confidence=0.65,
                    rsi=current_rsi,
                )
                self._in_position = "short"

        # Exit signals
        elif self._in_position == "long" and current_rsi >= exit_level:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"RSI reached neutral ({current_rsi:.1f} >= {exit_level})",
                confidence=0.6,
                rsi=current_rsi,
            )
            self._in_position = ""

        elif self._in_position == "short" and current_rsi <= exit_level:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"RSI reached neutral ({current_rsi:.1f} <= {exit_level})",
                confidence=0.6,
                rsi=current_rsi,
            )
            self._in_position = ""

        self._prev_rsi = current_rsi
        return signal


# Factory functions
def create_conservative_rsi_strategy(
    config: StrategyConfig,
) -> RSIMeanReversionStrategy:
    """Create conservative RSI strategy (extreme levels, trend filter)."""
    return RSIMeanReversionStrategy(
        config,
        rsi_period=14,
        oversold_level=25.0,
        overbought_level=75.0,
        exit_level=50.0,
        atr_multiplier=2.5,
        risk_reward=2.0,
        require_trend_filter=True,
    )


def create_moderate_rsi_strategy(config: StrategyConfig) -> RSIMeanReversionStrategy:
    """Create moderate RSI strategy (standard levels)."""
    return RSIMeanReversionStrategy(
        config,
        rsi_period=14,
        oversold_level=30.0,
        overbought_level=70.0,
        exit_level=50.0,
        atr_multiplier=2.0,
        risk_reward=1.5,
        require_trend_filter=False,
    )


def create_aggressive_rsi_strategy(config: StrategyConfig) -> RSIMeanReversionStrategy:
    """Create aggressive RSI strategy (wider levels, more trades)."""
    return RSIMeanReversionStrategy(
        config,
        rsi_period=7,
        oversold_level=35.0,
        overbought_level=65.0,
        exit_level=50.0,
        atr_multiplier=1.5,
        risk_reward=1.5,
        require_trend_filter=False,
    )


# =============================================================================
# Bollinger Bands Strategy
# =============================================================================


@dataclass
class BollingerBandsParams:
    """Parameters for Bollinger Bands strategy."""

    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0
    require_rsi_confirmation: bool = True
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0


BOLLINGER_BANDS_INFO = StrategyInfo(
    id="bollinger_bands",
    name="Bollinger Bands Mean Reversion",
    description="""
    Mean reversion strategy using Bollinger Bands.

    BUY: When price touches/crosses below lower band.
    SELL: When price touches/crosses above upper band.
    EXIT: When price returns to middle band.

    Optional: Confirm with RSI for higher probability.

    Best for: Range-bound markets with regular oscillation.
    """,
    category=StrategyCategory.MEAN_REVERSION,
    version="1.0.0",
    author="System",
    min_candles=30,
    recommended_timeframes=["15", "60", "240"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=2.5,
    expected_win_rate=0.52,
    expected_risk_reward=1.8,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.12,
    parameters=[
        ParameterSpec(
            name="bb_period",
            param_type=ParameterType.INT,
            default=20,
            description="Bollinger Bands period",
            min_value=10,
            max_value=30,
            step=2,
        ),
        ParameterSpec(
            name="bb_std",
            param_type=ParameterType.FLOAT,
            default=2.0,
            description="Standard deviation multiplier",
            min_value=1.5,
            max_value=3.0,
            step=0.25,
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
            min_value=1.0,
            max_value=3.0,
            step=0.5,
        ),
        ParameterSpec(
            name="require_rsi_confirmation",
            param_type=ParameterType.BOOL,
            default=True,
            description="Require RSI confirmation",
        ),
        ParameterSpec(
            name="rsi_period",
            param_type=ParameterType.INT,
            default=14,
            description="RSI period for confirmation",
            min_value=7,
            max_value=21,
            step=1,
            optimize=False,
        ),
        ParameterSpec(
            name="rsi_oversold",
            param_type=ParameterType.FLOAT,
            default=30.0,
            description="RSI oversold level",
            min_value=20.0,
            max_value=35.0,
            step=5.0,
            optimize=False,
        ),
        ParameterSpec(
            name="rsi_overbought",
            param_type=ParameterType.FLOAT,
            default=70.0,
            description="RSI overbought level",
            min_value=65.0,
            max_value=80.0,
            step=5.0,
            optimize=False,
        ),
    ],
    tags=["bollinger", "bands", "mean-reversion", "volatility"],
)


@register_strategy
class BollingerBandsStrategy(LibraryStrategy):
    """
    Bollinger Bands Mean Reversion Strategy.

    Trade when price reaches the bands expecting reversion to mean.
    """

    STRATEGY_INFO = BOLLINGER_BANDS_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        self._in_position: str = ""
        self._entry_price: float | None = None

    def on_candle(self, candle: dict) -> TradingSignal | None:
        """Process candle and generate Bollinger Band signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Get parameters
        bb_period = self.get_param("bb_period", 20)
        bb_std = self.get_param("bb_std", 2.0)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        # risk_reward reserved for future TP calculations
        _ = self.get_param("risk_reward", 2.0)
        use_rsi = self.get_param("require_rsi_confirmation", True)
        rsi_period = self.get_param("rsi_period", 14)
        rsi_oversold = self.get_param("rsi_oversold", 30.0)
        rsi_overbought = self.get_param("rsi_overbought", 70.0)

        # Calculate indicators
        upper, middle, lower = self.bollinger_bands(bb_period, bb_std)
        current_atr = self.atr(atr_period)
        current_rsi = self.rsi(rsi_period) if use_rsi else 50.0

        close = candle["close"]
        low = candle["low"]
        high = candle["high"]

        signal = None

        # Entry signals
        if not self._in_position:
            # Buy at lower band
            if low <= lower:
                # RSI confirmation
                if not use_rsi or current_rsi <= rsi_oversold:
                    stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                    take_profit = middle  # Target middle band

                    signal = self.create_signal(
                        signal_type=SignalType.BUY,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"Price touched lower Bollinger Band ({lower:.2f})",
                        confidence=0.7 if use_rsi else 0.6,
                        bb_upper=upper,
                        bb_middle=middle,
                        bb_lower=lower,
                        rsi=current_rsi,
                    )
                    self._in_position = "long"
                    self._entry_price = close

            # Sell at upper band (with RSI confirmation)
            elif high >= upper and (not use_rsi or current_rsi >= rsi_overbought):
                stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
                take_profit = middle  # Target middle band

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Price touched upper Bollinger Band ({upper:.2f})",
                    confidence=0.7 if use_rsi else 0.6,
                    bb_upper=upper,
                    bb_middle=middle,
                    bb_lower=lower,
                    rsi=current_rsi,
                )
                self._in_position = "short"
                self._entry_price = close

        # Exit at middle band
        elif self._in_position == "long" and close >= middle:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"Price reached middle band ({middle:.2f})",
                confidence=0.7,
                bb_middle=middle,
            )
            self._in_position = ""
            self._entry_price = None

        elif self._in_position == "short" and close <= middle:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"Price reached middle band ({middle:.2f})",
                confidence=0.7,
                bb_middle=middle,
            )
            self._in_position = ""
            self._entry_price = None

        return signal


# Factory functions
def create_conservative_bollinger_strategy(
    config: StrategyConfig,
) -> BollingerBandsStrategy:
    """Create conservative Bollinger strategy (wider bands, RSI confirmation)."""
    return BollingerBandsStrategy(
        config,
        bb_period=20,
        bb_std=2.5,
        atr_multiplier=2.5,
        risk_reward=2.0,
        require_rsi_confirmation=True,
        rsi_oversold=25.0,
        rsi_overbought=75.0,
    )


def create_moderate_bollinger_strategy(
    config: StrategyConfig,
) -> BollingerBandsStrategy:
    """Create moderate Bollinger strategy (standard settings)."""
    return BollingerBandsStrategy(
        config,
        bb_period=20,
        bb_std=2.0,
        atr_multiplier=2.0,
        risk_reward=1.8,
        require_rsi_confirmation=True,
    )


def create_aggressive_bollinger_strategy(
    config: StrategyConfig,
) -> BollingerBandsStrategy:
    """Create aggressive Bollinger strategy (tighter bands, no RSI)."""
    return BollingerBandsStrategy(
        config,
        bb_period=14,
        bb_std=1.5,
        atr_multiplier=1.5,
        risk_reward=1.5,
        require_rsi_confirmation=False,
    )
