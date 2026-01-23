"""
Tests for backend/core/anomaly_detector.py

Tests anomaly detection functionality:
- Strategy registration
- Metric recording
- Anomaly detection
- Trade result tracking
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.anomaly_detector import (
    AnomalyDetector,
    AnomalySeverity,
    AnomalyThresholds,
    AnomalyType,
    MetricWindow,
    get_anomaly_detector,
)


class TestMetricWindow:
    """Tests for MetricWindow class."""

    def test_add_values(self):
        """Test adding values to window."""
        window = MetricWindow(window_size=10)
        window.add(1.0)
        window.add(2.0)
        window.add(3.0)

        assert len(window.values) == 3

    def test_window_max_size(self):
        """Test window respects max size."""
        window = MetricWindow(window_size=5)
        for i in range(10):
            window.add(float(i))

        assert len(window.values) == 5
        assert list(window.values) == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_mean_calculation(self):
        """Test mean calculation."""
        window = MetricWindow()
        for i in [1, 2, 3, 4, 5]:
            window.add(float(i))

        assert window.mean() == 3.0

    def test_mean_empty_window(self):
        """Test mean with empty window."""
        window = MetricWindow()
        assert window.mean() == 0.0

    def test_std_calculation(self):
        """Test standard deviation calculation."""
        window = MetricWindow()
        for i in [2, 4, 4, 4, 5, 5, 7, 9]:
            window.add(float(i))

        # std of [2,4,4,4,5,5,7,9] ~ 2.14 (sample std)
        assert abs(window.std() - 2.14) < 0.2

    def test_std_insufficient_data(self):
        """Test std with insufficient data."""
        window = MetricWindow()
        window.add(1.0)
        assert window.std() == 0.0

    def test_z_score(self):
        """Test z-score calculation."""
        window = MetricWindow()
        for i in [10, 10, 10, 10, 10]:
            window.add(float(i))
        window.add(10.0)  # Add one more for std

        # For constant values, z-score is 0
        # Add some variation
        window.values.clear()
        for v in [8, 9, 10, 11, 12]:
            window.add(float(v))

        # Mean is 10, std is ~1.58
        z = window.z_score(13.0)
        assert z > 1.5  # Should be positive z-score


class TestAnomalyThresholds:
    """Tests for AnomalyThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = AnomalyThresholds()
        assert thresholds.z_score_warning == 2.0
        assert thresholds.z_score_critical == 3.0
        assert thresholds.drawdown_warning_pct == 5.0
        assert thresholds.consecutive_losses_warning == 5

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = AnomalyThresholds(z_score_warning=1.5, drawdown_critical_pct=15.0)
        assert thresholds.z_score_warning == 1.5
        assert thresholds.drawdown_critical_pct == 15.0


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""

    @pytest.fixture
    def detector(self):
        """Create fresh detector for testing."""
        return AnomalyDetector(
            thresholds=AnomalyThresholds(
                z_score_warning=2.0,
                z_score_critical=3.0,
                drawdown_warning_pct=5.0,
                drawdown_critical_pct=10.0,
                consecutive_losses_warning=3,
                consecutive_losses_critical=5,
            ),
            window_size=20,
        )

    def test_register_strategy(self, detector):
        """Test strategy registration."""
        detector.register_strategy("test_strategy")
        assert "test_strategy" in detector._strategy_metrics
        assert "test_strategy" in detector._anomalies

    def test_auto_register_on_metric(self, detector):
        """Test auto-registration when recording metric."""
        detector.record_metric("new_strategy", "drawdown", 1.0)
        assert "new_strategy" in detector._strategy_metrics

    def test_record_normal_metric(self, detector):
        """Test recording normal metric values."""
        detector.register_strategy("test")

        # Add baseline values
        for i in range(15):
            result = detector.record_metric("test", "drawdown", 2.0 + i * 0.1)

        # Should not detect anomaly for small changes
        result = detector.record_metric("test", "drawdown", 2.5)
        assert result is None

    def test_detect_drawdown_anomaly(self, detector):
        """Test detecting drawdown spike."""
        detector.register_strategy("test")

        # Add baseline values
        for _ in range(15):
            detector.record_metric("test", "drawdown", 2.0)

        # Add extreme value
        result = detector.record_metric("test", "drawdown", 15.0)

        # Should detect anomaly
        assert result is not None
        assert result.anomaly_type == AnomalyType.DRAWDOWN_SPIKE

    def test_detect_consecutive_losses(self, detector):
        """Test detecting consecutive losses."""
        detector.register_strategy("test")

        # Record losses
        for i in range(3):
            result = detector.record_trade_result("test", is_win=False)

        # After 3 losses (warning threshold), should get anomaly
        assert result is not None
        assert result.anomaly_type == AnomalyType.CONSECUTIVE_LOSSES
        assert result.severity == AnomalySeverity.WARNING

    def test_critical_consecutive_losses(self, detector):
        """Test critical consecutive losses detection."""
        detector.register_strategy("test")

        # Record many losses
        for i in range(5):
            result = detector.record_trade_result("test", is_win=False)

        assert result is not None
        assert result.severity == AnomalySeverity.CRITICAL

    def test_win_resets_consecutive_losses(self, detector):
        """Test that a win resets consecutive loss counter."""
        detector.register_strategy("test")

        # Record some losses
        detector.record_trade_result("test", is_win=False)
        detector.record_trade_result("test", is_win=False)

        # Win resets counter
        result = detector.record_trade_result("test", is_win=True)
        assert result is None
        assert detector._consecutive_losses["test"] == 0

    def test_get_anomalies(self, detector):
        """Test getting anomalies with filters."""
        detector.register_strategy("test")

        # Create some anomalies
        for _ in range(15):
            detector.record_metric("test", "drawdown", 1.0)
        detector.record_metric("test", "drawdown", 20.0)

        anomalies = detector.get_anomalies("test")
        assert len(anomalies) >= 1

    def test_get_anomalies_by_severity(self, detector):
        """Test filtering anomalies by severity."""
        detector.register_strategy("test")

        # Create critical anomaly
        for _ in range(5):
            detector.record_trade_result("test", is_win=False)

        critical_anomalies = detector.get_anomalies(
            "test", severity=AnomalySeverity.CRITICAL
        )
        assert all(a.severity == AnomalySeverity.CRITICAL for a in critical_anomalies)

    def test_acknowledge_anomaly(self, detector):
        """Test acknowledging an anomaly."""
        detector.register_strategy("test")

        # Create anomaly
        for _ in range(5):
            detector.record_trade_result("test", is_win=False)

        anomalies = detector.get_anomalies("test")
        assert len(anomalies) > 0

        anomaly_id = anomalies[0].anomaly_id
        result = detector.acknowledge_anomaly(anomaly_id, "user@test.com")

        assert result is True
        assert anomalies[0].acknowledged is True
        assert anomalies[0].acknowledged_by == "user@test.com"

    def test_get_strategy_health(self, detector):
        """Test getting strategy health summary."""
        detector.register_strategy("test")

        # Add some metrics
        for i in range(15):
            detector.record_metric("test", "drawdown", 2.0)
            detector.record_metric("test", "win_rate", 0.6)

        health = detector.get_strategy_health("test")

        assert health["strategy_id"] == "test"
        assert health["status"] == "healthy"
        assert health["health_score"] == 1.0
        assert "metrics" in health

    def test_health_degrades_with_anomalies(self, detector):
        """Test health score degrades with anomalies."""
        detector.register_strategy("test")

        # Create critical anomaly
        for _ in range(5):
            detector.record_trade_result("test", is_win=False)

        health = detector.get_strategy_health("test")

        assert health["status"] == "critical"
        assert health["health_score"] < 1.0
        assert health["critical_count"] >= 1

    def test_cleanup_old_anomalies(self, detector):
        """Test cleaning up old anomalies."""
        detector.register_strategy("test")

        # Create and acknowledge anomaly
        for _ in range(5):
            detector.record_trade_result("test", is_win=False)

        anomalies = detector.get_anomalies("test")
        for a in anomalies:
            detector.acknowledge_anomaly(a.anomaly_id)
            # Backdate the anomaly
            a.timestamp = datetime.now(timezone.utc) - timedelta(hours=25)

        # Cleanup with 24 hour max age
        removed = detector.cleanup_old_anomalies(max_age_hours=24)
        assert removed > 0

    def test_on_anomaly_callback(self):
        """Test callback is called on anomaly detection."""
        callback_called = []

        def callback(anomaly):
            callback_called.append(anomaly)

        detector = AnomalyDetector(
            thresholds=AnomalyThresholds(consecutive_losses_warning=2),
            on_anomaly=callback,
        )
        detector.register_strategy("test")

        # Trigger anomaly
        detector.record_trade_result("test", is_win=False)
        detector.record_trade_result("test", is_win=False)

        assert len(callback_called) > 0


class TestSingletonDetector:
    """Tests for singleton detector instance."""

    def test_get_anomaly_detector_returns_instance(self):
        """Test get_anomaly_detector returns instance."""
        detector = get_anomaly_detector()
        assert detector is not None
        assert isinstance(detector, AnomalyDetector)

    def test_singleton_returns_same_instance(self):
        """Test singleton returns same instance."""
        d1 = get_anomaly_detector()
        d2 = get_anomaly_detector()
        assert d1 is d2
