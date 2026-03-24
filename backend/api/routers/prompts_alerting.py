"""
Prompts Alerting API Router

Provides REST API for alerting:
- GET /api/v1/prompts/alerts - Get active alerts
- GET /api/v1/prompts/alerts/summary - Alert summary
- POST /api/v1/prompts/alerts/check - Check alerts now
- POST /api/v1/prompts/alerts/{alert_id}/acknowledge - Acknowledge alert
- POST /api/v1/prompts/alerts/{alert_id}/resolve - Resolve alert
- DELETE /api/v1/prompts/alerts/resolved - Clear resolved alerts
"""

from fastapi import APIRouter, HTTPException

from backend.monitoring.prompts_alerting import PromptsAlerting

router = APIRouter(prefix="/api/v1/prompts/alerts", tags=["Prompts Alerting"])

# Lazy initialization
_alerting: PromptsAlerting | None = None


def get_alerting() -> PromptsAlerting:
    """Get or create alerting instance."""
    global _alerting
    if _alerting is None:
        _alerting = PromptsAlerting()
    return _alerting


@router.get("")
def get_alerts() -> dict:
    """
    Get active alerts.

    Returns:
        List of active alerts
    """
    alerting = get_alerting()
    alerts = alerting.get_active_alerts()

    return {
        "total": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }


@router.get("/summary")
def get_alert_summary() -> dict:
    """
    Get alert summary.

    Returns:
        Summary statistics
    """
    alerting = get_alerting()
    return alerting.get_alert_summary()


@router.post("/check")
def check_alerts() -> dict:
    """
    Check alerts now.

    Returns:
        Triggered alerts
    """
    alerting = get_alerting()
    alerts = alerting.check_alerts()

    return {
        "triggered": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str) -> dict:
    """
    Acknowledge an alert.

    Args:
        alert_id: Alert ID

    Returns:
        Status
    """
    alerting = get_alerting()

    if not alerting.acknowledge_alert(alert_id):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {
        "success": True,
        "alert_id": alert_id,
        "acknowledged": True,
    }


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: str) -> dict:
    """
    Resolve an alert.

    Args:
        alert_id: Alert ID

    Returns:
        Status
    """
    alerting = get_alerting()

    if not alerting.resolve_alert(alert_id):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {
        "success": True,
        "alert_id": alert_id,
        "resolved": True,
    }


@router.delete("/resolved")
def clear_resolved_alerts() -> dict:
    """
    Clear resolved alerts.

    Returns:
        Number of cleared alerts
    """
    alerting = get_alerting()
    count = alerting.clear_resolved_alerts()

    return {
        "success": True,
        "cleared": count,
    }


@router.get("/history")
def get_alert_history(limit: int = 100) -> dict:
    """
    Get alert history.

    Args:
        limit: Maximum alerts to return

    Returns:
        Alert history
    """
    alerting = get_alerting()
    history = alerting.get_alert_history(limit)

    return {
        "total": len(history),
        "alerts": [a.to_dict() for a in history],
    }
