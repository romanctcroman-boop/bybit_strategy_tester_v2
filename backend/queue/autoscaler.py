"""
Auto-Scaling Controller with SLA-driven policies

Автоматически масштабирует количество workers на основе метрик очереди
"""

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

try:
    import redis.asyncio as aioredis
except ImportError:
    try:
        import aioredis
    except ImportError:
        raise ImportError("Install redis with: pip install redis>=5.0.0")


@dataclass
class SLATarget:
    """SLA метрики для масштабирования"""
    max_queue_latency_seconds: float = 300.0  # 5 минут
    min_throughput_tasks_per_minute: float = 10.0
    max_worker_utilization: float = 0.8  # 80%
    target_worker_utilization: float = 0.6  # 60% (оптимальная загрузка)


@dataclass
class ScalingMetrics:
    """Метрики для принятия решений о масштабировании"""
    pending_tasks: int
    active_tasks: int
    avg_task_duration_seconds: float
    queue_latency_seconds: float
    worker_count: int
    cpu_usage: float = 0.0  # опционально


class AutoScaler:
    """
    Автомасштабирование workers на основе SLA
    
    Стратегии масштабирования:
    - Scale UP: если queue latency > SLA или utilization > 80%
    - Scale DOWN: если utilization < 20% и queue latency в норме
    - Cooldown: 60 сек между изменениями (предотвращение flapping)
    
    Пример использования:
        scaler = AutoScaler(redis_url="redis://localhost:6379/0")
        await scaler.connect()
        await scaler.run(interval_seconds=30)
    """
    
    def __init__(
        self,
        redis_url: str,
        stream_name: str = "bybit:tasks",
        consumer_group: str = "workers",
        sla_target: SLATarget | None = None,
        min_workers: int = 1,
        max_workers: int = 10,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2,
        cooldown_seconds: int = 60,
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.sla_target = sla_target or SLATarget()
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.cooldown_seconds = cooldown_seconds
        
        self._redis: aioredis.Redis | None = None
        self._last_scale_time = 0.0
        self._running = False
        
        # История метрик для расчёта средних значений
        self._metrics_history = []
        self._max_history_size = 10
    
    async def connect(self):
        """Подключение к Redis"""
        self._redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await self._redis.ping()
        logger.info(f"✅ AutoScaler connected to Redis: {self.redis_url}")
    
    async def disconnect(self):
        """Отключение"""
        if self._redis:
            await self._redis.close()
            logger.info("✅ AutoScaler disconnected")
    
    async def get_metrics(self) -> ScalingMetrics:
        """Собрать метрики из Redis"""
        try:
            # Получить информацию о stream
            stream_info = await self._redis.xinfo_stream(self.stream_name)
            pending_tasks = stream_info.get("length", 0)
            
            # Получить активные задачи из consumer groups
            try:
                groups_info = await self._redis.xinfo_groups(self.stream_name)
                active_tasks = sum(g.get("pending", 0) for g in groups_info)
            except Exception:
                active_tasks = 0
            
            # Получить worker count
            # Предполагаем, что workers регистрируют себя в Redis Set
            worker_count = await self._redis.scard("workers:active")
            if worker_count == 0:
                # Если workers не регистрируются, использовать fallback
                worker_count = 1
            
            # Рассчитать queue latency (approx)
            queue_latency = 0.0
            if pending_tasks > 0:
                try:
                    # Взять первое сообщение и посмотреть его timestamp
                    messages = await self._redis.xrange(self.stream_name, count=1)
                    if messages:
                        msg_id = messages[0][0]
                        # msg_id format: "<timestamp_ms>-<seq>"
                        timestamp_ms = int(msg_id.split("-")[0])
                        queue_latency = (time.time() * 1000 - timestamp_ms) / 1000.0
                except Exception as e:
                    logger.debug(f"Could not calculate queue latency: {e}")
            
            # Средняя длительность задачи (из истории или заглушка)
            avg_duration = 60.0  # 1 минута по умолчанию
            if self._metrics_history:
                # Можно рассчитывать из завершённых задач
                pass
            
            metrics = ScalingMetrics(
                pending_tasks=pending_tasks,
                active_tasks=active_tasks,
                avg_task_duration_seconds=avg_duration,
                queue_latency_seconds=queue_latency,
                worker_count=worker_count,
            )
            
            # Добавить в историю
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history_size:
                self._metrics_history.pop(0)
            
            return metrics
        
        except Exception as e:
            logger.error(f"❌ Failed to get metrics: {e}", exc_info=True)
            # Вернуть дефолтные метрики
            return ScalingMetrics(
                pending_tasks=0,
                active_tasks=0,
                avg_task_duration_seconds=60.0,
                queue_latency_seconds=0.0,
                worker_count=1,
            )
    
    def should_scale_up(self, metrics: ScalingMetrics) -> bool:
        """Проверить, нужно ли масштабировать вверх"""
        # SLA violation: queue latency
        if metrics.queue_latency_seconds > self.sla_target.max_queue_latency_seconds:
            logger.warning(
                f"⚠️ SLA violation: queue latency {metrics.queue_latency_seconds:.1f}s "
                f"> {self.sla_target.max_queue_latency_seconds}s"
            )
            return True
        
        # High utilization
        if metrics.worker_count > 0:
            utilization = metrics.active_tasks / metrics.worker_count
            if utilization > self.scale_up_threshold:
                logger.warning(
                    f"⚠️ High utilization: {utilization:.1%} > {self.scale_up_threshold:.1%}"
                )
                return True
        
        # Большая очередь ожидающих задач
        if metrics.pending_tasks > metrics.worker_count * 5:
            logger.warning(
                f"⚠️ Large queue: {metrics.pending_tasks} pending tasks "
                f"for {metrics.worker_count} workers"
            )
            return True
        
        return False
    
    def should_scale_down(self, metrics: ScalingMetrics) -> bool:
        """Проверить, нужно ли масштабировать вниз"""
        if metrics.worker_count <= self.min_workers:
            return False
        
        if metrics.worker_count > 0:
            utilization = metrics.active_tasks / metrics.worker_count
            
            # Low utilization и queue в норме
            if (utilization < self.scale_down_threshold and
                metrics.queue_latency_seconds < self.sla_target.max_queue_latency_seconds * 0.5 and
                metrics.pending_tasks < metrics.worker_count):
                logger.info(
                    f"✅ Low utilization: {utilization:.1%} < {self.scale_down_threshold:.1%}"
                )
                return True
        
        return False
    
    async def scale_up(self, current_workers: int) -> int:
        """
        Масштабировать вверх (добавить worker)
        
        Returns:
            Новое количество workers
        """
        new_count = min(current_workers + 1, self.max_workers)
        
        if new_count == current_workers:
            logger.info(f"⚠️ Already at max workers: {self.max_workers}")
            return new_count
        
        logger.info(f"📈 Scaling UP: {current_workers} → {new_count} workers")
        
        # TODO: Здесь должна быть логика запуска нового worker процесса
        # Варианты реализации:
        # 1. subprocess.Popen([sys.executable, "-m", "backend.queue.worker_cli"])
        # 2. Docker API: docker.from_env().containers.run(...)
        # 3. Kubernetes API: client.AppsV1Api().patch_namespaced_deployment(...)
        
        # Заглушка: вывести команду для запуска
        logger.info(
            "💡 To scale up manually, run: "
            "python -m backend.queue.worker_cli --workers 1"
        )
        
        return new_count
    
    async def scale_down(self, current_workers: int) -> int:
        """
        Масштабировать вниз (удалить worker)
        
        Returns:
            Новое количество workers
        """
        new_count = max(current_workers - 1, self.min_workers)
        
        if new_count == current_workers:
            logger.info(f"⚠️ Already at min workers: {self.min_workers}")
            return new_count
        
        logger.info(f"📉 Scaling DOWN: {current_workers} → {new_count} workers")
        
        # TODO: Логика graceful shutdown одного worker
        # Можно использовать Redis pub/sub для отправки команды shutdown
        
        logger.info(
            "💡 To scale down manually, stop one worker process"
        )
        
        return new_count
    
    async def run(self, interval_seconds: int = 30):
        """
        Основной цикл автомасштабирования
        
        Args:
            interval_seconds: Интервал проверки метрик (default: 30 сек)
        """
        self._running = True
        logger.info("🤖 AutoScaler started")
        
        try:
            while self._running:
                try:
                    # Собрать метрики
                    metrics = await self.get_metrics()
                    
                    logger.info(
                        f"📊 Metrics: pending={metrics.pending_tasks}, "
                        f"active={metrics.active_tasks}, "
                        f"workers={metrics.worker_count}, "
                        f"latency={metrics.queue_latency_seconds:.1f}s"
                    )
                    
                    # Проверить cooldown
                    now = time.time()
                    cooldown_remaining = self.cooldown_seconds - (now - self._last_scale_time)
                    
                    if cooldown_remaining > 0:
                        logger.debug(
                            f"⏳ Cooldown active ({cooldown_remaining:.0f}s remaining)"
                        )
                        await asyncio.sleep(interval_seconds)
                        continue
                    
                    # Принять решение о масштабировании
                    if self.should_scale_up(metrics):
                        new_count = await self.scale_up(metrics.worker_count)
                        self._last_scale_time = now
                    elif self.should_scale_down(metrics):
                        new_count = await self.scale_down(metrics.worker_count)
                        self._last_scale_time = now
                    else:
                        logger.debug("✅ No scaling needed")
                    
                    await asyncio.sleep(interval_seconds)
                
                except Exception as e:
                    logger.error(f"❌ AutoScaler error: {e}", exc_info=True)
                    await asyncio.sleep(interval_seconds)
        
        finally:
            logger.info("🛑 AutoScaler stopped")
    
    async def stop(self):
        """Остановить автомасштабирование"""
        self._running = False
        await self.disconnect()


# CLI для запуска AutoScaler
if __name__ == "__main__":
    import os

    import click
    
    @click.command()
    @click.option('--redis-url', default=lambda: os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
    @click.option('--min-workers', default=1, type=int)
    @click.option('--max-workers', default=10, type=int)
    @click.option('--interval', default=30, type=int, help='Check interval in seconds')
    def main(redis_url: str, min_workers: int, max_workers: int, interval: int):
        """Start AutoScaler"""
        scaler = AutoScaler(
            redis_url=redis_url,
            min_workers=min_workers,
            max_workers=max_workers,
        )
        
        async def run():
            await scaler.connect()
            await scaler.run(interval_seconds=interval)
        
        try:
            asyncio.run(run())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
    
    main()
