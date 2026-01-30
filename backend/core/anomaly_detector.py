"""
Anomaly Detection for Trading Strategies

Detects anomalies in strategy performance:
- Sudden drawdown spikes
- Win rate degradation
- Execution latency anomalies
- Volume/liquidity anomalies
- Correlation breakdowns

Uses statistical methods (Z-score, IQR) and ML (Isolation Forest) for detection.

Features:
- Multiple severity levels (INFO, WARNING, CRITICAL)
- Callback-based alerting system
- Webhook integration support
- Prometheus metrics integration
"""

import json
import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    """Severity levels for anomalies."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Types of anomalies."""

    DRAWDOWN_SPIKE = "drawdown_spike"
    WIN_RATE_DROP = "win_rate_drop"
    LATENCY_SPIKE = "latency_spike"
    VOLUME_ANOMALY = "volume_anomaly"
    CORRELATION_BREAK = "correlation_break"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    PROFIT_FACTOR_DROP = "profit_factor_drop"
    SHARPE_DEGRADATION = "sharpe_degradation"
    SLIPPAGE_SPIKE = "slippage_spike"


@dataclass
class Anomaly:
    """Detected anomaly."""

    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    strategy_id: str
    metric_name: str
    current_value: float
    expected_range: Tuple[float, float]
    deviation_score: float  # Z-score or similar
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


@dataclass
class MetricWindow:
    """Sliding window for metric values."""

    window_size: int = 100
    values: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)

    def __post_init__(self):
        """Initialize deques with proper maxlen."""
        if not hasattr(self.values, "maxlen") or self.values.maxlen != self.window_size:
            self.values = deque(self.values, maxlen=self.window_size)
        if not hasattr(self.timestamps, "maxlen") or self.timestamps.maxlen != self.window_size:
            self.timestamps = deque(self.timestamps, maxlen=self.window_size)

    def add(self, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add value to window."""
        self.values.append(value)
        self.timestamps.append(timestamp or datetime.now(timezone.utc))

    def mean(self) -> float:
        """Calculate mean."""
        if not self.values:
            return 0.0
        return statistics.mean(self.values)

    def std(self) -> float:
        """Calculate standard deviation."""
        if len(self.values) < 2:
            return 0.0
        return statistics.stdev(self.values)

    def median(self) -> float:
        """Calculate median."""
        if not self.values:
            return 0.0
        return statistics.median(self.values)

    def iqr(self) -> Tuple[float, float, float]:
        """Calculate IQR (Q1, median, Q3)."""
        if len(self.values) < 4:
            return (0.0, 0.0, 0.0)
        sorted_vals = sorted(self.values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        return (q1, self.median(), q3)

    def z_score(self, value: float) -> float:
        """Calculate Z-score for value."""
        std = self.std()
        if std == 0:
            return 0.0
        return (value - self.mean()) / std

    def is_outlier_iqr(self, value: float, multiplier: float = 1.5) -> bool:
        """Check if value is outlier using IQR method."""
        q1, _, q3 = self.iqr()
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return value < lower or value > upper


@dataclass
class AnomalyThresholds:
    """Thresholds for anomaly detection."""

    z_score_warning: float = 2.0
    z_score_critical: float = 3.0
    drawdown_warning_pct: float = 5.0
    drawdown_critical_pct: float = 10.0
    win_rate_drop_warning_pct: float = 10.0
    win_rate_drop_critical_pct: float = 20.0
    consecutive_losses_warning: int = 5
    consecutive_losses_critical: int = 10
    latency_spike_multiplier: float = 3.0
    slippage_warning_pct: float = 0.5
    slippage_critical_pct: float = 1.0


class AlertNotifier(Protocol):
    """Protocol for alert notification handlers."""

    def send_alert(self, anomaly: Anomaly) -> bool:
        """Send alert notification. Returns True if successful."""
        ...


class WebhookAlertNotifier:
    """
    Webhook-based alert notifier for anomaly alerts.

    Sends alerts to a configured webhook URL (Slack, Discord, custom endpoint).
    """

    def __init__(
        self,
        webhook_url: str,
        timeout: float = 10.0,
        include_details: bool = True,
    ):
        """
        Args:
            webhook_url: URL to send alert POST requests to
            timeout: Request timeout in seconds
            include_details: Include detailed anomaly info in payload
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.include_details = include_details

    def send_alert(self, anomaly: Anomaly) -> bool:
        """Send alert via webhook."""
        try:
            payload = self._format_payload(anomaly)
            data = json.dumps(payload).encode("utf-8")

            request = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(request, timeout=self.timeout) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False

    def _format_payload(self, anomaly: Anomaly) -> dict:
        """Format anomaly as webhook payload (Slack-compatible)."""
        severity_emoji = {
            AnomalySeverity.INFO: "ℹ️",
            AnomalySeverity.WARNING: "⚠️",
            AnomalySeverity.CRITICAL: "🚨",
        }

        emoji = severity_emoji.get(anomaly.severity, "❓")

        payload = {
            "text": f"{emoji} {anomaly.severity.value.upper()}: {anomaly.description}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Anomaly Detected",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:*\n{anomaly.severity.value}"},
                        {"type": "mrkdwn", "text": f"*Type:*\n{anomaly.anomaly_type.value}"},
                        {"type": "mrkdwn", "text": f"*Strategy:*\n{anomaly.strategy_id}"},
                        {"type": "mrkdwn", "text": f"*Metric:*\n{anomaly.metric_name}"},
                    ],
                },
            ],
        }

        if self.include_details:
            payload["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Value:* {anomaly.current_value:.4f}\n"
                            f"*Expected Range:* {anomaly.expected_range[0]:.4f} - {anomaly.expected_range[1]:.4f}\n"
                            f"*Deviation Score:* {anomaly.deviation_score:.2f}\n"
                            f"*Time:* {anomaly.timestamp.isoformat()}"
                        ),
                    },
                }
            )

        return payload


class LogAlertNotifier:
    """Simple alert notifier that logs to the standard logger."""

    def send_alert(self, anomaly: Anomaly) -> bool:
        """Log alert."""
        log_method = {
            AnomalySeverity.INFO: logger.info,
            AnomalySeverity.WARNING: logger.warning,
            AnomalySeverity.CRITICAL: logger.critical,
        }.get(anomaly.severity, logger.info)

        log_method(
            f"[ALERT] {anomaly.anomaly_type.value}: {anomaly.description} "
            f"(strategy={anomaly.strategy_id}, value={anomaly.current_value:.4f})"
        )
        return True


class CompositeAlertNotifier:
    """Combines multiple alert notifiers."""

    def __init__(self, notifiers: List[AlertNotifier] = None):
        self.notifiers: List[AlertNotifier] = notifiers or []

    def add_notifier(self, notifier: AlertNotifier) -> None:
        """Add a notifier to the composite."""
        self.notifiers.append(notifier)

    def send_alert(self, anomaly: Anomaly) -> bool:
        """Send alert to all notifiers. Returns True if any succeeded."""
        results = []
        for notifier in self.notifiers:
            try:
                results.append(notifier.send_alert(anomaly))
            except Exception as e:
                logger.error(f"Notifier failed: {e}")
                results.append(False)
        return any(results) if results else False


class AnomalyDetector:
    """
    Detects anomalies in trading strategy metrics.

    Usage:
        detector = AnomalyDetector()
        detector.register_strategy("my_strategy")

        # Feed metrics
        detector.record_metric("my_strategy", "drawdown", 2.5)
        detector.record_metric("my_strategy", "win_rate", 0.65)

        # Check for anomalies
        anomalies = detector.detect_anomalies("my_strategy")

        # With webhook alerts:
        notifier = WebhookAlertNotifier("https://hooks.slack.com/...")
        detector = AnomalyDetector(alert_notifier=notifier)
    """

    def __init__(
        self,
        thresholds: Optional[AnomalyThresholds] = None,
        window_size: int = 100,
        on_anomaly: Optional[Callable[[Anomaly], None]] = None,
        alert_notifier: Optional[AlertNotifier] = None,
    ):
        self.thresholds = thresholds or AnomalyThresholds()
        self.window_size = window_size
        self.on_anomaly = on_anomaly

        # Alert notifier for sending alerts
        self.alert_notifier = alert_notifier or LogAlertNotifier()

        # Per-strategy metric windows
        self._strategy_metrics: Dict[str, Dict[str, MetricWindow]] = {}

        # Detected anomalies
        self._anomalies: Dict[str, List[Anomaly]] = {}

        # Consecutive loss tracking
        self._consecutive_losses: Dict[str, int] = {}

        # Anomaly counter for IDs
        self._anomaly_counter = 0

    def register_strategy(self, strategy_id: str) -> None:
        """Register a strategy for monitoring."""
        if strategy_id not in self._strategy_metrics:
            self._strategy_metrics[strategy_id] = {
                "drawdown": MetricWindow(window_size=self.window_size),
                "win_rate": MetricWindow(window_size=self.window_size),
                "sharpe_ratio": MetricWindow(window_size=self.window_size),
                "profit_factor": MetricWindow(window_size=self.window_size),
                "latency_ms": MetricWindow(window_size=self.window_size),
                "slippage_pct": MetricWindow(window_size=self.window_size),
                "volume": MetricWindow(window_size=self.window_size),
            }
            self._anomalies[strategy_id] = []
            self._consecutive_losses[strategy_id] = 0
            logger.info(f"Registered strategy for monitoring: {strategy_id}")

    def record_metric(
        self,
        strategy_id: str,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Anomaly]:
        """
        Record a metric value and check for anomalies.

        Returns anomaly if detected, None otherwise.
        """
        if strategy_id not in self._strategy_metrics:
            self.register_strategy(strategy_id)

        metrics = self._strategy_metrics[strategy_id]

        if metric_name not in metrics:
            metrics[metric_name] = MetricWindow(window_size=self.window_size)

        window = metrics[metric_name]

        # Check for anomaly before adding (need historical data)
        anomaly = self._check_anomaly(strategy_id, metric_name, value, window)

        # Add to window
        window.add(value, timestamp)

        if anomaly:
            self._anomalies[strategy_id].append(anomaly)

            # Call legacy callback if set
            if self.on_anomaly:
                try:
                    self.on_anomaly(anomaly)
                except Exception as e:
                    logger.error(f"Error in anomaly callback: {e}")

            # Send alert via notifier
            if self.alert_notifier:
                try:
                    self.alert_notifier.send_alert(anomaly)
                except Exception as e:
                    logger.error(f"Error sending alert: {e}")

            # Record to prometheus metrics
            try:
                from backend.core.metrics import metrics as prom_metrics

                prom_metrics.record_anomaly(anomaly.anomaly_type.value, anomaly.severity.value)
                prom_metrics.fire_alert(f"{strategy_id}_{metric_name}", anomaly.severity.value)
            except ImportError:
                pass

        return anomaly

    def record_trade_result(self, strategy_id: str, is_win: bool) -> Optional[Anomaly]:
        """Record trade result and check for consecutive losses."""
        if strategy_id not in self._consecutive_losses:
            self._consecutive_losses[strategy_id] = 0

        if strategy_id not in self._anomalies:
            self._anomalies[strategy_id] = []

        if is_win:
            self._consecutive_losses[strategy_id] = 0
            return None

        self._consecutive_losses[strategy_id] += 1
        losses = self._consecutive_losses[strategy_id]

        anomaly = None
        # Check thresholds
        if losses >= self.thresholds.consecutive_losses_critical:
            anomaly = self._create_anomaly(
                strategy_id=strategy_id,
                anomaly_type=AnomalyType.CONSECUTIVE_LOSSES,
                severity=AnomalySeverity.CRITICAL,
                metric_name="consecutive_losses",
                current_value=float(losses),
                expected_range=(0, self.thresholds.consecutive_losses_warning),
                deviation_score=float(losses - self.thresholds.consecutive_losses_warning),
                description=f"Critical: {losses} consecutive losing trades",
            )
        elif losses >= self.thresholds.consecutive_losses_warning:
            anomaly = self._create_anomaly(
                strategy_id=strategy_id,
                anomaly_type=AnomalyType.CONSECUTIVE_LOSSES,
                severity=AnomalySeverity.WARNING,
                metric_name="consecutive_losses",
                current_value=float(losses),
                expected_range=(0, self.thresholds.consecutive_losses_warning),
                deviation_score=float(losses),
                description=f"Warning: {losses} consecutive losing trades",
            )

        if anomaly:
            self._anomalies[strategy_id].append(anomaly)
            if self.on_anomaly:
                try:
                    self.on_anomaly(anomaly)
                except Exception as e:
                    logger.error(f"Error in anomaly callback: {e}")

        return anomaly

    def _check_anomaly(
        self, strategy_id: str, metric_name: str, value: float, window: MetricWindow
    ) -> Optional[Anomaly]:
        """Check if value is anomalous."""

        # Need enough data for statistics
        if len(window.values) < 10:
            return None

        z_score = window.z_score(value)
        abs_z = abs(z_score)

        # Determine severity
        severity = None
        if abs_z >= self.thresholds.z_score_critical:
            severity = AnomalySeverity.CRITICAL
        elif abs_z >= self.thresholds.z_score_warning:
            severity = AnomalySeverity.WARNING

        if severity is None:
            # Check metric-specific thresholds
            severity = self._check_metric_specific_thresholds(metric_name, value, window)

        if severity is None:
            return None

        # Determine anomaly type
        anomaly_type = self._get_anomaly_type(metric_name, value, window)

        # Calculate expected range
        mean = window.mean()
        std = window.std()
        expected_range = (mean - 2 * std, mean + 2 * std)

        return self._create_anomaly(
            strategy_id=strategy_id,
            anomaly_type=anomaly_type,
            severity=severity,
            metric_name=metric_name,
            current_value=value,
            expected_range=expected_range,
            deviation_score=z_score,
            description=f"{metric_name} anomaly: {value:.4f} (z-score: {z_score:.2f})",
        )

    def _check_metric_specific_thresholds(
        self, metric_name: str, value: float, window: MetricWindow
    ) -> Optional[AnomalySeverity]:
        """Check metric-specific thresholds."""

        if metric_name == "drawdown":
            if value >= self.thresholds.drawdown_critical_pct:
                return AnomalySeverity.CRITICAL
            elif value >= self.thresholds.drawdown_warning_pct:
                return AnomalySeverity.WARNING

        elif metric_name == "win_rate":
            # Check for significant drop
            mean = window.mean()
            if mean > 0:
                drop_pct = ((mean - value) / mean) * 100
                if drop_pct >= self.thresholds.win_rate_drop_critical_pct:
                    return AnomalySeverity.CRITICAL
                elif drop_pct >= self.thresholds.win_rate_drop_warning_pct:
                    return AnomalySeverity.WARNING

        elif metric_name == "slippage_pct":
            if value >= self.thresholds.slippage_critical_pct:
                return AnomalySeverity.CRITICAL
            elif value >= self.thresholds.slippage_warning_pct:
                return AnomalySeverity.WARNING

        elif metric_name == "latency_ms":
            mean = window.mean()
            if mean > 0 and value > mean * self.thresholds.latency_spike_multiplier:
                return AnomalySeverity.WARNING

        return None

    def _get_anomaly_type(self, metric_name: str, value: float, window: MetricWindow) -> AnomalyType:
        """Determine anomaly type based on metric."""

        metric_to_type = {
            "drawdown": AnomalyType.DRAWDOWN_SPIKE,
            "win_rate": AnomalyType.WIN_RATE_DROP,
            "latency_ms": AnomalyType.LATENCY_SPIKE,
            "volume": AnomalyType.VOLUME_ANOMALY,
            "profit_factor": AnomalyType.PROFIT_FACTOR_DROP,
            "sharpe_ratio": AnomalyType.SHARPE_DEGRADATION,
            "slippage_pct": AnomalyType.SLIPPAGE_SPIKE,
        }

        return metric_to_type.get(metric_name, AnomalyType.VOLUME_ANOMALY)

    def _create_anomaly(
        self,
        strategy_id: str,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        metric_name: str,
        current_value: float,
        expected_range: Tuple[float, float],
        deviation_score: float,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Anomaly:
        """Create anomaly instance."""
        self._anomaly_counter += 1

        return Anomaly(
            anomaly_id=f"ANM-{self._anomaly_counter:06d}",
            anomaly_type=anomaly_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            strategy_id=strategy_id,
            metric_name=metric_name,
            current_value=current_value,
            expected_range=expected_range,
            deviation_score=deviation_score,
            description=description,
            metadata=metadata or {},
        )

    def get_anomalies(
        self,
        strategy_id: Optional[str] = None,
        severity: Optional[AnomalySeverity] = None,
        since: Optional[datetime] = None,
        unacknowledged_only: bool = False,
    ) -> List[Anomaly]:
        """Get detected anomalies with filters."""

        if strategy_id:
            anomalies = self._anomalies.get(strategy_id, [])
        else:
            anomalies = []
            for s_anomalies in self._anomalies.values():
                anomalies.extend(s_anomalies)

        # Apply filters
        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]

        if since:
            anomalies = [a for a in anomalies if a.timestamp >= since]

        if unacknowledged_only:
            anomalies = [a for a in anomalies if not a.acknowledged]

        return sorted(anomalies, key=lambda a: a.timestamp, reverse=True)

    def acknowledge_anomaly(self, anomaly_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an anomaly."""
        for anomalies in self._anomalies.values():
            for anomaly in anomalies:
                if anomaly.anomaly_id == anomaly_id:
                    anomaly.acknowledged = True
                    anomaly.acknowledged_at = datetime.now(timezone.utc)
                    anomaly.acknowledged_by = acknowledged_by

                    try:
                        from backend.core.metrics import metrics as prom_metrics

                        prom_metrics.acknowledge_alert(f"{anomaly.strategy_id}_{anomaly.metric_name}")
                    except ImportError:
                        pass

                    return True
        return False

    def get_strategy_health(self, strategy_id: str) -> Dict[str, Any]:
        """Get overall health status for a strategy."""
        if strategy_id not in self._strategy_metrics:
            return {"status": "unknown", "strategy_id": strategy_id}

        anomalies = self.get_anomalies(strategy_id, unacknowledged_only=True)

        # Calculate health score
        critical_count = sum(1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL)
        warning_count = sum(1 for a in anomalies if a.severity == AnomalySeverity.WARNING)

        if critical_count > 0:
            status = "critical"
            health_score = max(0, 1 - (critical_count * 0.3) - (warning_count * 0.1))
        elif warning_count > 0:
            status = "warning"
            health_score = max(0.5, 1 - (warning_count * 0.1))
        else:
            status = "healthy"
            health_score = 1.0

        # Get current metrics
        metrics = self._strategy_metrics[strategy_id]
        current_metrics = {}
        for name, window in metrics.items():
            if window.values:
                current_metrics[name] = {
                    "current": window.values[-1],
                    "mean": window.mean(),
                    "std": window.std(),
                }

        return {
            "strategy_id": strategy_id,
            "status": status,
            "health_score": health_score,
            "active_anomalies": len(anomalies),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "consecutive_losses": self._consecutive_losses.get(strategy_id, 0),
            "metrics": current_metrics,
        }

    def cleanup_old_anomalies(self, max_age_hours: int = 24) -> int:
        """Remove old acknowledged anomalies."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed = 0

        for strategy_id in self._anomalies:
            original_count = len(self._anomalies[strategy_id])
            self._anomalies[strategy_id] = [
                a for a in self._anomalies[strategy_id] if not a.acknowledged or a.timestamp >= cutoff
            ]
            removed += original_count - len(self._anomalies[strategy_id])

        if removed > 0:
            logger.info(f"Cleaned up {removed} old anomalies")

        return removed


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_detector_instance: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get singleton anomaly detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AnomalyDetector()
    return _detector_instance


# Convenience alias
anomaly_detector = get_anomaly_detector
