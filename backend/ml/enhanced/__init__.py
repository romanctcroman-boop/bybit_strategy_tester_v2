"""
Enhanced ML Module for Trading Strategy Optimization

This module provides advanced ML capabilities:
- Concept Drift Detection (statistical tests for distribution shifts)
- Model Registry (versioning, A/B testing, rollback)
- Auto-ML Pipeline (automated model selection and tuning)
- Online Learning (incremental model updates)
- Feature Store (centralized feature management)
- Drift Alert Manager (alert integration for drift detection)
- Persistent Feature Store (Redis-backed feature caching)
- Validated Model Registry (model validation before deployment)
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
from .drift_alert_manager import (
    AlertChannel,
    AlertSeverity,
    DriftAlertConfig,
    DriftAlertManager,
    EnhancedDriftAlert,
    IntegratedDriftMonitor,
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
from .persistent_feature_store import (
    PersistentFeatureStore,
    create_feature_store,
)
from .validated_model_registry import (
    ValidatedModelRegistry,
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    create_validated_registry,
)

__all__ = [
    "ABTest",
    "AlertChannel",
    "AlertSeverity",
    "AutoMLConfig",
    "AutoMLPipeline",
    "ConceptDriftDetector",
    "DriftAlert",
    "DriftAlertConfig",
    "DriftAlertManager",
    "DriftResult",
    "DriftType",
    "EnhancedDriftAlert",
    "FeatureDefinition",
    "FeatureGroup",
    "FeatureStore",
    "FeatureVersion",
    "IncrementalModel",
    "IntegratedDriftMonitor",
    "LearningStats",
    "ModelCandidate",
    "ModelMetadata",
    "ModelRegistry",
    "ModelStatus",
    "ModelVersion",
    "MultiVariateDriftDetector",
    "OnlineLearner",
    "PersistentFeatureStore",
    "PipelineResult",
    "UpdateStrategy",
    "ValidatedModelRegistry",
    "ValidationConfig",
    "ValidationReport",
    "ValidationResult",
    "create_feature_store",
    "create_validated_registry",
]
