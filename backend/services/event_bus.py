"""
Event Bus Service for Event-Driven Architecture.

Provides centralized pub/sub messaging for decoupling microservices.
Supports Redis-based distributed events and local in-memory events.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Event Types and Enums
# ============================================================================


class EventPriority(Enum):
    """Event priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class EventCategory(Enum):
    """Event categories for routing."""

    TRADING = "trading"
    MARKET_DATA = "market_data"
    RISK = "risk"
    SYSTEM = "system"
    ML = "ml"
    MONITORING = "monitoring"
    USER = "user"


# ============================================================================
# Event Data Classes
# ============================================================================


@dataclass
class Event:
    """Base event class."""

    event_type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    category: EventCategory = EventCategory.SYSTEM
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: str | None = None
    source_service: str = "main"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "source_service": self.source_service,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data["event_type"],
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else datetime.now(UTC),
            category=EventCategory(data.get("category", "system")),
            priority=EventPriority(data.get("priority", 5)),
            correlation_id=data.get("correlation_id"),
            source_service=data.get("source_service", "unknown"),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Serialize event to JSON."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """Deserialize event from JSON."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class EventSubscription:
    """Event subscription details."""

    subscription_id: str
    event_pattern: str  # Supports wildcards: "trading.*", "*.created"
    handler: Callable[[Event], Coroutine[Any, Any, None]]
    filter_fn: Callable[[Event], bool] | None = None
    priority: EventPriority = EventPriority.NORMAL
    max_retries: int = 3
    timeout_seconds: float = 30.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ============================================================================
# Event Bus Interfaces
# ============================================================================


class EventBusBackend(ABC):
    """Abstract base class for event bus backends."""

    @abstractmethod
    async def publish(self, channel: str, event: Event) -> bool:
        """Publish event to channel."""
        pass

    @abstractmethod
    async def subscribe(
        self, pattern: str, handler: Callable[[Event], Coroutine[Any, Any, None]]
    ) -> str:
        """Subscribe to event pattern, returns subscription ID."""
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close backend connections."""
        pass


# ============================================================================
# In-Memory Event Bus (for local/testing)
# ============================================================================


class InMemoryEventBus(EventBusBackend):
    """In-memory event bus for single-process deployment."""

    def __init__(self):
        self._subscriptions: dict[str, EventSubscription] = {}
        self._pattern_handlers: dict[str, list[str]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history = 1000
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "delivery_failures": 0,
        }

    async def publish(self, channel: str, event: Event) -> bool:
        """Publish event to matching subscribers."""
        try:
            self._stats["events_published"] += 1
            self._event_history.append(event)

            # Trim history
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history :]

            # Find matching subscriptions
            matching_subs = self._find_matching_subscriptions(channel)

            # Deliver to all matching handlers
            delivery_tasks = []
            for sub_id in matching_subs:
                sub = self._subscriptions.get(sub_id)
                if sub:
                    # Apply filter if exists
                    if sub.filter_fn and not sub.filter_fn(event):
                        continue
                    delivery_tasks.append(self._deliver_event(sub, event))

            if delivery_tasks:
                results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        self._stats["delivery_failures"] += 1
                        logger.error(f"Event delivery failed: {result}")
                    else:
                        self._stats["events_delivered"] += 1

            return True

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    async def _deliver_event(self, sub: EventSubscription, event: Event) -> None:
        """Deliver event to subscription handler with retry."""
        last_error = None
        for attempt in range(sub.max_retries):
            try:
                await asyncio.wait_for(sub.handler(event), timeout=sub.timeout_seconds)
                return
            except TimeoutError:
                last_error = TimeoutError(
                    f"Handler timeout after {sub.timeout_seconds}s"
                )
                logger.warning(
                    f"Handler timeout, attempt {attempt + 1}/{sub.max_retries}"
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Handler error: {e}, attempt {attempt + 1}/{sub.max_retries}"
                )
            await asyncio.sleep(0.1 * (attempt + 1))  # Backoff

        raise last_error or Exception("Unknown delivery error")

    def _find_matching_subscriptions(self, channel: str) -> list[str]:
        """Find subscriptions matching channel using wildcard patterns."""
        matching = []
        channel_parts = channel.split(".")

        for pattern, sub_ids in self._pattern_handlers.items():
            pattern_parts = pattern.split(".")

            if self._pattern_matches(pattern_parts, channel_parts):
                matching.extend(sub_ids)

        return matching

    def _pattern_matches(
        self, pattern_parts: list[str], channel_parts: list[str]
    ) -> bool:
        """Check if pattern matches channel (supports * and ** wildcards)."""
        if len(pattern_parts) == 0 and len(channel_parts) == 0:
            return True

        if len(pattern_parts) == 0:
            return False

        if pattern_parts[0] == "**":
            # ** matches any number of parts
            if len(pattern_parts) == 1:
                return True
            for i in range(len(channel_parts) + 1):
                if self._pattern_matches(pattern_parts[1:], channel_parts[i:]):
                    return True
            return False

        if len(channel_parts) == 0:
            return False

        if pattern_parts[0] == "*" or pattern_parts[0] == channel_parts[0]:
            return self._pattern_matches(pattern_parts[1:], channel_parts[1:])

        return False

    async def subscribe(
        self, pattern: str, handler: Callable[[Event], Coroutine[Any, Any, None]]
    ) -> str:
        """Subscribe to event pattern."""
        sub_id = str(uuid.uuid4())
        subscription = EventSubscription(
            subscription_id=sub_id,
            event_pattern=pattern,
            handler=handler,
        )
        self._subscriptions[sub_id] = subscription
        self._pattern_handlers[pattern].append(sub_id)
        logger.info(f"Subscribed to '{pattern}' with ID {sub_id}")
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id not in self._subscriptions:
            return False

        sub = self._subscriptions.pop(subscription_id)
        if sub.event_pattern in self._pattern_handlers:
            self._pattern_handlers[sub.event_pattern].remove(subscription_id)
            if not self._pattern_handlers[sub.event_pattern]:
                del self._pattern_handlers[sub.event_pattern]

        logger.info(f"Unsubscribed {subscription_id}")
        return True

    async def close(self) -> None:
        """Close in-memory bus (no-op)."""
        self._subscriptions.clear()
        self._pattern_handlers.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get bus statistics."""
        return {
            **self._stats,
            "active_subscriptions": len(self._subscriptions),
            "patterns_registered": len(self._pattern_handlers),
            "history_size": len(self._event_history),
        }


# ============================================================================
# Redis Event Bus (for distributed deployment)
# ============================================================================


class RedisEventBus(EventBusBackend):
    """Redis-based event bus for distributed microservices."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Any | None = None
        self._pubsub: Any | None = None
        self._subscriptions: dict[str, EventSubscription] = {}
        self._listener_task: asyncio.Task[None] | None = None
        self._running = False
        self._stats = {
            "events_published": 0,
            "events_received": 0,
            "publish_failures": 0,
        }

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis

            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self._pubsub = self._redis.pubsub()
            self._running = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using mock")
            self._redis = None
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis = None

    async def publish(self, channel: str, event: Event) -> bool:
        """Publish event to Redis channel."""
        if not self._redis:
            logger.warning("Redis not connected, event not published")
            return False

        try:
            message = event.to_json()
            await self._redis.publish(channel, message)
            self._stats["events_published"] += 1
            logger.debug(f"Published event {event.event_id} to {channel}")
            return True
        except Exception as e:
            self._stats["publish_failures"] += 1
            logger.error(f"Failed to publish event: {e}")
            return False

    async def subscribe(
        self, pattern: str, handler: Callable[[Event], Coroutine[Any, Any, None]]
    ) -> str:
        """Subscribe to Redis channel pattern."""
        sub_id = str(uuid.uuid4())
        subscription = EventSubscription(
            subscription_id=sub_id,
            event_pattern=pattern,
            handler=handler,
        )
        self._subscriptions[sub_id] = subscription

        if self._pubsub:
            # Use psubscribe for pattern matching
            await self._pubsub.psubscribe(pattern)

            # Start listener if not running
            if not self._listener_task or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._listen_loop())

        logger.info(f"Subscribed to Redis pattern '{pattern}'")
        return sub_id

    async def _listen_loop(self) -> None:
        """Listen for Redis messages."""
        if not self._pubsub:
            return

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "pmessage":
                    self._stats["events_received"] += 1
                    await self._handle_message(message)
            except Exception as e:
                logger.error(f"Error in Redis listener: {e}")
                await asyncio.sleep(1.0)

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming Redis message."""
        try:
            pattern = message.get("pattern", "")
            channel = message.get("channel", "")
            data = message.get("data", "")

            event = Event.from_json(data)

            # Find matching subscriptions
            for sub in self._subscriptions.values():
                if sub.event_pattern == pattern or self._pattern_matches(
                    sub.event_pattern, channel
                ):
                    try:
                        await asyncio.wait_for(
                            sub.handler(event), timeout=sub.timeout_seconds
                        )
                    except Exception as e:
                        logger.error(f"Handler error: {e}")

        except Exception as e:
            logger.error(f"Failed to handle message: {e}")

    def _pattern_matches(self, pattern: str, channel: str) -> bool:
        """Simple pattern matching for Redis patterns."""
        import fnmatch

        return fnmatch.fnmatch(channel, pattern)

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from Redis channel."""
        if subscription_id not in self._subscriptions:
            return False

        sub = self._subscriptions.pop(subscription_id)
        if self._pubsub:
            await self._pubsub.punsubscribe(sub.event_pattern)

        return True

    async def close(self) -> None:
        """Close Redis connections."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    def get_stats(self) -> dict[str, Any]:
        """Get bus statistics."""
        return {
            **self._stats,
            "connected": self._redis is not None,
            "active_subscriptions": len(self._subscriptions),
        }


# ============================================================================
# Main Event Bus Service
# ============================================================================


class EventBusService:
    """
    Main Event Bus Service for the application.

    Provides high-level API for publishing and subscribing to events.
    Automatically selects backend based on configuration.
    """

    def __init__(self, backend: EventBusBackend | None = None):
        self._backend = backend or InMemoryEventBus()
        self._event_handlers: dict[
            str, list[Callable[[Event], Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        self._middleware: list[Callable[[Event], Event]] = []
        self._dead_letter_queue: list[Event] = []
        self._started = False

    async def start(self) -> None:
        """Start the event bus service."""
        if isinstance(self._backend, RedisEventBus):
            await self._backend.connect()
        self._started = True
        logger.info("EventBusService started")

    async def stop(self) -> None:
        """Stop the event bus service."""
        await self._backend.close()
        self._started = False
        logger.info("EventBusService stopped")

    def add_middleware(self, middleware: Callable[[Event], Event]) -> None:
        """Add middleware for event processing."""
        self._middleware.append(middleware)

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        category: EventCategory = EventCategory.SYSTEM,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str | None = None,
    ) -> Event:
        """Publish an event."""
        event = Event(
            event_type=event_type,
            payload=payload,
            category=category,
            priority=priority,
            correlation_id=correlation_id,
        )

        # Apply middleware
        for mw in self._middleware:
            event = mw(event)

        # Publish to backend
        channel = f"{category.value}.{event_type}"
        success = await self._backend.publish(channel, event)

        if not success:
            self._dead_letter_queue.append(event)
            logger.warning(f"Event {event.event_id} added to dead letter queue")

        return event

    async def subscribe(
        self,
        event_pattern: str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> str:
        """Subscribe to events matching pattern."""
        return await self._backend.subscribe(event_pattern, handler)

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        return await self._backend.unsubscribe(subscription_id)

    def on(
        self, event_type: str
    ) -> Callable[
        [Callable[[Event], Coroutine[Any, Any, None]]],
        Callable[[Event], Coroutine[Any, Any, None]],
    ]:
        """Decorator for event handlers."""

        def decorator(
            handler: Callable[[Event], Coroutine[Any, Any, None]],
        ) -> Callable[[Event], Coroutine[Any, Any, None]]:
            self._event_handlers[event_type].append(handler)
            return handler

        return decorator

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        backend_stats = {}
        if hasattr(self._backend, "get_stats"):
            backend_stats = self._backend.get_stats()

        return {
            "started": self._started,
            "middleware_count": len(self._middleware),
            "dead_letter_queue_size": len(self._dead_letter_queue),
            "registered_handlers": {k: len(v) for k, v in self._event_handlers.items()},
            "backend": backend_stats,
        }

    async def replay_dead_letters(self) -> int:
        """Replay events from dead letter queue."""
        replayed = 0
        while self._dead_letter_queue:
            event = self._dead_letter_queue.pop(0)
            channel = f"{event.category.value}.{event.event_type}"
            if await self._backend.publish(channel, event):
                replayed += 1
        return replayed


# ============================================================================
# Predefined Trading Events
# ============================================================================


class TradingEvents:
    """Predefined trading event types."""

    # Order events
    ORDER_CREATED = "order.created"
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"

    # Position events
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_UPDATED = "position.updated"

    # Market events
    PRICE_UPDATE = "market.price_update"
    CANDLE_CLOSED = "market.candle_closed"
    VOLATILITY_SPIKE = "market.volatility_spike"

    # Risk events
    RISK_LIMIT_APPROACHED = "risk.limit_approached"
    RISK_LIMIT_BREACHED = "risk.limit_breached"
    DRAWDOWN_ALERT = "risk.drawdown_alert"

    # System events
    SERVICE_STARTED = "system.service_started"
    SERVICE_STOPPED = "system.service_stopped"
    HEALTH_CHECK = "system.health_check"


# ============================================================================
# Global Instance
# ============================================================================

# Singleton event bus instance
_event_bus: EventBusService | None = None


def get_event_bus() -> EventBusService:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBusService()
    return _event_bus


async def init_event_bus(redis_url: str | None = None) -> EventBusService:
    """Initialize the global event bus with optional Redis backend."""
    global _event_bus
    if redis_url:
        backend = RedisEventBus(redis_url)
        _event_bus = EventBusService(backend)
    else:
        _event_bus = EventBusService()
    await _event_bus.start()
    return _event_bus
