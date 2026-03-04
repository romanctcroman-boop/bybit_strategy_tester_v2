"""
Unit tests for LiveSignalService.

Tests cover:
  - push_closed_bar returns dict with long/short keys
  - push_closed_bar returns error dict on adapter failure (expert fix #1)
  - Empty bar (volume=0) returns empty_bar dict without calling adapter
  - deque maxlen is respected (warmup_size truncation)
  - _build_df produces the correct column names for StrategyBuilderAdapter
  - window_size property reflects current window length
"""

from unittest.mock import MagicMock, patch

import pandas as pd

from backend.services.live_chart.signal_service import MIN_WARMUP_BARS, LiveSignalService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bars(n: int, base_price: float = 16_600.0) -> list[dict]:
    """Generate n synthetic OHLCV bars in chronological order."""
    return [
        {
            "time": 1_672_324_800 + i * 60,
            "open": base_price + i,
            "high": base_price + i + 100,
            "low": base_price + i - 100,
            "close": base_price + i + 50,
            "volume": 100.0 + i,
        }
        for i in range(n)
    ]


def _make_closed_bar(offset: int = 999, volume: float = 150.0) -> dict:
    return {
        "time": 1_672_324_800 + offset * 60,
        "open": 17_000.0,
        "high": 17_100.0,
        "low": 16_900.0,
        "close": 17_050.0,
        "volume": volume,
    }


def _mock_adapter_result(long: bool = False, short: bool = False, length: int = 200):
    """Build a fake StrategyBuilderAdapter result with entries/short_entries series."""

    entries_data = [False] * length
    short_entries_data = [False] * length
    if long and length > 0:
        entries_data[-1] = True
    if short and length > 0:
        short_entries_data[-1] = True

    result = MagicMock()
    result.entries = pd.Series(entries_data, dtype=bool)
    result.short_entries = pd.Series(short_entries_data, dtype=bool)
    return result


# ---------------------------------------------------------------------------
# push_closed_bar — happy path
# ---------------------------------------------------------------------------


class TestPushClosedBarHappyPath:
    def test_returns_dict_with_long_and_short_keys(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(long=True, length=201)
            svc = LiveSignalService({}, _make_bars(200))
            result = svc.push_closed_bar(_make_closed_bar())

        assert "long" in result
        assert "short" in result
        assert "bars_used" in result

    def test_long_signal_true_when_adapter_says_long(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(long=True, length=201)
            svc = LiveSignalService({}, _make_bars(200))
            result = svc.push_closed_bar(_make_closed_bar())

        assert result["long"] is True
        assert result["short"] is False

    def test_short_signal_true_when_adapter_says_short(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(short=True, length=201)
            svc = LiveSignalService({}, _make_bars(200))
            result = svc.push_closed_bar(_make_closed_bar())

        assert result["short"] is True
        assert result["long"] is False

    def test_bars_used_equals_window_plus_one(self):
        """After pushing a bar the window should grow by 1 (up to maxlen)."""
        warmup = _make_bars(100)
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(length=101)
            svc = LiveSignalService({}, warmup, warmup_size=200)
            result = svc.push_closed_bar(_make_closed_bar())

        assert result["bars_used"] == 101


# ---------------------------------------------------------------------------
# push_closed_bar — expert fix #1: structured error dict
# ---------------------------------------------------------------------------


class TestPushClosedBarError:
    def test_returns_error_dict_on_adapter_exception(self):
        """Expert fix: failure must return {error, long, short, bars_used}, never raise."""
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.side_effect = RuntimeError("boom")
            svc = LiveSignalService({}, _make_bars(50))
            result = svc.push_closed_bar(_make_closed_bar())

        assert result["long"] is False
        assert result["short"] is False
        assert "error" in result
        assert "boom" in result["error"]
        assert "bars_used" in result

    def test_error_dict_never_raises(self):
        """push_closed_bar must be exception-safe regardless of adapter error."""
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.side_effect = Exception("anything")
            svc = LiveSignalService({}, _make_bars(10))
            # Must not raise
            result = svc.push_closed_bar(_make_closed_bar())

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# push_closed_bar — expert fix #2: empty bar skip
# ---------------------------------------------------------------------------


class TestPushClosedBarEmptyBar:
    def test_volume_zero_returns_empty_bar_dict(self):
        """Expert fix: zero-volume bars must be skipped without calling adapter."""
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            svc = LiveSignalService({}, _make_bars(100))
            result = svc.push_closed_bar(_make_closed_bar(volume=0.0))

        # Adapter must NOT have been called
        MockAdapter.return_value.generate_signals.assert_not_called()
        assert result.get("empty_bar") is True
        assert result["long"] is False
        assert result["short"] is False

    def test_nonzero_volume_bar_is_processed_normally(self):
        """Volume > 0 must NOT be treated as empty."""
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(length=101)
            svc = LiveSignalService({}, _make_bars(100))
            result = svc.push_closed_bar(_make_closed_bar(volume=0.001))

        MockAdapter.return_value.generate_signals.assert_called_once()
        assert "empty_bar" not in result


# ---------------------------------------------------------------------------
# Window size / deque maxlen
# ---------------------------------------------------------------------------


class TestWindowSize:
    def test_window_truncated_to_warmup_size(self):
        """If warmup_bars > warmup_size, deque should hold only warmup_size bars."""
        svc_with_patch = None
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter"):
            svc_with_patch = LiveSignalService({}, _make_bars(500), warmup_size=50)

        assert svc_with_patch.window_size == 50

    def test_window_grows_after_push(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(length=51)
            svc = LiveSignalService({}, _make_bars(50), warmup_size=200)
            assert svc.window_size == 50
            svc.push_closed_bar(_make_closed_bar())
            assert svc.window_size == 51

    def test_window_does_not_exceed_maxlen(self):
        """After many pushes the window must never exceed warmup_size."""
        maxlen = 10
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter") as MockAdapter:
            MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(length=maxlen)
            svc = LiveSignalService({}, _make_bars(maxlen), warmup_size=maxlen)
            for i in range(50):
                MockAdapter.return_value.generate_signals.return_value = _mock_adapter_result(length=maxlen)
                svc.push_closed_bar(_make_closed_bar(offset=1000 + i))

        assert svc.window_size == maxlen

    def test_min_warmup_bars_constant_is_500(self):
        assert MIN_WARMUP_BARS == 500


# ---------------------------------------------------------------------------
# _build_df — column names
# ---------------------------------------------------------------------------


class TestBuildDf:
    def test_build_df_has_correct_columns(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter"):
            svc = LiveSignalService({}, _make_bars(5))

        df = svc._build_df()
        assert {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)

    def test_build_df_index_is_datetime(self):
        with patch("backend.services.live_chart.signal_service.StrategyBuilderAdapter"):
            svc = LiveSignalService({}, _make_bars(5))

        df = svc._build_df()
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.tz is not None  # must be UTC-aware
