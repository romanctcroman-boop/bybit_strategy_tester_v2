"""
Tests for backend/core/metrics.py

Tests unified metrics functionality:
- MetricsCollector methods
- Prometheus metrics registration
- MetricsTimer context manager
"""

import time

import pytest

from backend.core.metrics import (
    REGISTRY,
    MetricsTimer,
    get_metrics,
    metrics,
)


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @pytest.fixture
    def collector(self):
        """Get metrics collector instance."""
        return get_metrics()

    def test_singleton_instance(self):
        """Test that get_metrics returns same instance."""
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_convenience_alias(self):
        """Test metrics alias."""
        assert metrics is get_metrics()

    def test_backfill_upserts(self, collector):
        """Test backfill upserts counter."""
        # Should not raise
        collector.backfill_upserts("BTCUSDT", "1h", 100)

    def test_backfill_pages(self, collector):
        """Test backfill pages counter."""
        collector.backfill_pages("ETHUSDT", "4h", 5)

    def test_observe_backfill_duration(self, collector):
        """Test backfill duration histogram."""
        collector.observe_backfill_duration(15.5)

    def test_backfill_run_status(self, collector):
        """Test run status counter."""
        collector.backfill_run_status("completed")
        collector.backfill_run_status("failed")

    def test_mcp_tool_call(self, collector):
        """Test MCP tool call recording."""
        collector.mcp_tool_call("get_balance", True, 0.5)
        collector.mcp_tool_call("get_balance", False, None)

    def test_mcp_tool_error(self, collector):
        """Test MCP tool error recording."""
        collector.mcp_tool_error("get_balance", "timeout")

    def test_mcp_bridge_call(self, collector):
        """Test MCP bridge call recording."""
        collector.mcp_bridge_call("place_order", True, 0.1)

    def test_circuit_breaker_state(self, collector):
        """Test circuit breaker state gauge."""
        collector.record_circuit_breaker_state("bybit_api", "closed")
        collector.record_circuit_breaker_state("bybit_api", "open")
        collector.record_circuit_breaker_state("bybit_api", "half_open")

    def test_circuit_breaker_failure(self, collector):
        """Test circuit breaker failure counter."""
        collector.circuit_breaker_failure("bybit_api")

    def test_circuit_breaker_success(self, collector):
        """Test circuit breaker success counter."""
        collector.circuit_breaker_success("bybit_api")

    def test_circuit_breaker_opened(self, collector):
        """Test circuit breaker opened counter."""
        collector.circuit_breaker_opened("bybit_api")

    def test_record_strategy_health(self, collector):
        """Test strategy health recording."""
        collector.record_strategy_health(
            strategy_id="my_strategy",
            health_score=0.85,
            strategy_name="My Strategy",
            drawdown=2.5,
            win_rate=0.65,
            sharpe_ratio=1.2,
        )

    def test_record_trade(self, collector):
        """Test trade recording."""
        collector.record_trade("my_strategy", "buy", "win")
        collector.record_trade("my_strategy", "sell", "loss")

    def test_record_pnl(self, collector):
        """Test PnL recording."""
        collector.record_pnl("my_strategy", 150.0)

    def test_record_anomaly(self, collector):
        """Test anomaly recording."""
        collector.record_anomaly("drawdown_spike", "critical")

    def test_set_anomaly_score(self, collector):
        """Test anomaly score setting."""
        collector.set_anomaly_score("win_rate", 0.75)

    def test_fire_alert(self, collector):
        """Test alert firing."""
        collector.fire_alert("high_drawdown", "warning")

    def test_acknowledge_alert(self, collector):
        """Test alert acknowledgement."""
        collector.acknowledge_alert("high_drawdown")

    def test_consensus_loop_prevented(self, collector):
        """Test consensus loop prevention recording."""
        collector.consensus_loop_prevented("iteration_cap")

    def test_dlq_message(self, collector):
        """Test DLQ message recording."""
        collector.dlq_message("high", "deepseek")

    def test_dlq_retry(self, collector):
        """Test DLQ retry recording."""
        collector.dlq_retry("success")
        collector.dlq_retry("failed")

    def test_record_api_request(self, collector):
        """Test API request recording."""
        collector.record_api_request("GET", "/api/v1/health", 200, 0.05)
        collector.record_api_request("POST", "/api/v1/backtest", 500, 1.5)

    def test_get_metrics_text(self, collector):
        """Test Prometheus metrics text generation."""
        text = collector.get_metrics_text()
        assert isinstance(text, str)
        assert len(text) > 0
        # Should contain some known metric names
        assert (
            "backfill" in text.lower()
            or "circuit" in text.lower()
            or "mcp" in text.lower()
        )

    def test_get_content_type(self, collector):
        """Test content type string."""
        content_type = collector.get_content_type()
        assert "text/plain" in content_type or "openmetrics" in content_type.lower()


class TestMetricsTimer:
    """Tests for MetricsTimer context manager."""

    def test_timer_measures_duration(self):
        """Test timer measures duration."""
        with MetricsTimer("backfill") as timer:
            time.sleep(0.01)

        assert timer.duration is not None
        assert timer.duration >= 0.01

    def test_timer_success_default(self):
        """Test timer success defaults to True."""
        with MetricsTimer("backfill") as timer:
            pass

        assert timer.success is True

    def test_timer_failure_on_exception(self):
        """Test timer sets success to False on exception."""
        timer = None
        try:
            with MetricsTimer("mcp_tool", tool="test") as timer:
                raise ValueError("test error")
        except ValueError:
            pass

        assert timer is not None
        assert timer.success is False

    def test_timer_with_labels(self):
        """Test timer with custom labels."""
        with MetricsTimer("mcp_tool", tool="get_balance") as timer:
            pass

        assert timer.labels.get("tool") == "get_balance"

    def test_timer_api_type(self):
        """Test timer for API metrics."""
        with MetricsTimer(
            "api", method="GET", endpoint="/test", status_code=200
        ) as timer:
            time.sleep(0.001)

        assert timer.duration is not None
        assert timer.labels.get("method") == "GET"


class TestRegistry:
    """Tests for Prometheus registry."""

    def test_registry_exists(self):
        """Test REGISTRY exists and is not None."""
        assert REGISTRY is not None

    def test_registry_has_collectors(self):
        """Test registry has collectors registered."""
        # Registry should have some collectors
        collectors = list(REGISTRY.collect())
        assert len(collectors) > 0
