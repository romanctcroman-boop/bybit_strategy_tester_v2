"""
Settings (pydantic-settings) with graceful fallback when the package is unavailable.

Expose a unified SETTINGS object used across the backend. This file prefers
pydantic-settings when installed (for validation and .env parsing), and
falls back to a minimal environment loader otherwise.
"""

from __future__ import annotations

import os
from typing import List, Optional

try:
    from pydantic import BaseModel, Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover
    BaseSettings = None  # type: ignore
    BaseModel = object  # type: ignore

    def Field(*a, **k):  # type: ignore
        return None


if BaseSettings is not None:

    class DatabaseSettings(BaseSettings):
        url: Optional[str] = None
        model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    class RedisSettings(BaseSettings):
        url: Optional[str] = None
        channel_ticks: str = "bybit:ticks"
        channel_klines: str = "bybit:klines"
        stream_ticks: str = "stream:bybit:ticks"
        stream_klines: str = "stream:bybit:klines"
        model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    class WSSettings(BaseSettings):
        enabled: bool = Field(False, alias="BYBIT_WS_ENABLED")
        symbols: str = Field("BTCUSDT", alias="BYBIT_WS_SYMBOLS")
        intervals: str = Field("1", alias="BYBIT_WS_INTERVALS")
        reconnect_delay_sec: float = Field(1.5, alias="WS_RECONNECT_DELAY_SEC")
        max_reconnect_delay_sec: float = Field(15.0, alias="WS_RECONNECT_DELAY_MAX_SEC")
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

        @property
        def symbols_list(self) -> List[str]:
            return [s.strip().upper() for s in (self.symbols or "").split(",") if s.strip()]

        @property
        def intervals_list(self) -> List[str]:
            return [s.strip().upper() for s in (self.intervals or "").split(",") if s.strip()]

    class CelerySettings(BaseSettings):
        eager: bool = Field(False, alias="CELERY_EAGER")
        broker_url: Optional[str] = Field(None, alias="CELERY_BROKER_URL")
        result_backend: Optional[str] = Field(None, alias="CELERY_RESULT_BACKEND")
        task_default_queue: str = Field("default", alias="CELERY_TASK_DEFAULT_QUEUE")
        acks_late: bool = Field(True, alias="CELERY_ACKS_LATE")
        prefetch_multiplier: int = Field(4, alias="CELERY_PREFETCH_MULTIPLIER")
        task_default_retry_delay: int = Field(5, alias="CELERY_TASK_DEFAULT_RETRY_DELAY")
        task_max_retries: int = Field(3, alias="CELERY_TASK_MAX_RETRIES")
        # Per-algorithm routing (optional overrides)
        queue_grid: str = Field("optimizations.grid", alias="CELERY_QUEUE_GRID")
        queue_walk: str = Field("optimizations.walk", alias="CELERY_QUEUE_WALK")
        queue_bayes: str = Field("optimizations.bayes", alias="CELERY_QUEUE_BAYES")
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    class AppSettings(BaseSettings):
        database: DatabaseSettings = DatabaseSettings()
        redis: RedisSettings = RedisSettings()
        ws: WSSettings = WSSettings()
        celery: CelerySettings = CelerySettings()
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SETTINGS = AppSettings()
else:
    # Fallback implementation using environment variables only
    class _Redis:
        def __init__(self) -> None:
            url = os.environ.get("REDIS_URL")
            if not url:
                host = os.environ.get("REDIS_HOST", "127.0.0.1").strip()
                port = os.environ.get("REDIS_PORT", "6379").strip()
                db = os.environ.get("REDIS_DB", "0").strip()
                url = f"redis://{host}:{port}/{db}"
            self.url = url
            self.channel_ticks = os.environ.get("REDIS_CHANNEL_TICKS", "bybit:ticks")
            self.channel_klines = os.environ.get("REDIS_CHANNEL_KLINES", "bybit:klines")
            self.stream_ticks = os.environ.get("REDIS_STREAM_TICKS", "stream:bybit:ticks")
            self.stream_klines = os.environ.get("REDIS_STREAM_KLINES", "stream:bybit:klines")

    class _WS:
        def __init__(self) -> None:
            self.enabled = os.environ.get("BYBIT_WS_ENABLED", "0").lower() in ("1", "true", "yes")
            self.symbols = os.environ.get("BYBIT_WS_SYMBOLS", "BTCUSDT")
            self.intervals = os.environ.get("BYBIT_WS_INTERVALS", "1")
            self.reconnect_delay_sec = float(os.environ.get("WS_RECONNECT_DELAY_SEC", "1.5") or 1.5)
            self.max_reconnect_delay_sec = float(
                os.environ.get("WS_RECONNECT_DELAY_MAX_SEC", "15") or 15.0
            )

        @property
        def symbols_list(self) -> List[str]:
            return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]

        @property
        def intervals_list(self) -> List[str]:
            return [s.strip().upper() for s in self.intervals.split(",") if s.strip()]

    class _Celery:
        def __init__(self) -> None:
            self.eager = os.environ.get("CELERY_EAGER", "0").lower() in ("1", "true", "yes")
            self.broker_url = os.environ.get("CELERY_BROKER_URL")
            self.result_backend = os.environ.get("CELERY_RESULT_BACKEND")
            self.task_default_queue = os.environ.get("CELERY_TASK_DEFAULT_QUEUE", "default")
            self.acks_late = os.environ.get("CELERY_ACKS_LATE", "1").lower() in ("1", "true", "yes")
            self.prefetch_multiplier = int(os.environ.get("CELERY_PREFETCH_MULTIPLIER", "4") or 4)
            self.task_default_retry_delay = int(
                os.environ.get("CELERY_TASK_DEFAULT_RETRY_DELAY", "5") or 5
            )
            self.task_max_retries = int(os.environ.get("CELERY_TASK_MAX_RETRIES", "3") or 3)
            self.queue_grid = os.environ.get("CELERY_QUEUE_GRID", "optimizations.grid")
            self.queue_walk = os.environ.get("CELERY_QUEUE_WALK", "optimizations.walk")
            self.queue_bayes = os.environ.get("CELERY_QUEUE_BAYES", "optimizations.bayes")

    class _Settings:
        def __init__(self) -> None:
            self.database = type("DB", (), {"url": os.environ.get("DATABASE_URL")})()
            self.redis = _Redis()
            self.ws = _WS()
            self.celery = _Celery()

    SETTINGS = _Settings()

__all__ = ["SETTINGS", "AppSettings"]
