# Prompts Monitoring Guide

**Версия:** 1.0  
**Дата:** 2026-03-03  
**Статус:** ✅ Production Ready

---

## 📊 Обзор

Система мониторинга для AI prompt system предоставляет:

- **Real-time метрики** валидации, логирования, кэша
- **Cost tracking** с разбивкой по агентам и задачам
- **Performance trends** с детализацией по интервалам
- **Dashboard export** в JSON
- **REST API** для интеграции

---

## 🚀 Быстрый старт

### Python API

```python
from backend.monitoring.prompts_monitor import PromptsMonitor

# Создать монитор
monitor = PromptsMonitor()

# Получить дашборд
dashboard = monitor.get_dashboard(period_hours=24)

print(f"Total prompts: {dashboard.total_prompts}")
print(f"Validation success: {dashboard.validation_success_rate:.0%}")
print(f"Cache hit rate: {dashboard.cache_hit_rate:.0%}")
print(f"Total cost: ${dashboard.total_cost_usd:.2f}")
```

### REST API

```bash
# Дашборд
curl http://localhost:8000/api/v1/prompts/monitoring/dashboard

# Валидация
curl http://localhost:8000/api/v1/prompts/monitoring/validation

# Логирование
curl http://localhost:8000/api/v1/prompts/monitoring/logging

# Кэш
curl http://localhost:8000/api/v1/prompts/monitoring/cache

# Затраты
curl http://localhost:8000/api/v1/prompts/monitoring/costs

# Тренды
curl "http://localhost:8000/api/v1/prompts/monitoring/trends?period_hours=24&intervals=24"
```

---

## 📈 Метрики

### Validation Metrics

| Метрика | Описание | Тип |
|---------|----------|-----|
| `total_prompts` | Всего промтов | int |
| `validated_prompts` | Проверено | int |
| `failed_validations` | Провалено | int |
| `validation_success_rate` | % успешных | float (0-1) |
| `injection_attempts_blocked` | Заблокировано атак | int |

### Logging Metrics

| Метрика | Описание | Тип |
|---------|----------|-----|
| `total_logged` | Всего записей | int |
| `total_tokens` | Всего токенов | int |
| `total_cost_usd` | Общая стоимость | float |
| `avg_duration_ms` | Среднее время | float |
| `success_rate` | % успешных | float |

### Cache Metrics

| Метрика | Описание | Тип |
|---------|----------|-----|
| `cache_size` | Размер кэша | int |
| `cache_hits` | Попаданий | int |
| `cache_misses` | Промахов | int |
| `cache_hit_rate` | % попаданий | float (0-1) |

### Cost Metrics

| Метрика | Описание | Тип |
|---------|----------|-----|
| `total_cost_usd` | Всего потрачено | float |
| `by_agent` | По агентам | dict |
| `by_task` | По задачам | dict |
| `projected_monthly_cost` | Прогноз на месяц | float |

---

## 🔧 Конфигурация

### MonitoringConfig

```python
from backend.monitoring.prompts_monitor import MonitoringConfig

config = MonitoringConfig(
    log_db_path="data/prompt_logs.db",     # БД логов
    cache_db_path="data/prompt_cache.db",  # БД кэша (future)
    retention_days=30,                      # Хранение данных
    refresh_interval_sec=60                 # Кэширование метрик
)

monitor = PromptsMonitor(config)
```

---

## 📊 Dashboard API

### Get Dashboard

```python
monitor = PromptsMonitor()
dashboard = monitor.get_dashboard(period_hours=24)

# Доступные поля
dashboard.timestamp              # ISO timestamp
dashboard.period_hours           # Период
dashboard.total_prompts          # Всего промтов
dashboard.validation_success_rate # % валидаций
dashboard.injection_attempts_blocked # Атак заблокировано
dashboard.total_logged           # Записей в логах
dashboard.total_tokens           # Токенов использовано
dashboard.total_cost_usd         # Стоимость
dashboard.avg_duration_ms        # Среднее время
dashboard.cache_size             # Размер кэша
dashboard.cache_hit_rate         # % попаданий
dashboard.by_agent               # По агентам
dashboard.by_task                # По задачам
```

### Get Validation Stats

```python
validation = monitor.get_validation_stats(period_hours=24)

# Возвращает:
{
    "total_prompts": 100,
    "validated": 95,
    "success": 90,
    "failed": 5,
    "success_rate": 0.95,
    "injection_attempts_blocked": 3,
    "period_hours": 24
}
```

### Get Logging Stats

```python
logging = monitor.get_logging_stats(period_hours=24)

# Возвращает:
{
    "total_logged": 100,
    "total_tokens": 150000,
    "total_cost_usd": 0.18,
    "avg_duration_ms": 250.5,
    "success_rate": 0.98,
    "by_agent": {
        "qwen": {"count": 60, "cost": 0.10},
        "deepseek": {"count": 40, "cost": 0.08}
    },
    "by_task": {
        "strategy_generation": {"count": 50},
        "optimization": {"count": 30}
    }
}
```

### Get Cache Stats

```python
cache = monitor.get_cache_stats()

# Возвращает:
{
    "cache_size": 42,
    "max_size": 1000,
    "cache_hits": 85,
    "cache_misses": 15,
    "cache_hit_rate": 0.85,
    "expiring_soon": 5
}
```

### Get Cost Breakdown

```python
cost = monitor.get_cost_breakdown(period_hours=24)

# Возвращает:
{
    "total_cost_usd": 0.18,
    "by_agent": {
        "qwen": {"count": 60, "tokens": 90000, "cost": 0.10},
        "deepseek": {"count": 40, "tokens": 60000, "cost": 0.08}
    },
    "by_task": {
        "strategy_generation": {"count": 50, "cost": 0.10},
        "optimization": {"count": 30, "cost": 0.05}
    },
    "period_hours": 24,
    "projected_monthly_cost": 5.40  # 0.18 * (720 / 24)
}
```

### Get Performance Trends

```python
trends = monitor.get_performance_trends(
    period_hours=24,
    intervals=24  # hourly
)

# Возвращает:
{
    "trends": [
        {
            "timestamp": "2026-03-02T00:00:00",
            "count": 5,
            "avg_duration_ms": 230.5,
            "total_tokens": 7500,
            "total_cost": 0.009
        },
        ...
    ],
    "period_hours": 24,
    "intervals": 24
}
```

---

## 💾 Export Dashboard

### Export to JSON

```python
monitor = PromptsMonitor()

file_path = monitor.export_dashboard(
    output_path="data/prompts_dashboard.json",
    period_hours=24
)

print(f"Dashboard exported to {file_path}")
```

### Export Format

```json
{
  "timestamp": "2026-03-03T00:00:00",
  "period_hours": 24,
  "validation": {
    "total_prompts": 100,
    "validated_prompts": 95,
    "failed_validations": 5,
    "validation_success_rate": 0.95,
    "injection_attempts_blocked": 3
  },
  "logging": {
    "total_logged": 100,
    "total_tokens": 150000,
    "total_cost_usd": 0.18,
    "avg_duration_ms": 250.5
  },
  "cache": {
    "cache_size": 42,
    "cache_hits": 85,
    "cache_misses": 15,
    "cache_hit_rate": 0.85
  },
  "by_agent": {...},
  "by_task": {...}
}
```

---

## 🧪 Тестирование

### Запуск тестов

```bash
pytest tests/monitoring/test_prompts_monitor.py -v
```

### Тесты покрывают:

- ✅ Инициализация монитора
- ✅ Получение дашборда
- ✅ Validation statistics
- ✅ Logging statistics
- ✅ Cache statistics
- ✅ Cost breakdown
- ✅ Performance trends
- ✅ Export dashboard
- ✅ Кэширование метрик

---

## 📊 REST API Reference

### GET /api/v1/prompts/monitoring/dashboard

Получить полный дашборд.

**Parameters:**
- `period_hours` (int, default: 24): Период в часах (1-720)

**Response:**
```json
{
  "timestamp": "2026-03-03T00:00:00",
  "period_hours": 24,
  "validation": {...},
  "logging": {...},
  "cache": {...},
  "by_agent": {...},
  "by_task": {...}
}
```

### GET /api/v1/prompts/monitoring/validation

Получить статистику валидации.

**Parameters:**
- `period_hours` (int, default: 24)

### GET /api/v1/prompts/monitoring/logging

Получить статистику логирования.

**Parameters:**
- `period_hours` (int, default: 24)

### GET /api/v1/prompts/monitoring/cache

Получить статистику кэша.

**Parameters:** None

### GET /api/v1/prompts/monitoring/costs

Получить разбивку затрат.

**Parameters:**
- `period_hours` (int, default: 24)

### GET /api/v1/prompts/monitoring/trends

Получить тренды производительности.

**Parameters:**
- `period_hours` (int, default: 24)
- `intervals` (int, default: 24)

### POST /api/v1/prompts/monitoring/export

Экспортировать дашборд.

**Parameters:**
- `output_path` (str, default: "data/prompts_dashboard.json")
- `period_hours` (int, default: 24)

**Response:**
```json
{
  "success": true,
  "file_path": "data/prompts_dashboard.json",
  "period_hours": 24
}
```

### GET /api/v1/prompts/monitoring/health

Проверить статус сервиса мониторинга.

**Response:**
```json
{
  "status": "healthy",
  "monitor_initialized": true,
  "metrics_available": true,
  "total_prompts": 100,
  "cache_hit_rate": 0.85
}
```

---

## 🎯 Best Practices

### 1. Используйте кэширование

```python
# ✅ Хорошо
dashboard = monitor.get_dashboard(period_hours=24)  # Кэшируется на 60 сек

# ❌ Плохо
while True:
    dashboard = monitor.get_dashboard(period_hours=24)  # No cache
```

### 2. Экспортируйте регулярно

```python
# Ежедневный экспорт
monitor.export_dashboard(
    f"data/dashboards/dashboard_{date}.json",
    period_hours=24
)
```

### 3. Мониторьте тренды

```python
# Почасовые тренды за 7 дней
trends = monitor.get_performance_trends(
    period_hours=168,  # 7 days
    intervals=168      # hourly
)
```

### 4. Анализируйте затраты

```python
# Прогноз месячных затрат
cost = monitor.get_cost_breakdown(period_hours=24)
projected = cost['projected_monthly_cost']
print(f"Monthly projection: ${projected:.2f}")
```

---

## 🐛 Troubleshooting

### Проблема: Нет данных в дашборде

**Решение:** Убедитесь, что промты логируются:
```python
from backend.agents.prompts import PromptLogger
logger = PromptLogger()
stats = logger.get_stats(days=1)
print(f"Total requests: {stats['total_requests']}")
```

### Проблема: Высокая стоимость

**Решение:** Проверьте разбивку по агентам:
```python
cost = monitor.get_cost_breakdown(period_hours=24)
print("By agent:", cost['by_agent'])
```

### Проблема: Низкий cache hit rate

**Решение:** Увеличьте размер кэша:
```python
from backend.agents.prompts import ContextCache
cache = ContextCache(max_size=5000)  # Default: 1000
```

---

## 📚 Дополнительные ресурсы

- [PromptLogger Guide](../prompts/prompt_logger.md)
- [ContextCache Guide](../prompts/context_cache.md)
- [API Reference](../../api/README.md)

---

**Monitoring service готов к использованию!** 📊
