# Быстрый старт - Bybit Strategy Tester

## Предварительные требования

Убедитесь, что установлены и запущены:

- ✅ Redis (сервис)
- ✅ RabbitMQ (сервис)
- ✅ PostgreSQL (сервис)
- ✅ Python 3.11+ с venv

---

## 1. Запуск инфраструктуры

### Автоматический запуск (рекомендуется)

```powershell
# Запустить Celery + FastAPI
.\start_infrastructure.ps1

# Проверить статус
.\start_infrastructure.ps1 -StatusOnly

# Остановить всё
.\start_infrastructure.ps1 -StopAll
```

### Ручной запуск

```powershell
# 1. Redis (если не запущен как сервис)
cd C:\Redis
Start-Process redis-server.exe -WindowStyle Hidden

# 2. RabbitMQ (проверить сервис)
Get-Service RabbitMQ

# 3. Celery Worker
cd D:\bybit_strategy_tester_v2
.venv\Scripts\celery.exe -A backend.celery_app worker -Q optimization,backtest -P solo --loglevel=info

# 4. FastAPI Server (в новом терминале)
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 2. Проверка работоспособности

### API Health Check

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

Ожидаемый ответ:

```json
{
  "status": "healthy",
  "service": "Bybit Strategy Tester API",
  "version": "1.0.0"
}
```

### Тесты API

```powershell
# Быстрый тест (без реальной оптимизации)
.venv\Scripts\python.exe test_optimization_api_quick.py

# Полный тест (требует данные и ~1-2 минуты)
.venv\Scripts\python.exe test_optimization_api.py
```

### Web UI

- **Swagger UI**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (guest:guest или bybit:bybitpassword)

---

## 3. Использование API

### Пример 1: Grid Search оптимизация (Python)

```python
import requests
import time

# Запуск оптимизации
response = requests.post("http://localhost:8000/api/v1/optimize/grid", json={
    "strategy_class": "SMAStrategy",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-12-31T23:59:59",
    "parameters": {
        "fast_period": {"min": 5, "max": 20, "step": 5},
        "slow_period": {"min": 20, "max": 50, "step": 10}
    },
    "initial_capital": 10000.0,
    "commission": 0.001,
    "metric": "total_return"
})

task_id = response.json()["task_id"]
print(f"Task ID: {task_id}")

# Отслеживание прогресса
while True:
    status = requests.get(f"http://localhost:8000/api/v1/optimize/{task_id}/status").json()

    if status["status"] == "SUCCESS":
        break
    elif status["status"] == "FAILURE":
        print(f"Error: {status['error']}")
        break

    if status.get("progress"):
        print(f"Progress: {status['progress']['percent']}%")

    time.sleep(2)

# Получение результата
result = requests.get(f"http://localhost:8000/api/v1/optimize/{task_id}/result").json()
print(f"Best params: {result['best_params']}")
print(f"Best score: {result['best_score']}")
```

### Пример 2: PowerShell

```powershell
# Запуск оптимизации
$body = @{
    strategy_class = "SMAStrategy"
    symbol = "BTCUSDT"
    timeframe = "1h"
    start_date = "2024-01-01T00:00:00"
    end_date = "2024-12-31T23:59:59"
    parameters = @{
        fast_period = @{ min = 5; max = 20; step = 5 }
        slow_period = @{ min = 20; max = 50; step = 10 }
    }
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/optimize/grid" -Method Post -Body $body -ContentType "application/json"
$taskId = $response.task_id

Write-Host "Task ID: $taskId"

# Проверка статуса
$status = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/optimize/$taskId/status"
Write-Host "Status: $($status.status)"

# Получение результата (когда SUCCESS)
$result = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/optimize/$taskId/result"
Write-Host "Best params: $($result.best_params | ConvertTo-Json)"
```

---

## 4. Типичные проблемы

### Redis не запущен

```powershell
# Запустить Redis вручную
cd C:\Redis
Start-Process redis-server.exe -WindowStyle Hidden
```

### RabbitMQ не запущен

```powershell
# Запустить сервис
Start-Service RabbitMQ

# Проверить статус
Get-Service RabbitMQ
```

### Celery не подключается к RabbitMQ

Проверьте credentials в `.env`:

```properties
RABBITMQ_USER=bybit
RABBITMQ_PASS=bybitpassword
```

### FastAPI порт занят

```powershell
# Найти процесс на порту 8000
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess

# Остановить процесс
Stop-Process -Id <PID> -Force
```

---

## 5. Документация

- **Фаза 1 (Инфраструктура)**: `docs/PHASE1_COMPLETED.md`
- **Фаза 1.5 (API)**: `docs/PHASE1.5_COMPLETED.md`
- **Swagger UI**: http://localhost:8000/docs (интерактивная документация)
- **OpenAPI Schema**: http://localhost:8000/openapi.json

---

## 6. Полезные команды

```powershell
# Проверить статус инфраструктуры
.\start_infrastructure.ps1 -StatusOnly

# Просмотр логов Celery (если запущен в фоне)
# Логи сохраняются в WindowStyle Hidden, используйте Flower для мониторинга

# Проверить Redis
redis-cli ping  # Должно вернуть PONG

# Проверить RabbitMQ
Get-Service RabbitMQ

# Проверить PostgreSQL
Get-Service postgresql-x64-*
```

---

## 7. Следующие шаги

После успешного запуска инфраструктуры:

1. **Загрузить данные** - используйте `/api/v1/data/load` для загрузки исторических данных
2. **Запустить бэктест** - протестируйте стратегию через `/api/v1/backtest`
3. **Оптимизация** - найдите лучшие параметры через `/api/v1/optimize/grid`
4. **Frontend** - установите и запустите Electron приложение (Фаза 2)

---

**Поддержка**: См. документацию в `docs/` или используйте Swagger UI для интерактивного тестирования API.
