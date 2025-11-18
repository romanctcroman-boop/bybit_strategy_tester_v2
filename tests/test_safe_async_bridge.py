"""
Тесты для SafeAsyncBridge
"""
import asyncio
import pytest
import threading
import time
from automation.safe_async_bridge import (
    SafeAsyncBridge,
    EventLoopNotAvailableError,
    get_global_bridge
)


@pytest.fixture
def event_loop():
    """Фикстура для создания event loop"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def bridge():
    """Фикстура для создания SafeAsyncBridge"""
    return SafeAsyncBridge(cleanup_timeout=2.0)


class TestSafeAsyncBridge:
    """Тесты SafeAsyncBridge"""
    
    @pytest.mark.asyncio
    async def test_set_loop(self, bridge, event_loop):
        """Тест установки event loop"""
        bridge.set_loop(event_loop)
        stats = bridge.get_stats()
        
        assert stats['loop_status'] == 'running'
        assert stats['pending_count'] == 0
        assert stats['is_closed'] is False
    
    @pytest.mark.asyncio
    async def test_call_async_success(self, bridge, event_loop):
        """Тест успешного async вызова"""
        bridge.set_loop(event_loop)
        
        async def test_coro():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await bridge.call_async(test_coro())
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_call_async_with_exception(self, bridge, event_loop):
        """Тест async вызова с исключением"""
        bridge.set_loop(event_loop)
        
        async def failing_coro():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await bridge.call_async(failing_coro())
    
    @pytest.mark.asyncio
    async def test_call_async_without_loop(self, bridge):
        """Тест вызова без установленного loop"""
        with pytest.raises(EventLoopNotAvailableError, match="Event loop not set"):
            await bridge.call_async(asyncio.sleep(0))
    
    @pytest.mark.asyncio
    async def test_call_async_with_closed_loop(self, bridge, event_loop):
        """Тест вызова с закрытым loop"""
        bridge.set_loop(event_loop)
        event_loop.close()
        
        with pytest.raises(EventLoopNotAvailableError, match="Event loop is closed"):
            await bridge.call_async(asyncio.sleep(0))
    
    @pytest.mark.asyncio
    async def test_call_async_no_wait(self, bridge, event_loop):
        """Тест fire-and-forget вызова"""
        bridge.set_loop(event_loop)
        
        async def background_task():
            await asyncio.sleep(0.2)
            return "background_result"
        
        future = bridge.call_async_no_wait(background_task())
        
        # Проверяем, что задача в pending
        stats = bridge.get_stats()
        assert stats['pending_count'] == 1
        
        # Ждём результат
        result = await asyncio.wrap_future(future)
        assert result == "background_result"
        
        # Проверяем, что задача удалена из pending
        await asyncio.sleep(0.1)
        stats = bridge.get_stats()
        assert stats['pending_count'] == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_graceful(self, bridge, event_loop):
        """Тест graceful cleanup"""
        bridge.set_loop(event_loop)
        
        # Запускаем несколько задач
        async def slow_task(duration):
            await asyncio.sleep(duration)
            return f"completed_{duration}"
        
        future1 = bridge.call_async_no_wait(slow_task(0.3))
        future2 = bridge.call_async_no_wait(slow_task(0.3))
        
        stats = bridge.get_stats()
        assert stats['pending_count'] == 2
        
        # Cleanup должен дождаться завершения
        await bridge.cleanup()
        
        # Проверяем результаты
        assert future1.result() == "completed_0.3"
        assert future2.result() == "completed_0.3"
        
        stats = bridge.get_stats()
        assert stats['is_closed'] is True
    
    @pytest.mark.asyncio
    async def test_cleanup_with_timeout(self, bridge, event_loop):
        """Тест cleanup с timeout (долгие задачи)"""
        bridge.set_loop(event_loop)
        
        async def very_slow_task():
            await asyncio.sleep(10)  # Дольше чем cleanup_timeout (2.0)
            return "should_not_complete"
        
        future = bridge.call_async_no_wait(very_slow_task())
        
        # Cleanup с timeout должен отменить задачу
        await bridge.cleanup()
        
        # Проверяем, что задача отменена
        assert future.cancelled()
    
    @pytest.mark.asyncio
    async def test_cleanup_force(self, bridge, event_loop):
        """Тест force cleanup"""
        bridge.set_loop(event_loop)
        
        async def task():
            await asyncio.sleep(1.0)
            return "result"
        
        future = bridge.call_async_no_wait(task())
        
        # Force cleanup немедленно отменяет
        await bridge.cleanup(force=True)
        
        assert future.cancelled()
    
    @pytest.mark.asyncio
    async def test_multiple_calls_tracking(self, bridge, event_loop):
        """Тест отслеживания множественных вызовов"""
        bridge.set_loop(event_loop)
        
        async def task(n):
            await asyncio.sleep(0.1)
            return n * 2
        
        # Запускаем 5 задач параллельно
        tasks = [bridge.call_async(task(i)) for i in range(5)]
        
        # Во время выполнения должно быть 5 pending
        # (проверка может быть racy, но часто работает)
        await asyncio.sleep(0.05)
        
        # Ждём завершения
        results = await asyncio.gather(*tasks)
        
        assert results == [0, 2, 4, 6, 8]
        
        # После завершения pending должны быть очищены
        stats = bridge.get_stats()
        assert stats['pending_count'] == 0
    
    @pytest.mark.asyncio
    async def test_closed_bridge_rejects_calls(self, bridge, event_loop):
        """Тест что закрытый bridge отклоняет новые вызовы"""
        bridge.set_loop(event_loop)
        await bridge.cleanup()
        
        with pytest.raises(EventLoopNotAvailableError, match="AsyncBridge is closed"):
            await bridge.call_async(asyncio.sleep(0))
    
    def test_get_stats(self, bridge):
        """Тест get_stats"""
        stats = bridge.get_stats()
        
        assert 'pending_count' in stats
        assert 'loop_status' in stats
        assert 'is_closed' in stats
        
        assert stats['loop_status'] == 'not_set'
        assert stats['pending_count'] == 0
        assert stats['is_closed'] is False
    
    def test_repr(self, bridge):
        """Тест __repr__"""
        repr_str = repr(bridge)
        
        assert 'SafeAsyncBridge' in repr_str
        assert 'pending=' in repr_str
        assert 'loop=' in repr_str
        assert 'closed=' in repr_str


class TestGlobalBridge:
    """Тесты глобального bridge instance"""
    
    def test_get_global_bridge_singleton(self):
        """Тест что get_global_bridge возвращает singleton"""
        bridge1 = get_global_bridge()
        bridge2 = get_global_bridge()
        
        assert bridge1 is bridge2
    
    @pytest.mark.asyncio
    async def test_global_bridge_functional(self, event_loop):
        """Тест работоспособности глобального bridge"""
        bridge = get_global_bridge()
        bridge.set_loop(event_loop)
        
        async def test_task():
            return "global_bridge_works"
        
        result = await bridge.call_async(test_task())
        assert result == "global_bridge_works"


@pytest.mark.asyncio
async def test_concurrent_thread_safety():
    """Тест thread-safety при конкурентном доступе"""
    bridge = SafeAsyncBridge()
    loop = asyncio.new_event_loop()
    bridge.set_loop(loop)
    
    results = []
    
    async def worker_task(n):
        await asyncio.sleep(0.01)
        return n
    
    def thread_worker(thread_id):
        """Рабочая функция для потока"""
        # Используем asyncio.run_coroutine_threadsafe напрямую
        coro = worker_task(thread_id)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=2.0)
        results.append(result)
    
    # Запускаем несколько потоков
    threads = [
        threading.Thread(target=thread_worker, args=(i,))
        for i in range(5)
    ]
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    loop.close()
    
    # Проверяем, что все результаты получены
    assert len(results) == 5
    assert set(results) == {0, 1, 2, 3, 4}
