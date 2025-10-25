"""
Backtest Tasks

Celery tasks to run backtests in the background.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Task
from loguru import logger

from backend.celery_app import celery_app
from backend.core.engine_adapter import get_engine
from backend.database import SessionLocal
from backend.models import Backtest
from backend.services.data_service import DataService

# Optional Prometheus metrics
try:  # pragma: no cover
    from prometheus_client import Counter, Histogram

    BACKTEST_STARTED = Counter("backtest_runs_started_total", "Backtest runs started")
    BACKTEST_COMPLETED = Counter("backtest_runs_completed_total", "Backtest runs completed")
    BACKTEST_FAILED = Counter("backtest_runs_failed_total", "Backtest runs failed")
    BACKTEST_DURATION = Histogram(
        "backtest_run_duration_seconds", "Backtest task duration in seconds"
    )
except Exception:  # pragma: no cover
    BACKTEST_STARTED = BACKTEST_COMPLETED = BACKTEST_FAILED = BACKTEST_DURATION = None  # type: ignore


def _transform_results_for_frontend(engine_results: dict, initial_capital: float) -> dict:
    """
    Transform BacktestEngine output to Frontend-expected BacktestResults format.
    
    Frontend expects:
    - overview: {net_pnl, net_pct, total_trades, wins, losses, max_drawdown_abs/pct, profit_factor}
    - by_side: {all, long, short} stats
    - dynamics: {all, long, short} dynamics (unrealized, net, fees, runup, drawdown, buyhold)
    - risk: {sharpe, sortino, profit_factor}
    - equity: [{time, equity}]
    - pnl_bars: [{time, pnl}] (optional, cumulative PnL per bar)
    """
    metrics = engine_results.get('metrics', {})
    trades = engine_results.get('trades', [])
    
    # Calculate per-side stats
    long_trades = [t for t in trades if t.get('side', '').upper() in ('LONG', 'BUY')]
    short_trades = [t for t in trades if t.get('side', '').upper() in ('SHORT', 'SELL')]
    
    def calc_side_stats(trade_list):
        if not trade_list:
            return {
                'total_trades': 0,
                'open_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_pl': 0.0,
                'avg_pl_pct': 0.0,
                'avg_win': 0.0,
                'avg_win_pct': 0.0,
                'avg_loss': 0.0,
                'avg_loss_pct': 0.0,
                'max_win': 0.0,
                'max_win_pct': 0.0,
                'max_loss': 0.0,
                'max_loss_pct': 0.0,
                'profit_factor': 0.0,
                'avg_bars': 0.0,
                'avg_bars_win': 0.0,
                'avg_bars_loss': 0.0,
            }
        
        wins = [t for t in trade_list if t.get('pnl', 0) > 0]
        losses = [t for t in trade_list if t.get('pnl', 0) < 0]
        
        total = len(trade_list)
        num_wins = len(wins)
        num_losses = len(losses)
        
        gross_profit = sum(t.get('pnl', 0) for t in wins)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losses))
        
        return {
            'total_trades': total,
            'open_trades': 0,  # All trades are closed after backtest
            'wins': num_wins,
            'losses': num_losses,
            'win_rate': (num_wins / total * 100) if total > 0 else 0.0,
            'avg_pl': sum(t.get('pnl', 0) for t in trade_list) / total if total > 0 else 0.0,
            'avg_pl_pct': sum(t.get('pnl_pct', 0) for t in trade_list) / total if total > 0 else 0.0,
            'avg_win': gross_profit / num_wins if num_wins > 0 else 0.0,
            'avg_win_pct': sum(t.get('pnl_pct', 0) for t in wins) / num_wins if num_wins > 0 else 0.0,
            'avg_loss': -gross_loss / num_losses if num_losses > 0 else 0.0,
            'avg_loss_pct': sum(t.get('pnl_pct', 0) for t in losses) / num_losses if num_losses > 0 else 0.0,
            'max_win': max((t.get('pnl', 0) for t in wins), default=0.0),
            'max_win_pct': max((t.get('pnl_pct', 0) for t in wins), default=0.0),
            'max_loss': min((t.get('pnl', 0) for t in losses), default=0.0),
            'max_loss_pct': min((t.get('pnl_pct', 0) for t in losses), default=0.0),
            'profit_factor': (gross_profit / gross_loss) if gross_loss > 0 else 0.0,
            'avg_bars': sum(t.get('bars_held', 0) for t in trade_list) / total if total > 0 else 0.0,
            'avg_bars_win': sum(t.get('bars_held', 0) for t in wins) / num_wins if num_wins > 0 else 0.0,
            'avg_bars_loss': sum(t.get('bars_held', 0) for t in losses) / num_losses if num_losses > 0 else 0.0,
        }
    
    all_stats = calc_side_stats(trades)
    long_stats = calc_side_stats(long_trades)
    short_stats = calc_side_stats(short_trades)
    
    # Overview section
    overview = {
        'net_pnl': metrics.get('net_profit', 0.0),
        'net_pct': metrics.get('net_profit_pct', 0.0),
        'total_trades': engine_results.get('total_trades', 0),
        'wins': engine_results.get('winning_trades', 0),
        'losses': engine_results.get('losing_trades', 0),
        'max_drawdown_abs': metrics.get('max_drawdown_abs', 0.0),
        'max_drawdown_pct': metrics.get('max_drawdown_pct', 0.0),
        'profit_factor': engine_results.get('profit_factor', 0.0),
    }
    
    # Dynamics section
    def calc_dynamics(trade_list):
        if not trade_list:
            return {
                'unrealized_abs': 0.0,
                'unrealized_pct': 0.0,
                'net_abs': 0.0,
                'net_pct': 0.0,
                'gross_profit_abs': 0.0,
                'gross_profit_pct': 0.0,
                'gross_loss_abs': 0.0,
                'gross_loss_pct': 0.0,
                'fees_abs': 0.0,
                'fees_pct': 0.0,
                'max_runup_abs': 0.0,
                'max_runup_pct': 0.0,
                'max_drawdown_abs': 0.0,
                'max_drawdown_pct': 0.0,
                'buyhold_abs': 0.0,
                'buyhold_pct': 0.0,
                'max_contracts': 0,
            }
        
        wins = [t for t in trade_list if t.get('pnl', 0) > 0]
        losses = [t for t in trade_list if t.get('pnl', 0) < 0]
        
        gross_profit = sum(t.get('pnl', 0) for t in wins)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losses))
        net = sum(t.get('pnl', 0) for t in trade_list)
        fees = sum(t.get('commission', 0) for t in trade_list)
        
        return {
            'unrealized_abs': 0.0,  # All trades closed
            'unrealized_pct': 0.0,
            'net_abs': net,
            'net_pct': (net / initial_capital * 100) if initial_capital > 0 else 0.0,
            'gross_profit_abs': gross_profit,
            'gross_profit_pct': (gross_profit / initial_capital * 100) if initial_capital > 0 else 0.0,
            'gross_loss_abs': gross_loss,
            'gross_loss_pct': (gross_loss / initial_capital * 100) if initial_capital > 0 else 0.0,
            'fees_abs': fees,
            'fees_pct': (fees / initial_capital * 100) if initial_capital > 0 else 0.0,
            'max_runup_abs': max((t.get('run_up', 0) for t in trade_list), default=0.0),
            'max_runup_pct': max((t.get('run_up_pct', 0) for t in trade_list), default=0.0),
            'max_drawdown_abs': abs(min((t.get('drawdown', 0) for t in trade_list), default=0.0)),
            'max_drawdown_pct': abs(min((t.get('drawdown_pct', 0) for t in trade_list), default=0.0)),
            'buyhold_abs': metrics.get('buy_hold_return', 0.0) if trade_list == trades else 0.0,
            'buyhold_pct': (metrics.get('buy_hold_return', 0.0) / initial_capital * 100) if initial_capital > 0 and trade_list == trades else 0.0,
            'max_contracts': 1,  # Simple backtester, 1 position at a time
        }
    
    dynamics = {
        'all': calc_dynamics(trades),
        'long': calc_dynamics(long_trades),
        'short': calc_dynamics(short_trades),
    }
    
    # Risk section
    risk = {
        'sharpe': engine_results.get('sharpe_ratio', 0.0),
        'sortino': engine_results.get('sortino_ratio', 0.0),
        'profit_factor': engine_results.get('profit_factor', 0.0),
    }
    
    # Equity curve
    equity_curve = engine_results.get('equity_curve', [])
    equity = [
        {
            'time': point['timestamp'],
            'equity': point['equity'],
        }
        for point in equity_curve
    ]
    
    # PnL bars (cumulative PnL per bar) - optional, can be derived from equity
    pnl_bars = [
        {
            'time': point['timestamp'],
            'pnl': point['equity'] - initial_capital,
        }
        for point in equity_curve
    ]
    
    return {
        'overview': overview,
        'by_side': {
            'all': all_stats,
            'long': long_stats,
            'short': short_stats,
        },
        'dynamics': dynamics,
        'risk': risk,
        'equity': equity,
        'pnl_bars': pnl_bars,
    }


class BacktestTask(Task):
    """Base Celery Task for backtests with DB failure handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"❌ Backtest task {task_id} failed: {exc}")
        backtest_id = kwargs.get("backtest_id") or (args[0] if args else None)
        if backtest_id:
            try:
                db = SessionLocal()
                backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
                if backtest:
                    backtest.status = "failed"
                    backtest.error_message = str(exc)
                    backtest.updated_at = datetime.now(UTC)
                    db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to update backtest status: {e}")

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"✅ Backtest task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=BacktestTask,
    name="backend.tasks.backtest_tasks.run_backtest",
    max_retries=3,
    default_retry_delay=60,
)
def run_backtest_task(
    self,
    backtest_id: int,
    strategy_config: dict[str, Any],
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
) -> dict[str, Any]:
    """Run a backtest task (Celery).

    Attempts to claim the backtest row atomically via DataService.claim_backtest_to_run.
    Falls back to non-atomic legacy behavior if that method is not present.
    """
    logger.info(f"🚀 Starting backtest task: {backtest_id}")
    logger.info(f"   Symbol: {symbol}, Interval: {interval}")
    logger.info(f"   Period: {start_date} → {end_date}")
    t0 = time.perf_counter()
    if BACKTEST_STARTED:
        BACKTEST_STARTED.inc()

    db = SessionLocal()
    ds = DataService(db)

    try:
        backtest = ds.get_backtest(backtest_id)
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        if getattr(backtest, "status", None) == "completed":
            logger.info(f"Backtest {backtest_id} already completed; skipping")
            return {"backtest_id": backtest_id, "status": "completed"}

        now = datetime.now(UTC)
        if hasattr(ds, "claim_backtest_to_run"):
            claimed = ds.claim_backtest_to_run(backtest_id, now, stale_seconds=300)
            status = claimed.get("status") if isinstance(claimed, dict) else None

            if status == "not_found":
                raise ValueError("backtest not found or could not be claimed")

            if status == "completed":
                return {"backtest_id": backtest_id, "status": "completed"}

            if status == "running":
                logger.info(f"Backtest {backtest_id} is already running; skipping")
                return {"backtest_id": backtest_id, "status": "running"}

            if status == "error":
                raise RuntimeError(f"Failed to claim backtest: {claimed.get('message')}")
            # if status == 'claimed' we continue
        else:
            # Legacy path: mark running if not already running/recent
            running_since = getattr(backtest, "started_at", None)
            if (
                getattr(backtest, "status", None) == "running"
                and running_since
                and now - running_since < timedelta(hours=24)
            ):
                logger.info(f"Backtest {backtest_id} is already running; skipping")
                return {"backtest_id": backtest_id, "status": "running"}

            ds.update_backtest(backtest_id, status="running", started_at=now)

        logger.info("📥 Loading market data...")
        candles = ds.get_market_data(
            symbol=symbol, timeframe=interval, start_time=start_date, end_time=end_date
        )

        if candles is None:
            raise ValueError(f"No data available for {symbol} {interval}")

        logger.info(f"📊 Loaded {len(candles)} candles")

        logger.info("⚙️  Running backtest engine...")
        
        # Получаем параметры из strategy_config или используем значения по умолчанию
        leverage = strategy_config.get("leverage", 1)
        order_size_usd = strategy_config.get("order_size_usd", None)
        
        # Комиссия Bybit = 0.075%
        commission = 0.075 / 100  # 0.00075
        slippage_pct = 0.05  # 0.05%
        
        engine = get_engine(
            None,
            initial_capital=initial_capital,
            commission=commission,
            slippage_pct=slippage_pct,
            leverage=leverage,
            order_size_usd=order_size_usd,
        )
        
        results = engine.run(data=candles, strategy_config=strategy_config)

        logger.info("💾 Saving results...")
        
        # Transform results to frontend-expected format
        frontend_results = _transform_results_for_frontend(results, initial_capital)
        
        # Сохраняем результаты бэктеста
        ds.update_backtest_results(
            backtest_id=backtest_id,
            **{
                "final_capital": results.get("final_capital", 0),
                "total_return": results.get("total_return", 0),
                "total_trades": results.get("total_trades", 0),
                "winning_trades": results.get("winning_trades", 0),
                "losing_trades": results.get("losing_trades", 0),
                "win_rate": results.get("win_rate", 0),
                "sharpe_ratio": results.get("sharpe_ratio", 0),
                "max_drawdown": results.get("max_drawdown", 0),
                "results": frontend_results,  # Frontend-compatible format
            },
        )
        
        # Сохраняем трейды в БД
        trades = results.get("trades", [])
        if trades:
            logger.info(f"💾 Saving {len(trades)} trades...")
            trades_data = []
            for trade in trades:
                # Парсим ISO strings обратно в datetime для БД
                entry_time = trade.get("entry_time")
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                
                exit_time = trade.get("exit_time")
                if isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time)
                
                trade_data = {
                    "backtest_id": backtest_id,
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "side": trade.get("side", "long").upper(),
                    "entry_price": trade.get("entry_price"),
                    "exit_price": trade.get("exit_price"),
                    "quantity": trade.get("quantity"),
                    "pnl": trade.get("pnl"),
                    "pnl_pct": trade.get("pnl_pct"),
                    "run_up": trade.get("run_up"),
                    "run_up_pct": trade.get("run_up_pct"),
                    "drawdown": trade.get("drawdown"),
                    "drawdown_pct": trade.get("drawdown_pct"),
                    "cumulative_pnl": trade.get("cumulative_pnl"),
                }
                trades_data.append(trade_data)
            
            ds.create_trades_batch(trades_data)

        logger.info(f"✅ Backtest {backtest_id} completed")
        if BACKTEST_COMPLETED:
            BACKTEST_COMPLETED.inc()
        if BACKTEST_DURATION:
            try:
                BACKTEST_DURATION.observe(max(time.perf_counter() - t0, 0.0))
            except Exception:
                pass
        return {"backtest_id": backtest_id, "status": "completed", "results": results}

    except Exception as e:
        logger.error(f"❌ Backtest task failed: {e}")
        try:
            ds.update_backtest(
                backtest_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(UTC),
            )
        except Exception as db_error:
            logger.error(f"Failed to update backtest status: {db_error}")

        # Retry if possible (be robust when self is None in tests)
        if BACKTEST_FAILED:
            try:
                BACKTEST_FAILED.inc()
            except Exception:
                pass
        if BACKTEST_DURATION:
            try:
                BACKTEST_DURATION.observe(max(time.perf_counter() - t0, 0.0))
            except Exception:
                pass
        retries = 0
        max_retries = 0
        if self is not None:
            retries = getattr(getattr(self, "request", None), "retries", 0)
            max_retries = getattr(self, "max_retries", 0)

        if retries < max_retries:
            logger.info(f"Retrying backtest {backtest_id} (attempt {retries + 1}/{max_retries})")
            if self is not None and hasattr(self, "retry"):
                raise self.retry(exc=e)
            # If running in tests or self lacks retry, re-raise the exception to surface failure

        raise

    finally:
        try:
            if db is not None and hasattr(db, "close"):
                db.close()
        except Exception:
            # best-effort cleanup; nothing we can do here
            pass


@celery_app.task(name="backend.tasks.backtest_tasks.bulk_backtest")
def bulk_backtest_task(backtest_configs: list) -> dict[str, Any]:
    """Run multiple backtests in parallel (delegates to individual tasks)."""
    logger.info(f"🚀 Starting bulk backtest: {len(backtest_configs)} backtests")
    from celery import group

    job = group([run_backtest_task.s(**config) for config in backtest_configs])
    result = job.apply_async()

    return {"task_id": result.id, "total_backtests": len(backtest_configs), "status": "pending"}
