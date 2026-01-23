"""
Enhanced ML Module for Trading Strategy Optimization

This module provides advanced ML capabilities:
- Concept Drift Detection (statistical tests for distribution shifts)
- Model Registry (versioning, A/B testing, rollback)
- Auto-ML Pipeline (automated model selection and tuning)
- Online Learning (incremental model updates)
- Feature Store (centralized feature management)
"""

from .automl_pipeline import (
    AutoMLConfig,
    AutoMLPipeline,
    ModelCandidate,
    PipelineResult,
)
from .concept_drift import (
    ConceptDriftDetector,
    DriftAlert,
    DriftResult,
    DriftType,
    MultiVariateDriftDetector,
)
from .feature_store import (
    FeatureDefinition,
    FeatureGroup,
    FeatureStore,
    FeatureVersion,
)
from .model_registry import (
    ABTest,
    ModelMetadata,
    ModelRegistry,
    ModelStatus,
    ModelVersion,
)
from .online_learner import (
    IncrementalModel,
    LearningStats,
    OnlineLearner,
    UpdateStrategy,
)

__all__ = [
    # Concept Drift
    "ConceptDriftDetector",
    "DriftType",
    "DriftResult",
    "DriftAlert",
    "MultiVariateDriftDetector",
    # Model Registry
    "ModelRegistry",
    "ModelVersion",
    "ModelMetadata",
    "ModelStatus",
    "ABTest",
    # Auto-ML
    "AutoMLPipeline",
    "AutoMLConfig",
    "ModelCandidate",
    "PipelineResult",
    # Online Learning
    "OnlineLearner",
    "IncrementalModel",
    "UpdateStrategy",
    "LearningStats",
    # Feature Store
    "FeatureStore",
    "FeatureDefinition",
    "FeatureGroup",
    "FeatureVersion",
]
