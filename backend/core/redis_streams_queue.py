"""
Redis Streams Queue Manager для MCP Server
==========================================

Реализация высокопроизводительной системы очередей на Redis Streams с:
- High/Low priority очереди
- Consumer Groups для горизонтального масштабирования
- XPENDING автоматическое восстановление "застрявших" задач
- Checkpointing для промежуточных данных
- Dead Letter Queue (DLQ) для failed tasks
- Metrics integration для monitoring

Architecture:
    ┌────────────┐
    │   Client   │
    └─────┬──────┘
          │ add_task(priority, payload)
          ▼
    ┌────────────────────┐
    │  Priority Router   │
    ├────────────────────┤
    │ high_priority_stream│──┐
    │ low_priority_stream │──┤
    └────────────────────┘  │
                            ▼
    ┌──────────────────────────────┐
    │   Consumer Groups            │
    ├──────────────────────────────┤
    │ Worker-1 │ Worker-2 │ Worker-3│
    └──────────────────────────────┘
              │
              ▼
    ┌────────────────┐
    │ XPENDING Recovery│
    └────────────────┘

Author: DeepSeek Code Agent
Date: 2025-11-02
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as aioredis
from redis.asyncio.client import Redis
from redis.exceptions import ConnectionError, TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# TASK MODELS & ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class TaskPriority(str, Enum):
    """Task priority levels"""
    HIGH = "high"  # Reasoning, urgent coding
    LOW = "low"  # Background jobs, batch processing


class TaskStatus(str, Enum):
    """Task lifecycle states"""
    PENDING = "pending"  # In queue, not yet picked up
    PROCESSING = "processing"  # Currently being processed by worker
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed after all retries
    DEAD_LETTER = "dead_letter"  # Moved to DLQ


@dataclass
class Task:
    """
    Task representation for Redis Streams
    
    Attributes:
        task_id: Unique task identifier
        type: Task type (reasoning, codegen, ml, etc.)
        priority: Task priority (high/low)
        payload: Task data (serializable dict)
        created_at: Task creation timestamp
        worker_id: Worker currently processing the task
        retry_count: Number of retry attempts
        max_retries: Maximum allowed retries
        timeout: Task timeout in seconds
    """
    task_id: str
    type: str
    priority: TaskPriority
    payload: Dict[str, Any]
    created_at: float
    worker_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 120  # seconds
    
    def to_redis_dict(self) -> Dict[str, str]:
        """Convert task to Redis-compatible string dict"""
        return {
            "task_id": self.task_id,
            "type": self.type,
            "priority": self.priority.value,
            "payload": json.dumps(self.payload),
            "created_at": str(self.created_at),
            "worker_id": self.worker_id or "",
            "retry_count": str(self.retry_count),
            "max_retries": str(self.max_retries),
            "timeout": str(self.timeout)
        }
    
    @classmethod
    def from_redis_dict(cls, data: Dict[bytes, bytes]) -> 'Task':
        """Parse task from Redis stream entry"""
        return cls(
            task_id=data[b"task_id"].decode(),
            type=data[b"type"].decode(),
            priority=TaskPriority(data[b"priority"].decode()),
            payload=json.loads(data[b"payload"].decode()),
            created_at=float(data[b"created_at"].decode()),
            worker_id=data[b"worker_id"].decode() or None,
            retry_count=int(data[b"retry_count"].decode()),
            max_retries=int(data[b"max_retries"].decode()),
            timeout=int(data[b"timeout"].decode())
        )


# ═══════════════════════════════════════════════════════════════════════════
# REDIS STREAMS QUEUE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class RedisStreamsQueueManager:
    """
    High-performance queue manager using Redis Streams
    
    Features:
        ✅ Priority-based task routing (high/low)
        ✅ Horizontal scaling via Consumer Groups
        ✅ Automatic recovery of stalled tasks (XPENDING)
        ✅ Checkpointing for long-running workflows
        ✅ Dead Letter Queue (DLQ) for persistent failures
        ✅ Metrics tracking (queue depth, processing time, etc.)
        ✅ Graceful shutdown with task preservation
    
    Redis Streams используется вместо Redis Pub/Sub или Lists, т.к.:
        - Message persistence (задачи не теряются при рестарте)
        - Consumer Groups (горизонтальное масштабирование)
        - Message acknowledgment (XACK)
        - XPENDING для recovery
        - Встроенный ID генератор (time-ordered)
    """
    
    # Stream names
    HIGH_PRIORITY_STREAM = "mcp:tasks:high"
    LOW_PRIORITY_STREAM = "mcp:tasks:low"
    CHECKPOINT_STREAM = "mcp:checkpoints"
    DLQ_STREAM = "mcp:tasks:dlq"
    
    # Consumer group names
    CONSUMER_GROUP = "mcp_workers"
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_stream_len: int = 100000,
        recovery_interval: int = 60,
        consumer_name: Optional[str] = None
    ):
        """
        Initialize Redis Streams Queue Manager
        
        Args:
            redis_url: Redis connection URL
            max_stream_len: Maximum stream length (old messages trimmed)
            recovery_interval: Interval for checking stalled tasks (seconds)
            consumer_name: Unique consumer identifier (auto-generated if None)
        """
        self.redis_url = redis_url
        self.max_stream_len = max_stream_len
        self.recovery_interval = recovery_interval
        self.consumer_name = consumer_name or f"worker-{int(time.time())}"
        
        self.redis: Optional[Redis] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Metrics
        self.metrics = {
            "tasks_added": 0,
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_recovered": 0
        }
    
    async def connect(self):
        """Establish Redis connection and setup streams"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,
                max_connections=50
            )
            
            # Test connection
            await self.redis.ping()
            logger.info(f"[Redis] Connected to {self.redis_url}")
            
            # Initialize consumer groups (создаются если не существуют)
            await self._ensure_consumer_groups()
            
            logger.info(f"[Redis] Consumer groups initialized for worker: {self.consumer_name}")
            
        except Exception as e:
            logger.error(f"[Redis] Connection failed: {e}")
            raise
    
    async def _ensure_consumer_groups(self):
        """Create consumer groups if they don't exist"""
        streams = [
            self.HIGH_PRIORITY_STREAM,
            self.LOW_PRIORITY_STREAM
        ]
        
        for stream in streams:
            try:
                # Try to create consumer group
                await self.redis.xgroup_create(
                    name=stream,
                    groupname=self.CONSUMER_GROUP,
                    id="0",  # Start from beginning
                    mkstream=True  # Create stream if not exists
                )
                logger.info(f"[Redis] Created consumer group '{self.CONSUMER_GROUP}' for stream '{stream}'")
                
            except Exception as e:
                # Group likely already exists
                if "BUSYGROUP" in str(e):
                    logger.debug(f"[Redis] Consumer group already exists for stream '{stream}'")
                else:
                    logger.warning(f"[Redis] Error creating consumer group for '{stream}': {e}")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("[Redis] Disconnected")
    
    # ═════════════════════════════════════════════════════════════════
    # TASK MANAGEMENT
    # ═════════════════════════════════════════════════════════════════
    
    async def add_task(
        self,
        task: Task,
        maxlen: Optional[int] = None
    ) -> str:
        """
        Add task to appropriate priority stream
        
        Args:
            task: Task object
            maxlen: Override max stream length (default: self.max_stream_len)
        
        Returns:
            Redis Stream message ID (format: '1234567890-0')
        """
        if not self.redis:
            raise RuntimeError("Redis not connected. Call connect() first.")
        
        # Select stream based on priority
        stream = (
            self.HIGH_PRIORITY_STREAM
            if task.priority == TaskPriority.HIGH
            else self.LOW_PRIORITY_STREAM
        )
        
        # Add to stream with automatic trimming
        message_id = await self.redis.xadd(
            name=stream,
            fields=task.to_redis_dict(),
            maxlen=maxlen or self.max_stream_len,
            approximate=True  # ~MAXLEN для performance
        )
        
        self.metrics["tasks_added"] += 1
        
        logger.info(
            f"[Redis] Added task {task.task_id} to {stream} "
            f"(priority: {task.priority.value}, type: {task.type})"
        )
        
        return message_id.decode()
    
    async def read_tasks(
        self,
        count: int = 10,
        block: int = 5000,
        priority: Optional[TaskPriority] = None
    ) -> List[Tuple[str, Task]]:
        """
        Read tasks from streams using consumer group
        
        Args:
            count: Maximum number of tasks to read
            block: Block timeout in milliseconds (0 = non-blocking)
            priority: Read from specific priority stream (None = read both)
        
        Returns:
            List of (message_id, Task) tuples
        """
        if not self.redis:
            raise RuntimeError("Redis not connected")
        
        # Determine streams to read from
        if priority == TaskPriority.HIGH:
            streams = {self.HIGH_PRIORITY_STREAM: ">"}
        elif priority == TaskPriority.LOW:
            streams = {self.LOW_PRIORITY_STREAM: ">"}
        else:
            # Read from both (high priority first)
            streams = {
                self.HIGH_PRIORITY_STREAM: ">",
                self.LOW_PRIORITY_STREAM: ">"
            }
        
        try:
            # XREADGROUP: Read unacknowledged messages for this consumer
            result = await self.redis.xreadgroup(
                groupname=self.CONSUMER_GROUP,
                consumername=self.consumer_name,
                streams=streams,
                count=count,
                block=block
            )
            
            tasks = []
            for stream_name, messages in result:
                for message_id, data in messages:
                    try:
                        task = Task.from_redis_dict(data)
                        task.worker_id = self.consumer_name
                        tasks.append((message_id.decode(), task))
                    except Exception as e:
                        logger.error(f"[Redis] Failed to parse task from {message_id}: {e}")
            
            if tasks:
                logger.info(f"[Redis] Read {len(tasks)} tasks for worker {self.consumer_name}")
            
            return tasks
            
        except Exception as e:
            logger.error(f"[Redis] Error reading tasks: {e}")
            return []
    
    async def acknowledge_task(self, stream: str, message_id: str):
        """
        Acknowledge task completion (removes from pending list)
        
        Args:
            stream: Stream name
            message_id: Redis Stream message ID
        """
        if not self.redis:
            return
        
        try:
            await self.redis.xack(
                stream,
                self.CONSUMER_GROUP,
                message_id
            )
            self.metrics["tasks_processed"] += 1
            logger.debug(f"[Redis] Acknowledged task {message_id} from {stream}")
            
        except Exception as e:
            logger.error(f"[Redis] Failed to acknowledge {message_id}: {e}")
    
    async def move_to_dlq(self, task: Task, error_message: str):
        """
        Move failed task to Dead Letter Queue
        
        Args:
            task: Failed task
            error_message: Failure reason
        """
        if not self.redis:
            return
        
        dlq_data = task.to_redis_dict()
        dlq_data["error"] = error_message
        dlq_data["failed_at"] = str(time.time())
        
        await self.redis.xadd(
            name=self.DLQ_STREAM,
            fields=dlq_data,
            maxlen=10000
        )
        
        self.metrics["tasks_failed"] += 1
        logger.warning(f"[Redis] Task {task.task_id} moved to DLQ: {error_message}")
    
    # ═════════════════════════════════════════════════════════════════
    # CHECKPOINTING
    # ═════════════════════════════════════════════════════════════════
    
    async def save_checkpoint(
        self,
        task_id: str,
        step: str,
        data: Dict[str, Any]
    ):
        """
        Save workflow checkpoint для long-running tasks
        
        Args:
            task_id: Task identifier
            step: Workflow step name (e.g., "reasoning", "codegen")
            data: Checkpoint data to persist
        """
        if not self.redis:
            return
        
        checkpoint_data = {
            "task_id": task_id,
            "step": step,
            "data": json.dumps(data),
            "timestamp": str(time.time())
        }
        
        await self.redis.xadd(
            name=self.CHECKPOINT_STREAM,
            fields=checkpoint_data,
            maxlen=50000
        )
        
        logger.info(f"[Redis] Checkpoint saved: task={task_id}, step={step}")
    
    async def get_checkpoints(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all checkpoints for a task
        
        Args:
            task_id: Task identifier
        
        Returns:
            List of checkpoint data dicts
        """
        if not self.redis:
            return []
        
        # Read entire checkpoint stream and filter by task_id
        # (в production лучше использовать secondary index или отдельные keys)
        result = await self.redis.xread(
            {self.CHECKPOINT_STREAM: "0-0"},
            count=1000
        )
        
        checkpoints = []
        for stream_name, messages in result:
            for message_id, data in messages:
                if data[b"task_id"].decode() == task_id:
                    checkpoints.append({
                        "step": data[b"step"].decode(),
                        "data": json.loads(data[b"data"].decode()),
                        "timestamp": float(data[b"timestamp"].decode())
                    })
        
        return checkpoints
    
    # ═════════════════════════════════════════════════════════════════
    # XPENDING RECOVERY (Auto-recovery of stalled tasks)
    # ═════════════════════════════════════════════════════════════════
    
    async def start_recovery_monitor(self):
        """
        Start background task for monitoring and recovering stalled tasks
        
        Проверяет XPENDING каждые recovery_interval секунд и
        перераспределяет "застрявшие" задачи другим воркерам
        """
        self._running = True
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        logger.info(f"[Redis] Started recovery monitor (interval: {self.recovery_interval}s)")
    
    async def stop_recovery_monitor(self):
        """Stop recovery monitor"""
        self._running = False
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        logger.info("[Redis] Stopped recovery monitor")
    
    async def _recovery_loop(self):
        """Background loop for checking stalled tasks"""
        while self._running:
            try:
                await asyncio.sleep(self.recovery_interval)
                await self._recover_stalled_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Redis] Recovery loop error: {e}")
    
    async def _recover_stalled_tasks(self):
        """
        Check XPENDING and recover stalled tasks
        
        Tasks считается "застрявшей" если:
            - Idle time > task.timeout
            - Delivery count > task.max_retries → move to DLQ
            - Иначе → XCLAIM для другого воркера
        """
        if not self.redis:
            return
        
        streams = [self.HIGH_PRIORITY_STREAM, self.LOW_PRIORITY_STREAM]
        
        for stream in streams:
            try:
                # Get pending messages summary
                pending_info = await self.redis.xpending(
                    stream,
                    self.CONSUMER_GROUP
                )
                
                if not pending_info or pending_info[0] == 0:
                    continue
                
                # Get detailed pending list
                pending_messages = await self.redis.xpending_range(
                    stream,
                    self.CONSUMER_GROUP,
                    min="-",
                    max="+",
                    count=100
                )
                
                for msg in pending_messages:
                    message_id = msg["message_id"].decode()
                    consumer = msg["consumer"].decode()
                    idle_time = msg["time_since_delivered"]  # milliseconds
                    delivery_count = msg["times_delivered"]
                    
                    # Fetch full message data
                    message_data = await self.redis.xrange(
                        stream,
                        min=message_id,
                        max=message_id,
                        count=1
                    )
                    
                    if not message_data:
                        continue
                    
                    _, data = message_data[0]
                    task = Task.from_redis_dict(data)
                    
                    # Check if stalled (idle > timeout)
                    if idle_time > task.timeout * 1000:
                        if delivery_count >= task.max_retries:
                            # Max retries exceeded → DLQ
                            await self.move_to_dlq(
                                task,
                                f"Max retries exceeded ({delivery_count})"
                            )
                            await self.acknowledge_task(stream, message_id)
                            logger.warning(
                                f"[Redis] Task {task.task_id} moved to DLQ after {delivery_count} attempts"
                            )
                        else:
                            # Claim for re-processing by another worker
                            await self.redis.xclaim(
                                stream,
                                self.CONSUMER_GROUP,
                                self.consumer_name,
                                min_idle_time=task.timeout * 1000,
                                message_ids=[message_id]
                            )
                            self.metrics["tasks_recovered"] += 1
                            logger.info(
                                f"[Redis] Claimed stalled task {task.task_id} "
                                f"(idle: {idle_time}ms, attempt: {delivery_count})"
                            )
                
            except Exception as e:
                logger.error(f"[Redis] Error recovering tasks from {stream}: {e}")
    
    # ═════════════════════════════════════════════════════════════════
    # METRICS & MONITORING
    # ═════════════════════════════════════════════════════════════════
    
    async def get_queue_depth(self, priority: Optional[TaskPriority] = None) -> Dict[str, int]:
        """
        Get current queue depth (number of pending tasks)
        
        Args:
            priority: Filter by priority (None = all queues)
        
        Returns:
            Dict with queue depths: {"high": 42, "low": 15}
        """
        if not self.redis:
            return {"high": 0, "low": 0}
        
        depths = {}
        
        streams = (
            [self.HIGH_PRIORITY_STREAM]
            if priority == TaskPriority.HIGH
            else [self.LOW_PRIORITY_STREAM]
            if priority == TaskPriority.LOW
            else [self.HIGH_PRIORITY_STREAM, self.LOW_PRIORITY_STREAM]
        )
        
        for stream in streams:
            try:
                pending_info = await self.redis.xpending(
                    stream,
                    self.CONSUMER_GROUP
                )
                count = pending_info[0] if pending_info else 0
                
                key = "high" if "high" in stream else "low"
                depths[key] = count
                
            except Exception as e:
                logger.error(f"[Redis] Error getting queue depth for {stream}: {e}")
                key = "high" if "high" in stream else "low"
                depths[key] = 0
        
        return depths
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive queue metrics"""
        queue_depths = await self.get_queue_depth()
        
        return {
            "consumer_name": self.consumer_name,
            "queue_depth": queue_depths,
            "tasks_added": self.metrics["tasks_added"],
            "tasks_processed": self.metrics["tasks_processed"],
            "tasks_failed": self.metrics["tasks_failed"],
            "tasks_recovered": self.metrics["tasks_recovered"],
            "recovery_interval": self.recovery_interval,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Example usage of RedisStreamsQueueManager"""
    
    # Initialize manager
    manager = RedisStreamsQueueManager(
        redis_url="redis://localhost:6379",
        consumer_name="worker-example"
    )
    
    try:
        # Connect to Redis
        await manager.connect()
        
        # Start recovery monitor
        await manager.start_recovery_monitor()
        
        # Add some tasks
        high_priority_task = Task(
            task_id="task-123",
            type="reasoning",
            priority=TaskPriority.HIGH,
            payload={"prompt": "Analyze trading strategy"},
            created_at=time.time(),
            timeout=60
        )
        
        low_priority_task = Task(
            task_id="task-456",
            type="batch-optimization",
            priority=TaskPriority.LOW,
            payload={"strategy_ids": [1, 2, 3]},
            created_at=time.time(),
            timeout=300
        )
        
        msg_id_1 = await manager.add_task(high_priority_task)
        msg_id_2 = await manager.add_task(low_priority_task)
        
        print(f"✅ Added tasks: {msg_id_1}, {msg_id_2}")
        
        # Read tasks (consumer)
        tasks = await manager.read_tasks(count=10, block=1000)
        print(f"📥 Read {len(tasks)} tasks")
        
        # Process and acknowledge
        for message_id, task in tasks:
            print(f"Processing task {task.task_id} (type: {task.type})")
            
            # Save checkpoint (for long-running workflows)
            await manager.save_checkpoint(
                task.task_id,
                step="reasoning",
                data={"progress": 50, "intermediate_result": "..."}
            )
            
            # Simulate processing
            await asyncio.sleep(0.1)
            
            # Acknowledge completion
            stream = (
                manager.HIGH_PRIORITY_STREAM
                if task.priority == TaskPriority.HIGH
                else manager.LOW_PRIORITY_STREAM
            )
            await manager.acknowledge_task(stream, message_id)
        
        # Get metrics
        metrics = await manager.get_metrics()
        print(f"📊 Metrics: {metrics}")
        
        # Keep running for recovery monitor
        await asyncio.sleep(5)
        
    finally:
        # Cleanup
        await manager.stop_recovery_monitor()
        await manager.disconnect()
        print("✅ Cleanup completed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
