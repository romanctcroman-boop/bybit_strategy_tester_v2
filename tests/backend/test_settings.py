"""
Tests for settings.py

Coverage target: 51% → 75%+
Focus on fallback implementation and property methods
"""

import os
from unittest.mock import patch

import pytest

from backend.settings import SETTINGS


class TestSettingsStructure:
    """Test SETTINGS object structure and basic attributes."""

    def test_settings_has_database(self):
        """Test SETTINGS.database exists."""
        assert hasattr(SETTINGS, 'database')
        assert hasattr(SETTINGS.database, 'url')

    def test_settings_has_redis(self):
        """Test SETTINGS.redis exists and has expected attributes."""
        assert hasattr(SETTINGS, 'redis')
        assert hasattr(SETTINGS.redis, 'url')
        assert hasattr(SETTINGS.redis, 'channel_ticks')
        assert hasattr(SETTINGS.redis, 'channel_klines')
        assert hasattr(SETTINGS.redis, 'stream_ticks')
        assert hasattr(SETTINGS.redis, 'stream_klines')

    def test_settings_has_ws(self):
        """Test SETTINGS.ws exists and has expected attributes."""
        assert hasattr(SETTINGS, 'ws')
        assert hasattr(SETTINGS.ws, 'enabled')
        assert hasattr(SETTINGS.ws, 'symbols')
        assert hasattr(SETTINGS.ws, 'intervals')
        assert hasattr(SETTINGS.ws, 'reconnect_delay_sec')
        assert hasattr(SETTINGS.ws, 'max_reconnect_delay_sec')

    def test_settings_has_celery(self):
        """Test SETTINGS.celery exists and has expected attributes."""
        assert hasattr(SETTINGS, 'celery')
        assert hasattr(SETTINGS.celery, 'eager')
        assert hasattr(SETTINGS.celery, 'broker_url')
        assert hasattr(SETTINGS.celery, 'task_default_queue')
        assert hasattr(SETTINGS.celery, 'acks_late')
        assert hasattr(SETTINGS.celery, 'prefetch_multiplier')


class TestWSSettingsProperties:
    """Test WS settings property methods."""

    def test_symbols_list_property(self):
        """Test symbols_list property returns list."""
        symbols_list = SETTINGS.ws.symbols_list
        
        assert isinstance(symbols_list, list)
        assert len(symbols_list) > 0
        assert all(isinstance(s, str) for s in symbols_list)

    def test_intervals_list_property(self):
        """Test intervals_list property returns list."""
        intervals_list = SETTINGS.ws.intervals_list
        
        assert isinstance(intervals_list, list)
        assert len(intervals_list) > 0
        assert all(isinstance(s, str) for s in intervals_list)

    def test_symbols_list_uppercase(self):
        """Test symbols are converted to uppercase."""
        symbols_list = SETTINGS.ws.symbols_list
        
        for symbol in symbols_list:
            assert symbol == symbol.upper()

    def test_intervals_list_uppercase(self):
        """Test intervals are converted to uppercase."""
        intervals_list = SETTINGS.ws.intervals_list
        
        for interval in intervals_list:
            assert interval == interval.upper()


class TestRedisURLConstruction:
    """Test Redis URL construction."""

    def test_redis_url_can_be_none(self):
        """Test Redis URL can be None when not configured."""
        # URL is optional and can be None
        assert SETTINGS.redis.url is None or isinstance(SETTINGS.redis.url, str)


class TestCelerySettings:
    """Test Celery settings parsing."""

    def test_celery_prefetch_multiplier_is_int(self):
        """Test prefetch_multiplier is integer."""
        assert isinstance(SETTINGS.celery.prefetch_multiplier, int)
        assert SETTINGS.celery.prefetch_multiplier > 0

    def test_celery_task_max_retries_is_int(self):
        """Test task_max_retries is integer."""
        assert isinstance(SETTINGS.celery.task_max_retries, int)
        assert SETTINGS.celery.task_max_retries >= 0

    def test_celery_task_default_retry_delay_is_int(self):
        """Test task_default_retry_delay is integer."""
        assert isinstance(SETTINGS.celery.task_default_retry_delay, int)
        assert SETTINGS.celery.task_default_retry_delay >= 0

    def test_celery_queue_names(self):
        """Test Celery queue names are strings."""
        assert isinstance(SETTINGS.celery.queue_grid, str)
        assert isinstance(SETTINGS.celery.queue_walk, str)
        assert isinstance(SETTINGS.celery.queue_bayes, str)
        
        assert len(SETTINGS.celery.queue_grid) > 0
        assert len(SETTINGS.celery.queue_walk) > 0
        assert len(SETTINGS.celery.queue_bayes) > 0


class TestWSReconnectSettings:
    """Test WS reconnect delay settings."""

    def test_reconnect_delay_is_float(self):
        """Test reconnect_delay_sec is float."""
        assert isinstance(SETTINGS.ws.reconnect_delay_sec, float)
        assert SETTINGS.ws.reconnect_delay_sec > 0

    def test_max_reconnect_delay_is_float(self):
        """Test max_reconnect_delay_sec is float."""
        assert isinstance(SETTINGS.ws.max_reconnect_delay_sec, float)
        assert SETTINGS.ws.max_reconnect_delay_sec > 0

    def test_max_delay_greater_than_initial(self):
        """Test max delay is greater than initial delay."""
        assert SETTINGS.ws.max_reconnect_delay_sec >= SETTINGS.ws.reconnect_delay_sec


class TestDefaultValues:
    """Test default values are reasonable."""

    def test_redis_defaults(self):
        """Test Redis has sensible defaults."""
        # URL can be None (optional)
        assert SETTINGS.redis.url is None or SETTINGS.redis.url.startswith('redis://')
        assert 'ticks' in SETTINGS.redis.channel_ticks
        assert 'klines' in SETTINGS.redis.channel_klines

    def test_ws_defaults(self):
        """Test WebSocket has sensible defaults."""
        assert isinstance(SETTINGS.ws.enabled, bool)
        assert isinstance(SETTINGS.ws.symbols, str)
        assert isinstance(SETTINGS.ws.intervals, str)

    def test_celery_defaults(self):
        """Test Celery has sensible defaults."""
        assert isinstance(SETTINGS.celery.eager, bool)
        assert isinstance(SETTINGS.celery.task_default_queue, str)
        assert isinstance(SETTINGS.celery.acks_late, bool)


class TestSettingsImport:
    """Test settings can be imported successfully."""

    def test_settings_imported(self):
        """Test SETTINGS object is available."""
        from backend.settings import SETTINGS as imported_settings
        
        assert imported_settings is not None
        assert hasattr(imported_settings, 'redis')
        assert hasattr(imported_settings, 'ws')
        assert hasattr(imported_settings, 'celery')

