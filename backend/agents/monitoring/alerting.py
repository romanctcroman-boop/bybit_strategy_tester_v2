"""
Alert Manager for AI Agent System

Provides alerting and anomaly detection:
- Rule-based alerts with conditions
- Severity levels and escalation
- Alert aggregation and deduplication
- Notification channels (log, webhook, etc.)
- Anomaly detection using statistical methods
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class AlertSeverity(Enum):
    """Severity levels for alerts"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(Enum):
    """State of an alert"""

    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class ComparisonOperator(Enum):
    """Operators for alert conditions"""

    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "neq"


@dataclass
class AlertRule:
    """Definition of an alert rule"""

    name: str
    description: str
    metric_name: str
    operator: ComparisonOperator
    threshold: float
    severity: AlertSeverity
    duration_seconds: int = 0  # Must be true for this duration
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def evaluate(self, value: float) -> bool:
        """Check if condition is met"""
        if self.operator == ComparisonOperator.GREATER_THAN:
            return value > self.threshold
        elif self.operator == ComparisonOperator.LESS_THAN:
            return value < self.threshold
        elif self.operator == ComparisonOperator.GREATER_EQUAL:
            return value >= self.threshold
        elif self.operator == ComparisonOperator.LESS_EQUAL:
            return value <= self.threshold
        elif self.operator == ComparisonOperator.EQUAL:
            return value == self.threshold
        elif self.operator == ComparisonOperator.NOT_EQUAL:
            return value != self.threshold
        return False


@dataclass
class Alert:
    """An active alert"""

    id: str
    rule_name: str
    severity: AlertSeverity
    state: AlertState
    message: str
    value: float
    threshold: float
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    last_evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    firing_since: datetime | None = None
    notification_sent: bool = False

    @property
    def duration_seconds(self) -> float:
        """How long the alert has been active"""
        end = self.resolved_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "state": self.state.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "labels": self.labels,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "duration_seconds": self.duration_seconds,
        }


class AlertNotifier:
    """Base class for alert notifiers"""

    async def send(self, alert: Alert) -> bool:
        """Send alert notification"""
        raise NotImplementedError


class LogNotifier(AlertNotifier):
    """Log alerts using logger"""

    async def send(self, alert: Alert) -> bool:
        severity_icons = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨",
        }

        icon = severity_icons.get(alert.severity, "📢")

        log_fn = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical,
        }.get(alert.severity, logger.info)

        log_fn(f"{icon} ALERT [{alert.rule_name}]: {alert.message} (value={alert.value:.2f})")
        return True


class WebhookNotifier(AlertNotifier):
    """Send alerts to webhook"""

    def __init__(self, url: str, headers: dict[str, str] | None = None):
        self.url = url
        self.headers = headers or {}

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    json=alert.to_dict(),
                    headers=self.headers,
                    timeout=10.0,
                )
                return response.status_code < 400
        except Exception as e:
            logger.warning(f"Webhook notification failed: {e}")
            return False


class AlertManager:
    """
    Central alert management for AI agent system

    Features:
    - Rule-based alerting with duration conditions
    - Multiple severity levels
    - Alert deduplication and aggregation
    - Pluggable notifiers
    - Anomaly detection

    Example:
        manager = AlertManager()

        # Add rule
        manager.add_rule(AlertRule(
            name="high_error_rate",
            description="Error rate exceeds threshold",
            metric_name="agent_errors_total",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=10,
            severity=AlertSeverity.ERROR,
            duration_seconds=60,
        ))

        # Check metrics and fire alerts
        await manager.evaluate({"agent_errors_total": 15})

        # Get active alerts
        alerts = manager.get_active_alerts()
    """

    # Default alert rules for AI agent system
    DEFAULT_RULES = [
        AlertRule(
            name="high_agent_latency",
            description="Agent response latency is too high",
            metric_name="agent_latency_ms",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=5000,
            severity=AlertSeverity.WARNING,
            duration_seconds=60,
        ),
        AlertRule(
            name="agent_error_spike",
            description="Agent error rate spiked",
            metric_name="agent_errors_total",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=10,
            severity=AlertSeverity.ERROR,
            duration_seconds=30,
        ),
        AlertRule(
            name="low_consensus_confidence",
            description="Consensus confidence below threshold",
            metric_name="consensus_confidence",
            operator=ComparisonOperator.LESS_THAN,
            threshold=0.6,
            severity=AlertSeverity.WARNING,
        ),
        AlertRule(
            name="memory_pressure",
            description="Memory usage exceeds limit",
            metric_name="memory_tier_items",
            operator=ComparisonOperator.GREATER_THAN,
            threshold=1000,
            severity=AlertSeverity.WARNING,
            labels={"tier": "working"},
        ),
        AlertRule(
            name="no_active_keys",
            description="No active API keys available",
            metric_name="active_api_keys",
            operator=ComparisonOperator.LESS_THAN,
            threshold=1,
            severity=AlertSeverity.CRITICAL,
        ),
    ]

    def __init__(
        self,
        notifiers: list[AlertNotifier] | None = None,
        auto_add_defaults: bool = True,
    ):
        """
        Initialize alert manager

        Args:
            notifiers: List of notifiers for sending alerts
            auto_add_defaults: Add default alert rules
        """
        self.notifiers = notifiers or [LogNotifier()]

        self.rules: dict[str, AlertRule] = {}
        self.alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []

        # For anomaly detection
        self.metric_history: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

        # Silenced alerts
        self.silences: dict[str, datetime] = {}  # rule_name -> until

        # Stats
        self.stats = {
            "rules_evaluated": 0,
            "alerts_fired": 0,
            "alerts_resolved": 0,
            "notifications_sent": 0,
        }

        if auto_add_defaults:
            for rule in self.DEFAULT_RULES:
                self.add_rule(rule)

        logger.info(f"🚨 AlertManager initialized with {len(self.rules)} rules")

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule"""
        self.rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        """Remove an alert rule"""
        if name in self.rules:
            del self.rules[name]
            return True
        return False

    async def evaluate(self, metrics: dict[str, float]) -> list[Alert]:
        """
        Evaluate all rules against current metrics

        Args:
            metrics: Dict of metric_name -> value

        Returns:
            List of newly fired alerts
        """
        new_alerts = []
        now = datetime.now(UTC)

        for rule_name, rule in self.rules.items():
            if not rule.enabled:
                continue

            if rule_name in self.silences:
                if self.silences[rule_name] > now:
                    continue
                del self.silences[rule_name]

            value = metrics.get(rule.metric_name)
            if value is None:
                continue

            self.stats["rules_evaluated"] += 1

            # Store for anomaly detection
            self.metric_history[rule.metric_name].append((now, value))

            condition_met = rule.evaluate(value)
            alert_id = f"{rule_name}"

            if condition_met:
                if alert_id in self.alerts:
                    # Update existing alert
                    alert = self.alerts[alert_id]
                    alert.last_evaluated_at = now
                    alert.value = value

                    # Check duration condition
                    if rule.duration_seconds > 0:
                        if alert.firing_since is None:
                            alert.firing_since = now
                        elif (now - alert.firing_since).total_seconds() >= rule.duration_seconds:
                            if alert.state == AlertState.PENDING:
                                alert.state = AlertState.FIRING
                                new_alerts.append(alert)
                    elif alert.state == AlertState.PENDING:
                        alert.state = AlertState.FIRING
                        new_alerts.append(alert)
                else:
                    # Create new alert
                    alert = Alert(
                        id=alert_id,
                        rule_name=rule_name,
                        severity=rule.severity,
                        state=AlertState.PENDING if rule.duration_seconds > 0 else AlertState.FIRING,
                        message=rule.description,
                        value=value,
                        threshold=rule.threshold,
                        labels=rule.labels,
                        annotations=rule.annotations,
                        firing_since=now if rule.duration_seconds == 0 else None,
                    )

                    self.alerts[alert_id] = alert
                    self.stats["alerts_fired"] += 1

                    if rule.duration_seconds == 0:
                        new_alerts.append(alert)
            else:
                # Condition not met - resolve if firing
                if alert_id in self.alerts:
                    alert = self.alerts[alert_id]
                    if alert.state == AlertState.FIRING:
                        alert.state = AlertState.RESOLVED
                        alert.resolved_at = now
                        self.alert_history.append(alert)
                        self.stats["alerts_resolved"] += 1
                    del self.alerts[alert_id]

        # Send notifications for new alerts
        for alert in new_alerts:
            if not alert.notification_sent:
                await self._notify(alert)
                alert.notification_sent = True

        return new_alerts

    async def _notify(self, alert: Alert) -> None:
        """Send alert to all notifiers"""
        for notifier in self.notifiers:
            try:
                success = await notifier.send(alert)
                if success:
                    self.stats["notifications_sent"] += 1
            except Exception as e:
                logger.warning(f"Notifier failed: {e}")

    def silence(self, rule_name: str, duration_minutes: int) -> bool:
        """Silence an alert rule"""
        if rule_name not in self.rules:
            return False

        until = datetime.now(UTC) + timedelta(minutes=duration_minutes)
        self.silences[rule_name] = until

        # Resolve any active alerts for this rule
        if rule_name in self.alerts:
            self.alerts[rule_name].state = AlertState.SILENCED

        logger.info(f"🔇 Silenced alert '{rule_name}' until {until}")
        return True

    def unsilence(self, rule_name: str) -> bool:
        """Unsilence an alert rule"""
        if rule_name in self.silences:
            del self.silences[rule_name]
            return True
        return False

    def get_active_alerts(
        self,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """Get currently active alerts"""
        alerts = [a for a in self.alerts.values() if a.state == AlertState.FIRING]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.started_at, reverse=True)

    def get_alert_history(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """Get historical alerts"""
        history = self.alert_history[-limit:]

        if severity:
            history = [a for a in history if a.severity == severity]

        return sorted(history, key=lambda a: a.started_at, reverse=True)

    def detect_anomaly(
        self,
        metric_name: str,
        current_value: float,
        std_threshold: float = 3.0,
        min_samples: int = 10,
    ) -> Alert | None:
        """
        Detect anomaly using statistical methods

        Uses z-score based detection:
        - If value is > std_threshold standard deviations from mean, it's anomalous
        """
        history = self.metric_history.get(metric_name, [])

        if len(history) < min_samples:
            return None

        values = [v for _, v in history[-100:]]  # Use last 100 values

        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        if std == 0:
            return None

        z_score = abs(current_value - mean) / std

        if z_score > std_threshold:
            msg = (
                f"Anomaly detected: {metric_name} value {current_value:.2f} "
                f"is {z_score:.1f} std devs from mean {mean:.2f}"
            )
            alert = Alert(
                id=f"anomaly_{metric_name}",
                rule_name=f"anomaly_detection_{metric_name}",
                severity=AlertSeverity.WARNING,
                state=AlertState.FIRING,
                message=msg,
                value=current_value,
                threshold=mean + std_threshold * std,
                labels={"type": "anomaly", "metric": metric_name},
            )
            return alert

        return None

    def cleanup_history(self, max_items: int = 1000) -> int:
        """Cleanup old history items"""
        if len(self.alert_history) <= max_items:
            return 0

        removed = len(self.alert_history) - max_items
        self.alert_history = self.alert_history[-max_items:]

        # Also cleanup metric history
        max_metric_samples = 500
        for metric_name in self.metric_history:
            if len(self.metric_history[metric_name]) > max_metric_samples:
                self.metric_history[metric_name] = self.metric_history[metric_name][-max_metric_samples:]

        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get alert manager statistics"""
        return {
            **self.stats,
            "rules_count": len(self.rules),
            "active_alerts": len([a for a in self.alerts.values() if a.state == AlertState.FIRING]),
            "silenced_rules": len(self.silences),
            "history_size": len(self.alert_history),
        }


# Global instance
_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager"""
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager


__all__ = [
    "Alert",
    "AlertManager",
    "AlertNotifier",
    "AlertRule",
    "AlertSeverity",
    "AlertState",
    "ComparisonOperator",
    "LogNotifier",
    "WebhookNotifier",
    "get_alert_manager",
]
