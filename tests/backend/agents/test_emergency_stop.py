"""
Tests for PortfolioEmergencyStop — portfolio-level circuit breaker.

Tests cover:
- Initialization with valid/invalid thresholds
- Equity tracking and high-water mark updates
- Emergency trigger when drawdown exceeds threshold
- State transitions: armed → triggered → reset → armed
- Disarm/arm manual control
- should_halt() behavior in each state
- Callback registration and invocation on trigger
- History recording (ring buffer)
- Singleton behavior
- Edge cases (zero equity, negative values)
"""

from __future__ import annotations

import pytest

from backend.agents.trading.emergency_stop import (
    EmergencyStopEvent,
    EmergencyStopState,
    PortfolioEmergencyStop,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def estop() -> PortfolioEmergencyStop:
    """Fresh emergency stop with 7% threshold and 10000 initial equity."""
    return PortfolioEmergencyStop(threshold_pct=7.0, initial_equity=10000.0)


@pytest.fixture
def estop_5pct() -> PortfolioEmergencyStop:
    """Emergency stop with 5% threshold."""
    return PortfolioEmergencyStop(threshold_pct=5.0, initial_equity=10000.0)


# =============================================================================
# INITIALIZATION
# =============================================================================


class TestEmergencyStopInit:
    """Tests for initialization."""

    def test_init_default_threshold(self):
        """Default threshold is 7%."""
        estop = PortfolioEmergencyStop()
        assert estop.threshold_pct == 7.0

    def test_init_custom_threshold(self):
        """Custom threshold is stored."""
        estop = PortfolioEmergencyStop(threshold_pct=5.0)
        assert estop.threshold_pct == 5.0

    def test_init_with_initial_equity(self):
        """Initial equity sets peak and current."""
        estop = PortfolioEmergencyStop(initial_equity=10000.0)
        assert estop.peak_equity == 10000.0
        assert estop.current_equity == 10000.0

    def test_init_invalid_threshold_raises(self):
        """Zero or negative threshold raises ValueError."""
        with pytest.raises(ValueError, match="threshold_pct must be positive"):
            PortfolioEmergencyStop(threshold_pct=0.0)
        with pytest.raises(ValueError, match="threshold_pct must be positive"):
            PortfolioEmergencyStop(threshold_pct=-5.0)

    def test_init_state_is_armed(self):
        """Initial state is ARMED."""
        estop = PortfolioEmergencyStop()
        assert estop.state == EmergencyStopState.ARMED


# =============================================================================
# EQUITY TRACKING
# =============================================================================


class TestEquityTracking:
    """Tests for equity updates and high-water mark."""

    def test_update_equity_updates_current(self, estop):
        """update_equity sets current_equity."""
        estop.update_equity(9500.0)
        assert estop.current_equity == 9500.0

    def test_update_equity_updates_peak_upward(self, estop):
        """Peak equity tracks the high-water mark."""
        estop.update_equity(10500.0)
        assert estop.peak_equity == 10500.0

    def test_update_equity_peak_does_not_decrease(self, estop):
        """Peak doesn't decrease when equity drops."""
        estop.update_equity(10500.0)
        estop.update_equity(9000.0)
        assert estop.peak_equity == 10500.0

    def test_get_current_drawdown_pct(self, estop):
        """Current drawdown is calculated correctly."""
        estop.update_equity(9300.0)
        dd = estop.get_current_drawdown_pct()
        assert abs(dd - 7.0) < 0.01  # 7% drawdown

    def test_get_current_drawdown_zero_when_at_peak(self, estop):
        """Drawdown is 0 at peak."""
        assert estop.get_current_drawdown_pct() == 0.0

    def test_get_current_drawdown_zero_peak(self):
        """Drawdown is 0 when peak is 0."""
        estop = PortfolioEmergencyStop(initial_equity=0.0)
        assert estop.get_current_drawdown_pct() == 0.0


# =============================================================================
# TRIGGER BEHAVIOR
# =============================================================================


class TestTrigger:
    """Tests for emergency stop triggering."""

    def test_trigger_at_threshold(self, estop):
        """Trigger fires at exactly threshold drawdown."""
        # 7% of 10000 = 700, so 9300 is the trigger point
        triggered = estop.update_equity(9300.0)
        assert triggered is True
        assert estop.state == EmergencyStopState.TRIGGERED

    def test_trigger_beyond_threshold(self, estop):
        """Trigger fires when drawdown exceeds threshold."""
        triggered = estop.update_equity(9000.0)
        assert triggered is True
        assert estop.state == EmergencyStopState.TRIGGERED

    def test_no_trigger_below_threshold(self, estop):
        """No trigger when drawdown is below threshold."""
        triggered = estop.update_equity(9500.0)
        assert triggered is False
        assert estop.state == EmergencyStopState.ARMED

    def test_trigger_only_once(self, estop):
        """Second update while triggered doesn't re-trigger."""
        estop.update_equity(9000.0)
        assert estop.state == EmergencyStopState.TRIGGERED

        # Further equity drop doesn't return True again
        triggered = estop.update_equity(8500.0)
        assert triggered is False
        assert estop.state == EmergencyStopState.TRIGGERED

    def test_trigger_records_event(self, estop):
        """Trigger records an event in history."""
        estop.update_equity(9000.0)
        history = estop.get_history()
        assert len(history) >= 1
        assert history[-1]["event_type"] == "triggered"
        assert history[-1]["drawdown_pct"] > 0

    def test_should_halt_when_triggered(self, estop):
        """should_halt returns True when triggered."""
        estop.update_equity(9000.0)
        assert estop.should_halt() is True

    def test_should_halt_when_armed(self, estop):
        """should_halt returns False when armed."""
        assert estop.should_halt() is False

    def test_trigger_with_custom_threshold(self, estop_5pct):
        """5% threshold triggers at 9500."""
        triggered = estop_5pct.update_equity(9500.0)
        assert triggered is True


# =============================================================================
# STATE CONTROL
# =============================================================================


class TestStateControl:
    """Tests for arm/disarm/reset."""

    def test_disarm(self, estop):
        """Disarm changes state to DISARMED."""
        estop.disarm(reason="Maintenance")
        assert estop.state == EmergencyStopState.DISARMED

    def test_disarm_prevents_trigger(self, estop):
        """While disarmed, drawdown doesn't trigger."""
        estop.disarm(reason="Test")
        triggered = estop.update_equity(9000.0)
        assert triggered is False
        assert estop.state == EmergencyStopState.DISARMED

    def test_arm_after_disarm(self, estop):
        """Arm re-enables monitoring."""
        estop.disarm(reason="Test")
        estop.arm()
        assert estop.state == EmergencyStopState.ARMED

    def test_reset_clears_triggered_state(self, estop):
        """Reset after trigger returns to ARMED."""
        estop.update_equity(9000.0)
        assert estop.state == EmergencyStopState.TRIGGERED

        estop.reset()
        assert estop.state == EmergencyStopState.ARMED

    def test_reset_with_new_equity(self, estop):
        """Reset with new equity resets peak and current."""
        estop.update_equity(9000.0)
        estop.reset(new_equity=9500.0)

        assert estop.peak_equity == 9500.0
        assert estop.current_equity == 9500.0
        assert estop.state == EmergencyStopState.ARMED

    def test_reset_records_event(self, estop):
        """Reset records an event in history."""
        estop.reset()
        history = estop.get_history()
        assert any(e["event_type"] == "reset" for e in history)


# =============================================================================
# CALLBACKS
# =============================================================================


class TestCallbacks:
    """Tests for trigger callbacks."""

    def test_callback_fires_on_trigger(self, estop):
        """Registered callback is called when trigger fires."""
        events_received = []
        estop.on_trigger(lambda evt: events_received.append(evt))

        estop.update_equity(9000.0)
        assert len(events_received) == 1
        assert isinstance(events_received[0], EmergencyStopEvent)
        assert events_received[0].event_type == "triggered"

    def test_multiple_callbacks(self, estop):
        """Multiple callbacks all fire."""
        counter = {"count": 0}

        def cb1(_evt):
            counter["count"] += 1

        def cb2(_evt):
            counter["count"] += 10

        estop.on_trigger(cb1)
        estop.on_trigger(cb2)

        estop.update_equity(9000.0)
        assert counter["count"] == 11

    def test_callback_error_doesnt_prevent_trigger(self, estop):
        """Callback error doesn't prevent state change."""

        def bad_callback(_evt):
            raise RuntimeError("Callback failed!")

        estop.on_trigger(bad_callback)
        estop.update_equity(9000.0)
        assert estop.state == EmergencyStopState.TRIGGERED


# =============================================================================
# STATUS & HISTORY
# =============================================================================


class TestStatus:
    """Tests for status and history."""

    def test_get_status_returns_dict(self, estop):
        """get_status returns a complete status dict."""
        status = estop.get_status()
        assert "state" in status
        assert "threshold_pct" in status
        assert "peak_equity" in status
        assert "current_equity" in status
        assert "is_halted" in status

    def test_get_status_reflects_state(self, estop):
        """Status reflects current state correctly."""
        status = estop.get_status()
        assert status["state"] == "armed"
        assert status["is_halted"] is False

        estop.update_equity(9000.0)
        status = estop.get_status()
        assert status["state"] == "triggered"
        assert status["is_halted"] is True

    def test_history_ring_buffer(self):
        """History doesn't grow beyond MAX_HISTORY."""
        estop = PortfolioEmergencyStop(initial_equity=10000.0)
        for _ in range(150):
            estop.arm()
        assert len(estop._history) <= PortfolioEmergencyStop.MAX_HISTORY


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_zero_initial_equity(self):
        """Zero initial equity doesn't crash."""
        estop = PortfolioEmergencyStop(initial_equity=0.0)
        triggered = estop.update_equity(100.0)
        assert triggered is False

    def test_equity_goes_to_zero(self, estop):
        """Equity dropping to 0 triggers."""
        triggered = estop.update_equity(0.0)
        assert triggered is True

    def test_event_to_dict(self):
        """EmergencyStopEvent.to_dict serializes correctly."""
        event = EmergencyStopEvent(
            event_type="triggered",
            drawdown_pct=8.5,
            peak_equity=10000.0,
            current_equity=9150.0,
        )
        d = event.to_dict()
        assert d["event_type"] == "triggered"
        assert d["drawdown_pct"] == 8.5
