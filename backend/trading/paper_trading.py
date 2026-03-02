"""
📈 Paper Trading Engine

Paper trading simulation for testing strategies.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PaperTrade:
    """Paper trade representation"""

    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    entry_price: float
    exit_price: float | None = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: datetime | None = None
    id: str = field(default_factory=lambda: f"paper_{datetime.now().timestamp()}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


@dataclass
class PaperTradeResult:
    """Paper trading result"""

    success: bool
    trade: PaperTrade | None = None
    error: str | None = None
    balance: float = 0.0
    equity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "trade": self.trade.to_dict() if self.trade else None,
            "error": self.error,
            "balance": self.balance,
            "equity": self.equity,
        }


class PaperTradingEngine:
    """
    Paper trading engine for strategy testing.

    Симулирует trading на real-time данных без реальных денег.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission: float = 0.0007,
    ):
        """
        Args:
            initial_balance: Initial virtual balance
            commission: Commission rate
        """
        self.initial_balance = initial_balance
        self.commission = commission

        # Current state
        self.balance = initial_balance
        self.equity = initial_balance

        # Positions
        self.positions: dict[str, float] = {}  # symbol -> quantity

        # Open trades
        self.open_trades: dict[str, PaperTrade] = {}

        # Trade history
        self.trade_history: list[PaperTrade] = []

        # Current prices
        self.prices: dict[str, float] = {}

    def update_price(self, symbol: str, price: float):
        """
        Update current price.

        Args:
            symbol: Symbol
            price: Current price
        """
        self.prices[symbol] = price

        # Update equity
        self._update_equity()

    def _update_equity(self):
        """Update equity based on current positions"""
        unrealized_pnl = 0.0

        for symbol, quantity in self.positions.items():
            if symbol in self.prices and symbol in self.open_trades:
                trade = self.open_trades[symbol]
                current_price = self.prices[symbol]

                if trade.side == "buy":
                    pnl = (current_price - trade.entry_price) * quantity
                else:
                    pnl = (trade.entry_price - current_price) * quantity

                unrealized_pnl += pnl

        self.equity = self.balance + unrealized_pnl

    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None = None,
    ) -> PaperTradeResult:
        """
        Open position.

        Args:
            symbol: Symbol
            side: 'buy' or 'sell'
            quantity: Quantity
            price: Price (uses current if None)

        Returns:
            PaperTradeResult
        """
        # Get current price
        if price is None:
            if symbol not in self.prices:
                return PaperTradeResult(
                    success=False,
                    error=f"No price for {symbol}",
                    balance=self.balance,
                    equity=self.equity,
                )
            price = self.prices[symbol]

        # Check balance
        required_margin = price * quantity

        if side == "buy" and required_margin > self.balance:
            return PaperTradeResult(
                success=False,
                error="Insufficient balance",
                balance=self.balance,
                equity=self.equity,
            )

        # Create trade
        trade = PaperTrade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
        )

        # Update state
        self.positions[symbol] = quantity
        self.open_trades[symbol] = trade

        # Deduct margin for buy
        if side == "buy":
            self.balance -= required_margin

        logger.info(f"Paper trade opened: {trade.id} - {side} {quantity} {symbol} @ {price}")

        return PaperTradeResult(
            success=True,
            trade=trade,
            balance=self.balance,
            equity=self.equity,
        )

    def close_position(
        self,
        symbol: str,
        price: float | None = None,
    ) -> PaperTradeResult:
        """
        Close position.

        Args:
            symbol: Symbol
            price: Price (uses current if None)

        Returns:
            PaperTradeResult
        """
        if symbol not in self.open_trades:
            return PaperTradeResult(
                success=False,
                error=f"No open position for {symbol}",
                balance=self.balance,
                equity=self.equity,
            )

        # Get current price
        if price is None:
            if symbol not in self.prices:
                return PaperTradeResult(
                    success=False,
                    error=f"No price for {symbol}",
                    balance=self.balance,
                    equity=self.equity,
                )
            price = self.prices[symbol]

        trade = self.open_trades[symbol]
        quantity = self.positions[symbol]

        # Calculate PnL
        pnl = (price - trade.entry_price) * quantity if trade.side == "buy" else (trade.entry_price - price) * quantity

        # Commission
        commission = price * quantity * self.commission
        pnl -= commission

        # Update trade
        trade.exit_price = price
        trade.pnl = pnl
        trade.pnl_percent = pnl / (trade.entry_price * quantity) if trade.entry_price > 0 else 0
        trade.closed_at = datetime.now()

        # Update balance
        if trade.side == "buy":
            self.balance += price * quantity + pnl
        else:
            self.balance += pnl

        # Remove position
        del self.positions[symbol]
        del self.open_trades[symbol]

        # Add to history
        self.trade_history.append(trade)

        # Update equity
        self._update_equity()

        logger.info(f"Paper trade closed: {trade.id} - PnL: {pnl:.2f}")

        return PaperTradeResult(
            success=True,
            trade=trade,
            balance=self.balance,
            equity=self.equity,
        )

    def get_positions(self) -> dict[str, dict[str, Any]]:
        """Get current positions"""
        positions = {}

        for symbol, quantity in self.positions.items():
            if symbol in self.open_trades:
                trade = self.open_trades[symbol]
                current_price = self.prices.get(symbol, 0)

                if trade.side == "buy":
                    unrealized_pnl = (current_price - trade.entry_price) * quantity
                else:
                    unrealized_pnl = (trade.entry_price - current_price) * quantity

                positions[symbol] = {
                    "quantity": quantity,
                    "side": trade.side,
                    "entry_price": trade.entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_percent": unrealized_pnl / (trade.entry_price * quantity)
                    if trade.entry_price > 0
                    else 0,
                }

        return positions

    def get_performance(self) -> dict[str, Any]:
        """Get trading performance"""
        if not self.trade_history:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "max_drawdown": 0.0,
            }

        winning = [t for t in self.trade_history if t.pnl > 0]
        losing = [t for t in self.trade_history if t.pnl < 0]

        total_pnl = sum(t.pnl for t in self.trade_history)
        avg_pnl = total_pnl / len(self.trade_history)

        win_rate = len(winning) / len(self.trade_history)

        # Calculate max drawdown
        peak = self.initial_balance
        max_dd = 0.0

        for trade in self.trade_history:
            balance_change = trade.pnl

            peak = max(peak, self.initial_balance + balance_change)
            dd = (peak - (self.initial_balance + balance_change)) / peak
            max_dd = max(max_dd, dd)

        return {
            "total_trades": len(self.trade_history),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "max_drawdown": max_dd,
            "final_balance": self.balance,
            "final_equity": self.equity,
            "return_percent": (self.equity - self.initial_balance) / self.initial_balance * 100,
        }

    def reset(self):
        """Reset engine state"""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.positions.clear()
        self.open_trades.clear()
        self.trade_history.clear()
        self.prices.clear()

        logger.info("Paper trading engine reset")
