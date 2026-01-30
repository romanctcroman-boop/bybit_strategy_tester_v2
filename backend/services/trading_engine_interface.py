"""
Trading Engine Service Interface for Microservices Architecture.

Provides abstraction layer for trading operations that can be:
1. Run in-process (monolith mode)
2. Deployed as separate microservice (distributed mode)
3. Accessed via gRPC/REST from other services

This enables gradual migration from monolith to microservices.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Trading Domain Models
# ============================================================================


class OrderSide(Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """Position side."""

    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class Order:
    """Trading order."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exchange_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "exchange_order_id": self.exchange_order_id,
            "client_order_id": self.client_order_id,
            "metadata": self.metadata,
        }


@dataclass
class Position:
    """Trading position."""

    position_id: str
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    margin: float = 0.0
    liquidation_price: Optional[float] = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TradeResult:
    """Result of a trade operation."""

    success: bool
    order: Optional[Order] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class AccountBalance:
    """Account balance information."""

    currency: str
    total_balance: float
    available_balance: float
    locked_balance: float
    margin_balance: float = 0.0
    unrealized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Trading Engine Interface
# ============================================================================


class ITradingEngine(ABC):
    """
    Abstract Trading Engine Interface.

    All trading operations should go through this interface.
    Implementations can be:
    - LocalTradingEngine (in-process)
    - RemoteTradingEngine (microservice via HTTP/gRPC)
    - MockTradingEngine (for testing)
    """

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TradeResult:
        """Place a new order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> TradeResult:
        """Cancel an existing order."""
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> TradeResult:
        """Modify an existing order."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all open orders, optionally filtered by symbol."""
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        pass

    @abstractmethod
    async def get_all_positions(self) -> list[Position]:
        """Get all open positions."""
        pass

    @abstractmethod
    async def close_position(self, symbol: str, quantity: Optional[float] = None) -> TradeResult:
        """Close a position (fully or partially)."""
        pass

    @abstractmethod
    async def get_balance(self, currency: str = "USDT") -> Optional[AccountBalance]:
        """Get account balance."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check trading engine health."""
        pass


# ============================================================================
# Local Trading Engine (In-Process Implementation)
# ============================================================================


class LocalTradingEngine(ITradingEngine):
    """
    In-process trading engine implementation.

    Uses existing backend services for actual trading operations.
    This is the default mode for monolithic deployment.
    """

    def __init__(self):
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._balances: dict[str, AccountBalance] = {}
        self._event_bus: Optional[Any] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the trading engine."""
        # Import here to avoid circular imports
        try:
            from backend.services.event_bus import get_event_bus

            self._event_bus = get_event_bus()
        except ImportError:
            logger.warning("Event bus not available")

        self._initialized = True
        logger.info("LocalTradingEngine initialized")

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TradeResult:
        """Place a new order."""
        import time

        start_time = time.time()

        try:
            # Validate order
            if quantity <= 0:
                return TradeResult(
                    success=False,
                    error_code="INVALID_QUANTITY",
                    error_message="Quantity must be positive",
                )

            if order_type == OrderType.LIMIT and not price:
                return TradeResult(
                    success=False,
                    error_code="MISSING_PRICE",
                    error_message="Limit order requires price",
                )

            # Create order
            order_id = str(uuid4())
            order = Order(
                order_id=order_id,
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                client_order_id=client_order_id or str(uuid4()),
                metadata=metadata or {},
            )

            # Store order
            self._orders[order_id] = order

            # Publish event
            if self._event_bus:
                await self._event_bus.publish(
                    event_type="order.created",
                    payload=order.to_dict(),
                )

            latency = (time.time() - start_time) * 1000
            logger.info(f"Order placed: {order_id} ({latency:.2f}ms)")

            return TradeResult(success=True, order=order, latency_ms=latency)

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return TradeResult(
                success=False,
                error_code="ORDER_FAILED",
                error_message=str(e),
            )

    async def cancel_order(self, order_id: str) -> TradeResult:
        """Cancel an existing order."""
        order = self._orders.get(order_id)
        if not order:
            return TradeResult(
                success=False,
                error_code="ORDER_NOT_FOUND",
                error_message=f"Order {order_id} not found",
            )

        if order.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        ]:
            return TradeResult(
                success=False,
                error_code="INVALID_ORDER_STATUS",
                error_message=f"Cannot cancel order in status {order.status.value}",
            )

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)

        # Publish event
        if self._event_bus:
            await self._event_bus.publish(
                event_type="order.cancelled",
                payload=order.to_dict(),
            )

        return TradeResult(success=True, order=order)

    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> TradeResult:
        """Modify an existing order."""
        order = self._orders.get(order_id)
        if not order:
            return TradeResult(
                success=False,
                error_code="ORDER_NOT_FOUND",
                error_message=f"Order {order_id} not found",
            )

        if order.status != OrderStatus.PENDING:
            return TradeResult(
                success=False,
                error_code="INVALID_ORDER_STATUS",
                error_message="Can only modify pending orders",
            )

        if quantity is not None:
            order.quantity = quantity
        if price is not None:
            order.price = price
        if stop_price is not None:
            order.stop_price = stop_price

        order.updated_at = datetime.now(timezone.utc)

        return TradeResult(success=True, order=order)

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all open orders."""
        open_statuses = [OrderStatus.PENDING, OrderStatus.SUBMITTED]
        orders = [o for o in self._orders.values() if o.status in open_statuses]

        if symbol:
            orders = [o for o in orders if o.symbol == symbol.upper()]

        return orders

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        return self._positions.get(symbol.upper())

    async def get_all_positions(self) -> list[Position]:
        """Get all open positions."""
        return [p for p in self._positions.values() if p.side != PositionSide.NONE]

    async def close_position(self, symbol: str, quantity: Optional[float] = None) -> TradeResult:
        """Close a position."""
        position = self._positions.get(symbol.upper())
        if not position:
            return TradeResult(
                success=False,
                error_code="POSITION_NOT_FOUND",
                error_message=f"No position for {symbol}",
            )

        # Determine close side
        close_side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        close_qty = quantity or position.size

        return await self.place_order(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=close_qty,
            metadata={"close_position": True},
        )

    async def get_balance(self, currency: str = "USDT") -> Optional[AccountBalance]:
        """Get account balance."""
        return self._balances.get(currency.upper())

    async def health_check(self) -> dict[str, Any]:
        """Check trading engine health."""
        return {
            "status": "healthy",
            "initialized": self._initialized,
            "open_orders": len([o for o in self._orders.values() if o.status == OrderStatus.PENDING]),
            "positions": len(self._positions),
            "event_bus_connected": self._event_bus is not None,
        }


# ============================================================================
# Remote Trading Engine (Microservice Client)
# ============================================================================


class RemoteTradingEngine(ITradingEngine):
    """
    Remote trading engine client.

    Communicates with trading engine microservice via HTTP/gRPC.
    Used in distributed deployment mode.

    Recommended usage (context manager):
        async with RemoteTradingEngine("http://localhost:8001") as engine:
            result = await engine.place_order(...)

    Alternative (manual cleanup):
        engine = RemoteTradingEngine("http://localhost:8001")
        try:
            result = await engine.place_order(...)
        finally:
            await engine.close()
    """

    def __init__(
        self,
        base_url: str = "http://trading-engine:8001",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[Any] = None
        self._closed = False

    async def __aenter__(self) -> "RemoteTradingEngine":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures cleanup."""
        await self.close()

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._closed:
            return
        self._closed = True
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
            finally:
                self._client = None

    async def _get_client(self) -> Any:
        """Get or create HTTP client."""
        if self._closed:
            raise RuntimeError("RemoteTradingEngine is closed")
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make HTTP request to trading engine."""
        client = await self._get_client()
        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Trading engine request failed: {e}")
            raise

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TradeResult:
        """Place order via remote service."""
        try:
            data = await self._request(
                "POST",
                "/api/v1/orders",
                json={
                    "symbol": symbol,
                    "side": side.value,
                    "order_type": order_type.value,
                    "quantity": quantity,
                    "price": price,
                    "stop_price": stop_price,
                    "client_order_id": client_order_id,
                    "metadata": metadata,
                },
            )
            return TradeResult(
                success=True,
                order=Order(**data["order"]) if data.get("order") else None,
            )
        except Exception as e:
            return TradeResult(success=False, error_message=str(e))

    async def cancel_order(self, order_id: str) -> TradeResult:
        """Cancel order via remote service."""
        try:
            await self._request("DELETE", f"/api/v1/orders/{order_id}")
            return TradeResult(success=True)
        except Exception as e:
            return TradeResult(success=False, error_message=str(e))

    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> TradeResult:
        """Modify order via remote service."""
        try:
            await self._request(
                "PATCH",
                f"/api/v1/orders/{order_id}",
                json={"quantity": quantity, "price": price, "stop_price": stop_price},
            )
            return TradeResult(success=True)
        except Exception as e:
            return TradeResult(success=False, error_message=str(e))

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order from remote service."""
        try:
            data = await self._request("GET", f"/api/v1/orders/{order_id}")
            return Order(**data)
        except Exception:
            return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get open orders from remote service."""
        try:
            params = {"symbol": symbol} if symbol else {}
            data = await self._request("GET", "/api/v1/orders", params=params)
            return [Order(**o) for o in data.get("orders", [])]
        except Exception:
            return []

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position from remote service."""
        try:
            data = await self._request("GET", f"/api/v1/positions/{symbol}")
            return Position(**data)
        except Exception:
            return None

    async def get_all_positions(self) -> list[Position]:
        """Get all positions from remote service."""
        try:
            data = await self._request("GET", "/api/v1/positions")
            return [Position(**p) for p in data.get("positions", [])]
        except Exception:
            return []

    async def close_position(self, symbol: str, quantity: Optional[float] = None) -> TradeResult:
        """Close position via remote service."""
        try:
            await self._request(
                "POST",
                f"/api/v1/positions/{symbol}/close",
                json={"quantity": quantity},
            )
            return TradeResult(success=True)
        except Exception as e:
            return TradeResult(success=False, error_message=str(e))

    async def get_balance(self, currency: str = "USDT") -> Optional[AccountBalance]:
        """Get balance from remote service."""
        try:
            data = await self._request("GET", f"/api/v1/balance/{currency}")
            return AccountBalance(**data)
        except Exception:
            return None

    async def health_check(self) -> dict[str, Any]:
        """Check remote service health."""
        try:
            return await self._request("GET", "/health")
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# ============================================================================
# Factory Function
# ============================================================================


def create_trading_engine(mode: str = "local", **kwargs: Any) -> ITradingEngine:
    """
    Factory function to create trading engine.

    Args:
        mode: "local" for in-process, "remote" for microservice
        **kwargs: Additional configuration

    Returns:
        Trading engine instance
    """
    if mode == "local":
        return LocalTradingEngine()
    elif mode == "remote":
        base_url = kwargs.get("base_url", "http://trading-engine:8001")
        return RemoteTradingEngine(base_url=base_url)
    else:
        raise ValueError(f"Unknown trading engine mode: {mode}")


# ============================================================================
# Global Instance
# ============================================================================

_trading_engine: Optional[ITradingEngine] = None


def get_trading_engine() -> ITradingEngine:
    """Get or create the global trading engine instance."""
    global _trading_engine
    if _trading_engine is None:
        _trading_engine = LocalTradingEngine()
    return _trading_engine


async def init_trading_engine(mode: str = "local", **kwargs: Any) -> ITradingEngine:
    """Initialize the global trading engine."""
    global _trading_engine
    _trading_engine = create_trading_engine(mode, **kwargs)

    if isinstance(_trading_engine, LocalTradingEngine):
        await _trading_engine.initialize()

    return _trading_engine
