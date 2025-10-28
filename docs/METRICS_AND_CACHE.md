# Prometheus Metrics & Redis Cache Implementation

## 📊 Prometheus Метрики

### Реализованные метрики

#### 1. **API Request Metrics**
```python
# Счётчик запросов
bybit_api_requests_total
  labels: [symbol, interval, endpoint, status]
  
# Гистограмма задержек
bybit_api_duration_seconds
  labels: [symbol, interval, endpoint]
  buckets: [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
```

**Пример:**
```
bybit_api_requests_total{symbol="BTCUSDT",interval="1",endpoint="kline",status="success"} 150
bybit_api_duration_seconds_sum{symbol="BTCUSDT",interval="1",endpoint="kline"} 45.2
bybit_api_duration_seconds_count{symbol="BTCUSDT",interval="1",endpoint="kline"} 150
```

#### 2. **Cache Metrics**
```python
# Операции с кэшем
bybit_cache_operations_total
  labels: [operation, result]  # operation: get/set/clear, result: hit/miss/success

# Размер кэша
bybit_cache_size_bytes
  labels: [cache_type]  # redis/file

# Количество элементов
bybit_cache_items_total
  labels: [cache_type]
```

**Пример:**
```
bybit_cache_operations_total{operation="get",result="hit"} 89
bybit_cache_operations_total{operation="get",result="miss"} 11
bybit_cache_size_bytes{cache_type="redis"} 1048576
```

#### 3. **Data Metrics**
```python
# Количество свечей
bybit_candles_fetched_total
  labels: [symbol, interval, source]  # source: api/cache

bybit_candles_stored_total
  labels: [symbol, interval, destination]  # destination: cache/db
```

#### 4. **Error Metrics**
```python
# Ошибки
bybit_errors_total
  labels: [error_type, symbol, interval]

# Rate limit
bybit_rate_limit_hits_total
  labels: [symbol]

# Ретрай
bybit_retry_attempts_total
  labels: [symbol, interval, attempt]
```

#### 5. **Historical Fetch Metrics**
```python
# Исторические загрузки
bybit_historical_fetches_total
  labels: [symbol, interval]

bybit_historical_fetch_duration_seconds
  labels: [symbol, interval]
  buckets: [1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]

bybit_historical_api_requests_per_fetch
  labels: [symbol, interval]
  buckets: [1, 2, 3, 5, 7, 10, 15, 20]
```

### Endpoints

#### GET /api/v1/health/metrics
Prometheus-совместимый endpoint для скрейпинга метрик.

**Пример запроса:**
```bash
curl http://localhost:8000/api/v1/health/metrics
```

**Пример ответа:**
```prometheus
# HELP bybit_api_requests_total Total number of Bybit API requests
# TYPE bybit_api_requests_total counter
bybit_api_requests_total{symbol="BTCUSDT",interval="1",endpoint="kline",status="success"} 150.0

# HELP bybit_api_duration_seconds Bybit API request duration in seconds
# TYPE bybit_api_duration_seconds histogram
bybit_api_duration_seconds_bucket{symbol="BTCUSDT",interval="1",endpoint="kline",le="0.1"} 10.0
bybit_api_duration_seconds_bucket{symbol="BTCUSDT",interval="1",endpoint="kline",le="0.25"} 45.0
...
```

### Настройка Prometheus

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'bybit_strategy_tester'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/health/metrics'
```

### Запросы для анализа

**1. Cache hit rate:**
```promql
rate(bybit_cache_operations_total{result="hit"}[5m]) 
/ 
(rate(bybit_cache_operations_total{result="hit"}[5m]) + rate(bybit_cache_operations_total{result="miss"}[5m]))
```

**2. API latency (95th percentile):**
```promql
histogram_quantile(0.95, 
  rate(bybit_api_duration_seconds_bucket[5m])
)
```

**3. Error rate:**
```promql
rate(bybit_errors_total[5m])
```

**4. Rate limit hits:**
```promql
increase(bybit_rate_limit_hits_total[1h])
```

---

## 🗄️ Redis Cache

### Возможности

1. **Автоматическая сериализация**: Pickle + zlib compression
2. **TTL поддержка**: Настраиваемое время жизни кэша
3. **Compression**: Автоматическое сжатие данных >1KB
4. **Metrics integration**: Автоматический сбор метрик
5. **Graceful degradation**: Работает без Redis (fallback)

### Конфигурация

**.env:**
```bash
# Redis настройки
BYBIT_REDIS_ENABLED=true
BYBIT_REDIS_HOST=localhost
BYBIT_REDIS_PORT=6379
BYBIT_REDIS_DB=0
BYBIT_REDIS_PASSWORD=  # опционально

# Время жизни кэша (дни)
BYBIT_CACHE_TTL_DAYS=7
```

### Использование

#### Автоматический кэш (в BybitAdapter)
```python
from backend.services.adapters.bybit import BybitAdapter

adapter = BybitAdapter()

# Первый запрос - API call
candles = adapter.get_klines('BTCUSDT', '15', 1000)  # -> API

# Второй запрос - cache hit
candles = adapter.get_klines('BTCUSDT', '15', 1000)  # -> Redis Cache
```

#### Ручное использование
```python
from backend.core.cache import get_cache, make_cache_key

cache = get_cache()

# Set
cache_key = make_cache_key('BTCUSDT', '15', 1000)
cache.set(cache_key, candles_data, ttl=3600)

# Get
cached = cache.get(cache_key, symbol='BTCUSDT', interval='15')

# Delete
cache.delete(cache_key)

# Clear all
cache.clear('klines:*')
```

### Структура ключей

```
bybit:klines:{SYMBOL}:{INTERVAL}:{LIMIT}
```

**Примеры:**
```
bybit:klines:BTCUSDT:1:1000
bybit:klines:ETHUSDT:15:2000
bybit:klines:SOLUSDT:60:500
```

### Compression

Автоматическое сжатие для значений >1KB:

```python
# Данные до сжатия: 50KB
# Данные после сжатия: ~15KB (компрессия ~70%)

# Формат:
# Byte 0: 0x00 = not compressed, 0x01 = compressed
# Byte 1+: payload (pickle or zlib)
```

### Health Check

**Endpoint:** `GET /api/v1/health`

Проверяет:
- ✅ Redis connection
- ✅ Latency
- ✅ Memory usage

**Пример ответа:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T12:00:00Z",
  "components": {
    "cache": {
      "status": "healthy",
      "latency_ms": 1.23,
      "host": "localhost",
      "port": 6379,
      "total_keys": 45,
      "used_memory": "2.5MB"
    }
  }
}
```

### Statistics

```python
cache = get_cache()
stats = cache.get_stats()

# {
#   'connected': True,
#   'total_keys': 45,
#   'used_memory': '2.5MB',
#   'used_memory_rss': '3.1MB',
#   'db_keys': 150
# }
```

### Мониторинг

**Cache hit rate метрика:**
```promql
bybit_cache_operations_total{result="hit"} / 
(bybit_cache_operations_total{result="hit"} + bybit_cache_operations_total{result="miss"})
```

**Cache size метрика:**
```promql
bybit_cache_size_bytes{cache_type="redis"}
```

**Cache items метрика:**
```promql
bybit_cache_items_total{cache_type="redis"}
```

---

## 🚀 Быстрый старт

### 1. Установка Redis (Docker)

```bash
docker run -d \
  --name redis-bybit \
  -p 6379:6379 \
  redis:7-alpine
```

### 2. Настройка .env

```bash
# Включить Redis
BYBIT_REDIS_ENABLED=true
BYBIT_REDIS_HOST=localhost
BYBIT_REDIS_PORT=6379
```

### 3. Запуск API

```bash
uvicorn backend.api.app:app --reload --port 8000
```

### 4. Проверка метрик

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Metrics
curl http://localhost:8000/api/v1/health/metrics

# Redis stats
curl http://localhost:8000/api/v1/health | jq '.components.cache'
```

### 5. Тестирование кэша

```python
import requests

# Первый запрос (API)
r = requests.get('http://localhost:8000/api/v1/marketdata/klines/BTCUSDT?interval=15&limit=1000')
# Check metrics: bybit_cache_operations_total{result="miss"}

# Второй запрос (Cache)
r = requests.get('http://localhost:8000/api/v1/marketdata/klines/BTCUSDT?interval=15&limit=1000')
# Check metrics: bybit_cache_operations_total{result="hit"}
```

---

## 📈 Преимущества

### Prometheus Metrics
- ✅ **Observability**: Полная видимость работы системы
- ✅ **Alerting**: Настройка алертов на критические метрики
- ✅ **Performance analysis**: Анализ задержек и bottleneck'ов
- ✅ **Capacity planning**: Прогнозирование нагрузки

### Redis Cache
- ✅ **Performance**: Сокращение API запросов на 80-90%
- ✅ **Cost reduction**: Снижение rate limit violations
- ✅ **Reliability**: Работа при недоступности Bybit API
- ✅ **Scalability**: Horizontal scaling с Redis Cluster

---

## 🔧 Troubleshooting

### Redis не подключается

```bash
# Проверка Redis
docker ps | grep redis

# Логи Redis
docker logs redis-bybit

# Тест подключения
redis-cli -h localhost -p 6379 ping
# Ожидаемый ответ: PONG
```

### Метрики не появляются

```bash
# Проверка endpoint
curl http://localhost:8000/api/v1/health/metrics

# Проверка логов
tail -f logs/app.log | grep metrics
```

### Cache не работает

```python
# Проверка конфигурации
from backend.core.config import get_config
config = get_config()
print(f"Redis enabled: {config.REDIS_ENABLED}")

# Проверка кэша
from backend.core.cache import get_cache
cache = get_cache()
print(cache.health_check())
```

---

## 📝 Следующие шаги

### Реализовано ✅
- [x] Prometheus метрики
- [x] Redis кэширование
- [x] Metrics endpoint
- [x] Cache integration в BybitAdapter

### В разработке 🔄
- [ ] Async BybitAdapter
- [ ] Rate limiting middleware
- [ ] Grafana dashboards

### Планируется 📋
- [ ] Redis Sentinel для HA
- [ ] Redis Cluster для scaling
- [ ] Custom Prometheus exporters
