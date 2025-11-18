"""
Comprehensive tests for Redis Queue Manager
Testing Redis Streams queue with consumer groups, retry logic, and metrics
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from backend.queue.redis_queue_manager import (
    RedisQueueManager,
    Task,
    TaskStatus,
    TaskPriority,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock redis client"""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.xgroup_create = AsyncMock()
    redis.xadd = AsyncMock(return_value=b"test-msg-id")
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xack = AsyncMock()
    redis.xdel = AsyncMock()
    redis.xinfo_stream = AsyncMock(return_value={"length": 0})
    redis.hset = AsyncMock()
    redis.hexists = AsyncMock(return_value=False)
    redis.hincrby = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.close = AsyncMock()
    return redis


@pytest.fixture
async def queue_manager(mock_redis):
    """Queue manager instance with mocked redis"""
    manager = RedisQueueManager(
        redis_url="redis://localhost:6379/0",
        stream_name="test:tasks",
        consumer_group="test-workers",
        consumer_name="test-worker-1",
        max_pending_tasks=100,
        batch_size=5,
    )
    
    # Make from_url return awaitable mock
    async def mock_from_url(*args, **kwargs):
        return mock_redis
    
    with patch("backend.queue.redis_queue_manager.aioredis.from_url", side_effect=mock_from_url):
        await manager.connect()
    
    yield manager
    
    await manager.disconnect()


@pytest.fixture
def sample_task():
    """Sample task for testing"""
    return Task(
        task_id="test-task-123",
        task_type="backtest",
        payload={"strategy": "bollinger", "symbol": "BTCUSDT"},
        priority=TaskPriority.NORMAL.value,
        max_retries=3,
        timeout_seconds=3600,
    )


# ============================================================================
# Task Model Tests
# ============================================================================

class TestTaskModel:
    """Test Task dataclass"""
    
    def test_task_creation(self):
        """Should create task with all fields"""
        task = Task(
            task_id="task-1",
            task_type="backtest",
            payload={"data": "test"},
            priority=TaskPriority.HIGH.value,
        )
        
        assert task.task_id == "task-1"
        assert task.task_type == "backtest"
        assert task.payload == {"data": "test"}
        assert task.priority == TaskPriority.HIGH.value
        assert task.status == TaskStatus.PENDING.value
        assert task.created_at is not None
    
    def test_task_to_dict(self):
        """Should serialize task to dict"""
        task = Task(
            task_id="task-1",
            task_type="optimization",
            payload={"param": "value"},
        )
        
        data = task.to_dict()
        
        assert isinstance(data, dict)
        assert data["task_id"] == "task-1"
        assert data["task_type"] == "optimization"
        assert data["payload"] == {"param": "value"}
        assert "created_at" in data
    
    def test_task_from_dict(self):
        """Should deserialize task from dict"""
        data = {
            "task_id": "task-2",
            "task_type": "data_fetch",
            "payload": {"symbol": "ETHUSDT"},
            "priority": 5,
            "max_retries": 3,
            "retry_count": 0,
            "timeout_seconds": 3600,
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "error_message": None,
            "result": None,
        }
        
        task = Task.from_dict(data)
        
        assert task.task_id == "task-2"
        assert task.task_type == "data_fetch"
        assert task.payload == {"symbol": "ETHUSDT"}
        assert task.status == "pending"


# ============================================================================
# RedisQueueManager Connection Tests
# ============================================================================

class TestRedisConnection:
    """Test Redis connection management"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_redis):
        """Should connect to Redis successfully"""
        manager = RedisQueueManager(redis_url="redis://localhost:6379/0")
        
        async def mock_from_url(*args, **kwargs):
            return mock_redis
        
        with patch("backend.queue.redis_queue_manager.aioredis.from_url", side_effect=mock_from_url):
            await manager.connect()
        
        mock_redis.ping.assert_called_once()
        mock_redis.xgroup_create.assert_called_once()
        assert manager._redis is not None
    
    @pytest.mark.asyncio
    async def test_connect_existing_consumer_group(self, mock_redis):
        """Should handle existing consumer group gracefully"""
        mock_redis.xgroup_create.side_effect = Exception("BUSYGROUP Consumer Group name already exists")
        
        manager = RedisQueueManager()
        
        async def mock_from_url(*args, **kwargs):
            return mock_redis
        
        with patch("backend.queue.redis_queue_manager.aioredis.from_url", side_effect=mock_from_url):
            await manager.connect()
        
        assert manager._redis is not None
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Should raise error on connection failure"""
        manager = RedisQueueManager(redis_url="redis://invalid:9999/0")
        
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        async def mock_from_url(*args, **kwargs):
            return mock_redis
        
        with patch("backend.queue.redis_queue_manager.aioredis.from_url", side_effect=mock_from_url):
            with pytest.raises(Exception, match="Connection failed"):
                await manager.connect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, queue_manager, mock_redis):
        """Should disconnect from Redis"""
        # Store reference to mock redis before disconnect
        redis_ref = queue_manager._redis
        
        await queue_manager.disconnect()
        
        # Verify close was called on the mock
        redis_ref.close.assert_called_once()
        # Verify _redis is None after disconnect
        assert queue_manager._redis is None


# ============================================================================
# Task Submission Tests
# ============================================================================

class TestTaskSubmission:
    """Test task submission to queue"""
    
    @pytest.mark.asyncio
    async def test_submit_task_success(self, queue_manager, mock_redis):
        """Should submit task to Redis stream"""
        task_id = await queue_manager.submit_task(
            task_type="backtest",
            payload={"strategy": "rsi"},
            priority=TaskPriority.HIGH.value,
        )
        
        assert isinstance(task_id, str)
        assert len(task_id) == 36  # UUID format
        
        # Verify xadd called
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args.kwargs["name"] == "test:tasks"
        assert "data" in call_args.kwargs["fields"]
        
        # Verify metrics incremented
        mock_redis.hincrby.assert_called_with(
            "test:tasks:metrics", "tasks_submitted", 1
        )
    
    @pytest.mark.asyncio
    async def test_submit_task_with_custom_params(self, queue_manager, mock_redis):
        """Should submit task with custom parameters"""
        await queue_manager.submit_task(
            task_type="optimization",
            payload={"param": "grid_search"},
            priority=TaskPriority.CRITICAL.value,
            max_retries=5,
            timeout_seconds=7200,
        )
        
        mock_redis.xadd.assert_called_once()
        
        # Extract task data from call
        call_args = mock_redis.xadd.call_args
        task_json = call_args.kwargs["fields"]["data"]
        task_data = json.loads(task_json)
        
        assert task_data["task_type"] == "optimization"
        assert task_data["priority"] == TaskPriority.CRITICAL.value
        assert task_data["max_retries"] == 5
        assert task_data["timeout_seconds"] == 7200
    
    @pytest.mark.asyncio
    async def test_submit_multiple_tasks(self, queue_manager, mock_redis):
        """Should submit multiple tasks"""
        task_ids = []
        
        for i in range(3):
            task_id = await queue_manager.submit_task(
                task_type=f"task_{i}",
                payload={"index": i},
            )
            task_ids.append(task_id)
        
        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3  # All unique
        assert mock_redis.xadd.call_count == 3


# ============================================================================
# Handler Registration Tests
# ============================================================================

class TestHandlerRegistration:
    """Test task handler registration"""
    
    def test_register_handler(self, queue_manager):
        """Should register handler for task type"""
        async def test_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
            return {"result": "success"}
        
        queue_manager.register_handler("backtest", test_handler)
        
        assert "backtest" in queue_manager._handlers
        assert queue_manager._handlers["backtest"] == test_handler
    
    def test_register_multiple_handlers(self, queue_manager):
        """Should register multiple handlers"""
        async def handler1(payload): return {"h": 1}
        async def handler2(payload): return {"h": 2}
        
        queue_manager.register_handler("type1", handler1)
        queue_manager.register_handler("type2", handler2)
        
        assert len(queue_manager._handlers) == 2
        assert queue_manager._handlers["type1"] == handler1
        assert queue_manager._handlers["type2"] == handler2


# ============================================================================
# Worker Processing Tests
# ============================================================================

class TestWorkerProcessing:
    """Test worker task processing"""
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, queue_manager, sample_task, mock_redis):
        """Should process message successfully"""
        # Register handler
        result_data = {"status": "completed", "profit": 1500}
        
        async def test_handler(payload):
            return result_data
        
        queue_manager.register_handler("backtest", test_handler)
        
        # Mock message
        msg_id = "test-msg-1"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        await queue_manager._process_message(msg_id, fields)
        
        # Verify ACK and delete
        mock_redis.xack.assert_called_once_with(
            "test:tasks", "test-workers", msg_id
        )
        mock_redis.xdel.assert_called_once_with("test:tasks", msg_id)
        
        # Verify metrics
        mock_redis.hincrby.assert_called_with(
            "test:tasks:metrics", "tasks_completed", 1
        )
    
    @pytest.mark.asyncio
    async def test_process_message_no_handler(self, queue_manager, sample_task, mock_redis):
        """Should handle missing handler gracefully"""
        # Don't register handler
        msg_id = "test-msg-2"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        await queue_manager._process_message(msg_id, fields)
        
        # Should ACK but not increment completed
        mock_redis.xack.assert_called_once()
        
        # Verify no completion metric increment
        for call in mock_redis.hincrby.call_args_list:
            assert call.args[1] != "tasks_completed"
    
    @pytest.mark.asyncio
    async def test_process_message_handler_error_with_retry(self, queue_manager, sample_task, mock_redis):
        """Should retry on handler error"""
        # Handler that raises error
        async def failing_handler(payload):
            raise ValueError("Handler error")
        
        queue_manager.register_handler("backtest", failing_handler)
        
        # Reset retry_count to allow retries
        sample_task.retry_count = 0
        sample_task.max_retries = 3
        
        msg_id = "test-msg-3"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        await queue_manager._process_message(msg_id, fields)
        
        # Should not increment completed
        completed_calls = [
            call for call in mock_redis.hincrby.call_args_list
            if call.args[1] == "tasks_completed"
        ]
        assert len(completed_calls) == 0
        
        # Should re-submit for retry
        assert mock_redis.xadd.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_process_message_max_retries_exceeded(self, queue_manager, sample_task, mock_redis):
        """Should move to DLQ after max retries"""
        async def failing_handler(payload):
            raise RuntimeError("Persistent error")
        
        queue_manager.register_handler("backtest", failing_handler)
        
        # Exhaust retries
        sample_task.retry_count = 3
        sample_task.max_retries = 3
        
        msg_id = "test-msg-4"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        await queue_manager._process_message(msg_id, fields)
        
        # Should increment failed metric
        mock_redis.hincrby.assert_any_call(
            "test:tasks:metrics", "tasks_failed", 1
        )
        
        # Should add to DLQ
        dlq_calls = [
            call for call in mock_redis.xadd.call_args_list
            if "dlq" in str(call)
        ]
        assert len(dlq_calls) >= 1
    
    @pytest.mark.asyncio
    async def test_process_message_timeout(self, queue_manager, sample_task, mock_redis):
        """Should detect task timeout"""
        # Set started_at in the past
        sample_task.started_at = time.time() - 4000  # 4000 seconds ago
        sample_task.timeout_seconds = 3600  # 1 hour timeout
        
        async def slow_handler(payload):
            await asyncio.sleep(1)
            return {"result": "done"}
        
        queue_manager.register_handler("backtest", slow_handler)
        
        msg_id = "test-msg-5"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        await queue_manager._process_message(msg_id, fields)
        
        # Should move to DLQ
        dlq_calls = [
            call for call in mock_redis.xadd.call_args_list
            if "dlq" in str(call)
        ]
        assert len(dlq_calls) >= 1


# ============================================================================
# Worker Lifecycle Tests
# ============================================================================

class TestWorkerLifecycle:
    """Test worker start/stop lifecycle"""
    
    @pytest.mark.asyncio
    async def test_start_worker_no_messages(self, queue_manager, mock_redis):
        """Should start worker and handle no messages"""
        # Make xreadgroup properly awaitable with small delay to simulate blocking
        async def mock_xreadgroup(*args, **kwargs):
            # Check shutdown flag before returning empty result
            if not queue_manager._running or queue_manager._shutdown_event.is_set():
                return []
            # Small delay to simulate blocking read
            await asyncio.sleep(0.05)
            return []
        
        mock_redis.xreadgroup = mock_xreadgroup
        
        # Start worker in background
        worker_task = asyncio.create_task(queue_manager.start_worker())
        
        # Wait a bit for worker to start
        await asyncio.sleep(0.1)
        
        # Shutdown
        queue_manager._running = False
        queue_manager._shutdown_event.set()
        
        # Wait for worker to finish
        try:
            await asyncio.wait_for(worker_task, timeout=2)
        except asyncio.TimeoutError:
            worker_task.cancel()
        
        # Test passes if no crash
        assert True
    
    @pytest.mark.asyncio
    async def test_start_worker_with_message(self, queue_manager, mock_redis, sample_task):
        """Should process message when available"""
        # Mock one message then stop
        msg_id = "msg-123"
        fields = {"data": json.dumps(sample_task.to_dict())}
        
        # Make xreadgroup properly awaitable with side_effect
        call_count = [0]
        
        async def mock_xreadgroup(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [("test:tasks", [(msg_id, fields)])]
            # Check shutdown before continuing
            if not queue_manager._running or queue_manager._shutdown_event.is_set():
                return []
            # Small delay to simulate blocking
            await asyncio.sleep(0.05)
            return []
        
        mock_redis.xreadgroup = mock_xreadgroup
        
        # Register handler
        async def handler(payload):
            return {"processed": True}
        
        queue_manager.register_handler("backtest", handler)
        
        # Start worker
        worker_task = asyncio.create_task(queue_manager.start_worker())
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # Stop
        queue_manager._running = False
        queue_manager._shutdown_event.set()
        
        try:
            await asyncio.wait_for(worker_task, timeout=2)
        except asyncio.TimeoutError:
            worker_task.cancel()
        
        # Verify message processed
        mock_redis.xack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_worker_cancellation(self, queue_manager, mock_redis):
        """Should handle worker cancellation gracefully"""
        # Make xreadgroup properly awaitable with small delay
        async def mock_xreadgroup(*args, **kwargs):
            # Small delay to allow cancellation to happen
            await asyncio.sleep(0.05)
            return []
        
        mock_redis.xreadgroup = mock_xreadgroup
        
        worker_task = asyncio.create_task(queue_manager.start_worker())
        
        await asyncio.sleep(0.1)
        
        # Cancel task
        worker_task.cancel()
        
        try:
            await worker_task
        except asyncio.CancelledError:
            pass  # Expected


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetrics:
    """Test metrics collection"""
    
    def test_get_metrics_success(self, queue_manager, mock_redis):
        """Should retrieve metrics from Redis"""
        # Mock sync redis client
        mock_sync_redis = MagicMock()
        mock_sync_redis.hgetall.return_value = {
            "tasks_submitted": "10",
            "tasks_completed": "8",
            "tasks_failed": "1",
            "tasks_timeout": "0",
        }
        mock_sync_redis.xinfo_stream.return_value = {"length": 5}
        
        # Patch the redis module import directly
        with patch("redis.from_url", return_value=mock_sync_redis):
            metrics = queue_manager.get_metrics()
        
        assert metrics["tasks_submitted"] == 10
        assert metrics["tasks_completed"] == 8
        assert metrics["tasks_failed"] == 1
        assert metrics["active_tasks"] == 5
        
        mock_sync_redis.close.assert_called_once()
    
    def test_get_metrics_no_connection(self):
        """Should return zeros when not connected"""
        manager = RedisQueueManager()
        # Don't connect
        
        metrics = manager.get_metrics()
        
        assert metrics["tasks_submitted"] == 0
        assert metrics["tasks_completed"] == 0
        assert metrics["tasks_failed"] == 0
        assert metrics["active_tasks"] == 0
    
    def test_get_metrics_redis_error(self, queue_manager):
        """Should handle Redis error gracefully"""
        mock_sync_redis = MagicMock()
        mock_sync_redis.hgetall.side_effect = Exception("Redis error")
        
        # Patch the redis module import directly
        with patch("redis.from_url", return_value=mock_sync_redis):
            metrics = queue_manager.get_metrics()
        
        # Should return zeros on error
        assert metrics["tasks_submitted"] == 0


# ============================================================================
# Shutdown Tests
# ============================================================================

class TestShutdown:
    """Test graceful shutdown"""
    
    @pytest.mark.asyncio
    async def test_shutdown_no_active_tasks(self, queue_manager, mock_redis):
        """Should shutdown immediately with no active tasks"""
        mock_redis.xinfo_stream.return_value = {"length": 0}
        
        await queue_manager.shutdown(timeout=5)
        
        assert queue_manager._running is False
        assert queue_manager._shutdown_event.is_set()
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_active_tasks(self, queue_manager, mock_redis):
        """Should wait for active tasks to complete"""
        # Mock active tasks decreasing
        mock_redis.xinfo_stream.side_effect = [
            {"length": 3},  # 3 tasks
            {"length": 1},  # 1 task
            {"length": 0},  # 0 tasks
        ]
        
        start = time.time()
        await queue_manager.shutdown(timeout=10)
        elapsed = time.time() - start
        
        assert elapsed < 10  # Should complete before timeout
        assert mock_redis.xinfo_stream.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_shutdown_timeout(self, queue_manager, mock_redis):
        """Should timeout if tasks don't complete"""
        # Tasks never complete
        mock_redis.xinfo_stream.return_value = {"length": 5}
        
        start = time.time()
        await queue_manager.shutdown(timeout=2)
        elapsed = time.time() - start
        
        assert 1.8 < elapsed < 2.5  # Should timeout around 2s


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for full workflow"""
    
    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, queue_manager, mock_redis):
        """Should complete full task lifecycle: submit -> process -> complete"""
        # Register handler
        processed_payloads = []
        
        async def test_handler(payload):
            processed_payloads.append(payload)
            return {"status": "success", "data": payload}
        
        queue_manager.register_handler("test_task", test_handler)
        
        # Submit task
        task_id = await queue_manager.submit_task(
            task_type="test_task",
            payload={"key": "value"},
        )
        
        assert task_id is not None
        
        # Mock message in stream
        task = Task(
            task_id=task_id,
            task_type="test_task",
            payload={"key": "value"},
        )
        msg_id = "msg-integration"
        fields = {"data": json.dumps(task.to_dict())}
        
        # Process message
        await queue_manager._process_message(msg_id, fields)
        
        # Verify handler called
        assert len(processed_payloads) == 1
        assert processed_payloads[0] == {"key": "value"}
        
        # Verify completion
        mock_redis.xack.assert_called_once()
        mock_redis.hincrby.assert_any_call(
            "test:tasks:metrics", "tasks_completed", 1
        )
