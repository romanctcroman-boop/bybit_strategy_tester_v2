"""
Model Registry for ML Model Versioning and Management

Features:
- Model versioning with semantic versions
- A/B testing support
- Model metadata tracking
- Automatic rollback on degradation
- Model promotion workflow
"""

import hashlib
import json
import logging
import pickle
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model lifecycle status"""

    STAGING = "staging"  # Under evaluation
    PRODUCTION = "production"  # Active in production
    SHADOW = "shadow"  # Running alongside production
    ARCHIVED = "archived"  # No longer active
    FAILED = "failed"  # Failed validation


@dataclass
class ModelMetadata:
    """Metadata for a registered model"""

    name: str
    version: str
    description: str = ""
    algorithm: str = ""
    framework: str = "sklearn"

    # Training info
    training_data_hash: str = ""
    training_samples: int = 0
    training_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    training_duration_seconds: float = 0.0

    # Features
    feature_names: List[str] = field(default_factory=list)
    feature_importance: Dict[str, float] = field(default_factory=dict)

    # Performance metrics
    metrics: Dict[str, float] = field(default_factory=dict)
    validation_metrics: Dict[str, float] = field(default_factory=dict)

    # Environment
    python_version: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)

    # Custom tags
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "algorithm": self.algorithm,
            "framework": self.framework,
            "training_data_hash": self.training_data_hash,
            "training_samples": self.training_samples,
            "training_date": self.training_date.isoformat(),
            "training_duration_seconds": self.training_duration_seconds,
            "feature_names": self.feature_names,
            "feature_importance": self.feature_importance,
            "metrics": self.metrics,
            "validation_metrics": self.validation_metrics,
            "python_version": self.python_version,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary"""
        data = data.copy()
        if isinstance(data.get("training_date"), str):
            data["training_date"] = datetime.fromisoformat(data["training_date"])
        return cls(**data)


@dataclass
class ModelVersion:
    """A specific version of a model"""

    model_id: str
    version: str
    status: ModelStatus
    metadata: ModelMetadata
    artifact_path: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Performance tracking
    production_metrics: Dict[str, float] = field(default_factory=dict)
    prediction_count: int = 0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "model_id": self.model_id,
            "version": self.version,
            "status": self.status.value,
            "metadata": self.metadata.to_dict(),
            "artifact_path": self.artifact_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "production_metrics": self.production_metrics,
            "prediction_count": self.prediction_count,
            "error_count": self.error_count,
        }


@dataclass
class ABTest:
    """A/B test configuration"""

    test_id: str
    name: str
    model_a: str  # model_id:version
    model_b: str  # model_id:version
    traffic_split: float  # Fraction of traffic to model_b
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None

    # Metrics
    model_a_predictions: int = 0
    model_b_predictions: int = 0
    model_a_metrics: Dict[str, float] = field(default_factory=dict)
    model_b_metrics: Dict[str, float] = field(default_factory=dict)

    # Status
    is_active: bool = True
    winner: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "model_a": self.model_a,
            "model_b": self.model_b,
            "traffic_split": self.traffic_split,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "model_a_predictions": self.model_a_predictions,
            "model_b_predictions": self.model_b_predictions,
            "model_a_metrics": self.model_a_metrics,
            "model_b_metrics": self.model_b_metrics,
            "is_active": self.is_active,
            "winner": self.winner,
        }


class ModelRegistry:
    """
    Central registry for ML model management

    Example:
        registry = ModelRegistry("./models")

        # Register a new model
        version = registry.register_model(
            model=trained_model,
            name="price_predictor",
            version="1.0.0",
            metadata=ModelMetadata(name="price_predictor", version="1.0.0")
        )

        # Promote to production
        registry.promote_model("price_predictor", "1.0.0")

        # Load production model
        model = registry.load_model("price_predictor")
    """

    def __init__(self, storage_path: str = "./model_registry"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory indices
        self.models: Dict[str, Dict[str, ModelVersion]] = {}  # name -> version -> model
        self.ab_tests: Dict[str, ABTest] = {}

        # Load existing models
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from disk"""
        index_path = self.storage_path / "registry_index.json"
        if index_path.exists():
            try:
                with open(index_path, "r") as f:
                    data = json.load(f)

                for name, versions in data.get("models", {}).items():
                    self.models[name] = {}
                    for version, model_data in versions.items():
                        model_data["status"] = ModelStatus(model_data["status"])
                        model_data["metadata"] = ModelMetadata.from_dict(
                            model_data["metadata"]
                        )
                        model_data["created_at"] = datetime.fromisoformat(
                            model_data["created_at"]
                        )
                        model_data["updated_at"] = datetime.fromisoformat(
                            model_data["updated_at"]
                        )
                        self.models[name][version] = ModelVersion(**model_data)

                logger.info(f"Loaded {len(self.models)} models from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self) -> None:
        """Save registry to disk"""
        index_path = self.storage_path / "registry_index.json"

        data = {
            "models": {
                name: {version: mv.to_dict() for version, mv in versions.items()}
                for name, versions in self.models.items()
            },
            "ab_tests": {
                test_id: test.to_dict() for test_id, test in self.ab_tests.items()
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)

    def register_model(
        self,
        model: Any,
        name: str,
        version: str,
        metadata: Optional[ModelMetadata] = None,
        initial_status: ModelStatus = ModelStatus.STAGING,
    ) -> ModelVersion:
        """
        Register a new model version

        Args:
            model: Trained model object (must be picklable)
            name: Model name
            version: Semantic version (e.g., "1.0.0")
            metadata: Optional metadata
            initial_status: Initial model status

        Returns:
            ModelVersion object
        """
        model_id = f"{name}:{version}"

        # Create model directory
        model_dir = self.storage_path / name / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model artifact
        artifact_path = model_dir / "model.pkl"
        with open(artifact_path, "wb") as f:
            pickle.dump(model, f)

        # Create metadata if not provided
        if metadata is None:
            metadata = ModelMetadata(name=name, version=version)

        # Create version entry
        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            status=initial_status,
            metadata=metadata,
            artifact_path=str(artifact_path),
        )

        # Store in registry
        if name not in self.models:
            self.models[name] = {}
        self.models[name][version] = model_version

        # Save metadata
        meta_path = model_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        self._save_registry()

        logger.info(f"Registered model {model_id} with status {initial_status.value}")
        return model_version

    def load_model(self, name: str, version: Optional[str] = None) -> Any:
        """
        Load a model from registry

        Args:
            name: Model name
            version: Optional version (defaults to production version)

        Returns:
            Loaded model object
        """
        if version is None:
            # Find production version
            version = self.get_production_version(name)
            if version is None:
                raise ValueError(f"No production version found for {name}")

        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        model_version = self.models[name][version]

        with open(model_version.artifact_path, "rb") as f:
            model = pickle.load(f)

        logger.info(f"Loaded model {name}:{version}")
        return model

    def get_production_version(self, name: str) -> Optional[str]:
        """Get the production version of a model"""
        if name not in self.models:
            return None

        for version, mv in self.models[name].items():
            if mv.status == ModelStatus.PRODUCTION:
                return version
        return None

    def promote_model(
        self, name: str, version: str, demote_current: bool = True
    ) -> None:
        """
        Promote a model version to production

        Args:
            name: Model name
            version: Version to promote
            demote_current: Whether to archive current production version
        """
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        # Demote current production if exists
        if demote_current:
            current_prod = self.get_production_version(name)
            if current_prod and current_prod != version:
                self.models[name][current_prod].status = ModelStatus.ARCHIVED
                self.models[name][current_prod].updated_at = datetime.now(timezone.utc)

        # Promote new version
        self.models[name][version].status = ModelStatus.PRODUCTION
        self.models[name][version].updated_at = datetime.now(timezone.utc)

        self._save_registry()
        logger.info(f"Promoted {name}:{version} to production")

    def rollback(self, name: str, to_version: Optional[str] = None) -> str:
        """
        Rollback to a previous version

        Args:
            name: Model name
            to_version: Version to rollback to (or latest archived)

        Returns:
            Version that was activated
        """
        if name not in self.models:
            raise ValueError(f"Model {name} not found")

        # Find version to rollback to
        if to_version is None:
            # Find latest archived version
            archived = [
                (v, mv)
                for v, mv in self.models[name].items()
                if mv.status == ModelStatus.ARCHIVED
            ]
            if not archived:
                raise ValueError(f"No archived versions for {name}")

            # Sort by date
            archived.sort(key=lambda x: x[1].updated_at, reverse=True)
            to_version = archived[0][0]

        # Perform rollback
        self.promote_model(name, to_version, demote_current=True)

        logger.info(f"Rolled back {name} to version {to_version}")
        return to_version

    def create_ab_test(
        self,
        name: str,
        model_a: str,  # "model_name:version"
        model_b: str,
        traffic_split: float = 0.5,
    ) -> ABTest:
        """
        Create an A/B test between two model versions

        Args:
            name: Test name
            model_a: Control model (format: "name:version")
            model_b: Treatment model
            traffic_split: Fraction of traffic to model_b
        """
        test_id = f"ab_{hashlib.md5(f'{model_a}{model_b}{datetime.now(timezone.utc)}'.encode()).hexdigest()[:8]}"

        ab_test = ABTest(
            test_id=test_id,
            name=name,
            model_a=model_a,
            model_b=model_b,
            traffic_split=traffic_split,
        )

        self.ab_tests[test_id] = ab_test
        self._save_registry()

        logger.info(f"Created A/B test {test_id}: {model_a} vs {model_b}")
        return ab_test

    def get_ab_model(self, test_id: str) -> str:
        """
        Get model to use for A/B test (random selection based on split)

        Returns:
            Model identifier (name:version)
        """
        if test_id not in self.ab_tests:
            raise ValueError(f"A/B test {test_id} not found")

        test = self.ab_tests[test_id]
        if not test.is_active:
            raise ValueError(f"A/B test {test_id} is not active")

        if np.random.random() < test.traffic_split:
            test.model_b_predictions += 1
            return test.model_b
        else:
            test.model_a_predictions += 1
            return test.model_a

    def record_ab_outcome(
        self, test_id: str, model: str, metric_name: str, value: float
    ) -> None:
        """Record outcome for A/B test"""
        if test_id not in self.ab_tests:
            return

        test = self.ab_tests[test_id]

        if model == test.model_a:
            if metric_name not in test.model_a_metrics:
                test.model_a_metrics[metric_name] = []
            test.model_a_metrics[metric_name].append(value)
        else:
            if metric_name not in test.model_b_metrics:
                test.model_b_metrics[metric_name] = []
            test.model_b_metrics[metric_name].append(value)

    def evaluate_ab_test(self, test_id: str) -> Dict[str, Any]:
        """
        Evaluate A/B test results

        Returns:
            Dict with statistical analysis
        """
        if test_id not in self.ab_tests:
            raise ValueError(f"A/B test {test_id} not found")

        test = self.ab_tests[test_id]

        results = {
            "test_id": test_id,
            "model_a": test.model_a,
            "model_b": test.model_b,
            "model_a_predictions": test.model_a_predictions,
            "model_b_predictions": test.model_b_predictions,
            "metrics_comparison": {},
        }

        # Compare metrics
        all_metrics = set(test.model_a_metrics.keys()) | set(
            test.model_b_metrics.keys()
        )

        for metric in all_metrics:
            a_values = test.model_a_metrics.get(metric, [])
            b_values = test.model_b_metrics.get(metric, [])

            if len(a_values) < 30 or len(b_values) < 30:
                results["metrics_comparison"][metric] = {
                    "status": "insufficient_data",
                    "model_a_count": len(a_values),
                    "model_b_count": len(b_values),
                }
                continue

            # Statistical test
            from scipy import stats

            t_stat, p_value = stats.ttest_ind(a_values, b_values)

            a_mean = np.mean(a_values)
            b_mean = np.mean(b_values)
            improvement = (b_mean - a_mean) / (abs(a_mean) + 1e-10) * 100

            results["metrics_comparison"][metric] = {
                "model_a_mean": float(a_mean),
                "model_b_mean": float(b_mean),
                "improvement_pct": float(improvement),
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "significant": p_value < 0.05,
                "winner": "model_b"
                if b_mean > a_mean and p_value < 0.05
                else (
                    "model_a" if a_mean > b_mean and p_value < 0.05 else "inconclusive"
                ),
            }

        return results

    def list_models(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered models"""
        result = []

        models_to_list = {name: self.models[name]} if name else self.models

        for model_name, versions in models_to_list.items():
            for version, mv in versions.items():
                result.append(
                    {
                        "name": model_name,
                        "version": version,
                        "status": mv.status.value,
                        "created_at": mv.created_at.isoformat(),
                        "metrics": mv.metadata.metrics,
                        "prediction_count": mv.prediction_count,
                    }
                )

        return result

    def delete_model(self, name: str, version: str) -> bool:
        """Delete a model version"""
        if name not in self.models or version not in self.models[name]:
            return False

        mv = self.models[name][version]

        # Don't allow deleting production models
        if mv.status == ModelStatus.PRODUCTION:
            raise ValueError("Cannot delete production model. Demote first.")

        # Delete files
        model_dir = self.storage_path / name / version
        if model_dir.exists():
            shutil.rmtree(model_dir)

        # Remove from registry
        del self.models[name][version]
        if not self.models[name]:
            del self.models[name]

        self._save_registry()

        logger.info(f"Deleted model {name}:{version}")
        return True

    def get_model_metrics(
        self, name: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get performance metrics for a model"""
        if version is None:
            version = self.get_production_version(name)

        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        mv = self.models[name][version]

        return {
            "model_id": mv.model_id,
            "status": mv.status.value,
            "training_metrics": mv.metadata.metrics,
            "validation_metrics": mv.metadata.validation_metrics,
            "production_metrics": mv.production_metrics,
            "prediction_count": mv.prediction_count,
            "error_count": mv.error_count,
            "error_rate": mv.error_count / max(mv.prediction_count, 1),
        }

    def update_production_metrics(self, name: str, metrics: Dict[str, float]) -> None:
        """Update production metrics for the production model"""
        version = self.get_production_version(name)
        if version is None:
            return

        mv = self.models[name][version]
        mv.production_metrics.update(metrics)
        mv.prediction_count += 1
        mv.updated_at = datetime.now(timezone.utc)

        # Periodic save
        if mv.prediction_count % 100 == 0:
            self._save_registry()

    def check_degradation(
        self, name: str, threshold: float = 0.1
    ) -> Optional[Dict[str, Any]]:
        """
        Check if production model has degraded

        Args:
            name: Model name
            threshold: Degradation threshold (fraction)

        Returns:
            Degradation info if detected, None otherwise
        """
        version = self.get_production_version(name)
        if version is None:
            return None

        mv = self.models[name][version]

        # Compare validation vs production metrics
        degraded_metrics = []

        for metric, val_value in mv.metadata.validation_metrics.items():
            prod_value = mv.production_metrics.get(metric)
            if prod_value is None:
                continue

            # Calculate degradation
            degradation = (val_value - prod_value) / (abs(val_value) + 1e-10)

            if degradation > threshold:
                degraded_metrics.append(
                    {
                        "metric": metric,
                        "validation_value": val_value,
                        "production_value": prod_value,
                        "degradation_pct": degradation * 100,
                    }
                )

        if degraded_metrics:
            return {
                "model_id": mv.model_id,
                "degraded": True,
                "metrics": degraded_metrics,
                "recommendation": "Consider rollback or retraining",
            }

        return None
