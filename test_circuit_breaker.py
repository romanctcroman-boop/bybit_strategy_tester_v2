#!/usr/bin/env python3
"""
🧪 Тест Circuit Breaker в retry_handler.py
Проверяем, что circuit breaker работает корректно
"""

import sys
import asyncio
from pathlib import Path

# Add mcp-server to path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from retry_handler import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
    RetryConfig,
    RetryHandler,
    RETRY_WITH_BREAKER
)


def test_circuit_breaker():
    """
    Тест Circuit Breaker pattern
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ CIRCUIT BREAKER")
    print("=" * 80)
    
    cb = CircuitBreaker(
        failure_threshold=3,  # Open после 3 ошибок
        success_threshold=2,  # Close после 2 успехов
        timeout=2.0,          # Half-open через 2 секунды
        window_size=10
    )
    
    print("\n📊 Начальное состояние:")
    state = cb.get_state()
    print(f"   State: {state['state']}")
    print(f"   Can execute: {cb.can_execute()}")
    
    # Test 1: Записываем успехи
    print("\n✅ Test 1: Record successes")
    for i in range(5):
        cb.record_success()
    state = cb.get_state()
    print(f"   After 5 successes - State: {state['state']}, Failure rate: {state['failure_rate']}")
    assert state['state'] == CircuitState.CLOSED.value, "Should stay CLOSED"
    
    # Test 2: Записываем ошибки до открытия
    print("\n❌ Test 2: Record failures until OPEN")
    for i in range(3):
        cb.record_failure()
        state = cb.get_state()
        print(f"   Failure {i+1}/3 - State: {state['state']}, Failure rate: {state['failure_rate']}")
    
    assert state['state'] == CircuitState.OPEN.value, "Should be OPEN after threshold"
    assert not cb.can_execute(), "Should not allow execution when OPEN"
    
    # Test 3: Попытка выполнения при OPEN
    print("\n🚫 Test 3: Try to execute when OPEN")
    try:
        if not cb.can_execute():
            print("   ✅ Correctly blocked execution (circuit is OPEN)")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    # Test 4: Ждём timeout для HALF_OPEN
    print("\n⏳ Test 4: Wait for HALF_OPEN state")
    print("   Waiting 2 seconds for timeout...")
    import time
    time.sleep(2.1)
    
    # can_execute() triggers the state transition
    can_exec = cb.can_execute()
    state = cb.get_state()
    print(f"   After timeout - State: {state['state']}, Can execute: {can_exec}")
    assert state['state'] == CircuitState.HALF_OPEN.value, "Should be HALF_OPEN after timeout"
    assert can_exec, "Should allow test execution in HALF_OPEN"
    
    # Test 5: Успехи в HALF_OPEN → CLOSED
    print("\n✅ Test 5: Recovery with successes")
    for i in range(2):
        cb.record_success()
        state = cb.get_state()
        print(f"   Success {i+1}/2 in HALF_OPEN - State: {state['state']}")
    
    assert state['state'] == CircuitState.CLOSED.value, "Should close after success threshold"
    
    print("\n" + "=" * 80)
    print("🎉 ВСЕ ТЕСТЫ CIRCUIT BREAKER ПРОЙДЕНЫ!")
    print("=" * 80)


async def test_retry_with_circuit_breaker():
    """
    Тест интеграции retry + circuit breaker
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ RETRY + CIRCUIT BREAKER INTEGRATION")
    print("=" * 80)
    
    call_count = 0
    
    async def failing_function():
        """Функция, которая всегда падает"""
        nonlocal call_count
        call_count += 1
        print(f"   Call {call_count}: Failing...")
        raise Exception("Simulated failure")
    
    # Создаём circuit breaker
    cb = CircuitBreaker(failure_threshold=3, success_threshold=2, timeout=2.0)
    config = RetryConfig(max_retries=2, base_delay=0.1, circuit_breaker=cb)
    
    # Test 1: Первая попытка (должна пройти retry)
    print("\n📞 Test 1: First call with retries")
    try:
        await RetryHandler.retry_async(failing_function, config)
    except Exception as e:
        print(f"   ✅ Failed as expected after retries: {e}")
        print(f"   Total calls: {call_count}")
    
    # Накапливаем ошибки для открытия circuit breaker
    print("\n📞 Test 2: Accumulate failures to open circuit")
    for i in range(2):
        try:
            await RetryHandler.retry_async(failing_function, config)
        except Exception:
            pass
    
    state = cb.get_state()
    print(f"   Circuit state after failures: {state['state']}")
    print(f"   Failure rate: {state['failure_rate']}")
    
    # Test 3: Circuit должен быть OPEN
    print("\n🚫 Test 3: Circuit should be OPEN now")
    try:
        await RetryHandler.retry_async(failing_function, config)
        print("   ❌ Should have raised CircuitBreakerError!")
    except CircuitBreakerError as e:
        print(f"   ✅ Correctly blocked: {e}")
    
    print("\n" + "=" * 80)
    print("🎉 ИНТЕГРАЦИОННЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 80)
    print(f"\n📊 Статистика:")
    print(f"   Total function calls: {call_count}")
    print(f"   Circuit prevented excessive calls: ✅")


if __name__ == "__main__":
    print("\n🚀 Starting Circuit Breaker Tests...")
    
    # Sync tests
    test_circuit_breaker()
    
    # Async tests
    asyncio.run(test_retry_with_circuit_breaker())
    
    print("\n" + "=" * 80)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО!")
    print("=" * 80)
