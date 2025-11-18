"""
Упрощённый запрос аудита к DeepSeek и Perplexity
Использует прямые HTTP запросы через httpx
"""

import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
import os


# Загрузка API ключей из .env
def load_api_keys():
    """Загрузить API ключи из .env"""
    env_file = Path(__file__).parent / ".env"
    
    deepseek_keys = []
    perplexity_keys = []
    
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY"):
                    key = line.split("=", 1)[1].strip().strip('"\'')
                    if key and key != "your-key-here":
                        deepseek_keys.append(key)
                elif line.startswith("PERPLEXITY_API_KEY"):
                    key = line.split("=", 1)[1].strip().strip('"\'')
                    if key and key != "your-key-here":
                        perplexity_keys.append(key)
    
    return deepseek_keys, perplexity_keys


async def query_deepseek(api_key: str, prompt: str, index: int) -> dict:
    """Запрос к DeepSeek API"""
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    try:
        print(f"🔍 DeepSeek Query {index}/8 starting...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print(f"✅ DeepSeek Query {index}/8 completed ({len(content)} chars)")
            
            return {
                "index": index,
                "response": content,
                "success": True
            }
    
    except Exception as e:
        print(f"❌ DeepSeek Query {index}/8 failed: {e}")
        return {
            "index": index,
            "error": str(e),
            "success": False
        }


async def query_perplexity(api_key: str, prompt: str, index: int) -> dict:
    """Запрос к Perplexity API"""
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    try:
        print(f"🔎 Perplexity Query {index}/4 starting...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print(f"✅ Perplexity Query {index}/4 completed ({len(content)} chars)")
            
            return {
                "index": index,
                "response": content,
                "success": True
            }
    
    except Exception as e:
        print(f"❌ Perplexity Query {index}/4 failed: {e}")
        return {
            "index": index,
            "error": str(e),
            "success": False
        }


async def main():
    """Основная функция"""
    
    print("=" * 80)
    print("🚀 ЗАПУСК АУДИТА PHASE 3 DAYS 22-25")
    print("=" * 80)
    print()
    
    # Загрузка ключей
    deepseek_keys, perplexity_keys = load_api_keys()
    
    print(f"📊 DeepSeek ключей: {len(deepseek_keys)}")
    print(f"📊 Perplexity ключей: {len(perplexity_keys)}")
    print()
    
    if not deepseek_keys or not perplexity_keys:
        print("❌ ERROR: API ключи не найдены в .env!")
        return
    
    # Контекст для анализа
    context = """
# КОНТЕКСТ ДЛЯ АУДИТА

## Выполненная работа (Phase 3 Days 22-25)

### HIGH Priority Tasks (4/4 COMPLETE ✅)
1. ✅ Redis Memory Leak - VERIFIED
2. ✅ RateLimiter Race Conditions - FIXED (asyncio.Lock, 155K req/s)
3. ✅ Circuit Breaker Integration - FIXED
4. ✅ Configurable Jitter - IMPLEMENTED (AWS SDK 100%)

### MEDIUM Priority Tasks (4/4 COMPLETE ✅)
5. ✅ Integration Test Coverage - INCREASED (78% → 85%+)
6. ✅ TTL Cleanup - IMPLEMENTED
7. ✅ LRU Optimization - OPTIMIZED (O(1), 377K ops/s)
8. ✅ Time-Based Rolling Window - ENHANCED

## Метрики
- Code Quality: 8.7/10 (было 7.5/10)
- Compliance: ~92% (было 78.75%)
- Test Coverage: 85%+ (было 78%)
- Tests: 15/16 passed (93.75%)

## Производительность
- LRU Cache: 377,831 ops/s
- RateLimiter: 155,052 req/s
- Integration: 57,988 req/s
"""
    
    # Вопросы для DeepSeek
    deepseek_questions = [
        f"{context}\n\nВопрос 1/8: Оцени reliability patterns (RetryPolicy, CircuitBreaker, RateLimiter, Cache). Верни JSON с оценками.",
        f"{context}\n\nВопрос 2/8: Проверь integration между компонентами. Верни JSON с найденными проблемами.",
        f"{context}\n\nВопрос 3/8: Оцени test coverage (15/16 passed, 85%). Верни JSON с gap analysis.",
        f"{context}\n\nВопрос 4/8: Проверь performance (125x LRU, 155K req/s). Верни JSON с bottleneck analysis.",
        f"{context}\n\nВопрос 5/8: Сравни с Netflix, AWS, Google SRE стандартами. Верни JSON с compliance score.",
        f"{context}\n\nВопрос 6/8: Определи риски production deployment. Верни JSON с risk matrix.",
        f"{context}\n\nВопрос 7/8: Оцени scalability (horizontal scaling, distributed). Верни JSON с assessment.",
        f"{context}\n\nВопрос 8/8: Составь план Phase 4 (приоритеты, время, dependencies). Верни JSON с roadmap."
    ]
    
    # Вопросы для Perplexity
    perplexity_questions = [
        f"{context}\n\nWhat are top 5 production readiness gaps for trading system? Compare to Netflix, AWS, Google SRE. Return JSON.",
        f"{context}\n\nAre these benchmarks production-ready for HFT? What are industry standards? Return JSON with assessment.",
        f"{context}\n\nWhat critical test scenarios are missing? Chaos testing plan? Return JSON with recommendations.",
        f"{context}\n\nCreate Phase 4 roadmap (2-4 weeks). Priorities: observability, tracing, chaos, SLI/SLO. Return JSON."
    ]
    
    # Параллельный запуск
    print("🔄 Запуск параллельных запросов (8 DeepSeek + 4 Perplexity)...")
    print()
    
    deepseek_tasks = [
        query_deepseek(deepseek_keys[i % len(deepseek_keys)], q, i+1)
        for i, q in enumerate(deepseek_questions)
    ]
    
    perplexity_tasks = [
        query_perplexity(perplexity_keys[i % len(perplexity_keys)], q, i+1)
        for i, q in enumerate(perplexity_questions)
    ]
    
    deepseek_results, perplexity_results = await asyncio.gather(
        asyncio.gather(*deepseek_tasks),
        asyncio.gather(*perplexity_tasks)
    )
    
    # Сохранение результатов
    results = {
        "audit_date": datetime.now().isoformat(),
        "phase": "Phase 3 Days 22-25",
        "deepseek": {
            "total": len(deepseek_questions),
            "successful": sum(1 for r in deepseek_results if r["success"]),
            "results": deepseek_results
        },
        "perplexity": {
            "total": len(perplexity_questions),
            "successful": sum(1 for r in perplexity_results if r["success"]),
            "results": perplexity_results
        }
    }
    
    # Сохранение
    output_dir = Path("ai_audit_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"phase3_audit_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Отчёт
    print()
    print("=" * 80)
    print("✅ АУДИТ ЗАВЕРШЁН")
    print("=" * 80)
    print()
    print(f"📊 DeepSeek: {results['deepseek']['successful']}/{results['deepseek']['total']}")
    print(f"📊 Perplexity: {results['perplexity']['successful']}/{results['perplexity']['total']}")
    print(f"💾 Результаты: {output_file}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
