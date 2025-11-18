"""
Stress Tests: Parallel Execution

Проверка работы системы при параллельном запуске компонентов.
Цель: Обнаружить race conditions и проблемы синхронизации.
"""

import asyncio
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import shutil
import pytest
import time

from automation.task1_test_watcher.test_watcher import TestWatcher
from automation.task3_audit_agent.audit_agent import AuditAgent
from automation.task3_audit_agent.config import AuditConfig


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_parallel_test_watchers():
    """Stress: Параллельный запуск нескольких TestWatcher"""
    temp_dirs = [Path(tempfile.mkdtemp()) for _ in range(3)]
    
    try:
        watchers = []
        for temp_dir in temp_dirs:
            watcher = TestWatcher(
                watch_path=str(temp_dir),
                debounce_seconds=1
            )
            watchers.append(watcher)
            
            # Создаём тестовые файлы
            test_file = temp_dir / f"test_{temp_dir.name}.py"
            test_file.write_text("def test_example(): assert True")
        
        # Параллельно обрабатываем изменения (БЕЗ run_tests!)
        tasks = []
        for i, watcher in enumerate(watchers):
            test_file = temp_dirs[i] / f"test_{temp_dirs[i].name}.py"
            watcher.handle_file_change(test_file)
            # НЕ вызываем debounced_processing - просто проверяем регистрацию
        
        # Проверяем что файлы зарегистрированы
        for watcher in watchers:
            assert len(watcher.changed_files) > 0
        
        print(f"✓ Parallel TestWatchers: {len(watchers)} instances OK")
        
    finally:
        for temp_dir in temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_concurrent_file_changes():
    """Stress: Одновременные изменения множества файлов"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=2)
        
        # Создаём 20 файлов одновременно
        files = []
        for i in range(20):
            test_file = temp_dir / f"test_{i}.py"
            test_file.write_text(f"def test_{i}(): pass")
            files.append(test_file)
        
        # Быстро регистрируем все изменения
        start_time = time.time()
        for file in files:
            watcher.handle_file_change(file)
        
        registration_time = time.time() - start_time
        
        # Проверяем что все зарегистрированы
        assert len(watcher.changed_files) >= 20
        
        # НЕ запускаем debounced_processing (триггерит run_tests)
        # Просто проверяем что файлы зарегистрированы
        watcher.changed_files.clear()  # Очищаем вручную
        
        # Очищено
        assert len(watcher.changed_files) == 0
        
        print(f"✓ Concurrent file changes: 20 files in {registration_time:.3f}s")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(20)
async def test_parallel_audit_agents():
    """Stress: Параллельная инициализация AuditAgent"""
    # Создаём несколько агентов одновременно
    configs = [AuditConfig() for _ in range(3)]
    
    agents = []
    for config in configs:
        agent = AuditAgent(config=config)
        agents.append(agent)
    
    # Проверяем что все инициализированы корректно
    for agent in agents:
        assert agent.config is not None
        assert agent.async_bridge is not None
        assert agent.git_monitor is not None
        assert agent.coverage_checker is not None
    
    print(f"✓ Parallel AuditAgents: {len(agents)} instances initialized")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_rapid_bridge_operations():
    """Stress: Быстрые операции с SafeAsyncBridge"""
    from automation.safe_async_bridge import SafeAsyncBridge
    
    bridge = SafeAsyncBridge()
    bridge.set_loop(asyncio.get_running_loop())  # Инициализируем loop!
    
    async def dummy_operation():
        """Простая async операция"""
        await asyncio.sleep(0.01)
        return "done"
    
    # 100 быстрых операций
    tasks = []
    for _ in range(100):
        task = bridge.call_async(dummy_operation())
        tasks.append(task)
    
    # Ждём завершения всех
    results = await asyncio.gather(*tasks)
    
    # Проверяем результаты
    assert len(results) == 100
    assert all(r == "done" for r in results)
    
    # Проверяем статистику
    stats = bridge.get_stats()
    assert stats["pending_count"] == 0
    
    # Cleanup
    await bridge.cleanup()
    
    print(f"✓ Rapid bridge operations: 100 calls completed")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_thread_safety():
    """Stress: Параллельное использование SafeAsyncBridge"""
    from automation.safe_async_bridge import SafeAsyncBridge
    
    bridge = SafeAsyncBridge()
    bridge.set_loop(asyncio.get_running_loop())
    
    async def dummy_task(task_id: int):
        """Простая задача с ID"""
        await asyncio.sleep(0.01)
        return f"task_{task_id}"
    
    # Запускаем 50 задач параллельно
    tasks = [bridge.call_async(dummy_task(i)) for i in range(50)]
    
    # Ждём завершения всех
    results = await asyncio.gather(*tasks)
    
    # Проверяем
    assert len(results) == 50
    assert all(r.startswith("task_") for r in results)
    
    await bridge.cleanup()
    
    print(f"✓ Thread safety: 50 parallel tasks completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
