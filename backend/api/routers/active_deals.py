"""
Active Deals Router - Manages active trading deals and positions
"""

from fastapi import APIRouter

router = APIRouter(prefix="/active-deals", tags=["active-deals"])


@router.get("/")
async def get_active_deals():
    """Get list of active trading deals"""
    return {"deals": [], "total": 0}


@router.get("/{deal_id}")
async def get_deal(deal_id: str):
    """Get details of a specific deal"""
    return {"deal_id": deal_id, "status": "not_found"}
