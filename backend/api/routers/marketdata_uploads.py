"""
Market Data Upload Endpoints

Extracted from marketdata.py for better maintainability.
Handles file upload, listing, deletion and ingestion.
"""

import csv
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.api.schemas import (
    DataIngestResponse,
    DataUploadResponse,
    UploadsListResponse,
)
from backend.services.candle_cache import CANDLE_CACHE

router = APIRouter(tags=["Market Data Uploads"])
logger = logging.getLogger(__name__)


# =============================================================================
# UPLOAD ENDPOINTS
# =============================================================================


@router.post("/upload", response_model=DataUploadResponse)
async def upload_market_data(
    file: UploadFile = File(...),
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Form(..., description="Timeframe: e.g. 1,3,5,15,60,240,D,W"),
):
    """Accept a market data file upload and store it on disk.

    This endpoint does not parse the file contents yet; it simply stores the uploaded
    payload under the configured uploads directory and returns basic metadata.
    """
    try:
        uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
        uploads_root.mkdir(parents=True, exist_ok=True)

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

        try:
            await file.close()
        except Exception as e:
            logger.debug("File close failed: %s", e)

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
    """List all uploaded files."""
    uploads_root = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    if not uploads_root.exists():
        return {"dir": str(uploads_root), "items": []}

    items = []
    for upload_dir in uploads_root.iterdir():
        try:
            if not upload_dir.is_dir():
                continue
            uid = upload_dir.name
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

    items.sort(key=lambda x: x.get("mtime") or 0, reverse=True)
    return {"dir": str(uploads_root), "items": items}


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: str):
    """Delete an uploaded file."""
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
        except Exception as e:
            logger.debug("rmdir failed: %s", e)
        return {"deleted": removed or [str(target)]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("delete upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# INGEST ENDPOINTS
# =============================================================================


def _parse_ts_ms(row: dict) -> int | None:
    """Parse timestamp from various formats."""
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


def _to_float(x) -> float | None:
    """Safe float conversion."""
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@router.post("/uploads/{upload_id}/ingest", response_model=DataIngestResponse)
def ingest_upload(
    upload_id: str,
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Form(..., description="Timeframe: 1,3,5,15,60,240,D,W"),
    fmt: str = Form("csv", description="Input format: csv or jsonl"),
):
    """Parse an uploaded file and ingest candles from CSV/JSONL."""
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

    if fmt.lower() not in {"csv", "jsonl"}:
        raise HTTPException(status_code=400, detail="unsupported format")

    # Parse file
    if fmt.lower() == "csv":
        rows, earliest_ms, latest_ms = _parse_csv(src, symbol, interval)
    else:
        rows, earliest_ms, latest_ms = _parse_jsonl(src, symbol, interval)

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

    # Insert to DB
    inserted = _insert_to_db(rows, symbol, interval)

    # Update working set cache
    updated_ws = _update_working_set(rows, symbol, interval)

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


def _parse_csv(
    src: Path, symbol: str, interval: str
) -> tuple[list[dict], int | None, int | None]:
    """Parse CSV file."""
    rows = []
    earliest_ms = None
    latest_ms = None

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ms = _parse_ts_ms(r)
            if ms is None:
                continue
            o = _to_float(r.get("open"))
            h = _to_float(r.get("high"))
            low_val = _to_float(r.get("low"))
            c = _to_float(r.get("close"))
            v = _to_float(r.get("volume"))
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

    return rows, earliest_ms, latest_ms


def _parse_jsonl(
    src: Path, symbol: str, interval: str
) -> tuple[list[dict], int | None, int | None]:
    """Parse JSONL file."""
    rows = []
    earliest_ms = None
    latest_ms = None

    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ms = _parse_ts_ms(r)
            if ms is None:
                continue
            o = _to_float(r.get("open"))
            h = _to_float(r.get("high"))
            low_val = _to_float(r.get("low"))
            c = _to_float(r.get("close"))
            v = _to_float(r.get("volume")) if r.get("volume") is not None else None
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

    return rows, earliest_ms, latest_ms


def _insert_to_db(rows: list[dict], symbol: str, interval: str) -> int:
    """Insert rows to database."""
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

    return inserted


def _update_working_set(rows: list[dict], symbol: str, interval: str) -> int:
    """Update in-memory working set cache."""
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
        return len(working)
    except Exception as exc:
        logger.warning("Failed to update working set: %s", exc)
        return 0
