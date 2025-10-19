"""
Utility functions for timestamp normalization and handling

Ensures consistent datetime handling across the application.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
import pandas as pd


def normalize_timestamps(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize timestamps in candles to naive datetime objects
    
    Converts:
    - Timezone-aware datetime → naive datetime (UTC)
    - Integer (milliseconds) → naive datetime
    - String (ISO format) → naive datetime
    
    Args:
        candles: List of candle dictionaries with 'timestamp' key
        
    Returns:
        Same candles list with normalized timestamps (in-place modification)
        
    Example:
        >>> candles = [{'timestamp': 1697500000000, 'open': 100, ...}]
        >>> normalize_timestamps(candles)
        >>> isinstance(candles[0]['timestamp'], datetime)
        True
    """
    for candle in candles:
        if 'timestamp' not in candle:
            continue
            
        ts = candle['timestamp']
        
        # Already naive datetime - nothing to do
        if isinstance(ts, datetime) and ts.tzinfo is None:
            continue
            
        # Timezone-aware datetime - convert to naive UTC
        elif isinstance(ts, datetime) and ts.tzinfo is not None:
            candle['timestamp'] = ts.replace(tzinfo=None)
            
        # Integer (milliseconds) - convert to datetime
        elif isinstance(ts, (int, float)):
            candle['timestamp'] = datetime.fromtimestamp(ts / 1000)
            
        # String - parse to datetime
        elif isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                candle['timestamp'] = dt.replace(tzinfo=None)
            except ValueError:
                # Fallback: try parsing as timestamp
                try:
                    candle['timestamp'] = datetime.fromtimestamp(float(ts) / 1000)
                except:
                    pass  # Keep original if can't parse
                    
    return candles


def candles_to_dataframe(candles: List[Dict[str, Any]], set_index: bool = True) -> pd.DataFrame:
    """
    Convert candles list to pandas DataFrame with proper timestamp handling
    
    Args:
        candles: List of candle dictionaries
        set_index: If True, set 'timestamp' as DataFrame index
        
    Returns:
        pandas DataFrame with OHLCV data
        
    Example:
        >>> candles = [{'timestamp': datetime.now(), 'open': 100, ...}]
        >>> df = candles_to_dataframe(candles)
        >>> df.index.name
        'timestamp'
    """
    # Normalize timestamps first
    normalize_timestamps(candles)
    
    # Create DataFrame
    df = pd.DataFrame(candles)
    
    # Ensure timestamp is datetime type
    if 'timestamp' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            # Try to convert if not already datetime
            try:
                if pd.api.types.is_integer_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            except:
                pass  # Keep as is if conversion fails
        
        # Set as index if requested
        if set_index:
            df = df.set_index('timestamp')
    
    return df


def dataframe_to_candles(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert pandas DataFrame back to candles list
    
    Args:
        df: DataFrame with OHLCV data (timestamp as index or column)
        
    Returns:
        List of candle dictionaries
        
    Example:
        >>> df = pd.DataFrame({'open': [100], 'high': [105], ...})
        >>> candles = dataframe_to_candles(df)
        >>> len(candles)
        1
    """
    # Reset index if timestamp is index
    if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
    
    # Convert to dict
    candles = df.to_dict('records')
    
    # Normalize timestamps
    normalize_timestamps(candles)
    
    return candles


def get_naive_utc_now() -> datetime:
    """
    Get current UTC time as naive datetime
    
    Returns:
        Current UTC datetime without timezone info
        
    Example:
        >>> now = get_naive_utc_now()
        >>> now.tzinfo is None
        True
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def datetime_to_ms(dt: datetime) -> int:
    """
    Convert datetime to milliseconds timestamp
    
    Args:
        dt: datetime object (naive or aware)
        
    Returns:
        Unix timestamp in milliseconds
        
    Example:
        >>> dt = datetime(2025, 1, 1, 0, 0, 0)
        >>> ms = datetime_to_ms(dt)
        >>> ms > 0
        True
    """
    return int(dt.timestamp() * 1000)


def ms_to_datetime(ms: int) -> datetime:
    """
    Convert milliseconds timestamp to naive datetime
    
    Args:
        ms: Unix timestamp in milliseconds
        
    Returns:
        Naive datetime object
        
    Example:
        >>> dt = ms_to_datetime(1704067200000)
        >>> dt.year
        2024
    """
    return datetime.fromtimestamp(ms / 1000)
