"""
👥 Leaderboard

Strategy and trader leaderboard.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Leaderboard:
    """
    Leaderboard for strategies and traders.

    Features:
    - Top traders by return
    - Top strategies by Sharpe
    - Most followed
    - Verified traders
    """

    def __init__(self):
        # In-memory storage (use database in production)
        self.strategies: dict[str, Any] = {}
        self.traders: dict[str, Any] = {}

    def add_strategy(self, strategy_data: dict[str, Any]):
        """Add strategy to leaderboard"""
        strategy_id = strategy_data.get("id")
        if strategy_id:
            self.strategies[strategy_id] = strategy_data
            logger.info(f"Added strategy {strategy_id} to leaderboard")

    def add_trader(self, trader_data: dict[str, Any]):
        """Add trader to leaderboard"""
        trader_id = trader_data.get("user_id")
        if trader_id:
            self.traders[trader_id] = trader_data
            logger.info(f"Added trader {trader_id} to leaderboard")

    def get_top_traders(
        self,
        by: str = "return",
        limit: int = 10,
        period: str = "all_time",
    ) -> list[dict[str, Any]]:
        """
        Get top traders.

        Args:
            by: Sort by ('return', 'sharpe', 'followers')
            limit: Number of results
            period: Time period

        Returns:
            List of top traders
        """
        traders_list = list(self.traders.values())

        # Sort
        if by == "return":
            traders_list.sort(key=lambda x: x.get("total_return", 0), reverse=True)
        elif by == "sharpe":
            traders_list.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
        elif by == "followers":
            traders_list.sort(key=lambda x: x.get("followers", 0), reverse=True)

        # Add rank
        for i, trader in enumerate(traders_list[:limit]):
            trader["rank"] = i + 1

        return traders_list[:limit]

    def get_top_strategies(
        self,
        by: str = "sharpe",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top strategies.

        Args:
            by: Sort by ('sharpe', 'return', 'copies', 'rating')
            limit: Number of results

        Returns:
            List of top strategies
        """
        strategies_list = list(self.strategies.values())

        # Sort
        if by == "sharpe":
            strategies_list.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
        elif by == "return":
            strategies_list.sort(key=lambda x: x.get("total_return", 0), reverse=True)
        elif by == "copies":
            strategies_list.sort(key=lambda x: x.get("copies", 0), reverse=True)
        elif by == "rating":
            strategies_list.sort(key=lambda x: x.get("rating", 0), reverse=True)

        # Add rank
        for i, strategy in enumerate(strategies_list[:limit]):
            strategy["rank"] = i + 1

        return strategies_list[:limit]

    def get_most_followed(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most followed traders"""
        return self.get_top_traders(by="followers", limit=limit)

    def get_verified_traders(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get verified traders"""
        verified = [t for t in self.traders.values() if t.get("verified", False)]
        verified.sort(key=lambda x: x.get("total_return", 0), reverse=True)

        for i, trader in enumerate(verified[:limit]):
            trader["rank"] = i + 1

        return verified[:limit]

    def get_user_rank(self, user_id: str) -> dict[str, Any] | None:
        """Get user's rank"""
        if user_id not in self.traders:
            return None

        trader = self.traders[user_id]
        all_traders = list(self.traders.values())
        all_traders.sort(key=lambda x: x.get("total_return", 0), reverse=True)

        rank = next((i + 1 for i, t in enumerate(all_traders) if t.get("user_id") == user_id), None)

        return {
            "user_id": user_id,
            "rank": rank,
            "total_return": trader.get("total_return", 0),
            "sharpe_ratio": trader.get("sharpe_ratio", 0),
        }
