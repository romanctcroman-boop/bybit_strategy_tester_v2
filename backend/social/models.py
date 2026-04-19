"""
👥 Social Trading Models

Models for social trading features.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PublicStrategy:
    """Public strategy for sharing"""

    name: str
    description: str
    creator_id: str
    symbol: str
    timeframe: str
    strategy_type: str
    parameters: dict[str, Any]

    # Stats
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0

    # Social
    followers: int = 0
    copies: int = 0
    rating: float = 0.0
    votes: int = 0

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_public: bool = True
    is_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "creator_id": self.creator_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy_type": self.strategy_type,
            "parameters": self.parameters,
            "performance": {
                "total_return": self.total_return,
                "sharpe_ratio": self.sharpe_ratio,
                "max_drawdown": self.max_drawdown,
                "win_rate": self.win_rate,
                "total_trades": self.total_trades,
            },
            "social": {
                "followers": self.followers,
                "copies": self.copies,
                "rating": self.rating,
                "votes": self.votes,
            },
            "created_at": self.created_at.isoformat(),
            "is_public": self.is_public,
            "is_verified": self.is_verified,
        }


@dataclass
class StrategyRating:
    """Strategy rating/vote"""

    strategy_id: str
    user_id: str
    rating: int  # 1-5
    comment: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CopyTrade:
    """Copy trade relationship"""

    strategy_id: str
    follower_id: str
    allocation: float  # Allocation amount
    is_active: bool = True
    copied_trades: int = 0
    total_pnl: float = 0.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.now)
    stopped_at: datetime | None = None


@dataclass
class LeaderboardEntry:
    """Leaderboard entry"""

    user_id: str
    username: str
    rank: int
    total_return: float
    sharpe_ratio: float
    followers: int
    strategies_count: int
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "rank": self.rank,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "followers": self.followers,
            "strategies_count": self.strategies_count,
            "verified": self.verified,
        }
