from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import Response

from backend.api.schemas import (
    ApiListResponse,
    BacktestClaimResponse,
    BacktestCreate,
    BacktestOut,
    BacktestResultsUpdate,
    BacktestUpdate,
    TradeOut,
)


def _get_data_service():
    try:
        from backend.services.data_service import DataService

        return DataService
    except Exception:
        return None


router = APIRouter()


@router.get("/", response_model=ApiListResponse[BacktestOut])
def list_backtests(
    strategy_id: int | None = Query(None),
    symbol: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = 100,
    offset: int = 0,
    order_by: str = "created_at",
    order_dir: str = "desc",
):
    DS = _get_data_service()
    if DS is None:
        return {"items": [], "total": 0}
    with DS() as ds:
        items = ds.get_backtests(
            strategy_id=strategy_id,
            symbol=symbol,
            status=status,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_dir=order_dir,
        )
        total = ds.count_backtests(strategy_id=strategy_id, symbol=symbol, status=status)

        def to_iso(d):
            out = d.__dict__.copy()
            for k, v in list(out.items()):
                if isinstance(v, datetime):
                    out[k] = v.isoformat()
            return out

    return {"items": [to_iso(i) for i in items], "total": total}


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.post("/", response_model=BacktestOut)
def create_backtest(payload: BacktestCreate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    # payload must contain strategy_id, symbol, timeframe, start_date, end_date, initial_capital
    with DS() as ds:
        bt = ds.create_backtest(**payload.model_dump())
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.put("/{backtest_id}", response_model=BacktestOut)
def update_backtest(backtest_id: int, payload: BacktestUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        bt = ds.update_backtest(
            backtest_id, **{k: v for k, v in payload.model_dump(exclude_none=True).items()}
        )
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.post("/{backtest_id}/claim", response_model=BacktestClaimResponse)
def claim_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    now = datetime.now(UTC)
    with DS() as ds:
        res = ds.claim_backtest_to_run(backtest_id, now)

        # Pydantic-free serialization: ensure any datetimes in nested objects are ISO strings
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

    return {k: convert(v) for k, v in res.items()}  # type: ignore


@router.post("/{backtest_id}/results", response_model=BacktestOut)
def update_results(backtest_id: int, payload: BacktestResultsUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        bt = ds.update_backtest_results(backtest_id, **payload.model_dump())
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.get("/{backtest_id}/trades", response_model=list[TradeOut])
def list_trades(
    backtest_id: int,
    side: str | None = Query(None, description="buy|sell or LONG|SHORT"),
    limit: int = 1000,
    offset: int = 0,
):
    """Return backtest trades normalized for frontend schema.

    Maps internal fields to:
      - price := entry_price
      - qty   := quantity
      - side  LONG/SHORT -> buy/sell
    """
    DS = _get_data_service()
    if DS is None:
        return []
    # Normalize side filter to internal representation if provided
    side_norm: str | None = None
    if side:
        up = side.upper()
        if up in ("LONG", "SHORT"):
            side_norm = up
        elif side.lower() in ("buy", "sell"):
            side_norm = "LONG" if side.lower() == "buy" else "SHORT"
    with DS() as ds:
        items = ds.get_trades(backtest_id=backtest_id, side=side_norm, limit=limit, offset=offset)
        out = []
        for t in items:
            d = t.__dict__.copy()
            # map fields to frontend expectations
            price = d.get("entry_price")
            qty = d.get("quantity")
            side_v = d.get("side")
            if isinstance(side_v, str):
                side_out = (
                    "buy"
                    if side_v.upper() == "LONG"
                    else "sell" if side_v.upper() == "SHORT" else side_v.lower()
                )
            else:
                side_out = "buy"
            out.append(
                {
                    "id": d.get("id"),
                    "backtest_id": d.get("backtest_id"),
                    "entry_time": d.get("entry_time").isoformat() if d.get("entry_time") else None,
                    "exit_time": d.get("exit_time").isoformat() if d.get("exit_time") else None,
                    "price": price,
                    "qty": qty,
                    "side": side_out,
                    "pnl": d.get("pnl"),
                    "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
                }
            )
    return out


# ========================================================================
# CSV EXPORT ENDPOINTS (ТЗ 4)
# ========================================================================

@router.get("/{backtest_id}/export/{report_type}")
def export_csv_report(
    backtest_id: int,
    report_type: str = Path(..., description="list_of_trades|performance|risk_ratios|trades_analysis|all")
):
    """
    Export CSV reports (ТЗ 4)
    
    Args:
        backtest_id: ID бэктеста
        report_type: Тип отчета:
            - list_of_trades: List-of-trades.csv (ТЗ 4.1)
            - performance: Performance.csv (ТЗ 4.2)
            - risk_ratios: Risk-performance-ratios.csv (ТЗ 4.3)
            - trades_analysis: Trades-analysis.csv (ТЗ 4.4)
            - all: ZIP архив со всеми отчетами
    
    Returns:
        CSV file или ZIP архив
    """
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, 
            detail="Backend database not configured in this environment"
        )
    
    with DS() as ds:
        # Получаем backtest
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        # Проверяем, что есть результаты
        if not bt.results or bt.status != 'completed':
            raise HTTPException(
                status_code=400, 
                detail="Backtest must be completed to export reports"
            )
        
        # Создаем ReportGenerator
        from backend.services.report_generator import ReportGenerator
        
        # Результаты из JSON
        results = bt.results if isinstance(bt.results, dict) else {}
        initial_capital = bt.initial_capital or 10000.0
        
        generator = ReportGenerator(results, initial_capital)
        
        # Генерируем отчет по типу
        if report_type == "list_of_trades":
            csv_content = generator.generate_list_of_trades_csv()
            filename = f"backtest_{backtest_id}_list_of_trades.csv"
            
        elif report_type == "performance":
            csv_content = generator.generate_performance_csv()
            filename = f"backtest_{backtest_id}_performance.csv"
            
        elif report_type == "risk_ratios":
            csv_content = generator.generate_risk_ratios_csv()
            filename = f"backtest_{backtest_id}_risk_ratios.csv"
            
        elif report_type == "trades_analysis":
            csv_content = generator.generate_trades_analysis_csv()
            filename = f"backtest_{backtest_id}_trades_analysis.csv"
            
        elif report_type == "all":
            # Генерируем все отчеты и создаем ZIP
            import zipfile
            import io
            
            reports = generator.generate_all_reports()
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"backtest_{backtest_id}_list_of_trades.csv", reports['list_of_trades'])
                zip_file.writestr(f"backtest_{backtest_id}_performance.csv", reports['performance'])
                zip_file.writestr(f"backtest_{backtest_id}_risk_ratios.csv", reports['risk_ratios'])
                zip_file.writestr(f"backtest_{backtest_id}_trades_analysis.csv", reports['trades_analysis'])
            
            zip_buffer.seek(0)
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=backtest_{backtest_id}_reports.zip"
                }
            )
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid report_type: {report_type}. Must be one of: list_of_trades, performance, risk_ratios, trades_analysis, all"
            )
        
        # Возвращаем CSV
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )


# ========================================================================
# CHARTS API ENDPOINTS (ТЗ 3.7.2)
# ========================================================================

@router.get("/{backtest_id}/charts/equity_curve")
def get_equity_curve_chart(
    backtest_id: int,
    show_drawdown: bool = Query(True, description="Show drawdown subplot")
):
    """
    Generate Equity Curve chart (ТЗ 3.7.2)
    
    Returns Plotly figure as JSON for PlotlyChart component
    
    Args:
        backtest_id: ID бэктеста
        show_drawdown: Показывать ли subplot с drawdown
    
    Returns:
        {"plotly_json": "<plotly_figure_json>"}
    """
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501,
            detail="Backend database not configured in this environment"
        )
    
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        if not bt.results or bt.status != 'completed':
            raise HTTPException(
                status_code=400,
                detail="Backtest must be completed to generate charts"
            )
        
        # Extract equity curve from results
        from backend.visualization.advanced_charts import create_equity_curve
        import pandas as pd
        
        results = bt.results if isinstance(bt.results, dict) else {}
        equity_data = results.get('equity', [])
        
        if not equity_data:
            raise HTTPException(
                status_code=400,
                detail="No equity data available"
            )
        
        # Convert to pandas Series
        equity_series = pd.Series(
            [point.get('equity', 0) for point in equity_data],
            index=pd.to_datetime([point.get('time') for point in equity_data])
        )
        
        # Generate chart
        fig = create_equity_curve(equity_series, show_drawdown=show_drawdown)
        
        # Return Plotly JSON
        return {"plotly_json": fig.to_json()}


@router.get("/{backtest_id}/charts/drawdown_overlay")
def get_drawdown_overlay_chart(backtest_id: int):
    """
    Generate Drawdown Overlay chart (ТЗ 3.7.2)
    
    Dual y-axis visualization: equity + drawdown
    
    Returns:
        {"plotly_json": "<plotly_figure_json>"}
    """
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501,
            detail="Backend database not configured in this environment"
        )
    
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        if not bt.results or bt.status != 'completed':
            raise HTTPException(
                status_code=400,
                detail="Backtest must be completed to generate charts"
            )
        
        from backend.visualization.advanced_charts import create_drawdown_overlay
        import pandas as pd
        
        results = bt.results if isinstance(bt.results, dict) else {}
        equity_data = results.get('equity', [])
        
        if not equity_data:
            raise HTTPException(
                status_code=400,
                detail="No equity data available"
            )
        
        equity_series = pd.Series(
            [point.get('equity', 0) for point in equity_data],
            index=pd.to_datetime([point.get('time') for point in equity_data])
        )
        
        fig = create_drawdown_overlay(equity_series)
        
        return {"plotly_json": fig.to_json()}


@router.get("/{backtest_id}/charts/pnl_distribution")
def get_pnl_distribution_chart(
    backtest_id: int,
    bins: int = Query(30, ge=10, le=100, description="Number of histogram bins")
):
    """
    Generate PnL Distribution histogram (ТЗ 3.7.2)
    
    Shows distribution of trade profits/losses with statistics
    
    Returns:
        {"plotly_json": "<plotly_figure_json>"}
    """
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501,
            detail="Backend database not configured in this environment"
        )
    
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        if not bt.results or bt.status != 'completed':
            raise HTTPException(
                status_code=400,
                detail="Backtest must be completed to generate charts"
            )
        
        from backend.visualization.advanced_charts import create_pnl_distribution
        import pandas as pd
        
        results = bt.results if isinstance(bt.results, dict) else {}
        trades = results.get('trades', [])
        
        if not trades:
            raise HTTPException(
                status_code=400,
                detail="No trades available"
            )
        
        # Convert to DataFrame
        trades_df = pd.DataFrame(trades)
        
        # Filter only completed trades (with exit_price)
        completed_trades = trades_df[trades_df['exit_price'].notna()]
        
        if len(completed_trades) == 0:
            raise HTTPException(
                status_code=400,
                detail="No completed trades available"
            )
        
        fig = create_pnl_distribution(completed_trades, bins=bins)
        
        return {"plotly_json": fig.to_json()}

