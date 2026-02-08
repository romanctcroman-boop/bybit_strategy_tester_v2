"""
Strategy Optimization API Router.

Full-featured REST API for strategy parameter optimization:
- Grid Search: Exhaustive search over parameter combinations
- Random Search: Randomized parameter sampling
- Bayesian Optimization: Smart search using TPE (Optuna)
- Walk-Forward Analysis: Rolling window optimization + OOS testing

Endpoints:
- POST /optimizations/ - Create new optimization job
- GET /optimizations/ - List all optimizations
- GET /optimizations/{id} - Get optimization details
- GET /optimizations/{id}/status - Get job status/progress
- DELETE /optimizations/{id} - Cancel optimization
- GET /optimizations/{id}/results - Get detailed results
- POST /optimizations/{id}/rerun - Rerun optimization
"""

import logging
import os
from datetime import UTC, datetime
from itertools import product
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models.optimization import (
    Optimization,
    OptimizationStatus,
    OptimizationType,
)
from backend.database.models.strategy import Strategy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Optimization"])  # Prefix set in app.py


def _normalize_interval(interval: str) -> str:
    """
    Normalize interval format for database queries.

    Converts frontend-friendly formats to Bybit API/DB format:
    - '30m' -> '30'
    - '1h' -> '60'
    - '4h' -> '240'
    - '1d' -> 'D'
    - '1w' -> 'W'
    """
    interval = interval.lower().strip()
    if interval.endswith("m"):
        return interval[:-1]  # "30m" -> "30"
    elif interval.endswith("h"):
        hours = int(interval[:-1])
        return str(hours * 60)  # "1h" -> "60", "4h" -> "240"
    elif interval in ("d", "1d", "day"):
        return "D"
    elif interval in ("w", "1w", "week"):
        return "W"
    return interval


def generate_param_values(spec: "ParamRangeSpec") -> list[Any]:
    """
    Generate parameter values from a ParamRangeSpec.

    Supports:
    - Negative values (low=-50, high=50)
    - Fractional steps (step=0.01, step=0.001)
    - High precision (precision=4 for 0.0001)
    - Integer and float types

    Args:
        spec: Parameter range specification

    Returns:
        List of parameter values
    """
    if spec.values:
        return spec.values

    if spec.low is None or spec.high is None:
        return []

    # Determine default step based on type
    if spec.step is not None:
        step = spec.step
    else:
        # Default step: 1 for int, 0.01 for float
        step = 1.0 if spec.type == "int" else 0.01

    # Determine precision for rounding
    if spec.precision is not None:
        precision = spec.precision
    else:
        # Auto-detect precision from step
        if step >= 1:
            precision = 0
        else:
            # Count decimal places in step
            step_str = f"{step:.10f}".rstrip("0")
            precision = len(step_str.split(".")[-1]) if "." in step_str else 0

    values = []
    val = spec.low

    # Handle both positive and negative ranges
    # Including cases where low > high (should not happen, but handle gracefully)
    if spec.low <= spec.high:
        while val <= spec.high + step * 0.001:  # Small epsilon for float comparison
            if spec.type == "int":
                values.append(int(round(val)))
            else:
                # Round to specified precision
                rounded_val = round(val, precision) if precision > 0 else round(val)
                values.append(rounded_val)
            val += step

            # Safety limit: max 10000 values
            if len(values) >= 10000:
                logger.warning(
                    f"Parameter range truncated to 10000 values (low={spec.low}, high={spec.high}, step={step})"
                )
                break

    # Remove duplicates while preserving order (important for int type)
    seen = set()
    unique_values = []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique_values.append(v)

    return unique_values


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


def optimization_to_response(opt: Optimization) -> OptimizationResponse:
    """Convert Optimization model to response."""
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


def calculate_total_combinations(param_ranges: dict[str, ParamRangeSpec], opt_type: OptimizationType) -> int:
    """Calculate total parameter combinations."""
    if opt_type in (OptimizationType.BAYESIAN, OptimizationType.RANDOM_SEARCH):
        return 0

    total = 1
    for param_name, spec in param_ranges.items():
        if spec.values:
            total *= len(spec.values)
        elif spec.low is not None and spec.high is not None and spec.step:
            count = int((spec.high - spec.low) / spec.step) + 1
            total *= count
        else:
            total *= 10

    return total


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/", response_model=OptimizationResponse)
async def create_optimization(
    request: CreateOptimizationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new optimization job.

    Supported optimization types:
    - **grid_search**: Exhaustive search over all parameter combinations
    - **random_search**: Random sampling from parameter space
    - **bayesian**: Intelligent search using TPE (Optuna)
    - **walk_forward**: Rolling window optimization with OOS validation

    The job runs asynchronously. Use GET /optimizations/{id}/status to monitor progress.
    """
    strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    opt_type = parse_optimization_type(request.optimization_type)
    total_combinations = calculate_total_combinations({k: v for k, v in request.param_ranges.items()}, opt_type)
    param_ranges_dict = {k: v.model_dump() for k, v in request.param_ranges.items()}

    optimization = Optimization(
        strategy_id=request.strategy_id,
        optimization_type=opt_type,
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=datetime.fromisoformat(request.start_date),
        end_date=datetime.fromisoformat(request.end_date),
        param_ranges=param_ranges_dict,
        metric=request.metric,
        initial_capital=request.initial_capital,
        total_combinations=total_combinations,
        status=OptimizationStatus.QUEUED,
        config={
            "n_trials": request.n_trials,
            "train_size": request.train_size,
            "test_size": request.test_size,
            "step_size": request.step_size,
            "n_jobs": request.n_jobs,
            "random_state": request.random_state,
        },
    )

    db.add(optimization)
    db.commit()
    db.refresh(optimization)

    logger.info(f"Created optimization {optimization.id}: {opt_type.value} for strategy {request.strategy_id}")

    background_tasks.add_task(
        launch_optimization_task,
        optimization_id=optimization.id,
        opt_type=opt_type,
        strategy_config=strategy.parameters or {},
        request=request,
    )

    return optimization_to_response(optimization)


async def launch_optimization_task(
    optimization_id: int,
    opt_type: OptimizationType,
    strategy_config: dict[str, Any],
    request: CreateOptimizationRequest,
):
    """Launch the appropriate Celery task for optimization."""
    try:
        from backend.tasks.optimize_tasks import (
            bayesian_optimization_task,
            grid_search_task,
            walk_forward_task,
        )

        if opt_type == OptimizationType.GRID_SEARCH:
            param_space = {}
            for param_name, spec in request.param_ranges.items():
                param_space[param_name] = generate_param_values(spec)

            grid_search_task.delay(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=request.symbol,
                interval=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                metric=request.metric,
            )

        elif opt_type == OptimizationType.BAYESIAN:
            param_space = {k: v.model_dump() for k, v in request.param_ranges.items()}

            bayesian_optimization_task.delay(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=request.symbol,
                interval=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                n_trials=request.n_trials,
                metric=request.metric,
                n_jobs=request.n_jobs,
                random_state=request.random_state,
            )

        elif opt_type == OptimizationType.WALK_FORWARD:
            param_space = {}
            for param_name, spec in request.param_ranges.items():
                param_space[param_name] = generate_param_values(spec)

            walk_forward_task.delay(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=request.symbol,
                interval=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                train_size=request.train_size,
                test_size=request.test_size,
                step_size=request.step_size,
                metric=request.metric,
            )

        elif opt_type == OptimizationType.RANDOM_SEARCH:
            import random

            param_space = {}
            for param_name, spec in request.param_ranges.items():
                if spec.values:
                    sample_size = min(request.n_trials, len(spec.values))
                    param_space[param_name] = random.sample(spec.values, sample_size)
                elif spec.low is not None and spec.high is not None:
                    # Determine precision for rounding
                    precision = spec.precision
                    if precision is None:
                        if spec.step and spec.step < 1:
                            step_str = f"{spec.step:.10f}".rstrip("0")
                            precision = len(step_str.split(".")[-1]) if "." in step_str else 2
                        else:
                            precision = 2  # Default for floats

                    if spec.type == "int":
                        param_space[param_name] = list(
                            set(
                                [
                                    random.randint(int(spec.low), int(spec.high))
                                    for _ in range(min(request.n_trials, 50))
                                ]
                            )
                        )
                    else:
                        # Generate random floats with proper precision
                        param_space[param_name] = list(
                            set(
                                [
                                    round(random.uniform(spec.low, spec.high), precision)
                                    for _ in range(min(request.n_trials, 50))
                                ]
                            )
                        )

            grid_search_task.delay(
                optimization_id=optimization_id,
                strategy_config=strategy_config,
                param_space=param_space,
                symbol=request.symbol,
                interval=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                metric=request.metric,
            )

        logger.info(f"Launched {opt_type.value} task for optimization {optimization_id}")

    except Exception as e:
        logger.error(f"Failed to launch optimization task: {e}")
        from backend.database import SessionLocal

        db = SessionLocal()
        try:
            opt = db.query(Optimization).filter(Optimization.id == optimization_id).first()
            if opt:
                opt.status = OptimizationStatus.FAILED
                opt.error_message = str(e)
                db.commit()
        finally:
            db.close()


@router.get("/", response_model=list[OptimizationResponse])
async def list_optimizations(
    strategy_id: int | None = Query(None, description="Filter by strategy"),
    status: str | None = Query(None, description="Filter by status"),
    optimization_type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all optimization jobs with optional filters."""
    query = db.query(Optimization)

    if strategy_id:
        query = query.filter(Optimization.strategy_id == strategy_id)
    if status:
        try:
            status_enum = OptimizationStatus(status)
            query = query.filter(Optimization.status == status_enum)
        except ValueError:
            pass
    if optimization_type:
        opt_type = parse_optimization_type(optimization_type)
        query = query.filter(Optimization.optimization_type == opt_type)

    query = query.order_by(Optimization.created_at.desc())
    query = query.offset(offset).limit(limit)

    return [optimization_to_response(opt) for opt in query.all()]


@router.get("/{optimization_id}", response_model=OptimizationResponse)
async def get_optimization(optimization_id: int, db: Session = Depends(get_db)):
    """Get optimization details by ID."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    return optimization_to_response(optimization)


@router.get("/{optimization_id}/status", response_model=OptimizationStatusResponse)
async def get_optimization_status(optimization_id: int, db: Session = Depends(get_db)):
    """Get current status and progress of an optimization job."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    eta_seconds = None
    if optimization.status == OptimizationStatus.RUNNING and optimization.started_at and optimization.progress > 0:
        elapsed = (datetime.now(UTC) - optimization.started_at).total_seconds()
        eta_seconds = elapsed / optimization.progress * (1 - optimization.progress)

    return OptimizationStatusResponse(
        id=optimization.id,
        status=optimization.status.value
        if isinstance(optimization.status, OptimizationStatus)
        else optimization.status,
        progress=optimization.progress or 0.0,
        evaluated_combinations=optimization.evaluated_combinations or 0,
        total_combinations=optimization.total_combinations or 0,
        current_best_score=optimization.best_score,
        current_best_params=optimization.best_params,
        eta_seconds=eta_seconds,
    )


@router.get("/{optimization_id}/results", response_model=OptimizationResultsResponse)
async def get_optimization_results(optimization_id: int, db: Session = Depends(get_db)):
    """Get detailed results of a completed optimization."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Optimization not completed. Status: {optimization.status.value}",
        )

    duration = None
    if optimization.started_at and optimization.completed_at:
        duration = (optimization.completed_at - optimization.started_at).total_seconds()

    results = optimization.results or {}

    return OptimizationResultsResponse(
        id=optimization.id,
        optimization_type=optimization.optimization_type.value
        if isinstance(optimization.optimization_type, OptimizationType)
        else optimization.optimization_type,
        status=optimization.status.value
        if isinstance(optimization.status, OptimizationStatus)
        else optimization.status,
        metric=optimization.metric,
        best_params=optimization.best_params,
        best_score=optimization.best_score,
        all_results=results.get("top_10") or results.get("all_trials"),
        param_importance=results.get("param_importance"),
        convergence=results.get("convergence") or results.get("best_values_history"),
        duration_seconds=duration,
    )


# =============================================================================
# Results Viewer API Endpoints (P0 - Optimization Results Viewer)
# =============================================================================


class ConvergenceDataResponse(BaseModel):
    """Convergence chart data."""

    trials: list[int]
    best_scores: list[float]
    all_scores: list[float]
    metric: str


class SensitivityDataResponse(BaseModel):
    """Parameter sensitivity data."""

    param_name: str
    values: list[float]
    scores: list[float]
    metric: str


class ApplyParamsRequest(BaseModel):
    """Request to apply optimization result parameters."""

    strategy_id: int
    params: dict[str, Any]


class ApplyParamsResponse(BaseModel):
    """Response after applying parameters."""

    success: bool
    message: str
    strategy_id: int
    applied_params: dict[str, Any]


@router.get("/{optimization_id}/charts/convergence", response_model=ConvergenceDataResponse)
async def get_convergence_data(optimization_id: int, db: Session = Depends(get_db)):
    """Get convergence chart data for visualization."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Optimization not completed. Status: {optimization.status.value}",
        )

    results = optimization.results or {}
    all_trials = results.get("all_trials") or results.get("top_10") or []

    # Build convergence data
    trials = []
    best_scores = []
    all_scores = []
    best_so_far = float("-inf")

    for i, trial in enumerate(all_trials):
        score = float(trial.get(optimization.metric, trial.get("sharpe_ratio", 0)))
        trials.append(i + 1)
        all_scores.append(score)
        if score > best_so_far:
            best_so_far = score
        best_scores.append(best_so_far)

    # Also try convergence from results
    if results.get("convergence"):
        best_scores = results["convergence"]
        trials = list(range(1, len(best_scores) + 1))

    return ConvergenceDataResponse(
        trials=trials,
        best_scores=best_scores,
        all_scores=all_scores,
        metric=optimization.metric or "sharpe_ratio",
    )


@router.get("/{optimization_id}/charts/sensitivity/{param_name}", response_model=SensitivityDataResponse)
async def get_sensitivity_data(optimization_id: int, param_name: str, db: Session = Depends(get_db)):
    """Get parameter sensitivity data for visualization."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Optimization not completed. Status: {optimization.status.value}",
        )

    results = optimization.results or {}
    all_trials = results.get("all_trials") or results.get("top_10") or []

    # Extract parameter values and scores
    values = []
    scores = []

    for trial in all_trials:
        if param_name in trial:
            try:
                val = float(trial[param_name])
                score = float(trial.get(optimization.metric, trial.get("sharpe_ratio", 0)))
                values.append(val)
                scores.append(score)
            except (ValueError, TypeError):
                continue

    if not values:
        raise HTTPException(status_code=404, detail=f"Parameter '{param_name}' not found in results")

    return SensitivityDataResponse(
        param_name=param_name,
        values=values,
        scores=scores,
        metric=optimization.metric or "sharpe_ratio",
    )


@router.post("/{optimization_id}/apply/{result_rank}", response_model=ApplyParamsResponse)
async def apply_optimization_result(
    optimization_id: int,
    result_rank: int,
    strategy_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Apply parameters from a specific optimization result to a strategy."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Optimization not completed. Status: {optimization.status.value}",
        )

    # Get results and find the one with matching rank
    results = optimization.results or {}
    all_trials = results.get("all_trials") or results.get("top_10") or []

    if result_rank < 1 or result_rank > len(all_trials):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rank. Must be between 1 and {len(all_trials)}",
        )

    # Sort by metric to ensure correct ranking
    metric = optimization.metric or "sharpe_ratio"
    sorted_trials = sorted(all_trials, key=lambda x: float(x.get(metric, 0)), reverse=True)
    selected_trial = sorted_trials[result_rank - 1]

    # Extract parameters (exclude metrics)
    metric_keys = {
        "rank",
        "sharpe_ratio",
        "total_return",
        "win_rate",
        "max_drawdown",
        "total_trades",
        "profit_factor",
        "expectancy",
        "cagr",
        "sortino_ratio",
        "calmar_ratio",
    }
    params = {k: v for k, v in selected_trial.items() if k not in metric_keys and not k.startswith("_")}

    # Target strategy ID
    target_strategy_id = strategy_id or optimization.strategy_id

    # Load and update strategy
    strategy = db.query(Strategy).filter(Strategy.id == target_strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {target_strategy_id} not found")

    # Update strategy params
    if strategy.config:
        if isinstance(strategy.config, dict):
            strategy.config["params"] = params
        else:
            strategy.config = {"params": params}
    else:
        strategy.config = {"params": params}

    db.commit()

    logger.info(
        f"Applied params from optimization {optimization_id} rank #{result_rank} to strategy {target_strategy_id}"
    )

    return ApplyParamsResponse(
        success=True,
        message=f"Applied rank #{result_rank} parameters to strategy {target_strategy_id}",
        strategy_id=target_strategy_id,
        applied_params=params,
    )


@router.get("/{optimization_id}/results/paginated")
async def get_paginated_results(
    optimization_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("sharpe_ratio"),
    sort_order: str = Query("desc"),
    min_sharpe: float | None = None,
    max_drawdown: float | None = None,
    min_win_rate: float | None = None,
    min_trades: int | None = None,
    db: Session = Depends(get_db),
):
    """Get paginated and filtered optimization results."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Optimization not completed. Status: {optimization.status.value}",
        )

    results = optimization.results or {}
    all_trials = results.get("all_trials") or results.get("top_10") or []

    # Apply filters
    filtered = all_trials
    if min_sharpe is not None:
        filtered = [t for t in filtered if float(t.get("sharpe_ratio", 0)) >= min_sharpe]
    if max_drawdown is not None:
        filtered = [t for t in filtered if float(t.get("max_drawdown", 0)) <= max_drawdown]
    if min_win_rate is not None:
        filtered = [t for t in filtered if float(t.get("win_rate", 0)) >= min_win_rate]
    if min_trades is not None:
        filtered = [t for t in filtered if int(t.get("total_trades", 0)) >= min_trades]

    # Sort
    try:
        reverse = sort_order.lower() == "desc"
        filtered = sorted(filtered, key=lambda x: float(x.get(sort_by, 0)), reverse=reverse)
    except (ValueError, TypeError):
        pass

    # Add ranks
    for i, trial in enumerate(filtered):
        trial["rank"] = i + 1

    # Paginate
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    page_results = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": page_results,
        "optimization_id": optimization_id,
        "metric": optimization.metric,
    }


@router.delete("/{optimization_id}")
async def cancel_optimization(optimization_id: int, db: Session = Depends(get_db)):
    """Cancel a running or queued optimization."""
    optimization = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    if optimization.status in (
        OptimizationStatus.COMPLETED,
        OptimizationStatus.FAILED,
        OptimizationStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel optimization with status: {optimization.status.value}",
        )

    optimization.status = OptimizationStatus.CANCELLED
    optimization.completed_at = datetime.now(UTC)
    db.commit()

    logger.info(f"Cancelled optimization {optimization_id}")
    return {"message": "Optimization cancelled", "id": optimization_id}


@router.post("/{optimization_id}/rerun", response_model=OptimizationResponse)
async def rerun_optimization(
    optimization_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Rerun a completed or failed optimization with the same settings."""
    original = db.query(Optimization).filter(Optimization.id == optimization_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Optimization not found")

    new_optimization = Optimization(
        strategy_id=original.strategy_id,
        optimization_type=original.optimization_type,
        symbol=original.symbol,
        timeframe=original.timeframe,
        start_date=original.start_date,
        end_date=original.end_date,
        param_ranges=original.param_ranges,
        metric=original.metric,
        initial_capital=original.initial_capital,
        total_combinations=original.total_combinations,
        status=OptimizationStatus.QUEUED,
        config=original.config,
    )

    db.add(new_optimization)
    db.commit()
    db.refresh(new_optimization)

    logger.info(f"Created rerun optimization {new_optimization.id} from {optimization_id}")

    strategy = db.query(Strategy).filter(Strategy.id == original.strategy_id).first()
    strategy_config = strategy.parameters if strategy else {}

    config = original.config or {}
    param_ranges = {k: ParamRangeSpec(**v) for k, v in (original.param_ranges or {}).items()}

    request = CreateOptimizationRequest(
        strategy_id=original.strategy_id,
        optimization_type=original.optimization_type.value,
        symbol=original.symbol,
        timeframe=original.timeframe,
        start_date=original.start_date.isoformat()[:10] if original.start_date else "",
        end_date=original.end_date.isoformat()[:10] if original.end_date else "",
        param_ranges=param_ranges,
        metric=original.metric,
        initial_capital=original.initial_capital,
        n_trials=config.get("n_trials", 100),
        train_size=config.get("train_size", 120),
        test_size=config.get("test_size", 60),
        step_size=config.get("step_size", 30),
        n_jobs=config.get("n_jobs", 1),
        random_state=config.get("random_state"),
    )

    background_tasks.add_task(
        launch_optimization_task,
        optimization_id=new_optimization.id,
        opt_type=original.optimization_type,
        strategy_config=strategy_config,
        request=request,
    )

    return optimization_to_response(new_optimization)


@router.get("/stats/summary")
async def get_optimization_stats(db: Session = Depends(get_db)):
    """Get summary statistics about optimization jobs."""
    from sqlalchemy import func

    total = db.query(func.count(Optimization.id)).scalar()
    completed = (
        db.query(func.count(Optimization.id)).filter(Optimization.status == OptimizationStatus.COMPLETED).scalar()
    )
    running = db.query(func.count(Optimization.id)).filter(Optimization.status == OptimizationStatus.RUNNING).scalar()
    failed = db.query(func.count(Optimization.id)).filter(Optimization.status == OptimizationStatus.FAILED).scalar()
    queued = db.query(func.count(Optimization.id)).filter(Optimization.status == OptimizationStatus.QUEUED).scalar()

    by_type = (
        db.query(Optimization.optimization_type, func.count(Optimization.id))
        .group_by(Optimization.optimization_type)
        .all()
    )

    return {
        "total": total,
        "by_status": {
            "completed": completed,
            "running": running,
            "failed": failed,
            "queued": queued,
        },
        "by_type": {t.value if hasattr(t, "value") else t: count for t, count in by_type},
    }


# =============================================================================
# СИНХРОННАЯ ОПТИМИЗАЦИЯ (без Celery)
# =============================================================================


def _run_batch_backtests(
    batch: list,
    request_params: dict,
    candles_dict: list,
    start_dt_str: str,
    end_dt_str: str,
    strategy_type_str: str,
) -> list:
    """
    Выполняет батч бэктестов в отдельном процессе.
    ОБНОВЛЕНО: Поддержка V2 движков (GPU/Numba/Fallback).
    Для ProcessPoolExecutor - все аргументы должны быть сериализуемыми.
    """
    from datetime import datetime as dt

    import pandas as pd

    from backend.backtesting.engine_selector import get_engine
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.signal_generators import generate_rsi_signals

    # Восстанавливаем DataFrame из dict
    candles = pd.DataFrame(candles_dict)
    candles["timestamp"] = pd.to_datetime(candles["timestamp"])
    candles.set_index("timestamp", inplace=True)

    # Парсим даты (validation - ensure valid datetime format)
    dt.fromisoformat(start_dt_str)  # Validate start date
    dt.fromisoformat(end_dt_str)  # Validate end date

    # Получаем движок на основе выбранного engine_type
    engine_type = request_params.get("engine_type", "auto")
    engine = get_engine(engine_type=engine_type)

    # Преобразуем direction
    direction_str = request_params.get("direction", "both")
    if direction_str == "long":
        trade_direction = TradeDirection.LONG
    elif direction_str == "short":
        trade_direction = TradeDirection.SHORT
    else:
        trade_direction = TradeDirection.BOTH

    results = []

    for combo in batch:
        period, overbought, oversold, stop_loss, take_profit = combo
        try:
            # Генерируем сигналы RSI для текущих параметров
            long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(
                candles=candles,
                period=period,
                overbought=overbought,
                oversold=oversold,
                direction=direction_str,
            )

            # Создаём BacktestInput для V2 движков
            # Position sizing: use fixed amount if specified, otherwise percentage
            use_fixed = request_params.get("use_fixed_amount", False)
            fixed_amt = request_params.get("fixed_amount", 0.0)
            pos_size = 0.1 if use_fixed else 1.0  # 10% default or 100%

            backtest_input = BacktestInput(
                candles=candles,
                candles_1m=None,  # Bar Magnifier отключен для оптимизации (скорость)
                long_entries=long_entries,
                long_exits=long_exits,
                short_entries=short_entries,
                short_exits=short_exits,
                symbol=request_params["symbol"],
                interval=request_params["interval"],
                initial_capital=request_params["initial_capital"],
                position_size=pos_size,
                use_fixed_amount=use_fixed,
                fixed_amount=fixed_amt,
                leverage=request_params["leverage"],
                stop_loss=stop_loss / 100.0 if stop_loss else 0.0,
                take_profit=take_profit / 100.0 if take_profit else 0.0,
                direction=trade_direction,
                taker_fee=request_params["commission"],
                maker_fee=request_params["commission"],
                slippage=0.0005,  # 0.05% slippage
                use_bar_magnifier=False,  # Отключаем для скорости
                max_drawdown_limit=0.0,
                pyramiding=1,
            )

            # Запуск бэктеста на выбранном движке
            bt_output = engine.run(backtest_input)

            if not bt_output.is_valid:
                continue

            metrics = bt_output.metrics
            result = {
                "total_return": metrics.total_return if metrics else 0,
                "sharpe_ratio": metrics.sharpe_ratio if metrics else 0,
                "max_drawdown": metrics.max_drawdown if metrics else 0,
                "win_rate": metrics.win_rate * 100 if metrics else 0,  # V2 возвращает 0-1, конвертируем в %
                "total_trades": metrics.total_trades if metrics else 0,
                "profit_factor": metrics.profit_factor if metrics else 0,
                # Additional metrics for full reporting
                "winning_trades": metrics.winning_trades if metrics else 0,
                "losing_trades": metrics.losing_trades if metrics else 0,
                "net_profit": metrics.net_profit if metrics else 0,
                "net_profit_pct": metrics.total_return if metrics else 0,
                "gross_profit": metrics.gross_profit if metrics else 0,
                "gross_loss": metrics.gross_loss if metrics else 0,
                "avg_win": metrics.avg_win if metrics else 0,
                "avg_loss": metrics.avg_loss if metrics else 0,
                "avg_win_value": metrics.avg_win if metrics else 0,
                "avg_loss_value": metrics.avg_loss if metrics else 0,
                "largest_win": metrics.largest_win if metrics else 0,
                "largest_loss": metrics.largest_loss if metrics else 0,
                "largest_win_value": metrics.largest_win if metrics else 0,
                "largest_loss_value": metrics.largest_loss if metrics else 0,
                "recovery_factor": metrics.recovery_factor if metrics else 0,
                "expectancy": metrics.expectancy if metrics else 0,
                "sortino_ratio": metrics.sortino_ratio if metrics else 0,
                "calmar_ratio": metrics.calmar_ratio if metrics else 0,
                "max_drawdown_value": 0,
                # Long/Short breakdown for TV parity
                "long_trades": metrics.long_trades if metrics else 0,
                "long_winning_trades": getattr(metrics, "long_winning_trades", 0) if metrics else 0,
                "long_losing_trades": getattr(metrics, "long_losing_trades", 0) if metrics else 0,
                "long_win_rate": metrics.long_win_rate * 100 if metrics else 0,
                "long_gross_profit": getattr(metrics, "long_gross_profit", 0) if metrics else 0,
                "long_gross_loss": getattr(metrics, "long_gross_loss", 0) if metrics else 0,
                "long_net_profit": metrics.long_profit if metrics else 0,
                "long_profit_factor": getattr(metrics, "long_profit_factor", 0) if metrics else 0,
                "long_avg_win": getattr(metrics, "long_avg_win", 0) if metrics else 0,
                "long_avg_loss": getattr(metrics, "long_avg_loss", 0) if metrics else 0,
                "short_trades": metrics.short_trades if metrics else 0,
                "short_winning_trades": getattr(metrics, "short_winning_trades", 0) if metrics else 0,
                "short_losing_trades": getattr(metrics, "short_losing_trades", 0) if metrics else 0,
                "short_win_rate": metrics.short_win_rate * 100 if metrics else 0,
                "short_gross_profit": getattr(metrics, "short_gross_profit", 0) if metrics else 0,
                "short_gross_loss": getattr(metrics, "short_gross_loss", 0) if metrics else 0,
                "short_net_profit": metrics.short_profit if metrics else 0,
                "short_profit_factor": getattr(metrics, "short_profit_factor", 0) if metrics else 0,
                "short_avg_win": getattr(metrics, "short_avg_win", 0) if metrics else 0,
                "short_avg_loss": getattr(metrics, "short_avg_loss", 0) if metrics else 0,
                # Duration metrics
                "avg_bars_in_trade": metrics.avg_trade_duration if metrics else 0,
                "avg_bars_in_winning": metrics.avg_winning_duration if metrics else 0,
                "avg_bars_in_losing": metrics.avg_losing_duration if metrics else 0,
                # Commission
                "total_commission": sum(t.fees for t in bt_output.trades) if bt_output.trades else 0,
            }

            # Проверить фильтры с учётом форматов (win_rate приходит в процентах)
            if not _passes_filters(result, request_params):
                continue

            # Унифицированный расчёт метрики/скора
            score = _calculate_composite_score(
                result,
                request_params.get("optimize_metric", "sharpe_ratio"),
                request_params.get("weights"),
            )

            # Serialize trades for best results (limit to avoid memory issues)
            trades_data = []
            if bt_output.trades:
                for t in bt_output.trades[:500]:  # Limit to 500 trades
                    # Calculate duration if we have entry and exit times
                    duration_hours = 0
                    if t.entry_time and t.exit_time:
                        duration_hours = (t.exit_time - t.entry_time).total_seconds() / 3600

                    trades_data.append(
                        {
                            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                            # V2 uses 'direction' field instead of 'side'
                            "side": t.direction
                            if hasattr(t, "direction")
                            else (
                                t.side.value
                                if hasattr(t, "side") and hasattr(t.side, "value")
                                else str(getattr(t, "side", "unknown"))
                            ),
                            "entry_price": float(t.entry_price) if t.entry_price else 0,
                            "exit_price": float(t.exit_price) if t.exit_price else 0,
                            "size": float(t.size) if t.size else 0,
                            "pnl": float(t.pnl) if t.pnl else 0,
                            "pnl_pct": float(t.pnl_pct) if hasattr(t, "pnl_pct") and t.pnl_pct else 0,
                            "return_pct": float(t.pnl_pct) if hasattr(t, "pnl_pct") and t.pnl_pct else 0,
                            "fees": float(t.fees) if hasattr(t, "fees") and t.fees else 0,
                            "duration_hours": duration_hours,
                            # MFE/MAE (TradingView style)
                            "mfe": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                            "mae": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
                            "mfe_pct": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                            "mae_pct": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
                        }
                    )

            # Serialize equity curve (sample if too large)
            # V2 BacktestOutput has equity_curve as numpy array, timestamps as numpy array
            equity_data = None
            if bt_output.equity_curve is not None and len(bt_output.equity_curve) > 0:
                equity = bt_output.equity_curve
                timestamps = bt_output.timestamps if bt_output.timestamps is not None else []
                # Sample if too many points
                step = max(1, len(equity) // 500)
                equity_data = {
                    "timestamps": [
                        t.isoformat() if hasattr(t, "isoformat") else str(t)
                        for t in (timestamps[::step] if len(timestamps) > 0 else [])
                    ],
                    "equity": [float(e) for e in equity[::step]],
                    "drawdown": [],  # V2 computes drawdown separately in metrics
                    "returns": [],
                }

            results.append(
                {
                    "params": {
                        "rsi_period": period,
                        "rsi_overbought": overbought,
                        "rsi_oversold": oversold,
                        "stop_loss_pct": stop_loss,
                        "take_profit_pct": take_profit,
                    },
                    "score": score,
                    # Core metrics
                    "total_return": result["total_return"],
                    "sharpe_ratio": result["sharpe_ratio"],
                    "max_drawdown": result["max_drawdown"],
                    "win_rate": result["win_rate"],
                    "total_trades": result["total_trades"],
                    "profit_factor": result["profit_factor"],
                    # Extended metrics
                    "winning_trades": result["winning_trades"],
                    "losing_trades": result["losing_trades"],
                    "net_profit": result["net_profit"],
                    "net_profit_pct": result["net_profit_pct"],
                    "gross_profit": result["gross_profit"],
                    "gross_loss": result["gross_loss"],
                    "max_drawdown_value": result["max_drawdown_value"],
                    "avg_win": result["avg_win"],
                    "avg_loss": result["avg_loss"],
                    "avg_win_value": result.get("avg_win_value", result["avg_win"]),
                    "avg_loss_value": result.get("avg_loss_value", result["avg_loss"]),
                    "largest_win": result["largest_win"],
                    "largest_loss": result["largest_loss"],
                    "recovery_factor": result["recovery_factor"],
                    "expectancy": result["expectancy"],
                    "sortino_ratio": result["sortino_ratio"],
                    "calmar_ratio": result["calmar_ratio"],
                    "total_commission": result.get("total_commission", 0),
                    # Trade and equity data
                    "trades": trades_data,
                    "equity_curve": equity_data,
                }
            )
        except Exception as e:
            logger.warning("Skipped failed backtest in grid: %s", e)

    return results


def _run_single_backtest_for_process(args: tuple) -> dict:
    """
    Выполняет один бэктест для заданных параметров.
    Версия для ProcessPoolExecutor - принимает tuple аргументов.
    """
    (
        period,
        overbought,
        oversold,
        request_params,
        candles_dict,
        start_dt_str,
        end_dt_str,
    ) = args

    from datetime import datetime as dt

    import pandas as pd

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType

    try:
        # Восстанавливаем DataFrame из dict
        candles = pd.DataFrame(candles_dict)
        candles["timestamp"] = pd.to_datetime(candles["timestamp"])
        candles.set_index("timestamp", inplace=True)

        # Парсим даты
        start_dt = dt.fromisoformat(start_dt_str)
        end_dt = dt.fromisoformat(end_dt_str)

        # Собрать конфигурацию стратегии
        strategy_params = {
            "period": period,
            "overbought": overbought,
            "oversold": oversold,
        }

        # Преобразуем strategy_type в StrategyType enum
        if request_params["strategy_type"].lower() == "rsi":
            strategy_type = StrategyType.RSI
        else:
            strategy_type = StrategyType.SMA_CROSSOVER

        config = BacktestConfig(
            symbol=request_params["symbol"],
            interval=request_params["interval"],
            start_date=start_dt,
            end_date=end_dt,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            initial_capital=request_params["initial_capital"],
            leverage=request_params["leverage"],
            direction=request_params["direction"],
            stop_loss=request_params["stop_loss_percent"] / 100.0 if request_params["stop_loss_percent"] else None,
            take_profit=request_params["take_profit_percent"] / 100.0
            if request_params["take_profit_percent"]
            else None,
            taker_fee=request_params["commission"],
            maker_fee=request_params["commission"],
        )

        engine = BacktestEngine()
        bt_result = engine.run(config, candles)

        # BacktestResult -> dict
        result = {
            "total_return": bt_result.metrics.total_return if bt_result.metrics else 0,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio if bt_result.metrics else 0,
            "max_drawdown": bt_result.metrics.max_drawdown if bt_result.metrics else 0,
            "win_rate": bt_result.metrics.win_rate if bt_result.metrics else 0,
            "total_trades": bt_result.metrics.total_trades if bt_result.metrics else 0,
            "profit_factor": bt_result.metrics.profit_factor if bt_result.metrics else 0,
        }

        # Получить значение метрики
        metric_value = result.get(request_params["optimize_metric"], 0) or 0

        return {
            "params": {
                "rsi_period": period,
                "rsi_overbought": overbought,
                "rsi_oversold": oversold,
            },
            "score": metric_value,
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "win_rate": result.get("win_rate", 0),
            "total_trades": result.get("total_trades", 0),
        }
    except Exception:
        return None


def _calculate_composite_score(result: dict, metric: str, weights: dict = None) -> float:
    """
    Вычисляет композитный скор для результата бэктеста.

    Поддерживаемые метрики:
    - net_profit: чистая прибыль (больше = лучше) - PRIMARY
    - max_drawdown: максимальная просадка (меньше = лучше) - PRIMARY
    - sharpe_ratio, total_return, win_rate, profit_factor (простые)
    - calmar_ratio: Return / MaxDrawdown (чем выше, тем лучше)
    - risk_adjusted_return: Return * (1 - Drawdown/100)

    Примечание: max_drawdown приходит в ПРОЦЕНТАХ (17.29 = 17.29%)
    """
    total_return = result.get("total_return", 0) or 0
    sharpe_ratio = result.get("sharpe_ratio", 0) or 0
    net_profit = result.get("net_profit", 0) or 0
    # max_drawdown уже в процентах, конвертируем в долю для расчётов
    max_drawdown_pct = abs(result.get("max_drawdown", 0) or 0)
    max_drawdown = max_drawdown_pct / 100.0  # Теперь в долях (0.1729)
    # Win rate from engine is in PERCENT (0-100). Normalize to fraction for calculations.
    win_rate_pct = result.get("win_rate", 0) or 0
    win_rate = win_rate_pct / 100.0
    profit_factor = result.get("profit_factor", 1) or 1

    # Простые метрики
    if metric == "net_profit":
        # Total P&L - больше = лучше
        return net_profit
    elif metric == "sharpe_ratio":
        return sharpe_ratio
    elif metric == "total_return":
        return total_return
    elif metric == "win_rate":
        return win_rate
    elif metric == "profit_factor":
        return profit_factor
    elif metric == "max_drawdown":
        # Инвертируем: меньше просадка = лучше (возвращаем отрицательное)
        return -max_drawdown_pct  # В процентах для сортировки

    # Композитные метрики
    elif metric == "calmar_ratio":
        # Calmar = Return / Max Drawdown (оба в %)
        # Положительный = хорошо, отрицательный = плохо
        if max_drawdown_pct > 0.01:
            calmar = total_return / max_drawdown_pct
            return calmar  # Может быть отрицательным при убытке
        return total_return * 10 if total_return > 0 else total_return

    elif metric == "risk_adjusted_return":
        # Risk-Adjusted Return - работает с любой просадкой
        # Используем формулу: Return / (1 + Drawdown)
        # При DD=0%: score = return, при DD=100%: score = return/2
        drawdown_factor = 1 + max_drawdown  # max_drawdown в долях (1.729 = 172.9%)
        return total_return / drawdown_factor

    # По умолчанию - net_profit
    return net_profit


def _rank_by_multi_criteria(results: list, selection_criteria: list) -> list:
    """
    Ранжирует результаты по нескольким критериям.

    Логика:
    - net_profit: больше = лучше (ранг по убыванию)
    - max_drawdown: меньше = лучше (ранг по возрастанию)

    Если выбрано несколько критериев, вычисляем средний ранг.
    Лучший результат = минимальный средний ранг.
    """
    if not results or not selection_criteria:
        return results

    # Определяем направление для каждого критерия
    # True = больше лучше, False = меньше лучше
    criteria_direction = {
        "net_profit": True,  # больше = лучше
        "max_drawdown": False,  # меньше = лучше (абсолютное значение)
        "sharpe_ratio": True,
        "total_return": True,
        "win_rate": True,
        "profit_factor": True,
        "total_trades": True,
    }

    n = len(results)

    # Для каждого критерия вычисляем ранги
    for criterion in selection_criteria:
        if criterion not in criteria_direction:
            continue

        higher_is_better = criteria_direction[criterion]

        # Получаем значение метрики для каждого результата
        def get_value(r):
            if criterion == "max_drawdown":
                return abs(r.get(criterion, 0) or 0)  # Используем абсолютное значение
            return r.get(criterion, 0) or 0

        # Сортируем индексы по значению
        sorted_indices = sorted(
            range(n),
            key=lambda i: get_value(results[i]),
            reverse=higher_is_better,  # Если больше лучше, сортируем по убыванию
        )

        # Присваиваем ранги (1 = лучший)
        for rank, idx in enumerate(sorted_indices, 1):
            if "_ranks" not in results[idx]:
                results[idx]["_ranks"] = {}
            results[idx]["_ranks"][criterion] = rank

    # Вычисляем средний ранг
    for r in results:
        ranks = r.get("_ranks", {})
        if ranks:
            r["_avg_rank"] = sum(ranks.values()) / len(ranks)
        else:
            r["_avg_rank"] = n  # Худший ранг

    # Сортируем по среднему рангу (меньше = лучше)
    sorted_results = sorted(results, key=lambda x: x.get("_avg_rank", n))

    # Устанавливаем итоговый score как отрицательный средний ранг
    # (чтобы сохранить совместимость с существующей сортировкой)
    for r in sorted_results:
        r["score"] = -r.get("_avg_rank", n)
        # Удаляем временные поля
        r.pop("_ranks", None)
        r.pop("_avg_rank", None)

    return sorted_results


def _compute_weighted_composite(result: dict, weights: dict) -> float:
    """Compute weighted composite score from evaluation criteria weights.

    Args:
        result: Optimization result dict with metrics
        weights: Dict mapping metric names to weights (should sum to 1.0)
            Example: {"profit_factor": 0.4, "sharpe_ratio": 0.3, "max_drawdown": 0.3}

    Returns:
        Weighted composite score (higher is better)
    """
    if not weights:
        return 0.0

    score = 0.0

    for metric, weight in weights.items():
        value = result.get(metric, 0) or 0

        # Normalize based on metric type
        if metric == "profit_factor":
            # PF: 0-3 is typical range, cap at 5
            normalized = min(value, 5.0) / 5.0
        elif metric == "sharpe_ratio":
            # Sharpe: -2 to +3 typical, normalize to 0-1
            normalized = (min(max(value, -2.0), 3.0) + 2.0) / 5.0
        elif metric == "max_drawdown":
            # Drawdown: 0-100%, lower is better, invert
            normalized = 1.0 - min(abs(value), 100.0) / 100.0
        elif metric == "win_rate":
            # Win rate: 0-100%
            normalized = min(value, 100.0) / 100.0
        elif metric == "total_return":
            # Return: -100% to +500% typical
            normalized = (min(max(value, -100.0), 500.0) + 100.0) / 600.0
        elif metric == "calmar_ratio":
            # Calmar: -5 to +10 typical
            normalized = (min(max(value, -5.0), 10.0) + 5.0) / 15.0
        elif metric == "recovery_factor":
            # Recovery: 0-10 typical
            normalized = min(value, 10.0) / 10.0
        else:
            # Unknown metric - use raw value capped at 0-1
            normalized = min(max(value, 0.0), 1.0)

        score += normalized * weight

    return round(score, 4)


def _apply_custom_sort_order(results: list, sort_order: list[dict]) -> list:
    """Apply custom multi-level sorting from frontend.

    Sort order format: [{"metric": "sharpe_ratio", "direction": "desc"}, ...]
    Direction: "asc" (ascending) or "desc" (descending)
    """
    if not results or not sort_order:
        return results

    # Build sort key function for multi-level sorting
    def get_sort_key(result):
        keys = []
        for level in sort_order:
            metric = level.get("metric", "score")
            direction = level.get("direction", "desc")

            value = result.get(metric, 0) or 0

            # For numeric values, handle direction
            if isinstance(value, (int, float)):
                # Descending: negate so larger values come first
                keys.append(-value if direction == "desc" else value)
            else:
                keys.append(value)

        return tuple(keys)

    return sorted(results, key=get_sort_key)


def _generate_smart_recommendations(results: list) -> dict:
    """
    Генерирует умные рекомендации на основе результатов оптимизации.
    Анализирует все результаты и предлагает лучшие варианты по разным критериям.
    """
    if not results:
        return {
            "best_balanced": None,
            "best_conservative": None,
            "best_aggressive": None,
            "recommendation_text": "Нет результатов для анализа",
        }

    # Фильтруем только прибыльные результаты
    profitable = [r for r in results if r.get("total_return", 0) > 0]

    recommendations = {
        "best_balanced": None,
        "best_conservative": None,
        "best_aggressive": None,
        "recommendation_text": "",
    }

    if not profitable:
        # Если нет прибыльных, берём наименее убыточный
        sorted_by_return = sorted(results, key=lambda x: x.get("total_return", -999), reverse=True)
        if sorted_by_return:
            recommendations["best_balanced"] = sorted_by_return[0]
            recommendations["recommendation_text"] = (
                "⚠️ Все комбинации убыточны. Рекомендуем изменить параметры стратегии или период тестирования."
            )
        return recommendations

    # 1. ЛУЧШИЙ СБАЛАНСИРОВАННЫЙ - максимальный Calmar Ratio (Return / Drawdown)
    for r in profitable:
        dd = abs(r.get("max_drawdown", 1)) or 1
        r["_calmar"] = r.get("total_return", 0) / dd

    sorted_by_calmar = sorted(profitable, key=lambda x: x.get("_calmar", 0), reverse=True)
    recommendations["best_balanced"] = sorted_by_calmar[0] if sorted_by_calmar else None

    # 2. ЛУЧШИЙ КОНСЕРВАТИВНЫЙ - минимальная просадка при положительной доходности
    # Сортируем по просадке (меньше = лучше), но только прибыльные
    sorted_by_dd = sorted(profitable, key=lambda x: abs(x.get("max_drawdown", 999)))
    recommendations["best_conservative"] = sorted_by_dd[0] if sorted_by_dd else None

    # 3. ЛУЧШИЙ АГРЕССИВНЫЙ - максимальная доходность
    sorted_by_return = sorted(profitable, key=lambda x: x.get("total_return", 0), reverse=True)
    recommendations["best_aggressive"] = sorted_by_return[0] if sorted_by_return else None

    # Генерируем текст рекомендации
    balanced = recommendations["best_balanced"]
    conservative = recommendations["best_conservative"]
    aggressive = recommendations["best_aggressive"]

    texts = []

    def _format_params(r):
        """Форматирует параметры для отображения"""
        p = r.get("params", {})
        rsi_str = f"RSI({p.get('rsi_period')}, {p.get('rsi_overbought')}, {p.get('rsi_oversold')})"
        tpsl_str = f"SL={p.get('stop_loss_pct', 10)}%, TP={p.get('take_profit_pct', 1.5)}%"
        return f"{rsi_str}, {tpsl_str}"

    if balanced:
        texts.append(
            f"🎯 **Сбалансированный**: {_format_params(balanced)} - "
            f"Return {balanced.get('total_return', 0):.1f}%, DD {abs(balanced.get('max_drawdown', 0)):.1f}%"
        )

    if conservative and conservative != balanced:
        texts.append(
            f"🛡️ **Консервативный**: {_format_params(conservative)} - "
            f"Return {conservative.get('total_return', 0):.1f}%, DD {abs(conservative.get('max_drawdown', 0)):.1f}%"
        )

    if aggressive and aggressive != balanced:
        texts.append(
            f"🚀 **Агрессивный**: {_format_params(aggressive)} - "
            f"Return {aggressive.get('total_return', 0):.1f}%, DD {abs(aggressive.get('max_drawdown', 0)):.1f}%"
        )

    recommendations["recommendation_text"] = "\n".join(texts)

    # Убираем временные поля
    for r in profitable:
        r.pop("_calmar", None)

    return recommendations


def _passes_filters(result: dict, request_params: dict) -> bool:
    """Проверяет, проходит ли результат фильтры."""
    # Минимум сделок
    min_trades = request_params.get("min_trades")
    if min_trades is not None and (result.get("total_trades", 0) or 0) < min_trades:
        return False

    # Максимальная просадка (limit приходит как доля 0-1, max_drawdown в процентах)
    max_dd_limit = request_params.get("max_drawdown_limit")
    if max_dd_limit is not None:
        max_dd_pct = abs(result.get("max_drawdown", 0) or 0)  # В процентах
        max_dd_limit_pct = max_dd_limit * 100  # Конвертируем лимит в проценты
        if max_dd_pct > max_dd_limit_pct:
            return False

    # Минимальный Profit Factor
    min_pf = request_params.get("min_profit_factor")
    if min_pf is not None and (result.get("profit_factor", 0) or 0) < min_pf:
        return False

    # Минимальный Win Rate (limit приходит как доля 0-1, результат в процентах)
    min_wr = request_params.get("min_win_rate")
    if min_wr is not None:
        win_rate_pct = result.get("win_rate", 0) or 0
        win_rate_fraction = win_rate_pct / 100.0
        if win_rate_fraction < min_wr:
            return False

    # Dynamic constraints from frontend EvaluationCriteriaPanel
    constraints = request_params.get("constraints")
    if constraints and not _passes_dynamic_constraints(result, constraints):
        return False

    return True


def _passes_dynamic_constraints(result: dict, constraints: list[dict]) -> bool:
    """Check if result passes all dynamic constraints from frontend.

    Constraint format: {"metric": "max_drawdown", "operator": "<=", "value": 15}
    Supported operators: <=, >=, <, >, ==, !=
    """
    for constraint in constraints:
        metric = constraint.get("metric")
        operator = constraint.get("operator")
        threshold = constraint.get("value")

        if not all([metric, operator, threshold is not None]):
            continue

        # Get metric value from result
        value = result.get(metric, 0) or 0

        # For percentage metrics stored as negative (like max_drawdown), use absolute
        if metric in ("max_drawdown", "avg_drawdown") and value < 0:
            value = abs(value)

        # Apply operator
        try:
            if (operator == "<=" and value > threshold) or (operator == ">=" and value < threshold) or (operator == "<" and value >= threshold) or (operator == ">" and value <= threshold) or (operator == "==" and value != threshold) or (operator == "!=" and value == threshold):
                return False
        except (TypeError, ValueError):
            continue

    return True


def _run_single_backtest(
    period: int,
    overbought: int,
    oversold: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    request_params: dict,
    candles,  # pandas DataFrame уже готовый
    start_dt,
    end_dt,
    engine,  # BacktestEngine уже создан
    strategy_type,  # StrategyType уже определён
) -> dict:
    """
    Выполняет один бэктест для заданных параметров.
    Функция для параллельного выполнения.
    Оптимизировано: переиспользует engine и candles DataFrame.
    """
    from backend.backtesting.models import BacktestConfig

    try:
        # Собрать конфигурацию стратегии
        strategy_params = {
            "period": period,
            "overbought": overbought,
            "oversold": oversold,
        }

        # Расчёт размера позиции: поддержка фиксированной суммы сделки
        position_size = 1.0  # по умолчанию используем весь капитал на сделку
        if request_params.get("use_fixed_amount"):
            fixed_amount = request_params.get("fixed_amount") or 0
            initial_capital = request_params.get("initial_capital") or 1
            # Преобразуем фиксированную сумму в долю капитала, ограничиваем 0-1
            position_size = max(0.0001, min(1.0, fixed_amount / initial_capital))

        config = BacktestConfig(
            symbol=request_params["symbol"],
            interval=request_params["interval"],
            start_date=start_dt,
            end_date=end_dt,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            initial_capital=request_params["initial_capital"],
            position_size=position_size,
            leverage=request_params["leverage"],
            direction=request_params["direction"],
            stop_loss=stop_loss_pct / 100.0 if stop_loss_pct else None,
            take_profit=take_profit_pct / 100.0 if take_profit_pct else None,
            taker_fee=request_params["commission"],
            maker_fee=request_params["commission"],
            commission_on_margin=True,  # TradingView-compatible commission calculation
        )

        # silent=True для ускорения массового выполнения
        bt_result = engine.run(config, candles, silent=True)

        # BacktestResult -> dict
        result = {
            "total_return": bt_result.metrics.total_return if bt_result.metrics else 0,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio if bt_result.metrics else 0,
            "max_drawdown": bt_result.metrics.max_drawdown if bt_result.metrics else 0,
            "win_rate": bt_result.metrics.win_rate if bt_result.metrics else 0,
            "total_trades": bt_result.metrics.total_trades if bt_result.metrics else 0,
            "profit_factor": bt_result.metrics.profit_factor if bt_result.metrics else 0,
        }

        # Проверить фильтры
        if not _passes_filters(result, request_params):
            return None  # Результат не прошёл фильтры

        # Вычислить композитный скор
        metric_value = _calculate_composite_score(
            result, request_params["optimize_metric"], request_params.get("weights")
        )

        return {
            "params": {
                "rsi_period": period,
                "rsi_overbought": overbought,
                "rsi_oversold": oversold,
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
            },
            "score": metric_value,
            "total_return": result.get("total_return", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "max_drawdown": result.get("max_drawdown", 0),
            "win_rate": result.get("win_rate", 0),
            "total_trades": result.get("total_trades", 0),
            "profit_factor": result.get("profit_factor", 0),
            "calmar_ratio": result.get("total_return", 0) / max(abs(result.get("max_drawdown", 0.01) * 100), 0.01),
        }
    except Exception as e:
        from loguru import logger

        logger.warning(
            f"Backtest failed for period={period}, ob={overbought}, os={oversold}, SL={stop_loss_pct}, TP={take_profit_pct}: {e}"
        )
        return None


class SyncOptimizationRequest(BaseModel):
    """Запрос для синхронной оптимизации"""

    symbol: str = "BTCUSDT"
    interval: str = "30m"
    start_date: str = "2025-01-01"
    end_date: str = "2025-06-01"

    # Базовые параметры стратегии
    strategy_type: str = "rsi"
    direction: str = "long"
    use_fixed_amount: bool = True
    fixed_amount: float = 100.0
    leverage: int = 10
    initial_capital: float = 10000.0
    commission: float = 0.0007  # 0.07% TradingView parity

    # Пространство параметров для оптимизации RSI (списки значений)
    rsi_period_range: list[int] = [7, 14, 21]
    rsi_overbought_range: list[int] = [70, 75, 80]
    rsi_oversold_range: list[int] = [20, 25, 30]

    # Пространство параметров TP/SL (списки значений в процентах)
    stop_loss_range: list[float] = [10.0]  # По умолчанию одно значение
    take_profit_range: list[float] = [1.5]  # По умолчанию одно значение

    # Метрика для оптимизации (основная, для обратной совместимости)
    optimize_metric: str = "net_profit"

    # Новая система: массив критериев отбора
    # net_profit - Total P&L (больше = лучше)
    # max_drawdown - Max Equity Drawdown (меньше = лучше)
    selection_criteria: list[str] = ["net_profit", "max_drawdown"]

    # Выбор движка бэктеста
    # auto - автоматический выбор (GPU > Numba > Fallback)
    # gpu - CUDA-ускорение
    # numba - JIT-компиляция
    # fallback - чистый Python (эталонная реализация)
    engine_type: str = "auto"

    # Метод поиска оптимальных параметров
    # grid - Grid Search (все комбинации)
    # random - Random Search (случайная выборка)
    search_method: str = "grid"

    # Максимум итераций для Random Search (игнорируется для Grid)
    # Если 0 - используется 10% от общего числа комбинаций
    max_iterations: int = 0

    # Тип рынка для источника данных
    # spot - данные спотового рынка (идентичны TradingView для паритета сигналов)
    # linear - перпетуальные фьючерсы (для реальной торговли)
    market_type: str = "linear"

    # Гибридный pipeline: после оптимизации на Numba/GPU перепроверить best_params на FallbackV4
    # Даёт эталонные метрики для аудита (при Numba паритет 100%, drift = 0)
    validate_best_with_fallback: bool = False

    # Market Regime Filter (P1 Regime integration)
    # При включении используется FallbackV4 (Numba не поддерживает regime)
    market_regime_enabled: bool = False
    market_regime_filter: str = "not_volatile"  # all|trending|ranging|volatile|not_volatile
    market_regime_lookback: int = 50

    # === NEW: Evaluation Criteria from Frontend ===
    # Dynamic constraints from EvaluationCriteriaPanel
    # Format: [{"metric": "max_drawdown", "operator": "<=", "value": 15}, ...]
    constraints: list[dict] | None = None

    # Multi-level sort order
    # Format: [{"metric": "sharpe_ratio", "direction": "desc"}, ...]
    sort_order: list[dict] | None = None

    # Composite scoring (weighted metrics)
    use_composite: bool = False
    weights: dict[str, float] | None = None


class OptimizationResult(BaseModel):
    """Результат одной комбинации параметров"""

    params: dict[str, Any]
    score: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int


class SmartRecommendation(BaseModel):
    """Одна рекомендация"""

    params: dict[str, Any] | None = None
    total_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    win_rate: float | None = None
    total_trades: int | None = None


class SmartRecommendations(BaseModel):
    """Умные рекомендации системы"""

    best_balanced: SmartRecommendation | None = None
    best_conservative: SmartRecommendation | None = None
    best_aggressive: SmartRecommendation | None = None
    recommendation_text: str = ""


class SyncOptimizationResponse(BaseModel):
    """Ответ синхронной оптимизации"""

    status: str
    total_combinations: int
    tested_combinations: int
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    execution_time_seconds: float
    speed_combinations_per_sec: int | None = None  # Actual speed achieved
    num_workers: int | None = None  # Number of parallel workers used
    smart_recommendations: SmartRecommendations | None = None
    # Hybrid pipeline: эталонные метрики от FallbackV4 (при validate_best_with_fallback=True)
    validated_metrics: dict[str, Any] | None = None


@router.post("/sync/grid-search", response_model=SyncOptimizationResponse)
async def sync_grid_search_optimization(
    request: SyncOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    Синхронная Grid Search оптимизация (без Celery).

    Тестирует все комбинации параметров RSI и возвращает лучшие результаты.
    Подходит для небольшого пространства параметров (до 100-200 комбинаций).
    """
    import time
    from datetime import datetime as dt

    import pandas as pd

    from backend.services.data_service import DataService

    start_time = time.time()

    logger.info("🔍 Starting sync grid search optimization")
    logger.info(f"   Symbol: {request.symbol}, Interval: {request.interval}")
    logger.info(f"   Period range: {request.rsi_period_range}")
    logger.info(f"   Overbought range: {request.rsi_overbought_range}")
    logger.info(f"   Oversold range: {request.rsi_oversold_range}")

    # Normalize interval format for database queries (4h -> 240, 1h -> 60, etc.)
    db_interval = _normalize_interval(request.interval)
    logger.info(f"   Normalized interval: {request.interval} -> {db_interval}")

    try:
        # Преобразовать строки дат в datetime
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        logger.error(f"Date parsing error: {parse_err}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    try:
        # Загрузить данные с учётом market_type (SPOT для паритета с TV, LINEAR для фьючерсов)
        market_type = getattr(request, "market_type", "linear")
        logger.info(f"   Market type: {market_type}")

        data_service = DataService(db)
        candle_records = data_service.get_market_data(
            symbol=request.symbol,
            timeframe=db_interval,  # Use normalized interval
            start_time=start_dt,
            end_time=end_dt,
            market_type=market_type,  # SPOT or LINEAR data filter
        )
    except Exception as data_err:
        logger.error(f"Data loading error: {data_err}")
        raise HTTPException(status_code=500, detail=f"Data loading failed: {data_err}")

    if not candle_records:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} {request.interval} ({market_type}) from {request.start_date} to {request.end_date}",
        )

    # Конвертируем в DataFrame для движка бэктеста
    candles = pd.DataFrame(
        [
            {
                "timestamp": pd.to_datetime(c.open_time, unit="ms", utc=True),
                "open": float(c.open_price) if c.open_price else 0,
                "high": float(c.high_price) if c.high_price else 0,
                "low": float(c.low_price) if c.low_price else 0,
                "close": float(c.close_price) if c.close_price else 0,
                "volume": float(c.volume) if c.volume else 0,
            }
            for c in candle_records
        ]
    )
    # Устанавливаем timestamp как индекс
    candles.set_index("timestamp", inplace=True)

    logger.info(f"📊 Loaded {len(candles)} candles")

    # Генерация комбинаций параметров (RSI + TP/SL)
    # Fix: empty lists cause product() to return no combinations
    # Default to [0] (no SL/TP) if range is empty
    sl_range = request.stop_loss_range if request.stop_loss_range else [0]
    tp_range = request.take_profit_range if request.take_profit_range else [0]

    param_combinations = list(
        product(
            request.rsi_period_range,
            request.rsi_overbought_range,
            request.rsi_oversold_range,
            sl_range,
            tp_range,
        )
    )

    total_combinations = len(param_combinations)

    # Random Search: sample subset of combinations
    search_method = getattr(request, "search_method", "grid").lower()
    if search_method == "random":
        import random

        max_iter = getattr(request, "max_iterations", 0)
        if max_iter <= 0:
            max_iter = max(10, total_combinations // 10)  # Default: 10% of total

        if max_iter < total_combinations:
            param_combinations = random.sample(param_combinations, max_iter)
            logger.info(f"🎲 Random Search: sampling {max_iter} from {total_combinations} combinations")
            total_combinations = max_iter
        else:
            logger.info(f"🎲 Random Search: using all {total_combinations} combinations (< max_iterations)")
    else:
        logger.info(f"🔢 Grid Search: testing all {total_combinations} parameter combinations")

    # No limit - user is informed about time estimate in UI

    # Запуск бэктестов
    from backend.backtesting.models import StrategyType

    results = []

    best_score = float("-inf")
    best_params = None
    best_result = None

    # Market Regime: Numba не поддерживает regime → при включении используем FallbackV4
    effective_engine = request.engine_type
    if getattr(request, "market_regime_enabled", False):
        effective_engine = "fallback_v4"
        logger.info("📊 Market regime enabled → using FallbackV4 for regime filter support")

    # Подготовить параметры запроса для передачи в worker
    request_params = {
        "symbol": request.symbol,
        "interval": db_interval,  # Use normalized interval for BacktestConfig
        "initial_capital": request.initial_capital,
        "leverage": request.leverage,
        "direction": request.direction,
        "commission": request.commission,
        "strategy_type": request.strategy_type,
        "optimize_metric": request.optimize_metric,
        "use_fixed_amount": request.use_fixed_amount,
        "fixed_amount": request.fixed_amount,
        # Новая система: массив критериев отбора
        "selection_criteria": request.selection_criteria,
        # Выбранный движок (fallback при regime)
        "engine_type": effective_engine,
        # Market Regime Filter (P1)
        "market_regime_enabled": getattr(request, "market_regime_enabled", False),
        "market_regime_filter": getattr(request, "market_regime_filter", "not_volatile"),
        "market_regime_lookback": getattr(request, "market_regime_lookback", 50),
        # EvaluationCriteriaPanel: constraints, sort_order, composite score
        "constraints": getattr(request, "constraints", None),
        "sort_order": getattr(request, "sort_order", None),
        "use_composite": getattr(request, "use_composite", False),
        "weights": getattr(request, "weights", None),
    }

    # Преобразуем strategy_type в StrategyType enum (сохраняем в request_params)
    if request.strategy_type.lower() == "rsi":
        request_params["strategy_type_enum"] = StrategyType.RSI
    else:
        request_params["strategy_type_enum"] = StrategyType.SMA_CROSSOVER

    # Smart execution strategy based on engine type:
    # - GPU Batch: ultra-fast batch optimization (GPU accelerated)
    # - GPU/Numba: single-process (avoid CUDA context issues, JIT warmup)
    # - Fallback: multiprocessing (CPU parallelism)
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    engine_type = effective_engine.lower()
    completed = 0  # Initialize counter

    logger.info(f"🔧 Engine type requested: {engine_type}")

    # GPU Batch Optimization - ultra fast screening + full verification
    if engine_type == "gpu" and total_combinations >= 50 and request.strategy_type.lower() == "rsi":
        logger.info(f"🚀 Using GPU Batch Optimizer (hybrid mode) for {total_combinations} combinations")

        try:
            from backend.backtesting.engine_selector import get_engine
            from backend.backtesting.gpu_batch_optimizer import GPUBatchOptimizer
            from backend.backtesting.interfaces import BacktestInput, TradeDirection
            from backend.backtesting.signal_generators import generate_rsi_signals

            # Phase 1: Fast GPU Batch screening
            batch_optimizer = GPUBatchOptimizer()
            batch_results = batch_optimizer.optimize_rsi_batch(
                candles=candles,
                param_combinations=param_combinations,
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                commission=request.commission,
                direction=request.direction,
            )

            # Sort by score and take top 20 for verification
            batch_with_scores = []
            for res in batch_results:
                result_entry = {
                    "total_return": res.total_return,
                    "sharpe_ratio": res.sharpe_ratio,
                    "max_drawdown": res.max_drawdown,
                    "win_rate": res.win_rate,
                    "total_trades": res.total_trades,
                    "profit_factor": res.profit_factor,
                    "net_profit": res.net_profit,
                    "params": res.params,
                }
                score = _calculate_composite_score(
                    result_entry,
                    request_params.get("optimize_metric", "sharpe_ratio"),
                    request_params.get("weights"),
                )
                result_entry["score"] = score
                batch_with_scores.append(result_entry)

            # Sort by score descending
            batch_with_scores.sort(key=lambda x: x["score"], reverse=True)

            # Phase 2: Full verification of top candidates
            top_n = min(100, len(batch_with_scores))  # Verify top 100 for better accuracy
            logger.info(f"🔍 Phase 2: Verifying top {top_n} candidates with full engine")

            # Get full engine for verification
            engine = get_engine(engine_type="numba")  # Use Numba for verification (faster than fallback)

            # Convert direction
            direction_str = request_params.get("direction", "both")
            if direction_str == "long":
                trade_direction = TradeDirection.LONG
            elif direction_str == "short":
                trade_direction = TradeDirection.SHORT
            else:
                trade_direction = TradeDirection.BOTH

            for candidate in batch_with_scores[:top_n]:
                params = candidate["params"]
                period = params["rsi_period"]
                overbought = params["rsi_overbought"]
                oversold = params["rsi_oversold"]
                stop_loss = params["stop_loss_pct"]
                take_profit = params["take_profit_pct"]

                try:
                    # Generate signals with full engine
                    long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(
                        candles=candles,
                        period=period,
                        overbought=overbought,
                        oversold=oversold,
                        direction=direction_str,
                    )

                    backtest_input = BacktestInput(
                        candles=candles,
                        candles_1m=None,
                        long_entries=long_entries,
                        long_exits=long_exits,
                        short_entries=short_entries,
                        short_exits=short_exits,
                        symbol=request_params["symbol"],
                        interval=request_params["interval"],
                        initial_capital=request_params["initial_capital"],
                        position_size=0.1 if request_params.get("use_fixed_amount") else 1.0,
                        use_fixed_amount=request_params.get("use_fixed_amount", False),
                        fixed_amount=request_params.get("fixed_amount", 0.0),
                        leverage=request_params["leverage"],
                        stop_loss=stop_loss / 100.0 if stop_loss else 0.0,
                        take_profit=take_profit / 100.0 if take_profit else 0.0,
                        direction=trade_direction,
                        taker_fee=request_params["commission"],
                        maker_fee=request_params["commission"],
                        slippage=0.0005,
                        use_bar_magnifier=False,
                        max_drawdown_limit=0.0,
                        pyramiding=1,
                        market_regime_enabled=request_params.get("market_regime_enabled", False),
                        market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
                        market_regime_lookback=request_params.get("market_regime_lookback", 50),
                    )

                    bt_output = engine.run(backtest_input)

                    if bt_output.is_valid and bt_output.metrics:
                        metrics = bt_output.metrics
                        result_entry = {
                            "total_return": metrics.total_return,
                            "sharpe_ratio": metrics.sharpe_ratio,
                            "max_drawdown": metrics.max_drawdown,
                            "win_rate": metrics.win_rate * 100,
                            "total_trades": metrics.total_trades,
                            "profit_factor": metrics.profit_factor,
                            "net_profit": metrics.net_profit,
                            "params": params,
                        }

                        score = _calculate_composite_score(
                            result_entry,
                            request_params.get("optimize_metric", "sharpe_ratio"),
                            request_params.get("weights"),
                        )
                        result_entry["score"] = score

                        results.append(result_entry)
                        completed += 1

                        if score > best_score:
                            best_score = score
                            best_params = result_entry["params"]
                            best_result = result_entry

                except Exception as verify_err:
                    logger.warning(f"Verification failed for {params}: {verify_err}")

            logger.info(f"✅ GPU Batch Hybrid completed: {total_combinations} screened, {completed} verified")

        except Exception as batch_err:
            logger.warning(f"GPU Batch failed: {batch_err}, falling back to single-process")
            # Fall through to single-process mode
            engine_type = "numba"  # Use Numba as fallback

    # Single-process mode for GPU/Numba/FallbackV4/Optimization OR small jobs
    # FallbackV4 required for market_regime (Numba doesn't support it)
    # "optimization" = Numba-based, works best in single-process (JIT warmup)
    if completed == 0 and (engine_type in ("gpu", "numba", "fallback_v4", "optimization") or total_combinations <= 10):
        logger.info(f"⚡ Using single-process mode for {engine_type} ({total_combinations} combinations)")

        from backend.backtesting.engine_selector import get_engine
        from backend.backtesting.interfaces import BacktestInput, TradeDirection
        from backend.backtesting.signal_generators import generate_rsi_signals

        # Get engine once (single warmup)
        engine = get_engine(engine_type=engine_type)
        logger.info(f"   Engine: {engine.__class__.__name__}")

        # Convert direction
        direction_str = request_params.get("direction", "both")
        if direction_str == "long":
            trade_direction = TradeDirection.LONG
        elif direction_str == "short":
            trade_direction = TradeDirection.SHORT
        else:
            trade_direction = TradeDirection.BOTH

        # Process all combinations in single process
        for combo in param_combinations:
            period, overbought, oversold, stop_loss, take_profit = combo
            try:
                # Generate RSI signals
                long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(
                    candles=candles,
                    period=period,
                    overbought=overbought,
                    oversold=oversold,
                    direction=direction_str,
                )

                # Create BacktestInput
                backtest_input = BacktestInput(
                    candles=candles,
                    candles_1m=None,
                    long_entries=long_entries,
                    long_exits=long_exits,
                    short_entries=short_entries,
                    short_exits=short_exits,
                    symbol=request_params["symbol"],
                    interval=request_params["interval"],
                    initial_capital=request_params["initial_capital"],
                    position_size=0.1 if request_params.get("use_fixed_amount") else 1.0,
                    use_fixed_amount=request_params.get("use_fixed_amount", False),
                    fixed_amount=request_params.get("fixed_amount", 0.0),
                    leverage=request_params["leverage"],
                    stop_loss=stop_loss / 100.0 if stop_loss else 0.0,
                    take_profit=take_profit / 100.0 if take_profit else 0.0,
                    direction=trade_direction,
                    taker_fee=request_params["commission"],
                    maker_fee=request_params["commission"],
                    slippage=0.0005,
                    use_bar_magnifier=False,
                    max_drawdown_limit=0.0,
                    pyramiding=1,
                    market_regime_enabled=request_params.get("market_regime_enabled", False),
                    market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
                    market_regime_lookback=request_params.get("market_regime_lookback", 50),
                )

                # Run backtest
                bt_output = engine.run(backtest_input)

                if not bt_output.is_valid:
                    continue

                metrics = bt_output.metrics
                result_entry = {
                    "total_return": metrics.total_return if metrics else 0,
                    "sharpe_ratio": metrics.sharpe_ratio if metrics else 0,
                    "max_drawdown": metrics.max_drawdown if metrics else 0,
                    "win_rate": metrics.win_rate * 100 if metrics else 0,
                    "total_trades": metrics.total_trades if metrics else 0,
                    "profit_factor": metrics.profit_factor if metrics else 0,
                    "winning_trades": metrics.winning_trades if metrics else 0,
                    "losing_trades": metrics.losing_trades if metrics else 0,
                    "net_profit": metrics.net_profit if metrics else 0,
                    "gross_profit": metrics.gross_profit if metrics else 0,
                    "gross_loss": metrics.gross_loss if metrics else 0,
                    "avg_win": metrics.avg_win if metrics else 0,
                    "avg_loss": metrics.avg_loss if metrics else 0,
                    "avg_win_value": metrics.avg_win if metrics else 0,  # Same as avg_win for TV parity
                    "avg_loss_value": metrics.avg_loss if metrics else 0,
                    "largest_win": metrics.largest_win if metrics else 0,
                    "largest_loss": metrics.largest_loss if metrics else 0,
                    "largest_win_value": metrics.largest_win if metrics else 0,
                    "largest_loss_value": metrics.largest_loss if metrics else 0,
                    "recovery_factor": metrics.recovery_factor if metrics else 0,
                    "expectancy": metrics.expectancy if metrics else 0,
                    "sortino_ratio": metrics.sortino_ratio if metrics else 0,
                    "calmar_ratio": metrics.calmar_ratio if metrics else 0,
                    # Long/Short breakdown
                    "long_trades": metrics.long_trades if metrics else 0,
                    "long_winning_trades": getattr(metrics, "long_winning_trades", 0) if metrics else 0,
                    "long_losing_trades": getattr(metrics, "long_losing_trades", 0) if metrics else 0,
                    "long_win_rate": metrics.long_win_rate * 100 if metrics else 0,
                    "long_gross_profit": getattr(metrics, "long_gross_profit", 0) if metrics else 0,
                    "long_gross_loss": getattr(metrics, "long_gross_loss", 0) if metrics else 0,
                    "long_net_profit": metrics.long_profit if metrics else 0,
                    "long_profit_factor": getattr(metrics, "long_profit_factor", 0) if metrics else 0,
                    "long_avg_win": getattr(metrics, "long_avg_win", 0) if metrics else 0,
                    "long_avg_loss": getattr(metrics, "long_avg_loss", 0) if metrics else 0,
                    "short_trades": metrics.short_trades if metrics else 0,
                    "short_winning_trades": getattr(metrics, "short_winning_trades", 0) if metrics else 0,
                    "short_losing_trades": getattr(metrics, "short_losing_trades", 0) if metrics else 0,
                    "short_win_rate": metrics.short_win_rate * 100 if metrics else 0,
                    "short_gross_profit": getattr(metrics, "short_gross_profit", 0) if metrics else 0,
                    "short_gross_loss": getattr(metrics, "short_gross_loss", 0) if metrics else 0,
                    "short_net_profit": metrics.short_profit if metrics else 0,
                    "short_profit_factor": getattr(metrics, "short_profit_factor", 0) if metrics else 0,
                    "short_avg_win": getattr(metrics, "short_avg_win", 0) if metrics else 0,
                    "short_avg_loss": getattr(metrics, "short_avg_loss", 0) if metrics else 0,
                    # Duration metrics
                    "avg_bars_in_trade": metrics.avg_trade_duration if metrics else 0,
                    "avg_bars_in_winning": metrics.avg_winning_duration if metrics else 0,
                    "avg_bars_in_losing": metrics.avg_losing_duration if metrics else 0,
                    # Commission
                    "total_commission": sum(t.fees for t in bt_output.trades) if bt_output.trades else 0,
                    "params": {
                        "rsi_period": period,
                        "rsi_overbought": overbought,
                        "rsi_oversold": oversold,
                        "stop_loss_pct": stop_loss,
                        "take_profit_pct": take_profit,
                    },
                    # Trade list for comparison with TV
                    "trades": [
                        {
                            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                            "direction": t.direction,
                            "entry_price": round(t.entry_price, 2),
                            "exit_price": round(t.exit_price, 2),
                            "pnl": round(t.pnl, 2),
                            "pnl_pct": round(t.pnl_pct, 4) if t.pnl_pct else 0,
                            "exit_reason": str(t.exit_reason.value) if t.exit_reason else "unknown",
                            "duration_bars": t.duration_bars,
                        }
                        for t in (bt_output.trades or [])
                    ],
                }

                # Calculate score
                score = _calculate_composite_score(
                    result_entry,
                    request_params.get("optimize_metric", "sharpe_ratio"),
                    request_params.get("weights"),
                )
                result_entry["score"] = score

                results.append(result_entry)
                completed += 1

                if score > best_score:
                    best_score = score
                    best_params = result_entry["params"]
                    best_result = result_entry

            except Exception as e:
                logger.warning(f"Combo failed: {combo} - {e}")

        logger.info(f"   Completed: {completed}/{total_combinations}")

    # Multiprocessing mode for Fallback (CPU parallelism)
    if completed == 0:
        max_workers = min(os.cpu_count() or 4, 8)
        logger.info(f"📝 Using multiprocessing with {max_workers} processes for {engine_type}")

        # Prepare serializable data
        candles_dict = candles.reset_index().to_dict("records")
        start_dt_str = start_dt.isoformat()
        end_dt_str = end_dt.isoformat()
        strategy_type_str = request.strategy_type.lower()

        # Split into batches
        batch_size = max(1, len(param_combinations) // max_workers)
        batches = [param_combinations[i : i + batch_size] for i in range(0, len(param_combinations), batch_size)]
        logger.info(f"📦 Split into {len(batches)} batches of ~{batch_size} combinations each")

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _run_batch_backtests,
                    batch,
                    request_params,
                    candles_dict,
                    start_dt_str,
                    end_dt_str,
                    strategy_type_str,
                ): batch
                for batch in batches
            }

            for future in as_completed(futures):
                try:
                    batch_results = future.result()
                    if batch_results:
                        for result_entry in batch_results:
                            if result_entry:
                                results.append(result_entry)
                                completed += 1

                                if result_entry["score"] > best_score:
                                    best_score = result_entry["score"]
                                    best_params = result_entry["params"]
                                    best_result = result_entry

                        logger.info(
                            f"   Progress: {completed}/{total_combinations} ({completed / total_combinations * 100:.1f}%)"
                        )

                except Exception as e:
                    logger.warning(f"Batch failed: {e}")

    # Применяем мультикритериальное ранжирование если есть selection_criteria
    selection_criteria = getattr(request, "selection_criteria", None) or [request.optimize_metric]
    if len(selection_criteria) > 1:
        # Используем мультикритериальное ранжирование
        results = _rank_by_multi_criteria(results, selection_criteria)
        logger.info(f"   Applied multi-criteria ranking: {selection_criteria}")
    else:
        # Стандартная сортировка по одному критерию
        results.sort(key=lambda x: x["score"], reverse=True)

    # Apply custom sort_order from frontend if provided
    custom_sort_order = getattr(request, "sort_order", None)
    if custom_sort_order and len(custom_sort_order) > 0:
        results = _apply_custom_sort_order(results, custom_sort_order)
        logger.info(f"   Applied custom sort order: {custom_sort_order}")

    # Calculate composite_score for each result if use_composite=True
    use_composite = getattr(request, "use_composite", False)
    composite_weights = getattr(request, "weights", None)
    if use_composite and composite_weights and results:
        for result in results:
            composite_score = _compute_weighted_composite(result, composite_weights)
            result["composite_score"] = composite_score
        logger.info(f"   Calculated composite scores with weights: {composite_weights}")

    # Обновляем лучший результат после ранжирования
    if results:
        best_result = results[0]
        best_score = best_result["score"]
        best_params = best_result["params"]

    execution_time = time.time() - start_time

    # Hybrid pipeline: optional FallbackV4 validation for gold-standard metrics
    validated_metrics = None
    if getattr(request, "validate_best_with_fallback", False) and best_params and engine_type in ("numba", "gpu"):
        try:
            from backend.backtesting.engine_selector import get_engine
            from backend.backtesting.interfaces import BacktestInput, TradeDirection
            from backend.backtesting.signal_generators import generate_rsi_signals

            fallback_engine = get_engine(engine_type="fallback_v4")
            direction_str = request_params.get("direction", "both")
            trade_direction = (
                TradeDirection.LONG
                if direction_str == "long"
                else (TradeDirection.SHORT if direction_str == "short" else TradeDirection.BOTH)
            )
            long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(
                candles=candles,
                period=best_params["rsi_period"],
                overbought=best_params["rsi_overbought"],
                oversold=best_params["rsi_oversold"],
                direction=direction_str,
            )
            bt_input = BacktestInput(
                candles=candles,
                candles_1m=None,
                long_entries=long_entries,
                long_exits=long_exits,
                short_entries=short_entries,
                short_exits=short_exits,
                symbol=request_params["symbol"],
                interval=request_params["interval"],
                initial_capital=request_params["initial_capital"],
                position_size=0.1 if request_params.get("use_fixed_amount") else 1.0,
                use_fixed_amount=request_params.get("use_fixed_amount", False),
                fixed_amount=request_params.get("fixed_amount", 0.0),
                leverage=request_params["leverage"],
                stop_loss=best_params.get("stop_loss_pct", 0) / 100.0,
                take_profit=best_params.get("take_profit_pct", 0) / 100.0,
                direction=trade_direction,
                taker_fee=request_params["commission"],
                maker_fee=request_params["commission"],
                slippage=0.0005,
                use_bar_magnifier=False,
                max_drawdown_limit=0.0,
                pyramiding=1,
                market_regime_enabled=request_params.get("market_regime_enabled", False),
                market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
                market_regime_lookback=request_params.get("market_regime_lookback", 50),
            )
            bt_out = fallback_engine.run(bt_input)
            if bt_out.is_valid and bt_out.metrics:
                validated_metrics = {
                    "sharpe_ratio": bt_out.metrics.sharpe_ratio,
                    "total_return": bt_out.metrics.total_return,
                    "max_drawdown": bt_out.metrics.max_drawdown,
                    "win_rate": bt_out.metrics.win_rate * 100,
                    "total_trades": bt_out.metrics.total_trades,
                    "net_profit": bt_out.metrics.net_profit,
                    "profit_factor": bt_out.metrics.profit_factor,
                }
                logger.info(f"   ✅ FallbackV4 validation: Sharpe={validated_metrics['sharpe_ratio']:.4f}")
        except Exception as val_err:
            logger.warning(f"FallbackV4 validation failed: {val_err}")

    logger.info(f"✅ Optimization completed in {execution_time:.2f}s")
    logger.info(f"   Selection criteria: {selection_criteria}")
    logger.info(f"   Best params: {best_params}")

    # Генерируем умные рекомендации
    smart_recs = _generate_smart_recommendations(results)

    # Преобразуем в модель
    def _to_recommendation(r: dict) -> SmartRecommendation | None:
        if not r:
            return None
        return SmartRecommendation(
            params=r.get("params"),
            total_return=r.get("total_return"),
            max_drawdown=r.get("max_drawdown"),
            sharpe_ratio=r.get("sharpe_ratio"),
            win_rate=r.get("win_rate"),
            total_trades=r.get("total_trades"),
        )

    smart_recommendations = SmartRecommendations(
        best_balanced=_to_recommendation(smart_recs.get("best_balanced")),
        best_conservative=_to_recommendation(smart_recs.get("best_conservative")),
        best_aggressive=_to_recommendation(smart_recs.get("best_aggressive")),
        recommendation_text=smart_recs.get("recommendation_text", ""),
    )

    # Calculate speed
    speed = int(len(results) / execution_time) if execution_time > 0 else 0

    return SyncOptimizationResponse(
        status="completed",
        total_combinations=total_combinations,
        tested_combinations=len(results),
        best_params=best_params or {},
        best_score=best_score if best_score != float("-inf") else 0,
        best_metrics={
            "total_return": best_result.get("total_return", 0) if best_result else 0,
            "sharpe_ratio": best_result.get("sharpe_ratio", 0) if best_result else 0,
            "max_drawdown": best_result.get("max_drawdown", 0) if best_result else 0,
            "max_drawdown_value": best_result.get("max_drawdown_value", 0) if best_result else 0,
            "win_rate": best_result.get("win_rate", 0) if best_result else 0,
            "total_trades": best_result.get("total_trades", 0) if best_result else 0,
            "winning_trades": best_result.get("winning_trades", 0) if best_result else 0,
            "losing_trades": best_result.get("losing_trades", 0) if best_result else 0,
            "profit_factor": best_result.get("profit_factor", 0) if best_result else 0,
            "net_profit": best_result.get("net_profit", 0) if best_result else 0,
            "gross_profit": best_result.get("gross_profit", 0) if best_result else 0,
            "gross_loss": best_result.get("gross_loss", 0) if best_result else 0,
            "avg_win": best_result.get("avg_win", 0) if best_result else 0,
            "avg_loss": best_result.get("avg_loss", 0) if best_result else 0,
            "avg_win_value": best_result.get("avg_win_value", best_result.get("avg_win", 0)) if best_result else 0,
            "avg_loss_value": best_result.get("avg_loss_value", best_result.get("avg_loss", 0)) if best_result else 0,
            "largest_win": best_result.get("largest_win", 0) if best_result else 0,
            "largest_loss": best_result.get("largest_loss", 0) if best_result else 0,
            "largest_win_value": best_result.get("largest_win", 0) if best_result else 0,
            "largest_loss_value": best_result.get("largest_loss", 0) if best_result else 0,
            "recovery_factor": best_result.get("recovery_factor", 0) if best_result else 0,
            "expectancy": best_result.get("expectancy", 0) if best_result else 0,
            "sortino_ratio": best_result.get("sortino_ratio", 0) if best_result else 0,
            "calmar_ratio": best_result.get("calmar_ratio", 0) if best_result else 0,
            "max_consecutive_wins": best_result.get("max_consecutive_wins", 0) if best_result else 0,
            "max_consecutive_losses": best_result.get("max_consecutive_losses", 0) if best_result else 0,
            "best_trade": best_result.get("best_trade", 0) if best_result else 0,
            "worst_trade": best_result.get("worst_trade", 0) if best_result else 0,
            "best_trade_pct": best_result.get("best_trade_pct", 0) if best_result else 0,
            "worst_trade_pct": best_result.get("worst_trade_pct", 0) if best_result else 0,
            # Long/Short statistics
            "long_trades": best_result.get("long_trades", 0) if best_result else 0,
            "long_winning_trades": best_result.get("long_winning_trades", 0) if best_result else 0,
            "long_losing_trades": best_result.get("long_losing_trades", 0) if best_result else 0,
            "long_win_rate": best_result.get("long_win_rate", 0) if best_result else 0,
            "long_gross_profit": best_result.get("long_gross_profit", 0) if best_result else 0,
            "long_gross_loss": best_result.get("long_gross_loss", 0) if best_result else 0,
            "long_net_profit": best_result.get("long_net_profit", 0) if best_result else 0,
            "long_profit_factor": best_result.get("long_profit_factor", 0) if best_result else 0,
            "long_avg_win": best_result.get("long_avg_win", 0) if best_result else 0,
            "long_avg_loss": best_result.get("long_avg_loss", 0) if best_result else 0,
            "short_trades": best_result.get("short_trades", 0) if best_result else 0,
            "short_winning_trades": best_result.get("short_winning_trades", 0) if best_result else 0,
            "short_losing_trades": best_result.get("short_losing_trades", 0) if best_result else 0,
            "short_win_rate": best_result.get("short_win_rate", 0) if best_result else 0,
            "short_gross_profit": best_result.get("short_gross_profit", 0) if best_result else 0,
            "short_gross_loss": best_result.get("short_gross_loss", 0) if best_result else 0,
            "short_net_profit": best_result.get("short_net_profit", 0) if best_result else 0,
            "short_profit_factor": best_result.get("short_profit_factor", 0) if best_result else 0,
            "short_avg_win": best_result.get("short_avg_win", 0) if best_result else 0,
            "short_avg_loss": best_result.get("short_avg_loss", 0) if best_result else 0,
            # Average bars in trade
            "avg_bars_in_trade": best_result.get("avg_bars_in_trade", 0) if best_result else 0,
            "avg_bars_in_winning": best_result.get("avg_bars_in_winning", 0) if best_result else 0,
            "avg_bars_in_losing": best_result.get("avg_bars_in_losing", 0) if best_result else 0,
            "avg_bars_in_long": best_result.get("avg_bars_in_long", 0) if best_result else 0,
            "avg_bars_in_short": best_result.get("avg_bars_in_short", 0) if best_result else 0,
            "avg_bars_in_winning_long": best_result.get("avg_bars_in_winning_long", 0) if best_result else 0,
            "avg_bars_in_losing_long": best_result.get("avg_bars_in_losing_long", 0) if best_result else 0,
            "avg_bars_in_winning_short": best_result.get("avg_bars_in_winning_short", 0) if best_result else 0,
            "avg_bars_in_losing_short": best_result.get("avg_bars_in_losing_short", 0) if best_result else 0,
            # Recovery factor Long/Short
            "recovery_long": best_result.get("recovery_long", 0) if best_result else 0,
            "recovery_short": best_result.get("recovery_short", 0) if best_result else 0,
            # Commission, Buy&Hold, CAGR
            "total_commission": best_result.get("total_commission", 0) if best_result else 0,
            "buy_hold_return": best_result.get("buy_hold_return", 0) if best_result else 0,
            "buy_hold_return_pct": best_result.get("buy_hold_return_pct", 0) if best_result else 0,
            "strategy_outperformance": best_result.get("strategy_outperformance", 0) if best_result else 0,
            "cagr": best_result.get("cagr", 0) if best_result else 0,
            "cagr_long": best_result.get("cagr_long", 0) if best_result else 0,
            "cagr_short": best_result.get("cagr_short", 0) if best_result else 0,
        },
        top_results=results[:10],
        execution_time_seconds=round(execution_time, 2),
        speed_combinations_per_sec=speed,
        num_workers=os.cpu_count() or 4,
        smart_recommendations=smart_recommendations,
        validated_metrics=validated_metrics,
    )


# =============================================================================
# OPTUNA BAYESIAN OPTIMIZATION (TPE/GP, fewer iterations, same quality)
# =============================================================================


class OptunaSyncRequest(SyncOptimizationRequest):
    """Optuna Bayesian optimization — extends grid-search request."""

    n_trials: int = Field(100, ge=10, le=500, description="Number of Optuna trials")
    sampler_type: str = Field(
        "tpe",
        description="Optuna sampler: tpe (default), random, cmaes",
    )
    n_jobs: int = Field(1, ge=1, le=8, description="Parallel trials (n_jobs)")
    validate_best_with_fallback: bool = False


@router.post("/sync/optuna-search", response_model=SyncOptimizationResponse)
async def sync_optuna_optimization(
    request: OptunaSyncRequest,
    db: Session = Depends(get_db),
):
    """
    Bayesian оптимизация (Optuna TPE).

    Меньше итераций при том же качестве, многокритериальность, ограничения.
    """
    import time
    from datetime import datetime as dt

    import pandas as pd

    from backend.optimization.optuna_optimizer import OPTUNA_AVAILABLE, OptunaOptimizer
    from backend.services.data_service import DataService

    if not OPTUNA_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Optuna not installed. pip install optuna",
        )

    start_time = time.time()
    logger.info("🔬 Starting Optuna Bayesian optimization")
    logger.info(f"   n_trials={request.n_trials}, sampler={request.sampler_type}")

    db_interval = _normalize_interval(request.interval)
    try:
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {e}")

    market_type = getattr(request, "market_type", "linear")
    data_service = DataService(db)
    candle_records = data_service.get_market_data(
        symbol=request.symbol,
        timeframe=db_interval,
        start_time=start_dt,
        end_time=end_dt,
        market_type=market_type,
    )
    if not candle_records:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} {request.interval}",
        )

    candles = pd.DataFrame(
        [
            {
                "timestamp": pd.to_datetime(c.open_time, unit="ms", utc=True),
                "open": float(c.open_price or 0),
                "high": float(c.high_price or 0),
                "low": float(c.low_price or 0),
                "close": float(c.close_price or 0),
                "volume": float(c.volume or 0),
            }
            for c in candle_records
        ]
    )
    candles.set_index("timestamp", inplace=True)

    # Param space from ranges (min/max for Optuna)
    def _low_high(arr, default_lo, default_hi):
        if not arr:
            return default_lo, default_hi
        return min(arr), max(arr)

    param_space = {
        "rsi_period": {
            "type": "int",
            "low": _low_high(request.rsi_period_range, 7, 30)[0],
            "high": _low_high(request.rsi_period_range, 7, 30)[1],
        },
        "rsi_overbought": {
            "type": "int",
            "low": _low_high(request.rsi_overbought_range, 65, 85)[0],
            "high": _low_high(request.rsi_overbought_range, 65, 85)[1],
        },
        "rsi_oversold": {
            "type": "int",
            "low": _low_high(request.rsi_oversold_range, 15, 35)[0],
            "high": _low_high(request.rsi_oversold_range, 15, 35)[1],
        },
        "stop_loss_pct": {
            "type": "float",
            "low": _low_high(request.stop_loss_range, 1.0, 10.0)[0],
            "high": _low_high(request.stop_loss_range, 1.0, 10.0)[1],
            "step": 0.5,
        },
        "take_profit_pct": {
            "type": "float",
            "low": _low_high(request.take_profit_range, 1.0, 20.0)[0],
            "high": _low_high(request.take_profit_range, 1.0, 20.0)[1],
            "step": 0.5,
        },
    }

    from backend.backtesting.engine_selector import get_engine
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.signal_generators import generate_rsi_signals

    # Market regime requires FallbackV4 (Numba doesn't support it)
    optuna_engine = "fallback_v4" if getattr(request, "market_regime_enabled", False) else "numba"
    engine = get_engine(engine_type=optuna_engine)
    request_params = {
        "symbol": request.symbol,
        "interval": request.interval,
        "initial_capital": request.initial_capital,
        "leverage": request.leverage,
        "commission": request.commission,
        "use_fixed_amount": request.use_fixed_amount,
        "fixed_amount": request.fixed_amount,
        "optimize_metric": request.optimize_metric,
        "direction": request.direction,
        "market_regime_enabled": getattr(request, "market_regime_enabled", False),
        "market_regime_filter": getattr(request, "market_regime_filter", "not_volatile"),
        "market_regime_lookback": getattr(request, "market_regime_lookback", 50),
    }
    direction_str = request.direction
    trade_direction = (
        TradeDirection.LONG
        if direction_str == "long"
        else (TradeDirection.SHORT if direction_str == "short" else TradeDirection.BOTH)
    )

    def objective(params):
        try:
            le, lex, se, sex = generate_rsi_signals(
                candles=candles,
                period=int(params["rsi_period"]),
                overbought=int(params["rsi_overbought"]),
                oversold=int(params["rsi_oversold"]),
                direction=direction_str,
            )
            sl = params.get("stop_loss_pct", 0) / 100.0
            tp = params.get("take_profit_pct", 0) / 100.0
            pos_size = 0.1 if request_params.get("use_fixed_amount") else 1.0
            bt_input = BacktestInput(
                candles=candles,
                candles_1m=None,
                long_entries=le,
                long_exits=lex,
                short_entries=se,
                short_exits=sex,
                symbol=request_params["symbol"],
                interval=request_params["interval"],
                initial_capital=request_params["initial_capital"],
                position_size=pos_size,
                use_fixed_amount=request_params.get("use_fixed_amount", False),
                fixed_amount=request_params.get("fixed_amount", 0.0),
                leverage=request_params["leverage"],
                stop_loss=sl if sl else 0.0,
                take_profit=tp if tp else 0.0,
                direction=trade_direction,
                taker_fee=request_params["commission"],
                maker_fee=request_params["commission"],
                slippage=0.0005,
                use_bar_magnifier=False,
                max_drawdown_limit=0.0,
                pyramiding=1,
                market_regime_enabled=request_params.get("market_regime_enabled", False),
                market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
                market_regime_lookback=request_params.get("market_regime_lookback", 50),
            )
            out = engine.run(bt_input)
            if not out.is_valid or not out.metrics:
                return float("-inf")
            return _calculate_composite_score(
                {
                    "sharpe_ratio": out.metrics.sharpe_ratio,
                    "total_return": out.metrics.total_return,
                    "max_drawdown": out.metrics.max_drawdown,
                    "win_rate": out.metrics.win_rate,
                    "total_trades": out.metrics.total_trades,
                    "profit_factor": out.metrics.profit_factor,
                    "net_profit": out.metrics.net_profit,
                },
                request_params["optimize_metric"],
                None,
            )
        except Exception as e:
            logger.debug(f"Optuna trial failed: {e}")
            return float("-inf")

    optuna_opt = OptunaOptimizer(sampler_type=request.sampler_type)
    result = optuna_opt.optimize_strategy(
        objective_fn=objective,
        param_space=param_space,
        n_trials=request.n_trials,
        n_jobs=request.n_jobs,
        show_progress=True,
    )

    # Re-run best params for full metrics
    best_p = result.best_params
    le, lex, se, sex = generate_rsi_signals(
        candles=candles,
        period=int(best_p["rsi_period"]),
        overbought=int(best_p["rsi_overbought"]),
        oversold=int(best_p["rsi_oversold"]),
        direction=direction_str,
    )
    sl = best_p.get("stop_loss_pct", 0) / 100.0
    tp = best_p.get("take_profit_pct", 0) / 100.0
    pos_size = 0.1 if request_params.get("use_fixed_amount") else 1.0
    bt_input = BacktestInput(
        candles=candles,
        candles_1m=None,
        long_entries=le,
        long_exits=lex,
        short_entries=se,
        short_exits=sex,
        symbol=request_params["symbol"],
        interval=request_params["interval"],
        initial_capital=request_params["initial_capital"],
        position_size=pos_size,
        use_fixed_amount=request_params.get("use_fixed_amount", False),
        fixed_amount=request_params.get("fixed_amount", 0.0),
        leverage=request_params["leverage"],
        stop_loss=sl if sl else 0.0,
        take_profit=tp if tp else 0.0,
        direction=trade_direction,
        taker_fee=request_params["commission"],
        maker_fee=request_params["commission"],
        slippage=0.0005,
        use_bar_magnifier=False,
        max_drawdown_limit=0.0,
        pyramiding=1,
        market_regime_enabled=request_params.get("market_regime_enabled", False),
        market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
        market_regime_lookback=request_params.get("market_regime_lookback", 50),
    )
    out = engine.run(bt_input)
    metrics = out.metrics

    best_result = {
        "params": {
            "rsi_period": int(best_p["rsi_period"]),
            "rsi_overbought": int(best_p["rsi_overbought"]),
            "rsi_oversold": int(best_p["rsi_oversold"]),
            "stop_loss_pct": best_p.get("stop_loss_pct", 0),
            "take_profit_pct": best_p.get("take_profit_pct", 0),
        },
        "score": result.best_value,
        "total_return": metrics.total_return if metrics else 0,
        "sharpe_ratio": metrics.sharpe_ratio if metrics else 0,
        "max_drawdown": metrics.max_drawdown if metrics else 0,
        "win_rate": metrics.win_rate * 100 if metrics else 0,
        "total_trades": metrics.total_trades if metrics else 0,
        "profit_factor": metrics.profit_factor if metrics else 0,
        "net_profit": metrics.net_profit if metrics else 0,
    }

    execution_time = time.time() - start_time
    results = [{"params": best_result["params"], "score": best_result["score"], **best_result}]

    return SyncOptimizationResponse(
        status="completed",
        total_combinations=request.n_trials,
        tested_combinations=request.n_trials,
        best_params=best_result["params"],
        best_score=best_result["score"],
        best_metrics=best_result,
        top_results=results[:10],
        execution_time_seconds=round(execution_time, 2),
        speed_combinations_per_sec=int(request.n_trials / execution_time) if execution_time > 0 else 0,
        num_workers=request.n_jobs,
        smart_recommendations=None,
        validated_metrics=None,
    )


# =============================================================================
# VECTORBT HIGH-PERFORMANCE OPTIMIZATION (100K - 100M+ combinations)
# =============================================================================


class VectorbtOptimizationRequest(BaseModel):
    """Request for VectorBT high-performance optimization"""

    symbol: str = "BTCUSDT"
    interval: str = "30m"
    start_date: str = "2025-01-01"
    end_date: str = "2025-06-01"

    # Базовые параметры
    direction: str = "long"
    leverage: int = 10
    initial_capital: float = 10000.0
    commission: float = 0.0007  # 0.07% TradingView parity
    slippage: float = 0.0005  # Slippage per trade (0.0005 = 0.05%)
    position_size: float = 1.0  # 1.0 = 100% of capital per trade

    # RSI parameter ranges (lists of values)
    rsi_period_range: list[int] = [7, 14, 21]
    rsi_overbought_range: list[int] = [70, 75, 80]
    rsi_oversold_range: list[int] = [20, 25, 30]

    # TP/SL ranges
    stop_loss_range: list[float] = [5.0, 10.0, 15.0]
    take_profit_range: list[float] = [1.0, 2.0, 3.0]

    # Optimization settings
    optimize_metric: str = "sharpe_ratio"

    # Custom weights (for custom_score metric)
    weight_return: float = 0.4
    weight_drawdown: float = 0.3
    weight_sharpe: float = 0.2
    weight_win_rate: float = 0.1

    # Filters
    min_trades: int | None = None
    max_drawdown_limit: float | None = None
    min_profit_factor: float | None = None
    min_win_rate: float | None = None


class VectorbtOptimizationResponse(BaseModel):
    """Response from VectorBT optimization"""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    speed_combinations_per_sec: int | None = None  # Actual speed achieved
    num_workers: int | None = None  # Number of parallel workers used
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]
    smart_recommendations: SmartRecommendations | None = None


@router.post("/vectorbt/grid-search", response_model=VectorbtOptimizationResponse)
async def vectorbt_grid_search_optimization(
    request: VectorbtOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    🚀 Ultra-Fast Numba JIT Grid Search Optimization.

    Designed for massive parameter spaces (1,000 - 100,000+ combinations).

    Performance targets:
    - 1,000 combinations: < 1 second
    - 10,000 combinations: < 5 seconds
    - 100,000 combinations: < 30 seconds

    Uses:
    - Pure Numba JIT compilation (no VectorBT overhead)
    - Parallel processing with Numba prange
    - Pre-computed RSI caching
    - Vectorized PnL calculation
    """
    from datetime import datetime as dt

    import numpy as np
    import pandas as pd

    from backend.backtesting.fast_optimizer import (
        get_candle_cache,
        load_candles_fast,
    )

    # Use Universal optimizer with auto backend selection (GPU if available, CPU otherwise)
    from backend.backtesting.optimizer import (
        UniversalOptimizer,
        get_available_backends,
        get_recommended_backend,
    )

    backends = get_available_backends()
    recommended = get_recommended_backend()
    optimizer = UniversalOptimizer(backend="auto")
    logger.info(f"🚀 Using UniversalOptimizer (auto-backend: {recommended}, GPU: {backends.get('gpu', False)})")

    logger.info("🚀 Starting ultra-fast optimization")

    # DEBUG: Log received parameters
    logger.info(f"   RSI Period range: {request.rsi_period_range}")
    logger.info(f"   Overbought range: {request.rsi_overbought_range}")
    logger.info(f"   Oversold range: {request.rsi_oversold_range}")
    logger.info(f"   Stop Loss range: {request.stop_loss_range}")
    logger.info(f"   Take Profit range: {request.take_profit_range}")

    # Calculate total combinations
    total_combinations = (
        len(request.rsi_period_range)
        * len(request.rsi_overbought_range)
        * len(request.rsi_oversold_range)
        * len(request.stop_loss_range)
        * len(request.take_profit_range)
    )

    logger.info(f"   Total combinations: {total_combinations:,}")

    try:
        # Parse dates
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    # Normalize interval format: "30m" -> "30", "1h" -> "60", "4h" -> "240", "1d" -> "D"
    interval = _normalize_interval(request.interval)
    logger.info(f"📊 Normalized interval: {request.interval} -> {interval}")

    # Get DB path from environment with dynamic fallback
    from pathlib import Path

    default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
    db_path = os.environ.get("DATABASE_PATH", default_db)

    try:
        # Load market data via DIRECT SQL (bypass ORM for speed)
        import time as _time

        load_start = _time.perf_counter()

        candle_data = load_candles_fast(
            db_path=db_path,
            symbol=request.symbol,
            interval=interval,
            start_date=start_dt,
            end_date=end_dt,
            use_cache=True,
        )

        load_time = _time.perf_counter() - load_start
        cache_stats = get_candle_cache().stats()
        logger.info(f"📊 Data loaded in {load_time:.3f}s (cache size: {cache_stats['size']}/{cache_stats['max_size']})")

    except Exception as data_err:
        logger.error(f"Direct SQL load failed: {data_err}, falling back to ORM")
        # Fallback to ORM if direct SQL fails
        from backend.services.data_service import DataService

        data_service = DataService(db)
        candle_records = data_service.get_market_data(
            symbol=request.symbol,
            timeframe=interval,
            start_time=start_dt,
            end_time=end_dt,
        )
        if candle_records:
            candle_data = np.array(
                [
                    [
                        c.open_time,
                        c.open_price,
                        c.high_price,
                        c.low_price,
                        c.close_price,
                        c.volume,
                    ]
                    for c in candle_records
                ],
                dtype=np.float64,
            )
        else:
            candle_data = None

    if candle_data is None or len(candle_data) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol} interval={interval} (original: {request.interval}). Check that data is loaded.",
        )

    # Convert numpy array to DataFrame
    # candle_data columns: [open_time, open, high, low, close, volume]
    candles = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(candle_data[:, 0], unit="ms", utc=True),
            "open": candle_data[:, 1],
            "high": candle_data[:, 2],
            "low": candle_data[:, 3],
            "close": candle_data[:, 4],
            "volume": candle_data[:, 5],
        }
    )
    candles.set_index("timestamp", inplace=True)

    logger.info(f"📊 Loaded {len(candles)} candles")

    # Prepare filters
    filters = {}
    if request.min_trades:
        filters["min_trades"] = request.min_trades
    if request.max_drawdown_limit:
        filters["max_drawdown_limit"] = request.max_drawdown_limit
    if request.min_profit_factor:
        filters["min_profit_factor"] = request.min_profit_factor
    if request.min_win_rate:
        filters["min_win_rate"] = request.min_win_rate

    # Prepare weights
    weights = {
        "return": request.weight_return,
        "drawdown": request.weight_drawdown,
        "sharpe": request.weight_sharpe,
        "win_rate": request.weight_win_rate,
    }

    try:
        # Run optimization (GPU optimizer already created above)
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=request.rsi_period_range,
            rsi_overbought_range=request.rsi_overbought_range,
            rsi_oversold_range=request.rsi_oversold_range,
            stop_loss_range=request.stop_loss_range,
            take_profit_range=request.take_profit_range,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            commission=request.commission,
            slippage=request.slippage,
            optimize_metric=request.optimize_metric,
            direction=request.direction,
            # position_size removed - not supported by VectorBT optimizer
            weights=weights,
            filters=filters if filters else None,
        )
    except Exception as e:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e!s}")

    # Enrich best result with full metrics using BacktestEngine
    if result.top_results:
        try:
            from backend.backtesting.engine import BacktestEngine
            from backend.backtesting.models import BacktestConfig, StrategyType

            best = result.top_results[0]
            best_params = best.get("params", {})

            logger.info(f"🔄 Enriching best result with full metrics: {best_params}")

            # Build proper BacktestConfig
            backtest_config = BacktestConfig(
                symbol=request.symbol,
                interval=request.interval,
                start_date=dt.fromisoformat(request.start_date),
                end_date=dt.fromisoformat(request.end_date),
                strategy_type=StrategyType.RSI,
                strategy_params={
                    "period": best_params.get("rsi_period", 14),
                    "overbought": best_params.get("rsi_overbought", 70),
                    "oversold": best_params.get("rsi_oversold", 30),
                },
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                # GPU optimizer treats 'both' as 'long' (direction >= 0), so match that here
                direction="long" if request.direction in ("long", "both") else "short",
                stop_loss=best_params.get("stop_loss_pct", 0) / 100 if best_params.get("stop_loss_pct") else None,
                take_profit=best_params.get("take_profit_pct", 0) / 100 if best_params.get("take_profit_pct") else None,
                taker_fee=request.commission,
                maker_fee=request.commission,
                slippage=request.slippage,
                position_size=1.0,  # Match GPU optimizer's 100% allocation
            )

            # Run full backtest
            engine = BacktestEngine()
            full_result = engine.run(backtest_config, candles, silent=True)

            if full_result and full_result.metrics:
                metrics = full_result.metrics
                # Enrich best result with full metrics from PerformanceMetrics
                # Core trade statistics (for header cards)
                best["total_trades"] = getattr(metrics, "total_trades", 0)
                best["winning_trades"] = getattr(metrics, "winning_trades", 0)
                best["losing_trades"] = getattr(metrics, "losing_trades", 0)
                best["win_rate"] = getattr(metrics, "win_rate", 0)
                # Long/Short breakdown
                best["long_trades"] = getattr(metrics, "long_trades", 0)
                best["short_trades"] = getattr(metrics, "short_trades", 0)
                best["long_winning_trades"] = getattr(metrics, "long_winning_trades", 0)
                best["short_winning_trades"] = getattr(metrics, "short_winning_trades", 0)
                best["long_win_rate"] = getattr(metrics, "long_win_rate", 0)
                best["short_win_rate"] = getattr(metrics, "short_win_rate", 0)
                best["long_gross_profit"] = getattr(metrics, "long_gross_profit", 0)
                best["long_gross_loss"] = getattr(metrics, "long_gross_loss", 0)
                best["short_gross_profit"] = getattr(metrics, "short_gross_profit", 0)
                best["short_gross_loss"] = getattr(metrics, "short_gross_loss", 0)
                best["long_net_profit"] = getattr(metrics, "long_net_profit", 0)
                best["short_net_profit"] = getattr(metrics, "short_net_profit", 0)
                best["long_profit_factor"] = getattr(metrics, "long_profit_factor", 0)
                best["short_profit_factor"] = getattr(metrics, "short_profit_factor", 0)
                best["gross_profit"] = getattr(metrics, "gross_profit", 0)
                best["gross_loss"] = getattr(metrics, "gross_loss", 0)
                best["net_profit"] = getattr(metrics, "net_profit", 0)
                best["avg_win"] = getattr(metrics, "avg_win", 0)
                best["avg_loss"] = getattr(metrics, "avg_loss", 0)
                best["avg_trade"] = getattr(metrics, "avg_trade", 0)
                best["avg_win_value"] = getattr(metrics, "avg_win_value", 0)
                best["avg_loss_value"] = getattr(metrics, "avg_loss_value", 0)
                best["avg_trade_value"] = getattr(metrics, "avg_trade_value", 0)
                best["largest_win"] = getattr(metrics, "largest_win", 0)
                best["largest_loss"] = getattr(metrics, "largest_loss", 0)
                best["largest_win_value"] = getattr(metrics, "largest_win_value", 0)
                best["largest_loss_value"] = getattr(metrics, "largest_loss_value", 0)
                best["sharpe_ratio"] = getattr(metrics, "sharpe_ratio", 0)
                best["sortino_ratio"] = getattr(metrics, "sortino_ratio", 0)
                best["calmar_ratio"] = getattr(metrics, "calmar_ratio", 0)
                # Only overwrite max_drawdown if full backtest calculated a valid value
                # GPU optimizer already has correct max_drawdown from simulation
                full_bt_max_dd = getattr(metrics, "max_drawdown", 0)
                if full_bt_max_dd > 0:
                    best["max_drawdown"] = full_bt_max_dd
                    best["max_drawdown_value"] = getattr(metrics, "max_drawdown_value", 0)
                # else: keep GPU optimizer's max_drawdown from top_results[0]
                best["recovery_factor"] = getattr(metrics, "recovery_factor", 0)
                best["expectancy"] = getattr(metrics, "expectancy", 0)
                best["cagr"] = getattr(metrics, "cagr", 0)
                best["total_commission"] = getattr(metrics, "total_commission", 0)

                best["avg_bars_in_trade"] = getattr(metrics, "avg_bars_in_trade", 0)
                best["avg_bars_in_winning"] = getattr(metrics, "avg_bars_in_winning", 0)
                best["avg_bars_in_losing"] = getattr(metrics, "avg_bars_in_losing", 0)

                # Convert trades to dict list
                best["trades"] = [t.model_dump() for t in full_result.trades] if full_result.trades else []

                # Convert equity curve (EquityCurve has timestamps and equity lists)
                if full_result.equity_curve and hasattr(full_result.equity_curve, "timestamps"):
                    ec = full_result.equity_curve
                    drawdowns = ec.drawdown if hasattr(ec, "drawdown") and ec.drawdown else [0] * len(ec.equity)
                    best["equity_curve"] = [
                        {
                            "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                            "equity": v,
                            "drawdown": d,
                        }
                        for t, v, d in zip(
                            ec.timestamps,
                            ec.equity,
                            drawdowns,
                        )
                    ]
                else:
                    best["equity_curve"] = []

                logger.info(
                    f"✅ Enriched best result with full metrics: Long={best['long_trades']}, Short={best['short_trades']}"
                )

                # Also update best_metrics in result
                result.best_metrics.update(
                    {
                        # Core trade stats
                        "total_trades": best.get("total_trades", len(best.get("trades", []))),
                        "winning_trades": best.get("winning_trades", 0),
                        "losing_trades": best.get("losing_trades", 0),
                        "win_rate": best.get("win_rate", 0),
                        # Long/Short stats
                        "long_trades": best["long_trades"],
                        "short_trades": best["short_trades"],
                        "long_win_rate": best["long_win_rate"],
                        "short_win_rate": best["short_win_rate"],
                        "gross_profit": best["gross_profit"],
                        "gross_loss": best["gross_loss"],
                        "net_profit": best["net_profit"],
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to enrich best result with full metrics: {e}")

    # Generate smart recommendations
    smart_recs = _generate_smart_recommendations(result.top_results)

    # DEBUG: Log trade data
    if result.top_results:
        first = result.top_results[0]
        logger.info(f"DEBUG top_results[0] keys: {list(first.keys())}")
        logger.info(f"DEBUG trades: {len(first.get('trades', [])) if first.get('trades') else 'None'}")
        logger.info(f"DEBUG equity_curve: {first.get('equity_curve') is not None}")

    def _to_recommendation(r: dict) -> SmartRecommendation | None:
        if not r:
            return None
        return SmartRecommendation(
            params=r.get("params"),
            total_return=r.get("total_return"),
            max_drawdown=r.get("max_drawdown"),
            sharpe_ratio=r.get("sharpe_ratio"),
            win_rate=r.get("win_rate"),
            total_trades=r.get("total_trades"),
        )

    smart_recommendations = SmartRecommendations(
        best_balanced=_to_recommendation(smart_recs.get("best_balanced")),
        best_conservative=_to_recommendation(smart_recs.get("best_conservative")),
        best_aggressive=_to_recommendation(smart_recs.get("best_aggressive")),
        recommendation_text=smart_recs.get("recommendation_text", ""),
    )

    # Calculate speed
    speed = int(result.tested_combinations / result.execution_time_seconds) if result.execution_time_seconds > 0 else 0
    num_workers = getattr(result, "num_workers", None) or (os.cpu_count() or 4)

    return VectorbtOptimizationResponse(
        status=result.status,
        total_combinations=result.total_combinations,
        tested_combinations=result.tested_combinations,
        execution_time_seconds=result.execution_time_seconds,
        speed_combinations_per_sec=speed,
        num_workers=num_workers,
        best_params=result.best_params,
        best_score=result.best_score,
        best_metrics=result.best_metrics,
        top_results=result.top_results,
        performance_stats=result.performance_stats,
        smart_recommendations=smart_recommendations,
    )


# =============================================================================
# SSE STREAMING OPTIMIZATION (for large parameter spaces > 2 minutes)
# =============================================================================


@router.get("/vectorbt/grid-search-stream")
async def vectorbt_grid_search_stream(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("30m"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    direction: str = Query("long"),
    leverage: int = Query(10),
    initial_capital: float = Query(10000.0),
    commission: float = Query(0.0007, description="0.07% TradingView parity"),
    position_size: float = Query(1.0),
    rsi_period_range: str = Query("7,14,21"),
    rsi_overbought_range: str = Query("70,75,80"),
    rsi_oversold_range: str = Query("20,25,30"),
    stop_loss_range: str = Query("5.0,10.0,15.0"),
    take_profit_range: str = Query("1.0,2.0,3.0"),
    optimize_metric: str = Query("sharpe_ratio"),
    weight_return: float = Query(0.4),
    weight_drawdown: float = Query(0.3),
    weight_sharpe: float = Query(0.2),
    weight_win_rate: float = Query(0.1),
    min_trades: int | None = Query(None),
    max_drawdown_limit: float | None = Query(None),
    min_profit_factor: float | None = Query(None),
    min_win_rate: float | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    🚀 SSE Streaming Grid Search Optimization.

    Uses Server-Sent Events to send progress updates and keep connection alive.
    Ideal for large parameter spaces (>1M combinations) that take >2 minutes.

    Events:
    - progress: {percent, tested, total, speed, eta_seconds}
    - heartbeat: {timestamp} (every 10 sec to keep connection alive)
    - complete: {result JSON}
    - error: {message}
    """
    import asyncio
    import json
    import time
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.responses import StreamingResponse

    # Parse comma-separated ranges
    def parse_int_list(s: str) -> list[int]:
        return [int(x.strip()) for x in s.split(",") if x.strip()]

    def parse_float_list(s: str) -> list[float]:
        return [float(x.strip()) for x in s.split(",") if x.strip()]

    period_range = parse_int_list(rsi_period_range)
    overbought_range = parse_int_list(rsi_overbought_range)
    oversold_range = parse_int_list(rsi_oversold_range)
    sl_range = parse_float_list(stop_loss_range)
    tp_range = parse_float_list(take_profit_range)

    total_combinations = len(period_range) * len(overbought_range) * len(oversold_range) * len(sl_range) * len(tp_range)

    logger.info(f"🚀 SSE Grid Search: {total_combinations:,} combinations")

    # Build request object
    request = VectorbtOptimizationRequest(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        leverage=leverage,
        initial_capital=initial_capital,
        commission=commission,
        position_size=position_size,
        rsi_period_range=period_range,
        rsi_overbought_range=overbought_range,
        rsi_oversold_range=oversold_range,
        stop_loss_range=sl_range,
        take_profit_range=tp_range,
        optimize_metric=optimize_metric,
        weight_return=weight_return,
        weight_drawdown=weight_drawdown,
        weight_sharpe=weight_sharpe,
        weight_win_rate=weight_win_rate,
        min_trades=min_trades,
        max_drawdown_limit=max_drawdown_limit,
        min_profit_factor=min_profit_factor,
        min_win_rate=min_win_rate,
    )

    # Result container for thread
    result_container = {"result": None, "error": None, "done": False}

    def run_optimization():
        """Run optimization in thread"""
        try:
            import os
            from datetime import datetime as dt

            from backend.backtesting.fast_optimizer import load_candles_fast

            # Use Universal optimizer with auto backend selection
            from backend.backtesting.optimizer import UniversalOptimizer

            optimizer = UniversalOptimizer(backend="auto")

            # Get DB path with dynamic fallback
            from pathlib import Path

            default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
            db_path = os.environ.get("DATABASE_PATH", default_db)

            # Normalize interval
            interval_map = {
                "1m": "1",
                "3m": "3",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "1h": "60",
                "2h": "120",
                "4h": "240",
                "1d": "D",
                "1w": "W",
            }
            db_interval = interval_map.get(request.interval.lower(), request.interval)

            # Parse dates
            start_dt = dt.fromisoformat(request.start_date)
            end_dt = dt.fromisoformat(request.end_date)

            # Load candles
            candle_data = load_candles_fast(
                db_path=db_path,
                symbol=request.symbol,
                interval=db_interval,
                start_date=start_dt,
                end_date=end_dt,
                use_cache=True,
            )

            if candle_data is None or len(candle_data) < 50:
                result_container["error"] = (
                    f"Not enough data: {len(candle_data) if candle_data is not None else 0} candles"
                )
                result_container["done"] = True
                return

            # Convert numpy array to DataFrame
            import pandas as pd

            candles = pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(candle_data[:, 0], unit="ms", utc=True),
                    "open": candle_data[:, 1],
                    "high": candle_data[:, 2],
                    "low": candle_data[:, 3],
                    "close": candle_data[:, 4],
                    "volume": candle_data[:, 5],
                }
            )
            candles.set_index("timestamp", inplace=True)

            # Run optimization
            result = optimizer.optimize(
                candles=candles,
                rsi_period_range=request.rsi_period_range,
                rsi_overbought_range=request.rsi_overbought_range,
                rsi_oversold_range=request.rsi_oversold_range,
                stop_loss_range=request.stop_loss_range,
                take_profit_range=request.take_profit_range,
                initial_capital=request.initial_capital,
                leverage=request.leverage,
                commission=request.commission,
                optimize_metric=request.optimize_metric,
                direction=request.direction,
            )

            # Convert result to dict for JSON serialization
            speed_per_sec = (
                int(result.tested_combinations / result.execution_time_seconds)
                if result.execution_time_seconds > 0
                else 0
            )

            logger.info("[SSE] Optimization completed, preparing result dict...")

            # Get trades and equity from best result (first in top_results)
            best_result = result.top_results[0] if result.top_results else {}
            trades = best_result.get("trades", [])
            equity_curve = best_result.get("equity_curve", [])

            # ============================================
            # ENRICH with full backtest if trades are missing
            # GPU optimizer only returns metrics, not actual trades
            # ============================================
            if not trades and best_result:
                try:
                    from backend.backtesting.engine import BacktestEngine
                    from backend.backtesting.models import BacktestConfig, StrategyType

                    best_params = best_result.get("params", {})
                    logger.info(f"[SSE] Running full backtest for enrichment: {best_params}")

                    backtest_config = BacktestConfig(
                        symbol=request.symbol,
                        interval=request.interval,
                        start_date=dt.fromisoformat(request.start_date),
                        end_date=dt.fromisoformat(request.end_date),
                        strategy_type=StrategyType.RSI,
                        strategy_params={
                            "rsi_period": best_params.get("rsi_period", 14),
                            "rsi_overbought": best_params.get("rsi_overbought", 70),
                            "rsi_oversold": best_params.get("rsi_oversold", 30),
                        },
                        initial_capital=request.initial_capital,
                        leverage=request.leverage,
                        direction=request.direction,
                        stop_loss=best_params.get("stop_loss_pct", best_params.get("stop_loss", 0)) / 100
                        if best_params.get("stop_loss_pct", best_params.get("stop_loss"))
                        else None,
                        take_profit=best_params.get("take_profit_pct", best_params.get("take_profit", 0)) / 100
                        if best_params.get("take_profit_pct", best_params.get("take_profit"))
                        else None,
                        taker_fee=request.commission,
                        maker_fee=request.commission,
                        position_size=1.0,
                    )

                    engine = BacktestEngine()
                    full_result = engine.run(backtest_config, candles, silent=True)

                    if full_result and full_result.trades:
                        trades = [t.model_dump() for t in full_result.trades]
                        logger.info(f"[SSE] Got {len(trades)} trades from full backtest")

                        # Update best_result with full metrics
                        if full_result.metrics:
                            m = full_result.metrics
                            best_result["avg_win"] = getattr(m, "avg_win", 0)
                            best_result["avg_loss"] = getattr(m, "avg_loss", 0)
                            best_result["avg_trade"] = getattr(m, "avg_trade", 0)
                            best_result["avg_win_value"] = getattr(m, "avg_win_value", 0)
                            best_result["avg_loss_value"] = getattr(m, "avg_loss_value", 0)
                            best_result["largest_win"] = getattr(m, "largest_win", 0)
                            best_result["largest_loss"] = getattr(m, "largest_loss", 0)
                            best_result["largest_win_value"] = getattr(m, "largest_win_value", 0)
                            best_result["largest_loss_value"] = getattr(m, "largest_loss_value", 0)
                            best_result["gross_profit"] = getattr(m, "gross_profit", 0)
                            best_result["gross_loss"] = getattr(m, "gross_loss", 0)
                            best_result["net_profit"] = getattr(m, "net_profit", 0)
                            best_result["long_trades"] = getattr(m, "long_trades", 0)
                            best_result["short_trades"] = getattr(m, "short_trades", 0)
                            best_result["long_winning_trades"] = getattr(m, "long_winning_trades", 0)
                            best_result["short_winning_trades"] = getattr(m, "short_winning_trades", 0)
                            best_result["long_win_rate"] = getattr(m, "long_win_rate", 0)
                            best_result["short_win_rate"] = getattr(m, "short_win_rate", 0)
                            best_result["long_gross_profit"] = getattr(m, "long_gross_profit", 0)
                            best_result["long_gross_loss"] = getattr(m, "long_gross_loss", 0)
                            best_result["short_gross_profit"] = getattr(m, "short_gross_profit", 0)
                            best_result["short_gross_loss"] = getattr(m, "short_gross_loss", 0)
                            best_result["long_net_profit"] = getattr(m, "long_net_profit", 0)
                            best_result["short_net_profit"] = getattr(m, "short_net_profit", 0)
                            best_result["max_consecutive_wins"] = getattr(m, "max_consecutive_wins", 0)
                            best_result["max_consecutive_losses"] = getattr(m, "max_consecutive_losses", 0)
                            best_result["expectancy"] = getattr(m, "expectancy", 0)
                            best_result["total_commission"] = getattr(m, "total_commission", 0)
                            best_result["trades"] = trades
                            logger.info(f"[SSE] Enriched with full metrics: avg_win={best_result['avg_win']:.2f}%")

                    if full_result and full_result.equity_curve:
                        ec = full_result.equity_curve
                        if hasattr(ec, "timestamps") and hasattr(ec, "equity"):
                            drawdowns = ec.drawdown if hasattr(ec, "drawdown") and ec.drawdown else [0] * len(ec.equity)
                            equity_curve = [
                                {
                                    "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                                    "equity": v,
                                    "drawdown": d,
                                }
                                for t, v, d in zip(ec.timestamps, ec.equity, drawdowns)
                            ]
                            logger.info(f"[SSE] Got {len(equity_curve)} equity curve points")

                except Exception as enrich_err:
                    logger.warning(f"[SSE] Failed to enrich with full backtest: {enrich_err}")

            result_dict = {
                "best_params": result.best_params,
                "best_metrics": result.best_metrics,
                "top_results": result.top_results[:50] if result.top_results else [],
                "tested_combinations": result.tested_combinations,
                "execution_time": result.execution_time_seconds,
                "speed_per_sec": speed_per_sec,
                "trades": trades,
                "equity_curve": equity_curve,
            }

            logger.info(f"[SSE] Result dict ready, trades={len(trades)}, equity={len(equity_curve)}")

            result_container["result"] = result_dict
            result_container["done"] = True

            logger.info("[SSE] Container updated successfully")

        except Exception as e:
            logger.exception(f"SSE optimization error: {e}")
            result_container["error"] = str(e)
            result_container["done"] = True

    async def event_generator():
        """Generate SSE events"""
        # Start optimization in thread
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_optimization)  # Fire and forget - results via container

        start_time = time.time()
        last_heartbeat = time.time()
        heartbeat_interval = 3  # Send heartbeat every 3 seconds (was 10, too slow!)

        try:
            # Send initial event
            yield f"data: {json.dumps({'event': 'start', 'total': total_combinations})}\n\n"

            while not result_container["done"]:
                await asyncio.sleep(0.3)  # Check more frequently

                current_time = time.time()
                elapsed = current_time - start_time

                # Send heartbeat to keep connection alive (every 3 sec)
                if current_time - last_heartbeat >= heartbeat_interval:
                    # Estimate progress based on expected speed (~25k combos/sec)
                    estimated_speed = 25000
                    estimated_done = min(int(elapsed * estimated_speed), total_combinations)
                    percent = min(99, int(estimated_done * 100 / total_combinations)) if total_combinations > 0 else 0
                    eta = max(0, (total_combinations - estimated_done) / estimated_speed) if estimated_speed > 0 else 0

                    yield f"data: {json.dumps({'event': 'heartbeat', 'elapsed': round(elapsed, 1), 'percent': percent, 'eta_seconds': round(eta, 0)})}\n\n"
                    last_heartbeat = current_time

            # Check for error
            if result_container["error"]:
                logger.error(f"[SSE] Optimization error: {result_container['error']}")
                yield f"data: {json.dumps({'event': 'error', 'message': result_container['error']})}\n\n"
                return

            # Send result
            logger.info("[SSE] Preparing to send result to client...")
            result = result_container["result"]
            if result:
                # Build response - result is a dict, access via []
                top_results = result.get("top_results", [])
                smart_recs = _generate_smart_recommendations(top_results)

                def _to_rec(r):
                    if not r:
                        return None
                    return {
                        "params": r.get("params"),
                        "total_return": r.get("total_return"),
                        "max_drawdown": r.get("max_drawdown"),
                        "sharpe_ratio": r.get("sharpe_ratio"),
                        "win_rate": r.get("win_rate"),
                        "total_trades": r.get("total_trades"),
                    }

                tested = result.get("tested_combinations", 0)
                exec_time = result.get("execution_time", 0)
                speed = int(tested / exec_time) if exec_time > 0 else 0

                response_data = {
                    "event": "complete",
                    "status": "completed",
                    "total_combinations": tested,
                    "tested_combinations": tested,
                    "execution_time_seconds": round(exec_time, 2),
                    "speed_combinations_per_sec": speed,
                    "num_workers": os.cpu_count() or 4,
                    "best_params": result.get("best_params"),
                    "best_score": result.get("best_metrics", {}).get("sharpe_ratio", 0),
                    "best_metrics": result.get("best_metrics"),
                    "top_results": top_results[:10],
                    "trades": result.get("trades", []),
                    "equity_curve": result.get("equity_curve", []),
                    "performance_stats": {},
                    "smart_recommendations": {
                        "best_balanced": _to_rec(smart_recs.get("best_balanced")),
                        "best_conservative": _to_rec(smart_recs.get("best_conservative")),
                        "best_aggressive": _to_rec(smart_recs.get("best_aggressive")),
                        "recommendation_text": smart_recs.get("recommendation_text", ""),
                    },
                }

                logger.info(
                    f"[SSE] Sending complete event, JSON size: {len(json.dumps(response_data, default=str))} bytes"
                )
                yield f"data: {json.dumps(response_data, default=str)}\n\n"
                logger.info("[SSE] Complete event sent successfully")

        except Exception as e:
            logger.exception(f"SSE generator error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            executor.shutdown(wait=False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# TWO-STAGE OPTIMIZATION (VBT Screening + Fallback Validation)
# =============================================================================


class TwoStageOptimizationRequest(BaseModel):
    """Request for two-stage optimization."""

    # Data
    symbol: str = Field("BTCUSDT", description="Trading symbol")
    interval: str = Field("60", description="Timeframe (1, 5, 15, 30, 60, 240, D)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")

    # Strategy parameters
    rsi_period_range: list[int] = Field([7, 14, 21], description="RSI periods")
    rsi_overbought_range: list[int] = Field([65, 70, 75, 80], description="Overbought levels")
    rsi_oversold_range: list[int] = Field([20, 25, 30, 35], description="Oversold levels")
    stop_loss_range: list[float] = Field([0.02, 0.03, 0.05], description="Stop loss %")
    take_profit_range: list[float] = Field([0.02, 0.04, 0.06], description="Take profit %")

    # Trading settings
    direction: str = Field("both", description="long/short/both")
    leverage: int = Field(10, ge=1, le=125)
    initial_capital: float = Field(10000.0)
    commission: float = Field(0.0007, description="0.07% TradingView parity")
    slippage: float = Field(0.0005)

    # Two-stage settings
    top_n: int = Field(50, ge=10, le=200, description="Candidates to validate in Stage 2")
    use_bar_magnifier: bool = Field(True, description="Use tick-level precision (Bar Magnifier)")
    parallel_workers: int = Field(4, ge=1, le=8, description="Parallel validation workers")
    drift_threshold: float = Field(0.25, description="Max acceptable metric drift")

    # TradingView-like simulation settings
    fill_mode: str = Field(
        "next_bar_open",
        description="Order execution mode: 'bar_close' or 'next_bar_open'",
    )
    max_drawdown_trading: float = Field(
        0.0,
        ge=0,
        le=1.0,
        description="Max drawdown limit to stop trading (0 = disabled)",
    )


class TwoStageValidationResult(BaseModel):
    """Single validated result from Stage 2."""

    rank_stage1: int
    params: dict[str, Any]

    # VBT metrics
    vbt_sharpe: float
    vbt_total_return: float

    # Validated metrics
    validated_sharpe: float
    validated_total_return: float
    validated_max_drawdown: float
    validated_win_rate: float
    validated_total_trades: int

    # Analysis
    sharpe_drift: float
    is_reliable: bool
    confidence_score: float


class TwoStageOptimizationResponse(BaseModel):
    """Response for two-stage optimization."""

    status: str

    # Stage 1
    stage1_total_combinations: int
    stage1_tested: int
    stage1_execution_time: float
    stage1_backend: str

    # Stage 2
    stage2_candidates: int
    stage2_validated: int
    stage2_execution_time: float
    use_bar_magnifier: bool

    # Best result
    best_params: dict[str, Any]
    best_validated_sharpe: float
    best_validated_return: float
    best_confidence: float

    # All validated
    validated_results: list[TwoStageValidationResult]

    # Drift stats
    avg_sharpe_drift: float
    max_sharpe_drift: float
    reliable_count: int

    # Performance
    total_execution_time: float
    speedup_factor: float


@router.post(
    "/two-stage/optimize",
    response_model=TwoStageOptimizationResponse,
    summary="🚀 Two-Stage Optimization",
    description="""
    Two-Stage Optimization combines VBT speed with Fallback precision.

    **Stage 1 (Screening):** Fast VBT/GPU grid search over all combinations
    **Stage 2 (Validation):** Precise Fallback validation of top-N candidates

    Benefits:
    - 100x-600x faster than full Fallback optimization
    - Validates top candidates with tick-level precision
    - Detects "false champions" (VBT overestimates)
    - Calculates confidence scores for results
    """,
)
async def two_stage_optimization(
    request: TwoStageOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    Run two-stage optimization: VBT screening → Fallback validation.
    """
    import os
    import time
    from datetime import datetime as dt

    from backend.backtesting.fast_optimizer import load_candles_fast
    from backend.backtesting.two_stage_optimizer import TwoStageOptimizer

    logger.info("=" * 60)
    logger.info("🚀 TWO-STAGE OPTIMIZATION API")
    logger.info("=" * 60)

    total_combinations = (
        len(request.rsi_period_range)
        * len(request.rsi_overbought_range)
        * len(request.rsi_oversold_range)
        * len(request.stop_loss_range)
        * len(request.take_profit_range)
    )

    logger.info(f"   Total combinations: {total_combinations:,}")
    logger.info(f"   Top-N for validation: {request.top_n}")
    logger.info(f"   Bar Magnifier: {request.use_bar_magnifier}")

    try:
        # Parse dates
        start_dt = dt.fromisoformat(request.start_date)
        end_dt = dt.fromisoformat(request.end_date)
    except Exception as parse_err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {parse_err}")

    # Normalize interval
    interval = _normalize_interval(request.interval)

    # Load data - try DB first, then SmartKlineService
    from pathlib import Path

    default_db = str(Path(__file__).resolve().parents[3] / "data.sqlite3")
    db_path = os.environ.get("DATABASE_PATH", default_db)
    candle_data = None

    try:
        load_start = time.perf_counter()
        candle_data = load_candles_fast(
            db_path=db_path,
            symbol=request.symbol,
            interval=interval,
            start_date=start_dt,
            end_date=end_dt,
            use_cache=True,
        )
        load_time = time.perf_counter() - load_start
        if candle_data is not None and len(candle_data) > 0:
            logger.info(f"📊 Data loaded from DB in {load_time:.3f}s ({len(candle_data)} candles)")

    except Exception as e:
        logger.warning(f"DB load failed: {e}, trying SmartKlineService...")

    # Fallback to SmartKlineService if DB has no data
    if candle_data is None or len(candle_data) == 0:
        try:
            import numpy as np

            from backend.services.smart_kline_service import SMART_KLINE_SERVICE

            logger.info("📊 Loading data via SmartKlineService...")
            raw_candles = SMART_KLINE_SERVICE.get_candles(request.symbol, interval, limit=5000)

            if raw_candles:
                # Convert list of dicts to numpy array
                candle_data = np.array(
                    [
                        [
                            c["open_time"],
                            c["open"],
                            c["high"],
                            c["low"],
                            c["close"],
                            c["volume"],
                        ]
                        for c in raw_candles
                    ],
                    dtype=np.float64,
                )
                logger.info(f"📊 Loaded {len(candle_data)} candles via SmartKlineService")
        except Exception as e:
            logger.error(f"SmartKlineService failed: {e}")

    if candle_data is None or len(candle_data) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No data for {request.symbol}/{interval}. Load data first.",
        )

    # Convert to DataFrame
    candles = pd.DataFrame(
        {
            "open_time": candle_data[:, 0],  # Keep as ms for TwoStageOptimizer
            "open": candle_data[:, 1],
            "high": candle_data[:, 2],
            "low": candle_data[:, 3],
            "close": candle_data[:, 4],
            "volume": candle_data[:, 5],
        }
    )

    logger.info(f"📊 Loaded {len(candles)} candles")

    # Initialize optimizer
    optimizer = TwoStageOptimizer(
        top_n=request.top_n,
        use_bar_magnifier=request.use_bar_magnifier,
        parallel_workers=request.parallel_workers,
        drift_threshold=request.drift_threshold,
    )

    try:
        # Run two-stage optimization
        result = optimizer.optimize(
            candles=candles,
            symbol=request.symbol,
            interval=interval,
            rsi_period_range=request.rsi_period_range,
            rsi_overbought_range=request.rsi_overbought_range,
            rsi_oversold_range=request.rsi_oversold_range,
            stop_loss_range=request.stop_loss_range,
            take_profit_range=request.take_profit_range,
            initial_capital=request.initial_capital,
            leverage=request.leverage,
            commission=request.commission,
            slippage=request.slippage,
            direction=request.direction,
            # TradingView-like simulation settings
            fill_mode=request.fill_mode,
            max_drawdown=request.max_drawdown_trading,
        )

    except Exception as e:
        logger.exception("Two-stage optimization failed")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {e}")

    # Convert validated results to response format
    validated_results = []
    for r in result.validated_results[:100]:  # Limit to top 100
        validated_results.append(
            TwoStageValidationResult(
                rank_stage1=r.rank_stage1,
                params=r.params,
                vbt_sharpe=r.vbt_sharpe,
                vbt_total_return=r.vbt_total_return,
                validated_sharpe=r.validated_sharpe,
                validated_total_return=r.validated_total_return,
                validated_max_drawdown=r.validated_max_drawdown,
                validated_win_rate=r.validated_win_rate,
                validated_total_trades=r.validated_total_trades,
                sharpe_drift=r.sharpe_drift,
                is_reliable=r.is_reliable,
                confidence_score=r.confidence_score,
            )
        )

    logger.info(f"✅ Two-stage optimization completed in {result.total_execution_time:.1f}s")
    logger.info(f"🚀 Speedup: {result.speedup_factor:.0f}x")

    return TwoStageOptimizationResponse(
        status=result.status,
        stage1_total_combinations=result.stage1_total_combinations,
        stage1_tested=result.stage1_tested,
        stage1_execution_time=result.stage1_execution_time,
        stage1_backend=result.stage1_backend,
        stage2_candidates=result.stage2_candidates,
        stage2_validated=result.stage2_validated,
        stage2_execution_time=result.stage2_execution_time,
        use_bar_magnifier=result.use_bar_magnifier,
        best_params=result.best_params,
        best_validated_sharpe=result.best_validated_sharpe,
        best_validated_return=result.best_validated_return,
        best_confidence=result.best_confidence,
        validated_results=validated_results,
        avg_sharpe_drift=result.avg_sharpe_drift,
        max_sharpe_drift=result.max_sharpe_drift,
        reliable_count=result.reliable_count,
        total_execution_time=result.total_execution_time,
        speedup_factor=result.speedup_factor,
    )
