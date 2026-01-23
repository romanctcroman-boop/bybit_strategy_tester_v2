"""
Configuration management for Bybit Adapter.

Loads configuration from environment variables with sensible defaults.
Uses pydantic-settings for validation and type checking.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class BybitConfig(BaseSettings):
    """
    Bybit Adapter configuration.

    All settings can be overridden via environment variables with BYBIT_ prefix.
    Example: BYBIT_API_TIMEOUT=30
    """

    # API настройки
    API_BASE_URL: str = "https://api.bybit.com"
    API_TIMEOUT: int = 10  # секунд
    RATE_LIMIT_DELAY: float = 0.2  # секунд между запросами
    MAX_REQUESTS_PER_BATCH: int = 7  # макс запросов за batch загрузку

    # Retry настройки
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_INITIAL_DELAY: float = 1.0
    RETRY_BACKOFF_FACTOR: float = 2.0

    # Кэш настройки
    CACHE_ENABLED: bool = True
    CACHE_DIR: str = "cache/bybit_klines"
    CACHE_TTL_DAYS: int = 7
    CACHE_MAX_CANDLES: int = 2000

    # Redis настройки
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_ENABLED: bool = False  # Включить Redis кэш

    # База данных
    DB_PERSIST_ENABLED: bool = True
    PERSIST_KLINES: str = "1"  # "1", "true", "yes" для включения
    DB_BATCH_SIZE: int = 1000

    # API ключи (опционально, для приватных запросов)
    API_KEY: Optional[str] = None
    API_SECRET: Optional[str] = None

    # Мониторинг и логирование
    ENABLE_METRICS: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    LOG_JSON_FORMAT: bool = False

    # Детальное логирование (для отладки)
    ENABLE_DETAILED_LOGGING: bool = False

    # Agent analysis cache settings
    AGENT_ANALYSIS_CACHE_ENABLED: bool = True
    AGENT_ANALYSIS_CACHE_TTL: int = 3600
    AGENT_ANALYSIS_CACHE_NAMESPACE: str = "agent:analysis"

    # AI Response Cache settings (NEW!)
    AI_CACHE_ENABLED: bool = True
    AI_CACHE_TTL: int = 3600  # 1 hour default
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BYBIT_", case_sensitive=False, extra="ignore"
    )

    @property
    def persist_to_db(self) -> bool:
        """
        Check if DB persistence is enabled.
        """
        return self.PERSIST_KLINES.lower() in ("1", "true", "yes", "y")

    @property
    def cache_path(self) -> str:
        """
        Get full cache directory path.
        """
        return os.path.abspath(self.CACHE_DIR)


# Global config instance
config = BybitConfig()


def get_config() -> BybitConfig:
    """
    Get global configuration instance.
    """
    return config


def reload_config() -> BybitConfig:
    """
    Reload configuration from environment.
    Useful for testing or runtime config changes.
    """
    global config
    config = BybitConfig()
    return config
