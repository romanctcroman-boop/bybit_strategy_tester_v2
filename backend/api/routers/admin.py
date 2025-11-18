import json
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

# Optional Basic Auth for admin endpoints (enabled if ADMIN_USER/ADMIN_PASS set)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import desc, text

from backend.celery_app import celery_app
from backend.services.backfill_service import BackfillConfig, BackfillService

security = HTTPBasic()


def _admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    # Default credentials if not provided via env
    user = os.environ.get("ADMIN_USER", "admi")
    pw = os.environ.get("ADMIN_PASS", "admin")
    correct_user = secrets.compare_digest(credentials.username or "", user or "")
    correct_pass = secrets.compare_digest(credentials.password or "", pw or "")
    if not (correct_user and correct_pass):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return True


router = APIRouter()


class BackfillRequest(BaseModel):
    symbol: str = Field(..., description="e.g. BTCUSDT")
    interval: str = Field("1", description="1,3,5,15,60,240,D,W")
    lookback_minutes: int | None = Field(None, ge=1)
    start_at_iso: str | None = Field(None, description="ISO datetime, UTC recommended")
    end_at_iso: str | None = Field(None, description="ISO datetime, UTC recommended")
    page_limit: int = Field(1000, ge=1, le=1000)
    max_pages: int = Field(500, ge=1, le=5000)
    mode: str = Field("sync", description="sync | async")


class ArchiveRequest(BaseModel):
    output_dir: str = Field("archives")
    before_iso: str | None = Field(
        None, description="Archive rows with open_time <= this ISO timestamp (UTC recommended)"
    )
    symbol: str | None = Field(None, description="Optional symbol filter")
    interval_for_partition: str = Field("1", description="Used only for partition path naming")
    batch_size: int = Field(5000, ge=100, le=100000)
    mode: str = Field("sync", description="sync | async")


class RestoreRequest(BaseModel):
    input_dir: str = Field("archives")
    mode: str = Field("sync", description="sync | async")


def _check_allowlist(symbol: str, interval: str):
    symbols = os.environ.get("ADMIN_BACKFILL_ALLOWED_SYMBOLS")
    intervals = os.environ.get("ADMIN_BACKFILL_ALLOWED_INTERVALS")
    if symbols:
        allowed_syms = {s.strip().upper() for s in symbols.split(",") if s.strip()}
        if allowed_syms and symbol.upper() not in allowed_syms:
            raise HTTPException(status_code=403, detail="symbol not allowed")
    if intervals:
        allowed_iv = {s.strip().upper() for s in intervals.split(",") if s.strip()}
        if allowed_iv and interval.upper() not in allowed_iv:
            raise HTTPException(status_code=403, detail="interval not allowed")


from backend.api.schemas import (
    ArchiveAsyncResponse,
    ArchivesListOut,
    ArchiveSyncResponse,
    BackfillAsyncResponse,
    BackfillRunOut,
    BackfillSyncResponse,
    DeleteArchiveResponse,
    RestoreAsyncResponse,
    RestoreSyncResponse,
    TaskStatusOut,
)


@router.post("/backfill", response_model=BackfillAsyncResponse | BackfillSyncResponse)
def trigger_backfill(req: BackfillRequest, _: bool = Depends(_admin_auth)):
    _check_allowlist(req.symbol, req.interval)

    if req.mode.lower() == "async":
        # Lazy import to avoid import-time issues during modules import in tests
        from backend.tasks.backfill_tasks import backfill_symbol_task

        # create a BackfillRun row with PENDING, then enqueue task
        try:
            from backend.database import Base, engine

            Base.metadata.create_all(bind=engine)
        except Exception:
            pass
        run_id = None
        from backend.database import SessionLocal

        s = SessionLocal()
        try:
            from backend.models.backfill_run import BackfillRun

            run = BackfillRun(
                symbol=req.symbol,
                interval=req.interval,
                params=json.dumps(req.dict(), ensure_ascii=False),
                status="PENDING",
            )
            s.add(run)
            s.commit()
            s.refresh(run)
            run_id = run.id
        finally:
            s.close()

        res = backfill_symbol_task.delay(
            symbol=req.symbol,
            interval=req.interval,
            lookback_minutes=req.lookback_minutes,
            start_at_iso=req.start_at_iso,
            end_at_iso=req.end_at_iso,
            page_limit=req.page_limit,
            max_pages=req.max_pages,
        )
        # update run with task_id and RUNNING
        from backend.database import SessionLocal

        s = SessionLocal()
        try:
            from backend.models.backfill_run import BackfillRun

            run = s.query(BackfillRun).get(run_id)
            if run:
                run.task_id = res.id
                run.status = "RUNNING"
                s.commit()
        finally:
            s.close()
        logger.info(f"Admin backfill async queued: task_id={res.id} {req.symbol} {req.interval}")
    return {"mode": "async", "task_id": res.id, "run_id": run_id}

    # sync mode
    # Ensure table exists
    try:
        from backend.database import Base, engine

        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    svc = BackfillService()
    from datetime import datetime

    def _parse(ts: str | None):
        if not ts:
            return None
        return datetime.fromisoformat(ts).astimezone(UTC)

    cfg = BackfillConfig(
        symbol=req.symbol,
        interval=req.interval,
        lookback_minutes=req.lookback_minutes,
        start_at=_parse(req.start_at_iso),
        end_at=_parse(req.end_at_iso),
        page_limit=req.page_limit,
        max_pages=req.max_pages,
    )
    # Create BackfillRun row
    from backend.database import SessionLocal

    s = SessionLocal()
    run_id = None
    try:
        from backend.models.backfill_run import BackfillRun

        run = BackfillRun(
            symbol=req.symbol,
            interval=req.interval,
            params=json.dumps(cfg.__dict__, default=str, ensure_ascii=False),
            status="RUNNING",
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    finally:
        s.close()

    # Metrics: mark RUNNING
    try:
        from backend.api.app import metrics_inc_run_status

        metrics_inc_run_status("RUNNING")
    except Exception:
        pass
    t0 = time.perf_counter()
    upserts, pages, eta, est_left = svc.backfill(cfg, return_stats=True)
    dt = max(time.perf_counter() - t0, 1e-6)
    rps = upserts / dt
    logger.info(
        f"Admin backfill sync done: {req.symbol} {req.interval} upserts={upserts} pages={pages} elapsed={dt:.3f}s rps={rps:.1f}"
    )
    # Prometheus metrics
    try:
        from backend.api.app import (
            metrics_inc_pages,
            metrics_inc_run_status,
            metrics_inc_upserts,
            metrics_observe_duration,
        )

        metrics_inc_upserts(req.symbol, req.interval, upserts)
        metrics_inc_pages(req.symbol, req.interval, pages)
        metrics_observe_duration(dt)
        metrics_inc_run_status("SUCCEEDED")
    except Exception:
        pass
    # finalize run row
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_run import BackfillRun

        run = s.query(BackfillRun).get(run_id)
        if run:
            run.upserts = upserts
            run.pages = pages
            run.status = "SUCCEEDED"
            run.finished_at = __import__("datetime").datetime.utcnow()
            s.commit()
    finally:
        s.close()
    return {
        "mode": "sync",
        "symbol": req.symbol,
        "interval": req.interval,
        "upserts": upserts,
        "pages": pages,
        "elapsed_sec": round(dt, 3),
        "rows_per_sec": round(rps, 1),
        "eta_sec": round(eta, 1) if eta is not None else None,
        "est_pages_left": est_left,
        "run_id": run_id,
    }


@router.post("/archive", response_model=ArchiveAsyncResponse | ArchiveSyncResponse)
def trigger_archive(req: ArchiveRequest, _: bool = Depends(_admin_auth)):
    # Validate and parse time boundary
    before_ms: int | None = None
    if req.before_iso:
        try:
            before_dt = datetime.fromisoformat(req.before_iso).astimezone(UTC)
            before_ms = int(before_dt.timestamp() * 1000)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid before_iso: {e}")

    if req.mode.lower() == "async":
        try:
            from backend.tasks.backfill_tasks import archive_candles_task

            res = archive_candles_task.delay(
                output_dir=req.output_dir,
                before_ms=before_ms,
                symbol=req.symbol,
                interval_for_partition=req.interval_for_partition,
                batch_size=req.batch_size,
            )
            return {"mode": "async", "task_id": res.id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # sync
    try:
        from backend.services.archival_service import ArchivalService, ArchiveConfig

        svc = ArchivalService(req.output_dir)
        cfg = ArchiveConfig(
            output_dir=req.output_dir,
            before_ms=before_ms,
            symbol=req.symbol,
            batch_size=req.batch_size,
        )
        total = svc.archive(cfg, interval_for_partition=req.interval_for_partition)
        return {"mode": "sync", "archived_rows": total, "output_dir": req.output_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore", response_model=RestoreAsyncResponse | RestoreSyncResponse)
def trigger_restore(req: RestoreRequest, _: bool = Depends(_admin_auth)):
    if req.mode.lower() == "async":
        try:
            from backend.tasks.backfill_tasks import restore_archives_task

            res = restore_archives_task.delay(input_dir=req.input_dir)
            return {"mode": "async", "task_id": res.id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    try:
        from backend.services.archival_service import ArchivalService

        svc = ArchivalService(req.input_dir)
        total = svc.restore_from_dir(req.input_dir)
        return {"mode": "sync", "restored_rows": total, "input_dir": req.input_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archives", response_model=ArchivesListOut)
def list_archives(dir: str = "archives", _: bool = Depends(_admin_auth)):
    base = Path(dir).resolve()
    if not base.exists():
        return {"dir": str(base), "files": []}
    files = []
    for p in base.rglob("*.parquet"):
        try:
            stat = p.stat()
            files.append(
                {
                    "path": str(p),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
        except Exception:
            pass
    return {"dir": str(base), "files": sorted(files, key=lambda x: x["path"])}


class DeleteArchiveRequest(BaseModel):
    path: str = Field(
        ..., description="Absolute path to a parquet file or a directory under archives"
    )


@router.delete("/archives", response_model=DeleteArchiveResponse)
def delete_archive(req: DeleteArchiveRequest, _: bool = Depends(_admin_auth)):
    p = Path(req.path).resolve()
    # Safety: only allow deletion under the configured archives root or current working dir/archives
    allowed_root = Path(os.environ.get("ARCHIVE_DIR", "archives")).resolve()
    try:
        p.relative_to(allowed_root)
    except Exception:
        raise HTTPException(status_code=400, detail="path must be under archives root")
    try:
        if p.is_file():
            p.unlink()
            return {"deleted": str(p)}
        if p.is_dir():
            # Remove empty dir only to avoid accidental tree wipe
            removed = []
            for child in sorted(p.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                    removed.append(str(child))
            # Try remove directories if empty
            for child in sorted(p.rglob("*"), reverse=True):
                if child.is_dir():
                    try:
                        child.rmdir()
                        removed.append(str(child))
                    except Exception:
                        pass
            # Finally try remove root dir
            try:
                p.rmdir()
                removed.append(str(p))
            except Exception:
                pass
            return {"deleted": removed}
        raise HTTPException(status_code=404, detail="not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}", response_model=TaskStatusOut)
def task_status(task_id: str, _: bool = Depends(_admin_auth)):
    """Return Celery task status for a given task_id."""
    try:
        res = celery_app.AsyncResult(task_id)
        payload = {
            "task_id": task_id,
            "state": res.state,
            "ready": res.ready(),
            "successful": res.successful() if res.ready() else False,
            "failed": res.failed() if res.ready() else False,
        }
        # include info if it's a dict or short str
        try:
            info = getattr(res, "info", None)
            if isinstance(info, dict) or isinstance(info, str) and len(info) <= 500:
                payload["info"] = info
        except Exception:
            pass
        # include result if ready and small dict
        if res.ready():
            try:
                result = res.get(propagate=False)
                if isinstance(result, dict):
                    payload["result"] = result
            except Exception as e:
                payload["error"] = str(e)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backfill/runs", response_model=list[BackfillRunOut])
def list_runs(limit: int = 50, _: bool = Depends(_admin_auth)):
    try:
        from backend.database import Base, engine

        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_run import BackfillRun

        q = s.query(BackfillRun).order_by(desc(BackfillRun.started_at)).limit(int(limit)).all()
        return [
            {
                "id": r.id,
                "task_id": r.task_id,
                "symbol": r.symbol,
                "interval": r.interval,
                "status": r.status,
                "upserts": r.upserts,
                "pages": r.pages,
                "started_at": r.started_at.isoformat() if getattr(r, "started_at", None) else None,
                "finished_at": (
                    r.finished_at.isoformat() if getattr(r, "finished_at", None) else None
                ),
                "error": r.error,
            }
            for r in q
        ]
    finally:
        s.close()


@router.get("/backfill/runs/{run_id}", response_model=BackfillRunOut)
def get_run(run_id: int, _: bool = Depends(_admin_auth)):
    try:
        from backend.database import Base, engine

        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_run import BackfillRun

        r = s.query(BackfillRun).get(run_id)
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        return {
            "id": r.id,
            "task_id": r.task_id,
            "symbol": r.symbol,
            "interval": r.interval,
            "status": r.status,
            "upserts": r.upserts,
            "pages": r.pages,
            "started_at": r.started_at.isoformat() if getattr(r, "started_at", None) else None,
            "finished_at": r.finished_at.isoformat() if getattr(r, "finished_at", None) else None,
            "params": r.params,
            "error": r.error,
        }
    finally:
        s.close()


class OkResponse(BaseModel):
    ok: bool


@router.post("/backfill/{run_id}/cancel", response_model=OkResponse)
def cancel_run(run_id: int, _: bool = Depends(_admin_auth)):
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_run import BackfillRun

        r = s.query(BackfillRun).get(run_id)
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        if not r.task_id:
            raise HTTPException(status_code=400, detail="run has no task_id")
        # Attempt to revoke Celery task
        try:
            celery_app.control.revoke(r.task_id, terminate=True)
        except Exception as e:
            logger.warning(f"celery revoke failed: {e}")
        r.status = "CANCELED"
        r.finished_at = __import__("datetime").datetime.utcnow()
        s.commit()
        return {"ok": True}
    finally:
        s.close()


class ProgressOut(BaseModel):
    symbol: str
    interval: str
    current_cursor_ms: int | None
    updated_at: str | None = None


@router.get("/backfill/progress", response_model=ProgressOut)
def get_progress(symbol: str, interval: str, _: bool = Depends(_admin_auth)):
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_progress import BackfillProgress

        rec = (
            s.query(BackfillProgress)
            .filter(BackfillProgress.symbol == symbol, BackfillProgress.interval == interval)
            .one_or_none()
        )
        if not rec:
            return {"symbol": symbol, "interval": interval, "current_cursor_ms": None}
        return {
            "symbol": rec.symbol,
            "interval": rec.interval,
            "current_cursor_ms": rec.current_cursor_ms,
            "updated_at": rec.updated_at.isoformat() if getattr(rec, "updated_at", None) else None,
        }
    finally:
        s.close()


@router.delete("/backfill/progress")
def reset_progress(symbol: str, interval: str, _: bool = Depends(_admin_auth)):
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        from backend.models.backfill_progress import BackfillProgress

        rec = (
            s.query(BackfillProgress)
            .filter(BackfillProgress.symbol == symbol, BackfillProgress.interval == interval)
            .one_or_none()
        )
        if rec:
            s.delete(rec)
            s.commit()
        return {"ok": True}
    finally:
        s.close()


class DBStatusOut(BaseModel):
    ok: bool
    connectivity: bool
    alembic_version: str | None = None
    info: str | None = None


@router.get("/db/status", response_model=DBStatusOut)
def db_status(_: bool = Depends(_admin_auth)):
    """Quick DB status: connectivity check and current alembic version.

    Returns:
      - connectivity: True if a trivial SELECT 1 succeeds
      - alembic_version: current version from alembic_version table if present
    """
    try:
        from backend.database import engine

        connectivity = False
        version = None
        with engine.connect() as conn:
            try:
                conn.execute(text("SELECT 1"))
                connectivity = True
            except Exception:
                connectivity = False
            try:
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                version = None
        return {"ok": True, "connectivity": connectivity, "alembic_version": version}
    except Exception as e:
        return {"ok": False, "connectivity": False, "info": str(e)}
