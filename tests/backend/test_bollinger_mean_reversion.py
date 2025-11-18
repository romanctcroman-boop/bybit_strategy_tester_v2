"""
Comprehensive tests for Bollinger Bands Mean Reversion Strategy

Test Coverage:
- Initialization (config handling, validation, legacy API)
- Default parameters
- Configuration validation (types, ranges, missing fields)
- Bollinger Bands calculation (legacy + optimized)
- on_start (state initialization, vectorized precomputation)
- on_bar (entry signals, exit conditions, position management)
- Signal generation (LONG/SHORT with stop/take profit)
- Edge cases (insufficient data, NaN handling, boundary conditions)

Target Coverage: 75% (147 statements)
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from backend.strategies.bollinger_mean_reversion import BollingerMeanReversionStrategy


# ===========================
# 1. INITIALIZATION TESTS (8 tests)
# ===========================

def test_init_with_config_dict():
    """✅ Test initialization with config dictionary (preferred method)"""
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.5,
        'entry_threshold_pct': 0.1,
        'stop_loss_pct': 1.0,
        'max_holding_bars': 50
    }
    
    strategy = BollingerMeanReversionStrategy(config=config)
    
    assert strategy.bb_period == 20
    assert strategy.bb_std_dev == 2.5
    assert strategy.entry_threshold_pct == 0.1
    assert strategy.stop_loss_pct == 1.0
    assert strategy.max_holding_bars == 50
    assert strategy.config == config


def test_init_with_legacy_parameters():
    """✅ Test initialization with legacy individual parameters (backward compatibility)"""
    strategy = BollingerMeanReversionStrategy(
        bb_period=30,
        bb_std_dev=3.0,
        entry_threshold_pct=0.2,
        stop_loss_pct=1.5,
        max_holding_bars=60
    )
    
    assert strategy.bb_period == 30
    assert strategy.bb_std_dev == 3.0
    assert strategy.entry_threshold_pct == 0.2
    assert strategy.stop_loss_pct == 1.5
    assert strategy.max_holding_bars == 60


def test_init_applies_defaults_for_missing_params():
    """✅ Test that missing parameters get default values"""
    config = {
        'bb_period': 25,
        'bb_std_dev': 2.0
        # Missing: entry_threshold_pct, stop_loss_pct, max_holding_bars
    }
    
    strategy = BollingerMeanReversionStrategy(config=config)
    
    # Check defaults applied
    assert strategy.bb_period == 25
    assert strategy.bb_std_dev == 2.0
    assert strategy.entry_threshold_pct == 0.05  # default
    assert strategy.stop_loss_pct == 0.8  # default
    assert strategy.max_holding_bars == 48  # default


def test_init_with_empty_config_uses_all_defaults():
    """✅ Test initialization with empty config (all defaults)"""
    strategy = BollingerMeanReversionStrategy(config={})
    
    defaults = BollingerMeanReversionStrategy.get_default_params()
    assert strategy.bb_period == defaults['bb_period']
    assert strategy.bb_std_dev == defaults['bb_std_dev']
    assert strategy.entry_threshold_pct == defaults['entry_threshold_pct']
    assert strategy.stop_loss_pct == defaults['stop_loss_pct']
    assert strategy.max_holding_bars == defaults['max_holding_bars']


def test_init_sets_initial_state():
    """✅ Test that initialization sets correct initial state"""
    strategy = BollingerMeanReversionStrategy()
    
    assert strategy.position == 0  # Flat
    assert strategy.entry_bar == 0
    assert strategy.bb_upper is None
    assert strategy.bb_middle is None
    assert strategy.bb_lower is None


def test_init_with_none_config_creates_empty_config():
    """✅ Test that config=None creates empty config dict"""
    strategy = BollingerMeanReversionStrategy(config=None)
    
    # Should use all defaults
    defaults = BollingerMeanReversionStrategy.get_default_params()
    assert strategy.config == defaults


def test_init_legacy_partial_parameters():
    """✅ Test legacy API with only some parameters specified"""
    strategy = BollingerMeanReversionStrategy(
        bb_period=25,
        stop_loss_pct=1.2
        # Other params should use defaults
    )
    
    assert strategy.bb_period == 25
    assert strategy.stop_loss_pct == 1.2
    assert strategy.bb_std_dev == 2.0  # default
    assert strategy.entry_threshold_pct == 0.05  # default


def test_init_calls_validate_config():
    """✅ Test that __init__ calls validate_config"""
    config = {'bb_period': -10}  # Invalid
    
    with pytest.raises(ValueError, match="bb_period must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


# ===========================
# 2. DEFAULT PARAMETERS TESTS (1 test)
# ===========================

def test_get_default_params_returns_correct_values():
    """✅ Test default parameters structure"""
    defaults = BollingerMeanReversionStrategy.get_default_params()
    
    assert defaults == {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }


# ===========================
# 3. CONFIGURATION VALIDATION TESTS (9 tests)
# ===========================

def test_validate_config_accepts_valid_config():
    """✅ Test that valid config passes validation"""
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }
    
    strategy = BollingerMeanReversionStrategy(config=config)
    result = strategy.validate_config(config)
    
    assert result is True


def test_validate_config_rejects_missing_bb_period():
    """✅ Test validation directly on validate_config method"""
    strategy = BollingerMeanReversionStrategy()
    
    config = {
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
        # Missing bb_period
    }
    
    with pytest.raises(ValueError, match="Missing required parameters"):
        strategy.validate_config(config)


def test_validate_config_rejects_negative_bb_period():
    """✅ Test validation fails for negative bb_period"""
    config = {
        'bb_period': -10,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }
    
    with pytest.raises(ValueError, match="bb_period must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_zero_bb_period():
    """✅ Test validation fails for zero bb_period"""
    config = {
        'bb_period': 0,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }
    
    with pytest.raises(ValueError, match="bb_period must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_negative_bb_std_dev():
    """✅ Test validation fails for negative bb_std_dev"""
    config = {
        'bb_period': 20,
        'bb_std_dev': -1.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }
    
    with pytest.raises(ValueError, match="bb_std_dev must be positive"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_zero_stop_loss_pct():
    """✅ Test validation fails for zero stop_loss_pct"""
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0,
        'max_holding_bars': 48
    }
    
    with pytest.raises(ValueError, match="stop_loss_pct must be positive"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_negative_max_holding_bars():
    """✅ Test validation fails for negative max_holding_bars"""
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': -5
    }
    
    with pytest.raises(ValueError, match="max_holding_bars must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_float_bb_period():
    """✅ Test validation fails for float bb_period (expects int)"""
    config = {
        'bb_period': 20.5,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48
    }
    
    with pytest.raises(ValueError, match="bb_period must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


def test_validate_config_rejects_float_max_holding_bars():
    """✅ Test validation fails for float max_holding_bars"""
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 0.8,
        'max_holding_bars': 48.5
    }
    
    with pytest.raises(ValueError, match="max_holding_bars must be positive integer"):
        BollingerMeanReversionStrategy(config=config)


# ===========================
# 4. BOLLINGER BANDS CALCULATION TESTS (7 tests)
# ===========================

def test_calculate_bollinger_bands_with_sufficient_data():
    """✅ Test legacy BB calculation with enough data"""
    strategy = BollingerMeanReversionStrategy()
    
    # Create synthetic data
    prices = [50000 + i * 100 for i in range(20)]
    df = pd.DataFrame({'close': prices})
    
    bands = strategy.calculate_bollinger_bands(df)
    
    assert bands is not None
    assert 'upper' in bands
    assert 'middle' in bands
    assert 'lower' in bands
    assert 'std' in bands
    assert bands['upper'] > bands['middle'] > bands['lower']


def test_calculate_bollinger_bands_with_insufficient_data():
    """✅ Test legacy BB calculation returns None with insufficient data"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 20})
    
    # Only 10 bars (need 20)
    df = pd.DataFrame({'close': [50000] * 10})
    
    bands = strategy.calculate_bollinger_bands(df)
    
    assert bands is None


def test_add_bollinger_bands_static_method():
    """✅ Test optimized vectorized BB calculation (static method)"""
    df = pd.DataFrame({'close': [50000 + i * 100 for i in range(50)]})
    
    result = BollingerMeanReversionStrategy.add_bollinger_bands(
        df, period=20, std_dev=2.0, price_col='close'
    )
    
    # Check columns added
    assert 'bb_middle' in result.columns
    assert 'bb_upper' in result.columns
    assert 'bb_lower' in result.columns
    
    # Check first 19 rows are NaN (not enough data)
    assert pd.isna(result.at[0, 'bb_middle'])
    assert pd.isna(result.at[18, 'bb_middle'])
    
    # Check row 20 has values
    assert not pd.isna(result.at[19, 'bb_middle'])
    assert result.at[19, 'bb_upper'] > result.at[19, 'bb_middle']
    assert result.at[19, 'bb_middle'] > result.at[19, 'bb_lower']


def test_add_bollinger_bands_with_custom_period():
    """✅ Test vectorized BB with custom period"""
    df = pd.DataFrame({'close': [50000] * 100})
    
    result = BollingerMeanReversionStrategy.add_bollinger_bands(
        df, period=50, std_dev=2.0
    )
    
    # First 49 rows should be NaN
    assert pd.isna(result.at[48, 'bb_middle'])
    # Row 50 should have values
    assert not pd.isna(result.at[49, 'bb_middle'])


def test_add_bollinger_bands_missing_column_raises_error():
    """✅ Test vectorized BB raises KeyError for missing column"""
    df = pd.DataFrame({'price': [50000] * 20})  # Wrong column name
    
    with pytest.raises(KeyError, match="Column 'close' not found"):
        BollingerMeanReversionStrategy.add_bollinger_bands(df)


def test_add_bollinger_bands_invalid_period_raises_error():
    """✅ Test vectorized BB raises ValueError for invalid period"""
    df = pd.DataFrame({'close': [50000] * 20})
    
    with pytest.raises(ValueError, match="period must be a positive integer"):
        BollingerMeanReversionStrategy.add_bollinger_bands(df, period=-5)


def test_add_bollinger_bands_returns_float64_dtype():
    """✅ Test vectorized BB returns float64 for compatibility"""
    df = pd.DataFrame({'close': [50000 + i for i in range(50)]})
    
    result = BollingerMeanReversionStrategy.add_bollinger_bands(df, period=20)
    
    assert result['bb_middle'].dtype == np.float64
    assert result['bb_upper'].dtype == np.float64
    assert result['bb_lower'].dtype == np.float64


# ===========================
# 5. ON_START TESTS (5 tests)
# ===========================

def test_on_start_initializes_position():
    """✅ Test on_start resets position to flat"""
    strategy = BollingerMeanReversionStrategy()
    strategy.position = 1  # Set to long
    
    df = pd.DataFrame({'close': [50000] * 30})
    strategy.on_start(df)
    
    assert strategy.position == 0


def test_on_start_resets_entry_bar():
    """✅ Test on_start resets entry_bar to 0"""
    strategy = BollingerMeanReversionStrategy()
    strategy.entry_bar = 42
    
    df = pd.DataFrame({'close': [50000] * 30})
    strategy.on_start(df)
    
    assert strategy.entry_bar == 0


def test_on_start_precomputes_bollinger_bands():
    """✅ Test on_start precomputes Bollinger Bands (vectorized optimization)"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({'close': [50000 + i * 10 for i in range(50)]})
    strategy.on_start(df)
    
    # Check BB columns added
    assert 'bb_middle' in df.columns
    assert 'bb_upper' in df.columns
    assert 'bb_lower' in df.columns
    
    # Check last values stored in strategy state
    assert strategy.bb_upper is not None
    assert strategy.bb_middle is not None
    assert strategy.bb_lower is not None


def test_on_start_stores_last_bollinger_values():
    """✅ Test on_start stores last BB values in instance variables"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 20})
    
    prices = [50000 + i * 50 for i in range(30)]
    df = pd.DataFrame({'close': prices})
    strategy.on_start(df)
    
    # Check stored values match last row
    last_idx = len(df) - 1
    assert strategy.bb_upper == df.at[last_idx, 'bb_upper']
    assert strategy.bb_middle == df.at[last_idx, 'bb_middle']
    assert strategy.bb_lower == df.at[last_idx, 'bb_lower']


def test_on_start_with_insufficient_data_no_bb_values():
    """✅ Test on_start with insufficient data (< bb_period)"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 20})
    
    # Only 10 bars (need 20)
    df = pd.DataFrame({'close': [50000] * 10})
    strategy.on_start(df)
    
    # BB values should remain None
    assert strategy.bb_upper is None
    assert strategy.bb_middle is None
    assert strategy.bb_lower is None


# ===========================
# 6. ON_BAR - ENTRY SIGNALS (6 tests)
# ===========================

def test_on_bar_generates_long_signal_at_lower_band():
    """✅ Test LONG signal when price touches lower band"""
    strategy = BollingerMeanReversionStrategy()
    
    # Create data with precomputed bands
    df = pd.DataFrame({
        'close': [50000, 49900, 49800, 49700, 49500],  # Declining
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    # Last bar touches lower band
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    assert signal is not None
    assert signal['action'] == 'LONG'
    assert signal['entry_price'] == 49500
    assert signal['stop_loss'] < 49500  # Stop below entry
    assert signal['take_profit'] == 50000  # Middle band
    assert 'reason' in signal


def test_on_bar_generates_short_signal_at_upper_band():
    """✅ Test SHORT signal when price touches upper band"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({
        'close': [50000, 50100, 50200, 50300, 50500],  # Rising
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    # Last bar touches upper band
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    assert signal is not None
    assert signal['action'] == 'SHORT'
    assert signal['entry_price'] == 50500
    assert signal['stop_loss'] > 50500  # Stop above entry
    assert signal['take_profit'] == 50000  # Middle band


def test_on_bar_no_signal_when_price_in_middle():
    """✅ Test no signal when price between bands"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({
        'close': [50000, 50100, 50000, 49900, 50000],
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    assert signal is None


def test_on_bar_no_signal_when_already_in_position():
    """✅ Test no new entry signal when already in position"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({
        'close': [50000, 49900, 49800, 49700, 49500],
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    # NOW set position after on_start (on_start resets position)
    strategy.position = 1  # Already long
    strategy.entry_bar = 0
    
    # Price touches lower band again, but already in position
    # Should not generate new LONG signal (position != 0 check)
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    # With position != 0, on_bar skips entry logic
    # Should return None (no new entry, no exit conditions met)
    assert signal is None


def test_on_bar_long_signal_sets_position():
    """✅ Test LONG signal updates position state"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({
        'close': [49500] * 5,
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    assert signal['action'] == 'LONG'
    assert strategy.position == 1


def test_on_bar_short_signal_sets_position():
    """✅ Test SHORT signal updates position state"""
    strategy = BollingerMeanReversionStrategy()
    
    df = pd.DataFrame({
        'close': [50500] * 5,
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    assert signal['action'] == 'SHORT'
    assert strategy.position == -1


# ===========================
# 7. ON_BAR - EXIT SIGNALS (4 tests)
# ===========================

def test_on_bar_exit_signal_after_max_holding_bars():
    """✅ Test time-based exit after max_holding_bars"""
    strategy = BollingerMeanReversionStrategy(config={'max_holding_bars': 10})
    
    # Need >= 20 bars for bb_period=20 to avoid NaN in precomputed bands
    df = pd.DataFrame({
        'close': [50000] * 50,
        'open': [50000] * 50,
        'high': [50100] * 50,
        'low': [49900] * 50,
        'volume': [1000] * 50
    })
    strategy.on_start(df)
    
    # Set position AFTER on_start (on_start resets position/entry_bar)
    strategy.position = 1  # In long position
    strategy.entry_bar = 1  # Entered at bar 1
    
    # Bar 11 (entered at 1, held for 10 bars: 11 - 1 = 10, equals max)
    bar = df.iloc[21]  # Use bar 21 to ensure BB values exist
    signal = strategy.on_bar(bar, bar_index=21, data=df.iloc[:22])
    
    assert signal is not None
    assert signal['action'] == 'CLOSE'
    assert 'max_holding_bars' in signal['reason']


def test_on_bar_no_exit_before_max_holding_bars():
    """✅ Test no time-based exit before max_holding_bars"""
    strategy = BollingerMeanReversionStrategy(config={'max_holding_bars': 20})
    strategy.position = 1
    strategy.entry_bar = 0
    
    df = pd.DataFrame({
        'close': [50000] * 30,
        'bb_upper': [50500] * 30,
        'bb_middle': [50000] * 30,
        'bb_lower': [49500] * 30
    })
    strategy.on_start(df)
    
    # Bar 10 (held for 10 bars, below max of 20)
    bar = df.iloc[10]
    signal = strategy.on_bar(bar, bar_index=10, data=df.iloc[:11])
    
    # Should not exit yet
    assert signal is None or signal['action'] != 'CLOSE'


def test_on_bar_exit_exactly_at_max_holding_bars():
    """✅ Test exit exactly at max_holding_bars boundary"""
    strategy = BollingerMeanReversionStrategy(config={'max_holding_bars': 5})
    
    df = pd.DataFrame({
        'close': [50000] * 50,
        'open': [50000] * 50,
        'high': [50100] * 50,
        'low': [49900] * 50,
        'volume': [1000] * 50
    })
    strategy.on_start(df)
    
    # Set position AFTER on_start
    strategy.position = 1
    strategy.entry_bar = 20  # Entered at bar 20 (after BB values available)
    
    # Bar 25 (entered at 20, held for 5 bars: 25 - 20 = 5, equals max)
    bar = df.iloc[25]
    signal = strategy.on_bar(bar, bar_index=25, data=df.iloc[:26])
    
    assert signal is not None
    assert signal['action'] == 'CLOSE'


def test_on_bar_exit_works_for_short_position():
    """✅ Test time-based exit works for SHORT positions"""
    strategy = BollingerMeanReversionStrategy(config={'max_holding_bars': 5})
    
    df = pd.DataFrame({
        'close': [50000] * 50,
        'open': [50000] * 50,
        'high': [50100] * 50,
        'low': [49900] * 50,
        'volume': [1000] * 50
    })
    strategy.on_start(df)
    
    # Set position AFTER on_start
    strategy.position = -1  # Short position
    strategy.entry_bar = 20  # Entered at bar 20
    
    # Bar 25 (entered at 20, held for 5 bars: 25 - 20 = 5, equals max)
    bar = df.iloc[25]
    signal = strategy.on_bar(bar, bar_index=25, data=df.iloc[:26])
    
    assert signal is not None
    assert signal['action'] == 'CLOSE'


# ===========================
# 8. EDGE CASES & FALLBACK (5 tests)
# ===========================

def test_on_bar_fallback_to_legacy_calculation_when_no_precomputed_bands():
    """✅ Test on_bar falls back to legacy BB calculation if no precomputed bands"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 10})
    
    # Don't call on_start (no precomputed bands)
    df = pd.DataFrame({
        'close': [50000 + i * 10 for i in range(30)]
    })
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=29, data=df)
    
    # Should still work using legacy calculation
    assert strategy.bb_upper is not None
    assert strategy.bb_middle is not None
    assert strategy.bb_lower is not None


def test_on_bar_returns_none_with_insufficient_data_legacy():
    """✅ Test on_bar returns None when not enough data for legacy BB calculation"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 20})
    
    # Only 10 bars (need 20)
    df = pd.DataFrame({'close': [50000] * 10})
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=9, data=df)
    
    assert signal is None


def test_on_bar_handles_nan_in_precomputed_bands():
    """✅ Test on_bar falls back when precomputed bands have NaN"""
    strategy = BollingerMeanReversionStrategy(config={'bb_period': 20})
    
    df = pd.DataFrame({
        'close': [50000 + i for i in range(30)],
        'bb_upper': [np.nan] * 19 + [50500] * 11,
        'bb_middle': [np.nan] * 19 + [50000] * 11,
        'bb_lower': [np.nan] * 19 + [49500] * 11
    })
    strategy.on_start(df)
    
    # Bar 10 has NaN bands (should fallback to legacy)
    bar = df.iloc[10]
    signal = strategy.on_bar(bar, bar_index=10, data=df.iloc[:11])
    
    # Should not crash, should use legacy calculation
    # No assertion on signal value (depends on data), just check it runs


def test_on_bar_long_signal_stop_loss_calculation():
    """✅ Test LONG signal stop loss is correctly calculated"""
    strategy = BollingerMeanReversionStrategy(config={'stop_loss_pct': 1.0})
    
    df = pd.DataFrame({
        'close': [49500] * 5,
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    # Stop loss should be 1% below entry
    expected_stop = 49500 * (1 - 0.01)
    assert signal['stop_loss'] == pytest.approx(expected_stop, rel=0.001)


def test_on_bar_short_signal_stop_loss_calculation():
    """✅ Test SHORT signal stop loss is correctly calculated"""
    strategy = BollingerMeanReversionStrategy(config={'stop_loss_pct': 1.0})
    
    df = pd.DataFrame({
        'close': [50500] * 5,
        'bb_upper': [50500] * 5,
        'bb_middle': [50000] * 5,
        'bb_lower': [49500] * 5
    })
    strategy.on_start(df)
    
    bar = df.iloc[-1]
    signal = strategy.on_bar(bar, bar_index=4, data=df)
    
    # Stop loss should be 1% above entry
    expected_stop = 50500 * (1 + 0.01)
    assert signal['stop_loss'] == pytest.approx(expected_stop, rel=0.001)


# ===========================
# TEST SUMMARY
# ===========================
# Total: 45 tests
# Categories:
#   1. Initialization: 8 tests
#   2. Default Parameters: 1 test
#   3. Config Validation: 9 tests
#   4. Bollinger Bands Calculation: 7 tests
#   5. on_start: 5 tests
#   6. on_bar Entry Signals: 6 tests
#   7. on_bar Exit Signals: 4 tests
#   8. Edge Cases: 5 tests
#
# Expected Coverage: 75% (target) of 147 statements
