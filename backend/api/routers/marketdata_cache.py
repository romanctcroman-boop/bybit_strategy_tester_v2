"""
Market Data Cache Management Endpoints

Extracted from marketdata.py for better maintainability.
Handles prime and reset operations for working sets.
"""

import logging

from fastapi import APIRouter, Form, HTTPException

from backend.services.candle_cache import CANDLE_CACHE

router = APIRouter(tags=["Market Data Cache"])
logger = logging.getLogger(__name__)


@router.post("/bybit/prime")
def prime_working_sets(
    symbol: str = Form(..., description="Instrument symbol, e.g. BTCUSDT"),
    intervals: str = Form(
        "1,5,15,60", description="Comma-separated list: e.g. '1,5,15,60,240,D'"
    ),
    load_limit: int = Form(
        1000, description="Initial load size per interval (max 1000)"
    ),
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
                data = CANDLE_CACHE.load_initial(
                    symbol, itv, load_limit=load_limit, persist=True
                )
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
    reload: int = Form(
        1, description="If 1, reload from remote after reset; if 0, just clear"
    ),
    load_limit: int = Form(
        1000, description="Load size per interval when reload=1 (max 1000)"
    ),
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
                    data = CANDLE_CACHE.reset(symbol, itv, reload=True)
                    if load_limit and load_limit != CANDLE_CACHE.LOAD_LIMIT:
                        data = CANDLE_CACHE.load_initial(
                            symbol, itv, load_limit=load_limit, persist=True
                        )
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
