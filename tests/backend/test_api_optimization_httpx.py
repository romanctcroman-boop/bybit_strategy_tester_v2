"""
API Integration Tests for Optimization Endpoints (httpx.AsyncClient)

Phase 2.2: API Integration Tests
Using httpx.AsyncClient for FastAPI async testing.

Tests:
- POST /api/v1/optimize/walk-forward
- POST /api/v1/optimize/bayesian
- GET /api/v1/optimize/{task_id}/status
- GET /api/v1/optimize/{task_id}/result
- DELETE /api/v1/optimize/{task_id}

Mock Celery tasks to avoid actual background processing.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime
import json


@pytest_asyncio.fixture
async def async_client():
    """httpx.AsyncClient for FastAPI testing"""
    from backend.main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_walkforward_request():
    """Valid Walk-Forward optimization request"""
    return {
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
        "commission": 0.001,
        "metric": "sharpe_ratio",
        "in_sample_period": 90,
        "out_sample_period": 30,  # Corrected field name
        "step_period": 30
    }


@pytest.fixture
def valid_bayesian_request():
    """Valid Bayesian optimization request"""
    return {
        "strategy_class": "MA_Crossover",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-06-30T23:59:59",
        "initial_capital": 10000.0,
        "parameters": {
            "fast_period": {"type": "int", "low": 5, "high": 20},  # BayesianParameter requires type, low, high
            "slow_period": {"type": "int", "low": 20, "high": 50}
        },
        "commission": 0.001,
        "metric": "sharpe_ratio",
        "n_trials": 50,
        "timeout": 300,
        "sampler": "TPE"
    }


# ============================================================================
# Walk-Forward Endpoint Tests
# ============================================================================

class TestWalkForwardEndpoint:
    """Test /api/v1/optimize/walk-forward endpoint"""
    
    @pytest.mark.asyncio
    async def test_create_walkforward_optimization_success(self, async_client, valid_walkforward_request):
        """Test successful Walk-Forward optimization creation"""
        with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
            # Mock Celery task
            mock_result = Mock()
            mock_result.id = "wf-task-123"
            mock_task.return_value = mock_result
            
            # Send request
            response = await async_client.post("/api/v1/optimize/walk-forward", json=valid_walkforward_request)
            
            # Assertions
            assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
            data = response.json()
            
            assert "task_id" in data
            assert data["task_id"] == "wf-task-123"
            assert data["status"] == "PENDING"
            assert data["method"] == "walk_forward"
            
            # Verify Celery task was called
            mock_task.assert_called_once()
    
    
    @pytest.mark.asyncio
    async def test_walkforward_missing_required_fields(self, async_client):
        """Test Walk-Forward with missing required fields"""
        invalid_request = {
            "symbol": "BTCUSDT"
            # Missing strategy_class, timeframe, dates, etc.
        }
        
        response = await async_client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    
    @pytest.mark.asyncio
    async def test_walkforward_invalid_date_range(self, async_client, valid_walkforward_request):
        """Test Walk-Forward with end_date before start_date"""
        invalid_request = valid_walkforward_request.copy()
        invalid_request["start_date"] = "2024-06-30T00:00:00"
        invalid_request["end_date"] = "2024-01-01T00:00:00"  # Invalid
        
        response = await async_client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        # Should fail validation (400/422) or raise server error (500)
        assert response.status_code in [400, 422, 500]
    
    
    @pytest.mark.asyncio
    async def test_walkforward_invalid_parameters(self, async_client, valid_walkforward_request):
        """Test Walk-Forward with invalid parameter ranges"""
        invalid_request = valid_walkforward_request.copy()
        invalid_request["parameters"] = {
            "fast_period": {"min": 20, "max": 10, "step": 5}  # min > max
        }
        
        response = await async_client.post("/api/v1/optimize/walk-forward", json=invalid_request)
        assert response.status_code in [400, 422]


# ============================================================================
# Bayesian Endpoint Tests
# ============================================================================

class TestBayesianEndpoint:
    """Test /api/v1/optimize/bayesian endpoint"""
    
    @pytest.mark.asyncio
    async def test_create_bayesian_optimization_success(self, async_client, valid_bayesian_request):
        """Test successful Bayesian optimization creation"""
        with patch('backend.tasks.optimize_tasks.bayesian_optimization_task.apply_async') as mock_task:
            # Mock Celery task
            mock_result = Mock()
            mock_result.id = "bayesian-task-456"
            mock_task.return_value = mock_result
            
            # Send request
            response = await async_client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            # Assertions
            assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
            data = response.json()
            
            assert "task_id" in data
            assert data["task_id"] == "bayesian-task-456"
            assert data["status"] == "PENDING"
            assert data["method"] == "bayesian"
            
            # Verify Celery task was called
            mock_task.assert_called_once()
    
    
    @pytest.mark.asyncio
    async def test_bayesian_missing_required_fields(self, async_client):
        """Test Bayesian with missing required fields"""
        invalid_request = {
            "symbol": "BTCUSDT"
            # Missing strategy_class, parameters, etc.
        }
        
        response = await async_client.post("/api/v1/optimize/bayesian", json=invalid_request)
        assert response.status_code == 422  # Validation error
    
    
    @pytest.mark.asyncio
    async def test_bayesian_invalid_n_trials(self, async_client, valid_bayesian_request):
        """Test Bayesian with invalid n_trials"""
        invalid_request = valid_bayesian_request.copy()
        invalid_request["n_trials"] = -10  # Negative
        
        response = await async_client.post("/api/v1/optimize/bayesian", json=invalid_request)
        assert response.status_code in [400, 422]
    
    
    @pytest.mark.asyncio
    async def test_bayesian_with_categorical_parameters(self, async_client, valid_bayesian_request):
        """Test Bayesian with categorical parameters"""
        request_with_categorical = valid_bayesian_request.copy()
        request_with_categorical["parameters"] = {
            "fast_period": {"type": "int", "low": 5, "high": 20},  # Corrected to use type, low, high
            "strategy_type": {"type": "categorical", "choices": ["aggressive", "conservative", "balanced"]}
        }
        
        with patch('backend.tasks.optimize_tasks.bayesian_optimization_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "bayesian-categorical-789"
            mock_task.return_value = mock_result
            
            response = await async_client.post("/api/v1/optimize/bayesian", json=request_with_categorical)
            
            # Should succeed
            assert response.status_code == 202
            data = response.json()
            assert data["task_id"] == "bayesian-categorical-789"


# ============================================================================
# Task Status Endpoint Tests
# ============================================================================

class TestTaskStatusEndpoint:
    """Test /api/v1/optimize/{task_id}/status endpoint"""
    
    @pytest.mark.asyncio
    async def test_get_status_pending(self, async_client):
        """Test getting status for pending task"""
        with patch('backend.services.optimization_service.AsyncResult') as mock_result:
            # Mock pending task
            mock_task_result = Mock()
            mock_task_result.state = "PENDING"
            mock_task_result.info = None
            mock_result.return_value = mock_task_result
            
            response = await async_client.get("/api/v1/optimize/test-task-123/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "PENDING"
    
    
    @pytest.mark.asyncio
    async def test_get_status_in_progress(self, async_client):
        """Test getting status for task in progress"""
        # Mock AsyncResult where it's imported (in optimization_service)
        with patch('backend.services.optimization_service.AsyncResult') as MockAsyncResult:
            # Mock task in progress
            mock_task_result = Mock()
            mock_task_result.state = "PROGRESS"
            mock_task_result.info = {
                "current": 25,
                "total": 100,
                "percent": 25.0,
                "message": "Testing combination 25 of 100"
            }
            MockAsyncResult.return_value = mock_task_result
            
            response = await async_client.get("/api/v1/optimize/test-task-456/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-456"
            assert data["status"] == "PROGRESS"
            assert "progress" in data
            assert data["progress"]["percent"] == 25.0


# ============================================================================
# Result Endpoint Tests
# ============================================================================

class TestResultEndpoint:
    """Test /api/v1/optimize/{task_id}/result endpoint"""
    
    @pytest.mark.asyncio
    async def test_get_result_not_completed(self, async_client):
        """Test getting result for task that's not completed yet"""
        with patch('backend.services.optimization_service.AsyncResult') as mock_result:
            # Mock pending task
            mock_task_result = Mock()
            mock_task_result.state = "PENDING"
            mock_task_result.result = None
            mock_result.return_value = mock_task_result
            
            response = await async_client.get("/api/v1/optimize/test-task-123/result")
            
            # Should return 404 - task not completed
            assert response.status_code == 404
    
    
    @pytest.mark.asyncio
    async def test_get_result_success(self, async_client):
        """Test getting result for completed task"""
        # Mock service layer directly with correct schema
        with patch('backend.services.optimization_service.OptimizationService.get_task_result') as mock_service:
            from backend.models.optimization_schemas import OptimizationResultsResponse, OptimizationResult
            
            # Create valid OptimizationResultsResponse matching backend schema
            mock_service.return_value = OptimizationResultsResponse(
                task_id="test-task-123",
                status="SUCCESS",
                method="bayesian",
                best_params={"fast_period": 10, "slow_period": 30},
                best_score=0.85,
                top_results=[
                    OptimizationResult(
                        params={"fast_period": 10, "slow_period": 30},
                        metrics={"sharpe_ratio": 0.85, "total_return": 0.45},
                        score=0.85,
                        rank=1
                    ),
                    OptimizationResult(
                        params={"fast_period": 15, "slow_period": 40},
                        metrics={"sharpe_ratio": 0.82, "total_return": 0.42},
                        score=0.82,
                        rank=2
                    )
                ],
                total_combinations=100,
                tested_combinations=50,
                execution_time=120.5,
                strategy_class="MA_Crossover",
                symbol="BTCUSDT",
                timeframe="15",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 6, 30)
            )
            
            response = await async_client.get("/api/v1/optimize/test-task-123/result")
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "SUCCESS"
            assert data["best_score"] == 0.85
            assert data["best_params"]["fast_period"] == 10
    
    
    @pytest.mark.asyncio
    async def test_get_result_failure(self, async_client):
        """Test getting result for failed task"""
        with patch('backend.services.optimization_service.AsyncResult') as mock_result:
            # Mock failed task
            mock_task_result = Mock()
            mock_task_result.state = "FAILURE"
            mock_task_result.result = Exception("Optimization failed: Invalid data")
            mock_task_result.info = str(mock_task_result.result)
            mock_result.return_value = mock_task_result
            
            response = await async_client.get("/api/v1/optimize/test-task-123/result")
            
            # Should return 404 for failed task (not completed successfully)
            assert response.status_code == 404


# ============================================================================
# Cancel Endpoint Tests
# ============================================================================

class TestCancelEndpoint:
    """Test /api/v1/optimize/{task_id} DELETE endpoint"""
    
    @pytest.mark.asyncio
    async def test_cancel_task_success(self, async_client):
        """Test successful task cancellation"""
        with patch('backend.celery_app.celery_app.control.revoke') as mock_revoke:
            # Mock service layer
            with patch('backend.services.optimization_service.OptimizationService.cancel_task') as mock_service:
                mock_service.return_value = {
                    "success": True,
                    "task_id": "test-task-123",
                    "message": "Task cancelled successfully"
                }
                
                response = await async_client.delete("/api/v1/optimize/test-task-123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] == True
                assert data["task_id"] == "test-task-123"
                assert "cancel" in data["message"].lower()
    
    
    @pytest.mark.asyncio
    async def test_cancel_already_completed_task(self, async_client):
        """Test cancelling a task that's already completed"""
        with patch('backend.services.optimization_service.OptimizationService.cancel_task') as mock_service:
            mock_service.return_value = {
                "success": False,
                "task_id": "test-task-456",
                "message": "Cannot cancel completed task"
            }
            
            response = await async_client.delete("/api/v1/optimize/test-task-456")
            
            # Should return 400 Bad Request
            assert response.status_code == 400


# ============================================================================
# Celery Task Mocking Verification
# ============================================================================

class TestCeleryTaskMocking:
    """Verify Celery task mocking works correctly"""
    
    @pytest.mark.asyncio
    async def test_celery_task_called_with_correct_params(self, async_client, valid_walkforward_request):
        """Verify Celery task is called with correct parameters"""
        with patch('backend.tasks.optimize_tasks.walk_forward_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "verify-task-999"
            mock_task.return_value = mock_result
            
            response = await async_client.post("/api/v1/optimize/walk-forward", json=valid_walkforward_request)
            
            assert response.status_code == 202
            
            # Verify task was called
            mock_task.assert_called_once()
            
            # Check call arguments
            call_kwargs = mock_task.call_args[1]
            assert "kwargs" in call_kwargs
            task_params = call_kwargs["kwargs"]
            assert task_params["symbol"] == "BTCUSDT"
            assert task_params["strategy_class"] == "MA_Crossover"
    
    
    @pytest.mark.asyncio
    async def test_multiple_tasks_create_different_ids(self, async_client, valid_bayesian_request):
        """Test that multiple task creations get different IDs"""
        with patch('backend.tasks.optimize_tasks.bayesian_optimization_task.apply_async') as mock_task:
            # First task
            mock_result_1 = Mock()
            mock_result_1.id = "task-1"
            mock_task.return_value = mock_result_1
            response1 = await async_client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            # Second task
            mock_result_2 = Mock()
            mock_result_2.id = "task-2"
            mock_task.return_value = mock_result_2
            response2 = await async_client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            
            assert response1.status_code == 202
            assert response2.status_code == 202
            
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
    
    @pytest.mark.asyncio
    async def test_very_large_parameter_space(self, async_client, valid_walkforward_request):
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
            
            response = await async_client.post("/api/v1/optimize/walk-forward", json=large_request)
            
            # Should succeed (backend will handle large space)
            assert response.status_code == 202
    
    
    @pytest.mark.asyncio
    async def test_empty_parameter_space(self, async_client, valid_walkforward_request):
        """Test with empty parameter space"""
        empty_request = valid_walkforward_request.copy()
        empty_request["parameters"] = {}
        
        response = await async_client.post("/api/v1/optimize/walk-forward", json=empty_request)
        
        # Should fail validation (422) or raise server error (500)
        assert response.status_code in [400, 422, 500]
    
    
    @pytest.mark.asyncio
    async def test_malformed_json(self, async_client):
        """Test with malformed JSON"""
        response = await async_client.post(
            "/api/v1/optimize/bayesian",
            content="{ this is not valid json }",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error


# ============================================================================
# Performance & Timeout Tests
# ============================================================================

class TestPerformance:
    """Test API performance and timeouts"""
    
    @pytest.mark.asyncio
    async def test_api_response_time(self, async_client, valid_bayesian_request):
        """Test that API responds quickly (mocked Celery)"""
        import time
        
        with patch('backend.tasks.optimize_tasks.bayesian_optimization_task.apply_async') as mock_task:
            mock_result = Mock()
            mock_result.id = "perf-test"
            mock_task.return_value = mock_result
            
            start = time.time()
            response = await async_client.post("/api/v1/optimize/bayesian", json=valid_bayesian_request)
            elapsed = time.time() - start
            
            assert response.status_code == 202
            # Should respond in less than 1 second (Celery is mocked)
            assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
