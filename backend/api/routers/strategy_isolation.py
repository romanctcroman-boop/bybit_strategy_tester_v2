"""
Strategy Isolation API Router

Provides REST API endpoints for managing isolated strategy execution environments.

Created: 2025-12-21
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.strategy_isolation import (
    IsolationLevel,
    ResourceQuota,
    StrategyState,
    get_isolation_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-isolation", tags=["Strategy Isolation"])


# Request/Response Models


class ResourceQuotaRequest(BaseModel):
    """Resource quota configuration"""

    max_memory_mb: float = Field(default=512.0, ge=64, le=4096)
    max_cpu_percent: float = Field(default=25.0, ge=1, le=100)
    max_concurrent_trades: int = Field(default=10, ge=1, le=100)
    max_position_size_usdt: float = Field(default=10000.0, ge=100)
    max_daily_trades: int = Field(default=100, ge=1, le=1000)
    max_daily_loss_usdt: float = Field(default=500.0, ge=10)
    max_drawdown_percent: float = Field(default=20.0, ge=1, le=100)
    api_rate_limit_per_minute: int = Field(default=60, ge=10, le=1000)


class RegisterStrategyRequest(BaseModel):
    """Request to register a new strategy"""

    strategy_name: str = Field(..., min_length=1, max_length=100)
    strategy_id: str | None = Field(default=None, max_length=50)
    isolation_level: IsolationLevel = Field(default=IsolationLevel.SOFT)
    quota: ResourceQuotaRequest | None = None


class UpdateQuotaRequest(BaseModel):
    """Request to update strategy quota"""

    quota: ResourceQuotaRequest


class StrategyActionRequest(BaseModel):
    """Request for strategy actions"""

    reason: str = Field(default="api_request", max_length=200)


class QuotaCheckRequest(BaseModel):
    """Request to check quota for a trade"""

    trade_size_usdt: float | None = Field(default=None, ge=0)


class RecordErrorRequest(BaseModel):
    """Request to record an error"""

    error: str = Field(..., max_length=1000)


class ResourceUsageUpdate(BaseModel):
    """Update resource usage metrics"""

    memory_mb: float | None = Field(default=None, ge=0)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)


# Endpoints


@router.get("/status")
async def get_manager_status():
    """Get overall status of the isolation manager"""
    manager = get_isolation_manager()
    return {
        "status": "active",
        "manager": manager.get_status(),
    }


@router.get("/strategies")
async def list_strategies():
    """List all registered strategies"""
    manager = get_isolation_manager()
    strategies = manager.list_strategies()
    return {
        "count": len(strategies),
        "strategies": [s.to_dict() for s in strategies],
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details by ID"""
    manager = get_isolation_manager()
    context = manager.get_context(strategy_id)

    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return context.to_dict()


@router.post("/strategies")
async def register_strategy(request: RegisterStrategyRequest):
    """Register a new strategy with isolated execution context"""
    manager = get_isolation_manager()

    quota = None
    if request.quota:
        quota = ResourceQuota(**request.quota.model_dump())

    context = await manager.register_strategy(
        strategy_name=request.strategy_name,
        strategy_id=request.strategy_id,
        quota=quota,
        isolation_level=request.isolation_level,
    )

    return {
        "message": "Strategy registered successfully",
        "strategy": context.to_dict(),
    }


@router.delete("/strategies/{strategy_id}")
async def unregister_strategy(strategy_id: str):
    """Unregister a strategy"""
    manager = get_isolation_manager()

    success = await manager.unregister_strategy(strategy_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return {"message": f"Strategy {strategy_id} unregistered successfully"}


@router.post("/strategies/{strategy_id}/start")
async def start_strategy(
    strategy_id: str, request: StrategyActionRequest | None = None
):
    """Start strategy execution"""
    manager = get_isolation_manager()

    context = manager.get_context(strategy_id)
    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    success = await manager.start_strategy(strategy_id)

    if not success:
        # Check if in cooldown
        if context.cooldown_until:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy is in cooldown until {context.cooldown_until.isoformat()}",
            )
        raise HTTPException(status_code=400, detail="Failed to start strategy")

    return {
        "message": f"Strategy {strategy_id} started",
        "state": context.state.value,
    }


@router.post("/strategies/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: str, request: StrategyActionRequest | None = None
):
    """Stop strategy execution"""
    manager = get_isolation_manager()

    reason = request.reason if request else "api_request"
    success = await manager.stop_strategy(strategy_id, reason=reason)

    if not success:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    context = manager.get_context(strategy_id)
    return {
        "message": f"Strategy {strategy_id} stopped",
        "state": context.state.value if context else "unknown",
    }


@router.post("/strategies/{strategy_id}/pause")
async def pause_strategy(
    strategy_id: str, request: StrategyActionRequest | None = None
):
    """Pause strategy execution"""
    manager = get_isolation_manager()

    reason = request.reason if request else "api_request"
    success = await manager.pause_strategy(strategy_id, reason=reason)

    if not success:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    context = manager.get_context(strategy_id)
    return {
        "message": f"Strategy {strategy_id} paused",
        "state": context.state.value if context else "unknown",
    }


@router.get("/strategies/{strategy_id}/quota")
async def get_strategy_quota(strategy_id: str):
    """Get strategy resource quota"""
    manager = get_isolation_manager()
    context = manager.get_context(strategy_id)

    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return {
        "strategy_id": strategy_id,
        "quota": context.quota.to_dict(),
        "usage": context.usage.to_dict(),
    }


@router.put("/strategies/{strategy_id}/quota")
async def update_strategy_quota(strategy_id: str, request: UpdateQuotaRequest):
    """Update strategy resource quota"""
    manager = get_isolation_manager()
    context = manager.get_context(strategy_id)

    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    # Update quota
    new_quota = ResourceQuota(**request.quota.model_dump())
    context.quota = new_quota

    return {
        "message": f"Quota updated for strategy {strategy_id}",
        "quota": context.quota.to_dict(),
    }


@router.post("/strategies/{strategy_id}/check-quota")
async def check_strategy_quota(
    strategy_id: str, request: QuotaCheckRequest | None = None
):
    """Check if strategy is within quota limits"""
    manager = get_isolation_manager()

    trade_size = request.trade_size_usdt if request else None
    allowed, reason = await manager.check_quota(strategy_id, trade_size_usdt=trade_size)

    return {
        "strategy_id": strategy_id,
        "allowed": allowed,
        "reason": reason,
    }


@router.post("/strategies/{strategy_id}/record-error")
async def record_strategy_error(strategy_id: str, request: RecordErrorRequest):
    """Record an error for a strategy"""
    manager = get_isolation_manager()

    context = manager.get_context(strategy_id)
    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    await manager.record_error(strategy_id, request.error)

    return {
        "message": "Error recorded",
        "error_count": context.error_count,
        "state": context.state.value,
    }


@router.post("/strategies/{strategy_id}/update-usage")
async def update_resource_usage(strategy_id: str, request: ResourceUsageUpdate):
    """Update resource usage metrics for a strategy"""
    manager = get_isolation_manager()

    context = manager.get_context(strategy_id)
    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    await manager.update_resource_usage(
        strategy_id,
        memory_mb=request.memory_mb,
        cpu_percent=request.cpu_percent,
    )

    return {
        "message": "Usage updated",
        "usage": context.usage.to_dict(),
    }


@router.post("/reset-daily-counters")
async def reset_daily_counters():
    """Reset daily counters for all strategies"""
    manager = get_isolation_manager()
    await manager.reset_daily_counters()

    return {"message": "Daily counters reset for all strategies"}


@router.get("/states")
async def get_available_states():
    """Get list of available strategy states"""
    return {
        "states": [state.value for state in StrategyState],
        "isolation_levels": [level.value for level in IsolationLevel],
    }


@router.get("/default-quota")
async def get_default_quota():
    """Get default resource quota configuration"""
    manager = get_isolation_manager()
    return {
        "default_quota": manager.default_quota.to_dict(),
        "default_isolation_level": manager.default_isolation_level.value,
    }


@router.get("/strategies/{strategy_id}/circuit-breaker")
async def get_circuit_breaker_status(strategy_id: str):
    """Get circuit breaker status for a strategy"""
    manager = get_isolation_manager()
    context = manager.get_context(strategy_id)

    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    return {
        "strategy_id": strategy_id,
        "triggered": context.circuit_breaker_triggered,
        "reason": context.circuit_breaker_reason,
        "triggered_at": context.circuit_breaker_triggered_at.isoformat()
        if context.circuit_breaker_triggered_at
        else None,
        "cooldown_until": context.cooldown_until.isoformat()
        if context.cooldown_until
        else None,
        "state": context.state.value,
    }


@router.post("/strategies/{strategy_id}/reset-circuit-breaker")
async def reset_circuit_breaker(strategy_id: str):
    """Reset circuit breaker for a strategy"""
    manager = get_isolation_manager()
    context = manager.get_context(strategy_id)

    if not context:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    # Reset circuit breaker
    context.circuit_breaker_triggered = False
    context.circuit_breaker_reason = None
    context.circuit_breaker_triggered_at = None
    context.cooldown_until = None

    if context.state == StrategyState.COOLDOWN:
        context.state = StrategyState.IDLE

    return {
        "message": f"Circuit breaker reset for strategy {strategy_id}",
        "state": context.state.value,
    }
