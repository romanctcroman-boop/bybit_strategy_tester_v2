# Шаг 1.2: Тесты для circuit breakers (Базовое состояние)

**Дата:** 2026-02-26  
**Статус:** ✅ Завершён  
**Задача:** P0-4 — Circuit breakers на MCP инструменты

---

## Цель

Создать полный набор тестов для circuit breakers MCP bridge до начала рефакторинга.

---

## Результаты тестов

### Сводка

```
======================== test session starts =========================
platform win32 -- Python 3.13.3, pytest-9.0.2
plugins: anyio, Faker, hypothesis, locust, asyncio, cov, timeout
collected 13 items

tests\backend\mcp\test_mcp_circuit_breakers.py ...F.F..F.FF.    [100%]

=================== 5 failed, 8 passed in 12.35s ===================
```

### Прошедшие тесты (8) ✅

| Тест | Статус | Описание |
|------|--------|----------|
| `test_single_breaker_initialization` | ✅ PASS | Проверка инициализации единого breaker |
| `test_call_tool_with_circuit_breaker` | ✅ PASS | Вызов инструмента через circuit breaker |
| `test_circuit_breaker_open_behavior` | ✅ PASS | Поведение при открытом circuit breaker |
| `test_no_retry_on_non_timeout_error` | ✅ PASS | Отсутствие retry для non-timeout ошибок |
| `test_isolated_circuit_breaker_failures` | ✅ PASS | Изоляция отказов (тест для будущей функциональности) |
| `test_breaker_categories` | ✅ PASS | Категоризация breaker (тест для будущей функциональности) |
| `test_per_tool_metrics` | ✅ PASS | Per-tool метрики (тест для будущей функциональности) |
| `test_concurrent_tool_calls` | ✅ PASS | Конкурентные вызовы инструментов |

### Провалившиеся тесты (5) ⚠️

**Ожидаемо!** Эти тесты для новой функциональности P0-4.

| Тест | Причина failure | Требуемое изменение |
|------|----------------|---------------------|
| `test_progressive_retry_on_timeout` | `assert call_count == 4` (фактически 1) | Исправить логику retry в call_tool() |
| `test_per_tool_breaker_registration` | `assert len(breakers) >= 3` (фактически 0) | Реализовать per-tool breakers |
| `test_metrics_recorded_on_tool_call` | `bridge.metrics` не существует | Добавить метрики в MCPFastAPIBridge |
| `test_real_circuit_breaker_behavior` | Breaker не открывается после 3 failures | Проверить логику CircuitBreakerManager |
| `test_circuit_breaker_overhead` | Overhead > 1s для 100 вызовов | Оптимизировать circuit breaker логику |

---

## Анализ текущего кода

### Файл: `backend/mcp/mcp_integration.py`

**Текущая реализация:**

```python
class MCPFastAPIBridge:
    def __init__(self) -> None:
        self._initialized = False
        self._tools: dict[str, McpToolInfo] = {}
        self._lock = asyncio.Lock()
        self.breaker_name = "mcp_server"  # ← ОДИН breaker на все инструменты!
        self.circuit_manager = None
```

**Проблема:**
- Один circuit breaker `mcp_server` для всех 79 инструментов
- Отказ одного инструмента влияет на все остальные

**Требуемое изменение:**

```python
class MCPFastAPIBridge:
    def __init__(self) -> None:
        self._initialized = False
        self._tools: dict[str, McpToolInfo] = {}
        self._lock = asyncio.Lock()
        
        # Per-tool circuit breakers
        self.circuit_breakers: dict[str, Any] = {}
        self.breaker_categories: dict[str, str] = {}  # tool_name → category
        
        # Category thresholds
        self.breaker_thresholds = {
            "high": 3,    # Agent-to-Agent, Backtest
            "medium": 5,  # Strategy Builder, System, Memory
            "low": 10,    # Indicators, Risk, Files, Strategies
        }
        
        self.circuit_manager = None
```

---

## План реализации (Шаги 2.1-2.5)

### Шаг 2.1: Создать реестр circuit breakers

**Файл:** `backend/mcp/mcp_integration.py`

**Изменения:**
1. Добавить `self.circuit_breakers: dict[str, CircuitBreaker]`
2. Добавить `self.breaker_categories: dict[str, str]`
3. Создать метод `_register_per_tool_breakers()`

### Шаг 2.2: Категоризация инструментов

**Файл:** `backend/mcp/mcp_integration.py`

**Изменения:**
1. Создать словарь категорий инструментов
2. Назначить категории для каждого инструмента
3. Разные пороги для разных категорий

### Шаг 2.3: Модифицировать call_tool()

**Файл:** `backend/mcp/mcp_integration.py`

**Изменения:**
1. Использовать per-tool breaker вместо общего
2. Логирование с именем инструмента
3. Метрики per-tool

### Шаг 2.4: Добавить метрики

**Файл:** `backend/mcp/mcp_integration.py`

**Изменения:**
1. Добавить `self.tool_metrics: dict[str, dict]`
2. Запись метрик для каждого вызова
3. API для получения метрик

### Шаг 2.5: Обновить документацию

**Файл:** `docs/mcp/CIRCUIT_BREAKERS.md`

**Содержание:**
1. Архитектура per-tool circuit breakers
2. Категории инструментов
3. Пороги срабатывания
4. API для управления

---

## Критерии приёмки

После реализации все тесты должны проходить:

- [ ] `test_per_tool_breaker_registration` — PASS
- [ ] `test_isolated_circuit_breaker_failures` — PASS
- [ ] `test_metrics_recorded_on_tool_call` — PASS
- [ ] `test_circuit_breaker_overhead` — PASS (< 1s для 100 вызовов)
- [ ] `test_progressive_retry_on_timeout` — PASS

---

## Следующий шаг

➡️ **Шаг 2.1: Создать реестр circuit breakers**

**Файл:** `backend/mcp/mcp_integration.py`  
**Оценка усилий:** 2 часа  
**Ожидаемый результат:** Каждый инструмент имеет свой circuit breaker

---

*Отчёт о шаге 1.2 завершён: 2026-02-26*
