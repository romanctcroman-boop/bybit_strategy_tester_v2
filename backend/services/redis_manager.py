"""
Redis Manager

Централизованное управление Redis подключением и операциями кэширования.
"""

import json
from typing import Any, Optional

import redis
from loguru import logger

from backend.core.config import settings


class RedisManager:
    """
    Менеджер Redis для кэширования и pub/sub операций
    """
    
    def __init__(self):
        """Инициализация подключения к Redis"""
        self._client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self):
        """Установить подключение к Redis"""
        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Проверка подключения
            self._client.ping()
            logger.info(f"✅ Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._client = None
        except Exception as e:
            logger.error(f"❌ Redis initialization error: {e}")
            self._client = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Получить Redis client"""
        if self._client is None:
            self._connect()
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Проверить доступность Redis"""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша
        
        Args:
            key: Ключ
        
        Returns:
            Значение или None
        """
        if not self.is_available:
            return None
        
        try:
            value = self._client.get(key)
            if value is None:
                return None
            
            # Попытка десериализовать JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.warning(f"Redis GET error for key '{key}': {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Установить значение в кэш
        
        Args:
            key: Ключ
            value: Значение (будет сериализовано в JSON если не строка)
            ttl: Time to live в секундах (опционально)
        
        Returns:
            True если успешно, False иначе
        """
        if not self.is_available:
            return False
        
        try:
            # Сериализация в JSON если не строка
            if not isinstance(value, str):
                value = json.dumps(value, default=str)
            
            if ttl:
                self._client.setex(key, ttl, value)
            else:
                self._client.set(key, value)
            
            return True
        except Exception as e:
            logger.warning(f"Redis SET error for key '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Удалить ключ из кэша
        
        Args:
            key: Ключ
        
        Returns:
            True если успешно, False иначе
        """
        if not self.is_available:
            return False
        
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE error for key '{key}': {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Проверить существование ключа
        
        Args:
            key: Ключ
        
        Returns:
            True если ключ существует
        """
        if not self.is_available:
            return False
        
        try:
            return self._client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis EXISTS error for key '{key}': {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Удалить все ключи по паттерну
        
        Args:
            pattern: Паттерн (например, "candles:*")
        
        Returns:
            Количество удалённых ключей
        """
        if not self.is_available:
            return 0
        
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis CLEAR_PATTERN error for pattern '{pattern}': {e}")
            return 0
    
    def publish(self, channel: str, message: Any) -> bool:
        """
        Опубликовать сообщение в канал (Pub/Sub)
        
        Args:
            channel: Имя канала
            message: Сообщение (будет сериализовано в JSON)
        
        Returns:
            True если успешно
        """
        if not self.is_available:
            return False
        
        try:
            if not isinstance(message, str):
                message = json.dumps(message, default=str)
            
            self._client.publish(channel, message)
            return True
        except Exception as e:
            logger.warning(f"Redis PUBLISH error for channel '{channel}': {e}")
            return False
    
    def subscribe(self, *channels: str):
        """
        Подписаться на каналы (Pub/Sub)
        
        Args:
            *channels: Имена каналов
        
        Returns:
            PubSub объект или None
        """
        if not self.is_available:
            return None
        
        try:
            pubsub = self._client.pubsub()
            pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error(f"Redis SUBSCRIBE error: {e}")
            return None
    
    def flushdb(self) -> bool:
        """
        Очистить текущую БД Redis (ОСТОРОЖНО!)
        
        Returns:
            True если успешно
        """
        if not self.is_available:
            return False
        
        try:
            self._client.flushdb()
            logger.warning("⚠️  Redis DB flushed!")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False
    
    def get_stats(self) -> dict:
        """
        Получить статистику Redis
        
        Returns:
            Словарь со статистикой
        """
        if not self.is_available:
            return {"available": False}
        
        try:
            info = self._client.info()
            return {
                "available": True,
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands": info.get("total_commands_processed"),
                "keyspace": info.get("db0", {}),
            }
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {"available": False, "error": str(e)}


# Глобальный экземпляр Redis manager
redis_manager = RedisManager()


def get_redis() -> RedisManager:
    """
    Dependency injection для FastAPI
    
    Returns:
        RedisManager instance
    """
    return redis_manager
