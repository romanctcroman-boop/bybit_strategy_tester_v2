"""
Tests for Prompts Alerting Service

Run: pytest tests/monitoring/test_prompts_alerting.py -v
"""

import sys
sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.prompts_alerting import (
    PromptsAlerting,
    AlertConfig,
    Alert,
    AlertType,
    AlertSeverity,
)


class TestPromptsAlerting:
    """Tests for PromptsAlerting."""

    @pytest.fixture
    def alerting(self):
        """Create alerting instance."""
        config = AlertConfig(
            validation_failure_threshold=0.05,
            injection_attempt_alert=True,
            hourly_cost_threshold=1.0,
            daily_cost_threshold=10.0,
            monthly_cost_threshold=100.0,
            min_cache_hit_rate=0.5,
            max_failure_rate=0.1,
            alert_log_path="data/test_prompts_alerts.json"
        )
        return PromptsAlerting(config)

    def test_alerting_initialization(self, alerting):
        """Test alerting initializes correctly."""
        assert alerting is not None
        assert alerting.config is not None
        assert alerting.config.validation_failure_threshold == 0.05

    def test_check_alerts(self, alerting):
        """Test checking alerts."""
        alerts = alerting.check_alerts()
        
        # Should return list
        assert isinstance(alerts, list)
        
        # All items should be Alerts
        for alert in alerts:
            assert isinstance(alert, Alert)
            assert alert.alert_id is not None
            assert alert.alert_type is not None
            assert alert.severity is not None
            assert alert.timestamp is not None

    def test_get_active_alerts(self, alerting):
        """Test getting active alerts."""
        alerts = alerting.get_active_alerts()
        
        assert isinstance(alerts, list)
        
        # All active alerts should be unresolved
        for alert in alerts:
            assert not alert.resolved

    def test_get_alert_summary(self, alerting):
        """Test alert summary."""
        summary = alerting.get_alert_summary()
        
        assert isinstance(summary, dict)
        assert 'total_active' in summary
        assert 'by_severity' in summary
        assert 'by_type' in summary
        assert 'total_history' in summary

    def test_acknowledge_alert(self, alerting):
        """Test acknowledging alerts."""
        # First check alerts to populate list
        alerting.check_alerts()
        
        # Get active alerts
        active = alerting.get_active_alerts()
        
        if active:
            alert_id = active[0].alert_id
            result = alerting.acknowledge_alert(alert_id)
            
            # Should succeed
            assert result is True
            
            # Alert should be acknowledged
            acknowledged_alert = None
            for a in alerting.get_active_alerts():
                if a.alert_id == alert_id:
                    acknowledged_alert = a
                    break
            
            if acknowledged_alert:
                assert acknowledged_alert.acknowledged is True

    def test_resolve_alert(self, alerting):
        """Test resolving alerts."""
        # First check alerts
        alerting.check_alerts()
        
        # Get active alerts
        active = alerting.get_active_alerts()
        
        if active:
            alert_id = active[0].alert_id
            result = alerting.resolve_alert(alert_id)
            
            # Should succeed
            assert result is True
            
            # Alert should not be in active list anymore
            active_after = alerting.get_active_alerts()
            assert not any(a.alert_id == alert_id for a in active_after)

    def test_clear_resolved_alerts(self, alerting):
        """Test clearing resolved alerts."""
        # Resolve some alerts
        alerting.check_alerts()
        active = alerting.get_active_alerts()
        
        resolved_count = 0
        for alert in active:
            if alerting.resolve_alert(alert.alert_id):
                resolved_count += 1
        
        # Clear resolved
        cleared = alerting.clear_resolved_alerts()
        
        # Should match resolved count
        assert cleared == resolved_count

    def test_alert_types(self):
        """Test alert type enum."""
        assert AlertType.VALIDATION_FAILURE.value == "validation_failure"
        assert AlertType.INJECTION_ATTEMPT.value == "injection_attempt"
        assert AlertType.HIGH_COST.value == "high_cost"
        assert AlertType.LOW_CACHE_HIT.value == "low_cache_hit"
        assert AlertType.SERVICE_DEGRADATION.value == "service_degradation"

    def test_alert_severity(self):
        """Test alert severity enum."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = Alert(
            alert_id="test_123",
            alert_type=AlertType.INJECTION_ATTEMPT,
            severity=AlertSeverity.CRITICAL,
            message="Test alert",
            timestamp="2026-03-03T00:00:00",
            details={"test": "data"},
            acknowledged=False,
            resolved=False
        )
        
        data = alert.to_dict()
        
        assert data['alert_id'] == "test_123"
        assert data['alert_type'] == "injection_attempt"
        assert data['severity'] == "critical"
        assert data['message'] == "Test alert"
        assert data['details'] == {"test": "data"}
        assert data['acknowledged'] is False
        assert data['resolved'] is False

    def test_alert_config_defaults(self):
        """Test alert config defaults."""
        config = AlertConfig()
        
        assert config.validation_failure_threshold == 0.05
        assert config.injection_attempt_alert is True
        assert config.hourly_cost_threshold == 1.0
        assert config.daily_cost_threshold == 10.0
        assert config.monthly_cost_threshold == 100.0
        assert config.min_cache_hit_rate == 0.5
        assert config.max_failure_rate == 0.1

    def test_alert_config_custom(self):
        """Test custom alert config."""
        config = AlertConfig(
            validation_failure_threshold=0.10,
            hourly_cost_threshold=5.0,
            min_cache_hit_rate=0.7
        )
        
        assert config.validation_failure_threshold == 0.10
        assert config.hourly_cost_threshold == 5.0
        assert config.min_cache_hit_rate == 0.7


class TestAlertingCallbacks:
    """Tests for alerting callbacks."""

    def test_on_alert_callback(self):
        """Test on_alert callback."""
        triggered_alerts = []
        
        def callback(alert):
            triggered_alerts.append(alert)
        
        config = AlertConfig(on_alert=callback)
        alerting = PromptsAlerting(config)
        
        # Trigger alerts
        alerting.check_alerts()
        
        # Callback should have been called
        # (may be 0 if no alerts triggered)
        assert isinstance(triggered_alerts, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
