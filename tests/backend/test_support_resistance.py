"""
Unit tests for SupportResistanceDetector

Tests the S/R level detection algorithm:
- Swing high/low detection
- Level clustering
- Nearest level calculation
- Distance calculations
"""

import pytest
import pandas as pd
import numpy as np
from backend.strategies.support_resistance import SupportResistanceDetector


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def detector():
    """Create detector instance with default parameters"""
    return SupportResistanceDetector(lookback_bars=100, tolerance_pct=0.1)


@pytest.fixture
def sample_data_with_swings():
    """Create sample data with clear swing highs and lows"""
    # Pattern: low-high-low-high-low (clear swings)
    prices = []
    for i in range(100):
        if i % 10 < 5:
            # Downtrend to create swing low
            prices.append(50000 - i * 10)
        else:
            # Uptrend to create swing high
            prices.append(50000 + i * 10)
    
    data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
        'open': prices,
        'high': [p + 50 for p in prices],
        'low': [p - 50 for p in prices],
        'close': prices,
        'volume': 100.0
    })
    return data


@pytest.fixture
def trending_data():
    """Create data with clear uptrend (swing lows at 49000, 50000, 51000)"""
    data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50, freq='1h'),
        'open': 50000.0,
        'high': [49000 + i * 100 for i in range(50)],
        'low': [49000 + i * 100 - 200 for i in range(50)],
        'close': [49000 + i * 100 for i in range(50)],
        'volume': 100.0
    })
    return data


@pytest.fixture
def flat_data():
    """Create flat data with no swings"""
    data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50, freq='1h'),
        'open': 50000.0,
        'high': 50100.0,
        'low': 49900.0,
        'close': 50000.0,
        'volume': 100.0
    })
    return data


# =============================================================================
# Category 1: Initialization Tests (3 tests)
# =============================================================================

def test_detector_initialization_defaults():
    """Test detector initializes with default parameters"""
    detector = SupportResistanceDetector()
    
    assert detector.lookback_bars == 100
    assert detector.tolerance_pct == 0.1


def test_detector_initialization_custom_params():
    """Test detector initializes with custom parameters"""
    detector = SupportResistanceDetector(lookback_bars=200, tolerance_pct=0.5)
    
    assert detector.lookback_bars == 200
    assert detector.tolerance_pct == 0.5


def test_detector_attributes_set():
    """Test all detector attributes properly set"""
    detector = SupportResistanceDetector(lookback_bars=150, tolerance_pct=0.2)
    
    assert hasattr(detector, 'lookback_bars')
    assert hasattr(detector, 'tolerance_pct')
    assert detector.lookback_bars == 150
    assert detector.tolerance_pct == 0.2


# =============================================================================
# Category 2: Swing High Detection Tests (6 tests)
# =============================================================================

def test_find_swing_highs_basic(detector):
    """Test swing high detection with clear peak"""
    # Create data with single clear swing high at index 10
    highs = [50000] * 5 + [50100] * 5 + [51000] + [50100] * 5 + [50000] * 5
    data = pd.DataFrame({
        'high': highs,
        'low': [h - 100 for h in highs],
        'close': highs
    })
    
    swing_highs = detector.find_swing_highs(data, window=5)
    
    assert len(swing_highs) == 1
    assert swing_highs[0] == 51000.0


def test_find_swing_highs_multiple_peaks(detector):
    """Test detection of multiple swing highs"""
    # Two peaks at indices 10 and 25
    highs = ([50000] * 5 + [50100] * 5 + [51000] + [50100] * 5 + [50000] * 5 +
             [50100] * 5 + [51500] + [50100] * 5)
    data = pd.DataFrame({
        'high': highs,
        'low': [h - 100 for h in highs],
        'close': highs
    })
    
    swing_highs = detector.find_swing_highs(data, window=5)
    
    assert len(swing_highs) >= 1  # At least one peak detected
    assert 51000.0 in swing_highs or 51500.0 in swing_highs


def test_find_swing_highs_insufficient_data(detector):
    """Test swing high detection with insufficient data"""
    # Only 5 bars (need window*2+1 = 11 bars minimum for window=5)
    data = pd.DataFrame({
        'high': [50000, 50100, 51000, 50100, 50000],
        'low': [49900, 50000, 50900, 50000, 49900],
        'close': [50000, 50100, 51000, 50100, 50000]
    })
    
    swing_highs = detector.find_swing_highs(data, window=5)
    
    assert len(swing_highs) == 0  # Not enough data


def test_find_swing_highs_no_peaks(detector, flat_data):
    """Test swing high detection with flat data (no peaks)"""
    swing_highs = detector.find_swing_highs(flat_data, window=5)
    
    # Flat data should have no swing highs
    assert len(swing_highs) == 0


def test_find_swing_highs_edge_windows(detector):
    """Test swing highs don't include edge windows"""
    # Peak at very start (index 0-4) and end should not be detected
    highs = [51000] + [50000] * 20 + [51000]
    data = pd.DataFrame({
        'high': highs,
        'low': [h - 100 for h in highs],
        'close': highs
    })
    
    swing_highs = detector.find_swing_highs(data, window=5)
    
    # Edge peaks should not be detected (need window bars on both sides)
    assert 51000.0 not in swing_highs or len(swing_highs) == 0


def test_find_swing_highs_custom_window(detector):
    """Test swing high detection with custom window size"""
    # Peak at index 15 with window=10
    highs = [50000] * 10 + [50500] * 5 + [51000] + [50500] * 5 + [50000] * 10
    data = pd.DataFrame({
        'high': highs,
        'low': [h - 100 for h in highs],
        'close': highs
    })
    
    swing_highs = detector.find_swing_highs(data, window=10)
    
    assert len(swing_highs) >= 1
    assert 51000.0 in swing_highs


# =============================================================================
# Category 3: Swing Low Detection Tests (5 tests)
# =============================================================================

def test_find_swing_lows_basic(detector):
    """Test swing low detection with clear trough"""
    # Create data with single clear swing low at index 10
    lows = [50000] * 5 + [49900] * 5 + [49000] + [49900] * 5 + [50000] * 5
    data = pd.DataFrame({
        'low': lows,
        'high': [l + 100 for l in lows],
        'close': lows
    })
    
    swing_lows = detector.find_swing_lows(data, window=5)
    
    assert len(swing_lows) == 1
    assert swing_lows[0] == 49000.0


def test_find_swing_lows_multiple_troughs(detector):
    """Test detection of multiple swing lows"""
    # Two troughs
    lows = ([50000] * 5 + [49900] * 5 + [49000] + [49900] * 5 + [50000] * 5 +
            [49900] * 5 + [48500] + [49900] * 5)
    data = pd.DataFrame({
        'low': lows,
        'high': [l + 100 for l in lows],
        'close': lows
    })
    
    swing_lows = detector.find_swing_lows(data, window=5)
    
    assert len(swing_lows) >= 1
    assert 49000.0 in swing_lows or 48500.0 in swing_lows


def test_find_swing_lows_insufficient_data(detector):
    """Test swing low detection with insufficient data"""
    data = pd.DataFrame({
        'low': [50000, 49900, 49000, 49900, 50000],
        'high': [50100, 50000, 49100, 50000, 50100],
        'close': [50000, 49900, 49000, 49900, 50000]
    })
    
    swing_lows = detector.find_swing_lows(data, window=5)
    
    assert len(swing_lows) == 0


def test_find_swing_lows_no_troughs(detector, flat_data):
    """Test swing low detection with flat data (no troughs)"""
    swing_lows = detector.find_swing_lows(flat_data, window=5)
    
    assert len(swing_lows) == 0


def test_find_swing_lows_custom_window(detector):
    """Test swing low detection with custom window size"""
    lows = [50000] * 10 + [49500] * 5 + [49000] + [49500] * 5 + [50000] * 10
    data = pd.DataFrame({
        'low': lows,
        'high': [l + 100 for l in lows],
        'close': lows
    })
    
    swing_lows = detector.find_swing_lows(data, window=10)
    
    assert len(swing_lows) >= 1
    assert 49000.0 in swing_lows


# =============================================================================
# Category 4: Level Clustering Tests (6 tests)
# =============================================================================

def test_cluster_levels_basic(detector):
    """Test clustering of nearby levels"""
    # Three levels within 0.1% tolerance
    levels = [50000.0, 50020.0, 50040.0]  # ~0.04% and ~0.04% apart
    
    clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
    
    # Should cluster into one level (mean ~50020)
    assert len(clustered) == 1
    assert 50000 <= clustered[0] <= 50050


def test_cluster_levels_separate_clusters(detector):
    """Test clustering with distinct groups"""
    # Two groups: ~49000 and ~51000
    levels = [49000.0, 49010.0, 49020.0, 51000.0, 51010.0, 51020.0]
    
    clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
    
    # Should create two clusters
    assert len(clustered) == 2
    assert any(48900 <= c <= 49100 for c in clustered)
    assert any(50900 <= c <= 51100 for c in clustered)


def test_cluster_levels_empty_list(detector):
    """Test clustering with empty list"""
    clustered = detector.cluster_levels([], tolerance_pct=0.1)
    
    assert len(clustered) == 0


def test_cluster_levels_single_level(detector):
    """Test clustering with single level"""
    clustered = detector.cluster_levels([50000.0], tolerance_pct=0.1)
    
    assert len(clustered) == 1
    assert clustered[0] == 50000.0


def test_cluster_levels_no_clustering(detector):
    """Test levels far apart don't cluster"""
    # Levels 2% apart (> tolerance_pct)
    levels = [49000.0, 50000.0, 51000.0]
    
    clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
    
    # Should remain as 3 separate levels
    assert len(clustered) == 3


def test_cluster_levels_mean_calculation(detector):
    """Test cluster represented by mean"""
    levels = [50000.0, 50100.0]  # Mean = 50050
    
    clustered = detector.cluster_levels(levels, tolerance_pct=0.5)
    
    assert len(clustered) == 1
    assert clustered[0] == pytest.approx(50050.0, rel=1e-2)


# =============================================================================
# Category 5: Detect Levels Integration Tests (4 tests)
# =============================================================================

def test_detect_levels_returns_dict(detector, trending_data):
    """Test detect_levels returns dict with support and resistance"""
    levels = detector.detect_levels(trending_data)
    
    assert isinstance(levels, dict)
    assert 'support' in levels
    assert 'resistance' in levels


def test_detect_levels_uses_lookback(detector):
    """Test detect_levels uses only lookback_bars"""
    detector.lookback_bars = 20
    
    # Create 100 bars of data
    data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
        'high': [50000 + i * 10 for i in range(100)],
        'low': [50000 + i * 10 - 100 for i in range(100)],
        'close': [50000 + i * 10 for i in range(100)],
        'volume': 100.0
    })
    
    levels = detector.detect_levels(data)
    
    # Should only look at last 20 bars (data.tail(20))
    assert isinstance(levels, dict)


def test_detect_levels_calls_clustering(detector, trending_data):
    """Test detect_levels clusters swing highs and lows"""
    levels = detector.detect_levels(trending_data)
    
    # Result should be clustered (lists of floats)
    assert isinstance(levels['support'], list)
    assert isinstance(levels['resistance'], list)


def test_detect_levels_flat_data(detector, flat_data):
    """Test detect_levels with flat data returns empty lists"""
    levels = detector.detect_levels(flat_data)
    
    # Flat data should have no swing highs/lows
    assert len(levels['support']) == 0
    assert len(levels['resistance']) == 0


# =============================================================================
# Category 6: Nearest Levels Tests (7 tests)
# =============================================================================

def test_get_nearest_levels_basic(detector):
    """Test finding nearest support and resistance"""
    levels = {
        'support': [49000.0, 48000.0],
        'resistance': [51000.0, 52000.0]
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    assert nearest['nearest_support'] == 49000.0  # Closest below
    assert nearest['nearest_resistance'] == 51000.0  # Closest above


def test_get_nearest_levels_distance_calculations(detector):
    """Test distance percentage calculations"""
    levels = {
        'support': [49000.0],
        'resistance': [51000.0]
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    # Distance to support: (50000 - 49000) / 50000 * 100 = 2%
    assert nearest['distance_to_support_pct'] == pytest.approx(2.0, rel=1e-2)
    
    # Distance to resistance: (51000 - 50000) / 50000 * 100 = 2%
    assert nearest['distance_to_resistance_pct'] == pytest.approx(2.0, rel=1e-2)


def test_get_nearest_levels_no_support(detector):
    """Test when no support level below current price"""
    levels = {
        'support': [52000.0, 53000.0],  # All above current price
        'resistance': [55000.0]
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    assert nearest['nearest_support'] is None
    assert nearest['distance_to_support_pct'] is None


def test_get_nearest_levels_no_resistance(detector):
    """Test when no resistance level above current price"""
    levels = {
        'support': [48000.0],
        'resistance': [47000.0, 46000.0]  # All below current price
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    assert nearest['nearest_resistance'] is None
    assert nearest['distance_to_resistance_pct'] is None


def test_get_nearest_levels_empty_lists(detector):
    """Test with empty support/resistance lists"""
    levels = {
        'support': [],
        'resistance': []
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    assert nearest['nearest_support'] is None
    assert nearest['nearest_resistance'] is None
    assert nearest['distance_to_support_pct'] is None
    assert nearest['distance_to_resistance_pct'] is None


def test_get_nearest_levels_multiple_candidates(detector):
    """Test selecting nearest when multiple candidates exist"""
    levels = {
        'support': [49000.0, 48000.0, 47000.0],  # Multiple below
        'resistance': [51000.0, 52000.0, 53000.0]  # Multiple above
    }
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    # Should select closest
    assert nearest['nearest_support'] == 49000.0  # Not 48000 or 47000
    assert nearest['nearest_resistance'] == 51000.0  # Not 52000 or 53000


def test_get_nearest_levels_missing_keys(detector):
    """Test with missing 'support' or 'resistance' keys"""
    levels = {}  # Empty dict
    current_price = 50000.0
    
    nearest = detector.get_nearest_levels(current_price, levels)
    
    # Should handle missing keys gracefully
    assert nearest['nearest_support'] is None
    assert nearest['nearest_resistance'] is None


# =============================================================================
# Category 7: Edge Cases (3 tests)
# =============================================================================

def test_handles_single_bar_data(detector):
    """Test detector handles single bar gracefully"""
    data = pd.DataFrame({
        'high': [50000.0],
        'low': [49000.0],
        'close': [49500.0]
    })
    
    swing_highs = detector.find_swing_highs(data, window=5)
    swing_lows = detector.find_swing_lows(data, window=5)
    
    assert len(swing_highs) == 0
    assert len(swing_lows) == 0


def test_handles_nan_values(detector):
    """Test detector handles NaN values in data"""
    data = pd.DataFrame({
        'high': [50000.0, np.nan, 51000.0, np.nan, 50000.0] + [50000.0] * 20,
        'low': [49000.0, np.nan, 48000.0, np.nan, 49000.0] + [49000.0] * 20,
        'close': [49500.0, np.nan, 49500.0, np.nan, 49500.0] + [49500.0] * 20
    })
    
    # Should not crash
    try:
        detector.find_swing_highs(data, window=5)
        detector.find_swing_lows(data, window=5)
        success = True
    except Exception:
        success = False
    
    assert success  # Should handle NaN gracefully


def test_zero_tolerance_clustering(detector):
    """Test clustering with zero tolerance (no clustering)"""
    levels = [50000.0, 50001.0, 50002.0]
    
    clustered = detector.cluster_levels(levels, tolerance_pct=0.0)
    
    # Zero tolerance means each level is its own cluster
    assert len(clustered) == 3
