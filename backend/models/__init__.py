"""
Database Models - SQLAlchemy ORM models
Re-exports models from backend.database.models for backward compatibility.
"""

# Re-export real SQLAlchemy models from backend.database.models
from backend.database.models import (
    Backtest,
    BacktestStatus,
    ChatConversation,
    Optimization,
    OptimizationStatus,
    OptimizationType,
    Strategy,
    StrategyStatus,
    StrategyType,
    Trade,
    TradeSide,
    TradeStatus,
)

# Re-export bybit_kline_audit model as MarketData alias for backward compatibility
from backend.models.bybit_kline_audit import BybitKlineAudit

# MarketData is an alias for BybitKlineAudit - all market data uses this table
MarketData = BybitKlineAudit

# OptimizationResult is stored within Optimization.results (JSON column)
# This alias is for backward compatibility where separate model was expected
OptimizationResult = Optimization

__all__ = [
    "Backtest",
    "BacktestStatus",
    "BybitKlineAudit",
    "ChatConversation",
    "MarketData",  # Alias for BybitKlineAudit
    "Optimization",
    "OptimizationResult",  # Alias for Optimization
    "OptimizationStatus",
    "OptimizationType",
    "Strategy",
    "StrategyStatus",
    "StrategyType",
    "Trade",
    "TradeSide",
    "TradeStatus",
]
