"""
Strategy Marketplace Database Models.

Provides models for:
- Strategy sharing between users
- Ratings and reviews
- Download tracking
- Strategy versioning
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.database.base import Base


class StrategyVisibility(str, Enum):
    """Strategy visibility options."""

    PRIVATE = "private"
    PUBLIC = "public"
    UNLISTED = "unlisted"  # Accessible via link but not searchable


class MarketplaceStrategy(Base):
    """Published strategy in the marketplace."""

    __tablename__ = "marketplace_strategies"

    id = Column(Integer, primary_key=True, index=True)

    # Owner
    user_id = Column(Integer, index=True, nullable=False)
    username = Column(String(100), nullable=False)

    # Strategy info
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)  # rsi, sma, macd, etc.
    strategy_params = Column(Text, nullable=False)  # JSON
    tags = Column(String(500), nullable=True)  # Comma-separated

    # Performance metrics (from backtest)
    total_return = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    backtest_period = Column(
        String(100), nullable=True
    )  # e.g., "2024-01-01 to 2025-01-01"

    # Marketplace metadata
    visibility = Column(String(20), default=StrategyVisibility.PUBLIC.value)
    version = Column(String(20), default="1.0.0")
    price = Column(Float, default=0.0)  # 0 = free
    currency = Column(String(10), default="USD")

    # Stats
    downloads = Column(Integer, default=0)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Flags
    is_featured = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)  # Verified by admin
    is_active = Column(Boolean, default=True)

    # Relationships
    reviews = relationship(
        "StrategyReview", back_populates="strategy", cascade="all, delete-orphan"
    )
    downloads_log = relationship(
        "StrategyDownload", back_populates="strategy", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MarketplaceStrategy(id={self.id}, name='{self.name}', by={self.username})>"


class StrategyReview(Base):
    """User review for a marketplace strategy."""

    __tablename__ = "strategy_reviews"

    id = Column(Integer, primary_key=True, index=True)

    # References
    strategy_id = Column(
        Integer, ForeignKey("marketplace_strategies.id"), nullable=False
    )
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)

    # Review content
    rating = Column(Integer, nullable=False)  # 1-5
    title = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)

    # Verification
    is_verified_purchase = Column(Boolean, default=False)  # User actually downloaded

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    strategy = relationship("MarketplaceStrategy", back_populates="reviews")

    # Constraints
    __table_args__ = (
        UniqueConstraint("strategy_id", "user_id", name="unique_strategy_review"),
    )

    def __repr__(self):
        return f"<StrategyReview(strategy_id={self.strategy_id}, rating={self.rating})>"


class StrategyDownload(Base):
    """Download tracking for marketplace strategies."""

    __tablename__ = "strategy_downloads"

    id = Column(Integer, primary_key=True, index=True)

    # References
    strategy_id = Column(
        Integer, ForeignKey("marketplace_strategies.id"), nullable=False
    )
    user_id = Column(Integer, nullable=False)

    # Metadata
    version = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Timestamps
    downloaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    strategy = relationship("MarketplaceStrategy", back_populates="downloads_log")

    def __repr__(self):
        return f"<StrategyDownload(strategy_id={self.strategy_id}, user_id={self.user_id})>"


class StrategyLike(Base):
    """User likes for marketplace strategies."""

    __tablename__ = "strategy_likes"

    id = Column(Integer, primary_key=True, index=True)

    # References
    strategy_id = Column(
        Integer, ForeignKey("marketplace_strategies.id"), nullable=False
    )
    user_id = Column(Integer, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("strategy_id", "user_id", name="unique_strategy_like"),
    )

    def __repr__(self):
        return f"<StrategyLike(strategy_id={self.strategy_id}, user_id={self.user_id})>"
