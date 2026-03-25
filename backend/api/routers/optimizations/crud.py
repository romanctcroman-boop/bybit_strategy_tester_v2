"""
Optimization Router — CRUD endpoints.

Covers:
- POST /  → create_optimization
- GET /   → list_optimizations
- GET /{id} → get_optimization
- GET /{id}/status → get_optimization_status
- GET /{id}/results → get_optimization_results
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.routers.optimizations.helpers import generate_param_values
from backend.api.routers.optimizations.models import (
    CreateOptimizationRequest,
    OptimizationResponse,
    OptimizationResultsResponse,
    OptimizationStatusResponse,
    calculate_total_combinations,
    optimization_to_response,
    parse_optimization_type,
)
from backend.database import get_db
from backend.database.models.optimization import (
    Optimization,
    OptimizationStatus,
    OptimizationType,
)
from backend.database.models.strategy import Strategy

logger = logging.getLogger(__name__)
router = APIRouter()


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
    total_combinations = calculate_total_combinations(dict(request.param_ranges.items()), opt_type)
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
            param_space = {k: v.model_dump() for k, v in request.param_ranges.items()}  # type: ignore[no-redef]

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
                            {random.randint(int(spec.low), int(spec.high)) for _ in range(min(request.n_trials, 50))}
                        )
                    else:
                        # Generate random floats with proper precision
                        param_space[param_name] = list(
                            {
                                round(random.uniform(spec.low, spec.high), precision)
                                for _ in range(min(request.n_trials, 50))
                            }
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
                opt.status = OptimizationStatus.FAILED  # type: ignore[assignment]
                opt.error_message = str(e)  # type: ignore[assignment]
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

    return OptimizationStatusResponse(  # type: ignore[arg-type]
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

    return OptimizationResultsResponse(  # type: ignore[arg-type]
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
