"""
Database Connection Pool Monitor

Monitors SQLAlchemy connection pool health, provides statistics,
and detects potential connection leaks.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, event, text
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


class ConnectionPoolMonitor:
    """
    Monitors database connection pool health and performance.

    Features:
    - Real-time pool statistics
    - Connection leak detection
    - Health recommendations
    - Performance metrics
    """

    def __init__(self, engine: Engine):
        """Initialize the pool monitor with an SQLAlchemy engine."""
        self.engine = engine
        self._pool: Pool | None = engine.pool if hasattr(engine, "pool") else None
        self._connection_times: dict[int, float] = {}
        self._checkout_count = 0
        self._checkin_count = 0
        self._overflow_count = 0
        self._timeout_count = 0
        self._initialized_at = datetime.now(UTC)

        # Register event listeners
        self._register_events()

    def _register_events(self):
        """Register SQLAlchemy pool event listeners."""
        if self._pool is None:
            return

        @event.listens_for(self._pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout."""
            self._checkout_count += 1
            conn_id = id(dbapi_conn)
            self._connection_times[conn_id] = time.time()
            logger.debug(f"Connection {conn_id} checked out")

        @event.listens_for(self._pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Track connection checkin."""
            self._checkin_count += 1
            conn_id = id(dbapi_conn)
            if conn_id in self._connection_times:
                duration = time.time() - self._connection_times[conn_id]
                del self._connection_times[conn_id]
                if duration > 30:  # Log slow connections
                    logger.warning(f"Connection {conn_id} held for {duration:.2f}s")
            logger.debug(f"Connection {conn_id} checked in")

    def get_pool_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive pool statistics.

        Returns:
            Dictionary with pool metrics and health status
        """
        if self._pool is None:
            return self._get_no_pool_stats()

        try:
            pool = self._pool

            # Basic pool info
            size = (
                pool.size()
                if hasattr(pool, "size") and callable(pool.size)
                else getattr(pool, "_pool", {}).get("size", 5)
            )
            checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
            checked_in = pool.checkedin() if hasattr(pool, "checkedin") else 0
            overflow = pool.overflow() if hasattr(pool, "overflow") else 0

            # For StaticPool (SQLite in-memory), provide sensible defaults
            if not hasattr(pool, "size") or not callable(pool.size):
                size = 1
                checked_out = len(self._connection_times)
                checked_in = 1 - checked_out
                overflow = 0

            # Calculate utilization
            total_capacity = size + getattr(pool, "_max_overflow", 0)
            utilization = (
                (checked_out / total_capacity * 100) if total_capacity > 0 else 0
            )

            # Determine health status
            if utilization >= 90:
                health = "critical"
            elif utilization >= 70:
                health = "warning"
            else:
                health = "healthy"

            return {
                "size": size,
                "checked_out": checked_out,
                "checked_in": checked_in,
                "overflow": overflow,
                "max_overflow": getattr(pool, "_max_overflow", 0),
                "utilization": round(utilization, 2),
                "health": health,
                "timeout": getattr(pool, "_timeout", 30),
                "recycle": getattr(pool, "_recycle", -1),
                "pre_ping": getattr(pool, "_pre_ping", False),
                "total_checkouts": self._checkout_count,
                "total_checkins": self._checkin_count,
                "active_connections": len(self._connection_times),
                "uptime_seconds": (
                    datetime.now(UTC) - self._initialized_at
                ).total_seconds(),
            }

        except Exception as e:
            logger.error(f"Error getting pool statistics: {e}")
            return self._get_error_stats(str(e))

    def _get_no_pool_stats(self) -> dict[str, Any]:
        """Return stats when no pool is available (e.g., SQLite)."""
        return {
            "size": 1,
            "checked_out": 0,
            "checked_in": 1,
            "overflow": 0,
            "max_overflow": 0,
            "utilization": 0.0,
            "health": "healthy",
            "timeout": 30,
            "recycle": -1,
            "pre_ping": False,
            "total_checkouts": self._checkout_count,
            "total_checkins": self._checkin_count,
            "active_connections": len(self._connection_times),
            "uptime_seconds": (
                datetime.now(UTC) - self._initialized_at
            ).total_seconds(),
            "note": "Using SQLite or StaticPool - limited pool statistics available",
        }

    def _get_error_stats(self, error: str) -> dict[str, Any]:
        """Return stats when an error occurs."""
        return {
            "size": 0,
            "checked_out": 0,
            "checked_in": 0,
            "overflow": 0,
            "max_overflow": 0,
            "utilization": 0.0,
            "health": "unknown",
            "error": error,
            "timeout": 0,
            "recycle": 0,
            "pre_ping": False,
        }

    def get_recommendations(self) -> list[str]:
        """
        Generate health recommendations based on current pool state.

        Returns:
            List of recommendation strings
        """
        recommendations = []
        stats = self.get_pool_statistics()

        if stats.get("health") == "critical":
            recommendations.append(
                "CRITICAL: Pool utilization is very high. Consider increasing pool size."
            )

        if stats.get("utilization", 0) > 50:
            recommendations.append(
                f"Pool utilization at {stats['utilization']}%. Monitor for potential bottlenecks."
            )

        active = stats.get("active_connections", 0)
        if active > 5:
            recommendations.append(
                f"{active} connections currently active. Check for connection leaks."
            )

        # Check for long-held connections
        long_held = sum(
            1 for t in self._connection_times.values() if time.time() - t > 60
        )
        if long_held > 0:
            recommendations.append(
                f"{long_held} connection(s) held for over 60 seconds. Possible leak detected."
            )

        if stats.get("recycle", -1) == -1:
            recommendations.append(
                "Connection recycling is disabled. Consider enabling for long-running apps."
            )

        if not stats.get("pre_ping", False):
            recommendations.append(
                "Pre-ping is disabled. Enable to detect stale connections."
            )

        if not recommendations:
            recommendations.append("Pool is healthy. No immediate actions required.")

        return recommendations

    def check_connection_leaks(self) -> dict[str, Any]:
        """
        Check for potential connection leaks.

        Returns:
            Dictionary with leak detection results
        """
        current_time = time.time()
        leaks = []

        for conn_id, checkout_time in list(self._connection_times.items()):
            duration = current_time - checkout_time
            if duration > 120:  # 2 minutes threshold
                leaks.append(
                    {
                        "connection_id": conn_id,
                        "duration_seconds": round(duration, 2),
                        "severity": "high" if duration > 300 else "medium",
                    }
                )

        return {
            "leak_detected": len(leaks) > 0,
            "potential_leaks": leaks,
            "threshold_seconds": 120,
            "total_active": len(self._connection_times),
        }

    def get_connection_summary(self) -> dict[str, Any]:
        """Get a summary of connection activity."""
        return {
            "total_checkouts": self._checkout_count,
            "total_checkins": self._checkin_count,
            "delta": self._checkout_count - self._checkin_count,
            "currently_active": len(self._connection_times),
            "timeout_events": self._timeout_count,
            "monitoring_since": self._initialized_at.isoformat() + "Z",
        }

    def test_connection(self) -> dict[str, Any]:
        """Test database connectivity."""
        start = time.time()
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            return {
                "success": True,
                "latency_ms": round(latency, 2),
                "timestamp": datetime.now(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            }


# Singleton instance for global access
_monitor_instance: ConnectionPoolMonitor | None = None


def get_pool_monitor(engine: Engine | None = None) -> ConnectionPoolMonitor:
    """
    Get or create the global pool monitor instance.

    Args:
        engine: SQLAlchemy engine (required on first call)

    Returns:
        ConnectionPoolMonitor instance
    """
    global _monitor_instance

    if _monitor_instance is None:
        if engine is None:
            from backend.database import engine as default_engine

            engine = default_engine
        _monitor_instance = ConnectionPoolMonitor(engine)

    return _monitor_instance


__all__ = ["ConnectionPoolMonitor", "get_pool_monitor"]
