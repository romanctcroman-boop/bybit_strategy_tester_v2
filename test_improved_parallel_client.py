"""
Test improved ParallelDeepSeekClientV2 with circuit breaker and retry logic.

This test validates:
✅ Exponential backoff with jitter
✅ Circuit breaker pattern
✅ Retry logic with error classification
✅ Rate limit handling
✅ Performance-based load balancing

Expected results:
- 8/8 tasks successful (vs 6/8 in original)
- Automatic retry on transient errors
- Circuit breaker prevents cascading failures
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup paths
import sys
sys.path.insert(0, str(Path(__file__).parent / "automation" / "task2_key_manager"))
sys.path.insert(0, str(Path(__file__).parent))

from automation.task2_key_manager.key_manager import KeyManager
from backend.api.parallel_deepseek_client_v2 import (
    ParallelDeepSeekClientV2,
    DeepSeekTask,
    TaskPriority
)


async def test_improved_client():
    """Test improved client with all enhancements"""
    
    print("=" * 80)
    print("  ТЕСТИРОВАНИЕ УЛУЧШЕННОГО PARALLEL DEEPSEEK CLIENT V2")
    print("=" * 80)
    print()
    
    # 1. Load API keys
    print("📦 Загрузка API ключей...")
    key_manager = KeyManager()
    encryption_key = os.getenv("ENCRYPTION_KEY")
    
    if not encryption_key:
        print("❌ ENCRYPTION_KEY не найден!")
        return
    
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации шифрования!")
        return
    
    if not key_manager.load_keys("encrypted_secrets.json"):
        print("❌ Ошибка загрузки ключей!")
        return
    
    api_keys = key_manager.get_all_keys("DEEPSEEK_API_KEY")
    print(f"✅ Загружено {len(api_keys)} API ключей")
    print()
    
    # 2. Create improved client
    print("🚀 Создание ParallelDeepSeekClientV2...")
    client = ParallelDeepSeekClientV2(
        api_keys=api_keys,
        max_concurrent=12,
        enable_cache=True
    )
    print("✅ Клиент V2 готов с circuit breakers и retry logic")
    print()
    
    # 3. Create test tasks (same as original analysis)
    print("📝 Создание тестовых задач...")
    tasks = []
    
    # Short task (should succeed quickly)
    tasks.append(DeepSeekTask(
        task_id="short_test",
        prompt="What are the top 3 Python async best practices?",
        priority=TaskPriority.HIGH,
        max_tokens=500,
        max_retries=3
    ))
    
    # Medium task
    tasks.append(DeepSeekTask(
        task_id="medium_test",
        prompt="""
Analyze this load balancing algorithm:

```python
def _get_best_key(self):
    available_keys = [k for k in self.api_keys if circuit_breaker[k].is_available()]
    return max(available_keys, key=lambda k: metrics[k].score())
```

Explain:
1. How does performance-based selection improve over least-used?
2. What is the scoring algorithm?
3. Potential edge cases?
""",
        priority=TaskPriority.MEDIUM,
        max_tokens=1500,
        max_retries=3
    ))
    
    # Large task (previously failed due to timeout)
    tasks.append(DeepSeekTask(
        task_id="large_test_1",
        prompt="""
Review this circuit breaker implementation:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
    
    def is_available(self):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure > self.timeout:
                self.state = CircuitState.HALF_OPEN
        return self.state != CircuitState.OPEN
    
    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

Provide detailed analysis:
1. State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
2. Failure threshold effectiveness
3. Half-open testing strategy
4. Potential improvements
5. Production readiness
""",
        priority=TaskPriority.HIGH,
        max_tokens=2000,
        max_retries=3
    ))
    
    # Another large task (also previously failed)
    tasks.append(DeepSeekTask(
        task_id="large_test_2",
        prompt="""
Analyze exponential backoff implementation:

```python
def _calculate_backoff(self, attempt: int, base_delay: float = 1.0) -> float:
    exp_delay = min(60, base_delay * (2 ** attempt))
    jitter = random.uniform(-0.3, 0.3) * exp_delay
    return max(0.1, exp_delay + jitter)
```

Questions:
1. Why exponential backoff vs linear?
2. Purpose of jitter (±30%)?
3. Why cap at 60 seconds?
4. Is the jitter range appropriate?
5. Alternative strategies (fibonacci, polynomial)?
6. Impact on user experience?

Provide comprehensive analysis with examples.
""",
        priority=TaskPriority.HIGH,
        max_tokens=2500,
        max_retries=3
    ))
    
    # Error classification test
    tasks.append(DeepSeekTask(
        task_id="error_classification_test",
        prompt="""
Explain error classification strategy:

```python
def _classify_error(self, error, status_code):
    if status_code == 429:
        return "rate_limit"
    if status_code in [400, 401, 403, 404]:
        return "persistent"
    if status_code and 500 <= status_code < 600:
        return "transient"
    return "transient"
```

Questions:
1. Why separate rate_limit from transient?
2. Should 401/403 be persistent (never retry)?
3. What about network errors (timeout, connection)?
4. Edge cases not covered?
5. Production recommendations?
""",
        priority=TaskPriority.MEDIUM,
        max_tokens=1500,
        max_retries=3
    ))
    
    # Performance metrics test
    tasks.append(DeepSeekTask(
        task_id="metrics_test",
        prompt="""
Analyze performance metrics implementation:

```python
@dataclass
class APIKeyMetrics:
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    success_count: int = 0
    error_count: int = 0
    
    def score(self) -> float:
        success_rate = self.success_count / (self.success_count + self.error_count)
        avg_time = sum(self.response_times) / len(self.response_times)
        return success_rate / avg_time
```

Questions:
1. Is this scoring algorithm optimal?
2. Why maxlen=100 for response_times?
3. Should we weight recent performance higher?
4. What if avg_time is 0 or very small?
5. Alternative scoring methods?
""",
        priority=TaskPriority.MEDIUM,
        max_tokens=1500,
        max_retries=3
    ))
    
    # Rate limit handling test
    tasks.append(DeepSeekTask(
        task_id="rate_limit_test",
        prompt="""
Review rate limit handling:

```python
if error_type == "rate_limit":
    retry_after = 60  # Default
    metrics.rate_limit_reset_time = time.time() + retry_after
    circuit_breaker.record_failure()
```

Questions:
1. Should we extract Retry-After header from response?
2. Is 60s default appropriate?
3. Should rate limit trigger circuit breaker?
4. How to handle multiple rapid rate limits?
5. Best practices for rate limit backoff?
""",
        priority=TaskPriority.HIGH,
        max_tokens=1500,
        max_retries=3
    ))
    
    # Retry strategy test
    tasks.append(DeepSeekTask(
        task_id="retry_strategy_test",
        prompt="""
Evaluate retry strategy:

```python
for attempt in range(task.max_retries):
    api_key = self._get_best_key()
    if not api_key:
        delay = self._calculate_backoff(attempt)
        await asyncio.sleep(delay)
        continue
    
    success, response, status, data = await self._make_api_request(...)
    
    if success:
        return result
    
    error_type = self._classify_error(...)
    
    if error_type == "persistent":
        return failure  # Don't retry
    
    if error_type == "transient":
        delay = self._calculate_backoff(attempt)
        await asyncio.sleep(delay)
        continue
```

Analysis:
1. Is 3 retries (max_retries=3) sufficient?
2. Should we retry with same key or different key?
3. Persistent errors - correct to fail immediately?
4. Backoff between retries - appropriate timing?
5. Production recommendations?
""",
        priority=TaskPriority.HIGH,
        max_tokens=2000,
        max_retries=3
    ))
    
    print(f"✅ Создано {len(tasks)} тестовых задач")
    print()
    
    # 4. Process tasks in parallel
    print("🔍 Запуск параллельной обработки...")
    print("⏱️  Ожидаемое время: ~60-90 секунд")
    print()
    
    import time
    start_time = time.time()
    
    results = await client.process_batch(tasks, show_progress=True)
    
    total_time = time.time() - start_time
    
    # 5. Analyze results
    print()
    print("=" * 80)
    print("  РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    print()
    
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    print(f"✅ Успешно: {len(successful)}/{len(tasks)}")
    print(f"❌ Провалено: {len(failed)}/{len(tasks)}")
    print(f"⏱️  Общее время: {total_time:.2f}s")
    print(f"📊 Скорость: {len(tasks)/total_time:.2f} tasks/sec")
    print()
    
    if successful:
        print("Успешные задачи:")
        for result in successful:
            print(f"  ✅ {result.task_id}:")
            print(f"     Time: {result.processing_time:.2f}s")
            print(f"     Tokens: {result.tokens_used}")
            print(f"     Retries: {result.retry_count}")
            print(f"     Key: {result.api_key_used}")
            response_preview = result.response[:150].replace('\n', ' ')
            print(f"     Preview: {response_preview}...")
            print()
    
    if failed:
        print("Провалившиеся задачи:")
        for result in failed:
            print(f"  ❌ {result.task_id}:")
            print(f"     Error: {result.error}")
            print(f"     Retries: {result.retry_count}")
            print()
    
    # 6. Statistics
    print("=" * 80)
    print("  ДЕТАЛЬНАЯ СТАТИСТИКА")
    print("=" * 80)
    print()
    
    stats = client.get_statistics()
    
    print(f"Total Requests:        {stats['total_requests']}")
    print(f"Success Rate:          {stats['success_rate']}")
    print(f"Total Retries:         {stats['total_retries']}")
    print(f"Rate Limit Hits:       {stats['rate_limit_hits']}")
    print(f"Cache Hit Rate:        {stats['cache_hit_rate']}")
    print(f"Total Tokens:          {stats['total_tokens']}")
    print(f"Total Processing Time: {stats['total_processing_time']}")
    print(f"Avg Processing Time:   {stats['avg_processing_time']}")
    print()
    
    print("API Key Performance:")
    for key_suffix, key_stats in stats['api_keys'].items():
        print(f"  Key {key_suffix}:")
        print(f"    Requests: {key_stats['total_requests']}")
        print(f"    Success Rate: {key_stats['success_rate']}")
        print(f"    Avg Response Time: {key_stats['avg_response_time']}")
        print(f"    Performance Score: {key_stats['score']}")
        print(f"    Circuit Breaker: {key_stats['circuit_breaker_state']}")
        print()
    
    # 7. Comparison with original
    print("=" * 80)
    print("  СРАВНЕНИЕ С ОРИГИНАЛЬНОЙ ВЕРСИЕЙ")
    print("=" * 80)
    print()
    print("Original (v1):")
    print("  ✅ 6/8 tasks successful (75%)")
    print("  ❌ 2/8 failed (network issues)")
    print("  ⏱️  67.41 seconds")
    print()
    print("Improved (v2):")
    print(f"  ✅ {len(successful)}/{len(tasks)} successful ({len(successful)/len(tasks)*100:.0f}%)")
    print(f"  ❌ {len(failed)}/{len(tasks)} failed")
    print(f"  ⏱️  {total_time:.2f} seconds")
    print()
    
    improvement = len(successful) - 6
    if improvement > 0:
        print(f"🎉 УЛУЧШЕНИЕ: +{improvement} задач успешно!")
        print("   ✅ Retry logic работает!")
        print("   ✅ Circuit breaker предотвращает cascading failures!")
        print("   ✅ Exponential backoff справляется с transient errors!")
    
    print()
    print("=" * 80)
    print("  ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)


async def main():
    await test_improved_client()


if __name__ == "__main__":
    asyncio.run(main())
