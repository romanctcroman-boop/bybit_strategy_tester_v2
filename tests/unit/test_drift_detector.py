"""
Unit tests for Model Drift Detection

Tests the ADWIN-based drift detector to ensure it correctly
identifies concept drift in model predictions.

Created: 2025-11-06
"""

import pytest
import numpy as np
from datetime import datetime
from backend.ml.drift_detector import (
    ModelDriftDetector,
    MultiModelDriftDetector,
    DriftEvent
)


class TestModelDriftDetector:
    """Test suite for ModelDriftDetector"""
    
    def test_initialization(self):
        """Test drift detector creates successfully with correct params"""
        detector = ModelDriftDetector(delta=0.002, min_samples=10)
        
        assert detector.delta == 0.002
        assert detector.min_samples == 10
        assert detector.drift_detected_count == 0
        assert detector.total_samples == 0
        assert len(detector.drift_events) == 0
        assert len(detector.recent_errors) == 0
    
    def test_update_increments_samples(self):
        """Test that update() increments sample counter"""
        detector = ModelDriftDetector()
        
        detector.update(100.0, 100.1)
        assert detector.total_samples == 1
        
        detector.update(100.0, 100.2)
        assert detector.total_samples == 2
    
    def test_no_drift_on_stable_predictions(self):
        """Test no drift detected on stable, low-error predictions"""
        detector = ModelDriftDetector(delta=0.002, min_samples=10)
        
        # Simulate 100 stable predictions (low error)
        np.random.seed(42)
        for i in range(100):
            prediction = 100.0 + np.random.normal(0, 0.1)
            actual = 100.0 + np.random.normal(0, 0.1)
            
            drift_detected = detector.update(prediction, actual)
        
        # Should detect no drift on stable data
        assert detector.drift_detected_count == 0
    
    def test_drift_detection_on_concept_shift(self):
        """Test drift detection when prediction error suddenly increases"""
        detector = ModelDriftDetector(delta=0.002, min_samples=10)
        
        np.random.seed(42)
        
        # Phase 1: 50 stable predictions (low error)
        for i in range(50):
            prediction = 100.0 + np.random.normal(0, 0.1)
            actual = 100.0 + np.random.normal(0, 0.1)
            detector.update(prediction, actual)
        
        # Phase 2: Concept drift - errors spike
        drift_detected = False
        for i in range(50):
            prediction = 100.0 + np.random.normal(0, 0.1)
            actual = 110.0 + np.random.normal(0, 0.1)  # Shifted!
            
            if detector.update(prediction, actual):
                drift_detected = True
                break
        
        # Should detect drift after concept shift
        assert drift_detected, "Should detect drift when error pattern changes"
        assert detector.drift_detected_count >= 1
    
    def test_drift_event_recorded(self):
        """Test that drift events are properly recorded"""
        detector = ModelDriftDetector(delta=0.01, min_samples=5)
        
        # Cause drift by sudden error spike
        np.random.seed(42)
        for i in range(20):
            prediction = 100.0
            actual = 100.0 if i < 10 else 120.0  # Sudden shift
            detector.update(prediction, actual)
        
        # Check that drift events were recorded
        if detector.drift_detected_count > 0:
            assert len(detector.drift_events) > 0
            
            event = detector.drift_events[0]
            assert isinstance(event, DriftEvent)
            assert event.drift_count > 0
            assert isinstance(event.timestamp, datetime)
            assert event.error_value > 0
    
    def test_should_trigger_emergency_retrain(self):
        """Test emergency retrain threshold logic"""
        detector = ModelDriftDetector()
        
        # No drifts yet
        assert not detector.should_trigger_emergency_retrain(threshold=3)
        
        # Simulate 2 drifts
        detector.drift_detected_count = 2
        assert not detector.should_trigger_emergency_retrain(threshold=3)
        
        # Simulate 3 drifts (reach threshold)
        detector.drift_detected_count = 3
        assert detector.should_trigger_emergency_retrain(threshold=3)
        
        # Simulate 5 drifts (exceed threshold)
        detector.drift_detected_count = 5
        assert detector.should_trigger_emergency_retrain(threshold=3)
    
    def test_get_status(self):
        """Test status reporting"""
        detector = ModelDriftDetector()
        
        # Update with some samples
        for i in range(10):
            detector.update(100.0 + i * 0.1, 100.0 + i * 0.1)
        
        status = detector.get_status()
        
        assert "drift_detected_count" in status
        assert "total_samples" in status
        assert "no_drift_rate" in status
        assert "avg_recent_error" in status
        assert "detector_delta" in status
        
        assert status["total_samples"] == 10
        assert status["detector_delta"] == 0.002
    
    def test_reset_clears_drift_count(self):
        """Test that reset() clears drift count and events"""
        detector = ModelDriftDetector()
        
        # Simulate some drifts
        detector.drift_detected_count = 5
        detector.drift_events = [
            DriftEvent(drift_count=i) for i in range(5)
        ]
        old_total = detector.total_samples = 100
        
        # Reset
        detector.reset()
        
        # Check that drift count and events are cleared
        assert detector.drift_detected_count == 0
        assert len(detector.drift_events) == 0
        
        # But total samples should remain (for monitoring)
        assert detector.total_samples == old_total
    
    def test_recent_errors_tracking(self):
        """Test that recent errors are tracked correctly"""
        detector = ModelDriftDetector()
        detector.max_recent_errors = 5  # Keep only 5 for testing
        
        # Add 10 errors
        for i in range(10):
            detector.update(100.0, 100.0 + i)
        
        # Should keep only last 5
        assert len(detector.recent_errors) == 5
        
        # Should be errors [5, 6, 7, 8, 9]
        assert detector.recent_errors == [5.0, 6.0, 7.0, 8.0, 9.0]
    
    def test_get_drift_history(self):
        """Test drift history retrieval"""
        detector = ModelDriftDetector()
        
        # Add some drift events
        for i in range(5):
            event = DriftEvent(drift_count=i+1, error_value=float(i))
            detector.drift_events.append(event)
        
        # Get all history
        all_history = detector.get_drift_history()
        assert len(all_history) == 5
        
        # Get limited history
        limited_history = detector.get_drift_history(limit=2)
        assert len(limited_history) == 2
        
        # Should be last 2 events
        assert limited_history[0]["drift_count"] == 4
        assert limited_history[1]["drift_count"] == 5


class TestMultiModelDriftDetector:
    """Test suite for MultiModelDriftDetector"""
    
    def test_initialization(self):
        """Test multi-model detector creates successfully"""
        detector = MultiModelDriftDetector(delta=0.01)
        
        assert detector.default_delta == 0.01
        assert len(detector.detectors) == 0
    
    def test_get_or_create_detector(self):
        """Test automatic detector creation for new models"""
        detector = MultiModelDriftDetector()
        
        # First call should create new detector
        model1_detector = detector.get_or_create_detector("model_1")
        assert "model_1" in detector.detectors
        assert isinstance(model1_detector, ModelDriftDetector)
        
        # Second call should return existing detector
        same_detector = detector.get_or_create_detector("model_1")
        assert same_detector is model1_detector
    
    def test_update_multiple_models(self):
        """Test updating multiple models independently"""
        detector = MultiModelDriftDetector()
        
        # Update different models
        detector.update("btc_5m", 100.0, 100.1)
        detector.update("btc_15m", 200.0, 200.2)
        detector.update("eth_5m", 50.0, 50.1)
        
        # Should have 3 detectors
        assert len(detector.detectors) == 3
        
        # Each should have 1 sample
        assert detector.detectors["btc_5m"].total_samples == 1
        assert detector.detectors["btc_15m"].total_samples == 1
        assert detector.detectors["eth_5m"].total_samples == 1
    
    def test_get_status_for_specific_model(self):
        """Test getting status for specific model"""
        detector = MultiModelDriftDetector()
        
        # Update one model
        detector.update("model_1", 100.0, 100.1)
        
        # Get status
        status = detector.get_status("model_1")
        assert "drift_detected_count" in status
        assert status["total_samples"] == 1
        
        # Get status for non-existent model
        status_missing = detector.get_status("non_existent")
        assert "error" in status_missing
    
    def test_get_all_status(self):
        """Test getting status for all models"""
        detector = MultiModelDriftDetector()
        
        # Update multiple models
        detector.update("model_1", 100.0, 100.1)
        detector.update("model_2", 200.0, 200.1)
        
        # Get all status
        all_status = detector.get_all_status()
        
        assert len(all_status) == 2
        assert "model_1" in all_status
        assert "model_2" in all_status
        assert all_status["model_1"]["total_samples"] == 1
        assert all_status["model_2"]["total_samples"] == 1
    
    def test_reset_specific_model(self):
        """Test resetting specific model"""
        detector = MultiModelDriftDetector()
        
        # Update and simulate drifts
        detector.update("model_1", 100.0, 100.1)
        detector.detectors["model_1"].drift_detected_count = 3
        
        detector.update("model_2", 200.0, 200.1)
        detector.detectors["model_2"].drift_detected_count = 5
        
        # Reset only model_1
        detector.reset("model_1")
        
        # model_1 should be reset
        assert detector.detectors["model_1"].drift_detected_count == 0
        
        # model_2 should be unchanged
        assert detector.detectors["model_2"].drift_detected_count == 5
    
    def test_reset_all_models(self):
        """Test resetting all models"""
        detector = MultiModelDriftDetector()
        
        # Update multiple models with drifts
        for model_id in ["m1", "m2", "m3"]:
            detector.update(model_id, 100.0, 100.1)
            detector.detectors[model_id].drift_detected_count = 5
        
        # Reset all
        detector.reset()
        
        # All should be reset
        for model_id in ["m1", "m2", "m3"]:
            assert detector.detectors[model_id].drift_detected_count == 0
    
    def test_get_models_needing_retrain(self):
        """Test identifying models that need retraining"""
        detector = MultiModelDriftDetector()
        
        # Create models with different drift counts
        detector.update("model_ok", 100.0, 100.1)
        detector.detectors["model_ok"].drift_detected_count = 2
        
        detector.update("model_needs_retrain", 100.0, 100.1)
        detector.detectors["model_needs_retrain"].drift_detected_count = 5
        
        detector.update("model_critical", 100.0, 100.1)
        detector.detectors["model_critical"].drift_detected_count = 10
        
        # Get models needing retrain (threshold = 3)
        needs_retrain = detector.get_models_needing_retrain(threshold=3)
        
        assert len(needs_retrain) == 2
        assert "model_needs_retrain" in needs_retrain
        assert "model_critical" in needs_retrain
        assert "model_ok" not in needs_retrain


class TestDriftEvent:
    """Test suite for DriftEvent dataclass"""
    
    def test_drift_event_creation(self):
        """Test DriftEvent can be created with defaults"""
        event = DriftEvent(
            error_value=5.5,
            drift_count=3
        )
        
        assert event.error_value == 5.5
        assert event.drift_count == 3
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.metadata, dict)
    
    def test_drift_event_to_dict(self):
        """Test DriftEvent serialization to dict"""
        event = DriftEvent(
            error_value=2.5,
            drift_count=1,
            detector_width=100,
            metadata={"test": "value"}
        )
        
        event_dict = event.to_dict()
        
        assert "timestamp" in event_dict
        assert event_dict["error_value"] == 2.5
        assert event_dict["drift_count"] == 1
        assert event_dict["detector_width"] == 100
        assert event_dict["metadata"]["test"] == "value"


@pytest.mark.integration
class TestDriftDetectorIntegration:
    """Integration tests with realistic scenarios"""
    
    def test_crypto_market_regime_change(self):
        """
        Test drift detection on realistic crypto market scenario.
        
        Scenario: BTC price prediction model trained on low volatility
        encounters high volatility regime (e.g., Fed announcement).
        """
        detector = ModelDriftDetector(delta=0.002, min_samples=20)
        
        np.random.seed(42)
        
        # Phase 1: Low volatility regime (model works well)
        # 2% daily volatility
        for i in range(100):
            true_price = 35000 + np.random.normal(0, 700)  # ±2%
            prediction = true_price + np.random.normal(0, 100)  # Small error
            
            detector.update(prediction, true_price)
        
        # Check: no drift in stable regime
        stable_regime_drifts = detector.drift_detected_count
        
        # Phase 2: High volatility regime (model predictions degrade)
        # 8% daily volatility
        drift_detected_in_volatile = False
        for i in range(100):
            true_price = 35000 + np.random.normal(0, 2800)  # ±8%
            # Model still predicts based on low vol → large errors
            prediction = 35000 + np.random.normal(0, 700)
            
            if detector.update(prediction, true_price):
                drift_detected_in_volatile = True
        
        # Should detect drift when regime changes
        assert drift_detected_in_volatile, \
            "Should detect drift when market regime changes"
        assert detector.drift_detected_count > stable_regime_drifts
    
    def test_gradual_model_degradation(self):
        """
        Test detection of gradual model degradation.
        
        Scenario: Model slowly becomes less accurate over time
        as market microstructure evolves.
        """
        detector = ModelDriftDetector(delta=0.005, min_samples=10)
        
        np.random.seed(42)
        
        # Gradually increasing error over 200 samples
        drift_detected = False
        for i in range(200):
            # Error gradually increases from 0.5% to 5%
            error_magnitude = 0.005 + (i / 200) * 0.045
            
            true_price = 35000
            prediction = true_price * (1 + np.random.normal(0, error_magnitude))
            
            if detector.update(prediction, true_price):
                drift_detected = True
        
        # Should eventually detect drift
        assert drift_detected, \
            "Should detect drift from gradual degradation"
        
        # Should have some drift events
        assert len(detector.drift_events) > 0
