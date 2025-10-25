from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import ApiListResponse, StrategyCreate, StrategyOut, StrategyUpdate


def _get_data_service():
    try:
        from backend.services.data_service import DataService

        return DataService
    except Exception:
        return None


router = APIRouter()


@router.get("/", response_model=ApiListResponse[StrategyOut])
def list_strategies(
    is_active: bool | None = Query(None),
    strategy_type: str | None = Query(None),
    limit: int = 100,
    offset: int = 0,
):
    """List strategies

    Note: bybit-specific interactions (Bybit API v5) are handled in separate service adapters.
    This endpoint returns stored strategy configurations.
    """
    DS = _get_data_service()
    if DS is None:
        # backend models/database not available — return empty list response
        return {"items": [], "total": 0}
    with DS() as ds:
        items = ds.get_strategies(
            is_active=is_active, strategy_type=strategy_type, limit=limit, offset=offset
        )
        total = ds.count_strategies(is_active=is_active, strategy_type=strategy_type)

        def to_iso(d):
            out = d.__dict__.copy()
            for k, v in list(out.items()):
                if isinstance(v, datetime):
                    out[k] = v.isoformat()
            return out

        return {"items": [to_iso(i) for i in items], "total": total}


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        s = ds.get_strategy(strategy_id)
        if not s:
            raise HTTPException(status_code=404, detail="Strategy not found")
        d = s.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.post("/", response_model=StrategyOut)
def create_strategy(payload: StrategyCreate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        s = ds.create_strategy(**payload.model_dump())
        d = s.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return d


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, payload: StrategyUpdate):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        s = ds.update_strategy(
            strategy_id, **{k: v for k, v in payload.model_dump(exclude_none=True).items()}
        )
        if not s:
            raise HTTPException(status_code=404, detail="Strategy not found")
        d = s.__dict__.copy()
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int):
    DS = _get_data_service()
    if DS is None:
        raise HTTPException(
            status_code=501, detail="Backend database not configured in this environment"
        )
    with DS() as ds:
        ok = ds.delete_strategy(strategy_id)
        return {"success": ok}
