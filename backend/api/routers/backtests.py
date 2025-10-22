from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from backend.api.schemas import BacktestOut, TradeOut, ApiListResponse, BacktestCreate, BacktestUpdate, BacktestResultsUpdate, BacktestClaimResponse

def _get_data_service():
    try:
        from backend.services.data_service import DataService
        return DataService
    except Exception:
        return None

router = APIRouter()


@router.get("/", response_model=ApiListResponse[BacktestOut])
def list_backtests(strategy_id: Optional[int] = Query(None), symbol: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = 100, offset: int = 0, order_by: str = "created_at", order_dir: str = "desc"):
    DS = _get_data_service()
    if DS is None:
        return {"items": [], "total": 0}
    with DS() as ds:
        items = ds.get_backtests(strategy_id=strategy_id, symbol=symbol, status=status, limit=limit, offset=offset, order_by=order_by, order_dir=order_dir)
        total = ds.count_backtests(strategy_id=strategy_id, symbol=symbol, status=status)

        def to_iso(d):
            out = d.__dict__.copy()
            for k, v in list(out.items()):
                if isinstance(v, datetime):
                    out[k] = v.isoformat()
            return out

    return {"items": [to_iso(i) for i in items], "total": total}


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.post("/", response_model=BacktestOut)
def create_backtest(payload: BacktestCreate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    # payload must contain strategy_id, symbol, timeframe, start_date, end_date, initial_capital
    with DS() as ds:
        bt = ds.create_backtest(**payload.model_dump())
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.put("/{backtest_id}", response_model=BacktestOut)
def update_backtest(backtest_id: int, payload: BacktestUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.update_backtest(backtest_id, **{k: v for k, v in payload.model_dump(exclude_none=True).items()})
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.post("/{backtest_id}/claim", response_model=BacktestClaimResponse)
def claim_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    now = datetime.now(timezone.utc)
    with DS() as ds:
        res = ds.claim_backtest_to_run(backtest_id, now)
        # Pydantic-free serialization: ensure any datetimes in nested objects are ISO strings
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
    return {k: convert(v) for k, v in res.items()}  # type: ignore


@router.post("/{backtest_id}/results", response_model=BacktestOut)
def update_results(backtest_id: int, payload: BacktestResultsUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.update_backtest_results(backtest_id, **payload.model_dump())
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        d = bt.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.get("/{backtest_id}/trades", response_model=List[TradeOut])
def list_trades(backtest_id: int, side: Optional[str] = Query(None, description="buy|sell or LONG|SHORT"), limit: int = 1000, offset: int = 0):
    """Return backtest trades normalized for frontend schema.

    Maps internal fields to:
      - price := entry_price
      - qty   := quantity
      - side  LONG/SHORT -> buy/sell
    """
    DS = _get_data_service()
    if DS is None:
        return []
    # Normalize side filter to internal representation if provided
    side_norm: Optional[str] = None
    if side:
        up = side.upper()
        if up in ("LONG", "SHORT"):
            side_norm = up
        elif side.lower() in ("buy", "sell"):
            side_norm = "LONG" if side.lower() == "buy" else "SHORT"
    with DS() as ds:
        items = ds.get_trades(backtest_id=backtest_id, side=side_norm, limit=limit, offset=offset)
        out = []
        for t in items:
            d = t.__dict__.copy()
            # map fields to frontend expectations
            price = d.get('entry_price')
            qty = d.get('quantity')
            side_v = d.get('side')
            if isinstance(side_v, str):
                side_out = 'buy' if side_v.upper() == 'LONG' else 'sell' if side_v.upper() == 'SHORT' else side_v.lower()
            else:
                side_out = 'buy'
            out.append({
                'id': d.get('id'),
                'backtest_id': d.get('backtest_id'),
                'entry_time': d.get('entry_time').isoformat() if d.get('entry_time') else None,
                'exit_time': d.get('exit_time').isoformat() if d.get('exit_time') else None,
                'price': price,
                'qty': qty,
                'side': side_out,
                'pnl': d.get('pnl'),
                'created_at': d.get('created_at').isoformat() if d.get('created_at') else None,
            })
    return out
