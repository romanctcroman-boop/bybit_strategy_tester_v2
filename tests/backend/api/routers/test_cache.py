"""
Comprehensive tests for cache router endpoints.

Tests cover:
- Cache statistics retrieval
- Cache clearing operations
- Pattern-based cache deletion
- Cache health monitoring
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.routers.cache import get_cache_manager_dependency
import backend.api.routers.cache  # Force module import for coverage


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def cache_manager_stub():
    """Override cache manager dependency with a fully-configured stub."""
    manager = MagicMock()

    manager.l1_cache = MagicMock()
    manager.l1_cache.get_stats = AsyncMock(return_value={
        "size": 150,
        "max_size": 1000,
        "hits": 5420,
        "misses": 234,
        "hit_rate": 0.958,
        "evictions": 45,
        "expired": 12,
    })
    manager.l1_cache.clear = AsyncMock()

    manager.redis_client = MagicMock()
    manager.redis_client.set = AsyncMock()
    manager.redis_client.get = AsyncMock(return_value="ok")

    manager._stats = {
        'l1_hits': 5420,
        'l2_hits': 1234,
        'misses': 234,
        'computes': 234,
        'compute_errors': 0,
        'l2_errors': 0,
    }

    manager.delete_pattern = AsyncMock(return_value=42)

    async def _provider():
        return manager

    def override_dependency():
        return _provider

    app.dependency_overrides[get_cache_manager_dependency] = override_dependency
    try:
        yield manager
    finally:
        app.dependency_overrides.pop(get_cache_manager_dependency, None)


# ============================================================================
# Test Class: Cache Statistics
# ============================================================================

class TestGetCacheStats:
    """Tests for GET /api/v1/cache/stats endpoint"""
    
    def test_get_stats_success(self, client, cache_manager_stub):
        """Should return comprehensive cache statistics"""
        response = client.get("/api/v1/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "l1_cache" in data
        assert "l2_cache" in data
        assert "overall" in data
        assert "status" in data
        
        # Verify L1 stats
        assert data["l1_cache"]["size"] == 150
        assert data["l1_cache"]["max_size"] == 1000
        assert data["l1_cache"]["hits"] == 5420
        assert data["l1_cache"]["misses"] == 234
        assert data["l1_cache"]["hit_rate"] == 0.958
        
        # Verify L2 stats
        assert data["l2_cache"]["hits"] == 1234
        assert data["l2_cache"]["errors"] == 0
        
        # Verify overall stats
        assert data["overall"]["total_hits"] == 6654  # 5420 + 1234
        assert data["overall"]["total_misses"] == 234
        assert data["overall"]["hit_rate"] == 0.966  # Rounded to 3 decimals
        assert data["overall"]["computes"] == 234
        assert data["overall"]["compute_errors"] == 0
        
        # Verify status
        assert data["status"] == "healthy"
    
    def test_get_stats_degraded_status(self, client, cache_manager_stub):
        """Should return degraded status when L2 has errors"""
        # Simulate L2 errors
        cache_manager_stub._stats['l2_errors'] = 5
        
        response = client.get("/api/v1/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["l2_cache"]["errors"] == 5
    
    def test_get_stats_zero_requests(self, client, cache_manager_stub):
        """Should handle zero requests (avoid division by zero)"""
        # Simulate empty cache
        cache_manager_stub._stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'misses': 0,
            'computes': 0,
            'compute_errors': 0,
            'l2_errors': 0
        }
        
        response = client.get("/api/v1/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall"]["hit_rate"] == 0.0
        assert data["overall"]["total_hits"] == 0
        assert data["overall"]["total_misses"] == 0
    
    def test_get_stats_error_handling(self, client):
        """Should return 500 when cache manager fails"""
        async def _failing_provider():
            raise Exception("Cache unavailable")

        app.dependency_overrides[get_cache_manager_dependency] = lambda: _failing_provider
        try:
            response = client.get("/api/v1/cache/stats")
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

        assert response.status_code == 500
        assert "Failed to retrieve cache statistics" in response.json()["detail"]


# ============================================================================
# Test Class: Cache Clear
# ============================================================================

class TestClearCache:
    """Tests for POST /api/v1/cache/clear endpoint"""
    
    def test_clear_cache_success(self, client, cache_manager_stub):
        """Should clear L1 cache successfully"""
        response = client.post("/api/v1/cache/clear")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["message"] == "Cache cleared successfully"
        assert data["cleared"] == "L1 (memory) cache"
        
        # Verify L1 cache clear was called
        cache_manager_stub.l1_cache.clear.assert_called_once()
    
    def test_clear_cache_without_redis(self, client, cache_manager_stub):
        """Should clear L1 cache even when Redis is unavailable"""
        # Simulate no Redis client
        cache_manager_stub.redis_client = None
        
        response = client.post("/api/v1/cache/clear")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify L1 cache clear was still called
        cache_manager_stub.l1_cache.clear.assert_called_once()
    
    def test_clear_cache_error_handling(self, client, cache_manager_stub):
        """Should return 500 when cache clear fails"""
        # Simulate cache clear failure
        cache_manager_stub.l1_cache.clear.side_effect = Exception("Clear failed")
        
        response = client.post("/api/v1/cache/clear")
        
        assert response.status_code == 500
        assert "Failed to clear cache" in response.json()["detail"]


# ============================================================================
# Test Class: Delete Cache Pattern
# ============================================================================

class TestDeleteCachePattern:
    """Tests for DELETE /api/v1/cache/keys/{key_pattern} endpoint"""
    
    def test_delete_pattern_success(self, client, cache_manager_stub):
        """Should delete cache keys matching pattern"""
        response = client.delete("/api/v1/cache/keys/backtest:*")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["pattern"] == "backtest:*"
        assert data["deleted_count"] == 42
        
        # Verify delete_pattern was called with correct argument
        cache_manager_stub.delete_pattern.assert_called_once_with("backtest:*")
    
    def test_delete_pattern_user_keys(self, client, cache_manager_stub):
        """Should handle user-specific pattern deletion"""
        cache_manager_stub.delete_pattern.return_value = 15
        
        response = client.delete("/api/v1/cache/keys/user:123:*")
        
        assert response.status_code == 200
        data = response.json()
        assert data["pattern"] == "user:123:*"
        assert data["deleted_count"] == 15
    
    def test_delete_pattern_zero_matches(self, client, cache_manager_stub):
        """Should return zero when no keys match pattern"""
        cache_manager_stub.delete_pattern.return_value = 0
        
        response = client.delete("/api/v1/cache/keys/nonexistent:*")
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
    
    def test_delete_pattern_error_handling(self, client, cache_manager_stub):
        """Should return 500 when deletion fails"""
        cache_manager_stub.delete_pattern.side_effect = Exception("Redis connection lost")
        
        response = client.delete("/api/v1/cache/keys/test:*")
        
        assert response.status_code == 500
        assert "Failed to delete cache keys" in response.json()["detail"]
    
    def test_delete_pattern_special_characters(self, client, cache_manager_stub):
        """Should handle patterns with special characters"""
        cache_manager_stub.delete_pattern.return_value = 3
        
        response = client.delete("/api/v1/cache/keys/strategy:sr-rsi:*")
        
        assert response.status_code == 200
        data = response.json()
        assert data["pattern"] == "strategy:sr-rsi:*"


# ============================================================================
# Test Class: Cache Health Check
# ============================================================================

class TestCacheHealthCheck:
    """Tests for GET /api/v1/cache/health endpoint"""
    
    def test_health_check_healthy(self, client, cache_manager_stub):
        """Should return healthy status when all systems operational"""
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["l1_cache"]["status"] == "healthy"
        assert data["l1_cache"]["available"] is True
        assert data["l2_cache"]["status"] == "healthy"
        assert data["l2_cache"]["available"] is True
        assert data["l2_cache"]["error_count"] == 0
    
    def test_health_check_degraded_l2_errors(self, client, cache_manager_stub):
        """Should return degraded status when L2 has errors"""
        # Simulate L2 errors
        cache_manager_stub._stats['l2_errors'] = 15
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["l1_cache"]["status"] == "healthy"
        assert data["l2_cache"]["status"] == "degraded"
        assert data["l2_cache"]["error_count"] == 15
    
    def test_health_check_degraded_redis_unavailable(self, client, cache_manager_stub):
        """Should return degraded when Redis is unavailable"""
        # Simulate Redis connection failure
        cache_manager_stub.redis_client.set.side_effect = Exception("Redis timeout")
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["l2_cache"]["available"] is False
    
    def test_health_check_redis_get_failure(self, client, cache_manager_stub):
        """Should handle Redis get() exception (line 199 coverage)"""
        # Simulate Redis get() failure after set() success
        cache_manager_stub.redis_client.set.return_value = None  # set() succeeds
        cache_manager_stub.redis_client.get.side_effect = Exception("Get failed")
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should mark Redis as unavailable (line 199: redis_available = False)
        assert data["status"] == "degraded"
        assert data["l2_cache"]["available"] is False
    
    def test_health_check_no_redis_client(self, client, cache_manager_stub):
        """Should handle missing Redis client gracefully"""
        # Simulate no Redis client configured
        cache_manager_stub.redis_client = None
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["l2_cache"]["available"] is False
    
    def test_health_check_redis_ping_failure(self, client, cache_manager_stub):
        """Should detect Redis ping failures"""
        # Simulate Redis ping returning wrong value
        cache_manager_stub.redis_client.get.return_value = "wrong"
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still show available=False because test failed
        assert data["l2_cache"]["available"] is False
    
    def test_health_check_critical_exception(self, client):
        """Should return critical status on exception"""

        async def _failing_provider():
            raise Exception("Critical failure")

        app.dependency_overrides[get_cache_manager_dependency] = lambda: _failing_provider
        try:
            response = client.get("/api/v1/cache/health")
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)
        
        # Note: Health check catches exceptions and returns 200 with critical status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert "Critical failure" in data["error"]
    
    def test_health_check_boundary_l2_errors(self, client, cache_manager_stub):
        """Should handle boundary condition (exactly 10 L2 errors)"""
        # Exactly 10 errors should still be healthy
        cache_manager_stub._stats['l2_errors'] = 10
        
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["l2_cache"]["status"] == "healthy"
        
        # 11 errors should be degraded
        cache_manager_stub._stats['l2_errors'] = 11
        response = client.get("/api/v1/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["l2_cache"]["status"] == "degraded"


# ============================================================================
# Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Integration tests combining multiple cache operations"""
    
    def test_stats_after_clear(self, client, cache_manager_stub):
        """Should show updated stats after cache clear"""
        # Get initial stats
        response1 = client.get("/api/v1/cache/stats")
        assert response1.status_code == 200
        
        # Clear cache
        response2 = client.post("/api/v1/cache/clear")
        assert response2.status_code == 200
        
        # Verify clear was called
        cache_manager_stub.l1_cache.clear.assert_called_once()
    
    def test_health_check_before_stats(self, client, cache_manager_stub):
        """Should check health before retrieving stats"""
        # Health check
        response1 = client.get("/api/v1/cache/health")
        assert response1.status_code == 200
        assert response1.json()["status"] == "healthy"
        
        # Stats retrieval
        response2 = client.get("/api/v1/cache/stats")
        assert response2.status_code == 200
    
    def test_delete_pattern_then_stats(self, client, cache_manager_stub):
        """Should show consistent state after pattern deletion"""
        # Delete pattern
        response1 = client.delete("/api/v1/cache/keys/test:*")
        assert response1.status_code == 200
        assert response1.json()["deleted_count"] == 42
        
        # Get stats
        response2 = client.get("/api/v1/cache/stats")
        assert response2.status_code == 200
