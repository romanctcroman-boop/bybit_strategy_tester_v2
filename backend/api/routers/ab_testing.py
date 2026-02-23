"""
A/B Testing API Router

Provides REST endpoints for managing A/B experiments:
- Create, start, stop experiments
- Record metrics
- Get results and dashboards
"""

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.ab_testing import (
    AllocationStrategy,
    ExperimentConfig,
    ExperimentStatus,
    Variant,
    create_strategy_ab_test,
    get_experiment_manager,
)

router = APIRouter(prefix="/ab-testing", tags=["A/B Testing"])


# ============================================================================
# Pydantic Models
# ============================================================================


class VariantCreate(BaseModel):
    """Model for creating a variant."""

    name: str
    weight: float = Field(default=0.5, ge=0, le=1)
    config: dict[str, Any] = Field(default_factory=dict)
    is_control: bool = False


class ExperimentCreate(BaseModel):
    """Model for creating an experiment."""

    name: str
    description: str = ""
    variants: list[VariantCreate]
    allocation_strategy: str = "deterministic"
    min_samples_per_variant: int = Field(default=100, ge=10)
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)
    primary_metric: str = "pnl"
    target_symbols: list[str] | None = None
    target_users: list[str] | None = None
    guardrail_metrics: dict[str, list[float]] | None = None


class QuickExperimentCreate(BaseModel):
    """Simplified model for quick A/B test creation."""

    name: str
    control_config: dict[str, Any]
    treatment_config: dict[str, Any]
    target_symbols: list[str] | None = None
    traffic_split: float = Field(default=0.5, ge=0.1, le=0.9)


class MetricRecord(BaseModel):
    """Model for recording a metric."""

    variant_name: str
    metric_name: str
    value: float


class TradeRecord(BaseModel):
    """Model for recording a trade result."""

    variant_name: str
    pnl: float
    win: bool
    metrics: dict[str, float] | None = None


class ExperimentResponse(BaseModel):
    """Response model for experiment."""

    id: str
    name: str
    status: str
    variants: list[str]
    total_samples: int
    created_at: str
    started_at: str | None = None


class ExperimentResultResponse(BaseModel):
    """Response model for experiment results."""

    experiment_id: str
    status: str
    winner: str | None = None
    confidence: float
    p_value: float
    effect_size: float
    total_samples: int
    recommendation: str
    warnings: list[str]
    variant_stats: dict[str, Any]


class VariantAllocationResponse(BaseModel):
    """Response for variant allocation."""

    experiment_id: str | None = None
    variant_name: str | None = None
    variant_config: dict[str, Any] | None = None
    is_control: bool = True


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(request: ExperimentCreate) -> ExperimentResponse:
    """Create a new A/B experiment."""
    try:
        # Convert allocation strategy
        strategy_map = {
            "random": AllocationStrategy.RANDOM,
            "deterministic": AllocationStrategy.DETERMINISTIC,
            "time_based": AllocationStrategy.TIME_BASED,
            "symbol_based": AllocationStrategy.SYMBOL_BASED,
        }
        allocation = strategy_map.get(
            request.allocation_strategy.lower(), AllocationStrategy.DETERMINISTIC
        )

        # Convert variants
        variants = [
            Variant(
                name=v.name, weight=v.weight, config=v.config, is_control=v.is_control
            )
            for v in request.variants
        ]

        # Convert guardrails
        guardrails = {}
        if request.guardrail_metrics:
            for name, bounds in request.guardrail_metrics.items():
                if len(bounds) >= 2:
                    guardrails[name] = (bounds[0], bounds[1])

        # Create config
        config = ExperimentConfig(
            name=request.name,
            description=request.description,
            variants=variants,
            allocation_strategy=allocation,
            min_samples_per_variant=request.min_samples_per_variant,
            confidence_level=request.confidence_level,
            primary_metric=request.primary_metric,
            target_symbols=set(request.target_symbols)
            if request.target_symbols
            else None,
            target_users=set(request.target_users) if request.target_users else None,
            guardrail_metrics=guardrails,
        )

        # Create experiment
        manager = get_experiment_manager()
        experiment = manager.create_experiment(config)

        return ExperimentResponse(
            id=experiment.id,
            name=experiment.config.name,
            status=experiment.status.value,
            variants=[v.name for v in experiment.config.variants],
            total_samples=0,
            created_at=experiment.created_at.isoformat(),
            started_at=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/experiments/quick",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_quick_experiment(request: QuickExperimentCreate) -> ExperimentResponse:
    """Create a quick A/B test with control and treatment."""
    try:
        experiment = create_strategy_ab_test(
            name=request.name,
            control_config=request.control_config,
            treatment_config=request.treatment_config,
            target_symbols=request.target_symbols,
            traffic_split=request.traffic_split,
        )

        return ExperimentResponse(
            id=experiment.id,
            name=experiment.config.name,
            status=experiment.status.value,
            variants=[v.name for v in experiment.config.variants],
            total_samples=0,
            created_at=experiment.created_at.isoformat(),
            started_at=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    status_filter: str | None = None,
) -> list[ExperimentResponse]:
    """List all experiments."""
    manager = get_experiment_manager()

    exp_status = None
    if status_filter:
        with contextlib.suppress(ValueError):
            exp_status = ExperimentStatus(status_filter.lower())

    experiments = manager.list_experiments(status=exp_status)

    return [
        ExperimentResponse(
            id=exp["id"],
            name=exp["name"],
            status=exp["status"],
            variants=exp["variants"],
            total_samples=exp["total_samples"],
            created_at=exp["created_at"],
            started_at=exp.get("started_at"),
        )
        for exp in experiments
    ]


@router.get("/experiments/{experiment_id}", response_model=dict[str, Any])
async def get_experiment(experiment_id: str) -> dict[str, Any]:
    """Get experiment details and dashboard data."""
    manager = get_experiment_manager()
    data = manager.get_dashboard_data(experiment_id)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    return data


@router.post("/experiments/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(experiment_id: str) -> ExperimentResponse:
    """Start an experiment."""
    manager = get_experiment_manager()

    try:
        manager.start_experiment(experiment_id)
        exp = manager.experiments.get(experiment_id)

        if not exp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found",
            )

        return ExperimentResponse(
            id=exp.id,
            name=exp.config.name,
            status=exp.status.value,
            variants=[v.name for v in exp.config.variants],
            total_samples=sum(v.samples for v in exp.config.variants),
            created_at=exp.created_at.isoformat(),
            started_at=exp.started_at.isoformat() if exp.started_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/experiments/{experiment_id}/stop", response_model=ExperimentResultResponse
)
async def stop_experiment(experiment_id: str) -> ExperimentResultResponse:
    """Stop an experiment and get results."""
    manager = get_experiment_manager()

    try:
        result = manager.stop_experiment(experiment_id)

        return ExperimentResultResponse(
            experiment_id=result.experiment_id,
            status=result.status.value,
            winner=result.winner,
            confidence=result.confidence,
            p_value=result.p_value,
            effect_size=result.effect_size,
            total_samples=result.total_samples,
            recommendation=result.recommendation,
            warnings=result.warnings,
            variant_stats=result.variant_stats,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(experiment_id: str) -> dict[str, str]:
    """Pause an experiment."""
    manager = get_experiment_manager()
    exp = manager.experiments.get(experiment_id)

    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    try:
        exp.pause()
        return {"status": "paused", "experiment_id": experiment_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/experiments/{experiment_id}/resume")
async def resume_experiment(experiment_id: str) -> dict[str, str]:
    """Resume a paused experiment."""
    manager = get_experiment_manager()
    exp = manager.experiments.get(experiment_id)

    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    try:
        exp.resume()
        return {"status": "running", "experiment_id": experiment_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/experiments/{experiment_id}/results", response_model=ExperimentResultResponse
)
async def get_experiment_results(experiment_id: str) -> ExperimentResultResponse:
    """Get current results for an experiment."""
    manager = get_experiment_manager()
    exp = manager.experiments.get(experiment_id)

    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    result = exp.get_results()

    return ExperimentResultResponse(
        experiment_id=result.experiment_id,
        status=result.status.value,
        winner=result.winner,
        confidence=result.confidence,
        p_value=result.p_value,
        effect_size=result.effect_size,
        total_samples=result.total_samples,
        recommendation=result.recommendation,
        warnings=result.warnings,
        variant_stats=result.variant_stats,
    )


@router.post("/experiments/{experiment_id}/metrics")
async def record_metric(experiment_id: str, request: MetricRecord) -> dict[str, str]:
    """Record a metric for an experiment variant."""
    manager = get_experiment_manager()
    exp = manager.experiments.get(experiment_id)

    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    exp.record_metric(
        variant_name=request.variant_name,
        metric_name=request.metric_name,
        value=request.value,
    )

    return {"status": "recorded"}


@router.post("/experiments/{experiment_id}/trades")
async def record_trade(experiment_id: str, request: TradeRecord) -> dict[str, str]:
    """Record a trade result for an experiment variant."""
    manager = get_experiment_manager()

    manager.record_trade_result(
        experiment_id=experiment_id,
        variant_name=request.variant_name,
        pnl=request.pnl,
        win=request.win,
        metrics=request.metrics,
    )

    return {"status": "recorded"}


@router.get("/allocate", response_model=VariantAllocationResponse)
async def allocate_variant(
    symbol: str, user_id: str | None = None
) -> VariantAllocationResponse:
    """Get the variant allocation for a request."""
    manager = get_experiment_manager()

    exp_id, variant = manager.get_variant_for_request(symbol=symbol, user_id=user_id)

    if exp_id and variant:
        return VariantAllocationResponse(
            experiment_id=exp_id,
            variant_name=variant.name,
            variant_config=variant.config,
            is_control=variant.is_control,
        )

    return VariantAllocationResponse(
        experiment_id=None,
        variant_name=None,
        variant_config=None,
        is_control=True,
    )
