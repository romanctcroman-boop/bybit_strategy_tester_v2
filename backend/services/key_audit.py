"""
Key Usage Audit Logging Service.

AI Agent Security Recommendation - Phase 4 Implementation:
- Track all API key access patterns
- Log key usage with timestamps and context
- Detect anomalous usage patterns
- Generate compliance reports
- Integration with structured logging
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class KeyAccessType(str, Enum):
    """Types of key access."""

    READ = "read"
    USE = "use"
    ROTATE = "rotate"
    CREATE = "create"
    DELETE = "delete"
    VALIDATE = "validate"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


class KeyProvider(str, Enum):
    """Key providers."""

    BYBIT = "bybit"
    DEEPSEEK = "deepseek"
    PERPLEXITY = "perplexity"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DATABASE = "database"
    INTERNAL = "internal"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class KeyAccessEvent:
    """Event for key access."""

    event_id: str
    timestamp: datetime
    key_id: str
    key_provider: KeyProvider
    access_type: KeyAccessType
    user_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_path: str | None = None
    success: bool = True
    error_message: str | None = None
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class UsageAnomaly:
    """Detected usage anomaly."""

    anomaly_id: str
    detected_at: datetime
    key_id: str
    anomaly_type: str
    severity: AlertSeverity
    description: str
    evidence: dict = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class KeyUsageStats:
    """Usage statistics for a key."""

    key_id: str
    key_provider: KeyProvider
    total_accesses: int = 0
    successful_accesses: int = 0
    failed_accesses: int = 0
    last_access: datetime | None = None
    first_access: datetime | None = None
    unique_users: int = 0
    unique_ips: int = 0
    avg_latency_ms: float = 0.0
    accesses_by_type: dict = field(default_factory=dict)
    accesses_by_hour: dict = field(default_factory=dict)


@dataclass
class AuditConfig:
    """Configuration for audit logging."""

    enabled: bool = True
    log_file_path: Path | None = None
    max_events_in_memory: int = 10000
    anomaly_detection_enabled: bool = True
    max_requests_per_minute: int = 100
    max_requests_per_hour: int = 1000
    alert_on_new_ip: bool = True
    alert_on_failure_spike: bool = True
    failure_spike_threshold: float = 0.3  # 30% failure rate


class KeyUsageAuditService:
    """
    Key Usage Audit Logging Service.

    Tracks API key access patterns and detects anomalies.
    """

    _instance: Optional["KeyUsageAuditService"] = None

    def __init__(self, config: AuditConfig | None = None):
        self.config = config or AuditConfig()
        self._events: list[KeyAccessEvent] = []
        self._anomalies: list[UsageAnomaly] = []
        self._event_count = 0
        self._anomaly_count = 0

        # Tracking data
        self._key_stats: dict[str, KeyUsageStats] = {}
        self._ip_history: dict[str, set[str]] = defaultdict(set)
        self._user_history: dict[str, set[str]] = defaultdict(set)
        self._recent_events: dict[str, list[datetime]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "KeyUsageAuditService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def log_access(
        self,
        key_id: str,
        key_provider: KeyProvider,
        access_type: KeyAccessType,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_path: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        latency_ms: float = 0.0,
        metadata: dict | None = None,
    ) -> KeyAccessEvent:
        """Log a key access event."""
        self._event_count += 1
        event_id = (
            f"evt-{self._event_count}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        )

        event = KeyAccessEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            key_id=key_id,
            key_provider=key_provider,
            access_type=access_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            success=success,
            error_message=error_message,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

        # Store event
        self._events.append(event)

        # Trim events if needed
        if len(self._events) > self.config.max_events_in_memory:
            self._events = self._events[-self.config.max_events_in_memory :]

        # Update stats
        self._update_stats(event)

        # Track for anomaly detection
        self._track_for_anomalies(event)

        # Check for anomalies
        if self.config.anomaly_detection_enabled:
            self._check_anomalies(event)

        # Log to file if configured
        if self.config.log_file_path:
            self._write_to_file(event)

        logger.debug(
            f"Key access logged: {key_id} ({access_type.value}) - "
            f"{'success' if success else 'failed'}"
        )

        return event

    def _update_stats(self, event: KeyAccessEvent) -> None:
        """Update usage statistics."""
        key_id = event.key_id

        if key_id not in self._key_stats:
            self._key_stats[key_id] = KeyUsageStats(
                key_id=key_id,
                key_provider=event.key_provider,
                first_access=event.timestamp,
            )

        stats = self._key_stats[key_id]
        stats.total_accesses += 1
        stats.last_access = event.timestamp

        if event.success:
            stats.successful_accesses += 1
        else:
            stats.failed_accesses += 1

        # Track access type
        access_type = event.access_type.value
        stats.accesses_by_type[access_type] = (
            stats.accesses_by_type.get(access_type, 0) + 1
        )

        # Track hourly access
        hour = event.timestamp.hour
        stats.accesses_by_hour[hour] = stats.accesses_by_hour.get(hour, 0) + 1

        # Track unique users and IPs
        if event.user_id:
            self._user_history[key_id].add(event.user_id)
            stats.unique_users = len(self._user_history[key_id])

        if event.ip_address:
            self._ip_history[key_id].add(event.ip_address)
            stats.unique_ips = len(self._ip_history[key_id])

        # Update average latency
        total = stats.total_accesses
        stats.avg_latency_ms = (
            stats.avg_latency_ms * (total - 1) + event.latency_ms
        ) / total

    def _track_for_anomalies(self, event: KeyAccessEvent) -> None:
        """Track event for anomaly detection."""
        key_id = event.key_id
        now = datetime.now()

        # Track recent events
        self._recent_events[key_id].append(now)

        # Remove events older than 1 hour
        cutoff = now - timedelta(hours=1)
        self._recent_events[key_id] = [
            t for t in self._recent_events[key_id] if t > cutoff
        ]

    def _check_anomalies(self, event: KeyAccessEvent) -> None:
        """Check for usage anomalies."""
        key_id = event.key_id
        now = datetime.now()

        # Check rate limits
        recent = self._recent_events[key_id]
        minute_cutoff = now - timedelta(minutes=1)
        events_last_minute = sum(1 for t in recent if t > minute_cutoff)

        if events_last_minute > self.config.max_requests_per_minute:
            self._create_anomaly(
                key_id=key_id,
                anomaly_type="rate_limit_exceeded",
                severity=AlertSeverity.HIGH,
                description=f"Rate limit exceeded: {events_last_minute} requests in last minute",
                evidence={"requests_per_minute": events_last_minute},
            )

        # Check hourly limit
        if len(recent) > self.config.max_requests_per_hour:
            self._create_anomaly(
                key_id=key_id,
                anomaly_type="hourly_limit_exceeded",
                severity=AlertSeverity.MEDIUM,
                description=f"Hourly limit exceeded: {len(recent)} requests",
                evidence={"requests_per_hour": len(recent)},
            )

        # Check for new IP
        if self.config.alert_on_new_ip and event.ip_address:
            known_ips = self._ip_history.get(key_id, set())
            if event.ip_address not in known_ips and len(known_ips) > 0:
                self._create_anomaly(
                    key_id=key_id,
                    anomaly_type="new_ip_detected",
                    severity=AlertSeverity.MEDIUM,
                    description=f"New IP address detected: {event.ip_address}",
                    evidence={
                        "new_ip": event.ip_address,
                        "known_ips": list(known_ips)[:10],
                    },
                )

        # Check failure spike
        if self.config.alert_on_failure_spike and not event.success:
            stats = self._key_stats.get(key_id)
            if stats and stats.total_accesses >= 10:
                failure_rate = stats.failed_accesses / stats.total_accesses
                if failure_rate > self.config.failure_spike_threshold:
                    self._create_anomaly(
                        key_id=key_id,
                        anomaly_type="failure_spike",
                        severity=AlertSeverity.HIGH,
                        description=f"High failure rate detected: {failure_rate:.1%}",
                        evidence={
                            "failure_rate": failure_rate,
                            "total_accesses": stats.total_accesses,
                            "failed_accesses": stats.failed_accesses,
                        },
                    )

    def _create_anomaly(
        self,
        key_id: str,
        anomaly_type: str,
        severity: AlertSeverity,
        description: str,
        evidence: dict,
    ) -> UsageAnomaly:
        """Create an anomaly record."""
        self._anomaly_count += 1
        anomaly_id = f"anomaly-{self._anomaly_count}"

        anomaly = UsageAnomaly(
            anomaly_id=anomaly_id,
            detected_at=datetime.now(),
            key_id=key_id,
            anomaly_type=anomaly_type,
            severity=severity,
            description=description,
            evidence=evidence,
        )

        self._anomalies.append(anomaly)

        # Keep only recent anomalies
        if len(self._anomalies) > 1000:
            self._anomalies = self._anomalies[-1000:]

        logger.warning(f"Anomaly detected: {anomaly_type} for key {key_id}")

        return anomaly

    def _write_to_file(self, event: KeyAccessEvent) -> None:
        """Write event to log file."""
        try:
            if not self.config.log_file_path:
                return

            self.config.log_file_path.parent.mkdir(parents=True, exist_ok=True)

            entry = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "key_id": event.key_id,
                "key_provider": event.key_provider.value,
                "access_type": event.access_type.value,
                "user_id": event.user_id,
                "ip_address": event.ip_address,
                "success": event.success,
                "error_message": event.error_message,
                "latency_ms": event.latency_ms,
            }

            with open(self.config.log_file_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_events(
        self,
        key_id: str | None = None,
        access_type: KeyAccessType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        success_only: bool | None = None,
        limit: int = 100,
    ) -> list[KeyAccessEvent]:
        """Get audit events with optional filters."""
        events = self._events

        if key_id:
            events = [e for e in events if e.key_id == key_id]

        if access_type:
            events = [e for e in events if e.access_type == access_type]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if success_only is not None:
            events = [e for e in events if e.success == success_only]

        return events[-limit:]

    def get_anomalies(
        self,
        key_id: str | None = None,
        severity: AlertSeverity | None = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
    ) -> list[UsageAnomaly]:
        """Get detected anomalies."""
        anomalies = self._anomalies

        if key_id:
            anomalies = [a for a in anomalies if a.key_id == key_id]

        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]

        if unacknowledged_only:
            anomalies = [a for a in anomalies if not a.acknowledged]

        return anomalies[-limit:]

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Acknowledge an anomaly."""
        for anomaly in self._anomalies:
            if anomaly.anomaly_id == anomaly_id:
                anomaly.acknowledged = True
                logger.info(f"Anomaly acknowledged: {anomaly_id}")
                return True
        return False

    def get_key_stats(self, key_id: str) -> KeyUsageStats | None:
        """Get usage statistics for a key."""
        return self._key_stats.get(key_id)

    def get_all_stats(self) -> list[KeyUsageStats]:
        """Get all key statistics."""
        return list(self._key_stats.values())

    def get_summary(self) -> dict:
        """Get audit summary."""
        total_events = len(self._events)
        successful = sum(1 for e in self._events if e.success)
        failed = total_events - successful

        active_keys = len(self._key_stats)
        total_anomalies = len(self._anomalies)
        unack_anomalies = sum(1 for a in self._anomalies if not a.acknowledged)

        # Provider breakdown
        by_provider = defaultdict(int)
        for event in self._events:
            by_provider[event.key_provider.value] += 1

        # Access type breakdown
        by_type = defaultdict(int)
        for event in self._events:
            by_type[event.access_type.value] += 1

        return {
            "total_events": total_events,
            "successful_events": successful,
            "failed_events": failed,
            "success_rate": successful / total_events if total_events > 0 else 1.0,
            "active_keys": active_keys,
            "total_anomalies": total_anomalies,
            "unacknowledged_anomalies": unack_anomalies,
            "events_by_provider": dict(by_provider),
            "events_by_type": dict(by_type),
        }

    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Generate a compliance report for a date range."""
        events = [e for e in self._events if start_date <= e.timestamp <= end_date]

        # Group by key
        by_key = defaultdict(list)
        for event in events:
            by_key[event.key_id].append(event)

        key_reports = []
        for key_id, key_events in by_key.items():
            stats = self._key_stats.get(key_id)
            successful = sum(1 for e in key_events if e.success)
            failed = len(key_events) - successful

            key_reports.append(
                {
                    "key_id": key_id,
                    "provider": stats.key_provider.value if stats else "unknown",
                    "total_accesses": len(key_events),
                    "successful": successful,
                    "failed": failed,
                    "unique_users": len(
                        {e.user_id for e in key_events if e.user_id}
                    ),
                    "unique_ips": len(
                        {e.ip_address for e in key_events if e.ip_address}
                    ),
                }
            )

        # Anomalies in period
        anomalies_in_period = [
            a for a in self._anomalies if start_date <= a.detected_at <= end_date
        ]

        return {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_events": len(events),
                "total_keys_accessed": len(by_key),
                "anomalies_detected": len(anomalies_in_period),
            },
            "key_details": key_reports,
            "anomalies": [
                {
                    "anomaly_id": a.anomaly_id,
                    "detected_at": a.detected_at.isoformat(),
                    "key_id": a.key_id,
                    "type": a.anomaly_type,
                    "severity": a.severity.value,
                    "description": a.description,
                }
                for a in anomalies_in_period
            ],
        }

    def get_status(self) -> dict:
        """Get service status."""
        return {
            "enabled": self.config.enabled,
            "total_events": len(self._events),
            "total_anomalies": len(self._anomalies),
            "tracked_keys": len(self._key_stats),
            "anomaly_detection": self.config.anomaly_detection_enabled,
            "log_file": str(self.config.log_file_path)
            if self.config.log_file_path
            else None,
        }


# Singleton accessor
def get_key_audit_service() -> KeyUsageAuditService:
    """Get key usage audit service instance."""
    return KeyUsageAuditService.get_instance()
