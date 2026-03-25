"""
Tests for Online Learning Module

Covers:
- IncrementalModel: partial_fit, predict, predict_proba
- OnlineLearner: update strategies, buffer management, drift detection
- LearningStats tracking
- AdaptiveLearningRateScheduler: step, on_drift, reset
- Reset, retrain_on_window, boost_learning_rate
- Record outcome and accuracy tracking
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.linear_model import SGDClassifier
from sklearn.tree import DecisionTreeClassifier

from backend.ml.enhanced.online_learner import (
    AdaptiveLearningRateScheduler,
    IncrementalModel,
    LearningStats,
    OnlineLearner,
    UpdateStrategy,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sgd_model():
    """SGDClassifier that supports partial_fit."""
    return SGDClassifier(loss="log_loss", random_state=42)


@pytest.fixture
def tree_model():
    """DecisionTree that does NOT support partial_fit."""
    return DecisionTreeClassifier(random_state=42)


@pytest.fixture
def binary_data():
    """Simple binary classification dataset."""
    np.random.seed(42)
    n = 200
    X = np.random.randn(n, 4)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    return X, y


@pytest.fixture
def batch_data():
    """Multiple batches of data for streaming updates."""
    np.random.seed(42)
    batches = []
    for _ in range(5):
        n = 50
        X = np.random.randn(n, 4)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        batches.append((X, y))
    return batches


@pytest.fixture
def learner(sgd_model):
    """OnlineLearner with SGD in batch mode."""
    return OnlineLearner(
        model=sgd_model,
        update_strategy=UpdateStrategy.BATCH,
        batch_size=50,
        window_size=500,
        learning_rate=0.01,
        classes=np.array([0, 1]),
    )


@pytest.fixture
def streaming_learner(sgd_model):
    """OnlineLearner in streaming mode."""
    return OnlineLearner(
        model=sgd_model,
        update_strategy=UpdateStrategy.STREAMING,
        batch_size=1,
        classes=np.array([0, 1]),
    )


@pytest.fixture
def adaptive_learner(sgd_model):
    """OnlineLearner in adaptive mode."""
    return OnlineLearner(
        model=sgd_model,
        update_strategy=UpdateStrategy.ADAPTIVE,
        batch_size=50,
        accuracy_threshold=0.6,
        drift_threshold=0.1,
        classes=np.array([0, 1]),
    )


# ═══════════════════════════════════════════════════════════════════
# UpdateStrategy Enum Tests
# ═══════════════════════════════════════════════════════════════════


class TestUpdateStrategy:
    """Tests for UpdateStrategy enum."""

    def test_values(self):
        """Test all strategies exist."""
        assert UpdateStrategy.BATCH.value == "batch"
        assert UpdateStrategy.STREAMING.value == "streaming"
        assert UpdateStrategy.SCHEDULED.value == "scheduled"
        assert UpdateStrategy.ADAPTIVE.value == "adaptive"
        assert UpdateStrategy.HYBRID.value == "hybrid"


# ═══════════════════════════════════════════════════════════════════
# LearningStats Tests
# ═══════════════════════════════════════════════════════════════════


class TestLearningStats:
    """Tests for LearningStats dataclass."""

    def test_defaults(self):
        """Test default values."""
        stats = LearningStats()
        assert stats.total_samples == 0
        assert stats.update_count == 0
        assert stats.last_update is None
        assert stats.learning_rate == 0.01

    def test_to_dict(self):
        """Test serialization."""
        stats = LearningStats(
            total_samples=100,
            update_count=5,
            cumulative_accuracy=0.85,
            recent_accuracy=0.90,
            learning_rate=0.005,
        )
        d = stats.to_dict()
        assert d["total_samples"] == 100
        assert d["update_count"] == 5
        assert d["cumulative_accuracy"] == 0.85
        assert d["learning_rate"] == 0.005


# ═══════════════════════════════════════════════════════════════════
# IncrementalModel Tests
# ═══════════════════════════════════════════════════════════════════


class TestIncrementalModel:
    """Tests for IncrementalModel wrapper."""

    def test_wrap_partial_fit_model(self, sgd_model):
        """Test wrapping a model that supports partial_fit."""
        wrapped = IncrementalModel(
            model=sgd_model,
            model_type="SGDClassifier",
            supports_partial_fit=True,
            classes=np.array([0, 1]),
        )
        assert wrapped.supports_partial_fit is True
        assert wrapped.is_fitted is False
        assert wrapped.sample_count == 0

    def test_partial_fit(self, sgd_model, binary_data):
        """Test incremental fitting."""
        X, y = binary_data
        wrapped = IncrementalModel(
            model=sgd_model,
            model_type="SGDClassifier",
            supports_partial_fit=True,
            classes=np.array([0, 1]),
        )
        wrapped.partial_fit(X[:50], y[:50])
        assert wrapped.is_fitted is True
        assert wrapped.sample_count == 50

    def test_predict_before_fit_raises(self, sgd_model):
        """Test that predict before fit raises."""
        wrapped = IncrementalModel(
            model=sgd_model,
            model_type="SGDClassifier",
            supports_partial_fit=True,
        )
        with pytest.raises(ValueError, match="not fitted"):
            wrapped.predict(np.array([[1, 2, 3, 4]]))

    def test_predict_after_fit(self, sgd_model, binary_data):
        """Test predictions after fitting."""
        X, y = binary_data
        wrapped = IncrementalModel(
            model=sgd_model,
            model_type="SGDClassifier",
            supports_partial_fit=True,
            classes=np.array([0, 1]),
        )
        wrapped.partial_fit(X, y)
        preds = wrapped.predict(X[:10])
        assert len(preds) == 10
        assert set(preds).issubset({0, 1})

    def test_predict_proba_before_fit_raises(self, sgd_model):
        """Test that predict_proba before fit raises."""
        wrapped = IncrementalModel(
            model=sgd_model,
            model_type="SGDClassifier",
            supports_partial_fit=True,
        )
        with pytest.raises(ValueError, match="not fitted"):
            wrapped.predict_proba(np.array([[1, 2, 3, 4]]))

    def test_non_partial_fit_model(self, tree_model, binary_data):
        """Test wrapping a model without partial_fit (uses warm_start)."""
        X, y = binary_data
        wrapped = IncrementalModel(
            model=tree_model,
            model_type="DecisionTreeClassifier",
            supports_partial_fit=False,
        )
        # Should fall back to fit()
        wrapped.partial_fit(X, y)
        assert wrapped.is_fitted is True


# ═══════════════════════════════════════════════════════════════════
# OnlineLearner Tests
# ═══════════════════════════════════════════════════════════════════


class TestOnlineLearner:
    """Tests for OnlineLearner class."""

    def test_init(self, learner):
        """Test initialization."""
        assert learner.update_strategy == UpdateStrategy.BATCH
        assert learner.batch_size == 50
        assert learner.stats.total_samples == 0
        assert learner.incremental_model.supports_partial_fit is True

    def test_wrap_model(self, sgd_model):
        """Test model wrapping."""
        learner = OnlineLearner(model=sgd_model, classes=np.array([0, 1]))
        assert learner.incremental_model.model_type == "SGDClassifier"
        assert learner.incremental_model.supports_partial_fit is True

    def test_update_batch_mode(self, learner, binary_data):
        """Test batch update triggers at batch_size."""
        X, y = binary_data
        # Send 30 samples (below batch_size=50)
        result = learner.update(X[:30], y[:30])
        assert result["updated"] is False
        assert result["samples_buffered"] == 30

        # Send 30 more (total 60 > batch_size)
        result = learner.update(X[30:60], y[30:60])
        assert result["updated"] is True

    def test_update_streaming_mode(self, streaming_learner, binary_data):
        """Test streaming mode updates on every call."""
        X, y = binary_data
        result = streaming_learner.update(X[:5], y[:5])
        assert result["updated"] is True
        assert streaming_learner.stats.update_count == 1

    def test_update_force(self, learner, binary_data):
        """Test force update ignores batch size."""
        X, y = binary_data
        result = learner.update(X[:5], y[:5], force=True)
        assert result["updated"] is True

    def test_update_increments_stats(self, learner, batch_data):
        """Test that stats are updated after each update."""
        X, y = batch_data[0]
        learner.update(X, y)  # Should trigger (batch_size=50)
        assert learner.stats.total_samples == 50
        assert learner.stats.update_count == 1
        assert learner.stats.last_update is not None

    def test_learning_rate_decay(self, learner, batch_data):
        """Test learning rate decays after update."""
        initial_lr = learner.stats.learning_rate
        X, y = batch_data[0]
        learner.update(X, y)
        assert learner.stats.learning_rate < initial_lr
        assert learner.stats.learning_rate >= learner.min_learning_rate

    def test_predict_after_update(self, learner, binary_data):
        """Test predictions after model update."""
        X, y = binary_data
        learner.update(X[:100], y[:100], force=True)
        preds = learner.predict(X[100:110])
        assert len(preds) == 10

    def test_predict_before_update_raises(self, learner, binary_data):
        """Test predict before any update raises."""
        X, _ = binary_data
        with pytest.raises(ValueError, match="not fitted"):
            learner.predict(X[:5])

    def test_record_outcome(self, learner, binary_data):
        """Test recording prediction outcomes."""
        X, y = binary_data
        learner.update(X[:100], y[:100], force=True)
        preds = learner.predict(X[100:150])
        metrics = learner.record_outcome(preds, y[100:150])

        assert "batch_accuracy" in metrics
        assert "cumulative_accuracy" in metrics
        assert "recent_accuracy" in metrics
        assert 0.0 <= metrics["batch_accuracy"] <= 1.0

    def test_reset(self, learner, binary_data):
        """Test reset clears state."""
        X, y = binary_data
        learner.update(X[:100], y[:100], force=True)
        assert learner.stats.total_samples == 100

        learner.reset(keep_stats=False)
        assert learner.incremental_model.is_fitted is False
        assert learner.stats.total_samples == 0
        assert len(learner.X_buffer) == 0

    def test_reset_keep_stats(self, learner, binary_data):
        """Test reset keeping stats."""
        X, y = binary_data
        learner.update(X[:100], y[:100], force=True)
        learner.reset(keep_stats=True)
        # Stats preserved
        assert learner.stats.total_samples == 100
        # But model is reset
        assert learner.incremental_model.is_fitted is False

    def test_retrain_on_window_empty(self, learner):
        """Test retrain with no window data."""
        result = learner.retrain_on_window()
        assert result["status"] == "no_data"

    def test_retrain_on_window(self, learner, binary_data):
        """Test retrain on rolling window."""
        X, y = binary_data
        learner.update(X[:100], y[:100], force=True)
        result = learner.retrain_on_window()
        assert result["status"] == "retrained"
        assert result["samples"] >= 100

    def test_boost_learning_rate(self, learner, batch_data):
        """Test learning rate boosting."""
        X, y = batch_data[0]
        learner.update(X, y)
        decayed_lr = learner.stats.learning_rate

        learner.boost_learning_rate(factor=2.0)
        assert learner.stats.learning_rate > decayed_lr

    def test_get_stats(self, learner):
        """Test get_stats returns dict."""
        stats = learner.get_stats()
        assert isinstance(stats, dict)
        assert "total_samples" in stats
        assert "update_count" in stats

    def test_set_drift_detector(self, learner):
        """Test setting external drift detector."""
        assert learner.drift_detector is None
        learner.set_drift_detector("mock_detector")
        assert learner.drift_detector == "mock_detector"

    def test_on_update_callback(self, learner, binary_data):
        """Test on_update callback fires."""
        X, y = binary_data
        callback_results = []
        learner.on_update = lambda r: callback_results.append(r)

        learner.update(X[:100], y[:100], force=True)
        assert len(callback_results) == 1
        assert callback_results[0]["updated"] is True

    def test_adaptive_weights(self, adaptive_learner, binary_data):
        """Test adaptive sample weight calculation."""
        X, y = binary_data
        weights = adaptive_learner._calculate_adaptive_weights(X[:50], y[:50])
        assert len(weights) == 50
        # More recent samples should have higher weight
        assert weights[-1] > weights[0]
        # Weights should approximately sum to n_samples
        assert abs(weights.sum() - 50) < 1.0

    def test_multiple_updates(self, learner, batch_data):
        """Test multiple sequential updates."""
        for X, y in batch_data:
            learner.update(X, y)

        assert learner.stats.total_samples == 250
        assert learner.stats.update_count == 5

    def test_should_update_hybrid(self, sgd_model, binary_data):
        """Test hybrid update strategy."""
        learner = OnlineLearner(
            model=sgd_model,
            update_strategy=UpdateStrategy.HYBRID,
            batch_size=50,
            classes=np.array([0, 1]),
        )
        X, _y = binary_data
        # Small batch — should not trigger
        assert learner._should_update(force=False) is False

        # Add enough data
        learner.X_buffer.append(X[:60])
        assert learner._should_update(force=False) is True


# ═══════════════════════════════════════════════════════════════════
# AdaptiveLearningRateScheduler Tests
# ═══════════════════════════════════════════════════════════════════


class TestAdaptiveLearningRateScheduler:
    """Tests for AdaptiveLearningRateScheduler."""

    def test_init(self):
        """Test default initialization."""
        scheduler = AdaptiveLearningRateScheduler()
        assert scheduler.current_lr == 0.01
        assert scheduler.best_accuracy == 0.0
        assert scheduler.wait == 0

    def test_step_improving(self):
        """Test step with improving accuracy."""
        scheduler = AdaptiveLearningRateScheduler(patience=5)
        lr = scheduler.step(0.5)
        assert lr == scheduler.initial_lr  # No reduction yet
        assert scheduler.best_accuracy == 0.5
        assert scheduler.wait == 0

    def test_step_no_improvement_reduces_lr(self):
        """Test LR reduction after patience exhausted."""
        scheduler = AdaptiveLearningRateScheduler(initial_lr=0.01, patience=3, factor=0.5)
        scheduler.step(0.8)
        scheduler.step(0.79)
        scheduler.step(0.78)
        lr = scheduler.step(0.77)  # 3 steps without improvement → reduce
        assert lr < 0.01
        assert lr == pytest.approx(0.005)

    def test_step_respects_min_lr(self):
        """Test that LR doesn't drop below min_lr."""
        scheduler = AdaptiveLearningRateScheduler(initial_lr=0.001, min_lr=0.0005, patience=1, factor=0.1)
        scheduler.step(0.9)
        scheduler.step(0.8)  # Triggers reduction
        assert scheduler.current_lr >= 0.0005

    def test_on_drift_increases_lr(self):
        """Test that on_drift increases learning rate."""
        scheduler = AdaptiveLearningRateScheduler(initial_lr=0.01, factor=0.5)
        # First reduce LR
        scheduler.current_lr = 0.002
        scheduler.best_accuracy = 0.9

        lr = scheduler.on_drift()
        assert lr > 0.002
        assert scheduler.best_accuracy == 0.0  # Reset
        assert scheduler.wait == 0

    def test_on_drift_respects_max_lr(self):
        """Test that on_drift doesn't exceed max_lr."""
        scheduler = AdaptiveLearningRateScheduler(initial_lr=0.01, max_lr=0.05, factor=0.5)
        scheduler.current_lr = 0.04
        lr = scheduler.on_drift()
        assert lr <= 0.05

    def test_reset(self):
        """Test resetting scheduler."""
        scheduler = AdaptiveLearningRateScheduler(initial_lr=0.01)
        scheduler.step(0.5)
        scheduler.step(0.6)
        scheduler.current_lr = 0.002

        scheduler.reset()
        assert scheduler.current_lr == 0.01
        assert scheduler.best_accuracy == 0.0
        assert scheduler.history == []

    def test_history_tracking(self):
        """Test accuracy history."""
        scheduler = AdaptiveLearningRateScheduler()
        scheduler.step(0.5)
        scheduler.step(0.6)
        scheduler.step(0.7)
        assert len(scheduler.history) == 3
        assert scheduler.history == [0.5, 0.6, 0.7]
