"""
Tests for BackfillRun SQLAlchemy model.

BackfillRun tracks execution of backfill tasks with status, metrics, and error information.
"""

import pytest
from datetime import datetime, timezone

from backend.models.backfill_run import BackfillRun


class TestBackfillRunInit:
    """Test BackfillRun model initialization."""

    def test_backfill_run_minimal_fields(self):
        """Test creating BackfillRun with minimal required fields."""
        run = BackfillRun(
            symbol="BTCUSDT",
            interval="1m"
        )
        assert run.symbol == "BTCUSDT"
        assert run.interval == "1m"
        assert run.task_id is None  # Optional
        assert run.params is None  # Optional
        assert run.finished_at is None  # Optional

    def test_backfill_run_with_task_id(self):
        """Test creating BackfillRun with task_id."""
        run = BackfillRun(
            task_id="task-12345",
            symbol="ETHUSDT",
            interval="5m"
        )
        assert run.task_id == "task-12345"
        assert run.symbol == "ETHUSDT"
        assert run.interval == "5m"

    def test_backfill_run_with_params(self):
        """Test creating BackfillRun with JSON params."""
        params_json = '{"start_time": 1700000000, "end_time": 1700100000}'
        run = BackfillRun(
            symbol="SOLUSDT",
            interval="15m",
            params=params_json
        )
        assert run.params == params_json

    def test_backfill_run_all_fields(self):
        """Test creating BackfillRun with all fields."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        
        run = BackfillRun(
            id=999,
            task_id="task-abc",
            symbol="BNBUSDT",
            interval="1h",
            params='{"limit": 1000}',
            started_at=started,
            finished_at=finished,
            status="SUCCEEDED",
            upserts=5000,
            pages=10,
            error=None
        )
        
        assert run.id == 999
        assert run.task_id == "task-abc"
        assert run.symbol == "BNBUSDT"
        assert run.interval == "1h"
        assert run.params == '{"limit": 1000}'
        assert run.started_at == started
        assert run.finished_at == finished
        assert run.status == "SUCCEEDED"
        assert run.upserts == 5000
        assert run.pages == 10
        assert run.error is None


class TestBackfillRunColumns:
    """Test BackfillRun column attributes and types."""

    def test_symbol_is_string(self):
        """Test symbol column accepts string values."""
        run = BackfillRun(symbol="ADAUSDT", interval="4h")
        assert isinstance(run.symbol, str)
        assert run.symbol == "ADAUSDT"

    def test_interval_is_string(self):
        """Test interval column accepts string values."""
        run = BackfillRun(symbol="DOTUSDT", interval="1d")
        assert isinstance(run.interval, str)
        assert run.interval == "1d"

    def test_task_id_nullable(self):
        """Test task_id can be None."""
        run = BackfillRun(symbol="LINKUSDT", interval="1w")
        assert run.task_id is None

    def test_task_id_can_be_set(self):
        """Test task_id can be set explicitly."""
        run = BackfillRun(
            task_id="task-xyz-789",
            symbol="MATICUSDT",
            interval="1m"
        )
        assert run.task_id == "task-xyz-789"

    def test_status_can_be_set_and_updated(self):
        """Test status can be set and updated."""
        run = BackfillRun(
            symbol="AVAXUSDT",
            interval="5m",
            status="PENDING"
        )
        assert run.status == "PENDING"
        
        run.status = "RUNNING"
        assert run.status == "RUNNING"
        
        run.status = "SUCCEEDED"
        assert run.status == "SUCCEEDED"

    def test_status_values(self):
        """Test various status values."""
        statuses = ["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
        for status in statuses:
            run = BackfillRun(
                symbol="BTCUSDT",
                interval="1m",
                status=status
            )
            assert run.status == status

    def test_upserts_can_be_set(self):
        """Test upserts counter can be set."""
        run = BackfillRun(
            symbol="ETHUSDT",
            interval="1h",
            upserts=1234
        )
        assert run.upserts == 1234

    def test_pages_can_be_set(self):
        """Test pages counter can be set."""
        run = BackfillRun(
            symbol="SOLUSDT",
            interval="15m",
            pages=42
        )
        assert run.pages == 42

    def test_started_at_accepts_datetime(self):
        """Test started_at accepts datetime values."""
        now = datetime.now(timezone.utc)
        run = BackfillRun(
            symbol="BNBUSDT",
            interval="1m",
            started_at=now
        )
        assert run.started_at == now
        assert isinstance(run.started_at, datetime)

    def test_finished_at_nullable(self):
        """Test finished_at can be None."""
        run = BackfillRun(symbol="ADAUSDT", interval="5m")
        assert run.finished_at is None

    def test_finished_at_can_be_set(self):
        """Test finished_at can be set."""
        finished = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        run = BackfillRun(
            symbol="DOTUSDT",
            interval="1h",
            finished_at=finished
        )
        assert run.finished_at == finished

    def test_error_nullable(self):
        """Test error can be None."""
        run = BackfillRun(symbol="LINKUSDT", interval="1d")
        assert run.error is None

    def test_error_can_be_set(self):
        """Test error message can be set."""
        error_msg = "Connection timeout after 30s"
        run = BackfillRun(
            symbol="MATICUSDT",
            interval="1m",
            error=error_msg
        )
        assert run.error == error_msg


class TestBackfillRunTableMetadata:
    """Test BackfillRun table metadata."""

    def test_tablename(self):
        """Test table name is 'backfill_runs'."""
        assert BackfillRun.__tablename__ == "backfill_runs"


class TestBackfillRunIntegration:
    """Test BackfillRun integration scenarios."""

    def test_backfill_run_lifecycle_pending_to_succeeded(self):
        """Test complete backfill run lifecycle."""
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
        
        run = BackfillRun(
            task_id="task-001",
            symbol="BTCUSDT",
            interval="1m",
            status="PENDING",
            upserts=0,
            pages=0
        )
        
        # Start
        assert run.status == "PENDING"
        run.status = "RUNNING"
        run.started_at = started
        
        # Process
        run.upserts = 10000
        run.pages = 20
        
        # Complete
        run.status = "SUCCEEDED"
        run.finished_at = finished
        
        assert run.status == "SUCCEEDED"
        assert run.upserts == 10000
        assert run.pages == 20
        assert run.finished_at > run.started_at

    def test_backfill_run_lifecycle_pending_to_failed(self):
        """Test failed backfill run lifecycle."""
        run = BackfillRun(
            task_id="task-002",
            symbol="ETHUSDT",
            interval="5m",
            status="PENDING"
        )
        
        # Start
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        
        # Fail
        run.status = "FAILED"
        run.error = "API rate limit exceeded"
        run.finished_at = datetime.now(timezone.utc)
        
        assert run.status == "FAILED"
        assert run.error is not None
        assert "rate limit" in run.error

    def test_backfill_run_canceled(self):
        """Test canceled backfill run."""
        run = BackfillRun(
            task_id="task-003",
            symbol="SOLUSDT",
            interval="15m",
            status="RUNNING"
        )
        
        # Cancel
        run.status = "CANCELED"
        run.finished_at = datetime.now(timezone.utc)
        
        assert run.status == "CANCELED"
        assert run.finished_at is not None

    def test_multiple_runs_same_symbol(self):
        """Test multiple runs for same symbol/interval."""
        run1 = BackfillRun(
            task_id="task-001",
            symbol="BTCUSDT",
            interval="1h",
            status="SUCCEEDED",
            upserts=1000
        )
        run2 = BackfillRun(
            task_id="task-002",
            symbol="BTCUSDT",
            interval="1h",
            status="SUCCEEDED",
            upserts=500
        )
        
        assert run1.symbol == run2.symbol
        assert run1.interval == run2.interval
        assert run1.task_id != run2.task_id
        assert run1.upserts != run2.upserts

    def test_backfill_run_metrics_accumulation(self):
        """Test accumulating upserts and pages during run."""
        run = BackfillRun(
            symbol="ETHUSDT",
            interval="1m",
            status="RUNNING",
            upserts=0,
            pages=0
        )
        
        # Simulate processing
        for _ in range(5):
            run.pages += 1
            run.upserts += 200
        
        assert run.pages == 5
        assert run.upserts == 1000


class TestBackfillRunEdgeCases:
    """Test BackfillRun edge cases."""

    def test_very_long_task_id(self):
        """Test task_id with maximum length (128 chars)."""
        long_task_id = "task-" + "a" * 123
        run = BackfillRun(
            task_id=long_task_id,
            symbol="BTCUSDT",
            interval="1m"
        )
        assert run.task_id == long_task_id
        assert len(run.task_id) == 128

    def test_long_symbol_name(self):
        """Test symbol with maximum length (64 chars)."""
        long_symbol = "S" * 64
        run = BackfillRun(
            symbol=long_symbol,
            interval="1m"
        )
        assert run.symbol == long_symbol
        assert len(run.symbol) == 64

    def test_long_interval_name(self):
        """Test interval with maximum length (16 chars)."""
        long_interval = "I" * 16
        run = BackfillRun(
            symbol="BTCUSDT",
            interval=long_interval
        )
        assert run.interval == long_interval
        assert len(run.interval) == 16

    def test_zero_upserts(self):
        """Test run with zero upserts (no data inserted)."""
        run = BackfillRun(
            symbol="ETHUSDT",
            interval="1m",
            upserts=0
        )
        assert run.upserts == 0

    def test_zero_pages(self):
        """Test run with zero pages."""
        run = BackfillRun(
            symbol="SOLUSDT",
            interval="5m",
            pages=0
        )
        assert run.pages == 0

    def test_very_large_upserts(self):
        """Test run with very large upserts count."""
        large_count = 1_000_000
        run = BackfillRun(
            symbol="BNBUSDT",
            interval="1h",
            upserts=large_count
        )
        assert run.upserts == large_count

    def test_very_long_error_message(self):
        """Test run with very long error message."""
        long_error = "Error: " + "x" * 5000
        run = BackfillRun(
            symbol="ADAUSDT",
            interval="1m",
            error=long_error
        )
        assert run.error == long_error
        assert len(run.error) > 5000

    def test_complex_params_json(self):
        """Test params with complex JSON structure."""
        complex_json = '{"start": 1700000000, "end": 1700100000, "options": {"retry": true, "timeout": 30}}'
        run = BackfillRun(
            symbol="DOTUSDT",
            interval="15m",
            params=complex_json
        )
        assert run.params == complex_json
        assert "retry" in run.params

    def test_special_characters_in_symbol(self):
        """Test symbol with special characters."""
        run = BackfillRun(
            symbol="BTC-USD_PERP",
            interval="1m"
        )
        assert run.symbol == "BTC-USD_PERP"

    def test_finished_before_started_edge_case(self):
        """Test edge case where finished_at could be set before started_at."""
        started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # Before started
        
        run = BackfillRun(
            symbol="LINKUSDT",
            interval="1h",
            started_at=started,
            finished_at=finished
        )
        
        # Model allows this (validation should be at app level)
        assert run.finished_at < run.started_at
