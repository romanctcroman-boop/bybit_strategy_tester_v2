"""
Enhanced Model Registry with Validation Before Deployment

This module extends the ModelRegistry with proper validation
to prevent deploying bad models to production.

Audit Reference: docs/ML_SYSTEM_AUDIT_2026_01_28.md - P0 Issue #2
"""

from __future__ import annotations

import logging
import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

import numpy as np

from backend.ml.enhanced.model_registry import (
    ModelMetadata,
    ModelRegistry,
    ModelStatus,
    ModelVersion,
)

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of model validation."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationReport:
    """Report from model validation."""

    result: ValidationResult
    model_name: str
    model_version: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    score: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result": self.result.value,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "score": self.score,
            "timestamp": self.timestamp.isoformat(),
        }


class ModelValidator(Protocol):
    """Protocol for model validators."""

    def validate(
        self,
        model: Any,
        metadata: ModelMetadata,
        validation_data: Any | None = None,
    ) -> dict[str, Any]:
        """Validate a model."""
        ...


@dataclass
class ValidationConfig:
    """Configuration for model validation."""

    # Minimum performance thresholds
    min_sharpe_ratio: float | None = None
    min_accuracy: float | None = None
    min_precision: float | None = None
    min_recall: float | None = None
    min_f1: float | None = None
    min_auc: float | None = None

    # Maximum thresholds
    max_drawdown: float | None = None
    max_error_rate: float = 0.1

    # Required metrics
    required_metrics: list[str] = field(default_factory=list)

    # Sample size requirements
    min_training_samples: int = 100
    min_validation_samples: int = 50

    # Feature requirements
    min_feature_importance_coverage: float = 0.8  # Top features explain 80%+

    # Model size constraints
    max_model_size_mb: float = 100.0

    # Comparison with current production
    require_improvement: bool = False
    improvement_threshold: float = 0.05  # 5% improvement required

    # Custom validators
    custom_validators: list[ModelValidator] = field(default_factory=list)


class ValidatedModelRegistry(ModelRegistry):
    """
    Model Registry with validation before deployment.

    Solves the P0 issue where models can be deployed without
    proper validation, leading to bad predictions.

    Features:
        - Pre-deployment validation
        - Performance threshold checks
        - Comparison with production model
        - Drift detection integration
        - Validation reports

    Example:
        registry = ValidatedModelRegistry(
            storage_path="./models",
            validation_config=ValidationConfig(
                min_sharpe_ratio=1.0,
                max_drawdown=0.2,
                require_improvement=True,
            )
        )

        # Register model - runs validation
        registry.register_model(model, "price_predictor", "1.0.0")

        # Promote with validation
        report = registry.promote_with_validation(
            "price_predictor", "1.0.0", validation_data
        )

        if report.result == ValidationResult.PASSED:
            print("Model deployed!")
    """

    def __init__(
        self,
        storage_path: str = "./model_registry",
        validation_config: ValidationConfig | None = None,
        drift_detector: Any | None = None,
        alert_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        """
        Initialize validated model registry.

        Args:
            storage_path: Path for model storage
            validation_config: Validation configuration
            drift_detector: Optional ConceptDriftDetector instance
            alert_callback: Callback for validation alerts
        """
        super().__init__(storage_path)

        self.validation_config = validation_config or ValidationConfig()
        self.drift_detector = drift_detector
        self.alert_callback = alert_callback

        # Validation history
        self.validation_history: dict[str, list[ValidationReport]] = {}

    def validate_model(
        self,
        model: Any,
        name: str,
        version: str,
        metadata: ModelMetadata,
        validation_data: Any | None = None,
    ) -> ValidationReport:
        """
        Validate a model before deployment.

        Args:
            model: Model object
            name: Model name
            version: Model version
            metadata: Model metadata
            validation_data: Optional validation dataset

        Returns:
            ValidationReport with results
        """
        report = ValidationReport(
            result=ValidationResult.PASSED,
            model_name=name,
            model_version=version,
        )

        config = self.validation_config
        checks = []

        # Check 1: Training samples
        if metadata.training_samples < config.min_training_samples:
            report.errors.append(
                f"Insufficient training samples: {metadata.training_samples} < {config.min_training_samples}"
            )
            checks.append(
                {
                    "name": "training_samples",
                    "passed": False,
                    "value": metadata.training_samples,
                    "threshold": config.min_training_samples,
                }
            )
        else:
            checks.append(
                {
                    "name": "training_samples",
                    "passed": True,
                    "value": metadata.training_samples,
                }
            )

        # Check 2: Required metrics present
        for metric in config.required_metrics:
            if metric not in metadata.metrics:
                report.errors.append(f"Required metric missing: {metric}")
                checks.append(
                    {
                        "name": f"metric_{metric}",
                        "passed": False,
                        "error": "missing",
                    }
                )

        # Check 3: Performance thresholds
        threshold_checks = [
            ("sharpe_ratio", config.min_sharpe_ratio, ">="),
            ("accuracy", config.min_accuracy, ">="),
            ("precision", config.min_precision, ">="),
            ("recall", config.min_recall, ">="),
            ("f1", config.min_f1, ">="),
            ("auc", config.min_auc, ">="),
            ("max_drawdown", config.max_drawdown, "<="),
        ]

        for metric_name, threshold, op in threshold_checks:
            if threshold is None:
                continue

            value = metadata.metrics.get(metric_name)
            if value is None:
                value = metadata.validation_metrics.get(metric_name)

            if value is None:
                report.warnings.append(f"Metric {metric_name} not found for threshold check")
                continue

            if op == ">=" and value < threshold:
                report.errors.append(f"{metric_name} below threshold: {value:.4f} < {threshold:.4f}")
                checks.append(
                    {
                        "name": metric_name,
                        "passed": False,
                        "value": value,
                        "threshold": threshold,
                        "operator": op,
                    }
                )
            elif op == "<=" and value > threshold:
                report.errors.append(f"{metric_name} above threshold: {value:.4f} > {threshold:.4f}")
                checks.append(
                    {
                        "name": metric_name,
                        "passed": False,
                        "value": value,
                        "threshold": threshold,
                        "operator": op,
                    }
                )
            else:
                checks.append(
                    {
                        "name": metric_name,
                        "passed": True,
                        "value": value,
                        "threshold": threshold,
                    }
                )

        # Check 4: Model size
        model_size_mb = self._get_model_size(model)
        if model_size_mb > config.max_model_size_mb:
            report.warnings.append(f"Model size {model_size_mb:.1f}MB exceeds {config.max_model_size_mb}MB")
            checks.append(
                {
                    "name": "model_size",
                    "passed": False,
                    "value": model_size_mb,
                    "threshold": config.max_model_size_mb,
                }
            )
        else:
            checks.append(
                {
                    "name": "model_size",
                    "passed": True,
                    "value": model_size_mb,
                }
            )

        # Check 5: Feature importance coverage
        if metadata.feature_importance:
            sorted_importance = sorted(metadata.feature_importance.values(), reverse=True)
            total = sum(sorted_importance)
            if total > 0:
                cumsum = 0
                for _coverage_count, imp in enumerate(sorted_importance, 1):
                    cumsum += imp
                    if cumsum / total >= config.min_feature_importance_coverage:
                        break

                coverage_ratio = cumsum / total
                if coverage_ratio < config.min_feature_importance_coverage:
                    report.warnings.append(f"Feature importance coverage low: {coverage_ratio:.2%}")

        # Check 6: Comparison with production model
        if config.require_improvement:
            improvement_check = self._check_improvement(name, metadata)
            checks.append(improvement_check)
            if not improvement_check["passed"]:
                report.errors.append(
                    f"Model does not improve over production: "
                    f"{improvement_check.get('improvement', 0):.2%} < {config.improvement_threshold:.2%}"
                )

        # Check 7: Concept drift check
        if self.drift_detector and validation_data is not None:
            drift_check = self._check_drift(model, validation_data)
            checks.append(drift_check)
            if drift_check.get("drift_detected"):
                report.warnings.append(f"Concept drift detected: confidence={drift_check.get('confidence', 0):.2%}")

        # Check 8: Run custom validators
        for validator in config.custom_validators:
            try:
                custom_result = validator.validate(model, metadata, validation_data)
                checks.append(
                    {
                        "name": f"custom_{type(validator).__name__}",
                        **custom_result,
                    }
                )
                if not custom_result.get("passed", True):
                    report.errors.append(f"Custom validation failed: {custom_result.get('error', 'unknown')}")
            except Exception as e:
                report.warnings.append(f"Custom validator error: {e}")

        # Check 9: Validation on provided data
        if validation_data is not None:
            validation_check = self._validate_on_data(model, validation_data)
            checks.append(validation_check)
            if not validation_check["passed"]:
                report.errors.append(f"Validation failed: {validation_check.get('error', 'unknown')}")

        # Finalize report
        report.checks = checks
        passed_checks = sum(1 for c in checks if c.get("passed", True))
        report.score = passed_checks / len(checks) if checks else 1.0

        if report.errors:
            report.result = ValidationResult.FAILED
        elif report.warnings:
            report.result = ValidationResult.WARNING

        # Store in history
        model_key = f"{name}:{version}"
        if model_key not in self.validation_history:
            self.validation_history[model_key] = []
        self.validation_history[model_key].append(report)

        # Log and alert
        if report.result == ValidationResult.FAILED:
            logger.error(f"Model validation FAILED for {name}:{version}: {report.errors}")
            if self.alert_callback:
                self.alert_callback("model_validation_failed", report.to_dict())
        elif report.result == ValidationResult.WARNING:
            logger.warning(f"Model validation WARNING for {name}:{version}: {report.warnings}")
        else:
            logger.info(f"Model validation PASSED for {name}:{version}")

        return report

    def _get_model_size(self, model: Any) -> float:
        """Get model size in MB."""
        try:
            serialized = pickle.dumps(model)
            return len(serialized) / (1024 * 1024)
        except Exception:
            return 0.0

    def _check_improvement(
        self,
        name: str,
        metadata: ModelMetadata,
    ) -> dict[str, Any]:
        """Check if model improves over production."""
        prod_version = self.get_production_version(name)

        if prod_version is None:
            return {
                "name": "improvement_over_production",
                "passed": True,
                "note": "No production model to compare",
            }

        prod_model = self.models[name][prod_version]

        # Compare key metrics
        key_metric = "sharpe_ratio"  # Primary metric

        new_value = metadata.metrics.get(key_metric, 0)
        prod_value = prod_model.metadata.metrics.get(key_metric, 0)

        if prod_value == 0:
            return {
                "name": "improvement_over_production",
                "passed": True,
                "note": "Production model has no metrics",
            }

        improvement = (new_value - prod_value) / abs(prod_value)
        passed = improvement >= self.validation_config.improvement_threshold

        return {
            "name": "improvement_over_production",
            "passed": passed,
            "new_value": new_value,
            "prod_value": prod_value,
            "improvement": improvement,
            "threshold": self.validation_config.improvement_threshold,
        }

    def _check_drift(
        self,
        model: Any,
        validation_data: Any,
    ) -> dict[str, Any]:
        """Check for concept drift."""
        if self.drift_detector is None:
            return {
                "name": "drift_check",
                "passed": True,
                "note": "No drift detector configured",
            }

        try:
            # Assuming validation_data has features
            if hasattr(validation_data, "values"):
                data = validation_data.values.flatten()
            else:
                data = np.array(validation_data).flatten()

            result = self.drift_detector.detect(data)

            return {
                "name": "drift_check",
                "passed": not result.is_drift,
                "drift_detected": result.is_drift,
                "confidence": result.confidence,
                "drift_type": result.drift_type.value if result.drift_type else None,
            }
        except Exception as e:
            return {
                "name": "drift_check",
                "passed": True,
                "error": str(e),
            }

    def _validate_on_data(
        self,
        model: Any,
        validation_data: Any,
    ) -> dict[str, Any]:
        """Validate model on provided data."""
        try:
            # Check if model can make predictions
            if hasattr(model, "predict"):
                X = validation_data.values if hasattr(validation_data, "values") else validation_data

                predictions = model.predict(X)

                # Basic sanity checks
                if np.any(np.isnan(predictions)):
                    return {
                        "name": "validation_data",
                        "passed": False,
                        "error": "Model produces NaN predictions",
                    }

                if np.any(np.isinf(predictions)):
                    return {
                        "name": "validation_data",
                        "passed": False,
                        "error": "Model produces infinite predictions",
                    }

                return {
                    "name": "validation_data",
                    "passed": True,
                    "predictions_count": len(predictions),
                    "predictions_mean": float(np.mean(predictions)),
                    "predictions_std": float(np.std(predictions)),
                }

            return {
                "name": "validation_data",
                "passed": True,
                "note": "Model has no predict method",
            }
        except Exception as e:
            return {
                "name": "validation_data",
                "passed": False,
                "error": str(e),
            }

    def register_model(
        self,
        model: Any,
        name: str,
        version: str,
        metadata: ModelMetadata | None = None,
        initial_status: ModelStatus = ModelStatus.STAGING,
        validation_data: Any | None = None,
        skip_validation: bool = False,
    ) -> ModelVersion:
        """
        Register a new model with validation.

        Args:
            model: Model object
            name: Model name
            version: Model version
            metadata: Model metadata
            initial_status: Initial status
            validation_data: Optional validation data
            skip_validation: Skip validation (use with caution!)

        Returns:
            ModelVersion object

        Raises:
            ValueError: If validation fails (unless skip_validation=True)
        """
        if metadata is None:
            metadata = ModelMetadata(name=name, version=version)

        # Run validation
        if not skip_validation:
            report = self.validate_model(model, name, version, metadata, validation_data)

            if report.result == ValidationResult.FAILED:
                raise ValueError(f"Model validation failed: {report.errors}. Use skip_validation=True to bypass.")

        # Register with parent class
        return super().register_model(model, name, version, metadata, initial_status)

    def promote_with_validation(
        self,
        name: str,
        version: str,
        validation_data: Any | None = None,
        demote_current: bool = True,
    ) -> ValidationReport:
        """
        Promote model to production with validation.

        Args:
            name: Model name
            version: Version to promote
            validation_data: Validation data
            demote_current: Demote current production

        Returns:
            ValidationReport

        Raises:
            ValueError: If model not found or validation fails
        """
        if name not in self.models or version not in self.models[name]:
            raise ValueError(f"Model {name}:{version} not found")

        mv = self.models[name][version]
        model = self.load_model(name, version)

        # Run validation
        report = self.validate_model(model, name, version, mv.metadata, validation_data)

        if report.result == ValidationResult.FAILED:
            logger.error(f"Cannot promote {name}:{version}: validation failed")
            return report

        if report.result == ValidationResult.WARNING:
            logger.warning(f"Promoting {name}:{version} with warnings: {report.warnings}")

        # Promote
        self.promote_model(name, version, demote_current)

        return report

    def get_validation_history(
        self,
        name: str,
        version: str | None = None,
    ) -> list[ValidationReport]:
        """Get validation history for a model."""
        if version:
            key = f"{name}:{version}"
            return self.validation_history.get(key, [])

        # Return all versions
        results = []
        for key, reports in self.validation_history.items():
            if key.startswith(f"{name}:"):
                results.extend(reports)
        return results

    def get_validation_summary(self) -> dict[str, Any]:
        """Get summary of all validations."""
        total = 0
        passed = 0
        failed = 0
        warnings = 0

        for reports in self.validation_history.values():
            for report in reports:
                total += 1
                if report.result == ValidationResult.PASSED:
                    passed += 1
                elif report.result == ValidationResult.FAILED:
                    failed += 1
                elif report.result == ValidationResult.WARNING:
                    warnings += 1

        return {
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "pass_rate": passed / total if total > 0 else 1.0,
        }


# Factory function
def create_validated_registry(
    storage_path: str = "./model_registry",
    min_sharpe: float | None = 1.0,
    max_drawdown: float | None = 0.25,
    require_improvement: bool = False,
    drift_detector: Any | None = None,
) -> ValidatedModelRegistry:
    """
    Create a validated model registry with common defaults.

    Args:
        storage_path: Path for storage
        min_sharpe: Minimum Sharpe ratio
        max_drawdown: Maximum drawdown
        require_improvement: Require improvement over production
        drift_detector: Optional drift detector

    Returns:
        ValidatedModelRegistry instance
    """
    config = ValidationConfig(
        min_sharpe_ratio=min_sharpe,
        max_drawdown=max_drawdown,
        require_improvement=require_improvement,
        required_metrics=["sharpe_ratio", "total_return"],
    )

    return ValidatedModelRegistry(
        storage_path=storage_path,
        validation_config=config,
        drift_detector=drift_detector,
    )
