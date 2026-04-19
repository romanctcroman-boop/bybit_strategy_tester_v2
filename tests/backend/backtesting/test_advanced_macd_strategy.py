"""
Tests for AdvancedMACDStrategy (Strategy_MACD_01)

Verifies that the Python implementation matches the TradingView Pine Script v6
"Advanced MACD Strategy with TP/SL" reference strategy.

TV Reference Test Configuration (from aa5.csv):
    Symbol: BYBIT:ETHUSDT.P   Timeframe: 30m
    Period: 2025-01-04 15:30 → 2026-03-01 13:30
    fast=14, slow=15, signal=9, source=close
    use_cross_zero=True, opposite_cross_zero=True
    use_cross_signal=True, opposite_cross_signal=True
    zero_filter=False

TV Reference Results (from aa1.csv, aa2.csv):
    Total trades: 42  |  Win rate: 88.10%
    Net profit:   +1723.14 USDT (+17.23%)
    Profit factor: 3.584
    Sharpe: 0.934  |  Sortino: 4.19
    Max drawdown (intrabar): 2.60%
"""

from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from backend.backtesting.strategies import AdvancedMACDStrategy, get_strategy

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate synthetic OHLCV data (500 bars, 30-min resolution)."""
    np.random.seed(2025)
    n = 500
    dates = pd.date_range("2025-01-01", periods=n, freq="30min", tz=UTC)
    returns = np.random.normal(0.0001, 0.008, n)
    close = 3500 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.004, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.004, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = np.random.uniform(500, 5000, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def default_strategy() -> AdvancedMACDStrategy:
    """Strategy with TV reference defaults (fast=14, slow=15, signal=9)."""
    return AdvancedMACDStrategy()


# ============================================================
# Instantiation & parameter tests
# ============================================================


class TestAdvancedMACDInit:
    def test_default_params(self):
        s = AdvancedMACDStrategy()
        assert s.fast_period == 14
        assert s.slow_period == 15
        assert s.signal_period == 9
        assert s.use_cross_zero is True
        assert s.opposite_cross_zero is True
        assert s.use_cross_signal is True
        assert s.opposite_cross_signal is True
        assert s.zero_filter is False

    def test_custom_params(self):
        s = AdvancedMACDStrategy(
            {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_cross_zero": False,
                "opposite_cross_zero": False,
                "use_cross_signal": True,
                "opposite_cross_signal": False,
                "zero_filter": True,
            }
        )
        assert s.fast_period == 12
        assert s.slow_period == 26
        assert s.use_cross_zero is False
        assert s.zero_filter is True

    def test_invalid_fast_period(self):
        with pytest.raises(ValueError, match="fast_period"):
            AdvancedMACDStrategy({"fast_period": 0})

    def test_invalid_slow_period(self):
        with pytest.raises(ValueError, match="slow_period"):
            AdvancedMACDStrategy({"slow_period": 0})

    def test_invalid_signal_period(self):
        with pytest.raises(ValueError, match="signal_period"):
            AdvancedMACDStrategy({"signal_period": 0})

    def test_registry_lookup(self):
        """Strategy is accessible via both 'advanced_macd' and 'macd_01' aliases."""
        s1 = get_strategy("advanced_macd")
        s2 = get_strategy("macd_01")
        assert isinstance(s1, AdvancedMACDStrategy)
        assert isinstance(s2, AdvancedMACDStrategy)

    def test_name_and_description(self):
        s = AdvancedMACDStrategy()
        assert s.name == "advanced_macd"
        assert "MACD" in s.description

    def test_get_default_params(self):
        params = AdvancedMACDStrategy.get_default_params()
        assert params["fast_period"] == 14
        assert params["slow_period"] == 15
        assert params["signal_period"] == 9


# ============================================================
# Signal generation tests
# ============================================================


class TestAdvancedMACDSignals:
    def test_returns_signal_result(self, default_strategy, sample_ohlcv):
        from backend.backtesting.strategies import SignalResult

        result = default_strategy.generate_signals(sample_ohlcv)
        assert isinstance(result, SignalResult)

    def test_signal_arrays_match_input_length(self, default_strategy, sample_ohlcv):
        result = default_strategy.generate_signals(sample_ohlcv)
        n = len(sample_ohlcv)
        assert len(result.entries) == n
        assert len(result.exits) == n
        assert len(result.short_entries) == n
        assert len(result.short_exits) == n

    def test_signals_are_bool(self, default_strategy, sample_ohlcv):
        result = default_strategy.generate_signals(sample_ohlcv)
        assert result.entries.dtype == bool
        assert result.short_entries.dtype == bool

    def test_exits_are_empty(self, default_strategy, sample_ohlcv):
        """TV strategy uses TP/SL for all exits — no signal-based exits."""
        result = default_strategy.generate_signals(sample_ohlcv)
        assert result.exits.sum() == 0, "Long exits should be empty (TP/SL only)"
        assert result.short_exits.sum() == 0, "Short exits should be empty (TP/SL only)"

    def test_first_bar_has_no_signal(self, default_strategy, sample_ohlcv):
        result = default_strategy.generate_signals(sample_ohlcv)
        assert result.entries.iloc[0] is False or not result.entries.iloc[0]
        assert result.short_entries.iloc[0] is False or not result.short_entries.iloc[0]

    def test_no_simultaneous_long_and_short(self, default_strategy, sample_ohlcv):
        """Conflict guard: long and short cannot fire on the same bar."""
        result = default_strategy.generate_signals(sample_ohlcv)
        conflict = result.entries & result.short_entries
        assert conflict.sum() == 0, f"Found {conflict.sum()} conflicting signals"

    def test_signals_generated_with_sufficient_data(self, default_strategy, sample_ohlcv):
        """Strategy should produce at least some signals on 500 bars."""
        result = default_strategy.generate_signals(sample_ohlcv)
        total_signals = result.entries.sum() + result.short_entries.sum()
        assert total_signals > 0, "No signals generated on 500-bar dataset"

    def test_no_signal_when_both_sources_disabled(self, sample_ohlcv):
        """When both cross_zero and cross_signal are disabled, no entries should fire."""
        s = AdvancedMACDStrategy({"use_cross_zero": False, "use_cross_signal": False})
        result = s.generate_signals(sample_ohlcv)
        assert result.entries.sum() == 0
        assert result.short_entries.sum() == 0


# ============================================================
# Logic correctness tests (deterministic synthetic data)
# ============================================================


class TestAdvancedMACDLogic:
    def _make_zero_cross_data(self) -> pd.DataFrame:
        """
        Build synthetic close prices where MACD (fast=14, slow=15, sig=9)
        clearly crosses zero at a known bar.

        Strategy: force a sustained trend reversal.
        200 bars down-trend then 200 bars up-trend.
        With fast=14, slow=15 the MACD zero-cross happens roughly around bar 200.
        """
        n = 400
        prices = []
        for i in range(200):
            prices.append(3500 - i * 2)  # Downtrend: MACD goes negative
        for i in range(200):
            prices.append(3100 + i * 2)  # Uptrend: MACD goes positive
        idx = pd.date_range("2025-01-01", periods=n, freq="30min", tz=UTC)
        # IMPORTANT: assign idx before building the DataFrame so pandas
        # doesn't try to align an integer-indexed Series against a
        # DatetimeIndex (which would produce all-NaN columns).
        close = pd.Series(prices, dtype=float, index=idx)
        return pd.DataFrame(
            {
                "open": close.shift(1).fillna(close.iloc[0]),
                "high": close * 1.001,
                "low": close * 0.999,
                "close": close,
                "volume": 1000.0,
            },
            index=idx,
        )

    def test_opposite_cross_zero_logic(self):
        """
        With opposite_cross_zero=True:
            longSignal fires when MACD crosses UNDER zero
            shortSignal fires when MACD crosses OVER zero

        Downtrend → Uptrend data:
        - MACD should cross OVER zero somewhere after bar 200
        - That means shortSignal fires (MACD crosses above zero with opposite=True)
        """
        data = self._make_zero_cross_data()
        s = AdvancedMACDStrategy(
            {
                "fast_period": 14,
                "slow_period": 15,
                "signal_period": 9,
                "use_cross_zero": True,
                "opposite_cross_zero": True,
                "use_cross_signal": False,
                "zero_filter": False,
            }
        )
        result = s.generate_signals(data)
        # In uptrend half MACD crosses ABOVE zero → short (opposite=True)
        assert result.short_entries.sum() > 0, "Expected short signals when MACD crosses above zero (opposite=True)"

    def test_normal_cross_zero_logic(self):
        """
        With opposite_cross_zero=False:
            longSignal fires when MACD crosses OVER zero (standard)
        """
        data = self._make_zero_cross_data()
        s = AdvancedMACDStrategy(
            {
                "fast_period": 14,
                "slow_period": 15,
                "signal_period": 9,
                "use_cross_zero": True,
                "opposite_cross_zero": False,
                "use_cross_signal": False,
                "zero_filter": False,
            }
        )
        result = s.generate_signals(data)
        assert result.entries.sum() > 0, "Expected long signals when MACD crosses above zero (normal direction)"

    def test_zero_filter_suppresses_wrong_direction(self, sample_ohlcv):
        """
        Zero filter: LONG only when MACD > 0, SHORT only when MACD < 0.
        With zero_filter=True, the total signals should be <= without filter.
        """
        s_no_filter = AdvancedMACDStrategy({"zero_filter": False})
        s_filter = AdvancedMACDStrategy({"zero_filter": True})

        r_no = s_no_filter.generate_signals(sample_ohlcv)
        r_yes = s_filter.generate_signals(sample_ohlcv)

        total_no = r_no.entries.sum() + r_no.short_entries.sum()
        total_yes = r_yes.entries.sum() + r_yes.short_entries.sum()

        assert total_yes <= total_no, "Zero filter should reduce or keep equal number of signals"

    def test_only_signal_source(self, sample_ohlcv):
        """use_cross_zero=False, use_cross_signal=True: only signal-line crossovers."""
        s = AdvancedMACDStrategy(
            {
                "use_cross_zero": False,
                "use_cross_signal": True,
                "opposite_cross_signal": False,  # Standard: long on MACD > signal
                "zero_filter": False,
            }
        )
        result = s.generate_signals(sample_ohlcv)
        assert result.entries.sum() > 0 or result.short_entries.sum() > 0

    def test_only_zero_source(self, sample_ohlcv):
        """use_cross_zero=True, use_cross_signal=False: only zero-line crossovers."""
        s = AdvancedMACDStrategy(
            {
                "use_cross_zero": True,
                "opposite_cross_zero": False,
                "use_cross_signal": False,
                "zero_filter": False,
            }
        )
        result = s.generate_signals(sample_ohlcv)
        assert result.entries.sum() > 0 or result.short_entries.sum() > 0

    def test_both_sources_and_logic(self, sample_ohlcv):
        """
        Both sources active = AND logic → fewer or equal signals than single source.
        """
        s_both = AdvancedMACDStrategy(
            {
                "use_cross_zero": True,
                "opposite_cross_zero": True,
                "use_cross_signal": True,
                "opposite_cross_signal": True,
                "zero_filter": False,
            }
        )
        s_zero_only = AdvancedMACDStrategy(
            {
                "use_cross_zero": True,
                "opposite_cross_zero": True,
                "use_cross_signal": False,
                "zero_filter": False,
            }
        )
        r_both = s_both.generate_signals(sample_ohlcv)
        r_zero = s_zero_only.generate_signals(sample_ohlcv)

        total_both = r_both.entries.sum() + r_both.short_entries.sum()
        total_zero = r_zero.entries.sum() + r_zero.short_entries.sum()

        # AND of two conditions ≤ single condition
        assert total_both <= total_zero, "Both-sources (AND) should produce fewer or equal signals than single source"


# ============================================================
# MACD calculation parity test
# ============================================================


class TestAdvancedMACDCalculation:
    def test_macd_calculation_matches_ewm(self, sample_ohlcv):
        """
        Verify that internal MACD calculation matches manual EWM computation.
        Pine: ta.ema(src, period) = ewm(span=period, adjust=False).mean()
        """
        s = AdvancedMACDStrategy({"fast_period": 14, "slow_period": 15, "signal_period": 9})
        close = sample_ohlcv["close"]

        macd_line, signal_line, histogram = s._calculate_macd(close)

        expected_fast = close.ewm(span=14, adjust=False).mean()
        expected_slow = close.ewm(span=15, adjust=False).mean()
        expected_macd = expected_fast - expected_slow
        expected_signal = expected_macd.ewm(span=9, adjust=False).mean()
        expected_hist = expected_macd - expected_signal

        pd.testing.assert_series_equal(macd_line, expected_macd, check_names=False)
        pd.testing.assert_series_equal(signal_line, expected_signal, check_names=False)
        pd.testing.assert_series_equal(histogram, expected_hist, check_names=False)


# ============================================================
# TV reference data comparison (structural parity)
# ============================================================


class TestTVReferenceParity:
    """
    Structural parity checks based on the TV reference CSV data.

    These tests verify the SIGNAL PATTERN properties that correspond
    to the known TV results.  Full numerical parity requires running
    the engine with the actual ETHUSDT 30m market data.
    """

    TV_TRADE_ENTRIES = [
        # (signal_type, approx_date)  — from aa4.csv
        ("short", "2025-01-04"),
        ("short", "2025-01-15"),
        ("short", "2025-02-06"),
        ("long", "2025-02-12"),
        ("short", "2025-02-18"),
        ("short", "2025-03-02"),
        ("short", "2025-03-05"),
        ("long", "2025-03-12"),
        ("long", "2025-03-21"),
        ("short", "2025-03-26"),
    ]

    def test_strategy_generates_both_directions(self, default_strategy, sample_ohlcv):
        """TV reference has both LONG and SHORT trades."""
        result = default_strategy.generate_signals(sample_ohlcv)
        assert result.entries.sum() > 0, "Should produce LONG entries"
        assert result.short_entries.sum() > 0, "Should produce SHORT entries"

    def test_tv_reference_params_match_defaults(self):
        """Validate that default params match the TV reference test configuration."""
        defaults = AdvancedMACDStrategy.get_default_params()
        # From aa5.csv
        assert defaults["fast_period"] == 14, "TV fast length = 14"
        assert defaults["slow_period"] == 15, "TV slow length = 15"
        assert defaults["signal_period"] == 9, "TV signal smoothing = 9"
        assert defaults["use_cross_zero"] is True, "TV: use_cross_zero = Вкл"
        assert defaults["opposite_cross_zero"] is True, "TV: opposite_cross_zero = Вкл"
        assert defaults["use_cross_signal"] is True, "TV: use_cross_signal = Вкл"
        assert defaults["opposite_cross_signal"] is True, "TV: opposite_cross_signal = Вкл"
        assert defaults["zero_filter"] is False, "TV: zero_filter = Выкл"

    def test_signal_count_reasonable(self, default_strategy, sample_ohlcv):
        """
        TV result: 42 trades over ~14 months on 30m ETHUSDT.
        On synthetic 500-bar data we expect a similar density ~1-5 trades/month.
        """
        result = default_strategy.generate_signals(sample_ohlcv)
        total = result.entries.sum() + result.short_entries.sum()
        # 500 bars × 30min ≈ 10 days → expect at least 1 signal, not more than 50
        assert 1 <= total <= 50, f"Signal count {total} out of expected range [1, 50] for 500-bar 30m data"
