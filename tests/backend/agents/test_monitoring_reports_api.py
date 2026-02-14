"""
Tests for Agent Monitoring & Reports API endpoints.

Tests cover:
- GET /api/v1/agents/monitoring/metrics
- GET /api/v1/agents/monitoring/metrics/{name}/history
- POST /api/v1/agents/monitoring/reset
- POST /api/v1/reports/generate (JSON)
- POST /api/v1/reports/generate (HTML)
- Validation errors (bad metric name, missing metrics, bad format)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.agents.monitoring.system_monitor import SystemMonitor

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fresh_monitor() -> SystemMonitor:
    """
    A fresh SystemMonitor that replaces the singleton for tests.

    We patch get_system_monitor to always return THIS instance,
    so each test is isolated.
    """
    return SystemMonitor()


@pytest.fixture
async def client(fresh_monitor: SystemMonitor):
    """Async HTTP test client with patched monitor singleton."""
    from backend.api.app import app

    with patch(
        "backend.agents.monitoring.system_monitor.get_system_monitor",
        return_value=fresh_monitor,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
def sample_report_request() -> dict[str, Any]:
    """Valid report generation request body."""
    return {
        "strategy_name": "Test RSI Strategy",
        "backtest_results": {
            "metrics": {
                "net_profit_pct": 0.25,
                "sharpe_ratio": 1.5,
                "max_drawdown": 0.10,
                "win_rate": 0.55,
                "profit_factor": 1.4,
                "total_trades": 100,
            },
            "trades": [
                {"pnl": 50.0},
                {"pnl": -20.0},
                {"pnl": 80.0},
            ],
        },
        "format": "json",
        "strategy_params": {"period": 14},
        "walk_forward": {},
        "benchmarks": {},
    }


# =============================================================================
# TestMonitoringMetricsEndpoint
# =============================================================================


class TestMonitoringMetricsEndpoint:
    """GET /api/v1/agents/monitoring/metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics_empty(self, client: AsyncClient):
        """Returns zero metrics when nothing tracked."""
        response = await client.get("/api/v1/agents/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "alerts" in data
        assert data["metrics"]["total_runs"] == 0

    @pytest.mark.asyncio
    async def test_get_metrics_after_tracking(
        self,
        client: AsyncClient,
        fresh_monitor: SystemMonitor,
    ):
        """Returns tracked metrics after recording pipeline runs."""
        fresh_monitor.record_pipeline_run(
            success=True,
            tokens_used=500,
            cost_usd=0.02,
        )
        response = await client.get("/api/v1/agents/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["total_runs"] == 1
        assert data["metrics"]["llm_token_usage"] == 500


# =============================================================================
# TestMetricHistoryEndpoint
# =============================================================================


class TestMetricHistoryEndpoint:
    """GET /api/v1/agents/monitoring/metrics/{name}/history."""

    @pytest.mark.asyncio
    async def test_get_valid_metric_history(
        self,
        client: AsyncClient,
        fresh_monitor: SystemMonitor,
    ):
        """Returns history for a valid metric name."""
        fresh_monitor.track_metric("llm_token_usage", 100)
        fresh_monitor.track_metric("llm_token_usage", 200)

        response = await client.get("/api/v1/agents/monitoring/metrics/llm_token_usage/history")
        assert response.status_code == 200
        data = response.json()
        assert data["metric_name"] == "llm_token_usage"
        assert data["count"] == 2
        assert len(data["entries"]) == 2

    @pytest.mark.asyncio
    async def test_unknown_metric_returns_404(self, client: AsyncClient):
        """Unknown metric name returns 404."""
        response = await client.get("/api/v1/agents/monitoring/metrics/nonexistent_metric/history")
        assert response.status_code == 404


# =============================================================================
# TestResetEndpoint
# =============================================================================


class TestResetEndpoint:
    """POST /api/v1/agents/monitoring/reset."""

    @pytest.mark.asyncio
    async def test_reset_clears_data(
        self,
        client: AsyncClient,
        fresh_monitor: SystemMonitor,
    ):
        """Reset endpoint clears all monitoring data."""
        fresh_monitor.record_pipeline_run(success=True, tokens_used=1000)

        response = await client.post("/api/v1/agents/monitoring/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify metrics are cleared
        response2 = await client.get("/api/v1/agents/monitoring/metrics")
        assert response2.json()["metrics"]["total_runs"] == 0


# =============================================================================
# TestReportsGenerateEndpoint
# =============================================================================


class TestReportsGenerateEndpoint:
    """POST /api/v1/reports/generate."""

    @pytest.mark.asyncio
    async def test_generate_json_report(
        self,
        client: AsyncClient,
        sample_report_request: dict[str, Any],
    ):
        """JSON report returns structured response."""
        response = await client.post(
            "/api/v1/reports/generate",
            json=sample_report_request,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["strategy_name"] == "Test RSI Strategy"
        assert "data" in data
        assert data["data"]["assessment"]["grade"] in ("A+", "A", "B", "C", "D", "F")

    @pytest.mark.asyncio
    async def test_generate_html_report(
        self,
        client: AsyncClient,
        sample_report_request: dict[str, Any],
    ):
        """HTML report returns text/html content type."""
        sample_report_request["format"] = "html"
        response = await client.post(
            "/api/v1/reports/generate",
            json=sample_report_request,
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
        assert "Test RSI Strategy" in response.text

    @pytest.mark.asyncio
    async def test_invalid_format_returns_400(
        self,
        client: AsyncClient,
        sample_report_request: dict[str, Any],
    ):
        """Invalid format returns 400 error."""
        sample_report_request["format"] = "pdf"
        response = await client.post(
            "/api/v1/reports/generate",
            json=sample_report_request,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_metrics_returns_400(
        self,
        client: AsyncClient,
    ):
        """Missing metrics dict returns 400 error."""
        response = await client.post(
            "/api/v1/reports/generate",
            json={
                "strategy_name": "Bad",
                "backtest_results": {"trades": []},
                "format": "json",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_report_with_walk_forward(
        self,
        client: AsyncClient,
        sample_report_request: dict[str, Any],
    ):
        """Walk-forward data is included in the report."""
        sample_report_request["walk_forward"] = {
            "consistency_ratio": 0.72,
            "overfit_score": 0.15,
            "parameter_stability": 0.85,
            "confidence_level": "high",
        }
        response = await client.post(
            "/api/v1/reports/generate",
            json=sample_report_request,
        )
        assert response.status_code == 200
        data = response.json()
        assert "walk_forward" in data["data"]
        assert data["data"]["walk_forward"]["consistency_ratio"] == 0.72

    @pytest.mark.asyncio
    async def test_report_with_benchmarks(
        self,
        client: AsyncClient,
        sample_report_request: dict[str, Any],
    ):
        """Benchmark data is included in the report."""
        sample_report_request["benchmarks"] = {
            "buy_hold": {"total_return": 0.15},
        }
        response = await client.post(
            "/api/v1/reports/generate",
            json=sample_report_request,
        )
        assert response.status_code == 200
        data = response.json()
        assert "benchmarks" in data["data"]
        assert "buy_hold" in data["data"]["benchmarks"]
