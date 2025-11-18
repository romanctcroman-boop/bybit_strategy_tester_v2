"""
Sync wrapper для SafeAsyncBridge - удобный интерфейс из sync кода
"""
import asyncio
from typing import Coroutine, Any, TypeVar
from .safe_async_bridge import SafeAsyncBridge

T = TypeVar("T")


class SyncAsyncWrapper:
    """
    Обёртка для вызова async функций из sync кода.
    
    Использование:
        wrapper = SyncAsyncWrapper()
        result = wrapper.call(my_async_function(args))
        wrapper.close()
    
    Или через context manager:
        with SyncAsyncWrapper() as wrapper:
            result = wrapper.call(my_async_function(args))
    """
    
    def __init__(self):
        self._bridge: SafeAsyncBridge | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread = None
        self._started = False
    
    def __enter__(self):
        """Context manager вход"""
        self._start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.close()
        return False
    
    def _start(self):
        """Запускает event loop в отдельном потоке"""
        if self._started:
            return
        
        import threading
        
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            
            # Создаём bridge в этом loop
            self._bridge = SafeAsyncBridge()
            self._bridge.set_loop(loop)
            
            # Запускаем loop
            loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Ждём создания loop
        import time
        for _ in range(100):  # 1 секунда максимум
            if self._loop is not None and self._bridge is not None:
                break
            time.sleep(0.01)
        else:
            raise RuntimeError("Failed to start event loop")
        
        self._started = True
    
    def call(self, coro: Coroutine[Any, Any, T], timeout: float = 30.0) -> T:
        """
        Вызывает async функцию из sync кода.
        
        Args:
            coro: Корутина для выполнения
            timeout: Таймаут в секундах
        
        Returns:
            Результат выполнения корутины
        
        Raises:
            RuntimeError: Если wrapper не запущен
            TimeoutError: Если операция превысила timeout
            Exception: Любое исключение из корутины
        """
        if not self._started:
            self._start()
        
        if self._loop is None or self._bridge is None:
            raise RuntimeError("Wrapper not initialized")
        
        # Создаём future для получения результата
        future = asyncio.run_coroutine_threadsafe(
            self._bridge.call_async(coro),
            self._loop
        )
        
        # Ждём результат с timeout
        try:
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            future.cancel()
            raise TimeoutError(f"Operation timed out after {timeout}s")
    
    def close(self, timeout: float = 5.0):
        """
        Закрывает wrapper и event loop.
        
        Args:
            timeout: Таймаут для graceful shutdown
        """
        if not self._started:
            return
        
        if self._loop is None or self._bridge is None:
            return
        
        # Запускаем cleanup в event loop
        cleanup_future = asyncio.run_coroutine_threadsafe(
            self._bridge.cleanup(force=False),
            self._loop
        )
        
        try:
            cleanup_future.result(timeout=timeout)
        except Exception:
            # Force cleanup если graceful не удался
            pass
        
        # Останавливаем loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        
        # Ждём завершения потока
        if self._loop_thread:
            self._loop_thread.join(timeout=1.0)
        
        self._started = False
    
    def __del__(self):
        """Гарантированная очистка"""
        try:
            self.close(timeout=1.0)
        except:
            pass


# Convenience функция для одиночных вызовов
def run_async(coro: Coroutine[Any, Any, T], timeout: float = 30.0) -> T:
    """
    Быстрый способ вызвать одну async функцию из sync кода.
    
    Для множественных вызовов используйте SyncAsyncWrapper напрямую.
    
    Args:
        coro: Корутина для выполнения
        timeout: Таймаут в секундах
    
    Returns:
        Результат выполнения
    
    Example:
        result = run_async(fetch_data_from_api())
    """
    with SyncAsyncWrapper() as wrapper:
        return wrapper.call(coro, timeout=timeout)
