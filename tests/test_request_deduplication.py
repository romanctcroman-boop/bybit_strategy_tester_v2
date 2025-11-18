"""
Tests for Request Deduplication System

Comprehensive test suite covering:
- Basic deduplication (identical concurrent requests)
- Key generation (endpoint, method, params, body)
- Request lifecycle (pending, completed, failed)
- Error propagation to all waiters
- Timeout handling
- Cancellation
- Cleanup (stale requests, automatic cleanup task)
- Metrics and statistics
- Middleware integration
- Edge cases

Phase 3, Day 19-20
Target: 30+ tests, >90% coverage
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from reliability.request_deduplication import (
    RequestDeduplicator,
    DeduplicationConfig,
    DeduplicationStats,
    RequestStatus,
    RequestState,
    DeduplicationMiddleware
)


@pytest.fixture
def dedup_config():
    """Default config for tests"""
    return DeduplicationConfig(
        max_pending_requests=100,
        request_ttl=5,
        cleanup_interval=10,
        enable_metrics=True
    )


@pytest.fixture
def deduplicator(dedup_config):
    """Request deduplicator instance"""
    return RequestDeduplicator(config=dedup_config, enable_metrics=True)


# ============================================================================
# Test Key Generation
# ============================================================================

class TestKeyGeneration:
    """Test unique key generation"""
    
    def test_same_request_same_key(self, deduplicator):
        """Should generate same key for identical requests"""
        key1 = deduplicator.generate_key(
            endpoint="/api/users",
            method="GET",
            params={"id": 123}
        )
        key2 = deduplicator.generate_key(
            endpoint="/api/users",
            method="GET",
            params={"id": 123}
        )
        
        assert key1 == key2
    
    def test_different_endpoint_different_key(self, deduplicator):
        """Should generate different key for different endpoints"""
        key1 = deduplicator.generate_key(endpoint="/api/users")
        key2 = deduplicator.generate_key(endpoint="/api/posts")
        
        assert key1 != key2
    
    def test_different_method_different_key(self, deduplicator):
        """Should generate different key for different methods"""
        key1 = deduplicator.generate_key(endpoint="/api/users", method="GET")
        key2 = deduplicator.generate_key(endpoint="/api/users", method="POST")
        
        assert key1 != key2
    
    def test_different_params_different_key(self, deduplicator):
        """Should generate different key for different params"""
        key1 = deduplicator.generate_key(
            endpoint="/api/users",
            params={"id": 123}
        )
        key2 = deduplicator.generate_key(
            endpoint="/api/users",
            params={"id": 456}
        )
        
        assert key1 != key2
    
    def test_different_body_different_key(self, deduplicator):
        """Should generate different key for different body"""
        key1 = deduplicator.generate_key(
            endpoint="/api/users",
            method="POST",
            body={"name": "Alice"}
        )
        key2 = deduplicator.generate_key(
            endpoint="/api/users",
            method="POST",
            body={"name": "Bob"}
        )
        
        assert key1 != key2
    
    def test_param_order_irrelevant(self, deduplicator):
        """Should generate same key regardless of param order"""
        key1 = deduplicator.generate_key(
            endpoint="/api/users",
            params={"id": 123, "name": "Alice"}
        )
        key2 = deduplicator.generate_key(
            endpoint="/api/users",
            params={"name": "Alice", "id": 123}
        )
        
        assert key1 == key2
    
    def test_hash_algorithm_sha256(self, dedup_config):
        """Should support SHA256 hashing"""
        dedup_config.hash_algorithm = "sha256"
        deduplicator = RequestDeduplicator(config=dedup_config)
        
        key = deduplicator.generate_key(endpoint="/api/test")
        
        # SHA256 produces 64 character hex string
        assert len(key) == 64


# ============================================================================
# Test Basic Deduplication
# ============================================================================

class TestBasicDeduplication:
    """Test basic request deduplication"""
    
    @pytest.mark.asyncio
    async def test_single_request_executes(self, deduplicator):
        """Should execute single request normally"""
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            return "result"
        
        result = await deduplicator.deduplicate("key1", fetch)
        
        assert result == "result"
        assert call_count == 1
        assert deduplicator.stats.unique_requests == 1
        assert deduplicator.stats.deduplicated_requests == 0
    
    @pytest.mark.asyncio
    async def test_duplicate_requests_coalesced(self, deduplicator):
        """Should coalesce duplicate concurrent requests"""
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow request
            return "result"
        
        # Launch 5 concurrent identical requests
        results = await asyncio.gather(
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch)
        )
        
        # All should get same result
        assert all(r == "result" for r in results)
        
        # Should only execute once
        assert call_count == 1
        
        # Stats
        assert deduplicator.stats.unique_requests == 1
        assert deduplicator.stats.deduplicated_requests == 4
        assert deduplicator.stats.total_requests == 5
    
    @pytest.mark.asyncio
    async def test_different_keys_execute_separately(self, deduplicator):
        """Should execute different keys separately"""
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        results = await asyncio.gather(
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key2", fetch),
            deduplicator.deduplicate("key3", fetch)
        )
        
        # Should execute all 3 times
        assert call_count == 3
        assert len(set(results)) == 3  # All different results
    
    @pytest.mark.asyncio
    async def test_sync_fetch_function(self, deduplicator):
        """Should work with synchronous fetch function"""
        def sync_fetch():
            return "sync_result"
        
        result = await deduplicator.deduplicate("key1", sync_fetch)
        
        assert result == "sync_result"


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error propagation and handling"""
    
    @pytest.mark.asyncio
    async def test_error_propagated_to_all_waiters(self, deduplicator):
        """Should propagate error to all waiting requests"""
        async def fetch_error():
            await asyncio.sleep(0.05)
            raise ValueError("Test error")
        
        # Launch 3 concurrent requests
        tasks = [
            deduplicator.deduplicate("key1", fetch_error),
            deduplicator.deduplicate("key1", fetch_error),
            deduplicator.deduplicate("key1", fetch_error)
        ]
        
        # All should receive the same error
        with pytest.raises(ValueError, match="Test error"):
            await asyncio.gather(*tasks)
        
        assert deduplicator.stats.failed_requests == 1
    
    @pytest.mark.asyncio
    async def test_error_does_not_affect_other_keys(self, deduplicator):
        """Error in one key should not affect others"""
        async def fetch_error():
            raise ValueError("Error")
        
        async def fetch_success():
            return "success"
        
        # Launch mixed requests
        with pytest.raises(ValueError):
            await deduplicator.deduplicate("key_error", fetch_error)
        
        result = await deduplicator.deduplicate("key_success", fetch_success)
        
        assert result == "success"


# ============================================================================
# Test Timeout Handling
# ============================================================================

class TestTimeoutHandling:
    """Test request timeout"""
    
    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, deduplicator):
        """Should raise TimeoutError when request times out"""
        async def slow_fetch():
            await asyncio.sleep(10)  # Very slow
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await deduplicator.deduplicate("key1", slow_fetch, timeout=0.1)
        
        assert deduplicator.stats.timeouts == 1
    
    @pytest.mark.asyncio
    async def test_timeout_affects_all_waiters(self, deduplicator):
        """Timeout should affect all waiting requests"""
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        tasks = [
            deduplicator.deduplicate("key1", slow_fetch, timeout=0.1),
            deduplicator.deduplicate("key1", slow_fetch, timeout=0.1),
            deduplicator.deduplicate("key1", slow_fetch, timeout=0.1)
        ]
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.gather(*tasks)
    
    @pytest.mark.asyncio
    async def test_default_timeout_from_config(self, deduplicator):
        """Should use default timeout from config"""
        deduplicator.config.request_ttl = 0.1
        
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await deduplicator.deduplicate("key1", slow_fetch)


# ============================================================================
# Test Cancellation
# ============================================================================

class TestCancellation:
    """Test request cancellation"""
    
    @pytest.mark.asyncio
    async def test_cancel_pending_request(self, deduplicator):
        """Should cancel pending request"""
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        # Start request
        task = asyncio.create_task(
            deduplicator.deduplicate("key1", slow_fetch)
        )
        
        await asyncio.sleep(0.01)  # Let it start
        
        # Cancel
        success = await deduplicator.cancel_request("key1")
        
        assert success is True
        assert deduplicator.stats.cancelled_requests == 1
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_request(self, deduplicator):
        """Should return False when cancelling non-existent request"""
        success = await deduplicator.cancel_request("nonexistent")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_request(self, deduplicator):
        """Should not cancel already completed request"""
        async def fetch():
            return "result"
        
        result = await deduplicator.deduplicate("key1", fetch)
        
        # Try to cancel after completion
        await asyncio.sleep(0.01)
        success = await deduplicator.cancel_request("key1")
        
        assert success is False


# ============================================================================
# Test Cleanup
# ============================================================================

class TestCleanup:
    """Test request cleanup"""
    
    @pytest.mark.asyncio
    async def test_completed_request_cleanup(self, deduplicator):
        """Should clean up completed requests"""
        async def fetch():
            return "result"
        
        await deduplicator.deduplicate("key1", fetch)
        
        # Wait for cleanup
        await asyncio.sleep(1.1)
        
        active = deduplicator.get_active_requests()
        assert "key1" not in active
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_requests(self, deduplicator):
        """Should clean up stale/timed-out requests"""
        deduplicator.config.request_ttl = 0.1
        
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        # Start request (will be stale)
        task = asyncio.create_task(
            deduplicator.deduplicate("key1", slow_fetch, timeout=10)
        )
        
        await asyncio.sleep(0.15)  # Exceed TTL
        
        # Run cleanup
        await deduplicator.cleanup_stale_requests()
        
        active = deduplicator.get_active_requests()
        assert "key1" not in active
    
    @pytest.mark.asyncio
    async def test_cleanup_task_runs_periodically(self, deduplicator):
        """Should run cleanup task periodically"""
        deduplicator.config.cleanup_interval = 0.1
        
        await deduplicator.start_cleanup_task()
        
        # Task should be running
        assert deduplicator._cleanup_task is not None
        
        await asyncio.sleep(0.2)
        
        # Stop task
        await deduplicator.stop_cleanup_task()
        
        assert deduplicator._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_clear_all_requests(self, deduplicator):
        """Should clear all pending requests"""
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        # Start multiple requests
        tasks = [
            asyncio.create_task(deduplicator.deduplicate(f"key{i}", slow_fetch))
            for i in range(5)
        ]
        
        await asyncio.sleep(0.01)
        
        # Clear all
        await deduplicator.clear()
        
        active = deduplicator.get_active_requests()
        assert len(active) == 0


# ============================================================================
# Test Metrics
# ============================================================================

class TestMetrics:
    """Test metrics and statistics"""
    
    @pytest.mark.asyncio
    async def test_deduplication_rate_calculation(self, deduplicator):
        """Should calculate deduplication rate correctly"""
        async def fetch():
            await asyncio.sleep(0.05)
            return "result"
        
        # 1 unique + 4 duplicates = 5 total, 4 deduplicated
        await asyncio.gather(
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch),
            deduplicator.deduplicate("key1", fetch)
        )
        
        stats = deduplicator.get_stats()
        
        assert stats.total_requests == 5
        assert stats.deduplicated_requests == 4
        assert stats.deduplication_rate == pytest.approx(4/5, 0.01)
    
    @pytest.mark.asyncio
    async def test_metrics_disabled(self, dedup_config):
        """Should not track metrics when disabled"""
        dedup = RequestDeduplicator(config=dedup_config, enable_metrics=False)
        
        async def fetch():
            return "result"
        
        await dedup.deduplicate("key1", fetch)
        
        stats = dedup.get_stats()
        
        assert stats.total_requests == 0
        assert stats.unique_requests == 0
    
    @pytest.mark.asyncio
    async def test_active_request_count(self, deduplicator):
        """Should track active request count"""
        async def slow_fetch():
            await asyncio.sleep(0.2)
            return "result"
        
        # Start 3 requests
        tasks = [
            asyncio.create_task(deduplicator.deduplicate(f"key{i}", slow_fetch))
            for i in range(3)
        ]
        
        await asyncio.sleep(0.01)
        
        stats = deduplicator.get_stats()
        assert stats.active_requests == 3
        
        # Wait for completion
        await asyncio.gather(*tasks)
        
        # Wait for cleanup (1s delay in _cleanup_request)
        await asyncio.sleep(1.1)
        
        stats = deduplicator.get_stats()
        assert stats.active_requests == 0


# ============================================================================
# Test Middleware
# ============================================================================

class TestMiddleware:
    """Test deduplication middleware"""
    
    @pytest.mark.asyncio
    async def test_middleware_deduplicates_requests(self, deduplicator):
        """Middleware should deduplicate requests"""
        middleware = DeduplicationMiddleware(deduplicator)
        
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return "result"
        
        # Launch 3 identical requests through middleware
        results = await asyncio.gather(
            middleware(
                endpoint="/api/users",
                method="GET",
                fetch_func=fetch,
                params={"id": 123}
            ),
            middleware(
                endpoint="/api/users",
                method="GET",
                fetch_func=fetch,
                params={"id": 123}
            ),
            middleware(
                endpoint="/api/users",
                method="GET",
                fetch_func=fetch,
                params={"id": 123}
            )
        )
        
        # Should only execute once
        assert call_count == 1
        assert all(r == "result" for r in results)
    
    @pytest.mark.asyncio
    async def test_middleware_with_custom_key_generator(self, deduplicator):
        """Should support custom key generator"""
        def custom_key_gen(**kwargs):
            return "custom_key"
        
        middleware = DeduplicationMiddleware(
            deduplicator=deduplicator,
            key_generator=custom_key_gen
        )
        
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            return "result"
        
        # Different endpoints but same custom key
        await asyncio.gather(
            middleware(
                endpoint="/api/users",
                method="GET",
                fetch_func=fetch
            ),
            middleware(
                endpoint="/api/posts",
                method="GET",
                fetch_func=fetch
            )
        )
        
        # Should deduplicate despite different endpoints
        assert call_count == 1


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_empty_params_and_body(self, deduplicator):
        """Should handle empty params and body"""
        key = deduplicator.generate_key(
            endpoint="/api/test",
            params={},
            body={}
        )
        
        assert isinstance(key, str)
        assert len(key) > 0
    
    @pytest.mark.asyncio
    async def test_none_params_and_body(self, deduplicator):
        """Should handle None params and body"""
        key = deduplicator.generate_key(
            endpoint="/api/test",
            params=None,
            body=None
        )
        
        assert isinstance(key, str)
        assert len(key) > 0
    
    @pytest.mark.asyncio
    async def test_complex_nested_params(self, deduplicator):
        """Should handle complex nested params"""
        key = deduplicator.generate_key(
            endpoint="/api/test",
            params={
                "nested": {
                    "level1": {
                        "level2": [1, 2, 3]
                    }
                }
            }
        )
        
        assert isinstance(key, str)
    
    @pytest.mark.asyncio
    async def test_fetch_returns_none(self, deduplicator):
        """Should handle fetch function returning None"""
        async def fetch_none():
            return None
        
        result = await deduplicator.deduplicate("key1", fetch_none)
        
        assert result is None
        assert deduplicator.stats.completed_requests == 1
    
    @pytest.mark.asyncio
    async def test_zero_deduplication_rate(self, deduplicator):
        """Should handle zero deduplication rate (all unique)"""
        async def fetch():
            return "result"
        
        # All different keys
        await deduplicator.deduplicate("key1", fetch)
        await deduplicator.deduplicate("key2", fetch)
        await deduplicator.deduplicate("key3", fetch)
        
        stats = deduplicator.get_stats()
        
        assert stats.deduplication_rate == 0.0
    
    @pytest.mark.asyncio
    async def test_sequential_requests_not_deduplicated(self, deduplicator):
        """Sequential requests should not be deduplicated"""
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            return "result"
        
        # Execute sequentially (not concurrent)
        await deduplicator.deduplicate("key1", fetch)
        await asyncio.sleep(1.1)  # Wait for cleanup
        await deduplicator.deduplicate("key1", fetch)
        
        # Should execute twice
        assert call_count == 2


# ============================================================================
# Test Request State
# ============================================================================

class TestRequestState:
    """Test RequestState lifecycle"""
    
    @pytest.mark.asyncio
    async def test_get_active_requests(self, deduplicator):
        """Should get all active requests"""
        async def slow_fetch():
            await asyncio.sleep(0.2)
            return "result"
        
        # Start requests
        tasks = [
            asyncio.create_task(deduplicator.deduplicate(f"key{i}", slow_fetch))
            for i in range(3)
        ]
        
        await asyncio.sleep(0.01)
        
        active = deduplicator.get_active_requests()
        
        assert len(active) == 3
        assert all(isinstance(state, RequestState) for state in active.values())
        
        await asyncio.gather(*tasks)
    
    @pytest.mark.asyncio
    async def test_request_state_attributes(self, deduplicator):
        """Should track request state attributes"""
        async def fetch():
            await asyncio.sleep(0.05)
            return "result"
        
        # Start request
        task = asyncio.create_task(deduplicator.deduplicate("key1", fetch))
        
        await asyncio.sleep(0.01)
        
        active = deduplicator.get_active_requests()
        state = active.get("key1")
        
        assert state is not None
        assert state.status == RequestStatus.PENDING
        assert state.waiter_count >= 1
        assert state.created_at > 0
        
        await task


# ============================================================================
# Test Configuration
# ============================================================================

class TestConfiguration:
    """Test configuration options"""
    
    @pytest.mark.asyncio
    async def test_custom_cleanup_interval(self):
        """Should use custom cleanup interval"""
        config = DeduplicationConfig(cleanup_interval=0.05)
        dedup = RequestDeduplicator(config=config)
        
        assert dedup.config.cleanup_interval == 0.05
    
    @pytest.mark.asyncio
    async def test_custom_request_ttl(self):
        """Should use custom request TTL"""
        config = DeduplicationConfig(request_ttl=10)
        dedup = RequestDeduplicator(config=config)
        
        assert dedup.config.request_ttl == 10
    
    @pytest.mark.asyncio
    async def test_max_pending_requests_config(self):
        """Should use max_pending_requests from config"""
        config = DeduplicationConfig(max_pending_requests=500)
        dedup = RequestDeduplicator(config=config)
        
        assert dedup.config.max_pending_requests == 500
    
    @pytest.mark.asyncio
    async def test_zero_total_requests_rate(self):
        """Should handle zero total requests for rate calculation"""
        stats = DeduplicationStats()
        
        # No requests yet
        assert stats.deduplication_rate == 0.0


# ============================================================================
# Test Additional Coverage
# ============================================================================

class TestAdditionalCoverage:
    """Tests for additional coverage"""
    
    @pytest.mark.asyncio
    async def test_cleanup_task_already_running(self, deduplicator):
        """Should warn when cleanup task already running"""
        await deduplicator.start_cleanup_task()
        
        # Try to start again
        await deduplicator.start_cleanup_task()
        
        # Should still have only one task
        assert deduplicator._cleanup_task is not None
        
        await deduplicator.stop_cleanup_task()
    
    @pytest.mark.asyncio
    async def test_stop_cleanup_task_when_not_running(self, deduplicator):
        """Should handle stopping non-running cleanup task"""
        # Try to stop when not running
        await deduplicator.stop_cleanup_task()
        
        # Should not crash
        assert deduplicator._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_middleware_with_timeout(self, deduplicator):
        """Middleware should support custom timeout"""
        middleware = DeduplicationMiddleware(deduplicator)
        
        async def slow_fetch():
            await asyncio.sleep(10)
            return "result"
        
        with pytest.raises(asyncio.TimeoutError):
            await middleware(
                endpoint="/api/test",
                method="GET",
                fetch_func=slow_fetch,
                timeout=0.1
            )
    
    @pytest.mark.asyncio
    async def test_middleware_with_body(self, deduplicator):
        """Middleware should handle request body"""
        middleware = DeduplicationMiddleware(deduplicator)
        
        call_count = 0
        
        async def fetch():
            nonlocal call_count
            call_count += 1
            return "result"
        
        # Two identical POST requests with body
        await asyncio.gather(
            middleware(
                endpoint="/api/users",
                method="POST",
                fetch_func=fetch,
                body={"name": "Alice"}
            ),
            middleware(
                endpoint="/api/users",
                method="POST",
                fetch_func=fetch,
                body={"name": "Alice"}
            )
        )
        
        # Should deduplicate
        assert call_count == 1
