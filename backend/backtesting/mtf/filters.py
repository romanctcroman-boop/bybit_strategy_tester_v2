"""
рџЋЇ HTF Filters Module

Provides filters based on Higher Timeframe (HTF) data to control
which signals are allowed in the backtesting.

Filter Types:
- HTFTrendFilter: EMA/SMA-based trend direction filter
- BTCCorrelationFilter: BTC sentiment-based filter for altcoins

Example Usage:
    # Create trend filter (200 SMA)
    trend_filter = HTFTrendFilter(period=200, filter_type="sma")

    # Check if signal is allowed
    allow_long, allow_short = trend_filter.check(htf_close, htf_indicator)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import numpy as np

from backend.core.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_sma,
)

logger = logging.getLogger(__name__)


class FilterType(Enum):
    """HTF filter types."""

    SMA = "sma"
    EMA = "ema"
    SUPERTREND = "supertrend"
    ICHIMOKU = "ichimoku"
    MACD = "macd"
    BOLLINGER = "bollinger"
    ADX = "adx"


@dataclass
class FilterResult:
    """Result of HTF filter check."""

    allow_long: bool
    allow_short: bool
    htf_value: float = 0.0
    indicator_value: float = 0.0
    reason: str = ""


class HTFFilter(ABC):
    """
    Abstract base class for HTF filters.

    All HTF filters must implement the check() method which determines
    whether long/short signals are allowed based on HTF context.
    """

    @abstractmethod
    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check if long/short signals are allowed.

        Args:
            htf_close: HTF close price
            htf_indicator: HTF indicator value (e.g., EMA, SMA)
            **kwargs: Additional parameters

        Returns:
            Tuple of (allow_long, allow_short)
        """
        pass

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """
        Check with detailed result.

        Args:
            htf_close: HTF close price
            htf_indicator: HTF indicator value

        Returns:
            FilterResult with details
        """
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=htf_indicator,
        )


class HTFTrendFilter(HTFFilter):
    """
    HTF Trend Filter based on EMA or SMA.

    Logic (Dav1zoN Scalp style):
    - HTF close ABOVE indicator в†’ Allow LONG only
    - HTF close BELOW indicator в†’ Allow SHORT only
    - Can be configured to allow both in neutral zone

    Example:
        # SuperTrend 5m with 15m SMA200 filter
        filter = HTFTrendFilter(period=200, filter_type="sma")

        # On each LTF bar:
        htf_close = htf_candles.iloc[htf_idx]['close']
        htf_sma = htf_indicators['sma200'][htf_idx]
        allow_long, allow_short = filter.check(htf_close, htf_sma)
    """

    def __init__(
        self,
        period: int = 200,
        filter_type: str = "sma",
        neutral_zone_pct: float = 0.0,
        strict_mode: bool = True,
    ):
        """
        Initialize HTF Trend Filter.

        Args:
            period: Indicator period (e.g., 200 for SMA200)
            filter_type: "sma" or "ema"
            neutral_zone_pct: Percentage around indicator where both are allowed
            strict_mode: If True, only allow signals aligned with trend
        """
        self.period = period
        self.filter_type = FilterType(filter_type.lower())
        self.neutral_zone_pct = neutral_zone_pct
        self.strict_mode = strict_mode

        logger.debug(
            f"HTFTrendFilter initialized: period={period}, type={filter_type}, neutral_zone={neutral_zone_pct}%"
        )

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check trend alignment.

        Args:
            htf_close: HTF close price
            htf_indicator: HTF indicator value (SMA/EMA)

        Returns:
            (allow_long, allow_short)
        """
        if htf_indicator <= 0:
            # No valid indicator - allow both or none based on strict_mode
            return not self.strict_mode, not self.strict_mode

        # Calculate distance from indicator
        distance_pct = (htf_close - htf_indicator) / htf_indicator * 100

        # Check neutral zone
        if abs(distance_pct) <= self.neutral_zone_pct:
            # In neutral zone - allow both
            return True, True

        # Above indicator - bullish trend
        if htf_close > htf_indicator:
            return True, False  # Allow LONG only

        # Below indicator - bearish trend
        if htf_close < htf_indicator:
            return False, True  # Allow SHORT only

        return True, True  # Exactly equal - allow both

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator)

        if htf_indicator > 0:
            distance_pct = (htf_close - htf_indicator) / htf_indicator * 100
            if distance_pct > self.neutral_zone_pct:
                reason = f"BULLISH: Close {distance_pct:.2f}% above {self.filter_type.value.upper()}{self.period}"
            elif distance_pct < -self.neutral_zone_pct:
                reason = f"BEARISH: Close {abs(distance_pct):.2f}% below {self.filter_type.value.upper()}{self.period}"
            else:
                reason = f"NEUTRAL: Close within {self.neutral_zone_pct}% of indicator"
        else:
            reason = "No valid indicator"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=htf_indicator,
            reason=reason,
        )


class BTCCorrelationFilter(HTFFilter):
    """
    BTC Correlation Filter for Altcoin Trading.

    Logic:
    - Only trade alts in the direction BTC is trending
    - BTC above its SMA в†’ allow LONG on alts
    - BTC below its SMA в†’ allow SHORT on alts

    This filter helps avoid trading against the overall market sentiment.

    Example:
        # Trade ETHUSDT only when BTC confirms direction
        filter = BTCCorrelationFilter(btc_sma_period=50)

        btc_close = btc_candles.iloc[btc_idx]['close']
        btc_sma = btc_indicators['sma50'][btc_idx]
        allow_long, allow_short = filter.check(btc_close, btc_sma)
    """

    def __init__(
        self,
        btc_sma_period: int = 50,
        min_distance_pct: float = 0.0,
        correlation_threshold: float = 0.5,
    ):
        """
        Initialize BTC Correlation Filter.

        Args:
            btc_sma_period: SMA period for BTC (e.g., 50 for D50)
            min_distance_pct: Minimum distance from SMA to confirm trend
            correlation_threshold: Minimum correlation coefficient (not used in basic mode)
        """
        self.btc_sma_period = btc_sma_period
        self.min_distance_pct = min_distance_pct
        self.correlation_threshold = correlation_threshold

        logger.debug(f"BTCCorrelationFilter initialized: sma_period={btc_sma_period}, min_distance={min_distance_pct}%")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check BTC sentiment.

        Args:
            htf_close: BTC close price
            htf_indicator: BTC SMA value

        Returns:
            (allow_long, allow_short) for altcoin trading
        """
        # Validate inputs - if invalid, allow both directions
        if htf_indicator <= 0 or htf_close <= 0:
            return True, True  # No valid data - allow both

        # Calculate distance from SMA
        distance_pct = (htf_close - htf_indicator) / htf_indicator * 100

        # Check minimum distance requirement
        if abs(distance_pct) < self.min_distance_pct:
            return True, True  # Too close to call - allow both

        # BTC bullish - allow LONG on alts
        if htf_close > htf_indicator:
            return True, False

        # BTC bearish - allow SHORT on alts
        if htf_close < htf_indicator:
            return False, True

        return True, True

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator)

        if htf_indicator > 0:
            distance_pct = (htf_close - htf_indicator) / htf_indicator * 100
            if distance_pct >= self.min_distance_pct:
                reason = f"BTC BULLISH: {distance_pct:.2f}% above SMA{self.btc_sma_period}"
            elif distance_pct <= -self.min_distance_pct:
                reason = f"BTC BEARISH: {abs(distance_pct):.2f}% below SMA{self.btc_sma_period}"
            else:
                reason = f"BTC NEUTRAL: within {self.min_distance_pct}% of SMA"
        else:
            reason = "No valid BTC indicator"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=htf_indicator,
            reason=reason,
        )


def calculate_htf_indicator(htf_close: np.ndarray, period: int, filter_type: str = "sma") -> np.ndarray:
    """
    Calculate HTF indicator for filtering.
    Uses unified indicators library.

    Args:
        htf_close: HTF close prices
        period: Indicator period
        filter_type: "sma" or "ema"

    Returns:
        Indicator array
    """
    if filter_type.lower() == "ema":
        return calculate_ema(htf_close, period)
    else:
        return calculate_sma(htf_close, period)


# =============================================================================
# Additional HTF Filters: SuperTrend, Ichimoku, MACD
# =============================================================================


def calculate_supertrend(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate SuperTrend indicator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
        multiplier: ATR multiplier

    Returns:
        (supertrend values, trend direction: 1=bullish, -1=bearish)
    """
    n = len(close)
    atr = calculate_atr(high, low, close, period)

    # HL2 (average of high and low)
    hl2 = (high + low) / 2

    # Basic upper and lower bands
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    # Final bands and trend
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = np.ones(n)  # 1 = bullish, -1 = bearish

    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]

    for i in range(1, n):
        # Final upper band
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final lower band
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Trend direction
        if trend[i - 1] == 1:  # Was bullish
            if close[i] < final_lower[i]:
                trend[i] = -1
                supertrend[i] = final_upper[i]
            else:
                trend[i] = 1
                supertrend[i] = final_lower[i]
        else:  # Was bearish
            if close[i] > final_upper[i]:
                trend[i] = 1
                supertrend[i] = final_lower[i]
            else:
                trend[i] = -1
                supertrend[i] = final_upper[i]

    return supertrend, trend


class SuperTrendFilter(HTFFilter):
    """
    SuperTrend HTF Filter (Dav1zoN Scalp style).

    Logic:
    - SuperTrend bullish (price above ST line) в†’ Allow LONG only
    - SuperTrend bearish (price below ST line) в†’ Allow SHORT only

    Example:
        filter = SuperTrendFilter(period=10, multiplier=3.0)
        # Pass trend direction from calculate_supertrend()
        allow_long, allow_short = filter.check(close, st_value, trend=trend_dir)
    """

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        """
        Initialize SuperTrend filter.

        Args:
            period: ATR period
            multiplier: ATR multiplier for bands
        """
        self.period = period
        self.multiplier = multiplier
        logger.debug(f"SuperTrendFilter initialized: period={period}, mult={multiplier}")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check SuperTrend trend direction.

        Args:
            htf_close: HTF close price
            htf_indicator: SuperTrend value (not used directly, use trend)
            **kwargs: Must include 'trend' (1=bullish, -1=bearish)

        Returns:
            (allow_long, allow_short)
        """
        trend = kwargs.get("trend", 0)

        if trend == 0:
            return True, True  # No valid trend - allow both

        if trend > 0:  # Bullish
            return True, False
        else:  # Bearish
            return False, True

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        trend = kwargs.get("trend", 0)

        if trend > 0:
            reason = f"SuperTrend BULLISH (period={self.period}, mult={self.multiplier})"
        elif trend < 0:
            reason = f"SuperTrend BEARISH (period={self.period}, mult={self.multiplier})"
        else:
            reason = "SuperTrend NEUTRAL"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=htf_indicator,
            reason=reason,
        )


def calculate_ichimoku(
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> dict:
    """
    Calculate Ichimoku Cloud components.

    Args:
        high: High prices
        low: Low prices
        tenkan_period: Tenkan-sen period (default 9)
        kijun_period: Kijun-sen period (default 26)
        senkou_b_period: Senkou Span B period (default 52)
        displacement: Cloud displacement (default 26)

    Returns:
        Dict with tenkan, kijun, senkou_a, senkou_b arrays
    """
    n = len(high)

    def donchian_mid(h, low_arr, period):
        """Calculate Donchian channel midpoint."""
        result = np.full(n, np.nan)
        for i in range(period - 1, n):
            result[i] = (np.max(h[i - period + 1 : i + 1]) + np.min(low_arr[i - period + 1 : i + 1])) / 2
        return result

    tenkan = donchian_mid(high, low, tenkan_period)
    kijun = donchian_mid(high, low, kijun_period)

    # Senkou Span A = (Tenkan + Kijun) / 2, displaced forward
    senkou_a = np.full(n, np.nan)
    for i in range(n - displacement):
        if not np.isnan(tenkan[i]) and not np.isnan(kijun[i]):
            senkou_a[i + displacement] = (tenkan[i] + kijun[i]) / 2

    # Senkou Span B = Donchian(52) midpoint, displaced forward
    senkou_b_raw = donchian_mid(high, low, senkou_b_period)
    senkou_b = np.full(n, np.nan)
    for i in range(n - displacement):
        if not np.isnan(senkou_b_raw[i]):
            senkou_b[i + displacement] = senkou_b_raw[i]

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b,
    }


class IchimokuFilter(HTFFilter):
    """
    Ichimoku Cloud HTF Filter.

    Logic:
    - Price above cloud (senkou_a & senkou_b) в†’ Allow LONG only
    - Price below cloud в†’ Allow SHORT only
    - Price inside cloud в†’ NEUTRAL (configurable)

    Example:
        filter = IchimokuFilter()
        # Pass cloud values
        allow_long, allow_short = filter.check(close, 0, senkou_a=sa, senkou_b=sb)
    """

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        allow_in_cloud: bool = True,
    ):
        """
        Initialize Ichimoku filter.

        Args:
            tenkan_period: Tenkan-sen period
            kijun_period: Kijun-sen period
            senkou_b_period: Senkou Span B period
            allow_in_cloud: If True, allow both directions when price in cloud
        """
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.allow_in_cloud = allow_in_cloud
        logger.debug(f"IchimokuFilter initialized: T={tenkan_period}, K={kijun_period}")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check Ichimoku cloud position.

        Args:
            htf_close: HTF close price
            htf_indicator: Not used (pass 0)
            **kwargs: Must include 'senkou_a' and 'senkou_b'

        Returns:
            (allow_long, allow_short)
        """
        senkou_a = kwargs.get("senkou_a", np.nan)
        senkou_b = kwargs.get("senkou_b", np.nan)

        if np.isnan(senkou_a) or np.isnan(senkou_b):
            return True, True  # No valid cloud - allow both

        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)

        if htf_close > cloud_top:
            return True, False  # Above cloud - LONG only
        elif htf_close < cloud_bottom:
            return False, True  # Below cloud - SHORT only
        else:
            # Inside cloud
            return self.allow_in_cloud, self.allow_in_cloud

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        senkou_a = kwargs.get("senkou_a", np.nan)
        senkou_b = kwargs.get("senkou_b", np.nan)

        if np.isnan(senkou_a) or np.isnan(senkou_b):
            reason = "Ichimoku: No valid cloud data"
        else:
            cloud_top = max(senkou_a, senkou_b)
            cloud_bottom = min(senkou_a, senkou_b)

            if htf_close > cloud_top:
                reason = f"Ichimoku BULLISH: Price {htf_close:.2f} above cloud ({cloud_top:.2f})"
            elif htf_close < cloud_bottom:
                reason = f"Ichimoku BEARISH: Price {htf_close:.2f} below cloud ({cloud_bottom:.2f})"
            else:
                reason = f"Ichimoku NEUTRAL: Price {htf_close:.2f} inside cloud"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=senkou_a if not np.isnan(senkou_a) else 0,
            reason=reason,
        )


def calculate_macd(
    close: np.ndarray,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate MACD indicator.

    Args:
        close: Close prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line period

    Returns:
        (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(close, fast_period)
    slow_ema = calculate_ema(close, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


class MACDFilter(HTFFilter):
    """
    MACD HTF Filter.

    Logic:
    - MACD above signal line в†’ Allow LONG only
    - MACD below signal line в†’ Allow SHORT only
    - Optional: Consider histogram direction

    Example:
        filter = MACDFilter()
        # Pass MACD values
        allow_long, allow_short = filter.check(0, 0, macd=macd_val, signal=signal_val)
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        use_histogram: bool = False,
    ):
        """
        Initialize MACD filter.

        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            use_histogram: If True, also consider histogram direction
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.use_histogram = use_histogram
        logger.debug(f"MACDFilter initialized: {fast_period}/{slow_period}/{signal_period}")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check MACD trend direction.

        Args:
            htf_close: Not used (pass 0)
            htf_indicator: Not used (pass 0)
            **kwargs: Must include 'macd' and 'signal', optionally 'histogram'

        Returns:
            (allow_long, allow_short)
        """
        macd = kwargs.get("macd", np.nan)
        signal = kwargs.get("signal", np.nan)
        histogram = kwargs.get("histogram", 0)

        if np.isnan(macd) or np.isnan(signal):
            return True, True  # No valid MACD - allow both

        # Basic check: MACD vs Signal
        bullish = macd > signal
        bearish = macd < signal

        # Optional: Consider histogram trend
        if self.use_histogram and histogram != 0:
            # Histogram growing = trend strengthening
            if bullish and histogram > 0:
                return True, False
            elif bearish and histogram < 0:
                return False, True
            else:
                # Divergence - allow both
                return True, True

        if bullish:
            return True, False
        elif bearish:
            return False, True
        else:
            return True, True  # MACD = Signal - neutral

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        macd = kwargs.get("macd", np.nan)
        signal = kwargs.get("signal", np.nan)
        histogram = kwargs.get("histogram", 0)

        if np.isnan(macd) or np.isnan(signal):
            reason = "MACD: No valid data"
        else:
            diff = macd - signal
            if diff > 0:
                reason = f"MACD BULLISH: MACD ({macd:.4f}) above Signal ({signal:.4f})"
            elif diff < 0:
                reason = f"MACD BEARISH: MACD ({macd:.4f}) below Signal ({signal:.4f})"
            else:
                reason = "MACD NEUTRAL: At signal line"

            if self.use_histogram:
                reason += f" | Histogram: {histogram:.4f}"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=macd if not np.isnan(macd) else 0,
            indicator_value=signal if not np.isnan(signal) else 0,
            reason=reason,
        )


# =============================================================================
# Bollinger Bands and ADX Filters
# =============================================================================


def calculate_bollinger_bands(
    close: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands.

    Args:
        close: Close prices
        period: SMA period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)

    Returns:
        (middle_band, upper_band, lower_band)
    """
    n = len(close)
    middle = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)

    if n < period:
        return middle, upper, lower

    # Calculate SMA as middle band
    middle = calculate_sma(close, period)

    # Calculate standard deviation
    for i in range(period - 1, n):
        window = close[i - period + 1 : i + 1]
        std = np.std(window, ddof=0)  # Population std dev
        upper[i] = middle[i] + std_dev * std
        lower[i] = middle[i] - std_dev * std

    return middle, upper, lower


def calculate_bandwidth(middle: np.ndarray, upper: np.ndarray, lower: np.ndarray) -> np.ndarray:
    """
    Calculate Bollinger Bandwidth (volatility indicator).

    Bandwidth = (Upper - Lower) / Middle * 100

    High bandwidth = high volatility
    Low bandwidth = low volatility (squeeze)
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        bandwidth = np.where(middle > 0, (upper - lower) / middle * 100, np.nan)
    return bandwidth


def calculate_percent_b(close: np.ndarray, upper: np.ndarray, lower: np.ndarray) -> np.ndarray:
    """
    Calculate %B indicator.

    %B = (Close - Lower) / (Upper - Lower)

    %B > 1: Above upper band
    %B < 0: Below lower band
    %B = 0.5: At middle band
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        band_width = upper - lower
        percent_b = np.where(band_width > 0, (close - lower) / band_width, np.nan)
    return percent_b


class BollingerFilter(HTFFilter):
    """
    Bollinger Bands HTF Filter.

    Logic:
    - Price touches/crosses lower band в†’ Allow LONG (mean reversion)
    - Price touches/crosses upper band в†’ Allow SHORT (mean reversion)
    - Price in middle zone в†’ Allow both or use momentum mode

    Modes:
    - "mean_reversion": Trade bounces off bands
    - "breakout": Trade breakouts through bands
    - "squeeze": Trade only during low volatility squeeze

    Example:
        filter = BollingerFilter(period=20, std_dev=2.0, mode="mean_reversion")
        allow_long, allow_short = filter.check(close, 0, upper=ub, lower=lb, middle=mb)
    """

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        mode: str = "mean_reversion",
        bandwidth_threshold: float = 4.0,  # For squeeze detection
    ):
        """
        Initialize Bollinger filter.

        Args:
            period: SMA period
            std_dev: Standard deviation multiplier
            mode: "mean_reversion", "breakout", or "squeeze"
            bandwidth_threshold: Bandwidth below this = squeeze
        """
        self.period = period
        self.std_dev = std_dev
        self.mode = mode.lower()
        self.bandwidth_threshold = bandwidth_threshold
        logger.debug(f"BollingerFilter initialized: period={period}, std={std_dev}, mode={mode}")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check Bollinger Bands position.

        Args:
            htf_close: HTF close price
            htf_indicator: Not used (pass 0)
            **kwargs: Must include 'upper', 'lower', 'middle'
                     Optional: 'bandwidth', 'percent_b'

        Returns:
            (allow_long, allow_short)
        """
        upper = kwargs.get("upper", np.nan)
        lower = kwargs.get("lower", np.nan)
        middle = kwargs.get("middle", np.nan)
        bandwidth = kwargs.get("bandwidth", np.nan)

        if np.isnan(upper) or np.isnan(lower) or np.isnan(middle):
            return True, True  # No valid bands - allow both

        if self.mode == "mean_reversion":
            # Price at or below lower band в†’ potential LONG (bounce up)
            if htf_close <= lower:
                return True, False
            # Price at or above upper band в†’ potential SHORT (bounce down)
            elif htf_close >= upper:
                return False, True
            else:
                # In the bands - allow both
                return True, True

        elif self.mode == "breakout":
            # Opposite of mean reversion: trade breakouts
            # Price breaks above upper в†’ momentum LONG
            if htf_close > upper:
                return True, False
            # Price breaks below lower в†’ momentum SHORT
            elif htf_close < lower:
                return False, True
            else:
                # No breakout - no signals
                return False, False

        elif self.mode == "squeeze":
            # Only trade during low volatility squeeze
            if not np.isnan(bandwidth) and bandwidth < self.bandwidth_threshold:
                # Squeeze detected - trade based on position
                if htf_close > middle:
                    return True, False  # Above middle - expect upward breakout
                else:
                    return False, True  # Below middle - expect downward breakout
            else:
                # No squeeze - no signals
                return False, False

        return True, True

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        upper = kwargs.get("upper", np.nan)
        lower = kwargs.get("lower", np.nan)
        middle = kwargs.get("middle", np.nan)
        bandwidth = kwargs.get("bandwidth", np.nan)

        if np.isnan(upper) or np.isnan(lower):
            reason = "Bollinger: No valid band data"
        else:
            percent_b = (htf_close - lower) / (upper - lower) * 100 if upper != lower else 50

            if self.mode == "mean_reversion":
                if htf_close <= lower:
                    reason = f"BB Mean Reversion: Price at lower band, %B={percent_b:.1f}%"
                elif htf_close >= upper:
                    reason = f"BB Mean Reversion: Price at upper band, %B={percent_b:.1f}%"
                else:
                    reason = f"BB Neutral: Price in bands, %B={percent_b:.1f}%"
            elif self.mode == "breakout":
                if htf_close > upper:
                    reason = "BB Breakout UP: Price above upper band"
                elif htf_close < lower:
                    reason = "BB Breakout DOWN: Price below lower band"
                else:
                    reason = "BB No Breakout: Price inside bands"
            else:  # squeeze
                if not np.isnan(bandwidth) and bandwidth < self.bandwidth_threshold:
                    reason = f"BB Squeeze: Bandwidth={bandwidth:.2f}% < threshold"
                else:
                    reason = f"BB No Squeeze: Bandwidth={bandwidth:.2f}%"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=htf_close,
            indicator_value=middle if not np.isnan(middle) else 0,
            reason=reason,
        )


def calculate_adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate ADX (Average Directional Index) with +DI and -DI.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ADX period (default 14)

    Returns:
        (adx, plus_di, minus_di)
    """
    n = len(close)
    adx = np.full(n, np.nan)
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)

    if n < period + 1:
        return adx, plus_di, minus_di

    # Calculate True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    # Calculate +DM and -DM
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smoothed averages using Wilder's method
    atr = np.zeros(n)
    smoothed_plus_dm = np.zeros(n)
    smoothed_minus_dm = np.zeros(n)

    # Initial values (sum of first period)
    atr[period] = np.sum(tr[1 : period + 1])
    smoothed_plus_dm[period] = np.sum(plus_dm[1 : period + 1])
    smoothed_minus_dm[period] = np.sum(minus_dm[1 : period + 1])

    # Wilder smoothing
    for i in range(period + 1, n):
        atr[i] = atr[i - 1] - (atr[i - 1] / period) + tr[i]
        smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] - (smoothed_plus_dm[i - 1] / period) + plus_dm[i]
        smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] - (smoothed_minus_dm[i - 1] / period) + minus_dm[i]

    # Calculate +DI and -DI
    for i in range(period, n):
        if atr[i] > 0:
            plus_di[i] = (smoothed_plus_dm[i] / atr[i]) * 100
            minus_di[i] = (smoothed_minus_dm[i] / atr[i]) * 100

    # Calculate DX
    dx = np.zeros(n)
    for i in range(period, n):
        if not np.isnan(plus_di[i]) and not np.isnan(minus_di[i]):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = abs(plus_di[i] - minus_di[i]) / di_sum * 100

    # Calculate ADX (smoothed DX)
    adx[2 * period - 1] = np.mean(dx[period : 2 * period])
    for i in range(2 * period, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return adx, plus_di, minus_di


class ADXFilter(HTFFilter):
    """
    ADX (Average Directional Index) HTF Filter.

    Logic:
    - ADX > threshold в†’ Strong trend, trade with +DI/-DI direction
    - ADX < threshold в†’ Weak/ranging market
    - +DI > -DI в†’ Bullish trend (allow LONG)
    - -DI > +DI в†’ Bearish trend (allow SHORT)

    Modes:
    - "trend_only": Only allow trades when ADX > threshold
    - "direction": Use +DI/-DI for direction, ignore ADX level
    - "combined": Both strong trend AND correct direction

    Example:
        filter = ADXFilter(period=14, threshold=25, mode="combined")
        allow_long, allow_short = filter.check(0, 0, adx=adx_val, plus_di=pdi, minus_di=mdi)
    """

    def __init__(
        self,
        period: int = 14,
        threshold: float = 25.0,
        strong_threshold: float = 50.0,
        mode: str = "combined",
    ):
        """
        Initialize ADX filter.

        Args:
            period: ADX period
            threshold: Minimum ADX for trend confirmation (default 25)
            strong_threshold: ADX level for very strong trend (default 50)
            mode: "trend_only", "direction", or "combined"
        """
        self.period = period
        self.threshold = threshold
        self.strong_threshold = strong_threshold
        self.mode = mode.lower()
        logger.debug(f"ADXFilter initialized: period={period}, threshold={threshold}, mode={mode}")

    def check(self, htf_close: float, htf_indicator: float, **kwargs) -> tuple[bool, bool]:
        """
        Check ADX trend strength and direction.

        Args:
            htf_close: Not used (pass 0)
            htf_indicator: Not used (pass 0)
            **kwargs: Must include 'adx', 'plus_di', 'minus_di'

        Returns:
            (allow_long, allow_short)
        """
        adx = kwargs.get("adx", np.nan)
        plus_di = kwargs.get("plus_di", np.nan)
        minus_di = kwargs.get("minus_di", np.nan)

        if np.isnan(adx) or np.isnan(plus_di) or np.isnan(minus_di):
            return True, True  # No valid ADX - allow both

        # Determine trend direction from DI
        bullish_trend = plus_di > minus_di
        bearish_trend = minus_di > plus_di

        # Strong trend?
        strong_trend = adx >= self.threshold

        if self.mode == "trend_only":
            # Only care about trend strength, not direction
            if strong_trend:
                return True, True
            else:
                return False, False  # No trading in ranging market

        elif self.mode == "direction":
            # Only care about direction, ignore ADX level
            if bullish_trend:
                return True, False
            elif bearish_trend:
                return False, True
            else:
                return True, True

        elif self.mode == "combined":
            # Both strong trend AND direction must align
            if not strong_trend:
                return False, False  # No trading in weak trend

            if bullish_trend:
                return True, False
            elif bearish_trend:
                return False, True
            else:
                return False, False

        return True, True

    def check_detailed(self, htf_close: float, htf_indicator: float, **kwargs) -> FilterResult:
        """Check with detailed result."""
        allow_long, allow_short = self.check(htf_close, htf_indicator, **kwargs)
        adx = kwargs.get("adx", np.nan)
        plus_di = kwargs.get("plus_di", np.nan)
        minus_di = kwargs.get("minus_di", np.nan)

        if np.isnan(adx) or np.isnan(plus_di) or np.isnan(minus_di):
            reason = "ADX: No valid data"
        else:
            trend_strength = (
                "STRONG" if adx >= self.strong_threshold else "MODERATE" if adx >= self.threshold else "WEAK"
            )
            direction = "BULLISH" if plus_di > minus_di else "BEARISH"

            reason = f"ADX {trend_strength} ({adx:.1f}): {direction} (+DI={plus_di:.1f}, -DI={minus_di:.1f})"

        return FilterResult(
            allow_long=allow_long,
            allow_short=allow_short,
            htf_value=adx if not np.isnan(adx) else 0,
            indicator_value=plus_di if not np.isnan(plus_di) else 0,
            reason=reason,
        )
