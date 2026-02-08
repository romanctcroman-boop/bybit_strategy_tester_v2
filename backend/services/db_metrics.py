"""
Database Query Metrics Service.

Provides comprehensive database performance monitoring with:
- Query timing and duration tracking
- Slow query detection and logging
- Connection pool metrics
- Query pattern analysis
- Performance recommendations
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of database queries."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRANSACTION = "TRANSACTION"
    OTHER = "OTHER"


class QueryStatus(str, Enum):
    """Query execution status."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class QueryMetric:
    """Metrics for a single query execution."""

    query_id: str
    query_type: QueryType
    table: str | None
    duration_ms: float
    status: QueryStatus
    timestamp: datetime
    rows_affected: int = 0
    rows_returned: int = 0
    error_message: str | None = None
    query_hash: str | None = None
    caller: str | None = None


@dataclass
class QueryPattern:
    """Statistics for a query pattern."""

    query_hash: str
    sample_query: str
    query_type: QueryType
    table: str | None
    execution_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    error_count: int = 0
    last_executed: datetime | None = None


@dataclass
class PoolMetrics:
    """Connection pool metrics."""

    pool_size: int
    active_connections: int
    idle_connections: int
    waiting_requests: int
    max_connections: int
    connection_timeouts: int = 0
    total_connections_created: int = 0
    total_connections_closed: int = 0


@dataclass
class SlowQueryConfig:
    """Configuration for slow query detection."""

    slow_query_threshold_ms: float = 100.0  # Queries slower than this are slow
    very_slow_query_threshold_ms: float = 1000.0  # Very slow queries
    log_slow_queries: bool = True
    alert_on_very_slow: bool = True
    max_slow_queries_stored: int = 100


class DatabaseMetricsService:
    """
    Database Query Metrics Service.

    Features:
    - Query execution timing
    - Slow query detection and logging
    - Query pattern analysis
    - Connection pool monitoring
    - Performance recommendations
    """

    def __init__(self, config: SlowQueryConfig | None = None):
        self._config = config or SlowQueryConfig()
        self._query_metrics: list[QueryMetric] = []
        self._query_patterns: dict[str, QueryPattern] = {}
        self._slow_queries: list[QueryMetric] = []
        self._pool_metrics = PoolMetrics(
            pool_size=0,
            active_connections=0,
            idle_connections=0,
            waiting_requests=0,
            max_connections=20,
        )
        self._stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "slow_queries": 0,
            "very_slow_queries": 0,
        }
        self._query_counter = 0
        self._initialized = False
        self._type_stats: dict[str, int] = defaultdict(int)
        self._table_stats: dict[str, int] = defaultdict(int)
        self._initialized = True
        logger.info("✅ Database Metrics Service initialized")

    # ============================================================
    # Query Timing
    # ============================================================

    def start_query_timer(self) -> float:
        """Start timing a query. Returns start time."""
        return time.time()

    def record_query(
        self,
        start_time: float,
        query_type: QueryType,
        table: str | None = None,
        status: QueryStatus = QueryStatus.SUCCESS,
        rows_affected: int = 0,
        rows_returned: int = 0,
        error_message: str | None = None,
        query_hash: str | None = None,
        caller: str | None = None,
        sample_query: str | None = None,
    ) -> QueryMetric:
        """
        Record query execution metrics.

        Args:
            start_time: Query start time from start_query_timer()
            query_type: Type of query
            table: Target table name
            status: Execution status
            rows_affected: Number of rows affected
            rows_returned: Number of rows returned
            error_message: Error message if failed
            query_hash: Hash for query pattern tracking
            caller: Calling function/module
            sample_query: Sample query for pattern tracking

        Returns:
            QueryMetric record
        """
        duration_ms = (time.time() - start_time) * 1000
        self._query_counter += 1

        metric = QueryMetric(
            query_id=f"Q-{self._query_counter:08d}",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            status=status,
            timestamp=datetime.now(UTC),
            rows_affected=rows_affected,
            rows_returned=rows_returned,
            error_message=error_message,
            query_hash=query_hash,
            caller=caller,
        )

        # Update stats
        self._stats["total_queries"] += 1
        self._type_stats[query_type.value] += 1
        if table:
            self._table_stats[table] += 1

        if status == QueryStatus.SUCCESS:
            self._stats["successful_queries"] += 1
        else:
            self._stats["failed_queries"] += 1

        # Check for slow query
        is_slow = duration_ms >= self._config.slow_query_threshold_ms
        is_very_slow = duration_ms >= self._config.very_slow_query_threshold_ms

        if is_slow:
            self._stats["slow_queries"] += 1
            self._slow_queries.append(metric)

            # Trim slow queries list
            if len(self._slow_queries) > self._config.max_slow_queries_stored:
                self._slow_queries = self._slow_queries[
                    -self._config.max_slow_queries_stored :
                ]

            if self._config.log_slow_queries:
                log_msg = (
                    f"🐢 Slow query detected: {query_type.value} on {table or 'unknown'} "
                    f"took {duration_ms:.2f}ms"
                )
                if is_very_slow:
                    logger.warning(log_msg)
                    self._stats["very_slow_queries"] += 1
                else:
                    logger.info(log_msg)

        # Update query pattern
        if query_hash and sample_query:
            self._update_pattern(
                query_hash=query_hash,
                sample_query=sample_query,
                query_type=query_type,
                table=table,
                duration_ms=duration_ms,
                is_error=status != QueryStatus.SUCCESS,
            )

        # Store metric (keep last 1000)
        self._query_metrics.append(metric)
        if len(self._query_metrics) > 1000:
            self._query_metrics = self._query_metrics[-1000:]

        return metric

    def _update_pattern(
        self,
        query_hash: str,
        sample_query: str,
        query_type: QueryType,
        table: str | None,
        duration_ms: float,
        is_error: bool,
    ) -> None:
        """Update query pattern statistics."""
        if query_hash not in self._query_patterns:
            self._query_patterns[query_hash] = QueryPattern(
                query_hash=query_hash,
                sample_query=sample_query[:500],  # Limit size
                query_type=query_type,
                table=table,
            )

        pattern = self._query_patterns[query_hash]
        pattern.execution_count += 1
        pattern.total_duration_ms += duration_ms
        pattern.min_duration_ms = min(pattern.min_duration_ms, duration_ms)
        pattern.max_duration_ms = max(pattern.max_duration_ms, duration_ms)
        pattern.avg_duration_ms = pattern.total_duration_ms / pattern.execution_count
        pattern.last_executed = datetime.now(UTC)

        if is_error:
            pattern.error_count += 1

    # ============================================================
    # Query Timing Context Manager
    # ============================================================

    class QueryTimer:
        """Context manager for timing queries."""

        def __init__(
            self,
            service: "DatabaseMetricsService",
            query_type: QueryType,
            table: str | None = None,
            query_hash: str | None = None,
            sample_query: str | None = None,
            caller: str | None = None,
        ):
            self.service = service
            self.query_type = query_type
            self.table = table
            self.query_hash = query_hash
            self.sample_query = sample_query
            self.caller = caller
            self.start_time: float = 0
            self.rows_affected = 0
            self.rows_returned = 0
            self.status = QueryStatus.SUCCESS
            self.error_message: str | None = None

        def __enter__(self) -> "DatabaseMetricsService.QueryTimer":
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            if exc_type:
                self.status = QueryStatus.ERROR
                self.error_message = str(exc_val) if exc_val else None

            self.service.record_query(
                start_time=self.start_time,
                query_type=self.query_type,
                table=self.table,
                status=self.status,
                rows_affected=self.rows_affected,
                rows_returned=self.rows_returned,
                error_message=self.error_message,
                query_hash=self.query_hash,
                caller=self.caller,
                sample_query=self.sample_query,
            )

    def time_query(
        self,
        query_type: QueryType,
        table: str | None = None,
        query_hash: str | None = None,
        sample_query: str | None = None,
        caller: str | None = None,
    ) -> "DatabaseMetricsService.QueryTimer":
        """
        Get a context manager for timing a query.

        Usage:
            with metrics.time_query(QueryType.SELECT, "users") as timer:
                result = db.execute("SELECT * FROM users")
                timer.rows_returned = len(result)
        """
        return self.QueryTimer(
            service=self,
            query_type=query_type,
            table=table,
            query_hash=query_hash,
            sample_query=sample_query,
            caller=caller,
        )

    # ============================================================
    # Connection Pool Metrics
    # ============================================================

    def update_pool_metrics(
        self,
        pool_size: int | None = None,
        active_connections: int | None = None,
        idle_connections: int | None = None,
        waiting_requests: int | None = None,
        max_connections: int | None = None,
    ) -> None:
        """Update connection pool metrics."""
        if pool_size is not None:
            self._pool_metrics.pool_size = pool_size
        if active_connections is not None:
            self._pool_metrics.active_connections = active_connections
        if idle_connections is not None:
            self._pool_metrics.idle_connections = idle_connections
        if waiting_requests is not None:
            self._pool_metrics.waiting_requests = waiting_requests
        if max_connections is not None:
            self._pool_metrics.max_connections = max_connections

    def record_connection_event(
        self,
        event_type: str,  # "created", "closed", "timeout"
    ) -> None:
        """Record a connection pool event."""
        if event_type == "created":
            self._pool_metrics.total_connections_created += 1
        elif event_type == "closed":
            self._pool_metrics.total_connections_closed += 1
        elif event_type == "timeout":
            self._pool_metrics.connection_timeouts += 1

    def get_pool_metrics(self) -> dict:
        """Get connection pool metrics."""
        return {
            "pool_size": self._pool_metrics.pool_size,
            "active_connections": self._pool_metrics.active_connections,
            "idle_connections": self._pool_metrics.idle_connections,
            "waiting_requests": self._pool_metrics.waiting_requests,
            "max_connections": self._pool_metrics.max_connections,
            "utilization_pct": (
                (
                    self._pool_metrics.active_connections
                    / self._pool_metrics.max_connections
                )
                * 100
                if self._pool_metrics.max_connections > 0
                else 0
            ),
            "total_connections_created": self._pool_metrics.total_connections_created,
            "total_connections_closed": self._pool_metrics.total_connections_closed,
            "connection_timeouts": self._pool_metrics.connection_timeouts,
        }

    # ============================================================
    # Query Analysis
    # ============================================================

    def get_slow_queries(
        self,
        limit: int = 50,
        min_duration_ms: float | None = None,
    ) -> list[dict]:
        """Get recent slow queries."""
        queries = self._slow_queries
        if min_duration_ms:
            queries = [q for q in queries if q.duration_ms >= min_duration_ms]

        return [
            {
                "query_id": q.query_id,
                "query_type": q.query_type.value,
                "table": q.table,
                "duration_ms": q.duration_ms,
                "status": q.status.value,
                "timestamp": q.timestamp.isoformat(),
                "rows_affected": q.rows_affected,
                "rows_returned": q.rows_returned,
                "caller": q.caller,
            }
            for q in queries[-limit:]
        ]

    def get_query_patterns(
        self,
        order_by: str = "execution_count",  # or "avg_duration_ms", "total_duration_ms"
        limit: int = 20,
    ) -> list[dict]:
        """Get query patterns sorted by specified metric."""
        patterns = list(self._query_patterns.values())

        if order_by == "avg_duration_ms":
            patterns.sort(key=lambda p: p.avg_duration_ms, reverse=True)
        elif order_by == "total_duration_ms":
            patterns.sort(key=lambda p: p.total_duration_ms, reverse=True)
        else:
            patterns.sort(key=lambda p: p.execution_count, reverse=True)

        return [
            {
                "query_hash": p.query_hash,
                "sample_query": p.sample_query,
                "query_type": p.query_type.value,
                "table": p.table,
                "execution_count": p.execution_count,
                "avg_duration_ms": round(p.avg_duration_ms, 2),
                "min_duration_ms": round(p.min_duration_ms, 2),
                "max_duration_ms": round(p.max_duration_ms, 2),
                "total_duration_ms": round(p.total_duration_ms, 2),
                "error_count": p.error_count,
                "error_rate_pct": round(
                    (p.error_count / p.execution_count) * 100
                    if p.execution_count > 0
                    else 0,
                    2,
                ),
                "last_executed": p.last_executed.isoformat()
                if p.last_executed
                else None,
            }
            for p in patterns[:limit]
        ]

    def get_table_stats(self) -> dict[str, int]:
        """Get query counts by table."""
        return dict(self._table_stats)

    def get_type_stats(self) -> dict[str, int]:
        """Get query counts by type."""
        return dict(self._type_stats)

    # ============================================================
    # Performance Recommendations
    # ============================================================

    def get_recommendations(self) -> list[dict]:
        """Get performance recommendations based on metrics."""
        recommendations = []

        # Check for high slow query rate
        if self._stats["total_queries"] > 100:
            slow_rate = (
                self._stats["slow_queries"] / self._stats["total_queries"]
            ) * 100
            if slow_rate > 10:
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "slow_queries",
                        "message": f"High slow query rate: {slow_rate:.1f}% of queries are slow",
                        "suggestion": "Review slow queries and add indexes or optimize queries",
                    }
                )

        # Check for very slow queries
        if self._stats["very_slow_queries"] > 0:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "very_slow_queries",
                    "message": f"Found {self._stats['very_slow_queries']} very slow queries (>{self._config.very_slow_query_threshold_ms}ms)",
                    "suggestion": "Investigate and optimize these queries immediately",
                }
            )

        # Check connection pool utilization
        pool = self._pool_metrics
        if pool.max_connections > 0:
            utilization = (pool.active_connections / pool.max_connections) * 100
            if utilization > 80:
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "pool_utilization",
                        "message": f"High connection pool utilization: {utilization:.1f}%",
                        "suggestion": "Consider increasing max_connections or optimizing query patterns",
                    }
                )

        # Check for connection timeouts
        if pool.connection_timeouts > 10:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "connection_timeouts",
                    "message": f"High connection timeouts: {pool.connection_timeouts}",
                    "suggestion": "Increase pool size or reduce query duration",
                }
            )

        # Check for high error rate
        if self._stats["total_queries"] > 50:
            error_rate = (
                self._stats["failed_queries"] / self._stats["total_queries"]
            ) * 100
            if error_rate > 5:
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "error_rate",
                        "message": f"High query error rate: {error_rate:.1f}%",
                        "suggestion": "Review error logs and fix failing queries",
                    }
                )

        # Check for frequently executed slow patterns
        slow_patterns = [
            p
            for p in self._query_patterns.values()
            if p.avg_duration_ms > self._config.slow_query_threshold_ms
            and p.execution_count > 10
        ]
        if slow_patterns:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "slow_patterns",
                    "message": f"Found {len(slow_patterns)} frequently executed slow query patterns",
                    "suggestion": "Optimize these common slow queries for maximum impact",
                }
            )

        return recommendations

    # ============================================================
    # Status & Reporting
    # ============================================================

    def get_stats(self) -> dict:
        """Get query statistics."""
        avg_duration = 0.0
        if self._query_metrics:
            avg_duration = sum(q.duration_ms for q in self._query_metrics) / len(
                self._query_metrics
            )

        return {
            "total_queries": self._stats["total_queries"],
            "successful_queries": self._stats["successful_queries"],
            "failed_queries": self._stats["failed_queries"],
            "slow_queries": self._stats["slow_queries"],
            "very_slow_queries": self._stats["very_slow_queries"],
            "success_rate_pct": (
                (self._stats["successful_queries"] / self._stats["total_queries"]) * 100
                if self._stats["total_queries"] > 0
                else 100
            ),
            "slow_query_rate_pct": (
                (self._stats["slow_queries"] / self._stats["total_queries"]) * 100
                if self._stats["total_queries"] > 0
                else 0
            ),
            "avg_duration_ms": round(avg_duration, 2),
            "query_patterns_count": len(self._query_patterns),
        }

    def get_status(self) -> dict:
        """Get service status."""
        stats = self.get_stats()
        pool = self.get_pool_metrics()
        recommendations = self.get_recommendations()

        return {
            "initialized": self._initialized,
            "stats": stats,
            "pool": pool,
            "config": {
                "slow_query_threshold_ms": self._config.slow_query_threshold_ms,
                "very_slow_query_threshold_ms": self._config.very_slow_query_threshold_ms,
                "log_slow_queries": self._config.log_slow_queries,
            },
            "recommendations_count": len(recommendations),
            "health": "healthy" if len(recommendations) == 0 else "needs_attention",
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._query_metrics.clear()
        self._query_patterns.clear()
        self._slow_queries.clear()
        self._stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "slow_queries": 0,
            "very_slow_queries": 0,
        }
        self._type_stats.clear()
        self._table_stats.clear()
        logger.info("📊 Database metrics reset")


# Singleton instance
_db_metrics_service: DatabaseMetricsService | None = None


def get_db_metrics_service() -> DatabaseMetricsService:
    """Get or create database metrics service instance."""
    global _db_metrics_service
    if _db_metrics_service is None:
        _db_metrics_service = DatabaseMetricsService()
        logger.info("📈 Database Metrics Service initialized")
    return _db_metrics_service
