"""
Strategy Builder package.

Provides StrategyBuilderAdapter and related helpers for converting
visual block graphs into executable backtesting strategies.

Public API (backward-compatible with original strategy_builder_adapter module):
    StrategyBuilderAdapter  — main adapter class
    _param                  — helper: get param by key with fallback
    _clamp_period           — helper: clamp numeric period to safe range
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
