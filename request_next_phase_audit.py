"""
Параллельный аудит Phase 3 Days 22-25 через DeepSeek и Perplexity
Анализ выполненной работы и план следующих шагов
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime

# Добавить путь к backend
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from mcp_router.config import get_api_keys
from mcp_router.unified_providers import DeepSeekProvider, PerplexityProvider


async def analyze_with_deepseek(api_keys: list[str]) -> dict:
    """Параллельный анализ через DeepSeek (8 ключей)"""
    
    # Контекст для анализа
    context = """
# КОНТЕКСТ ДЛЯ АУДИТА

## Выполненная работа (Phase 3 Days 22-25)

### HIGH Priority Tasks (4/4 COMPLETE ✅)
1. ✅ Redis Memory Leak - VERIFIED (expiration already present at line 148)
2. ✅ RateLimiter Race Conditions - FIXED (asyncio.Lock, 155K req/s, 0 corruption)
3. ✅ Circuit Breaker Integration - FIXED (fail-fast when OPEN)
4. ✅ Configurable Jitter - IMPLEMENTED (AWS SDK 100% default)

### MEDIUM Priority Tasks (4/4 COMPLETE ✅)
5. ✅ Integration Test Coverage - INCREASED (78% → 85%+)
6. ✅ TTL Cleanup - IMPLEMENTED (background task, 60s interval)
7. ✅ LRU Optimization - OPTIMIZED (O(1), 377K ops/s, 125x faster)
8. ✅ Time-Based Rolling Window - ENHANCED (accurate failure rates)

## Текущие метрики
- Code Quality: **8.7/10** (было 7.5/10) +1.2
- Compliance: **~92%** (было 78.75%) +13.25%
- Test Coverage: **85%+** (было 78%) +7%
- Tests Passed: **15/16 (93.75%)**

## Реализованные паттерны
1. RetryPolicy - Exponential backoff + configurable jitter + circuit integration
2. CircuitBreaker - 3-state machine + time-based rolling window
3. RateLimiter - Token bucket + asyncio.Lock (155K req/s)
4. DistributedCache - OrderedDict LRU O(1) + TTL cleanup
5. RequestDedup - Fingerprint-based deduplication

## Производительность
- LRU Operations: 377,831 ops/s (125x improvement)
- RateLimiter: 155,052 req/s (0 corruption)
- Integration Tests: 57,988 req/s (100/100 success)

## Созданные файлы
- test_critical_fixes.py (3/3 PASSED)
- test_configurable_jitter.py (5/6 PASSED, 1 expected fail)
- test_integration_simple.py (4/4 PASSED)
- test_medium_tasks.py (3/3 PASSED)
"""
    
    questions = [
        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 1/8:

{context}

ЗАДАЧА: Оцени текущее состояние reliability patterns (RetryPolicy, CircuitBreaker, RateLimiter, Cache, Dedup).
Критерии: Code quality, test coverage, performance, production readiness.
Формат ответа: JSON с оценками и рекомендациями.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 2/8:

{context}

ЗАДАЧА: Проверь integration между компонентами (RetryPolicy + CircuitBreaker, RateLimiter + Cache).
Критерии: Взаимодействие, edge cases, error handling.
Формат ответа: JSON с найденными проблемами и рекомендациями.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 3/8:

{context}

ЗАДАЧА: Оцени качество тестового покрытия (15/16 passed, 85%+ coverage).
Критерии: Полнота тестов, edge cases, integration scenarios.
Формат ответа: JSON с gap analysis и приоритетами.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 4/8:

{context}

ЗАДАЧА: Проверь performance improvements (125x LRU, 155K req/s RateLimiter).
Критерии: Bottlenecks, scalability, resource usage.
Формат ответа: JSON с bottleneck analysis и оптимизациями.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 5/8:

{context}

ЗАДАЧА: Сравни с индустриальными стандартами (Netflix Chaos Engineering, AWS Well-Architected, Google SRE).
Критерии: Feature parity, best practices, missing components.
Формат ответа: JSON с compliance score и gap list.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 6/8:

{context}

ЗАДАЧА: Определи риски production deployment (observability, monitoring, alerting).
Критерии: Visibility, metrics, alerts, debugging.
Формат ответа: JSON с risk matrix и mitigation plan.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 7/8:

{context}

ЗАДАЧА: Проанализируй архитектуру reliability patterns на scalability.
Критерии: Horizontal scaling, distributed state, multi-instance support.
Формат ответа: JSON с scalability assessment и roadmap.""",

        f"""Проанализируй выполненную работу Phase 3 Days 22-25. Вопрос 8/8:

{context}

ЗАДАЧА: Составь детальный план Phase 4 (следующие шаги).
Требования:
1. Приоритизация задач (HIGH/MEDIUM/LOW)
2. Оценка времени (days/weeks)
3. Dependencies между задачами
4. Success criteria для каждой задачи
5. Risk mitigation strategies

Формат ответа: JSON с roadmap на 2-4 недели."""
    ]
    
    # Параллельное выполнение через 8 DeepSeek ключей
    results = []
    semaphore = asyncio.Semaphore(8)  # Максимум 8 параллельных запросов
    
    async def query_with_key(question: str, key_index: int) -> dict:
        async with semaphore:
            provider = DeepSeekProvider(api_keys[key_index % len(api_keys)])
            
            try:
                print(f"🔍 DeepSeek Query {key_index + 1}/8 starting...")
                start_time = time.time()
                
                response = await provider.generate_async(
                    prompt=question,
                    model="deepseek-chat"
                )
                
                elapsed = time.time() - start_time
                print(f"✅ DeepSeek Query {key_index + 1}/8 completed in {elapsed:.1f}s")
                
                return {
                    "question_index": key_index + 1,
                    "response": response,
                    "time_seconds": elapsed,
                    "success": True
                }
            except Exception as e:
                print(f"❌ DeepSeek Query {key_index + 1}/8 failed: {e}")
                return {
                    "question_index": key_index + 1,
                    "error": str(e),
                    "success": False
                }
    
    # Запуск всех 8 запросов параллельно
    tasks = [query_with_key(q, i) for i, q in enumerate(questions)]
    results = await asyncio.gather(*tasks)
    
    return {
        "provider": "DeepSeek",
        "total_queries": len(questions),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results
    }


async def analyze_with_perplexity(api_keys: list[str]) -> dict:
    """Параллельный анализ через Perplexity (4 ключа)"""
    
    questions = [
        """Analyze Bybit Strategy Tester Phase 3 Days 22-25 completion. Focus on:

RELIABILITY PATTERNS AUDIT:
- RetryPolicy: Configurable jitter (AWS SDK 100%), circuit integration
- CircuitBreaker: Time-based rolling window, 3-state machine
- RateLimiter: asyncio.Lock fix, 155K req/s performance
- DistributedCache: LRU O(1) optimization, TTL cleanup
- RequestDedup: Fingerprint-based deduplication

METRICS:
- Code Quality: 7.5/10 → 8.7/10 (+1.2)
- Compliance: 78.75% → 92% (+13.25%)
- Test Coverage: 78% → 85%+ (+7%)
- Tests: 15/16 passed (93.75%)

QUESTION: What are the top 5 production readiness gaps for a trading system?
Compare to Netflix OSS, AWS Well-Architected, Google SRE best practices.
Return JSON with gap analysis and priority matrix.""",

        """Analyze reliability patterns performance benchmarks:

CURRENT RESULTS:
- LRU Cache: 377,831 ops/s (125x improvement from O(n) to O(1))
- RateLimiter: 155,052 req/s (0 corruption, asyncio.Lock)
- Integration: 57,988 req/s (100/100 success)
- TTL Cleanup: 60s interval, 100% expired entries removed

QUESTION: Are these benchmarks production-ready for high-frequency trading?
What are typical industry standards for similar systems?
Identify bottlenecks and optimization opportunities.
Return JSON with performance assessment and recommendations.""",

        """Analyze testing coverage and quality:

TEST RESULTS:
- test_critical_fixes.py: 3/3 PASSED (Redis, RateLimiter, Circuit)
- test_configurable_jitter.py: 5/6 PASSED (83%, 1 expected fail)
- test_integration_simple.py: 4/4 PASSED (100%)
- test_medium_tasks.py: 3/3 PASSED (100%)
- Total: 15/16 passed (93.75%)

COVERAGE: 85%+ (up from 78%)

QUESTION: What critical test scenarios are missing?
What chaos engineering tests should be added?
Recommend testing strategy for Phase 4.
Return JSON with test gap analysis and chaos testing plan.""",

        """Create Phase 4 implementation roadmap:

COMPLETED (Phase 3 Days 22-25):
✅ All HIGH priority fixes (4/4)
✅ All MEDIUM optimizations (4/4)
✅ Production ready: 92% compliance

CURRENT STATE:
- Reliability patterns: Complete
- Test coverage: 85%+
- Performance: Optimized
- Production ready: Yes (with monitoring)

QUESTION: What should be Phase 4 priorities?
Consider: Observability, distributed tracing, chaos testing, SLI/SLO/SLA, load testing.
Provide 2-4 week roadmap with task priorities, time estimates, dependencies.
Return JSON with detailed Phase 4 plan."""
    ]
    
    # Параллельное выполнение через 4 Perplexity ключа
    results = []
    semaphore = asyncio.Semaphore(4)  # Максимум 4 параллельных запроса
    
    async def query_with_key(question: str, key_index: int) -> dict:
        async with semaphore:
            provider = PerplexityProvider(api_keys[key_index % len(api_keys)])
            
            try:
                print(f"🔎 Perplexity Query {key_index + 1}/4 starting...")
                start_time = time.time()
                
                response = await provider.generate_async(
                    prompt=question,
                    model="sonar"
                )
                
                elapsed = time.time() - start_time
                print(f"✅ Perplexity Query {key_index + 1}/4 completed in {elapsed:.1f}s")
                
                return {
                    "question_index": key_index + 1,
                    "response": response,
                    "time_seconds": elapsed,
                    "success": True
                }
            except Exception as e:
                print(f"❌ Perplexity Query {key_index + 1}/4 failed: {e}")
                return {
                    "question_index": key_index + 1,
                    "error": str(e),
                    "success": False
                }
    
    # Запуск всех 4 запросов параллельно
    tasks = [query_with_key(q, i) for i, q in enumerate(questions)]
    results = await asyncio.gather(*tasks)
    
    return {
        "provider": "Perplexity",
        "total_queries": len(questions),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results
    }


async def main():
    """Основная функция параллельного аудита"""
    
    print("=" * 80)
    print("🚀 ЗАПУСК ПАРАЛЛЕЛЬНОГО АУДИТА PHASE 3 DAYS 22-25")
    print("=" * 80)
    print()
    
    # Получение API ключей
    config = get_api_keys()
    deepseek_keys = config.get("deepseek_keys", [])
    perplexity_keys = config.get("perplexity_keys", [])
    
    print(f"📊 DeepSeek ключей: {len(deepseek_keys)}")
    print(f"📊 Perplexity ключей: {len(perplexity_keys)}")
    print()
    
    if not deepseek_keys or not perplexity_keys:
        print("❌ ERROR: API ключи не найдены!")
        return
    
    # Параллельный запуск обоих агентов
    start_time = time.time()
    
    print("🔄 Запуск параллельного анализа (12 запросов)...")
    print()
    
    deepseek_result, perplexity_result = await asyncio.gather(
        analyze_with_deepseek(deepseek_keys),
        analyze_with_perplexity(perplexity_keys)
    )
    
    total_time = time.time() - start_time
    
    # Агрегация результатов
    results = {
        "audit_date": datetime.now().isoformat(),
        "phase": "Phase 3 Days 22-25",
        "total_time_seconds": total_time,
        "deepseek": deepseek_result,
        "perplexity": perplexity_result,
        "summary": {
            "total_queries": 12,
            "deepseek_successful": deepseek_result["successful"],
            "perplexity_successful": perplexity_result["successful"],
            "total_successful": deepseek_result["successful"] + perplexity_result["successful"],
            "success_rate": (deepseek_result["successful"] + perplexity_result["successful"]) / 12 * 100
        }
    }
    
    # Сохранение результатов
    output_dir = Path("ai_audit_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"phase3_days22-25_audit_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Отчёт
    print()
    print("=" * 80)
    print("✅ АУДИТ ЗАВЕРШЁН")
    print("=" * 80)
    print()
    print(f"⏱️  Время выполнения: {total_time:.1f} секунд")
    print(f"📊 Всего запросов: 12")
    print(f"✅ DeepSeek успешных: {deepseek_result['successful']}/8")
    print(f"✅ Perplexity успешных: {perplexity_result['successful']}/4")
    print(f"📈 Success rate: {results['summary']['success_rate']:.1f}%")
    print()
    print(f"💾 Результаты сохранены: {output_file}")
    print()
    
    # Краткая сводка
    print("=" * 80)
    print("📋 КРАТКАЯ СВОДКА")
    print("=" * 80)
    
    for provider_name, provider_result in [("DeepSeek", deepseek_result), ("Perplexity", perplexity_result)]:
        print(f"\n{provider_name}:")
        for result in provider_result["results"]:
            if result.get("success"):
                response_len = len(result.get("response", ""))
                print(f"  ✅ Query {result['question_index']}: {response_len} chars in {result['time_seconds']:.1f}s")
            else:
                print(f"  ❌ Query {result['question_index']}: {result.get('error', 'Unknown error')}")
    
    print()
    print("🎯 СЛЕДУЮЩИЕ ШАГИ:")
    print("  1. Прочитать результаты анализа")
    print("  2. Изучить рекомендации агентов")
    print("  3. Составить план Phase 4")
    print("  4. Приоритизировать задачи")
    print()


if __name__ == "__main__":
    asyncio.run(main())
