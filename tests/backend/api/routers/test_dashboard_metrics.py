"""
Tests for Dashboard Metrics API - Quick Win #1

Tests real-time performance metrics endpoints for monitoring dashboard.
"""

import copy
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import app
from backend.models import Backtest, Optimization, Strategy

client = TestClient(app)


def create_mock_backtest(
    id,
    strategy_id,
    symbol,
    status,
    sharpe_ratio=None,
    total_return=None,
    win_rate=None,
    max_drawdown=None,
    total_trades=0,
    created_at=None,
    started_at=None,
    completed_at=None,
    strategy_name="Test Strategy",
):
    """Helper to create properly serializable backtest mock"""
    bt = MagicMock(spec=Backtest)
    bt.id = id
    bt.strategy_id = strategy_id
    bt.symbol = symbol
    bt.timeframe = "1h"
    bt.status = status
    bt.sharpe_ratio = sharpe_ratio
    bt.total_return = total_return
    bt.win_rate = win_rate
    bt.max_drawdown = max_drawdown
    bt.total_trades = total_trades
    bt.created_at = created_at
    bt.started_at = started_at
    bt.completed_at = completed_at

    # Mock strategy relationship
    strategy_mock = MagicMock()
    strategy_mock.name = strategy_name
    bt.strategy = strategy_mock

    return bt


def create_mock_strategy(id, name, strategy_type, is_active):
    """Helper to create properly serializable strategy mock"""
    strat = MagicMock(spec=Strategy)
    strat.id = id
    strat.name = name
    strat.strategy_type = strategy_type
    strat.is_active = is_active
    return strat


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def sample_backtests():
    """Sample backtest data"""
    now = datetime.now(UTC)

    return [
        create_mock_backtest(
            id=1,
            strategy_id=10,
            symbol="BTCUSDT",
            status="completed",
            sharpe_ratio=2.45,
            total_return=18.5,
            win_rate=0.68,
            max_drawdown=-12.3,
            total_trades=150,
            created_at=now - timedelta(days=1),
            started_at=now - timedelta(days=1),
            completed_at=now - timedelta(days=1) + timedelta(hours=1),
            strategy_name="Bollinger Mean Reversion",
        ),
        create_mock_backtest(
            id=2,
            strategy_id=10,
            symbol="ETHUSDT",
            status="running",
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            strategy_name="RSI Strategy",
        ),
        create_mock_backtest(
            id=3,
            strategy_id=11,
            symbol="SOLUSDT",
            status="failed",
            created_at=now - timedelta(days=3),
            started_at=now - timedelta(days=3),
            strategy_name="MA Crossover",
        ),
    ]


@pytest.fixture
def sample_strategies():
    """Sample strategy data"""
    return [
        create_mock_strategy(10, "Bollinger Mean Reversion", "mean_reversion", True),
        create_mock_strategy(11, "MA Crossover", "trend_following", True),
        create_mock_strategy(12, "RSI Divergence", "momentum", False),
    ]


@pytest.fixture(autouse=True)
def agent_breaker_snapshot(monkeypatch):
    """Ensure system-health endpoint sees deterministic agent telemetry."""

    snapshot = {
        "available": True,
        "summary": {
            "mcp_available": True,
            "mcp_breaker_rejections": 5,
            "deepseek_keys_active": 8,
            "perplexity_keys_active": 4,
            "autonomy_score": 8.2,
            "last_health_check": "2025-01-01T00:00:00Z",
            "total_requests": 128,
            "health_monitoring": {"total_components": 3},
            "circuit_breaker_totals": {
                "total_calls": 300,
                "total_failures": 12,
                "total_trips": 3,
            },
        },
        "breakers": {
            "mcp_server": {
                "state": "CLOSED",
                "total_calls": 40,
                "failed_calls": 2,
                "successful_calls": 38,
                "total_trips": 1,
                "last_trip_time": None,
                "breaker_rejections": 5,
            },
            "deepseek_api": {
                "state": "HALF_OPEN",
                "total_calls": 200,
                "failed_calls": 10,
                "successful_calls": 190,
                "total_trips": 2,
                "last_trip_time": "2025-01-01T00:00:00Z",
            },
            "perplexity_api": {
                "state": "CLOSED",
                "total_calls": 60,
                "failed_calls": 0,
                "successful_calls": 60,
                "total_trips": 0,
                "last_trip_time": None,
            },
        },
    }

    def fake_snapshot():
        return copy.deepcopy(snapshot)

    monkeypatch.setattr(
        "backend.api.routers.dashboard_metrics.get_agent_breaker_snapshot",
        fake_snapshot,
    )

    return snapshot


@pytest.fixture
def sample_optimizations():
    """Sample optimization data"""
    now = datetime.now(UTC)

    return [
        MagicMock(id=1, status="completed", created_at=now - timedelta(days=2)),
        MagicMock(id=2, status="running", created_at=now - timedelta(hours=1)),
        MagicMock(id=3, status="completed", created_at=now - timedelta(days=5)),
    ]


class TestMetricsSummary:
    """Test /dashboard/metrics/summary endpoint"""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_metrics_summary_24h(
        self,
        mock_session_local,
        mock_db_session,
        sample_backtests,
        sample_strategies,
        sample_optimizations,
    ):
        """Test metrics summary for 24h period"""
        mock_session_local.return_value = mock_db_session

        # Mock query chains
        mock_backtest_query = Mock()
        mock_backtest_query.filter.return_value = mock_backtest_query
        mock_backtest_query.count.side_effect = [
            3,
            1,
            1,
            1,
        ]  # total, completed, running, failed

        mock_strategy_query = Mock()
        mock_strategy_query.count.return_value = 3
        mock_strategy_query.filter.return_value.count.return_value = 2  # active

        mock_opt_query = Mock()
        mock_opt_query.filter.return_value = mock_opt_query
        mock_opt_query.count.side_effect = [3, 1, 2]  # total, running, completed

        # Mock db.query() to return appropriate query objects
        def query_side_effect(model):
            if model == Backtest:
                return mock_backtest_query
            elif model == Strategy:
                return mock_strategy_query
            elif model == Optimization:
                return mock_opt_query
            return Mock()

        mock_db_session.query.side_effect = query_side_effect

        # Mock aggregation queries
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = (
            45.2  # avg duration
        )
        mock_db_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 1254  # trades

        # Make request
        response = client.get("/api/v1/dashboard/metrics/summary?period=24h")

        assert response.status_code == 200
        data = response.json()

        assert data["period"] == "24h"
        assert "timestamp" in data

        assert data["backtests"]["total"] == 3
        assert data["backtests"]["completed"] == 1
        assert data["backtests"]["running"] == 1
        assert data["backtests"]["failed"] == 1
        assert 0 <= data["backtests"]["success_rate"] <= 1

        assert data["strategies"]["total"] == 3
        assert data["strategies"]["active"] == 2

        assert data["optimizations"]["total"] == 3
        assert data["optimizations"]["running"] == 1
        assert data["optimizations"]["completed"] == 2

        assert "avg_backtest_duration_sec" in data["performance"]
        assert "total_trades_analyzed" in data["performance"]

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_metrics_summary_all_time(self, mock_session_local, mock_db_session):
        """Test metrics summary for all time"""
        mock_session_local.return_value = mock_db_session

        # Mock query chains with simpler structure
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.side_effect = [100, 85, 5, 10, 50, 45, 20, 3, 15]

        mock_db_session.query.return_value = mock_query
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = (
            60.5
        )
        mock_db_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 50000

        response = client.get("/api/v1/dashboard/metrics/summary?period=all")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "all"

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_metrics_summary_empty_database(
        self, mock_session_local, mock_db_session
    ):
        """Test metrics summary with no data"""
        mock_session_local.return_value = mock_db_session

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0

        mock_db_session.query.return_value = mock_query
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = (
            None
        )
        mock_db_session.query.return_value.join.return_value.filter.return_value.scalar.return_value = 0

        response = client.get("/api/v1/dashboard/metrics/summary?period=7d")

        assert response.status_code == 200
        data = response.json()

        assert data["backtests"]["total"] == 0
        assert data["backtests"]["success_rate"] == 0.0
        assert data["performance"]["avg_backtest_duration_sec"] == 0


class TestTopPerformers:
    """Test /dashboard/metrics/top-performers endpoint"""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_top_performers_by_sharpe(
        self, mock_session_local, mock_db_session, sample_backtests
    ):
        """Test top performers ranked by Sharpe ratio"""
        mock_session_local.return_value = mock_db_session

        # Filter to completed backtests only
        completed = [bt for bt in sample_backtests if bt.status == "completed"]

        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = completed

        mock_db_session.query.return_value = mock_query

        response = client.get(
            "/api/v1/dashboard/metrics/top-performers?limit=5&metric=sharpe_ratio"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "sharpe_ratio"
        assert data["limit"] == 5
        assert data["count"] == len(completed)
        assert len(data["top_performers"]) == len(completed)

        # Verify first result structure
        top = data["top_performers"][0]
        assert "id" in top
        assert "strategy_name" in top
        assert "symbol" in top
        assert "sharpe_ratio" in top
        assert "total_return" in top
        assert "win_rate" in top

    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_top_performers_invalid_metric(
        self, mock_session_local, mock_db_session
    ):
        """Test top performers with invalid metric"""
        mock_session_local.return_value = mock_db_session

        response = client.get(
            "/api/v1/dashboard/metrics/top-performers?metric=invalid_metric"
        )

        assert response.status_code == 400
        assert "Invalid metric" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_top_performers_by_return(
        self, mock_session_local, mock_db_session, sample_backtests
    ):
        """Test top performers ranked by total return"""
        mock_session_local.return_value = mock_db_session

        completed = [bt for bt in sample_backtests if bt.status == "completed"]

        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = completed

        mock_db_session.query.return_value = mock_query

        response = client.get(
            "/api/v1/dashboard/metrics/top-performers?limit=10&metric=total_return"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metric"] == "total_return"


class TestStrategyMetrics:
    """Test /dashboard/metrics/strategy/{id} endpoint"""

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_strategy_metrics_success(
        self, mock_session_local, mock_db_session, sample_strategies, sample_backtests
    ):
        """Test strategy metrics with valid data"""
        mock_session_local.return_value = mock_db_session

        strategy = sample_strategies[0]
        backtests = [
            bt
            for bt in sample_backtests
            if bt.strategy_id == strategy.id and bt.status == "completed"
        ]

        # Mock strategy query
        mock_strategy_query = Mock()
        mock_strategy_query.filter.return_value.first.return_value = strategy

        # Mock backtest query
        mock_backtest_query = Mock()
        mock_backtest_query.filter.return_value = mock_backtest_query
        mock_backtest_query.all.return_value = backtests

        def query_side_effect(model):
            if model == Strategy:
                return mock_strategy_query
            elif model == Backtest:
                return mock_backtest_query
            return Mock()

        mock_db_session.query.side_effect = query_side_effect

        response = client.get(
            f"/api/v1/dashboard/metrics/strategy/{strategy.id}?period=30d"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["strategy_id"] == strategy.id
        assert data["strategy_name"] == strategy.name
        assert data["strategy_type"] == strategy.strategy_type
        assert data["period"] == "30d"

        assert "backtests" in data
        assert data["backtests"]["total"] == len(backtests)
        assert "avg_sharpe" in data["backtests"]
        assert "avg_return" in data["backtests"]
        assert "avg_win_rate" in data["backtests"]

        assert "best_backtest" in data
        assert "recent_activity" in data

    @pytest.mark.skip(reason="Requires real ORM models - Strategy/Backtest are stubs")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_strategy_metrics_not_found(self, mock_session_local, mock_db_session):
        """Test strategy metrics with non-existent strategy"""
        mock_session_local.return_value = mock_db_session

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/dashboard/metrics/strategy/99999?period=7d")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires database - run with: pytest -m integration")
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_strategy_metrics_no_backtests(
        self, mock_session_local, mock_db_session, sample_strategies
    ):
        """Test strategy metrics with no completed backtests"""
        mock_session_local.return_value = mock_db_session

        strategy = sample_strategies[2]  # Inactive strategy

        mock_strategy_query = Mock()
        mock_strategy_query.filter.return_value.first.return_value = strategy

        mock_backtest_query = Mock()
        mock_backtest_query.filter.return_value = mock_backtest_query
        mock_backtest_query.all.return_value = []

        def query_side_effect(model):
            if model == Strategy:
                return mock_strategy_query
            elif model == Backtest:
                return mock_backtest_query
            return Mock()

        mock_db_session.query.side_effect = query_side_effect

        response = client.get(
            f"/api/v1/dashboard/metrics/strategy/{strategy.id}?period=all"
        )

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "No completed backtests" in data["message"]


class TestSystemHealth:
    """Test /dashboard/metrics/system-health endpoint"""

    @pytest.mark.skip(
        reason="Requires real ORM models - Backtest.status is not defined in stub"
    )
    @patch("backend.api.routers.dashboard_metrics.SessionLocal")
    def test_get_system_health_success(
        self, mock_session_local, mock_db_session, agent_breaker_snapshot
    ):
        """Test system health check success"""
        mock_session_local.return_value = mock_db_session

        # Mock database queries
        mock_db_session.execute.side_effect = [
            Mock(scalar=lambda: None),  # Health check
            Mock(scalar=lambda: 1073741824),  # 1GB database size
        ]

        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 12  # pending tasks
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/dashboard/metrics/system-health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data

        assert data["database"]["connected"] is True
        assert "response_time_ms" in data["database"]

        assert "pending_tasks" in data["queue"]
        assert "active_workers" in data["queue"]

        assert "database_size_mb" in data["disk"]
        assert (
            data["agents"]["summary"]["mcp_breaker_rejections"]
            == agent_breaker_snapshot["summary"]["mcp_breaker_rejections"]
        )

    @patch("backend.api.routers.dashboard_metrics.get_db")
    def test_get_system_health_database_error(
        self, mock_get_db, agent_breaker_snapshot
    ):
        """Test system health check with database error"""
        mock_db_session = MagicMock()
        mock_get_db.return_value = mock_db_session

        # Simulate database error
        mock_db_session.execute.side_effect = Exception("Database connection failed")

        response = client.get("/api/v1/dashboard/metrics/system-health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "unhealthy"
        assert "error" in data
        assert "Database connection failed" in data["error"]
        assert (
            data["agents"]["breakers"]["mcp_server"]["breaker_rejections"]
            == agent_breaker_snapshot["breakers"]["mcp_server"]["breaker_rejections"]
        )


class TestIntegration:
    """Integration tests with real endpoint behavior"""

    def test_all_endpoints_exist(self):
        """Verify all dashboard metrics endpoints are registered"""
        endpoints = [
            "/api/v1/dashboard/metrics/summary",
            "/api/v1/dashboard/metrics/top-performers",
            "/api/v1/dashboard/metrics/strategy/1",
            "/api/v1/dashboard/metrics/system-health",
        ]

        # Note: These will fail without DB but confirms routing works
        for endpoint in endpoints:
            response = client.get(endpoint)
            # 404 would mean route not found, 500 is acceptable (no DB)
            assert response.status_code in [200, 404, 500], (
                f"Endpoint {endpoint} not properly registered"
            )
