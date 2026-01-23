"""
Advanced Backtesting Module

Provides comprehensive backtesting capabilities:
- Realistic execution simulation (slippage, fees, fills)
- Multi-asset portfolio backtesting
- Custom metrics and benchmarks
- Trade analytics and attribution
- Regime-aware performance analysis

Usage:
    from backend.services.advanced_backtesting import (
        AdvancedBacktestEngine,
        SlippageModel,
        BacktestAnalytics,
        PortfolioBacktester,
    )
"""

from .analytics import (
    BacktestAnalytics,
    DrawdownAnalysis,
    PerformanceAttribution,
    RegimeAnalysis,
    TradeAnalysis,
)
from .engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
    ExecutionSimulator,
    RealisticFillModel,
)
from .metrics import (
    BenchmarkComparison,
    CustomMetrics,
    RiskAdjustedMetrics,
    RollingMetrics,
)
from .portfolio import (
    AssetAllocation,
    CorrelationAnalysis,
    PortfolioBacktester,
    RebalanceStrategy,
)
from .slippage import (
    OrderBookSlippage,
    SlippageModel,
    VolatilitySlippage,
    VolumeImpactSlippage,
)

__all__ = [
    # Engine
    "AdvancedBacktestEngine",
    "BacktestConfig",
    "ExecutionSimulator",
    "RealisticFillModel",
    # Slippage
    "SlippageModel",
    "VolumeImpactSlippage",
    "VolatilitySlippage",
    "OrderBookSlippage",
    # Analytics
    "BacktestAnalytics",
    "TradeAnalysis",
    "PerformanceAttribution",
    "RegimeAnalysis",
    "DrawdownAnalysis",
    # Portfolio
    "PortfolioBacktester",
    "AssetAllocation",
    "CorrelationAnalysis",
    "RebalanceStrategy",
    # Metrics
    "CustomMetrics",
    "RiskAdjustedMetrics",
    "BenchmarkComparison",
    "RollingMetrics",
]
