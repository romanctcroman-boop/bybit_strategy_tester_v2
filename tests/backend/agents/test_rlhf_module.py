"""
Tests for RLHF (Reinforcement Learning from Human/AI Feedback) Module.

Covers:
- FeedbackSample dataclass serialization/deserialization
- QualityScore weighted scoring
- RewardModel: feature extraction, training, prediction, cross-validation
- RLHFModule: human/AI/self feedback collection, reward training, preference prediction
- Persistence (save/load feedback to disk)
- Auto-training trigger on buffer threshold
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.self_improvement.rlhf_module import (
    FeedbackSample,
    PreferenceType,
    QualityScore,
    RewardModel,
    RLHFModule,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def reward_model():
    """Fresh RewardModel instance"""
    return RewardModel(learning_rate=0.1, patience=3)


@pytest.fixture
def rlhf_module():
    """RLHFModule without persistence"""
    return RLHFModule(min_samples_for_training=5)


@pytest.fixture
def persistent_rlhf(tmp_path):
    """RLHFModule with disk persistence"""
    return RLHFModule(
        persist_path=str(tmp_path / "feedback"),
        min_samples_for_training=5,
    )


@pytest.fixture
def sample_feedback():
    """Pre-built FeedbackSample"""
    return FeedbackSample(
        id="test_001",
        prompt="Explain RSI indicator for trading",
        response_a="RSI measures momentum by comparing average gains to average losses over a period.",
        response_b="RSI is a number between 0 and 100.",
        preference=-1,  # A is better
        preference_type=PreferenceType.HUMAN,
        confidence=1.0,
        reasoning="Response A is more detailed and accurate.",
    )


@pytest.fixture
def feedback_samples():
    """Multiple feedback samples for training"""
    return [
        FeedbackSample(
            id=f"train_{i}",
            prompt=f"Question {i} about trading strategies",
            response_a=f"Detailed response {i} with specific examples and analysis of the strategy including backtesting results.",
            response_b=f"Short response {i}.",
            preference=-1,  # A is better (longer, more detailed)
            preference_type=PreferenceType.AI,
            confidence=0.8,
        )
        for i in range(15)
    ]


# ═══════════════════════════════════════════════════════════════════
# FeedbackSample
# ═══════════════════════════════════════════════════════════════════


class TestFeedbackSample:
    """Tests for FeedbackSample dataclass"""

    def test_creation(self, sample_feedback):
        """Test creating FeedbackSample with all fields"""
        s = sample_feedback
        assert s.id == "test_001"
        assert s.preference == -1
        assert s.preference_type == PreferenceType.HUMAN
        assert s.confidence == 1.0
        assert "RSI" in s.prompt

    def test_to_dict(self, sample_feedback):
        """Test serialization to dict"""
        d = sample_feedback.to_dict()

        assert d["id"] == "test_001"
        assert d["preference"] == -1
        assert d["preference_type"] == "human"
        assert d["confidence"] == 1.0
        assert d["reasoning"] == "Response A is more detailed and accurate."
        assert "created_at" in d

    def test_from_dict_roundtrip(self, sample_feedback):
        """Test dict → FeedbackSample roundtrip"""
        d = sample_feedback.to_dict()
        restored = FeedbackSample.from_dict(d)

        assert restored.id == sample_feedback.id
        assert restored.prompt == sample_feedback.prompt
        assert restored.preference == sample_feedback.preference
        assert restored.preference_type == sample_feedback.preference_type
        assert restored.confidence == sample_feedback.confidence

    def test_default_metadata(self):
        """Test that metadata defaults to empty dict"""
        s = FeedbackSample(
            id="x",
            prompt="p",
            response_a="a",
            response_b="b",
            preference=0,
            preference_type=PreferenceType.SELF,
            confidence=0.5,
        )
        assert s.metadata == {}
        assert s.reasoning is None


# ═══════════════════════════════════════════════════════════════════
# PreferenceType enum
# ═══════════════════════════════════════════════════════════════════


class TestPreferenceType:
    """Tests for PreferenceType enum"""

    def test_all_types(self):
        """Test all preference types exist"""
        assert PreferenceType.HUMAN.value == "human"
        assert PreferenceType.AI.value == "ai"
        assert PreferenceType.SELF.value == "self"
        assert PreferenceType.CONSENSUS.value == "consensus"

    def test_enum_count(self):
        """Test 4 preference types"""
        assert len(PreferenceType) == 4


# ═══════════════════════════════════════════════════════════════════
# QualityScore
# ═══════════════════════════════════════════════════════════════════


class TestQualityScore:
    """Tests for QualityScore dataclass"""

    def test_default_scores(self):
        """Test that all scores default to 0"""
        q = QualityScore()
        assert q.helpfulness == 0.0
        assert q.accuracy == 0.0
        assert q.relevance == 0.0
        assert q.safety == 0.0
        assert q.clarity == 0.0
        assert q.creativity == 0.0

    def test_overall_weighted_score(self):
        """Test that overall is a weighted average"""
        q = QualityScore(
            helpfulness=1.0,
            accuracy=1.0,
            relevance=1.0,
            safety=1.0,
            clarity=1.0,
            creativity=1.0,
        )
        assert abs(q.overall - 1.0) < 0.001

    def test_overall_partial_scores(self):
        """Test overall with mixed scores"""
        q = QualityScore(
            helpfulness=0.8,
            accuracy=0.6,
            relevance=0.7,
            safety=1.0,
            clarity=0.5,
            creativity=0.3,
        )
        # Weights: help=0.25, acc=0.25, rel=0.20, safe=0.15, clar=0.10, cre=0.05
        expected = 0.8 * 0.25 + 0.6 * 0.25 + 0.7 * 0.20 + 1.0 * 0.15 + 0.5 * 0.10 + 0.3 * 0.05
        assert abs(q.overall - expected) < 0.001

    def test_overall_zero_scores(self):
        """Test overall with all zero scores"""
        q = QualityScore()
        assert q.overall == 0.0


# ═══════════════════════════════════════════════════════════════════
# RewardModel — Feature Extraction
# ═══════════════════════════════════════════════════════════════════


class TestRewardModelFeatures:
    """Tests for RewardModel feature extraction"""

    def test_extract_features_returns_all_keys(self, reward_model):
        """Test that all feature keys are present"""
        features = reward_model.extract_features("test prompt", "test response")

        expected_keys = {
            "length_ratio",
            "keyword_overlap",
            "sentiment_score",
            "structure_score",
            "specificity_score",
        }
        assert set(features.keys()) == expected_keys

    def test_length_ratio_normalized(self, reward_model):
        """Test length_ratio is between 0 and 1"""
        features = reward_model.extract_features(
            "short",
            "a much longer response with many words to test ratio",
        )
        assert 0.0 <= features["length_ratio"] <= 1.0

    def test_keyword_overlap_high(self, reward_model):
        """Test high keyword overlap when response contains prompt words"""
        features = reward_model.extract_features(
            "trading strategy backtest results",
            "The trading strategy shows good backtest results with high returns.",
        )
        assert features["keyword_overlap"] > 0.3

    def test_keyword_overlap_low(self, reward_model):
        """Test low overlap when response is unrelated"""
        features = reward_model.extract_features(
            "quantum physics experiments",
            "The cat sat on the mat.",
        )
        assert features["keyword_overlap"] < 0.3

    def test_sentiment_score_positive(self, reward_model):
        """Test positive sentiment detection"""
        features = reward_model.extract_features(
            "How is this?",
            "This is an excellent and great solution with clear and accurate results.",
        )
        assert features["sentiment_score"] > 0.5

    def test_structure_score_good_sentences(self, reward_model):
        """Test structure score with well-formed sentences"""
        features = reward_model.extract_features(
            "Explain RSI.",
            "RSI measures the magnitude of recent price changes. "
            "It oscillates between zero and one hundred. "
            "Values below thirty indicate oversold conditions.",
        )
        assert features["structure_score"] >= 0.4

    def test_specificity_score(self, reward_model):
        """Test specificity score with specific language"""
        features = reward_model.extract_features(
            "What is RSI?",
            "Specifically, RSI uses a 14-period lookback. For example, 70% indicates overbought.",
        )
        assert features["specificity_score"] > 0.3

    def test_empty_prompt_handling(self, reward_model):
        """Test feature extraction with empty prompt"""
        features = reward_model.extract_features("", "Some response text here.")
        assert features["keyword_overlap"] == 0.0
        assert features["length_ratio"] >= 0.0


# ═══════════════════════════════════════════════════════════════════
# RewardModel — Training
# ═══════════════════════════════════════════════════════════════════


class TestRewardModelTraining:
    """Tests for RewardModel training"""

    def test_train_returns_metrics(self, reward_model, feedback_samples):
        """Test that training returns metrics dict"""
        result = reward_model.train(feedback_samples[:5], epochs=3)

        assert "loss" in result
        assert "accuracy" in result
        assert "samples" in result
        assert "weights" in result
        assert result["samples"] == 5

    def test_train_updates_weights(self, reward_model, feedback_samples):
        """Test that training updates feature weights"""
        initial_weights = dict(reward_model.feature_weights)

        reward_model.train(feedback_samples[:5], epochs=5)

        # At least some weights should have changed
        changed = sum(1 for k in initial_weights if abs(reward_model.feature_weights[k] - initial_weights[k]) > 1e-10)
        assert changed > 0

    def test_train_records_history(self, reward_model, feedback_samples):
        """Test that training records history"""
        reward_model.train(feedback_samples[:5], epochs=3)

        assert len(reward_model.training_history) == 1
        assert "loss" in reward_model.training_history[0]

    def test_train_with_early_stopping(self, reward_model, feedback_samples):
        """Test early stopping functionality"""
        result = reward_model.train(
            feedback_samples[:10],
            epochs=100,
            use_early_stopping=True,
        )

        # Should stop before 100 epochs if validation loss stops improving
        assert "early_stopped" in result
        assert "epochs_run" in result

    def test_train_without_early_stopping(self, reward_model, feedback_samples):
        """Test training with early stopping disabled"""
        result = reward_model.train(
            feedback_samples[:5],
            epochs=5,
            use_early_stopping=False,
        )

        assert result["epochs_run"] == 5
        assert result["early_stopped"] is False

    def test_predict_reward_in_range(self, reward_model):
        """Test that predict_reward returns value in [0, 1]"""
        score = reward_model.predict_reward("test prompt", "test response")
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════
# RewardModel — Cross-Validation
# ═══════════════════════════════════════════════════════════════════


class TestRewardModelCrossValidation:
    """Tests for RewardModel cross-validation"""

    def test_cross_validate_returns_metrics(self, reward_model, feedback_samples):
        """Test cross-validation returns average metrics"""
        result = reward_model.cross_validate(
            feedback_samples[:10],
            k_folds=3,
            epochs=3,
        )

        assert "avg_train_loss" in result
        assert "avg_train_accuracy" in result
        assert "avg_val_loss" in result
        assert result["k_folds"] == 3

    def test_cross_validate_few_samples(self, reward_model):
        """Test cross-validation with fewer samples than folds"""
        samples = [
            FeedbackSample(
                id=f"cv_{i}",
                prompt="test",
                response_a="a",
                response_b="b",
                preference=1,
                preference_type=PreferenceType.AI,
                confidence=0.5,
            )
            for i in range(3)
        ]

        result = reward_model.cross_validate(samples, k_folds=5, epochs=2)
        # k_folds should be reduced to len(samples)
        assert result["k_folds"] == 3

    def test_cosine_lr_schedule(self, reward_model):
        """Test cosine annealing learning rate"""
        lr_start = reward_model._cosine_lr(0, 10, 0.1)
        lr_mid = reward_model._cosine_lr(5, 10, 0.1)
        lr_end = reward_model._cosine_lr(10, 10, 0.1)

        assert abs(lr_start - 0.1) < 0.001  # Full LR at start
        assert lr_mid < lr_start  # Decayed at midpoint
        assert abs(lr_end) < 0.001  # Near zero at end


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Human Feedback
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleHumanFeedback:
    """Tests for RLHFModule human feedback collection"""

    @pytest.mark.asyncio
    async def test_collect_human_feedback(self, rlhf_module):
        """Test collecting human feedback"""
        sample = await rlhf_module.collect_human_feedback(
            prompt="What is RSI?",
            response_a="RSI is a momentum indicator.",
            response_b="RSI is a number.",
            preference=-1,
            reasoning="A is more informative",
        )

        assert isinstance(sample, FeedbackSample)
        assert sample.preference_type == PreferenceType.HUMAN
        assert sample.confidence == 1.0
        assert sample.preference == -1
        assert rlhf_module.stats["human_feedback"] == 1

    @pytest.mark.asyncio
    async def test_human_feedback_adds_to_buffer(self, rlhf_module):
        """Test that human feedback is added to buffer"""
        assert len(rlhf_module.feedback_buffer) == 0

        await rlhf_module.collect_human_feedback(
            prompt="test",
            response_a="a",
            response_b="b",
            preference=1,
        )

        assert len(rlhf_module.feedback_buffer) == 1


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — AI Feedback
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleAIFeedback:
    """Tests for RLHFModule AI feedback (RLAIF)"""

    @pytest.mark.asyncio
    async def test_collect_ai_feedback_with_evaluator(self, rlhf_module):
        """Test AI feedback with custom evaluator function"""

        async def mock_evaluator(prompt, resp_a, resp_b):
            return (-1, 0.9, "A is better")

        samples = await rlhf_module.collect_ai_feedback(
            prompt="Explain MACD",
            responses=["Detailed MACD explanation with examples.", "MACD is an indicator."],
            evaluator_fn=mock_evaluator,
        )

        assert len(samples) == 1
        assert samples[0].preference == -1
        assert samples[0].confidence == 0.9
        assert rlhf_module.stats["ai_feedback"] == 1

    @pytest.mark.asyncio
    async def test_collect_ai_feedback_heuristic(self, rlhf_module):
        """Test AI feedback with default heuristic evaluation"""
        samples = await rlhf_module.collect_ai_feedback(
            prompt="What is Bollinger Bands?",
            responses=[
                "Bollinger Bands are a volatility indicator using standard deviations around a moving average.",
                "BB.",
            ],
        )

        assert len(samples) == 1
        assert samples[0].preference_type == PreferenceType.AI

    @pytest.mark.asyncio
    async def test_collect_ai_feedback_multiple_responses(self, rlhf_module):
        """Test AI feedback with 3 responses (3 pairs)"""
        samples = await rlhf_module.collect_ai_feedback(
            prompt="Explain SMA",
            responses=["Response A", "Response B", "Response C"],
        )

        # 3 responses → 3 pairwise comparisons (A-B, A-C, B-C)
        assert len(samples) == 3

    @pytest.mark.asyncio
    async def test_collect_ai_feedback_single_response(self, rlhf_module):
        """Test that single response returns empty list"""
        samples = await rlhf_module.collect_ai_feedback(
            prompt="test",
            responses=["Only one response"],
        )
        assert samples == []

    @pytest.mark.asyncio
    async def test_collect_ai_feedback_evaluator_error(self, rlhf_module):
        """Test graceful handling of evaluator errors"""

        async def failing_evaluator(prompt, resp_a, resp_b):
            raise RuntimeError("Evaluator crashed")

        samples = await rlhf_module.collect_ai_feedback(
            prompt="test",
            responses=["a", "b"],
            evaluator_fn=failing_evaluator,
        )
        assert len(samples) == 0  # Error → no samples collected


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Self Evaluation
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleSelfEvaluation:
    """Tests for RLHFModule self-evaluation"""

    @pytest.mark.asyncio
    async def test_self_evaluate_returns_quality_score(self, rlhf_module):
        """Test self-evaluation returns QualityScore"""
        score = await rlhf_module.self_evaluate(
            prompt="Explain RSI calculation",
            response="RSI is calculated by dividing the average gain by the average loss over 14 periods.",
        )

        assert isinstance(score, QualityScore)
        assert 0.0 <= score.overall <= 1.0

    @pytest.mark.asyncio
    async def test_self_evaluate_high_quality_response(self, rlhf_module):
        """Test self-evaluation of a high-quality response"""
        score = await rlhf_module.self_evaluate(
            prompt="How to calculate RSI",
            response=(
                "RSI is calculated as follows. First, compute the average gain and average loss "
                "over the lookback period. Then, divide gain by loss to get RS. "
                "Finally, RSI = 100 - 100/(1+RS). Good values are above 50. Clear and helpful."
            ),
        )

        assert score.helpfulness > 0.3
        assert score.clarity > 0.3

    @pytest.mark.asyncio
    async def test_self_evaluate_unsafe_response(self, rlhf_module):
        """Test self-evaluation flags unsafe content"""
        score = await rlhf_module.self_evaluate(
            prompt="How to query database",
            response="Just run eval('DROP TABLE users') to delete everything.",
        )

        assert score.safety < 0.5  # Should flag unsafe patterns

    @pytest.mark.asyncio
    async def test_self_evaluate_uncertain_response(self, rlhf_module):
        """Test self-evaluation flags uncertainty"""
        score = await rlhf_module.self_evaluate(
            prompt="What is MACD?",
            response="Maybe MACD is possibly some kind of indicator, perhaps it could be useful.",
        )

        assert score.accuracy < 1.0


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Reward Training
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleRewardTraining:
    """Tests for reward model training through RLHFModule"""

    @pytest.mark.asyncio
    async def test_train_reward_model_sufficient_samples(self, rlhf_module, feedback_samples):
        """Test training with sufficient samples"""
        for s in feedback_samples[:6]:
            rlhf_module._add_feedback(s)

        result = rlhf_module.train_reward_model()
        assert result is not None
        assert "loss" in result
        assert rlhf_module.stats["training_runs"] == 1

    @pytest.mark.asyncio
    async def test_train_reward_model_insufficient_samples(self, rlhf_module, feedback_samples):
        """Test training with insufficient samples returns None"""
        for s in feedback_samples[:2]:  # Only 2, need 5
            rlhf_module._add_feedback(s)

        result = rlhf_module.train_reward_model()
        assert result is None

    @pytest.mark.asyncio
    async def test_train_reward_model_force(self, rlhf_module, feedback_samples):
        """Test force training with insufficient samples"""
        for s in feedback_samples[:2]:
            rlhf_module._add_feedback(s)

        result = rlhf_module.train_reward_model(force=True)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Preference Prediction
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModulePreference:
    """Tests for preference prediction"""

    def test_predict_preference_returns_tuple(self, rlhf_module):
        """Test predict_preference returns (preference, confidence)"""
        preference, confidence = rlhf_module.predict_preference(
            prompt="What is RSI?",
            response_a="RSI measures momentum.",
            response_b="RSI is a number.",
        )

        assert preference in (-1, 0, 1)
        assert 0.0 <= confidence <= 1.0

    def test_predict_preference_tie(self, rlhf_module):
        """Test preference prediction for similar responses"""
        preference, _confidence = rlhf_module.predict_preference(
            prompt="test",
            response_a="test response",
            response_b="test response",  # Identical
        )

        assert preference == 0  # Should be a tie


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Heuristic Evaluation
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleHeuristic:
    """Tests for heuristic evaluation"""

    def test_heuristic_returns_tuple(self, rlhf_module):
        """Test heuristic evaluation returns (preference, confidence, reasoning)"""
        pref, conf, reason = rlhf_module._heuristic_evaluation(
            prompt="Explain trading",
            response_a="Trading is the act of buying and selling financial instruments for profit.",
            response_b="Trade.",
        )

        assert pref in (-1, 0, 1)
        assert 0.0 <= conf <= 1.0
        assert len(reason) > 0

    def test_heuristic_prefers_relevant_response(self, rlhf_module):
        """Test that heuristic prefers response with better keyword overlap"""
        pref, _conf, _reason = rlhf_module._heuristic_evaluation(
            prompt="What is the RSI trading indicator used for momentum analysis",
            response_a="The RSI is a momentum indicator used in trading for momentum analysis and overbought/oversold detection.",
            response_b="Cats and dogs are common pets.",
        )

        # A should be preferred (better keyword overlap)
        assert pref == -1


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Persistence
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModulePersistence:
    """Tests for feedback persistence"""

    @pytest.mark.asyncio
    async def test_persist_and_load_feedback(self, tmp_path):
        """Test that feedback is persisted and reloaded"""
        persist_dir = str(tmp_path / "feedback")

        # Create module and add feedback
        mod1 = RLHFModule(persist_path=persist_dir, min_samples_for_training=100)
        await mod1.collect_human_feedback(
            prompt="test",
            response_a="a",
            response_b="b",
            preference=1,
        )
        assert len(mod1.feedback_buffer) == 1

        # Create new module from same path
        mod2 = RLHFModule(persist_path=persist_dir, min_samples_for_training=100)

        # Should have loaded the persisted feedback
        assert len(mod2.feedback_buffer) == 1
        assert mod2.feedback_buffer[0].preference == 1

    @pytest.mark.asyncio
    async def test_persist_multiple_samples(self, tmp_path):
        """Test persisting multiple feedback samples"""
        persist_dir = str(tmp_path / "feedback")
        mod = RLHFModule(persist_path=persist_dir, min_samples_for_training=100)

        for i in range(5):
            await mod.collect_human_feedback(
                prompt=f"Q{i}",
                response_a=f"A{i}",
                response_b=f"B{i}",
                preference=1 if i % 2 == 0 else -1,
            )

        # Verify files on disk
        feedback_path = Path(persist_dir)
        json_files = list(feedback_path.glob("*.json"))
        assert len(json_files) == 5


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Auto-Training
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleAutoTraining:
    """Tests for auto-training trigger"""

    @pytest.mark.asyncio
    async def test_auto_train_on_threshold(self, feedback_samples):
        """Test that auto-training triggers when buffer reaches 2x threshold"""
        mod = RLHFModule(min_samples_for_training=5)

        # Add 10 samples (2x threshold of 5)
        for s in feedback_samples[:10]:
            mod._add_feedback(s)

        # Auto-training should have triggered
        assert mod.stats["training_runs"] >= 1


# ═══════════════════════════════════════════════════════════════════
# RLHFModule — Statistics
# ═══════════════════════════════════════════════════════════════════


class TestRLHFModuleStats:
    """Tests for RLHFModule statistics"""

    @pytest.mark.asyncio
    async def test_initial_stats(self, rlhf_module):
        """Test initial statistics"""
        stats = rlhf_module.get_stats()

        assert stats["total_feedback"] == 0
        assert stats["human_feedback"] == 0
        assert stats["ai_feedback"] == 0
        assert stats["self_feedback"] == 0
        assert stats["training_runs"] == 0
        assert stats["buffer_size"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_feedback(self, rlhf_module):
        """Test statistics after collecting feedback"""
        await rlhf_module.collect_human_feedback(prompt="test", response_a="a", response_b="b", preference=1)

        stats = rlhf_module.get_stats()
        assert stats["total_feedback"] == 1
        assert stats["human_feedback"] == 1
        assert stats["buffer_size"] == 1

    @pytest.mark.asyncio
    async def test_stats_training_history(self, rlhf_module, feedback_samples):
        """Test that training history is included in stats"""
        for s in feedback_samples[:6]:
            rlhf_module._add_feedback(s)

        rlhf_module.train_reward_model()

        stats = rlhf_module.get_stats()
        assert stats["training_runs"] == 1
        assert "training_history" in stats
