"""
Tickers API — список тикеров Bybit для Strategy Builder (Properties Symbol).

Соответствует Bybit API v5:
- GET /v5/market/tickers — тикеры по категории (linear/spot)
- GET /v5/market/instruments-info — список инструментов (symbols), пагинация cursor

См.: https://bybit-exchange.github.io/docs/v5/market/tickers
     https://bybit-exchange.github.io/docs/v5/market/instrument
"""
import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/v1", tags=["tickers"])
logger = logging.getLogger(__name__)


@router.get("/marketdata/symbols-list", include_in_schema=False)
async def get_symbols_list(
    request: Request,
    category: str = Query("linear", description="linear (USDT perpetual) or spot"),
):
    """
    Список тикеров Bybit по типу рынка. Для выпадающего списка Symbol в Properties.
    Ответ из кэша (startup) или запрос к Bybit GET /v5/market/instruments-info.
    """
    if category not in ("linear", "spot"):
        category = "linear"
    try:
        cache = getattr(request.app.state, "symbols_cache", None)
        if cache and isinstance(cache, dict) and cache.get(category):
            return {"symbols": cache[category], "category": category}
        from backend.services.adapters.bybit import BybitAdapter

        adapter = BybitAdapter(
            api_key=os.environ.get("BYBIT_API_KEY"),
            api_secret=os.environ.get("BYBIT_API_SECRET"),
        )
        loop = asyncio.get_event_loop()
        symbols = await loop.run_in_executor(
            None, lambda: adapter.get_symbols_list(category=category)
        )
        if cache is not None and isinstance(cache, dict):
            cache[category] = symbols
        return {"symbols": symbols or [], "category": category}
    except Exception as exc:
        logger.exception("get_symbols_list failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refresh-tickers", include_in_schema=False)
async def refresh_tickers(request: Request):
    """
    Принудительно загрузить тикеры с Bybit (linear + spot) в кэш.
    Вызов по кнопке «Обновить список» в Properties.
    При сбое одной категории (сеть/DNS) не затираем кэш — обновляем только успешные.
    """
    from backend.services.adapters.bybit import BybitAdapter

    if not hasattr(request.app.state, "symbols_cache"):
        request.app.state.symbols_cache = {}
    cache = request.app.state.symbols_cache

    adapter = BybitAdapter(
        api_key=os.environ.get("BYBIT_API_KEY"),
        api_secret=os.environ.get("BYBIT_API_SECRET"),
    )
    loop = asyncio.get_event_loop()

    linear: list = []
    spot: list = []
    try:
        linear = await loop.run_in_executor(
            None, lambda: adapter.get_symbols_list(category="linear", trading_only=True)
        )
    except Exception as exc:
        logger.warning("refresh_tickers linear failed: %s", exc)
    if linear:
        cache["linear"] = linear

    try:
        spot = await loop.run_in_executor(
            None, lambda: adapter.get_symbols_list(category="spot", trading_only=True)
        )
    except Exception as exc:
        logger.warning("refresh_tickers spot failed: %s", exc)
    if spot:
        cache["spot"] = spot

    return {
        "ok": True,
        "linear": len(cache.get("linear", [])),
        "spot": len(cache.get("spot", [])),
    }
