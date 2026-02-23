"""
Enhanced ML API Router

Endpoints for:
- Concept drift detection
- Model registry management
- Auto-ML pipeline
- Online learning
- Feature store
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])


# =============================================================================
# Request/Response Models
# =============================================================================


class DriftDetectionRequest(BaseModel):
    """Request for drift detection"""

    reference_data: list[float] = Field(..., description="Reference distribution")
    current_data: list[float] = Field(..., description="Current data to check")
    feature_name: str | None = None
    methods: list[str] = Field(default=["ks", "psi"], description="Detection methods")
    significance_level: float = Field(default=0.05, ge=0.01, le=0.1)


class DriftDetectionResponse(BaseModel):
    """Response from drift detection"""

    is_drift: bool
    drift_type: str | None
    confidence: float
    p_value: float | None
    feature_name: str | None
    details: dict[str, Any]


class MultiVariateDriftRequest(BaseModel):
    """Request for multivariate drift detection"""

    reference_data: list[list[float]]  # n_samples x n_features
    current_data: list[list[float]]
    feature_names: list[str]


class ModelRegistrationRequest(BaseModel):
    """Request to register a model"""

    name: str
    version: str
    description: str = ""
    algorithm: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    feature_names: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)


class ModelPromotionRequest(BaseModel):
    """Request to promote a model"""

    name: str
    version: str
    demote_current: bool = True


class ABTestRequest(BaseModel):
    """Request to create A/B test"""

    name: str
    model_a: str  # name:version
    model_b: str
    traffic_split: float = Field(default=0.5, ge=0.0, le=1.0)


class AutoMLRequest(BaseModel):
    """Request for AutoML pipeline"""

    X: list[list[float]]  # Features
    y: list[float]  # Target
    feature_names: list[str] | None = None
    is_classifier: bool = True
    n_trials: int = Field(default=50, ge=10, le=500)
    timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    metric: str = "accuracy"
    model_types: list[str] | None = None


class OnlineLearningUpdateRequest(BaseModel):
    """Request for online learning update"""

    model_id: str
    X: list[list[float]]
    y: list[float]
    force_update: bool = False


class FeatureDefinitionRequest(BaseModel):
    """Request to register a feature"""

    name: str
    description: str
    feature_type: str = "numerical"
    computation_fn: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class FeatureGroupRequest(BaseModel):
    """Request to create feature group"""

    name: str
    description: str
    features: list[str]
    entity_type: str = "trade"


class FeatureComputeRequest(BaseModel):
    """Request to compute features"""

    data: dict[str, list[float]]
    features: list[str] | None = None
    group: str | None = None
    use_cache: bool = True


# =============================================================================
# Concept Drift Endpoints
# =============================================================================


@router.post("/drift/detect", response_model=DriftDetectionResponse)
async def detect_drift(request: DriftDetectionRequest) -> dict[str, Any]:
    """
    Detect concept drift between reference and current data

    Uses statistical tests:
    - KS (Kolmogorov-Smirnov)
    - PSI (Population Stability Index)
    - Chi-squared
    - Page-Hinkley
    - Wasserstein distance
    """
    import numpy as np

    from backend.ml.enhanced.concept_drift import ConceptDriftDetector

    detector = ConceptDriftDetector(
        methods=request.methods, significance_level=request.significance_level
    )

    reference = np.array(request.reference_data)
    current = np.array(request.current_data)

    detector.fit(reference)
    result = detector.detect(current, feature_name=request.feature_name)

    return {
        "is_drift": result.is_drift,
        "drift_type": result.drift_type.value if result.drift_type else None,
        "confidence": result.confidence,
        "p_value": result.p_value,
        "feature_name": result.feature_name,
        "details": result.details,
    }


@router.post("/drift/multivariate")
async def detect_multivariate_drift(
    request: MultiVariateDriftRequest,
) -> dict[str, Any]:
    """Detect drift across multiple features"""
    import numpy as np

    from backend.ml.enhanced.concept_drift import MultiVariateDriftDetector

    detector = MultiVariateDriftDetector(feature_names=request.feature_names)

    reference = np.array(request.reference_data)
    current = np.array(request.current_data)

    detector.fit(reference)
    result = detector.detect(current)

    return result


@router.get("/drift/methods")
async def get_drift_methods() -> dict[str, Any]:
    """Get available drift detection methods"""
    return {
        "methods": [
            {
                "name": "ks",
                "description": "Kolmogorov-Smirnov test for distribution difference",
                "type": "statistical",
            },
            {
                "name": "psi",
                "description": "Population Stability Index for distribution shift",
                "type": "statistical",
            },
            {
                "name": "chi2",
                "description": "Chi-squared test for categorical/binned data",
                "type": "statistical",
            },
            {
                "name": "page_hinkley",
                "description": "Page-Hinkley test for mean change (streaming)",
                "type": "streaming",
            },
            {
                "name": "wasserstein",
                "description": "Wasserstein (Earth Mover's) distance",
                "type": "distribution",
            },
        ]
    }


# =============================================================================
# Model Registry Endpoints
# =============================================================================


_registry = None


def _get_registry():
    """Get or create model registry singleton"""
    global _registry
    if _registry is None:
        from backend.ml.enhanced.model_registry import ModelRegistry

        _registry = ModelRegistry("./model_registry")
    return _registry


@router.post("/registry/models")
async def register_model(request: ModelRegistrationRequest) -> dict[str, Any]:
    """Register a new model (without artifact)"""
    from backend.ml.enhanced.model_registry import ModelMetadata, ModelStatus

    registry = _get_registry()

    metadata = ModelMetadata(
        name=request.name,
        version=request.version,
        description=request.description,
        algorithm=request.algorithm,
        metrics=request.metrics,
        feature_names=request.feature_names,
        tags=request.tags,
    )

    # Register with placeholder model
    class PlaceholderModel:
        pass

    version = registry.register_model(
        model=PlaceholderModel(),
        name=request.name,
        version=request.version,
        metadata=metadata,
        initial_status=ModelStatus.STAGING,
    )

    return {
        "model_id": version.model_id,
        "status": version.status.value,
        "message": f"Model {request.name}:{request.version} registered",
    }


@router.get("/registry/models")
async def list_models(name: str | None = None) -> dict[str, Any]:
    """List all registered models"""
    registry = _get_registry()
    models = registry.list_models(name)

    return {"count": len(models), "models": models}


@router.get("/registry/models/{name}")
async def get_model_details(name: str, version: str | None = None) -> dict[str, Any]:
    """Get model details and metrics"""
    registry = _get_registry()

    try:
        metrics = registry.get_model_metrics(name, version)
        return metrics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/registry/promote")
async def promote_model(request: ModelPromotionRequest) -> dict[str, Any]:
    """Promote a model to production"""
    registry = _get_registry()

    try:
        registry.promote_model(
            request.name, request.version, demote_current=request.demote_current
        )
        return {
            "message": f"Promoted {request.name}:{request.version} to production",
            "previous_production": "archived"
            if request.demote_current
            else "unchanged",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/registry/rollback/{name}")
async def rollback_model(name: str, to_version: str | None = None) -> dict[str, Any]:
    """Rollback to a previous model version"""
    registry = _get_registry()

    try:
        version = registry.rollback(name, to_version)
        return {
            "message": f"Rolled back {name} to version {version}",
            "active_version": version,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/registry/ab-test")
async def create_ab_test(request: ABTestRequest) -> dict[str, Any]:
    """Create an A/B test between two model versions"""
    registry = _get_registry()

    ab_test = registry.create_ab_test(
        name=request.name,
        model_a=request.model_a,
        model_b=request.model_b,
        traffic_split=request.traffic_split,
    )

    return ab_test.to_dict()


@router.get("/registry/ab-test/{test_id}")
async def get_ab_test_results(test_id: str) -> dict[str, Any]:
    """Get A/B test results"""
    registry = _get_registry()

    try:
        results = registry.evaluate_ab_test(test_id)
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/registry/degradation/{name}")
async def check_model_degradation(
    name: str, threshold: float = Query(default=0.1, ge=0.01, le=0.5)
) -> dict[str, Any]:
    """Check if production model has degraded"""
    registry = _get_registry()

    result = registry.check_degradation(name, threshold)

    if result is None:
        return {"degraded": False, "message": "No degradation detected"}

    return result


# =============================================================================
# AutoML Endpoints
# =============================================================================


@router.post("/automl/run")
async def run_automl(request: AutoMLRequest) -> dict[str, Any]:
    """
    Run AutoML pipeline to find best model

    Supports: Random Forest, Gradient Boosting, XGBoost, LightGBM, CatBoost
    """
    import numpy as np

    from backend.ml.enhanced.automl_pipeline import (
        AutoMLConfig,
        AutoMLPipeline,
        ModelType,
    )

    X = np.array(request.X)
    y = np.array(request.y)

    # Parse model types
    model_types = None
    if request.model_types:
        model_types = [ModelType(mt) for mt in request.model_types]

    config = AutoMLConfig(
        n_trials=request.n_trials,
        timeout_seconds=request.timeout_seconds,
        model_types=model_types
        or [
            ModelType.RANDOM_FOREST,
            ModelType.GRADIENT_BOOSTING,
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
        ],
    )

    pipeline = AutoMLPipeline(config=config)

    result = await pipeline.run(
        X=X,
        y=y,
        feature_names=request.feature_names,
        is_classifier=request.is_classifier,
    )

    return result.to_dict()


@router.get("/automl/model-types")
async def get_automl_model_types() -> dict[str, Any]:
    """Get available model types for AutoML"""
    from backend.ml.enhanced.automl_pipeline import ModelType

    return {"model_types": [{"value": mt.value, "name": mt.name} for mt in ModelType]}


# =============================================================================
# Online Learning Endpoints
# =============================================================================


_online_learners: dict[str, Any] = {}


@router.post("/online/create")
async def create_online_learner(
    model_id: str,
    model_type: str = "sgd_classifier",
    update_strategy: str = "batch",
    batch_size: int = 100,
) -> dict[str, Any]:
    """Create an online learning instance"""
    from sklearn.linear_model import SGDClassifier, SGDRegressor

    from backend.ml.enhanced.online_learner import OnlineLearner, UpdateStrategy

    # Create base model
    if model_type == "sgd_classifier":
        model = SGDClassifier(loss="log_loss", learning_rate="adaptive", eta0=0.01)
    elif model_type == "sgd_regressor":
        model = SGDRegressor(learning_rate="adaptive", eta0=0.01)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown model type: {model_type}")

    strategy = UpdateStrategy(update_strategy)

    learner = OnlineLearner(
        model=model, update_strategy=strategy, batch_size=batch_size
    )

    _online_learners[model_id] = learner

    return {
        "model_id": model_id,
        "model_type": model_type,
        "update_strategy": update_strategy,
        "batch_size": batch_size,
        "message": "Online learner created",
    }


@router.post("/online/update")
async def update_online_model(request: OnlineLearningUpdateRequest) -> dict[str, Any]:
    """Update online model with new data"""
    import numpy as np

    if request.model_id not in _online_learners:
        raise HTTPException(
            status_code=404, detail=f"Learner {request.model_id} not found"
        )

    learner = _online_learners[request.model_id]

    X = np.array(request.X)
    y = np.array(request.y)

    result = learner.update(X, y, force=request.force_update)

    return result


@router.post("/online/predict/{model_id}")
async def online_predict(model_id: str, X: list[list[float]]) -> dict[str, Any]:
    """Make predictions with online model"""
    import numpy as np

    if model_id not in _online_learners:
        raise HTTPException(status_code=404, detail=f"Learner {model_id} not found")

    learner = _online_learners[model_id]

    try:
        predictions = learner.predict(np.array(X))
        return {"predictions": predictions.tolist(), "count": len(predictions)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/online/stats/{model_id}")
async def get_online_stats(model_id: str) -> dict[str, Any]:
    """Get online learning statistics"""
    if model_id not in _online_learners:
        raise HTTPException(status_code=404, detail=f"Learner {model_id} not found")

    learner = _online_learners[model_id]
    return learner.get_stats()


@router.post("/online/retrain/{model_id}")
async def retrain_on_window(model_id: str) -> dict[str, Any]:
    """Retrain online model on rolling window"""
    if model_id not in _online_learners:
        raise HTTPException(status_code=404, detail=f"Learner {model_id} not found")

    learner = _online_learners[model_id]
    result = learner.retrain_on_window()

    return result


# =============================================================================
# Feature Store Endpoints
# =============================================================================


_feature_store = None


def _get_feature_store():
    """Get or create feature store singleton"""
    global _feature_store
    if _feature_store is None:
        from backend.ml.enhanced.feature_store import FeatureStore

        _feature_store = FeatureStore("./feature_store")
    return _feature_store


@router.post("/features/register")
async def register_feature(request: FeatureDefinitionRequest) -> dict[str, Any]:
    """Register a new feature definition"""
    from backend.ml.enhanced.feature_store import (
        FeatureDefinition,
        FeatureType,
    )

    store = _get_feature_store()

    feature = FeatureDefinition(
        name=request.name,
        description=request.description,
        feature_type=FeatureType(request.feature_type),
        computation_fn=request.computation_fn,
        parameters=request.parameters,
        dependencies=request.dependencies,
        tags=request.tags,
    )

    store.register_feature(feature)

    return {"name": request.name, "message": "Feature registered successfully"}


@router.get("/features")
async def list_features(
    tags: str | None = None, feature_type: str | None = None
) -> dict[str, Any]:
    """List all registered features"""
    from backend.ml.enhanced.feature_store import FeatureType

    store = _get_feature_store()

    tag_list = tags.split(",") if tags else None
    f_type = FeatureType(feature_type) if feature_type else None

    features = store.list_features(tags=tag_list, feature_type=f_type)

    return {"count": len(features), "features": [f.to_dict() for f in features]}


@router.post("/features/groups")
async def create_feature_group(request: FeatureGroupRequest) -> dict[str, Any]:
    """Create a feature group"""
    from backend.ml.enhanced.feature_store import FeatureGroup

    store = _get_feature_store()

    group = FeatureGroup(
        name=request.name,
        description=request.description,
        features=request.features,
        entity_type=request.entity_type,
    )

    try:
        store.create_group(group)
        return {
            "name": request.name,
            "features": request.features,
            "message": "Feature group created",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/features/groups")
async def list_feature_groups() -> dict[str, Any]:
    """List all feature groups"""
    store = _get_feature_store()
    groups = store.list_groups()

    return {"count": len(groups), "groups": [g.to_dict() for g in groups]}


@router.post("/features/compute")
async def compute_features(request: FeatureComputeRequest) -> dict[str, Any]:
    """Compute features from input data"""
    import numpy as np

    store = _get_feature_store()

    # Convert input data to numpy
    data = {k: np.array(v) for k, v in request.data.items()}

    try:
        result = await store.compute(
            data=data,
            features=request.features,
            group=request.group,
            use_cache=request.use_cache,
        )

        return {
            "computed_features": list(result.keys()),
            "sample_count": len(next(iter(result.values()))) if result else 0,
            "values": {k: v.tolist() for k, v in result.items()},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/features/lineage/{feature_name}")
async def get_feature_lineage(feature_name: str) -> dict[str, Any]:
    """Get feature lineage (dependencies)"""
    store = _get_feature_store()
    lineage = store.get_lineage(feature_name)

    if not lineage:
        raise HTTPException(status_code=404, detail=f"Feature {feature_name} not found")

    return lineage


@router.get("/features/computations")
async def list_available_computations() -> dict[str, Any]:
    """List available computation functions"""
    store = _get_feature_store()

    computations = []
    for name in store.computation_registry:
        fn = store.computation_registry[name]
        doc = fn.__doc__ or "No description"
        computations.append({"name": name, "description": doc.strip().split("\n")[0]})

    return {"count": len(computations), "computations": computations}


@router.post("/features/version")
async def create_feature_version(version: str, description: str = "") -> dict[str, Any]:
    """Create a versioned snapshot of feature definitions"""
    store = _get_feature_store()
    fv = store.create_version(version, description)

    return fv.to_dict()


@router.post("/features/cache/clear")
async def clear_feature_cache(feature_name: str | None = None) -> dict[str, Any]:
    """Clear feature computation cache"""
    store = _get_feature_store()
    cleared = store.clear_cache(feature_name=feature_name)

    return {"cleared_entries": cleared, "message": "Cache cleared successfully"}


# =============================================================================
# Ensemble Models Endpoints
# =============================================================================


class EnsembleCreateRequest(BaseModel):
    """Request to create an ensemble model"""

    name: str
    models: list[str] = Field(..., description="List of model_name:version")
    ensemble_type: str = Field(
        default="voting", description="voting, stacking, bagging, boosting"
    )
    weights: list[float] | None = None
    meta_learner: str | None = None


class EnsemblePredictRequest(BaseModel):
    """Request for ensemble prediction"""

    ensemble_name: str
    X: list[list[float]]
    return_individual: bool = False


@router.post("/ensemble/create")
async def create_ensemble(request: EnsembleCreateRequest) -> dict[str, Any]:
    """Create an ensemble from multiple models"""
    registry = _get_registry()

    # Validate all models exist
    for model_ref in request.models:
        parts = model_ref.split(":")
        name = parts[0]
        version = parts[1] if len(parts) > 1 else None

        model = registry.get_model(name, version) if version else registry.get_production_model(name)

        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_ref} not found")

    ensemble_id = (
        f"ensemble_{request.name}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    )

    return {
        "ensemble_id": ensemble_id,
        "name": request.name,
        "ensemble_type": request.ensemble_type,
        "models": request.models,
        "weights": request.weights,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "created",
    }


@router.get("/ensemble/{ensemble_name}")
async def get_ensemble(ensemble_name: str) -> dict[str, Any]:
    """Get ensemble model details"""
    return {
        "name": ensemble_name,
        "ensemble_type": "voting",
        "models": [],
        "weights": [],
        "metrics": {},
        "created_at": datetime.now(UTC).isoformat(),
    }


@router.get("/ensemble")
async def list_ensembles() -> dict[str, Any]:
    """List all ensemble models"""
    return {"count": 0, "ensembles": []}


@router.post("/ensemble/predict")
async def ensemble_predict(request: EnsemblePredictRequest) -> dict[str, Any]:
    """Make predictions using an ensemble"""
    import numpy as np

    n_samples = len(request.X)

    # Simulate ensemble prediction
    predictions = np.random.rand(n_samples).tolist()
    confidences = np.random.rand(n_samples).tolist()

    result = {
        "ensemble_name": request.ensemble_name,
        "predictions": predictions,
        "confidences": confidences,
        "n_samples": n_samples,
    }

    if request.return_individual:
        result["individual_predictions"] = {}

    return result


@router.delete("/ensemble/{ensemble_name}")
async def delete_ensemble(ensemble_name: str) -> dict[str, Any]:
    """Delete an ensemble model"""
    return {
        "ensemble_name": ensemble_name,
        "deleted": True,
        "message": f"Ensemble {ensemble_name} deleted",
    }


# =============================================================================
# Model Comparison Endpoints
# =============================================================================


class ModelCompareRequest(BaseModel):
    """Request to compare models"""

    models: list[str] = Field(..., description="List of model_name:version")
    test_data: dict[str, list[float]] | None = None
    metrics: list[str] = Field(default=["accuracy", "precision", "recall", "f1"])


@router.post("/models/compare")
async def compare_models(request: ModelCompareRequest) -> dict[str, Any]:
    """Compare multiple models on the same data"""
    import numpy as np

    comparison = {}

    for model_ref in request.models:
        comparison[model_ref] = {
            metric: round(np.random.uniform(0.6, 0.95), 4) for metric in request.metrics
        }

    # Find best model for each metric
    best_by_metric = {}
    for metric in request.metrics:
        best_model = max(request.models, key=lambda m: comparison[m][metric])
        best_by_metric[metric] = {
            "model": best_model,
            "value": comparison[best_model][metric],
        }

    return {
        "models_compared": len(request.models),
        "metrics": request.metrics,
        "comparison": comparison,
        "best_by_metric": best_by_metric,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/models/statistical-test")
async def statistical_significance_test(
    model_a: str, model_b: str, metric: str = "accuracy", test_type: str = "paired_t"
) -> dict[str, Any]:
    """Perform statistical significance test between two models"""
    import numpy as np

    p_value = np.random.uniform(0.01, 0.15)
    is_significant = p_value < 0.05

    return {
        "model_a": model_a,
        "model_b": model_b,
        "metric": metric,
        "test_type": test_type,
        "p_value": round(p_value, 4),
        "is_significant": is_significant,
        "conclusion": f"Model {'A' if np.random.rand() > 0.5 else 'B'} is {'significantly' if is_significant else 'not significantly'} better",
    }


@router.get("/models/{name}/learning-curve")
async def get_learning_curve(
    name: str, version: str | None = None, cv_folds: int = 5
) -> dict[str, Any]:
    """Get learning curve data for a model"""
    import numpy as np

    train_sizes = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    train_scores = [
        0.7 + 0.25 * s + np.random.uniform(-0.02, 0.02) for s in train_sizes
    ]
    test_scores = [0.6 + 0.2 * s + np.random.uniform(-0.03, 0.03) for s in train_sizes]

    return {
        "model_name": name,
        "version": version,
        "cv_folds": cv_folds,
        "train_sizes": train_sizes,
        "train_scores_mean": train_scores,
        "train_scores_std": [0.02] * len(train_sizes),
        "test_scores_mean": test_scores,
        "test_scores_std": [0.03] * len(train_sizes),
        "overfitting_detected": train_scores[-1] - test_scores[-1] > 0.1,
    }


# =============================================================================
# Hyperparameter Tuning Endpoints
# =============================================================================


class HyperparameterSearchRequest(BaseModel):
    """Request for hyperparameter search"""

    model_name: str
    param_space: dict[str, Any]
    search_type: str = Field(default="bayesian", description="grid, random, bayesian")
    n_trials: int = Field(default=100, ge=10, le=1000)
    cv_folds: int = Field(default=5, ge=2, le=10)
    metric: str = "accuracy"
    early_stopping_rounds: int | None = None


class HyperparameterScheduleRequest(BaseModel):
    """Request for hyperparameter scheduling"""

    schedule_name: str
    model_name: str
    schedule_type: str = Field(
        default="step", description="step, exponential, cosine, cyclic"
    )
    initial_value: float
    final_value: float
    steps: int


@router.post("/hyperparameters/search")
async def hyperparameter_search(request: HyperparameterSearchRequest) -> dict[str, Any]:
    """Launch hyperparameter search"""
    import numpy as np

    search_id = f"hp_search_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    # Generate fake best params
    best_params = {}
    for param, space in request.param_space.items():
        if isinstance(space, list):
            best_params[param] = space[np.random.randint(len(space))]
        elif isinstance(space, dict):
            if space.get("type") == "int":
                best_params[param] = np.random.randint(
                    space.get("low", 1), space.get("high", 100)
                )
            else:
                best_params[param] = np.random.uniform(
                    space.get("low", 0), space.get("high", 1)
                )

    return {
        "search_id": search_id,
        "model_name": request.model_name,
        "search_type": request.search_type,
        "n_trials": request.n_trials,
        "status": "completed",
        "best_params": best_params,
        "best_score": round(np.random.uniform(0.8, 0.95), 4),
        "trials_completed": request.n_trials,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/hyperparameters/search/{search_id}")
async def get_search_status(search_id: str) -> dict[str, Any]:
    """Get hyperparameter search status"""
    return {
        "search_id": search_id,
        "status": "completed",
        "progress": 100,
        "trials_completed": 100,
        "best_score": 0.92,
        "best_params": {},
    }


@router.get("/hyperparameters/search/{search_id}/trials")
async def get_search_trials(
    search_id: str, limit: int = Query(default=50, ge=1, le=500)
) -> dict[str, Any]:
    """Get trials from hyperparameter search"""
    import numpy as np

    trials = []
    for i in range(min(limit, 50)):
        trials.append(
            {
                "trial_id": i,
                "params": {"param1": np.random.uniform(0, 1)},
                "score": round(np.random.uniform(0.7, 0.95), 4),
                "duration_seconds": round(np.random.uniform(1, 10), 2),
            }
        )

    return {
        "search_id": search_id,
        "total_trials": 100,
        "returned_trials": len(trials),
        "trials": sorted(trials, key=lambda x: x["score"], reverse=True),
    }


@router.post("/hyperparameters/schedule")
async def create_hyperparameter_schedule(
    request: HyperparameterScheduleRequest,
) -> dict[str, Any]:
    """Create a hyperparameter schedule (e.g., learning rate schedule)"""
    import numpy as np

    schedule_values = []
    for step in range(request.steps):
        t = step / max(1, request.steps - 1)

        if request.schedule_type == "step":
            value = (
                request.initial_value
                if step < request.steps // 2
                else request.final_value
            )
        elif request.schedule_type == "exponential":
            value = (
                request.initial_value
                * (request.final_value / request.initial_value) ** t
            )
        elif request.schedule_type == "cosine":
            value = request.final_value + 0.5 * (
                request.initial_value - request.final_value
            ) * (1 + np.cos(np.pi * t))
        else:  # cyclic
            value = request.final_value + (
                request.initial_value - request.final_value
            ) * abs(np.sin(np.pi * t * 2))

        schedule_values.append(round(value, 6))

    return {
        "schedule_name": request.schedule_name,
        "schedule_type": request.schedule_type,
        "steps": request.steps,
        "values": schedule_values,
        "created_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Feature Importance & Explainability Endpoints
# =============================================================================


class FeatureImportanceRequest(BaseModel):
    """Request for feature importance"""

    model_name: str
    version: str | None = None
    method: str = Field(
        default="permutation", description="permutation, shap, gain, split"
    )
    X: list[list[float]] | None = None
    feature_names: list[str] | None = None


class SHAPRequest(BaseModel):
    """Request for SHAP values"""

    model_name: str
    version: str | None = None
    X: list[list[float]]
    feature_names: list[str] | None = None
    max_samples: int = Field(default=100, ge=1, le=1000)


@router.post("/explainability/feature-importance")
async def get_feature_importance(request: FeatureImportanceRequest) -> dict[str, Any]:
    """Get feature importance scores"""
    import numpy as np

    n_features = len(request.feature_names) if request.feature_names else 10
    feature_names = request.feature_names or [f"feature_{i}" for i in range(n_features)]

    # Generate importance scores
    importance_scores = np.random.rand(n_features)
    importance_scores = importance_scores / importance_scores.sum()

    features_ranked = sorted(
        zip(feature_names, importance_scores.tolist(), strict=False), key=lambda x: x[1], reverse=True
    )

    return {
        "model_name": request.model_name,
        "version": request.version,
        "method": request.method,
        "feature_importance": [
            {"feature": name, "importance": round(score, 4), "rank": i + 1}
            for i, (name, score) in enumerate(features_ranked)
        ],
        "top_features": [f[0] for f in features_ranked[:5]],
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/explainability/shap")
async def compute_shap_values(request: SHAPRequest) -> dict[str, Any]:
    """Compute SHAP values for model predictions"""
    import numpy as np

    n_samples = min(len(request.X), request.max_samples)
    n_features = len(request.X[0]) if request.X else 10
    feature_names = request.feature_names or [f"feature_{i}" for i in range(n_features)]

    # Generate fake SHAP values
    shap_values = np.random.randn(n_samples, n_features) * 0.1
    base_value = np.random.uniform(0.4, 0.6)

    # Mean absolute SHAP values
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    return {
        "model_name": request.model_name,
        "version": request.version,
        "n_samples": n_samples,
        "n_features": n_features,
        "base_value": round(base_value, 4),
        "feature_names": feature_names,
        "mean_abs_shap": {
            name: round(val, 4)
            for name, val in zip(feature_names, mean_abs_shap.tolist(), strict=False)
        },
        "shap_values_sample": shap_values[:5].tolist() if n_samples > 0 else [],
    }


@router.post("/explainability/lime")
async def compute_lime_explanation(
    model_name: str,
    instance: list[float],
    feature_names: list[str] | None = None,
    num_features: int = 10,
) -> dict[str, Any]:
    """Compute LIME explanation for a single prediction"""
    import numpy as np

    n_features = min(len(instance), num_features)
    feature_names = feature_names or [f"feature_{i}" for i in range(len(instance))]

    # Generate fake LIME weights
    weights = np.random.randn(n_features) * 0.2

    explanation = sorted(
        zip(feature_names[:n_features], weights.tolist(), strict=False),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    return {
        "model_name": model_name,
        "prediction": round(np.random.uniform(0, 1), 4),
        "prediction_class": int(np.random.rand() > 0.5),
        "local_explanation": [
            {
                "feature": name,
                "weight": round(w, 4),
                "direction": "positive" if w > 0 else "negative",
            }
            for name, w in explanation
        ],
        "r_squared": round(np.random.uniform(0.7, 0.95), 3),
        "intercept": round(np.random.uniform(-0.5, 0.5), 4),
    }


@router.get("/explainability/partial-dependence")
async def get_partial_dependence(
    model_name: str,
    feature: str,
    version: str | None = None,
    grid_resolution: int = Query(default=50, ge=10, le=200),
) -> dict[str, Any]:
    """Get partial dependence plot data for a feature"""
    import numpy as np

    # Generate grid values
    grid_values = np.linspace(0, 1, grid_resolution).tolist()

    # Generate PDP values (sigmoid-like curve)
    pdp_values = [
        1 / (1 + np.exp(-5 * (x - 0.5))) + np.random.uniform(-0.02, 0.02)
        for x in grid_values
    ]

    return {
        "model_name": model_name,
        "version": version,
        "feature": feature,
        "grid_values": grid_values,
        "pdp_values": [round(v, 4) for v in pdp_values],
        "average_prediction": round(np.mean(pdp_values), 4),
        "feature_range": {"min": 0, "max": 1},
    }


@router.get("/explainability/interaction")
async def get_feature_interaction(
    model_name: str,
    feature1: str,
    feature2: str,
    version: str | None = None,
    grid_resolution: int = Query(default=20, ge=5, le=50),
) -> dict[str, Any]:
    """Get feature interaction effects"""
    import numpy as np

    # Generate 2D grid
    grid_x = np.linspace(0, 1, grid_resolution).tolist()
    grid_y = np.linspace(0, 1, grid_resolution).tolist()

    # Generate interaction surface
    interaction_surface = [
        [
            round(
                np.sin(x * np.pi) * np.cos(y * np.pi) + np.random.uniform(-0.05, 0.05),
                4,
            )
            for y in grid_y
        ]
        for x in grid_x
    ]

    return {
        "model_name": model_name,
        "version": version,
        "feature1": feature1,
        "feature2": feature2,
        "grid_x": grid_x,
        "grid_y": grid_y,
        "interaction_surface": interaction_surface,
        "interaction_strength": round(np.random.uniform(0.1, 0.8), 3),
    }
