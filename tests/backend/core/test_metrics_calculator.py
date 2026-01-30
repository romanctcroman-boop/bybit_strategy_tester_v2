"""
Tests for backend/core/metrics_calculator.py

Centralized metrics calculator tests ensuring:
- Formula correctness
- Consistency with TradingView definitions
- Edge case handling
- Numba-optimized function parity

Author: Audit 2026-01-25
"""

import numpy as np
import pytest

from backend.core.metrics_calculator import (
    MetricsCalculator,
    TimeFrequency,
    calculate_margin_efficiency,
    calculate_metrics_numba,
    calculate_profit_factor,
    calculate_sharpe,
    calculate_sortino,
    calculate_ulcer_index,
    calculate_win_rate,
)


class TestCalculateWinRate:
    """Tests for win rate calculation."""

    def test_win_rate_basic(self):
        """Test basic win rate calculation."""
        assert calculate_win_rate(7, 10) == 70.0

    def test_win_rate_100_percent(self):
        """Test 100% win rate."""
        assert calculate_win_rate(10, 10) == 100.0

    def test_win_rate_0_percent(self):
        """Test 0% win rate."""
        assert calculate_win_rate(0, 10) == 0.0

    def test_win_rate_no_trades(self):
        """Test win rate with no trades returns 0."""
        assert calculate_win_rate(0, 0) == 0.0

    def test_win_rate_negative_trades(self):
        """Test win rate with negative trades returns 0."""
        assert calculate_win_rate(5, -1) == 0.0


class TestCalculateProfitFactor:
    """Tests for profit factor calculation."""

    def test_profit_factor_basic(self):
        """Test basic profit factor calculation."""
        # gross_profit / gross_loss
        assert calculate_profit_factor(1000, 500) == 2.0

    def test_profit_factor_no_loss(self):
        """Test profit factor with no losses."""
        # Should return capped max (100.0)
        assert calculate_profit_factor(1000, 0) == 100.0

    def test_profit_factor_no_profit(self):
        """Test profit factor with no profit."""
        assert calculate_profit_factor(0, 500) == 0.0

    def test_profit_factor_capped(self):
        """Test profit factor is capped at 100."""
        # Very high ratio should be capped
        assert calculate_profit_factor(100000, 1) == 100.0


class TestCalculateSharpe:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_positive_returns(self):
        """Test Sharpe with positive returns."""
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.HOURLY)
        assert sharpe > 0

    def test_sharpe_negative_returns(self):
        """Test Sharpe with negative returns."""
        returns = np.array([-0.01, -0.02, -0.01, -0.015, -0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.HOURLY)
        assert sharpe < 0

    def test_sharpe_zero_std(self):
        """Test Sharpe with zero standard deviation."""
        returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.HOURLY)
        # Should return 0 when std is zero (or near zero)
        assert sharpe == 0.0

    def test_sharpe_single_return(self):
        """Test Sharpe with single return."""
        returns = np.array([0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.HOURLY)
        assert sharpe == 0.0

    def test_sharpe_empty_returns(self):
        """Test Sharpe with empty array."""
        returns = np.array([])
        sharpe = calculate_sharpe(returns, TimeFrequency.HOURLY)
        assert sharpe == 0.0


class TestCalculateSortino:
    """Tests for Sortino ratio calculation."""

    def test_sortino_positive_returns(self):
        """Test Sortino with positive returns (no downside)."""
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.01])
        sortino = calculate_sortino(returns, TimeFrequency.HOURLY)
        # Should be high since no downside
        assert sortino > 0

    def test_sortino_mixed_returns(self):
        """Test Sortino with mixed returns."""
        returns = np.array([0.01, -0.02, 0.01, -0.015, 0.01])
        sortino = calculate_sortino(returns, TimeFrequency.HOURLY)
        # Should be finite
        assert np.isfinite(sortino)

    def test_sortino_empty_returns(self):
        """Test Sortino with empty array."""
        returns = np.array([])
        sortino = calculate_sortino(returns, TimeFrequency.HOURLY)
        assert sortino == 0.0


class TestCalculateUlcerIndex:
    """Tests for Ulcer Index calculation."""

    def test_ulcer_index_no_drawdown(self):
        """Test Ulcer Index with no drawdowns."""
        drawdowns = np.array([0.0, 0.0, 0.0, 0.0])
        ulcer = calculate_ulcer_index(drawdowns)
        assert ulcer == 0.0

    def test_ulcer_index_with_drawdowns(self):
        """Test Ulcer Index with drawdowns."""
        drawdowns = np.array([0.01, 0.02, 0.015, 0.01])
        ulcer = calculate_ulcer_index(drawdowns)
        assert ulcer > 0

    def test_ulcer_index_empty(self):
        """Test Ulcer Index with empty array."""
        drawdowns = np.array([])
        ulcer = calculate_ulcer_index(drawdowns)
        assert ulcer == 0.0


class TestCalculateMarginEfficiency:
    """Tests for margin efficiency calculation."""

    def test_margin_efficiency_basic(self):
        """Test basic margin efficiency calculation."""
        # Formula: (net_profit / (avg_margin * 0.7)) * 100
        efficiency = calculate_margin_efficiency(1000, 10000)
        expected = (1000 / (10000 * 0.7)) * 100
        assert abs(efficiency - expected) < 0.01

    def test_margin_efficiency_zero_margin(self):
        """Test margin efficiency with zero margin."""
        efficiency = calculate_margin_efficiency(1000, 0)
        assert efficiency == 0.0


class TestCalculateMetricsNumba:
    """Tests for Numba-optimized metrics calculation."""

    def test_numba_basic(self):
        """Test basic Numba metrics calculation."""
        pnl_array = np.array([100.0, -50.0, 75.0, -25.0, 50.0])
        equity_array = np.array([10000.0, 10100.0, 10050.0, 10125.0, 10100.0, 10150.0])
        daily_returns = np.diff(equity_array) / equity_array[:-1]
        initial_capital = 10000.0

        result = calculate_metrics_numba(
            pnl_array, equity_array, daily_returns, initial_capital
        )

        total_return, sharpe, max_dd, win_rate, n_trades, profit_factor, calmar = result

        # Verify total return
        expected_return = (sum(pnl_array) / initial_capital) * 100
        assert abs(total_return - expected_return) < 0.1

        # Verify trade count
        assert n_trades == 5

        # Verify win rate (3 wins out of 5)
        assert abs(win_rate - 0.6) < 0.01

        # Verify profit factor
        expected_pf = (100 + 75 + 50) / (50 + 25)
        assert abs(profit_factor - expected_pf) < 0.01

    def test_numba_no_trades(self):
        """Test Numba metrics with no trades."""
        pnl_array = np.array([])
        equity_array = np.array([10000.0])
        daily_returns = np.array([0.0])
        initial_capital = 10000.0

        result = calculate_metrics_numba(
            pnl_array, equity_array, daily_returns, initial_capital
        )

        total_return, sharpe, max_dd, win_rate, n_trades, profit_factor, calmar = result

        assert total_return == 0.0
        assert n_trades == 0
        assert win_rate == 0.0


class TestMetricsCalculatorCalculateAll:
    """Tests for MetricsCalculator.calculate_all method."""

    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        return [
            {
                "pnl": 100.0,
                "pnl_pct": 1.0,
                "entry_price": 10000.0,
                "exit_price": 10100.0,
                "size": 1.0,
                "side": "long",
                "bars_in_trade": 10,
                "commission": 7.0,
            },
            {
                "pnl": -50.0,
                "pnl_pct": -0.5,
                "entry_price": 10100.0,
                "exit_price": 10050.0,
                "size": 1.0,
                "side": "long",
                "bars_in_trade": 5,
                "commission": 7.0,
            },
            {
                "pnl": 75.0,
                "pnl_pct": 0.75,
                "entry_price": 10050.0,
                "exit_price": 10125.0,
                "size": 1.0,
                "side": "short",
                "bars_in_trade": 8,
                "commission": 7.0,
            },
        ]

    @pytest.fixture
    def sample_equity(self):
        """Create sample equity curve."""
        return np.array([10000.0, 10100.0, 10050.0, 10125.0])

    def test_calculate_all_returns_dict(self, sample_trades, sample_equity):
        """Test that calculate_all returns a dictionary."""
        result = MetricsCalculator.calculate_all(
            trades=sample_trades,
            equity=sample_equity,
            initial_capital=10000.0,
            years=1.0,
            frequency=TimeFrequency.HOURLY,
        )

        assert isinstance(result, dict)

    def test_calculate_all_has_required_keys(self, sample_trades, sample_equity):
        """Test that calculate_all returns all required keys."""
        result = MetricsCalculator.calculate_all(
            trades=sample_trades,
            equity=sample_equity,
            initial_capital=10000.0,
            years=1.0,
            frequency=TimeFrequency.HOURLY,
        )

        required_keys = [
            "total_trades",
            "winning_trades",
            "losing_trades",
            "net_profit",
            "gross_profit",
            "gross_loss",
            "win_rate",
            "profit_factor",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown",
            "cagr",
        ]

        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_calculate_all_trade_counts(self, sample_trades, sample_equity):
        """Test trade count accuracy."""
        result = MetricsCalculator.calculate_all(
            trades=sample_trades,
            equity=sample_equity,
            initial_capital=10000.0,
            years=1.0,
            frequency=TimeFrequency.HOURLY,
        )

        assert result["total_trades"] == 3
        assert result["winning_trades"] == 2
        assert result["losing_trades"] == 1

    def test_calculate_all_empty_trades(self, sample_equity):
        """Test with empty trades."""
        result = MetricsCalculator.calculate_all(
            trades=[],
            equity=sample_equity,
            initial_capital=10000.0,
            years=1.0,
            frequency=TimeFrequency.HOURLY,
        )

        assert result["total_trades"] == 0
        assert result["net_profit"] == 0.0
        assert result["win_rate"] == 0.0


class TestMetricsConsistency:
    """Tests ensuring consistency between different calculation methods."""

    def test_numba_vs_python_win_rate(self):
        """Test that Numba and Python win rates match."""
        pnl_array = np.array([100.0, -50.0, 75.0, -25.0, 50.0])
        equity_array = np.array([10000.0, 10100.0, 10050.0, 10125.0, 10100.0, 10150.0])
        daily_returns = np.diff(equity_array) / equity_array[:-1]

        # Numba result
        result = calculate_metrics_numba(pnl_array, equity_array, daily_returns, 10000.0)
        numba_win_rate = result[3]

        # Python result
        wins = sum(1 for p in pnl_array if p > 0)
        python_win_rate = wins / len(pnl_array)

        assert abs(numba_win_rate - python_win_rate) < 0.001

    def test_numba_vs_python_profit_factor(self):
        """Test that Numba and Python profit factors match."""
        pnl_array = np.array([100.0, -50.0, 75.0, -25.0, 50.0])
        equity_array = np.array([10000.0, 10100.0, 10050.0, 10125.0, 10100.0, 10150.0])
        daily_returns = np.diff(equity_array) / equity_array[:-1]

        # Numba result
        result = calculate_metrics_numba(pnl_array, equity_array, daily_returns, 10000.0)
        numba_pf = result[5]

        # Python result
        gross_profit = sum(p for p in pnl_array if p > 0)
        gross_loss = abs(sum(p for p in pnl_array if p < 0))
        python_pf = calculate_profit_factor(gross_profit, gross_loss)

        assert abs(numba_pf - python_pf) < 0.01
