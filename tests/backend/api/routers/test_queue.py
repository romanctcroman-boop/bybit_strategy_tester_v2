"""
Test suite for backend/api/routers/queue.py

Week 5, Day 6: Queue Router Testing
- Target: 85%+ coverage
- Endpoints: run_backtest, create_and_run_backtest, run_optimization, get_queue_metrics, queue_health
- Mocking: Redis queue_adapter, DataService
- Challenges: Async queue operations, DataService context manager mocking
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.schemas import BacktestCreate


# Test client
client = TestClient(app)


@pytest.fixture
def mock_queue_adapter():
    """Mock queue_adapter with async methods"""
    with patch("backend.api.routers.queue.queue_adapter") as mock_adapter:
        # Mock async methods
        mock_adapter.submit_backtest = AsyncMock(return_value="task_123abc")
        mock_adapter.submit_grid_search = AsyncMock(return_value="task_grid_456")
        mock_adapter.submit_walk_forward = AsyncMock(return_value="task_wf_789")
        mock_adapter.submit_bayesian = AsyncMock(return_value="task_bayes_012")
        
        # Mock sync methods
        mock_adapter.get_metrics = MagicMock(return_value={
            "tasks_submitted": 100,
            "tasks_completed": 85,
            "tasks_failed": 5,
            "tasks_timeout": 2,
            "active_tasks": 8
        })
        mock_adapter._qm = MagicMock()  # Simulate Redis connection
        
        yield mock_adapter


@pytest.fixture
def mock_data_service():
    """Mock DataService with context manager delegation pattern"""
    
    class MockDataServiceClass:
        def __init__(self):
            self.instance = MagicMock()
            
        def __enter__(self):
            return self.instance
            
        def __exit__(self, *args):
            pass
    
    mock_ds_class = MockDataServiceClass()
    
    # DataService is imported inside functions, so patch where it's used
    with patch("backend.services.data_service.DataService", return_value=mock_ds_class):
        # Mock backtest
        mock_backtest = MagicMock()
        mock_backtest.id = 123
        mock_backtest.strategy_id = 1
        mock_backtest.symbol = "BTCUSDT"
        mock_backtest.timeframe = "15"
        mock_backtest.start_date = datetime(2024, 1, 1)
        mock_backtest.end_date = datetime(2024, 1, 31)
        mock_backtest.initial_capital = 10000.0
        mock_backtest.config = {"rsi_period": 14}
        
        # Mock strategy
        mock_strategy = MagicMock()
        mock_strategy.id = 1
        mock_strategy.name = "Test Strategy"
        
        # Mock optimization
        mock_optimization = MagicMock()
        mock_optimization.id = 42
        mock_optimization.strategy_id = 1
        mock_optimization.symbol = "BTCUSDT"
        mock_optimization.timeframe = "15"
        mock_optimization.start_date = datetime(2024, 1, 1)
        mock_optimization.end_date = datetime(2024, 1, 31)
        mock_optimization.strategy_config = {"leverage": 1}
        mock_optimization.param_space = {"rsi_period": [7, 14, 21]}
        mock_optimization.metric = "sharpe_ratio"
        
        # Configure instance methods
        mock_ds_class.instance.get_backtest = MagicMock(return_value=mock_backtest)
        mock_ds_class.instance.get_strategy = MagicMock(return_value=mock_strategy)
        mock_ds_class.instance.get_optimization = MagicMock(return_value=mock_optimization)
        mock_ds_class.instance.create_backtest = MagicMock(return_value=mock_backtest)
        
        yield mock_ds_class.instance


# ==================== Test run_backtest endpoint ====================

class TestRunBacktest:
    """Test POST /queue/backtest/run endpoint"""
    
    def test_run_backtest_success(self, mock_queue_adapter, mock_data_service):
        """Should submit backtest to queue successfully"""
        response = client.post(
            "/api/v1/queue/backtest/run",
            json={"backtest_id": 123, "priority": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_123abc"
        assert data["status"] == "submitted"
        assert "Backtest 123 submitted" in data["message"]
        
        # Verify queue_adapter called
        mock_queue_adapter.submit_backtest.assert_called_once()
        call_kwargs = mock_queue_adapter.submit_backtest.call_args.kwargs
        assert call_kwargs["backtest_id"] == 123
        assert call_kwargs["priority"] == 10
        assert call_kwargs["symbol"] == "BTCUSDT"
    
    def test_run_backtest_not_found(self, mock_queue_adapter, mock_data_service):
        """Should return 404 when backtest not found"""
        mock_data_service.get_backtest.return_value = None
        
        response = client.post(
            "/api/v1/queue/backtest/run",
            json={"backtest_id": 999, "priority": 5}
        )
        
        assert response.status_code == 404
        assert "Backtest 999 not found" in response.json()["detail"]
    
    def test_run_backtest_strategy_not_found(self, mock_queue_adapter, mock_data_service):
        """Should return 404 when strategy not found"""
        mock_data_service.get_strategy.return_value = None
        
        response = client.post(
            "/api/v1/queue/backtest/run",
            json={"backtest_id": 123, "priority": 5}
        )
        
        assert response.status_code == 404
        assert "Strategy" in response.json()["detail"]
    
    def test_run_backtest_default_priority(self, mock_queue_adapter, mock_data_service):
        """Should use default priority 5 when not specified"""
        response = client.post(
            "/api/v1/queue/backtest/run",
            json={"backtest_id": 123}
        )
        
        assert response.status_code == 200
        call_kwargs = mock_queue_adapter.submit_backtest.call_args.kwargs
        assert call_kwargs["priority"] == 5  # Default from schema
    
    def test_run_backtest_queue_error(self, mock_queue_adapter, mock_data_service):
        """Should return 500 when queue submission fails"""
        mock_queue_adapter.submit_backtest.side_effect = Exception("Redis connection failed")
        
        response = client.post(
            "/api/v1/queue/backtest/run",
            json={"backtest_id": 123, "priority": 10}
        )
        
        assert response.status_code == 500
        assert "Failed to submit backtest" in response.json()["detail"]


# ==================== Test create_and_run_backtest endpoint ====================

class TestCreateAndRunBacktest:
    """Test POST /queue/backtest/create-and-run endpoint"""
    
    def test_create_and_run_success(self, mock_queue_adapter, mock_data_service):
        """Should create backtest and submit to queue"""
        payload = {
            "strategy_id": 1,
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-01-31T23:59:59",
            "initial_capital": 10000.0,
            "leverage": 1,
            "commission": 0.0006,
            "config": {"rsi_period": 14}
        }
        
        response = client.post("/api/v1/queue/backtest/create-and-run", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["backtest_id"] == 123
        assert data["task_id"] == "task_123abc"
        assert data["status"] == "submitted"
        
        # Verify backtest created
        mock_data_service.create_backtest.assert_called_once()
        create_kwargs = mock_data_service.create_backtest.call_args.kwargs
        assert create_kwargs["strategy_id"] == 1
        assert create_kwargs["symbol"] == "BTCUSDT"
        assert create_kwargs["status"] == "queued"
        
        # Verify submitted to queue
        mock_queue_adapter.submit_backtest.assert_called_once()
    
    def test_create_and_run_strategy_not_found(self, mock_queue_adapter, mock_data_service):
        """Should return 404 when strategy doesn't exist"""
        mock_data_service.get_strategy.return_value = None
        
        payload = {
            "strategy_id": 999,
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-01-31T23:59:59",
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/queue/backtest/create-and-run", json=payload)
        
        assert response.status_code == 404
        assert "Strategy 999 not found" in response.json()["detail"]
    
    def test_create_and_run_validation_error(self, mock_queue_adapter, mock_data_service):
        """Should return 422 for invalid payload"""
        payload = {
            "strategy_id": 1,
            "symbol": "INVALID",  # Not matching pattern
            "timeframe": "15",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-01-31T23:59:59",
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/queue/backtest/create-and-run", json=payload)
        
        assert response.status_code == 422
    
    def test_create_and_run_high_priority(self, mock_queue_adapter, mock_data_service):
        """Should submit with high priority (10) by default"""
        payload = {
            "strategy_id": 1,
            "symbol": "BTCUSDT",
            "timeframe": "15",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-01-31T23:59:59",
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/queue/backtest/create-and-run", json=payload)
        
        assert response.status_code == 200
        call_kwargs = mock_queue_adapter.submit_backtest.call_args.kwargs
        assert call_kwargs["priority"] == 10  # HIGH priority for new backtests


# ==================== Test run_optimization endpoint ====================

class TestRunOptimization:
    """Test POST /queue/optimization/run endpoint"""
    
    def test_run_grid_search_success(self, mock_queue_adapter, mock_data_service):
        """Should submit grid search optimization"""
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 42,
                "optimization_type": "grid",
                "priority": 8
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_grid_456"
        assert data["status"] == "submitted"
        
        mock_queue_adapter.submit_grid_search.assert_called_once()
    
    def test_run_walk_forward_success(self, mock_queue_adapter, mock_data_service):
        """Should submit walk-forward optimization"""
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 42,
                "optimization_type": "walk_forward",
                "priority": 7
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_wf_789"
        
        mock_queue_adapter.submit_walk_forward.assert_called_once()
    
    def test_run_bayesian_success(self, mock_queue_adapter, mock_data_service):
        """Should submit bayesian optimization"""
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 42,
                "optimization_type": "bayesian",
                "priority": 6
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task_bayes_012"
        
        mock_queue_adapter.submit_bayesian.assert_called_once()
    
    def test_run_optimization_not_found(self, mock_queue_adapter, mock_data_service):
        """Should return 404 when optimization not found"""
        mock_data_service.get_optimization.return_value = None
        
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 999,
                "optimization_type": "grid",
                "priority": 5
            }
        )
        
        assert response.status_code == 404
        assert "Optimization 999 not found" in response.json()["detail"]
    
    def test_run_optimization_invalid_type(self, mock_queue_adapter, mock_data_service):
        """Should return 400 for invalid optimization type"""
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 42,
                "optimization_type": "invalid_type",
                "priority": 5
            }
        )
        
        assert response.status_code == 400
        assert "Invalid optimization type" in response.json()["detail"]
    
    def test_run_optimization_default_priority(self, mock_queue_adapter, mock_data_service):
        """Should use default priority 5"""
        response = client.post(
            "/api/v1/queue/optimization/run",
            json={
                "optimization_id": 42,
                "optimization_type": "grid"
            }
        )
        
        assert response.status_code == 200
        call_kwargs = mock_queue_adapter.submit_grid_search.call_args.kwargs
        assert call_kwargs["priority"] == 5


# ==================== Test get_queue_metrics endpoint ====================

class TestGetQueueMetrics:
    """Test GET /queue/metrics endpoint"""
    
    def test_get_metrics_success(self, mock_queue_adapter):
        """Should return queue metrics"""
        response = client.get("/api/v1/queue/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tasks_submitted"] == 100
        assert data["tasks_completed"] == 85
        assert data["tasks_failed"] == 5
        assert data["tasks_timeout"] == 2
        assert data["active_tasks"] == 8
        
        mock_queue_adapter.get_metrics.assert_called_once()
    
    def test_get_metrics_error(self, mock_queue_adapter):
        """Should return 500 when metrics retrieval fails"""
        mock_queue_adapter.get_metrics.side_effect = Exception("Redis unavailable")
        
        response = client.get("/api/v1/queue/metrics")
        
        assert response.status_code == 500
        assert "Failed to get queue metrics" in response.json()["detail"]


# ==================== Test queue_health endpoint ====================

class TestQueueHealth:
    """Test GET /queue/health endpoint"""
    
    def test_health_check_healthy(self, mock_queue_adapter):
        """Should return healthy status when Redis connected"""
        response = client.get("/api/v1/queue/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connected"] is True
        assert "metrics" in data
        assert data["metrics"]["tasks_submitted"] == 100
    
    def test_health_check_unhealthy_no_redis(self, mock_queue_adapter):
        """Should return unhealthy when Redis disconnected"""
        mock_queue_adapter._qm = None  # Simulate no Redis connection
        mock_queue_adapter.get_metrics.side_effect = Exception("Redis connection error")
        
        response = client.get("/api/v1/queue/health")
        
        assert response.status_code == 200  # Still returns 200, but status=unhealthy
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data
    
    def test_health_check_metrics_exception(self, mock_queue_adapter):
        """Should handle metrics exception gracefully"""
        mock_queue_adapter.get_metrics.side_effect = RuntimeError("Metrics unavailable")
        
        response = client.get("/api/v1/queue/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "Metrics unavailable" in data["error"]


# ============================================================================
# Additional Tests for 100% Coverage
# ============================================================================

class TestExceptionHandlers:
    """Tests for generic exception handlers (lines 192-194, 279-281)"""
    
    @patch("backend.queue.queue_adapter")
    @patch("backend.services.data_service.DataService")
    def test_create_and_run_generic_exception(self, mock_ds_class, mock_adapter):
        """Should catch generic Exception in create_and_run (covers lines 192-194)"""
        # Mock DataService to raise generic exception
        mock_ds_instance = MagicMock()
        mock_ds_instance.__enter__.side_effect = ConnectionError("Redis connection lost")
        mock_ds_instance.__exit__ = MagicMock(return_value=False)
        mock_ds_class.return_value = mock_ds_instance
        
        payload = {
            "strategy_id": 1,
            "symbol": "BTCUSDT",
            "timeframe": "60",  # 1h in minutes
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-12-31T23:59:59",
            "initial_capital": 10000
        }
        
        response = client.post("/api/v1/queue/backtest/create-and-run", json=payload)
        
        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()
    
    @patch("backend.queue.queue_adapter")
    @patch("backend.services.data_service.DataService")
    def test_run_optimization_generic_exception(self, mock_ds_class, mock_adapter):
        """Should catch generic Exception in run_optimization (covers lines 279-281)"""
        # Mock DataService to raise generic exception
        mock_ds_instance = MagicMock()
        mock_ds_instance.__enter__.side_effect = ValueError("Invalid parameter format")
        mock_ds_instance.__exit__ = MagicMock(return_value=False)
        mock_ds_class.return_value = mock_ds_instance
        
        payload = {
            "optimization_id": 456,
            "optimization_type": "grid",
            "priority": 5
        }
        
        response = client.post("/api/v1/queue/optimization/run", json=payload)
        
        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()
