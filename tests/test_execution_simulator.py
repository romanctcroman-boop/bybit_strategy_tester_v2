"""Tests for ExecutionSimulator."""


from backend.backtesting.execution_simulator import (
    ExecutionSimulator,
    FillResult,
    FillStatus,
)


class TestExecutionSimulator:
    """Tests for ExecutionSimulator."""

    def test_simulate_fill_basic(self):
        """Simulate fill returns valid FillResult."""
        sim = ExecutionSimulator(seed=42)
        fill = sim.simulate_fill(order_price=50000.0, side="buy", size=0.1)
        assert isinstance(fill, FillResult)
        assert fill.status in (FillStatus.FILLED, FillStatus.PARTIAL, FillStatus.REJECTED)
        assert fill.fill_price >= 0
        assert 0 <= fill.fill_size <= 0.1

    def test_slippage_direction(self):
        """Buy orders have positive slippage, sell have negative."""
        sim = ExecutionSimulator(
            slippage_bps=100,
            seed=42,
            rejection_probability=0,
            fill_probability=1.0,
        )
        buy_fill = sim.simulate_fill(50000.0, "buy", 0.1)
        sell_fill = sim.simulate_fill(50000.0, "sell", 0.1)
        assert buy_fill.fill_price >= 50000.0
        assert sell_fill.fill_price <= 50000.0

    def test_reproducibility_with_seed(self):
        """Same seed produces same results."""
        sim1 = ExecutionSimulator(seed=123)
        sim2 = ExecutionSimulator(seed=123)
        f1 = sim1.simulate_fill(100.0, "buy", 1.0)
        f2 = sim2.simulate_fill(100.0, "buy", 1.0)
        assert f1.fill_price == f2.fill_price
        assert f1.fill_size == f2.fill_size
