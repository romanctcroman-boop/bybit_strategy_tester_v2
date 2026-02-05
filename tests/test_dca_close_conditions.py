"""
Tests for DCA Engine Close Conditions (Session 5.5).

Tests:
- RSI Close
- Stochastic Close
- Channel Close
- MA Close
- PSAR Close
- Time/Bars Close
- Indent Order
"""

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.engines.dca_engine import (
    CloseConditionsConfig,
    DCAEngine,
    IndentOrderConfig,
    PendingIndentOrder,
)


@pytest.fixture
def sample_df():
    """Create sample OHLCV DataFrame."""
    np.random.seed(42)
    n = 200

    close = 100 + np.cumsum(np.random.randn(n) * 0.5)

    df = pd.DataFrame({
        'open': close - 0.2,
        'high': close + np.abs(np.random.randn(n) * 0.5),
        'low': close - np.abs(np.random.randn(n) * 0.5),
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    })

    return df


class TestCloseConditionsConfig:
    """Tests for CloseConditionsConfig dataclass."""

    def test_default_values(self):
        """Test default config values."""
        config = CloseConditionsConfig()

        assert config.rsi_close_enable is False
        assert config.rsi_close_length == 14
        assert config.stoch_close_enable is False
        assert config.channel_close_enable is False
        assert config.ma_close_enable is False
        assert config.psar_close_enable is False
        assert config.time_bars_close_enable is False

    def test_custom_values(self):
        """Test custom config values."""
        config = CloseConditionsConfig(
            rsi_close_enable=True,
            rsi_close_length=21,
            rsi_close_min_profit=1.0,
            stoch_close_enable=True,
        )

        assert config.rsi_close_enable is True
        assert config.rsi_close_length == 21
        assert config.rsi_close_min_profit == 1.0
        assert config.stoch_close_enable is True


class TestIndentOrderConfig:
    """Tests for IndentOrderConfig dataclass."""

    def test_default_values(self):
        """Test default indent order config."""
        config = IndentOrderConfig()

        assert config.enabled is False
        assert config.indent_percent == 0.1
        assert config.cancel_after_bars == 10

    def test_pending_indent_order(self):
        """Test PendingIndentOrder dataclass."""
        order = PendingIndentOrder(
            direction="long",
            signal_bar=10,
            signal_price=100.0,
            entry_price=99.9,
            expires_bar=20,
        )

        assert order.direction == "long"
        assert order.signal_price == 100.0
        assert order.entry_price == 99.9
        assert order.filled is False


class TestDCAEngineIndicatorCalculations:
    """Tests for DCAEngine indicator calculations."""

    def test_calculate_rsi(self, sample_df):
        """Test RSI calculation in DCAEngine."""
        engine = DCAEngine()
        close = sample_df['close'].values

        rsi = engine._calculate_rsi(close, 14)

        assert len(rsi) == len(close)
        # RSI should be between 0 and 100
        assert np.all(rsi >= 0)
        assert np.all(rsi <= 100)

    def test_calculate_stochastic(self, sample_df):
        """Test Stochastic calculation in DCAEngine."""
        engine = DCAEngine()
        high = sample_df['high'].values
        low = sample_df['low'].values
        close = sample_df['close'].values

        stoch_k, stoch_d = engine._calculate_stochastic(high, low, close, 14, 1, 3)

        assert len(stoch_k) == len(close)
        assert len(stoch_d) == len(close)

    def test_calculate_bollinger(self, sample_df):
        """Test Bollinger Bands calculation."""
        engine = DCAEngine()
        close = sample_df['close'].values

        upper, lower = engine._calculate_bollinger(close, 20, 2.0)

        assert len(upper) == len(close)
        assert len(lower) == len(close)
        # Upper should be above lower
        valid_idx = 25  # After warmup
        assert upper[valid_idx] > lower[valid_idx]

    def test_calculate_keltner(self, sample_df):
        """Test Keltner Channel calculation."""
        engine = DCAEngine()
        high = sample_df['high'].values
        low = sample_df['low'].values
        close = sample_df['close'].values

        upper, lower = engine._calculate_keltner(high, low, close, 20, 2.0)

        assert len(upper) == len(close)
        assert len(lower) == len(close)

    def test_calculate_psar(self, sample_df):
        """Test Parabolic SAR calculation."""
        engine = DCAEngine()
        high = sample_df['high'].values
        low = sample_df['low'].values

        psar = engine._calculate_psar(high, low, 0.02, 0.02, 0.2)

        assert len(psar) == len(high)

    def test_calculate_ma_sma(self, sample_df):
        """Test SMA calculation."""
        engine = DCAEngine()
        close = sample_df['close'].values

        ma = engine._calculate_ma(close, 20, "SMA")

        assert len(ma) == len(close)

    def test_calculate_ma_ema(self, sample_df):
        """Test EMA calculation."""
        engine = DCAEngine()
        close = sample_df['close'].values

        ma = engine._calculate_ma(close, 20, "EMA")

        assert len(ma) == len(close)

    def test_calculate_ma_wma(self, sample_df):
        """Test WMA calculation."""
        engine = DCAEngine()
        close = sample_df['close'].values

        ma = engine._calculate_ma(close, 20, "WMA")

        assert len(ma) == len(close)


class TestDCAEngineCloseConditionChecks:
    """Tests for close condition check methods."""

    def test_check_rsi_close_no_trigger(self, sample_df):
        """Test RSI close when condition not met."""
        engine = DCAEngine()
        engine.close_conditions = CloseConditionsConfig(
            rsi_close_enable=True,
            rsi_close_only_profit=False,
            rsi_close_reach_enable=True,
            rsi_close_reach_long_more=95,  # Very high threshold
        )

        # Set up caches
        engine._precompute_close_condition_indicators(sample_df)

        # Set up position
        engine.position.direction = "long"
        engine.position.unrealized_pnl_percent = 1.0

        result = engine._check_rsi_close(50, 1.0)

        # Should not trigger with normal RSI
        assert result is False

    def test_check_time_bars_close(self):
        """Test time/bars close condition."""
        engine = DCAEngine()
        engine.close_conditions = CloseConditionsConfig(
            time_bars_close_enable=True,
            close_after_bars=10,
            close_only_profit=True,
            close_min_profit=0.5,
        )

        # Set up position
        engine.position.entry_bar = 0
        engine.position.unrealized_pnl_percent = 1.0

        # Check at bar 15 (after close_after_bars)
        result = engine._check_close_conditions(15, 100.0)

        from backend.backtesting.engines.dca_engine import ExitReason
        assert result == ExitReason.TIME_EXIT


class TestIndentOrderLogic:
    """Tests for Indent Order functionality."""

    def test_create_indent_order_long(self):
        """Test creating a long indent order."""
        engine = DCAEngine()
        engine.indent_order = IndentOrderConfig(
            enabled=True,
            indent_percent=0.5,
            cancel_after_bars=10,
        )

        engine._create_indent_order(bar_index=5, price=100.0, direction="long")

        assert engine.pending_indent is not None
        assert engine.pending_indent.direction == "long"
        assert engine.pending_indent.signal_price == 100.0
        assert engine.pending_indent.entry_price == 99.5  # 100 * (1 - 0.5%)
        assert engine.pending_indent.expires_bar == 15  # 5 + 10

    def test_create_indent_order_short(self):
        """Test creating a short indent order."""
        engine = DCAEngine()
        engine.indent_order = IndentOrderConfig(
            enabled=True,
            indent_percent=0.5,
            cancel_after_bars=10,
        )

        engine._create_indent_order(bar_index=5, price=100.0, direction="short")

        assert engine.pending_indent is not None
        assert engine.pending_indent.direction == "short"
        assert abs(engine.pending_indent.entry_price - 100.5) < 0.0001  # 100 * (1 + 0.5%)

    def test_check_indent_order_expired(self):
        """Test indent order expiration."""
        engine = DCAEngine()
        engine.pending_indent = PendingIndentOrder(
            direction="long",
            signal_bar=5,
            signal_price=100.0,
            entry_price=99.5,
            expires_bar=15,
        )

        # Check at bar 20 (expired)
        result = engine._check_indent_order_fill(20, 100.0, 99.0, 99.5, 10000.0)

        # Order should be cancelled
        assert engine.pending_indent is None
        assert result == 10000.0  # Equity unchanged


class TestDCAEngineIntegration:
    """Integration tests for DCAEngine with close conditions."""

    def test_precompute_close_condition_indicators(self, sample_df):
        """Test indicator precomputation."""
        engine = DCAEngine()
        engine.close_conditions = CloseConditionsConfig(
            rsi_close_enable=True,
            stoch_close_enable=True,
            ma_close_enable=True,
            channel_close_enable=True,
            channel_close_type="Bollinger",
            psar_close_enable=True,
        )

        engine._precompute_close_condition_indicators(sample_df)

        # Check caches are populated
        assert engine._rsi_cache is not None
        assert len(engine._rsi_cache) == len(sample_df)

        assert engine._stoch_k_cache is not None
        assert engine._stoch_d_cache is not None

        assert engine._ma1_cache is not None
        assert engine._ma2_cache is not None

        assert engine._bb_upper_cache is not None
        assert engine._bb_lower_cache is not None

        assert engine._psar_cache is not None
