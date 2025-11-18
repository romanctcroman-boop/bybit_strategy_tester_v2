"""
Правильные async тесты для SafeAsyncBridge
"""
import asyncio
import pytest
from pathlib import Path
import sys

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.safe_async_bridge import SafeAsyncBridge


@pytest.mark.asyncio
async def test_creation():
    """Тест создания моста"""
    bridge = SafeAsyncBridge()
    assert bridge is not None
    assert not bridge._closed
    await bridge.cleanup()


@pytest.mark.asyncio
async def test_stats():
    """Тест статистики"""
    bridge = SafeAsyncBridge()
    stats = bridge.get_stats()
    
    assert "pending_count" in stats
    assert "loop_status" in stats
    assert "is_closed" in stats
    assert stats["pending_count"] == 0
    assert stats["is_closed"] == False
    
    await bridge.cleanup()


@pytest.mark.asyncio
async def test_simple_async_call():
    """Тест простого async вызова"""
    
    async def simple_coro():
        await asyncio.sleep(0.01)
        return "success"
    
    bridge = SafeAsyncBridge()
    
    # Устанавливаем текущий loop
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Вызываем async функцию
    result = await bridge.call_async(simple_coro())
    assert result == "success"
    
    # Проверяем что bridge работает
    stats = bridge.get_stats()
    assert stats["loop_status"] == "running"
    assert stats["is_closed"] == False
    
    await bridge.cleanup()


@pytest.mark.asyncio
async def test_async_with_exception():
    """Тест обработки исключений"""
    
    async def failing_coro():
        await asyncio.sleep(0.01)
        raise ValueError("Test error")
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Исключение должно пробрасываться
    with pytest.raises(ValueError, match="Test error"):
        await bridge.call_async(failing_coro())
    
    # Bridge всё ещё работает
    stats = bridge.get_stats()
    assert stats["is_closed"] == False
    
    await bridge.cleanup()


@pytest.mark.asyncio
async def test_multiple_calls():
    """Тест множественных вызовов"""
    
    async def counter_coro(n):
        await asyncio.sleep(0.001)
        return n * 2
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    results = []
    for i in range(5):
        result = await bridge.call_async(counter_coro(i))
        results.append(result)
    
    assert results == [0, 2, 4, 6, 8]
    
    # Проверяем что bridge работает
    stats = bridge.get_stats()
    assert stats["loop_status"] == "running"
    
    await bridge.cleanup()


@pytest.mark.asyncio  
async def test_cleanup():
    """Тест graceful cleanup"""
    
    async def slow_operation():
        await asyncio.sleep(0.1)
        return "done"
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Запускаем операцию
    task = asyncio.create_task(bridge.call_async(slow_operation()))
    
    # Даём ей начаться
    await asyncio.sleep(0.01)
    
    # Cleanup без force - дождётся завершения
    await bridge.cleanup(force=False)
    
    # Операция должна завершиться успешно
    result = await task
    assert result == "done"
    
    assert bridge._closed


@pytest.mark.asyncio
async def test_force_cleanup():
    """Тест force cleanup"""
    
    async def very_slow_operation():
        await asyncio.sleep(10)  # Очень долго
        return "done"
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Запускаем долгую операцию
    task = asyncio.create_task(bridge.call_async(very_slow_operation()))
    
    # Даём ей начаться
    await asyncio.sleep(0.01)
    
    # Force cleanup - немедленно отменит
    await bridge.cleanup(force=True)
    
    # Task должен быть отменён
    with pytest.raises(asyncio.CancelledError):
        await task
    
    assert bridge._closed


@pytest.mark.asyncio
async def test_closed_bridge_rejects_calls():
    """Тест что закрытый bridge отклоняет вызовы"""
    
    async def simple_coro():
        return "test"
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Закрываем bridge
    await bridge.cleanup()
    
    # Попытка вызова должна падать (EventLoopNotAvailableError)
    from automation.safe_async_bridge import EventLoopNotAvailableError
    with pytest.raises(EventLoopNotAvailableError, match="AsyncBridge is closed"):
        await bridge.call_async(simple_coro())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
