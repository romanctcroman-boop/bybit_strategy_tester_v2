"""
Backtest Tasks

Celery tasks to run backtests in the background.
"""

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict

from celery import Task
from loguru import logger

from backend.celery_app import celery_app
from backend.core.engine_adapter import get_engine
from backend.database import Backtest, SessionLocal
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
                    backtest.updated_at = datetime.now(timezone.utc)
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
    strategy_config: Dict[str, Any],
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
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

        now = datetime.now(timezone.utc)
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
            if getattr(backtest, "status", None) == "running" and running_since:
                if now - running_since < timedelta(hours=24):
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
        engine = get_engine(
            None,
            data_service=ds,
            initial_capital=initial_capital,
            commission=0.0006,
            slippage=0.0001,
        )
        results = engine.run(data=candles, strategy_config=strategy_config)

        logger.info("💾 Saving results...")
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
                "results": results,
            },
        )

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
                completed_at=datetime.now(timezone.utc),
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
def bulk_backtest_task(backtest_configs: list) -> Dict[str, Any]:
    """Run multiple backtests in parallel (delegates to individual tasks)."""
    logger.info(f"🚀 Starting bulk backtest: {len(backtest_configs)} backtests")
    from celery import group

    job = group([run_backtest_task.s(**config) for config in backtest_configs])
    result = job.apply_async()

    return {"task_id": result.id, "total_backtests": len(backtest_configs), "status": "pending"}
