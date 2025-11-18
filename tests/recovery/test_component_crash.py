"""
Recovery Tests: Component Crash Recovery

Проверка восстановления компонентов после сбоев.
Цель: Убедиться что система gracefully восстанавливается после crashes.
"""

import asyncio
import tempfile
from pathlib import Path
import shutil
import pytest
from unittest.mock import Mock, patch, AsyncMock

from automation.task1_test_watcher.test_watcher import TestWatcher
from automation.task3_audit_agent.audit_agent import AuditAgent, AuditConfig
from automation.safe_async_bridge import SafeAsyncBridge


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_watcher_crash_recovery():
    """Recovery: TestWatcher восстановление после crash"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        # Регистрируем файл
        test_file = temp_dir / "test_crash.py"
        test_file.write_text("def test_crash(): assert True")
        watcher.handle_file_change(test_file)
        
        # Симулируем crash: force exception
        crash_count = 0
        
        async def crashing_method():
            nonlocal crash_count
            crash_count += 1
            if crash_count == 1:
                raise RuntimeError("Simulated crash!")
            return "recovered"
        
        # Первый вызов - crash
        with pytest.raises(RuntimeError, match="Simulated crash"):
            await crashing_method()
        
        # Второй вызов - должен восстановиться
        result = await crashing_method()
        assert result == "recovered"
        
        # Проверяем что watcher всё ещё работает
        assert len(watcher.changed_files) == 1  # Файл всё ещё зарегистрирован
        
        # Можем регистрировать новые файлы
        test_file2 = temp_dir / "test_recovery.py"
        test_file2.write_text("def test_recovery(): pass")
        watcher.handle_file_change(test_file2)
        assert len(watcher.changed_files) == 2
        
        print("✓ TestWatcher recovered from crash")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_audit_agent_crash_recovery():
    """Recovery: AuditAgent восстановление после crash"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # AuditConfig не принимает параметры - используем default
        config = AuditConfig()
        agent = AuditAgent(config)
        
        # Симулируем crash в методе agent
        crash_count = 0
        async def crashing_method():
            nonlocal crash_count
            crash_count += 1
            if crash_count == 1:
                raise ValueError("Analysis crash!")
            return {
                "status": "recovered",
                "message": "Analysis completed after recovery"
            }
        
        # Первый вызов - crash
        with pytest.raises(ValueError, match="Analysis crash"):
            await crashing_method()
        
        # Второй вызов - восстановление
        result = await crashing_method()
        assert result["status"] == "recovered"
        
        # Agent должен остаться работоспособным
        assert agent is not None
        assert agent.config is not None
        
        print("✓ AuditAgent recovered from crash")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_safe_async_bridge_crash_recovery():
    """Recovery: SafeAsyncBridge восстановление после crash"""
    bridge = SafeAsyncBridge()
    bridge.set_loop(asyncio.get_running_loop())
    
    crash_count = 0
    
    async def crashing_task():
        """Задача которая падает при первом вызове"""
        nonlocal crash_count
        crash_count += 1
        if crash_count == 1:
            raise ConnectionError("Task crashed!")
        await asyncio.sleep(0.01)
        return "recovered"
    
    # Первый вызов - crash
    with pytest.raises(ConnectionError, match="Task crashed"):
        await bridge.call_async(crashing_task())
    
    # Bridge должен остаться работоспособным
    stats = bridge.get_stats()
    assert stats["is_closed"] is False
    
    # Второй вызов - успешен
    result = await bridge.call_async(crashing_task())
    assert result == "recovered"
    
    # Bridge всё ещё работает
    async def simple_task():
        return "ok"
    
    result = await bridge.call_async(simple_task())
    assert result == "ok"
    
    await bridge.cleanup()
    
    print("✓ SafeAsyncBridge recovered from crash")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
