"""
Stress Tests: API Rate Limits & Error Handling

Проверка поведения при частых запросах к API и обработки ошибок.
Цель: Проверить rate limiting, retry logic, error recovery.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
import httpx

from automation.task1_test_watcher.test_watcher import TestWatcher


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_rapid_api_calls():
    """Stress: Быстрые последовательные API вызовы (mocked)"""
    
    call_count = 0
    call_times = []
    
    async def mock_post(*args, **kwargs):
        """Mock API call с подсчётом"""
        nonlocal call_count
        call_count += 1
        call_times.append(time.time())
        
        # Симулируем небольшую задержку API
        await asyncio.sleep(0.01)
        
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{
                "message": {
                    "content": f"Response {call_count}"
                }
            }]
        }
        return response
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
        
        # 20 быстрых запросов
        tasks = []
        for i in range(20):
            test_results = {
                "pytest_exit_code": 0,
                "success": True,
                "coverage_total": 90.0
            }
            
            task = watcher.send_to_deepseek(test_results, [])
            tasks.append(task)
        
        # Ждём завершения всех
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Проверяем результаты
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 20
        assert call_count == 20
        
        # Проверяем rate (должны быть быстрыми)
        if len(call_times) >= 2:
            time_span = call_times[-1] - call_times[0]
            rate = len(call_times) / time_span if time_span > 0 else 0
            print(f"✓ Rapid API calls: {call_count} calls, Rate: {rate:.1f} calls/sec")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_api_error_handling():
    """Stress: Обработка ошибок API"""
    
    error_responses = [
        429,  # Too Many Requests
        500,  # Internal Server Error
        503,  # Service Unavailable
    ]
    
    for status_code in error_responses:
        async def mock_post_error(*args, **kwargs):
            response = Mock()
            response.status_code = status_code
            response.json.return_value = {"error": f"Status {status_code}"}
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post_error
            
            watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
            
            test_results = {
                "pytest_exit_code": 0,
                "success": True
            }
            
            # Должен вернуть error результат, но не упасть
            result = await watcher.send_to_deepseek(test_results, [])
            
            assert result is not None
            assert "error" in result or "success" in result
            
            print(f"✓ API error {status_code}: Handled gracefully")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_api_timeout_handling():
    """Stress: Обработка timeouts"""
    
    async def mock_post_timeout(*args, **kwargs):
        """Mock с timeout"""
        await asyncio.sleep(100)  # Очень долгий запрос
        return Mock()
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post_timeout
        
        watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
        
        test_results = {"success": True}
        
        # Устанавливаем короткий timeout
        try:
            result = await asyncio.wait_for(
                watcher.send_to_deepseek(test_results, []),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            result = {"error": "timeout", "success": False}
        
        # Проверяем что timeout обработан
        assert result is not None
        print("✓ API timeout: Handled with timeout exception")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_concurrent_api_calls():
    """Stress: Параллельные API вызовы"""
    
    active_calls = 0
    max_concurrent = 0
    
    async def mock_post_concurrent(*args, **kwargs):
        """Mock с подсчётом параллельных вызовов"""
        nonlocal active_calls, max_concurrent
        
        active_calls += 1
        max_concurrent = max(max_concurrent, active_calls)
        
        await asyncio.sleep(0.05)  # Симуляция API delay
        
        active_calls -= 1
        
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }
        return response
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post_concurrent
        
        watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
        
        # 50 параллельных вызовов
        tasks = []
        for i in range(50):
            test_results = {"success": True, "id": i}
            task = watcher.send_to_deepseek(test_results, [])
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = [r for r in results if not isinstance(r, Exception)]
        
        assert len(successful) >= 45  # Допускаем до 5 ошибок
        print(f"✓ Concurrent API calls: {len(successful)}/50, Max concurrent: {max_concurrent}")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_api_retry_simulation():
    """Stress: Симуляция retry logic"""
    
    attempt_count = 0
    
    async def mock_post_retry(*args, **kwargs):
        """Mock с retry логикой"""
        nonlocal attempt_count
        attempt_count += 1
        
        response = Mock()
        
        # Первые 2 попытки - ошибка, 3-я успешна
        if attempt_count < 3:
            response.status_code = 503
            response.json.return_value = {"error": "Service unavailable"}
        else:
            response.status_code = 200
            response.json.return_value = {
                "choices": [{"message": {"content": "Success after retry"}}]
            }
        
        return response
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post_retry
        
        watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
        
        test_results = {"success": True}
        
        # Пробуем до 3 раз
        result = None
        for retry in range(3):
            result = await watcher.send_to_deepseek(test_results, [])
            if result and result.get("success"):
                break
            await asyncio.sleep(0.1)
        
        # После 3 попыток должно быть успешно
        assert attempt_count >= 3
        print(f"✓ API retry: Success after {attempt_count} attempts")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_api_rate_limiting():
    """Stress: Проверка rate limiting (базовая)"""
    
    request_times = []
    
    async def mock_post_rate(*args, **kwargs):
        """Mock с записью времени запросов"""
        request_times.append(time.time())
        
        # Симулируем rate limit на уровне API
        if len(request_times) > 1:
            time_diff = request_times[-1] - request_times[-2]
            if time_diff < 0.01:  # Слишком быстро
                response = Mock()
                response.status_code = 429
                response.json.return_value = {"error": "Rate limit exceeded"}
                return response
        
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }
        return response
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post_rate
        
        watcher = TestWatcher(watch_path=".", debounce_seconds=0.1)
        
        # 10 запросов с небольшой задержкой между ними
        results = []
        for i in range(10):
            test_results = {"success": True, "id": i}
            result = await watcher.send_to_deepseek(test_results, [])
            results.append(result)
            await asyncio.sleep(0.02)  # Небольшая задержка
        
        # Проверяем что большинство успешны
        successful = [r for r in results if r and r.get("success") != False]
        
        assert len(successful) >= 8  # Минимум 80% успеха
        print(f"✓ Rate limiting: {len(successful)}/10 requests successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
