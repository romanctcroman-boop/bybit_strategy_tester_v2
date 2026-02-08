"""
Tests for Walk-Forward Optimization Service.
"""

from datetime import UTC

import pytest

from backend.services.walk_forward import (
    WalkForwardOptimizer,
    WalkForwardResult,
    WalkForwardWindow,
    get_walk_forward_optimizer,
)


def simple_strategy_runner(
    candles: list, params: dict, initial_capital: float = 10000.0
) -> dict:
    """Simple test strategy runner."""
    if not candles:
        return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

    # Simple moving average crossover simulation
    returns = []
    for i in range(1, len(candles)):
        change = (
            candles[i].get("close", 100) - candles[i - 1].get("close", 100)
        ) / candles[i - 1].get("close", 100)
        returns.append(change)

    total_return = sum(returns) if returns else 0
    sharpe = total_return / (max(0.01, abs(total_return)) + 0.001) if returns else 0

    return {
        "return": total_return,
        "sharpe": sharpe,
        "max_drawdown": abs(min(returns)) if returns else 0,
        "trades": len(candles) // 10,
    }


class TestWalkForwardWindow:
    """Test cases for WalkForwardWindow dataclass."""

    def test_window_to_dict(self):
        """Test window serialization."""
        from datetime import datetime

        window = WalkForwardWindow(
            window_id=1,
            train_start=datetime(2024, 1, 1, tzinfo=UTC),
            train_end=datetime(2024, 3, 1, tzinfo=UTC),
            test_start=datetime(2024, 3, 1, tzinfo=UTC),
            test_end=datetime(2024, 4, 1, tzinfo=UTC),
            train_return=0.15,
            test_return=0.08,
            train_sharpe=1.5,
            test_sharpe=0.8,
        )

        data = window.to_dict()

        assert data["window_id"] == 1
        assert "train_period" in data
        assert "test_period" in data
        assert "train_metrics" in data
        assert "test_metrics" in data


class TestWalkForwardResult:
    """Test cases for WalkForwardResult dataclass."""

    def test_result_to_dict(self):
        """Test result serialization."""
        result = WalkForwardResult(
            n_splits=5,
            train_ratio=0.7,
            windows=[],
            avg_train_return=0.1,
            avg_test_return=0.05,
            consistency_ratio=0.8,
            overfit_score=0.2,
        )

        data = result.to_dict()

        assert data["config"]["n_splits"] == 5
        assert data["config"]["train_ratio"] == 0.7
        assert "aggregate_metrics" in data
        assert "robustness" in data
        assert "recommendation" in data


class TestWalkForwardOptimizer:
    """Test cases for WalkForwardOptimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance for testing."""
        return WalkForwardOptimizer(n_splits=3, train_ratio=0.7)

    @pytest.fixture
    def sample_candles(self):
        """Create sample candle data for walk-forward."""
        candles = []
        base_price = 100
        for i in range(100):
            change = (i % 5 - 2) * 0.5
            close = base_price + change
            candles.append(
                {
                    "open_time": f"2024-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z",
                    "open": base_price,
                    "high": max(base_price, close) + 1,
                    "low": min(base_price, close) - 1,
                    "close": close,
                    "volume": 1000 + i * 10,
                }
            )
            base_price = close
        return candles

    @pytest.fixture
    def param_grid(self):
        """Sample parameter grid."""
        return {
            "threshold": [0.01, 0.02, 0.03],
        }

    def test_optimizer_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.n_splits == 3
        assert optimizer.train_ratio == 0.7
        assert optimizer.gap_periods == 0

    def test_run_optimization(self, optimizer, sample_candles, param_grid):
        """Test running walk-forward optimization."""
        result = optimizer.optimize(
            data=sample_candles,
            param_grid=param_grid,
            strategy_runner=simple_strategy_runner,
        )

        assert result is not None
        assert isinstance(result, WalkForwardResult)
        assert result.n_splits == 3
        assert len(result.windows) == 3

    def test_aggregate_metrics(self, optimizer, sample_candles, param_grid):
        """Test aggregate metrics calculation."""
        result = optimizer.optimize(
            data=sample_candles,
            param_grid=param_grid,
            strategy_runner=simple_strategy_runner,
        )

        assert hasattr(result, "avg_train_return")
        assert hasattr(result, "avg_test_return")
        assert hasattr(result, "consistency_ratio")
        assert hasattr(result, "overfit_score")

    def test_to_dict(self, optimizer, sample_candles, param_grid):
        """Test result serialization."""
        result = optimizer.optimize(
            data=sample_candles,
            param_grid=param_grid,
            strategy_runner=simple_strategy_runner,
        )

        data = result.to_dict()

        assert "config" in data
        assert "aggregate_metrics" in data
        assert "robustness" in data
        assert "windows" in data

    def test_small_data(self, optimizer, param_grid):
        """Test with small data set raises error."""
        small_candles = [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 100}
            for _ in range(20)
        ]

        # Should raise ValueError with insufficient data
        with pytest.raises(ValueError, match="Insufficient data"):
            optimizer.optimize(
                data=small_candles,
                param_grid=param_grid,
                strategy_runner=simple_strategy_runner,
            )


class TestGlobalOptimizer:
    """Test global optimizer instance."""

    def test_get_walk_forward_optimizer(self):
        """Test getting global optimizer instance."""
        opt1 = get_walk_forward_optimizer()
        opt2 = get_walk_forward_optimizer()

        assert opt1 is opt2  # Same instance
        assert isinstance(opt1, WalkForwardOptimizer)
