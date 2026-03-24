"""
Strategy Builder package.

Provides StrategyBuilderAdapter and related helpers for converting
visual block graphs into executable backtesting strategies.

Modules:
    adapter.py       — StrategyBuilderAdapter (main orchestrator, ~1400 lines)
    block_executor.py — pure execution functions (conditions, logic, filters, ...)
    graph_parser.py  — connection normalization (parse_source_id, etc.)
    signal_router.py — PORT_ALIASES, SIGNAL_PORT_ALIASES constants
    topology.py      — BLOCK_CATEGORY_MAP, infer_category, build_execution_order
    utils.py         — shared helpers: _param, _clamp_period

Public API (backward-compatible with original strategy_builder_adapter module):
    StrategyBuilderAdapter  — main adapter class
    _param                  — helper: get param by key with fallback
    _clamp_period           — helper: clamp numeric period to safe range
"""

from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.backtesting.strategy_builder.block_executor import (
    apply_signal_memory,
    execute_action,
    execute_close_condition,
    execute_condition,
    execute_divergence,
    execute_exit,
    execute_filter,
    execute_input,
    execute_logic,
    execute_position_sizing,
    execute_price_action,
    execute_signal_block,
    execute_time_filter,
    extend_dual_signal_memory,
)
from backend.backtesting.strategy_builder.graph_parser import normalize_connections
from backend.backtesting.strategy_builder.signal_router import PORT_ALIASES, SIGNAL_PORT_ALIASES
from backend.backtesting.strategy_builder.topology import (
    BLOCK_CATEGORY_MAP,
    build_execution_order,
    infer_category,
)
from backend.backtesting.strategy_builder.utils import _clamp_period, _param

__all__ = [
    "BLOCK_CATEGORY_MAP",
    "PORT_ALIASES",
    "SIGNAL_PORT_ALIASES",
    "StrategyBuilderAdapter",
    "_clamp_period",
    "_param",
    "apply_signal_memory",
    "build_execution_order",
    "execute_action",
    "execute_close_condition",
    "execute_condition",
    "execute_divergence",
    "execute_exit",
    "execute_filter",
    "execute_input",
    "execute_logic",
    "execute_position_sizing",
    "execute_price_action",
    "execute_signal_block",
    "execute_time_filter",
    "extend_dual_signal_memory",
    "infer_category",
    "normalize_connections",
]
