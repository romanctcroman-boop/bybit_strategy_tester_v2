"""
👥 Social Trading API Router

REST API for social trading:
- GET /social/strategies - List public strategies
- POST /social/strategies - Create public strategy
- GET /social/leaderboard - Get leaderboard
- POST /social/copy - Start copy trading
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["Social Trading"])

# In-memory storage
_strategies: dict[str, Any] = {}
_leaderboard_data: list[dict[str, Any]] = []


class CreateStrategyRequest(BaseModel):
    """Create public strategy request"""

    name: str
    description: str
    symbol: str
    timeframe: str
    strategy_type: str
    parameters: dict[str, Any]


class StrategyResponse(BaseModel):
    """Strategy response"""

    id: str
    name: str
    description: str
    symbol: str
    timeframe: str
    performance: dict[str, float]
    social: dict[str, int]
    created_at: str


class LeaderboardResponse(BaseModel):
    """Leaderboard response"""

    top_traders: list[dict[str, Any]]
    top_strategies: list[dict[str, Any]]
    most_followed: list[dict[str, Any]]


class CopyTradingRequest(BaseModel):
    """Copy trading request"""

    strategy_id: str
    allocation: float = Field(..., gt=0)
    copy_ratio: float = Field(default=1.0, ge=0, le=1)


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    limit: int = 20,
    sort_by: str = "sharpe",
):
    """List public strategies"""
    strategies = list(_strategies.values())

    # Sort
    if sort_by == "sharpe":
        strategies.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
    elif sort_by == "return":
        strategies.sort(key=lambda x: x.get("total_return", 0), reverse=True)
    elif sort_by == "followers":
        strategies.sort(key=lambda x: x.get("followers", 0), reverse=True)

    return strategies[:limit]


@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(request: CreateStrategyRequest):
    """Create public strategy"""
    from backend.social.models import PublicStrategy

    strategy = PublicStrategy(
        name=request.name,
        description=request.description,
        creator_id="user_123",  # In production, get from auth
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_type=request.strategy_type,
        parameters=request.parameters,
    )

    _strategies[strategy.id] = strategy.to_dict()

    logger.info(f"Created public strategy: {strategy.id}")

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        symbol=strategy.symbol,
        timeframe=strategy.timeframe,
        performance={
            "total_return": strategy.total_return,
            "sharpe_ratio": strategy.sharpe_ratio,
            "max_drawdown": strategy.max_drawdown,
            "win_rate": strategy.win_rate,
        },
        social={
            "followers": strategy.followers,
            "copies": strategy.copies,
            "rating": strategy.rating,
        },
        created_at=strategy.created_at.isoformat(),
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(limit: int = 10):
    """Get leaderboard"""
    from backend.social.leaderboard import Leaderboard

    leaderboard = Leaderboard()

    # Add mock data
    leaderboard.add_trader(
        {
            "user_id": "trader_1",
            "username": "CryptoKing",
            "total_return": 0.85,
            "sharpe_ratio": 2.5,
            "followers": 1250,
            "verified": True,
        }
    )

    return LeaderboardResponse(
        top_traders=leaderboard.get_top_traders(limit=limit),
        top_strategies=leaderboard.get_top_strategies(limit=limit),
        most_followed=leaderboard.get_most_followed(limit=limit),
    )


@router.post("/copy")
async def start_copy_trading(request: CopyTradingRequest):
    """Start copy trading"""
    from backend.social.copy_trading import CopyTradingEngine

    engine = CopyTradingEngine()

    success = engine.start_copy(
        follower_id="user_456",  # In production, get from auth
        strategy_id=request.strategy_id,
        allocation=request.allocation,
        copy_ratio=request.copy_ratio,
    )

    return {
        "success": success,
        "strategy_id": request.strategy_id,
        "allocation": request.allocation,
        "copy_ratio": request.copy_ratio,
    }
