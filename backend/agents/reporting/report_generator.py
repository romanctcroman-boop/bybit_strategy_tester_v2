"""
Report Generator for AI Trading Strategies.

Per spec section 4.3 / 5.2 (step 9): generates comprehensive reports
comparing strategy backtest results with benchmarks.

Supported formats:
- JSON: structured data for API consumers
- HTML: styled standalone report for viewing/sharing

Features:
- Performance metrics summary
- Equity curve data
- Trade-level details
- Benchmark comparison (buy & hold, simple MA)
- Walk-forward validation results
- Strategy quality assessment
"""

from __future__ import annotations

import html as html_lib
from datetime import UTC, datetime
from typing import Any

from loguru import logger

__all__ = [
    "ReportFormat",
    "ReportGenerator",
    "StrategyReport",
]


class ReportFormat:
    """Supported report output formats."""

    JSON = "json"
    HTML = "html"


class StrategyReport:
    """
    Encapsulates a generated strategy report.

    Attributes:
        report_id: Unique report identifier.
        format: Output format (json / html).
        strategy_name: Name of the strategy.
        generated_at: Timestamp of report generation.
        data: Structured report data (always populated).
        html_content: Rendered HTML string (only for HTML format).
    """

    def __init__(
        self,
        report_id: str,
        fmt: str,
        strategy_name: str,
        data: dict[str, Any],
        html_content: str = "",
    ) -> None:
        self.report_id = report_id
        self.format = fmt
        self.strategy_name = strategy_name
        self.generated_at = datetime.now(UTC).isoformat()
        self.data = data
        self.html_content = html_content

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "report_id": self.report_id,
            "format": self.format,
            "strategy_name": self.strategy_name,
            "generated_at": self.generated_at,
            "data": self.data,
        }
        if self.html_content:
            result["html_content"] = self.html_content
        return result


class ReportGenerator:
    """
    Generates strategy performance reports.

    Accepts backtest results, optional walk-forward data,
    and benchmark comparisons. Outputs JSON or HTML.
    """

    # Metrics to highlight in report summary
    KEY_METRICS: list[str] = [
        "net_profit",
        "net_profit_pct",
        "total_return",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "total_trades",
        "total_closed_trades",
        "avg_trade_pnl",
        "largest_winning_trade",
        "largest_losing_trade",
        "avg_winning_trade",
        "avg_losing_trade",
        "max_consecutive_wins",
        "max_consecutive_losses",
        "recovery_factor",
    ]

    def generate(
        self,
        strategy_name: str,
        backtest_results: dict[str, Any],
        fmt: str = ReportFormat.JSON,
        walk_forward: dict[str, Any] | None = None,
        benchmarks: dict[str, dict[str, Any]] | None = None,
        strategy_params: dict[str, Any] | None = None,
        report_id: str = "",
    ) -> StrategyReport:
        """
        Generate a strategy report.

        Args:
            strategy_name: Name of the strategy.
            backtest_results: Dict with 'metrics', optionally 'trades', 'equity_curve'.
            fmt: Output format ('json' or 'html').
            walk_forward: Optional walk-forward validation results.
            benchmarks: Optional benchmark comparison results.
                e.g. {"buy_hold": {"total_return": 0.15, ...}}
            strategy_params: Optional strategy parameters.
            report_id: Optional custom report ID.

        Returns:
            StrategyReport with data and optional HTML content.
        """
        if not report_id:
            import uuid

            report_id = str(uuid.uuid4())[:12]

        logger.info(f"Generating {fmt} report: {strategy_name} (id={report_id})")

        # Build structured data
        data = self._build_report_data(
            strategy_name=strategy_name,
            backtest_results=backtest_results,
            walk_forward=walk_forward,
            benchmarks=benchmarks,
            strategy_params=strategy_params,
        )

        html_content = ""
        if fmt == ReportFormat.HTML:
            html_content = self._render_html(data, strategy_name, report_id)

        return StrategyReport(
            report_id=report_id,
            fmt=fmt,
            strategy_name=strategy_name,
            data=data,
            html_content=html_content,
        )

    def _build_report_data(
        self,
        strategy_name: str,
        backtest_results: dict[str, Any],
        walk_forward: dict[str, Any] | None,
        benchmarks: dict[str, dict[str, Any]] | None,
        strategy_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the structured report data."""
        metrics = backtest_results.get("metrics", {})
        trades = backtest_results.get("trades", [])
        equity_curve = backtest_results.get("equity_curve", [])

        # Extract key metrics
        key_metrics: dict[str, Any] = {}
        for key in self.KEY_METRICS:
            if key in metrics:
                key_metrics[key] = metrics[key]

        # Performance assessment
        assessment = self._assess_performance(metrics)

        # Trade analysis
        trade_summary = self._summarize_trades(trades)

        data: dict[str, Any] = {
            "strategy_name": strategy_name,
            "generated_at": datetime.now(UTC).isoformat(),
            "metrics": key_metrics,
            "all_metrics": metrics,
            "assessment": assessment,
            "trade_summary": trade_summary,
            "total_trades_count": len(trades),
        }

        if strategy_params:
            data["strategy_params"] = strategy_params

        if equity_curve:
            data["equity_curve_length"] = len(equity_curve)
            # Include first/last few points for summary
            if len(equity_curve) > 10:
                data["equity_start"] = equity_curve[:3]
                data["equity_end"] = equity_curve[-3:]
            else:
                data["equity_curve"] = equity_curve

        if walk_forward:
            data["walk_forward"] = {
                "consistency_ratio": walk_forward.get("consistency_ratio", 0),
                "overfit_score": walk_forward.get("overfit_score", 0),
                "parameter_stability": walk_forward.get("parameter_stability", 0),
                "confidence_level": walk_forward.get("confidence_level", ""),
            }

        if benchmarks:
            data["benchmarks"] = benchmarks

        return data

    def _assess_performance(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Assess strategy quality based on metrics thresholds."""
        thresholds = {
            "sharpe_ratio": {"min": 1.0, "good": 1.5, "excellent": 2.0},
            "max_drawdown": {"max": 0.15, "good": 0.10, "excellent": 0.05},
            "win_rate": {"min": 0.45, "good": 0.55, "excellent": 0.65},
            "profit_factor": {"min": 1.2, "good": 1.5, "excellent": 2.0},
            "calmar_ratio": {"min": 1.0, "good": 2.0, "excellent": 3.0},
        }

        strengths: list[str] = []
        weaknesses: list[str] = []
        scores: list[float] = []

        for metric_name, thresh in thresholds.items():
            value = metrics.get(metric_name)
            if value is None:
                continue

            value = float(value)

            if "max" in thresh:
                # Lower is better (drawdown)
                if value <= thresh["excellent"]:
                    level, score = "excellent", 1.0
                elif value <= thresh["good"]:
                    level, score = "good", 0.7
                elif value <= thresh["max"]:
                    level, score = "acceptable", 0.4
                else:
                    level, score = "poor", 0.1
                if level == "poor":
                    weaknesses.append(f"{metric_name}: {value:.2%}")
                elif level == "excellent":
                    strengths.append(f"{metric_name}: {value:.2%}")
            else:
                # Higher is better
                if value >= thresh["excellent"]:
                    level, score = "excellent", 1.0
                elif value >= thresh["good"]:
                    level, score = "good", 0.7
                elif value >= thresh["min"]:
                    level, score = "acceptable", 0.4
                else:
                    level, score = "poor", 0.1
                if level == "poor":
                    weaknesses.append(f"{metric_name}: {value:.2f}")
                elif level == "excellent":
                    strengths.append(f"{metric_name}: {value:.2f}")

            scores.append(score)

        overall = sum(scores) / len(scores) if scores else 0.0

        return {
            "overall_score": round(overall, 3),
            "grade": self._score_to_grade(overall),
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 0.9:
            return "A+"
        if score >= 0.8:
            return "A"
        if score >= 0.7:
            return "B"
        if score >= 0.55:
            return "C"
        if score >= 0.4:
            return "D"
        return "F"

    def _summarize_trades(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize trade-level data."""
        if not trades:
            return {"count": 0}

        pnls = [t.get("pnl", 0) for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        return {
            "count": len(trades),
            "winners": len(winners),
            "losers": len(losers),
            "breakeven": len(pnls) - len(winners) - len(losers),
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
        }

    def _render_html(
        self,
        data: dict[str, Any],
        strategy_name: str,
        report_id: str,
    ) -> str:
        """Render a standalone HTML report."""
        assessment = data.get("assessment", {})
        metrics = data.get("metrics", {})
        trade_summary = data.get("trade_summary", {})
        benchmarks = data.get("benchmarks", {})
        walk_forward = data.get("walk_forward", {})
        params = data.get("strategy_params", {})

        grade = assessment.get("grade", "N/A")
        overall = assessment.get("overall_score", 0)
        strengths = assessment.get("strengths", [])
        weaknesses = assessment.get("weaknesses", [])

        # Build metrics rows
        metrics_rows = ""
        for key, val in metrics.items():
            formatted = self._format_metric_value(key, val)
            metrics_rows += f"<tr><td>{html_lib.escape(key)}</td><td>{formatted}</td></tr>\n"

        # Build benchmark rows
        benchmark_html = ""
        if benchmarks:
            benchmark_rows = ""
            for bname, bmetrics in benchmarks.items():
                for bkey, bval in bmetrics.items():
                    formatted = self._format_metric_value(bkey, bval)
                    benchmark_rows += (
                        f"<tr><td>{html_lib.escape(bname)}</td>"
                        f"<td>{html_lib.escape(bkey)}</td>"
                        f"<td>{formatted}</td></tr>\n"
                    )
            benchmark_html = f"""
            <h2>Benchmark Comparison</h2>
            <table>
                <thead><tr><th>Benchmark</th><th>Metric</th><th>Value</th></tr></thead>
                <tbody>{benchmark_rows}</tbody>
            </table>
            """

        # Walk-forward section
        wf_html = ""
        if walk_forward:
            wf_html = f"""
            <h2>Walk-Forward Validation</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-label">Consistency</div>
                    <div class="metric-val">{self._format_metric_value("consistency_ratio", walk_forward.get("consistency_ratio", 0))}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Overfit Score</div>
                    <div class="metric-val">{walk_forward.get("overfit_score", 0):.3f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Param Stability</div>
                    <div class="metric-val">{self._format_metric_value("parameter_stability", walk_forward.get("parameter_stability", 0))}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Confidence</div>
                    <div class="metric-val">{html_lib.escape(str(walk_forward.get("confidence_level", "N/A")))}</div>
                </div>
            </div>
            """

        # Params section
        params_html = ""
        if params:
            params_items = "".join(
                f"<li><strong>{html_lib.escape(str(k))}</strong>: {html_lib.escape(str(v))}</li>"
                for k, v in params.items()
            )
            params_html = f"<h2>Strategy Parameters</h2><ul>{params_items}</ul>"

        # Trade summary
        trades_html = ""
        if trade_summary.get("count", 0) > 0:
            ts = trade_summary
            trades_html = f"""
            <h2>Trade Summary</h2>
            <div class="metrics-grid">
                <div class="metric-box"><div class="metric-label">Total</div><div class="metric-val">{ts["count"]}</div></div>
                <div class="metric-box"><div class="metric-label">Winners</div><div class="metric-val win">{ts["winners"]}</div></div>
                <div class="metric-box"><div class="metric-label">Losers</div><div class="metric-val lose">{ts["losers"]}</div></div>
                <div class="metric-box"><div class="metric-label">Total PnL</div><div class="metric-val">${ts["total_pnl"]:.2f}</div></div>
                <div class="metric-box"><div class="metric-label">Avg PnL</div><div class="metric-val">${ts["avg_pnl"]:.2f}</div></div>
                <div class="metric-box"><div class="metric-label">Best Trade</div><div class="metric-val win">${ts["best_trade"]:.2f}</div></div>
                <div class="metric-box"><div class="metric-label">Worst Trade</div><div class="metric-val lose">${ts["worst_trade"]:.2f}</div></div>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Report - {html_lib.escape(strategy_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #f0f6fc; padding: 24px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  h2 {{ font-size: 1.15rem; margin: 24px 0 12px; color: #58a6ff; }}
  .subtitle {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 24px; }}
  .grade-badge {{ display: inline-block; background: #161b22; border: 2px solid #58a6ff;
                  border-radius: 12px; padding: 8px 20px; font-size: 1.3rem; font-weight: 700;
                  color: #58a6ff; margin: 12px 0; }}
  .score {{ font-size: 0.9rem; color: #8b949e; margin-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }}
  th {{ color: #8b949e; font-size: 0.8rem; text-transform: uppercase; }}
  td {{ font-size: 0.9rem; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }}
  .metric-box {{ background: #161b22; border-radius: 8px; padding: 12px; text-align: center; }}
  .metric-label {{ font-size: 0.75rem; color: #8b949e; text-transform: uppercase; }}
  .metric-val {{ font-size: 1.2rem; font-weight: 700; margin-top: 4px; }}
  .metric-val.win {{ color: #3fb950; }}
  .metric-val.lose {{ color: #f85149; }}
  ul {{ list-style: none; padding: 0; }}
  ul li {{ padding: 4px 0; font-size: 0.9rem; }}
  .strengths li::before {{ content: "\\2705 "; }}
  .weaknesses li::before {{ content: "\\274C "; }}
  .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d;
             font-size: 0.8rem; color: #6e7681; }}
</style>
</head>
<body>
<div class="container">
  <h1>Strategy Report: {html_lib.escape(strategy_name)}</h1>
  <p class="subtitle">Report ID: {html_lib.escape(report_id)} | Generated: {data.get("generated_at", "")}</p>

  <div class="grade-badge">{html_lib.escape(grade)}<span class="score">({overall:.1%})</span></div>

  {params_html}

  <h2>Performance Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>{metrics_rows}</tbody>
  </table>

  {trades_html}

  <h2>Strengths</h2>
  <ul class="strengths">{"".join(f"<li>{html_lib.escape(s)}</li>" for s in strengths) or "<li>None identified</li>"}</ul>

  <h2>Weaknesses</h2>
  <ul class="weaknesses">{"".join(f"<li>{html_lib.escape(w)}</li>" for w in weaknesses) or "<li>None identified</li>"}</ul>

  {wf_html}
  {benchmark_html}

  <div class="footer">
    Bybit Strategy Tester v2 — AI Pipeline Report Generator<br>
    Commission: 0.07% | Engine: FallbackEngineV4
  </div>
</div>
</body>
</html>"""

    @staticmethod
    def _format_metric_value(key: str, value: Any) -> str:
        """Format a metric value for display."""
        if value is None:
            return "N/A"
        try:
            val = float(value)
        except (ValueError, TypeError):
            return html_lib.escape(str(value))

        # Percentage metrics
        pct_keys = {
            "net_profit_pct",
            "total_return",
            "max_drawdown",
            "win_rate",
            "consistency_ratio",
            "parameter_stability",
        }
        if key in pct_keys:
            return f"{val:.2%}"

        # Integer metrics
        int_keys = {
            "total_trades",
            "total_closed_trades",
            "max_consecutive_wins",
            "max_consecutive_losses",
        }
        if key in int_keys:
            return str(int(val))

        # Dollar metrics
        dollar_keys = {"net_profit", "avg_trade_pnl", "largest_winning_trade", "largest_losing_trade"}
        if key in dollar_keys:
            return f"${val:,.2f}"

        return f"{val:.4f}"
