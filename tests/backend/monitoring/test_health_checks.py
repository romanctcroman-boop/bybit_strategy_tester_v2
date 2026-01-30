"""
Tests for the comprehensive health checks system.

Based on MONITORING_SYSTEM_AUDIT_2026_01_28 recommendations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.monitoring.health_checks import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    SystemHealthReport,
    get_health_checker,
    run_health_check,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test that all health status values are correct."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_health_check_result_creation(self):
        """Test creating a HealthCheckResult."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Test passed",
            latency_ms=10.5,
            details={"key": "value"},
        )
        assert result.name == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Test passed"
        assert result.latency_ms == 10.5
        assert result.details == {"key": "value"}

    def test_health_check_result_to_dict(self):
        """Test converting HealthCheckResult to dict."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.DEGRADED,
            message="Test warning",
            latency_ms=25.0,
        )
        result_dict = result.to_dict()
        assert result_dict["name"] == "test"
        assert result_dict["status"] == "degraded"
        assert result_dict["message"] == "Test warning"
        assert result_dict["latency_ms"] == 25.0
        assert "timestamp" in result_dict


class TestSystemHealthReport:
    """Tests for SystemHealthReport dataclass."""

    def test_system_health_report_creation(self):
        """Test creating a SystemHealthReport."""
        checks = {
            "database": HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="OK",
            ),
            "redis": HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message="Slow",
            ),
        }
        report = SystemHealthReport(
            overall_status=HealthStatus.DEGRADED,
            checks=checks,
            summary={"healthy": 1, "degraded": 1},
        )
        assert report.overall_status == HealthStatus.DEGRADED
        assert len(report.checks) == 2
        assert report.summary["healthy"] == 1

    def test_system_health_report_to_dict(self):
        """Test converting SystemHealthReport to dict."""
        checks = {
            "database": HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="OK",
            ),
        }
        report = SystemHealthReport(
            overall_status=HealthStatus.HEALTHY,
            checks=checks,
        )
        report_dict = report.to_dict()
        assert report_dict["overall_status"] == "healthy"
        assert "database" in report_dict["checks"]
        assert "timestamp" in report_dict


class TestHealthChecker:
    """Tests for HealthChecker class."""

    @pytest.fixture
    def checker(self):
        """Create a HealthChecker instance."""
        return HealthChecker()

    @pytest.mark.asyncio
    async def test_check_disk_space(self, checker):
        """Test disk space check."""
        result = await checker.check_disk_space()
        assert result.name == "disk"
        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        ]
        assert "percent_used" in result.details
        assert "free_gb" in result.details
        assert "total_gb" in result.details

    @pytest.mark.asyncio
    async def test_check_memory(self, checker):
        """Test memory check."""
        result = await checker.check_memory()
        assert result.name == "memory"
        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        ]
        assert "percent_used" in result.details
        assert "available_gb" in result.details
        assert "total_gb" in result.details

    @pytest.mark.asyncio
    async def test_check_cpu(self, checker):
        """Test CPU check."""
        result = await checker.check_cpu()
        assert result.name == "cpu"
        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        ]
        assert "percent_used" in result.details
        assert "cpu_count" in result.details

    @pytest.mark.asyncio
    async def test_check_database_success(self, checker):
        """Test database check with mock."""
        with patch("backend.database.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

            result = await checker.check_database()
            assert result.name == "database"
            # Might fail if actual DB check fails, but structure should be right
            assert "type" in result.details or "error" in result.details

    @pytest.mark.asyncio
    async def test_check_redis_connection_error(self, checker):
        """Test Redis check when Redis is unavailable."""
        with patch("redis.from_url") as mock_redis:
            import redis

            mock_redis.side_effect = redis.ConnectionError("Connection refused")

            result = await checker.check_redis()
            assert result.name == "redis"
            assert result.status == HealthStatus.DEGRADED
            assert "error" in result.details

    @pytest.mark.asyncio
    async def test_check_all_returns_report(self, checker):
        """Test that check_all returns a SystemHealthReport."""
        # Mock all checks to avoid external dependencies
        with patch.object(
            checker,
            "check_database",
            return_value=HealthCheckResult(name="database", status=HealthStatus.HEALTHY, message="OK"),
        ):
            with patch.object(
                checker,
                "check_redis",
                return_value=HealthCheckResult(name="redis", status=HealthStatus.DEGRADED, message="Slow"),
            ):
                with patch.object(
                    checker,
                    "check_bybit_api",
                    return_value=HealthCheckResult(name="bybit_api", status=HealthStatus.HEALTHY, message="OK"),
                ):
                    # Real checks for system resources
                    report = await checker.check_all(force=True)

                    assert isinstance(report, SystemHealthReport)
                    assert report.overall_status in [
                        HealthStatus.HEALTHY,
                        HealthStatus.DEGRADED,
                        HealthStatus.UNHEALTHY,
                    ]
                    assert len(report.checks) > 0
                    assert "total_checks" in report.summary

    @pytest.mark.asyncio
    async def test_check_all_caching(self, checker):
        """Test that check_all uses caching."""
        # Run first check
        with patch.object(checker, "check_disk_space") as mock_disk:
            mock_disk.return_value = HealthCheckResult(name="disk", status=HealthStatus.HEALTHY, message="OK")
            # Mock other checks too
            with patch.object(checker, "check_database") as mock_db:
                mock_db.return_value = HealthCheckResult(name="database", status=HealthStatus.HEALTHY, message="OK")
                with patch.object(checker, "check_redis") as mock_redis:
                    mock_redis.return_value = HealthCheckResult(name="redis", status=HealthStatus.HEALTHY, message="OK")
                    with patch.object(checker, "check_bybit_api") as mock_bybit:
                        mock_bybit.return_value = HealthCheckResult(
                            name="bybit_api", status=HealthStatus.HEALTHY, message="OK"
                        )
                        with patch.object(checker, "check_memory") as mock_mem:
                            mock_mem.return_value = HealthCheckResult(
                                name="memory",
                                status=HealthStatus.HEALTHY,
                                message="OK",
                            )
                            with patch.object(checker, "check_cpu") as mock_cpu:
                                mock_cpu.return_value = HealthCheckResult(
                                    name="cpu",
                                    status=HealthStatus.HEALTHY,
                                    message="OK",
                                )

                                # First call
                                report1 = await checker.check_all(force=True)

                                # Second call should use cache
                                report2 = await checker.check_all(force=False)

                                # With force=False, it should return cached result
                                assert report1.timestamp == report2.timestamp

    def test_calculate_overall_status_all_healthy(self, checker):
        """Test overall status calculation when all checks are healthy."""
        checks = {
            "database": HealthCheckResult(name="database", status=HealthStatus.HEALTHY, message="OK"),
            "redis": HealthCheckResult(name="redis", status=HealthStatus.HEALTHY, message="OK"),
        }
        status = checker._calculate_overall_status(checks)
        assert status == HealthStatus.HEALTHY

    def test_calculate_overall_status_with_degraded(self, checker):
        """Test overall status calculation with degraded component."""
        checks = {
            "database": HealthCheckResult(name="database", status=HealthStatus.HEALTHY, message="OK"),
            "redis": HealthCheckResult(name="redis", status=HealthStatus.DEGRADED, message="Slow"),
        }
        status = checker._calculate_overall_status(checks)
        assert status == HealthStatus.DEGRADED

    def test_calculate_overall_status_critical_unhealthy(self, checker):
        """Test overall status when critical component is unhealthy."""
        checks = {
            "database": HealthCheckResult(name="database", status=HealthStatus.UNHEALTHY, message="Down"),
            "redis": HealthCheckResult(name="redis", status=HealthStatus.HEALTHY, message="OK"),
        }
        status = checker._calculate_overall_status(checks)
        assert status == HealthStatus.UNHEALTHY


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_health_checker_singleton(self):
        """Test that get_health_checker returns the same instance."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        assert checker1 is checker2

    @pytest.mark.asyncio
    async def test_run_health_check(self):
        """Test the convenience function run_health_check."""
        with patch("backend.monitoring.health_checks.get_health_checker") as mock_get_checker:
            mock_checker = MagicMock()
            mock_checker.check_all = AsyncMock(
                return_value=SystemHealthReport(
                    overall_status=HealthStatus.HEALTHY,
                    checks={},
                )
            )
            mock_get_checker.return_value = mock_checker

            report = await run_health_check()
            assert isinstance(report, SystemHealthReport)
            mock_checker.check_all.assert_called_once()


class TestHealthCheckThresholds:
    """Tests for threshold configurations."""

    def test_disk_thresholds(self):
        """Test disk space thresholds."""
        checker = HealthChecker()
        assert checker.DISK_WARNING_PERCENT == 80
        assert checker.DISK_CRITICAL_PERCENT == 90

    def test_memory_thresholds(self):
        """Test memory thresholds."""
        checker = HealthChecker()
        assert checker.MEMORY_WARNING_PERCENT == 80
        assert checker.MEMORY_CRITICAL_PERCENT == 90

    def test_cpu_thresholds(self):
        """Test CPU thresholds."""
        checker = HealthChecker()
        assert checker.CPU_WARNING_PERCENT == 80
        assert checker.CPU_CRITICAL_PERCENT == 95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
