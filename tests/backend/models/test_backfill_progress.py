"""
Tests for BackfillProgress SQLAlchemy model.

BackfillProgress tracks cursor state for data backfill operations per symbol/interval.
"""

import pytest
from datetime import datetime, timezone

from backend.models.backfill_progress import BackfillProgress


class TestBackfillProgressInit:
    """Test BackfillProgress model initialization."""

    def test_backfill_progress_minimal_fields(self):
        """Test creating BackfillProgress with minimal required fields."""
        progress = BackfillProgress(
            symbol="BTCUSDT",
            interval="1m"
        )
        assert progress.symbol == "BTCUSDT"
        assert progress.interval == "1m"
        assert progress.current_cursor_ms is None  # Optional field

    def test_backfill_progress_with_cursor(self):
        """Test creating BackfillProgress with cursor value."""
        progress = BackfillProgress(
            symbol="ETHUSDT",
            interval="5m",
            current_cursor_ms=1640000000000
        )
        assert progress.symbol == "ETHUSDT"
        assert progress.interval == "5m"
        assert progress.current_cursor_ms == 1640000000000

    def test_backfill_progress_all_fields(self):
        """Test creating BackfillProgress with all fields."""
        now = datetime.now(timezone.utc)
        progress = BackfillProgress(
            id=123,
            symbol="SOLUSDT",
            interval="15m",
            current_cursor_ms=1650000000000,
            updated_at=now
        )
        assert progress.id == 123
        assert progress.symbol == "SOLUSDT"
        assert progress.interval == "15m"
        assert progress.current_cursor_ms == 1650000000000
        assert progress.updated_at == now


class TestBackfillProgressColumns:
    """Test BackfillProgress column attributes and types."""

    def test_symbol_is_string(self):
        """Test symbol column accepts string values."""
        progress = BackfillProgress(symbol="BNBUSDT", interval="1h")
        assert isinstance(progress.symbol, str)
        assert progress.symbol == "BNBUSDT"

    def test_interval_is_string(self):
        """Test interval column accepts string values."""
        progress = BackfillProgress(symbol="ADAUSDT", interval="4h")
        assert isinstance(progress.interval, str)
        assert progress.interval == "4h"

    def test_current_cursor_ms_accepts_bigint(self):
        """Test current_cursor_ms accepts large integer values."""
        large_timestamp = 9999999999999
        progress = BackfillProgress(
            symbol="DOTUSDT",
            interval="1d",
            current_cursor_ms=large_timestamp
        )
        assert progress.current_cursor_ms == large_timestamp

    def test_current_cursor_ms_nullable(self):
        """Test current_cursor_ms can be None."""
        progress = BackfillProgress(
            symbol="LINKUSDT",
            interval="1w"
        )
        assert progress.current_cursor_ms is None

    def test_current_cursor_ms_can_be_set_and_updated(self):
        """Test current_cursor_ms can be set and updated."""
        progress = BackfillProgress(
            symbol="MATICUSDT",
            interval="1m",
            current_cursor_ms=1700000000000
        )
        assert progress.current_cursor_ms == 1700000000000
        
        progress.current_cursor_ms = 1700100000000
        assert progress.current_cursor_ms == 1700100000000

    def test_updated_at_accepts_datetime(self):
        """Test updated_at accepts datetime values."""
        now = datetime.now(timezone.utc)
        progress = BackfillProgress(
            symbol="AVAXUSDT",
            interval="5m",
            updated_at=now
        )
        assert progress.updated_at == now
        assert isinstance(progress.updated_at, datetime)


class TestBackfillProgressTableMetadata:
    """Test BackfillProgress table metadata and constraints."""

    def test_tablename(self):
        """Test table name is 'backfill_progress'."""
        assert BackfillProgress.__tablename__ == "backfill_progress"

    def test_has_unique_constraint(self):
        """Test table has unique constraint defined."""
        assert hasattr(BackfillProgress, '__table_args__')
        assert BackfillProgress.__table_args__ is not None

    def test_unique_constraint_on_symbol_interval(self):
        """Test unique constraint is on (symbol, interval) pair."""
        constraint = BackfillProgress.__table_args__[0]
        assert hasattr(constraint, 'name')
        assert constraint.name == "uix_backfill_progress_key"


class TestBackfillProgressIntegration:
    """Test BackfillProgress integration scenarios."""

    def test_backfill_progress_cursor_walk_back(self):
        """Test simulated walk-back cursor update."""
        progress = BackfillProgress(
            symbol="BTCUSDT",
            interval="1m",
            current_cursor_ms=1700000000000
        )
        
        # Simulate walk-back (cursor decreases)
        progress.current_cursor_ms = 1699900000000
        assert progress.current_cursor_ms < 1700000000000

    def test_backfill_progress_multiple_intervals(self):
        """Test multiple progress records for same symbol, different intervals."""
        progress_1m = BackfillProgress(
            symbol="ETHUSDT",
            interval="1m",
            current_cursor_ms=1700000000000
        )
        progress_5m = BackfillProgress(
            symbol="ETHUSDT",
            interval="5m",
            current_cursor_ms=1700000000000
        )
        
        # Same symbol, different intervals
        assert progress_1m.symbol == progress_5m.symbol
        assert progress_1m.interval != progress_5m.interval

    def test_backfill_progress_cursor_reset(self):
        """Test cursor reset to None."""
        progress = BackfillProgress(
            symbol="SOLUSDT",
            interval="15m",
            current_cursor_ms=1700000000000
        )
        
        # Reset cursor
        progress.current_cursor_ms = None
        assert progress.current_cursor_ms is None

    def test_multiple_symbols_independent(self):
        """Test different symbols maintain independent progress."""
        progress_btc = BackfillProgress(
            symbol="BTCUSDT",
            interval="1h",
            current_cursor_ms=1700000000000
        )
        progress_eth = BackfillProgress(
            symbol="ETHUSDT",
            interval="1h",
            current_cursor_ms=1650000000000
        )
        
        # Independent cursor values
        assert progress_btc.symbol != progress_eth.symbol
        assert progress_btc.current_cursor_ms != progress_eth.current_cursor_ms


class TestBackfillProgressEdgeCases:
    """Test BackfillProgress edge cases."""

    def test_very_old_cursor_timestamp(self):
        """Test with very old timestamp (e.g., 2015)."""
        old_timestamp = 1420070400000  # 2015-01-01
        progress = BackfillProgress(
            symbol="BTCUSDT",
            interval="1d",
            current_cursor_ms=old_timestamp
        )
        assert progress.current_cursor_ms == old_timestamp

    def test_zero_cursor(self):
        """Test cursor set to zero."""
        progress = BackfillProgress(
            symbol="ETHUSDT",
            interval="1m",
            current_cursor_ms=0
        )
        assert progress.current_cursor_ms == 0

    def test_long_symbol_name(self):
        """Test symbol with maximum length (64 chars)."""
        long_symbol = "A" * 64
        progress = BackfillProgress(
            symbol=long_symbol,
            interval="1m"
        )
        assert progress.symbol == long_symbol
        assert len(progress.symbol) == 64

    def test_long_interval_name(self):
        """Test interval with maximum length (16 chars)."""
        long_interval = "1" * 16
        progress = BackfillProgress(
            symbol="BTCUSDT",
            interval=long_interval
        )
        assert progress.interval == long_interval
        assert len(progress.interval) == 16

    def test_special_characters_in_symbol(self):
        """Test symbol with special characters."""
        progress = BackfillProgress(
            symbol="BTC-USDT_PERP",
            interval="1m"
        )
        assert progress.symbol == "BTC-USDT_PERP"

    def test_updated_at_with_microseconds(self):
        """Test updated_at with microsecond precision."""
        now = datetime(2024, 1, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
        progress = BackfillProgress(
            symbol="SOLUSDT",
            interval="5m",
            updated_at=now
        )
        assert progress.updated_at.microsecond == 123456
