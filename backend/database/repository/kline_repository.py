"""
Kline Repository - Specialized repository for OHLCV candlestick data.

Provides optimized methods for:
- Bulk UPSERT operations
- Time-series queries
- Data coverage analysis
- Gap detection

All methods include exception handling with proper logging.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database.exceptions import classify_sqlalchemy_error
from backend.models.bybit_kline_audit import BybitKlineAudit

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


# Interval to milliseconds mapping
INTERVAL_MS = {
    "1": 60_000,
    "3": 180_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "120": 7_200_000,
    "240": 14_400_000,
    "D": 86_400_000,
    "W": 604_800_000,
}


class KlineRepository(BaseRepository[BybitKlineAudit]):
    """
    Repository for Kline (candlestick) data operations.

    Optimized for:
    - High-throughput batch inserts (10k+ records)
    - Time-series queries with proper indexing
    - Data quality analysis (gaps, coverage)

    Usage:
        with UnitOfWork() as uow:
            repo = KlineRepository(uow.session)
            repo.bulk_upsert(candles)
    """

    def __init__(self, session: Session):
        super().__init__(session, BybitKlineAudit)

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def bulk_upsert(
        self,
        symbol: str,
        interval: str,
        candles: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk insert/update candles using UPSERT pattern.

        Uses INSERT ... ON CONFLICT DO UPDATE for efficient upserts.
        Returns number of affected rows.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Timeframe (e.g., '15', '60', 'D')
            candles: List of candle dicts with open_time, open, high, low, close, volume

        Raises:
            DatabaseError: If bulk upsert fails
        """
        if not candles:
            return 0

        try:
            # Prepare values for bulk insert
            values = []
            for c in candles:
                open_time = c.get("open_time", 0)
                # Convert seconds to milliseconds if needed
                if open_time < 1e12:
                    open_time = int(open_time * 1000)

                # Serialize raw data
                try:
                    raw_json = json.dumps(c, default=str)
                except Exception:
                    raw_json = str(c)

                values.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": open_time,
                        "open_time_dt": datetime.fromtimestamp(
                            open_time / 1000, tz=timezone.utc
                        ),
                        "open_price": float(c.get("open", 0)),
                        "high_price": float(c.get("high", 0)),
                        "low_price": float(c.get("low", 0)),
                        "close_price": float(c.get("close", 0)),
                        "volume": float(c.get("volume", 0)),
                        "turnover": float(c.get("turnover", 0)),
                        "raw": raw_json,
                    }
                )

            # SQLite UPSERT using ON CONFLICT
            stmt = sqlite_insert(BybitKlineAudit).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "interval", "open_time"],
                set_={
                    "open_price": stmt.excluded.open_price,
                    "high_price": stmt.excluded.high_price,
                    "low_price": stmt.excluded.low_price,
                    "close_price": stmt.excluded.close_price,
                    "volume": stmt.excluded.volume,
                    "turnover": stmt.excluded.turnover,
                    "raw": stmt.excluded.raw,
                },
            )

            result = self.session.execute(stmt)
            affected = result.rowcount if hasattr(result, "rowcount") else len(values)

            logger.debug(f"Bulk upsert: {symbol}:{interval} - {affected} rows")
            return affected

        except SQLAlchemyError as e:
            logger.error(f"Bulk upsert failed for {symbol}:{interval}: {e}")
            raise classify_sqlalchemy_error(e, "bulk_upsert", "BybitKlineAudit") from e

    def bulk_upsert_raw(
        self,
        candles: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk upsert candles that already contain symbol/interval.

        Args:
            candles: List of candle dicts with symbol, interval, open_time, OHLCV
        """
        if not candles:
            return 0

        # Group by symbol+interval for efficiency
        groups: Dict[str, List[Dict]] = {}
        for c in candles:
            key = f"{c.get('symbol')}:{c.get('interval')}"
            if key not in groups:
                groups[key] = []
            groups[key].append(c)

        total = 0
        for key, group in groups.items():
            symbol, interval = key.split(":", 1)
            total += self.bulk_upsert(symbol, interval, group)

        return total

    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        ascending: bool = False,
        market_type: Optional[str] = None,
    ) -> List[BybitKlineAudit]:
        """
        Get klines for a symbol/interval with optional time filters.

        Args:
            symbol: Trading pair
            interval: Timeframe
            limit: Maximum records to return
            start_time: Filter >= this timestamp (ms)
            end_time: Filter <= this timestamp (ms)
            ascending: If True, oldest first; if False, newest first
            market_type: Optional market type filter ('spot' or 'linear')

        Returns:
            List of BybitKlineAudit entities

        Raises:
            DatabaseError: If query fails
        """
        try:
            query = self.session.query(BybitKlineAudit).filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
            )

            # Filter by market_type if specified
            if market_type:
                query = query.filter(BybitKlineAudit.market_type == market_type)

            if start_time:
                query = query.filter(BybitKlineAudit.open_time >= start_time)
            if end_time:
                query = query.filter(BybitKlineAudit.open_time <= end_time)

            if ascending:
                query = query.order_by(BybitKlineAudit.open_time.asc())
            else:
                query = query.order_by(BybitKlineAudit.open_time.desc())

            return query.limit(limit).all()

        except SQLAlchemyError as e:
            logger.error(f"get_klines failed for {symbol}:{interval}: {e}")
            raise classify_sqlalchemy_error(e, "get_klines", "BybitKlineAudit") from e

    def get_klines_as_dicts(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get klines as dictionaries (for API responses).
        Results are ordered oldest-first for charting.
        """
        rows = self.get_klines(
            symbol, interval, limit, start_time, end_time, ascending=False
        )

        # Reverse to oldest-first for charting
        candles = []
        for r in reversed(rows):
            candles.append(
                {
                    "open_time": r.open_time,
                    "open": float(r.open_price),
                    "high": float(r.high_price),
                    "low": float(r.low_price),
                    "close": float(r.close_price),
                    "volume": float(r.volume) if r.volume else 0,
                    "turnover": float(r.turnover) if r.turnover else 0,
                }
            )

        return candles

    def get_latest(
        self,
        symbol: str,
        interval: str,
    ) -> Optional[BybitKlineAudit]:
        """Get the most recent candle for a symbol/interval."""
        return (
            self.session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
            )
            .order_by(BybitKlineAudit.open_time.desc())
            .first()
        )

    def get_oldest(
        self,
        symbol: str,
        interval: str,
    ) -> Optional[BybitKlineAudit]:
        """Get the oldest candle for a symbol/interval."""
        return (
            self.session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
            )
            .order_by(BybitKlineAudit.open_time.asc())
            .first()
        )

    # =========================================================================
    # COVERAGE & ANALYTICS
    # =========================================================================

    def get_coverage(
        self,
        symbol: str,
        interval: str,
    ) -> Dict[str, Any]:
        """
        Get data coverage statistics for a symbol/interval.

        Returns:
            Dict with count, oldest, newest, expected, completeness_pct

        Raises:
            DatabaseError: If query fails
        """
        try:
            result = (
                self.session.query(
                    func.count(BybitKlineAudit.id).label("count"),
                    func.min(BybitKlineAudit.open_time).label("oldest"),
                    func.max(BybitKlineAudit.open_time).label("newest"),
                )
                .filter(
                    BybitKlineAudit.symbol == symbol,
                    BybitKlineAudit.interval == interval,
                )
                .first()
            )

            if not result or result.count == 0:
                return {
                    "count": 0,
                    "oldest": None,
                    "newest": None,
                    "expected": 0,
                    "completeness_pct": 0.0,
                }

            # Calculate expected candle count
            interval_ms = INTERVAL_MS.get(interval, 60_000)
            expected = int((result.newest - result.oldest) / interval_ms) + 1
            completeness = (result.count / expected * 100) if expected > 0 else 100

            return {
                "count": result.count,
                "oldest": result.oldest,
                "newest": result.newest,
                "oldest_dt": datetime.fromtimestamp(
                    result.oldest / 1000, tz=timezone.utc
                ),
                "newest_dt": datetime.fromtimestamp(
                    result.newest / 1000, tz=timezone.utc
                ),
                "expected": expected,
                "completeness_pct": round(completeness, 2),
            }

        except SQLAlchemyError as e:
            logger.error(f"get_coverage failed for {symbol}:{interval}: {e}")
            raise classify_sqlalchemy_error(e, "get_coverage", "BybitKlineAudit") from e

    def get_all_symbols(self) -> List[str]:
        """Get list of all unique symbols in database."""
        try:
            result = self.session.query(BybitKlineAudit.symbol).distinct().all()
            return [r[0] for r in result]
        except SQLAlchemyError as e:
            logger.error(f"get_all_symbols failed: {e}")
            raise classify_sqlalchemy_error(
                e, "get_all_symbols", "BybitKlineAudit"
            ) from e

    def get_intervals_for_symbol(self, symbol: str) -> List[str]:
        """Get list of intervals available for a symbol."""
        try:
            result = (
                self.session.query(BybitKlineAudit.interval)
                .filter(BybitKlineAudit.symbol == symbol)
                .distinct()
                .all()
            )
            return [r[0] for r in result]
        except SQLAlchemyError as e:
            logger.error(f"get_intervals_for_symbol failed for {symbol}: {e}")
            raise classify_sqlalchemy_error(
                e, "get_intervals_for_symbol", "BybitKlineAudit"
            ) from e

    # =========================================================================
    # GAP DETECTION
    # =========================================================================

    def find_gaps(
        self,
        symbol: str,
        interval: str,
        max_gaps: int = 50,
        skip_weekends: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Find timestamp gaps in data using window functions.

        Args:
            symbol: Trading pair
            interval: Timeframe
            max_gaps: Maximum number of gaps to return
            skip_weekends: If True, filter out weekend gaps

        Returns:
            List of gap dicts with gap_start, gap_end, missing_candles

        Raises:
            DatabaseError: If query fails
        """
        try:
            interval_ms = INTERVAL_MS.get(interval, 60_000)
            gap_threshold = int(interval_ms * 1.5)

            query = text("""
                WITH ordered AS (
                    SELECT
                        open_time,
                        LEAD(open_time) OVER (ORDER BY open_time) as next_time
                    FROM bybit_kline_audit
                    WHERE symbol = :symbol AND interval = :interval
                )
                SELECT
                    open_time as gap_start,
                    next_time as gap_end,
                    (next_time - open_time) as gap_ms,
                    CAST((next_time - open_time) / :interval_ms AS INTEGER) - 1 as missing_candles
                FROM ordered
                WHERE next_time IS NOT NULL
                  AND (next_time - open_time) > :threshold
                ORDER BY gap_ms DESC
                LIMIT :max_gaps
            """)

            result = self.session.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "interval_ms": interval_ms,
                    "threshold": gap_threshold,
                    "max_gaps": max_gaps,
                },
            )

            gaps = []
            for row in result:
                row_dict = dict(row._mapping)

                # Add datetime versions for readability
                row_dict["gap_start_dt"] = datetime.fromtimestamp(
                    row_dict["gap_start"] / 1000, tz=timezone.utc
                )
                row_dict["gap_end_dt"] = datetime.fromtimestamp(
                    row_dict["gap_end"] / 1000, tz=timezone.utc
                )

                # Check if weekend gap
                start_weekday = row_dict["gap_start_dt"].weekday()
                is_weekend = start_weekday >= 4  # Friday, Saturday, Sunday
                row_dict["is_weekend"] = is_weekend

                if skip_weekends and is_weekend:
                    continue

                gaps.append(row_dict)

            return gaps

        except SQLAlchemyError as e:
            logger.error(f"find_gaps failed for {symbol}:{interval}: {e}")
            raise classify_sqlalchemy_error(e, "find_gaps", "BybitKlineAudit") from e

    # =========================================================================
    # MAINTENANCE OPERATIONS
    # =========================================================================

    def delete_before(
        self,
        symbol: str,
        interval: str,
        cutoff_time: int,
    ) -> int:
        """
        Delete candles older than cutoff time.

        Args:
            symbol: Trading pair
            interval: Timeframe
            cutoff_time: Timestamp in ms - delete records before this

        Returns:
            Number of deleted records
        """
        result = (
            self.session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.open_time < cutoff_time,
            )
            .delete(synchronize_session=False)
        )

        logger.info(f"Deleted {result} old candles for {symbol}:{interval}")
        return result

    def delete_all_before(self, cutoff_time: int) -> int:
        """
        Delete all candles older than cutoff time (regardless of symbol).

        Args:
            cutoff_time: Timestamp in ms

        Returns:
            Number of deleted records
        """
        result = (
            self.session.query(BybitKlineAudit)
            .filter(BybitKlineAudit.open_time < cutoff_time)
            .delete(synchronize_session=False)
        )

        logger.info(f"Deleted {result} old candles (all symbols)")
        return result

    @staticmethod
    def interval_to_ms(interval: str) -> int:
        """Convert interval string to milliseconds."""
        return INTERVAL_MS.get(str(interval).upper(), 60_000)
