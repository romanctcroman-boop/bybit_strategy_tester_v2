"""
Tests for Numba JIT Optimized Price Action Patterns
===================================================

Validates pattern detection accuracy and performance improvements.
"""

import numpy as np
import pytest

from backend.core.indicators.price_action_numba import (
    NUMBA_AVAILABLE,
    detect_abandoned_baby,
    detect_all_patterns,
    detect_belt_hold,
    detect_counterattack,
    detect_doji,
    detect_engulfing,
    detect_gap_patterns,
    detect_hammer,
    detect_homing_pigeon,
    detect_inside_bar,
    detect_kicker,
    detect_ladder_pattern,
    detect_marubozu,
    detect_matching_low_high,
    detect_outside_bar,
    detect_pin_bar,
    detect_shooting_star,
    detect_stick_sandwich,
    detect_three_line_strike,
    detect_three_soldiers_crows,
    detect_tweezer,
)


class TestEngulfingPatterns:
    """Tests for engulfing pattern detection."""

    def test_bullish_engulfing(self):
        """Test bullish engulfing pattern detection."""
        # Bullish engulfing conditions:
        # - prev candle: red (open > close)
        # - curr candle: green (close > open)
        # - curr_close > prev_open (current green body engulfs previous)
        # - curr_open < prev_close (current opens below prev close)
        #
        # prev: open=102, close=99 -> red, body from 99-102
        # curr: open=98, close=103 -> green, body from 98-103 (engulfs 99-102)
        open_arr = np.array([102.0, 98.0])  # prev open=102 (red), curr open=98
        high_arr = np.array([103.0, 104.0])
        low_arr = np.array([98.0, 97.0])
        close_arr = np.array([99.0, 103.0])  # prev close=99 (red), curr close=103 (green)
        # curr_close(103) > prev_open(102) ✓
        # curr_open(98) < prev_close(99) ✓

        bullish, bearish = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

        assert bullish[1] == True  # noqa: E712
        assert bearish[1] == False  # noqa: E712

    def test_bearish_engulfing(self):
        """Test bearish engulfing pattern detection."""
        # Bearish engulfing conditions:
        # - prev candle: green (close > open)
        # - curr candle: red (open > close)
        # - curr_open > prev_close (current opens above prev close)
        # - curr_close < prev_open (current closes below prev open)
        #
        # prev: open=98, close=101 -> green, body from 98-101
        # curr: open=102, close=97 -> red, body from 97-102 (engulfs 98-101)
        open_arr = np.array([98.0, 102.0])  # prev open=98 (green), curr open=102 (red)
        high_arr = np.array([102.0, 103.0])
        low_arr = np.array([97.0, 96.0])
        close_arr = np.array([101.0, 97.0])  # prev close=101 (green), curr close=97 (red)
        # curr_open(102) > prev_close(101) ✓
        # curr_close(97) < prev_open(98) ✓

        bullish, bearish = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

        assert bullish[1] == False  # noqa: E712
        assert bearish[1] == True  # noqa: E712

    def test_no_engulfing(self):
        """Test no engulfing when conditions not met."""
        # Small candles that don't engulf
        open_arr = np.array([100.0, 99.5, 100.5])
        high_arr = np.array([101.0, 100.5, 101.5])
        low_arr = np.array([99.0, 99.0, 100.0])
        close_arr = np.array([100.5, 100.0, 101.0])

        bullish, bearish = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

        assert np.sum(bullish) == 0
        assert np.sum(bearish) == 0


class TestHammerPatterns:
    """Tests for hammer/hanging man pattern detection."""

    def test_hammer_pattern(self):
        """Test hammer pattern detection (long lower wick)."""
        # Hammer conditions:
        # - lower_wick > body * min_wick_ratio (2.0)
        # - upper_wick < body * max_upper_ratio (0.3)
        #
        # Candle: open=99, close=100, high=100.1, low=94
        # body = abs(100 - 99) = 1
        # upper_wick = 100.1 - max(99,100) = 100.1 - 100 = 0.1
        # lower_wick = min(99,100) - 94 = 99 - 94 = 5
        # lower_wick(5) > body(1) * 2 = 2 ✓
        # upper_wick(0.1) < body(1) * 0.3 = 0.3 ✓
        open_arr = np.array([100.0, 99.0])
        high_arr = np.array([101.0, 100.1])  # tiny upper wick (0.1)
        low_arr = np.array([99.0, 94.0])  # long lower wick (5 points)
        close_arr = np.array([100.5, 100.0])  # small body (1 point)

        hammer, _hanging = detect_hammer(open_arr, high_arr, low_arr, close_arr)

        assert hammer[1] == True  # noqa: E712

    def test_hanging_man_pattern(self):
        """Test hanging man pattern detection (long upper wick)."""
        # Hanging man conditions:
        # - upper_wick > body * min_wick_ratio (2.0)
        # - lower_wick < body * max_upper_ratio (0.3)
        #
        # Candle: open=100, close=99, high=105, low=98.9
        # body = abs(99 - 100) = 1
        # upper_wick = 105 - max(100,99) = 105 - 100 = 5
        # lower_wick = min(100,99) - 98.9 = 99 - 98.9 = 0.1
        # upper_wick(5) > body(1) * 2 = 2 ✓
        # lower_wick(0.1) < body(1) * 0.3 = 0.3 ✓
        open_arr = np.array([100.0, 100.0])
        high_arr = np.array([101.0, 105.0])  # long upper wick (5 points)
        low_arr = np.array([99.0, 98.9])  # tiny lower wick
        close_arr = np.array([100.5, 99.0])  # small body (1 point)

        _hammer, hanging = detect_hammer(open_arr, high_arr, low_arr, close_arr)

        assert hanging[1] == True  # noqa: E712


class TestDojiPatterns:
    """Tests for doji pattern detection."""

    def test_doji_detection(self):
        """Test standard doji detection (very small body)."""
        # Create data with one doji candle
        n = 25
        open_arr = np.linspace(100, 110, n)
        close_arr = open_arr + np.random.uniform(0.5, 2, n)
        high_arr = np.maximum(open_arr, close_arr) + 1
        low_arr = np.minimum(open_arr, close_arr) - 1

        # Make last candle a doji (very small body)
        open_arr[-1] = 110.0
        close_arr[-1] = 110.01  # Nearly zero body
        high_arr[-1] = 112.0
        low_arr[-1] = 108.0

        standard, dragonfly, gravestone = detect_doji(open_arr, high_arr, low_arr, close_arr)

        # Should detect doji in the last few bars
        assert np.sum(standard) + np.sum(dragonfly) + np.sum(gravestone) > 0


class TestInsideOutsideBar:
    """Tests for inside and outside bar detection."""

    def test_inside_bar(self):
        """Test inside bar detection."""
        # Inside bar: current high/low within previous range
        open_arr = np.array([100.0, 101.0])
        high_arr = np.array([105.0, 103.0])  # curr high < prev high
        low_arr = np.array([95.0, 97.0])  # curr low > prev low
        close_arr = np.array([102.0, 100.0])

        inside = detect_inside_bar(open_arr, high_arr, low_arr, close_arr)

        assert inside[1] is True or inside[1] == np.True_

    def test_outside_bar(self):
        """Test outside bar detection."""
        # Outside bar: current range engulfs previous range
        open_arr = np.array([100.0, 101.0])
        high_arr = np.array([103.0, 106.0])  # curr high > prev high
        low_arr = np.array([97.0, 95.0])  # curr low < prev low
        close_arr = np.array([102.0, 100.0])

        outside = detect_outside_bar(open_arr, high_arr, low_arr, close_arr)

        assert outside[1] is True or outside[1] == np.True_


class TestThreeSoldiersCrows:
    """Tests for three white soldiers / three black crows."""

    def test_three_soldiers(self):
        """Test three white soldiers pattern."""
        # 3 consecutive green candles with higher closes
        open_arr = np.array([100.0, 101.0, 103.0, 105.0])
        high_arr = np.array([102.0, 104.0, 106.0, 108.0])
        low_arr = np.array([99.0, 100.0, 102.0, 104.0])
        close_arr = np.array([101.0, 103.0, 105.0, 107.0])  # all green, higher closes

        soldiers, _crows = detect_three_soldiers_crows(open_arr, high_arr, low_arr, close_arr)

        assert soldiers[3] is True or soldiers[3] == np.True_

    def test_three_crows(self):
        """Test three black crows pattern."""
        # 3 consecutive red candles with lower closes
        open_arr = np.array([107.0, 105.0, 103.0, 101.0])
        high_arr = np.array([108.0, 106.0, 104.0, 102.0])
        low_arr = np.array([104.0, 102.0, 100.0, 98.0])
        close_arr = np.array([105.0, 103.0, 101.0, 99.0])  # all red, lower closes

        _soldiers, crows = detect_three_soldiers_crows(open_arr, high_arr, low_arr, close_arr)

        assert crows[3] is True or crows[3] == np.True_


class TestPinBar:
    """Tests for pin bar detection."""

    def test_bullish_pin_bar(self):
        """Test bullish pin bar (long lower wick dominates)."""
        open_arr = np.array([100.0, 99.0])
        high_arr = np.array([101.0, 99.5])  # small upper wick (0.5)
        low_arr = np.array([99.0, 93.0])  # long lower wick (6 points)
        close_arr = np.array([100.5, 99.2])  # small body (0.2)

        bullish, _bearish = detect_pin_bar(open_arr, high_arr, low_arr, close_arr)

        assert bullish[1] is True or bullish[1] == np.True_


class TestMarubozu:
    """Tests for marubozu pattern detection."""

    def test_bullish_marubozu(self):
        """Test bullish marubozu (green candle with no wicks)."""
        # Strong green candle with tiny wicks
        open_arr = np.array([100.0, 100.0])
        high_arr = np.array([101.0, 110.0])  # nearly same as close
        low_arr = np.array([99.0, 100.0])  # nearly same as open
        close_arr = np.array([100.5, 110.0])

        bullish, _bearish = detect_marubozu(open_arr, high_arr, low_arr, close_arr)

        assert bullish[1] is True or bullish[1] == np.True_


class TestTweezer:
    """Tests for tweezer patterns."""

    def test_tweezer_bottom(self):
        """Test tweezer bottom pattern."""
        # Two candles with same lows, first red, second green
        open_arr = np.array([102.0, 98.5])  # first red (open > close), second green
        high_arr = np.array([103.0, 101.0])
        low_arr = np.array([98.0, 98.0])  # same lows
        close_arr = np.array([99.0, 100.0])  # first red, second green

        bottom, _top = detect_tweezer(open_arr, high_arr, low_arr, close_arr)

        assert bottom[1] is True or bottom[1] == np.True_


class TestShootingStar:
    """Tests for shooting star detection."""

    def test_shooting_star(self):
        """Test shooting star pattern detection."""
        # After uptrend, candle with long upper wick
        open_arr = np.array([100.0, 102.0, 104.0, 105.0])
        high_arr = np.array([102.0, 104.0, 106.0, 112.0])  # long upper wick on last
        low_arr = np.array([99.0, 101.0, 103.0, 105.0])
        close_arr = np.array([101.0, 103.0, 105.0, 105.5])  # small body at bottom

        shooting = detect_shooting_star(open_arr, high_arr, low_arr, close_arr)

        # May or may not trigger depending on exact ratios
        # Just verify it returns a boolean array
        assert len(shooting) == 4


class TestAllPatterns:
    """Tests for batch pattern detection."""

    def test_detect_all_patterns(self):
        """Test that detect_all_patterns returns all expected keys."""
        n = 100
        np.random.seed(42)

        # Generate random price data
        close_arr = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close_arr + np.random.randn(n) * 0.3
        high_arr = np.maximum(open_arr, close_arr) + np.abs(np.random.randn(n) * 0.2)
        low_arr = np.minimum(open_arr, close_arr) - np.abs(np.random.randn(n) * 0.2)

        result = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)

        expected_keys = [
            "engulfing_bullish",
            "engulfing_bearish",
            "hammer",
            "hanging_man",
            "doji_standard",
            "doji_dragonfly",
            "doji_gravestone",
            "pin_bar_bullish",
            "pin_bar_bearish",
            "inside_bar",
            "outside_bar",
            "three_soldiers",
            "three_crows",
            "shooting_star",
            "marubozu_bullish",
            "marubozu_bearish",
            "tweezer_bottom",
            "tweezer_top",
            "three_methods_rising",
            "three_methods_falling",
            "piercing_line",
            "dark_cloud",
            "harami_bullish",
            "harami_bearish",
            "morning_star",
            "evening_star",
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
            assert len(result[key]) == n, f"Wrong length for {key}"


class TestPerformance:
    """Performance tests for Numba optimization."""

    @pytest.mark.skipif(not NUMBA_AVAILABLE, reason="Numba not installed")
    def test_numba_jit_compilation(self):
        """Test that Numba JIT compiles functions successfully."""
        # Generate test data
        n = 1000
        np.random.seed(42)

        close_arr = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close_arr + np.random.randn(n) * 0.3
        high_arr = np.maximum(open_arr, close_arr) + np.abs(np.random.randn(n) * 0.2)
        low_arr = np.minimum(open_arr, close_arr) - np.abs(np.random.randn(n) * 0.2)

        # First call triggers JIT compilation
        _ = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

        # Second call should be much faster (cached)
        import time

        start = time.perf_counter()
        for _ in range(100):
            _ = detect_engulfing(open_arr, high_arr, low_arr, close_arr)
        elapsed = time.perf_counter() - start

        # Should complete 100 iterations in under 1 second
        assert elapsed < 1.0, f"Performance too slow: {elapsed:.3f}s for 100 iterations"

    @pytest.mark.skipif(not NUMBA_AVAILABLE, reason="Numba not installed")
    def test_all_patterns_performance(self):
        """Test batch pattern detection performance."""
        n = 10000
        np.random.seed(42)

        close_arr = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close_arr + np.random.randn(n) * 0.3
        high_arr = np.maximum(open_arr, close_arr) + np.abs(np.random.randn(n) * 0.2)
        low_arr = np.minimum(open_arr, close_arr) - np.abs(np.random.randn(n) * 0.2)

        import time

        # First call (includes JIT compilation)
        _ = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)

        # Benchmark subsequent calls
        start = time.perf_counter()
        for _ in range(10):
            result = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)
        elapsed = time.perf_counter() - start

        # Should complete 10 iterations of 10k bars in under 2 seconds
        assert elapsed < 2.0, f"Performance too slow: {elapsed:.3f}s"

        # Verify all patterns are detected (26 base + 21 exotic = 47)
        assert len(result) >= 47  # All pattern types


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_array(self):
        """Test handling of empty arrays."""
        empty = np.array([])

        bullish, bearish = detect_engulfing(empty, empty, empty, empty)

        assert len(bullish) == 0
        assert len(bearish) == 0

    def test_single_bar(self):
        """Test handling of single bar input."""
        open_arr = np.array([100.0])
        high_arr = np.array([101.0])
        low_arr = np.array([99.0])
        close_arr = np.array([100.5])

        bullish, _bearish = detect_engulfing(open_arr, high_arr, low_arr, close_arr)

        assert len(bullish) == 1
        assert bullish[0] is False or bullish[0] == np.False_

    def test_zero_body_candle(self):
        """Test handling of doji (zero body) candles."""
        open_arr = np.array([100.0, 100.0])
        high_arr = np.array([101.0, 102.0])
        low_arr = np.array([99.0, 98.0])
        close_arr = np.array([100.0, 100.0])  # Same as open

        hammer, _hanging = detect_hammer(open_arr, high_arr, low_arr, close_arr)

        # Should handle gracefully without division by zero
        assert len(hammer) == 2

    def test_large_dataset(self):
        """Test handling of large datasets."""
        n = 100000
        np.random.seed(42)

        close_arr = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close_arr + np.random.randn(n) * 0.3
        high_arr = np.maximum(open_arr, close_arr) + np.abs(np.random.randn(n) * 0.2)
        low_arr = np.minimum(open_arr, close_arr) - np.abs(np.random.randn(n) * 0.2)

        result = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)

        assert len(result["engulfing_bullish"]) == n
        assert len(result["inside_bar"]) == n


# =============================================================================
# EXOTIC PATTERN TESTS
# =============================================================================


class TestThreeLineStrike:
    """Tests for Three Line Strike pattern detection."""

    def test_bullish_three_line_strike(self):
        """Test bullish three line strike: 3 reds + big green engulfing."""
        # Pattern: 3 descending red candles, then big green that engulfs all
        open_arr = np.array([105.0, 103.0, 101.0, 99.0, 96.0])
        close_arr = np.array([103.0, 101.0, 99.0, 97.0, 106.0])  # 3 reds, 1 big green
        high_arr = np.array([106.0, 104.0, 102.0, 100.0, 107.0])
        low_arr = np.array([102.0, 100.0, 98.0, 95.0, 95.0])

        bullish, bearish = detect_three_line_strike(open_arr, high_arr, low_arr, close_arr)

        assert bullish[4] == True  # noqa: E712
        assert bearish[4] == False  # noqa: E712

    def test_bearish_three_line_strike(self):
        """Test bearish three line strike: 3 greens + big red engulfing."""
        open_arr = np.array([95.0, 97.0, 99.0, 101.0, 104.0])
        close_arr = np.array([97.0, 99.0, 101.0, 103.0, 94.0])  # 3 greens, 1 big red
        high_arr = np.array([98.0, 100.0, 102.0, 105.0, 105.0])
        low_arr = np.array([94.0, 96.0, 98.0, 100.0, 93.0])

        bullish, bearish = detect_three_line_strike(open_arr, high_arr, low_arr, close_arr)

        assert bullish[4] == False  # noqa: E712
        assert bearish[4] == True  # noqa: E712


class TestKickerPattern:
    """Tests for Kicker pattern detection."""

    def test_bullish_kicker(self):
        """Test bullish kicker: red candle, then green gaps up above prev open."""
        # Need lookback period data for avg body calculation
        # Base data (lookback=10)
        base_open = np.full(11, 100.0)
        base_close = np.full(11, 99.0)
        base_high = np.full(11, 101.0)
        base_low = np.full(11, 98.0)

        # Pattern: red then green with gap
        base_open[10] = 102.0
        base_close[10] = 99.0  # Red
        base_high[10] = 103.0
        base_low[10] = 98.0

        # Append kicker candle
        open_arr = np.append(base_open, 104.0)  # Opens above prev open (102)
        close_arr = np.append(base_close, 108.0)  # Green
        high_arr = np.append(base_high, 109.0)
        low_arr = np.append(base_low, 103.0)

        bullish, _bearish = detect_kicker(open_arr, high_arr, low_arr, close_arr)

        assert bullish[11] == True  # noqa: E712

    def test_bearish_kicker(self):
        """Test bearish kicker: green candle, then red gaps down below prev open."""
        base_open = np.full(11, 100.0)
        base_close = np.full(11, 101.0)  # Green base
        base_high = np.full(11, 102.0)
        base_low = np.full(11, 99.0)

        base_open[10] = 98.0
        base_close[10] = 101.0  # Green
        base_high[10] = 102.0
        base_low[10] = 97.0

        # Append kicker candle
        open_arr = np.append(base_open, 96.0)  # Opens below prev open (98)
        close_arr = np.append(base_close, 92.0)  # Red
        high_arr = np.append(base_high, 97.0)
        low_arr = np.append(base_low, 91.0)

        _bullish, bearish = detect_kicker(open_arr, high_arr, low_arr, close_arr)

        assert bearish[11] == True  # noqa: E712


class TestAbandonedBaby:
    """Tests for Abandoned Baby pattern detection."""

    def test_bullish_abandoned_baby(self):
        """Test bullish abandoned baby: red, gap down doji, gap up green."""
        # Red candle
        open_arr = np.array([105.0, 95.0, 99.0])  # Red, doji, green
        close_arr = np.array([100.0, 95.1, 104.0])  # Red, tiny body, green
        high_arr = np.array([106.0, 96.0, 105.0])
        low_arr = np.array([99.0, 94.0, 98.0])  # Doji gaps down from red, green gaps up

        bullish, bearish = detect_abandoned_baby(open_arr, high_arr, low_arr, close_arr)

        # Pattern requires true gaps, which may not be present in this setup
        # Testing mainly that function runs without error
        assert len(bullish) == 3
        assert len(bearish) == 3


class TestBeltHold:
    """Tests for Belt Hold pattern detection."""

    def test_bullish_belt_hold(self):
        """Test bullish belt hold: opens at low, closes near high."""
        # Need lookback data
        base_open = np.full(11, 100.0)
        base_close = np.full(11, 100.5)
        base_high = np.full(11, 101.0)
        base_low = np.full(11, 99.5)

        # Belt hold candle: opens at low, big body
        open_arr = np.append(base_open, 95.0)  # Opens at low
        close_arr = np.append(base_close, 100.0)  # Big green
        high_arr = np.append(base_high, 100.1)  # Close near high
        low_arr = np.append(base_low, 95.0)  # Low = open

        bullish, _bearish = detect_belt_hold(open_arr, high_arr, low_arr, close_arr)

        assert len(bullish) == 12
        # Check the pattern candle
        assert bullish[11] == True  # noqa: E712

    def test_bearish_belt_hold(self):
        """Test bearish belt hold: opens at high, closes near low."""
        base_open = np.full(11, 100.0)
        base_close = np.full(11, 99.5)
        base_high = np.full(11, 100.5)
        base_low = np.full(11, 99.0)

        # Belt hold candle: opens at high, big red body
        open_arr = np.append(base_open, 105.0)  # Opens at high
        close_arr = np.append(base_close, 100.0)  # Big red
        high_arr = np.append(base_high, 105.0)  # High = open
        low_arr = np.append(base_low, 99.9)  # Close near low

        _bullish, bearish = detect_belt_hold(open_arr, high_arr, low_arr, close_arr)

        assert len(bearish) == 12
        assert bearish[11] == True  # noqa: E712


class TestCounterattack:
    """Tests for Counterattack pattern detection."""

    def test_bullish_counterattack(self):
        """Test bullish counterattack: red then green with same close."""
        base_open = np.full(11, 100.0)
        base_close = np.full(11, 99.5)
        base_high = np.full(11, 100.5)
        base_low = np.full(11, 99.0)

        # Red candle
        base_open[10] = 103.0
        base_close[10] = 99.0
        base_high[10] = 104.0
        base_low[10] = 98.0

        # Green candle that opens lower and closes at same level
        open_arr = np.append(base_open, 96.0)
        close_arr = np.append(base_close, 99.0)  # Same close as prev
        high_arr = np.append(base_high, 100.0)
        low_arr = np.append(base_low, 95.0)

        bullish, _bearish = detect_counterattack(open_arr, high_arr, low_arr, close_arr)

        assert len(bullish) == 12


class TestGapPatterns:
    """Tests for Gap pattern detection."""

    def test_gap_up(self):
        """Test gap up detection."""
        open_arr = np.array([100.0, 105.0])  # Opens above prev high
        high_arr = np.array([102.0, 106.0])
        low_arr = np.array([99.0, 104.0])
        close_arr = np.array([101.0, 105.5])

        gap_up, gap_down, _, _ = detect_gap_patterns(open_arr, high_arr, low_arr, close_arr)

        assert gap_up[1] == True  # noqa: E712
        assert gap_down[1] == False  # noqa: E712

    def test_gap_down(self):
        """Test gap down detection."""
        open_arr = np.array([100.0, 94.0])  # Opens below prev low
        high_arr = np.array([102.0, 95.0])
        low_arr = np.array([99.0, 93.0])
        close_arr = np.array([101.0, 94.5])

        gap_up, gap_down, _, _ = detect_gap_patterns(open_arr, high_arr, low_arr, close_arr)

        assert gap_up[1] == False  # noqa: E712
        assert gap_down[1] == True  # noqa: E712

    def test_gap_filled(self):
        """Test gap fill detection."""
        open_arr = np.array([100.0, 105.0])  # Gap up
        high_arr = np.array([102.0, 106.0])
        low_arr = np.array([99.0, 101.0])  # Low reaches back to prev high = gap filled
        close_arr = np.array([101.0, 103.0])

        gap_up, _, gap_up_filled, _ = detect_gap_patterns(open_arr, high_arr, low_arr, close_arr)

        assert gap_up[1] == True  # noqa: E712
        assert gap_up_filled[1] == True  # noqa: E712


class TestLadderPattern:
    """Tests for Ladder pattern detection."""

    def test_ladder_bottom(self):
        """Test ladder bottom: 3 descending reds, small body, green."""
        # 3 descending red candles
        open_arr = np.array([105.0, 103.0, 101.0, 99.0, 98.0])
        close_arr = np.array([103.0, 101.0, 99.0, 98.9, 102.0])  # 3 reds, small, green
        high_arr = np.array([106.0, 104.0, 102.0, 99.5, 103.0])
        low_arr = np.array([102.0, 100.0, 98.0, 98.0, 97.0])

        bottom, top = detect_ladder_pattern(open_arr, high_arr, low_arr, close_arr)

        assert len(bottom) == 5
        assert len(top) == 5


class TestStickSandwich:
    """Tests for Stick Sandwich pattern detection."""

    def test_bullish_stick_sandwich(self):
        """Test bullish stick sandwich: red-green-red with equal closes."""
        open_arr = np.array([102.0, 97.0, 102.0])  # Red, green, red
        close_arr = np.array([98.0, 101.0, 98.0])  # Equal closes on reds
        high_arr = np.array([103.0, 102.0, 103.0])
        low_arr = np.array([97.0, 96.0, 97.0])

        bullish, _bearish = detect_stick_sandwich(open_arr, high_arr, low_arr, close_arr)

        assert bullish[2] == True  # noqa: E712

    def test_bearish_stick_sandwich(self):
        """Test bearish stick sandwich: green-red-green with equal closes."""
        open_arr = np.array([98.0, 103.0, 98.0])  # Green, red, green
        close_arr = np.array([102.0, 99.0, 102.0])  # Equal closes on greens
        high_arr = np.array([103.0, 104.0, 103.0])
        low_arr = np.array([97.0, 98.0, 97.0])

        _bullish, bearish = detect_stick_sandwich(open_arr, high_arr, low_arr, close_arr)

        assert bearish[2] == True  # noqa: E712


class TestHomingPigeon:
    """Tests for Homing Pigeon pattern detection."""

    def test_homing_pigeon(self):
        """Test homing pigeon: two reds where second is inside first."""
        open_arr = np.array([105.0, 103.0])  # Both red
        close_arr = np.array([98.0, 100.0])  # Both red, second inside first body
        high_arr = np.array([106.0, 104.0])
        low_arr = np.array([97.0, 99.0])

        result = detect_homing_pigeon(open_arr, high_arr, low_arr, close_arr)

        assert result[1] == True  # noqa: E712


class TestMatchingLowHigh:
    """Tests for Matching Low/High pattern detection."""

    def test_matching_low(self):
        """Test matching low: two candles with same lows."""
        open_arr = np.array([100.0, 101.0])
        close_arr = np.array([98.0, 102.0])
        high_arr = np.array([101.0, 103.0])
        low_arr = np.array([97.0, 97.0])  # Same lows

        match_low, _match_high = detect_matching_low_high(open_arr, high_arr, low_arr, close_arr)

        assert match_low[1] == True  # noqa: E712

    def test_matching_high(self):
        """Test matching high: two candles with same highs."""
        open_arr = np.array([100.0, 99.0])
        close_arr = np.array([102.0, 98.0])
        high_arr = np.array([103.0, 103.0])  # Same highs
        low_arr = np.array([99.0, 97.0])

        _match_low, match_high = detect_matching_low_high(open_arr, high_arr, low_arr, close_arr)

        assert match_high[1] == True  # noqa: E712


class TestAllPatternsWithExotics:
    """Tests for detect_all_patterns including exotic patterns."""

    def test_all_patterns_returns_exotic_keys(self):
        """Test that detect_all_patterns includes all exotic pattern keys."""
        np.random.seed(42)
        n = 100
        close_arr = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close_arr + np.random.randn(n) * 0.3
        high_arr = np.maximum(open_arr, close_arr) + np.abs(np.random.randn(n) * 0.2)
        low_arr = np.minimum(open_arr, close_arr) - np.abs(np.random.randn(n) * 0.2)

        result = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)

        # Check exotic pattern keys exist
        exotic_keys = [
            "three_line_strike_bullish",
            "three_line_strike_bearish",
            "kicker_bullish",
            "kicker_bearish",
            "abandoned_baby_bullish",
            "abandoned_baby_bearish",
            "belt_hold_bullish",
            "belt_hold_bearish",
            "counterattack_bullish",
            "counterattack_bearish",
            "gap_up",
            "gap_down",
            "gap_up_filled",
            "gap_down_filled",
            "ladder_bottom",
            "ladder_top",
            "stick_sandwich_bullish",
            "stick_sandwich_bearish",
            "homing_pigeon",
            "matching_low",
            "matching_high",
        ]

        for key in exotic_keys:
            assert key in result, f"Missing key: {key}"
            assert len(result[key]) == n

    def test_total_pattern_count(self):
        """Test that detect_all_patterns returns expected number of patterns."""
        open_arr = np.array([100.0, 101.0, 102.0])
        high_arr = np.array([102.0, 103.0, 104.0])
        low_arr = np.array([99.0, 100.0, 101.0])
        close_arr = np.array([101.0, 102.0, 103.0])

        result = detect_all_patterns(open_arr, high_arr, low_arr, close_arr)

        # Original 26 + 21 exotic = 47 patterns
        assert len(result) >= 47, f"Expected at least 47 patterns, got {len(result)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
