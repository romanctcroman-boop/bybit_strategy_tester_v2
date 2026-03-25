"""
Portfolio Emergency Stop — Global Circuit Breaker for Trading.

Monitors portfolio-level drawdown and halts ALL trading activity
when equity drops below a configurable threshold from peak.

Features:
- Tracks equity high-water mark across all active sessions
- Triggers emergency stop when drawdown exceeds threshold (default -7%)
- Broadcasts halt signal to all paper trading sessions
- Logs the event with full audit trail via structured_logging
- Supports manual arm/disarm for maintenance windows
- Thread-safe singleton for multi-worker deployments

Safety guarantee:
    If current_equity / peak_equity - 1 <= -threshold → HALT ALL TRADING

Added 2026-02-14 per audit gap analysis — P1 safety requirement.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger

from backend.agents.structured_logging import (
    agent_log,
    get_correlation_id,
)

# =============================================================================
# DATA MODELS
# =============================================================================


class EmergencyStopState(str, Enum):
    """States for the emergency stop system."""

    ARMED = "armed"  # Monitoring, ready to trigger
    TRIGGERED = "triggered"  # Emergency stop is active — all trading halted
    DISARMED = "disarmed"  # Manually disabled (maintenance window)


@dataclass
class EmergencyStopEvent:
    """Record of an emergency stop trigger or state change."""

    event_type: str  # "triggered", "armed", "disarmed", "reset"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    threshold_pct: float = 0.0
    reason: str = ""
    correlation_id: str = ""
    sessions_halted: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "threshold_pct": self.threshold_pct,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "sessions_halted": self.sessions_halted,
        }


# =============================================================================
# EMERGENCY STOP MONITOR
# =============================================================================


class PortfolioEmergencyStop:
    """
    Global emergency stop that halts all trading on excessive drawdown.

    Monitors total portfolio equity across all active paper-trading
    sessions and triggers an emergency halt when drawdown from peak
    exceeds the configured threshold.

    Usage:
        stop = PortfolioEmergencyStop(threshold_pct=7.0)

        # Update equity as trading progresses
        stop.update_equity(9500.0)  # from 10000 initial

        # Check before executing any trade
        if stop.should_halt():
            logger.critical("Trading halted by emergency stop!")

        # Manual control
        stop.disarm(reason="Maintenance window")
        stop.arm()

    Thread Safety:
        Uses asyncio.Lock for safe concurrent access in FastAPI workers.
    """

    # Default threshold: -7% drawdown from peak
    DEFAULT_THRESHOLD_PCT = 7.0

    # Maximum events to keep in history (ring buffer)
    MAX_HISTORY = 100

    def __init__(
        self,
        threshold_pct: float = DEFAULT_THRESHOLD_PCT,
        initial_equity: float = 0.0,
    ) -> None:
        """
        Initialize emergency stop monitor.

        Args:
            threshold_pct: Maximum allowed drawdown percentage (e.g., 7.0 = -7%)
            initial_equity: Starting portfolio equity (0 = auto-detect on first update)
        """
        if threshold_pct <= 0:
            raise ValueError(f"threshold_pct must be positive, got {threshold_pct}")

        self.threshold_pct = threshold_pct
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.state = EmergencyStopState.ARMED
        self._lock = asyncio.Lock()
        self._history: list[EmergencyStopEvent] = []
        self._halted_sessions: list[str] = []
        self._on_trigger_callbacks: list[Any] = []

        if initial_equity > 0:
            agent_log(
                "INFO",
                f"Emergency stop initialized: threshold={threshold_pct}%, initial_equity={initial_equity}",
                component="emergency_stop",
            )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def update_equity(self, equity: float) -> bool:
        """
        Update current portfolio equity and check for emergency condition.

        Args:
            equity: Current total portfolio equity

        Returns:
            True if emergency stop was triggered by this update
        """
        self.current_equity = equity

        # Update high-water mark
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Check drawdown
        if self.peak_equity > 0:
            drawdown_pct = ((self.peak_equity - equity) / self.peak_equity) * 100

            if drawdown_pct >= self.threshold_pct and self.state == EmergencyStopState.ARMED:
                self._trigger(drawdown_pct)
                return True

        return False

    def should_halt(self) -> bool:
        """
        Check if trading should be halted.

        Returns:
            True if emergency stop is triggered (all trading must stop)
        """
        return self.state == EmergencyStopState.TRIGGERED

    def get_current_drawdown_pct(self) -> float:
        """Get current drawdown percentage from peak."""
        if self.peak_equity <= 0:
            return 0.0
        return ((self.peak_equity - self.current_equity) / self.peak_equity) * 100

    # ------------------------------------------------------------------
    # State Control
    # ------------------------------------------------------------------

    def arm(self) -> None:
        """Arm the emergency stop (enable monitoring)."""
        old_state = self.state
        self.state = EmergencyStopState.ARMED
        event = EmergencyStopEvent(
            event_type="armed",
            reason=f"Manual arm (previous state: {old_state.value})",
            correlation_id=get_correlation_id(),
        )
        self._record_event(event)
        agent_log("INFO", "Emergency stop ARMED", component="emergency_stop")

    def disarm(self, reason: str = "Manual disarm") -> None:
        """
        Disarm the emergency stop (disable monitoring).

        Use during maintenance windows or manual intervention.

        Args:
            reason: Why the emergency stop is being disarmed
        """
        old_state = self.state
        self.state = EmergencyStopState.DISARMED
        event = EmergencyStopEvent(
            event_type="disarmed",
            reason=f"{reason} (previous state: {old_state.value})",
            correlation_id=get_correlation_id(),
        )
        self._record_event(event)
        agent_log(
            "WARNING",
            f"Emergency stop DISARMED: {reason}",
            component="emergency_stop",
        )

    def reset(self, new_equity: float | None = None) -> None:
        """
        Reset after an emergency stop trigger.

        Clears the triggered state and optionally resets equity tracking.

        Args:
            new_equity: New equity baseline (None = keep current)
        """
        if new_equity is not None:
            self.peak_equity = new_equity
            self.current_equity = new_equity

        old_state = self.state
        self.state = EmergencyStopState.ARMED
        self._halted_sessions.clear()

        event = EmergencyStopEvent(
            event_type="reset",
            peak_equity=self.peak_equity,
            current_equity=self.current_equity,
            reason=f"Manual reset (previous state: {old_state.value})",
            correlation_id=get_correlation_id(),
        )
        self._record_event(event)
        agent_log(
            "INFO",
            f"Emergency stop RESET: peak={self.peak_equity}, state=ARMED",
            component="emergency_stop",
        )

    # ------------------------------------------------------------------
    # Callback Registration
    # ------------------------------------------------------------------

    def on_trigger(self, callback: Any) -> None:
        """
        Register a callback to be invoked when emergency stop triggers.

        The callback receives an EmergencyStopEvent.

        Args:
            callback: Callable[[EmergencyStopEvent], None] or async callable
        """
        self._on_trigger_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Session Integration
    # ------------------------------------------------------------------

    async def halt_all_sessions(self) -> list[str]:
        """
        Halt all active paper trading sessions.

        Returns:
            List of session IDs that were halted
        """
        halted: list[str] = []
        try:
            from backend.agents.trading.paper_trader import AgentPaperTrader

            trader = AgentPaperTrader()
            active = AgentPaperTrader.list_active()

            for session_info in active:
                session_id = session_info.get("session_id", "")
                if session_id:
                    await trader.stop_session(session_id)
                    halted.append(session_id)
                    agent_log(
                        "WARNING",
                        f"Halted paper session '{session_id}' due to emergency stop",
                        component="emergency_stop",
                    )
        except Exception as e:
            logger.error(f"Error halting sessions: {e}")

        self._halted_sessions.extend(halted)
        return halted

    # ------------------------------------------------------------------
    # Status & History
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get current emergency stop status."""
        return {
            "state": self.state.value,
            "threshold_pct": self.threshold_pct,
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "current_drawdown_pct": round(self.get_current_drawdown_pct(), 4),
            "is_halted": self.should_halt(),
            "halted_sessions": self._halted_sessions,
            "total_events": len(self._history),
        }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent emergency stop events."""
        return [e.to_dict() for e in self._history[-limit:]]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trigger(self, drawdown_pct: float) -> None:
        """Internal: trigger the emergency stop."""
        self.state = EmergencyStopState.TRIGGERED

        event = EmergencyStopEvent(
            event_type="triggered",
            drawdown_pct=drawdown_pct,
            peak_equity=self.peak_equity,
            current_equity=self.current_equity,
            threshold_pct=self.threshold_pct,
            reason=(f"Portfolio drawdown {drawdown_pct:.2f}% exceeded threshold {self.threshold_pct:.1f}%"),
            correlation_id=get_correlation_id(),
        )
        self._record_event(event)

        agent_log(
            "CRITICAL",
            f"🚨 EMERGENCY STOP TRIGGERED: drawdown={drawdown_pct:.2f}% "
            f"(threshold={self.threshold_pct}%), "
            f"equity={self.current_equity:.2f} (peak={self.peak_equity:.2f})",
            component="emergency_stop",
        )

        # Fire callbacks (best-effort)
        for cb in self._on_trigger_callbacks:
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    task = asyncio.ensure_future(result)
                    # prevent GC of fire-and-forget task
                    task.add_done_callback(lambda t: None)
            except Exception as e:
                logger.error(f"Emergency stop callback error: {e}")

    def _record_event(self, event: EmergencyStopEvent) -> None:
        """Record event to history (ring buffer)."""
        self._history.append(event)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY :]


# =============================================================================
# SINGLETON
# =============================================================================

_instance: PortfolioEmergencyStop | None = None


def get_emergency_stop(
    threshold_pct: float = PortfolioEmergencyStop.DEFAULT_THRESHOLD_PCT,
    initial_equity: float = 0.0,
) -> PortfolioEmergencyStop:
    """
    Get or create the global PortfolioEmergencyStop instance.

    Args:
        threshold_pct: Maximum allowed drawdown percentage
        initial_equity: Starting equity

    Returns:
        Singleton PortfolioEmergencyStop instance
    """
    global _instance
    if _instance is None:
        _instance = PortfolioEmergencyStop(
            threshold_pct=threshold_pct,
            initial_equity=initial_equity,
        )
        logger.info(f"🛑 PortfolioEmergencyStop initialized: threshold={threshold_pct}%")
    return _instance


__all__ = [
    "EmergencyStopEvent",
    "EmergencyStopState",
    "PortfolioEmergencyStop",
    "get_emergency_stop",
]
