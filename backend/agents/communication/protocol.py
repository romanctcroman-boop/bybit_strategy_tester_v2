"""
Agent Communication Protocol

Standardized communication between AI agents:
- Async pub/sub messaging
- Agent discovery
- Request/response patterns
- Event broadcasting
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger


class MessageType(Enum):
    """Message types"""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class MessagePriority(Enum):
    """Message priorities"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class AgentInfo:
    """Agent registration info"""

    agent_id: str
    agent_type: str
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "status": self.status,
        }


@dataclass
class Message:
    """Communication message"""

    id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    type: MessageType = MessageType.REQUEST
    sender_id: str = ""
    receiver_id: str | None = None  # None for broadcast
    topic: str = ""
    payload: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str | None = None  # For request/response matching
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int | None = None  # Time to live
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "topic": self.topic,
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Create from dictionary"""
        return cls(
            id=data.get("id", f"msg_{uuid.uuid4().hex[:12]}"),
            type=MessageType(data.get("type", "request")),
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id"),
            topic=data.get("topic", ""),
            payload=data.get("payload"),
            priority=MessagePriority(data.get("priority", 2)),
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if data.get("timestamp")
            else datetime.now(UTC),
            ttl_seconds=data.get("ttl_seconds"),
            metadata=data.get("metadata", {}),
        )

    def is_expired(self) -> bool:
        """Check if message has expired"""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now(UTC) - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def create_response(self, payload: Any, error: bool = False) -> Message:
        """Create response message"""
        return Message(
            type=MessageType.ERROR if error else MessageType.RESPONSE,
            sender_id=self.receiver_id or "",
            receiver_id=self.sender_id,
            topic=self.topic,
            payload=payload,
            correlation_id=self.id,
        )


class MessageHandler(ABC):
    """Abstract message handler"""

    @abstractmethod
    async def handle(self, message: Message) -> Any | None:
        """Handle incoming message"""
        pass


@dataclass
class Subscription:
    """Topic subscription"""

    id: str = field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:8]}")
    topic: str = ""
    handler: Callable[[Message], Any] | None = None
    filter_fn: Callable[[Message], bool] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MessageBroker:
    """
    Central message broker for agent communication

    Features:
    - Pub/sub messaging
    - Request/response patterns
    - Topic-based routing
    - Priority queues
    - Message persistence

    Example:
        broker = MessageBroker()

        # Subscribe to topic
        async def handle_trades(msg):
            print(f"Trade: {msg.payload}")

        broker.subscribe("trades", handle_trades)

        # Publish message
        await broker.publish(Message(
            sender_id="agent_1",
            topic="trades",
            payload={"symbol": "BTCUSDT", "action": "buy"},
        ))

        # Request/response
        response = await broker.request(
            receiver_id="agent_2",
            topic="analyze",
            payload={"data": [...]}
        )
    """

    def __init__(self, max_queue_size: int = 10000):
        self._subscriptions: dict[str, list[Subscription]] = {}
        self._agents: dict[str, AgentInfo] = {}
        self._queues: dict[str, asyncio.PriorityQueue] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._message_history: list[Message] = []
        self._max_queue_size = max_queue_size
        self._max_history_size = 1000
        self._running = False
        self._processor_task: asyncio.Task | None = None

        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_expired": 0,
            "requests_sent": 0,
            "requests_completed": 0,
        }

        logger.info("📬 MessageBroker initialized")

    async def start(self) -> None:
        """Start the broker"""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_queues())
        logger.info("📬 MessageBroker started")

    async def stop(self) -> None:
        """Stop the broker"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("📬 MessageBroker stopped")

    def register_agent(self, agent_info: AgentInfo) -> None:
        """Register an agent"""
        self._agents[agent_info.agent_id] = agent_info
        self._queues[agent_info.agent_id] = asyncio.PriorityQueue(self._max_queue_size)
        logger.info(
            f"📥 Registered agent: {agent_info.agent_id} [{agent_info.agent_type}]"
        )

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._queues:
            del self._queues[agent_id]
        logger.info(f"📤 Unregistered agent: {agent_id}")

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get agent by ID"""
        return self._agents.get(agent_id)

    def list_agents(self, agent_type: str | None = None) -> list[AgentInfo]:
        """List registered agents"""
        agents = list(self._agents.values())
        if agent_type:
            agents = [a for a in agents if a.agent_type == agent_type]
        return agents

    def find_agents_by_capability(self, capability: str) -> list[AgentInfo]:
        """Find agents with specific capability"""
        return [
            agent for agent in self._agents.values() if capability in agent.capabilities
        ]

    def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Any],
        filter_fn: Callable[[Message], bool] | None = None,
    ) -> str:
        """Subscribe to topic"""
        sub = Subscription(
            topic=topic,
            handler=handler,
            filter_fn=filter_fn,
        )

        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(sub)

        logger.debug(f"📩 Subscribed to topic: {topic}")
        return sub.id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from topic"""
        for topic, subs in self._subscriptions.items():
            for sub in subs:
                if sub.id == subscription_id:
                    subs.remove(sub)
                    logger.debug(f"📤 Unsubscribed: {subscription_id}")
                    return True
        return False

    async def publish(self, message: Message) -> None:
        """Publish message to topic"""
        self._stats["messages_sent"] += 1

        # Add to history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history_size:
            self._message_history = self._message_history[-self._max_history_size :]

        # Get subscribers
        subscribers = self._subscriptions.get(message.topic, [])

        for sub in subscribers:
            # Apply filter
            if sub.filter_fn and not sub.filter_fn(message):
                continue

            # Call handler
            if sub.handler:
                try:
                    if asyncio.iscoroutinefunction(sub.handler):
                        await sub.handler(message)
                    else:
                        sub.handler(message)
                    self._stats["messages_delivered"] += 1
                except Exception as e:
                    logger.error(f"Handler error for topic {message.topic}: {e}")

    async def send(self, message: Message) -> None:
        """Send message to specific agent"""
        if not message.receiver_id:
            raise ValueError("receiver_id required for direct send")

        if message.receiver_id not in self._queues:
            raise KeyError(f"Unknown agent: {message.receiver_id}")

        queue = self._queues[message.receiver_id]

        # Priority tuple: (priority_value, timestamp, message)
        priority_item = (
            -message.priority.value,  # Negative for highest first
            message.timestamp.timestamp(),
            message,
        )

        await queue.put(priority_item)
        self._stats["messages_sent"] += 1

    async def broadcast(self, message: Message) -> None:
        """Broadcast message to all agents"""
        message.type = MessageType.BROADCAST
        message.receiver_id = None

        for agent_id in self._queues:
            msg_copy = Message(
                type=message.type,
                sender_id=message.sender_id,
                receiver_id=agent_id,
                topic=message.topic,
                payload=message.payload,
                priority=message.priority,
                correlation_id=message.correlation_id,
                ttl_seconds=message.ttl_seconds,
                metadata=message.metadata.copy(),
            )
            await self.send(msg_copy)

    async def request(
        self,
        sender_id: str,
        receiver_id: str,
        topic: str,
        payload: Any,
        timeout_seconds: float = 30.0,
    ) -> Any:
        """Send request and wait for response"""
        message = Message(
            type=MessageType.REQUEST,
            sender_id=sender_id,
            receiver_id=receiver_id,
            topic=topic,
            payload=payload,
            priority=MessagePriority.HIGH,
        )

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[message.id] = future

        self._stats["requests_sent"] += 1

        # Send message
        await self.send(message)

        try:
            result = await asyncio.wait_for(future, timeout=timeout_seconds)
            self._stats["requests_completed"] += 1
            return result
        except TimeoutError:
            self._pending_requests.pop(message.id, None)
            raise TimeoutError(f"Request to {receiver_id} timed out")

    async def respond(self, original_message: Message, response_payload: Any) -> None:
        """Send response to request"""
        response = original_message.create_response(response_payload)

        # Check for pending request
        if original_message.id in self._pending_requests:
            future = self._pending_requests.pop(original_message.id)
            future.set_result(response_payload)
        else:
            # Send as regular message
            await self.send(response)

    async def receive(
        self,
        agent_id: str,
        timeout_seconds: float | None = None,
    ) -> Message | None:
        """Receive next message for agent"""
        if agent_id not in self._queues:
            raise KeyError(f"Unknown agent: {agent_id}")

        queue = self._queues[agent_id]

        try:
            if timeout_seconds:
                _, _, message = await asyncio.wait_for(
                    queue.get(), timeout=timeout_seconds
                )
            else:
                _, _, message = await queue.get()

            # Check expiration
            if message.is_expired():
                self._stats["messages_expired"] += 1
                return None

            # Update agent last seen
            if agent_id in self._agents:
                self._agents[agent_id].last_seen = datetime.now(UTC)

            self._stats["messages_delivered"] += 1
            return message

        except TimeoutError:
            return None

    async def _process_queues(self) -> None:
        """Background queue processor"""
        while self._running:
            await asyncio.sleep(0.1)

            # Handle responses for pending requests
            for msg_id, future in list(self._pending_requests.items()):
                if future.done():
                    self._pending_requests.pop(msg_id, None)

    def get_stats(self) -> dict[str, Any]:
        """Get broker statistics"""
        return {
            **self._stats,
            "registered_agents": len(self._agents),
            "active_subscriptions": sum(len(s) for s in self._subscriptions.values()),
            "pending_requests": len(self._pending_requests),
            "queue_sizes": {
                agent_id: queue.qsize() for agent_id, queue in self._queues.items()
            },
        }


class AgentCommunicator:
    """
    Agent-side communication helper

    Simplifies agent communication patterns.

    Example:
        comm = AgentCommunicator(broker, "my_agent")

        # Register handlers
        @comm.on("analyze")
        async def handle_analyze(msg):
            return {"result": "analysis complete"}

        # Start listening
        await comm.start()

        # Send request to another agent
        result = await comm.ask("other_agent", "process", {"data": [...]})
    """

    def __init__(
        self,
        broker: MessageBroker,
        agent_id: str,
        agent_type: str = "generic",
        capabilities: list[str] | None = None,
    ):
        self.broker = broker
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities or []

        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._listener_task: asyncio.Task | None = None

        # Register with broker
        self.broker.register_agent(
            AgentInfo(
                agent_id=agent_id,
                agent_type=agent_type,
                capabilities=self.capabilities,
            )
        )

    def on(self, topic: str) -> Callable:
        """Decorator to register message handler"""

        def decorator(func: Callable) -> Callable:
            self._handlers[topic] = func
            return func

        return decorator

    async def start(self) -> None:
        """Start listening for messages"""
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info(f"🎧 Agent {self.agent_id} started listening")

    async def stop(self) -> None:
        """Stop listening"""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        self.broker.unregister_agent(self.agent_id)
        logger.info(f"🛑 Agent {self.agent_id} stopped")

    async def _listen_loop(self) -> None:
        """Main listening loop"""
        while self._running:
            try:
                message = await self.broker.receive(self.agent_id, timeout_seconds=1.0)
                if message:
                    await self._handle_message(message)
            except Exception as e:
                logger.error(f"Listen error: {e}")

    async def _handle_message(self, message: Message) -> None:
        """Handle incoming message"""
        handler = self._handlers.get(message.topic)

        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)

                # Auto-respond to requests
                if message.type == MessageType.REQUEST:
                    await self.broker.respond(message, result)

            except Exception as e:
                logger.error(f"Handler error for {message.topic}: {e}")
                if message.type == MessageType.REQUEST:
                    await self.broker.respond(
                        message,
                        {"error": str(e)},
                    )
        else:
            logger.warning(f"No handler for topic: {message.topic}")

    async def send(
        self,
        receiver_id: str,
        topic: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """Send message to another agent"""
        message = Message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            topic=topic,
            payload=payload,
            priority=priority,
        )
        await self.broker.send(message)

    async def ask(
        self,
        receiver_id: str,
        topic: str,
        payload: Any,
        timeout_seconds: float = 30.0,
    ) -> Any:
        """Send request and wait for response"""
        return await self.broker.request(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            topic=topic,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

    async def broadcast(self, topic: str, payload: Any) -> None:
        """Broadcast to all agents"""
        await self.broker.broadcast(
            Message(
                sender_id=self.agent_id,
                topic=topic,
                payload=payload,
            )
        )

    async def publish(self, topic: str, payload: Any) -> None:
        """Publish to topic subscribers"""
        await self.broker.publish(
            Message(
                sender_id=self.agent_id,
                topic=topic,
                payload=payload,
            )
        )


# Global broker instance
_global_broker: MessageBroker | None = None


def get_message_broker() -> MessageBroker:
    """Get global message broker"""
    global _global_broker
    if _global_broker is None:
        _global_broker = MessageBroker()
    return _global_broker


__all__ = [
    "AgentCommunicator",
    "AgentInfo",
    "Message",
    "MessageBroker",
    "MessageHandler",
    "MessagePriority",
    "MessageType",
    "Subscription",
    "get_message_broker",
]
