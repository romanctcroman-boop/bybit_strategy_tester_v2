"""
Упрощённые тесты для SafeAsyncBridge - без зависаний
"""
import asyncio
import pytest
import time
from pathlib import Path
import sys

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.safe_async_bridge import SafeAsyncBridge


class TestSafeAsyncBridgeBasic:
    """Базовые тесты SafeAsyncBridge"""
    
    def test_creation(self):
        """Тест создания моста"""
        bridge = SafeAsyncBridge()
        assert bridge is not None
        assert not bridge._closed
        bridge.cleanup(force=True, timeout=0.1)
    
    def test_stats(self):
        """Тест статистики"""
        bridge = SafeAsyncBridge()
        stats = bridge.get_stats()
        
        assert "pending_count" in stats
        assert "loop_status" in stats
        assert "is_closed" in stats
        assert stats["pending_count"] == 0
        assert stats["loop_status"] == "not_set"
        assert stats["is_closed"] == False
        
        bridge.cleanup(force=True, timeout=0.1)
    
    def test_repr(self):
        """Тест строкового представления"""
        bridge = SafeAsyncBridge()
        repr_str = repr(bridge)
        
        assert "SafeAsyncBridge" in repr_str
        assert "closed=False" in repr_str
        
        bridge.cleanup(force=True, timeout=0.1)
    
    def test_cleanup(self):
        """Тест очистки ресурсов"""
        bridge = SafeAsyncBridge()
        assert not bridge._closed
        
        # cleanup - это обычная sync функция, не async
        bridge.cleanup(force=True, timeout=0.1)
        assert bridge._closed
        
        # Повторная очистка не должна падать
        bridge.cleanup()


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
    result = bridge.call_async(simple_coro())
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
        bridge.call_async(failing_coro())
    
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
        result = bridge.call_async(counter_coro(i))
        results.append(result)
    
    assert results == [0, 2, 4, 6, 8]
    
    # Проверяем что bridge работает
    stats = bridge.get_stats()
    assert stats["loop_status"] == "running"
    
    await bridge.cleanup()


def test_without_loop():
    """Тест вызова без установленного loop"""
    bridge = SafeAsyncBridge()
    
    async def simple_coro():
        return "test"
    
    # Без loop должна быть ошибка
    with pytest.raises(RuntimeError, match="Event loop not set"):
        bridge.call_async(simple_coro())
    
    bridge.cleanup(force=True, timeout=0.1)


def test_closed_bridge():
    """Тест вызова на закрытом мосте"""
    bridge = SafeAsyncBridge()
    bridge.cleanup()
    
    async def simple_coro():
        return "test"
    
    # После cleanup вызовы должны игнорироваться
    with pytest.raises(RuntimeError, match="Bridge is closed"):
        bridge.call_async(simple_coro())


@pytest.mark.asyncio
async def test_timeout_handling():
    """Тест обработки timeout"""
    
    async def slow_coro():
        await asyncio.sleep(10)  # Долгий вызов
        return "done"
    
    bridge = SafeAsyncBridge()
    loop = asyncio.get_running_loop()
    bridge.set_loop(loop)
    
    # Вызываем с wait=False чтобы не зависнуть
    future = bridge.call_async(slow_coro(), wait=False)
    assert future is not None
    
    # Сразу очищаем
    bridge.cleanup(force=True, timeout=0.1)
    
    # После force cleanup future должен быть отменён
    assert future.cancelled() or future.done()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
