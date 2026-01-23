"""
Extended Database Metrics - Query Histograms, Connection Timing, Archive Stats.

Provides additional Prometheus metrics as recommended by DeepSeek audit:
1. Query duration histograms by operation and table
2. Connection pool wait time tracking
3. Archive table size metrics
4. Circuit breaker integration

Usage:
    from backend.monitoring.extended_metrics import metrics_collector

    # Record a query duration
    with metrics_collector.time_query("select", "bybit_kline_audit"):
        cursor.execute("SELECT ...")

    # Get Prometheus metrics
    print(metrics_collector.get_prometheus_metrics())
"""

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class HistogramBucket:
    """Histogram bucket for latency distribution."""

    le: float  # Less than or equal threshold
    count: int = 0


@dataclass
class Histogram:
    """
    Simple histogram implementation for query latencies.

    Buckets: 1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, +Inf
    """

    # Bucket thresholds in milliseconds
    BUCKET_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

    buckets: List[HistogramBucket] = field(default_factory=list)
    count: int = 0
    sum: float = 0.0

    def __post_init__(self):
        if not self.buckets:
            self.buckets = [HistogramBucket(le=t) for t in self.BUCKET_THRESHOLDS]
            self.buckets.append(HistogramBucket(le=float("inf")))

    def observe(self, value_ms: float) -> None:
        """Record an observation."""
        self.count += 1
        self.sum += value_ms

        for bucket in self.buckets:
            if value_ms <= bucket.le:
                bucket.count += 1


@dataclass
class CounterWithLabels:
    """Counter metric with label support."""

    values: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def inc(self, labels: str, value: int = 1) -> None:
        """Increment counter for given labels."""
        self.values[labels] += value


class MetricsCollector:
    """
    Extended metrics collector for database operations.

    Collects:
    - Query duration histograms by operation/table
    - Connection pool wait times
    - Archive table sizes
    - Operation counts and errors
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Query duration histograms: {(operation, table): Histogram}
        self._query_histograms: Dict[tuple, Histogram] = defaultdict(Histogram)

        # Connection pool wait time histogram
        self._connection_wait_histogram = Histogram()

        # Archive table sizes: {table_name: size_bytes}
        self._archive_sizes: Dict[str, int] = {}

        # Operation counters: {(operation, table): count}
        self._operation_counts: Dict[tuple, int] = defaultdict(int)
        self._error_counts: Dict[tuple, int] = defaultdict(int)

        # Last update timestamps
        self._archive_sizes_updated: float = 0

    @contextmanager
    def time_query(self, operation: str, table: str = "unknown"):
        """
        Context manager to time a database query.

        Args:
            operation: Query type (select, insert, update, delete, etc.)
            table: Table name

        Usage:
            with metrics.time_query("select", "bybit_kline_audit"):
                cursor.execute("SELECT ...")
        """
        start = time.perf_counter()
        error = False
        try:
            yield
        except Exception:
            error = True
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            key = (operation.lower(), table.lower())

            with self._lock:
                self._query_histograms[key].observe(duration_ms)
                self._operation_counts[key] += 1
                if error:
                    self._error_counts[key] += 1

    @contextmanager
    def time_connection_wait(self):
        """
        Context manager to time connection pool wait.

        Usage:
            with metrics.time_connection_wait():
                conn = pool.get_connection()
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            with self._lock:
                self._connection_wait_histogram.observe(duration_ms)

    def record_query_time(self, operation: str, table: str, duration_ms: float) -> None:
        """Directly record a query duration."""
        key = (operation.lower(), table.lower())
        with self._lock:
            self._query_histograms[key].observe(duration_ms)
            self._operation_counts[key] += 1

    def record_error(self, operation: str, table: str) -> None:
        """Record an operation error."""
        key = (operation.lower(), table.lower())
        with self._lock:
            self._error_counts[key] += 1

    def update_archive_sizes(self, sizes: Dict[str, int]) -> None:
        """Update archive table sizes."""
        with self._lock:
            self._archive_sizes = sizes.copy()
            self._archive_sizes_updated = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics as dictionary."""
        with self._lock:
            # Aggregate query stats
            query_stats = {}
            for (op, table), histogram in self._query_histograms.items():
                key = f"{op}_{table}"
                query_stats[key] = {
                    "count": histogram.count,
                    "sum_ms": histogram.sum,
                    "avg_ms": histogram.sum / histogram.count
                    if histogram.count > 0
                    else 0,
                }

            return {
                "query_stats": query_stats,
                "total_operations": sum(self._operation_counts.values()),
                "total_errors": sum(self._error_counts.values()),
                "connection_wait": {
                    "count": self._connection_wait_histogram.count,
                    "sum_ms": self._connection_wait_histogram.sum,
                    "avg_ms": (
                        self._connection_wait_histogram.sum
                        / self._connection_wait_histogram.count
                        if self._connection_wait_histogram.count > 0
                        else 0
                    ),
                },
                "archive_sizes": self._archive_sizes.copy(),
                "archive_sizes_updated": self._archive_sizes_updated,
            }

    def get_prometheus_metrics(self) -> str:
        """Get all metrics in Prometheus format."""
        lines = []

        with self._lock:
            # Query duration histograms
            lines.append(
                "# HELP db_query_duration_seconds Database query duration in seconds"
            )
            lines.append("# TYPE db_query_duration_seconds histogram")

            for (op, table), histogram in self._query_histograms.items():
                labels = f'operation="{op}",table="{table}"'

                cumulative = 0
                for bucket in histogram.buckets:
                    cumulative += bucket.count
                    le = (
                        "+Inf"
                        if bucket.le == float("inf")
                        else f"{bucket.le / 1000:.3f}"
                    )
                    lines.append(
                        f'db_query_duration_seconds_bucket{{{labels},le="{le}"}} {cumulative}'
                    )

                lines.append(
                    f"db_query_duration_seconds_sum{{{labels}}} {histogram.sum / 1000:.6f}"
                )
                lines.append(
                    f"db_query_duration_seconds_count{{{labels}}} {histogram.count}"
                )

            lines.append("")

            # Connection wait histogram
            lines.append(
                "# HELP db_connection_wait_seconds Time spent waiting for database connection"
            )
            lines.append("# TYPE db_connection_wait_seconds histogram")

            hist = self._connection_wait_histogram
            cumulative = 0
            for bucket in hist.buckets:
                cumulative += bucket.count
                le = "+Inf" if bucket.le == float("inf") else f"{bucket.le / 1000:.3f}"
                lines.append(
                    f'db_connection_wait_seconds_bucket{{le="{le}"}} {cumulative}'
                )

            lines.append(f"db_connection_wait_seconds_sum {hist.sum / 1000:.6f}")
            lines.append(f"db_connection_wait_seconds_count {hist.count}")
            lines.append("")

            # Operation counts
            lines.append("# HELP db_operations_total Total database operations by type")
            lines.append("# TYPE db_operations_total counter")
            for (op, table), count in self._operation_counts.items():
                lines.append(
                    f'db_operations_total{{operation="{op}",table="{table}"}} {count}'
                )
            lines.append("")

            # Error counts
            lines.append("# HELP db_errors_total Total database errors by type")
            lines.append("# TYPE db_errors_total counter")
            for (op, table), count in self._error_counts.items():
                if count > 0:
                    lines.append(
                        f'db_errors_total{{operation="{op}",table="{table}"}} {count}'
                    )
            lines.append("")

            # Archive sizes
            lines.append(
                "# HELP db_archive_table_size_bytes Size of archive tables in bytes"
            )
            lines.append("# TYPE db_archive_table_size_bytes gauge")
            for table, size in self._archive_sizes.items():
                lines.append(f'db_archive_table_size_bytes{{table="{table}"}} {size}')

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._query_histograms.clear()
            self._connection_wait_histogram = Histogram()
            self._archive_sizes.clear()
            self._operation_counts.clear()
            self._error_counts.clear()


# ============================================================================
# Global Instance
# ============================================================================

metrics_collector = MetricsCollector()


def get_extended_metrics() -> Dict[str, Any]:
    """Get extended metrics as dictionary."""
    return metrics_collector.get_stats()


def get_extended_prometheus_metrics() -> str:
    """Get extended metrics in Prometheus format."""
    return metrics_collector.get_prometheus_metrics()
