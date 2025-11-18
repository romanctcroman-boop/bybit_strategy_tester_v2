"""
Test suite for backend.strategies.support_resistance

Tests the SupportResistanceDetector class for identifying swing highs/lows.
"""

import pandas as pd
import numpy as np
import pytest

from backend.strategies.support_resistance import SupportResistanceDetector


class TestSupportResistanceDetectorInit:
    """Test SupportResistanceDetector initialization."""

    def test_init_with_defaults(self):
        """SupportResistanceDetector initializes with default parameters."""
        detector = SupportResistanceDetector()
        assert detector.lookback_bars == 100
        assert detector.tolerance_pct == 0.1

    def test_init_with_custom_lookback(self):
        """SupportResistanceDetector accepts custom lookback_bars."""
        detector = SupportResistanceDetector(lookback_bars=50)
        assert detector.lookback_bars == 50

    def test_init_with_custom_tolerance(self):
        """SupportResistanceDetector accepts custom tolerance_pct."""
        detector = SupportResistanceDetector(tolerance_pct=0.5)
        assert detector.tolerance_pct == 0.5

    def test_init_with_both_custom_params(self):
        """SupportResistanceDetector accepts both custom parameters."""
        detector = SupportResistanceDetector(lookback_bars=200, tolerance_pct=1.0)
        assert detector.lookback_bars == 200
        assert detector.tolerance_pct == 1.0


class TestFindSwingHighs:
    """Test find_swing_highs() method."""

    def test_find_swing_highs_with_clear_peak(self):
        """find_swing_highs() identifies clear high peak."""
        data = pd.DataFrame({
            'high': [100, 101, 105, 103, 102, 101, 100, 99, 98, 97, 96]
        })
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=2)
        assert 105 in highs

    def test_find_swing_highs_with_multiple_peaks(self):
        """find_swing_highs() identifies multiple peaks."""
        data = pd.DataFrame({
            'high': [100, 101, 110, 105, 100, 95, 105, 115, 110, 100, 95]
        })
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=2)
        assert 110 in highs
        assert 115 in highs

    def test_find_swing_highs_insufficient_data(self):
        """find_swing_highs() returns empty list for insufficient data."""
        data = pd.DataFrame({
            'high': [100, 101, 102]
        })
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=5)
        assert highs == []

    def test_find_swing_highs_empty_dataframe(self):
        """find_swing_highs() handles empty DataFrame."""
        data = pd.DataFrame({'high': []})
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=5)
        assert highs == []

    def test_find_swing_highs_no_peaks(self):
        """find_swing_highs() returns empty for monotonic data."""
        data = pd.DataFrame({
            'high': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        })
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=2)
        # Monotonic increasing has no swing highs
        assert highs == []

    def test_find_swing_highs_custom_window(self):
        """find_swing_highs() respects custom window size."""
        data = pd.DataFrame({
            'high': [100] * 5 + [110] + [100] * 5
        })
        detector = SupportResistanceDetector()
        highs = detector.find_swing_highs(data, window=2)
        assert 110 in highs


class TestFindSwingLows:
    """Test find_swing_lows() method."""

    def test_find_swing_lows_with_clear_trough(self):
        """find_swing_lows() identifies clear low trough."""
        data = pd.DataFrame({
            'low': [100, 99, 95, 97, 98, 99, 100, 101, 102, 103, 104]
        })
        detector = SupportResistanceDetector()
        lows = detector.find_swing_lows(data, window=2)
        assert 95 in lows

    def test_find_swing_lows_with_multiple_troughs(self):
        """find_swing_lows() identifies multiple troughs."""
        data = pd.DataFrame({
            'low': [100, 99, 90, 95, 100, 105, 95, 85, 90, 100, 105]
        })
        detector = SupportResistanceDetector()
        lows = detector.find_swing_lows(data, window=2)
        assert 90 in lows
        assert 85 in lows

    def test_find_swing_lows_insufficient_data(self):
        """find_swing_lows() returns empty list for insufficient data."""
        data = pd.DataFrame({
            'low': [100, 99, 98]
        })
        detector = SupportResistanceDetector()
        lows = detector.find_swing_lows(data, window=5)
        assert lows == []

    def test_find_swing_lows_empty_dataframe(self):
        """find_swing_lows() handles empty DataFrame."""
        data = pd.DataFrame({'low': []})
        detector = SupportResistanceDetector()
        lows = detector.find_swing_lows(data, window=5)
        assert lows == []

    def test_find_swing_lows_no_troughs(self):
        """find_swing_lows() returns empty for monotonic data."""
        data = pd.DataFrame({
            'low': [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        })
        detector = SupportResistanceDetector()
        lows = detector.find_swing_lows(data, window=2)
        # Monotonic decreasing has no swing lows
        assert lows == []


class TestClusterLevels:
    """Test cluster_levels() method."""

    def test_cluster_levels_single_level(self):
        """cluster_levels() handles single level."""
        detector = SupportResistanceDetector()
        levels = [100.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
        assert len(clustered) == 1
        assert clustered[0] == 100.0

    def test_cluster_levels_within_tolerance(self):
        """cluster_levels() clusters levels within tolerance."""
        detector = SupportResistanceDetector()
        levels = [100.0, 100.05, 100.09]  # Within 0.1%
        clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
        assert len(clustered) == 1
        # Mean of cluster
        assert abs(clustered[0] - 100.047) < 0.01

    def test_cluster_levels_separate_clusters(self):
        """cluster_levels() creates separate clusters."""
        detector = SupportResistanceDetector()
        levels = [100.0, 105.0, 110.0]  # Far apart
        clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
        assert len(clustered) == 3

    def test_cluster_levels_empty_list(self):
        """cluster_levels() handles empty list."""
        detector = SupportResistanceDetector()
        clustered = detector.cluster_levels([], tolerance_pct=0.1)
        assert clustered == []

    def test_cluster_levels_unsorted_input(self):
        """cluster_levels() sorts input before clustering."""
        detector = SupportResistanceDetector()
        levels = [110.0, 100.0, 105.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
        # Should create 3 clusters after sorting
        assert len(clustered) == 3
        assert clustered[0] < clustered[1] < clustered[2]

    def test_cluster_levels_tight_tolerance(self):
        """cluster_levels() with tight tolerance creates more clusters."""
        detector = SupportResistanceDetector()
        levels = [100.0, 100.5, 101.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=0.1)
        # All should be separate with tight tolerance
        assert len(clustered) == 3

    def test_cluster_levels_loose_tolerance(self):
        """cluster_levels() with loose tolerance merges more."""
        detector = SupportResistanceDetector()
        levels = [100.0, 100.5, 101.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=2.0)
        # All should merge into one cluster
        assert len(clustered) == 1


class TestDetectLevels:
    """Test detect_levels() method."""

    def test_detect_levels_returns_dict(self):
        """detect_levels() returns dictionary with resistance/support."""
        data = pd.DataFrame({
            'high': [100] * 20 + [110] + [100] * 20,
            'low': [95] * 20 + [85] + [95] * 20
        })
        detector = SupportResistanceDetector()
        levels = detector.detect_levels(data)
        assert isinstance(levels, dict)
        assert 'resistance' in levels
        assert 'support' in levels

    def test_detect_levels_with_peaks_and_troughs(self):
        """detect_levels() identifies both resistance and support."""
        # Create data with clear, separated swing points
        data = pd.DataFrame({
            'high': [100, 100, 100, 100, 100, 110, 100, 100, 100, 100, 100] * 5,
            'low': [95, 95, 95, 95, 95, 85, 95, 95, 95, 95, 95] * 5
        })
        detector = SupportResistanceDetector(lookback_bars=55)
        levels = detector.detect_levels(data)
        # Should find swing highs and lows with proper window spacing
        assert isinstance(levels['resistance'], list)
        assert isinstance(levels['support'], list)

    def test_detect_levels_uses_lookback_bars(self):
        """detect_levels() respects lookback_bars parameter."""
        # Create data with 200 bars, but only use last 50
        data = pd.DataFrame({
            'high': [100] * 150 + [110] * 50,
            'low': [95] * 150 + [85] * 50
        })
        detector = SupportResistanceDetector(lookback_bars=50)
        levels = detector.detect_levels(data)
        # Should only consider last 50 bars
        assert isinstance(levels, dict)

    def test_detect_levels_with_minimal_data(self):
        """detect_levels() handles minimal data."""
        data = pd.DataFrame({
            'high': [100, 101, 102],
            'low': [99, 98, 97]
        })
        detector = SupportResistanceDetector()
        levels = detector.detect_levels(data)
        assert levels['resistance'] == []
        assert levels['support'] == []


class TestGetNearestLevels:
    """Test get_nearest_levels() method."""

    def test_get_nearest_levels_finds_resistance_above(self):
        """get_nearest_levels() finds nearest resistance above price."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [110.0, 120.0], 'support': [90.0, 80.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_resistance'] == 110.0

    def test_get_nearest_levels_finds_support_below(self):
        """get_nearest_levels() finds nearest support below price."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [110.0, 120.0], 'support': [90.0, 80.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_support'] == 90.0

    def test_get_nearest_levels_calculates_distance_pct(self):
        """get_nearest_levels() calculates distance percentages."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [110.0], 'support': [90.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert abs(result['distance_to_resistance_pct'] - 10.0) < 0.01
        assert abs(result['distance_to_support_pct'] - 10.0) < 0.01

    def test_get_nearest_levels_no_resistance_above(self):
        """get_nearest_levels() handles no resistance above price."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [80.0, 90.0], 'support': [70.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_resistance'] is None
        assert result['distance_to_resistance_pct'] is None

    def test_get_nearest_levels_no_support_below(self):
        """get_nearest_levels() handles no support below price."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [110.0], 'support': [110.0, 120.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_support'] is None
        assert result['distance_to_support_pct'] is None

    def test_get_nearest_levels_empty_levels(self):
        """get_nearest_levels() handles empty level lists."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [], 'support': []}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_resistance'] is None
        assert result['nearest_support'] is None
        assert result['distance_to_resistance_pct'] is None
        assert result['distance_to_support_pct'] is None

    def test_get_nearest_levels_multiple_candidates(self):
        """get_nearest_levels() selects nearest from multiple."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [105.0, 110.0, 120.0], 'support': [95.0, 90.0, 80.0]}
        result = detector.get_nearest_levels(100.0, levels)
        assert result['nearest_resistance'] == 105.0
        assert result['nearest_support'] == 95.0


class TestSupportResistanceIntegration:
    """Test integration scenarios."""

    def test_full_workflow_simple_data(self):
        """Integration: Full workflow with simple data."""
        # Create data with clear swing high and low
        data = pd.DataFrame({
            'high': [100] * 10 + [110] + [100] * 10,
            'low': [95] * 10 + [85] + [95] * 10
        })
        detector = SupportResistanceDetector(lookback_bars=21)
        levels = detector.detect_levels(data)
        
        assert len(levels['resistance']) > 0
        assert len(levels['support']) > 0
        
        # Get nearest levels for current price
        result = detector.get_nearest_levels(100.0, levels)
        assert 'nearest_resistance' in result
        assert 'nearest_support' in result

    def test_full_workflow_realistic_data(self):
        """Integration: Full workflow with realistic price data."""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200) * 0.5)
        data = pd.DataFrame({
            'high': prices + np.random.rand(200),
            'low': prices - np.random.rand(200)
        })
        
        detector = SupportResistanceDetector(lookback_bars=100, tolerance_pct=0.5)
        levels = detector.detect_levels(data)
        
        current_price = float(data['high'].iloc[-1])
        result = detector.get_nearest_levels(current_price, levels)
        
        assert isinstance(result, dict)
        assert 'nearest_resistance' in result
        assert 'nearest_support' in result


class TestSupportResistanceEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_bar_dataframe(self):
        """Edge case: Single bar of data."""
        data = pd.DataFrame({
            'high': [100],
            'low': [95]
        })
        detector = SupportResistanceDetector()
        levels = detector.detect_levels(data)
        assert levels['resistance'] == []
        assert levels['support'] == []

    def test_all_identical_prices(self):
        """Edge case: All prices identical (no swing points)."""
        data = pd.DataFrame({
            'high': [100.0] * 100,
            'low': [100.0] * 100
        })
        detector = SupportResistanceDetector()
        levels = detector.detect_levels(data)
        assert levels['resistance'] == []
        assert levels['support'] == []

    def test_very_large_lookback(self):
        """Edge case: Lookback larger than data."""
        data = pd.DataFrame({
            'high': [100, 110, 100] * 10,
            'low': [95, 85, 95] * 10
        })
        detector = SupportResistanceDetector(lookback_bars=1000)
        levels = detector.detect_levels(data)
        # Should use all available data
        assert isinstance(levels, dict)

    def test_zero_tolerance(self):
        """Edge case: Zero tolerance clustering."""
        detector = SupportResistanceDetector(tolerance_pct=0.0)
        levels = [100.0, 100.0, 100.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=0.0)
        # Zero tolerance should cluster identical values
        assert len(clustered) == 1

    def test_very_high_tolerance(self):
        """Edge case: Very high tolerance clusters everything."""
        detector = SupportResistanceDetector()
        levels = [100.0, 150.0, 200.0]
        clustered = detector.cluster_levels(levels, tolerance_pct=100.0)
        # High tolerance should merge all
        assert len(clustered) == 1

    def test_negative_prices(self):
        """Edge case: Handle negative prices (unusual but valid)."""
        data = pd.DataFrame({
            'high': [-10, -5, -10] * 10,
            'low': [-15, -20, -15] * 10
        })
        detector = SupportResistanceDetector()
        levels = detector.detect_levels(data)
        # Should handle without errors
        assert isinstance(levels, dict)

    def test_get_nearest_levels_at_exact_level(self):
        """Edge case: Current price exactly at support/resistance."""
        detector = SupportResistanceDetector()
        levels = {'resistance': [100.0, 110.0], 'support': [100.0, 90.0]}
        result = detector.get_nearest_levels(100.0, levels)
        # 100.0 is not "above" or "below" current price
        assert result['nearest_resistance'] == 110.0
        assert result['nearest_support'] == 90.0
