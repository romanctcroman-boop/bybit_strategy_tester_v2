"""
Redis Streams Queue Manager
Замена Celery для легковесной обработки задач с SLA-гарантиями
"""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    # Fallback для старых версий redis
    try:
        import aioredis
    except ImportError:
        raise ImportError("Install redis with: pip install redis>=5.0.0")

from loguru import logger


class TaskStatus(str, Enum):
    """Статусы задач"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """Приоритеты задач"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class Task:
    """Модель задачи"""
    task_id: str
    task_type: str  # 'backtest', 'optimization', 'data_fetch'
    payload: dict[str, Any]
    priority: int = TaskPriority.NORMAL.value
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 3600  # 1 час по умолчанию
    created_at: float = None
    started_at: float | None = None
    completed_at: float | None = None
    status: str = TaskStatus.PENDING.value
    error_message: str | None = None
    result: dict[str, Any] | None = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализация в dict для Redis"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Task':
        """Десериализация из dict"""
        return cls(**data)


class RedisQueueManager:
    """
    Менеджер очередей на Redis Streams
    
    Особенности:
    - Consumer Groups для параллельной обработки
    - Автоматический retry с exponential backoff
    - Dead Letter Queue для проблемных задач
    - Мониторинг метрик (Prometheus-ready)
    - Graceful shutdown
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream_name: str = "bybit:tasks",
        consumer_group: str = "workers",
        consumer_name: str | None = None,
        max_pending_tasks: int = 1000,
        batch_size: int = 10,
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"worker-{uuid.uuid4().hex[:8]}"
        self.max_pending_tasks = max_pending_tasks
        self.batch_size = batch_size
        
        self._redis: aioredis.Redis | None = None
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Метрики - теперь в Redis Hash для multi-process sync
        self.metrics_key = f"{stream_name}:metrics"
    
    async def connect(self):
        """Подключение к Redis"""
        try:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Проверить подключение
            await self._redis.ping()
            
            # Инициализировать Redis Hash metrics
            await self._init_metrics()
            
            # Создать Consumer Group если не существует
            try:
                await self._redis.xgroup_create(
                    name=self.stream_name,
                    groupname=self.consumer_group,
                    id="0",
                    mkstream=True
                )
                logger.info(f"✅ Created consumer group: {self.consumer_group}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"Consumer group already exists: {self.consumer_group}")
                else:
                    raise
                    
            logger.info(f"✅ Connected to Redis: {self.redis_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("✅ Disconnected from Redis")
    
    async def _init_metrics(self):
        """Инициализация metrics в Redis Hash"""
        # Проверить существование ключей, если нет - установить 0
        for metric in ["tasks_submitted", "tasks_completed", "tasks_failed", "tasks_timeout"]:
            exists = await self._redis.hexists(self.metrics_key, metric)
            if not exists:
                await self._redis.hset(self.metrics_key, metric, 0)
        logger.debug(f"✅ Metrics initialized in Redis Hash: {self.metrics_key}")
    
    def register_handler(self, task_type: str, handler: Callable):
        """
        Регистрация обработчика для типа задачи
        
        Args:
            task_type: Тип задачи ('backtest', 'optimization')
            handler: Async функция-обработчик
        """
        self._handlers[task_type] = handler
        logger.info(f"📝 Registered handler for task_type: {task_type}")
    
    async def submit_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        priority: int = TaskPriority.NORMAL.value,
        max_retries: int = 3,
        timeout_seconds: int = 3600,
    ) -> str:
        """
        Отправка задачи в очередь
        
        Returns:
            task_id: ID созданной задачи
        """
        task = Task(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        
        # Добавить в Redis Stream
        await self._redis.xadd(
            name=self.stream_name,
            fields={"data": json.dumps(task.to_dict())},
            maxlen=self.max_pending_tasks,
        )
        
        # ATOMIC increment в Redis Hash
        await self._redis.hincrby(self.metrics_key, "tasks_submitted", 1)
        logger.info(f"📤 Submitted task {task.task_id} (type: {task_type}, priority: {priority})")
        
        return task.task_id
    
    async def start_worker(self):
        """
        Запуск worker для обработки задач
        Блокирующий вызов - запускать в отдельной задаче
        """
        self._running = True
        logger.info(f"🚀 Worker {self.consumer_name} started")
        
        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    # Читать задачи из stream (blocking read)
                    messages = await self._redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_name,
                        streams={self.stream_name: ">"},
                        count=self.batch_size,
                        block=5000,  # 5 сек timeout
                    )
                    
                    if not messages:
                        continue
                    
                    # Обработать batch задач
                    for stream, msg_list in messages:
                        for msg_id, fields in msg_list:
                            await self._process_message(msg_id, fields)
                
                except asyncio.CancelledError:
                    logger.info("Worker received cancellation")
                    break
                except Exception as e:
                    # Игнорировать ошибки закрытия соединения при shutdown
                    if "Connection closed" in str(e) and not self._running:
                        break
                    logger.error(f"❌ Worker error: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Backoff
        
        finally:
            logger.info(f"🛑 Worker {self.consumer_name} stopped")
    
    async def _process_message(self, msg_id: str, fields: dict[str, str]):
        """Обработка одного сообщения из stream"""
        try:
            # Десериализовать задачу
            task_data = json.loads(fields["data"])
            task = Task.from_dict(task_data)
            
            # Проверить timeout
            if task.started_at:
                elapsed = time.time() - task.started_at
                if elapsed > task.timeout_seconds:
                    logger.warning(f"⏰ Task {task.task_id} timeout ({elapsed:.1f}s > {task.timeout_seconds}s)")
                    task.status = TaskStatus.TIMEOUT.value
                    await self._handle_failed_task(task, msg_id, "Task timeout")
                    return
            
            # Найти обработчик
            handler = self._handlers.get(task.task_type)
            if not handler:
                logger.error(f"❌ No handler for task_type: {task.task_type}")
                await self._redis.xack(self.stream_name, self.consumer_group, msg_id)
                return
            
            # Обновить статус
            task.status = TaskStatus.RUNNING.value
            task.started_at = time.time()
            
            logger.info(f"▶️  Processing task {task.task_id} (type: {task.task_type})")
            
            # Выполнить обработчик
            result = await handler(task.payload)
            
            # Успех
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = time.time()
            task.result = result
            
            # ATOMIC increment в Redis Hash
            await self._redis.hincrby(self.metrics_key, "tasks_completed", 1)
            
            logger.success(f"✅ Task {task.task_id} completed in {task.completed_at - task.started_at:.2f}s")
            
            # ACK message
            await self._redis.xack(self.stream_name, self.consumer_group, msg_id)
            
            # Удалить из stream (cleanup)
            await self._redis.xdel(self.stream_name, msg_id)
        
        except Exception as e:
            logger.error(f"❌ Task processing error: {e}", exc_info=True)
            
            # Retry logic
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING.value
                # Exponential backoff
                delay = 2 ** task.retry_count
                logger.warning(f"🔄 Retrying task {task.task_id} in {delay}s (attempt {task.retry_count}/{task.max_retries})")
                await asyncio.sleep(delay)
                # Re-submit
                await self._redis.xadd(
                    name=self.stream_name,
                    fields={"data": json.dumps(task.to_dict())},
                )
            else:
                await self._handle_failed_task(task, msg_id, str(e))
    
    async def _handle_failed_task(self, task: Task, msg_id: str, error: str):
        """Обработка проваленной задачи (Dead Letter Queue)"""
        task.status = TaskStatus.FAILED.value
        task.error_message = error
        
        # ATOMIC increment в Redis Hash
        await self._redis.hincrby(self.metrics_key, "tasks_failed", 1)
        
        # Переместить в DLQ
        dlq_stream = f"{self.stream_name}:dlq"
        await self._redis.xadd(
            name=dlq_stream,
            fields={"data": json.dumps(task.to_dict())},
        )
        
        # ACK и удалить из основного stream
        await self._redis.xack(self.stream_name, self.consumer_group, msg_id)
        await self._redis.xdel(self.stream_name, msg_id)
        
        logger.error(f"💀 Task {task.task_id} moved to DLQ: {error}")
    
    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Получить статус задачи по ID"""
        # TODO: Реализовать хранение статусов в отдельном hash
        return None
    
    async def shutdown(self, timeout: int = 30):
        """Graceful shutdown worker"""
        logger.info(f"🛑 Shutting down worker {self.consumer_name}...")
        self._running = False
        self._shutdown_event.set()
        
        # Ждать завершения активных задач
        start = time.time()
        # Получить active tasks из Redis Stream
        try:
            info = await self._redis.xinfo_stream(self.stream_name)
            active_tasks = info.get('length', 0)
        except:
            active_tasks = 0
        
        while active_tasks > 0 and (time.time() - start) < timeout:
            logger.info(f"⏳ Waiting for {active_tasks} active tasks...")
            await asyncio.sleep(1)
            try:
                info = await self._redis.xinfo_stream(self.stream_name)
                active_tasks = info.get('length', 0)
            except:
                break
        
        await self.disconnect()
        logger.info("✅ Worker shutdown complete")
    
    def get_metrics(self) -> dict[str, int]:
        """
        Получить метрики из Redis Hash (синхронизировано между всеми процессами)
        
        Использует Redis Hash для atomic counters - работает в multi-process окружении
        """
        try:
            if self._redis is None:
                return {
                    "tasks_submitted": 0,
                    "tasks_completed": 0,
                    "tasks_failed": 0,
                    "tasks_timeout": 0,
                    "active_tasks": 0,
                }
            
            # Синхронный Redis client для sync метода
            import redis
            sync_redis = redis.from_url(self.redis_url, decode_responses=True)
            
            # Читаем все метрики из Redis Hash АТОМАРНО
            metrics_data = sync_redis.hgetall(self.metrics_key)
            
            # Получить pending tasks из stream
            try:
                info = sync_redis.xinfo_stream(self.stream_name)
                active_tasks = info.get('length', 0)
            except:
                active_tasks = 0
            
            sync_redis.close()
            
            return {
                "tasks_submitted": int(metrics_data.get("tasks_submitted", 0)),
                "tasks_completed": int(metrics_data.get("tasks_completed", 0)),
                "tasks_failed": int(metrics_data.get("tasks_failed", 0)),
                "tasks_timeout": int(metrics_data.get("tasks_timeout", 0)),
                "active_tasks": active_tasks,
            }
        except Exception as e:
            logger.warning(f"Failed to get metrics from Redis: {e}")
            return {
                "tasks_submitted": 0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "tasks_timeout": 0,
                "active_tasks": 0,
            }
