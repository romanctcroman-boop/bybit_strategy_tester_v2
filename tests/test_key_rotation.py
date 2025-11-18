"""
Unit Tests for Key Rotation Strategy

Tests intelligent API key rotation based on DeepSeek Agent recommendations:
1. Weighted priority queue selection
2. Health tracking per key
3. Exponential cooldown (2^failures minutes)
4. Rate limit handling (5-minute cooldown)
5. Dead key detection (>10 failures)
6. Alert when >50% keys unhealthy
7. Fair distribution (Gini coefficient)
"""

import asyncio
import pytest
import time

from reliability.key_rotation import (
    KeyRotation,
    KeyConfig,
    KeyStatus,
    KeyHealth,
)


@pytest.fixture
def test_keys():
    """Create test API keys"""
    return [
        KeyConfig(id="key1", api_key="test1", secret="secret1", weight=1.0),
        KeyConfig(id="key2", api_key="test2", secret="secret2", weight=1.0),
        KeyConfig(id="key3", api_key="test3", secret="secret3", weight=0.5),  # Lower weight
    ]


@pytest.fixture
def rotation(test_keys):
    """Create key rotation instance"""
    return KeyRotation(test_keys)


class TestKeyRotationInit:
    """Test key rotation initialization"""
    
    def test_init_with_keys(self, test_keys):
        """Test initialization with valid keys"""
        rotation = KeyRotation(test_keys)
        assert len(rotation.keys) == 3
        assert len(rotation.health) == 3
        assert all(h.status == KeyStatus.HEALTHY for h in rotation.health.values())
    
    def test_init_without_keys(self):
        """Test initialization fails with no keys"""
        with pytest.raises(ValueError, match="At least one API key required"):
            KeyRotation([])


class TestKeySelection:
    """Test key selection logic"""
    
    @pytest.mark.asyncio
    async def test_get_next_key_returns_healthy_key(self, rotation):
        """Test that get_next_key returns a healthy key"""
        key = await rotation.get_next_key()
        assert key is not None
        assert key.id in rotation.keys
        assert rotation.health[key.id].is_available()
    
    @pytest.mark.asyncio
    async def test_weighted_priority_selection(self):
        """Test that higher weight keys are preferred"""
        keys = [
            KeyConfig(id="low", api_key="test1", secret="s1", weight=0.1),
            KeyConfig(id="high", api_key="test2", secret="s2", weight=10.0),
        ]
        rotation = KeyRotation(keys)
        
        # Get key multiple times - high weight should be selected
        selected = []
        for _ in range(10):
            key = await rotation.get_next_key()
            selected.append(key.id)
            await rotation.report_success(key.id)
        
        # High weight key should be selected more often
        high_count = selected.count("high")
        assert high_count >= 8  # At least 80% of the time
    
    @pytest.mark.asyncio
    async def test_get_next_key_timeout(self, rotation):
        """Test timeout when no keys available"""
        # Mark all keys as dead
        for key_id in rotation.keys:
            rotation.health[key_id].status = KeyStatus.DEAD
        
        with pytest.raises(RuntimeError, match="All API keys are DEAD"):
            await rotation.get_next_key(timeout=0.5)


class TestSuccessReporting:
    """Test success reporting"""
    
    @pytest.mark.asyncio
    async def test_report_success_increments_counters(self, rotation):
        """Test that success increments counters"""
        key = await rotation.get_next_key()
        
        await rotation.report_success(key.id)
        
        health = rotation.health[key.id]
        assert health.total_requests == 1
        assert health.total_successes == 1
        assert health.total_failures == 0
        assert health.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_success_clears_cooldown(self, rotation):
        """Test that success clears cooldown"""
        key = await rotation.get_next_key()
        
        # Fail the key (puts it in cooldown)
        await rotation.report_failure(key.id)
        assert rotation.health[key.id].status == KeyStatus.COOLING
        
        # Wait a bit, then succeed
        await asyncio.sleep(0.1)
        await rotation.report_success(key.id)
        
        # Should be HEALTHY again
        assert rotation.health[key.id].status == KeyStatus.HEALTHY
        assert rotation.health[key.id].consecutive_failures == 0


class TestFailureReporting:
    """Test failure reporting and cooldown logic"""
    
    @pytest.mark.asyncio
    async def test_report_failure_increments_counters(self, rotation):
        """Test that failure increments counters"""
        key = await rotation.get_next_key()
        
        await rotation.report_failure(key.id)
        
        health = rotation.health[key.id]
        assert health.total_requests == 1
        assert health.total_failures == 1
        assert health.consecutive_failures == 1
    
    @pytest.mark.asyncio
    async def test_exponential_cooldown(self, rotation):
        """Test exponential cooldown: 2^failures minutes"""
        key = await rotation.get_next_key()
        
        # First failure: 2^1 = 2 minutes
        await rotation.report_failure(key.id)
        health = rotation.health[key.id]
        assert health.status == KeyStatus.COOLING
        assert health.cooldown_until is not None
        cooldown1 = health.cooldown_until - time.time()
        assert 115 <= cooldown1 <= 125  # ~120 seconds (2 minutes)
        
        # Reset and fail again with 2 consecutive failures
        await rotation.report_success(key.id)
        await rotation.report_failure(key.id)
        await rotation.report_failure(key.id)
        
        health = rotation.health[key.id]
        cooldown2 = health.cooldown_until - time.time()
        assert 235 <= cooldown2 <= 245  # ~240 seconds (4 minutes = 2^2)
    
    @pytest.mark.asyncio
    async def test_rate_limit_special_handling(self, rotation):
        """Test rate limit gets 5-minute cooldown"""
        key = await rotation.get_next_key()
        
        await rotation.report_failure(key.id, error_type="rate_limit")
        
        health = rotation.health[key.id]
        assert health.status == KeyStatus.RATE_LIMITED
        assert health.rate_limit_until is not None
        cooldown = health.rate_limit_until - time.time()
        assert 295 <= cooldown <= 305  # ~300 seconds (5 minutes)
    
    @pytest.mark.asyncio
    async def test_auth_failure_marks_dead(self, rotation):
        """Test authentication failure marks key as DEAD"""
        key = await rotation.get_next_key()
        
        await rotation.report_failure(key.id, error_type="auth")
        
        health = rotation.health[key.id]
        assert health.status == KeyStatus.DEAD
    
    @pytest.mark.asyncio
    async def test_max_failures_marks_dead(self, rotation):
        """Test exceeding max_failures marks key as DEAD"""
        key = await rotation.get_next_key()
        
        # Fail 10 times (default max_failures)
        for _ in range(10):
            await rotation.report_failure(key.id)
        
        health = rotation.health[key.id]
        assert health.status == KeyStatus.DEAD


class TestKeyAvailability:
    """Test key availability logic"""
    
    def test_healthy_key_is_available(self, rotation):
        """Test that HEALTHY key is available"""
        health = rotation.health["key1"]
        health.status = KeyStatus.HEALTHY
        assert health.is_available() is True
    
    def test_dead_key_not_available(self, rotation):
        """Test that DEAD key is not available"""
        health = rotation.health["key1"]
        health.status = KeyStatus.DEAD
        assert health.is_available() is False
    
    def test_cooling_key_not_available(self, rotation):
        """Test that COOLING key is not available"""
        health = rotation.health["key1"]
        health.status = KeyStatus.COOLING
        health.cooldown_until = time.time() + 60
        assert health.is_available() is False
    
    def test_cooled_down_key_becomes_available(self, rotation):
        """Test that cooled down key becomes available"""
        health = rotation.health["key1"]
        health.status = KeyStatus.COOLING
        health.cooldown_until = time.time() - 1  # Already passed
        assert health.is_available() is True
    
    def test_time_until_available(self, rotation):
        """Test time_until_available calculation"""
        health = rotation.health["key1"]
        
        # HEALTHY - immediately available
        health.status = KeyStatus.HEALTHY
        assert health.time_until_available() == 0.0
        
        # COOLING - wait time
        health.status = KeyStatus.COOLING
        health.cooldown_until = time.time() + 60
        wait = health.time_until_available()
        assert 58 <= wait <= 62
        
        # DEAD - infinite wait
        health.status = KeyStatus.DEAD
        assert health.time_until_available() == float('inf')


class TestHealthMetrics:
    """Test health metrics and monitoring"""
    
    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, rotation):
        """Test success rate calculation"""
        key = await rotation.get_next_key()
        
        # 3 successes, 2 failures = 60% success rate
        await rotation.report_success(key.id)
        await rotation.report_success(key.id)
        await rotation.report_success(key.id)
        await rotation.report_failure(key.id)
        await rotation.report_failure(key.id)
        
        health = rotation.health[key.id]
        assert health.success_rate() == pytest.approx(0.6, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_alert_when_half_keys_unhealthy(self, rotation, caplog):
        """Test alert when >50% keys are unhealthy"""
        import logging
        caplog.set_level(logging.ERROR)
        
        # Fail 2 out of 3 keys (66% unhealthy)
        key1 = await rotation.get_next_key()
        await rotation.report_failure(key1.id)
        
        # Find second different key
        key2 = None
        for _ in range(10):
            k = await rotation.get_next_key()
            if k.id != key1.id:
                key2 = k
                break
        
        if key2:
            await rotation.report_failure(key2.id)
        
        # Check for alert in logs
        assert any("ALERT" in record.message for record in caplog.records)
        assert any("unhealthy" in record.message for record in caplog.records)


class TestMetrics:
    """Test metrics collection"""
    
    @pytest.mark.asyncio
    async def test_get_metrics_structure(self, rotation):
        """Test metrics structure"""
        metrics = rotation.get_metrics()
        
        assert "total_keys" in metrics
        assert "healthy_keys" in metrics
        assert "cooling_keys" in metrics
        assert "rate_limited_keys" in metrics
        assert "dead_keys" in metrics
        assert "avg_success_rate" in metrics
        assert "gini_coefficient" in metrics
        assert "per_key_stats" in metrics
    
    @pytest.mark.asyncio
    async def test_gini_coefficient_perfect_distribution(self, rotation):
        """Test Gini coefficient for perfect distribution"""
        # Use all keys equally
        for _ in range(10):
            for key_id in rotation.keys:
                await rotation.report_success(key_id)
        
        metrics = rotation.get_metrics()
        gini = metrics["gini_coefficient"]
        
        # Perfect distribution should have Gini ~0
        assert gini < 0.1
    
    @pytest.mark.asyncio
    async def test_gini_coefficient_uneven_distribution(self, rotation):
        """Test Gini coefficient for uneven distribution"""
        # Use only one key
        for _ in range(10):
            await rotation.report_success("key1")
        
        metrics = rotation.get_metrics()
        gini = metrics["gini_coefficient"]
        
        # Uneven distribution should have higher Gini
        assert gini > 0.5


class TestManualReset:
    """Test manual key reset"""
    
    @pytest.mark.asyncio
    async def test_reset_key(self, rotation):
        """Test manual key reset"""
        # Fail a key
        await rotation.report_failure("key1")
        assert rotation.health["key1"].status == KeyStatus.COOLING
        
        # Reset it
        rotation.reset_key("key1")
        
        health = rotation.health["key1"]
        assert health.status == KeyStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.cooldown_until is None
    
    def test_reset_nonexistent_key(self, rotation):
        """Test reset of nonexistent key raises error"""
        with pytest.raises(KeyError, match="Key 'nonexistent' not found"):
            rotation.reset_key("nonexistent")


class TestFailover:
    """Test automatic failover scenarios"""
    
    @pytest.mark.asyncio
    async def test_failover_to_healthy_keys(self, rotation):
        """Test automatic failover to healthy keys"""
        # Fail key1
        await rotation.report_failure("key1")
        
        # Next call should get key2 or key3 (not key1)
        key = await rotation.get_next_key()
        assert key.id != "key1"
    
    @pytest.mark.asyncio
    async def test_recovery_after_cooldown(self, rotation):
        """Test key recovery after cooldown expires"""
        # This test would take too long with real cooldowns
        # Instead, manually manipulate cooldown time
        health = rotation.health["key1"]
        health.status = KeyStatus.COOLING
        health.cooldown_until = time.time() - 1  # Already expired
        
        # Should be available again
        assert health.is_available() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
