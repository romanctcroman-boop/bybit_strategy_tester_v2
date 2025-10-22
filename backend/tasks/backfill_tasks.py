"""
Celery tasks for historical backfill.
"""
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from backend.celery_app import celery_app
from backend.services.backfill_service import BackfillService, BackfillConfig
from backend.database import SessionLocal
from backend.models.backfill_run import BackfillRun
import json
from backend.services.archival_service import ArchivalService, ArchiveConfig


@celery_app.task(name="backend.tasks.backfill_tasks.backfill_symbol")
def backfill_symbol_task(
    symbol: str,
    interval: str = "1",
    lookback_minutes: Optional[int] = None,
    start_at_iso: Optional[str] = None,
    end_at_iso: Optional[str] = None,
    page_limit: int = 1000,
    max_pages: int = 500,
):
    svc = BackfillService()
    def _parse(ts: Optional[str]):
        if not ts:
            return None
        return datetime.fromisoformat(ts).astimezone(timezone.utc)

    cfg = BackfillConfig(
        symbol=symbol,
        interval=interval,
        lookback_minutes=lookback_minutes,
        start_at=_parse(start_at_iso),
        end_at=_parse(end_at_iso),
        page_limit=page_limit,
        max_pages=max_pages,
    )

    # Attempt to find a matching BackfillRun by task_id
    s = SessionLocal()
    run = None
    try:
        run = s.query(BackfillRun).filter(BackfillRun.task_id == backfill_symbol_task.request.id).one_or_none()  # type: ignore[attr-defined]
        if run:
            run.status = 'RUNNING'
            s.commit()
    finally:
        s.close()
    # Metrics: mark RUNNING
    try:
        from backend.api.app import metrics_inc_run_status
        metrics_inc_run_status('RUNNING')
    except Exception:
        pass

    try:
        t0 = __import__('time').perf_counter()
        upserts, pages, eta, est_left = svc.backfill(cfg, return_stats=True)
        dt = max(__import__('time').perf_counter() - t0, 1e-6)
        logger.info(f"Backfill task done: {symbol} {interval} upserts={upserts} pages={pages}")
        # Update run row
        s = SessionLocal()
        try:
            if not run:
                run = s.query(BackfillRun).filter(BackfillRun.task_id == backfill_symbol_task.request.id).one_or_none()  # type: ignore[attr-defined]
            if run:
                run.upserts = upserts
                run.pages = pages
                run.status = 'SUCCEEDED'
                run.finished_at = __import__('datetime').datetime.utcnow()
                s.commit()
        finally:
            s.close()
        # Prometheus metrics
        try:
            from backend.api.app import metrics_inc_upserts, metrics_inc_pages, metrics_observe_duration, metrics_inc_run_status
            metrics_inc_upserts(symbol, interval, upserts)
            metrics_inc_pages(symbol, interval, pages)
            metrics_observe_duration(dt)
            metrics_inc_run_status('SUCCEEDED')
        except Exception:
            pass
        return {"symbol": symbol, "interval": interval, "upserts": upserts, "pages": pages, "eta_sec": eta, "est_pages_left": est_left}
    except Exception as e:
        logger.exception("Backfill task failed")
        s = SessionLocal()
        try:
            if not run:
                run = s.query(BackfillRun).filter(BackfillRun.task_id == backfill_symbol_task.request.id).one_or_none()  # type: ignore[attr-defined]
            if run:
                run.status = 'FAILED'
                run.error = str(e)
                run.finished_at = __import__('datetime').datetime.utcnow()
                s.commit()
        finally:
            s.close()
        # Prometheus metrics
        try:
            from backend.api.app import metrics_inc_run_status
            metrics_inc_run_status('FAILED')
        except Exception:
            pass
        return {"symbol": symbol, "interval": interval, "error": str(e)}


@celery_app.task(name="backend.tasks.backfill_tasks.archive_candles")
def archive_candles_task(
    output_dir: str = "archives",
    before_ms: int = None,
    symbol: str = None,
    interval_for_partition: str = "1",
    batch_size: int = 5000,
):
    svc = ArchivalService(output_dir)
    cfg = ArchiveConfig(output_dir=output_dir, before_ms=before_ms, symbol=symbol, batch_size=batch_size)
    total = svc.archive(cfg, interval_for_partition=interval_for_partition)
    return {"archived_rows": total, "output_dir": output_dir}


@celery_app.task(name="backend.tasks.backfill_tasks.restore_archives")
def restore_archives_task(
    input_dir: str = "archives",
):
    svc = ArchivalService(input_dir)
    total = svc.restore_from_dir(input_dir)
    return {"restored_rows": total, "input_dir": input_dir}
