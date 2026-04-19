"""
Agent Monitoring API Router.

Exposes SystemMonitor metrics for the AI Pipeline frontend:
- GET /metrics — aggregated monitoring data
- GET /metrics/{metric_name}/history — raw history for a metric
- POST /reset — reset monitoring data (admin)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/monitoring",
    tags=["Agent Monitoring"],
    responses={
        404: {"description": "Metric not found"},
        500: {"description": "Internal server error"},
    },
)


class MonitoringMetricsResponse(BaseModel):
    """Aggregated monitoring metrics."""

    metrics: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class MetricHistoryResponse(BaseModel):
    """Raw history for a single metric."""

    metric_name: str
    entries: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class ResetResponse(BaseModel):
    """Response after resetting monitoring data."""

    success: bool
    message: str


@router.get("/metrics", response_model=MonitoringMetricsResponse)
async def get_monitoring_metrics() -> MonitoringMetricsResponse:
    """
    Get aggregated monitoring metrics for all LLM agents.

    Returns:
    - **metrics**: success_rate, avg generation time, token usage, costs, etc.
    - **alerts**: recent alert events
    """
    try:
        from backend.agents.monitoring.system_monitor import get_system_monitor

        monitor = get_system_monitor()
        report = monitor.get_full_report()

        return MonitoringMetricsResponse(
            metrics=report["metrics"],
            alerts=report["alerts"],
        )
    except Exception as e:
        logger.error(f"Failed to get monitoring metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}/history", response_model=MetricHistoryResponse)
async def get_metric_history(
    metric_name: str,
    last_n: int = 100,
) -> MetricHistoryResponse:
    """
    Get raw history entries for a specific metric.

    - **metric_name**: One of agent_success_rate, strategy_generation_time,
      backtest_duration, llm_token_usage, api_costs, strategy_performance, system_errors
    - **last_n**: Number of most recent entries (default 100)
    """
    try:
        from backend.agents.monitoring.system_monitor import (
            SystemMonitor,
            get_system_monitor,
        )

        if metric_name not in SystemMonitor.METRICS_TO_TRACK:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown metric: {metric_name}. Valid metrics: {SystemMonitor.METRICS_TO_TRACK}",
            )

        monitor = get_system_monitor()
        entries = monitor.get_metrics_history(metric_name, last_n=min(last_n, 1000))

        return MetricHistoryResponse(
            metric_name=metric_name,
            entries=entries,
            count=len(entries),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metric history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", response_model=ResetResponse)
async def reset_monitoring() -> ResetResponse:
    """
    Reset all monitoring data. Use with caution.
    """
    try:
        from backend.agents.monitoring.system_monitor import get_system_monitor

        monitor = get_system_monitor()
        monitor.reset()
        logger.info("Monitoring data reset by API request")

        return ResetResponse(success=True, message="Monitoring data has been reset")
    except Exception as e:
        logger.error(f"Failed to reset monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
