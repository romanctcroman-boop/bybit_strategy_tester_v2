"""
Redis Consumer Groups - Distributed task processing with Redis Streams

Provides reliable distributed task processing with:
- Consumer groups for parallel processing
- Automatic task claiming and acknowledgment
- Dead letter queue for failed tasks
- Backpressure handling
"""

import redis
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import uuid
from loguru import logger


class RedisConsumerGroup:
    """
    Redis Consumer Group for distributed task processing.
    
    Features:
    - Parallel task processing across multiple workers
    - Automatic task claiming and acknowledgment
    - Pending task recovery
    - Dead letter queue for failed tasks
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        stream_name: str,
        group_name: str,
        consumer_name: Optional[str] = None,
        max_pending_time_ms: int = 300000,  # 5 minutes
        max_retries: int = 3
    ):
        """
        Initialize consumer group.
        
        Args:
            redis_client: Redis client instance
            stream_name: Name of Redis stream
            group_name: Name of consumer group
            consumer_name: Name of this consumer (auto-generated if None)
            max_pending_time_ms: Max time before claiming pending tasks
            max_retries: Max retry attempts before moving to DLQ
        """
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
        self.max_pending_time_ms = max_pending_time_ms
        self.max_retries = max_retries
        
        # Dead letter queue stream
        self.dlq_stream = f"{stream_name}:dlq"
        
        # Initialize consumer group
        self._ensure_group_exists()
    
    def _ensure_group_exists(self):
        """Create consumer group if it doesn't exist"""
        try:
            self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id='0',
                mkstream=True
            )
            logger.info(f"Created consumer group: {self.group_name} on {self.stream_name}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group already exists: {self.group_name}")
            else:
                raise
    
    def add_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """
        Add task to stream.
        
        Args:
            task_type: Type of task
            task_data: Task data
            priority: Task priority (higher = more important)
        
        Returns:
            Task ID (stream message ID)
        """
        message = {
            'task_type': task_type,
            'task_data': json.dumps(task_data),
            'priority': priority,
            'created_at': datetime.utcnow().isoformat(),
            'retry_count': 0
        }
        
        task_id = self.redis.xadd(self.stream_name, message)
        logger.info(f"Added task {task_id} to {self.stream_name}")
        
        return task_id.decode() if isinstance(task_id, bytes) else task_id
    
    def read_tasks(
        self,
        count: int = 10,
        block_ms: int = 5000
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Read tasks from stream (consumer group).
        
        Args:
            count: Max number of tasks to read
            block_ms: Block time in milliseconds
        
        Returns:
            List of (task_id, task_data) tuples
        """
        try:
            # Read new tasks
            response = self.redis.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: '>'},
                count=count,
                block=block_ms
            )
            
            if not response:
                return []
            
            tasks = []
            for stream_name, messages in response:
                for msg_id, fields in messages:
                    task_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                    
                    # Decode fields
                    decoded_fields = {
                        k.decode() if isinstance(k, bytes) else k: 
                        v.decode() if isinstance(v, bytes) else v
                        for k, v in fields.items()
                    }
                    
                    # Parse task data
                    task_data = {
                        'task_id': task_id,
                        'task_type': decoded_fields.get('task_type'),
                        'task_data': json.loads(decoded_fields.get('task_data', '{}')),
                        'priority': int(decoded_fields.get('priority', 0)),
                        'created_at': decoded_fields.get('created_at'),
                        'retry_count': int(decoded_fields.get('retry_count', 0))
                    }
                    
                    tasks.append((task_id, task_data))
            
            return tasks
            
        except Exception as e:
            logger.error(f"Error reading tasks: {e}")
            return []
    
    def acknowledge_task(self, task_id: str) -> bool:
        """
        Acknowledge task completion.
        
        Args:
            task_id: Task ID to acknowledge
        
        Returns:
            True if acknowledged successfully
        """
        try:
            self.redis.xack(self.stream_name, self.group_name, task_id)
            logger.debug(f"Acknowledged task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error acknowledging task {task_id}: {e}")
            return False
    
    def retry_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        Retry failed task.
        
        Args:
            task_id: Original task ID
            task_data: Task data
        
        Returns:
            True if retry queued, False if moved to DLQ
        """
        retry_count = task_data.get('retry_count', 0) + 1
        
        # Check retry limit
        if retry_count > self.max_retries:
            logger.warning(f"Task {task_id} exceeded max retries, moving to DLQ")
            return self._move_to_dlq(task_id, task_data, reason="max_retries_exceeded")
        
        # Re-add task with incremented retry count
        message = {
            'task_type': task_data.get('task_type'),
            'task_data': json.dumps(task_data.get('task_data', {})),
            'priority': task_data.get('priority', 0),
            'created_at': task_data.get('created_at'),
            'retry_count': retry_count,
            'original_task_id': task_id
        }
        
        self.redis.xadd(self.stream_name, message)
        
        # Acknowledge original task
        self.acknowledge_task(task_id)
        
        logger.info(f"Retrying task {task_id} (attempt {retry_count}/{self.max_retries})")
        return True
    
    def _move_to_dlq(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        reason: str
    ) -> bool:
        """
        Move task to dead letter queue.
        
        Args:
            task_id: Task ID
            task_data: Task data
            reason: Failure reason
        
        Returns:
            True if moved successfully
        """
        dlq_message = {
            'original_task_id': task_id,
            'task_type': task_data.get('task_type'),
            'task_data': json.dumps(task_data.get('task_data', {})),
            'failure_reason': reason,
            'failed_at': datetime.utcnow().isoformat(),
            'retry_count': task_data.get('retry_count', 0)
        }
        
        self.redis.xadd(self.dlq_stream, dlq_message)
        
        # Acknowledge original task
        self.acknowledge_task(task_id)
        
        logger.error(f"Moved task {task_id} to DLQ: {reason}")
        return True
    
    def claim_pending_tasks(self, idle_time_ms: Optional[int] = None) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Claim pending tasks from other consumers.
        
        Useful for recovering tasks from dead/slow consumers.
        
        Args:
            idle_time_ms: Minimum idle time before claiming (default: max_pending_time_ms)
        
        Returns:
            List of claimed (task_id, task_data) tuples
        """
        if idle_time_ms is None:
            idle_time_ms = self.max_pending_time_ms
        
        try:
            # Get pending tasks
            pending = self.redis.xpending_range(
                name=self.stream_name,
                groupname=self.group_name,
                min='-',
                max='+',
                count=10
            )
            
            claimed_tasks = []
            
            for item in pending:
                msg_id = item['message_id']
                idle_ms = item['time_since_delivered']
                
                # Claim if idle too long
                if idle_ms >= idle_time_ms:
                    claimed = self.redis.xclaim(
                        name=self.stream_name,
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        min_idle_time=idle_time_ms,
                        message_ids=[msg_id]
                    )
                    
                    if claimed:
                        for msg in claimed:
                            task_id = msg[0].decode() if isinstance(msg[0], bytes) else msg[0]
                            fields = msg[1]
                            
                            decoded_fields = {
                                k.decode() if isinstance(k, bytes) else k:
                                v.decode() if isinstance(v, bytes) else v
                                for k, v in fields.items()
                            }
                            
                            task_data = {
                                'task_id': task_id,
                                'task_type': decoded_fields.get('task_type'),
                                'task_data': json.loads(decoded_fields.get('task_data', '{}')),
                                'priority': int(decoded_fields.get('priority', 0)),
                                'retry_count': int(decoded_fields.get('retry_count', 0))
                            }
                            
                            claimed_tasks.append((task_id, task_data))
                            logger.info(f"Claimed pending task: {task_id}")
            
            return claimed_tasks
            
        except Exception as e:
            logger.error(f"Error claiming pending tasks: {e}")
            return []
    
    def get_stream_info(self) -> Dict[str, Any]:
        """Get stream and consumer group statistics"""
        try:
            stream_info = self.redis.xinfo_stream(self.stream_name)
            group_info = self.redis.xinfo_groups(self.stream_name)
            
            return {
                'stream_name': self.stream_name,
                'length': stream_info.get('length', 0),
                'groups': len(group_info),
                'first_entry': stream_info.get('first-entry'),
                'last_entry': stream_info.get('last-entry'),
                'group_info': group_info
            }
        except Exception as e:
            logger.error(f"Error getting stream info: {e}")
            return {}
    
    def get_dlq_tasks(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get tasks from dead letter queue"""
        try:
            messages = self.redis.xrange(self.dlq_stream, count=count)
            
            dlq_tasks = []
            for msg_id, fields in messages:
                decoded_fields = {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in fields.items()
                }
                
                dlq_tasks.append({
                    'dlq_id': msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                    'original_task_id': decoded_fields.get('original_task_id'),
                    'task_type': decoded_fields.get('task_type'),
                    'failure_reason': decoded_fields.get('failure_reason'),
                    'failed_at': decoded_fields.get('failed_at'),
                    'retry_count': int(decoded_fields.get('retry_count', 0))
                })
            
            return dlq_tasks
            
        except Exception as e:
            logger.error(f"Error getting DLQ tasks: {e}")
            return []


class TaskPriorityQueue:
    """
    Priority queue for tasks using Redis sorted sets.
    
    Higher priority tasks are processed first.
    """
    
    def __init__(self, redis_client: redis.Redis, queue_name: str):
        """
        Initialize priority queue.
        
        Args:
            redis_client: Redis client instance
            queue_name: Name of priority queue
        """
        self.redis = redis_client
        self.queue_name = queue_name
    
    def add_task(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        priority: int = 0
    ):
        """
        Add task to priority queue.
        
        Args:
            task_id: Unique task ID
            task_data: Task data
            priority: Priority (higher = more important)
        """
        # Store task data
        task_key = f"{self.queue_name}:task:{task_id}"
        self.redis.set(task_key, json.dumps(task_data))
        
        # Add to priority queue (negative priority for descending order)
        self.redis.zadd(self.queue_name, {task_id: -priority})
        
        logger.debug(f"Added task {task_id} with priority {priority}")
    
    def pop_task(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Pop highest priority task from queue.
        
        Returns:
            (task_id, task_data) or None if queue empty
        """
        # Pop highest priority (lowest score due to negation)
        result = self.redis.zpopmin(self.queue_name)
        
        if not result:
            return None
        
        task_id, _ = result[0]
        task_id = task_id.decode() if isinstance(task_id, bytes) else task_id
        
        # Get task data
        task_key = f"{self.queue_name}:task:{task_id}"
        task_data_json = self.redis.get(task_key)
        
        if task_data_json:
            task_data = json.loads(task_data_json)
            self.redis.delete(task_key)
            return (task_id, task_data)
        
        return None
    
    def get_queue_size(self) -> int:
        """Get number of tasks in queue"""
        return self.redis.zcard(self.queue_name)
    
    def peek_tasks(self, count: int = 10) -> List[Tuple[str, int]]:
        """
        Peek at highest priority tasks without removing them.
        
        Returns:
            List of (task_id, priority) tuples
        """
        results = self.redis.zrange(
            self.queue_name,
            0,
            count - 1,
            withscores=True
        )
        
        return [
            (
                task_id.decode() if isinstance(task_id, bytes) else task_id,
                -int(score)  # Convert back to positive priority
            )
            for task_id, score in results
        ]
