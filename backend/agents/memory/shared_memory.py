"""
Shared Memory for Multi-Agent Systems

Provides thread-safe shared state across agents:
- Atomic operations
- Conflict resolution
- Transaction support
- Event notifications
- Cross-agent synchronization
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from loguru import logger


T = TypeVar("T")


class ConflictResolution(Enum):
    """Conflict resolution strategies"""

    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    REJECT = "reject"
    CUSTOM = "custom"


@dataclass
class SharedValue:
    """Value in shared memory with metadata"""

    value: Any
    version: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    lock_holder: Optional[str] = None
    lock_expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "value": self.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
        }


@dataclass
class Transaction:
    """Transaction for atomic operations"""

    id: str = field(default_factory=lambda: f"tx_{uuid.uuid4().hex[:12]}")
    agent_id: Optional[str] = None
    operations: List[Tuple[str, str, Any]] = field(
        default_factory=list
    )  # (op, key, value)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    committed: bool = False

    def set(self, key: str, value: Any) -> "Transaction":
        """Add SET operation"""
        self.operations.append(("SET", key, value))
        return self

    def delete(self, key: str) -> "Transaction":
        """Add DELETE operation"""
        self.operations.append(("DELETE", key, None))
        return self

    def increment(self, key: str, delta: float = 1.0) -> "Transaction":
        """Add INCREMENT operation"""
        self.operations.append(("INCREMENT", key, delta))
        return self


class SharedMemoryEvent(Enum):
    """Shared memory events"""

    SET = "set"
    DELETE = "delete"
    UPDATE = "update"
    LOCK = "lock"
    UNLOCK = "unlock"
    TRANSACTION_COMMIT = "transaction_commit"
    TRANSACTION_ROLLBACK = "transaction_rollback"


@dataclass
class MemoryEvent:
    """Event notification"""

    event_type: SharedMemoryEvent
    key: str
    value: Any
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SharedMemory:
    """
    Thread-safe shared memory for multi-agent systems

    Features:
    - Atomic read/write operations
    - Optimistic locking with versioning
    - Pessimistic locking with timeouts
    - Transaction support
    - Event notifications
    - Conflict resolution strategies

    Example:
        memory = SharedMemory()

        # Basic operations
        await memory.set("agent_1", "counter", 0)
        value = await memory.get("counter")

        # Atomic increment
        await memory.increment("agent_1", "counter", 1)

        # Transactions
        async with memory.transaction("agent_1") as tx:
            tx.set("key1", "value1")
            tx.set("key2", "value2")
            # Auto-commits on exit

        # Subscribe to changes
        async def on_change(event):
            print(f"{event.key} changed to {event.value}")

        memory.subscribe("counter", on_change)
    """

    def __init__(
        self,
        conflict_resolution: ConflictResolution = ConflictResolution.LAST_WRITE_WINS,
        lock_timeout_seconds: int = 30,
    ):
        self._data: Dict[str, SharedValue] = {}
        self._lock = asyncio.Lock()
        self._thread_lock = threading.RLock()

        self.conflict_resolution = conflict_resolution
        self.lock_timeout_seconds = lock_timeout_seconds

        self._subscribers: Dict[str, List[Callable]] = {}  # key -> callbacks
        self._global_subscribers: List[Callable] = []

        self._pending_transactions: Dict[str, Transaction] = {}

        logger.info("🧠 SharedMemory initialized")

    async def set(
        self,
        agent_id: str,
        key: str,
        value: Any,
        expected_version: Optional[int] = None,
    ) -> bool:
        """
        Set value with optional optimistic locking

        Args:
            agent_id: ID of agent making the change
            key: Key to set
            value: Value to set
            expected_version: If provided, only update if version matches

        Returns:
            True if successful, False if version conflict
        """
        async with self._lock:
            now = datetime.now(timezone.utc)

            if key in self._data:
                existing = self._data[key]

                # Check optimistic lock
                if (
                    expected_version is not None
                    and existing.version != expected_version
                ):
                    logger.warning(
                        f"Version conflict on {key}: expected {expected_version}, got {existing.version}"
                    )
                    return False

                # Check pessimistic lock
                if existing.lock_holder and existing.lock_holder != agent_id:
                    if existing.lock_expires_at and existing.lock_expires_at > now:
                        logger.warning(f"Key {key} is locked by {existing.lock_holder}")
                        return False

                # Update existing
                existing.value = value
                existing.version += 1
                existing.updated_at = now
                existing.updated_by = agent_id

            else:
                # Create new
                self._data[key] = SharedValue(
                    value=value,
                    version=1,
                    created_at=now,
                    updated_at=now,
                    updated_by=agent_id,
                )

            # Notify subscribers
            await self._notify(
                MemoryEvent(
                    event_type=SharedMemoryEvent.SET,
                    key=key,
                    value=value,
                    agent_id=agent_id,
                )
            )

            return True

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value by key"""
        async with self._lock:
            if key in self._data:
                return self._data[key].value
            return default

    async def get_with_version(self, key: str) -> Tuple[Any, int]:
        """Get value with version for optimistic locking"""
        async with self._lock:
            if key in self._data:
                sv = self._data[key]
                return sv.value, sv.version
            return None, 0

    async def delete(self, agent_id: str, key: str) -> bool:
        """Delete key"""
        async with self._lock:
            if key in self._data:
                sv = self._data[key]

                # Check lock
                if sv.lock_holder and sv.lock_holder != agent_id:
                    now = datetime.now(timezone.utc)
                    if sv.lock_expires_at and sv.lock_expires_at > now:
                        return False

                del self._data[key]

                await self._notify(
                    MemoryEvent(
                        event_type=SharedMemoryEvent.DELETE,
                        key=key,
                        value=None,
                        agent_id=agent_id,
                    )
                )

                return True
            return False

    async def increment(
        self,
        agent_id: str,
        key: str,
        delta: float = 1.0,
    ) -> float:
        """Atomic increment operation"""
        async with self._lock:
            current = 0.0
            if key in self._data:
                current = float(self._data[key].value)

            new_value = current + delta
            await self.set(agent_id, key, new_value)

            return new_value

    async def compare_and_swap(
        self,
        agent_id: str,
        key: str,
        expected: Any,
        new_value: Any,
    ) -> bool:
        """Atomic compare-and-swap operation"""
        async with self._lock:
            current = self._data.get(key)

            if current is None:
                if expected is None:
                    await self.set(agent_id, key, new_value)
                    return True
                return False

            if current.value == expected:
                await self.set(agent_id, key, new_value)
                return True

            return False

    async def acquire_lock(
        self,
        agent_id: str,
        key: str,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """Acquire pessimistic lock on key"""
        timeout = timeout_seconds or self.lock_timeout_seconds

        async with self._lock:
            now = datetime.now(timezone.utc)
            expires_at = datetime.fromtimestamp(
                now.timestamp() + timeout, tz=timezone.utc
            )

            if key not in self._data:
                self._data[key] = SharedValue(
                    value=None,
                    lock_holder=agent_id,
                    lock_expires_at=expires_at,
                )
                return True

            sv = self._data[key]

            # Check if already locked by another agent
            if sv.lock_holder and sv.lock_holder != agent_id:
                if sv.lock_expires_at and sv.lock_expires_at > now:
                    return False

            # Acquire lock
            sv.lock_holder = agent_id
            sv.lock_expires_at = expires_at

            await self._notify(
                MemoryEvent(
                    event_type=SharedMemoryEvent.LOCK,
                    key=key,
                    value=None,
                    agent_id=agent_id,
                )
            )

            return True

    async def release_lock(self, agent_id: str, key: str) -> bool:
        """Release lock on key"""
        async with self._lock:
            if key not in self._data:
                return False

            sv = self._data[key]

            if sv.lock_holder != agent_id:
                return False

            sv.lock_holder = None
            sv.lock_expires_at = None

            await self._notify(
                MemoryEvent(
                    event_type=SharedMemoryEvent.UNLOCK,
                    key=key,
                    value=None,
                    agent_id=agent_id,
                )
            )

            return True

    def transaction(self, agent_id: str) -> "_TransactionContext":
        """Create transaction context manager"""
        return _TransactionContext(self, agent_id)

    async def begin_transaction(self, agent_id: str) -> Transaction:
        """Begin a new transaction"""
        tx = Transaction(agent_id=agent_id)
        self._pending_transactions[tx.id] = tx
        return tx

    async def commit_transaction(self, tx: Transaction) -> bool:
        """Commit transaction"""
        async with self._lock:
            try:
                for op, key, value in tx.operations:
                    if op == "SET":
                        await self.set(tx.agent_id, key, value)
                    elif op == "DELETE":
                        await self.delete(tx.agent_id, key)
                    elif op == "INCREMENT":
                        await self.increment(tx.agent_id, key, value)

                tx.committed = True
                self._pending_transactions.pop(tx.id, None)

                await self._notify(
                    MemoryEvent(
                        event_type=SharedMemoryEvent.TRANSACTION_COMMIT,
                        key=tx.id,
                        value=len(tx.operations),
                        agent_id=tx.agent_id,
                    )
                )

                return True

            except Exception as e:
                logger.error(f"Transaction commit failed: {e}")
                await self.rollback_transaction(tx)
                return False

    async def rollback_transaction(self, tx: Transaction) -> None:
        """Rollback transaction"""
        self._pending_transactions.pop(tx.id, None)

        await self._notify(
            MemoryEvent(
                event_type=SharedMemoryEvent.TRANSACTION_ROLLBACK,
                key=tx.id,
                value=None,
                agent_id=tx.agent_id,
            )
        )

    def subscribe(
        self,
        key: Optional[str],
        callback: Callable[[MemoryEvent], Any],
    ) -> str:
        """Subscribe to changes on key (or all if key is None)"""
        subscription_id = f"sub_{uuid.uuid4().hex[:8]}"

        if key is None:
            self._global_subscribers.append(callback)
        else:
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(callback)

        return subscription_id

    def unsubscribe(self, key: Optional[str], callback: Callable) -> None:
        """Unsubscribe from changes"""
        if key is None:
            if callback in self._global_subscribers:
                self._global_subscribers.remove(callback)
        else:
            if key in self._subscribers and callback in self._subscribers[key]:
                self._subscribers[key].remove(callback)

    async def _notify(self, event: MemoryEvent) -> None:
        """Notify subscribers of event"""
        # Key-specific subscribers
        if event.key in self._subscribers:
            for callback in self._subscribers[event.key]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")

        # Global subscribers
        for callback in self._global_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Global subscriber error: {e}")

    async def get_all(self) -> Dict[str, Any]:
        """Get all key-value pairs"""
        async with self._lock:
            return {key: sv.value for key, sv in self._data.items()}

    async def keys(self) -> List[str]:
        """Get all keys"""
        async with self._lock:
            return list(self._data.keys())

    async def clear(self, agent_id: str) -> None:
        """Clear all data"""
        async with self._lock:
            self._data.clear()
            logger.info(f"SharedMemory cleared by {agent_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        with self._thread_lock:
            locked_keys = [
                key for key, sv in self._data.items() if sv.lock_holder is not None
            ]

            return {
                "total_keys": len(self._data),
                "locked_keys": len(locked_keys),
                "pending_transactions": len(self._pending_transactions),
                "subscribers": sum(len(subs) for subs in self._subscribers.values()),
                "global_subscribers": len(self._global_subscribers),
            }


class _TransactionContext:
    """Context manager for transactions"""

    def __init__(self, memory: SharedMemory, agent_id: str):
        self.memory = memory
        self.agent_id = agent_id
        self.tx: Optional[Transaction] = None

    async def __aenter__(self) -> Transaction:
        self.tx = await self.memory.begin_transaction(self.agent_id)
        return self.tx

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.memory.commit_transaction(self.tx)
        else:
            await self.memory.rollback_transaction(self.tx)
        return False


class DistributedSharedMemory(SharedMemory):
    """
    Distributed shared memory with network synchronization

    Extends SharedMemory with:
    - Cross-process synchronization
    - Network replication
    - Partition tolerance
    """

    def __init__(
        self,
        node_id: str,
        peers: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.node_id = node_id
        self.peers = peers or []
        self._vector_clock: Dict[str, int] = {node_id: 0}

        logger.info(f"🌐 DistributedSharedMemory initialized: {node_id}")

    async def set(
        self,
        agent_id: str,
        key: str,
        value: Any,
        expected_version: Optional[int] = None,
    ) -> bool:
        """Set with vector clock update"""
        result = await super().set(agent_id, key, value, expected_version)

        if result:
            # Update vector clock
            self._vector_clock[self.node_id] = (
                self._vector_clock.get(self.node_id, 0) + 1
            )

            # Replicate to peers (placeholder)
            # await self._replicate_to_peers(key, value)

        return result

    async def sync_from_peer(
        self,
        peer_id: str,
        data: Dict[str, Any],
        peer_clock: Dict[str, int],
    ) -> None:
        """Sync data from peer"""
        # Merge vector clocks
        for node, time in peer_clock.items():
            self._vector_clock[node] = max(self._vector_clock.get(node, 0), time)

        # Merge data (last-write-wins based on timestamp)
        for key, peer_sv in data.items():
            if key not in self._data:
                self._data[key] = SharedValue(**peer_sv)
            else:
                local_sv = self._data[key]
                # Compare by timestamp
                peer_updated = datetime.fromisoformat(peer_sv["updated_at"])
                if peer_updated > local_sv.updated_at:
                    local_sv.value = peer_sv["value"]
                    local_sv.updated_at = peer_updated


# Global shared memory instance
_global_shared_memory: Optional[SharedMemory] = None


def get_shared_memory() -> SharedMemory:
    """Get global shared memory"""
    global _global_shared_memory
    if _global_shared_memory is None:
        _global_shared_memory = SharedMemory()
    return _global_shared_memory


__all__ = [
    "ConflictResolution",
    "SharedValue",
    "Transaction",
    "SharedMemoryEvent",
    "MemoryEvent",
    "SharedMemory",
    "DistributedSharedMemory",
    "get_shared_memory",
]
