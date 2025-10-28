"""
Prometheus metrics for Bybit Adapter monitoring.

Provides metrics for:
- API request counts and latencies
- Cache hit/miss rates
- Error rates by type
- Data volume (candles fetched)
- Rate limiting status
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable, TypeVar

# Type variable for generic function
F = TypeVar('F', bound=Callable)

# API Request metrics
bybit_api_requests_total = Counter(
    'bybit_api_requests_total',
    'Total number of Bybit API requests',
    ['symbol', 'interval', 'endpoint', 'status']
)

bybit_api_duration_seconds = Histogram(
    'bybit_api_duration_seconds',
    'Bybit API request duration in seconds',
    ['symbol', 'interval', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Cache metrics
bybit_cache_operations_total = Counter(
    'bybit_cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # operation: get/set/clear, result: hit/miss/success/error
)

bybit_cache_size_bytes = Gauge(
    'bybit_cache_size_bytes',
    'Current cache size in bytes',
    ['cache_type']
)

bybit_cache_items_total = Gauge(
    'bybit_cache_items_total',
    'Number of items in cache',
    ['cache_type']
)

# Data metrics
bybit_candles_fetched_total = Counter(
    'bybit_candles_fetched_total',
    'Total number of candles fetched',
    ['symbol', 'interval', 'source']  # source: api/cache
)

bybit_candles_stored_total = Counter(
    'bybit_candles_stored_total',
    'Total number of candles stored',
    ['symbol', 'interval', 'destination']  # destination: cache/db
)

# Error metrics
bybit_errors_total = Counter(
    'bybit_errors_total',
    'Total number of errors',
    ['error_type', 'symbol', 'interval']
)

bybit_rate_limit_hits_total = Counter(
    'bybit_rate_limit_hits_total',
    'Number of times rate limit was hit',
    ['symbol']
)

# Retry metrics
bybit_retry_attempts_total = Counter(
    'bybit_retry_attempts_total',
    'Total retry attempts',
    ['symbol', 'interval', 'attempt']
)

# Historical fetch metrics
bybit_historical_fetches_total = Counter(
    'bybit_historical_fetches_total',
    'Total historical fetch operations',
    ['symbol', 'interval']
)

bybit_historical_fetch_duration_seconds = Histogram(
    'bybit_historical_fetch_duration_seconds',
    'Historical fetch duration in seconds',
    ['symbol', 'interval'],
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

bybit_historical_api_requests_per_fetch = Histogram(
    'bybit_historical_api_requests_per_fetch',
    'Number of API requests per historical fetch',
    ['symbol', 'interval'],
    buckets=[1, 2, 3, 5, 7, 10, 15, 20]
)

# System info
bybit_adapter_info = Info(
    'bybit_adapter_info',
    'Bybit adapter version and configuration'
)


def track_api_request(symbol: str, interval: str, endpoint: str = 'kline'):
    """
    Decorator to track API request metrics.
    
    Usage:
        @track_api_request('BTCUSDT', '15', 'kline')
        def fetch_klines():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                bybit_errors_total.labels(
                    error_type=type(e).__name__,
                    symbol=symbol,
                    interval=interval
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                
                bybit_api_requests_total.labels(
                    symbol=symbol,
                    interval=interval,
                    endpoint=endpoint,
                    status=status
                ).inc()
                
                bybit_api_duration_seconds.labels(
                    symbol=symbol,
                    interval=interval,
                    endpoint=endpoint
                ).observe(duration)
        
        return wrapper  # type: ignore
    return decorator


def record_cache_hit(symbol: str, interval: str, candles_count: int):
    """Record cache hit metrics."""
    bybit_cache_operations_total.labels(
        operation='get',
        result='hit'
    ).inc()
    
    bybit_candles_fetched_total.labels(
        symbol=symbol,
        interval=interval,
        source='cache'
    ).inc(candles_count)


def record_cache_miss(symbol: str, interval: str):
    """Record cache miss metrics."""
    bybit_cache_operations_total.labels(
        operation='get',
        result='miss'
    ).inc()


def record_cache_set(symbol: str, interval: str, candles_count: int):
    """Record cache set metrics."""
    bybit_cache_operations_total.labels(
        operation='set',
        result='success'
    ).inc()
    
    bybit_candles_stored_total.labels(
        symbol=symbol,
        interval=interval,
        destination='cache'
    ).inc(candles_count)


def record_api_fetch(symbol: str, interval: str, candles_count: int):
    """Record API fetch metrics."""
    bybit_candles_fetched_total.labels(
        symbol=symbol,
        interval=interval,
        source='api'
    ).inc(candles_count)


def record_db_store(symbol: str, interval: str, candles_count: int):
    """Record database storage metrics."""
    bybit_candles_stored_total.labels(
        symbol=symbol,
        interval=interval,
        destination='db'
    ).inc(candles_count)


def record_rate_limit_hit(symbol: str):
    """Record rate limit hit."""
    bybit_rate_limit_hits_total.labels(symbol=symbol).inc()


def record_retry_attempt(symbol: str, interval: str, attempt: int):
    """Record retry attempt."""
    bybit_retry_attempts_total.labels(
        symbol=symbol,
        interval=interval,
        attempt=str(attempt)
    ).inc()


def record_historical_fetch(
    symbol: str, 
    interval: str, 
    duration: float, 
    api_requests: int,
    candles_fetched: int
):
    """Record historical fetch metrics."""
    bybit_historical_fetches_total.labels(
        symbol=symbol,
        interval=interval
    ).inc()
    
    bybit_historical_fetch_duration_seconds.labels(
        symbol=symbol,
        interval=interval
    ).observe(duration)
    
    bybit_historical_api_requests_per_fetch.labels(
        symbol=symbol,
        interval=interval
    ).observe(api_requests)
    
    bybit_candles_fetched_total.labels(
        symbol=symbol,
        interval=interval,
        source='api'
    ).inc(candles_fetched)


def init_adapter_info(version: str = '2.0', **config):
    """Initialize adapter info metric."""
    info_dict = {
        'version': version,
        **{k: str(v) for k, v in config.items()}
    }
    bybit_adapter_info.info(info_dict)
