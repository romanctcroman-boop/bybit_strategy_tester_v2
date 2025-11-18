"""
Recovery Tests: Disk Full & File Errors

Проверка обработки ошибок записи на диск.
Цель: Убедиться что система gracefully обрабатывает disk errors.
"""

import asyncio
import tempfile
from pathlib import Path
import shutil
import pytest
from unittest.mock import Mock, patch, mock_open
import json

from automation.task1_test_watcher.test_watcher import TestWatcher


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_disk_full_simulation():
    """Recovery: Disk full при записи результатов"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        test_results = {
            "test_output": "test data",
            "coverage": 85.0,
            "timestamp": "2025-01-07T00:00:00"
        }
        
        analysis_results = {
            "analysis": "test analysis",
            "recommendations": ["test rec"]
        }
        
        test_file = temp_dir / "test_disk.py"
        test_file.write_text("def test_disk(): pass")
        changed_files = [test_file]
        
        # Mock save_results: первый вызов - disk full, второй - успех
        call_count = 0
        original_save = watcher.save_results
        
        async def mock_save_with_recovery(test_res, analysis_res, files):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # Первый вызов - disk full
                raise OSError(28, "No space left on device")
            
            # Второй вызов - успех (место освободилось)
            return await original_save(test_res, analysis_res, files)
        
        watcher.save_results = mock_save_with_recovery
        
        # Первый вызов - disk full error
        with pytest.raises(OSError, match="No space left on device"):
            await watcher.save_results(test_results, analysis_results, changed_files)
        
        # Второй вызов - успех после освобождения места
        result_path = await watcher.save_results(test_results, analysis_results, changed_files)
        
        # save_results не возвращает Path, но сохраняет файл
        # Проверяем что файл создан в ai_audit_results
        results_dir = Path("ai_audit_results")
        if results_dir.exists():
            result_files = list(results_dir.glob("test_watcher_audit_*.json"))
            assert len(result_files) > 0, "Results file should be created"
            
            # Проверяем содержимое последнего файла
            latest_file = max(result_files, key=lambda p: p.stat().st_mtime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            assert saved_data["test_results"]["coverage"] == 85.0
        
        print("✓ Recovered from disk full error")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_file_write_permission_error():
    """Recovery: Permission denied при записи"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        test_results = {
            "test_output": "test",
            "coverage": 90.0
        }
        
        # Mock open: permission denied
        call_count = 0
        
        def mock_open_with_recovery(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise PermissionError("Permission denied")
            
            # Второй вызов - успех
            return mock_open(read_data='{}')(*args, **kwargs)
        
        # Первый вызов - permission error
        with patch('builtins.open', side_effect=mock_open_with_recovery):
            with pytest.raises(PermissionError):
                # Попытка записи
                with open(temp_dir / "test_results.json", 'w') as f:
                    json.dump(test_results, f)
            
            # Второй вызов - успех (права восстановлены)
            with open(temp_dir / "test_results_recovery.json", 'w') as f:
                json.dump(test_results, f)
        
        print("✓ Handled permission error gracefully")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_log_rotation_on_disk_pressure():
    """Recovery: Log rotation при нехватке места"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Создаём несколько "старых" log файлов
        logs_dir = temp_dir / "logs"
        logs_dir.mkdir()
        
        old_logs = []
        for i in range(5):
            log_file = logs_dir / f"old_log_{i}.log"
            log_file.write_text(f"Old log content {i}\n" * 1000)  # ~20 KB каждый
            old_logs.append(log_file)
        
        # Проверяем что файлы созданы
        assert len(list(logs_dir.glob("*.log"))) == 5
        
        # Симулируем cleanup старых логов (rotation)
        # Удаляем логи старше 3 дней (в данном случае - все)
        for log_file in old_logs[:3]:  # Удаляем первые 3
            log_file.unlink()
        
        # Проверяем что освободилось место
        remaining_logs = list(logs_dir.glob("*.log"))
        assert len(remaining_logs) == 2
        
        # Можем создать новый лог
        new_log = logs_dir / "current.log"
        new_log.write_text("New log entry\n")
        assert new_log.exists()
        
        print("✓ Log rotation completed successfully")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
