"""
Tests for SLO Error Budget Service.
"""

import pytest

from backend.services.slo_error_budget import (
    BudgetStatus,
    SLODefinition,
    SLOErrorBudgetService,
    SLOType,
    get_slo_service,
)


class TestSLODefinition:
    """Test cases for SLODefinition."""

    def test_default_slo_definition(self):
        """Test default SLO definition values."""
        slo = SLODefinition(name="test_slo", slo_type=SLOType.LATENCY_P99, target=500.0)

        assert slo.name == "test_slo"
        assert slo.slo_type == SLOType.LATENCY_P99
        assert slo.target == 500.0
        assert slo.window_hours == 24 * 7  # Default 7 days
        assert slo.description == ""

    def test_custom_slo_definition(self):
        """Test custom SLO definition."""
        slo = SLODefinition(
            name="custom_slo",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,
            window_hours=24,
            description="Custom availability SLO",
        )

        assert slo.name == "custom_slo"
        assert slo.target == 99.9
        assert slo.window_hours == 24
        assert slo.description == "Custom availability SLO"


class TestSLOType:
    """Test SLO type enum."""

    def test_slo_types(self):
        """Test all SLO type values."""
        assert SLOType.LATENCY_P50.value == "latency_p50"
        assert SLOType.LATENCY_P95.value == "latency_p95"
        assert SLOType.LATENCY_P99.value == "latency_p99"
        assert SLOType.ERROR_RATE.value == "error_rate"
        assert SLOType.AVAILABILITY.value == "availability"
        assert SLOType.THROUGHPUT.value == "throughput"


class TestBudgetStatus:
    """Test budget status enum."""

    def test_budget_statuses(self):
        """Test all budget status values."""
        assert BudgetStatus.HEALTHY.value == "healthy"
        assert BudgetStatus.WARNING.value == "warning"
        assert BudgetStatus.CRITICAL.value == "critical"
        assert BudgetStatus.EXHAUSTED.value == "exhausted"


class TestSLOErrorBudgetService:
    """Test cases for SLOErrorBudgetService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for testing."""
        return SLOErrorBudgetService()

    def test_service_init(self, service):
        """Test service initialization."""
        # Should have default SLOs
        slos = service.list_slos()
        assert len(slos) >= 6  # Default SLOs

    def test_register_slo(self, service):
        """Test registering a new SLO."""
        slo = SLODefinition(
            name="custom_test_slo", slo_type=SLOType.LATENCY_P99, target=100.0
        )

        service.register_slo(slo)

        slos = service.list_slos()
        names = [s["name"] for s in slos]
        assert "custom_test_slo" in names

    def test_record_latency_good(self, service):
        """Test recording good latency metric."""
        is_good = service.record_latency(
            slo_name="api_latency_p99",
            latency_ms=100.0,  # Under 500ms target
            endpoint="/test",
        )

        assert is_good is True

    def test_record_latency_bad(self, service):
        """Test recording bad latency metric."""
        is_good = service.record_latency(
            slo_name="api_latency_p99",
            latency_ms=600.0,  # Over 500ms target
            endpoint="/test",
        )

        assert is_good is False

    def test_record_success(self, service):
        """Test recording success event."""
        service.record_success(slo_name="api_availability", endpoint="/test")

        state = service.get_error_budget_state("api_availability")
        assert state.total_events >= 1
        assert state.good_events >= 1

    def test_record_failure(self, service):
        """Test recording failure event."""
        service.record_failure(
            slo_name="api_availability", endpoint="/test", error="Connection timeout"
        )

        state = service.get_error_budget_state("api_availability")
        assert state.total_events >= 1
        assert state.bad_events >= 1

    def test_get_error_budget_state_empty(self, service):
        """Test getting error budget state with no data."""
        state = service.get_error_budget_state("api_latency_p99")

        assert state is not None
        assert state.slo_name == "api_latency_p99"
        assert state.total_events == 0
        assert state.error_budget_remaining_pct == 100.0
        assert state.status == BudgetStatus.HEALTHY

    def test_get_error_budget_state_with_data(self, service):
        """Test getting error budget state with data."""
        # Record some metrics
        for _ in range(90):
            service.record_latency("api_latency_p99", 100.0)
        for _ in range(10):
            service.record_latency("api_latency_p99", 600.0)

        state = service.get_error_budget_state("api_latency_p99")

        assert state.total_events == 100
        assert state.good_events == 90
        assert state.bad_events == 10
        assert state.current_sli == 90.0  # 90% good

    def test_budget_status_healthy(self, service):
        """Test budget status is healthy with good metrics."""
        for _ in range(100):
            service.record_latency("api_latency_p99", 100.0)

        state = service.get_error_budget_state("api_latency_p99")
        assert state.status == BudgetStatus.HEALTHY

    def test_budget_status_exhausted(self, service):
        """Test budget status is exhausted with bad metrics."""
        for _ in range(50):
            service.record_latency("api_latency_p99", 600.0)

        state = service.get_error_budget_state("api_latency_p99")
        assert state.status == BudgetStatus.EXHAUSTED

    def test_get_all_slo_states(self, service):
        """Test getting all SLO states."""
        states = service.get_all_slo_states()

        assert len(states) >= 6
        assert "api_latency_p99" in states
        assert "api_availability" in states

    def test_get_dashboard_summary(self, service):
        """Test getting dashboard summary."""
        summary = service.get_dashboard_summary()

        assert "timestamp" in summary
        assert "total_slos" in summary
        assert "summary" in summary
        assert "overall_health" in summary
        assert summary["summary"]["healthy"] >= 0
        assert summary["summary"]["warning"] >= 0
        assert summary["summary"]["critical"] >= 0
        assert summary["summary"]["exhausted"] >= 0

    def test_list_slos(self, service):
        """Test listing SLOs."""
        slos = service.list_slos()

        assert len(slos) >= 6
        for slo in slos:
            assert "name" in slo
            assert "type" in slo
            assert "target" in slo
            assert "window_hours" in slo

    def test_clear_alerts(self, service):
        """Test clearing alerts."""
        count = service.clear_alerts()
        assert count >= 0

    def test_unknown_slo(self, service):
        """Test operations on unknown SLO."""
        result = service.record_latency("unknown_slo", 100.0)
        assert result is False

        state = service.get_error_budget_state("unknown_slo")
        assert state is None


class TestGlobalService:
    """Test global service instance."""

    def test_get_slo_service(self):
        """Test getting global service instance."""
        svc1 = get_slo_service()
        svc2 = get_slo_service()

        assert svc1 is svc2  # Same instance
        assert isinstance(svc1, SLOErrorBudgetService)
