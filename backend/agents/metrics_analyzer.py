"""
Metrics Analyzer — backtest results analysis with threshold-based grading.

Implements Section 3.6 of the spec:
- Threshold assessment (excellent / good / acceptable / poor)
- Overall composite score
- Strengths & weaknesses detection
- Actionable recommendations for strategy improvement
- Integration with ConsensusEngine for feedback loop

The analyzer grades each metric against configurable thresholds
and produces a human-readable analysis with specific improvement
suggestions that can be fed back into the LLM prompt for iteration.

Usage:
    analyzer = MetricsAnalyzer()
    analysis = analyzer.analyze(backtest_metrics)

    print(f"Overall: {analysis.overall_score:.0%}")
    print(f"Grade: {analysis.grade}")
    for rec in analysis.recommendations:
        print(f"  💡 {rec}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

# =============================================================================
# ENUMS & MODELS
# =============================================================================


class MetricGrade(str, Enum):
    """Quality grade for a single metric."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


class OverallGrade(str, Enum):
    """Overall strategy quality grade."""

    A = "A"  # Excellent — deploy-ready
    B = "B"  # Good — minor tuning recommended
    C = "C"  # Acceptable — moderate optimization needed
    D = "D"  # Poor — significant changes required
    F = "F"  # Fail — redesign needed


@dataclass
class MetricAssessment:
    """Assessment of a single metric."""

    metric_name: str
    value: float
    grade: MetricGrade
    score: float  # 0.0-1.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize."""
        return {
            "metric_name": self.metric_name,
            "value": round(self.value, 4),
            "grade": self.grade.value,
            "score": round(self.score, 4),
            "description": self.description,
        }


@dataclass
class AnalysisResult:
    """Complete analysis of backtest results."""

    overall_score: float  # 0.0-1.0
    grade: OverallGrade
    assessments: dict[str, MetricAssessment] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_metrics: dict[str, float] = field(default_factory=dict)

    @property
    def needs_optimization(self) -> bool:
        """Whether strategy needs further optimization."""
        return self.overall_score < 0.7

    @property
    def is_deployable(self) -> bool:
        """Whether strategy quality is sufficient for deployment."""
        return self.overall_score >= 0.6 and self.grade in (OverallGrade.A, OverallGrade.B)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade.value,
            "needs_optimization": self.needs_optimization,
            "is_deployable": self.is_deployable,
            "assessments": {k: v.to_dict() for k, v in self.assessments.items()},
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
        }

    def to_prompt_context(self) -> str:
        """
        Format analysis as text for LLM re-prompting.

        Used in the feedback loop:
        backtest → analyze → re-prompt LLM → improved strategy.
        """
        parts = [
            f"Overall Score: {self.overall_score:.0%} (Grade: {self.grade.value})",
            "",
            "METRIC GRADES:",
        ]
        for name, assessment in self.assessments.items():
            parts.append(f"  {name}: {assessment.value:.4f} — {assessment.grade.value.upper()}")

        if self.strengths:
            parts.append("")
            parts.append("STRENGTHS:")
            for s in self.strengths:
                parts.append(f"  ✅ {s}")

        if self.weaknesses:
            parts.append("")
            parts.append("WEAKNESSES:")
            for w in self.weaknesses:
                parts.append(f"  ❌ {w}")

        if self.recommendations:
            parts.append("")
            parts.append("RECOMMENDATIONS:")
            for r in self.recommendations:
                parts.append(f"  💡 {r}")

        return "\n".join(parts)


# =============================================================================
# THRESHOLDS
# =============================================================================

# Metric thresholds define grading boundaries.
# Metrics are classified as "higher_is_better" or "lower_is_better".

METRIC_THRESHOLDS: dict[str, dict[str, Any]] = {
    "sharpe_ratio": {
        "direction": "higher_is_better",
        "excellent": 2.0,
        "good": 1.5,
        "acceptable": 1.0,
        "weight": 0.25,  # importance weight in overall score
        "display": "Sharpe Ratio",
    },
    "profit_factor": {
        "direction": "higher_is_better",
        "excellent": 2.0,
        "good": 1.5,
        "acceptable": 1.2,
        "weight": 0.20,
        "display": "Profit Factor",
    },
    "win_rate": {
        "direction": "higher_is_better",
        "excellent": 0.65,
        "good": 0.55,
        "acceptable": 0.45,
        "weight": 0.15,
        "display": "Win Rate",
    },
    "max_drawdown": {
        "direction": "lower_is_better",
        "excellent": 0.05,
        "good": 0.10,
        "acceptable": 0.15,
        "weight": 0.20,
        "display": "Max Drawdown",
    },
    "calmar_ratio": {
        "direction": "higher_is_better",
        "excellent": 3.0,
        "good": 2.0,
        "acceptable": 1.0,
        "weight": 0.10,
        "display": "Calmar Ratio",
    },
    "total_trades": {
        "direction": "higher_is_better",
        "excellent": 50,
        "good": 30,
        "acceptable": 10,
        "weight": 0.10,
        "display": "Total Trades",
    },
}

# Recommendation templates keyed by metric + grade
_RECOMMENDATIONS: dict[str, list[str]] = {
    "sharpe_ratio:poor": [
        "Increase risk-adjusted return: add trend-following filters",
        "Reduce trade frequency to filter low-quality signals",
        "Optimize stop-loss to improve average trade quality",
    ],
    "sharpe_ratio:acceptable": [
        "Fine-tune entry timing for better risk-reward ratio",
        "Consider adding a confirming secondary indicator",
    ],
    "profit_factor:poor": [
        "Average loss exceeds average win — tighten stop-loss or widen take-profit",
        "Remove weakest signal if using multiple indicators",
    ],
    "profit_factor:acceptable": [
        "Optimize take-profit/stop-loss ratio to improve profit factor",
    ],
    "win_rate:poor": [
        "Add confirming indicators to improve signal accuracy",
        "Add volume filter to remove false signals",
        "Consider stricter entry conditions",
    ],
    "win_rate:acceptable": [
        "Fine-tune indicator parameters for better entry precision",
    ],
    "max_drawdown:poor": [
        "Reduce position size or leverage",
        "Add trailing stop-loss to protect gains",
        "Introduce volatility filter to avoid high-volatility periods",
    ],
    "max_drawdown:acceptable": [
        "Consider dynamic position sizing based on ATR",
    ],
    "calmar_ratio:poor": [
        "Strategy return does not justify the drawdown risk",
        "Consider reducing exposure during drawdown periods",
    ],
    "total_trades:poor": [
        "Too few trades for statistical significance",
        "Loosen entry conditions or reduce minimum signal threshold",
        "Extend backtest period for more data",
    ],
}


# =============================================================================
# METRICS ANALYZER
# =============================================================================


class MetricsAnalyzer:
    """
    Analyzes backtest results against quality thresholds.

    Produces:
    - Per-metric grading (excellent/good/acceptable/poor)
    - Overall composite score (0-1)
    - Overall letter grade (A-F)
    - Strengths and weaknesses list
    - Actionable recommendations for improvement

    Thresholds are configurable via constructor or class-level defaults.

    Example:
        analyzer = MetricsAnalyzer()
        result = analyzer.analyze({
            "sharpe_ratio": 1.82,
            "profit_factor": 1.67,
            "win_rate": 0.524,
            "max_drawdown": 0.123,
            "calmar_ratio": 3.67,
            "total_trades": 245,
        })
        print(result.grade)        # OverallGrade.B
        print(result.strengths)    # ["Calmar Ratio: 3.67 (excellent)", ...]
        print(result.recommendations)
    """

    def __init__(
        self,
        thresholds: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._thresholds = thresholds or METRIC_THRESHOLDS

    def analyze(self, metrics: dict[str, Any]) -> AnalysisResult:
        """
        Analyze backtest metrics against thresholds.

        Args:
            metrics: Dict of metric_name → value.
                     Keys should match METRIC_THRESHOLDS keys.
                     Extra keys are preserved but not graded.

        Returns:
            AnalysisResult with grades, score, and recommendations.
        """
        if not metrics:
            return AnalysisResult(
                overall_score=0.0,
                grade=OverallGrade.F,
                recommendations=["No metrics provided — run a backtest first"],
                raw_metrics={},
            )

        assessments: dict[str, MetricAssessment] = {}
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommendations: list[str] = []
        score_components: list[tuple[float, float]] = []  # (score, weight)

        for metric_name, config in self._thresholds.items():
            value = metrics.get(metric_name)
            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            # Grade the metric
            grade, score = self._grade_metric(value, config)
            display = config.get("display", metric_name)

            assessment = MetricAssessment(
                metric_name=metric_name,
                value=value,
                grade=grade,
                score=score,
                description=f"{display}: {self._format_value(metric_name, value)} — {grade.value}",
            )
            assessments[metric_name] = assessment

            # Weighted score
            weight = config.get("weight", 0.1)
            score_components.append((score, weight))

            # Strengths / Weaknesses
            formatted = self._format_value(metric_name, value)
            if grade == MetricGrade.EXCELLENT:
                strengths.append(f"{display}: {formatted} (excellent)")
            elif grade == MetricGrade.GOOD:
                strengths.append(f"{display}: {formatted} (good)")
            elif grade == MetricGrade.POOR:
                if config["direction"] == "lower_is_better":
                    weaknesses.append(f"{display}: {formatted} (exceeds {config['acceptable']})")
                else:
                    weaknesses.append(f"{display}: {formatted} (below {config['acceptable']})")

            # Recommendations
            recs_key = f"{metric_name}:{grade.value}"
            if recs_key in _RECOMMENDATIONS:
                recommendations.extend(_RECOMMENDATIONS[recs_key])

        # Overall score (weighted)
        if score_components:
            total_weight = sum(w for _, w in score_components)
            overall = sum(s * w for s, w in score_components) / total_weight if total_weight > 0 else 0.0
        else:
            overall = 0.0

        # Overall grade
        overall_grade = self._score_to_grade(overall)

        # General recommendations for low scores (insert at front)
        if overall < 0.4:
            recommendations.insert(
                0,
                "Consider a complete strategy redesign — current approach is not viable",
            )
        elif overall < 0.6:
            recommendations.insert(
                0,
                "Moderate optimization required — focus on the weakest metrics",
            )

        # Deduplicate recommendations
        seen: set[str] = set()
        unique_recs: list[str] = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)

        result = AnalysisResult(
            overall_score=overall,
            grade=overall_grade,
            assessments=assessments,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=unique_recs[:7],  # cap at 7
            raw_metrics={k: float(v) for k, v in metrics.items() if isinstance(v, int | float)},
        )

        logger.info(
            f"📊 Metrics analysis: score={overall:.2%}, grade={overall_grade.value}, "
            f"{len(strengths)} strengths, {len(weaknesses)} weaknesses, "
            f"{len(unique_recs)} recommendations"
        )
        return result

    # ─────────────────────────────────────────────────────────────────
    # GRADING
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _grade_metric(
        value: float,
        config: dict[str, Any],
    ) -> tuple[MetricGrade, float]:
        """
        Grade a single metric value against thresholds.

        Returns:
            (MetricGrade, normalized_score 0-1)
        """
        direction = config.get("direction", "higher_is_better")
        excellent = config["excellent"]
        good = config["good"]
        acceptable = config["acceptable"]

        if direction == "lower_is_better":
            # Lower is better (e.g. max_drawdown)
            if value <= excellent:
                return MetricGrade.EXCELLENT, 1.0
            if value <= good:
                # Interpolate between 1.0 and 0.7
                frac = (value - excellent) / (good - excellent) if good != excellent else 0
                return MetricGrade.GOOD, 1.0 - 0.3 * frac
            if value <= acceptable:
                frac = (value - good) / (acceptable - good) if acceptable != good else 0
                return MetricGrade.ACCEPTABLE, 0.7 - 0.3 * frac
            # Poor: above acceptable
            # Score decays from 0.4 toward 0
            overshoot = (value - acceptable) / max(acceptable, 0.01)
            return MetricGrade.POOR, max(0.0, 0.4 - 0.4 * min(overshoot, 1.0))
        else:
            # Higher is better (e.g. sharpe_ratio)
            if value >= excellent:
                return MetricGrade.EXCELLENT, 1.0
            if value >= good:
                frac = (excellent - value) / (excellent - good) if excellent != good else 0
                return MetricGrade.GOOD, 1.0 - 0.3 * frac
            if value >= acceptable:
                frac = (good - value) / (good - acceptable) if good != acceptable else 0
                return MetricGrade.ACCEPTABLE, 0.7 - 0.3 * frac
            # Poor: below acceptable
            undershoot = (acceptable - value) / acceptable if acceptable > 0 else 1.0
            return MetricGrade.POOR, max(0.0, 0.4 - 0.4 * min(undershoot, 1.0))

    @staticmethod
    def _score_to_grade(score: float) -> OverallGrade:
        """Map overall score (0-1) to letter grade."""
        if score >= 0.85:
            return OverallGrade.A
        if score >= 0.70:
            return OverallGrade.B
        if score >= 0.55:
            return OverallGrade.C
        if score >= 0.40:
            return OverallGrade.D
        return OverallGrade.F

    @staticmethod
    def _format_value(metric_name: str, value: float) -> str:
        """Format metric value for display."""
        if metric_name in ("win_rate", "max_drawdown"):
            return f"{value:.2%}"
        if metric_name == "total_trades":
            return str(int(value))
        return f"{value:.2f}"
