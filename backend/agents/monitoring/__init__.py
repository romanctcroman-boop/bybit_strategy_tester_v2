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

from backend.agents.monitoring.alerting import (
    Alert,
    AlertManager,
    AlertRule,
    AlertSeverity,
)
from backend.agents.monitoring.dashboard import (
    DashboardDataProvider,
    DashboardWidget,
    WidgetType,
)
from backend.agents.monitoring.metrics_collector import (
    Metric,
    MetricAggregation,
    MetricsCollector,
    MetricType,
)
from backend.agents.monitoring.system_monitor import (
    SystemMonitor,
    get_system_monitor,
)
from backend.agents.monitoring.tracing import (
    DistributedTracer,
    Span,
    SpanContext,
    TraceExporter,
)

__all__ = [
    "Alert",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "DashboardDataProvider",
    "DashboardWidget",
    "DistributedTracer",
    "Metric",
    "MetricAggregation",
    "MetricType",
    "MetricsCollector",
    "Span",
    "SpanContext",
    "SystemMonitor",
    "TraceExporter",
    "WidgetType",
    "get_system_monitor",
]
