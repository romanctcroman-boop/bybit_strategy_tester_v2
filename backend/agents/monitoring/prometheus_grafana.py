"""
Grafana/Prometheus Integration

Production-ready integration with:
- Prometheus metrics endpoint
- Grafana dashboard provisioning
- Remote write support
- Alert manager integration
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger


@dataclass
class PrometheusConfig:
    """Prometheus configuration"""

    endpoint: str = "/metrics"
    host: str = "0.0.0.0"
    port: int = 9090
    namespace: str = "ai_agent"
    subsystem: str = ""
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class GrafanaConfig:
    """Grafana configuration"""

    url: str = "http://localhost:3000"
    api_key: Optional[str] = None
    org_id: int = 1
    datasource_name: str = "Prometheus"


class PrometheusExporter:
    """
    Prometheus metrics exporter

    Exposes metrics in Prometheus format for scraping.

    Example:
        from backend.agents.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        exporter = PrometheusExporter(collector)

        # Get metrics in Prometheus format
        metrics_text = exporter.export()

        # Start HTTP server
        await exporter.start_server()
    """

    def __init__(
        self,
        metrics_collector: Any,  # MetricsCollector instance
        config: Optional[PrometheusConfig] = None,
    ):
        self.collector = metrics_collector
        self.config = config or PrometheusConfig()
        self._server = None

        logger.info("📊 PrometheusExporter initialized")

    def export(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        # Add namespace/subsystem prefixes
        prefix = self.config.namespace
        if self.config.subsystem:
            prefix = f"{prefix}_{self.config.subsystem}"

        # Get metrics from collector
        if hasattr(self.collector, "export_prometheus"):
            return self.collector.export_prometheus()

        # Manual export if collector doesn't have export method
        if hasattr(self.collector, "_counters"):
            for name, value in self.collector._counters.items():
                metric_name = f"{prefix}_{name}_total"
                lines.append(f"# HELP {metric_name} Counter metric")
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {value}")

        if hasattr(self.collector, "_gauges"):
            for name, value in self.collector._gauges.items():
                metric_name = f"{prefix}_{name}"
                lines.append(f"# HELP {metric_name} Gauge metric")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {value}")

        return "\n".join(lines)

    async def start_server(self) -> None:
        """Start HTTP server for Prometheus scraping"""
        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_get(self.config.endpoint, self._handle_metrics)
            app.router.add_get("/health", self._handle_health)

            runner = web.AppRunner(app)
            await runner.setup()

            self._server = web.TCPSite(
                runner,
                self.config.host,
                self.config.port,
            )
            await self._server.start()

            logger.info(
                f"📊 Prometheus metrics available at "
                f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"
            )

        except ImportError:
            logger.error("aiohttp required for Prometheus server")

    async def stop_server(self) -> None:
        """Stop HTTP server"""
        if self._server:
            await self._server.stop()
            logger.info("📊 Prometheus server stopped")

    async def _handle_metrics(self, request) -> Any:
        """Handle metrics request"""
        from aiohttp import web

        metrics = self.export()
        return web.Response(
            text=metrics,
            content_type="text/plain; charset=utf-8",
        )

    async def _handle_health(self, request) -> Any:
        """Handle health check"""
        from aiohttp import web

        return web.json_response({"status": "healthy"})


class PrometheusRemoteWriter:
    """
    Prometheus remote write client

    Pushes metrics to Prometheus remote write endpoint.
    """

    def __init__(
        self,
        remote_url: str,
        batch_size: int = 100,
        flush_interval_seconds: float = 10.0,
    ):
        self.remote_url = remote_url
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds

        self._buffer: List[Dict[str, Any]] = []
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None

        logger.info(f"📤 PrometheusRemoteWriter initialized: {remote_url}")

    async def start(self) -> None:
        """Start the writer"""
        self._session = aiohttp.ClientSession()
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        """Stop and flush remaining metrics"""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self._flush()

        if self._session:
            await self._session.close()

    async def write(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add metric to buffer"""
        ts = timestamp or datetime.now(timezone.utc)

        self._buffer.append(
            {
                "__name__": metric_name,
                "value": value,
                "timestamp": int(ts.timestamp() * 1000),
                "labels": labels or {},
            }
        )

        if len(self._buffer) >= self.batch_size:
            await self._flush()

    async def _flush(self) -> None:
        """Flush buffer to remote"""
        if not self._buffer or not self._session:
            return

        batch = self._buffer[: self.batch_size]
        self._buffer = self._buffer[self.batch_size :]

        try:
            # Convert to Prometheus remote write format
            timeseries = []
            for metric in batch:
                labels = [{"name": "__name__", "value": metric["__name__"]}]
                for k, v in metric.get("labels", {}).items():
                    labels.append({"name": k, "value": str(v)})

                timeseries.append(
                    {
                        "labels": labels,
                        "samples": [
                            {
                                "value": metric["value"],
                                "timestamp": metric["timestamp"],
                            }
                        ],
                    }
                )

            payload = {"timeseries": timeseries}

            async with self._session.post(
                self.remote_url,
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Remote write failed: {resp.status} - {text}")
                    # Re-add failed batch
                    self._buffer = batch + self._buffer

        except Exception as e:
            logger.error(f"Remote write error: {e}")
            self._buffer = batch + self._buffer

    async def _flush_loop(self) -> None:
        """Periodic flush loop"""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            await self._flush()


@dataclass
class GrafanaDashboard:
    """Grafana dashboard definition"""

    uid: str
    title: str
    panels: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    refresh: str = "5s"
    time_from: str = "now-1h"
    time_to: str = "now"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana dashboard JSON"""
        return {
            "uid": self.uid,
            "title": self.title,
            "tags": self.tags,
            "refresh": self.refresh,
            "time": {
                "from": self.time_from,
                "to": self.time_to,
            },
            "panels": self.panels,
            "schemaVersion": 38,
            "version": 1,
        }


class GrafanaClient:
    """
    Grafana API client

    Features:
    - Dashboard CRUD
    - Datasource management
    - Alert rule management

    Example:
        client = GrafanaClient(config)

        # Create dashboard
        dashboard = GrafanaDashboard(
            uid="ai-agents",
            title="AI Agent Metrics",
            panels=[...],
        )
        await client.create_dashboard(dashboard)
    """

    def __init__(self, config: GrafanaConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session"""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def health_check(self) -> bool:
        """Check Grafana health"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.url}/api/health") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def create_dashboard(
        self,
        dashboard: GrafanaDashboard,
        folder_uid: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """Create or update dashboard"""
        session = await self._get_session()

        payload = {
            "dashboard": dashboard.to_dict(),
            "overwrite": overwrite,
        }
        if folder_uid:
            payload["folderUid"] = folder_uid

        async with session.post(
            f"{self.config.url}/api/dashboards/db",
            json=payload,
        ) as resp:
            result = await resp.json()

            if resp.status in (200, 201):
                logger.info(f"📊 Created dashboard: {dashboard.title}")
            else:
                logger.error(f"Dashboard creation failed: {result}")

            return result

    async def get_dashboard(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get dashboard by UID"""
        session = await self._get_session()

        async with session.get(f"{self.config.url}/api/dashboards/uid/{uid}") as resp:
            if resp.status == 200:
                return await resp.json()
            return None

    async def delete_dashboard(self, uid: str) -> bool:
        """Delete dashboard"""
        session = await self._get_session()

        async with session.delete(
            f"{self.config.url}/api/dashboards/uid/{uid}"
        ) as resp:
            return resp.status == 200

    async def list_datasources(self) -> List[Dict[str, Any]]:
        """List all datasources"""
        session = await self._get_session()

        async with session.get(f"{self.config.url}/api/datasources") as resp:
            if resp.status == 200:
                return await resp.json()
            return []

    async def create_datasource(
        self,
        name: str,
        ds_type: str = "prometheus",
        url: str = "http://localhost:9090",
        access: str = "proxy",
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """Create datasource"""
        session = await self._get_session()

        payload = {
            "name": name,
            "type": ds_type,
            "url": url,
            "access": access,
            "isDefault": is_default,
        }

        async with session.post(
            f"{self.config.url}/api/datasources",
            json=payload,
        ) as resp:
            result = await resp.json()

            if resp.status in (200, 201):
                logger.info(f"📊 Created datasource: {name}")

            return result


def create_ai_agent_dashboard() -> GrafanaDashboard:
    """Create pre-configured AI Agent monitoring dashboard"""
    return GrafanaDashboard(
        uid="ai-agent-monitoring",
        title="AI Agent System Monitoring",
        tags=["ai", "agents", "monitoring"],
        panels=[
            # Row 1: Overview
            {
                "id": 1,
                "type": "stat",
                "title": "Total Requests",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                "targets": [
                    {
                        "expr": "sum(ai_agent_requests_total)",
                        "refId": "A",
                    }
                ],
            },
            {
                "id": 2,
                "type": "stat",
                "title": "Active Agents",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
                "targets": [
                    {
                        "expr": "ai_agent_active_count",
                        "refId": "A",
                    }
                ],
            },
            {
                "id": 3,
                "type": "stat",
                "title": "Avg Latency",
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
                "targets": [
                    {
                        "expr": "avg(ai_agent_latency_ms)",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {"unit": "ms"},
                },
            },
            {
                "id": 4,
                "type": "stat",
                "title": "Error Rate",
                "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
                "targets": [
                    {
                        "expr": "sum(rate(ai_agent_errors_total[5m])) / sum(rate(ai_agent_requests_total[5m])) * 100",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {
                    "defaults": {"unit": "percent"},
                },
            },
            # Row 2: Time series
            {
                "id": 5,
                "type": "timeseries",
                "title": "Request Rate",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
                "targets": [
                    {
                        "expr": "sum(rate(ai_agent_requests_total[1m])) by (agent_type)",
                        "refId": "A",
                        "legendFormat": "{{agent_type}}",
                    }
                ],
            },
            {
                "id": 6,
                "type": "timeseries",
                "title": "Latency Distribution",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(ai_agent_latency_ms_bucket[5m]))",
                        "refId": "A",
                        "legendFormat": "p95",
                    },
                    {
                        "expr": "histogram_quantile(0.50, rate(ai_agent_latency_ms_bucket[5m]))",
                        "refId": "B",
                        "legendFormat": "p50",
                    },
                ],
            },
            # Row 3: Memory & Resources
            {
                "id": 7,
                "type": "gauge",
                "title": "Memory Usage",
                "gridPos": {"h": 6, "w": 8, "x": 0, "y": 12},
                "targets": [
                    {
                        "expr": "ai_agent_memory_items_total",
                        "refId": "A",
                    }
                ],
            },
            {
                "id": 8,
                "type": "timeseries",
                "title": "Token Usage",
                "gridPos": {"h": 6, "w": 16, "x": 8, "y": 12},
                "targets": [
                    {
                        "expr": "sum(rate(ai_agent_tokens_total[5m])) by (provider)",
                        "refId": "A",
                        "legendFormat": "{{provider}}",
                    }
                ],
            },
        ],
    )


class PrometheusAlertManager:
    """
    Prometheus AlertManager integration

    Sends alerts to Prometheus AlertManager.
    """

    def __init__(self, alertmanager_url: str = "http://localhost:9093"):
        self.url = alertmanager_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_alert(
        self,
        alert_name: str,
        severity: str = "warning",
        summary: str = "",
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Send alert to AlertManager"""
        session = await self._get_session()

        alert = {
            "labels": {
                "alertname": alert_name,
                "severity": severity,
                **(labels or {}),
            },
            "annotations": {
                "summary": summary,
                "description": description,
                **(annotations or {}),
            },
            "startsAt": datetime.now(timezone.utc).isoformat(),
        }

        try:
            async with session.post(
                f"{self.url}/api/v2/alerts",
                json=[alert],
            ) as resp:
                if resp.status == 200:
                    logger.info(f"🚨 Sent alert: {alert_name}")
                    return True
                else:
                    text = await resp.text()
                    logger.error(f"Alert failed: {text}")
                    return False
        except Exception as e:
            logger.error(f"AlertManager error: {e}")
            return False

    async def resolve_alert(
        self,
        alert_name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Resolve an alert"""
        session = await self._get_session()

        now = datetime.now(timezone.utc)

        alert = {
            "labels": {
                "alertname": alert_name,
                **(labels or {}),
            },
            "startsAt": (now.replace(hour=now.hour - 1)).isoformat(),
            "endsAt": now.isoformat(),
        }

        try:
            async with session.post(
                f"{self.url}/api/v2/alerts",
                json=[alert],
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"AlertManager error: {e}")
            return False

    async def get_alerts(self) -> List[Dict[str, Any]]:
        """Get current alerts"""
        session = await self._get_session()

        try:
            async with session.get(f"{self.url}/api/v2/alerts") as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except Exception as e:
            logger.error(f"Get alerts error: {e}")
            return []


__all__ = [
    "PrometheusConfig",
    "GrafanaConfig",
    "PrometheusExporter",
    "PrometheusRemoteWriter",
    "GrafanaDashboard",
    "GrafanaClient",
    "create_ai_agent_dashboard",
    "PrometheusAlertManager",
]
