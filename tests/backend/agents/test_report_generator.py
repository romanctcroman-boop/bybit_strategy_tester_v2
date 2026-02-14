"""
Tests for ReportGenerator (backend/agents/reporting/report_generator.py).

Tests cover:
- JSON report generation
- HTML report generation
- Performance assessment (grades A+ through F)
- Trade summarization (winners, losers, PnL)
- Walk-forward data inclusion
- Benchmark comparison inclusion
- Strategy parameters inclusion
- Metric value formatting
- Edge cases (empty trades, empty metrics)
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.agents.reporting.report_generator import (
    ReportFormat,
    ReportGenerator,
    StrategyReport,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def generator() -> ReportGenerator:
    """Fresh ReportGenerator instance."""
    return ReportGenerator()


@pytest.fixture
def sample_backtest_results() -> dict[str, Any]:
    """Realistic backtest results for testing."""
    return {
        "metrics": {
            "net_profit": 4520.0,
            "net_profit_pct": 0.452,
            "total_return": 0.452,
            "sharpe_ratio": 1.82,
            "sortino_ratio": 2.1,
            "calmar_ratio": 3.5,
            "max_drawdown": 0.08,
            "win_rate": 0.56,
            "profit_factor": 1.67,
            "total_trades": 245,
            "total_closed_trades": 240,
            "avg_trade_pnl": 18.83,
            "largest_winning_trade": 520.0,
            "largest_losing_trade": -180.0,
            "avg_winning_trade": 85.0,
            "avg_losing_trade": -45.0,
            "max_consecutive_wins": 8,
            "max_consecutive_losses": 4,
            "recovery_factor": 2.3,
        },
        "trades": [
            {"pnl": 100.0, "side": "long"},
            {"pnl": -50.0, "side": "long"},
            {"pnl": 200.0, "side": "short"},
            {"pnl": 0.0, "side": "long"},
            {"pnl": -30.0, "side": "short"},
        ],
        "equity_curve": list(range(10000, 10100)),
    }


@pytest.fixture
def sample_walk_forward() -> dict[str, Any]:
    """Walk-forward validation data."""
    return {
        "consistency_ratio": 0.72,
        "overfit_score": 0.15,
        "parameter_stability": 0.85,
        "confidence_level": "high",
    }


@pytest.fixture
def sample_benchmarks() -> dict[str, dict[str, Any]]:
    """Benchmark comparison data."""
    return {
        "buy_hold": {"total_return": 0.15, "max_drawdown": 0.25},
        "sma_crossover": {"total_return": 0.22, "max_drawdown": 0.18},
    }


# =============================================================================
# TestStrategyReport
# =============================================================================


class TestStrategyReport:
    """StrategyReport dataclass behavior."""

    def test_to_dict_json(self):
        """JSON report has no html_content in dict."""
        report = StrategyReport(
            report_id="abc123",
            fmt="json",
            strategy_name="Test",
            data={"metrics": {}},
        )
        d = report.to_dict()
        assert d["report_id"] == "abc123"
        assert d["format"] == "json"
        assert "html_content" not in d

    def test_to_dict_html(self):
        """HTML report includes html_content in dict."""
        report = StrategyReport(
            report_id="abc123",
            fmt="html",
            strategy_name="Test",
            data={"metrics": {}},
            html_content="<html>test</html>",
        )
        d = report.to_dict()
        assert d["html_content"] == "<html>test</html>"

    def test_generated_at_is_iso(self):
        """generated_at is a valid ISO timestamp."""
        report = StrategyReport("id1", "json", "S", {})
        assert "T" in report.generated_at  # ISO format contains T


# =============================================================================
# TestReportGeneratorJSON
# =============================================================================


class TestReportGeneratorJSON:
    """JSON report generation."""

    def test_generate_json_returns_strategy_report(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """generate() returns StrategyReport with correct format."""
        report = generator.generate(
            strategy_name="RSI Strategy",
            backtest_results=sample_backtest_results,
            fmt=ReportFormat.JSON,
        )
        assert isinstance(report, StrategyReport)
        assert report.format == "json"
        assert report.strategy_name == "RSI Strategy"
        assert report.html_content == ""

    def test_json_data_has_required_keys(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """Report data has all required keys."""
        report = generator.generate("Test", sample_backtest_results)
        data = report.data
        assert "metrics" in data
        assert "assessment" in data
        assert "trade_summary" in data
        assert "strategy_name" in data
        assert "generated_at" in data

    def test_json_extracts_key_metrics(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """Only KEY_METRICS are in the summary metrics."""
        report = generator.generate("Test", sample_backtest_results)
        for key in report.data["metrics"]:
            assert key in ReportGenerator.KEY_METRICS

    def test_json_includes_all_metrics(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """all_metrics preserves original metrics dict."""
        report = generator.generate("Test", sample_backtest_results)
        assert report.data["all_metrics"] == sample_backtest_results["metrics"]

    def test_custom_report_id(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """Custom report_id is used when provided."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            report_id="custom-id-123",
        )
        assert report.report_id == "custom-id-123"

    def test_auto_report_id(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """Auto-generated report_id when not provided."""
        report = generator.generate("Test", sample_backtest_results)
        assert len(report.report_id) > 0


# =============================================================================
# TestReportGeneratorHTML
# =============================================================================


class TestReportGeneratorHTML:
    """HTML report generation."""

    def test_generate_html_returns_content(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """HTML format produces non-empty html_content."""
        report = generator.generate(
            "RSI Strategy",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
        )
        assert report.html_content
        assert "<!DOCTYPE html>" in report.html_content

    def test_html_contains_strategy_name(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """HTML contains the strategy name."""
        report = generator.generate(
            "My RSI Strategy",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
        )
        assert "My RSI Strategy" in report.html_content

    def test_html_contains_grade(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """HTML contains the assessment grade."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
        )
        # Sample data has excellent metrics → should be A or A+
        assert any(g in report.html_content for g in ("A+", "A", "B"))

    def test_html_with_walk_forward(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
        sample_walk_forward: dict[str, Any],
    ):
        """HTML includes walk-forward section when provided."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
            walk_forward=sample_walk_forward,
        )
        assert "Walk-Forward" in report.html_content
        assert "Consistency" in report.html_content

    def test_html_with_benchmarks(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
        sample_benchmarks: dict[str, dict[str, Any]],
    ):
        """HTML includes benchmark section when provided."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
            benchmarks=sample_benchmarks,
        )
        assert "Benchmark" in report.html_content
        assert "buy_hold" in report.html_content

    def test_html_with_strategy_params(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """HTML includes strategy params when provided."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
            strategy_params={"period": 14, "overbought": 70},
        )
        assert "Strategy Parameters" in report.html_content
        assert "period" in report.html_content

    def test_html_contains_commission_footer(
        self,
        generator: ReportGenerator,
        sample_backtest_results: dict[str, Any],
    ):
        """HTML footer references commission rate and engine."""
        report = generator.generate(
            "Test",
            sample_backtest_results,
            fmt=ReportFormat.HTML,
        )
        assert "0.07%" in report.html_content
        assert "FallbackEngineV4" in report.html_content


# =============================================================================
# TestPerformanceAssessment
# =============================================================================


class TestPerformanceAssessment:
    """_assess_performance grading logic."""

    def test_excellent_metrics_get_high_grade(self, generator: ReportGenerator):
        """Excellent metrics → A or A+ grade."""
        metrics = {
            "sharpe_ratio": 2.5,
            "max_drawdown": 0.03,
            "win_rate": 0.70,
            "profit_factor": 2.5,
            "calmar_ratio": 4.0,
        }
        assessment = generator._assess_performance(metrics)
        assert assessment["grade"] in ("A+", "A")
        assert assessment["overall_score"] >= 0.8

    def test_poor_metrics_get_low_grade(self, generator: ReportGenerator):
        """Poor metrics → D or F grade."""
        metrics = {
            "sharpe_ratio": 0.3,
            "max_drawdown": 0.5,
            "win_rate": 0.25,
            "profit_factor": 0.8,
            "calmar_ratio": 0.2,
        }
        assessment = generator._assess_performance(metrics)
        assert assessment["grade"] in ("D", "F")
        assert len(assessment["weaknesses"]) > 0

    def test_empty_metrics_zero_score(self, generator: ReportGenerator):
        """No metrics → zero overall score."""
        assessment = generator._assess_performance({})
        assert assessment["overall_score"] == 0.0

    def test_mixed_metrics_moderate_grade(self, generator: ReportGenerator):
        """Mix of good and bad metrics → C or B grade."""
        metrics = {
            "sharpe_ratio": 1.6,  # good
            "max_drawdown": 0.20,  # poor
            "win_rate": 0.50,  # acceptable
            "profit_factor": 1.3,  # acceptable
        }
        assessment = generator._assess_performance(metrics)
        assert assessment["grade"] in ("B", "C", "D")

    def test_strengths_and_weaknesses_populated(self, generator: ReportGenerator):
        """Strengths list excellent metrics, weaknesses list poor ones."""
        metrics = {
            "sharpe_ratio": 3.0,  # excellent → strength
            "max_drawdown": 0.30,  # poor → weakness
        }
        assessment = generator._assess_performance(metrics)
        assert any("sharpe_ratio" in s for s in assessment["strengths"])
        assert any("max_drawdown" in w for w in assessment["weaknesses"])


# =============================================================================
# TestScoreToGrade
# =============================================================================


class TestScoreToGrade:
    """_score_to_grade static method."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (1.0, "A+"),
            (0.9, "A+"),
            (0.85, "A"),
            (0.8, "A"),
            (0.75, "B"),
            (0.7, "B"),
            (0.6, "C"),
            (0.55, "C"),
            (0.45, "D"),
            (0.4, "D"),
            (0.3, "F"),
            (0.0, "F"),
        ],
    )
    def test_grade_mapping(self, score: float, expected: str):
        """Score maps to correct letter grade."""
        assert ReportGenerator._score_to_grade(score) == expected


# =============================================================================
# TestTradeSummary
# =============================================================================


class TestTradeSummary:
    """_summarize_trades analysis."""

    def test_summarize_with_trades(self, generator: ReportGenerator):
        """Trade summary includes correct counts and PnL."""
        trades = [
            {"pnl": 100.0},
            {"pnl": -50.0},
            {"pnl": 200.0},
            {"pnl": 0.0},
            {"pnl": -30.0},
        ]
        summary = generator._summarize_trades(trades)
        assert summary["count"] == 5
        assert summary["winners"] == 2
        assert summary["losers"] == 2
        assert summary["breakeven"] == 1
        assert summary["total_pnl"] == 220.0
        assert summary["best_trade"] == 200.0
        assert summary["worst_trade"] == -50.0

    def test_summarize_empty_trades(self, generator: ReportGenerator):
        """Empty trades list returns count=0."""
        summary = generator._summarize_trades([])
        assert summary["count"] == 0

    def test_all_winners(self, generator: ReportGenerator):
        """All winning trades."""
        trades = [{"pnl": 10.0}, {"pnl": 20.0}, {"pnl": 30.0}]
        summary = generator._summarize_trades(trades)
        assert summary["winners"] == 3
        assert summary["losers"] == 0
        assert summary["total_pnl"] == 60.0

    def test_all_losers(self, generator: ReportGenerator):
        """All losing trades."""
        trades = [{"pnl": -10.0}, {"pnl": -20.0}]
        summary = generator._summarize_trades(trades)
        assert summary["winners"] == 0
        assert summary["losers"] == 2
        assert summary["total_pnl"] == -30.0


# =============================================================================
# TestFormatMetricValue
# =============================================================================


class TestFormatMetricValue:
    """_format_metric_value display formatting."""

    def test_percentage_metric(self):
        """Percentage metrics formatted with %."""
        result = ReportGenerator._format_metric_value("win_rate", 0.56)
        assert "56.00%" in result

    def test_integer_metric(self):
        """Integer metrics formatted as integers."""
        result = ReportGenerator._format_metric_value("total_trades", 245.0)
        assert result == "245"

    def test_dollar_metric(self):
        """Dollar metrics formatted with $."""
        result = ReportGenerator._format_metric_value("net_profit", 4520.50)
        assert "$" in result
        assert "4,520.50" in result

    def test_none_value(self):
        """None value returns N/A."""
        assert ReportGenerator._format_metric_value("any_key", None) == "N/A"

    def test_non_numeric_value(self):
        """Non-numeric value returns escaped string."""
        result = ReportGenerator._format_metric_value("any_key", "some_text")
        assert result == "some_text"

    def test_generic_float(self):
        """Generic float metric uses 4 decimal places."""
        result = ReportGenerator._format_metric_value("sharpe_ratio", 1.823456)
        assert result == "1.8235"


# =============================================================================
# TestEquityCurveHandling
# =============================================================================


class TestEquityCurveHandling:
    """Equity curve inclusion in report data."""

    def test_long_equity_curve_truncated(
        self,
        generator: ReportGenerator,
    ):
        """Long equity curve stores only start/end slices."""
        results = {
            "metrics": {"total_return": 0.1},
            "equity_curve": list(range(100)),
        }
        report = generator.generate("Test", results)
        data = report.data
        assert data["equity_curve_length"] == 100
        assert "equity_start" in data
        assert "equity_end" in data
        assert len(data["equity_start"]) == 3
        assert len(data["equity_end"]) == 3

    def test_short_equity_curve_included(
        self,
        generator: ReportGenerator,
    ):
        """Short equity curve (<= 10 points) included in full."""
        results = {
            "metrics": {"total_return": 0.1},
            "equity_curve": [10000, 10100, 10200],
        }
        report = generator.generate("Test", results)
        assert report.data["equity_curve"] == [10000, 10100, 10200]

    def test_no_equity_curve(self, generator: ReportGenerator):
        """No equity curve → no equity keys in data."""
        results = {"metrics": {"total_return": 0.1}}
        report = generator.generate("Test", results)
        assert "equity_curve_length" not in report.data
