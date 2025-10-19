# Celery Setup Guide

## Установка зависимостей

```powershell
.venv\Scripts\python.exe -m pip install celery==5.3.4 redis==5.0.1
```

## Предварительные требования

1. **Redis** должен быть запущен (порт 6379)
2. **RabbitMQ** должен быть запущен (порт 5672)

Проверка:

```powershell
# Redis
redis-cli ping  # Должен вернуть PONG

# RabbitMQ
curl http://localhost:15672  # Management UI
```

## Запуск Celery Worker

### Windows PowerShell

**Backtest Worker:**

```powershell
cd d:\bybit_strategy_tester_v2
.venv\Scripts\python.exe -m celery -A backend.celery_app worker -Q backtest -c 4 --loglevel=info -P solo
```

**Optimization Worker:**

```powershell
cd d:\bybit_strategy_tester_v2
.venv\Scripts\python.exe -m celery -A backend.celery_app worker -Q optimization -c 2 --loglevel=info -P solo
```

**All Queues Worker:**

```powershell
.venv\Scripts\python.exe -m celery -A backend.celery_app worker -Q backtest,optimization -c 4 --loglevel=info -P solo
```

> **Примечание:** На Windows используем `-P solo` (single-threaded) вместо дефолтного prefork.

### Параметры

- `-A backend.celery_app` — путь к Celery приложению
- `-Q backtest,optimization` — очереди для обработки
- `-c 4` — количество worker процессов (concurrency)
- `--loglevel=info` — уровень логирования
- `-P solo` — pool implementation для Windows

## Мониторинг

### Flower (Web UI для Celery)

```powershell
.venv\Scripts\python.exe -m pip install flower
.venv\Scripts\python.exe -m celery -A backend.celery_app flower
```

Откройте http://localhost:5555

### Командная строка

**Активные задачи:**

```powershell
.venv\Scripts\python.exe -m celery -A backend.celery_app inspect active
```

**Зарегистрированные задачи:**

```powershell
.venv\Scripts\python.exe -m celery -A backend.celery_app inspect registered
```

**Статистика:**

```powershell
.venv\Scripts\python.exe -m celery -A backend.celery_app inspect stats
```

## Тестирование

### Debug Task

```python
from backend.celery_app import debug_task

# Синхронный вызов
result = debug_task.apply_async()
print(result.get(timeout=10))
```

### Backtest Task

```python
from backend.tasks.backtest_tasks import run_backtest_task

result = run_backtest_task.apply_async(
    kwargs={
        "backtest_id": 1,
        "strategy_config": {"type": "ma_crossover", "fast_period": 10, "slow_period": 20},
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 10000.0
    }
)

# Проверить статус
print(result.status)

# Получить результат (блокирует)
print(result.get(timeout=600))
```

### Grid Search Task

```python
from backend.tasks.optimize_tasks import grid_search_task

result = grid_search_task.apply_async(
    kwargs={
        "optimization_id": 1,
        "strategy_config": {"type": "ma_crossover"},
        "param_space": {
            "fast_period": [5, 10, 15, 20],
            "slow_period": [20, 30, 40, 50]
        },
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "metric": "sharpe_ratio"
    }
)

# Ждать результат
best_params = result.get(timeout=3600)
print(best_params)
```

## Конфигурация

### .env файл

```properties
# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=bybit
RABBITMQ_PASS=bybitpassword

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery (опционально)
CELERY_BROKER_URL=amqp://bybit:bybitpassword@localhost:5672//
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### backend/core/config.py

Проверьте, что `broker_url` и `result_backend_url` корректно сформированы:

```python
@property
def broker_url(self) -> str:
    return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}//"

@property
def result_backend_url(self) -> str:
    return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
```

## Архитектура

```
┌─────────────┐
│  FastAPI    │  ──► Создаёт задачу backtest/optimize
│  Backend    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RabbitMQ   │  ──► Message Broker (очереди: backtest, optimization)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Celery    │  ──► Workers обрабатывают задачи
│   Workers   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Redis    │  ──► Хранит результаты задач
└─────────────┘
```

## Производственные рекомендации

1. **Supervisor / systemd** — запускать workers как сервис
2. **Flower** — мониторинг в реальном времени
3. **Retry policy** — автоматические повторы при сбоях
4. **Time limits** — защита от зависших задач
5. **Prefetch multiplier** — оптимизация для длинных задач
6. **Result expiration** — очистка старых результатов

## Troubleshooting

### Worker не стартует

```powershell
# Проверить подключение к RabbitMQ
telnet localhost 5672

# Проверить логи RabbitMQ
# C:\Users\<User>\AppData\Roaming\RabbitMQ\log\
```

### Задачи не выполняются

```powershell
# Проверить очереди в RabbitMQ
http://localhost:15672/#/queues

# Проверить зарегистрированные задачи
.venv\Scripts\python.exe -m celery -A backend.celery_app inspect registered
```

### Результаты не сохраняются

```powershell
# Проверить Redis
redis-cli
> KEYS *
> GET celery-task-meta-<task_id>
```

## Дополнительно

- [Celery Documentation](https://docs.celeryproject.org/)
- [RabbitMQ Management](http://localhost:15672/)
- [Flower Monitoring](http://localhost:5555/)
