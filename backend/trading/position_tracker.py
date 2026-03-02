"""
📈 Position Tracker

Track open positions and PnL.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position representation"""

    symbol: str
    quantity: float
    entry_price: float
    side: str  # 'long' or 'short'
    opened_at: datetime = field(default_factory=datetime.now)
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "side": self.side,
            "opened_at": self.opened_at.isoformat(),
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


class PositionTracker:
    """
    Track open positions and calculate PnL.
    """

    def __init__(self):
        """Initialize position tracker"""
        self.positions: dict[str, Position] = {}
        self.closed_positions: list[Position] = []

    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        side: str,
    ) -> Position:
        """
        Open position.

        Args:
            symbol: Symbol
            quantity: Quantity
            entry_price: Entry price
            side: 'long' or 'short'

        Returns:
            Position
        """
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            side=side,
        )

        self.positions[symbol] = position

        logger.info(f"Position opened: {side} {quantity} {symbol} @ {entry_price}")

        return position

    def close_position(
        self,
        symbol: str,
        exit_price: float,
    ) -> Position | None:
        """
        Close position.

        Args:
            symbol: Symbol
            exit_price: Exit price

        Returns:
            Closed position or None
        """
        if symbol not in self.positions:
            logger.warning(f"No position for {symbol}")
            return None

        position = self.positions[symbol]

        # Calculate realized PnL
        if position.side == "long":
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity

        position.realized_pnl = pnl
        position.current_price = exit_price

        # Move to closed
        self.closed_positions.append(position)
        del self.positions[symbol]

        logger.info(f"Position closed: {symbol} PnL: {pnl:.2f}")

        return position

    def update_price(self, symbol: str, price: float):
        """
        Update current price.

        Args:
            symbol: Symbol
            price: Current price
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = price

            # Calculate unrealized PnL
            if position.side == "long":
                pnl = (price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - price) * position.quantity

            position.unrealized_pnl = pnl

    def get_position(self, symbol: str) -> Position | None:
        """Get position by symbol"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> dict[str, Position]:
        """Get all open positions"""
        return self.positions.copy()

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL"""
        return sum(p.unrealized_pnl for p in self.positions.values())

    def get_total_realized_pnl(self) -> float:
        """Get total realized PnL"""
        return sum(p.realized_pnl for p in self.closed_positions)

    def get_performance(self) -> dict[str, Any]:
        """Get position performance"""
        open_pnl = self.get_total_unrealized_pnl()
        closed_pnl = self.get_total_realized_pnl()

        return {
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed_positions),
            "unrealized_pnl": open_pnl,
            "realized_pnl": closed_pnl,
            "total_pnl": open_pnl + closed_pnl,
        }
