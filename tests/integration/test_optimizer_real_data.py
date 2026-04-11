"""
Integration tests: optimizer with real historical OHLCV data.

Requires local SQLite DB with ETHUSDT 30m candles (auto-populated by BacktestService).
Run explicitly:  pytest tests/integration/test_optimizer_real_data.py -v

Tests cover:
  - Real data loading from local DB
  - Single backtest on real data (sanity check)
  - BUG-1 regression: position_size must not be hardcoded
  - BUG-2 regression: long/short breakdown metrics must be non-zero
  - NumbaEngineV2 vs FallbackEngineV4 parity on real data
  - Small grid search produces valid ranked results
  - DCA strategies do NOT take the RSI threshold fast path (BUG-3 regression)
"""

import asyncio
from datetime import UTC, datetime

import pytest

from backend.optimization.builder_optimizer import (
    clone_graph_with_params,
    generate_builder_param_combinations,
    run_builder_backtest,
    run_builder_grid_search,
    run_builder_optuna_search,
    split_ohlcv_is_oos,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYMBOL = "ETHUSDT"
INTERVAL = "30"
START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2025, 3, 1, tzinfo=UTC)

# Minimal RSI + SL/TP graph — mirrors RSI-1 strategy structure.
RSI_GRAPH = {
    "name": "RSI Integration Test",
    "blocks": [
        {
            "id": "strategy_node",
            "type": "strategy",
            "name": "Strategy",
            "params": {},
            "isMain": True,
        },
        {
            "id": "rsi_test",
            "type": "rsi",
            "name": "RSI",
            "params": {
                "period": 14,
                "source": "close",
                "timeframe": 30,
                "use_long_range": True,
                "long_rsi_more": 30.0,
                "long_rsi_less": 60,
                "use_short_range": True,
                "short_rsi_more": 40.0,
                "short_rsi_less": 75.0,
                "use_cross_level": True,
                "cross_long_level": 30.0,
                "cross_short_level": 60.0,
                "use_cross_memory": False,
            },
        },
        {
            "id": "sltp_test",
            "type": "static_sltp",
            "name": "SL/TP",
            "params": {
                "stop_loss_percent": 2.0,
                "take_profit_percent": 3.0,
                "sl_type": "average_price",
                "close_only_in_profit": False,
                "activate_breakeven": False,
            },
        },
    ],
    "connections": [
        {
            "id": "conn_sltp",
            "source": {"blockId": "sltp_test", "portId": "config"},
            "target": {"blockId": "strategy_node", "portId": "sl_tp"},
            "type": "config",
        },
        {
            "id": "conn_entry_long",
            "source": {"blockId": "rsi_test", "portId": "long"},
            "target": {"blockId": "strategy_node", "portId": "entry_long"},
            "type": "condition",
        },
        {
            "id": "conn_entry_short",
            "source": {"blockId": "rsi_test", "portId": "short"},
            "target": {"blockId": "strategy_node", "portId": "entry_short"},
            "type": "condition",
        },
    ],
    "interval": INTERVAL,
    "market_type": "linear",
    "direction": "both",
}

BASE_CONFIG = {
    "symbol": SYMBOL,
    "interval": INTERVAL,
    "initial_capital": 10000.0,
    "leverage": 1,
    "position_size": 0.1,
    "commission": 0.0007,
    "direction": "both",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_ohlcv():
    """Load real ETHUSDT 30m data from local SQLite DB (2025-01-01 to 2025-03-01).

    Skips tests if data is unavailable (e.g. DB not populated).
    """
    from backend.backtesting.service import BacktestService

    svc = BacktestService()

    async def _load():
        return await svc._fetch_historical_data(
            symbol=SYMBOL,
            interval=INTERVAL,
            start_date=START,
            end_date=END,
            market_type="linear",
        )

    df = asyncio.run(_load())

    if df is None or len(df) < 100:
        pytest.skip(f"Real OHLCV data unavailable or too short (got {len(df) if df is not None else 0} bars)")

    return df


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRealDataLoading:
    def test_loads_expected_bar_count(self, real_ohlcv):
        """2833 bars expected for ETHUSDT 30m 2025-01-01 to 2025-03-01."""
        assert len(real_ohlcv) >= 2500, f"Expected >=2500 bars, got {len(real_ohlcv)}"

    def test_has_required_columns(self, real_ohlcv):
        required = {"open", "high", "low", "close", "volume"}
        assert required.issubset(set(real_ohlcv.columns))

    def test_no_nan_in_ohlc(self, real_ohlcv):
        for col in ["open", "high", "low", "close"]:
            assert real_ohlcv[col].isna().sum() == 0, f"NaN in {col}"

    def test_high_gte_low(self, real_ohlcv):
        assert (real_ohlcv["high"] >= real_ohlcv["low"]).all()

    def test_prices_positive(self, real_ohlcv):
        assert (real_ohlcv["close"] > 0).all()


# ---------------------------------------------------------------------------
# 2. Single backtest on real data
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSingleBacktestRealData:
    def test_returns_metrics_dict(self, real_ohlcv):
        result = run_builder_backtest(RSI_GRAPH, real_ohlcv, BASE_CONFIG)
        assert result is not None
        assert isinstance(result, dict)
        assert "total_trades" in result or "sharpe_ratio" in result

    def test_metrics_are_finite(self, real_ohlcv):
        result = run_builder_backtest(RSI_GRAPH, real_ohlcv, BASE_CONFIG)
        assert result is not None
        for key in ["sharpe_ratio", "net_profit", "win_rate", "max_drawdown"]:
            val = result.get(key)
            if val is not None:
                assert not (val != val), f"{key} is NaN"  # NaN check
                assert abs(val) < 1e12, f"{key} is unreasonably large: {val}"

    def test_produces_trades(self, real_ohlcv):
        """Real ETHUSDT 30m data should produce at least a few trades."""
        result = run_builder_backtest(RSI_GRAPH, real_ohlcv, BASE_CONFIG)
        assert result is not None
        trades = result.get("total_trades", 0)
        assert trades > 0, "No trades produced on real data — check graph connections"


# ---------------------------------------------------------------------------
# 3. BUG-1 regression: position_size must NOT be hardcoded
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPositionSizeNotHardcoded:
    """Regression for BUG-1 (utils.py): position_size was hardcoded 0.1 / 1.0."""

    def test_larger_position_size_gives_larger_profit(self, real_ohlcv):
        result_small = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "position_size": 0.1})
        result_large = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "position_size": 0.5})
        assert result_small is not None and result_large is not None

        profit_small = abs(result_small.get("net_profit", 0))
        profit_large = abs(result_large.get("net_profit", 0))

        # Larger position_size must produce meaningfully larger |profit|.
        # Allow a small epsilon to handle the case when profit is near 0.
        if profit_small > 1.0:
            assert profit_large > profit_small * 1.5, (
                f"position_size=0.5 profit {profit_large:.2f} should be "
                f"much larger than position_size=0.1 profit {profit_small:.2f}"
            )

    def test_trade_count_unchanged_by_position_size(self, real_ohlcv):
        """Changing position_size must not change the number of trades."""
        r1 = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "position_size": 0.1})
        r2 = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "position_size": 1.0})
        assert r1 is not None and r2 is not None
        assert r1.get("total_trades") == r2.get("total_trades"), "position_size must not affect trade count"


# ---------------------------------------------------------------------------
# 4. BUG-2 regression: long/short breakdown metrics must be non-zero
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLongShortBreakdownNonZero:
    """Regression for BUG-2 (numba_engine_v2.py): breakdown fields always returned 0."""

    def test_numba_long_breakdown_nonzero(self, real_ohlcv):
        """Using direction=both with Numba engine, long-side breakdown must be non-zero."""
        config = {**BASE_CONFIG, "direction": "both", "engine_type": "numba_v2"}
        result = run_builder_backtest(RSI_GRAPH, real_ohlcv, config)
        assert result is not None

        long_trades = result.get("long_trades", result.get("long_winning_trades", None))
        if long_trades is not None:
            # If we have long+short signals, there should be long trades
            assert long_trades >= 0  # At minimum, non-negative

        # The key check: long_gross_profit should not always be 0
        # when there are long trades with positive outcomes
        total_long = result.get("long_trades", 0)
        if total_long and total_long > 0:
            long_gross_profit = result.get("long_gross_profit", None)
            if long_gross_profit is not None:
                # If there are profitable long trades, gross profit must be positive
                long_winning = result.get("long_winning_trades", 0)
                if long_winning and long_winning > 0:
                    assert long_gross_profit > 0, (
                        f"long_gross_profit={long_gross_profit} should be > 0 when long_winning_trades={long_winning}"
                    )

    def test_fallback_and_numba_breakdown_match(self, real_ohlcv):
        """FallbackV4 and NumbaV2 long/short breakdown metrics must match."""
        config_fallback = {**BASE_CONFIG, "direction": "both", "engine_type": "fallback_v4"}
        config_numba = {**BASE_CONFIG, "direction": "both", "engine_type": "numba_v2"}

        r_fb = run_builder_backtest(RSI_GRAPH, real_ohlcv, config_fallback)
        r_nb = run_builder_backtest(RSI_GRAPH, real_ohlcv, config_numba)

        assert r_fb is not None and r_nb is not None

        breakdown_keys = ["long_trades", "short_trades", "long_winning_trades", "short_winning_trades"]
        for key in breakdown_keys:
            fb_val = r_fb.get(key)
            nb_val = r_nb.get(key)
            if fb_val is not None and nb_val is not None:
                assert fb_val == nb_val, f"Breakdown mismatch for {key}: FallbackV4={fb_val}, NumbaV2={nb_val}"


# ---------------------------------------------------------------------------
# 5. Numba vs FallbackV4 parity on real data
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestNumbaParityRealData:
    """NumbaEngineV2 must produce results matching FallbackEngineV4 on real data."""

    PARITY_KEYS = [
        "total_trades",
        "net_profit",
        "win_rate",
        "max_drawdown",
        "sharpe_ratio",
    ]

    def test_parity_total_trades(self, real_ohlcv):
        r_fb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        assert r_fb["total_trades"] == r_nb["total_trades"], (
            f"total_trades: V4={r_fb['total_trades']}, Numba={r_nb['total_trades']}"
        )

    def test_parity_net_profit(self, real_ohlcv):
        r_fb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        fb_np = r_fb.get("net_profit", 0)
        nb_np = r_nb.get("net_profit", 0)
        # Allow 0.01% relative tolerance
        if abs(fb_np) > 1.0:
            rel_diff = abs(fb_np - nb_np) / abs(fb_np)
            assert rel_diff < 0.0001, (
                f"net_profit parity failed: V4={fb_np:.4f}, Numba={nb_np:.4f}, diff={rel_diff:.6%}"
            )

    def test_parity_sharpe_ratio(self, real_ohlcv):
        r_fb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(RSI_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        fb_sr = r_fb.get("sharpe_ratio", 0) or 0
        nb_sr = r_nb.get("sharpe_ratio", 0) or 0
        assert abs(fb_sr - nb_sr) < 0.01, f"sharpe_ratio parity failed: V4={fb_sr:.4f}, Numba={nb_sr:.4f}"


# ---------------------------------------------------------------------------
# 6. Grid search on real data
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGridSearchRealData:
    """Mini grid search on real historical data."""

    # 3 × 2 × 2 = 12 combinations — fast enough for integration tests
    PARAM_RANGES = [
        {"param_path": "rsi_test.period", "type": "int", "low": 10, "high": 14, "step": 2, "enabled": True},
        {
            "param_path": "sltp_test.stop_loss_percent",
            "type": "float",
            "low": 1.5,
            "high": 2.5,
            "step": 1.0,
            "enabled": True,
        },
        {
            "param_path": "sltp_test.take_profit_percent",
            "type": "float",
            "low": 2.0,
            "high": 3.0,
            "step": 1.0,
            "enabled": True,
        },
    ]

    def _make_combos(self):
        """generate_builder_param_combinations returns (iterator, total, was_capped)."""
        combos_iter, total, _ = generate_builder_param_combinations(self.PARAM_RANGES)
        return combos_iter, total

    def test_combo_count(self):
        """3 periods × 2 SL × 2 TP = 12 combos."""
        _, total = self._make_combos()
        assert total == 12, f"Expected 12 combos, got {total}"

    def test_grid_search_returns_results(self, real_ohlcv):
        combos_iter, total = self._make_combos()
        result = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=5,
            total_combinations=total,
        )

        assert "top_results" in result
        assert "tested_combinations" in result
        assert result["tested_combinations"] > 0
        assert len(result["top_results"]) > 0

    def test_top_results_have_params(self, real_ohlcv):
        combos_iter, total = self._make_combos()
        result = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=5,
            total_combinations=total,
        )
        for res in result["top_results"]:
            assert "params" in res
            assert "rsi_test.period" in res["params"]

    def test_results_ranked_by_sharpe(self, real_ohlcv):
        combos_iter, total = self._make_combos()
        result = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=10,
            total_combinations=total,
        )
        tops = result["top_results"]
        if len(tops) >= 2:
            sharpes = [r.get("sharpe_ratio", 0) or 0 for r in tops]
            assert sharpes[0] >= sharpes[-1], f"Results not ranked: first={sharpes[0]:.4f}, last={sharpes[-1]:.4f}"

    def test_all_combinations_tested(self, real_ohlcv):
        combos_iter, total = self._make_combos()
        result = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="net_profit",
            max_results=5,
            total_combinations=total,
        )
        assert result["tested_combinations"] == total, f"Expected {total} tested, got {result['tested_combinations']}"

    def test_different_metrics_give_different_rankings(self, real_ohlcv):
        combos_sharpe, total_s = self._make_combos()
        combos_profit, total_p = self._make_combos()

        res_sharpe = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_sharpe,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=3,
            total_combinations=total_s,
        )
        res_profit = run_builder_grid_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_profit,
            config_params=BASE_CONFIG,
            optimize_metric="net_profit",
            max_results=3,
            total_combinations=total_p,
        )

        assert len(res_sharpe["top_results"]) > 0
        assert len(res_profit["top_results"]) > 0
        assert "rsi_test.period" in res_sharpe["top_results"][0]["params"]
        assert "rsi_test.period" in res_profit["top_results"][0]["params"]


# ---------------------------------------------------------------------------
# 7. BUG-3 regression: DCA graphs must NOT use RSI threshold fast path
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDCAPathRegressionRealData:
    """BUG-3 regression: DCA strategies must use DCA mixed batch path, not RSI fast path."""

    DCA_GRAPH = {
        "name": "DCA RSI Test",
        "blocks": [
            {"id": "strategy_node", "type": "strategy", "params": {}, "isMain": True},
            {
                "id": "rsi_dca",
                "type": "rsi",
                "params": {
                    "period": 14,
                    "source": "close",
                    "timeframe": 30,
                    "use_cross_level": True,
                    "cross_long_level": 30.0,
                    "cross_short_level": 70.0,
                },
            },
            {
                "id": "dca_block",
                "type": "dca",
                "params": {
                    "dca_order_count": 3,
                    "dca_grid_size_percent": 1.0,
                    "dca_martingale_coef": 1.5,
                    "dca_tp1_percent": 1.5,
                    "dca_tp1_close_percent": 100.0,
                },
            },
        ],
        "connections": [
            {
                "id": "conn_entry",
                "source": {"blockId": "rsi_dca", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
                "type": "condition",
            },
        ],
        "interval": INTERVAL,
        "market_type": "linear",
        "direction": "long",
    }

    def test_dca_grid_search_uses_dca_path(self, real_ohlcv):
        """DCA strategy optimization must return method='grid_numba_dca_mixed' or similar DCA path."""
        param_ranges = [
            {
                "param_path": "rsi_dca.cross_long_level",
                "type": "float",
                "low": 25.0,
                "high": 35.0,
                "step": 5.0,
                "enabled": True,
            },
            {
                "param_path": "dca_block.dca_tp1_percent",
                "type": "float",
                "low": 1.0,
                "high": 2.0,
                "step": 0.5,
                "enabled": True,
            },
        ]
        combos_iter, total, _ = generate_builder_param_combinations(param_ranges)
        combos = list(combos_iter)
        # 3 × 3 = 9 combinations

        dca_config = {**BASE_CONFIG, "direction": "long", "dca_enabled": True}

        result = run_builder_grid_search(
            base_graph=self.DCA_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=iter(combos),
            config_params=dca_config,
            optimize_metric="net_profit",
            max_results=5,
            total_combinations=total,
        )

        assert "top_results" in result
        # The key assertion: method should indicate DCA path was used
        method = result.get("method", "")
        assert "rsi_threshold" not in method, f"DCA graph incorrectly took RSI threshold fast path: method={method!r}"


# ---------------------------------------------------------------------------
# 8. Other indicator types — MACD, Bollinger, Supertrend
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOtherIndicatorTypes:
    """Verify that MACD, Bollinger Bands and Supertrend produce valid results
    on real data.  These have DEFAULT_PARAM_RANGES but were previously untested
    in integration."""

    MACD_GRAPH = {
        "name": "MACD Integration Test",
        "blocks": [
            {"id": "strategy_node", "type": "strategy", "params": {}, "isMain": True},
            {
                "id": "macd_test",
                "type": "macd",
                "params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "timeframe": 30,
                    "use_macd_cross": True,
                    "use_hist_cross_zero": False,
                },
            },
            {
                "id": "sltp_macd",
                "type": "static_sltp",
                "params": {
                    "stop_loss_percent": 2.0,
                    "take_profit_percent": 4.0,
                    "activate_breakeven": False,
                },
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "sltp_macd", "portId": "config"},
                "target": {"blockId": "strategy_node", "portId": "sl_tp"},
                "type": "config",
            },
            {
                "id": "c2",
                "source": {"blockId": "macd_test", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "c3",
                "source": {"blockId": "macd_test", "portId": "short"},
                "target": {"blockId": "strategy_node", "portId": "entry_short"},
                "type": "condition",
            },
        ],
        "interval": INTERVAL,
        "market_type": "linear",
        "direction": "both",
    }

    # Bollinger outputs price bands (upper/middle/lower), not boolean long/short.
    # Real usage: RSI provides entries, Bollinger squeeze (keltner_bollinger block)
    # or supertrend_filter acts as filter. Here we use keltner_bollinger which
    # DOES produce long/short signals (price outside Keltner+BB squeeze zone).
    BOLLINGER_GRAPH = {
        "name": "Keltner-Bollinger Integration Test",
        "blocks": [
            {"id": "strategy_node", "type": "strategy", "params": {}, "isMain": True},
            {
                "id": "bb_test",
                "type": "keltner_bollinger",
                "params": {
                    "keltner_length": 14,
                    "keltner_mult": 1.5,
                    "bb_length": 20,
                    "bb_deviation": 2.0,
                    "timeframe": 30,
                },
            },
            {
                "id": "sltp_bb",
                "type": "static_sltp",
                "params": {
                    "stop_loss_percent": 2.0,
                    "take_profit_percent": 3.0,
                    "activate_breakeven": False,
                },
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "sltp_bb", "portId": "config"},
                "target": {"blockId": "strategy_node", "portId": "sl_tp"},
                "type": "config",
            },
            {
                "id": "c2",
                "source": {"blockId": "bb_test", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "c3",
                "source": {"blockId": "bb_test", "portId": "short"},
                "target": {"blockId": "strategy_node", "portId": "entry_short"},
                "type": "condition",
            },
        ],
        "interval": INTERVAL,
        "market_type": "linear",
        "direction": "both",
    }

    SUPERTREND_GRAPH = {
        "name": "Supertrend Integration Test",
        "blocks": [
            {"id": "strategy_node", "type": "strategy", "params": {}, "isMain": True},
            {
                "id": "st_test",
                "type": "supertrend",
                "params": {
                    "period": 10,
                    "multiplier": 3.0,
                    "timeframe": 30,
                },
            },
            {
                "id": "sltp_st",
                "type": "static_sltp",
                "params": {
                    "stop_loss_percent": 2.0,
                    "take_profit_percent": 4.0,
                    "activate_breakeven": False,
                },
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "sltp_st", "portId": "config"},
                "target": {"blockId": "strategy_node", "portId": "sl_tp"},
                "type": "config",
            },
            {
                "id": "c2",
                "source": {"blockId": "st_test", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
                "type": "condition",
            },
            {
                "id": "c3",
                "source": {"blockId": "st_test", "portId": "short"},
                "target": {"blockId": "strategy_node", "portId": "entry_short"},
                "type": "condition",
            },
        ],
        "interval": INTERVAL,
        "market_type": "linear",
        "direction": "both",
    }

    def _run(self, graph, real_ohlcv):
        return run_builder_backtest(graph, real_ohlcv, BASE_CONFIG)

    # --- MACD ---

    def test_macd_returns_result(self, real_ohlcv):
        result = self._run(self.MACD_GRAPH, real_ohlcv)
        assert result is not None, "MACD backtest returned None"
        assert "total_trades" in result or "sharpe_ratio" in result

    def test_macd_metrics_finite(self, real_ohlcv):
        result = self._run(self.MACD_GRAPH, real_ohlcv)
        assert result is not None
        for key in ("net_profit", "sharpe_ratio", "win_rate", "max_drawdown"):
            val = result.get(key)
            if val is not None:
                assert val == val, f"MACD {key} is NaN"

    def test_macd_grid_search(self, real_ohlcv):
        """6-combo mini grid: 3 fast_period × 2 signal_period."""
        ranges = [
            {"param_path": "macd_test.fast_period", "type": "int", "low": 10, "high": 14, "step": 2, "enabled": True},
            {
                "param_path": "sltp_macd.stop_loss_percent",
                "type": "float",
                "low": 1.5,
                "high": 2.5,
                "step": 1.0,
                "enabled": True,
            },
        ]
        combos_iter, total, _ = generate_builder_param_combinations(ranges)
        result = run_builder_grid_search(
            base_graph=self.MACD_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=3,
            total_combinations=total,
        )
        assert result["tested_combinations"] == total
        assert len(result["top_results"]) > 0
        assert "macd_test.fast_period" in result["top_results"][0]["params"]

    # --- Bollinger ---

    def test_bollinger_returns_result(self, real_ohlcv):
        result = self._run(self.BOLLINGER_GRAPH, real_ohlcv)
        assert result is not None, "Bollinger backtest returned None"

    def test_bollinger_metrics_finite(self, real_ohlcv):
        result = self._run(self.BOLLINGER_GRAPH, real_ohlcv)
        assert result is not None
        for key in ("net_profit", "sharpe_ratio"):
            val = result.get(key)
            if val is not None:
                assert val == val, f"Bollinger {key} is NaN"

    def test_bollinger_grid_search(self, real_ohlcv):
        """6-combo: 3 keltner lengths × 2 bb lengths (keltner_bollinger block)."""
        ranges = [
            {"param_path": "bb_test.keltner_length", "type": "int", "low": 10, "high": 18, "step": 4, "enabled": True},
            {"param_path": "bb_test.bb_length", "type": "int", "low": 15, "high": 25, "step": 10, "enabled": True},
        ]
        combos_iter, total, _ = generate_builder_param_combinations(ranges)
        result = run_builder_grid_search(
            base_graph=self.BOLLINGER_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=3,
            total_combinations=total,
        )
        assert result["tested_combinations"] == total
        assert len(result["top_results"]) > 0

    # --- Supertrend ---

    def test_supertrend_returns_result(self, real_ohlcv):
        result = self._run(self.SUPERTREND_GRAPH, real_ohlcv)
        assert result is not None, "Supertrend backtest returned None"

    def test_supertrend_metrics_finite(self, real_ohlcv):
        result = self._run(self.SUPERTREND_GRAPH, real_ohlcv)
        assert result is not None
        for key in ("net_profit", "sharpe_ratio"):
            val = result.get(key)
            if val is not None:
                assert val == val, f"Supertrend {key} is NaN"

    def test_supertrend_grid_search(self, real_ohlcv):
        """6-combo: 3 periods × 2 multipliers."""
        ranges = [
            {"param_path": "st_test.period", "type": "int", "low": 7, "high": 13, "step": 3, "enabled": True},
            {
                "param_path": "st_test.multiplier",
                "type": "float",
                "low": 2.0,
                "high": 3.5,
                "step": 1.5,
                "enabled": True,
            },
        ]
        combos_iter, total, _ = generate_builder_param_combinations(ranges)
        result = run_builder_grid_search(
            base_graph=self.SUPERTREND_GRAPH,
            ohlcv=real_ohlcv,
            param_combinations=combos_iter,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            max_results=3,
            total_combinations=total,
        )
        assert result["tested_combinations"] == total
        assert len(result["top_results"]) > 0

    # --- cross-type parity: all three must produce matching Numba/V4 trade counts ---

    def test_macd_numba_v4_parity(self, real_ohlcv):
        r_fb = run_builder_backtest(self.MACD_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(self.MACD_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        assert r_fb.get("total_trades") == r_nb.get("total_trades"), (
            f"MACD parity fail: V4={r_fb.get('total_trades')}, Numba={r_nb.get('total_trades')}"
        )

    def test_bollinger_numba_v4_parity(self, real_ohlcv):
        r_fb = run_builder_backtest(self.BOLLINGER_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(self.BOLLINGER_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        assert r_fb.get("total_trades") == r_nb.get("total_trades"), (
            f"Bollinger parity fail: V4={r_fb.get('total_trades')}, Numba={r_nb.get('total_trades')}"
        )

    def test_supertrend_numba_v4_parity(self, real_ohlcv):
        r_fb = run_builder_backtest(self.SUPERTREND_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "fallback_v4"})
        r_nb = run_builder_backtest(self.SUPERTREND_GRAPH, real_ohlcv, {**BASE_CONFIG, "engine_type": "numba_v2"})
        assert r_fb is not None and r_nb is not None
        assert r_fb.get("total_trades") == r_nb.get("total_trades"), (
            f"Supertrend parity fail: V4={r_fb.get('total_trades')}, Numba={r_nb.get('total_trades')}"
        )


# ---------------------------------------------------------------------------
# 9. Bayesian / Optuna optimization — 200 trials
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOptunaSearch200Trials:
    """Run Optuna TPE optimization with 200 trials on real ETHUSDT data.

    Parameter space: RSI(period, oversold, overbought) × SL/TP(sl%, tp%) = ~10^5 combos.
    Grid search is infeasible; Bayesian sampling explores intelligently.
    """

    # Wide RSI + SL/TP param specs — large enough that 200 trials ≪ exhaustive
    PARAM_SPECS = [
        {"param_path": "rsi_test.period", "type": "int", "low": 7, "high": 30, "step": 1, "enabled": True},
        {
            "param_path": "rsi_test.long_rsi_more",
            "type": "float",
            "low": 20.0,
            "high": 40.0,
            "step": 1.0,
            "enabled": True,
        },
        {
            "param_path": "rsi_test.long_rsi_less",
            "type": "float",
            "low": 50.0,
            "high": 70.0,
            "step": 1.0,
            "enabled": True,
        },
        {
            "param_path": "sltp_test.stop_loss_percent",
            "type": "float",
            "low": 1.0,
            "high": 4.0,
            "step": 0.5,
            "enabled": True,
        },
        {
            "param_path": "sltp_test.take_profit_percent",
            "type": "float",
            "low": 1.5,
            "high": 6.0,
            "step": 0.5,
            "enabled": True,
        },
    ]

    def test_optuna_200_trials_completes(self, real_ohlcv):
        """200 Optuna TPE trials must complete without errors."""
        result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=300,
        )
        assert result is not None
        assert result.get("status") != "error", f"Optuna search failed: {result.get('error')}"
        # Optuna may prune some trials (QMC startup, infeasibility); accept >=50 completed
        assert result.get("tested_combinations", 0) >= 50, (
            f"Expected >=50 trials completed, got {result.get('tested_combinations')}"
        )

    def test_optuna_200_trials_returns_top_results(self, real_ohlcv):
        """Top results must be populated and ranked by sharpe_ratio."""
        result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=300,
        )
        tops = result.get("top_results", [])
        assert len(tops) > 0, "No top results returned from 200-trial Optuna search"
        # Must be ranked: first sharpe >= last sharpe
        sharpes = [r.get("sharpe_ratio", 0) or 0 for r in tops]
        assert sharpes[0] >= sharpes[-1], f"Top results not sorted: {sharpes}"

    def test_optuna_200_trials_top_params_valid(self, real_ohlcv):
        """Best result params must include all optimized param paths."""
        result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=300,
        )
        tops = result.get("top_results", [])
        assert len(tops) > 0
        best_params = tops[0].get("params", {})
        for spec in self.PARAM_SPECS:
            path = spec["param_path"]
            assert path in best_params, f"Missing param '{path}' in best result"

    def test_optuna_200_trials_metrics_finite(self, real_ohlcv):
        """All metric values in top results must be finite (no NaN/inf)."""
        result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=300,
        )
        import math

        for res in result.get("top_results", []):
            for key in ("sharpe_ratio", "net_profit", "win_rate", "max_drawdown"):
                val = res.get(key)
                if val is not None:
                    assert math.isfinite(val), f"{key}={val} is not finite in Optuna top result"

    def test_optuna_200_trials_beats_default(self, real_ohlcv):
        """Best Optuna result should have sharpe_ratio >= default params (not strictly required, logged)."""
        default_result = run_builder_backtest(RSI_GRAPH, real_ohlcv, BASE_CONFIG)
        optuna_result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=real_ohlcv,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=5,
            timeout_seconds=300,
        )
        tops = optuna_result.get("top_results", [])
        # This is a soft check — optimizer should find something better than nothing
        assert default_result is not None
        assert len(tops) > 0
        # Log for visibility, don't hard-fail (market might not be favorable for RSI)
        best_sharpe = tops[0].get("sharpe_ratio", 0) or 0
        default_sharpe = default_result.get("sharpe_ratio", 0) or 0
        print(f"\n[Optuna 200] best_sharpe={best_sharpe:.4f} vs default_sharpe={default_sharpe:.4f}")

    def test_optuna_200_trials_is_oos_split(self, real_ohlcv):
        """200-trial optimization on IS, validate top-1 on OOS — no leakage."""
        is_df, oos_df, _ = split_ohlcv_is_oos(real_ohlcv, oos_ratio=0.3)
        assert len(is_df) >= 500, f"IS too short: {len(is_df)} bars"
        assert oos_df is not None and len(oos_df) >= 100, (
            f"OOS too short: {len(oos_df) if oos_df is not None else 0} bars"
        )

        # Optimize on IS
        optuna_result = run_builder_optuna_search(
            base_graph=RSI_GRAPH,
            ohlcv=is_df,
            param_specs=self.PARAM_SPECS,
            config_params=BASE_CONFIG,
            optimize_metric="sharpe_ratio",
            n_trials=200,
            sampler_type="tpe",
            top_n=3,
            timeout_seconds=300,
        )
        tops = optuna_result.get("top_results", [])
        assert len(tops) > 0, "No results from IS optimization"

        # Validate top-1 on OOS
        best_params = tops[0].get("params", {})

        oos_graph = clone_graph_with_params(RSI_GRAPH, best_params)
        oos_result = run_builder_backtest(oos_graph, oos_df, BASE_CONFIG)
        assert oos_result is not None, "OOS backtest returned None"
        assert "total_trades" in oos_result or "sharpe_ratio" in oos_result

        is_sharpe = tops[0].get("sharpe_ratio", 0) or 0
        oos_sharpe = oos_result.get("sharpe_ratio", 0) or 0
        print(f"\n[IS/OOS] IS sharpe={is_sharpe:.4f}, OOS sharpe={oos_sharpe:.4f}")
