"""
Week 1, Day 6: PagerDuty Integration
Incident management and escalation via PagerDuty
"""

import os
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    """PagerDuty severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class EventAction(str, Enum):
    """PagerDuty event actions"""
    TRIGGER = "trigger"
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"


class PagerDutyService:
    """
    PagerDuty integration for incident management.
    
    Features:
    - Incident creation with severity levels
    - Automatic escalation
    - Incident acknowledgment
    - Incident resolution
    - Deduplication
    """
    
    def __init__(
        self,
        integration_key: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize PagerDuty service.
        
        Args:
            integration_key: PagerDuty integration key
            enabled: Enable/disable PagerDuty integration
        """
        self.integration_key = integration_key or os.getenv("PAGERDUTY_INTEGRATION_KEY")
        self.enabled = enabled and os.getenv("PAGERDUTY_ENABLED", "true").lower() == "true"
        self.api_url = "https://events.pagerduty.com/v2/enqueue"
        
        if self.enabled and not self.integration_key:
            logger.warning("PagerDuty enabled but no integration key provided")
            self.enabled = False
    
    def trigger_incident(
        self,
        summary: str,
        severity: Severity,
        source: str,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        custom_details: Optional[Dict[str, Any]] = None,
        links: Optional[List[Dict[str, str]]] = None,
        dedup_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger a PagerDuty incident.
        
        Args:
            summary: Brief description of the incident
            severity: Incident severity (critical, error, warning, info)
            source: Source of the alert (e.g., "prometheus", "application")
            component: Affected component (e.g., "database", "backend")
            details: Additional details about the incident
            custom_details: Custom key-value pairs
            links: List of related links (runbooks, dashboards)
            dedup_key: Deduplication key (prevents duplicate incidents)
            
        Returns:
            API response with incident details
            
        Example:
            >>> pd = PagerDutyService()
            >>> result = pd.trigger_incident(
            ...     summary="Database connection pool exhausted",
            ...     severity=Severity.CRITICAL,
            ...     source="prometheus",
            ...     component="database",
            ...     details={
            ...         "pool_size": 20,
            ...         "active_connections": 19,
            ...         "threshold": 0.90
            ...     },
            ...     links=[
            ...         {"href": "https://runbook.example.com/db-pool", "text": "Runbook"}
            ...     ],
            ...     dedup_key="db-pool-exhausted-prod"
            ... )
        """
        if not self.enabled:
            logger.warning("PagerDuty disabled, skipping incident creation")
            return {
                "status": "disabled",
                "message": "PagerDuty integration is disabled"
            }
        
        # Generate dedup key if not provided
        if not dedup_key:
            dedup_key = f"{source}-{component}-{datetime.utcnow().strftime('%Y%m%d')}"
        
        # Build event payload
        payload = {
            "routing_key": self.integration_key,
            "event_action": EventAction.TRIGGER.value,
            "dedup_key": dedup_key,
            "payload": {
                "summary": summary,
                "severity": severity.value,
                "source": source,
                "timestamp": datetime.utcnow().isoformat(),
                "component": component,
                "group": component,
                "class": "alert",
                "custom_details": custom_details or {}
            }
        }
        
        # Add optional details
        if details:
            payload["payload"]["custom_details"].update(details)
        
        # Add links
        if links:
            payload["links"] = links
        
        try:
            logger.info(f"Triggering PagerDuty incident: {summary} (dedup_key: {dedup_key})")
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(
                f"PagerDuty incident triggered successfully: {result.get('dedup_key')} "
                f"(status: {result.get('status')})"
            )
            
            return {
                "success": True,
                "dedup_key": result.get("dedup_key"),
                "status": result.get("status"),
                "message": result.get("message"),
                "incident_key": result.get("dedup_key")
            }
            
        except requests.exceptions.Timeout:
            logger.error("PagerDuty API timeout")
            return {
                "success": False,
                "error": "API timeout",
                "message": "PagerDuty API request timed out"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"PagerDuty API error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create incident: {e}"
            }
    
    def acknowledge_incident(
        self,
        dedup_key: str,
        source: str = "api"
    ) -> Dict[str, Any]:
        """
        Acknowledge a PagerDuty incident.
        
        Args:
            dedup_key: Deduplication key of the incident
            source: Source of the acknowledgment
            
        Returns:
            API response
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "PagerDuty integration is disabled"
            }
        
        payload = {
            "routing_key": self.integration_key,
            "event_action": EventAction.ACKNOWLEDGE.value,
            "dedup_key": dedup_key
        }
        
        try:
            logger.info(f"Acknowledging PagerDuty incident: {dedup_key}")
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"PagerDuty incident acknowledged: {dedup_key}")
            
            return {
                "success": True,
                "dedup_key": result.get("dedup_key"),
                "status": result.get("status"),
                "message": result.get("message")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PagerDuty acknowledge error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to acknowledge incident: {e}"
            }
    
    def resolve_incident(
        self,
        dedup_key: str,
        resolution_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve a PagerDuty incident.
        
        Args:
            dedup_key: Deduplication key of the incident
            resolution_note: Optional resolution note
            
        Returns:
            API response
            
        Example:
            >>> pd = PagerDutyService()
            >>> result = pd.resolve_incident(
            ...     dedup_key="db-pool-exhausted-prod",
            ...     resolution_note="Connection pool size increased to 30"
            ... )
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "PagerDuty integration is disabled"
            }
        
        payload = {
            "routing_key": self.integration_key,
            "event_action": EventAction.RESOLVE.value,
            "dedup_key": dedup_key
        }
        
        if resolution_note:
            payload["payload"] = {
                "summary": resolution_note,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        try:
            logger.info(f"Resolving PagerDuty incident: {dedup_key}")
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"PagerDuty incident resolved: {dedup_key}")
            
            return {
                "success": True,
                "dedup_key": result.get("dedup_key"),
                "status": result.get("status"),
                "message": result.get("message")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PagerDuty resolve error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to resolve incident: {e}"
            }
    
    def send_change_event(
        self,
        summary: str,
        timestamp: Optional[datetime] = None,
        custom_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a change event to PagerDuty.
        
        Useful for correlating incidents with deployments or configuration changes.
        
        Args:
            summary: Description of the change
            timestamp: When the change occurred
            custom_details: Additional change details
            
        Returns:
            API response
            
        Example:
            >>> pd = PagerDutyService()
            >>> result = pd.send_change_event(
            ...     summary="Deployed v1.2.3 to production",
            ...     custom_details={
            ...         "version": "1.2.3",
            ...         "environment": "production",
            ...         "deployed_by": "ci/cd"
            ...     }
            ... )
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "PagerDuty integration is disabled"
            }
        
        change_url = "https://events.pagerduty.com/v2/change/enqueue"
        
        payload = {
            "routing_key": self.integration_key,
            "payload": {
                "summary": summary,
                "timestamp": (timestamp or datetime.utcnow()).isoformat(),
                "source": "bybit-strategy-tester",
                "custom_details": custom_details or {}
            }
        }
        
        try:
            logger.info(f"Sending PagerDuty change event: {summary}")
            
            response = requests.post(
                change_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info("PagerDuty change event sent successfully")
            
            return {
                "success": True,
                "status": result.get("status"),
                "message": result.get("message")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PagerDuty change event error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to send change event: {e}"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get PagerDuty service status.
        
        Returns:
            Service status information
        """
        return {
            "enabled": self.enabled,
            "configured": self.integration_key is not None,
            "api_url": self.api_url,
            "integration_key_present": bool(self.integration_key)
        }


# Global PagerDuty service instance
pagerduty_service = PagerDutyService()
