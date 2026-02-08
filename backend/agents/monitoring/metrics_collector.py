"""
Metrics Collector for AI Agent System

Provides Prometheus-style metrics collection:
- Counter: Monotonically increasing values (requests, errors)
- Gauge: Values that can go up and down (active requests, memory)
- Histogram: Distribution of values (latency, response sizes)
- Summary: Similar to histogram with quantiles

Features:
- Thread-safe metric updates
- Automatic aggregation
- Time-series storage
- Export to various formats
"""

from __future__ import annotations

import json
import statistics
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class MetricType(Enum):
    """Types of metrics"""

    COUNTER = "counter"  # Always increasing
    GAUGE = "gauge"  # Can go up/down
    HISTOGRAM = "histogram"  # Distribution
    SUMMARY = "summary"  # Quantiles


class MetricAggregation(Enum):
    """Time-series aggregation methods"""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"  # Per-second rate
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"


@dataclass
class MetricValue:
    """A single metric value with timestamp"""

    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    """Metric definition"""

    name: str
    description: str
    type: MetricType
    unit: str = ""
    labels: list[str] = field(default_factory=list)
    buckets: list[float] = field(default_factory=list)  # For histograms

    def __hash__(self):
        return hash(self.name)


@dataclass
class MetricSeries:
    """Time series data for a metric"""

    metric: Metric
    values: list[MetricValue] = field(default_factory=list)
    histogram_counts: dict[float, int] = field(default_factory=dict)
    sum_value: float = 0.0
    count: int = 0

    def add_value(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Add a value to the series"""
        self.values.append(MetricValue(value=value, labels=labels or {}))
        self.sum_value += value
        self.count += 1

        # For histograms, update bucket counts
        if self.metric.type == MetricType.HISTOGRAM and self.metric.buckets:
            for bucket in self.metric.buckets:
                if value <= bucket:
                    self.histogram_counts[bucket] = (
                        self.histogram_counts.get(bucket, 0) + 1
                    )

    def get_aggregated(
        self,
        aggregation: MetricAggregation,
        window_seconds: int = 60,
    ) -> float:
        """Get aggregated value over time window"""
        cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
        recent = [v.value for v in self.values if v.timestamp >= cutoff]

        if not recent:
            return 0.0

        if aggregation == MetricAggregation.SUM:
            return sum(recent)
        elif aggregation == MetricAggregation.AVG:
            return statistics.mean(recent)
        elif aggregation == MetricAggregation.MIN:
            return min(recent)
        elif aggregation == MetricAggregation.MAX:
            return max(recent)
        elif aggregation == MetricAggregation.COUNT:
            return len(recent)
        elif aggregation == MetricAggregation.RATE:
            return len(recent) / window_seconds
        elif aggregation == MetricAggregation.P50:
            return self._percentile(recent, 50)
        elif aggregation == MetricAggregation.P95:
            return self._percentile(recent, 95)
        elif aggregation == MetricAggregation.P99:
            return self._percentile(recent, 99)
        else:
            return sum(recent)

    def _percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


class MetricsCollector:
    """
    Centralized metrics collection for AI agent system

    Example:
        collector = MetricsCollector()

        # Define metrics
        collector.register(Metric(
            name="agent_requests_total",
            description="Total agent requests",
            type=MetricType.COUNTER,
            labels=["agent_type", "status"]
        ))

        collector.register(Metric(
            name="agent_latency_ms",
            description="Agent response latency",
            type=MetricType.HISTOGRAM,
            unit="ms",
            buckets=[100, 250, 500, 1000, 2500, 5000]
        ))

        # Record metrics
        collector.increment("agent_requests_total", labels={"agent_type": "deepseek", "status": "success"})
        collector.observe("agent_latency_ms", 1234.5)

        # Query metrics
        stats = collector.get_stats()
    """

    # Pre-defined agent metrics
    AGENT_METRICS = [
        Metric(
            name="agent_requests_total",
            description="Total number of agent requests",
            type=MetricType.COUNTER,
            labels=["agent_type", "status", "channel"],
        ),
        Metric(
            name="agent_latency_ms",
            description="Agent response latency in milliseconds",
            type=MetricType.HISTOGRAM,
            unit="ms",
            buckets=[100, 250, 500, 1000, 2500, 5000, 10000],
        ),
        Metric(
            name="agent_tokens_used",
            description="Tokens used per request",
            type=MetricType.HISTOGRAM,
            unit="tokens",
            buckets=[100, 500, 1000, 2000, 4000, 8000],
        ),
        Metric(
            name="agent_errors_total",
            description="Total number of agent errors",
            type=MetricType.COUNTER,
            labels=["agent_type", "error_type"],
        ),
        Metric(
            name="agent_active_requests",
            description="Currently active requests",
            type=MetricType.GAUGE,
            labels=["agent_type"],
        ),
        Metric(
            name="memory_usage_bytes",
            description="Memory usage in bytes",
            type=MetricType.GAUGE,
            unit="bytes",
        ),
        Metric(
            name="consensus_confidence",
            description="Consensus decision confidence",
            type=MetricType.HISTOGRAM,
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
        ),
        Metric(
            name="deliberation_rounds",
            description="Number of deliberation rounds",
            type=MetricType.HISTOGRAM,
            buckets=[1, 2, 3, 4, 5],
        ),
        Metric(
            name="rlhf_reward_score",
            description="RLHF reward model scores",
            type=MetricType.HISTOGRAM,
            buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        ),
        Metric(
            name="memory_tier_items",
            description="Items in each memory tier",
            type=MetricType.GAUGE,
            labels=["tier"],
        ),
    ]

    def __init__(
        self,
        persist_path: str | None = None,
        retention_hours: int = 24,
        auto_register_defaults: bool = True,
    ):
        """
        Initialize metrics collector

        Args:
            persist_path: Path for metrics persistence
            retention_hours: Hours to retain metrics
            auto_register_defaults: Register default agent metrics
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.retention = timedelta(hours=retention_hours)

        self._metrics: dict[str, Metric] = {}
        self._series: dict[str, dict[str, MetricSeries]] = defaultdict(dict)
        self._lock = threading.RLock()

        # Callbacks for metric updates
        self._callbacks: list[Callable[[str, float, dict], None]] = []

        if auto_register_defaults:
            for metric in self.AGENT_METRICS:
                self.register(metric)

        logger.info(
            f"📊 MetricsCollector initialized with {len(self._metrics)} metrics"
        )

    def register(self, metric: Metric) -> None:
        """Register a new metric"""
        with self._lock:
            self._metrics[metric.name] = metric
            # Initialize empty series
            self._series[metric.name][""] = MetricSeries(metric=metric)

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric"""
        self._record(name, value, labels, is_increment=True)

    def set(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric value"""
        self._record(name, value, labels, is_set=True)

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Observe a value for histogram/summary"""
        self._record(name, value, labels)

    def _record(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        is_increment: bool = False,
        is_set: bool = False,
    ) -> None:
        """Internal record method"""
        with self._lock:
            if name not in self._metrics:
                logger.warning(f"Metric {name} not registered")
                return

            labels = labels or {}
            label_key = self._label_key(labels)

            if label_key not in self._series[name]:
                self._series[name][label_key] = MetricSeries(metric=self._metrics[name])

            series = self._series[name][label_key]

            if is_set:
                # For gauges, just record the value
                series.add_value(value, labels)
            elif is_increment:
                # For counters, add to running total
                series.add_value(value, labels)
            else:
                # For histograms/summaries
                series.add_value(value, labels)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(name, value, labels or {})
            except Exception as e:
                logger.warning(f"Metric callback error: {e}")

    def _label_key(self, labels: dict[str, str]) -> str:
        """Create consistent key from labels"""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def get(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        aggregation: MetricAggregation = MetricAggregation.SUM,
        window_seconds: int = 60,
    ) -> float:
        """Get aggregated metric value"""
        with self._lock:
            if name not in self._series:
                return 0.0

            label_key = self._label_key(labels or {})

            if label_key and label_key in self._series[name]:
                return self._series[name][label_key].get_aggregated(
                    aggregation, window_seconds
                )

            # Aggregate across all label combinations
            total = 0.0
            for series in self._series[name].values():
                total += series.get_aggregated(aggregation, window_seconds)
            return total

    def get_all(
        self,
        window_seconds: int = 60,
    ) -> dict[str, dict[str, Any]]:
        """Get all metrics with their values"""
        result = {}

        with self._lock:
            for name, label_series in self._series.items():
                metric = self._metrics.get(name)
                if not metric:
                    continue

                result[name] = {
                    "type": metric.type.value,
                    "description": metric.description,
                    "unit": metric.unit,
                    "series": {},
                }

                for label_key, series in label_series.items():
                    if metric.type == MetricType.COUNTER:
                        value = series.get_aggregated(
                            MetricAggregation.SUM, window_seconds
                        )
                    elif metric.type == MetricType.GAUGE:
                        # For gauges, get the latest value
                        value = series.values[-1].value if series.values else 0
                    else:
                        value = {
                            "count": series.count,
                            "sum": series.sum_value,
                            "avg": series.sum_value / max(series.count, 1),
                            "p50": series.get_aggregated(
                                MetricAggregation.P50, window_seconds
                            ),
                            "p95": series.get_aggregated(
                                MetricAggregation.P95, window_seconds
                            ),
                            "p99": series.get_aggregated(
                                MetricAggregation.P99, window_seconds
                            ),
                        }

                    result[name]["series"][label_key or "default"] = value

        return result

    def add_callback(self, callback: Callable[[str, float, dict], None]) -> None:
        """Add callback for metric updates"""
        self._callbacks.append(callback)

    def cleanup(self) -> int:
        """Remove old metric values beyond retention"""
        cutoff = datetime.now(UTC) - self.retention
        removed = 0

        with self._lock:
            for label_series in self._series.values():
                for series in label_series.values():
                    original_count = len(series.values)
                    series.values = [v for v in series.values if v.timestamp >= cutoff]
                    removed += original_count - len(series.values)

        return removed

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        with self._lock:
            for name, label_series in self._series.items():
                metric = self._metrics.get(name)
                if not metric:
                    continue

                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} {metric.type.value}")

                for label_key, series in label_series.items():
                    labels_str = "{" + label_key + "}" if label_key else ""

                    if metric.type == MetricType.HISTOGRAM:
                        # Export histogram buckets
                        for bucket, count in sorted(series.histogram_counts.items()):
                            lines.append(
                                f'{name}_bucket{{le="{bucket}"{label_key and "," + label_key}}} {count}'
                            )
                        lines.append(f"{name}_sum{labels_str} {series.sum_value}")
                        lines.append(f"{name}_count{labels_str} {series.count}")
                    else:
                        value = series.values[-1].value if series.values else 0
                        lines.append(f"{name}{labels_str} {value}")

        return "\n".join(lines)

    def export_json(self) -> str:
        """Export metrics as JSON"""
        return json.dumps(self.get_all(), indent=2)

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics"""
        total_values = 0
        with self._lock:
            for label_series in self._series.values():
                for series in label_series.values():
                    total_values += len(series.values)

        return {
            "registered_metrics": len(self._metrics),
            "total_series": sum(len(s) for s in self._series.values()),
            "total_values": total_values,
            "callbacks": len(self._callbacks),
        }


# Global collector instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


__all__ = [
    "Metric",
    "MetricAggregation",
    "MetricSeries",
    "MetricType",
    "MetricValue",
    "MetricsCollector",
    "get_metrics_collector",
]
