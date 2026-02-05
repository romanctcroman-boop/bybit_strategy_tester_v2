"""
Report Export API Router.

Endpoints for exporting backtest results in various formats:
- PDF reports with charts and metrics
- Excel spreadsheets with multiple sheets
- CSV files for trade data
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.services.report_export import (
    BacktestReportData,
    get_report_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/backtest/{backtest_id}/pdf")
async def export_backtest_pdf(backtest_id: str):
    """
    Export backtest results as PDF report.

    Args:
        backtest_id: ID of the backtest to export

    Returns:
        PDF file download
    """
    try:
        # Get backtest data from database
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        with SessionLocal() as db:
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            if not backtest:
                raise HTTPException(
                    status_code=404, detail=f"Backtest {backtest_id} not found"
                )

            # Build report data
            metrics = backtest.metrics or {}
            report_data = BacktestReportData(
                backtest_id=str(backtest.id),
                symbol=backtest.symbol,
                interval=backtest.interval,
                start_date=str(backtest.start_date),
                end_date=str(backtest.end_date),
                strategy_type=backtest.strategy_type,
                strategy_params=backtest.strategy_params or {},
                initial_capital=float(backtest.initial_capital),
                final_capital=float(
                    metrics.get("final_capital", backtest.initial_capital)
                ),
                total_return_pct=float(metrics.get("total_return_pct", 0)),
                total_trades=int(metrics.get("total_trades", 0)),
                winning_trades=int(metrics.get("winning_trades", 0)),
                losing_trades=int(metrics.get("losing_trades", 0)),
                win_rate=float(metrics.get("win_rate", 0)),
                profit_factor=float(metrics.get("profit_factor", 0)),
                sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
                sortino_ratio=float(metrics.get("sortino_ratio", 0)),
                max_drawdown=float(metrics.get("max_drawdown", 0)),
                avg_trade_pnl=float(metrics.get("avg_trade_pnl", 0)),
                avg_win=float(metrics.get("avg_win", 0)),
                avg_loss=float(metrics.get("avg_loss", 0)),
                largest_win=float(metrics.get("largest_win", 0)),
                largest_loss=float(metrics.get("largest_loss", 0)),
                equity_curve=backtest.equity_curve or [],
                trades=backtest.trades or [],
            )

        service = get_report_service()
        pdf_bytes = service.generate_pdf_report(report_data)

        filename = (
            f"backtest_{backtest.symbol}_{backtest.interval}_{backtest_id[:8]}.pdf"
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate PDF report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e!s}")


@router.get("/backtest/{backtest_id}/excel")
async def export_backtest_excel(backtest_id: str):
    """
    Export backtest results as Excel spreadsheet.

    Args:
        backtest_id: ID of the backtest to export

    Returns:
        Excel file download
    """
    try:
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        with SessionLocal() as db:
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            if not backtest:
                raise HTTPException(
                    status_code=404, detail=f"Backtest {backtest_id} not found"
                )

            metrics = backtest.metrics or {}
            report_data = BacktestReportData(
                backtest_id=str(backtest.id),
                symbol=backtest.symbol,
                interval=backtest.interval,
                start_date=str(backtest.start_date),
                end_date=str(backtest.end_date),
                strategy_type=backtest.strategy_type,
                strategy_params=backtest.strategy_params or {},
                initial_capital=float(backtest.initial_capital),
                final_capital=float(
                    metrics.get("final_capital", backtest.initial_capital)
                ),
                total_return_pct=float(metrics.get("total_return_pct", 0)),
                total_trades=int(metrics.get("total_trades", 0)),
                winning_trades=int(metrics.get("winning_trades", 0)),
                losing_trades=int(metrics.get("losing_trades", 0)),
                win_rate=float(metrics.get("win_rate", 0)),
                profit_factor=float(metrics.get("profit_factor", 0)),
                sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
                sortino_ratio=float(metrics.get("sortino_ratio", 0)),
                max_drawdown=float(metrics.get("max_drawdown", 0)),
                avg_trade_pnl=float(metrics.get("avg_trade_pnl", 0)),
                avg_win=float(metrics.get("avg_win", 0)),
                avg_loss=float(metrics.get("avg_loss", 0)),
                largest_win=float(metrics.get("largest_win", 0)),
                largest_loss=float(metrics.get("largest_loss", 0)),
                equity_curve=backtest.equity_curve or [],
                trades=backtest.trades or [],
            )

        service = get_report_service()
        excel_bytes = service.generate_excel_report(report_data)

        filename = (
            f"backtest_{backtest.symbol}_{backtest.interval}_{backtest_id[:8]}.xlsx"
        )
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate Excel report: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate Excel: {e!s}"
        )


@router.get("/backtest/{backtest_id}/csv")
async def export_backtest_csv(backtest_id: str):
    """
    Export backtest trades as CSV file.

    Args:
        backtest_id: ID of the backtest to export

    Returns:
        CSV file download
    """
    try:
        from backend.database import SessionLocal
        from backend.database.models import Backtest

        with SessionLocal() as db:
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            if not backtest:
                raise HTTPException(
                    status_code=404, detail=f"Backtest {backtest_id} not found"
                )

            metrics = backtest.metrics or {}
            report_data = BacktestReportData(
                backtest_id=str(backtest.id),
                symbol=backtest.symbol,
                interval=backtest.interval,
                start_date=str(backtest.start_date),
                end_date=str(backtest.end_date),
                strategy_type=backtest.strategy_type,
                strategy_params=backtest.strategy_params or {},
                initial_capital=float(backtest.initial_capital),
                final_capital=float(
                    metrics.get("final_capital", backtest.initial_capital)
                ),
                total_return_pct=float(metrics.get("total_return_pct", 0)),
                total_trades=int(metrics.get("total_trades", 0)),
                winning_trades=int(metrics.get("winning_trades", 0)),
                losing_trades=int(metrics.get("losing_trades", 0)),
                win_rate=float(metrics.get("win_rate", 0)),
                profit_factor=float(metrics.get("profit_factor", 0)),
                sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
                sortino_ratio=float(metrics.get("sortino_ratio", 0)),
                max_drawdown=float(metrics.get("max_drawdown", 0)),
                avg_trade_pnl=float(metrics.get("avg_trade_pnl", 0)),
                avg_win=float(metrics.get("avg_win", 0)),
                avg_loss=float(metrics.get("avg_loss", 0)),
                largest_win=float(metrics.get("largest_win", 0)),
                largest_loss=float(metrics.get("largest_loss", 0)),
                equity_curve=backtest.equity_curve or [],
                trades=backtest.trades or [],
            )

        service = get_report_service()
        csv_bytes = service.generate_csv_report(report_data)

        filename = f"trades_{backtest.symbol}_{backtest.interval}_{backtest_id[:8]}.csv"
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {e!s}")


@router.get("/formats")
async def get_available_formats():
    """Get available export formats and their requirements."""
    service = get_report_service()
    deps = service._check_dependencies()

    return {
        "formats": [
            {
                "name": "PDF",
                "extension": ".pdf",
                "available": deps.get("reportlab", False),
                "description": "Professional PDF report with metrics, charts, and trade list",
                "requirements": "reportlab" if not deps.get("reportlab") else None,
            },
            {
                "name": "Excel",
                "extension": ".xlsx",
                "available": deps.get("xlsxwriter", False)
                or deps.get("openpyxl", False),
                "description": "Excel spreadsheet with multiple sheets for analysis",
                "requirements": "xlsxwriter or openpyxl"
                if not (deps.get("xlsxwriter") or deps.get("openpyxl"))
                else None,
            },
            {
                "name": "CSV",
                "extension": ".csv",
                "available": True,
                "description": "CSV file with trade data for external analysis",
                "requirements": None,
            },
        ],
        "dependencies": deps,
    }
