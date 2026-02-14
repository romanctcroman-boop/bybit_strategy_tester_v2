"""
AI Agent Dashboard API

FastAPI router for AI agent monitoring dashboard.
Provides REST endpoints and WebSocket for real-time updates.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket
from loguru import logger
from pydantic import BaseModel


# Pydantic models for API
class MetricQuery(BaseModel):
    """Metric query parameters"""

    metric_name: str
    time_from: str | None = "now-1h"
    time_to: str | None = "now"
    aggregation: str | None = "avg"
    labels: dict[str, str] | None = None


class AlertCreate(BaseModel):
    """Alert creation request"""

    name: str
    metric_name: str
    condition: str  # "gt", "lt", "eq"
    threshold: float
    severity: str = "warning"
    message: str | None = None


class DashboardWidget(BaseModel):
    """Dashboard widget definition"""

    id: str
    type: str  # "stat", "chart", "table", "gauge"
    title: str
    metric_name: str
    position: dict[str, int]  # x, y, w, h
    options: dict[str, Any] | None = None


class DashboardLayout(BaseModel):
    """Dashboard layout"""

    id: str
    name: str
    widgets: list[DashboardWidget]


# Create router
router = APIRouter(prefix="/api/agents", tags=["AI Agents"])


# In-memory state (replace with actual collectors in production)
_dashboard_state: dict[str, Any] = {
    "connected_clients": set(),
    "last_update": None,
}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "ai-agent-dashboard",
    }


@router.get("/metrics")
async def list_metrics():
    """List available metrics"""
    try:
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        MetricsCollector()  # Verify import works

        return {
            "metrics": [
                {
                    "name": "agent_requests_total",
                    "type": "counter",
                    "description": "Total agent requests",
                },
                {
                    "name": "agent_latency_ms",
                    "type": "histogram",
                    "description": "Request latency",
                },
                {
                    "name": "agent_errors_total",
                    "type": "counter",
                    "description": "Total errors",
                },
                {
                    "name": "memory_items_total",
                    "type": "gauge",
                    "description": "Memory items count",
                },
                {
                    "name": "tokens_used_total",
                    "type": "counter",
                    "description": "Total tokens used",
                },
            ]
        }
    except Exception as e:
        logger.error(f"Error listing metrics: {e}")
        return {"metrics": []}


@router.post("/metrics/query")
async def query_metrics(query: MetricQuery):
    """Query metric data"""
    try:
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        # Get metric data
        data = collector.get_metric(query.metric_name)

        return {
            "metric_name": query.metric_name,
            "data": data,
            "query": query.model_dump(),
        }
    except Exception as e:
        logger.error(f"Error querying metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/prometheus")
async def prometheus_export():
    """Export metrics in Prometheus format"""
    try:
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        return {
            "format": "prometheus",
            "content": collector.export_prometheus(),
        }
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        return {"format": "prometheus", "content": ""}


@router.get("/agents")
async def list_agents():
    """List registered agents"""
    try:
        from backend.agents.communication.protocol import get_message_broker

        broker = get_message_broker()

        agents = broker.list_agents()
        return {
            "agents": [agent.to_dict() for agent in agents],
            "total": len(agents),
        }
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return {"agents": [], "total": 0}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details"""
    try:
        from backend.agents.communication.protocol import get_message_broker

        broker = get_message_broker()

        agent = broker.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return agent.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/stats")
async def memory_stats():
    """Get memory system statistics"""
    try:
        from backend.agents.memory.shared_memory import get_shared_memory

        memory = get_shared_memory()

        return memory.get_stats()
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        return {"error": str(e)}


@router.get("/memory/keys")
async def memory_keys():
    """List memory keys"""
    try:
        from backend.agents.memory.shared_memory import get_shared_memory

        memory = get_shared_memory()

        keys = await memory.keys()
        return {"keys": keys, "total": len(keys)}
    except Exception as e:
        logger.error(f"Error listing memory keys: {e}")
        return {"keys": [], "total": 0}


@router.get("/alerts")
async def list_alerts():
    """List active alerts"""
    try:
        from backend.agents.monitoring.alerting import AlertManager

        manager = AlertManager()

        return {
            "alerts": [
                {
                    "id": alert.id,
                    "name": alert.rule_name,
                    "severity": alert.severity.value,
                    "value": alert.current_value,
                    "message": alert.message,
                    "fired_at": alert.fired_at.isoformat(),
                }
                for alert in manager.get_active_alerts()
            ]
        }
    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        return {"alerts": []}


@router.post("/alerts")
async def create_alert(alert: AlertCreate):
    """Create new alert rule"""
    try:
        from backend.agents.monitoring.alerting import (
            AlertManager,
            AlertRule,
            AlertSeverity,
        )

        manager = AlertManager()

        rule = AlertRule(
            name=alert.name,
            metric_name=alert.metric_name,
            condition=alert.condition,
            threshold=alert.threshold,
            severity=AlertSeverity(alert.severity),
            message=alert.message,
        )

        manager.add_rule(rule)

        return {
            "status": "created",
            "rule": {
                "name": rule.name,
                "metric_name": rule.metric_name,
                "threshold": rule.threshold,
            },
        }
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces")
async def list_traces(limit: int = 50):
    """List recent traces"""
    try:
        from backend.agents.monitoring.tracing import DistributedTracer

        tracer = DistributedTracer()

        spans = list(tracer._completed_spans.values())[-limit:]

        return {
            "traces": [
                {
                    "trace_id": span.trace_id,
                    "span_id": span.span_id,
                    "name": span.name,
                    "duration_ms": span.duration_ms,
                    "status": span.status.value if hasattr(span, "status") else "ok",
                }
                for span in spans
            ]
        }
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        return {"traces": []}


@router.get("/anomalies")
async def list_anomalies(metric_name: str | None = None, limit: int = 100):
    """List detected anomalies"""
    try:
        from backend.agents.monitoring.ml_anomaly import get_anomaly_detector

        detector = get_anomaly_detector()

        if metric_name:
            anomalies = detector.get_anomaly_history(metric_name, limit)
        else:
            anomalies = []
            for name in detector._anomaly_history:
                anomalies.extend(detector.get_anomaly_history(name, limit // 10))

        return {
            "anomalies": [a.to_dict() for a in anomalies[-limit:]],
            "total": len(anomalies),
        }
    except Exception as e:
        logger.error(f"Error listing anomalies: {e}")
        return {"anomalies": [], "total": 0}


@router.get("/dashboard/default")
async def get_default_dashboard():
    """Get default dashboard configuration"""
    return {
        "id": "ai-agents-overview",
        "name": "AI Agents Overview",
        "widgets": [
            {
                "id": "w1",
                "type": "stat",
                "title": "Total Requests",
                "metric_name": "agent_requests_total",
                "position": {"x": 0, "y": 0, "w": 3, "h": 2},
            },
            {
                "id": "w2",
                "type": "stat",
                "title": "Active Agents",
                "metric_name": "active_agents",
                "position": {"x": 3, "y": 0, "w": 3, "h": 2},
            },
            {
                "id": "w3",
                "type": "stat",
                "title": "Memory Items",
                "metric_name": "memory_items_total",
                "position": {"x": 6, "y": 0, "w": 3, "h": 2},
            },
            {
                "id": "w4",
                "type": "stat",
                "title": "Active Alerts",
                "metric_name": "active_alerts",
                "position": {"x": 9, "y": 0, "w": 3, "h": 2},
            },
            {
                "id": "w5",
                "type": "chart",
                "title": "Request Rate",
                "metric_name": "agent_requests_total",
                "position": {"x": 0, "y": 2, "w": 6, "h": 4},
                "options": {"chartType": "line"},
            },
            {
                "id": "w6",
                "type": "chart",
                "title": "Latency",
                "metric_name": "agent_latency_ms",
                "position": {"x": 6, "y": 2, "w": 6, "h": 4},
                "options": {"chartType": "line"},
            },
            {
                "id": "w7",
                "type": "table",
                "title": "Recent Alerts",
                "metric_name": "alerts",
                "position": {"x": 0, "y": 6, "w": 12, "h": 4},
            },
        ],
    }


# WebSocket for real-time updates
class ConnectionManager:
    """WebSocket connection manager"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        for connection in self.active_connections:
            with suppress(Exception):
                await connection.send_json(message)


manager = ConnectionManager()
