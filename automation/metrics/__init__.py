"""
Prometheus Metrics Module
=========================

Exports custom metrics for monitoring automation platform.
"""

from .prometheus_exporter import PrometheusExporter, start_metrics_server
from .custom_metrics import (
    test_watcher_metrics,
    audit_agent_metrics,
    safe_async_bridge_metrics,
    api_metrics
)

__all__ = [
    'PrometheusExporter',
    'start_metrics_server',
    'test_watcher_metrics',
    'audit_agent_metrics',
    'safe_async_bridge_metrics',
    'api_metrics',
]
