"""
Regression tests for BacktestBridge.

Bugs covered:
- B1: m.net_pnl → m.net_profit (BacktestMetrics has no .net_pnl field)
- B2: m.total_return_pct → m.total_return (BacktestMetrics has no .total_return_pct field)
- B3: m.avg_trade_pnl → m.avg_trade (BacktestMetrics has no .avg_trade_pnl field)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.integration.backtest_bridge import BacktestBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    np.random.seed(0)
    n = 100
    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="15min"),
            "open": close + np.random.randn(n) * 10,
            "high": close + np.abs(np.random.randn(n) * 20),
            "low": close - np.abs(np.random.randn(n) * 20),
            "close": close,
            "volume": np.random.randint(1, 100, n).astype(float),
        }
    )


def _make_fake_output(
    net_profit: float = 1500.0,
    total_return: float = 15.0,
    avg_trade: float = 50.0,
    sharpe: float = 1.2,
    max_drawdown_pct: float = 8.5,
    win_rate: float = 0.55,
    profit_factor: float = 1.8,
    total_trades: int = 30,
    winning_trades: int = 16,
    losing_trades: int = 14,
    largest_win: float = 300.0,
    largest_loss: float = -120.0,
):
    """Build a fake BacktestOutput that mirrors the real dataclass."""
    from backend.backtesting.interfaces import BacktestMetrics, BacktestOutput

    m = BacktestMetrics(
        net_profit=net_profit,
        total_return=total_return,
        avg_trade=avg_trade,
        sharpe_ratio=sharpe,
        max_drawdown=max_drawdown_pct,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        largest_win=largest_win,
        largest_loss=largest_loss,
    )
    out = BacktestOutput(
        metrics=m,
        is_valid=True,
        execution_time=0.1,
        engine_name="FallbackEngineV4",
        bars_processed=100,
    )
    return out


# ---------------------------------------------------------------------------
# Bug B1: m.net_pnl → m.net_profit
# ---------------------------------------------------------------------------

class TestBacktestBridgeFieldAccess:
    """
    Regression suite: verify _run_backtest_sync() returns the correct values
    from BacktestMetrics (no AttributeError on field access).
    """

    def _run_sync_with_mock_engine(self, ohlcv_df, fake_output):
        """
        Patch FallbackEngineV4 and signal generator; run bridge synchronously.
        """
        bridge = BacktestBridge()

        long_entries = np.zeros(len(ohlcv_df), dtype=bool)
        long_entries[::10] = True
        long_exits = np.zeros(len(ohlcv_df), dtype=bool)
        long_exits[5::10] = True

        with (
            patch(
                "backend.agents.integration.backtest_bridge.BacktestBridge._get_engine"
            ) as mock_get_engine,
            patch(
                "backend.backtesting.signal_generators.generate_signals_for_strategy",
                return_value=(
                    long_entries,
                    long_exits,
                    np.zeros(len(ohlcv_df), dtype=bool),
                    np.zeros(len(ohlcv_df), dtype=bool),
                ),
            ),
        ):
            mock_engine = MagicMock()
            mock_engine.run.return_value = fake_output
            mock_get_engine.return_value = mock_engine

            result = bridge._run_backtest_sync(
                strategy_type="sma_crossover",
                strategy_params={"fast_period": 5, "slow_period": 20},
                df=ohlcv_df,
                symbol="BTCUSDT",
                timeframe="15",
                initial_capital=10000.0,
                leverage=1,
                direction="both",
                stop_loss=0.02,
                take_profit=0.03,
            )
        return result

    def test_no_attribute_error_on_success(self, ohlcv_df):
        """Regression B1/B2/B3: _run_backtest_sync must not raise AttributeError."""
        fake_output = _make_fake_output()
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert isinstance(result, dict)
        assert "error" not in result

    def test_net_pnl_maps_to_net_profit(self, ohlcv_df):
        """Bug B1: 'net_pnl' key in result must equal BacktestMetrics.net_profit."""
        fake_output = _make_fake_output(net_profit=2345.67)
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert result["net_pnl"] == pytest.approx(2345.67)

    def test_net_profit_alias_for_evolution(self, ohlcv_df):
        """Bug B6: 'net_profit' alias key must exist for strategy_evolution.compute_fitness()."""
        fake_output = _make_fake_output(net_profit=2345.67)
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert result["net_profit"] == pytest.approx(2345.67)
        assert result["net_profit"] == result["net_pnl"]

    def test_total_return_pct_maps_to_total_return(self, ohlcv_df):
        """Bug B2: 'total_return_pct' key must equal BacktestMetrics.total_return."""
        fake_output = _make_fake_output(total_return=23.45)
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert result["total_return_pct"] == pytest.approx(23.45)

    def test_avg_trade_pnl_maps_to_avg_trade(self, ohlcv_df):
        """Bug B3: 'avg_trade_pnl' key must equal BacktestMetrics.avg_trade."""
        fake_output = _make_fake_output(avg_trade=78.9)
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert result["avg_trade_pnl"] == pytest.approx(78.9)

    def test_all_expected_keys_present(self, ohlcv_df):
        """All keys expected by callers (FeedbackLoop, StrategyEvolution) must be present."""
        fake_output = _make_fake_output()
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        expected_keys = {
            "net_pnl",
            "net_profit",   # Bug B6: alias for strategy_evolution.compute_fitness()
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "win_rate",
            "profit_factor",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "avg_trade_pnl",
            "largest_win",
            "largest_loss",
            "execution_time",
            "engine_name",
            "bars_processed",
            "strategy_type",
            "strategy_params",
        }
        assert expected_keys.issubset(result.keys())

    def test_win_rate_is_fraction(self, ohlcv_df):
        """win_rate must be returned as fraction (0–1) from BacktestMetrics, not percent."""
        fake_output = _make_fake_output(win_rate=0.58)
        result = self._run_sync_with_mock_engine(ohlcv_df, fake_output)
        assert 0.0 <= result["win_rate"] <= 1.0
        assert result["win_rate"] == pytest.approx(0.58)

    def test_invalid_backtest_returns_error_dict(self, ohlcv_df):
        """When output.is_valid=False, result must have 'error' key and total_trades=0."""
        from backend.backtesting.interfaces import BacktestMetrics, BacktestOutput

        invalid_output = BacktestOutput(
            metrics=BacktestMetrics(),
            is_valid=False,
            validation_errors=["insufficient data"],
        )
        result = self._run_sync_with_mock_engine(ohlcv_df, invalid_output)
        assert "error" in result
        assert result["total_trades"] == 0
