"""
Tests for MetricsAnalyzer — backtest results grading & recommendations.

Tests cover:
- Excellent metrics grading
- Good metrics grading
- Acceptable metrics grading
- Poor metrics grading
- Mixed metrics overall score
- Overall grade assignment (A-F)
- Strengths and weaknesses detection
- Recommendations generation
- to_prompt_context formatting
- needs_optimization / is_deployable properties
- Empty metrics handling
- Custom thresholds
- Lower-is-better metric (max_drawdown)
- Partial metrics (not all thresholds matched)
"""

from __future__ import annotations

import pytest

from backend.agents.metrics_analyzer import (
    MetricGrade,
    MetricsAnalyzer,
    OverallGrade,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def analyzer() -> MetricsAnalyzer:
    """Default MetricsAnalyzer instance."""
    return MetricsAnalyzer()


@pytest.fixture
def excellent_metrics() -> dict[str, float]:
    """Metrics that should all grade as Excellent."""
    return {
        "sharpe_ratio": 2.5,
        "profit_factor": 2.5,
        "win_rate": 0.70,
        "max_drawdown": 0.03,
        "calmar_ratio": 4.0,
        "total_trades": 80,
    }


@pytest.fixture
def poor_metrics() -> dict[str, float]:
    """Metrics that should all grade as Poor."""
    return {
        "sharpe_ratio": 0.3,
        "profit_factor": 0.8,
        "win_rate": 0.30,
        "max_drawdown": 0.35,
        "calmar_ratio": 0.2,
        "total_trades": 3,
    }


@pytest.fixture
def mixed_metrics() -> dict[str, float]:
    """Mixed quality metrics."""
    return {
        "sharpe_ratio": 1.82,
        "profit_factor": 1.67,
        "win_rate": 0.524,
        "max_drawdown": 0.123,
        "calmar_ratio": 3.67,
        "total_trades": 245,
    }


# =============================================================================
# TESTS — GRADING
# =============================================================================


class TestMetricGrading:
    """Tests for individual metric grading."""

    def test_excellent_sharpe(self, analyzer: MetricsAnalyzer):
        """sharpe_ratio >= 2.0 → Excellent."""
        result = analyzer.analyze({"sharpe_ratio": 2.5})
        assert result.assessments["sharpe_ratio"].grade == MetricGrade.EXCELLENT

    def test_good_sharpe(self, analyzer: MetricsAnalyzer):
        """1.5 <= sharpe_ratio < 2.0 → Good."""
        result = analyzer.analyze({"sharpe_ratio": 1.7})
        assert result.assessments["sharpe_ratio"].grade == MetricGrade.GOOD

    def test_acceptable_sharpe(self, analyzer: MetricsAnalyzer):
        """1.0 <= sharpe_ratio < 1.5 → Acceptable."""
        result = analyzer.analyze({"sharpe_ratio": 1.2})
        assert result.assessments["sharpe_ratio"].grade == MetricGrade.ACCEPTABLE

    def test_poor_sharpe(self, analyzer: MetricsAnalyzer):
        """sharpe_ratio < 1.0 → Poor."""
        result = analyzer.analyze({"sharpe_ratio": 0.5})
        assert result.assessments["sharpe_ratio"].grade == MetricGrade.POOR

    def test_lower_is_better_excellent(self, analyzer: MetricsAnalyzer):
        """max_drawdown <= 0.05 → Excellent (lower is better)."""
        result = analyzer.analyze({"max_drawdown": 0.03})
        assert result.assessments["max_drawdown"].grade == MetricGrade.EXCELLENT

    def test_lower_is_better_poor(self, analyzer: MetricsAnalyzer):
        """max_drawdown > 0.15 → Poor (lower is better)."""
        result = analyzer.analyze({"max_drawdown": 0.25})
        assert result.assessments["max_drawdown"].grade == MetricGrade.POOR


# =============================================================================
# TESTS — OVERALL SCORE & GRADE
# =============================================================================


class TestOverallScoring:
    """Tests for overall score and grade computation."""

    def test_excellent_metrics_high_score(self, analyzer: MetricsAnalyzer, excellent_metrics: dict):
        """All-excellent metrics → overall_score > 0.85."""
        result = analyzer.analyze(excellent_metrics)
        assert result.overall_score >= 0.85
        assert result.grade == OverallGrade.A

    def test_poor_metrics_low_score(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """All-poor metrics → overall_score < 0.4."""
        result = analyzer.analyze(poor_metrics)
        assert result.overall_score < 0.4
        assert result.grade in (OverallGrade.D, OverallGrade.F)

    def test_mixed_metrics_moderate_score(self, analyzer: MetricsAnalyzer, mixed_metrics: dict):
        """Mixed metrics → moderate score (roughly B or C)."""
        result = analyzer.analyze(mixed_metrics)
        assert 0.4 < result.overall_score < 0.95
        assert result.grade in (OverallGrade.B, OverallGrade.C, OverallGrade.A)

    def test_grade_boundaries(self, analyzer: MetricsAnalyzer):
        """Verify grade boundary logic via _score_to_grade."""
        assert MetricsAnalyzer._score_to_grade(0.90) == OverallGrade.A
        assert MetricsAnalyzer._score_to_grade(0.85) == OverallGrade.A
        assert MetricsAnalyzer._score_to_grade(0.75) == OverallGrade.B
        assert MetricsAnalyzer._score_to_grade(0.60) == OverallGrade.C
        assert MetricsAnalyzer._score_to_grade(0.45) == OverallGrade.D
        assert MetricsAnalyzer._score_to_grade(0.30) == OverallGrade.F


# =============================================================================
# TESTS — STRENGTHS & WEAKNESSES
# =============================================================================


class TestStrengthsWeaknesses:
    """Tests for strengths and weaknesses detection."""

    def test_excellent_metrics_produce_strengths(self, analyzer: MetricsAnalyzer, excellent_metrics: dict):
        """Excellent metrics generate strengths."""
        result = analyzer.analyze(excellent_metrics)
        assert len(result.strengths) > 0
        assert any("excellent" in s for s in result.strengths)

    def test_poor_metrics_produce_weaknesses(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """Poor metrics generate weaknesses."""
        result = analyzer.analyze(poor_metrics)
        assert len(result.weaknesses) > 0

    def test_mixed_has_both(self, analyzer: MetricsAnalyzer, mixed_metrics: dict):
        """Mixed metrics may produce both strengths and weaknesses."""
        result = analyzer.analyze(mixed_metrics)
        # At least one of strengths or weaknesses should be present
        assert len(result.strengths) + len(result.weaknesses) > 0


# =============================================================================
# TESTS — RECOMMENDATIONS
# =============================================================================


class TestRecommendations:
    """Tests for actionable recommendations."""

    def test_poor_sharpe_generates_recommendations(self, analyzer: MetricsAnalyzer):
        """Poor sharpe_ratio triggers recommendations."""
        result = analyzer.analyze({"sharpe_ratio": 0.3})
        assert len(result.recommendations) > 0

    def test_no_duplicate_recommendations(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """Recommendations should be deduplicated."""
        result = analyzer.analyze(poor_metrics)
        assert len(result.recommendations) == len(set(result.recommendations))

    def test_low_score_adds_general_recommendation(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """Overall score < 0.4 produces multiple actionable recommendations."""
        result = analyzer.analyze(poor_metrics)
        # With all-poor metrics, there should be many recommendations
        assert len(result.recommendations) >= 3


# =============================================================================
# TESTS — SERIALIZATION
# =============================================================================


class TestSerialization:
    """Tests for to_dict and to_prompt_context."""

    def test_to_dict_structure(self, analyzer: MetricsAnalyzer, mixed_metrics: dict):
        """to_dict returns expected keys."""
        result = analyzer.analyze(mixed_metrics)
        d = result.to_dict()

        assert "overall_score" in d
        assert "grade" in d
        assert "needs_optimization" in d
        assert "is_deployable" in d
        assert "assessments" in d
        assert "strengths" in d
        assert "weaknesses" in d
        assert "recommendations" in d

    def test_to_prompt_context_is_string(self, analyzer: MetricsAnalyzer, mixed_metrics: dict):
        """to_prompt_context returns a non-empty string."""
        result = analyzer.analyze(mixed_metrics)
        ctx = result.to_prompt_context()

        assert isinstance(ctx, str)
        assert len(ctx) > 0
        assert "Overall Score:" in ctx
        assert "METRIC GRADES:" in ctx

    def test_to_prompt_context_includes_strengths(self, analyzer: MetricsAnalyzer, excellent_metrics: dict):
        """to_prompt_context includes strengths section."""
        result = analyzer.analyze(excellent_metrics)
        ctx = result.to_prompt_context()
        assert "STRENGTHS:" in ctx


# =============================================================================
# TESTS — PROPERTIES
# =============================================================================


class TestProperties:
    """Tests for computed properties."""

    def test_needs_optimization_for_poor(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """Poor metrics → needs_optimization = True."""
        result = analyzer.analyze(poor_metrics)
        assert result.needs_optimization is True

    def test_not_needs_optimization_for_excellent(self, analyzer: MetricsAnalyzer, excellent_metrics: dict):
        """Excellent metrics → needs_optimization = False."""
        result = analyzer.analyze(excellent_metrics)
        assert result.needs_optimization is False

    def test_is_deployable_for_excellent(self, analyzer: MetricsAnalyzer, excellent_metrics: dict):
        """Excellent metrics → is_deployable = True."""
        result = analyzer.analyze(excellent_metrics)
        assert result.is_deployable is True

    def test_not_deployable_for_poor(self, analyzer: MetricsAnalyzer, poor_metrics: dict):
        """Poor metrics → is_deployable = False."""
        result = analyzer.analyze(poor_metrics)
        assert result.is_deployable is False


# =============================================================================
# TESTS — EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_empty_metrics(self, analyzer: MetricsAnalyzer):
        """Empty metrics dict → F grade with recommendation."""
        result = analyzer.analyze({})
        assert result.grade == OverallGrade.F
        assert result.overall_score == 0.0
        assert len(result.recommendations) > 0

    def test_unknown_metrics_ignored(self, analyzer: MetricsAnalyzer):
        """Unknown metric keys are not graded."""
        result = analyzer.analyze(
            {
                "sharpe_ratio": 2.0,
                "custom_metric_xyz": 42.0,
            }
        )
        assert "sharpe_ratio" in result.assessments
        assert "custom_metric_xyz" not in result.assessments

    def test_partial_metrics(self, analyzer: MetricsAnalyzer):
        """Providing only some metrics still works."""
        result = analyzer.analyze({"sharpe_ratio": 1.5, "win_rate": 0.55})
        assert len(result.assessments) == 2
        assert result.overall_score > 0.0

    def test_custom_thresholds(self):
        """Custom thresholds override defaults."""
        custom = {
            "sharpe_ratio": {
                "direction": "higher_is_better",
                "excellent": 5.0,
                "good": 3.0,
                "acceptable": 1.0,
                "weight": 1.0,
                "display": "Custom Sharpe",
            },
        }
        analyzer = MetricsAnalyzer(thresholds=custom)
        result = analyzer.analyze({"sharpe_ratio": 2.0})
        # 2.0 is between acceptable(1.0) and good(3.0) with custom thresholds
        assert result.assessments["sharpe_ratio"].grade == MetricGrade.ACCEPTABLE

    def test_non_numeric_metric_skipped(self, analyzer: MetricsAnalyzer):
        """Non-numeric metric values are safely skipped."""
        result = analyzer.analyze(
            {
                "sharpe_ratio": "not_a_number",
                "win_rate": 0.55,
            }
        )
        assert "sharpe_ratio" not in result.assessments
        assert "win_rate" in result.assessments

    def test_metric_grade_enum_values(self):
        """MetricGrade enum has expected values."""
        assert MetricGrade.EXCELLENT == "excellent"
        assert MetricGrade.GOOD == "good"
        assert MetricGrade.ACCEPTABLE == "acceptable"
        assert MetricGrade.POOR == "poor"

    def test_overall_grade_enum_values(self):
        """OverallGrade enum has expected values."""
        assert OverallGrade.A == "A"
        assert OverallGrade.B == "B"
        assert OverallGrade.C == "C"
        assert OverallGrade.D == "D"
        assert OverallGrade.F == "F"
