"""
MLflow Integration Adapter.

This module provides integration with MLflow for experiment tracking,
model versioning, and model registry.

Audit Task: P2 - MLflow Integration
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import mlflow

logger = logging.getLogger(__name__)

# Try to import mlflow, fall back gracefully
try:
    import mlflow
    from mlflow.tracking import MlflowClient

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None  # type: ignore
    MlflowClient = None  # type: ignore


@dataclass
class ExperimentConfig:
    """MLflow experiment configuration."""

    name: str
    tracking_uri: str = "http://localhost:5000"
    artifact_location: str | None = None
    tags: dict[str, str] | None = None


@dataclass
class ModelVersion:
    """Model version information."""

    name: str
    version: str
    stage: str
    source: str
    run_id: str
    created_at: datetime | None = None
    description: str | None = None


class MLflowAdapter:
    """
    MLflow integration adapter for experiment tracking and model registry.

    Features:
    - Experiment tracking with auto-logging
    - Model versioning and staging
    - Metric and parameter logging
    - Artifact storage
    - Model registry integration

    Usage:
        adapter = MLflowAdapter()
        adapter.set_experiment("backtest_optimization")

        with adapter.start_run(run_name="rsi_optimization"):
            adapter.log_params({"period": 14, "overbought": 70})
            adapter.log_metrics({"sharpe": 1.5, "profit": 0.25})
            adapter.log_model(model, "strategy_model")
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        registry_uri: str | None = None,
    ):
        """
        Initialize MLflow adapter.

        Args:
            tracking_uri: MLflow tracking server URI
            registry_uri: Model registry URI (optional, uses tracking_uri if not set)
        """
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        self.registry_uri = registry_uri or self.tracking_uri
        self._client: Any = None
        self._initialized = False

        if not MLFLOW_AVAILABLE:
            logger.warning(
                "mlflow library not installed. MLflow integration disabled. Install with: pip install mlflow"
            )
        else:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize MLflow connection."""
        if not MLFLOW_AVAILABLE:
            return

        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            if self.registry_uri != self.tracking_uri:
                mlflow.set_registry_uri(self.registry_uri)

            self._client = MlflowClient(tracking_uri=self.tracking_uri)
            self._initialized = True
            logger.info(f"Connected to MLflow at {self.tracking_uri}")
        except Exception as e:
            logger.warning(f"Failed to connect to MLflow: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if MLflow is available."""
        return MLFLOW_AVAILABLE and self._initialized

    def set_experiment(
        self,
        name: str,
        artifact_location: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        """
        Set or create an experiment.

        Args:
            name: Experiment name
            artifact_location: Artifact storage location
            tags: Experiment tags

        Returns:
            Experiment ID or None if failed
        """
        if not self.is_available:
            logger.debug(f"MLflow unavailable, skipping experiment: {name}")
            return None

        try:
            experiment = mlflow.set_experiment(
                experiment_name=name,
                artifact_location=artifact_location,
            )

            if tags:
                for key, value in tags.items():
                    mlflow.set_experiment_tag(key, value)

            logger.info(f"Set experiment: {name} (ID: {experiment.experiment_id})")
            return experiment.experiment_id
        except Exception as e:
            logger.warning(f"Failed to set experiment '{name}': {e}")
            return None

    def start_run(
        self,
        run_name: str | None = None,
        nested: bool = False,
        tags: dict[str, str] | None = None,
        description: str | None = None,
    ) -> Any:
        """
        Start a new MLflow run.

        Args:
            run_name: Run name
            nested: Whether this is a nested run
            tags: Run tags
            description: Run description

        Returns:
            MLflow run context manager or dummy context
        """
        if not self.is_available:
            return _DummyRunContext()

        try:
            run = mlflow.start_run(run_name=run_name, nested=nested, tags=tags)

            if description:
                mlflow.set_tag("mlflow.note.content", description)

            return run
        except Exception as e:
            logger.warning(f"Failed to start run: {e}")
            return _DummyRunContext()

    def end_run(self, status: str = "FINISHED") -> None:
        """End the current run."""
        if not self.is_available:
            return

        try:
            mlflow.end_run(status=status)
        except Exception as e:
            logger.warning(f"Failed to end run: {e}")

    def log_param(self, key: str, value: Any) -> None:
        """Log a single parameter."""
        if not self.is_available:
            return

        try:
            mlflow.log_param(key, value)
        except Exception as e:
            logger.debug(f"Failed to log param '{key}': {e}")

    def log_params(self, params: dict[str, Any]) -> None:
        """Log multiple parameters."""
        if not self.is_available:
            return

        try:
            mlflow.log_params(params)
        except Exception as e:
            logger.debug(f"Failed to log params: {e}")

    def log_metric(self, key: str, value: float, step: int | None = None) -> None:
        """Log a single metric."""
        if not self.is_available:
            return

        try:
            mlflow.log_metric(key, value, step=step)
        except Exception as e:
            logger.debug(f"Failed to log metric '{key}': {e}")

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log multiple metrics."""
        if not self.is_available:
            return

        try:
            mlflow.log_metrics(metrics, step=step)
        except Exception as e:
            logger.debug(f"Failed to log metrics: {e}")

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        """Log an artifact file."""
        if not self.is_available:
            return

        try:
            mlflow.log_artifact(local_path, artifact_path)
        except Exception as e:
            logger.warning(f"Failed to log artifact '{local_path}': {e}")

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """
        Log a model to MLflow.

        Args:
            model: Model object (sklearn, pytorch, etc.)
            artifact_path: Path within artifacts
            registered_model_name: Name for model registry
            **kwargs: Additional arguments for model logging

        Returns:
            Model URI or None
        """
        if not self.is_available:
            return None

        try:
            # Detect model type and use appropriate logger
            model_info = self._log_model_by_type(model, artifact_path, registered_model_name, **kwargs)
            return model_info.model_uri if model_info else None
        except Exception as e:
            logger.warning(f"Failed to log model: {e}")
            return None

    def _log_model_by_type(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: str | None,
        **kwargs: Any,
    ) -> Any:
        """Log model based on its type."""
        model_type = type(model).__module__.split(".")[0]

        if model_type == "sklearn":
            return mlflow.sklearn.log_model(model, artifact_path, registered_model_name=registered_model_name, **kwargs)
        elif model_type == "xgboost":
            return mlflow.xgboost.log_model(model, artifact_path, registered_model_name=registered_model_name, **kwargs)
        elif model_type == "lightgbm":
            return mlflow.lightgbm.log_model(
                model, artifact_path, registered_model_name=registered_model_name, **kwargs
            )
        elif model_type in ("torch", "pytorch"):
            return mlflow.pytorch.log_model(model, artifact_path, registered_model_name=registered_model_name, **kwargs)
        else:
            # Generic model logging
            return mlflow.pyfunc.log_model(
                artifact_path, python_model=model, registered_model_name=registered_model_name
            )

    def load_model(self, model_uri: str) -> Any:
        """
        Load a model from MLflow.

        Args:
            model_uri: Model URI (e.g., "models:/MyModel/1")

        Returns:
            Loaded model or None
        """
        if not self.is_available:
            return None

        try:
            return mlflow.pyfunc.load_model(model_uri)
        except Exception as e:
            logger.warning(f"Failed to load model '{model_uri}': {e}")
            return None

    def transition_model_stage(
        self,
        name: str,
        version: str,
        stage: str,
        archive_existing: bool = True,
    ) -> bool:
        """
        Transition a model version to a new stage.

        Args:
            name: Model name
            version: Model version
            stage: Target stage (Staging, Production, Archived)
            archive_existing: Archive existing models in target stage

        Returns:
            True if successful
        """
        if not self.is_available or not self._client:
            return False

        try:
            self._client.transition_model_version_stage(
                name=name,
                version=version,
                stage=stage,
                archive_existing_versions=archive_existing,
            )
            logger.info(f"Model {name} v{version} transitioned to {stage}")
            return True
        except Exception as e:
            logger.warning(f"Failed to transition model stage: {e}")
            return False

    def get_latest_model_version(self, name: str, stages: list[str] | None = None) -> ModelVersion | None:
        """
        Get the latest version of a registered model.

        Args:
            name: Model name
            stages: Filter by stages (e.g., ["Production", "Staging"])

        Returns:
            ModelVersion or None
        """
        if not self.is_available or not self._client:
            return None

        try:
            versions = self._client.get_latest_versions(name, stages=stages)
            if versions:
                v = versions[0]
                return ModelVersion(
                    name=v.name,
                    version=v.version,
                    stage=v.current_stage,
                    source=v.source,
                    run_id=v.run_id,
                    description=v.description,
                )
            return None
        except Exception as e:
            logger.warning(f"Failed to get model version: {e}")
            return None

    def search_runs(
        self,
        experiment_ids: list[str] | None = None,
        filter_string: str = "",
        max_results: int = 100,
        order_by: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for runs matching criteria.

        Args:
            experiment_ids: Experiment IDs to search
            filter_string: MLflow search filter
            max_results: Maximum results to return
            order_by: Ordering (e.g., ["metrics.accuracy DESC"])

        Returns:
            List of run dictionaries
        """
        if not self.is_available:
            return []

        try:
            runs = mlflow.search_runs(
                experiment_ids=experiment_ids,
                filter_string=filter_string,
                max_results=max_results,
                order_by=order_by,
            )
            return runs.to_dict("records") if hasattr(runs, "to_dict") else []
        except Exception as e:
            logger.warning(f"Failed to search runs: {e}")
            return []


class _DummyRunContext:
    """Dummy context manager when MLflow is unavailable."""

    def __enter__(self) -> _DummyRunContext:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


# Singleton instance
_mlflow_adapter: MLflowAdapter | None = None


def get_mlflow_adapter() -> MLflowAdapter:
    """Get singleton MLflow adapter instance."""
    global _mlflow_adapter
    if _mlflow_adapter is None:
        _mlflow_adapter = MLflowAdapter()
    return _mlflow_adapter
