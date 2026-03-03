"""
Tests for A/B Testing Framework

Run: pytest tests/monitoring/test_ab_testing.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.ab_testing import (
    ABTesting,
    ABTest,
    ABTestVariant,
    ABTestResults,
    get_ab_testing,
)


class TestABTesting:
    """Tests for ABTesting."""

    @pytest.fixture
    def ab_testing(self):
        """Create A/B testing instance with temp storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "ab_tests.json"
            yield ABTesting(str(storage_path))

    def test_create_test(self, ab_testing):
        """Test creating an A/B test."""
        test_id = ab_testing.create_test(
            name="Strategy Test",
            prompt_name="strategy_prompt",
            variants=["v1", "v2"],
            traffic_split=[0.5, 0.5],
        )
        
        assert test_id
        assert test_id.startswith("ab_")
        
        # Verify test created
        test = ab_testing.get_test(test_id)
        assert test is not None
        assert test.name == "Strategy Test"
        assert len(test.variants) == 2

    def test_create_test_equal_split(self, ab_testing):
        """Test creating test with equal traffic split."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2", "v3"],
        )
        
        test = ab_testing.get_test(test_id)
        
        # Should have equal split
        for variant in test.variants:
            assert abs(variant.traffic_split - 1/3) < 0.01

    def test_create_test_invalid_split(self, ab_testing):
        """Test creating test with invalid traffic split."""
        with pytest.raises(ValueError):
            ab_testing.create_test(
                name="Test",
                prompt_name="prompt",
                variants=["v1", "v2"],
                traffic_split=[0.5, 0.6],  # Doesn't sum to 1.0
            )

    def test_get_variant(self, ab_testing):
        """Test getting variant for user."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
            traffic_split=[0.5, 0.5],
        )
        
        # Get variant without user_id (random assignment)
        variant = ab_testing.get_variant(test_id)
        
        # Variant should be assigned (v1 or v2)
        assert variant in ["v1", "v2"]

    def test_record_conversion(self, ab_testing):
        """Test recording conversion."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Record conversion
        success = ab_testing.record_conversion(test_id, "v1", converted=True)
        assert success is True
        
        # Verify recorded
        test = ab_testing.get_test(test_id)
        for variant in test.variants:
            if variant.prompt_version == "v1":
                assert variant.conversions == 1

    def test_record_conversion_with_reward(self, ab_testing):
        """Test recording conversion with reward."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Record conversion with reward
        ab_testing.record_conversion(test_id, "v1", converted=True, reward=5.0)
        
        # Verify reward recorded
        test = ab_testing.get_test(test_id)
        for variant in test.variants:
            if variant.prompt_version == "v1":
                assert variant.total_reward == 5.0

    def test_get_results(self, ab_testing):
        """Test getting test results."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
            min_sample_size=10,
        )
        
        # Record some data directly through variants
        test = ab_testing.get_test(test_id)
        for variant in test.variants:
            variant.impressions = 20
            variant.conversions = 10
        
        # Save
        ab_testing._save()
        
        # Get results
        results = ab_testing.get_results(test_id)
        
        assert results is not None
        assert results.test_id == test_id
        assert results.total_impressions == 40
        assert isinstance(results.variant_results, list)

    def test_stop_test(self, ab_testing):
        """Test stopping a test."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Stop test
        success = ab_testing.stop_test(test_id)
        assert success is True
        
        # Verify stopped
        test = ab_testing.get_test(test_id)
        assert test.status == "completed"
        assert test.completed_at is not None

    def test_stop_test_select_winner(self, ab_testing):
        """Test stopping test with winner selection."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
            min_sample_size=5,
        )
        
        # Record clear winner
        for i in range(20):
            ab_testing.record_conversion(test_id, "v1", converted=True)
            ab_testing.record_conversion(test_id, "v2", converted=False)
        
        # Stop with winner selection
        ab_testing.stop_test(test_id, select_winner=True)
        
        test = ab_testing.get_test(test_id)
        assert test.winner_variant == "v1"

    def test_pause_test(self, ab_testing):
        """Test pausing a test."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Pause test
        success = ab_testing.pause_test(test_id)
        assert success is True
        
        # Verify paused
        test = ab_testing.get_test(test_id)
        assert test.status == "paused"

    def test_resume_test(self, ab_testing):
        """Test resuming a paused test."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Pause then resume
        ab_testing.pause_test(test_id)
        success = ab_testing.resume_test(test_id)
        assert success is True
        
        # Verify running
        test = ab_testing.get_test(test_id)
        assert test.status == "running"

    def test_list_tests(self, ab_testing):
        """Test listing tests."""
        ab_testing.create_test("Test 1", "prompt1", ["v1", "v2"])
        ab_testing.create_test("Test 2", "prompt2", ["v1", "v2"])
        ab_testing.create_test("Test 3", "prompt3", ["v1", "v2"])
        
        # List all
        tests = ab_testing.list_tests()
        assert len(tests) == 3
        
        # Pause one
        ab_testing.pause_test(tests[0].test_id)
        
        # List running only
        running = ab_testing.list_tests(status="running")
        assert len(running) == 2
        
        # List paused only
        paused = ab_testing.list_tests(status="paused")
        assert len(paused) == 1

    def test_delete_test(self, ab_testing):
        """Test deleting a test."""
        test_id = ab_testing.create_test(
            name="Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Delete
        success = ab_testing.delete_test(test_id)
        assert success is True
        
        # Verify deleted
        test = ab_testing.get_test(test_id)
        assert test is None

    def test_get_stats(self, ab_testing):
        """Test getting statistics."""
        ab_testing.create_test("Test 1", "prompt1", ["v1", "v2"])
        ab_testing.create_test("Test 2", "prompt2", ["v1", "v2"])
        
        stats = ab_testing.get_stats()
        
        assert stats["total_tests"] == 2
        assert "running" in stats
        assert "paused" in stats
        assert "completed" in stats

    def test_persistence(self, ab_testing):
        """Test saving and loading from disk."""
        test_id = ab_testing.create_test(
            name="Persistent Test",
            prompt_name="prompt",
            variants=["v1", "v2"],
        )
        
        # Record some data
        ab_testing.record_conversion(test_id, "v1", converted=True)
        
        # Create new instance (should load from disk)
        ab_testing2 = ABTesting(ab_testing.storage_path)
        
        # Should have same data
        test = ab_testing2.get_test(test_id)
        assert test is not None
        assert test.name == "Persistent Test"
        
        for variant in test.variants:
            if variant.prompt_version == "v1":
                assert variant.conversions == 1

    def test_get_nonexistent_test(self, ab_testing):
        """Test getting nonexistent test."""
        test = ab_testing.get_test("nonexistent_test")
        assert test is None

    def test_record_conversion_nonexistent_test(self, ab_testing):
        """Test recording conversion for nonexistent test."""
        success = ab_testing.record_conversion("nonexistent", "v1", converted=True)
        assert success is False

    def test_conversion_rate_calculation(self):
        """Test conversion rate calculation."""
        variant = ABTestVariant(
            variant_id="v1",
            name="Variant 1",
            prompt_version="v1",
            traffic_split=0.5,
            impressions=100,
            conversions=25,
            total_reward=25.0,
        )
        
        assert variant.conversion_rate == 0.25
        assert variant.avg_reward == 0.25

    def test_ab_test_to_dict(self):
        """Test ABTest serialization."""
        test = ABTest(
            test_id="ab_test123",
            name="Test",
            prompt_name="prompt",
            variants=[
                ABTestVariant(
                    variant_id="v1",
                    name="Variant 1",
                    prompt_version="v1",
                    traffic_split=0.5,
                )
            ],
        )
        
        data = test.to_dict()
        
        assert data["test_id"] == "ab_test123"
        assert data["name"] == "Test"
        assert len(data["variants"]) == 1

    def test_ab_test_from_dict(self):
        """Test ABTest deserialization."""
        data = {
            "test_id": "ab_test123",
            "name": "Test",
            "prompt_name": "prompt",
            "variants": [
                {
                    "variant_id": "v1",
                    "name": "Variant 1",
                    "prompt_version": "v1",
                    "traffic_split": 0.5,
                    "impressions": 100,
                    "conversions": 25,
                    "total_reward": 25.0,
                }
            ],
            "status": "running",
        }
        
        test = ABTest.from_dict(data)
        
        assert test.test_id == "ab_test123"
        assert len(test.variants) == 1
        assert test.variants[0].impressions == 100


class TestABTestResults:
    """Tests for ABTestResults."""

    def test_results_to_dict(self):
        """Test results serialization."""
        results = ABTestResults(
            test_id="ab_test123",
            total_impressions=200,
            total_conversions=50,
            winner="v1",
            confidence=0.95,
            statistical_significance=True,
            variant_results=[],
            recommendation="Deploy winner",
        )
        
        data = results.to_dict()
        
        assert data["test_id"] == "ab_test123"
        assert data["winner"] == "v1"
        assert data["statistical_significance"] is True


class TestGlobalABTesting:
    """Tests for global A/B testing functions."""

    def test_get_ab_testing_singleton(self):
        """Test singleton pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "ab_tests.json"
            
            ab1 = get_ab_testing(str(storage_path))
            ab2 = get_ab_testing(str(storage_path))
            
            # Should be same instance
            assert ab1 is ab2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
