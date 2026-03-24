"""
Strategy Builder Adapter - backward-compatibility stub.

The implementation has been moved to:
    backend/backtesting/strategy_builder/adapter.py

All existing imports of the form:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
    from backend.backtesting.strategy_builder_adapter import _param, _clamp_period

continue to work unchanged via this re-export stub.
"""

from backend.backtesting.strategy_builder.adapter import (
    StrategyBuilderAdapter,
    _clamp_period,
    _param,
)

__all__ = [
    "StrategyBuilderAdapter",
    "_clamp_period",
    "_param",
]
