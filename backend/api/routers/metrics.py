"""
Prometheus Metrics Router - P0-5

FastAPI router for exposing Prometheus metrics via GET /metrics endpoint.
Includes both orchestrator metrics and cache system metrics.
"""

from fastapi import APIRouter, Response
from loguru import logger
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Import metrics module (will be created in orchestrator/api/metrics.py)
try:
    from orchestrator.api.metrics import get_metrics, initialize_metrics
    METRICS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Orchestrator metrics module not available")
    METRICS_AVAILABLE = False


router = APIRouter()


@router.get("/metrics")
async def prometheus_metrics():
    """
    GET /metrics - Prometheus metrics endpoint
    
    Returns system metrics in Prometheus text exposition format.
    
    Metrics included:
    - mcp_tasks_enqueued_total (counter)
    - mcp_tasks_completed_total (counter)
    - mcp_tasks_failed_total (counter)
    - mcp_ack_failures_total (counter)
    - mcp_worker_restarts_total (counter)
    - mcp_ack_success_rate (gauge, 0.0-1.0)
    - mcp_consumer_group_lag (gauge)
    - mcp_queue_depth (gauge)
    - mcp_active_workers (gauge)
    - mcp_task_latency_seconds_* (histogram per task type)
    
    Example response:
    ```
    # HELP mcp_tasks_completed_total Total number of tasks completed successfully
    # TYPE mcp_tasks_completed_total counter
    mcp_tasks_completed_total 1523
    
    # HELP mcp_ack_success_rate ACK success rate (0.0 to 1.0)
    # TYPE mcp_ack_success_rate gauge
    mcp_ack_success_rate 0.9987
    ```
    
    Returns:
        Response with Prometheus text format (Content-Type: text/plain)
    """
    if not METRICS_AVAILABLE:
        return Response(
            content="# Metrics module not available\n",
            media_type="text/plain; version=0.0.4"
        )
    
    try:
        metrics = get_metrics()
        
        # Export metrics in Prometheus format
        prometheus_text = await metrics.export_prometheus()
        
        # Return with proper content type
        return Response(
            content=prometheus_text,
            media_type="text/plain; version=0.0.4"
        )
    
    except Exception as e:
        logger.error(f"❌ Failed to export Prometheus metrics: {e}")
        return Response(
            content=f"# Error exporting metrics: {str(e)}\n",
            media_type="text/plain; version=0.0.4",
            status_code=500
        )


@router.get("/metrics/cache")
async def cache_metrics_prometheus():
    """
    GET /metrics/cache - Prometheus cache metrics endpoint
    
    Returns cache system metrics in Prometheus text exposition format.
    
    Metrics included:
    - cache_hits_total: Total cache hits (L1, L2)
    - cache_misses_total: Total cache misses
    - cache_operations_total: Cache operations by type
    - cache_hit_rate: Current hit rate (0-1)
    - cache_size: Current cache size (L1, L2)
    - cache_evictions_total: Total evictions
    - cache_l2_errors_total: Total L2 errors
    - cache_operation_duration_seconds: Operation latency
    
    Example response:
    ```
    # HELP cache_hits_total Total number of cache hits
    # TYPE cache_hits_total counter
    cache_hits_total{level="l1"} 5420
    cache_hits_total{level="l2"} 1234
    
    # HELP cache_hit_rate Current cache hit rate
    # TYPE cache_hit_rate gauge
    cache_hit_rate{level="overall"} 0.958
    ```
    
    Returns:
        Response with Prometheus text format
    """
    try:
        # Generate Prometheus metrics from cache system
        metrics_output = generate_latest()
        
        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST
        )
    
    except Exception as e:
        logger.error(f"❌ Failed to export cache metrics: {e}")
        return Response(
            content=f"# Error exporting cache metrics: {str(e)}\n",
            media_type="text/plain; version=0.0.4",
            status_code=500
        )


@router.get("/metrics/health")
async def metrics_health():
    """
    GET /metrics/health - Health check for metrics system
    
    Returns:
        Dict with metrics system status
    """
    if not METRICS_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "Metrics module not available"
        }
    
    try:
        metrics = get_metrics()
        
        return {
            "status": "healthy",
            "connected": metrics.queue is not None,
            "counters": len(metrics.counters),
            "gauges": len(metrics.gauges),
            "histograms": len(metrics.latency_histogram)
        }
    
    except Exception as e:
        logger.error(f"❌ Metrics health check failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
