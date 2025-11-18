# Grafana Dashboards для Bybit Strategy Tester

Эта директория содержит готовые Grafana dashboard конфигурации для мониторинга производительности и эффективности Bybit Strategy Tester.

## 📊 Доступные Dashboards

### 1. **bybit_performance.json** - Производительность системы

Метрики:
- **API Request Rate** - Частота запросов к Bybit API
- **API Latency (95th percentile)** - Задержки API запросов
- **Cache Hit Rate** - Процент попаданий в кэш
- **Error Rate** - Частота ошибок
- **Rate Limit Hits** - Количество превышений лимитов
- **Cache Size** - Размер кэша Redis
- **Candles Fetched** - Количество свечей по источникам (API/Cache)
- **Historical Fetch Duration** - Время исторических загрузок

**Использование:**
- Мониторинг общей производительности
- Выявление bottleneck'ов
- Контроль rate limiting
- Анализ нагрузки на API

### 2. **bybit_cache_efficiency.json** - Эффективность кэширования

Метрики:
- **Cache Hit/Miss Rate** (pie chart) - Распределение попаданий/промахов
- **Cache Hit Rate Over Time** - Динамика hit rate
- **Cache Operations Rate** - Частота операций с кэшем (GET/SET)
- **Cache Size Trend** - Рост размера кэша
- **Cache Items Count** - Количество элементов
- **API Requests Saved** - Сколько запросов сэкономлено благодаря кэшу
- **Data Source Distribution** - Откуда получены данные (API vs Cache)
- **Cache Efficiency Score** - Общая оценка эффективности (gauge)

**Использование:**
- Оптимизация TTL кэша
- Анализ эффективности кэширования
- Планирование емкости Redis
- ROI анализ кэширования

---

## 🚀 Быстрый старт

### Шаг 1: Установка Prometheus

**Docker Compose:**
```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'

volumes:
  prometheus_data:
```

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'bybit_strategy_tester'
    scrape_interval: 10s
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/api/v1/health/metrics'
```

**Запуск:**
```bash
docker-compose up -d prometheus
```

### Шаг 2: Установка Grafana

**Docker Compose (добавить в тот же файл):**
```yaml
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning

volumes:
  grafana_data:
```

**Запуск:**
```bash
docker-compose up -d grafana
```

### Шаг 3: Настройка Grafana

1. **Открыть Grafana:**
   ```
   http://localhost:3000
   Login: admin
   Password: admin
   ```

2. **Добавить Prometheus Data Source:**
   - Configuration → Data Sources → Add data source
   - Выбрать "Prometheus"
   - URL: `http://prometheus:9090`
   - Нажать "Save & Test"

3. **Импортировать Dashboards:**
   - Dashboards → Import → Upload JSON file
   - Выбрать `bybit_performance.json`
   - Повторить для `bybit_cache_efficiency.json`

### Шаг 4: Запуск API с метриками

```bash
# Включить метрики в .env
BYBIT_ENABLE_METRICS=true
BYBIT_REDIS_ENABLED=true

# Запустить API
uvicorn backend.api.app:app --reload --port 8000
```

### Шаг 5: Проверка

```bash
# Проверить метрики доступны
curl http://localhost:8000/api/v1/health/metrics

# Проверить Prometheus собирает данные
curl http://localhost:9090/api/v1/targets

# Открыть Grafana dashboard
# http://localhost:3000/dashboards
```

---

## 📈 Настройка и кастомизация

### Изменение refresh rate

В JSON файле найти:
```json
"refresh": "30s"
```

Можно установить: `"5s"`, `"10s"`, `"1m"`, `"5m"`

### Добавление новых панелей

Пример добавления панели для specific symbol:

```json
{
  "id": 10,
  "title": "BTCUSDT Specific Metrics",
  "type": "graph",
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
  "targets": [
    {
      "expr": "rate(bybit_api_requests_total{symbol=\"BTCUSDT\"}[5m])",
      "legendFormat": "{{status}}",
      "refId": "A"
    }
  ]
}
```

### Настройка алертов

В Grafana UI:
1. Открыть панель
2. Edit → Alert
3. Создать условие, например:
   ```
   WHEN avg() OF query(A, 5m, now) IS ABOVE 0.1
   ```
4. Настроить notification channel (Email, Slack, etc.)

---

## 🔧 Troubleshooting

### Метрики не отображаются

**Проблема:** Grafana показывает "No data"

**Решение:**
```bash
# 1. Проверить endpoint метрик
curl http://localhost:8000/api/v1/health/metrics

# 2. Проверить Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# 3. Проверить Prometheus Query
curl 'http://localhost:9090/api/v1/query?query=bybit_api_requests_total'

# 4. Проверить data source в Grafana
# Settings → Data Sources → Prometheus → Test
```

### Prometheus не скрейпит

**Проблема:** Targets в Prometheus показывают DOWN

**Решение:**
```yaml
# Для Docker на Windows использовать host.docker.internal
targets: ['host.docker.internal:8000']

# Для Linux использовать
targets: ['172.17.0.1:8000']  # Docker bridge IP

# Или запустить Prometheus в host network mode
docker run --network=host prom/prometheus
```

### Dashboard не импортируется

**Проблема:** "Dashboard import failed"

**Решение:**
1. Проверить JSON валидность: https://jsonlint.com/
2. Убедиться что Prometheus data source добавлен
3. Попробовать импортировать через UI вместо provisioning

---

## 📊 Полезные Prometheus запросы

### Cache Hit Rate (%)
```promql
rate(bybit_cache_operations_total{result="hit"}[5m]) 
/ 
(rate(bybit_cache_operations_total{result="hit"}[5m]) + rate(bybit_cache_operations_total{result="miss"}[5m])) 
* 100
```

### API Latency 99th percentile
```promql
histogram_quantile(0.99, 
  rate(bybit_api_duration_seconds_bucket[5m])
)
```

### Error Rate (%)
```promql
rate(bybit_errors_total[5m]) 
/ 
rate(bybit_api_requests_total[5m]) 
* 100
```

### Top 5 symbols by request count
```promql
topk(5, 
  rate(bybit_api_requests_total[5m])
)
```

### API Requests saved by cache (last hour)
```promql
increase(bybit_cache_operations_total{result="hit"}[1h])
```

### Average historical fetch duration
```promql
rate(bybit_historical_fetch_duration_seconds_sum[5m]) 
/ 
rate(bybit_historical_fetches_total[5m])
```

---

## 🎯 Best Practices

### 1. Retention Policy

Настроить retention в Prometheus:
```yaml
# prometheus.yml
global:
  storage:
    tsdb:
      retention.time: 30d
      retention.size: 10GB
```

### 2. Dashboard Organization

- **Папки**: Организовать по категориям (Performance, Cache, Errors)
- **Tags**: Использовать для быстрого поиска
- **Naming**: Понятные имена с префиксом проекта

### 3. Alert Thresholds

Рекомендуемые пороги:
```
Cache Hit Rate < 50% → Warning
Cache Hit Rate < 30% → Critical

Error Rate > 1% → Warning
Error Rate > 5% → Critical

API Latency > 2s → Warning
API Latency > 5s → Critical

Rate Limit Hits > 10/hour → Warning
```

### 4. Performance Optimization

- Использовать recording rules для сложных запросов
- Установить разумный scrape_interval (10-30s)
- Включить downsampling для старых данных
- Регулярно проверять cardinality метрик

---

## 📚 Дополнительные ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

---

## 🔄 Обновление Dashboards

При добавлении новых метрик:

1. Обновить JSON конфигурацию
2. Экспортировать из Grafana UI:
   ```
   Dashboard Settings → JSON Model → Copy
   ```
3. Сохранить в файл
4. Commit в репозиторий

---

## 📝 Changelog

### v1.0 (2025-10-26)
- ✅ Initial release
- ✅ Performance dashboard
- ✅ Cache efficiency dashboard
- ✅ 16 visualization panels total
