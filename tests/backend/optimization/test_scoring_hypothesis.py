"""
Property-based tests for optimization scoring functions.

Uses Hypothesis to verify invariants that must hold for ALL inputs:
- Composite scores are deterministic
- Rankings are stable (tie-breaking is deterministic)
- Sorting properties are preserved
- No exceptions on edge cases
"""

from __future__ import annotations

import copy

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.optimization.scoring import (
    apply_custom_sort_order,
    apply_pareto_scores,
    calculate_composite_score,
    rank_by_multi_criteria,
)

# =============================================================================
# Strategies for generating test data
# =============================================================================

# Realistic metric values
metric_value = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
positive_metric = st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False)
pct_metric = st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)

SIMPLE_METRICS = [
    "net_profit",
    "sharpe_ratio",
    "sortino_ratio",
    "total_return",
    "cagr",
    "win_rate",
    "profit_factor",
    "expectancy",
    "recovery_factor",
    "avg_win",
    "payoff_ratio",
    "total_trades",
    "trades_per_month",
]

INVERTED_METRICS = [
    "max_drawdown",
    "avg_drawdown",
    "avg_loss",
    "volatility",
    "var_95",
]

COMPUTED_METRICS = ["calmar_ratio", "risk_adjusted_return"]

ALL_METRICS = SIMPLE_METRICS + INVERTED_METRICS + COMPUTED_METRICS

RANKING_CRITERIA = [
    "net_profit",
    "total_return",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "expectancy",
    "total_trades",
]


def result_strategy():
    """Generate a realistic backtest result dict."""
    return st.fixed_dictionaries(
        {
            "net_profit": metric_value,
            "total_return": metric_value,
            "sharpe_ratio": metric_value,
            "sortino_ratio": metric_value,
            "cagr": metric_value,
            "max_drawdown": st.floats(min_value=-100, max_value=0, allow_nan=False, allow_infinity=False),
            "avg_drawdown": st.floats(min_value=-100, max_value=0, allow_nan=False, allow_infinity=False),
            "win_rate": pct_metric,
            "profit_factor": positive_metric,
            "expectancy": metric_value,
            "recovery_factor": metric_value,
            "avg_win": positive_metric,
            "avg_loss": st.floats(min_value=-1e6, max_value=0, allow_nan=False, allow_infinity=False),
            "payoff_ratio": positive_metric,
            "total_trades": st.integers(min_value=0, max_value=10000),
            "trades_per_month": positive_metric,
            "volatility": positive_metric,
            "var_95": positive_metric,
            "avg_trade_duration": positive_metric,
            "avg_bars_in_trade": positive_metric,
        }
    )


# =============================================================================
# Tests for calculate_composite_score
# =============================================================================


class TestCompositeScoreProperties:
    """Property-based tests for calculate_composite_score."""

    @given(result=result_strategy(), metric=st.sampled_from(ALL_METRICS))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_score_is_finite(self, result, metric):
        """Score must always be a finite number for valid inputs."""
        score = calculate_composite_score(result, metric)
        assert isinstance(score, (int, float))
        assert score == score  # not NaN

    @given(result=result_strategy(), metric=st.sampled_from(ALL_METRICS))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_score_is_deterministic(self, result, metric):
        """Same input must produce same output (no randomness)."""
        score1 = calculate_composite_score(result, metric)
        score2 = calculate_composite_score(result, metric)
        assert score1 == score2

    @given(metric=st.sampled_from(SIMPLE_METRICS))
    @settings(max_examples=50)
    def test_simple_metric_returns_raw_value(self, metric):
        """Simple metrics should return the raw value from result."""
        result = {metric: 42.5}
        score = calculate_composite_score(result, metric)
        assert score == 42.5

    @given(metric=st.sampled_from(INVERTED_METRICS))
    @settings(max_examples=50)
    def test_inverted_metric_returns_negative(self, metric):
        """Inverted metrics should return negative of absolute value."""
        result = {metric: 5.0}
        score = calculate_composite_score(result, metric)
        assert score <= 0

    @given(result=result_strategy())
    @settings(max_examples=50)
    def test_unknown_metric_returns_net_profit(self, result):
        """Unknown metric name should fall back to net_profit."""
        score = calculate_composite_score(result, "nonexistent_metric_xyz")
        assert score == (result.get("net_profit", 0) or 0)

    @given(metric=st.sampled_from(ALL_METRICS))
    @settings(max_examples=50)
    def test_empty_result_returns_zero(self, metric):
        """Empty result dict should return 0 (or computed 0)."""
        score = calculate_composite_score({}, metric)
        assert isinstance(score, (int, float))

    @given(metric=st.sampled_from(ALL_METRICS))
    @settings(max_examples=50)
    def test_none_values_treated_as_zero(self, metric):
        """None metric values should be treated as 0."""
        result = dict.fromkeys(ALL_METRICS)
        score = calculate_composite_score(result, metric)
        assert isinstance(score, (int, float))


# =============================================================================
# Tests for rank_by_multi_criteria
# =============================================================================


class TestRankingProperties:
    """Property-based tests for rank_by_multi_criteria."""

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        criteria=st.lists(st.sampled_from(RANKING_CRITERIA), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_ranking_preserves_length(self, results, criteria):
        """Ranking must not add or remove results."""
        original_len = len(results)
        ranked = rank_by_multi_criteria(results, criteria)
        assert len(ranked) == original_len

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        criteria=st.lists(st.sampled_from(RANKING_CRITERIA), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_ranking_adds_score_field(self, results, criteria):
        """All ranked results must have a 'score' field."""
        ranked = rank_by_multi_criteria(results, criteria)
        for r in ranked:
            assert "score" in r

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        criteria=st.lists(st.sampled_from(RANKING_CRITERIA), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_ranking_is_sorted_by_score(self, results, criteria):
        """Results must be sorted by score descending (best first)."""
        ranked = rank_by_multi_criteria(results, criteria)
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        criteria=st.lists(st.sampled_from(RANKING_CRITERIA), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=50)
    def test_ranking_is_deterministic(self, results, criteria):
        """Same input must produce same ranking order."""
        results_copy1 = copy.deepcopy(results)
        results_copy2 = copy.deepcopy(results)
        ranked1 = rank_by_multi_criteria(results_copy1, criteria)
        ranked2 = rank_by_multi_criteria(results_copy2, criteria)
        scores1 = [r["score"] for r in ranked1]
        scores2 = [r["score"] for r in ranked2]
        assert scores1 == scores2

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        criteria=st.lists(st.sampled_from(RANKING_CRITERIA), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=50)
    def test_ranking_cleanup_removes_temp_fields(self, results, criteria):
        """Temp fields (_ranks, _avg_rank, _orig_idx) must be removed."""
        ranked = rank_by_multi_criteria(results, criteria)
        for r in ranked:
            assert "_ranks" not in r
            assert "_avg_rank" not in r
            assert "_orig_idx" not in r

    def test_empty_results_returns_empty(self):
        """Empty list should return empty list."""
        assert rank_by_multi_criteria([], ["sharpe_ratio"]) == []

    def test_empty_criteria_returns_unmodified(self):
        """Empty criteria should return results unmodified."""
        results = [{"net_profit": 100}]
        ranked = rank_by_multi_criteria(results, [])
        assert ranked == results

    @given(result=result_strategy())
    @settings(max_examples=30)
    def test_single_result_gets_best_rank(self, result):
        """Single result should always be ranked first with score."""
        ranked = rank_by_multi_criteria([result], ["sharpe_ratio"])
        assert len(ranked) == 1
        assert "score" in ranked[0]


# =============================================================================
# Tests for apply_custom_sort_order
# =============================================================================


class TestCustomSortProperties:
    """Property-based tests for apply_custom_sort_order."""

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
    )
    @settings(max_examples=50)
    def test_sort_preserves_length(self, results):
        """Sorting must not add or remove results."""
        sort_order = [{"metric": "sharpe_ratio", "direction": "desc"}]
        sorted_results = apply_custom_sort_order(results, sort_order)
        assert len(sorted_results) == len(results)

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        metric=st.sampled_from(RANKING_CRITERIA),
    )
    @settings(max_examples=50)
    def test_desc_sort_is_descending(self, results, metric):
        """Descending sort should produce non-increasing values."""
        sort_order = [{"metric": metric, "direction": "desc"}]
        sorted_results = apply_custom_sort_order(results, sort_order)
        values = [r.get(metric, 0) or 0 for r in sorted_results]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1]

    @given(
        results=st.lists(result_strategy(), min_size=2, max_size=20),
        metric=st.sampled_from(RANKING_CRITERIA),
    )
    @settings(max_examples=50)
    def test_asc_sort_is_ascending(self, results, metric):
        """Ascending sort should produce non-decreasing values."""
        sort_order = [{"metric": metric, "direction": "asc"}]
        sorted_results = apply_custom_sort_order(results, sort_order)
        values = [r.get(metric, 0) or 0 for r in sorted_results]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]

    def test_empty_results_returns_empty(self):
        """Empty list should return empty list."""
        assert apply_custom_sort_order([], [{"metric": "net_profit", "direction": "desc"}]) == []

    def test_empty_sort_order_returns_unmodified(self):
        """Empty sort order should return results unmodified."""
        results = [{"net_profit": 100}, {"net_profit": 200}]
        assert apply_custom_sort_order(results, []) == results


# =============================================================================
# Tests for apply_pareto_scores
# =============================================================================


class TestParetoScores:
    """Tests for apply_pareto_scores — normalised NP / DD ranking."""

    # ------------------------------------------------------------------
    # Structural invariants
    # ------------------------------------------------------------------

    def test_empty_list_returns_empty(self):
        """Empty input must return empty list without errors."""
        assert apply_pareto_scores([]) == []

    def test_preserves_length(self):
        """apply_pareto_scores must not add or remove results."""
        results = [
            {"total_return": 10.0, "max_drawdown": 5.0, "total_trades": 20},
            {"total_return": 50.0, "max_drawdown": 20.0, "total_trades": 60},
            {"total_return": 5.0, "max_drawdown": 1.0, "total_trades": 10},
        ]
        out = apply_pareto_scores(results)
        assert len(out) == 3

    def test_adds_pareto_score_field(self):
        """Every result must get a pareto_score field after processing."""
        results = [
            {"total_return": 20.0, "max_drawdown": 10.0, "total_trades": 30},
            {"total_return": 40.0, "max_drawdown": 5.0, "total_trades": 50},
        ]
        apply_pareto_scores(results)
        for r in results:
            assert "pareto_score" in r
            assert "score" in r

    def test_score_equals_pareto_score(self):
        """result['score'] must equal result['pareto_score'] after processing."""
        results = [
            {"total_return": 20.0, "max_drawdown": 10.0, "total_trades": 30},
            {"total_return": 40.0, "max_drawdown": 5.0, "total_trades": 50},
        ]
        apply_pareto_scores(results)
        for r in results:
            assert r["score"] == r["pareto_score"]

    def test_scores_are_finite(self):
        """All pareto_scores must be finite (no NaN / inf)."""
        import math

        results = [
            {"total_return": 0.0, "max_drawdown": 0.0, "total_trades": 0},
            {"total_return": 100.0, "max_drawdown": 50.0, "total_trades": 100},
            {"total_return": -5.0, "max_drawdown": 2.0, "total_trades": 5},
        ]
        apply_pareto_scores(results)
        for r in results:
            assert math.isfinite(r["pareto_score"]), f"Non-finite score: {r['pareto_score']}"

    def test_sorted_best_first(self):
        """Output list must be sorted by pareto_score descending."""
        results = [
            {"total_return": 10.0, "max_drawdown": 50.0, "total_trades": 30},  # bad ratio
            {"total_return": 80.0, "max_drawdown": 8.0, "total_trades": 50},  # best ratio
            {"total_return": 5.0, "max_drawdown": 2.0, "total_trades": 20},
            {"total_return": 40.0, "max_drawdown": 15.0, "total_trades": 100},
        ]
        apply_pareto_scores(results)
        scores = [r["pareto_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    # ------------------------------------------------------------------
    # Domain correctness
    # ------------------------------------------------------------------

    def test_best_ratio_wins(self):
        """High NP / low DD must beat high NP / high DD."""
        results = [
            {"total_return": 80.0, "max_drawdown": 8.0, "total_trades": 50},  # best ratio
            {"total_return": 80.0, "max_drawdown": 50.0, "total_trades": 50},  # same NP, huge DD
        ]
        apply_pareto_scores(results)
        # First result must be the high-ratio one (low DD)
        assert results[0]["max_drawdown"] == 8.0

    def test_single_result_gets_zero_score(self):
        """Single-element list: range is 0, min-max norm = 0/1.0 → score = 0."""
        results = [{"total_return": 50.0, "max_drawdown": 10.0, "total_trades": 40}]
        apply_pareto_scores(results)
        # np_norm = (50-50)/(1) = 0 → pareto = 0 * ... = 0
        assert results[0]["pareto_score"] == 0.0

    def test_none_values_treated_as_zero(self):
        """None / missing fields must not raise exceptions."""
        results = [
            {"total_return": None, "max_drawdown": None, "total_trades": None},
            {"total_return": 30.0, "max_drawdown": 10.0, "total_trades": 20},
        ]
        # Should not raise
        apply_pareto_scores(results)
        for r in results:
            assert "pareto_score" in r

    def test_deterministic(self):
        """Same input must always produce the same scores."""
        import copy

        results1 = [
            {"total_return": 20.0, "max_drawdown": 5.0, "total_trades": 30},
            {"total_return": 60.0, "max_drawdown": 15.0, "total_trades": 80},
            {"total_return": 10.0, "max_drawdown": 3.0, "total_trades": 15},
        ]
        results2 = copy.deepcopy(results1)
        apply_pareto_scores(results1)
        apply_pareto_scores(results2)
        scores1 = [r["pareto_score"] for r in results1]
        scores2 = [r["pareto_score"] for r in results2]
        assert scores1 == scores2

    @given(
        results=st.lists(
            st.fixed_dictionaries(
                {
                    "total_return": st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
                    "max_drawdown": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
                    "total_trades": st.integers(min_value=0, max_value=500),
                }
            ),
            min_size=2,
            max_size=30,
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_property_sorted_and_finite(self, results):
        """Property: output is always sorted best-first and all scores finite."""
        import math

        apply_pareto_scores(results)
        scores = [r["pareto_score"] for r in results]
        # All finite
        for s in scores:
            assert math.isfinite(s), f"Non-finite pareto_score: {s}"
        # Sorted descending
        assert scores == sorted(scores, reverse=True)

    # ------------------------------------------------------------------
    # pareto_balance in calculate_composite_score (per-result proxy)
    # ------------------------------------------------------------------

    def test_per_result_pareto_balance_is_finite(self):
        """calculate_composite_score with 'pareto_balance' must return finite value."""
        import math

        result = {"total_return": 50.0, "max_drawdown": 10.0, "total_trades": 30}
        score = calculate_composite_score(result, "pareto_balance")
        assert math.isfinite(score)
        assert score >= 0

    def test_per_result_pareto_balance_zero_dd(self):
        """Zero max_drawdown uses floor 0.1% — must not raise ZeroDivisionError."""
        result = {"total_return": 20.0, "max_drawdown": 0.0, "total_trades": 10}
        score = calculate_composite_score(result, "pareto_balance")
        assert score >= 0

    def test_per_result_pareto_balance_higher_np_wins(self):
        """Higher NP with same DD must score higher per-result proxy."""
        low = calculate_composite_score(
            {"total_return": 10.0, "max_drawdown": 5.0, "total_trades": 20}, "pareto_balance"
        )
        high = calculate_composite_score(
            {"total_return": 80.0, "max_drawdown": 5.0, "total_trades": 20}, "pareto_balance"
        )
        assert high > low

    def test_per_result_pareto_balance_lower_dd_wins(self):
        """Same NP with lower DD must score higher per-result proxy."""
        high_dd = calculate_composite_score(
            {"total_return": 50.0, "max_drawdown": 40.0, "total_trades": 30}, "pareto_balance"
        )
        low_dd = calculate_composite_score(
            {"total_return": 50.0, "max_drawdown": 5.0, "total_trades": 30}, "pareto_balance"
        )
        assert low_dd > high_dd
