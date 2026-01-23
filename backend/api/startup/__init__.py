"""
Startup Module

Contains application startup and shutdown helpers.
Extracted from app.py lifespan for better modularity.
"""

from backend.api.startup.warmup import warmup_cache
from backend.api.startup.refresh import refresh_daily_data_background

__all__ = [
    "warmup_cache",
    "refresh_daily_data_background",
]
