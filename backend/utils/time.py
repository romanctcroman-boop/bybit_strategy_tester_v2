"""Time utilities for UTC-aware timestamps.

All system timestamps must be timezone-aware (UTC) to comply with project rules.
Use utc_now() instead of datetime.now() / datetime.utcnow().
"""
from datetime import datetime, timezone

__all__ = ["utc_now"]

def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime.

    Example ISO format: 2025-11-17T18:45:04.891604+00:00
    """
    return datetime.now(timezone.utc)
