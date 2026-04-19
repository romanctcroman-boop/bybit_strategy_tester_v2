"""
📄 Report Generator

Main report generator class.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ReportData:
    """Data for report generation"""

    backtest_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    metrics: dict[str, float]
    equity_curve: pd.Series
    trades: list[dict[str, Any]]
    monthly_returns: pd.DataFrame | None = None
    optimization_results: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ReportGenerator:
    """
    Generate professional reports for backtest results.

    Generates:
    - HTML reports
    - PDF reports
    - Email reports

    Example:
    ```python
    generator = ReportGenerator()

    html = generator.generate_html(report_data)
    pdf = generator.generate_pdf(report_data)
    await generator.send_email(report_data, recipient='user@example.com')
    ```
    """

    def __init__(
        self,
        template_dir: str = "backend/reports/templates",
        include_charts: bool = True,
        include_trades: bool = True,
    ):
        """
        Args:
            template_dir: Directory with HTML templates
            include_charts: Include charts in report
            include_trades: Include trades table
        """
        self.template_dir = template_dir
        self.include_charts = include_charts
        self.include_trades = include_trades

        # Metrics categories
        self.metrics_categories = {
            "Performance": [
                "total_return",
                "annual_return",
                "sharpe_ratio",
                "sortino_ratio",
                "calmar_ratio",
                "profit_factor",
            ],
            "Risk": ["volatility", "max_drawdown", "avg_drawdown", "drawdown_duration", "var_95", "cvar_95"],
            "Trades": [
                "total_trades",
                "winning_trades",
                "losing_trades",
                "win_rate",
                "avg_win",
                "avg_loss",
                "profit_factor",
            ],
            "Timing": ["avg_trade_duration", "avg_bars_in_trade", "market_exposure", "turnover"],
        }

    def generate_html(self, data: ReportData, template: str = "backtest_report.html") -> str:
        """
        Generate HTML report.

        Args:
            data: Report data
            template: Template file name

        Returns:
            HTML string
        """
        try:
            from jinja2 import Environment, FileSystemLoader

            # Setup Jinja2
            env = Environment(loader=FileSystemLoader(self.template_dir), autoescape=True)

            # Load template
            tpl = env.get_template(template)

            # Prepare context
            context = self._prepare_context(data)

            # Render
            html = tpl.render(**context)

            logger.info(f"Generated HTML report for {data.backtest_id}")

            return html

        except Exception as e:
            logger.error(f"HTML generation failed: {e}")
            return self._generate_simple_html(data)

    def _prepare_context(self, data: ReportData) -> dict[str, Any]:
        """Prepare template context"""
        # Categorize metrics
        categorized_metrics = {}

        for category, metric_names in self.metrics_categories.items():
            categorized_metrics[category] = {name: data.metrics.get(name, 0) for name in metric_names}

        # Format dates
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Summary stats
        total_return = data.metrics.get("total_return", 0)
        sharpe = data.metrics.get("sharpe_ratio", 0)
        max_dd = data.metrics.get("max_drawdown", 0)
        win_rate = data.metrics.get("win_rate", 0)

        return {
            "backtest_id": data.backtest_id,
            "strategy_name": data.strategy_name,
            "symbol": data.symbol,
            "timeframe": data.timeframe,
            "start_date": data.start_date,
            "end_date": data.end_date,
            "generated_at": generated_at,
            "metrics": data.metrics,
            "categorized_metrics": categorized_metrics,
            "equity_curve": data.equity_curve,
            "trades": data.trades[:50] if self.include_trades else [],  # Limit trades
            "monthly_returns": data.monthly_returns,
            "optimization_results": data.optimization_results,
            "summary": {
                "total_return": total_return,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "win_rate": win_rate,
            },
            "include_charts": self.include_charts,
            "include_trades": self.include_trades,
        }

    def _generate_simple_html(self, data: ReportData) -> str:
        """Generate simple HTML if template fails"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report - {data.strategy_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
                .metric {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #f5f5f5; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Backtest Report</h1>
            <p><strong>Strategy:</strong> {data.strategy_name}</p>
            <p><strong>Symbol:</strong> {data.symbol} | <strong>Timeframe:</strong> {data.timeframe}</p>
            <p><strong>Period:</strong> {data.start_date} to {data.end_date}</p>

            <h2>Performance Metrics</h2>
            <div class="metrics">
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("total_return", 0):.2%}</div>
                    <div class="metric-label">Total Return</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("sharpe_ratio", 0):.2f}</div>
                    <div class="metric-label">Sharpe Ratio</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("max_drawdown", 0):.2%}</div>
                    <div class="metric-label">Max Drawdown</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("win_rate", 0):.1%}</div>
                    <div class="metric-label">Win Rate</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("total_trades", 0)}</div>
                    <div class="metric-label">Total Trades</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data.metrics.get("profit_factor", 0):.2f}</div>
                    <div class="metric-label">Profit Factor</div>
                </div>
            </div>

            <h2>Trade History</h2>
            <table>
                <tr>
                    <th>#</th>
                    <th>Date</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>PnL</th>
                </tr>
                {
            "".join(
                f'''
                <tr>
                    <td>{i + 1}</td>
                    <td>{trade.get("exit_time", "N/A")}</td>
                    <td>{trade.get("side", "N/A")}</td>
                    <td>{trade.get("entry_price", 0):.2f}</td>
                    <td>{trade.get("exit_price", 0):.2f}</td>
                    <td class="{"positive" if trade.get("pnl", 0) > 0 else "negative"}">{trade.get("pnl", 0):.2f}</td>
                </tr>
                '''
                for i, trade in enumerate(data.trades[:20])
            )
        }
            </table>

            <p style="margin-top: 40px; color: #666; font-size: 12px;">
                Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </body>
        </html>
        """
        return html

    def generate_summary(self, data: ReportData) -> dict[str, Any]:
        """
        Generate report summary.

        Args:
            data: Report data

        Returns:
            Summary dictionary
        """
        total_return = data.metrics.get("total_return", 0)
        sharpe = data.metrics.get("sharpe_ratio", 0)
        sortino = data.metrics.get("sortino_ratio", 0)
        max_dd = data.metrics.get("max_drawdown", 0)
        win_rate = data.metrics.get("win_rate", 0)

        # Grade
        if sharpe >= 2.0:
            grade = "A+"
        elif sharpe >= 1.5:
            grade = "A"
        elif sharpe >= 1.0:
            grade = "B"
        elif sharpe >= 0.5:
            grade = "C"
        else:
            grade = "D"

        return {
            "grade": grade,
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "total_trades": data.metrics.get("total_trades", 0),
            "profit_factor": data.metrics.get("profit_factor", 0),
            "recommendation": self._get_recommendation(sharpe, max_dd, win_rate),
        }

    def _get_recommendation(self, sharpe: float, max_dd: float, win_rate: float) -> str:
        """Get recommendation based on metrics"""
        if sharpe >= 2.0 and abs(max_dd) < 0.15:
            return "Excellent strategy - Ready for live trading"
        elif sharpe >= 1.5 and abs(max_dd) < 0.25:
            return "Good strategy - Consider minor optimizations"
        elif sharpe >= 1.0:
            return "Average strategy - Further optimization recommended"
        else:
            return "Poor performance - Significant improvements needed"

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "template_dir": self.template_dir,
            "include_charts": self.include_charts,
            "include_trades": self.include_trades,
            "metrics_categories": list(self.metrics_categories.keys()),
        }
