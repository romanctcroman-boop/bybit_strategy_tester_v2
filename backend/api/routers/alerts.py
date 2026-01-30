"""
Alerting API Router.

Provides endpoints for:
- Testing alerts
- Viewing alert configuration status
- Sending manual alerts
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.services.alerting import (
    Alert,
    AlertLevel,
    get_alerting_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertRequest(BaseModel):
    """Request model for sending an alert."""

    level: str = Field(
        default="warning",
        description="Alert level: info, warning, or critical",
    )
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    source: str = Field(default="api", description="Source system/component")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class AlertResponse(BaseModel):
    """Response model for alert operations."""

    success: bool
    message: str
    alert_id: Optional[str] = None
    channels_notified: list[str] = []


class AlertConfigStatus(BaseModel):
    """Status of alerting configuration."""

    slack_enabled: bool
    slack_configured: bool
    slack_channel: str
    telegram_enabled: bool
    telegram_configured: bool
    telegram_chat_count: int
    email_enabled: bool
    email_configured: bool
    email_recipients: int
    rate_limit_seconds: int


class TestAlertResponse(BaseModel):
    """Response for test alert endpoint."""

    test_sent: bool
    slack_result: Optional[bool] = None
    telegram_result: Optional[bool] = None
    email_result: Optional[bool] = None
    message: str


@router.get("/status", response_model=AlertConfigStatus)
async def get_alerting_status() -> AlertConfigStatus:
    """
    Get the current alerting configuration status.

    Returns which channels are enabled and configured.
    """
    service = get_alerting_service()
    config = service.config

    return AlertConfigStatus(
        slack_enabled=config.slack_enabled,
        slack_configured=bool(config.slack_webhook_url),
        slack_channel=config.slack_channel,
        telegram_enabled=config.telegram_enabled,
        telegram_configured=bool(
            config.telegram_bot_token and config.telegram_chat_ids
        ),
        telegram_chat_count=len(config.telegram_chat_ids),
        email_enabled=config.email_enabled,
        email_configured=all(
            [
                config.smtp_host,
                config.smtp_username,
                config.smtp_password,
                config.smtp_from_email,
                config.smtp_to_emails,
            ]
        ),
        email_recipients=len(config.smtp_to_emails),
        rate_limit_seconds=config.rate_limit_seconds,
    )


@router.post("/send", response_model=AlertResponse)
async def send_alert(
    request: AlertRequest,
    background_tasks: BackgroundTasks,
) -> AlertResponse:
    """
    Send an alert through configured channels.

    - **level**: Alert severity (info, warning, critical)
    - **title**: Short alert title
    - **message**: Detailed alert message
    - **source**: Source system/component
    - **metadata**: Additional key-value data
    """
    try:
        level = AlertLevel(request.level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid alert level: {request.level}. Must be one of: info, warning, critical",
        )

    service = get_alerting_service()

    # Send alert
    success = await service.send_alert(
        level=level,
        title=request.title,
        message=request.message,
        source=request.source,
        metadata=request.metadata,
    )

    channels = []
    if service.config.slack_enabled:
        channels.append("slack")
    if service.config.email_enabled:
        channels.append("email")

    return AlertResponse(
        success=success,
        message="Alert sent successfully"
        if success
        else "Alert sending failed or was rate-limited",
        channels_notified=channels if success else [],
    )


@router.post("/test", response_model=TestAlertResponse)
async def test_alerting() -> TestAlertResponse:
    """
    Send a test alert to verify configuration.

    Sends a test message to all configured channels.
    """
    service = get_alerting_service()
    config = service.config

    if not config.slack_enabled and not config.email_enabled:
        return TestAlertResponse(
            test_sent=False,
            message="No alerting channels are enabled. Set ALERT_SLACK_ENABLED=true or ALERT_EMAIL_ENABLED=true in environment.",
        )

    # Create test alert
    test_alert = Alert(
        level=AlertLevel.INFO,
        title="Test Alert",
        message="This is a test alert from Bybit Strategy Tester. If you received this, alerting is configured correctly!",
        source="alerting_api_test",
        metadata={
            "test": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": "production",
        },
    )

    slack_result = None
    email_result = None

    if config.slack_enabled:
        slack_result = await service._send_slack(test_alert)

    if config.email_enabled:
        email_result = await service._send_email(test_alert)

    results = []
    if slack_result is True:
        results.append("Slack")
    if email_result is True:
        results.append("Email")

    if results:
        message = f"Test alert sent successfully via: {', '.join(results)}"
    else:
        message = (
            "Test alert failed to send via any channel. Check configuration and logs."
        )

    return TestAlertResponse(
        test_sent=bool(results),
        slack_result=slack_result,
        email_result=email_result,
        message=message,
    )


@router.get("/levels")
async def list_alert_levels() -> dict:
    """
    List available alert levels with descriptions.
    """
    return {
        "levels": [
            {
                "name": "info",
                "description": "Informational alerts for successful operations",
                "emoji": "ℹ️",
                "color": "#36a64f",
            },
            {
                "name": "warning",
                "description": "Warning alerts for non-critical issues that need attention",
                "emoji": "⚠️",
                "color": "#ffa500",
            },
            {
                "name": "critical",
                "description": "Critical alerts for system failures or urgent issues",
                "emoji": "🚨",
                "color": "#ff0000",
            },
        ]
    }


@router.post("/critical", response_model=AlertResponse)
async def send_critical_alert(
    title: str,
    message: str,
    source: str = "api",
) -> AlertResponse:
    """
    Quick endpoint to send a critical alert.

    Critical alerts bypass rate limiting.
    """
    service = get_alerting_service()
    success = await service.critical(title, message, source)

    return AlertResponse(
        success=success,
        message="Critical alert sent" if success else "Failed to send critical alert",
        channels_notified=["slack", "email"] if success else [],
    )
