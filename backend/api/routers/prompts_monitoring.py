"""
Prompts Monitoring API Router

Provides REST API for monitoring AI prompt system:
- GET /api/v1/prompts/monitoring/dashboard - Full dashboard
- GET /api/v1/prompts/monitoring/validation - Validation stats
- GET /api/v1/prompts/monitoring/logging - Logging stats
- GET /api/v1/prompts/monitoring/cache - Cache stats
- GET /api/v1/prompts/monitoring/costs - Cost breakdown
- GET /api/v1/prompts/monitoring/trends - Performance trends
- POST /api/v1/prompts/monitoring/export - Export dashboard
"""

from fastapi import APIRouter, HTTPException, Query

from backend.monitoring.prompts_monitor import PromptsMonitor

router = APIRouter(prefix="/api/v1/prompts/monitoring", tags=["Prompts Monitoring"])

# Lazy initialization
_monitor: PromptsMonitor | None = None


def get_monitor() -> PromptsMonitor:
    """Get or create monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PromptsMonitor()
    return _monitor


@router.get("/dashboard")
def get_dashboard(period_hours: int = Query(default=24, ge=1, le=720)) -> dict:
    """
    Get full monitoring dashboard.

    Args:
        period_hours: Period for statistics (1-720 hours)

    Returns:
        Complete dashboard metrics
    """
    monitor = get_monitor()
    metrics = monitor.get_dashboard(period_hours)

    return {
        "timestamp": metrics.timestamp,
        "period_hours": metrics.period_hours,
        "validation": {
            "total_prompts": metrics.total_prompts,
            "validated_prompts": metrics.validated_prompts,
            "failed_validations": metrics.failed_validations,
            "validation_success_rate": metrics.validation_success_rate,
            "injection_attempts_blocked": metrics.injection_attempts_blocked,
        },
        "logging": {
            "total_logged": metrics.total_logged,
            "total_tokens": metrics.total_tokens,
            "total_cost_usd": metrics.total_cost_usd,
            "avg_duration_ms": metrics.avg_duration_ms,
        },
        "cache": {
            "cache_size": metrics.cache_size,
            "cache_hits": metrics.cache_hits,
            "cache_misses": metrics.cache_misses,
            "cache_hit_rate": metrics.cache_hit_rate,
        },
        "by_agent": metrics.by_agent,
        "by_task": metrics.by_task,
    }


@router.get("/validation")
def get_validation_stats(period_hours: int = Query(default=24, ge=1, le=720)) -> dict:
    """
    Get validation statistics.

    Args:
        period_hours: Period for statistics

    Returns:
        Validation stats
    """
    monitor = get_monitor()
    return monitor.get_validation_stats(period_hours)


@router.get("/logging")
def get_logging_stats(period_hours: int = Query(default=24, ge=1, le=720)) -> dict:
    """
    Get logging statistics.

    Args:
        period_hours: Period for statistics

    Returns:
        Logging stats
    """
    monitor = get_monitor()
    return monitor.get_logging_stats(period_hours)


@router.get("/cache")
def get_cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Cache stats
    """
    monitor = get_monitor()
    return monitor.get_cache_stats()


@router.get("/costs")
def get_cost_breakdown(period_hours: int = Query(default=24, ge=1, le=720)) -> dict:
    """
    Get cost breakdown by agent and task.

    Args:
        period_hours: Period for statistics

    Returns:
        Cost breakdown with projections
    """
    monitor = get_monitor()
    return monitor.get_cost_breakdown(period_hours)


@router.get("/trends")
def get_performance_trends(
    period_hours: int = Query(default=24, ge=1, le=720),
    intervals: int = Query(default=24, ge=1, le=100),
) -> dict:
    """
    Get performance trends over time.

    Args:
        period_hours: Total period
        intervals: Number of intervals

    Returns:
        Time series data
    """
    monitor = get_monitor()
    return monitor.get_performance_trends(period_hours, intervals)


@router.post("/export")
def export_dashboard(
    output_path: str = Query(default="data/prompts_dashboard.json"),
    period_hours: int = Query(default=24, ge=1, le=720),
) -> dict:
    """
    Export dashboard to JSON file.

    Args:
        output_path: Output file path
        period_hours: Period for statistics

    Returns:
        Export status
    """
    try:
        monitor = get_monitor()
        file_path = monitor.export_dashboard(output_path, period_hours)

        return {
            "success": True,
            "file_path": file_path,
            "period_hours": period_hours,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@router.get("/health")
def monitoring_health() -> dict:
    """
    Get monitoring service health status.

    Returns:
        Health status
    """
    try:
        monitor = get_monitor()
        metrics = monitor.get_dashboard(period_hours=1)

        return {
            "status": "healthy",
            "monitor_initialized": True,
            "metrics_available": True,
            "total_prompts": metrics.total_prompts,
            "cache_hit_rate": metrics.cache_hit_rate,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }
