# 🧪 AI Agent Test: Static SL/TP Exit Block Knowledge

> **Тест для AI-агентов:** DeepSeek, Qwen, Perplexity
> **Цель:** Проверить понимание параметров Static SL/TP, режимов Normal/Optimization,
> комбинации с фильтрами RSI/MACD.
> **Дата:** 2026-02-16

---

## 📋 ЧАСТЬ 1: STATIC SL/TP — Полное описание

### Общая информация

**Название блока:** `Static SL/TP`
**Тип:** Exit (`category: "exit"`, `type: "static_sltp"`)
**Иконка:** `shield-check`
**Особенность:** Config-only блок — НЕ генерирует exit сигналы. Движок (FallbackEngineV4) читает параметры и исполняет SL/TP на каждом баре.

### Как работает

1. Пользователь добавляет блок **Static SL/TP** на холст
2. Блок **НЕ подключается** к стратегии проводами — это standalone блок
3. Адаптер (`StrategyBuilderAdapter`) сохраняет параметры в `_value_cache`
4. Движок читает конфиг и на каждом баре проверяет:
    - Достигнута ли цена TP → закрыть с прибылью
    - Достигнута ли цена SL → закрыть с убытком
    - Если breakeven активирован → перенести SL

---

## 📊 Параметры блока

### Основные (всегда видны в панели)

| Параметр              | UI Label        | Тип    | Default           | Описание                                   | Optimizable |
| --------------------- | --------------- | ------ | ----------------- | ------------------------------------------ | ----------- |
| `take_profit_percent` | Take Profit (%) | number | **1.5**           | Процент прибыли от цены входа для закрытия | ✅ Да       |
| `stop_loss_percent`   | Stop Loss (%)   | number | **1.5**           | Процент убытка от цены входа для закрытия  | ✅ Да       |
| `sl_type`             | Тип стоп-лосса  | select | **average_price** | Тип расчёта SL                             | ❌ Нет      |

### sl_type — варианты

| Значение        | UI Label             | Описание                                          |
| --------------- | -------------------- | ------------------------------------------------- |
| `average_price` | От средней цены      | SL рассчитывается от средней цены входа (для DCA) |
| `last_order`    | От последнего ордера | SL рассчитывается от цены последнего ордера       |

### Advanced — дополнительные

| Параметр                       | UI Label                  | Тип      | Default   | Описание                                | Optimizable |
| ------------------------------ | ------------------------- | -------- | --------- | --------------------------------------- | ----------- |
| `close_only_in_profit`         | Close only in Profit      | checkbox | **false** | SL не срабатывает при убытке, только TP | ❌ Нет      |
| `activate_breakeven`           | Activate Breakeven?       | checkbox | **false** | Включить перенос SL в безубыток         | ❌ Нет      |
| `breakeven_activation_percent` | (%) to Activate Breakeven | number   | **0.5**   | % прибыли для активации безубытка       | ✅ Да       |
| `new_breakeven_sl_percent`     | New Breakeven SL (%)      | number   | **0.1**   | Новый SL после активации (% от entry)   | ✅ Да       |

---

## 🔧 Режимы работы

### Normal Mode (Скриншот 1)

В обычном режиме видны все поля:

- Take Profit (%)
- Stop Loss (%)
- Тип стоп-лосса (select)
- Advanced секция с чекбоксами и числовыми полями

### Optimization Mode (Скриншот 2)

При нажатии кнопки "Optimization":

- **Optimizable поля** (number с `optimizable: true`) показывают формат: `[min] → [max] / [step]`
- **Non-optimizable поля** (checkbox, select) скрываются
- Оптимизатор перебирает ВСЕ комбинации параметров в диапазонах

**Optimizable:** `take_profit_percent`, `stop_loss_percent`, `breakeven_activation_percent`, `new_breakeven_sl_percent`
**Non-optimizable:** `sl_type`, `close_only_in_profit`, `activate_breakeven`

---

## 🧠 Для AI-агентов: как формировать JSON блока

### Минимальная конфигурация

```json
{
    "id": "sltp_1",
    "type": "static_sltp",
    "category": "exit",
    "name": "Static SL/TP",
    "icon": "shield-check",
    "x": 600,
    "y": 450,
    "params": {
        "take_profit_percent": 1.5,
        "stop_loss_percent": 1.5
    }
}
```

### Полная конфигурация

```json
{
    "id": "sltp_1",
    "type": "static_sltp",
    "category": "exit",
    "name": "Static SL/TP",
    "icon": "shield-check",
    "x": 600,
    "y": 450,
    "params": {
        "take_profit_percent": 2.5,
        "stop_loss_percent": 1.2,
        "sl_type": "average_price",
        "close_only_in_profit": true,
        "activate_breakeven": true,
        "breakeven_activation_percent": 0.8,
        "new_breakeven_sl_percent": 0.15
    }
}
```

### ❗ Важно — подключение НЕ нужно

Static SL/TP — standalone блок. Он **НЕ подключается** к стратегии проводами.
Движок автоматически находит его по `type: "static_sltp"` в списке блоков.

---

## 📈 Комбинации с фильтрами

### RSI range + SL/TP

```
RSI (range 20-50 для long) → entry_long → Strategy
Static SL/TP (TP=2%, SL=1%) — standalone, без проводов
```

### MACD cross + SL/TP + Breakeven

```
MACD (cross signal) → entry_long → Strategy
Static SL/TP (TP=3%, SL=1.5%, breakeven at 1%) — standalone
```

### RSI + MACD combo + SL/TP

```
RSI (cross level 30/70) → entry_long → Strategy
MACD (cross signal) → entry_short → Strategy
Static SL/TP (TP=2%, SL=1%, close_only_in_profit) — standalone
```

---

## 🧪 Тестовые вопросы для AI-агентов

### Уровень 1 — Базовое понимание

1. **Q:** Какие default значения у Static SL/TP?
   **A:** TP=1.5%, SL=1.5%, sl_type=average_price, close_only_in_profit=false, breakeven=false, breakeven_activation=0.5%, new_sl=0.1%

2. **Q:** Нужно ли подключать Static SL/TP к стратегии проводами?
   **A:** НЕТ. Это standalone блок. Движок автоматически его находит.

3. **Q:** Генерирует ли Static SL/TP exit сигналы?
   **A:** НЕТ. Это config-only блок. exit всегда False. Движок обрабатывает SL/TP.

### Уровень 2 — Breakeven

4. **Q:** Как работает breakeven?
   **A:** Когда прибыль достигает `breakeven_activation_percent`, SL переносится на уровень entry + `new_breakeven_sl_percent`.

5. **Q:** Какие поля нужны для breakeven?
   **A:** `activate_breakeven=true`, `breakeven_activation_percent` (активация), `new_breakeven_sl_percent` (новый SL).

### Уровень 3 — Оптимизация

6. **Q:** Какие поля можно оптимизировать?
   **A:** `take_profit_percent`, `stop_loss_percent`, `breakeven_activation_percent`, `new_breakeven_sl_percent` — все number поля с `optimizable: true`.

7. **Q:** Что НЕ оптимизируется?
   **A:** `sl_type` (select), `close_only_in_profit` (checkbox), `activate_breakeven` (checkbox).

### Уровень 4 — Комбинации

8. **Q:** Влияет ли SL/TP на entry сигналы?
   **A:** НЕТ. Entry и exit полностью независимы. Изменение SL/TP не меняет количество entry сигналов.
