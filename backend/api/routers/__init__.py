"""
API Routers - Organizing FastAPI routes by domain
"""

# Re-export available routers
from . import (
    active_deals,
    dashboard_metrics,
    executions,
    health,
    health_monitoring,
    marketdata,
    reasoning,
)

__all__ = [
    "active_deals",
    "dashboard_metrics",
    "executions",
    "health",
    "health_monitoring",
    "marketdata",
    "reasoning",
]
