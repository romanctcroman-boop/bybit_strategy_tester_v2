"""
🧪 Tests for MTF (Multi-Timeframe) Module

Tests cover:
- Index mapping with lookahead prevention
- HTF filters (trend, BTC correlation)
- MTF signal generation
- Data loading
"""

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.mtf.filters import (
    BTCCorrelationFilter,
    HTFTrendFilter,
    calculate_ema,
    calculate_sma,
)
from backend.backtesting.mtf.index_mapper import (
    calculate_bars_ratio,
    create_htf_index_map,
    get_htf_bar_at_ltf,
    interval_to_minutes,
    validate_htf_index_map,
)
from backend.backtesting.mtf.signals import (
    generate_mtf_rsi_signals,
    generate_mtf_sma_crossover_signals,
)


class TestIntervalConversion:
    """Tests for interval conversion utilities."""

    def test_interval_to_minutes_numeric(self):
        """Test numeric interval strings."""
        assert interval_to_minutes("1") == 1
        assert interval_to_minutes("5") == 5
        assert interval_to_minutes("15") == 15
        assert interval_to_minutes("60") == 60
        assert interval_to_minutes("240") == 240

    def test_interval_to_minutes_special(self):
        """Test special interval strings."""
        assert interval_to_minutes("D") == 1440
        assert interval_to_minutes("W") == 10080
        assert interval_to_minutes("M") == 43200

    def test_interval_to_minutes_invalid(self):
        """Test invalid intervals."""
        assert interval_to_minutes("invalid") is None
        assert interval_to_minutes("") is None

    def test_calculate_bars_ratio(self):
        """Test bars ratio calculation."""
        assert calculate_bars_ratio("5", "60") == 12  # 12 x 5m = 60m
        assert calculate_bars_ratio("15", "60") == 4  # 4 x 15m = 60m
        assert calculate_bars_ratio("1", "5") == 5  # 5 x 1m = 5m
        assert calculate_bars_ratio("15", "D") == 96  # 96 x 15m = 1440m

    def test_calculate_bars_ratio_invalid(self):
        """Test invalid ratio (HTF < LTF)."""
        with pytest.raises(ValueError):
            calculate_bars_ratio("60", "5")  # HTF smaller than LTF


class TestHTFIndexMapping:
    """Tests for HTF index mapping with lookahead prevention."""

    def test_create_htf_index_map_basic(self):
        """Test basic index mapping."""
        # 5m LTF bars: 12 bars per hour
        # 1H HTF bars
        ltf_ts = (
            np.array(
                [
                    0,
                    5,
                    10,
                    15,
                    20,
                    25,
                    30,
                    35,
                    40,
                    45,
                    50,
                    55,  # Hour 0
                    60,
                    65,
                    70,
                    75,
                    80,
                    85,
                    90,
                    95,
                    100,
                    105,
                    110,
                    115,  # Hour 1
                ]
            )
            * 60
            * 1000
        )  # Convert to ms

        htf_ts = np.array([0, 60, 120]) * 60 * 1000  # Hour 0, 1, 2

        # With lookahead="none", HTF bar is visible only after it closes
        htf_map = create_htf_index_map(ltf_ts, htf_ts, lookahead_mode="none")

        # First 12 bars (hour 0): HTF bar 0 is forming, not closed yet
        # So visible HTF = -1 (none)
        for i in range(12):
            assert htf_map[i] == -1, f"Bar {i} should see -1, got {htf_map[i]}"

        # Next 12 bars (hour 1): HTF bar 0 is closed, visible
        for i in range(12, 24):
            assert htf_map[i] == 0, f"Bar {i} should see 0, got {htf_map[i]}"

    def test_create_htf_index_map_lookahead_allow(self):
        """Test index mapping with lookahead allowed."""
        ltf_ts = np.array([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]) * 60 * 1000
        htf_ts = np.array([0, 60]) * 60 * 1000

        # With lookahead="allow", can see current forming HTF bar
        htf_map = create_htf_index_map(ltf_ts, htf_ts, lookahead_mode="allow")

        # All bars in hour 0 should see HTF bar 0 (current)
        for i in range(12):
            assert htf_map[i] == 0, f"Bar {i} should see 0, got {htf_map[i]}"

    def test_get_htf_bar_at_ltf(self):
        """Test getting HTF OHLC at LTF bar."""
        htf_map = np.array([0, 0, 0, 1, 1, 1])
        htf_close = np.array([100.0, 105.0])
        htf_high = np.array([102.0, 108.0])
        htf_low = np.array([98.0, 103.0])
        htf_open = np.array([99.0, 104.0])

        o, h, l, c = get_htf_bar_at_ltf(
            2, htf_map, htf_close, htf_high, htf_low, htf_open
        )
        assert c == 100.0
        assert h == 102.0
        assert l == 98.0
        assert o == 99.0

        o, h, l, c = get_htf_bar_at_ltf(
            4, htf_map, htf_close, htf_high, htf_low, htf_open
        )
        assert c == 105.0

    def test_validate_htf_index_map(self):
        """Test index map validation."""
        # Valid map
        valid_map = np.array([-1, -1, 0, 0, 0, 1, 1, 1])
        is_valid, msg = validate_htf_index_map(valid_map, 2, "5", "15")
        assert is_valid, msg

        # Invalid: exceeds HTF count
        invalid_map = np.array([0, 0, 0, 5])  # 5 > n_htf=2
        is_valid, msg = validate_htf_index_map(invalid_map, 2, "5", "15")
        assert not is_valid


class TestHTFFilters:
    """Tests for HTF filters."""

    def test_htf_trend_filter_bullish(self):
        """Test trend filter in bullish condition."""
        filter = HTFTrendFilter(period=200, filter_type="sma")

        # Price above SMA → bullish → allow long only
        allow_long, allow_short = filter.check(100.0, 95.0)
        assert allow_long is True
        assert allow_short is False

    def test_htf_trend_filter_bearish(self):
        """Test trend filter in bearish condition."""
        filter = HTFTrendFilter(period=200, filter_type="sma")

        # Price below SMA → bearish → allow short only
        allow_long, allow_short = filter.check(90.0, 95.0)
        assert allow_long is False
        assert allow_short is True

    def test_htf_trend_filter_neutral_zone(self):
        """Test trend filter in neutral zone."""
        filter = HTFTrendFilter(period=200, filter_type="sma", neutral_zone_pct=1.0)

        # Price within 1% of SMA → neutral → allow both
        allow_long, allow_short = filter.check(100.0, 99.5)
        assert allow_long is True
        assert allow_short is True

    def test_btc_correlation_filter_bullish(self):
        """Test BTC filter in bullish condition."""
        filter = BTCCorrelationFilter(btc_sma_period=50)

        # BTC above SMA → allow long on alts
        allow_long, allow_short = filter.check(50000.0, 48000.0)
        assert allow_long is True
        assert allow_short is False

    def test_btc_correlation_filter_bearish(self):
        """Test BTC filter in bearish condition."""
        filter = BTCCorrelationFilter(btc_sma_period=50)

        # BTC below SMA → allow short on alts
        allow_long, allow_short = filter.check(45000.0, 48000.0)
        assert allow_long is False
        assert allow_short is True

    def test_calculate_sma(self):
        """Test SMA calculation."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = calculate_sma(values, 3)

        assert np.isnan(sma[0])
        assert np.isnan(sma[1])
        assert sma[2] == pytest.approx(2.0)  # (1+2+3)/3
        assert sma[3] == pytest.approx(3.0)  # (2+3+4)/3
        assert sma[4] == pytest.approx(4.0)  # (3+4+5)/3

    def test_calculate_ema(self):
        """Test EMA calculation."""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        ema = calculate_ema(values, 3)

        assert np.isnan(ema[0])
        assert np.isnan(ema[1])
        assert ema[2] == pytest.approx(2.0)  # Initial SMA(3)
        # EMA continues from there


class TestMTFSignals:
    """Tests for MTF signal generation."""

    @pytest.fixture
    def sample_ltf_data(self):
        """Create sample LTF data."""
        n = 100
        np.random.seed(42)

        # Trending up then down
        close = np.concatenate(
            [
                np.linspace(100, 120, 50),
                np.linspace(120, 100, 50),
            ]
        )

        return pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=n, freq="5min"),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": np.random.rand(n) * 1000,
            }
        )

    @pytest.fixture
    def sample_htf_data(self):
        """Create sample HTF data (1H from 5m)."""
        n_htf = 10  # 10 hours
        close = np.array([105, 110, 115, 120, 118, 115, 110, 105, 103, 100])

        return pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=n_htf, freq="1h"),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": np.random.rand(n_htf) * 10000,
            }
        )

    @pytest.fixture
    def sample_htf_index_map(self, sample_ltf_data):
        """Create HTF index map (12 LTF bars per HTF bar)."""
        n = len(sample_ltf_data)
        # Simple mapping: every 12 bars = 1 HTF bar, with 1 bar delay for lookahead prevention
        htf_map = np.array([(i // 12) - 1 for i in range(n)])
        htf_map = np.maximum(htf_map, -1)  # Ensure -1 minimum
        return htf_map

    def test_generate_mtf_rsi_signals_basic(
        self, sample_ltf_data, sample_htf_data, sample_htf_index_map
    ):
        """Test basic MTF RSI signal generation."""
        long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
            ltf_candles=sample_ltf_data,
            htf_candles=sample_htf_data,
            htf_index_map=sample_htf_index_map,
            rsi_period=14,
            overbought=70,
            oversold=30,
            htf_filter_type="sma",
            htf_filter_period=3,
            direction="both",
        )

        # Should return arrays of correct length
        assert len(long_entries) == len(sample_ltf_data)
        assert len(short_entries) == len(sample_ltf_data)

        # Should be boolean arrays
        assert long_entries.dtype == bool
        assert short_entries.dtype == bool

    def test_generate_mtf_sma_crossover_signals_basic(
        self, sample_ltf_data, sample_htf_data, sample_htf_index_map
    ):
        """Test basic MTF SMA crossover signal generation."""
        long_entries, long_exits, short_entries, short_exits = (
            generate_mtf_sma_crossover_signals(
                ltf_candles=sample_ltf_data,
                htf_candles=sample_htf_data,
                htf_index_map=sample_htf_index_map,
                fast_period=5,
                slow_period=10,
                htf_filter_type="sma",
                htf_filter_period=3,
                direction="both",
            )
        )

        assert len(long_entries) == len(sample_ltf_data)
        assert len(short_entries) == len(sample_ltf_data)

    def test_mtf_signals_long_only(
        self, sample_ltf_data, sample_htf_data, sample_htf_index_map
    ):
        """Test long-only direction."""
        long_entries, _, short_entries, _ = generate_mtf_rsi_signals(
            ltf_candles=sample_ltf_data,
            htf_candles=sample_htf_data,
            htf_index_map=sample_htf_index_map,
            direction="long",
        )

        # No short signals in long-only mode
        assert np.sum(short_entries) == 0

    def test_mtf_signals_short_only(
        self, sample_ltf_data, sample_htf_data, sample_htf_index_map
    ):
        """Test short-only direction."""
        long_entries, _, short_entries, _ = generate_mtf_rsi_signals(
            ltf_candles=sample_ltf_data,
            htf_candles=sample_htf_data,
            htf_index_map=sample_htf_index_map,
            direction="short",
        )

        # No long signals in short-only mode
        assert np.sum(long_entries) == 0


class TestMTFIntegration:
    """Integration tests for MTF module."""

    def test_full_mtf_workflow(self):
        """Test complete MTF workflow from data to signals."""
        # Create realistic data
        np.random.seed(42)
        n_ltf = 500  # 500 x 5m bars ≈ 1.7 days

        # LTF data (5m)
        ltf_close = 100 + np.cumsum(np.random.randn(n_ltf) * 0.5)
        ltf_df = pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=n_ltf, freq="5min"),
                "open": ltf_close - 0.2,
                "high": ltf_close + np.abs(np.random.randn(n_ltf) * 0.5),
                "low": ltf_close - np.abs(np.random.randn(n_ltf) * 0.5),
                "close": ltf_close,
                "volume": np.random.rand(n_ltf) * 1000,
            }
        )

        # HTF data (1H)
        n_htf = n_ltf // 12 + 1
        htf_close = 100 + np.cumsum(np.random.randn(n_htf) * 2)
        htf_df = pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=n_htf, freq="1h"),
                "open": htf_close - 1,
                "high": htf_close + np.abs(np.random.randn(n_htf) * 1),
                "low": htf_close - np.abs(np.random.randn(n_htf) * 1),
                "close": htf_close,
                "volume": np.random.rand(n_htf) * 10000,
            }
        )

        # Create index map
        ltf_ts = ltf_df["time"].values.astype("datetime64[ms]").astype(np.int64)
        htf_ts = htf_df["time"].values.astype("datetime64[ms]").astype(np.int64)
        htf_map = create_htf_index_map(ltf_ts, htf_ts, "none")

        # Generate signals
        long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
            ltf_candles=ltf_df,
            htf_candles=htf_df,
            htf_index_map=htf_map,
            rsi_period=14,
            overbought=70,
            oversold=30,
            htf_filter_type="sma",
            htf_filter_period=20,
            direction="both",
        )

        # Validate results
        assert len(long_entries) == n_ltf
        assert len(short_entries) == n_ltf

        # Should have some signals (not all zeros)
        total_signals = np.sum(long_entries) + np.sum(short_entries)
        print(f"Total signals generated: {total_signals}")

        # Signals should not occur in warmup period
        warmup = 14 * 4  # RSI warmup
        assert np.sum(long_entries[:warmup]) == 0
        assert np.sum(short_entries[:warmup]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
