"""
Backend Configuration Package
Central configuration management for the backend system.
"""

import os
from typing import Any


class ConfigNamespace:
    """Configuration namespace"""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"No attribute '{name}'")
        return self._data.get(name)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._data.get(key, default)


def _ns(**kwargs) -> ConfigNamespace:
    """Create configuration namespace"""
    return ConfigNamespace(kwargs)


def _build_config() -> ConfigNamespace:
    """Build configuration from environment and defaults"""
    return ConfigNamespace(
        {
            "DEBUG": os.getenv("DEBUG", "False").lower() in ("true", "1", "yes"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///./bybit_strategy_tester.db"),
            "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            "API_HOST": os.getenv("API_HOST", "0.0.0.0"),
            "API_PORT": int(os.getenv("API_PORT", "8000")),
            "ENABLE_WEBSOCKETS": os.getenv("ENABLE_WEBSOCKETS", "False").lower() in ("true", "1", "yes"),
            "BYBIT_API_KEY": os.getenv("BYBIT_API_KEY", ""),
            "BYBIT_API_SECRET": os.getenv("BYBIT_API_SECRET", ""),
            "BYBIT_TESTNET": os.getenv("BYBIT_TESTNET", "True").lower() in ("true", "1", "yes"),
        }
    )


# Global configuration instance
CONFIG = _build_config()

# Settings alias for compatibility
SETTINGS = CONFIG

# Re-export database policy constants for convenience
from backend.config.database_policy import (
    DAILY_INTERVAL,
    DATA_START_DATE,
    DATA_START_TIMESTAMP_MS,
    DEFAULT_INITIAL_CANDLES,
    MANDATORY_INTERVALS,
    MAX_RETENTION_DAYS,
    RETENTION_CHECK_DAYS,
    RETENTION_YEARS,
)

__all__ = [
    "CONFIG",
    "SETTINGS",
    "_ns",
    "_build_config",
    # Database policy
    "DATA_START_DATE",
    "DATA_START_TIMESTAMP_MS",
    "RETENTION_YEARS",
    "MAX_RETENTION_DAYS",
    "RETENTION_CHECK_DAYS",
    "DAILY_INTERVAL",
    "DEFAULT_INITIAL_CANDLES",
    "MANDATORY_INTERVALS",
]
