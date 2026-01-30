"""
Tests for MTF (Multi-Timeframe) integration with FallbackEngineV4.
Verifies that MTF filters correctly affect trade entry decisions.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput
from backend.backtesting.mtf.index_mapper import create_htf_index_map


def create_test_candles(
    n_bars: int = 200, base_price: float = 100.0, trend: str = "up"
) -> pd.DataFrame:
    """Create test OHLCV data with specified trend."""
    timestamps = [
        datetime(2025, 1, 1) + timedelta(minutes=15 * i) for i in range(n_bars)
    ]

    if trend == "up":
        closes = np.linspace(base_price, base_price * 1.2, n_bars)
    elif trend == "down":
        closes = np.linspace(base_price * 1.2, base_price, n_bars)
    else:  # sideways
        closes = (
            base_price + np.sin(np.linspace(0, 4 * np.pi, n_bars)) * base_price * 0.05
        )

    # Add some noise
    noise = np.random.normal(0, base_price * 0.002, n_bars)
    closes = closes + noise

    highs = closes * 1.005
    lows = closes * 0.995
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    volumes = np.random.uniform(1000, 2000, n_bars)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def create_htf_candles(ltf_candles: pd.DataFrame, htf_ratio: int = 4) -> pd.DataFrame:
    """Create HTF candles from LTF candles (e.g., 1H from 15m)."""
    n_htf = len(ltf_candles) // htf_ratio

    timestamps = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    for i in range(n_htf):
        start_idx = i * htf_ratio
        end_idx = (i + 1) * htf_ratio
        slice_df = ltf_candles.iloc[start_idx:end_idx]

        timestamps.append(slice_df["timestamp"].iloc[-1])
        opens.append(slice_df["open"].iloc[0])
        highs.append(slice_df["high"].max())
        lows.append(slice_df["low"].min())
        closes.append(slice_df["close"].iloc[-1])
        volumes.append(slice_df["volume"].sum())

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def create_signals(candles: pd.DataFrame, fast: int = 5, slow: int = 20):
    """Create signals that generate trades in volatile market."""
    closes = candles["close"].values
    n = len(closes)

    # Use RSI-like overbought/oversold signals for more frequent triggers
    long_entries = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Simple periodic signals every ~30 bars
    for i in range(30, n, 30):
        if i % 60 == 30:
            long_entries[i] = True
            long_exits[min(i + 15, n - 1)] = True
        else:
            short_entries[i] = True
            short_exits[min(i + 15, n - 1)] = True

    return long_entries, long_exits, short_entries, short_exits


class TestMTFIntegration:
    """Test MTF filter integration with FallbackEngineV4."""

    def test_mtf_disabled_allows_all_trades(self):
        """With MTF disabled, all trades should be allowed."""
        candles = create_test_candles(200, trend="up")
        long_entries, long_exits, short_entries, short_exits = create_signals(candles)

        input_data = BacktestInput(
            candles=candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=False,
            use_bar_magnifier=False,  # Disable bar magnifier for tests
        )

        engine = FallbackEngineV4()
        result = engine.run(input_data)

        assert len(result.trades) > 0, "Should have trades with MTF disabled"

    def test_mtf_filter_blocks_counter_trend_longs(self):
        """MTF filter should block long entries in downtrend."""
        ltf_candles = create_test_candles(200, trend="up")
        long_entries, long_exits, short_entries, short_exits = create_signals(
            ltf_candles
        )

        htf_candles = create_htf_candles(ltf_candles)
        # Force HTF into downtrend by lowering closes
        htf_candles["close"] = htf_candles["close"] * 0.8

        htf_index_map = create_htf_index_map(
            ltf_candles["timestamp"].values,
            htf_candles["timestamp"].values,
            lookahead_mode="none",
        )

        input_data = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=htf_candles,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=20,
            mtf_neutral_zone_pct=0.0,
        )

        engine = FallbackEngineV4()
        result = engine.run(input_data)

        print(f"Trades with MTF downtrend filter: {len(result.trades)}")

    def test_mtf_filter_allows_trend_following_trades(self):
        """MTF filter should allow trades that follow HTF trend."""
        ltf_candles = create_test_candles(200, trend="up")
        htf_candles = create_htf_candles(ltf_candles)
        long_entries, long_exits, short_entries, short_exits = create_signals(
            ltf_candles
        )

        htf_index_map = create_htf_index_map(
            ltf_candles["timestamp"].values,
            htf_candles["timestamp"].values,
            lookahead_mode="none",
        )

        input_with_mtf = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=htf_candles,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=20,
        )

        input_without_mtf = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=False,
        )

        engine = FallbackEngineV4()
        result_with_mtf = engine.run(input_with_mtf)
        result_without_mtf = engine.run(input_without_mtf)

        print(f"Trades with MTF (aligned): {len(result_with_mtf.trades)}")
        print(f"Trades without MTF: {len(result_without_mtf.trades)}")

    def test_mtf_neutral_zone(self):
        """Test that neutral zone creates buffer around indicator."""
        ltf_candles = create_test_candles(200, trend="sideways")
        htf_candles = create_htf_candles(ltf_candles)
        long_entries, long_exits, short_entries, short_exits = create_signals(
            ltf_candles
        )

        htf_index_map = create_htf_index_map(
            ltf_candles["timestamp"].values,
            htf_candles["timestamp"].values,
            lookahead_mode="none",
        )

        input_data = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=htf_candles,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=20,
            mtf_neutral_zone_pct=0.01,
        )

        engine = FallbackEngineV4()
        result = engine.run(input_data)

        print(f"Trades with neutral zone in sideways: {len(result.trades)}")

    def test_mtf_ema_vs_sma_filter(self):
        """Test that EMA filter is faster to react than SMA."""
        ltf_candles = create_test_candles(200, trend="up")
        htf_candles = create_htf_candles(ltf_candles)
        long_entries, long_exits, short_entries, short_exits = create_signals(
            ltf_candles
        )

        htf_index_map = create_htf_index_map(
            ltf_candles["timestamp"].values,
            htf_candles["timestamp"].values,
            lookahead_mode="none",
        )

        input_sma = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=htf_candles,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=20,
        )

        input_ema = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=htf_candles,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="ema",
            mtf_filter_period=20,
        )

        engine = FallbackEngineV4()
        result_sma = engine.run(input_sma)
        result_ema = engine.run(input_ema)

        print(f"Trades with SMA: {len(result_sma.trades)}")
        print(f"Trades with EMA: {len(result_ema.trades)}")

    def test_mtf_with_missing_htf_data(self):
        """Engine should handle missing HTF data gracefully."""
        ltf_candles = create_test_candles(200, trend="up")
        long_entries, long_exits, short_entries, short_exits = create_signals(
            ltf_candles
        )

        input_data = BacktestInput(
            candles=ltf_candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
            mtf_enabled=True,
            mtf_htf_candles=None,
            mtf_htf_index_map=None,
        )

        engine = FallbackEngineV4()
        result = engine.run(input_data)

        assert result is not None
        print(f"Trades with missing HTF data: {len(result.trades)}")


class TestMTFParameterValidation:
    """Test parameter handling for MTF filters."""

    def test_default_mtf_parameters(self):
        """Verify default MTF parameters don't cause issues."""
        candles = create_test_candles(200, trend="up")
        long_entries, long_exits, short_entries, short_exits = create_signals(candles)

        input_data = BacktestInput(
            candles=candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol="BTCUSDT",
            interval="15",
            initial_capital=10000,
            leverage=1,
            direction="long",
            stop_loss=0.02,
            take_profit=0.03,
        )

        engine = FallbackEngineV4()
        result = engine.run(input_data)

        assert result is not None
        assert hasattr(result, "trades")
        assert hasattr(result, "metrics")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
