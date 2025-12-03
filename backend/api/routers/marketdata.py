from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

try:
    # Soft-import DB dependency; some tests/endpoints don't require DB
    from sqlalchemy.orm import Session  # type: ignore

    from backend.database import get_db  # type: ignore
except Exception:  # pragma: no cover - fallback for environments without DB wiring

    def get_db():  # type: ignore
        raise HTTPException(status_code=500, detail="Database not configured")

    class Session:  # type: ignore
        ...


import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from backend.api.schemas import (
    BybitKlineAuditOut,
    BybitKlineFetchRowOut,
    DataIngestResponse,
    DataUploadResponse,
    MtfResponseOut,
    RecentTradeOut,
    UploadsListResponse,
    WorkingSetCandleOut,
)
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter
from backend.services.candle_cache import CANDLE_CACHE
from backend.services.mtf_manager import MTF_MANAGER

router = APIRouter()
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)


@router.get("/bybit/klines", response_model=list[BybitKlineAuditOut])
def get_bybit_klines(
    symbol: str = Query(...),
    interval: str | None = Query(
        None, description="Optional timeframe filter; defaults to all intervals"
    ),
    limit: int = Query(100, ge=1, le=1000),
    start_time: int | None = None,
    db: Session = Depends(get_db),
):
    """Return kline audit rows for a symbol. start_time is open_time in ms; returns rows older than or equal to start_time when provided."""
    q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
    if interval:
        q = q.filter(BybitKlineAudit.interval == interval)
    if start_time:
        q = q.filter(BybitKlineAudit.open_time <= start_time)
    rows = q.order_by(BybitKlineAudit.open_time.desc()).limit(limit).all()
    results = []
    for r in rows:
        results.append(
            {
                "symbol": r.symbol,
                "interval": r.interval,
                "open_time": r.open_time,
                "open_time_dt": r.open_time_dt.isoformat() if r.open_time_dt else None,
                "open": r.open_price,
                "high": r.high_price,
                "low": r.low_price,
                "close": r.close_price,
                "volume": r.volume,
                "turnover": r.turnover,
                "raw": r.raw,
            }
        )
    return results


@router.get("/bybit/klines/fetch", response_model=list[BybitKlineFetchRowOut])
async def fetch_klines(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Query("1", description="Bybit v5 minutes as string: '1','3','60' or 'D'"),
    limit: int = Query(200, ge=1, le=1000),
    persist: int = Query(0, description="If 1, persist normalized rows into audit table"),
    db: Session = Depends(get_db),
):
    """Fetch live klines from Bybit adapter and optionally persist to audit table.

    Returns normalized rows: { open_time(ms), open, high, low, close, volume, turnover }
    """
    # Get API credentials from environment (.env file)
    api_key = os.environ.get("BYBIT_API_KEY")
    api_secret = os.environ.get("BYBIT_API_SECRET")

    def _fetch():
        adapter = BybitAdapter(api_key=api_key, api_secret=api_secret)
        try:
            rows = adapter.get_klines(symbol=symbol, interval=interval, limit=limit)
            return rows
        except Exception as exc:
            logger.exception(f"Bybit fetch failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Bybit fetch failed: {exc}")

    # Run adapter call in thread pool to avoid blocking event loop
    try:
        rows = await asyncio.get_event_loop().run_in_executor(executor, _fetch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    if persist:
        try:
            # best-effort persistence using adapter helper
            # Note: persistence can cause shutdown issues; skip for now
            logger.warning("Kline persistence requested but disabled in marketdata router")
            pass
        except Exception:
            # do not fail the endpoint for persistence errors
            pass

    # ensure minimal projection
    out = []
    for r in rows:
        out.append(
            {
                "open_time": r.get("open_time"),
                "interval": interval,
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
                "turnover": r.get("turnover"),
            }
        )
    return out


@router.get("/bybit/recent-trades", response_model=list[RecentTradeOut])
async def fetch_recent_trades(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Fetch recent trades/ticks from Bybit to build real-time OHLCV candle.

    Returns normalized trades that update every tick (not every minute like candles).
    Format: [ {time(ms), price, qty, side}, ... ]
    """
    api_key = os.environ.get("BYBIT_API_KEY")
    api_secret = os.environ.get("BYBIT_API_SECRET")

    def _fetch():
        adapter = BybitAdapter(api_key=api_key, api_secret=api_secret)
        try:
            trades = adapter.get_recent_trades(symbol=symbol, limit=limit)
            return trades
        except Exception as exc:
            logger.exception(f"Bybit trades fetch failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Bybit trades fetch failed: {exc}")

    try:
        trades = await asyncio.get_event_loop().run_in_executor(executor, _fetch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    return trades


@router.get("/bybit/klines/working", response_model=list[WorkingSetCandleOut])
async def fetch_working_set(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Query(
        "15", description="Bybit/house timeframe: '1','5','15','60','240','D','W'"
    ),
    load_limit: int = Query(1000, ge=100, le=1000, description="Initial load size (max 1000)"),
):
    """Return the working set of candles (<=500) for given (symbol, interval).

    On first access for a key, loads up to `load_limit` candles from Bybit, persists to DB,
    and keeps only the last 500 in RAM. Subsequent calls return the RAM working set.
    Format: [{ time(seconds), open, high, low, close, volume? }]
    """
    try:
        # Try to get from cache; if missing, load initial (1000 default)
        data = CANDLE_CACHE.get_working_set(symbol, interval, ensure_loaded=False)
        if not data:
            data = CANDLE_CACHE.load_initial(symbol, interval, load_limit=load_limit, persist=True)
        return data
    except Exception as exc:
        logger.exception("Failed to fetch working set: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/bybit/mtf", response_model=MtfResponseOut)
async def fetch_mtf(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    intervals: str = Query(
        "1,15,60", description="Comma-separated list, e.g. '1,15,60' or include 'D','W'"
    ),
    base: str = Query(
        None, description="Optional base timeframe to align from; defaults to smallest interval"
    ),
    aligned: int = Query(
        1,
        description="If 1, return aligned data resampled from base; if 0, return raw working sets",
    ),
    load_limit: int = Query(1000, ge=100, le=1000),
):
    try:
        ivs = [s.strip() for s in intervals.split(",") if s.strip()]
        if not ivs:
            raise HTTPException(status_code=400, detail="intervals is empty")
        if aligned:
            res = MTF_MANAGER.get_aligned(symbol, ivs, base_interval=base, load_limit=load_limit)
        else:
            res = MTF_MANAGER.get_working_sets(symbol, ivs, load_limit=load_limit)
        return {
            "symbol": res.symbol,
            "intervals": res.intervals,
            "data": res.data,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch MTF: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload", response_model=DataUploadResponse)
async def upload_market_data(
    file: UploadFile = File(...),
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Form(..., description="Timeframe: e.g. 1,3,5,15,60,240,D,W"),
):
    """Accept a market data file upload and store it on disk.

    This endpoint does not parse the file contents yet; it simply stores the uploaded
    payload under the configured uploads directory and returns basic metadata.

    Frontend can use this to verify successful upload and later trigger server-side
    processing via admin/archive/restore endpoints.
    """
    try:
        import uuid
        from pathlib import Path

        uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
        uploads_root.mkdir(parents=True, exist_ok=True)

        # Generate a unique subfolder per upload to avoid name collisions
        upload_id = uuid.uuid4().hex
        target_dir = uploads_root / upload_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / (file.filename or "payload.bin")

        size = 0
        with target_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)

        # Best-effort close
        try:
            await file.close()
        except Exception:
            pass

        return {
            "upload_id": upload_id,
            "filename": file.filename or "payload.bin",
            "size": size,
            "symbol": symbol,
            "interval": interval,
            "stored_path": str(target_path),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/uploads", response_model=UploadsListResponse)
def list_uploads():
    from pathlib import Path

    uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    if not uploads_root.exists():
        return {"dir": str(uploads_root), "items": []}
    items = []
    for upload_dir in uploads_root.iterdir():
        try:
            if not upload_dir.is_dir():
                continue
            uid = upload_dir.name
            # expect exactly one file inside; if multiple, pick largest/newest
            files = [p for p in upload_dir.iterdir() if p.is_file()]
            if not files:
                continue
            f = max(files, key=lambda p: p.stat().st_mtime)
            st = f.stat()
            items.append(
                {
                    "upload_id": uid,
                    "filename": f.name,
                    "size": st.st_size,
                    "stored_path": str(f.resolve()),
                    "mtime": st.st_mtime,
                }
            )
        except Exception:
            continue
    # sort by mtime desc
    items.sort(key=lambda x: x.get("mtime") or 0, reverse=True)
    return {"dir": str(uploads_root), "items": items}


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: str):
    from pathlib import Path

    uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    target = (uploads_root / upload_id).resolve()
    try:
        target.relative_to(uploads_root)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid upload_id")
    if not target.exists():
        raise HTTPException(status_code=404, detail="not found")
    try:
        removed = []
        for child in sorted(target.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
                removed.append(str(child))
        try:
            target.rmdir()
        except Exception:
            pass
        return {"deleted": removed or [str(target)]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("delete upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/uploads/{upload_id}/ingest", response_model=DataIngestResponse)
def ingest_upload(
    upload_id: str,
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Form(..., description="Timeframe: 1,3,5,15,60,240,D,W"),
    fmt: str = Form("csv", description="Input format: csv or jsonl"),
):
    """Parse an uploaded file and ingest candles from CSV/JSONL, update cache, best-effort DB insert."""
    import csv
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    target_dir = (uploads_root / upload_id).resolve()
    try:
        target_dir.relative_to(uploads_root)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid upload_id")
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="upload not found")

    files = [p for p in target_dir.iterdir() if p.is_file()]
    if not files:
        raise HTTPException(status_code=404, detail="no file in upload")
    src = max(files, key=lambda p: p.stat().st_mtime)

    rows: list[dict] = []
    earliest_ms: int | None = None
    latest_ms: int | None = None

    def parse_ts_ms(row: dict) -> int | None:
        v = row.get("open_time") or row.get("openTime")
        if v is not None:
            try:
                return int(float(v))
            except Exception:
                pass
        v = row.get("time")
        if v is not None:
            try:
                return int(float(v)) * 1000
            except Exception:
                pass
        v = row.get("datetime") or row.get("timestamp")
        if v is not None:
            try:
                dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception:
                pass
        return None

    def to_float(x) -> float | None:
        try:
            if x is None:
                return None
            return float(x)
        except Exception:
            return None

    if fmt.lower() not in {"csv", "jsonl"}:
        raise HTTPException(status_code=400, detail="unsupported format")

    if fmt.lower() == "csv":
        with src.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ms = parse_ts_ms(r)
                if ms is None:
                    continue
                o = to_float(r.get("open"))
                h = to_float(r.get("high"))
                low_val = to_float(r.get("low"))
                c = to_float(r.get("close"))
                v = to_float(r.get("volume"))
                if None in (o, h, low_val, c):
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": ms,
                        "open": o,
                        "high": h,
                        "low": low_val,
                        "close": c,
                        "volume": v,
                    }
                )
                earliest_ms = ms if earliest_ms is None or ms < earliest_ms else earliest_ms
                latest_ms = ms if latest_ms is None or ms > latest_ms else latest_ms
    else:
        with src.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ms = parse_ts_ms(r)
                if ms is None:
                    continue
                o = to_float(r.get("open"))
                h = to_float(r.get("high"))
                low_val = to_float(r.get("low"))
                c = to_float(r.get("close"))
                v = to_float(r.get("volume")) if r.get("volume") is not None else None
                if None in (o, h, low_val, c):
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "open_time": ms,
                        "open": o,
                        "high": h,
                        "low": low_val,
                        "close": c,
                        "volume": v,
                    }
                )
                earliest_ms = ms if earliest_ms is None or ms < earliest_ms else earliest_ms
                latest_ms = ms if latest_ms is None or ms > latest_ms else latest_ms

    if not rows:
        return {
            "upload_id": upload_id,
            "symbol": symbol,
            "interval": interval,
            "format": fmt,
            "ingested": 0,
            "skipped": None,
            "earliest_ms": None,
            "latest_ms": None,
            "updated_working_set": 0,
        }

    inserted = 0
    try:
        from sqlalchemy.orm import Session as SASession

        from backend.database import Base, SessionLocal, engine
        from backend.models.bybit_kline_audit import BybitKlineAudit

        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

        sess: SASession = SessionLocal()
        try:
            objs = []
            for r in rows:
                ms = int(r["open_time"])
                dt = datetime.fromtimestamp(ms / 1000.0, tz=UTC)
                obj = BybitKlineAudit(
                    symbol=symbol,
                    interval=interval,
                    open_time=ms,
                    open_time_dt=dt,
                    open_price=float(r["open"]),
                    high_price=float(r["high"]),
                    low_price=float(r["low"]),
                    close_price=float(r["close"]),
                    volume=float(r["volume"]) if r.get("volume") is not None else None,
                    turnover=None,
                    raw="{}",
                )
                obj.set_raw({**r, "symbol": symbol, "interval": interval})
                objs.append(obj)
            sess.bulk_save_objects(objs)
            sess.commit()
            inserted = len(objs)
        finally:
            sess.close()
    except Exception as exc:
        logger.warning("DB insert skipped or failed: %s", exc)

    try:
        rows_sorted = sorted(rows, key=lambda r: int(r["open_time"]))
        working = [
            {
                "time": int(r["open_time"]) // 1000,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]) if r.get("volume") is not None else None,
            }
            for r in rows_sorted[-CANDLE_CACHE.RAM_LIMIT :]
        ]
        CANDLE_CACHE._store[CANDLE_CACHE._key(symbol, interval)] = working
        updated_ws = len(working)
    except Exception as exc:
        logger.warning("Failed to update working set: %s", exc)
        updated_ws = 0

    return {
        "upload_id": upload_id,
        "symbol": symbol,
        "interval": interval,
        "format": fmt,
        "ingested": inserted or len(rows),
        "skipped": (len(rows) - inserted) if inserted and inserted < len(rows) else 0,
        "earliest_ms": earliest_ms,
        "latest_ms": latest_ms,
        "updated_working_set": updated_ws,
    }


@router.post("/bybit/prime")
def prime_working_sets(
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    intervals: str = Form("1,5,15,60", description="Comma-separated list: e.g. '1,5,15,60,240,D'"),
    load_limit: int = Form(1000, description="Initial load size per interval (max 1000)"),
):
    """Preload working sets for a symbol across multiple intervals.

    For each interval: fetch up to `load_limit` candles from Bybit (real API),
    persist best-effort to the audit table, and keep last 500 candles in RAM.

    Returns lengths of in-RAM working sets per interval.
    """
    try:
        ivs = [s.strip() for s in intervals.split(",") if s.strip()]
        if not ivs:
            raise HTTPException(status_code=400, detail="intervals is empty")
        results: dict[str, int] = {}
        for itv in ivs:
            try:
                data = CANDLE_CACHE.load_initial(symbol, itv, load_limit=load_limit, persist=True)
                results[itv] = len(data or [])
            except Exception as exc:
                results[itv] = -1
                logger.warning("prime failed for %s %s: %s", symbol, itv, exc)
        return {"symbol": symbol.upper(), "intervals": ivs, "ram_working_set": results}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("prime_working_sets failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/bybit/reset")
def reset_working_sets(
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    intervals: str = Form(
        "1,5,15,60", description="Comma-separated list: e.g. '1,5,15,60,240,D'"
    ),
    reload: int = Form(1, description="If 1, reload from remote after reset; if 0, just clear"),
    load_limit: int = Form(1000, description="Load size per interval when reload=1 (max 1000)"),
):
    """Reset in-memory candle bases (working sets) for the given symbol and intervals.

    - Clears RAM cache for each (symbol, interval).
    - If reload=1 (default), fetches up to `load_limit` candles and repopulates the working set.

    Returns the new in-RAM lengths per interval (or -1 if clear-only).
    """
    try:
        ivs = [s.strip() for s in intervals.split(",") if s.strip()]
        if not ivs:
            raise HTTPException(status_code=400, detail="intervals is empty")
        results: dict[str, int] = {}
        for itv in ivs:
            try:
                if reload:
                    # use reset(reload=True) which internally calls load_initial
                    data = CANDLE_CACHE.reset(symbol, itv, reload=True)
                    # if load_limit differs from default, force a refresh with that limit
                    if load_limit and load_limit != CANDLE_CACHE.LOAD_LIMIT:
                        data = CANDLE_CACHE.load_initial(symbol, itv, load_limit=load_limit, persist=True)
                    results[itv] = len(data or [])
                else:
                    CANDLE_CACHE.reset(symbol, itv, reload=False)
                    results[itv] = -1
            except Exception as exc:
                results[itv] = -2
                logger.warning("reset failed for %s %s: %s", symbol, itv, exc)
        return {"symbol": symbol.upper(), "intervals": ivs, "ram_working_set": results}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("reset_working_sets failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
