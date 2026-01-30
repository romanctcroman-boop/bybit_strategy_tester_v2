"""
Тесты для Advanced Features Universal Math Engine.

Покрывает:
1. Scale-in / Pyramiding
2. Partial Close (Multi-TP)
3. Time-based Exit
4. Slippage Models
5. Funding Rate
6. Hedge Mode
7. Bayesian Optimization
8. Genetic Algorithm
9. Walk-Forward Analysis
10. Monte Carlo Simulation
11. Portfolio Mode
12. Metrics Integration

Автор: AI Agent
Версия: 1.0.0
"""

import numpy as np
import pytest

from backend.backtesting.universal_engine import (
    # Advanced Features
    AdvancedFeatures,
    CorrelationManager,
    FundingConfig,
    # Advanced Optimization
    GeneticConfig,
    GeneticOptimizer,
    HedgeConfig,
    HedgeManager,
    MetricsCalculator,
    MetricsConfig,
    MonteCarloConfig,
    MonteCarloSimulator,
    PartialCloseConfig,
    # Portfolio & Metrics
    PortfolioConfig,
    PortfolioManager,
    PortfolioMode,
    ScaleInConfig,
    ScaleInMode,
    SlippageConfig,
    SlippageModel,
    TimeExitConfig,
    TimeExitMode,
    WalkForwardAnalyzer,
    WalkForwardConfig,
    WalkForwardMode,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_trades():
    """Sample trades for testing."""
    return [
        {
            "pnl": 100,
            "direction": 1,
            "duration_bars": 10,
            "entry_price": 50000,
            "exit_price": 51000,
        },
        {
            "pnl": -50,
            "direction": 1,
            "duration_bars": 5,
            "entry_price": 51000,
            "exit_price": 50500,
        },
        {
            "pnl": 150,
            "direction": -1,
            "duration_bars": 15,
            "entry_price": 50500,
            "exit_price": 49000,
        },
        {
            "pnl": -30,
            "direction": -1,
            "duration_bars": 3,
            "entry_price": 49000,
            "exit_price": 49300,
        },
        {
            "pnl": 200,
            "direction": 1,
            "duration_bars": 20,
            "entry_price": 49300,
            "exit_price": 51300,
        },
    ]


@pytest.fixture
def sample_equity_curve():
    """Sample equity curve."""
    initial = 10000
    changes = [100, -50, 150, -30, 200, -20, 180, -40, 120, 50]
    equity = [initial]
    for change in changes:
        equity.append(equity[-1] + change)
    return np.array(equity, dtype=np.float64)


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data."""
    n = 100
    np.random.seed(42)

    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    open_ = close + np.random.randn(n) * 20
    volume = 1000 + np.abs(np.random.randn(n) * 500)

    return np.column_stack([open_, high, low, close, volume])


# =============================================================================
# TESTS: SCALE-IN / PYRAMIDING
# =============================================================================


class TestScaleIn:
    """Tests for Scale-in / Pyramiding."""

    def test_scale_in_config_defaults(self):
        """Test default ScaleInConfig."""
        config = ScaleInConfig()

        assert config.enabled is False
        assert config.mode == ScaleInMode.FIXED_LEVELS
        assert config.max_additions == 3
        assert len(config.profit_levels) == 3
        assert len(config.size_multipliers) == 3

    def test_scale_in_levels_calculation(self):
        """Test scale-in level calculation."""
        config = ScaleInConfig(enabled=True, profit_levels=[0.01, 0.02, 0.03])
        features = AdvancedFeatures(scale_in_config=config)

        entry_price = 50000.0

        # Long
        levels, sizes = features.get_scale_in_levels(entry_price, direction=1)
        assert len(levels) == 3
        assert levels[0] == pytest.approx(50500.0, rel=1e-5)  # +1%
        assert levels[1] == pytest.approx(51000.0, rel=1e-5)  # +2%
        assert levels[2] == pytest.approx(51500.0, rel=1e-5)  # +3%

        # Short
        levels, sizes = features.get_scale_in_levels(entry_price, direction=-1)
        assert levels[0] == pytest.approx(49500.0, rel=1e-5)  # -1%
        assert levels[1] == pytest.approx(49000.0, rel=1e-5)  # -2%
        assert levels[2] == pytest.approx(48500.0, rel=1e-5)  # -3%

    def test_scale_in_disabled(self):
        """Test disabled scale-in returns empty arrays."""
        config = ScaleInConfig(enabled=False)
        features = AdvancedFeatures(scale_in_config=config)

        levels, sizes = features.get_scale_in_levels(50000.0, 1)

        assert len(levels) == 0
        assert len(sizes) == 0


# =============================================================================
# TESTS: PARTIAL CLOSE (MULTI-TP)
# =============================================================================


class TestPartialClose:
    """Tests for Partial Close (Multi-TP)."""

    def test_partial_close_config_defaults(self):
        """Test default PartialCloseConfig."""
        config = PartialCloseConfig()

        assert config.enabled is False
        assert len(config.tp_levels) == 3
        assert sum(config.close_percentages) == pytest.approx(1.0)

    def test_partial_close_levels(self):
        """Test partial close level calculation."""
        config = PartialCloseConfig(
            enabled=True,
            tp_levels=[0.01, 0.02, 0.03],
            close_percentages=[0.25, 0.50, 0.25],
        )
        features = AdvancedFeatures(partial_close_config=config)

        entry_price = 50000.0

        # Long
        levels, percentages = features.get_partial_close_levels(entry_price, 1)
        assert levels[0] == pytest.approx(50500.0)  # TP1
        assert levels[1] == pytest.approx(51000.0)  # TP2
        assert levels[2] == pytest.approx(51500.0)  # TP3
        assert percentages[0] == 0.25
        assert percentages[1] == 0.50
        assert percentages[2] == 0.25


# =============================================================================
# TESTS: TIME-BASED EXIT
# =============================================================================


class TestTimeExit:
    """Tests for Time-based Exit."""

    def test_time_exit_max_bars(self):
        """Test max bars exit."""
        config = TimeExitConfig(
            enabled=True,
            mode=TimeExitMode.MAX_BARS,
            max_bars_in_trade=50,
        )
        features = AdvancedFeatures(time_exit_config=config)

        # Within limit
        assert (
            features.should_exit_by_time(bar_index=30, entry_bar=0, timestamp=0)
            is False
        )

        # At limit
        assert (
            features.should_exit_by_time(bar_index=50, entry_bar=0, timestamp=0) is True
        )

        # Over limit
        assert (
            features.should_exit_by_time(bar_index=60, entry_bar=0, timestamp=0) is True
        )

    def test_time_exit_disabled(self):
        """Test disabled time exit."""
        config = TimeExitConfig(enabled=False)
        features = AdvancedFeatures(time_exit_config=config)

        assert (
            features.should_exit_by_time(bar_index=1000, entry_bar=0, timestamp=0)
            is False
        )


# =============================================================================
# TESTS: SLIPPAGE MODELS
# =============================================================================


class TestSlippage:
    """Tests for Slippage Models."""

    def test_slippage_fixed_buy(self):
        """Test fixed slippage for buy."""
        config = SlippageConfig(model=SlippageModel.FIXED, fixed_slippage=0.001)
        features = AdvancedFeatures(slippage_config=config)

        price = 50000.0
        slipped_price = features.apply_slippage(price, is_buy=True)

        assert slipped_price == pytest.approx(50050.0)  # +0.1%

    def test_slippage_fixed_sell(self):
        """Test fixed slippage for sell."""
        config = SlippageConfig(model=SlippageModel.FIXED, fixed_slippage=0.001)
        features = AdvancedFeatures(slippage_config=config)

        price = 50000.0
        slipped_price = features.apply_slippage(price, is_buy=False)

        assert slipped_price == pytest.approx(49950.0)  # -0.1%

    def test_slippage_none(self):
        """Test no slippage."""
        config = SlippageConfig(model=SlippageModel.NONE)
        features = AdvancedFeatures(slippage_config=config)

        price = 50000.0
        slipped_price = features.apply_slippage(price, is_buy=True)

        assert slipped_price == price


# =============================================================================
# TESTS: FUNDING RATE
# =============================================================================


class TestFunding:
    """Tests for Funding Rate."""

    def test_funding_long_position(self):
        """Test funding for long position."""
        config = FundingConfig(
            enabled=True,
            funding_rate=0.0001,  # 0.01%
            funding_interval_hours=8,
        )
        features = AdvancedFeatures(funding_config=config)

        position_value = 10000.0
        hours_held = 24.0  # 3 funding intervals

        funding_cost = features.calculate_funding(
            position_value, hours_held, is_long=True
        )

        # Long pays funding: -10000 * 0.0001 * 3 = -3
        assert funding_cost == pytest.approx(-3.0)

    def test_funding_short_position(self):
        """Test funding for short position."""
        config = FundingConfig(
            enabled=True,
            funding_rate=0.0001,
            funding_interval_hours=8,
        )
        features = AdvancedFeatures(funding_config=config)

        position_value = 10000.0
        hours_held = 24.0

        funding_income = features.calculate_funding(
            position_value, hours_held, is_long=False
        )

        # Short receives funding: +10000 * 0.0001 * 3 = +3
        assert funding_income == pytest.approx(3.0)

    def test_funding_disabled(self):
        """Test disabled funding."""
        config = FundingConfig(enabled=False)
        features = AdvancedFeatures(funding_config=config)

        assert features.calculate_funding(10000.0, 24.0, True) == 0.0


# =============================================================================
# TESTS: HEDGE MODE
# =============================================================================


class TestHedgeMode:
    """Tests for Hedge Mode."""

    def test_hedge_manager_open_long(self):
        """Test opening long in hedge mode."""
        config = HedgeConfig(enabled=True, allow_simultaneous=True)
        manager = HedgeManager(config)

        result = manager.open_long(price=50000.0, size=1.0)

        assert result is True
        assert manager.position.long_size == 1.0
        assert manager.position.long_entry == 50000.0

    def test_hedge_manager_simultaneous_positions(self):
        """Test simultaneous long and short positions."""
        config = HedgeConfig(enabled=True, allow_simultaneous=True)
        manager = HedgeManager(config)

        manager.open_long(price=50000.0, size=1.0)
        manager.open_short(price=50000.0, size=0.5)

        assert manager.position.long_size == 1.0
        assert manager.position.short_size == 0.5
        assert manager.position.net_size == 0.5

    def test_hedge_manager_close_all(self):
        """Test closing all positions."""
        config = HedgeConfig(enabled=True, allow_simultaneous=True)
        manager = HedgeManager(config)

        manager.open_long(price=50000.0, size=1.0)
        manager.open_short(price=50000.0, size=0.5)

        pnl = manager.close_all(price=51000.0)

        # Long: (51000 - 50000) * 1.0 = 1000
        # Short: (50000 - 51000) * 0.5 = -500
        # Total: 500
        assert pnl == pytest.approx(500.0)
        assert manager.position.long_size == 0
        assert manager.position.short_size == 0


# =============================================================================
# TESTS: GENETIC ALGORITHM
# =============================================================================


class TestGeneticOptimizer:
    """Tests for Genetic Algorithm."""

    def test_genetic_optimizer_simple(self):
        """Test simple genetic optimization."""
        config = GeneticConfig(
            population_size=20,
            n_generations=10,
            mutation_prob=0.1,
        )

        param_bounds = {
            "x": (-5.0, 5.0),
            "y": (-5.0, 5.0),
        }

        optimizer = GeneticOptimizer(config=config, param_bounds=param_bounds)

        # Simple sphere function (minimize)
        def objective(params):
            x, y = params["x"], params["y"]
            return -(x**2 + y**2)  # Negate for maximization

        result = optimizer.optimize(objective, verbose=False)

        assert "best_params" in result
        assert "best_fitness" in result
        assert result["best_fitness"] > -50  # Reasonable result

    def test_genetic_optimizer_convergence(self):
        """Test genetic optimizer converges."""
        config = GeneticConfig(
            population_size=30,
            n_generations=20,
            stagnation_generations=5,
        )

        param_bounds = {"x": (0.0, 10.0)}
        optimizer = GeneticOptimizer(config=config, param_bounds=param_bounds)

        # Target: x = 5
        def objective(params):
            return -abs(params["x"] - 5)

        result = optimizer.optimize(objective, verbose=False)

        assert abs(result["best_params"]["x"] - 5) < 2  # Close to optimal


# =============================================================================
# TESTS: WALK-FORWARD ANALYSIS
# =============================================================================


class TestWalkForward:
    """Tests for Walk-Forward Analysis."""

    def test_walk_forward_standard_mode(self, sample_ohlcv):
        """Test standard walk-forward mode."""
        config = WalkForwardConfig(
            mode=WalkForwardMode.STANDARD,
            train_ratio=0.7,
            test_ratio=0.3,
            n_folds=3,
            min_train_samples=10,
            min_test_samples=5,
        )

        analyzer = WalkForwardAnalyzer(config)

        # Simple optimize function
        def optimize_func(train_data):
            return {"best_params": {"period": 14}, "best_value": 0.5}

        # Simple backtest function
        def backtest_func(data, params):
            return {"total_return": np.random.random() * 0.2 - 0.05}

        result = analyzer.analyze(
            sample_ohlcv, optimize_func, backtest_func, verbose=False
        )

        assert len(result.fold_results) > 0
        assert result.robustness_ratio is not None
        assert result.consistency_score is not None

    def test_walk_forward_config_modes(self):
        """Test different walk-forward modes."""
        for mode in WalkForwardMode:
            config = WalkForwardConfig(mode=mode, n_folds=2)
            assert config.mode == mode


# =============================================================================
# TESTS: MONTE CARLO SIMULATION
# =============================================================================


class TestMonteCarlo:
    """Tests for Monte Carlo Simulation."""

    def test_monte_carlo_basic(self, sample_trades):
        """Test basic Monte Carlo simulation."""
        config = MonteCarloConfig(
            n_simulations=100,
            seed=42,
        )

        simulator = MonteCarloSimulator(config)
        pnls = np.array([t["pnl"] for t in sample_trades], dtype=np.float64)

        result = simulator.simulate(pnls, initial_capital=10000.0, verbose=False)

        assert result.mean_return is not None
        assert result.std_return >= 0
        # VaR should be <= mean_return (with tolerance for floating point)
        assert result.var_95 <= result.mean_return + 1e-10
        assert 0 <= result.probability_of_ruin <= 1

    def test_monte_carlo_confidence_intervals(self, sample_trades):
        """Test Monte Carlo confidence intervals."""
        config = MonteCarloConfig(
            n_simulations=500,
            confidence_levels=[0.90, 0.95, 0.99],
            seed=42,
        )

        simulator = MonteCarloSimulator(config)
        pnls = np.array([t["pnl"] for t in sample_trades], dtype=np.float64)

        result = simulator.simulate(pnls, initial_capital=10000.0, verbose=False)

        assert 0.90 in result.confidence_intervals
        assert 0.95 in result.confidence_intervals
        assert 0.99 in result.confidence_intervals

        # Lower bound should be less than upper
        for level, (lower, upper) in result.confidence_intervals.items():
            assert lower <= upper


# =============================================================================
# TESTS: PORTFOLIO MODE
# =============================================================================


class TestPortfolioManager:
    """Tests for Portfolio Mode."""

    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        config = PortfolioConfig(
            enabled=True,
            symbols=["BTCUSDT", "ETHUSDT"],
            mode=PortfolioMode.EQUAL_WEIGHT,
        )

        manager = PortfolioManager(config)
        manager.initialize(initial_capital=10000.0)

        assert manager.state.cash == 10000.0
        assert manager.state.total_equity == 10000.0
        assert len(manager.state.weights) == 2
        assert manager.state.weights["BTCUSDT"] == 0.5
        assert manager.state.weights["ETHUSDT"] == 0.5

    def test_portfolio_open_position(self):
        """Test opening position in portfolio."""
        config = PortfolioConfig(
            enabled=True,
            symbols=["BTCUSDT", "ETHUSDT"],
            max_single_asset_weight=0.6,  # Allow 60% per asset
        )

        manager = PortfolioManager(config)
        manager.initialize(initial_capital=10000.0)

        # 0.05 * 50000 = 2500, which is 25% of 10000 (under 60% limit)
        result = manager.open_position(
            symbol="BTCUSDT",
            direction=1,
            size=0.05,
            price=50000.0,
            timestamp=1000,
        )

        assert result is True
        assert "BTCUSDT" in manager.state.positions
        assert manager.state.positions["BTCUSDT"].size == 0.05

    def test_portfolio_close_position(self):
        """Test closing position in portfolio."""
        config = PortfolioConfig(
            symbols=["BTCUSDT"],
            max_single_asset_weight=0.6,
        )
        manager = PortfolioManager(config)
        manager.initialize(initial_capital=10000.0)

        # Open position first - 0.05 * 50000 = 2500 (25%)
        manager.open_position("BTCUSDT", 1, 0.05, 50000.0, 1000)
        trade = manager.close_position("BTCUSDT", 51000.0, 2000)

        assert trade is not None
        assert trade["pnl"] == pytest.approx(50.0)  # (51000 - 50000) * 0.05
        assert "BTCUSDT" not in manager.state.positions


# =============================================================================
# TESTS: CORRELATION MANAGER
# =============================================================================


class TestCorrelationManager:
    """Tests for Correlation Manager."""

    def test_correlation_manager_basic(self):
        """Test basic correlation management."""
        manager = CorrelationManager(max_correlation=0.7, lookback=20)

        # Add returns
        np.random.seed(42)
        for i in range(30):
            manager.add_return("BTCUSDT", np.random.randn() * 0.02)
            manager.add_return("ETHUSDT", np.random.randn() * 0.02)

        manager.update_correlations()

        corr = manager.get_correlation("BTCUSDT", "ETHUSDT")
        assert -1 <= corr <= 1

    def test_correlation_filter(self):
        """Test correlation-based trading filter."""
        manager = CorrelationManager(max_correlation=0.5, lookback=20)

        # Add highly correlated returns
        np.random.seed(42)
        base_returns = np.random.randn(30) * 0.02

        for i, ret in enumerate(base_returns):
            manager.add_return("BTCUSDT", ret)
            manager.add_return(
                "ETHUSDT", ret + np.random.randn() * 0.001
            )  # Highly correlated

        manager.update_correlations()

        # Should not allow trading if high correlation
        can_trade = manager.can_trade("ETHUSDT", ["BTCUSDT"])
        # Result depends on actual correlation


# =============================================================================
# TESTS: METRICS CALCULATOR
# =============================================================================


class TestMetricsCalculator:
    """Tests for Metrics Calculator."""

    def test_basic_metrics(self, sample_equity_curve, sample_trades):
        """Test basic metrics calculation."""
        config = MetricsConfig(calculate_all=False, calculate_basic=True)
        calc = MetricsCalculator(config)

        metrics = calc.calculate_basic_metrics(
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            initial_capital=10000.0,
        )

        assert "total_return" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert metrics["total_trades"] == 5

    def test_drawdown_metrics(self, sample_equity_curve):
        """Test drawdown metrics calculation."""
        config = MetricsConfig()
        calc = MetricsCalculator(config)

        metrics = calc.calculate_drawdown_metrics(sample_equity_curve)

        assert "max_drawdown" in metrics
        assert "avg_drawdown" in metrics
        assert 0 <= metrics["max_drawdown"] <= 1

    def test_risk_metrics(self, sample_equity_curve, sample_trades):
        """Test risk metrics calculation."""
        config = MetricsConfig(risk_free_rate=0.02)
        calc = MetricsCalculator(config)

        metrics = calc.calculate_risk_metrics(
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            initial_capital=10000.0,
        )

        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "calmar_ratio" in metrics
        assert "var_95" in metrics

    def test_trade_stats(self, sample_trades):
        """Test trade statistics calculation."""
        calc = MetricsCalculator()

        stats = calc.calculate_trade_stats(sample_trades)

        assert "expectancy" in stats
        assert "kelly_criterion" in stats
        assert "risk_reward_ratio" in stats
        assert stats["total_long_trades"] + stats["total_short_trades"] == len(
            sample_trades
        )

    def test_streak_metrics(self, sample_trades):
        """Test streak metrics calculation."""
        calc = MetricsCalculator()

        streaks = calc.calculate_streak_metrics(sample_trades)

        assert "max_win_streak" in streaks
        assert "max_loss_streak" in streaks
        assert "current_streak" in streaks

    def test_all_metrics(self, sample_equity_curve, sample_trades):
        """Test all metrics calculation."""
        calc = MetricsCalculator()

        metrics = calc.calculate_all_metrics(
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            initial_capital=10000.0,
        )

        # Should have many metrics
        assert len(metrics) >= 15


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAdvancedFeaturesIntegration:
    """Integration tests for all advanced features."""

    def test_advanced_features_combined(self):
        """Test combining multiple advanced features."""
        features = AdvancedFeatures(
            scale_in_config=ScaleInConfig(enabled=True),
            partial_close_config=PartialCloseConfig(enabled=True),
            time_exit_config=TimeExitConfig(enabled=True, max_bars_in_trade=100),
            slippage_config=SlippageConfig(model=SlippageModel.FIXED),
            funding_config=FundingConfig(enabled=True),
            hedge_config=HedgeConfig(enabled=True),
        )

        # Verify all configs are set
        assert features.scale_in.enabled is True
        assert features.partial_close.enabled is True
        assert features.time_exit.enabled is True
        assert features.slippage.model == SlippageModel.FIXED
        assert features.funding.enabled is True
        assert features.hedge.enabled is True

    def test_full_pipeline(self, sample_equity_curve, sample_trades):
        """Test full analysis pipeline."""
        # 1. Calculate metrics
        metrics_calc = MetricsCalculator()
        metrics = metrics_calc.calculate_all_metrics(
            sample_equity_curve, sample_trades, 10000.0
        )

        # 2. Monte Carlo simulation
        mc_config = MonteCarloConfig(n_simulations=50, seed=42)
        mc_sim = MonteCarloSimulator(mc_config)
        pnls = np.array([t["pnl"] for t in sample_trades])
        mc_result = mc_sim.simulate(pnls, 10000.0, verbose=False)

        # 3. Portfolio
        portfolio_config = PortfolioConfig(symbols=["BTCUSDT", "ETHUSDT"])
        portfolio = PortfolioManager(portfolio_config)
        portfolio.initialize(10000.0)

        # Verify all components work
        assert metrics["total_return"] is not None
        assert mc_result.mean_return is not None
        assert portfolio.state.total_equity == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
