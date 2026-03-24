"""
Live Chart package.

Provides real-time chart streaming via WebSocket → SSE fan-out.

Exports:
    LIVE_CHART_MANAGER  — singleton LiveChartSessionManager
    LiveSignalService   — per-session signal computation
"""

from backend.services.live_chart.session_manager import LIVE_CHART_MANAGER, LiveChartSessionManager
from backend.services.live_chart.signal_service import LiveSignalService

__all__ = [
    "LIVE_CHART_MANAGER",
    "LiveChartSessionManager",
    "LiveSignalService",
]
