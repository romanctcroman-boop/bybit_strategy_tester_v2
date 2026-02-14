"""
Reports API Router.

Generates strategy performance reports in JSON or HTML:
- POST /generate — generate a report for a strategy backtest
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
    responses={
        400: {"description": "Invalid parameters"},
        500: {"description": "Internal server error"},
    },
)


class GenerateReportRequest(BaseModel):
    """Request to generate a strategy report."""

    strategy_name: str = Field(..., description="Strategy name")
    backtest_results: dict[str, Any] = Field(
        ...,
        description="Backtest results with 'metrics', optional 'trades', 'equity_curve'",
    )
    format: str = Field("json", description="Output format: json or html")
    strategy_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Strategy parameters",
    )
    walk_forward: dict[str, Any] = Field(
        default_factory=dict,
        description="Walk-forward validation results",
    )
    benchmarks: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Benchmark results, e.g. {'buy_hold': {'total_return': 0.15}}",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "strategy_name": "AI RSI Strategy",
                "backtest_results": {
                    "metrics": {
                        "net_profit_pct": 0.452,
                        "sharpe_ratio": 1.82,
                        "max_drawdown": 0.123,
                        "win_rate": 0.524,
                        "profit_factor": 1.67,
                        "total_trades": 245,
                    },
                    "trades": [],
                    "equity_curve": [10000, 10100, 10250],
                },
                "format": "json",
                "strategy_params": {"period": 14, "overbought": 70},
                "walk_forward": {},
                "benchmarks": {"buy_hold": {"total_return": 0.15}},
            }
        }
    }


class ReportResponse(BaseModel):
    """JSON report response."""

    success: bool
    report_id: str = ""
    strategy_name: str = ""
    generated_at: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


@router.post("/generate")
async def generate_report(request: GenerateReportRequest):
    """
    Generate a strategy performance report.

    - **format=json** returns a structured ReportResponse.
    - **format=html** returns a standalone HTML page.

    The report includes metrics summary, performance assessment (grade),
    trade summary, walk-forward results, and benchmark comparison.
    """
    try:
        from backend.agents.reporting.report_generator import (
            ReportFormat,
            ReportGenerator,
        )

        if request.format not in (ReportFormat.JSON, ReportFormat.HTML):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format: {request.format}. Must be 'json' or 'html'.",
            )

        if not request.backtest_results.get("metrics"):
            raise HTTPException(
                status_code=400,
                detail="backtest_results must contain a 'metrics' dict.",
            )

        generator = ReportGenerator()
        report = generator.generate(
            strategy_name=request.strategy_name,
            backtest_results=request.backtest_results,
            fmt=request.format,
            walk_forward=request.walk_forward or None,
            benchmarks=request.benchmarks or None,
            strategy_params=request.strategy_params or None,
        )

        if request.format == ReportFormat.HTML:
            return HTMLResponse(content=report.html_content)

        return ReportResponse(
            success=True,
            report_id=report.report_id,
            strategy_name=report.strategy_name,
            generated_at=report.generated_at,
            data=report.data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
