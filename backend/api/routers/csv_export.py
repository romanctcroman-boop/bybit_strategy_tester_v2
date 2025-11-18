"""
CSV Export Functionality - Quick Win #4

Provides CSV export endpoints for backtests and optimizations:
- Export backtest results with trades (Excel-compatible)
- Export optimization results with parameters and metrics
- Streaming responses for large datasets
"""

import csv
import io
from collections.abc import Generator
from datetime import datetime
from backend.utils.time import utc_now

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Backtest, Optimization, OptimizationResult, Trade

router = APIRouter(prefix="/export", tags=["csv-export"])


def generate_backtest_csv(backtest: Backtest, trades: list[Trade]) -> Generator[str]:
    """
    Generate CSV content for backtest results.
    
    Yields CSV rows with headers and trade data.
    Format: timestamp, action, symbol, price, quantity, pnl, cumulative_pnl
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write metadata header
    writer.writerow(["# Backtest Export"])
    writer.writerow(["# Backtest ID", backtest.id])
    writer.writerow(["# Strategy ID", backtest.strategy_id])
    writer.writerow(["# Symbol", backtest.symbol])
    writer.writerow(["# Timeframe", backtest.timeframe])
    writer.writerow(["# Period", f"{backtest.start_date} to {backtest.end_date}"])
    writer.writerow(["# Initial Capital", backtest.initial_capital])
    writer.writerow(["# Final Capital", backtest.final_capital or "N/A"])
    writer.writerow(["# Total Return", f"{backtest.total_return:.2f}%" if backtest.total_return else "N/A"])
    writer.writerow(["# Total Trades", backtest.total_trades or 0])
    writer.writerow(["# Win Rate", f"{backtest.win_rate:.2f}%" if backtest.win_rate else "N/A"])
    writer.writerow(["# Sharpe Ratio", f"{backtest.sharpe_ratio:.3f}" if backtest.sharpe_ratio else "N/A"])
    writer.writerow(["# Max Drawdown", f"{backtest.max_drawdown:.2f}%" if backtest.max_drawdown else "N/A"])
    writer.writerow([])  # Empty row separator
    
    # Write CSV headers for trades
    writer.writerow([
        "Entry Time",
        "Exit Time",
        "Side",
        "Entry Price",
        "Exit Price",
        "Quantity",
        "PnL (USDT)",
        "PnL (%)",
        "Cumulative PnL",
        "Run-up (USDT)",
        "Run-up (%)",
        "Drawdown (USDT)",
        "Drawdown (%)"
    ])
    
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)
    
    # Write trade rows
    for trade in trades:
        writer.writerow([
            trade.entry_time.strftime("%Y-%m-%d %H:%M:%S") if trade.entry_time else "",
            trade.exit_time.strftime("%Y-%m-%d %H:%M:%S") if trade.exit_time else "",
            trade.side,
            f"{trade.entry_price:.4f}" if trade.entry_price else "",
            f"{trade.exit_price:.4f}" if trade.exit_price else "",
            f"{trade.quantity:.6f}" if trade.quantity else "",
            f"{trade.pnl:.2f}" if trade.pnl is not None else "",
            f"{trade.pnl_pct:.2f}" if trade.pnl_pct is not None else "",
            f"{trade.cumulative_pnl:.2f}" if trade.cumulative_pnl is not None else "",
            f"{trade.run_up:.2f}" if trade.run_up is not None else "",
            f"{trade.run_up_pct:.2f}" if trade.run_up_pct is not None else "",
            f"{trade.drawdown:.2f}" if trade.drawdown is not None else "",
            f"{trade.drawdown_pct:.2f}" if trade.drawdown_pct is not None else "",
        ])
        
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


def generate_optimization_csv(
    optimization: Optimization, 
    results: list[OptimizationResult]
) -> Generator[str]:
    """
    Generate CSV content for optimization results.
    
    Yields CSV rows with headers and parameter combinations + metrics.
    Format: param1, param2, ..., metric_value, total_return, sharpe_ratio, max_drawdown
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write metadata header
    writer.writerow(["# Optimization Export"])
    writer.writerow(["# Optimization ID", optimization.id])
    writer.writerow(["# Strategy ID", optimization.strategy_id])
    writer.writerow(["# Type", optimization.optimization_type])
    writer.writerow(["# Symbol", optimization.symbol])
    writer.writerow(["# Timeframe", optimization.timeframe])
    writer.writerow(["# Metric", optimization.metric])
    writer.writerow(["# Total Combinations", optimization.total_combinations or 0])
    writer.writerow(["# Period", f"{optimization.start_date} to {optimization.end_date}"])
    writer.writerow([])  # Empty row separator
    
    # Determine parameter names from first result
    if results:
        param_names = list(results[0].parameters.keys())
        
        # Write CSV headers
        headers = param_names + ["Metric Value"]
        writer.writerow(headers)
        
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        # Write result rows
        for result in results:
            row = [result.parameters.get(param, "") for param in param_names]
            row.append(f"{result.metric_value:.4f}" if result.metric_value is not None else "")
            writer.writerow(row)
            
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
    else:
        writer.writerow(["# No results found"])
        yield output.getvalue()


@router.get("/backtests/{backtest_id}/csv")
async def export_backtest_csv(
    backtest_id: int,
    db: Session = Depends(get_db)
):
    """
    Export backtest results to CSV format.
    
    Returns a streaming CSV file with:
    - Metadata (backtest info, performance metrics)
    - Trade history (entry/exit times, prices, PnL, etc.)
    
    Compatible with Excel and Google Sheets.
    
    Args:
        backtest_id: ID of the backtest to export
        
    Returns:
        StreamingResponse with text/csv content
        
    Raises:
        404: Backtest not found
    """
    # Fetch backtest
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not backtest:
        raise HTTPException(status_code=404, detail=f"Backtest {backtest_id} not found")
    
    # Fetch trades
    trades = (
        db.query(Trade)
        .filter(Trade.backtest_id == backtest_id)
        .order_by(Trade.entry_time)
        .all()
    )
    
    # Generate filename
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    filename = f"backtest_{backtest_id}_{backtest.symbol}_{timestamp}.csv"
    
    # Return streaming response
    return StreamingResponse(
        generate_backtest_csv(backtest, trades),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/optimizations/{optimization_id}/csv")
async def export_optimization_csv(
    optimization_id: int,
    db: Session = Depends(get_db)
):
    """
    Export optimization results to CSV format.
    
    Returns a streaming CSV file with:
    - Metadata (optimization info, parameter ranges)
    - Results (parameter combinations and metric values)
    
    Sorted by metric value (best first).
    Compatible with Excel and Google Sheets.
    
    Args:
        optimization_id: ID of the optimization to export
        
    Returns:
        StreamingResponse with text/csv content
        
    Raises:
        404: Optimization not found
    """
    # Fetch optimization
    optimization = (
        db.query(Optimization)
        .filter(Optimization.id == optimization_id)
        .first()
    )
    if not optimization:
        raise HTTPException(
            status_code=404, 
            detail=f"Optimization {optimization_id} not found"
        )
    
    # Fetch results (sorted by metric value descending)
    results = (
        db.query(OptimizationResult)
        .filter(OptimizationResult.optimization_id == optimization_id)
        .order_by(OptimizationResult.metric_value.desc())
        .all()
    )
    
    # Generate filename
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    filename = f"optimization_{optimization_id}_{optimization.symbol}_{timestamp}.csv"
    
    # Return streaming response
    return StreamingResponse(
        generate_optimization_csv(optimization, results),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
