"""
AI Agent Dashboard Module

Provides REST API and WebSocket endpoints for monitoring.
"""

from .api import router, broadcast_metric_update, broadcast_alert

__all__ = [
    "router",
    "broadcast_metric_update",
    "broadcast_alert",
]
