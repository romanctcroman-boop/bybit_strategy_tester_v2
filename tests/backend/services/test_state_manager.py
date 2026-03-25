"""
Tests for UnifiedStateManager

Tests the unified state management service that coordinates state
between Redis (fast access) and PostgreSQL (persistence).
"""

from datetime import UTC, datetime

import pytest


class TestStateSource:
    """Tests for StateSource enum"""

    def test_state_source_values(self):
        """Test StateSource enum values"""
        from backend.services.state_manager import StateSource

        assert StateSource.REDIS.value == "redis"
        assert StateSource.POSTGRES.value == "postgres"
        assert StateSource.LOCAL.value == "local"


class TestEventType:
    """Tests for EventType enum"""

    def test_event_type_order_values(self):
        """Test EventType order-related values"""
        from backend.services.state_manager import EventType

        assert EventType.ORDER_CREATED.value == "order_created"
        assert EventType.ORDER_UPDATED.value == "order_updated"
        assert EventType.ORDER_FILLED.value == "order_filled"
        assert EventType.ORDER_CANCELLED.value == "order_cancelled"

    def test_event_type_position_values(self):
        """Test EventType position-related values"""
        from backend.services.state_manager import EventType

        assert EventType.POSITION_OPENED.value == "position_opened"
        assert EventType.POSITION_UPDATED.value == "position_updated"
        assert EventType.POSITION_CLOSED.value == "position_closed"


class TestOrderStatus:
    """Tests for OrderStatus enum"""

    def test_order_status_values(self):
        """Test OrderStatus enum values"""
        from backend.services.state_manager import OrderStatus

        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.SUBMITTED.value == "submitted"
        assert OrderStatus.PARTIAL.value == "partial"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.REJECTED.value == "rejected"


class TestPositionSide:
    """Tests for PositionSide enum"""

    def test_position_side_values(self):
        """Test PositionSide enum values"""
        from backend.services.state_manager import PositionSide

        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        assert PositionSide.FLAT.value == "flat"


class TestConflictResolution:
    """Tests for ConflictResolution enum"""

    def test_conflict_resolution_values(self):
        """Test ConflictResolution enum values"""
        from backend.services.state_manager import ConflictResolution

        assert ConflictResolution.LATEST_WINS.value == "latest_wins"
        assert ConflictResolution.REDIS_WINS.value == "redis_wins"
        assert ConflictResolution.POSTGRES_WINS.value == "postgres_wins"
        assert ConflictResolution.MANUAL.value == "manual"


class TestOrderDataclass:
    """Tests for Order dataclass"""

    def test_order_creation(self):
        """Test Order can be created with valid data"""
        from backend.services.state_manager import Order, OrderStatus

        order = Order(
            order_id="order-123",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=1.0,
            price=50000.0,
        )

        assert order.order_id == "order-123"
        assert order.symbol == "BTCUSDT"
        assert order.side == "buy"
        assert order.order_type == "limit"
        assert order.quantity == 1.0
        assert order.price == 50000.0
        assert order.status == OrderStatus.PENDING

    def test_order_to_dict(self):
        """Test Order serialization"""
        from backend.services.state_manager import Order

        order = Order(
            order_id="order-456",
            symbol="ETHUSDT",
            side="sell",
            order_type="market",
            quantity=10.0,
        )

        data = order.to_dict()

        assert data["order_id"] == "order-456"
        assert data["symbol"] == "ETHUSDT"
        assert data["side"] == "sell"
        assert "created_at" in data
        assert "status" in data

    def test_order_from_dict(self):
        """Test Order deserialization"""
        from backend.services.state_manager import Order

        data = {
            "order_id": "order-789",
            "symbol": "SOLUSDT",
            "side": "buy",
            "order_type": "limit",
            "quantity": 100.0,
            "price": 150.0,
            "status": "filled",
            "filled_quantity": 100.0,
            "average_price": 149.5,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:01:00",
        }

        order = Order.from_dict(data)

        assert order.order_id == "order-789"
        assert order.symbol == "SOLUSDT"
        assert order.quantity == 100.0


class TestPositionDataclass:
    """Tests for Position dataclass"""

    def test_position_creation(self):
        """Test Position can be created with valid data"""
        from backend.services.state_manager import Position, PositionSide

        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            quantity=0.5,
            entry_price=48000.0,
        )

        assert position.position_id == "pos-123"
        assert position.symbol == "BTCUSDT"
        assert position.side == PositionSide.LONG
        assert position.quantity == 0.5
        assert position.entry_price == 48000.0

    def test_position_to_dict(self):
        """Test Position serialization"""
        from backend.services.state_manager import Position, PositionSide

        position = Position(
            position_id="pos-456",
            symbol="ETHUSDT",
            side=PositionSide.SHORT,
            quantity=5.0,
            entry_price=3000.0,
        )

        data = position.to_dict()

        assert data["position_id"] == "pos-456"
        assert data["symbol"] == "ETHUSDT"
        assert data["side"] == "short"
        assert "created_at" in data


class TestStateEvent:
    """Tests for StateEvent dataclass"""

    def test_state_event_creation(self):
        """Test StateEvent creation"""
        from backend.services.state_manager import EventType, StateEvent, StateSource

        event = StateEvent(
            event_id="event-123",
            event_type=EventType.ORDER_CREATED,
            entity_type="order",
            entity_id="order-123",
            timestamp=datetime.now(UTC),
            data={"symbol": "BTCUSDT"},
            source=StateSource.REDIS,
        )

        assert event.event_id == "event-123"
        assert event.event_type == EventType.ORDER_CREATED
        assert event.entity_type == "order"
        assert event.processed is False

    def test_state_event_to_dict(self):
        """Test StateEvent serialization"""
        from backend.services.state_manager import EventType, StateEvent, StateSource

        event = StateEvent(
            event_id="event-456",
            event_type=EventType.POSITION_OPENED,
            entity_type="position",
            entity_id="pos-456",
            timestamp=datetime.now(UTC),
            data={"symbol": "ETHUSDT"},
            source=StateSource.POSTGRES,
        )

        data = event.to_dict()

        assert data["event_id"] == "event-456"
        assert data["event_type"] == "position_opened"


class TestStateMetrics:
    """Tests for StateMetrics dataclass"""

    def test_state_metrics_defaults(self):
        """Test StateMetrics default values"""
        from backend.services.state_manager import StateMetrics

        metrics = StateMetrics()

        assert metrics.orders_in_redis == 0
        assert metrics.orders_in_postgres == 0
        assert metrics.pending_events == 0
        assert metrics.conflicts_detected == 0


class TestEventQueue:
    """Tests for EventQueue"""

    def test_event_queue_creation(self):
        """Test EventQueue can be created"""
        from backend.services.state_manager import EventQueue

        queue = EventQueue()

        assert queue is not None
        assert queue.pending_count == 0
        assert queue.dead_letter_count == 0

    @pytest.mark.asyncio
    async def test_event_queue_publish(self):
        """Test publishing event to queue"""
        from backend.services.state_manager import (
            EventQueue,
            EventType,
            StateEvent,
            StateSource,
        )

        queue = EventQueue()

        event = StateEvent(
            event_id="test-event",
            event_type=EventType.ORDER_CREATED,
            entity_type="order",
            entity_id="order-1",
            timestamp=datetime.now(UTC),
            data={},
            source=StateSource.REDIS,
        )

        result = await queue.publish(event)

        assert result is True
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_event_queue_consume(self):
        """Test consuming events from queue"""
        from backend.services.state_manager import (
            EventQueue,
            EventType,
            StateEvent,
            StateSource,
        )

        queue = EventQueue()

        # Publish some events
        for i in range(3):
            event = StateEvent(
                event_id=f"test-event-{i}",
                event_type=EventType.ORDER_CREATED,
                entity_type="order",
                entity_id=f"order-{i}",
                timestamp=datetime.now(UTC),
                data={},
                source=StateSource.REDIS,
            )
            await queue.publish(event)

        events = await queue.consume(batch_size=2)

        assert len(events) == 2
        assert queue.pending_count == 1


class TestInMemoryStateStore:
    """Tests for InMemoryStateStore"""

    def test_store_creation(self):
        """Test InMemoryStateStore can be created"""
        from backend.services.state_manager import InMemoryStateStore

        store = InMemoryStateStore()

        assert store is not None
        assert hasattr(store, "_orders")
        assert hasattr(store, "_positions")

    @pytest.mark.asyncio
    async def test_store_save_and_get_order(self):
        """Test saving and getting order from store"""
        from backend.services.state_manager import InMemoryStateStore, Order

        store = InMemoryStateStore()

        order = Order(
            order_id="store-order-1",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.5,
        )

        await store.set_order(order)
        result = await store.get_order("store-order-1")

        assert result is not None
        assert result.order_id == "store-order-1"

    @pytest.mark.asyncio
    async def test_store_delete_order(self):
        """Test deleting order from store"""
        from backend.services.state_manager import InMemoryStateStore, Order

        store = InMemoryStateStore()

        order = Order(
            order_id="delete-order",
            symbol="ETHUSDT",
            side="sell",
            order_type="market",
            quantity=1.0,
        )

        await store.set_order(order)
        result = await store.delete_order("delete-order")

        assert result is True
        assert await store.get_order("delete-order") is None

    @pytest.mark.asyncio
    async def test_store_list_orders(self):
        """Test listing orders from store"""
        from backend.services.state_manager import InMemoryStateStore, Order

        store = InMemoryStateStore()

        for i in range(3):
            order = Order(
                order_id=f"list-order-{i}",
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                quantity=0.1,
            )
            await store.set_order(order)

        orders = await store.list_orders()

        assert len(orders) == 3

    @pytest.mark.asyncio
    async def test_store_list_orders_by_symbol(self):
        """Test listing orders filtered by symbol"""
        from backend.services.state_manager import InMemoryStateStore, Order

        store = InMemoryStateStore()

        await store.set_order(
            Order(
                order_id="btc-1",
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                quantity=1.0,
            )
        )
        await store.set_order(
            Order(
                order_id="eth-1",
                symbol="ETHUSDT",
                side="buy",
                order_type="limit",
                quantity=1.0,
            )
        )

        btc_orders = await store.list_orders(symbol="BTCUSDT")

        assert len(btc_orders) == 1
        assert btc_orders[0].symbol == "BTCUSDT"


class TestUnifiedStateManagerInit:
    """Tests for UnifiedStateManager initialization"""

    def test_service_creation(self):
        """Test UnifiedStateManager can be created"""
        from backend.services.state_manager import UnifiedStateManager

        manager = UnifiedStateManager()

        assert manager is not None
        assert hasattr(manager, "redis_store")
        assert hasattr(manager, "postgres_store")
        assert hasattr(manager, "event_queue")

    def test_singleton_pattern(self):
        """Test singleton pattern via get_instance"""
        from backend.services.state_manager import UnifiedStateManager

        # Reset singleton
        UnifiedStateManager._instance = None

        manager1 = UnifiedStateManager.get_instance()
        manager2 = UnifiedStateManager.get_instance()

        assert manager1 is manager2

    def test_initial_state(self):
        """Test initial manager state"""
        from backend.services.state_manager import UnifiedStateManager

        manager = UnifiedStateManager()

        assert manager._running is False


class TestUnifiedStateManagerAsync:
    """Tests for async UnifiedStateManager methods"""

    @pytest.mark.asyncio
    async def test_start_stop_service(self):
        """Test starting and stopping the service"""
        from backend.services.state_manager import UnifiedStateManager

        manager = UnifiedStateManager()

        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_create_order(self):
        """Test creating an order"""
        from backend.services.state_manager import Order, UnifiedStateManager

        manager = UnifiedStateManager()

        order = Order(
            order_id="new-order-1",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=50000.0,
        )

        result = await manager.create_order(order)

        assert result is not None
        assert result.order_id == "new-order-1"

    @pytest.mark.asyncio
    async def test_get_order(self):
        """Test getting an order after creation"""
        from backend.services.state_manager import Order, UnifiedStateManager

        manager = UnifiedStateManager()

        order = Order(
            order_id="get-order-test",
            symbol="ETHUSDT",
            side="sell",
            order_type="market",
            quantity=1.0,
        )

        await manager.create_order(order)
        result = await manager.get_order("get-order-test")

        assert result is not None
        assert result.order_id == "get-order-test"
        assert result.symbol == "ETHUSDT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
