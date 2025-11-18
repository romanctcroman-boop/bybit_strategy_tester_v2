"""
Тесты для SyncAsyncWrapper - вызов async из sync кода
"""
import asyncio
import time
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.sync_async_wrapper import SyncAsyncWrapper, run_async


def test_sync_async_wrapper_basic():
    """Тест базового использования wrapper"""
    
    async def simple_async():
        await asyncio.sleep(0.01)
        return "success"
    
    wrapper = SyncAsyncWrapper()
    result = wrapper.call(simple_async())
    assert result == "success"
    
    wrapper.close()


def test_sync_async_wrapper_context_manager():
    """Тест через context manager"""
    
    async def get_value():
        await asyncio.sleep(0.01)
        return 42
    
    with SyncAsyncWrapper() as wrapper:
        result = wrapper.call(get_value())
        assert result == 42


def test_sync_async_wrapper_multiple_calls():
    """Тест множественных вызовов"""
    
    async def multiply(x, y):
        await asyncio.sleep(0.01)
        return x * y
    
    with SyncAsyncWrapper() as wrapper:
        r1 = wrapper.call(multiply(2, 3))
        r2 = wrapper.call(multiply(4, 5))
        r3 = wrapper.call(multiply(6, 7))
        
        assert r1 == 6
        assert r2 == 20
        assert r3 == 42


def test_sync_async_wrapper_exception():
    """Тест обработки исключений"""
    
    async def failing():
        await asyncio.sleep(0.01)
        raise ValueError("Test error")
    
    with SyncAsyncWrapper() as wrapper:
        with pytest.raises(ValueError, match="Test error"):
            wrapper.call(failing())


def test_sync_async_wrapper_timeout():
    """Тест timeout"""
    
    async def slow_operation():
        await asyncio.sleep(10)  # Очень долго
        return "done"
    
    with SyncAsyncWrapper() as wrapper:
        with pytest.raises(TimeoutError):
            wrapper.call(slow_operation(), timeout=0.1)


def test_run_async_convenience():
    """Тест convenience функции run_async"""
    
    async def quick_calc():
        await asyncio.sleep(0.01)
        return 10 + 20
    
    result = run_async(quick_calc())
    assert result == 30


def test_run_async_with_exception():
    """Тест run_async с исключением"""
    
    async def failing():
        raise RuntimeError("Quick fail")
    
    with pytest.raises(RuntimeError, match="Quick fail"):
        run_async(failing())


def test_wrapper_performance():
    """Тест производительности - должен быть быстрым"""
    
    async def fast_op():
        return "fast"
    
    start = time.time()
    
    with SyncAsyncWrapper() as wrapper:
        for _ in range(10):
            result = wrapper.call(fast_op())
            assert result == "fast"
    
    elapsed = time.time() - start
    assert elapsed < 1.0  # Должно быть очень быстро


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
