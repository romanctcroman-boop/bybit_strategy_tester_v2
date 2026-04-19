"""
Optimization Router — Results viewer, chart, action and stats endpoints.

Covers:
- GET /{id}/charts/convergence
- GET /{id}/charts/sensitivity/{param}
- POST /{id}/apply/{rank}
- GET /{id}/results/paginated
- DELETE /{id}
- POST /{id}/rerun
- GET /stats/summary
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.routers.optimizations.crud import launch_optimization_task
from backend.api.routers.optimizations.models import (
    CreateOptimizationRequest,
    OptimizationResponse,
    ParamRangeSpec,
    optimization_to_response,
)
from backend.database import get_db
from backend.database.models.optimization import (
    Optimization,
    OptimizationStatus,
)
from backend.database.models.strategy import Strategy

logger = logging.getLogger(__name__)
router = APIRouter()


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

    strategy_id: str
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

    return ConvergenceDataResponse(  # type: ignore[arg-type]
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

    return SensitivityDataResponse(  # type: ignore[arg-type]
        param_name=param_name,
        values=values,
        scores=scores,
        metric=optimization.metric or "sharpe_ratio",
    )


@router.post("/{optimization_id}/apply/{result_rank}", response_model=ApplyParamsResponse)
async def apply_optimization_result(
    optimization_id: int,
    result_rank: int,
    strategy_id: str | None = None,
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
