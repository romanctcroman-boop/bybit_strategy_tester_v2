"""
Synthetic Monitoring API Router.

AI Agent Recommendation Implementation:
Provides REST API endpoints for synthetic monitoring and SLA tracking.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.synthetic_monitoring import (
    ProbeStatus,
    ProbeType,
    get_synthetic_monitor,
)

router = APIRouter(prefix="/api/v1/synthetic-monitoring")


# ============================================================================
# Request/Response Models
# ============================================================================


class ProbeResultResponse(BaseModel):
    """Response model for probe result."""

    probe_id: str
    probe_name: str
    probe_type: str
    status: str
    latency_ms: float
    timestamp: datetime
    success: bool
    error_message: str | None


class ProbeMetricsResponse(BaseModel):
    """Response model for probe metrics."""

    probe_id: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    current_status: str
    uptime_pct: float
    last_run: datetime | None
    last_success: datetime | None
    last_failure: datetime | None


class ProbeConfigResponse(BaseModel):
    """Response model for probe configuration."""

    probe_id: str
    name: str
    probe_type: str
    interval_seconds: float
    timeout_seconds: float
    healthy_threshold_ms: float
    degraded_threshold_ms: float
    enabled: bool
    tags: list[str]


class SLAStatusResponse(BaseModel):
    """Response model for SLA status."""

    name: str
    uptime_pct: float
    latency_p95_ms: float
    latency_p99_ms: float
    uptime_breach: bool
    latency_breach: bool
    error_budget_remaining_pct: float
    evaluation_period_hours: float


class MonitorStatusResponse(BaseModel):
    """Response model for monitor status."""

    running: bool
    overall_status: str
    total_probes: int
    enabled_probes: int
    by_status: dict[str, int]
    uptime_hours: float


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=MonitorStatusResponse)
async def get_monitor_status():
    """Get synthetic monitoring status."""
    monitor = get_synthetic_monitor()
    status = monitor.get_status()

    return MonitorStatusResponse(
        running=status["running"],
        overall_status=status["overall_status"],
        total_probes=status["total_probes"],
        enabled_probes=status["enabled_probes"],
        by_status=status["by_status"],
        uptime_hours=status["uptime_hours"],
    )


@router.post("/start")
async def start_monitoring():
    """Start background synthetic monitoring."""
    monitor = get_synthetic_monitor()
    await monitor.start()
    return {"status": "started", "message": "Synthetic monitoring started"}


@router.post("/stop")
async def stop_monitoring():
    """Stop background synthetic monitoring."""
    monitor = get_synthetic_monitor()
    await monitor.stop()
    return {"status": "stopped", "message": "Synthetic monitoring stopped"}


@router.get("/probes", response_model=list[ProbeConfigResponse])
async def list_probes():
    """List all registered probes."""
    monitor = get_synthetic_monitor()

    return [
        ProbeConfigResponse(
            probe_id=config.probe_id,
            name=config.name,
            probe_type=config.probe_type.value,
            interval_seconds=config.interval_seconds,
            timeout_seconds=config.timeout_seconds,
            healthy_threshold_ms=config.healthy_threshold_ms,
            degraded_threshold_ms=config.degraded_threshold_ms,
            enabled=config.enabled,
            tags=config.tags,
        )
        for config in monitor._probes.values()
    ]


@router.get("/probes/{probe_id}", response_model=ProbeConfigResponse)
async def get_probe(probe_id: str):
    """Get probe configuration."""
    monitor = get_synthetic_monitor()

    if probe_id not in monitor._probes:
        raise HTTPException(status_code=404, detail=f"Probe {probe_id} not found")

    config = monitor._probes[probe_id]
    return ProbeConfigResponse(
        probe_id=config.probe_id,
        name=config.name,
        probe_type=config.probe_type.value,
        interval_seconds=config.interval_seconds,
        timeout_seconds=config.timeout_seconds,
        healthy_threshold_ms=config.healthy_threshold_ms,
        degraded_threshold_ms=config.degraded_threshold_ms,
        enabled=config.enabled,
        tags=config.tags,
    )


@router.post("/probes/{probe_id}/run", response_model=ProbeResultResponse)
async def run_probe(probe_id: str):
    """Manually run a specific probe."""
    monitor = get_synthetic_monitor()

    result = await monitor.run_probe(probe_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Probe {probe_id} not found")

    return ProbeResultResponse(
        probe_id=result.probe_id,
        probe_name=result.probe_name,
        probe_type=result.probe_type.value,
        status=result.status.value,
        latency_ms=result.latency_ms,
        timestamp=result.timestamp,
        success=result.success,
        error_message=result.error_message,
    )


@router.post("/run-all", response_model=list[ProbeResultResponse])
async def run_all_probes():
    """Run all enabled probes."""
    monitor = get_synthetic_monitor()
    results = []

    for probe_id, config in monitor._probes.items():
        if config.enabled:
            result = await monitor.run_probe(probe_id)
            if result:
                results.append(
                    ProbeResultResponse(
                        probe_id=result.probe_id,
                        probe_name=result.probe_name,
                        probe_type=result.probe_type.value,
                        status=result.status.value,
                        latency_ms=result.latency_ms,
                        timestamp=result.timestamp,
                        success=result.success,
                        error_message=result.error_message,
                    )
                )

    return results


@router.get("/metrics", response_model=list[ProbeMetricsResponse])
async def get_all_metrics():
    """Get metrics for all probes."""
    monitor = get_synthetic_monitor()
    all_metrics = monitor.get_all_metrics()

    return [
        ProbeMetricsResponse(
            probe_id=m.probe_id,
            total_runs=m.total_runs,
            successful_runs=m.successful_runs,
            failed_runs=m.failed_runs,
            avg_latency_ms=m.avg_latency_ms,
            p95_latency_ms=m.p95_latency_ms,
            p99_latency_ms=m.p99_latency_ms,
            min_latency_ms=m.min_latency_ms
            if m.min_latency_ms != float("inf")
            else 0.0,
            max_latency_ms=m.max_latency_ms,
            current_status=m.current_status.value,
            uptime_pct=m.uptime_pct,
            last_run=m.last_run,
            last_success=m.last_success,
            last_failure=m.last_failure,
        )
        for m in all_metrics.values()
    ]


@router.get("/metrics/{probe_id}", response_model=ProbeMetricsResponse)
async def get_probe_metrics(probe_id: str):
    """Get metrics for a specific probe."""
    monitor = get_synthetic_monitor()
    metrics = monitor.get_probe_metrics(probe_id)

    if not metrics:
        raise HTTPException(status_code=404, detail=f"Metrics for {probe_id} not found")

    return ProbeMetricsResponse(
        probe_id=metrics.probe_id,
        total_runs=metrics.total_runs,
        successful_runs=metrics.successful_runs,
        failed_runs=metrics.failed_runs,
        avg_latency_ms=metrics.avg_latency_ms,
        p95_latency_ms=metrics.p95_latency_ms,
        p99_latency_ms=metrics.p99_latency_ms,
        min_latency_ms=metrics.min_latency_ms
        if metrics.min_latency_ms != float("inf")
        else 0.0,
        max_latency_ms=metrics.max_latency_ms,
        current_status=metrics.current_status.value,
        uptime_pct=metrics.uptime_pct,
        last_run=metrics.last_run,
        last_success=metrics.last_success,
        last_failure=metrics.last_failure,
    )


@router.get("/history/{probe_id}", response_model=list[ProbeResultResponse])
async def get_probe_history(probe_id: str, limit: int = 100):
    """Get execution history for a probe."""
    monitor = get_synthetic_monitor()

    if probe_id not in monitor._probes:
        raise HTTPException(status_code=404, detail=f"Probe {probe_id} not found")

    history = monitor.get_probe_history(probe_id, limit=limit)

    return [
        ProbeResultResponse(
            probe_id=r.probe_id,
            probe_name=r.probe_name,
            probe_type=r.probe_type.value,
            status=r.status.value,
            latency_ms=r.latency_ms,
            timestamp=r.timestamp,
            success=r.success,
            error_message=r.error_message,
        )
        for r in history
    ]


@router.get("/sla", response_model=SLAStatusResponse)
async def get_sla_status(sla_name: str = "default"):
    """Get SLA status."""
    monitor = get_synthetic_monitor()
    sla_status = monitor.get_sla_status(sla_name)

    if not sla_status:
        raise HTTPException(status_code=404, detail=f"SLA {sla_name} not found")

    return SLAStatusResponse(
        name=sla_status.name,
        uptime_pct=sla_status.uptime_pct,
        latency_p95_ms=sla_status.latency_p95_ms,
        latency_p99_ms=sla_status.latency_p99_ms,
        uptime_breach=sla_status.uptime_breach,
        latency_breach=sla_status.latency_breach,
        error_budget_remaining_pct=sla_status.error_budget_remaining_pct,
        evaluation_period_hours=sla_status.evaluation_period_hours,
    )


@router.get("/summary")
async def get_monitoring_summary():
    """Get comprehensive monitoring summary."""
    monitor = get_synthetic_monitor()
    return monitor.get_summary()


@router.get("/probe-types")
async def list_probe_types():
    """List all probe types and statuses."""
    return {
        "probe_types": [t.value for t in ProbeType],
        "probe_statuses": [s.value for s in ProbeStatus],
    }


@router.get("/health")
async def get_monitoring_health():
    """Get synthetic monitoring health status."""
    monitor = get_synthetic_monitor()
    status = monitor.get_status()
    sla = monitor.get_sla_status()

    # Determine health
    if status["overall_status"] == "healthy" and (not sla or not sla.uptime_breach):
        health = "healthy"
    elif status["overall_status"] == "degraded" or (sla and sla.latency_breach):
        health = "degraded"
    else:
        health = "unhealthy"

    return {
        "health": health,
        "monitoring_running": status["running"],
        "overall_status": status["overall_status"],
        "probes_healthy": status["by_status"].get("healthy", 0),
        "probes_degraded": status["by_status"].get("degraded", 0),
        "probes_unhealthy": status["by_status"].get("unhealthy", 0),
        "sla_status": {
            "uptime_pct": sla.uptime_pct if sla else None,
            "error_budget_remaining_pct": sla.error_budget_remaining_pct
            if sla
            else None,
            "breaches": sla.uptime_breach or sla.latency_breach if sla else False,
        },
    }
