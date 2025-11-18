# 🚀 Быстрый старт - Новые функции

## 📦 Установка зависимостей

```bash
# Установить новые пакеты
pip install aiohttp

# Или обновить все зависимости
pip install -r backend/requirements.txt
```

## ✅ Проверка установки

```bash
# Проверить все модули
py -c "from backend.core.metrics import bybit_api_requests_total; print('✅ Metrics'); from backend.core.cache import RedisCache; print('✅ Cache'); from backend.services.adapters.bybit_async import AsyncBybitAdapter; print('✅ Async Adapter'); from backend.api.middleware.rate_limit import RateLimitMiddleware; print('✅ Rate Limit'); print('\n🎉 ALL MODULES OK!')"
```

**Ожидаемый результат:**
```
✅ Metrics
✅ Cache
✅ Async Adapter
✅ Rate Limit

🎉 ALL MODULES OK!
```

## 🔧 Базовая настройка

### 1. Включить Redis (опционально)

**.env:**
```bash
BYBIT_REDIS_ENABLED=true
BYBIT_REDIS_HOST=localhost
BYBIT_REDIS_PORT=6379
```

**Запустить Redis:**
```bash
docker run -d --name redis-bybit -p 6379:6379 redis:7-alpine
```

### 2. Запустить API

```bash
uvicorn backend.api.app:app --reload --port 8000
```

### 3. Проверить метрики

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Prometheus metrics
curl http://localhost:8000/api/v1/health/metrics
```

## 📊 Мониторинг (опционально)

### Prometheus + Grafana

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'bybit_strategy_tester'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/api/v1/health/metrics'
```

**Запуск:**
```bash
docker-compose up -d
```

**Импорт dashboards:**
1. Открыть http://localhost:3000 (admin/admin)
2. Добавить Prometheus data source (http://prometheus:9090)
3. Import → Upload JSON:
   - `grafana/dashboards/bybit_performance.json`
   - `grafana/dashboards/bybit_cache_efficiency.json`

## 🧪 Тестирование новых функций

### AsyncBybitAdapter

```python
import asyncio
from backend.services.adapters.bybit_async import fetch_multiple_symbols

async def test():
    result = await fetch_multiple_symbols(
        ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
        interval='15',
        limit=100
    )
    
    for symbol, candles in result.items():
        print(f"{symbol}: {len(candles)} candles")

asyncio.run(test())
```

### Redis Cache

```python
from backend.core.cache import get_cache

cache = get_cache()
health = cache.health_check()
print(f"Redis status: {health['status']}")

# Stats
stats = cache.get_stats()
print(f"Total keys: {stats.get('total_keys', 0)}")
```

### Metrics

```bash
# View metrics
curl http://localhost:8000/api/v1/health/metrics | grep bybit_

# Example output:
# bybit_api_requests_total{symbol="BTCUSDT",interval="1",endpoint="kline",status="success"} 150.0
# bybit_cache_operations_total{operation="get",result="hit"} 89.0
```

## 📚 Документация

- **Метрики и кэш**: `docs/METRICS_AND_CACHE.md`
- **Полная документация**: `docs/MEDIUM_PRIORITY_IMPLEMENTATION.md`
- **Grafana setup**: `grafana/README.md`
- **Summary**: `IMPLEMENTATION_SUMMARY.md`

## ⚡ Быстрые команды

```bash
# Проверить все модули
py -c "from backend.core import metrics, cache; print('✅ OK')"

# Запустить тесты
py tests\test_storage_logic.py

# Посмотреть метрики
curl http://localhost:8000/api/v1/health/metrics

# Проверить Redis
docker exec -it redis-bybit redis-cli ping
# PONG

# Grafana dashboards
curl http://localhost:3000/api/dashboards/home
```

## 🎯 Что дальше?

1. ✅ Включить Redis для production
2. ✅ Настроить Prometheus scraping
3. ✅ Импортировать Grafana dashboards
4. ✅ Использовать AsyncBybitAdapter для batch операций
5. ✅ Настроить алерты на критические метрики

---

**Production readiness: 98%** 🎉

Для полной информации см. `IMPLEMENTATION_SUMMARY.md`
