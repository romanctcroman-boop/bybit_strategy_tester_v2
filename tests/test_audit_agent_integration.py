"""
Integration тесты для SafeAsyncBridge в audit_agent
"""
import asyncio
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "automation"))
sys.path.insert(0, str(Path(__file__).parent.parent / "automation" / "task3_audit_agent"))

from automation.safe_async_bridge import SafeAsyncBridge
from automation.task3_audit_agent.config import AuditConfig


@pytest.mark.asyncio
async def test_safe_async_bridge_initialization():
    """Тест инициализации SafeAsyncBridge в AuditAgent"""
    from automation.task3_audit_agent.audit_agent import AuditAgent
    
    # Создаём config (без параметров)
    config = AuditConfig()
    
    # Создаём агент
    agent = AuditAgent(config)
    
    # Проверяем что bridge создан
    assert agent.async_bridge is not None
    assert agent.async_bridge.__class__.__name__ == "SafeAsyncBridge"
    
    # Проверяем начальное состояние
    stats = agent.async_bridge.get_stats()
    assert stats["pending_count"] == 0
    assert stats["is_closed"] == False


@pytest.mark.asyncio
async def test_safe_async_bridge_set_loop():
    """Тест установки event loop в SafeAsyncBridge"""
    from automation.task3_audit_agent.audit_agent import AuditAgent
    
    config = AuditConfig()
    agent = AuditAgent(config)
    
    # Устанавливаем loop вручную (как в start())
    loop = asyncio.get_running_loop()
    agent.async_bridge.set_loop(loop)
    
    # Проверяем статус
    stats = agent.async_bridge.get_stats()
    assert stats["loop_status"] == "running"


@pytest.mark.asyncio
async def test_safe_async_bridge_call_async():
    """Тест вызова async функции через SafeAsyncBridge"""
    from automation.task3_audit_agent.audit_agent import AuditAgent
    
    config = AuditConfig()
    agent = AuditAgent(config)
    agent.loop = asyncio.get_running_loop()
    agent.async_bridge.set_loop(agent.loop)
    
    # Тестовая async функция
    async def test_operation():
        await asyncio.sleep(0.01)
        return "success"
    
    # Вызываем через bridge
    result = await agent.async_bridge.call_async(test_operation())
    
    assert result == "success"
    
    # Cleanup
    await agent.async_bridge.cleanup()


@pytest.mark.asyncio
async def test_safe_async_bridge_cleanup():
    """Тест graceful cleanup SafeAsyncBridge"""
    from automation.task3_audit_agent.audit_agent import AuditAgent
    
    config = AuditConfig()
    agent = AuditAgent(config)
    agent.loop = asyncio.get_running_loop()
    agent.async_bridge.set_loop(agent.loop)
    
    # Запускаем операцию
    async def slow_operation():
        await asyncio.sleep(0.1)
        return "done"
    
    task = asyncio.create_task(
        agent.async_bridge.call_async(slow_operation())
    )
    
    # Даём операции начаться
    await asyncio.sleep(0.01)
    
    # Graceful cleanup должен дождаться
    await agent.async_bridge.cleanup(force=False)
    
    # Операция должна завершиться
    result = await task
    assert result == "done"
    
    # Bridge должен быть закрыт
    assert agent.async_bridge._closed


@pytest.mark.asyncio
async def test_marker_file_handler_integration():
    """Тест интеграции SafeAsyncBridge с MarkerFileHandler"""
    from automation.task3_audit_agent.audit_agent import AuditAgent, MarkerFileHandler
    
    config = AuditConfig()
    agent = AuditAgent(config)
    agent.loop = asyncio.get_running_loop()
    agent.async_bridge.set_loop(agent.loop)
    
    # Mock handle_marker_creation
    async def mock_handle_marker(file_path):
        await asyncio.sleep(0.01)
        return f"Handled: {file_path}"
    
    agent.handle_marker_creation = mock_handle_marker
    
    # Создаём handler
    handler = MarkerFileHandler(agent)
    
    # Симулируем событие (manual call, not через watchdog)
    test_path = Path("test_marker.md")
    
    # Вызываем через bridge
    result = await agent.async_bridge.call_async(
        agent.handle_marker_creation(test_path)
    )
    
    assert result == f"Handled: {test_path}"
    
    # Cleanup
    await agent.async_bridge.cleanup()


@pytest.mark.asyncio
async def test_multiple_async_calls_through_bridge():
    """Тест множественных async вызовов через SafeAsyncBridge"""
    from automation.task3_audit_agent.audit_agent import AuditAgent
    
    config = AuditConfig()
    agent = AuditAgent(config)
    agent.loop = asyncio.get_running_loop()
    agent.async_bridge.set_loop(agent.loop)
    
    # Множественные операции
    async def operation(n):
        await asyncio.sleep(0.01)
        return n * 2
    
    results = []
    for i in range(5):
        result = await agent.async_bridge.call_async(operation(i))
        results.append(result)
    
    assert results == [0, 2, 4, 6, 8]
    
    # Проверяем статистику
    stats = agent.async_bridge.get_stats()
    assert stats["pending_count"] == 0  # Все операции завершены
    
    # Cleanup
    await agent.async_bridge.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
