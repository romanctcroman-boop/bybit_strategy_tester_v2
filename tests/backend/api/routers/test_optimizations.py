"""
Comprehensive tests for backend/api/routers/optimizations.py

Week 5 Day 4: optimizations.py router testing
Target: 35-40 tests, 70%+ coverage
Module: 170 statements, 10 endpoints + 4 utility functions

Test Coverage:
- GET /optimizations/ - list optimizations with filtering
- GET /optimizations/{id} - get single optimization
- POST /optimizations/ - create optimization
- PUT /optimizations/{id} - update optimization
- GET /optimizations/{id}/results - list optimization results
- GET /optimizations/{id}/results/best - get best result
- POST /optimizations/{id}/run/grid - enqueue grid search
- POST /optimizations/{id}/run/walk-forward - enqueue walk-forward optimization
- POST /optimizations/{id}/run/bayesian - enqueue bayesian optimization
- Utility functions (_to_iso_dict, _map_result, _choose_queue)

High Complexity Areas:
- Async job queue operations
- Optimization algorithm parameter validation
- Queue routing logic
- Result mapping and serialization
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

# ========================================================================
# FIXTURES AND MOCKS
# ========================================================================

@pytest.fixture
def app():
    """Create FastAPI app with optimizations router"""
    app = FastAPI()
    from backend.api.routers import optimizations
    app.include_router(optimizations.router, prefix="/optimizations", tags=["optimizations"])
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_data_service():
    """Mock DataService for testing with context manager support"""
    
    # Mock optimization object
    class MockOptimization:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.strategy_id = kwargs.get('strategy_id', 1)
            self.optimization_type = kwargs.get('optimization_type', 'grid_search')
            self.symbol = kwargs.get('symbol', 'BTCUSDT')
            self.timeframe = kwargs.get('timeframe', '1h')
            self.start_date = kwargs.get('start_date', datetime(2023, 1, 1, tzinfo=UTC))
            self.end_date = kwargs.get('end_date', datetime(2023, 12, 31, tzinfo=UTC))
            self.param_ranges = kwargs.get('param_ranges', {'rsi_period': [7, 14, 21]})
            self.metric = kwargs.get('metric', 'sharpe_ratio')
            self.initial_capital = kwargs.get('initial_capital', 10000.0)
            self.total_combinations = kwargs.get('total_combinations', 3)
            self.status = kwargs.get('status', 'queued')
            self.created_at = kwargs.get('created_at', datetime(2023, 1, 1, tzinfo=UTC))
            self.updated_at = kwargs.get('updated_at', datetime(2023, 1, 1, tzinfo=UTC))
            self.started_at = kwargs.get('started_at')
            self.completed_at = kwargs.get('completed_at')
            self.best_params = kwargs.get('best_params')
            self.best_score = kwargs.get('best_score')
            self.results = kwargs.get('results')
            
        @property
        def __dict__(self):
            return {
                'id': self.id,
                'strategy_id': self.strategy_id,
                'optimization_type': self.optimization_type,
                'symbol': self.symbol,
                'timeframe': self.timeframe,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'param_ranges': self.param_ranges,
                'metric': self.metric,
                'initial_capital': self.initial_capital,
                'total_combinations': self.total_combinations,
                'status': self.status,
                'created_at': self.created_at,
                'updated_at': self.updated_at,
                'started_at': self.started_at,
                'completed_at': self.completed_at,
                'best_params': self.best_params,
                'best_score': self.best_score,
                'results': self.results,
            }
    
    # Mock optimization result object
    class MockOptimizationResult:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.optimization_id = kwargs.get('optimization_id', 1)
            self.params = kwargs.get('params', {'rsi_period': 14})
            self.score = kwargs.get('score', 1.5)
            self.total_return = kwargs.get('total_return', 0.15)
            self.sharpe_ratio = kwargs.get('sharpe_ratio', 1.5)
            self.max_drawdown = kwargs.get('max_drawdown', 0.10)
            self.win_rate = kwargs.get('win_rate', 0.60)
            self.total_trades = kwargs.get('total_trades', 50)
            self.metrics = kwargs.get('metrics', {})
    
    # Create mock DataService instance with context manager support
    class MockDataServiceInstance:
        """Mock DataService instance that supports context manager protocol"""
        
        def __init__(self):
            self.MockOptimization = MockOptimization
            self.MockOptimizationResult = MockOptimizationResult
            
            # Mock methods
            self.get_optimizations = Mock(return_value=[
                MockOptimization(id=1, status='queued'),
                MockOptimization(id=2, status='running')
            ])
            self.get_optimization = Mock(return_value=MockOptimization(id=1, status='queued'))
            self.create_optimization = Mock(return_value=MockOptimization(id=1, status='queued'))
            self.update_optimization = Mock(return_value=MockOptimization(id=1, status='completed'))
            self.get_optimization_results = Mock(return_value=[
                MockOptimizationResult(id=1, score=1.5),
                MockOptimizationResult(id=2, score=1.3)
            ])
            self.get_best_optimization_result = Mock(return_value=MockOptimizationResult(id=1, score=1.5))
        
        def __enter__(self):
            """Enter context manager"""
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            """Exit context manager"""
            return False
    
    # Create callable class that returns MockDataServiceInstance
    class MockDataServiceClass:
        """Mock DataService class that can be called to create instances"""
        
        def __init__(self):
            self.instance = MockDataServiceInstance()
            # Expose mock classes for test access
            self.MockOptimization = MockOptimization
            self.MockOptimizationResult = MockOptimizationResult
            
            # Delegate all mock methods to instance for easier access in tests
            self.get_optimizations = self.instance.get_optimizations
            self.get_optimization = self.instance.get_optimization
            self.create_optimization = self.instance.create_optimization
            self.update_optimization = self.instance.update_optimization
            self.get_optimization_results = self.instance.get_optimization_results
            self.get_best_optimization_result = self.instance.get_best_optimization_result
        
        def __call__(self, *args, **kwargs):
            """Return the mock instance when called"""
            return self.instance
    
    return MockDataServiceClass()


# ========================================================================
# TEST: LIST OPTIMIZATIONS
# ========================================================================

class TestListOptimizations:
    """Test GET /optimizations/ endpoint"""
    
    def test_list_optimizations_success(self, client, mock_data_service):
        """Test successful optimization list retrieval"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/")
            
            assert response.status_code == 200
            data = response.json()
            assert 'items' in data
            assert 'total' in data
            assert data['total'] == 2
            assert len(data['items']) == 2
    
    def test_list_optimizations_with_strategy_filter(self, client, mock_data_service):
        """Test optimization list with strategy_id filter"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/?strategy_id=1")
            
            assert response.status_code == 200
            mock_data_service.instance.get_optimizations.assert_called_once()
            call_kwargs = mock_data_service.instance.get_optimizations.call_args[1]
            assert call_kwargs['strategy_id'] == 1
    
    def test_list_optimizations_with_status_filter(self, client, mock_data_service):
        """Test optimization list with status filter"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/?status=completed")
            
            assert response.status_code == 200
            call_kwargs = mock_data_service.instance.get_optimizations.call_args[1]
            assert call_kwargs['status'] == 'completed'
    
    def test_list_optimizations_with_pagination(self, client, mock_data_service):
        """Test optimization list with pagination parameters"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/?limit=50&offset=10")
            
            assert response.status_code == 200
            call_kwargs = mock_data_service.instance.get_optimizations.call_args[1]
            assert call_kwargs['limit'] == 50
            assert call_kwargs['offset'] == 10
    
    def test_list_optimizations_no_data_service(self, client):
        """Test list optimizations when DataService is unavailable"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=None):
            response = client.get("/optimizations/")
            
            assert response.status_code == 200
            data = response.json()
            assert data['items'] == []
            assert data['total'] == 0


# ========================================================================
# TEST: GET SINGLE OPTIMIZATION
# ========================================================================

class TestGetOptimization:
    """Test GET /optimizations/{id} endpoint"""
    
    def test_get_optimization_success(self, client, mock_data_service):
        """Test successful optimization retrieval"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/1")
            
            assert response.status_code == 200
            data = response.json()
            assert data['id'] == 1
            assert data['optimization_type'] == 'grid_search'
    
    def test_get_optimization_not_found(self, client, mock_data_service):
        """Test get optimization when optimization doesn't exist"""
        mock_data_service.instance.get_optimization = Mock(return_value=None)
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/999")
            
            assert response.status_code == 404
    
    def test_get_optimization_no_data_service(self, client):
        """Test get optimization when DataService is unavailable"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=None):
            response = client.get("/optimizations/1")
            
            assert response.status_code == 501


# ========================================================================
# TEST: CREATE OPTIMIZATION
# ========================================================================

class TestCreateOptimization:
    """Test POST /optimizations/ endpoint"""
    
    def test_create_optimization_success(self, client, mock_data_service):
        """Test successful optimization creation"""
        payload = {
            "strategy_id": 1,
            "optimization_type": "grid_search",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2023-01-01T00:00:00Z",
            "end_date": "2023-12-31T23:59:59Z",
            "param_ranges": {"rsi_period": [7, 14, 21]},
            "metric": "sharpe_ratio",
            "initial_capital": 10000.0,
            "total_combinations": 3
        }
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.post("/optimizations/", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data['id'] == 1
            assert data['optimization_type'] == 'grid_search'
    
    def test_create_optimization_no_data_service(self, client):
        """Test create optimization when DataService is unavailable"""
        payload = {
            "strategy_id": 1,
            "optimization_type": "grid_search",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2023-01-01T00:00:00Z",
            "end_date": "2023-12-31T23:59:59Z",
            "param_ranges": {"rsi_period": [7, 14, 21]},
            "metric": "sharpe_ratio",
            "initial_capital": 10000.0,
            "total_combinations": 3
        }
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=None):
            response = client.post("/optimizations/", json=payload)
            
            assert response.status_code == 501


# ========================================================================
# TEST: UPDATE OPTIMIZATION
# ========================================================================

class TestUpdateOptimization:
    """Test PUT /optimizations/{id} endpoint"""
    
    def test_update_optimization_success(self, client, mock_data_service):
        """Test successful optimization update"""
        payload = {
            "status": "completed",
            "best_score": 1.5,
            "best_params": {"rsi_period": 14}
        }
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.put("/optimizations/1", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'completed'
    
    def test_update_optimization_not_found(self, client, mock_data_service):
        """Test update optimization when optimization doesn't exist"""
        mock_data_service.instance.update_optimization = Mock(return_value=None)
        
        payload = {"status": "completed"}
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.put("/optimizations/999", json=payload)
            
            assert response.status_code == 404


# ========================================================================
# TEST: LIST OPTIMIZATION RESULTS
# ========================================================================

class TestListOptimizationResults:
    """Test GET /optimizations/{id}/results endpoint"""
    
    def test_list_results_success(self, client, mock_data_service):
        """Test successful results list retrieval"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/1/results")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]['score'] == 1.5
    
    def test_list_results_with_pagination(self, client, mock_data_service):
        """Test results list with pagination"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/1/results?limit=10&offset=5")
            
            assert response.status_code == 200
            call_kwargs = mock_data_service.instance.get_optimization_results.call_args[1]
            assert call_kwargs['limit'] == 10
            assert call_kwargs['offset'] == 5


# ========================================================================
# TEST: GET BEST OPTIMIZATION RESULT
# ========================================================================

class TestBestOptimizationResult:
    """Test GET /optimizations/{id}/results/best endpoint"""
    
    def test_get_best_result_success(self, client, mock_data_service):
        """Test successful best result retrieval"""
        # Set up mock to return valid result for any call
        result_obj = mock_data_service.MockOptimizationResult(
            id=1,
            optimization_id=1,
            params={"rsi_period": 14},
            score=1.5,
            total_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=0.10,
            win_rate=0.60,
            total_trades=50,
            metrics={"calmar_ratio": 1.2}
        )

        # IMPORTANT: Must set return_value explicitly and reset the mock
        mock_data_service.instance.get_best_optimization_result.reset_mock()
        mock_data_service.instance.get_best_optimization_result.return_value = result_obj

        # We need to mock at MODULE level, not return level
        import backend.api.routers.optimizations as opt_module
        with patch.object(opt_module, '_get_data_service', return_value=mock_data_service):
            # FIX: The correct route is /{optimization_id}/best, NOT /results/best
            response = client.get("/optimizations/1/best")

            assert response.status_code == 200
            data = response.json()
            assert 'score' in data
            assert data['score'] == 1.5
    
    def test_get_best_result_not_found(self, client, mock_data_service):
        """Test get best result when no results exist"""
        mock_data_service.instance.get_best_optimization_result = Mock(return_value=None)
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            # FIX: The correct route is /{optimization_id}/best, NOT /results/best
            response = client.get("/optimizations/1/best")
            
            assert response.status_code == 404


# ========================================================================
# TEST: UTILITY FUNCTIONS
# ========================================================================

class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_choose_queue_with_custom_queue(self):
        """Test _choose_queue with custom queue name"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue("custom_queue", "grid_search")
        assert result == "custom_queue"
    
    def test_choose_queue_grid_search(self):
        """Test _choose_queue for grid search algorithm"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue(None, "grid_search")
        assert result == "optimizations.grid"
    
    def test_choose_queue_walk_forward(self):
        """Test _choose_queue for walk-forward algorithm"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue(None, "walk_forward")
        assert result == "optimizations.walk"
    
    def test_choose_queue_bayesian(self):
        """Test _choose_queue for bayesian algorithm"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue(None, "bayesian")
        assert result == "optimizations.bayes"
    
    def test_choose_queue_unknown_algo(self):
        """Test _choose_queue for unknown algorithm"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue(None, "unknown")
        assert result == "optimizations"
    
    def test_choose_queue_with_whitespace(self):
        """Test _choose_queue trims whitespace from custom queue"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue("  priority_queue  ", "grid_search")
        assert result == "priority_queue"
    
    def test_choose_queue_with_empty_string(self):
        """Test _choose_queue treats empty string as None"""
        from backend.api.routers.optimizations import _choose_queue
        
        result = _choose_queue("", "grid_search")
        assert result == "optimizations.grid"
    
    def test_to_iso_dict_with_datetime_fields(self):
        """Test _to_iso_dict converts datetime fields to ISO format"""
        from backend.api.routers.optimizations import _to_iso_dict
        from datetime import datetime, UTC
        
        class MockObj:
            def __init__(self):
                self.id = 1
                self.created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
                self.updated_at = datetime(2023, 1, 2, 13, 30, 0, tzinfo=UTC)
                self.name = "test"
        
        obj = MockObj()
        result = _to_iso_dict(obj)
        
        assert result['id'] == 1
        assert result['name'] == "test"
        assert result['created_at'] == "2023-01-01T12:00:00+00:00"
        assert result['updated_at'] == "2023-01-02T13:30:00+00:00"
    
    def test_to_iso_dict_without_datetime(self):
        """Test _to_iso_dict with no datetime fields"""
        from backend.api.routers.optimizations import _to_iso_dict
        
        class MockObj:
            def __init__(self):
                self.id = 1
                self.name = "test"
                self.score = 1.5
        
        obj = MockObj()
        result = _to_iso_dict(obj)
        
        assert result == {'id': 1, 'name': "test", 'score': 1.5}
    
    def test_map_result_basic_fields(self):
        """Test _map_result extracts all result fields"""
        from backend.api.routers.optimizations import _map_result
        
        class MockResult:
            def __init__(self):
                self.id = 1
                self.optimization_id = 10
                self.params = {"rsi_period": 14}
                self.score = 1.5
                self.total_return = 0.15
                self.sharpe_ratio = 1.5
                self.max_drawdown = 0.10
                self.win_rate = 0.60
                self.total_trades = 50
                self.metrics = {"calmar_ratio": 1.2}
        
        result = _map_result(MockResult())
        
        assert result['id'] == 1
        assert result['optimization_id'] == 10
        assert result['params'] == {"rsi_period": 14}
        assert result['score'] == 1.5
        assert result['total_return'] == 0.15
        assert result['sharpe_ratio'] == 1.5
        assert result['max_drawdown'] == 0.10
        assert result['win_rate'] == 0.60
        assert result['total_trades'] == 50
        assert result['metrics'] == {"calmar_ratio": 1.2}
    
    def test_map_result_with_datetime_in_metrics(self):
        """Test _map_result converts datetime in metrics dict"""
        from backend.api.routers.optimizations import _map_result
        from datetime import datetime, UTC
        
        class MockResult:
            def __init__(self):
                self.id = 1
                self.optimization_id = 10
                self.params = {}
                self.score = 1.5
                self.total_return = None
                self.sharpe_ratio = None
                self.max_drawdown = None
                self.win_rate = None
                self.total_trades = None
                self.metrics = {
                    "last_trade_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
                    "calmar_ratio": 1.2
                }
        
        result = _map_result(MockResult())
        
        assert result['metrics']['last_trade_time'] == "2023-01-01T12:00:00+00:00"
        assert result['metrics']['calmar_ratio'] == 1.2
    
    def test_map_result_with_missing_fields(self):
        """Test _map_result handles missing attributes gracefully"""
        from backend.api.routers.optimizations import _map_result
        
        class MinimalResult:
            id = 1
        
        result = _map_result(MinimalResult())
        
        assert result['id'] == 1
        assert result['optimization_id'] is None
        assert result['params'] is None
        assert result['metrics'] is None
    
    def test_map_result_with_none_metrics(self):
        """Test _map_result when metrics is None"""
        from backend.api.routers.optimizations import _map_result
        
        class MockResult:
            id = 1
            optimization_id = 10
            params = {}
            score = 1.5
            total_return = 0.15
            sharpe_ratio = 1.5
            max_drawdown = 0.10
            win_rate = 0.60
            total_trades = 50
            metrics = None
        
        result = _map_result(MockResult())
        
        assert result['metrics'] is None


# ========================================================================
# CELERY TASK ENQUEUE ENDPOINTS
# ========================================================================

class TestEnqueueGridSearch:
    """Test POST /optimizations/{id}/run/grid endpoint"""
    
    def test_enqueue_grid_search_success(self, client, mock_data_service):
        """Test successful grid search task enqueue"""
        from backend.api.routers.optimizations import _get_data_service
        
        # Mock Celery task AT IMPORT LEVEL (inside the endpoint function)
        mock_task = Mock()
        mock_async_result = Mock()
        mock_async_result.id = "task-12345-grid"
        mock_task.apply_async.return_value = mock_async_result
        
        # Create mock module for optimize_tasks
        mock_optimize_module = Mock()
        mock_optimize_module.grid_search_task = mock_task
        
        # Mock get_optimization
        mock_optimization = Mock()
        mock_optimization.symbol = "BTCUSDT"
        mock_optimization.timeframe = "1h"
        mock_optimization.start_date = datetime(2023, 1, 1, tzinfo=UTC)
        mock_optimization.end_date = datetime(2023, 12, 31, tzinfo=UTC)
        mock_optimization.metric = "sharpe_ratio"
        mock_optimization.config = {"strategy": "bollinger"}
        mock_optimization.param_ranges = {"rsi_period": [7, 14, 21]}
        mock_data_service.instance.get_optimization.return_value = mock_optimization
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            # Patch the import inside the endpoint function
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'metric': 'total_return',
                    'strategy_config': {'param1': 'value1'},
                    'param_space': {'fast_period': [5, 10, 15]},
                    'queue': None
                }
                
                response = client.post("/optimizations/1/run/grid", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['task_id'] == "task-12345-grid"
                assert data['optimization_id'] == 1
                assert data['queue'] == "optimizations.grid"
                assert data['status'] == "queued"
                
                # Verify task was called
                mock_task.apply_async.assert_called_once()
                call_kwargs = mock_task.apply_async.call_args[1]['kwargs']
                assert call_kwargs['optimization_id'] == 1
                assert call_kwargs['metric'] == 'total_return'
                assert call_kwargs['symbol'] == "BTCUSDT"
    
    def test_enqueue_grid_search_optimization_not_found(self, client, mock_data_service):
        """Test grid search enqueue when optimization not found"""
        mock_data_service.instance.get_optimization.return_value = None
        
        mock_task = Mock()
        mock_optimize_module = Mock()
        mock_optimize_module.grid_search_task = mock_task
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {'strategy_config': {}, 'param_space': {}}
                
                response = client.post("/optimizations/999/run/grid", json=payload)
                
                assert response.status_code == 404
                assert 'optimization not found' in response.json()['detail'].lower()
    
    def test_enqueue_grid_search_custom_queue(self, client, mock_data_service):
        """Test grid search with custom queue name"""
        mock_task = Mock()
        mock_async_result = Mock()
        mock_async_result.id = "task-67890-grid"
        mock_task.apply_async.return_value = mock_async_result
        
        mock_optimize_module = Mock()
        mock_optimize_module.grid_search_task = mock_task
        
        mock_optimization = Mock()
        mock_optimization.symbol = "ETHUSDT"
        mock_optimization.timeframe = "4h"
        mock_optimization.start_date = datetime(2023, 1, 1, tzinfo=UTC)
        mock_optimization.end_date = datetime(2023, 6, 30, tzinfo=UTC)
        mock_optimization.metric = "total_return"
        mock_optimization.config = {}
        mock_optimization.param_ranges = {}
        mock_data_service.instance.get_optimization.return_value = mock_optimization
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'queue': 'priority_optimizations'
                }
                
                response = client.post("/optimizations/1/run/grid", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['queue'] == 'priority_optimizations'
    
    def test_enqueue_grid_search_celery_not_available(self, client, mock_data_service):
        """Test grid search enqueue when Celery not available"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': None}):
                payload = {'strategy_config': {}, 'param_space': {}}
                
                response = client.post("/optimizations/1/run/grid", json=payload)
                
                assert response.status_code == 501
                assert 'celery tasks not available' in response.json()['detail'].lower()


class TestEnqueueWalkForward:
    """Test POST /optimizations/{id}/run/walk-forward endpoint"""
    
    def test_enqueue_walk_forward_success(self, client, mock_data_service):
        """Test successful walk-forward task enqueue"""
        mock_task = Mock()
        mock_async_result = Mock()
        mock_async_result.id = "task-wf-123"
        mock_task.apply_async.return_value = mock_async_result
        
        mock_optimize_module = Mock()
        mock_optimize_module.walk_forward_task = mock_task
        
        mock_optimization = Mock()
        mock_optimization.symbol = "BTCUSDT"
        mock_optimization.timeframe = "1d"
        mock_optimization.start_date = datetime(2022, 1, 1, tzinfo=UTC)
        mock_optimization.end_date = datetime(2023, 12, 31, tzinfo=UTC)
        mock_optimization.metric = "sharpe_ratio"
        mock_optimization.config = {}
        mock_optimization.param_ranges = {}
        mock_data_service.instance.get_optimization.return_value = mock_optimization
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'train_size': 180,
                    'test_size': 30,
                    'step_size': 15,
                    'metric': 'total_return',
                    'queue': None
                }
                
                response = client.post("/optimizations/2/run/walk-forward", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['task_id'] == "task-wf-123"
                assert data['optimization_id'] == 2
                assert data['queue'] == "optimizations.walk"
                assert data['status'] == "queued"
                
                # Verify walk-forward specific params passed
                call_kwargs = mock_task.apply_async.call_args[1]['kwargs']
                assert call_kwargs['train_size'] == 180
                assert call_kwargs['test_size'] == 30
                assert call_kwargs['step_size'] == 15
    
    def test_enqueue_walk_forward_optimization_not_found(self, client, mock_data_service):
        """Test walk-forward enqueue when optimization not found"""
        mock_data_service.instance.get_optimization.return_value = None
        
        mock_task = Mock()
        mock_optimize_module = Mock()
        mock_optimize_module.walk_forward_task = mock_task
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'train_size': 180,
                    'test_size': 30,
                    'step_size': 15
                }
                
                response = client.post("/optimizations/999/run/walk-forward", json=payload)
                
                assert response.status_code == 404
    
    def test_enqueue_walk_forward_celery_not_available(self, client, mock_data_service):
        """Test walk-forward enqueue when Celery not available"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': None}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'train_size': 180,
                    'test_size': 30,
                    'step_size': 15
                }
                
                response = client.post("/optimizations/2/run/walk-forward", json=payload)
                
                assert response.status_code == 501
                assert 'celery' in response.json()['detail'].lower()


class TestEnqueueBayesian:
    """Test POST /optimizations/{id}/run/bayesian endpoint"""
    
    def test_enqueue_bayesian_success(self, client, mock_data_service):
        """Test successful Bayesian optimization task enqueue"""
        mock_task = Mock()
        mock_async_result = Mock()
        mock_async_result.id = "task-bayes-456"
        mock_task.apply_async.return_value = mock_async_result
        
        mock_optimize_module = Mock()
        mock_optimize_module.bayesian_optimization_task = mock_task
        
        mock_optimization = Mock()
        mock_optimization.symbol = "ETHUSDT"
        mock_optimization.timeframe = "4h"
        mock_optimization.start_date = datetime(2023, 1, 1, tzinfo=UTC)
        mock_optimization.end_date = datetime(2023, 6, 30, tzinfo=UTC)
        mock_optimization.metric = "sharpe_ratio"
        mock_optimization.config = {"strategy": "rsi"}
        mock_optimization.param_ranges = {}
        mock_data_service.instance.get_optimization.return_value = mock_optimization
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'strategy_config': {"param": "value"},
                    'param_space': {
                        "rsi_period": {"type": "int", "low": 10, "high": 20}
                    },
                    'n_trials': 100,
                    'direction': 'maximize',
                    'metric': 'profit_factor',
                    'n_jobs': 4,
                    'random_state': 42
                }
                
                response = client.post("/optimizations/3/run/bayesian", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['task_id'] == "task-bayes-456"
                assert data['optimization_id'] == 3
                assert data['queue'] == "optimizations"  # Default from schema
                assert data['status'] == "queued"
                
                # Verify Bayesian-specific params passed
                call_kwargs = mock_task.apply_async.call_args[1]['kwargs']
                assert call_kwargs['n_trials'] == 100
                assert call_kwargs['direction'] == 'maximize'
                assert call_kwargs['n_jobs'] == 4
                assert call_kwargs['random_state'] == 42
                assert call_kwargs['metric'] == 'profit_factor'
    
    def test_enqueue_bayesian_optimization_not_found(self, client, mock_data_service):
        """Test Bayesian enqueue when optimization not found"""
        mock_data_service.instance.get_optimization.return_value = None
        
        mock_task = Mock()
        mock_optimize_module = Mock()
        mock_optimize_module.bayesian_optimization_task = mock_task
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': mock_optimize_module}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'n_trials': 50,
                    'direction': 'maximize'
                }
                
                response = client.post("/optimizations/999/run/bayesian", json=payload)
                
                assert response.status_code == 404
    
    def test_enqueue_bayesian_celery_not_available(self, client, mock_data_service):
        """Test Bayesian enqueue when Celery not available"""
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            with patch.dict('sys.modules', {'backend.tasks.optimize_tasks': None}):
                payload = {
                    'strategy_config': {},
                    'param_space': {},
                    'n_trials': 50,
                    'direction': 'maximize'
                }
                
                response = client.post("/optimizations/3/run/bayesian", json=payload)
                
                assert response.status_code == 501


# ========================================================================
# TEST: ADDITIONAL EDGE CASES FOR 95%+ COVERAGE
# ========================================================================

class TestEdgeCasesForCoverage:
    """Test edge cases to reach 95%+ coverage (focusing on reachable lines)"""
    
    def test_update_optimization_not_found(self, client, mock_data_service):
        """Test update_optimization returns 404 when not found (line 142)"""
        mock_data_service.update_optimization.return_value = None
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.put("/optimizations/999", json={"status": "completed"})
            assert response.status_code == 404
    
    def test_best_optimization_result_not_found(self, client, mock_data_service):
        """Test best_optimization_result returns 404 when not found (line 177)"""
        mock_data_service.get_best_optimization_result.return_value = None
        
        with patch('backend.api.routers.optimizations._get_data_service', return_value=mock_data_service):
            response = client.get("/optimizations/999/best")
            assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
