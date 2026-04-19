"""
Strategy Builder API Router package.

Assembles the strategy builder router and re-exports all public symbols
that tests and other modules import from this package.

Public API (backward-compatible with original strategy_builder module):
    router                       — the FastAPI router (mounted at /strategy-builder)
    All Pydantic models used by tests
"""

from backend.api.routers.strategy_builder.router import (
    # Request/Response models imported by tests
    AddBlockRequest,
    AdvancedOptions,
    BacktestRequest,
    BlockResponse,
    BuilderOptimizationRequest,
    ConnectBlocksRequest,
    CreateStrategyRequest,
    DataPeriod,
    EvaluationCriteria,
    GenerateCodeFromDbRequest,
    GenerateCodeRequest,
    InstantiateTemplateRequest,
    MetricConstraint,
    OptimizationConfig,
    OptimizationLimits,
    ParamRangeSpec,
    SortSpec,
    StrategyGraph,
    StrategyResponse,
    UpdateBlockRequest,
    code_generator,
    indicator_library,
    # FastAPI router
    router,
    # Singleton services — tests patch these via sb_router.strategy_builder.strategies etc.
    strategy_builder,
    template_manager,
    validator,
)
from backend.services.adapters.bybit import BybitAdapter

__all__ = [
    "AddBlockRequest",
    "AdvancedOptions",
    "BacktestRequest",
    "BlockResponse",
    "BuilderOptimizationRequest",
    "BybitAdapter",
    "ConnectBlocksRequest",
    "CreateStrategyRequest",
    "DataPeriod",
    "EvaluationCriteria",
    "GenerateCodeFromDbRequest",
    "GenerateCodeRequest",
    "InstantiateTemplateRequest",
    "MetricConstraint",
    "OptimizationConfig",
    "OptimizationLimits",
    "ParamRangeSpec",
    "SortSpec",
    "StrategyGraph",
    "StrategyResponse",
    "UpdateBlockRequest",
    "code_generator",
    "get_db",
    "indicator_library",
    "router",
    # Singleton services — exposed for test patching
    "strategy_builder",
    "template_manager",
    "validator",
]

# Re-export get_db so that unittest.mock.patch("backend.api.routers.strategy_builder.get_db")
# still works after the monolith was moved to the sub-package.
from backend.database import get_db
