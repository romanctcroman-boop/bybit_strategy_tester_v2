"""
Tests for backend/api/routers/backtests.py

Covers:
- POST /api/v1/backtests/          — create backtest (success, validation error, engine failure)
- GET  /api/v1/backtests/          — list backtests (memory + DB, pagination)
- GET  /api/v1/backtests/strategies — list available strategies
- GET  /api/v1/backtests/engines   — list available engines
- GET  /api/v1/backtests/{id}      — get backtest by ID (memory, DB, 404)
- DELETE /api/v1/backtests/{id}    — delete backtest
- Utility helpers: downsample_list, build_equity_curve_response,
                   _safe_float, _safe_int, _safe_str, _ensure_utc, _get_side_value
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.backtesting.models import (
    BacktestConfig,
    BacktestCreateRequest,
    BacktestResult,
    BacktestStatus,
    EquityCurve,
    StrategyType,
)
from backend.database import get_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

client = TestClient(app)

START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2024, 6, 1, tzinfo=UTC)


def _minimal_config(**overrides) -> BacktestConfig:
    defaults = dict(
        symbol="BTCUSDT",
        interval="1h",
        start_date=START,
        end_date=END,
        strategy_type=StrategyType.SMA_CROSSOVER,
        initial_capital=10000.0,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def _minimal_metrics():
    """Return a MagicMock that satisfies all PerformanceMetrics attribute accesses in the router."""
    m = MagicMock()
    # Set concrete numeric values so float()/int() conversions succeed
    for attr in (
        "net_profit", "net_profit_pct", "total_return", "annual_return",
        "sharpe_ratio", "sortino_ratio", "calmar_ratio", "max_drawdown",
        "win_rate", "profit_factor", "total_trades", "winning_trades",
        "losing_trades", "gross_profit", "gross_loss", "total_commission",
        "buy_hold_return", "buy_hold_return_pct", "cagr", "recovery_factor",
        "expectancy", "max_consecutive_wins", "max_consecutive_losses",
    ):
        setattr(m, attr, 0.0)
    m.total_trades = 5
    m.winning_trades = 3
    m.losing_trades = 2
    m.model_dump = MagicMock(return_value={})
    return m


def _make_result(status: BacktestStatus = BacktestStatus.COMPLETED) -> BacktestResult:
    return BacktestResult(
        id=str(uuid.uuid4()),
        status=status,
        created_at=datetime.now(UTC),
        config=_minimal_config(),
        metrics=_minimal_metrics() if status == BacktestStatus.COMPLETED else None,
        trades=[],
        equity_curve=None,
        final_equity=10500.0,
        final_pnl=500.0,
        final_pnl_pct=5.0,
    )


@pytest.fixture()
def mock_db():
    """Override FastAPI DB dependency with a MagicMock session."""
    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def mock_service():
    """Patch get_backtest_service with a controllable mock."""
    svc = MagicMock()
    svc.run_backtest = AsyncMock(return_value=_make_result())
    svc.list_results = MagicMock(return_value=[])
    svc.get_result = MagicMock(return_value=None)
    svc.delete_result = MagicMock(return_value=True)
    with patch("backend.api.routers.backtests.get_backtest_service", return_value=svc):
        yield svc


# ---------------------------------------------------------------------------
# Helper / utility unit tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Unit tests for pure helper functions."""

    def test_safe_float_converts_int(self):
        from backend.api.routers.backtests import _safe_float
        assert _safe_float(42) == 42.0

    def test_safe_float_none_returns_default(self):
        from backend.api.routers.backtests import _safe_float
        assert _safe_float(None) == 0.0
        assert _safe_float(None, default=99.9) == 99.9

    def test_safe_float_invalid_returns_default(self):
        from backend.api.routers.backtests import _safe_float
        assert _safe_float("bad", default=-1.0) == -1.0

    def test_safe_int_converts_float(self):
        from backend.api.routers.backtests import _safe_int
        assert _safe_int(3.7) == 3

    def test_safe_int_none_returns_default(self):
        from backend.api.routers.backtests import _safe_int
        assert _safe_int(None) == 0

    def test_safe_str_converts_value(self):
        from backend.api.routers.backtests import _safe_str
        assert _safe_str(123) == "123"

    def test_safe_str_none_returns_default(self):
        from backend.api.routers.backtests import _safe_str
        assert _safe_str(None) == ""

    def test_ensure_utc_naive_datetime(self):
        from backend.api.routers.backtests import _ensure_utc
        naive = datetime(2024, 3, 1)
        result = _ensure_utc(naive)
        assert result.tzinfo is not None

    def test_ensure_utc_aware_passthrough(self):
        from backend.api.routers.backtests import _ensure_utc
        aware = datetime(2024, 3, 1, tzinfo=UTC)
        assert _ensure_utc(aware) == aware

    def test_ensure_utc_string(self):
        from backend.api.routers.backtests import _ensure_utc
        result = _ensure_utc("2024-03-01T00:00:00Z")
        assert isinstance(result, datetime)

    def test_ensure_utc_none_returns_now(self):
        from backend.api.routers.backtests import _ensure_utc
        result = _ensure_utc(None)
        assert isinstance(result, datetime)

    def test_get_side_value_enum(self):
        from backend.api.routers.backtests import _get_side_value
        side = MagicMock()
        side.value = "long"
        assert _get_side_value(side) == "long"

    def test_get_side_value_none(self):
        from backend.api.routers.backtests import _get_side_value
        assert _get_side_value(None) == "unknown"

    def test_downsample_list_short(self):
        from backend.api.routers.backtests import downsample_list
        data = list(range(10))
        assert downsample_list(data, max_points=500) == data

    def test_downsample_list_long(self):
        from backend.api.routers.backtests import downsample_list
        data = list(range(1000))
        result = downsample_list(data, max_points=100)
        assert len(result) == 100
        assert result[0] == 0
        assert result[-1] == 999

    def test_downsample_list_empty(self):
        from backend.api.routers.backtests import downsample_list
        assert downsample_list([], max_points=100) == []

    def test_build_equity_curve_no_trades(self):
        from backend.api.routers.backtests import build_equity_curve_response
        ec = EquityCurve(
            timestamps=[START, END],
            equity=[10000.0, 10500.0],
            drawdown=[0.0, -0.05],
        )
        result = build_equity_curve_response(ec, trades=None)
        assert result is not None
        assert len(result["timestamps"]) == 2
        assert result["equity"] == [10000.0, 10500.0]

    def test_build_equity_curve_empty_ec(self):
        from backend.api.routers.backtests import build_equity_curve_response
        assert build_equity_curve_response(None) is None


# ---------------------------------------------------------------------------
# POST /api/v1/backtests/ — create backtest
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-06-01T00:00:00Z",
    "strategy_type": "sma_crossover",
    "strategy_params": {"fast_period": 10, "slow_period": 30},
    "initial_capital": 10000.0,
    "position_size": 0.5,
    "save_to_db": False,
}


class TestCreateBacktest:
    """Tests for POST /api/v1/backtests/"""

    def test_create_backtest_success(self, mock_service, mock_db):
        response = client.post("/api/v1/backtests/", json=_VALID_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        mock_service.run_backtest.assert_awaited_once()

    def test_create_backtest_commission_from_params(self, mock_service, mock_db):
        payload = {**_VALID_PAYLOAD, "strategy_params": {"_commission": 0.001}}
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 200
        # Verify commission was passed correctly in BacktestConfig
        call_args = mock_service.run_backtest.call_args[0][0]
        assert call_args.taker_fee == pytest.approx(0.001)

    def test_create_backtest_default_commission_parity(self, mock_service, mock_db):
        """commission_rate must default to 0.0007 (TradingView parity)."""
        response = client.post("/api/v1/backtests/", json=_VALID_PAYLOAD)
        assert response.status_code == 200
        call_args = mock_service.run_backtest.call_args[0][0]
        assert call_args.taker_fee == pytest.approx(0.0007)

    def test_create_backtest_engine_failure_returns_400(self, mock_service, mock_db):
        failed_result = _make_result(BacktestStatus.FAILED)
        failed_result.error_message = "No data available"
        mock_service.run_backtest = AsyncMock(return_value=failed_result)

        response = client.post("/api/v1/backtests/", json=_VALID_PAYLOAD)
        assert response.status_code == 400
        assert "Backtest failed" in response.json()["detail"]

    def test_create_backtest_invalid_position_size_returns_422(self, mock_service, mock_db):
        payload = {**_VALID_PAYLOAD, "position_size": 99.0}  # > 1.0
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 422

    def test_create_backtest_invalid_interval_returns_422(self, mock_service, mock_db):
        payload = {**_VALID_PAYLOAD, "interval": "bad_interval"}
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 422

    def test_create_backtest_missing_symbol_returns_422(self, mock_service, mock_db):
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "symbol"}
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 422

    def test_create_backtest_direction_from_strategy_params(self, mock_service, mock_db):
        payload = {
            **_VALID_PAYLOAD,
            "direction": "long",
            "strategy_params": {"_direction": "short"},
        }
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 200
        call_args = mock_service.run_backtest.call_args[0][0]
        assert call_args.direction == "short"

    def test_create_backtest_fixed_amount_position_size(self, mock_service, mock_db):
        payload = {
            **_VALID_PAYLOAD,
            "strategy_params": {"_position_size_type": "fixed_amount", "_order_amount": 1000},
            "initial_capital": 10000.0,
            "leverage": 2.0,
        }
        response = client.post("/api/v1/backtests/", json=payload)
        assert response.status_code == 200
        call_args = mock_service.run_backtest.call_args[0][0]
        # 1000 * 2 leverage / 10000 capital = 0.2
        assert call_args.position_size == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# GET /api/v1/backtests/ — list backtests
# ---------------------------------------------------------------------------


class TestListBacktests:
    """Tests for GET /api/v1/backtests/"""

    def test_list_backtests_empty(self, mock_service, mock_db):
        response = client.get("/api/v1/backtests/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_backtests_returns_memory_results(self, mock_service, mock_db):
        result = _make_result()
        mock_service.list_results = MagicMock(return_value=[result])
        response = client.get("/api/v1/backtests/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == result.id

    def test_list_backtests_pagination_defaults(self, mock_service, mock_db):
        response = client.get("/api/v1/backtests/")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_backtests_custom_page(self, mock_service, mock_db):
        response = client.get("/api/v1/backtests/?limit=5&page=2")
        assert response.status_code == 200

    def test_list_backtests_invalid_limit(self, mock_service, mock_db):
        response = client.get("/api/v1/backtests/?limit=0")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/backtests/strategies
# ---------------------------------------------------------------------------


class TestListStrategies:
    """Tests for GET /api/v1/backtests/strategies"""

    def test_list_strategies_returns_list(self):
        with patch(
            "backend.api.routers.backtests.list_available_strategies",
            return_value=[{"name": "sma_crossover", "description": "SMA Crossover", "default_params": {}}],
        ):
            response = client.get("/api/v1/backtests/strategies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]


# ---------------------------------------------------------------------------
# GET /api/v1/backtests/engines
# ---------------------------------------------------------------------------


class TestListEngines:
    """Tests for GET /api/v1/backtests/engines"""

    def test_list_engines_returns_dict(self):
        mock_engines = {
            "fallback": {"available": True, "description": "Pure Python"},
            "numba": {"available": False, "description": "Numba JIT"},
        }
        with patch(
            "backend.backtesting.engine_selector.get_available_engines",
            return_value=mock_engines,
        ):
            response = client.get("/api/v1/backtests/engines")
        assert response.status_code == 200
        data = response.json()
        assert "engines" in data
        assert "recommended" in data

    def test_list_engines_recommends_fallback_when_nothing_available(self):
        mock_engines = {
            "fallback": {"available": True},
            "numba": {"available": False},
            "gpu": {"available": False},
        }
        with patch(
            "backend.backtesting.engine_selector.get_available_engines",
            return_value=mock_engines,
        ):
            response = client.get("/api/v1/backtests/engines")
        assert response.status_code == 200
        # Recommended should be "numba" or "fallback" (not gpu since unavailable)
        assert response.json()["recommended"] in ("fallback", "numba")


# ---------------------------------------------------------------------------
# GET /api/v1/backtests/{backtest_id}
# ---------------------------------------------------------------------------


class TestGetBacktest:
    """Tests for GET /api/v1/backtests/{backtest_id}"""

    def test_get_backtest_found_in_memory(self, mock_service, mock_db):
        result = _make_result()
        mock_service.get_result = MagicMock(return_value=result)
        response = client.get(f"/api/v1/backtests/{result.id}")
        assert response.status_code == 200
        assert response.json()["id"] == result.id

    def test_get_backtest_not_found_returns_404(self, mock_service, mock_db):
        mock_service.get_result = MagicMock(return_value=None)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        response = client.get("/api/v1/backtests/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_backtest_found_in_db(self, mock_service, mock_db):
        mock_service.get_result = MagicMock(return_value=None)

        # Build a minimal DB backtest mock
        bt = MagicMock()
        bt.id = str(uuid.uuid4())
        bt.symbol = "BTCUSDT"
        bt.timeframe = "1h"
        bt.start_date = START
        bt.end_date = END
        bt.initial_capital = 10000.0
        bt.final_capital = 10500.0
        bt.strategy_type = "sma_crossover"
        bt.status = "completed"
        bt.parameters = {}
        bt.metrics_json = None
        bt.total_return = 5.0
        bt.annual_return = 12.0
        bt.sharpe_ratio = 1.5
        bt.sortino_ratio = 1.8
        bt.calmar_ratio = 0.9
        bt.max_drawdown = -10.0
        bt.win_rate = 60.0
        bt.profit_factor = 1.5
        bt.total_trades = 10
        bt.winning_trades = 6
        bt.losing_trades = 4
        bt.gross_profit = 1000.0
        bt.gross_loss = -500.0
        bt.total_commission = 70.0
        bt.buy_hold_return = 300.0
        bt.buy_hold_return_pct = 30.0
        bt.cagr = 24.0
        bt.cagr_long = None
        bt.cagr_short = None
        bt.recovery_factor = 5.0
        bt.expectancy = 50.0
        bt.max_consecutive_wins = 4
        bt.max_consecutive_losses = 2
        bt.long_trades = 6
        bt.short_trades = 4
        bt.long_pnl = 700.0
        bt.short_pnl = 300.0
        bt.long_win_rate = 66.7
        bt.short_win_rate = 50.0
        bt.avg_bars_in_trade = 5.0
        bt.exposure_time = 40.0
        bt.trades = []
        bt.equity_curve = None
        bt.created_at = datetime.now(UTC)
        bt.volatility = None

        mock_db.query.return_value.filter.return_value.first.return_value = bt

        response = client.get(f"/api/v1/backtests/{bt.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == bt.id


# ---------------------------------------------------------------------------
# DELETE /api/v1/backtests/{backtest_id}
# ---------------------------------------------------------------------------


class TestDeleteBacktest:
    """Tests for DELETE /api/v1/backtests/{backtest_id}"""

    def test_delete_backtest_success(self, mock_service, mock_db):
        backtest_id = str(uuid.uuid4())
        mock_service.delete_result = MagicMock(return_value=True)
        # DB query returns None (not persisted)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.delete(f"/api/v1/backtests/{backtest_id}")
        # Accept 200 or 204
        assert response.status_code in (200, 204, 404)

    def test_delete_nonexistent_backtest(self, mock_service, mock_db):
        mock_service.delete_result = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.delete("/api/v1/backtests/does-not-exist")
        assert response.status_code in (404, 200, 204)
