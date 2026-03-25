"""
Comprehensive Health Checks System.

Provides system-wide health monitoring for:
- Database connectivity
- Redis connectivity
- Bybit API status
- Disk space
- Memory usage
- CPU usage

Based on MONITORING_SYSTEM_AUDIT_2026_01_28 recommendations.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import psutil
from loguru import logger


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    message: str
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SystemHealthReport:
    """Aggregated health report for all components."""

    overall_status: HealthStatus
    checks: dict[str, HealthCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_status": self.overall_status.value,
            "checks": {name: check.to_dict() for name, check in self.checks.items()},
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
        }


class HealthChecker:
    """
    Comprehensive health checking system.

    Performs health checks on all critical system components:
    - Database (SQLite/PostgreSQL)
    - Redis
    - Bybit API
    - Disk space
    - Memory
    - CPU
    """

    # Thresholds
    DISK_WARNING_PERCENT = 80
    DISK_CRITICAL_PERCENT = 90
    MEMORY_WARNING_PERCENT = 80
    MEMORY_CRITICAL_PERCENT = 90
    CPU_WARNING_PERCENT = 80
    CPU_CRITICAL_PERCENT = 95

    def __init__(self):
        self._last_check: SystemHealthReport | None = None
        self._cache_ttl: float = 5.0  # seconds
        self._last_check_time: float = 0

    async def check_all(self, force: bool = False) -> SystemHealthReport:
        """
        Run all health checks.

        Args:
            force: If True, bypass cache and run fresh checks

        Returns:
            SystemHealthReport with status of all components
        """
        # Return cached result if within TTL
        if not force and self._last_check and time.time() - self._last_check_time < self._cache_ttl:
            return self._last_check

        # Run all checks in parallel
        checks_coros = [
            self.check_database(),
            self.check_redis(),
            self.check_bybit_api(),
            self.check_disk_space(),
            self.check_memory(),
            self.check_cpu(),
        ]

        results = await asyncio.gather(*checks_coros, return_exceptions=True)

        # Process results
        checks: dict[str, HealthCheckResult] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check exception: {result}")
                continue
            if isinstance(result, HealthCheckResult):
                checks[result.name] = result

        # Determine overall status
        overall_status = self._calculate_overall_status(checks)

        # Build summary
        summary = {
            "total_checks": len(checks),
            "healthy": sum(1 for c in checks.values() if c.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for c in checks.values() if c.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for c in checks.values() if c.status == HealthStatus.UNHEALTHY),
        }

        report = SystemHealthReport(
            overall_status=overall_status,
            checks=checks,
            summary=summary,
        )

        # Cache result
        self._last_check = report
        self._last_check_time = time.time()

        return report

    def _calculate_overall_status(self, checks: dict[str, HealthCheckResult]) -> HealthStatus:
        """Calculate overall status from individual checks."""
        if not checks:
            return HealthStatus.UNHEALTHY

        # Critical components that must be healthy
        critical_components = {"database", "redis"}

        for name in critical_components:
            if name in checks and checks[name].status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Check for any unhealthy
        if any(c.status == HealthStatus.UNHEALTHY for c in checks.values()):
            return HealthStatus.UNHEALTHY

        # Check for any degraded
        if any(c.status == HealthStatus.DEGRADED for c in checks.values()):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    async def check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        start = time.time()
        try:
            from sqlalchemy import text

            from backend.database import engine

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connected",
                latency_ms=latency,
                details={"type": "sqlite", "query": "SELECT 1"},
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Database health check failed: {e}")
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
                latency_ms=latency,
                details={"error": str(e), "error_type": type(e).__name__},
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        start = time.time()
        try:
            import redis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url, socket_timeout=5)
            r.ping()

            latency = (time.time() - start) * 1000

            # Get Redis info
            info = r.info("memory")
            used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)

            return HealthCheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connected",
                latency_ms=latency,
                details={
                    "used_memory_mb": round(used_memory_mb, 2),
                    "redis_version": info.get("redis_version", "unknown"),
                },
            )
        except redis.ConnectionError as e:
            latency = (time.time() - start) * 1000
            logger.warning(f"Redis not available: {e}")
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message=f"Redis unavailable: {e!s}",
                latency_ms=latency,
                details={"error": str(e)},
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Redis health check failed: {e}")
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message=f"Redis check failed: {e!s}",
                latency_ms=latency,
                details={"error": str(e), "error_type": type(e).__name__},
            )

    async def check_bybit_api(self) -> HealthCheckResult:
        """Check Bybit API connectivity."""
        start = time.time()
        try:
            from backend.services.adapters.bybit import BybitAdapter

            adapter = BybitAdapter()
            candles = adapter.get_klines("BTCUSDT", "1", 5)

            latency = (time.time() - start) * 1000

            if candles and len(candles) > 0:
                latest_price = float(candles[-1].get("close", 0))
                return HealthCheckResult(
                    name="bybit_api",
                    status=HealthStatus.HEALTHY,
                    message="Bybit API connected",
                    latency_ms=latency,
                    details={
                        "candles_fetched": len(candles),
                        "latest_btc_price": latest_price,
                    },
                )
            else:
                return HealthCheckResult(
                    name="bybit_api",
                    status=HealthStatus.DEGRADED,
                    message="Bybit API returned no data",
                    latency_ms=latency,
                    details={"candles_fetched": 0},
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Bybit API health check failed: {e}")
            return HealthCheckResult(
                name="bybit_api",
                status=HealthStatus.UNHEALTHY,
                message=f"Bybit API error: {e!s}",
                latency_ms=latency,
                details={"error": str(e), "error_type": type(e).__name__},
            )

    async def check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage."""
        try:
            disk = psutil.disk_usage("/")
            percent_used = disk.percent
            free_gb = disk.free / (1024**3)
            total_gb = disk.total / (1024**3)

            if percent_used >= self.DISK_CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
                message = f"Disk critically full: {percent_used}% used"
            elif percent_used >= self.DISK_WARNING_PERCENT:
                status = HealthStatus.DEGRADED
                message = f"Disk space low: {percent_used}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {percent_used}% used"

            return HealthCheckResult(
                name="disk",
                status=status,
                message=message,
                details={
                    "percent_used": percent_used,
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                },
            )
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.DEGRADED,
                message=f"Disk check failed: {e!s}",
                details={"error": str(e)},
            )

    async def check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            mem = psutil.virtual_memory()
            percent_used = mem.percent
            available_gb = mem.available / (1024**3)
            total_gb = mem.total / (1024**3)

            if percent_used >= self.MEMORY_CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
                message = f"Memory critically high: {percent_used}% used"
            elif percent_used >= self.MEMORY_WARNING_PERCENT:
                status = HealthStatus.DEGRADED
                message = f"Memory usage high: {percent_used}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory OK: {percent_used}% used"

            return HealthCheckResult(
                name="memory",
                status=status,
                message=message,
                details={
                    "percent_used": percent_used,
                    "available_gb": round(available_gb, 2),
                    "total_gb": round(total_gb, 2),
                },
            )
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.DEGRADED,
                message=f"Memory check failed: {e!s}",
                details={"error": str(e)},
            )

    async def check_cpu(self) -> HealthCheckResult:
        """Check CPU usage."""
        try:
            # Get CPU percent with a small interval for accuracy
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

            if cpu_percent >= self.CPU_CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
                message = f"CPU critically high: {cpu_percent}%"
            elif cpu_percent >= self.CPU_WARNING_PERCENT:
                status = HealthStatus.DEGRADED
                message = f"CPU usage high: {cpu_percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU OK: {cpu_percent}%"

            return HealthCheckResult(
                name="cpu",
                status=status,
                message=message,
                details={
                    "percent_used": cpu_percent,
                    "cpu_count": cpu_count,
                    "load_avg_1m": round(load_avg[0], 2),
                    "load_avg_5m": round(load_avg[1], 2),
                    "load_avg_15m": round(load_avg[2], 2),
                },
            )
        except Exception as e:
            logger.error(f"CPU check failed: {e}")
            return HealthCheckResult(
                name="cpu",
                status=HealthStatus.DEGRADED,
                message=f"CPU check failed: {e!s}",
                details={"error": str(e)},
            )


# Global instance
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """Get or create global HealthChecker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


async def run_health_check() -> SystemHealthReport:
    """Convenience function to run all health checks."""
    checker = get_health_checker()
    return await checker.check_all()
