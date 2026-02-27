"""
Unified API Module

Unified interface for backtest -> live trading.

@version: 1.0.0
@date: 2026-02-26
"""

from .interface import (
    DataProvider,
    HistoricalDataProvider,
    LiveDataProvider,
    LiveExecutor,
    OrderExecutor,
    SimulatedExecutor,
    UnifiedTradingAPI,
)

__all__ = [
    "UnifiedTradingAPI",
    "DataProvider",
    "HistoricalDataProvider",
    "LiveDataProvider",
    "OrderExecutor",
    "SimulatedExecutor",
    "LiveExecutor",
]
