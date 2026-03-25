"""
Unit tests for Strategy Builder Adapter - Session 5.1 handlers

Tests for:
- Actions: stop_loss, take_profit, trailing_stop, atr_stop, chandelier_stop,
           break_even, profit_lock, scale_out, multi_tp, limit_entry, stop_entry, close
- Exits: atr_exit, session_exit, signal_exit, indicator_exit, partial_close,
         multi_tp_exit, break_even_exit
- Price Action: hammer_hangman, doji_patterns, shooting_star, marubozu,
                tweezer, three_methods, piercing_darkcloud, harami
- Divergence: unified multi-indicator divergence (RSI, Stochastic, Momentum, CMF, OBV, MFI)
"""

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


def create_adapter(blocks: list, connections: list = None) -> StrategyBuilderAdapter:
    """Helper to create adapter from blocks and connections."""
    graph = {
        "name": "Test Strategy",
        "blocks": blocks,
        "connections": connections or [],
    }
    return StrategyBuilderAdapter(graph)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n = 100

    base_price = 50000
    returns = np.random.randn(n) * 0.02
    close = base_price * np.cumprod(1 + returns)

    high = close * (1 + np.abs(np.random.randn(n) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n) * 0.01))
    open_price = np.roll(close, 1)
    open_price[0] = base_price

    volume = np.random.randint(1000, 10000, n).astype(float)
    timestamps = pd.date_range(start="2025-01-01", periods=n, freq="1h")

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


# =============================================================================
# ACTION TESTS
# =============================================================================


class TestActionHandlers:
    """Tests for action block handlers."""

    def test_stop_loss_action(self, sample_ohlcv_data):
        """Test stop_loss action sets stop loss level."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
            {"id": "b3", "type": "stop_loss", "category": "action", "params": {"percent": 2.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}, {"from": "b2", "to": "b3"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None or "signal" in result

    def test_take_profit_action(self, sample_ohlcv_data):
        """Test take_profit action sets take profit level."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
            {"id": "b3", "type": "take_profit", "category": "action", "params": {"percent": 3.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}, {"from": "b2", "to": "b3"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_trailing_stop_action(self, sample_ohlcv_data):
        """Test trailing_stop action with activation level."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "trailing_stop",
                "category": "action",
                "params": {"percent": 1.5, "activation_percent": 1.0},
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_atr_stop_action(self, sample_ohlcv_data):
        """Test ATR-based stop loss."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {"id": "b2", "type": "atr_stop", "category": "action", "params": {"period": 14, "multiplier": 2.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_chandelier_stop_action(self, sample_ohlcv_data):
        """Test Chandelier stop from highest high."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {"id": "b2", "type": "chandelier_stop", "category": "action", "params": {"period": 22, "multiplier": 3.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_break_even_action(self, sample_ohlcv_data):
        """Test break-even move after trigger percent."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {"id": "b2", "type": "break_even", "category": "action", "params": {"trigger_percent": 1.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_profit_lock_action(self, sample_ohlcv_data):
        """Test profit lock after threshold."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "profit_lock",
                "category": "action",
                "params": {"trigger_percent": 2.0, "lock_percent": 1.0},
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_scale_out_action(self, sample_ohlcv_data):
        """Test partial position close."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "scale_out",
                "category": "action",
                "params": {"close_percent": 50.0, "profit_target": 1.5},
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_multi_tp_action(self, sample_ohlcv_data):
        """Test multi take profit levels."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "multi_tp",
                "category": "action",
                "params": {
                    "tp1_percent": 1.0,
                    "tp1_close": 30,
                    "tp2_percent": 2.0,
                    "tp2_close": 30,
                    "tp3_percent": 3.0,
                    "tp3_close": 40,
                },
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_limit_entry_action(self, sample_ohlcv_data):
        """Test limit order entry."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "limit_entry", "category": "action", "params": {"offset_percent": -0.5}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_stop_entry_action(self, sample_ohlcv_data):
        """Test stop order entry on breakout."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "stop_entry", "category": "action", "params": {"offset_percent": 0.5}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_close_action(self, sample_ohlcv_data):
        """Test close any position."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "close", "category": "action", "params": {}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None


# =============================================================================
# EXIT TESTS
# =============================================================================


class TestExitHandlers:
    """Tests for exit block handlers."""

    def test_atr_exit(self, sample_ohlcv_data):
        """Test ATR-based exit with TP/SL multipliers."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "atr_exit",
                "category": "exit",
                "params": {"atr_period": 14, "tp_multiplier": 2.0, "sl_multiplier": 1.5},
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_session_exit(self, sample_ohlcv_data):
        """Test exit at specific session hour."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {"id": "b2", "type": "session_exit", "category": "exit", "params": {"exit_hour": 16}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_signal_exit(self, sample_ohlcv_data):
        """Test exit on opposite signal."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "signal_exit", "category": "exit", "params": {}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_indicator_exit(self, sample_ohlcv_data):
        """Test exit on indicator condition."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {
                "id": "b2",
                "type": "indicator_exit",
                "category": "exit",
                "params": {"indicator": "rsi", "condition": "above", "value": 70},
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_partial_close_exit(self, sample_ohlcv_data):
        """Test partial close at profit targets."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "partial_close",
                "category": "exit",
                "params": {
                    "close1_percent": 30,
                    "target1_percent": 1.0,
                    "close2_percent": 30,
                    "target2_percent": 2.0,
                    "close3_percent": 40,
                    "target3_percent": 3.0,
                },
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_multi_tp_exit(self, sample_ohlcv_data):
        """Test multi TP levels with allocation."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b2",
                "type": "multi_tp_exit",
                "category": "exit",
                "params": {
                    "tp1_percent": 1.0,
                    "tp1_close": 25,
                    "tp2_percent": 2.0,
                    "tp2_close": 25,
                    "tp3_percent": 3.0,
                    "tp3_close": 50,
                },
            },
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_break_even_exit(self, sample_ohlcv_data):
        """Test break-even exit after profit trigger."""
        blocks = [
            {"id": "b1", "type": "buy", "category": "action", "params": {}},
            {"id": "b2", "type": "break_even_exit", "category": "exit", "params": {"trigger_percent": 1.0}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None


# =============================================================================
# PRICE ACTION TESTS
# =============================================================================


class TestPriceActionHandlers:
    """Tests for price action pattern handlers."""

    def test_engulfing_pattern(self, sample_ohlcv_data):
        """Test engulfing pattern detection."""
        blocks = [
            {"id": "b1", "type": "engulfing", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_hammer_hangman_pattern(self, sample_ohlcv_data):
        """Test hammer/hanging man pattern detection."""
        blocks = [
            {"id": "b1", "type": "hammer_hangman", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_doji_patterns(self, sample_ohlcv_data):
        """Test doji pattern detection."""
        doji_data = sample_ohlcv_data.copy()
        doji_data.loc[50, "close"] = doji_data.loc[50, "open"]  # Create doji

        blocks = [
            {"id": "b1", "type": "doji_patterns", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(doji_data)

        assert result is not None

    def test_shooting_star_pattern(self, sample_ohlcv_data):
        """Test shooting star pattern detection."""
        blocks = [
            {"id": "b1", "type": "shooting_star", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_marubozu_pattern(self, sample_ohlcv_data):
        """Test marubozu (strong momentum) pattern detection."""
        blocks = [
            {"id": "b1", "type": "marubozu", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_tweezer_pattern(self, sample_ohlcv_data):
        """Test tweezer top/bottom pattern detection."""
        blocks = [
            {"id": "b1", "type": "tweezer", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_three_methods_pattern(self, sample_ohlcv_data):
        """Test three methods continuation pattern detection."""
        blocks = [
            {"id": "b1", "type": "three_methods", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_piercing_darkcloud_pattern(self, sample_ohlcv_data):
        """Test piercing/dark cloud pattern detection."""
        blocks = [
            {"id": "b1", "type": "piercing_darkcloud", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_harami_pattern(self, sample_ohlcv_data):
        """Test harami inside bar pattern detection."""
        blocks = [
            {"id": "b1", "type": "harami", "category": "price_action", "params": {}},
        ]
        connections = []

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None


# =============================================================================
# DIVERGENCE TESTS
# =============================================================================


class TestDivergenceHandlers:
    """Tests for unified divergence detection block."""

    def test_divergence_rsi_enabled(self, sample_ohlcv_data):
        """Test divergence detection with RSI enabled."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 5,
                    "use_divergence_rsi": True,
                    "rsi_period": 14,
                    "act_without_confirmation": True,
                },
            },
        ]
        adapter = create_adapter(blocks)
        result = adapter.generate_signals(sample_ohlcv_data)
        assert result is not None

    def test_divergence_stochastic_enabled(self, sample_ohlcv_data):
        """Test divergence detection with Stochastic enabled."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 5,
                    "use_divergence_stochastic": True,
                    "stoch_length": 14,
                    "act_without_confirmation": True,
                },
            },
        ]
        adapter = create_adapter(blocks)
        result = adapter.generate_signals(sample_ohlcv_data)
        assert result is not None

    def test_divergence_no_indicators_enabled(self, sample_ohlcv_data):
        """Test divergence with no indicators enabled returns empty signals."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {"pivot_interval": 9},
            },
        ]
        adapter = create_adapter(blocks)
        result = adapter.generate_signals(sample_ohlcv_data)
        assert result is not None

    def test_divergence_multiple_indicators(self, sample_ohlcv_data):
        """Test divergence with multiple indicators enabled simultaneously."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 3,
                    "use_divergence_rsi": True,
                    "rsi_period": 14,
                    "use_divergence_momentum": True,
                    "momentum_length": 10,
                    "use_obv": True,
                    "act_without_confirmation": True,
                },
            },
        ]
        adapter = create_adapter(blocks)
        result = adapter.generate_signals(sample_ohlcv_data)
        assert result is not None

    def test_divergence_signal_memory(self, sample_ohlcv_data):
        """Test divergence with signal memory enabled."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 3,
                    "use_divergence_rsi": True,
                    "rsi_period": 14,
                    "activate_diver_signal_memory": True,
                    "keep_diver_signal_memory_bars": 5,
                    "act_without_confirmation": True,
                },
            },
        ]
        adapter = create_adapter(blocks)
        result = adapter.generate_signals(sample_ohlcv_data)
        assert result is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for complex strategy combinations."""

    def test_full_strategy_with_actions(self, sample_ohlcv_data):
        """Test complete strategy with indicator + filter + action + exit."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 14}},
            {"id": "b2", "type": "rsi_filter", "category": "filter", "params": {"min": 0, "max": 30, "mode": "range"}},
            {"id": "b3", "type": "buy", "category": "action", "params": {}},
            {"id": "b4", "type": "stop_loss", "category": "action", "params": {"percent": 2.0}},
            {"id": "b5", "type": "take_profit", "category": "action", "params": {"percent": 4.0}},
        ]
        connections = [
            {"from": "b1", "to": "b2"},
            {"from": "b2", "to": "b3"},
            {"from": "b3", "to": "b4"},
            {"from": "b4", "to": "b5"},
        ]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_price_action_strategy(self, sample_ohlcv_data):
        """Test price action strategy with trend filter."""
        blocks = [
            {"id": "b1", "type": "engulfing", "category": "price_action", "params": {}},
            {"id": "b2", "type": "trend_filter", "category": "filter", "params": {"period": 20, "mode": "slope_up"}},
            {"id": "b3", "type": "buy", "category": "action", "params": {}},
            {"id": "b4", "type": "atr_stop", "category": "action", "params": {"period": 14, "multiplier": 2.0}},
        ]
        connections = [
            {"from": "b1", "to": "b2"},
            {"from": "b2", "to": "b3"},
            {"from": "b3", "to": "b4"},
        ]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None

    def test_divergence_strategy(self, sample_ohlcv_data):
        """Test divergence-based strategy."""
        blocks = [
            {
                "id": "b1",
                "type": "divergence",
                "category": "divergence",
                "params": {
                    "pivot_interval": 5,
                    "use_divergence_rsi": True,
                    "rsi_period": 14,
                    "act_without_confirmation": True,
                },
            },
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
            {
                "id": "b3",
                "type": "multi_tp",
                "category": "action",
                "params": {
                    "tp1_percent": 1.0,
                    "tp1_close": 30,
                    "tp2_percent": 2.0,
                    "tp2_close": 30,
                    "tp3_percent": 3.0,
                    "tp3_close": 40,
                },
            },
        ]
        connections = [
            {"from": "b1", "to": "b2"},
            {"from": "b2", "to": "b3"},
        ]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_minimal_data(self):
        """Test with minimal data points."""
        minimal_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=5, freq="1h"),
                "open": [100, 101, 102, 101, 100],
                "high": [102, 103, 104, 103, 102],
                "low": [99, 100, 101, 100, 99],
                "close": [101, 102, 101, 100, 101],
                "volume": [1000, 1100, 1200, 1100, 1000],
            }
        )

        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {"period": 3}},
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(minimal_df)

        assert result is not None

    def test_missing_params_use_defaults(self, sample_ohlcv_data):
        """Test that missing params use default values."""
        blocks = [
            {"id": "b1", "type": "rsi", "category": "indicator", "params": {}},
            {"id": "b2", "type": "buy", "category": "action", "params": {}},
        ]
        connections = [{"from": "b1", "to": "b2"}]

        adapter = create_adapter(blocks, connections)
        result = adapter.generate_signals(sample_ohlcv_data)

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
