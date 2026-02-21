"""
Live Trading Bridge Module for Universal Math Engine v2.4.

This module provides bridge to live trading:
1. PaperTradingEngine - Simulated live trading
2. LiveTradingBridge - Connection to exchanges
3. OrderManager - Order creation and management
4. PositionTracker - Real-time position tracking
5. RiskManager - Live risk controls
6. ExecutionAnalytics - Execution quality analysis

Author: Universal Math Engine Team
Version: 2.4.0
"""

import asyncio
import hashlib
import hmac
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import numpy as np

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """Position side."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class TradingMode(Enum):
    """Trading mode."""

    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


@dataclass
class Order:
    """Trading order."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None  # For limit orders
    stop_price: float | None = None  # For stop orders
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    client_order_id: str = ""
    time_in_force: str = "GTC"  # GTC, IOC, FOK
    reduce_only: bool = False
    post_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.client_order_id:
            self.client_order_id = str(uuid.uuid4())[:8]


@dataclass
class Position:
    """Trading position."""

    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    liquidation_price: float = 0.0
    margin_used: float = 0.0
    opened_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def notional_value(self) -> float:
        """Calculate notional value."""
        return self.quantity * self.current_price

    @property
    def pnl_percent(self) -> float:
        """Calculate PnL percentage."""
        if self.entry_price == 0:
            return 0.0
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100


@dataclass
class Trade:
    """Executed trade."""

    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime = field(default_factory=datetime.now)
    is_maker: bool = False


@dataclass
class AccountBalance:
    """Account balance."""

    total_equity: float
    available_balance: float
    margin_balance: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    margin_ratio: float = 0.0  # Used margin / Total equity


@dataclass
class RiskLimits:
    """Risk management limits."""

    max_position_size: float = 1.0  # Max position as fraction of equity
    max_leverage: float = 10.0
    max_drawdown: float = 0.2  # 20%
    daily_loss_limit: float = 0.05  # 5% daily
    max_open_orders: int = 10
    max_positions: int = 5
    min_order_size: float = 0.001
    max_order_size: float = 100.0


@dataclass
class ExecutionReport:
    """Order execution report."""

    order_id: str
    status: OrderStatus
    filled_quantity: float
    avg_fill_price: float
    slippage: float  # As percentage
    execution_time_ms: float
    commission: float
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# EXCHANGE CONNECTION (ABSTRACT)
# ============================================================================


class ExchangeConnection(ABC):
    """Abstract base class for exchange connections."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        pass

    @abstractmethod
    async def get_balance(self) -> AccountBalance:
        """Get account balance."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get open positions."""
        pass

    @abstractmethod
    async def place_order(self, order: Order) -> ExecutionReport:
        """Place order on exchange."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        pass

    @abstractmethod
    async def get_market_price(self, symbol: str) -> float:
        """Get current market price."""
        pass


# ============================================================================
# PAPER TRADING ENGINE
# ============================================================================


class PaperTradingEngine(ExchangeConnection):
    """
    Simulated trading engine for paper trading.

    Simulates order execution with configurable slippage and latency.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_rate: float = 0.0007,  # Must match BacktestConfig (TradingView parity)
        slippage_rate: float = 0.0005,
        latency_ms: float = 50.0,
    ):
        self.initial_balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.latency_ms = latency_ms

        # State
        self._balance = initial_balance
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._trades: list[Trade] = []
        self._market_prices: dict[str, float] = {}
        self._unrealized_pnl = 0.0
        self._realized_pnl = 0.0

        self._connected = False

    async def connect(self) -> bool:
        """Simulate connection."""
        await asyncio.sleep(self.latency_ms / 1000)
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    def set_market_price(self, symbol: str, price: float) -> None:
        """Set market price for symbol."""
        self._market_prices[symbol] = price
        self._update_positions()

    async def get_market_price(self, symbol: str) -> float:
        """Get current market price."""
        return self._market_prices.get(symbol, 0.0)

    async def get_balance(self) -> AccountBalance:
        """Get account balance."""
        self._update_positions()

        margin_used = sum(pos.margin_used for pos in self._positions.values())

        return AccountBalance(
            total_equity=self._balance + self._unrealized_pnl,
            available_balance=self._balance - margin_used,
            margin_balance=self._balance,
            unrealized_pnl=self._unrealized_pnl,
            realized_pnl=self._realized_pnl,
            margin_used=margin_used,
            margin_ratio=margin_used / self._balance if self._balance > 0 else 0,
        )

    async def get_positions(self) -> list[Position]:
        """Get open positions."""
        self._update_positions()
        return list(self._positions.values())

    async def place_order(self, order: Order) -> ExecutionReport:
        """Execute order in paper trading."""
        start_time = time.time()

        # Simulate latency
        await asyncio.sleep(self.latency_ms / 1000)

        # Get market price
        market_price = self._market_prices.get(order.symbol, 0.0)
        if market_price == 0:
            order.status = OrderStatus.REJECTED
            return ExecutionReport(
                order_id=order.order_id,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                avg_fill_price=0,
                slippage=0,
                execution_time_ms=(time.time() - start_time) * 1000,
                commission=0,
            )

        # Calculate fill price with slippage
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + self.slippage_rate)
        else:
            fill_price = market_price * (1 - self.slippage_rate)

        # Check for limit order
        if order.order_type == OrderType.LIMIT:
            if (order.side == OrderSide.BUY and fill_price > order.price) or (
                order.side == OrderSide.SELL and fill_price < order.price
            ):
                order.status = OrderStatus.OPEN
                self._orders[order.order_id] = order
                return ExecutionReport(
                    order_id=order.order_id,
                    status=OrderStatus.OPEN,
                    filled_quantity=0,
                    avg_fill_price=0,
                    slippage=0,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    commission=0,
                )
            fill_price = order.price

        # Calculate commission
        commission = order.quantity * fill_price * self.commission_rate

        # Update balance
        if order.side == OrderSide.BUY:
            cost = order.quantity * fill_price + commission
            if cost > self._balance:
                order.status = OrderStatus.REJECTED
                return ExecutionReport(
                    order_id=order.order_id,
                    status=OrderStatus.REJECTED,
                    filled_quantity=0,
                    avg_fill_price=0,
                    slippage=0,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    commission=0,
                )
            self._balance -= cost
        else:
            revenue = order.quantity * fill_price - commission
            self._balance += revenue

        # Update position
        self._update_position_from_order(order, fill_price)

        # Record trade
        trade = Trade(
            trade_id=str(uuid.uuid4())[:8],
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
        )
        self._trades.append(trade)

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.commission = commission
        order.updated_at = datetime.now()
        self._orders[order.order_id] = order

        slippage = (fill_price - market_price) / market_price * 100

        return ExecutionReport(
            order_id=order.order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            avg_fill_price=fill_price,
            slippage=slippage,
            execution_time_ms=(time.time() - start_time) * 1000,
            commission=commission,
        )

    def _update_position_from_order(self, order: Order, fill_price: float) -> None:
        """Update position after order fill."""
        symbol = order.symbol

        if symbol not in self._positions:
            # New position
            if order.side == OrderSide.BUY:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    current_price=fill_price,
                )
            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    current_price=fill_price,
                )
        else:
            pos = self._positions[symbol]

            if (pos.side == PositionSide.LONG and order.side == OrderSide.BUY) or (
                pos.side == PositionSide.SHORT and order.side == OrderSide.SELL
            ):
                # Adding to position
                total_qty = pos.quantity + order.quantity
                pos.entry_price = (pos.entry_price * pos.quantity + fill_price * order.quantity) / total_qty
                pos.quantity = total_qty
            else:
                # Reducing or closing position
                if order.quantity >= pos.quantity:
                    # Close position and possibly reverse
                    pnl = self._calculate_pnl(pos, fill_price, pos.quantity)
                    self._realized_pnl += pnl

                    remaining = order.quantity - pos.quantity

                    if remaining > 0:
                        # Reverse position
                        new_side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
                        self._positions[symbol] = Position(
                            symbol=symbol,
                            side=new_side,
                            quantity=remaining,
                            entry_price=fill_price,
                            current_price=fill_price,
                        )
                    else:
                        del self._positions[symbol]
                else:
                    # Partial close
                    pnl = self._calculate_pnl(pos, fill_price, order.quantity)
                    self._realized_pnl += pnl
                    pos.quantity -= order.quantity

    def _calculate_pnl(self, pos: Position, exit_price: float, quantity: float) -> float:
        """Calculate PnL for closed position."""
        if pos.side == PositionSide.LONG:
            return (exit_price - pos.entry_price) * quantity
        else:
            return (pos.entry_price - exit_price) * quantity

    def _update_positions(self) -> None:
        """Update all positions with current prices."""
        self._unrealized_pnl = 0.0

        for pos in self._positions.values():
            price = self._market_prices.get(pos.symbol, pos.current_price)
            pos.current_price = price

            if pos.side == PositionSide.LONG:
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = (pos.entry_price - price) * pos.quantity

            self._unrealized_pnl += pos.unrealized_pnl

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status == OrderStatus.OPEN:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                return True
        return False

    async def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        return self._orders.get(order_id)

    def get_trades(self) -> list[Trade]:
        """Get all trades."""
        return self._trades

    def reset(self) -> None:
        """Reset paper trading state."""
        self._balance = self.initial_balance
        self._positions.clear()
        self._orders.clear()
        self._trades.clear()
        self._unrealized_pnl = 0.0
        self._realized_pnl = 0.0


# ============================================================================
# BYBIT CONNECTION
# ============================================================================


class BybitConnection(ExchangeConnection):
    """
    Connection to Bybit exchange.

    Note: This is a skeleton implementation.
    Real implementation would use websockets and REST API.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"

        self._connected = False
        self._positions: dict[str, Position] = {}

    def _sign_request(self, params: dict) -> str:
        """Create signature for request."""
        param_str = urlencode(sorted(params.items()))
        signature = hmac.new(self.api_secret.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    async def connect(self) -> bool:
        """Connect to Bybit."""
        # In real implementation: establish websocket connection
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from Bybit."""
        self._connected = False

    async def get_balance(self) -> AccountBalance:
        """Get account balance from Bybit."""
        # Placeholder - real implementation would call Bybit API
        return AccountBalance(
            total_equity=10000,
            available_balance=8000,
            margin_balance=10000,
            unrealized_pnl=0,
            realized_pnl=0,
            margin_used=2000,
        )

    async def get_positions(self) -> list[Position]:
        """Get positions from Bybit."""
        # Placeholder
        return list(self._positions.values())

    async def place_order(self, order: Order) -> ExecutionReport:
        """Place order on Bybit."""
        # Placeholder
        return ExecutionReport(
            order_id=order.order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            avg_fill_price=order.price or 0,
            slippage=0,
            execution_time_ms=100,
            commission=0,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Bybit."""
        return True

    async def get_order_status(self, order_id: str) -> Order:
        """Get order status from Bybit."""
        return Order(
            order_id=order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
            status=OrderStatus.FILLED,
        )

    async def get_market_price(self, symbol: str) -> float:
        """Get market price from Bybit."""
        # Placeholder
        return 50000.0


# ============================================================================
# ORDER MANAGER
# ============================================================================


class OrderManager:
    """
    Manages order lifecycle and execution.
    """

    def __init__(self, connection: ExchangeConnection, risk_limits: RiskLimits | None = None):
        self.connection = connection
        self.risk_limits = risk_limits or RiskLimits()

        self._pending_orders: dict[str, Order] = {}
        self._open_orders: dict[str, Order] = {}
        self._filled_orders: list[Order] = []
        self._order_callbacks: list[Callable[[ExecutionReport], None]] = []

    def add_callback(self, callback: Callable[[ExecutionReport], None]) -> None:
        """Add order callback."""
        self._order_callbacks.append(callback)

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
        stop_price: float | None = None,
        reduce_only: bool = False,
    ) -> ExecutionReport:
        """
        Submit order to exchange.

        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Type of order
            price: Limit price (for limit orders)
            stop_price: Stop trigger price
            reduce_only: Only reduce position

        Returns:
            Execution report
        """
        # Validate order
        validation = self._validate_order(symbol, side, quantity, order_type, price)
        if not validation["valid"]:
            return ExecutionReport(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                avg_fill_price=0,
                slippage=0,
                execution_time_ms=0,
                commission=0,
            )

        # Create order
        order = Order(
            order_id=str(uuid.uuid4())[:16],
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            reduce_only=reduce_only,
        )

        self._pending_orders[order.order_id] = order

        # Submit to exchange
        try:
            report = await self.connection.place_order(order)

            # Update order status
            order.status = report.status
            order.filled_quantity = report.filled_quantity
            order.filled_price = report.avg_fill_price
            order.commission = report.commission

            if report.status == OrderStatus.FILLED:
                self._filled_orders.append(order)
                del self._pending_orders[order.order_id]
            elif report.status == OrderStatus.OPEN:
                self._open_orders[order.order_id] = order
                del self._pending_orders[order.order_id]
            else:
                del self._pending_orders[order.order_id]

            # Notify callbacks
            for callback in self._order_callbacks:
                callback(report)

            return report

        except Exception:
            order.status = OrderStatus.REJECTED
            del self._pending_orders[order.order_id]
            return ExecutionReport(
                order_id=order.order_id,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                avg_fill_price=0,
                slippage=0,
                execution_time_ms=0,
                commission=0,
            )

    def _validate_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType,
        price: float | None,
    ) -> dict[str, Any]:
        """Validate order against risk limits."""
        errors = []

        # Check quantity limits
        if quantity < self.risk_limits.min_order_size:
            errors.append(f"Quantity {quantity} below minimum {self.risk_limits.min_order_size}")

        if quantity > self.risk_limits.max_order_size:
            errors.append(f"Quantity {quantity} above maximum {self.risk_limits.max_order_size}")

        # Check max open orders
        if len(self._open_orders) >= self.risk_limits.max_open_orders:
            errors.append(f"Max open orders ({self.risk_limits.max_open_orders}) reached")

        # Check limit order has price
        if order_type == OrderType.LIMIT and price is None:
            errors.append("Limit order requires price")

        return {"valid": len(errors) == 0, "errors": errors}

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel open order."""
        if order_id not in self._open_orders:
            return False

        success = await self.connection.cancel_order(order_id)
        if success:
            order = self._open_orders[order_id]
            order.status = OrderStatus.CANCELLED
            del self._open_orders[order_id]

        return success

    async def cancel_all_orders(self, symbol: str | None = None) -> int:
        """Cancel all open orders."""
        cancelled = 0
        orders_to_cancel = list(self._open_orders.keys())

        for order_id in orders_to_cancel:
            order = self._open_orders[order_id]
            if symbol is None or order.symbol == symbol:
                if await self.cancel_order(order_id):
                    cancelled += 1

        return cancelled

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get open orders."""
        orders = list(self._open_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_filled_orders(self, symbol: str | None = None) -> list[Order]:
        """Get filled orders."""
        orders = self._filled_orders
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders


# ============================================================================
# POSITION TRACKER
# ============================================================================


class PositionTracker:
    """
    Tracks positions in real-time.
    """

    def __init__(self, connection: ExchangeConnection):
        self.connection = connection
        self._positions: dict[str, Position] = {}
        self._position_callbacks: list[Callable[[Position], None]] = []

    def add_callback(self, callback: Callable[[Position], None]) -> None:
        """Add position update callback."""
        self._position_callbacks.append(callback)

    async def sync_positions(self) -> None:
        """Sync positions from exchange."""
        positions = await self.connection.get_positions()
        self._positions = {p.symbol: p for p in positions}

        for callback in self._position_callbacks:
            for pos in positions:
                callback(pos)

    def get_position(self, symbol: str) -> Position | None:
        """Get position for symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[Position]:
        """Get all positions."""
        return list(self._positions.values())

    def update_position(self, symbol: str, price: float) -> None:
        """Update position with new price."""
        if symbol in self._positions:
            pos = self._positions[symbol]
            pos.current_price = price
            pos.updated_at = datetime.now()

            if pos.side == PositionSide.LONG:
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = (pos.entry_price - price) * pos.quantity

            for callback in self._position_callbacks:
                callback(pos)

    def total_exposure(self) -> float:
        """Calculate total exposure."""
        return sum(p.notional_value for p in self._positions.values())

    def total_unrealized_pnl(self) -> float:
        """Calculate total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self._positions.values())


# ============================================================================
# RISK MANAGER
# ============================================================================


class RiskManager:
    """
    Live risk management controls.
    """

    def __init__(self, connection: ExchangeConnection, limits: RiskLimits | None = None):
        self.connection = connection
        self.limits = limits or RiskLimits()

        self._daily_pnl = 0.0
        self._daily_start_equity = 0.0
        self._max_equity = 0.0
        self._drawdown = 0.0
        self._trading_halted = False
        self._halt_reason = ""

    async def initialize(self) -> None:
        """Initialize risk manager."""
        balance = await self.connection.get_balance()
        self._daily_start_equity = balance.total_equity
        self._max_equity = balance.total_equity

    async def check_limits(self) -> dict[str, Any]:
        """Check all risk limits."""
        balance = await self.connection.get_balance()
        positions = await self.connection.get_positions()

        breaches = []

        # Update tracking
        current_equity = balance.total_equity
        self._max_equity = max(self._max_equity, current_equity)
        self._drawdown = (self._max_equity - current_equity) / self._max_equity
        self._daily_pnl = (current_equity - self._daily_start_equity) / self._daily_start_equity

        # Check drawdown
        if self._drawdown > self.limits.max_drawdown:
            breaches.append(
                {
                    "type": "drawdown",
                    "current": self._drawdown,
                    "limit": self.limits.max_drawdown,
                }
            )
            self._halt_trading("Max drawdown exceeded")

        # Check daily loss
        if self._daily_pnl < -self.limits.daily_loss_limit:
            breaches.append(
                {
                    "type": "daily_loss",
                    "current": self._daily_pnl,
                    "limit": self.limits.daily_loss_limit,
                }
            )
            self._halt_trading("Daily loss limit exceeded")

        # Check position count
        if len(positions) > self.limits.max_positions:
            breaches.append(
                {
                    "type": "position_count",
                    "current": len(positions),
                    "limit": self.limits.max_positions,
                }
            )

        # Check position sizes
        for pos in positions:
            position_ratio = pos.notional_value / current_equity
            if position_ratio > self.limits.max_position_size:
                breaches.append(
                    {
                        "type": "position_size",
                        "symbol": pos.symbol,
                        "current": position_ratio,
                        "limit": self.limits.max_position_size,
                    }
                )

            if pos.leverage > self.limits.max_leverage:
                breaches.append(
                    {
                        "type": "leverage",
                        "symbol": pos.symbol,
                        "current": pos.leverage,
                        "limit": self.limits.max_leverage,
                    }
                )

        return {
            "breaches": breaches,
            "trading_halted": self._trading_halted,
            "halt_reason": self._halt_reason,
            "current_drawdown": self._drawdown,
            "daily_pnl": self._daily_pnl,
        }

    def _halt_trading(self, reason: str) -> None:
        """Halt all trading."""
        self._trading_halted = True
        self._halt_reason = reason

    def resume_trading(self) -> None:
        """Resume trading."""
        self._trading_halted = False
        self._halt_reason = ""

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed."""
        return not self._trading_halted

    def reset_daily(self) -> None:
        """Reset daily counters."""
        asyncio.create_task(self._reset_daily_async())

    async def _reset_daily_async(self) -> None:
        """Async reset daily counters."""
        balance = await self.connection.get_balance()
        self._daily_start_equity = balance.total_equity
        self._daily_pnl = 0.0


# ============================================================================
# EXECUTION ANALYTICS
# ============================================================================


class ExecutionAnalytics:
    """
    Analyze execution quality.
    """

    def __init__(self):
        self._executions: list[ExecutionReport] = []
        self._market_prices_at_order: dict[str, float] = {}

    def record_execution(self, report: ExecutionReport, market_price_at_order: float) -> None:
        """Record execution for analysis."""
        self._executions.append(report)
        self._market_prices_at_order[report.order_id] = market_price_at_order

    def get_summary(self) -> dict[str, float]:
        """Get execution summary statistics."""
        if not self._executions:
            return {}

        filled = [e for e in self._executions if e.status == OrderStatus.FILLED]

        if not filled:
            return {}

        slippages = [e.slippage for e in filled]
        execution_times = [e.execution_time_ms for e in filled]
        commissions = [e.commission for e in filled]

        return {
            "total_orders": len(self._executions),
            "filled_orders": len(filled),
            "fill_rate": len(filled) / len(self._executions) * 100,
            "avg_slippage": float(np.mean(slippages)),
            "max_slippage": float(np.max(slippages)),
            "avg_execution_time_ms": float(np.mean(execution_times)),
            "total_commissions": float(np.sum(commissions)),
            "avg_commission": float(np.mean(commissions)),
        }

    def get_slippage_analysis(self) -> dict[str, Any]:
        """Detailed slippage analysis."""
        filled = [e for e in self._executions if e.status == OrderStatus.FILLED]

        if not filled:
            return {}

        slippages = [e.slippage for e in filled]

        return {
            "mean": float(np.mean(slippages)),
            "median": float(np.median(slippages)),
            "std": float(np.std(slippages)),
            "min": float(np.min(slippages)),
            "max": float(np.max(slippages)),
            "percentile_95": float(np.percentile(slippages, 95)),
            "negative_slippage_count": sum(1 for s in slippages if s < 0),
            "positive_slippage_count": sum(1 for s in slippages if s > 0),
        }


# ============================================================================
# LIVE TRADING BRIDGE
# ============================================================================


class LiveTradingBridge:
    """
    Main bridge for live/paper trading.

    Coordinates order management, position tracking, and risk management.
    """

    def __init__(
        self,
        mode: TradingMode = TradingMode.PAPER,
        connection: ExchangeConnection | None = None,
        risk_limits: RiskLimits | None = None,
    ):
        self.mode = mode
        self.risk_limits = risk_limits or RiskLimits()

        # Create connection based on mode
        if connection:
            self.connection = connection
        elif mode == TradingMode.PAPER:
            self.connection = PaperTradingEngine()
        else:
            raise ValueError("Live mode requires exchange connection")

        # Initialize components
        self.order_manager = OrderManager(self.connection, self.risk_limits)
        self.position_tracker = PositionTracker(self.connection)
        self.risk_manager = RiskManager(self.connection, self.risk_limits)
        self.execution_analytics = ExecutionAnalytics()

        self._running = False
        self._price_callbacks: list[Callable[[str, float], None]] = []

    async def start(self) -> bool:
        """Start the trading bridge."""
        # Connect to exchange
        connected = await self.connection.connect()
        if not connected:
            return False

        # Initialize components
        await self.risk_manager.initialize()
        await self.position_tracker.sync_positions()

        self._running = True
        return True

    async def stop(self) -> None:
        """Stop the trading bridge."""
        self._running = False
        await self.connection.disconnect()

    def add_price_callback(self, callback: Callable[[str, float], None]) -> None:
        """Add price update callback."""
        self._price_callbacks.append(callback)

    def update_price(self, symbol: str, price: float) -> None:
        """Update market price."""
        if isinstance(self.connection, PaperTradingEngine):
            self.connection.set_market_price(symbol, price)

        self.position_tracker.update_position(symbol, price)

        for callback in self._price_callbacks:
            callback(symbol, price)

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
        stop_price: float | None = None,
        reduce_only: bool = False,
    ) -> ExecutionReport:
        """Submit trading order."""
        # Check risk limits
        if not self.risk_manager.is_trading_allowed():
            return ExecutionReport(
                order_id="",
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                avg_fill_price=0,
                slippage=0,
                execution_time_ms=0,
                commission=0,
            )

        # Get market price for slippage analysis
        market_price = await self.connection.get_market_price(symbol)

        # Submit order
        report = await self.order_manager.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            reduce_only=reduce_only,
        )

        # Record for analytics
        self.execution_analytics.record_execution(report, market_price)

        # Sync positions
        await self.position_tracker.sync_positions()

        # Check risk limits
        await self.risk_manager.check_limits()

        return report

    async def get_status(self) -> dict[str, Any]:
        """Get current trading status."""
        balance = await self.connection.get_balance()
        positions = self.position_tracker.get_all_positions()
        open_orders = self.order_manager.get_open_orders()
        risk_status = await self.risk_manager.check_limits()
        execution_summary = self.execution_analytics.get_summary()

        return {
            "mode": self.mode.value,
            "running": self._running,
            "balance": {
                "total_equity": balance.total_equity,
                "available_balance": balance.available_balance,
                "unrealized_pnl": balance.unrealized_pnl,
                "realized_pnl": balance.realized_pnl,
            },
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side.value,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "pnl_percent": p.pnl_percent,
                }
                for p in positions
            ],
            "open_orders": len(open_orders),
            "risk": risk_status,
            "execution": execution_summary,
        }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "PositionSide",
    "TradingMode",
    # Data structures
    "Order",
    "Position",
    "Trade",
    "AccountBalance",
    "RiskLimits",
    "ExecutionReport",
    # Connections
    "ExchangeConnection",
    "PaperTradingEngine",
    "BybitConnection",
    # Components
    "OrderManager",
    "PositionTracker",
    "RiskManager",
    "ExecutionAnalytics",
    # Main bridge
    "LiveTradingBridge",
]
