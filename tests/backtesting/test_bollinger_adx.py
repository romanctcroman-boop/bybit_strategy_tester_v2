"""
Test Bollinger Bands and ADX filters.
"""

import numpy as np
import pytest

from backend.backtesting.mtf.filters import (
    ADXFilter,
    BollingerFilter,
    calculate_adx,
    calculate_bandwidth,
    calculate_bollinger_bands,
)


class TestBollingerBands:
    """Tests for Bollinger Bands calculations and filter."""

    def test_calculate_bollinger_bands_basic(self):
        """Test basic BB calculation."""
        # Generate trending data
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)

        middle, upper, lower = calculate_bollinger_bands(close, period=20, std_dev=2.0)

        # Check dimensions
        assert len(middle) == len(close)
        assert len(upper) == len(close)
        assert len(lower) == len(close)

        # Check NaN for warm-up period
        assert np.all(np.isnan(middle[:19]))
        assert not np.isnan(middle[19])

        # Upper should be above middle, lower below
        valid_idx = 25
        assert upper[valid_idx] > middle[valid_idx]
        assert lower[valid_idx] < middle[valid_idx]

    def test_calculate_bandwidth(self):
        """Test bandwidth calculation."""
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)

        middle, upper, lower = calculate_bollinger_bands(close, period=20, std_dev=2.0)
        bandwidth = calculate_bandwidth(middle, upper, lower)

        # Bandwidth should be positive
        valid_bw = bandwidth[~np.isnan(bandwidth)]
        assert np.all(valid_bw >= 0)

    def test_bollinger_filter_mean_reversion(self):
        """Test mean reversion mode."""
        filter = BollingerFilter(period=20, std_dev=2.0, mode="mean_reversion")

        # Price at lower band -> allow LONG
        allow_long, allow_short = filter.check(
            htf_close=95.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is True
        assert allow_short is False

        # Price at upper band -> allow SHORT
        allow_long, allow_short = filter.check(
            htf_close=110.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is False
        assert allow_short is True

        # Price in middle -> allow both
        allow_long, allow_short = filter.check(
            htf_close=102.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is True
        assert allow_short is True

    def test_bollinger_filter_breakout(self):
        """Test breakout mode."""
        filter = BollingerFilter(period=20, std_dev=2.0, mode="breakout")

        # Price above upper -> breakout LONG
        allow_long, allow_short = filter.check(
            htf_close=112.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is True
        assert allow_short is False

        # Price below lower -> breakout SHORT
        allow_long, allow_short = filter.check(
            htf_close=93.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is False
        assert allow_short is True

        # Price inside bands -> no signals
        allow_long, allow_short = filter.check(
            htf_close=102.0, htf_indicator=0, upper=110.0, lower=95.0, middle=102.5
        )
        assert allow_long is False
        assert allow_short is False

    def test_bollinger_filter_squeeze(self):
        """Test squeeze mode."""
        filter = BollingerFilter(
            period=20, std_dev=2.0, mode="squeeze", bandwidth_threshold=4.0
        )

        # Squeeze (low bandwidth) + above middle -> LONG
        allow_long, allow_short = filter.check(
            htf_close=103.0,
            htf_indicator=0,
            upper=105.0,
            lower=100.0,
            middle=102.5,
            bandwidth=3.0,  # Below threshold
        )
        assert allow_long is True
        assert allow_short is False

        # No squeeze (high bandwidth) -> no signals
        allow_long, allow_short = filter.check(
            htf_close=103.0,
            htf_indicator=0,
            upper=110.0,
            lower=95.0,
            middle=102.5,
            bandwidth=10.0,  # Above threshold
        )
        assert allow_long is False
        assert allow_short is False


class TestADX:
    """Tests for ADX calculations and filter."""

    def test_calculate_adx_basic(self):
        """Test basic ADX calculation."""
        np.random.seed(42)
        n = 100
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)

        adx, plus_di, minus_di = calculate_adx(high, low, close, period=14)

        # Check dimensions
        assert len(adx) == n
        assert len(plus_di) == n
        assert len(minus_di) == n

        # ADX and DI should be positive (0-100 range)
        valid_adx = adx[~np.isnan(adx)]
        assert np.all(valid_adx >= 0)
        assert np.all(valid_adx <= 100)

    def test_adx_trending_market(self):
        """Test ADX in trending market."""
        # Create strong uptrend
        n = 100
        close = 100 + np.arange(n) * 0.5  # Steady uptrend
        high = close + 0.2
        low = close - 0.2

        adx, plus_di, minus_di = calculate_adx(high, low, close, period=14)

        # In uptrend, +DI should be > -DI at the end
        assert plus_di[-1] > minus_di[-1]
        # ADX should be elevated
        assert adx[-1] > 15

    def test_adx_filter_combined_mode(self):
        """Test ADX filter in combined mode."""
        filter = ADXFilter(period=14, threshold=25, mode="combined")

        # Strong uptrend -> LONG only
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=35.0, plus_di=30.0, minus_di=15.0
        )
        assert allow_long is True
        assert allow_short is False

        # Strong downtrend -> SHORT only
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=35.0, plus_di=15.0, minus_di=30.0
        )
        assert allow_long is False
        assert allow_short is True

        # Weak ADX -> no signals
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=20.0, plus_di=30.0, minus_di=15.0
        )
        assert allow_long is False
        assert allow_short is False

    def test_adx_filter_direction_mode(self):
        """Test ADX filter in direction-only mode."""
        filter = ADXFilter(period=14, threshold=25, mode="direction")

        # Uptrend (ignore ADX level)
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=15.0, plus_di=30.0, minus_di=15.0
        )
        assert allow_long is True
        assert allow_short is False

    def test_adx_filter_trend_only_mode(self):
        """Test ADX filter in trend-only mode."""
        filter = ADXFilter(period=14, threshold=25, mode="trend_only")

        # Strong trend -> allow both
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=35.0, plus_di=25.0, minus_di=20.0
        )
        assert allow_long is True
        assert allow_short is True

        # Weak trend -> no signals
        allow_long, allow_short = filter.check(
            htf_close=0, htf_indicator=0, adx=15.0, plus_di=25.0, minus_di=20.0
        )
        assert allow_long is False
        assert allow_short is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
