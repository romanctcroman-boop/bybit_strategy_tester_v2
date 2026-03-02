"""
AI Response Caching System

Кэширует ответы от AI моделей для ускорения повторных запросов
и снижения затрат на API.

Features:
- Redis backend для distributed кэширования
- Настраиваемый TTL (по умолчанию 1 час)
- Cache key основан на prompt + model + temperature + max_tokens
- Автоматическая сериализация/десериализация
- Graceful fallback если Redis недоступен
"""

import hashlib
import json
import time
from typing import Any

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class AICacheManager:
    """
    Менеджер кэширования ответов AI

    Использует Redis для хранения закэшированных ответов.
    Если Redis недоступен - работает без кэша (pass-through mode).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600,  # 1 hour
        enabled: bool = True,
    ):
        """
        Args:
            redis_url: URL Redis сервера
            default_ttl: Время жизни кэша в секундах
            enabled: Включить/выключить кэширование
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.enabled = enabled
        self.redis_client = None

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "bypassed": 0,
        }

        if self.enabled:
            self._init_redis()
        else:
            logger.info("🚫 AI Cache disabled via config")

    def _init_redis(self):
        """Инициализировать Redis клиент"""
        try:
            import redis

            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis cache connected: {self.redis_url}")
        except ImportError:
            logger.warning("⚠️ redis package not installed. Install: pip install redis")
            self.enabled = False
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Cache disabled.")
            self.enabled = False
            self.redis_client = None

    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> str:
        """
        Генерировать уникальный ключ кэша

        Args:
            prompt: User prompt
            model: Model name
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional parameters

        Returns:
            SHA256 hash string
        """
        # Include all relevant parameters in cache key
        key_data = {
            "prompt": prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Create deterministic JSON string
        key_string = json.dumps(key_data, sort_keys=True)

        # Generate hash
        hash_obj = hashlib.sha256(key_string.encode())
        cache_key = f"ai_cache:{hash_obj.hexdigest()}"

        return cache_key

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Получить закэшированный ответ

        Returns:
            Cached response dict or None if not found
        """
        if not self.enabled or not self.redis_client:
            self.stats["bypassed"] += 1
            return None

        try:
            cache_key = self._generate_cache_key(prompt, model, temperature, max_tokens, **kwargs)

            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                self.stats["hits"] += 1
                response = json.loads(cached_data)

                # Add cache metadata
                response["from_cache"] = True
                response["cached_at"] = response.get("cached_at")

                logger.info(f"✅ Cache HIT for key: {cache_key[:16]}...")
                return response
            else:
                self.stats["misses"] += 1
                logger.debug(f"❌ Cache MISS for key: {cache_key[:16]}...")
                return None

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ Cache get error: {e}")
            return None

    def set(
        self,
        prompt: str,
        model: str,
        response: dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        ttl: int | None = None,
        **kwargs,
    ) -> bool:
        """
        Сохранить ответ в кэш

        Args:
            prompt: User prompt
            model: Model name
            response: AI response to cache
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            ttl: Custom TTL (seconds), default uses self.default_ttl
            **kwargs: Additional parameters

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            cache_key = self._generate_cache_key(prompt, model, temperature, max_tokens, **kwargs)

            # Add cache metadata
            response_copy = response.copy()
            response_copy["cached_at"] = time.time()
            response_copy["cache_key"] = cache_key

            # Serialize to JSON
            cached_data = json.dumps(response_copy)

            # Set with TTL
            ttl_seconds = ttl or self.default_ttl
            self.redis_client.setex(cache_key, ttl_seconds, cached_data)

            logger.debug(f"💾 Cached response for key: {cache_key[:16]}... (TTL: {ttl_seconds}s)")
            return True

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"❌ Cache set error: {e}")
            return False

    def invalidate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> bool:
        """
        Инвалидировать (удалить) закэшированный ответ

        Returns:
            True if deleted, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            cache_key = self._generate_cache_key(prompt, model, temperature, max_tokens, **kwargs)

            deleted = self.redis_client.delete(cache_key)

            if deleted:
                logger.info(f"🗑️ Invalidated cache for key: {cache_key[:16]}...")
                return True
            else:
                logger.debug(f"❌ No cache entry found for key: {cache_key[:16]}...")
                return False

        except Exception as e:
            logger.error(f"❌ Cache invalidation error: {e}")
            return False

    def clear_all(self) -> int:
        """
        Очистить весь AI кэш

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            # Find all AI cache keys
            keys = self.redis_client.keys("ai_cache:*")

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cleared {deleted} cache entries")
                return deleted
            else:
                logger.info("ℹ️ No cache entries to clear")
                return 0

        except Exception as e:
            logger.error(f"❌ Cache clear error: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """
        Получить статистику кэша

        Returns:
            Dict with hit rate, miss rate, errors, etc.
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "enabled": self.enabled,
            "redis_connected": self.redis_client is not None,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "bypassed": self.stats["bypassed"],
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "default_ttl": self.default_ttl,
        }


# Global cache manager instance
_cache_manager: AICacheManager | None = None


def get_cache_manager() -> AICacheManager:
    """Get or create global cache manager instance"""
    global _cache_manager

    if _cache_manager is None:
        # Read config from environment or config file
        from backend.core.config import get_config

        config = get_config()

        # Check if caching is enabled
        cache_enabled = getattr(config, "AI_CACHE_ENABLED", True)
        redis_url = getattr(config, "REDIS_URL", "redis://localhost:6379/0")
        cache_ttl = getattr(config, "AI_CACHE_TTL", 3600)

        _cache_manager = AICacheManager(
            redis_url=redis_url,
            default_ttl=cache_ttl,
            enabled=cache_enabled,
        )

    return _cache_manager
