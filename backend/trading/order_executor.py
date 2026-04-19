"""
📈 Order Executor

Order execution for live trading.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Order types"""

    MARKET = "Market"
    LIMIT = "Limit"


class OrderSide(str, Enum):
    """Order sides"""

    BUY = "Buy"
    SELL = "Sell"


class OrderStatus(str, Enum):
    """Order statuses"""

    PENDING = "Pending"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartiallyFilled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


@dataclass
class Order:
    """Order representation"""

    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    id: str = field(default_factory=lambda: f"order_{datetime.now().timestamp()}")
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class OrderResult:
    """Order execution result"""

    success: bool
    order: Order | None = None
    error: str | None = None
    fills: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "order": self.order.to_dict() if self.order else None,
            "error": self.error,
            "fills": self.fills,
        }


class OrderExecutor:
    """
    Order executor for live trading.

    Поддерживает:
    - Market orders
    - Limit orders
    - Stop-loss/Take-profit
    - Order cancellation
    - Order status tracking
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        testnet: bool = True,
    ):
        """
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # Active orders
        self.orders: dict[str, Order] = {}

        # Order history
        self.order_history: list[Order] = []

        # Fills
        self.fills: list[dict[str, Any]] = []

        # CCXT exchange (if available)
        self._exchange = None

    def _init_exchange(self):
        """Initialize CCXT exchange"""
        try:
            import ccxt

            self._exchange = ccxt.bybit(
                {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "sandbox": self.testnet,
                    "options": {
                        "defaultType": "linear",  # USDT perpetual
                    },
                }
            )

            logger.info("Exchange initialized")

        except ImportError:
            logger.warning("CCXT not installed, using mock execution")
        except Exception as e:
            logger.error(f"Exchange init failed: {e}")

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: float,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> OrderResult:
        """
        Submit order.

        Args:
            symbol: Symbol (e.g., BTCUSDT)
            side: Buy or Sell
            type: Market or Limit
            quantity: Quantity
            price: Price (for limit orders)
            stop_loss: Stop-loss price
            take_profit: Take-profit price

        Returns:
            OrderResult
        """
        # Create order
        order = Order(
            symbol=symbol,
            side=side,
            type=type,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        logger.info(f"Submitting order: {order.id} - {side.value} {quantity} {symbol}")

        try:
            # Initialize exchange if needed
            if self._exchange is None and self.api_key:
                self._init_exchange()

            # Execute order
            if self._exchange and self.api_key:
                # Real execution
                result = await self._execute_real_order(order)
            else:
                # Mock execution
                result = await self._execute_mock_order(order)

            # Store order
            self.orders[order.id] = order
            self.order_history.append(order)

            return result

        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            return OrderResult(
                success=False,
                error=str(e),
            )

    async def _execute_real_order(self, order: Order) -> OrderResult:
        """Execute real order via CCXT"""
        try:
            # Prepare order parameters
            params = {
                "symbol": order.symbol,
                "type": order.type.value.lower(),
                "side": order.side.value.lower(),
                "amount": order.quantity,
            }

            if order.price:
                params["price"] = order.price

            if order.stop_loss:
                params["stopLoss"] = order.stop_loss

            if order.take_profit:
                params["takeProfit"] = order.take_profit

            # Submit order
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._exchange.create_order(**params)
            )

            # Update order
            order.status = OrderStatus.FILLED if response["status"] == "closed" else OrderStatus.PENDING
            order.filled_quantity = response.get("filled", 0)
            order.avg_fill_price = response.get("average", 0)

            return OrderResult(
                success=True,
                order=order,
            )

        except Exception as e:
            order.status = OrderStatus.REJECTED
            return OrderResult(
                success=False,
                order=order,
                error=str(e),
            )

    async def _execute_mock_order(self, order: Order) -> OrderResult:
        """Execute mock order (paper trading)"""
        # Simulate fill

        # Mock fill price
        fill_price = 50000.0 if order.type == OrderType.MARKET else order.price or 50000.0

        # Mock fill
        fill = {
            "id": f"fill_{order.id}",
            "order_id": order.id,
            "price": fill_price,
            "quantity": order.quantity,
            "timestamp": datetime.now().isoformat(),
        }

        # Update order
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.status = OrderStatus.FILLED
        order.updated_at = datetime.now()

        self.fills.append(fill)

        logger.info(f"Mock order filled: {order.id} @ {fill_price}")

        return OrderResult(
            success=True,
            order=order,
            fills=[fill],
        )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.

        Args:
            order_id: Order ID

        Returns:
            True if cancelled
        """
        if order_id not in self.orders:
            logger.warning(f"Order not found: {order_id}")
            return False

        order = self.orders[order_id]

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            logger.warning(f"Cannot cancel order in status {order.status}")
            return False

        try:
            if self._exchange and self.api_key:
                # Real cancellation
                await asyncio.get_event_loop().run_in_executor(None, lambda: self._exchange.cancel_order(order_id))

            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()

            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    async def get_order_status(self, order_id: str) -> Order | None:
        """Get order status"""
        return self.orders.get(order_id)

    def get_active_orders(self) -> list[Order]:
        """Get all active orders"""
        return [
            order
            for order in self.orders.values()
            if order.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]
        ]

    def get_order_history(self, symbol: str | None = None) -> list[Order]:
        """Get order history"""
        if symbol:
            return [o for o in self.order_history if o.symbol == symbol]
        return self.order_history


# Import asyncio for real execution
import asyncio
