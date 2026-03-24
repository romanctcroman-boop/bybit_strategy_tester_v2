"""
Prompts Alerting Service

Monitors AI prompt system and sends alerts for:
- High validation failure rate
- Injection attempts detected
- High cost threshold exceeded
- Low cache hit rate
- Service degradation

Usage:
    from backend.monitoring.prompts_alerting import PromptsAlerting
    alerting = PromptsAlerting()
    alerts = alerting.check_alerts()
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert types."""

    VALIDATION_FAILURE = "validation_failure"
    INJECTION_ATTEMPT = "injection_attempt"
    HIGH_COST = "high_cost"
    LOW_CACHE_HIT = "low_cache_hit"
    SERVICE_DEGRADATION = "service_degradation"
    HIGH_FAILURE_RATE = "high_failure_rate"


@dataclass
class Alert:
    """Alert object."""

    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


@dataclass
class AlertConfig:
    """Alerting configuration."""

    # Validation failure threshold (%)
    validation_failure_threshold: float = 0.05  # 5%

    # Injection attempt alert (any attempt)
    injection_attempt_alert: bool = True

    # Cost thresholds (USD)
    hourly_cost_threshold: float = 1.0
    daily_cost_threshold: float = 10.0
    monthly_cost_threshold: float = 100.0

    # Cache hit rate threshold (%)
    min_cache_hit_rate: float = 0.5  # 50%

    # Service failure rate threshold (%)
    max_failure_rate: float = 0.1  # 10%

    # Alert callbacks
    on_alert: Callable[[Alert], None] | None = None

    # Alert storage
    alert_log_path: str = "data/prompts_alerts.json"


class PromptsAlerting:
    """
    Alerting service for AI prompt system.

    Monitors:
    - Validation failures
    - Injection attempts
    - Cost thresholds
    - Cache performance
    - Service health

    Example:
        alerting = PromptsAlerting()
        alerts = alerting.check_alerts()

        for alert in alerts:
            print(f"[{alert.severity}] {alert.message}")
    """

    def __init__(self, config: AlertConfig | None = None):
        """
        Initialize alerting service.

        Args:
            config: Alerting configuration
        """
        self.config = config or AlertConfig()
        self._active_alerts: list[Alert] = []
        self._alert_history: list[Alert] = []

        logger.info("🚨 PromptsAlerting initialized")

    def check_alerts(self) -> list[Alert]:
        """
        Check all alert conditions.

        Returns:
            List of triggered alerts
        """
        alerts = []

        # Check validation failures
        validation_alerts = self._check_validation_failures()
        alerts.extend(validation_alerts)

        # Check injection attempts
        injection_alerts = self._check_injection_attempts()
        alerts.extend(injection_alerts)

        # Check cost thresholds
        cost_alerts = self._check_cost_thresholds()
        alerts.extend(cost_alerts)

        # Check cache performance
        cache_alerts = self._check_cache_performance()
        alerts.extend(cache_alerts)

        # Check service health
        health_alerts = self._check_service_health()
        alerts.extend(health_alerts)

        # Store alerts
        self._active_alerts = alerts
        self._alert_history.extend(alerts)

        # Trigger callbacks
        if self.config.on_alert:
            for alert in alerts:
                self.config.on_alert(alert)

        # Log alerts
        for alert in alerts:
            self._log_alert(alert)

        return alerts

    def _check_validation_failures(self) -> list[Alert]:
        """Check validation failure rate."""
        try:
            from backend.monitoring.prompts_monitor import PromptsMonitor

            monitor = PromptsMonitor()

            stats = monitor.get_validation_stats(period_hours=1)

            total = stats.get("total_prompts", 0)
            failed = stats.get("failed", 0)

            if total == 0:
                return []

            failure_rate = failed / total

            if failure_rate > self.config.validation_failure_threshold:
                alert = Alert(
                    alert_id=f"val_fail_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.VALIDATION_FAILURE,
                    severity=AlertSeverity.WARNING,
                    message=f"High validation failure rate: {failure_rate:.0%} (threshold: {self.config.validation_failure_threshold:.0%})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "total_prompts": total,
                        "failed_validations": failed,
                        "failure_rate": failure_rate,
                        "threshold": self.config.validation_failure_threshold,
                        "period_hours": 1,
                    },
                )
                return [alert]
        except Exception as e:
            logger.error(f"Failed to check validation failures: {e}")

        return []

    def _check_injection_attempts(self) -> list[Alert]:
        """Check for injection attempts."""
        try:
            from backend.monitoring.prompts_monitor import PromptsMonitor

            monitor = PromptsMonitor()

            stats = monitor.get_validation_stats(period_hours=1)
            injection_attempts = stats.get("injection_attempts_blocked", 0)

            if self.config.injection_attempt_alert and injection_attempts > 0:
                alert = Alert(
                    alert_id=f"inj_attempt_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.INJECTION_ATTEMPT,
                    severity=AlertSeverity.CRITICAL,
                    message=f"🚨 {injection_attempts} prompt injection attempt(s) detected!",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "injection_attempts": injection_attempts,
                        "period_hours": 1,
                    },
                )
                return [alert]
        except Exception as e:
            logger.error(f"Failed to check injection attempts: {e}")

        return []

    def _check_cost_thresholds(self) -> list[Alert]:
        """Check cost thresholds."""
        try:
            from backend.monitoring.prompts_monitor import PromptsMonitor

            monitor = PromptsMonitor()

            # Hourly cost
            hourly_cost = monitor.get_cost_breakdown(period_hours=1)
            total_hourly = hourly_cost.get("total_cost_usd", 0)

            if total_hourly > self.config.hourly_cost_threshold:
                alert = Alert(
                    alert_id=f"cost_hourly_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.HIGH_COST,
                    severity=AlertSeverity.WARNING,
                    message=f"High hourly cost: ${total_hourly:.2f} (threshold: ${self.config.hourly_cost_threshold:.2f})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "hourly_cost": total_hourly,
                        "threshold": self.config.hourly_cost_threshold,
                    },
                )
                return [alert]

            # Daily cost
            daily_cost = monitor.get_cost_breakdown(period_hours=24)
            total_daily = daily_cost.get("total_cost_usd", 0)

            if total_daily > self.config.daily_cost_threshold:
                alert = Alert(
                    alert_id=f"cost_daily_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.HIGH_COST,
                    severity=AlertSeverity.ERROR,
                    message=f"High daily cost: ${total_daily:.2f} (threshold: ${self.config.daily_cost_threshold:.2f})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "daily_cost": total_daily,
                        "threshold": self.config.daily_cost_threshold,
                    },
                )
                return [alert]

            # Monthly projection
            projected = daily_cost.get("projected_monthly_cost", 0)

            if projected > self.config.monthly_cost_threshold:
                alert = Alert(
                    alert_id=f"cost_monthly_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.HIGH_COST,
                    severity=AlertSeverity.WARNING,
                    message=f"High projected monthly cost: ${projected:.2f} (threshold: ${self.config.monthly_cost_threshold:.2f})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "projected_monthly_cost": projected,
                        "threshold": self.config.monthly_cost_threshold,
                    },
                )
                return [alert]
        except Exception as e:
            logger.error(f"Failed to check cost thresholds: {e}")

        return []

    def _check_cache_performance(self) -> list[Alert]:
        """Check cache hit rate."""
        try:
            from backend.monitoring.prompts_monitor import PromptsMonitor

            monitor = PromptsMonitor()

            cache_stats = monitor.get_cache_stats()
            hit_rate = cache_stats.get("cache_hit_rate", 0)

            # Skip alert if no cache activity yet — avoid false alarms on startup
            total_ops = cache_stats.get("cache_hits", 0) + cache_stats.get("cache_misses", 0)
            if total_ops == 0:
                return []

            if hit_rate < self.config.min_cache_hit_rate:
                alert = Alert(
                    alert_id=f"cache_low_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.LOW_CACHE_HIT,
                    severity=AlertSeverity.WARNING,
                    message=f"Low cache hit rate: {hit_rate:.0%} (minimum: {self.config.min_cache_hit_rate:.0%})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "cache_hit_rate": hit_rate,
                        "minimum": self.config.min_cache_hit_rate,
                        "cache_size": cache_stats.get("cache_size", 0),
                    },
                )
                return [alert]
        except Exception as e:
            logger.error(f"Failed to check cache performance: {e}")

        return []

    def _check_service_health(self) -> list[Alert]:
        """Check service health."""
        try:
            from backend.monitoring.prompts_monitor import PromptsMonitor

            monitor = PromptsMonitor()

            # Check logging stats
            logging_stats = monitor.get_logging_stats(period_hours=1)
            success_rate = logging_stats.get("success_rate", 1.0)

            if success_rate < (1 - self.config.max_failure_rate):
                failure_rate = 1 - success_rate
                alert = Alert(
                    alert_id=f"service_health_{datetime.now(UTC).isoformat()}",
                    alert_type=AlertType.SERVICE_DEGRADATION,
                    severity=AlertSeverity.ERROR,
                    message=f"High service failure rate: {failure_rate:.0%} (maximum: {self.config.max_failure_rate:.0%})",
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "failure_rate": failure_rate,
                        "maximum": self.config.max_failure_rate,
                        "success_rate": success_rate,
                    },
                )
                return [alert]
        except Exception as e:
            logger.error(f"Failed to check service health: {e}")

        return []

    def _log_alert(self, alert: Alert) -> None:
        """Log alert to file."""
        try:
            alert_path = Path(self.config.alert_log_path)
            alert_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing alerts
            alerts = []
            if alert_path.exists():
                with open(alert_path, encoding="utf-8") as f:
                    alerts = json.load(f)

            # Add new alert
            alerts.append(alert.to_dict())

            # Keep only last 1000 alerts
            alerts = alerts[-1000:]

            # Save
            with open(alert_path, "w", encoding="utf-8") as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False)

            logger.info(f"🚨 Alert logged: {alert.alert_type.value} - {alert.severity.value}")
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

    def get_active_alerts(self) -> list[Alert]:
        """Get active (unresolved) alerts."""
        return [a for a in self._active_alerts if not a.resolved]

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get alert history."""
        return self._alert_history[-limit:]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._active_alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self._active_alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                return True
        return False

    def clear_resolved_alerts(self) -> int:
        """Clear resolved alerts."""
        count = len([a for a in self._active_alerts if a.resolved])
        self._active_alerts = [a for a in self._active_alerts if not a.resolved]
        return count

    def get_alert_summary(self) -> dict[str, Any]:
        """Get alert summary."""
        active = self.get_active_alerts()

        by_severity = {}
        by_type = {}

        for alert in active:
            # By severity
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

            # By type
            typ = alert.alert_type.value
            by_type[typ] = by_type.get(typ, 0) + 1

        return {
            "total_active": len(active),
            "by_severity": by_severity,
            "by_type": by_type,
            "total_history": len(self._alert_history),
        }
