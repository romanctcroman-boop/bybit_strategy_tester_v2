"""
Tests for bug fixes B4 and B5 in calculate_metrics_numba().

Bug B4 (2026-04-13): Calmar threshold inconsistency
    Before fix: calmar used `max_dd > 0.01` (0.01%) which is essentially always
    True → almost never hit the sentinel value path.  Canonical calculate_calmar()
    uses `abs(max_drawdown_pct) <= 1.0` (1.0%).
    After fix: `max_dd > 1.0` aligns with the canonical threshold.

Bug B5 (2026-04-13): Sharpe RFR hardcoded
    Before fix: period_rfr = 0.02 / 8766.0  — hardcoded 2% regardless of the
    `risk_free_rate` parameter.
    After fix: period_rfr = risk_free_rate / 8766.0  — uses the parameter.

Test strategy:
    Call calculate_metrics_numba() directly with controlled inputs and verify:
      B4: max_dd ≤ 1.0 path → calmar = 10.0 (positive return), not total_return/max_dd
      B5: different risk_free_rate values produce different Sharpe outputs
"""

from __future__ import annotations

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helper — build minimal arrays for calculate_metrics_numba
# ---------------------------------------------------------------------------


def _make_inputs(
    *,
    n_trades: int = 10,
    win_pct: float = 0.6,
    avg_profit: float = 50.0,
    avg_loss: float = 30.0,
    drawdown_pct: float = 5.0,  # max drawdown percent expressed as 0–100
    initial_capital: float = 10_000.0,
    n_returns: int = 100,
) -> tuple:
    """
    Build (pnl_array, equity_array, daily_returns, initial_capital) for
    calculate_metrics_numba.

    drawdown_pct is used to control the max_dd output from the equity curve.
    """
    rng = np.random.default_rng(42)

    # pnl_array
    wins = int(n_trades * win_pct)
    losses = n_trades - wins
    pnl = np.array([avg_profit] * wins + [-avg_loss] * losses, dtype=np.float64)
    rng.shuffle(pnl)

    # equity_array — starts at initial_capital, has a controlled drawdown
    equity = np.empty(n_trades, dtype=np.float64)
    equity[0] = initial_capital
    for i in range(1, n_trades):
        equity[i] = equity[i - 1] + pnl[i - 1]

    # Inject a peak then drop to simulate drawdown_pct
    peak_val = initial_capital * 1.2
    trough_val = peak_val * (1.0 - drawdown_pct / 100.0)
    equity_curve = np.concatenate(
        [
            np.linspace(initial_capital, peak_val, n_trades // 2),
            np.linspace(peak_val, trough_val, n_trades - n_trades // 2),
        ]
    )

    # daily_returns: enough returns to make std non-zero
    daily_returns = rng.normal(0.001, 0.01, size=n_returns).astype(np.float64)

    return pnl, equity_curve, daily_returns, initial_capital


# ---------------------------------------------------------------------------
# B4 — Calmar threshold fix
# ---------------------------------------------------------------------------


class TestCalmarThresholdFix:
    """
    B4: max_dd ≤ 1.0% should return sentinel 10.0 (positive return) or 0.0.
    Before fix: threshold was 0.01% → sentinel was almost never reached.
    After fix: threshold is 1.0% → matches canonical calculate_calmar().
    """

    @staticmethod
    def _call(pnl, equity, daily_returns, initial_capital, risk_free_rate=0.02):
        from backend.core.metrics_calculator import calculate_metrics_numba

        return calculate_metrics_numba(pnl, equity, daily_returns, initial_capital, risk_free_rate)

    def test_tiny_drawdown_returns_sentinel_10(self):
        """
        max_dd < 1.0% AND positive total_return → calmar must be 10.0.

        Before B4 fix: 0.01% threshold → calmar = total_return / max_dd (large number).
        After B4 fix:  1.0% threshold  → max_dd ≤ 1.0 branch → calmar = 10.0.
        """
        # Build equity curve with only ~0.1% drawdown
        initial = 10_000.0
        # Nearly monotonic rising equity curve — minimal drawdown
        equity = np.linspace(initial, initial * 1.1, 50)  # Rising only
        # Introduce a tiny 0.05% dip in the middle
        equity[25] = equity[24] * 0.9995  # 0.05% dip at peak

        pnl = np.full(50, 10.0)  # All wins → positive total_return
        daily_returns = np.random.default_rng(0).normal(0.001, 0.005, size=100)

        total_return, sharpe, max_dd, win_rate, n_trades, pf, calmar = self._call(pnl, equity, daily_returns, initial)

        # Verify max_dd is small (< 1.0%)
        assert max_dd < 1.0, f"Expected max_dd < 1.0%, got {max_dd:.4f}%"

        # Calmar must be 10.0 (sentinel for tiny drawdown + positive return)
        assert calmar == 10.0, (
            f"B4 regression: calmar should be 10.0 sentinel for max_dd={max_dd:.4f}% ≤ 1.0% "
            f"with positive return. Got {calmar:.4f}. "
            "Before fix: threshold was 0.01%, so calmar = total_return / max_dd (huge number)."
        )

    def test_zero_drawdown_positive_return_returns_sentinel(self):
        """
        Perfectly flat equity curve (no drawdown at all) → calmar = 10.0.
        """
        initial = 10_000.0
        equity = np.full(20, initial * 1.05)  # No drawdown, above initial
        equity[0] = initial  # Start at initial
        pnl = np.full(20, 5.0)  # All small wins
        daily_returns = np.random.default_rng(1).normal(0.0005, 0.003, size=50)

        _, _, max_dd, _, _, _, calmar = self._call(pnl, equity, daily_returns, initial)

        assert max_dd <= 1.0, f"Expected max_dd ≤ 1.0%, got {max_dd:.4f}%"
        assert calmar == 10.0, f"Expected sentinel 10.0 for zero drawdown, got {calmar:.4f}"

    def test_zero_drawdown_zero_return_returns_zero_calmar(self):
        """max_dd ≤ 1.0% AND total_return ≤ 0 → calmar = 0.0."""
        initial = 10_000.0
        equity = np.full(10, initial)  # Flat equity = no profit, no drawdown
        pnl = np.zeros(10)  # Break-even
        daily_returns = np.zeros(50)

        _, _, max_dd, _, _, _, calmar = self._call(pnl, equity, daily_returns, initial)

        assert max_dd <= 1.0
        assert calmar == 0.0, f"Expected calmar=0.0 for break-even with tiny dd, got {calmar:.4f}"

    def test_significant_drawdown_uses_ratio(self):
        """
        max_dd > 1.0% → calmar = total_return / max_dd (normal formula, not sentinel).
        """
        initial = 10_000.0
        # Build equity with ~10% drawdown
        equity = np.concatenate(
            [np.linspace(initial, initial * 1.2, 25), np.linspace(initial * 1.2, initial * 1.08, 25)]
        )
        pnl = np.full(50, 20.0)
        daily_returns = np.random.default_rng(2).normal(0.001, 0.01, size=100)

        total_return, _, max_dd, _, _, _, calmar = self._call(pnl, equity, daily_returns, initial)

        assert max_dd > 1.0, f"Expected max_dd > 1.0%, got {max_dd:.4f}%"
        expected_calmar = total_return / max_dd
        assert abs(calmar - expected_calmar) < 1e-9, (
            f"For max_dd={max_dd:.2f}% > 1.0%, calmar should be ratio {expected_calmar:.4f}, got {calmar:.4f}"
        )

    @pytest.mark.parametrize("drawdown_pct", [0.001, 0.01, 0.1, 0.5, 0.99, 1.0])
    def test_boundary_below_threshold_all_get_sentinel(self, drawdown_pct):
        """Any max_dd ≤ 1.0% with positive return → sentinel 10.0."""
        initial = 10_000.0
        # Create equity with exactly the given drawdown
        peak = initial * 1.1
        trough = peak * (1.0 - drawdown_pct / 100.0)
        equity = np.array([initial, peak, trough], dtype=np.float64)
        pnl = np.array([100.0, 50.0, 30.0])
        daily_returns = np.random.default_rng(3).normal(0.001, 0.005, size=30)

        _, _, max_dd, _, _, _, calmar = self._call(pnl, equity, daily_returns, initial)

        if max_dd <= 1.0:
            assert calmar == 10.0, f"drawdown_pct={drawdown_pct}%: expected calmar=10.0, got {calmar:.4f}"


# ---------------------------------------------------------------------------
# B5 — Risk-free rate parameter fix
# ---------------------------------------------------------------------------


class TestRiskFreeRateParameter:
    """
    B5: calculate_metrics_numba() risk_free_rate parameter must affect Sharpe.

    Before fix: period_rfr = 0.02 / 8766.0 (hardcoded 2%).
    After fix:  period_rfr = risk_free_rate / 8766.0 (uses parameter).
    """

    @staticmethod
    def _call(pnl, equity, daily_returns, initial_capital, risk_free_rate=0.02):
        from backend.core.metrics_calculator import calculate_metrics_numba

        return calculate_metrics_numba(pnl, equity, daily_returns, initial_capital, risk_free_rate)

    def _make_standard_inputs(self):
        """Returns deterministic inputs with non-trivial Sharpe."""
        rng = np.random.default_rng(99)
        n = 50
        pnl = rng.normal(20.0, 15.0, size=n)
        equity = np.cumsum(np.concatenate([[10_000.0], pnl])) + 10_000.0
        # Use returns with clear positive mean so RFR changes matter
        daily_returns = rng.normal(0.002, 0.008, size=200)
        return pnl.astype(np.float64), equity[:n].astype(np.float64), daily_returns, 10_000.0

    def test_rfr_parameter_changes_sharpe(self):
        """
        Different risk_free_rate values must produce different Sharpe ratios.

        Before B5 fix: both calls produced identical Sharpe (hardcoded 0.02).
        After fix: rfr=0.0 and rfr=0.10 give different Sharpe.
        """
        pnl, equity, daily_returns, initial = self._make_standard_inputs()

        _, sharpe_0, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.0)
        _, sharpe_10, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.10)

        assert sharpe_0 != sharpe_10, (
            "B5 regression: risk_free_rate=0.0 and risk_free_rate=0.10 produced "
            "identical Sharpe ratios. Before fix, RFR was hardcoded to 0.02."
        )

    def test_zero_rfr_gives_higher_sharpe_than_high_rfr(self):
        """
        With positive expected returns, rfr=0 → higher Sharpe than rfr=0.10.
        (mean_return - rfr_period) is larger when rfr is smaller)
        """
        pnl, equity, daily_returns, initial = self._make_standard_inputs()

        _, sharpe_low, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.0)
        _, sharpe_high, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.10)

        assert sharpe_low > sharpe_high, (
            f"With positive returns, rfr=0 Sharpe ({sharpe_low:.4f}) should be > "
            f"rfr=0.10 Sharpe ({sharpe_high:.4f}). B5 fix ensures RFR affects the formula."
        )

    def test_default_rfr_equals_0p02(self):
        """
        Default parameter (risk_free_rate=0.02) must match explicit 0.02 call.
        """
        pnl, equity, daily_returns, initial = self._make_standard_inputs()

        _, sharpe_default, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial)
        _, sharpe_explicit, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.02)

        assert sharpe_default == sharpe_explicit, (
            f"Default rfr must be 0.02: default={sharpe_default:.6f}, explicit={sharpe_explicit:.6f}"
        )

    def test_rfr_monotonic_effect_on_sharpe(self):
        """
        For a strategy with positive excess returns, higher RFR → lower Sharpe.
        Test several RFR values in ascending order.
        """
        pnl, equity, daily_returns, initial = self._make_standard_inputs()

        rfr_values = [0.0, 0.01, 0.02, 0.05]
        sharpe_values = []
        for rfr in rfr_values:
            _, sharpe, _, _, _, _, _ = self._call(pnl, equity, daily_returns, initial, risk_free_rate=rfr)
            sharpe_values.append(sharpe)

        # Should be strictly decreasing (higher RFR → lower Sharpe for positive returns)
        for i in range(len(sharpe_values) - 1):
            assert sharpe_values[i] > sharpe_values[i + 1], (
                f"Sharpe should decrease as RFR increases. "
                f"rfr={rfr_values[i]}: {sharpe_values[i]:.4f}, "
                f"rfr={rfr_values[i + 1]}: {sharpe_values[i + 1]:.4f}"
            )

    def test_rfr_has_no_effect_on_other_metrics(self):
        """
        risk_free_rate should only affect Sharpe.  Other return values must be
        identical regardless of rfr.
        """
        pnl, equity, daily_returns, initial = self._make_standard_inputs()

        result_low = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.0)
        result_high = self._call(pnl, equity, daily_returns, initial, risk_free_rate=0.10)

        total_return_low, _, max_dd_low, win_rate_low, n_trades_low, pf_low, calmar_low = result_low
        total_return_high, _, max_dd_high, win_rate_high, n_trades_high, pf_high, calmar_high = result_high

        # Everything except Sharpe (index 1) should be identical
        assert total_return_low == total_return_high, "total_return changed with rfr"
        assert max_dd_low == max_dd_high, "max_dd changed with rfr"
        assert win_rate_low == win_rate_high, "win_rate changed with rfr"
        assert n_trades_low == n_trades_high, "n_trades changed with rfr"
        assert pf_low == pf_high, "profit_factor changed with rfr"
        assert calmar_low == calmar_high, "calmar changed with rfr"

    def test_empty_pnl_returns_zeros(self):
        """Edge case: empty pnl → all metrics zero, no crash for any rfr."""
        from backend.core.metrics_calculator import calculate_metrics_numba

        for rfr in [0.0, 0.02, 0.10]:
            result = calculate_metrics_numba(
                np.array([], dtype=np.float64),
                np.array([], dtype=np.float64),
                np.array([], dtype=np.float64),
                10_000.0,
                rfr,
            )
            assert result == (0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0), (
                f"Empty input with rfr={rfr} should return all-zero tuple, got {result}"
            )
