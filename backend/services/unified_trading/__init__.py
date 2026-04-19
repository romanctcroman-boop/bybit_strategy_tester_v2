"""
Unified Trading API — Backtest / Paper / Live.

Единые абстракции DataProvider и OrderExecutor для переключения режимов:
- Backtest: HistoricalDataProvider + SimulatedExecutor
- Paper: LiveDataProvider + SimulatedExecutor
- Live: LiveDataProvider + BybitExecutor (OrderExecutor from live_trading)
"""

from backend.services.unified_trading.historical_data_provider import (
    HistoricalDataProvider,
)
from backend.services.unified_trading.interfaces import (
    DataProvider,
    OrderExecutorInterface,
)
from backend.services.unified_trading.live_data_provider import LiveDataProvider
from backend.services.unified_trading.simulated_executor import SimulatedExecutor
from backend.services.unified_trading.strategy_runner import StrategyRunner

__all__ = [
    "DataProvider",
    "HistoricalDataProvider",
    "LiveDataProvider",
    "OrderExecutorInterface",
    "SimulatedExecutor",
    "StrategyRunner",
]
