"""
Momentum Strategies.

Strategies that trade momentum continuation:
- RSI Momentum: Trade in direction of strong RSI readings
- Stochastic Momentum: Trade stochastic crossovers
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
# RSI Momentum Strategy
# =============================================================================


@dataclass
class RSIMomentumParams:
    """Parameters for RSI Momentum strategy."""

    rsi_period: int = 14
    momentum_threshold: float = 50.0
    strong_momentum: float = 60.0
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0
    require_trend: bool = True
    trend_ema_period: int = 50


RSI_MOMENTUM_INFO = StrategyInfo(
    id="rsi_momentum",
    name="RSI Momentum",
    description="""
    Momentum strategy using RSI as trend strength indicator.

    Unlike mean reversion, this trades WITH momentum:
    BUY: When RSI crosses above 50 (or 60 for strong momentum).
    SELL: When RSI crosses below 50 (or 40 for strong momentum).

    Idea: RSI above 50 = bullish momentum, below 50 = bearish.

    Best for: Trending markets with clear momentum.
    """,
    category=StrategyCategory.MOMENTUM,
    version="1.0.0",
    author="System",
    min_candles=50,
    recommended_timeframes=["60", "240"],
    suitable_markets=["crypto", "forex"],
    avg_trades_per_day=2.0,
    expected_win_rate=0.45,
    expected_risk_reward=2.5,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.18,
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
            name="momentum_threshold",
            param_type=ParameterType.FLOAT,
            default=50.0,
            description="RSI level that defines momentum direction",
            min_value=45.0,
            max_value=55.0,
            step=5.0,
        ),
        ParameterSpec(
            name="strong_momentum",
            param_type=ParameterType.FLOAT,
            default=60.0,
            description="RSI level for strong momentum signals",
            min_value=55.0,
            max_value=65.0,
            step=5.0,
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
            max_value=3.5,
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
            name="require_trend",
            param_type=ParameterType.BOOL,
            default=True,
            description="Require EMA trend confirmation",
        ),
        ParameterSpec(
            name="trend_ema_period",
            param_type=ParameterType.INT,
            default=50,
            description="Trend EMA period",
            min_value=30,
            max_value=100,
            step=10,
        ),
    ],
    tags=["rsi", "momentum", "trend-following"],
)


@register_strategy
class RSIMomentumStrategy(LibraryStrategy):
    """
    RSI Momentum Strategy.

    Trade in direction of RSI momentum.
    """

    STRATEGY_INFO = RSI_MOMENTUM_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        self._prev_rsi: Optional[float] = None
        self._in_position: str = ""

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate momentum signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Parameters
        rsi_period = self.get_param("rsi_period", 14)
        threshold = self.get_param("momentum_threshold", 50.0)
        strong = self.get_param("strong_momentum", 60.0)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)
        use_trend = self.get_param("require_trend", True)
        trend_period = self.get_param("trend_ema_period", 50)

        # Calculate indicators
        current_rsi = self.rsi(rsi_period)
        current_atr = self.atr(atr_period)
        trend_ema = self.ema(trend_period) if use_trend else None

        close = candle["close"]

        if self._prev_rsi is None:
            self._prev_rsi = current_rsi
            return None

        signal = None
        weak_threshold = 100 - strong  # 40 if strong=60

        # Entry: RSI crosses above threshold = bullish momentum
        if not self._in_position:
            # Bullish momentum
            if self._prev_rsi <= threshold and current_rsi > threshold:
                if not use_trend or (trend_ema and close > trend_ema):
                    confidence = 0.7 if current_rsi >= strong else 0.6
                    stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                    take_profit = calculate_take_profit(close, stop_loss, rr)

                    signal = self.create_signal(
                        signal_type=SignalType.BUY,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"Bullish RSI momentum ({current_rsi:.1f} > {threshold})",
                        confidence=confidence,
                        rsi=current_rsi,
                    )
                    self._in_position = "long"

            # Bearish momentum
            elif self._prev_rsi >= threshold and current_rsi < threshold:
                if not use_trend or (trend_ema and close < trend_ema):
                    confidence = 0.7 if current_rsi <= weak_threshold else 0.6
                    stop_loss = calculate_stop_loss(
                        close, "sell", current_atr, atr_mult
                    )
                    take_profit = calculate_take_profit(close, stop_loss, rr)

                    signal = self.create_signal(
                        signal_type=SignalType.SELL,
                        price=close,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"Bearish RSI momentum ({current_rsi:.1f} < {threshold})",
                        confidence=confidence,
                        rsi=current_rsi,
                    )
                    self._in_position = "short"

        # Exit on momentum reversal
        elif self._in_position == "long" and current_rsi < threshold:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"Momentum reversal ({current_rsi:.1f} < {threshold})",
                confidence=0.6,
                rsi=current_rsi,
            )
            self._in_position = ""

        elif self._in_position == "short" and current_rsi > threshold:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"Momentum reversal ({current_rsi:.1f} > {threshold})",
                confidence=0.6,
                rsi=current_rsi,
            )
            self._in_position = ""

        self._prev_rsi = current_rsi
        return signal


# =============================================================================
# Stochastic Momentum Strategy
# =============================================================================


@dataclass
class StochasticMomentumParams:
    """Parameters for Stochastic Momentum strategy."""

    k_period: int = 14
    d_period: int = 3
    smooth_k: int = 3
    oversold: float = 20.0
    overbought: float = 80.0
    atr_period: int = 14
    atr_multiplier: float = 2.0
    risk_reward: float = 2.0


STOCHASTIC_INFO = StrategyInfo(
    id="stochastic_momentum",
    name="Stochastic Momentum",
    description="""
    Momentum strategy using Stochastic oscillator.

    BUY: When %K crosses above %D in oversold zone (<20).
    SELL: When %K crosses below %D in overbought zone (>80).

    Combines mean reversion (zones) with momentum (%K/%D cross).

    Best for: Markets with clear swings.
    """,
    category=StrategyCategory.MOMENTUM,
    version="1.0.0",
    author="System",
    min_candles=30,
    recommended_timeframes=["15", "60"],
    suitable_markets=["crypto", "forex", "stocks"],
    avg_trades_per_day=3.0,
    expected_win_rate=0.50,
    expected_risk_reward=1.8,
    typical_holding_period="hours",
    risk_level="moderate",
    max_drawdown_expected=0.15,
    parameters=[
        ParameterSpec(
            name="k_period",
            param_type=ParameterType.INT,
            default=14,
            description="Stochastic %K period",
            min_value=5,
            max_value=21,
            step=1,
        ),
        ParameterSpec(
            name="d_period",
            param_type=ParameterType.INT,
            default=3,
            description="Stochastic %D period (SMA of %K)",
            min_value=2,
            max_value=5,
            step=1,
        ),
        ParameterSpec(
            name="smooth_k",
            param_type=ParameterType.INT,
            default=3,
            description="Smoothing for %K",
            min_value=1,
            max_value=5,
            step=1,
        ),
        ParameterSpec(
            name="oversold",
            param_type=ParameterType.FLOAT,
            default=20.0,
            description="Oversold level",
            min_value=10.0,
            max_value=30.0,
            step=5.0,
        ),
        ParameterSpec(
            name="overbought",
            param_type=ParameterType.FLOAT,
            default=80.0,
            description="Overbought level",
            min_value=70.0,
            max_value=90.0,
            step=5.0,
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
            max_value=3.0,
            step=0.5,
        ),
    ],
    tags=["stochastic", "momentum", "oscillator"],
)


@register_strategy
class StochasticMomentumStrategy(LibraryStrategy):
    """
    Stochastic Momentum Strategy.

    Trade %K/%D crossovers in overbought/oversold zones.
    """

    STRATEGY_INFO = STOCHASTIC_INFO

    def __init__(self, config: StrategyConfig, **params):
        super().__init__(config, **params)

        self._k_values: List[float] = []
        self._prev_k: Optional[float] = None
        self._prev_d: Optional[float] = None
        self._in_position: str = ""

    def _calculate_stochastic(
        self, k_period: int, d_period: int, smooth_k: int
    ) -> tuple[float, float]:
        """Calculate Stochastic %K and %D."""
        candles = self.get_candles()
        if len(candles) < k_period:
            return (50.0, 50.0)

        # Raw %K values
        raw_k_values = []
        for i in range(min(k_period + smooth_k, len(candles))):
            end_idx = len(candles) - i
            start_idx = max(0, end_idx - k_period)

            period_candles = candles[start_idx:end_idx]
            if not period_candles:
                continue

            highest = max(c["high"] for c in period_candles)
            lowest = min(c["low"] for c in period_candles)
            close = period_candles[-1]["close"]

            if highest == lowest:
                raw_k = 50.0
            else:
                raw_k = ((close - lowest) / (highest - lowest)) * 100

            raw_k_values.insert(0, raw_k)

        if len(raw_k_values) < smooth_k:
            return (50.0, 50.0)

        # Smoothed %K (SMA of raw %K)
        k = sum(raw_k_values[-smooth_k:]) / smooth_k

        # Store for %D calculation
        self._k_values.append(k)
        if len(self._k_values) > 50:
            self._k_values = self._k_values[-50:]

        # %D (SMA of %K)
        if len(self._k_values) >= d_period:
            d = sum(self._k_values[-d_period:]) / d_period
        else:
            d = k

        return (k, d)

    def on_candle(self, candle: dict) -> Optional[TradingSignal]:
        """Process candle and generate stochastic signals."""
        self.add_candle(candle)

        if not self.warmup_complete():
            return None

        # Parameters
        k_period = self.get_param("k_period", 14)
        d_period = self.get_param("d_period", 3)
        smooth_k = self.get_param("smooth_k", 3)
        oversold = self.get_param("oversold", 20.0)
        overbought = self.get_param("overbought", 80.0)
        atr_period = self.get_param("atr_period", 14)
        atr_mult = self.get_param("atr_multiplier", 2.0)
        rr = self.get_param("risk_reward", 2.0)

        # Calculate indicators
        k, d = self._calculate_stochastic(k_period, d_period, smooth_k)
        current_atr = self.atr(atr_period)

        close = candle["close"]

        if self._prev_k is None:
            self._prev_k = k
            self._prev_d = d
            return None

        signal = None

        # Entry signals
        if not self._in_position:
            # Bullish: %K crosses above %D in oversold zone
            if self._prev_k <= self._prev_d and k > d and self._prev_k <= oversold:
                stop_loss = calculate_stop_loss(close, "buy", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.BUY,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Stochastic bullish crossover in oversold (%K:{k:.1f} > %D:{d:.1f})",
                    confidence=0.65,
                    stoch_k=k,
                    stoch_d=d,
                )
                self._in_position = "long"

            # Bearish: %K crosses below %D in overbought zone
            elif self._prev_k >= self._prev_d and k < d and self._prev_k >= overbought:
                stop_loss = calculate_stop_loss(close, "sell", current_atr, atr_mult)
                take_profit = calculate_take_profit(close, stop_loss, rr)

                signal = self.create_signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"Stochastic bearish crossover in overbought (%K:{k:.1f} < %D:{d:.1f})",
                    confidence=0.65,
                    stoch_k=k,
                    stoch_d=d,
                )
                self._in_position = "short"

        # Exit on opposite zone
        elif self._in_position == "long" and k >= overbought:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_LONG,
                price=close,
                reason=f"Stochastic reached overbought ({k:.1f})",
                confidence=0.6,
                stoch_k=k,
            )
            self._in_position = ""

        elif self._in_position == "short" and k <= oversold:
            signal = self.create_signal(
                signal_type=SignalType.CLOSE_SHORT,
                price=close,
                reason=f"Stochastic reached oversold ({k:.1f})",
                confidence=0.6,
                stoch_k=k,
            )
            self._in_position = ""

        self._prev_k = k
        self._prev_d = d

        return signal
