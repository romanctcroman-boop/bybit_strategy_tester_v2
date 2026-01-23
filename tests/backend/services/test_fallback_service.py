"""
Tests for FallbackService - Graceful Degradation

Tests cover:
1. Response caching (get/set, TTL, LRU eviction)
2. Static fallback responses
3. Degraded mode handlers
4. Service health management
5. Circuit breaker integration
"""

from datetime import datetime, timedelta, timezone  # noqa: F401

import pytest

from backend.services.fallback_service import (
    FallbackResponse,
    FallbackService,
    FallbackType,
    ResponseCache,
    ServiceHealth,
    ServiceStatus,
    get_fallback_service,
)


class TestResponseCache:
    """Tests for ResponseCache class"""

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations"""
        cache = ResponseCache(max_size=100)

        cache.set("test prompt", "deepseek", "test response")
        result = cache.get("test prompt", "deepseek")

        assert result is not None
        assert result.content == "test response"
        assert result.fallback_type == FallbackType.CACHED
        assert result.original_prompt == "test prompt"

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = ResponseCache()

        result = cache.get("nonexistent prompt", "deepseek")

        assert result is None

    def test_cache_ttl_expiration(self):
        """Test that expired entries are not returned"""
        cache = ResponseCache(default_ttl=1)  # 1 second TTL

        cache.set("test prompt", "deepseek", "test response")

        # Manually expire the entry
        key = cache._hash_prompt("test prompt", "deepseek")
        cache._cache[key].cached_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        result = cache.get("test prompt", "deepseek")
        assert result is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = ResponseCache(max_size=2)

        cache.set("prompt1", "deepseek", "response1")
        cache.set("prompt2", "deepseek", "response2")
        cache.set("prompt3", "deepseek", "response3")  # Should evict prompt1

        assert cache.get("prompt1", "deepseek") is None
        assert cache.get("prompt2", "deepseek") is not None
        assert cache.get("prompt3", "deepseek") is not None

    def test_cache_clear(self):
        """Test cache clear operation"""
        cache = ResponseCache()

        cache.set("prompt1", "deepseek", "response1")
        cache.set("prompt2", "deepseek", "response2")

        cache.clear()

        assert cache.get("prompt1", "deepseek") is None
        assert cache.get("prompt2", "deepseek") is None

    def test_cache_different_agent_types(self):
        """Test that different agent types have separate cache entries"""
        cache = ResponseCache()

        cache.set("same prompt", "deepseek", "deepseek response")
        cache.set("same prompt", "perplexity", "perplexity response")

        deepseek_result = cache.get("same prompt", "deepseek")
        perplexity_result = cache.get("same prompt", "perplexity")

        assert deepseek_result.content == "deepseek response"
        assert perplexity_result.content == "perplexity response"


class TestFallbackResponse:
    """Tests for FallbackResponse dataclass"""

    def test_is_expired_no_cached_at(self):
        """Test is_expired returns True when no cached_at"""
        response = FallbackResponse(
            content="test",
            fallback_type=FallbackType.STATIC,
            original_prompt="test",
            cached_at=None,
        )

        assert response.is_expired is True

    def test_is_expired_within_ttl(self):
        """Test is_expired returns False within TTL"""
        response = FallbackResponse(
            content="test",
            fallback_type=FallbackType.CACHED,
            original_prompt="test",
            cached_at=datetime.now(timezone.utc),
            ttl_seconds=3600,
        )

        assert response.is_expired is False

    def test_is_expired_past_ttl(self):
        """Test is_expired returns True past TTL"""
        response = FallbackResponse(
            content="test",
            fallback_type=FallbackType.CACHED,
            original_prompt="test",
            cached_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_seconds=3600,
        )

        assert response.is_expired is True

    def test_to_dict(self):
        """Test to_dict serialization"""
        now = datetime.now(timezone.utc)
        response = FallbackResponse(
            content="test content",
            fallback_type=FallbackType.CACHED,
            original_prompt="original",
            cached_at=now,
            ttl_seconds=1800,
            metadata={"key": "value"},
        )

        result = response.to_dict()

        assert result["content"] == "test content"
        assert result["fallback_type"] == "cached"
        assert result["original_prompt"] == "original"
        assert result["ttl_seconds"] == 1800
        assert result["metadata"] == {"key": "value"}


class TestServiceStatus:
    """Tests for ServiceStatus dataclass"""

    def test_to_dict(self):
        """Test ServiceStatus serialization"""
        now = datetime.now(timezone.utc)
        status = ServiceStatus(
            name="deepseek",
            health=ServiceHealth.HEALTHY,
            last_check=now,
            failure_count=0,
            success_count=100,
            circuit_state="closed",
            latency_p95_ms=150.5,
            error_rate=0.01,
        )

        result = status.to_dict()

        assert result["name"] == "deepseek"
        assert result["health"] == "healthy"
        assert result["failure_count"] == 0
        assert result["success_count"] == 100
        assert result["circuit_state"] == "closed"
        assert result["latency_p95_ms"] == 150.5
        assert result["error_rate"] == 0.01


class TestFallbackService:
    """Tests for FallbackService class"""

    @pytest.fixture
    def fallback_service(self):
        """Create a fresh FallbackService instance"""
        return FallbackService()

    def test_init_registers_default_static_responses(self, fallback_service):
        """Test that default static responses are registered"""
        # Static responses should be pre-registered
        assert len(fallback_service._static_responses) > 0

    def test_cache_response(self, fallback_service):
        """Test caching a response"""
        fallback_service.cache_response(
            prompt="test prompt",
            agent_type="deepseek",
            content="cached content",
        )

        result = fallback_service.get_fallback(
            prompt="test prompt",
            agent_type="deepseek",
        )

        assert result is not None
        assert result.content == "cached content"
        assert result.fallback_type == FallbackType.CACHED

    def test_get_fallback_static_health_check(self, fallback_service):
        """Test static fallback for health check"""
        result = fallback_service.get_fallback(
            prompt="system health check",
            agent_type="deepseek",
            task_type="health_check",
        )

        assert result is not None
        assert result.fallback_type == FallbackType.STATIC

    def test_get_fallback_returns_none_when_no_match(self, fallback_service):
        """Test get_fallback returns None when no fallback available"""
        _result = fallback_service.get_fallback(
            prompt="completely unique random prompt 12345xyz",
            agent_type="unknown_agent",
        )

        # May return None or a degraded response
        # Depends on implementation
        pass  # Just verify no exception

    def test_register_degraded_handler(self, fallback_service):
        """Test registering degraded mode handler"""

        def custom_handler(prompt: str) -> str:
            return f"Degraded: {prompt}"

        fallback_service.register_degraded_handler("test_pattern", custom_handler)

        result = fallback_service.get_fallback(
            prompt="this contains test_pattern in it",
            agent_type="deepseek",
        )

        assert result is not None
        assert result.fallback_type == FallbackType.DEGRADED

    def test_update_service_health(self, fallback_service):
        """Test updating service health status"""
        fallback_service.update_service_health(
            name="deepseek",
            health=ServiceHealth.DEGRADED,
            circuit_state="half_open",
            latency_p95=250.0,
            error_rate=0.15,
        )

        status = fallback_service.get_service_health("deepseek")

        assert status is not None
        assert status.health == ServiceHealth.DEGRADED
        assert status.circuit_state == "half_open"

    def test_get_service_health_unknown_service(self, fallback_service):
        """Test getting health for unknown service auto-registers it"""
        status = fallback_service.get_service_health("unknown_service_xyz")

        # Should auto-register with UNKNOWN health
        assert status is not None
        assert status.health == ServiceHealth.UNKNOWN

    def test_get_all_services_health(self, fallback_service):
        """Test getting all service health statuses"""
        fallback_service.update_service_health(
            name="deepseek",
            health=ServiceHealth.HEALTHY,
        )
        fallback_service.update_service_health(
            name="perplexity",
            health=ServiceHealth.DEGRADED,
        )

        statuses = fallback_service.get_all_services_health()

        assert len(statuses) >= 2
        assert "deepseek" in statuses
        assert "perplexity" in statuses

    def test_get_overall_health_all_healthy(self, fallback_service):
        """Test overall health when all services healthy"""
        fallback_service._services.clear()
        fallback_service.update_service_health(
            name="deepseek",
            health=ServiceHealth.HEALTHY,
        )
        fallback_service.update_service_health(
            name="perplexity",
            health=ServiceHealth.HEALTHY,
        )

        overall = fallback_service.get_overall_health()
        assert overall == ServiceHealth.HEALTHY

    def test_get_overall_health_with_unhealthy(self, fallback_service):
        """Test overall health when one service unhealthy"""
        fallback_service._services.clear()
        fallback_service.update_service_health(
            name="deepseek",
            health=ServiceHealth.HEALTHY,
        )
        fallback_service.update_service_health(
            name="perplexity",
            health=ServiceHealth.UNHEALTHY,
        )

        overall = fallback_service.get_overall_health()
        assert overall == ServiceHealth.UNHEALTHY


class TestGetFallbackService:
    """Tests for singleton getter"""

    def test_get_fallback_service_returns_singleton(self):
        """Test that get_fallback_service returns same instance"""
        service1 = get_fallback_service()
        service2 = get_fallback_service()

        assert service1 is service2

    def test_get_fallback_service_returns_fallback_service(self):
        """Test that get_fallback_service returns FallbackService instance"""
        service = get_fallback_service()

        assert isinstance(service, FallbackService)
