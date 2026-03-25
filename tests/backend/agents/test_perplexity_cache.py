"""
Tests for PerplexityIntegration TTL cache.

Tests cover:
- Cache miss on first call
- Cache hit on subsequent calls within TTL
- Cache expiry after TTL
- Cache invalidation (by symbol, full clear)
- Cache stats tracking
- Eviction of expired entries
- parse_error responses not cached
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.consensus.perplexity_integration import (
    PerplexityIntegration,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def integration() -> PerplexityIntegration:
    """Fresh PerplexityIntegration with short TTL for testing."""
    config = {"perplexity_relevance": "ALWAYS", "perplexity_cache_ttl": 2}
    pi = PerplexityIntegration(config=config)
    pi.cache_ttl_seconds = 2  # Short TTL for tests
    return pi


# =============================================================================
# CACHE BEHAVIOR
# =============================================================================


class TestPerplexityCacheInit:
    """Tests for cache initialization."""

    def test_cache_starts_empty(self, integration):
        """Cache is empty on init."""
        assert len(integration._context_cache) == 0

    def test_stats_include_cache_hits(self, integration):
        """Stats include cache_hits counter."""
        stats = integration.get_stats()
        assert "cache_hits" in stats
        assert stats["cache_hits"] == 0

    def test_stats_include_cache_size(self, integration):
        """Stats include cache_size."""
        stats = integration.get_stats()
        assert "cache_size" in stats
        assert stats["cache_size"] == 0

    def test_stats_include_cache_ttl(self, integration):
        """Stats include cache TTL."""
        stats = integration.get_stats()
        assert "cache_ttl_seconds" in stats


class TestCacheHitMiss:
    """Tests for cache hit/miss behavior."""

    @pytest.mark.asyncio
    async def test_cache_miss_first_call(self, integration):
        """First call should be a cache miss."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "trending", "trend_direction": "up"}'
        mock_response.latency_ms = 500
        mock_response.total_tokens = 100

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        result = await integration.enrich_context("BTCUSDT", "rsi")

        assert result.get("perplexity_cache_hit") is False
        assert result["market_context"]["regime"] == "trending"
        assert mock_client.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_hit_second_call(self, integration):
        """Second call within TTL should be a cache hit."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "ranging", "trend_direction": "sideways"}'
        mock_response.latency_ms = 400
        mock_response.total_tokens = 80

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        # First call (miss)
        await integration.enrich_context("BTCUSDT", "macd")

        # Second call (hit)
        result = await integration.enrich_context("BTCUSDT", "macd")

        assert result.get("perplexity_cache_hit") is True
        assert result["market_context"]["regime"] == "ranging"
        # Client should have been called only once
        assert mock_client.chat.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_miss_different_symbol(self, integration):
        """Different symbol should be a cache miss."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "volatile"}'
        mock_response.latency_ms = 300
        mock_response.total_tokens = 60

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")
        await integration.enrich_context("ETHUSDT", "rsi")

        # Both should be API calls (different symbols)
        assert mock_client.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_miss_different_strategy(self, integration):
        """Different strategy type should be a cache miss."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "trending"}'
        mock_response.latency_ms = 300
        mock_response.total_tokens = 60

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")
        await integration.enrich_context("BTCUSDT", "macd")

        # Both should be API calls (different strategies)
        assert mock_client.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self, integration):
        """Stats correctly track cache hits."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "trending"}'
        mock_response.latency_ms = 300
        mock_response.total_tokens = 60

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")
        await integration.enrich_context("BTCUSDT", "rsi")
        await integration.enrich_context("BTCUSDT", "rsi")

        stats = integration.get_stats()
        assert stats["cache_hits"] == 2  # 2nd and 3rd calls are hits
        assert stats["calls_made"] == 1  # Only 1 real API call


class TestCacheExpiry:
    """Tests for TTL-based cache expiration."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, integration):
        """Cache entry expires after TTL seconds."""
        integration.cache_ttl_seconds = 0.1  # 100ms TTL for test

        mock_response = MagicMock()
        mock_response.content = '{"regime": "trending"}'
        mock_response.latency_ms = 100
        mock_response.total_tokens = 50

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")

        # Wait for TTL to expire
        time.sleep(0.15)

        await integration.enrich_context("BTCUSDT", "rsi")

        # Should have made 2 API calls (cache expired)
        assert mock_client.chat.call_count == 2


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_all(self, integration):
        """invalidate_cache() clears entire cache."""
        integration._context_cache[("BTCUSDT", "rsi")] = (time.time(), {"regime": "trending"})
        integration._context_cache[("ETHUSDT", "macd")] = (time.time(), {"regime": "ranging"})

        count = integration.invalidate_cache()
        assert count == 2
        assert len(integration._context_cache) == 0

    def test_invalidate_by_symbol(self, integration):
        """invalidate_cache(symbol=...) clears only that symbol."""
        integration._context_cache[("BTCUSDT", "rsi")] = (time.time(), {"regime": "trending"})
        integration._context_cache[("BTCUSDT", "macd")] = (time.time(), {"regime": "ranging"})
        integration._context_cache[("ETHUSDT", "rsi")] = (time.time(), {"regime": "volatile"})

        count = integration.invalidate_cache(symbol="BTCUSDT")
        assert count == 2
        assert len(integration._context_cache) == 1
        assert ("ETHUSDT", "rsi") in integration._context_cache

    def test_invalidate_empty_cache(self, integration):
        """Invalidating empty cache returns 0."""
        count = integration.invalidate_cache()
        assert count == 0

    def test_evict_expired(self, integration):
        """_evict_expired_cache removes old entries."""
        integration.cache_ttl_seconds = 0.05

        integration._context_cache[("BTCUSDT", "rsi")] = (time.time() - 1.0, {"regime": "old"})
        integration._context_cache[("ETHUSDT", "rsi")] = (time.time(), {"regime": "fresh"})

        integration._evict_expired_cache()

        assert ("BTCUSDT", "rsi") not in integration._context_cache
        assert ("ETHUSDT", "rsi") in integration._context_cache


class TestCacheEdgeCases:
    """Edge case tests for cache."""

    @pytest.mark.asyncio
    async def test_parse_error_not_cached(self, integration):
        """Responses with parse_error are NOT cached."""
        mock_response = MagicMock()
        mock_response.content = "not valid json at all"
        mock_response.latency_ms = 300
        mock_response.total_tokens = 60

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")

        # Should NOT be in cache due to parse error
        assert ("BTCUSDT", "rsi") not in integration._context_cache

    @pytest.mark.asyncio
    async def test_cache_hit_includes_age(self, integration):
        """Cache hit response includes age information."""
        mock_response = MagicMock()
        mock_response.content = '{"regime": "trending"}'
        mock_response.latency_ms = 300
        mock_response.total_tokens = 60

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        integration._perplexity_client = mock_client

        await integration.enrich_context("BTCUSDT", "rsi")
        result = await integration.enrich_context("BTCUSDT", "rsi")

        assert "perplexity_cache_age_s" in result
        assert result["perplexity_cache_age_s"] >= 0

    @pytest.mark.asyncio
    async def test_close_clears_cache(self, integration):
        """close() clears the cache."""
        integration._context_cache[("BTCUSDT", "rsi")] = (time.time(), {"regime": "trending"})

        await integration.close()

        assert len(integration._context_cache) == 0
