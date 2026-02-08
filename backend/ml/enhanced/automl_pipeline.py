"""
Auto-ML Pipeline for Trading Strategy Optimization

Features:
- Automated model selection from multiple algorithms
- Hyperparameter optimization with Optuna
- Cross-validation with time-series aware splits
- Ensemble model creation
- Feature selection
"""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported model types"""

    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    LINEAR = "linear"
    SVM = "svm"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"


@dataclass
class AutoMLConfig:
    """Configuration for AutoML pipeline"""

    # Search space
    model_types: list[ModelType] = field(
        default_factory=lambda: [
            ModelType.RANDOM_FOREST,
            ModelType.GRADIENT_BOOSTING,
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
        ]
    )

    # Optimization
    n_trials: int = 100
    timeout_seconds: int = 3600
    metric: str = "sharpe_ratio"  # Optimization target
    direction: str = "maximize"

    # Cross-validation
    cv_folds: int = 5
    cv_type: str = "time_series"  # "time_series" or "stratified"
    test_size: float = 0.2

    # Feature selection
    feature_selection: bool = True
    max_features: int | None = None
    min_feature_importance: float = 0.01

    # Ensemble
    create_ensemble: bool = True
    top_n_models: int = 3

    # Early stopping
    early_stopping_rounds: int = 50
    patience: int = 10

    # Constraints
    max_model_size_mb: float = 100.0
    max_inference_time_ms: float = 100.0


@dataclass
class ModelCandidate:
    """A candidate model from AutoML search"""

    model_id: str
    model_type: ModelType
    hyperparameters: dict[str, Any]

    # Performance
    cv_scores: list[float] = field(default_factory=list)
    mean_score: float = 0.0
    std_score: float = 0.0

    # Timing
    training_time_seconds: float = 0.0
    inference_time_ms: float = 0.0

    # Model info
    model_size_mb: float = 0.0
    feature_importance: dict[str, float] = field(default_factory=dict)
    selected_features: list[str] = field(default_factory=list)

    # Trained model
    model: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding model)"""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "hyperparameters": self.hyperparameters,
            "cv_scores": self.cv_scores,
            "mean_score": self.mean_score,
            "std_score": self.std_score,
            "training_time_seconds": self.training_time_seconds,
            "inference_time_ms": self.inference_time_ms,
            "model_size_mb": self.model_size_mb,
            "feature_importance": self.feature_importance,
            "selected_features": self.selected_features,
        }


@dataclass
class PipelineResult:
    """Result of AutoML pipeline run"""

    run_id: str
    config: AutoMLConfig

    # Best model
    best_model: ModelCandidate | None = None
    best_score: float = 0.0

    # All candidates
    candidates: list[ModelCandidate] = field(default_factory=list)

    # Ensemble
    ensemble_model: Any = None
    ensemble_score: float = 0.0

    # Selected features
    selected_features: list[str] = field(default_factory=list)
    feature_importance: dict[str, float] = field(default_factory=dict)

    # Timing
    total_time_seconds: float = 0.0
    trials_completed: int = 0

    # Metadata
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "run_id": self.run_id,
            "best_score": self.best_score,
            "best_model": self.best_model.to_dict() if self.best_model else None,
            "ensemble_score": self.ensemble_score,
            "selected_features": self.selected_features,
            "feature_importance": self.feature_importance,
            "total_time_seconds": self.total_time_seconds,
            "trials_completed": self.trials_completed,
            "status": self.status,
            "candidates_count": len(self.candidates),
        }


class AutoMLPipeline:
    """
    Automated Machine Learning Pipeline for Trading

    Example:
        pipeline = AutoMLPipeline(config=AutoMLConfig(n_trials=50))
        result = await pipeline.run(X_train, y_train, feature_names)

        best_model = result.best_model.model
        predictions = best_model.predict(X_test)
    """

    def __init__(self, config: AutoMLConfig | None = None):
        self.config = config or AutoMLConfig()
        self.results: list[PipelineResult] = []

        # Optuna study
        self.study = None

        # Model factory
        self._model_factories: dict[ModelType, Callable] = {}
        self._setup_model_factories()

    def _setup_model_factories(self) -> None:
        """Setup model creation functions"""

        def create_random_forest(params: dict) -> Any:
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

            is_classifier = params.pop("is_classifier", True)
            cls = RandomForestClassifier if is_classifier else RandomForestRegressor
            return cls(**params)

        def create_gradient_boosting(params: dict) -> Any:
            from sklearn.ensemble import (
                GradientBoostingClassifier,
                GradientBoostingRegressor,
            )

            is_classifier = params.pop("is_classifier", True)
            cls = GradientBoostingClassifier if is_classifier else GradientBoostingRegressor
            return cls(**params)

        def create_xgboost(params: dict) -> Any:
            try:
                import xgboost as xgb

                is_classifier = params.pop("is_classifier", True)
                cls = xgb.XGBClassifier if is_classifier else xgb.XGBRegressor
                return cls(**params, use_label_encoder=False, eval_metric="logloss")
            except ImportError:
                logger.warning("XGBoost not installed, using GradientBoosting")
                return create_gradient_boosting(params)

        def create_lightgbm(params: dict) -> Any:
            try:
                import lightgbm as lgb

                is_classifier = params.pop("is_classifier", True)
                cls = lgb.LGBMClassifier if is_classifier else lgb.LGBMRegressor
                return cls(**params, verbose=-1)
            except ImportError:
                logger.warning("LightGBM not installed, using GradientBoosting")
                return create_gradient_boosting(params)

        def create_catboost(params: dict) -> Any:
            try:
                from catboost import CatBoostClassifier, CatBoostRegressor

                is_classifier = params.pop("is_classifier", True)
                cls = CatBoostClassifier if is_classifier else CatBoostRegressor
                return cls(**params, verbose=False)
            except ImportError:
                logger.warning("CatBoost not installed, using GradientBoosting")
                return create_gradient_boosting(params)

        def create_linear(params: dict) -> Any:
            from sklearn.linear_model import LogisticRegression, Ridge

            is_classifier = params.pop("is_classifier", True)
            cls = LogisticRegression if is_classifier else Ridge
            return cls(**params)

        def create_svm(params: dict) -> Any:
            from sklearn.svm import SVC, SVR

            is_classifier = params.pop("is_classifier", True)
            cls = SVC if is_classifier else SVR
            return cls(**params)

        def create_neural_network(params: dict) -> Any:
            from sklearn.neural_network import MLPClassifier, MLPRegressor

            is_classifier = params.pop("is_classifier", True)
            cls = MLPClassifier if is_classifier else MLPRegressor
            return cls(**params, max_iter=500)

        self._model_factories = {
            ModelType.RANDOM_FOREST: create_random_forest,
            ModelType.GRADIENT_BOOSTING: create_gradient_boosting,
            ModelType.XGBOOST: create_xgboost,
            ModelType.LIGHTGBM: create_lightgbm,
            ModelType.CATBOOST: create_catboost,
            ModelType.LINEAR: create_linear,
            ModelType.SVM: create_svm,
            ModelType.NEURAL_NETWORK: create_neural_network,
        }

    def _get_hyperparameter_space(self, model_type: ModelType, trial: Any) -> dict[str, Any]:
        """Get hyperparameter search space for model type"""

        if model_type == ModelType.RANDOM_FOREST:
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 20),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
            }

        elif model_type in [
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
            ModelType.GRADIENT_BOOSTING,
        ]:
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 15),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0)
                if model_type != ModelType.GRADIENT_BOOSTING
                else None,
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            }

        elif model_type == ModelType.CATBOOST:
            return {
                "iterations": trial.suggest_int("iterations", 100, 1000),
                "depth": trial.suggest_int("depth", 4, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 10),
                "border_count": trial.suggest_int("border_count", 32, 255),
            }

        elif model_type == ModelType.LINEAR:
            return {
                "C": trial.suggest_float("C", 1e-5, 100, log=True),
            }

        elif model_type == ModelType.SVM:
            return {
                "C": trial.suggest_float("C", 1e-3, 100, log=True),
                "kernel": trial.suggest_categorical("kernel", ["rbf", "linear", "poly"]),
                "gamma": trial.suggest_categorical("gamma", ["scale", "auto"]),
            }

        elif model_type == ModelType.NEURAL_NETWORK:
            n_layers = trial.suggest_int("n_layers", 1, 3)
            hidden_layer_sizes = tuple(trial.suggest_int(f"layer_{i}", 32, 256) for i in range(n_layers))
            return {
                "hidden_layer_sizes": hidden_layer_sizes,
                "alpha": trial.suggest_float("alpha", 1e-5, 1e-1, log=True),
                "learning_rate_init": trial.suggest_float("learning_rate_init", 1e-4, 1e-2, log=True),
            }

        return {}

    async def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
        is_classifier: bool = True,
        custom_scorer: Callable | None = None,
    ) -> PipelineResult:
        """
        Run the AutoML pipeline

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target variable
            feature_names: Optional feature names
            is_classifier: Whether this is classification
            custom_scorer: Optional custom scoring function

        Returns:
            PipelineResult with best model and all candidates
        """
        import time

        import optuna
        from sklearn.model_selection import (
            StratifiedKFold,
            TimeSeriesSplit,
            cross_val_score,
        )

        run_id = hashlib.sha256(f"{datetime.now(UTC)}".encode()).hexdigest()[:12]

        result = PipelineResult(run_id=run_id, config=self.config, started_at=datetime.now(UTC))

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        # Feature selection
        if self.config.feature_selection:
            X, selected_features, importance = await self._select_features(X, y, feature_names, is_classifier)
            result.selected_features = selected_features
            result.feature_importance = importance
        else:
            result.selected_features = feature_names

        # Setup cross-validation
        if self.config.cv_type == "time_series":
            cv = TimeSeriesSplit(n_splits=self.config.cv_folds)
        else:
            cv = StratifiedKFold(n_splits=self.config.cv_folds, shuffle=True)

        # Optuna objective
        candidates: list[ModelCandidate] = []

        def objective(trial: optuna.Trial) -> float:
            # Select model type
            model_type = ModelType(trial.suggest_categorical("model_type", [m.value for m in self.config.model_types]))

            # Get hyperparameters
            params = self._get_hyperparameter_space(model_type, trial)
            params = {k: v for k, v in params.items() if v is not None}
            params["is_classifier"] = is_classifier

            # Create model
            model = self._model_factories[model_type](params.copy())

            # Cross-validate
            start_time = time.time()

            try:
                if custom_scorer:
                    scores = []
                    for train_idx, val_idx in cv.split(X, y):
                        model.fit(X[train_idx], y[train_idx])
                        pred = model.predict(X[val_idx])
                        scores.append(custom_scorer(y[val_idx], pred))
                else:
                    scores = cross_val_score(
                        model,
                        X,
                        y,
                        cv=cv,
                        scoring="accuracy" if is_classifier else "neg_mean_squared_error",
                    )

                mean_score = np.mean(scores)
                std_score = np.std(scores)

            except Exception as e:
                logger.warning(f"Model {model_type.value} failed: {e}")
                return float("-inf") if self.config.direction == "maximize" else float("inf")

            training_time = time.time() - start_time

            # Create candidate
            candidate = ModelCandidate(
                model_id=f"{run_id}_{trial.number}",
                model_type=model_type,
                hyperparameters=params,
                cv_scores=list(scores),
                mean_score=float(mean_score),
                std_score=float(std_score),
                training_time_seconds=training_time,
                selected_features=result.selected_features,
                model=model,
            )

            candidates.append(candidate)

            return mean_score

        # Run optimization
        logger.info(f"Starting AutoML pipeline with {self.config.n_trials} trials")
        start_time = time.time()

        try:
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            self.study = optuna.create_study(direction=self.config.direction, study_name=run_id)

            self.study.optimize(
                objective,
                n_trials=self.config.n_trials,
                timeout=self.config.timeout_seconds,
                show_progress_bar=False,
            )

            result.trials_completed = len(self.study.trials)

        except Exception as e:
            logger.error(f"AutoML optimization failed: {e}")
            result.status = "failed"
            return result

        result.total_time_seconds = time.time() - start_time

        # Get best model
        result.candidates = sorted(
            candidates,
            key=lambda x: x.mean_score,
            reverse=(self.config.direction == "maximize"),
        )

        if result.candidates:
            result.best_model = result.candidates[0]
            result.best_score = result.best_model.mean_score

            # Retrain best model on full data
            result.best_model.model.fit(X, y)

        # Create ensemble
        if self.config.create_ensemble and len(result.candidates) >= self.config.top_n_models:
            result.ensemble_model, result.ensemble_score = await self._create_ensemble(
                X, y, result.candidates[: self.config.top_n_models], cv, is_classifier
            )

        result.completed_at = datetime.now(UTC)
        result.status = "completed"

        self.results.append(result)

        logger.info(f"AutoML completed: {result.trials_completed} trials, best score: {result.best_score:.4f}")

        return result

    async def _select_features(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        is_classifier: bool,
    ) -> tuple:
        """Select important features"""
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.feature_selection import SelectFromModel

        # Train a quick RF for feature importance
        estimator = (
            RandomForestClassifier(n_estimators=100, random_state=42)
            if is_classifier
            else RandomForestRegressor(n_estimators=100, random_state=42)
        )

        estimator.fit(X, y)

        # Get importances
        importance = dict(zip(feature_names, estimator.feature_importances_))

        # Select features
        selector = SelectFromModel(
            estimator,
            threshold=self.config.min_feature_importance,
            max_features=self.config.max_features,
        )

        X_selected = selector.fit_transform(X, y)

        # Get selected feature names
        mask = selector.get_support()
        selected_features = [name for name, m in zip(feature_names, mask) if m]

        logger.info(f"Selected {len(selected_features)}/{len(feature_names)} features")

        return X_selected, selected_features, importance

    async def _create_ensemble(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_models: list[ModelCandidate],
        cv: Any,
        is_classifier: bool,
    ) -> tuple:
        """Create ensemble from top models"""
        from sklearn.ensemble import VotingClassifier, VotingRegressor
        from sklearn.model_selection import cross_val_score

        # Rebuild models for ensemble
        estimators = []
        for i, candidate in enumerate(top_models):
            params = candidate.hyperparameters.copy()
            params["is_classifier"] = is_classifier
            model = self._model_factories[candidate.model_type](params)
            estimators.append((f"model_{i}", model))

        # Create voting ensemble
        if is_classifier:
            ensemble = VotingClassifier(estimators=estimators, voting="soft")
        else:
            ensemble = VotingRegressor(estimators=estimators)

        # Evaluate
        scores = cross_val_score(
            ensemble,
            X,
            y,
            cv=cv,
            scoring="accuracy" if is_classifier else "neg_mean_squared_error",
        )

        # Fit on full data
        ensemble.fit(X, y)

        ensemble_score = float(np.mean(scores))
        logger.info(f"Ensemble score: {ensemble_score:.4f}")

        return ensemble, ensemble_score

    def get_best_params(self) -> dict[str, Any] | None:
        """Get best hyperparameters from last run"""
        if not self.results:
            return None

        last_result = self.results[-1]
        if last_result.best_model:
            return last_result.best_model.hyperparameters
        return None

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance from last run"""
        if not self.results:
            return {}
        return self.results[-1].feature_importance

    def export_results(self, path: str) -> None:
        """Export results to JSON"""
        import json

        if not self.results:
            return

        data = {"runs": [r.to_dict() for r in self.results]}

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
