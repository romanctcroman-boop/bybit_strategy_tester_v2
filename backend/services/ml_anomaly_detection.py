"""
ML Anomaly Detection Service.

AI Agent Recommendation Implementation:
- Statistical anomaly detection for trading patterns
- Isolation Forest for multivariate anomalies
- Z-score for univariate outliers
- Rolling window analysis
- Real-time anomaly alerts
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies detected."""

    PRICE_SPIKE = "price_spike"
    VOLUME_SURGE = "volume_surge"
    VOLATILITY_ANOMALY = "volatility_anomaly"
    SPREAD_ANOMALY = "spread_anomaly"
    LATENCY_ANOMALY = "latency_anomaly"
    ORDER_FLOW_IMBALANCE = "order_flow_imbalance"
    CORRELATION_BREAK = "correlation_break"
    PATTERN_DEVIATION = "pattern_deviation"


class AnomalySeverity(str, Enum):
    """Severity levels for detected anomalies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DataPoint:
    """Single data point for anomaly detection."""

    timestamp: float
    value: float
    symbol: str = ""
    metric_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyEvent:
    """Detected anomaly event."""

    id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    value: float
    expected_range: tuple[float, float]
    z_score: float
    symbol: str
    metric_type: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class AnomalyStats:
    """Statistics for anomaly detection."""

    total_detections: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    by_symbol: dict[str, int] = field(default_factory=dict)
    last_detection: datetime | None = None
    detection_rate_per_hour: float = 0.0


class RollingStatistics:
    """Rolling window statistics calculator."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.values: deque[float] = deque(maxlen=window_size)
        self._sum: float = 0.0
        self._sum_sq: float = 0.0

    def add(self, value: float) -> None:
        """Add value to rolling window."""
        if len(self.values) == self.window_size:
            old_value = self.values[0]
            self._sum -= old_value
            self._sum_sq -= old_value * old_value

        self.values.append(value)
        self._sum += value
        self._sum_sq += value * value

    @property
    def mean(self) -> float:
        """Calculate mean of current window."""
        if not self.values:
            return 0.0
        return self._sum / len(self.values)

    @property
    def std(self) -> float:
        """Calculate standard deviation of current window."""
        n = len(self.values)
        if n < 2:
            return 0.0
        variance = (self._sum_sq - (self._sum * self._sum) / n) / (n - 1)
        return math.sqrt(max(0, variance))

    @property
    def count(self) -> int:
        """Number of values in window."""
        return len(self.values)

    def z_score(self, value: float) -> float:
        """Calculate Z-score for a value."""
        std = self.std
        if std == 0:
            return 0.0
        return (value - self.mean) / std

    def is_anomaly(self, value: float, threshold: float = 3.0) -> bool:
        """Check if value is anomalous based on Z-score."""
        if self.count < 10:
            return False
        return abs(self.z_score(value)) > threshold


class IsolationTree:
    """
    Simplified Isolation Tree for anomaly detection.

    Based on Liu et al. "Isolation Forest" algorithm.
    Anomalies are isolated with fewer splits than normal points.
    """

    def __init__(self, height_limit: int = 10):
        self.height_limit = height_limit
        self.split_feature: int | None = None
        self.split_value: float | None = None
        self.left: IsolationTree | None = None
        self.right: IsolationTree | None = None
        self.size: int = 0

    def fit(self, data: list[list[float]], current_height: int = 0) -> "IsolationTree":
        """Build isolation tree from data."""
        import random

        self.size = len(data)

        if current_height >= self.height_limit or len(data) <= 1:
            return self

        n_features = len(data[0]) if data else 0
        if n_features == 0:
            return self

        # Randomly select feature and split value
        self.split_feature = random.randint(0, n_features - 1)
        feature_values = [row[self.split_feature] for row in data]
        min_val, max_val = min(feature_values), max(feature_values)

        if min_val == max_val:
            return self

        self.split_value = random.uniform(min_val, max_val)

        left_data = [row for row in data if row[self.split_feature] < self.split_value]
        right_data = [
            row for row in data if row[self.split_feature] >= self.split_value
        ]

        if left_data:
            self.left = IsolationTree(self.height_limit)
            self.left.fit(left_data, current_height + 1)

        if right_data:
            self.right = IsolationTree(self.height_limit)
            self.right.fit(right_data, current_height + 1)

        return self

    def path_length(self, point: list[float], current_height: int = 0) -> float:
        """Calculate path length for a point."""
        if self.split_feature is None or self.split_value is None:
            return current_height + self._c(self.size)

        if point[self.split_feature] < self.split_value:
            if self.left:
                return self.left.path_length(point, current_height + 1)
        else:
            if self.right:
                return self.right.path_length(point, current_height + 1)

        return current_height + self._c(self.size)

    @staticmethod
    def _c(n: int) -> float:
        """Average path length of unsuccessful search in BST."""
        if n <= 1:
            return 0
        return 2 * (math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n)


class IsolationForest:
    """
    Isolation Forest for multivariate anomaly detection.

    Ensemble of Isolation Trees for robust anomaly scoring.
    """

    def __init__(
        self,
        n_trees: int = 100,
        sample_size: int = 256,
        contamination: float = 0.1,
    ):
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.contamination = contamination
        self.trees: list[IsolationTree] = []
        self.threshold: float = 0.5
        self._fitted = False

    def fit(self, data: list[list[float]]) -> "IsolationForest":
        """Fit Isolation Forest to data."""
        import random

        sample_size = len(data) if len(data) < self.sample_size else self.sample_size

        height_limit = math.ceil(math.log2(sample_size))

        self.trees = []
        for _ in range(self.n_trees):
            sample = (
                random.sample(data, sample_size) if len(data) > sample_size else data
            )
            tree = IsolationTree(height_limit)
            tree.fit(sample)
            self.trees.append(tree)

        # Calculate threshold based on contamination
        scores = [self.anomaly_score(point) for point in data]
        scores.sort(reverse=True)
        threshold_idx = int(len(scores) * self.contamination)
        self.threshold = scores[threshold_idx] if threshold_idx < len(scores) else 0.5
        self._fitted = True

        logger.info(
            f"IsolationForest fitted with {self.n_trees} trees, threshold={self.threshold:.4f}"
        )
        return self

    def anomaly_score(self, point: list[float]) -> float:
        """Calculate anomaly score for a point (0 to 1, higher = more anomalous)."""
        if not self.trees:
            return 0.0

        avg_path_length = sum(tree.path_length(point) for tree in self.trees) / len(
            self.trees
        )
        c = IsolationTree._c(self.sample_size)

        if c == 0:
            return 0.0

        score = 2 ** (-avg_path_length / c)
        return score

    def predict(self, point: list[float]) -> bool:
        """Predict if point is an anomaly."""
        return self.anomaly_score(point) > self.threshold


class MLAnomalyDetector:
    """
    ML-based anomaly detection service.

    Combines multiple detection methods:
    1. Z-score for univariate outliers
    2. Isolation Forest for multivariate patterns
    3. Rolling statistics for trend analysis
    """

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        window_size: int = 100,
        isolation_forest_trees: int = 50,
        contamination: float = 0.1,
        history_limit: int = 1000,
    ):
        self.z_score_threshold = z_score_threshold
        self.window_size = window_size
        self.history_limit = history_limit

        # Per-metric rolling statistics
        self._rolling_stats: dict[str, RollingStatistics] = {}

        # Isolation Forest for multivariate detection
        self._isolation_forest = IsolationForest(
            n_trees=isolation_forest_trees,
            contamination=contamination,
        )
        self._multivariate_buffer: list[list[float]] = []
        self._min_samples_for_iforest = 100

        # Detected anomalies
        self._anomalies: deque[AnomalyEvent] = deque(maxlen=history_limit)
        self._stats = AnomalyStats()

        # Callbacks
        self._callbacks: list[callable] = []

        self._start_time = time.time()
        logger.info("MLAnomalyDetector initialized")

    def _get_metric_key(self, symbol: str, metric_type: str) -> str:
        """Generate key for metric-specific statistics."""
        return f"{symbol}:{metric_type}"

    def _get_or_create_stats(self, symbol: str, metric_type: str) -> RollingStatistics:
        """Get or create rolling statistics for a metric."""
        key = self._get_metric_key(symbol, metric_type)
        if key not in self._rolling_stats:
            self._rolling_stats[key] = RollingStatistics(self.window_size)
        return self._rolling_stats[key]

    def add_data_point(self, point: DataPoint) -> AnomalyEvent | None:
        """
        Add data point and check for anomalies.

        Returns AnomalyEvent if anomaly detected, None otherwise.
        """
        stats = self._get_or_create_stats(point.symbol, point.metric_type)

        # Check for anomaly before adding to stats
        anomaly = None
        if stats.count >= 10:
            z = stats.z_score(point.value)
            if abs(z) > self.z_score_threshold:
                anomaly = self._create_anomaly_event(point, stats, z)
                self._record_anomaly(anomaly)

        # Add to rolling statistics
        stats.add(point.value)

        # Add to multivariate buffer
        self._multivariate_buffer.append(
            [point.value, point.timestamp, len(self._multivariate_buffer)]
        )
        if len(self._multivariate_buffer) > self.history_limit:
            self._multivariate_buffer.pop(0)

        # Retrain Isolation Forest periodically
        if (
            len(self._multivariate_buffer) >= self._min_samples_for_iforest
            and len(self._multivariate_buffer) % 100 == 0
        ):
            self._retrain_isolation_forest()

        return anomaly

    def _create_anomaly_event(
        self,
        point: DataPoint,
        stats: RollingStatistics,
        z_score: float,
    ) -> AnomalyEvent:
        """Create anomaly event from data point."""
        import uuid

        # Determine severity based on Z-score
        abs_z = abs(z_score)
        if abs_z > 5:
            severity = AnomalySeverity.CRITICAL
        elif abs_z > 4:
            severity = AnomalySeverity.HIGH
        elif abs_z > 3.5:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW

        # Determine anomaly type
        anomaly_type = self._classify_anomaly_type(point.metric_type)

        # Calculate expected range (mean ± 2*std)
        expected_min = stats.mean - 2 * stats.std
        expected_max = stats.mean + 2 * stats.std

        return AnomalyEvent(
            id=str(uuid.uuid4()),
            anomaly_type=anomaly_type,
            severity=severity,
            timestamp=datetime.fromtimestamp(point.timestamp),
            value=point.value,
            expected_range=(expected_min, expected_max),
            z_score=z_score,
            symbol=point.symbol,
            metric_type=point.metric_type,
            description=self._generate_description(
                point, stats, z_score, anomaly_type, severity
            ),
            metadata=point.metadata,
        )

    def _classify_anomaly_type(self, metric_type: str) -> AnomalyType:
        """Classify anomaly type based on metric."""
        metric_lower = metric_type.lower()

        if "price" in metric_lower:
            return AnomalyType.PRICE_SPIKE
        elif "volume" in metric_lower:
            return AnomalyType.VOLUME_SURGE
        elif "volatility" in metric_lower or "atr" in metric_lower:
            return AnomalyType.VOLATILITY_ANOMALY
        elif "spread" in metric_lower:
            return AnomalyType.SPREAD_ANOMALY
        elif "latency" in metric_lower or "time" in metric_lower:
            return AnomalyType.LATENCY_ANOMALY
        elif "order" in metric_lower or "flow" in metric_lower:
            return AnomalyType.ORDER_FLOW_IMBALANCE
        elif "correlation" in metric_lower:
            return AnomalyType.CORRELATION_BREAK
        else:
            return AnomalyType.PATTERN_DEVIATION

    def _generate_description(
        self,
        point: DataPoint,
        stats: RollingStatistics,
        z_score: float,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
    ) -> str:
        """Generate human-readable description of anomaly."""
        direction = "above" if z_score > 0 else "below"
        deviation = abs(z_score)

        return (
            f"{severity.value.upper()} {anomaly_type.value}: "
            f"{point.symbol} {point.metric_type} = {point.value:.4f} "
            f"({deviation:.1f}σ {direction} mean of {stats.mean:.4f})"
        )

    def _record_anomaly(self, anomaly: AnomalyEvent) -> None:
        """Record detected anomaly and update stats."""
        self._anomalies.append(anomaly)

        # Update statistics
        self._stats.total_detections += 1
        self._stats.by_type[anomaly.anomaly_type.value] = (
            self._stats.by_type.get(anomaly.anomaly_type.value, 0) + 1
        )
        self._stats.by_severity[anomaly.severity.value] = (
            self._stats.by_severity.get(anomaly.severity.value, 0) + 1
        )
        self._stats.by_symbol[anomaly.symbol] = (
            self._stats.by_symbol.get(anomaly.symbol, 0) + 1
        )
        self._stats.last_detection = anomaly.timestamp

        # Calculate detection rate
        elapsed_hours = (time.time() - self._start_time) / 3600
        if elapsed_hours > 0:
            self._stats.detection_rate_per_hour = (
                self._stats.total_detections / elapsed_hours
            )

        # Trigger callbacks
        for callback in self._callbacks:
            try:
                callback(anomaly)
            except Exception as e:
                logger.error(f"Anomaly callback error: {e}")

        logger.warning(f"Anomaly detected: {anomaly.description}")

    def _retrain_isolation_forest(self) -> None:
        """Retrain Isolation Forest with current data."""
        if len(self._multivariate_buffer) < self._min_samples_for_iforest:
            return

        try:
            self._isolation_forest.fit(self._multivariate_buffer[-500:])
        except Exception as e:
            logger.error(f"Failed to retrain Isolation Forest: {e}")

    def check_multivariate_anomaly(self, features: list[float]) -> tuple[bool, float]:
        """
        Check for multivariate anomaly using Isolation Forest.

        Returns (is_anomaly, anomaly_score).
        """
        if not self._isolation_forest._fitted:
            return False, 0.0

        score = self._isolation_forest.anomaly_score(features)
        is_anomaly = self._isolation_forest.predict(features)

        return is_anomaly, score

    def register_callback(self, callback: callable) -> None:
        """Register callback for anomaly notifications."""
        self._callbacks.append(callback)

    def get_recent_anomalies(
        self,
        limit: int = 100,
        severity: AnomalySeverity | None = None,
        anomaly_type: AnomalyType | None = None,
        symbol: str | None = None,
    ) -> list[AnomalyEvent]:
        """Get recent anomalies with optional filters."""
        anomalies = list(self._anomalies)

        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]
        if anomaly_type:
            anomalies = [a for a in anomalies if a.anomaly_type == anomaly_type]
        if symbol:
            anomalies = [a for a in anomalies if a.symbol == symbol]

        return anomalies[-limit:]

    def get_statistics(self) -> AnomalyStats:
        """Get anomaly detection statistics."""
        return self._stats

    def get_rolling_stats(
        self, symbol: str, metric_type: str
    ) -> dict[str, float] | None:
        """Get rolling statistics for a metric."""
        stats = self._rolling_stats.get(self._get_metric_key(symbol, metric_type))
        if not stats:
            return None

        return {
            "mean": stats.mean,
            "std": stats.std,
            "count": stats.count,
            "z_score_threshold": self.z_score_threshold,
        }

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Acknowledge an anomaly."""
        for anomaly in self._anomalies:
            if anomaly.id == anomaly_id:
                anomaly.acknowledged = True
                return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Get detector status."""
        return {
            "enabled": True,
            "z_score_threshold": self.z_score_threshold,
            "window_size": self.window_size,
            "metrics_tracked": len(self._rolling_stats),
            "multivariate_samples": len(self._multivariate_buffer),
            "isolation_forest_fitted": self._isolation_forest._fitted,
            "total_anomalies": len(self._anomalies),
            "unacknowledged_anomalies": sum(
                1 for a in self._anomalies if not a.acknowledged
            ),
            "uptime_hours": (time.time() - self._start_time) / 3600,
        }


# Global detector instance
_detector: MLAnomalyDetector | None = None


def get_anomaly_detector() -> MLAnomalyDetector:
    """Get or create global anomaly detector."""
    global _detector
    if _detector is None:
        _detector = MLAnomalyDetector()
    return _detector
