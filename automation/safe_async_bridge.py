"""
Safe AsyncIO Bridge - Устранение race conditions в многопоточных async операциях
==================================================================================

Проблема (из DeepSeek анализа):
- asyncio.run_coroutine_threadsafe() может использовать stale event loop
- Unawaited futures накапливаются (resource leak)
- Нет error handling при сбое event loop

Решение:
- Отслеживание активного event loop
- Автоматическая очистка pending futures
- Graceful shutdown с timeout
- Thread-safe операции с proper error handling

Использование:
    bridge = SafeAsyncBridge()
    bridge.set_loop(asyncio.get_event_loop())
    
    # В синхронном коде:
    result = await bridge.call_async(some_coroutine())
    
    # При shutdown:
    await bridge.cleanup()
"""

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import Optional, Coroutine, Any, TypeVar, Set

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncBridgeError(Exception):
    """Ошибки AsyncBridge"""
    pass


class EventLoopNotAvailableError(AsyncBridgeError):
    """Event loop недоступен или закрыт"""
    pass


class SafeAsyncBridge:
    """
    Thread-safe мост между синхронным и асинхронным кодом.
    
    Решает проблемы:
    - Race conditions при перезапуске event loop
    - Resource leaks от unawaited futures
    - Отсутствие error handling в thread-safe calls
    
    Features:
    - Автоматическое отслеживание pending операций
    - Graceful cleanup с timeout
    - Thread-safe операции
    - Детальное логирование для debugging
    """
    
    def __init__(self, cleanup_timeout: float = 5.0):
        """
        Args:
            cleanup_timeout: Таймаут для cleanup операций (секунды)
        """
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending: Set[Future] = set()
        self._lock = threading.Lock()
        self._cleanup_timeout = cleanup_timeout
        self._closed = False
        
        logger.info("SafeAsyncBridge initialized")
    
    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Установить event loop для использования.
        
        Args:
            loop: Event loop для асинхронных операций
            
        Raises:
            ValueError: Если loop уже закрыт
        """
        if loop.is_closed():
            raise ValueError("Cannot set closed event loop")
        
        with self._lock:
            old_loop = self._loop
            self._loop = loop
            
        if old_loop and old_loop != loop:
            logger.warning(f"Event loop changed from {old_loop} to {loop}")
        else:
            logger.info(f"Event loop set: {loop}")
    
    def _check_loop_available(self) -> None:
        """
        Проверить доступность event loop.
        
        Raises:
            EventLoopNotAvailableError: Если loop недоступен
        """
        if self._closed:
            raise EventLoopNotAvailableError("AsyncBridge is closed")
            
        if not self._loop:
            raise EventLoopNotAvailableError("Event loop not set. Call set_loop() first.")
            
        if self._loop.is_closed():
            raise EventLoopNotAvailableError("Event loop is closed")
    
    async def call_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Безопасно выполнить coroutine в event loop из синхронного контекста.
        
        Args:
            coro: Coroutine для выполнения
            
        Returns:
            Результат coroutine
            
        Raises:
            EventLoopNotAvailableError: Если event loop недоступен
            Exception: Любые исключения из coroutine пробрасываются
            
        Example:
            result = await bridge.call_async(fetch_data())
        """
        self._check_loop_available()
        
        # Создаём future для thread-safe вызова
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        
        # Добавляем в pending для отслеживания
        with self._lock:
            self._pending.add(future)
        
        try:
            # Ожидаем результат
            result = await asyncio.wrap_future(future)
            logger.debug(f"Async call completed successfully: {coro}")
            return result
            
        except Exception as e:
            logger.error(f"Async call failed: {coro}, error: {e}", exc_info=True)
            raise
            
        finally:
            # Удаляем из pending
            with self._lock:
                self._pending.discard(future)
    
    def call_async_no_wait(self, coro: Coroutine[Any, Any, Any]) -> Future:
        """
        Запустить coroutine без ожидания результата (fire-and-forget).
        
        Args:
            coro: Coroutine для выполнения
            
        Returns:
            Future для отслеживания результата
            
        Raises:
            EventLoopNotAvailableError: Если event loop недоступен
            
        Warning:
            Используйте осторожно! Future должен быть явно awaited 
            или будет очищен при cleanup().
            
        Example:
            future = bridge.call_async_no_wait(background_task())
            # ... позже ...
            result = await asyncio.wrap_future(future)
        """
        self._check_loop_available()
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        
        with self._lock:
            self._pending.add(future)
        
        logger.debug(f"Fire-and-forget async call: {coro}")
        return future
    
    async def cleanup(self, force: bool = False) -> None:
        """
        Graceful cleanup всех pending операций.
        
        Args:
            force: Если True, немедленно отменяет все операции без ожидания
            
        Процесс:
        1. Отмечает bridge как закрытый (новые вызовы блокируются)
        2. Ожидает завершения pending операций с timeout
        3. Отменяет незавершённые операции
        4. Логирует результаты
        """
        logger.info(f"Starting cleanup (force={force}, pending={len(self._pending)})")
        
        with self._lock:
            self._closed = True
            pending_copy = self._pending.copy()
        
        if not pending_copy:
            logger.info("No pending operations to cleanup")
            return
        
        if force:
            # Немедленная отмена всех операций
            for future in pending_copy:
                future.cancel()
            logger.warning(f"Force cancelled {len(pending_copy)} operations")
            return
        
        # Graceful cleanup с timeout
        try:
            done, pending = await asyncio.wait(
                pending_copy,
                timeout=self._cleanup_timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            completed_count = len(done)
            timeout_count = len(pending)
            
            # Отменяем операции, которые не завершились
            for future in pending:
                future.cancel()
            
            logger.info(
                f"Cleanup completed: {completed_count} finished, "
                f"{timeout_count} cancelled after timeout"
            )
            
            # Логируем ошибки из завершённых операций
            for future in done:
                if future.exception():
                    logger.error(
                        f"Pending operation failed during cleanup: {future.exception()}"
                    )
                    
        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            # В случае ошибки cleanup, отменяем всё
            for future in pending_copy:
                future.cancel()
    
    def get_stats(self) -> dict:
        """
        Получить статистику bridge.
        
        Returns:
            Словарь с метриками:
            - pending_count: количество pending операций
            - loop_status: статус event loop
            - is_closed: закрыт ли bridge
        """
        with self._lock:
            stats = {
                "pending_count": len(self._pending),
                "loop_status": (
                    "running" if self._loop and not self._loop.is_closed()
                    else "closed" if self._loop
                    else "not_set"
                ),
                "is_closed": self._closed
            }
        
        return stats
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"SafeAsyncBridge("
            f"pending={stats['pending_count']}, "
            f"loop={stats['loop_status']}, "
            f"closed={stats['is_closed']})"
        )


# Singleton instance для глобального использования (опционально)
_global_bridge: Optional[SafeAsyncBridge] = None


def get_global_bridge() -> SafeAsyncBridge:
    """
    Получить глобальный экземпляр SafeAsyncBridge.
    
    Returns:
        Singleton instance SafeAsyncBridge
        
    Note:
        Не забудьте вызвать set_loop() перед использованием!
    """
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = SafeAsyncBridge()
    return _global_bridge
