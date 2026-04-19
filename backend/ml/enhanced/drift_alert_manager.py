"""
Drift Alert Manager for Concept Drift Detection

This module provides alert integration for the concept drift detection
system, solving the P1 issue of drift alerts not being integrated.

Audit Reference: docs/ML_SYSTEM_AUDIT_2026_01_28.md - P1 Issue #6
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.ml.enhanced.concept_drift import (
    DriftResult,
    DriftType,
    MultiVariateDriftDetector,
)

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert notification channels."""

    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    REDIS = "redis"
    CALLBACK = "callback"


@dataclass
class DriftAlertConfig:
    """Configuration for drift alerts."""

    # Alert thresholds
    confidence_threshold: float = 0.7  # Min confidence to alert
    consecutive_drift_threshold: int = 3  # Alert after N consecutive drifts

    # Severity escalation
    severity_thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "low": 0.5,
            "medium": 0.7,
            "high": 0.85,
            "critical": 0.95,
        }
    )

    # Alert channels
    channels: list[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])

    # Rate limiting
    min_alert_interval_seconds: int = 60  # Min time between alerts for same feature
    max_alerts_per_hour: int = 10

    # Webhook configuration
    webhook_url: str | None = None
    webhook_timeout: int = 30

    # Email configuration
    email_recipients: list[str] = field(default_factory=list)
    email_smtp_host: str = ""
    email_smtp_port: int = 587

    # Slack configuration
    slack_webhook_url: str | None = None
    slack_channel: str = "#alerts"

    # Redis configuration (for alert persistence)
    redis_url: str | None = None
    redis_alert_ttl: int = 86400 * 7  # 7 days


@dataclass
class EnhancedDriftAlert:
    """Enhanced drift alert with more context."""

    alert_id: str
    severity: AlertSeverity
    feature_name: str | None
    drift_result: DriftResult
    model_name: str | None = None
    recommended_action: str = ""
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "feature_name": self.feature_name,
            "model_name": self.model_name,
            "drift_detected": self.drift_result.is_drift,
            "drift_type": self.drift_result.drift_type.value if self.drift_result.drift_type else None,
            "confidence": self.drift_result.confidence,
            "p_value": self.drift_result.p_value,
            "recommended_action": self.recommended_action,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class DriftAlertManager:
    """
    Manages drift detection alerts with multiple notification channels.

    Features:
        - Multiple alert channels (log, webhook, email, Slack, Redis)
        - Rate limiting to prevent alert storms
        - Severity escalation based on drift confidence
        - Alert history and acknowledgment
        - Integration with monitoring systems

    Example:
        config = DriftAlertConfig(
            channels=[AlertChannel.LOG, AlertChannel.SLACK],
            slack_webhook_url="https://hooks.slack.com/..."
        )

        manager = DriftAlertManager(config)

        # Register alert callback
        manager.register_callback(my_alert_handler)

        # Process drift result
        alert = await manager.process_drift(drift_result, "rsi_14", "price_predictor")
    """

    def __init__(
        self,
        config: DriftAlertConfig | None = None,
    ):
        """
        Initialize drift alert manager.

        Args:
            config: Alert configuration
        """
        self.config = config or DriftAlertConfig()

        # Alert history
        self._alerts: dict[str, EnhancedDriftAlert] = {}
        self._alert_counts: dict[str, list[datetime]] = {}  # Feature -> timestamps

        # Consecutive drift tracking
        self._consecutive_drifts: dict[str, int] = {}

        # Rate limiting
        self._last_alert_time: dict[str, datetime] = {}

        # Callbacks
        self._callbacks: list[Callable[[EnhancedDriftAlert], None]] = []
        self._async_callbacks: list[Callable[[EnhancedDriftAlert], Any]] = []

        # Redis connection
        self._redis: Any = None
        if self.config.redis_url:
            self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection for alert persistence."""
        try:
            import redis

            self._redis = redis.from_url(
                self.config.redis_url,
                decode_responses=True,
            )
            self._redis.ping()
            logger.info("Connected to Redis for alert persistence")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._redis = None

    def register_callback(
        self,
        callback: Callable[[EnhancedDriftAlert], None],
    ) -> None:
        """Register a synchronous callback for alerts."""
        self._callbacks.append(callback)

    def register_async_callback(
        self,
        callback: Callable[[EnhancedDriftAlert], Any],
    ) -> None:
        """Register an async callback for alerts."""
        self._async_callbacks.append(callback)

    async def process_drift(
        self,
        drift_result: DriftResult,
        feature_name: str | None = None,
        model_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EnhancedDriftAlert | None:
        """
        Process a drift detection result and potentially create an alert.

        Args:
            drift_result: Result from drift detector
            feature_name: Name of the feature
            model_name: Name of the model
            metadata: Additional metadata

        Returns:
            EnhancedDriftAlert if alert was created, None otherwise
        """
        feature_key = feature_name or "global"

        # Track consecutive drifts
        if drift_result.is_drift:
            self._consecutive_drifts[feature_key] = self._consecutive_drifts.get(feature_key, 0) + 1
        else:
            self._consecutive_drifts[feature_key] = 0

        # Check if we should alert
        if not self._should_alert(drift_result, feature_key):
            return None

        # Create alert
        alert = self._create_alert(drift_result, feature_name, model_name, metadata)

        # Store alert
        self._alerts[alert.alert_id] = alert

        # Track alert time
        self._last_alert_time[feature_key] = datetime.now(UTC)

        # Track hourly count
        if feature_key not in self._alert_counts:
            self._alert_counts[feature_key] = []
        self._alert_counts[feature_key].append(datetime.now(UTC))

        # Send through channels
        await self._dispatch_alert(alert)

        return alert

    def _should_alert(
        self,
        drift_result: DriftResult,
        feature_key: str,
    ) -> bool:
        """Check if we should create an alert."""
        # Must be drift
        if not drift_result.is_drift:
            return False

        # Check confidence threshold
        if drift_result.confidence < self.config.confidence_threshold:
            return False

        # Check consecutive drift threshold
        consecutive = self._consecutive_drifts.get(feature_key, 0)
        if consecutive < self.config.consecutive_drift_threshold:
            return False

        # Check rate limiting
        now = datetime.now(UTC)

        # Min interval check
        last_time = self._last_alert_time.get(feature_key)
        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.config.min_alert_interval_seconds:
                return False

        # Hourly limit check
        if feature_key in self._alert_counts:
            hour_ago = datetime.now(UTC).replace(hour=now.hour - 1 if now.hour > 0 else 23)
            recent = [t for t in self._alert_counts[feature_key] if t > hour_ago]
            if len(recent) >= self.config.max_alerts_per_hour:
                return False

        return True

    def _create_alert(
        self,
        drift_result: DriftResult,
        feature_name: str | None,
        model_name: str | None,
        metadata: dict[str, Any] | None,
    ) -> EnhancedDriftAlert:
        """Create an enhanced drift alert."""
        # Determine severity
        severity = self._calculate_severity(drift_result)

        # Generate recommended action
        recommended_action = self._get_recommended_action(drift_result, severity)

        return EnhancedDriftAlert(
            alert_id=str(uuid.uuid4()),
            severity=severity,
            feature_name=feature_name,
            drift_result=drift_result,
            model_name=model_name,
            recommended_action=recommended_action,
            metadata=metadata or {},
        )

    def _calculate_severity(self, drift_result: DriftResult) -> AlertSeverity:
        """Calculate alert severity based on drift result."""
        confidence = drift_result.confidence
        thresholds = self.config.severity_thresholds

        if confidence >= thresholds.get("critical", 0.95):
            return AlertSeverity.CRITICAL
        elif confidence >= thresholds.get("high", 0.85):
            return AlertSeverity.HIGH
        elif confidence >= thresholds.get("medium", 0.7):
            return AlertSeverity.MEDIUM
        elif confidence >= thresholds.get("low", 0.5):
            return AlertSeverity.LOW
        else:
            return AlertSeverity.INFO

    def _get_recommended_action(
        self,
        drift_result: DriftResult,
        severity: AlertSeverity,
    ) -> str:
        """Get recommended action based on drift and severity."""
        if drift_result.drift_type == DriftType.SUDDEN:
            if severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH):
                return "URGENT: Sudden drift detected. Halt predictions and investigate immediately."
            return "Sudden drift detected. Schedule model retraining."

        if drift_result.drift_type == DriftType.GRADUAL:
            return "Gradual drift detected. Monitor closely and plan retraining."

        if drift_result.drift_type == DriftType.INCREMENTAL:
            return "Incremental drift detected. Consider online learning adaptation."

        if drift_result.drift_type == DriftType.RECURRING:
            return "Recurring drift pattern detected. Review for seasonality."

        if severity == AlertSeverity.CRITICAL:
            return "Critical drift detected. Immediate action required."

        return "Drift detected. Review model performance."

    async def _dispatch_alert(self, alert: EnhancedDriftAlert) -> None:
        """Dispatch alert through configured channels."""
        tasks = []

        for channel in self.config.channels:
            if channel == AlertChannel.LOG:
                self._send_to_log(alert)
            elif channel == AlertChannel.WEBHOOK:
                tasks.append(self._send_to_webhook(alert))
            elif channel == AlertChannel.SLACK:
                tasks.append(self._send_to_slack(alert))
            elif channel == AlertChannel.REDIS:
                self._send_to_redis(alert)
            elif channel == AlertChannel.CALLBACK:
                self._invoke_callbacks(alert)
                tasks.extend([cb(alert) for cb in self._async_callbacks])

        # Wait for async tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _send_to_log(self, alert: EnhancedDriftAlert) -> None:
        """Send alert to log."""
        level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.WARNING)

        logger.log(
            level,
            f"DRIFT ALERT [{alert.severity.value.upper()}] "
            f"Feature: {alert.feature_name}, Model: {alert.model_name}, "
            f"Confidence: {alert.drift_result.confidence:.2%}, "
            f"Action: {alert.recommended_action}",
        )

    async def _send_to_webhook(self, alert: EnhancedDriftAlert) -> None:
        """Send alert to webhook."""
        if not self.config.webhook_url:
            return

        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.config.webhook_timeout) as client:
                await client.post(
                    self.config.webhook_url,
                    json=alert.to_dict(),
                )
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    async def _send_to_slack(self, alert: EnhancedDriftAlert) -> None:
        """Send alert to Slack."""
        if not self.config.slack_webhook_url:
            return

        try:
            import httpx

            # Format Slack message
            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.LOW: "#2eb886",
                AlertSeverity.MEDIUM: "#daa038",
                AlertSeverity.HIGH: "#ff6b6b",
                AlertSeverity.CRITICAL: "#ff0000",
            }.get(alert.severity, "#daa038")

            payload = {
                "channel": self.config.slack_channel,
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 Drift Alert: {alert.severity.value.upper()}",
                        "fields": [
                            {
                                "title": "Feature",
                                "value": alert.feature_name or "N/A",
                                "short": True,
                            },
                            {
                                "title": "Model",
                                "value": alert.model_name or "N/A",
                                "short": True,
                            },
                            {
                                "title": "Confidence",
                                "value": f"{alert.drift_result.confidence:.2%}",
                                "short": True,
                            },
                            {
                                "title": "Drift Type",
                                "value": alert.drift_result.drift_type.value
                                if alert.drift_result.drift_type
                                else "Unknown",
                                "short": True,
                            },
                            {
                                "title": "Recommended Action",
                                "value": alert.recommended_action,
                                "short": False,
                            },
                        ],
                        "footer": f"Alert ID: {alert.alert_id}",
                        "ts": int(alert.created_at.timestamp()),
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(self.config.slack_webhook_url, json=payload)

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def _send_to_redis(self, alert: EnhancedDriftAlert) -> None:
        """Send alert to Redis for persistence."""
        if not self._redis:
            return

        try:
            key = f"drift_alert:{alert.alert_id}"
            self._redis.setex(
                key,
                self.config.redis_alert_ttl,
                json.dumps(alert.to_dict()),
            )

            # Add to sorted set for queries
            self._redis.zadd(
                "drift_alerts:timeline",
                {alert.alert_id: alert.created_at.timestamp()},
            )
        except Exception as e:
            logger.error(f"Failed to persist alert to Redis: {e}")

    def _invoke_callbacks(self, alert: EnhancedDriftAlert) -> None:
        """Invoke synchronous callbacks."""
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> bool:
        """Acknowledge an alert."""
        if alert_id not in self._alerts:
            return False

        alert = self._alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(UTC)

        # Update in Redis if available
        if self._redis:
            try:
                key = f"drift_alert:{alert_id}"
                self._redis.setex(
                    key,
                    self.config.redis_alert_ttl,
                    json.dumps(alert.to_dict()),
                )
            except Exception:
                pass

        return True

    def get_alert(self, alert_id: str) -> EnhancedDriftAlert | None:
        """Get an alert by ID."""
        # Check memory first
        if alert_id in self._alerts:
            return self._alerts[alert_id]

        # Check Redis
        if self._redis:
            try:
                key = f"drift_alert:{alert_id}"
                data = self._redis.get(key)
                if data:
                    # Reconstruct from JSON (simplified)
                    return None  # Would need proper reconstruction
            except Exception:
                pass

        return None

    def get_recent_alerts(
        self,
        limit: int = 50,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> list[EnhancedDriftAlert]:
        """Get recent alerts with optional filtering."""
        alerts = list(self._alerts.values())

        # Filter by severity
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # Filter by acknowledged
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)

        return alerts[:limit]

    def get_alert_summary(self) -> dict[str, Any]:
        """Get summary of alerts."""
        alerts = list(self._alerts.values())

        if not alerts:
            return {
                "total": 0,
                "unacknowledged": 0,
                "by_severity": {},
                "by_feature": {},
            }

        by_severity = {}
        by_feature = {}

        for alert in alerts:
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

            feat = alert.feature_name or "global"
            by_feature[feat] = by_feature.get(feat, 0) + 1

        return {
            "total": len(alerts),
            "unacknowledged": sum(1 for a in alerts if not a.acknowledged),
            "by_severity": by_severity,
            "by_feature": by_feature,
            "latest_alert": alerts[-1].created_at.isoformat() if alerts else None,
        }

    def clear_old_alerts(self, max_age_days: int = 7) -> int:
        """Clear alerts older than specified days."""
        cutoff = datetime.now(UTC).replace(day=datetime.now(UTC).day - max_age_days)
        old_ids = [aid for aid, alert in self._alerts.items() if alert.created_at < cutoff]

        for aid in old_ids:
            del self._alerts[aid]

        return len(old_ids)


class IntegratedDriftMonitor:
    """
    High-level drift monitor that integrates detection with alerting.

    Example:
        monitor = IntegratedDriftMonitor(
            feature_names=["rsi", "macd", "price"],
            model_name="price_predictor",
            alert_config=DriftAlertConfig(
                channels=[AlertChannel.LOG, AlertChannel.SLACK],
                slack_webhook_url="...",
            )
        )

        # Fit on training data
        monitor.fit(training_features)

        # Monitor production data
        async def on_new_data(features):
            result = await monitor.check(features)
            if result["is_drift"]:
                print(f"Drift detected! {result}")
    """

    def __init__(
        self,
        feature_names: list[str],
        model_name: str | None = None,
        alert_config: DriftAlertConfig | None = None,
        detector_window_size: int = 1000,
        significance_level: float = 0.05,
    ):
        self.model_name = model_name

        # Initialize detector
        self.detector = MultiVariateDriftDetector(
            feature_names=feature_names,
            window_size=detector_window_size,
            significance_level=significance_level,
        )

        # Initialize alert manager
        self.alert_manager = DriftAlertManager(alert_config)

        # Tracking
        self._check_count = 0
        self._drift_count = 0

    def fit(self, reference_data: Any) -> None:
        """Fit detector on reference data."""
        import numpy as np

        data = np.asarray(reference_data)
        self.detector.fit(data)

    async def check(
        self,
        current_data: Any,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Check for drift and potentially create alerts.

        Args:
            current_data: Current feature data (n_samples, n_features)
            metadata: Additional metadata

        Returns:
            Dict with detection results and any alert info
        """
        import numpy as np

        data = np.asarray(current_data)

        # Run detection
        results = self.detector.detect(data)
        self._check_count += 1

        # Process alerts for drifted features
        alerts_created = []
        overall = results.get("overall", {})

        if overall.get("is_drift"):
            self._drift_count += 1

            # Create synthetic DriftResult for alerting
            for feature_name in overall.get("drifted_features", []):
                feat_result = results["per_feature"].get(feature_name, {})

                drift_result = DriftResult(
                    is_drift=True,
                    drift_type=DriftType(feat_result.get("drift_type")) if feat_result.get("drift_type") else None,
                    confidence=feat_result.get("confidence", 0.5),
                    p_value=feat_result.get("p_value"),
                    statistic=None,
                    feature_name=feature_name,
                )

                alert = await self.alert_manager.process_drift(
                    drift_result,
                    feature_name=feature_name,
                    model_name=self.model_name,
                    metadata=metadata,
                )

                if alert:
                    alerts_created.append(alert.alert_id)

        results["alerts_created"] = alerts_created
        results["check_count"] = self._check_count
        results["drift_rate"] = self._drift_count / self._check_count

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "checks": self._check_count,
            "drifts": self._drift_count,
            "drift_rate": self._drift_count / self._check_count if self._check_count > 0 else 0,
            "alerts": self.alert_manager.get_alert_summary(),
        }
