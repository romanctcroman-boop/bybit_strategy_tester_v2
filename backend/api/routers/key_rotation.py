"""
API Key Rotation API Router.

AI Agent Security Recommendation Implementation:
Provides REST API endpoints for API key rotation management.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.api_key_rotation import (
    KeyProvider,
    KeyStatus,
    get_rotation_service,
)

router = APIRouter(prefix="/api/v1/key-rotation")


# ============================================================================
# Request/Response Models
# ============================================================================


class RegisterKeyRequest(BaseModel):
    """Request to register a new API key."""

    key_id: str = Field(..., description="Unique identifier for the key")
    key_value: str = Field(..., description="The actual API key value")
    provider: str = Field(
        ..., description="Key provider (deepseek, perplexity, bybit, etc.)"
    )
    description: str = Field(default="", description="Key description")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class RotateKeyRequest(BaseModel):
    """Request to rotate a key."""

    key_id: str = Field(..., description="ID of the key to rotate")
    new_key_value: str = Field(..., description="New key value")
    reason: str = Field(default="manual_rotation", description="Reason for rotation")


class KeyMetadataResponse(BaseModel):
    """Response model for key metadata."""

    key_id: str
    provider: str
    created_at: datetime
    expires_at: datetime
    last_used: datetime | None
    usage_count: int
    status: str
    rotated_from: str | None
    description: str
    tags: list[str]
    days_until_expiry: int


class RotationEventResponse(BaseModel):
    """Response model for rotation event."""

    event_id: str
    key_id: str
    provider: str
    old_key_hash: str
    new_key_hash: str
    rotated_at: datetime
    reason: str
    success: bool
    error_message: str | None


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics."""

    key_id: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    last_success: datetime | None
    last_failure: datetime | None
    avg_latency_ms: float
    error_rate: float


class ServiceStatusResponse(BaseModel):
    """Response model for service status."""

    enabled: bool
    rotation_days: int
    warning_days: int
    total_keys: int
    by_status: dict[str, int]
    by_provider: dict[str, int]
    total_rotations: int
    registered_fetchers: list[str]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """Get API key rotation service status."""
    service = get_rotation_service()
    status = service.get_status()

    return ServiceStatusResponse(
        enabled=status["enabled"],
        rotation_days=status["rotation_days"],
        warning_days=status["warning_days"],
        total_keys=status["total_keys"],
        by_status=status["by_status"],
        by_provider=status["by_provider"],
        total_rotations=status["total_rotations"],
        registered_fetchers=[
            p.value if hasattr(p, "value") else str(p)
            for p in status["registered_fetchers"]
        ],
    )


@router.post("/keys", response_model=dict[str, Any])
async def register_key(request: RegisterKeyRequest):
    """Register a new API key for rotation management."""
    # Validate provider
    try:
        provider = KeyProvider(request.provider)
    except ValueError:
        valid = [p.value for p in KeyProvider]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Valid: {valid}",
        )

    service = get_rotation_service()
    success = service.register_key(
        key_id=request.key_id,
        key_value=request.key_value,
        provider=provider,
        description=request.description,
        tags=request.tags,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to register key",
        )

    return {
        "status": "registered",
        "key_id": request.key_id,
        "provider": request.provider,
        "expires_in_days": service.rotation_days,
    }


@router.get("/keys", response_model=list[KeyMetadataResponse])
async def list_keys(provider: str | None = None):
    """List all registered API keys."""
    service = get_rotation_service()

    # Filter by provider if specified
    provider_enum = None
    if provider:
        try:
            provider_enum = KeyProvider(provider)
        except ValueError:
            valid = [p.value for p in KeyProvider]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Valid: {valid}",
            )

    keys = service.storage.list_keys(provider_enum)
    now = datetime.now()

    return [
        KeyMetadataResponse(
            key_id=k.key_id,
            provider=k.provider.value,
            created_at=k.created_at,
            expires_at=k.expires_at,
            last_used=k.last_used,
            usage_count=k.usage_count,
            status=k.status.value,
            rotated_from=k.rotated_from,
            description=k.description,
            tags=k.tags,
            days_until_expiry=(k.expires_at - now).days,
        )
        for k in keys
    ]


@router.get("/keys/{key_id}", response_model=KeyMetadataResponse)
async def get_key_info(key_id: str):
    """Get information about a specific key."""
    service = get_rotation_service()
    result = service.storage.retrieve_key(key_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Key {key_id} not found",
        )

    _, metadata = result
    now = datetime.now()

    return KeyMetadataResponse(
        key_id=metadata.key_id,
        provider=metadata.provider.value,
        created_at=metadata.created_at,
        expires_at=metadata.expires_at,
        last_used=metadata.last_used,
        usage_count=metadata.usage_count,
        status=metadata.status.value,
        rotated_from=metadata.rotated_from,
        description=metadata.description,
        tags=metadata.tags,
        days_until_expiry=(metadata.expires_at - now).days,
    )


@router.post("/keys/{key_id}/rotate", response_model=RotationEventResponse)
async def rotate_key(key_id: str, request: RotateKeyRequest):
    """Manually rotate a specific key."""
    service = get_rotation_service()

    event = service.rotate_key(
        key_id=key_id,
        new_key_value=request.new_key_value,
        reason=request.reason,
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Key {key_id} not found or rotation failed",
        )

    return RotationEventResponse(
        event_id=event.event_id,
        key_id=event.key_id,
        provider=event.provider.value,
        old_key_hash=event.old_key_hash,
        new_key_hash=event.new_key_hash,
        rotated_at=event.rotated_at,
        reason=event.reason,
        success=event.success,
        error_message=event.error_message,
    )


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: str):
    """Revoke a specific key."""
    service = get_rotation_service()

    success = service.storage.revoke_key(key_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Key {key_id} not found",
        )

    return {"status": "revoked", "key_id": key_id}


@router.get("/check-rotation", response_model=list[KeyMetadataResponse])
async def check_rotation_needed():
    """Check which keys need rotation."""
    service = get_rotation_service()
    keys_needing_rotation = service.check_rotation_needed()
    now = datetime.now()

    return [
        KeyMetadataResponse(
            key_id=k.key_id,
            provider=k.provider.value,
            created_at=k.created_at,
            expires_at=k.expires_at,
            last_used=k.last_used,
            usage_count=k.usage_count,
            status=k.status.value,
            rotated_from=k.rotated_from,
            description=k.description,
            tags=k.tags,
            days_until_expiry=(k.expires_at - now).days,
        )
        for k in keys_needing_rotation
    ]


@router.get("/history", response_model=list[RotationEventResponse])
async def get_rotation_history(limit: int = 100, provider: str | None = None):
    """Get rotation history."""
    service = get_rotation_service()

    provider_enum = None
    if provider:
        try:
            provider_enum = KeyProvider(provider)
        except ValueError:
            valid = [p.value for p in KeyProvider]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Valid: {valid}",
            )

    history = service.get_rotation_history(limit=limit, provider=provider_enum)

    return [
        RotationEventResponse(
            event_id=e.event_id,
            key_id=e.key_id,
            provider=e.provider.value,
            old_key_hash=e.old_key_hash,
            new_key_hash=e.new_key_hash,
            rotated_at=e.rotated_at,
            reason=e.reason,
            success=e.success,
            error_message=e.error_message,
        )
        for e in history
    ]


@router.get("/usage/{key_id}", response_model=UsageStatsResponse)
async def get_key_usage(key_id: str):
    """Get usage statistics for a key."""
    service = get_rotation_service()
    stats = service.get_usage_stats(key_id)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"No usage stats found for {key_id}",
        )

    return UsageStatsResponse(
        key_id=stats.key_id,
        total_requests=stats.total_requests,
        successful_requests=stats.successful_requests,
        failed_requests=stats.failed_requests,
        last_success=stats.last_success,
        last_failure=stats.last_failure,
        avg_latency_ms=stats.avg_latency_ms,
        error_rate=stats.error_rate,
    )


@router.get("/usage", response_model=dict[str, UsageStatsResponse])
async def get_all_usage_stats():
    """Get usage statistics for all keys."""
    service = get_rotation_service()
    all_stats = service.get_all_usage_stats()

    return {
        key_id: UsageStatsResponse(
            key_id=stats.key_id,
            total_requests=stats.total_requests,
            successful_requests=stats.successful_requests,
            failed_requests=stats.failed_requests,
            last_success=stats.last_success,
            last_failure=stats.last_failure,
            avg_latency_ms=stats.avg_latency_ms,
            error_rate=stats.error_rate,
        )
        for key_id, stats in all_stats.items()
    }


@router.get("/providers")
async def list_providers():
    """List all supported key providers."""
    return {
        "providers": [p.value for p in KeyProvider],
        "statuses": [s.value for s in KeyStatus],
    }


@router.get("/summary")
async def get_rotation_summary():
    """Get comprehensive rotation status summary."""
    service = get_rotation_service()
    status = service.get_status()
    keys = service.storage.list_keys()
    now = datetime.now()

    # Find keys expiring soon
    expiring_soon = [
        {
            "key_id": k.key_id,
            "provider": k.provider.value,
            "days_left": (k.expires_at - now).days,
        }
        for k in keys
        if k.status == KeyStatus.ACTIVE and (k.expires_at - now).days <= 14
    ]

    # Recent rotations
    recent_rotations = service.get_rotation_history(limit=5)

    return {
        "status": status,
        "expiring_soon": expiring_soon,
        "recent_rotations": [
            {
                "event_id": e.event_id,
                "key_id": e.key_id,
                "provider": e.provider.value,
                "rotated_at": e.rotated_at.isoformat(),
                "success": e.success,
            }
            for e in recent_rotations
        ],
        "health": {
            "active_keys": status["by_status"].get("active", 0),
            "pending_rotation": status["by_status"].get("pending_rotation", 0),
            "expired_keys": status["by_status"].get("expired", 0),
            "revoked_keys": status["by_status"].get("revoked", 0),
        },
    }
