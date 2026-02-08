"""
Universal Filter Engine - Фильтрация сигналов по ВСЕМ условиям.

Поддерживаемые фильтры:
- MTF HTF Filter: SMA/EMA на старшем таймфрейме
- BTC Correlation Filter: Направление BTC для альткоинов
- Volatility Filter: ATR percentile
- Volume Filter: Volume percentile
- Trend Filter: SMA direction
- Momentum Filter: RSI zones
- Market Regime Filter: Hurst exponent
- Time Filter: Sessions, days, hours

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger

try:
    from numba import njit

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# =============================================================================
# NUMBA-ACCELERATED FILTER FUNCTIONS
# =============================================================================


@njit(cache=True)
def calculate_sma_filter(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate SMA for filtering."""
    n = len(data)
    sma = np.zeros(n, dtype=np.float64)
    if n < period:
        return sma
    cumsum = 0.0
    for i in range(period):
        cumsum += data[i]
    sma[period - 1] = cumsum / period
    for i in range(period, n):
        cumsum = cumsum - data[i - period] + data[i]
        sma[i] = cumsum / period
    for i in range(period - 1):
        sma[i] = sma[period - 1]
    return sma


@njit(cache=True)
def calculate_ema_filter(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate EMA for filtering."""
    n = len(data)
    ema = np.zeros(n, dtype=np.float64)
    if n == 0:
        return ema
    multiplier = 2.0 / (period + 1)
    if n < period:
        ema[:] = np.mean(data)
        return ema
    ema[period - 1] = np.mean(data[:period])
    for i in range(period, n):
        ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
    for i in range(period - 1):
        ema[i] = ema[period - 1]
    return ema


@njit(cache=True)
def calculate_atr_filter(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> np.ndarray:
    """Calculate ATR for volatility filtering."""
    n = len(close)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    if n < 2:
        return atr
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)
    if n < period:
        return tr
    atr_sum = 0.0
    for i in range(period):
        atr_sum += tr[i]
    atr[period - 1] = atr_sum / period
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    for i in range(period - 1):
        atr[i] = atr[period - 1]
    return atr


@njit(cache=True)
def calculate_rsi_filter(close: np.ndarray, period: int) -> np.ndarray:
    """Calculate RSI for momentum filtering."""
    n = len(close)
    rsi = np.full(n, 50.0, dtype=np.float64)
    if n < period + 1:
        return rsi
    deltas = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        deltas[i] = close[i] - close[i - 1]
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
def calculate_percentile_rank(data: np.ndarray, lookback: int) -> np.ndarray:
    """
    Calculate rolling percentile rank of current value.
    Returns 0-100 where 100 means current value is highest in lookback.
    """
    n = len(data)
    rank = np.zeros(n, dtype=np.float64)
    for i in range(lookback - 1, n):
        current = data[i]
        count_below = 0
        for j in range(i - lookback + 1, i + 1):
            if data[j] < current:
                count_below += 1
        rank[i] = (count_below / lookback) * 100.0
    return rank


@njit(cache=True)
def calculate_hurst_exponent(close: np.ndarray, lookback: int) -> np.ndarray:
    """
    Calculate rolling Hurst exponent for market regime detection.
    H > 0.5: Trending (persistent)
    H < 0.5: Mean-reverting (anti-persistent)
    H = 0.5: Random walk
    """
    n = len(close)
    hurst = np.full(n, 0.5, dtype=np.float64)

    if n < lookback + 10:
        return hurst

    for i in range(lookback - 1, n):
        # Get returns
        window = close[i - lookback + 1 : i + 1]
        returns = np.zeros(lookback - 1, dtype=np.float64)
        for j in range(lookback - 1):
            if window[j] > 0:
                returns[j] = np.log(window[j + 1] / window[j])

        # R/S analysis (simplified)
        mean_ret = np.mean(returns)
        dev = returns - mean_ret
        cumdev = np.cumsum(dev)
        R = np.max(cumdev) - np.min(cumdev)
        S = np.std(returns)

        if S > 0 and R > 0:
            # Simplified Hurst estimation
            rs = R / S
            # log(R/S) / log(n) approximation
            if rs > 0 and lookback > 1:
                hurst[i] = np.log(rs) / np.log(lookback)
                # Clamp to reasonable range
                if hurst[i] < 0:
                    hurst[i] = 0.0
                elif hurst[i] > 1:
                    hurst[i] = 1.0
        else:
            hurst[i] = 0.5

    return hurst


@njit(cache=True)
def apply_htf_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    htf_close: np.ndarray,
    htf_ma: np.ndarray,
    index_map: np.ndarray,
    neutral_zone_pct: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply HTF trend filter to signals.

    Args:
        long_entries: Original long entry signals
        short_entries: Original short entry signals
        htf_close: HTF close prices
        htf_ma: HTF moving average
        index_map: LTF index -> HTF index mapping
        neutral_zone_pct: Neutral zone % around MA (0 = strict mode)

    Returns:
        Filtered (long_entries, short_entries)
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        htf_idx = index_map[i]
        if htf_idx < 0 or htf_idx >= len(htf_close):
            continue

        htf_price = htf_close[htf_idx]
        htf_ma_val = htf_ma[htf_idx]

        # Calculate neutral zone
        neutral_upper = htf_ma_val * (1 + neutral_zone_pct)
        neutral_lower = htf_ma_val * (1 - neutral_zone_pct)

        # Filter long: HTF price above MA (or in neutral zone)
        if long_entries[i]:
            if htf_price > neutral_lower:
                filtered_long[i] = True

        # Filter short: HTF price below MA (or in neutral zone)
        if short_entries[i]:
            if htf_price < neutral_upper:
                filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_btc_correlation_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    btc_close: np.ndarray,
    btc_ma: np.ndarray,
    index_map: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply BTC correlation filter for altcoins.
    Long only when BTC is bullish, Short only when BTC is bearish.
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        btc_idx = index_map[i]
        if btc_idx < 0 or btc_idx >= len(btc_close):
            continue

        btc_bullish = btc_close[btc_idx] > btc_ma[btc_idx]

        if long_entries[i] and btc_bullish:
            filtered_long[i] = True
        if short_entries[i] and not btc_bullish:
            filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_volatility_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    atr_percentile: np.ndarray,
    min_percentile: float,
    max_percentile: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply volatility filter: trade only within ATR percentile range.
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        vol_ok = min_percentile <= atr_percentile[i] <= max_percentile
        if long_entries[i] and vol_ok:
            filtered_long[i] = True
        if short_entries[i] and vol_ok:
            filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_volume_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    volume_percentile: np.ndarray,
    min_percentile: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply volume filter: trade only when volume is above min percentile.
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        vol_ok = volume_percentile[i] >= min_percentile
        if long_entries[i] and vol_ok:
            filtered_long[i] = True
        if short_entries[i] and vol_ok:
            filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_trend_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    close: np.ndarray,
    trend_ma: np.ndarray,
    mode: int,  # 0 = with trend, 1 = against trend
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply trend filter.
    Mode 0 (with trend): Long when price > MA, Short when price < MA
    Mode 1 (against trend): Long when price < MA, Short when price > MA
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        above_ma = close[i] > trend_ma[i]

        if mode == 0:  # With trend
            if long_entries[i] and above_ma:
                filtered_long[i] = True
            if short_entries[i] and not above_ma:
                filtered_short[i] = True
        else:  # Against trend
            if long_entries[i] and not above_ma:
                filtered_long[i] = True
            if short_entries[i] and above_ma:
                filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_momentum_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    rsi: np.ndarray,
    oversold: float,
    overbought: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply momentum filter: avoid trading in extreme RSI zones.
    Long: not in overbought zone
    Short: not in oversold zone
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        if long_entries[i] and rsi[i] < overbought:
            filtered_long[i] = True
        if short_entries[i] and rsi[i] > oversold:
            filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_market_regime_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    hurst: np.ndarray,
    regime_filter: int,  # 0=all, 1=trending, 2=ranging, 3=volatile, 4=not_volatile
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply market regime filter based on Hurst exponent.

    Regimes:
    - Trending: Hurst > 0.55
    - Ranging: Hurst < 0.45
    - Volatile: Hurst > 0.6 (strong trend)
    - Not Volatile: Hurst < 0.6
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        h = hurst[i]

        allow = False
        if regime_filter == 0:  # All
            allow = True
        elif regime_filter == 1:  # Trending
            allow = h > 0.55
        elif regime_filter == 2:  # Ranging
            allow = h < 0.45
        elif regime_filter == 3:  # Volatile
            allow = h > 0.6
        elif regime_filter == 4:  # Not volatile
            allow = h < 0.6

        if long_entries[i] and allow:
            filtered_long[i] = True
        if short_entries[i] and allow:
            filtered_short[i] = True

    return filtered_long, filtered_short


@njit(cache=True)
def apply_time_filter(
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    hours: np.ndarray,
    weekdays: np.ndarray,
    session_start: int,
    session_end: int,
    no_trade_days: np.ndarray,
    no_trade_hours: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply time-based filter.

    Args:
        hours: Hour of day (0-23) for each bar
        weekdays: Day of week (0=Mon, 6=Sun) for each bar
        session_start: Trading session start hour
        session_end: Trading session end hour
        no_trade_days: Days to exclude (e.g., [5, 6] for weekend)
        no_trade_hours: Hours to exclude
    """
    n = len(long_entries)
    filtered_long = np.zeros(n, dtype=np.bool_)
    filtered_short = np.zeros(n, dtype=np.bool_)

    for i in range(n):
        hour = hours[i]
        weekday = weekdays[i]

        # Check session hours
        if hour < session_start or hour >= session_end:
            continue

        # Check no-trade days
        skip_day = False
        for d in no_trade_days:
            if weekday == d:
                skip_day = True
                break
        if skip_day:
            continue

        # Check no-trade hours
        skip_hour = False
        for h in no_trade_hours:
            if hour == h:
                skip_hour = True
                break
        if skip_hour:
            continue

        # Allow trade
        if long_entries[i]:
            filtered_long[i] = True
        if short_entries[i]:
            filtered_short[i] = True

    return filtered_long, filtered_short


# =============================================================================
# MAIN FILTER ENGINE CLASS
# =============================================================================


@dataclass
class FilterConfig:
    """Configuration for all filters."""

    # MTF HTF Filter
    mtf_enabled: bool = False
    mtf_htf_candles: pd.DataFrame | None = None
    mtf_htf_index_map: np.ndarray | None = None
    mtf_filter_type: str = "sma"  # "sma" or "ema"
    mtf_filter_period: int = 200
    mtf_neutral_zone_pct: float = 0.0

    # BTC Correlation Filter
    btc_filter_enabled: bool = False
    btc_candles: pd.DataFrame | None = None
    btc_index_map: np.ndarray | None = None
    btc_filter_period: int = 50

    # Volatility Filter
    volatility_filter_enabled: bool = False
    min_volatility_percentile: float = 10.0
    max_volatility_percentile: float = 90.0
    volatility_lookback: int = 100

    # Volume Filter
    volume_filter_enabled: bool = False
    min_volume_percentile: float = 20.0
    volume_lookback: int = 50

    # Trend Filter
    trend_filter_enabled: bool = False
    trend_filter_period: int = 200
    trend_filter_mode: str = "with"  # "with" or "against"

    # Momentum Filter
    momentum_filter_enabled: bool = False
    momentum_oversold: float = 30.0
    momentum_overbought: float = 70.0
    momentum_period: int = 14

    # Market Regime Filter
    market_regime_enabled: bool = False
    market_regime_filter: str = (
        "not_volatile"  # "all", "trending", "ranging", "volatile", "not_volatile"
    )
    market_regime_lookback: int = 50

    # Time Filter
    time_filter_enabled: bool = False
    session_start_hour: int = 0
    session_end_hour: int = 24
    no_trade_days: tuple[int, ...] = ()
    no_trade_hours: tuple[int, ...] = ()


@dataclass
class FilterOutput:
    """Output from filter engine."""

    long_entries: np.ndarray
    short_entries: np.ndarray
    filters_applied: list[str] = field(default_factory=list)
    filter_stats: dict[str, dict] = field(default_factory=dict)


class UniversalFilterEngine:
    """
    Universal filter engine for signal filtering.

    Applies multiple filters in sequence:
    1. MTF HTF Filter
    2. BTC Correlation Filter
    3. Volatility Filter
    4. Volume Filter
    5. Trend Filter
    6. Momentum Filter
    7. Market Regime Filter
    8. Time Filter
    """

    REGIME_MAP = {
        "all": 0,
        "trending": 1,
        "ranging": 2,
        "volatile": 3,
        "not_volatile": 4,
    }

    def __init__(self, use_numba: bool = True):
        self.use_numba = use_numba and NUMBA_AVAILABLE
        if self.use_numba:
            logger.debug("UniversalFilterEngine: Numba acceleration enabled")

    def apply_filters(
        self,
        candles: pd.DataFrame,
        long_entries: np.ndarray,
        short_entries: np.ndarray,
        config: FilterConfig,
    ) -> FilterOutput:
        """
        Apply all enabled filters to signals.

        Args:
            candles: OHLCV DataFrame
            long_entries: Original long entry signals
            short_entries: Original short entry signals
            config: Filter configuration

        Returns:
            FilterOutput with filtered signals and stats
        """
        filters_applied = []
        filter_stats = {}

        # Count original signals
        orig_long = np.sum(long_entries)
        orig_short = np.sum(short_entries)

        # Work with copies
        filtered_long = long_entries.copy()
        filtered_short = short_entries.copy()

        # Extract OHLCV
        close = candles["close"].values.astype(np.float64)
        high = candles["high"].values.astype(np.float64) if "high" in candles else close
        low = candles["low"].values.astype(np.float64) if "low" in candles else close
        volume = (
            candles["volume"].values.astype(np.float64)
            if "volume" in candles
            else np.ones_like(close)
        )

        # 1. MTF HTF Filter
        if (
            config.mtf_enabled
            and config.mtf_htf_candles is not None
            and config.mtf_htf_index_map is not None
        ):
            htf_close = config.mtf_htf_candles["close"].values.astype(np.float64)
            if config.mtf_filter_type == "ema":
                htf_ma = calculate_ema_filter(htf_close, config.mtf_filter_period)
            else:
                htf_ma = calculate_sma_filter(htf_close, config.mtf_filter_period)

            filtered_long, filtered_short = apply_htf_filter(
                filtered_long,
                filtered_short,
                htf_close,
                htf_ma,
                config.mtf_htf_index_map,
                config.mtf_neutral_zone_pct,
            )
            filters_applied.append("mtf_htf")
            filter_stats["mtf_htf"] = {
                "htf_period": config.mtf_filter_period,
                "filter_type": config.mtf_filter_type,
            }

        # 2. BTC Correlation Filter
        if (
            config.btc_filter_enabled
            and config.btc_candles is not None
            and config.btc_index_map is not None
        ):
            btc_close = config.btc_candles["close"].values.astype(np.float64)
            btc_ma = calculate_sma_filter(btc_close, config.btc_filter_period)

            filtered_long, filtered_short = apply_btc_correlation_filter(
                filtered_long, filtered_short, btc_close, btc_ma, config.btc_index_map
            )
            filters_applied.append("btc_correlation")
            filter_stats["btc_correlation"] = {"period": config.btc_filter_period}

        # 3. Volatility Filter
        if config.volatility_filter_enabled:
            atr = calculate_atr_filter(high, low, close, 14)
            atr_percentile = calculate_percentile_rank(atr, config.volatility_lookback)

            filtered_long, filtered_short = apply_volatility_filter(
                filtered_long,
                filtered_short,
                atr_percentile,
                config.min_volatility_percentile,
                config.max_volatility_percentile,
            )
            filters_applied.append("volatility")
            filter_stats["volatility"] = {
                "min_pct": config.min_volatility_percentile,
                "max_pct": config.max_volatility_percentile,
            }

        # 4. Volume Filter
        if config.volume_filter_enabled:
            volume_percentile = calculate_percentile_rank(
                volume, config.volume_lookback
            )

            filtered_long, filtered_short = apply_volume_filter(
                filtered_long,
                filtered_short,
                volume_percentile,
                config.min_volume_percentile,
            )
            filters_applied.append("volume")
            filter_stats["volume"] = {"min_pct": config.min_volume_percentile}

        # 5. Trend Filter
        if config.trend_filter_enabled:
            trend_ma = calculate_sma_filter(close, config.trend_filter_period)
            mode = 0 if config.trend_filter_mode == "with" else 1

            filtered_long, filtered_short = apply_trend_filter(
                filtered_long, filtered_short, close, trend_ma, mode
            )
            filters_applied.append("trend")
            filter_stats["trend"] = {
                "period": config.trend_filter_period,
                "mode": config.trend_filter_mode,
            }

        # 6. Momentum Filter
        if config.momentum_filter_enabled:
            rsi = calculate_rsi_filter(close, config.momentum_period)

            filtered_long, filtered_short = apply_momentum_filter(
                filtered_long,
                filtered_short,
                rsi,
                config.momentum_oversold,
                config.momentum_overbought,
            )
            filters_applied.append("momentum")
            filter_stats["momentum"] = {
                "period": config.momentum_period,
                "oversold": config.momentum_oversold,
                "overbought": config.momentum_overbought,
            }

        # 7. Market Regime Filter
        if config.market_regime_enabled:
            hurst = calculate_hurst_exponent(close, config.market_regime_lookback)
            regime_int = self.REGIME_MAP.get(config.market_regime_filter, 0)

            filtered_long, filtered_short = apply_market_regime_filter(
                filtered_long, filtered_short, hurst, regime_int
            )
            filters_applied.append("market_regime")
            filter_stats["market_regime"] = {
                "filter": config.market_regime_filter,
                "lookback": config.market_regime_lookback,
            }

        # 8. Time Filter
        if config.time_filter_enabled and hasattr(candles.index, "hour"):
            try:
                hours = candles.index.hour.values.astype(np.int64)
                weekdays = candles.index.weekday.values.astype(np.int64)
                no_trade_days = np.array(config.no_trade_days, dtype=np.int64)
                no_trade_hours = np.array(config.no_trade_hours, dtype=np.int64)

                filtered_long, filtered_short = apply_time_filter(
                    filtered_long,
                    filtered_short,
                    hours,
                    weekdays,
                    config.session_start_hour,
                    config.session_end_hour,
                    no_trade_days,
                    no_trade_hours,
                )
                filters_applied.append("time")
                filter_stats["time"] = {
                    "session_start": config.session_start_hour,
                    "session_end": config.session_end_hour,
                    "no_trade_days": config.no_trade_days,
                    "no_trade_hours": config.no_trade_hours,
                }
            except Exception as e:
                logger.warning(f"Time filter failed: {e}")

        # Calculate filter effectiveness
        final_long = np.sum(filtered_long)
        final_short = np.sum(filtered_short)
        filter_stats["summary"] = {
            "original_long": int(orig_long),
            "original_short": int(orig_short),
            "filtered_long": int(final_long),
            "filtered_short": int(final_short),
            "long_removed_pct": round((1 - final_long / max(orig_long, 1)) * 100, 1),
            "short_removed_pct": round((1 - final_short / max(orig_short, 1)) * 100, 1),
        }

        return FilterOutput(
            long_entries=filtered_long,
            short_entries=filtered_short,
            filters_applied=filters_applied,
            filter_stats=filter_stats,
        )

    @staticmethod
    def from_backtest_input(input_data) -> FilterConfig:
        """
        Create FilterConfig from BacktestInput.

        Args:
            input_data: BacktestInput instance

        Returns:
            FilterConfig populated from input_data
        """
        return FilterConfig(
            # MTF
            mtf_enabled=getattr(input_data, "mtf_enabled", False),
            mtf_htf_candles=getattr(input_data, "mtf_htf_candles", None),
            mtf_htf_index_map=getattr(input_data, "mtf_htf_index_map", None),
            mtf_filter_type=getattr(input_data, "mtf_filter_type", "sma"),
            mtf_filter_period=getattr(input_data, "mtf_filter_period", 200),
            mtf_neutral_zone_pct=getattr(input_data, "mtf_neutral_zone_pct", 0.0),
            # BTC
            btc_filter_enabled=getattr(input_data, "mtf_btc_filter_enabled", False),
            btc_candles=getattr(input_data, "mtf_btc_candles", None),
            btc_index_map=getattr(input_data, "mtf_btc_index_map", None),
            btc_filter_period=getattr(input_data, "mtf_btc_filter_period", 50),
            # Volatility
            volatility_filter_enabled=getattr(
                input_data, "volatility_filter_enabled", False
            ),
            min_volatility_percentile=getattr(
                input_data, "min_volatility_percentile", 10.0
            ),
            max_volatility_percentile=getattr(
                input_data, "max_volatility_percentile", 90.0
            ),
            volatility_lookback=getattr(input_data, "volatility_lookback", 100),
            # Volume
            volume_filter_enabled=getattr(input_data, "volume_filter_enabled", False),
            min_volume_percentile=getattr(input_data, "min_volume_percentile", 20.0),
            volume_lookback=getattr(input_data, "volume_lookback", 50),
            # Trend
            trend_filter_enabled=getattr(input_data, "trend_filter_enabled", False),
            trend_filter_period=getattr(input_data, "trend_filter_period", 200),
            trend_filter_mode=getattr(input_data, "trend_filter_mode", "with"),
            # Momentum
            momentum_filter_enabled=getattr(
                input_data, "momentum_filter_enabled", False
            ),
            momentum_oversold=getattr(input_data, "momentum_oversold", 30.0),
            momentum_overbought=getattr(input_data, "momentum_overbought", 70.0),
            momentum_period=getattr(input_data, "momentum_period", 14),
            # Market Regime
            market_regime_enabled=getattr(input_data, "market_regime_enabled", False),
            market_regime_filter=getattr(
                input_data, "market_regime_filter", "not_volatile"
            ),
            market_regime_lookback=getattr(input_data, "market_regime_lookback", 50),
            # Time
            time_filter_enabled=getattr(input_data, "exit_on_session_close", False)
            or len(getattr(input_data, "no_trade_days", ())) > 0,
            session_start_hour=getattr(input_data, "session_start_hour", 0),
            session_end_hour=getattr(input_data, "session_end_hour", 24),
            no_trade_days=getattr(input_data, "no_trade_days", ()),
            no_trade_hours=getattr(input_data, "no_trade_hours", ()),
        )
