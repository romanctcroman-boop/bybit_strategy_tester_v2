"""
Week 1, Day 6: Slack Integration
Real-time alert notifications via Slack webhooks
"""

import os
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class SlackColor(str, Enum):
    """Slack message colors"""
    GOOD = "good"  # Green
    WARNING = "warning"  # Orange
    DANGER = "danger"  # Red
    INFO = "#439FE0"  # Blue


class SlackService:
    """
    Slack integration for alert notifications.
    
    Features:
    - Alert notifications to #alerts channel
    - Status updates to #ops channel
    - Rich message formatting
    - @channel mentions for critical alerts
    - Attachment with context and actions
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize Slack service.
        
        Args:
            webhook_url: Slack incoming webhook URL
            enabled: Enable/disable Slack integration
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = enabled and os.getenv("SLACK_ENABLED", "true").lower() == "true"
        
        # Channel configuration
        self.alerts_channel = os.getenv("SLACK_ALERTS_CHANNEL", "#alerts")
        self.ops_channel = os.getenv("SLACK_OPS_CHANNEL", "#ops")
        self.database_channel = os.getenv("SLACK_DATABASE_CHANNEL", "#database")
        self.security_channel = os.getenv("SLACK_SECURITY_CHANNEL", "#security")
        
        if self.enabled and not self.webhook_url:
            logger.warning("Slack enabled but no webhook URL provided")
            self.enabled = False
    
    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        component: Optional[str] = None,
        channel: Optional[str] = None,
        mention_channel: bool = False,
        fields: Optional[List[Dict[str, str]]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        runbook_url: Optional[str] = None,
        dashboard_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send alert notification to Slack.
        
        Args:
            title: Alert title
            message: Alert message/description
            severity: Alert severity (critical, warning, info)
            component: Affected component
            channel: Slack channel (overrides default)
            mention_channel: Mention @channel for critical alerts
            fields: Additional fields to display
            actions: Action buttons
            runbook_url: Link to runbook
            dashboard_url: Link to dashboard
            
        Returns:
            Response with delivery status
            
        Example:
            >>> slack = SlackService()
            >>> result = slack.send_alert(
            ...     title="High CPU Usage",
            ...     message="CPU usage is 85% on backend-01",
            ...     severity="warning",
            ...     component="backend",
            ...     fields=[
            ...         {"title": "Current CPU", "value": "85%", "short": True},
            ...         {"title": "Threshold", "value": "80%", "short": True}
            ...     ],
            ...     runbook_url="https://runbook.example.com/high-cpu"
            ... )
        """
        if not self.enabled:
            logger.warning("Slack disabled, skipping alert")
            return {
                "status": "disabled",
                "message": "Slack integration is disabled"
            }
        
        # Determine channel based on severity/component
        if not channel:
            if severity == "critical":
                channel = self.alerts_channel
            elif component == "database":
                channel = self.database_channel
            elif component == "security":
                channel = self.security_channel
            else:
                channel = self.alerts_channel
        
        # Determine color
        color_map = {
            "critical": SlackColor.DANGER.value,
            "error": SlackColor.DANGER.value,
            "warning": SlackColor.WARNING.value,
            "info": SlackColor.INFO.value
        }
        color = color_map.get(severity.lower(), SlackColor.INFO.value)
        
        # Determine emoji
        emoji_map = {
            "critical": ":fire:",
            "error": ":x:",
            "warning": ":warning:",
            "info": ":information_source:"
        }
        emoji = emoji_map.get(severity.lower(), ":bell:")
        
        # Build message text
        text = message
        if mention_channel and severity == "critical":
            text = f"<!channel> {message}"
        
        # Build attachment fields
        attachment_fields = fields or []
        
        if component:
            attachment_fields.append({
                "title": "Component",
                "value": component,
                "short": True
            })
        
        attachment_fields.append({
            "title": "Severity",
            "value": severity.upper(),
            "short": True
        })
        
        attachment_fields.append({
            "title": "Timestamp",
            "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "short": True
        })
        
        # Build actions
        action_buttons = []
        
        if runbook_url:
            action_buttons.append({
                "type": "button",
                "text": "📖 View Runbook",
                "url": runbook_url
            })
        
        if dashboard_url:
            action_buttons.append({
                "type": "button",
                "text": "📊 View Dashboard",
                "url": dashboard_url
            })
        
        if actions:
            action_buttons.extend(actions)
        
        # Build Slack payload
        payload = {
            "channel": channel,
            "username": "Alertmanager",
            "icon_emoji": emoji,
            "text": f"{emoji} *{title}*",
            "attachments": [
                {
                    "color": color,
                    "text": text,
                    "fields": attachment_fields,
                    "footer": "Bybit Strategy Tester",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }
        
        # Add action buttons if present
        if action_buttons:
            payload["attachments"][0]["actions"] = action_buttons
        
        try:
            logger.info(f"Sending Slack alert to {channel}: {title}")
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            response.raise_for_status()
            
            logger.info(f"Slack alert sent successfully to {channel}")
            
            return {
                "success": True,
                "channel": channel,
                "title": title,
                "severity": severity,
                "status": "sent"
            }
            
        except requests.exceptions.Timeout:
            logger.error("Slack API timeout")
            return {
                "success": False,
                "error": "API timeout",
                "message": "Slack API request timed out"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Slack API error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to send alert: {e}"
            }
    
    def send_critical_alert(
        self,
        title: str,
        message: str,
        component: str,
        impact: str,
        action: str,
        runbook_url: Optional[str] = None,
        dashboard_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send critical alert with @channel mention.
        
        Args:
            title: Alert title
            message: Alert description
            component: Affected component
            impact: Impact description
            action: Required actions
            runbook_url: Runbook URL
            dashboard_url: Dashboard URL
            
        Returns:
            Response with delivery status
        """
        fields = [
            {"title": "Impact", "value": impact, "short": False},
            {"title": "Required Actions", "value": action, "short": False}
        ]
        
        return self.send_alert(
            title=f"🚨 CRITICAL: {title}",
            message=message,
            severity="critical",
            component=component,
            mention_channel=True,
            fields=fields,
            runbook_url=runbook_url,
            dashboard_url=dashboard_url
        )
    
    def send_warning_alert(
        self,
        title: str,
        message: str,
        component: str,
        recommended_action: Optional[str] = None,
        runbook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send warning alert.
        
        Args:
            title: Alert title
            message: Alert description
            component: Affected component
            recommended_action: Recommended actions
            runbook_url: Runbook URL
            
        Returns:
            Response with delivery status
        """
        fields = []
        if recommended_action:
            fields.append({
                "title": "Recommended Action",
                "value": recommended_action,
                "short": False
            })
        
        return self.send_alert(
            title=f"⚠️ WARNING: {title}",
            message=message,
            severity="warning",
            component=component,
            fields=fields,
            runbook_url=runbook_url
        )
    
    def send_info_message(
        self,
        title: str,
        message: str,
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send informational message to ops channel.
        
        Args:
            title: Message title
            message: Message content
            channel: Override default ops channel
            
        Returns:
            Response with delivery status
        """
        return self.send_alert(
            title=f"ℹ️ {title}",
            message=message,
            severity="info",
            channel=channel or self.ops_channel
        )
    
    def send_resolved_alert(
        self,
        title: str,
        resolution_note: str,
        component: str,
        duration: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send alert resolution notification.
        
        Args:
            title: Original alert title
            resolution_note: How the issue was resolved
            component: Affected component
            duration: How long the incident lasted
            
        Returns:
            Response with delivery status
        """
        fields = [
            {"title": "Resolution", "value": resolution_note, "short": False}
        ]
        
        if duration:
            fields.append({
                "title": "Duration",
                "value": duration,
                "short": True
            })
        
        return self.send_alert(
            title=f"✅ RESOLVED: {title}",
            message=f"Issue has been resolved: {resolution_note}",
            severity="info",
            component=component,
            fields=fields
        )
    
    def send_deployment_notification(
        self,
        version: str,
        environment: str,
        deployed_by: str,
        changes: Optional[List[str]] = None,
        rollback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send deployment notification.
        
        Args:
            version: Deployed version
            environment: Target environment
            deployed_by: Who triggered the deployment
            changes: List of changes
            rollback_url: URL to trigger rollback
            
        Returns:
            Response with delivery status
        """
        fields = [
            {"title": "Version", "value": version, "short": True},
            {"title": "Environment", "value": environment, "short": True},
            {"title": "Deployed By", "value": deployed_by, "short": True}
        ]
        
        message = f"Deployed version {version} to {environment}"
        
        if changes:
            changes_text = "\n".join(f"• {change}" for change in changes[:5])
            if len(changes) > 5:
                changes_text += f"\n• ... and {len(changes) - 5} more"
            fields.append({
                "title": "Changes",
                "value": changes_text,
                "short": False
            })
        
        actions = []
        if rollback_url:
            actions.append({
                "type": "button",
                "text": "🔄 Rollback",
                "url": rollback_url,
                "style": "danger"
            })
        
        return self.send_alert(
            title="🚀 Deployment Complete",
            message=message,
            severity="info",
            channel=self.ops_channel,
            fields=fields,
            actions=actions
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get Slack service status.
        
        Returns:
            Service status information
        """
        return {
            "enabled": self.enabled,
            "configured": self.webhook_url is not None,
            "channels": {
                "alerts": self.alerts_channel,
                "ops": self.ops_channel,
                "database": self.database_channel,
                "security": self.security_channel
            },
            "webhook_url_present": bool(self.webhook_url)
        }


# Global Slack service instance
slack_service = SlackService()
