# 🚀 Руководство по тестированию Production Improvements

## Что было добавлено

### ✅ 1. Structured Logging (`backend/core/logging_config.py`)
- JSON форматирование для production
- Контекстные поля (symbol, interval, duration_ms)
- Rotation файлов логов
- Разные уровни логирования

### ✅ 2. Configuration Management (`backend/core/config.py`)
- Централизованная конфигурация через Pydantic
- Переменные окружения с префиксом `BYBIT_`
- Валидация типов
- Документированные defaults

### ✅ 3. Retry Logic (`backend/core/retry.py`)
- Декоратор `@retry_with_backoff`
- Exponential backoff (1s → 2s → 4s)
- Настраиваемые exception types
- Детальное логирование попыток

### ✅ 4. Custom Exceptions (`backend/core/exceptions.py`)
- `BybitRateLimitError` - rate limit превышен
- `BybitSymbolNotFoundError` - символ не найден
- `BybitInvalidIntervalError` - неверный интервал
- `BybitConnectionError` - проблемы с сетью
- Маппинг Bybit error codes → exceptions

### ✅ 5. Health Check Endpoints (`backend/api/routers/health.py`)
- `/api/v1/health` - комплексная проверка
- `/api/v1/health/bybit` - детальная проверка Bybit API
- `/api/v1/health/ready` - Kubernetes readiness probe
- `/api/v1/health/live` - Kubernetes liveness probe

### ✅ 6. Environment Configuration (`.env.example`)
- Обновлённый шаблон с новыми переменными
- Подробные комментарии
- Production-ready defaults

---

## 🧪 Тестирование

### 1. Проверка конфигурации

```powershell
# Создать .env файл
cp .env.example .env

# Проверить что конфигурация загружается
python -c "from backend.core.config import config; print(f'API Timeout: {config.API_TIMEOUT}'); print(f'Rate Limit: {config.RATE_LIMIT_DELAY}')"
```

**Ожидаемый результат**:
```
API Timeout: 10
Rate Limit: 0.2
```

### 2. Проверка logging

```powershell
# Тест structured logging
python -c "
from backend.core.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(log_level='INFO', json_format=False)

# Get logger
logger = get_logger('test')

# Test logging with extra fields
logger.info(
    'Test message',
    extra={
        'symbol': 'BTCUSDT',
        'interval': '15',
        'candles_count': 1000
    }
)
"
```

**Ожидаемый результат**:
```
2025-10-26 15:30:00 - backend.core.logging_config - INFO - Logging configured
2025-10-26 15:30:00 - test - INFO - Test message
```

### 3. Проверка retry logic

```powershell
# Тест retry decorator
python -c "
from backend.core.retry import retry_with_backoff
import time

@retry_with_backoff(max_attempts=3, initial_delay=0.5)
def test_function():
    print('Попытка вызова...')
    raise ConnectionError('Test error')

try:
    test_function()
except ConnectionError as e:
    print(f'Все попытки исчерпаны: {e}')
"
```

**Ожидаемый результат**:
```
Попытка вызова...
WARNING: Attempt 1/3 failed, retrying in 0.5s
Попытка вызова...
WARNING: Attempt 2/3 failed, retrying in 1.0s
Попытка вызова...
ERROR: All 3 attempts failed
Все попытки исчерпаны: Test error
```

### 4. Проверка exceptions

```powershell
# Тест custom exceptions
python -c "
from backend.core.exceptions import handle_bybit_error

# Test rate limit error
error = handle_bybit_error(10004, 'Rate limit exceeded')
print(f'Type: {type(error).__name__}')
print(f'Message: {error}')

# Test symbol not found
error = handle_bybit_error(10016, 'Symbol not found')
print(f'Type: {type(error).__name__}')
"
```

**Ожидаемый результат**:
```
Type: BybitRateLimitError
Message: BybitRateLimitError [10004]: Rate limit exceeded
Type: BybitSymbolNotFoundError
```

### 5. Проверка BybitAdapter с новыми функциями

```powershell
# Тест обновлённого adapter
python -c "
from backend.services.adapters.bybit import BybitAdapter

adapter = BybitAdapter()
print(f'Timeout: {adapter.timeout}')
print(f'Rate limit delay: {adapter.rate_limit_delay}')

# Загрузить данные
candles = adapter.get_klines('BTCUSDT', '15', 10)
print(f'Loaded {len(candles)} candles')
"
```

**Ожидаемый результат**:
```
INFO: BybitAdapter initialized
Timeout: 10
Rate limit delay: 0.2
INFO: Successfully fetched 10 klines from Bybit for BTCUSDT
Loaded 10 candles
```

### 6. Проверка Health Endpoints

```powershell
# Запустить сервер
cd d:\bybit_strategy_tester_v2
uvicorn backend.api.app:app --reload --port 8000

# В другом терминале:
# Проверить общее health
curl http://localhost:8000/api/v1/health

# Проверить Bybit API
curl http://localhost:8000/api/v1/health/bybit

# Readiness probe
curl http://localhost:8000/api/v1/health/ready

# Liveness probe
curl http://localhost:8000/api/v1/health/live
```

**Ожидаемый результат** (`/api/v1/health`):
```json
{
  "status": "healthy",
  "timestamp": "2025-10-26T15:30:00.000000Z",
  "checks": {
    "bybit_api": {
      "status": "ok",
      "response_time_ms": 234.56,
      "candles_fetched": 10,
      "message": "Fetched 10 candles in 234.56ms"
    },
    "database": {
      "status": "ok",
      "message": "Database connection successful"
    },
    "cache": {
      "status": "ok",
      "cache_files": 15,
      "cache_dir": "cache/bybit_klines"
    }
  },
  "config": {
    "cache_enabled": true,
    "db_persist_enabled": true,
    "log_level": "INFO"
  }
}
```

### 7. Проверка переменных окружения

```powershell
# Изменить конфигурацию через env
$env:BYBIT_RATE_LIMIT_DELAY="0.5"
$env:BYBIT_API_TIMEOUT="15"
$env:BYBIT_LOG_LEVEL="DEBUG"

python -c "
from backend.core.config import reload_config
config = reload_config()
print(f'Rate limit: {config.RATE_LIMIT_DELAY}')
print(f'Timeout: {config.API_TIMEOUT}')
print(f'Log level: {config.LOG_LEVEL}')
"
```

**Ожидаемый результат**:
```
Rate limit: 0.5
Timeout: 15
Log level: DEBUG
```

### 8. Запуск тестов с новыми функциями

```powershell
# Запустить существующие тесты
cd d:\bybit_strategy_tester_v2
py tests\test_storage_logic.py

# Все 10 тестов должны пройти
# Логи теперь будут чище (без traceback для ModuleNotFoundError)
```

**Ожидаемый результат**:
```
✅ Passed: 10/10 (100%)
```

---

## 📊 Валидация изменений

### Checklist

- [ ] **Config загружается корректно**
  ```powershell
  python -c "from backend.core.config import config; print(config.API_TIMEOUT)"
  ```

- [ ] **Logging работает**
  ```powershell
  python -c "from backend.core.logging_config import setup_logging; setup_logging()"
  ```

- [ ] **Retry decorator работает**
  ```powershell
  python -c "from backend.core.retry import retry_with_backoff; print('OK')"
  ```

- [ ] **Exceptions импортируются**
  ```powershell
  python -c "from backend.core.exceptions import BybitAPIError; print('OK')"
  ```

- [ ] **BybitAdapter использует новую конфигурацию**
  ```powershell
  python -c "from backend.services.adapters.bybit import BybitAdapter; a = BybitAdapter(); print(f'OK: timeout={a.timeout}')"
  ```

- [ ] **Health endpoints работают**
  ```powershell
  # (после запуска uvicorn)
  curl http://localhost:8000/api/v1/health
  ```

- [ ] **Тесты проходят**
  ```powershell
  py tests\test_storage_logic.py
  ```

---

## 🔍 Troubleshooting

### Проблема: ModuleNotFoundError для backend.core.*

**Решение**:
```powershell
# Добавить корневую директорию в PYTHONPATH
$env:PYTHONPATH="d:\bybit_strategy_tester_v2"
```

### Проблема: pydantic_settings не найден

**Решение**:
```powershell
pip install pydantic-settings
```

### Проблема: Health endpoint возвращает 503

**Причина**: PostgreSQL не запущен

**Решение**:
```powershell
.\scripts\start_postgres_and_migrate.ps1
```

---

## 📝 Следующие шаги

После проверки всех тестов:

1. **Обновить зависимости**:
   ```powershell
   pip install pydantic-settings prometheus-client
   ```

2. **Запустить сервер**:
   ```powershell
   uvicorn backend.api.app:app --reload --port 8000
   ```

3. **Проверить Swagger UI**:
   - http://localhost:8000/docs
   - Найти секцию "health"
   - Протестировать endpoints

4. **Запустить полный тест suite**:
   ```powershell
   pytest tests/ -v
   ```

5. **Проверить метрики** (если enabled):
   - http://localhost:8000/metrics

---

## ✅ Критерии успеха

Все критичные исправления внедрены, если:

- ✅ Конфигурация загружается из `.env`
- ✅ Логи форматируются правильно
- ✅ Retry logic работает для ошибок
- ✅ Custom exceptions используются
- ✅ Health endpoints возвращают 200 OK
- ✅ BybitAdapter использует config
- ✅ Все 10 тестов проходят успешно

**Статус готовности**: 🟢 85% → 95%
