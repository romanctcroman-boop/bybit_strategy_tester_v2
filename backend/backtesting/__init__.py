"""
Backtesting Module

High-performance backtesting engine based on vectorbt.
Provides strategy testing, performance metrics, and equity curve generation.

NOTE: Heavy imports (optimizer, walk_forward, position_sizing) are LAZY LOADED
to speed up application startup. Import them directly when needed:

    from backend.backtesting.optimizer import UniversalOptimizer
    from backend.backtesting.walk_forward import WalkForwardOptimizer
    from backend.backtesting.position_sizing import KellyCalculator
"""

# =============================================================================
# FAST IMPORTS - These are lightweight and needed by most code paths
# =============================================================================

# Engine and service - commonly used
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

# Multi-Timeframe module - needed for MTF backtests
from backend.backtesting.mtf import (
    BTCCorrelationFilter,
    HTFFilter,
    HTFTrendFilter,
    MTFData,
    MTFDataLoader,
    create_htf_index_map,
    generate_mtf_rsi_signals,
    generate_mtf_sma_crossover_signals,
)
from backend.backtesting.service import BacktestService, get_backtest_service

# Strategies - lightweight
from backend.backtesting.strategies import (
    BaseStrategy,
    BollingerBandsStrategy,
    MACDStrategy,
    RSIStrategy,
    SMAStrategy,
    get_strategy,
    list_available_strategies,
)

# =============================================================================
# LAZY IMPORTS - Heavy modules loaded only when accessed via __getattr__
# This speeds up startup by ~30-60 seconds (GPU/Numba init deferred)
# =============================================================================


def __getattr__(name: str):
    """Lazy load heavy modules only when actually needed."""
    # Optimizer imports (heavy - loads GPU/Numba)
    if name in ("OptimizationResult", "UniversalOptimizer", "optimize"):
        from backend.backtesting.optimizer import (
            OptimizationResult,
            UniversalOptimizer,
            optimize,
        )

        return locals()[name]

    # Position sizing imports (moderate)
    if name in ("IndicatorCache", "KellyCalculator", "MonteCarloAnalyzer", "TradeResult"):
        from backend.backtesting.position_sizing import (
            IndicatorCache,
            KellyCalculator,
            MonteCarloAnalyzer,
            TradeResult,
        )

        return locals()[name]

    # Walk-forward imports (moderate)
    if name in ("WalkForwardOptimizer", "WalkForwardResult", "WalkForwardWindow"):
        from backend.backtesting.walk_forward import (
            WalkForwardOptimizer,
            WalkForwardResult,
            WalkForwardWindow,
        )

        return locals()[name]

    raise AttributeError(f"module 'backend.backtesting' has no attribute '{name}'")


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
    # Position Sizing & Analysis
    "KellyCalculator",
    "MonteCarloAnalyzer",
    "IndicatorCache",
    "TradeResult",
    # Walk-Forward Optimization
    "WalkForwardOptimizer",
    "WalkForwardResult",
    "WalkForwardWindow",
    # Multi-Timeframe
    "MTFData",
    "MTFDataLoader",
    "create_htf_index_map",
    "HTFFilter",
    "HTFTrendFilter",
    "BTCCorrelationFilter",
    "generate_mtf_rsi_signals",
    "generate_mtf_sma_crossover_signals",
]
