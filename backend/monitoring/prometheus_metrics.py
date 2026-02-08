"""
Prometheus Metrics Exporter for FastAPI

Exports all system metrics to Prometheus format:
- Cache performance (hits, misses, latency)
- AI agent latency and success rates
- Backtest execution metrics
- API endpoint performance
- System health indicators
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PrometheusMetrics:
    """Container for all Prometheus metrics"""

    # Cache metrics
    cache_hits: Counter = field(
        default_factory=lambda: Counter(
            "cache_hits_total", "Total cache hits", ["operation_type"]
        )
    )

    cache_misses: Counter = field(
        default_factory=lambda: Counter(
            "cache_misses_total", "Total cache misses", ["operation_type"]
        )
    )

    cache_hit_rate: Gauge = field(
        default_factory=lambda: Gauge(
            "cache_hit_rate", "Current cache hit rate", ["operation_type"]
        )
    )

    cache_latency: Histogram = field(
        default_factory=lambda: Histogram(
            "cache_latency_seconds",
            "Cache retrieval latency",
            ["operation_type"],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
        )
    )

    # AI Agent metrics
    ai_request_duration: Histogram = field(
        default_factory=lambda: Histogram(
            "ai_request_duration_seconds",
            "AI API request duration",
            ["model", "endpoint"],
            buckets=(1, 5, 10, 20, 30, 60, 120, 300),
        )
    )

    ai_request_total: Counter = field(
        default_factory=lambda: Counter(
            "ai_requests_total",
            "Total AI API requests",
            ["model", "endpoint", "status"],
        )
    )

    ai_response_length: Gauge = field(
        default_factory=lambda: Gauge(
            "ai_response_length_bytes", "AI response size", ["model"]
        )
    )

    # Backtest metrics
    backtest_duration: Histogram = field(
        default_factory=lambda: Histogram(
            "backtest_duration_seconds",
            "Backtest execution time",
            ["asset", "timeframe"],
            buckets=(10, 30, 60, 300, 600, 1800, 3600),
        )
    )

    backtest_total: Counter = field(
        default_factory=lambda: Counter(
            "backtests_total", "Total backtests executed", ["asset", "status"]
        )
    )

    backtest_win_rate: Gauge = field(
        default_factory=lambda: Gauge(
            "backtest_win_rate", "Backtest win rate", ["strategy", "asset"]
        )
    )

    backtest_profit_factor: Gauge = field(
        default_factory=lambda: Gauge(
            "backtest_profit_factor", "Backtest profit factor", ["strategy", "asset"]
        )
    )

    backtest_max_drawdown: Gauge = field(
        default_factory=lambda: Gauge(
            "backtest_max_drawdown", "Backtest maximum drawdown", ["strategy", "asset"]
        )
    )

    backtest_sharpe_ratio: Gauge = field(
        default_factory=lambda: Gauge(
            "backtest_sharpe_ratio", "Backtest Sharpe ratio", ["strategy", "asset"]
        )
    )

    # API endpoint metrics
    api_request_duration: Histogram = field(
        default_factory=lambda: Histogram(
            "api_request_duration_seconds",
            "API endpoint request duration",
            ["endpoint", "method", "status"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
        )
    )

    api_requests_total: Counter = field(
        default_factory=lambda: Counter(
            "api_requests_total", "Total API requests", ["endpoint", "method", "status"]
        )
    )

    # System health metrics
    system_health: Gauge = field(
        default_factory=lambda: Gauge(
            "system_health",
            "System health status (1=healthy, 0=unhealthy)",
            ["component"],
        )
    )

    redis_connection_status: Gauge = field(
        default_factory=lambda: Gauge(
            "redis_connection_status",
            "Redis connection status (1=connected, 0=disconnected)",
        )
    )

    database_connection_status: Gauge = field(
        default_factory=lambda: Gauge(
            "database_connection_status",
            "Database connection status (1=connected, 0=disconnected)",
        )
    )

    active_backtest_jobs: Gauge = field(
        default_factory=lambda: Gauge(
            "active_backtest_jobs", "Number of active backtest jobs"
        )
    )


class MetricsCollector:
    """Centralized metrics collection and export"""

    def __init__(self, registry=None):
        if registry is None:
            self.registry = CollectorRegistry()
        else:
            self.registry = registry

        # Create metrics with the provided registry
        self.metrics = self._create_metrics()
        self._initialize_metrics()

    def _create_metrics(self) -> PrometheusMetrics:
        """Create all metrics with the configured registry"""
        return PrometheusMetrics(
            cache_hits=Counter(
                "cache_hits_total",
                "Total cache hits",
                ["operation_type"],
                registry=self.registry,
            ),
            cache_misses=Counter(
                "cache_misses_total",
                "Total cache misses",
                ["operation_type"],
                registry=self.registry,
            ),
            cache_hit_rate=Gauge(
                "cache_hit_rate",
                "Current cache hit rate",
                ["operation_type"],
                registry=self.registry,
            ),
            cache_latency=Histogram(
                "cache_latency_seconds",
                "Cache retrieval latency",
                ["operation_type"],
                buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
                registry=self.registry,
            ),
            ai_request_duration=Histogram(
                "ai_request_duration_seconds",
                "AI API request duration",
                ["model", "endpoint"],
                buckets=(1, 5, 10, 20, 30, 60, 120, 300),
                registry=self.registry,
            ),
            ai_request_total=Counter(
                "ai_requests_total",
                "Total AI API requests",
                ["model", "endpoint", "status"],
                registry=self.registry,
            ),
            ai_response_length=Gauge(
                "ai_response_length_bytes",
                "AI response size",
                ["model"],
                registry=self.registry,
            ),
            backtest_duration=Histogram(
                "backtest_duration_seconds",
                "Backtest execution time",
                ["asset", "timeframe"],
                buckets=(10, 30, 60, 300, 600, 1800, 3600),
                registry=self.registry,
            ),
            backtest_total=Counter(
                "backtests_total",
                "Total backtests executed",
                ["asset", "status"],
                registry=self.registry,
            ),
            backtest_win_rate=Gauge(
                "backtest_win_rate",
                "Backtest win rate",
                ["strategy", "asset"],
                registry=self.registry,
            ),
            backtest_profit_factor=Gauge(
                "backtest_profit_factor",
                "Backtest profit factor",
                ["strategy", "asset"],
                registry=self.registry,
            ),
            backtest_max_drawdown=Gauge(
                "backtest_max_drawdown",
                "Backtest maximum drawdown",
                ["strategy", "asset"],
                registry=self.registry,
            ),
            backtest_sharpe_ratio=Gauge(
                "backtest_sharpe_ratio",
                "Backtest Sharpe ratio",
                ["strategy", "asset"],
                registry=self.registry,
            ),
            api_request_duration=Histogram(
                "api_request_duration_seconds",
                "API endpoint request duration",
                ["endpoint", "method", "status"],
                buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
                registry=self.registry,
            ),
            api_requests_total=Counter(
                "api_requests_total",
                "Total API requests",
                ["endpoint", "method", "status"],
                registry=self.registry,
            ),
            system_health=Gauge(
                "system_health",
                "System health status (1=healthy, 0=unhealthy)",
                ["component"],
                registry=self.registry,
            ),
            redis_connection_status=Gauge(
                "redis_connected", "Redis connection status", registry=self.registry
            ),
            database_connection_status=Gauge(
                "database_connected",
                "Database connection status",
                registry=self.registry,
            ),
            active_backtest_jobs=Gauge(
                "active_backtest_jobs",
                "Number of active backtest jobs",
                registry=self.registry,
            ),
        )

    def _initialize_metrics(self):
        """Initialize all metrics in registry - already done in _create_metrics"""
        # Metrics are already registered when created above
        pass

    def record_cache_hit(self, operation_type: str, latency_ms: float):
        """Record cache hit"""
        self.metrics.cache_hits.labels(operation_type=operation_type).inc()
        self.metrics.cache_latency.labels(operation_type=operation_type).observe(
            latency_ms / 1000.0
        )

    def record_cache_miss(self, operation_type: str):
        """Record cache miss"""
        self.metrics.cache_misses.labels(operation_type=operation_type).inc()

    def update_cache_hit_rate(self, operation_type: str, hit_rate: float):
        """Update cache hit rate gauge"""
        self.metrics.cache_hit_rate.labels(operation_type=operation_type).set(hit_rate)

    def record_ai_request(
        self,
        model: str,
        endpoint: str,
        duration_seconds: float,
        status: str,
        response_length: int = 0,
    ):
        """Record AI API request"""
        self.metrics.ai_request_duration.labels(model=model, endpoint=endpoint).observe(
            duration_seconds
        )
        self.metrics.ai_request_total.labels(
            model=model, endpoint=endpoint, status=status
        ).inc()
        if response_length > 0:
            self.metrics.ai_response_length.labels(model=model).set(response_length)

    def record_backtest(
        self,
        asset: str,
        timeframe: str,
        duration_seconds: float,
        status: str,
        strategy: str = "",
        win_rate: float = None,
        profit_factor: float = None,
        max_drawdown: float = None,
        sharpe_ratio: float = None,
    ):
        """Record backtest execution"""
        self.metrics.backtest_duration.labels(asset=asset, timeframe=timeframe).observe(
            duration_seconds
        )
        self.metrics.backtest_total.labels(asset=asset, status=status).inc()

        if strategy and win_rate is not None:
            self.metrics.backtest_win_rate.labels(strategy=strategy, asset=asset).set(
                win_rate
            )

        if strategy and profit_factor is not None:
            self.metrics.backtest_profit_factor.labels(
                strategy=strategy, asset=asset
            ).set(profit_factor)

        if strategy and max_drawdown is not None:
            self.metrics.backtest_max_drawdown.labels(
                strategy=strategy, asset=asset
            ).set(max_drawdown)

        if strategy and sharpe_ratio is not None:
            self.metrics.backtest_sharpe_ratio.labels(
                strategy=strategy, asset=asset
            ).set(sharpe_ratio)

    def record_api_request(
        self, endpoint: str, method: str, status: int, duration_seconds: float
    ):
        """Record API request"""
        status_str = "success" if status < 400 else "error"
        self.metrics.api_request_duration.labels(
            endpoint=endpoint, method=method, status=status_str
        ).observe(duration_seconds)
        self.metrics.api_requests_total.labels(
            endpoint=endpoint, method=method, status=status_str
        ).inc()

    def set_component_health(self, component: str, healthy: bool):
        """Set component health status"""
        self.metrics.system_health.labels(component=component).set(1 if healthy else 0)

    def set_redis_status(self, connected: bool):
        """Set Redis connection status"""
        self.metrics.redis_connection_status.set(1 if connected else 0)

    def set_database_status(self, connected: bool):
        """Set database connection status"""
        self.metrics.database_connection_status.set(1 if connected else 0)

    def set_active_backtests(self, count: int):
        """Set number of active backtest jobs"""
        self.metrics.active_backtest_jobs.set(count)

    def get_metrics_text(self) -> str:
        """Export metrics in Prometheus text format"""
        return generate_latest(self.registry).decode("utf-8")

    def get_metrics_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary"""
        metrics_text = self.get_metrics_text()

        result = {"timestamp": datetime.now(UTC).isoformat(), "metrics": {}}

        for line in metrics_text.split("\n"):
            if line and not line.startswith("#"):
                # Parse metric line
                if "{" in line:
                    metric_name = line.split("{")[0]
                    metric_value = line.split()[-1]
                else:
                    metric_name = line.split()[0]
                    metric_value = line.split()[-1]

                result["metrics"][metric_name] = metric_value

        return result


# Global metrics collector instance
_metrics_collector: MetricsCollector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector

    # Create new if not exists - always use its own registry
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
        logger.info("[METRICS] Metrics collector initialized")

    return _metrics_collector
