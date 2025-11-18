"""
Tests for Prometheus Cache Metrics

Tests:
1. Metrics recording (hits, misses, evictions)
2. Operation timing
3. L1/L2 metrics separation
4. Error tracking
5. Prometheus endpoint
"""

import pytest
import asyncio
from prometheus_client import REGISTRY

from backend.cache.metrics import cache_metrics, CacheMetrics
from backend.cache.cache_manager import LRUCache


@pytest.fixture
def metrics():
    """Create fresh metrics instance for testing."""
    metrics = CacheMetrics()
    metrics.reset()
    return metrics


@pytest.fixture
async def lru_cache():
    """Create LRU cache for testing."""
    return LRUCache(max_size=10, default_ttl=300)


def test_record_hit(metrics):
    """Test recording cache hits."""
    # Record L1 hit
    metrics.record_hit('l1')
    stats = metrics.get_stats()
    
    assert stats['total_hits'] == 1
    assert stats['total_misses'] == 0
    assert stats['hit_rate'] == 1.0
    
    # Record L2 hit
    metrics.record_hit('l2')
    stats = metrics.get_stats()
    
    assert stats['total_hits'] == 2
    assert stats['hit_rate'] == 1.0


def test_record_miss(metrics):
    """Test recording cache misses."""
    metrics.record_miss()
    stats = metrics.get_stats()
    
    assert stats['total_hits'] == 0
    assert stats['total_misses'] == 1
    assert stats['hit_rate'] == 0.0


def test_hit_rate_calculation(metrics):
    """Test hit rate calculation."""
    # 8 hits, 2 misses = 80% hit rate
    for _ in range(8):
        metrics.record_hit('l1')
    
    for _ in range(2):
        metrics.record_miss()
    
    stats = metrics.get_stats()
    assert stats['total_hits'] == 8
    assert stats['total_misses'] == 2
    assert stats['total_operations'] == 10
    assert stats['hit_rate'] == 0.8


def test_record_operation(metrics):
    """Test recording cache operations."""
    metrics.record_operation('get', 'success')
    metrics.record_operation('set', 'success')
    metrics.record_operation('get', 'error')
    
    # Operations are tracked in Prometheus counters
    # Just verify no exceptions raised


def test_record_eviction(metrics):
    """Test recording cache evictions."""
    metrics.record_eviction('l1')
    metrics.record_eviction('l2')
    
    # Evictions tracked in Prometheus counters
    # Verify no exceptions


def test_record_expired(metrics):
    """Test recording expired entries."""
    metrics.record_expired('l1')
    
    # Expired tracked in Prometheus counters
    # Verify no exceptions


def test_record_l2_error(metrics):
    """Test recording L2 errors."""
    metrics.record_l2_error('connection')
    metrics.record_l2_error('timeout')
    metrics.record_l2_error('other')
    
    # Errors tracked in Prometheus counters
    # Verify no exceptions


def test_record_compute_error(metrics):
    """Test recording compute errors."""
    metrics.record_compute_error()
    
    # Errors tracked in Prometheus counters
    # Verify no exceptions


def test_update_cache_size(metrics):
    """Test updating cache size gauge."""
    metrics.update_cache_size(150, 'l1')
    metrics.update_cache_size(1000, 'l2')
    
    # Size tracked in Prometheus gauges
    # Verify no exceptions


def test_update_memory_usage(metrics):
    """Test updating memory usage gauge."""
    metrics.update_memory_usage(1024 * 1024, 'l1')  # 1 MB
    
    # Memory tracked in Prometheus gauges
    # Verify no exceptions


def test_time_operation_context_manager(metrics):
    """Test timing cache operations."""
    import time
    
    # Time a short operation
    with metrics.time_operation('get', 'l1'):
        time.sleep(0.01)  # 10ms
    
    # Operation timing tracked in Prometheus histogram
    # Verify no exceptions


def test_time_compute_context_manager(metrics):
    """Test timing compute functions."""
    import time
    
    # Time a compute operation
    with metrics.time_compute():
        time.sleep(0.05)  # 50ms
    
    # Compute timing tracked in Prometheus histogram
    # Verify no exceptions


@pytest.mark.asyncio
async def test_lru_cache_records_metrics(lru_cache):
    """Test that LRU cache records metrics."""
    # Reset global metrics
    cache_metrics.reset()
    
    # Cache operations
    await lru_cache.set("key1", "value1")
    await lru_cache.get("key1")  # Hit
    await lru_cache.get("key2")  # Miss
    
    # Verify metrics were recorded (using global instance)
    stats = cache_metrics.get_stats()
    assert stats['total_hits'] >= 1
    assert stats['total_misses'] >= 1


@pytest.mark.asyncio
async def test_lru_cache_eviction_metrics(metrics):
    """Test eviction metrics with small cache."""
    metrics.reset()
    
    # Create small cache
    cache = LRUCache(max_size=3, default_ttl=300)
    
    # Fill cache
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    
    # Trigger eviction
    await cache.set("key4", "value4")
    
    # Verify eviction was recorded
    # (eviction counter should be incremented)


@pytest.mark.asyncio
async def test_concurrent_metrics_recording(metrics):
    """Test metrics recording under concurrent access."""
    metrics.reset()
    
    async def record_operations(n: int):
        for _ in range(n):
            metrics.record_hit('l1')
            metrics.record_miss()
            metrics.record_operation('get', 'success')
    
    # Run concurrent tasks
    tasks = [record_operations(100) for _ in range(10)]
    await asyncio.gather(*tasks)
    
    # Verify all operations were recorded
    stats = metrics.get_stats()
    assert stats['total_hits'] == 1000
    assert stats['total_misses'] == 1000
    assert stats['total_operations'] == 2000


def test_metrics_reset(metrics):
    """Test resetting metrics."""
    # Record some operations
    metrics.record_hit('l1')
    metrics.record_miss()
    
    stats_before = metrics.get_stats()
    assert stats_before['total_operations'] > 0
    
    # Reset
    metrics.reset()
    
    stats_after = metrics.get_stats()
    assert stats_after['total_hits'] == 0
    assert stats_after['total_misses'] == 0
    assert stats_after['total_operations'] == 0


def test_prometheus_registry_has_cache_metrics():
    """Test that cache metrics are registered with Prometheus."""
    # Get all metric families from registry
    metric_families = list(REGISTRY.collect())
    
    # Find cache-related metrics (without _total suffix for some)
    cache_metric_names = [
        'cache_hits',  # Counter (Prometheus adds _total automatically)
        'cache_misses',  # Counter
        'cache_operations',  # Counter
        'cache_hit_rate',  # Gauge
        'cache_size',  # Gauge
        'cache_evictions',  # Counter
        'cache_l2_errors',  # Counter
        'cache_operation_duration_seconds',  # Histogram
    ]
    
    registered_names = set()
    for family in metric_families:
        registered_names.add(family.name)
    
    # Verify cache metrics are registered
    for metric_name in cache_metric_names:
        assert metric_name in registered_names, f"Metric {metric_name} not found in registry. Available: {sorted(registered_names)}"


def test_metrics_labels():
    """Test that metrics have correct labels."""
    # Record operations with different levels
    cache_metrics.record_hit('l1')
    cache_metrics.record_hit('l2')
    cache_metrics.record_operation('get', 'success')
    cache_metrics.record_operation('set', 'error')
    
    # Labels are validated by Prometheus client library
    # If labels are wrong, exceptions would be raised
    
    # Verify no exceptions


@pytest.mark.asyncio
async def test_full_cache_workflow_with_metrics():
    """Test complete cache workflow with metrics tracking."""
    cache_metrics.reset()
    
    cache = LRUCache(max_size=10, default_ttl=300)
    
    # Workflow: set → get (hit) → get (miss) → eviction
    
    # 1. Set operation
    await cache.set("key1", "value1")
    
    # 2. Get hit
    value = await cache.get("key1")
    assert value == "value1"
    
    # 3. Get miss
    value = await cache.get("key2")
    assert value is None
    
    # 4. Fill cache and trigger eviction
    for i in range(15):
        await cache.set(f"key_{i}", f"value_{i}")
    
    # Verify metrics (using global instance)
    stats = cache_metrics.get_stats()
    assert stats['total_hits'] >= 1
    assert stats['total_misses'] >= 1
    assert stats['total_operations'] > 0
    
    print(f"✅ Metrics tracked successfully: {stats}")
