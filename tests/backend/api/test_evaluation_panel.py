"""
Tests for Evaluation Criteria Panel — field propagation and constraint filtering.

Tests cover:
1. _calculate_composite_score() — all 20 frontend metrics
2. _passes_dynamic_constraints() — all 6 operators
3. _rank_by_multi_criteria() — multi-criteria ranking
4. _compute_weighted_composite() — weighted normalization
5. _apply_custom_sort_order() — multi-level sorting
6. _passes_filters() — combined filters + dynamic constraints
7. SyncOptimizationRequest model — field acceptance
"""

import pytest

# ============================================================================
# Helper: import backend functions
# ============================================================================
from backend.api.routers.optimizations import (
    SyncOptimizationRequest,
    _apply_custom_sort_order,
    _calculate_composite_score,
    _compute_weighted_composite,
    _passes_dynamic_constraints,
    _passes_filters,
    _rank_by_multi_criteria,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_result() -> dict:
    """Sample optimization result dict with all metrics."""
    return {
        "total_return": 25.5,
        "cagr": 12.3,
        "sharpe_ratio": 1.8,
        "sortino_ratio": 2.5,
        "calmar_ratio": 3.0,
        "max_drawdown": -8.5,
        "avg_drawdown": -3.2,
        "volatility": 15.0,
        "var_95": -2.5,
        "risk_adjusted_return": 20.0,
        "win_rate": 65.0,
        "profit_factor": 2.1,
        "avg_win": 3.5,
        "avg_loss": -1.8,
        "expectancy": 150.0,
        "payoff_ratio": 1.94,
        "recovery_factor": 3.0,
        "total_trades": 120,
        "trades_per_month": 20.0,
        "avg_trade_duration": 12.0,
        "avg_bars_in_trade": 12.0,
        "net_profit": 2550.0,
        "params": {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "stop_loss_pct": 10.0,
            "take_profit_pct": 1.5,
        },
    }


@pytest.fixture
def multiple_results() -> list[dict]:
    """Multiple optimization results for ranking tests."""
    return [
        {
            "total_return": 30.0,
            "sharpe_ratio": 1.5,
            "max_drawdown": -20.0,
            "win_rate": 55.0,
            "profit_factor": 1.8,
            "total_trades": 100,
            "net_profit": 3000.0,
            "sortino_ratio": 2.0,
            "expectancy": 100.0,
            "score": 0,
            "params": {"rsi_period": 14},
        },
        {
            "total_return": 15.0,
            "sharpe_ratio": 2.5,
            "max_drawdown": -5.0,
            "win_rate": 70.0,
            "profit_factor": 3.0,
            "total_trades": 50,
            "net_profit": 1500.0,
            "sortino_ratio": 3.5,
            "expectancy": 200.0,
            "score": 0,
            "params": {"rsi_period": 21},
        },
        {
            "total_return": 50.0,
            "sharpe_ratio": 0.8,
            "max_drawdown": -35.0,
            "win_rate": 45.0,
            "profit_factor": 1.2,
            "total_trades": 200,
            "net_profit": 5000.0,
            "sortino_ratio": 1.0,
            "expectancy": 50.0,
            "score": 0,
            "params": {"rsi_period": 7},
        },
    ]


# ============================================================================
# Test: _calculate_composite_score — all 20 metrics
# ============================================================================


class TestCalculateCompositeScore:
    """Tests for _calculate_composite_score with all frontend metrics."""

    # --- Performance metrics (higher = better) ---

    def test_net_profit_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "net_profit")
        assert score == 2550.0

    def test_sharpe_ratio_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "sharpe_ratio")
        assert score == 1.8

    def test_sortino_ratio_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "sortino_ratio")
        assert score == 2.5

    def test_total_return_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "total_return")
        assert score == 25.5

    def test_cagr_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "cagr")
        assert score == 12.3

    def test_win_rate_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "win_rate")
        assert score == 65.0

    def test_profit_factor_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "profit_factor")
        assert score == 2.1

    def test_expectancy_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "expectancy")
        assert score == 150.0

    def test_recovery_factor_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "recovery_factor")
        assert score == 3.0

    def test_avg_win_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "avg_win")
        assert score == 3.5

    def test_payoff_ratio_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "payoff_ratio")
        assert score == 1.94

    def test_total_trades_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "total_trades")
        assert score == 120

    def test_trades_per_month_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "trades_per_month")
        assert score == 20.0

    # --- Inverted metrics (lower = better, returns negative) ---

    def test_max_drawdown_metric_returns_negative(self, sample_result):
        score = _calculate_composite_score(sample_result, "max_drawdown")
        assert score == -8.5  # negative of abs(max_drawdown)

    def test_avg_drawdown_metric_returns_negative(self, sample_result):
        score = _calculate_composite_score(sample_result, "avg_drawdown")
        assert score == -3.2

    def test_avg_loss_metric_returns_negative(self, sample_result):
        score = _calculate_composite_score(sample_result, "avg_loss")
        assert score == -1.8

    def test_volatility_metric_returns_negative(self, sample_result):
        score = _calculate_composite_score(sample_result, "volatility")
        assert score == -15.0

    def test_var_95_metric_returns_negative(self, sample_result):
        score = _calculate_composite_score(sample_result, "var_95")
        assert score == -2.5

    # --- Composite metrics ---

    def test_calmar_ratio_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "calmar_ratio")
        assert score == pytest.approx(25.5 / 8.5)

    def test_risk_adjusted_return_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "risk_adjusted_return")
        drawdown_factor = 1 + 8.5 / 100.0
        expected = 25.5 / drawdown_factor
        assert score == pytest.approx(expected)

    # --- Activity metrics ---

    def test_avg_trade_duration_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "avg_trade_duration")
        assert score == 12.0

    def test_avg_bars_in_trade_metric(self, sample_result):
        score = _calculate_composite_score(sample_result, "avg_bars_in_trade")
        assert score == 12.0

    # --- Edge cases ---

    def test_unknown_metric_defaults_to_net_profit(self, sample_result):
        score = _calculate_composite_score(sample_result, "unknown_metric_xyz")
        assert score == 2550.0

    def test_missing_metric_value_defaults_to_zero(self):
        result = {"params": {}}
        score = _calculate_composite_score(result, "sharpe_ratio")
        assert score == 0

    def test_calmar_ratio_zero_drawdown(self):
        result = {"total_return": 10.0, "max_drawdown": 0.0}
        score = _calculate_composite_score(result, "calmar_ratio")
        assert score == 100.0  # 10 * 10

    def test_none_values_handled(self):
        result = {"sharpe_ratio": None, "net_profit": None}
        score = _calculate_composite_score(result, "sharpe_ratio")
        assert score == 0


# ============================================================================
# Test: _passes_dynamic_constraints — all 6 operators
# ============================================================================


class TestPassesDynamicConstraints:
    """Tests for constraint filtering with all operator types."""

    def test_less_than_or_equal_passes(self, sample_result):
        constraints = [{"metric": "max_drawdown", "operator": "<=", "value": 10}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_less_than_or_equal_fails(self, sample_result):
        constraints = [{"metric": "max_drawdown", "operator": "<=", "value": 5}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_greater_than_or_equal_passes(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": ">=", "value": 50}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_greater_than_or_equal_fails(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": ">=", "value": 200}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_less_than_passes(self, sample_result):
        constraints = [{"metric": "max_drawdown", "operator": "<", "value": 10}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_less_than_fails(self, sample_result):
        constraints = [{"metric": "max_drawdown", "operator": "<", "value": 8}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_greater_than_passes(self, sample_result):
        constraints = [{"metric": "win_rate", "operator": ">", "value": 60}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_greater_than_fails(self, sample_result):
        constraints = [{"metric": "win_rate", "operator": ">", "value": 70}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_equal_passes(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": "==", "value": 120}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_equal_fails(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": "==", "value": 100}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_not_equal_passes(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": "!=", "value": 100}]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_not_equal_fails(self, sample_result):
        constraints = [{"metric": "total_trades", "operator": "!=", "value": 120}]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_multiple_constraints_all_pass(self, sample_result):
        constraints = [
            {"metric": "max_drawdown", "operator": "<=", "value": 15},
            {"metric": "total_trades", "operator": ">=", "value": 50},
            {"metric": "win_rate", "operator": ">", "value": 50},
        ]
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_multiple_constraints_one_fails(self, sample_result):
        constraints = [
            {"metric": "max_drawdown", "operator": "<=", "value": 5},  # fails
            {"metric": "total_trades", "operator": ">=", "value": 50},
        ]
        assert _passes_dynamic_constraints(sample_result, constraints) is False

    def test_empty_constraints_passes(self, sample_result):
        assert _passes_dynamic_constraints(sample_result, []) is True

    def test_constraint_with_missing_metric_skipped(self, sample_result):
        constraints = [{"metric": "nonexistent_metric", "operator": ">=", "value": 0}]
        # Should pass because metric value defaults to 0, and 0 >= 0 is True
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_constraint_with_none_value_skipped(self, sample_result):
        constraints = [{"metric": "win_rate", "operator": ">=", "value": None}]
        # Should be skipped (incomplete constraint)
        assert _passes_dynamic_constraints(sample_result, constraints) is True

    def test_max_drawdown_absolute_value_used(self):
        """max_drawdown stored as negative should use absolute value."""
        result = {"max_drawdown": -15.0}
        constraints = [{"metric": "max_drawdown", "operator": "<=", "value": 20}]
        assert _passes_dynamic_constraints(result, constraints) is True

    def test_max_drawdown_absolute_value_fails(self):
        result = {"max_drawdown": -25.0}
        constraints = [{"metric": "max_drawdown", "operator": "<=", "value": 20}]
        assert _passes_dynamic_constraints(result, constraints) is False


# ============================================================================
# Test: _passes_filters — combined filters + dynamic constraints
# ============================================================================


class TestPassesFilters:
    """Tests for _passes_filters which combines static and dynamic constraints."""

    def test_no_filters_passes(self, sample_result):
        assert _passes_filters(sample_result, {}) is True

    def test_min_trades_filter_passes(self, sample_result):
        assert _passes_filters(sample_result, {"min_trades": 50}) is True

    def test_min_trades_filter_fails(self, sample_result):
        assert _passes_filters(sample_result, {"min_trades": 200}) is False

    def test_max_drawdown_limit_passes(self, sample_result):
        # max_drawdown_limit is fraction (0-1), max_drawdown is in percent
        assert _passes_filters(sample_result, {"max_drawdown_limit": 0.15}) is True

    def test_max_drawdown_limit_fails(self, sample_result):
        assert _passes_filters(sample_result, {"max_drawdown_limit": 0.05}) is False

    def test_min_profit_factor_passes(self, sample_result):
        assert _passes_filters(sample_result, {"min_profit_factor": 1.5}) is True

    def test_min_profit_factor_fails(self, sample_result):
        assert _passes_filters(sample_result, {"min_profit_factor": 3.0}) is False

    def test_min_win_rate_passes(self, sample_result):
        assert _passes_filters(sample_result, {"min_win_rate": 0.5}) is True

    def test_min_win_rate_fails(self, sample_result):
        assert _passes_filters(sample_result, {"min_win_rate": 0.8}) is False

    def test_dynamic_constraints_in_filters(self, sample_result):
        """Dynamic constraints from EvaluationCriteriaPanel should be applied."""
        request_params = {
            "constraints": [
                {"metric": "max_drawdown", "operator": "<=", "value": 10},
                {"metric": "total_trades", "operator": ">=", "value": 50},
            ]
        }
        assert _passes_filters(sample_result, request_params) is True

    def test_dynamic_constraints_fail(self, sample_result):
        request_params = {
            "constraints": [
                {"metric": "max_drawdown", "operator": "<=", "value": 3},  # fails
            ]
        }
        assert _passes_filters(sample_result, request_params) is False

    def test_combined_static_and_dynamic(self, sample_result):
        """Both static filters and dynamic constraints must pass."""
        request_params = {
            "min_trades": 50,
            "constraints": [
                {"metric": "win_rate", "operator": ">=", "value": 60},
            ],
        }
        assert _passes_filters(sample_result, request_params) is True


# ============================================================================
# Test: _rank_by_multi_criteria — multi-criteria ranking
# ============================================================================


class TestRankByMultiCriteria:
    """Tests for multi-criteria ranking system."""

    def test_single_criterion_ranking(self, multiple_results):
        ranked = _rank_by_multi_criteria(multiple_results, ["sharpe_ratio"])
        # Best sharpe: result[1] (2.5) > result[0] (1.5) > result[2] (0.8)
        assert ranked[0]["params"]["rsi_period"] == 21

    def test_multi_criteria_ranking(self, multiple_results):
        ranked = _rank_by_multi_criteria(multiple_results, ["sharpe_ratio", "max_drawdown"])
        # result[1] is best in both sharpe (rank 1) and drawdown (rank 1)
        assert ranked[0]["params"]["rsi_period"] == 21

    def test_inverted_metric_ranking(self, multiple_results):
        """max_drawdown: lower = better."""
        ranked = _rank_by_multi_criteria(multiple_results, ["max_drawdown"])
        # Best drawdown: result[1] (-5%) > result[0] (-20%) > result[2] (-35%)
        assert ranked[0]["params"]["rsi_period"] == 21

    def test_score_set_negative_avg_rank(self, multiple_results):
        ranked = _rank_by_multi_criteria(multiple_results, ["net_profit"])
        # Score should be negative average rank
        assert ranked[0]["score"] == -1  # rank 1 → score -1

    def test_empty_results(self):
        assert _rank_by_multi_criteria([], ["sharpe_ratio"]) == []

    def test_empty_criteria(self, multiple_results):
        original_len = len(multiple_results)
        result = _rank_by_multi_criteria(multiple_results, [])
        assert len(result) == original_len

    def test_unknown_criterion_ignored(self, multiple_results):
        """Unknown criterion should not crash."""
        ranked = _rank_by_multi_criteria(multiple_results, ["unknown_metric"])
        assert len(ranked) == 3

    def test_new_metrics_supported(self, multiple_results):
        """New metrics (sortino_ratio, expectancy) should be rankable."""
        ranked = _rank_by_multi_criteria(multiple_results, ["sortino_ratio"])
        # result[1] has sortino 3.5 > result[0] 2.0 > result[2] 1.0
        assert ranked[0]["params"]["rsi_period"] == 21


# ============================================================================
# Test: _compute_weighted_composite — weighted normalization
# ============================================================================


class TestComputeWeightedComposite:
    """Tests for weighted composite score calculation."""

    def test_single_metric_weight(self, sample_result):
        weights = {"sharpe_ratio": 1.0}
        score = _compute_weighted_composite(sample_result, weights)
        # sharpe 1.8 → normalized: (min(max(1.8, -2), 3) + 2) / 5 = 3.8/5 = 0.76
        assert score == pytest.approx(0.76, abs=0.01)

    def test_multiple_metrics_weighted(self, sample_result):
        weights = {"sharpe_ratio": 0.5, "win_rate": 0.5}
        score = _compute_weighted_composite(sample_result, weights)
        # sharpe 1.8 → 0.76, win_rate 65 → 0.65
        expected = 0.76 * 0.5 + 0.65 * 0.5
        assert score == pytest.approx(expected, abs=0.01)

    def test_max_drawdown_inverted(self, sample_result):
        weights = {"max_drawdown": 1.0}
        score = _compute_weighted_composite(sample_result, weights)
        # max_dd -8.5 → abs(8.5) → 1 - 8.5/100 = 0.915
        assert score == pytest.approx(0.915, abs=0.01)

    def test_profit_factor_normalized(self, sample_result):
        weights = {"profit_factor": 1.0}
        score = _compute_weighted_composite(sample_result, weights)
        # PF 2.1 → min(2.1, 5)/5 = 0.42
        assert score == pytest.approx(0.42, abs=0.01)

    def test_empty_weights_returns_zero(self, sample_result):
        assert _compute_weighted_composite(sample_result, {}) == 0.0
        assert _compute_weighted_composite(sample_result, None) == 0.0

    def test_new_metrics_normalized(self, sample_result):
        """New metrics (sortino, expectancy, etc.) should have normalization."""
        weights = {"sortino_ratio": 0.5, "expectancy": 0.5}
        score = _compute_weighted_composite(sample_result, weights)
        assert 0.0 <= score <= 1.0

    def test_all_twenty_metrics_handled(self, sample_result):
        """Each of 20 frontend metrics should be handled without crash."""
        all_metrics = [
            "total_return",
            "cagr",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "max_drawdown",
            "avg_drawdown",
            "volatility",
            "var_95",
            "risk_adjusted_return",
            "win_rate",
            "profit_factor",
            "avg_win",
            "avg_loss",
            "expectancy",
            "payoff_ratio",
            "total_trades",
            "trades_per_month",
            "avg_trade_duration",
            "avg_bars_in_trade",
        ]
        for metric in all_metrics:
            weights = {metric: 1.0}
            score = _compute_weighted_composite(sample_result, weights)
            assert isinstance(score, float), f"Metric {metric} failed"
            assert 0.0 <= score <= 1.0, f"Metric {metric} score {score} out of [0,1]"


# ============================================================================
# Test: _apply_custom_sort_order — multi-level sorting
# ============================================================================


class TestApplyCustomSortOrder:
    """Tests for custom sort order application."""

    def test_single_level_desc(self, multiple_results):
        sort_order = [{"metric": "sharpe_ratio", "direction": "desc"}]
        sorted_results = _apply_custom_sort_order(multiple_results, sort_order)
        assert sorted_results[0]["sharpe_ratio"] >= sorted_results[1]["sharpe_ratio"]

    def test_single_level_asc(self, multiple_results):
        sort_order = [{"metric": "max_drawdown", "direction": "asc"}]
        sorted_results = _apply_custom_sort_order(multiple_results, sort_order)
        # asc sorts by value: -35 < -20 < -5
        assert sorted_results[0]["max_drawdown"] <= sorted_results[1]["max_drawdown"]

    def test_multi_level_sort(self, multiple_results):
        sort_order = [
            {"metric": "sharpe_ratio", "direction": "desc"},
            {"metric": "total_return", "direction": "desc"},
        ]
        sorted_results = _apply_custom_sort_order(multiple_results, sort_order)
        # Primary sort by sharpe desc
        assert sorted_results[0]["sharpe_ratio"] >= sorted_results[1]["sharpe_ratio"]

    def test_empty_sort_order(self, multiple_results):
        result = _apply_custom_sort_order(multiple_results, [])
        assert len(result) == len(multiple_results)

    def test_empty_results(self):
        assert _apply_custom_sort_order([], [{"metric": "sharpe_ratio", "direction": "desc"}]) == []


# ============================================================================
# Test: SyncOptimizationRequest — Pydantic model validation
# ============================================================================


class TestSyncOptimizationRequestModel:
    """Tests for SyncOptimizationRequest Pydantic model."""

    def test_default_values(self):
        req = SyncOptimizationRequest()
        assert req.optimize_metric == "net_profit"
        assert req.selection_criteria == ["net_profit", "max_drawdown"]
        assert req.constraints is None
        assert req.sort_order is None
        assert req.use_composite is False
        assert req.weights is None

    def test_accepts_evaluation_criteria_fields(self):
        req = SyncOptimizationRequest(
            optimize_metric="sharpe_ratio",
            selection_criteria=["sharpe_ratio", "max_drawdown", "win_rate"],
            constraints=[{"metric": "max_drawdown", "operator": "<=", "value": 15}],
            sort_order=[{"metric": "sharpe_ratio", "direction": "desc"}],
            use_composite=True,
            weights={"sharpe_ratio": 0.4, "win_rate": 0.3, "max_drawdown": 0.3},
        )
        assert req.optimize_metric == "sharpe_ratio"
        assert len(req.selection_criteria) == 3
        assert len(req.constraints) == 1
        assert len(req.sort_order) == 1
        assert req.use_composite is True
        assert req.weights["sharpe_ratio"] == 0.4

    def test_accepts_all_frontend_metrics_as_optimize_metric(self):
        """All 20 frontend metrics should be accepted as optimize_metric."""
        all_metrics = [
            "total_return",
            "cagr",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "max_drawdown",
            "avg_drawdown",
            "volatility",
            "var_95",
            "risk_adjusted_return",
            "win_rate",
            "profit_factor",
            "avg_win",
            "avg_loss",
            "expectancy",
            "payoff_ratio",
            "total_trades",
            "trades_per_month",
            "avg_trade_duration",
            "avg_bars_in_trade",
        ]
        for metric in all_metrics:
            req = SyncOptimizationRequest(optimize_metric=metric)
            assert req.optimize_metric == metric

    def test_accepts_properties_panel_fields(self):
        """Fields from Properties panel should be accepted."""
        req = SyncOptimizationRequest(
            symbol="ETHUSDT",
            interval="4h",
            direction="long",
            initial_capital=50000.0,
            leverage=20,
            commission=0.0005,
        )
        assert req.symbol == "ETHUSDT"
        assert req.interval == "4h"
        assert req.direction == "long"
        assert req.initial_capital == 50000.0
        assert req.leverage == 20
        assert req.commission == 0.0005

    def test_default_commission_is_tv_parity(self):
        req = SyncOptimizationRequest()
        assert req.commission == 0.0007


# ============================================================================
# Test: Integration — evaluation criteria end-to-end flow
# ============================================================================


class TestEvaluationCriteriaIntegration:
    """Integration tests for the full evaluation criteria flow."""

    def test_conservative_preset_flow(self, multiple_results):
        """Simulate conservative preset: optimize sharpe, constrain drawdown."""
        # Conservative preset from frontend:
        # primary: sharpe_ratio, constraints: max_dd <= 15%
        request_params = {
            "optimize_metric": "sharpe_ratio",
            "constraints": [
                {"metric": "max_drawdown", "operator": "<=", "value": 15},
            ],
        }

        # Filter
        filtered = [r for r in multiple_results if _passes_filters(r, request_params)]
        # result[0] has abs(max_dd)=20% → fails (>15)
        # result[1] has abs(max_dd)=5%  → passes
        # result[2] has abs(max_dd)=35% → fails
        assert len(filtered) == 1
        assert filtered[0]["params"]["rsi_period"] == 21

        # Score
        for r in filtered:
            r["score"] = _calculate_composite_score(r, "sharpe_ratio")

        # Best should be result[1] (sharpe=2.5)
        best = max(filtered, key=lambda x: x["score"])
        assert best["params"]["rsi_period"] == 21

    def test_aggressive_preset_flow(self, multiple_results):
        """Simulate aggressive preset: optimize total_return, no constraints."""
        request_params = {
            "optimize_metric": "total_return",
        }

        for r in multiple_results:
            r["score"] = _calculate_composite_score(r, "total_return")

        best = max(multiple_results, key=lambda x: x["score"])
        # result[2] has highest total_return (50%)
        assert best["params"]["rsi_period"] == 7

    def test_composite_score_flow(self, multiple_results):
        """Simulate composite scoring with weights."""
        weights = {"sharpe_ratio": 0.4, "win_rate": 0.3, "max_drawdown": 0.3}

        for r in multiple_results:
            r["composite_score"] = _compute_weighted_composite(r, weights)

        best = max(multiple_results, key=lambda x: x["composite_score"])
        # result[1] should win: best sharpe + best drawdown + good win_rate
        assert best["params"]["rsi_period"] == 21

    def test_multi_criteria_with_sort_order(self, multiple_results):
        """Test ranking + custom sort order combination."""
        # Multi-criteria ranking
        ranked = _rank_by_multi_criteria(multiple_results, ["sharpe_ratio", "max_drawdown"])

        # Apply custom sort order (override ranking by return desc)
        sorted_results = _apply_custom_sort_order(ranked, [{"metric": "total_return", "direction": "desc"}])
        # After sort by total_return desc: result[2] (50%) first
        assert sorted_results[0]["total_return"] == 50.0

    def test_constraints_filter_all_results(self):
        """If all results fail constraints, return empty."""
        results = [
            {"max_drawdown": -30.0, "total_trades": 10, "score": 0, "params": {}},
            {"max_drawdown": -40.0, "total_trades": 20, "score": 0, "params": {}},
        ]
        request_params = {
            "constraints": [
                {"metric": "max_drawdown", "operator": "<=", "value": 5},
            ]
        }
        filtered = [r for r in results if _passes_filters(r, request_params)]
        assert len(filtered) == 0
