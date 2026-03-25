"""
Self-Learning Signal Service
Публикует сигналы для self-learning системы, отслеживает performance drift,
триггерит автоматическое переобучение моделей
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Snapshot метрик производительности"""

    timestamp: str
    tournament_id: str
    phase: str

    # Performance metrics
    latency_ms: float
    throughput_rps: float
    error_rate: float
    success_rate: float

    # Model metrics
    model_accuracy: float | None = None
    concept_drift_score: float | None = None
    confidence_scores: dict[str, float] = field(default_factory=dict)

    # Resource metrics
    cpu_usage: float | None = None
    memory_mb: float | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftAlert:
    """Алерт о performance drift"""

    timestamp: str
    alert_type: str  # "performance_degradation", "concept_drift", "error_spike"
    severity: str  # "low", "medium", "high", "critical"
    metric_name: str
    current_value: float
    baseline_value: float
    threshold: float
    recommendation: str


class SelfLearningSignalPublisher:
    """
    Публикует сигналы для self-learning системы

    Функциональность:
    - Публикация performance snapshots
    - Детекция concept drift
    - Триггеры для автоматического переобучения
    - Логирование в файлы и Redis (опционально)
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        redis_url: str | None = None,
        drift_threshold: float = 0.15,
        error_rate_threshold: float = 0.05,
        latency_threshold_ms: float = 120.0,
    ):
        """
        Args:
            output_dir: Директория для сохранения snapshots (по умолчанию logs/self_learning)
            redis_url: Redis URL для pub/sub (опционально)
            drift_threshold: Порог для детекции concept drift
            error_rate_threshold: Порог error rate для алертов
            latency_threshold_ms: Порог latency для алертов
        """
        self.output_dir = output_dir or Path("logs/self_learning")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.redis_url = redis_url
        self.redis_client = None

        # Thresholds
        self.drift_threshold = drift_threshold
        self.error_rate_threshold = error_rate_threshold
        self.latency_threshold_ms = latency_threshold_ms

        # In-memory storage для baseline
        self.baseline_metrics: dict[str, float] = {}
        self.recent_snapshots: list[PerformanceSnapshot] = []
        self.max_recent_snapshots = 100

        # Alerts
        self.alerts: list[DriftAlert] = []

        logger.info(
            f"✅ SelfLearningSignalPublisher initialized "
            f"(drift_threshold={drift_threshold}, output_dir={self.output_dir})"
        )

    async def publish_snapshot(self, snapshot: dict[str, Any]) -> None:
        """
        Публикует performance snapshot

        Args:
            snapshot: Словарь с метриками производительности
        """
        try:
            # Convert dict to PerformanceSnapshot
            perf_snapshot = self._dict_to_snapshot(snapshot)

            # Store in memory
            self.recent_snapshots.append(perf_snapshot)
            if len(self.recent_snapshots) > self.max_recent_snapshots:
                self.recent_snapshots.pop(0)

            # Save to file
            await self._save_snapshot_to_file(perf_snapshot)

            # Publish to Redis (if configured)
            if self.redis_client:
                await self._publish_to_redis(perf_snapshot)

            # Analyze for drift
            alerts = await self._analyze_drift(perf_snapshot)
            if alerts:
                await self._handle_alerts(alerts)

            logger.debug(
                f"📊 Published snapshot: {perf_snapshot.tournament_id} "
                f"(latency={perf_snapshot.latency_ms:.1f}ms, "
                f"error_rate={perf_snapshot.error_rate:.2%})"
            )

        except Exception as e:
            logger.error(f"Failed to publish snapshot: {e}", exc_info=True)

    def _dict_to_snapshot(self, data: dict[str, Any]) -> PerformanceSnapshot:
        """Конвертирует словарь в PerformanceSnapshot"""
        return PerformanceSnapshot(
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            tournament_id=data.get("tournament_id", "unknown"),
            phase=data.get("phase", "unknown"),
            latency_ms=float(data.get("latency_ms", 0.0)),
            throughput_rps=float(data.get("throughput_rps", 0.0)),
            error_rate=float(data.get("error_rate", 0.0)),
            success_rate=float(data.get("success_rate", 1.0)),
            model_accuracy=data.get("model_accuracy"),
            concept_drift_score=data.get("concept_drift_score"),
            confidence_scores=data.get("confidence_scores", {}),
            cpu_usage=data.get("cpu_usage"),
            memory_mb=data.get("memory_mb"),
            metadata=data.get("metadata", {}),
        )

    async def _save_snapshot_to_file(self, snapshot: PerformanceSnapshot) -> None:
        """Сохраняет snapshot в JSON файл"""
        try:
            # Имя файла: snapshots_YYYY-MM-DD.jsonl
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            file_path = self.output_dir / f"snapshots_{date_str}.jsonl"

            # Append to JSONL file
            snapshot_dict = asdict(snapshot)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(snapshot_dict) + "\n")

        except Exception as e:
            logger.warning(f"Failed to save snapshot to file: {e}")

    async def _publish_to_redis(self, snapshot: PerformanceSnapshot) -> None:
        """Публикует snapshot в Redis pub/sub для real-time мониторинга"""
        try:
            import json
            from dataclasses import asdict

            import redis.asyncio as aioredis

            redis_client = aioredis.Redis(host="localhost", port=6379, db=0)

            # Publish to channel
            channel = "signal_service:snapshots"
            snapshot_data = json.dumps(asdict(snapshot), default=str)
            await redis_client.publish(channel, snapshot_data)

            # Also store latest snapshot in a key for polling
            await redis_client.set(
                "signal_service:latest_snapshot",
                snapshot_data,
                ex=300,  # Expire after 5 minutes
            )

            await redis_client.close()
            logger.debug(f"Published snapshot to Redis channel: {channel}")

        except ImportError:
            pass  # Redis async client not available
        except Exception as e:
            # Non-critical - just log and continue
            logger.debug(f"Redis pub/sub not available: {e}")

    async def _analyze_drift(self, snapshot: PerformanceSnapshot) -> list[DriftAlert]:
        """
        Анализирует snapshot на наличие drift и performance issues

        Returns:
            Список алертов (если есть проблемы)
        """
        alerts = []

        # Update baseline если это первый snapshot
        if not self.baseline_metrics:
            self._update_baseline(snapshot)
            return []

        # Check error rate
        if snapshot.error_rate > self.error_rate_threshold:
            alerts.append(
                DriftAlert(
                    timestamp=snapshot.timestamp,
                    alert_type="error_spike",
                    severity="high" if snapshot.error_rate > 0.1 else "medium",
                    metric_name="error_rate",
                    current_value=snapshot.error_rate,
                    baseline_value=self.baseline_metrics.get("error_rate", 0.0),
                    threshold=self.error_rate_threshold,
                    recommendation="Investigate error logs, check service health",
                )
            )

        # Check latency
        if snapshot.latency_ms > self.latency_threshold_ms:
            alerts.append(
                DriftAlert(
                    timestamp=snapshot.timestamp,
                    alert_type="performance_degradation",
                    severity="medium",
                    metric_name="latency_ms",
                    current_value=snapshot.latency_ms,
                    baseline_value=self.baseline_metrics.get("latency_ms", 0.0),
                    threshold=self.latency_threshold_ms,
                    recommendation="Check system resources, optimize bottlenecks",
                )
            )

        # Check concept drift
        if snapshot.concept_drift_score and snapshot.concept_drift_score > self.drift_threshold:
            alerts.append(
                DriftAlert(
                    timestamp=snapshot.timestamp,
                    alert_type="concept_drift",
                    severity="high",
                    metric_name="concept_drift_score",
                    current_value=snapshot.concept_drift_score,
                    baseline_value=self.baseline_metrics.get("concept_drift_score", 0.0),
                    threshold=self.drift_threshold,
                    recommendation="Trigger model retraining, update training data",
                )
            )

        return alerts

    def _update_baseline(self, snapshot: PerformanceSnapshot) -> None:
        """Обновляет baseline метрики"""
        self.baseline_metrics = {
            "error_rate": snapshot.error_rate,
            "latency_ms": snapshot.latency_ms,
            "throughput_rps": snapshot.throughput_rps,
            "concept_drift_score": snapshot.concept_drift_score or 0.0,
        }
        logger.info(f"📊 Baseline metrics updated: {self.baseline_metrics}")

    async def _handle_alerts(self, alerts: list[DriftAlert]) -> None:
        """Обрабатывает алерты (логирование, сохранение)"""
        self.alerts.extend(alerts)

        for alert in alerts:
            # Log alert
            log_level = logging.ERROR if alert.severity == "critical" else logging.WARNING
            logger.log(
                log_level,
                f"🚨 {alert.alert_type.upper()}: {alert.metric_name}={alert.current_value:.3f} "
                f"(threshold={alert.threshold:.3f}, baseline={alert.baseline_value:.3f}) "
                f"→ {alert.recommendation}",
            )

            # Save alert to file
            await self._save_alert_to_file(alert)

    async def _save_alert_to_file(self, alert: DriftAlert) -> None:
        """Сохраняет alert в файл"""
        try:
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            file_path = self.output_dir / f"alerts_{date_str}.jsonl"

            alert_dict = asdict(alert)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert_dict) + "\n")

        except Exception as e:
            logger.warning(f"Failed to save alert to file: {e}")

    def get_recent_snapshots(self, limit: int = 10) -> list[dict[str, Any]]:
        """Возвращает последние N snapshots"""
        recent = self.recent_snapshots[-limit:]
        return [asdict(s) for s in recent]

    def get_alerts(self, severity: str | None = None) -> list[dict[str, Any]]:
        """
        Возвращает алерты

        Args:
            severity: Фильтр по severity (optional)
        """
        filtered = [a for a in self.alerts if a.severity == severity] if severity else self.alerts

        return [asdict(a) for a in filtered]

    def get_baseline_metrics(self) -> dict[str, float]:
        """Возвращает baseline метрики"""
        return self.baseline_metrics.copy()

    async def trigger_retraining(self, reason: str) -> dict[str, Any]:
        """
        Триггерит автоматическое переобучение модели

        Args:
            reason: Причина переобучения

        Returns:
            Результат триггера
        """
        logger.warning(f"🔄 Triggering model retraining: {reason}")

        # Save retraining trigger
        trigger_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "reason": reason,
            "baseline_metrics": self.baseline_metrics,
            "recent_drift_alerts": [asdict(a) for a in self.alerts[-5:] if a.alert_type == "concept_drift"],
        }

        file_path = self.output_dir / "retraining_triggers.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trigger_data) + "\n")

        return {
            "triggered": True,
            "reason": reason,
            "timestamp": trigger_data["timestamp"],
        }


# Singleton instance
_publisher_instance: SelfLearningSignalPublisher | None = None


def get_self_learning_publisher() -> SelfLearningSignalPublisher:
    """Получить singleton instance publisher"""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = SelfLearningSignalPublisher()
    return _publisher_instance


__all__ = [
    "DriftAlert",
    "PerformanceSnapshot",
    "SelfLearningSignalPublisher",
    "get_self_learning_publisher",
]
