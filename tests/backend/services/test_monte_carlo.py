"""
Tests for Monte Carlo Simulation Service.
"""

import pytest

from backend.services.monte_carlo import (
    MonteCarloResult,
    MonteCarloSimulator,
    Trade,
    get_monte_carlo_simulator,
)


class TestTrade:
    """Test cases for Trade dataclass."""

    def test_trade_from_dict(self):
        """Test creating Trade from dictionary."""
        data = {
            "entry_price": 100.0,
            "exit_price": 110.0,
            "size": 1.0,
            "side": "long",
            "pnl": 10.0,
            "pnl_pct": 0.10,
        }
        trade = Trade.from_dict(data)

        assert trade.entry_price == 100.0
        assert trade.exit_price == 110.0
        assert trade.pnl == 10.0
        assert trade.pnl_pct == 0.10


class TestMonteCarloSimulator:
    """Test cases for MonteCarloSimulator."""

    @pytest.fixture
    def simulator(self):
        """Create a simulator instance for testing."""
        return MonteCarloSimulator(n_simulations=100, random_seed=42)

    @pytest.fixture
    def sample_backtest_results(self):
        """Sample backtest results for testing."""
        trades = [
            {
                "entry_price": 100,
                "exit_price": 105,
                "size": 1,
                "side": "long",
                "pnl": 5,
                "pnl_pct": 0.05,
            },
            {
                "entry_price": 105,
                "exit_price": 103,
                "size": 1,
                "side": "long",
                "pnl": -2,
                "pnl_pct": -0.02,
            },
            {
                "entry_price": 103,
                "exit_price": 110,
                "size": 1,
                "side": "long",
                "pnl": 7,
                "pnl_pct": 0.07,
            },
            {
                "entry_price": 110,
                "exit_price": 108,
                "size": 1,
                "side": "long",
                "pnl": -2,
                "pnl_pct": -0.02,
            },
            {
                "entry_price": 108,
                "exit_price": 115,
                "size": 1,
                "side": "long",
                "pnl": 7,
                "pnl_pct": 0.065,
            },
        ]
        return {"trades": trades}

    def test_simulator_init(self, simulator):
        """Test simulator initialization."""
        assert simulator.n_simulations == 100
        assert simulator.random_seed == 42

    def test_analyze_strategy_permutation(self, simulator, sample_backtest_results):
        """Test permutation method simulation."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="permutation"
        )

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 100
        assert result.original_return is not None
        assert len(result.simulated_returns) == 100
        assert result.mean_return is not None
        assert result.std_return is not None

    def test_analyze_strategy_bootstrap(self, simulator, sample_backtest_results):
        """Test bootstrap method simulation."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="bootstrap"
        )

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 100

    def test_analyze_strategy_block_bootstrap(self, simulator, sample_backtest_results):
        """Test block bootstrap method simulation."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="block_bootstrap"
        )

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 100

    def test_probability_of_positive_return(self, simulator, sample_backtest_results):
        """Test probability calculation."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="permutation"
        )

        prob = result.probability_of_return(0.0)
        assert 0 <= prob <= 1

    def test_var_calculation(self, simulator, sample_backtest_results):
        """Test VaR is calculated."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="permutation"
        )

        assert result.var_95 is not None
        assert isinstance(result.var_95, float)

    def test_cvar_calculation(self, simulator, sample_backtest_results):
        """Test CVaR is calculated."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="permutation"
        )

        assert result.cvar_95 is not None
        assert isinstance(result.cvar_95, float)

    def test_empty_trades(self, simulator):
        """Test with empty trades - should use summary stats."""
        result = simulator.analyze_strategy(backtest_results={}, method="permutation")
        # Should still return a result (using synthetic data)
        assert result is not None

    def test_result_to_dict(self, simulator, sample_backtest_results):
        """Test result serialization to dict."""
        result = simulator.analyze_strategy(
            backtest_results=sample_backtest_results, method="permutation"
        )

        data = result.to_dict()
        assert "n_simulations" in data
        assert "original" in data
        assert "return" in data["original"]
        assert "statistics" in data
        assert "probabilities" in data


class TestGlobalInstance:
    """Test global simulator instance."""

    def test_get_monte_carlo_simulator(self):
        """Test getting global simulator instance."""
        sim1 = get_monte_carlo_simulator()
        sim2 = get_monte_carlo_simulator()

        assert sim1 is sim2  # Same instance
        assert isinstance(sim1, MonteCarloSimulator)
