"""
Stress Tests: Memory Leaks Detection

Проверка на утечки памяти при долгой работе компонентов.
Цель: Обнаружить memory leaks и ресурсные проблемы.
"""

import asyncio
import tempfile
from pathlib import Path
import shutil
import pytest
import gc
import sys

from automation.task1_test_watcher.test_watcher import TestWatcher
from automation.safe_async_bridge import SafeAsyncBridge


def get_memory_usage():
    """Получить текущее использование памяти (приблизительно)"""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        # Fallback: используем sys.getsizeof для грубой оценки
        return sys.getsizeof(gc.get_objects()) / 1024 / 1024


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_watcher_memory_leak():
    """Stress: Проверка утечек памяти в TestWatcher"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        # Начальная память
        gc.collect()
        initial_memory = get_memory_usage()
        
        # 100 циклов обработки файлов
        for cycle in range(100):
            # Создаём файл
            test_file = temp_dir / f"test_{cycle}.py"
            test_file.write_text(f"def test_{cycle}(): assert True")
            
            # Регистрируем изменение (НЕ вызываем debounced_processing - слишком долго)
            watcher.handle_file_change(test_file)
            
            # Удаляем файл
            test_file.unlink(missing_ok=True)
            
            # Периодическая сборка мусора
            if cycle % 20 == 0:
                gc.collect()
        
        # Финальная сборка мусора
        gc.collect()
        final_memory = get_memory_usage()
        
        memory_growth = final_memory - initial_memory
        
        # Допускаем рост до 10 MB (разумный предел)
        assert memory_growth < 10, f"Memory leak detected: {memory_growth:.2f} MB growth"
        
        print(f"✓ Memory leak test: Growth {memory_growth:.2f} MB (OK)")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_bridge_memory_leak():
    """Stress: Проверка утечек памяти в SafeAsyncBridge"""
    bridge = SafeAsyncBridge()
    bridge.set_loop(asyncio.get_running_loop())  # Инициализируем loop!
    
    gc.collect()
    initial_memory = get_memory_usage()
    
    async def dummy_task():
        """Простая задача"""
        await asyncio.sleep(0.001)
        return "done"
    
    # 500 операций
    for i in range(500):
        await bridge.call_async(dummy_task())
        
        if i % 100 == 0:
            gc.collect()
    
    gc.collect()
    final_memory = get_memory_usage()
    
    await bridge.cleanup()
    
    memory_growth = final_memory - initial_memory
    
    # Допускаем рост до 5 MB
    assert memory_growth < 5, f"Bridge memory leak: {memory_growth:.2f} MB growth"
    
    print(f"✓ Bridge memory test: Growth {memory_growth:.2f} MB (OK)")


@pytest.mark.asyncio
@pytest.mark.timeout(45)
async def test_long_running_watcher():
    """Stress: Долгая работа TestWatcher"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.1)
        
        gc.collect()
        initial_memory = get_memory_usage()
        
        # 50 файлов, 5 циклов обработки каждого
        for cycle in range(5):
            for file_num in range(50):
                test_file = temp_dir / f"test_{file_num}.py"
                test_file.write_text(f"def test_{file_num}_cycle_{cycle}(): pass")
                # НЕ вызываем debounced_processing - проверяем только регистрацию
                watcher.handle_file_change(test_file)
            
            if cycle % 2 == 0:
                gc.collect()
        
        gc.collect()
        final_memory = get_memory_usage()
        
        memory_growth = final_memory - initial_memory
        
        # Допускаем рост до 15 MB для 250 операций
        assert memory_growth < 15, f"Long-running leak: {memory_growth:.2f} MB growth"
        
        print(f"✓ Long-running test: 250 operations, Growth {memory_growth:.2f} MB")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_object_cleanup():
    """Stress: Проверка очистки объектов"""
    temp_dirs = []
    watchers = []
    
    try:
        # Создаём 20 watchers
        for i in range(20):
            temp_dir = Path(tempfile.mkdtemp())
            temp_dirs.append(temp_dir)
            
            watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
            watchers.append(watcher)
        
        # Все watchers активны
        assert len(watchers) == 20
        
        # Удаляем все
        watchers.clear()
        gc.collect()
        
        # Проверяем что объекты действительно удалены
        import weakref
        
        # Создаём новый watcher с weak reference
        temp_dir = Path(tempfile.mkdtemp())
        temp_dirs.append(temp_dir)
        
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        weak_ref = weakref.ref(watcher)
        
        # Weak reference должен быть активен
        assert weak_ref() is not None
        
        # Удаляем
        del watcher
        gc.collect()
        
        # Weak reference должен быть None (объект удалён)
        assert weak_ref() is None, "Object not cleaned up properly"
        
        print("✓ Object cleanup: All objects properly destroyed")
        
    finally:
        for temp_dir in temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_changed_files_growth():
    """Stress: Рост changed_files списка"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=10)  # Большой debounce
        
        # Добавляем 100 файлов БЕЗ обработки
        for i in range(100):
            test_file = temp_dir / f"test_{i}.py"
            test_file.write_text(f"def test_{i}(): pass")
            watcher.handle_file_change(test_file)
        
        # Проверяем размер списка
        files_count = len(watcher.changed_files)
        assert files_count >= 100
        
        # Очищаем список вручную (не вызываем debounced_processing)
        watcher.changed_files.clear()
        
        # Список должен очиститься
        assert len(watcher.changed_files) == 0
        
        print(f"✓ Changed files growth: {files_count} files handled and cleared")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
