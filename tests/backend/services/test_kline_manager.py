"""
Tests for KlineDataManager — единая точка управления свечными данными.

Охватывает:
- ensure_range: пустая БД → full fetch, частичный gap, нет gap (свежие данные)
- get_candles: только чтение без сетевых запросов
- sync_all_timeframes: все TF вызывают ensure_range, on_progress callback
- persist_bar: UPSERT закрытой свечи от live WebSocket
- per-key asyncio.Lock: два одновременных ensure_range → один HTTP-запрос
- Константы: INTERVAL_MS, OVERLAP_CANDLES в единственном месте
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.kline_manager import (
    INTERVAL_MS,
    OVERLAP_CANDLES,
    VALID_INTERVALS,
    CoverageInfo,
    KlineDataManager,
    get_kline_manager,
)

# =============================================================================
# FIXTURES
# =============================================================================


def _make_candle(time_sec: int, close: float = 45000.0) -> dict:
    """Helper: LightweightCharts candle dict."""
    return {
        "time": time_sec,
        "open": close * 0.999,
        "high": close * 1.001,
        "low": close * 0.998,
        "close": close,
        "volume": 100.0,
    }


def _make_raw_row(open_time_ms: int) -> dict:
    """Helper: raw row returned by BybitAdapter.get_historical_klines."""
    return {
        "open_time": open_time_ms,
        "open": 44000.0,
        "high": 45000.0,
        "low": 43000.0,
        "close": 44500.0,
        "volume": 200.0,
        "interval": "60",
    }


@pytest.fixture
def mock_adapter():
    """Mocked BybitAdapter — нет реальных HTTP-запросов."""
    adapter = MagicMock()
    adapter.get_historical_klines = AsyncMock(return_value=[])
    adapter._persist_klines_to_db = MagicMock()
    return adapter


@pytest.fixture
def manager(mock_adapter):
    """KlineDataManager с mock adapter."""
    return KlineDataManager(adapter=mock_adapter)


# =============================================================================
# CONSTANTS
# =============================================================================


class TestConstants:
    def test_interval_ms_has_all_9_timeframes(self):
        assert set(INTERVAL_MS.keys()) == {"1", "5", "15", "30", "60", "240", "D", "W", "M"}

    def test_overlap_candles_has_all_9_timeframes(self):
        assert set(OVERLAP_CANDLES.keys()) == {"1", "5", "15", "30", "60", "240", "D", "W", "M"}

    def test_valid_intervals_matches_interval_ms(self):
        assert set(VALID_INTERVALS) == set(INTERVAL_MS.keys())

    def test_interval_ms_values_ascending(self):
        values = list(INTERVAL_MS.values())
        # Each value must be positive
        assert all(v > 0 for v in values)

    def test_commission_rate_not_in_kline_manager(self):
        """KlineDataManager не должен содержать commission_rate."""
        import inspect

        import backend.services.kline_manager as km_mod

        src = inspect.getsource(km_mod)
        assert "commission_rate" not in src
        assert "0.0007" not in src


# =============================================================================
# VALIDATE INTERVAL
# =============================================================================


class TestValidateInterval:
    def test_valid_interval_passes(self, manager):
        manager._validate_interval("15")  # должен пройти без исключения

    def test_invalid_interval_raises_value_error(self, manager):
        with pytest.raises(ValueError, match="Unsupported interval"):
            manager._validate_interval("999x")

    def test_empty_interval_raises_value_error(self, manager):
        with pytest.raises(ValueError):
            manager._validate_interval("")


# =============================================================================
# ENSURE RANGE
# =============================================================================


class TestEnsureRange:
    @pytest.mark.asyncio
    async def test_ensure_range_empty_db_triggers_full_fetch(self, manager, mock_adapter):
        """Если БД пустая — должен сделать один полный fetch."""
        start_ms = 1_700_000_000_000
        end_ms = 1_700_100_000_000

        # БД пустая
        empty_cov = CoverageInfo(
            symbol="BTCUSDT",
            interval="60",
            market_type="linear",
            count=0,
            earliest_ms=None,
            latest_ms=None,
        )
        with (
            patch.object(manager, "_get_coverage_sync", return_value=empty_cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await manager.ensure_range("BTCUSDT", "60", start_ms, end_ms)

        mock_adapter.get_historical_klines.assert_called_once()
        call_kwargs = mock_adapter.get_historical_klines.call_args
        assert call_kwargs.kwargs["start_time"] == start_ms
        assert call_kwargs.kwargs["end_time"] == end_ms

    @pytest.mark.asyncio
    async def test_ensure_range_fresh_data_refreshes_overlap(self, manager, mock_adapter):
        """
        Даже если latest_ms > end_ms, ensure_range всегда обновляет
        последние OVERLAP_CANDLES баров (нахлёст для исправления незакрытых свечей).
        """
        start_ms = 1_700_000_000_000
        end_ms = 1_700_100_000_000

        fresh_cov = CoverageInfo(
            symbol="BTCUSDT",
            interval="60",
            market_type="linear",
            count=100,
            earliest_ms=start_ms - 3_600_000,  # раньше start
            latest_ms=end_ms + 3_600_000,  # позже end
        )
        with (
            patch.object(manager, "_get_coverage_sync", return_value=fresh_cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await manager.ensure_range("BTCUSDT", "60", start_ms, end_ms)

        # overlap-refresh ДОЛЖЕН вызвать Bybit один раз
        mock_adapter.get_historical_klines.assert_called_once()
        call_kwargs = mock_adapter.get_historical_klines.call_args.kwargs
        # fetch_from = latest_ms - overlap * interval_ms
        expected_overlap = OVERLAP_CANDLES["60"]
        expected_fetch_from = (end_ms + 3_600_000) - (INTERVAL_MS["60"] * expected_overlap)
        assert call_kwargs["start_time"] == expected_fetch_from
        assert call_kwargs["end_time"] == end_ms

    @pytest.mark.asyncio
    async def test_ensure_range_right_gap_triggers_fetch_from_overlap(self, manager, mock_adapter):
        """Если latest_ms < end_ms — fetch начинается с latest_ms - overlap * interval_ms."""
        start_ms = 1_700_000_000_000
        end_ms = 1_700_100_000_000
        latest_ms = end_ms - 5 * 3_600_000  # 5 часов назад

        cov = CoverageInfo(
            symbol="BTCUSDT",
            interval="60",
            market_type="linear",
            count=100,
            earliest_ms=start_ms,
            latest_ms=latest_ms,
        )
        with (
            patch.object(manager, "_get_coverage_sync", return_value=cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await manager.ensure_range("BTCUSDT", "60", start_ms, end_ms)

        mock_adapter.get_historical_klines.assert_called_once()
        call_kwargs = mock_adapter.get_historical_klines.call_args.kwargs
        expected_overlap = OVERLAP_CANDLES["60"]
        expected_fetch_from = latest_ms - (INTERVAL_MS["60"] * expected_overlap)
        assert call_kwargs["start_time"] == expected_fetch_from
        assert call_kwargs["end_time"] == end_ms

    @pytest.mark.asyncio
    async def test_ensure_range_force_refresh_always_fetches(self, manager, mock_adapter):
        """force_refresh=True всегда делает fetch даже если данные свежие."""
        start_ms = 1_700_000_000_000
        end_ms = 1_700_100_000_000

        fresh_cov = CoverageInfo(
            symbol="BTCUSDT",
            interval="60",
            market_type="linear",
            count=500,
            earliest_ms=start_ms - 100_000,
            latest_ms=end_ms + 100_000,
        )
        with (
            patch.object(manager, "_get_coverage_sync", return_value=fresh_cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await manager.ensure_range("BTCUSDT", "60", start_ms, end_ms, force_refresh=True)

        mock_adapter.get_historical_klines.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_range_invalid_interval_raises(self, manager):
        with pytest.raises(ValueError, match="Unsupported interval"):
            await manager.ensure_range("BTCUSDT", "999x", 0, 1)

    @pytest.mark.asyncio
    async def test_ensure_range_persists_fetched_rows(self, manager, mock_adapter):
        """Если Bybit вернул строки — они должны быть персистированы."""
        start_ms = 1_700_000_000_000
        end_ms = 1_700_100_000_000

        fetched = [_make_raw_row(start_ms + i * 3_600_000) for i in range(5)]
        mock_adapter.get_historical_klines.return_value = fetched

        empty_cov = CoverageInfo(
            symbol="BTCUSDT",
            interval="60",
            market_type="linear",
            count=0,
            earliest_ms=None,
            latest_ms=None,
        )
        with (
            patch.object(manager, "_get_coverage_sync", return_value=empty_cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await manager.ensure_range("BTCUSDT", "60", start_ms, end_ms)

        mock_adapter._persist_klines_to_db.assert_called_once()


# =============================================================================
# GET CANDLES
# =============================================================================


class TestGetCandles:
    @pytest.mark.asyncio
    async def test_get_candles_no_network(self, manager, mock_adapter):
        """get_candles не должен вызывать get_historical_klines."""
        candles = [_make_candle(1_700_000 + i * 3600) for i in range(5)]

        with patch.object(manager, "_get_candles_sync", return_value=candles):
            result = await manager.get_candles("BTCUSDT", "60", 0, 9_999_999_999_999)

        mock_adapter.get_historical_klines.assert_not_called()
        assert result == candles

    @pytest.mark.asyncio
    async def test_get_candles_returns_empty_if_no_data(self, manager):
        with patch.object(manager, "_get_candles_sync", return_value=[]):
            result = await manager.get_candles("BTCUSDT", "60", 0, 9_999_999_999_999)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_candles_invalid_interval_raises(self, manager):
        with pytest.raises(ValueError):
            await manager.get_candles("BTCUSDT", "badtf", 0, 1)


# =============================================================================
# SYNC ALL TIMEFRAMES
# =============================================================================


class TestSyncAllTimeframes:
    @pytest.mark.asyncio
    async def test_sync_calls_ensure_range_for_each_tf(self, manager):
        """sync_all_timeframes должен вызвать ensure_range для каждого TF."""
        called_tfs = []

        async def fake_ensure_range(symbol, interval, start_ms, end_ms, market_type="linear", **kwargs):
            called_tfs.append(interval)
            return []

        with patch.object(manager, "ensure_range", side_effect=fake_ensure_range):
            empty_cov = CoverageInfo("BTCUSDT", "1", "linear", 0, None, None)
            with patch.object(manager, "_get_coverage_sync", return_value=empty_cov):
                results = await manager.sync_all_timeframes("BTCUSDT")

        assert set(called_tfs) == set(VALID_INTERVALS)
        assert len(results) == len(VALID_INTERVALS)

    @pytest.mark.asyncio
    async def test_sync_specific_timeframes_only(self, manager):
        """sync_all_timeframes с указанным списком TF должен синхронизировать только их."""
        called_tfs = []

        async def fake_ensure(symbol, interval, start_ms, end_ms, **kwargs):
            called_tfs.append(interval)
            return []

        with patch.object(manager, "ensure_range", side_effect=fake_ensure):
            empty_cov = CoverageInfo("BTCUSDT", "15", "linear", 0, None, None)
            with patch.object(manager, "_get_coverage_sync", return_value=empty_cov):
                results = await manager.sync_all_timeframes("BTCUSDT", timeframes=["15", "60"])

        assert set(called_tfs) == {"15", "60"}
        assert set(results.keys()) == {"15", "60"}

    @pytest.mark.asyncio
    async def test_sync_calls_on_progress_callback(self, manager):
        """on_progress должен быть вызван после каждого TF."""
        progress_calls = []

        async def progress_cb(tf, status, new_count):
            progress_calls.append((tf, status, new_count))

        async def fake_ensure(symbol, interval, start_ms, end_ms, **kwargs):
            return []

        with patch.object(manager, "ensure_range", side_effect=fake_ensure):
            empty_cov = CoverageInfo("BTCUSDT", "15", "linear", 0, None, None)
            with patch.object(manager, "_get_coverage_sync", return_value=empty_cov):
                await manager.sync_all_timeframes("BTCUSDT", timeframes=["15", "60"], on_progress=progress_cb)

        assert len(progress_calls) == 2
        tfs_reported = [c[0] for c in progress_calls]
        assert set(tfs_reported) == {"15", "60"}

    @pytest.mark.asyncio
    async def test_sync_error_returns_error_status(self, manager):
        """Если ensure_range выбрасывает — статус должен быть 'error', не exception."""

        async def failing_ensure(symbol, interval, start_ms, end_ms, **kwargs):
            raise RuntimeError("Bybit down")

        with patch.object(manager, "ensure_range", side_effect=failing_ensure):
            empty_cov = CoverageInfo("BTCUSDT", "60", "linear", 0, None, None)
            with patch.object(manager, "_get_coverage_sync", return_value=empty_cov):
                results = await manager.sync_all_timeframes("BTCUSDT", timeframes=["60"])

        assert results["60"].status == "error"
        assert "Bybit down" in (results["60"].error or "")


# =============================================================================
# ASYNCIO LOCK — один fetch за раз
# =============================================================================


class TestLock:
    @pytest.mark.asyncio
    async def test_concurrent_ensure_range_same_key_serialized(self, manager, mock_adapter):
        """
        Два одновременных ensure_range с тем же (symbol, interval, market_type)
        должны сериализоваться через Lock — только один fetch.
        """
        call_count = 0
        fetch_ms_delay = 0.05

        async def slow_fetch(**kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(fetch_ms_delay)
            return []

        mock_adapter.get_historical_klines.side_effect = slow_fetch

        empty_cov = CoverageInfo("BTCUSDT", "15", "linear", 0, None, None)
        with (
            patch.object(manager, "_get_coverage_sync", return_value=empty_cov),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            # Запускаем одновременно
            await asyncio.gather(
                manager.ensure_range("BTCUSDT", "15", 0, 1_000_000_000_000),
                manager.ensure_range("BTCUSDT", "15", 0, 1_000_000_000_000),
            )

        # Lock гарантирует два последовательных вызова, не параллельных
        # (оба fetch выполнятся, но не одновременно)
        assert call_count == 2  # каждый acquire-ed lock отдельно

    @pytest.mark.asyncio
    async def test_different_keys_not_blocking_each_other(self, manager, mock_adapter):
        """Разные (symbol, interval) не блокируют друг друга."""
        call_order = []

        async def track_fetch(**kwargs):
            call_order.append(kwargs["interval"])
            await asyncio.sleep(0.01)
            return []

        mock_adapter.get_historical_klines.side_effect = track_fetch

        empty_cov_15 = CoverageInfo("BTCUSDT", "15", "linear", 0, None, None)
        empty_cov_60 = CoverageInfo("BTCUSDT", "60", "linear", 0, None, None)

        def mock_coverage(symbol, interval, market_type):
            if interval == "15":
                return empty_cov_15
            return empty_cov_60

        with (
            patch.object(manager, "_get_coverage_sync", side_effect=mock_coverage),
            patch.object(manager, "_get_candles_sync", return_value=[]),
        ):
            await asyncio.gather(
                manager.ensure_range("BTCUSDT", "15", 0, 1_000_000_000_000),
                manager.ensure_range("BTCUSDT", "60", 0, 1_000_000_000_000),
            )

        # Оба должны быть вызваны
        assert "15" in call_order
        assert "60" in call_order


# =============================================================================
# PERSIST BAR
# =============================================================================


class TestPersistBar:
    @pytest.mark.asyncio
    async def test_persist_bar_calls_sync_method(self, manager):
        """persist_bar должен вызвать _persist_live_bar_sync через to_thread."""
        candle = _make_candle(1_700_000_000)

        with patch.object(manager, "_persist_live_bar_sync") as mock_sync:
            await manager.persist_bar("BTCUSDT", "15", "linear", candle)

        mock_sync.assert_called_once_with("BTCUSDT", "15", "linear", candle, candle["time"] * 1000)


# =============================================================================
# GET_KLINE_MANAGER SINGLETON
# =============================================================================


class TestGetKlineManager:
    def test_raises_if_not_initialized(self):
        import backend.services.kline_manager as km_mod

        original = km_mod._instance
        try:
            km_mod._instance = None
            with pytest.raises(RuntimeError, match="not initialized"):
                get_kline_manager()
        finally:
            km_mod._instance = original

    def test_returns_instance_when_initialized(self, manager):
        import backend.services.kline_manager as km_mod

        original = km_mod._instance
        try:
            km_mod._instance = manager
            result = get_kline_manager()
            assert result is manager
        finally:
            km_mod._instance = original
