"""
Tests for formatting.py

Coverage target: 14.41% → 90%+
"""

import json
from datetime import datetime, timezone

import pytest

from backend.utils.formatting import (
    clamp,
    format_bytes,
    format_currency,
    format_duration_minutes,
    format_duration_seconds,
    format_large_number,
    format_number,
    format_percentage,
    format_percentage_change,
    format_timestamp,
    safe_float,
    safe_int,
    safe_json_loads,
    truncate_string,
)


class TestFormatNumber:
    """Test format_number function."""

    def test_format_number_basic(self):
        """Test basic number formatting."""
        assert format_number(1234.5678, 2) == "1,234.57"
        assert format_number(1000000, 0) == "1,000,000"

    def test_format_number_negative(self):
        """Test negative number formatting."""
        assert format_number(-1234.56, 2) == "-1,234.56"

    def test_format_number_zero(self):
        """Test zero formatting."""
        assert format_number(0, 2) == "0.00"

    def test_format_number_precision(self):
        """Test different precision levels."""
        assert format_number(123.456789, 0) == "123"
        assert format_number(123.456789, 3) == "123.457"
        assert format_number(123.456789, 5) == "123.45679"


class TestFormatPercentage:
    """Test format_percentage function."""

    def test_format_percentage_basic(self):
        """Test basic percentage formatting."""
        assert format_percentage(0.4567, 2) == "45.67%"
        assert format_percentage(1.0, 1) == "100.0%"

    def test_format_percentage_zero(self):
        """Test zero percentage."""
        assert format_percentage(0, 2) == "0.00%"

    def test_format_percentage_negative(self):
        """Test negative percentage."""
        assert format_percentage(-0.25, 2) == "-25.00%"

    def test_format_percentage_small(self):
        """Test small percentage values."""
        assert format_percentage(0.0001, 2) == "0.01%"


class TestFormatCurrency:
    """Test format_currency function."""

    def test_format_currency_basic(self):
        """Test basic currency formatting."""
        assert format_currency(1234.56) == "1,234.56 USDT"
        assert format_currency(1000000, "USD", 0) == "1,000,000 USD"

    def test_format_currency_custom(self):
        """Test custom currency codes."""
        assert format_currency(500.25, "BTC", 8) == "500.25000000 BTC"
        assert format_currency(1000, "EUR", 2) == "1,000.00 EUR"

    def test_format_currency_negative(self):
        """Test negative amounts."""
        assert format_currency(-100.50, "USDT", 2) == "-100.50 USDT"


class TestFormatTimestamp:
    """Test format_timestamp function."""

    def test_format_timestamp_datetime(self):
        """Test datetime object formatting."""
        dt = datetime(2023, 10, 31, 12, 30, 0)
        result = format_timestamp(dt, "%Y-%m-%d %H:%M:%S")
        assert "2023-10-31 12:30:00" in result

    def test_format_timestamp_unix(self):
        """Test Unix timestamp formatting."""
        timestamp = 1698765432  # 2023-10-31
        result = format_timestamp(timestamp)
        assert "2023-10-31" in result

    def test_format_timestamp_none(self):
        """Test None handling."""
        assert format_timestamp(None) == "—"

    def test_format_timestamp_string(self):
        """Test ISO string formatting."""
        iso_string = "2023-10-31T12:30:00Z"
        result = format_timestamp(iso_string)
        assert "2023-10-31" in result

    def test_format_timestamp_custom_format(self):
        """Test custom format string."""
        dt = datetime(2023, 10, 31, 12, 30)
        assert format_timestamp(dt, "%Y/%m/%d") == "2023/10/31"


class TestFormatDurationSeconds:
    """Test format_duration_seconds function."""

    def test_duration_seconds_only(self):
        """Test seconds formatting."""
        assert format_duration_seconds(45) == "45s"
        assert format_duration_seconds(30) == "30s"

    def test_duration_minutes_seconds(self):
        """Test minutes and seconds."""
        assert format_duration_seconds(150) == "2m 30s"
        assert format_duration_seconds(90) == "1m 30s"

    def test_duration_hours_minutes_seconds(self):
        """Test hours, minutes, seconds."""
        assert format_duration_seconds(7265) == "2h 1m 5s"
        assert format_duration_seconds(3661) == "1h 1m 1s"

    def test_duration_zero(self):
        """Test zero duration."""
        assert format_duration_seconds(0) == "0s"


class TestFormatDurationMinutes:
    """Test format_duration_minutes function."""

    def test_duration_minutes_only(self):
        """Test minutes formatting."""
        assert format_duration_minutes(45) == "45 мин"
        assert format_duration_minutes(30) == "30 мин"

    def test_duration_hours_minutes(self):
        """Test hours and minutes."""
        assert format_duration_minutes(150) == "2 ч 30 мин"
        assert format_duration_minutes(120) == "2 ч 0 мин"

    def test_duration_zero_minutes(self):
        """Test zero minutes."""
        assert format_duration_minutes(0) == "0 мин"


class TestFormatBytes:
    """Test format_bytes function."""

    def test_bytes_basic_units(self):
        """Test different byte units."""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1048576) == "1.00 MB"
        assert format_bytes(1073741824) == "1.00 GB"

    def test_bytes_large_values(self):
        """Test large byte values."""
        assert format_bytes(5368709120) == "5.00 GB"
        assert format_bytes(1099511627776) == "1.00 TB"

    def test_bytes_small_values(self):
        """Test bytes smaller than KB."""
        assert format_bytes(500) == "500.00 B"
        assert format_bytes(0) == "0.00 B"

    def test_bytes_custom_precision(self):
        """Test custom precision."""
        assert format_bytes(1500, 1) == "1.5 KB"
        assert format_bytes(2500000, 0) == "2 MB"


class TestFormatLargeNumber:
    """Test format_large_number function."""

    def test_large_number_thousands(self):
        """Test thousands (K) suffix."""
        assert format_large_number(1500) == "1.5K"
        assert format_large_number(50000) == "50.0K"

    def test_large_number_millions(self):
        """Test millions (M) suffix."""
        assert format_large_number(1500000) == "1.5M"
        assert format_large_number(75000000) == "75.0M"

    def test_large_number_billions(self):
        """Test billions (B) suffix."""
        assert format_large_number(2300000000) == "2.3B"
        assert format_large_number(15000000000) == "15.0B"

    def test_large_number_small(self):
        """Test numbers smaller than 1000."""
        assert format_large_number(500) == "500"
        assert format_large_number(99) == "99"

    def test_large_number_negative(self):
        """Test negative numbers."""
        assert format_large_number(-1500) == "-1.5K"
        assert format_large_number(-2000000) == "-2.0M"

    def test_large_number_zero(self):
        """Test zero."""
        assert format_large_number(0) == "0"


class TestSafeFloat:
    """Test safe_float function."""

    def test_safe_float_string(self):
        """Test string conversion."""
        assert safe_float("123.45") == 123.45
        assert safe_float("100") == 100.0

    def test_safe_float_invalid(self):
        """Test invalid values."""
        assert safe_float("invalid", 0.0) == 0.0
        assert safe_float("abc", -1.0) == -1.0

    def test_safe_float_none(self):
        """Test None handling."""
        assert safe_float(None, 0.0) == 0.0
        assert safe_float(None, 99.9) == 99.9

    def test_safe_float_numeric(self):
        """Test numeric values."""
        assert safe_float(123.45) == 123.45
        assert safe_float(100) == 100.0

    def test_safe_float_nan(self):
        """Test NaN handling."""
        assert safe_float(float('nan'), 0.0) == 0.0


class TestSafeInt:
    """Test safe_int function."""

    def test_safe_int_string(self):
        """Test string conversion."""
        assert safe_int("123") == 123
        assert safe_int("123.99") == 123

    def test_safe_int_invalid(self):
        """Test invalid values."""
        assert safe_int("invalid", -1) == -1
        assert safe_int("abc", 0) == 0

    def test_safe_int_none(self):
        """Test None handling."""
        assert safe_int(None, 0) == 0
        assert safe_int(None, 999) == 999

    def test_safe_int_numeric(self):
        """Test numeric values."""
        assert safe_int(123) == 123
        assert safe_int(123.99) == 123


class TestTruncateString:
    """Test truncate_string function."""

    def test_truncate_long_string(self):
        """Test truncating long string."""
        text = "Very long text that needs truncation"
        result = truncate_string(text, 20)
        assert result == "Very long text th..."
        assert len(result) == 20

    def test_truncate_short_string(self):
        """Test short string unchanged."""
        text = "Short text"
        assert truncate_string(text, 50) == "Short text"

    def test_truncate_custom_suffix(self):
        """Test custom suffix."""
        text = "Very long text"
        result = truncate_string(text, 10, " [...]")
        assert result.endswith(" [...]")
        assert len(result) == 10

    def test_truncate_exact_length(self):
        """Test string at exact max length."""
        text = "12345"
        assert truncate_string(text, 5) == "12345"


class TestSafeJsonLoads:
    """Test safe_json_loads function."""

    def test_json_loads_valid(self):
        """Test valid JSON parsing."""
        assert safe_json_loads('{"key": "value"}') == {"key": "value"}
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]

    def test_json_loads_invalid(self):
        """Test invalid JSON."""
        assert safe_json_loads('invalid json', default={}) == {}
        assert safe_json_loads('not json', default=None) is None

    def test_json_loads_empty(self):
        """Test empty string."""
        assert safe_json_loads('', default={}) == {}
        assert safe_json_loads('   ', default=None) is None

    def test_json_loads_none_string(self):
        """Test non-string input."""
        assert safe_json_loads(None, default={}) == {}

    def test_json_loads_complex(self):
        """Test complex JSON structures."""
        json_str = '{"nested": {"key": "value"}, "array": [1, 2, 3]}'
        result = safe_json_loads(json_str)
        assert result["nested"]["key"] == "value"
        assert result["array"] == [1, 2, 3]


class TestClamp:
    """Test clamp function."""

    def test_clamp_within_range(self):
        """Test value within range."""
        assert clamp(5, 0, 10) == 5
        assert clamp(7.5, 0, 10) == 7.5

    def test_clamp_below_min(self):
        """Test value below minimum."""
        assert clamp(-5, 0, 10) == 0
        assert clamp(-100, -50, 50) == -50

    def test_clamp_above_max(self):
        """Test value above maximum."""
        assert clamp(15, 0, 10) == 10
        assert clamp(200, 0, 100) == 100

    def test_clamp_at_boundaries(self):
        """Test values at boundaries."""
        assert clamp(0, 0, 10) == 0
        assert clamp(10, 0, 10) == 10


class TestFormatPercentageChange:
    """Test format_percentage_change function."""

    def test_percentage_change_positive(self):
        """Test positive change."""
        assert format_percentage_change(100, 150) == "+50.00%"
        assert format_percentage_change(50, 75) == "+50.00%"

    def test_percentage_change_negative(self):
        """Test negative change."""
        assert format_percentage_change(100, 75) == "-25.00%"
        assert format_percentage_change(200, 150) == "-25.00%"

    def test_percentage_change_no_change(self):
        """Test zero change."""
        assert format_percentage_change(100, 100) == "0.00%"

    def test_percentage_change_zero_base(self):
        """Test zero base value."""
        assert format_percentage_change(0, 100) == "N/A"
        assert format_percentage_change(0, 0) == "N/A"

    def test_percentage_change_custom_precision(self):
        """Test custom precision."""
        assert format_percentage_change(100, 133.333, 1) == "+33.3%"
        assert format_percentage_change(100, 166.666, 3) == "+66.666%"
