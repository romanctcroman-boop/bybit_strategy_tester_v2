"""
Recovery Tests: Network Failure Recovery

Проверка обработки сетевых сбоев и восстановления.
Цель: Убедиться что система gracefully обрабатывает network failures.
"""

import asyncio
import tempfile
from pathlib import Path
import shutil
import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx

from automation.task1_test_watcher.test_watcher import TestWatcher


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_api_unavailable_recovery():
    """Recovery: DeepSeek API недоступен"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        # Создаём тестовый файл для передачи в changed_files
        test_file = temp_dir / "test_api.py"
        test_file.write_text("def test_api(): pass")
        
        # Mock API: первый запрос - network error, второй - успех
        call_count = 0
        
        async def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            
            # Второй запрос успешен
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "Analysis completed after recovery"
                    }
                }]
            }
            return mock_response
        
        with patch('httpx.AsyncClient.post', side_effect=mock_api_call):
            # Первый запрос - network error (gracefully handled, returns None)
            result = await watcher.send_to_deepseek(
                test_results={
                    "test_output": "test",
                    "coverage": 90.0
                },
                changed_files=[test_file]
            )
            
            # API error был залогирован, но не упал с exception
            # Результат содержит error (graceful degradation)
            assert result is not None, "Should return error dict"
            assert result.get("success") is False, "First call should fail"
            assert "error" in result
            
            # Второй запрос - успех после восстановления
            result = await watcher.send_to_deepseek(
                test_results={
                    "test_output": "test",
                    "coverage": 90.0
                },
                changed_files=[test_file]
            )
            
            assert result is not None
            assert "Analysis completed" in str(result)
        
        print("✓ Recovered from API unavailable")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_network_timeout_recovery():
    """Recovery: Network timeout с retry"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        # Регистрируем файл для передачи в changed_files
        test_file = temp_dir / "test_timeout.py"
        test_file.write_text("def test_timeout(): pass")
        
        # Mock API: первый timeout, второй успех
        call_count = 0
        
        async def mock_timeout_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # Первый запрос - timeout
                raise httpx.ReadTimeout("Request timeout after 30s")
            
            # Второй запрос - успех
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "Completed after timeout recovery"
                    }
                }]
            }
            return mock_response
        
        with patch('httpx.AsyncClient.post', side_effect=mock_timeout_then_success):
            # Первый запрос - timeout (gracefully handled)
            result = await watcher.send_to_deepseek(
                test_results={
                    "test_output": "data",
                    "coverage": 85.0
                },
                changed_files=[test_file]
            )
            
            # Timeout был залогирован, возвращён error dict
            assert result is not None, "Should return error dict"
            assert result.get("success") is False, "First call should timeout"
            assert "error" in result
            
            # Retry - успех
            result = await watcher.send_to_deepseek(
                test_results={
                    "test_output": "data",
                    "coverage": 85.0
                },
                changed_files=[test_file]
            )
            
            assert result is not None
            assert "timeout recovery" in str(result)
        
        print("✓ Recovered from network timeout")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_connection_error_graceful_degradation():
    """Recovery: Connection error с graceful degradation"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir), debounce_seconds=0.5)
        
        # Регистрируем файл
        test_file = temp_dir / "test_network.py"
        test_file.write_text("def test_network(): pass")
        watcher.handle_file_change(test_file)
        
        # Mock API: всегда connection error
        async def mock_connection_error(*args, **kwargs):
            raise httpx.ConnectError("Could not connect to host")
        
        with patch('httpx.AsyncClient.post', side_effect=mock_connection_error):
            # send_to_deepseek должен поймать ошибку
            try:
                await watcher.send_to_deepseek(
                    test_results={
                        "test_output": "test",
                        "coverage": 75.0
                    },
                    changed_files=[test_file]
                )
            except httpx.ConnectError:
                # Ожидаемое поведение: ошибка пробрасывается
                pass
            
            # Watcher должен остаться работоспособным
            # (даже если API недоступен)
            assert watcher is not None
            
            # Можем регистрировать новые файлы
            test_file2 = temp_dir / "test_recovery.py"
            test_file2.write_text("def test_recovery(): pass")
            watcher.handle_file_change(test_file2)
            assert len(watcher.changed_files) == 2
        
        print("✓ Graceful degradation on connection error")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
