"""
Cache Warming API Router.

Provides REST API endpoints for cache warming management.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.cache_warming import (
    WarmingPriority,
    get_cache_warming_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cache-warming", tags=["Cache Warming"])


# ============================================================================
# Request/Response Models
# ============================================================================


class AddTargetRequest(BaseModel):
    """Add warming target request."""

    symbol: str = Field(..., description="Trading pair symbol")
    interval: str = Field(..., description="Candle interval")
    priority: str = Field("medium", description="Priority: critical, high, medium, low")


class TargetResponse(BaseModel):
    """Warming target response."""

    symbol: str
    interval: str
    priority: str
    enabled: bool
    last_warmed: str | None
    warm_count: int
    failure_count: int
    avg_warm_time_ms: float


class WarmingResultResponse(BaseModel):
    """Warming result response."""

    symbol: str
    interval: str
    status: str
    candles_loaded: int
    duration_ms: float
    error_message: str | None
    timestamp: str


class WarmingMetricsResponse(BaseModel):
    """Warming metrics response."""

    total_warms: int
    successful_warms: int
    failed_warms: int
    skipped_warms: int
    total_candles_loaded: int
    total_warm_time_ms: float
    avg_warm_time_ms: float
    cache_hit_rate: float
    target_hit_rate: float
    last_full_warm: str | None
    warm_queue_size: int
    active_warming: bool


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""

    hits: int
    misses: int
    evictions: int
    hit_rate: float
    target_hit_rate: float
    hit_rate_gap: float


class StatusResponse(BaseModel):
    """Service status response."""

    running: bool
    total_targets: int
    enabled_targets: int
    stale_targets: int
    metrics: dict[str, Any]
    cache_stats: dict[str, Any]


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    running: bool
    cache_hit_rate: float
    target_hit_rate: float
    hit_rate_ok: bool
    failures_ok: bool
    checks: dict[str, bool]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get cache warming service status."""
    try:
        service = get_cache_warming_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Get cache warming service health."""
    try:
        service = get_cache_warming_service()
        return service.get_health()
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=WarmingMetricsResponse)
async def get_metrics():
    """Get warming metrics."""
    try:
        service = get_cache_warming_service()
        metrics = service.get_metrics()
        return WarmingMetricsResponse(
            total_warms=metrics.total_warms,
            successful_warms=metrics.successful_warms,
            failed_warms=metrics.failed_warms,
            skipped_warms=metrics.skipped_warms,
            total_candles_loaded=metrics.total_candles_loaded,
            total_warm_time_ms=metrics.total_warm_time_ms,
            avg_warm_time_ms=(
                metrics.total_warm_time_ms / metrics.total_warms
                if metrics.total_warms > 0
                else 0
            ),
            cache_hit_rate=metrics.cache_hit_rate,
            target_hit_rate=95.0,
            last_full_warm=metrics.last_full_warm.isoformat()
            if metrics.last_full_warm
            else None,
            warm_queue_size=metrics.warm_queue_size,
            active_warming=metrics.active_warming,
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics."""
    try:
        service = get_cache_warming_service()
        return service.get_cache_stats()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/targets", response_model=list[TargetResponse])
async def get_targets(
    priority: str | None = Query(None, description="Filter by priority"),
    enabled_only: bool = Query(True, description="Only enabled targets"),
):
    """Get warming targets."""
    try:
        service = get_cache_warming_service()
        prio = WarmingPriority(priority) if priority else None
        targets = service.get_targets(priority=prio, enabled_only=enabled_only)
        return [
            TargetResponse(
                symbol=t.symbol,
                interval=t.interval,
                priority=t.priority.value,
                enabled=t.enabled,
                last_warmed=t.last_warmed.isoformat() if t.last_warmed else None,
                warm_count=t.warm_count,
                failure_count=t.failure_count,
                avg_warm_time_ms=t.avg_warm_time_ms,
            )
            for t in targets
        ]
    except Exception as e:
        logger.error(f"Error getting targets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/targets", response_model=TargetResponse, status_code=201)
async def add_target(request: AddTargetRequest):
    """Add a warming target."""
    try:
        service = get_cache_warming_service()
        priority = WarmingPriority(request.priority)
        target = service.add_target(request.symbol, request.interval, priority)
        return TargetResponse(
            symbol=target.symbol,
            interval=target.interval,
            priority=target.priority.value,
            enabled=target.enabled,
            last_warmed=target.last_warmed.isoformat() if target.last_warmed else None,
            warm_count=target.warm_count,
            failure_count=target.failure_count,
            avg_warm_time_ms=target.avg_warm_time_ms,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/targets/{symbol}/{interval}")
async def remove_target(symbol: str, interval: str):
    """Remove a warming target."""
    try:
        service = get_cache_warming_service()
        removed = service.remove_target(symbol, interval)
        if not removed:
            raise HTTPException(
                status_code=404, detail=f"Target {symbol}:{interval} not found"
            )
        return {"message": f"Target {symbol}:{interval} removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/targets/{symbol}/{interval}/enable")
async def enable_target(symbol: str, interval: str):
    """Enable a warming target."""
    try:
        service = get_cache_warming_service()
        enabled = service.enable_target(symbol, interval, enabled=True)
        if not enabled:
            raise HTTPException(
                status_code=404, detail=f"Target {symbol}:{interval} not found"
            )
        return {"message": f"Target {symbol}:{interval} enabled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/targets/{symbol}/{interval}/disable")
async def disable_target(symbol: str, interval: str):
    """Disable a warming target."""
    try:
        service = get_cache_warming_service()
        disabled = service.enable_target(symbol, interval, enabled=False)
        if not disabled:
            raise HTTPException(
                status_code=404, detail=f"Target {symbol}:{interval} not found"
            )
        return {"message": f"Target {symbol}:{interval} disabled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warm/{symbol}/{interval}", response_model=WarmingResultResponse)
async def warm_single(symbol: str, interval: str):
    """Warm a single target."""
    try:
        service = get_cache_warming_service()
        result = await service.warm_target(symbol, interval)
        return WarmingResultResponse(
            symbol=result.symbol,
            interval=result.interval,
            status=result.status.value,
            candles_loaded=result.candles_loaded,
            duration_ms=result.duration_ms,
            error_message=result.error_message,
            timestamp=result.timestamp.isoformat(),
        )
    except Exception as e:
        logger.error(f"Error warming target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warm-all", response_model=list[WarmingResultResponse])
async def warm_all(
    priority: str | None = Query(None, description="Only warm this priority"),
    force: bool = Query(False, description="Force warm even if recently warmed"),
):
    """Warm all targets."""
    try:
        service = get_cache_warming_service()
        prio = WarmingPriority(priority) if priority else None
        results = await service.warm_all(priority=prio, force=force)
        return [
            WarmingResultResponse(
                symbol=r.symbol,
                interval=r.interval,
                status=r.status.value,
                candles_loaded=r.candles_loaded,
                duration_ms=r.duration_ms,
                error_message=r.error_message,
                timestamp=r.timestamp.isoformat(),
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error warming all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warm-critical", response_model=list[WarmingResultResponse])
async def warm_critical():
    """Warm only critical targets (BTC, ETH)."""
    try:
        service = get_cache_warming_service()
        results = await service.warm_critical()
        return [
            WarmingResultResponse(
                symbol=r.symbol,
                interval=r.interval,
                status=r.status.value,
                candles_loaded=r.candles_loaded,
                duration_ms=r.duration_ms,
                error_message=r.error_message,
                timestamp=r.timestamp.isoformat(),
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error warming critical: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results", response_model=list[WarmingResultResponse])
async def get_results(
    limit: int = Query(100, ge=1, le=1000, description="Number of results to return"),
):
    """Get recent warming results."""
    try:
        service = get_cache_warming_service()
        results = service.get_results(limit=limit)
        return [
            WarmingResultResponse(
                symbol=r.symbol,
                interval=r.interval,
                status=r.status.value,
                candles_loaded=r.candles_loaded,
                duration_ms=r.duration_ms,
                error_message=r.error_message,
                timestamp=r.timestamp.isoformat(),
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_service():
    """Start background warming service."""
    try:
        service = get_cache_warming_service()
        await service.start()
        return {"status": "started"}
    except Exception as e:
        logger.error(f"Error starting service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_service():
    """Stop background warming service."""
    try:
        service = get_cache_warming_service()
        await service.stop()
        return {"status": "stopped"}
    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-hit")
async def record_cache_hit():
    """Record a cache hit (for tracking purposes)."""
    service = get_cache_warming_service()
    service.record_cache_hit()
    return {"recorded": "hit"}


@router.post("/record-miss")
async def record_cache_miss():
    """Record a cache miss (for tracking purposes)."""
    service = get_cache_warming_service()
    service.record_cache_miss()
    return {"recorded": "miss"}
