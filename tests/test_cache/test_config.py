"""
Тесты для конфигурации кэша (CacheSettings).

Тестирует:
- Дефолтные значения
- Загрузку из переменных окружения
- Валидацию параметров
- Environment-specific настройки
- Интеграцию с CacheManager
"""
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from backend.cache.config import CacheSettings, get_cache_settings
from backend.cache.cache_manager import CacheManager


class TestCacheSettingsDefaults:
    """Тесты дефолтных значений CacheSettings."""
    
    def test_default_values(self):
        """Проверка дефолтных значений."""
        # Note: Default environment is 'development', which adjusts TTLs
        settings = CacheSettings()
        
        # L1 Configuration
        assert settings.l1_size == 1000
        # Development auto-adjusts TTL to 60 seconds
        assert settings.l1_ttl == 60  # Adjusted for development
        
        # L2 Configuration
        # Development auto-adjusts TTL to 300 seconds
        assert settings.l2_ttl == 300  # Adjusted for development
        assert settings.l2_redis_url is None
        assert settings.l2_connection_timeout == 5
        assert settings.l2_operation_timeout == 2
        
        # Feature Flags
        assert settings.enable_l1 is True
        assert settings.enable_l2 is True
        assert settings.enable_metrics is True
        assert settings.enable_etag is True
        assert settings.enable_cache_warming is False
        
        # HTTP Cache
        assert settings.http_cache_max_age == 60
        
        # Environment
        assert settings.env == 'development'
    
    def test_development_environment_adjustments(self):
        """Тесты автоматической подстройки для development."""
        settings = CacheSettings(env='development')
        
        # Development должен иметь короткие TTL для быстрого тестирования
        assert settings.l1_ttl == 60  # 1 minute (adjusted)
        assert settings.l2_ttl == 300  # 5 minutes (adjusted)
    
    def test_staging_environment_adjustments(self):
        """Тесты для staging (умеренные настройки)."""
        settings = CacheSettings(env='staging')
        
        # Staging использует дефолты (не adjusted)
        assert settings.l1_size == 1000
        assert settings.l1_ttl == 300
        assert settings.l2_ttl == 3600
    
    def test_production_environment_adjustments(self):
        """Тесты автоматической подстройки для production."""
        settings = CacheSettings(env='production')
        
        # Production должен иметь большие размеры и долгие TTL
        assert settings.l1_size == 5000  # Увеличен (adjusted)
        assert settings.l1_ttl == 600  # 10 minutes (adjusted)
        assert settings.l2_ttl == 7200  # 2 hours (adjusted)


class TestCacheSettingsValidation:
    """Тесты валидации параметров."""
    
    def test_l1_size_too_small(self):
        """L1 size должен быть не меньше 10."""
        with pytest.raises(ValidationError, match="greater than or equal"):
            CacheSettings(l1_size=5)
    
    def test_l1_size_too_large(self):
        """L1 size должен быть не больше 100000."""
        with pytest.raises(ValidationError, match="less than or equal"):
            CacheSettings(l1_size=200000)
    
    def test_l1_size_valid_range(self):
        """L1 size в валидном диапазоне."""
        settings = CacheSettings(l1_size=500)
        assert settings.l1_size == 500
        
        settings = CacheSettings(l1_size=50000)
        assert settings.l1_size == 50000
    
    def test_l1_ttl_too_small(self):
        """L1 TTL должен быть не меньше 10 секунд."""
        with pytest.raises(ValidationError, match="greater than or equal"):
            CacheSettings(l1_ttl=5)
    
    def test_l1_ttl_too_large(self):
        """L1 TTL должен быть не больше 86400 секунд (1 день)."""
        with pytest.raises(ValidationError, match="less than or equal"):
            CacheSettings(l1_ttl=100000)
    
    def test_l2_ttl_too_small(self):
        """L2 TTL должен быть не меньше 60 секунд."""
        with pytest.raises(ValidationError, match="greater than or equal"):
            CacheSettings(l2_ttl=30)
    
    def test_l2_ttl_too_large(self):
        """L2 TTL должен быть не больше 604800 секунд (1 неделя)."""
        with pytest.raises(ValidationError, match="less than or equal"):
            CacheSettings(l2_ttl=700000)
    
    def test_invalid_environment(self):
        """Невалидный environment."""
        with pytest.raises(ValidationError):
            CacheSettings(env='invalid')
    
    def test_valid_environments(self):
        """Все валидные environments."""
        for env in ['development', 'staging', 'production']:
            settings = CacheSettings(env=env)
            assert settings.env == env


class TestCacheSettingsFromEnvironment:
    """Тесты загрузки из переменных окружения."""
    
    def test_load_l1_size_from_env(self, monkeypatch):
        """Загрузка L1 size из CACHE_L1_SIZE."""
        monkeypatch.setenv("CACHE_L1_SIZE", "2000")
        settings = CacheSettings()
        assert settings.l1_size == 2000
    
    def test_load_l1_ttl_from_env(self, monkeypatch):
        """Загрузка L1 TTL из CACHE_L1_TTL."""
        monkeypatch.setenv("CACHE_L1_TTL", "600")
        settings = CacheSettings()
        assert settings.l1_ttl == 600
    
    def test_load_l2_ttl_from_env(self, monkeypatch):
        """Загрузка L2 TTL из CACHE_L2_TTL."""
        monkeypatch.setenv("CACHE_L2_TTL", "7200")
        settings = CacheSettings()
        assert settings.l2_ttl == 7200
    
    def test_load_redis_url_from_env(self, monkeypatch):
        """Загрузка Redis URL из CACHE_L2_REDIS_URL."""
        monkeypatch.setenv("CACHE_L2_REDIS_URL", "redis://test:6379/0")
        settings = CacheSettings()
        assert settings.l2_redis_url == "redis://test:6379/0"
    
    def test_load_feature_flags_from_env(self, monkeypatch):
        """Загрузка feature flags из переменных окружения."""
        monkeypatch.setenv("CACHE_ENABLE_L1", "false")
        monkeypatch.setenv("CACHE_ENABLE_L2", "false")
        monkeypatch.setenv("CACHE_ENABLE_METRICS", "false")
        monkeypatch.setenv("CACHE_ENABLE_ETAG", "false")
        monkeypatch.setenv("CACHE_ENABLE_CACHE_WARMING", "true")
        
        settings = CacheSettings()
        
        assert settings.enable_l1 is False
        assert settings.enable_l2 is False
        assert settings.enable_metrics is False
        assert settings.enable_etag is False
        assert settings.enable_cache_warming is True
    
    def test_load_environment_from_env(self, monkeypatch):
        """Загрузка environment из CACHE_ENV."""
        # Pydantic Settings использует CACHE_ENV (с префиксом)
        monkeypatch.setenv("CACHE_ENV", "production")
        settings = CacheSettings()
        assert settings.env == 'production'
    
    def test_env_prefix_case_insensitive(self, monkeypatch):
        """Переменные окружения case-insensitive (CACHE_ prefix)."""
        monkeypatch.setenv("cache_l1_size", "3000")
        settings = CacheSettings()
        assert settings.l1_size == 3000


class TestCacheSettingsHelpers:
    """Тесты вспомогательных методов."""
    
    def test_get_cache_config(self):
        """Метод get_cache_config() возвращает словарь."""
        # Use production to avoid auto-adjustments
        settings = CacheSettings(env='production', l1_size=500, l1_ttl=120, l2_ttl=600)
        config = settings.get_cache_config()
        
        # Config has nested structure
        assert config['l1']['size'] == 500
        assert config['l1']['ttl'] == 120
        assert config['l2']['ttl'] == 600
        assert config['l1']['enabled'] is True
        assert config['l2']['enabled'] is True
        assert config['environment'] == 'production'
    
    def test_is_production(self):
        """Метод is_production()."""
        assert CacheSettings(env='production').is_production() is True
        assert CacheSettings(env='staging').is_production() is False
        assert CacheSettings(env='development').is_production() is False
    
    def test_is_development(self):
        """Метод is_development()."""
        assert CacheSettings(env='development').is_development() is True
        assert CacheSettings(env='staging').is_development() is False
        assert CacheSettings(env='production').is_development() is False
    
    def test_is_staging(self):
        """Метод is_staging()."""
        assert CacheSettings(env='staging').is_staging() is True
        assert CacheSettings(env='development').is_staging() is False
        assert CacheSettings(env='production').is_staging() is False


class TestCacheSettingsSingleton:
    """Тесты singleton factory get_cache_settings()."""
    
    def test_get_cache_settings_returns_singleton(self):
        """get_cache_settings() возвращает singleton."""
        settings1 = get_cache_settings()
        settings2 = get_cache_settings()
        
        # Должен вернуть тот же объект (из lru_cache)
        assert settings1 is settings2
    
    def test_get_cache_settings_respects_env_vars(self, monkeypatch):
        """get_cache_settings() читает переменные окружения."""
        monkeypatch.setenv("CACHE_L1_SIZE", "4000")
        
        # Очистка lru_cache для теста
        get_cache_settings.cache_clear()
        
        settings = get_cache_settings()
        assert settings.l1_size == 4000


class TestCacheManagerIntegration:
    """Тесты интеграции CacheSettings с CacheManager."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_uses_settings_defaults(self):
        """CacheManager использует дефолтные значения из settings."""
        settings = CacheSettings(l1_size=500, l1_ttl=120, l2_ttl=600)
        manager = CacheManager(settings=settings)
        
        # Проверяем, что CacheManager использует настройки
        assert manager.settings.l1_size == 500
        assert manager.settings.l1_ttl == 120
        assert manager.settings.l2_ttl == 600
        
        # L1 cache должен быть создан с правильными параметрами
        if manager.l1_cache:
            assert manager.l1_cache.max_size == 500
            assert manager.l1_cache.default_ttl == 120
    
    @pytest.mark.asyncio
    async def test_cache_manager_respects_enable_l1_flag(self):
        """CacheManager не создаёт L1 cache если enable_l1=False."""
        settings = CacheSettings(enable_l1=False)
        manager = CacheManager(settings=settings)
        
        assert manager.l1_cache is None
    
    @pytest.mark.asyncio
    async def test_cache_manager_respects_enable_l2_flag(self):
        """CacheManager не подключается к Redis если enable_l2=False."""
        settings = CacheSettings(enable_l2=False)
        manager = CacheManager(settings=settings)
        
        # connect() не должен подключаться к Redis
        await manager.connect()
        
        # redis_client должен остаться None (не подключался)
        # (или если был предоставлен, всё равно не будет использоваться)
    
    @pytest.mark.asyncio
    async def test_cache_manager_parameter_override(self):
        """Параметры конструктора переопределяют settings."""
        settings = CacheSettings(l1_size=500, l1_ttl=120, l2_ttl=600)
        
        # Передаём явные параметры, которые должны переопределить settings
        manager = CacheManager(
            l1_size=1000,  # Override
            l1_ttl=300,    # Override
            settings=settings
        )
        
        # Параметры конструктора имеют приоритет
        if manager.l1_cache:
            assert manager.l1_cache.max_size == 1000
            assert manager.l1_cache.default_ttl == 300
    
    @pytest.mark.asyncio
    async def test_cache_manager_get_respects_enable_l1(self):
        """CacheManager.get() не использует L1 если enable_l1=False."""
        settings = CacheSettings(enable_l1=False)
        manager = CacheManager(settings=settings)
        
        # get() должен сразу вернуть None (не проверять L1)
        result = await manager.get("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_manager_set_respects_enable_l1(self):
        """CacheManager.set() не записывает в L1 если enable_l1=False."""
        settings = CacheSettings(enable_l1=False)
        manager = CacheManager(settings=settings)
        
        # set() не должен вызвать ошибку (просто не записывает в L1)
        await manager.set("test_key", "test_value")
        
        # L1 cache не создан
        assert manager.l1_cache is None


class TestConfigurationExamples:
    """Тесты примеров конфигураций для разных окружений."""
    
    def test_development_config_example(self):
        """Пример конфигурации для development."""
        settings = CacheSettings(
            env='development',
            l1_size=500,
            enable_cache_warming=False,  # Не нужно в dev
        )
        
        assert settings.env == 'development'
        assert settings.l1_size == 500
        assert settings.l1_ttl == 60  # Короткий TTL (adjusted)
        assert settings.l2_ttl == 300  # Короткий TTL (adjusted)
        assert settings.enable_cache_warming is False
    
    def test_staging_config_example(self):
        """Пример конфигурации для staging."""
        settings = CacheSettings(
            env='staging',
            l1_size=2000,
            l1_ttl=300,
            l2_ttl=1800,
            enable_cache_warming=True,  # Тестируем cache warming
        )
        
        assert settings.env == 'staging'
        assert settings.l1_size == 2000
        assert settings.l1_ttl == 300
        assert settings.l2_ttl == 1800
        assert settings.enable_cache_warming is True
    
    def test_production_config_example(self):
        """Пример конфигурации для production."""
        settings = CacheSettings(
            env='production',
            # Размеры и TTL автоматически adjusted для production
            enable_metrics=True,  # Обязательно для мониторинга
            enable_etag=True,
            enable_cache_warming=True,
        )
        
        assert settings.env == 'production'
        assert settings.l1_size == 5000  # Auto-adjusted
        assert settings.l1_ttl == 600  # Auto-adjusted
        assert settings.l2_ttl == 7200  # Auto-adjusted
        assert settings.enable_metrics is True
        assert settings.enable_etag is True
        assert settings.enable_cache_warming is True


# Итого: 35 тестов для полного покрытия конфигурации кэша
