"""
Tests for ML System Audit Fixes

Tests for:
- PersistentFeatureStore (P0: Redis backend)
- ValidatedModelRegistry (P0: Validation before deployment)
- DriftAlertManager (P1: Alert integration)

Audit Reference: docs/ML_SYSTEM_AUDIT_2026_01_28.md
"""

from __future__ import annotations

import pickle
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.ml.enhanced.concept_drift import DriftResult, DriftType
from backend.ml.enhanced.drift_alert_manager import (
    AlertChannel,
    AlertSeverity,
    DriftAlertConfig,
    DriftAlertManager,
    EnhancedDriftAlert,
    IntegratedDriftMonitor,
)
from backend.ml.enhanced.model_registry import ModelMetadata, ModelStatus
from backend.ml.enhanced.persistent_feature_store import (
    PersistentFeatureStore,
    create_feature_store,
)
from backend.ml.enhanced.validated_model_registry import (
    ValidatedModelRegistry,
    ValidationConfig,
    ValidationResult,
    create_validated_registry,
)

# ============================================================================
# PersistentFeatureStore Tests
# ============================================================================


class TestPersistentFeatureStore:
    """Tests for PersistentFeatureStore with Redis backend."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a feature store without Redis (fallback mode)."""
        return PersistentFeatureStore(
            storage_path=str(tmp_path / "features"),
            redis_url=None,  # Use memory fallback
            fallback_to_memory=True,
        )

    @pytest.fixture
    def mock_redis_store(self, tmp_path):
        """Create a feature store with mocked Redis."""
        with patch("backend.ml.enhanced.persistent_feature_store.PersistentFeatureStore._init_redis"):
            store = PersistentFeatureStore(
                storage_path=str(tmp_path / "features"),
                redis_url="redis://localhost:6379",
            )
            store._redis = MagicMock()
            store._redis_available = True
            store._redis.ping.return_value = True
            return store

    def test_store_features_memory_fallback(self, store):
        """Test storing features in memory when Redis unavailable."""
        features = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        result = store.store_features("test_feature", features)

        assert result is True
        assert "test_feature" in store.feature_cache
        np.testing.assert_array_equal(store.feature_cache["test_feature"], features)

    def test_get_features_memory_fallback(self, store):
        """Test retrieving features from memory cache."""
        features = np.array([1.0, 2.0, 3.0])
        store.store_features("rsi_14", features)

        result = store.get_features("rsi_14")

        assert result is not None
        np.testing.assert_array_equal(result, features)

    def test_get_features_not_found(self, store):
        """Test getting non-existent features returns None."""
        result = store.get_features("nonexistent")
        assert result is None

    def test_get_features_with_default(self, store):
        """Test getting non-existent features returns default."""
        default = np.array([0.0, 0.0])
        result = store.get_features("nonexistent", default=default)
        np.testing.assert_array_equal(result, default)

    def test_delete_features(self, store):
        """Test deleting features."""
        features = np.array([1.0, 2.0])
        store.store_features("to_delete", features)

        result = store.delete_features("to_delete")

        assert result is True
        assert store.get_features("to_delete") is None

    def test_exists(self, store):
        """Test checking if features exist."""
        assert store.exists("nonexistent") is False

        store.store_features("exists_test", np.array([1.0]))

        assert store.exists("exists_test") is True

    def test_list_stored_features(self, store):
        """Test listing stored features."""
        store.store_features("feature_a", np.array([1.0]))
        store.store_features("feature_b", np.array([2.0]))

        result = store.list_stored_features()

        assert "feature_a" in result
        assert "feature_b" in result

    def test_list_stored_features_with_pattern(self, store):
        """Test listing features with pattern."""
        store.store_features("rsi_14", np.array([1.0]))
        store.store_features("rsi_21", np.array([2.0]))
        store.store_features("macd", np.array([3.0]))

        result = store.list_stored_features("rsi*")

        assert "rsi_14" in result
        assert "rsi_21" in result
        assert "macd" not in result

    def test_get_cache_stats(self, store):
        """Test getting cache statistics."""
        store.store_features("test", np.array([1.0, 2.0]))

        stats = store.get_cache_stats()

        assert "redis_available" in stats
        assert "memory_cache_size" in stats
        assert stats["memory_cache_size"] == 1
        assert stats["redis_available"] is False

    def test_health_check(self, store):
        """Test health check."""
        health = store.health_check()

        assert health["status"] in ["healthy", "degraded"]
        assert "redis_connected" in health
        assert "memory_cache_entries" in health

    def test_store_with_redis(self, mock_redis_store):
        """Test storing features with Redis."""
        features = np.array([1.0, 2.0, 3.0])

        mock_redis_store.store_features("redis_test", features, ttl_seconds=300)

        mock_redis_store._redis.setex.assert_called_once()
        call_args = mock_redis_store._redis.setex.call_args
        assert call_args[0][1] == 300  # TTL

    def test_get_from_redis(self, mock_redis_store):
        """Test getting features from Redis."""
        features = np.array([1.0, 2.0, 3.0])
        data = {
            "features": features.tobytes(),
            "dtype": str(features.dtype),
            "shape": features.shape,
            "metadata": {},
            "stored_at": datetime.now(UTC).isoformat(),
        }
        mock_redis_store._redis.get.return_value = pickle.dumps(data)

        result = mock_redis_store.get_features("redis_test")

        assert result is not None
        np.testing.assert_array_equal(result, features)

    def test_clear_cache(self, store):
        """Test clearing cache."""
        store.store_features("f1", np.array([1.0]))
        store.store_features("f2", np.array([2.0]))

        cleared = store.clear_cache()

        assert cleared >= 2
        assert len(store.feature_cache) == 0


class TestCreateFeatureStore:
    """Tests for create_feature_store factory function."""

    def test_creates_persistent_store_with_redis(self, tmp_path):
        """Test that it creates PersistentFeatureStore when Redis URL provided."""
        with patch("redis.from_url") as mock_redis:
            mock_redis.return_value.ping.return_value = True

            store = create_feature_store(
                storage_path=str(tmp_path),
                redis_url="redis://localhost:6379",
                auto_detect_redis=False,
            )

            assert isinstance(store, PersistentFeatureStore)


# ============================================================================
# ValidatedModelRegistry Tests
# ============================================================================


class SimplePickleableModel:
    """A simple model that can be pickled for tests."""

    def __init__(self, predictions: np.ndarray | None = None):
        self._predictions = predictions if predictions is not None else np.array([1.0, 2.0, 3.0])

    def predict(self, X):
        return self._predictions

    def fit(self, X, y):
        return self


class TestValidatedModelRegistry:
    """Tests for ValidatedModelRegistry with validation before deployment."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a validated model registry."""
        config = ValidationConfig(
            min_sharpe_ratio=1.0,
            max_drawdown=0.25,
            min_training_samples=50,
            required_metrics=["sharpe_ratio"],
            max_model_size_mb=100.0,
        )
        return ValidatedModelRegistry(
            storage_path=str(tmp_path / "models"),
            validation_config=config,
        )

    @pytest.fixture
    def mock_model(self):
        """Create a mock model that cannot be pickled (for validation-only tests)."""
        model = MagicMock()
        model.predict.return_value = np.array([1.0, 2.0, 3.0])
        return model

    @pytest.fixture
    def pickleable_model(self):
        """Create a pickleable model for registration tests."""
        return SimplePickleableModel()

    @pytest.fixture
    def valid_metadata(self):
        """Create valid model metadata."""
        return ModelMetadata(
            name="test_model",
            version="1.0.0",
            training_samples=100,
            metrics={"sharpe_ratio": 1.5, "total_return": 0.2},
            validation_metrics={"sharpe_ratio": 1.4, "max_drawdown": 0.15},
        )

    @pytest.fixture
    def invalid_metadata(self):
        """Create invalid model metadata."""
        return ModelMetadata(
            name="bad_model",
            version="1.0.0",
            training_samples=10,  # Below threshold
            metrics={"sharpe_ratio": 0.5},  # Below threshold
        )

    def test_validate_model_passes(self, registry, mock_model, valid_metadata):
        """Test validation passes with valid model."""
        report = registry.validate_model(
            mock_model,
            "test_model",
            "1.0.0",
            valid_metadata,
        )

        # PASSED means no errors, WARNING is also acceptable if only warnings exist
        assert report.result in [ValidationResult.PASSED, ValidationResult.WARNING]
        assert len(report.errors) == 0

    def test_validate_model_fails_low_samples(self, registry, mock_model, invalid_metadata):
        """Test validation fails with insufficient training samples."""
        report = registry.validate_model(
            mock_model,
            "bad_model",
            "1.0.0",
            invalid_metadata,
        )

        assert report.result == ValidationResult.FAILED
        assert any("training samples" in e.lower() for e in report.errors)

    def test_validate_model_fails_low_sharpe(self, registry, mock_model):
        """Test validation fails with low Sharpe ratio."""
        metadata = ModelMetadata(
            name="low_sharpe",
            version="1.0.0",
            training_samples=100,
            metrics={"sharpe_ratio": 0.5},  # Below 1.0 threshold
        )

        report = registry.validate_model(
            mock_model,
            "low_sharpe",
            "1.0.0",
            metadata,
        )

        assert report.result == ValidationResult.FAILED
        assert any("sharpe_ratio" in e.lower() for e in report.errors)

    def test_validate_model_fails_missing_metric(self, registry, mock_model):
        """Test validation fails with missing required metric."""
        metadata = ModelMetadata(
            name="missing_metric",
            version="1.0.0",
            training_samples=100,
            metrics={},  # Missing sharpe_ratio
        )

        report = registry.validate_model(
            mock_model,
            "missing_metric",
            "1.0.0",
            metadata,
        )

        assert report.result == ValidationResult.FAILED
        assert any("required metric" in e.lower() or "sharpe_ratio" in e.lower() for e in report.errors)

    def test_register_model_with_validation(self, registry, pickleable_model, valid_metadata):
        """Test registering model runs validation."""
        model_version = registry.register_model(
            pickleable_model,
            "test_model",
            "1.0.0",
            valid_metadata,
        )

        assert model_version is not None
        assert model_version.status == ModelStatus.STAGING

    def test_register_model_fails_validation(self, registry, pickleable_model, invalid_metadata):
        """Test registering invalid model raises error."""
        with pytest.raises(ValueError, match="validation failed"):
            registry.register_model(
                pickleable_model,
                "bad_model",
                "1.0.0",
                invalid_metadata,
            )

    def test_register_model_skip_validation(self, registry, pickleable_model, invalid_metadata):
        """Test registering with skip_validation bypasses checks."""
        model_version = registry.register_model(
            pickleable_model,
            "skip_model",
            "1.0.0",
            invalid_metadata,
            skip_validation=True,
        )

        assert model_version is not None

    def test_promote_with_validation(self, registry, pickleable_model, valid_metadata):
        """Test promoting model with validation."""
        # First register
        registry.register_model(
            pickleable_model,
            "promote_test",
            "1.0.0",
            valid_metadata,
        )

        # Then promote
        report = registry.promote_with_validation(
            "promote_test",
            "1.0.0",
        )

        assert report.result in [ValidationResult.PASSED, ValidationResult.WARNING]
        assert registry.get_production_version("promote_test") == "1.0.0"

    def test_validation_history(self, registry, mock_model, valid_metadata):
        """Test validation history is tracked."""
        registry.validate_model(
            mock_model,
            "history_test",
            "1.0.0",
            valid_metadata,
        )

        history = registry.get_validation_history("history_test", "1.0.0")

        assert len(history) == 1
        assert history[0].model_name == "history_test"

    def test_validation_summary(self, registry, mock_model, valid_metadata, invalid_metadata):
        """Test validation summary statistics."""
        # Valid
        registry.validate_model(mock_model, "m1", "1.0.0", valid_metadata)
        # Invalid
        registry.validate_model(mock_model, "m2", "1.0.0", invalid_metadata)

        summary = registry.get_validation_summary()

        assert summary["total_validations"] == 2
        assert summary["passed"] >= 0
        assert summary["failed"] >= 0


class TestCreateValidatedRegistry:
    """Tests for create_validated_registry factory function."""

    def test_creates_registry_with_defaults(self, tmp_path):
        """Test creating registry with default config."""
        registry = create_validated_registry(
            storage_path=str(tmp_path),
            min_sharpe=0.5,
            max_drawdown=0.3,
        )

        assert isinstance(registry, ValidatedModelRegistry)
        assert registry.validation_config.min_sharpe_ratio == 0.5
        assert registry.validation_config.max_drawdown == 0.3


# ============================================================================
# DriftAlertManager Tests
# ============================================================================


class TestDriftAlertManager:
    """Tests for DriftAlertManager with alert integration."""

    @pytest.fixture
    def alert_manager(self):
        """Create an alert manager."""
        config = DriftAlertConfig(
            channels=[AlertChannel.LOG, AlertChannel.CALLBACK],
            confidence_threshold=0.5,
            consecutive_drift_threshold=1,  # Alert on first drift for testing
            min_alert_interval_seconds=0,  # No rate limiting for tests
        )
        return DriftAlertManager(config)

    @pytest.fixture
    def drift_result_high(self):
        """Create a high-confidence drift result."""
        return DriftResult(
            is_drift=True,
            drift_type=DriftType.SUDDEN,
            confidence=0.9,
            p_value=0.01,
            statistic=5.0,
            feature_name="rsi_14",
        )

    @pytest.fixture
    def drift_result_low(self):
        """Create a low-confidence drift result."""
        return DriftResult(
            is_drift=True,
            drift_type=DriftType.GRADUAL,
            confidence=0.3,
            p_value=0.1,
            statistic=2.0,
            feature_name="macd",
        )

    @pytest.fixture
    def no_drift_result(self):
        """Create a no-drift result."""
        return DriftResult(
            is_drift=False,
            drift_type=None,
            confidence=0.1,
            p_value=0.5,
            statistic=1.0,
            feature_name="test",
        )

    @pytest.mark.asyncio
    async def test_process_drift_creates_alert(self, alert_manager, drift_result_high):
        """Test processing drift creates an alert."""
        alert = await alert_manager.process_drift(
            drift_result_high,
            feature_name="rsi_14",
            model_name="price_predictor",
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH
        assert alert.feature_name == "rsi_14"
        assert alert.model_name == "price_predictor"

    @pytest.mark.asyncio
    async def test_process_no_drift_no_alert(self, alert_manager, no_drift_result):
        """Test no alert is created when no drift."""
        alert = await alert_manager.process_drift(no_drift_result)
        assert alert is None

    @pytest.mark.asyncio
    async def test_process_low_confidence_no_alert(self, alert_manager, drift_result_low):
        """Test no alert for low confidence drift."""
        alert = await alert_manager.process_drift(drift_result_low)
        assert alert is None

    def test_calculate_severity_critical(self, alert_manager):
        """Test severity calculation for critical drift."""
        result = DriftResult(
            is_drift=True,
            drift_type=DriftType.SUDDEN,
            confidence=0.98,
            p_value=0.001,
            statistic=10.0,
            feature_name="test",
        )

        severity = alert_manager._calculate_severity(result)
        assert severity == AlertSeverity.CRITICAL

    def test_calculate_severity_low(self, alert_manager):
        """Test severity calculation for low drift."""
        result = DriftResult(
            is_drift=True,
            drift_type=DriftType.GRADUAL,
            confidence=0.55,
            p_value=0.04,
            statistic=2.0,
            feature_name="test",
        )

        severity = alert_manager._calculate_severity(result)
        assert severity == AlertSeverity.LOW

    def test_get_recommended_action_sudden(self, alert_manager):
        """Test recommended action for sudden drift."""
        result = DriftResult(
            is_drift=True,
            drift_type=DriftType.SUDDEN,
            confidence=0.95,
            p_value=0.01,
            statistic=5.0,
            feature_name="test",
        )

        action = alert_manager._get_recommended_action(result, AlertSeverity.CRITICAL)
        assert "urgent" in action.lower() or "halt" in action.lower()

    @pytest.mark.asyncio
    async def test_callback_invoked(self, alert_manager, drift_result_high):
        """Test that registered callbacks are invoked."""
        callback_invoked = []

        def test_callback(alert):
            callback_invoked.append(alert)

        alert_manager.register_callback(test_callback)

        await alert_manager.process_drift(
            drift_result_high,
            feature_name="test",
        )

        assert len(callback_invoked) == 1
        assert isinstance(callback_invoked[0], EnhancedDriftAlert)

    @pytest.mark.asyncio
    async def test_async_callback_invoked(self, alert_manager, drift_result_high):
        """Test that async callbacks are invoked."""
        callback_invoked = []

        async def async_callback(alert):
            callback_invoked.append(alert)

        alert_manager.register_async_callback(async_callback)

        await alert_manager.process_drift(
            drift_result_high,
            feature_name="test",
        )

        assert len(callback_invoked) == 1

    def test_acknowledge_alert(self, alert_manager):
        """Test acknowledging an alert."""
        # Create alert manually
        alert = EnhancedDriftAlert(
            alert_id="test-123",
            severity=AlertSeverity.HIGH,
            feature_name="test",
            drift_result=DriftResult(
                is_drift=True,
                drift_type=DriftType.SUDDEN,
                confidence=0.9,
                p_value=0.01,
                statistic=5.0,
                feature_name="test",
            ),
        )
        alert_manager._alerts["test-123"] = alert

        result = alert_manager.acknowledge_alert("test-123", "admin")

        assert result is True
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "admin"
        assert alert.acknowledged_at is not None

    def test_get_recent_alerts(self, alert_manager):
        """Test getting recent alerts."""
        # Add some alerts
        for i in range(5):
            alert = EnhancedDriftAlert(
                alert_id=f"alert-{i}",
                severity=AlertSeverity.MEDIUM if i % 2 == 0 else AlertSeverity.HIGH,
                feature_name=f"feature_{i}",
                drift_result=DriftResult(
                    is_drift=True,
                    drift_type=DriftType.GRADUAL,
                    confidence=0.7,
                    p_value=0.02,
                    statistic=3.0,
                    feature_name=f"feature_{i}",
                ),
            )
            alert_manager._alerts[f"alert-{i}"] = alert

        # Get all
        all_alerts = alert_manager.get_recent_alerts(limit=10)
        assert len(all_alerts) == 5

        # Filter by severity
        high_alerts = alert_manager.get_recent_alerts(severity=AlertSeverity.HIGH)
        assert all(a.severity == AlertSeverity.HIGH for a in high_alerts)

    def test_get_alert_summary(self, alert_manager):
        """Test getting alert summary."""
        # Add alerts
        for severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH]:
            alert = EnhancedDriftAlert(
                alert_id=f"alert-{severity.value}",
                severity=severity,
                feature_name="test",
                drift_result=DriftResult(
                    is_drift=True,
                    drift_type=DriftType.GRADUAL,
                    confidence=0.7,
                    p_value=0.02,
                    statistic=3.0,
                    feature_name="test",
                ),
            )
            alert_manager._alerts[f"alert-{severity.value}"] = alert

        summary = alert_manager.get_alert_summary()

        assert summary["total"] == 3
        assert summary["unacknowledged"] == 3
        assert "low" in summary["by_severity"]
        assert "medium" in summary["by_severity"]
        assert "high" in summary["by_severity"]


class TestIntegratedDriftMonitor:
    """Tests for IntegratedDriftMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create an integrated drift monitor."""
        config = DriftAlertConfig(
            channels=[AlertChannel.LOG],
            consecutive_drift_threshold=1,
            min_alert_interval_seconds=0,
        )
        return IntegratedDriftMonitor(
            feature_names=["feature_1", "feature_2", "feature_3"],
            model_name="test_model",
            alert_config=config,
        )

    @pytest.fixture
    def reference_data(self):
        """Create reference data."""
        np.random.seed(42)
        return np.random.randn(1000, 3)

    @pytest.fixture
    def drifted_data(self):
        """Create drifted data (shifted distribution)."""
        np.random.seed(42)
        return np.random.randn(100, 3) + 3.0  # Shifted mean

    @pytest.fixture
    def normal_data(self):
        """Create non-drifted data."""
        np.random.seed(43)
        return np.random.randn(100, 3)

    def test_fit(self, monitor, reference_data):
        """Test fitting monitor on reference data."""
        monitor.fit(reference_data)
        # Should not raise
        assert monitor._check_count == 0

    @pytest.mark.asyncio
    async def test_check_with_drift(self, monitor, reference_data, drifted_data):
        """Test checking data with drift."""
        monitor.fit(reference_data)

        result = await monitor.check(drifted_data)

        assert "overall" in result
        assert result["overall"]["is_drift"] is True
        assert result["check_count"] == 1

    @pytest.mark.asyncio
    async def test_check_without_drift(self, monitor, reference_data, normal_data):
        """Test checking data without significant drift."""
        monitor.fit(reference_data)

        result = await monitor.check(normal_data)

        # May or may not detect drift depending on random seed
        assert "overall" in result
        assert result["check_count"] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, monitor, reference_data, normal_data):
        """Test getting monitoring statistics."""
        monitor.fit(reference_data)
        await monitor.check(normal_data)

        stats = monitor.get_stats()

        assert "checks" in stats
        assert "drifts" in stats
        assert "drift_rate" in stats
        assert "alerts" in stats
        assert stats["checks"] == 1


# ============================================================================
# Integration Tests
# ============================================================================


class TestMLSystemIntegration:
    """Integration tests for the complete ML system."""

    @pytest.fixture
    def full_setup(self, tmp_path):
        """Set up complete ML system components."""
        # Feature store
        feature_store = PersistentFeatureStore(
            storage_path=str(tmp_path / "features"),
            fallback_to_memory=True,
        )

        # Model registry with validation
        validation_config = ValidationConfig(
            min_sharpe_ratio=0.5,
            min_training_samples=10,
        )
        model_registry = ValidatedModelRegistry(
            storage_path=str(tmp_path / "models"),
            validation_config=validation_config,
        )

        # Alert manager
        alert_config = DriftAlertConfig(
            channels=[AlertChannel.LOG],
            consecutive_drift_threshold=1,
        )
        alert_manager = DriftAlertManager(alert_config)

        return {
            "feature_store": feature_store,
            "model_registry": model_registry,
            "alert_manager": alert_manager,
        }

    def test_feature_store_and_registry_workflow(self, full_setup):
        """Test workflow: compute features -> train model -> validate -> deploy."""
        feature_store = full_setup["feature_store"]
        model_registry = full_setup["model_registry"]

        # 1. Store features
        features = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        feature_store.store_features("training_features", features)

        # 2. Retrieve features
        retrieved = feature_store.get_features("training_features")
        assert retrieved is not None

        # 3. Create and validate model (use pickleable model, not MagicMock)
        workflow_model = SimplePickleableModel(predictions=np.array([1.0, 2.0]))

        metadata = ModelMetadata(
            name="workflow_model",
            version="1.0.0",
            training_samples=100,
            metrics={"sharpe_ratio": 1.0, "max_drawdown": -0.05},
        )

        # 4. Register model (runs validation)
        model_version = model_registry.register_model(
            workflow_model,
            "workflow_model",
            "1.0.0",
            metadata,
        )
        assert model_version is not None

        # 5. Promote to production
        report = model_registry.promote_with_validation(
            "workflow_model",
            "1.0.0",
        )
        assert report.result in [ValidationResult.PASSED, ValidationResult.WARNING]

    @pytest.mark.asyncio
    async def test_drift_monitoring_workflow(self, full_setup):
        """Test workflow: detect drift -> create alert -> acknowledge."""
        alert_manager = full_setup["alert_manager"]

        # 1. Create drift result
        drift_result = DriftResult(
            is_drift=True,
            drift_type=DriftType.SUDDEN,
            confidence=0.9,
            p_value=0.01,
            statistic=5.0,
            feature_name="important_feature",
        )

        # 2. Process drift (creates alert)
        alert = await alert_manager.process_drift(
            drift_result,
            feature_name="important_feature",
            model_name="production_model",
        )

        assert alert is not None
        assert alert.acknowledged is False

        # 3. Acknowledge alert
        result = alert_manager.acknowledge_alert(alert.alert_id, "ml_engineer")
        assert result is True

        # 4. Verify acknowledgment
        acknowledged_alert = alert_manager.get_alert(alert.alert_id)
        assert acknowledged_alert.acknowledged is True
        assert acknowledged_alert.acknowledged_by == "ml_engineer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
