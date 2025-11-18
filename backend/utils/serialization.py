"""
Serialization utilities for FastAPI endpoints.

Provides recursive datetime serialization to ensure all nested datetime
objects are converted to ISO format strings.
"""

from datetime import date, datetime
from typing import Any


def recursive_datetime_serializer(obj: Any) -> Any:
    """
    Recursively convert datetime objects to ISO format strings.
    
    Handles nested dictionaries, lists, and datetime objects at any depth.
    Essential for FastAPI responses with complex nested structures.
    
    Args:
        obj: Object to serialize (dict, list, datetime, or primitive)
        
    Returns:
        Serialized object with all datetime instances converted to ISO strings
        
    Examples:
        >>> from datetime import datetime, UTC
        >>> data = {
        ...     'created_at': datetime(2023, 1, 1, 12, 0, tzinfo=UTC),
        ...     'nested': {
        ...         'timestamps': [datetime(2023, 1, 1), datetime(2023, 1, 2)]
        ...     }
        ... }
        >>> result = recursive_datetime_serializer(data)
        >>> isinstance(result['created_at'], str)
        True
        >>> all(isinstance(ts, str) for ts in result['nested']['timestamps'])
        True
    
    Use cases:
        - FastAPI endpoint responses with nested datetime fields
        - JSON serialization of complex database models
        - Ensuring consistent datetime format across API responses
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: recursive_datetime_serializer(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_datetime_serializer(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(recursive_datetime_serializer(item) for item in obj)
    else:
        return obj


def serialize_model_dict(model_dict: dict) -> dict:
    """
    Serialize a SQLAlchemy model's __dict__ with datetime conversion.
    
    Convenience wrapper around recursive_datetime_serializer specifically
    for database model dictionaries.
    
    Args:
        model_dict: Dictionary from model.__dict__
        
    Returns:
        Serialized dictionary ready for JSON response
        
    Example:
        >>> from backend.models.backtest import Backtest
        >>> backtest = db.get_backtest(1)
        >>> serialized = serialize_model_dict(backtest.__dict__)
        >>> # All datetime fields are now ISO strings
    """
    return recursive_datetime_serializer(model_dict)
