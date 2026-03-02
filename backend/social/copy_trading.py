"""
👥 Copy Trading Engine

Copy trading functionality.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CopyPosition:
    """Copied position"""

    original_trade_id: str
    strategy_id: str
    follower_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    copy_ratio: float
    pnl: float = 0.0
    closed: bool = False


class CopyTradingEngine:
    """
    Copy trading engine.

    Features:
    - Auto-copy trades
    - Allocation management
    - Risk limits
    - PnL tracking
    """

    def __init__(self):
        # Active copy relationships
        self.copy_relationships: dict[str, dict[str, Any]] = {}

        # Copied positions
        self.positions: list[CopyPosition] = []

        # Copy history
        self.history: list[dict[str, Any]] = []

    def start_copy(
        self,
        follower_id: str,
        strategy_id: str,
        allocation: float,
        copy_ratio: float = 1.0,
        max_positions: int = 10,
    ) -> bool:
        """
        Start copying a strategy.

        Args:
            follower_id: Follower user ID
            strategy_id: Strategy to copy
            allocation: Allocation amount
            copy_ratio: Ratio to copy (0.0-1.0)
            max_positions: Maximum concurrent positions

        Returns:
            True if started successfully
        """
        key = f"{follower_id}:{strategy_id}"

        self.copy_relationships[key] = {
            "follower_id": follower_id,
            "strategy_id": strategy_id,
            "allocation": allocation,
            "copy_ratio": copy_ratio,
            "max_positions": max_positions,
            "started_at": datetime.now(),
            "is_active": True,
            "copied_trades": 0,
            "total_pnl": 0.0,
        }

        logger.info(f"Started copy trading: {follower_id} copying {strategy_id}")
        return True

    def stop_copy(self, follower_id: str, strategy_id: str) -> bool:
        """Stop copying a strategy"""
        key = f"{follower_id}:{strategy_id}"

        if key in self.copy_relationships:
            self.copy_relationships[key]["is_active"] = False
            self.copy_relationships[key]["stopped_at"] = datetime.now()

            logger.info(f"Stopped copy trading: {follower_id} stopped copying {strategy_id}")
            return True

        return False

    def copy_trade(
        self,
        strategy_id: str,
        trade_data: dict[str, Any],
    ) -> list[CopyPosition]:
        """
        Copy a trade to all followers.

        Args:
            strategy_id: Strategy ID
            trade_data: Original trade data

        Returns:
            List of copied positions
        """
        copied_positions = []

        # Find all active followers
        for _key, relationship in self.copy_relationships.items():
            if not relationship["is_active"]:
                continue

            if relationship["strategy_id"] != strategy_id:
                continue

            follower_id = relationship["follower_id"]
            relationship["allocation"]
            copy_ratio = relationship["copy_ratio"]

            # Calculate copy quantity
            original_quantity = trade_data.get("quantity", 0)
            copy_quantity = original_quantity * copy_ratio

            # Create copied position
            position = CopyPosition(
                original_trade_id=trade_data.get("id", ""),
                strategy_id=strategy_id,
                follower_id=follower_id,
                symbol=trade_data.get("symbol", ""),
                side=trade_data.get("side", ""),
                quantity=copy_quantity,
                entry_price=trade_data.get("entry_price", 0),
                copy_ratio=copy_ratio,
            )

            self.positions.append(position)
            copied_positions.append(position)

            # Update relationship stats
            relationship["copied_trades"] += 1

        logger.info(f"Copied trade to {len(copied_positions)} followers")
        return copied_positions

    def update_position_pnl(self, position_id: str, pnl: float):
        """Update position PnL"""
        for position in self.positions:
            if id(position) == position_id:
                position.pnl = pnl

                # Update relationship total
                for _key, relationship in self.copy_relationships.items():
                    if relationship["follower_id"] == position.follower_id:
                        relationship["total_pnl"] += pnl
                break

    def get_follower_positions(self, follower_id: str) -> list[CopyPosition]:
        """Get all positions for a follower"""
        return [p for p in self.positions if p.follower_id == follower_id and not p.closed]

    def get_copy_stats(self, follower_id: str) -> dict[str, Any]:
        """Get copy trading stats for a follower"""
        positions = self.get_follower_positions(follower_id)

        total_pnl = sum(p.pnl for p in positions)
        active_positions = len(positions)

        return {
            "follower_id": follower_id,
            "active_positions": active_positions,
            "total_pnl": total_pnl,
            "total_copied_trades": len([p for p in self.positions if p.follower_id == follower_id]),
        }
