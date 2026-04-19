# ✅ Strategy Builder API Fix Complete

> **Дата**: 2026-01-29  
> **Статус**: ВСЕ ИСПРАВЛЕНО И ПРОТЕСТИРОВАНО

---

## 📋 Исправленные проблемы

### Исходная проблема

Кнопка **Validate** работала ✅, но **Save**, **Generate Code**, **Backtest** возвращали 404/405 ошибки.

---

## 🔧 Корневые причины и решения

### 1. ❌ Стратегия не существовала в БД (ROOT CAUSE #1)

**Симптом**: 404 "Strategy Builder strategy {id} not found"

**Причина**: Frontend использовал ID стратегии `4a9f2d78-b85d-4eb3-afb0-28a8c57b5396`, которая не существовала в базе данных.

**Решение**: Необходимо создавать стратегию через API (`POST /api/v1/strategy-builder/strategies`) перед использованием.

---

### 2. ❌ Формат соединений не совпадал (ROOT CAUSE #2)

**Симптом**: `KeyError: 'source'` в `strategy_builder_adapter.py`

**Причина**: Адаптер ожидал старый формат соединений:

```python
# Старый формат (ожидался)
conn["source"]["blockId"]
conn["target"]["blockId"]

# Новый формат (из API)
conn["source_block"]
conn["target_block"]
```

**Решение**: Добавлены helper методы для поддержки обоих форматов:

```python
def _get_connection_source_id(self, conn: dict) -> str:
    """Get source block ID supporting both formats"""
    if "source_block" in conn:
        return conn["source_block"]
    elif "source" in conn:
        src = conn["source"]
        return src["blockId"] if isinstance(src, dict) else src
    raise KeyError("Connection has no source_block or source")
```

**Файл**: `backend/backtesting/strategy_builder_adapter.py`

---

### 3. ❌ Топологическая сортировка включала non-block targets (ROOT CAUSE #3)

**Симптом**: `KeyError: 'main_strategy'` в `_build_execution_order()`

**Причина**: Некоторые connections указывали на `main_strategy` (не блок), и код пытался уменьшить `in_degree` для несуществующего ключа.

**Решение**: Добавлена проверка перед декрементом:

```python
if target_id in in_degree:
    in_degree[target_id] -= 1
```

**Файл**: `backend/backtesting/strategy_builder_adapter.py` (строка ~138)

---

### 4. ❌ SignalResult возвращал None вместо Series (ROOT CAUSE #4)

**Симптом**: `'NoneType' object has no attribute 'values'` в `engine.py` строка 1367

**Причина**: Адаптер возвращал `None` для `short_entries`/`short_exits` когда все значения False:

```python
# Было
short_entries=short_entries if short_entries.any() else None,
```

**Решение**: Всегда возвращать pd.Series:

```python
# Стало
short_entries=short_entries,
short_exits=short_exits,
```

**Файл**: `backend/backtesting/strategy_builder_adapter.py` (строки 428-430)

---

### 5. ❌ Использование несуществующего атрибута final_capital (ROOT CAUSE #5)

**Симптом**: `'PerformanceMetrics' object has no attribute 'final_capital'`

**Причина**: Код в `strategy_builder.py` обращался к `result.metrics.final_capital`, но `PerformanceMetrics` не имеет такого атрибута.

**Решение**: Использовать `result.final_equity` из `BacktestResult`:

```python
# Было
final_capital=result.metrics.final_capital if result.metrics else ...

# Стало
final_capital=result.final_equity if result.final_equity else ...
```

**Файл**: `backend/api/routers/strategy_builder.py` (строка 1471)

---

## ✅ Результат тестирования

После всех исправлений API тест прошел успешно:

```
=== Creating new Strategy Builder strategy ===
Create Status: 200 ✅

=== Testing GET ===
GET Status: 200 ✅

=== Testing PUT (update) ===
PUT Status: 200 ✅

=== Testing POST /generate-code ===
Generate Code Status: 200 ✅

=== Testing POST /backtest ===
Backtest Status: 200 ✅
Backtest completed!

🎉 All API tests completed!
```

---

## 📁 Измененные файлы

| Файл                                              | Изменения                                                                         |
| ------------------------------------------------- | --------------------------------------------------------------------------------- |
| `backend/backtesting/strategy_builder_adapter.py` | +4 helper методы, исправление топологической сортировки, исправление SignalResult |
| `backend/api/routers/strategy_builder.py`         | `result.final_equity` вместо `result.metrics.final_capital`                       |

---

## 🧪 Тестовый скрипт

Создан `test_create_strategy.py` для E2E тестирования всех эндпоинтов:

- Создает стратегию с RSI блоками
- Тестирует GET, PUT, generate-code, backtest
- Выводит статусы и результаты

---

## 📝 Уроки

1. **Форматы данных**: При интеграции frontend/backend проверять совпадение форматов JSON
2. **Атрибуты моделей**: Проверять существование атрибутов перед использованием
3. **None safety**: Всегда возвращать корректные типы (pd.Series вместо None)
4. **Топологическая сортировка**: Учитывать edge cases (connections на non-block targets)

---

## 🔗 Связанные документы

- `STRATEGY_BUILDER_API_ISSUES.md` - Исходная документация проблемы
- `STRATEGY_BUILDER_PHASE2_COMPLETE.md` - Документация Phase 2
- `STRATEGY_BUILDER_ARCHITECTURE.md` - Архитектура системы
