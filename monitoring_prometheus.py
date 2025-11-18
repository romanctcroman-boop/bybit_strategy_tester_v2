"""
Production Monitoring: Prometheus Instrumentation
Adds metrics collection to AsyncDataService and BacktestEngine

Based on Phase 3 Deployment Plan from Perplexity AI
"""

from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
import time
import psutil
import asyncio
from functools import wraps
from typing import Any, Callable


# ============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ============================================================================

# Backtest Metrics
backtest_throughput = Gauge(
    'backtest_throughput_bars_per_sec',
    'Backtest processing throughput in bars per second'
)

backtest_total = Counter(
    'backtest_total',
    'Total number of backtests executed',
    ['status']  # success, error
)

backtest_duration = Histogram(
    'backtest_duration_seconds',
    'Backtest execution duration in seconds',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Data Loading Metrics
data_loading_latency = Histogram(
    'data_loading_latency_seconds',
    'Data loading latency in seconds',
    ['source'],  # local, remote
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

data_files_loaded = Counter(
    'data_files_loaded_total',
    'Total number of data files loaded',
    ['status']  # success, error
)

# Connection Pool Metrics
connection_pool_usage = Gauge(
    'connection_pool_usage_percent',
    'Connection pool usage percentage'
)

connection_pool_size = Gauge(
    'connection_pool_size',
    'Connection pool maximum size'
)

# Memory Metrics
memory_consumption = Gauge(
    'memory_consumption_mb',
    'Memory consumption in megabytes'
)

# CPU Metrics
cpu_utilization = Gauge(
    'cpu_utilization_percent',
    'CPU utilization percentage'
)

# Error Metrics
error_rate = Counter(
    'error_rate_total',
    'Total number of errors',
    ['component', 'error_type']
)

# System Info
system_info = Info(
    'system_info',
    'System information'
)


# ============================================================================
# DECORATOR: ASYNC FUNCTION METRICS
# ============================================================================

def async_metrics(metric_name: str):
    """
    Decorator to automatically collect metrics for async functions.
    
    Args:
        metric_name: Name identifier for the metric
        
    Usage:
        @async_metrics('data_loading')
        async def load_data(path):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Success metrics
                duration = time.time() - start_time
                
                if metric_name == 'data_loading':
                    source = 'local' if 'local' in str(kwargs.get('path', '')) else 'remote'
                    data_loading_latency.labels(source=source).observe(duration)
                    data_files_loaded.labels(status='success').inc()
                
                elif metric_name == 'backtest':
                    backtest_duration.observe(duration)
                    backtest_total.labels(status='success').inc()
                    
                    # Calculate throughput
                    bars = kwargs.get('bars', 0)
                    if bars > 0 and duration > 0:
                        throughput = bars / duration
                        backtest_throughput.set(throughput)
                
                return result
                
            except Exception as e:
                # Error metrics
                duration = time.time() - start_time
                
                if metric_name == 'data_loading':
                    data_files_loaded.labels(status='error').inc()
                    error_rate.labels(
                        component='data_service',
                        error_type=type(e).__name__
                    ).inc()
                
                elif metric_name == 'backtest':
                    backtest_total.labels(status='error').inc()
                    error_rate.labels(
                        component='backtest_engine',
                        error_type=type(e).__name__
                    ).inc()
                
                raise
        
        return wrapper
    return decorator


# ============================================================================
# SYSTEM METRICS COLLECTOR
# ============================================================================

class SystemMetricsCollector:
    """Collects system-level metrics (CPU, memory) periodically."""
    
    def __init__(self, interval: float = 5.0):
        """
        Initialize system metrics collector.
        
        Args:
            interval: Collection interval in seconds (default: 5.0)
        """
        self.interval = interval
        self._running = False
        self._task = None
    
    async def start(self):
        """Start collecting system metrics."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        
        # Set system info
        system_info.info({
            'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
            'platform': psutil.platform.system(),
            'cpu_count': str(psutil.cpu_count()),
        })
    
    async def stop(self):
        """Stop collecting system metrics."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _collect_loop(self):
        """Main collection loop."""
        while self._running:
            try:
                # CPU utilization
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_utilization.set(cpu_percent)
                
                # Memory consumption
                memory = psutil.Process().memory_info()
                memory_mb = memory.rss / 1024 / 1024
                memory_consumption.set(memory_mb)
                
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                error_rate.labels(
                    component='metrics_collector',
                    error_type=type(e).__name__
                ).inc()
                await asyncio.sleep(self.interval)


# ============================================================================
# METRICS SERVER
# ============================================================================

def start_metrics_server(port: int = 8000):
    """
    Start Prometheus metrics HTTP server.
    
    Args:
        port: Port to expose metrics on (default: 8000)
        
    Usage:
        start_metrics_server(port=8000)
        # Metrics available at http://localhost:8000/metrics
    """
    start_http_server(port)
    print(f"✅ Prometheus metrics server started on http://localhost:{port}/metrics")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of how to use monitoring in production code."""
    
    # Start metrics server
    start_metrics_server(port=8000)
    
    # Start system metrics collector
    collector = SystemMetricsCollector(interval=5.0)
    await collector.start()
    
    # Your application code here
    # Decorated functions will automatically collect metrics
    
    @async_metrics('data_loading')
    async def load_data(path: str):
        """Example data loading function with metrics."""
        await asyncio.sleep(0.1)  # Simulate loading
        return {"data": "loaded"}
    
    @async_metrics('backtest')
    async def run_backtest(bars: int):
        """Example backtest function with metrics."""
        await asyncio.sleep(0.5)  # Simulate backtest
        return {"result": "success"}
    
    # Execute operations
    await load_data("local/data.csv")
    await run_backtest(bars=1000)
    
    # Keep running
    await asyncio.sleep(30)
    
    # Cleanup
    await collector.stop()


if __name__ == "__main__":
    """
    Run this script to test Prometheus instrumentation:
    
    1. python monitoring_prometheus.py
    2. Open http://localhost:8000/metrics
    3. See collected metrics
    """
    asyncio.run(example_usage())
