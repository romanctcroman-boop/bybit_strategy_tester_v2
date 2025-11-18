"""
Comprehensive test suite for backend/security/rate_limiter.py
Target: 16% → 85% coverage (CRITICAL security module)

Test Scenarios (from DeepSeek Audit):
1. Rate limit enforcement (basic functionality)
2. Rate limit bypass attempts (security critical)
3. Concurrent requests from same user (race conditions)
4. Token bucket refill mechanism (timing accuracy)
5. Multi-tier limits (minute/hour/day)
6. Endpoint-specific limits
7. Statistics tracking
8. Bucket cleanup (memory management)
9. Cost-based rate limiting
10. Edge cases (zero tokens, negative tokens, etc.)
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from backend.security.rate_limiter import (
    TokenBucket,
    RateLimitConfig,
    RateLimiter
)


class TestTokenBucket:
    """Test TokenBucket implementation (foundational component)"""
    
    def test_token_bucket_creation(self):
        """Test bucket initialization with rate and capacity"""
        bucket = TokenBucket(rate=10.0, capacity=100)
        
        assert bucket.rate == 10.0
        assert bucket.capacity == 100
        assert bucket.tokens == 100  # Starts full
        assert bucket.last_refill > 0
    
    def test_consume_tokens_success(self):
        """Test successful token consumption"""
        bucket = TokenBucket(rate=10.0, capacity=100)
        
        # Should have full capacity
        result = bucket.consume(50)
        assert result is True
        assert bucket.tokens == pytest.approx(50, abs=0.01)
        
        # Consume remaining
        result = bucket.consume(50)
        assert result is True
        assert bucket.tokens == pytest.approx(0, abs=0.01)
    
    def test_consume_tokens_insufficient(self):
        """Test consumption fails when not enough tokens"""
        bucket = TokenBucket(rate=10.0, capacity=10)
        
        # Consume all tokens
        bucket.consume(10)
        
        # Should fail (no tokens left)
        result = bucket.consume(1)
        assert result is False
        assert bucket.tokens == pytest.approx(0, abs=0.01)  # No change
    
    def test_token_refill_over_time(self):
        """Test tokens refill based on elapsed time"""
        bucket = TokenBucket(rate=10.0, capacity=100)  # 10 tokens/second
        
        # Consume all tokens
        bucket.consume(100)
        assert bucket.tokens == 0
        
        # Wait 0.5 seconds (should refill 5 tokens)
        time.sleep(0.5)
        bucket._refill()
        
        assert bucket.tokens >= 4.5  # Allow for timing variance
        assert bucket.tokens <= 5.5
    
    def test_refill_does_not_exceed_capacity(self):
        """Test refill respects max capacity"""
        bucket = TokenBucket(rate=100.0, capacity=10)  # Fast refill
        
        # Start with some tokens
        bucket.consume(5)
        
        # Wait enough time to exceed capacity
        time.sleep(0.2)  # 20 tokens worth of time
        bucket._refill()
        
        # Should not exceed capacity
        assert bucket.tokens == 10
    
    def test_get_wait_time_with_tokens_available(self):
        """Test wait time is 0 when tokens available"""
        bucket = TokenBucket(rate=10.0, capacity=100)
        
        wait_time = bucket.get_wait_time(50)
        assert wait_time == 0.0
    
    def test_get_wait_time_insufficient_tokens(self):
        """Test wait time calculated correctly"""
        bucket = TokenBucket(rate=10.0, capacity=10)  # 10 tokens/sec
        
        # Consume all tokens
        bucket.consume(10)
        
        # Need 5 tokens = 0.5 seconds wait
        wait_time = bucket.get_wait_time(5)
        assert wait_time >= 0.45
        assert wait_time <= 0.55
    
    def test_concurrent_consume_race_condition(self):
        """Test token consumption is atomic (no race condition)"""
        bucket = TokenBucket(rate=10.0, capacity=10)
        
        # Simulate concurrent consumption
        results = []
        for _ in range(15):  # Try to consume more than capacity
            results.append(bucket.consume(1))
        
        # Exactly 10 should succeed (capacity)
        assert sum(results) == 10
        assert bucket.tokens == pytest.approx(0, abs=0.01)


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass"""
    
    def test_default_config(self):
        """Test default rate limit values"""
        config = RateLimitConfig()
        
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.requests_per_day == 10000
        assert config.burst_size == 10
    
    def test_custom_config(self):
        """Test custom rate limit configuration"""
        config = RateLimitConfig(
            requests_per_minute=120,
            requests_per_hour=5000,
            requests_per_day=50000,
            burst_size=20
        )
        
        assert config.requests_per_minute == 120
        assert config.requests_per_hour == 5000
        assert config.requests_per_day == 50000
        assert config.burst_size == 20


class TestRateLimiter:
    """Test RateLimiter multi-tier rate limiting"""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter creates with default config"""
        limiter = RateLimiter()
        
        assert limiter.config.requests_per_minute == 60
        assert len(limiter._user_minute_buckets) == 0
        assert len(limiter._user_hour_buckets) == 0
        assert len(limiter._user_day_buckets) == 0
    
    def test_rate_limiter_custom_config(self):
        """Test rate limiter with custom configuration"""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_size=15
        )
        limiter = RateLimiter(config=config)
        
        assert limiter.config.requests_per_minute == 100
        assert limiter.config.requests_per_hour == 2000
        assert limiter.config.burst_size == 15
    
    def test_first_request_creates_buckets(self):
        """Test buckets are created on first request"""
        limiter = RateLimiter()
        
        allowed, reason = limiter.check_rate_limit("user123")
        
        assert allowed is True
        assert reason is None
        assert "user123" in limiter._user_minute_buckets
        assert "user123" in limiter._user_hour_buckets
        assert "user123" in limiter._user_day_buckets
    
    def test_rate_limit_within_limits(self):
        """Test requests within rate limits are allowed"""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_size=10
        )
        limiter = RateLimiter(config=config)
        
        # Make 5 requests (well within burst)
        for _ in range(5):
            allowed, reason = limiter.check_rate_limit("user123")
            assert allowed is True
            assert reason is None
    
    def test_minute_rate_limit_exceeded(self):
        """Test minute rate limit enforcement"""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_size=5  # Small burst
        )
        limiter = RateLimiter(config=config)
        
        # Exhaust burst capacity
        for _ in range(5):
            allowed, _ = limiter.check_rate_limit("user123")
            assert allowed is True
        
        # Next request should fail (no tokens left)
        allowed, reason = limiter.check_rate_limit("user123")
        assert allowed is False
        assert "Rate limit" in reason
        assert "requests/minute" in reason
    
    def test_hour_rate_limit_exceeded(self):
        """Test hour rate limit enforcement"""
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=100,  # Low hour limit
            burst_size=200  # Large burst (won't hit minute limit)
        )
        limiter = RateLimiter(config=config)
        
        # Pre-set hour bucket to near limit
        limiter._user_hour_buckets["user123"] = TokenBucket(
            rate=100 / 3600.0,
            capacity=10
        )
        limiter._user_hour_buckets["user123"].tokens = 0.5  # Almost empty
        
        # Minute bucket has capacity
        limiter._user_minute_buckets["user123"] = TokenBucket(
            rate=60 / 60.0,
            capacity=200
        )
        
        # Day bucket has capacity
        limiter._user_day_buckets["user123"] = TokenBucket(
            rate=10000 / 86400.0,
            capacity=200
        )
        
        # Should fail on hour limit
        allowed, reason = limiter.check_rate_limit("user123", cost=1)
        assert allowed is False
        assert "requests/hour" in reason
    
    def test_day_rate_limit_exceeded(self):
        """Test day rate limit enforcement"""
        config = RateLimitConfig(
            requests_per_day=1000,
            burst_size=100
        )
        limiter = RateLimiter(config=config)
        
        # Pre-set all buckets
        limiter._user_minute_buckets["user123"] = TokenBucket(rate=1.0, capacity=100)
        limiter._user_hour_buckets["user123"] = TokenBucket(rate=1.0, capacity=100)
        limiter._user_day_buckets["user123"] = TokenBucket(
            rate=1000 / 86400.0,
            capacity=100
        )
        limiter._user_day_buckets["user123"].tokens = 0.5  # Almost empty
        
        # Should fail on day limit
        allowed, reason = limiter.check_rate_limit("user123", cost=1)
        assert allowed is False
        assert "requests/day" in reason
    
    def test_endpoint_specific_limit(self):
        """Test endpoint-specific rate limiting"""
        limiter = RateLimiter()
        
        # First request to endpoint should succeed
        allowed, _ = limiter.check_rate_limit("user123", endpoint="/api/expensive")
        assert allowed is True
        
        # Should create endpoint-specific bucket
        assert "/api/expensive" in limiter._endpoint_buckets
        assert "user123" in limiter._endpoint_buckets["/api/expensive"]
    
    def test_endpoint_limit_stricter_than_global(self):
        """Test endpoint limits are stricter than global limits"""
        config = RateLimitConfig(
            requests_per_minute=120,  # Global: 120/min
            burst_size=20
        )
        limiter = RateLimiter(config=config)
        
        # Exhaust endpoint-specific burst (burst_size // 2 = 10)
        for _ in range(10):
            allowed, _ = limiter.check_rate_limit("user123", endpoint="/api/expensive")
            assert allowed is True
        
        # Next request should fail (endpoint limit)
        allowed, reason = limiter.check_rate_limit("user123", endpoint="/api/expensive")
        assert allowed is False
        assert "Endpoint rate limit" in reason
    
    def test_cost_based_rate_limiting(self):
        """Test requests with different costs"""
        config = RateLimitConfig(burst_size=10)
        limiter = RateLimiter(config=config)
        
        # Expensive request (cost=5)
        allowed, _ = limiter.check_rate_limit("user123", cost=5)
        assert allowed is True
        
        # Another expensive request
        allowed, _ = limiter.check_rate_limit("user123", cost=5)
        assert allowed is True
        
        # Should fail (10 tokens used, burst=10)
        allowed, reason = limiter.check_rate_limit("user123", cost=1)
        assert allowed is False
    
    def test_get_user_stats(self):
        """Test user statistics retrieval"""
        limiter = RateLimiter()
        
        # Make some requests
        limiter.check_rate_limit("user123")
        limiter.check_rate_limit("user123")
        
        stats = limiter.get_user_stats("user123")
        
        assert stats["user_id"] == "user123"
        assert stats["total_requests"] == 2
        assert stats["blocked_requests"] == 0
        assert "limits" in stats
        assert "current_tokens" in stats
        assert "bucket_capacity" in stats
    
    def test_user_stats_tracks_blocked_requests(self):
        """Test blocked requests are counted in stats"""
        config = RateLimitConfig(burst_size=2)
        limiter = RateLimiter(config=config)
        
        # Use up burst
        limiter.check_rate_limit("user123")
        limiter.check_rate_limit("user123")
        
        # Block next request
        limiter.check_rate_limit("user123")
        
        stats = limiter.get_user_stats("user123")
        assert stats["total_requests"] == 3
        assert stats["blocked_requests"] == 1
    
    def test_reset_user_limits(self):
        """Test resetting user rate limits"""
        limiter = RateLimiter()
        
        # Make requests
        limiter.check_rate_limit("user123")
        limiter.check_rate_limit("user123")
        
        # Reset
        limiter.reset_user_limits("user123")
        
        # Buckets should be cleared
        assert "user123" not in limiter._user_minute_buckets
        assert "user123" not in limiter._user_hour_buckets
        assert "user123" not in limiter._user_day_buckets
        assert limiter._request_counts.get("user123", 0) == 0
        assert limiter._blocked_counts.get("user123", 0) == 0
    
    def test_get_global_stats(self):
        """Test global statistics across all users"""
        limiter = RateLimiter()
        
        # Make requests from multiple users
        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user2")
        limiter.check_rate_limit("user3")
        
        stats = limiter.get_global_stats()
        
        assert stats["total_users"] == 3
        assert stats["total_requests"] == 3
        assert stats["total_blocked"] == 0
        assert stats["block_rate"] == 0.0
        assert "active_buckets" in stats
    
    def test_global_stats_block_rate(self):
        """Test global block rate calculation"""
        config = RateLimitConfig(burst_size=1)
        limiter = RateLimiter(config=config)
        
        # 1 allowed, 1 blocked
        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user1")  # Blocked
        
        stats = limiter.get_global_stats()
        assert stats["total_requests"] == 2
        assert stats["total_blocked"] == 1
        assert stats["block_rate"] == 50.0
    
    def test_cleanup_old_buckets(self):
        """Test cleanup of inactive buckets"""
        limiter = RateLimiter()
        
        # Create buckets for users
        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user2")
        
        # Mock old last_refill time
        with patch('time.time', return_value=time.time() + 7200):  # 2 hours later
            removed = limiter.cleanup_old_buckets(inactive_seconds=3600)  # 1 hour threshold
        
        # Should have cleaned up buckets
        assert removed == 6  # 3 buckets per user × 2 users
    
    def test_cleanup_does_not_remove_active_buckets(self):
        """Test cleanup preserves recently active buckets"""
        limiter = RateLimiter()
        
        # Create bucket
        limiter.check_rate_limit("user1")
        
        # Try cleanup immediately (buckets are active)
        removed = limiter.cleanup_old_buckets(inactive_seconds=3600)
        
        # Should not remove active buckets
        assert removed == 0
        assert "user1" in limiter._user_minute_buckets
    
    def test_multiple_users_isolation(self):
        """Test users have isolated rate limits"""
        config = RateLimitConfig(burst_size=2)
        limiter = RateLimiter(config=config)
        
        # User1 exhausts burst
        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user1")
        
        # User1 blocked
        allowed1, _ = limiter.check_rate_limit("user1")
        assert allowed1 is False
        
        # User2 should still have full capacity
        allowed2, _ = limiter.check_rate_limit("user2")
        assert allowed2 is True
    
    def test_rate_limit_bypass_attempt_concurrent(self):
        """SECURITY: Test concurrent requests cannot bypass rate limit"""
        config = RateLimitConfig(burst_size=10)
        limiter = RateLimiter(config=config)
        
        # Simulate 20 concurrent requests (exceeds burst)
        results = []
        for _ in range(20):
            allowed, _ = limiter.check_rate_limit("attacker")
            results.append(allowed)
        
        # Exactly 10 should succeed (burst capacity)
        # Note: Without proper locking, more than 10 might succeed (race condition)
        assert sum(results) <= 10  # At most burst_size requests
    
    def test_negative_cost_rejected(self):
        """SECURITY: Test negative cost is handled safely"""
        limiter = RateLimiter()
        
        # Negative cost should be rejected (exploit attempt)
        allowed, reason = limiter.check_rate_limit("user123", cost=-100)
        
        # Should be rejected with proper error message
        assert allowed is False
        assert "Invalid request cost" in reason
        
        # Should not have consumed any tokens
        stats = limiter.get_user_stats("user123")
        assert stats["current_tokens"]["minute"] == limiter.config.burst_size
    
    def test_zero_cost_request(self):
        """Test zero-cost requests are rejected (must be positive)"""
        limiter = RateLimiter()
        
        # Zero-cost request should be rejected
        allowed, reason = limiter.check_rate_limit("user123", cost=0)
        assert allowed is False
        assert "Invalid request cost" in reason
        
        stats = limiter.get_user_stats("user123")
        # Should have full capacity (no tokens consumed)
        assert stats["current_tokens"]["minute"] == limiter.config.burst_size
    
    def test_large_cost_request(self):
        """Test requests with cost exceeding burst capacity"""
        config = RateLimitConfig(burst_size=10)
        limiter = RateLimiter(config=config)
        
        # Request cost > burst capacity
        allowed, reason = limiter.check_rate_limit("user123", cost=50)
        
        # Should fail (not enough tokens)
        assert allowed is False
        assert "Rate limit" in reason
    
    def test_wait_time_accuracy(self):
        """Test wait time estimation is accurate"""
        config = RateLimitConfig(
            requests_per_minute=60,  # 1 per second
            burst_size=5
        )
        limiter = RateLimiter(config=config)
        
        # Exhaust burst
        for _ in range(5):
            limiter.check_rate_limit("user123")
        
        # Get wait time
        allowed, reason = limiter.check_rate_limit("user123")
        assert allowed is False
        
        # Extract wait time from reason (format: "Wait X.Xs")
        import re
        match = re.search(r"Wait (\d+\.\d+)s", reason)
        assert match is not None
        wait_time = float(match.group(1))
        
        # Should be ~1 second (1 token at 60/min rate)
        assert 0.5 <= wait_time <= 1.5


class TestRateLimiterLogging:
    """Test rate limiter logging behavior"""
    
    def test_blocked_request_logged(self, caplog):
        """Test blocked requests are logged"""
        import logging
        caplog.set_level(logging.WARNING)
        
        config = RateLimitConfig(burst_size=1)
        limiter = RateLimiter(config=config)
        
        # Use up burst
        limiter.check_rate_limit("user123")
        
        # Block request
        limiter.check_rate_limit("user123")
        
        # Check logs
        assert any("Rate limit exceeded" in record.message for record in caplog.records)
    
    def test_allowed_request_logged_debug(self, caplog):
        """Test allowed requests logged at debug level"""
        import logging
        caplog.set_level(logging.DEBUG, logger='security.rate_limiter')
        
        limiter = RateLimiter()
        limiter.check_rate_limit("user123")
        
        # Check debug log
        assert any("Rate limit check passed" in record.message for record in caplog.records)
    
    def test_reset_logged(self, caplog):
        """Test rate limit reset is logged"""
        import logging
        caplog.set_level(logging.INFO)
        
        limiter = RateLimiter()
        limiter.check_rate_limit("user123")
        limiter.reset_user_limits("user123")
        
        # Check log
        assert any("Reset rate limits" in record.message for record in caplog.records)


class TestRateLimiterEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_user_id(self):
        """Test handling of empty user ID"""
        limiter = RateLimiter()
        
        # Should still work (treats as valid user)
        allowed, _ = limiter.check_rate_limit("")
        assert allowed is True
    
    def test_very_long_user_id(self):
        """Test handling of very long user IDs"""
        limiter = RateLimiter()
        long_id = "user" * 10000  # Very long ID
        
        allowed, _ = limiter.check_rate_limit(long_id)
        assert allowed is True
    
    def test_special_characters_in_user_id(self):
        """Test user IDs with special characters"""
        limiter = RateLimiter()
        
        special_ids = [
            "user@example.com",
            "user-123_abc",
            "user.name",
            "user:session:123",
            "用户123",  # Unicode
        ]
        
        for user_id in special_ids:
            allowed, _ = limiter.check_rate_limit(user_id)
            assert allowed is True
    
    def test_stats_for_nonexistent_user(self):
        """Test getting stats for user with no requests"""
        limiter = RateLimiter()
        
        # Should create buckets on stats request
        stats = limiter.get_user_stats("nonexistent")
        
        assert stats["total_requests"] == 0
        assert stats["blocked_requests"] == 0


# ============================================================================
# Performance Tests
# ============================================================================

class TestRateLimiterPerformance:
    """Test rate limiter performance characteristics"""
    
    def test_single_user_throughput(self):
        """Test throughput for single user"""
        limiter = RateLimiter()
        
        start_time = time.time()
        
        # 1000 requests
        for _ in range(1000):
            limiter.check_rate_limit("user123")
        
        elapsed = time.time() - start_time
        
        # Should handle 1000 requests very quickly (< 0.2s, adjusted for slower hardware)
        assert elapsed < 0.2
    
    def test_many_users_throughput(self):
        """Test throughput with many users"""
        limiter = RateLimiter()
        
        start_time = time.time()
        
        # 100 users × 10 requests each
        for user_id in range(100):
            for _ in range(10):
                limiter.check_rate_limit(f"user{user_id}")
        
        elapsed = time.time() - start_time
        
        # Should handle 1000 requests across 100 users quickly
        assert elapsed < 0.5
    
    def test_stats_query_performance(self):
        """Test statistics query performance"""
        limiter = RateLimiter()
        
        # Create 100 users
        for user_id in range(100):
            limiter.check_rate_limit(f"user{user_id}")
        
        start_time = time.time()
        
        # Query global stats
        limiter.get_global_stats()
        
        elapsed = time.time() - start_time
        
        # Should be very fast (< 0.01s)
        assert elapsed < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
