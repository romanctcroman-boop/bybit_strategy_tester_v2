"""Debug script for list_backtests endpoint"""
import traceback
from datetime import datetime, timezone

from backend.database import SessionLocal
from backend.database.models import Backtest as BacktestModel
from backend.backtesting.models import BacktestConfig, PerformanceMetrics, EquityCurve, BacktestResult, BacktestStatus

db = SessionLocal()

try:
    backtests = db.query(BacktestModel).order_by(BacktestModel.created_at.desc()).limit(100).all()
    print(f"Found {len(backtests)} backtests in DB")
    
    for i, bt in enumerate(backtests):
        print(f"\n=== Backtest {i+1}: {bt.id[:8]}... ===")
        print(f"  strategy_type: {bt.strategy_type}, symbol: {bt.symbol}")
        
        try:
            # Step 1: Parse dates
            start_dt = bt.start_date
            end_dt = bt.end_date
            if start_dt and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            print("  [OK] Dates parsed")
            
            # Step 2: Create BacktestConfig
            config = BacktestConfig(
                symbol=bt.symbol or "BTCUSDT",
                interval=bt.timeframe or "30",
                start_date=start_dt or datetime.now(timezone.utc),
                end_date=end_dt or datetime.now(timezone.utc),
                initial_capital=bt.initial_capital or 10000.0,
                strategy_type=bt.strategy_type or "rsi",
                strategy_params=bt.parameters.get("strategy_params", {}) if bt.parameters else {},
            )
            print("  [OK] Config created")
            
            # Step 3: Get optimization metrics
            opt_metrics = bt.parameters.get("optimization_metrics", {}) if bt.parameters else {}
            
            # Step 4: Create PerformanceMetrics
            net_profit = (bt.final_capital - bt.initial_capital) if bt.final_capital and bt.initial_capital else 0
            
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
            print("  [OK] Metrics created")
            
            # Step 5: Create BacktestResult
            result = BacktestResult(
                id=bt.id,
                status=BacktestStatus.COMPLETED,
                created_at=bt.created_at or datetime.now(timezone.utc),
                config=config,
                metrics=metrics,
                trades=[],
                equity_curve=None,
                final_equity=bt.final_capital,
                final_pnl=net_profit,
                final_pnl_pct=bt.total_return or 0,
            )
            print("  [OK] BacktestResult created")
            
        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()

except Exception as e:
    print(f"DB Error: {e}")
    traceback.print_exc()
finally:
    db.close()
