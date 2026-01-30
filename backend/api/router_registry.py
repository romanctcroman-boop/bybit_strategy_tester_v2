"""
Router registry module for FastAPI application.

⚠️ DEPRECATED: This module is NOT currently used.
Routers are registered directly in backend/api/app.py (lines 370-415).
This file exists for future refactoring but register_all_routers() is never called.

TODO: Either:
  1. Migrate app.py to use this registry (cleaner, more maintainable)
  2. Remove this file entirely if migration is not planned

See: docs/audits/API_MIDDLEWARE_AUDIT.md - P1 task "router_registry.py dead code"

Historical Usage (not currently implemented):
    from backend.api.router_registry import register_all_routers
    register_all_routers(app)
"""

import logging
import os
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Issue deprecation warning when imported
warnings.warn(
    "router_registry.py is deprecated and not used. "
    "Routers are registered directly in app.py. "
    "See API_MIDDLEWARE_AUDIT.md for details.",
    DeprecationWarning,
    stacklevel=2,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("uvicorn.error")


@dataclass
class RouterConfig:
    """Configuration for a single router."""

    module_path: str  # e.g., "backend.api.routers.health"
    router_attr: str = "router"  # attribute name in module
    prefix: str = ""  # URL prefix
    tags: list[str] | None = None  # OpenAPI tags
    include_in_schema: bool = True
    condition: str | None = None  # env var condition (e.g., "USE_MOCK_BACKTESTS")


# ============================================================================
# ROUTER DEFINITIONS - Organized by category
# ============================================================================

# Core API routers (always loaded)
CORE_ROUTERS: list[RouterConfig] = [
    # Security (must be first)
    RouterConfig("backend.api.routers.security", prefix="/api/v1", tags=["security"]),
    # Strategies
    RouterConfig("backend.api.routers.strategies", prefix="/api/v1/strategies", tags=["strategies"]),
    # Backtests
    RouterConfig("backend.api.routers.backtests", prefix="/api/v1/backtests", tags=["backtests"]),
    # Market Data
    RouterConfig("backend.api.routers.marketdata", prefix="/api/v1/marketdata", tags=["marketdata"]),
    RouterConfig("backend.api.routers.tick_charts", prefix="/api/v1/marketdata", tags=["tick-charts"]),
    # Admin
    RouterConfig("backend.api.routers.admin", prefix="/api/v1/admin", tags=["admin"]),
    # Optimizations
    RouterConfig("backend.api.routers.optimizations", prefix="/api/v1/optimizations", tags=["optimizations"]),
]

# Health & Monitoring routers
HEALTH_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.health", prefix="/api/v1", tags=["health"]),
    RouterConfig("backend.api.routers.health", prefix="", tags=["k8s-probes"], include_in_schema=False),
    RouterConfig("backend.api.routers.health_monitoring", prefix="/api/v1", tags=["health-monitoring"]),
    RouterConfig("backend.api.routers.monitoring", prefix="", tags=["monitoring"]),
    RouterConfig("backend.api.routers.slo_error_budget", prefix="/api/v1", tags=["slo-error-budget"]),
]

# Trading routers
TRADING_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.live", prefix="/api/v1", tags=["live"]),
    RouterConfig("backend.api.routers.live", prefix="/ws", tags=["live-ws"]),
    RouterConfig("backend.api.routers.live_trading", prefix="/api/v1/live", tags=["live-trading"]),
    RouterConfig("backend.api.routers.paper_trading", prefix="/api/v1", tags=["paper-trading"]),
    RouterConfig("backend.api.routers.active_deals", prefix="/api/v1/active-deals", tags=["active-deals"]),
    RouterConfig("backend.api.routers.trading_halt", prefix="/api/v1", tags=["trading-halt"]),
]

# Strategy management routers
STRATEGY_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.strategy_library", prefix="/api/v1/strategy-library", tags=["strategy-library"]),
    RouterConfig("backend.api.routers.strategy_builder", prefix="/api/v1", tags=["strategy-builder"]),
    RouterConfig("backend.api.routers.strategy_isolation", prefix="/api/v1", tags=["strategy-isolation"]),
    RouterConfig("backend.api.routers.strategy_templates", prefix="/api/v1", tags=["strategy-templates"]),
    RouterConfig("backend.api.routers.marketplace", prefix="/api/v1", tags=["marketplace"]),
]

# Risk & Analysis routers
RISK_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.risk_management", prefix="/api/v1/risk-management", tags=["risk-management"]),
    RouterConfig("backend.api.routers.risk", prefix="/api/v1", tags=["risk"]),
    RouterConfig("backend.api.routers.market_regime", prefix="/api/v1", tags=["market-regime"]),
    RouterConfig("backend.api.routers.monte_carlo", prefix="/api/v1", tags=["monte-carlo"]),
    RouterConfig("backend.api.routers.walk_forward", prefix="/api/v1", tags=["walk-forward"]),
    RouterConfig("backend.api.routers.advanced_backtesting", prefix="/api/v1", tags=["advanced-backtesting"]),
]

# AI & Agents routers
AI_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.ai", prefix="/api/v1", tags=["ai"]),
    RouterConfig("backend.api.routers.agents", prefix="/api/v1/agents", tags=["agents"]),
    RouterConfig("backend.api.routers.agents_advanced", prefix="/api/v1/agents/advanced", tags=["agents-advanced"]),
    RouterConfig("backend.api.routers.ai_strategy_generator", prefix="/api/v1", tags=["ai-strategy-generator"]),
    RouterConfig("backend.api.routers.perplexity", prefix="/api/v1", tags=["perplexity"]),
    RouterConfig("backend.api import agent_to_agent_api", prefix="/api/v1/agents", tags=["agents"]),
    RouterConfig("backend.api import orchestrator", prefix="/api/v1/orchestrator", tags=["orchestrator"]),
]

# ML & Analytics routers
ML_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.enhanced_ml", prefix="", tags=["machine-learning"]),
    RouterConfig("backend.api.routers.inference", prefix="/api/v1", tags=["inference"]),
    RouterConfig("backend.api.routers.metrics", prefix="/api/v1", tags=["metrics"]),
    RouterConfig("backend.api.routers.anomaly_detection", prefix="/api/v1", tags=["anomaly-detection"]),
]

# Dashboard routers
DASHBOARD_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.dashboard", prefix="", tags=["dashboard"]),
    RouterConfig("backend.api.routers.dashboard_metrics", prefix="/api/v1", tags=["dashboard-metrics"]),
    RouterConfig("backend.api.routers.dashboard_improvements", prefix="/api/v1", tags=["dashboard-improvements"]),
]

# Utility routers
UTILITY_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.alerts", prefix="/api/v1", tags=["alerts"]),
    RouterConfig("backend.api.routers.wizard", prefix="/api/v1/wizard", tags=["wizard"]),
    RouterConfig("backend.api.routers.bots", prefix="/api/v1/bots", tags=["bots"]),
    RouterConfig("backend.api.routers.csv_export", prefix="/api/v1", tags=["csv-export"]),
    RouterConfig("backend.api.routers.context", prefix="/api/v1", tags=["context"]),
    RouterConfig("backend.api.routers.file_ops", prefix="/api/v1", tags=["file-ops"]),
    RouterConfig("backend.api.routers.test_runner", prefix="/api/v1", tags=["tests"]),
    RouterConfig("backend.api.routers.test", prefix="/api/v1", tags=["testing"]),
    RouterConfig("backend.api.routers.cache", prefix="/api/v1", tags=["cache"]),
    RouterConfig("backend.api.routers.chat_history", prefix="/api/v1", tags=["chat-history"]),
    RouterConfig("backend.api.routers.queue", prefix="/api/v1", tags=["queue"]),
    RouterConfig("backend.api.routers.executions", prefix="/api/v1", tags=["executions"]),
]

# Infrastructure routers (Phase 4-5)
INFRA_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.routers.circuit_breakers", prefix="/api/v1", tags=["circuit-breakers"]),
    RouterConfig("backend.api.routers.tracing", prefix="/api/v1", tags=["tracing"]),
    RouterConfig("backend.api.routers.orchestration", prefix="/api/v1", tags=["orchestration"]),
    RouterConfig("backend.api.routers.degradation", prefix="/api/v1", tags=["degradation"]),
    RouterConfig("backend.api.routers.chaos", prefix="/api/v1", tags=["chaos"]),
    RouterConfig("backend.api.routers.key_rotation", prefix="/api/v1", tags=["key-rotation"]),
    RouterConfig("backend.api.routers.data_quality", prefix="/api/v1", tags=["data-quality"]),
    RouterConfig("backend.api.routers.synthetic_monitoring", prefix="/api/v1", tags=["synthetic-monitoring"]),
    RouterConfig("backend.api.routers.property_testing", prefix="/api/v1", tags=["property-testing"]),
    RouterConfig("backend.api.routers.rate_limiting", prefix="/api/v1", tags=["rate-limiting"]),
    RouterConfig("backend.api.routers.db_metrics", prefix="/api/v1", tags=["db-metrics"]),
    RouterConfig("backend.api.routers.kms", prefix="", tags=["kms"]),
    RouterConfig("backend.api.routers.secrets_scanner", prefix="", tags=["secrets-scanner"]),
    RouterConfig("backend.api.routers.state_management", prefix="/api/v1", tags=["state-management"]),
    RouterConfig("backend.api.routers.cache_warming", prefix="/api/v1", tags=["cache-warming"]),
    RouterConfig("backend.api.routers.ab_testing", prefix="/api/v1", tags=["ab-testing"]),
]

# Cost & Rate Limit Dashboard (from backend.api directly)
API_MODULE_ROUTERS: list[RouterConfig] = [
    RouterConfig("backend.api.cost_dashboard", prefix="", tags=["costs"]),
    RouterConfig("backend.api.streaming", prefix="", tags=["streaming"]),
    RouterConfig("backend.api.rate_limit_dashboard", prefix="", tags=["rate-limits"]),
]


def _load_router(config: RouterConfig):
    """
    Dynamically load a router from module path.

    Returns:
        Router object or None if failed to load
    """
    try:
        # Handle special "import" syntax for non-routers modules
        if " import " in config.module_path:
            parts = config.module_path.split(" import ")
            module_path = parts[0]
            attr_name = parts[1]
        else:
            module_path = config.module_path
            attr_name = config.router_attr

        # Dynamic import
        import importlib

        module = importlib.import_module(module_path)
        router = getattr(module, attr_name)
        return router
    except Exception as e:
        logger.warning(f"Failed to load router {config.module_path}: {e}")
        return None


def _check_condition(config: RouterConfig) -> bool:
    """Check if router should be loaded based on env condition."""
    if config.condition is None:
        return True
    return os.environ.get(config.condition, "0").lower() in ("1", "true", "yes")


def register_routers_from_list(app: "FastAPI", routers: list[RouterConfig], category: str = "") -> int:
    """
    Register routers from a list of configurations.

    Args:
        app: FastAPI application
        routers: List of RouterConfig objects
        category: Category name for logging

    Returns:
        Number of successfully registered routers
    """
    registered = 0
    for config in routers:
        if not _check_condition(config):
            logger.debug(f"Skipping {config.module_path} (condition not met)")
            continue

        router = _load_router(config)
        if router is None:
            continue

        try:
            app.include_router(
                router,
                prefix=config.prefix,
                tags=config.tags,
                include_in_schema=config.include_in_schema,
            )
            registered += 1
        except Exception as e:
            logger.warning(f"Failed to register router {config.module_path}: {e}")

    if category:
        logger.debug(f"[{category}] Registered {registered}/{len(routers)} routers")
    return registered


def register_all_routers(app: "FastAPI") -> int:
    """
    Register all routers to the FastAPI application.

    Args:
        app: FastAPI application instance

    Returns:
        Total number of registered routers
    """
    total = 0

    # Register by category
    total += register_routers_from_list(app, CORE_ROUTERS, "Core")
    total += register_routers_from_list(app, HEALTH_ROUTERS, "Health")
    total += register_routers_from_list(app, TRADING_ROUTERS, "Trading")
    total += register_routers_from_list(app, STRATEGY_ROUTERS, "Strategy")
    total += register_routers_from_list(app, RISK_ROUTERS, "Risk")
    total += register_routers_from_list(app, AI_ROUTERS, "AI")
    total += register_routers_from_list(app, ML_ROUTERS, "ML")
    total += register_routers_from_list(app, DASHBOARD_ROUTERS, "Dashboard")
    total += register_routers_from_list(app, UTILITY_ROUTERS, "Utility")
    total += register_routers_from_list(app, INFRA_ROUTERS, "Infrastructure")
    total += register_routers_from_list(app, API_MODULE_ROUTERS, "API Modules")

    # MCP bridge routes (optional)
    try:
        from backend.api.mcp_routes import router as mcp_bridge_router

        app.include_router(mcp_bridge_router, tags=["mcp-bridge"])
        total += 1
        logger.info("✅ MCP bridge routes included at /mcp/bridge")
    except Exception as e:
        logger.debug(f"MCP bridge routes not available: {e}")

    logger.info(f"✅ Router registry: {total} routers registered")
    return total


def get_router_summary() -> dict:
    """
    Get summary of all configured routers.

    Returns:
        Dictionary with router counts by category
    """
    return {
        "core": len(CORE_ROUTERS),
        "health": len(HEALTH_ROUTERS),
        "trading": len(TRADING_ROUTERS),
        "strategy": len(STRATEGY_ROUTERS),
        "risk": len(RISK_ROUTERS),
        "ai": len(AI_ROUTERS),
        "ml": len(ML_ROUTERS),
        "dashboard": len(DASHBOARD_ROUTERS),
        "utility": len(UTILITY_ROUTERS),
        "infrastructure": len(INFRA_ROUTERS),
        "api_modules": len(API_MODULE_ROUTERS),
        "total": (
            len(CORE_ROUTERS)
            + len(HEALTH_ROUTERS)
            + len(TRADING_ROUTERS)
            + len(STRATEGY_ROUTERS)
            + len(RISK_ROUTERS)
            + len(AI_ROUTERS)
            + len(ML_ROUTERS)
            + len(DASHBOARD_ROUTERS)
            + len(UTILITY_ROUTERS)
            + len(INFRA_ROUTERS)
            + len(API_MODULE_ROUTERS)
        ),
    }
