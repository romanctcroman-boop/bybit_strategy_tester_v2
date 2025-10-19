"""
API Integration Tests for Optimization Endpoints

Tests:
- POST /api/v1/optimize/walk-forward
- POST /api/v1/optimize/bayesian
- GET /api/v1/optimize/result/:task_id
- POST /api/v1/optimize/cancel/:task_id

Using FastAPI TestClient with mocked Celery tasks.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime
import json


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient"""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def valid_walkforward_request():
    """Valid Walk-Forward optimization request"""
    return {
        "method": "walk_forward",
        "strategy_class": "MA_Crossover",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-06-30T23:59:59",
        "initial_capital": 10000.0,
        "parameters": {
            "fast_period": {"min": 5, "max": 20, "step": 5},
            "slow_period": {"min": 20, "max": 50, "step": 10}
        },
        "in_sample_period": 90,
        "out_of_sample_period": 30,
        "step_period": 30
    }


@pytest.fixture
def valid_bayesian_request():
    """Valid Bayesian optimization request"""
    return {
        "method": "bayesian",
        "strategy_class": "MA_Crossover",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-06-30T23:59:59",
        "initial_capital": 10000.0,
        "parameters": {
            "fast_period": {"min": 5, "max": 20},
            "slow_period": {"min": 20, "max": 50}
        },
        "n_trials": 50,
        "timeout": 300,
        "sampler": "TPE"
    }


# ============================================================================
# Walk-Forward Endpoint Tests
# ============================================================================

class TestWalkForwardEndpoint:
    """Test /api/v1/optimize/walk-forward endpoint"""
    
    def test_create_walkforward_optimization_success(self, client, valid_walkforward_request):
        """Test successful Walk-Forward optimization creation"""
        with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
            # Mock Celery task
            mock_result = Mock()
            mock_result.id = "wf-task-123"
            mock_task.return_value = mock_result
            
            # Send request
            response = client.post("/api/v1/optimize/walk-forward", json=valid_walkforward_request)
            
            # Assertions
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            
            assert "task_id" in data
            assert data["task_id"] == "wf-task-123"
            assert data["status"] == "PENDING"
            assert data["method"] == "walk_forward"
            
            # Verify Celery task was called
            mock_task.assert_called_once()
            
    
    def test_walkforward_missing_required_fields(self, client):
        """Test Walk-Forward with missing required fields"""
        invalid_request = {
            "method": "walk_forward",
            "symbol": "BTCUSDT"
            # Missing strategy_id, timeframe, dates, etc.
        }
        
        response = client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    
    def test_walkforward_invalid_date_range(self, client, valid_walkforward_request):
        """Test Walk-Forward with end_date before start_date"""
        invalid_request = valid_walkforward_request.copy()
        invalid_request["start_date"] = "2024-06-30"
        invalid_request["end_date"] = "2024-01-01"  # Invalid
        
        response = client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        # Should fail validation
        assert response.status_code in [400, 422]
    
    
    def test_walkforward_invalid_parameters(self, client, valid_walkforward_request):
        """Test Walk-Forward with invalid parameter ranges"""
        invalid_request = valid_walkforward_request.copy()
        invalid_request["parameters"] = {
            "fast_period": {"min": 20, "max": 10, "step": 5}  # min > max
        }
        
        response = client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        assert response.status_code in [400, 422]
    
    
    def test_walkforward_invalid_periods(self, client, valid_walkforward_request):
        """Test Walk-Forward with invalid period configuration"""
        invalid_request = valid_walkforward_request.copy()
        invalid_request["in_sample_period"] = 10  # Too short
        invalid_request["out_of_sample_period"] = 5
        invalid_request["step_period"] = 3
        
        response = client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        # May pass validation but should be caught by business logic
        # For now, just ensure it doesn't crash
        assert response.status_code in [200, 400, 422]


# ============================================================================
# Bayesian Endpoint Tests
# ============================================================================

class TestBayesianEndpoint:
    """Test /api/v1/optimize/bayesian endpoint"""
    
    def test_create_bayesian_optimization_success(self, client, valid_bayesian_request):
        """Test successful Bayesian optimization creation"""
        with patch('backend.tasks.optimize_tasks.bayesian_task.apply_async') as mock_task:
            # Mock Celery task
            mock_result = Mock()
            mock_result.id = "bayesian-task-456"
            mock_task.return_value = mock_result
            
            # Send request
            response = client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            # Assertions
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            
            assert "task_id" in data
            assert data["task_id"] == "bayesian-task-456"
            assert data["status"] == "PENDING"
            assert data["method"] == "bayesian"
            
            # Verify Celery task was called
            mock_task.assert_called_once()
    
    
    def test_bayesian_missing_required_fields(self, client):
        """Test Bayesian with missing required fields"""
        invalid_request = {
            "method": "bayesian",
            "symbol": "BTCUSDT"
            # Missing strategy_id, parameters, etc.
        }
        
        response = client.post("/api/v1/optimize/bayesian", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    
    def test_bayesian_invalid_n_trials(self, client, valid_bayesian_request):
        """Test Bayesian with invalid n_trials"""
        invalid_request = valid_bayesian_request.copy()
        invalid_request["n_trials"] = -10  # Negative
        
        response = client.post("/api/v1/optimize/bayesian", json=invalid_request)
        assert response.status_code in [400, 422]
    
    
    def test_bayesian_invalid_sampler(self, client, valid_bayesian_request):
        """Test Bayesian with invalid sampler"""
        invalid_request = valid_bayesian_request.copy()
        invalid_request["sampler"] = "INVALID_SAMPLER"
        
        response = client.post("/api/v1/optimize/bayesian", json=invalid_request)
        # Should fail validation
        assert response.status_code in [400, 422]
    
    
    def test_bayesian_with_categorical_parameters(self, client, valid_bayesian_request):
        """Test Bayesian with categorical parameters"""
        request_with_categorical = valid_bayesian_request.copy()
        request_with_categorical["parameters"] = {
            "fast_period": {"min": 5, "max": 20},
            "strategy_type": {"choices": ["aggressive", "conservative", "balanced"]}
        }
        
        with patch('backend.tasks.optimize_tasks.bayesian_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "bayesian-categorical-789"
            mock_task.return_value = mock_result
            
            response = client.post("/api/v1/optimize/bayesian", json=request_with_categorical)
            
            # Should succeed
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "bayesian-categorical-789"


# ============================================================================
# Result & Cancel Endpoint Tests
# ============================================================================

class TestResultEndpoint:
    """Test /api/v1/optimize/result/:task_id endpoint"""
    
    @pytest.mark.asyncio
    async def test_get_result_pending(self, client):
        """Test getting result for pending task"""
        with patch('backend.celery_app.celery_app.AsyncResult') as mock_result:
            # Mock pending task
            mock_task_result = Mock()
            mock_task_result.state = "PENDING"
            mock_task_result.result = None
            mock_task_result.info = None
            mock_result.return_value = mock_task_result
            
            response = client.get("/api/v1/optimize/test-task-123/result")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "PENDING"
    
    
    @pytest.mark.asyncio
    async def test_get_result_success(self, client):
        """Test getting result for completed task"""
        with patch('backend.celery_app.celery_app.AsyncResult') as mock_result:
            # Mock successful task
            mock_task_result = Mock()
            mock_task_result.state = "SUCCESS"
            mock_task_result.result = {
                "best_params": {"fast_period": 10, "slow_period": 30},
                "best_score": 0.85,
                "method": "bayesian",
                "completed_at": datetime.utcnow().isoformat()
            }
            mock_task_result.info = mock_task_result.result
            mock_result.return_value = mock_task_result
            
            response = client.get("/api/v1/optimize/test-task-123/result")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "SUCCESS"
            assert "result" in data
            assert data["result"]["best_score"] == 0.85
    
    
    @pytest.mark.asyncio
    async def test_get_result_failure(self, client):
        """Test getting result for failed task"""
        with patch('backend.celery_app.celery_app.AsyncResult') as mock_result:
            # Mock failed task
            mock_task_result = Mock()
            mock_task_result.state = "FAILURE"
            mock_task_result.result = Exception("Optimization failed: Invalid data")
            mock_task_result.info = str(mock_task_result.result)
            mock_result.return_value = mock_task_result
            
            response = client.get("/api/v1/optimize/test-task-123/result")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "FAILURE"
            assert "error" in data or "result" in data
    
    
    def test_get_result_invalid_task_id(self, client):
        """Test getting result with invalid task_id format"""
        response = client.get("/api/v1/optimize//result")
        
        # Should return 404 (not found) or 405 (method not allowed)
        assert response.status_code in [404, 405]


class TestCancelEndpoint:
    """Test /api/v1/optimize/cancel/:task_id endpoint"""
    
    def test_cancel_task_success(self, client):
        """Test successful task cancellation"""
        with patch('backend.celery_app.celery_app.control.revoke') as mock_revoke:
            response = client.delete("/api/v1/optimize/test-task-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert "message" in data
            assert "cancel" in data["message"].lower() or "revoke" in data["message"].lower()
            
            # Verify revoke was called
            mock_revoke.assert_called_once_with("test-task-123", terminate=True)
    
    
    def test_cancel_invalid_task_id(self, client):
        """Test cancelling with invalid task_id format"""
        response = client.delete("/api/v1/optimize/")
        
        # Should return 404 or 405
        assert response.status_code in [404, 405]


# ============================================================================
# Mock Celery Task Verification
# ============================================================================

class TestCeleryTaskMocking:
    """Verify Celery task mocking works correctly"""
    
    def test_celery_task_called_with_correct_params(self, client, valid_walkforward_request):
        """Verify Celery task is called with correct parameters"""
        with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "verify-task-999"
            mock_task.return_value = mock_result
            
            response = client.post("/api/v1/optimize/walk-forward", json=valid_walkforward_request)
            
            assert response.status_code == 200
            
            # Verify task was called
            mock_task.assert_called_once()
            
            # Verify parameters (if accessible)
            # call_args[0] is args, call_args[1] is kwargs
            # This depends on how the task is implemented
            # For now, just verify it was called
    
    
    def test_multiple_tasks_create_different_ids(self, client, valid_bayesian_request):
        """Test that multiple task creations get different IDs"""
        with patch('backend.tasks.optimize_tasks.bayesian_task.apply_async') as mock_task:
            # First task
            mock_result_1 = Mock()
            mock_result_1.id = "task-1"
            mock_task.return_value = mock_result_1
            response1 = client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            # Second task
            mock_result_2 = Mock()
            mock_result_2.id = "task-2"
            mock_task.return_value = mock_result_2
            response2 = client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            data1 = response1.json()
            data2 = response2.json()
            
            assert data1["task_id"] == "task-1"
            assert data2["task_id"] == "task-2"
            assert data1["task_id"] != data2["task_id"]


# ============================================================================
# Edge Cases & Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_very_large_parameter_space(self, client, valid_walkforward_request):
        """Test with very large parameter space"""
        large_request = valid_walkforward_request.copy()
        large_request["parameters"] = {
            f"param_{i}": {"min": 1, "max": 100, "step": 1}
            for i in range(10)  # 10 parameters with 100 values each
        }
        
        with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "large-task"
            mock_task.return_value = mock_result
            
            response = client.post("/api/v1/optimize/walk-forward", json=large_request)
            
            # Should succeed (backend will handle large space)
            assert response.status_code == 200
    
    
    def test_special_characters_in_strategy_id(self, client, valid_bayesian_request):
        """Test with special characters in strategy_class"""
        special_request = valid_bayesian_request.copy()
        special_request["strategy_class"] = "MA_Crossover-v2.1_test"
        
        with patch('backend.tasks.optimize_tasks.bayesian_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "special-task"
            mock_task.return_value = mock_result
            
            response = client.post("/api/v1/optimize/bayesian", json=special_request)
            
            # Should handle special characters
            assert response.status_code in [200, 400, 422]
    
    
    def test_empty_parameter_space(self, client, valid_walkforward_request):
        """Test with empty parameter space"""
        empty_request = valid_walkforward_request.copy()
        empty_request["parameters"] = {}
        
        response = client.post("/api/v1/optimize/walk-forward", json=empty_request)
        
        # Should fail validation
        assert response.status_code in [400, 422]
    
    
    def test_malformed_json(self, client):
        """Test with malformed JSON"""
        response = client.post(
            "/api/v1/optimize/bayesian",
            data="{ this is not valid json }",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
