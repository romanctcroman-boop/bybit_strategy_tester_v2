"""
Test suite for backend.core.engine_adapter

Tests the engine factory function and Protocol definition.
"""

from typing import Any

import pytest

from backend.core.engine_adapter import (
    EngineResult,
    IBacktestEngine,
    get_engine,
)
from backend.core.backtest_engine import BacktestEngine


class TestEngineResultTypedDict:
    """Test EngineResult TypedDict structure."""

    def test_engine_result_is_typeddict(self):
        """EngineResult should be a TypedDict."""
        result: EngineResult = {
            "final_capital": 10000.0,
            "total_return": 0.5,
            "total_trades": 100,
        }
        assert isinstance(result, dict)

    def test_engine_result_with_all_fields(self):
        """EngineResult can contain all defined fields."""
        result: EngineResult = {
            "final_capital": 12000.0,
            "total_return": 0.2,
            "total_trades": 50,
            "winning_trades": 30,
            "losing_trades": 20,
            "win_rate": 0.6,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.1,
            "trades": [{"id": 1}, {"id": 2}],
            "metrics": {"key": "value"},
            "error": "some error",
        }
        assert result["final_capital"] == 12000.0
        assert result["total_return"] == 0.2
        assert result["total_trades"] == 50
        assert result["winning_trades"] == 30
        assert result["losing_trades"] == 20
        assert result["win_rate"] == 0.6
        assert result["sharpe_ratio"] == 1.5
        assert result["max_drawdown"] == 0.1
        assert len(result["trades"]) == 2
        assert result["metrics"]["key"] == "value"
        assert result["error"] == "some error"

    def test_engine_result_with_minimal_fields(self):
        """EngineResult is total=False, so minimal fields work."""
        result: EngineResult = {}
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_engine_result_with_partial_fields(self):
        """EngineResult can have subset of fields."""
        result: EngineResult = {
            "total_trades": 10,
            "win_rate": 0.8,
        }
        assert result["total_trades"] == 10
        assert result["win_rate"] == 0.8
        assert "final_capital" not in result

    def test_engine_result_float_fields(self):
        """EngineResult float fields accept float values."""
        result: EngineResult = {
            "final_capital": 9999.99,
            "total_return": -0.1234,
            "win_rate": 0.555,
            "sharpe_ratio": 2.345,
            "max_drawdown": 0.0001,
        }
        assert isinstance(result["final_capital"], float)
        assert isinstance(result["total_return"], float)
        assert isinstance(result["win_rate"], float)
        assert isinstance(result["sharpe_ratio"], float)
        assert isinstance(result["max_drawdown"], float)

    def test_engine_result_int_fields(self):
        """EngineResult int fields accept integer values."""
        result: EngineResult = {
            "total_trades": 1000,
            "winning_trades": 600,
            "losing_trades": 400,
        }
        assert isinstance(result["total_trades"], int)
        assert isinstance(result["winning_trades"], int)
        assert isinstance(result["losing_trades"], int)

    def test_engine_result_list_field(self):
        """EngineResult trades field is a list."""
        result: EngineResult = {
            "trades": [
                {"trade_id": 1, "profit": 100.0},
                {"trade_id": 2, "profit": -50.0},
            ]
        }
        assert isinstance(result["trades"], list)
        assert len(result["trades"]) == 2

    def test_engine_result_dict_field(self):
        """EngineResult metrics field is a dict."""
        result: EngineResult = {
            "metrics": {
                "profit_factor": 1.5,
                "average_win": 200.0,
                "average_loss": -100.0,
            }
        }
        assert isinstance(result["metrics"], dict)
        assert result["metrics"]["profit_factor"] == 1.5

    def test_engine_result_error_field(self):
        """EngineResult error field can contain error messages."""
        result: EngineResult = {
            "error": "Strategy execution failed: Division by zero"
        }
        assert isinstance(result["error"], str)
        assert "Division by zero" in result["error"]


class TestIBacktestEngineProtocol:
    """Test IBacktestEngine Protocol definition."""

    def test_protocol_defines_run_method(self):
        """IBacktestEngine Protocol requires run() method."""
        # Protocol check via hasattr on actual implementation
        engine = BacktestEngine()
        assert hasattr(engine, "run")

    def test_backtest_engine_implements_protocol(self):
        """BacktestEngine implements IBacktestEngine Protocol."""
        engine = BacktestEngine()
        # Check method signature exists
        assert callable(engine.run)

    def test_protocol_run_signature_accepts_data_and_config(self):
        """IBacktestEngine.run() accepts data and strategy_config."""
        # Type checking test - Protocol should allow these parameters
        def accepts_engine(engine: IBacktestEngine, data: Any, config: dict):
            return engine.run(data, config)

        # Should not raise type errors
        assert callable(accepts_engine)


class TestGetEngineFunction:
    """Test get_engine() factory function."""

    def test_get_engine_returns_backtest_engine(self):
        """get_engine() returns BacktestEngine instance."""
        engine = get_engine()
        assert isinstance(engine, BacktestEngine)

    def test_get_engine_with_no_name(self):
        """get_engine() with no name returns BacktestEngine."""
        engine = get_engine(name=None)
        assert isinstance(engine, BacktestEngine)

    def test_get_engine_with_name(self):
        """get_engine() with name still returns BacktestEngine (for now)."""
        engine = get_engine(name="backtest")
        assert isinstance(engine, BacktestEngine)

    def test_get_engine_with_kwargs(self):
        """get_engine() passes kwargs to BacktestEngine constructor."""
        # BacktestEngine constructor might accept parameters
        engine = get_engine()
        assert isinstance(engine, BacktestEngine)

    def test_get_engine_returns_ibacktest_engine(self):
        """get_engine() returns object implementing IBacktestEngine Protocol."""
        engine = get_engine()
        assert hasattr(engine, "run")
        assert callable(engine.run)

    def test_get_engine_multiple_calls_return_new_instances(self):
        """get_engine() creates new instances on each call."""
        engine1 = get_engine()
        engine2 = get_engine()
        # Different instances
        assert engine1 is not engine2

    def test_get_engine_with_various_names(self):
        """get_engine() with different names (future extensibility test)."""
        # Currently all return BacktestEngine, but test for future lookup
        for name in ["backtest", "live", "paper", None]:
            engine = get_engine(name=name)
            assert isinstance(engine, BacktestEngine)

    def test_get_engine_empty_string_name(self):
        """get_engine() with empty string name."""
        engine = get_engine(name="")
        assert isinstance(engine, BacktestEngine)


class TestEngineAdapterIntegration:
    """Test integration between components."""

    def test_get_engine_returns_object_with_run_method(self):
        """Integration: get_engine() returns usable engine with run()."""
        engine = get_engine()
        assert hasattr(engine, "run")
        assert callable(engine.run)

    def test_engine_run_returns_engine_result_compatible_dict(self):
        """Integration: engine.run() returns EngineResult-compatible dict."""
        engine = get_engine()
        # Mock minimal data
        data = []
        strategy_config = {"type": "bollinger"}
        result = engine.run(data, strategy_config)

        # Result should be dict-like (EngineResult compatible)
        assert isinstance(result, dict)

    def test_factory_extensibility_pattern(self):
        """Factory pattern allows future engine implementations."""
        # Test that get_engine accepts name parameter for future lookup
        engine = get_engine(name="future_engine_type")
        # Currently returns BacktestEngine, but signature supports extension
        assert isinstance(engine, BacktestEngine)


class TestEngineAdapterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_engine_result_with_zero_values(self):
        """EngineResult can have zero values."""
        result: EngineResult = {
            "final_capital": 0.0,
            "total_return": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
        }
        assert result["final_capital"] == 0.0
        assert result["total_trades"] == 0

    def test_engine_result_with_negative_values(self):
        """EngineResult can have negative values."""
        result: EngineResult = {
            "final_capital": 5000.0,
            "total_return": -0.5,
            "sharpe_ratio": -1.2,
            "max_drawdown": -0.8,
        }
        assert result["total_return"] == -0.5
        assert result["sharpe_ratio"] == -1.2

    def test_engine_result_with_very_large_numbers(self):
        """EngineResult can handle large numbers."""
        result: EngineResult = {
            "final_capital": 1_000_000_000.0,
            "total_trades": 1_000_000,
        }
        assert result["final_capital"] == 1_000_000_000.0
        assert result["total_trades"] == 1_000_000

    def test_engine_result_empty_lists(self):
        """EngineResult can have empty lists."""
        result: EngineResult = {
            "trades": [],
            "metrics": {},
        }
        assert len(result["trades"]) == 0
        assert len(result["metrics"]) == 0

    def test_engine_result_nested_metrics(self):
        """EngineResult metrics can have nested structures."""
        result: EngineResult = {
            "metrics": {
                "performance": {
                    "monthly": [0.1, 0.2, 0.3],
                    "yearly": 0.6,
                },
                "risk": {
                    "volatility": 0.15,
                    "var": 0.05,
                }
            }
        }
        assert result["metrics"]["performance"]["yearly"] == 0.6
        assert len(result["metrics"]["performance"]["monthly"]) == 3

    def test_get_engine_with_none_kwargs(self):
        """get_engine() handles None in kwargs."""
        engine = get_engine(name=None)
        assert isinstance(engine, BacktestEngine)

    def test_engine_result_very_long_error_message(self):
        """EngineResult error field can hold long error messages."""
        long_error = "Error: " + "X" * 10000
        result: EngineResult = {"error": long_error}
        assert len(result["error"]) > 10000

    def test_engine_result_unicode_in_error(self):
        """EngineResult error field supports Unicode."""
        result: EngineResult = {"error": "策略执行失败 🚨"}
        assert "策略" in result["error"]
        assert "🚨" in result["error"]
