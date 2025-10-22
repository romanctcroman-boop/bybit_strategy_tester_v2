from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel


router = APIRouter()


class ActiveDeal(BaseModel):
    id: str
    bot_id: str
    symbol: str
    entry_price: float
    quantity: float
    next_open_price: float
    current_price: Optional[float] = None
    pnl_abs: float
    pnl_pct: float
    opened_at: datetime


class DealsListResponse(BaseModel):
    items: List[ActiveDeal]
    total: int


_DEALS: Dict[str, ActiveDeal] = {}


def _seed():
    if _DEALS:
        return
    now = datetime.now(timezone.utc)
    ex = [
        ActiveDeal(
            id="deal_1",
            bot_id="bot_1",
            symbol="BTCUSDT",
            entry_price=60000.0,
            quantity=0.02,
            next_open_price=60350.0,
            current_price=60200.0,
            pnl_abs=4.0,
            pnl_pct=0.33,
            opened_at=now,
        ),
        ActiveDeal(
            id="deal_2",
            bot_id="bot_3",
            symbol="SOLUSDT",
            entry_price=150.0,
            quantity=1.2,
            next_open_price=149.0,
            current_price=148.5,
            pnl_abs=-1.8,
            pnl_pct=-1.2,
            opened_at=now,
        ),
    ]
    for d in ex:
        _DEALS[d.id] = d


@router.get("/", response_model=DealsListResponse)
async def list_active_deals(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DealsListResponse:
    _seed()
    all_items = list(_DEALS.values())
    total = len(all_items)
    items = all_items[offset : offset + limit]
    return DealsListResponse(items=items, total=total)


class ActionResponse(BaseModel):
    ok: bool
    action: str
    message: Optional[str] = None


def _get_deal_or_404(deal_id: str) -> ActiveDeal:
    d = _DEALS.get(deal_id)
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    return d


@router.post("/{deal_id}/close", response_model=ActionResponse)
async def close_deal(deal_id: str = Path(...)) -> ActionResponse:
    _seed()
    _get_deal_or_404(deal_id)
    # For mock, just remove it
    del _DEALS[deal_id]
    return ActionResponse(ok=True, action="close", message="Deal closed")


@router.post("/{deal_id}/average", response_model=ActionResponse)
async def average_deal(deal_id: str = Path(...)) -> ActionResponse:
    _seed()
    d = _get_deal_or_404(deal_id)
    # Mock: adjust entry slightly towards current
    if d.current_price is not None:
        d.entry_price = round((d.entry_price + d.current_price) / 2, 4)
        _DEALS[deal_id] = d
    return ActionResponse(ok=True, action="average", message="Averaged position")


@router.post("/{deal_id}/cancel", response_model=ActionResponse)
async def cancel_deal(deal_id: str = Path(...)) -> ActionResponse:
    _seed()
    _get_deal_or_404(deal_id)
    # Mock: remove from active as cancelled
    del _DEALS[deal_id]
    return ActionResponse(ok=True, action="cancel", message="Deal cancelled")
