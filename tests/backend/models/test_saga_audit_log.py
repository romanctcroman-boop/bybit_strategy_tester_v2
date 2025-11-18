"""
Tests for SagaAuditLog SQLAlchemy model.

SagaAuditLog provides immutable audit trail for saga events (compliance/forensics).
"""

import pytest
from datetime import datetime, timezone, UTC

from backend.models.saga_audit_log import SagaAuditLog


class TestSagaAuditLogInit:
    """Test SagaAuditLog model initialization."""

    def test_saga_audit_log_minimal_fields(self):
        """Test creating SagaAuditLog with minimal required fields."""
        log = SagaAuditLog(
            saga_id="saga-12345",
            event_type="saga_start"
        )
        assert log.saga_id == "saga-12345"
        assert log.event_type == "saga_start"

    def test_saga_audit_log_with_step_info(self):
        """Test creating SagaAuditLog with step information."""
        log = SagaAuditLog(
            saga_id="saga-abc",
            event_type="step_start",
            step_name="create_order",
            step_index=0
        )
        assert log.step_name == "create_order"
        assert log.step_index == 0

    def test_saga_audit_log_with_event_data(self):
        """Test creating SagaAuditLog with event data."""
        event_data = {
            "order_id": "order-123",
            "symbol": "BTCUSDT",
            "quantity": 0.5
        }
        log = SagaAuditLog(
            saga_id="saga-event",
            event_type="step_complete",
            event_data=event_data
        )
        assert log.event_data == event_data
        assert log.event_data["order_id"] == "order-123"

    def test_saga_audit_log_with_error(self):
        """Test creating SagaAuditLog with error information."""
        log = SagaAuditLog(
            saga_id="saga-error",
            event_type="step_failed",
            step_name="payment",
            error_message="Insufficient funds",
            error_stack_trace="Traceback (most recent call last)..."
        )
        assert log.error_message == "Insufficient funds"
        assert log.error_stack_trace is not None

    def test_saga_audit_log_all_fields(self):
        """Test creating SagaAuditLog with all fields."""
        timestamp = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        
        log = SagaAuditLog(
            id=999,
            saga_id="saga-complete",
            event_type="step_complete",
            step_name="reserve_inventory",
            step_index=2,
            event_data={"items": ["item1", "item2"]},
            context_snapshot={"user_id": "user-123"},
            error_message=None,
            error_stack_trace=None,
            timestamp=timestamp,
            duration_ms=250,
            user_id="user-123",
            ip_address="192.168.1.100",
            saga_state_before="RUNNING",
            saga_state_after="RUNNING",
            retry_count=0
        )
        
        assert log.id == 999
        assert log.saga_id == "saga-complete"
        assert log.event_type == "step_complete"
        assert log.step_name == "reserve_inventory"
        assert log.step_index == 2
        assert log.duration_ms == 250
        assert log.user_id == "user-123"
        assert log.ip_address == "192.168.1.100"


class TestSagaAuditLogColumns:
    """Test SagaAuditLog column attributes."""

    def test_saga_id_is_string(self):
        """Test saga_id column accepts string values."""
        log = SagaAuditLog(saga_id="saga-123", event_type="saga_start")
        assert isinstance(log.saga_id, str)

    def test_event_type_values(self):
        """Test various event type values."""
        event_types = [
            "saga_start", "step_start", "step_complete", "step_failed",
            "step_retry", "compensation_start", "compensation_complete",
            "saga_complete", "saga_failed"
        ]
        for event_type in event_types:
            log = SagaAuditLog(saga_id="saga-test", event_type=event_type)
            assert log.event_type == event_type

    def test_step_name_nullable(self):
        """Test step_name can be None (for saga-level events)."""
        log = SagaAuditLog(saga_id="saga-level", event_type="saga_start")
        assert log.step_name is None

    def test_step_name_can_be_set(self):
        """Test step_name can be set."""
        log = SagaAuditLog(
            saga_id="saga-step",
            event_type="step_start",
            step_name="validate_payment"
        )
        assert log.step_name == "validate_payment"

    def test_step_index_nullable(self):
        """Test step_index can be None."""
        log = SagaAuditLog(saga_id="saga-idx", event_type="saga_start")
        assert log.step_index is None

    def test_event_data_nullable(self):
        """Test event_data can be None."""
        log = SagaAuditLog(saga_id="saga-nodata", event_type="saga_start")
        assert log.event_data is None

    def test_context_snapshot_nullable(self):
        """Test context_snapshot can be None."""
        log = SagaAuditLog(saga_id="saga-nosnap", event_type="saga_start")
        assert log.context_snapshot is None

    def test_context_snapshot_can_be_set(self):
        """Test context_snapshot stores saga context."""
        context = {
            "user_id": "user-456",
            "order_total": 9999.99,
            "items": ["A", "B", "C"]
        }
        log = SagaAuditLog(
            saga_id="saga-ctx",
            event_type="step_complete",
            context_snapshot=context
        )
        assert log.context_snapshot == context

    def test_error_fields_nullable(self):
        """Test error fields can be None."""
        log = SagaAuditLog(saga_id="saga-ok", event_type="step_complete")
        assert log.error_message is None
        assert log.error_stack_trace is None

    def test_timestamp_can_be_set(self):
        """Test timestamp can be set."""
        ts = datetime(2024, 6, 15, 14, 30, 0, tzinfo=UTC)
        log = SagaAuditLog(
            saga_id="saga-time",
            event_type="saga_start",
            timestamp=ts
        )
        assert log.timestamp == ts

    def test_duration_ms_nullable(self):
        """Test duration_ms can be None (for non-completion events)."""
        log = SagaAuditLog(saga_id="saga-dur", event_type="step_start")
        assert log.duration_ms is None

    def test_duration_ms_can_be_set(self):
        """Test duration_ms can be set."""
        log = SagaAuditLog(
            saga_id="saga-perf",
            event_type="step_complete",
            duration_ms=1250
        )
        assert log.duration_ms == 1250

    def test_user_id_nullable(self):
        """Test user_id can be None."""
        log = SagaAuditLog(saga_id="saga-sys", event_type="saga_start")
        assert log.user_id is None

    def test_user_id_can_be_set(self):
        """Test user_id can be set."""
        log = SagaAuditLog(
            saga_id="saga-user",
            event_type="saga_start",
            user_id="user-789"
        )
        assert log.user_id == "user-789"

    def test_ip_address_nullable(self):
        """Test ip_address can be None."""
        log = SagaAuditLog(saga_id="saga-noip", event_type="saga_start")
        assert log.ip_address is None

    def test_ip_address_ipv4(self):
        """Test ip_address accepts IPv4."""
        log = SagaAuditLog(
            saga_id="saga-ipv4",
            event_type="saga_start",
            ip_address="10.20.30.40"
        )
        assert log.ip_address == "10.20.30.40"

    def test_ip_address_ipv6(self):
        """Test ip_address accepts IPv6."""
        log = SagaAuditLog(
            saga_id="saga-ipv6",
            event_type="saga_start",
            ip_address="2001:0db8::1"
        )
        assert log.ip_address == "2001:0db8::1"

    def test_saga_state_fields(self):
        """Test saga state before/after fields."""
        log = SagaAuditLog(
            saga_id="saga-state",
            event_type="step_complete",
            saga_state_before="RUNNING",
            saga_state_after="RUNNING"
        )
        assert log.saga_state_before == "RUNNING"
        assert log.saga_state_after == "RUNNING"

    def test_retry_count_can_be_set(self):
        """Test retry_count can be set."""
        log = SagaAuditLog(
            saga_id="saga-retry",
            event_type="step_retry",
            retry_count=2
        )
        assert log.retry_count == 2


class TestSagaAuditLogRepr:
    """Test SagaAuditLog __repr__ method."""

    def test_repr_includes_id(self):
        """Test __repr__ includes log id."""
        log = SagaAuditLog(saga_id="saga-r1", event_type="saga_start")
        log.id = 123
        repr_str = repr(log)
        assert "id=123" in repr_str

    def test_repr_includes_saga_id(self):
        """Test __repr__ includes saga_id."""
        log = SagaAuditLog(saga_id="saga-repr", event_type="saga_start")
        repr_str = repr(log)
        assert "saga-repr" in repr_str

    def test_repr_includes_event_type(self):
        """Test __repr__ includes event type."""
        log = SagaAuditLog(saga_id="saga-evt", event_type="step_failed")
        repr_str = repr(log)
        assert "event=step_failed" in repr_str

    def test_repr_includes_step_name(self):
        """Test __repr__ includes step name."""
        log = SagaAuditLog(
            saga_id="saga-stp",
            event_type="step_complete",
            step_name="payment"
        )
        repr_str = repr(log)
        assert "step=payment" in repr_str

    def test_repr_format(self):
        """Test __repr__ has expected format."""
        log = SagaAuditLog(saga_id="saga-fmt", event_type="saga_start")
        repr_str = repr(log)
        assert repr_str.startswith("<SagaAuditLog(")
        assert repr_str.endswith(")>")


class TestSagaAuditLogToDict:
    """Test SagaAuditLog to_dict method."""

    def test_to_dict_returns_dict(self):
        """Test to_dict returns dictionary."""
        log = SagaAuditLog(saga_id="saga-dict", event_type="saga_start")
        result = log.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all expected fields."""
        ts = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        
        log = SagaAuditLog(
            id=456,
            saga_id="saga-all",
            event_type="step_complete",
            step_name="inventory",
            step_index=1,
            event_data={"result": "success"},
            context_snapshot={"ctx": "data"},
            error_message=None,
            timestamp=ts,
            duration_ms=300,
            user_id="user-abc",
            ip_address="192.168.1.1",
            saga_state_before="RUNNING",
            saga_state_after="RUNNING",
            retry_count=0
        )
        
        result = log.to_dict()
        assert result["id"] == 456
        assert result["saga_id"] == "saga-all"
        assert result["event_type"] == "step_complete"
        assert result["step_name"] == "inventory"
        assert result["step_index"] == 1
        assert result["event_data"] == {"result": "success"}
        assert result["context_snapshot"] == {"ctx": "data"}
        assert result["duration_ms"] == 300
        assert result["user_id"] == "user-abc"
        assert result["ip_address"] == "192.168.1.1"
        assert result["saga_state_before"] == "RUNNING"
        assert result["saga_state_after"] == "RUNNING"
        assert result["retry_count"] == 0

    def test_to_dict_timestamp_iso_format(self):
        """Test to_dict converts timestamp to ISO format."""
        ts = datetime(2024, 3, 15, 10, 30, 45, tzinfo=UTC)
        log = SagaAuditLog(
            saga_id="saga-iso",
            event_type="saga_start",
            timestamp=ts
        )
        
        result = log.to_dict()
        assert isinstance(result["timestamp"], str)
        assert "2024-03-15" in result["timestamp"]

    def test_to_dict_with_none_timestamp(self):
        """Test to_dict handles None timestamp."""
        log = SagaAuditLog(saga_id="saga-nots", event_type="saga_start")
        log.timestamp = None
        
        result = log.to_dict()
        assert result["timestamp"] is None

    def test_to_dict_preserves_nested_data(self):
        """Test to_dict preserves nested JSON structures."""
        event_data = {
            "order": {
                "id": "ord-123",
                "items": [
                    {"sku": "A", "qty": 2},
                    {"sku": "B", "qty": 1}
                ]
            }
        }
        log = SagaAuditLog(
            saga_id="saga-nested",
            event_type="step_complete",
            event_data=event_data
        )
        
        result = log.to_dict()
        assert result["event_data"]["order"]["id"] == "ord-123"
        assert len(result["event_data"]["order"]["items"]) == 2


class TestSagaAuditLogTableMetadata:
    """Test SagaAuditLog table metadata."""

    def test_tablename(self):
        """Test table name is 'saga_audit_logs'."""
        assert SagaAuditLog.__tablename__ == "saga_audit_logs"

    def test_has_composite_indexes(self):
        """Test table has composite indexes defined."""
        assert hasattr(SagaAuditLog, '__table_args__')
        assert SagaAuditLog.__table_args__ is not None
        assert len(SagaAuditLog.__table_args__) == 3


class TestSagaAuditLogIntegration:
    """Test SagaAuditLog integration scenarios."""

    def test_complete_saga_audit_trail(self):
        """Test logging complete saga execution."""
        logs = []
        
        # Saga start
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="saga_start",
            user_id="user-123",
            saga_state_after="RUNNING"
        ))
        
        # Step 1 start
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="step_start",
            step_name="create_order",
            step_index=0
        ))
        
        # Step 1 complete
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="step_complete",
            step_name="create_order",
            step_index=0,
            duration_ms=150
        ))
        
        # Step 2 start
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="step_start",
            step_name="payment",
            step_index=1
        ))
        
        # Step 2 complete
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="step_complete",
            step_name="payment",
            step_index=1,
            duration_ms=500
        ))
        
        # Saga complete
        logs.append(SagaAuditLog(
            saga_id="saga-audit-1",
            event_type="saga_complete",
            saga_state_before="RUNNING",
            saga_state_after="COMPLETED"
        ))
        
        assert len(logs) == 6
        assert all(log.saga_id == "saga-audit-1" for log in logs)

    def test_saga_with_retry_audit(self):
        """Test logging saga with retry."""
        logs = []
        
        # Step fails
        logs.append(SagaAuditLog(
            saga_id="saga-retry-1",
            event_type="step_failed",
            step_name="api_call",
            error_message="Connection timeout",
            retry_count=0
        ))
        
        # First retry
        logs.append(SagaAuditLog(
            saga_id="saga-retry-1",
            event_type="step_retry",
            step_name="api_call",
            retry_count=1
        ))
        
        # Second retry succeeds
        logs.append(SagaAuditLog(
            saga_id="saga-retry-1",
            event_type="step_complete",
            step_name="api_call",
            retry_count=1,
            duration_ms=200
        ))
        
        assert len(logs) == 3
        assert logs[0].error_message == "Connection timeout"
        assert logs[1].retry_count == 1
        assert logs[2].retry_count == 1

    def test_saga_with_compensation_audit(self):
        """Test logging saga compensation flow."""
        logs = []
        
        # Steps complete
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="step_complete",
            step_name="reserve_inventory"
        ))
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="step_complete",
            step_name="charge_payment"
        ))
        
        # Next step fails
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="step_failed",
            step_name="send_confirmation",
            error_message="Email service down"
        ))
        
        # Compensation starts
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="compensation_start",
            saga_state_before="RUNNING",
            saga_state_after="COMPENSATING"
        ))
        
        # Compensate charge_payment
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="compensation_complete",
            step_name="refund_payment"
        ))
        
        # Compensate reserve_inventory
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="compensation_complete",
            step_name="release_inventory"
        ))
        
        # Saga aborted
        logs.append(SagaAuditLog(
            saga_id="saga-comp-1",
            event_type="saga_failed",
            saga_state_after="ABORTED"
        ))
        
        assert len(logs) == 7
        compensation_logs = [log for log in logs if "compensation" in log.event_type]
        assert len(compensation_logs) == 3

    def test_multiple_sagas_independent_logs(self):
        """Test logs from multiple sagas are independent."""
        log1 = SagaAuditLog(
            saga_id="saga-A",
            event_type="saga_start",
            user_id="user-1"
        )
        log2 = SagaAuditLog(
            saga_id="saga-B",
            event_type="saga_start",
            user_id="user-2"
        )
        
        assert log1.saga_id != log2.saga_id
        assert log1.user_id != log2.user_id


class TestSagaAuditLogEdgeCases:
    """Test SagaAuditLog edge cases."""

    def test_very_long_saga_id(self):
        """Test saga_id with maximum length."""
        long_id = "saga-" + "x" * 250
        log = SagaAuditLog(saga_id=long_id, event_type="saga_start")
        assert len(log.saga_id) == 255

    def test_very_long_step_name(self):
        """Test step_name with maximum length."""
        long_name = "step_" + "y" * 250
        log = SagaAuditLog(
            saga_id="saga-long",
            event_type="step_start",
            step_name=long_name
        )
        assert len(log.step_name) == 255

    def test_very_long_error_message(self):
        """Test error_message with very long text."""
        long_error = "Error: " + "z" * 10000
        log = SagaAuditLog(
            saga_id="saga-err",
            event_type="step_failed",
            error_message=long_error
        )
        assert len(log.error_message) > 10000

    def test_large_event_data(self):
        """Test event_data with large JSON object."""
        large_data = {f"field{i}": f"value{i}" * 100 for i in range(100)}
        log = SagaAuditLog(
            saga_id="saga-big",
            event_type="step_complete",
            event_data=large_data
        )
        assert len(log.event_data) == 100

    def test_zero_duration(self):
        """Test duration_ms with zero value."""
        log = SagaAuditLog(
            saga_id="saga-fast",
            event_type="step_complete",
            duration_ms=0
        )
        assert log.duration_ms == 0

    def test_very_high_duration(self):
        """Test duration_ms with very high value (hours)."""
        log = SagaAuditLog(
            saga_id="saga-slow",
            event_type="step_complete",
            duration_ms=3600000  # 1 hour
        )
        assert log.duration_ms == 3600000

    def test_negative_step_index_edge_case(self):
        """Test negative step_index (edge case)."""
        log = SagaAuditLog(
            saga_id="saga-neg",
            event_type="step_start",
            step_index=-1
        )
        # Model allows this (validation at app level)
        assert log.step_index == -1

    def test_to_dict_multiple_calls(self):
        """Test to_dict can be called multiple times."""
        log = SagaAuditLog(saga_id="saga-multi", event_type="saga_start")
        dict1 = log.to_dict()
        dict2 = log.to_dict()
        dict1.pop("timestamp")  # Remove timestamp for comparison
        dict2.pop("timestamp")
        assert dict1 == dict2
