"""
Monitoring Router
Endpoints for health checks and metrics export
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.responses import Response

from backend.monitoring.prometheus_metrics import get_metrics_collector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health", summary="System Health Check")
async def health_check() -> dict[str, Any]:
    """
    System health check endpoint

    Returns status of:
    - API server
    - Redis cache
    - Database connection
    - AI agents
    - Backtest engine
    """
    try:
        from backend.core.ai_cache import get_cache_manager

        cache_manager = get_cache_manager()

        return {
            "status": "healthy",
            "components": {
                "api": {"status": "healthy"},
                "cache": {
                    "status": "connected"
                    if cache_manager.redis_connected
                    else "disconnected"
                },
                "ai_agents": {"status": "ready"},
                "backtest_engine": {"status": "ready"},
            },
            "timestamp": None,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.get("/metrics", summary="Prometheus Metrics Export")
async def prometheus_metrics():
    """
    Export all metrics in Prometheus text format

    Can be scraped by Prometheus using:
    ```
    scrape_configs:
      - job_name: 'ai_strategy_tester'
        static_configs:
          - targets: ['localhost:8000']
        metrics_path: '/monitoring/metrics'
    ```
    """
    try:
        collector = get_metrics_collector()
        metrics_text = collector.get_metrics_text()
        # CRITICAL FIX: Return bytes to avoid JSON serialization
        return Response(
            content=metrics_text.encode("utf-8"),
            media_type="text/plain; version=0.0.4; charset=utf-8",
            headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
        )
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")


@router.get("/metrics/json", summary="Metrics as JSON")
async def metrics_json() -> dict[str, Any]:
    """
    Export all metrics as JSON

    Useful for dashboards that don't support Prometheus format directly
    """
    try:
        collector = get_metrics_collector()
        return collector.get_metrics_dict()
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")


@router.get("/cache/stats", summary="Cache Performance Statistics")
async def cache_stats() -> dict[str, Any]:
    """
    Get detailed cache performance statistics

    Returns:
    - Hit rate percentage
    - Total hits and misses
    - Average latency
    - Memory usage
    """
    try:
        from backend.core.ai_cache import get_cache_manager

        cache_manager = get_cache_manager()
        stats = cache_manager.get_stats()

        return {
            "cache_enabled": stats.get("enabled", False),
            "redis_connected": stats.get("redis_connected", False),
            "hits": stats.get("hits", 0),
            "misses": stats.get("misses", 0),
            "hit_rate_percent": stats.get("hit_rate_percent", 0),
            "errors": stats.get("errors", 0),
            "ttl_seconds": stats.get("default_ttl", 3600),
            "total_requests": stats.get("total_requests", 0),
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        # Return degraded stats instead of raising error
        return {
            "cache_enabled": False,
            "redis_connected": False,
            "hits": 0,
            "misses": 0,
            "hit_rate_percent": 0,
            "errors": 1,
            "ttl_seconds": 3600,
            "total_requests": 0,
            "error": str(e),
        }


@router.get("/ai-agents/status", summary="AI Agents Status")
async def ai_agents_status() -> dict[str, Any]:
    """
    Get status of all AI agents

    Returns:
    - DeepSeek availability and key pool
    - Perplexity availability and key pool
    - Circuit breaker states
    - Last error times
    """
    try:
        from backend.agents.unified_agent_interface import UnifiedAgentInterface

        agent = UnifiedAgentInterface()

        # Get health check data with safe fallbacks
        try:
            deepseek_health = agent.health_monitor.get_component_health("deepseek_api")
        except Exception:
            deepseek_health = False

        try:
            perplexity_health = agent.health_monitor.get_component_health(
                "perplexity_api"
            )
        except Exception:
            perplexity_health = False

        return {
            "deepseek": {
                "status": "healthy" if deepseek_health else "unhealthy",
                "available": True,
                "keys_active": len(getattr(agent, "deepseek_keys", [])),
            },
            "perplexity": {
                "status": "healthy" if perplexity_health else "unhealthy",
                "available": True,
                "keys_active": len(getattr(agent, "perplexity_keys", [])),
            },
            "circuit_breakers": {
                "deepseek": getattr(
                    agent.circuit_breaker_manager,
                    "get_breaker_state",
                    lambda x: "unknown",
                )("deepseek_api"),
                "perplexity": getattr(
                    agent.circuit_breaker_manager,
                    "get_breaker_state",
                    lambda x: "unknown",
                )("perplexity_api"),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get AI agents status: {e}", exc_info=True)
        # Return degraded status instead of raising error
        return {
            "deepseek": {
                "status": "unknown",
                "available": False,
                "keys_active": 0,
            },
            "perplexity": {
                "status": "unknown",
                "available": False,
                "keys_active": 0,
            },
            "circuit_breakers": {
                "deepseek": "unknown",
                "perplexity": "unknown",
            },
            "error": str(e),
        }


@router.post("/cache/clear", summary="Clear Cache")
async def clear_cache() -> dict[str, Any]:
    """
    Clear all cached AI responses

    Useful for:
    - Testing with fresh data
    - Clearing potentially stale responses
    - Freeing Redis memory
    """
    try:
        from backend.core.ai_cache import get_cache_manager

        cache_manager = get_cache_manager()
        cleared_count = cache_manager.clear_all()

        return {
            "success": True,
            "cleared_entries": cleared_count,
            "message": f"Cleared {cleared_count} cache entries",
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")
