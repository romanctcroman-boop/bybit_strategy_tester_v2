"""
Tests for BybitKlineAudit SQLAlchemy model.

BybitKlineAudit stores OHLCV candlestick data from Bybit with audit trail.
"""

import json
import pytest
from datetime import datetime, timezone

from backend.models.bybit_kline_audit import BybitKlineAudit


class TestBybitKlineAuditInit:
    """Test BybitKlineAudit model initialization."""

    def test_bybit_kline_audit_minimal_fields(self):
        """Test creating BybitKlineAudit with minimal required fields."""
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="5",
            open_time=1700000000000,
            raw='{"data": "test"}'
        )
        assert audit.symbol == "BTCUSDT"
        assert audit.interval == "5"
        assert audit.open_time == 1700000000000
        assert audit.raw == '{"data": "test"}'

    def test_bybit_kline_audit_with_ohlcv(self):
        """Test creating BybitKlineAudit with OHLCV data."""
        audit = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="15",
            open_time=1700000000000,
            open_price=2000.5,
            high_price=2010.0,
            low_price=1990.0,
            close_price=2005.25,
            volume=1234.56,
            raw='{"test": "data"}'
        )
        assert audit.open_price == 2000.5
        assert audit.high_price == 2010.0
        assert audit.low_price == 1990.0
        assert audit.close_price == 2005.25
        assert audit.volume == 1234.56

    def test_bybit_kline_audit_with_turnover(self):
        """Test creating BybitKlineAudit with turnover."""
        audit = BybitKlineAudit(
            symbol="SOLUSDT",
            interval="60",
            open_time=1700000000000,
            turnover=5000000.75,
            raw='{"raw": "payload"}'
        )
        assert audit.turnover == 5000000.75

    def test_bybit_kline_audit_all_fields(self):
        """Test creating BybitKlineAudit with all fields."""
        now = datetime.now(timezone.utc)
        open_time_dt = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        audit = BybitKlineAudit(
            id=123,
            symbol="BNBUSDT",
            interval="D",
            open_time=1704096000000,
            open_time_dt=open_time_dt,
            open_price=300.0,
            high_price=310.5,
            low_price=295.0,
            close_price=308.25,
            volume=10000.0,
            turnover=3000000.0,
            raw='{"complete": "data"}',
            inserted_at=now
        )
        
        assert audit.id == 123
        assert audit.symbol == "BNBUSDT"
        assert audit.interval == "D"
        assert audit.open_time == 1704096000000
        assert audit.open_time_dt == open_time_dt
        assert audit.open_price == 300.0
        assert audit.high_price == 310.5
        assert audit.low_price == 295.0
        assert audit.close_price == 308.25
        assert audit.volume == 10000.0
        assert audit.turnover == 3000000.0
        assert audit.raw == '{"complete": "data"}'
        assert audit.inserted_at == now


class TestBybitKlineAuditColumns:
    """Test BybitKlineAudit column attributes."""

    def test_symbol_is_string(self):
        """Test symbol column accepts string values."""
        audit = BybitKlineAudit(
            symbol="ADAUSDT",
            interval="30",
            open_time=1700000000000,
            raw="{}"
        )
        assert isinstance(audit.symbol, str)
        assert audit.symbol == "ADAUSDT"

    def test_interval_accepts_various_formats(self):
        """Test interval column accepts different time formats."""
        intervals = ["5", "15", "30", "60", "D", "W", "M"]
        for interval in intervals:
            audit = BybitKlineAudit(
                symbol="BTCUSDT",
                interval=interval,
                open_time=1700000000000,
                raw="{}"
            )
            assert audit.interval == interval

    def test_open_time_is_bigint(self):
        """Test open_time accepts large integer timestamps."""
        large_timestamp = 9999999999999
        audit = BybitKlineAudit(
            symbol="DOTUSDT",
            interval="5",
            open_time=large_timestamp,
            raw="{}"
        )
        assert audit.open_time == large_timestamp

    def test_open_time_dt_nullable(self):
        """Test open_time_dt can be None."""
        audit = BybitKlineAudit(
            symbol="LINKUSDT",
            interval="15",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.open_time_dt is None

    def test_open_time_dt_can_be_set(self):
        """Test open_time_dt can be set."""
        dt = datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        audit = BybitKlineAudit(
            symbol="MATICUSDT",
            interval="60",
            open_time=1700000000000,
            open_time_dt=dt,
            raw="{}"
        )
        assert audit.open_time_dt == dt

    def test_ohlc_prices_nullable(self):
        """Test OHLC prices can be None."""
        audit = BybitKlineAudit(
            symbol="AVAXUSDT",
            interval="D",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.open_price is None
        assert audit.high_price is None
        assert audit.low_price is None
        assert audit.close_price is None

    def test_volume_nullable(self):
        """Test volume can be None."""
        audit = BybitKlineAudit(
            symbol="ATOMUSDT",
            interval="5",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.volume is None

    def test_turnover_nullable(self):
        """Test turnover can be None."""
        audit = BybitKlineAudit(
            symbol="FTMUSDT",
            interval="15",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.turnover is None

    def test_raw_is_required(self):
        """Test raw field is required (not nullable)."""
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="5",
            open_time=1700000000000,
            raw='{"required": true}'
        )
        assert audit.raw is not None
        assert audit.raw == '{"required": true}'


class TestBybitKlineAuditSetRaw:
    """Test set_raw method."""

    def test_set_raw_with_dict(self):
        """Test set_raw converts dictionary to JSON string."""
        audit = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="5",
            open_time=1700000000000,
            raw="{}"
        )
        
        raw_data = {
            "symbol": "ETHUSDT",
            "interval": "5",
            "open": 2000.0,
            "high": 2010.0
        }
        audit.set_raw(raw_data)
        
        assert isinstance(audit.raw, str)
        parsed = json.loads(audit.raw)
        assert parsed["symbol"] == "ETHUSDT"
        assert parsed["open"] == 2000.0

    def test_set_raw_with_nested_dict(self):
        """Test set_raw handles nested dictionaries."""
        audit = BybitKlineAudit(
            symbol="SOLUSDT",
            interval="15",
            open_time=1700000000000,
            raw="{}"
        )
        
        raw_data = {
            "data": {
                "prices": {
                    "open": 100.0,
                    "close": 105.0
                }
            }
        }
        audit.set_raw(raw_data)
        
        parsed = json.loads(audit.raw)
        assert parsed["data"]["prices"]["open"] == 100.0

    def test_set_raw_with_list(self):
        """Test set_raw handles lists."""
        audit = BybitKlineAudit(
            symbol="BNBUSDT",
            interval="60",
            open_time=1700000000000,
            raw="{}"
        )
        
        raw_data = {
            "trades": [1, 2, 3, 4, 5]
        }
        audit.set_raw(raw_data)
        
        parsed = json.loads(audit.raw)
        assert parsed["trades"] == [1, 2, 3, 4, 5]

    def test_set_raw_preserves_unicode(self):
        """Test set_raw preserves unicode characters."""
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="D",
            open_time=1700000000000,
            raw="{}"
        )
        
        raw_data = {"message": "测试 тест テスト"}
        audit.set_raw(raw_data)
        
        parsed = json.loads(audit.raw)
        assert "测试" in parsed["message"]
        assert "тест" in parsed["message"]


class TestBybitKlineAuditTableMetadata:
    """Test BybitKlineAudit table metadata."""

    def test_tablename(self):
        """Test table name is 'bybit_kline_audit'."""
        assert BybitKlineAudit.__tablename__ == "bybit_kline_audit"

    def test_has_unique_constraint(self):
        """Test table has unique constraint defined."""
        assert hasattr(BybitKlineAudit, '__table_args__')
        assert BybitKlineAudit.__table_args__ is not None

    def test_unique_constraint_on_symbol_interval_time(self):
        """Test unique constraint is on (symbol, interval, open_time)."""
        constraint = BybitKlineAudit.__table_args__[0]
        assert hasattr(constraint, 'name')
        assert constraint.name == "uix_symbol_interval_open_time"


class TestBybitKlineAuditIntegration:
    """Test BybitKlineAudit integration scenarios."""

    def test_complete_kline_data_workflow(self):
        """Test storing complete kline data."""
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="5",
            open_time=1700000000000
        )
        
        # Set raw data
        raw_data = {
            "symbol": "BTCUSDT",
            "interval": "5",
            "open_time": 1700000000000,
            "open": 40000.0,
            "high": 40500.0,
            "low": 39800.0,
            "close": 40200.0,
            "volume": 1234.567,
            "turnover": 50000000.0
        }
        audit.set_raw(raw_data)
        
        # Set OHLCV fields
        audit.open_price = raw_data["open"]
        audit.high_price = raw_data["high"]
        audit.low_price = raw_data["low"]
        audit.close_price = raw_data["close"]
        audit.volume = raw_data["volume"]
        audit.turnover = raw_data["turnover"]
        
        # Verify
        assert audit.open_price == 40000.0
        assert audit.high_price == 40500.0
        assert audit.low_price == 39800.0
        assert audit.close_price == 40200.0
        assert "40000.0" in audit.raw or "40000" in audit.raw

    def test_multiple_intervals_same_symbol(self):
        """Test multiple klines for same symbol, different intervals."""
        audit_5m = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="5",
            open_time=1700000000000,
            raw='{"interval": "5"}'
        )
        audit_15m = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="15",
            open_time=1700000000000,
            raw='{"interval": "15"}'
        )
        
        assert audit_5m.symbol == audit_15m.symbol
        assert audit_5m.interval != audit_15m.interval
        assert audit_5m.open_time == audit_15m.open_time

    def test_time_series_data(self):
        """Test storing sequential klines."""
        timestamps = [1700000000000, 1700000300000, 1700000600000]
        audits = []
        
        for ts in timestamps:
            audit = BybitKlineAudit(
                symbol="SOLUSDT",
                interval="5",
                open_time=ts,
                raw=f'{{"open_time": {ts}}}'
            )
            audits.append(audit)
        
        # Verify sequential timestamps
        for i in range(len(audits) - 1):
            assert audits[i].open_time < audits[i + 1].open_time


class TestBybitKlineAuditEdgeCases:
    """Test BybitKlineAudit edge cases."""

    def test_very_old_timestamp(self):
        """Test with very old timestamp (e.g., 2015)."""
        old_timestamp = 1420070400000  # 2015-01-01
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="D",
            open_time=old_timestamp,
            raw="{}"
        )
        assert audit.open_time == old_timestamp

    def test_zero_prices(self):
        """Test kline with zero prices (edge case)."""
        audit = BybitKlineAudit(
            symbol="TESTUSDT",
            interval="5",
            open_time=1700000000000,
            open_price=0.0,
            high_price=0.0,
            low_price=0.0,
            close_price=0.0,
            raw="{}"
        )
        assert audit.open_price == 0.0
        assert audit.close_price == 0.0

    def test_zero_volume(self):
        """Test kline with zero volume."""
        audit = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="5",
            open_time=1700000000000,
            volume=0.0,
            raw="{}"
        )
        assert audit.volume == 0.0

    def test_very_high_prices(self):
        """Test kline with very high prices."""
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="5",
            open_time=1700000000000,
            open_price=1000000.0,
            high_price=1100000.0,
            low_price=990000.0,
            close_price=1050000.0,
            raw="{}"
        )
        assert audit.high_price == 1100000.0

    def test_very_large_volume(self):
        """Test kline with very large volume."""
        large_volume = 999999999.999
        audit = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="D",
            open_time=1700000000000,
            volume=large_volume,
            raw="{}"
        )
        assert audit.volume == large_volume

    def test_long_symbol_name(self):
        """Test symbol with maximum length (64 chars)."""
        long_symbol = "S" * 64
        audit = BybitKlineAudit(
            symbol=long_symbol,
            interval="5",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.symbol == long_symbol
        assert len(audit.symbol) == 64

    def test_very_long_raw_json(self):
        """Test with very long raw JSON payload."""
        large_data = {"data": "x" * 10000}
        audit = BybitKlineAudit(
            symbol="BTCUSDT",
            interval="5",
            open_time=1700000000000,
            raw="{}"
        )
        audit.set_raw(large_data)
        
        assert len(audit.raw) > 10000

    def test_special_characters_in_symbol(self):
        """Test symbol with special characters."""
        audit = BybitKlineAudit(
            symbol="BTC-USD_PERP",
            interval="5",
            open_time=1700000000000,
            raw="{}"
        )
        assert audit.symbol == "BTC-USD_PERP"

    def test_negative_prices_edge_case(self):
        """Test negative prices (shouldn't happen but model allows)."""
        audit = BybitKlineAudit(
            symbol="TESTUSDT",
            interval="5",
            open_time=1700000000000,
            open_price=-100.0,
            raw="{}"
        )
        # Model allows this (validation should be at app level)
        assert audit.open_price == -100.0

    def test_decimal_precision_prices(self):
        """Test prices with high decimal precision."""
        audit = BybitKlineAudit(
            symbol="ETHUSDT",
            interval="5",
            open_time=1700000000000,
            open_price=2000.123456789,
            close_price=2001.987654321,
            raw="{}"
        )
        assert audit.open_price == pytest.approx(2000.123456789)
        assert audit.close_price == pytest.approx(2001.987654321)
