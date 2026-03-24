"""
📄 Reports API Router

REST API for report generation:
- POST /reports/generate - Generate report
- POST /reports/email - Email report
- GET /reports/{id} - Get report

Example request:
```json
{
  "backtest_id": "bt_123",
  "format": "pdf",
  "email": "user@example.com"
}
```
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.reports import ReportData

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reports"])

# In-memory report storage (use database in production)
_reports_cache: dict[str, dict[str, Any]] = {}


class GenerateReportRequest(BaseModel):
    """Generate report request"""

    backtest_id: str
    format: str = Field(default="pdf", description="pdf, html, or both")
    email: str | None = Field(default=None, description="Email to send report")
    include_charts: bool = Field(default=True)
    include_trades: bool = Field(default=True)


class GenerateReportResponse(BaseModel):
    """Generate report response"""

    success: bool
    report_id: str
    format: str
    size_bytes: int
    download_url: str | None = None
    email_sent: bool = False
    error: str | None = None


class EmailReportRequest(BaseModel):
    """Email report request"""

    report_id: str
    recipient: str
    subject: str | None = None


class MonitoringReportRequest(BaseModel):
    """Request body for the monitoring-style report generation endpoint.

    Accepts backtest results directly (no DB lookup needed).
    """

    strategy_name: str
    backtest_results: dict[str, Any] = Field(default_factory=dict)
    format: str = Field(default="json", description="'json' or 'html'")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    walk_forward: dict[str, Any] = Field(default_factory=dict)
    benchmarks: dict[str, Any] = Field(default_factory=dict)


def _grade_strategy(metrics: dict[str, Any]) -> str:
    """Return a letter grade for a strategy based on its key metrics."""
    score = 0.0
    sharpe = float(metrics.get("sharpe_ratio", 0))
    win_rate = float(metrics.get("win_rate", 0))
    profit_factor = float(metrics.get("profit_factor", 0))
    max_dd = abs(float(metrics.get("max_drawdown", 0)))
    net_profit_pct = float(metrics.get("net_profit_pct", 0))

    if sharpe >= 2.0:
        score += 3
    elif sharpe >= 1.5:
        score += 2
    elif sharpe >= 1.0:
        score += 1

    if win_rate >= 0.6:
        score += 2
    elif win_rate >= 0.5:
        score += 1

    if profit_factor >= 2.0:
        score += 2
    elif profit_factor >= 1.5:
        score += 1

    if max_dd < 0.10:
        score += 2
    elif max_dd < 0.20:
        score += 1

    if net_profit_pct > 0.3:
        score += 1

    if score >= 9:
        return "A+"
    if score >= 7:
        return "A"
    if score >= 5:
        return "B"
    if score >= 3:
        return "C"
    if score >= 1:
        return "D"
    return "F"


@router.post("/generate")
async def generate_report(request: MonitoringReportRequest):  # type: ignore[misc]
    """Generate a monitoring-style strategy report.

    Accepts direct backtest metrics (no DB lookup). Supports 'json' and 'html' formats.
    """
    if request.format not in ("json", "html"):
        raise HTTPException(status_code=400, detail=f"Unsupported format '{request.format}'. Use 'json' or 'html'.")

    metrics = request.backtest_results.get("metrics")
    if not metrics:
        raise HTTPException(status_code=400, detail="'backtest_results.metrics' is required.")

    grade = _grade_strategy(metrics)

    report_data: dict[str, Any] = {
        "assessment": {
            "grade": grade,
            "metrics_summary": metrics,
        },
        "trades_count": len(request.backtest_results.get("trades", [])),
    }

    if request.walk_forward:
        report_data["walk_forward"] = request.walk_forward

    if request.benchmarks:
        report_data["benchmarks"] = request.benchmarks

    if request.format == "json":
        return {
            "success": True,
            "strategy_name": request.strategy_name,
            "format": "json",
            "data": report_data,
        }

    # HTML format
    from fastapi.responses import HTMLResponse

    html_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in metrics.items())
    html = f"""<!DOCTYPE html>
<html>
<head><title>Strategy Report — {request.strategy_name}</title></head>
<body>
<h1>Strategy Report: {request.strategy_name}</h1>
<h2>Grade: {grade}</h2>
<h3>Metrics</h3>
<table border="1"><thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>{html_rows}</tbody></table>
</body>
</html>"""
    return HTMLResponse(content=html, media_type="text/html")


@router.post("/email")
async def email_report(request: EmailReportRequest):
    """Email existing report"""
    try:
        from backend.reports import EmailSender

        # Get report from cache
        pdf_key = f"{request.report_id}.pdf"
        html_key = f"{request.report_id}.html"

        if pdf_key not in _reports_cache and html_key not in _reports_cache:
            raise HTTPException(status_code=404, detail="Report not found")

        email_sender = EmailSender()

        html_content = _reports_cache.get(html_key, {}).get("content", "")
        pdf_content = _reports_cache.get(pdf_key, {}).get("content")

        success = await email_sender.send_report(
            recipient=request.recipient,
            subject=request.subject or f"Backtest Report: {request.report_id}",
            html_body=html_content,
            pdf_attachment=pdf_content,
        )

        return {
            "success": success,
            "recipient": request.recipient,
        }

    except Exception as e:
        logger.error(f"Email send failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}")
async def get_report(report_id: str, format: str = "pdf"):
    """Get report content"""
    key = f"{report_id}.{format}"

    if key not in _reports_cache:
        raise HTTPException(status_code=404, detail="Report not found")

    report = _reports_cache[key]

    return {
        "report_id": report_id,
        "format": format,
        "size_bytes": report["size"],
        "content_preview": report["content"][:500]
        if isinstance(report["content"], str)
        else f"<{len(report['content'])} bytes>",
    }


def _get_mock_backtest_data(backtest_id: str) -> ReportData:
    """Get mock backtest data (replace with database fetch)"""
    import numpy as np
    import pandas as pd

    from backend.reports import ReportData

    # Mock equity curve
    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    equity = pd.Series(np.random.randn(100).cumsum() + 100, index=dates)

    # Mock trades
    trades = [
        {
            "id": i,
            "entry_time": f"2025-01-{i % 28 + 1:02d}",
            "exit_time": f"2025-01-{i % 28 + 3:02d}",
            "side": "buy" if i % 2 == 0 else "sell",
            "entry_price": 50000 + np.random.randn() * 1000,
            "exit_price": 50000 + np.random.randn() * 1000,
            "pnl": np.random.randn() * 500,
        }
        for i in range(20)
    ]

    # Mock metrics
    metrics = {
        "total_return": np.random.uniform(0.1, 0.5),
        "annual_return": np.random.uniform(0.2, 0.6),
        "sharpe_ratio": np.random.uniform(1.0, 2.5),
        "sortino_ratio": np.random.uniform(1.5, 3.0),
        "max_drawdown": -np.random.uniform(0.1, 0.25),
        "win_rate": np.random.uniform(0.5, 0.7),
        "profit_factor": np.random.uniform(1.5, 3.0),
        "total_trades": 50,
        "volatility": np.random.uniform(0.15, 0.25),
        "avg_drawdown": -np.random.uniform(0.05, 0.1),
        "drawdown_duration": np.random.uniform(10, 30),
        "var_95": -np.random.uniform(0.02, 0.05),
        "cvar_95": -np.random.uniform(0.03, 0.07),
    }

    return ReportData(
        backtest_id=backtest_id,
        strategy_name="RSI Momentum Strategy",
        symbol="BTCUSDT",
        timeframe="1h",
        start_date="2025-01-01",
        end_date="2025-04-10",
        metrics=metrics,
        equity_curve=equity,
        trades=trades,
    )
