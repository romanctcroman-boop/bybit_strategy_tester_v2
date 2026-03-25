"""
AI Agent Dashboard Module

Provides REST API and WebSocket endpoints for monitoring.
"""

from .api import broadcast_alert, broadcast_metric_update, router

__all__ = [
    "broadcast_alert",
    "broadcast_metric_update",
    "router",
]
