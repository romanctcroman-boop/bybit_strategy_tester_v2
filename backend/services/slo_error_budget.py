"""
SLO Error Budget Service.

Tracks Service Level Objectives and Error Budgets for:
- API latency (p50, p95, p99)
- Error rates
- Availability
- Throughput

Provides burn rate alerts when error budget is being consumed too fast.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SLOType(str, Enum):
    """Types of SLOs supported."""

    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    THROUGHPUT = "throughput"


class BudgetStatus(str, Enum):
    """Error budget consumption status."""

    HEALTHY = "healthy"  # < 50% consumed
    WARNING = "warning"  # 50-80% consumed
    CRITICAL = "critical"  # 80-100% consumed
    EXHAUSTED = "exhausted"  # > 100% consumed


@dataclass
class SLODefinition:
    """Definition of a Service Level Objective."""

    name: str
    slo_type: SLOType
    target: float  # Target value (e.g., 99.9 for availability, 500 for latency_ms)
    window_hours: int = 24 * 7  # Default: 7-day window
    description: str = ""

    # For latency SLOs: threshold in ms
    # For error_rate: max error percentage (e.g., 0.1 for 0.1%)
    # For availability: target percentage (e.g., 99.9)
    # For throughput: minimum requests per second


@dataclass
class SLOMetric:
    """A single SLO metric data point."""

    timestamp: datetime
    value: float
    is_good: bool  # Did this event meet the SLO?
    endpoint: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ErrorBudgetState:
    """Current state of error budget for an SLO."""

    slo_name: str
    total_events: int
    good_events: int
    bad_events: int
    current_sli: float  # Current Service Level Indicator
    target_slo: float
    error_budget_total: float  # Total allowed bad events
    error_budget_remaining: float  # Remaining bad events allowed
    error_budget_remaining_pct: float
    burn_rate_1h: float  # How fast budget is being consumed (1 = normal)
    burn_rate_6h: float
    burn_rate_24h: float
    status: BudgetStatus
    time_until_exhausted: timedelta | None
    window_start: datetime
    window_end: datetime


@dataclass
class BurnRateAlert:
    """Alert for high burn rate."""

    slo_name: str
    severity: str  # critical, warning
    burn_rate: float
    window: str
    message: str
    timestamp: datetime
    budget_remaining_pct: float


class SLOErrorBudgetService:
    """
    Service for tracking SLOs and Error Budgets.

    Features:
    - Define multiple SLOs per service
    - Track real-time SLI metrics
    - Calculate error budget remaining
    - Burn rate calculations for alerting
    - Multi-window burn rate alerts
    """

    # Default SLO definitions for trading platform
    DEFAULT_SLOS = [
        SLODefinition(
            name="api_latency_p99",
            slo_type=SLOType.LATENCY_P99,
            target=500.0,  # 500ms
            window_hours=24 * 7,
            description="99th percentile API latency should be under 500ms",
        ),
        SLODefinition(
            name="api_latency_p95",
            slo_type=SLOType.LATENCY_P95,
            target=200.0,  # 200ms
            window_hours=24 * 7,
            description="95th percentile API latency should be under 200ms",
        ),
        SLODefinition(
            name="api_error_rate",
            slo_type=SLOType.ERROR_RATE,
            target=0.1,  # 0.1% error rate
            window_hours=24 * 7,
            description="API error rate should be under 0.1%",
        ),
        SLODefinition(
            name="api_availability",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,  # 99.9% availability
            window_hours=24 * 7,
            description="API should be available 99.9% of the time",
        ),
        SLODefinition(
            name="bybit_api_latency",
            slo_type=SLOType.LATENCY_P99,
            target=2000.0,  # 2s for external API
            window_hours=24 * 7,
            description="Bybit API calls should complete within 2s",
        ),
        SLODefinition(
            name="ai_agent_latency",
            slo_type=SLOType.LATENCY_P99,
            target=30000.0,  # 30s for AI operations
            window_hours=24 * 7,
            description="AI agent operations should complete within 30s",
        ),
    ]

    def __init__(self, max_events_per_slo: int = 100000):
        """Initialize SLO Error Budget Service."""
        self._slos: dict[str, SLODefinition] = {}
        self._metrics: dict[str, deque[SLOMetric]] = {}
        self._max_events = max_events_per_slo
        self._alerts: list[BurnRateAlert] = []
        self._last_alert_time: dict[str, datetime] = {}
        self._alert_cooldown = timedelta(minutes=15)

        # Initialize default SLOs
        for slo in self.DEFAULT_SLOS:
            self.register_slo(slo)

        logger.info(f"SLO Error Budget Service initialized with {len(self._slos)} SLOs")

    def register_slo(self, slo: SLODefinition) -> None:
        """Register a new SLO definition."""
        self._slos[slo.name] = slo
        self._metrics[slo.name] = deque(maxlen=self._max_events)
        logger.debug(f"Registered SLO: {slo.name} ({slo.slo_type.value})")

    def record_latency(
        self,
        slo_name: str,
        latency_ms: float,
        endpoint: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """
        Record a latency metric for an SLO.

        Returns True if the metric met the SLO target.
        """
        if slo_name not in self._slos:
            logger.warning(f"Unknown SLO: {slo_name}")
            return False

        slo = self._slos[slo_name]
        is_good = latency_ms <= slo.target

        metric = SLOMetric(
            timestamp=datetime.now(UTC),
            value=latency_ms,
            is_good=is_good,
            endpoint=endpoint,
            metadata=metadata or {},
        )

        self._metrics[slo_name].append(metric)
        self._check_burn_rate_alerts(slo_name)

        return is_good

    def record_success(
        self, slo_name: str, endpoint: str = "", metadata: dict | None = None
    ) -> None:
        """Record a successful event (for availability/error rate SLOs)."""
        if slo_name not in self._slos:
            return

        metric = SLOMetric(
            timestamp=datetime.now(UTC),
            value=1.0,
            is_good=True,
            endpoint=endpoint,
            metadata=metadata or {},
        )

        self._metrics[slo_name].append(metric)

    def record_failure(
        self,
        slo_name: str,
        endpoint: str = "",
        error: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Record a failed event (for availability/error rate SLOs)."""
        if slo_name not in self._slos:
            return

        meta = metadata or {}
        meta["error"] = error

        metric = SLOMetric(
            timestamp=datetime.now(UTC),
            value=0.0,
            is_good=False,
            endpoint=endpoint,
            metadata=meta,
        )

        self._metrics[slo_name].append(metric)
        self._check_burn_rate_alerts(slo_name)

    def get_error_budget_state(self, slo_name: str) -> ErrorBudgetState | None:
        """Get current error budget state for an SLO."""
        if slo_name not in self._slos:
            return None

        slo = self._slos[slo_name]
        metrics = list(self._metrics[slo_name])

        if not metrics:
            # No data yet
            return ErrorBudgetState(
                slo_name=slo_name,
                total_events=0,
                good_events=0,
                bad_events=0,
                current_sli=100.0,
                target_slo=slo.target,
                error_budget_total=0,
                error_budget_remaining=0,
                error_budget_remaining_pct=100.0,
                burn_rate_1h=0.0,
                burn_rate_6h=0.0,
                burn_rate_24h=0.0,
                status=BudgetStatus.HEALTHY,
                time_until_exhausted=None,
                window_start=datetime.now(UTC),
                window_end=datetime.now(UTC),
            )

        # Filter metrics within window
        window_start = datetime.now(UTC) - timedelta(hours=slo.window_hours)
        window_metrics = [m for m in metrics if m.timestamp >= window_start]

        total_events = len(window_metrics)
        good_events = sum(1 for m in window_metrics if m.is_good)
        bad_events = total_events - good_events

        # Calculate SLI (Service Level Indicator)
        if slo.slo_type == SLOType.AVAILABILITY:
            current_sli = (
                (good_events / total_events * 100) if total_events > 0 else 100.0
            )
            # Error budget = allowed bad events
            error_budget_total = total_events * (1 - slo.target / 100)
        elif slo.slo_type == SLOType.ERROR_RATE:
            current_sli = (bad_events / total_events * 100) if total_events > 0 else 0.0
            error_budget_total = total_events * (slo.target / 100)
        else:
            # Latency SLOs
            current_sli = (
                (good_events / total_events * 100) if total_events > 0 else 100.0
            )
            # Assume 99.9% SLO for latency metrics
            error_budget_total = total_events * 0.001

        error_budget_remaining = max(0, error_budget_total - bad_events)
        error_budget_remaining_pct = (
            (error_budget_remaining / error_budget_total * 100)
            if error_budget_total > 0
            else 100.0
        )

        # Calculate burn rates
        burn_rate_1h = self._calculate_burn_rate(slo_name, hours=1)
        burn_rate_6h = self._calculate_burn_rate(slo_name, hours=6)
        burn_rate_24h = self._calculate_burn_rate(slo_name, hours=24)

        # Determine status
        if error_budget_remaining_pct <= 0:
            status = BudgetStatus.EXHAUSTED
        elif error_budget_remaining_pct < 20:
            status = BudgetStatus.CRITICAL
        elif error_budget_remaining_pct < 50:
            status = BudgetStatus.WARNING
        else:
            status = BudgetStatus.HEALTHY

        # Estimate time until exhausted based on current burn rate
        time_until_exhausted = None
        if burn_rate_1h > 0 and error_budget_remaining > 0:
            hours_remaining = error_budget_remaining / burn_rate_1h
            time_until_exhausted = timedelta(hours=hours_remaining)

        return ErrorBudgetState(
            slo_name=slo_name,
            total_events=total_events,
            good_events=good_events,
            bad_events=bad_events,
            current_sli=round(current_sli, 3),
            target_slo=slo.target,
            error_budget_total=round(error_budget_total, 2),
            error_budget_remaining=round(error_budget_remaining, 2),
            error_budget_remaining_pct=round(error_budget_remaining_pct, 2),
            burn_rate_1h=round(burn_rate_1h, 3),
            burn_rate_6h=round(burn_rate_6h, 3),
            burn_rate_24h=round(burn_rate_24h, 3),
            status=status,
            time_until_exhausted=time_until_exhausted,
            window_start=window_start,
            window_end=datetime.now(UTC),
        )

    def _calculate_burn_rate(self, slo_name: str, hours: int) -> float:
        """
        Calculate burn rate for a time window.

        Burn rate = 1 means consuming budget at expected rate
        Burn rate = 2 means consuming 2x faster than expected
        """
        if slo_name not in self._slos:
            return 0.0

        slo = self._slos[slo_name]
        metrics = list(self._metrics[slo_name])

        if not metrics:
            return 0.0

        window_start = datetime.now(UTC) - timedelta(hours=hours)
        window_metrics = [m for m in metrics if m.timestamp >= window_start]

        if not window_metrics:
            return 0.0

        total = len(window_metrics)
        bad = sum(1 for m in window_metrics if not m.is_good)

        # Expected error rate based on SLO
        if slo.slo_type == SLOType.AVAILABILITY:
            expected_error_rate = 1 - (slo.target / 100)  # e.g., 0.001 for 99.9%
        elif slo.slo_type == SLOType.ERROR_RATE:
            expected_error_rate = slo.target / 100
        else:
            expected_error_rate = 0.001  # 0.1% for latency SLOs

        actual_error_rate = bad / total if total > 0 else 0

        if expected_error_rate == 0:
            return float("inf") if actual_error_rate > 0 else 0.0

        return actual_error_rate / expected_error_rate

    def _check_burn_rate_alerts(self, slo_name: str) -> None:
        """Check if burn rate alerts should be triggered."""
        state = self.get_error_budget_state(slo_name)
        if not state:
            return

        now = datetime.now(UTC)
        last_alert = self._last_alert_time.get(slo_name)

        if last_alert and (now - last_alert) < self._alert_cooldown:
            return

        alert = None

        # Critical: 14.4x burn rate over 1 hour (burns 100% in 2.5 days)
        if state.burn_rate_1h >= 14.4:
            alert = BurnRateAlert(
                slo_name=slo_name,
                severity="critical",
                burn_rate=state.burn_rate_1h,
                window="1h",
                message=f"Critical: {slo_name} burn rate is {state.burn_rate_1h:.1f}x over 1h",
                timestamp=now,
                budget_remaining_pct=state.error_budget_remaining_pct,
            )
        # Warning: 6x burn rate over 6 hours
        elif state.burn_rate_6h >= 6.0:
            alert = BurnRateAlert(
                slo_name=slo_name,
                severity="warning",
                burn_rate=state.burn_rate_6h,
                window="6h",
                message=f"Warning: {slo_name} burn rate is {state.burn_rate_6h:.1f}x over 6h",
                timestamp=now,
                budget_remaining_pct=state.error_budget_remaining_pct,
            )

        if alert:
            self._alerts.append(alert)
            self._last_alert_time[slo_name] = now
            logger.warning(alert.message)

    def get_all_slo_states(self) -> dict[str, ErrorBudgetState]:
        """Get error budget states for all SLOs."""
        states = {}
        for slo_name in self._slos:
            state = self.get_error_budget_state(slo_name)
            if state:
                states[slo_name] = state
        return states

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get summary for dashboard display."""
        states = self.get_all_slo_states()

        healthy = sum(1 for s in states.values() if s.status == BudgetStatus.HEALTHY)
        warning = sum(1 for s in states.values() if s.status == BudgetStatus.WARNING)
        critical = sum(1 for s in states.values() if s.status == BudgetStatus.CRITICAL)
        exhausted = sum(
            1 for s in states.values() if s.status == BudgetStatus.EXHAUSTED
        )

        # Find most critical SLOs
        critical_slos = [
            {
                "name": s.slo_name,
                "budget_remaining_pct": s.error_budget_remaining_pct,
                "burn_rate_1h": s.burn_rate_1h,
                "status": s.status.value,
            }
            for s in states.values()
            if s.status in [BudgetStatus.CRITICAL, BudgetStatus.EXHAUSTED]
        ]

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_slos": len(states),
            "summary": {
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "exhausted": exhausted,
            },
            "overall_health": (
                "critical"
                if exhausted > 0 or critical > 0
                else "warning"
                if warning > 0
                else "healthy"
            ),
            "critical_slos": critical_slos,
            "recent_alerts": [
                {
                    "slo_name": a.slo_name,
                    "severity": a.severity,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in sorted(self._alerts, key=lambda x: x.timestamp, reverse=True)[
                    :10
                ]
            ],
        }

    def list_slos(self) -> list[dict[str, Any]]:
        """List all registered SLOs."""
        return [
            {
                "name": slo.name,
                "type": slo.slo_type.value,
                "target": slo.target,
                "window_hours": slo.window_hours,
                "description": slo.description,
            }
            for slo in self._slos.values()
        ]

    def clear_alerts(self) -> int:
        """Clear all alerts. Returns count of cleared alerts."""
        count = len(self._alerts)
        self._alerts.clear()
        self._last_alert_time.clear()
        return count


# Global instance
_slo_service: SLOErrorBudgetService | None = None


def get_slo_service() -> SLOErrorBudgetService:
    """Get or create the global SLO Error Budget service instance."""
    global _slo_service
    if _slo_service is None:
        _slo_service = SLOErrorBudgetService()
    return _slo_service
