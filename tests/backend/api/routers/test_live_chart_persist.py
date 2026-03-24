"""
Tests for persist_bar() and _persist_live_bar_sync()
(P1: Save live candles to BybitKlineAudit on bar_closed)

After Рек. 7, the sync UPSERT helper lives in:
    backend/services/kline_manager.py → KlineDataManager._persist_live_bar_sync

The async wrapper _persist_live_bar lives in:
    backend/api/routers/marketdata.py → _persist_live_bar
    (delegates to kline_manager.persist_bar())
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.services.kline_manager import KlineDataManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CANDLE = {
    "time": 1_700_000_000,  # seconds (LightweightCharts format)
    "open": 100.0,
    "high": 101.5,
    "low": 99.0,
    "close": 100.8,
    "volume": 500.0,
}

OPEN_TIME_MS = SAMPLE_CANDLE["time"] * 1000  # 1_700_000_000_000


def _make_in_memory_session():
    """Return an in-memory SQLite session wired to the full ORM Base."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# Unit tests for _persist_live_bar_sync
# ---------------------------------------------------------------------------


class TestPersistLiveBarSync:
    """Unit tests for the synchronous DB-write helper (now in KlineDataManager)."""

    def _make_manager(self) -> KlineDataManager:
        """Create a KlineDataManager with a dummy adapter (not used for persist)."""
        adapter = MagicMock()
        return KlineDataManager(adapter=adapter)

    def test_bar_inserted_to_db(self):
        """Closed bar is written to bybit_kline_audit."""
        from backend.models.bybit_kline_audit import BybitKlineAudit

        manager = self._make_manager()
        session = _make_in_memory_session()
        bind = session.get_bind()

        # Patch SessionLocal so it returns our in-memory session
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("backend.database.SessionLocal", return_value=mock_ctx):
            # Simulate dialect = sqlite (in-memory)
            bind.dialect.name = "sqlite"
            manager._persist_live_bar_sync("ETHUSDT", "30", "linear", SAMPLE_CANDLE, OPEN_TIME_MS)

        row = (
            session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == "ETHUSDT",
                BybitKlineAudit.open_time == OPEN_TIME_MS,
            )
            .first()
        )
        assert row is not None, "Bar should be inserted"
        assert row.close_price == pytest.approx(100.8)
        assert row.high_price == pytest.approx(101.5)
        assert row.low_price == pytest.approx(99.0)
        assert row.volume == pytest.approx(500.0)
        assert row.interval == "30"
        assert row.market_type == "linear"

    def test_bar_fields_are_correct(self):
        """All OHLCV fields map correctly from candle dict."""
        from backend.models.bybit_kline_audit import BybitKlineAudit

        candle = {
            "time": 1_700_100_000,
            "open": 200.0,
            "high": 205.0,
            "low": 198.0,
            "close": 203.5,
            "volume": 1234.5,
        }
        open_ms = candle["time"] * 1000

        manager = self._make_manager()
        session = _make_in_memory_session()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("backend.database.SessionLocal", return_value=mock_ctx):
            manager._persist_live_bar_sync("BTCUSDT", "60", "spot", candle, open_ms)

        row = session.query(BybitKlineAudit).filter(BybitKlineAudit.open_time == open_ms).first()
        assert row is not None
        assert row.symbol == "BTCUSDT"
        assert row.interval == "60"
        assert row.market_type == "spot"
        assert row.open_price == pytest.approx(200.0)
        assert row.high_price == pytest.approx(205.0)
        assert row.low_price == pytest.approx(198.0)
        assert row.close_price == pytest.approx(203.5)
        assert row.volume == pytest.approx(1234.5)

    def test_raw_is_empty_json_object(self):
        """raw column is stored as '{}' when not available from WS."""
        from backend.models.bybit_kline_audit import BybitKlineAudit

        manager = self._make_manager()
        session = _make_in_memory_session()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("backend.database.SessionLocal", return_value=mock_ctx):
            manager._persist_live_bar_sync("SOLUSDT", "15", "linear", SAMPLE_CANDLE, OPEN_TIME_MS)

        row = session.query(BybitKlineAudit).first()
        assert row is not None
        assert row.raw == "{}"

    def test_volume_used_as_turnover_approximation(self):
        """turnover stores volume when WS data has no turnover field."""
        from backend.models.bybit_kline_audit import BybitKlineAudit

        manager = self._make_manager()
        session = _make_in_memory_session()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("backend.database.SessionLocal", return_value=mock_ctx):
            manager._persist_live_bar_sync("BTCUSDT", "5", "linear", SAMPLE_CANDLE, OPEN_TIME_MS)

        row = session.query(BybitKlineAudit).first()
        assert row is not None
        assert row.turnover == pytest.approx(SAMPLE_CANDLE["volume"])

    def test_db_error_is_propagated_to_caller(self):
        """DB errors propagate — _persist_live_bar catches them as warnings."""
        manager = self._make_manager()

        mock_ctx = MagicMock()
        broken_session = MagicMock()
        broken_session.execute.side_effect = RuntimeError("DB locked")
        mock_ctx.__enter__ = MagicMock(return_value=broken_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("backend.database.SessionLocal", return_value=mock_ctx),
            pytest.raises(RuntimeError, match="DB locked"),
        ):
            manager._persist_live_bar_sync("BTCUSDT", "5", "linear", SAMPLE_CANDLE, OPEN_TIME_MS)


# ---------------------------------------------------------------------------
# Async tests for _persist_live_bar (wrapper)
# ---------------------------------------------------------------------------


class TestPersistLiveBar:
    """Async wrapper tests — fire-and-forget, errors silently logged.

    After Рек. 7: _persist_live_bar delegates to km.persist_bar()
    (not asyncio.to_thread with _persist_live_bar_sync).
    """

    @pytest.mark.asyncio
    async def test_delegates_to_kline_manager_persist_bar(self):
        """_persist_live_bar calls km.persist_bar()."""
        from backend.api.routers.marketdata import _persist_live_bar

        mock_km = MagicMock()
        mock_km.persist_bar = AsyncMock(return_value=None)

        with patch(
            "backend.services.kline_manager.get_kline_manager",
            return_value=mock_km,
        ):
            await _persist_live_bar("BTCUSDT", "60", "linear", SAMPLE_CANDLE)

        mock_km.persist_bar.assert_awaited_once_with("BTCUSDT", "60", "linear", SAMPLE_CANDLE)

    @pytest.mark.asyncio
    async def test_passes_all_arguments_to_persist_bar(self):
        """All 4 arguments (symbol, interval, market_type, candle) are forwarded."""
        from backend.api.routers.marketdata import _persist_live_bar

        custom_candle = {**SAMPLE_CANDLE, "time": 1_700_000_123}
        mock_km = MagicMock()
        mock_km.persist_bar = AsyncMock(return_value=None)

        with patch(
            "backend.services.kline_manager.get_kline_manager",
            return_value=mock_km,
        ):
            await _persist_live_bar("ETHUSDT", "15", "spot", custom_candle)

        mock_km.persist_bar.assert_awaited_once_with("ETHUSDT", "15", "spot", custom_candle)

    @pytest.mark.asyncio
    async def test_error_logged_not_raised(self):
        """DB errors in _persist_live_bar are swallowed (non-critical path)."""
        from backend.api.routers.marketdata import _persist_live_bar

        mock_km = MagicMock()
        mock_km.persist_bar = AsyncMock(side_effect=Exception("network error"))

        with patch(
            "backend.services.kline_manager.get_kline_manager",
            return_value=mock_km,
        ):
            # Should NOT raise — just logs a warning
            await _persist_live_bar("BTCUSDT", "60", "linear", SAMPLE_CANDLE)

    @pytest.mark.asyncio
    async def test_warning_logged_on_error(self, caplog):
        """logger.warning is called when persist fails."""
        import logging

        from backend.api.routers.marketdata import _persist_live_bar

        mock_km = MagicMock()
        mock_km.persist_bar = AsyncMock(side_effect=Exception("timeout"))

        with (
            patch(
                "backend.services.kline_manager.get_kline_manager",
                return_value=mock_km,
            ),
            caplog.at_level(logging.WARNING),
        ):
            await _persist_live_bar("ETHUSDT", "15", "spot", SAMPLE_CANDLE)

        assert any(
            "Failed to persist live bar" in r.message or "persist" in r.message.lower() for r in caplog.records
        ), "Expected a warning log message about failed persist"


# ---------------------------------------------------------------------------
# Integration: market_type parameter in SSE signature
# ---------------------------------------------------------------------------


class TestSSEMarketTypeParam:
    """Verify the SSE endpoint signature includes market_type."""

    def test_live_chart_stream_has_market_type_param(self):
        """live_chart_stream() must accept market_type query parameter."""
        import inspect

        from backend.api.routers.marketdata import live_chart_stream

        sig = inspect.signature(live_chart_stream)
        assert "market_type" in sig.parameters, "live_chart_stream must have market_type parameter"

    def test_market_type_default_is_linear(self):
        """Default value for market_type must be 'linear'."""
        import inspect

        from backend.api.routers.marketdata import live_chart_stream

        sig = inspect.signature(live_chart_stream)
        param = sig.parameters["market_type"]
        # FastAPI wraps defaults in Query(…), but the .default or annotation holds 'linear'
        default_val = param.default
        # Either the default is 'linear' directly, or it's a Query with default='linear'
        if hasattr(default_val, "default"):
            assert default_val.default == "linear"
        else:
            assert default_val == "linear"
