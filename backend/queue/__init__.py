"""
Redis Streams Queue Manager

Замена Celery для легковесной обработки задач с SLA-гарантиями
"""

from backend.queue.adapter import QueueAdapter, get_queue_adapter, queue_adapter
from backend.queue.redis_queue_manager import RedisQueueManager, Task, TaskPriority, TaskStatus
from backend.queue.task_handlers import backtest_handler, optimization_handler

__all__ = [
    "RedisQueueManager",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "backtest_handler",
    "optimization_handler",
    "QueueAdapter",
    "get_queue_adapter",
    "queue_adapter",
]
