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
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.strategies import RSIStrategy
from backend.services.data_service import DataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/genetic", tags=["Genetic Optimization"])

# Store for optimization jobs (in production, use Redis/DB)
_jobs: Dict[str, Dict[str, Any]] = {}


class GeneticOptimizationRequest(BaseModel):
    """Request model for genetic optimization"""

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Candlestick timeframe (e.g., 1h, 15m)")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")

    strategy_type: str = Field(default="rsi", description="Strategy type")
    param_ranges: Dict[str, List[float]] = Field(..., description="Parameter ranges {name: [min, max]}")

    # Genetic algorithm parameters
    fitness_function: str = Field(default="sharpe", description="Fitness function: sharpe, sortino, multi_objective")
    population_size: int = Field(default=50, ge=10, le=200)
    n_generations: int = Field(default=100, ge=10, le=500)
    selection: str = Field(default="tournament", description="Selection strategy")
    crossover: str = Field(default="arithmetic", description="Crossover operator")
    mutation: str = Field(default="gaussian", description="Mutation operator")
    elitism_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    crossover_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    # Multi-objective weights
    multi_objective_weights: Optional[Dict[str, float]] = Field(
        default=None, description="Weights for multi-objective optimization"
    )

    # Execution
    n_workers: int = Field(default=1, ge=1, le=8)
    random_state: Optional[int] = Field(default=None)


class GeneticOptimizationResponse(BaseModel):
    """Response model for genetic optimization"""

    job_id: str
    status: str
    message: str
    estimated_time: Optional[float] = None


class GeneticJobStatus(BaseModel):
    """Job status model"""

    job_id: str
    status: str  # running, completed, failed, cancelled
    progress: float = 0.0  # 0-100
    current_generation: int = 0
    best_fitness: Optional[float] = None
    best_params: Optional[Dict[str, float]] = None
    message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


class GeneticJobResult(BaseModel):
    """Job result model"""

    job_id: str
    status: str
    best_fitness: float
    best_params: Dict[str, float]
    n_evaluations: int
    execution_time: float
    generations: int
    improvement_percent: float
    history: Dict[str, List[float]]
    pareto_front: Optional[List[Dict[str, Any]]] = None
    metrics: Dict[str, float]


def _get_strategy_class(strategy_type: str):
    """Get strategy class by type"""
    strategies = {
        "rsi": RSIStrategy,
        # Add more strategies as needed
    }

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategies[strategy_type]


def _run_genetic_optimization(job_id: str, request: GeneticOptimizationRequest):
    """Run genetic optimization in background"""
    try:
        logger.info(f"[{job_id}] Starting genetic optimization")

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

        # Store results
        _jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100.0,
                "result": result.to_dict(),
                "completed_at": datetime.now(),
                "execution_time": result.execution_time,
            }
        )

        logger.info(f"[{job_id}] Optimization completed: {result.best_individual.fitness:.4f}")

    except Exception as e:
        logger.error(f"[{job_id}] Optimization failed: {e}", exc_info=True)
        _jobs[job_id].update(
            {
                "status": "failed",
                "message": str(e),
                "completed_at": datetime.now(),
            }
        )


@router.post("/optimize", response_model=GeneticOptimizationResponse)
async def create_genetic_optimization(request: GeneticOptimizationRequest, background_tasks: BackgroundTasks):
    """
    Create a new genetic optimization job.

    Runs genetic algorithm optimization in the background.
    Use GET /genetic/jobs/{job_id} to check status and retrieve results.
    """
    job_id = str(uuid.uuid4())

    # Estimate execution time (rough estimate: 0.1s per evaluation)
    n_evaluations = request.population_size * request.n_generations
    estimated_time = n_evaluations * 0.1 * request.n_workers

    # Create job record
    _jobs[job_id] = {
        "status": "running",
        "progress": 0.0,
        "request": request.dict(),
        "created_at": datetime.now(),
        "current_generation": 0,
    }

    # Run in background
    background_tasks.add_task(_run_genetic_optimization, job_id, request)

    return GeneticOptimizationResponse(
        job_id=job_id,
        status="running",
        message="Optimization started",
        estimated_time=estimated_time,
    )


@router.get("/jobs", response_model=List[GeneticJobStatus])
async def list_genetic_jobs(status: Optional[str] = None, limit: int = 20):
    """List all genetic optimization jobs"""
    jobs = []

    for job_id, job_data in _jobs.items():
        if status and job_data.get("status") != status:
            continue

        result = job_data.get("result", {})

        jobs.append(
            GeneticJobStatus(
                job_id=job_id,
                status=job_data.get("status", "unknown"),
                progress=job_data.get("progress", 0.0),
                current_generation=job_data.get("current_generation", 0),
                best_fitness=result.get("best_fitness"),
                best_params=result.get("best_params"),
                message=job_data.get("message"),
                created_at=job_data.get("created_at"),
                completed_at=job_data.get("completed_at"),
                execution_time=job_data.get("execution_time"),
            )
        )

        if len(jobs) >= limit:
            break

    return jobs


@router.get("/jobs/{job_id}", response_model=GeneticJobResult)
async def get_genetic_job_result(job_id: str):
    """Get genetic optimization job result"""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = _jobs[job_id]

    if job_data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job_data['status']})")

    result = job_data.get("result", {})

    return GeneticJobResult(
        job_id=job_id,
        status="completed",
        best_fitness=result.get("best_fitness", 0.0),
        best_params=result.get("best_params", {}),
        n_evaluations=result.get("n_evaluations", 0),
        execution_time=result.get("execution_time", 0.0),
        generations=result.get("generations", 0),
        improvement_percent=result.get("improvement_percent", 0.0),
        history=result.get("history", {}),
        pareto_front=result.get("pareto_front"),
        metrics=result.get("best_individual", {}).get("backtest_results", {}).get("metrics", {}),
    )


@router.delete("/jobs/{job_id}")
async def cancel_genetic_job(job_id: str):
    """Cancel a running genetic optimization job"""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = _jobs[job_id]

    if job_data["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Job already finished")

    # Mark as cancelled (in production, would need to stop the actual task)
    job_data["status"] = "cancelled"
    job_data["message"] = "Cancelled by user"
    job_data["completed_at"] = datetime.now()

    return {"message": f"Job {job_id} cancelled"}
