"""
Unified State Management Service.

AI Agent Recommendation Implementation:
Implements a unified state management layer using Redis for real-time trading
state (orders, positions) with PostgreSQL as source-of-truth, adding message
queue support for guaranteed event delivery between components.

Features:
- Redis for real-time state (orders, positions)
- PostgreSQL as source-of-truth
- Event queue for guaranteed delivery
- State synchronization
- Conflict resolution
- Audit trail
"""

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Enums and Constants
# ============================================================================


class StateSource(str, Enum):
    """Source of state data."""

    REDIS = "redis"
    POSTGRES = "postgres"
    LOCAL = "local"


class EventType(str, Enum):
    """Types of state events."""

    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    BALANCE_UPDATED = "balance_updated"
    STATE_SYNC = "state_sync"
    STATE_CONFLICT = "state_conflict"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(str, Enum):
    """Position side."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class ConflictResolution(str, Enum):
    """Conflict resolution strategy."""

    LATEST_WINS = "latest_wins"
    REDIS_WINS = "redis_wins"
    POSTGRES_WINS = "postgres_wins"
    MANUAL = "manual"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class Order:
    """Order data structure."""

    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market", "limit", etc.
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exchange_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value
            if isinstance(self.status, OrderStatus)
            else self.status,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "exchange_order_id": self.exchange_order_id,
            "client_order_id": self.client_order_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create from dictionary."""
        data = data.copy()
        if "status" in data and isinstance(data["status"], str):
            data["status"] = OrderStatus(data["status"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class Position:
    """Position data structure."""

    position_id: str
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    margin_used: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value
            if isinstance(self.side, PositionSide)
            else self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin_used": self.margin_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create from dictionary."""
        data = data.copy()
        if "side" in data and isinstance(data["side"], str):
            data["side"] = PositionSide(data["side"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class StateEvent:
    """State change event."""

    event_id: str
    event_type: EventType
    entity_type: str  # "order", "position", "balance"
    entity_id: str
    timestamp: datetime
    data: Dict[str, Any]
    source: StateSource
    processed: bool = False
    retry_count: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source.value,
            "processed": self.processed,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
        }


@dataclass
class StateConflict:
    """State conflict record."""

    conflict_id: str
    entity_type: str
    entity_id: str
    redis_state: Dict[str, Any]
    postgres_state: Dict[str, Any]
    redis_timestamp: datetime
    postgres_timestamp: datetime
    resolved: bool = False
    resolution: Optional[ConflictResolution] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


@dataclass
class StateMetrics:
    """State management metrics."""

    orders_in_redis: int = 0
    orders_in_postgres: int = 0
    positions_in_redis: int = 0
    positions_in_postgres: int = 0
    pending_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    last_sync: Optional[datetime] = None
    sync_latency_ms: float = 0.0
    redis_latency_ms: float = 0.0
    postgres_latency_ms: float = 0.0


# ============================================================================
# Event Queue (In-Memory Implementation)
# ============================================================================


class EventQueue:
    """
    In-memory event queue for guaranteed delivery.

    In production, replace with RabbitMQ/Redis Streams.
    """

    def __init__(self, max_size: int = 10000):
        """Initialize event queue."""
        self.max_size = max_size
        self._queue: List[StateEvent] = []
        self._dead_letter: List[StateEvent] = []
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._processing = False

    async def publish(self, event: StateEvent) -> bool:
        """Publish event to queue."""
        async with self._lock:
            if len(self._queue) >= self.max_size:
                logger.warning("Event queue full, dropping oldest event")
                self._queue.pop(0)

            self._queue.append(event)
            logger.debug(
                f"Event published: {event.event_type.value} - {event.entity_id}"
            )
            return True

    async def consume(self, batch_size: int = 10) -> List[StateEvent]:
        """Consume events from queue."""
        async with self._lock:
            events = self._queue[:batch_size]
            self._queue = self._queue[batch_size:]
            return events

    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe to event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def process_events(self, batch_size: int = 10):
        """Process events from queue."""
        if self._processing:
            return

        self._processing = True
        try:
            events = await self.consume(batch_size)
            for event in events:
                handlers = self._handlers.get(event.event_type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                        event.processed = True
                    except Exception as e:
                        event.retry_count += 1
                        event.error_message = str(e)
                        logger.error(f"Event handler error: {e}")

                        if event.retry_count >= 3:
                            self._dead_letter.append(event)
                        else:
                            await self.publish(event)
        finally:
            self._processing = False

    @property
    def pending_count(self) -> int:
        """Get pending event count."""
        return len(self._queue)

    @property
    def dead_letter_count(self) -> int:
        """Get dead letter count."""
        return len(self._dead_letter)


# ============================================================================
# State Store (Abstract Interface)
# ============================================================================


class StateStore:
    """Abstract state store interface."""

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        raise NotImplementedError

    async def set_order(self, order: Order) -> bool:
        """Set/update order."""
        raise NotImplementedError

    async def delete_order(self, order_id: str) -> bool:
        """Delete order."""
        raise NotImplementedError

    async def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        raise NotImplementedError

    async def set_position(self, position: Position) -> bool:
        """Set/update position."""
        raise NotImplementedError

    async def delete_position(self, position_id: str) -> bool:
        """Delete position."""
        raise NotImplementedError

    async def list_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """List orders."""
        raise NotImplementedError

    async def list_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """List positions."""
        raise NotImplementedError


# ============================================================================
# In-Memory State Store (Development/Testing)
# ============================================================================


class InMemoryStateStore(StateStore):
    """In-memory state store for development."""

    def __init__(self):
        """Initialize store."""
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._lock = asyncio.Lock()

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)

    async def set_order(self, order: Order) -> bool:
        """Set/update order."""
        async with self._lock:
            order.updated_at = datetime.now(timezone.utc)
            self._orders[order.order_id] = order
            return True

    async def delete_order(self, order_id: str) -> bool:
        """Delete order."""
        async with self._lock:
            if order_id in self._orders:
                del self._orders[order_id]
                return True
            return False

    async def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self._positions.get(position_id)

    async def set_position(self, position: Position) -> bool:
        """Set/update position."""
        async with self._lock:
            position.updated_at = datetime.now(timezone.utc)
            self._positions[position.position_id] = position
            return True

    async def delete_position(self, position_id: str) -> bool:
        """Delete position."""
        async with self._lock:
            if position_id in self._positions:
                del self._positions[position_id]
                return True
            return False

    async def list_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """List orders."""
        orders = list(self._orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    async def list_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """List positions."""
        positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        return positions


# ============================================================================
# Unified State Manager
# ============================================================================


class UnifiedStateManager:
    """
    Unified State Management Service.

    Coordinates between Redis (fast, real-time) and PostgreSQL (durable, source-of-truth).
    Ensures consistency and provides conflict resolution.
    """

    _instance: Optional["UnifiedStateManager"] = None

    def __init__(
        self,
        redis_store: Optional[StateStore] = None,
        postgres_store: Optional[StateStore] = None,
        conflict_resolution: ConflictResolution = ConflictResolution.LATEST_WINS,
        sync_interval_seconds: int = 30,
    ):
        """Initialize unified state manager."""
        # Use in-memory stores for development
        self.redis_store = redis_store or InMemoryStateStore()
        self.postgres_store = postgres_store or InMemoryStateStore()
        self.conflict_resolution = conflict_resolution
        self.sync_interval = sync_interval_seconds

        # Event queue
        self.event_queue = EventQueue()

        # Metrics
        self.metrics = StateMetrics()

        # Conflict tracking
        self._conflicts: Dict[str, StateConflict] = {}

        # Sync task
        self._sync_task: Optional[asyncio.Task] = None
        self._event_processor_task: Optional[asyncio.Task] = None
        self._running = False

        # Audit log
        self._audit_log: List[Dict[str, Any]] = []

        logger.info("UnifiedStateManager initialized")

    @classmethod
    def get_instance(cls) -> "UnifiedStateManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        """Start background tasks."""
        if self._running:
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        self._event_processor_task = asyncio.create_task(self._event_processor_loop())
        logger.info("UnifiedStateManager started")

    async def stop(self):
        """Stop background tasks."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        if self._event_processor_task:
            self._event_processor_task.cancel()
        logger.info("UnifiedStateManager stopped")

    # ========================================================================
    # Order Operations
    # ========================================================================

    async def create_order(self, order: Order) -> Order:
        """
        Create new order.

        1. Write to Redis (fast, real-time)
        2. Publish event for PostgreSQL sync
        """
        start = time.time()

        # Generate ID if not set
        if not order.order_id:
            order.order_id = str(uuid.uuid4())

        order.created_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)

        # Write to Redis first (fast path)
        await self.redis_store.set_order(order)
        self.metrics.redis_latency_ms = (time.time() - start) * 1000

        # Publish event for PostgreSQL sync
        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ORDER_CREATED,
            entity_type="order",
            entity_id=order.order_id,
            timestamp=datetime.now(timezone.utc),
            data=order.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        # Audit log
        self._log_audit("order_created", order.order_id, order.to_dict())

        logger.info(f"Order created: {order.order_id}")
        return order

    async def update_order(self, order: Order) -> Order:
        """Update existing order."""
        start = time.time()
        order.updated_at = datetime.now(timezone.utc)

        # Update Redis
        await self.redis_store.set_order(order)
        self.metrics.redis_latency_ms = (time.time() - start) * 1000

        # Publish sync event
        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ORDER_UPDATED,
            entity_type="order",
            entity_id=order.order_id,
            timestamp=datetime.now(timezone.utc),
            data=order.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        self._log_audit("order_updated", order.order_id, order.to_dict())
        return order

    async def get_order(
        self, order_id: str, source: StateSource = StateSource.REDIS
    ) -> Optional[Order]:
        """
        Get order by ID.

        By default reads from Redis for speed.
        Use source=POSTGRES for guaranteed consistency.
        """
        start = time.time()

        if source == StateSource.REDIS:
            order = await self.redis_store.get_order(order_id)
            self.metrics.redis_latency_ms = (time.time() - start) * 1000
        else:
            order = await self.postgres_store.get_order(order_id)
            self.metrics.postgres_latency_ms = (time.time() - start) * 1000

        return order

    async def list_orders(
        self,
        symbol: Optional[str] = None,
        source: StateSource = StateSource.REDIS,
    ) -> List[Order]:
        """List orders."""
        if source == StateSource.REDIS:
            return await self.redis_store.list_orders(symbol)
        return await self.postgres_store.list_orders(symbol)

    async def cancel_order(self, order_id: str) -> Optional[Order]:
        """Cancel order."""
        order = await self.get_order(order_id)
        if not order:
            return None

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)

        await self.redis_store.set_order(order)

        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ORDER_CANCELLED,
            entity_type="order",
            entity_id=order.order_id,
            timestamp=datetime.now(timezone.utc),
            data=order.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        self._log_audit("order_cancelled", order.order_id, order.to_dict())
        return order

    # ========================================================================
    # Position Operations
    # ========================================================================

    async def open_position(self, position: Position) -> Position:
        """Open new position."""
        if not position.position_id:
            position.position_id = str(uuid.uuid4())

        position.created_at = datetime.now(timezone.utc)
        position.updated_at = datetime.now(timezone.utc)

        await self.redis_store.set_position(position)

        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_OPENED,
            entity_type="position",
            entity_id=position.position_id,
            timestamp=datetime.now(timezone.utc),
            data=position.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        self._log_audit("position_opened", position.position_id, position.to_dict())
        return position

    async def update_position(self, position: Position) -> Position:
        """Update position."""
        position.updated_at = datetime.now(timezone.utc)

        # Calculate unrealized PnL
        if position.side == PositionSide.LONG:
            position.unrealized_pnl = (
                position.current_price - position.entry_price
            ) * position.quantity
        elif position.side == PositionSide.SHORT:
            position.unrealized_pnl = (
                position.entry_price - position.current_price
            ) * position.quantity

        await self.redis_store.set_position(position)

        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_UPDATED,
            entity_type="position",
            entity_id=position.position_id,
            timestamp=datetime.now(timezone.utc),
            data=position.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        return position

    async def close_position(
        self, position_id: str, close_price: float
    ) -> Optional[Position]:
        """Close position."""
        position = await self.redis_store.get_position(position_id)
        if not position:
            return None

        # Calculate realized PnL
        if position.side == PositionSide.LONG:
            position.realized_pnl = (
                close_price - position.entry_price
            ) * position.quantity
        elif position.side == PositionSide.SHORT:
            position.realized_pnl = (
                position.entry_price - close_price
            ) * position.quantity

        position.current_price = close_price
        position.quantity = 0
        position.side = PositionSide.FLAT
        position.updated_at = datetime.now(timezone.utc)

        await self.redis_store.set_position(position)

        event = StateEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_CLOSED,
            entity_type="position",
            entity_id=position.position_id,
            timestamp=datetime.now(timezone.utc),
            data=position.to_dict(),
            source=StateSource.REDIS,
        )
        await self.event_queue.publish(event)

        self._log_audit("position_closed", position.position_id, position.to_dict())
        return position

    async def get_position(
        self, position_id: str, source: StateSource = StateSource.REDIS
    ) -> Optional[Position]:
        """Get position by ID."""
        if source == StateSource.REDIS:
            return await self.redis_store.get_position(position_id)
        return await self.postgres_store.get_position(position_id)

    async def list_positions(
        self,
        symbol: Optional[str] = None,
        source: StateSource = StateSource.REDIS,
    ) -> List[Position]:
        """List positions."""
        if source == StateSource.REDIS:
            return await self.redis_store.list_positions(symbol)
        return await self.postgres_store.list_positions(symbol)

    # ========================================================================
    # Synchronization
    # ========================================================================

    async def sync_state(self) -> Dict[str, Any]:
        """
        Synchronize state between Redis and PostgreSQL.

        1. Process pending events
        2. Detect conflicts
        3. Resolve conflicts
        4. Update metrics
        """
        start = time.time()
        results = {
            "synced_orders": 0,
            "synced_positions": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "errors": [],
        }

        try:
            # Process pending events first
            await self.event_queue.process_events()

            # Sync orders
            redis_orders = await self.redis_store.list_orders()
            for order in redis_orders:
                try:
                    postgres_order = await self.postgres_store.get_order(order.order_id)

                    if postgres_order is None:
                        # New order, sync to PostgreSQL
                        await self.postgres_store.set_order(order)
                        results["synced_orders"] += 1
                    else:
                        # Check for conflict
                        conflict = await self._check_order_conflict(
                            order, postgres_order
                        )
                        if conflict:
                            results["conflicts_detected"] += 1
                            resolved = await self._resolve_conflict(conflict)
                            if resolved:
                                results["conflicts_resolved"] += 1
                        else:
                            # No conflict, sync latest
                            if order.updated_at > postgres_order.updated_at:
                                await self.postgres_store.set_order(order)
                                results["synced_orders"] += 1
                except Exception as e:
                    results["errors"].append(f"Order {order.order_id}: {str(e)}")

            # Sync positions
            redis_positions = await self.redis_store.list_positions()
            for position in redis_positions:
                try:
                    postgres_position = await self.postgres_store.get_position(
                        position.position_id
                    )

                    if postgres_position is None:
                        await self.postgres_store.set_position(position)
                        results["synced_positions"] += 1
                    else:
                        conflict = await self._check_position_conflict(
                            position, postgres_position
                        )
                        if conflict:
                            results["conflicts_detected"] += 1
                            resolved = await self._resolve_conflict(conflict)
                            if resolved:
                                results["conflicts_resolved"] += 1
                        else:
                            if position.updated_at > postgres_position.updated_at:
                                await self.postgres_store.set_position(position)
                                results["synced_positions"] += 1
                except Exception as e:
                    results["errors"].append(
                        f"Position {position.position_id}: {str(e)}"
                    )

            # Update metrics
            self.metrics.last_sync = datetime.now(timezone.utc)
            self.metrics.sync_latency_ms = (time.time() - start) * 1000
            self.metrics.orders_in_redis = len(redis_orders)
            self.metrics.orders_in_postgres = len(
                await self.postgres_store.list_orders()
            )
            self.metrics.positions_in_redis = len(redis_positions)
            self.metrics.positions_in_postgres = len(
                await self.postgres_store.list_positions()
            )
            self.metrics.pending_events = self.event_queue.pending_count
            self.metrics.conflicts_detected += results["conflicts_detected"]
            self.metrics.conflicts_resolved += results["conflicts_resolved"]

        except Exception as e:
            logger.error(f"Sync error: {e}")
            results["errors"].append(str(e))

        return results

    async def _check_order_conflict(
        self, redis_order: Order, postgres_order: Order
    ) -> Optional[StateConflict]:
        """Check for order conflict."""
        # Generate state hash for comparison
        redis_hash = self._hash_order(redis_order)
        postgres_hash = self._hash_order(postgres_order)

        if redis_hash != postgres_hash:
            # Conflict exists if both were updated after last sync
            if self.metrics.last_sync:
                if (
                    redis_order.updated_at > self.metrics.last_sync
                    and postgres_order.updated_at > self.metrics.last_sync
                ):
                    conflict = StateConflict(
                        conflict_id=str(uuid.uuid4()),
                        entity_type="order",
                        entity_id=redis_order.order_id,
                        redis_state=redis_order.to_dict(),
                        postgres_state=postgres_order.to_dict(),
                        redis_timestamp=redis_order.updated_at,
                        postgres_timestamp=postgres_order.updated_at,
                    )
                    self._conflicts[conflict.conflict_id] = conflict
                    return conflict
        return None

    async def _check_position_conflict(
        self, redis_pos: Position, postgres_pos: Position
    ) -> Optional[StateConflict]:
        """Check for position conflict."""
        redis_hash = self._hash_position(redis_pos)
        postgres_hash = self._hash_position(postgres_pos)

        if redis_hash != postgres_hash:
            if self.metrics.last_sync:
                if (
                    redis_pos.updated_at > self.metrics.last_sync
                    and postgres_pos.updated_at > self.metrics.last_sync
                ):
                    conflict = StateConflict(
                        conflict_id=str(uuid.uuid4()),
                        entity_type="position",
                        entity_id=redis_pos.position_id,
                        redis_state=redis_pos.to_dict(),
                        postgres_state=postgres_pos.to_dict(),
                        redis_timestamp=redis_pos.updated_at,
                        postgres_timestamp=postgres_pos.updated_at,
                    )
                    self._conflicts[conflict.conflict_id] = conflict
                    return conflict
        return None

    async def _resolve_conflict(self, conflict: StateConflict) -> bool:
        """Resolve state conflict."""
        try:
            if self.conflict_resolution == ConflictResolution.LATEST_WINS:
                if conflict.redis_timestamp > conflict.postgres_timestamp:
                    winner = conflict.redis_state
                else:
                    winner = conflict.postgres_state
            elif self.conflict_resolution == ConflictResolution.REDIS_WINS:
                winner = conflict.redis_state
            elif self.conflict_resolution == ConflictResolution.POSTGRES_WINS:
                winner = conflict.postgres_state
            else:
                # Manual resolution required
                logger.warning(
                    f"Manual conflict resolution required: {conflict.conflict_id}"
                )
                return False

            # Apply winner to both stores
            if conflict.entity_type == "order":
                order = Order.from_dict(winner)
                await self.redis_store.set_order(order)
                await self.postgres_store.set_order(order)
            elif conflict.entity_type == "position":
                position = Position.from_dict(winner)
                await self.redis_store.set_position(position)
                await self.postgres_store.set_position(position)

            conflict.resolved = True
            conflict.resolution = self.conflict_resolution
            conflict.resolved_at = datetime.now(timezone.utc)

            self._log_audit(
                "conflict_resolved",
                conflict.entity_id,
                {
                    "conflict_id": conflict.conflict_id,
                    "resolution": self.conflict_resolution.value,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Conflict resolution error: {e}")
            return False

    def _hash_order(self, order: Order) -> str:
        """Generate hash for order comparison."""
        key_fields = f"{order.status}:{order.filled_quantity}:{order.average_price}"
        return hashlib.md5(key_fields.encode()).hexdigest()

    def _hash_position(self, position: Position) -> str:
        """Generate hash for position comparison."""
        key_fields = f"{position.quantity}:{position.side}:{position.entry_price}"
        return hashlib.md5(key_fields.encode()).hexdigest()

    # ========================================================================
    # Background Tasks
    # ========================================================================

    async def _sync_loop(self):
        """Background sync loop."""
        while self._running:
            try:
                await asyncio.sleep(self.sync_interval)
                await self.sync_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")

    async def _event_processor_loop(self):
        """Background event processor loop."""
        while self._running:
            try:
                await asyncio.sleep(1)  # Process events every second
                await self.event_queue.process_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event processor error: {e}")

    # ========================================================================
    # Audit and Metrics
    # ========================================================================

    def _log_audit(self, action: str, entity_id: str, data: Dict[str, Any]):
        """Log audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "entity_id": entity_id,
            "data": data,
        }
        self._audit_log.append(entry)

        # Keep last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]

    def get_metrics(self) -> StateMetrics:
        """Get current metrics."""
        return self.metrics

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        return self._audit_log[-limit:]

    def get_conflicts(self, resolved: Optional[bool] = None) -> List[StateConflict]:
        """Get conflict list."""
        conflicts = list(self._conflicts.values())
        if resolved is not None:
            conflicts = [c for c in conflicts if c.resolved == resolved]
        return conflicts

    def get_health(self) -> Dict[str, Any]:
        """Get service health status."""
        return {
            "status": "healthy" if self._running else "stopped",
            "running": self._running,
            "metrics": {
                "orders_in_redis": self.metrics.orders_in_redis,
                "orders_in_postgres": self.metrics.orders_in_postgres,
                "positions_in_redis": self.metrics.positions_in_redis,
                "positions_in_postgres": self.metrics.positions_in_postgres,
                "pending_events": self.metrics.pending_events,
                "conflicts_detected": self.metrics.conflicts_detected,
                "conflicts_resolved": self.metrics.conflicts_resolved,
                "last_sync": self.metrics.last_sync.isoformat()
                if self.metrics.last_sync
                else None,
                "sync_latency_ms": self.metrics.sync_latency_ms,
            },
            "event_queue": {
                "pending": self.event_queue.pending_count,
                "dead_letter": self.event_queue.dead_letter_count,
            },
        }

    # ========================================================================
    # Snapshot & Recovery (Data Integrity)
    # ========================================================================

    async def create_snapshot(
        self, snapshot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a full state snapshot for disaster recovery.

        Captures:
        - All orders (from both Redis and PostgreSQL)
        - All positions
        - Pending events
        - Current metrics
        - Audit log

        Returns:
            Snapshot dictionary with all state data
        """
        snapshot_id = snapshot_id or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        logger.info(f"Creating state snapshot: {snapshot_id}")

        try:
            # Collect orders from Redis
            redis_orders = await self.redis_store.list_orders()
            redis_orders_dict = [o.to_dict() for o in redis_orders]

            # Collect orders from PostgreSQL
            postgres_orders = await self.postgres_store.list_orders()
            postgres_orders_dict = [o.to_dict() for o in postgres_orders]

            # Collect positions from Redis
            redis_positions = await self.redis_store.list_positions()
            redis_positions_dict = [p.to_dict() for p in redis_positions]

            # Collect positions from PostgreSQL
            postgres_positions = await self.postgres_store.list_positions()
            postgres_positions_dict = [p.to_dict() for p in postgres_positions]

            # Collect pending events
            pending_events = [e.to_dict() for e in self.event_queue._queue]

            # Collect conflicts
            conflicts = [
                {
                    "conflict_id": c.conflict_id,
                    "entity_type": c.entity_type,
                    "entity_id": c.entity_id,
                    "resolved": c.resolved,
                    "resolution": c.resolution.value if c.resolution else None,
                }
                for c in self._conflicts.values()
            ]

            snapshot = {
                "snapshot_id": snapshot_id,
                "created_at": timestamp.isoformat(),
                "version": "1.0",
                "state": {
                    "redis": {
                        "orders": redis_orders_dict,
                        "positions": redis_positions_dict,
                    },
                    "postgres": {
                        "orders": postgres_orders_dict,
                        "positions": postgres_positions_dict,
                    },
                },
                "events": {
                    "pending": pending_events,
                    "dead_letter_count": self.event_queue.dead_letter_count,
                },
                "conflicts": conflicts,
                "metrics": {
                    "orders_in_redis": len(redis_orders),
                    "orders_in_postgres": len(postgres_orders),
                    "positions_in_redis": len(redis_positions),
                    "positions_in_postgres": len(postgres_positions),
                    "pending_events": len(pending_events),
                },
                "audit_log_count": len(self._audit_log),
                "checksum": self._calculate_checksum(
                    redis_orders_dict, postgres_positions_dict
                ),
            }

            self._log_audit(
                "snapshot_created", snapshot_id, {"metrics": snapshot["metrics"]}
            )
            logger.info(
                f"Snapshot created: {snapshot_id} with {len(redis_orders)} orders, {len(redis_positions)} positions"
            )

            return snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise

    async def restore_from_snapshot(
        self, snapshot: Dict[str, Any], target: str = "redis"
    ) -> bool:
        """
        Restore state from a snapshot.

        Args:
            snapshot: Snapshot dictionary from create_snapshot()
            target: Target store ("redis" or "postgres" or "both")

        Returns:
            True if restoration successful
        """
        snapshot_id = snapshot.get("snapshot_id", "unknown")
        logger.info(f"Restoring from snapshot: {snapshot_id} to {target}")

        try:
            state = snapshot.get("state", {})

            if target in ("redis", "both"):
                # Restore Redis state
                redis_state = state.get("redis", {})

                for order_data in redis_state.get("orders", []):
                    order = Order.from_dict(order_data)
                    await self.redis_store.set_order(order)

                for position_data in redis_state.get("positions", []):
                    position = Position.from_dict(position_data)
                    await self.redis_store.set_position(position)

                logger.info(
                    f"Redis restored: {len(redis_state.get('orders', []))} orders, {len(redis_state.get('positions', []))} positions"
                )

            if target in ("postgres", "both"):
                # Restore PostgreSQL state
                postgres_state = state.get("postgres", {})

                for order_data in postgres_state.get("orders", []):
                    order = Order.from_dict(order_data)
                    await self.postgres_store.set_order(order)

                for position_data in postgres_state.get("positions", []):
                    position = Position.from_dict(position_data)
                    await self.postgres_store.set_position(position)

                logger.info(
                    f"PostgreSQL restored: {len(postgres_state.get('orders', []))} orders, {len(postgres_state.get('positions', []))} positions"
                )

            self._log_audit("snapshot_restored", snapshot_id, {"target": target})
            logger.info(f"Snapshot restoration complete: {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return False

    def _calculate_checksum(self, orders: List[Dict], positions: List[Dict]) -> str:
        """Calculate checksum for data integrity verification."""
        import json

        data = json.dumps({"orders": orders, "positions": positions}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    async def verify_data_integrity(self) -> Dict[str, Any]:
        """
        Verify data integrity between Redis and PostgreSQL.

        Returns:
            Integrity report with any discrepancies found
        """
        logger.info("Verifying data integrity...")

        redis_orders = await self.redis_store.list_orders()
        postgres_orders = await self.postgres_store.list_orders()

        redis_positions = await self.redis_store.list_positions()
        postgres_positions = await self.postgres_store.list_positions()

        # Build ID sets
        redis_order_ids = {o.order_id for o in redis_orders}
        postgres_order_ids = {o.order_id for o in postgres_orders}

        redis_position_ids = {p.position_id for p in redis_positions}
        postgres_position_ids = {p.position_id for p in postgres_positions}

        # Find discrepancies
        orders_only_in_redis = redis_order_ids - postgres_order_ids
        orders_only_in_postgres = postgres_order_ids - redis_order_ids

        positions_only_in_redis = redis_position_ids - postgres_position_ids
        positions_only_in_postgres = postgres_position_ids - redis_position_ids

        is_consistent = (
            len(orders_only_in_redis) == 0
            and len(orders_only_in_postgres) == 0
            and len(positions_only_in_redis) == 0
            and len(positions_only_in_postgres) == 0
        )

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_consistent": is_consistent,
            "summary": {
                "redis_orders": len(redis_orders),
                "postgres_orders": len(postgres_orders),
                "redis_positions": len(redis_positions),
                "postgres_positions": len(postgres_positions),
            },
            "discrepancies": {
                "orders_only_in_redis": list(orders_only_in_redis),
                "orders_only_in_postgres": list(orders_only_in_postgres),
                "positions_only_in_redis": list(positions_only_in_redis),
                "positions_only_in_postgres": list(positions_only_in_postgres),
            },
            "recommendation": "No action needed"
            if is_consistent
            else "Run sync_state() to reconcile",
        }

        if not is_consistent:
            logger.warning(f"Data integrity issues found: {report['discrepancies']}")
        else:
            logger.info("Data integrity verified: consistent")

        return report


# ============================================================================
# Module-level accessor
# ============================================================================


def get_state_manager() -> UnifiedStateManager:
    """Get singleton state manager instance."""
    return UnifiedStateManager.get_instance()
