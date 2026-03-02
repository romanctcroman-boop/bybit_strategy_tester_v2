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
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.reports import ReportData

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])

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


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest):
    """
    Generate backtest report.

    Generates PDF and/or HTML report for a backtest.
    """
    try:
        from backend.reports import PDFGenerator, ReportGenerator

        # Mock backtest data (in production, fetch from database)
        report_data = _get_mock_backtest_data(request.backtest_id)

        # Generate report
        generator = ReportGenerator(
            include_charts=request.include_charts,
            include_trades=request.include_trades,
        )

        report_id = f"rpt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = GenerateReportResponse(
            success=True,
            report_id=report_id,
            format=request.format,
            size_bytes=0,
        )

        # Generate HTML
        if request.format in ["html", "both"]:
            html = generator.generate_html(report_data)
            _reports_cache[f"{report_id}.html"] = {
                "content": html,
                "type": "text/html",
                "size": len(html),
            }
            result.size_bytes += len(html)

        # Generate PDF
        if request.format in ["pdf", "both"]:
            pdf_gen = PDFGenerator()
            pdf_bytes = pdf_gen.generate(report_data.to_dict() if hasattr(report_data, "to_dict") else report_data)
            _reports_cache[f"{report_id}.pdf"] = {
                "content": pdf_bytes,
                "type": "application/pdf",
                "size": len(pdf_bytes),
            }
            result.size_bytes += len(pdf_bytes)

        # Send email if requested
        if request.email:
            try:
                from backend.reports import EmailSender

                email_sender = EmailSender()
                html_content = _reports_cache.get(f"{report_id}.html", {}).get("content", "")
                pdf_content = _reports_cache.get(f"{report_id}.pdf", {}).get("content")

                await email_sender.send_report(
                    recipient=request.email,
                    subject=f"Backtest Report: {report_data.strategy_name}",
                    html_body=html_content,
                    pdf_attachment=pdf_content,
                )

                result.email_sent = True
            except Exception as e:
                logger.warning(f"Email send failed: {e}")
                result.email_sent = False

        result.download_url = f"/api/v1/reports/{report_id}"

        return result

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return GenerateReportResponse(
            success=False,
            report_id="",
            format=request.format,
            size_bytes=0,
            error=str(e),
        )


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
