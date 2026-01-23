"""
Monitoring & Observability for AI Agent System

This package provides comprehensive monitoring capabilities:
- Real-time metrics collection and aggregation
- Distributed tracing for multi-agent interactions
- Alerting and anomaly detection
- Dashboard data export
- Performance profiling

Based on observability best practices:
- OpenTelemetry patterns
- Prometheus-style metrics
- Structured logging
"""

from backend.agents.monitoring.metrics_collector import (
    MetricsCollector,
    Metric,
    MetricType,
    MetricAggregation,
)
from backend.agents.monitoring.tracing import (
    DistributedTracer,
    Span,
    SpanContext,
    TraceExporter,
)
from backend.agents.monitoring.alerting import (
    AlertManager,
    Alert,
    AlertSeverity,
    AlertRule,
)
from backend.agents.monitoring.dashboard import (
    DashboardDataProvider,
    DashboardWidget,
    WidgetType,
)

__all__ = [
    "MetricsCollector",
    "Metric",
    "MetricType",
    "MetricAggregation",
    "DistributedTracer",
    "Span",
    "SpanContext",
    "TraceExporter",
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "AlertRule",
    "DashboardDataProvider",
    "DashboardWidget",
    "WidgetType",
]
