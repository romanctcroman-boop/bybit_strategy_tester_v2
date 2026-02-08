"""
Chaos Engineering Router
Provides API endpoints for chaos engineering experiments.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.chaos_engineering import (
    FaultConfig,
    FaultType,
    get_chaos_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chaos", tags=["Chaos Engineering"])


# ============================================================================
# Request/Response Models
# ============================================================================


class FaultConfigRequest(BaseModel):
    """Request to create a fault configuration."""

    fault_type: str = Field(..., description="Type of fault to inject")
    target_service: str = Field(..., description="Service to target")
    duration_seconds: int = Field(30, ge=1, le=300)
    probability: float = Field(1.0, ge=0.0, le=1.0)
    latency_ms: int = Field(1000, ge=0, le=30000)
    error_code: int = Field(500, ge=400, le=599)
    error_message: str = "Chaos experiment induced failure"


class ExperimentRequest(BaseModel):
    """Request to create an experiment."""

    name: str = Field(..., min_length=1, max_length=100)
    fault_config: FaultConfigRequest
    hypothesis: str = ""


class ExperimentResponse(BaseModel):
    """Response with experiment details."""

    experiment_id: str
    name: str
    status: str
    fault_config: dict[str, Any]
    started_at: str | None = None
    ended_at: str | None = None
    affected_requests: int = 0
    errors_injected: int = 0
    observations: list[str] = []


class ChaosStatusResponse(BaseModel):
    """Chaos engineering status."""

    enabled: bool
    active_faults: int
    total_experiments: int
    completed_experiments: int
    failed_experiments: int
    available_templates: list[str]
    pending_experiments: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=ChaosStatusResponse)
async def get_chaos_status():
    """
    Get chaos engineering status and metrics.

    Returns:
        Current status and metrics
    """
    try:
        service = get_chaos_service()
        metrics = service.get_metrics()
        return ChaosStatusResponse(**metrics)
    except Exception as e:
        logger.error(f"Error getting chaos status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_chaos(
    confirm: bool = Query(False, description="Confirm enabling chaos engineering"),
):
    """
    Enable chaos engineering.

    ⚠️ DANGEROUS: This enables fault injection in the system.

    Args:
        confirm: Must be True to enable

    Returns:
        Confirmation of enablement
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm=true to enable chaos engineering. This is dangerous!",
        )

    try:
        service = get_chaos_service()
        service.enable()
        return {
            "success": True,
            "message": "⚠️ Chaos engineering ENABLED",
            "warning": "Faults can now be injected into the system",
        }
    except Exception as e:
        logger.error(f"Error enabling chaos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_chaos():
    """
    Disable chaos engineering and clear all faults.

    Returns:
        Confirmation of disablement
    """
    try:
        service = get_chaos_service()
        service.disable()
        return {
            "success": True,
            "message": "Chaos engineering disabled",
            "faults_cleared": True,
        }
    except Exception as e:
        logger.error(f"Error disabling chaos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates():
    """
    List available experiment templates.

    Returns:
        List of template names and configurations
    """
    try:
        service = get_chaos_service()
        templates = {}
        for name, config in service.templates.items():
            templates[name] = config.to_dict()
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments")
async def create_experiment(request: ExperimentRequest):
    """
    Create a new chaos experiment.

    Args:
        request: Experiment configuration

    Returns:
        Created experiment details
    """
    try:
        service = get_chaos_service()

        # Validate fault type
        try:
            fault_type = FaultType(request.fault_config.fault_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fault type. Must be one of: {[ft.value for ft in FaultType]}",
            )

        config = FaultConfig(
            fault_type=fault_type,
            target_service=request.fault_config.target_service,
            duration_seconds=request.fault_config.duration_seconds,
            probability=request.fault_config.probability,
            latency_ms=request.fault_config.latency_ms,
            error_code=request.fault_config.error_code,
            error_message=request.fault_config.error_message,
        )

        experiment = service.create_experiment(
            name=request.name,
            fault_config=config,
            hypothesis=request.hypothesis,
        )

        return {
            "success": True,
            "experiment_id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "fault_config": config.to_dict(),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/from-template/{template_name}")
async def create_from_template(
    template_name: str,
    experiment_name: str | None = Query(None),
):
    """
    Create an experiment from a pre-defined template.

    Args:
        template_name: Name of the template
        experiment_name: Optional custom name

    Returns:
        Created experiment details
    """
    try:
        service = get_chaos_service()
        experiment = service.create_from_template(template_name, experiment_name)

        return {
            "success": True,
            "experiment_id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "fault_config": experiment.fault_config.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating from template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/run", response_model=ExperimentResponse)
async def run_experiment(experiment_id: str):
    """
    Run a chaos experiment.

    Args:
        experiment_id: ID of experiment to run

    Returns:
        Experiment results
    """
    try:
        service = get_chaos_service()
        result = await service.run_experiment(experiment_id)

        return ExperimentResponse(
            experiment_id=result.experiment_id,
            name=result.name,
            status=result.status.value,
            fault_config=result.fault_config.to_dict(),
            started_at=result.started_at.isoformat(),
            ended_at=result.ended_at.isoformat() if result.ended_at else None,
            affected_requests=result.affected_requests,
            errors_injected=result.errors_injected,
            observations=result.observations,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error running experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-test")
async def run_quick_test(
    fault_type: str = Query(..., description="Type of fault"),
    target_service: str = Query(..., description="Service to target"),
    duration: int = Query(10, ge=1, le=60, description="Duration in seconds"),
):
    """
    Run a quick chaos test.

    Args:
        fault_type: Type of fault to inject
        target_service: Service to target
        duration: Duration in seconds

    Returns:
        Test results
    """
    try:
        # Validate fault type
        try:
            ft = FaultType(fault_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fault type. Must be one of: {[ftype.value for ftype in FaultType]}",
            )

        service = get_chaos_service()
        result = await service.run_quick_test(ft, target_service, duration)

        return {
            "success": True,
            "experiment_id": result.experiment_id,
            "name": result.name,
            "status": result.status.value,
            "duration_seconds": duration,
            "observations": result.observations,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error running quick test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faults")
async def get_active_faults():
    """
    Get currently active faults.

    Returns:
        List of active faults
    """
    try:
        service = get_chaos_service()
        faults = service.get_active_faults()
        return {
            "active_faults": [config.to_dict() for config in faults.values()],
            "count": len(faults),
        }
    except Exception as e:
        logger.error(f"Error getting active faults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/faults")
async def clear_all_faults():
    """
    Clear all active faults immediately.

    Returns:
        Confirmation of clearing
    """
    try:
        service = get_chaos_service()
        count = len(service.injector.active_faults)
        service.injector.clear_all_faults()
        return {
            "success": True,
            "message": f"Cleared {count} active faults",
            "cleared": count,
        }
    except Exception as e:
        logger.error(f"Error clearing faults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=list[ExperimentResponse])
async def get_experiment_history(limit: int = Query(50, ge=1, le=100)):
    """
    Get experiment history.

    Args:
        limit: Maximum number of results

    Returns:
        List of past experiments
    """
    try:
        service = get_chaos_service()
        results = service.get_experiment_history(limit)

        return [
            ExperimentResponse(
                experiment_id=r.experiment_id,
                name=r.name,
                status=r.status.value,
                fault_config=r.fault_config.to_dict(),
                started_at=r.started_at.isoformat(),
                ended_at=r.ended_at.isoformat() if r.ended_at else None,
                affected_requests=r.affected_requests,
                errors_injected=r.errors_injected,
                observations=r.observations,
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    """
    Get details of a specific experiment.

    Args:
        experiment_id: Experiment ID

    Returns:
        Experiment details
    """
    try:
        service = get_chaos_service()
        experiment = service.experiments.get(experiment_id)

        if not experiment:
            raise HTTPException(
                status_code=404,
                detail=f"Experiment '{experiment_id}' not found",
            )

        return {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "hypothesis": experiment.hypothesis,
            "fault_config": experiment.fault_config.to_dict(),
            "has_result": experiment.result is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
