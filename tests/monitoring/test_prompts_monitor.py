"""
Tests for Prompts Monitoring Service

Run: pytest tests/monitoring/test_prompts_monitor.py -v
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.prompts_monitor import DashboardMetrics, MonitoringConfig, PromptsMonitor


class TestPromptsMonitor:
    """Tests for PromptsMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create monitor instance."""
        config = MonitoringConfig(log_db_path="data/prompt_logs.db", refresh_interval_sec=1)
        return PromptsMonitor(config)

    def test_monitor_initialization(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor is not None
        assert monitor.config is not None
        assert monitor.config.retention_days == 30

    def test_get_dashboard(self, monitor):
        """Test dashboard retrieval."""
        dashboard = monitor.get_dashboard(period_hours=24)

        assert isinstance(dashboard, DashboardMetrics)
        assert dashboard.period_hours == 24
        assert dashboard.timestamp is not None

        # Check all fields exist
        assert hasattr(dashboard, "total_prompts")
        assert hasattr(dashboard, "validation_success_rate")
        assert hasattr(dashboard, "cache_hit_rate")
        assert hasattr(dashboard, "total_cost_usd")

    def test_get_validation_stats(self, monitor):
        """Test validation statistics."""
        stats = monitor.get_validation_stats(period_hours=24)

        assert isinstance(stats, dict)
        # Stats may be empty if no logs yet
        assert "total_prompts" in stats or "error" in stats

        # If we have data, check structure
        if "total_prompts" in stats:
            assert "validation_success_rate" in stats or "success_rate" in stats
            assert "period_hours" in stats

            # Rate should be between 0 and 1 if present
            rate = stats.get("validation_success_rate", stats.get("success_rate", 0))
            assert 0 <= rate <= 1

    def test_get_logging_stats(self, monitor):
        """Test logging statistics."""
        stats = monitor.get_logging_stats(period_hours=24)

        assert isinstance(stats, dict)
        assert "total_logged" in stats
        assert "total_tokens" in stats
        assert "total_cost_usd" in stats
        assert "avg_duration_ms" in stats
        assert "success_rate" in stats

    def test_get_cache_stats(self, monitor):
        """Test cache statistics."""
        stats = monitor.get_cache_stats()

        assert isinstance(stats, dict)
        assert "cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cache_hit_rate" in stats

        # Hit rate should be between 0 and 1
        assert 0 <= stats.get("cache_hit_rate", 0) <= 1

    def test_get_cost_breakdown(self, monitor):
        """Test cost breakdown."""
        breakdown = monitor.get_cost_breakdown(period_hours=24)

        assert isinstance(breakdown, dict)
        assert "total_cost_usd" in breakdown
        assert "by_agent" in breakdown
        assert "by_task" in breakdown
        assert "projected_monthly_cost" in breakdown

        # Cost should be non-negative
        assert breakdown.get("total_cost_usd", 0) >= 0

    def test_get_performance_trends(self, monitor):
        """Test performance trends."""
        trends = monitor.get_performance_trends(period_hours=24, intervals=24)

        assert isinstance(trends, dict)
        assert "trends" in trends
        assert "period_hours" in trends
        assert "intervals" in trends

        # Trends should be a list
        assert isinstance(trends.get("trends"), list)

    def test_export_dashboard(self, monitor, tmp_path):
        """Test dashboard export."""
        output_file = tmp_path / "dashboard.json"

        file_path = monitor.export_dashboard(str(output_file), period_hours=24)

        assert file_path is not None
        assert output_file.exists()

        # Check file is valid JSON
        import json

        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "validation" in data
        assert "logging" in data
        assert "cache" in data

    def test_dashboard_caching(self, monitor):
        """Test dashboard caching."""
        # First call
        dashboard1 = monitor.get_dashboard(period_hours=24)

        # Second call (should be cached)
        dashboard2 = monitor.get_dashboard(period_hours=24)

        # Should return same object (cached)
        assert dashboard1 is dashboard2

        # Different period should refresh
        dashboard3 = monitor.get_dashboard(period_hours=48)
        assert dashboard3 is not dashboard1
        assert dashboard3.period_hours == 48

    def test_monitoring_config(self):
        """Test monitoring configuration."""
        config = MonitoringConfig(log_db_path="custom/path.db", retention_days=60, refresh_interval_sec=30)

        assert config.log_db_path == "custom/path.db"
        assert config.retention_days == 60
        assert config.refresh_interval_sec == 30


class TestDashboardMetrics:
    """Tests for DashboardMetrics dataclass."""

    def test_dashboard_metrics_creation(self):
        """Test creating DashboardMetrics."""
        metrics = DashboardMetrics(timestamp="2026-03-03T00:00:00", period_hours=24)

        assert metrics.timestamp == "2026-03-03T00:00:00"
        assert metrics.period_hours == 24
        assert metrics.total_prompts == 0
        assert metrics.validation_success_rate == 0.0
        assert metrics.cache_hit_rate == 0.0

    def test_dashboard_metrics_with_data(self):
        """Test DashboardMetrics with data."""
        metrics = DashboardMetrics(
            timestamp="2026-03-03T00:00:00",
            period_hours=24,
            total_prompts=100,
            validated_prompts=95,
            failed_validations=5,
            validation_success_rate=0.95,
            total_cost_usd=1.50,
            cache_hit_rate=0.85,
        )

        assert metrics.total_prompts == 100
        assert metrics.validation_success_rate == 0.95
        assert metrics.total_cost_usd == 1.50
        assert metrics.cache_hit_rate == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
