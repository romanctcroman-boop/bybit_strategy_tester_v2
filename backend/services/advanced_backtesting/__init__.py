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
    AllocationMethod,
    AssetAllocation,
    CorrelationAnalysis,
    PortfolioBacktester,
    RebalanceStrategy,
    aggregate_multi_symbol_equity,
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
    "AllocationMethod",
    "AssetAllocation",
    # Analytics
    "BacktestAnalytics",
    "BacktestConfig",
    "BenchmarkComparison",
    "CorrelationAnalysis",
    # Metrics
    "CustomMetrics",
    "DrawdownAnalysis",
    "ExecutionSimulator",
    "OrderBookSlippage",
    "PerformanceAttribution",
    "PortfolioBacktester",
    "RealisticFillModel",
    "RebalanceStrategy",
    "RegimeAnalysis",
    "RiskAdjustedMetrics",
    "RollingMetrics",
    # Slippage
    "SlippageModel",
    "TradeAnalysis",
    "VolatilitySlippage",
    "VolumeImpactSlippage",
    # Portfolio
    "aggregate_multi_symbol_equity",
]
