"""
MTF (Multi-Timeframe) Manager
Handles fetching and aligning multi-timeframe candle data.
"""

import logging
from dataclasses import dataclass

from backend.services.candle_cache import CANDLE_CACHE

logger = logging.getLogger(__name__)


@dataclass
class MtfResponse:
    """Multi-timeframe response data structure"""

    symbol: str
    intervals: list[str]
    data: dict[str, list[dict]]


class MtfManager:
    """
    Multi-Timeframe Manager

    Provides functionality to:
    - Fetch working sets for multiple intervals
    - Align data across different timeframes
    - Resample from base interval to higher timeframes
    """

    def __init__(self):
        """Initialize MTF Manager"""
        logger.info("MTF Manager initialized")

    def get_working_sets(
        self, symbol: str, intervals: list[str], load_limit: int = 1000
    ) -> MtfResponse:
        """
        Get working sets for multiple intervals (raw, unaligned).

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            intervals: List of interval strings (e.g., ['1', '15', '60'])
            load_limit: Maximum number of candles to load per interval

        Returns:
            MtfResponse with symbol, intervals, and data dict
        """
        logger.debug(f"Fetching working sets for {symbol}, intervals: {intervals}")

        data = {}
        for interval in intervals:
            try:
                # Get working set for this interval
                candles = CANDLE_CACHE.get_working_set(
                    symbol, interval, ensure_loaded=False
                )
                if not candles:
                    candles = CANDLE_CACHE.load_initial(
                        symbol, interval, load_limit=load_limit, persist=True
                    )
                data[interval] = candles or []
            except Exception as exc:
                logger.warning(
                    f"Failed to fetch interval {interval} for {symbol}: {exc}"
                )
                data[interval] = []

        return MtfResponse(symbol=symbol, intervals=intervals, data=data)

    def get_aligned(
        self,
        symbol: str,
        intervals: list[str],
        base_interval: str | None = None,
        load_limit: int = 1000,
    ) -> MtfResponse:
        """
        Get aligned multi-timeframe data resampled from base interval.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            intervals: List of interval strings (e.g., ['1', '15', '60'])
            base_interval: Base interval to resample from (defaults to smallest)
            load_limit: Maximum number of candles to load

        Returns:
            MtfResponse with symbol, intervals, and aligned data dict
        """
        if not intervals:
            logger.warning(f"No intervals provided for {symbol}")
            return MtfResponse(symbol=symbol, intervals=[], data={})

        # Determine base interval (smallest if not specified)
        if not base_interval:
            base_interval = self._get_smallest_interval(intervals)

        logger.debug(
            f"Aligning data for {symbol}, base: {base_interval}, intervals: {intervals}"
        )

        # Load base interval data
        try:
            base_data = CANDLE_CACHE.get_working_set(
                symbol, base_interval, ensure_loaded=False
            )
            if not base_data:
                base_data = CANDLE_CACHE.load_initial(
                    symbol, base_interval, load_limit=load_limit, persist=True
                )
        except Exception as exc:
            logger.error(f"Failed to load base interval {base_interval}: {exc}")
            base_data = []

        # Resample to other intervals
        data = {base_interval: base_data or []}
        for interval in intervals:
            if interval == base_interval:
                continue
            try:
                resampled = self._resample_candles(base_data, base_interval, interval)
                data[interval] = resampled
            except Exception as exc:
                logger.warning(f"Failed to resample to {interval}: {exc}")
                data[interval] = []

        return MtfResponse(symbol=symbol, intervals=intervals, data=data)

    def _get_smallest_interval(self, intervals: list[str]) -> str:
        """
        Determine the smallest interval from a list.

        Args:
            intervals: List of interval strings

        Returns:
            Smallest interval string
        """
        # Simple heuristic: convert to minutes and find min
        interval_minutes = {}
        for itv in intervals:
            minutes = self._interval_to_minutes(itv)
            if minutes is not None:
                interval_minutes[itv] = minutes

        if not interval_minutes:
            return intervals[0]

        return min(interval_minutes, key=interval_minutes.get)

    def _interval_to_minutes(self, interval: str) -> int | None:
        """
        Convert interval string to minutes.

        Args:
            interval: Interval string (e.g., '1', '15', '60', 'D', 'W')

        Returns:
            Number of minutes, or None if unable to parse
        """
        try:
            # Handle numeric intervals (assume minutes)
            if interval.isdigit():
                return int(interval)

            # Handle special intervals
            interval_map = {
                "D": 1440,  # 1 day = 1440 minutes
                "W": 10080,  # 1 week = 10080 minutes
                "M": 43200,  # 1 month ≈ 30 days
            }
            return interval_map.get(interval.upper())
        except Exception:
            return None

    def _resample_candles(
        self, base_candles: list[dict], base_interval: str, target_interval: str
    ) -> list[dict]:
        """
        Resample base candles to target interval.

        Args:
            base_candles: List of base candles
            base_interval: Base interval string
            target_interval: Target interval to resample to

        Returns:
            List of resampled candles
        """
        if not base_candles:
            return []

        base_minutes = self._interval_to_minutes(base_interval)
        target_minutes = self._interval_to_minutes(target_interval)

        if not base_minutes or not target_minutes:
            logger.warning(
                f"Unable to resample from {base_interval} to {target_interval}"
            )
            return []

        if target_minutes <= base_minutes:
            # Can't downsample, return base candles
            return base_candles

        # Calculate aggregation factor
        factor = target_minutes // base_minutes
        if factor < 1:
            factor = 1

        # Aggregate candles
        resampled = []
        for i in range(0, len(base_candles), factor):
            chunk = base_candles[i : i + factor]
            if not chunk:
                continue

            aggregated = {
                "time": chunk[0].get("time", 0),
                "open": chunk[0].get("open", 0.0),
                "high": max(c.get("high", 0.0) for c in chunk),
                "low": min(c.get("low", 0.0) for c in chunk if c.get("low", 0) > 0),
                "close": chunk[-1].get("close", 0.0),
                "volume": sum(c.get("volume", 0.0) for c in chunk),
            }
            resampled.append(aggregated)

        logger.debug(
            f"Resampled {len(base_candles)} candles from {base_interval} "
            f"to {len(resampled)} candles at {target_interval}"
        )

        return resampled


# Singleton instance
MTF_MANAGER = MtfManager()
