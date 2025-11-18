"""
Tests for serialization utilities

Coverage target: 0% → 100%
"""

import pytest
from datetime import UTC, date, datetime

from backend.utils.serialization import (
    recursive_datetime_serializer,
    serialize_model_dict,
)


class TestRecursiveDatetimeSerializer:
    """Test recursive datetime serialization."""

    def test_datetime_to_iso_string(self):
        """Test datetime conversion to ISO string."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        result = recursive_datetime_serializer(dt)
        
        assert isinstance(result, str)
        assert result == "2024-01-15T10:30:45+00:00"

    def test_date_to_iso_string(self):
        """Test date conversion to ISO string."""
        d = date(2024, 1, 15)
        result = recursive_datetime_serializer(d)
        
        assert isinstance(result, str)
        assert result == "2024-01-15"

    def test_dict_with_datetime(self):
        """Test dictionary with datetime values."""
        data = {
            "name": "test",
            "created_at": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            "count": 42,
        }
        
        result = recursive_datetime_serializer(data)
        
        assert result["name"] == "test"
        assert result["created_at"] == "2024-01-01T12:00:00+00:00"
        assert result["count"] == 42

    def test_nested_dict_with_datetimes(self):
        """Test nested dictionaries with multiple datetime levels."""
        data = {
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "nested": {
                "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
                "deep": {
                    "timestamp": datetime(2024, 1, 3, tzinfo=UTC),
                }
            }
        }
        
        result = recursive_datetime_serializer(data)
        
        assert isinstance(result["created_at"], str)
        assert isinstance(result["nested"]["updated_at"], str)
        assert isinstance(result["nested"]["deep"]["timestamp"], str)

    def test_list_with_datetimes(self):
        """Test list containing datetime objects."""
        data = [
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 3, tzinfo=UTC),
        ]
        
        result = recursive_datetime_serializer(data)
        
        assert len(result) == 3
        assert all(isinstance(item, str) for item in result)
        assert result[0] == "2024-01-01T00:00:00+00:00"

    def test_tuple_with_datetimes(self):
        """Test tuple containing datetime objects."""
        data = (
            datetime(2024, 1, 1, tzinfo=UTC),
            "text",
            42,
        )
        
        result = recursive_datetime_serializer(data)
        
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[0] == "2024-01-01T00:00:00+00:00"
        assert result[1] == "text"
        assert result[2] == 42

    def test_list_of_dicts_with_datetimes(self):
        """Test list of dictionaries containing datetimes."""
        data = [
            {"id": 1, "timestamp": datetime(2024, 1, 1, tzinfo=UTC)},
            {"id": 2, "timestamp": datetime(2024, 1, 2, tzinfo=UTC)},
        ]
        
        result = recursive_datetime_serializer(data)
        
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert isinstance(result[0]["timestamp"], str)
        assert result[1]["id"] == 2
        assert isinstance(result[1]["timestamp"], str)

    def test_primitives_unchanged(self):
        """Test that primitive types pass through unchanged."""
        assert recursive_datetime_serializer("text") == "text"
        assert recursive_datetime_serializer(42) == 42
        assert recursive_datetime_serializer(3.14) == 3.14
        assert recursive_datetime_serializer(True) is True
        assert recursive_datetime_serializer(None) is None

    def test_empty_containers(self):
        """Test empty containers."""
        assert recursive_datetime_serializer({}) == {}
        assert recursive_datetime_serializer([]) == []
        assert recursive_datetime_serializer(()) == ()

    def test_mixed_nested_structure(self):
        """Test complex nested structure with mixed types."""
        data = {
            "backtest": {
                "id": 1,
                "created_at": datetime(2024, 1, 1, tzinfo=UTC),
                "trades": [
                    {
                        "entry_time": datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                        "exit_time": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                        "pnl": 100.5,
                    },
                    {
                        "entry_time": datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
                        "exit_time": datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
                        "pnl": -50.2,
                    },
                ],
                "metadata": ("info", datetime(2024, 1, 1, tzinfo=UTC)),
            }
        }
        
        result = recursive_datetime_serializer(data)
        
        assert isinstance(result["backtest"]["created_at"], str)
        assert isinstance(result["backtest"]["trades"][0]["entry_time"], str)
        assert isinstance(result["backtest"]["trades"][1]["exit_time"], str)
        assert result["backtest"]["trades"][0]["pnl"] == 100.5
        assert isinstance(result["backtest"]["metadata"][1], str)


class TestSerializeModelDict:
    """Test serialize_model_dict convenience wrapper."""

    def test_serialize_model_dict_with_datetimes(self):
        """Test serializing model dictionary."""
        model_dict = {
            "id": 1,
            "name": "Test Strategy",
            "created_at": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            "updated_at": datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
            "config": {
                "param1": 10,
                "last_modified": datetime(2024, 1, 3, tzinfo=UTC),
            },
        }
        
        result = serialize_model_dict(model_dict)
        
        assert result["id"] == 1
        assert result["name"] == "Test Strategy"
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)
        assert isinstance(result["config"]["last_modified"], str)

    def test_serialize_empty_dict(self):
        """Test serializing empty dictionary."""
        result = serialize_model_dict({})
        assert result == {}

    def test_serialize_dict_without_datetimes(self):
        """Test serializing dictionary with no datetime fields."""
        model_dict = {
            "id": 1,
            "name": "Test",
            "count": 42,
        }
        
        result = serialize_model_dict(model_dict)
        
        assert result == model_dict
