"""
Tests for AutoML Pipeline

Covers:
- AutoMLConfig defaults and customization
- ModelCandidate dataclass serialization
- PipelineResult dataclass serialization
- AutoMLPipeline initialization and model factories
- Hyperparameter space generation
- Feature selection
- Full pipeline run (with small n_trials)
- Ensemble creation
- Results export
"""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from backend.ml.enhanced.automl_pipeline import (
    AutoMLConfig,
    AutoMLPipeline,
    ModelCandidate,
    ModelType,
    PipelineResult,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def default_config():
    """Default AutoML configuration."""
    return AutoMLConfig()


@pytest.fixture
def fast_config():
    """Fast config for testing (minimal trials)."""
    return AutoMLConfig(
        model_types=[ModelType.RANDOM_FOREST, ModelType.LINEAR],
        n_trials=4,
        timeout_seconds=30,
        cv_folds=2,
        feature_selection=False,
        create_ensemble=False,
        early_stopping_rounds=5,
        patience=3,
    )


@pytest.fixture
def ensemble_config():
    """Config with ensemble creation enabled."""
    return AutoMLConfig(
        model_types=[ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING, ModelType.LINEAR],
        n_trials=6,
        timeout_seconds=60,
        cv_folds=2,
        feature_selection=False,
        create_ensemble=True,
        top_n_models=2,
    )


@pytest.fixture
def classification_data():
    """Binary classification dataset."""
    np.random.seed(42)
    n_samples = 200
    n_features = 5
    X = np.random.randn(n_samples, n_features)
    # Simple linear boundary with noise
    y = (X[:, 0] + X[:, 1] * 0.5 + np.random.randn(n_samples) * 0.3 > 0).astype(int)
    feature_names = [f"feat_{i}" for i in range(n_features)]
    return X, y, feature_names


@pytest.fixture
def regression_data():
    """Regression dataset."""
    np.random.seed(42)
    n_samples = 200
    n_features = 5
    X = np.random.randn(n_samples, n_features)
    y = X[:, 0] * 2 + X[:, 1] * 0.5 + np.random.randn(n_samples) * 0.1
    feature_names = [f"feat_{i}" for i in range(n_features)]
    return X, y, feature_names


# ═══════════════════════════════════════════════════════════════════
# AutoMLConfig Tests
# ═══════════════════════════════════════════════════════════════════


class TestAutoMLConfig:
    """Tests for AutoMLConfig dataclass."""

    def test_default_values(self, default_config):
        """Test default config values."""
        assert default_config.n_trials == 100
        assert default_config.timeout_seconds == 3600
        assert default_config.metric == "sharpe_ratio"
        assert default_config.direction == "maximize"
        assert default_config.cv_folds == 5
        assert default_config.test_size == 0.2
        assert default_config.feature_selection is True
        assert default_config.create_ensemble is True
        assert default_config.top_n_models == 3

    def test_default_model_types(self, default_config):
        """Test that default model types include main algorithms."""
        expected = [
            ModelType.RANDOM_FOREST,
            ModelType.GRADIENT_BOOSTING,
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
        ]
        assert default_config.model_types == expected

    def test_custom_config(self):
        """Test creating custom config."""
        config = AutoMLConfig(
            model_types=[ModelType.LINEAR, ModelType.SVM],
            n_trials=10,
            cv_folds=3,
            feature_selection=False,
        )
        assert len(config.model_types) == 2
        assert config.n_trials == 10
        assert config.cv_folds == 3
        assert config.feature_selection is False

    def test_constraints(self, default_config):
        """Test constraint defaults."""
        assert default_config.max_model_size_mb == 100.0
        assert default_config.max_inference_time_ms == 100.0


# ═══════════════════════════════════════════════════════════════════
# ModelCandidate Tests
# ═══════════════════════════════════════════════════════════════════


class TestModelCandidate:
    """Tests for ModelCandidate dataclass."""

    def test_creation(self):
        """Test creating a model candidate."""
        candidate = ModelCandidate(
            model_id="test_001",
            model_type=ModelType.RANDOM_FOREST,
            hyperparameters={"n_estimators": 100, "max_depth": 5},
            cv_scores=[0.8, 0.82, 0.79],
            mean_score=0.803,
            std_score=0.012,
        )
        assert candidate.model_id == "test_001"
        assert candidate.model_type == ModelType.RANDOM_FOREST
        assert len(candidate.cv_scores) == 3
        assert candidate.mean_score == pytest.approx(0.803)

    def test_to_dict(self):
        """Test serialization to dict."""
        candidate = ModelCandidate(
            model_id="test_002",
            model_type=ModelType.GRADIENT_BOOSTING,
            hyperparameters={"n_estimators": 200},
            cv_scores=[0.75, 0.78],
            mean_score=0.765,
            std_score=0.015,
            training_time_seconds=5.2,
            selected_features=["feat_0", "feat_1"],
        )
        d = candidate.to_dict()

        assert d["model_id"] == "test_002"
        assert d["model_type"] == "gradient_boosting"
        assert d["mean_score"] == 0.765
        assert "model" not in d  # Model excluded

    def test_defaults(self):
        """Test default field values."""
        candidate = ModelCandidate(
            model_id="x",
            model_type=ModelType.LINEAR,
            hyperparameters={},
        )
        assert candidate.cv_scores == []
        assert candidate.mean_score == 0.0
        assert candidate.model is None
        assert candidate.feature_importance == {}
        assert candidate.selected_features == []


# ═══════════════════════════════════════════════════════════════════
# PipelineResult Tests
# ═══════════════════════════════════════════════════════════════════


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_creation(self):
        """Test creating a pipeline result."""
        config = AutoMLConfig(n_trials=5)
        result = PipelineResult(run_id="run_123", config=config)
        assert result.run_id == "run_123"
        assert result.status == "running"
        assert result.best_model is None
        assert result.candidates == []

    def test_to_dict(self):
        """Test serialization to dict."""
        config = AutoMLConfig(n_trials=5)
        result = PipelineResult(
            run_id="run_456",
            config=config,
            best_score=0.85,
            trials_completed=5,
            status="completed",
        )
        d = result.to_dict()
        assert d["run_id"] == "run_456"
        assert d["best_score"] == 0.85
        assert d["trials_completed"] == 5
        assert d["status"] == "completed"
        assert d["candidates_count"] == 0

    def test_to_dict_with_best_model(self):
        """Test serialization includes best_model."""
        config = AutoMLConfig(n_trials=5)
        best = ModelCandidate(
            model_id="m1",
            model_type=ModelType.RANDOM_FOREST,
            hyperparameters={"n_estimators": 50},
            mean_score=0.9,
        )
        result = PipelineResult(
            run_id="run_789",
            config=config,
            best_model=best,
            best_score=0.9,
        )
        d = result.to_dict()
        assert d["best_model"] is not None
        assert d["best_model"]["model_type"] == "random_forest"


# ═══════════════════════════════════════════════════════════════════
# AutoMLPipeline Tests
# ═══════════════════════════════════════════════════════════════════


class TestAutoMLPipeline:
    """Tests for AutoMLPipeline class."""

    def test_init_default(self):
        """Test default initialization."""
        pipeline = AutoMLPipeline()
        assert pipeline.config is not None
        assert pipeline.study is None
        assert pipeline.results == []
        assert len(pipeline._model_factories) == 8

    def test_init_custom_config(self, fast_config):
        """Test initialization with custom config."""
        pipeline = AutoMLPipeline(config=fast_config)
        assert pipeline.config.n_trials == 4
        assert pipeline.config.feature_selection is False

    def test_model_factories_available(self):
        """Test all model factories are registered."""
        pipeline = AutoMLPipeline()
        expected_types = [
            ModelType.RANDOM_FOREST,
            ModelType.GRADIENT_BOOSTING,
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
            ModelType.CATBOOST,
            ModelType.LINEAR,
            ModelType.SVM,
            ModelType.NEURAL_NETWORK,
        ]
        for mt in expected_types:
            assert mt in pipeline._model_factories

    def test_create_random_forest(self):
        """Test Random Forest factory."""
        pipeline = AutoMLPipeline()
        model = pipeline._model_factories[ModelType.RANDOM_FOREST](
            {"n_estimators": 10, "max_depth": 3, "is_classifier": True}
        )
        assert model is not None
        assert hasattr(model, "fit")
        assert hasattr(model, "predict")

    def test_create_linear(self):
        """Test Linear model factory."""
        pipeline = AutoMLPipeline()
        model = pipeline._model_factories[ModelType.LINEAR]({"C": 1.0, "is_classifier": True})
        assert model is not None

    def test_create_gradient_boosting(self):
        """Test Gradient Boosting factory."""
        pipeline = AutoMLPipeline()
        model = pipeline._model_factories[ModelType.GRADIENT_BOOSTING]({"n_estimators": 10, "is_classifier": False})
        assert model is not None
        # Should be regressor
        from sklearn.ensemble import GradientBoostingRegressor

        assert isinstance(model, GradientBoostingRegressor)

    def test_create_svm(self):
        """Test SVM factory."""
        pipeline = AutoMLPipeline()
        model = pipeline._model_factories[ModelType.SVM](
            {"C": 1.0, "kernel": "rbf", "gamma": "scale", "is_classifier": True}
        )
        from sklearn.svm import SVC

        assert isinstance(model, SVC)

    def test_create_neural_network(self):
        """Test Neural Network factory."""
        pipeline = AutoMLPipeline()
        model = pipeline._model_factories[ModelType.NEURAL_NETWORK](
            {"hidden_layer_sizes": (32, 16), "alpha": 0.001, "is_classifier": True}
        )
        from sklearn.neural_network import MLPClassifier

        assert isinstance(model, MLPClassifier)

    def test_get_best_params_empty(self):
        """Test get_best_params with no runs."""
        pipeline = AutoMLPipeline()
        assert pipeline.get_best_params() is None

    def test_get_feature_importance_empty(self):
        """Test get_feature_importance with no runs."""
        pipeline = AutoMLPipeline()
        assert pipeline.get_feature_importance() == {}

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_classification(self, fast_config, classification_data):
        """Test full pipeline run with classification."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=fast_config)

        result = await pipeline.run(X, y, feature_names, is_classifier=True)

        assert result.status == "completed"
        assert result.trials_completed > 0
        assert result.best_model is not None
        assert result.best_score > 0
        assert len(result.candidates) > 0
        assert result.total_time_seconds > 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_regression(self, fast_config, regression_data):
        """Test full pipeline run with regression."""
        X, y, feature_names = regression_data
        config = AutoMLConfig(
            model_types=[ModelType.RANDOM_FOREST, ModelType.LINEAR],
            n_trials=4,
            timeout_seconds=30,
            cv_folds=2,
            cv_type="time_series",
            feature_selection=False,
            create_ensemble=False,
        )
        pipeline = AutoMLPipeline(config=config)

        result = await pipeline.run(X, y, feature_names, is_classifier=False)

        assert result.status == "completed"
        assert result.best_model is not None

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_with_feature_selection(self, classification_data):
        """Test pipeline with feature selection enabled."""
        X, y, feature_names = classification_data
        config = AutoMLConfig(
            model_types=[ModelType.RANDOM_FOREST],
            n_trials=2,
            timeout_seconds=30,
            cv_folds=2,
            feature_selection=True,
            min_feature_importance=0.01,
            create_ensemble=False,
        )
        pipeline = AutoMLPipeline(config=config)

        result = await pipeline.run(X, y, feature_names, is_classifier=True)

        assert result.status == "completed"
        assert len(result.selected_features) > 0
        assert len(result.feature_importance) > 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_with_ensemble(self, ensemble_config, classification_data):
        """Test pipeline with ensemble creation."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=ensemble_config)

        result = await pipeline.run(X, y, feature_names, is_classifier=True)

        assert result.status == "completed"
        if len(result.candidates) >= ensemble_config.top_n_models:
            assert result.ensemble_model is not None
            assert result.ensemble_score > 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_stores_results(self, fast_config, classification_data):
        """Test that pipeline stores results."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=fast_config)

        await pipeline.run(X, y, feature_names)

        assert len(pipeline.results) == 1
        assert pipeline.get_best_params() is not None

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_export_results(self, fast_config, classification_data, tmp_path):
        """Test exporting results to JSON."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=fast_config)

        await pipeline.run(X, y, feature_names)

        export_path = str(tmp_path / "results.json")
        pipeline.export_results(export_path)

        assert os.path.exists(export_path)
        with open(export_path) as f:
            data = json.load(f)
        assert "runs" in data
        assert len(data["runs"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_with_custom_scorer(self, fast_config, classification_data):
        """Test pipeline with custom scoring function."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=fast_config)

        def custom_scorer(y_true, y_pred):
            return float(np.mean(y_true == y_pred))

        result = await pipeline.run(X, y, feature_names, is_classifier=True, custom_scorer=custom_scorer)

        assert result.status == "completed"
        assert result.best_model is not None

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_best_model_retrained_on_full_data(self, fast_config, classification_data):
        """Test that best model is retrained on full data."""
        X, y, feature_names = classification_data
        pipeline = AutoMLPipeline(config=fast_config)

        result = await pipeline.run(X, y, feature_names, is_classifier=True)

        # Best model should be able to predict
        assert result.best_model is not None
        predictions = result.best_model.model.predict(X[:10])
        assert len(predictions) == 10


# ═══════════════════════════════════════════════════════════════════
# ModelType Enum Tests
# ═══════════════════════════════════════════════════════════════════


class TestModelType:
    """Tests for ModelType enum."""

    def test_all_types(self):
        """Test all model types exist."""
        assert len(ModelType) == 9
        assert ModelType.RANDOM_FOREST.value == "random_forest"
        assert ModelType.ENSEMBLE.value == "ensemble"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        mt = ModelType("random_forest")
        assert mt == ModelType.RANDOM_FOREST
