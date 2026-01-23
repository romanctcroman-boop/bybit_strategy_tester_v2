"""Full emulation of list_backtests with detailed logging"""
import traceback
from datetime import datetime, timezone

from backend.database import SessionLocal
from backend.database.models import Backtest as BacktestModel
from backend.database.models import BacktestStatus as DBBacktestStatus
from backend.backtesting.models import (
    BacktestConfig, PerformanceMetrics, EquityCurve, 
    BacktestResult, BacktestStatus, BacktestListResponse
)
from backend.backtesting.service import get_backtest_service

db = SessionLocal()

try:
    print("Step 1: Get memory results")
    service = get_backtest_service()
    memory_results = service.list_results(limit=1000)
    memory_ids = {r.id for r in memory_results}
    print(f"  Memory: {len(memory_results)}")
    
    print("\nStep 2: Get DB backtests")
    db.expire_all()
    db_backtests = (
        db.query(BacktestModel)
        .order_by(BacktestModel.created_at.desc())
        .limit(1000)
        .all()
    )
    print(f"  DB: {len(db_backtests)}")
    
    print("\nStep 3: Convert each backtest")
    db_results = []
    
    for i, bt in enumerate(db_backtests):
        if bt.id in memory_ids:
            continue
            
        try:
            # Date parsing
            start_dt = bt.start_date
            end_dt = bt.end_date
            if isinstance(start_dt, str):
                start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            if isinstance(end_dt, str):
                end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
            if start_dt and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            config = BacktestConfig(
                symbol=bt.symbol or "BTCUSDT",
                interval=bt.timeframe or "30",
                start_date=start_dt or datetime.now(timezone.utc),
                end_date=end_dt or datetime.now(timezone.utc),
                initial_capital=bt.initial_capital or 10000.0,
                strategy_type=bt.strategy_type or "rsi",
                strategy_params=bt.parameters.get("strategy_params", {}) if bt.parameters else {},
            )

            opt_metrics = bt.parameters.get("optimization_metrics", {}) if bt.parameters else {}
            net_profit = (bt.final_capital - bt.initial_capital) if bt.final_capital and bt.initial_capital else 0
            
            # Simplified metrics (key fields only)
            metrics = PerformanceMetrics(
                net_profit=opt_metrics.get("net_profit", net_profit),
                net_profit_pct=opt_metrics.get("net_profit_pct", bt.total_return or 0),
                total_return=bt.total_return or 0,
                annual_return=bt.annual_return or opt_metrics.get("annual_return", 0),
                sharpe_ratio=bt.sharpe_ratio or 0,
                sortino_ratio=bt.sortino_ratio or 0,
                calmar_ratio=opt_metrics.get("calmar_ratio", 0),
                max_drawdown=bt.max_drawdown or 0,
                max_drawdown_value=opt_metrics.get("max_drawdown_value", 0),
                avg_drawdown=opt_metrics.get("avg_drawdown", 0),
                avg_drawdown_value=opt_metrics.get("avg_drawdown_value", 0),
                max_drawdown_duration_days=opt_metrics.get("max_drawdown_duration_days", 0),
                total_trades=bt.total_trades or opt_metrics.get("total_trades", 0),
                winning_trades=bt.winning_trades or opt_metrics.get("winning_trades", 0),
                losing_trades=bt.losing_trades or opt_metrics.get("losing_trades", 0),
                win_rate=bt.win_rate or 0,
                profit_factor=bt.profit_factor or 0,
                avg_win=opt_metrics.get("avg_win", 0),
                avg_loss=opt_metrics.get("avg_loss", 0),
                avg_win_value=opt_metrics.get("avg_win", 0),
                avg_loss_value=opt_metrics.get("avg_loss", 0),
                exposure_time=bt.exposure_time if bt.exposure_time is not None else opt_metrics.get("exposure_time", 0),
                avg_trade_duration_hours=opt_metrics.get("avg_trade_duration_hours", 0),
            )

            # CRITICAL: trades_data and equity_curve_data
            trades_data = bt.trades if bt.trades else []
            
            equity_curve_data = None
            if bt.equity_curve:
                raw_ec = bt.equity_curve
                if isinstance(raw_ec, dict) and "timestamps" in raw_ec:
                    equity_curve_data = EquityCurve(**raw_ec)
                elif isinstance(raw_ec, list) and len(raw_ec) > 0:
                    # Convert from list format
                    timestamps = []
                    equity = []
                    drawdown = []
                    returns_list = []
                    for point in raw_ec:
                        ts = point.get("timestamp", 0)
                        if isinstance(ts, (int, float)):
                            ts = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                        elif isinstance(ts, str):
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        timestamps.append(ts)
                        equity.append(point.get("equity", 0))
                        drawdown.append(point.get("drawdown", 0))
                        returns_list.append(point.get("returns", 0))
                    equity_curve_data = EquityCurve(
                        timestamps=timestamps,
                        equity=equity,
                        drawdown=drawdown,
                        returns=returns_list if any(returns_list) else [],
                    )

            result = BacktestResult(
                id=bt.id,
                status=BacktestStatus.COMPLETED if bt.status == DBBacktestStatus.COMPLETED else BacktestStatus.FAILED,
                created_at=bt.created_at or datetime.now(timezone.utc),
                config=config,
                metrics=metrics,
                trades=trades_data,
                equity_curve=equity_curve_data,
                final_equity=bt.final_capital,
                final_pnl=net_profit,
                final_pnl_pct=bt.total_return or 0,
            )
            db_results.append(result)
            
        except Exception as e:
            print(f"  ERROR at backtest {i} ({bt.id[:8]}...): {e}")
            traceback.print_exc()
            continue
    
    print(f"  Converted: {len(db_results)}")
    
    print("\nStep 4: Combine and sort")
    all_results = memory_results + db_results
    all_results.sort(key=lambda x: x.created_at, reverse=True)
    print(f"  Total: {len(all_results)}")
    
    print("\nStep 5: Build response")
    page = 1
    limit = 20
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    items = all_results[start_idx:end_idx]
    
    response = BacktestListResponse(
        total=len(all_results),
        items=items,
        page=page,
        page_size=limit,
    )
    print(f"  Response OK: {len(items)} items")
    
    print("\n=== SUCCESS ===")
    
except Exception as e:
    print(f"\n=== FAILED ===")
    print(f"Error: {e}")
    traceback.print_exc()
finally:
    db.close()
