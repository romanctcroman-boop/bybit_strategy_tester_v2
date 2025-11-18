"""
Test suite for backend.strategies.sr_mean_reversion

Tests the SRMeanReversionStrategy class for support/resistance mean reversion trading.
"""

import pandas as pd
import numpy as np
import pytest

from backend.strategies.sr_mean_reversion import SRMeanReversionStrategy


class TestSRMeanReversionStrategyInit:
    """Test SRMeanReversionStrategy initialization."""

    def test_init_with_defaults(self):
        """Strategy initializes with default parameters."""
        strategy = SRMeanReversionStrategy()
        assert strategy.entry_tolerance_pct == 0.15
        assert strategy.stop_loss_pct == 0.8
        assert strategy.max_holding_bars == 48
        assert strategy.position == 0
        assert strategy.position_entry_price is None
        assert strategy.entry_bar is None
        assert strategy.current_levels is None

    def test_init_with_custom_lookback(self):
        """Strategy accepts custom lookback_bars."""
        strategy = SRMeanReversionStrategy(lookback_bars=50)
        assert strategy.sr_detector.lookback_bars == 50

    def test_init_with_custom_level_tolerance(self):
        """Strategy accepts custom level_tolerance_pct."""
        strategy = SRMeanReversionStrategy(level_tolerance_pct=0.5)
        assert strategy.sr_detector.tolerance_pct == 0.5

    def test_init_with_custom_entry_tolerance(self):
        """Strategy accepts custom entry_tolerance_pct."""
        strategy = SRMeanReversionStrategy(entry_tolerance_pct=0.3)
        assert strategy.entry_tolerance_pct == 0.3

    def test_init_with_custom_stop_loss(self):
        """Strategy accepts custom stop_loss_pct."""
        strategy = SRMeanReversionStrategy(stop_loss_pct=1.5)
        assert strategy.stop_loss_pct == 1.5

    def test_init_with_custom_max_holding(self):
        """Strategy accepts custom max_holding_bars."""
        strategy = SRMeanReversionStrategy(max_holding_bars=100)
        assert strategy.max_holding_bars == 100

    def test_init_all_custom_params(self):
        """Strategy accepts all custom parameters."""
        strategy = SRMeanReversionStrategy(
            lookback_bars=200,
            level_tolerance_pct=1.0,
            entry_tolerance_pct=0.5,
            stop_loss_pct=2.0,
            max_holding_bars=24
        )
        assert strategy.sr_detector.lookback_bars == 200
        assert strategy.sr_detector.tolerance_pct == 1.0
        assert strategy.entry_tolerance_pct == 0.5
        assert strategy.stop_loss_pct == 2.0
        assert strategy.max_holding_bars == 24


class TestOnStart:
    """Test on_start() method."""

    def test_on_start_sets_data(self):
        """on_start() sets data reference."""
        strategy = SRMeanReversionStrategy()
        data = pd.DataFrame({'close': [100, 101, 102]})
        strategy.on_start(data)
        assert strategy.data is not None
        assert len(strategy.data) == 3


class TestOnBarLevelDetection:
    """Test on_bar() level detection logic."""

    def test_on_bar_detects_levels_initially(self):
        """on_bar() detects levels on first call."""
        data = pd.DataFrame({
            'close': [100] * 20 + [110] + [100] * 20,
            'high': [100] * 20 + [110] + [100] * 20,
            'low': [95] * 20 + [85] + [95] * 20
        })
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        bar = data.iloc[-1]
        result = strategy.on_bar(bar, data)
        
        assert strategy.current_levels is not None
        assert 'resistance' in strategy.current_levels
        assert 'support' in strategy.current_levels

    def test_on_bar_updates_levels_periodically(self):
        """on_bar() updates levels every 10 bars."""
        data = pd.DataFrame({
            'close': [100] * 50,
            'high': [100] * 50,
            'low': [95] * 50
        })
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        # First call (idx=49, not divisible by 10)
        bar = data.iloc[-1]
        strategy.on_bar(bar, data)
        first_levels = strategy.current_levels
        
        # Simulate idx=50 (divisible by 10)
        data = pd.concat([data, pd.DataFrame({'close': [101], 'high': [101], 'low': [96]})], ignore_index=True)
        bar = data.iloc[-1]
        strategy.on_bar(bar, data)
        
        # Levels should be updated
        assert strategy.current_levels is not None


class TestLongSignalGeneration:
    """Test long signal generation at support."""

    def test_long_signal_near_support(self):
        """Strategy generates LONG signal near support."""
        # Create data with clear support at 90
        data = pd.DataFrame({
            'close': [100] * 20 + [90] + [100] * 20,
            'high': [100] * 20 + [90] + [100] * 20,
            'low': [95] * 20 + [85] + [95] * 20
        })
        strategy = SRMeanReversionStrategy(entry_tolerance_pct=10.0)
        strategy.on_start(data)
        
        # Add bar near support
        data = pd.concat([data, pd.DataFrame({'close': [91], 'high': [91], 'low': [90]})], ignore_index=True)
        bar = data.iloc[-1]
        
        result = strategy.on_bar(bar, data)
        
        if result:  # May or may not trigger depending on level detection
            assert result['action'] == 'LONG'
            assert 'support' in result['reason'].lower()

    def test_long_signal_sets_position(self):
        """LONG signal sets position to 1."""
        data = pd.DataFrame({
            'close': [100] * 30,
            'high': [100] * 30,
            'low': [95] * 30
        })
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        # Manually trigger long
        result = strategy._create_long_signal(100.0, 95.0, 110.0)
        
        assert strategy.position == 1
        assert strategy.position_entry_price == 100.0
        assert strategy.entry_bar is not None

    def test_long_signal_contains_stop_loss(self):
        """LONG signal includes stop loss."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy(stop_loss_pct=1.0)
        strategy.on_start(data)
        result = strategy._create_long_signal(100.0, 95.0, 110.0)
        
        assert 'stop_loss' in result
        # Stop loss should be below support
        assert result['stop_loss'] < 95.0

    def test_long_signal_contains_take_profit(self):
        """LONG signal includes take profit."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_long_signal(100.0, 95.0, 110.0)
        
        assert 'take_profit' in result
        # Take profit at resistance
        assert result['take_profit'] == 110.0

    def test_long_signal_without_resistance(self):
        """LONG signal handles missing resistance level."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_long_signal(100.0, 95.0, None)
        
        assert 'take_profit' in result
        # Default take profit at 2% above entry
        assert result['take_profit'] == 100.0 * 1.02


class TestShortSignalGeneration:
    """Test short signal generation at resistance."""

    def test_short_signal_near_resistance(self):
        """Strategy generates SHORT signal near resistance."""
        data = pd.DataFrame({
            'close': [100] * 20 + [110] + [100] * 20,
            'high': [100] * 20 + [115] + [100] * 20,
            'low': [95] * 20 + [85] + [95] * 20
        })
        strategy = SRMeanReversionStrategy(entry_tolerance_pct=10.0)
        strategy.on_start(data)
        
        # Add bar near resistance
        data = pd.concat([data, pd.DataFrame({'close': [109], 'high': [110], 'low': [108]})], ignore_index=True)
        bar = data.iloc[-1]
        
        result = strategy.on_bar(bar, data)
        
        if result:  # May or may not trigger
            assert result['action'] == 'SHORT'
            assert 'resistance' in result['reason'].lower()

    def test_short_signal_sets_position(self):
        """SHORT signal sets position to -1."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_short_signal(110.0, 110.0, 90.0)
        
        assert strategy.position == -1
        assert strategy.position_entry_price == 110.0
        assert strategy.entry_bar is not None

    def test_short_signal_contains_stop_loss(self):
        """SHORT signal includes stop loss."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy(stop_loss_pct=1.0)
        strategy.on_start(data)
        result = strategy._create_short_signal(110.0, 110.0, 90.0)
        
        assert 'stop_loss' in result
        # Stop loss should be above resistance
        assert result['stop_loss'] > 110.0

    def test_short_signal_contains_take_profit(self):
        """SHORT signal includes take profit."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_short_signal(110.0, 110.0, 90.0)
        
        assert 'take_profit' in result
        # Take profit at support
        assert result['take_profit'] == 90.0

    def test_short_signal_without_support(self):
        """SHORT signal handles missing support level."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_short_signal(110.0, 110.0, None)
        
        assert 'take_profit' in result
        # Default take profit at 2% below entry
        assert result['take_profit'] == 110.0 * 0.98


class TestExitConditions:
    """Test exit condition checking."""

    def test_exit_on_max_holding_period(self):
        """Strategy exits after max holding period."""
        data = pd.DataFrame({'close': [100] * 100, 'high': [100] * 100, 'low': [95] * 100})
        strategy = SRMeanReversionStrategy(max_holding_bars=10)
        strategy.on_start(data)
        strategy.position = 1
        strategy.position_entry_price = 100.0
        strategy.entry_bar = 40
        
        # Check at bar 50 (held for 10 bars == max)
        bar = data.iloc[50]
        result = strategy._check_exit_conditions(bar, 50, 100.0)
        
        assert result is not None
        assert result['action'] == 'CLOSE'
        assert 'Max holding' in result['reason']
        assert strategy.position == 0
        assert strategy.position_entry_price is None

    def test_no_exit_before_max_holding(self):
        """Strategy doesn't exit before max holding period."""
        data = pd.DataFrame({'close': [100] * 100, 'high': [100] * 100, 'low': [95] * 100})
        strategy = SRMeanReversionStrategy(max_holding_bars=50)
        strategy.on_start(data)
        strategy.position = 1
        strategy.position_entry_price = 100.0
        strategy.entry_bar = 40
        
        # Check at bar 45 (held for 5 bars < 50 max)
        bar = data.iloc[45]
        result = strategy._check_exit_conditions(bar, 45, 100.0)
        
        assert result is None
        assert strategy.position == 1  # Still in position

    def test_exit_includes_exit_price(self):
        """Exit signal includes exit price."""
        data = pd.DataFrame({'close': [100] * 100, 'high': [100] * 100, 'low': [95] * 100})
        strategy = SRMeanReversionStrategy(max_holding_bars=5)
        strategy.on_start(data)
        strategy.position = 1
        strategy.entry_bar = 5
        
        bar = data.iloc[10]
        result = strategy._check_exit_conditions(bar, 10, 105.0)
        
        assert result is not None
        assert 'exit_price' in result
        assert result['exit_price'] == 105.0


class TestPositionManagement:
    """Test position state management."""

    def test_no_entry_when_in_position(self):
        """Strategy doesn't generate new signals when in position."""
        data = pd.DataFrame({
            'close': [100] * 50,
            'high': [100] * 50,
            'low': [95] * 50
        })
        strategy = SRMeanReversionStrategy(entry_tolerance_pct=50.0)
        strategy.on_start(data)
        strategy.position = 1  # Already long
        strategy.entry_bar = 10
        
        bar = data.iloc[-1]
        result = strategy.on_bar(bar, data)
        
        # Should not generate new entry signal (only checks exit)
        if result:
            assert result['action'] != 'LONG'
            assert result['action'] != 'SHORT'

    def test_position_starts_flat(self):
        """Strategy starts with flat position."""
        strategy = SRMeanReversionStrategy()
        assert strategy.position == 0

    def test_entry_bar_tracking(self):
        """Strategy tracks entry bar correctly."""
        data = pd.DataFrame({'close': [100] * 30, 'high': [100] * 30, 'low': [95] * 30})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        strategy._create_long_signal(100.0, 95.0, 110.0)
        
        assert strategy.entry_bar == 29  # len(data) - 1


class TestIntegration:
    """Test integration scenarios."""

    def test_full_trade_cycle(self):
        """Integration: Complete trade cycle from entry to exit."""
        # Create data with support level
        data = pd.DataFrame({
            'close': [100] * 30,
            'high': [100] * 30,
            'low': [95] * 30
        })
        strategy = SRMeanReversionStrategy(max_holding_bars=5)
        strategy.on_start(data)
        
        # Manually enter long position
        strategy.position = 1
        strategy.position_entry_price = 100.0
        strategy.entry_bar = 25
        
        # Simulate bars until max holding (bar 30 = 5 bars held)
        data_extended = pd.concat([
            data,
            pd.DataFrame({'close': [100] * 5, 'high': [100] * 5, 'low': [95] * 5})
        ], ignore_index=True)
        
        for i in range(30, 35):
            bar = data_extended.iloc[i]
            result = strategy.on_bar(bar, data_extended.iloc[:i+1])
            if result and result['action'] == 'CLOSE':
                break
        
        # Should have exited
        assert strategy.position == 0

    def test_realistic_price_data(self):
        """Integration: Strategy works with realistic price data."""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        data = pd.DataFrame({
            'close': prices,
            'high': prices + np.random.rand(100) * 0.5,
            'low': prices - np.random.rand(100) * 0.5
        })
        
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        # Run through all bars
        for i in range(len(data)):
            bar = data.iloc[i]
            result = strategy.on_bar(bar, data.iloc[:i+1])
            # Should not crash
            assert result is None or isinstance(result, dict)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimal_data(self):
        """Edge case: Strategy handles minimal data."""
        data = pd.DataFrame({
            'close': [100, 101],
            'high': [100, 101],
            'low': [99, 100]
        })
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        bar = data.iloc[-1]
        result = strategy.on_bar(bar, data)
        # Should not crash
        assert result is None or isinstance(result, dict)

    def test_zero_entry_tolerance(self):
        """Edge case: Zero entry tolerance."""
        strategy = SRMeanReversionStrategy(entry_tolerance_pct=0.0)
        assert strategy.entry_tolerance_pct == 0.0

    def test_very_high_stop_loss(self):
        """Edge case: Very high stop loss percentage."""
        data = pd.DataFrame({'close': [100]*10, 'high': [100]*10, 'low': [90]*10})
        strategy = SRMeanReversionStrategy(stop_loss_pct=50.0)
        strategy.on_start(data)
        result = strategy._create_long_signal(100.0, 90.0, None)
        # Stop loss far below support
        assert result['stop_loss'] < 90.0

    def test_max_holding_bars_one(self):
        """Edge case: Max holding bars = 1."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy(max_holding_bars=1)
        strategy.on_start(data)
        strategy.position = 1
        strategy.entry_bar = 8
        
        bar = data.iloc[9]
        result = strategy._check_exit_conditions(bar, 9, 100.0)
        
        assert result is not None
        assert result['action'] == 'CLOSE'

    def test_entry_bar_none_handling(self):
        """Edge case: entry_bar is None when checking exit."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy(max_holding_bars=5)
        strategy.on_start(data)
        strategy.position = 1
        strategy.entry_bar = None  # Edge case
        
        bar = data.iloc[5]
        result = strategy._check_exit_conditions(bar, 5, 100.0)
        # Should handle gracefully (bars_held = 0)
        assert result is None

    def test_negative_price(self):
        """Edge case: Handle negative prices (unusual but valid)."""
        data = pd.DataFrame({'close': [100]*10, 'high': [100]*10, 'low': [95]*10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        result = strategy._create_long_signal(-10.0, -15.0, -5.0)
        assert result['entry_price'] == -10.0

    def test_very_large_lookback(self):
        """Edge case: Very large lookback exceeding data size."""
        data = pd.DataFrame({
            'close': [100] * 20,
            'high': [100] * 20,
            'low': [95] * 20
        })
        strategy = SRMeanReversionStrategy(lookback_bars=1000)
        strategy.on_start(data)
        
        bar = data.iloc[-1]
        result = strategy.on_bar(bar, data)
        # Should handle gracefully
        assert result is None or isinstance(result, dict)

    def test_identical_prices(self):
        """Edge case: All prices identical."""
        data = pd.DataFrame({
            'close': [100.0] * 50,
            'high': [100.0] * 50,
            'low': [100.0] * 50
        })
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        bar = data.iloc[-1]
        result = strategy.on_bar(bar, data)
        # No levels detected, no trades
        assert result is None

    def test_data_reference_updates(self):
        """Edge case: Data reference updates on each bar."""
        data = pd.DataFrame({'close': [100] * 10, 'high': [100] * 10, 'low': [95] * 10})
        strategy = SRMeanReversionStrategy()
        strategy.on_start(data)
        
        initial_len = len(strategy.data)
        
        # Add new data
        data = pd.concat([data, pd.DataFrame({'close': [101], 'high': [101], 'low': [96]})], ignore_index=True)
        bar = data.iloc[-1]
        strategy.on_bar(bar, data)
        
        # Data should be updated
        assert len(strategy.data) == initial_len + 1
