"""
Market Data Endpoints

Core klines and trades fetching from Bybit API.
Upload and cache management endpoints moved to:
- marketdata_uploads.py
- marketdata_cache.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

try:
    from sqlalchemy.orm import Session

    from backend.database import get_db
except Exception:

    def get_db():
        raise HTTPException(status_code=500, detail="Database not configured")

    class Session: ...


import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from backend.api.routers.marketdata_cache import router as cache_router

# Include sub-routers for uploads and cache management
from backend.api.routers.marketdata_uploads import router as uploads_router
from backend.api.schemas import (
    BybitKlineAuditOut,
    BybitKlineFetchRowOut,
    MtfResponseOut,
    RecentTradeOut,
    WorkingSetCandleOut,
)
from backend.config.database_policy import DATA_START_TIMESTAMP_MS
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter
from backend.services.candle_cache import CANDLE_CACHE
from backend.services.mtf_manager import MTF_MANAGER
from backend.services.smart_kline_service import SMART_KLINE_SERVICE

router = APIRouter()
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)

# Global cached BybitAdapter instance (avoid recreating on each request)
_bybit_adapter: BybitAdapter | None = None

# Cache for db-groups query (heavy GROUP BY - takes ~500ms on 2M+ rows)
_db_groups_cache: dict | None = None
_db_groups_cache_time: float = 0
_DB_GROUPS_CACHE_TTL: float = 5.0  # seconds


def invalidate_db_groups_cache():
    """Invalidate db-groups cache (call after delete/block/unblock operations)."""
    global _db_groups_cache, _db_groups_cache_time
    _db_groups_cache = None
    _db_groups_cache_time = 0


def get_bybit_adapter() -> BybitAdapter:
    """Get or create cached BybitAdapter instance."""
    global _bybit_adapter
    if _bybit_adapter is None:
        api_key = os.environ.get("BYBIT_API_KEY")
        api_secret = os.environ.get("BYBIT_API_SECRET")
        _bybit_adapter = BybitAdapter(api_key=api_key, api_secret=api_secret)
    return _bybit_adapter


# Include sub-routers
router.include_router(uploads_router)
router.include_router(cache_router)


# =============================================================================
# KLINES ENDPOINTS
# =============================================================================


@router.get("/symbols/local")
def get_local_symbols(
    db: Session = Depends(get_db),
):
    """
    Return list of symbols that have local data in the database.
    Used to mark symbols in the Symbol picker dropdown.
    """
    try:
        from sqlalchemy import func

        # Get distinct symbols with their intervals and row counts
        results = (
            db.query(
                BybitKlineAudit.symbol,
                BybitKlineAudit.interval,
                func.count(BybitKlineAudit.id).label("count"),
                func.min(BybitKlineAudit.open_time).label("min_time"),
                func.max(BybitKlineAudit.open_time).label("max_time"),
            )
            .group_by(BybitKlineAudit.symbol, BybitKlineAudit.interval)
            .all()
        )

        # Organize by symbol
        symbols_data = {}
        for row in results:
            symbol = row.symbol
            if symbol not in symbols_data:
                symbols_data[symbol] = {"intervals": {}, "total_rows": 0}
            symbols_data[symbol]["intervals"][row.interval] = {
                "count": row.count,
                "min_time": row.min_time,
                "max_time": row.max_time,
            }
            symbols_data[symbol]["total_rows"] += row.count

        blocked = set()
        try:
            from backend.services.blocked_tickers import get_blocked

            blocked = get_blocked()
        except Exception:
            pass

        return {
            "symbols": list(symbols_data.keys()),
            "details": symbols_data,
            "blocked": list(blocked),
        }
    except Exception as e:
        logger.error(f"Error getting local symbols: {e}")
        return {"symbols": [], "details": {}, "blocked": []}


# =============================================================================
# База Даннах (Dunnah Base) — группы тикеров в БД, удаление, блокировка
# =============================================================================


@router.get("/symbols/db-groups")
def get_db_groups(db: Session = Depends(get_db)):
    """
    Группы тикеров в БД: (symbol, market_type) → интервалы и счётчики.
    Для секции «База Даннах». Кэшируется на 5 секунд.
    """
    import time

    global _db_groups_cache, _db_groups_cache_time

    # Return cached data if fresh (within TTL)
    now = time.time()
    if _db_groups_cache is not None and (now - _db_groups_cache_time) < _DB_GROUPS_CACHE_TTL:
        # Update blocked list (fast operation)
        _db_groups_cache["blocked"] = list(_get_blocked())
        return _db_groups_cache

    try:
        from sqlalchemy import func
        from sqlalchemy.exc import OperationalError

        try:
            results = (
                db.query(
                    BybitKlineAudit.symbol,
                    BybitKlineAudit.market_type,
                    BybitKlineAudit.interval,
                    func.count(BybitKlineAudit.id).label("count"),
                    func.min(BybitKlineAudit.open_time).label("min_time"),
                    func.max(BybitKlineAudit.open_time).label("max_time"),
                )
                .group_by(BybitKlineAudit.symbol, BybitKlineAudit.market_type, BybitKlineAudit.interval)
                .all()
            )
        except OperationalError:
            # Fallback: БД без market_type (старая схема)
            results = (
                db.query(
                    BybitKlineAudit.symbol,
                    BybitKlineAudit.interval,
                    func.count(BybitKlineAudit.id).label("count"),
                    func.min(BybitKlineAudit.open_time).label("min_time"),
                    func.max(BybitKlineAudit.open_time).label("max_time"),
                )
                .group_by(BybitKlineAudit.symbol, BybitKlineAudit.interval)
                .all()
            )
            # Normalize to (symbol, market_type, interval, count, min_time, max_time)
            results = [(r.symbol, "linear", r.interval, r.count, r.min_time, r.max_time) for r in results]

        groups = {}
        for row in results:
            sym, mt, iv, cnt, min_t, max_t = row[0], row[1] or "linear", row[2], row[3], row[4], row[5]
            key = (sym, mt)
            if key not in groups:
                groups[key] = {"symbol": sym, "market_type": mt, "intervals": {}, "total_rows": 0}
            groups[key]["intervals"][iv] = {"count": cnt, "min_time": min_t, "max_time": max_t}
            groups[key]["total_rows"] += cnt

        result = {"groups": list(groups.values()), "blocked": list(_get_blocked())}

        # Cache the result
        _db_groups_cache = result
        _db_groups_cache_time = now

        return result
    except Exception as e:
        logger.error(f"Error getting db groups: {e}")
        return {"groups": [], "blocked": []}


def _get_blocked():
    try:
        from backend.services.blocked_tickers import get_blocked

        return get_blocked()
    except Exception:
        return set()


@router.delete("/symbols/db-groups")
def delete_db_group(
    symbol: str = Query(..., description="Symbol to delete"),
    market_type: str = Query("linear", description="Market type: spot or linear"),
    db: Session = Depends(get_db),
):
    """Удалить все свечи тикера (symbol + market_type) из БД."""
    from sqlalchemy import or_
    from sqlalchemy.exc import OperationalError

    symbol = symbol.upper()
    try:
        q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
        q = q.filter(
            or_(
                BybitKlineAudit.market_type == market_type,
                BybitKlineAudit.market_type.is_(None),
            )
        )
        count = q.delete(synchronize_session=False)
    except OperationalError:
        q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
        count = q.delete(synchronize_session=False)
    db.commit()

    # Invalidate cache after delete
    invalidate_db_groups_cache()

    logger.info(f"Deleted {count} candles for {symbol}/{market_type}")
    return {"deleted": count, "symbol": symbol, "market_type": market_type}


@router.get("/symbols/blocked")
def get_blocked_tickers():
    """Список тикеров, заблокированных для догрузки."""
    try:
        from backend.services.blocked_tickers import get_blocked

        return {"symbols": list(get_blocked())}
    except Exception as e:
        logger.error(f"Error getting blocked: {e}")
        return {"symbols": []}


@router.post("/symbols/blocked")
def add_blocked_ticker(symbol: str = Query(...)):
    """Заблокировать тикер — не догружать при старте и в Properties."""
    try:
        from backend.services.blocked_tickers import add_blocked

        added = add_blocked(symbol)
        from backend.services.blocked_tickers import get_blocked

        return {"added": added, "symbols": list(get_blocked())}
    except Exception as e:
        logger.error(f"Error adding blocked: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/symbols/blocked/{symbol}")
def remove_blocked_ticker(symbol: str):
    """Разблокировать тикер."""
    try:
        from backend.services.blocked_tickers import get_blocked, remove_blocked

        removed = remove_blocked(symbol)
        return {"removed": removed, "symbols": list(get_blocked())}
    except Exception as e:
        logger.error(f"Error removing blocked: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bybit/klines", response_model=list[BybitKlineAuditOut])
def get_bybit_klines(
    symbol: str = Query(...),
    interval: str | None = Query(None, description="Optional timeframe filter; defaults to all intervals"),
    limit: int = Query(100, ge=1, le=1000),
    start_time: int | None = None,
    db: Session = Depends(get_db),
):
    """Return kline audit rows for a symbol from database."""
    q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
    if interval:
        q = q.filter(BybitKlineAudit.interval == interval)
    if start_time:
        q = q.filter(BybitKlineAudit.open_time <= start_time)

    rows = q.order_by(BybitKlineAudit.open_time.desc()).limit(limit).all()

    return [
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
        for r in rows
    ]


@router.get("/bybit/volatility")
def get_volatility(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    days: int = Query(90, ge=7, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Calculate volatility metrics for a symbol over specified days.

    Returns:
    - atr_percent: Average True Range as percentage of price
    - max_daily_move: Maximum single day move (high-low) as percentage
    - max_drawdown: Maximum peak-to-trough decline as percentage
    - avg_daily_range: Average daily range (high-low) as percentage
    """
    from datetime import datetime, timedelta

    # Calculate start time (N days ago)
    start_date = datetime.now(UTC) - timedelta(days=days)
    start_time_ms = int(start_date.timestamp() * 1000)

    # Query daily candles from database
    q = (
        db.query(BybitKlineAudit)
        .filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.interval == "D",  # Daily candles
            BybitKlineAudit.open_time >= start_time_ms,
        )
        .order_by(BybitKlineAudit.open_time.asc())
    )

    rows = q.all()

    if len(rows) < 7:
        # Not enough data, try to return empty response
        return {
            "symbol": symbol,
            "days": days,
            "actual_days": len(rows),
            "atr_percent": None,
            "max_daily_move": None,
            "max_drawdown": None,
            "avg_daily_range": None,
            "error": f"Not enough data. Found {len(rows)} daily candles, need at least 7.",
        }

    # Calculate metrics
    daily_ranges = []
    true_ranges = []
    closes = []
    highs = []

    prev_close = None
    for r in rows:
        high = float(r.high_price)
        low = float(r.low_price)
        close = float(r.close_price)

        # Daily range as percentage
        if close > 0:
            daily_range_pct = ((high - low) / close) * 100
            daily_ranges.append(daily_range_pct)

        # True Range (includes gaps)
        if prev_close is not None:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            if close > 0:
                true_ranges.append((tr / close) * 100)

        closes.append(close)
        highs.append(high)
        prev_close = close

    # Calculate max drawdown
    max_drawdown = 0
    peak = closes[0] if closes else 0
    for close in closes:
        if close > peak:
            peak = close
        drawdown = ((peak - close) / peak) * 100 if peak > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Calculate averages
    atr_percent = sum(true_ranges) / len(true_ranges) if true_ranges else 0
    avg_daily_range = sum(daily_ranges) / len(daily_ranges) if daily_ranges else 0
    max_daily_move = max(daily_ranges) if daily_ranges else 0

    return {
        "symbol": symbol,
        "days": days,
        "actual_days": len(rows),
        "atr_percent": round(atr_percent, 2),
        "max_daily_move": round(max_daily_move, 2),
        "max_drawdown": round(max_drawdown, 2),
        "avg_daily_range": round(avg_daily_range, 2),
    }


@router.post("/bybit/volatility/refresh-all")
async def refresh_all_daily_data(
    days: int = Query(90, ge=30, le=365, description="Days of daily data to ensure"),
    db: Session = Depends(get_db),
):
    """
    Refresh daily (D) candle data for ALL symbols in the database.

    This ensures volatility calculations work correctly for risk assessment.
    Should be called on startup or periodically.

    Returns:
    - symbols_updated: List of symbols that were refreshed
    - symbols_skipped: List of symbols already up-to-date
    - errors: Any errors encountered
    """
    from datetime import datetime

    from sqlalchemy import distinct, func

    # Get all unique symbols in database
    symbols = db.query(distinct(BybitKlineAudit.symbol)).all()
    symbols = [s[0] for s in symbols if s[0]]

    if not symbols:
        return {"status": "no_symbols", "message": "No symbols found in database"}

    adapter = get_bybit_adapter()
    results = {
        "total_symbols": len(symbols),
        "symbols_updated": [],
        "symbols_skipped": [],
        "errors": [],
    }

    # Calculate required time range

    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    one_day_ms = 24 * 60 * 60 * 1000

    for symbol in symbols:
        try:
            # Check latest daily candle in DB
            latest = (
                db.query(func.max(BybitKlineAudit.open_time))
                .filter(
                    BybitKlineAudit.symbol == symbol,
                    BybitKlineAudit.interval == "D",
                )
                .scalar()
            )

            # If latest is less than 1 day old, skip
            if latest and (now_ms - latest) < one_day_ms:
                results["symbols_skipped"].append(symbol)
                continue

            # Fetch daily candles from Bybit
            try:
                rows = adapter.get_klines(symbol=symbol, interval="D", limit=days)
                if rows:
                    rows_with_interval = [{**r, "interval": "D"} for r in rows]
                    adapter._persist_klines_to_db(symbol, rows_with_interval)
                    results["symbols_updated"].append({"symbol": symbol, "candles": len(rows)})
                    logger.info(f"[VOLATILITY] Refreshed {len(rows)} daily candles for {symbol}")
            except Exception as e:
                results["errors"].append({"symbol": symbol, "error": str(e)})
                logger.warning(f"[VOLATILITY] Failed to refresh {symbol}: {e}")

        except Exception as e:
            results["errors"].append({"symbol": symbol, "error": str(e)})

    results["status"] = "completed"
    return results


@router.get("/bybit/klines/fetch", response_model=list[BybitKlineFetchRowOut])
async def fetch_klines(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Query("1", description="Bybit v5 minutes as string: '1','3','60' or 'D'"),
    limit: int = Query(200, ge=1, le=1000),
    persist: int = Query(0, description="If 1, persist normalized rows into audit table"),
    db: Session = Depends(get_db),
):
    """Fetch live klines from Bybit adapter and optionally persist to audit table."""
    adapter = get_bybit_adapter()

    def _fetch():
        try:
            return adapter.get_klines(symbol=symbol, interval=interval, limit=limit)
        except Exception as exc:
            logger.exception(f"Bybit fetch failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Bybit fetch failed: {exc}")

    try:
        rows = await asyncio.get_event_loop().run_in_executor(executor, _fetch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    # Persist to database if requested
    if persist and rows:
        try:
            adapter = get_bybit_adapter()
            # Add interval to each row for persistence
            rows_with_interval = [{**r, "interval": interval} for r in rows]
            adapter._persist_klines_to_db(symbol, rows_with_interval)
            logger.info(f"Persisted {len(rows)} klines for {symbol}/{interval}")
        except Exception as e:
            logger.warning(f"Failed to persist klines: {e}")

    return [
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
        for r in rows
    ]


@router.get("/bybit/klines/history", response_model=list[BybitKlineFetchRowOut])
async def fetch_history(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Query("60", description="Bybit interval: '1','5','15','60','D'"),
    end_time: int = Query(..., description="End timestamp in milliseconds (load data BEFORE this time)"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Fetch historical klines before a specific time.
    Used for infinite scroll - loads older data when user scrolls left.
    First checks DB cache, then fetches from Bybit API if needed.
    """
    adapter = get_bybit_adapter()

    # First check if we have data in DB
    existing = (
        db.query(BybitKlineAudit)
        .filter(
            BybitKlineAudit.symbol == symbol,
            BybitKlineAudit.interval == interval,
            BybitKlineAudit.open_time < end_time,
        )
        .order_by(BybitKlineAudit.open_time.desc())
        .limit(limit)
        .all()
    )

    if len(existing) >= limit:
        # We have enough data in DB
        logger.info(f"[History] Serving {len(existing)} rows from DB for {symbol}/{interval}")
        return [
            {
                "open_time": r.open_time,
                "interval": r.interval,
                "open": r.open_price,
                "high": r.high_price,
                "low": r.low_price,
                "close": r.close_price,
                "volume": r.volume,
                "turnover": r.turnover,
            }
            for r in existing
        ]

    # Need to fetch from Bybit API
    def _fetch():
        try:
            # Bybit API uses 'end' parameter for fetching data before a time
            return adapter.get_klines_before(symbol=symbol, interval=interval, end_time=end_time, limit=limit)
        except Exception as exc:
            logger.exception(f"Bybit history fetch failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Bybit history fetch failed: {exc}")

    try:
        rows = await asyncio.get_event_loop().run_in_executor(executor, _fetch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    # Persist to database
    if rows:
        try:
            # Add interval to each row for persistence
            rows_with_interval = [{**r, "interval": interval} for r in rows]
            adapter._persist_klines_to_db(symbol, rows_with_interval)
            logger.info(f"[History] Persisted {len(rows)} historical klines for {symbol}/{interval}")
        except Exception as e:
            logger.warning(f"Failed to persist historical klines: {e}")

    return [
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
        for r in rows
    ]


# =============================================================================
# TRADES ENDPOINT
# =============================================================================


@router.get("/bybit/recent-trades", response_model=list[RecentTradeOut])
async def fetch_recent_trades(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Fetch recent trades/ticks from Bybit to build real-time OHLCV candle."""
    adapter = get_bybit_adapter()

    def _fetch():
        try:
            return adapter.get_recent_trades(symbol=symbol, limit=limit)
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


# =============================================================================
# WORKING SET ENDPOINT
# =============================================================================


@router.get("/bybit/klines/working", response_model=list[WorkingSetCandleOut])
async def fetch_working_set(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    interval: str = Query("15", description="Bybit/house timeframe: '1','5','15','60','240','D','W'"),
    load_limit: int = Query(1000, ge=100, le=1000, description="Initial load size (max 1000)"),
):
    """Return the working set of candles (<=500) for given (symbol, interval)."""
    try:
        data = CANDLE_CACHE.get_working_set(symbol, interval, ensure_loaded=False)
        if not data:
            data = CANDLE_CACHE.load_initial(symbol, interval, load_limit=load_limit, persist=True)
        return data
    except Exception as exc:
        logger.exception("Failed to fetch working set: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# MTF ENDPOINT
# =============================================================================


@router.get("/bybit/mtf", response_model=MtfResponseOut)
async def fetch_mtf(
    symbol: str = Query(..., description="Instrument symbol, e.g. BTCUSDT"),
    intervals: str = Query("1,15,60", description="Comma-separated list, e.g. '1,15,60' or include 'D','W'"),
    base: str = Query(
        None,
        description="Optional base timeframe to align from; defaults to smallest interval",
    ),
    aligned: int = Query(
        1,
        description="If 1, return aligned data resampled from base; if 0, return raw working sets",
    ),
    load_limit: int = Query(1000, ge=100, le=1000),
):
    """Fetch multi-timeframe data for a symbol."""
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


# =============================================================================
# SMART KLINE SERVICE ENDPOINTS
# =============================================================================


@router.post("/bybit/symbol/initialize")
async def initialize_symbol(
    symbol: str = Query(..., description="Trading pair symbol, e.g. BTCUSDT"),
    interval: str = Query("60", description="Primary timeframe interval"),
    load_history: bool = Query(True, description="Load 12 months of history"),
    load_adjacent: bool = Query(True, description="Also load adjacent timeframes"),
):
    """
    Initialize a trading pair.

    This endpoint should be called when user first selects a trading pair.
    It will:
    1. Load 12 months of historical data for the selected timeframe
    2. Pre-load adjacent timeframes (e.g., 30m → 15m, 30m, 1h)
    3. Keep 500 candles in RAM for fast access
    4. Store all data in database

    The loading happens in background, so this endpoint returns immediately
    with status information.
    """
    try:
        result = await SMART_KLINE_SERVICE.initialize_symbol(
            symbol=symbol,
            primary_interval=interval,
            load_history=load_history,
            load_adjacent=load_adjacent,
        )
        return result
    except Exception as exc:
        logger.exception(f"Failed to initialize symbol: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/bybit/symbol/status")
async def get_symbol_status():
    """
    Get status of the Smart Kline Service.

    Returns information about:
    - Loaded symbols and intervals
    - Loading progress for background tasks
    - RAM cache usage
    """
    return SMART_KLINE_SERVICE.get_status()


@router.get("/bybit/symbol/loading-progress")
async def get_loading_progress():
    """Get progress of background loading operations."""
    return SMART_KLINE_SERVICE.get_loading_status()


@router.get("/bybit/klines/smart")
async def get_smart_klines(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query("60", description="Timeframe interval"),
    limit: int = Query(500, ge=1, le=2000),
    force_fresh: bool = Query(False, description="Force fetch from API for latest data"),
):
    """
    Get candles using Smart Kline Service.

    This endpoint uses intelligent caching:
    1. First checks RAM cache
    2. Then checks database
    3. Only fetches from API if needed

    Use this endpoint for chart display.
    Set force_fresh=true to bypass cache and get latest data from API.
    """
    try:
        # Run synchronous get_candles in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        candles = await loop.run_in_executor(
            executor,
            lambda: SMART_KLINE_SERVICE.get_candles(
                symbol=symbol, interval=interval, limit=limit, force_fresh=force_fresh
            ),
        )
        return candles
    except Exception as exc:
        logger.exception(f"Failed to get smart klines: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/bybit/klines/smart-history")
async def get_smart_history(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query("60", description="Timeframe interval"),
    end_time: int = Query(..., description="Load candles BEFORE this timestamp (ms)"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Get historical candles for infinite scroll.

    Returns candles older than end_time.
    Uses database first, then API if needed.
    """
    try:
        # Run synchronous get_historical_candles in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        candles = await loop.run_in_executor(
            executor,
            lambda: SMART_KLINE_SERVICE.get_historical_candles(
                symbol=symbol, interval=interval, end_time=end_time, limit=limit
            ),
        )
        return candles
    except Exception as exc:
        logger.exception(f"Failed to get smart history: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# DATA QUALITY ENDPOINTS
# =============================================================================


@router.get("/bybit/data-quality/check")
async def check_data_quality(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query("60", description="Timeframe interval"),
):
    """
    Run data quality checks on symbol/interval.

    Returns:
    - is_healthy: Overall health status
    - completeness_pct: % of expected candles present
    - freshness_ok: Whether data is up-to-date
    - continuity_issues: Number of unusual price jumps
    - ml_anomalies: Number of ML-detected outliers
    - anomalies: List of detected issues
    """
    try:
        from backend.services.data_quality_service import DATA_QUALITY_SERVICE

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, lambda: DATA_QUALITY_SERVICE.run_all_checks(symbol, interval))

        return {
            "symbol": result.symbol,
            "interval": result.interval,
            "check_time": result.check_time.isoformat(),
            "is_healthy": result.is_healthy,
            "completeness_pct": round(result.completeness_pct, 2),
            "freshness_ok": result.freshness_ok,
            "continuity_issues": result.continuity_issues,
            "ml_anomalies": result.ml_anomalies,
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "description": a.description,
                    "timestamp": a.timestamp,
                    "auto_repaired": a.auto_repaired,
                }
                for a in result.anomalies[:20]  # Limit to 20 anomalies
            ],
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Data quality service not available")
    except Exception as exc:
        logger.exception(f"Data quality check failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/bybit/data-quality/repair")
async def repair_data_issues(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query("60", description="Timeframe interval"),
):
    """
    Run data quality check and auto-repair detected issues.

    Returns:
    - issues_found: Number of issues detected
    - issues_repaired: Number of issues automatically repaired
    """
    try:
        from backend.services.data_quality_service import DATA_QUALITY_SERVICE

        loop = asyncio.get_event_loop()

        # First run checks
        result = await loop.run_in_executor(executor, lambda: DATA_QUALITY_SERVICE.run_all_checks(symbol, interval))

        issues_found = len(result.anomalies)
        issues_repaired = 0

        # Auto-repair if issues found
        if issues_found > 0:
            issues_repaired = await DATA_QUALITY_SERVICE.auto_repair(symbol, interval, result)

        return {
            "symbol": symbol,
            "interval": interval,
            "is_healthy": result.is_healthy,
            "issues_found": issues_found,
            "issues_repaired": issues_repaired,
            "message": f"Repaired {issues_repaired} of {issues_found} issues",
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Data quality service not available")
    except Exception as exc:
        logger.exception(f"Data quality repair failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# TOP SYMBOLS BY VOLUME
# =============================================================================
# GET /symbols-list и POST /refresh-tickers вынесены в tickers_api и регистрируются
# на уровне app (add_api_route), чтобы один источник правды и полная пагинация Bybit.


@router.get("/tickers")
async def get_all_tickers(
    category: str = Query("linear", description="Market category: linear or spot"),
):
    """
    Get all tickers with price, 24h change, and volume data.
    Used for symbol picker with sorting capabilities.
    """
    try:
        adapter = get_bybit_adapter()
        loop = asyncio.get_event_loop()

        # Fetch all tickers for the requested category
        tickers = await loop.run_in_executor(executor, lambda: adapter.get_tickers(symbols=None, category=category))

        # Format response
        result = [
            {
                "symbol": t["symbol"],
                "price": float(t.get("price") or 0),
                "change_24h": float(t.get("change_24h") or 0),
                "volume_24h": float(t.get("turnover_24h") or 0),  # Use turnover (USDT value)
            }
            for t in tickers
        ]

        return {"tickers": result, "count": len(result)}

    except Exception as exc:
        logger.exception(f"Failed to fetch tickers: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query("BTCUSDT", description="Trading pair"),
    category: str = Query("linear", description="Market category: linear, spot, inverse, option"),
    limit: int = Query(25, ge=1, le=500, description="Order book depth levels"),
):
    """
    Get L2 order book snapshot from Bybit.

    Experimental: for L2 order book research and Generative LOB.
    """
    try:
        adapter = get_bybit_adapter()
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            executor,
            lambda: adapter.get_orderbook(symbol=symbol.upper(), category=category, limit=limit),
        )
        if not raw:
            raise HTTPException(status_code=502, detail="Bybit orderbook unavailable")
        return raw
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_orderbook failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/symbols/cache-refresh")
async def refresh_symbols_cache(request: Request):
    """
    Принудительно загрузить тикеры с Bybit (Futures + Spot) и обновить кэш.
    Вызов после старта или по кнопке «Обновить список» в Properties.
    """
    try:
        adapter = get_bybit_adapter()
        loop = asyncio.get_event_loop()
        linear = await loop.run_in_executor(
            None, lambda: adapter.get_symbols_list(category="linear", trading_only=True)
        )
        spot = await loop.run_in_executor(None, lambda: adapter.get_symbols_list(category="spot", trading_only=True))
        if not hasattr(request.app.state, "symbols_cache"):
            request.app.state.symbols_cache = {}
        request.app.state.symbols_cache["linear"] = linear or []
        request.app.state.symbols_cache["spot"] = spot or []
        return {
            "ok": True,
            "linear": len(request.app.state.symbols_cache["linear"]),
            "spot": len(request.app.state.symbols_cache["spot"]),
        }
    except Exception as exc:
        logger.exception("refresh_symbols_cache failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/symbols/top")
async def get_top_symbols(
    limit: int = Query(20, ge=1, le=100, description="Number of top symbols to return"),
):
    """
    Get top trading pairs by 24h volume from Bybit.

    Returns list of symbols sorted by volume descending.
    """
    try:
        adapter = get_bybit_adapter()
        loop = asyncio.get_event_loop()

        # Fetch all tickers
        tickers = await loop.run_in_executor(executor, adapter.get_tickers)

        # Sort by 24h volume (turnover in USDT is more accurate)
        sorted_tickers = sorted(tickers, key=lambda x: x.get("turnover_24h", 0) or 0, reverse=True)

        # Return top N
        top_symbols = [
            {
                "symbol": t["symbol"],
                "price": t.get("price"),
                "change_24h": t.get("change_24h"),
                "volume_24h": t.get("volume_24h"),
                "turnover_24h": t.get("turnover_24h"),
            }
            for t in sorted_tickers[:limit]
        ]

        return {"symbols": top_symbols, "count": len(top_symbols)}

    except Exception as exc:
        logger.exception(f"Failed to fetch top symbols: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/symbols/check-data")
async def check_symbol_data(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query(..., description="Timeframe interval"),
    db: Session = Depends(get_db),
):
    """
    Check if data exists in database for symbol/interval pair.
    Returns status and triggers data loading if needed.
    """
    try:
        # Convert frontend interval format to DB format
        # Frontend: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
        # DB: 1, 5, 15, 30, 60, 240, D, W
        interval_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "12h": "720",
            "1d": "D",
            "1w": "W",
            "1M": "M",
        }
        db_interval = interval_map.get(interval, interval)

        # Check if data exists in DB
        count = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == db_interval,
            )
            .count()
        )

        has_data = count > 0

        # Get latest candle timestamp if exists
        latest = None
        if has_data:
            latest_row = (
                db.query(BybitKlineAudit)
                .filter(
                    BybitKlineAudit.symbol == symbol.upper(),
                    BybitKlineAudit.interval == db_interval,
                )
                .order_by(BybitKlineAudit.open_time.desc())
                .first()
            )
            if latest_row:
                latest = latest_row.open_time

        # Calculate freshness (how old is the latest candle)
        from datetime import datetime

        freshness_status = "unknown"
        hours_old = None
        latest_datetime = None

        if latest:
            # latest is in milliseconds

            latest_dt = datetime.fromtimestamp(latest / 1000, tz=UTC)
            latest_datetime = latest_dt.isoformat()
            now = datetime.now(UTC)
            delta = now - latest_dt
            hours_old = delta.total_seconds() / 3600

            # Determine freshness based on interval
            interval_hours = {
                "1": 1 / 60,
                "3": 3 / 60,
                "5": 5 / 60,
                "15": 0.25,
                "30": 0.5,
                "60": 1,
                "120": 2,
                "240": 4,
                "360": 6,
                "720": 12,
                "D": 24,
                "W": 168,
                "M": 720,
            }
            expected_interval = interval_hours.get(db_interval, 1)

            # Fresh if latest candle is within 2x the interval
            if hours_old <= expected_interval * 2:
                freshness_status = "fresh"
            elif hours_old <= expected_interval * 24:
                freshness_status = "stale"
            else:
                freshness_status = "outdated"

        # Get earliest candle timestamp
        earliest = None
        earliest_datetime = None
        if has_data:
            earliest_row = (
                db.query(BybitKlineAudit)
                .filter(
                    BybitKlineAudit.symbol == symbol.upper(),
                    BybitKlineAudit.interval == db_interval,
                )
                .order_by(BybitKlineAudit.open_time.asc())
                .first()
            )
            if earliest_row:
                earliest = earliest_row.open_time
                earliest_dt = datetime.utcfromtimestamp(earliest / 1000)
                earliest_datetime = earliest_dt.isoformat() + "Z"

        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "db_interval": db_interval,
            "has_data": has_data,
            "candle_count": count,
            "earliest_timestamp": earliest,
            "earliest_datetime": earliest_datetime,
            "latest_timestamp": latest,
            "latest_datetime": latest_datetime,
            "hours_old": round(hours_old, 1) if hours_old else None,
            "freshness": freshness_status,
            "status": "available" if has_data else "missing",
        }

    except Exception as exc:
        logger.exception(f"Failed to check symbol data: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/symbols/refresh-data")
async def refresh_symbol_data(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query(..., description="Timeframe interval (e.g., 30m, 1h)"),
    market_type: str = Query("linear", description="Market type: 'spot' or 'linear' (perpetual)"),
    db: Session = Depends(get_db),
):
    """
    Refresh/update data for a symbol/interval pair.
    Fetches candles from Bybit starting from DATA_START_DATE (from centralized config).
    Uses smart fetching - only gets missing candles at both ends.
    """
    # Use centralized config constants
    data_start_ts = DATA_START_TIMESTAMP_MS

    try:
        # Convert frontend interval to DB/Bybit format
        interval_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "12h": "720",
            "1d": "D",
            "1w": "W",
            "1M": "M",
        }
        bybit_interval = interval_map.get(interval, interval)

        adapter = get_bybit_adapter()

        # Get current date range in DB
        earliest_row = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .order_by(BybitKlineAudit.open_time.asc())
            .first()
        )
        latest_row = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .order_by(BybitKlineAudit.open_time.desc())
            .first()
        )

        earliest_in_db = earliest_row.open_time if earliest_row else None
        latest_in_db = latest_row.open_time if latest_row else None
        now_ts = int(datetime.now(UTC).timestamp() * 1000)

        # Count current records before any updates
        initial_count = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .count()
        )

        # Case 1: No data in DB - load everything from 2025-01-01
        # Case 2: Data exists but starts after 2025-01-01 - backfill historical
        # Case 3: Data exists - just update to current time

        async def fetch_and_persist(start_ts: int, end_ts: int, mtype: str = "linear") -> int:
            """Fetch candles between start and end, persist and return count."""
            try:
                rows = await adapter.get_historical_klines(
                    symbol=symbol.upper(),
                    interval=bybit_interval,
                    start_time=start_ts,
                    end_time=end_ts,
                    limit=1000,
                    market_type=mtype,
                )
                if rows:
                    rows_with_interval = [{**r, "interval": bybit_interval} for r in rows]
                    adapter._persist_klines_to_db(symbol.upper(), rows_with_interval, market_type=mtype)
                    return len(rows)
                return 0
            except Exception as e:
                logger.error(f"Failed to fetch klines {start_ts}-{end_ts}: {e}")
                return 0

        if not earliest_in_db:
            # No data - full historical load from 2025-01-01
            logger.info(f"Loading full history for {symbol}/{interval}/{market_type} from 2025-01-01")
            await fetch_and_persist(data_start_ts, now_ts, market_type)
        else:
            # Check if we need to backfill (data starts after 2025-01-01)
            # Allow 1 day tolerance (86400000 ms) for minor gaps
            if earliest_in_db > data_start_ts + 86400000:
                logger.info(f"Backfilling {symbol}/{interval}/{market_type} from 2025-01-01 to existing data")
                await fetch_and_persist(data_start_ts, earliest_in_db - 1, market_type)

            # Update to current time - fetch from last known candle
            if latest_in_db and latest_in_db < now_ts:
                # Calculate interval in milliseconds
                interval_ms_map = {
                    "1": 60000,  # 1 min
                    "3": 180000,  # 3 min
                    "5": 300000,  # 5 min
                    "15": 900000,  # 15 min
                    "30": 1800000,  # 30 min
                    "60": 3600000,  # 1 hour
                    "120": 7200000,  # 2 hours
                    "240": 14400000,  # 4 hours
                    "360": 21600000,  # 6 hours
                    "720": 43200000,  # 12 hours
                    "D": 86400000,  # 1 day
                    "W": 604800000,  # 1 week
                    "M": 2592000000,  # 30 days
                }
                interval_ms = interval_ms_map.get(bybit_interval, 3600000)

                # Нахлёст свечей: 5 для малых TF, меньше для D/W/M
                overlap = OVERLAP_CANDLES.get(bybit_interval, 5)
                update_start = latest_in_db - (interval_ms * overlap)

                logger.info(f"Updating {symbol}/{interval}/{market_type} from last known candle (overlap={overlap})")
                await fetch_and_persist(update_start, now_ts, market_type)

        # Get updated stats from DB
        total_in_db = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .count()
        )

        # Get updated date range
        new_earliest = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .order_by(BybitKlineAudit.open_time.asc())
            .first()
        )
        new_latest = (
            db.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol.upper(),
                BybitKlineAudit.interval == bybit_interval,
            )
            .order_by(BybitKlineAudit.open_time.desc())
            .first()
        )

        earliest_dt = None
        latest_dt = None
        if new_earliest:
            earliest_dt = datetime.utcfromtimestamp(new_earliest.open_time / 1000).isoformat() + "Z"
        if new_latest:
            latest_dt = datetime.utcfromtimestamp(new_latest.open_time / 1000).isoformat() + "Z"

        # Calculate actual new candles by comparing counts (most accurate)
        actual_new = max(0, total_in_db - initial_count)

        # ========== BACKGROUND: Refresh 1m data for Bar Magnifier / Intrabar simulation ==========
        # Only if the requested interval is not already 1m
        if bybit_interval != "1":
            import asyncio

            async def refresh_1m_background():
                """Refresh 1m candles in background for intrabar simulation."""
                try:
                    from backend.database import SessionLocal

                    bg_db = SessionLocal()
                    try:
                        # Check if 1m data exists
                        m1_count = (
                            bg_db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol.upper(),
                                BybitKlineAudit.interval == "1",
                            )
                            .count()
                        )

                        # Get latest 1m candle
                        m1_latest = (
                            bg_db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol.upper(),
                                BybitKlineAudit.interval == "1",
                            )
                            .order_by(BybitKlineAudit.open_time.desc())
                            .first()
                        )

                        m1_latest_ts = m1_latest.open_time if m1_latest else None

                        # Only update if no data or stale (>1 hour old)
                        should_update = m1_count == 0 or (m1_latest_ts and (now_ts - m1_latest_ts) > 3600000)

                        if should_update:
                            logger.info(f"[BAR_MAGNIFIER] Background refresh 1m data for {symbol}")

                            # Fetch last 24h of 1m data (1440 candles) for intrabar simulation
                            start_1m = now_ts - (24 * 60 * 60 * 1000)  # 24 hours ago
                            if m1_latest_ts:
                                start_1m = m1_latest_ts - 60000  # 1 minute overlap

                            rows = await adapter.get_historical_klines(
                                symbol=symbol.upper(),
                                interval="1",
                                start_time=start_1m,
                                end_time=now_ts,
                                limit=1000,
                            )

                            if rows:
                                rows_with_interval = [{**r, "interval": "1"} for r in rows]
                                adapter._persist_klines_to_db(symbol.upper(), rows_with_interval)
                                logger.info(f"[BAR_MAGNIFIER] Loaded {len(rows)} 1m candles for {symbol}")
                    finally:
                        bg_db.close()

                except Exception as e:
                    logger.warning(f"[BAR_MAGNIFIER] Background 1m refresh failed: {e}")

            # Schedule background task (non-blocking)
            asyncio.create_task(refresh_1m_background())

        # ========== BACKGROUND: Refresh 1h data for Volatility and "Precha" protection ==========
        # Only if the requested interval is not already 1h
        if bybit_interval != "60":

            async def refresh_1h_background():
                """Refresh 1h candles in background for volatility calculations."""
                try:
                    from backend.database import SessionLocal

                    bg_db = SessionLocal()
                    try:
                        # Check if 1h data exists
                        h1_count = (
                            bg_db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol.upper(),
                                BybitKlineAudit.interval == "60",
                            )
                            .count()
                        )

                        # Get latest 1h candle
                        h1_latest = (
                            bg_db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol.upper(),
                                BybitKlineAudit.interval == "60",
                            )
                            .order_by(BybitKlineAudit.open_time.desc())
                            .first()
                        )

                        h1_latest_ts = h1_latest.open_time if h1_latest else None

                        # Only update if no data or stale (>2 hours old)
                        should_update = h1_count == 0 or (h1_latest_ts and (now_ts - h1_latest_ts) > 2 * 3600000)

                        if should_update:
                            logger.info(f"[VOLATILITY] Background refresh 1h data for {symbol}")

                            # Fetch last 30 days of 1h data (720 candles) for volatility
                            start_1h = now_ts - (30 * 24 * 60 * 60 * 1000)  # 30 days ago
                            if h1_latest_ts:
                                start_1h = h1_latest_ts - 3600000  # 1 hour overlap

                            rows = await adapter.get_historical_klines(
                                symbol=symbol.upper(),
                                interval="60",
                                start_time=start_1h,
                                end_time=now_ts,
                                limit=1000,
                            )

                            if rows:
                                rows_with_interval = [{**r, "interval": "60"} for r in rows]
                                adapter._persist_klines_to_db(symbol.upper(), rows_with_interval)
                                logger.info(f"[VOLATILITY] Loaded {len(rows)} 1h candles for {symbol}")
                    finally:
                        bg_db.close()

                except Exception as e:
                    logger.warning(f"[VOLATILITY] Background 1h refresh failed: {e}")

            # Schedule background task (non-blocking)
            asyncio.create_task(refresh_1h_background())

        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "new_candles": actual_new,
            "total_count": total_in_db,
            "earliest_datetime": earliest_dt,
            "latest_datetime": latest_dt,
            "status": "success",
            "message": f"Добавлено {actual_new} новых свечей" if actual_new > 0 else "Данные актуальны",
        }

    except Exception as exc:
        logger.exception(f"Failed to refresh data: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# Единый набор таймфреймов: от младшего к старшему (1m → M). Синхронизация выполняется в этом порядке.
ALL_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
ALL_TIMEFRAMES_FULL = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]

# Нахлёст свечей при догрузке (5 для малых TF, меньше для больших — избегаем gaps на границе)
OVERLAP_CANDLES = {
    "1": 5,
    "5": 5,
    "15": 5,
    "30": 5,
    "60": 5,
    "240": 4,
    "D": 3,
    "W": 2,
    "M": 2,
}


def _get_kline_audit_state_sync(symbol: str, interval: str, market_type: str) -> tuple:
    """Sync DB read - run in thread to avoid blocking event loop."""
    from backend.database import SessionLocal

    with SessionLocal() as session:
        latest_row = (
            session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.market_type == market_type,
            )
            .order_by(BybitKlineAudit.open_time.desc())
            .first()
        )
        earliest_row = (
            session.query(BybitKlineAudit)
            .filter(
                BybitKlineAudit.symbol == symbol,
                BybitKlineAudit.interval == interval,
                BybitKlineAudit.market_type == market_type,
            )
            .order_by(BybitKlineAudit.open_time.asc())
            .first()
        )
        latest_ts = latest_row.open_time if latest_row else None
        earliest_ts = earliest_row.open_time if earliest_row else None
        return (latest_ts, earliest_ts)


def _persist_klines_sync(adapter, symbol: str, rows: list, interval: str, market_type: str) -> None:
    """Sync persist - run in thread to avoid blocking event loop."""
    if rows:
        rows_with_interval = [{**r, "interval": interval} for r in rows]
        adapter._persist_klines_to_db(symbol, rows_with_interval, market_type=market_type)


async def _wait_client_disconnect(request: Request, poll_interval: float = 0.5) -> None:
    """Завершается, когда клиент отключился (abort/закрытие вкладки). Освобождает сервер от работы по отменённому запросу."""
    try:
        while True:
            if await request.is_disconnected():
                return
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        pass


@router.post("/symbols/sync-all-tf")
async def sync_all_timeframes(
    request: Request,
    symbol: str = Query(..., description="Trading pair symbol"),
    market_type: str = Query("linear", description="Market type: 'spot' or 'linear'"),
):
    """
    Sync ALL timeframes (1m, 5m, 15m, 30m, 1h, 4h, D, W) for a symbol.

    If symbol doesn't exist in DB - loads all TFs from 2025-01-01.
    If symbol exists - checks freshness and updates stale TFs.

    When client disconnects (e.g. user switched ticker and frontend aborted the request),
    sync is cancelled so the server does not block for 180s on the old symbol.
    """
    from datetime import datetime

    _sync_start = datetime.now(UTC)
    logger.info(f"[SYNC] Request received for {symbol} (market_type={market_type}) at {_sync_start.isoformat()}")

    data_start_ts = DATA_START_TIMESTAMP_MS
    now_ts = int(datetime.now(UTC).timestamp() * 1000)

    symbol = symbol.upper()
    results = {}

    # Interval to milliseconds mapping (1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M)
    interval_ms_map = {
        "1": 60000,
        "5": 300000,
        "15": 900000,
        "30": 1800000,
        "60": 3600000,
        "240": 14400000,
        "D": 86400000,
        "W": 604800000,
        "M": 30 * 86400000,  # ~30 days
    }

    # Freshness thresholds (in ms) - TF value * 2 for tolerance
    freshness_thresholds = {
        "1": 2 * 60000,  # 2 minutes
        "5": 2 * 300000,  # 10 minutes
        "15": 2 * 900000,  # 30 minutes
        "30": 2 * 1800000,  # 1 hour
        "60": 2 * 3600000,  # 2 hours
        "240": 2 * 14400000,  # 8 hours
        "D": 2 * 86400000,  # 2 days
        "W": 2 * 604800000,  # 2 weeks
        "M": 2 * 30 * 86400000,  # 2 months
    }

    try:
        adapter = get_bybit_adapter()

        async def sync_interval(interval: str) -> dict:
            """Sync single interval for given market_type, return status."""
            try:
                # DB read in thread pool — не блокирует event loop
                latest_ts, earliest_ts = await asyncio.to_thread(
                    _get_kline_audit_state_sync, symbol, interval, market_type
                )

                # Determine what needs to be done
                needs_full_load = latest_ts is None
                needs_backfill = earliest_ts and earliest_ts > data_start_ts + 86400000
                threshold = freshness_thresholds.get(interval, 3600000)
                needs_update = latest_ts and (now_ts - latest_ts) > threshold

                new_candles = 0

                if needs_full_load:
                    # Full load from 2025-01-01
                    logger.info(f"[SYNC] Full load {symbol}/{interval} from 2025-01-01")
                    rows = await adapter.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_time=data_start_ts,
                        end_time=now_ts,
                        limit=1000,
                        market_type=market_type,
                    )
                    if rows:
                        await asyncio.to_thread(_persist_klines_sync, adapter, symbol, rows, interval, market_type)
                        new_candles = len(rows)
                    return {"status": "loaded", "new_candles": new_candles}

                if needs_backfill:
                    # Backfill historical data
                    logger.info(f"[SYNC] Backfill {symbol}/{interval} from 2025-01-01")
                    rows = await adapter.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_time=data_start_ts,
                        end_time=earliest_ts - 1,
                        limit=1000,
                        market_type=market_type,
                    )
                    if rows:
                        await asyncio.to_thread(_persist_klines_sync, adapter, symbol, rows, interval, market_type)
                        new_candles += len(rows)

                if needs_update:
                    # Update to current (с нахлёстом свечей — 5 для малых TF, меньше для D/W/M)
                    interval_ms = interval_ms_map.get(interval, 3600000)
                    overlap = OVERLAP_CANDLES.get(interval, 3)
                    start_ts = latest_ts - (interval_ms * overlap)
                    logger.info(f"[SYNC] Update {symbol}/{interval} to current (overlap={overlap})")
                    rows = await adapter.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_time=start_ts,
                        end_time=now_ts,
                        limit=1000,
                        market_type=market_type,
                    )
                    if rows:
                        await asyncio.to_thread(_persist_klines_sync, adapter, symbol, rows, interval, market_type)
                        new_candles += len(rows)
                    return {"status": "updated", "new_candles": new_candles}

                return {"status": "fresh", "new_candles": 0}

            except Exception as e:
                logger.error(f"[SYNC] Error syncing {symbol}/{interval}: {e}")
                return {"status": "error", "error": str(e)}

        # Sync all timeframes with timeout
        import asyncio

        async def sync_with_timeout(tf: str, timeout_sec: int = 30) -> dict:
            """Sync with timeout to prevent hangs."""
            try:
                return await asyncio.wait_for(sync_interval(tf), timeout=timeout_sec)
            except TimeoutError:
                logger.warning(f"[SYNC] Timeout syncing {symbol}/{tf} after {timeout_sec}s")
                return {"status": "timeout", "error": f"Timeout after {timeout_sec}s"}

        # Timeouts per TF — 1m ограничен 45 с, чтобы не блокировать сервер 180 с при переключении тикера
        tf_timeouts = {
            "1": 45,
            "5": 45,
            "15": 30,
            "30": 30,
            "60": 30,
            "240": 45,
            "D": 45,
            "W": 45,
            "M": 60,
        }

        sync_tasks = [asyncio.create_task(sync_with_timeout(tf, tf_timeouts.get(tf, 45))) for tf in ALL_TIMEFRAMES]
        disconnect_task = asyncio.create_task(_wait_client_disconnect(request))
        _elapsed_ms = (datetime.now(UTC) - _sync_start).total_seconds() * 1000
        logger.info(f"[SYNC] Tasks started for {symbol}, elapsed since request: {_elapsed_ms:.0f} ms")

        done, pending = await asyncio.wait(
            sync_tasks + [disconnect_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if disconnect_task in done:
            # Клиент отключился — отменяем синхронизацию, чтобы не блокировать следующий запрос
            for t in sync_tasks:
                if not t.done():
                    t.cancel()
            gathered = await asyncio.gather(*sync_tasks, return_exceptions=True)
            logger.info(f"[SYNC] Client disconnected for {symbol}, sync cancelled")
            tf_results = []
            for r in gathered:
                if isinstance(r, BaseException):
                    tf_results.append({"status": "cancelled", "new_candles": 0})
                else:
                    tf_results.append(r)
        else:
            # Ждём завершения всех TF; отменяем фоновую проверку отключения
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass
            pending_sync = [t for t in sync_tasks if t not in done]
            if pending_sync:
                await asyncio.gather(*pending_sync)
            tf_results = []
            for t in sync_tasks:
                try:
                    tf_results.append(t.result())
                except (asyncio.CancelledError, Exception):
                    tf_results.append({"status": "error", "new_candles": 0})

        for tf, result in zip(ALL_TIMEFRAMES, tf_results, strict=False):
            results[tf] = result

        total_new = sum(r.get("new_candles", 0) for r in tf_results)
        statuses = [r.get("status") for r in tf_results]
        cancelled = sum(1 for s in statuses if s == "cancelled")
        _total_ms = (datetime.now(UTC) - _sync_start).total_seconds() * 1000
        logger.info(f"[SYNC] Complete for {symbol}, total elapsed: {_total_ms:.0f} ms, +{total_new} candles")

        return {
            "symbol": symbol,
            "market_type": market_type,
            "timeframes": results,
            "total_new_candles": total_new,
            "all_fresh": all(s == "fresh" for s in statuses),
            "summary": f"Синхронизировано {len(ALL_TIMEFRAMES)} TF, добавлено {total_new} свечей"
            + (f", отменено при отключении клиента: {cancelled}" if cancelled else ""),
        }

    except Exception as exc:
        logger.exception(f"Failed to sync all timeframes: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/symbols/sync-all-tf-stream")
async def sync_all_timeframes_stream(
    request: Request,
    symbol: str = Query(..., description="Trading pair symbol"),
    market_type: str = Query("linear", description="Market type: 'spot' or 'linear'"),
):
    """
    Stream progress of syncing ALL timeframes using Server-Sent Events (SSE).
    Shows real-time progress as each TF is processed.

    Events format:
    - progress: {tf, step, totalSteps, percent, message, newCandles}
    - complete: {totalNew, results}
    - error: {message}
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    symbol = symbol.upper()
    data_start_ts = DATA_START_TIMESTAMP_MS
    now_ts = int(datetime.now(UTC).timestamp() * 1000)
    total_steps = len(ALL_TIMEFRAMES)

    # Human-readable TF names (1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M)
    tf_names = {
        "1": "1 минута",
        "5": "5 минут",
        "15": "15 минут",
        "30": "30 минут",
        "60": "1 час",
        "240": "4 часа",
        "D": "1 день",
        "W": "1 неделя",
        "M": "1 месяц",
    }

    # Interval to milliseconds mapping
    interval_ms_map = {
        "1": 60000,
        "5": 300000,
        "15": 900000,
        "30": 1800000,
        "60": 3600000,
        "240": 14400000,
        "D": 86400000,
        "W": 604800000,
        "M": 30 * 86400000,
    }

    # Freshness thresholds
    freshness_thresholds = {
        "1": 2 * 60000,
        "5": 2 * 300000,
        "15": 2 * 900000,
        "30": 2 * 1800000,
        "60": 2 * 3600000,
        "240": 2 * 14400000,
        "D": 2 * 86400000,
        "W": 2 * 604800000,
        "M": 2 * 30 * 86400000,
    }

    # Timeout per TF (optimized for faster sync)
    tf_timeouts = {
        "1": 15.0,  # 1m: reduced - only incremental sync, not full backfill
        "5": 20.0,  # 5m: reduced
        "15": 20.0,
        "30": 20.0,
        "60": 20.0,
        "240": 30.0,
        "D": 30.0,
        "W": 30.0,
        "M": 45.0,
    }

    # Max backfill depth per TF (to avoid slow initial loads)
    # For 1m, only backfill 7 days max (10,080 candles)
    # For higher TFs, allow full history
    max_backfill_ms = {
        "1": 7 * 24 * 60 * 60 * 1000,  # 7 days max for 1m
        "5": 30 * 24 * 60 * 60 * 1000,  # 30 days for 5m
        "15": 90 * 24 * 60 * 60 * 1000,  # 90 days for 15m
        "30": 180 * 24 * 60 * 60 * 1000,  # 180 days for 30m
        "60": 365 * 24 * 60 * 60 * 1000,  # 1 year for 60m
    }

    async def event_generator():
        """Generate SSE events for each TF sync."""
        from backend.database import SessionLocal

        results = {}
        total_new = 0

        logger.info(f"[SYNC-STREAM] Starting sync for {symbol}")

        # Сразу отправить первый прогресс, чтобы клиент не ждал (первая загрузка не «зависала»)
        yield f"data: {json.dumps({'event': 'progress', 'tf': '1', 'tfName': '1 минута', 'step': 0, 'totalSteps': total_steps, 'percent': 0, 'message': 'Синхронизация 1m...'})}\n\n"
        await asyncio.sleep(0.01)

        try:
            adapter = get_bybit_adapter()
            db = SessionLocal()

            try:
                for step, tf in enumerate(ALL_TIMEFRAMES, 1):
                    if await request.is_disconnected():
                        logger.info(f"[SYNC-STREAM] Client disconnected for {symbol}, stopping")
                        yield f"data: {json.dumps({'event': 'complete', 'totalNew': total_new, 'results': results, 'message': 'Синхронизация прервана (клиент отключился)', 'cancelled': True})}\n\n"
                        return

                    tf_name = tf_names.get(tf, tf)
                    percent = int((step - 1) / total_steps * 100)

                    # Send progress for starting TF
                    event_data = json.dumps(
                        {
                            "event": "progress",
                            "tf": tf,
                            "tfName": tf_name,
                            "step": step,
                            "totalSteps": total_steps,
                            "percent": percent,
                            "message": f"Синхронизация {tf_name}...",
                        }
                    )
                    logger.debug(f"[SYNC-STREAM] Yielding: {event_data[:100]}")
                    yield f"data: {event_data}\n\n"
                    await asyncio.sleep(0.01)  # Small delay to ensure flush

                    try:
                        # Check current state (filter by market_type for spot/linear)
                        latest_row = (
                            db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol,
                                BybitKlineAudit.interval == tf,
                                BybitKlineAudit.market_type == market_type,
                            )
                            .order_by(BybitKlineAudit.open_time.desc())
                            .first()
                        )

                        earliest_row = (
                            db.query(BybitKlineAudit)
                            .filter(
                                BybitKlineAudit.symbol == symbol,
                                BybitKlineAudit.interval == tf,
                                BybitKlineAudit.market_type == market_type,
                            )
                            .order_by(BybitKlineAudit.open_time.asc())
                            .first()
                        )

                        latest_ts = latest_row.open_time if latest_row else None
                        earliest_ts = earliest_row.open_time if earliest_row else None

                        needs_full_load = latest_ts is None
                        needs_backfill = earliest_ts and earliest_ts > data_start_ts + 86400000
                        threshold = freshness_thresholds.get(tf, 3600000)
                        needs_update = latest_ts and (now_ts - latest_ts) > threshold

                        new_candles = 0

                        if needs_full_load:
                            # Full load with timeout
                            try:
                                rows = await asyncio.wait_for(
                                    adapter.get_historical_klines(
                                        symbol=symbol,
                                        interval=tf,
                                        start_time=data_start_ts,
                                        end_time=now_ts,
                                        limit=1000,
                                        market_type=market_type,
                                    ),
                                    timeout=tf_timeouts.get(tf, 45.0),
                                )
                                if rows:
                                    rows_with_interval = [{**r, "interval": tf} for r in rows]
                                    adapter._persist_klines_to_db(symbol, rows_with_interval, market_type=market_type)
                                    new_candles = len(rows)
                                results[tf] = {"status": "loaded", "new_candles": new_candles}
                            except TimeoutError:
                                logger.warning(f"[SYNC-STREAM] Timeout loading {symbol}/{tf}")
                                results[tf] = {"status": "timeout", "new_candles": 0}

                        elif needs_backfill:
                            # Backfill with timeout - use limited depth for lower TFs
                            try:
                                # Limit backfill depth for low TFs (1m, 5m) to avoid 45s timeouts
                                backfill_start = data_start_ts
                                if tf in max_backfill_ms:
                                    max_depth = max_backfill_ms[tf]
                                    limited_start = earliest_ts - max_depth
                                    backfill_start = max(data_start_ts, limited_start)
                                    if backfill_start > data_start_ts:
                                        logger.info(
                                            f"[SYNC-STREAM] Limited backfill for {symbol}/{tf}: {max_depth // (24 * 60 * 60 * 1000)} days"
                                        )

                                rows = await asyncio.wait_for(
                                    adapter.get_historical_klines(
                                        symbol=symbol,
                                        interval=tf,
                                        start_time=backfill_start,
                                        end_time=earliest_ts - 1,
                                        limit=1000,
                                        market_type=market_type,
                                    ),
                                    timeout=tf_timeouts.get(tf, 30.0),
                                )
                                if rows:
                                    rows_with_interval = [{**r, "interval": tf} for r in rows]
                                    adapter._persist_klines_to_db(symbol, rows_with_interval, market_type=market_type)
                                    new_candles += len(rows)

                                if needs_update:
                                    interval_ms = interval_ms_map.get(tf, 3600000)
                                    overlap = OVERLAP_CANDLES.get(tf, 3)
                                    start_ts = latest_ts - (interval_ms * overlap)
                                    rows = await asyncio.wait_for(
                                        adapter.get_historical_klines(
                                            symbol=symbol,
                                            interval=tf,
                                            start_time=start_ts,
                                            end_time=now_ts,
                                            limit=1000,
                                            market_type=market_type,
                                        ),
                                        timeout=tf_timeouts.get(tf, 30.0),
                                    )
                                    if rows:
                                        rows_with_interval = [{**r, "interval": tf} for r in rows]
                                        adapter._persist_klines_to_db(
                                            symbol, rows_with_interval, market_type=market_type
                                        )
                                        new_candles += len(rows)
                                results[tf] = {"status": "backfilled", "new_candles": new_candles}
                            except TimeoutError:
                                logger.warning(f"[SYNC-STREAM] Timeout backfilling {symbol}/{tf}")
                                results[tf] = {"status": "timeout", "new_candles": new_candles}

                        elif needs_update:
                            # Just update with timeout (переменный нахлёст)
                            try:
                                interval_ms = interval_ms_map.get(tf, 3600000)
                                overlap = OVERLAP_CANDLES.get(tf, 3)
                                start_ts = latest_ts - (interval_ms * overlap)
                                rows = await asyncio.wait_for(
                                    adapter.get_historical_klines(
                                        symbol=symbol,
                                        interval=tf,
                                        start_time=start_ts,
                                        end_time=now_ts,
                                        limit=1000,
                                        market_type=market_type,
                                    ),
                                    timeout=tf_timeouts.get(tf, 30.0),
                                )
                                if rows:
                                    rows_with_interval = [{**r, "interval": tf} for r in rows]
                                    adapter._persist_klines_to_db(symbol, rows_with_interval, market_type=market_type)
                                    new_candles = len(rows)
                                results[tf] = {"status": "updated", "new_candles": new_candles}
                            except TimeoutError:
                                logger.warning(f"[SYNC-STREAM] Timeout updating {symbol}/{tf}")
                                results[tf] = {"status": "timeout", "new_candles": 0}
                        else:
                            results[tf] = {"status": "fresh", "new_candles": 0}

                        total_new += new_candles

                        # Send progress after completing TF
                        percent = int(step / total_steps * 100)
                        status_msg = "✓" if new_candles == 0 else f"+{new_candles}"
                        event_data = json.dumps(
                            {
                                "event": "progress",
                                "tf": tf,
                                "tfName": tf_name,
                                "step": step,
                                "totalSteps": total_steps,
                                "percent": percent,
                                "message": f"{tf_name}: {status_msg}",
                                "newCandles": new_candles,
                                "totalNew": total_new,
                            }
                        )
                        logger.info(f"[SYNC-STREAM] TF {tf} done: {status_msg}")
                        yield f"data: {event_data}\n\n"
                        await asyncio.sleep(0.01)

                    except Exception as e:
                        logger.error(f"[SYNC-STREAM] Error syncing {symbol}/{tf}: {e}")
                        results[tf] = {"status": "error", "error": str(e)}
                        err_percent = int(step / total_steps * 100)
                        yield f"data: {json.dumps({'event': 'progress', 'tf': tf, 'tfName': tf_name, 'step': step, 'totalSteps': total_steps, 'percent': err_percent, 'message': f'{tf_name}: ошибка', 'error': str(e)})}\n\n"

            finally:
                db.close()

            # Send complete event
            logger.info(f"[SYNC-STREAM] Complete: {symbol}, total new={total_new}")
            yield f"data: {json.dumps({'event': 'complete', 'totalNew': total_new, 'results': results, 'message': f'Синхронизировано {len(ALL_TIMEFRAMES)} TF, +{total_new} свечей'})}\n\n"

        except Exception as e:
            logger.exception(f"[SYNC-STREAM] Failed: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/symbols/refresh-data-stream")
async def refresh_symbol_data_stream(
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query(..., description="Timeframe interval (e.g., 30m, 1h)"),
):
    """
    Stream progress of data refresh using Server-Sent Events (SSE).
    Provides real-time progress updates for candle loading.

    Events format:
    - progress: {percent, loaded, total, message}
    - complete: {total_count, new_candles, status}
    - error: {message}
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    # Use centralized config constants
    data_start_ts = DATA_START_TIMESTAMP_MS
    now_ts = int(datetime.now(UTC).timestamp() * 1000)

    # Interval mapping
    interval_map = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
        "1w": "W",
        "1M": "M",
    }
    bybit_interval = interval_map.get(interval, interval)

    # Interval duration in ms
    interval_ms_map = {
        "1": 60000,
        "3": 180000,
        "5": 300000,
        "15": 900000,
        "30": 1800000,
        "60": 3600000,
        "120": 7200000,
        "240": 14400000,
        "360": 21600000,
        "720": 43200000,
        "D": 86400000,
        "W": 604800000,
        "M": 2592000000,
    }
    interval_ms = interval_ms_map.get(bybit_interval, 3600000)

    async def event_generator():
        """Generate SSE events for progress updates."""
        try:
            # Calculate expected total candles from 2025-01-01 to now
            total_time_range = now_ts - data_start_ts
            expected_candles = total_time_range // interval_ms

            # Send initial progress
            yield f"data: {json.dumps({'event': 'progress', 'percent': 0, 'loaded': 0, 'total': expected_candles, 'message': 'Инициализация...'})}\n\n"
            await asyncio.sleep(0.1)

            # Get adapter
            adapter = get_bybit_adapter()

            # Check current DB state
            from backend.database import SessionLocal

            db = SessionLocal()

            try:
                earliest_row = (
                    db.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol.upper(),
                        BybitKlineAudit.interval == bybit_interval,
                    )
                    .order_by(BybitKlineAudit.open_time.asc())
                    .first()
                )
                latest_row = (
                    db.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol.upper(),
                        BybitKlineAudit.interval == bybit_interval,
                    )
                    .order_by(BybitKlineAudit.open_time.desc())
                    .first()
                )

                current_count = (
                    db.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol.upper(),
                        BybitKlineAudit.interval == bybit_interval,
                    )
                    .count()
                )

                earliest_in_db = earliest_row.open_time if earliest_row else None
                latest_in_db = latest_row.open_time if latest_row else None

            finally:
                db.close()

            total_new = 0

            # Determine what needs to be fetched
            if not earliest_in_db:
                # No data - full historical load
                yield f"data: {json.dumps({'event': 'progress', 'percent': 5, 'loaded': 0, 'total': expected_candles, 'message': 'Загрузка истории с 01.01.2025...'})}\n\n"

                # Fetch in batches with progress updates
                current_start = data_start_ts
                batch_size = 1000
                loaded = 0

                while current_start < now_ts:
                    try:
                        rows = await adapter.get_historical_klines(
                            symbol=symbol.upper(),
                            interval=bybit_interval,
                            start_time=current_start,
                            end_time=now_ts,
                            limit=batch_size,
                        )

                        if rows:
                            rows_with_interval = [{**r, "interval": bybit_interval} for r in rows]
                            adapter._persist_klines_to_db(symbol.upper(), rows_with_interval)
                            loaded += len(rows)
                            total_new += len(rows)

                            # Get max time for next batch
                            max_time = max(r.get("open_time", 0) for r in rows)

                            if max_time >= now_ts - interval_ms:
                                # Reached current time
                                break

                            current_start = max_time + 1

                            # Calculate progress
                            percent = min(95, int((loaded / expected_candles) * 100))
                            yield f"data: {json.dumps({'event': 'progress', 'percent': percent, 'loaded': loaded, 'total': expected_candles, 'message': f'Загружено {loaded:,} свечей...'})}\n\n"
                            await asyncio.sleep(0.05)
                        else:
                            break

                    except Exception as e:
                        logger.error(f"Batch fetch error: {e}")
                        break

            else:
                # Data exists - check if backfill needed
                if earliest_in_db > data_start_ts + 86400000:
                    yield f"data: {json.dumps({'event': 'progress', 'percent': 10, 'loaded': current_count, 'total': expected_candles, 'message': 'Догрузка старых данных...'})}\n\n"

                    try:
                        rows = await adapter.get_historical_klines(
                            symbol=symbol.upper(),
                            interval=bybit_interval,
                            start_time=data_start_ts,
                            end_time=earliest_in_db - 1,
                            limit=1000,
                        )
                        if rows:
                            rows_with_interval = [{**r, "interval": bybit_interval} for r in rows]
                            adapter._persist_klines_to_db(symbol.upper(), rows_with_interval)
                            total_new += len(rows)
                    except Exception as e:
                        logger.error(f"Backfill error: {e}")

                # Update to current
                yield f"data: {json.dumps({'event': 'progress', 'percent': 70, 'loaded': current_count + total_new, 'total': expected_candles, 'message': 'Обновление до текущего времени...'})}\n\n"

                if latest_in_db and latest_in_db < now_ts:
                    overlap = OVERLAP_CANDLES.get(bybit_interval, 5)
                    update_start = latest_in_db - (interval_ms * overlap)

                    try:
                        rows = await adapter.get_historical_klines(
                            symbol=symbol.upper(),
                            interval=bybit_interval,
                            start_time=update_start,
                            end_time=now_ts,
                            limit=1000,
                        )
                        if rows:
                            # Count only truly new candles (after latest_in_db)
                            new_rows = [r for r in rows if r.get("open_time", 0) > latest_in_db]

                            rows_with_interval = [{**r, "interval": bybit_interval} for r in rows]
                            adapter._persist_klines_to_db(symbol.upper(), rows_with_interval)
                            # Count only new candles, not duplicates
                            total_new += len(new_rows)
                    except Exception as e:
                        logger.error(f"Update error: {e}")

            # Get final count
            db = SessionLocal()
            try:
                final_count = (
                    db.query(BybitKlineAudit)
                    .filter(
                        BybitKlineAudit.symbol == symbol.upper(),
                        BybitKlineAudit.interval == bybit_interval,
                    )
                    .count()
                )
            finally:
                db.close()

            # Calculate actual new candles by comparing counts
            # This is more accurate than tracking during load (UPSERT may not add duplicates)
            actual_new = max(0, final_count - current_count)

            # Use the more accurate count
            new_candles_count = actual_new if actual_new > 0 else total_new

            # Send completion
            yield f"data: {json.dumps({'event': 'complete', 'percent': 100, 'total_count': final_count, 'new_candles': new_candles_count, 'message': f'Готово! {final_count:,} свечей в базе'})}\n\n"

        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# INSTRUMENT INFO ENDPOINT
# =============================================================================


@router.get("/symbols/{symbol}/instrument-info")
async def get_instrument_info(symbol: str):
    """
    Get trading instrument info including leverage limits and minimum order sizes.

    Returns:
        - maxLeverage: Maximum allowed leverage for this symbol
        - minLeverage: Minimum leverage (usually 1)
        - minNotionalValue: Minimum order value in USDT
        - minOrderQty: Minimum order quantity
        - qtyStep: Order quantity step
        - tickSize: Price tick size
    """
    try:
        adapter = get_bybit_adapter()
        adapter._refresh_instruments_cache()

        sym = symbol.upper()
        if not sym.endswith("USDT"):
            sym = sym + "USDT"

        if sym not in adapter._instruments_cache:
            raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

        instrument = adapter._instruments_cache[sym]

        leverage_filter = instrument.get("leverageFilter", {})
        lot_size_filter = instrument.get("lotSizeFilter", {})
        price_filter = instrument.get("priceFilter", {})

        return {
            "symbol": sym,
            "status": instrument.get("status"),
            "maxLeverage": float(leverage_filter.get("maxLeverage", 100)),
            "minLeverage": float(leverage_filter.get("minLeverage", 1)),
            "leverageStep": float(leverage_filter.get("leverageStep", 0.01)),
            "minNotionalValue": float(lot_size_filter.get("minNotionalValue", 5)),
            "minOrderQty": float(lot_size_filter.get("minOrderQty", 0.001)),
            "maxOrderQty": float(lot_size_filter.get("maxOrderQty", 1000)),
            "qtyStep": float(lot_size_filter.get("qtyStep", 0.001)),
            "tickSize": float(price_filter.get("tickSize", 0.01)),
            "minPrice": float(price_filter.get("minPrice", 0.1)),
            "maxPrice": float(price_filter.get("maxPrice", 999999)),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching instrument info for {symbol}")
        raise HTTPException(status_code=500, detail=str(e))
