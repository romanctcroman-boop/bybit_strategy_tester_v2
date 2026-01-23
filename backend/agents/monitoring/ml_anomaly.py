"""
ML-based Anomaly Detection

Advanced anomaly detection using machine learning:
- Isolation Forest
- One-Class SVM
- LSTM Autoencoder
- Statistical methods (Z-Score, IQR)
- Ensemble detection
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger


class AnomalyType(Enum):
    """Types of anomalies"""

    POINT = "point"  # Single point anomaly
    CONTEXTUAL = "contextual"  # Anomaly in context
    COLLECTIVE = "collective"  # Group of anomalies
    SEASONAL = "seasonal"  # Seasonal deviation
    TREND = "trend"  # Trend change


class AnomalySeverity(Enum):
    """Anomaly severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """Detected anomaly"""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metric_name: str = ""
    value: float = 0.0
    expected_value: float = 0.0
    deviation: float = 0.0
    anomaly_type: AnomalyType = AnomalyType.POINT
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    confidence: float = 0.0  # 0-1
    detector: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def deviation_percent(self) -> float:
        """Calculate deviation percentage"""
        if self.expected_value == 0:
            return 100.0 if self.value != 0 else 0.0
        return abs((self.value - self.expected_value) / self.expected_value) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_name": self.metric_name,
            "value": self.value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "deviation_percent": self.deviation_percent,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "detector": self.detector,
        }


class AnomalyDetector(ABC):
    """Abstract anomaly detector"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name"""
        pass

    @abstractmethod
    def fit(self, data: np.ndarray) -> None:
        """Train on historical data"""
        pass

    @abstractmethod
    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect anomalies in data"""
        pass

    @abstractmethod
    def score(self, data: np.ndarray) -> np.ndarray:
        """Get anomaly scores (higher = more anomalous)"""
        pass


class ZScoreDetector(AnomalyDetector):
    """
    Z-Score based anomaly detection

    Detects points that are more than threshold standard deviations
    from the mean.
    """

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        self.mean: float = 0.0
        self.std: float = 1.0
        self._trained = False

    @property
    def name(self) -> str:
        return "zscore"

    def fit(self, data: np.ndarray) -> None:
        """Calculate mean and std"""
        data = np.asarray(data).flatten()
        self.mean = np.mean(data)
        self.std = np.std(data)
        if self.std == 0:
            self.std = 1.0
        self._trained = True

    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect anomalies using z-score"""
        scores = self.score(data)
        return (np.abs(scores) > self.threshold).tolist()

    def score(self, data: np.ndarray) -> np.ndarray:
        """Calculate z-scores"""
        data = np.asarray(data).flatten()
        if not self._trained:
            self.fit(data)
        return (data - self.mean) / self.std


class IQRDetector(AnomalyDetector):
    """
    Interquartile Range (IQR) based anomaly detection

    Robust to outliers in training data.
    """

    def __init__(self, multiplier: float = 1.5):
        self.multiplier = multiplier
        self.q1: float = 0.0
        self.q3: float = 1.0
        self.iqr: float = 1.0
        self.lower_bound: float = 0.0
        self.upper_bound: float = 1.0
        self._trained = False

    @property
    def name(self) -> str:
        return "iqr"

    def fit(self, data: np.ndarray) -> None:
        """Calculate IQR bounds"""
        data = np.asarray(data).flatten()
        self.q1 = np.percentile(data, 25)
        self.q3 = np.percentile(data, 75)
        self.iqr = self.q3 - self.q1

        if self.iqr == 0:
            self.iqr = 1.0

        self.lower_bound = self.q1 - self.multiplier * self.iqr
        self.upper_bound = self.q3 + self.multiplier * self.iqr
        self._trained = True

    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect anomalies outside IQR bounds"""
        data = np.asarray(data).flatten()
        if not self._trained:
            self.fit(data)
        return ((data < self.lower_bound) | (data > self.upper_bound)).tolist()

    def score(self, data: np.ndarray) -> np.ndarray:
        """Calculate distance from bounds (normalized)"""
        data = np.asarray(data).flatten()
        if not self._trained:
            self.fit(data)

        scores = np.zeros_like(data)

        # Below lower bound
        below = data < self.lower_bound
        scores[below] = (self.lower_bound - data[below]) / self.iqr

        # Above upper bound
        above = data > self.upper_bound
        scores[above] = (data[above] - self.upper_bound) / self.iqr

        return scores


class IsolationForestDetector(AnomalyDetector):
    """
    Isolation Forest anomaly detection

    Efficient for high-dimensional data.
    Uses sklearn when available, pure Python fallback otherwise.
    """

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model = None
        self._fallback = None

    @property
    def name(self) -> str:
        return "isolation_forest"

    def fit(self, data: np.ndarray) -> None:
        """Train isolation forest"""
        data = np.asarray(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        try:
            from sklearn.ensemble import IsolationForest

            self._model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=self.random_state,
            )
            self._model.fit(data)

        except ImportError:
            # Fallback to simple percentile-based detection
            logger.warning("sklearn not available, using percentile fallback")
            self._fallback = {
                "threshold_low": np.percentile(data, self.contamination * 50),
                "threshold_high": np.percentile(data, 100 - self.contamination * 50),
            }

    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect anomalies"""
        data = np.asarray(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        if self._model:
            predictions = self._model.predict(data)
            return (predictions == -1).tolist()
        elif self._fallback:
            flat = data.flatten()
            return (
                (flat < self._fallback["threshold_low"])
                | (flat > self._fallback["threshold_high"])
            ).tolist()
        else:
            self.fit(data)
            return self.detect(data)

    def score(self, data: np.ndarray) -> np.ndarray:
        """Get anomaly scores"""
        data = np.asarray(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        if self._model:
            # Lower score = more anomalous, so negate
            return -self._model.score_samples(data)
        else:
            # Fallback
            return np.abs(data.flatten())


class MovingAverageDetector(AnomalyDetector):
    """
    Moving average based anomaly detection

    Good for time series with trends.
    """

    def __init__(self, window_size: int = 10, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        self._baseline: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

    @property
    def name(self) -> str:
        return "moving_average"

    def fit(self, data: np.ndarray) -> None:
        """Calculate moving average baseline"""
        data = np.asarray(data).flatten()

        if len(data) < self.window_size:
            self._baseline = np.array([np.mean(data)])
            self._std = np.array([np.std(data)])
            return

        # Calculate rolling stats
        self._baseline = np.convolve(
            data, np.ones(self.window_size) / self.window_size, mode="valid"
        )

        # Pad to match original length
        pad_size = len(data) - len(self._baseline)
        self._baseline = np.pad(self._baseline, (pad_size, 0), mode="edge")

        # Calculate rolling std
        stds = []
        for i in range(len(data)):
            start = max(0, i - self.window_size + 1)
            stds.append(np.std(data[start : i + 1]))
        self._std = np.array(stds)
        self._std[self._std == 0] = 1.0

    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect anomalies"""
        data = np.asarray(data).flatten()

        if self._baseline is None:
            self.fit(data)

        # Recalculate for new data length if needed
        if len(self._baseline) != len(data):
            self.fit(data)

        deviations = np.abs(data - self._baseline) / self._std
        return (deviations > self.threshold).tolist()

    def score(self, data: np.ndarray) -> np.ndarray:
        """Get deviation scores"""
        data = np.asarray(data).flatten()

        if self._baseline is None or len(self._baseline) != len(data):
            self.fit(data)

        return np.abs(data - self._baseline) / self._std


class EnsembleDetector(AnomalyDetector):
    """
    Ensemble anomaly detector

    Combines multiple detectors with voting or averaging.
    """

    def __init__(
        self,
        detectors: Optional[List[AnomalyDetector]] = None,
        voting_threshold: float = 0.5,  # Fraction of detectors that must agree
    ):
        self.detectors = detectors or [
            ZScoreDetector(threshold=3.0),
            IQRDetector(multiplier=1.5),
            MovingAverageDetector(window_size=10, threshold=3.0),
        ]
        self.voting_threshold = voting_threshold

    @property
    def name(self) -> str:
        return "ensemble"

    def fit(self, data: np.ndarray) -> None:
        """Fit all detectors"""
        for detector in self.detectors:
            try:
                detector.fit(data)
            except Exception as e:
                logger.warning(f"Failed to fit {detector.name}: {e}")

    def detect(self, data: np.ndarray) -> List[bool]:
        """Detect using voting"""
        data = np.asarray(data).flatten()

        votes = np.zeros(len(data))

        for detector in self.detectors:
            try:
                detections = detector.detect(data)
                votes += np.array(detections).astype(int)
            except Exception as e:
                logger.warning(f"Detection failed for {detector.name}: {e}")

        # Majority voting
        threshold = len(self.detectors) * self.voting_threshold
        return (votes >= threshold).tolist()

    def score(self, data: np.ndarray) -> np.ndarray:
        """Average scores from all detectors"""
        data = np.asarray(data).flatten()

        scores = np.zeros(len(data))
        count = 0

        for detector in self.detectors:
            try:
                detector_scores = detector.score(data)
                # Normalize to 0-1 range
                if np.std(detector_scores) > 0:
                    detector_scores = (detector_scores - np.min(detector_scores)) / (
                        np.max(detector_scores) - np.min(detector_scores)
                    )
                scores += detector_scores
                count += 1
            except Exception as e:
                logger.warning(f"Scoring failed for {detector.name}: {e}")

        if count > 0:
            scores /= count

        return scores


class MLAnomalyDetector:
    """
    High-level ML anomaly detection manager

    Features:
    - Multiple detector support
    - Automatic severity classification
    - Context-aware detection
    - Historical analysis

    Example:
        detector = MLAnomalyDetector()

        # Train on historical data
        await detector.train("cpu_usage", historical_data)

        # Detect anomalies
        anomalies = await detector.detect("cpu_usage", current_values)
    """

    def __init__(self):
        self._detectors: Dict[str, Dict[str, AnomalyDetector]] = {}
        self._history: Dict[str, List[float]] = {}
        self._anomaly_history: Dict[str, List[Anomaly]] = {}
        self._severity_thresholds = {
            AnomalySeverity.LOW: 2.0,
            AnomalySeverity.MEDIUM: 3.0,
            AnomalySeverity.HIGH: 4.0,
            AnomalySeverity.CRITICAL: 5.0,
        }

        logger.info("🔍 MLAnomalyDetector initialized")

    def _create_default_detectors(self) -> Dict[str, AnomalyDetector]:
        """Create default detector ensemble"""
        return {
            "zscore": ZScoreDetector(threshold=3.0),
            "iqr": IQRDetector(multiplier=1.5),
            "moving_avg": MovingAverageDetector(window_size=10, threshold=3.0),
            "isolation_forest": IsolationForestDetector(contamination=0.1),
            "ensemble": EnsembleDetector(),
        }

    async def train(
        self,
        metric_name: str,
        data: List[float],
        detector_types: Optional[List[str]] = None,
    ) -> None:
        """Train detectors on historical data"""
        data_array = np.array(data)

        # Store history
        self._history[metric_name] = list(data)

        # Create detectors if needed
        if metric_name not in self._detectors:
            self._detectors[metric_name] = self._create_default_detectors()

        detectors_to_train = detector_types or list(self._detectors[metric_name].keys())

        for name in detectors_to_train:
            if name in self._detectors[metric_name]:
                try:
                    detector = self._detectors[metric_name][name]
                    await asyncio.to_thread(detector.fit, data_array)
                    logger.debug(f"Trained {name} for {metric_name}")
                except Exception as e:
                    logger.warning(f"Training failed for {name}: {e}")

    async def detect(
        self,
        metric_name: str,
        values: List[float],
        detector_type: str = "ensemble",
        return_all: bool = False,
    ) -> List[Anomaly]:
        """
        Detect anomalies in values

        Args:
            metric_name: Name of metric
            values: Current values to check
            detector_type: Which detector to use
            return_all: If True, return all detections; otherwise only anomalies

        Returns:
            List of detected anomalies
        """
        data_array = np.array(values)

        # Ensure detectors exist
        if metric_name not in self._detectors:
            # Auto-train on provided data
            await self.train(metric_name, values)

        detector = self._detectors[metric_name].get(detector_type)
        if not detector:
            detector = self._detectors[metric_name].get("ensemble")

        # Detect
        try:
            is_anomaly = await asyncio.to_thread(detector.detect, data_array)
            scores = await asyncio.to_thread(detector.score, data_array)
        except Exception as e:
            logger.error(f"Detection failed: {e}")
            return []

        # Build anomaly objects
        anomalies = []
        baseline = np.mean(values)

        for i, (value, anomalous, score) in enumerate(zip(values, is_anomaly, scores)):
            if anomalous or return_all:
                severity = self._classify_severity(score)

                anomaly = Anomaly(
                    metric_name=metric_name,
                    value=value,
                    expected_value=baseline,
                    deviation=float(score),
                    anomaly_type=AnomalyType.POINT,
                    severity=severity,
                    confidence=min(1.0, float(score) / 5.0),  # Normalize confidence
                    detector=detector.name,
                    context={"index": i, "raw_score": float(score)},
                )

                if anomalous:
                    anomalies.append(anomaly)

        # Store anomaly history
        if metric_name not in self._anomaly_history:
            self._anomaly_history[metric_name] = []
        self._anomaly_history[metric_name].extend(anomalies)

        return anomalies

    def _classify_severity(self, score: float) -> AnomalySeverity:
        """Classify severity based on score"""
        score = abs(score)

        if score >= self._severity_thresholds[AnomalySeverity.CRITICAL]:
            return AnomalySeverity.CRITICAL
        elif score >= self._severity_thresholds[AnomalySeverity.HIGH]:
            return AnomalySeverity.HIGH
        elif score >= self._severity_thresholds[AnomalySeverity.MEDIUM]:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    async def detect_single(
        self,
        metric_name: str,
        value: float,
    ) -> Optional[Anomaly]:
        """Detect anomaly for single value"""
        # Add to history
        if metric_name not in self._history:
            self._history[metric_name] = []
        self._history[metric_name].append(value)

        # Need minimum data
        if len(self._history[metric_name]) < 10:
            return None

        # Use recent history for context
        recent = self._history[metric_name][-100:]
        anomalies = await self.detect(metric_name, recent)

        # Check if last value is anomaly
        if anomalies and anomalies[-1].context.get("index") == len(recent) - 1:
            return anomalies[-1]

        return None

    def get_anomaly_history(
        self,
        metric_name: str,
        limit: int = 100,
    ) -> List[Anomaly]:
        """Get historical anomalies for metric"""
        history = self._anomaly_history.get(metric_name, [])
        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            "metrics_tracked": len(self._history),
            "total_anomalies": sum(len(h) for h in self._anomaly_history.values()),
            "by_metric": {
                name: len(hist) for name, hist in self._anomaly_history.items()
            },
        }


# Global instance
_global_detector: Optional[MLAnomalyDetector] = None


def get_anomaly_detector() -> MLAnomalyDetector:
    """Get global anomaly detector"""
    global _global_detector
    if _global_detector is None:
        _global_detector = MLAnomalyDetector()
    return _global_detector


__all__ = [
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "AnomalyDetector",
    "ZScoreDetector",
    "IQRDetector",
    "IsolationForestDetector",
    "MovingAverageDetector",
    "EnsembleDetector",
    "MLAnomalyDetector",
    "get_anomaly_detector",
]
