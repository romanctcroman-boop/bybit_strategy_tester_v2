"""
Unit tests for timestamp_utils module

Tests timestamp normalization and conversion functions
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd

from backend.utils.timestamp_utils import (
    normalize_timestamps,
    candles_to_dataframe,
    dataframe_to_candles,
    get_naive_utc_now,
    datetime_to_ms,
    ms_to_datetime
)


class TestNormalizeTimestamps:
    """Test normalize_timestamps function"""
    
    def test_normalizes_timezone_aware_datetime(self):
        """Should remove timezone from datetime objects"""
        candles = [
            {'timestamp': datetime(2025, 1, 1, tzinfo=timezone.utc), 'open': 100}
        ]
        
        result = normalize_timestamps(candles)
        
        assert result[0]['timestamp'].tzinfo is None
        assert result[0]['timestamp'] == datetime(2025, 1, 1)
    
    def test_keeps_naive_datetime_unchanged(self):
        """Should not modify naive datetime"""
        dt = datetime(2025, 1, 1)
        candles = [{'timestamp': dt, 'open': 100}]
        
        result = normalize_timestamps(candles)
        
        assert result[0]['timestamp'] == dt
        assert result[0]['timestamp'].tzinfo is None
    
    def test_converts_integer_milliseconds(self):
        """Should convert int milliseconds to datetime"""
        candles = [
            {'timestamp': 1704067200000, 'open': 100}  # 2024-01-01 00:00:00
        ]
        
        result = normalize_timestamps(candles)
        
        assert isinstance(result[0]['timestamp'], datetime)
        assert result[0]['timestamp'].year == 2024
        assert result[0]['timestamp'].month == 1
        assert result[0]['timestamp'].day == 1
    
    def test_converts_iso_string(self):
        """Should parse ISO format strings"""
        candles = [
            {'timestamp': '2025-01-01T00:00:00Z', 'open': 100}
        ]
        
        result = normalize_timestamps(candles)
        
        assert isinstance(result[0]['timestamp'], datetime)
        assert result[0]['timestamp'].tzinfo is None
    
    def test_handles_missing_timestamp(self):
        """Should skip candles without timestamp"""
        candles = [
            {'open': 100, 'high': 105}  # No timestamp
        ]
        
        result = normalize_timestamps(candles)
        
        assert 'timestamp' not in result[0]
    
    def test_modifies_in_place(self):
        """Should modify original list"""
        candles = [
            {'timestamp': datetime(2025, 1, 1, tzinfo=timezone.utc), 'open': 100}
        ]
        
        result = normalize_timestamps(candles)
        
        assert result is candles  # Same object
        assert candles[0]['timestamp'].tzinfo is None


class TestCandlesToDataframe:
    """Test candles_to_dataframe function"""
    
    def test_converts_to_dataframe(self):
        """Should create DataFrame from candles"""
        candles = [
            {'timestamp': datetime(2025, 1, 1), 'open': 100, 'high': 105, 'low': 95, 'close': 102},
            {'timestamp': datetime(2025, 1, 2), 'open': 102, 'high': 107, 'low': 100, 'close': 105}
        ]
        
        df = candles_to_dataframe(candles)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert df.index.name == 'timestamp'
        assert list(df.columns) == ['open', 'high', 'low', 'close']
    
    def test_set_index_false(self):
        """Should keep timestamp as column when set_index=False"""
        candles = [
            {'timestamp': datetime(2025, 1, 1), 'open': 100}
        ]
        
        df = candles_to_dataframe(candles, set_index=False)
        
        assert 'timestamp' in df.columns
        assert df.index.name != 'timestamp'
    
    def test_normalizes_timestamps(self):
        """Should normalize timestamps before conversion"""
        candles = [
            {'timestamp': datetime(2025, 1, 1, tzinfo=timezone.utc), 'open': 100}
        ]
        
        df = candles_to_dataframe(candles)
        
        assert df.index.tz is None  # No timezone


class TestDataframeToCandles:
    """Test dataframe_to_candles function"""
    
    def test_converts_to_candles(self):
        """Should convert DataFrame to candles list"""
        df = pd.DataFrame({
            'timestamp': [datetime(2025, 1, 1), datetime(2025, 1, 2)],
            'open': [100, 102],
            'close': [102, 105]
        })
        df = df.set_index('timestamp')
        
        candles = dataframe_to_candles(df)
        
        assert isinstance(candles, list)
        assert len(candles) == 2
        assert 'timestamp' in candles[0]
        assert candles[0]['open'] == 100
    
    def test_normalizes_output_timestamps(self):
        """Should normalize timestamps in output"""
        df = pd.DataFrame({
            'timestamp': [datetime(2025, 1, 1, tzinfo=timezone.utc)],
            'open': [100]
        })
        df = df.set_index('timestamp')
        
        candles = dataframe_to_candles(df)
        
        assert candles[0]['timestamp'].tzinfo is None


class TestGetNaiveUtcNow:
    """Test get_naive_utc_now function"""
    
    def test_returns_naive_datetime(self):
        """Should return current UTC as naive datetime"""
        now = get_naive_utc_now()
        
        assert isinstance(now, datetime)
        assert now.tzinfo is None
    
    def test_returns_current_time(self):
        """Should be close to current time"""
        now = get_naive_utc_now()
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        diff = abs((now - utc_now).total_seconds())
        assert diff < 1  # Within 1 second


class TestDatetimeConversions:
    """Test datetime_to_ms and ms_to_datetime"""
    
    def test_datetime_to_ms(self):
        """Should convert datetime to milliseconds"""
        dt = datetime(2024, 1, 1, 0, 0, 0)
        
        ms = datetime_to_ms(dt)
        
        assert isinstance(ms, int)
        assert ms > 0
    
    def test_ms_to_datetime(self):
        """Should convert milliseconds to datetime"""
        ms = 1704067200000  # 2024-01-01 00:00:00
        
        dt = ms_to_datetime(ms)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
    
    def test_round_trip_conversion(self):
        """Should convert datetime→ms→datetime without loss"""
        original = datetime(2025, 6, 15, 12, 30, 0)
        
        ms = datetime_to_ms(original)
        converted = ms_to_datetime(ms)
        
        assert converted == original
    
    def test_handles_timezone_aware(self):
        """Should handle timezone-aware datetime"""
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        ms = datetime_to_ms(dt)
        
        assert isinstance(ms, int)
        assert ms > 0


# Parametrized tests for edge cases
@pytest.mark.parametrize("timestamp,expected_type", [
    (datetime(2025, 1, 1), datetime),
    (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime),
    (1704067200000, datetime),
    ('2025-01-01T00:00:00Z', datetime),
])
def test_normalize_various_formats(timestamp, expected_type):
    """Test normalization of various timestamp formats"""
    candles = [{'timestamp': timestamp, 'open': 100}]
    
    result = normalize_timestamps(candles)
    
    assert isinstance(result[0]['timestamp'], expected_type)
    assert result[0]['timestamp'].tzinfo is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
