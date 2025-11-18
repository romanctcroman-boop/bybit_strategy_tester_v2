"""
Queue Adapter - Unified interface для замены Celery на Redis Streams

Предоставляет обратно-совместимый API для существующего кода,
который использует Celery tasks.
"""

import asyncio
from typing import Any

from loguru import logger

from backend.queue.redis_queue_manager import RedisQueueManager, TaskPriority


class QueueAdapter:
    """
    Адаптер для замены Celery на Redis Streams
    
    Использование:
        # Вместо:
        from backend.tasks.backtest_tasks import run_backtest_task
        task = run_backtest_task.delay(...)
        
        # Используйте:
        from backend.queue.adapter import queue_adapter
        task_id = await queue_adapter.submit_backtest(...)
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._qm: RedisQueueManager | None = None
        self._loop = None
    
    def _get_or_create_loop(self):
        """Получить event loop (создать если нужно)"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    async def _ensure_connected(self):
        """Подключиться к Redis если ещё не подключен"""
        if self._qm is None:
            self._qm = RedisQueueManager(redis_url=self.redis_url)
            await self._qm.connect()
            logger.info("✅ QueueAdapter connected to Redis")
    
    async def submit_backtest(
        self,
        backtest_id: int,
        strategy_config: dict[str, Any],
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        priority: int = TaskPriority.NORMAL.value,
    ) -> str:
        """
        Отправить задачу бэктеста
        
        Args:
            backtest_id: ID бэктеста в БД
            strategy_config: Конфигурация стратегии
            symbol: Торговая пара
            interval: Таймфрейм
            start_date: Дата начала
            end_date: Дата окончания
            initial_capital: Начальный капитал
            priority: Приоритет задачи
            
        Returns:
            task_id: UUID задачи
        """
        await self._ensure_connected()
        
        task_id = await self._qm.submit_task(
            task_type="backtest",
            payload={
                "backtest_id": backtest_id,
                "strategy_config": strategy_config,
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
            },
            priority=priority,
            max_retries=3,
            timeout_seconds=3600,
        )
        
        logger.info(f"📤 Submitted backtest task: {task_id} (backtest_id={backtest_id})")
        return task_id
    
    async def submit_grid_search(
        self,
        optimization_id: int,
        strategy_config: dict[str, Any],
        param_space: dict[str, list],
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        metric: str = "sharpe_ratio",
        priority: int = TaskPriority.NORMAL.value,
    ) -> str:
        """Отправить задачу Grid Search оптимизации"""
        await self._ensure_connected()
        
        task_id = await self._qm.submit_task(
            task_type="optimization",
            payload={
                "optimization_id": optimization_id,
                "optimization_type": "grid",
                "strategy_config": strategy_config,
                "param_space": param_space,
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
                "metric": metric,
            },
            priority=priority,
            max_retries=2,
            timeout_seconds=7200,  # 2 часа для оптимизации
        )
        
        logger.info(f"📤 Submitted grid search task: {task_id}")
        return task_id
    
    async def submit_walk_forward(
        self,
        optimization_id: int,
        strategy_config: dict[str, Any],
        param_space: dict[str, list],
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        train_size: int = 120,
        test_size: int = 60,
        step_size: int = 30,
        metric: str = "sharpe_ratio",
        priority: int = TaskPriority.NORMAL.value,
    ) -> str:
        """Отправить задачу Walk-Forward оптимизации"""
        await self._ensure_connected()
        
        task_id = await self._qm.submit_task(
            task_type="optimization",
            payload={
                "optimization_id": optimization_id,
                "optimization_type": "walk_forward",
                "strategy_config": strategy_config,
                "param_space": param_space,
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
                "train_size": train_size,
                "test_size": test_size,
                "step_size": step_size,
                "metric": metric,
            },
            priority=priority,
            max_retries=2,
            timeout_seconds=7200,
        )
        
        logger.info(f"📤 Submitted walk-forward task: {task_id}")
        return task_id
    
    async def submit_bayesian(
        self,
        optimization_id: int,
        strategy_config: dict[str, Any],
        param_space: dict[str, dict[str, Any]],
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        n_trials: int = 100,
        metric: str = "sharpe_ratio",
        direction: str = "maximize",
        priority: int = TaskPriority.NORMAL.value,
    ) -> str:
        """Отправить задачу Bayesian оптимизации"""
        await self._ensure_connected()
        
        task_id = await self._qm.submit_task(
            task_type="optimization",
            payload={
                "optimization_id": optimization_id,
                "optimization_type": "bayesian",
                "strategy_config": strategy_config,
                "param_space": param_space,
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
                "n_trials": n_trials,
                "metric": metric,
                "direction": direction,
            },
            priority=priority,
            max_retries=2,
            timeout_seconds=7200,
        )
        
        logger.info(f"📤 Submitted bayesian optimization task: {task_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Получить статус задачи по ID"""
        await self._ensure_connected()
        return await self._qm.get_task_status(task_id)
    
    def get_metrics(self) -> dict[str, int]:
        """Получить метрики очереди"""
        if self._qm is None:
            return {
                "tasks_submitted": 0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "tasks_timeout": 0,
                "active_tasks": 0,
            }
        return self._qm.get_metrics()
    
    async def disconnect(self):
        """Отключиться от Redis"""
        if self._qm:
            await self._qm.disconnect()
            self._qm = None
            logger.info("✅ QueueAdapter disconnected")
    
    # Sync wrappers для обратной совместимости с не-async кодом
    def submit_backtest_sync(self, **kwargs) -> str:
        """Синхронная версия submit_backtest"""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(self.submit_backtest(**kwargs))
    
    def submit_grid_search_sync(self, **kwargs) -> str:
        """Синхронная версия submit_grid_search"""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(self.submit_grid_search(**kwargs))
    
    def submit_walk_forward_sync(self, **kwargs) -> str:
        """Синхронная версия submit_walk_forward"""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(self.submit_walk_forward(**kwargs))
    
    def submit_bayesian_sync(self, **kwargs) -> str:
        """Синхронная версия submit_bayesian"""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(self.submit_bayesian(**kwargs))


# Глобальный singleton для использования в API
_queue_adapter: QueueAdapter | None = None


def get_queue_adapter() -> QueueAdapter:
    """Получить singleton queue adapter"""
    global _queue_adapter
    if _queue_adapter is None:
        import os
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _queue_adapter = QueueAdapter(redis_url=redis_url)
    return _queue_adapter


# Convenience alias
queue_adapter = get_queue_adapter()
