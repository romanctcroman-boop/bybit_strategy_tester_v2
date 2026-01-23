"""
Celery Application Configuration

Модуль конфигурации Celery для асинхронных задач оптимизации.
Поддерживает Redis как брокер и backend для результатов.
"""

import os

from celery import Celery
from loguru import logger

# Celery configuration from environment
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")
CELERY_EAGER = os.getenv("CELERY_EAGER", "0").lower() in ("1", "true", "yes")

# Create Celery application
celery_app = Celery(
    "backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.optimize_tasks",
        "backend.tasks.backtest_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # Soft limit 55 min
    # Worker settings
    worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH_MULTIPLIER", "4")),
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "4")),
    # Result settings
    result_expires=86400,  # Results expire in 24 hours
    # Reliability
    task_acks_late=os.getenv("CELERY_ACKS_LATE", "1").lower() in ("1", "true", "yes"),
    task_reject_on_worker_lost=True,
    # Retry policy
    task_default_retry_delay=int(os.getenv("CELERY_TASK_DEFAULT_RETRY_DELAY", "5")),
    # Eager mode for testing (synchronous execution)
    task_always_eager=CELERY_EAGER,
    task_eager_propagates=CELERY_EAGER,
    # Queues for different optimization types
    task_routes={
        "backend.tasks.optimize_tasks.grid_search_task": {
            "queue": "optimizations.grid"
        },
        "backend.tasks.optimize_tasks.walk_forward_task": {
            "queue": "optimizations.walk"
        },
        "backend.tasks.optimize_tasks.bayesian_optimization_task": {
            "queue": "optimizations.bayes"
        },
        "backend.tasks.backtest_tasks.*": {"queue": "backtests"},
    },
    # Default queue
    task_default_queue=os.getenv("CELERY_TASK_DEFAULT_QUEUE", "default"),
)

# Beat schedule for periodic tasks (optional)
celery_app.conf.beat_schedule = {
    # Example: periodic cleanup every hour
    # 'cleanup-expired-results': {
    #     'task': 'backend.tasks.maintenance.cleanup_expired',
    #     'schedule': 3600.0,
    # },
}

logger.info(
    f"✅ Celery app configured | "
    f"Broker: {CELERY_BROKER_URL} | "
    f"Backend: {CELERY_RESULT_BACKEND} | "
    f"Eager: {CELERY_EAGER}"
)


# Export for external imports
__all__ = ["celery_app"]
