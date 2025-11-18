"""
Tests for Rate Limiter (Phase 2)
Token bucket algorithm with backpressure handling
"""

import pytest
import asyncio
import time
from rate_limiter import RateLimiter


class TestRateLimiter:
    """Test rate limiter functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_creation(self, rate_limiter_fixture):
        """Test rate limiter is created and started"""
        assert rate_limiter_fixture is not None
        assert rate_limiter_fixture._running is True
        assert len(rate_limiter_fixture._buckets) == 0  # No buckets yet
    
    @pytest.mark.asyncio
    async def test_acquire_token_success(self, rate_limiter_fixture):
        """Test successful token acquisition"""
        result = await rate_limiter_fixture.acquire("test_key", tokens=1, wait=False)
        assert result is True
        
        # Check stats
        stats = rate_limiter_fixture.get_stats("test_key")
        assert stats["total_requests"] == 1
        assert stats["allowed"] == 1
        assert stats["rejected"] == 0
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, rate_limiter_fixture):
        """Test rate limit rejection when exceeded"""
        # Set very low limit for testing
        rate_limiter_fixture.set_limit("test_key", rate=1, burst=1)
        
        # First request should succeed
        result1 = await rate_limiter_fixture.acquire("test_key", tokens=1, wait=False)
        assert result1 is True
        
        # Second request should fail (burst exhausted)
        result2 = await rate_limiter_fixture.acquire("test_key", tokens=1, wait=False)
        assert result2 is False
        
        stats = rate_limiter_fixture.get_stats("test_key")
        assert stats["allowed"] == 1
        assert stats["rejected"] == 1
        assert stats["rejection_rate"] > 0
    
    @pytest.mark.asyncio
    async def test_rate_limit_with_wait(self, rate_limiter_fixture):
        """Test automatic waiting when rate limit exceeded"""
        rate_limiter_fixture.set_limit("test_key", rate=60, burst=2)  # 60/min, burst=2
        
        # Use up burst capacity
        await rate_limiter_fixture.acquire("test_key", tokens=2, wait=False)
        
        # This should wait for tokens to refill
        start_time = time.time()
        result = await rate_limiter_fixture.acquire("test_key", tokens=1, wait=True)
        elapsed = time.time() - start_time
        
        assert result is True
        assert elapsed > 0  # Should have waited
        
        stats = rate_limiter_fixture.get_stats("test_key")
        assert stats["total_wait_time"] > 0
    
    @pytest.mark.asyncio
    async def test_custom_rate_limits(self, rate_limiter_fixture):
        """Test setting custom rate limits per key"""
        # Set custom limit
        rate_limiter_fixture.set_limit("api_a", rate=100, burst=5)
        rate_limiter_fixture.set_limit("api_b", rate=50, burst=3)
        
        # Acquire from both
        result_a = await rate_limiter_fixture.acquire("api_a", tokens=5, wait=False)
        result_b = await rate_limiter_fixture.acquire("api_b", tokens=3, wait=False)
        
        assert result_a is True
        assert result_b is True
        
        # Check capacities
        stats_a = rate_limiter_fixture.get_stats("api_a")
        stats_b = rate_limiter_fixture.get_stats("api_b")
        
        assert stats_a["capacity"] == 5
        assert stats_b["capacity"] == 3
    
    @pytest.mark.asyncio
    async def test_check_limit_without_consuming(self, rate_limiter_fixture):
        """Test checking rate limit without consuming tokens"""
        rate_limiter_fixture.set_limit("test_key", rate=60, burst=5)
        
        # Check limit (should not consume)
        can_proceed = await rate_limiter_fixture.check_limit("test_key")
        assert can_proceed is True
        
        # Tokens should still be available
        stats = rate_limiter_fixture.get_stats("test_key")
        assert stats["current_tokens"] > 4.9  # Full capacity (minus floating point error)
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit(self, rate_limiter_fixture):
        """Test resetting rate limit for a key"""
        rate_limiter_fixture.set_limit("test_key", rate=60, burst=3)
        
        # Use up all tokens
        await rate_limiter_fixture.acquire("test_key", tokens=3, wait=False)
        
        stats_before = rate_limiter_fixture.get_stats("test_key")
        assert stats_before["current_tokens"] < 1
        
        # Reset
        await rate_limiter_fixture.reset("test_key")
        
        # Should have full capacity again
        stats_after = rate_limiter_fixture.get_stats("test_key")
        assert stats_after["current_tokens"] >= 2.9  # Full capacity restored
    
    @pytest.mark.asyncio
    async def test_rate_limiter_stats(self, rate_limiter_fixture):
        """Test comprehensive statistics tracking"""
        rate_limiter_fixture.set_limit("test_key", rate=60, burst=5)
        
        # Make several requests
        await rate_limiter_fixture.acquire("test_key", tokens=1, wait=False)  # Success
        await rate_limiter_fixture.acquire("test_key", tokens=2, wait=False)  # Success
        await rate_limiter_fixture.acquire("test_key", tokens=3, wait=False)  # Fail (only 2 left)
        
        stats = rate_limiter_fixture.get_stats("test_key")
        
        assert stats["exists"] is True
        assert stats["total_requests"] == 3
        assert stats["allowed"] == 2
        assert stats["rejected"] == 1
        assert stats["rejection_rate"] > 0
        assert "current_tokens" in stats
        assert "capacity" in stats
    
    @pytest.mark.asyncio
    async def test_get_all_stats(self, rate_limiter_fixture):
        """Test getting statistics for all keys"""
        # Create multiple keys
        await rate_limiter_fixture.acquire("key1", wait=False)
        await rate_limiter_fixture.acquire("key2", wait=False)
        await rate_limiter_fixture.acquire("key3", wait=False)
        
        all_stats = rate_limiter_fixture.get_all_stats()
        
        assert len(all_stats) == 3
        assert "key1" in all_stats
        assert "key2" in all_stats
        assert "key3" in all_stats
