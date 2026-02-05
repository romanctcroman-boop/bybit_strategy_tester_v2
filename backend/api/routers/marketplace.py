"""
Strategy Marketplace API Router.

Endpoints for:
- Browse and search strategies
- Publish strategies
- Download strategies
- Rate and review strategies
- Like/unlike strategies
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models.marketplace import (
    MarketplaceStrategy,
    StrategyDownload,
    StrategyLike,
    StrategyReview,
    StrategyVisibility,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketplace", tags=["Strategy Marketplace"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class PublishStrategyRequest(BaseModel):
    """Request to publish a strategy."""

    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    strategy_type: str = Field(..., description="Strategy type: rsi, sma, macd, etc.")
    strategy_params: dict[str, Any] = Field(..., description="Strategy parameters")
    tags: list[str] = Field(default_factory=list, max_length=10)
    visibility: str = Field(default="public")
    version: str = Field(default="1.0.0")

    # Performance metrics (optional, from backtest)
    total_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    profit_factor: float | None = None
    total_trades: int | None = None
    backtest_period: str | None = None


class StrategyResponse(BaseModel):
    """Strategy response model."""

    id: int
    name: str
    description: str | None
    strategy_type: str
    username: str
    visibility: str
    version: str
    tags: list[str]

    # Performance
    total_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    win_rate: float | None
    profit_factor: float | None
    total_trades: int | None
    backtest_period: str | None

    # Stats
    downloads: int
    views: int
    likes: int
    rating_avg: float
    rating_count: int

    # Flags
    is_featured: bool
    is_verified: bool

    # Timestamps
    created_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}


class StrategyDetailResponse(StrategyResponse):
    """Detailed strategy response with params."""

    strategy_params: dict[str, Any]
    reviews: list[dict]


class ReviewRequest(BaseModel):
    """Request to review a strategy."""

    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(None, max_length=200)
    comment: str | None = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    """Review response model."""

    id: int
    username: str
    rating: int
    title: str | None
    comment: str | None
    is_verified_purchase: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MarketplaceStatsResponse(BaseModel):
    """Marketplace statistics."""

    total_strategies: int
    total_downloads: int
    total_reviews: int
    featured_count: int
    top_rated_count: int
    categories: dict[str, int]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_current_user_id() -> int:
    """Get current user ID (placeholder - implement with auth)."""
    # TODO: Implement proper authentication
    return 1


def get_current_username() -> str:
    """Get current username (placeholder - implement with auth)."""
    # TODO: Implement proper authentication
    return "demo_user"


def strategy_to_response(strategy: MarketplaceStrategy) -> dict:
    """Convert strategy model to response dict."""
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "strategy_type": strategy.strategy_type,
        "username": strategy.username,
        "visibility": strategy.visibility,
        "version": strategy.version,
        "tags": strategy.tags.split(",") if strategy.tags else [],
        "total_return": strategy.total_return,
        "sharpe_ratio": strategy.sharpe_ratio,
        "max_drawdown": strategy.max_drawdown,
        "win_rate": strategy.win_rate,
        "profit_factor": strategy.profit_factor,
        "total_trades": strategy.total_trades,
        "backtest_period": strategy.backtest_period,
        "downloads": strategy.downloads,
        "views": strategy.views,
        "likes": strategy.likes,
        "rating_avg": strategy.rating_avg,
        "rating_count": strategy.rating_count,
        "is_featured": strategy.is_featured,
        "is_verified": strategy.is_verified,
        "created_at": strategy.created_at,
        "published_at": strategy.published_at,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    db: Session = Depends(get_db),
    search: str | None = Query(None, description="Search by name or description"),
    strategy_type: str | None = Query(None, description="Filter by strategy type"),
    sort_by: str = Query(
        "downloads", description="Sort by: downloads, rating, newest, return"
    ),
    min_rating: float | None = Query(None, ge=0, le=5),
    featured_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List marketplace strategies with filtering and sorting.
    """
    query = db.query(MarketplaceStrategy).filter(
        MarketplaceStrategy.is_active == True,  # noqa: E712
        MarketplaceStrategy.visibility == StrategyVisibility.PUBLIC.value,
    )

    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (MarketplaceStrategy.name.ilike(search_pattern))
            | (MarketplaceStrategy.description.ilike(search_pattern))
            | (MarketplaceStrategy.tags.ilike(search_pattern))
        )

    if strategy_type:
        query = query.filter(MarketplaceStrategy.strategy_type == strategy_type)

    if min_rating is not None:
        query = query.filter(MarketplaceStrategy.rating_avg >= min_rating)

    if featured_only:
        query = query.filter(MarketplaceStrategy.is_featured == True)  # noqa: E712

    # Apply sorting
    if sort_by == "downloads":
        query = query.order_by(desc(MarketplaceStrategy.downloads))
    elif sort_by == "rating":
        query = query.order_by(desc(MarketplaceStrategy.rating_avg))
    elif sort_by == "newest":
        query = query.order_by(desc(MarketplaceStrategy.published_at))
    elif sort_by == "return":
        query = query.order_by(desc(MarketplaceStrategy.total_return))
    else:
        query = query.order_by(desc(MarketplaceStrategy.downloads))

    # Paginate
    strategies = query.offset(offset).limit(limit).all()

    return [strategy_to_response(s) for s in strategies]


@router.get("/strategies/{strategy_id}", response_model=StrategyDetailResponse)
async def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed strategy information including params.
    """
    strategy = (
        db.query(MarketplaceStrategy)
        .filter(
            MarketplaceStrategy.id == strategy_id,
            MarketplaceStrategy.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Increment view count
    strategy.views += 1
    db.commit()

    # Get reviews
    reviews = (
        db.query(StrategyReview)
        .filter(StrategyReview.strategy_id == strategy_id)
        .order_by(desc(StrategyReview.created_at))
        .limit(10)
        .all()
    )

    response = strategy_to_response(strategy)
    response["strategy_params"] = json.loads(strategy.strategy_params)
    response["reviews"] = [
        {
            "id": r.id,
            "username": r.username,
            "rating": r.rating,
            "title": r.title,
            "comment": r.comment,
            "is_verified_purchase": r.is_verified_purchase,
            "created_at": r.created_at,
        }
        for r in reviews
    ]

    return response


@router.post("/strategies", response_model=StrategyResponse)
async def publish_strategy(
    request: PublishStrategyRequest,
    db: Session = Depends(get_db),
):
    """
    Publish a new strategy to the marketplace.
    """
    user_id = get_current_user_id()
    username = get_current_username()

    strategy = MarketplaceStrategy(
        user_id=user_id,
        username=username,
        name=request.name,
        description=request.description,
        strategy_type=request.strategy_type,
        strategy_params=json.dumps(request.strategy_params),
        tags=",".join(request.tags) if request.tags else None,
        visibility=request.visibility,
        version=request.version,
        total_return=request.total_return,
        sharpe_ratio=request.sharpe_ratio,
        max_drawdown=request.max_drawdown,
        win_rate=request.win_rate,
        profit_factor=request.profit_factor,
        total_trades=request.total_trades,
        backtest_period=request.backtest_period,
        published_at=datetime.now(UTC)
        if request.visibility == "public"
        else None,
    )

    db.add(strategy)
    db.commit()
    db.refresh(strategy)

    logger.info(f"Strategy published: {strategy.id} by {username}")
    return strategy_to_response(strategy)


@router.post("/strategies/{strategy_id}/download")
async def download_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
):
    """
    Download a strategy (get full params).
    """
    strategy = (
        db.query(MarketplaceStrategy)
        .filter(
            MarketplaceStrategy.id == strategy_id,
            MarketplaceStrategy.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    user_id = get_current_user_id()

    # Log download
    download = StrategyDownload(
        strategy_id=strategy_id,
        user_id=user_id,
        version=strategy.version,
    )
    db.add(download)

    # Increment counter
    strategy.downloads += 1
    db.commit()

    return {
        "strategy_type": strategy.strategy_type,
        "strategy_params": json.loads(strategy.strategy_params),
        "version": strategy.version,
        "name": strategy.name,
    }


@router.post("/strategies/{strategy_id}/review", response_model=ReviewResponse)
async def review_strategy(
    strategy_id: int,
    request: ReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Add or update a review for a strategy.
    """
    strategy = (
        db.query(MarketplaceStrategy)
        .filter(MarketplaceStrategy.id == strategy_id)
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    user_id = get_current_user_id()
    username = get_current_username()

    # Check if user already reviewed
    existing = (
        db.query(StrategyReview)
        .filter(
            StrategyReview.strategy_id == strategy_id,
            StrategyReview.user_id == user_id,
        )
        .first()
    )

    # Check if user downloaded
    has_downloaded = (
        db.query(StrategyDownload)
        .filter(
            StrategyDownload.strategy_id == strategy_id,
            StrategyDownload.user_id == user_id,
        )
        .first()
        is not None
    )

    if existing:
        # Update existing review
        existing.rating = request.rating
        existing.title = request.title
        existing.comment = request.comment
        existing.updated_at = datetime.now(UTC)
        review = existing
    else:
        # Create new review
        review = StrategyReview(
            strategy_id=strategy_id,
            user_id=user_id,
            username=username,
            rating=request.rating,
            title=request.title,
            comment=request.comment,
            is_verified_purchase=has_downloaded,
        )
        db.add(review)

    # Update strategy rating
    all_reviews = (
        db.query(StrategyReview).filter(StrategyReview.strategy_id == strategy_id).all()
    )

    if all_reviews:
        strategy.rating_avg = sum(r.rating for r in all_reviews) / len(all_reviews)
        strategy.rating_count = len(all_reviews)

    db.commit()
    db.refresh(review)

    return review


@router.post("/strategies/{strategy_id}/like")
async def like_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
):
    """
    Like or unlike a strategy.
    """
    strategy = (
        db.query(MarketplaceStrategy)
        .filter(MarketplaceStrategy.id == strategy_id)
        .first()
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    user_id = get_current_user_id()

    existing = (
        db.query(StrategyLike)
        .filter(
            StrategyLike.strategy_id == strategy_id,
            StrategyLike.user_id == user_id,
        )
        .first()
    )

    if existing:
        # Unlike
        db.delete(existing)
        strategy.likes -= 1
        action = "unliked"
    else:
        # Like
        like = StrategyLike(strategy_id=strategy_id, user_id=user_id)
        db.add(like)
        strategy.likes += 1
        action = "liked"

    db.commit()

    return {"action": action, "likes": strategy.likes}


@router.get("/stats", response_model=MarketplaceStatsResponse)
async def get_marketplace_stats(
    db: Session = Depends(get_db),
):
    """
    Get marketplace statistics.
    """
    total_strategies = (
        db.query(func.count(MarketplaceStrategy.id))
        .filter(
            MarketplaceStrategy.is_active == True,  # noqa: E712
            MarketplaceStrategy.visibility == StrategyVisibility.PUBLIC.value,
        )
        .scalar()
    )

    total_downloads = db.query(func.sum(MarketplaceStrategy.downloads)).scalar() or 0

    total_reviews = db.query(func.count(StrategyReview.id)).scalar()

    featured_count = (
        db.query(func.count(MarketplaceStrategy.id))
        .filter(
            MarketplaceStrategy.is_featured == True,  # noqa: E712
        )
        .scalar()
    )

    top_rated_count = (
        db.query(func.count(MarketplaceStrategy.id))
        .filter(
            MarketplaceStrategy.rating_avg >= 4.0,
        )
        .scalar()
    )

    # Category counts
    categories = (
        db.query(
            MarketplaceStrategy.strategy_type,
            func.count(MarketplaceStrategy.id).label("count"),
        )
        .filter(
            MarketplaceStrategy.is_active == True,  # noqa: E712
        )
        .group_by(MarketplaceStrategy.strategy_type)
        .all()
    )

    return MarketplaceStatsResponse(
        total_strategies=total_strategies,
        total_downloads=total_downloads,
        total_reviews=total_reviews,
        featured_count=featured_count,
        top_rated_count=top_rated_count,
        categories={c.strategy_type: c.count for c in categories},
    )


@router.get("/categories")
async def get_categories(
    db: Session = Depends(get_db),
):
    """
    Get available strategy categories with counts.
    """
    categories = (
        db.query(
            MarketplaceStrategy.strategy_type,
            func.count(MarketplaceStrategy.id).label("count"),
        )
        .filter(
            MarketplaceStrategy.is_active == True,  # noqa: E712
            MarketplaceStrategy.visibility == StrategyVisibility.PUBLIC.value,
        )
        .group_by(MarketplaceStrategy.strategy_type)
        .all()
    )

    return [
        {"type": c.strategy_type, "count": c.count, "label": c.strategy_type.upper()}
        for c in categories
    ]
