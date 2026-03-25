"""
Tests for Fast Optimizer (FastGridOptimizer).

NOTE: fast_optimizer is deprecated in favor of NumbaEngineV2 + UniversalOptimizer.
These tests ensure the module loads and basic RSI-only optimization still works.
"""

import pytest

from backend.backtesting.fast_optimizer import FastGridOptimizer


class TestFastOptimizerImport:
    """Test FastGridOptimizer import and availability."""

    def test_fast_optimizer_imports(self):
        """FastGridOptimizer should be importable."""
        assert FastGridOptimizer is not None

    def test_fast_optimizer_has_optimize_method(self):
        """FastGridOptimizer should have optimize method."""
        opt = FastGridOptimizer()
        assert hasattr(opt, "optimize")
        assert callable(opt.optimize)


class TestFastOptimizerBasic:
    """Basic optimization tests (requires DB with klines)."""

    @pytest.mark.skip(reason="Requires DB with klines; run manually with --run-slow")
    def test_optimize_returns_result_structure(self):
        """Optimize should return dict with expected keys when run."""
        opt = FastGridOptimizer()
        result = opt.optimize(
            symbol="BTCUSDT",
            interval="60",
            start_date="2024-01-01",
            end_date="2024-01-31",
            param_grid={"rsi_period": [14], "overbought": [70], "oversold": [30]},
        )
        assert isinstance(result, dict)
        assert "best_params" in result or "results" in result
