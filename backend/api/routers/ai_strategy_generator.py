"""
AI Strategy Generator API Router.

Endpoints for AI-powered trading strategy generation:
- Generate strategies from pattern descriptions
- Validate generated code
- Run automatic backtesting
- Manage generated strategies
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from backend.services.ai_strategy_generator import (
    GeneratedStrategy,
    GenerationRequest,
    GenerationStatus,
    IndicatorType,
    PatternType,
    get_ai_strategy_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-strategy-generator", tags=["AI Strategy Generator"])


# ============================================================================
# Request/Response Models
# ============================================================================


class IndicatorSpec(BaseModel):
    """Indicator specification for request."""

    indicator: str = Field(..., description="Indicator type (rsi, macd, etc.)")


class GenerateStrategyRequest(BaseModel):
    """Request to generate a new trading strategy."""

    name: str = Field(..., min_length=1, max_length=100, description="Strategy name")
    description: str = Field(
        default="", max_length=1000, description="Strategy description"
    )

    # Pattern
    pattern_type: str = Field(
        default="trend_following",
        description="Pattern type: trend_following, mean_reversion, breakout, momentum, etc.",
    )
    pattern_description: str = Field(
        default="",
        max_length=2000,
        description="Detailed description of entry/exit conditions",
    )

    # Indicators
    indicators: List[str] = Field(
        default_factory=lambda: ["rsi", "atr"],
        description="List of indicators to use",
    )
    custom_conditions: str = Field(
        default="", max_length=2000, description="Additional custom conditions"
    )

    # Risk parameters
    max_drawdown: float = Field(
        default=0.15, ge=0.01, le=0.50, description="Max drawdown target (0.01-0.50)"
    )
    risk_per_trade: float = Field(
        default=0.02, ge=0.005, le=0.10, description="Risk per trade (0.5%-10%)"
    )
    target_win_rate: float = Field(
        default=0.50, ge=0.30, le=0.80, description="Target win rate (30%-80%)"
    )
    target_risk_reward: float = Field(
        default=2.0, ge=1.0, le=5.0, description="Risk/reward ratio"
    )

    # Backtesting
    symbols: List[str] = Field(
        default_factory=lambda: ["BTCUSDT"], description="Symbols to backtest"
    )
    timeframes: List[str] = Field(
        default_factory=lambda: ["60", "240"], description="Timeframes to use"
    )
    min_backtest_period_days: int = Field(
        default=30, ge=7, le=365, description="Backtest period in days"
    )

    # Advanced
    use_ml_features: bool = Field(default=False, description="Use ML features")
    multi_timeframe: bool = Field(default=False, description="Multi-timeframe analysis")
    position_sizing: str = Field(default="fixed", description="Position sizing method")
    auto_backtest: bool = Field(default=False, description="Run automatic backtesting")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "RSI Trend Follower",
                "description": "Follow trends using RSI momentum",
                "pattern_type": "trend_following",
                "indicators": ["rsi", "ema", "atr"],
                "risk_per_trade": 0.02,
                "target_risk_reward": 2.5,
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "timeframes": ["60", "240"],
            }
        }
    )


class GeneratedStrategyResponse(BaseModel):
    """Response containing generated strategy."""

    id: str
    request_id: str
    name: str
    status: str

    # Code
    code: Optional[str] = None
    class_name: Optional[str] = None

    # Metadata
    description: str = ""
    pattern_type: str = ""
    indicators_used: List[str] = Field(default_factory=list)

    # Parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)
    default_params: Dict[str, Any] = Field(default_factory=dict)

    # Validation
    is_valid: bool = False
    validation_errors: List[str] = Field(default_factory=list)

    # Backtest results
    backtest_results: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Error
    error_message: Optional[str] = None

    @classmethod
    def from_strategy(cls, strategy: GeneratedStrategy) -> "GeneratedStrategyResponse":
        """Convert GeneratedStrategy to response model."""
        return cls(
            id=strategy.id,
            request_id=strategy.request_id,
            name=strategy.name,
            status=strategy.status.value,
            code=strategy.code,
            class_name=strategy.class_name,
            description=strategy.description,
            pattern_type=strategy.pattern_type.value,
            indicators_used=strategy.indicators_used,
            parameters=strategy.parameters,
            default_params=strategy.default_params,
            is_valid=strategy.is_valid,
            validation_errors=strategy.validation_errors,
            backtest_results=strategy.backtest_results,
            created_at=strategy.created_at,
            completed_at=strategy.completed_at,
            error_message=strategy.error_message,
        )


class StrategyListResponse(BaseModel):
    """Response containing list of strategies."""

    total: int
    strategies: List[GeneratedStrategyResponse]


class PatternTypesResponse(BaseModel):
    """Available pattern types."""

    pattern_types: List[Dict[str, str]]


class IndicatorsResponse(BaseModel):
    """Available indicators."""

    indicators: List[Dict[str, str]]


class ValidationRequest(BaseModel):
    """Request to validate strategy code."""

    code: str = Field(
        ..., min_length=100, description="Python strategy code to validate"
    )


class ValidationResponse(BaseModel):
    """Code validation response."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/pattern-types", response_model=PatternTypesResponse)
async def get_pattern_types():
    """
    Get available pattern types for strategy generation.

    Returns list of pattern types with descriptions.
    """
    patterns = [
        {"id": pt.value, "name": pt.value.replace("_", " ").title()}
        for pt in PatternType
    ]
    return PatternTypesResponse(pattern_types=patterns)


@router.get("/indicators", response_model=IndicatorsResponse)
async def get_indicators():
    """
    Get available technical indicators.

    Returns list of indicators that can be used in strategies.
    """
    indicators = [
        {"id": ind.value, "name": ind.value.replace("_", " ").upper()}
        for ind in IndicatorType
    ]
    return IndicatorsResponse(indicators=indicators)


@router.post(
    "/generate",
    response_model=GeneratedStrategyResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_strategy(
    request: GenerateStrategyRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate a new trading strategy using AI.

    This endpoint starts strategy generation asynchronously.
    Use GET /ai-strategy-generator/{strategy_id} to check status.

    **Pattern Types:**
    - trend_following: Follow market trends
    - mean_reversion: Trade reversals at extremes
    - breakout: Trade price breakouts
    - momentum: Trade momentum signals
    - scalping: Quick trades on short timeframes
    - swing_trading: Hold positions for days
    - grid_trading: Place orders at grid levels
    - dca: Dollar-cost averaging

    **Indicators:**
    rsi, macd, bollinger_bands, ema, sma, atr, stochastic, adx, vwap, volume, ichimoku, supertrend
    """
    generator = get_ai_strategy_generator()

    # Convert request to GenerationRequest
    try:
        pattern = PatternType(request.pattern_type)
    except ValueError:
        pattern = PatternType.CUSTOM

    indicators = []
    for ind_str in request.indicators:
        try:
            indicators.append(IndicatorType(ind_str.lower()))
        except ValueError:
            pass  # Skip unknown indicators

    gen_request = GenerationRequest(
        name=request.name,
        description=request.description,
        pattern_type=pattern,
        pattern_description=request.pattern_description,
        indicators=indicators,
        custom_conditions=request.custom_conditions,
        max_drawdown=request.max_drawdown,
        risk_per_trade=request.risk_per_trade,
        target_win_rate=request.target_win_rate,
        target_risk_reward=request.target_risk_reward,
        symbols=request.symbols,
        timeframes=request.timeframes,
        min_backtest_period_days=request.min_backtest_period_days,
        use_ml_features=request.use_ml_features,
        multi_timeframe=request.multi_timeframe,
        position_sizing=request.position_sizing,
    )

    # Start generation in background
    async def run_generation():
        await generator.generate_strategy(
            gen_request, auto_backtest=request.auto_backtest
        )

    background_tasks.add_task(run_generation)

    # Create initial response
    initial_strategy = GeneratedStrategy(
        request_id=gen_request.request_id,
        name=request.name,
        pattern_type=pattern,
        status=GenerationStatus.PENDING,
    )
    generator._generation_cache[initial_strategy.id] = initial_strategy

    logger.info(f"Started strategy generation: {initial_strategy.id}")

    return GeneratedStrategyResponse.from_strategy(initial_strategy)


@router.get("/{strategy_id}", response_model=GeneratedStrategyResponse)
async def get_strategy(strategy_id: str):
    """
    Get a generated strategy by ID.

    Returns the full strategy including code, parameters, and backtest results.
    """
    generator = get_ai_strategy_generator()
    strategy = generator.get_generation_status(strategy_id)

    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy not found: {strategy_id}",
        )

    return GeneratedStrategyResponse.from_strategy(strategy)


@router.get("/", response_model=StrategyListResponse)
async def list_strategies(
    limit: int = Query(
        default=50, ge=1, le=200, description="Maximum strategies to return"
    ),
    status_filter: Optional[str] = Query(default=None, description="Filter by status"),
    pattern_filter: Optional[str] = Query(
        default=None, description="Filter by pattern type"
    ),
):
    """
    List all generated strategies.

    Supports filtering by status and pattern type.
    """
    generator = get_ai_strategy_generator()
    strategies = generator.list_generations(limit=limit)

    # Apply filters
    if status_filter:
        try:
            target_status = GenerationStatus(status_filter)
            strategies = [s for s in strategies if s.status == target_status]
        except ValueError:
            pass

    if pattern_filter:
        try:
            target_pattern = PatternType(pattern_filter)
            strategies = [s for s in strategies if s.pattern_type == target_pattern]
        except ValueError:
            pass

    return StrategyListResponse(
        total=len(strategies),
        strategies=[GeneratedStrategyResponse.from_strategy(s) for s in strategies],
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_strategy_code(request: ValidationRequest):
    """
    Validate strategy code without generating.

    Checks for:
    - Syntax errors
    - Required imports and class inheritance
    - Dangerous code patterns
    - Proper implementation of generate_signals()
    """
    generator = get_ai_strategy_generator()

    # Use static validation
    errors = generator._static_validate(request.code)

    if errors:
        return ValidationResponse(
            is_valid=False,
            errors=errors,
            warnings=[],
            suggestions=["Fix the errors above and try again"],
        )

    # Check for optional improvements
    warnings = []
    suggestions = []

    if "calculate_stop_loss" not in request.code:
        warnings.append("No stop-loss calculation found")
        suggestions.append("Add stop-loss using calculate_stop_loss helper")

    if "calculate_take_profit" not in request.code:
        warnings.append("No take-profit calculation found")
        suggestions.append("Add take-profit using calculate_take_profit helper")

    if "@register_strategy" not in request.code:
        warnings.append("Strategy not registered with @register_strategy decorator")
        suggestions.append(
            "Add @register_strategy decorator for automatic registration"
        )

    return ValidationResponse(
        is_valid=True,
        errors=[],
        warnings=warnings,
        suggestions=suggestions,
    )


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: str):
    """
    Delete a generated strategy.

    Removes the strategy from the cache.
    """
    generator = get_ai_strategy_generator()

    if strategy_id not in generator._generation_cache:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy not found: {strategy_id}",
        )

    del generator._generation_cache[strategy_id]
    logger.info(f"Deleted strategy: {strategy_id}")


@router.post("/{strategy_id}/save")
async def save_strategy_to_library(strategy_id: str):
    """
    Save a generated strategy to the strategy library.

    Creates a new file in backend/services/strategies/generated/.
    """
    generator = get_ai_strategy_generator()
    strategy = generator.get_generation_status(strategy_id)

    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy not found: {strategy_id}",
        )

    if not strategy.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot save invalid strategy",
        )

    if not strategy.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy has no code to save",
        )

    # Create filename
    import os
    import re

    safe_name = re.sub(r"[^a-z0-9_]", "_", strategy.name.lower())
    filename = f"ai_{safe_name}_{strategy.id[:8]}.py"

    # Save to generated strategies folder
    generated_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "services", "strategies", "generated"
    )
    os.makedirs(generated_dir, exist_ok=True)

    filepath = os.path.join(generated_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'"""\nAI-Generated Strategy: {strategy.name}\n')
        f.write(f"Generated: {strategy.created_at.isoformat()}\n")
        f.write(f"Pattern: {strategy.pattern_type.value}\n")
        f.write('"""\n\n')
        f.write(strategy.code)

    logger.info(f"Saved strategy to: {filepath}")

    return {
        "message": "Strategy saved successfully",
        "filename": filename,
        "path": filepath,
    }


@router.post("/{strategy_id}/backtest")
async def run_strategy_backtest(
    strategy_id: str,
    background_tasks: BackgroundTasks,
    symbol: str = Query(default="BTCUSDT", description="Trading symbol"),
    timeframe: str = Query(default="60", description="Timeframe"),
    days: int = Query(default=30, ge=7, le=365, description="Backtest period"),
):
    """
    Run backtesting on a generated strategy.

    Executes the strategy on historical data and returns performance metrics.
    """
    generator = get_ai_strategy_generator()
    strategy = generator.get_generation_status(strategy_id)

    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy not found: {strategy_id}",
        )

    if not strategy.is_valid or not strategy.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy must be valid with code to backtest",
        )

    # Create backtest request
    request = GenerationRequest(
        symbols=[symbol],
        timeframes=[timeframe],
        min_backtest_period_days=days,
    )

    # Run backtest in background
    async def run_backtest():
        results = await generator._run_backtest(strategy, request)
        strategy.backtest_results = results

    background_tasks.add_task(run_backtest)

    return {
        "message": "Backtest started",
        "strategy_id": strategy_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "days": days,
    }
