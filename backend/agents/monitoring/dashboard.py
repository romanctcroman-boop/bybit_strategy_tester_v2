"""
Dashboard Data Provider for AI Agent System

Provides data for monitoring dashboards:
- Widget definitions and layouts
- Real-time data aggregation
- Time-series queries
- Export to various formats (JSON, CSV)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class WidgetType(Enum):
    """Types of dashboard widgets"""

    COUNTER = "counter"  # Single value display
    GAUGE = "gauge"  # Gauge with min/max
    LINE_CHART = "line_chart"  # Time series line chart
    BAR_CHART = "bar_chart"  # Bar chart
    PIE_CHART = "pie_chart"  # Pie/donut chart
    TABLE = "table"  # Data table
    HEATMAP = "heatmap"  # Heat map
    STATUS = "status"  # Status indicator


class TimeRange(Enum):
    """Predefined time ranges"""

    LAST_5M = "5m"
    LAST_15M = "15m"
    LAST_1H = "1h"
    LAST_6H = "6h"
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"


@dataclass
class DashboardWidget:
    """Definition of a dashboard widget"""

    id: str
    title: str
    widget_type: WidgetType
    data_source: str  # Metric name or query
    refresh_seconds: int = 30
    position: dict[str, int] = field(
        default_factory=lambda: {"x": 0, "y": 0, "w": 4, "h": 3}
    )
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.widget_type.value,
            "data_source": self.data_source,
            "refresh_seconds": self.refresh_seconds,
            "position": self.position,
            "options": self.options,
        }


@dataclass
class Dashboard:
    """Dashboard definition"""

    id: str
    name: str
    description: str = ""
    widgets: list[DashboardWidget] = field(default_factory=list)
    refresh_seconds: int = 30
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_widget(self, widget: DashboardWidget) -> None:
        self.widgets.append(widget)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "widgets": [w.to_dict() for w in self.widgets],
            "refresh_seconds": self.refresh_seconds,
        }


@dataclass
class WidgetData:
    """Data for a widget"""

    widget_id: str
    data: Any  # Type depends on widget type
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class DashboardDataProvider:
    """
    Provides data for monitoring dashboards

    Integrates with MetricsCollector, AlertManager, and Tracer
    to provide unified dashboard data.

    Example:
        provider = DashboardDataProvider(metrics_collector, alert_manager, tracer)

        # Get widget data
        data = await provider.get_widget_data("agent_requests_chart", TimeRange.LAST_1H)

        # Get full dashboard
        dashboard = provider.get_default_dashboard()
        dashboard_data = await provider.get_dashboard_data(dashboard.id)
    """

    # Pre-defined widgets for agent monitoring
    DEFAULT_WIDGETS = [
        DashboardWidget(
            id="total_requests",
            title="Total Requests",
            widget_type=WidgetType.COUNTER,
            data_source="agent_requests_total",
            position={"x": 0, "y": 0, "w": 2, "h": 2},
        ),
        DashboardWidget(
            id="active_requests",
            title="Active Requests",
            widget_type=WidgetType.GAUGE,
            data_source="agent_active_requests",
            position={"x": 2, "y": 0, "w": 2, "h": 2},
            options={"min": 0, "max": 50, "thresholds": [10, 25, 40]},
        ),
        DashboardWidget(
            id="error_rate",
            title="Error Rate",
            widget_type=WidgetType.GAUGE,
            data_source="agent_error_rate",
            position={"x": 4, "y": 0, "w": 2, "h": 2},
            options={"min": 0, "max": 100, "unit": "%", "thresholds": [5, 15, 30]},
        ),
        DashboardWidget(
            id="latency_chart",
            title="Response Latency",
            widget_type=WidgetType.LINE_CHART,
            data_source="agent_latency_ms",
            position={"x": 0, "y": 2, "w": 6, "h": 3},
            options={"aggregation": "p95", "unit": "ms"},
        ),
        DashboardWidget(
            id="requests_by_agent",
            title="Requests by Agent",
            widget_type=WidgetType.PIE_CHART,
            data_source="agent_requests_by_type",
            position={"x": 6, "y": 0, "w": 3, "h": 3},
        ),
        DashboardWidget(
            id="consensus_confidence",
            title="Consensus Confidence",
            widget_type=WidgetType.LINE_CHART,
            data_source="consensus_confidence",
            position={"x": 0, "y": 5, "w": 4, "h": 3},
        ),
        DashboardWidget(
            id="memory_usage",
            title="Memory Tier Usage",
            widget_type=WidgetType.BAR_CHART,
            data_source="memory_tier_items",
            position={"x": 4, "y": 5, "w": 4, "h": 3},
        ),
        DashboardWidget(
            id="active_alerts",
            title="Active Alerts",
            widget_type=WidgetType.TABLE,
            data_source="alerts",
            position={"x": 8, "y": 3, "w": 4, "h": 5},
        ),
        DashboardWidget(
            id="system_status",
            title="System Status",
            widget_type=WidgetType.STATUS,
            data_source="system_health",
            position={"x": 9, "y": 0, "w": 3, "h": 3},
        ),
    ]

    def __init__(
        self,
        metrics_collector: Any | None = None,
        alert_manager: Any | None = None,
        tracer: Any | None = None,
    ):
        """
        Initialize dashboard data provider

        Args:
            metrics_collector: MetricsCollector instance
            alert_manager: AlertManager instance
            tracer: DistributedTracer instance
        """
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager
        self.tracer = tracer

        self.dashboards: dict[str, Dashboard] = {}

        # Create default dashboard
        self._create_default_dashboard()

        logger.info("📊 DashboardDataProvider initialized")

    def _create_default_dashboard(self) -> None:
        """Create the default agent monitoring dashboard"""
        dashboard = Dashboard(
            id="agent_monitoring",
            name="AI Agent Monitoring",
            description="Real-time monitoring of AI agent system",
            refresh_seconds=30,
        )

        for widget in self.DEFAULT_WIDGETS:
            dashboard.add_widget(widget)

        self.dashboards[dashboard.id] = dashboard

    def get_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Get dashboard by ID"""
        return self.dashboards.get(dashboard_id)

    def list_dashboards(self) -> list[dict[str, Any]]:
        """List all dashboards"""
        return [
            {"id": d.id, "name": d.name, "widget_count": len(d.widgets)}
            for d in self.dashboards.values()
        ]

    async def get_widget_data(
        self,
        widget_id: str,
        time_range: TimeRange = TimeRange.LAST_1H,
        dashboard_id: str = "agent_monitoring",
    ) -> WidgetData:
        """Get data for a specific widget"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return WidgetData(widget_id=widget_id, data=None)

        widget = next((w for w in dashboard.widgets if w.id == widget_id), None)
        if not widget:
            return WidgetData(widget_id=widget_id, data=None)

        return await self._fetch_widget_data(widget, time_range)

    async def get_dashboard_data(
        self,
        dashboard_id: str,
        time_range: TimeRange = TimeRange.LAST_1H,
    ) -> dict[str, WidgetData]:
        """Get data for all widgets in a dashboard"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return {}

        result = {}
        for widget in dashboard.widgets:
            data = await self._fetch_widget_data(widget, time_range)
            result[widget.id] = data

        return result

    async def _fetch_widget_data(
        self,
        widget: DashboardWidget,
        time_range: TimeRange,
    ) -> WidgetData:
        """Fetch data for a widget based on its type and data source"""
        window_seconds = self._time_range_to_seconds(time_range)

        if widget.data_source == "alerts":
            return await self._get_alerts_data(widget)
        elif widget.data_source == "system_health":
            return await self._get_system_health_data(widget)
        elif widget.data_source == "agent_requests_by_type":
            return await self._get_requests_by_type_data(widget, window_seconds)
        elif widget.data_source == "agent_error_rate":
            return await self._get_error_rate_data(widget, window_seconds)
        else:
            return await self._get_metric_data(widget, window_seconds)

    async def _get_metric_data(
        self,
        widget: DashboardWidget,
        window_seconds: int,
    ) -> WidgetData:
        """Get data from metrics collector"""
        if not self.metrics_collector:
            return WidgetData(
                widget_id=widget.id, data=self._generate_mock_data(widget)
            )

        data = None

        if widget.widget_type == WidgetType.COUNTER or widget.widget_type == WidgetType.GAUGE:
            data = self.metrics_collector.get(
                widget.data_source,
                window_seconds=window_seconds,
            )
        elif widget.widget_type == WidgetType.LINE_CHART:
            # Get time series data
            data = self._get_time_series_data(widget, window_seconds)
        elif widget.widget_type == WidgetType.BAR_CHART:
            data = self._get_bar_chart_data(widget, window_seconds)

        return WidgetData(widget_id=widget.id, data=data)

    def _get_time_series_data(
        self,
        widget: DashboardWidget,
        window_seconds: int,
    ) -> dict[str, Any]:
        """Generate time series data for charts"""
        # Mock time series data
        import random

        points = []
        now = datetime.now(UTC)
        interval = max(window_seconds // 60, 1)

        for i in range(60):
            timestamp = now - timedelta(seconds=interval * (60 - i))
            value = (
                random.uniform(100, 2000)
                if "latency" in widget.data_source
                else random.uniform(0, 1)
            )
            points.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "value": value,
                }
            )

        return {
            "series": [{"name": widget.title, "data": points}],
            "unit": widget.options.get("unit", ""),
        }

    def _get_bar_chart_data(
        self,
        widget: DashboardWidget,
        window_seconds: int,
    ) -> dict[str, Any]:
        """Generate bar chart data"""
        if "memory" in widget.data_source:
            return {
                "categories": ["Working", "Episodic", "Semantic", "Procedural"],
                "values": [45, 120, 80, 25],
            }
        return {"categories": [], "values": []}

    async def _get_alerts_data(self, widget: DashboardWidget) -> WidgetData:
        """Get active alerts data"""
        if not self.alert_manager:
            return WidgetData(widget_id=widget.id, data=[])

        alerts = self.alert_manager.get_active_alerts()
        data = [
            {
                "severity": a.severity.value,
                "rule": a.rule_name,
                "message": a.message,
                "started_at": a.started_at.isoformat(),
            }
            for a in alerts
        ]

        return WidgetData(widget_id=widget.id, data=data)

    async def _get_system_health_data(self, widget: DashboardWidget) -> WidgetData:
        """Get system health status"""
        health_status = {
            "overall": "healthy",
            "components": {
                "deepseek_api": {"status": "healthy", "latency_ms": 450},
                "perplexity_api": {"status": "healthy", "latency_ms": 380},
                "memory_system": {"status": "healthy", "items": 265},
                "consensus_engine": {"status": "healthy", "confidence": 0.92},
            },
        }

        # Check for issues
        if self.alert_manager:
            active_alerts = self.alert_manager.get_active_alerts()
            critical_count = sum(
                1 for a in active_alerts if a.severity.value == "critical"
            )

            if critical_count > 0:
                health_status["overall"] = "critical"
            elif len(active_alerts) > 0:
                health_status["overall"] = "degraded"

        return WidgetData(widget_id=widget.id, data=health_status)

    async def _get_requests_by_type_data(
        self,
        widget: DashboardWidget,
        window_seconds: int,
    ) -> WidgetData:
        """Get requests breakdown by agent type"""
        data = {
            "labels": ["DeepSeek", "Perplexity", "Local"],
            "values": [150, 80, 45],
        }
        return WidgetData(widget_id=widget.id, data=data)

    async def _get_error_rate_data(
        self,
        widget: DashboardWidget,
        window_seconds: int,
    ) -> WidgetData:
        """Calculate error rate percentage"""
        error_rate = 2.5  # Mock value

        if self.metrics_collector:
            total = self.metrics_collector.get(
                "agent_requests_total", window_seconds=window_seconds
            )
            errors = self.metrics_collector.get(
                "agent_errors_total", window_seconds=window_seconds
            )

            if total > 0:
                error_rate = (errors / total) * 100

        return WidgetData(widget_id=widget.id, data=error_rate)

    def _time_range_to_seconds(self, time_range: TimeRange) -> int:
        """Convert time range to seconds"""
        mapping = {
            TimeRange.LAST_5M: 300,
            TimeRange.LAST_15M: 900,
            TimeRange.LAST_1H: 3600,
            TimeRange.LAST_6H: 21600,
            TimeRange.LAST_24H: 86400,
            TimeRange.LAST_7D: 604800,
            TimeRange.LAST_30D: 2592000,
        }
        return mapping.get(time_range, 3600)

    def _generate_mock_data(self, widget: DashboardWidget) -> Any:
        """Generate mock data for testing"""
        import random

        if widget.widget_type == WidgetType.COUNTER:
            return random.randint(100, 10000)
        elif widget.widget_type == WidgetType.GAUGE:
            return random.uniform(0, 100)
        elif widget.widget_type == WidgetType.LINE_CHART:
            return self._get_time_series_data(widget, 3600)
        elif widget.widget_type == WidgetType.PIE_CHART:
            return {"labels": ["A", "B", "C"], "values": [30, 50, 20]}
        elif widget.widget_type == WidgetType.BAR_CHART:
            return {"categories": ["X", "Y", "Z"], "values": [10, 20, 15]}
        elif widget.widget_type == WidgetType.TABLE:
            return []
        else:
            return None

    def export_json(self, dashboard_id: str) -> str:
        """Export dashboard configuration as JSON"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return "{}"
        return json.dumps(dashboard.to_dict(), indent=2)

    def add_dashboard(self, dashboard: Dashboard) -> None:
        """Add a custom dashboard"""
        self.dashboards[dashboard.id] = dashboard

    def get_stats(self) -> dict[str, Any]:
        """Get provider statistics"""
        return {
            "dashboard_count": len(self.dashboards),
            "total_widgets": sum(len(d.widgets) for d in self.dashboards.values()),
        }


__all__ = [
    "Dashboard",
    "DashboardDataProvider",
    "DashboardWidget",
    "TimeRange",
    "WidgetData",
    "WidgetType",
]
