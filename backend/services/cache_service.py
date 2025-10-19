"""
CacheService - Redis кэширование для производительности

Функционал:
- Кэширование маркет данных (OHLCV)
- Кэширование результатов бэктестов
- Кэширование результатов оптимизаций
- TTL (Time To Live) управление
- Pub/Sub для real-time обновлений
- Namespace management
"""

import json
import pickle
import redis
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timedelta
from functools import wraps

from loguru import logger

from backend.core.config import settings


class CacheService:
    """
    Сервис кэширования через Redis
    
    Примеры использования:
        # Создать сервис
        cache = CacheService()
        
        # Простое кэширование
        cache.set('my_key', {'data': 'value'}, ttl=3600)
        data = cache.get('my_key')
        
        # Кэширование с декоратором
        @cache.cached(ttl=300, key_prefix='backtest')
        def run_backtest(strategy_id, symbol):
            # Долгая операция
            return results
        
        # Pub/Sub
        cache.publish('prices', {'symbol': 'BTCUSDT', 'price': 50000})
        
        def handle_price(message):
            print(message)
        
        cache.subscribe('prices', handle_price)
    """
    
    # Default settings
    DEFAULT_TTL = 3600  # 1 hour
    
    # Namespaces
    NS_MARKET_DATA = 'market_data'
    NS_BACKTEST = 'backtest'
    NS_OPTIMIZATION = 'optimization'
    NS_STRATEGY = 'strategy'
    NS_SESSION = 'session'
    
    def __init__(self):
        """
        Инициализация с прямым Redis client (без decode_responses для pickle)
        """
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=False,  # Важно для pickle!
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Проверка подключения
            self.client.ping()
            logger.info("✅ CacheService initialized with Redis")
        except redis.ConnectionError as e:
            logger.warning(f"⚠️  Redis connection failed: {e}")
            self.client = None
        except Exception as e:
            logger.error(f"❌ CacheService initialization error: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Проверить доступность Redis"""
        if not self.client:
            return False
        try:
            return self.client.ping()
        except:
            return False
    
    def _make_key(self, namespace: str, key: str) -> str:
        """
        Создать полный ключ с namespace
        
        Args:
            namespace: Namespace (market_data, backtest, etc.)
            key: Ключ
            
        Returns:
            Полный ключ
        """
        return f"{namespace}:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Сериализовать значение"""
        return pickle.dumps(value)
    
    def _deserialize(self, value: bytes) -> Any:
        """Десериализовать значение"""
        if value is None:
            return None
        return pickle.loads(value)
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = ''
    ) -> bool:
        """
        Сохранить значение в кэш
        
        Args:
            key: Ключ
            value: Значение (любой Python объект)
            ttl: Time to live в секундах (если None, то DEFAULT_TTL)
            namespace: Namespace для группировки
            
        Returns:
            True если сохранено успешно
        """
        if not self.is_available():
            return False
        
        full_key = self._make_key(namespace, key) if namespace else key
        ttl = ttl if ttl is not None else self.DEFAULT_TTL
        
        try:
            serialized = self._serialize(value)
            # Используем прямой client для сохранения сырых bytes
            self.client.setex(full_key, ttl, serialized)
            logger.debug(f"Cached: {full_key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def get(
        self,
        key: str,
        namespace: str = '',
        default: Any = None
    ) -> Any:
        """
        Получить значение из кэша
        
        Args:
            key: Ключ
            namespace: Namespace
            default: Значение по умолчанию если не найдено
            
        Returns:
            Значение или default
        """
        if not self.is_available():
            return default
        
        full_key = self._make_key(namespace, key) if namespace else key
        
        try:
            value = self.client.get(full_key)
            if value is None:
                return default
            
            logger.debug(f"Cache hit: {full_key}")
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return default
    
    def delete(self, key: str, namespace: str = '') -> bool:
        """
        Удалить значение из кэша
        
        Args:
            key: Ключ
            namespace: Namespace
            
        Returns:
            True если удалено
        """
        if not self.is_available():
            return False
        
        full_key = self._make_key(namespace, key) if namespace else key
        
        try:
            result = self.client.delete(full_key)
            logger.debug(f"Deleted: {full_key}")
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def exists(self, key: str, namespace: str = '') -> bool:
        """Проверить существование ключа"""
        if not self.is_available():
            return False
        
        full_key = self._make_key(namespace, key) if namespace else key
        
        try:
            return self.client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False
    
    def expire(self, key: str, ttl: int, namespace: str = '') -> bool:
        """Установить TTL для существующего ключа"""
        if not self.client:
            return False
        
        full_key = self._make_key(namespace, key) if namespace else key
        
        try:
            return self.client.expire(full_key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error: {e}")
            return False
    
    def ttl(self, key: str, namespace: str = '') -> int:
        """
        Получить оставшееся время жизни ключа
        
        Returns:
            Секунды до истечения (-1 если бессрочный, -2 если не существует)
        """
        if not self.client:
            return -2
        
        full_key = self._make_key(namespace, key) if namespace else key
        
        try:
            return self.client.ttl(full_key)
        except Exception as e:
            logger.error(f"Cache TTL error: {e}")
            return -2
    
    def flush_namespace(self, namespace: str) -> int:
        """
        Удалить все ключи в namespace
        
        Args:
            namespace: Namespace для очистки
            
        Returns:
            Количество удалённых ключей
        """
        if not self.client:
            return 0
        
        pattern = f"{namespace}:*"
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                count = self.client.delete(*keys)
                logger.info(f"Flushed {count} keys from namespace '{namespace}'")
                return count
            return 0
        except Exception as e:
            logger.error(f"Flush namespace error: {e}")
            return 0
    
    def flush_all(self) -> bool:
        """Очистить всю базу данных Redis"""
        if not self.client:
            return False
        
        try:
            self.client.flushdb()
            logger.info("Flushed entire Redis database")
            return True
        except Exception as e:
            logger.error(f"Flush all error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Получить информацию о Redis сервере"""
        if not self.client:
            return {'available': False}
        
        try:
            info = self.client.info()
            return {
                'available': True,
                'redis_version': info.get('redis_version'),
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime_days': info.get('uptime_in_days'),
                'total_keys': self.client.dbsize()
            }
        except Exception as e:
            logger.error(f"Get info error: {e}")
            return {'available': False, 'error': str(e)}
    
    # ========================================================================
    # DECORATOR
    # ========================================================================
    
    def cached(
        self,
        ttl: int = DEFAULT_TTL,
        key_prefix: str = '',
        namespace: str = ''
    ):
        """
        Декоратор для кэширования результатов функций
        
        Args:
            ttl: Time to live
            key_prefix: Префикс ключа
            namespace: Namespace
            
        Example:
            @cache.cached(ttl=300, key_prefix='backtest')
            def run_backtest(strategy_id, symbol):
                # Долгая операция
                return results
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Создать ключ из аргументов
                key_parts = [key_prefix, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ':'.join(filter(None, key_parts))
                
                # Попытка получить из кэша
                cached_value = self.get(cache_key, namespace)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_value
                
                # Вызвать функцию
                logger.debug(f"Cache miss for {func.__name__}")
                result = func(*args, **kwargs)
                
                # Сохранить в кэш
                self.set(cache_key, result, ttl, namespace)
                
                return result
            
            return wrapper
        return decorator
    
    # ========================================================================
    # HIGH-LEVEL METHODS
    # ========================================================================
    
    def cache_market_data(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Dict],
        ttl: int = 300
    ) -> bool:
        """
        Кэшировать маркет данные
        
        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            candles: Список свечей
            ttl: Time to live (default 5 минут)
            
        Returns:
            True если закэшировано
        """
        key = f"{symbol}:{timeframe}"
        return self.set(key, candles, ttl, self.NS_MARKET_DATA)
    
    def get_market_data(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[List[Dict]]:
        """Получить закэшированные маркет данные"""
        key = f"{symbol}:{timeframe}"
        return self.get(key, self.NS_MARKET_DATA)
    
    def cache_backtest_result(
        self,
        backtest_id: int,
        result: Dict,
        ttl: int = 3600
    ) -> bool:
        """
        Кэшировать результат бэктеста
        
        Args:
            backtest_id: ID бэктеста
            result: Результаты
            ttl: Time to live (default 1 час)
            
        Returns:
            True если закэшировано
        """
        key = f"result:{backtest_id}"
        return self.set(key, result, ttl, self.NS_BACKTEST)
    
    def get_backtest_result(self, backtest_id: int) -> Optional[Dict]:
        """Получить закэшированный результат бэктеста"""
        key = f"result:{backtest_id}"
        return self.get(key, self.NS_BACKTEST)
    
    def cache_optimization_results(
        self,
        optimization_id: int,
        results: List[Dict],
        ttl: int = 7200
    ) -> bool:
        """
        Кэшировать результаты оптимизации
        
        Args:
            optimization_id: ID оптимизации
            results: Результаты всех комбинаций
            ttl: Time to live (default 2 часа)
            
        Returns:
            True если закэшировано
        """
        key = f"results:{optimization_id}"
        return self.set(key, results, ttl, self.NS_OPTIMIZATION)
    
    def get_optimization_results(
        self,
        optimization_id: int
    ) -> Optional[List[Dict]]:
        """Получить закэшированные результаты оптимизации"""
        key = f"results:{optimization_id}"
        return self.get(key, self.NS_OPTIMIZATION)
    
    # ========================================================================
    # PUB/SUB
    # ========================================================================
    
    def publish(self, channel: str, message: Any) -> int:
        """
        Опубликовать сообщение в канал
        
        Args:
            channel: Название канала
            message: Сообщение (будет сериализовано в JSON)
            
        Returns:
            Количество подписчиков, получивших сообщение
        """
        if not self.client:
            return 0
        
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            
            count = self.client.publish(channel, message)
            logger.debug(f"Published to '{channel}': {count} subscribers")
            return count
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return 0
    
    def subscribe(self, channel: str, callback: callable):
        """
        Подписаться на канал (blocking)
        
        Args:
            channel: Название канала
            callback: Функция обработки сообщений
            
        Note:
            Это blocking операция, запускайте в отдельном потоке
        """
        if not self.client:
            return
        
        try:
            pubsub = self.client.pubsub()
            pubsub.subscribe(channel)
            
            logger.info(f"Subscribed to channel: {channel}")
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        callback(data)
                    except json.JSONDecodeError:
                        callback(message['data'])
                    
        except Exception as e:
            logger.error(f"Subscribe error: {e}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Глобальный экземпляр (опционально)
_cache_instance: Optional[CacheService] = None

def get_cache() -> CacheService:
    """Получить глобальный экземпляр кэша"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Создать сервис
    cache = CacheService()
    
    # Проверить доступность
    print(f"Redis available: {cache.is_available()}")
    
    if cache.is_available():
        # Простое кэширование
        print("\n=== Simple Caching ===")
        cache.set('test_key', {'data': 'value', 'number': 123}, ttl=60)
        value = cache.get('test_key')
        print(f"Cached value: {value}")
        
        # Кэширование с namespace
        print("\n=== Namespace Caching ===")
        cache.cache_market_data('BTCUSDT', '15', [
            {'time': 1000, 'open': 50000, 'close': 50100}
        ])
        candles = cache.get_market_data('BTCUSDT', '15')
        print(f"Cached candles: {candles}")
        
        # Декоратор
        print("\n=== Decorator Caching ===")
        
        @cache.cached(ttl=30, key_prefix='calc')
        def expensive_calculation(x, y):
            print(f"  Computing {x} + {y}...")
            import time
            time.sleep(1)  # Simulate expensive operation
            return x + y
        
        # First call (cache miss)
        result1 = expensive_calculation(5, 3)
        print(f"Result 1: {result1}")
        
        # Second call (cache hit)
        result2 = expensive_calculation(5, 3)
        print(f"Result 2: {result2} (from cache)")
        
        # Info
        print("\n=== Redis Info ===")
        info = cache.get_info()
        print(f"Version: {info.get('redis_version')}")
        print(f"Memory: {info.get('used_memory')}")
        print(f"Total keys: {info.get('total_keys')}")
        
        print("\n✅ All cache operations completed")
    
    else:
        print("⚠️  Redis not available - cache disabled")
