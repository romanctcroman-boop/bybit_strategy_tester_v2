"""
Tests for RSI indicator

Coverage target: 0% → 70%+
"""

import numpy as np
import pandas as pd
import pytest

from backend.indicators.rsi import calculate_rsi, get_rsi_signal


class TestCalculateRSI:
    """Test RSI calculation."""

    def test_rsi_with_minimal_data(self):
        """Test RSI with insufficient data (less than period)."""
        df = pd.DataFrame({
            'close': [100, 101, 102, 103, 104],
        })
        
        rsi = calculate_rsi(df, period=14)
        
        # Should return neutral RSI (50) for all bars
        assert len(rsi) == 5
        assert all(val == 50.0 for val in rsi)

    def test_rsi_uptrend(self):
        """Test RSI with consistent uptrend."""
        # Strong uptrend should produce high RSI
        prices = [100 + i * 2 for i in range(30)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Later values in uptrend should have high RSI (>60)
        assert len(rsi) == 30
        assert rsi.iloc[-1] > 60.0

    def test_rsi_downtrend(self):
        """Test RSI with consistent downtrend."""
        # Strong downtrend should produce low RSI
        prices = [200 - i * 2 for i in range(30)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Later values in downtrend should have low RSI (<40)
        assert len(rsi) == 30
        assert rsi.iloc[-1] < 40.0

    def test_rsi_range_0_to_100(self):
        """Test that RSI values are always between 0 and 100."""
        # Create random price data
        np.random.seed(42)
        prices = [100 + np.random.randn() * 10 for _ in range(50)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # All RSI values should be between 0 and 100
        assert all(0 <= val <= 100 for val in rsi)

    def test_rsi_neutral_market(self):
        """Test RSI with sideways market (neutral RSI ~50)."""
        # Sideways market should have RSI around 50
        np.random.seed(42)
        prices = [100 + np.random.randn() * 2 for _ in range(50)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Average RSI should be close to neutral (40-60 range)
        avg_rsi = rsi.iloc[20:].mean()
        assert 40 < avg_rsi < 60

    def test_rsi_with_custom_period(self):
        """Test RSI with different period lengths."""
        # Create more varied price data to avoid all gains
        np.random.seed(42)
        prices = [100 + i + np.random.randn() * 3 for i in range(50)]
        df = pd.DataFrame({'close': prices})
        
        rsi_7 = calculate_rsi(df, period=7)
        rsi_14 = calculate_rsi(df, period=14)
        rsi_21 = calculate_rsi(df, period=21)
        
        # All RSI calculations should complete and return values
        assert len(rsi_7) == 50
        assert len(rsi_14) == 50
        assert len(rsi_21) == 50
        
        # Shorter periods are more responsive to changes
        # Check that we have valid RSI values
        assert all(0 <= val <= 100 for val in rsi_7.iloc[10:])
        assert all(0 <= val <= 100 for val in rsi_14.iloc[15:])
        assert all(0 <= val <= 100 for val in rsi_21.iloc[22:])

    def test_rsi_with_custom_price_column(self):
        """Test RSI using different price column."""
        np.random.seed(42)
        # Create different price patterns for close vs open
        df = pd.DataFrame({
            'close': [100 + i + np.random.randn() * 2 for i in range(30)],
            'open': [99 + i + np.random.randn() * 3 for i in range(30)],
        })
        
        rsi_close = calculate_rsi(df, period=14, price_col='close')
        rsi_open = calculate_rsi(df, period=14, price_col='open')
        
        # Should calculate based on different columns
        assert len(rsi_close) == 30
        assert len(rsi_open) == 30
        
        # Both should produce valid RSI values
        assert all(0 <= val <= 100 for val in rsi_close)
        assert all(0 <= val <= 100 for val in rsi_open)

    def test_rsi_extreme_gains(self):
        """Test RSI with only gains (should approach 100)."""
        # Consistent gains should push RSI toward 100
        prices = [100 + i for i in range(30)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # RSI should be very high
        assert rsi.iloc[-1] > 80.0

    def test_rsi_extreme_losses(self):
        """Test RSI with only losses (should approach 0)."""
        # Consistent losses should push RSI toward 0
        prices = [150 - i for i in range(30)]
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # RSI should be very low
        assert rsi.iloc[-1] < 20.0

    def test_rsi_index_preservation(self):
        """Test that RSI preserves DataFrame index."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 2 for i in range(30)]
        }, index=dates)
        
        rsi = calculate_rsi(df, period=14)
        
        # Index should be preserved
        assert list(rsi.index) == list(df.index)


class TestGetRSISignal:
    """Test RSI signal generation."""

    def test_signal_oversold(self):
        """Test oversold signal."""
        assert get_rsi_signal(25.0) == 'OVERSOLD'
        assert get_rsi_signal(30.0) == 'OVERSOLD'
        assert get_rsi_signal(10.0) == 'OVERSOLD'

    def test_signal_overbought(self):
        """Test overbought signal."""
        assert get_rsi_signal(75.0) == 'OVERBOUGHT'
        assert get_rsi_signal(70.0) == 'OVERBOUGHT'
        assert get_rsi_signal(90.0) == 'OVERBOUGHT'

    def test_signal_neutral(self):
        """Test neutral signal."""
        assert get_rsi_signal(50.0) == 'NEUTRAL'
        assert get_rsi_signal(40.0) == 'NEUTRAL'
        assert get_rsi_signal(60.0) == 'NEUTRAL'

    def test_signal_custom_thresholds(self):
        """Test with custom oversold/overbought thresholds."""
        assert get_rsi_signal(25.0, oversold=20.0, overbought=80.0) == 'NEUTRAL'
        assert get_rsi_signal(15.0, oversold=20.0, overbought=80.0) == 'OVERSOLD'
        assert get_rsi_signal(85.0, oversold=20.0, overbought=80.0) == 'OVERBOUGHT'

    def test_signal_boundary_values(self):
        """Test signal at exact threshold boundaries."""
        # At exact threshold should be included in that zone
        assert get_rsi_signal(30.0) == 'OVERSOLD'
        assert get_rsi_signal(70.0) == 'OVERBOUGHT'
        
        # Just above/below thresholds
        assert get_rsi_signal(30.1) == 'NEUTRAL'
        assert get_rsi_signal(29.9) == 'OVERSOLD'
        assert get_rsi_signal(69.9) == 'NEUTRAL'
        assert get_rsi_signal(70.1) == 'OVERBOUGHT'


class TestRSISelfTest:
    """Test the self-test function in rsi.py."""

    def test_rsi_self_test_execution(self):
        """Test that test_rsi() executes successfully."""
        from backend.indicators.rsi import test_rsi
        
        # Should execute without errors
        test_rsi()
        # If we get here, test_rsi() completed successfully
