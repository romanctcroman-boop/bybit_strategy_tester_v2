"""
Trading MCP Tools — Category Modules

Split from monolithic trading_tools.py (1353 LOC) for maintainability.
Each module auto-registers tools with the global registry on import.

Modules:
    indicators       — RSI, MACD, Bollinger, ATR, trend analysis, S/R
    risk             — Position sizing, risk-reward calculation
    backtest         — run_backtest, get_backtest_metrics
    strategy         — list/validate/evolve strategies
    strategy_builder — Visual Strategy Builder (create/add blocks/connect/validate/backtest)
    system           — Health check, report generation, agent logging
"""

from backend.agents.mcp.tools.backtest import get_backtest_metrics, run_backtest
from backend.agents.mcp.tools.indicators import (
    analyze_trend,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_rsi,
    find_support_resistance,
)
from backend.agents.mcp.tools.risk import calculate_position_size, calculate_risk_reward
from backend.agents.mcp.tools.strategy import (
    evolve_strategy,
    list_strategies,
    validate_strategy,
)
from backend.agents.mcp.tools.strategy_builder import (
    builder_add_block,
    builder_analyze_strategy,
    builder_connect_blocks,
    builder_create_strategy,
    builder_delete_strategy,
    builder_disconnect_blocks,
    builder_export_strategy,
    builder_generate_code,
    builder_get_block_library,
    builder_get_optimizable_params,
    builder_get_strategy,
    builder_get_versions,
    builder_import_strategy,
    builder_instantiate_template,
    builder_list_strategies,
    builder_list_templates,
    builder_remove_block,
    builder_revert_version,
    builder_run_backtest,
    builder_update_block_params,
    builder_update_strategy,
    builder_validate_strategy,
)
from backend.agents.mcp.tools.system import (
    check_system_health,
    generate_backtest_report,
    log_agent_action,
)

__all__ = [
    "analyze_trend",
    "builder_add_block",
    "builder_analyze_strategy",
    "builder_connect_blocks",
    "builder_create_strategy",
    "builder_delete_strategy",
    "builder_disconnect_blocks",
    "builder_export_strategy",
    "builder_generate_code",
    "builder_get_block_library",
    "builder_get_optimizable_params",
    "builder_get_strategy",
    "builder_get_versions",
    "builder_import_strategy",
    "builder_instantiate_template",
    "builder_list_strategies",
    "builder_list_templates",
    "builder_remove_block",
    "builder_revert_version",
    "builder_run_backtest",
    "builder_update_block_params",
    "builder_update_strategy",
    "builder_validate_strategy",
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
    "run_backtest",
    "validate_strategy",
]
