"""
Time utilities for backend
Provides common time functions used across the application
"""

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime

    Returns:
        datetime: Current time in UTC timezone

    Example:
        >>> now = utc_now()
        >>> now.isoformat()
        '2024-12-04T10:30:45.123456+00:00'
    """
    return datetime.now(UTC)


def utc_timestamp() -> float:
    """
    Get current UTC time as UNIX timestamp (seconds since epoch)

    Returns:
        float: UNIX timestamp

    Example:
        >>> ts = utc_timestamp()
        >>> ts > 1700000000
        True
    """
    return utc_now().timestamp()


def utc_isoformat(dt: datetime | None = None, include_tz: bool = True) -> str:
    """
    Convert datetime to ISO format string

    Args:
        dt: Datetime object. If None, uses current UTC time
        include_tz: Whether to include timezone in output (default: True)

    Returns:
        str: ISO format datetime string

    Example:
        >>> iso = utc_isoformat()
        >>> iso
        '2024-12-04T10:30:45.123456+00:00'
        >>> iso_z = utc_isoformat(include_tz=True)
        >>> iso_z.endswith('Z')
        False
    """
    if dt is None:
        dt = utc_now()

    iso_str = dt.isoformat()

    if include_tz and "+00:00" in iso_str:
        # Convert +00:00 to Z for consistency with some APIs
        iso_str = iso_str.replace("+00:00", "Z")

    return iso_str


def parse_iso_timestamp(iso_str: str) -> datetime:
    """
    Parse ISO format datetime string to timezone-aware datetime

    Args:
        iso_str: ISO format datetime string (e.g., '2024-12-04T10:30:45Z')

    Returns:
        datetime: Timezone-aware datetime object in UTC

    Example:
        >>> dt = parse_iso_timestamp('2024-12-04T10:30:45Z')
        >>> dt.tzinfo is not None
        True
    """
    # Handle Z timezone indicator
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"

    return datetime.fromisoformat(iso_str)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convert datetime to UNIX timestamp

    Args:
        dt: Datetime object

    Returns:
        float: UNIX timestamp
    """
    return dt.timestamp()


def timestamp_to_datetime(ts: float) -> datetime:
    """
    Convert UNIX timestamp to timezone-aware datetime (UTC)

    Args:
        ts: UNIX timestamp (seconds since epoch)

    Returns:
        datetime: Timezone-aware datetime in UTC
    """
    return datetime.fromtimestamp(ts, tz=UTC)


def add_days(dt: datetime, days: int) -> datetime:
    """
    Add days to a datetime object

    Args:
        dt: Base datetime
        days: Number of days to add (can be negative)

    Returns:
        datetime: New datetime with days added
    """
    return dt + timedelta(days=days)


def add_hours(dt: datetime, hours: int) -> datetime:
    """
    Add hours to a datetime object

    Args:
        dt: Base datetime
        hours: Number of hours to add (can be negative)

    Returns:
        datetime: New datetime with hours added
    """
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Add minutes to a datetime object

    Args:
        dt: Base datetime
        minutes: Number of minutes to add (can be negative)

    Returns:
        datetime: New datetime with minutes added
    """
    return dt + timedelta(minutes=minutes)


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """
    Add seconds to a datetime object

    Args:
        dt: Base datetime
        seconds: Number of seconds to add (can be negative)

    Returns:
        datetime: New datetime with seconds added
    """
    return dt + timedelta(seconds=seconds)


def time_until(target: datetime) -> timedelta:
    """
    Calculate time until a target datetime from now

    Args:
        target: Target datetime

    Returns:
        timedelta: Time remaining (can be negative if target is in the past)
    """
    return target - utc_now()


def seconds_until(target: datetime) -> float:
    """
    Calculate seconds until a target datetime from now

    Args:
        target: Target datetime

    Returns:
        float: Seconds remaining (can be negative if target is in the past)
    """
    return time_until(target).total_seconds()


__all__ = [
    "add_days",
    "add_hours",
    "add_minutes",
    "add_seconds",
    "datetime_to_timestamp",
    "parse_iso_timestamp",
    "seconds_until",
    "time_until",
    "timestamp_to_datetime",
    "utc_isoformat",
    "utc_now",
    "utc_timestamp",
]
