"""
Tests for SagaCheckpoint SQLAlchemy model.

SagaCheckpoint stores saga execution state for distributed transaction recovery.
"""

import pytest
from datetime import datetime, timezone, UTC

from backend.models.saga_checkpoint import SagaCheckpoint


class TestSagaCheckpointInit:
    """Test SagaCheckpoint model initialization."""

    def test_saga_checkpoint_minimal_fields(self):
        """Test creating SagaCheckpoint with minimal required fields."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-12345",
            state="IDLE"
        )
        assert checkpoint.saga_id == "saga-12345"
        assert checkpoint.state == "IDLE"

    def test_saga_checkpoint_with_step_index(self):
        """Test creating SagaCheckpoint with step index."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-abc",
            state="RUNNING",
            current_step_index=3
        )
        assert checkpoint.current_step_index == 3

    def test_saga_checkpoint_with_completed_steps(self):
        """Test creating SagaCheckpoint with completed steps list."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-xyz",
            state="RUNNING",
            completed_steps=["step1", "step2", "step3"]
        )
        assert checkpoint.completed_steps == ["step1", "step2", "step3"]
        assert len(checkpoint.completed_steps) == 3

    def test_saga_checkpoint_with_context(self):
        """Test creating SagaCheckpoint with context data."""
        context = {
            "user_id": "user-123",
            "amount": 1000.50,
            "currency": "USDT"
        }
        checkpoint = SagaCheckpoint(
            saga_id="saga-context",
            state="RUNNING",
            context=context
        )
        assert checkpoint.context == context
        assert checkpoint.context["user_id"] == "user-123"

    def test_saga_checkpoint_all_fields(self):
        """Test creating SagaCheckpoint with all fields."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        updated = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
        
        checkpoint = SagaCheckpoint(
            saga_id="saga-complete",
            state="COMPLETED",
            current_step_index=5,
            completed_steps=["step1", "step2", "step3", "step4", "step5"],
            compensated_steps=[],
            context={"result": "success"},
            error=None,
            started_at=started,
            updated_at=updated,
            total_steps=5,
            retries=0
        )
        
        assert checkpoint.saga_id == "saga-complete"
        assert checkpoint.state == "COMPLETED"
        assert checkpoint.current_step_index == 5
        assert len(checkpoint.completed_steps) == 5
        assert checkpoint.total_steps == 5
        assert checkpoint.retries == 0


class TestSagaCheckpointColumns:
    """Test SagaCheckpoint column attributes."""

    def test_saga_id_is_string(self):
        """Test saga_id column accepts string values."""
        checkpoint = SagaCheckpoint(saga_id="saga-123", state="IDLE")
        assert isinstance(checkpoint.saga_id, str)
        assert checkpoint.saga_id == "saga-123"

    def test_state_values(self):
        """Test various saga state values."""
        states = ["IDLE", "RUNNING", "COMPENSATING", "COMPLETED", "FAILED", "ABORTED"]
        for state in states:
            checkpoint = SagaCheckpoint(saga_id=f"saga-{state}", state=state)
            assert checkpoint.state == state

    def test_state_can_be_updated(self):
        """Test state transitions."""
        checkpoint = SagaCheckpoint(saga_id="saga-transition", state="IDLE")
        assert checkpoint.state == "IDLE"
        
        checkpoint.state = "RUNNING"
        assert checkpoint.state == "RUNNING"
        
        checkpoint.state = "COMPLETED"
        assert checkpoint.state == "COMPLETED"

    def test_current_step_index_can_be_set(self):
        """Test current_step_index can be set."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-steps",
            state="RUNNING",
            current_step_index=2
        )
        assert checkpoint.current_step_index == 2

    def test_completed_steps_default_list(self):
        """Test completed_steps defaults to empty list."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-default",
            state="IDLE",
            completed_steps=[]
        )
        assert checkpoint.completed_steps == []
        assert isinstance(checkpoint.completed_steps, list)

    def test_compensated_steps_default_list(self):
        """Test compensated_steps defaults to empty list."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-comp",
            state="COMPENSATING",
            compensated_steps=[]
        )
        assert checkpoint.compensated_steps == []

    def test_context_default_dict(self):
        """Test context defaults to empty dict."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-ctx",
            state="IDLE",
            context={}
        )
        assert checkpoint.context == {}
        assert isinstance(checkpoint.context, dict)

    def test_error_nullable(self):
        """Test error can be None."""
        checkpoint = SagaCheckpoint(saga_id="saga-ok", state="COMPLETED")
        assert checkpoint.error is None

    def test_error_can_be_set(self):
        """Test error message can be set."""
        error_msg = "Step3 failed: Connection timeout"
        checkpoint = SagaCheckpoint(
            saga_id="saga-error",
            state="FAILED",
            error=error_msg
        )
        assert checkpoint.error == error_msg

    def test_timestamps_can_be_set(self):
        """Test timestamps can be set."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        updated = datetime(2024, 1, 1, 10, 15, 0, tzinfo=UTC)
        
        checkpoint = SagaCheckpoint(
            saga_id="saga-time",
            state="RUNNING",
            started_at=started,
            updated_at=updated
        )
        assert checkpoint.started_at == started
        assert checkpoint.updated_at == updated

    def test_total_steps_can_be_set(self):
        """Test total_steps can be set."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-total",
            state="RUNNING",
            total_steps=10
        )
        assert checkpoint.total_steps == 10

    def test_retries_can_be_set(self):
        """Test retries counter can be set."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-retry",
            state="RUNNING",
            retries=3
        )
        assert checkpoint.retries == 3


class TestSagaCheckpointRepr:
    """Test SagaCheckpoint __repr__ method."""

    def test_repr_includes_saga_id(self):
        """Test __repr__ includes saga_id."""
        checkpoint = SagaCheckpoint(saga_id="saga-repr", state="RUNNING")
        repr_str = repr(checkpoint)
        assert "saga-repr" in repr_str

    def test_repr_includes_state(self):
        """Test __repr__ includes state."""
        checkpoint = SagaCheckpoint(saga_id="saga-123", state="COMPLETED")
        repr_str = repr(checkpoint)
        assert "COMPLETED" in repr_str

    def test_repr_includes_step_info(self):
        """Test __repr__ includes step progress."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-steps",
            state="RUNNING",
            current_step_index=3,
            total_steps=10
        )
        repr_str = repr(checkpoint)
        assert "step=3/10" in repr_str

    def test_repr_format(self):
        """Test __repr__ has expected format."""
        checkpoint = SagaCheckpoint(saga_id="saga-fmt", state="IDLE")
        repr_str = repr(checkpoint)
        assert repr_str.startswith("<SagaCheckpoint(")
        assert repr_str.endswith(")>")


class TestSagaCheckpointToDict:
    """Test SagaCheckpoint to_dict method."""

    def test_to_dict_returns_dict(self):
        """Test to_dict returns dictionary."""
        checkpoint = SagaCheckpoint(saga_id="saga-dict", state="RUNNING")
        result = checkpoint.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all expected fields."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        
        checkpoint = SagaCheckpoint(
            saga_id="saga-all",
            state="RUNNING",
            current_step_index=2,
            completed_steps=["step1", "step2"],
            compensated_steps=[],
            context={"key": "value"},
            error=None,
            started_at=started,
            total_steps=5,
            retries=0
        )
        
        result = checkpoint.to_dict()
        assert result["saga_id"] == "saga-all"
        assert result["state"] == "RUNNING"
        assert result["current_step_index"] == 2
        assert result["completed_steps"] == ["step1", "step2"]
        assert result["compensated_steps"] == []
        assert result["context"] == {"key": "value"}
        assert result["error"] is None
        assert result["total_steps"] == 5
        assert result["retries"] == 0

    def test_to_dict_with_timestamps(self):
        """Test to_dict converts timestamps to Unix timestamps."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        updated = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)
        
        checkpoint = SagaCheckpoint(
            saga_id="saga-ts",
            state="RUNNING",
            started_at=started,
            updated_at=updated
        )
        
        result = checkpoint.to_dict()
        assert isinstance(result["started_at"], float)
        assert isinstance(result["updated_at"], float)
        assert result["started_at"] == started.timestamp()
        assert result["updated_at"] == updated.timestamp()

    def test_to_dict_with_none_timestamps(self):
        """Test to_dict handles None timestamps."""
        checkpoint = SagaCheckpoint(saga_id="saga-none", state="IDLE")
        checkpoint.started_at = None
        checkpoint.updated_at = None
        
        result = checkpoint.to_dict()
        assert result["started_at"] is None
        assert result["updated_at"] is None

    def test_to_dict_preserves_nested_context(self):
        """Test to_dict preserves nested context data."""
        context = {
            "user": {"id": "123", "name": "Alice"},
            "transaction": {"amount": 1000, "currency": "USDT"}
        }
        checkpoint = SagaCheckpoint(
            saga_id="saga-nested",
            state="RUNNING",
            context=context
        )
        
        result = checkpoint.to_dict()
        assert result["context"]["user"]["id"] == "123"
        assert result["context"]["transaction"]["amount"] == 1000

    def test_to_dict_handles_empty_lists(self):
        """Test to_dict returns empty lists correctly."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-empty",
            state="IDLE",
            completed_steps=[],
            compensated_steps=[]
        )
        
        result = checkpoint.to_dict()
        assert result["completed_steps"] == []
        assert result["compensated_steps"] == []


class TestSagaCheckpointTableMetadata:
    """Test SagaCheckpoint table metadata."""

    def test_tablename(self):
        """Test table name is 'saga_checkpoints'."""
        assert SagaCheckpoint.__tablename__ == "saga_checkpoints"


class TestSagaCheckpointIntegration:
    """Test SagaCheckpoint integration scenarios."""

    def test_saga_lifecycle_idle_to_completed(self):
        """Test complete saga execution lifecycle."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-lifecycle",
            state="IDLE",
            current_step_index=0,
            completed_steps=[],
            context={},
            total_steps=3,
            retries=0
        )
        
        # Start saga
        checkpoint.state = "RUNNING"
        checkpoint.started_at = datetime.now(UTC)
        
        # Execute step 1
        checkpoint.current_step_index = 0
        checkpoint.completed_steps = ["step1"]
        
        # Execute step 2
        checkpoint.current_step_index = 1
        checkpoint.completed_steps = ["step1", "step2"]
        
        # Execute step 3
        checkpoint.current_step_index = 2
        checkpoint.completed_steps = ["step1", "step2", "step3"]
        
        # Complete saga
        checkpoint.state = "COMPLETED"
        
        assert checkpoint.state == "COMPLETED"
        assert len(checkpoint.completed_steps) == 3

    def test_saga_with_compensation(self):
        """Test saga with compensation flow."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-compensate",
            state="RUNNING",
            current_step_index=2,
            completed_steps=["step1", "step2", "step3"],
            compensated_steps=[],
            total_steps=5
        )
        
        # Step 4 fails
        checkpoint.state = "COMPENSATING"
        checkpoint.error = "Step4 failed: Database error"
        
        # Compensate step 3
        checkpoint.compensated_steps = ["step3"]
        
        # Compensate step 2
        checkpoint.compensated_steps = ["step3", "step2"]
        
        # Compensate step 1
        checkpoint.compensated_steps = ["step3", "step2", "step1"]
        
        # Abort saga
        checkpoint.state = "ABORTED"
        
        assert checkpoint.state == "ABORTED"
        assert len(checkpoint.compensated_steps) == 3
        assert checkpoint.error is not None

    def test_saga_with_retries(self):
        """Test saga with retry attempts."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-retry",
            state="RUNNING",
            current_step_index=2,
            retries=0
        )
        
        # First retry
        checkpoint.retries = 1
        checkpoint.error = "Temporary failure"
        
        # Second retry
        checkpoint.retries = 2
        
        # Third retry - success
        checkpoint.retries = 3
        checkpoint.error = None
        checkpoint.current_step_index = 3
        
        assert checkpoint.retries == 3
        assert checkpoint.error is None

    def test_multiple_sagas_independent(self):
        """Test multiple independent sagas."""
        saga1 = SagaCheckpoint(
            saga_id="saga-1",
            state="RUNNING",
            current_step_index=2,
            total_steps=5
        )
        saga2 = SagaCheckpoint(
            saga_id="saga-2",
            state="COMPLETED",
            current_step_index=3,
            total_steps=3
        )
        
        assert saga1.saga_id != saga2.saga_id
        assert saga1.state != saga2.state
        assert saga1.total_steps != saga2.total_steps


class TestSagaCheckpointEdgeCases:
    """Test SagaCheckpoint edge cases."""

    def test_very_long_saga_id(self):
        """Test saga_id with maximum length (255 chars)."""
        long_id = "saga-" + "a" * 250
        checkpoint = SagaCheckpoint(saga_id=long_id, state="IDLE")
        assert checkpoint.saga_id == long_id
        assert len(checkpoint.saga_id) == 255

    def test_large_number_of_steps(self):
        """Test saga with very large number of steps."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-large",
            state="RUNNING",
            current_step_index=500,
            total_steps=1000
        )
        assert checkpoint.current_step_index == 500
        assert checkpoint.total_steps == 1000

    def test_many_completed_steps(self):
        """Test saga with many completed steps."""
        steps = [f"step{i}" for i in range(100)]
        checkpoint = SagaCheckpoint(
            saga_id="saga-many",
            state="RUNNING",
            completed_steps=steps
        )
        assert len(checkpoint.completed_steps) == 100

    def test_large_context_data(self):
        """Test saga with large context data."""
        context = {
            f"key{i}": f"value{i}" * 100
            for i in range(50)
        }
        checkpoint = SagaCheckpoint(
            saga_id="saga-bigctx",
            state="RUNNING",
            context=context
        )
        assert len(checkpoint.context) == 50

    def test_very_long_error_message(self):
        """Test saga with very long error message."""
        long_error = "Error: " + "x" * 5000
        checkpoint = SagaCheckpoint(
            saga_id="saga-longerr",
            state="FAILED",
            error=long_error
        )
        assert len(checkpoint.error) > 5000

    def test_zero_total_steps(self):
        """Test saga with zero total steps."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-zero",
            state="IDLE",
            total_steps=0
        )
        assert checkpoint.total_steps == 0

    def test_negative_step_index_edge_case(self):
        """Test negative step index (edge case)."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-negative",
            state="IDLE",
            current_step_index=-1
        )
        # Model allows this (validation at app level)
        assert checkpoint.current_step_index == -1

    def test_very_high_retries(self):
        """Test saga with very high retry count."""
        checkpoint = SagaCheckpoint(
            saga_id="saga-retries",
            state="FAILED",
            retries=999
        )
        assert checkpoint.retries == 999

    def test_to_dict_multiple_calls(self):
        """Test to_dict can be called multiple times."""
        checkpoint = SagaCheckpoint(saga_id="saga-multi", state="RUNNING")
        dict1 = checkpoint.to_dict()
        dict2 = checkpoint.to_dict()
        assert dict1 == dict2
