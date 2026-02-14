"""
Strategy Management Tools

List, validate, and evolve trading strategies.
Auto-registered with the global MCP tool registry on import.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry

registry = get_tool_registry()


@registry.register(
    name="list_strategies",
    description="List all available backtest strategies with their default parameters",
    category="backtesting",
)
async def list_strategies() -> dict[str, Any]:
    """
    List all available trading strategies and their default parameters.

    Returns:
        Dict with strategy names, descriptions, and default params
    """
    try:
        from backend.backtesting.strategies import list_available_strategies

        strategies = list_available_strategies()
        return {
            "count": len(strategies),
            "strategies": strategies,
        }
    except Exception as e:
        logger.error(f"list_strategies tool error: {e}")
        return {"error": str(e)}


@registry.register(
    name="validate_strategy",
    description=(
        "Validate strategy parameters before running a backtest. "
        "Checks param types, ranges, and strategy-specific constraints."
    ),
    category="backtesting",
)
async def validate_strategy(
    strategy_type: str,
    strategy_params: dict[str, Any],
    leverage: float = 1.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Validate strategy parameters and risk settings.

    Args:
        strategy_type: Strategy name
        strategy_params: Strategy-specific parameters
        leverage: Leverage to validate
        stop_loss: Stop loss fraction to validate
        take_profit: Take profit fraction to validate

    Returns:
        Validation result with is_valid, warnings, and suggested fixes
    """
    try:
        from backend.backtesting.models import StrategyType
        from backend.backtesting.strategies import STRATEGY_REGISTRY

        errors: list[str] = []
        warnings: list[str] = []

        # 1. Check strategy type
        valid_types = {e.value for e in StrategyType}
        if strategy_type not in valid_types:
            errors.append(f"Unknown strategy '{strategy_type}'. Valid: {sorted(valid_types)}")
            return {"is_valid": False, "errors": errors, "warnings": []}

        # 2. Check strategy-specific params
        strategy_cls = STRATEGY_REGISTRY.get(strategy_type)
        if strategy_cls:
            defaults = strategy_cls.get_default_params()
            for key in strategy_params:
                if key not in defaults:
                    warnings.append(f"Unknown param '{key}' for {strategy_type}. Known: {list(defaults.keys())}")

            for key, default_val in defaults.items():
                if key in strategy_params:
                    val = strategy_params[key]
                    if isinstance(default_val, (int, float)) and not isinstance(val, (int, float)):
                        errors.append(f"Param '{key}' must be numeric, got {type(val).__name__}")
                    if isinstance(default_val, int) and isinstance(val, (int, float)) and val <= 0:
                        errors.append(f"Param '{key}' must be positive, got {val}")

        # 3. Leverage safety
        if leverage > 50:
            warnings.append(f"High leverage ({leverage}x) — significant liquidation risk")
        if leverage > 125:
            errors.append("Leverage cannot exceed 125x (Bybit limit)")

        # 4. Stop loss / take profit sanity
        if stop_loss is not None:
            if stop_loss < 0.001 or stop_loss > 0.5:
                errors.append(f"stop_loss must be 0.001-0.5, got {stop_loss}")
            if leverage > 20 and stop_loss < 0.005:
                warnings.append("Very tight stop loss with high leverage — likely to be stopped out frequently")

        if take_profit is not None and (take_profit < 0.001 or take_profit > 1.0):
            errors.append(f"take_profit must be 0.001-1.0, got {take_profit}")

        if stop_loss and take_profit:
            rr = take_profit / stop_loss
            if rr < 1.0:
                warnings.append(f"Risk-reward ratio ({rr:.2f}) < 1.0 — reward is less than risk")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "strategy_type": strategy_type,
            "params_checked": list(strategy_params.keys()),
        }

    except Exception as e:
        logger.error(f"validate_strategy tool error: {e}")
        return {"is_valid": False, "errors": [str(e)], "warnings": []}


@registry.register(
    name="evolve_strategy",
    description=(
        "Run AI-powered strategy evolution: iteratively improve a trading strategy "
        "using LLM reflection and backtesting. Requires OHLCV data in DB and a DeepSeek API key."
    ),
    category="backtesting",
)
async def evolve_strategy(
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    max_generations: int = 3,
    initial_capital: float = 10000.0,
    leverage: int = 1,
    direction: str = "both",
    start_date: str = "2025-06-01",
    end_date: str = "2025-07-01",
) -> dict[str, Any]:
    """
    Run strategy evolution using the StrategyEvolution engine.

    Iteratively generates, backtests, reflects, and improves strategies.
    Each generation uses LLM feedback to evolve parameters.

    Args:
        symbol: Trading pair
        timeframe: Timeframe (1, 5, 15, 30, 60, 240, D, W, M)
        max_generations: Number of evolution iterations (1-10)
        initial_capital: Starting capital
        leverage: Leverage multiplier (1-125)
        direction: Trade direction (long, short, both)
        start_date: YYYY-MM-DD start date
        end_date: YYYY-MM-DD end date

    Returns:
        Evolution results with best strategy and fitness history
    """
    try:
        from backend.agents.self_improvement.strategy_evolution import (
            StrategyEvolution,
        )
        from backend.services.data_service import DataService

        max_generations = max(1, min(max_generations, 10))
        if not (1 <= leverage <= 125):
            return {"error": "leverage must be 1-125"}

        valid_intervals = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}
        if timeframe not in valid_intervals:
            return {
                "error": f"Invalid timeframe: {timeframe}",
                "valid": sorted(valid_intervals),
            }

        data_service = DataService()
        df = await data_service.get_klines(
            symbol=symbol,
            interval=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty or len(df) < 50:
            return {
                "error": (
                    f"Insufficient data for {symbol} {timeframe}: "
                    f"got {len(df) if df is not None else 0} candles (need >=50)"
                ),
            }

        evo = StrategyEvolution()
        result = await evo.evolve(
            symbol=symbol,
            timeframe=timeframe,
            df=df,
            max_generations=max_generations,
            initial_capital=initial_capital,
            leverage=leverage,
            direction=direction,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"evolve_strategy tool error: {e}")
        return {"error": str(e)}
