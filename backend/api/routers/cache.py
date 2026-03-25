"""
Cache Router
Endpoints for cache management and statistics.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return {"total_keys": 0, "hit_rate": 0.0}


@router.delete("/")
async def clear_cache():
    """Clear cache"""
    return {"status": "cleared"}
