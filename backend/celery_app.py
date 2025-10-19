"""
Celery Application Configuration

Настройка Celery для асинхронных задач бэктеста и оптимизации.
"""

from celery import Celery
from loguru import logger

from backend.core.config import settings

# Создание Celery app
celery_app = Celery(
    "bybit_strategy_tester",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=[
        "backend.tasks.backtest_tasks",
        "backend.tasks.optimize_tasks",
    ]
)

# Конфигурация Celery
celery_app.conf.update(
    # Task routing
    task_routes={
        "backend.tasks.backtest_tasks.*": {"queue": "backtest"},
        "backend.tasks.optimize_tasks.*": {"queue": "optimization"},
    },
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,
    
    # Task settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
    
    # Retry settings
    task_acks_late=True,  # Ack after task completion
    task_reject_on_worker_lost=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

logger.info("✅ Celery app configured")
logger.info(f"   Broker: {settings.broker_url}")
logger.info(f"   Backend: {settings.result_backend_url}")


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    logger.info(f"Request: {self.request!r}")
    return {"status": "ok", "message": "Celery is working!"}
