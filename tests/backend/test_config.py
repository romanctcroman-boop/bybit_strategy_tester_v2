"""
Tests for config.py

Coverage target: 0% → 80%+
"""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.config import CONFIG, _build_config, _ns


class TestNamespaceHelper:
    """Test _ns() helper function."""

    def test_ns_creates_namespace(self):
        """Test that _ns creates SimpleNamespace."""
        ns = _ns(key1="value1", key2=42)
        
        assert isinstance(ns, SimpleNamespace)
        assert ns.key1 == "value1"
        assert ns.key2 == 42

    def test_ns_empty(self):
        """Test _ns with no arguments."""
        ns = _ns()
        
        assert isinstance(ns, SimpleNamespace)
        assert not hasattr(ns, "__dict__") or len(ns.__dict__) == 0


class TestBuildConfigFallback:
    """Test _build_config() with SETTINGS=None (environment fallback)."""

    @patch('backend.config.SETTINGS', None)
    def test_build_config_fallback_defaults(self):
        """Test fallback config with default environment values."""
        with patch.dict(os.environ, {}, clear=True):
            config = _build_config()
            
            assert config.redis.url == "redis://127.0.0.1:6379/0"
            assert config.redis.channel_ticks == "bybit:ticks"
            assert config.redis.channel_klines == "bybit:klines"
            assert config.ws_enabled is False
            assert config.ws_symbols == ["BTCUSDT"]
            assert config.ws_intervals == ["1"]

    @patch('backend.config.SETTINGS', None)
    def test_build_config_fallback_custom_env(self):
        """Test fallback config with custom environment variables."""
        env = {
            'REDIS_URL': 'redis://custom:6380/1',
            'REDIS_CHANNEL_TICKS': 'custom:ticks',
            'REDIS_CHANNEL_KLINES': 'custom:klines',
            'BYBIT_WS_ENABLED': 'true',
            'BYBIT_WS_SYMBOLS': 'BTCUSDT,ETHUSDT,SOLUSDT',
            'BYBIT_WS_INTERVALS': '1,5,15',
        }
        
        with patch.dict(os.environ, env, clear=True):
            config = _build_config()
            
            assert config.redis.url == 'redis://custom:6380/1'
            assert config.redis.channel_ticks == 'custom:ticks'
            assert config.redis.channel_klines == 'custom:klines'
            assert config.ws_enabled is True
            assert config.ws_symbols == ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            assert config.ws_intervals == ['1', '5', '15']

    @patch('backend.config.SETTINGS', None)
    @pytest.mark.parametrize('ws_value,expected', [
        ('1', True),
        ('true', True),
        ('TRUE', True),
        ('yes', True),
        ('YES', True),
        ('0', False),
        ('false', False),
        ('no', False),
        ('', False),
    ])
    def test_build_config_ws_enabled_parsing(self, ws_value, expected):
        """Test ws_enabled boolean parsing from environment."""
        with patch.dict(os.environ, {'BYBIT_WS_ENABLED': ws_value}, clear=True):
            config = _build_config()
            assert config.ws_enabled is expected

    @patch('backend.config.SETTINGS', None)
    def test_build_config_symbols_with_whitespace(self):
        """Test symbol list parsing handles whitespace."""
        with patch.dict(os.environ, {'BYBIT_WS_SYMBOLS': ' BTCUSDT , ETHUSDT , SOLUSDT '}, clear=True):
            config = _build_config()
            
            assert config.ws_symbols == ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    @patch('backend.config.SETTINGS', None)
    def test_build_config_intervals_lowercase_to_uppercase(self):
        """Test intervals are converted to uppercase."""
        with patch.dict(os.environ, {'BYBIT_WS_INTERVALS': '1,5m,15m'}, clear=True):
            config = _build_config()
            
            assert config.ws_intervals == ['1', '5M', '15M']


class TestBuildConfigWithSettings:
    """Test _build_config() with mocked SETTINGS object."""

    def test_build_config_with_settings(self):
        """Test config built from SETTINGS object."""
        mock_settings = SimpleNamespace(
            redis=SimpleNamespace(
                url='redis://settings:6379/0',
                channel_ticks='settings:ticks',
                channel_klines='settings:klines',
            ),
            ws=SimpleNamespace(
                enabled=True,
                symbols_list=['BTC', 'ETH'],
                intervals_list=['5', '15'],
            ),
        )
        
        with patch('backend.config.SETTINGS', mock_settings):
            config = _build_config()
            
            assert config.redis.url == 'redis://settings:6379/0'
            assert config.redis.channel_ticks == 'settings:ticks'
            assert config.redis.channel_klines == 'settings:klines'
            assert config.ws_enabled is True
            assert config.ws_symbols == ['BTC', 'ETH']
            assert config.ws_intervals == ['5', '15']

    def test_build_config_missing_attributes_use_defaults(self):
        """Test config uses defaults when SETTINGS attributes missing."""
        mock_settings = SimpleNamespace(
            redis=SimpleNamespace(),
            ws=SimpleNamespace(),
        )
        
        with patch('backend.config.SETTINGS', mock_settings):
            config = _build_config()
            
            # Should use defaults when attributes missing
            assert config.redis.url == 'redis://127.0.0.1:6379/0'
            assert config.redis.channel_ticks == 'bybit:ticks'
            assert config.redis.channel_klines == 'bybit:klines'
            assert config.ws_enabled is False
            assert config.ws_symbols == ['BTCUSDT']
            assert config.ws_intervals == ['1']

    def test_build_config_none_values_use_defaults(self):
        """Test config handles None values in SETTINGS."""
        mock_settings = SimpleNamespace(
            redis=SimpleNamespace(
                url=None,
                channel_ticks='ticks',
                channel_klines='klines',
            ),
            ws=SimpleNamespace(
                enabled=True,
                symbols_list=None,
                intervals_list=None,
            ),
        )
        
        with patch('backend.config.SETTINGS', mock_settings):
            config = _build_config()
            
            assert config.redis.url == 'redis://127.0.0.1:6379/0'  # None → default
            assert config.ws_symbols == ['BTCUSDT']  # None → default
            assert config.ws_intervals == ['1']  # None → default


class TestConfigGlobal:
    """Test global CONFIG object."""

    def test_config_exists(self):
        """Test CONFIG is created and accessible."""
        assert CONFIG is not None
        assert hasattr(CONFIG, 'redis')
        assert hasattr(CONFIG, 'ws_enabled')
        assert hasattr(CONFIG, 'ws_symbols')
        assert hasattr(CONFIG, 'ws_intervals')

    def test_config_redis_structure(self):
        """Test CONFIG.redis has expected structure."""
        assert hasattr(CONFIG.redis, 'url')
        assert hasattr(CONFIG.redis, 'channel_ticks')
        assert hasattr(CONFIG.redis, 'channel_klines')
        
        assert isinstance(CONFIG.redis.url, str)
        assert isinstance(CONFIG.redis.channel_ticks, str)
        assert isinstance(CONFIG.redis.channel_klines, str)

    def test_config_ws_structure(self):
        """Test CONFIG websocket settings structure."""
        assert isinstance(CONFIG.ws_enabled, bool)
        assert isinstance(CONFIG.ws_symbols, list)
        assert isinstance(CONFIG.ws_intervals, list)
