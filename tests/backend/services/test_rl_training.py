"""Tests for backend.services.rl_training — RL Training Pipeline."""

import json

import pytest

from backend.services.rl_training import (
    EvaluationResult,
    LocalExperimentTracker,
    RLTrainingPipeline,
    TrainingRun,
)

# ============================================================================
# TrainingRun
# ============================================================================


class TestTrainingRun:
    """Tests for TrainingRun dataclass."""

    def test_to_dict_roundtrip(self):
        """Test serialization produces JSON-safe dict."""
        run = TrainingRun(
            run_id="test_001",
            symbol="BTCUSDT",
            timeframe="15",
            episodes=50,
            config={"learning_rate": 1e-4},
            metrics={"mean_reward": 0.5},
            status="completed",
        )
        d = run.to_dict()
        assert d["run_id"] == "test_001"
        assert d["symbol"] == "BTCUSDT"
        assert d["metrics"]["mean_reward"] == 0.5
        # Ensure JSON serializable
        json.dumps(d)

    def test_duration_seconds_with_times(self):
        """Test duration calculation when both times present."""
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        run = TrainingRun(
            run_id="t",
            symbol="BTC",
            timeframe="15",
            episodes=1,
            config={},
            started_at=now,
            completed_at=now + timedelta(seconds=120),
        )
        assert run.duration_seconds() == pytest.approx(120.0)

    def test_duration_seconds_without_times(self):
        """Test duration returns 0 when times missing."""
        run = TrainingRun(run_id="t", symbol="BTC", timeframe="15", episodes=1, config={})
        assert run.duration_seconds() == 0.0


# ============================================================================
# EvaluationResult
# ============================================================================


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_to_dict_serializable(self):
        """Test evaluation result serializes to dict."""
        result = EvaluationResult(
            run_id="eval_001",
            eval_episodes=20,
            avg_reward=0.123456,
            total_return=0.15,
            sharpe_ratio=1.23,
            max_drawdown=0.05,
            win_rate=0.55,
            avg_trades_per_episode=12.5,
        )
        d = result.to_dict()
        assert d["run_id"] == "eval_001"
        assert d["avg_reward"] == 0.123456
        json.dumps(d)


# ============================================================================
# LocalExperimentTracker
# ============================================================================


class TestLocalExperimentTracker:
    """Tests for file-based experiment tracker."""

    def test_log_and_load_run(self, tmp_path):
        """Test persist and reload a training run."""
        tracker = LocalExperimentTracker(tmp_path)
        run = TrainingRun(
            run_id="track_001",
            symbol="ETHUSDT",
            timeframe="60",
            episodes=10,
            config={"gamma": 0.99},
            metrics={"mean_reward": 0.3},
            status="completed",
        )
        tracker.log_run(run)

        loaded = tracker.load_run("track_001")
        assert loaded is not None
        assert loaded.symbol == "ETHUSDT"
        assert loaded.metrics["mean_reward"] == 0.3

    def test_load_nonexistent_run_returns_none(self, tmp_path):
        """Test loading non-existent run returns None."""
        tracker = LocalExperimentTracker(tmp_path)
        assert tracker.load_run("does_not_exist") is None

    def test_list_runs_all(self, tmp_path):
        """Test listing all runs."""
        tracker = LocalExperimentTracker(tmp_path)
        for i in range(3):
            tracker.log_run(
                TrainingRun(
                    run_id=f"run_{i}",
                    symbol="BTC" if i < 2 else "ETH",
                    timeframe="15",
                    episodes=10,
                    config={},
                    status="completed",
                )
            )
        assert len(tracker.list_runs()) == 3

    def test_list_runs_filter_by_symbol(self, tmp_path):
        """Test listing runs filtered by symbol."""
        tracker = LocalExperimentTracker(tmp_path)
        for sym in ["BTC", "BTC", "ETH"]:
            import uuid

            tracker.log_run(
                TrainingRun(
                    run_id=uuid.uuid4().hex[:8],
                    symbol=sym,
                    timeframe="15",
                    episodes=10,
                    config={},
                    status="completed",
                )
            )
        assert len(tracker.list_runs("BTC")) == 2
        assert len(tracker.list_runs("ETH")) == 1

    def test_best_run_by_metric(self, tmp_path):
        """Test selecting best run by metric."""
        tracker = LocalExperimentTracker(tmp_path)
        for i, sr in enumerate([0.5, 1.2, 0.8]):
            tracker.log_run(
                TrainingRun(
                    run_id=f"best_{i}",
                    symbol="BTC",
                    timeframe="15",
                    episodes=10,
                    config={},
                    metrics={"sharpe_ratio": sr},
                    status="completed",
                )
            )
        best = tracker.best_run("BTC", "sharpe_ratio")
        assert best is not None
        assert best.run_id == "best_1"  # sharpe=1.2


# ============================================================================
# RLTrainingPipeline
# ============================================================================


class TestRLTrainingPipeline:
    """Tests for the RL training pipeline."""

    def test_generate_run_id_unique(self):
        """Test run IDs are unique."""
        ids = {RLTrainingPipeline._generate_run_id() for _ in range(10)}
        assert len(ids) == 10

    def test_build_config_defaults(self):
        """Test config with no overrides uses defaults."""
        config = RLTrainingPipeline._build_config()
        assert config.learning_rate == 1e-4
        assert config.gamma == 0.99

    def test_build_config_with_overrides(self):
        """Test config overrides are applied."""
        config = RLTrainingPipeline._build_config({"learning_rate": 3e-4, "gamma": 0.95})
        assert config.learning_rate == 3e-4
        assert config.gamma == 0.95

    def test_build_config_unknown_key_warns(self, caplog):
        """Test unknown config keys produce warnings."""
        import logging

        with caplog.at_level(logging.WARNING):
            RLTrainingPipeline._build_config({"nonexistent_param": 42})
        assert "Unknown config key" in caplog.text

    def test_generate_synthetic_episode(self):
        """Test synthetic data generation produces valid states."""
        states = RLTrainingPipeline._generate_synthetic_episode(length=100, lookback=10)
        assert len(states) == 90  # length - lookback
        # Each state should convert to array
        arr = states[0].to_array()
        assert arr.ndim == 1
        assert len(arr) > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_train_short_run(self, tmp_path):
        """Test a short training run completes successfully."""
        pipeline = RLTrainingPipeline(artifacts_dir=tmp_path)
        run = await pipeline.train(
            symbol="BTCUSDT",
            timeframe="15",
            episodes=5,
            config_overrides={"batch_size": 16},
        )
        assert run.status == "completed"
        assert run.run_id.startswith("rl_")
        assert "mean_reward" in run.metrics
        assert "sharpe_ratio" in run.metrics
        assert run.model_path != ""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_train_saves_to_tracker(self, tmp_path):
        """Test that completed runs are persisted by tracker."""
        pipeline = RLTrainingPipeline(artifacts_dir=tmp_path)
        run = await pipeline.train(symbol="ETHUSDT", timeframe="60", episodes=3)

        loaded = pipeline.get_run(run.run_id)
        assert loaded is not None
        assert loaded.status == "completed"

    def test_list_runs_empty(self, tmp_path):
        """Test listing runs on empty tracker."""
        pipeline = RLTrainingPipeline(artifacts_dir=tmp_path)
        assert pipeline.list_runs() == []

    def test_best_model_none_when_empty(self, tmp_path):
        """Test best_model returns None when no runs."""
        pipeline = RLTrainingPipeline(artifacts_dir=tmp_path)
        assert pipeline.best_model("BTCUSDT") is None

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_evaluate_nonexistent_run_raises(self, tmp_path):
        """Test evaluating non-existent run raises ValueError."""
        pipeline = RLTrainingPipeline(artifacts_dir=tmp_path)
        with pytest.raises(ValueError, match="not found"):
            await pipeline.evaluate("fake_run_id")
