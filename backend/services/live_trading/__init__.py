"""
Live Trading Module for Bybit Strategy Tester V2.

This module provides real-time trading capabilities:
- WebSocket connections to Bybit V5 API
- Order execution and management
- Position tracking
- Risk management integration
- Strategy runner for live trading
- Graceful shutdown handling

Components:
- bybit_websocket: WebSocket client for real-time data
- order_executor: Order placement and management
- position_manager: Position tracking and P&L
- strategy_runner: Live strategy execution engine
- graceful_shutdown: Graceful shutdown manager
"""

from backend.services.live_trading.bybit_websocket import BybitWebSocketClient
from backend.services.live_trading.graceful_shutdown import (
    GracefulShutdownManager,
    ShutdownContext,
    ShutdownState,
    setup_graceful_shutdown,
)
from backend.services.live_trading.order_executor import OrderExecutor
from backend.services.live_trading.position_manager import PositionManager
from backend.services.live_trading.strategy_runner import LiveStrategyRunner

__all__ = [
    "BybitWebSocketClient",
    "GracefulShutdownManager",
    "LiveStrategyRunner",
    "OrderExecutor",
    "PositionManager",
    "ShutdownContext",
    "ShutdownState",
    "setup_graceful_shutdown",
]
