"""Dead Letter Queue for Agent Communications

Redis-based DLQ for failed agent messages with retry logic and monitoring.

Features:
- Automatic retry with exponential backoff
- Message expiration (TTL)
- Priority queue (critical messages first)
- Metrics integration (DLQ size, retry count)
- Manual intervention support (admin API)

Integration points:
- UnifiedAgentInterface: Catch failures and enqueue
- AgentToAgentCommunicator: Catch routing failures
- Admin API: DLQ inspection and manual retry
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import redis.asyncio as redis
from loguru import logger


class DLQPriority(Enum):
    """Priority levels for DLQ messages"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DLQMessage:
    """Dead letter queue message"""
    message_id: str
    agent_type: str
    content: str
    context: dict[str, Any]
    error: str
    retry_count: int = 0
    max_retries: int = 3
    priority: DLQPriority = DLQPriority.NORMAL
    enqueued_at: float = None
    last_retry_at: float = None
    correlation_id: str | None = None

    def __post_init__(self):
        if self.enqueued_at is None:
            self.enqueued_at = time.time()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["priority"] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DLQMessage":
        data["priority"] = DLQPriority(data["priority"])
        return cls(**data)

    def should_retry(self) -> bool:
        """Check if message should be retried"""
        return self.retry_count < self.max_retries

    def get_backoff_delay(self) -> float:
        """Calculate exponential backoff delay in seconds"""
        # 2^retry_count seconds: 1s, 2s, 4s, 8s, ...
        return min(2 ** self.retry_count, 300)  # Max 5 min

    def is_expired(self, ttl_seconds: int = 86400) -> bool:
        """Check if message has exceeded TTL (default 24h)"""
        return (time.time() - self.enqueued_at) > ttl_seconds


class DeadLetterQueue:
    """Redis-based dead letter queue for failed agent communications"""

    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 3):
        """Initialize DLQ
        
        Args:
            redis_url: Redis connection URL
            db: Redis database number (default 3, separate from main data)
        """
        self.redis_url = redis_url
        self.db = db
        self.redis_client: redis.Redis | None = None
        
        # Queue keys by priority
        self.queue_keys = {
            DLQPriority.CRITICAL: "dlq:critical",
            DLQPriority.HIGH: "dlq:high",
            DLQPriority.NORMAL: "dlq:normal",
            DLQPriority.LOW: "dlq:low",
        }
        
        # Metrics
        self.stats = {
            "total_enqueued": 0,
            "total_retried": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_expired": 0,
        }

    async def _get_redis(self) -> redis.Redis:
        """Lazy Redis connection"""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=True
            )
        return self.redis_client

    async def enqueue(self, message: DLQMessage) -> bool:
        """Add message to DLQ
        
        Args:
            message: DLQ message to enqueue
            
        Returns:
            True if successfully enqueued
        """
        try:
            r = await self._get_redis()
            queue_key = self.queue_keys[message.priority]
            
            # Add to priority queue (list)
            await r.lpush(queue_key, json.dumps(message.to_dict()))
            
            # Track in metadata (for inspection)
            metadata_key = f"dlq:metadata:{message.message_id}"
            await r.setex(metadata_key, 86400, json.dumps(message.to_dict()))  # 24h TTL
            
            # Update stats
            self.stats["total_enqueued"] += 1
            await r.incr("dlq:stats:enqueued")
            
            # Task 13: Track DLQ metrics
            try:
                from backend.api.app import DLQ_MESSAGES
                DLQ_MESSAGES.labels(
                    priority=message.priority.value,
                    agent_type=message.agent_type
                ).inc()
            except Exception:
                pass
            
            logger.warning(
                f"📬 DLQ: Enqueued message {message.message_id} "
                f"(priority={message.priority.value}, retry={message.retry_count}/{message.max_retries})"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ DLQ enqueue failed: {e}")
            return False

    async def dequeue(self, priority: DLQPriority = None) -> DLQMessage | None:
        """Dequeue message from DLQ
        
        Args:
            priority: Specific priority to dequeue (None = highest available)
            
        Returns:
            DLQMessage if available, None otherwise
        """
        try:
            r = await self._get_redis()
            
            # Determine which queues to check
            if priority:
                queues_to_check = [self.queue_keys[priority]]
            else:
                # Check in priority order: CRITICAL > HIGH > NORMAL > LOW
                queues_to_check = [
                    self.queue_keys[DLQPriority.CRITICAL],
                    self.queue_keys[DLQPriority.HIGH],
                    self.queue_keys[DLQPriority.NORMAL],
                    self.queue_keys[DLQPriority.LOW],
                ]
            
            # Try to pop from first non-empty queue
            for queue_key in queues_to_check:
                data = await r.rpop(queue_key)
                if data:
                    message = DLQMessage.from_dict(json.loads(data))
                    logger.info(f"📤 DLQ: Dequeued message {message.message_id}")
                    return message
            
            return None
            
        except Exception as e:
            logger.error(f"❌ DLQ dequeue failed: {e}")
            return None

    async def retry_message(self, message: DLQMessage) -> tuple[bool, str]:
        """Retry a failed message
        
        Args:
            message: Message to retry
            
        Returns:
            (success: bool, result: str) tuple
        """
        try:
            # Import here to avoid circular dependency
            from backend.agents.unified_agent_interface import (
                AgentRequest,
                AgentType,
                get_agent_interface,
            )
            
            # Update retry metadata
            message.retry_count += 1
            message.last_retry_at = time.time()
            
            logger.info(
                f"🔄 DLQ: Retrying message {message.message_id} "
                f"(attempt {message.retry_count}/{message.max_retries})"
            )
            
            # Create agent request
            agent_interface = get_agent_interface()
            request = AgentRequest(
                agent_type=AgentType(message.agent_type),
                task_type="dlq_retry",
                prompt=message.content,
                context=message.context
            )
            
            # Execute retry
            response = await agent_interface.send_request(request)
            
            if response.success:
                self.stats["total_success"] += 1
                r = await self._get_redis()
                await r.incr("dlq:stats:success")
                
                # Task 13: Track successful retries
                try:
                    from backend.api.app import DLQ_RETRIES
                    DLQ_RETRIES.labels(status="success").inc()
                except Exception:
                    pass
                
                logger.success(
                    f"✅ DLQ: Retry succeeded for message {message.message_id} "
                    f"(latency={response.latency_ms:.0f}ms)"
                )
                
                return True, response.content
            else:
                # Retry failed - re-enqueue if retries remain
                if message.should_retry():
                    # Wait for backoff before re-enqueueing
                    delay = message.get_backoff_delay()
                    logger.warning(
                        f"⏱️ DLQ: Retry failed, re-enqueueing after {delay}s backoff "
                        f"(message {message.message_id})"
                    )
                    
                    await asyncio.sleep(delay)
                    await self.enqueue(message)
                    self.stats["total_retried"] += 1
                    r = await self._get_redis()
                    await r.incr("dlq:stats:retried")
                    
                    return False, f"Retry failed, re-enqueued (backoff={delay}s)"
                else:
                    # Max retries exceeded
                    self.stats["total_failed"] += 1
                    r = await self._get_redis()
                    await r.incr("dlq:stats:failed")
                    
                    # Task 13: Track failed retries
                    try:
                        from backend.api.app import DLQ_RETRIES
                        DLQ_RETRIES.labels(status="failed").inc()
                    except Exception:
                        pass
                    
                    # Move to failed messages set for manual inspection
                    await self._archive_failed_message(message)
                    
                    logger.error(
                        f"❌ DLQ: Max retries exceeded for message {message.message_id}"
                    )
                    
                    return False, f"Max retries exceeded ({message.max_retries})"
                    
        except Exception as e:
            logger.error(f"❌ DLQ retry error: {e}")
            return False, str(e)

    async def _archive_failed_message(self, message: DLQMessage):
        """Archive permanently failed message"""
        try:
            r = await self._get_redis()
            archive_key = f"dlq:failed:{message.message_id}"
            await r.setex(archive_key, 604800, json.dumps(message.to_dict()))  # 7 days
            
            # Add to failed set for listing
            await r.zadd("dlq:failed_set", {message.message_id: time.time()})
            
        except Exception as e:
            logger.error(f"❌ Failed to archive message: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """Get DLQ statistics"""
        try:
            r = await self._get_redis()
            
            # Get queue sizes
            queue_sizes = {}
            for priority, key in self.queue_keys.items():
                size = await r.llen(key)
                queue_sizes[priority.value] = size
            
            # Get persistent stats
            enqueued = await r.get("dlq:stats:enqueued") or "0"
            retried = await r.get("dlq:stats:retried") or "0"
            success = await r.get("dlq:stats:success") or "0"
            failed = await r.get("dlq:stats:failed") or "0"
            
            # Get failed messages count
            failed_count = await r.zcard("dlq:failed_set")
            
            return {
                "queue_sizes": queue_sizes,
                "total_enqueued": int(enqueued),
                "total_retried": int(retried),
                "total_success": int(success),
                "total_failed": int(failed),
                "failed_messages_count": failed_count,
                "success_rate": (
                    int(success) / int(enqueued) if int(enqueued) > 0 else 0.0
                ),
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get DLQ stats: {e}")
            return {"error": str(e)}

    async def process_queue(self, batch_size: int = 10, max_runtime: float = 60.0):
        """Background task to process DLQ
        
        Args:
            batch_size: Max messages to process per batch
            max_runtime: Max runtime in seconds
        """
        start_time = time.time()
        processed = 0
        
        logger.info(f"🚀 DLQ processor starting (batch_size={batch_size})")
        
        while (time.time() - start_time) < max_runtime:
            message = await self.dequeue()
            
            if not message:
                # Queue empty, wait before checking again
                await asyncio.sleep(5)
                continue
            
            # Check expiration
            if message.is_expired():
                self.stats["total_expired"] += 1
                
                # Task 13: Track expired messages
                try:
                    from backend.api.app import DLQ_RETRIES
                    DLQ_RETRIES.labels(status="expired").inc()
                except Exception:
                    pass
                
                logger.warning(f"⏰ DLQ: Message {message.message_id} expired, skipping")
                continue
            
            # Retry message
            await self.retry_message(message)
            processed += 1
            
            if processed >= batch_size:
                break
        
        logger.info(
            f"✅ DLQ processor finished: {processed} messages processed "
            f"in {time.time() - start_time:.1f}s"
        )


# Global instance
_dlq_instance: DeadLetterQueue | None = None


def get_dlq() -> DeadLetterQueue:
    """Get global DLQ instance (singleton)"""
    global _dlq_instance
    if _dlq_instance is None:
        _dlq_instance = DeadLetterQueue()
    return _dlq_instance


__all__ = ["DeadLetterQueue", "DLQMessage", "DLQPriority", "get_dlq"]
