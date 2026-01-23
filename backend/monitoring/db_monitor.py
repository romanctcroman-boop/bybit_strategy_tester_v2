"""
Database Monitoring Module - Health Checks, Metrics, and Alerting.

This module provides:
1. Health check endpoint for database components
2. Prometheus-compatible metrics export
3. Alerting thresholds and status indicators

Usage:
    from backend.monitoring.db_monitor import DatabaseMonitor

    monitor = DatabaseMonitor()
    health = monitor.check_health()
    metrics = monitor.get_metrics_prometheus()
"""

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""

    warning: float
    critical: float
    unit: str = "ms"


@dataclass
class ComponentHealth:
    """Health status of a component."""

    name: str
    status: HealthStatus
    latency_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabaseHealth:
    """Overall database health report."""

    status: HealthStatus
    timestamp: str
    components: List[ComponentHealth]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "latency_ms": round(c.latency_ms, 2),
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.components
            ],
            "summary": self.summary,
        }


class DatabaseMonitor:
    """
    Database monitoring and health checking.

    Provides comprehensive health checks and metrics for:
    - SQLite database connectivity
    - Table integrity
    - Query performance
    - Archive status
    - Connection pool status
    """

    # Default alert thresholds
    THRESHOLDS = {
        "query_latency": AlertThreshold(warning=50.0, critical=200.0, unit="ms"),
        "connection_time": AlertThreshold(warning=10.0, critical=50.0, unit="ms"),
        "table_size": AlertThreshold(
            warning=1_000_000, critical=10_000_000, unit="rows"
        ),
        "archive_age": AlertThreshold(warning=30, critical=90, unit="days"),
    }

    def __init__(self, db_path: str = "data.sqlite3"):
        """
        Initialize database monitor.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._last_health: Optional[DatabaseHealth] = None
        self._metrics_cache: Dict[str, Any] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 5.0  # seconds

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def check_health(self) -> DatabaseHealth:
        """
        Perform comprehensive health check.

        Returns:
            DatabaseHealth with status of all components
        """
        components: List[ComponentHealth] = []

        # Check database connectivity
        components.append(self._check_connectivity())

        # Check table integrity
        components.append(self._check_table_integrity())

        # Check query performance
        components.append(self._check_query_performance())

        # Check archive status
        components.append(self._check_archive_status())

        # Check database size
        components.append(self._check_database_size())

        # Determine overall status
        statuses = [c.status for c in components]
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        health = DatabaseHealth(
            status=overall_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            components=components,
            summary={
                "total_components": len(components),
                "healthy": sum(
                    1 for c in components if c.status == HealthStatus.HEALTHY
                ),
                "degraded": sum(
                    1 for c in components if c.status == HealthStatus.DEGRADED
                ),
                "unhealthy": sum(
                    1 for c in components if c.status == HealthStatus.UNHEALTHY
                ),
                "db_path": str(self.db_path),
            },
        )

        self._last_health = health
        return health

    def _check_connectivity(self) -> ComponentHealth:
        """Check database connectivity."""
        start = time.perf_counter()
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            conn.close()
            latency = (time.perf_counter() - start) * 1000

            threshold = self.THRESHOLDS["connection_time"]
            if latency > threshold.critical:
                status = HealthStatus.UNHEALTHY
                message = f"Connection time {latency:.1f}ms exceeds critical threshold"
            elif latency > threshold.warning:
                status = HealthStatus.DEGRADED
                message = f"Connection time {latency:.1f}ms exceeds warning threshold"
            else:
                status = HealthStatus.HEALTHY
                message = f"Database connected in {latency:.1f}ms"

            return ComponentHealth(
                name="connectivity",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "threshold_warning": threshold.warning,
                    "threshold_critical": threshold.critical,
                },
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="connectivity",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e}",
            )

    def _check_table_integrity(self) -> ComponentHealth:
        """Check main table integrity."""
        start = time.perf_counter()
        try:
            conn = self._get_connection()

            # Check if main table exists and get row count
            cursor = conn.execute("""
                SELECT COUNT(*) as cnt FROM bybit_kline_audit
            """)
            row_count = cursor.fetchone()["cnt"]

            # Check for any corrupted records (null required fields)
            cursor = conn.execute("""
                SELECT COUNT(*) as corrupted
                FROM bybit_kline_audit
                WHERE symbol IS NULL OR interval IS NULL OR open_time IS NULL
            """)
            corrupted = cursor.fetchone()["corrupted"]

            conn.close()
            latency = (time.perf_counter() - start) * 1000

            if corrupted > 0:
                status = HealthStatus.DEGRADED
                message = f"{corrupted} corrupted records found"
            elif row_count == 0:
                status = HealthStatus.DEGRADED
                message = "Main table is empty"
            else:
                status = HealthStatus.HEALTHY
                message = f"Table integrity OK, {row_count:,} records"

            return ComponentHealth(
                name="table_integrity",
                status=status,
                latency_ms=latency,
                message=message,
                details={"row_count": row_count, "corrupted_records": corrupted},
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="table_integrity",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Integrity check failed: {e}",
            )

    def _check_query_performance(self) -> ComponentHealth:
        """Check typical query performance."""
        start = time.perf_counter()
        try:
            conn = self._get_connection()

            # Run a typical query pattern
            cursor = conn.execute("""
                SELECT open_time, open_price, high_price, low_price, close_price, volume
                FROM bybit_kline_audit
                WHERE symbol = 'BTCUSDT' AND interval = '15'
                ORDER BY open_time DESC
                LIMIT 100
            """)
            rows = cursor.fetchall()

            conn.close()
            latency = (time.perf_counter() - start) * 1000

            threshold = self.THRESHOLDS["query_latency"]
            if latency > threshold.critical:
                status = HealthStatus.UNHEALTHY
                message = f"Query latency {latency:.1f}ms exceeds critical threshold"
            elif latency > threshold.warning:
                status = HealthStatus.DEGRADED
                message = f"Query latency {latency:.1f}ms exceeds warning threshold"
            else:
                status = HealthStatus.HEALTHY
                message = f"Query completed in {latency:.1f}ms, {len(rows)} rows"

            return ComponentHealth(
                name="query_performance",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "rows_returned": len(rows),
                    "threshold_warning": threshold.warning,
                },
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="query_performance",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Query failed: {e}",
            )

    def _check_archive_status(self) -> ComponentHealth:
        """Check archive tables status."""
        start = time.perf_counter()
        try:
            conn = self._get_connection()

            # Get archive tables
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'bybit_kline_archive_%'
                ORDER BY name
            """)
            archive_tables = [row["name"] for row in cursor.fetchall()]

            # Count total archived records
            total_archived = 0
            for table in archive_tables:
                cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                total_archived += cursor.fetchone()["cnt"]

            conn.close()
            latency = (time.perf_counter() - start) * 1000

            if len(archive_tables) == 0:
                status = HealthStatus.HEALTHY
                message = "No archive tables (archiving may not be configured)"
            else:
                status = HealthStatus.HEALTHY
                message = (
                    f"{len(archive_tables)} archive tables, {total_archived:,} records"
                )

            return ComponentHealth(
                name="archive_status",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "archive_tables_count": len(archive_tables),
                    "total_archived_records": total_archived,
                    "tables": archive_tables[:5] if archive_tables else [],  # First 5
                },
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="archive_status",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message=f"Archive check failed: {e}",
            )

    def _check_database_size(self) -> ComponentHealth:
        """Check database file size."""
        start = time.perf_counter()
        try:
            if self.db_path.exists():
                size_bytes = self.db_path.stat().st_size
                size_mb = size_bytes / (1024 * 1024)

                latency = (time.perf_counter() - start) * 1000

                if size_mb > 10000:  # > 10GB
                    status = HealthStatus.DEGRADED
                    message = f"Database size {size_mb:.1f}MB is very large"
                elif size_mb > 1000:  # > 1GB
                    status = HealthStatus.HEALTHY
                    message = f"Database size {size_mb:.1f}MB"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Database size {size_mb:.1f}MB"

                return ComponentHealth(
                    name="database_size",
                    status=status,
                    latency_ms=latency,
                    message=message,
                    details={"size_bytes": size_bytes, "size_mb": round(size_mb, 2)},
                )
            else:
                return ComponentHealth(
                    name="database_size",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0,
                    message="Database file not found",
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="database_size",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message=f"Size check failed: {e}",
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.

        Returns cached metrics if within TTL.
        """
        now = time.time()
        if now - self._cache_time < self._cache_ttl and self._metrics_cache:
            return self._metrics_cache

        metrics = {}

        try:
            conn = self._get_connection()

            # Main table stats
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_records,
                    MIN(open_time) as oldest_time,
                    MAX(open_time) as newest_time,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COUNT(DISTINCT interval) as unique_intervals
                FROM bybit_kline_audit
            """)
            row = cursor.fetchone()
            metrics["main_table"] = {
                "total_records": row["total_records"],
                "oldest_time": row["oldest_time"],
                "newest_time": row["newest_time"],
                "unique_symbols": row["unique_symbols"],
                "unique_intervals": row["unique_intervals"],
            }

            # Archive stats
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE 'bybit_kline_archive_%'
            """)
            archive_tables = [row["name"] for row in cursor.fetchall()]

            total_archived = 0
            for table in archive_tables:
                cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                total_archived += cursor.fetchone()["cnt"]

            metrics["archives"] = {
                "table_count": len(archive_tables),
                "total_records": total_archived,
            }

            # Database size
            if self.db_path.exists():
                metrics["database_size_mb"] = round(
                    self.db_path.stat().st_size / (1024 * 1024), 2
                )

            conn.close()

        except Exception as e:
            metrics["error"] = str(e)

        metrics["timestamp"] = datetime.now(timezone.utc).isoformat()

        self._metrics_cache = metrics
        self._cache_time = now

        return metrics

    def get_metrics_prometheus(self) -> str:
        """
        Get metrics in Prometheus format.

        Returns:
            Prometheus-compatible metrics string
        """
        metrics = self.get_metrics()
        lines = []

        # Database size
        if "database_size_mb" in metrics:
            lines.append("# HELP database_size_mb Database file size in megabytes")
            lines.append("# TYPE database_size_mb gauge")
            lines.append(
                f'database_size_mb{{db="kline"}} {metrics["database_size_mb"]}'
            )

        # Main table records
        if "main_table" in metrics:
            mt = metrics["main_table"]
            lines.append("# HELP kline_main_table_records Total records in main table")
            lines.append("# TYPE kline_main_table_records gauge")
            lines.append(
                f'kline_main_table_records{{table="bybit_kline_audit"}} {mt["total_records"]}'
            )

            lines.append("# HELP kline_unique_symbols Number of unique trading symbols")
            lines.append("# TYPE kline_unique_symbols gauge")
            lines.append(f"kline_unique_symbols {mt['unique_symbols']}")

        # Archive stats
        if "archives" in metrics:
            arch = metrics["archives"]
            lines.append("# HELP kline_archive_tables Number of archive tables")
            lines.append("# TYPE kline_archive_tables gauge")
            lines.append(f"kline_archive_tables {arch['table_count']}")

            lines.append("# HELP kline_archived_records Total archived records")
            lines.append("# TYPE kline_archived_records gauge")
            lines.append(f"kline_archived_records {arch['total_records']}")

        return "\n".join(lines)


# FastAPI router for health endpoints
def create_health_router():
    """Create FastAPI router for health and metrics endpoints."""
    from fastapi import APIRouter, Response

    router = APIRouter(prefix="/health", tags=["health"])
    monitor = DatabaseMonitor()

    @router.get("/")
    async def health_check():
        """Basic health check endpoint."""
        health = monitor.check_health()
        return health.to_dict()

    @router.get("/ready")
    async def readiness_check():
        """Kubernetes readiness probe."""
        health = monitor.check_health()
        if health.status == HealthStatus.UNHEALTHY:
            return Response(
                content='{"status": "unhealthy"}',
                status_code=503,
                media_type="application/json",
            )
        return {"status": "ready"}

    @router.get("/live")
    async def liveness_check():
        """Kubernetes liveness probe."""
        # Simple check - just verify we can respond
        return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

    @router.get("/metrics")
    async def get_metrics():
        """Get metrics as JSON."""
        return monitor.get_metrics()

    @router.get("/metrics/prometheus")
    async def get_prometheus_metrics():
        """Get metrics in Prometheus format."""
        metrics = monitor.get_metrics_prometheus()
        return Response(content=metrics, media_type="text/plain")

    return router


if __name__ == "__main__":
    # Test the monitor
    import json

    monitor = DatabaseMonitor()

    print("=" * 60)
    print("DATABASE HEALTH CHECK")
    print("=" * 60)

    health = monitor.check_health()
    print(json.dumps(health.to_dict(), indent=2))

    print("\n" + "=" * 60)
    print("PROMETHEUS METRICS")
    print("=" * 60)
    print(monitor.get_metrics_prometheus())
