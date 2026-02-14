"""Trading-Specific MCP Tools - Re-export Facade.

All tool implementations live in backend.agents.mcp.tools sub-modules.
This file re-exports every public symbol so existing imports work unchanged.
"""

from __future__ import annotations

from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry
from backend.agents.mcp.tools import (
    analyze_trend,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_position_size,
    calculate_risk_reward,
    calculate_rsi,
    check_system_health,
    evolve_strategy,
    find_support_resistance,
    generate_backtest_report,
    get_backtest_metrics,
    list_strategies,
    log_agent_action,
    run_backtest,
    validate_strategy,
)

registry = get_tool_registry()

__all__ = [
    "analyze_trend",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_macd",
    "calculate_position_size",
    "calculate_risk_reward",
    "calculate_rsi",
    "check_system_health",
    "evolve_strategy",
    "find_support_resistance",
    "generate_backtest_report",
    "get_backtest_metrics",
    "list_strategies",
    "log_agent_action",
    "registry",
    "run_backtest",
    "validate_strategy",
]

logger.info(
    "Trading MCP Tools registered: "
    + f"{len(registry.list_tools(category='indicators'))} indicators, "
    + f"{len(registry.list_tools(category='analysis'))} analysis, "
    + f"{len(registry.list_tools(category='risk'))} risk tools, "
    + f"{len(registry.list_tools(category='backtesting'))} backtesting, "
    + f"{len(registry.list_tools(category='monitoring'))} monitoring"
)
