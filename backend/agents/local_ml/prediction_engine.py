"""
Ensemble Prediction Engine

Provides ensemble ML predictions for trading signals:
- Multiple model aggregation
- Confidence-weighted voting
- Uncertainty quantification
- Online learning support

Combines traditional ML with AI agent insights.
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
from loguru import logger


class SignalType(Enum):
    """Trading signal types"""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class ModelType(Enum):
    """Types of prediction models"""

    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOST = "gradient_boost"
    NEURAL_NETWORK = "neural_network"
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    ENSEMBLE = "ensemble"


@dataclass
class PredictionResult:
    """Result from prediction engine"""

    signal: SignalType
    confidence: float
    probability: float  # Probability of positive return
    expected_return: float
    uncertainty: float  # Model uncertainty
    model_votes: dict[str, SignalType]
    model_confidences: dict[str, float]
    features_importance: dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal.value,
            "confidence": self.confidence,
            "probability": self.probability,
            "expected_return": self.expected_return,
            "uncertainty": self.uncertainty,
            "model_votes": {k: v.value for k, v in self.model_votes.items()},
            "model_confidences": self.model_confidences,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ModelWrapper:
    """Wrapper for individual prediction models"""

    name: str
    model_type: ModelType
    model: Any
    weight: float = 1.0
    accuracy: float = 0.5
    predictions_count: int = 0
    correct_predictions: int = 0

    def update_accuracy(self, was_correct: bool) -> None:
        """Update model accuracy with new prediction result"""
        self.predictions_count += 1
        if was_correct:
            self.correct_predictions += 1
        self.accuracy = self.correct_predictions / max(self.predictions_count, 1)


class PredictionEngine:
    """
    Ensemble prediction engine for trading signals

    Combines multiple ML models with AI-enhanced features:
    - Weighted voting across models
    - Dynamic weight adjustment based on performance
    - Uncertainty quantification
    - Feature importance tracking

    Example:
        engine = PredictionEngine()
        engine.add_model("rf", sklearn_rf_model, ModelType.RANDOM_FOREST)
        engine.add_model("gb", sklearn_gb_model, ModelType.GRADIENT_BOOST)

        result = await engine.predict(features)
        print(f"Signal: {result.signal}, Confidence: {result.confidence:.2%}")
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        voting_threshold: float = 0.6,
    ):
        """
        Initialize prediction engine

        Args:
            min_confidence: Minimum confidence for non-neutral signal
            voting_threshold: Threshold for majority voting
        """
        self.min_confidence = min_confidence
        self.voting_threshold = voting_threshold

        self.models: dict[str, ModelWrapper] = {}
        self.prediction_history: list[PredictionResult] = []

        # Feature importance tracking
        self.feature_importance: dict[str, float] = {}

        # Statistics
        self.stats = {
            "total_predictions": 0,
            "avg_confidence": 0.0,
            "signal_distribution": {s.value: 0 for s in SignalType},
        }

        logger.info("📊 PredictionEngine initialized")

    def add_model(
        self,
        name: str,
        model: Any,
        model_type: ModelType,
        weight: float = 1.0,
    ) -> None:
        """
        Add a model to the ensemble

        Args:
            name: Model name/identifier
            model: Trained model with predict/predict_proba methods
            model_type: Type of model
            weight: Initial voting weight
        """
        self.models[name] = ModelWrapper(
            name=name,
            model_type=model_type,
            model=model,
            weight=weight,
        )
        logger.info(f"📊 Added model: {name} ({model_type.value})")

    def remove_model(self, name: str) -> bool:
        """Remove model from ensemble"""
        if name in self.models:
            del self.models[name]
            return True
        return False

    async def predict(
        self,
        features: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> PredictionResult:
        """
        Generate ensemble prediction

        Args:
            features: Feature vector or matrix
            feature_names: Optional feature names for importance tracking

        Returns:
            PredictionResult with signal and confidence
        """
        if not self.models:
            return PredictionResult(
                signal=SignalType.NEUTRAL,
                confidence=0.0,
                probability=0.5,
                expected_return=0.0,
                uncertainty=1.0,
                model_votes={},
                model_confidences={},
                features_importance={},
            )

        model_votes: dict[str, SignalType] = {}
        model_confidences: dict[str, float] = {}
        model_probabilities: list[float] = []
        model_returns: list[float] = []

        # Get predictions from all models
        for name, wrapper in self.models.items():
            try:
                (
                    vote,
                    confidence,
                    probability,
                    expected_return,
                ) = await self._get_model_prediction(wrapper, features)
                model_votes[name] = vote
                model_confidences[name] = confidence
                model_probabilities.append(probability * wrapper.weight)
                model_returns.append(expected_return * wrapper.weight)
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")

        if not model_votes:
            return PredictionResult(
                signal=SignalType.NEUTRAL,
                confidence=0.0,
                probability=0.5,
                expected_return=0.0,
                uncertainty=1.0,
                model_votes={},
                model_confidences={},
                features_importance={},
            )

        # Aggregate predictions
        signal, confidence = self._aggregate_votes(model_votes, model_confidences)

        # Calculate weighted probability
        total_weight = sum(w.weight for w in self.models.values())
        probability = (
            sum(model_probabilities) / total_weight if total_weight > 0 else 0.5
        )
        expected_return = sum(model_returns) / total_weight if total_weight > 0 else 0.0

        # Calculate uncertainty
        uncertainty = self._calculate_uncertainty(model_confidences)

        # Get feature importance
        features_importance = self._aggregate_feature_importance(feature_names)

        result = PredictionResult(
            signal=signal,
            confidence=confidence,
            probability=probability,
            expected_return=expected_return,
            uncertainty=uncertainty,
            model_votes=model_votes,
            model_confidences=model_confidences,
            features_importance=features_importance,
        )

        self.prediction_history.append(result)
        self._update_stats(result)

        logger.debug(
            f"📊 Prediction: {signal.value}, "
            f"confidence={confidence:.2f}, uncertainty={uncertainty:.2f}"
        )

        return result

    async def _get_model_prediction(
        self,
        wrapper: ModelWrapper,
        features: np.ndarray,
    ) -> tuple[SignalType, float, float, float]:
        """Get prediction from single model"""
        model = wrapper.model

        # Ensure 2D features
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Get prediction
        def get_prediction():
            # Try probability prediction first
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(features)[0]
                # Assume binary classification: 0=down, 1=up
                prob_up = proba[1] if len(proba) > 1 else proba[0]
                return prob_up
            else:
                # Just get class prediction
                pred = model.predict(features)[0]
                return 1.0 if pred > 0.5 else 0.0

        try:
            prob_up = await asyncio.to_thread(get_prediction)
        except Exception:
            prob_up = 0.5

        # Convert probability to signal
        if prob_up >= 0.7:
            signal = SignalType.STRONG_BUY
            confidence = prob_up
        elif prob_up >= 0.55:
            signal = SignalType.BUY
            confidence = prob_up
        elif prob_up <= 0.3:
            signal = SignalType.STRONG_SELL
            confidence = 1 - prob_up
        elif prob_up <= 0.45:
            signal = SignalType.SELL
            confidence = 1 - prob_up
        else:
            signal = SignalType.NEUTRAL
            confidence = 1 - abs(prob_up - 0.5) * 2

        # Estimate expected return (simplified)
        expected_return = (prob_up - 0.5) * 0.02  # ±1% expected

        return signal, confidence, prob_up, expected_return

    def _aggregate_votes(
        self,
        votes: dict[str, SignalType],
        confidences: dict[str, float],
    ) -> tuple[SignalType, float]:
        """Aggregate model votes using weighted voting"""
        if not votes:
            return SignalType.NEUTRAL, 0.0

        # Count weighted votes
        signal_weights: dict[SignalType, float] = dict.fromkeys(SignalType, 0.0)

        for name, vote in votes.items():
            weight = self.models[name].weight * confidences.get(name, 0.5)
            signal_weights[vote] += weight

        total_weight = sum(signal_weights.values())
        if total_weight == 0:
            return SignalType.NEUTRAL, 0.0

        # Find winning signal
        best_signal = max(signal_weights.keys(), key=lambda s: signal_weights[s])
        best_weight = signal_weights[best_signal]

        # Calculate confidence
        confidence = best_weight / total_weight

        # Apply minimum confidence threshold
        if confidence < self.min_confidence:
            return SignalType.NEUTRAL, confidence

        return best_signal, confidence

    def _calculate_uncertainty(self, confidences: dict[str, float]) -> float:
        """Calculate prediction uncertainty based on model disagreement"""
        if len(confidences) < 2:
            return 0.5

        values = list(confidences.values())

        # Standard deviation of confidences
        std = statistics.stdev(values) if len(values) > 1 else 0.0

        # Low average confidence also increases uncertainty
        avg = statistics.mean(values)

        # Combine: high std or low avg = high uncertainty
        uncertainty = std * 0.5 + (1 - avg) * 0.5

        return max(0.0, min(1.0, uncertainty))

    def _aggregate_feature_importance(
        self,
        feature_names: list[str] | None,
    ) -> dict[str, float]:
        """Aggregate feature importance across models"""
        if not feature_names:
            return {}

        importance: dict[str, float] = dict.fromkeys(feature_names, 0.0)
        weight_sum = 0.0

        for wrapper in self.models.values():
            model = wrapper.model

            if hasattr(model, "feature_importances_"):
                fi = model.feature_importances_
                for i, name in enumerate(feature_names):
                    if i < len(fi):
                        importance[name] += fi[i] * wrapper.weight
                weight_sum += wrapper.weight

        if weight_sum > 0:
            importance = {k: v / weight_sum for k, v in importance.items()}

        # Update tracked importance
        self.feature_importance = importance

        return importance

    def _update_stats(self, result: PredictionResult) -> None:
        """Update statistics"""
        self.stats["total_predictions"] += 1
        self.stats["signal_distribution"][result.signal.value] += 1

        total = self.stats["total_predictions"]
        prev_avg = self.stats["avg_confidence"]
        self.stats["avg_confidence"] = (
            prev_avg * (total - 1) + result.confidence
        ) / total

    def update_model_performance(
        self,
        actual_return: float,
        threshold: float = 0.0,
    ) -> None:
        """
        Update model weights based on actual outcome

        Args:
            actual_return: Actual return/outcome
            threshold: Return threshold for correct prediction
        """
        if not self.prediction_history:
            return

        last_prediction = self.prediction_history[-1]
        predicted_positive = last_prediction.signal in [
            SignalType.BUY,
            SignalType.STRONG_BUY,
        ]
        actual_positive = actual_return > threshold

        # Track correctness for ensemble accuracy
        was_correct = predicted_positive == actual_positive  # noqa: F841

        # Update individual model accuracy
        for name, vote in last_prediction.model_votes.items():
            if name in self.models:
                model_predicted_positive = vote in [
                    SignalType.BUY,
                    SignalType.STRONG_BUY,
                ]
                model_correct = model_predicted_positive == actual_positive
                self.models[name].update_accuracy(model_correct)

        # Adjust weights based on accuracy
        self._rebalance_weights()

    def _rebalance_weights(self) -> None:
        """Rebalance model weights based on performance"""
        if not self.models:
            return

        # Calculate new weights based on accuracy
        total_accuracy = sum(m.accuracy for m in self.models.values())

        if total_accuracy > 0:
            for _name, model in self.models.items():
                # Weight proportional to accuracy, with minimum floor
                model.weight = max(
                    0.2, model.accuracy / total_accuracy * len(self.models)
                )

    def get_model_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for each model"""
        return {
            name: {
                "type": wrapper.model_type.value,
                "weight": wrapper.weight,
                "accuracy": wrapper.accuracy,
                "predictions": wrapper.predictions_count,
            }
            for name, wrapper in self.models.items()
        }

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            "model_count": len(self.models),
            "models": self.get_model_stats(),
        }


# Simple model implementations for testing
class SimpleMovingAverageModel:
    """Simple MA-based prediction model for testing"""

    def __init__(self, short_window: int = 10, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Predict based on MA crossover logic encoded in features"""
        # Assume features contain price series or derived indicators
        if features.shape[1] > 1:
            # Use last two features as short and long MA
            short_ma = features[0, -2]
            long_ma = features[0, -1]

            if short_ma > long_ma:
                prob_up = 0.6 + min(0.2, (short_ma - long_ma) / long_ma * 10)
            else:
                prob_up = 0.4 - min(0.2, (long_ma - short_ma) / long_ma * 10)
        else:
            prob_up = 0.5

        return np.array([[1 - prob_up, prob_up]])


class SimpleMomentumModel:
    """Simple momentum-based prediction model for testing"""

    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Predict based on momentum"""
        if features.shape[1] >= self.lookback:
            # Calculate momentum as percent change
            momentum = (features[0, -1] - features[0, 0]) / features[0, 0]

            # Scale to probability
            prob_up = 0.5 + np.clip(momentum * 50, -0.3, 0.3)
        else:
            prob_up = 0.5

        return np.array([[1 - prob_up, prob_up]])


__all__ = [
    "ModelType",
    "ModelWrapper",
    "PredictionEngine",
    "PredictionResult",
    "SignalType",
    "SimpleMomentumModel",
    "SimpleMovingAverageModel",
]
