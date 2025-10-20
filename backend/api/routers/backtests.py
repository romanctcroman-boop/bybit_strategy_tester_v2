from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone

def _get_data_service():
    try:
        from backend.services.data_service import DataService
        return DataService
    except Exception:
        return None

router = APIRouter()


@router.get("/", response_model=List[dict])
def list_backtests(strategy_id: Optional[int] = Query(None), symbol: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = 100, offset: int = 0, order_by: str = "created_at", order_dir: str = "desc"):
    DS = _get_data_service()
    if DS is None:
        return []
    with DS() as ds:
        items = ds.get_backtests(strategy_id=strategy_id, symbol=symbol, status=status, limit=limit, offset=offset, order_by=order_by, order_dir=order_dir)
        return [i.__dict__ for i in items]


@router.get("/{backtest_id}")
def get_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.get_backtest(backtest_id)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return bt.__dict__


@router.post("/")
def create_backtest(payload: dict):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    # payload must contain strategy_id, symbol, timeframe, start_date, end_date, initial_capital
    with DS() as ds:
        bt = ds.create_backtest(**payload)
        return bt.__dict__


@router.put("/{backtest_id}")
def update_backtest(backtest_id: int, payload: dict):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.update_backtest(backtest_id, **payload)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return bt.__dict__


@router.post("/{backtest_id}/claim")
def claim_backtest(backtest_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    now = datetime.now(timezone.utc)
    with DS() as ds:
        res = ds.claim_backtest_to_run(backtest_id, now)
        return res


@router.post("/{backtest_id}/results")
def update_results(backtest_id: int, payload: dict):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        bt = ds.update_backtest_results(backtest_id, **payload)
        if not bt:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return bt.__dict__
