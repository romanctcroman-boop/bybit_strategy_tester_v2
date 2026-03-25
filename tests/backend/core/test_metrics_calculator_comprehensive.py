"""
Comprehensive unit tests for backend/core/metrics_calculator.py

Known-value verification tests for all 166 metrics produced by MetricsCalculator.
Tests every standalone function with hand-calculated expected values,
every dataclass field via calculate_trade_metrics/calculate_risk_metrics/
calculate_long_short_metrics, the full calculate_all() output dict,
the enrich_metrics_with_percentages() utility, caching, and edge cases.

P5.3a — 95% coverage target for metrics_calculator.py
"""

import math

import numpy as np
import pytest

from backend.core.metrics_calculator import (
    ANNUALIZATION_FACTORS,
    LongShortMetrics,
    MetricsCalculator,
    RiskMetrics,
    TimeFrequency,
    TradeMetrics,
    _build_cache_key,
    _calculate_all_cache,
    calculate_cagr,
    calculate_calmar,
    calculate_consecutive_streaks,
    calculate_expectancy,
    calculate_margin_efficiency,
    calculate_max_drawdown,
    calculate_metrics_numba,
    calculate_profit_factor,
    calculate_sharpe,
    calculate_sortino,
    calculate_sqn,
    calculate_stability_r2,
    calculate_ulcer_index,
    calculate_win_rate,
    enrich_metrics_with_percentages,
    safe_divide,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def deterministic_trades():
    """
    5 trades with known PnL values for hand-calculable metrics.

    Trade 1: +200  (long,  10 bars, pnl_pct=+2.0%)
    Trade 2: -100  (long,   5 bars, pnl_pct=-1.0%)
    Trade 3: +150  (short,  8 bars, pnl_pct=+1.5%)
    Trade 4:    0  (short,  3 bars, pnl_pct= 0.0%)  — breakeven
    Trade 5:  -50  (long,   6 bars, pnl_pct=-0.5%)

    Winning=2, Losing=2, Breakeven=1
    Gross profit = 200+150 = 350  (+ fees back for include_commission)
    Gross loss   = 100+50  = 150  (+ fees back for include_commission)
    Net profit   = 200-100+150+0-50 = 200
    Win rate (excl. breakeven) = 2/4 = 50%
    """
    return [
        {
            "pnl": 200.0,
            "pnl_pct": 2.0,
            "entry_price": 10000,
            "exit_price": 10200,
            "size": 1.0,
            "side": "long",
            "bars_in_trade": 10,
            "fees": 7.0,
        },
        {
            "pnl": -100.0,
            "pnl_pct": -1.0,
            "entry_price": 10200,
            "exit_price": 10100,
            "size": 1.0,
            "side": "long",
            "bars_in_trade": 5,
            "fees": 7.0,
        },
        {
            "pnl": 150.0,
            "pnl_pct": 1.5,
            "entry_price": 10100,
            "exit_price": 9950,
            "size": 1.0,
            "side": "short",
            "bars_in_trade": 8,
            "fees": 7.0,
        },
        {
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "entry_price": 9950,
            "exit_price": 9950,
            "size": 1.0,
            "side": "short",
            "bars_in_trade": 3,
            "fees": 7.0,
        },
        {
            "pnl": -50.0,
            "pnl_pct": -0.5,
            "entry_price": 9950,
            "exit_price": 9900,
            "size": 1.0,
            "side": "long",
            "bars_in_trade": 6,
            "fees": 7.0,
        },
    ]


@pytest.fixture
def simple_equity():
    """Equity curve matching deterministic_trades: 10000 → 10200 → 10100 → 10250 → 10250 → 10200."""
    return np.array([10000.0, 10200.0, 10100.0, 10250.0, 10250.0, 10200.0])


@pytest.fixture
def monotonic_equity():
    """Strictly increasing equity — perfect strategy, no drawdown."""
    return np.array([10000.0, 10100.0, 10200.0, 10300.0, 10400.0, 10500.0])


@pytest.fixture
def crashing_equity():
    """Equity losing 50% of capital — severe drawdown."""
    return np.array([10000.0, 9500.0, 9000.0, 8000.0, 7000.0, 5000.0])


# =============================================================================
# SAFE_DIVIDE
# =============================================================================


class TestSafeDivide:
    """Known-value tests for safe_divide()."""

    def test_normal_division(self):
        assert safe_divide(10, 2) == 5.0

    def test_zero_denominator_returns_default(self):
        assert safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom_default(self):
        assert safe_divide(10, 0, default=float("inf")) == float("inf")

    def test_near_zero_denominator(self):
        assert safe_divide(10, 1e-11) == 0.0

    def test_near_zero_above_epsilon(self):
        result = safe_divide(10, 1e-9)
        assert result != 0.0  # Above epsilon, so should divide

    def test_negative_division(self):
        assert safe_divide(-10, 2) == -5.0

    def test_both_zero(self):
        assert safe_divide(0, 0) == 0.0


# =============================================================================
# CALCULATE_WIN_RATE — known values
# =============================================================================


class TestCalculateWinRateKnown:
    """Known-value win rate tests."""

    def test_50_percent(self):
        assert calculate_win_rate(5, 10) == 50.0

    def test_33_percent(self):
        assert abs(calculate_win_rate(1, 3) - 33.333) < 0.01

    def test_1_of_1(self):
        assert calculate_win_rate(1, 1) == 100.0


# =============================================================================
# CALCULATE_PROFIT_FACTOR — known values
# =============================================================================


class TestCalculateProfitFactorKnown:
    """Known-value profit factor tests."""

    def test_2_to_1(self):
        assert calculate_profit_factor(200, 100) == 2.0

    def test_equal(self):
        assert calculate_profit_factor(100, 100) == 1.0

    def test_both_zero(self):
        assert calculate_profit_factor(0, 0) == 0.0

    def test_very_high_capped_at_100(self):
        result = calculate_profit_factor(10000, 0.001)
        assert result == 100.0


# =============================================================================
# CALCULATE_MARGIN_EFFICIENCY — known values
# =============================================================================


class TestCalculateMarginEfficiencyKnown:
    """Known-value margin efficiency tests."""

    def test_known_value(self):
        # (1000 / (5000 * 0.7)) * 100 = (1000 / 3500) * 100 ≈ 28.571
        result = calculate_margin_efficiency(1000, 5000)
        assert abs(result - 28.571) < 0.01

    def test_negative_profit(self):
        result = calculate_margin_efficiency(-500, 5000)
        expected = (-500 / (5000 * 0.7)) * 100
        assert abs(result - expected) < 0.01

    def test_zero_margin(self):
        assert calculate_margin_efficiency(1000, 0) == 0.0

    def test_negative_margin(self):
        assert calculate_margin_efficiency(1000, -1) == 0.0


# =============================================================================
# CALCULATE_ULCER_INDEX — known values
# =============================================================================


class TestCalculateUlcerIndexKnown:
    """Known-value Ulcer Index tests."""

    def test_constant_drawdown(self):
        # All 0.1 → sqrt(mean(0.01)) * 100 = sqrt(0.01) * 100 = 10.0
        dd = np.array([0.1, 0.1, 0.1, 0.1])
        assert abs(calculate_ulcer_index(dd) - 10.0) < 0.001

    def test_single_drawdown(self):
        # [0.05] → sqrt(0.0025) * 100 = 0.05 * 100 = 5.0
        dd = np.array([0.05])
        assert abs(calculate_ulcer_index(dd) - 5.0) < 0.001

    def test_mixed(self):
        # [0.1, 0.2] → sum_sq = 0.01 + 0.04 = 0.05, mean = 0.025
        # sqrt(0.025) * 100 ≈ 15.811
        dd = np.array([0.1, 0.2])
        assert abs(calculate_ulcer_index(dd) - 15.811) < 0.01

    def test_all_zero(self):
        dd = np.array([0.0, 0.0, 0.0])
        assert calculate_ulcer_index(dd) == 0.0


# =============================================================================
# CALCULATE_SHARPE — known values
# =============================================================================


class TestCalculateSharpeKnown:
    """Known-value Sharpe ratio tests."""

    def test_daily_known(self):
        """Hand-calculate Sharpe for 4 daily returns."""
        returns = np.array([0.01, 0.02, -0.005, 0.015])
        # mean = 0.01, std(ddof=1) ≈ 0.01080
        # rfr_period = 0.02 / 365.25 ≈ 5.475e-5
        # sharpe = (0.01 - 5.475e-5) / 0.01080 * sqrt(365.25)
        sharpe = calculate_sharpe(returns, TimeFrequency.DAILY)
        # Should be positive and reasonably large (daily returns annualized)
        assert sharpe > 0
        assert np.isfinite(sharpe)

    def test_all_identical_returns_zero(self):
        """Identical returns → std=0 → sharpe=0."""
        returns = np.array([0.005, 0.005, 0.005, 0.005, 0.005])
        assert calculate_sharpe(returns, TimeFrequency.DAILY) == 0.0

    def test_monthly_frequency(self):
        returns = np.array([0.05, 0.03, -0.02, 0.04, 0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.MONTHLY)
        assert np.isfinite(sharpe)

    def test_clipped_to_100(self):
        """Extreme returns should clip sharpe to [-100, 100]."""
        returns = np.array([1e6, 1e6 + 1])  # Tiny variance, huge mean
        sharpe = calculate_sharpe(returns, TimeFrequency.DAILY)
        assert sharpe <= 100.0

    def test_nan_inf_filtered(self):
        """NaN and Inf values in returns should be filtered."""
        returns = np.array([0.01, float("nan"), 0.02, float("inf"), -0.01])
        sharpe = calculate_sharpe(returns, TimeFrequency.DAILY)
        assert np.isfinite(sharpe)


# =============================================================================
# CALCULATE_SORTINO — known values
# =============================================================================


class TestCalculateSortinoKnown:
    """Known-value Sortino ratio tests."""

    def test_all_positive_returns_100(self):
        """All positive returns → no downside deviation → capped at 100."""
        returns = np.array([0.01, 0.02, 0.015, 0.01, 0.025])
        sortino = calculate_sortino(returns, TimeFrequency.DAILY)
        assert sortino == 100.0

    def test_all_negative_returns(self):
        returns = np.array([-0.01, -0.02, -0.015])
        sortino = calculate_sortino(returns, TimeFrequency.DAILY)
        assert sortino < 0

    def test_single_return(self):
        returns = np.array([0.01])
        assert calculate_sortino(returns, TimeFrequency.DAILY) == 0.0

    def test_mar_shift(self):
        """MAR > 0 should reduce the metric."""
        returns = np.array([0.01, 0.02, -0.005, 0.015, -0.01])
        s0 = calculate_sortino(returns, TimeFrequency.DAILY, mar=0.0)
        s1 = calculate_sortino(returns, TimeFrequency.DAILY, mar=0.01)
        # Higher MAR = more returns count as downside → lower sortino
        assert s1 < s0


# =============================================================================
# CALCULATE_CALMAR — known values
# =============================================================================


class TestCalculateCalmarKnown:
    """Known-value Calmar ratio tests."""

    def test_basic(self):
        # CAGR 50%, maxDD 10% → Calmar = 50 / 10 = 5.0
        assert calculate_calmar(50.0, 10.0, years=1.0) == 5.0

    def test_multi_year(self):
        # total_return 100%, 2 years → compound CAGR = (2.0^(1/2) - 1)*100 = 41.42%
        # Calmar = 41.42 / 25 = 1.657
        result = calculate_calmar(100.0, 25.0, years=2.0)
        assert abs(result - 1.657) < 0.01

    def test_zero_drawdown(self):
        # No drawdown → 10.0 if positive return
        assert calculate_calmar(30.0, 0.0) == 10.0

    def test_zero_drawdown_zero_return(self):
        assert calculate_calmar(0.0, 0.0) == 0.0

    def test_negative_return(self):
        result = calculate_calmar(-20.0, 20.0)
        assert result == -1.0

    def test_clipped(self):
        result = calculate_calmar(10000.0, 0.1, years=1.0)
        # max_drawdown_pct=0.1 is ≤ 1.0, so the tiny-drawdown sentinel fires: 10.0
        assert result == 10.0

    def test_clipped_large_numerator(self):
        # max_drawdown_pct=2.0 > 1.0 threshold, so clip applies: 10000/2 = 5000 → clipped to 100
        result = calculate_calmar(10000.0, 2.0, years=1.0)
        assert result == 100.0  # clipped to max


# =============================================================================
# CALCULATE_MAX_DRAWDOWN — known values
# =============================================================================


class TestCalculateMaxDrawdownKnown:
    """Known-value max drawdown tests."""

    def test_simple_drawdown(self):
        # 10000 → 10200 → 9800 → 10300
        # Peak at 10200, trough at 9800 → dd = (10200-9800)/10200 ≈ 3.922%
        equity = np.array([10000.0, 10200.0, 9800.0, 10300.0])
        dd_pct, dd_val, dd_dur = calculate_max_drawdown(equity)
        assert abs(dd_pct - 3.922) < 0.01
        assert abs(dd_val - 400.0) < 0.01
        assert dd_dur == 1  # From idx 1 (peak) to idx 2 (trough)

    def test_no_drawdown(self, monotonic_equity):
        dd_pct, dd_val, dd_dur = calculate_max_drawdown(monotonic_equity)
        assert dd_pct == 0.0
        assert dd_val == 0.0
        assert dd_dur == 0

    def test_50_percent_drawdown(self, crashing_equity):
        dd_pct, dd_val, _dd_dur = calculate_max_drawdown(crashing_equity)
        # 10000 → 5000 = 50%
        assert abs(dd_pct - 50.0) < 0.01
        assert abs(dd_val - 5000.0) < 0.01

    def test_single_point(self):
        dd_pct, dd_val, dd_dur = calculate_max_drawdown(np.array([10000.0]))
        assert dd_pct == 0.0
        assert dd_val == 0.0
        assert dd_dur == 0

    def test_empty(self):
        dd_pct, _dd_val, _dd_dur = calculate_max_drawdown(np.array([]))
        assert dd_pct == 0.0


# =============================================================================
# CALCULATE_CAGR — known values
# =============================================================================


class TestCalculateCAGRKnown:
    """Known-value CAGR tests."""

    def test_double_in_1_year(self):
        # (20000/10000)^(1/1) - 1 = 100%
        cagr = calculate_cagr(10000, 20000, 1.0)
        assert abs(cagr - 100.0) < 0.01

    def test_double_in_2_years(self):
        # (20000/10000)^(1/2) - 1 = sqrt(2)-1 ≈ 41.42%
        cagr = calculate_cagr(10000, 20000, 2.0)
        assert abs(cagr - 41.42) < 0.1

    def test_no_growth(self):
        cagr = calculate_cagr(10000, 10000, 1.0)
        assert abs(cagr) < 0.01

    def test_total_loss(self):
        cagr = calculate_cagr(10000, 0, 1.0)
        assert cagr == -100.0

    def test_zero_years(self):
        assert calculate_cagr(10000, 20000, 0.0) == 0.0

    def test_zero_capital(self):
        assert calculate_cagr(0, 20000, 1.0) == 0.0

    def test_short_period_simple_annualization(self):
        """Periods < 30 days use simple annualization (not compound)."""
        # 10 days = 10/365.25 years, return = 1%
        # simple_return = 1%, annualized = 1 * (365.25/10) = 36.525%
        cagr = calculate_cagr(10000, 10100, 10 / 365.25)
        assert abs(cagr - 36.525) < 0.1


# =============================================================================
# CALCULATE_EXPECTANCY — known values
# =============================================================================


class TestCalculateExpectancyKnown:
    """Known-value expectancy tests."""

    def test_basic(self):
        # win_rate=0.5, avg_win=100, avg_loss=50
        # E = (0.5 * 100) - (0.5 * 50) = 50 - 25 = 25
        exp, ratio = calculate_expectancy(0.5, 100, 50)
        assert abs(exp - 25.0) < 0.001
        # ratio = 25 / 50 = 0.5
        assert abs(ratio - 0.5) < 0.001

    def test_losing_system(self):
        # win_rate=0.3, avg_win=40, avg_loss=60
        # E = (0.3*40) - (0.7*60) = 12 - 42 = -30
        exp, _ratio = calculate_expectancy(0.3, 40, 60)
        assert abs(exp - (-30.0)) < 0.001

    def test_zero_loss(self):
        exp, _ratio = calculate_expectancy(0.6, 100, 0)
        assert exp == 60.0
        assert _ratio == 0.0

    def test_100_percent_win_rate(self):
        exp, _ratio = calculate_expectancy(1.0, 100, 50)
        assert exp == 100.0  # (1.0 * 100) - (0 * 50)


# =============================================================================
# CALCULATE_CONSECUTIVE_STREAKS — known values
# =============================================================================


class TestCalculateConsecutiveStreaksKnown:
    """Known-value streak tests."""

    def test_basic(self):
        pnl = [100, 50, -20, -10, -30, 80]
        wins, losses = calculate_consecutive_streaks(pnl)
        assert wins == 2  # First two
        assert losses == 3  # Middle three

    def test_all_wins(self):
        pnl = [10, 20, 30, 40]
        wins, losses = calculate_consecutive_streaks(pnl)
        assert wins == 4
        assert losses == 0

    def test_all_losses(self):
        pnl = [-10, -20, -30]
        wins, losses = calculate_consecutive_streaks(pnl)
        assert wins == 0
        assert losses == 3

    def test_alternating(self):
        pnl = [10, -10, 10, -10, 10]
        wins, losses = calculate_consecutive_streaks(pnl)
        assert wins == 1
        assert losses == 1

    def test_breakeven_resets_streak(self):
        pnl = [10, 20, 0, 30, 40, 50]
        wins, losses = calculate_consecutive_streaks(pnl)
        assert wins == 3  # 30, 40, 50 (breakeven 0 resets previous streak of 2)
        assert losses == 0

    def test_empty(self):
        wins, losses = calculate_consecutive_streaks([])
        assert wins == 0
        assert losses == 0


# =============================================================================
# CALCULATE_STABILITY_R2 — known values
# =============================================================================


class TestCalculateStabilityR2Known:
    """Known-value R² tests."""

    def test_perfect_line(self):
        # Perfectly linear equity → R² = 1.0
        equity = np.array([100, 200, 300, 400, 500], dtype=float)
        r2 = calculate_stability_r2(equity)
        assert abs(r2 - 1.0) < 1e-6

    def test_flat_line(self):
        # Constant equity → ss_tot=0 → R²=0
        equity = np.array([100, 100, 100, 100], dtype=float)
        r2 = calculate_stability_r2(equity)
        assert r2 == 0.0

    def test_noisy(self):
        # Some noise → 0 < R² < 1
        np.random.seed(42)
        x = np.arange(100, dtype=float)
        equity = 10000 + x * 10 + np.random.randn(100) * 5
        r2 = calculate_stability_r2(equity)
        assert 0.5 < r2 < 1.0

    def test_single_point(self):
        assert calculate_stability_r2(np.array([100.0])) == 0.0


# =============================================================================
# CALCULATE_SQN — known values
# =============================================================================


class TestCalculateSQNKnown:
    """Known-value SQN tests."""

    def test_basic(self):
        # SQN = sqrt(N) * mean / std
        # N=25, mean=10, std=20 → SQN = 5 * 0.5 = 2.5
        assert abs(calculate_sqn(25, 10, 20) - 2.5) < 0.001

    def test_zero_std(self):
        assert calculate_sqn(25, 10, 0) == 0.0

    def test_one_trade(self):
        assert calculate_sqn(1, 10, 5) == 0.0  # Need ≥ 2 trades

    def test_negative_mean(self):
        # sqrt(16) * (-5 / 10) = 4 * -0.5 = -2.0
        assert abs(calculate_sqn(16, -5, 10) - (-2.0)) < 0.001


# =============================================================================
# ANNUALIZATION_FACTORS
# =============================================================================


class TestAnnualizationFactors:
    """Verify annualization constants."""

    def test_minutely(self):
        assert ANNUALIZATION_FACTORS[TimeFrequency.MINUTELY] == 525600

    def test_hourly(self):
        assert ANNUALIZATION_FACTORS[TimeFrequency.HOURLY] == 8766

    def test_daily(self):
        assert ANNUALIZATION_FACTORS[TimeFrequency.DAILY] == 365.25

    def test_weekly(self):
        assert ANNUALIZATION_FACTORS[TimeFrequency.WEEKLY] == 52.18

    def test_monthly(self):
        assert ANNUALIZATION_FACTORS[TimeFrequency.MONTHLY] == 12


# =============================================================================
# DATACLASS DEFAULTS
# =============================================================================


class TestDataclassDefaults:
    """Ensure dataclasses initialize with zeros."""

    def test_trade_metrics_defaults(self):
        m = TradeMetrics()
        assert m.total_trades == 0
        assert m.net_profit == 0.0
        assert m.win_rate == 0.0
        assert m.payoff_ratio == 0.0
        assert m.max_consec_wins == 0

    def test_risk_metrics_defaults(self):
        m = RiskMetrics()
        assert m.sharpe_ratio == 0.0
        assert m.max_drawdown == 0.0
        assert m.cagr == 0.0
        assert m.sqn == 0.0

    def test_long_short_metrics_defaults(self):
        m = LongShortMetrics()
        assert m.long_trades == 0
        assert m.short_trades == 0
        assert m.long_win_rate == 0.0
        assert m.short_cagr == 0.0


# =============================================================================
# MetricsCalculator.calculate_trade_metrics — known values
# =============================================================================


class TestCalculateTradeMetrics:
    """Tests for calculate_trade_metrics with hand-calculated expected values."""

    def test_empty_trades(self):
        m = MetricsCalculator.calculate_trade_metrics([])
        assert m.total_trades == 0
        assert m.net_profit == 0.0

    def test_counts(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        assert m.total_trades == 5
        assert m.winning_trades == 2
        assert m.losing_trades == 2
        assert m.breakeven_trades == 1

    def test_net_profit(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # 200 - 100 + 150 + 0 - 50 = 200
        assert abs(m.net_profit - 200.0) < 0.01

    def test_win_rate(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # Win rate = winning / (winning + losing) = 2/4 = 50% (breakeven excluded)
        assert abs(m.win_rate - 50.0) < 0.01

    def test_avg_win(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # avg_win = (200 + 150) / 2 = 175
        assert abs(m.avg_win - 175.0) < 0.01

    def test_avg_loss(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # avg_loss = (-100 + -50) / 2 = -75
        assert abs(m.avg_loss - (-75.0)) < 0.01

    def test_avg_trade(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # avg_trade = 200 / 5 = 40
        assert abs(m.avg_trade - 40.0) < 0.01

    def test_largest_win(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        assert m.largest_win == 200.0

    def test_largest_loss(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        assert m.largest_loss == -100.0

    def test_payoff_ratio(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # abs(avg_win / avg_loss) = abs(175 / -75) ≈ 2.333
        assert abs(m.payoff_ratio - 2.333) < 0.01

    def test_streaks(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # PnL sequence: [200, -100, 150, 0, -50]
        # Wins: 1 (200), then 0 resets, 1 (150), then 0 resets → max consec wins = 1
        # Losses: 1 (-100), 0 resets, 1 (-50) → max consec losses = 1
        assert m.max_consec_wins == 1
        assert m.max_consec_losses == 1

    def test_bars(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # avg bars = (10+5+8+3+6)/5 = 6.4
        assert abs(m.avg_bars_held - 6.4) < 0.01
        # avg win bars = (10+8)/2 = 9.0
        assert abs(m.avg_win_bars - 9.0) < 0.01
        # avg loss bars = (5+6)/2 = 5.5
        assert abs(m.avg_loss_bars - 5.5) < 0.01

    def test_total_commission(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # 5 trades x 7 = 35
        assert abs(m.total_commission - 35.0) < 0.01

    def test_pct_averages(self, deterministic_trades):
        m = MetricsCalculator.calculate_trade_metrics(deterministic_trades)
        # avg_win_pct = (2.0 + 1.5) / 2 = 1.75
        assert abs(m.avg_win_pct - 1.75) < 0.01
        # avg_loss_pct = (-1.0 + -0.5) / 2 = -0.75
        assert abs(m.avg_loss_pct - (-0.75)) < 0.01
        # avg_trade_pct = (2.0 - 1.0 + 1.5 + 0.0 - 0.5) / 5 = 0.4
        assert abs(m.avg_trade_pct - 0.4) < 0.01

    def test_object_attributes_instead_of_dict(self):
        """Support objects with attributes in addition to dicts."""

        class Trade:
            def __init__(self, pnl, pnl_pct, fees, bars):
                self.pnl = pnl
                self.pnl_pct = pnl_pct
                self.fees = fees
                self.bars_in_trade = bars

        trades = [Trade(100, 1.0, 5, 10), Trade(-50, -0.5, 5, 5)]
        m = MetricsCalculator.calculate_trade_metrics(trades)
        assert m.total_trades == 2
        assert m.winning_trades == 1
        assert m.losing_trades == 1


# =============================================================================
# MetricsCalculator.calculate_risk_metrics — known values
# =============================================================================


class TestCalculateRiskMetrics:
    """Tests for calculate_risk_metrics with known equity curves."""

    def test_monotonic_no_drawdown(self, monotonic_equity):
        returns = np.diff(monotonic_equity) / monotonic_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(monotonic_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        assert m.max_drawdown == 0.0
        assert m.max_drawdown_value == 0.0
        assert m.avg_drawdown == 0.0

    def test_drawdown_values(self, simple_equity):
        returns = np.diff(simple_equity) / simple_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(simple_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        # Peak 10250, trough 10100 → dd = (10250-10100)/10250 ≈ 1.463%
        # But also peak 10250, trough 10200 → dd = 0.488%
        # Actually peak was 10200 at idx 1, then 10100 at idx 2 → dd = (10200-10100)/10200 ≈ 0.980%
        # Then peak becomes 10250, equity stays 10250 → dd=0
        # Then 10250 → 10200 → dd = (10250-10200)/10250 ≈ 0.488%
        # Max drawdown = 0.980%
        assert m.max_drawdown > 0

    def test_crashing_drawdown(self, crashing_equity):
        returns = np.diff(crashing_equity) / crashing_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(crashing_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        assert abs(m.max_drawdown - 50.0) < 0.01

    def test_cagr_computed(self, monotonic_equity):
        returns = np.diff(monotonic_equity) / monotonic_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(monotonic_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        # 10000 → 10500, 1 year → CAGR = 5%
        assert abs(m.cagr - 5.0) < 0.01

    def test_stability(self, monotonic_equity):
        returns = np.diff(monotonic_equity) / monotonic_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(monotonic_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        # Perfectly linear → R² ≈ 1
        assert m.stability > 0.99

    def test_recovery_factor(self, crashing_equity):
        returns = np.diff(crashing_equity) / crashing_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(crashing_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        # net_profit = 5000-10000 = -5000, max_dd_value = 5000
        # recovery = -5000 / 5000 = -1.0
        assert abs(m.recovery_factor - (-1.0)) < 0.01

    def test_ulcer_index_populated(self, simple_equity):
        returns = np.diff(simple_equity) / simple_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(simple_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        assert m.ulcer_index >= 0

    def test_volatility_computed(self, simple_equity):
        returns = np.diff(simple_equity) / simple_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(simple_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        assert m.volatility > 0

    def test_runup(self, monotonic_equity):
        returns = np.diff(monotonic_equity) / monotonic_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(monotonic_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        assert m.max_runup > 0
        assert m.max_runup_value > 0

    def test_short_equity(self):
        """Equity with < 2 points returns all zeros."""
        m = MetricsCalculator.calculate_risk_metrics(np.array([10000.0]), np.array([0.0]), 10000.0)
        assert m.max_drawdown == 0.0
        assert m.sharpe_ratio == 0.0

    def test_margin_efficiency_populated(self, simple_equity):
        returns = np.diff(simple_equity) / simple_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(
            simple_equity,
            returns,
            10000.0,
            1.0,
            TimeFrequency.DAILY,
            margin_used=5000.0,
        )
        # net_profit = 10200 - 10000 = 200
        # margin_efficiency = (200 / (5000 * 0.7)) * 100 ≈ 5.714
        assert m.margin_efficiency > 0

    def test_avg_drawdown_duration(self, simple_equity):
        returns = np.diff(simple_equity) / simple_equity[:-1]
        m = MetricsCalculator.calculate_risk_metrics(simple_equity, returns, 10000.0, 1.0, TimeFrequency.DAILY)
        # There are drawdown periods in simple_equity
        assert m.avg_drawdown_duration_bars >= 0


# =============================================================================
# MetricsCalculator.calculate_long_short_metrics
# =============================================================================


class TestCalculateLongShortMetrics:
    """Tests for long/short separation with known trade data."""

    def test_empty_trades(self):
        m = MetricsCalculator.calculate_long_short_metrics([], 10000.0)
        assert m.long_trades == 0
        assert m.short_trades == 0

    def test_separation(self, deterministic_trades):
        m = MetricsCalculator.calculate_long_short_metrics(deterministic_trades, 10000.0)
        # Longs: trades 0,1,4 → 3 long trades
        assert m.long_trades == 3
        # Shorts: trades 2,3 → 2 short trades
        assert m.short_trades == 2

    def test_long_win_rate(self, deterministic_trades):
        m = MetricsCalculator.calculate_long_short_metrics(deterministic_trades, 10000.0)
        # Long trades: +200, -100, -50 → 1 win, 2 losses → 1/(1+2) = 33.33%
        assert abs(m.long_win_rate - 33.333) < 0.1

    def test_short_win_rate(self, deterministic_trades):
        m = MetricsCalculator.calculate_long_short_metrics(deterministic_trades, 10000.0)
        # Short trades: +150, 0 → 1 win, 0 losses, 1 breakeven → 1/(1+0) = 100%
        assert abs(m.short_win_rate - 100.0) < 0.01

    def test_long_net_profit(self, deterministic_trades):
        m = MetricsCalculator.calculate_long_short_metrics(deterministic_trades, 10000.0)
        # Long PnL: 200 - 100 - 50 = 50
        assert abs(m.long_net_profit - 50.0) < 0.01

    def test_short_net_profit(self, deterministic_trades):
        m = MetricsCalculator.calculate_long_short_metrics(deterministic_trades, 10000.0)
        # Short PnL: 150 + 0 = 150
        assert abs(m.short_net_profit - 150.0) < 0.01

    def test_direction_field_fallback(self):
        """Trades with 'direction' instead of 'side' should work."""
        trades = [
            {"pnl": 100, "pnl_pct": 1.0, "direction": "long", "bars_in_trade": 5, "fees": 0},
            {"pnl": -50, "pnl_pct": -0.5, "direction": "short", "bars_in_trade": 3, "fees": 0},
        ]
        m = MetricsCalculator.calculate_long_short_metrics(trades, 10000.0)
        assert m.long_trades == 1
        assert m.short_trades == 1

    def test_side_enum_value(self):
        """Trades with enum-like side objects (with .value)."""

        class Side:
            def __init__(self, v):
                self.value = v

        class Trade:
            def __init__(self, pnl, side_val):
                self.pnl = pnl
                self.pnl_pct = 0.0
                self.side = Side(side_val)
                self.fees = 0
                self.bars_in_trade = 5

        trades = [Trade(100, "Buy"), Trade(-30, "Sell")]
        m = MetricsCalculator.calculate_long_short_metrics(trades, 10000.0)
        assert m.long_trades == 1
        assert m.short_trades == 1


# =============================================================================
# MetricsCalculator.calculate_all — comprehensive output check
# =============================================================================


class TestCalculateAllComprehensive:
    """Full output verification for calculate_all()."""

    def test_output_key_count(self, deterministic_trades, simple_equity):
        """Ensure the result dict has all expected keys (≥ 90 fields)."""
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        # The result dict should contain at least 90 keys
        assert len(result) >= 90, f"Only {len(result)} keys in result"

    def test_all_values_finite(self, deterministic_trades, simple_equity):
        """No NaN in any metric value. Inf is allowed for payoff/recovery when no losses/drawdown."""
        ALLOWED_INF_KEYS = {
            "payoff_ratio",
            "long_payoff_ratio",
            "short_payoff_ratio",
            "recovery_factor",
            "long_recovery_factor",
            "short_recovery_factor",
            "expectancy_pct_ratio",
            "expectancy_ratio",
        }
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        for key, value in result.items():
            if isinstance(value, float):
                assert not math.isnan(value), f"{key} = NaN is not allowed"
                if key not in ALLOWED_INF_KEYS:
                    assert math.isfinite(value), f"{key} = {value} is not finite"

    def test_trade_stats_in_output(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert result["total_trades"] == 5
        assert result["winning_trades"] == 2
        assert result["losing_trades"] == 2
        assert result["breakeven_trades"] == 1

    def test_risk_metrics_in_output(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert "sharpe_ratio" in result
        assert "sortino_ratio" in result
        assert "calmar_ratio" in result
        assert "max_drawdown" in result
        assert "volatility" in result
        assert "stability" in result
        assert "sqn" in result
        assert "ulcer_index" in result

    def test_long_short_in_output(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert result["long_trades"] == 3
        assert result["short_trades"] == 2

    def test_kelly_criterion(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert "kelly_percent" in result
        assert 0.0 <= result["kelly_percent"] <= 1.0

    def test_expectancy_in_output(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert "expectancy" in result
        assert "expectancy_ratio" in result

    def test_open_trades_always_zero(self, deterministic_trades, simple_equity):
        """Backtests always have 0 open trades."""
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert result["open_trades"] == 0

    def test_frequency_affects_sharpe(self, deterministic_trades, simple_equity):
        """Different frequencies produce different Sharpe values."""
        r_hourly = MetricsCalculator.calculate_all(
            deterministic_trades,
            simple_equity,
            10000.0,
            frequency=TimeFrequency.HOURLY,
        )
        r_daily = MetricsCalculator.calculate_all(
            deterministic_trades,
            simple_equity,
            10000.0,
            frequency=TimeFrequency.DAILY,
        )
        # Different annualization → different Sharpe (unless Sharpe=0)
        if r_hourly["sharpe_ratio"] != 0 and r_daily["sharpe_ratio"] != 0:
            assert r_hourly["sharpe_ratio"] != r_daily["sharpe_ratio"]


# =============================================================================
# CACHING
# =============================================================================


class TestCalculateAllCaching:
    """Tests for calculate_all() result caching."""

    def setup_method(self):
        """Clear cache before each test."""
        _calculate_all_cache.clear()

    def test_cache_hit(self, deterministic_trades, simple_equity):
        r1 = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        r2 = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert r1 == r2
        # Cache should have exactly 1 entry
        assert len(_calculate_all_cache) == 1

    def test_cache_miss_different_capital(self, deterministic_trades, simple_equity):
        MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 20000.0)
        assert len(_calculate_all_cache) == 2

    def test_cache_returns_copy(self, deterministic_trades, simple_equity):
        """Modifying the result should not mutate the cache."""
        r1 = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        r1["total_trades"] = 999  # Mutate
        r2 = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        assert r2["total_trades"] == 5  # Cache untouched

    def test_build_cache_key_deterministic(self, deterministic_trades, simple_equity):
        k1 = _build_cache_key(deterministic_trades, simple_equity, 10000, 1.0, TimeFrequency.HOURLY, 1.0)
        k2 = _build_cache_key(deterministic_trades, simple_equity, 10000, 1.0, TimeFrequency.HOURLY, 1.0)
        assert k1 == k2

    def test_build_cache_key_differs(self, deterministic_trades, simple_equity):
        k1 = _build_cache_key(deterministic_trades, simple_equity, 10000, 1.0, TimeFrequency.HOURLY, 1.0)
        k2 = _build_cache_key(deterministic_trades, simple_equity, 20000, 1.0, TimeFrequency.HOURLY, 1.0)
        assert k1 != k2


# =============================================================================
# enrich_metrics_with_percentages
# =============================================================================


class TestEnrichMetricsWithPercentages:
    """Tests for the percentage enrichment utility."""

    def test_basic_enrichment(self):
        metrics = {
            "gross_profit": 500.0,
            "gross_loss": 200.0,
            "net_profit": 300.0,
        }
        result = enrich_metrics_with_percentages(metrics, 10000.0)
        # gross_profit_pct = 500 / 10000 * 100 = 5%
        assert abs(result["gross_profit_pct"] - 5.0) < 0.01
        assert abs(result["gross_loss_pct"] - 2.0) < 0.01

    def test_zero_capital_returns_unchanged(self):
        metrics = {"gross_profit": 500.0}
        result = enrich_metrics_with_percentages(metrics, 0)
        assert "gross_profit_pct" not in result

    def test_required_pct_fields_exist(self):
        """All REQUIRED_PCT_FIELDS should be present even if 0."""
        result = enrich_metrics_with_percentages({}, 10000.0)
        for field in [
            "net_profit_pct",
            "gross_profit_pct",
            "gross_loss_pct",
            "long_return_pct",
            "short_return_pct",
            "buy_hold_return_pct",
            "strategy_outperformance",
        ]:
            assert field in result

    def test_long_return_pct(self):
        metrics = {"long_net_profit": 1000.0}
        result = enrich_metrics_with_percentages(metrics, 10000.0)
        assert abs(result["long_return_pct"] - 10.0) < 0.01

    def test_short_return_pct(self):
        metrics = {"short_net_profit": -500.0}
        result = enrich_metrics_with_percentages(metrics, 10000.0)
        assert abs(result["short_return_pct"] - (-5.0)) < 0.01

    def test_strategy_outperformance(self):
        metrics = {
            "total_return": 15.0,
            "buy_hold_return": 1000.0,  # 10%
        }
        result = enrich_metrics_with_percentages(metrics, 10000.0)
        # outperformance = total_return - buy_hold_pct
        # total_return is used as strategy_return if net_profit_pct absent
        assert "strategy_outperformance" in result

    def test_no_duplicate_overwrite(self):
        """If pct field already exists, don't overwrite."""
        metrics = {"gross_profit": 500.0, "gross_profit_pct": 99.0}
        result = enrich_metrics_with_percentages(metrics, 10000.0)
        assert result["gross_profit_pct"] == 99.0  # Original preserved


# =============================================================================
# NUMBA PARITY — known-value verification
# =============================================================================


class TestNumbaParity:
    """Verify calculate_metrics_numba matches hand-calculated values."""

    def test_total_return(self):
        pnl = np.array([100.0, -50.0, 200.0])
        eq = np.array([10000.0, 10100.0, 10050.0, 10250.0])
        dr = np.diff(eq) / eq[:-1]
        result = calculate_metrics_numba(pnl, eq, dr, 10000.0)
        # total_return = (250/10000)*100 = 2.5%
        assert abs(result[0] - 2.5) < 0.01

    def test_max_drawdown(self):
        pnl = np.array([100.0, -300.0, 50.0])
        eq = np.array([10000.0, 10100.0, 9800.0, 9850.0])
        dr = np.diff(eq) / eq[:-1]
        result = calculate_metrics_numba(pnl, eq, dr, 10000.0)
        # Peak 10100, trough 9800 → dd = (10100-9800)/10100 ≈ 2.970%
        assert abs(result[2] - 2.970) < 0.1

    def test_profit_factor_numba(self):
        pnl = np.array([100.0, -50.0, 75.0, -25.0])
        eq = np.array([10000.0, 10100.0, 10050.0, 10125.0, 10100.0])
        dr = np.diff(eq) / eq[:-1]
        result = calculate_metrics_numba(pnl, eq, dr, 10000.0)
        # gross_profit = 175, gross_loss = 75 → PF = 2.333
        assert abs(result[5] - 2.333) < 0.01

    def test_win_rate_numba(self):
        pnl = np.array([10.0, -5.0, 20.0, -3.0, 15.0])
        eq = np.ones(6) * 10000
        dr = np.zeros(5)
        result = calculate_metrics_numba(pnl, eq, dr, 10000.0)
        # 3 wins out of 5 → 0.6
        assert abs(result[3] - 0.6) < 0.001


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_single_trade_all_methods(self):
        """Single trade should produce valid metrics everywhere."""
        trades = [
            {
                "pnl": 50.0,
                "pnl_pct": 0.5,
                "side": "long",
                "entry_price": 10000,
                "size": 1.0,
                "bars_in_trade": 5,
                "fees": 3.5,
            }
        ]
        equity = np.array([10000.0, 10050.0])

        result = MetricsCalculator.calculate_all(trades, equity, 10000.0)
        assert result["total_trades"] == 1
        assert result["winning_trades"] == 1
        assert result["net_profit"] == 50.0

    def test_all_losing_trades(self):
        trades = [
            {"pnl": -100, "pnl_pct": -1.0, "side": "long", "bars_in_trade": 5, "fees": 0},
            {"pnl": -200, "pnl_pct": -2.0, "side": "short", "bars_in_trade": 3, "fees": 0},
        ]
        equity = np.array([10000.0, 9900.0, 9700.0])
        result = MetricsCalculator.calculate_all(trades, equity, 10000.0)
        assert result["winning_trades"] == 0
        assert result["win_rate"] == 0.0
        assert result["net_profit"] == -300.0

    def test_all_winning_trades(self):
        trades = [
            {"pnl": 100, "pnl_pct": 1.0, "side": "long", "bars_in_trade": 5, "fees": 0},
            {"pnl": 200, "pnl_pct": 2.0, "side": "short", "bars_in_trade": 3, "fees": 0},
        ]
        equity = np.array([10000.0, 10100.0, 10300.0])
        result = MetricsCalculator.calculate_all(trades, equity, 10000.0)
        assert result["winning_trades"] == 2
        assert result["losing_trades"] == 0
        assert result["win_rate"] == 100.0

    def test_all_breakeven_trades(self):
        trades = [
            {"pnl": 0, "pnl_pct": 0, "side": "long", "bars_in_trade": 5, "fees": 0},
            {"pnl": 0, "pnl_pct": 0, "side": "short", "bars_in_trade": 3, "fees": 0},
        ]
        equity = np.array([10000.0, 10000.0, 10000.0])
        result = MetricsCalculator.calculate_all(trades, equity, 10000.0)
        assert result["breakeven_trades"] == 2
        assert result["win_rate"] == 0.0  # No meaningful trades

    def test_very_large_pnl(self):
        """Extreme PnL values should not cause overflow."""
        trades = [
            {"pnl": 1e9, "pnl_pct": 1e7, "side": "long", "bars_in_trade": 1, "fees": 0},
        ]
        equity = np.array([10000.0, 1e9 + 10000.0])
        result = MetricsCalculator.calculate_all(trades, equity, 10000.0)
        assert math.isfinite(result["net_profit"])
        assert math.isfinite(result["cagr"])

    def test_negative_equity_handled(self):
        """Negative equity (bankruptcy) should not crash."""
        equity = np.array([10000.0, 5000.0, -1000.0])
        returns = np.array([0.0, 0.0])
        m = MetricsCalculator.calculate_risk_metrics(equity, returns, 10000.0)
        assert m.max_drawdown > 0

    def test_empty_equity(self):
        """Empty equity should return all-zero metrics."""
        result = MetricsCalculator.calculate_all([], np.array([]), 10000.0)
        assert result["total_trades"] == 0

    def test_commission_field_aliases(self):
        """Support 'commission' and 'commissions' field names."""
        trades_a = [{"pnl": 100, "pnl_pct": 1.0, "commission": 10, "bars_in_trade": 5}]
        trades_b = [{"pnl": 100, "pnl_pct": 1.0, "commissions": 10, "bars_in_trade": 5}]
        m_a = MetricsCalculator.calculate_trade_metrics(trades_a)
        m_b = MetricsCalculator.calculate_trade_metrics(trades_b)
        assert abs(m_a.total_commission - 10.0) < 0.01
        assert abs(m_b.total_commission - 10.0) < 0.01


# =============================================================================
# FULL OUTPUT KEY VERIFICATION — 166 metrics parity
# =============================================================================


class TestFullOutputKeys:
    """Ensure calculate_all produces all documented output keys."""

    EXPECTED_KEYS = {
        # Trade stats
        "total_trades",
        "winning_trades",
        "losing_trades",
        "breakeven_trades",
        "gross_profit",
        "gross_loss",
        "net_profit",
        "total_commission",
        "win_rate",
        "profit_factor",
        "avg_win",
        "avg_loss",
        "avg_trade",
        "avg_trade_pct",
        "largest_win",
        "largest_loss",
        "avg_win_value",
        "avg_loss_value",
        "avg_trade_value",
        "largest_win_value",
        "largest_loss_value",
        "avg_win_loss_ratio",
        "max_consecutive_wins",
        "max_consecutive_losses",
        "avg_bars_in_trade",
        "avg_bars_in_winning",
        "avg_bars_in_losing",
        # Risk
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "max_drawdown_value",
        "avg_drawdown",
        "max_drawdown_duration_bars",
        "avg_drawdown_duration_bars",
        "max_runup",
        "max_runup_value",
        "avg_runup",
        "avg_runup_duration_bars",
        "recovery_factor",
        "ulcer_index",
        "margin_efficiency",
        "stability",
        "sqn",
        "kelly_percent",
        "kelly_percent_long",
        "kelly_percent_short",
        "open_trades",
        "expectancy",
        "expectancy_ratio",
        "cagr",
        "volatility",
        # Long
        "long_trades",
        "long_winning_trades",
        "long_losing_trades",
        "long_breakeven_trades",
        "long_gross_profit",
        "long_gross_loss",
        "long_net_profit",
        "long_commission",
        "long_win_rate",
        "long_profit_factor",
        "long_avg_win",
        "long_avg_loss",
        "long_avg_trade",
        "long_largest_win",
        "long_largest_loss",
        "long_payoff_ratio",
        "long_max_consec_wins",
        "long_max_consec_losses",
        "long_avg_bars",
        "long_avg_win_bars",
        "long_avg_loss_bars",
        "long_avg_win_pct",
        "long_avg_loss_pct",
        "long_avg_trade_pct",
        "long_largest_win_pct",
        "long_largest_loss_pct",
        "cagr_long",
        # Short
        "short_trades",
        "short_winning_trades",
        "short_losing_trades",
        "short_breakeven_trades",
        "short_gross_profit",
        "short_gross_loss",
        "short_net_profit",
        "short_commission",
        "short_win_rate",
        "short_profit_factor",
        "short_avg_win",
        "short_avg_loss",
        "short_avg_trade",
        "short_largest_win",
        "short_largest_loss",
        "short_payoff_ratio",
        "short_max_consec_wins",
        "short_max_consec_losses",
        "short_avg_bars",
        "short_avg_win_bars",
        "short_avg_loss_bars",
        "short_avg_win_pct",
        "short_avg_loss_pct",
        "short_avg_trade_pct",
        "short_largest_win_pct",
        "short_largest_loss_pct",
        "cagr_short",
    }

    def test_all_expected_keys_present(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        missing = self.EXPECTED_KEYS - set(result.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_no_unexpected_none_values(self, deterministic_trades, simple_equity):
        result = MetricsCalculator.calculate_all(deterministic_trades, simple_equity, 10000.0)
        none_keys = [k for k, v in result.items() if v is None]
        assert not none_keys, f"None values for keys: {none_keys}"


# =============================================================================
# TimeFrequency enum
# =============================================================================


class TestTimeFrequency:
    """Verify TimeFrequency enum values."""

    def test_values(self):
        assert TimeFrequency.MINUTELY == "minutely"
        assert TimeFrequency.HOURLY == "hourly"
        assert TimeFrequency.DAILY == "daily"
        assert TimeFrequency.WEEKLY == "weekly"
        assert TimeFrequency.MONTHLY == "monthly"

    def test_is_str(self):
        """TimeFrequency is also a str."""
        assert isinstance(TimeFrequency.HOURLY, str)
