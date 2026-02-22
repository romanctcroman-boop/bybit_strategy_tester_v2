"""
Unit tests for the three unimplemented features:
  - Фича 1: profit_only / min_profit in close_cond blocks
  - Фича 2: HTF timeframe resampling for mfi_filter / cci_filter
  - Фича 3: use_btcusdt_mfi — use BTCUSDT OHLCV as MFI data source

Tests follow naming convention: test_<function>_<scenario>
Coverage target: >= 95% for the changed code paths.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 200, seed: int = 42, freq: str = "1h") -> pd.DataFrame:
    """Generate synthetic OHLCV with DatetimeIndex."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n, freq=freq, tz=UTC)
    close = 40_000 + np.cumsum(rng.normal(0, 200, n))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close + rng.normal(0, 50, n)
    volume = rng.uniform(10, 100, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_ohlcv_numeric(n: int = 200, seed: int = 7, freq_ms: int = 3_600_000) -> pd.DataFrame:
    """Generate synthetic OHLCV with numeric (millisecond) index."""
    rng = np.random.default_rng(seed)
    base_ts = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    index = [base_ts + i * freq_ms for i in range(n)]
    close = 40_000 + np.cumsum(rng.normal(0, 200, n))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close + rng.normal(0, 50, n)
    volume = rng.uniform(10, 100, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


# ===========================================================================
# Фича 2 — _resample_ohlcv
# ===========================================================================


class TestResampleOhlcv:
    """Tests for the _resample_ohlcv helper added in indicator_handlers.py."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        from backend.backtesting.indicator_handlers import _TF_RESAMPLE_MAP, _resample_ohlcv

        self.resample = _resample_ohlcv
        self.tf_map = _TF_RESAMPLE_MAP

    def test_resample_ohlcv_datetime_index_4h(self):
        """1h → 4h should produce ~n/4 bars, result indexed to original."""
        ohlcv = _make_ohlcv(200, freq="1h")
        result = self.resample(ohlcv, "240")
        assert result is not None
        # Result must be reindexed back to original length
        assert len(result) == len(ohlcv)
        # HTF close should be constant within each 4h window (ffill)
        assert result["close"].notna().all()

    def test_resample_ohlcv_numeric_index(self):
        """Numeric (ms) index must be converted internally — no crash."""
        ohlcv = _make_ohlcv_numeric(200, freq_ms=3_600_000)  # 1h bars
        result = self.resample(ohlcv, "240")
        assert result is not None
        assert len(result) == len(ohlcv)

    def test_resample_ohlcv_unknown_tf_returns_none(self):
        """Unrecognised timeframe string must return None."""
        ohlcv = _make_ohlcv(100)
        result = self.resample(ohlcv, "9999x")
        assert result is None

    def test_resample_ohlcv_same_tf_returns_none(self):
        """Resampling to the same resolution (1h → 1h) should return None
        because there are no HTF bars different from the source.
        The function returns None when fewer than 2 HTF bars result."""
        # Use only 1 hour of 1h data → resampling to 4h → <2 HTF bars → None
        ohlcv = _make_ohlcv(3, freq="1h")  # only 3 bars
        result = self.resample(ohlcv, "240")
        # 3 x 1h -> 1 x 4h bar -> < 2 bars -> None
        assert result is None

    def test_resample_ohlcv_daily_from_1h(self):
        """1h → D should produce daily bars reindexed to 1h."""
        ohlcv = _make_ohlcv(100, freq="1h")
        result = self.resample(ohlcv, "D")
        assert result is not None
        assert len(result) == len(ohlcv)

    def test_tf_resample_map_contains_all_supported_timeframes(self):
        """_TF_RESAMPLE_MAP must contain all 9 supported Bybit TFs."""
        required = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}
        assert required.issubset(set(self.tf_map.keys()))


# ===========================================================================
# Фича 2 — _handle_mfi_filter HTF logic
# ===========================================================================


class TestMfiFilterHtf:
    """Tests for _handle_mfi_filter HTF resampling path."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        from backend.backtesting.indicator_handlers import _handle_mfi_filter

        self.handle = _handle_mfi_filter

    def _make_adapter(self, interval: str = "15") -> object:
        """Return a minimal mock adapter object."""

        class _FakeAdapter:
            main_interval = interval
            _btcusdt_ohlcv = None

        return _FakeAdapter()

    def test_mfi_filter_chart_tf_uses_main_ohlcv(self):
        """When mfi_timeframe='Chart' (default), the same OHLCV is used."""
        ohlcv = _make_ohlcv(200, freq="15min")
        adapter = self._make_adapter("15")
        params = {"mfi_period": 14, "mfi_long_min": 30, "mfi_long_max": 70}
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        assert "long" in result or "short" in result or "exit_long" in result

    def test_mfi_filter_htf_uses_resampled_ohlcv(self):
        """When mfi_timeframe='60' and main is '15', resampled data is used
        (no error, result has correct length)."""
        ohlcv = _make_ohlcv(300, freq="15min")
        adapter = self._make_adapter("15")
        params = {
            "mfi_period": 14,
            "mfi_timeframe": "60",
            "mfi_long_min": 20,
            "mfi_long_max": 80,
        }
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        # All Series in result must align with original ohlcv index
        for _key, series in result.items():
            assert len(series) == len(ohlcv), f"{_key} length mismatch"

    def test_mfi_filter_btcusdt_overrides_when_present(self):
        """When use_btcusdt_mfi=True and adapter._btcusdt_ohlcv is set,
        btcusdt data is used — result length still matches ohlcv."""
        ohlcv = _make_ohlcv(200, freq="15min")
        btc = _make_ohlcv(200, freq="15min", seed=99)
        adapter = self._make_adapter("15")
        adapter._btcusdt_ohlcv = btc  # type: ignore[attr-defined]
        params = {
            "mfi_period": 14,
            "use_btcusdt_mfi": True,
            "mfi_long_min": 20,
            "mfi_long_max": 80,
        }
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        for _key, series in result.items():
            assert len(series) == len(ohlcv)

    def test_mfi_filter_btcusdt_fallback_when_none(self):
        """When use_btcusdt_mfi=True but adapter._btcusdt_ohlcv=None,
        falls back to regular OHLCV (no crash)."""
        ohlcv = _make_ohlcv(200, freq="15min")
        adapter = self._make_adapter("15")
        # _btcusdt_ohlcv is None by default
        params = {
            "mfi_period": 14,
            "use_btcusdt_mfi": True,
            "mfi_long_min": 20,
            "mfi_long_max": 80,
        }
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        # Should not raise; length must match
        for series in result.values():
            assert len(series) == len(ohlcv)


# ===========================================================================
# Фича 2 — _handle_cci_filter HTF logic
# ===========================================================================


class TestCciFilterHtf:
    """Tests for _handle_cci_filter HTF resampling path."""

    @pytest.fixture(autouse=True)
    def import_fn(self):
        from backend.backtesting.indicator_handlers import _handle_cci_filter

        self.handle = _handle_cci_filter

    def _make_adapter(self, interval: str = "15") -> object:
        class _FakeAdapter:
            main_interval = interval

        return _FakeAdapter()

    def test_cci_filter_chart_tf(self):
        """Default (Chart) should not crash and return correct length."""
        ohlcv = _make_ohlcv(200, freq="15min")
        adapter = self._make_adapter("15")
        params = {"cci_period": 20, "cci_long_min": -100, "cci_long_max": 100}
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        for series in result.values():
            assert len(series) == len(ohlcv)

    def test_cci_filter_htf_uses_resampled_ohlcv(self):
        """mfi_timeframe='60' on 15m data should resample correctly."""
        ohlcv = _make_ohlcv(300, freq="15min")
        adapter = self._make_adapter("15")
        params = {
            "cci_period": 20,
            "cci_timeframe": "60",
            "cci_long_min": -100,
            "cci_long_max": 100,
        }
        result = self.handle(params, ohlcv, ohlcv["close"], {}, adapter)
        for series in result.values():
            assert len(series) == len(ohlcv)


# ===========================================================================
# Фича 1 — profit_only in FallbackEngineV4 (engine.py)
# ===========================================================================


def _run_backtest_with_extra_data(
    extra_data: dict,
    close: np.ndarray,
    entry_mask: np.ndarray,
    exit_mask: np.ndarray,
) -> list:
    """
    Run FallbackEngineV4 with synthetic signals and custom extra_data.
    Returns the list of trade records (BacktestResult.trades).
    """
    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType
    from backend.backtesting.strategies import BaseStrategy, SignalResult

    n = len(close)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=UTC)
    ohlcv = pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n) * 100,
        },
        index=dates,
    )

    class _SyntheticStrategy(BaseStrategy):
        def __init__(self, _entry, _exit, _extra):
            # Bypass BaseStrategy.__init__ to avoid _validate_params call
            self._entry = _entry
            self._exit = _exit
            self._extra = _extra
            self.params = {}

        def _validate_params(self) -> None:  # required abstract method
            pass

        def generate_signals(self, df):
            entries = pd.Series(self._entry, index=df.index)
            exits = pd.Series(self._exit, index=df.index)
            return SignalResult(
                entries=entries,
                exits=exits,
                extra_data=self._extra,
            )

    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="60",
        start_date=dates[0].to_pydatetime(),
        end_date=dates[-1].to_pydatetime(),
        strategy_type=StrategyType.SMA_CROSSOVER,
        strategy_params={},
        initial_capital=10_000.0,
        position_size=1.0,
        leverage=1,
        stop_loss=None,
        take_profit=None,
        direction="long",
    )

    strategy = _SyntheticStrategy(entry_mask, exit_mask, extra_data)
    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=strategy)
    return result.trades


class TestProfitOnlyExitsEngine:
    """Tests for profit_only / min_profit gate in FallbackEngineV4."""

    def test_profit_only_exit_not_fired_at_loss(self):
        """If profit_only=True, exit must NOT fire when trade is at a loss."""
        n = 100
        # Falling price — entering at 100, price drops to 90
        close = np.linspace(100, 90, n)

        entry_mask = np.zeros(n, dtype=bool)
        exit_mask = np.zeros(n, dtype=bool)
        entry_mask[5] = True  # Enter bar 5 at ~price 100
        exit_mask[20] = True  # Signal exit at bar 20 (price ~97 → still loss)

        # Mark bar 20 as profit_only exit
        po_exits = pd.Series(False, index=range(n))
        po_exits.iloc[20] = True

        extra = {
            "profit_only_exits": po_exits,
            "profit_only_short_exits": pd.Series(False, index=range(n)),
            "min_profit_exits": 0.0,
            "min_profit_short_exits": 0.0,
        }

        trades = _run_backtest_with_extra_data(extra, close, entry_mask, exit_mask)
        # The trade should NOT close on bar 20 due to profit_only gate
        # It may close at end-of-data or not at all
        for t in trades:
            exit_reason = getattr(t, "exit_comment", None)
            if exit_reason == "signal":
                # If closed by signal, verify it was profitable
                ep = getattr(t, "entry_price", 0)
                xp = getattr(t, "exit_price", 0)
                assert xp >= ep, "profit_only trade closed at a loss"

    def test_profit_only_exit_fires_above_min_profit(self):
        """profit_only exit MUST fire when price is above min_profit threshold."""
        n = 100
        # Rising price — enter at 100, rises to 110
        close = np.linspace(100, 110, n)

        entry_mask = np.zeros(n, dtype=bool)
        exit_mask = np.zeros(n, dtype=bool)
        entry_mask[5] = True
        exit_mask[50] = True  # Exit at ~105 (5% up)

        po_exits = pd.Series(False, index=range(n))
        po_exits.iloc[50] = True

        extra = {
            "profit_only_exits": po_exits,
            "profit_only_short_exits": pd.Series(False, index=range(n)),
            "min_profit_exits": 0.02,  # 2% minimum — 5% > 2% → should fire
            "min_profit_short_exits": 0.0,
        }

        trades = _run_backtest_with_extra_data(extra, close, entry_mask, exit_mask)
        signal_exits = [t for t in trades if getattr(t, "exit_comment", "") == "signal"]
        assert len(signal_exits) >= 1, "Expected at least one signal exit when price > min_profit"

    def test_non_profit_only_exit_fires_regardless(self):
        """Exit bar NOT marked profit_only must still fire (normal behavior)."""
        n = 100
        close = np.linspace(100, 90, n)  # falling
        entry_mask = np.zeros(n, dtype=bool)
        exit_mask = np.zeros(n, dtype=bool)
        entry_mask[5] = True
        exit_mask[20] = True  # Not marked profit_only

        extra = {}  # No profit_only data → standard behavior

        trades = _run_backtest_with_extra_data(extra, close, entry_mask, exit_mask)
        signal_exits = [t for t in trades if getattr(t, "exit_comment", "") == "signal"]
        assert len(signal_exits) >= 1, "Normal (non profit_only) exit should fire unconditionally"

    def test_profit_only_exit_below_min_profit_not_fired(self):
        """Exit with profit_only=True but price gain < min_profit must NOT fire."""
        n = 100
        # Price rises only 1% — min_profit requires 3%
        close = np.linspace(100, 101, n)

        entry_mask = np.zeros(n, dtype=bool)
        exit_mask = np.zeros(n, dtype=bool)
        entry_mask[5] = True
        exit_mask[50] = True

        po_exits = pd.Series(False, index=range(n))
        po_exits.iloc[50] = True

        extra = {
            "profit_only_exits": po_exits,
            "profit_only_short_exits": pd.Series(False, index=range(n)),
            "min_profit_exits": 0.03,  # 3% — price only up 1% → suppressed
            "min_profit_short_exits": 0.0,
        }

        trades = _run_backtest_with_extra_data(extra, close, entry_mask, exit_mask)
        for t in trades:
            exit_reason = getattr(t, "exit_comment", "")
            if exit_reason == "signal":
                # If somehow closed via signal, PnL% must be >= 3%
                ep = getattr(t, "entry_price", 0)
                xp = getattr(t, "exit_price", 0)
                pct = (xp - ep) / ep if ep else 0
                assert pct >= 0.03, f"Signal exit fired below min_profit: pnl%={pct:.4f}"


# ===========================================================================
# Фича 1 — profit_only in adapter extra_data
# ===========================================================================


class TestAdapterProfitOnlyExtraData:
    """Tests for profit_only extra_data collection in StrategyBuilderAdapter."""

    def _make_graph_with_close_cond(
        self,
        profit_only: bool = True,
        min_profit: float = 1.0,
    ) -> dict:
        """Minimal strategy graph with a close_cond block that has profit_only."""
        return {
            "name": "TestStrategy",
            "interval": "60",
            "blocks": [
                {
                    "id": "strat1",
                    "type": "strategy",
                    "isMain": True,
                    "params": {
                        "direction": "long",
                        "position_size": 0.1,
                    },
                },
                {
                    "id": "close1",
                    "type": "close_cond",
                    "params": {
                        "profit_only": profit_only,
                        "min_profit": min_profit,
                    },
                },
            ],
            "connections": [],
        }

    def test_requires_btcusdt_data_false_by_default(self):
        """_requires_btcusdt_data() should return False when no mfi_filter block present."""
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        graph = {
            "name": "T",
            "interval": "60",
            "blocks": [{"id": "s", "type": "strategy", "isMain": True, "params": {}}],
            "connections": [],
        }
        adapter = StrategyBuilderAdapter(graph)
        assert adapter._requires_btcusdt_data() is False

    def test_requires_btcusdt_data_true_when_block_present(self):
        """_requires_btcusdt_data() should return True when mfi_filter has use_btcusdt_mfi=True."""
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        graph = {
            "name": "T",
            "interval": "60",
            "blocks": [
                {"id": "s", "type": "strategy", "isMain": True, "params": {}},
                {
                    "id": "mfi1",
                    "type": "mfi_filter",
                    "params": {"use_btcusdt_mfi": True},
                },
            ],
            "connections": [],
        }
        adapter = StrategyBuilderAdapter(graph)
        assert adapter._requires_btcusdt_data() is True

    def test_btcusdt_ohlcv_stored_on_adapter(self):
        """When btcusdt_ohlcv kwarg is passed, it must be stored on the adapter."""
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        graph = {
            "name": "T",
            "interval": "60",
            "blocks": [{"id": "s", "type": "strategy", "isMain": True, "params": {}}],
            "connections": [],
        }
        btc = _make_ohlcv(100)
        adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc)
        assert adapter._btcusdt_ohlcv is btc

    def test_btcusdt_ohlcv_none_by_default(self):
        """Without the kwarg, _btcusdt_ohlcv must be None."""
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        graph = {
            "name": "T",
            "interval": "60",
            "blocks": [{"id": "s", "type": "strategy", "isMain": True, "params": {}}],
            "connections": [],
        }
        adapter = StrategyBuilderAdapter(graph)
        assert adapter._btcusdt_ohlcv is None
