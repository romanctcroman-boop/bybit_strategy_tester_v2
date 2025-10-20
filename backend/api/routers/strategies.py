from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

def _get_data_service():
    try:
        from backend.services.data_service import DataService
        return DataService
    except Exception:
        return None

router = APIRouter()


@router.get("/", response_model=List[dict])
def list_strategies(is_active: Optional[bool] = Query(None), strategy_type: Optional[str] = Query(None), limit: int = 100, offset: int = 0):
    """List strategies

    Note: bybit-specific interactions (Bybit API v5) are handled in separate service adapters.
    This endpoint returns stored strategy configurations.
    """
    DS = _get_data_service()
    if DS is None:
        # backend models/database not available in this environment — return placeholder
        return []
    with DS() as ds:
        items = ds.get_strategies(is_active=is_active, strategy_type=strategy_type, limit=limit, offset=offset)
        return [item.__dict__ for item in items]


@router.get("/{strategy_id}")
def get_strategy(strategy_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        s = ds.get_strategy(strategy_id)
        if not s:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return s.__dict__


@router.post("/")
def create_strategy(payload: dict):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        s = ds.create_strategy(**payload)
        return s.__dict__


@router.put("/{strategy_id}")
def update_strategy(strategy_id: int, payload: dict):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        s = ds.update_strategy(strategy_id, **payload)
        if not s:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return s.__dict__


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(status_code=501, detail="Backend database not configured in this environment")
    with DS() as ds:
        ok = ds.delete_strategy(strategy_id)
        return {"success": ok}
