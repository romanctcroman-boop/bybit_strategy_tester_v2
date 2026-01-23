"""
Database Retention Policy Configuration.

Centralized configuration for data retention and management.
All database-related services MUST import constants from here.

Policy:
- Minimum start date: DATA_START_DATE (2025-01-01)
- Maximum retention period: RETENTION_YEARS (2 years)
- Retention check frequency: RETENTION_CHECK_DAYS (30 days)
- Sliding window: when data exceeds limit, oldest month is trimmed
"""

from datetime import datetime, timezone

# =============================================================================
# DATA RETENTION POLICY CONSTANTS
# =============================================================================

# Minimum start date for all historical data
# No data before this date will be stored in the database
DATA_START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)

# Data start timestamp in milliseconds (for DB queries)
DATA_START_TIMESTAMP_MS = int(DATA_START_DATE.timestamp() * 1000)

# Maximum retention period in years
RETENTION_YEARS = 2

# Maximum retention period in days
MAX_RETENTION_DAYS = RETENTION_YEARS * 365

# How often to check and enforce retention policy (in days)
RETENTION_CHECK_DAYS = 30


# =============================================================================
# DEFAULT INTERVALS AND SYMBOLS
# =============================================================================

# Default warmup pairs for server startup
DEFAULT_WARMUP_PAIRS = [
    ("BTCUSDT", "15"),
    ("BTCUSDT", "60"),
    ("BTCUSDT", "D"),
]

# Daily interval identifier (for volatility calculations)
DAILY_INTERVAL = "D"

# Default number of candles to load for initial history
DEFAULT_INITIAL_CANDLES = 500

# Intervals to always include when loading symbol data
MANDATORY_INTERVALS = ["D"]  # Daily always required for volatility


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_data_start_timestamp_ms() -> int:
    """Get the minimum allowed timestamp in milliseconds."""
    return DATA_START_TIMESTAMP_MS


def is_timestamp_valid(timestamp_ms: int) -> bool:
    """Check if timestamp is within valid retention window."""
    return timestamp_ms >= DATA_START_TIMESTAMP_MS


def get_min_allowed_date() -> datetime:
    """Get the minimum allowed date for data storage."""
    return DATA_START_DATE


def calculate_cutoff_date(min_date: datetime, months: int = 1) -> datetime:
    """Calculate cutoff date for retention trimming."""
    from dateutil.relativedelta import relativedelta

    return min_date + relativedelta(months=months)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    "DATA_START_DATE",
    "DATA_START_TIMESTAMP_MS",
    "RETENTION_YEARS",
    "MAX_RETENTION_DAYS",
    "RETENTION_CHECK_DAYS",
    "DEFAULT_WARMUP_PAIRS",
    "DAILY_INTERVAL",
    "DEFAULT_INITIAL_CANDLES",
    "MANDATORY_INTERVALS",
    # Functions
    "get_data_start_timestamp_ms",
    "is_timestamp_valid",
    "get_min_allowed_date",
    "calculate_cutoff_date",
]
