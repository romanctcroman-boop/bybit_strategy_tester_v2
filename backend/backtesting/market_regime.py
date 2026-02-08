"""
📊 Market Regime Detection Module

Identifies market conditions to improve strategy performance by adapting
entry signals, position sizing, and risk management to current regime.

Market Regimes:
1. TRENDING_UP - Strong upward trend (ADX high, +DI > -DI)
2. TRENDING_DOWN - Strong downward trend (ADX high, -DI > +DI)
3. RANGING - Low volatility sideways (ADX low, tight BBands)
4. VOLATILE - High volatility, no clear direction
5. BREAKOUT - Transitioning from ranging to trending

Detection Methods:
- ADX + DI for trend strength/direction
- Bollinger Bandwidth for volatility
- ATR for volatility magnitude
- Heikin Ashi for trend smoothing

Example Usage:
    from backend.backtesting.market_regime import MarketRegimeDetector, RegimeType

    # Create detector
    detector = MarketRegimeDetector()

    # Detect regime for current bar
    regime = detector.detect(
        high=df['high'].values,
        low=df['low'].values,
        close=df['close'].values,
        idx=current_idx,
    )

    if regime.regime == RegimeType.TRENDING_UP:
        # Allow only LONG trades
        pass
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from backend.backtesting.mtf.filters import (
    calculate_adx,
    calculate_atr,
    calculate_bandwidth,
    calculate_bollinger_bands,
    calculate_ema,
)

logger = logging.getLogger(__name__)


class RegimeType(Enum):
    """Market regime types."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """Current market regime state."""

    regime: RegimeType
    confidence: float  # 0-1 confidence score
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    volatility: float = 0.0  # ATR as % of price
    bandwidth: float = 0.0  # Bollinger bandwidth
    trend_strength: float = 0.0  # Normalized 0-1
    allow_long: bool = True
    allow_short: bool = True
    recommended_position_size: float = 1.0  # Multiplier
    reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 3),
            "adx": round(self.adx, 2),
            "plus_di": round(self.plus_di, 2),
            "minus_di": round(self.minus_di, 2),
            "volatility": round(self.volatility, 4),
            "bandwidth": round(self.bandwidth, 2),
            "trend_strength": round(self.trend_strength, 3),
            "allow_long": self.allow_long,
            "allow_short": self.allow_short,
            "recommended_position_size": round(self.recommended_position_size, 3),
            "reason": self.reason,
        }


@dataclass
class RegimeConfig:
    """Configuration for regime detection thresholds."""

    # ADX thresholds
    adx_trending_threshold: float = 25.0  # Above = trending
    adx_strong_threshold: float = 40.0  # Very strong trend
    adx_weak_threshold: float = 15.0  # Below = ranging

    # Volatility thresholds (ATR % of price)
    volatility_low: float = 0.005  # 0.5%
    volatility_high: float = 0.02  # 2%
    volatility_extreme: float = 0.05  # 5%

    # Bollinger Bandwidth thresholds
    bandwidth_squeeze: float = 4.0  # Below = squeeze
    bandwidth_normal: float = 8.0  # Normal range
    bandwidth_wide: float = 15.0  # Above = volatile

    # Detection periods
    adx_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_std_dev: float = 2.0

    # Position sizing adjustments
    trending_size_mult: float = 1.2  # Larger in trends
    ranging_size_mult: float = 0.8  # Smaller in ranges
    volatile_size_mult: float = 0.5  # Much smaller in volatile

    # Lookback for regime persistence
    regime_lookback: int = 5  # Bars to confirm regime


class MarketRegimeDetector:
    """
    Market Regime Detection System.

    Combines multiple indicators to identify current market conditions
    and provide trading recommendations.
    """

    def __init__(self, config: RegimeConfig | None = None):
        """
        Initialize regime detector.

        Args:
            config: Configuration for thresholds
        """
        self.config = config or RegimeConfig()
        self._cache: dict[str, np.ndarray] = {}

        logger.debug(
            f"MarketRegimeDetector initialized: ADX threshold={self.config.adx_trending_threshold}"
        )

    def precompute_indicators(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> None:
        """
        Precompute all indicators for the entire dataset.

        Call this once before processing to avoid recalculating.

        Args:
            high: High prices array
            low: Low prices array
            close: Close prices array
        """
        logger.debug(f"Precomputing indicators for {len(close)} bars")

        # ADX with +DI/-DI
        adx, plus_di, minus_di = calculate_adx(high, low, close, self.config.adx_period)
        self._cache["adx"] = adx
        self._cache["plus_di"] = plus_di
        self._cache["minus_di"] = minus_di

        # ATR for volatility
        atr = calculate_atr(high, low, close, self.config.atr_period)
        self._cache["atr"] = atr

        # ATR as percentage of close
        with np.errstate(divide="ignore", invalid="ignore"):
            self._cache["atr_pct"] = np.where(close > 0, atr / close, 0)

        # Bollinger Bands
        bb_middle, bb_upper, bb_lower = calculate_bollinger_bands(
            close, self.config.bb_period, self.config.bb_std_dev
        )
        self._cache["bb_middle"] = bb_middle
        self._cache["bb_upper"] = bb_upper
        self._cache["bb_lower"] = bb_lower
        self._cache["bandwidth"] = calculate_bandwidth(bb_middle, bb_upper, bb_lower)

        # Trend EMA for additional confirmation
        self._cache["ema_20"] = calculate_ema(close, 20)
        self._cache["ema_50"] = calculate_ema(close, 50)

        logger.debug("Indicators precomputed successfully")

    def detect(
        self,
        high: np.ndarray | None = None,
        low: np.ndarray | None = None,
        close: np.ndarray | None = None,
        idx: int = -1,
    ) -> RegimeState:
        """
        Detect market regime at given index.

        If indicators aren't cached, will compute them.

        Args:
            high: High prices (optional if precomputed)
            low: Low prices (optional if precomputed)
            close: Close prices (optional if precomputed)
            idx: Bar index to detect (-1 for last)

        Returns:
            RegimeState with detected regime
        """
        # Precompute if not cached
        if "adx" not in self._cache and close is not None:
            self.precompute_indicators(high, low, close)

        if "adx" not in self._cache:
            return RegimeState(
                regime=RegimeType.UNKNOWN, confidence=0.0, reason="No data"
            )

        # Get indicator values at index
        adx = self._cache["adx"][idx]
        plus_di = self._cache["plus_di"][idx]
        minus_di = self._cache["minus_di"][idx]
        atr_pct = self._cache["atr_pct"][idx]
        bandwidth = self._cache["bandwidth"][idx]

        # Handle NaN values
        if np.isnan(adx) or np.isnan(plus_di) or np.isnan(minus_di):
            return RegimeState(
                regime=RegimeType.UNKNOWN,
                confidence=0.0,
                reason="Insufficient data for indicators",
            )

        # Detect regime using decision tree
        regime, confidence, reason = self._classify_regime(
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            atr_pct=atr_pct,
            bandwidth=bandwidth,
        )

        # Determine allowed directions and position sizing
        allow_long, allow_short = self._get_allowed_directions(
            regime, plus_di, minus_di
        )
        position_mult = self._get_position_multiplier(regime, adx, atr_pct)

        # Trend strength (normalized ADX to 0-1)
        trend_strength = min(adx / self.config.adx_strong_threshold, 1.0)

        return RegimeState(
            regime=regime,
            confidence=confidence,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            volatility=atr_pct,
            bandwidth=bandwidth,
            trend_strength=trend_strength,
            allow_long=allow_long,
            allow_short=allow_short,
            recommended_position_size=position_mult,
            reason=reason,
        )

    def _classify_regime(
        self,
        adx: float,
        plus_di: float,
        minus_di: float,
        atr_pct: float,
        bandwidth: float,
    ) -> tuple[RegimeType, float, str]:
        """
        Classify market regime based on indicator values.

        Returns:
            (regime_type, confidence, reason)
        """
        cfg = self.config

        # Check for extreme volatility first
        if atr_pct > cfg.volatility_extreme:
            return (
                RegimeType.VOLATILE,
                0.9,
                f"Extreme volatility: ATR={atr_pct * 100:.2f}%",
            )

        # Check ADX for trend strength
        has_strong_trend = adx >= cfg.adx_trending_threshold
        is_ranging = adx < cfg.adx_weak_threshold

        # Check for squeeze/breakout
        is_squeeze = bandwidth < cfg.bandwidth_squeeze
        is_wide = bandwidth > cfg.bandwidth_wide

        # Determine direction
        bullish = plus_di > minus_di
        bearish = minus_di > plus_di
        di_diff = abs(plus_di - minus_di)

        # Decision tree
        if has_strong_trend:
            if bullish:
                conf = min(0.5 + adx / 100 + di_diff / 100, 0.95)
                return (
                    RegimeType.TRENDING_UP,
                    conf,
                    f"Uptrend: ADX={adx:.1f}, +DI={plus_di:.1f}>{minus_di:.1f}",
                )
            elif bearish:
                conf = min(0.5 + adx / 100 + di_diff / 100, 0.95)
                return (
                    RegimeType.TRENDING_DOWN,
                    conf,
                    f"Downtrend: ADX={adx:.1f}, -DI={minus_di:.1f}>{plus_di:.1f}",
                )

        # Check for breakout from squeeze
        if is_squeeze and adx > cfg.adx_weak_threshold:
            if bullish:
                return (
                    RegimeType.BREAKOUT_UP,
                    0.7,
                    "Breakout UP: Squeeze with rising +DI",
                )
            elif bearish:
                return (
                    RegimeType.BREAKOUT_DOWN,
                    0.7,
                    "Breakout DOWN: Squeeze with rising -DI",
                )

        # High volatility without trend
        if is_wide or atr_pct > cfg.volatility_high:
            return (
                RegimeType.VOLATILE,
                0.6 + atr_pct * 10,
                f"Volatile: BW={bandwidth:.1f}%, ATR={atr_pct * 100:.2f}%",
            )

        # Low ADX + narrow bands = ranging
        if is_ranging:
            return (
                RegimeType.RANGING,
                0.6 + (cfg.adx_weak_threshold - adx) / 30,
                f"Ranging: ADX={adx:.1f} < {cfg.adx_weak_threshold}",
            )

        # Default: mild trend or transition
        if bullish:
            return (
                RegimeType.TRENDING_UP,
                0.5,
                f"Weak uptrend: ADX={adx:.1f}",
            )
        elif bearish:
            return (
                RegimeType.TRENDING_DOWN,
                0.5,
                f"Weak downtrend: ADX={adx:.1f}",
            )

        return (
            RegimeType.RANGING,
            0.4,
            f"Uncertain: ADX={adx:.1f}, DI±≈equal",
        )

    def _get_allowed_directions(
        self, regime: RegimeType, plus_di: float, minus_di: float
    ) -> tuple[bool, bool]:
        """
        Get allowed trade directions based on regime.

        Returns:
            (allow_long, allow_short)
        """
        if regime == RegimeType.TRENDING_UP or regime == RegimeType.BREAKOUT_UP:
            return True, False  # Long only
        elif regime == RegimeType.TRENDING_DOWN or regime == RegimeType.BREAKOUT_DOWN:
            return False, True  # Short only
        elif regime == RegimeType.VOLATILE:
            return False, False  # No trading in high volatility
        else:  # RANGING or UNKNOWN
            return True, True  # Both allowed (mean reversion)

    def _get_position_multiplier(
        self, regime: RegimeType, adx: float, atr_pct: float
    ) -> float:
        """
        Calculate position size multiplier based on regime.

        Returns:
            Position size multiplier (0.5-1.5)
        """
        cfg = self.config

        if regime in (RegimeType.TRENDING_UP, RegimeType.TRENDING_DOWN):
            # Larger positions in strong trends
            if adx >= cfg.adx_strong_threshold:
                return cfg.trending_size_mult
            else:
                return 1.0 + (adx - cfg.adx_trending_threshold) / 50

        elif regime == RegimeType.VOLATILE:
            # Much smaller in volatile markets
            return cfg.volatile_size_mult

        elif regime == RegimeType.RANGING:
            # Smaller in ranging markets
            return cfg.ranging_size_mult

        elif regime in (RegimeType.BREAKOUT_UP, RegimeType.BREAKOUT_DOWN):
            # Normal or slightly larger for breakouts
            return 1.0

        return 1.0

    def detect_all(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> list[RegimeState]:
        """
        Detect regime for all bars in the dataset.

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            List of RegimeState for each bar
        """
        self.precompute_indicators(high, low, close)

        regimes = []
        for i in range(len(close)):
            regimes.append(self.detect(idx=i))

        return regimes

    def get_regime_summary(self, regimes: list[RegimeState]) -> dict[str, float]:
        """
        Get summary statistics of regime distribution.

        Args:
            regimes: List of detected regimes

        Returns:
            Dictionary with regime percentages
        """
        if not regimes:
            return {}

        counts: dict[str, int] = {}
        for r in regimes:
            key = r.regime.value
            counts[key] = counts.get(key, 0) + 1

        total = len(regimes)
        return {k: v / total * 100 for k, v in counts.items()}

    def clear_cache(self) -> None:
        """Clear cached indicators."""
        self._cache.clear()


class AdaptiveStrategy:
    """
    Strategy adapter that adjusts behavior based on market regime.

    Wraps existing signals and filters them based on detected regime.
    """

    def __init__(
        self,
        regime_detector: MarketRegimeDetector | None = None,
        config: RegimeConfig | None = None,
    ):
        """
        Initialize adaptive strategy.

        Args:
            regime_detector: Detector instance (or creates new one)
            config: Configuration for regime detection
        """
        self.detector = regime_detector or MarketRegimeDetector(config)
        self.config = config or RegimeConfig()

    def filter_signals(
        self,
        signals: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> np.ndarray:
        """
        Filter signals based on market regime.

        Args:
            signals: Array of signals (1=long, -1=short, 0=none)
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            Filtered signals array
        """
        self.detector.precompute_indicators(high, low, close)

        filtered = signals.copy()

        for i in range(len(signals)):
            if signals[i] == 0:
                continue

            regime = self.detector.detect(idx=i)

            # Filter based on allowed directions
            if (signals[i] == 1 and not regime.allow_long) or (signals[i] == -1 and not regime.allow_short):
                filtered[i] = 0

        return filtered

    def adjust_position_sizes(
        self,
        sizes: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> np.ndarray:
        """
        Adjust position sizes based on market regime.

        Args:
            sizes: Original position sizes
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            Adjusted position sizes
        """
        self.detector.precompute_indicators(high, low, close)

        adjusted = sizes.copy()

        for i in range(len(sizes)):
            if sizes[i] == 0:
                continue

            regime = self.detector.detect(idx=i)
            adjusted[i] = sizes[i] * regime.recommended_position_size

        return adjusted
