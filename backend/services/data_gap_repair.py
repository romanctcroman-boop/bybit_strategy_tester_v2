"""
Data Gap Repair Service - Automatically detect and fill price gaps.

This service:
1. Scans database for timestamp gaps and price gaps
2. Fetches missing candles from Bybit API
3. Inserts/updates data in the database
4. Can run as a scheduled task or on-demand

Weekend gaps (Saturday-Sunday) are typically not data errors but market closures,
so they can be optionally skipped.
"""

import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data.sqlite3"

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


@dataclass
class GapInfo:
    """Information about a detected gap."""

    symbol: str
    interval: str
    gap_start: int  # timestamp ms of last candle before gap
    gap_end: int  # timestamp ms of first candle after gap
    gap_start_dt: datetime
    gap_end_dt: datetime
    missing_candles: int
    is_weekend: bool = False


class DataGapRepairService:
    """Service to detect and repair data gaps in kline database."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DB_PATH)
        self._adapter = None

    def _get_adapter(self):
        """Get Bybit adapter for API calls."""
        if self._adapter is None:
            from backend.services.adapters.bybit import BybitAdapter

            self._adapter = BybitAdapter()
        return self._adapter

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_timestamp_gaps(
        self,
        symbol: str,
        interval: str,
        max_gaps: int = 100,
        skip_weekends: bool = True,
    ) -> list[GapInfo]:
        """
        Find timestamp gaps in the database.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1", "5", "60")
            max_gaps: Maximum number of gaps to return
            skip_weekends: Skip gaps that start on Friday/Saturday (weekend gaps)

        Returns:
            List of GapInfo objects
        """
        conn = self._get_connection()
        interval_ms = INTERVAL_MS.get(interval, 60_000)

        # Get consecutive candles and find gaps
        query = """
        WITH ordered_candles AS (
            SELECT
                open_time,
                open_time_dt,
                LEAD(open_time) OVER (ORDER BY open_time) as next_open_time,
                LEAD(open_time_dt) OVER (ORDER BY open_time) as next_open_time_dt
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ?
            ORDER BY open_time
        )
        SELECT
            open_time,
            open_time_dt,
            next_open_time,
            next_open_time_dt,
            (next_open_time - open_time) as gap_ms
        FROM ordered_candles
        WHERE next_open_time IS NOT NULL
          AND (next_open_time - open_time) > ? * 1.5
        ORDER BY gap_ms DESC
        LIMIT ?
        """

        cursor = conn.execute(query, (symbol, interval, interval_ms, max_gaps))
        rows = cursor.fetchall()
        conn.close()

        gaps = []
        for row in rows:
            gap_start = row["open_time"]
            gap_end = row["next_open_time"]
            gap_ms = row["gap_ms"]
            missing_candles = int(gap_ms / interval_ms) - 1

            # Parse datetime to check for weekend
            gap_start_dt = datetime.fromisoformat(
                row["open_time_dt"].replace("+00:00", "")
            ).replace(tzinfo=timezone.utc)
            gap_end_dt = datetime.fromisoformat(
                row["next_open_time_dt"].replace("+00:00", "")
            ).replace(tzinfo=timezone.utc)

            # Check if this is a weekend gap (Friday 21:00 UTC to Sunday 21:00 UTC typical)
            is_weekend = gap_start_dt.weekday() >= 4 and gap_end_dt.weekday() <= 1

            if skip_weekends and is_weekend:
                continue

            gaps.append(
                GapInfo(
                    symbol=symbol,
                    interval=interval,
                    gap_start=gap_start,
                    gap_end=gap_end,
                    gap_start_dt=gap_start_dt,
                    gap_end_dt=gap_end_dt,
                    missing_candles=missing_candles,
                    is_weekend=is_weekend,
                )
            )

        return gaps

    def find_price_gaps(
        self,
        symbol: str,
        interval: str,
        threshold_pct: float = 1.0,
        max_gaps: int = 100,
    ) -> list[dict]:
        """
        Find price gaps (close → open) in the database.

        Args:
            symbol: Trading symbol
            interval: Timeframe
            threshold_pct: Minimum gap percentage to report
            max_gaps: Maximum gaps to return

        Returns:
            List of price gap records
        """
        conn = self._get_connection()

        query = """
        WITH ordered_candles AS (
            SELECT
                open_time,
                open_time_dt,
                open_price,
                close_price,
                LAG(open_time) OVER (ORDER BY open_time) as prev_open_time,
                LAG(close_price) OVER (ORDER BY open_time) as prev_close
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ?
        )
        SELECT
            open_time,
            open_time_dt,
            open_price,
            close_price,
            prev_open_time,
            prev_close,
            CASE
                WHEN prev_close > 0 THEN
                    ABS(open_price - prev_close) / prev_close * 100
                ELSE 0
            END as gap_pct
        FROM ordered_candles
        WHERE prev_close IS NOT NULL
          AND prev_close > 0
          AND ABS(open_price - prev_close) / prev_close * 100 > ?
        ORDER BY gap_pct DESC
        LIMIT ?
        """

        cursor = conn.execute(query, (symbol, interval, threshold_pct, max_gaps))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "open_time": row["open_time"],
                "datetime": row["open_time_dt"],
                "prev_close": row["prev_close"],
                "current_open": row["open_price"],
                "gap_pct": round(row["gap_pct"], 4),
                "prev_open_time": row["prev_open_time"],
            }
            for row in rows
        ]

    def fetch_candles_for_range(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[dict]:
        """
        Fetch candles from Bybit API for a specific time range.

        Args:
            symbol: Trading symbol
            interval: Timeframe
            start_time: Start timestamp in ms
            end_time: End timestamp in ms

        Returns:
            List of candle dicts
        """
        adapter = self._get_adapter()
        interval_ms = INTERVAL_MS.get(interval, 60_000)
        expected_candles = int((end_time - start_time) / interval_ms)

        logger.info(
            f"Fetching {expected_candles} candles for {symbol}:{interval} "
            f"from {datetime.fromtimestamp(start_time / 1000, tz=timezone.utc)} "
            f"to {datetime.fromtimestamp(end_time / 1000, tz=timezone.utc)}"
        )

        # Bybit API limits to 1000 candles per request
        all_candles = []
        current_end = end_time

        while current_end > start_time:
            try:
                candles = adapter.get_klines_before(
                    symbol=symbol,
                    interval=interval,
                    end_time=current_end,
                    limit=min(1000, expected_candles),
                )

                if not candles:
                    break

                # Filter candles within range
                candles = [c for c in candles if c["open_time"] >= start_time]
                all_candles.extend(candles)

                if candles:
                    oldest_time = min(c["open_time"] for c in candles)
                    current_end = oldest_time
                else:
                    break

            except Exception as e:
                logger.error(f"API fetch failed: {e}")
                break

        # Remove duplicates and sort
        seen = set()
        unique_candles = []
        for c in all_candles:
            if c["open_time"] not in seen:
                seen.add(c["open_time"])
                unique_candles.append(c)

        unique_candles.sort(key=lambda x: x["open_time"])
        return unique_candles

    def repair_gap(self, gap: GapInfo) -> dict:
        """
        Repair a single timestamp gap by fetching and inserting missing candles.

        Args:
            gap: GapInfo object describing the gap

        Returns:
            Result dict with status and details
        """
        logger.info(
            f"Repairing gap: {gap.symbol}:{gap.interval} "
            f"from {gap.gap_start_dt} to {gap.gap_end_dt} "
            f"(~{gap.missing_candles} candles)"
        )

        # Fetch candles from API
        interval_ms = INTERVAL_MS.get(gap.interval, 60_000)
        fetch_start = gap.gap_start + interval_ms  # Start after the last known candle
        fetch_end = gap.gap_end  # End at the first known candle after gap

        candles = self.fetch_candles_for_range(
            symbol=gap.symbol,
            interval=gap.interval,
            start_time=fetch_start,
            end_time=fetch_end,
        )

        if not candles:
            return {
                "status": "no_data",
                "gap": gap,
                "message": "No candles returned from API",
            }

        # Insert candles into database
        inserted = self._insert_candles(gap.symbol, gap.interval, candles)

        return {
            "status": "repaired",
            "gap": gap,
            "fetched": len(candles),
            "inserted": inserted,
        }

    def _insert_candles(self, symbol: str, interval: str, candles: list[dict]) -> int:
        """Insert candles into database, replacing existing if needed."""
        conn = self._get_connection()
        inserted = 0

        for candle in candles:
            try:
                # Prepare datetime string
                open_time_dt = datetime.fromtimestamp(
                    candle["open_time"] / 1000, tz=timezone.utc
                ).isoformat()

                # Use INSERT OR REPLACE to handle existing candles
                conn.execute(
                    """
                    INSERT OR REPLACE INTO bybit_kline_audit
                    (symbol, interval, open_time, open_time_dt,
                     open_price, high_price, low_price, close_price,
                     volume, turnover, raw)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        interval,
                        candle["open_time"],
                        open_time_dt,
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle.get("volume", 0),
                        candle.get("turnover", 0),
                        str(candle),
                    ),
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert candle: {e}")

        conn.commit()
        conn.close()
        return inserted

    def repair_all_gaps(
        self,
        symbol: str,
        interval: str,
        skip_weekends: bool = True,
        max_gaps: int = 50,
    ) -> dict:
        """
        Find and repair all timestamp gaps for a symbol/interval.

        Args:
            symbol: Trading symbol
            interval: Timeframe
            skip_weekends: Skip weekend gaps (market closed)
            max_gaps: Maximum gaps to repair in one run

        Returns:
            Summary dict with repair results
        """
        logger.info(f"Starting gap repair for {symbol}:{interval}")

        gaps = self.find_timestamp_gaps(
            symbol=symbol,
            interval=interval,
            max_gaps=max_gaps,
            skip_weekends=skip_weekends,
        )

        if not gaps:
            logger.info(f"No gaps found for {symbol}:{interval}")
            return {"status": "no_gaps", "symbol": symbol, "interval": interval}

        logger.info(f"Found {len(gaps)} gaps to repair")

        results = []
        total_inserted = 0

        for gap in gaps:
            result = self.repair_gap(gap)
            results.append(result)
            if result.get("inserted"):
                total_inserted += result["inserted"]

        return {
            "status": "completed",
            "symbol": symbol,
            "interval": interval,
            "gaps_found": len(gaps),
            "gaps_repaired": sum(1 for r in results if r["status"] == "repaired"),
            "total_candles_inserted": total_inserted,
            "details": results,
        }

    def get_repair_summary(self, symbol: str, interval: str) -> dict:
        """Get summary of data quality for a symbol/interval."""
        conn = self._get_connection()

        # Count total candles
        cursor = conn.execute(
            "SELECT COUNT(*), MIN(open_time), MAX(open_time) "
            "FROM bybit_kline_audit WHERE symbol = ? AND interval = ?",
            (symbol, interval),
        )
        row = cursor.fetchone()
        total_candles = row[0]
        min_time = row[1]
        max_time = row[2]

        # Count expected candles
        if min_time and max_time:
            interval_ms = INTERVAL_MS.get(interval, 60_000)
            expected = int((max_time - min_time) / interval_ms) + 1
            completeness = (total_candles / expected * 100) if expected > 0 else 100
        else:
            expected = 0
            completeness = 100

        conn.close()

        # Find gaps
        timestamp_gaps = self.find_timestamp_gaps(
            symbol, interval, max_gaps=100, skip_weekends=False
        )
        weekend_gaps = [g for g in timestamp_gaps if g.is_weekend]
        data_gaps = [g for g in timestamp_gaps if not g.is_weekend]

        return {
            "symbol": symbol,
            "interval": interval,
            "total_candles": total_candles,
            "expected_candles": expected,
            "completeness_pct": round(completeness, 2),
            "data_gaps": len(data_gaps),
            "weekend_gaps": len(weekend_gaps),
            "needs_repair": len(data_gaps) > 0,
        }


# Singleton instance
_repair_service: Optional[DataGapRepairService] = None


def get_repair_service() -> DataGapRepairService:
    """Get the singleton repair service instance."""
    global _repair_service
    if _repair_service is None:
        _repair_service = DataGapRepairService()
    return _repair_service


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    service = DataGapRepairService()

    if len(sys.argv) > 1 and sys.argv[1] == "repair":
        # Run repair
        symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSDT"
        interval = sys.argv[3] if len(sys.argv) > 3 else "1"

        print(f"\n{'=' * 60}")
        print(f"REPAIRING GAPS: {symbol}:{interval}")
        print(f"{'=' * 60}")

        result = service.repair_all_gaps(symbol, interval)
        print(f"\nResult: {result['status']}")
        print(f"Gaps found: {result.get('gaps_found', 0)}")
        print(f"Gaps repaired: {result.get('gaps_repaired', 0)}")
        print(f"Candles inserted: {result.get('total_candles_inserted', 0)}")

    else:
        # Show summary
        print(f"\n{'=' * 60}")
        print("DATA QUALITY SUMMARY")
        print(f"{'=' * 60}")

        for symbol in ["BTCUSDT", "ETHUSDT"]:
            for interval in ["1", "5", "15", "60"]:
                try:
                    summary = service.get_repair_summary(symbol, interval)
                    if summary["total_candles"] > 0:
                        status = (
                            "⚠️ NEEDS REPAIR" if summary["needs_repair"] else "✅ OK"
                        )
                        print(
                            f"{symbol}:{interval:>3} | "
                            f"{summary['total_candles']:>6} candles | "
                            f"{summary['completeness_pct']:>6.2f}% complete | "
                            f"gaps: {summary['data_gaps']} | "
                            f"{status}"
                        )
                except Exception:
                    pass

        print(f"\n{'=' * 60}")
        print("Usage: python data_gap_repair.py repair [SYMBOL] [INTERVAL]")
        print("Example: python data_gap_repair.py repair BTCUSDT 1")
        print(f"{'=' * 60}")
