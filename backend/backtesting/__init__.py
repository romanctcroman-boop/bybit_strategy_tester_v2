"""
Backtesting Module

High-performance backtesting engine based on vectorbt.
Provides strategy testing, performance metrics, and equity curve generation.
"""

from backend.backtesting.engine import BacktestEngine, get_engine
from backend.backtesting.models import (
    BacktestConfig,
    BacktestCreateRequest,
    BacktestListResponse,
    BacktestResult,
    BacktestStatus,
    EquityCurve,
    PerformanceMetrics,
    StrategyType,
    TradeRecord,
)
from backend.backtesting.service import BacktestService, get_backtest_service
from backend.backtesting.strategies import (
    BaseStrategy,
    BollingerBandsStrategy,
    MACDStrategy,
    RSIStrategy,
    SMAStrategy,
    get_strategy,
    list_available_strategies,
)
from backend.backtesting.optimizer import (
    UniversalOptimizer,
    OptimizationResult,
    optimize,
)

__all__ = [
    # Engine
    "BacktestEngine",
    "get_engine",
    # Service
    "BacktestService",
    "get_backtest_service",
    # Models
    "BacktestConfig",
    "BacktestCreateRequest",
    "BacktestListResponse",
    "BacktestResult",
    "BacktestStatus",
    "TradeRecord",
    "PerformanceMetrics",
    "EquityCurve",
    "StrategyType",
    # Strategies
    "BaseStrategy",
    "SMAStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "BollingerBandsStrategy",
    "get_strategy",
    "list_available_strategies",
    # Optimizers
    "UniversalOptimizer",
    "OptimizationResult",
    "optimize",
]
