"""
Paper Trading Service.

Simulates real-time trading without real money:
- Virtual portfolio management
- Real-time price feeds integration
- Order execution simulation
- P&L tracking
- Position management
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, Enum):
    """Position side."""

    LONG = "long"
    SHORT = "short"


@dataclass
class PaperOrder:
    """Paper trading order."""

    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    price: float | None = None  # For limit orders
    stop_price: float | None = None  # For stop orders
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    filled_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reduce_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "qty": self.qty,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_qty": self.filled_qty,
            "filled_price": self.filled_price,
            "created_at": self.created_at.isoformat(),
            "reduce_only": self.reduce_only,
        }


@dataclass
class PaperPosition:
    """Paper trading position."""

    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    leverage: float = 1.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    liquidation_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def notional_value(self) -> float:
        """Position notional value."""
        return self.size * self.entry_price

    @property
    def margin_used(self) -> float:
        """Margin used for position."""
        return self.notional_value / self.leverage

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        if self.side == PositionSide.LONG:
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size

    def calculate_pnl_percent(self, current_price: float) -> float:
        """Calculate P&L percentage."""
        pnl = self.calculate_pnl(current_price)
        return (pnl / self.margin_used) * 100 if self.margin_used > 0 else 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "size": self.size,
            "entry_price": self.entry_price,
            "leverage": self.leverage,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "notional_value": self.notional_value,
            "margin_used": self.margin_used,
            "liquidation_price": self.liquidation_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at.isoformat(),
        }


@dataclass
class PaperTrade:
    """Executed paper trade."""

    id: str
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: float
    fee: float
    pnl: float = 0.0
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "qty": self.qty,
            "price": self.price,
            "fee": self.fee,
            "pnl": self.pnl,
            "executed_at": self.executed_at.isoformat(),
        }


@dataclass
class PaperAccount:
    """Paper trading account."""

    initial_balance: float
    balance: float
    equity: float
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def available_balance(self) -> float:
        return self.balance - self.margin_used

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def total_return(self) -> float:
        return ((self.equity - self.initial_balance) / self.initial_balance) * 100

    def to_dict(self) -> dict:
        return {
            "initial_balance": self.initial_balance,
            "balance": self.balance,
            "equity": self.equity,
            "available_balance": self.available_balance,
            "margin_used": self.margin_used,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_return": self.total_return,
        }


class PaperTradingEngine:
    """
    Paper trading engine for simulated trading.

    Features:
    - Virtual balance management
    - Market/Limit order execution
    - Position tracking
    - P&L calculation
    - Slippage simulation
    - Fee simulation
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        fee_rate: float = 0.0007,  # 0.07% taker fee
        slippage_rate: float = 0.0001,  # 0.01% slippage
        default_leverage: float = 1.0,
    ):
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.default_leverage = default_leverage

        # Account state
        self.account = PaperAccount(
            initial_balance=initial_balance,
            balance=initial_balance,
            equity=initial_balance,
        )

        # Trading state
        self.positions: dict[str, PaperPosition] = {}
        self.orders: dict[str, PaperOrder] = {}
        self.pending_orders: list[PaperOrder] = []
        self.trades: list[PaperTrade] = []
        self.equity_curve: list[tuple[datetime, float]] = []

        # Callbacks
        self._on_order_filled: list[Callable] = []
        self._on_position_update: list[Callable] = []
        self._on_price_update: list[Callable] = []

        # Current prices
        self._prices: dict[str, float] = {}

        # Record initial equity
        self._record_equity()

    def on_order_filled(self, callback: Callable) -> None:
        """Register callback for order fill events."""
        self._on_order_filled.append(callback)

    def on_position_update(self, callback: Callable) -> None:
        """Register callback for position updates."""
        self._on_position_update.append(callback)

    def update_price(self, symbol: str, price: float) -> None:
        """
        Update price and check pending orders.

        Should be called on each price tick.
        """
        old_price = self._prices.get(symbol)
        self._prices[symbol] = price

        # Update position P&L
        if symbol in self.positions:
            position = self.positions[symbol]
            position.unrealized_pnl = position.calculate_pnl(price)

            # Check stop loss / take profit
            self._check_position_exits(position, price)

        # Check pending orders
        self._check_pending_orders(symbol, price, old_price)

        # Update account equity
        self._update_account_equity()

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
        stop_price: float | None = None,
        reduce_only: bool = False,
        leverage: float | None = None,
    ) -> PaperOrder:
        """
        Place a paper trading order.

        Args:
            symbol: Trading pair
            side: Buy or sell
            qty: Order quantity
            order_type: Market, limit, stop
            price: Limit price (for limit orders)
            stop_price: Stop trigger price
            reduce_only: Only reduce position
            leverage: Position leverage

        Returns:
            Created order
        """
        order = PaperOrder(
            id=str(uuid4())[:8],
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            stop_price=stop_price,
            reduce_only=reduce_only,
            metadata={"leverage": leverage or self.default_leverage},
        )

        self.orders[order.id] = order

        # Execute market orders immediately
        if order_type == OrderType.MARKET:
            current_price = self._prices.get(symbol)
            if current_price:
                self._execute_order(order, current_price)
            else:
                order.status = OrderStatus.REJECTED
                logger.warning(f"Order rejected: no price for {symbol}")
        else:
            # Add to pending orders
            self.pending_orders.append(order)
            logger.info(
                f"Pending order created: {order.id} {side.value} {qty} {symbol}"
            )

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self.orders.get(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(UTC)

        if order in self.pending_orders:
            self.pending_orders.remove(order)

        logger.info(f"Order cancelled: {order_id}")
        return True

    def close_position(
        self, symbol: str, qty: float | None = None
    ) -> PaperOrder | None:
        """
        Close a position (fully or partially).

        Args:
            symbol: Symbol to close
            qty: Quantity to close (None = full position)

        Returns:
            Closing order or None
        """
        position = self.positions.get(symbol)
        if not position:
            return None

        close_qty = qty or position.size
        close_side = (
            OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        )

        return self.place_order(
            symbol=symbol,
            side=close_side,
            qty=close_qty,
            order_type=OrderType.MARKET,
            reduce_only=True,
        )

    def set_stop_loss(self, symbol: str, price: float) -> bool:
        """Set stop loss for position."""
        if symbol not in self.positions:
            return False
        self.positions[symbol].stop_loss = price
        return True

    def set_take_profit(self, symbol: str, price: float) -> bool:
        """Set take profit for position."""
        if symbol not in self.positions:
            return False
        self.positions[symbol].take_profit = price
        return True

    def get_account_summary(self) -> dict:
        """Get account summary."""
        return {
            "account": self.account.to_dict(),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "pending_orders": len(self.pending_orders),
            "total_trades": len(self.trades),
        }

    def get_trade_history(self, limit: int = 100) -> list[dict]:
        """Get recent trade history."""
        return [t.to_dict() for t in self.trades[-limit:]]

    def get_equity_curve(self) -> list[dict]:
        """Get equity curve data."""
        return [
            {"timestamp": ts.isoformat(), "equity": eq} for ts, eq in self.equity_curve
        ]

    def reset(self) -> None:
        """Reset the paper trading engine."""
        self.account = PaperAccount(
            initial_balance=self.account.initial_balance,
            balance=self.account.initial_balance,
            equity=self.account.initial_balance,
        )
        self.positions.clear()
        self.orders.clear()
        self.pending_orders.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self._record_equity()
        logger.info("Paper trading engine reset")

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _execute_order(self, order: PaperOrder, price: float) -> None:
        """Execute an order at given price."""
        # Apply slippage for market orders
        if order.order_type == OrderType.MARKET:
            if order.side == OrderSide.BUY:
                price *= 1 + self.slippage_rate
            else:
                price *= 1 - self.slippage_rate

        # Calculate fee
        notional = order.qty * price
        fee = notional * self.fee_rate

        # Check balance for new positions
        leverage = order.metadata.get("leverage", self.default_leverage)
        required_margin = notional / leverage

        if not order.reduce_only:
            if required_margin > self.account.available_balance:
                order.status = OrderStatus.REJECTED
                logger.warning("Order rejected: insufficient margin")
                return

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_qty = order.qty
        order.filled_price = price
        order.updated_at = datetime.now(UTC)

        # Create trade record
        trade = PaperTrade(
            id=str(uuid4())[:8],
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=price,
            fee=fee,
        )

        # Update position
        pnl = self._update_position(order, price, leverage)
        trade.pnl = pnl

        # Update account
        self.account.balance -= fee
        self.account.realized_pnl += pnl

        if pnl > 0:
            self.account.winning_trades += 1
        elif pnl < 0:
            self.account.losing_trades += 1

        self.account.total_trades += 1

        # Record trade
        self.trades.append(trade)

        # Update equity
        self._update_account_equity()
        self._record_equity()

        # Callbacks
        for callback in self._on_order_filled:
            try:
                callback(order, trade)
            except Exception as e:
                logger.error(f"Order filled callback error: {e}")

        logger.info(
            f"Order filled: {order.id} {order.side.value} {order.qty} {order.symbol} "
            f"@ {price:.2f} (fee: {fee:.4f}, pnl: {pnl:.2f})"
        )

    def _update_position(
        self,
        order: PaperOrder,
        price: float,
        leverage: float,
    ) -> float:
        """Update position based on order. Returns realized P&L."""
        symbol = order.symbol
        existing = self.positions.get(symbol)

        pnl = 0.0

        if existing:
            # Determine if adding to or closing position
            is_same_direction = (
                order.side == OrderSide.BUY and existing.side == PositionSide.LONG
            ) or (order.side == OrderSide.SELL and existing.side == PositionSide.SHORT)

            if is_same_direction:
                # Add to position (average entry)
                total_size = existing.size + order.qty
                existing.entry_price = (
                    existing.entry_price * existing.size + price * order.qty
                ) / total_size
                existing.size = total_size
            else:
                # Close/reduce position
                close_size = min(existing.size, order.qty)
                pnl = existing.calculate_pnl(price) * (close_size / existing.size)

                # Release margin
                released_margin = (
                    close_size * existing.entry_price
                ) / existing.leverage
                self.account.balance += released_margin + pnl

                remaining = existing.size - close_size
                if remaining <= 0:
                    # Position fully closed
                    del self.positions[symbol]

                    # Open opposite position with remaining qty
                    excess = order.qty - close_size
                    if excess > 0 and not order.reduce_only:
                        self._create_position(order, price, excess, leverage)
                else:
                    existing.size = remaining
        else:
            # New position
            if not order.reduce_only:
                self._create_position(order, price, order.qty, leverage)

        # Update margin used
        self._update_margin_used()

        # Position update callbacks
        for callback in self._on_position_update:
            try:
                callback(symbol, self.positions.get(symbol))
            except Exception as e:
                logger.error(f"Position update callback error: {e}")

        return pnl

    def _create_position(
        self,
        order: PaperOrder,
        price: float,
        size: float,
        leverage: float,
    ) -> None:
        """Create a new position."""
        side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT

        # Calculate liquidation price
        if side == PositionSide.LONG:
            liq_price = price * (1 - 1 / leverage * 0.95)  # 95% margin used
        else:
            liq_price = price * (1 + 1 / leverage * 0.95)

        position = PaperPosition(
            symbol=order.symbol,
            side=side,
            size=size,
            entry_price=price,
            leverage=leverage,
            liquidation_price=liq_price,
        )

        self.positions[order.symbol] = position

        # Deduct margin
        margin = (size * price) / leverage
        self.account.balance -= margin

    def _check_pending_orders(
        self,
        symbol: str,
        current_price: float,
        old_price: float | None,
    ) -> None:
        """Check and execute pending orders."""
        if old_price is None:
            return

        executed = []

        for order in self.pending_orders:
            if order.symbol != symbol:
                continue

            should_execute = False
            exec_price = current_price

            if order.order_type == OrderType.LIMIT:
                # Limit buy: execute when price <= limit
                # Limit sell: execute when price >= limit
                if (
                    order.side == OrderSide.BUY
                    and order.price is not None
                    and current_price <= order.price
                ) or (
                    order.side == OrderSide.SELL
                    and order.price is not None
                    and current_price >= order.price
                ):
                    should_execute = True
                    exec_price = order.price

            elif order.order_type == OrderType.STOP_MARKET:
                # Stop buy: execute when price >= stop
                # Stop sell: execute when price <= stop
                if (
                    order.side == OrderSide.BUY
                    and order.stop_price is not None
                    and current_price >= order.stop_price
                ) or (
                    order.side == OrderSide.SELL
                    and order.stop_price is not None
                    and current_price <= order.stop_price
                ):
                    should_execute = True

            elif order.order_type == OrderType.TAKE_PROFIT_MARKET:
                # TP buy (short close): execute when price <= tp
                # TP sell (long close): execute when price >= tp
                if (
                    order.side == OrderSide.BUY
                    and order.stop_price is not None
                    and current_price <= order.stop_price
                ) or (
                    order.side == OrderSide.SELL
                    and order.stop_price is not None
                    and current_price >= order.stop_price
                ):
                    should_execute = True

            if should_execute:
                self._execute_order(order, exec_price)
                executed.append(order)

        # Remove executed orders
        for order in executed:
            self.pending_orders.remove(order)

    def _check_position_exits(self, position: PaperPosition, price: float) -> None:
        """Check stop loss and take profit."""
        symbol = position.symbol

        if position.side == PositionSide.LONG:
            # Check SL
            if position.stop_loss is not None and price <= position.stop_loss:
                logger.info(f"Stop loss triggered for {symbol} @ {price}")
                self.close_position(symbol)
                return

            # Check TP
            if position.take_profit is not None and price >= position.take_profit:
                logger.info(f"Take profit triggered for {symbol} @ {price}")
                self.close_position(symbol)
                return

            # Check liquidation
            if (
                position.liquidation_price is not None
                and price <= position.liquidation_price
            ):
                logger.warning(f"Liquidation triggered for {symbol} @ {price}")
                self._liquidate_position(position)

        else:  # SHORT
            # Check SL
            if position.stop_loss is not None and price >= position.stop_loss:
                logger.info(f"Stop loss triggered for {symbol} @ {price}")
                self.close_position(symbol)
                return

            # Check TP
            if position.take_profit is not None and price <= position.take_profit:
                logger.info(f"Take profit triggered for {symbol} @ {price}")
                self.close_position(symbol)
                return

            # Check liquidation
            if (
                position.liquidation_price is not None
                and price >= position.liquidation_price
            ):
                logger.warning(f"Liquidation triggered for {symbol} @ {price}")
                self._liquidate_position(position)

    def _liquidate_position(self, position: PaperPosition) -> None:
        """Liquidate a position (complete loss of margin)."""
        # Close at liquidation price with full margin loss
        margin_lost = position.margin_used
        self.account.balance -= margin_lost
        self.account.realized_pnl -= margin_lost
        self.account.losing_trades += 1
        self.account.total_trades += 1

        del self.positions[position.symbol]

        logger.warning(
            f"Position liquidated: {position.symbol}, loss: {margin_lost:.2f}"
        )

    def _update_margin_used(self) -> None:
        """Update total margin used."""
        self.account.margin_used = sum(p.margin_used for p in self.positions.values())

    def _update_account_equity(self) -> None:
        """Update account equity based on positions."""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self.account.unrealized_pnl = unrealized
        self.account.equity = (
            self.account.balance + self.account.margin_used + unrealized
        )

    def _record_equity(self) -> None:
        """Record current equity to curve."""
        self.equity_curve.append(
            (
                datetime.now(UTC),
                self.account.equity,
            )
        )


# Singleton instance
_paper_engine: PaperTradingEngine | None = None


def get_paper_trading_engine(
    initial_balance: float = 10000.0,
    reset: bool = False,
) -> PaperTradingEngine:
    """Get or create paper trading engine instance."""
    global _paper_engine

    if _paper_engine is None or reset:
        _paper_engine = PaperTradingEngine(initial_balance=initial_balance)

    return _paper_engine
