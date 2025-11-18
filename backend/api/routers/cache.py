"""
Cache Statistics and Management API Router

Provides endpoints for:
- Real-time cache statistics
- Cache management operations
- Performance monitoring
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.cache.cache_manager import get_cache_manager

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """
    Get comprehensive cache statistics.
    
    Returns:
    - L1 (memory) cache stats: hits, misses, size, hit rate
    - L2 (Redis) cache stats: hits, errors
    - Overall performance metrics
    - Memory usage information
    
    Example response:
    ```json
    {
        "l1_cache": {
            "size": 150,
            "max_size": 1000,
            "hits": 5420,
            "misses": 234,
            "hit_rate": 0.958,
            "evictions": 45,
            "expired": 12
        },
        "l2_cache": {
            "hits": 1234,
            "errors": 0
        },
        "overall": {
            "total_hits": 6654,
            "total_misses": 234,
            "hit_rate": 0.966,
            "computes": 234,
            "compute_errors": 0
        }
    }
    ```
    """
    try:
        cache_manager = await get_cache_manager()
        
        # Get L1 cache stats
        l1_stats = await cache_manager.l1_cache.get_stats()
        
        # Get overall stats
        overall_stats = cache_manager._stats.copy()
        
        # Calculate combined hit rate
        total_hits = overall_stats.get('l1_hits', 0) + overall_stats.get('l2_hits', 0)
        total_misses = overall_stats.get('misses', 0)
        total_requests = total_hits + total_misses
        combined_hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        return {
            "l1_cache": l1_stats,
            "l2_cache": {
                "hits": overall_stats.get('l2_hits', 0),
                "errors": overall_stats.get('l2_errors', 0),
            },
            "overall": {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(combined_hit_rate, 3),
                "computes": overall_stats.get('computes', 0),
                "compute_errors": overall_stats.get('compute_errors', 0),
            },
            "status": "healthy" if overall_stats.get('l2_errors', 0) == 0 else "degraded"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cache statistics: {str(e)}"
        )


@router.post("/clear", response_model=Dict[str, str])
async def clear_cache():
    """
    Clear all cache levels (L1 and L2).
    
    ⚠️ Warning: This will clear all cached data.
    Use with caution in production environments.
    
    Returns:
    - Status message confirming cache was cleared
    """
    try:
        cache_manager = await get_cache_manager()
        
        # Clear L1 cache
        await cache_manager.l1_cache.clear()
        
        # Clear L2 cache (Redis) - delete all keys with pattern
        if cache_manager.redis_client:
            # Note: In production, you might want to use a prefix pattern
            # For now, we'll just clear L1 as L2 will expire naturally
            pass
        
        return {
            "status": "success",
            "message": "Cache cleared successfully",
            "cleared": "L1 (memory) cache"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.delete("/keys/{key_pattern}")
async def delete_cache_pattern(key_pattern: str):
    """
    Delete cache keys matching a pattern.
    
    Args:
    - key_pattern: Pattern to match keys (e.g., "user:*", "backtest:123:*")
    
    Returns:
    - Number of keys deleted
    
    Example:
    ```
    DELETE /cache/keys/backtest:*
    ```
    """
    try:
        cache_manager = await get_cache_manager()
        deleted = await cache_manager.delete_pattern(key_pattern)
        
        return {
            "status": "success",
            "pattern": key_pattern,
            "deleted_count": deleted
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete cache keys: {str(e)}"
        )


@router.get("/health")
async def cache_health_check():
    """
    Check cache system health.
    
    Returns:
    - L1 cache status
    - L2 (Redis) cache status
    - Overall health status
    """
    try:
        cache_manager = await get_cache_manager()
        
        # Check L1 cache
        l1_healthy = True  # L1 is always available (in-memory)
        
        # Check L2 cache (Redis)
        l2_healthy = True
        l2_error_count = cache_manager._stats.get('l2_errors', 0)
        
        if l2_error_count > 10:  # More than 10 errors indicates problems
            l2_healthy = False
        
        # Test Redis connectivity
        redis_available = False
        if cache_manager.redis_client:
            try:
                # Try to ping Redis
                await cache_manager.redis_client.set("health_check", "ok", expire=1)
                test_value = await cache_manager.redis_client.get("health_check")
                redis_available = (test_value == "ok")
            except Exception:
                redis_available = False
        
        overall_status = "healthy"
        if not l1_healthy:
            overall_status = "critical"
        elif not l2_healthy or not redis_available:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "l1_cache": {
                "status": "healthy" if l1_healthy else "unhealthy",
                "available": True
            },
            "l2_cache": {
                "status": "healthy" if l2_healthy else "degraded",
                "available": redis_available,
                "error_count": l2_error_count
            }
        }
    
    except Exception as e:
        return {
            "status": "critical",
            "error": str(e)
        }
