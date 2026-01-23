"""
Rate Limiting API Router.

Provides REST API for rate limiting management and monitoring.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services.rate_limiter import (
    RateLimitConfig,
    RateLimitScope,
    RateLimitStrategy,
    get_rate_limiter_service,
)

router = APIRouter(prefix="/api/v1/rate-limiting")


# ============================================================
# Request/Response Models
# ============================================================


class RateLimitRuleRequest(BaseModel):
    """Request to create/update a rate limit rule."""

    name: str
    requests_per_second: float
    burst_size: int = 10
    strategy: str = "token_bucket"
    scope: str = "per_ip"
    enabled: bool = True
    penalty_seconds: int = 60


class RateLimitCheckRequest(BaseModel):
    """Request to check rate limit."""

    rule_name: str
    identifier: str


class RateLimitCheckResponse(BaseModel):
    """Response for rate limit check."""

    allowed: bool
    remaining: int
    reset_after: float
    retry_after: Optional[float] = None
    limit: int
    scope: str
    rule_name: str


class RuleInfoResponse(BaseModel):
    """Response for rule information."""

    name: str
    requests_per_second: float
    burst_size: int
    strategy: str
    scope: str
    enabled: bool
    penalty_seconds: int


class ServiceStatusResponse(BaseModel):
    """Service status response."""

    initialized: bool
    rules_count: int
    active_limiters: int
    blocked_ips_count: int
    total_requests: int
    block_rate: float


class BlockedIPResponse(BaseModel):
    """Response for blocked IP."""

    ip: str
    rule: str
    blocked_until: str
    remaining_seconds: float


# ============================================================
# API Endpoints
# ============================================================


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """Get rate limiter service status."""
    service = get_rate_limiter_service()
    status = service.get_status()
    return ServiceStatusResponse(**status)


@router.get("/rules", response_model=list[RuleInfoResponse])
async def list_rules():
    """List all rate limiting rules."""
    service = get_rate_limiter_service()
    rules = service.list_rules()
    return [RuleInfoResponse(**r) for r in rules]


@router.get("/rules/{rule_name}", response_model=RuleInfoResponse)
async def get_rule(rule_name: str):
    """Get a specific rate limiting rule."""
    service = get_rate_limiter_service()
    rule = service.get_rule(rule_name)

    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"Rule '{rule_name}' not found",
        )

    return RuleInfoResponse(
        name=rule.name,
        requests_per_second=rule.requests_per_second,
        burst_size=rule.burst_size,
        strategy=rule.strategy.value,
        scope=rule.scope.value,
        enabled=rule.enabled,
        penalty_seconds=rule.penalty_seconds,
    )


@router.post("/rules", response_model=RuleInfoResponse)
async def create_rule(request: RateLimitRuleRequest):
    """Create a new rate limiting rule."""
    service = get_rate_limiter_service()

    # Validate strategy and scope
    try:
        strategy = RateLimitStrategy(request.strategy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy: {request.strategy}",
        )

    try:
        scope = RateLimitScope(request.scope)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope: {request.scope}",
        )

    config = RateLimitConfig(
        name=request.name,
        requests_per_second=request.requests_per_second,
        burst_size=request.burst_size,
        strategy=strategy,
        scope=scope,
        enabled=request.enabled,
        penalty_seconds=request.penalty_seconds,
    )

    service.register_rule(config)

    return RuleInfoResponse(
        name=config.name,
        requests_per_second=config.requests_per_second,
        burst_size=config.burst_size,
        strategy=config.strategy.value,
        scope=config.scope.value,
        enabled=config.enabled,
        penalty_seconds=config.penalty_seconds,
    )


@router.delete("/rules/{rule_name}")
async def delete_rule(rule_name: str):
    """Delete a rate limiting rule."""
    service = get_rate_limiter_service()

    if not service.unregister_rule(rule_name):
        raise HTTPException(
            status_code=404,
            detail=f"Rule '{rule_name}' not found",
        )

    return {"status": "deleted", "rule": rule_name}


@router.post("/check", response_model=RateLimitCheckResponse)
async def check_rate_limit(request: RateLimitCheckRequest):
    """Check if a request would be rate limited."""
    service = get_rate_limiter_service()

    result = await service.check_rate_limit(
        rule_name=request.rule_name,
        identifier=request.identifier,
    )

    return RateLimitCheckResponse(
        allowed=result.allowed,
        remaining=result.remaining,
        reset_after=result.reset_after,
        retry_after=result.retry_after,
        limit=result.limit,
        scope=result.scope,
        rule_name=result.rule_name,
    )


@router.get("/check-endpoint")
async def check_endpoint_limit(request: Request, path: str, method: str = "GET"):
    """Check rate limit for a specific endpoint."""
    service = get_rate_limiter_service()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Get appropriate rule for endpoint
    rule_name = service.get_rule_for_endpoint(path, method)

    result = await service.check_rate_limit(
        rule_name=rule_name,
        identifier=client_ip,
    )

    return {
        "endpoint": path,
        "method": method,
        "client_ip": client_ip,
        "rule_applied": rule_name,
        "allowed": result.allowed,
        "remaining": result.remaining,
        "reset_after": result.reset_after,
    }


@router.get("/blocked-ips", response_model=list[BlockedIPResponse])
async def get_blocked_ips():
    """Get list of currently blocked IPs."""
    service = get_rate_limiter_service()
    blocked = service.get_blocked_ips()
    return [BlockedIPResponse(**b) for b in blocked]


@router.post("/blocked-ips/{ip}/unblock")
async def unblock_ip(ip: str):
    """Manually unblock an IP address."""
    service = get_rate_limiter_service()

    if service.unblock_ip(ip):
        return {"status": "unblocked", "ip": ip}
    else:
        return {"status": "not_found", "ip": ip}


@router.get("/is-blocked/{ip}")
async def is_ip_blocked(ip: str):
    """Check if an IP is currently blocked."""
    service = get_rate_limiter_service()
    blocked = service.is_ip_blocked(ip)
    return {"ip": ip, "blocked": blocked}


@router.get("/metrics")
async def get_metrics(rule_name: Optional[str] = None):
    """Get rate limiting metrics."""
    service = get_rate_limiter_service()
    return service.get_metrics(rule_name)


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all rate limiting metrics."""
    service = get_rate_limiter_service()
    service.reset_metrics()
    return {"status": "reset"}


@router.post("/cleanup")
async def cleanup_expired():
    """Clean up expired rate limit states."""
    service = get_rate_limiter_service()
    cleaned = service.cleanup_expired_states()
    return {"status": "cleaned", "expired_states_removed": cleaned}


@router.get("/summary")
async def get_rate_limit_summary():
    """Get comprehensive rate limiting summary."""
    service = get_rate_limiter_service()

    status = service.get_status()
    metrics = service.get_metrics()
    blocked = service.get_blocked_ips()
    rules = service.list_rules()

    return {
        "status": "healthy" if status["initialized"] else "not_initialized",
        "rules_count": status["rules_count"],
        "active_limiters": status["active_limiters"],
        "blocked_ips": len(blocked),
        "total_requests": metrics["global"]["total_requests"],
        "allowed_requests": metrics["global"]["allowed_requests"],
        "blocked_requests": metrics["global"]["blocked_requests"],
        "block_rate_percent": round(metrics["global"]["block_rate"], 2),
        "rules_by_scope": {
            "per_ip": sum(1 for r in rules if r["scope"] == "per_ip"),
            "global": sum(1 for r in rules if r["scope"] == "global"),
            "per_user": sum(1 for r in rules if r["scope"] == "per_user"),
            "per_api_key": sum(1 for r in rules if r["scope"] == "per_api_key"),
        },
    }


@router.get("/strategies")
async def list_strategies():
    """List available rate limiting strategies."""
    return [
        {"value": "fixed_window", "description": "Fixed time window counting"},
        {"value": "sliding_window", "description": "Sliding time window counting"},
        {"value": "token_bucket", "description": "Token bucket algorithm (default)"},
        {"value": "leaky_bucket", "description": "Leaky bucket algorithm"},
    ]


@router.get("/scopes")
async def list_scopes():
    """List available rate limiting scopes."""
    return [
        {"value": "global", "description": "Global limit for all requests"},
        {"value": "per_ip", "description": "Limit per IP address (default)"},
        {"value": "per_user", "description": "Limit per authenticated user"},
        {"value": "per_api_key", "description": "Limit per API key"},
        {"value": "per_endpoint", "description": "Limit per endpoint path"},
    ]
