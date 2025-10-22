"""Compatibility layer for configuration.

Primary source is backend.settings.SETTINGS (pydantic-settings). If unavailable,
falls back to the local env-based loader included in backend.settings.

This module exposes a minimal CONFIG object with attributes used across the app:
 - redis.url, redis.channel_ticks, redis.channel_klines
 - ws_enabled, ws_symbols, ws_intervals
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import List

try:
    from backend.settings import SETTINGS  # type: ignore
except Exception:  # pragma: no cover
    SETTINGS = None  # type: ignore


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _build_config():
    if SETTINGS is None:
        # Very defensive fallback
        import os
        url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        return _ns(
            redis=_ns(
                url=url,
                channel_ticks=os.environ.get("REDIS_CHANNEL_TICKS", "bybit:ticks"),
                channel_klines=os.environ.get("REDIS_CHANNEL_KLINES", "bybit:klines"),
            ),
            ws_enabled=(os.environ.get("BYBIT_WS_ENABLED", "0").lower() in ("1", "true", "yes")),
            ws_symbols=[s.strip().upper() for s in os.environ.get("BYBIT_WS_SYMBOLS", "BTCUSDT").split(',') if s.strip()],
            ws_intervals=[s.strip().upper() for s in os.environ.get("BYBIT_WS_INTERVALS", "1").split(',') if s.strip()],
        )

    # Prefer SETTINGS (pydantic-settings or fallback in settings.py)
    redis_url = getattr(getattr(SETTINGS, "redis", _ns(url="redis://127.0.0.1:6379/0")), "url", None) or "redis://127.0.0.1:6379/0"
    channel_ticks = getattr(SETTINGS.redis, "channel_ticks", "bybit:ticks")
    channel_klines = getattr(SETTINGS.redis, "channel_klines", "bybit:klines")
    ws_enabled = getattr(getattr(SETTINGS, "ws", _ns(enabled=False)), "enabled", False)
    ws_symbols = getattr(SETTINGS.ws, "symbols_list", ["BTCUSDT"]) or ["BTCUSDT"]
    ws_intervals = getattr(SETTINGS.ws, "intervals_list", ["1"]) or ["1"]

    return _ns(
        redis=_ns(url=redis_url, channel_ticks=channel_ticks, channel_klines=channel_klines),
        ws_enabled=ws_enabled,
        ws_symbols=ws_symbols,
        ws_intervals=ws_intervals,
    )


CONFIG = _build_config()

__all__ = ["CONFIG"]
