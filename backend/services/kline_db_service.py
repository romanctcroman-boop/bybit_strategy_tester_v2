"""
Kline Database Service - Standalone Database Server for Market Data

This service runs as a separate process and handles all database operations
for kline data, preventing database locks and improving reliability.

Features:
- Runs as standalone background service
- Handles all INSERT/UPDATE/SELECT for kline data
- Uses queue-based architecture for reliability
- Prevents database lock issues
- Auto-reconnect on failures
"""

import json
import logging
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "logs" / "kline_db_service.log", mode="a"),
    ],
)
logger = logging.getLogger("KlineDBService")


@dataclass
class KlineRecord:
    """Kline record for database storage."""

    symbol: str
    interval: str
    open_time: int
    open_time_dt: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float
    raw: str


class KlineDBService:
    """
    Standalone Database Service for Kline Data.

    Runs as a separate process/thread and handles all database operations
    for market data. Uses a write queue for reliability.
    """

    _instance: Optional["KlineDBService"] = None

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(PROJECT_ROOT / "data.sqlite3")
        self._write_queue: Queue = Queue(maxsize=10000)
        self._read_lock = Lock()
        self._running = Event()
        self._writer_thread: Optional[Thread] = None
        self._connection: Optional[sqlite3.Connection] = None
        self._stats = {
            "inserts": 0,
            "updates": 0,
            "reads": 0,
            "errors": 0,
            "queue_size": 0,
        }
        logger.info(f"KlineDBService initialized with DB: {self.db_path}")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "KlineDBService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    def start(self):
        """Start the database service."""
        if self._running.is_set():
            logger.warning("Service already running")
            return

        logger.info("Starting KlineDBService...")
        self._running.set()

        # Ensure table exists
        self._ensure_table()

        # Start writer thread
        self._writer_thread = Thread(target=self._write_loop, daemon=True)
        self._writer_thread.start()

        logger.info("[OK] KlineDBService started")

    def stop(self):
        """Stop the database service."""
        logger.info("Stopping KlineDBService...")
        self._running.clear()

        # Wait for queue to drain
        if not self._write_queue.empty():
            logger.info(f"Waiting for {self._write_queue.qsize()} pending writes...")
            timeout = 10
            start = time.time()
            while not self._write_queue.empty() and (time.time() - start) < timeout:
                time.sleep(0.1)

        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5)

        if self._connection:
            self._connection.close()
            self._connection = None

        logger.info("[OK] KlineDBService stopped")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )
            self._connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.execute("PRAGMA cache_size=10000")
        return self._connection

    def _ensure_table(self):
        """Ensure kline table exists with correct schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bybit_kline_audit (
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
                raw TEXT NOT NULL,
                inserted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure unique index on (symbol, interval, open_time)
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uix_symbol_interval_open_time
                ON bybit_kline_audit(symbol, interval, open_time)
            """)
        except sqlite3.OperationalError:
            pass  # Index may already exist

        # Drop old index if exists
        try:
            cursor.execute("DROP INDEX IF EXISTS uix_symbol_open_time")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        logger.info("Database schema verified")

    def _write_loop(self):
        """Background thread for processing write queue."""
        logger.info("Write loop started")
        batch: List[KlineRecord] = []
        batch_size = 100
        flush_interval = 1.0  # seconds
        last_flush = time.time()

        while self._running.is_set():
            try:
                # Get item from queue with timeout
                try:
                    record = self._write_queue.get(timeout=0.1)
                    batch.append(record)
                except Empty:
                    pass

                # Flush if batch is full or timeout
                current_time = time.time()
                if len(batch) >= batch_size or (
                    batch and current_time - last_flush > flush_interval
                ):
                    self._flush_batch(batch)
                    batch = []
                    last_flush = current_time

            except Exception as e:
                logger.error(f"Write loop error: {e}")
                self._stats["errors"] += 1
                time.sleep(0.5)

        # Final flush
        if batch:
            self._flush_batch(batch)

        logger.info("Write loop stopped")

    def _flush_batch(self, batch: List[KlineRecord]):
        """Flush a batch of records to database."""
        if not batch:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        inserted = 0
        updated = 0

        for record in batch:
            try:
                # Use UPSERT (INSERT OR REPLACE)
                cursor.execute(
                    """
                    INSERT INTO bybit_kline_audit
                    (symbol, interval, open_time, open_time_dt, open_price, high_price,
                     low_price, close_price, volume, turnover, raw, inserted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(symbol, interval, open_time) DO UPDATE SET
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        raw = excluded.raw,
                        inserted_at = CURRENT_TIMESTAMP
                """,
                    (
                        record.symbol,
                        record.interval,
                        record.open_time,
                        record.open_time_dt.isoformat()
                        if record.open_time_dt
                        else None,
                        record.open_price,
                        record.high_price,
                        record.low_price,
                        record.close_price,
                        record.volume,
                        record.turnover,
                        record.raw,
                    ),
                )

                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error(f"Insert error for {record.symbol}/{record.interval}: {e}")
                self._stats["errors"] += 1

        conn.commit()
        self._stats["inserts"] += inserted
        self._stats["updates"] += updated
        self._stats["queue_size"] = self._write_queue.qsize()

        logger.debug(f"Flushed batch: {inserted} inserted, {updated} updated")

    # =========================================================================
    # Public API
    # =========================================================================

    def queue_klines(self, symbol: str, interval: str, candles: List[Dict]) -> int:
        """
        Queue candles for database insertion.

        Returns number of candles queued.
        """
        queued = 0
        for candle in candles:
            try:
                open_time = int(candle.get("open_time", candle.get("openTime", 0)))
                if not open_time:
                    continue

                record = KlineRecord(
                    symbol=symbol,
                    interval=interval,
                    open_time=open_time,
                    open_time_dt=datetime.fromtimestamp(
                        open_time / 1000, tz=timezone.utc
                    ),
                    open_price=float(candle.get("open", 0)),
                    high_price=float(candle.get("high", 0)),
                    low_price=float(candle.get("low", 0)),
                    close_price=float(candle.get("close", 0)),
                    volume=float(candle.get("volume", 0)),
                    turnover=float(candle.get("turnover", 0)),
                    raw=json.dumps(candle, default=str),
                )

                self._write_queue.put_nowait(record)
                queued += 1

            except Exception as e:
                logger.warning(f"Failed to queue candle: {e}")
                self._stats["errors"] += 1

        logger.info(f"Queued {queued} klines for {symbol}/{interval}")
        return queued

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        end_time: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get klines from database.

        Args:
            symbol: Trading pair symbol
            interval: Timeframe
            limit: Maximum number of candles
            end_time: Get candles before this timestamp (optional)

        Returns:
            List of candle dictionaries
        """
        with self._read_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                if end_time:
                    cursor.execute(
                        """
                        SELECT * FROM bybit_kline_audit
                        WHERE symbol = ? AND interval = ? AND open_time < ?
                        ORDER BY open_time DESC
                        LIMIT ?
                    """,
                        (symbol, interval, end_time, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM bybit_kline_audit
                        WHERE symbol = ? AND interval = ?
                        ORDER BY open_time DESC
                        LIMIT ?
                    """,
                        (symbol, interval, limit),
                    )

                rows = cursor.fetchall()
                self._stats["reads"] += 1

                candles = []
                for row in reversed(rows):  # Oldest first
                    candles.append(
                        {
                            "open_time": row["open_time"],
                            "open": row["open_price"],
                            "high": row["high_price"],
                            "low": row["low_price"],
                            "close": row["close_price"],
                            "volume": row["volume"],
                            "turnover": row["turnover"],
                        }
                    )

                return candles

            except Exception as e:
                logger.error(f"Read error for {symbol}/{interval}: {e}")
                self._stats["errors"] += 1
                return []

    def get_coverage(
        self, symbol: str, interval: str
    ) -> Optional[Tuple[int, int, int]]:
        """
        Get database coverage for a symbol/interval.

        Returns:
            Tuple of (oldest_time, newest_time, count) or None
        """
        with self._read_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT MIN(open_time), MAX(open_time), COUNT(*)
                    FROM bybit_kline_audit
                    WHERE symbol = ? AND interval = ?
                """,
                    (symbol, interval),
                )

                row = cursor.fetchone()
                if row and row[0]:
                    return (row[0], row[1], row[2])
                return None

            except Exception as e:
                logger.error(f"Coverage check error: {e}")
                return None

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            "queue_size": self._write_queue.qsize(),
            "running": self._running.is_set(),
        }

    def get_all_symbols_summary(self) -> List[Dict]:
        """Get summary of all symbols in database."""
        with self._read_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT symbol, interval, COUNT(*) as count,
                           MIN(open_time) as oldest, MAX(open_time) as newest
                    FROM bybit_kline_audit
                    GROUP BY symbol, interval
                    ORDER BY symbol, interval
                """)

                return [dict(row) for row in cursor.fetchall()]

            except Exception as e:
                logger.error(f"Summary error: {e}")
                return []


# ============================================================================
# Standalone Service Runner
# ============================================================================


def run_service():
    """Run the service as a standalone process."""
    logger.info("=" * 60)
    logger.info("Kline Database Service - Starting")
    logger.info("=" * 60)

    # Create logs directory
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    service = KlineDBService.get_instance()
    service.start()

    # Handle shutdown signals
    stop_event = Event()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Keep running until stopped
    logger.info("Service running. Press Ctrl+C to stop.")

    try:
        while not stop_event.is_set():
            # Print stats periodically
            stats = service.get_stats()
            logger.info(
                f"Stats - Inserts: {stats['inserts']}, "
                f"Updates: {stats['updates']}, "
                f"Reads: {stats['reads']}, "
                f"Queue: {stats['queue_size']}, "
                f"Errors: {stats['errors']}"
            )

            # Wait with interruptibility
            for _ in range(60):  # Check every second for 60 seconds
                if stop_event.is_set():
                    break
                time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")

    service.stop()
    logger.info("Service shutdown complete")


if __name__ == "__main__":
    run_service()
