"""
Strategy Library API Router.

Provides REST API endpoints for:
- Listing available strategies
- Getting strategy details and parameters
- Creating strategy instances
- Parameter optimization
"""

import contextlib
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import strategy library
from backend.services.strategies import (
    StrategyCategory,
    StrategyInfo,
    StrategyRegistry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Strategy Library"])


# =============================================================================
# Pydantic Models
# =============================================================================


class ParameterSpecResponse(BaseModel):
    """Parameter specification response."""

    name: str
    type: str
    default: Any
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    choices: list[Any] | None = None
    optimize: bool = True


class StrategyInfoResponse(BaseModel):
    """Strategy information response."""

    id: str
    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: str = "System"
    min_candles: int = 50
    recommended_timeframes: list[str] = []
    suitable_markets: list[str] = []
    avg_trades_per_day: float = 1.0
    expected_win_rate: float = 0.5
    expected_risk_reward: float = 2.0
    typical_holding_period: str = "hours"
    risk_level: str = "moderate"
    max_drawdown_expected: float = 0.15
    parameters: list[ParameterSpecResponse] = []
    tags: list[str] = []


class StrategySummaryResponse(BaseModel):
    """Brief strategy summary for list view."""

    id: str
    name: str
    category: str
    risk_level: str
    expected_win_rate: float
    tags: list[str] = []


class CategoryInfo(BaseModel):
    """Strategy category information."""

    id: str
    name: str
    description: str
    count: int


class OptimizationSpaceResponse(BaseModel):
    """Optimization parameter space response."""

    strategy_id: str
    parameters: dict[str, dict[str, Any]]


class CreateStrategyRequest(BaseModel):
    """Request to create a strategy instance."""

    strategy_id: str = Field(..., description="Strategy ID from registry")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    timeframe: str = Field("60", description="Candle timeframe")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Custom parameter values"
    )
    paper_trading: bool = Field(True, description="Use paper trading mode")


class CreateStrategyResponse(BaseModel):
    """Response after creating a strategy."""

    success: bool
    message: str
    strategy_id: str
    strategy_name: str
    parameters: dict[str, Any]


# =============================================================================
# Helper Functions
# =============================================================================


def strategy_info_to_response(info: StrategyInfo) -> StrategyInfoResponse:
    """Convert StrategyInfo to response model."""
    return StrategyInfoResponse(
        id=info.id,
        name=info.name,
        description=info.description.strip(),
        category=info.category.value,
        version=info.version,
        author=info.author,
        min_candles=info.min_candles,
        recommended_timeframes=info.recommended_timeframes,
        suitable_markets=info.suitable_markets,
        avg_trades_per_day=info.avg_trades_per_day,
        expected_win_rate=info.expected_win_rate,
        expected_risk_reward=info.expected_risk_reward,
        typical_holding_period=info.typical_holding_period,
        risk_level=info.risk_level,
        max_drawdown_expected=info.max_drawdown_expected,
        parameters=[
            ParameterSpecResponse(
                name=p.name,
                type=p.param_type.value,
                default=p.default,
                description=p.description,
                min_value=p.min_value,
                max_value=p.max_value,
                step=p.step,
                choices=p.choices,
                optimize=p.optimize,
            )
            for p in info.parameters
        ],
        tags=info.tags,
    )


def strategy_info_to_summary(info: StrategyInfo) -> StrategySummaryResponse:
    """Convert StrategyInfo to summary response."""
    return StrategySummaryResponse(
        id=info.id,
        name=info.name,
        category=info.category.value,
        risk_level=info.risk_level,
        expected_win_rate=info.expected_win_rate,
        tags=info.tags,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=list[StrategySummaryResponse])
async def list_strategies(
    category: str | None = Query(None, description="Filter by category"),
    risk_level: str | None = Query(None, description="Filter by risk level"),
    tag: str | None = Query(None, description="Filter by tag"),
    search: str | None = Query(None, description="Search query"),
):
    """
    List all available strategies with optional filters.

    Returns brief summaries for browsing.
    """
    try:
        # Parse category
        category_enum = None
        if category:
            with contextlib.suppress(ValueError):
                category_enum = StrategyCategory(category)

        # Search strategies
        tags_list = [tag] if tag else None
        strategies = StrategyRegistry.search(
            query=search,
            category=category_enum,
            risk_level=risk_level,
            tags=tags_list,
        )

        return [strategy_info_to_summary(s) for s in strategies]

    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=list[CategoryInfo])
async def get_categories():
    """
    Get all strategy categories with counts.
    """
    categories = []

    category_descriptions = {
        StrategyCategory.TREND_FOLLOWING: "Follow market trends using moving averages and momentum",
        StrategyCategory.MEAN_REVERSION: "Trade price reversion to historical average",
        StrategyCategory.MOMENTUM: "Trade momentum continuation signals",
        StrategyCategory.BREAKOUT: "Trade price breakouts from ranges",
        StrategyCategory.GRID_TRADING: "Automated grid of orders at intervals",
        StrategyCategory.DCA: "Dollar Cost Averaging - systematic buying",
        StrategyCategory.SCALPING: "High frequency small profit trades",
        StrategyCategory.SWING_TRADING: "Multi-day position trades",
        StrategyCategory.ARBITRAGE: "Cross-market price difference trades",
        StrategyCategory.CUSTOM: "User-defined custom strategies",
    }

    for cat in StrategyCategory:
        strategies = StrategyRegistry.list_by_category(cat)
        if strategies:
            categories.append(
                CategoryInfo(
                    id=cat.value,
                    name=cat.name.replace("_", " ").title(),
                    description=category_descriptions.get(cat, ""),
                    count=len(strategies),
                )
            )

    return categories


@router.get("/{strategy_id}", response_model=StrategyInfoResponse)
async def get_strategy_details(strategy_id: str):
    """
    Get full details for a specific strategy.

    Includes all parameters, optimization ranges, and metadata.
    """
    strategy_class = StrategyRegistry.get(strategy_id)

    if not strategy_class or not strategy_class.STRATEGY_INFO:
        raise HTTPException(
            status_code=404, detail=f"Strategy not found: {strategy_id}"
        )

    return strategy_info_to_response(strategy_class.STRATEGY_INFO)


@router.get("/{strategy_id}/parameters", response_model=list[ParameterSpecResponse])
async def get_strategy_parameters(strategy_id: str):
    """
    Get parameters for a specific strategy.
    """
    strategy_class = StrategyRegistry.get(strategy_id)

    if not strategy_class or not strategy_class.STRATEGY_INFO:
        raise HTTPException(
            status_code=404, detail=f"Strategy not found: {strategy_id}"
        )

    return [
        ParameterSpecResponse(
            name=p.name,
            type=p.param_type.value,
            default=p.default,
            description=p.description,
            min_value=p.min_value,
            max_value=p.max_value,
            step=p.step,
            choices=p.choices,
            optimize=p.optimize,
        )
        for p in strategy_class.STRATEGY_INFO.parameters
    ]


@router.get(
    "/{strategy_id}/optimization-space", response_model=OptimizationSpaceResponse
)
async def get_optimization_space(strategy_id: str):
    """
    Get parameter optimization space for Optuna or other optimizers.

    Returns Optuna-compatible parameter specifications.
    """
    space = StrategyRegistry.get_optimization_space(strategy_id)

    if not space:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy not found or has no optimizable parameters: {strategy_id}",
        )

    return OptimizationSpaceResponse(
        strategy_id=strategy_id,
        parameters=space,
    )


@router.get("/by-category/{category}", response_model=list[StrategySummaryResponse])
async def list_strategies_by_category(category: str):
    """
    List all strategies in a category.
    """
    try:
        category_enum = StrategyCategory(category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    strategies = StrategyRegistry.list_by_category(category_enum)
    return [strategy_info_to_summary(s) for s in strategies]


@router.get("/by-risk/{risk_level}", response_model=list[StrategySummaryResponse])
async def list_strategies_by_risk(risk_level: str):
    """
    List strategies by risk level.

    Risk levels: conservative, moderate, aggressive
    """
    if risk_level not in ("conservative", "moderate", "aggressive"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk level: {risk_level}. Must be one of: conservative, moderate, aggressive",
        )
    strategies = StrategyRegistry.search(risk_level=risk_level)
    return [strategy_info_to_summary(s) for s in strategies]


@router.post("/validate-parameters")
async def validate_parameters(
    strategy_id: str,
    parameters: dict[str, Any],
):
    """
    Validate parameters for a strategy.

    Returns validation result and any errors.
    """
    strategy_class = StrategyRegistry.get(strategy_id)

    if not strategy_class or not strategy_class.STRATEGY_INFO:
        raise HTTPException(
            status_code=404, detail=f"Strategy not found: {strategy_id}"
        )

    errors = []
    warnings = []

    info = strategy_class.STRATEGY_INFO
    param_specs = {p.name: p for p in info.parameters}

    for name, value in parameters.items():
        if name not in param_specs:
            warnings.append(f"Unknown parameter: {name}")
            continue

        spec = param_specs[name]

        # Type validation
        if spec.param_type.value == "int":
            if not isinstance(value, int):
                errors.append(f"{name}: expected int, got {type(value).__name__}")
                continue
        elif spec.param_type.value == "float":
            if not isinstance(value, (int, float)):
                errors.append(f"{name}: expected float, got {type(value).__name__}")
                continue
        elif spec.param_type.value == "bool" and not isinstance(value, bool):
            errors.append(f"{name}: expected bool, got {type(value).__name__}")
            continue

        # Range validation
        if spec.min_value is not None and value < spec.min_value:
            errors.append(f"{name}: value {value} below minimum {spec.min_value}")
        if spec.max_value is not None and value > spec.max_value:
            errors.append(f"{name}: value {value} above maximum {spec.max_value}")

        # Choices validation
        if spec.choices and value not in spec.choices:
            errors.append(
                f"{name}: value {value} not in allowed choices {spec.choices}"
            )

    # Check for missing required parameters (none currently required)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


@router.get("/tags/all")
async def get_all_tags():
    """
    Get all available strategy tags.
    """
    all_tags = set()

    for info in StrategyRegistry.list_all():
        all_tags.update(info.tags)

    return {"tags": sorted(all_tags)}


@router.get("/stats/summary")
async def get_library_summary():
    """
    Get summary statistics about the strategy library.
    """
    all_strategies = StrategyRegistry.list_all()

    by_category = {}
    by_risk = {"conservative": 0, "moderate": 0, "aggressive": 0}

    for info in all_strategies:
        cat = info.category.value
        by_category[cat] = by_category.get(cat, 0) + 1
        by_risk[info.risk_level] = by_risk.get(info.risk_level, 0) + 1

    return {
        "total_strategies": len(all_strategies),
        "by_category": by_category,
        "by_risk_level": by_risk,
        "categories_count": len(by_category),
    }


@router.get("/recommendations")
async def get_strategy_recommendations(
    market_condition: str | None = Query(
        None, description="trending, ranging, volatile"
    ),
    experience_level: str | None = Query(
        None, description="beginner, intermediate, advanced"
    ),
    preferred_timeframe: str | None = Query(None, description="Preferred timeframe"),
    max_risk: str | None = Query("moderate", description="Maximum risk level"),
):
    """
    Get strategy recommendations based on conditions.
    """
    all_strategies = StrategyRegistry.list_all()
    recommendations = []

    for info in all_strategies:
        score = 0
        reasons = []

        # Risk level filter
        risk_order = {"conservative": 1, "moderate": 2, "aggressive": 3}
        if max_risk and risk_order.get(info.risk_level, 2) > risk_order.get(
            max_risk, 2
        ):
            continue

        # Market condition matching
        if market_condition:
            if market_condition == "trending":
                if info.category in [
                    StrategyCategory.TREND_FOLLOWING,
                    StrategyCategory.BREAKOUT,
                ]:
                    score += 3
                    reasons.append("Good for trending markets")
            elif market_condition == "ranging":
                if info.category in [
                    StrategyCategory.MEAN_REVERSION,
                    StrategyCategory.GRID_TRADING,
                ]:
                    score += 3
                    reasons.append("Good for ranging markets")
            elif market_condition == "volatile" and info.category == StrategyCategory.BREAKOUT:
                score += 2
                reasons.append("Can capture volatility breakouts")

        # Experience level
        if experience_level and experience_level == "beginner":
            if "beginner-friendly" in info.tags:
                score += 2
                reasons.append("Beginner friendly")
            if info.risk_level == "conservative":
                score += 1

        # Timeframe matching
        if preferred_timeframe and preferred_timeframe in info.recommended_timeframes:
            score += 1
            reasons.append(f"Recommended for {preferred_timeframe} timeframe")

        if score > 0:
            recommendations.append(
                {
                    "strategy": strategy_info_to_summary(info),
                    "score": score,
                    "reasons": reasons,
                }
            )

    # Sort by score
    recommendations.sort(key=lambda x: x["score"], reverse=True)

    return {
        "recommendations": recommendations[:10],
        "total_matches": len(recommendations),
    }
