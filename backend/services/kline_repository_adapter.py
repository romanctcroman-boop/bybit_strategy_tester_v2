"""
KlineDBService integration with Repository pattern.

This module provides a thin adapter layer between the standalone KlineDBService
(queue-based, raw SQLite) and the new Repository pattern (SQLAlchemy-based).

The integration is gradual:
1. Read operations use KlineRepository for consistency
2. Write operations stay queue-based for performance
3. Stats and monitoring are unified
"""

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database.repository.kline_repository import KlineRepository
from backend.database.unit_of_work import ReadOnlyUnitOfWork, UnitOfWork

logger = logging.getLogger(__name__)


class RepositoryMetrics:
    """Simple metrics collector for Repository operations."""

    def __init__(self):
        self._stats = {
            "get_klines_calls": 0,
            "get_klines_total_ms": 0.0,
            "get_coverage_calls": 0,
            "get_coverage_total_ms": 0.0,
            "bulk_upsert_calls": 0,
            "bulk_upsert_total_ms": 0.0,
            "errors": 0,
        }

    def record_get_klines(self, duration_ms: float):
        self._stats["get_klines_calls"] += 1
        self._stats["get_klines_total_ms"] += duration_ms

    def record_get_coverage(self, duration_ms: float):
        self._stats["get_coverage_calls"] += 1
        self._stats["get_coverage_total_ms"] += duration_ms

    def record_bulk_upsert(self, duration_ms: float):
        self._stats["bulk_upsert_calls"] += 1
        self._stats["bulk_upsert_total_ms"] += duration_ms

    def record_error(self):
        self._stats["errors"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        stats = self._stats.copy()
        # Calculate averages
        if stats["get_klines_calls"] > 0:
            stats["get_klines_avg_ms"] = (
                stats["get_klines_total_ms"] / stats["get_klines_calls"]
            )
        if stats["get_coverage_calls"] > 0:
            stats["get_coverage_avg_ms"] = (
                stats["get_coverage_total_ms"] / stats["get_coverage_calls"]
            )
        if stats["bulk_upsert_calls"] > 0:
            stats["bulk_upsert_avg_ms"] = (
                stats["bulk_upsert_total_ms"] / stats["bulk_upsert_calls"]
            )
        return stats


class RepositoryAdapter:
    """
    Adapter for integrating Repository pattern with KlineDBService.

    This allows gradual migration from raw SQL to Repository pattern
    without breaking existing functionality.
    """

    def __init__(self, db_url: str | None = None):
        """
        Initialize adapter.

        Args:
            db_url: SQLAlchemy database URL (e.g., sqlite:///data.sqlite3)
        """
        self.db_url = db_url or "sqlite:///data.sqlite3"
        self._engine = None
        self._session_factory = None
        self._metrics = RepositoryMetrics()

    @property
    def metrics(self) -> RepositoryMetrics:
        """Get metrics collector."""
        return self._metrics

    @property
    def engine(self):
        """Lazy engine creation."""
        if self._engine is None:
            self._engine = create_engine(
                self.db_url,
                echo=False,
                pool_pre_ping=True,
                # SQLite specific optimizations
                connect_args={"check_same_thread": False, "timeout": 30.0},
            )
        return self._engine

    @property
    def session_factory(self):
        """Lazy session factory creation."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine, expire_on_commit=False
            )
        return self._session_factory

    @contextmanager
    def session(self) -> Generator[Session]:
        """Get a session context manager."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def unit_of_work(self) -> Generator[UnitOfWork]:
        """Get a Unit of Work for transaction management."""
        with self.session() as session:
            uow = UnitOfWork(session)
            with uow:
                yield uow

    @contextmanager
    def read_only(self) -> Generator[ReadOnlyUnitOfWork]:
        """Get a read-only Unit of Work."""
        with self.session() as session:
            uow = ReadOnlyUnitOfWork(session)
            with uow:
                yield uow

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get klines using Repository pattern.

        This is a drop-in replacement for KlineDBService.get_klines()

        Note: end_time uses exclusive semantics (< end_time) to match legacy behavior.
        """
        start_time_perf = time.perf_counter()
        try:
            with self.session() as session:
                repo = KlineRepository(session)
                # Convert exclusive end_time to inclusive (repo uses <=)
                # Legacy: < end_time, Repo: <= end_time, so use end_time - 1
                adjusted_end_time = end_time - 1 if end_time else None
                result = repo.get_klines_as_dicts(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    end_time=adjusted_end_time,
                )
                return result
        except Exception:
            self._metrics.record_error()
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time_perf) * 1000
            self._metrics.record_get_klines(duration_ms)

    def get_coverage(
        self, symbol: str, interval: str
    ) -> tuple[int, int, int] | None:
        """
        Get database coverage using Repository pattern.

        This is a drop-in replacement for KlineDBService.get_coverage()

        Returns:
            Tuple of (oldest_time, newest_time, count) or None
        """
        start_time_perf = time.perf_counter()
        try:
            with self.session() as session:
                repo = KlineRepository(session)
                result = repo.get_coverage(symbol, interval)

                if result["count"] == 0:
                    return None

                return (result["oldest"], result["newest"], result["count"])
        except Exception:
            self._metrics.record_error()
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time_perf) * 1000
            self._metrics.record_get_coverage(duration_ms)

    def find_gaps(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        expected_interval_ms: int,
    ) -> list[tuple[int, int]]:
        """
        Find gaps in kline data using Repository pattern.

        Returns list of (gap_start, gap_end) tuples.
        """
        with self.session() as session:
            repo = KlineRepository(session)
            return repo.find_gaps(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                expected_interval_ms=expected_interval_ms,
            )

    def bulk_upsert(
        self, symbol: str, interval: str, candles: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """
        Bulk upsert klines using Repository pattern.

        Returns (inserted_count, updated_count).
        """
        with self.session() as session:
            repo = KlineRepository(session)
            result = repo.bulk_upsert(symbol, interval, candles)
            session.commit()
            return result

    def get_all_symbols_summary(self) -> list[dict[str, Any]]:
        """Get summary of all symbols in database."""
        with self.session() as session:
            # Use raw SQL for this complex aggregation
            from sqlalchemy import text

            result = session.execute(
                text("""
                SELECT symbol, interval, COUNT(*) as count,
                       MIN(open_time) as oldest, MAX(open_time) as newest
                FROM bybit_kline_audit
                GROUP BY symbol, interval
                ORDER BY symbol, interval
            """)
            )
            return [dict(row._mapping) for row in result]


# Singleton instance
_adapter_instance: RepositoryAdapter | None = None


def get_repository_adapter(db_url: str | None = None) -> RepositoryAdapter:
    """
    Get singleton RepositoryAdapter instance.

    Usage:
        adapter = get_repository_adapter()
        klines = adapter.get_klines("BTCUSDT", "1h", limit=100)
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = RepositoryAdapter(db_url)
    return _adapter_instance
