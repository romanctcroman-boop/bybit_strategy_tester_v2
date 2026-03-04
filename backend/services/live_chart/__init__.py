"""
Live Chart Streaming Service.

Provides real-time OHLCV data via Bybit WebSocket → Server-Sent Events (SSE).

Architecture:
    Bybit WS → LiveChartSessionManager → asyncio.Queue → SSE → Browser

Fan-out: one WebSocket per (symbol, interval) → N SSE subscribers.
"""

from backend.services.live_chart.session_manager import (
    LIVE_CHART_MANAGER,
    LiveChartSession,
    LiveChartSessionManager,
)
from backend.services.live_chart.signal_service import LiveSignalService

__all__ = [
    "LIVE_CHART_MANAGER",
    "LiveChartSession",
    "LiveChartSessionManager",
    "LiveSignalService",
]
