"""
SLO Error Budget API Router.

Provides endpoints for:
- Viewing SLO definitions
- Getting error budget status
- Recording SLO metrics
- Dashboard summary
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.slo_error_budget import (
    BudgetStatus,
    SLOType,
    get_slo_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slo", tags=["slo-error-budget"])


# Pydantic models
class SLODefinitionResponse(BaseModel):
    """SLO definition response."""

    name: str
    type: str
    target: float
    window_hours: int
    description: str


class ErrorBudgetStateResponse(BaseModel):
    """Error budget state response."""

    slo_name: str
    total_events: int
    good_events: int
    bad_events: int
    current_sli: float
    target_slo: float
    error_budget_total: float
    error_budget_remaining: float
    error_budget_remaining_pct: float
    burn_rate_1h: float
    burn_rate_6h: float
    burn_rate_24h: float
    status: str
    time_until_exhausted_hours: float | None
    window_start: str
    window_end: str


class RecordLatencyRequest(BaseModel):
    """Request to record a latency metric."""

    slo_name: str = Field(..., description="Name of the SLO")
    latency_ms: float = Field(..., ge=0, description="Latency in milliseconds")
    endpoint: str = Field("", description="Endpoint or operation name")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordEventRequest(BaseModel):
    """Request to record a success/failure event."""

    slo_name: str = Field(..., description="Name of the SLO")
    success: bool = Field(..., description="Whether the event was successful")
    endpoint: str = Field("", description="Endpoint or operation name")
    error: str = Field("", description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary response."""

    timestamp: str
    total_slos: int
    summary: dict[str, int]
    overall_health: str
    critical_slos: list[dict[str, Any]]
    recent_alerts: list[dict[str, Any]]


# Endpoints
@router.get("/status", summary="Get SLO service status")
async def get_slo_status() -> dict[str, Any]:
    """Get current SLO Error Budget service status."""
    service = get_slo_service()
    summary = service.get_dashboard_summary()

    return {
        "service": "slo_error_budget",
        "active": True,
        "total_slos": summary["total_slos"],
        "overall_health": summary["overall_health"],
        "summary": summary["summary"],
    }


@router.get("/definitions", summary="List all SLO definitions")
async def list_slo_definitions() -> list[SLODefinitionResponse]:
    """List all registered SLO definitions."""
    service = get_slo_service()
    slos = service.list_slos()

    return [SLODefinitionResponse(**slo) for slo in slos]


@router.get("/budgets", summary="Get all error budget states")
async def get_all_budgets() -> dict[str, ErrorBudgetStateResponse]:
    """Get error budget states for all SLOs."""
    service = get_slo_service()
    states = service.get_all_slo_states()

    result = {}
    for name, state in states.items():
        result[name] = ErrorBudgetStateResponse(
            slo_name=state.slo_name,
            total_events=state.total_events,
            good_events=state.good_events,
            bad_events=state.bad_events,
            current_sli=state.current_sli,
            target_slo=state.target_slo,
            error_budget_total=state.error_budget_total,
            error_budget_remaining=state.error_budget_remaining,
            error_budget_remaining_pct=state.error_budget_remaining_pct,
            burn_rate_1h=state.burn_rate_1h,
            burn_rate_6h=state.burn_rate_6h,
            burn_rate_24h=state.burn_rate_24h,
            status=state.status.value,
            time_until_exhausted_hours=(
                state.time_until_exhausted.total_seconds() / 3600
                if state.time_until_exhausted
                else None
            ),
            window_start=state.window_start.isoformat(),
            window_end=state.window_end.isoformat(),
        )

    return result


@router.get("/budgets/{slo_name}", summary="Get error budget for specific SLO")
async def get_budget(slo_name: str) -> ErrorBudgetStateResponse:
    """Get error budget state for a specific SLO."""
    service = get_slo_service()
    state = service.get_error_budget_state(slo_name)

    if not state:
        raise HTTPException(status_code=404, detail=f"SLO not found: {slo_name}")

    return ErrorBudgetStateResponse(
        slo_name=state.slo_name,
        total_events=state.total_events,
        good_events=state.good_events,
        bad_events=state.bad_events,
        current_sli=state.current_sli,
        target_slo=state.target_slo,
        error_budget_total=state.error_budget_total,
        error_budget_remaining=state.error_budget_remaining,
        error_budget_remaining_pct=state.error_budget_remaining_pct,
        burn_rate_1h=state.burn_rate_1h,
        burn_rate_6h=state.burn_rate_6h,
        burn_rate_24h=state.burn_rate_24h,
        status=state.status.value,
        time_until_exhausted_hours=(
            state.time_until_exhausted.total_seconds() / 3600
            if state.time_until_exhausted
            else None
        ),
        window_start=state.window_start.isoformat(),
        window_end=state.window_end.isoformat(),
    )


@router.post("/record/latency", summary="Record latency metric")
async def record_latency(request: RecordLatencyRequest) -> dict[str, Any]:
    """Record a latency metric for an SLO."""
    service = get_slo_service()

    is_good = service.record_latency(
        slo_name=request.slo_name,
        latency_ms=request.latency_ms,
        endpoint=request.endpoint,
        metadata=request.metadata,
    )

    return {
        "recorded": True,
        "slo_name": request.slo_name,
        "latency_ms": request.latency_ms,
        "met_slo": is_good,
    }


@router.post("/record/event", summary="Record success/failure event")
async def record_event(request: RecordEventRequest) -> dict[str, Any]:
    """Record a success or failure event for an SLO."""
    service = get_slo_service()

    if request.success:
        service.record_success(
            slo_name=request.slo_name,
            endpoint=request.endpoint,
            metadata=request.metadata,
        )
    else:
        service.record_failure(
            slo_name=request.slo_name,
            endpoint=request.endpoint,
            error=request.error,
            metadata=request.metadata,
        )

    return {"recorded": True, "slo_name": request.slo_name, "success": request.success}


@router.get("/dashboard", summary="Get dashboard summary")
async def get_dashboard() -> DashboardSummaryResponse:
    """Get comprehensive dashboard summary for all SLOs."""
    service = get_slo_service()
    summary = service.get_dashboard_summary()

    return DashboardSummaryResponse(**summary)


@router.get("/types", summary="List SLO types")
async def list_slo_types() -> list[dict[str, str]]:
    """List all available SLO types."""
    return [
        {"type": t.value, "description": t.name.replace("_", " ").title()}
        for t in SLOType
    ]


@router.get("/statuses", summary="List budget statuses")
async def list_budget_statuses() -> list[dict[str, str]]:
    """List all budget status levels."""
    descriptions = {
        BudgetStatus.HEALTHY: "Less than 50% of error budget consumed",
        BudgetStatus.WARNING: "50-80% of error budget consumed",
        BudgetStatus.CRITICAL: "80-100% of error budget consumed",
        BudgetStatus.EXHAUSTED: "Error budget fully consumed",
    }
    return [{"status": s.value, "description": descriptions[s]} for s in BudgetStatus]


@router.delete("/alerts", summary="Clear all alerts")
async def clear_alerts() -> dict[str, Any]:
    """Clear all burn rate alerts."""
    service = get_slo_service()
    count = service.clear_alerts()

    return {"cleared": count, "message": f"Cleared {count} alerts"}


@router.post("/simulate", summary="Simulate SLO data for testing")
async def simulate_data(
    slo_name: str = Query("api_latency_p99", description="SLO to simulate"),
    good_events: int = Query(950, ge=0, description="Number of good events"),
    bad_events: int = Query(50, ge=0, description="Number of bad events"),
) -> dict[str, Any]:
    """Simulate SLO data for testing purposes."""
    service = get_slo_service()

    slo = service._slos.get(slo_name)
    if not slo:
        raise HTTPException(status_code=404, detail=f"SLO not found: {slo_name}")

    # Record good events
    for _ in range(good_events):
        service.record_latency(
            slo_name=slo_name,
            latency_ms=slo.target * 0.5,  # 50% of target
            endpoint="/simulated",
        )

    # Record bad events
    for _ in range(bad_events):
        service.record_latency(
            slo_name=slo_name,
            latency_ms=slo.target * 1.5,  # 150% of target
            endpoint="/simulated",
        )

    state = service.get_error_budget_state(slo_name)

    return {
        "simulated": True,
        "slo_name": slo_name,
        "good_events_added": good_events,
        "bad_events_added": bad_events,
        "current_status": state.status.value if state else "unknown",
        "budget_remaining_pct": state.error_budget_remaining_pct if state else 0,
    }
