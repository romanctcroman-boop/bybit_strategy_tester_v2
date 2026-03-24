"""
Prometheus Metrics Exporter

Exports application metrics in Prometheus format:
- HTTP request metrics
- AI agent metrics
- Cache metrics
- Backtest metrics
- Cost tracking

Usage:
    from backend.monitoring.prometheus_exporter import MetricsCollector
    collector = MetricsCollector()
    collector.record_http_request(200, 0.15)
    metrics = collector.get_metrics()
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class MetricPoint:
    """Single metric data point."""

    timestamp: float
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Prometheus-compatible metrics collector.

    Collects and exports metrics in Prometheus text format.

    Metrics collected:
    - http_requests_total (counter)
    - http_request_duration_seconds (histogram)
    - ai_agent_requests_total (counter)
    - ai_agent_request_duration_seconds (histogram)
    - cache_hits_total (counter)
    - cache_misses_total (counter)
    - backtest_total (counter)
    - backtest_failures_total (counter)
    - cost_usd_total (counter)

    Example:
        collector = MetricsCollector()
        collector.record_http_request(200, 0.15)
        collector.record_ai_request("qwen", 2.5, True)
        metrics = collector.get_metrics()
    """

    def __init__(self):
        """Initialize metrics collector."""
        # Counters
        self._counters: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))

        # Histograms (stored as buckets)
        self._histograms: dict[str, dict[tuple, dict[float, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )

        # Histogram buckets (in seconds)
        self._histogram_buckets = [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

        # Gauges
        self._gauges: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))

        # Start time
        self._start_time = time.time()

        logger.info("📊 MetricsCollector initialized")

    def record_http_request(
        self,
        status_code: int,
        duration_seconds: float,
        method: str = "GET",
        endpoint: str = "/",
    ) -> None:
        """
        Record HTTP request metrics.

        Args:
            status_code: HTTP status code
            duration_seconds: Request duration
            method: HTTP method
            endpoint: Request endpoint
        """
        labels = {"status": str(status_code), "method": method, "endpoint": endpoint}
        labels_tuple = tuple(sorted(labels.items()))

        # Increment counter
        self._counters["http_requests_total"][labels_tuple] += 1

        # Record histogram
        self._record_histogram("http_request_duration_seconds", labels_tuple, duration_seconds)

    def record_ai_request(
        self,
        agent: str,
        duration_seconds: float,
        success: bool,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """
        Record AI agent request metrics.

        Args:
            agent: Agent name (qwen, deepseek, perplexity)
            duration_seconds: Request duration
            success: Whether request succeeded
            tokens_used: Tokens consumed
            cost_usd: Cost in USD
        """
        labels = {"agent": agent, "success": str(success).lower()}
        labels_tuple = tuple(sorted(labels.items()))

        # Increment counter
        self._counters["ai_agent_requests_total"][labels_tuple] += 1

        # Record histogram
        self._record_histogram("ai_agent_request_duration_seconds", labels_tuple, duration_seconds)

        # Record tokens
        if tokens_used > 0:
            token_labels = tuple(sorted({"agent": agent}.items()))
            self._counters["ai_agent_tokens_total"][token_labels] += tokens_used

        # Record cost
        if cost_usd > 0:
            cost_labels = tuple(sorted({"agent": agent}.items()))
            self._counters["cost_usd_total"][cost_labels] += cost_usd

    def record_cache_hit(self) -> None:
        """Record cache hit."""
        self._counters["cache_hits_total"][()] += 1

    def record_cache_miss(self) -> None:
        """Record cache miss."""
        self._counters["cache_misses_total"][()] += 1

    def record_backtest(self, success: bool, duration_seconds: float) -> None:
        """
        Record backtest execution.

        Args:
            success: Whether backtest succeeded
            duration_seconds: Execution duration
        """
        labels = {"success": str(success).lower()}
        labels_tuple = tuple(sorted(labels.items()))

        self._counters["backtest_total"][()] += 1

        if not success:
            self._counters["backtest_failures_total"][()] += 1

        self._record_histogram("backtest_duration_seconds", labels_tuple, duration_seconds)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """
        Set gauge value.

        Args:
            name: Metric name
            value: Gauge value
            labels: Optional labels
        """
        labels_tuple = tuple(sorted(labels.items())) if labels else ()
        self._gauges[name][labels_tuple] = value

    def _record_histogram(
        self,
        name: str,
        labels_tuple: tuple,
        value: float,
    ) -> None:
        """Record histogram value."""
        for bucket in self._histogram_buckets:
            if value <= bucket:
                bucket_labels = labels_tuple + (("le", str(bucket)),)
                self._counters[f"{name}_bucket"][bucket_labels] += 1

        # Infinity bucket
        inf_labels = labels_tuple + (("le", "+Inf"),)
        self._counters[f"{name}_bucket"][inf_labels] += 1

        # Sum and count
        self._counters[f"{name}_sum"][labels_tuple] += value
        self._counters[f"{name}_count"][labels_tuple] += 1

    def get_metrics(self) -> str:
        """
        Get metrics in Prometheus text format.

        Returns:
            Metrics in Prometheus exposition format
        """
        lines = []

        # Add metadata
        lines.append("# HELP process_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {time.time() - self._start_time}")
        lines.append("")

        # First, export all histograms (they need special handling)
        histogram_bases = set()
        for name in self._counters.keys():
            if "_bucket" in name:
                base_name = name.replace("_bucket", "")
                histogram_bases.add(base_name)

        for base_name in histogram_bases:
            lines.append(f"# HELP {base_name} Request duration histogram")
            lines.append(f"# TYPE {base_name} histogram")

            # Export buckets
            for labels_tuple, value in self._counters.get(f"{base_name}_bucket", {}).items():
                labels_dict = dict(labels_tuple) if labels_tuple else {}
                le = labels_dict.pop("le", "+Inf")
                if labels_dict:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels_dict.items()) + f',le="{le}"' + "}"
                else:
                    labels_str = f'{{le="{le}"}}'
                lines.append(f"{base_name}_bucket{labels_str} {value}")

            # Export sum
            for labels_tuple, value in self._counters.get(f"{base_name}_sum", {}).items():
                if labels_tuple:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels_tuple) + "}"
                else:
                    labels_str = ""
                lines.append(f"{base_name}_sum{labels_str} {value}")

            # Export count
            for labels_tuple, value in self._counters.get(f"{base_name}_count", {}).items():
                if labels_tuple:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels_tuple) + "}"
                else:
                    labels_str = ""
                lines.append(f"{base_name}_count{labels_str} {value}")

            lines.append("")

        # Counters (excluding histogram buckets/sum/count)
        for name, data in self._counters.items():
            if "_bucket" in name or "_sum" in name or "_count" in name:
                continue

            lines.append(f"# HELP {name} Total count")
            lines.append(f"# TYPE {name} counter")

            for labels_tuple, value in data.items():
                if labels_tuple:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels_tuple) + "}"
                else:
                    labels_str = ""
                lines.append(f"{name}{labels_str} {value}")

            lines.append("")

        # Gauges
        for name, data in self._gauges.items():
            lines.append(f"# HELP {name} Gauge metric")
            lines.append(f"# TYPE {name} gauge")

            for labels_tuple, value in data.items():
                if labels_tuple:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels_tuple) + "}"
                else:
                    labels_str = ""
                lines.append(f"{name}{labels_str} {value}")

            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Get metrics as dict."""
        stats = {
            "uptime_seconds": time.time() - self._start_time,
            "counters": {},
            "gauges": {},
        }

        for name, data in self._counters.items():
            if "_bucket" not in name and "_sum" not in name and "_count" not in name:
                stats["counters"][name] = sum(data.values())

        for name, data in self._gauges.items():
            stats["gauges"][name] = sum(data.values())

        return stats


# Global collector instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector (singleton)."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
