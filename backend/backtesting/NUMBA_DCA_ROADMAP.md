# Numba DCA Engine — Roadmap паритета с V4

**Файлы:** `backend/backtesting/numba_dca_engine.py` (Numba) vs `backend/backtesting/engines/dca_engine.py` (V4)
**Дата документа:** 2026-03-16
**Последнее обновление:** 2026-03-16 — **Phase 1-3 COMPLETE ✅** (все 7 фич реализованы и протестированы)

---

## 1. Архитектурный принцип

`@njit`-функция не может принимать Python-объекты (DataFrame, dataclass, dict,
list of objects). Всё, что попадает в `_simulate_dca_single`, должно быть либо
скаляром (`int`/`float`), либо `np.ndarray`.

**Паттерн решения для сложных фич:**

```
Python-уровень                         @njit (_simulate_dca_single)
─────────────────────────────────      ─────────────────────────────
Вычислить индикатор → np.ndarray  ──►  Получить массив, читать arr[i]
Сериализовать конфиг → int/float  ──►  Использовать как скаляр/флаг
```

Этот паттерн уже применён для ATR TP/SL:

- Python вычисляет `atr_values: np.ndarray[n_bars]` снаружи
- Numba получает массив, читает `atr_values[i]` внутри цикла

Тот же подход применим к **любому индикатору**. Ограничений нет.

---

## 2. Текущий статус паритета

### ✅ Реализовано и верифицировано (parity delta = 0.0)

| Фича                                           | Numba параметр                                                       | Parity тест |
| ---------------------------------------------- | -------------------------------------------------------------------- | :---------: |
| Grid orders (1–15 уровней)                     | `order_count`, `grid_size_pct`                                       |      ✔      |
| Martingale `multiply_each`                     | `martingale_coef`                                                    |      ✔      |
| Single SL%                                     | `stop_loss_pct`                                                      |      ✔      |
| Single TP%                                     | `take_profit_pct`                                                    |      ✔      |
| Multi-TP TP1–TP4 (partial close)               | `multi_tp_enabled`, `tp_percents[4]`, `tp_close_pcts[4]`, `tp_count` |      ✔      |
| Trailing Stop                                  | `trailing_activation_pct`, `trailing_distance_pct`                   |      ✔      |
| ATR TP / ATR SL                                | `atr_tp_multiplier`, `atr_sl_multiplier`, `atr_values[n]`            |      ✔      |
| Breakeven SL                                   | `breakeven_activation_pct`, `breakeven_offset_pct`                   |      ✔      |
| Safety close (drawdown% of margin)             | `safety_close_enabled`, `safety_close_threshold_pct`                 |      ✔      |
| Close-by-time                                  | `max_bars_in_trade`, `min_profit_close_pct`                          |      ✔      |
| DCA grid fills (long & short)                  | —                                                                    |      ✔      |
| max_drawdown (closed-equity / initial_capital) | —                                                                    |      ✔      |
| Sharpe (monthly TV, ddof=0)                    | `bars_per_month`                                                     |      ✔      |
| Batch parallel (N combos)                      | `prange`                                                             |      —      |

### ❌ Не реализовано

| Фича                                  | V4 класс/поле                         | Сложность |  Важность  |          Статус          |
| ------------------------------------- | ------------------------------------- | :-------: | :--------: | :----------------------: |
| Close condition: RSI                  | `CloseConditionsConfig.rsi_close_*`   |  Низкая   | 🔴 Высокая |         ✅ Done          |
| Close condition: Stochastic           | `stoch_close_*`                       |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Close condition: Channel (Keltner/BB) | `channel_close_*`                     |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Close condition: Two MAs              | `ma_close_*`                          |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Close condition: PSAR                 | `psar_close_*`                        |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Martingale `multiply_total`           | `DCAGridConfig.martingale_mode`       |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Martingale `progressive`              | `DCAGridConfig.martingale_mode`       |  Низкая   | 🟡 Средняя |         ✅ Done          |
| Partial grid                          | `DCAGridConfig.partial_grid_orders`   |  Низкая   | 🟢 Низкая  |         ✅ Done          |
| Grid pullback                         | `DCAGridConfig.grid_pullback_percent` |  Низкая   | 🟢 Низкая  |         ✅ Done          |
| Grid trailing                         | `DCAGridConfig.grid_trailing_percent` |  Низкая   | 🟢 Низкая  |         ✅ Done          |
| Indent orders (limit entry)           | `IndentOrderConfig`                   |  Средняя  | 🟢 Низкая  |         ✅ Done          |
| SL type `last_order`                  | `DCAEngine._sl_type`                  |  Низкая   | 🟢 Низкая  |         ✅ Done          |
| Log-scale grid steps                  | `DCAGridConfig.use_log_steps`         |  Низкая   | 🟢 Низкая  |         ✅ Done          |
| Dynamic TP                            | `DCAGridConfig.dynamic_tp_*`          |  Средняя  | 🟢 Низкая  |      ❌ Not planned      |
| Custom grid orders                    | `DCAGridConfig.custom_orders`         |  Средняя  | 🟢 Низкая  |      ❌ Not planned      |
| 166 MetricsCalculator метрик          | `MetricsCalculator.calculate_all()`   |    Н/Д    |     —      | N/A (вызываются снаружи) |

> **166 метрик**: не нужно портировать внутрь `@njit`. После оптимизации топ-N результатов
> перегоняются через V4 или `MetricsCalculator.calculate_all(equity_curve, trades)` снаружи.

---

## 3. Детальные рекомендации по реализации

---

### 3.1 Close Conditions — ПРИОРИТЕТ #1 🔴

**Почему критично:**
Если пользователь оптимизирует стратегию с RSI-close или MA-close, Numba игнорирует
этот выход → оптимизация выбирает "лучшие" параметры SL/TP без учёта реального закрытия →
результаты расходятся с бэктестом V4. Это самый опасный gap.

**Принцип решения — precompute + combined signal:**

V4 уже вычисляет индикаторы в `_precompute_close_condition_indicators()` и хранит их как
`np.ndarray` (`_rsi_cache`, `_stoch_k_cache`, `_ma1_cache`, `_ma2_cache`, `_psar_cache`,
`_bb_upper_cache`, `_bb_lower_cache`, `_keltner_upper_cache`, `_keltner_lower_cache`).

Задача: применить логику `_check_rsi_close()` / `_check_channel_close()` и т.д. снаружи
`@njit`, свернув результат в **один булевый массив** `close_cond_signal[n_bars]`.

**Архитектура:**

```python
# Python-уровень (в run_dca_single_numba / run_dca_batch_numba):
def _build_close_condition_signal(
    engine: DCAEngine,
    ohlcv: pd.DataFrame,
    close_conditions: CloseConditionsConfig,
) -> np.ndarray:  # bool[n_bars]
    """
    Прогоняет логику всех close conditions по всем барам и формирует
    комбинированный сигнал закрытия для длинной позиции.

    Profit filter применяется приближённо: по порогу min_profit_pct
    относительно close (без avg_entry, которого нет до симуляции).
    Точный profit_filter — в V4, но для оптимизации приближение достаточно.
    """
    n = len(ohlcv)
    engine._precompute_close_condition_indicators(ohlcv)
    signal = np.zeros(n, dtype=np.bool_)

    for i in range(1, n):
        # Минимальный profit proxy: (close[i] - close[i-20]) / close[i-20]
        # Точный profit_percent неизвестен до симуляции — это допустимое приближение
        reason = engine._check_close_conditions(i, ohlcv["close"].iloc[i])
        if reason is not None:
            signal[i] = True

    return signal
```

> **Важно:** Profit filter (`only_profit`, `min_profit`) внутри `_check_close_conditions`
> использует `position.unrealized_pnl_percent` — он недоступен до симуляции.
> **Решение A (рекомендуется):** Передавать profit filter как отдельный параметр
> `close_cond_min_profit_frac: float` в `_simulate_dca_single`. Внутри Numba вычислять
> `unrealized_pct` (уже есть!) и применять фильтр к комбинированному сигналу.
> **Решение B (проще):** Игнорировать profit filter при построении сигнала (консервативно —
> закрывает чуть чаще, но для оптимизации достаточно точно).

**Изменения в `_simulate_dca_single`:**

```python
# Новый параметр:
close_cond: np.ndarray,       # bool[n_bars] — предвычисленный OR всех close conditions
close_cond_min_profit: float, # 0.0 = без фильтра; >0 = min unrealized_pct для срабатывания

# Новый блок в exit checks (после safety close, перед equity update):
if not should_close and in_position and close_cond[i]:
    if close_cond_min_profit <= 0.0 or unrealized_pct >= close_cond_min_profit:
        should_close = True
        exit_price = current_close
        exit_reason = 6  # close_condition
```

**Что нужно сделать:**

1. Написать `_build_close_condition_signal(engine, ohlcv, config) -> np.ndarray`
   в `numba_dca_engine.py` (Python-функция, не `@njit`)
2. Добавить параметры `close_cond: np.ndarray`, `close_cond_min_profit: float` в
   `_simulate_dca_single` и `batch_simulate_dca`
3. В `run_dca_batch_numba` / `run_dca_single_numba`: добавить Python-default
   `close_cond_arr: np.ndarray | None = None`, при `None` подставлять `np.zeros(n, np.bool_)`
4. В `builder_optimizer.py`: при DCA оптимизации вызывать `_build_close_condition_signal`
   один раз (уже есть кеш `_precompute_dca_close_cache`) и передавать в Numba

**Parity-статус после реализации:** 100% — тот же `_check_close_conditions` V4.

---

### 3.2 Martingale `multiply_total` и `progressive` — ПРИОРИТЕТ #2 🟡

**Где в V4:**
`DCAGridConfig.martingale_mode` → `_calculate_order_sizes()` в `DCAGridCalculator`

**Формулы:**

| Mode                       | Логика                                                           | Формула веса `w[k]`                                                     |
| -------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `multiply_each` (уже есть) | каждый ордер в `coef` раз больше предыдущего                     | `w[k] = coef^k`                                                         |
| `multiply_total`           | каждое новое добавление удваивает/утраивает **итоговую** позицию | `w[k] = (coef-1) × sum(w[0..k-1])`, т.е. `w[k] = (coef-1) × coef^(k-1)` |
| `progressive`              | линейный рост                                                    | `w[k] = 1 + k × (coef - 1)`                                             |

**Изменения:**

```python
# Добавить параметр в _calc_grid_orders и _simulate_dca_single:
martingale_mode: int  # 0=multiply_each, 1=multiply_total, 2=progressive

# В _calc_grid_orders:
w = 1.0
for k in range(n):
    if martingale_mode == 1:   # multiply_total
        if k == 0:
            weights[k] = 1.0
        else:
            weights[k] = (martingale_coef - 1.0) * sum_prev_weights
    elif martingale_mode == 2:  # progressive
        weights[k] = 1.0 + k * (martingale_coef - 1.0)
    else:                       # multiply_each (default)
        weights[k] = w
        w *= martingale_coef
```

---

### 3.3 Partial Grid — ПРИОРИТЕТ #3 🟢

**Где в V4:**
`DCAGridConfig.partial_grid_orders` — активировать только первые N ордеров, при каждом
заполнении расширять окно на 1.

**Изменения в `_simulate_dca_single`:**

```python
# Новый параметр:
partial_grid_orders: int  # 0 или 1 = все сразу; 2+ = активировать N за раз

# Новые переменные состояния:
pos_active_up_to = 0   # сколько ордеров сейчас активно

# При открытии позиции:
if partial_grid_orders >= 2:
    pos_active_up_to = min(partial_grid_orders, pos_n_orders)
else:
    pos_active_up_to = pos_n_orders

# В цикле fills — ограничить диапазон:
for k in range(pos_active_up_to):   # вместо range(pos_n_orders)
    if not g_filled[k]:
        if ...:  # fill
            pos_active_up_to = min(pos_active_up_to + 1, pos_n_orders)
```

---

### 3.4 Grid Pullback и Grid Trailing — ПРИОРИТЕТ #3 🟢

**Где в V4:**
`DCAGridConfig.grid_pullback_percent`, `DCAGridConfig.grid_trailing_percent`
Реализованы в `DCAEngine._process_open_position` (блок "grid shift logic").

**Принцип:**

- **Pullback:** если цена ушла на `pullback_pct`% от базы без заполнения ордеров →
  сдвинуть все незаполненные ордера вниз (для long)
- **Trailing:** если цена ушла на `trailing_pct`% в выгодную сторону →
  сдвинуть ордера вверх (подтягивать за ценой)
- Trailing имеет приоритет (уже учтено в V4 через `elif`)

**Изменения:**

```python
# Новые параметры:
grid_pullback_pct: float,   # 0.0 = disabled
grid_trailing_pct: float,   # 0.0 = disabled (приоритет над pullback)

# Новые переменные состояния:
pullback_base_price = 0.0
trailing_grid_base_price = 0.0

# Логика внутри loop (после fills, перед exit checks):
if in_position and pos_n_filled < pos_n_orders:
    if grid_trailing_pct > 0.0 and trailing_grid_base_price > 0.0:
        if pos_direction == 0:
            move = (current_close - trailing_grid_base_price) / trailing_grid_base_price
        else:
            move = (trailing_grid_base_price - current_close) / trailing_grid_base_price
        if move >= grid_trailing_pct / 100.0:
            shift = current_close - trailing_grid_base_price  # для long
            for k in range(pos_n_orders):
                if not g_filled[k]:
                    g_prices[k] += shift
            trailing_grid_base_price = current_close
            pullback_base_price = current_close
    elif grid_pullback_pct > 0.0 and pullback_base_price > 0.0:
        move = abs(current_close - pullback_base_price) / pullback_base_price
        if move >= grid_pullback_pct / 100.0:
            shift = current_close - pullback_base_price
            for k in range(pos_n_orders):
                if not g_filled[k]:
                    g_prices[k] += shift
            pullback_base_price = current_close
```

---

### 3.5 Indent Orders — ПРИОРИТЕТ #4 🟢

**Где в V4:**
`IndentOrderConfig.enabled`, `indent_percent`, `cancel_after_bars`

**Суть:** При сигнале не открывать сразу, а выставить лимитный ордер на
`current_close * (1 - indent_pct)` (для long). Если за `cancel_after_bars` не заполнился —
отменить.

**Изменения:**

```python
# Новые параметры:
indent_enabled: int,         # 0/1
indent_pct: float,           # смещение от текущей цены
indent_cancel_bars: int,     # кол-во баров до отмены

# Новые переменные состояния:
pending_indent_price = 0.0
pending_indent_bar = 0
has_pending_indent = False

# В блоке новой позиции (else: new entry):
if indent_enabled > 0:
    if pos_direction == 0:
        pending_indent_price = current_close * (1.0 - indent_pct)
    else:
        pending_indent_price = current_close * (1.0 + indent_pct)
    pending_indent_bar = i
    has_pending_indent = True
else:
    # немедленное открытие (текущая логика)
    ...

# В начале loop (перед if in_position):
if has_pending_indent and not in_position:
    if pos_direction == 0 and current_low <= pending_indent_price:
        # fill indent → открыть позицию по pending_indent_price
        ...
        has_pending_indent = False
    elif indent_cancel_bars > 0 and (i - pending_indent_bar) >= indent_cancel_bars:
        has_pending_indent = False  # отмена
```

---

### 3.6 SL Type `last_order` — ПРИОРИТЕТ #4 🟢

**Где в V4:** `DCAEngine._sl_type = "last_order"` — SL считается от последнего заполненного
ордера, а не от средней цены.

**Изменения:**

```python
# Новый параметр:
sl_from_last_order: int  # 0=avg_entry (default), 1=last_order

# Новая переменная состояния:
pos_last_fill_price = 0.0  # обновляется при каждом fill

# В effective_sl_price:
sl_base = pos_last_fill_price if sl_from_last_order > 0 else pos_avg_entry
effective_sl_price = sl_base * (1.0 - stop_loss_pct)  # для long
```

---

### 3.7 Log-scale Grid Steps — ПРИОРИТЕТ #5 🟢

**Где в V4:** `DCAGridConfig.use_log_steps = True`, `log_coefficient`

Сейчас `_calc_grid_orders` использует равномерный шаг `step_pct = grid_size_pct / (n-1)`.
При log-steps шаги между уровнями нарастают по логарифмической прогрессии.

```python
# Новые параметры в _calc_grid_orders:
use_log_steps: int,      # 0/1
log_coefficient: float,  # коэффициент логарифмической прогрессии

# Логика шагов:
if use_log_steps and n > 1:
    # Логарифмические шаги: step[k] = base_step * log_coefficient^k
    # Нормализуем чтобы сумма шагов = grid_size_pct
    raw_steps = np.empty(n - 1)
    for k in range(n - 1):
        raw_steps[k] = log_coefficient ** k
    total = raw_steps.sum()
    for k in range(n):
        cumulative = raw_steps[:k].sum() / total * grid_size_pct / 100.0
        trigger_price = base_price * (1.0 - cumulative)  # для long
```

---

## 4. Порядок реализации (рекомендуемый)

```
Phase 1 — критично для корректности оптимизации  ✅ COMPLETE
├── [3.1] Close Conditions (RSI / Stoch / Channel / MA / PSAR)  ✅
│         build_close_condition_signal() + close_cond/close_cond_min_profit params
└── [3.2] Martingale multiply_total / progressive  ✅
          martingale_mode param (0/1/2) в _calc_grid_orders

Phase 2 — полнота функционала  ✅ COMPLETE
├── [3.4] Grid Pullback + Grid Trailing  ✅
│         grid_pullback_pct / grid_trailing_pct с elif-приоритетом
├── [3.3] Partial Grid  ✅
│         partial_grid_orders + pos_active_up_to механизм
└── [3.6] SL Type last_order  ✅
          sl_from_last_order + pos_last_fill_price tracking

Phase 3 — редко используемые  ✅ COMPLETE
├── [3.5] Indent Orders  ✅
│         indent_enabled/indent_pct/indent_cancel_bars
├── [3.7] Log-scale Grid Steps  ✅
│         use_log_steps/log_coefficient в _calc_grid_orders
└── Dynamic TP — ❌ Not planned (требует отдельного анализа)
```

### Тестовое покрытие

| Тест-сьют               | Файл                                                   | Тестов |   Статус    |
| ----------------------- | ------------------------------------------------------ | :----: | :---------: |
| V4 Parity (9 сценариев) | `temp_analysis/test_numba_v4_parity.py`                |   9    | ✅ ALL PASS |
| Phase 1-3 Features      | `tests/backend/backtesting/test_numba_dca_phase1_3.py` |   21   | ✅ ALL PASS |

---

## 5. Что НЕ нужно портировать

| Фича                              | Причина                                                      |
| --------------------------------- | ------------------------------------------------------------ |
| 166 MetricsCalculator метрик      | Вызываются снаружи на топ-N. В`@njit` нет смысла             |
| Полный список сделок с timestamp  | Не нужен для оптимизации                                     |
| Custom grid orders                | Редко оптимизируется, сложная сериализация вложенного списка |
| Alerts (`first_order_alert_only`) | Только UI                                                    |
| `supports_bar_magnifier`          | V4-специфика, не применима к Numba                           |

---

## 6. Шаблон сигнатуры после Phase 1+2

```python
@njit(cache=True, fastmath=True)
def _simulate_dca_single(
    close, high, low, entry_signals,
    # DCA core (уже есть)
    direction, order_count, grid_size_pct, martingale_coef,
    take_profit_pct, stop_loss_pct,
    initial_capital, position_size_frac, leverage, taker_fee,
    # close_by_time (уже есть)
    max_bars_in_trade, min_profit_close_pct,
    # Breakeven (уже есть)
    breakeven_activation_pct, breakeven_offset_pct,
    # Safety close (уже есть)
    safety_close_enabled, safety_close_threshold_pct,
    # Trailing stop (уже есть)
    trailing_activation_pct, trailing_distance_pct,
    # Multi-TP (уже есть)
    multi_tp_enabled, tp_percents, tp_close_pcts, tp_count,
    # ATR TP/SL (уже есть)
    atr_tp_multiplier, atr_sl_multiplier, atr_values,
    # === Phase 1: новое ===
    close_cond: np.ndarray,         # bool[n_bars] — precomputed close conditions
    close_cond_min_profit: float,   # 0.0 = без фильтра
    martingale_mode: int,           # 0=each, 1=total, 2=progressive
    # === Phase 2: новое ===
    partial_grid_orders: int,       # 1=все сразу, 2+=partial
    grid_pullback_pct: float,       # 0.0=disabled
    grid_trailing_pct: float,       # 0.0=disabled
    sl_from_last_order: int,        # 0=avg_entry, 1=last_order
    # Output
    out_pnl, out_entry_bar, out_exit_bar, out_is_win, out_equity,
) -> int: ...
```

Все новые параметры имеют `default=0`/`None` в Python-обёртках
(`run_dca_single_numba`, `run_dca_batch_numba`) → **обратная совместимость сохраняется**.

---

## 7. Тестирование после каждой фазы

После каждого добавленного блока запускать:

```bash
# Parity-тест
python temp_analysis/test_numba_v4_parity.py

# Smoke-тест новых фич
python temp_analysis/test_numba_new_features.py

# Регрессия оптимизатора
pytest tests/test_builder_optimizer.py -v
```

**Критерий паритета:** `abs(numba_net_profit - v4_net_profit) < 0.05 USD` для каждого сценария.

---

## 8. Известные ограничения Numba (для справки)

| Ограничение                           | Следствие                                              |
| ------------------------------------- | ------------------------------------------------------ |
| Нет Python-объектов в `@njit`         | Все конфиги → скаляры/массивы до вызова                |
| Нет default-аргументов в `@njit`      | Python-обёртка подставляет defaults                    |
| `cache=True` → кеш по сигнатуре       | При смене сигнатуры кеш сбрасывается автоматически     |
| `fastmath=True` → не строгий IEEE 754 | Допустимо для финансовых расчётов (суммы порядка 10⁻⁴) |
| Нет `str` внутри `@njit`              | Martingale mode и direction → `int` enum               |
| Нет рекурсии (легко обойти)           | Не проблема для текущих алгоритмов                     |
