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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    reasoning: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackSample":
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
    """

    def __init__(self):
        self.feature_weights: Dict[str, float] = {
            "length_ratio": 0.0,
            "keyword_overlap": 0.0,
            "sentiment_score": 0.0,
        }
        self.training_samples: List[FeedbackSample] = []
        self.training_history: List[Dict[str, float]] = []

    def extract_features(self, prompt: str, response: str) -> Dict[str, float]:
        """Extract features from a response"""
        features = {}

        # Length features
        prompt_words = len(prompt.split())
        response_words = len(response.split())
        features["length_ratio"] = min(response_words / max(prompt_words, 1), 5.0) / 5.0

        # Keyword overlap
        prompt_keywords = set(word.lower() for word in prompt.split() if len(word) > 3)
        response_keywords = set(
            word.lower() for word in response.split() if len(word) > 3
        )
        if prompt_keywords:
            features["keyword_overlap"] = len(
                prompt_keywords & response_keywords
            ) / len(prompt_keywords)
        else:
            features["keyword_overlap"] = 0.0

        # Simple sentiment (presence of positive/negative words)
        positive_words = {"good", "great", "excellent", "helpful", "clear", "correct"}
        negative_words = {"error", "wrong", "bad", "unclear", "incorrect", "fail"}

        response_lower = response.lower()
        pos_count = sum(1 for w in positive_words if w in response_lower)
        neg_count = sum(1 for w in negative_words if w in response_lower)
        features["sentiment_score"] = (pos_count - neg_count + 5) / 10.0

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

    def train(
        self, samples: List[FeedbackSample], epochs: int = 10, lr: float = 0.1
    ) -> Dict[str, float]:
        """Train reward model on feedback samples"""
        self.training_samples.extend(samples)

        total_loss = 0.0
        correct = 0

        for epoch in range(epochs):
            for sample in samples:
                # Extract features for both responses
                features_a = self.extract_features(sample.prompt, sample.response_a)
                features_b = self.extract_features(sample.prompt, sample.response_b)

                # Compute rewards
                reward_a = sum(
                    self.feature_weights.get(k, 0) * v for k, v in features_a.items()
                )
                reward_b = sum(
                    self.feature_weights.get(k, 0) * v for k, v in features_b.items()
                )

                # Predicted preference (sigmoid of difference)
                import math

                diff = reward_b - reward_a
                pred_prob = 1 / (1 + math.exp(-diff))

                # Convert sample.preference to probability
                if sample.preference == 1:
                    target = 1.0
                elif sample.preference == -1:
                    target = 0.0
                else:
                    target = 0.5

                # Binary cross entropy loss
                eps = 1e-10
                loss = -(
                    target * math.log(pred_prob + eps)
                    + (1 - target) * math.log(1 - pred_prob + eps)
                )
                total_loss += loss

                # Gradient update
                error = (pred_prob - target) * sample.confidence
                for feature_name in self.feature_weights:
                    grad = error * (
                        features_b.get(feature_name, 0)
                        - features_a.get(feature_name, 0)
                    )
                    self.feature_weights[feature_name] -= lr * grad

                # Track accuracy
                pred = 1 if reward_b > reward_a else (-1 if reward_a > reward_b else 0)
                if pred == sample.preference:
                    correct += 1

        accuracy = correct / max(len(samples) * epochs, 1)
        avg_loss = total_loss / max(len(samples) * epochs, 1)

        result = {
            "loss": avg_loss,
            "accuracy": accuracy,
            "samples": len(samples),
            "weights": dict(self.feature_weights),
        }
        self.training_history.append(result)

        logger.info(
            f"🎓 Reward model trained: accuracy={accuracy:.2%}, loss={avg_loss:.4f}"
        )
        return result


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
        persist_path: Optional[str] = None,
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

        self.feedback_buffer: List[FeedbackSample] = []
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
        reasoning: Optional[str] = None,
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
        responses: List[str],
        evaluator_fn: Optional[Any] = None,
    ) -> List[FeedbackSample]:
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
                        preference, confidence, reasoning = await evaluator_fn(
                            prompt, response_a, response_b
                        )
                    except Exception as e:
                        logger.error(f"AI evaluation failed: {e}")
                        continue
                else:
                    # Default: use simple heuristics
                    preference, confidence, reasoning = self._heuristic_evaluation(
                        prompt, response_a, response_b
                    )

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
        criteria: Optional[List[str]] = None,
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

    def train_reward_model(self, force: bool = False) -> Optional[Dict[str, float]]:
        """
        Train reward model on collected feedback

        Args:
            force: Train even if below minimum samples

        Returns:
            Training metrics or None if not enough samples
        """
        if len(self.feedback_buffer) < self.min_samples_for_training and not force:
            logger.info(
                f"⏳ Need {self.min_samples_for_training - len(self.feedback_buffer)} "
                f"more samples to train"
            )
            return None

        result = self.reward_model.train(self.feedback_buffer)
        self.stats["training_runs"] += 1

        return result

    def predict_preference(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
    ) -> Tuple[int, float]:
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
    ) -> Tuple[int, float, str]:
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
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sample = FeedbackSample.from_dict(data)
                    self.feedback_buffer.append(sample)
            except Exception as e:
                logger.warning(f"Failed to load feedback {file_path}: {e}")

        logger.info(f"📂 Loaded {len(self.feedback_buffer)} feedback samples")

    def get_stats(self) -> Dict[str, Any]:
        """Get module statistics"""
        return {
            **self.stats,
            "buffer_size": len(self.feedback_buffer),
            "reward_model_samples": len(self.reward_model.training_samples),
            "training_history": self.reward_model.training_history[-5:],
        }


__all__ = [
    "RLHFModule",
    "FeedbackSample",
    "PreferenceType",
    "QualityScore",
    "RewardModel",
]
