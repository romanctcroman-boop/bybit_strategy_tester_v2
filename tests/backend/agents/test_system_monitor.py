"""
Tests for SystemMonitor (backend/agents/monitoring/system_monitor.py).

Tests cover:
- Metric tracking (valid & unknown metrics)
- Pipeline run recording (success/failure)
- Error recording
- Metrics summary aggregation
- Alert rules (lt, gt, deduplication)
- History retrieval
- Reset functionality
- Singleton accessor
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.agents.monitoring.system_monitor import (
    SystemMonitor,
    get_system_monitor,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def monitor() -> SystemMonitor:
    """Fresh SystemMonitor for each test (not the singleton)."""
    return SystemMonitor()


# =============================================================================
# TestSystemMonitorInit
# =============================================================================


class TestSystemMonitorInit:
    """Initialization and class-level constants."""

    def test_init_empty_state(self, monitor: SystemMonitor):
        """Fresh monitor has zero metrics and no alerts."""
        summary = monitor.get_metrics_summary()
        assert summary["total_runs"] == 0
        assert summary["agent_success_rate"] == 0.0
        assert summary["llm_token_usage"] == 0
        assert summary["system_errors"] == 0

    def test_metrics_to_track_contains_expected(self):
        """METRICS_TO_TRACK has the 7 required metrics."""
        expected = {
            "agent_success_rate",
            "strategy_generation_time",
            "backtest_duration",
            "llm_token_usage",
            "api_costs",
            "strategy_performance",
            "system_errors",
        }
        assert set(SystemMonitor.METRICS_TO_TRACK) == expected

    def test_alert_rules_exist(self):
        """ALERT_RULES cover at least the critical metrics."""
        assert "agent_success_rate" in SystemMonitor.ALERT_RULES
        assert "system_errors" in SystemMonitor.ALERT_RULES
        assert "api_costs" in SystemMonitor.ALERT_RULES


# =============================================================================
# TestTrackMetric
# =============================================================================


class TestTrackMetric:
    """track_metric records data and ignores unknowns."""

    def test_track_known_metric(self, monitor: SystemMonitor):
        """Tracking a known metric appends to history."""
        monitor.track_metric("llm_token_usage", 500)
        history = monitor.get_metrics_history("llm_token_usage")
        assert len(history) == 1
        assert history[0]["value"] == 500

    def test_track_unknown_metric_ignored(self, monitor: SystemMonitor):
        """Unknown metric names produce no error but log a warning."""
        monitor.track_metric("nonexistent_metric", 42)
        # Nothing in any history
        for name in SystemMonitor.METRICS_TO_TRACK:
            assert len(monitor.get_metrics_history(name)) == 0

    def test_track_metric_with_labels(self, monitor: SystemMonitor):
        """Labels are stored when provided."""
        monitor.track_metric("system_errors", 1, labels={"error": "timeout"})
        history = monitor.get_metrics_history("system_errors")
        assert history[0]["labels"]["error"] == "timeout"

    def test_track_metric_with_custom_timestamp(self, monitor: SystemMonitor):
        """Custom timestamps are stored correctly."""
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        monitor.track_metric("backtest_duration", 5.0, timestamp=ts)
        history = monitor.get_metrics_history("backtest_duration")
        assert history[0]["timestamp"] == ts.isoformat()


# =============================================================================
# TestRecordPipelineRun
# =============================================================================


class TestRecordPipelineRun:
    """record_pipeline_run convenience method."""

    def test_successful_run(self, monitor: SystemMonitor):
        """Success run increments counters and tracks metrics."""
        monitor.record_pipeline_run(
            success=True,
            generation_time_s=2.5,
            backtest_time_s=1.0,
            tokens_used=1000,
            cost_usd=0.05,
            quality_score=0.8,
        )
        summary = monitor.get_metrics_summary()
        assert summary["total_runs"] == 1
        assert summary["agent_success_rate"] == 1.0
        assert summary["strategy_generation_time"] == 2.5
        assert summary["backtest_duration"] == 1.0
        assert summary["llm_token_usage"] == 1000
        assert summary["api_costs"] == pytest.approx(0.05)
        assert summary["strategy_performance"] == 0.8
        assert summary["system_errors"] == 0

    def test_failed_run(self, monitor: SystemMonitor):
        """Failed run records error metric and updates success rate."""
        monitor.record_pipeline_run(success=False, generation_time_s=10.0)
        summary = monitor.get_metrics_summary()
        assert summary["total_runs"] == 1
        assert summary["agent_success_rate"] == 0.0
        assert summary["system_errors"] == 1

    def test_multiple_runs_average(self, monitor: SystemMonitor):
        """Success rate averages across multiple runs."""
        monitor.record_pipeline_run(success=True, generation_time_s=2.0)
        monitor.record_pipeline_run(success=False, generation_time_s=8.0)
        summary = monitor.get_metrics_summary()
        assert summary["total_runs"] == 2
        assert summary["agent_success_rate"] == pytest.approx(0.5)
        assert summary["strategy_generation_time"] == pytest.approx(5.0)

    def test_zero_values_not_tracked(self, monitor: SystemMonitor):
        """Zero optional values are not tracked as metrics."""
        monitor.record_pipeline_run(success=True)
        # Only agent_success_rate should be tracked
        assert len(monitor.get_metrics_history("strategy_generation_time")) == 0
        assert len(monitor.get_metrics_history("backtest_duration")) == 0
        assert len(monitor.get_metrics_history("llm_token_usage")) == 0


# =============================================================================
# TestRecordError
# =============================================================================


class TestRecordError:
    """record_error convenience method."""

    def test_record_error_increments(self, monitor: SystemMonitor):
        """Each error call increments system_errors count."""
        monitor.record_error("Something went wrong")
        monitor.record_error("Another issue")
        summary = monitor.get_metrics_summary()
        assert summary["system_errors"] == 2

    def test_record_error_with_message(self, monitor: SystemMonitor):
        """Error message is stored in labels."""
        monitor.record_error("Connection timeout")
        history = monitor.get_metrics_history("system_errors")
        assert history[0]["labels"]["error"] == "Connection timeout"

    def test_record_error_empty_message(self, monitor: SystemMonitor):
        """Empty message produces no labels."""
        monitor.record_error("")
        history = monitor.get_metrics_history("system_errors")
        assert "labels" not in history[0]


# =============================================================================
# TestAlerts
# =============================================================================


class TestAlerts:
    """Alert generation and deduplication."""

    def test_low_success_rate_triggers_alert(self, monitor: SystemMonitor):
        """agent_success_rate < 0.3 triggers warning alert."""
        monitor.track_metric("agent_success_rate", 0.1)
        alerts = monitor.get_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["metric"] == "agent_success_rate"
        assert alerts[0]["severity"] == "warning"

    def test_high_generation_time_triggers_alert(self, monitor: SystemMonitor):
        """strategy_generation_time > 30 triggers info alert."""
        monitor.track_metric("strategy_generation_time", 45.0)
        alerts = monitor.get_alerts()
        assert any(a["metric"] == "strategy_generation_time" and a["severity"] == "info" for a in alerts)

    def test_normal_values_no_alerts(self, monitor: SystemMonitor):
        """Values within thresholds produce no alerts."""
        monitor.track_metric("agent_success_rate", 0.9)
        monitor.track_metric("strategy_generation_time", 5.0)
        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_alert_deduplication_within_5min(self, monitor: SystemMonitor):
        """Same alert within 5 minutes is deduplicated."""
        now = datetime.now(UTC)
        # First alert
        monitor.track_metric("agent_success_rate", 0.1, timestamp=now)
        # Second within 5 minutes — should be deduped
        monitor.track_metric(
            "agent_success_rate",
            0.05,
            timestamp=now + timedelta(minutes=2),
        )
        alerts = monitor.get_alerts()
        success_alerts = [a for a in alerts if a["metric"] == "agent_success_rate"]
        assert len(success_alerts) == 1

    def test_alert_after_5min_not_deduped(self, monitor: SystemMonitor):
        """Same alert after 5+ minutes is NOT deduplicated."""
        now = datetime.now(UTC)
        monitor.track_metric("agent_success_rate", 0.1, timestamp=now)
        monitor.track_metric(
            "agent_success_rate",
            0.05,
            timestamp=now + timedelta(minutes=6),
        )
        alerts = monitor.get_alerts()
        success_alerts = [a for a in alerts if a["metric"] == "agent_success_rate"]
        assert len(success_alerts) == 2


# =============================================================================
# TestMetricsHistory
# =============================================================================


class TestMetricsHistory:
    """get_metrics_history retrieval."""

    def test_empty_history(self, monitor: SystemMonitor):
        """Unknown metric returns empty list."""
        assert monitor.get_metrics_history("nonexistent") == []

    def test_last_n_limits(self, monitor: SystemMonitor):
        """last_n parameter limits returned entries."""
        for i in range(20):
            monitor.track_metric("llm_token_usage", i * 100)
        history = monitor.get_metrics_history("llm_token_usage", last_n=5)
        assert len(history) == 5
        # Should be the last 5 entries (values 1500..1900)
        assert history[0]["value"] == 1500

    def test_full_history(self, monitor: SystemMonitor):
        """Default returns all entries when < 100."""
        for i in range(10):
            monitor.track_metric("api_costs", float(i))
        history = monitor.get_metrics_history("api_costs")
        assert len(history) == 10


# =============================================================================
# TestReset
# =============================================================================


class TestReset:
    """Reset clears all state."""

    def test_reset_clears_metrics(self, monitor: SystemMonitor):
        """After reset, all metrics are zero."""
        monitor.record_pipeline_run(success=True, tokens_used=500)
        monitor.record_error("test error")
        monitor.reset()
        summary = monitor.get_metrics_summary()
        assert summary["total_runs"] == 0
        assert summary["llm_token_usage"] == 0
        assert summary["system_errors"] == 0

    def test_reset_clears_alerts(self, monitor: SystemMonitor):
        """After reset, alerts list is empty."""
        monitor.track_metric("agent_success_rate", 0.01)
        assert len(monitor.get_alerts()) > 0
        monitor.reset()
        assert len(monitor.get_alerts()) == 0


# =============================================================================
# TestGetFullReport
# =============================================================================


class TestGetFullReport:
    """get_full_report combines metrics + alerts."""

    def test_full_report_structure(self, monitor: SystemMonitor):
        """Full report has metrics and alerts keys."""
        monitor.record_pipeline_run(success=True, tokens_used=200)
        report = monitor.get_full_report()
        assert "metrics" in report
        assert "alerts" in report
        assert report["metrics"]["total_runs"] == 1


# =============================================================================
# TestSingleton
# =============================================================================


class TestSingleton:
    """get_system_monitor singleton accessor."""

    def test_singleton_returns_same_instance(self):
        """Multiple calls return the same SystemMonitor."""
        m1 = get_system_monitor()
        m2 = get_system_monitor()
        assert m1 is m2

    def test_singleton_is_system_monitor_type(self):
        """Singleton is a SystemMonitor instance."""
        assert isinstance(get_system_monitor(), SystemMonitor)
