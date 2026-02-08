"""
Reinforcement Learning from Human/AI Feedback Module

Implements RLHF and RLAIF for autonomous agent self-improvement.
Uses preference learning to optimize agent behavior based on:
- Human feedback (explicit ratings)
- AI feedback (other agent evaluations)
- Self-evaluation (metacognitive assessment)

Key concepts:
1. Preference Collection: Gather A/B comparisons on agent outputs
2. Reward Modeling: Train a model to predict preferences
3. Policy Optimization: Use reward model to improve responses

References:
- "Training language models to follow instructions" (Ouyang et al., 2022)
- "Constitutional AI" (Anthropic, 2023)
- "RLAIF: Scaling Reinforcement Learning from Human Feedback" (2024)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class PreferenceType(Enum):
    """Type of preference feedback"""

    HUMAN = "human"  # Human-provided preference
    AI = "ai"  # AI-evaluated preference (RLAIF)
    SELF = "self"  # Self-evaluated preference
    CONSENSUS = "consensus"  # Multi-agent consensus


class ResponseQuality(Enum):
    """Quality rating for individual responses"""

    EXCELLENT = 5
    GOOD = 4
    ACCEPTABLE = 3
    POOR = 2
    UNACCEPTABLE = 1


@dataclass
class FeedbackSample:
    """A single feedback sample for RLHF training"""

    id: str
    prompt: str
    response_a: str
    response_b: str
    preference: int  # -1 = A better, 0 = tie, 1 = B better
    preference_type: PreferenceType
    confidence: float  # 0.0 to 1.0
    reasoning: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "response_a": self.response_a,
            "response_b": self.response_b,
            "preference": self.preference,
            "preference_type": self.preference_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackSample:
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            response_a=data["response_a"],
            response_b=data["response_b"],
            preference=data["preference"],
            preference_type=PreferenceType(data["preference_type"]),
            confidence=data["confidence"],
            reasoning=data.get("reasoning"),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QualityScore:
    """Quality score for a single response"""

    helpfulness: float = 0.0
    accuracy: float = 0.0
    relevance: float = 0.0
    safety: float = 0.0
    clarity: float = 0.0
    creativity: float = 0.0

    @property
    def overall(self) -> float:
        """Weighted overall score"""
        weights = {
            "helpfulness": 0.25,
            "accuracy": 0.25,
            "relevance": 0.20,
            "safety": 0.15,
            "clarity": 0.10,
            "creativity": 0.05,
        }
        score = 0.0
        for attr, weight in weights.items():
            score += getattr(self, attr) * weight
        return score


class RewardModel:
    """
    Simple reward model for preference prediction

    Uses a Bradley-Terry style model to learn from pairwise preferences.
    In production, this could be replaced with a neural network.

    Features (v2.0):
    - Learning rate scheduler (cosine annealing)
    - Early stopping with patience
    - Cross-validation support
    - Async batch training
    """

    def __init__(self, learning_rate: float = 0.1, patience: int = 3):
        self.feature_weights: dict[str, float] = {
            "length_ratio": 0.0,
            "keyword_overlap": 0.0,
            "sentiment_score": 0.0,
            "structure_score": 0.0,  # NEW: sentence structure quality
            "specificity_score": 0.0,  # NEW: specific vs vague
        }
        self.training_samples: list[FeedbackSample] = []
        self.training_history: list[dict[str, float]] = []
        self.initial_lr = learning_rate
        self.patience = patience
        self.best_weights: dict[str, float] = {}
        self.best_loss: float = float("inf")

    def extract_features(self, prompt: str, response: str) -> dict[str, float]:
        """Extract features from a response"""
        features = {}

        # Length features
        prompt_words = len(prompt.split())
        response_words = len(response.split())
        features["length_ratio"] = min(response_words / max(prompt_words, 1), 5.0) / 5.0

        # Keyword overlap
        prompt_keywords = {word.lower() for word in prompt.split() if len(word) > 3}
        response_keywords = {word.lower() for word in response.split() if len(word) > 3}
        if prompt_keywords:
            features["keyword_overlap"] = len(prompt_keywords & response_keywords) / len(prompt_keywords)
        else:
            features["keyword_overlap"] = 0.0

        # Simple sentiment (presence of positive/negative words)
        positive_words = {"good", "great", "excellent", "helpful", "clear", "correct", "accurate", "useful"}
        negative_words = {"error", "wrong", "bad", "unclear", "incorrect", "fail", "confusing", "poor"}

        response_lower = response.lower()
        pos_count = sum(1 for w in positive_words if w in response_lower)
        neg_count = sum(1 for w in negative_words if w in response_lower)
        features["sentiment_score"] = (pos_count - neg_count + 5) / 10.0

        # NEW: Structure score - good sentence structure
        sentences = response.count(".") + response.count("!") + response.count("?")
        if sentences > 0:
            avg_sentence_len = response_words / sentences
            # Ideal sentence length is 15-25 words
            if 15 <= avg_sentence_len <= 25:
                features["structure_score"] = 1.0
            elif 10 <= avg_sentence_len <= 30:
                features["structure_score"] = 0.7
            else:
                features["structure_score"] = 0.4
        else:
            features["structure_score"] = 0.3

        # NEW: Specificity score - specific terms vs vague
        specific_indicators = ["specifically", "exactly", "precisely", "for example", "such as", "%", "number"]
        vague_indicators = ["maybe", "perhaps", "might", "could", "possibly", "some", "sometimes"]

        specific_count = sum(1 for ind in specific_indicators if ind in response_lower)
        vague_count = sum(1 for ind in vague_indicators if ind in response_lower)
        features["specificity_score"] = min(1.0, (specific_count - vague_count * 0.5 + 3) / 6)

        return features

    def predict_reward(self, prompt: str, response: str) -> float:
        """Predict reward score for a response"""
        features = self.extract_features(prompt, response)

        reward = 0.0
        for feature_name, feature_value in features.items():
            weight = self.feature_weights.get(feature_name, 0.0)
            reward += weight * feature_value

        # Normalize to 0-1
        return max(0.0, min(1.0, (reward + 1) / 2))

    def _cosine_lr(self, epoch: int, total_epochs: int, initial_lr: float) -> float:
        """Cosine annealing learning rate scheduler"""
        import math

        return initial_lr * (1 + math.cos(math.pi * epoch / total_epochs)) / 2

    def train(
        self,
        samples: list[FeedbackSample],
        epochs: int = 10,
        lr: float = 0.1,
        use_early_stopping: bool = True,
        validation_split: float = 0.2,
    ) -> dict[str, float]:
        """
        Train reward model on feedback samples with improvements.

        Features:
        - Cosine annealing learning rate
        - Early stopping with patience
        - Optional validation split for cross-validation
        """
        import math
        import random

        self.training_samples.extend(samples)

        # Split into train/validation if enabled
        if use_early_stopping and len(samples) >= 5:
            random.shuffle(samples)
            split_idx = max(1, int(len(samples) * (1 - validation_split)))
            train_samples = samples[:split_idx]
            val_samples = samples[split_idx:]
        else:
            train_samples = samples
            val_samples = []

        total_loss = 0.0
        correct = 0
        no_improvement_count = 0

        # Save initial weights for potential rollback
        self.best_weights = dict(self.feature_weights)

        for epoch in range(epochs):
            epoch_loss = 0.0
            epoch_correct = 0

            # Cosine annealing LR
            current_lr = self._cosine_lr(epoch, epochs, lr)

            for sample in train_samples:
                # Extract features for both responses
                features_a = self.extract_features(sample.prompt, sample.response_a)
                features_b = self.extract_features(sample.prompt, sample.response_b)

                # Compute rewards
                reward_a = sum(self.feature_weights.get(k, 0) * v for k, v in features_a.items())
                reward_b = sum(self.feature_weights.get(k, 0) * v for k, v in features_b.items())

                # Predicted preference (sigmoid of difference)
                diff = reward_b - reward_a
                pred_prob = 1 / (1 + math.exp(-min(max(diff, -20), 20)))  # Clip for stability

                # Convert sample.preference to probability
                if sample.preference == 1:
                    target = 1.0
                elif sample.preference == -1:
                    target = 0.0
                else:
                    target = 0.5

                # Binary cross entropy loss
                eps = 1e-10
                loss = -(target * math.log(pred_prob + eps) + (1 - target) * math.log(1 - pred_prob + eps))
                epoch_loss += loss
                total_loss += loss

                # Gradient update with L2 regularization
                error = (pred_prob - target) * sample.confidence
                for feature_name in self.feature_weights:
                    grad = error * (features_b.get(feature_name, 0) - features_a.get(feature_name, 0))
                    # L2 regularization
                    grad += 0.01 * self.feature_weights[feature_name]
                    self.feature_weights[feature_name] -= current_lr * grad

                # Track accuracy
                pred = 1 if reward_b > reward_a else (-1 if reward_a > reward_b else 0)
                if pred == sample.preference:
                    epoch_correct += 1
                    correct += 1

            # Validation and early stopping
            if val_samples and use_early_stopping:
                val_loss = self._compute_validation_loss(val_samples)
                if val_loss < self.best_loss:
                    self.best_loss = val_loss
                    self.best_weights = dict(self.feature_weights)
                    no_improvement_count = 0
                else:
                    no_improvement_count += 1

                if no_improvement_count >= self.patience:
                    logger.info(f"⏹️ Early stopping at epoch {epoch + 1}")
                    # Restore best weights
                    self.feature_weights = dict(self.best_weights)
                    break

        accuracy = correct / max(len(train_samples) * (epoch + 1), 1)
        avg_loss = total_loss / max(len(train_samples) * (epoch + 1), 1)

        result = {
            "loss": avg_loss,
            "accuracy": accuracy,
            "samples": len(samples),
            "weights": dict(self.feature_weights),
            "epochs_run": epoch + 1,
            "early_stopped": no_improvement_count >= self.patience,
        }
        self.training_history.append(result)

        logger.info(f"🎓 Reward model trained: accuracy={accuracy:.2%}, loss={avg_loss:.4f}, epochs={epoch + 1}")
        return result

    def _compute_validation_loss(self, val_samples: list[FeedbackSample]) -> float:
        """Compute validation loss for early stopping"""
        import math

        total_loss = 0.0
        for sample in val_samples:
            features_a = self.extract_features(sample.prompt, sample.response_a)
            features_b = self.extract_features(sample.prompt, sample.response_b)

            reward_a = sum(self.feature_weights.get(k, 0) * v for k, v in features_a.items())
            reward_b = sum(self.feature_weights.get(k, 0) * v for k, v in features_b.items())

            diff = reward_b - reward_a
            pred_prob = 1 / (1 + math.exp(-min(max(diff, -20), 20)))

            if sample.preference == 1:
                target = 1.0
            elif sample.preference == -1:
                target = 0.0
            else:
                target = 0.5

            eps = 1e-10
            loss = -(target * math.log(pred_prob + eps) + (1 - target) * math.log(1 - pred_prob + eps))
            total_loss += loss

        return total_loss / max(len(val_samples), 1)

    def cross_validate(self, samples: list[FeedbackSample], k_folds: int = 5, epochs: int = 10) -> dict[str, float]:
        """
        Perform k-fold cross-validation on feedback samples.

        Returns average metrics across folds.
        """
        import random

        if len(samples) < k_folds:
            logger.warning(f"Not enough samples for {k_folds}-fold CV, using {len(samples)} folds")
            k_folds = len(samples)

        random.shuffle(samples)
        fold_size = len(samples) // k_folds

        fold_results = []

        for fold in range(k_folds):
            # Split data
            val_start = fold * fold_size
            val_end = val_start + fold_size
            val_samples = samples[val_start:val_end]
            train_samples = samples[:val_start] + samples[val_end:]

            # Reset weights
            for key in self.feature_weights:
                self.feature_weights[key] = 0.0

            # Train on fold
            result = self.train(train_samples, epochs=epochs, use_early_stopping=False)

            # Evaluate on validation
            val_loss = self._compute_validation_loss(val_samples)
            fold_results.append(
                {
                    "train_loss": result["loss"],
                    "train_accuracy": result["accuracy"],
                    "val_loss": val_loss,
                }
            )

        # Average results
        avg_results = {
            "avg_train_loss": sum(r["train_loss"] for r in fold_results) / k_folds,
            "avg_train_accuracy": sum(r["train_accuracy"] for r in fold_results) / k_folds,
            "avg_val_loss": sum(r["val_loss"] for r in fold_results) / k_folds,
            "k_folds": k_folds,
        }

        logger.info(f"📊 Cross-validation: avg_val_loss={avg_results['avg_val_loss']:.4f}")
        return avg_results


class RLHFModule:
    """
    Reinforcement Learning from Human/AI Feedback

    Provides:
    1. Feedback Collection: Gather preferences from humans or AI
    2. Reward Modeling: Train preference predictor
    3. Response Optimization: Generate optimized responses
    4. Self-Evaluation: Assess own performance

    Example:
        rlhf = RLHFModule(persist_path="./feedback_data")

        # Collect AI feedback (RLAIF)
        feedback = await rlhf.collect_ai_feedback(
            prompt="Explain RSI indicator",
            responses=["Response A...", "Response B..."],
            evaluator_agent=my_agent
        )

        # Train reward model
        rlhf.train_reward_model()

        # Evaluate response
        score = await rlhf.evaluate_response(prompt, response)
    """

    def __init__(
        self,
        persist_path: str | None = None,
        min_samples_for_training: int = 10,
    ):
        """
        Initialize RLHF module

        Args:
            persist_path: Path for feedback persistence
            min_samples_for_training: Minimum samples before training
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.min_samples_for_training = min_samples_for_training

        self.feedback_buffer: list[FeedbackSample] = []
        self.reward_model = RewardModel()
        self.evaluator_interface = None  # Will be set to AgentInterface

        # Statistics
        self.stats = {
            "total_feedback": 0,
            "human_feedback": 0,
            "ai_feedback": 0,
            "self_feedback": 0,
            "training_runs": 0,
        }

        # Load persisted feedback
        if self.persist_path:
            self._load_feedback()

        logger.info("🎯 RLHF Module initialized")

    async def collect_human_feedback(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
        preference: int,
        reasoning: str | None = None,
    ) -> FeedbackSample:
        """
        Store human preference feedback

        Args:
            prompt: Original prompt
            response_a: First response
            response_b: Second response
            preference: -1 = A better, 0 = tie, 1 = B better
            reasoning: Optional human reasoning
        """
        sample = FeedbackSample(
            id=f"human_{uuid.uuid4().hex[:12]}",
            prompt=prompt,
            response_a=response_a,
            response_b=response_b,
            preference=preference,
            preference_type=PreferenceType.HUMAN,
            confidence=1.0,  # Human feedback has full confidence
            reasoning=reasoning,
            metadata={"source": "user_interface"},
        )

        self._add_feedback(sample)
        self.stats["human_feedback"] += 1

        return sample

    async def collect_ai_feedback(
        self,
        prompt: str,
        responses: list[str],
        evaluator_fn: Any | None = None,
    ) -> list[FeedbackSample]:
        """
        Collect AI feedback on responses (RLAIF)

        Uses another AI agent to evaluate and rank responses.

        Args:
            prompt: Original prompt
            responses: List of candidate responses
            evaluator_fn: Optional async function(prompt, resp_a, resp_b) -> (preference, confidence, reasoning)
        """
        if len(responses) < 2:
            logger.warning("Need at least 2 responses for AI feedback")
            return []

        samples = []

        # Compare all pairs
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                response_a = responses[i]
                response_b = responses[j]

                # Get AI evaluation
                if evaluator_fn:
                    try:
                        preference, confidence, reasoning = await evaluator_fn(prompt, response_a, response_b)
                    except Exception as e:
                        logger.error(f"AI evaluation failed: {e}")
                        continue
                else:
                    # Default: use simple heuristics
                    preference, confidence, reasoning = self._heuristic_evaluation(prompt, response_a, response_b)

                sample = FeedbackSample(
                    id=f"ai_{uuid.uuid4().hex[:12]}",
                    prompt=prompt,
                    response_a=response_a,
                    response_b=response_b,
                    preference=preference,
                    preference_type=PreferenceType.AI,
                    confidence=confidence,
                    reasoning=reasoning,
                    metadata={
                        "response_a_index": i,
                        "response_b_index": j,
                    },
                )

                self._add_feedback(sample)
                samples.append(sample)

        self.stats["ai_feedback"] += len(samples)
        logger.info(f"🤖 Collected {len(samples)} AI feedback samples")

        return samples

    async def self_evaluate(
        self,
        prompt: str,
        response: str,
        criteria: list[str] | None = None,
    ) -> QualityScore:
        """
        Self-evaluate response quality

        Uses metacognitive prompts to assess own performance.

        Args:
            prompt: Original prompt
            response: Generated response
            criteria: Optional specific criteria to evaluate
        """
        criteria = criteria or [
            "helpfulness",
            "accuracy",
            "relevance",
            "safety",
            "clarity",
        ]

        scores = QualityScore()

        # Simple heuristic self-evaluation
        # In production, use the agent to self-critique

        # Helpfulness: Does it address the request?
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        overlap = len(prompt_words & response_words) / max(len(prompt_words), 1)
        scores.helpfulness = min(1.0, overlap * 2 + 0.3)

        # Accuracy: Check for hedging/uncertainty
        uncertainty_words = [
            "maybe",
            "possibly",
            "might",
            "could",
            "perhaps",
            "uncertain",
        ]
        uncertainty_count = sum(1 for w in uncertainty_words if w in response.lower())
        scores.accuracy = max(0.0, 1.0 - uncertainty_count * 0.1)

        # Relevance: Response length vs prompt
        ratio = len(response) / max(len(prompt), 1)
        scores.relevance = min(1.0, 0.5 + min(ratio, 3) / 6)

        # Safety: Check for dangerous patterns
        unsafe_patterns = ["execute", "delete", "rm -rf", "eval(", "drop table"]
        has_unsafe = any(p in response.lower() for p in unsafe_patterns)
        scores.safety = 0.3 if has_unsafe else 1.0

        # Clarity: Sentence structure
        sentences = response.count(".") + response.count("!") + response.count("?")
        avg_sentence_len = len(response.split()) / max(sentences, 1)
        scores.clarity = 1.0 if 10 <= avg_sentence_len <= 25 else 0.7

        logger.debug(f"📊 Self-evaluation: overall={scores.overall:.2f}")
        return scores

    def train_reward_model(self, force: bool = False) -> dict[str, float] | None:
        """
        Train reward model on collected feedback

        Args:
            force: Train even if below minimum samples

        Returns:
            Training metrics or None if not enough samples
        """
        if len(self.feedback_buffer) < self.min_samples_for_training and not force:
            logger.info(f"⏳ Need {self.min_samples_for_training - len(self.feedback_buffer)} more samples to train")
            return None

        result = self.reward_model.train(self.feedback_buffer)
        self.stats["training_runs"] += 1

        return result

    def predict_preference(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
    ) -> tuple[int, float]:
        """
        Predict which response is preferred

        Returns:
            Tuple of (preference, confidence)
            preference: -1 = A, 0 = tie, 1 = B
        """
        reward_a = self.reward_model.predict_reward(prompt, response_a)
        reward_b = self.reward_model.predict_reward(prompt, response_b)

        diff = abs(reward_a - reward_b)

        if diff < 0.1:
            return (0, 1.0 - diff)
        elif reward_a > reward_b:
            return (-1, min(1.0, diff * 2))
        else:
            return (1, min(1.0, diff * 2))

    def _heuristic_evaluation(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
    ) -> tuple[int, float, str]:
        """Simple heuristic-based evaluation"""
        # Length preference (moderate length is better)
        ideal_length = len(prompt) * 3
        dist_a = abs(len(response_a) - ideal_length)
        dist_b = abs(len(response_b) - ideal_length)

        # Keyword relevance
        prompt_words = set(prompt.lower().split())
        rel_a = len(prompt_words & set(response_a.lower().split()))
        rel_b = len(prompt_words & set(response_b.lower().split()))

        # Combine signals
        score_a = -dist_a / 1000 + rel_a * 0.1
        score_b = -dist_b / 1000 + rel_b * 0.1

        if abs(score_a - score_b) < 0.1:
            return (0, 0.5, "Responses are similar in quality")
        elif score_a > score_b:
            return (-1, 0.7, "Response A has better length and relevance")
        else:
            return (1, 0.7, "Response B has better length and relevance")

    def _add_feedback(self, sample: FeedbackSample) -> None:
        """Add feedback sample to buffer and persist"""
        self.feedback_buffer.append(sample)
        self.stats["total_feedback"] += 1

        if self.persist_path:
            self._persist_feedback(sample)

        # Auto-train if buffer is large enough
        if len(self.feedback_buffer) >= self.min_samples_for_training * 2:
            self.train_reward_model()

    def _persist_feedback(self, sample: FeedbackSample) -> None:
        """Persist feedback sample to disk"""
        if not self.persist_path:
            return

        self.persist_path.mkdir(parents=True, exist_ok=True)
        file_path = self.persist_path / f"{sample.id}.json"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(sample.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist feedback: {e}")

    def _load_feedback(self) -> None:
        """Load persisted feedback from disk"""
        if not self.persist_path or not self.persist_path.exists():
            return

        for file_path in self.persist_path.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    sample = FeedbackSample.from_dict(data)
                    self.feedback_buffer.append(sample)
            except Exception as e:
                logger.warning(f"Failed to load feedback {file_path}: {e}")

        logger.info(f"📂 Loaded {len(self.feedback_buffer)} feedback samples")

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics"""
        return {
            **self.stats,
            "buffer_size": len(self.feedback_buffer),
            "reward_model_samples": len(self.reward_model.training_samples),
            "training_history": self.reward_model.training_history[-5:],
        }


__all__ = [
    "FeedbackSample",
    "PreferenceType",
    "QualityScore",
    "RLHFModule",
    "RewardModel",
]
