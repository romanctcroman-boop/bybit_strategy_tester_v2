"""
Time-based Data Archiving and Partitioning for Kline Data.

This module provides:
1. Monthly archive tables for old data (>6 months)
2. Automatic data migration from main table to archives
3. Unified query layer across partitions
4. Compression support for archived data

Architecture:
- Main table: bybit_kline_audit (hot data, last 6 months)
- Archive tables: bybit_kline_archive_YYYYMM (cold data, compressed)

Usage:
    from backend.database.partitioning import KlineArchiver

    archiver = KlineArchiver(db_path)
    archiver.archive_old_data(months_to_keep=6)
"""

import logging
import sqlite3
import zlib
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# Interval mapping for gap detection
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


class KlineArchiver:
    """
    Time-based partitioning and archiving for kline data.

    Moves old data from main table to monthly archive tables
    with optional compression.
    """

    def __init__(self, db_path: str, compress: bool = True):
        """
        Initialize archiver.

        Args:
            db_path: Path to SQLite database
            compress: Whether to compress archived data
        """
        self.db_path = db_path
        self.compress = compress
        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=60.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _get_archive_table_name(self, year: int, month: int) -> str:
        """Get archive table name for a given year/month."""
        return f"bybit_kline_archive_{year:04d}{month:02d}"

    def _create_archive_table(self, table_name: str) -> None:
        """Create archive table if it doesn't exist."""
        conn = self._get_connection()

        # Same schema as main table but with compressed raw field
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(64) NOT NULL,
                interval VARCHAR(16),
                open_time BIGINT NOT NULL,
                open_time_dt DATETIME,
                open_price FLOAT,
                high_price FLOAT,
                low_price FLOAT,
                close_price FLOAT,
                volume FLOAT,
                turnover FLOAT,
                raw BLOB,  -- Compressed with zlib
                inserted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                archived_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, interval, open_time)
            )
        """)

        # Create indexes for common queries
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_interval
            ON {table_name}(symbol, interval, open_time)
        """)

        conn.commit()
        logger.info(f"Created archive table: {table_name}")

    def get_archive_tables(self) -> list[str]:
        """Get list of existing archive tables."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'bybit_kline_archive_%'
            ORDER BY name
        """)
        return [row[0] for row in cursor.fetchall()]

    def get_data_date_range(self) -> tuple[datetime, datetime] | None:
        """Get date range of data in main table."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT MIN(open_time), MAX(open_time)
            FROM bybit_kline_audit
        """)
        row = cursor.fetchone()

        if row and row[0]:
            oldest = datetime.fromtimestamp(row[0] / 1000, tz=UTC)
            newest = datetime.fromtimestamp(row[1] / 1000, tz=UTC)
            return (oldest, newest)
        return None

    def archive_old_data(
        self, months_to_keep: int = 6, batch_size: int = 10000, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Archive data older than specified months.

        Args:
            months_to_keep: Keep this many months of data in main table
            batch_size: Number of records to process per batch
            dry_run: If True, only report what would be done

        Returns:
            Dict with archive statistics
        """
        from datetime import timedelta

        conn = self._get_connection()

        # Calculate cutoff date
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=months_to_keep * 30)
        cutoff_ms = int(cutoff.timestamp() * 1000)

        logger.info(
            f"Archiving data older than {cutoff.date()} ({months_to_keep} months)"
        )

        # Get count of records to archive
        cursor = conn.execute(
            "SELECT COUNT(*) FROM bybit_kline_audit WHERE open_time < ?", (cutoff_ms,)
        )
        total_to_archive = cursor.fetchone()[0]

        if total_to_archive == 0:
            logger.info("No data to archive")
            return {"archived": 0, "tables_created": []}

        logger.info(f"Found {total_to_archive:,} records to archive")

        if dry_run:
            return {
                "archived": 0,
                "would_archive": total_to_archive,
                "cutoff_date": cutoff.isoformat(),
                "dry_run": True,
            }

        # Process in batches by month
        tables_created = []
        total_archived = 0

        # Get distinct year-months to archive
        cursor = conn.execute(
            """
            SELECT DISTINCT
                strftime('%Y', datetime(open_time/1000, 'unixepoch')) as year,
                strftime('%m', datetime(open_time/1000, 'unixepoch')) as month
            FROM bybit_kline_audit
            WHERE open_time < ?
            ORDER BY year, month
        """,
            (cutoff_ms,),
        )

        months_to_process = [(int(row[0]), int(row[1])) for row in cursor.fetchall()]

        for year, month in months_to_process:
            table_name = self._get_archive_table_name(year, month)

            # Create archive table
            if table_name not in self.get_archive_tables():
                self._create_archive_table(table_name)
                tables_created.append(table_name)

            # Calculate month boundaries
            month_start = datetime(year, month, 1, tzinfo=UTC)
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=UTC)
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=UTC)

            start_ms = int(month_start.timestamp() * 1000)
            end_ms = int(month_end.timestamp() * 1000)

            # Move data in batches
            archived_this_month = 0
            while True:
                # Select batch
                cursor = conn.execute(
                    """
                    SELECT id, symbol, interval, open_time, open_time_dt,
                           open_price, high_price, low_price, close_price,
                           volume, turnover, raw, inserted_at
                    FROM bybit_kline_audit
                    WHERE open_time >= ? AND open_time < ?
                    LIMIT ?
                """,
                    (start_ms, end_ms, batch_size),
                )

                rows = cursor.fetchall()
                if not rows:
                    break

                # Insert into archive (with compression)
                for row in rows:
                    raw_data = row["raw"]
                    if self.compress and raw_data:
                        raw_data = zlib.compress(raw_data.encode("utf-8"))

                    conn.execute(
                        f"""
                        INSERT OR REPLACE INTO {table_name}
                        (symbol, interval, open_time, open_time_dt,
                         open_price, high_price, low_price, close_price,
                         volume, turnover, raw, inserted_at, archived_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            row["symbol"],
                            row["interval"],
                            row["open_time"],
                            row["open_time_dt"],
                            row["open_price"],
                            row["high_price"],
                            row["low_price"],
                            row["close_price"],
                            row["volume"],
                            row["turnover"],
                            raw_data,
                            row["inserted_at"],
                        ),
                    )

                # Delete from main table
                ids = [row["id"] for row in rows]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"DELETE FROM bybit_kline_audit WHERE id IN ({placeholders})", ids
                )

                conn.commit()
                archived_this_month += len(rows)
                total_archived += len(rows)

                logger.debug(f"Archived {len(rows)} records to {table_name}")

            logger.info(f"Archived {archived_this_month:,} records to {table_name}")

        # Vacuum to reclaim space
        logger.info("Running VACUUM to reclaim space...")
        conn.execute("VACUUM")

        result = {
            "archived": total_archived,
            "tables_created": tables_created,
            "months_processed": len(months_to_process),
            "cutoff_date": cutoff.isoformat(),
        }

        logger.info(f"Archive complete: {total_archived:,} records moved")
        return result

    def query_archive(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query data from archive tables.

        Automatically decompresses raw field.
        """
        conn = self._get_connection()

        # Determine which archive tables to query
        start_dt = datetime.fromtimestamp(start_time / 1000, tz=UTC)
        end_dt = datetime.fromtimestamp(end_time / 1000, tz=UTC)

        # Get relevant archive tables
        archive_tables = self.get_archive_tables()
        relevant_tables = []

        for table in archive_tables:
            # Extract year-month from table name
            try:
                ym = table.replace("bybit_kline_archive_", "")
                year = int(ym[:4])
                month = int(ym[4:6])
                table_date = datetime(year, month, 1, tzinfo=UTC)

                # Check if table overlaps with query range
                if (
                    table_date.year * 12 + table_date.month
                    >= start_dt.year * 12 + start_dt.month
                ) and (
                    table_date.year * 12 + table_date.month
                    <= end_dt.year * 12 + end_dt.month
                ):
                    relevant_tables.append(table)
            except ValueError:
                continue

        if not relevant_tables:
            return []

        # Query from each table and merge results
        results = []
        remaining = limit

        for table in sorted(relevant_tables):
            cursor = conn.execute(
                f"""
                SELECT symbol, interval, open_time, open_time_dt,
                       open_price, high_price, low_price, close_price,
                       volume, turnover, raw
                FROM {table}
                WHERE symbol = ? AND interval = ?
                  AND open_time >= ? AND open_time <= ?
                ORDER BY open_time ASC
                LIMIT ?
            """,
                (symbol, interval, start_time, end_time, remaining),
            )

            for row in cursor.fetchall():
                raw_data = row["raw"]
                if raw_data and isinstance(raw_data, bytes):
                    try:
                        raw_data = zlib.decompress(raw_data).decode("utf-8")
                    except zlib.error:
                        raw_data = (
                            raw_data.decode("utf-8")
                            if isinstance(raw_data, bytes)
                            else raw_data
                        )

                results.append(
                    {
                        "open_time": row["open_time"],
                        "open": float(row["open_price"]),
                        "high": float(row["high_price"]),
                        "low": float(row["low_price"]),
                        "close": float(row["close_price"]),
                        "volume": float(row["volume"]) if row["volume"] else 0,
                        "turnover": float(row["turnover"]) if row["turnover"] else 0,
                    }
                )

                remaining -= 1
                if remaining <= 0:
                    break

            if remaining <= 0:
                break

        return results

    def get_archive_stats(self) -> dict[str, Any]:
        """Get statistics about archived data."""
        conn = self._get_connection()

        stats = {
            "archive_tables": [],
            "total_archived": 0,
            "main_table_count": 0,
            "compression_enabled": self.compress,
        }

        # Main table count
        cursor = conn.execute("SELECT COUNT(*) FROM bybit_kline_audit")
        stats["main_table_count"] = cursor.fetchone()[0]

        # Archive table stats
        for table in self.get_archive_tables():
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            cursor = conn.execute(f"""
                SELECT MIN(open_time), MAX(open_time) FROM {table}
            """)
            row = cursor.fetchone()

            table_stat = {
                "name": table,
                "count": count,
                "oldest": datetime.fromtimestamp(
                    row[0] / 1000, tz=UTC
                ).isoformat()
                if row[0]
                else None,
                "newest": datetime.fromtimestamp(
                    row[1] / 1000, tz=UTC
                ).isoformat()
                if row[1]
                else None,
            }

            stats["archive_tables"].append(table_stat)
            stats["total_archived"] += count

        return stats


class UnifiedKlineQuery:
    """
    Unified query layer that queries both main and archive tables.

    Provides seamless access to all historical data regardless
    of partitioning.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.archiver = KlineArchiver(db_path)

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get klines from both main and archive tables.

        Automatically routes queries to appropriate tables.
        """
        conn = self.archiver._get_connection()
        results = []
        remaining = limit

        # Build query for main table
        query = """
            SELECT open_time, open_price, high_price, low_price,
                   close_price, volume, turnover
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ?
        """
        params = [symbol, interval]

        if start_time:
            query += " AND open_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND open_time <= ?"
            params.append(end_time)

        query += " ORDER BY open_time ASC LIMIT ?"
        params.append(remaining)

        # Query main table first
        cursor = conn.execute(query, params)

        for row in cursor.fetchall():
            results.append(
                {
                    "open_time": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]) if row[5] else 0,
                    "turnover": float(row[6]) if row[6] else 0,
                }
            )
            remaining -= 1

        # If we need more data and have time range, query archives
        if remaining > 0 and start_time and end_time:
            archive_results = self.archiver.query_archive(
                symbol, interval, start_time, end_time, remaining
            )

            # Merge and deduplicate
            existing_times = {r["open_time"] for r in results}
            for ar in archive_results:
                if ar["open_time"] not in existing_times:
                    results.append(ar)

        # Sort by time
        results.sort(key=lambda x: x["open_time"])

        return results[:limit]

    def get_full_coverage(self, symbol: str, interval: str) -> dict[str, Any]:
        """Get coverage including archived data."""
        conn = self.archiver._get_connection()

        # Main table
        cursor = conn.execute(
            """
            SELECT MIN(open_time), MAX(open_time), COUNT(*)
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ?
        """,
            (symbol, interval),
        )
        main_row = cursor.fetchone()

        # Archives
        archive_min = None
        archive_max = None
        archive_count = 0

        for table in self.archiver.get_archive_tables():
            cursor = conn.execute(
                f"""
                SELECT MIN(open_time), MAX(open_time), COUNT(*)
                FROM {table}
                WHERE symbol = ? AND interval = ?
            """,
                (symbol, interval),
            )
            row = cursor.fetchone()

            if row and row[2] > 0:
                if archive_min is None or row[0] < archive_min:
                    archive_min = row[0]
                if archive_max is None or row[1] > archive_max:
                    archive_max = row[1]
                archive_count += row[2]

        # Combine
        oldest = (
            min(filter(None, [main_row[0], archive_min]))
            if main_row[0] or archive_min
            else None
        )
        newest = (
            max(filter(None, [main_row[1], archive_max]))
            if main_row[1] or archive_max
            else None
        )
        total_count = (main_row[2] or 0) + archive_count

        return {
            "symbol": symbol,
            "interval": interval,
            "oldest": oldest,
            "newest": newest,
            "total_count": total_count,
            "main_count": main_row[2] or 0,
            "archive_count": archive_count,
            "oldest_dt": datetime.fromtimestamp(oldest / 1000, tz=UTC)
            if oldest
            else None,
            "newest_dt": datetime.fromtimestamp(newest / 1000, tz=UTC)
            if newest
            else None,
        }


# Convenience function
def archive_old_klines(
    db_path: str = "data.sqlite3", months_to_keep: int = 6, dry_run: bool = False
) -> dict[str, Any]:
    """
    Archive old kline data.

    Usage:
        from backend.database.partitioning import archive_old_klines

        # Preview what would be archived
        result = archive_old_klines(dry_run=True)

        # Actually archive
        result = archive_old_klines(months_to_keep=6)
    """
    archiver = KlineArchiver(db_path)
    try:
        return archiver.archive_old_data(months_to_keep=months_to_keep, dry_run=dry_run)
    finally:
        archiver.close()
