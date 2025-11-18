from datetime import UTC, datetime
from enum import Enum

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

router = APIRouter()


class BotStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    awaiting_signal = "awaiting_signal"
    awaiting_start = "awaiting_start"
    awaiting_stop = "awaiting_stop"
    error = "error"


class Bot(BaseModel):
    id: str
    name: str
    strategy: str
    symbols: list[str]
    capital_allocated: float
    status: BotStatus
    created_at: datetime


class BotsListResponse(BaseModel):
    items: list[Bot]
    total: int


# In-memory mock storage (process-local)
_BOTS: dict[str, Bot] = {}


def _seed():
    if _BOTS:
        return
    now = datetime.now(UTC)
    examples = [
        Bot(
            id="bot_1",
            name="BTC Scalper",
            strategy="scalper_v1",
            symbols=["BTCUSDT"],
            capital_allocated=1000.0,
            status=BotStatus.running,
            created_at=now,
        ),
        Bot(
            id="bot_2",
            name="ETH Swing",
            strategy="swing_v2",
            symbols=["ETHUSDT"],
            capital_allocated=750.0,
            status=BotStatus.awaiting_signal,
            created_at=now,
        ),
        Bot(
            id="bot_3",
            name="Multi L2",
            strategy="grid_v1",
            symbols=["SOLUSDT", "DOGEUSDT"],
            capital_allocated=500.0,
            status=BotStatus.awaiting_start,
            created_at=now,
        ),
    ]
    for b in examples:
        _BOTS[b.id] = b


@router.get("/", response_model=BotsListResponse)
async def list_bots(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> BotsListResponse:
    _seed()
    all_items = list(_BOTS.values())
    total = len(all_items)
    items = all_items[offset : offset + limit]
    return BotsListResponse(items=items, total=total)


@router.get("/{bot_id}", response_model=Bot)
async def get_bot(bot_id: str = Path(..., description="Bot ID")) -> Bot:
    _seed()
    bot = _BOTS.get(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


class ActionResponse(BaseModel):
    ok: bool
    status: BotStatus | None = None
    message: str | None = None


@router.post("/{bot_id}/start", response_model=ActionResponse)
async def start_bot(bot_id: str) -> ActionResponse:
    _seed()
    bot = _BOTS.get(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    bot.status = BotStatus.awaiting_start
    _BOTS[bot_id] = bot
    return ActionResponse(ok=True, status=bot.status, message="Start requested")


@router.post("/{bot_id}/stop", response_model=ActionResponse)
async def stop_bot(bot_id: str) -> ActionResponse:
    _seed()
    bot = _BOTS.get(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    bot.status = BotStatus.awaiting_stop
    _BOTS[bot_id] = bot
    return ActionResponse(ok=True, status=bot.status, message="Stop requested")


@router.post("/{bot_id}/delete", response_model=ActionResponse)
async def delete_bot(bot_id: str) -> ActionResponse:
    _seed()
    if bot_id not in _BOTS:
        raise HTTPException(status_code=404, detail="Bot not found")
    del _BOTS[bot_id]
    return ActionResponse(ok=True, message="Bot deleted")
