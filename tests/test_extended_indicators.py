"""
Tests for Extended Indicators (Session 5.5).

Tests:
- RVI (Relative Volatility Index)
- Linear Regression Channel
- Levels Break (S/R)
- Accumulation Areas
"""

import numpy as np
import pytest

from backend.core.indicators.extended_indicators import (
    calculate_rvi,
    calculate_linear_regression_channel,
    find_pivot_points,
    levels_break_filter,
    find_accumulation_areas,
    linear_regression_filter,
)


class TestRVI:
    """Tests for Relative Volatility Index."""

    def test_rvi_basic(self):
        """Test basic RVI calculation."""
        # Generate sample data
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)
        high = close + np.abs(np.random.randn(100) * 0.3)
        low = close - np.abs(np.random.randn(100) * 0.3)

        rvi = calculate_rvi(close, high, low, length=10, ma_type="EMA", ma_length=14)

        assert len(rvi) == len(close)
        assert np.all(rvi >= 0)
        assert np.all(rvi <= 100)

    def test_rvi_uptrend(self):
        """Test RVI in uptrend - should be above 50."""
        close = np.linspace(100, 120, 100)  # Strong uptrend
        high = close + 0.5
        low = close - 0.5

        rvi = calculate_rvi(close, high, low, length=10, ma_type="EMA", ma_length=14)

        # Last values should be above 50 in uptrend
        assert np.mean(rvi[-20:]) > 50

    def test_rvi_downtrend(self):
        """Test RVI in downtrend - should be below 50."""
        close = np.linspace(120, 100, 100)  # Strong downtrend
        high = close + 0.5
        low = close - 0.5

        rvi = calculate_rvi(close, high, low, length=10, ma_type="EMA", ma_length=14)

        # Last values should be below 50 in downtrend
        assert np.mean(rvi[-20:]) < 50

    def test_rvi_different_ma_types(self):
        """Test RVI with different MA types."""
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)
        high = close + np.abs(np.random.randn(100) * 0.3)
        low = close - np.abs(np.random.randn(100) * 0.3)

        for ma_type in ["WMA", "RMA", "SMA", "EMA"]:
            rvi = calculate_rvi(close, high, low, length=10, ma_type=ma_type, ma_length=14)
            assert len(rvi) == len(close)
            assert np.all(rvi >= 0)
            assert np.all(rvi <= 100)


class TestLinearRegressionChannel:
    """Tests for Linear Regression Channel."""

    def test_linreg_basic(self):
        """Test basic linear regression channel calculation."""
        close = np.linspace(100, 110, 150)  # Simple uptrend

        middle, upper, lower, slope = calculate_linear_regression_channel(
            close, length=100, deviation=2.0
        )

        assert len(middle) == len(close)
        assert len(upper) == len(close)
        assert len(lower) == len(close)
        assert len(slope) == len(close)

        # In valid range, upper should be above middle, lower should be below
        valid_idx = 100
        assert upper[valid_idx] > middle[valid_idx]
        assert lower[valid_idx] < middle[valid_idx]

    def test_linreg_uptrend_positive_slope(self):
        """Test that uptrend produces positive slope."""
        close = np.linspace(100, 120, 150)

        middle, upper, lower, slope = calculate_linear_regression_channel(
            close, length=100, deviation=2.0
        )

        # Slope should be positive in uptrend
        assert slope[-1] > 0

    def test_linreg_downtrend_negative_slope(self):
        """Test that downtrend produces negative slope."""
        close = np.linspace(120, 100, 150)

        middle, upper, lower, slope = calculate_linear_regression_channel(
            close, length=100, deviation=2.0
        )

        # Slope should be negative in downtrend
        assert slope[-1] < 0

    def test_linreg_filter(self):
        """Test linear regression filter."""
        close = np.linspace(100, 120, 150)
        close[-10:] = 125  # Breakout above channel

        config = {
            'linreg_length': 100,
            'channel_mult': 2.0,
            'linreg_breakout_rebound': 'Breakout',
            'linreg_slope_direction': 'Allow_Any',
        }

        long_signals, short_signals = linear_regression_filter(close, config)

        # Should have some long signals after breakout
        assert np.any(long_signals[-10:])


class TestPivotPoints:
    """Tests for Pivot Points detection."""

    def test_find_pivots_basic(self):
        """Test basic pivot point detection."""
        # Create data with clear pivots
        high = np.array([10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 12, 11])
        low = np.array([9, 10, 11, 10, 9, 8, 9, 10, 11, 12, 11, 10])
        close = np.array([9.5, 10.5, 11.5, 10.5, 9.5, 8.5, 9.5, 10.5, 11.5, 12.5, 11.5, 10.5])

        pivot_highs, pivot_lows = find_pivot_points(high, low, close, pivot_bars=2)

        assert len(pivot_highs) == len(high)
        assert len(pivot_lows) == len(low)

    def test_levels_break_filter(self):
        """Test levels break filter."""
        np.random.seed(42)
        n = 200
        
        # Create price data with S/R levels
        base_price = 100 + np.cumsum(np.random.randn(n) * 0.3)
        high = base_price + np.abs(np.random.randn(n) * 0.5)
        low = base_price - np.abs(np.random.randn(n) * 0.5)
        close = base_price

        config = {
            'levels_pivot_bars': 5,
            'levels_search_period': 50,
            'levels_channel_width': 0.5,
            'levels_test_count': 2,
        }

        long_signals, short_signals = levels_break_filter(high, low, close, config)

        assert len(long_signals) == n
        assert len(short_signals) == n


class TestAccumulationAreas:
    """Tests for Accumulation Areas detection."""

    def test_accumulation_basic(self):
        """Test basic accumulation detection."""
        n = 200
        
        # Create consolidation followed by breakout
        close = np.full(n, 100.0)
        close[-20:] = 105  # Breakout
        
        volume = np.full(n, 1000.0)
        volume[80:120] = 3000  # High volume during consolidation

        config = {
            'acc_backtrack_interval': 50,
            'acc_min_bars': 3,
            'volume_threshold': 2.0,
            'price_range_percent': 1.0,
        }

        long_signals, short_signals = find_accumulation_areas(close, volume, config)

        assert len(long_signals) == n
        assert len(short_signals) == n


class TestMTFUtils:
    """Tests for Multi-Timeframe utilities."""

    def test_mtf_supertrend(self):
        """Test MTF SuperTrend calculation."""
        from backend.core.indicators.mtf_utils import calculate_supertrend_mtf

        np.random.seed(42)
        n = 200
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)

        supertrend, direction = calculate_supertrend_mtf(high, low, close, period=10, multiplier=3.0)

        assert len(supertrend) == n
        assert len(direction) == n
        assert np.all(np.isin(direction, [-1, 1]))

    def test_mtf_rsi(self):
        """Test MTF RSI calculation."""
        from backend.core.indicators.mtf_utils import calculate_rsi_mtf

        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)

        rsi = calculate_rsi_mtf(close, period=14)

        assert len(rsi) == len(close)
        # RSI should be between 0 and 100
        assert np.all(rsi >= 0)
        assert np.all(rsi <= 100)
