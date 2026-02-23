"""
KMS Integration API Router.

Provides REST API endpoints for key management operations
with proper authentication and audit logging.
"""

import base64
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.kms_integration import (
    AuditAction,
    KeyAlgorithm,
    KeyInfo,
    KeyType,
    KMSProvider,
    get_kms_service,
)

router = APIRouter(prefix="/kms", tags=["kms"])


# Request/Response Models
class CreateKeyRequest(BaseModel):
    """Request to create a new key."""

    key_type: KeyType = Field(default=KeyType.API_KEY)
    algorithm: KeyAlgorithm = Field(default=KeyAlgorithm.AES_256_GCM)
    metadata: dict = Field(default_factory=dict)


class EncryptRequest(BaseModel):
    """Request to encrypt data."""

    plaintext: str = Field(..., description="Data to encrypt (base64 or plain text)")
    key_id: str = Field(..., description="Key ID to use for encryption")
    is_base64: bool = Field(default=False, description="Is plaintext base64 encoded?")


class DecryptRequest(BaseModel):
    """Request to decrypt data."""

    ciphertext: str = Field(..., description="Base64 encoded ciphertext")
    key_id: str = Field(..., description="Key ID to use for decryption")


class EncryptApiKeyRequest(BaseModel):
    """Request to encrypt an API key."""

    api_key: str = Field(..., description="API key to encrypt")
    provider_name: str = Field(..., description="Name of the API provider")


class KeyInfoResponse(BaseModel):
    """Response with key information."""

    key_id: str
    key_type: str
    algorithm: str
    created_at: datetime
    expires_at: datetime | None = None
    rotated_at: datetime | None = None
    version: int
    is_enabled: bool
    metadata: dict


class EncryptResponse(BaseModel):
    """Response with encrypted data."""

    ciphertext: str  # Base64 encoded
    key_id: str


class DecryptResponse(BaseModel):
    """Response with decrypted data."""

    plaintext: str  # Base64 encoded


class EncryptApiKeyResponse(BaseModel):
    """Response with encrypted API key."""

    key_id: str
    encrypted_key: str  # Base64 encoded


class AuditLogEntryResponse(BaseModel):
    """Response for audit log entry."""

    entry_id: str
    timestamp: datetime
    action: str
    key_id: str
    user_id: str | None = None
    ip_address: str | None = None
    success: bool
    error_message: str | None = None
    details: dict


class ServiceStatusResponse(BaseModel):
    """Response for service status."""

    initialized: bool
    provider: str | None = None
    cache_size: int
    audit_log_size: int
    cache_ttl_seconds: int
    audit_logging_enabled: bool


class MetricsResponse(BaseModel):
    """Response for service metrics."""

    total_operations: int
    success_rate: float
    operations_by_type: dict


def _key_info_to_response(key_info: KeyInfo) -> KeyInfoResponse:
    """Convert KeyInfo to response model."""
    return KeyInfoResponse(
        key_id=key_info.key_id,
        key_type=key_info.key_type.value,
        algorithm=key_info.algorithm.value,
        created_at=key_info.created_at,
        expires_at=key_info.expires_at,
        rotated_at=key_info.rotated_at,
        version=key_info.version,
        is_enabled=key_info.is_enabled,
        metadata=key_info.metadata,
    )


@router.get("/status", response_model=ServiceStatusResponse)
async def get_status():
    """Get KMS service status."""
    service = get_kms_service()
    status_data = service.get_status()
    return ServiceStatusResponse(**status_data)


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get KMS service metrics."""
    service = get_kms_service()
    metrics = service.get_metrics()
    return MetricsResponse(**metrics)


@router.post("/initialize")
async def initialize_service():
    """Initialize the KMS service."""
    service = get_kms_service()
    success = await service.initialize()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize KMS service",
        )

    return {"message": "KMS service initialized", "status": service.get_status()}


@router.post("/shutdown")
async def shutdown_service():
    """Shutdown the KMS service."""
    service = get_kms_service()
    await service.shutdown()
    return {"message": "KMS service shutdown"}


@router.post(
    "/keys", response_model=KeyInfoResponse, status_code=status.HTTP_201_CREATED
)
async def create_key(request: CreateKeyRequest):
    """Create a new encryption key."""
    service = get_kms_service()

    try:
        key_info = await service.create_key(
            key_type=request.key_type,
            algorithm=request.algorithm,
            metadata=request.metadata,
        )
        return _key_info_to_response(key_info)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create key: {e!s}",
        )


@router.get("/keys", response_model=list[KeyInfoResponse])
async def list_keys():
    """List all managed keys."""
    service = get_kms_service()

    try:
        keys = await service.list_keys()
        return [_key_info_to_response(k) for k in keys]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list keys: {e!s}",
        )


@router.get("/keys/{key_id}", response_model=KeyInfoResponse)
async def get_key(key_id: str):
    """Get information about a specific key."""
    service = get_kms_service()

    try:
        key_info = await service.get_key_info(key_id)

        if not key_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found: {key_id}",
            )

        return _key_info_to_response(key_info)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key: {e!s}",
        )


@router.post("/keys/{key_id}/rotate", response_model=KeyInfoResponse)
async def rotate_key(key_id: str):
    """Rotate an existing key."""
    service = get_kms_service()

    try:
        key_info = await service.rotate_key(key_id)
        return _key_info_to_response(key_info)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate key: {e!s}",
        )


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str):
    """Delete a key (schedule for deletion)."""
    service = get_kms_service()

    try:
        result = await service.delete_key(key_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Key not found: {key_id}",
            )

        return {"message": f"Key {key_id} scheduled for deletion"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete key: {e!s}",
        )


@router.post("/encrypt", response_model=EncryptResponse)
async def encrypt_data(request: EncryptRequest):
    """Encrypt data using a specified key."""
    service = get_kms_service()

    try:
        plaintext = base64.b64decode(request.plaintext) if request.is_base64 else request.plaintext.encode()

        ciphertext = await service.encrypt(plaintext, request.key_id)

        return EncryptResponse(
            ciphertext=base64.b64encode(ciphertext).decode(),
            key_id=request.key_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e!s}",
        )


@router.post("/decrypt", response_model=DecryptResponse)
async def decrypt_data(request: DecryptRequest):
    """Decrypt data using a specified key."""
    service = get_kms_service()

    try:
        ciphertext = base64.b64decode(request.ciphertext)
        plaintext = await service.decrypt(ciphertext, request.key_id)

        return DecryptResponse(plaintext=base64.b64encode(plaintext).decode())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decryption failed: {e!s}",
        )


@router.post("/api-keys/encrypt", response_model=EncryptApiKeyResponse)
async def encrypt_api_key(request: EncryptApiKeyRequest):
    """Encrypt an API key for secure storage."""
    service = get_kms_service()

    try:
        key_id, encrypted_key = await service.encrypt_api_key(
            request.api_key, request.provider_name
        )

        return EncryptApiKeyResponse(
            key_id=key_id,
            encrypted_key=encrypted_key,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to encrypt API key: {e!s}",
        )


@router.post("/api-keys/decrypt")
async def decrypt_api_key(key_id: str, encrypted_key: str):
    """Decrypt an API key."""
    service = get_kms_service()

    try:
        api_key = await service.decrypt_api_key(key_id, encrypted_key)

        # Return masked key for security
        masked = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]

        return {
            "masked_key": masked,
            "length": len(api_key),
            "message": "API key decrypted successfully (masked for security)",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt API key: {e!s}",
        )


@router.get("/audit-log", response_model=list[AuditLogEntryResponse])
async def get_audit_log(
    key_id: str | None = Query(None, description="Filter by key ID"),
    action: str | None = Query(None, description="Filter by action"),
    start_time: datetime | None = Query(None, description="Filter from this time"),
    end_time: datetime | None = Query(None, description="Filter until this time"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
):
    """Get audit log entries."""
    service = get_kms_service()

    # Parse action if provided
    action_filter = None
    if action:
        try:
            action_filter = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}. Valid actions: {[a.value for a in AuditAction]}",
            )

    entries = service.get_audit_log(
        key_id=key_id,
        action=action_filter,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    return [
        AuditLogEntryResponse(
            entry_id=e.entry_id,
            timestamp=e.timestamp,
            action=e.action.value,
            key_id=e.key_id,
            user_id=e.user_id,
            ip_address=e.ip_address,
            success=e.success,
            error_message=e.error_message,
            details=e.details,
        )
        for e in entries
    ]


@router.get("/providers")
async def list_providers():
    """List available KMS providers."""
    return {
        "providers": [
            {
                "id": p.value,
                "name": p.name,
                "description": _get_provider_description(p),
            }
            for p in KMSProvider
        ]
    }


def _get_provider_description(provider: KMSProvider) -> str:
    """Get description for a provider."""
    descriptions = {
        KMSProvider.AWS_KMS: "Amazon Web Services Key Management Service",
        KMSProvider.AZURE_KEY_VAULT: "Microsoft Azure Key Vault",
        KMSProvider.HASHICORP_VAULT: "HashiCorp Vault Transit Secrets Engine",
        KMSProvider.LOCAL_HSM: "Local HSM simulation for development",
    }
    return descriptions.get(provider, "Unknown provider")


@router.get("/key-types")
async def list_key_types():
    """List available key types."""
    return {"key_types": [{"id": kt.value, "name": kt.name} for kt in KeyType]}


@router.get("/algorithms")
async def list_algorithms():
    """List available encryption algorithms."""
    return {"algorithms": [{"id": alg.value, "name": alg.name} for alg in KeyAlgorithm]}


@router.get("/health")
async def health_check():
    """Health check for KMS service."""
    service = get_kms_service()
    status_data = service.get_status()

    is_healthy = status_data.get("initialized", False)

    return {
        "healthy": is_healthy,
        "provider": status_data.get("provider"),
        "details": status_data,
    }
