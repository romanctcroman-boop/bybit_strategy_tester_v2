"""
Tests for Universal Math Engine.

Тестирует основные модули и интеграцию.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

# Import main classes
from backend.backtesting.universal_engine import (
    UniversalFilterEngine,
    UniversalMathEngine,
    UniversalOptimizer,
    UniversalSignalGenerator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_candles():
    """Generate sample OHLCV data."""
    np.random.seed(42)
    n = 500

    # Generate trending price with noise
    trend = np.cumsum(np.random.randn(n) * 0.5)
    base = 50000 + trend * 100

    # Add realistic OHLCV structure
    opens = base + np.random.randn(n) * 50
    highs = opens + np.abs(np.random.randn(n) * 100)
    lows = opens - np.abs(np.random.randn(n) * 100)
    closes = lows + np.random.rand(n) * (highs - lows)
    volumes = np.random.exponential(1000, n)

    timestamps = [datetime(2024, 1, 1) + timedelta(minutes=15 * i) for i in range(n)]

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "timestamp": timestamps,
        }
    )

    return df


# =============================================================================
# SIGNAL GENERATOR TESTS
# =============================================================================


class TestSignalGenerator:
    """Tests for UniversalSignalGenerator."""

    def test_signal_generator_initialization(self):
        """Test SignalGenerator initialization."""
        gen = UniversalSignalGenerator()
        assert gen is not None

    def test_rsi_signals(self, sample_candles):
        """Test RSI signal generation via generate method."""
        gen = UniversalSignalGenerator()

        # Use correct API: strategy_params not params
        output = gen.generate(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            direction="both",
        )

        # SignalOutput has long_entries, long_exits, short_entries, short_exits
        assert len(output.long_entries) == len(sample_candles)
        assert len(output.short_entries) == len(sample_candles)
        assert output.long_entries.dtype == bool
        assert "rsi" in output.indicator_values

    def test_macd_signals(self, sample_candles):
        """Test MACD signal generation."""
        gen = UniversalSignalGenerator()

        output = gen.generate(
            candles=sample_candles,
            strategy_type="macd",
            strategy_params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            direction="both",
        )

        assert len(output.long_entries) == len(sample_candles)
        assert "macd" in output.indicator_values

    def test_bollinger_signals(self, sample_candles):
        """Test Bollinger Bands signal generation."""
        gen = UniversalSignalGenerator()

        output = gen.generate(
            candles=sample_candles,
            strategy_type="bollinger",
            strategy_params={"period": 20, "std_dev": 2.0},
            direction="both",
        )

        assert len(output.long_entries) == len(sample_candles)
        assert (
            "bb_upper" in output.indicator_values or "upper" in output.indicator_values
        )


# =============================================================================
# FILTER ENGINE TESTS
# =============================================================================


class TestFilterEngine:
    """Tests for UniversalFilterEngine."""

    def test_filter_engine_initialization(self):
        """Test FilterEngine initialization."""
        engine = UniversalFilterEngine()
        assert engine is not None


# =============================================================================
# UNIVERSAL MATH ENGINE TESTS
# =============================================================================


class TestUniversalMathEngine:
    """Tests for UniversalMathEngine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = UniversalMathEngine()
        assert engine is not None

    def test_run_rsi_backtest(self, sample_candles):
        """Test RSI backtest run."""
        engine = UniversalMathEngine()

        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            leverage=10,
        )

        assert result.is_valid
        assert result.metrics is not None
        assert result.metrics.total_trades >= 0
        assert len(result.equity_curve) == len(sample_candles)

    def test_run_macd_backtest(self, sample_candles):
        """Test MACD backtest run."""
        engine = UniversalMathEngine()

        result = engine.run(
            candles=sample_candles,
            strategy_type="macd",
            strategy_params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            initial_capital=10000,
            direction="long",
            stop_loss=0.02,
            take_profit=0.04,
            leverage=5,
        )

        assert result.is_valid

    def test_run_bollinger_backtest(self, sample_candles):
        """Test Bollinger backtest run."""
        engine = UniversalMathEngine()

        result = engine.run(
            candles=sample_candles,
            strategy_type="bollinger",
            strategy_params={"period": 20, "std_dev": 2.0},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            leverage=10,
        )

        assert result.is_valid

    def test_metrics_calculation(self, sample_candles):
        """Test that metrics are calculated correctly."""
        engine = UniversalMathEngine()

        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 21, "overbought": 75, "oversold": 25},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            leverage=10,
        )

        m = result.metrics

        # Basic metrics should be present
        assert hasattr(m, "total_trades")
        assert hasattr(m, "win_rate")
        assert hasattr(m, "profit_factor")
        assert hasattr(m, "sharpe_ratio")
        assert hasattr(m, "max_drawdown")

        # Win rate should be between 0 and 1
        assert 0 <= m.win_rate <= 1

        # Profit factor should be >= 0
        assert m.profit_factor >= 0

    def test_different_directions(self, sample_candles):
        """Test different trading directions."""
        engine = UniversalMathEngine()

        for direction in ["long", "short", "both"]:
            result = engine.run(
                candles=sample_candles,
                strategy_type="rsi",
                strategy_params={"period": 14, "overbought": 70, "oversold": 30},
                initial_capital=10000,
                direction=direction,
                stop_loss=0.02,
                take_profit=0.03,
                leverage=10,
            )

            assert result.is_valid, f"Direction {direction} failed"


# =============================================================================
# OPTIMIZER TESTS
# =============================================================================


class TestUniversalOptimizer:
    """Tests for UniversalOptimizer."""

    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        optimizer = UniversalOptimizer()
        assert optimizer is not None

    def test_grid_search(self, sample_candles):
        """Test grid search optimization."""
        optimizer = UniversalOptimizer()

        result = optimizer.optimize(
            candles=sample_candles,
            strategy_type="rsi",
            base_params={
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30}
            },
            param_ranges={
                "period": [10, 14, 21],
                "overbought": [70, 75],
                "oversold": [25, 30],
            },
            initial_capital=10000,
            direction="both",
            leverage=10,
            optimize_metric="sharpe_ratio",
            filters={"min_trades": 3},
            method="grid",
            top_n=5,
        )

        assert result.total_combinations == 3 * 2 * 2  # 12
        assert len(result.top_n_results) <= 5

    def test_random_search(self, sample_candles):
        """Test random search optimization."""
        optimizer = UniversalOptimizer()

        result = optimizer.optimize(
            candles=sample_candles,
            strategy_type="rsi",
            base_params={
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30}
            },
            param_ranges={
                "period": list(range(10, 31)),  # 21 values
                "overbought": list(range(65, 86)),  # 21 values
                "oversold": list(range(15, 36)),  # 21 values
            },
            initial_capital=10000,
            direction="both",
            leverage=10,
            optimize_metric="net_profit",
            method="random",
            max_combinations=50,
            top_n=5,
        )

        # Should sample up to 50
        assert result.completed_combinations <= 50

    def test_quick_optimize(self, sample_candles):
        """Test quick optimization helper."""
        optimizer = UniversalOptimizer()

        result = optimizer.quick_optimize(
            candles=sample_candles,
            strategy_type="rsi",
            direction="both",
            optimize_metric="sharpe_ratio",
        )

        assert result.total_combinations > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow(self, sample_candles):
        """Test complete workflow: backtest -> optimize."""
        # 1. Run single backtest
        engine = UniversalMathEngine()

        result = engine.run(
            candles=sample_candles,
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            initial_capital=10000,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            leverage=10,
        )

        assert result.is_valid

        # 2. Optimize
        optimizer = UniversalOptimizer(engine=engine)

        opt_result = optimizer.optimize(
            candles=sample_candles,
            strategy_type="rsi",
            base_params={"strategy_params": {}},
            param_ranges={
                "period": [10, 14, 21],
                "overbought": [70, 75],
                "oversold": [25, 30],
            },
            initial_capital=10000,
            direction="both",
            leverage=10,
            optimize_metric="sharpe_ratio",
            method="grid",
        )

        assert opt_result.completed_combinations > 0

    def test_different_strategies(self, sample_candles):
        """Test that different strategies work."""
        engine = UniversalMathEngine()

        strategies = [
            ("rsi", {"period": 14, "overbought": 70, "oversold": 30}),
            ("macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}),
            ("bollinger", {"period": 20, "std_dev": 2.0}),
        ]

        for strategy_type, params in strategies:
            result = engine.run(
                candles=sample_candles,
                strategy_type=strategy_type,
                strategy_params=params,
                initial_capital=10000,
                direction="both",
                stop_loss=0.02,
                take_profit=0.03,
                leverage=10,
            )

            assert result.is_valid, f"Strategy {strategy_type} failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
