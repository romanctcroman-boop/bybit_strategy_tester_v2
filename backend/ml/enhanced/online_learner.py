"""
Online Learning Module for Trading ML Models

Features:
- Incremental model updates without full retraining
- Adaptive learning rate based on prediction accuracy
- Concept drift-aware updates
- Model warm-start support
- Rolling window training
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class UpdateStrategy(Enum):
    """Strategy for online model updates"""

    BATCH = "batch"  # Update after accumulating a batch
    STREAMING = "streaming"  # Update on each sample
    SCHEDULED = "scheduled"  # Update at fixed intervals
    ADAPTIVE = "adaptive"  # Update when drift detected
    HYBRID = "hybrid"  # Combination of strategies


@dataclass
class LearningStats:
    """Statistics for online learning"""

    total_samples: int = 0
    update_count: int = 0
    last_update: Optional[datetime] = None

    # Performance tracking
    cumulative_accuracy: float = 0.0
    recent_accuracy: float = 0.0
    accuracy_history: List[float] = field(default_factory=list)

    # Learning dynamics
    learning_rate: float = 0.01
    learning_rate_history: List[float] = field(default_factory=list)

    # Drift metrics
    drift_detected_count: int = 0
    last_drift: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_samples": self.total_samples,
            "update_count": self.update_count,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "cumulative_accuracy": self.cumulative_accuracy,
            "recent_accuracy": self.recent_accuracy,
            "learning_rate": self.learning_rate,
            "drift_detected_count": self.drift_detected_count,
        }


@dataclass
class IncrementalModel:
    """Wrapper for incrementally trainable models"""

    model: Any
    model_type: str
    supports_partial_fit: bool

    # Configuration
    classes: Optional[np.ndarray] = None  # For classifiers
    warm_start: bool = True

    # State
    is_fitted: bool = False
    sample_count: int = 0

    def partial_fit(
        self, X: np.ndarray, y: np.ndarray, sample_weight: Optional[np.ndarray] = None
    ) -> None:
        """Incrementally fit the model"""
        if self.supports_partial_fit:
            if self.classes is not None:
                self.model.partial_fit(
                    X, y, classes=self.classes, sample_weight=sample_weight
                )
            else:
                self.model.partial_fit(X, y, sample_weight=sample_weight)
        else:
            # For non-incremental models, do warm-start training
            if hasattr(self.model, "warm_start"):
                self.model.warm_start = True
            self.model.fit(X, y, sample_weight=sample_weight)

        self.is_fitted = True
        self.sample_count += len(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities (classifiers only)"""
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        raise AttributeError("Model does not support predict_proba")


class OnlineLearner:
    """
    Online Learning System for Trading Models

    Supports incremental updates to models as new data arrives,
    with automatic adaptation to changing market conditions.

    Example:
        learner = OnlineLearner(
            model=sgd_classifier,
            update_strategy=UpdateStrategy.ADAPTIVE,
            batch_size=100
        )

        for X_batch, y_batch in data_stream:
            predictions = learner.predict(X_batch)
            learner.update(X_batch, y_batch)

            if learner.stats.recent_accuracy < 0.5:
                learner.reset()  # Full retrain needed
    """

    def __init__(
        self,
        model: Any,
        update_strategy: UpdateStrategy = UpdateStrategy.BATCH,
        batch_size: int = 100,
        window_size: int = 1000,
        learning_rate: float = 0.01,
        decay_rate: float = 0.99,
        min_learning_rate: float = 0.001,
        drift_threshold: float = 0.1,
        accuracy_threshold: float = 0.6,
        classes: Optional[np.ndarray] = None,
    ):
        # Wrap model
        self.incremental_model = self._wrap_model(model, classes)

        # Configuration
        self.update_strategy = update_strategy
        self.batch_size = batch_size
        self.window_size = window_size
        self.initial_learning_rate = learning_rate
        self.decay_rate = decay_rate
        self.min_learning_rate = min_learning_rate
        self.drift_threshold = drift_threshold
        self.accuracy_threshold = accuracy_threshold

        # Buffers
        self.X_buffer: List[np.ndarray] = []
        self.y_buffer: List[np.ndarray] = []
        self.prediction_buffer: List[float] = []
        self.actual_buffer: List[float] = []

        # Rolling window for recent data
        self.X_window: List[np.ndarray] = []
        self.y_window: List[np.ndarray] = []

        # Statistics
        self.stats = LearningStats(learning_rate=learning_rate)

        # Callbacks
        self.on_update: Optional[Callable] = None
        self.on_drift: Optional[Callable] = None

        # Drift detector (optional integration)
        self.drift_detector = None

    def _wrap_model(
        self, model: Any, classes: Optional[np.ndarray]
    ) -> IncrementalModel:
        """Wrap model for incremental learning"""
        # Check if model supports partial_fit
        supports_partial_fit = hasattr(model, "partial_fit")

        model_type = type(model).__name__

        return IncrementalModel(
            model=model,
            model_type=model_type,
            supports_partial_fit=supports_partial_fit,
            classes=classes,
        )

    def update(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Optional[np.ndarray] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Update model with new data

        Args:
            X: Feature matrix
            y: Target values
            sample_weight: Optional sample weights
            force: Force immediate update regardless of strategy

        Returns:
            Dict with update statistics
        """
        X = np.atleast_2d(X)
        y = np.atleast_1d(y)

        # Add to buffers
        self.X_buffer.append(X)
        self.y_buffer.append(y)

        # Update rolling window
        self.X_window.append(X)
        self.y_window.append(y)

        # Trim window
        while len(self.X_window) > self.window_size // self.batch_size:
            self.X_window.pop(0)
            self.y_window.pop(0)

        self.stats.total_samples += len(X)

        # Decide whether to update
        should_update = self._should_update(force)

        result = {
            "updated": False,
            "samples_buffered": sum(len(x) for x in self.X_buffer),
            "total_samples": self.stats.total_samples,
        }

        if should_update:
            # Combine buffer
            X_batch = np.vstack(self.X_buffer)
            y_batch = np.concatenate(self.y_buffer)

            # Calculate sample weights if adaptive
            if self.update_strategy == UpdateStrategy.ADAPTIVE:
                sample_weight = self._calculate_adaptive_weights(X_batch, y_batch)

            # Update model
            self._do_update(X_batch, y_batch, sample_weight)

            # Clear buffer
            self.X_buffer = []
            self.y_buffer = []

            # Update stats
            self.stats.update_count += 1
            self.stats.last_update = datetime.now(timezone.utc)
            self.stats.learning_rate_history.append(self.stats.learning_rate)

            # Decay learning rate
            self._decay_learning_rate()

            result["updated"] = True
            result["update_count"] = self.stats.update_count
            result["learning_rate"] = self.stats.learning_rate

            # Callback
            if self.on_update:
                self.on_update(result)

        return result

    def _should_update(self, force: bool) -> bool:
        """Determine if model should be updated now"""
        if force:
            return True

        buffer_size = sum(len(x) for x in self.X_buffer)

        if self.update_strategy == UpdateStrategy.STREAMING:
            return True

        elif self.update_strategy == UpdateStrategy.BATCH:
            return buffer_size >= self.batch_size

        elif self.update_strategy == UpdateStrategy.ADAPTIVE:
            # Update when accuracy drops or drift detected
            if buffer_size >= self.batch_size:
                if self.stats.recent_accuracy < self.accuracy_threshold:
                    return True
                if self._check_drift():
                    return True
            return buffer_size >= self.batch_size * 5  # Max buffer

        elif self.update_strategy == UpdateStrategy.HYBRID:
            # Combine batch and adaptive
            if buffer_size >= self.batch_size:
                return True
            if buffer_size >= self.batch_size // 2 and self._check_drift():
                return True
            return False

        return buffer_size >= self.batch_size

    def _do_update(
        self, X: np.ndarray, y: np.ndarray, sample_weight: Optional[np.ndarray] = None
    ) -> None:
        """Perform model update"""
        try:
            self.incremental_model.partial_fit(X, y, sample_weight)
            logger.info(
                f"Model updated with {len(X)} samples "
                f"(total: {self.stats.total_samples})"
            )
        except Exception as e:
            logger.error(f"Model update failed: {e}")

    def _check_drift(self) -> bool:
        """Check for concept drift"""
        if len(self.actual_buffer) < 100:
            return False

        # Simple drift detection: compare recent vs historical accuracy
        recent = self.actual_buffer[-50:]
        historical = (
            self.actual_buffer[-200:-50] if len(self.actual_buffer) > 200 else []
        )

        if not historical:
            return False

        recent_accuracy = sum(recent) / len(recent)
        historical_accuracy = sum(historical) / len(historical)

        drift_detected = (historical_accuracy - recent_accuracy) > self.drift_threshold

        if drift_detected:
            self.stats.drift_detected_count += 1
            self.stats.last_drift = datetime.now(timezone.utc)

            if self.on_drift:
                self.on_drift(
                    {
                        "recent_accuracy": recent_accuracy,
                        "historical_accuracy": historical_accuracy,
                        "drift_amount": historical_accuracy - recent_accuracy,
                    }
                )

            logger.warning(
                f"Concept drift detected: accuracy dropped from "
                f"{historical_accuracy:.2f} to {recent_accuracy:.2f}"
            )

        return drift_detected

    def _calculate_adaptive_weights(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Calculate adaptive sample weights"""
        n_samples = len(X)

        # More recent samples get higher weight
        recency_weights = np.linspace(0.5, 1.0, n_samples)

        # Normalize
        weights = recency_weights / recency_weights.sum() * n_samples

        return weights

    def _decay_learning_rate(self) -> None:
        """Decay learning rate over time"""
        new_lr = max(self.stats.learning_rate * self.decay_rate, self.min_learning_rate)
        self.stats.learning_rate = new_lr

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions with current model

        Args:
            X: Feature matrix

        Returns:
            Predictions
        """
        if not self.incremental_model.is_fitted:
            raise ValueError(
                "Model not fitted. Call update() first with training data."
            )

        return self.incremental_model.predict(np.atleast_2d(X))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities (classifiers only)"""
        return self.incremental_model.predict_proba(np.atleast_2d(X))

    def record_outcome(
        self, predictions: np.ndarray, actuals: np.ndarray
    ) -> Dict[str, float]:
        """
        Record prediction outcomes for accuracy tracking

        Args:
            predictions: Predicted values
            actuals: Actual values

        Returns:
            Dict with accuracy metrics
        """
        predictions = np.atleast_1d(predictions)
        actuals = np.atleast_1d(actuals)

        # Calculate accuracy (works for both classification and regression)
        if len(np.unique(actuals)) <= 10:  # Classification
            correct = predictions == actuals
        else:  # Regression - use threshold
            correct = np.abs(predictions - actuals) < np.std(actuals) * 0.5

        # Store outcomes
        self.prediction_buffer.extend(predictions.tolist())
        self.actual_buffer.extend(correct.astype(float).tolist())

        # Trim buffers
        max_buffer = self.window_size * 10
        if len(self.prediction_buffer) > max_buffer:
            self.prediction_buffer = self.prediction_buffer[-max_buffer:]
            self.actual_buffer = self.actual_buffer[-max_buffer:]

        # Calculate accuracies
        cumulative_accuracy = sum(self.actual_buffer) / len(self.actual_buffer)
        recent_accuracy = sum(self.actual_buffer[-100:]) / min(
            len(self.actual_buffer), 100
        )

        self.stats.cumulative_accuracy = cumulative_accuracy
        self.stats.recent_accuracy = recent_accuracy
        self.stats.accuracy_history.append(recent_accuracy)

        return {
            "batch_accuracy": float(np.mean(correct)),
            "cumulative_accuracy": cumulative_accuracy,
            "recent_accuracy": recent_accuracy,
        }

    def reset(self, keep_stats: bool = True) -> None:
        """
        Reset learner state

        Args:
            keep_stats: Whether to keep statistics
        """
        self.X_buffer = []
        self.y_buffer = []
        self.prediction_buffer = []
        self.actual_buffer = []
        self.X_window = []
        self.y_window = []

        self.incremental_model.is_fitted = False
        self.incremental_model.sample_count = 0

        if not keep_stats:
            self.stats = LearningStats(learning_rate=self.initial_learning_rate)

        logger.info("Online learner reset")

    def retrain_on_window(self) -> Dict[str, Any]:
        """Retrain model on rolling window data"""
        if not self.X_window:
            return {"status": "no_data"}

        X = np.vstack(self.X_window)
        y = np.concatenate(self.y_window)

        # Full retrain
        self.incremental_model.model.fit(X, y)
        self.incremental_model.is_fitted = True

        logger.info(f"Retrained on window with {len(X)} samples")

        return {
            "status": "retrained",
            "samples": len(X),
            "window_size": len(self.X_window),
        }

    def boost_learning_rate(self, factor: float = 2.0) -> None:
        """Temporarily boost learning rate (e.g., after drift)"""
        boosted_lr = min(self.stats.learning_rate * factor, self.initial_learning_rate)
        self.stats.learning_rate = boosted_lr
        logger.info(f"Learning rate boosted to {boosted_lr}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current learning statistics"""
        return self.stats.to_dict()

    def set_drift_detector(self, detector: Any) -> None:
        """Set external drift detector"""
        self.drift_detector = detector


class AdaptiveLearningRateScheduler:
    """
    Adaptive learning rate scheduler for online learning

    Adjusts learning rate based on:
    - Prediction accuracy trends
    - Concept drift detection
    - Model convergence
    """

    def __init__(
        self,
        initial_lr: float = 0.01,
        min_lr: float = 0.0001,
        max_lr: float = 0.1,
        patience: int = 10,
        factor: float = 0.5,
        threshold: float = 0.01,
    ):
        self.initial_lr = initial_lr
        self.min_lr = min_lr
        self.max_lr = max_lr
        self.patience = patience
        self.factor = factor
        self.threshold = threshold

        self.current_lr = initial_lr
        self.best_accuracy = 0.0
        self.wait = 0
        self.history: List[float] = []

    def step(self, accuracy: float) -> float:
        """
        Update learning rate based on accuracy

        Args:
            accuracy: Current model accuracy

        Returns:
            New learning rate
        """
        self.history.append(accuracy)

        # Check for improvement
        if accuracy > self.best_accuracy + self.threshold:
            self.best_accuracy = accuracy
            self.wait = 0
        else:
            self.wait += 1

        # Reduce LR if no improvement
        if self.wait >= self.patience:
            self.current_lr = max(self.current_lr * self.factor, self.min_lr)
            self.wait = 0
            logger.info(f"Reduced learning rate to {self.current_lr}")

        return self.current_lr

    def on_drift(self) -> float:
        """Increase learning rate when drift detected"""
        self.current_lr = min(self.current_lr / self.factor, self.max_lr)
        self.best_accuracy = 0.0  # Reset best
        self.wait = 0
        logger.info(f"Increased learning rate to {self.current_lr} after drift")
        return self.current_lr

    def reset(self) -> None:
        """Reset scheduler"""
        self.current_lr = self.initial_lr
        self.best_accuracy = 0.0
        self.wait = 0
        self.history = []
