"""
Comprehensive tests for backend/models/task.py

Testing Task SQLAlchemy model:
- TaskStatus constants
- Task model initialization and defaults
- Column types and constraints
- to_dict() serialization
- __repr__ method
- Timestamp handling (timezone-aware)
- Index definitions
"""
import pytest
from datetime import datetime, timezone
from backend.models.task import Task, TaskStatus


# ==================== TASK STATUS TESTS ====================


class TestTaskStatus:
    """Test TaskStatus enum constants"""
    
    def test_status_constants_exist(self):
        """Test all status constants are defined"""
        assert hasattr(TaskStatus, 'PENDING')
        assert hasattr(TaskStatus, 'PROCESSING')
        assert hasattr(TaskStatus, 'COMPLETED')
        assert hasattr(TaskStatus, 'FAILED')
        assert hasattr(TaskStatus, 'DEAD_LETTER')
    
    def test_status_values(self):
        """Test status constant values"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.PROCESSING == "processing"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.DEAD_LETTER == "dead_letter"
    
    def test_all_statuses_are_strings(self):
        """Test all status values are strings"""
        statuses = [
            TaskStatus.PENDING,
            TaskStatus.PROCESSING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.DEAD_LETTER
        ]
        
        for status in statuses:
            assert isinstance(status, str)


# ==================== TASK MODEL INITIALIZATION ====================


class TestTaskModelInit:
    """Test Task model initialization and defaults"""
    
    def test_task_initialization_minimal(self):
        """Test task with minimal required fields"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium"
        )
        
        assert task.task_id == "test-123"
        assert task.task_type == "backtest"
        assert task.priority == "medium"
    
    def test_task_can_set_status(self):
        """Test status can be set during initialization"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            status=TaskStatus.PENDING
        )
        
        assert task.status == TaskStatus.PENDING
    
    def test_task_can_set_data(self):
        """Test data can be set during initialization"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            data={}
        )
        
        assert task.data == {}
        assert isinstance(task.data, dict)
    
    def test_task_can_set_timeout(self):
        """Test timeout can be set during initialization"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            timeout=300
        )
        
        assert task.timeout == 300
    
    def test_task_can_set_max_retries(self):
        """Test max_retries can be set during initialization"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            max_retries=3
        )
        
        assert task.max_retries == 3
    
    def test_task_can_set_retry_count(self):
        """Test retry_count can be set during initialization"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            retry_count=0
        )
        
        assert task.retry_count == 0
    
    def test_task_with_all_fields(self):
        """Test task initialization with all fields"""
        now = datetime.now(timezone.utc)
        
        task = Task(
            task_id="test-123",
            task_type="optimization",
            priority="high",
            status=TaskStatus.COMPLETED,
            data={"param": "value"},
            user_id="user-456",
            ip_address="192.168.1.1",
            timeout=600,
            max_retries=5,
            retry_count=2,
            error_message="Test error",
            created_at=now,
            started_at=now,
            completed_at=now,
            processing_time_ms=1500
        )
        
        assert task.task_id == "test-123"
        assert task.task_type == "optimization"
        assert task.priority == "high"
        assert task.status == TaskStatus.COMPLETED
        assert task.data == {"param": "value"}
        assert task.user_id == "user-456"
        assert task.ip_address == "192.168.1.1"
        assert task.timeout == 600
        assert task.max_retries == 5
        assert task.retry_count == 2
        assert task.error_message == "Test error"
        assert task.processing_time_ms == 1500


# ==================== COLUMN ATTRIBUTES ====================


class TestTaskColumns:
    """Test Task model column attributes"""
    
    def test_task_id_is_string(self):
        """Test task_id accepts string values"""
        task = Task(task_id="uuid-string", task_type="test", priority="low")
        assert isinstance(task.task_id, str)
    
    def test_task_type_is_string(self):
        """Test task_type accepts string values"""
        task = Task(task_id="123", task_type="backtest_workflow", priority="low")
        assert isinstance(task.task_type, str)
    
    def test_priority_values(self):
        """Test different priority values"""
        for priority in ["high", "medium", "low"]:
            task = Task(task_id=f"test-{priority}", task_type="test", priority=priority)
            assert task.priority == priority
    
    def test_status_can_be_set_and_updated(self):
        """Test status can be set and changed after creation"""
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            status=TaskStatus.PENDING
        )
        
        assert task.status == TaskStatus.PENDING
        
        task.status = TaskStatus.PROCESSING
        assert task.status == TaskStatus.PROCESSING
        
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED
    
    def test_data_accepts_json(self):
        """Test data field accepts JSON-serializable data"""
        complex_data = {
            "config": {"param1": 10, "param2": "value"},
            "arrays": [1, 2, 3],
            "nested": {"deep": {"value": True}}
        }
        
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            data=complex_data
        )
        
        assert task.data == complex_data
    
    def test_user_id_nullable(self):
        """Test user_id can be None"""
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            user_id=None
        )
        
        assert task.user_id is None
    
    def test_ip_address_formats(self):
        """Test ip_address accepts different formats"""
        # IPv4
        task1 = Task(task_id="test-1", task_type="test", priority="low", ip_address="192.168.1.1")
        assert task1.ip_address == "192.168.1.1"
        
        # IPv6
        task2 = Task(task_id="test-2", task_type="test", priority="low", ip_address="2001:0db8:85a3::8a2e:0370:7334")
        assert task2.ip_address == "2001:0db8:85a3::8a2e:0370:7334"
    
    def test_error_message_nullable(self):
        """Test error_message can be None"""
        task = Task(task_id="test-123", task_type="test", priority="medium")
        assert task.error_message is None
        
        task.error_message = "Something went wrong"
        assert task.error_message == "Something went wrong"
    
    def test_timestamps_nullable(self):
        """Test started_at and completed_at can be None"""
        task = Task(task_id="test-123", task_type="test", priority="medium")
        
        assert task.started_at is None
        assert task.completed_at is None
    
    def test_processing_time_ms_nullable(self):
        """Test processing_time_ms can be None"""
        task = Task(task_id="test-123", task_type="test", priority="medium")
        assert task.processing_time_ms is None


# ==================== REPR METHOD ====================


class TestTaskRepr:
    """Test Task.__repr__ method"""
    
    def test_repr_includes_task_id(self):
        """Test __repr__ includes task_id"""
        task = Task(task_id="test-123", task_type="backtest", priority="medium")
        repr_str = repr(task)
        
        assert "test-123" in repr_str
    
    def test_repr_includes_task_type(self):
        """Test __repr__ includes task_type"""
        task = Task(task_id="test-123", task_type="optimization", priority="medium")
        repr_str = repr(task)
        
        assert "optimization" in repr_str
    
    def test_repr_includes_status(self):
        """Test __repr__ includes status"""
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            status=TaskStatus.PROCESSING
        )
        repr_str = repr(task)
        
        assert "processing" in repr_str
    
    def test_repr_format(self):
        """Test __repr__ has expected format"""
        task = Task(task_id="test-123", task_type="backtest", priority="medium")
        repr_str = repr(task)
        
        assert repr_str.startswith("<Task(")
        assert repr_str.endswith(")>")
        assert "task_id=" in repr_str
        assert "type=" in repr_str
        assert "status=" in repr_str


# ==================== TO_DICT METHOD ====================


class TestTaskToDict:
    """Test Task.to_dict() method"""
    
    def test_to_dict_returns_dict(self):
        """Test to_dict returns dictionary"""
        task = Task(task_id="test-123", task_type="backtest", priority="medium")
        result = task.to_dict()
        
        assert isinstance(result, dict)
    
    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all task fields"""
        task = Task(task_id="test-123", task_type="backtest", priority="medium")
        result = task.to_dict()
        
        expected_keys = [
            "task_id", "task_type", "priority", "status", "data",
            "user_id", "ip_address", "timeout", "max_retries",
            "retry_count", "error_message", "created_at",
            "started_at", "completed_at", "processing_time_ms"
        ]
        
        for key in expected_keys:
            assert key in result
    
    def test_to_dict_with_timestamps(self):
        """Test to_dict converts timestamps to ISO format"""
        now = datetime.now(timezone.utc)
        
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            created_at=now,
            started_at=now,
            completed_at=now
        )
        
        result = task.to_dict()
        
        assert isinstance(result["created_at"], str)
        assert isinstance(result["started_at"], str)
        assert isinstance(result["completed_at"], str)
        
        # Should be ISO format
        assert "T" in result["created_at"]
    
    def test_to_dict_with_none_timestamps(self):
        """Test to_dict handles None timestamps"""
        task = Task(task_id="test-123", task_type="backtest", priority="medium")
        result = task.to_dict()
        
        assert result["started_at"] is None
        assert result["completed_at"] is None
    
    def test_to_dict_preserves_values(self):
        """Test to_dict preserves exact values"""
        task = Task(
            task_id="test-123",
            task_type="optimization",
            priority="high",
            status=TaskStatus.COMPLETED,
            data={"param": "value"},
            user_id="user-456",
            ip_address="192.168.1.1",
            timeout=600,
            max_retries=5,
            retry_count=2,
            error_message="Test error",
            processing_time_ms=1500
        )
        
        result = task.to_dict()
        
        assert result["task_id"] == "test-123"
        assert result["task_type"] == "optimization"
        assert result["priority"] == "high"
        assert result["status"] == TaskStatus.COMPLETED
        assert result["data"] == {"param": "value"}
        assert result["user_id"] == "user-456"
        assert result["ip_address"] == "192.168.1.1"
        assert result["timeout"] == 600
        assert result["max_retries"] == 5
        assert result["retry_count"] == 2
        assert result["error_message"] == "Test error"
        assert result["processing_time_ms"] == 1500
    
    def test_to_dict_with_nested_data(self):
        """Test to_dict preserves nested data structure"""
        complex_data = {
            "config": {"param1": 10, "param2": [1, 2, 3]},
            "metadata": {"user": "test", "version": "1.0"}
        }
        
        task = Task(
            task_id="test-123",
            task_type="backtest",
            priority="medium",
            data=complex_data
        )
        
        result = task.to_dict()
        
        assert result["data"] == complex_data


# ==================== TABLE METADATA ====================


class TestTaskTableMetadata:
    """Test Task model table metadata"""
    
    def test_tablename(self):
        """Test table name is 'tasks'"""
        assert Task.__tablename__ == "tasks"
    
    def test_has_indexes(self):
        """Test model defines indexes"""
        # Check __table_args__ exists
        assert hasattr(Task, '__table_args__')
        assert Task.__table_args__ is not None
    
    def test_index_count(self):
        """Test expected number of indexes defined"""
        # Should have 3 composite indexes in __table_args__
        assert len(Task.__table_args__) == 3


# ==================== INTEGRATION TESTS ====================


class TestTaskIntegration:
    """Test Task model in realistic scenarios"""
    
    def test_task_lifecycle_pending_to_completed(self):
        """Test complete task lifecycle"""
        # Create task
        task = Task(
            task_id="workflow-123",
            task_type="backtest_workflow",
            priority="high",
            user_id="user-789",
            ip_address="10.0.0.1",
            status=TaskStatus.PENDING,
            retry_count=0
        )
        
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        
        # Start processing
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now(timezone.utc)
        
        assert task.status == TaskStatus.PROCESSING
        assert task.started_at is not None
        
        # Complete successfully
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.processing_time_ms = 2500
        
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.processing_time_ms == 2500
    
    def test_task_with_retry_workflow(self):
        """Test task retry workflow"""
        task = Task(
            task_id="retry-test",
            task_type="optimization",
            priority="medium",
            max_retries=3
        )
        
        # First failure
        task.status = TaskStatus.FAILED
        task.retry_count = 1
        task.error_message = "Connection timeout"
        
        assert task.retry_count < task.max_retries
        
        # Retry
        task.status = TaskStatus.PENDING
        task.error_message = None
        
        # Second failure
        task.status = TaskStatus.FAILED
        task.retry_count = 2
        task.error_message = "Server error"
        
        # Final retry
        task.status = TaskStatus.PENDING
        task.error_message = None
        
        # Success on third attempt
        task.status = TaskStatus.COMPLETED
        
        assert task.retry_count == 2
        assert task.status == TaskStatus.COMPLETED
    
    def test_task_to_dead_letter(self):
        """Test task moving to dead letter queue"""
        task = Task(
            task_id="dead-letter-test",
            task_type="backtest",
            priority="low",
            max_retries=3,
            retry_count=3
        )
        
        # Exceeded max retries
        assert task.retry_count >= task.max_retries
        
        task.status = TaskStatus.DEAD_LETTER
        task.error_message = "Max retries exceeded"
        
        assert task.status == TaskStatus.DEAD_LETTER
    
    def test_multiple_tasks_independent(self):
        """Test multiple task instances are independent"""
        task1 = Task(task_id="task-1", task_type="backtest", priority="high")
        task2 = Task(task_id="task-2", task_type="optimization", priority="low")
        
        task1.status = TaskStatus.PROCESSING
        task2.status = TaskStatus.COMPLETED
        
        assert task1.status == TaskStatus.PROCESSING
        assert task2.status == TaskStatus.COMPLETED
        assert task1.task_id != task2.task_id


# ==================== EDGE CASES ====================


class TestTaskEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_task_with_empty_data(self):
        """Test task with explicitly empty data"""
        task = Task(task_id="test-123", task_type="test", priority="medium", data={})
        assert task.data == {}
    
    def test_task_with_very_long_error_message(self):
        """Test task with very long error message"""
        long_error = "Error: " + "x" * 10000
        
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            error_message=long_error
        )
        
        assert len(task.error_message) > 10000
    
    def test_task_with_zero_timeout(self):
        """Test task with zero timeout"""
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            timeout=0
        )
        
        assert task.timeout == 0
    
    def test_task_with_negative_retry_count(self):
        """Test task can store negative retry_count (though unusual)"""
        task = Task(
            task_id="test-123",
            task_type="test",
            priority="medium",
            retry_count=-1
        )
        
        assert task.retry_count == -1
    
    def test_task_with_special_characters_in_id(self):
        """Test task_id with special characters"""
        special_id = "task-@#$%^&*()-123"
        task = Task(task_id=special_id, task_type="test", priority="medium")
        
        assert task.task_id == special_id
    
    def test_to_dict_multiple_calls(self):
        """Test to_dict can be called multiple times"""
        task = Task(task_id="test-123", task_type="test", priority="medium")
        
        dict1 = task.to_dict()
        dict2 = task.to_dict()
        
        assert dict1 == dict2
        assert dict1 is not dict2  # Different objects
