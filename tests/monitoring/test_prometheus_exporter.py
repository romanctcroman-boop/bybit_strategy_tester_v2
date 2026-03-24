"""
Tests for Prometheus Metrics Exporter

Run: pytest tests/monitoring/test_prometheus_exporter.py -v
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.prometheus_exporter import (
    MetricsCollector,
    get_metrics_collector,
)


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Create metrics collector."""
        return MetricsCollector()

    def test_record_http_request(self, collector):
        """Test recording HTTP request."""
        collector.record_http_request(200, 0.15, method="GET", endpoint="/api/test")

        metrics = collector.get_metrics()

        assert "http_requests_total" in metrics
        assert "http_request_duration_seconds" in metrics
        assert "histogram" in metrics  # Verify histogram type is declared

    def test_record_ai_request(self, collector):
        """Test recording AI request."""
        collector.record_ai_request(
            agent="qwen",
            duration_seconds=2.5,
            success=True,
            tokens_used=1000,
            cost_usd=0.01,
        )

        metrics = collector.get_metrics()

        assert "ai_agent_requests_total" in metrics
        assert "ai_agent_request_duration_seconds" in metrics
        assert "ai_agent_tokens_total" in metrics
        assert "cost_usd_total" in metrics
        assert "histogram" in metrics  # Verify histogram type is declared

    def test_record_cache_hit_miss(self, collector):
        """Test recording cache hit/miss."""
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        metrics = collector.get_metrics()

        assert "cache_hits_total" in metrics
        assert "cache_misses_total" in metrics

    def test_record_backtest(self, collector):
        """Test recording backtest."""
        collector.record_backtest(success=True, duration_seconds=5.0)
        collector.record_backtest(success=False, duration_seconds=0.5)

        metrics = collector.get_metrics()

        assert "backtest_total" in metrics
        assert "backtest_failures_total" in metrics

    def test_set_gauge(self, collector):
        """Test setting gauge."""
        collector.set_gauge("active_connections", 10)
        collector.set_gauge("active_connections", 15, labels={"service": "api"})

        metrics = collector.get_metrics()

        assert "active_connections" in metrics
        assert 'service="api"' in metrics

    def test_get_metrics_format(self, collector):
        """Test metrics format."""
        collector.record_http_request(200, 0.1)

        metrics = collector.get_metrics()

        # Check Prometheus format
        assert "# HELP" in metrics
        assert "# TYPE" in metrics
        assert "counter" in metrics or "gauge" in metrics or "histogram" in metrics

    def test_get_stats(self, collector):
        """Test getting stats dict."""
        collector.record_http_request(200, 0.1)
        collector.record_cache_hit()

        stats = collector.get_stats()

        assert "uptime_seconds" in stats
        assert "counters" in stats
        assert "gauges" in stats
        assert stats["uptime_seconds"] > 0

    def test_histogram_buckets(self, collector):
        """Test histogram bucket recording."""
        collector.record_http_request(200, 0.05)

        metrics = collector.get_metrics()

        assert "http_request_duration_seconds_bucket" in metrics
        assert "+Inf" in metrics
        assert "http_request_duration_seconds_sum" in metrics
        assert "http_request_duration_seconds_count" in metrics

    def test_multiple_requests(self, collector):
        """Test recording multiple requests."""
        for i in range(100):
            collector.record_http_request(200 if i % 10 != 0 else 500, 0.1 + i * 0.01)

        stats = collector.get_stats()

        assert stats["counters"].get("http_requests_total", 0) == 100

    def test_cost_tracking(self, collector):
        """Test cost tracking."""
        collector.record_ai_request("qwen", 1.0, True, cost_usd=0.01)
        collector.record_ai_request("deepseek", 1.0, True, cost_usd=0.005)

        metrics = collector.get_metrics()

        assert "cost_usd_total" in metrics
        assert 'agent="qwen"' in metrics
        assert 'agent="deepseek"' in metrics


class TestGlobalCollector:
    """Tests for global collector functions."""

    def test_get_metrics_collector_singleton(self):
        """Test singleton pattern."""
        c1 = get_metrics_collector()
        c2 = get_metrics_collector()

        # Should be same instance
        assert c1 is c2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
