"""
Тестирование новых функций среднего приоритета
"""

import requests
import json

print("=" * 60)
print("ТЕСТИРОВАНИЕ НОВЫХ ФУНКЦИЙ")
print("=" * 60)

BASE_URL = "http://127.0.0.1:8000"

# 1. Проверка health endpoint
print("\n[1] Проверка /api/v1/health...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"    ✅ Health OK")
        print(f"    Timestamp: {data.get('timestamp', 'N/A')}")
    else:
        print(f"    ❌ Health check failed")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 2. Проверка Prometheus metrics endpoint
print("\n[2] Проверка /api/v1/health/metrics...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/health/metrics", timeout=5)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        content = r.text
        # Подсчитать метрики
        bybit_metrics = [line for line in content.split('\n') if line.startswith('bybit_')]
        print(f"    ✅ Prometheus endpoint OK")
        print(f"    Bybit metrics found: {len(bybit_metrics)}")
        
        # Показать первые 5 метрик
        print("\n    Sample metrics:")
        for metric in bybit_metrics[:5]:
            print(f"      {metric[:80]}...")
    else:
        print(f"    ❌ Metrics endpoint failed")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 3. Проверка Redis cache (опционально)
print("\n[3] Проверка Redis cache...")
try:
    from backend.core.cache import get_cache
    
    cache = get_cache()
    health = cache.health_check()
    
    if health.get('status') == 'healthy':
        print(f"    ✅ Redis connected")
        print(f"    Latency: {health.get('latency_ms', 'N/A')} ms")
    elif health.get('status') == 'unavailable':
        print(f"    ⚠️  Redis not configured (это нормально)")
    else:
        print(f"    ❌ Redis unhealthy: {health.get('error', 'Unknown')}")
except Exception as e:
    print(f"    ⚠️  Cache module not loaded: {e}")

# 4. Проверка metrics в коде
print("\n[4] Проверка metrics модуля...")
try:
    from backend.core.metrics import bybit_api_requests_total
    print(f"    ✅ Metrics module OK")
    print(f"    Metric: bybit_api_requests_total")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 5. Проверка async adapter
print("\n[5] Проверка async adapter...")
try:
    from backend.services.adapters.bybit_async import AsyncBybitAdapter
    print(f"    ✅ AsyncBybitAdapter OK")
except ImportError as e:
    if "aiohttp" in str(e):
        print(f"    ⚠️  aiohttp not installed: pip install aiohttp")
    else:
        print(f"    ❌ Error: {e}")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 6. Проверка rate limit middleware
print("\n[6] Проверка rate limit middleware...")
try:
    from backend.api.middleware.rate_limit import RateLimitMiddleware
    print(f"    ✅ RateLimitMiddleware OK")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 7. Тест API запроса с метриками
print("\n[7] Тест API запроса (должен записать метрики)...")
try:
    r = requests.get(
        f"{BASE_URL}/api/v1/marketdata/bybit/instruments/linear",
        timeout=10
    )
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"    ✅ API работает")
        print(f"    Instruments: {len(data.get('result', []))}")
    else:
        print(f"    ⚠️  Status: {r.status_code}")
except Exception as e:
    print(f"    ❌ Error: {e}")

# 8. Проверка метрик после запроса
print("\n[8] Проверка обновления метрик...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/health/metrics", timeout=5)
    if r.status_code == 200:
        content = r.text
        
        # Ищем конкретные метрики
        api_requests = [l for l in content.split('\n') if 'bybit_api_requests_total' in l and not l.startswith('#')]
        
        if api_requests:
            print(f"    ✅ Метрики обновляются")
            print(f"    API requests metrics: {len(api_requests)}")
        else:
            print(f"    ⚠️  Метрики пустые (нужно больше запросов)")
except Exception as e:
    print(f"    ❌ Error: {e}")

print("\n" + "=" * 60)
print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)
print("\n📚 Для подробной информации см:")
print("   - QUICKSTART.md")
print("   - IMPLEMENTATION_SUMMARY.md")
print("   - docs/METRICS_AND_CACHE.md")
print("\n🚀 Следующие шаги:")
print("   1. pip install aiohttp")
print("   2. Опционально: docker run -d -p 6379:6379 redis:7-alpine")
print("   3. Настроить BYBIT_REDIS_ENABLED=true в .env")
print("   4. Перезапустить API")
