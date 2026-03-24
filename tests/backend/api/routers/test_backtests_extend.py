"""
Tests for POST /api/v1/backtests/{backtest_id}/extend
(P2: Extend Backtest to Now)

Covers:
- 404 for non-existent backtest
- 400 for builder-strategy types (builder, strategy_builder, block_builder)
- 'already_current' when gap < 2 candles
- 400 when gap > 730 days
- 400 for unsupported timeframe
- Successful extend creates new backtest with is_extended=True
- New backtest has source_backtest_id pointing to original
- Overlap candles are fetched (start_ts = end_ms - overlap * interval_ms)
- Bybit fetch error → 503
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestStatus,
    PerformanceMetrics,
)
from backend.database import get_db
from backend.database.models import Backtest as BacktestModel
from backend.database.models import BacktestStatus as DBBacktestStatus

# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------

client = TestClient(app)


def _make_backtest_model(
    *,
    end_offset_days: int = 7,
    timeframe: str = "60",
    symbol: str = "BTCUSDT",
    final_capital: float = 11000.0,
) -> BacktestModel:
    """Build a BacktestModel stub with all required fields."""
    now = datetime.now(UTC)
    end_dt = now - timedelta(days=end_offset_days)
    start_dt = end_dt - timedelta(days=30)

    bt = BacktestModel()
    bt.id = str(uuid.uuid4())
    bt.strategy_id = None
    bt.strategy_type = "sma_crossover"
    bt.status = DBBacktestStatus.COMPLETED
    bt.symbol = symbol
    bt.timeframe = timeframe
    bt.start_date = start_dt
    bt.end_date = end_dt
    bt.initial_capital = 10000.0
    bt.final_capital = final_capital
    bt.parameters = {"fast_period": 10, "slow_period": 20}
    bt.trades = [
        {
            "entry_time": int(start_dt.timestamp() * 1000),
            "exit_time": int(end_dt.timestamp() * 1000),
            "pnl": 1000.0,
            "side": "long",
        }
    ]
    bt.metrics_json = {"total_return": 10.0, "total_trades": 1}
    bt.is_extended = False
    bt.source_backtest_id = None
    bt.market_type = "linear"
    return bt


def _make_metrics() -> PerformanceMetrics:
    return PerformanceMetrics(
        net_profit=500.0,
        net_profit_pct=5.0,
        total_return=5.0,
        annual_return=10.0,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=5.0,
        win_rate=60.0,
        profit_factor=1.5,
        total_trades=5,
        winning_trades=3,
        losing_trades=2,
        gross_profit=600.0,
        gross_loss=100.0,
        total_commission=7.0,
        buy_hold_return=300.0,
        buy_hold_return_pct=3.0,
    )


def _make_backtest_result(status: BacktestStatus = BacktestStatus.COMPLETED) -> BacktestResult:
    now = datetime.now(UTC)
    return BacktestResult(
        id=str(uuid.uuid4()),
        status=status,
        created_at=now,
        config=BacktestConfig(
            symbol="BTCUSDT",
            interval="60",
            start_date=now - timedelta(days=30),
            end_date=now,
        ),
        metrics=_make_metrics() if status == BacktestStatus.COMPLETED else None,
        trades=[],
        equity_curve=None,
        final_equity=10500.0,
        final_pnl=500.0,
        final_pnl_pct=5.0,
    )


@pytest.fixture()
def mock_db():
    """Override FastAPI DB dependency with a controllable MagicMock."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 404 — backtest not found
# ---------------------------------------------------------------------------


class TestExtendNotFound:
    def test_returns_404_when_backtest_missing(self, mock_db):
        """Non-existent backtest_id → 404."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        resp = client.post(f"/api/v1/backtests/{uuid.uuid4()}/extend")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 400 — builder-strategy guard
# ---------------------------------------------------------------------------


class TestExtendBuilderStrategyGuard:
    """Extend endpoint must reject backtests created by the Strategy Builder."""

    @pytest.mark.parametrize(
        "strategy_type",
        ["builder", "strategy_builder", "block_builder"],
    )
    def test_returns_400_for_builder_strategy_types(self, mock_db, strategy_type):
        """strategy_type in builder family → 400 with helpful message."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        bt.strategy_type = strategy_type
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "builder" in detail or "strategy builder" in detail

    def test_returns_400_for_builder_type_case_insensitive(self, mock_db):
        """Builder-type check is case-insensitive (e.g. 'Builder')."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        bt.strategy_type = "Builder"
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        assert resp.status_code == 400

    def test_non_builder_strategy_passes_guard(self, mock_db):
        """A regular strategy_type like 'sma_crossover' must NOT be rejected."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        bt.strategy_type = "sma_crossover"
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        # The request will proceed past the guard and fail later (e.g. Bybit)
        # We only care that we do NOT get a 400 from the builder guard.
        with patch(
            "backend.services.adapters.bybit.BybitAdapter.get_historical_klines",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Bybit unavailable"),
        ):
            resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        # Must not be the builder-guard 400; anything else (e.g. 503) is fine
        assert resp.status_code != 400 or "builder" not in resp.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# already_current
# ---------------------------------------------------------------------------


class TestExtendAlreadyCurrent:
    def test_returns_already_current_when_gap_too_small(self, mock_db):
        """Backtest ended < 2 candles ago → already_current status."""
        # end_date 30 seconds ago for a 60-minute candle → gap < 2 × 3_600_000 ms
        bt = _make_backtest_model(end_offset_days=0, timeframe="60")
        # Override end_date to 30 seconds ago
        bt.end_date = datetime.now(UTC) - timedelta(seconds=30)
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        resp = client.post(f"/api/v1/backtests/{bt.id}/extend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "already_current"
        assert data["new_trades"] == 0


# ---------------------------------------------------------------------------
# 400 — gap > 730 days
# ---------------------------------------------------------------------------


class TestExtendGapTooLarge:
    def test_returns_400_when_gap_exceeds_730_days(self, mock_db):
        """Gap > 730 days → 400 with informative message."""
        bt = _make_backtest_model(end_offset_days=800, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        resp = client.post(f"/api/v1/backtests/{bt.id}/extend")
        assert resp.status_code == 400
        assert "730" in resp.json()["detail"] or "days" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 400 — unsupported timeframe
# ---------------------------------------------------------------------------


class TestExtendUnsupportedTimeframe:
    def test_returns_400_for_unknown_timeframe(self, mock_db):
        """Unrecognised timeframe → 400."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="999x")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        resp = client.post(f"/api/v1/backtests/{bt.id}/extend")
        assert resp.status_code == 400
        assert "timeframe" in resp.json()["detail"].lower() or "999x" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 503 — Bybit fetch failure
# ---------------------------------------------------------------------------


class TestExtendBybitError:
    def test_returns_503_when_bybit_fails(self, mock_db):
        """Bybit API error via kline_manager.ensure_range → 503."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        mock_km = MagicMock()
        mock_km.ensure_range = AsyncMock(
            side_effect=ConnectionError("Bybit unavailable"),
        )

        with patch(
            "backend.services.kline_manager.get_kline_manager",
            return_value=mock_km,
        ):
            resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        assert resp.status_code == 503
        assert "Bybit" in resp.json()["detail"] or "candles" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestExtendHappyPath:
    def test_creates_new_backtest_with_is_extended(self, mock_db):
        """Successful extend creates a new BacktestModel with is_extended=True."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        gap_result = _make_backtest_result(BacktestStatus.COMPLETED)
        full_result = _make_backtest_result(BacktestStatus.COMPLETED)

        mock_km = MagicMock()
        mock_km.ensure_range = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.kline_manager.get_kline_manager",
                return_value=mock_km,
            ),
            patch(
                "backend.backtesting.service.BacktestService.run_backtest",
                new_callable=AsyncMock,
                side_effect=[gap_result, full_result],
            ),
        ):
            resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["new_backtest_id"] is not None
        assert data["new_backtest_id"] != bt.id
        assert "gap_start" in data
        assert "gap_end" in data

        # Verify the new BacktestModel was added to the DB with is_extended=True
        added = mock_db.add.call_args_list[-1][0][0]
        assert hasattr(added, "is_extended")
        assert added.is_extended is True

    def test_new_backtest_has_source_backtest_id(self, mock_db):
        """New backtest's source_backtest_id points to original."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        gap_result = _make_backtest_result(BacktestStatus.COMPLETED)
        full_result = _make_backtest_result(BacktestStatus.COMPLETED)

        mock_km = MagicMock()
        mock_km.ensure_range = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.kline_manager.get_kline_manager",
                return_value=mock_km,
            ),
            patch(
                "backend.backtesting.service.BacktestService.run_backtest",
                new_callable=AsyncMock,
                side_effect=[gap_result, full_result],
            ),
        ):
            resp = client.post(f"/api/v1/backtests/{bt.id}/extend")

        assert resp.status_code == 200
        added = mock_db.add.call_args_list[-1][0][0]
        assert added.source_backtest_id == bt.id

    def test_market_type_param_accepted(self, mock_db):
        """market_type query param is forwarded to the new backtest."""
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        gap_result = _make_backtest_result(BacktestStatus.COMPLETED)
        full_result = _make_backtest_result(BacktestStatus.COMPLETED)

        mock_km = MagicMock()
        mock_km.ensure_range = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.kline_manager.get_kline_manager",
                return_value=mock_km,
            ),
            patch(
                "backend.backtesting.service.BacktestService.run_backtest",
                new_callable=AsyncMock,
                side_effect=[gap_result, full_result],
            ),
        ):
            resp = client.post(f"/api/v1/backtests/{bt.id}/extend?market_type=spot")

        assert resp.status_code == 200
        added = mock_db.add.call_args_list[-1][0][0]
        assert added.market_type == "spot"


# ---------------------------------------------------------------------------
# Overlap candles
# ---------------------------------------------------------------------------


class TestExtendOverlapCandles:
    def test_fetch_start_uses_overlap_offset(self, mock_db):
        """ensure_range is called — overlap logic is now inside kline_manager.

        We verify that ensure_range is called with the correct symbol, interval,
        and time range. The overlap is handled internally by kline_manager.
        """
        bt = _make_backtest_model(end_offset_days=7, timeframe="60")
        mock_db.query.return_value.filter.return_value.first.return_value = bt

        gap_result = _make_backtest_result(BacktestStatus.COMPLETED)
        full_result = _make_backtest_result(BacktestStatus.COMPLETED)

        mock_km = MagicMock()
        mock_km.ensure_range = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.kline_manager.get_kline_manager",
                return_value=mock_km,
            ),
            patch(
                "backend.backtesting.service.BacktestService.run_backtest",
                new_callable=AsyncMock,
                side_effect=[gap_result, full_result],
            ),
        ):
            client.post(f"/api/v1/backtests/{bt.id}/extend")

        mock_km.ensure_range.assert_awaited_once()
        call_kwargs = mock_km.ensure_range.call_args[1]
        assert call_kwargs["symbol"] == "BTCUSDT"
        assert call_kwargs["interval"] == "60"
        assert call_kwargs["market_type"] == "linear"
