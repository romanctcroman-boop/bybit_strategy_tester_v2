"""
Health check endpoints for monitoring service health.

Provides endpoints to check:
- Overall service health
- Bybit API connectivity
- Database connectivity
- Redis connectivity (if enabled)
- Cache availability
- Prometheus metrics
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.core.config import get_config
from backend.core.logging_config import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)
config = get_config()


# =============================================================================
# KUBERNETES PROBES (minimal endpoints for K8s health checks)
# =============================================================================


@router.get("/liveness", include_in_schema=True)
@router.get("/livez", include_in_schema=False)
def liveness_probe():
    """
    Kubernetes liveness probe.
    Returns 200 if the process is alive.
    Used by K8s to determine if the pod should be restarted.
    """
    return {"status": "alive"}


@router.get("/readiness", include_in_schema=True)
@router.get("/readyz", include_in_schema=False)
def readiness_probe():
    """
    Kubernetes readiness probe.
    Returns 200 if the service is ready to accept traffic.
    """
    return {"status": "ready"}


@router.get("/startup", include_in_schema=True)
@router.get("/healthz", include_in_schema=False)
def startup_probe():
    """
    Kubernetes startup probe.
    Returns 200 if the service has started successfully.
    """
    return {"status": "ok"}


@router.get("", response_model=dict[str, Any])
async def health_check():
    """
    Overall health check.

    Returns:
        Health status of all components

    Status Codes:
        200: All components healthy
        503: One or more components unhealthy
    """
    checks = {}
    overall_status = "healthy"

    # 1. Check Bybit API
    try:
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter()
        start = time.time()
        candles = adapter.get_klines("BTCUSDT", "1", 10)
        duration_ms = (time.time() - start) * 1000

        checks["bybit_api"] = {
            "status": "ok" if len(candles) > 0 else "degraded",
            "response_time_ms": round(duration_ms, 2),
            "candles_fetched": len(candles),
            "message": f"Fetched {len(candles)} candles in {duration_ms:.2f}ms",
        }

        if len(candles) == 0:
            overall_status = "degraded"

    except Exception as e:
        checks["bybit_api"] = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
        overall_status = "unhealthy"
        logger.error("Bybit API health check failed", extra={"error": str(e)})

    # 2. Check PostgreSQL
    try:
        from sqlalchemy import text  # ✅ SQLAlchemy 2.0 compatibility

        from backend.database import SessionLocal

        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))  # ✅ Fixed: explicit text() for SQLAlchemy 2.0
            checks["database"] = {
                "status": "ok",
                "message": "Database connection successful",
            }
        finally:
            session.close()

    except Exception as e:
        checks["database"] = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
        overall_status = "unhealthy"
        logger.error("Database health check failed", extra={"error": str(e)})

    # 3. Check cache directory
    import os

    cache_dir = config.CACHE_DIR

    try:
        if os.path.exists(cache_dir):
            cache_files = len(os.listdir(cache_dir))
            checks["cache"] = {
                "status": "ok",
                "cache_files": cache_files,
                "cache_dir": cache_dir,
                "message": f"{cache_files} cache files in {cache_dir}",
            }
        else:
            checks["cache"] = {
                "status": "warning",
                "message": f"Cache directory not found: {cache_dir}",
            }
            if overall_status == "healthy":
                overall_status = "degraded"

    except Exception as e:
        checks["cache"] = {"status": "error", "error": str(e)}

    # Build response
    response = {
        "status": overall_status,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
        "config": {
            "cache_enabled": config.CACHE_ENABLED,
            "db_persist_enabled": config.DB_PERSIST_ENABLED,
            "log_level": config.LOG_LEVEL,
        },
    }

    # Return 503 if unhealthy
    if overall_status == "unhealthy":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response)

    return response


@router.get("/bybit", response_model=dict[str, Any])
async def bybit_health():
    """
    Detailed Bybit API health check.

    Tests multiple symbols and intervals to ensure API is working correctly.
    """
    from backend.services.adapters.bybit import BybitAdapter

    adapter = BybitAdapter()
    results = {}

    # Test symbols
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    for symbol in test_symbols:
        try:
            start = time.time()
            candles = adapter.get_klines(symbol, "1", 10)
            duration_ms = (time.time() - start) * 1000

            results[symbol] = {
                "status": "ok",
                "candles": len(candles),
                "response_time_ms": round(duration_ms, 2),
                "latest_price": float(candles[-1]["close"]) if candles else None,
                "latest_time": candles[-1]["open_time"] if candles else None,
            }
        except Exception as e:
            results[symbol] = {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }

    # Calculate success rate
    successful = sum(1 for r in results.values() if r.get("status") == "ok")
    total = len(results)
    success_rate = (successful / total) * 100 if total > 0 else 0

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "success_rate": round(success_rate, 2),
        "successful": successful,
        "total": total,
        "results": results,
    }


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe (Phase 2.1 enhanced).

    Checks:
    - Bybit API connectivity
    - Redis connectivity (if persistence enabled)
    - Agent config loaded
    - Circuit breakers initialized

    Returns 200 if service is ready to accept traffic, 503 otherwise.
    """
    checks = {}
    not_ready_reasons = []

    # 1. Check Bybit API connectivity
    try:
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter()
        candles = adapter.get_klines("BTCUSDT", "1", 1)
        checks["bybit_api"] = len(candles) > 0
        if not checks["bybit_api"]:
            not_ready_reasons.append("Bybit API not responding with data")
    except Exception as e:
        checks["bybit_api"] = False
        not_ready_reasons.append(f"Bybit API error: {e!s}")

    # 2. Check Redis connectivity (for circuit breaker persistence)
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        manager = get_circuit_manager()
        if manager._persistence_enabled and manager._redis:
            await manager._redis.ping()
            checks["redis"] = True
        else:
            checks["redis"] = None  # Not enabled
    except Exception as e:
        checks["redis"] = False
        not_ready_reasons.append(f"Redis connection failed: {e!s}")

    # 3. Check agent config loaded
    try:
        from backend.agents.agent_config import get_agent_config

        cfg = get_agent_config()
        checks["agent_config"] = cfg.meta.version >= 1
    except Exception as e:
        checks["agent_config"] = False
        not_ready_reasons.append(f"Agent config not loaded: {e!s}")

    # 4. Check circuit breakers initialized
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        manager = get_circuit_manager()
        checks["circuit_breakers"] = len(manager._breakers) > 0
        if not checks["circuit_breakers"]:
            not_ready_reasons.append("No circuit breakers registered")
    except Exception as e:
        checks["circuit_breakers"] = False
        not_ready_reasons.append(f"Circuit breaker manager error: {e!s}")

    # Determine overall readiness
    critical_checks = ["bybit_api", "agent_config", "circuit_breakers"]
    all_critical_ready = all(checks.get(key, False) for key in critical_checks)
    redis_ready = checks.get("redis")  # None if not enabled, True/False otherwise

    if not all_critical_ready or (redis_ready is False):
        logger.warning(f"Readiness check failed: {not_ready_reasons}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "checks": checks,
                "reasons": not_ready_reasons,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe.

    Returns 200 if service is alive (even if degraded).
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/db_pool", response_model=dict[str, Any])
async def database_pool_status():
    """
    Week 1, Day 3: Database connection pool monitoring.

    Returns real-time connection pool metrics:
    - Pool size and utilization
    - Checked out/in connections
    - Overflow status
    - Health assessment
    - Configuration details
    - Performance recommendations

    Returns:
        Detailed pool status and recommendations
    """
    try:
        from backend.database import engine
        from backend.database.pool_monitor import ConnectionPoolMonitor

        monitor = ConnectionPoolMonitor(engine)

        # Get comprehensive pool statistics
        statistics = monitor.get_pool_statistics()

        # Get health recommendations
        recommendations = monitor.get_recommendations()

        # Check for potential connection leaks
        leak_detected = monitor.check_connection_leaks()

        response = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "pool_status": statistics,
            "recommendations": recommendations,
            "leak_detected": leak_detected,
            "configuration": {
                "pool_size": statistics["size"],
                "max_overflow": statistics["max_overflow"],
                "timeout": statistics["timeout"],
                "recycle": statistics["recycle"],
                "pre_ping": statistics["pre_ping"],
            },
        }

        # Return 503 if pool is critical
        if statistics["health"] == "critical":
            logger.warning(f"Database pool in critical state: {statistics['utilization']}% utilization")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get DB pool status", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to get DB pool status: {e!s}")


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus format for scraping.

    Metrics include:
    - bybit_api_requests_total: Total API requests by symbol/interval/status
    - bybit_api_duration_seconds: API request latencies
    - bybit_cache_operations_total: Cache hit/miss rates
    - bybit_candles_fetched_total: Candles fetched from API/cache
    - bybit_errors_total: Error counts by type
    - bybit_rate_limit_hits_total: Rate limit violations
    - bybit_historical_fetches_total: Historical fetch operations
    - bybit_adapter_info: Adapter version and configuration
    - db_pool_*: Connection pool metrics (size, checked_out, overflow, utilization)
    """
    try:
        metrics_output = generate_latest()
        return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error("Failed to generate metrics", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to generate metrics: {e!s}")


@router.get("/phase2", response_model=dict[str, Any])
async def phase2_status():
    """
    Phase 2 deployment status endpoint.

    Returns:
        Circuit breaker persistence status, YAML config status, Redis health

    Example response:
    {
        "phase2_enabled": true,
        "persistence": {
            "enabled": true,
            "redis_connected": true,
            "autosave_interval": 60,
            "breakers_tracked": 3
        },
        "config": {
            "yaml_loaded": true,
            "config_file": "backend/config/agents.yaml",
            "circuit_breakers": 3,
            "prompt_max_length": 16000
        },
        "breakers": {
            "deepseek_api": {"total_calls": 120, "failed_calls": 2, "total_trips": 0},
            "perplexity_api": {"total_calls": 45, "failed_calls": 1, "total_trips": 0},
            "mcp_server": {"total_calls": 0, "failed_calls": 0, "total_trips": 0}
        }
    }
    """
    try:
        from backend.agents.circuit_breaker_manager import get_circuit_manager

        circuit_mgr = get_circuit_manager()
        metrics = circuit_mgr.get_metrics()

        # Get config status
        try:
            from backend.agents.agent_config import get_agent_config

            config = get_agent_config()
            config_status = {
                "yaml_loaded": True,
                "config_file": "backend/config/agents.yaml",
                "circuit_breakers": len(config.circuit_breakers),
                "prompt_max_length": config.prompt.max_length,
                "tool_calls_max": config.budget.tool_calls_max,
            }
        except Exception as e:
            config_status = {
                "yaml_loaded": False,
                "error": f"Config not loaded or file missing: {e!s}",
            }

        # Build response
        response = {
            "phase2_enabled": True,
            "persistence": {
                "enabled": circuit_mgr._persistence_enabled,
                "redis_connected": circuit_mgr._persistence_redis is not None,
                "autosave_interval": circuit_mgr._autosave_interval if circuit_mgr._persistence_enabled else None,
                "breakers_tracked": len(circuit_mgr._configs),
            },
            "config": config_status,
            "breakers": {},
        }

        # Add breaker details
        for name, config in metrics.breakers.items():
            response["breakers"][name] = {
                "total_calls": config["total_calls"],
                "failed_calls": config["failed_calls"],
                "successful_calls": config["successful_calls"],
                "total_trips": config["total_trips"],
                "current_state": config["current_state"],
                "success_rate_24h": config["success_rate_24h"],
            }

        return response

    except Exception as e:
        logger.error("Failed to get Phase 2 status", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to get Phase 2 status: {e!s}")


# =============================================================================
# DATABASE MONITORING (NEW: Database Modernization)
# =============================================================================


@router.get("/database", response_model=dict[str, Any])
async def database_health():
    """
    Detailed database health check.

    Returns comprehensive database status including:
    - Connectivity
    - Table integrity
    - Query performance
    - Archive status
    - Database size
    """
    try:
        from backend.monitoring.db_monitor import DatabaseMonitor

        monitor = DatabaseMonitor()
        health = monitor.check_health()

        return health.to_dict()

    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Database health check failed: {e!s}")


@router.get("/database/metrics", response_model=dict[str, Any])
async def database_metrics():
    """
    Get database metrics as JSON.

    Returns:
    - Main table statistics
    - Archive statistics
    - Database size
    """
    try:
        from backend.monitoring.db_monitor import DatabaseMonitor

        monitor = DatabaseMonitor()
        return monitor.get_metrics()

    except Exception as e:
        logger.error("Failed to get database metrics", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to get database metrics: {e!s}")


@router.get("/database/metrics/prometheus")
async def database_metrics_prometheus():
    """
    Get database metrics in Prometheus format.

    Use this endpoint for Prometheus scraping.
    """
    try:
        from backend.monitoring.db_monitor import DatabaseMonitor

        monitor = DatabaseMonitor()
        metrics = monitor.get_metrics_prometheus()

        return Response(content=metrics, media_type="text/plain")

    except Exception as e:
        logger.error("Failed to get Prometheus metrics", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to get Prometheus metrics: {e!s}")


# =============================================================================
# COMPREHENSIVE HEALTH CHECK (NEW: Based on MONITORING_SYSTEM_AUDIT_2026_01_28)
# =============================================================================


@router.get("/comprehensive", response_model=dict[str, Any])
async def comprehensive_health_check():
    """
    Comprehensive system health check.

    Checks all critical system components:
    - Database connectivity
    - Redis connectivity
    - Bybit API status
    - Disk space
    - Memory usage
    - CPU usage

    Returns overall system health status with details for each component.

    Returns:
        SystemHealthReport with status of all components

    Status Codes:
        200: All components healthy or degraded
        503: One or more critical components unhealthy
    """
    try:
        from backend.monitoring.health_checks import get_health_checker

        checker = get_health_checker()
        report = await checker.check_all(force=True)

        result = report.to_dict()

        # Return 503 if overall status is unhealthy
        if result["overall_status"] == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result,
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Comprehensive health check failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=500,
            detail=f"Comprehensive health check failed: {e!s}",
        )


@router.get("/comprehensive/{component}", response_model=dict[str, Any])
async def component_health_check(component: str):
    """
    Check health of a specific component.

    Args:
        component: Component name (database, redis, bybit_api, disk, memory, cpu)

    Returns:
        HealthCheckResult for the specified component
    """
    from backend.monitoring.health_checks import get_health_checker

    checker = get_health_checker()

    # Map component names to check methods
    check_methods = {
        "database": checker.check_database,
        "redis": checker.check_redis,
        "bybit_api": checker.check_bybit_api,
        "disk": checker.check_disk_space,
        "memory": checker.check_memory,
        "cpu": checker.check_cpu,
    }

    if component not in check_methods:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown component: {component}. Available: {list(check_methods.keys())}",
        )

    try:
        result = await check_methods[component]()
        return result.to_dict()
    except Exception as e:
        logger.error(
            f"Component health check failed: {component}",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Component health check failed: {e!s}",
        )
