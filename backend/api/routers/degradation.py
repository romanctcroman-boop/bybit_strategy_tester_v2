"""
Graceful Degradation Router
Provides API endpoints for monitoring and managing degradation status.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.graceful_degradation import (
    FallbackType,
    ServiceStatus,
    get_degradation_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/degradation", tags=["Degradation"])


# ============================================================================
# Response Models
# ============================================================================


class ServiceStatusResponse(BaseModel):
    """Status of a single service."""

    name: str
    status: str
    success_rate: float
    failure_count: int
    success_count: int
    degraded_since: Optional[str] = None
    error_message: Optional[str] = None


class CacheStatsResponse(BaseModel):
    """Cache statistics."""

    entries: int
    hits: int
    misses: int
    hit_rate: float
    evictions: int
    max_entries: int
    default_ttl: int


class SystemStatusResponse(BaseModel):
    """Overall system degradation status."""

    overall_status: str
    services: Dict[str, ServiceStatusResponse]
    cache_stats: CacheStatsResponse
    fallback_handlers: List[str]
    static_fallbacks: List[str]
    timestamp: str


class CacheEntryInfo(BaseModel):
    """Information about a cache entry."""

    key: str
    source: str
    created_at: str
    expires_at: str
    age_seconds: float
    is_expired: bool
    access_count: int
    last_accessed: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=SystemStatusResponse)
async def get_degradation_status():
    """
    Get overall system degradation status.

    Returns:
        Comprehensive status including all services, cache stats, and fallbacks
    """
    try:
        manager = get_degradation_manager()
        report = manager.get_status_report()

        services = {}
        for name, svc in report["services"].items():
            services[name] = ServiceStatusResponse(
                name=name,
                status=svc["status"],
                success_rate=svc["success_rate"],
                failure_count=svc["failure_count"],
                success_count=svc["success_count"],
                degraded_since=svc["degraded_since"],
                error_message=svc["error_message"],
            )

        return SystemStatusResponse(
            overall_status=report["overall_status"],
            services=services,
            cache_stats=CacheStatsResponse(**report["cache_stats"]),
            fallback_handlers=report["fallback_handlers"],
            static_fallbacks=report["static_fallbacks"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Error getting degradation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=List[ServiceStatusResponse])
async def list_services():
    """
    List all registered services with their health status.

    Returns:
        List of service status information
    """
    try:
        manager = get_degradation_manager()
        services = []

        for name, svc in manager.services.items():
            services.append(
                ServiceStatusResponse(
                    name=name,
                    status=svc.status.value,
                    success_rate=round(svc.success_rate, 2),
                    failure_count=svc.failure_count,
                    success_count=svc.success_count,
                    degraded_since=svc.degraded_since.isoformat()
                    if svc.degraded_since
                    else None,
                    error_message=svc.error_message,
                )
            )

        return services
    except Exception as e:
        logger.error(f"Error listing services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{service_name}", response_model=ServiceStatusResponse)
async def get_service_status(service_name: str):
    """
    Get status of a specific service.

    Args:
        service_name: Name of the service

    Returns:
        Service status information
    """
    try:
        manager = get_degradation_manager()
        svc = manager.get_service(service_name)

        if not svc:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{service_name}' not found",
            )

        return ServiceStatusResponse(
            name=svc.name,
            status=svc.status.value,
            success_rate=round(svc.success_rate, 2),
            failure_count=svc.failure_count,
            success_count=svc.success_count,
            degraded_since=svc.degraded_since.isoformat()
            if svc.degraded_since
            else None,
            error_message=svc.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """
    Get cache statistics.

    Returns:
        Cache hit/miss rates, entries count, etc.
    """
    try:
        manager = get_degradation_manager()
        stats = manager.cache.get_stats()
        return CacheStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/entries", response_model=List[CacheEntryInfo])
async def list_cache_entries():
    """
    List all cache entries with metadata.

    Returns:
        List of cache entries
    """
    try:
        manager = get_degradation_manager()
        entries = []

        for key, entry in manager.cache._cache.items():
            entries.append(
                CacheEntryInfo(
                    key=key,
                    source=entry.source,
                    created_at=entry.created_at.isoformat(),
                    expires_at=entry.expires_at.isoformat(),
                    age_seconds=round(entry.age_seconds, 2),
                    is_expired=entry.is_expired,
                    access_count=entry.access_count,
                    last_accessed=entry.last_accessed.isoformat()
                    if entry.last_accessed
                    else None,
                )
            )

        return entries
    except Exception as e:
        logger.error(f"Error listing cache entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/{key}")
async def invalidate_cache_entry(key: str):
    """
    Invalidate a specific cache entry.

    Args:
        key: Cache key to invalidate

    Returns:
        Confirmation of invalidation
    """
    try:
        manager = get_degradation_manager()
        manager.cache.invalidate(key)
        return {"success": True, "message": f"Cache key '{key}' invalidated"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def clear_cache():
    """
    Clear all cache entries.

    Returns:
        Count of cleared entries
    """
    try:
        manager = get_degradation_manager()
        count = manager.cache.clear()
        return {
            "success": True,
            "message": f"Cleared {count} cache entries",
            "cleared": count,
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_name}/reset")
async def reset_service_stats(service_name: str):
    """
    Reset statistics for a specific service.

    Args:
        service_name: Name of the service

    Returns:
        Confirmation of reset
    """
    try:
        manager = get_degradation_manager()
        svc = manager.get_service(service_name)

        if not svc:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{service_name}' not found",
            )

        # Reset statistics
        svc.failure_count = 0
        svc.success_count = 0
        svc.status = ServiceStatus.UNKNOWN
        svc.degraded_since = None
        svc.error_message = None

        return {
            "success": True,
            "message": f"Service '{service_name}' statistics reset",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting service stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fallbacks")
async def list_fallbacks():
    """
    List all registered fallbacks.

    Returns:
        Static and computed fallback handlers
    """
    try:
        manager = get_degradation_manager()
        return {
            "static_fallbacks": list(manager.static_fallbacks.keys()),
            "computed_handlers": list(manager.fallback_handlers.keys()),
            "total": len(manager.static_fallbacks) + len(manager.fallback_handlers),
        }
    except Exception as e:
        logger.error(f"Error listing fallbacks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-fallback/{key}")
async def test_fallback(key: str):
    """
    Test getting a fallback for a specific key.

    Args:
        key: Fallback key to test

    Returns:
        Fallback value if available
    """
    try:
        manager = get_degradation_manager()

        # Try cached first
        fallback = manager.get_fallback(key, FallbackType.CACHED)
        if fallback:
            return {
                "key": key,
                "fallback_type": "cached",
                "available": True,
                "value": fallback,
            }

        # Try static
        fallback = manager.get_fallback(key, FallbackType.STATIC)
        if fallback:
            return {
                "key": key,
                "fallback_type": "static",
                "available": True,
                "value": fallback,
            }

        return {
            "key": key,
            "available": False,
            "message": "No fallback available for this key",
        }
    except Exception as e:
        logger.error(f"Error testing fallback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
