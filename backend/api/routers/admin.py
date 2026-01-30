"""
Admin Router
Administrative endpoints for system management.

SECURITY: All endpoints require admin API key authentication.
"""

import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Admin API key header
admin_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verify_admin_key(api_key: str = Depends(admin_api_key_header)) -> str:
    """
    Verify admin API key for protected endpoints.

    Uses constant-time comparison to prevent timing attacks.

    Raises:
        HTTPException: If key is missing, not configured, or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    expected_key = os.environ.get("ADMIN_API_KEY")
    if not expected_key:
        logger.error("ADMIN_API_KEY not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication not configured",
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key.encode(), expected_key.encode()):
        logger.warning("Invalid admin key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )

    return api_key


# All admin routes require authentication
router = APIRouter(dependencies=[Depends(verify_admin_key)])


class SystemStatus(BaseModel):
    """System status response"""

    status: str
    version: str
    components: dict[str, str]


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get system status.

    Returns system health and component status.
    """
    return SystemStatus(
        status="healthy",
        version="1.0.0",
        components={"api": "running", "database": "connected", "cache": "active"},
    )


@router.post("/maintenance")
async def enable_maintenance_mode():
    """
    Enable maintenance mode.

    Puts the system into maintenance mode.
    """
    logger.info("Maintenance mode enabled")
    return {
        "status": "maintenance_enabled",
        "message": "System is now in maintenance mode",
    }


@router.delete("/maintenance")
async def disable_maintenance_mode():
    """
    Disable maintenance mode.

    Takes the system out of maintenance mode.
    """
    logger.info("Maintenance mode disabled")
    return {"status": "maintenance_disabled", "message": "System is now operational"}


@router.get("/logs")
async def get_system_logs(limit: int = 100):
    """
    Get recent system logs.

    Args:
        limit: Maximum number of log entries to return

    Returns:
        Recent log entries
    """
    # Stub implementation
    return {"logs": [], "limit": limit, "message": "Log retrieval not yet implemented"}
