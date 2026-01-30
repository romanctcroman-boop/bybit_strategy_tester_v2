"""
Security Services API Router.

Provides REST API endpoints for:
- Key Usage Audit Logging
- Secure Configuration Handler
- IP Whitelisting

SECURITY: All endpoints require security API key authentication.
"""

import hmac
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from backend.services.ip_whitelist import (
    ActionType,
    get_ip_whitelist_service,
)
from backend.services.key_audit import (
    AlertSeverity,
    KeyAccessType,
    KeyProvider,
    get_key_audit_service,
)
from backend.services.secure_config import (
    ConfigSeverity,
    ConfigType,
    ConfigVariable,
    get_config_handler,
)

logger = logging.getLogger(__name__)

# Security API key header
security_api_key_header = APIKeyHeader(name="X-Security-Key", auto_error=False)


async def verify_security_key(api_key: str = Depends(security_api_key_header)) -> str:
    """
    Verify security API key for protected endpoints.

    Uses constant-time comparison to prevent timing attacks.

    Raises:
        HTTPException: If key is missing, not configured, or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check SECURITY_API_KEY or fallback to ADMIN_API_KEY
    expected_key = os.environ.get("SECURITY_API_KEY") or os.environ.get("ADMIN_API_KEY")
    if not expected_key:
        logger.error("SECURITY_API_KEY or ADMIN_API_KEY not configured in environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security authentication not configured",
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(api_key.encode(), expected_key.encode()):
        logger.warning("Invalid security key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid security key",
        )

    return api_key


# All security routes require authentication
router = APIRouter(prefix="/security", tags=["security"], dependencies=[Depends(verify_security_key)])


# ============================================
# Request/Response Models
# ============================================


class LogKeyAccessRequest(BaseModel):
    """Request to log key access."""

    key_id: str = Field(..., description="Key identifier")
    key_provider: KeyProvider = Field(..., description="Key provider")
    access_type: KeyAccessType = Field(..., description="Type of access")
    user_id: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    metadata: dict = Field(default_factory=dict)


class AddIPRuleRequest(BaseModel):
    """Request to add an IP rule."""

    ip_pattern: str = Field(..., description="IP address or CIDR")
    is_whitelist: bool = Field(default=True)
    action_types: list[str] = Field(default=["all"])
    description: str = ""
    expires_in_hours: Optional[int] = None
    created_by: Optional[str] = None


class CheckIPRequest(BaseModel):
    """Request to check an IP."""

    ip_address: str = Field(..., description="IP to check")
    action_type: str = Field(default="all")


class LoadEnvRequest(BaseModel):
    """Request to load .env file."""

    file_path: str = Field(..., description="Path to .env file")


class AddVariableRequest(BaseModel):
    """Request to add a variable definition."""

    name: str
    config_type: str = "string"
    required: bool = False
    default_value: Optional[str] = None
    description: str = ""
    is_sensitive: bool = False


# ============================================
# Key Audit Endpoints
# ============================================


@router.get("/audit/status")
async def get_audit_status():
    """Get key audit service status."""
    service = get_key_audit_service()
    return service.get_status()


@router.get("/audit/summary")
async def get_audit_summary():
    """Get audit summary."""
    service = get_key_audit_service()
    return service.get_summary()


@router.post("/audit/log")
async def log_key_access(request: LogKeyAccessRequest, req: Request):
    """Log a key access event."""
    service = get_key_audit_service()

    # Get IP from request
    ip_address = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    event = service.log_access(
        key_id=request.key_id,
        key_provider=request.key_provider,
        access_type=request.access_type,
        user_id=request.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_path=str(req.url.path),
        success=request.success,
        error_message=request.error_message,
        latency_ms=request.latency_ms,
        metadata=request.metadata,
    )

    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat(),
        "message": "Access logged",
    }


@router.get("/audit/events")
async def get_audit_events(
    key_id: Optional[str] = Query(None),
    access_type: Optional[str] = Query(None),
    success_only: Optional[bool] = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Get audit events."""
    service = get_key_audit_service()

    access_type_filter = None
    if access_type:
        try:
            access_type_filter = KeyAccessType(access_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid access type: {access_type}",
            )

    events = service.get_events(
        key_id=key_id,
        access_type=access_type_filter,
        success_only=success_only,
        limit=limit,
    )

    return [
        {
            "event_id": e.event_id,
            "timestamp": e.timestamp.isoformat(),
            "key_id": e.key_id,
            "key_provider": e.key_provider.value,
            "access_type": e.access_type.value,
            "user_id": e.user_id,
            "ip_address": e.ip_address,
            "success": e.success,
            "error_message": e.error_message,
            "latency_ms": e.latency_ms,
        }
        for e in events
    ]


@router.get("/audit/anomalies")
async def get_anomalies(
    key_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    unacknowledged_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Get detected anomalies."""
    service = get_key_audit_service()

    severity_filter = None
    if severity:
        try:
            severity_filter = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}",
            )

    anomalies = service.get_anomalies(
        key_id=key_id,
        severity=severity_filter,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )

    return [
        {
            "anomaly_id": a.anomaly_id,
            "detected_at": a.detected_at.isoformat(),
            "key_id": a.key_id,
            "anomaly_type": a.anomaly_type,
            "severity": a.severity.value,
            "description": a.description,
            "acknowledged": a.acknowledged,
            "evidence": a.evidence,
        }
        for a in anomalies
    ]


@router.post("/audit/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(anomaly_id: str):
    """Acknowledge an anomaly."""
    service = get_key_audit_service()
    success = service.acknowledge_anomaly(anomaly_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly not found: {anomaly_id}",
        )

    return {"message": f"Anomaly acknowledged: {anomaly_id}"}


@router.get("/audit/stats/{key_id}")
async def get_key_stats(key_id: str):
    """Get usage statistics for a key."""
    service = get_key_audit_service()
    stats = service.get_key_stats(key_id)

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stats for key: {key_id}",
        )

    return {
        "key_id": stats.key_id,
        "key_provider": stats.key_provider.value,
        "total_accesses": stats.total_accesses,
        "successful_accesses": stats.successful_accesses,
        "failed_accesses": stats.failed_accesses,
        "last_access": stats.last_access.isoformat() if stats.last_access else None,
        "first_access": stats.first_access.isoformat() if stats.first_access else None,
        "unique_users": stats.unique_users,
        "unique_ips": stats.unique_ips,
        "avg_latency_ms": stats.avg_latency_ms,
        "accesses_by_type": stats.accesses_by_type,
        "accesses_by_hour": stats.accesses_by_hour,
    }


@router.get("/audit/compliance-report")
async def generate_compliance_report(
    days: int = Query(default=30, ge=1, le=365, description="Days to include"),
):
    """Generate a compliance report."""
    service = get_key_audit_service()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    report = service.generate_compliance_report(start_date, end_date)
    return report


# ============================================
# IP Whitelist Endpoints
# ============================================


@router.get("/ip/status")
async def get_ip_status():
    """Get IP whitelist service status."""
    service = get_ip_whitelist_service()
    return service.get_status()


@router.get("/ip/summary")
async def get_ip_summary():
    """Get IP whitelist summary."""
    service = get_ip_whitelist_service()
    return service.get_summary()


@router.post("/ip/check")
async def check_ip(request: CheckIPRequest):
    """Check if an IP is allowed."""
    service = get_ip_whitelist_service()

    try:
        action_type = ActionType(request.action_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {request.action_type}",
        )

    is_allowed, reason = service.check_ip(request.ip_address, action_type)

    return {
        "ip_address": request.ip_address,
        "action_type": request.action_type,
        "is_allowed": is_allowed,
        "reason": reason,
    }


@router.post("/ip/rules", status_code=status.HTTP_201_CREATED)
async def add_ip_rule(request: AddIPRuleRequest):
    """Add an IP rule."""
    service = get_ip_whitelist_service()

    try:
        action_types = [ActionType(at) for at in request.action_types]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {str(e)}",
        )

    expires_at = None
    if request.expires_in_hours:
        expires_at = datetime.now() + timedelta(hours=request.expires_in_hours)

    try:
        rule = service.add_rule(
            ip_pattern=request.ip_pattern,
            is_whitelist=request.is_whitelist,
            action_types=action_types,
            description=request.description,
            expires_at=expires_at,
            created_by=request.created_by,
        )

        return {
            "rule_id": rule.rule_id,
            "ip_pattern": rule.ip_pattern,
            "is_whitelist": rule.is_whitelist,
            "message": "Rule added",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/ip/rules")
async def get_ip_rules(
    is_whitelist: Optional[bool] = Query(None),
    enabled_only: bool = Query(default=False),
):
    """Get IP rules."""
    service = get_ip_whitelist_service()

    rules = service.get_rules(
        is_whitelist=is_whitelist,
        enabled_only=enabled_only,
    )

    return [
        {
            "rule_id": r.rule_id,
            "ip_pattern": r.ip_pattern,
            "is_whitelist": r.is_whitelist,
            "action_types": [at.value for at in r.action_types],
            "description": r.description,
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "is_enabled": r.is_enabled,
        }
        for r in rules
    ]


@router.delete("/ip/rules/{rule_id}")
async def remove_ip_rule(rule_id: str):
    """Remove an IP rule."""
    service = get_ip_whitelist_service()
    success = service.remove_rule(rule_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule not found: {rule_id}",
        )

    return {"message": f"Rule removed: {rule_id}"}


@router.post("/ip/rules/{rule_id}/enable")
async def enable_ip_rule(rule_id: str):
    """Enable an IP rule."""
    service = get_ip_whitelist_service()
    success = service.enable_rule(rule_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule not found: {rule_id}",
        )

    return {"message": f"Rule enabled: {rule_id}"}


@router.post("/ip/rules/{rule_id}/disable")
async def disable_ip_rule(rule_id: str):
    """Disable an IP rule."""
    service = get_ip_whitelist_service()
    success = service.disable_rule(rule_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule not found: {rule_id}",
        )

    return {"message": f"Rule disabled: {rule_id}"}


@router.get("/ip/blocked")
async def get_blocked_requests(
    ip_address: Optional[str] = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Get blocked request records."""
    service = get_ip_whitelist_service()

    records = service.get_blocked_requests(
        ip_address=ip_address,
        limit=limit,
    )

    return [
        {
            "request_id": r.request_id,
            "timestamp": r.timestamp.isoformat(),
            "ip_address": r.ip_address,
            "reason": r.reason.value,
            "action_type": r.action_type.value,
            "request_path": r.request_path,
        }
        for r in records
    ]


@router.get("/ip/auto-blocked")
async def get_auto_blocked():
    """Get auto-blocked IPs."""
    service = get_ip_whitelist_service()
    blocked = service.get_auto_blocked()

    return [{"ip_address": ip, "blocked_until": until.isoformat()} for ip, until in blocked.items()]


@router.post("/ip/unblock/{ip_address}")
async def unblock_ip(ip_address: str):
    """Unblock an IP address."""
    service = get_ip_whitelist_service()
    success = service.unblock_ip(ip_address)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP not found in auto-blocked list: {ip_address}",
        )

    return {"message": f"IP unblocked: {ip_address}"}


# ============================================
# Secure Config Endpoints
# ============================================


@router.get("/config/status")
async def get_config_status():
    """Get secure config handler status."""
    handler = get_config_handler()
    return handler.get_status()


@router.post("/config/load")
async def load_env_file(request: LoadEnvRequest):
    """Load an .env file."""
    handler = get_config_handler()

    file_path = Path(request.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.file_path}",
        )

    values = handler.load_env_file(file_path)

    return {
        "file_path": request.file_path,
        "variables_loaded": len(values),
        "message": "Configuration loaded",
    }


@router.post("/config/validate")
async def validate_config():
    """Validate current configuration."""
    handler = get_config_handler()
    result = handler.validate_config()

    return {
        "is_valid": result.is_valid,
        "variables_found": result.variables_found,
        "variables_missing": result.variables_missing,
        "sensitive_exposed": result.sensitive_exposed,
        "issues": [
            {
                "issue_id": i.issue_id,
                "severity": i.severity.value,
                "variable": i.variable,
                "message": i.message,
                "recommendation": i.recommendation,
            }
            for i in result.issues
        ],
    }


@router.get("/config/masked")
async def get_masked_config():
    """Get configuration with sensitive values masked."""
    handler = get_config_handler()
    return handler.get_masked_config()


@router.get("/config/template")
async def get_env_template():
    """Generate an .env template."""
    handler = get_config_handler()
    template = handler.get_env_template()

    return {"template": template}


@router.post("/config/variables")
async def add_variable_definition(request: AddVariableRequest):
    """Add a variable definition."""
    handler = get_config_handler()

    try:
        config_type = ConfigType(request.config_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config type: {request.config_type}",
        )

    variable = ConfigVariable(
        name=request.name,
        config_type=config_type,
        required=request.required,
        default_value=request.default_value,
        description=request.description,
        is_sensitive=request.is_sensitive,
    )

    handler.add_variable(variable)

    return {"message": f"Variable definition added: {request.name}"}


@router.get("/config/variables/{name}")
async def get_variable_info(name: str):
    """Get information about a variable."""
    handler = get_config_handler()
    info = handler.get_variable_info(name)

    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variable not found: {name}",
        )

    return info


@router.get("/config/issues")
async def get_config_issues(
    severity: Optional[str] = Query(None),
):
    """Get configuration issues."""
    handler = get_config_handler()

    severity_filter = None
    if severity:
        try:
            severity_filter = ConfigSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}",
            )

    issues = handler.get_issues(severity=severity_filter)

    return [
        {
            "issue_id": i.issue_id,
            "severity": i.severity.value,
            "variable": i.variable,
            "message": i.message,
            "recommendation": i.recommendation,
            "file_path": i.file_path,
        }
        for i in issues
    ]


@router.get("/config/checksum")
async def get_config_checksum():
    """Get configuration checksum."""
    handler = get_config_handler()
    return {"checksum": handler.get_checksum()}


# ============================================
# Combined Security Health
# ============================================


@router.get("/health")
async def security_health_check():
    """Combined security health check."""
    audit_service = get_key_audit_service()
    ip_service = get_ip_whitelist_service()
    config_handler = get_config_handler()

    audit_status = audit_service.get_status()
    ip_status = ip_service.get_status()
    config_status = config_handler.get_status()

    is_healthy = all(
        [
            audit_status.get("enabled", True),
            ip_status.get("operational", True),
        ]
    )

    return {
        "healthy": is_healthy,
        "services": {
            "key_audit": audit_status,
            "ip_whitelist": ip_status,
            "secure_config": config_status,
        },
    }
