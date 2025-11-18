"""
Comprehensive tests for backend/queue/adapter.py

Queue adapter для замены Celery на Redis Streams
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from backend.queue.adapter import QueueAdapter, get_queue_adapter, queue_adapter
from backend.queue.redis_queue_manager import TaskPriority


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis_manager():
    """Mock RedisQueueManager"""
    manager = AsyncMock()
    manager.connect = AsyncMock()
    manager.submit_task = AsyncMock(return_value="test-task-id-123")
    manager.get_task_status = AsyncMock(return_value={
        "task_id": "test-task-id-123",
        "status": "completed",
        "result": {"success": True}
    })
    manager.get_metrics = Mock(return_value={
        "tasks_submitted": 10,
        "tasks_completed": 8,
        "tasks_failed": 1,
        "tasks_timeout": 1,
        "active_tasks": 2
    })
    manager.disconnect = AsyncMock()
    return manager


@pytest.fixture
def adapter():
    """Create QueueAdapter instance"""
    return QueueAdapter(redis_url="redis://localhost:6379/0")


@pytest.fixture
def backtest_params():
    """Sample backtest parameters"""
    return {
        "backtest_id": 1,
        "strategy_config": {"strategy": "bollinger", "bb_period": 20},
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 10000.0,
    }


@pytest.fixture
def optimization_params():
    """Sample optimization parameters"""
    return {
        "optimization_id": 1,
        "strategy_config": {"strategy": "rsi"},
        "param_space": {"rsi_period": [10, 14, 20], "rsi_oversold": [20, 30]},
        "symbol": "ETHUSDT",
        "interval": "4h",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "metric": "sharpe_ratio",
    }


# ============================================================================
# Test QueueAdapter.__init__
# ============================================================================

class TestAdapterInit:
    """Test adapter initialization"""
    
    def test_init_default_url(self):
        """Test init with default Redis URL"""
        adapter = QueueAdapter()
        assert adapter.redis_url == "redis://localhost:6379/0"
        assert adapter._qm is None
        assert adapter._loop is None
    
    def test_init_custom_url(self):
        """Test init with custom Redis URL"""
        adapter = QueueAdapter(redis_url="redis://custom:6380/1")
        assert adapter.redis_url == "redis://custom:6380/1"
        assert adapter._qm is None


# ============================================================================
# Test _get_or_create_loop
# ============================================================================

class TestGetOrCreateLoop:
    """Test event loop management"""
    
    @pytest.mark.asyncio
    async def test_get_existing_loop(self, adapter):
        """Test getting existing event loop"""
        loop = adapter._get_or_create_loop()
        assert loop is not None
    
    def test_create_new_loop_when_none(self, adapter):
        """Test creating new loop when none exists"""
        with patch('asyncio.get_event_loop', side_effect=RuntimeError("no loop")):
            with patch('asyncio.new_event_loop') as mock_new:
                with patch('asyncio.set_event_loop') as mock_set:
                    mock_loop = Mock()
                    mock_new.return_value = mock_loop
                    
                    loop = adapter._get_or_create_loop()
                    
                    mock_new.assert_called_once()
                    mock_set.assert_called_once_with(mock_loop)
                    assert loop == mock_loop


# ============================================================================
# Test _ensure_connected
# ============================================================================

class TestEnsureConnected:
    """Test Redis connection management"""
    
    @pytest.mark.asyncio
    async def test_ensure_connected_first_time(self, adapter, mock_redis_manager):
        """Test connecting to Redis first time"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            await adapter._ensure_connected()
            
            assert adapter._qm is mock_redis_manager
            mock_redis_manager.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_connected_already_connected(self, adapter, mock_redis_manager):
        """Test ensure_connected when already connected"""
        adapter._qm = mock_redis_manager
        
        await adapter._ensure_connected()
        
        # Should not create new connection
        mock_redis_manager.connect.assert_not_called()


# ============================================================================
# Test submit_backtest
# ============================================================================

class TestSubmitBacktest:
    """Test backtest submission"""
    
    @pytest.mark.asyncio
    async def test_submit_backtest_success(self, adapter, mock_redis_manager, backtest_params):
        """Test successful backtest submission"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_backtest(**backtest_params)
            
            assert task_id == "test-task-id-123"
            mock_redis_manager.connect.assert_called_once()
            mock_redis_manager.submit_task.assert_called_once_with(
                task_type="backtest",
                payload={
                    "backtest_id": 1,
                    "strategy_config": {"strategy": "bollinger", "bb_period": 20},
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "initial_capital": 10000.0,
                },
                priority=TaskPriority.NORMAL.value,
                max_retries=3,
                timeout_seconds=3600,
            )
    
    @pytest.mark.asyncio
    async def test_submit_backtest_custom_priority(self, adapter, mock_redis_manager, backtest_params):
        """Test backtest submission with custom priority"""
        backtest_params["priority"] = TaskPriority.HIGH.value
        
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_backtest(**backtest_params)
            
            # Check priority was passed correctly
            call_kwargs = mock_redis_manager.submit_task.call_args[1]
            assert call_kwargs["priority"] == TaskPriority.HIGH.value


# ============================================================================
# Test submit_grid_search
# ============================================================================

class TestSubmitGridSearch:
    """Test grid search optimization submission"""
    
    @pytest.mark.asyncio
    async def test_submit_grid_search_success(self, adapter, mock_redis_manager, optimization_params):
        """Test successful grid search submission"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_grid_search(**optimization_params)
            
            assert task_id == "test-task-id-123"
            mock_redis_manager.submit_task.assert_called_once()
            
            call_kwargs = mock_redis_manager.submit_task.call_args[1]
            assert call_kwargs["task_type"] == "optimization"
            assert call_kwargs["payload"]["optimization_type"] == "grid"
            assert call_kwargs["payload"]["optimization_id"] == 1
            assert call_kwargs["timeout_seconds"] == 7200  # 2 hours


# ============================================================================
# Test submit_walk_forward
# ============================================================================

class TestSubmitWalkForward:
    """Test walk-forward optimization submission"""
    
    @pytest.mark.asyncio
    async def test_submit_walk_forward_default_params(self, adapter, mock_redis_manager, optimization_params):
        """Test walk-forward with default window params"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_walk_forward(**optimization_params)
            
            assert task_id == "test-task-id-123"
            
            call_kwargs = mock_redis_manager.submit_task.call_args[1]
            payload = call_kwargs["payload"]
            assert payload["optimization_type"] == "walk_forward"
            assert payload["train_size"] == 120
            assert payload["test_size"] == 60
            assert payload["step_size"] == 30
    
    @pytest.mark.asyncio
    async def test_submit_walk_forward_custom_windows(self, adapter, mock_redis_manager, optimization_params):
        """Test walk-forward with custom window sizes"""
        optimization_params.update({
            "train_size": 180,
            "test_size": 90,
            "step_size": 45,
        })
        
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_walk_forward(**optimization_params)
            
            payload = mock_redis_manager.submit_task.call_args[1]["payload"]
            assert payload["train_size"] == 180
            assert payload["test_size"] == 90
            assert payload["step_size"] == 45


# ============================================================================
# Test submit_bayesian
# ============================================================================

class TestSubmitBayesian:
    """Test Bayesian optimization submission"""
    
    @pytest.mark.asyncio
    async def test_submit_bayesian_default_params(self, adapter, mock_redis_manager):
        """Test Bayesian optimization with defaults"""
        params = {
            "optimization_id": 1,
            "strategy_config": {"strategy": "rsi"},
            "param_space": {
                "rsi_period": {"type": "int", "low": 10, "high": 20},
                "rsi_oversold": {"type": "int", "low": 20, "high": 40},
            },
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_bayesian(**params)
            
            assert task_id == "test-task-id-123"
            
            payload = mock_redis_manager.submit_task.call_args[1]["payload"]
            assert payload["optimization_type"] == "bayesian"
            assert payload["n_trials"] == 100
            assert payload["direction"] == "maximize"
    
    @pytest.mark.asyncio
    async def test_submit_bayesian_custom_trials(self, adapter, mock_redis_manager):
        """Test Bayesian with custom n_trials"""
        params = {
            "optimization_id": 1,
            "strategy_config": {"strategy": "rsi"},
            "param_space": {"rsi_period": {"type": "int", "low": 10, "high": 20}},
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "n_trials": 50,
            "direction": "minimize",
        }
        
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            task_id = await adapter.submit_bayesian(**params)
            
            payload = mock_redis_manager.submit_task.call_args[1]["payload"]
            assert payload["n_trials"] == 50
            assert payload["direction"] == "minimize"


# ============================================================================
# Test get_task_status
# ============================================================================

class TestGetTaskStatus:
    """Test task status retrieval"""
    
    @pytest.mark.asyncio
    async def test_get_task_status_success(self, adapter, mock_redis_manager):
        """Test getting task status"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            await adapter._ensure_connected()
            status = await adapter.get_task_status("test-task-id-123")
            
            assert status["task_id"] == "test-task-id-123"
            assert status["status"] == "completed"
            assert status["result"]["success"] is True
            mock_redis_manager.get_task_status.assert_called_once_with("test-task-id-123")


# ============================================================================
# Test get_metrics
# ============================================================================

class TestGetMetrics:
    """Test metrics retrieval"""
    
    def test_get_metrics_not_connected(self, adapter):
        """Test metrics when not connected"""
        metrics = adapter.get_metrics()
        
        assert metrics["tasks_submitted"] == 0
        assert metrics["tasks_completed"] == 0
        assert metrics["tasks_failed"] == 0
        assert metrics["tasks_timeout"] == 0
        assert metrics["active_tasks"] == 0
    
    def test_get_metrics_connected(self, adapter, mock_redis_manager):
        """Test metrics when connected"""
        adapter._qm = mock_redis_manager
        
        metrics = adapter.get_metrics()
        
        assert metrics["tasks_submitted"] == 10
        assert metrics["tasks_completed"] == 8
        assert metrics["tasks_failed"] == 1
        assert metrics["tasks_timeout"] == 1
        assert metrics["active_tasks"] == 2


# ============================================================================
# Test disconnect
# ============================================================================

class TestDisconnect:
    """Test disconnection"""
    
    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, adapter, mock_redis_manager):
        """Test disconnecting when connected"""
        adapter._qm = mock_redis_manager
        
        await adapter.disconnect()
        
        mock_redis_manager.disconnect.assert_called_once()
        assert adapter._qm is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, adapter):
        """Test disconnecting when not connected"""
        await adapter.disconnect()  # Should not raise


# ============================================================================
# Test Sync Wrappers
# ============================================================================

class TestSyncWrappers:
    """Test synchronous wrapper methods"""
    
    def test_submit_backtest_sync(self, adapter, backtest_params):
        """Test sync wrapper for submit_backtest"""
        with patch.object(adapter, '_get_or_create_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.run_until_complete = Mock(return_value="sync-task-id")
            mock_get_loop.return_value = mock_loop
            
            task_id = adapter.submit_backtest_sync(**backtest_params)
            
            assert task_id == "sync-task-id"
            mock_loop.run_until_complete.assert_called_once()
    
    def test_submit_grid_search_sync(self, adapter, optimization_params):
        """Test sync wrapper for submit_grid_search"""
        with patch.object(adapter, '_get_or_create_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.run_until_complete = Mock(return_value="sync-grid-id")
            mock_get_loop.return_value = mock_loop
            
            task_id = adapter.submit_grid_search_sync(**optimization_params)
            
            assert task_id == "sync-grid-id"
    
    def test_submit_walk_forward_sync(self, adapter, optimization_params):
        """Test sync wrapper for submit_walk_forward"""
        with patch.object(adapter, '_get_or_create_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.run_until_complete = Mock(return_value="sync-wf-id")
            mock_get_loop.return_value = mock_loop
            
            task_id = adapter.submit_walk_forward_sync(**optimization_params)
            
            assert task_id == "sync-wf-id"
    
    def test_submit_bayesian_sync(self, adapter):
        """Test sync wrapper for submit_bayesian"""
        params = {
            "optimization_id": 1,
            "strategy_config": {"strategy": "rsi"},
            "param_space": {"rsi_period": {"type": "int", "low": 10, "high": 20}},
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }
        
        with patch.object(adapter, '_get_or_create_loop') as mock_get_loop:
            mock_loop = Mock()
            mock_loop.run_until_complete = Mock(return_value="sync-bayesian-id")
            mock_get_loop.return_value = mock_loop
            
            task_id = adapter.submit_bayesian_sync(**params)
            
            assert task_id == "sync-bayesian-id"


# ============================================================================
# Test Global Singleton
# ============================================================================

class TestGlobalSingleton:
    """Test global singleton pattern"""
    
    def test_get_queue_adapter_creates_instance(self):
        """Test get_queue_adapter creates singleton"""
        with patch('backend.queue.adapter._queue_adapter', None):
            with patch.dict('os.environ', {'REDIS_URL': 'redis://test:6379/0'}):
                adapter = get_queue_adapter()
                
                assert adapter is not None
                assert isinstance(adapter, QueueAdapter)
                assert adapter.redis_url == 'redis://test:6379/0'
    
    def test_get_queue_adapter_returns_same_instance(self):
        """Test get_queue_adapter returns same instance"""
        with patch('backend.queue.adapter._queue_adapter', None):
            adapter1 = get_queue_adapter()
            adapter2 = get_queue_adapter()
            
            # Should be the same object
            assert adapter1 is adapter2
    
    def test_queue_adapter_alias(self):
        """Test queue_adapter is alias for get_queue_adapter"""
        # queue_adapter should be callable or instance
        assert queue_adapter is not None


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_multiple_ensure_connected_calls(self, adapter, mock_redis_manager):
        """Test multiple ensure_connected calls don't reconnect"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            await adapter._ensure_connected()
            await adapter._ensure_connected()
            await adapter._ensure_connected()
            
            # Should only connect once
            mock_redis_manager.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_submit_with_all_priorities(self, adapter, mock_redis_manager, backtest_params):
        """Test submitting tasks with different priorities"""
        with patch('backend.queue.adapter.RedisQueueManager', return_value=mock_redis_manager):
            priorities = [TaskPriority.LOW.value, TaskPriority.NORMAL.value, TaskPriority.HIGH.value]
            
            for priority in priorities:
                backtest_params["priority"] = priority
                task_id = await adapter.submit_backtest(**backtest_params)
                assert task_id == "test-task-id-123"
