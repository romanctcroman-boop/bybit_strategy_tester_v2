from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

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
    MtfResponseOut,
    RecentTradeOut,
    WorkingSetCandleOut,
)
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter
from backend.services.candle_cache import CANDLE_CACHE
from backend.services.mtf_manager import MTF_MANAGER

router = APIRouter()
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)


@router.get("/bybit/klines", response_model=List[BybitKlineAuditOut])
def get_bybit_klines(
    symbol: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Return kline audit rows for a symbol. start_time is open_time in ms; returns rows older than or equal to start_time when provided."""
    q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
    if start_time:
        q = q.filter(BybitKlineAudit.open_time <= start_time)
    rows = q.order_by(BybitKlineAudit.open_time.desc()).limit(limit).all()
    results = []
    for r in rows:
        results.append(
            {
                "symbol": r.symbol,
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


@router.get("/bybit/klines/fetch", response_model=List[BybitKlineFetchRowOut])
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
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
                "turnover": r.get("turnover"),
            }
        )
    return out


@router.get("/bybit/recent-trades", response_model=List[RecentTradeOut])
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


@router.get("/bybit/klines/working", response_model=List[WorkingSetCandleOut])
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
