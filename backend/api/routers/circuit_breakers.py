"""
Circuit Breaker Monitoring Router
Provides API endpoints for monitoring and managing circuit breakers.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.circuit_breaker_manager import (
    CircuitState,
    get_circuit_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/circuit-breakers", tags=["Circuit Breakers"])


# ============================================================================
# Response Models
# ============================================================================


class CircuitBreakerStatus(BaseModel):
    """Status of a single circuit breaker."""

    name: str
    state: str
    failure_count: int
    success_count: int
    total_calls: int
    success_rate: float
    is_healthy: bool
    last_failure: Optional[str] = None


class AdaptiveMetricsResponse(BaseModel):
    """Adaptive metrics for a circuit breaker."""

    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0
    current_threshold: int = 5
    current_timeout: int = 60
    backoff_multiplier: float = 1.0
    adaptive_enabled: bool = True
    has_fallback: bool = False
    trip_count: int = 0


class CircuitBreakersSummary(BaseModel):
    """Summary of all circuit breakers."""

    total_breakers: int
    healthy_count: int
    unhealthy_count: int
    breakers: List[CircuitBreakerStatus]
    overall_health: str
    timestamp: str


class CircuitBreakerMetrics(BaseModel):
    """Prometheus-style metrics for circuit breakers."""

    metrics: Dict[str, Any]
    prometheus_format: str


class ResetResponse(BaseModel):
    """Response for reset operation."""

    success: bool
    message: str
    reset_count: int


class ExtendedCircuitBreakerStatus(BaseModel):
    """Extended status including adaptive metrics for circuit breakers."""

    name: str
    state: str
    failure_count: int
    success_count: int
    failure_threshold: int
    recovery_timeout: int
    total_calls: int
    success_rate: float
    is_healthy: bool
    last_failure: Optional[str] = None
    # Adaptive metrics
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    is_adaptive: bool = False
    current_threshold: int = 5
    threshold_adjustments: int = 0
    last_threshold_change: Optional[str] = None
    fallback_available: bool = False


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=CircuitBreakersSummary)
async def get_circuit_breakers_status():
    """
    Get status of all circuit breakers.

    Returns summary of all circuit breakers including:
    - State (closed, open, half_open)
    - Failure/success counts
    - Success rate
    - Overall system health
    """
    try:
        manager = get_circuit_manager()
        status = manager.get_status()

        breakers = []
        healthy_count = 0

        for name, data in status.items():
            total_calls = data["failure_count"] + data["success_count"]
            success_rate = (
                (data["success_count"] / total_calls * 100)
                if total_calls > 0
                else 100.0
            )
            is_healthy = data["state"] == CircuitState.CLOSED.value

            if is_healthy:
                healthy_count += 1

            breaker = manager.breakers.get(name)
            last_failure = None
            if breaker and breaker.last_failure_time:
                last_failure = breaker.last_failure_time.isoformat()

            breakers.append(
                CircuitBreakerStatus(
                    name=name,
                    state=data["state"],
                    failure_count=data["failure_count"],
                    success_count=data["success_count"],
                    total_calls=total_calls,
                    success_rate=round(success_rate, 2),
                    is_healthy=is_healthy,
                    last_failure=last_failure,
                )
            )

        total = len(breakers)
        unhealthy = total - healthy_count

        # Determine overall health
        if total == 0:
            overall_health = "UNKNOWN"
        elif unhealthy == 0:
            overall_health = "HEALTHY"
        elif unhealthy < total / 2:
            overall_health = "DEGRADED"
        else:
            overall_health = "CRITICAL"

        return CircuitBreakersSummary(
            total_breakers=total,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy,
            breakers=breakers,
            overall_health=overall_health,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=CircuitBreakerMetrics)
async def get_circuit_breaker_metrics():
    """
    Get circuit breaker metrics in Prometheus-compatible format.

    Returns metrics that can be scraped by Prometheus:
    - circuit_breaker_state (0=closed, 1=open, 2=half_open)
    - circuit_breaker_failures_total
    - circuit_breaker_successes_total
    - circuit_breaker_success_rate
    """
    try:
        manager = get_circuit_manager()
        status = manager.get_status()

        metrics = {}
        prometheus_lines = []

        # Add help and type headers
        prometheus_lines.append(
            "# HELP circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open)"
        )
        prometheus_lines.append("# TYPE circuit_breaker_state gauge")
        prometheus_lines.append(
            "# HELP circuit_breaker_failures_total Total number of failures"
        )
        prometheus_lines.append("# TYPE circuit_breaker_failures_total counter")
        prometheus_lines.append(
            "# HELP circuit_breaker_successes_total Total number of successes"
        )
        prometheus_lines.append("# TYPE circuit_breaker_successes_total counter")
        prometheus_lines.append(
            "# HELP circuit_breaker_success_rate Current success rate percentage"
        )
        prometheus_lines.append("# TYPE circuit_breaker_success_rate gauge")

        state_map = {
            CircuitState.CLOSED.value: 0,
            CircuitState.OPEN.value: 1,
            CircuitState.HALF_OPEN.value: 2,
        }

        for name, data in status.items():
            # safe_name used for Prometheus metric names
            _ = name.replace("-", "_").replace(".", "_")

            total_calls = data["failure_count"] + data["success_count"]
            success_rate = (
                (data["success_count"] / total_calls * 100)
                if total_calls > 0
                else 100.0
            )

            metrics[name] = {
                "state": data["state"],
                "state_numeric": state_map.get(data["state"], -1),
                "failures": data["failure_count"],
                "successes": data["success_count"],
                "success_rate": round(success_rate, 2),
            }

            # Prometheus format
            prometheus_lines.append(
                f'circuit_breaker_state{{name="{name}"}} {state_map.get(data["state"], -1)}'
            )
            prometheus_lines.append(
                f'circuit_breaker_failures_total{{name="{name}"}} {data["failure_count"]}'
            )
            prometheus_lines.append(
                f'circuit_breaker_successes_total{{name="{name}"}} {data["success_count"]}'
            )
            prometheus_lines.append(
                f'circuit_breaker_success_rate{{name="{name}"}} {success_rate:.2f}'
            )

        return CircuitBreakerMetrics(
            metrics=metrics,
            prometheus_format="\n".join(prometheus_lines),
        )
    except Exception as e:
        logger.error(f"Error getting circuit breaker metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extended-status", response_model=List[ExtendedCircuitBreakerStatus])
async def get_extended_circuit_breaker_status():
    """
    Get extended status for all circuit breakers with adaptive metrics.

    Returns detailed information including:
    - Standard status (state, failure count, success count)
    - Latency metrics (average, p95, p99)
    - Adaptive threshold information
    - Fallback availability status
    """
    try:
        manager = get_circuit_manager()
        extended_statuses = []

        for name, breaker in manager.breakers.items():
            total_calls = breaker.failure_count + breaker.success_count
            success_rate = (
                (breaker.success_count / total_calls * 100)
                if total_calls > 0
                else 100.0
            )

            # Check if breaker has extended metrics (AdaptiveCircuitBreaker)
            extended_metrics = {}
            is_adaptive = False

            if hasattr(breaker, "get_extended_metrics"):
                extended_metrics = breaker.get_extended_metrics()
                is_adaptive = True

            # Build extended status
            status = ExtendedCircuitBreakerStatus(
                name=name,
                state=breaker.state.value,
                failure_count=breaker.failure_count,
                success_count=breaker.success_count,
                failure_threshold=breaker.failure_threshold,
                recovery_timeout=breaker.recovery_timeout,
                total_calls=total_calls,
                success_rate=round(success_rate, 2),
                is_healthy=breaker.state == CircuitState.CLOSED,
                last_failure=breaker.last_failure_time.isoformat()
                if breaker.last_failure_time
                else None,
                # Extended adaptive metrics
                avg_latency_ms=extended_metrics.get("avg_latency_ms"),
                p95_latency_ms=extended_metrics.get("p95_latency_ms"),
                p99_latency_ms=extended_metrics.get("p99_latency_ms"),
                is_adaptive=is_adaptive,
                current_threshold=extended_metrics.get(
                    "current_threshold", breaker.failure_threshold
                ),
                threshold_adjustments=extended_metrics.get("threshold_adjustments", 0),
                last_threshold_change=extended_metrics.get("last_threshold_change"),
                fallback_available=extended_metrics.get("fallback_available", False),
            )
            extended_statuses.append(status)

        return extended_statuses
    except Exception as e:
        logger.error(f"Error getting extended circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}")
async def get_circuit_breaker_by_name(name: str):
    """
    Get status of a specific circuit breaker by name.

    Args:
        name: Name of the circuit breaker

    Returns:
        Detailed status of the specified circuit breaker
    """
    try:
        manager = get_circuit_manager()

        if name not in manager.breakers:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker '{name}' not found. Available: {list(manager.breakers.keys())}",
            )

        breaker = manager.breakers[name]
        total_calls = breaker.failure_count + breaker.success_count
        success_rate = (
            (breaker.success_count / total_calls * 100) if total_calls > 0 else 100.0
        )

        return {
            "name": name,
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "success_count": breaker.success_count,
            "total_calls": total_calls,
            "success_rate": round(success_rate, 2),
            "failure_threshold": breaker.failure_threshold,
            "recovery_timeout": breaker.recovery_timeout,
            "is_healthy": breaker.state == CircuitState.CLOSED,
            "last_failure": breaker.last_failure_time.isoformat()
            if breaker.last_failure_time
            else None,
            "can_retry": breaker._should_attempt_reset()
            if breaker.state == CircuitState.OPEN
            else True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting circuit breaker '{name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", response_model=ResetResponse)
async def reset_all_circuit_breakers():
    """
    Reset all circuit breakers to closed state.

    Use with caution in production - this will reset all failure counts
    and close all open circuit breakers.
    """
    try:
        manager = get_circuit_manager()
        count = len(manager.breakers)
        manager.reset_all()

        logger.info(f"Reset {count} circuit breakers via API")

        return ResetResponse(
            success=True,
            message=f"Successfully reset {count} circuit breakers",
            reset_count=count,
        )
    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/reset")
async def reset_circuit_breaker(name: str):
    """
    Reset a specific circuit breaker by name.

    Args:
        name: Name of the circuit breaker to reset
    """
    try:
        manager = get_circuit_manager()

        if name not in manager.breakers:
            raise HTTPException(
                status_code=404, detail=f"Circuit breaker '{name}' not found"
            )

        breaker = manager.breakers[name]
        old_state = breaker.state.value
        breaker.state = CircuitState.CLOSED
        breaker.failure_count = 0

        logger.info(f"Reset circuit breaker '{name}' from {old_state} to closed")

        return {
            "success": True,
            "message": f"Circuit breaker '{name}' reset successfully",
            "previous_state": old_state,
            "current_state": "closed",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker '{name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Check Integration
# ============================================================================


def get_circuit_breakers_health() -> Dict[str, Any]:
    """
    Get circuit breakers health for integration with main health endpoint.

    Returns:
        Dict with health status and metrics
    """
    try:
        manager = get_circuit_manager()
        status = manager.get_status()

        healthy_count = sum(
            1 for data in status.values() if data["state"] == CircuitState.CLOSED.value
        )
        total = len(status)

        return {
            "healthy": healthy_count == total or total == 0,
            "total_breakers": total,
            "healthy_count": healthy_count,
            "unhealthy_count": total - healthy_count,
            "breakers": {name: data["state"] for name, data in status.items()},
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
        }
