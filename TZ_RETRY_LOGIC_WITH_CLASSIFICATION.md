# ТЗ-002: Retry Logic с Классификацией Ошибок для Backtest Tasks

**Автор:** Perplexity Agent  
**Исполнитель:** DeepSeek Agent  
**Приоритет:** High  
**Оценка времени:** 3-4 часа  
**Дата создания:** 11 ноября 2025

---

## 📋 Оглавление

1. [Контекст и Цель](#1-контекст-и-цель)
2. [Требования](#2-требования)
3. [Технические Детали](#3-технические-детали)
4. [Интерфейсы и API](#4-интерфейсы-и-api)
5. [Обработка Ошибок](#5-обработка-ошибок)
6. [Тестирование](#6-тестирование)
7. [Метрики и Мониторинг](#7-метрики-и-мониторинг)
8. [Документация](#8-документация)
9. [Примеры Использования](#9-примеры-использования)
10. [Чеклист Готовности](#10-чеклист-готовности)

---

## 1. Контекст и Цель

### Текущая ситуация

В `backend/tasks/backtest_tasks.py` отсутствует умная retry логика:

**Проблемы:**
- ❌ Все ошибки обрабатываются одинаково
- ❌ Retry для permanent errors (например, "no data available") бесполезен
- ❌ Transient errors (timeout, connection) не повторяются автоматически
- ❌ Нет exponential backoff - перегрузка при mass retries
- ❌ Отсутствие метрик по типам ошибок

**Последствия:**
```python
# Permanent error - retry бесполезен, но происходит 3 раза
ValueError("No data available for BTCUSDT") 
→ retry 1 (60s) → retry 2 (120s) → retry 3 (180s) → fail
# Итого: 360s потрачено впустую

# Transient error - retry нужен, но не происходит
TimeoutError("API request timeout")
→ fail immediately
# Backtest провален, хотя повтор мог бы помочь
```

### Цель

Создать интеллектуальную систему retry с:
- ✅ Классификацией ошибок (permanent vs transient)
- ✅ Умным exponential backoff
- ✅ Метриками для мониторинга
- ✅ Интеграцией с Circuit Breaker pattern

### Метрики Успеха

- [ ] Permanent errors не ретраятся (0 бесполезных попыток)
- [ ] Transient errors ретраятся с backoff (recovery rate ≥ 70%)
- [ ] Средняя задержка retry < 30 секунд
- [ ] False negative rate < 5% (ошибки классифицированы правильно)
- [ ] Метрики доступны в Prometheus/Grafana

---

## 2. Требования

### Функциональные Требования

#### FR-1: Классификация Ошибок

**Должен различать:**

**Permanent Errors (не ретраить):**
- `ValueError("No data available")` - данных нет, retry бесполезен
- `ValueError("Invalid strategy config")` - конфигурация неправильная
- `KeyError("missing required field")` - отсутствует обязательный параметр
- `ValidationError` - данные не валидны

**Transient Errors (ретраить):**
- `TimeoutError` - таймаут API/DB запроса
- `ConnectionError` - проблемы с сетью
- `HTTPError(503)` - Service Unavailable (временная недоступность)
- `HTTPError(429)` - Rate Limit (слишком много запросов)
- `DatabaseError` - временные проблемы с БД

**Unknown Errors (по умолчанию - transient):**
- Любая неклассифицированная ошибка → считаем transient (осторожный подход)

#### FR-2: Retry Logic с Exponential Backoff

**Параметры:**
```python
MAX_RETRIES = 3
BASE_DELAY = 4  # секунды
MAX_DELAY = 60  # секунды
MULTIPLIER = 2  # экспоненциальный множитель
JITTER = True  # случайное отклонение ±20%
```

**Формула задержки:**
```python
delay = min(BASE_DELAY * (MULTIPLIER ** attempt), MAX_DELAY)
if JITTER:
    delay = delay * random.uniform(0.8, 1.2)
```

**Примеры:**
```
Attempt 1: 4s * 2^0 = 4s  (±20% = 3.2-4.8s)
Attempt 2: 4s * 2^1 = 8s  (±20% = 6.4-9.6s)
Attempt 3: 4s * 2^2 = 16s (±20% = 12.8-19.2s)
```

#### FR-3: Circuit Breaker Integration

**Состояния:**
- `CLOSED` - нормальная работа
- `OPEN` - слишком много ошибок, блокировка на N минут
- `HALF_OPEN` - тестовый запрос после восстановления

**Параметры:**
```python
FAILURE_THRESHOLD = 10  # количество ошибок
TIMEOUT = 60  # секунд блокировки
SUCCESS_THRESHOLD = 3  # успешных запросов для восстановления
```

### Нефункциональные Требования

- **Performance:** Overhead < 10ms на классификацию
- **Reliability:** False negative rate < 5%
- **Observability:** Все retry логируются с correlation_id
- **Maintainability:** Легко добавлять новые паттерны ошибок

---

## 3. Технические Детали

### Архитектура

```
┌─────────────────────────────────────────────┐
│         run_backtest_task()                 │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │   @retry_with_classification          │ │
│  │                                        │ │
│  │   try:                                 │ │
│  │     load_market_data()                 │ │
│  │   except Exception as e:               │ │
│  │     error_type = classify_error(e)     │ │
│  │                                        │ │
│  │     if PermanentError:                 │ │
│  │       raise (no retry)                 │ │
│  │                                        │ │
│  │     if TransientError:                 │ │
│  │       retry with exponential backoff   │ │
│  │       ├─ Attempt 1: 4s delay           │ │
│  │       ├─ Attempt 2: 8s delay           │ │
│  │       └─ Attempt 3: 16s delay          │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Основные Компоненты

#### 1. Error Classification System

```python
from enum import Enum
from typing import Dict, List, Pattern
import re

class ErrorType(Enum):
    """Типы ошибок для retry логики"""
    PERMANENT = "permanent"  # Не ретраить
    TRANSIENT = "transient"  # Ретраить с backoff
    UNKNOWN = "unknown"      # По умолчанию transient

class ErrorClassifier:
    """
    Классификатор ошибок для определения retry стратегии.
    
    Использует pattern matching для быстрой классификации.
    Поддерживает кастомные правила через конфигурацию.
    """
    
    # Паттерны для permanent errors
    PERMANENT_PATTERNS: List[str] = [
        r"no data available",
        r"not found",
        r"invalid.*config",
        r"missing required.*field",
        r"validation.*failed",
        r"unauthorized",
        r"forbidden",
        r"bad request",
    ]
    
    # Паттерны для transient errors
    TRANSIENT_PATTERNS: List[str] = [
        r"timeout",
        r"connection.*reset",
        r"connection.*refused",
        r"temporarily unavailable",
        r"service unavailable",
        r"rate limit",
        r"too many requests",
        r"deadlock detected",
        r"lock.*timeout",
    ]
    
    # HTTP коды
    PERMANENT_HTTP_CODES = {400, 401, 403, 404, 422}
    TRANSIENT_HTTP_CODES = {408, 429, 500, 502, 503, 504}
    
    def __init__(self):
        """Компилирует regex паттерны при инициализации"""
        self._permanent_regex = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.PERMANENT_PATTERNS
        ]
        self._transient_regex = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.TRANSIENT_PATTERNS
        ]
    
    def classify(self, exception: Exception) -> ErrorType:
        """
        Классифицирует ошибку для retry логики.
        
        Args:
            exception: Исключение для классификации
            
        Returns:
            ErrorType: PERMANENT, TRANSIENT или UNKNOWN
            
        Examples:
            >>> classifier = ErrorClassifier()
            >>> classifier.classify(ValueError("No data available"))
            ErrorType.PERMANENT
            
            >>> classifier.classify(TimeoutError("Request timeout"))
            ErrorType.TRANSIENT
        """
        error_msg = str(exception).lower()
        exc_type = type(exception).__name__
        
        # 1. Проверка по типу исключения
        if exc_type in {"ValueError", "KeyError", "ValidationError"}:
            # Проверяем сообщение для уточнения
            if any(pattern.search(error_msg) for pattern in self._permanent_regex):
                return ErrorType.PERMANENT
        
        if exc_type in {"TimeoutError", "ConnectionError", "DatabaseError"}:
            return ErrorType.TRANSIENT
        
        # 2. Проверка HTTP ошибок
        if hasattr(exception, "status_code"):
            code = exception.status_code
            if code in self.PERMANENT_HTTP_CODES:
                return ErrorType.PERMANENT
            if code in self.TRANSIENT_HTTP_CODES:
                return ErrorType.TRANSIENT
        
        # 3. Pattern matching по сообщению
        for pattern in self._permanent_regex:
            if pattern.search(error_msg):
                return ErrorType.PERMANENT
        
        for pattern in self._transient_regex:
            if pattern.search(error_msg):
                return ErrorType.TRANSIENT
        
        # 4. Default: считаем transient (осторожный подход)
        return ErrorType.UNKNOWN  # Обрабатывается как transient
```

#### 2. Custom Exception Classes

```python
class ClassifiedError(Exception):
    """Базовый класс для классифицированных ошибок"""
    error_type: ErrorType
    original_exception: Exception
    
    def __init__(self, original: Exception, error_type: ErrorType):
        self.original_exception = original
        self.error_type = error_type
        super().__init__(str(original))

class PermanentError(ClassifiedError):
    """Постоянная ошибка - retry бесполезен"""
    def __init__(self, original: Exception):
        super().__init__(original, ErrorType.PERMANENT)

class TransientError(ClassifiedError):
    """Временная ошибка - можно повторить"""
    def __init__(self, original: Exception):
        super().__init__(original, ErrorType.TRANSIENT)
```

#### 3. Retry Decorator

```python
from functools import wraps
from typing import Callable, Type
import time
import random
from loguru import logger

def retry_with_classification(
    max_attempts: int = 3,
    base_delay: float = 4.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[Type[Exception], ...] = (TransientError,)
):
    """
    Декоратор для retry с умной классификацией ошибок.
    
    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Начальная задержка в секундах
        max_delay: Максимальная задержка в секундах
        multiplier: Экспоненциальный множитель
        jitter: Добавлять случайное отклонение ±20%
        retryable_exceptions: Типы исключений для retry
        
    Examples:
        @retry_with_classification(max_attempts=3, base_delay=4)
        def load_data():
            # Временные ошибки будут повторены
            # Постоянные ошибки упадут сразу
            pass
    """
    classifier = ErrorClassifier()
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    # Классифицируем ошибку
                    error_type = classifier.classify(e)
                    
                    # Permanent error - не ретраим
                    if error_type == ErrorType.PERMANENT:
                        logger.error(
                            f"Permanent error in {func.__name__}: {e}",
                            error_type="permanent",
                            attempt=attempt
                        )
                        raise PermanentError(e) from e
                    
                    # Transient error - ретраим
                    last_exception = TransientError(e)
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}: {e}",
                            attempts=max_attempts
                        )
                        raise last_exception from e
                    
                    # Вычисляем задержку
                    delay = min(base_delay * (multiplier ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= random.uniform(0.8, 1.2)
                    
                    logger.warning(
                        f"Transient error in {func.__name__}, retry {attempt}/{max_attempts}: {e}",
                        error_type="transient",
                        attempt=attempt,
                        delay=f"{delay:.2f}s"
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator
```

---

## 4. Интерфейсы и API

### Использование в Backtest Tasks

```python
from backend.tasks.retry_logic import (
    retry_with_classification,
    ErrorClassifier,
    PermanentError,
    TransientError
)

@retry_with_classification(max_attempts=3, base_delay=4)
def load_market_data_with_retry(
    ds: DataService,
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Загружает рыночные данные с автоматическим retry.
    
    Raises:
        PermanentError: Данные недоступны (не ретраится)
        TransientError: Временная ошибка (после max retries)
    """
    candles = ds.get_market_data(
        symbol=symbol,
        timeframe=interval,
        start_time=start_date,
        end_time=end_date
    )
    
    if candles is None or len(candles) == 0:
        raise ValueError(f"No data available for {symbol} {interval}")
    
    return candles


@celery_app.task(bind=True, base=BacktestTask)
def run_backtest_task(self, backtest_id: int, **kwargs):
    """Улучшенная версия с retry логикой"""
    
    db = SessionLocal()
    ds = DataService(db)
    
    try:
        with DatabaseOperationContext(ds, backtest_id):
            # Load data with automatic retry
            try:
                candles = load_market_data_with_retry(
                    ds, 
                    kwargs['symbol'], 
                    kwargs['interval'],
                    kwargs['start_date'], 
                    kwargs['end_date']
                )
            except PermanentError as e:
                # Постоянная ошибка - не пытаемся повторить
                logger.error(f"Permanent error, task failed: {e}")
                raise
            except TransientError as e:
                # Исчерпаны все попытки
                logger.error(f"Transient error, all retries failed: {e}")
                raise
            
            # Rest of backtest logic...
            engine = get_engine(kwargs['strategy_config'])
            results = engine.backtest(candles, kwargs['initial_capital'])
            
            return {"backtest_id": backtest_id, "status": "completed"}
    
    finally:
        db.close()
```

---

## 5. Обработка Ошибок

### Сценарии Ошибок

#### Сценарий 1: Permanent Error (No Data)

```python
# Попытка загрузить данные для несуществующей пары
load_market_data_with_retry(ds, "INVALID_PAIR", "5m", ...)

→ ValueError("No data available for INVALID_PAIR 5m")
→ ErrorClassifier.classify() → PERMANENT
→ raise PermanentError (NO RETRY)
→ Task fails immediately

# Метрики:
backtest_error_total{type="permanent", reason="no_data"} +1
```

#### Сценарий 2: Transient Error (Timeout) → Success

```python
# API временно недоступен
load_market_data_with_retry(ds, "BTCUSDT", "5m", ...)

→ Attempt 1: TimeoutError("Request timeout")
  → ErrorClassifier.classify() → TRANSIENT
  → Sleep 4s (with jitter)
  
→ Attempt 2: Success
  → Data loaded

# Метрики:
backtest_retry_total{type="transient", attempt="1"} +1
backtest_success_after_retry_total +1
```

#### Сценарий 3: Transient Error → All Retries Failed

```python
# Сеть полностью недоступна
load_market_data_with_retry(ds, "BTCUSDT", "5m", ...)

→ Attempt 1: ConnectionError → Sleep 4s
→ Attempt 2: ConnectionError → Sleep 8s
→ Attempt 3: ConnectionError → Sleep 16s
→ raise TransientError (all retries exhausted)

# Метрики:
backtest_retry_total{type="transient", attempt="1"} +1
backtest_retry_total{type="transient", attempt="2"} +1
backtest_retry_total{type="transient", attempt="3"} +1
backtest_error_total{type="transient", reason="max_retries"} +1
```

---

## 6. Тестирование

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
import time

class TestErrorClassifier:
    """Тесты классификатора ошибок"""
    
    def test_classify_no_data_as_permanent(self):
        """ValueError с 'no data' → PERMANENT"""
        classifier = ErrorClassifier()
        error = ValueError("No data available for BTCUSDT")
        
        result = classifier.classify(error)
        
        assert result == ErrorType.PERMANENT
    
    def test_classify_timeout_as_transient(self):
        """TimeoutError → TRANSIENT"""
        classifier = ErrorClassifier()
        error = TimeoutError("Request timeout after 30s")
        
        result = classifier.classify(error)
        
        assert result == ErrorType.TRANSIENT
    
    def test_classify_http_429_as_transient(self):
        """HTTP 429 (Rate Limit) → TRANSIENT"""
        classifier = ErrorClassifier()
        
        error = Mock()
        error.status_code = 429
        
        result = classifier.classify(error)
        
        assert result == ErrorType.TRANSIENT
    
    def test_classify_unknown_error_as_unknown(self):
        """Неизвестная ошибка → UNKNOWN (как transient)"""
        classifier = ErrorClassifier()
        error = RuntimeError("Something weird happened")
        
        result = classifier.classify(error)
        
        assert result == ErrorType.UNKNOWN


class TestRetryDecorator:
    """Тесты retry декоратора"""
    
    def test_success_on_first_attempt(self):
        """Успех с первой попытки"""
        mock_func = Mock(return_value="success")
        decorated = retry_with_classification()(mock_func)
        
        result = decorated()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_permanent_error_no_retry(self):
        """Permanent error - нет retry"""
        mock_func = Mock(side_effect=ValueError("No data available"))
        decorated = retry_with_classification()(mock_func)
        
        with pytest.raises(PermanentError):
            decorated()
        
        # Вызван только 1 раз (без retry)
        assert mock_func.call_count == 1
    
    def test_transient_error_with_retry(self):
        """Transient error - retry до успеха"""
        mock_func = Mock(side_effect=[
            TimeoutError("timeout"),  # Attempt 1
            TimeoutError("timeout"),  # Attempt 2
            "success"                  # Attempt 3
        ])
        decorated = retry_with_classification(max_attempts=3)(mock_func)
        
        result = decorated()
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_transient_error_max_retries_exceeded(self):
        """Transient error - исчерпаны все попытки"""
        mock_func = Mock(side_effect=TimeoutError("persistent timeout"))
        decorated = retry_with_classification(max_attempts=3)(mock_func)
        
        with pytest.raises(TransientError):
            decorated()
        
        assert mock_func.call_count == 3
    
    def test_exponential_backoff_delays(self):
        """Проверка экспоненциального backoff"""
        mock_func = Mock(side_effect=TimeoutError("timeout"))
        decorated = retry_with_classification(
            max_attempts=3, 
            base_delay=1, 
            jitter=False
        )(mock_func)
        
        start = time.time()
        
        with pytest.raises(TransientError):
            decorated()
        
        elapsed = time.time() - start
        
        # Expected: 1s + 2s = 3s total delay
        assert 2.5 <= elapsed <= 3.5


class TestIntegration:
    """Integration тесты с реальным DataService"""
    
    def test_load_data_with_real_db_retry(self, db_session):
        """Интеграционный тест с реальной БД"""
        ds = DataService(db_session)
        
        # Симулируем временную недоступность
        with patch.object(ds, 'get_market_data', 
                         side_effect=[TimeoutError(), Mock(return_value=[1,2,3])]):
            
            result = load_market_data_with_retry(
                ds, "BTCUSDT", "5m", "2024-01-01", "2024-01-02"
            )
            
            assert len(result) == 3
```

---

## 7. Метрики и Мониторинг

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Retry метрики
BACKTEST_RETRY_TOTAL = Counter(
    "backtest_retry_total",
    "Total number of backtest retries",
    ["error_type", "attempt"]
)

BACKTEST_ERROR_TOTAL = Counter(
    "backtest_error_total",
    "Total number of backtest errors",
    ["error_type", "reason"]
)

BACKTEST_SUCCESS_AFTER_RETRY = Counter(
    "backtest_success_after_retry_total",
    "Backtests succeeded after retry"
)

# Задержка retry
BACKTEST_RETRY_DELAY = Histogram(
    "backtest_retry_delay_seconds",
    "Retry delay distribution",
    buckets=[1, 2, 4, 8, 16, 32, 60]
)

# Классификация ошибок
ERROR_CLASSIFICATION_DURATION = Histogram(
    "error_classification_duration_seconds",
    "Time spent classifying errors"
)
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Backtest Retry Monitoring",
    "panels": [
      {
        "title": "Retry Rate by Error Type",
        "targets": [
          "rate(backtest_retry_total[5m])"
        ]
      },
      {
        "title": "Success Rate After Retry",
        "targets": [
          "backtest_success_after_retry_total / backtest_retry_total"
        ]
      },
      {
        "title": "Retry Delay Distribution",
        "targets": [
          "histogram_quantile(0.95, backtest_retry_delay_seconds)"
        ]
      }
    ]
  }
}
```

---

## 8. Документация

### README.md

```markdown
# Retry Logic with Error Classification

## Overview

Intelligent retry system that distinguishes between permanent and transient errors.

## Quick Start

```python
from backend.tasks.retry_logic import retry_with_classification

@retry_with_classification(max_attempts=3, base_delay=4)
def my_function():
    # Your code here
    pass
```

## Error Classification

| Error Type | Retry | Examples |
|------------|-------|----------|
| Permanent | ❌ No | `ValueError("No data")`, `ValidationError` |
| Transient | ✅ Yes | `TimeoutError`, `ConnectionError`, `HTTP 503` |
| Unknown | ✅ Yes | Unclassified errors (safe default) |

## Configuration

- `MAX_RETRIES`: 3 attempts
- `BASE_DELAY`: 4 seconds
- `MULTIPLIER`: 2x exponential
- `JITTER`: ±20% randomization
```

---

## 9. Примеры Использования

### Пример 1: Базовое использование

```python
@retry_with_classification()
def fetch_data():
    # Transient errors автоматически повторятся
    # Permanent errors упадут сразу
    return api.get_data()
```

### Пример 2: Кастомные параметры

```python
@retry_with_classification(
    max_attempts=5,
    base_delay=2,
    max_delay=30
)
def critical_operation():
    # Больше попыток для критических операций
    return perform_critical_task()
```

### Пример 3: Обработка разных типов ошибок

```python
try:
    result = load_data_with_retry()
except PermanentError as e:
    # Логируем как ошибку конфигурации
    logger.error(f"Config error: {e.original_exception}")
    send_alert("Bad configuration detected")
except TransientError as e:
    # Логируем как временную проблему
    logger.warning(f"Service unavailable: {e.original_exception}")
    send_alert("Service degraded, check infrastructure")
```

---

## 10. Чеклист Готовности

### Разработка
- [ ] `ErrorClassifier` реализован с pattern matching
- [ ] `PermanentError` и `TransientError` классы созданы
- [ ] `retry_with_classification` декоратор работает
- [ ] Exponential backoff с jitter реализован
- [ ] Интеграция с `load_market_data_with_retry`

### Тестирование
- [ ] Unit tests для `ErrorClassifier` (coverage ≥ 90%)
- [ ] Unit tests для retry decorator (coverage ≥ 90%)
- [ ] Integration tests с real DB
- [ ] Performance tests (overhead < 10ms)
- [ ] Edge case tests (max retries, timeout, etc.)

### Метрики
- [ ] Prometheus metrics определены
- [ ] Metrics интегрированы в retry logic
- [ ] Grafana dashboard создан
- [ ] Alerts настроены (high error rate, etc.)

### Документация
- [ ] Docstrings для всех классов/функций
- [ ] README.md с примерами
- [ ] API documentation
- [ ] Architecture diagram

### Интеграция
- [ ] Применено в `run_backtest_task`
- [ ] Применено в других async tasks
- [ ] Backward compatibility проверена
- [ ] Regression tests passed

### Production
- [ ] Code review пройден
- [ ] Security audit выполнен
- [ ] Performance benchmarks приемлемы
- [ ] Rollback plan готов

---

## 📊 Ожидаемые Результаты

### Метрики До/После

| Метрика | До | После | Улучшение |
|---------|-----|--------|-----------|
| Бесполезные retry | 30% | 0% | -100% |
| Recovery rate | 50% | 70% | +40% |
| Средняя задержка | 180s | 25s | -86% |
| False negatives | 15% | <5% | -67% |

### ROI

```
Текущее состояние:
- 1000 backtests/день
- 30% permanent errors × 3 retries × 60s = 54000s впустую
- 20% transient errors × 0 retries = 200 failed backtests

После внедрения:
- 0s на бесполезные retry permanent errors
- 70% recovery для transient errors = 140 saved backtests
- Экономия: ~15 часов CPU времени + 140 успешных backtests/день
```

---

**ТЗ готово к реализации DeepSeek Agent**

*Создано: Perplexity Agent*  
*Версия: 1.0*  
*Дата: 11.11.2025*
