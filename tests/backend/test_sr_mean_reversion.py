"""
Unit tests for SRMeanReversionStrategy

Tests the S/R mean reversion strategy:
- Entry at support/resistance levels
- Exit on max holding period
- Stop loss and take profit calculation
- Level detection integration
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from backend.strategies.sr_mean_reversion import SRMeanReversionStrategy


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing"""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    data = pd.DataFrame({
        'timestamp': dates,
        'open': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'close': 50000.0,
        'volume': 100.0
    })
    return data


@pytest.fixture
def mock_sr_detector():
    """Mock SupportResistanceDetector"""
    with patch('backend.strategies.sr_mean_reversion.SupportResistanceDetector') as mock:
        detector_instance = Mock()
        mock.return_value = detector_instance
        yield detector_instance


@pytest.fixture
def strategy(mock_sr_detector):
    """Create strategy instance with mocked S/R detector"""
    return SRMeanReversionStrategy(
        lookback_bars=100,
        level_tolerance_pct=0.1,
        entry_tolerance_pct=0.15,
        stop_loss_pct=0.8,
        max_holding_bars=48
    )


# =============================================================================
# Category 1: Initialization Tests (4 tests)
# =============================================================================

def test_strategy_initialization_with_defaults():
    """Test strategy initializes with default parameters"""
    with patch('backend.strategies.sr_mean_reversion.SupportResistanceDetector'):
        strategy = SRMeanReversionStrategy()
        
        assert strategy.entry_tolerance_pct == 0.15
        assert strategy.stop_loss_pct == 0.8
        assert strategy.max_holding_bars == 48
        assert strategy.position == 0
        assert strategy.current_levels is None
        assert strategy.entry_bar is None
        assert strategy.position_entry_price is None


def test_strategy_initialization_with_custom_params():
    """Test strategy initializes with custom parameters"""
    with patch('backend.strategies.sr_mean_reversion.SupportResistanceDetector'):
        strategy = SRMeanReversionStrategy(
            lookback_bars=200,
            level_tolerance_pct=0.2,
            entry_tolerance_pct=0.25,
            stop_loss_pct=1.0,
            max_holding_bars=96
        )
        
        assert strategy.entry_tolerance_pct == 0.25
        assert strategy.stop_loss_pct == 1.0
        assert strategy.max_holding_bars == 96


def test_sr_detector_created_with_params():
    """Test S/R detector created with correct parameters"""
    with patch('backend.strategies.sr_mean_reversion.SupportResistanceDetector') as mock_class:
        SRMeanReversionStrategy(lookback_bars=150, level_tolerance_pct=0.2)
        
        mock_class.assert_called_once_with(lookback_bars=150, tolerance_pct=0.2)


def test_on_start_sets_data(strategy, sample_data):
    """Test on_start sets data attribute"""
    strategy.on_start(sample_data)
    
    assert strategy.data is not None
    assert len(strategy.data) == 200


# =============================================================================
# Category 2: LONG Entry Tests (7 tests)
# =============================================================================

def test_long_entry_at_support(strategy, sample_data, mock_sr_detector):
    """Test LONG signal generated at support level"""
    strategy.on_start(sample_data)
    
    # Mock S/R levels
    mock_sr_detector.detect_levels.return_value = {
        'support': [49000.0],
        'resistance': [51000.0]
    }
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.1,  # Within entry tolerance
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 2.0
    }
    
    # Create bar at support level
    bar = pd.Series({
        'timestamp': pd.Timestamp('2024-01-01 10:00'),
        'open': 49050.0,
        'high': 49100.0,
        'low': 49000.0,
        'close': 49050.0,
        'volume': 100.0
    })
    
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is not None
    assert signal['action'] == 'LONG'
    assert signal['entry_price'] == 49050.0
    assert 'Near support' in signal['reason']
    assert strategy.position == 1
    assert strategy.position_entry_price == 49050.0


def test_long_signal_includes_stop_loss(strategy, sample_data, mock_sr_detector):
    """Test LONG signal includes stop loss below support"""
    strategy.on_start(sample_data)
    
    support_level = 49000.0
    mock_sr_detector.detect_levels.return_value = {'support': [support_level], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': support_level,
        'distance_to_support_pct': 0.1,
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    # Stop loss = support * (1 - stop_loss_pct/100) = 49000 * (1 - 0.8/100) = 48608.0
    expected_stop = support_level * (1 - strategy.stop_loss_pct / 100)
    assert signal['stop_loss'] == pytest.approx(expected_stop, rel=1e-2)


def test_long_signal_includes_take_profit(strategy, sample_data, mock_sr_detector):
    """Test LONG signal includes take profit at resistance"""
    strategy.on_start(sample_data)
    
    resistance_level = 51000.0
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [resistance_level]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.1,
        'nearest_resistance': resistance_level
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal['take_profit'] == resistance_level


def test_long_take_profit_defaults_when_no_resistance(strategy, sample_data, mock_sr_detector):
    """Test LONG take profit defaults to 2% when no resistance"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': []}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.1,
        'nearest_resistance': None
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    # Default take profit = current_price * 1.02
    expected_tp = 49050.0 * 1.02
    assert signal['take_profit'] == pytest.approx(expected_tp, rel=1e-2)


def test_no_long_signal_when_far_from_support(strategy, sample_data, mock_sr_detector):
    """Test no LONG signal when price too far from support"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.5,  # > entry_tolerance_pct (0.15)
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49500.0, 'high': 49600.0, 'low': 49400.0, 'open': 49500.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None
    assert strategy.position == 0


def test_no_long_when_nearest_support_none(strategy, sample_data, mock_sr_detector):
    """Test no LONG signal when no support level detected"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': None,
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None


def test_long_entry_sets_position_state(strategy, sample_data, mock_sr_detector):
    """Test LONG entry updates position state correctly"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.1,
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    
    # Before entry
    assert strategy.position == 0
    assert strategy.entry_bar is None
    
    strategy.on_bar(bar, sample_data)
    
    # After entry
    assert strategy.position == 1
    assert strategy.entry_bar == len(sample_data) - 1
    assert strategy.position_entry_price == 49050.0


# =============================================================================
# Category 3: SHORT Entry Tests (6 tests)
# =============================================================================

def test_short_entry_at_resistance(strategy, sample_data, mock_sr_detector):
    """Test SHORT signal generated at resistance level"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 2.0,
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 0.1  # Within entry tolerance
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is not None
    assert signal['action'] == 'SHORT'
    assert signal['entry_price'] == 50950.0
    assert 'Near resistance' in signal['reason']
    assert strategy.position == -1


def test_short_signal_includes_stop_loss(strategy, sample_data, mock_sr_detector):
    """Test SHORT signal includes stop loss above resistance"""
    strategy.on_start(sample_data)
    
    resistance_level = 51000.0
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [resistance_level]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_resistance': resistance_level,
        'distance_to_resistance_pct': 0.1,
        'nearest_support': 49000.0
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    # Stop loss = resistance * (1 + stop_loss_pct/100) = 51000 * (1 + 0.8/100) = 51408.0
    expected_stop = resistance_level * (1 + strategy.stop_loss_pct / 100)
    assert signal['stop_loss'] == pytest.approx(expected_stop, rel=1e-2)


def test_short_signal_includes_take_profit(strategy, sample_data, mock_sr_detector):
    """Test SHORT signal includes take profit at support"""
    strategy.on_start(sample_data)
    
    support_level = 49000.0
    mock_sr_detector.detect_levels.return_value = {'support': [support_level], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 0.1,
        'nearest_support': support_level
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal['take_profit'] == support_level


def test_short_take_profit_defaults_when_no_support(strategy, sample_data, mock_sr_detector):
    """Test SHORT take profit defaults to 2% when no support"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 0.1,
        'nearest_support': None
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    # Default take profit = current_price * 0.98
    expected_tp = 50950.0 * 0.98
    assert signal['take_profit'] == pytest.approx(expected_tp, rel=1e-2)


def test_no_short_signal_when_far_from_resistance(strategy, sample_data, mock_sr_detector):
    """Test no SHORT signal when price too far from resistance"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 0.5,  # > entry_tolerance_pct
        'nearest_support': 49000.0
    }
    
    bar = pd.Series({'close': 50500.0, 'high': 50600.0, 'low': 50400.0, 'open': 50500.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None


def test_short_entry_sets_position_state(strategy, sample_data, mock_sr_detector):
    """Test SHORT entry updates position state correctly"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': 0.1,
        'nearest_support': 49000.0
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    
    assert strategy.position == 0
    
    strategy.on_bar(bar, sample_data)
    
    assert strategy.position == -1
    assert strategy.entry_bar == len(sample_data) - 1
    assert strategy.position_entry_price == 50950.0


# =============================================================================
# Category 4: Exit Logic Tests (5 tests)
# =============================================================================

def test_exit_after_max_holding_bars_long(strategy, sample_data, mock_sr_detector):
    """Test exit after max holding period for LONG position"""
    strategy.on_start(sample_data)
    strategy.position = 1
    strategy.entry_bar = 100
    strategy.position_entry_price = 49050.0
    strategy.max_holding_bars = 10
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    
    # Bar at index 110 (held for 10 bars)
    bar = pd.Series({'close': 49500.0, 'high': 49600.0, 'low': 49400.0, 'open': 49500.0, 'volume': 100.0})
    
    # Manually set data length to simulate index 110
    extended_data = pd.concat([sample_data] * 2, ignore_index=True)[:111]
    
    signal = strategy.on_bar(bar, extended_data)
    
    assert signal is not None
    assert signal['action'] == 'CLOSE'
    assert 'Max holding period' in signal['reason']
    assert signal['exit_price'] == 49500.0
    assert strategy.position == 0
    assert strategy.position_entry_price is None


def test_exit_after_max_holding_bars_short(strategy, sample_data, mock_sr_detector):
    """Test exit after max holding period for SHORT position"""
    strategy.on_start(sample_data)
    strategy.position = -1
    strategy.entry_bar = 50
    strategy.position_entry_price = 50950.0
    strategy.max_holding_bars = 5
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    
    bar = pd.Series({'close': 50500.0, 'high': 50600.0, 'low': 50400.0, 'open': 50500.0, 'volume': 100.0})
    extended_data = pd.concat([sample_data] * 2, ignore_index=True)[:56]
    
    signal = strategy.on_bar(bar, extended_data)
    
    assert signal is not None
    assert signal['action'] == 'CLOSE'
    assert strategy.position == 0


def test_no_exit_before_max_holding_bars(strategy, sample_data, mock_sr_detector):
    """Test no exit before max holding period reached"""
    strategy.on_start(sample_data)
    strategy.position = 1
    strategy.entry_bar = 100
    strategy.max_holding_bars = 48
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    
    # Only 10 bars held (< max_holding_bars)
    bar = pd.Series({'close': 49500.0, 'high': 49600.0, 'low': 49400.0, 'open': 49500.0, 'volume': 100.0})
    extended_data = pd.concat([sample_data] * 2, ignore_index=True)[:111]
    
    signal = strategy.on_bar(bar, extended_data)
    
    assert signal is None  # No exit yet
    assert strategy.position == 1  # Still in position


def test_no_entry_while_in_position(strategy, sample_data, mock_sr_detector):
    """Test no new entry signals while already in position"""
    strategy.on_start(sample_data)
    strategy.position = 1
    strategy.entry_bar = 100
    
    # Mock perfect LONG entry conditions
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': 0.1,
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, extended_data := pd.concat([sample_data] * 2, ignore_index=True)[:110])
    
    # Should not generate new entry while in position
    assert signal is None
    assert strategy.position == 1  # Still in original position


def test_exit_resets_position_state(strategy, sample_data, mock_sr_detector):
    """Test exit properly resets position state"""
    strategy.on_start(sample_data)
    strategy.position = 1
    strategy.entry_bar = 100
    strategy.position_entry_price = 49050.0
    strategy.max_holding_bars = 10
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    
    bar = pd.Series({'close': 49500.0, 'high': 49600.0, 'low': 49400.0, 'open': 49500.0, 'volume': 100.0})
    extended_data = pd.concat([sample_data] * 2, ignore_index=True)[:111]
    
    strategy.on_bar(bar, extended_data)
    
    # Check state reset
    assert strategy.position == 0
    assert strategy.position_entry_price is None


# =============================================================================
# Category 5: Level Update Tests (3 tests)
# =============================================================================

def test_levels_updated_every_10_bars(strategy, sample_data, mock_sr_detector):
    """Test S/R levels updated every 10 bars"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {}
    
    bar = pd.Series({'close': 50000.0, 'high': 50100.0, 'low': 49900.0, 'open': 50000.0, 'volume': 100.0})
    
    # Bar 0 - should update
    strategy.on_bar(bar, sample_data[:1])
    assert mock_sr_detector.detect_levels.call_count == 1
    
    # Bar 5 - should not update
    strategy.on_bar(bar, sample_data[:6])
    assert mock_sr_detector.detect_levels.call_count == 1
    
    # Bar 10 - should update
    strategy.on_bar(bar, sample_data[:11])
    assert mock_sr_detector.detect_levels.call_count == 2
    
    # Bar 20 - should update
    strategy.on_bar(bar, sample_data[:21])
    assert mock_sr_detector.detect_levels.call_count == 3


def test_levels_updated_when_none(strategy, sample_data, mock_sr_detector):
    """Test levels updated when current_levels is None"""
    strategy.on_start(sample_data)
    strategy.current_levels = None
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {}
    
    bar = pd.Series({'close': 50000.0, 'high': 50100.0, 'low': 49900.0, 'open': 50000.0, 'volume': 100.0})
    
    # Bar 5 (not divisible by 10, but levels are None)
    strategy.on_bar(bar, sample_data[:6])
    
    assert mock_sr_detector.detect_levels.call_count == 1


def test_data_reference_updated_on_bar(strategy, sample_data, mock_sr_detector):
    """Test data reference updated on each bar"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [], 'resistance': []}
    mock_sr_detector.get_nearest_levels.return_value = {}
    
    bar = pd.Series({'close': 50000.0, 'high': 50100.0, 'low': 49900.0, 'open': 50000.0, 'volume': 100.0})
    
    new_data = sample_data.iloc[:150]
    strategy.on_bar(bar, new_data)
    
    assert len(strategy.data) == 150


# =============================================================================
# Category 6: Edge Cases (3 tests)
# =============================================================================

def test_handles_no_levels_detected(strategy, sample_data, mock_sr_detector):
    """Test strategy handles case when no S/R levels detected"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [], 'resistance': []}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': None,
        'nearest_resistance': None
    }
    
    bar = pd.Series({'close': 50000.0, 'high': 50100.0, 'low': 49900.0, 'open': 50000.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None


def test_handles_distance_none_support(strategy, sample_data, mock_sr_detector):
    """Test handles None distance to support"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'distance_to_support_pct': None,  # None distance
        'nearest_resistance': 51000.0
    }
    
    bar = pd.Series({'close': 49050.0, 'high': 49100.0, 'low': 49000.0, 'open': 49050.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None  # Should not enter when distance is None


def test_handles_distance_none_resistance(strategy, sample_data, mock_sr_detector):
    """Test handles None distance to resistance"""
    strategy.on_start(sample_data)
    
    mock_sr_detector.detect_levels.return_value = {'support': [49000.0], 'resistance': [51000.0]}
    mock_sr_detector.get_nearest_levels.return_value = {
        'nearest_support': 49000.0,
        'nearest_resistance': 51000.0,
        'distance_to_resistance_pct': None  # None distance
    }
    
    bar = pd.Series({'close': 50950.0, 'high': 51000.0, 'low': 50900.0, 'open': 50950.0, 'volume': 100.0})
    signal = strategy.on_bar(bar, sample_data)
    
    assert signal is None  # Should not enter when distance is None
