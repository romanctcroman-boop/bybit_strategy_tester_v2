"""
Genetic Algorithm Optimization API Router.

REST API for genetic algorithm optimization:
- POST /genetic/optimize - Run genetic optimization
- GET /genetic/jobs - List all genetic optimization jobs
- GET /genetic/jobs/{id} - Get job status and results
- DELETE /genetic/jobs/{id} - Cancel job

Example request:
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "start_date": "2025-01-01",
  "end_date": "2025-01-15",
  "strategy_type": "rsi",
  "param_ranges": {
    "period": [5, 30],
    "overbought": [60, 80],
    "oversold": [20, 40]
  },
  "fitness_function": "sharpe",
  "population_size": 50,
  "n_generations": 100,
  "selection": "tournament",
  "crossover": "arithmetic",
  "mutation": "gaussian"
}
```
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
import threading
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.strategies import RSIStrategy
from backend.database import get_db
from backend.database.models.genetic_job import GeneticJob, GeneticJobStatus
from backend.services.data_service import DataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/genetic", tags=["Genetic Optimization"])

# Global store for cancel events (in-memory, indexed by job_uuid)
_cancel_events: dict[str, threading.Event] = {}

# Configuration constants
MAX_ACTIVE_JOBS = 10
MAX_GENERATIONS = 500
MAX_POPULATION_SIZE = 200


class GeneticOptimizationRequest(BaseModel):
    """Request model for genetic optimization"""

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Candlestick timeframe (e.g., 1h, 15m)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")

    strategy_type: str = Field(default="rsi", description="Strategy type")
    param_ranges: dict[str, list[float]] = Field(..., description="Parameter ranges {name: [min, max]}")

    # Genetic algorithm parameters
    fitness_function: str = Field(default="sharpe", description="Fitness function: sharpe, sortino, multi_objective")
    population_size: int = Field(default=50, ge=10, le=MAX_POPULATION_SIZE)
    n_generations: int = Field(default=100, ge=10, le=MAX_GENERATIONS)
    selection: str = Field(default="tournament", description="Selection strategy")
    crossover: str = Field(default="arithmetic", description="Crossover operator")
    mutation: str = Field(default="gaussian", description="Mutation operator")
    elitism_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    crossover_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    # Multi-objective weights
    multi_objective_weights: dict[str, float] | None = Field(
        default=None, description="Weights for multi-objective optimization"
    )

    # Execution
    n_workers: int = Field(default=1, ge=1, le=8)
    random_state: int | None = Field(default=None)

    @validator("param_ranges")
    def validate_param_ranges(cls, v):
        """Validate parameter ranges"""
        for name, range_vals in v.items():
            if not isinstance(range_vals, list) or len(range_vals) != 2:
                raise ValueError(f"Parameter '{name}' must have [min, max] range")
            if range_vals[0] >= range_vals[1]:
                raise ValueError(f"Parameter '{name}': min must be less than max")
        return v


class GeneticOptimizationResponse(BaseModel):
    """Response model for genetic optimization"""

    job_id: str
    status: str
    message: str
    estimated_time: float | None = None


class GeneticJobStatusResponse(BaseModel):
    """Job status model for API response"""

    job_id: str
    status: str  # running, completed, failed, cancelled
    progress: float = 0.0  # 0-100
    current_generation: int = 0
    best_fitness: float | None = None
    best_params: dict[str, float] | None = None
    message: str | None = None
    created_at: str
    completed_at: str | None = None
    execution_time: float | None = None


class GeneticJobResultResponse(BaseModel):
    """Job result model for API response"""

    job_id: str
    status: str
    best_fitness: float
    best_params: dict[str, float]
    n_evaluations: int
    execution_time: float
    generations: int
    improvement_percent: float
    history: dict[str, list[float]]
    pareto_front: list[dict[str, Any]] | None = None
    metrics: dict[str, float]


def _get_strategy_class(strategy_type: str):
    """Get strategy class by type"""
    strategies = {
        "rsi": RSIStrategy,
        # Add more strategies as needed
    }

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategies[strategy_type]


def _run_genetic_optimization(job_uuid: str, request: GeneticOptimizationRequest, db: Session):
    """Run genetic optimization in background"""
    cancel_event = threading.Event()
    _cancel_events[job_uuid] = cancel_event

    try:
        logger.info(f"[{job_uuid}] Starting genetic optimization")

        # Get job from DB and mark as running
        job = db.query(GeneticJob).filter(GeneticJob.job_uuid == job_uuid).first()
        if not job:
            logger.error(f"[{job_uuid}] Job not found in database")
            return

        job.mark_running()
        db.commit()

        # Import genetic optimizer
        from backend.backtesting.genetic import (
            FitnessFactory,
            GeneticOptimizer,
        )

        # Load data
        data_service = DataService()
        data = data_service.load_ohlcv(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start_date,
            end=request.end_date,
        )

        if data.empty:
            raise ValueError("No data loaded")

        # Create optimizer
        if request.fitness_function == "multi_objective":
            fitness_fn = FitnessFactory.create(
                "multi_objective",
                weights=request.multi_objective_weights
                or {
                    "sharpe_ratio": 0.4,
                    "win_rate": 0.2,
                    "max_drawdown": 0.2,
                    "total_return": 0.2,
                },
            )
        else:
            fitness_fn = FitnessFactory.create(request.fitness_function)

        optimizer = GeneticOptimizer(
            population_size=request.population_size,
            n_generations=request.n_generations,
            selection=request.selection,
            crossover=request.crossover,
            mutation=request.mutation,
            fitness_function=fitness_fn,
            elitism_rate=request.elitism_rate,
            crossover_rate=request.crossover_rate,
            mutation_rate=request.mutation_rate,
            n_workers=request.n_workers,
            random_state=request.random_state,
            cancel_event=cancel_event,  # Pass cancel event
        )

        # Get strategy class
        strategy_class = _get_strategy_class(request.strategy_type)

        # Create backtest engine
        engine = FallbackEngineV4()

        # Run optimization
        result = optimizer.optimize(
            strategy_class=strategy_class,
            param_ranges=request.param_ranges,
            data=data,
            backtest_engine=engine,
            backtest_config={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
            },
        )

        # Check if cancelled
        if cancel_event.is_set():
            job.mark_cancelled()
            db.commit()
            logger.info(f"[{job_uuid}] Optimization cancelled by user")
            return

        # Store results
        result_dict = result.to_dict()
        job.mark_completed(
            best_fitness=result_dict.get("best_fitness", 0.0),
            best_params=result_dict.get("best_params", {}),
            n_evaluations=result_dict.get("n_evaluations", 0),
            execution_time=result_dict.get("execution_time", 0.0),
            generations=result_dict.get("generations", 0),
            improvement_percent=result_dict.get("improvement_percent", 0.0),
            history=result_dict.get("history", {}),
            pareto_front=result_dict.get("pareto_front"),
            metrics=result_dict.get("best_individual", {}).get("backtest_results", {}).get("metrics", {}),
        )
        db.commit()

        logger.info(f"[{job_uuid}] Optimization completed: {result.best_individual.fitness:.4f}")

    except Exception as e:
        logger.error(f"[{job_uuid}] Optimization failed: {e}", exc_info=True)

        # Update job in DB
        job = db.query(GeneticJob).filter(GeneticJob.job_uuid == job_uuid).first()
        if job:
            job.mark_failed(str(e))
            db.commit()


@router.post("/optimize", response_model=GeneticOptimizationResponse)
async def create_genetic_optimization(
    request: GeneticOptimizationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new genetic optimization job.

    Runs genetic algorithm optimization in the background.
    Use GET /genetic/jobs/{job_id} to check status and retrieve results.
    """
    # Check active jobs limit
    active_jobs = db.query(GeneticJob).filter(GeneticJob.status == GeneticJobStatus.RUNNING).count()

    if active_jobs >= MAX_ACTIVE_JOBS:
        raise HTTPException(
            status_code=429, detail=f"Too many active jobs (max: {MAX_ACTIVE_JOBS}). Please wait or cancel some jobs."
        )

    job_uuid = str(uuid.uuid4())

    # Estimate execution time (rough estimate: 0.1s per evaluation)
    n_evaluations = request.population_size * request.n_generations
    estimated_time = n_evaluations * 0.1 / request.n_workers

    # Create job record in DB
    db_job = GeneticJob(
        id=str(uuid.uuid4()),  # Internal ID
        job_uuid=job_uuid,
        status=GeneticJobStatus.PENDING,
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
        strategy_type=request.strategy_type,
        param_ranges=request.param_ranges,
        fitness_function=request.fitness_function,
        population_size=request.population_size,
        n_generations=request.n_generations,
        selection_strategy=request.selection,
        crossover_operator=request.crossover,
        mutation_operator=request.mutation,
        elitism_rate=request.elitism_rate,
        crossover_rate=request.crossover_rate,
        mutation_rate=request.mutation_rate,
        multi_objective_weights=request.multi_objective_weights,
        n_workers=request.n_workers,
        random_state=request.random_state,
    )
    db.add(db_job)
    db.commit()

    # Run in background
    background_tasks.add_task(_run_genetic_optimization, job_uuid, request, db)

    return GeneticOptimizationResponse(
        job_id=job_uuid,
        status="pending",
        message="Optimization job created and queued",
        estimated_time=estimated_time,
    )


@router.get("/jobs", response_model=list[GeneticJobStatusResponse])
async def list_genetic_jobs(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all genetic optimization jobs with pagination"""
    query = db.query(GeneticJob)

    if status:
        try:
            status_enum = GeneticJobStatus(status)
            query = query.filter(GeneticJob.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Order by created_at descending (newest first)
    query = query.order_by(GeneticJob.created_at.desc())

    # Pagination
    jobs = query.offset(offset).limit(limit).all()

    return [
        GeneticJobStatusResponse(
            job_id=job.job_uuid,
            status=job.status.value,
            progress=job.progress,
            current_generation=job.current_generation,
            best_fitness=job.best_fitness,
            best_params=job.best_params,
            message=job.error_message,
            created_at=job.created_at.isoformat() if job.created_at else "",
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            execution_time=job.execution_time,
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=GeneticJobResultResponse)
async def get_genetic_job_result(job_id: str, db: Session = Depends(get_db)):
    """Get genetic optimization job result"""
    job = db.query(GeneticJob).filter(GeneticJob.job_uuid == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != GeneticJobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job.status.value})")

    return GeneticJobResultResponse(
        job_id=job.job_uuid,
        status=job.status.value,
        best_fitness=job.best_fitness or 0.0,
        best_params=job.best_params or {},
        n_evaluations=job.n_evaluations,
        execution_time=job.execution_time or 0.0,
        generations=job.generations_completed,
        improvement_percent=job.improvement_percent or 0.0,
        history=job.history or {},
        pareto_front=job.pareto_front,
        metrics=job.metrics or {},
    )


@router.get("/jobs/{job_id}/status")
async def get_genetic_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get genetic optimization job status (lightweight endpoint)"""
    job = db.query(GeneticJob).filter(GeneticJob.job_uuid == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.job_uuid,
        "status": job.status.value,
        "progress": job.progress,
        "current_generation": job.current_generation,
        "best_fitness": job.best_fitness,
        "message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.delete("/jobs/{job_id}")
async def cancel_genetic_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running genetic optimization job"""
    job = db.query(GeneticJob).filter(GeneticJob.job_uuid == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in [GeneticJobStatus.COMPLETED, GeneticJobStatus.FAILED, GeneticJobStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Job already finished")

    # Mark as cancelled in DB
    job.request_cancel()
    db.commit()

    # Signal cancel event
    if job_id in _cancel_events:
        _cancel_events[job_id].set()
        del _cancel_events[job_id]

    logger.info(f"[{job_id}] Cancellation requested by user")

    return {"message": f"Job {job_id} cancellation requested"}
