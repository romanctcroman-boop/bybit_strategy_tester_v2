"""
Tests for centralized metrics formulas.

Tests for backend/core/formulas.py
"""

import numpy as np

from backend.core.formulas import (
    calculate_cvar,
    calculate_expectancy,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_total_return,
    calculate_var,
    calculate_win_rate,
)


class TestCalculateSharpeRatio:
    """Tests for calculate_sharpe_ratio"""

    def test_sharpe_with_positive_returns(self):
        """Test Sharpe with positive returns"""
        returns = [0.01, 0.02, 0.015, 0.025, 0.01]
        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe > 0
        assert np.isfinite(sharpe)

    def test_sharpe_with_negative_returns(self):
        """Test Sharpe with negative returns"""
        returns = [-0.01, -0.02, -0.015, -0.025, -0.01]
        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe < 0
        assert np.isfinite(sharpe)

    def test_sharpe_empty_returns(self):
        """Test Sharpe with empty returns"""
        returns = []
        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe == 0.0

    def test_sharpe_single_value(self):
        """Test Sharpe with single value"""
        returns = [0.01]
        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe == 0.0

    def test_sharpe_with_risk_free_rate(self):
        """Test Sharpe with risk-free rate"""
        returns = [0.01, 0.02, 0.015, 0.025, 0.01]
        sharpe_no_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.0)
        sharpe_with_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.05)

        # With higher RF, Sharpe should be different
        assert sharpe_no_rf != sharpe_with_rf or sharpe_no_rf == 0


class TestCalculateSortinoRatio:
    """Tests for calculate_sortino_ratio"""

    def test_sortino_with_positive_returns(self):
        """Test Sortino with positive returns"""
        returns = [0.01, 0.02, 0.015, 0.025, 0.01]
        sortino = calculate_sortino_ratio(returns)

        assert np.isfinite(sortino)

    def test_sortino_with_negative_returns(self):
        """Test Sortino with negative returns"""
        returns = [-0.01, -0.02, -0.015, -0.025, -0.01]
        sortino = calculate_sortino_ratio(returns)

        assert sortino < 0 or sortino == 0

    def test_sortino_empty_returns(self):
        """Test Sortino with empty returns"""
        returns = []
        sortino = calculate_sortino_ratio(returns)

        assert sortino == 0.0


class TestCalculateMaxDrawdown:
    """Tests for calculate_max_drawdown"""

    def test_max_drawdown_uptrend(self):
        """Test Max DD with uptrend"""
        equity = [100, 110, 120, 130, 140]
        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0 or max_dd > -0.01

    def test_max_drawdown_downtrend(self):
        """Test Max DD with downtrend"""
        equity = [100, 90, 80, 70, 60]
        max_dd = calculate_max_drawdown(equity)

        assert max_dd < 0
        assert abs(max_dd) > 0.3

    def test_max_drawdown_with_drawdown(self):
        """Test Max DD with drawdown"""
        equity = [100, 120, 110, 130, 100]
        max_dd = calculate_max_drawdown(equity)

        # Max DD from 130 to 100 = -23%
        assert max_dd < -0.2
        assert max_dd > -0.3

    def test_max_drawdown_empty(self):
        """Test Max DD with empty equity"""
        equity = []
        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0


class TestCalculateTotalReturn:
    """Tests for calculate_total_return"""

    def test_total_return_positive(self):
        """Test positive total return"""
        equity = [100, 110, 120, 130]
        total_return = calculate_total_return(equity)

        assert total_return > 0
        assert abs(total_return - 0.3) < 0.01

    def test_total_return_negative(self):
        """Test negative total return"""
        equity = [100, 90, 80, 70]
        total_return = calculate_total_return(equity)

        assert total_return < 0
        assert abs(total_return - (-0.3)) < 0.01

    def test_total_return_zero(self):
        """Test zero total return"""
        equity = [100, 100, 100, 100]
        total_return = calculate_total_return(equity)

        assert total_return == 0.0

    def test_total_return_empty(self):
        """Test empty equity"""
        equity = []
        total_return = calculate_total_return(equity)

        assert total_return == 0.0


class TestCalculateWinRate:
    """Tests for calculate_win_rate"""

    def test_win_rate_all_wins(self):
        """Test 100% win rate"""
        trades = [
            {"pnl": 100},
            {"pnl": 200},
            {"pnl": 150},
        ]
        win_rate = calculate_win_rate(trades)

        assert win_rate == 1.0

    def test_win_rate_all_losses(self):
        """Test 0% win rate"""
        trades = [
            {"pnl": -100},
            {"pnl": -200},
            {"pnl": -150},
        ]
        win_rate = calculate_win_rate(trades)

        assert win_rate == 0.0

    def test_win_rate_mixed(self):
        """Test mixed win rate"""
        trades = [
            {"pnl": 100},
            {"pnl": -100},
            {"pnl": 200},
            {"pnl": -200},
        ]
        win_rate = calculate_win_rate(trades)

        assert win_rate == 0.5

    def test_win_rate_empty(self):
        """Test empty trades"""
        trades = []
        win_rate = calculate_win_rate(trades)

        assert win_rate == 0.0


class TestCalculateProfitFactor:
    """Tests for calculate_profit_factor"""

    def test_profit_factor_profitable(self):
        """Test profitable profit factor"""
        trades = [
            {"pnl": 300},
            {"pnl": 200},
            {"pnl": -100},
        ]
        pf = calculate_profit_factor(trades)

        # Gross profit = 500, Gross loss = 100
        # PF = 500 / 100 = 5.0
        assert abs(pf - 5.0) < 0.01

    def test_profit_factor_unprofitable(self):
        """Test unprofitable profit factor"""
        trades = [
            {"pnl": 100},
            {"pnl": -200},
            {"pnl": -300},
        ]
        pf = calculate_profit_factor(trades)

        # Gross profit = 100, Gross loss = 500
        # PF = 100 / 500 = 0.2
        assert abs(pf - 0.2) < 0.01

    def test_profit_factor_no_losses(self):
        """Test profit factor with no losses"""
        trades = [
            {"pnl": 100},
            {"pnl": 200},
            {"pnl": 300},
        ]
        pf = calculate_profit_factor(trades)

        # No losses, should return 0 or inf
        assert pf == 0.0 or np.isinf(pf)

    def test_profit_factor_empty(self):
        """Test empty trades"""
        trades = []
        pf = calculate_profit_factor(trades)

        assert pf == 0.0


class TestCalculateExpectancy:
    """Tests for calculate_expectancy"""

    def test_expectancy_positive(self):
        """Test positive expectancy"""
        trades = [
            {"pnl": 300},
            {"pnl": -100},
            {"pnl": 300},
            {"pnl": -100},
        ]
        expectancy = calculate_expectancy(trades)

        # Win rate = 0.5, Avg win = 300, Avg loss = -100
        # Expectancy = (0.5 * 300) - (0.5 * 100) = 100
        assert abs(expectancy - 100) < 1

    def test_expectancy_negative(self):
        """Test negative expectancy"""
        trades = [
            {"pnl": 100},
            {"pnl": -300},
            {"pnl": 100},
            {"pnl": -300},
        ]
        expectancy = calculate_expectancy(trades)

        # Win rate = 0.5, Avg win = 100, Avg loss = -300
        # Expectancy = (0.5 * 100) - (0.5 * 300) = -100
        assert abs(expectancy - (-100)) < 1

    def test_expectancy_empty(self):
        """Test empty trades"""
        trades = []
        expectancy = calculate_expectancy(trades)

        assert expectancy == 0.0


class TestCalculateVaRCVaR:
    """Tests for VaR and CVaR"""

    def test_var_normal(self):
        """Test VaR with normal returns"""
        np.random.seed(42)
        returns = np.random.randn(1000) * 0.02

        var = calculate_var(returns, confidence_level=0.95)

        # VaR should be negative (loss)
        assert var < 0
        assert np.isfinite(var)

    def test_cvar_normal(self):
        """Test CVaR with normal returns"""
        np.random.seed(42)
        returns = np.random.randn(1000) * 0.02

        cvar = calculate_cvar(returns, confidence_level=0.95)

        # CVaR should be more negative than VaR
        var = calculate_var(returns, confidence_level=0.95)
        assert cvar <= var
        assert np.isfinite(cvar)

    def test_var_short_series(self):
        """Test VaR with short series"""
        returns = [0.01, 0.02, 0.03]
        var = calculate_var(returns)

        # Should return 0 for short series
        assert var == 0.0

    def test_cvar_short_series(self):
        """Test CVaR with short series"""
        returns = [0.01, 0.02, 0.03]
        cvar = calculate_cvar(returns)

        # Should return 0 for short series
        assert cvar == 0.0


class TestIntegration:
    """Integration tests"""

    def test_full_metrics_calculation(self):
        """Test full metrics calculation"""
        # Generate sample equity curve
        np.random.seed(42)
        returns = np.random.randn(252) * 0.02 + 0.0005  # Daily returns
        equity = 10000 * (1 + returns).cumprod()

        # Calculate metrics
        sharpe = calculate_sharpe_ratio(returns)
        max_dd = calculate_max_drawdown(equity)
        total_return = calculate_total_return(equity)

        # Verify
        assert np.isfinite(sharpe)
        assert max_dd < 0
        assert np.isfinite(total_return)

    def test_trades_metrics(self):
        """Test trades metrics"""
        trades = [
            {"pnl": 500, "duration": 5},
            {"pnl": -200, "duration": 3},
            {"pnl": 300, "duration": 7},
            {"pnl": -100, "duration": 2},
            {"pnl": 400, "duration": 4},
        ]

        win_rate = calculate_win_rate(trades)
        pf = calculate_profit_factor(trades)
        expectancy = calculate_expectancy(trades)

        assert 0 <= win_rate <= 1
        assert pf > 0
        assert np.isfinite(expectancy)
