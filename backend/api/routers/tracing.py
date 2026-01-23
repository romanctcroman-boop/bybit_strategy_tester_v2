"""
Tracing Monitoring Router
Provides API endpoints for monitoring OpenTelemetry traces.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.middleware.opentelemetry_tracing import (
    InMemorySpanExporter,
    get_tracing_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tracing", tags=["Tracing"])


# ============================================================================
# Response Models
# ============================================================================


class TracingMetrics(BaseModel):
    """Tracing metrics summary."""

    total_traces: int
    total_spans: int
    active_traces: int
    error_count: int
    error_rate: float
    sampling_rate: float
    enabled: bool


class SpanInfo(BaseModel):
    """Information about a single span."""

    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: str
    end_time: Optional[str]
    duration_ms: float
    status: str
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]


class TraceSummary(BaseModel):
    """Summary of trace storage."""

    total_traces: int
    total_spans: int
    traces: Dict[str, Any]


class TracingStatus(BaseModel):
    """Overall tracing status."""

    enabled: bool
    service_name: str
    sampling_rate: float
    metrics: TracingMetrics
    exporter_count: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=TracingStatus)
async def get_tracing_status():
    """
    Get overall tracing status and configuration.

    Returns:
        Current tracing configuration and metrics
    """
    try:
        manager = get_tracing_manager()
        metrics = manager.get_metrics()

        return TracingStatus(
            enabled=manager.enabled,
            service_name=manager.service_name,
            sampling_rate=manager.sampling_rate,
            metrics=TracingMetrics(**metrics),
            exporter_count=len(manager.exporters),
        )
    except Exception as e:
        logger.error(f"Error getting tracing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=TracingMetrics)
async def get_tracing_metrics():
    """
    Get tracing metrics.

    Returns:
        Metrics including total traces, spans, and error rates
    """
    try:
        manager = get_tracing_manager()
        metrics = manager.get_metrics()

        return TracingMetrics(**metrics)
    except Exception as e:
        logger.error(f"Error getting tracing metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spans", response_model=List[SpanInfo])
async def get_spans(
    trace_id: Optional[str] = Query(None, description="Filter by trace ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of spans"),
):
    """
    Get stored spans from in-memory exporter.

    Args:
        trace_id: Optional trace ID to filter by
        limit: Maximum number of spans to return

    Returns:
        List of span information
    """
    try:
        manager = get_tracing_manager()

        # Find in-memory exporter
        memory_exporter = None
        for exporter in manager.exporters:
            if isinstance(exporter, InMemorySpanExporter):
                memory_exporter = exporter
                break

        if not memory_exporter:
            return []

        spans_data = memory_exporter.get_spans(trace_id=trace_id)
        spans_data = spans_data[-limit:]  # Get last N spans

        return [SpanInfo(**span) for span in spans_data]
    except Exception as e:
        logger.error(f"Error getting spans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/summary", response_model=TraceSummary)
async def get_trace_summary():
    """
    Get summary of all stored traces.

    Returns:
        Summary including trace counts and durations
    """
    try:
        manager = get_tracing_manager()

        # Find in-memory exporter
        memory_exporter = None
        for exporter in manager.exporters:
            if isinstance(exporter, InMemorySpanExporter):
                memory_exporter = exporter
                break

        if not memory_exporter:
            return TraceSummary(total_traces=0, total_spans=0, traces={})

        summary = memory_exporter.get_trace_summary()
        return TraceSummary(**summary)
    except Exception as e:
        logger.error(f"Error getting trace summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}", response_model=List[SpanInfo])
async def get_trace_spans(trace_id: str):
    """
    Get all spans for a specific trace.

    Args:
        trace_id: The trace ID to look up

    Returns:
        All spans belonging to the trace
    """
    try:
        manager = get_tracing_manager()

        # Find in-memory exporter
        memory_exporter = None
        for exporter in manager.exporters:
            if isinstance(exporter, InMemorySpanExporter):
                memory_exporter = exporter
                break

        if not memory_exporter:
            raise HTTPException(
                status_code=404, detail="No in-memory exporter configured"
            )

        spans_data = memory_exporter.get_spans(trace_id=trace_id)

        if not spans_data:
            raise HTTPException(
                status_code=404, detail=f"No spans found for trace {trace_id}"
            )

        return [SpanInfo(**span) for span in spans_data]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trace spans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_tracing_config(
    enabled: Optional[bool] = Query(None, description="Enable/disable tracing"),
    sampling_rate: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Sampling rate (0.0 to 1.0)"
    ),
):
    """
    Update tracing configuration.

    Args:
        enabled: Whether to enable tracing
        sampling_rate: Rate at which to sample requests

    Returns:
        Updated configuration
    """
    try:
        manager = get_tracing_manager()

        if enabled is not None:
            manager.enabled = enabled

        if sampling_rate is not None:
            manager.sampling_rate = sampling_rate

        return {
            "success": True,
            "message": "Tracing configuration updated",
            "config": {
                "enabled": manager.enabled,
                "sampling_rate": manager.sampling_rate,
            },
        }
    except Exception as e:
        logger.error(f"Error updating tracing config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/spans")
async def clear_spans():
    """
    Clear all stored spans from in-memory exporter.

    Returns:
        Confirmation of cleared spans
    """
    try:
        manager = get_tracing_manager()

        # Find in-memory exporter
        memory_exporter = None
        for exporter in manager.exporters:
            if isinstance(exporter, InMemorySpanExporter):
                memory_exporter = exporter
                break

        if not memory_exporter:
            return {"success": False, "message": "No in-memory exporter configured"}

        span_count = len(memory_exporter.spans)
        memory_exporter.spans.clear()

        return {
            "success": True,
            "message": f"Cleared {span_count} spans",
            "cleared_count": span_count,
        }
    except Exception as e:
        logger.error(f"Error clearing spans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    Get tracing metrics in Prometheus format.

    Returns:
        Prometheus-formatted metrics text
    """
    try:
        manager = get_tracing_manager()
        metrics = manager.get_metrics()

        lines = [
            "# HELP tracing_total_traces Total number of traces created",
            "# TYPE tracing_total_traces counter",
            f"tracing_total_traces {metrics['total_traces']}",
            "",
            "# HELP tracing_total_spans Total number of spans created",
            "# TYPE tracing_total_spans counter",
            f"tracing_total_spans {metrics['total_spans']}",
            "",
            "# HELP tracing_active_traces Number of currently active traces",
            "# TYPE tracing_active_traces gauge",
            f"tracing_active_traces {metrics['active_traces']}",
            "",
            "# HELP tracing_error_count Total number of error spans",
            "# TYPE tracing_error_count counter",
            f"tracing_error_count {metrics['error_count']}",
            "",
            "# HELP tracing_error_rate Error rate percentage",
            "# TYPE tracing_error_rate gauge",
            f"tracing_error_rate {metrics['error_rate']:.2f}",
            "",
            "# HELP tracing_enabled Whether tracing is enabled (1=yes, 0=no)",
            "# TYPE tracing_enabled gauge",
            f"tracing_enabled {1 if metrics['enabled'] else 0}",
            "",
            "# HELP tracing_sampling_rate Current sampling rate",
            "# TYPE tracing_sampling_rate gauge",
            f"tracing_sampling_rate {metrics['sampling_rate']}",
        ]

        return {"prometheus_format": "\n".join(lines)}
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
