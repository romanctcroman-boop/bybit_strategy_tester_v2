"""
Prometheus Metrics for Cache System

Exposes cache performance metrics for Prometheus scraping:
- cache_hits_total: Total cache hits (L1 + L2)
- cache_misses_total: Total cache misses
- cache_operations_total: Total cache operations by type
- cache_hit_rate: Current cache hit rate (0-1)
- cache_size: Current cache size (L1 + L2)
- cache_evictions_total: Total cache evictions
- cache_l2_errors_total: Total L2 (Redis) errors
- cache_operation_duration_seconds: Cache operation latency

Usage:
    from backend.cache.metrics import cache_metrics
    
    # Increment metrics
    cache_metrics.record_hit('l1')
    cache_metrics.record_miss()
    cache_metrics.record_eviction()
    
    # Record latency
    with cache_metrics.time_operation('get'):
        value = await cache.get(key)
"""

from contextlib import contextmanager
from typing import Literal

from prometheus_client import Counter, Gauge, Histogram, Info

# ============================================================================
# Cache Operation Counters
# ============================================================================

cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['level']  # l1, l2
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses'
)

cache_operations_total = Counter(
    'cache_operations_total',
    'Total number of cache operations',
    ['operation', 'status']  # get/set/delete, success/error
)

cache_evictions_total = Counter(
    'cache_evictions_total',
    'Total number of cache evictions',
    ['level']  # l1, l2
)

cache_expired_total = Counter(
    'cache_expired_total',
    'Total number of expired cache entries',
    ['level']  # l1, l2
)

cache_l2_errors_total = Counter(
    'cache_l2_errors_total',
    'Total number of L2 (Redis) errors',
    ['error_type']  # connection, timeout, other
)

cache_compute_errors_total = Counter(
    'cache_compute_errors_total',
    'Total number of compute function errors'
)

# ============================================================================
# Cache State Gauges
# ============================================================================

cache_size = Gauge(
    'cache_size',
    'Current number of items in cache',
    ['level']  # l1, l2
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Current cache hit rate (0-1)',
    ['level']  # l1, l2, overall
)

cache_memory_bytes = Gauge(
    'cache_memory_bytes',
    'Estimated cache memory usage in bytes',
    ['level']  # l1, l2
)

# ============================================================================
# Cache Performance Histograms
# ============================================================================

cache_operation_duration_seconds = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration in seconds',
    ['operation', 'level'],  # get/set/delete, l1/l2
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

cache_compute_duration_seconds = Histogram(
    'cache_compute_duration_seconds',
    'Compute function duration in seconds',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# ============================================================================
# Cache Info (metadata)
# ============================================================================

cache_info = Info(
    'cache_info',
    'Cache system information and configuration'
)

# Set initial cache info
cache_info.info({
    'version': '2.0.0',
    'type': 'two_level',
    'l1_type': 'lru',
    'l2_type': 'redis',
})


class CacheMetrics:
    """
    High-level interface for recording cache metrics.
    
    This class provides convenient methods for tracking cache operations
    and automatically updates Prometheus metrics.
    
    Example:
        metrics = CacheMetrics()
        
        # Record cache hit
        metrics.record_hit('l1')
        
        # Record cache miss
        metrics.record_miss()
        
        # Time cache operation
        with metrics.time_operation('get', 'l1'):
            value = await cache.get(key)
    """
    
    def __init__(self):
        """Initialize cache metrics tracker."""
        self._total_hits = 0
        self._total_misses = 0
    
    def record_hit(self, level: Literal['l1', 'l2']):
        """
        Record a cache hit.
        
        Args:
            level: Cache level ('l1' or 'l2')
        """
        cache_hits_total.labels(level=level).inc()
        self._total_hits += 1
        self._update_hit_rate()
    
    def record_miss(self):
        """Record a cache miss."""
        cache_misses_total.inc()
        self._total_misses += 1
        self._update_hit_rate()
    
    def record_operation(
        self,
        operation: Literal['get', 'set', 'delete'],
        status: Literal['success', 'error']
    ):
        """
        Record a cache operation.
        
        Args:
            operation: Type of operation
            status: Operation status
        """
        cache_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
    
    def record_eviction(self, level: Literal['l1', 'l2'] = 'l1'):
        """
        Record a cache eviction.
        
        Args:
            level: Cache level where eviction occurred
        """
        cache_evictions_total.labels(level=level).inc()
    
    def record_expired(self, level: Literal['l1', 'l2'] = 'l1'):
        """
        Record an expired cache entry removal.
        
        Args:
            level: Cache level where expiration occurred
        """
        cache_expired_total.labels(level=level).inc()
    
    def record_l2_error(self, error_type: str = 'other'):
        """
        Record an L2 (Redis) error.
        
        Args:
            error_type: Type of error (connection, timeout, other)
        """
        cache_l2_errors_total.labels(error_type=error_type).inc()
    
    def record_compute_error(self):
        """Record a compute function error."""
        cache_compute_errors_total.inc()
    
    def update_cache_size(self, size: int, level: Literal['l1', 'l2']):
        """
        Update cache size gauge.
        
        Args:
            size: Current cache size
            level: Cache level
        """
        cache_size.labels(level=level).set(size)
    
    def update_memory_usage(self, bytes_used: int, level: Literal['l1', 'l2']):
        """
        Update cache memory usage gauge.
        
        Args:
            bytes_used: Memory usage in bytes
            level: Cache level
        """
        cache_memory_bytes.labels(level=level).set(bytes_used)
    
    @contextmanager
    def time_operation(
        self,
        operation: Literal['get', 'set', 'delete'],
        level: Literal['l1', 'l2']
    ):
        """
        Context manager to time cache operations.
        
        Args:
            operation: Type of operation
            level: Cache level
            
        Example:
            with metrics.time_operation('get', 'l1'):
                value = await cache.get(key)
        """
        with cache_operation_duration_seconds.labels(
            operation=operation,
            level=level
        ).time():
            yield
    
    @contextmanager
    def time_compute(self):
        """
        Context manager to time compute function execution.
        
        Example:
            with metrics.time_compute():
                value = await compute_func()
        """
        with cache_compute_duration_seconds.time():
            yield
    
    def _update_hit_rate(self):
        """Update cache hit rate gauges."""
        total_ops = self._total_hits + self._total_misses
        
        if total_ops > 0:
            overall_rate = self._total_hits / total_ops
            cache_hit_rate.labels(level='overall').set(overall_rate)
    
    def get_stats(self) -> dict:
        """
        Get current cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_ops = self._total_hits + self._total_misses
        hit_rate = self._total_hits / total_ops if total_ops > 0 else 0.0
        
        return {
            'total_hits': self._total_hits,
            'total_misses': self._total_misses,
            'total_operations': total_ops,
            'hit_rate': hit_rate,
        }
    
    def reset(self):
        """Reset internal counters (for testing)."""
        self._total_hits = 0
        self._total_misses = 0


# Global metrics instance
cache_metrics = CacheMetrics()


def get_cache_metrics() -> CacheMetrics:
    """
    Get global cache metrics instance.
    
    Returns:
        Global CacheMetrics instance
    """
    return cache_metrics
