# 🧪 AI Agent Test: RSI & MACD Filter Knowledge

> **Тест для AI-агентов:** DeepSeek, Qwen, Perplexity
> **Цель:** Проверить понимание каждого параметра фильтров RSI и MACD,
> их использования и настройки оптимизации.
> **Дата:** 2026-02-15

---

## 📋 ЧАСТЬ 1: RSI ФИЛЬТР — Полное описание параметров

### Общая информация

**Название блока:** `RSI - [IN RANGE FILTER OR CROSS SIGNAL]`
**Тип:** Индикатор (`indicator_type == "rsi"`)
**Выходные порты:** `value` (серия RSI 0-100), `long` (булевый сигнал), `short` (булевый сигнал)

### Режимы работы RSI

RSI поддерживает **3 основных режима**, которые комбинируются через **AND** логику:

| #   | Режим                    | Активация                                               | Описание                                                  |
| --- | ------------------------ | ------------------------------------------------------- | --------------------------------------------------------- |
| 1   | **Range Filter**         | `use_long_range=true` / `use_short_range=true`          | Непрерывное условие — True пока RSI в диапазоне           |
| 2   | **Cross Level**          | `use_cross_level=true`                                  | Событийный сигнал — True только на баре пересечения       |
| 3   | **Legacy** (автофоллбэк) | Ни один режим не включён + есть `overbought`/`oversold` | Классический RSI: < oversold → long, > overbought → short |
| 4   | **Passthrough**          | Ничего не включено                                      | RSI как источник данных, long/short = True всегда         |

**Важно:** Когда включены Range + Cross одновременно, итоговый сигнал = `Range AND Cross` (оба должны быть True).

---

### 1.1 Базовые настройки

| Параметр         | UI Label                         | Тип      | Default   | Описание                                            |
| ---------------- | -------------------------------- | -------- | --------- | --------------------------------------------------- |
| `period`         | RSI TF Long(14)                  | number   | **14**    | Период расчёта RSI (количество свечей)              |
| `timeframe`      | RSI TimeFrame                    | select   | **Chart** | Таймфрейм данных (Chart = текущий)                  |
| `use_btc_source` | Use BTCUSDT as Source for RSI 1? | checkbox | **false** | Использовать RSI от BTCUSDT вместо текущего символа |

**Как работает `period`:** RSI рассчитывается по формуле Wilder на N последних свечах. Чем больше период, тем более сглаженный индикатор. Типичные значения: 7 (агрессивный), 14 (стандартный), 21 (консервативный).

**Как работает `use_btc_source`:** Вместо RSI текущей монеты, используется RSI биткоина. Логика: BTC определяет общее настроение рынка — когда RSI BTC в зоне перепроданности, можно входить в лонг на альткоинах.

---

### 1.2 Range Filter — Диапазонный фильтр

#### LONG Range

| Параметр         | UI Label           | Тип      | Default   | Описание                                       |
| ---------------- | ------------------ | -------- | --------- | ---------------------------------------------- |
| `use_long_range` | Use RSI LONG Range | checkbox | **false** | Включить фильтр диапазона для LONG             |
| `long_rsi_more`  | (LONG) RSI is More | number   | **30**    | Нижняя граница — RSI должен быть БОЛЬШЕ этого  |
| `long_rsi_less`  | & RSI Less         | number   | **70**    | Верхняя граница — RSI должен быть МЕНЬШЕ этого |

**Как работает:** Разрешает LONG сигнал только когда `RSI > long_rsi_more AND RSI < long_rsi_less`.

**Пример:** `long_rsi_more=30, long_rsi_less=70` → LONG разрешён когда RSI между 30 и 70.

**Практика:** Для зоны перепроданности: `long_rsi_more=1, long_rsi_less=30` — входим в LONG когда RSI в зоне 1-30 (перепроданность).

#### SHORT Range

| Параметр          | UI Label            | Тип      | Default   | Описание                                       |
| ----------------- | ------------------- | -------- | --------- | ---------------------------------------------- |
| `use_short_range` | Use RSI SHORT Range | checkbox | **false** | Включить фильтр диапазона для SHORT            |
| `short_rsi_less`  | (SHORT) RSI is Less | number   | **70**    | Верхняя граница — RSI должен быть МЕНЬШЕ этого |
| `short_rsi_more`  | & RSI More          | number   | **30**    | Нижняя граница — RSI должен быть БОЛЬШЕ этого  |

**Как работает:** Разрешает SHORT сигнал только когда `RSI < short_rsi_less AND RSI > short_rsi_more`.

**Пример:** `short_rsi_less=100, short_rsi_more=70` → SHORT разрешён когда RSI между 70 и 100 (перекупленность).

**⚠️ Правило:** `short_rsi_more` (нижняя граница) ВСЕГДА должно быть < `short_rsi_less` (верхняя граница).

---

### 1.3 Cross Level — Пересечение уровня

| Параметр            | UI Label                                 | Тип      | Default   | Описание                                      |
| ------------------- | ---------------------------------------- | -------- | --------- | --------------------------------------------- |
| `use_cross_level`   | Use RSI Cross Level                      | checkbox | **false** | Включить сигнал пересечения уровня            |
| `cross_long_level`  | Level to Cross RSI for LONG              | number   | **30**    | Уровень для LONG: RSI пересекает снизу вверх  |
| `cross_short_level` | Level to Cross RSI for SHORT             | number   | **70**    | Уровень для SHORT: RSI пересекает сверху вниз |
| `opposite_signal`   | Opposite Signal - RSI Cross Level        | checkbox | **false** | Инвертировать направление сигналов            |
| `use_cross_memory`  | Activate RSI Cross Signal Memory         | checkbox | **false** | Включить память сигнала                       |
| `cross_memory_bars` | Keep RSI Cross Signal Memory for XX bars | number   | **5**     | Количество баров для хранения сигнала         |

**Как работает Cross Level:**

- **LONG:** RSI на предыдущем баре ≤ `cross_long_level`, на текущем > `cross_long_level` → сигнал True
- **SHORT:** RSI на предыдущем баре ≥ `cross_short_level`, на текущем < `cross_short_level` → сигнал True
- Это **событийный** сигнал — True только на одном баре пересечения

**Как работает `opposite_signal`:**

- Меняет местами LONG и SHORT сигналы
- Включено: LONG генерируется когда RSI пересекает short_level ВНИЗ, SHORT — когда RSI пересекает long_level ВВЕРХ
- Используется для контр-трендовых стратегий

**Как работает Signal Memory:**

- Без памяти: сигнал = True только на баре пересечения (1 бар)
- С памятью (N баров): сигнал остаётся True ещё N баров после пересечения
- Пример: `memory_bars=5` на 15-мин графике → сигнал активен 5×15 = 75 минут после пересечения
- Это даёт другим фильтрам время "совпасть" с сигналом RSI

---

### 1.4 Комбинирование режимов (Логика AND)

```
Итоговый LONG = long_range_condition AND long_cross_condition
Итоговый SHORT = short_range_condition AND short_cross_condition
```

**Пример комбинации:**

- `use_long_range=true, long_rsi_more=20, long_rsi_less=50` — RSI в зоне 20-50
- `use_cross_level=true, cross_long_level=30, use_cross_memory=true, memory_bars=3`
- Результат: LONG = True когда RSI в диапазоне 20-50 **И** RSI пересёк уровень 30 вверх в последних 3 барах

---

### 1.5 Оптимизация RSI

При нажатии кнопки **"Optimization"** показывается панель оптимизации. Каждый оптимизируемый параметр имеет:

- **Checkbox** — включить/выключить оптимизацию этого параметра
- **min** → **max** / **step** — диапазон перебора

#### Оптимизируемые параметры RSI:

| Параметр            | Default Range | Описание в оптимизации                   |
| ------------------- | ------------- | ---------------------------------------- |
| `period`            | 14 → 14 / 1   | RSI TF Long(14)                          |
| `long_rsi_more`     | 30 → 30 / 1   | (LONG) RSI is More                       |
| `long_rsi_less`     | 70 → 70 / 1   | Long RSI Less                            |
| `short_rsi_less`    | 70 → 70 / 1   | (SHORT) RSI is Less                      |
| `short_rsi_more`    | 30 → 30 / 1   | Short RSI More                           |
| `cross_long_level`  | 30 → 30 / 1   | Level to Cross RSI for LONG              |
| `cross_short_level` | 70 → 70 / 1   | Level to Cross RSI for SHORT             |
| `cross_memory_bars` | 5 → 5 / 1     | Keep RSI Cross Signal Memory for XX bars |

#### Рекомендуемые диапазоны оптимизации:

| Параметр            | min | max | step | Обоснование                        |
| ------------------- | --- | --- | ---- | ---------------------------------- |
| `period`            | 5   | 30  | 1    | От агрессивного до консервативного |
| `long_rsi_more`     | 10  | 45  | 5    | Нижняя граница зоны покупки        |
| `long_rsi_less`     | 55  | 90  | 5    | Верхняя граница зоны покупки       |
| `short_rsi_less`    | 55  | 90  | 5    | Верхняя граница зоны продажи       |
| `short_rsi_more`    | 10  | 45  | 5    | Нижняя граница зоны продажи        |
| `cross_long_level`  | 15  | 45  | 5    | Уровень пересечения для LONG       |
| `cross_short_level` | 55  | 85  | 5    | Уровень пересечения для SHORT      |
| `cross_memory_bars` | 1   | 20  | 1    | Длительность памяти сигнала        |

**Формат хранения:** `block.optimizationParams[key] = { enabled: true/false, min: N, max: N, step: N }`

---

## 📋 ЧАСТЬ 2: MACD ФИЛЬТР — Полное описание параметров

### Общая информация

**Название блока:** `MACD - [SIGNALS] (CROSS 0 LINE OR CROSS SIGNAL LINE)`
**Тип:** Индикатор (`indicator_type == "macd"`)
**Выходные порты:** `macd` (серия), `signal` (серия), `hist` (серия), `long` (булевый сигнал), `short` (булевый сигнал)

### Режимы работы MACD

MACD поддерживает **2 сигнальных режима**, комбинируемые через **OR** логику:

| #   | Режим                              | Активация                    | Описание                                           |
| --- | ---------------------------------- | ---------------------------- | -------------------------------------------------- |
| 1   | **Cross Zero (Level)**             | `use_macd_cross_zero=true`   | MACD пересекает заданный уровень (default 0)       |
| 2   | **Cross Signal Line**              | `use_macd_cross_signal=true` | MACD пересекает линию Signal                       |
| 3   | **Data-only** (ничего не включено) | По умолчанию                 | Только данные MACD/Signal/Hist, long/short = False |

**⚠️ Важное отличие от RSI:** Режимы MACD комбинируются через **OR** (любой из режимов может дать сигнал), а не AND как в RSI. Если включены оба режима — сигнал генерируется когда ЛЮБОЙ из них срабатывает.

---

### 2.1 Базовые настройки MACD

| Параметр               | UI Label                        | Тип      | Default   | Описание                                           |
| ---------------------- | ------------------------------- | -------- | --------- | -------------------------------------------------- |
| `enable_visualization` | Enable Visualisation MACD       | checkbox | **false** | Показать гистограмму MACD на графике               |
| `timeframe`            | MACD TimeFrame                  | select   | **Chart** | Таймфрейм для расчёта MACD                         |
| `use_btc_source`       | Use BTCUSDT as Source for MACD? | checkbox | **false** | Использовать данные BTC для расчёта                |
| `fast_period`          | MACD Fast Length (12)           | number   | **12**    | Период быстрой EMA                                 |
| `slow_period`          | MACD Slow Length (26)           | number   | **26**    | Период медленной EMA                               |
| `signal_period`        | MACD Signal Smoothing (9)       | number   | **9**     | Период сглаживания Signal линии                    |
| `source`               | MACD Source                     | select   | **close** | Источник цены (close/open/high/low/hl2/hlc3/ohlc4) |

**Как работает MACD:**

- **MACD Line** = EMA(fast_period) − EMA(slow_period)
- **Signal Line** = EMA(signal_period) от MACD Line
- **Histogram** = MACD Line − Signal Line
- **⚠️ Правило:** `fast_period` ВСЕГДА должен быть < `slow_period`

---

### 2.2 Cross Zero (Cross Level) — Пересечение нулевой линии

| Параметр                   | UI Label                                    | Тип      | Default   | Описание                               |
| -------------------------- | ------------------------------------------- | -------- | --------- | -------------------------------------- |
| `use_macd_cross_zero`      | Use MACD Cross with Level (0)               | checkbox | **false** | Включить сигнал пересечения уровня     |
| `opposite_macd_cross_zero` | Opposite Signal - MACD Cross with Level (0) | checkbox | **false** | Инвертировать сигналы                  |
| `macd_cross_zero_level`    | Cross Line Level (0)                        | number   | **0**     | Уровень пересечения (не обязательно 0) |

**Как работает:**

- **LONG:** MACD Line на предыдущем баре ≤ level, на текущем > level → пересечение ВВЕРХ
- **SHORT:** MACD Line на предыдущем баре ≥ level, на текущем < level → пересечение ВНИЗ

**Как работает `opposite_macd_cross_zero`:**

- Меняет местами LONG и SHORT сигналы
- Включено: LONG = пересечение вниз, SHORT = пересечение вверх

**Как работает `macd_cross_zero_level`:**

- По умолчанию 0 (нулевая линия), но можно задать любой уровень
- Пример: `level=-50` — LONG когда MACD пересекает -50 снизу вверх (ранний вход из глубокой коррекции)
- Пример: `level=50` — LONG только когда MACD уже высоко (подтверждение сильного тренда)

---

### 2.3 Cross Signal Line — Пересечение линии Signal

| Параметр                       | UI Label                                      | Тип      | Default   | Описание                                         |
| ------------------------------ | --------------------------------------------- | -------- | --------- | ------------------------------------------------ |
| `use_macd_cross_signal`        | Use MACD Cross with Signal Line               | checkbox | **false** | Включить сигнал пересечения Signal линии         |
| `signal_only_if_macd_positive` | Signal only if MACD < 0 (Long) or > 0 (Short) | checkbox | **false** | Фильтр: Long только при MACD<0, Short при MACD>0 |
| `opposite_macd_cross_signal`   | Opposite Signal - MACD Cross with Signal Line | checkbox | **false** | Инвертировать сигналы                            |

**Как работает:**

- **LONG:** MACD Line пересекает Signal Line СНИЗУ ВВЕРХ (бычий кроссовер)
- **SHORT:** MACD Line пересекает Signal Line СВЕРХУ ВНИЗ (медвежий кроссовер)

**Как работает `signal_only_if_macd_positive`:**

- Это фильтр для **mean-reversion** стратегий
- LONG генерируется ТОЛЬКО когда MACD < 0 (линия ниже нуля = медвежья территория → покупка на развороте)
- SHORT генерируется ТОЛЬКО когда MACD > 0 (линия выше нуля = бычья территория → продажа на развороте)
- Без фильтра: сигналы генерируются при любом положении MACD

**Как работает `opposite_macd_cross_signal`:**

- Меняет местами LONG и SHORT кроссоверы
- Включено: LONG = медвежий кроссовер, SHORT = бычий кроссовер

---

### 2.4 Signal Memory (Память сигнала)

| Параметр                | UI Label                                          | Тип      | Default   | Описание                 |
| ----------------------- | ------------------------------------------------- | -------- | --------- | ------------------------ |
| `disable_signal_memory` | ==Disable Signal Memory (for both MACD Crosses)== | checkbox | **false** | Отключить память сигнала |
| `signal_memory_bars`    | (не показан в UI, но используется)                | number   | **5**     | Количество баров памяти  |

**⚠️ Критическая особенность:** Signal Memory в MACD **ВКЛЮЧЕНА по умолчанию** (в отличие от RSI, где она выключена).

**Как работает:**

- По умолчанию: сигнал MACD остаётся активным ещё 5 баров после пересечения
- `disable_signal_memory=true` — сигнал только на баре пересечения (1 бар)
- Применяется к **обоим** режимам (Cross Zero и Cross Signal)

**Зачем нужна память:**

- MACD — запаздывающий индикатор, кроссовер может произойти, но другие фильтры могут не совпасть
- Память даёт "окно" для совпадения с другими условиями
- На 15-мин графике: 5 баров = 75 минут окна для входа

---

### 2.5 Комбинирование режимов MACD (Логика OR)

```python
long_signal = False  # Начинается с False
if use_cross_zero:
    long_signal = long_signal OR zero_long  # Добавляем через OR
if use_cross_signal:
    long_signal = long_signal OR sig_long   # Добавляем через OR
# Затем применяется Signal Memory к итоговому сигналу
```

**Пример комбинации:**

- `use_macd_cross_zero=true, level=0` — LONG когда MACD пересекает 0
- `use_macd_cross_signal=true` — LONG когда MACD пересекает Signal
- Результат: LONG = True когда ЛЮБОЕ из пересечений произошло

---

### 2.6 Оптимизация MACD

#### Оптимизируемые параметры MACD:

| Параметр                | Default Range | Описание в оптимизации    |
| ----------------------- | ------------- | ------------------------- |
| `fast_period`           | 12 → 12 / 1   | MACD Fast Length (12)     |
| `slow_period`           | 26 → 26 / 1   | MACD Slow Length (26)     |
| `signal_period`         | 9 → 9 / 1     | MACD Signal Smoothing (9) |
| `macd_cross_zero_level` | 0 → 0 / 1     | Cross Line Level (0)      |

**Примечание:** `signal_memory_bars` НЕ отображается в панели оптимизации в UI, но поддерживается программно.

#### Рекомендуемые диапазоны оптимизации:

| Параметр                | min | max | step | Обоснование            |
| ----------------------- | --- | --- | ---- | ---------------------- |
| `fast_period`           | 8   | 16  | 1    | Диапазон быстрой EMA   |
| `slow_period`           | 20  | 30  | 1    | Диапазон медленной EMA |
| `signal_period`         | 6   | 12  | 1    | Сглаживание Signal     |
| `macd_cross_zero_level` | -50 | 50  | 1    | Уровень пересечения    |
| `signal_memory_bars`    | 1   | 20  | 1    | Длительность памяти    |

**⚠️ Ограничение при оптимизации:** `fast_period` должен быть строго < `slow_period`.

---

## 📋 ЧАСТЬ 3: ВОПРОСЫ ДЛЯ ТЕСТИРОВАНИЯ AI АГЕНТОВ

### Уровень 1: Базовое понимание

1. **Что произойдёт, если RSI блок добавлен без включения ни одного режима?**

    > Ожидаемый ответ: RSI работает в режиме Passthrough — `long` и `short` всегда True. Блок работает как источник данных RSI-значения.

2. **В чём разница между Range Filter и Cross Level в RSI?**

    > Ожидаемый ответ: Range — непрерывное условие (True пока RSI в диапазоне). Cross — событийное (True только на баре пересечения). Range фильтрует, Cross генерирует сигнал.

3. **Какой оператор используется для комбинирования режимов RSI? А для MACD?**
    > Ожидаемый ответ: RSI — AND (оба условия должны быть True). MACD — OR (любой режим может дать сигнал).

### Уровень 2: Практическое использование

4. **Как настроить RSI для входа в LONG только в зоне перепроданности (RSI < 30) с пересечением уровня 25 вверх?**

    > Ожидаемый ответ:
    >
    > - `use_long_range=true, long_rsi_more=1, long_rsi_less=30`
    > - `use_cross_level=true, cross_long_level=25`
    > - Результат: LONG когда RSI в зоне 1-30 AND RSI пересекает 25 вверх

5. **Как настроить MACD для mean-reversion стратегии?**

    > Ожидаемый ответ:
    >
    > - `use_macd_cross_signal=true` — включить кроссовер Signal
    > - `signal_only_if_macd_positive=true` — фильтр: LONG только при MACD<0, SHORT только при MACD>0
    > - Логика: покупаем в медвежьей зоне на бычьем кроссовере, продаём в бычьей зоне на медвежьем

6. **Зачем нужна Signal Memory и как она влияет на сигналы?**
    > Ожидаемый ответ: Memory расширяет одноразовый сигнал пересечения на N баров. Без неё: True только на 1 баре. С memory_bars=5 на 15мин: сигнал активен 75 минут. Даёт время для совпадения с другими фильтрами.

### Уровень 3: Оптимизация

7. **Настройте оптимизацию RSI для поиска лучшего уровня Cross Level для LONG в диапазоне 15-45 с шагом 5:**

    > Ожидаемый ответ:
    >
    > ```json
    > {
    >     "cross_long_level": { "enabled": true, "min": 15, "max": 45, "step": 5 }
    > }
    > ```
    >
    > Это создаст 7 итераций: 15, 20, 25, 30, 35, 40, 45

8. **Почему при оптимизации MACD важно, чтобы fast_period < slow_period?**

    > Ожидаемый ответ: MACD = EMA(fast) - EMA(slow). Если fast ≥ slow, MACD теряет смысл — быстрая EMA не будет опережать медленную. Оптимизатор должен проверять это ограничение.

9. **Как правильно оптимизировать MACD Cross Level вместе с fast/slow периодами?**
    > Ожидаемый ответ:
    >
    > - `fast_period: {enabled: true, min: 8, max: 16, step: 1}`
    > - `slow_period: {enabled: true, min: 20, max: 30, step: 1}`
    > - `macd_cross_zero_level: {enabled: true, min: -50, max: 50, step: 5}`
    > - Важно: комбинаторный взрыв — 9 × 11 × 21 = 2079 комбинаций

### Уровень 4: Продвинутые сценарии

10. **Как создать стратегию с RSI + MACD, где RSI фильтрует, а MACD даёт сигнал входа?**

    > Ожидаемый ответ:
    >
    > - RSI блок: `use_long_range=true, long_rsi_more=20, long_rsi_less=50` (фильтр: RSI в нейтральной зоне)
    > - MACD блок: `use_macd_cross_signal=true` (сигнал: бычий кроссовер)
    > - Подключение: RSI.long → AND-логика → MACD.long → Entry Long
    > - Результат: вход в LONG только когда RSI 20-50 И MACD пересекает Signal вверх

11. **Что произойдёт если включить `opposite_signal` в RSI Cross Level?**

    > Ожидаемый ответ: Сигналы long и short меняются местами:
    >
    > - Обычно: LONG = RSI пересекает `cross_long_level` ВВЕРХ
    > - С opposite: LONG = RSI пересекает `cross_short_level` ВНИЗ
    > - Это контр-трендовая логика: входим в LONG когда RSI падает через уровень перекупленности

12. **Чем отличается Signal Memory в RSI от MACD?**
    > Ожидаемый ответ:
    >
    > - RSI: Memory **ВЫКЛЮЧЕНА** по умолчанию. Нужно включить `use_cross_memory=true`
    > - MACD: Memory **ВКЛЮЧЕНА** по умолчанию (5 баров). Нужно включить `disable_signal_memory=true` чтобы отключить
    > - В RSI memory применяется только к Cross Level
    > - В MACD memory применяется к обоим режимам (Cross Zero и Cross Signal)

---

## 📋 ЧАСТЬ 4: ТЕХНИЧЕСКАЯ РЕАЛИЗАЦИЯ (для проверки глубины понимания)

### Файлы реализации:

| Файл                                              | Что делает                                                                                        |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `backend/core/indicators/rsi_advanced.py`         | Модуль RSI Advanced Filter (NumPy, TradingView-parity)                                            |
| `backend/backtesting/strategy_builder_adapter.py` | Адаптер: связывает UI-блоки с вычислениями (lines 568-676 = RSI, lines 678-756 = MACD)            |
| `frontend/js/pages/strategy_builder.js`           | UI: дефолты (lines 4148-4172 = RSI, 4243-4262 = MACD), панели (5960-5998 = RSI, 6109-6129 = MACD) |
| `backend/agents/prompts/templates.py`             | Промпт-шаблоны для AI агентов с описанием параметров                                              |
| `backend/agents/mcp/tools/strategy_builder.py`    | MCP инструмент с документацией оптимизации                                                        |

### Код RSI в адаптере (ключевая логика):

```python
# Range: continuous condition
if use_long_range:
    long_range_condition = (rsi > long_rsi_more) & (rsi < long_rsi_less)
else:
    long_range_condition = True  # Default: allow all

# Cross: event-based signal
if use_cross_level:
    cross_long = (rsi.shift(1) <= cross_long_level) & (rsi > cross_long_level)
    if opposite_signal:
        cross_long, cross_short = cross_short, cross_long
    if use_cross_memory:
        cross_long = _apply_signal_memory(cross_long, memory_bars)
else:
    long_cross_condition = True  # Default: allow all

# Combine: AND
long_signal = long_range_condition & long_cross_condition
```

### Код MACD в адаптере (ключевая логика):

```python
long_signal = False  # Start with False (not True like RSI!)

if use_cross_zero:
    zero_long = (macd > level) & (macd.shift(1) <= level)
    if opposite:
        zero_long, zero_short = zero_short, zero_long
    long_signal = long_signal | zero_long  # OR logic

if use_cross_signal:
    sig_long = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))
    if signal_only_if_macd_positive:
        sig_long = sig_long & (macd < 0)  # Only in negative territory
    if opposite:
        sig_long, sig_short = sig_short, sig_long
    long_signal = long_signal | sig_long  # OR logic

# Memory (enabled by default!)
if not disable_signal_memory:
    long_signal = _apply_signal_memory(long_signal, memory_bars)
```

---

## ✅ Критерии оценки AI агентов

| Критерий                      | Баллы    | Описание                                  |
| ----------------------------- | -------- | ----------------------------------------- |
| Правильные дефолтные значения | /10      | Знает ли агент дефолты всех параметров    |
| Понимание режимов RSI         | /15      | Range vs Cross vs Legacy vs Passthrough   |
| Понимание режимов MACD        | /15      | Cross Zero vs Cross Signal vs Data-only   |
| AND vs OR логика              | /10      | RSI=AND, MACD=OR — критическое различие   |
| Signal Memory                 | /10      | RSI=off by default, MACD=on by default    |
| Opposite Signal               | /10      | Как инверсия работает в обоих фильтрах    |
| Оптимизация                   | /15      | Правильные диапазоны, формат, ограничения |
| Практические сценарии         | /15      | Умение составить рабочую конфигурацию     |
| **ИТОГО**                     | **/100** |                                           |
