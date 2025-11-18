"""
CLI для запуска Redis Queue Workers
"""

import asyncio
import os
import signal
import sys

import click
from loguru import logger

from backend.queue.redis_queue_manager import RedisQueueManager
from backend.queue.task_handlers import backtest_handler, data_fetch_handler, optimization_handler


class WorkerRunner:
    """Runner для управления worker lifecycle"""
    
    def __init__(self, redis_url: str, num_workers: int = 1):
        self.redis_url = redis_url
        self.num_workers = num_workers
        self.managers = []
        self.tasks = []
    
    async def start(self):
        """Запустить workers"""
        logger.info(f"🚀 Starting {self.num_workers} workers...")
        
        for i in range(self.num_workers):
            manager = RedisQueueManager(
                redis_url=self.redis_url,
                consumer_name=f"worker-{i}"
            )
            
            await manager.connect()
            
            # Регистрация обработчиков
            manager.register_handler("backtest", backtest_handler)
            manager.register_handler("optimization", optimization_handler)
            manager.register_handler("data_fetch", data_fetch_handler)
            
            self.managers.append(manager)
            
            # Запустить worker в отдельной задаче
            task = asyncio.create_task(manager.start_worker())
            self.tasks.append(task)
        
        logger.success(f"✅ {self.num_workers} workers started")
        
        # Настроить signal handlers для graceful shutdown
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            asyncio.create_task(self.shutdown())
        
        # Windows не поддерживает SIGTERM через signal.signal
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, signal_handler)
        
        # Ждать завершения всех задач
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt")
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown всех workers"""
        logger.info("🛑 Shutting down workers...")
        
        # Отменить все задачи
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Shutdown каждого manager
        shutdown_tasks = [m.shutdown() for m in self.managers]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        logger.info("✅ All workers stopped")
        sys.exit(0)


@click.command()
@click.option(
    '--redis-url',
    default=lambda: os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    help='Redis URL (default: from REDIS_URL env or redis://localhost:6379/0)'
)
@click.option(
    '--workers',
    default=4,
    type=int,
    help='Number of worker processes (default: 4)'
)
@click.option(
    '--stream',
    default='bybit:tasks',
    help='Redis stream name (default: bybit:tasks)'
)
@click.option(
    '--group',
    default='workers',
    help='Consumer group name (default: workers)'
)
def main(redis_url: str, workers: int, stream: str, group: str):
    """
    Start Redis Queue Workers
    
    Examples:
        # Start 4 workers (default)
        python -m backend.queue.worker_cli
        
        # Start 8 workers with custom Redis URL
        python -m backend.queue.worker_cli --workers 8 --redis-url redis://localhost:6379/1
        
        # With environment variable
        export REDIS_URL=redis://localhost:6379/0
        python -m backend.queue.worker_cli --workers 4
    """
    logger.info("🎯 Configuration:")
    logger.info(f"   Redis URL: {redis_url}")
    logger.info(f"   Workers: {workers}")
    logger.info(f"   Stream: {stream}")
    logger.info(f"   Group: {group}")
    
    runner = WorkerRunner(redis_url=redis_url, num_workers=workers)
    
    try:
        if sys.platform == "win32":
            # Windows: использовать ProactorEventLoop
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
