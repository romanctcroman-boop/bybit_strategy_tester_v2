"""
Redis Queue Module

Provides asynchronous task queue functionality using Redis.
Supports task scheduling, priority queues, and result tracking.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class Task:
    """Represents a queued task."""

    def __init__(
        self,
        func_name: str,
        args: tuple = (),
        kwargs: dict | None = None,  # Fixed to explicitly declare as Optional
        task_id: str | None = None,  # Fixed to explicitly declare as Optional
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout: int = 300,
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.func_name = func_name
        self.args = args
        self.kwargs = kwargs or {}
        self.priority = priority
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_count = 0
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(UTC)
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.result: Any = None
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "task_id": self.task_id,
            "func_name": self.func_name,
            "args": list(self.args),
            "kwargs": self.kwargs,
            "priority": self.priority.value,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize task from dictionary."""
        task = cls(
            func_name=data["func_name"],
            args=tuple(data.get("args", [])),
            kwargs=data.get("kwargs", {}),
            task_id=data["task_id"],
            priority=TaskPriority(data.get("priority", 5)),
            max_retries=data.get("max_retries", 3),
            timeout=data.get("timeout", 300),
        )
        task.retry_count = data.get("retry_count", 0)
        task.status = TaskStatus(data.get("status", "pending"))
        task.result = data.get("result")
        task.error = data.get("error")

        if data.get("created_at"):
            task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])

        return task


class QueueAdapter:
    """
    Redis Queue Adapter for async task processing.

    Features:
    - Async task submission
    - Priority queues
    - Task result tracking
    - Automatic retries
    - Dead letter queue for failed tasks
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        queue_name: str = "task_queue",
        result_ttl: int = 3600,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.result_ttl = result_ttl
        self._redis: Any = None
        self._connected = False
        self._handlers: dict[str, Callable] = {}
        self._worker_task: asyncio.Task | asyncio.Future | None = None
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
        }

    async def _ensure_connected(self) -> bool:
        """Ensure Redis connection is established."""
        if self._connected:
            return True

        try:
            import redis.asyncio as aioredis

            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True

        except ImportError:
            logger.warning("redis package not installed. Queue functionality disabled.")
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            return False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Redis connection closed")

    def register_handler(self, func_name: str, handler: Callable):
        """Register a task handler function."""
        self._handlers[func_name] = handler
        logger.debug(f"Registered handler for '{func_name}'")

    async def submit(
        self,
        func_name: str,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout: int = 300,
        **kwargs,
    ) -> str:
        """
        Submit a task to the queue.

        Args:
            func_name: Name of the registered handler function
            *args: Positional arguments for the handler
            priority: Task priority level
            max_retries: Maximum retry attempts
            timeout: Task timeout in seconds
            **kwargs: Keyword arguments for the handler

        Returns:
            Task ID for tracking
        """
        if not await self._ensure_connected():
            raise RuntimeError("Redis not connected")

        task = Task(
            func_name=func_name,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
        )

        # Store task data
        await self._redis.hset(
            f"task:{task.task_id}",
            mapping={"data": json.dumps(task.to_dict())},
        )
        await self._redis.expire(f"task:{task.task_id}", self.result_ttl * 24)

        # Add to priority queue (sorted set with priority as score)
        await self._redis.zadd(
            f"{self.queue_name}:pending",
            {task.task_id: task.priority.value},
        )

        self._stats["tasks_submitted"] += 1
        logger.debug(f"Task {task.task_id} submitted: {func_name}")

        return task.task_id

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        if not await self._ensure_connected():
            return None

        data = await self._redis.hget(f"task:{task_id}", "data")
        if data:
            return Task.from_dict(json.loads(data))
        return None

    async def get_result(self, task_id: str) -> Any | None:
        """Get task result."""
        task = await self.get_task(task_id)
        if task:
            return {
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        if not await self._ensure_connected():
            return False

        # Remove from pending queue
        removed = await self._redis.zrem(f"{self.queue_name}:pending", task_id)

        if removed:
            task = await self.get_task(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
                await self._redis.hset(
                    f"task:{task_id}",
                    mapping={"data": json.dumps(task.to_dict())},
                )
            return True
        return False

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        if not await self._ensure_connected():
            return {"connected": False, **self._stats}

        pending = await self._redis.zcard(f"{self.queue_name}:pending")
        processing = await self._redis.scard(f"{self.queue_name}:processing")

        return {
            "connected": True,
            "pending_tasks": pending,
            "processing_tasks": processing,
            **self._stats,
        }

    async def start_worker(self, concurrency: int = 3):
        """Start processing tasks from the queue."""
        if not await self._ensure_connected():
            logger.error("Cannot start worker: Redis not connected")
            return

        async def process_tasks():
            while True:
                try:
                    # Get highest priority task
                    result = await self._redis.zpopmax(f"{self.queue_name}:pending", count=1)

                    if not result:
                        await asyncio.sleep(0.1)
                        continue

                    task_id = result[0][0]

                    # Mark as processing
                    await self._redis.sadd(f"{self.queue_name}:processing", task_id)

                    task = await self.get_task(task_id)
                    if not task:
                        await self._redis.srem(f"{self.queue_name}:processing", task_id)
                        continue

                    # Execute task
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now(UTC)
                    await self._update_task(task)

                    try:
                        handler = self._handlers.get(task.func_name)
                        if not handler:
                            raise ValueError(f"No handler for '{task.func_name}'")

                        # Execute with timeout
                        if asyncio.iscoroutinefunction(handler):
                            result = await asyncio.wait_for(
                                handler(*task.args, **task.kwargs),
                                timeout=task.timeout,
                            )
                        else:
                            result = handler(*task.args, **task.kwargs)

                        task.status = TaskStatus.COMPLETED
                        task.result = result
                        task.completed_at = datetime.now(UTC)
                        self._stats["tasks_completed"] += 1

                    except Exception as e:
                        task.retry_count += 1

                        if task.retry_count < task.max_retries:
                            # Retry
                            task.status = TaskStatus.RETRYING
                            self._stats["tasks_retried"] += 1
                            await self._redis.zadd(
                                f"{self.queue_name}:pending",
                                {task.task_id: task.priority.value - 1},
                            )
                        else:
                            # Failed permanently
                            task.status = TaskStatus.FAILED
                            task.error = str(e)
                            self._stats["tasks_failed"] += 1
                            # Add to dead letter queue
                            await self._redis.lpush(
                                f"{self.queue_name}:dead",
                                task.task_id,
                            )

                    await self._update_task(task)
                    await self._redis.srem(f"{self.queue_name}:processing", task_id)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Worker error: {e}")
                    await asyncio.sleep(1)

        # Start worker tasks
        workers = [asyncio.create_task(process_tasks()) for _ in range(concurrency)]
        self._worker_task = asyncio.gather(*workers)
        logger.info(f"Started {concurrency} queue workers")

    async def stop_worker(self):
        """Stop the worker."""
        if self._worker_task:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):  # Use contextlib.suppress instead of try-except-pass
                await self._worker_task
            logger.info("Queue workers stopped")

    async def _update_task(self, task: Task):
        """Update task data in Redis."""
        await self._redis.hset(
            f"task:{task.task_id}",
            mapping={"data": json.dumps(task.to_dict())},
        )


# Create default queue adapter instance
queue_adapter = QueueAdapter()


__all__ = [
    "QueueAdapter",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "queue_adapter",
]
