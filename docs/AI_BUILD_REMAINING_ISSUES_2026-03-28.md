# AI Build Pipeline — Оставшиеся проблемы и рекомендации

**Дата:** 2026-03-28
**Статус:** Code Review после сессии отладки
**Файлы:** `builder_workflow.py`, `builder_optimizer.py`, `filters.py`

---

## 📋 Сводка

| #   | Проблема                                 | Приоритет | Статус         | Влияние                                |
| --- | ---------------------------------------- | --------- | -------------- | -------------------------------------- |
| 1   | `min_trades=0` по умолчанию              | 🔴 HIGH   | Не исправлено  | Optuna выбирает дегенеративные решения |
| 2   | RSI Config Conflict в auto-fix           | 🟡 MEDIUM | Не исправлено  | Регрессия на итерации 3                |
| 3   | Fallback использует unfiltered results   | 🟢 LOW    | Не исправлено  | Маскирует реальную проблему            |
| 4   | Auto-fix проверяет до применения         | 🟢 LOW    | OK (by design) | Работает, но неинтуитивно              |
| 5   | Auto-fix не триггерит immediate backtest | 🟢 LOW    | OK (by design) | Незначительно                          |

---

## 🔴 Проблема #1: `min_trades=0` по умолчанию

### Описание

Когда пользователь не добавляет constraint `total_trades >= N` в Evaluation Panel, optimizer использует `min_trades=0`, что позволяет Optuna выбирать решения с 2–4 trades.

### Файл и строка

`backend/agents/workflows/builder_workflow.py`, строки 2585–2590

### Текущий код

```python
_min_trades_constraint = next(
    (int(c.get("value", 0)) for c in _eval_constraints
     if c.get("metric") == "total_trades" and c.get("operator") in (">=", ">")),
    0,  # ← ПРОБЛЕМА: default = 0
)
```

### Проблема

При `min_trades=0` функция `passes_filters()` не фильтрует по количеству trades. Optuna может найти конфигурацию с 4 trades и Sharpe=0.01 (артефакт малой выборки) и выбрать её как "лучшую".

### Воспроизведение

1. Создать стратегию RSI + SuperTrend
2. Запустить AI Build **без** constraint `total_trades >= N`
3. Наблюдать: optimizer выбирает 4-trade решение

### Рекомендуемое исправление

```python
# Используем тот же порог что и для _MIN_TRADES_FOR_SWEEP
_MIN_TRADES_FOR_OPTIMIZER = 15

_min_trades_constraint = next(
    (int(c.get("value", 0)) for c in _eval_constraints
     if c.get("metric") == "total_trades" and c.get("operator") in (">=", ">")),
    _MIN_TRADES_FOR_OPTIMIZER,  # ← ИСПРАВЛЕНИЕ: default = 15
)
```

### Альтернатива

Если нужно сохранить backward compatibility, можно добавить warning:

```python
if _min_trades_constraint == 0:
    logger.warning(
        "[BuilderWorkflow] ⚠️ No min_trades constraint set — optimizer may select "
        "degenerate solutions. Add 'total_trades >= 15' to Evaluation Panel."
    )
```

---

## 🟡 Проблема #2: RSI Config Conflict в auto-fix

### Описание

Auto-fix расширяет `cross_long_level` до 40, но не проверяет значение `long_rsi_more`. Если `long_rsi_more > cross_long_level`, возникает Config Conflict → 0 сигналов.

### Файл и строка

`backend/agents/workflows/builder_workflow.py`, строки 1915–1923

### Текущий код

```python
if _cross_l < 35:
    rsi_level_fix["cross_long_level"] = 40.0
if _cross_s > 65:
    rsi_level_fix["cross_short_level"] = 60.0
```

### Проблема

Код не учитывает `long_rsi_more`. Если `long_rsi_more=42` (установлено ранее или агентом), то после auto-fix:

- `cross_long_level=40`
- `long_rsi_more=42`
- **Config Conflict:** `cross_long_level < long_rsi_more` → RSI cross событие происходит при RSI≈40, но range condition требует RSI≥42 → никогда не совпадают → 0 сигналов

### Воспроизведение (Run #6, итерация 3)

1. Итерация 1: 4 trades
2. Auto-fix: `cross_long_level=40`
3. Optuna предлагает `long_rsi_more=42` (или оставляет default)
4. Итерация 3: 3 trades (регрессия)

### Рекомендуемое исправление

```python
if _cross_l < 35:
    rsi_level_fix["cross_long_level"] = 40.0
    # Проверить Config Conflict с long_rsi_more
    _long_more = float(_bparams.get("long_rsi_more", 30))
    if 40.0 < _long_more:
        # cross_long_level должен быть >= long_rsi_more
        rsi_level_fix["long_rsi_more"] = 35.0  # или cross_long_level - 5
        logger.info(
            f"[BuilderWorkflow] Auto-fix: also setting long_rsi_more=35 "
            f"to avoid Config Conflict (was {_long_more})"
        )

if _cross_s > 65:
    rsi_level_fix["cross_short_level"] = 60.0
    # Аналогично для short
    _short_less = float(_bparams.get("short_rsi_less", 70))
    if 60.0 > _short_less:
        rsi_level_fix["short_rsi_less"] = 65.0
```

### Альтернатива

Запретить optimizer менять `long_rsi_more` / `short_rsi_less` когда `use_cross_level=True`:

```python
# В _suggest_param_ranges или param_specs filtering
if block.use_cross_level:
    exclude_params = ["long_rsi_more", "long_rsi_less", "short_rsi_more", "short_rsi_less"]
```

---

## 🟢 Проблема #3: Fallback использует unfiltered results

### Описание

Когда `min_trades` filter убирает все результаты, fallback возвращает `all_trial_results` которые содержат решения с любым количеством trades.

### Файл и строка

`backend/optimization/builder_optimizer.py`, строки 3480–3490

### Текущий код

```python
# Fallback: if min_trades filter pruned all results, use all_trial_results instead
if not top_results and all_trial_results:
    logger.warning(
        f"⚠️ Optuna: all {len(completed_trials)} completed trials were re-run but "
        f"produced no results (min_trades filter likely removed them). "
        f"Falling back to {len(all_trial_results)} stored trial results."
    )
    all_trial_results.sort(key=lambda r: r["score"], reverse=True)
    top_results = all_trial_results[:top_n]
    fallback_used = True
```

### Проблема

Fallback может вернуть 4-trade решение когда пользователь явно указал `min_trades >= 30`. Это нарушает constraint и маскирует реальную проблему (стратегия структурно не генерирует достаточно сигналов).

### Рекомендуемое исправление

```python
if not top_results and all_trial_results:
    logger.warning(
        f"⚠️ Optuna: all {len(completed_trials)} trials filtered out by min_trades={config_params.get('min_trades')}. "
        f"Strategy may be structurally unable to generate enough signals."
    )
    # Вернуть лучший результат с пометкой, а не молча игнорировать constraint
    all_trial_results.sort(key=lambda r: r["score"], reverse=True)
    top_results = all_trial_results[:top_n]
    fallback_used = True

    # Добавить флаг для UI
    for r in top_results:
        r["_warning"] = f"Below min_trades threshold ({config_params.get('min_trades')})"
```

Или более строгий вариант — не использовать fallback вообще:

```python
if not top_results:
    return {
        "status": "no_valid_results",
        "reason": f"All {len(all_trial_results)} trials had < {config_params.get('min_trades')} trades",
        "suggestion": "Lower min_trades constraint or change strategy structure",
        "best_invalid_result": all_trial_results[0] if all_trial_results else None,
    }
```

---

## 🟢 Проблема #4: Auto-fix проверяет `_has_st_change_mode` до применения фиксов

### Описание

Логика `_has_st_change_mode` проверяет **текущее** состояние блоков, но затем в том же цикле SuperTrend фиксируется. Выглядит как race condition, но на самом деле работает правильно.

### Файл и строка

`backend/agents/workflows/builder_workflow.py`, строки 1893–1897

### Код

```python
# Проверка ПЕРЕД циклом фиксов
_has_st_change_mode = any(
    ((_b.get("type") or "").lower() == "supertrend"
     and (_b.get("params") or {}).get("generate_on_trend_change", False))
    for _b in blocks_added
)

# Цикл фиксов
for _b in blocks_added:
    if _btype == "supertrend" and _bparams.get("generate_on_trend_change", False):
        auto_fixes.append(...)  # SuperTrend → False

    if _btype == "rsi" and _bparams.get("use_cross_level", False):
        if _has_st_change_mode:  # ← Использует значение ДО фикса SuperTrend
            # RSI остаётся trigger, только расширяем уровни
```

### Почему это работает

Логика правильная по намерению:

- Если SuperTrend **был** в trigger mode (`generate_on_trend_change=True`), мы его фиксим в filter mode **И** оставляем RSI как trigger
- Проверка `_has_st_change_mode` определяет **исходную** конфигурацию, а не после фиксов

### Рекомендация

Код работает, но добавить комментарий для ясности:

```python
# IMPORTANT: This checks the ORIGINAL state of SuperTrend blocks.
# If any SuperTrend has generate_on_trend_change=True, we will fix it to False
# (making it a continuous filter) AND keep RSI in cross-trigger mode.
# This prevents the flooding problem (both continuous → 200+ trades).
_has_st_change_mode = any(...)
```

---

## 🟢 Проблема #5: Auto-fix не триггерит immediate backtest

### Описание

`_suggest_adjustments()` возвращает `auto_fixes`, но они применяются через обычный flow (log → apply → save snapshot → backtest). Между решением применить фикс и его применением проходит несколько операций.

### Влияние

Незначительное — всё работает, просто занимает больше времени (лишний snapshot, лишние логи).

### Рекомендация

Оставить как есть — overhead минимален, а единообразный flow проще поддерживать.

---

## 📊 Приоритизация исправлений

### Немедленно (перед следующим AI Build тестом)

1. **Проблема #1:** Изменить default `min_trades` с 0 на 15
    - Время: 2 минуты
    - Риск: Низкий
    - Тест: Запустить AI Build без constraints

### В ближайшее время (до следующего релиза)

2. **Проблема #2:** Добавить проверку Config Conflict в auto-fix
    - Время: 15 минут
    - Риск: Средний (может сломать существующие стратегии если установить слишком низкий long_rsi_more)
    - Тест: Unit test на RSI auto-fix + Config Conflict

### При рефакторинге

3. **Проблема #3:** Улучшить fallback логику в optimizer
4. **Проблема #4:** Добавить комментарии

---

## 🧪 Тесты для валидации исправлений

### Тест #1: min_trades default

```python
def test_min_trades_default_is_15():
    """When no constraints provided, min_trades should default to 15."""
    config = BuilderWorkflowConfig(
        name="test",
        symbol="BTCUSDT",
        timeframe="30",
        evaluation_config={},  # No constraints
    )
    workflow = BuilderWorkflow(config)
    # Extract min_trades from _run_optimizer_for_ranges
    assert workflow._get_min_trades_constraint() == 15
```

### Тест #2: RSI Config Conflict auto-fix

```python
def test_rsi_autofix_prevents_config_conflict():
    """Auto-fix should not create cross_long_level < long_rsi_more."""
    blocks = [
        {"id": "rsi1", "type": "rsi", "params": {
            "use_cross_level": True,
            "cross_long_level": 25,
            "long_rsi_more": 42,  # Conflict: 25 < 42
        }},
        {"id": "st1", "type": "supertrend", "params": {
            "generate_on_trend_change": True,
        }},
    ]
    metrics = {"total_trades": 4}

    fixes = workflow._suggest_adjustments(..., blocks, metrics)

    # After auto-fix, should have no Config Conflict
    rsi_fix = next(f for f in fixes if f["block_id"] == "rsi1")
    new_cross_l = rsi_fix["params"].get("cross_long_level", 25)
    new_long_more = rsi_fix["params"].get("long_rsi_more", 42)

    assert new_cross_l >= new_long_more, "Auto-fix created Config Conflict"
```

### Тест #3: Fallback warning

```python
def test_optimizer_fallback_includes_warning():
    """When fallback is used, results should have warning flag."""
    result = run_builder_optuna_search(
        base_graph=graph_with_sparse_signals,
        config_params={"min_trades": 50},  # High threshold
        ...
    )

    if result.get("fallback_used"):
        for r in result["top_results"]:
            assert "_warning" in r, "Fallback results should have warning"
```

---

## 📁 Файлы для изменения

| Файл                                            | Изменения       |
| ----------------------------------------------- | --------------- |
| `backend/agents/workflows/builder_workflow.py`  | Проблемы #1, #2 |
| `backend/optimization/builder_optimizer.py`     | Проблема #3     |
| `tests/backend/agents/test_builder_workflow.py` | Новые тесты     |

---

_Документ создан: 2026-03-28_
_Автор: GitHub Copilot (Code Review)_
