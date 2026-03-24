"""
Optimization Router — Pydantic models and DB-to-response helpers.

Contains local models for this router plus conversion helper functions.
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

from typing import Any

from pydantic import BaseModel, Field

from backend.database.models.optimization import (
    Optimization,
    OptimizationStatus,
    OptimizationType,
)

# =============================================================================
# Pydantic Models
# =============================================================================


class ParamRangeSpec(BaseModel):
    """Parameter range specification.

    Supports:
    - Negative values (e.g., low=-50, high=50)
    - Fractional steps (e.g., step=0.01)
    - High precision floats (e.g., precision=4 for 0.0001)
    """

    type: str = Field(..., description="Parameter type: int, float, categorical")
    low: float | None = Field(None, description="Minimum value (can be negative)")
    high: float | None = Field(None, description="Maximum value (can be negative)")
    step: float | None = Field(
        None,
        description="Step size for grid search (default: 1 for int, 0.01 for float)",
    )
    precision: int | None = Field(
        None,
        description="Decimal precision for rounding (e.g., 2 for 0.01, 4 for 0.0001)",
    )
    values: list[Any] | None = Field(None, description="Explicit values (for categorical or grid)")
    log: bool = Field(False, description="Use log scale for sampling")


class CreateOptimizationRequest(BaseModel):
    """Request to create a new optimization job."""

    strategy_id: int = Field(..., description="Strategy ID to optimize")
    optimization_type: str = Field(
        "grid_search",
        description="Type: grid_search, random_search, bayesian, walk_forward",
    )
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    timeframe: str = Field("1h", description="Candle timeframe")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    param_ranges: dict[str, ParamRangeSpec] = Field(..., description="Parameter search space")
    metric: str = Field("sharpe_ratio", description="Metric to optimize")
    initial_capital: float = Field(10000.0, description="Starting capital")

    # Algorithm-specific settings
    n_trials: int = Field(100, description="Number of trials (Bayesian/Random)")
    train_size: int = Field(120, description="Training window days (Walk-Forward)")
    test_size: int = Field(60, description="Testing window days (Walk-Forward)")
    step_size: int = Field(30, description="Step size days (Walk-Forward)")
    n_jobs: int = Field(1, description="Parallel jobs")
    random_state: int | None = Field(None, description="Random seed")


class OptimizationResponse(BaseModel):
    """Optimization job response."""

    id: int
    strategy_id: int
    optimization_type: str
    symbol: str
    timeframe: str
    start_date: str | None
    end_date: str | None
    metric: str
    status: str
    progress: float
    best_params: dict[str, Any] | None
    best_score: float | None
    total_combinations: int
    evaluated_combinations: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None


class OptimizationResultsResponse(BaseModel):
    """Detailed optimization results."""

    id: int
    optimization_type: str
    status: str
    metric: str
    best_params: dict[str, Any] | None
    best_score: float | None
    all_results: list[dict[str, Any]] | None
    param_importance: dict[str, float] | None
    convergence: list[float] | None
    duration_seconds: float | None


class OptimizationStatusResponse(BaseModel):
    """Optimization status/progress."""

    id: int
    status: str
    progress: float
    evaluated_combinations: int
    total_combinations: int
    current_best_score: float | None
    current_best_params: dict[str, Any] | None
    eta_seconds: float | None


# =============================================================================
# Helper Functions
# =============================================================================


def optimization_to_response(opt: Optimization) -> OptimizationResponse:  # type: ignore[arg-type]
    """Convert Optimization model to response.

    Note: type: ignore is needed because SQLAlchemy 1.x Column[] types
    are not recognized as compatible with plain Python types by mypy.
    """
    return OptimizationResponse(
        id=opt.id,
        strategy_id=opt.strategy_id,
        optimization_type=opt.optimization_type.value
        if isinstance(opt.optimization_type, OptimizationType)
        else opt.optimization_type,
        symbol=opt.symbol,
        timeframe=opt.timeframe,
        start_date=opt.start_date.isoformat() if opt.start_date else None,
        end_date=opt.end_date.isoformat() if opt.end_date else None,
        metric=opt.metric,
        status=opt.status.value if isinstance(opt.status, OptimizationStatus) else opt.status,
        progress=opt.progress or 0.0,
        best_params=opt.best_params,
        best_score=opt.best_score,
        total_combinations=opt.total_combinations or 0,
        evaluated_combinations=opt.evaluated_combinations or 0,
        created_at=opt.created_at.isoformat() if opt.created_at else None,
        started_at=opt.started_at.isoformat() if opt.started_at else None,
        completed_at=opt.completed_at.isoformat() if opt.completed_at else None,
        error_message=opt.error_message,
    )


def parse_optimization_type(type_str: str) -> OptimizationType:
    """Parse optimization type string."""
    type_map = {
        "grid_search": OptimizationType.GRID_SEARCH,
        "grid": OptimizationType.GRID_SEARCH,
        "random_search": OptimizationType.RANDOM_SEARCH,
        "random": OptimizationType.RANDOM_SEARCH,
        "bayesian": OptimizationType.BAYESIAN,
        "optuna": OptimizationType.BAYESIAN,
        "walk_forward": OptimizationType.WALK_FORWARD,
        "walkforward": OptimizationType.WALK_FORWARD,
        "genetic": OptimizationType.GENETIC,
    }
    return type_map.get(type_str.lower(), OptimizationType.GRID_SEARCH)


def calculate_total_combinations(param_ranges: dict[str, "ParamRangeSpec"], opt_type: OptimizationType) -> int:
    """Calculate total parameter combinations."""
    if opt_type in (OptimizationType.BAYESIAN, OptimizationType.RANDOM_SEARCH):
        return 0

    total = 1
    for _param_name, spec in param_ranges.items():
        if spec.values:
            total *= len(spec.values)
        elif spec.low is not None and spec.high is not None and spec.step:
            count = int((spec.high - spec.low) / spec.step) + 1
            total *= count
        else:
            total *= 10

    return total
