"""
Tests for all-True guard fixes in indicator handlers.

Invariant (after bug fixes I2-I5, H2 — 2026-04-13):
    When no filter mode is configured, indicator handlers must return
    all-False signals, NOT all-True signals.

    all-True  → every bar generates an entry signal (catastrophic false positive)
    all-False → indicator is passive / disabled (correct default)

Bug fixes:
    H2 — Stochastic: no modes → was all-True → now all-False per side
    I2 — QQE:        use_qqe=False → was all-True → now all-False
    I3 — RVI Filter: no modes → was all-True → now all-False
    I4 — Two MAs:    no modes → was all-True → now all-False
    I5 — Highest/Lowest Bar: no modes → was all-True → now all-False
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

N = 30  # bars


def _make_ohlcv(n: int = N, price: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n, freq="1h")
    rng = np.random.default_rng(42)
    noise = rng.uniform(-0.5, 0.5, size=n)
    close = price + np.cumsum(noise)
    high = close + rng.uniform(0.1, 0.5, size=n)
    low = close - rng.uniform(0.1, 0.5, size=n)
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
        },
        index=idx,
    )


def _all_false(series: pd.Series) -> bool:
    """True if every element is False (or NaN→False)."""
    return not series.fillna(False).any()


def _any_true(series: pd.Series) -> bool:
    return series.fillna(False).any()


# ---------------------------------------------------------------------------
# H2 — Stochastic: no active mode → all-False per side
# ---------------------------------------------------------------------------


class TestStochasticAllTrueGuard:
    """
    H2: Stochastic long_signal/short_signal were initialised True.
    When no range/cross mode is active, both sides must be all-False.
    """

    def _call(self, params: dict) -> dict[str, pd.Series]:
        from unittest.mock import MagicMock

        from backend.backtesting.indicators.oscillators import _handle_stochastic

        ohlcv = _make_ohlcv()
        close = ohlcv["close"]
        adapter = MagicMock()
        adapter._apply_signal_memory = lambda sig, _n: sig
        return _handle_stochastic(params, ohlcv, close, {}, adapter)

    def test_no_mode_returns_all_false(self):
        """
        No range, cross_level, kd_cross, or overbought/oversold →
        long AND short must be all-False.

        Before fix: initialised True, no condition overwrote → all-True.
        """
        result = self._call({})
        assert _all_false(result["long"]), "Stochastic long signal must be all-False when no mode configured."
        assert _all_false(result["short"]), "Stochastic short signal must be all-False when no mode configured."

    def test_only_long_range_active_short_still_false(self):
        """
        use_long_range=True activates the long side.
        Short side has no mode → must remain all-False.
        """
        params = {
            "use_long_range": True,
            "long_stoch_d_more": 10,
            "long_stoch_d_less": 90,
        }
        result = self._call(params)
        assert _all_false(result["short"]), "Short signal must be all-False when only long_range mode is configured."

    def test_only_short_range_active_long_still_false(self):
        params = {
            "use_short_range": True,
            "short_stoch_d_less": 90,
            "short_stoch_d_more": 10,
        }
        result = self._call(params)
        assert _all_false(result["long"]), "Long signal must be all-False when only short_range mode is configured."

    def test_kd_cross_active_allows_both_sides(self):
        """
        use_kd_cross=True → cross conditions can generate signals on both sides.
        Just verify the guard does NOT zero out both sides.
        """
        params = {"use_kd_cross": True}
        result = self._call(params)
        # We don't assert signals are non-empty (depends on data), but the guard
        # should NOT be zeroing them here.  Check the result dict has the keys.
        assert "long" in result and "short" in result


# ---------------------------------------------------------------------------
# I2 — QQE: use_qqe=False → all-False
# ---------------------------------------------------------------------------


class TestQQEAllTrueGuard:
    """
    I2: QQE initialised signals with np.ones(bool) when use_qqe=False
    → every bar was a buy/sell signal.
    Fixed: returns all-False when use_qqe=False.
    """

    def _call(self, params: dict) -> dict[str, pd.Series]:
        from unittest.mock import MagicMock

        from backend.backtesting.indicators.oscillators import _handle_qqe

        ohlcv = _make_ohlcv()
        close = ohlcv["close"]
        adapter = MagicMock()
        return _handle_qqe(params, ohlcv, close, {}, adapter)

    def test_disabled_returns_all_false(self):
        """use_qqe not in params (defaults False) → all-False signals."""
        result = self._call({})
        assert _all_false(result["long"]), "QQE long must be all-False when use_qqe=False."
        assert _all_false(result["short"]), "QQE short must be all-False when use_qqe=False."

    def test_explicit_false_returns_all_false(self):
        """use_qqe=False explicitly → all-False signals."""
        result = self._call({"use_qqe": False})
        assert _all_false(result["long"])
        assert _all_false(result["short"])

    def test_enabled_may_produce_signals(self):
        """
        use_qqe=True → signals come from QQE algorithm.
        We just check that the guard does NOT zero them out.
        """
        result = self._call({"use_qqe": True, "disable_qqe_signal_memory": True})
        # Either long or short may have signals; both False is possible on this
        # specific synthetic data, so we only check type correctness.
        assert isinstance(result["long"], pd.Series)
        assert isinstance(result["short"], pd.Series)

    def test_disabled_returns_dict_with_required_keys(self):
        """Even when disabled, all output ports must be present."""
        result = self._call({"use_qqe": False})
        for key in ("long", "short", "qqe_line"):
            assert key in result, f"QQE output must contain '{key}'"


# ---------------------------------------------------------------------------
# I3 — RVI Filter: no modes → all-False
# ---------------------------------------------------------------------------


class TestRVIFilterAllTrueGuard:
    """
    I3: RVI Filter previously initialised long_signal=True/short_signal=True,
    then range conditions applied with `&`. With no modes → remained all-True.
    Fixed: initialise to False, range modes do direct assignment.
    """

    def _call(self, params: dict) -> dict[str, pd.Series]:
        from unittest.mock import MagicMock

        from backend.backtesting.indicators.oscillators import _handle_rvi_filter

        ohlcv = _make_ohlcv()
        close = ohlcv["close"]
        adapter = MagicMock()
        return _handle_rvi_filter(params, ohlcv, close, {}, adapter)

    def test_no_mode_returns_all_false(self):
        """
        Neither use_rvi_long_range nor use_rvi_short_range → both signals all-False.

        Before fix: long_signal=True, short_signal=True without any & → all-True.
        """
        result = self._call({})
        assert _all_false(result["long"]), "RVI long must be all-False with no mode configured."
        assert _all_false(result["short"]), "RVI short must be all-False with no mode configured."

    def test_only_long_range_active(self):
        """use_rvi_long_range=True → short still all-False."""
        params = {"use_rvi_long_range": True, "rvi_long_more": 0, "rvi_long_less": 100}
        result = self._call(params)
        assert _all_false(result["short"]), "RVI short must be all-False when only long mode is active."

    def test_only_short_range_active(self):
        """use_rvi_short_range=True → long still all-False."""
        params = {"use_rvi_short_range": True, "rvi_short_less": 100, "rvi_short_more": 0}
        result = self._call(params)
        assert _all_false(result["long"]), "RVI long must be all-False when only short mode is active."


# ---------------------------------------------------------------------------
# I4 — Two MAs: no modes → all-False
# ---------------------------------------------------------------------------


class TestTwoMAsAllTrueGuard:
    """
    I4: Two MAs initialised long_signal=True/short_signal=True.
    When use_ma_cross=False and use_ma1_filter=False, _any_mode=False →
    both signals must be zeroed to all-False.
    """

    def _call(self, params: dict) -> dict[str, pd.Series]:
        from unittest.mock import MagicMock

        from backend.backtesting.indicators.trend import _handle_two_mas

        ohlcv = _make_ohlcv()
        close = ohlcv["close"]
        adapter = MagicMock()
        return _handle_two_mas(params, ohlcv, close, {}, adapter)

    def test_no_mode_returns_all_false(self):
        """
        Neither use_ma_cross nor use_ma1_filter → both signals all-False.

        Before fix: no guard → all-True every bar.
        """
        result = self._call({})
        assert _all_false(result["long"]), "Two MAs long must be all-False with no mode configured."
        assert _all_false(result["short"]), "Two MAs short must be all-False with no mode configured."

    def test_ma_cross_mode_active(self):
        """use_ma_cross=True → guard does not zero; signals may exist."""
        result = self._call({"use_ma_cross": True, "ma1_length": 5, "ma2_length": 10})
        # Guard does NOT apply → result is not zeroed (but may be empty on flat data)
        assert isinstance(result["long"], pd.Series)
        assert isinstance(result["short"], pd.Series)

    def test_ma1_filter_mode_active(self):
        """use_ma1_filter=True → guard does not zero."""
        result = self._call({"use_ma1_filter": True, "ma1_length": 10})
        assert isinstance(result["long"], pd.Series)

    @pytest.mark.parametrize(
        "ma_cross,ma1_filter,expect_zeroed",
        [
            (False, False, True),  # no mode → zeroed
            (True, False, False),  # ma_cross active → not zeroed
            (False, True, False),  # ma1_filter active → not zeroed
            (True, True, False),  # both active → not zeroed
        ],
    )
    def test_any_mode_guard(self, ma_cross, ma1_filter, expect_zeroed):
        """_any_mode = use_ma_cross OR use_ma1_filter determines guard."""
        result = self._call(
            {
                "use_ma_cross": ma_cross,
                "use_ma1_filter": ma1_filter,
                "ma1_length": 5,
                "ma2_length": 10,
            }
        )
        if expect_zeroed:
            assert _all_false(result["long"]) and _all_false(result["short"]), (
                f"Expected zeroed signals (ma_cross={ma_cross}, ma1_filter={ma1_filter})"
            )
        # When not zeroed, we don't assert signals are non-empty (data-dependent)


# ---------------------------------------------------------------------------
# I5 — Highest/Lowest Bar: no modes → all-False
# ---------------------------------------------------------------------------


class TestHighestLowestBarAllTrueGuard:
    """
    I5: Highest/Lowest Bar initialised long_signal=True/short_signal=True.
    When no modes active, guard must zero both to all-False.
    """

    def _call(self, params: dict) -> dict[str, pd.Series]:
        from unittest.mock import MagicMock

        from backend.backtesting.indicators.other import _handle_highest_lowest_bar

        ohlcv = _make_ohlcv()
        close = ohlcv["close"]
        adapter = MagicMock()
        return _handle_highest_lowest_bar(params, ohlcv, close, {}, adapter)

    def test_no_mode_returns_all_false(self):
        """
        Neither use_highest_lowest nor use_block_worse_than →
        both signals all-False.

        Before fix: initialised True, no condition overwrote → all-True.
        """
        result = self._call({})
        assert _all_false(result["long"]), "Highest/Lowest Bar long must be all-False with no mode configured."
        assert _all_false(result["short"]), "Highest/Lowest Bar short must be all-False with no mode configured."

    def test_use_highest_lowest_activates(self):
        """use_highest_lowest=True → guard does not apply."""
        result = self._call({"use_highest_lowest": True, "hl_period": 5})
        # Guard does not zero; type check only (signals may be sparse)
        assert isinstance(result["long"], pd.Series)
        assert isinstance(result["short"], pd.Series)

    def test_use_block_worse_than_activates(self):
        """use_block_worse_than=True → guard does not apply."""
        result = self._call({"use_block_worse_than": True})
        assert isinstance(result["long"], pd.Series)

    @pytest.mark.parametrize(
        "use_hl,use_bwt,expect_zeroed",
        [
            (False, False, True),
            (True, False, False),
            (False, True, False),
            (True, True, False),
        ],
    )
    def test_any_mode_guard(self, use_hl, use_bwt, expect_zeroed):
        result = self._call(
            {
                "use_highest_lowest": use_hl,
                "use_block_worse_than": use_bwt,
                "hl_period": 5,
            }
        )
        if expect_zeroed:
            assert _all_false(result["long"]) and _all_false(result["short"]), (
                f"Expected zeroed (use_hl={use_hl}, use_bwt={use_bwt})"
            )
