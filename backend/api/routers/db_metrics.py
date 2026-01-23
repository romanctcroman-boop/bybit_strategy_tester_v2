"""
Database Metrics API Router.

Provides REST API for database performance monitoring.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.db_metrics import (
    QueryType,
    get_db_metrics_service,
)

router = APIRouter(prefix="/api/v1/db-metrics")


# ============================================================
# Response Models
# ============================================================


class QueryMetricResponse(BaseModel):
    """Response for a query metric."""

    query_id: str
    query_type: str
    table: Optional[str]
    duration_ms: float
    status: str
    timestamp: str
    rows_affected: int
    rows_returned: int
    caller: Optional[str]


class QueryPatternResponse(BaseModel):
    """Response for a query pattern."""

    query_hash: str
    sample_query: str
    query_type: str
    table: Optional[str]
    execution_count: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    total_duration_ms: float
    error_count: int
    error_rate_pct: float
    last_executed: Optional[str]


class RecommendationResponse(BaseModel):
    """Response for a recommendation."""

    priority: str
    category: str
    message: str
    suggestion: str


# ============================================================
# API Endpoints
# ============================================================


@router.get("/status")
async def get_service_status():
    """Get database metrics service status."""
    service = get_db_metrics_service()
    return service.get_status()


@router.get("/stats")
async def get_query_stats():
    """Get query statistics."""
    service = get_db_metrics_service()
    return service.get_stats()


@router.get("/pool")
async def get_pool_metrics():
    """Get connection pool metrics."""
    service = get_db_metrics_service()
    return service.get_pool_metrics()


@router.get("/slow-queries", response_model=list[QueryMetricResponse])
async def get_slow_queries(
    limit: int = 50,
    min_duration_ms: Optional[float] = None,
):
    """Get recent slow queries."""
    service = get_db_metrics_service()
    queries = service.get_slow_queries(limit=limit, min_duration_ms=min_duration_ms)
    return [QueryMetricResponse(**q) for q in queries]


@router.get("/patterns", response_model=list[QueryPatternResponse])
async def get_query_patterns(
    order_by: str = "execution_count",
    limit: int = 20,
):
    """Get query patterns."""
    service = get_db_metrics_service()
    patterns = service.get_query_patterns(order_by=order_by, limit=limit)
    return [QueryPatternResponse(**p) for p in patterns]


@router.get("/table-stats")
async def get_table_stats():
    """Get query counts by table."""
    service = get_db_metrics_service()
    return service.get_table_stats()


@router.get("/type-stats")
async def get_type_stats():
    """Get query counts by type."""
    service = get_db_metrics_service()
    return service.get_type_stats()


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def get_recommendations():
    """Get performance recommendations."""
    service = get_db_metrics_service()
    recommendations = service.get_recommendations()
    return [RecommendationResponse(**r) for r in recommendations]


@router.post("/reset")
async def reset_metrics():
    """Reset all database metrics."""
    service = get_db_metrics_service()
    service.reset_stats()
    return {"status": "reset"}


@router.get("/summary")
async def get_db_metrics_summary():
    """Get comprehensive database metrics summary."""
    service = get_db_metrics_service()

    stats = service.get_stats()
    pool = service.get_pool_metrics()
    recommendations = service.get_recommendations()
    slow_queries = service.get_slow_queries(limit=5)
    top_patterns = service.get_query_patterns(order_by="execution_count", limit=5)

    return {
        "health": "healthy" if len(recommendations) == 0 else "needs_attention",
        "total_queries": stats["total_queries"],
        "success_rate_pct": round(stats["success_rate_pct"], 2),
        "slow_query_rate_pct": round(stats["slow_query_rate_pct"], 2),
        "avg_duration_ms": stats["avg_duration_ms"],
        "pool_utilization_pct": round(pool["utilization_pct"], 2),
        "active_connections": pool["active_connections"],
        "connection_timeouts": pool["connection_timeouts"],
        "recommendations_count": len(recommendations),
        "top_recommendations": recommendations[:3],
        "recent_slow_queries": len(slow_queries),
        "query_patterns_count": stats["query_patterns_count"],
        "top_patterns": [
            {
                "table": p["table"],
                "type": p["query_type"],
                "count": p["execution_count"],
                "avg_ms": p["avg_duration_ms"],
            }
            for p in top_patterns
        ],
    }


@router.get("/query-types")
async def list_query_types():
    """List available query types."""
    return [{"value": qt.value, "description": qt.name} for qt in QueryType]
