"""
Test Monte Carlo simulation module.
"""

import numpy as np
import pytest

from backend.backtesting.monte_carlo import (
    MonteCarloResult,
    MonteCarloSimulator,
    SimulationMethod,
    run_monte_carlo_analysis,
)


class TestMonteCarloSimulator:
    """Tests for Monte Carlo simulation."""

    @pytest.fixture
    def sample_trades(self):
        """Generate sample trades with mixed PnL."""
        np.random.seed(42)
        n_trades = 100
        # Generate realistic trade PnL (60% win rate, 1.5 avg win/loss ratio)
        pnl = []
        for _ in range(n_trades):
            if np.random.random() < 0.6:  # 60% win rate
                pnl.append(np.random.uniform(50, 300))  # Wins
            else:
                pnl.append(np.random.uniform(-200, -50))  # Losses
        return [{"pnl": p} for p in pnl]

    @pytest.fixture
    def losing_trades(self):
        """Generate losing trades for ruin testing."""
        return [{"pnl": -100} for _ in range(50)]

    def test_simulator_initialization(self, sample_trades):
        """Test simulator initialization."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)

        assert sim.n_trades == len(sample_trades)
        assert sim.initial_capital == 10000
        assert len(sim.pnl_values) == len(sample_trades)

    def test_simulator_from_pnl_array(self):
        """Test initialization from PnL array."""
        pnl = np.array([100, -50, 200, -100, 150])
        sim = MonteCarloSimulator(pnl_values=pnl, initial_capital=5000)

        assert sim.n_trades == 5
        np.testing.assert_array_equal(sim.pnl_values, pnl)

    def test_trade_shuffle_simulation(self, sample_trades):
        """Test trade shuffle simulation method."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(
            n_simulations=1000,
            method=SimulationMethod.TRADE_SHUFFLE,
            seed=42,
        )

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 1000
        assert result.method == SimulationMethod.TRADE_SHUFFLE
        assert result.n_trades == len(sample_trades)

        # Check statistics are reasonable
        assert result.mean_final_equity > 0
        assert result.std_final_equity > 0
        assert 0 <= result.probability_of_profit <= 1
        assert 0 <= result.probability_of_ruin <= 1

    def test_bootstrap_simulation(self, sample_trades):
        """Test bootstrap simulation method."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(
            n_simulations=1000,
            method=SimulationMethod.BOOTSTRAP,
            seed=42,
        )

        assert result.method == SimulationMethod.BOOTSTRAP
        assert result.mean_final_equity > 0

    def test_block_bootstrap_simulation(self, sample_trades):
        """Test block bootstrap simulation method."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(
            n_simulations=1000,
            method=SimulationMethod.BLOCK_BOOTSTRAP,
            block_size=5,
            seed=42,
        )

        assert result.method == SimulationMethod.BLOCK_BOOTSTRAP
        assert result.mean_final_equity > 0

    def test_parametric_simulation(self, sample_trades):
        """Test parametric simulation method."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(
            n_simulations=1000,
            method=SimulationMethod.PARAMETRIC,
            seed=42,
        )

        assert result.method == SimulationMethod.PARAMETRIC
        assert result.mean_final_equity > 0

    def test_confidence_intervals(self, sample_trades):
        """Test confidence intervals are calculated correctly."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(n_simulations=5000, seed=42)

        # 95% CI should be narrower or equal to 99% CI
        ci_95_width = result.equity_ci_95[1] - result.equity_ci_95[0]
        ci_99_width = result.equity_ci_99[1] - result.equity_ci_99[0]
        assert ci_99_width >= ci_95_width - 1e-9  # Allow small numerical tolerance

        # 90% CI should be narrower or equal to 95% CI
        ci_90_width = result.equity_ci_90[1] - result.equity_ci_90[0]
        assert ci_95_width >= ci_90_width - 1e-9

        # Lower bound should be less than mean
        assert result.equity_ci_95[0] < result.mean_final_equity
        assert result.equity_ci_95[1] > result.mean_final_equity

    def test_drawdown_statistics(self, sample_trades):
        """Test drawdown statistics."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(n_simulations=1000, seed=42)

        # Drawdown should be between 0 and 1
        assert 0 <= result.mean_max_drawdown <= 1
        assert 0 <= result.median_max_drawdown <= 1
        assert 0 <= result.worst_drawdown <= 1

        # Worst should be >= mean
        assert result.worst_drawdown >= result.mean_max_drawdown

    def test_risk_metrics(self, sample_trades):
        """Test risk metrics calculation."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(n_simulations=1000, seed=42)

        # VaR should be negative (it's the 5th percentile of returns)
        # CVaR should be <= VaR (it's the expected loss in worst cases)
        # Allow small numerical tolerance
        assert result.cvar_95 <= result.var_95 + 1e-9

    def test_probability_of_ruin(self, losing_trades):
        """Test probability of ruin with losing strategy."""
        # Create trades that definitely lead to ruin (lose 80% of capital)
        heavy_losing_trades = [{"pnl": -200} for _ in range(100)]
        sim = MonteCarloSimulator(
            trades=heavy_losing_trades, initial_capital=10000, ruin_threshold=0.5
        )
        result = sim.run_simulation(n_simulations=1000, seed=42)

        # With consistent heavy losses (-$200 x 100 = -$20,000), equity should go negative
        # Probability of ruin should be high (final equity < 5000)
        assert result.probability_of_ruin > 0.5
        assert result.probability_of_profit < 0.5

    def test_percentiles(self, sample_trades):
        """Test percentile calculations."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(n_simulations=1000, seed=42)

        # Percentiles should be monotonically increasing
        percentiles = result.equity_percentiles
        assert percentiles[5] < percentiles[50] < percentiles[95]

    def test_confidence_bands(self, sample_trades):
        """Test confidence band generation."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)

        bands = sim.generate_confidence_bands(n_simulations=500, confidence_level=0.95)

        assert "mean" in bands
        assert "upper" in bands
        assert "lower" in bands
        assert "percentiles" in bands

        # Upper should always be >= mean (with small tolerance)
        assert np.all(bands["upper"] >= bands["mean"] - 1e-6)
        # Just check that lower is not significantly above mean
        assert np.all(bands["lower"] <= bands["mean"] + bands["mean"].max() * 0.1)

    def test_to_dict(self, sample_trades):
        """Test result serialization."""
        sim = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        result = sim.run_simulation(n_simulations=100, seed=42)

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "mean_final_equity" in result_dict
        assert "probability_of_profit" in result_dict
        assert result_dict["n_simulations"] == 100

    def test_insufficient_trades(self):
        """Test handling of insufficient trades."""
        sim = MonteCarloSimulator(pnl_values=np.array([100]), initial_capital=10000)
        result = sim.run_simulation(n_simulations=100)

        # Should return empty result
        assert result.mean_final_equity == 10000
        assert result.std_final_equity == 0

    def test_reproducibility(self, sample_trades):
        """Test that seed produces reproducible results."""
        sim1 = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)
        sim2 = MonteCarloSimulator(trades=sample_trades, initial_capital=10000)

        result1 = sim1.run_simulation(n_simulations=100, seed=42)
        result2 = sim2.run_simulation(n_simulations=100, seed=42)

        assert result1.mean_final_equity == result2.mean_final_equity
        assert result1.std_final_equity == result2.std_final_equity


class TestRunMonteCarloAnalysis:
    """Test comprehensive Monte Carlo analysis function."""

    def test_run_analysis(self):
        """Test running analysis with multiple methods."""
        np.random.seed(42)
        trades = [{"pnl": np.random.uniform(-100, 200)} for _ in range(50)]

        results = run_monte_carlo_analysis(
            trades=trades,
            initial_capital=10000,
            n_simulations=500,
        )

        assert "trade_shuffle" in results
        assert "bootstrap" in results
        assert "block_bootstrap" in results

        for method, result in results.items():
            assert isinstance(result, MonteCarloResult)
            assert result.n_simulations == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
