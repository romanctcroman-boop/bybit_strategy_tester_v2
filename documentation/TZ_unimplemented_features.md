# ТЗ: Реализация незавершённых фич блоков закрытия и MTF-фильтров

**Дата:** 2026-02-22  
**Приоритет:** Средний  
**Статус:** Не реализовано — только предупреждения в лог  
**Верифицировано по коду:** `strategy_builder_adapter.py` (3490 lines), `engine.py` (2259 lines), `indicator_handlers.py` (1824 lines), `numba_engine.py` (416 lines)

---

## Контекст: что уже исправлено

BUG 1 (критический, **уже исправлен**): `close_cond` ветка в `generate_signals`
добавлена на строках ~3270–3291 адаптера. Теперь сигналы `exit_long`/`exit_short`
из блоков закрытия доходят до движка. Ниже описаны три функции, которые
**по-прежнему не работают** несмотря на то что UI их предоставляет.

---

## Содержание

1. [Фича 1 — `profit_only` / `min_profit` в блоках закрытия](#feature1)
2. [Фича 2 — MTF таймфрейм для mfi_filter и cci_filter](#feature2)
3. [Фича 3 — `use_btcusdt_mfi` (альтернативный источник данных)](#feature3)

---

## <a name="feature1"></a>Фича 1 — `profit_only` / `min_profit` в блоках закрытия

### Описание проблемы

Пять блоков закрытия позиции поддерживают опцию «закрывать только в прибыль»:

| Блок               | Параметры в params                                                   |
| ------------------ | -------------------------------------------------------------------- |
| `close_ma_cross`   | `profit_only: bool`, `min_profit_percent: float`                     |
| `close_rsi`        | `rsi_close_profit_only: bool`, `rsi_close_min_profit: float`         |
| `close_stochastic` | `stoch_close_profit_only: bool`, `stoch_close_min_profit: float`     |
| `close_psar`       | `psar_close_profit_only: bool`, `psar_close_min_profit: float`       |
| `close_channel`    | `channel_close_profit_only: bool`, `channel_close_min_profit: float` |

`_execute_close_condition` корректно читает эти параметры и кладёт в result-dict
Series-константы `profit_only=True` и `min_profit=<float>`. Но дальше они
**нигде не читаются** — ни в маршрутизации Case 2, ни в движке.

В результате опция «profit_only» в UI не работает: движок закрывает позицию
по сигналу блока независимо от того, прибыльна ли сделка.

### Текущий код — что уже есть

**`strategy_builder_adapter.py` `_execute_close_condition`** (строки 2634–2652, 2657–2707, 2714–2715):

Каждый из 5 close-блоков читает свои флаги под разными именами параметров:

| Блок               | Чтение profit_only                               | Чтение min_profit                             | Запись в result                                 |
| ------------------ | ------------------------------------------------ | --------------------------------------------- | ----------------------------------------------- |
| `close_ma_cross`   | `params.get("profit_only", False)`               | `params.get("min_profit_percent", 1.0)`       | `result["profit_only"]`, `result["min_profit"]` |
| `close_rsi`        | `params.get("rsi_close_profit_only", False)`     | `params.get("rsi_close_min_profit", 1.0)`     | `result["profit_only"]`, `result["min_profit"]` |
| `close_stochastic` | `params.get("stoch_close_profit_only", False)`   | `params.get("stoch_close_min_profit", 1.0)`   | `result["profit_only"]`, `result["min_profit"]` |
| `close_psar`       | _(нужно проверить)_                              | _(нужно проверить)_                           | `result["profit_only"]`, `result["min_profit"]` |
| `close_channel`    | `params.get("channel_close_profit_only", False)` | `params.get("channel_close_min_profit", 1.0)` | `result["profit_only"]`, `result["min_profit"]` |

> **ВАЖНО:** `min_profit` читается из params уже в **процентах** (`1.0 = 1%`).
> При записи в `extra_data` для движка — конвертировать: `/ 100.0`.
> Движок работает с долями (0.01 = 1%), как и все risk-параметры.

Данные записываются в `result` dict, но в блоке `if target_port == "close_cond"`
(строки ~3270–3291) `raw.get("profit_only")` **никогда не читается** —
флаги `profit_only`/`min_profit` молча теряются.

**`engine.py` `_run_fallback_v4`** (строки 1265, 1277, 1780–1797):

```python
close_only_in_profit = getattr(config, "close_only_in_profit", False)
extra_data = getattr(signals, "extra_data", None) or {}
# ... (строки 1280–1303: extra_data читается для ATR SL/TP и trailing stop)

# Строки 1780–1797 — signal-exit блок:
if not should_exit:
    signal_exit_triggered = False
    if (is_long and long_exits[i]) or (not is_long and short_exits is not None and short_exits[i]):
        signal_exit_triggered = True

    if signal_exit_triggered:
        if close_only_in_profit:
            is_profitable = price > entry_price if is_long else price < entry_price
            if is_profitable:
                should_exit = True
                exit_reason = "signal"
                exit_price = price
        else:
            should_exit = True
            exit_reason = "signal"
            exit_price = price
```

Движок умеет `close_only_in_profit`, но:

- только через глобальный `BacktestConfig.close_only_in_profit` (не per-signal)
- только `price > entry_price` без `min_profit_percent`
- `extra_data` уже читается в этой функции — паттерн добавления новых ключей хорошо известен

**`numba_engine.py` `NumbaEngineV2`** (строки 192–196):

```python
# Check signal exit
if not should_exit and ((is_long and long_exits[i]) or (not is_long and short_exits[i])):
    should_exit = True
    exit_reason = 0  # signal
    exit_price = price
```

NumbaEngine — это Numba JIT-компилированная функция. Она **не принимает `extra_data`**
и не имеет понятия `close_only_in_profit`. Исправление сложнее — нужно передавать
numpy arrays как дополнительные аргументы функции.

### Требуемая реализация

#### Шаг 1 — Адаптер: собрать profit_only флаги в `close_cond` ветке

**Файл:** `backend/backtesting/strategy_builder_adapter.py`

Перед главным циклом по connections (до строки ~3200) инициализировать:

```python
profit_only_exits = pd.Series(False, index=ohlcv.index)
profit_only_short_exits = pd.Series(False, index=ohlcv.index)
min_profit_for_exits: float = 0.0
min_profit_for_short_exits: float = 0.0
```

В существующей ветке `if target_port == "close_cond":` (строки ~3270–3291)
расширить после `exits = exits | raw["exit_long"]`:

```python
if target_port == "close_cond":
    raw = source_outputs
    has_profit_only = raw.get("profit_only")  # pd.Series[bool] или None
    min_profit_val = raw.get("min_profit")     # pd.Series[float] или None

    if "exit_long" in raw:
        exits = exits | raw["exit_long"]
        if has_profit_only is not None:
            profit_only_exits = profit_only_exits | raw["exit_long"]
            # min_profit в params — в процентах (1.0 = 1%); делим на 100 для движка
            mp = float(min_profit_val.iloc[0]) / 100.0 if min_profit_val is not None else 0.0
            min_profit_for_exits = max(min_profit_for_exits, mp)

    if "exit_short" in raw:
        short_exits = short_exits | raw["exit_short"]
        if has_profit_only is not None:
            profit_only_short_exits = profit_only_short_exits | raw["exit_short"]
            mp = float(min_profit_val.iloc[0]) / 100.0 if min_profit_val is not None else 0.0
            min_profit_for_short_exits = max(min_profit_for_short_exits, mp)

    if "exit" in raw and "exit_long" not in raw and "exit_short" not in raw:
        exits = exits | raw["exit"]
        short_exits = short_exits | raw["exit"]

    logger.debug(...)
    continue
```

В существующем блоке сбора `extra_data` (строки ~3432–3462) добавить после ATR/trailing:

```python
# ========== Collect profit_only exit data ==========
any_profit_only = profit_only_exits.any() or profit_only_short_exits.any()
if any_profit_only:
    extra_data["profit_only_exits"] = profit_only_exits          # pd.Series[bool]
    extra_data["profit_only_short_exits"] = profit_only_short_exits
    extra_data["min_profit_exits"] = min_profit_for_exits         # float, decimal
    extra_data["min_profit_short_exits"] = min_profit_for_short_exits
```

#### Шаг 2 — FallbackEngineV4: читать флаги и применять фильтр

**Файл:** `backend/backtesting/engine.py`, метод `_run_fallback_v4`

После блока чтения ATR данных (строка ~1285), добавить:

```python
# ========== PER-SIGNAL PROFIT_ONLY EXITS ==========
profit_only_exit_mask  = extra_data.get("profit_only_exits")   # pd.Series или None
profit_only_sexit_mask = extra_data.get("profit_only_short_exits")
min_profit_exit_pct    = float(extra_data.get("min_profit_exits", 0.0))
min_profit_sexit_pct   = float(extra_data.get("min_profit_short_exits", 0.0))
po_exit_arr  = profit_only_exit_mask.values  if profit_only_exit_mask  is not None else None
po_sexit_arr = profit_only_sexit_mask.values if profit_only_sexit_mask is not None else None
```

Заменить существующий signal-exit блок (строки ~1780–1797):

```python
if signal_exit_triggered:
    # Определить, нужна ли profit_only проверка для этого бара
    apply_profit_only = False
    required_min_profit = 0.0

    if is_long and po_exit_arr is not None and po_exit_arr[i]:
        apply_profit_only = True
        required_min_profit = min_profit_exit_pct
    elif not is_long and po_sexit_arr is not None and po_sexit_arr[i]:
        apply_profit_only = True
        required_min_profit = min_profit_sexit_pct

    # Глобальный fallback (BacktestConfig.close_only_in_profit)
    if not apply_profit_only and close_only_in_profit:
        apply_profit_only = True
        required_min_profit = 0.0  # глобальный — без min_profit

    if apply_profit_only:
        pnl_pct = (price - entry_price) / entry_price if is_long \
                  else (entry_price - price) / entry_price
        if pnl_pct >= required_min_profit:
            should_exit = True
            exit_reason = "signal"
            exit_price = price
        # else: сигнал подавлен — позиция остаётся открытой
    else:
        should_exit = True
        exit_reason = "signal"
        exit_price = price
```

#### Шаг 3 — NumbaEngineV2: передать маски как numpy arrays

**Файл:** `backend/backtesting/numba_engine.py`

NumbaEngine — JIT-функция, не принимает `extra_data`. Нужно добавить аргументы:

В Python-обёртке над Numba-функцией (не в самой `@njit` функции) — передать массивы:

```python
# В методе/функции, вызывающей Numba-ядро:
po_exit_arr = extra_data["profit_only_exits"].values if "profit_only_exits" in extra_data \
              else np.zeros(n, dtype=np.bool_)
po_sexit_arr = extra_data["profit_only_short_exits"].values if "profit_only_short_exits" in extra_data \
               else np.zeros(n, dtype=np.bool_)
min_profit_exit = float(extra_data.get("min_profit_exits", 0.0))
min_profit_sexit = float(extra_data.get("min_profit_short_exits", 0.0))
```

В сигнатуре Numba-функции добавить параметры:

```python
# po_exit_arr: np.ndarray[bool], po_sexit_arr: np.ndarray[bool]
# min_profit_exit: float, min_profit_sexit: float
```

В сигнал-exit блоке (строки ~192–196) применить логику аналогично FallbackEngineV4.

> **Альтернатива:** Если изменение сигнатуры Numba-функции затруднено (re-compilation),
> допустимо применять фильтр в Python-обёртке post-hoc: удалять трейды из результата
> NumbaEngine, которые должны были быть подавлены. Это менее точно, но не требует
> изменения JIT-ядра.

### Граничные условия

- Несколько `close_cond` блоков у одной стратегии → используется `max(min_profit)`
- `min_profit` в params — **проценты** (`1.0 = 1%`); в `extra_data` — **доли** (`0.01 = 1%`)
- Глобальный `close_only_in_profit` сохраняет обратную совместимость (`min_profit = 0.0`)
- Если `profit_only_exits` — все `False` (ни один блок не активировал) — не писать в `extra_data` (оптимизация, избегаем лишних numpy операций в движке)

### Тест

```python
def test_profit_only_exit_not_fired_at_loss():
    # Создать стратегию с close_rsi(profit_only=True, min_profit=1.0%)
    # Установить цену так, чтобы в момент RSI-сигнала позиция убыточная
    # Ожидать: позиция НЕ закрыта по сигналу RSI
    ...

def test_profit_only_exit_fires_above_min():
    # Аналогично, но цена выше entry + 1.1%
    # Ожидать: позиция закрыта
    ...
```

---

## <a name="feature2"></a>Фича 2 — MTF таймфрейм для `mfi_filter` и `cci_filter`

### Описание проблемы

Блоки `mfi_filter` и `cci_filter` имеют параметр `mfi_timeframe` / `cci_timeframe`
(выпадающий список в UI). Если пользователь выбирает, например, `"1h"` при
основном таймфрейме `"15"`, хэндлер это игнорирует и вычисляет MFI/CCI на
основном OHLCV. В лог пишется предупреждение. Фактическая фильтрация на
старшем таймфрейме не работает.

### Текущее состояние

В `indicator_handlers.py` уже есть `_handle_mtf` (строки 934–1006), который делает
MTF через `resample()` + `ffill()`. Именно эта механика нужна для MFI/CCI.

`_handle_mtf` имеет локальный `tf_map` (строки ~970–977):

```python
tf_map = {
    "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D", "1w": "1W",
}
```

> **Проблема:** Нет числовых таймфреймов Bybit (`"1"`, `"5"`, `"15"`, `"60"`, `"240"`)
> и нет `"D"`, `"W"`, `"M"`. UI фильтров (mfi/cci) может присылать строки в любом формате.
> `_resample_ohlcv` должна покрывать оба формата.

Текущие `_handle_mfi_filter` и `_handle_cci_filter` (строки 1405–1424, 1466–1481):

### Требуемая реализация

**Файл:** `backend/backtesting/indicator_handlers.py`

#### 2.1 — Вынести MTF-ресамплинг в утилитарную функцию

Создать приватную функцию (до блока хэндлеров, можно рядом с `_handle_mtf`):

```python
# Покрывает числовые таймфреймы Bybit API ("1", "5", "15", "60", "240", "D")
# и строковые алиасы из UI ("1m", "1h", "4h", "1d")
_TF_RESAMPLE_MAP: dict[str, str] = {
    # Bybit API numeric format
    "1": "1min", "3": "3min", "5": "5min", "15": "15min",
    "30": "30min", "60": "1h", "120": "2h", "240": "4h",
    "D": "1D", "W": "1W", "M": "1ME",
    # UI string aliases
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1D", "1w": "1W",
}

def _resample_ohlcv(ohlcv: pd.DataFrame, timeframe: str) -> pd.DataFrame | None:
    """Ресамплировать OHLCV на старший таймфрейм.

    Возвращает None если таймфрейм не поддерживается.
    Результат reindexed + ffill на исходный индекс ohlcv.index.
    Поддерживает DatetimeTZAware и числовой (timestamp ms) индексы.
    """
    rule = _TF_RESAMPLE_MAP.get(str(timeframe))
    if rule is None:
        logger.warning("MTF: unknown timeframe '{}', skipping resample", timeframe)
        return None

    # Если индекс числовой (timestamp ms) — конвертировать временно
    numeric_index = not isinstance(ohlcv.index, pd.DatetimeIndex)
    working = ohlcv
    if numeric_index:
        working = ohlcv.copy()
        working.index = pd.to_datetime(working.index, unit="ms", utc=True)

    try:
        htf = (
            working.resample(rule)
            .agg({"open": "first", "high": "max", "low": "min",
                  "close": "last", "volume": "sum"})
            .dropna()
        )
        if len(htf) < 2:
            logger.warning("MTF: resample tf='{}' produced <2 bars, fallback", timeframe)
            return None
        # Reindex обратно на исходный индекс (ffill = last-known значение)
        result = htf.reindex(working.index).ffill()
        if numeric_index:
            result.index = ohlcv.index  # восстановить числовой индекс
        return result
    except Exception as e:
        logger.warning("MTF resample error for tf='{}': {}", timeframe, e)
        return None
```

#### 2.2 — Патч `_handle_mfi_filter`

Заменить текущий блок (строки ~1413–1436):

```python
def _handle_mfi_filter(params, ohlcv, close, inputs, adapter):
    mfi_len = int(params.get("mfi_length", 14))
    mfi_tf = params.get("mfi_timeframe", "Chart")

    working_ohlcv = ohlcv
    main_tf = str(adapter.main_interval)
    resolved_tf = main_tf if str(mfi_tf).lower() == "chart" else str(mfi_tf)

    if resolved_tf != main_tf:
        htf_ohlcv = _resample_ohlcv(ohlcv, resolved_tf)
        if htf_ohlcv is not None:
            working_ohlcv = htf_ohlcv
            logger.debug("MFI filter: using HTF ohlcv tf={}", resolved_tf)
        else:
            logger.warning(
                "MFI filter: resample to '{}' failed, falling back to main tf='{}'",
                resolved_tf, main_tf,
            )

    mfi_vals = pd.Series(
        calculate_mfi(
            working_ohlcv["high"].values,
            working_ohlcv["low"].values,
            working_ohlcv["close"].values,
            working_ohlcv["volume"].values.astype(float),
            period=mfi_len,
        ),
        index=ohlcv.index,  # всегда исходный индекс (reindex уже сделан)
    )
    # ... остальной код (long_signal / short_signal / ranges) без изменений
```

Удалить `# BUG-WARN: mfi_timeframe ...` (строки 1413–1415).

#### 2.3 — Патч `_handle_cci_filter`

Аналогично п. 2.2, используя:

- `cci_timeframe` вместо `mfi_timeframe`
- `calculate_cci(working_ohlcv["high"], working_ohlcv["low"], working_ohlcv["close"], period)` вместо `calculate_mfi`

Удалить `# BUG-WARN: cci_timeframe ...` (строки 1472–1474).

### Граничные условия

| Ситуация                                              | Ожидаемое поведение                           |
| ----------------------------------------------------- | --------------------------------------------- |
| `mfi_timeframe = "Chart"`                             | работает на основном OHLCV, как сейчас        |
| `mfi_timeframe` = младший таймфрейм (5m при main=15m) | warning + fallback на main                    |
| Индекс OHLCV — целочисленный (timestamp ms)           | конвертировать в DatetimeIndex перед resample |
| HTF даёт < 2 баров (слишком мало данных)              | warning + fallback на main                    |

### Тест

```python
def test_mfi_filter_htf_uses_resampled_ohlcv():
    # 500 баров 15-минутного OHLCV
    # mfi_filter с mfi_timeframe="1h"
    # Проверить: mfi_vals на HTF-барах ~= mfi_vals на 1h-ресамплированном OHLCV
    ...

def test_mfi_filter_chart_tf_unchanged():
    # mfi_timeframe="Chart" → результат идентичен текущему поведению
    ...
```

---

## <a name="feature3"></a>Фича 3 — `use_btcusdt_mfi` (MFI по данным BTCUSDT)

### Описание проблемы

В блоке `mfi_filter` есть параметр `use_btcusdt_mfi: bool`. Идея: вычислять
MFI не по торгуемому символу (например, ETHUSDT), а по BTCUSDT — как прокси
доминирования рынка. Полностью не реализовано.

### Сложность

Это сложнее чем MTF-ресамплинг, потому что требует **загрузки данных другого
символа** во время выполнения `generate_signals`. Хэндлер получает только OHLCV
текущего символа — доступа к DataService у него нет.

### Требуемая реализация

#### Шаг 1 — Роутер: предзагрузить BTCUSDT OHLCV и передать в адаптер

> **Правило:** НЕ использовать `asyncio.run()` внутри `generate_signals` —
> FastAPI уже имеет event loop. Загрузка должна происходить в async роутере
> до вызова адаптера.

**Файл:** `backend/api/routers/backtesting.py` (или аналогичный роутер бэктеста)

```python
# В async роутере перед созданием адаптера:
btcusdt_ohlcv = None
if strategy_uses_btcusdt_mfi(strategy_config):  # проверить граф
    if symbol != "BTCUSDT":
        from backend.services.data_service import DataService
        svc = DataService()
        btcusdt_ohlcv = await svc.load_ohlcv(
            "BTCUSDT", interval, start_dt, end_dt
        )

adapter = StrategyBuilderAdapter(
    ...,
    btcusdt_ohlcv=btcusdt_ohlcv,  # новый kwarg
)
```

#### Шаг 2 — Адаптер: принять и хранить BTCUSDT OHLCV

**Файл:** `backend/backtesting/strategy_builder_adapter.py`

В `__init__` добавить параметр:

```python
def __init__(self, ..., btcusdt_ohlcv: pd.DataFrame | None = None):
    ...
    self._btcusdt_ohlcv: pd.DataFrame | None = btcusdt_ohlcv
```

Вспомогательный метод для проверки графа:

```python
def _requires_btcusdt_data(self) -> bool:
    """Возвращает True если любой блок mfi_filter имеет use_btcusdt_mfi=True."""
    for block in self.blocks.values():
        if block.get("type") == "mfi_filter":
            if block.get("params", {}).get("use_btcusdt_mfi", False):
                return True
    return False
```

#### Шаг 3 — Хэндлер: использовать `adapter._btcusdt_ohlcv`

В `_handle_mfi_filter` (совмещается с Фичей 2):

```python
use_btc = params.get("use_btcusdt_mfi", False)
if use_btc:
    if adapter._btcusdt_ohlcv is not None:
        # Выровнять индекс на случай если BTCUSDT имеет другой DatetimeIndex
        btc_ohlcv = adapter._btcusdt_ohlcv.reindex(ohlcv.index).ffill()
        working_ohlcv = btc_ohlcv
        logger.debug("MFI filter: using BTCUSDT OHLCV as source")
    else:
        logger.warning(
            "MFI filter: use_btcusdt_mfi=True but BTCUSDT data not loaded "
            "(symbol already BTCUSDT, or router did not preload); "
            "falling back to current symbol."
        )
```

### Граничные условия

| Ситуация                                           | Ожидаемое поведение                                                                                                              |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `use_btcusdt_mfi=True`, символ уже BTCUSDT         | `_requires_btcusdt_data()` возвращает True, но роутер передаёт `btcusdt_ohlcv=None`; хэндлер логирует и использует текущий OHLCV |
| BTCUSDT OHLCV имеет другой DatetimeIndex           | Выровнять через `reindex(ohlcv.index).ffill()`                                                                                   |
| DataService недоступен или вернул пустой DataFrame | warning + fallback на текущий символ                                                                                             |
| `use_btcusdt_mfi=False` (дефолт)                   | без изменений, BTCUSDT не загружается                                                                                            |

> **Архитектурное правило:** `generate_signals` остаётся синхронным.
> Вся async-логика загрузки данных — в роутере перед созданием адаптера.
> `StrategyBuilderAdapter.__init__` принимает уже готовый DataFrame.

---

## Порядок реализации (рекомендуется)

```
Фича 2 (MTF resample) → Фича 1 (profit_only) → Фича 3 (btcusdt)
```

- Фича 2 — изолированная, не трогает движок, риск минимальный
- Фича 1 — требует патча движка + NumbaEngineV2, риск средний
- Фича 3 — архитектурно сложная (async + DataService), делать последней

---

## Проверка системы после реализации

После каждой фичи запускать:

```bash
# 1. Проверка реестра блоков
py -3.14 -c "
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
p = StrategyBuilderAdapter._check_registry_consistency()
print('Проблемы реестра:', p if p else 'Нет')
"

# 2. Unit-тесты адаптера
pytest tests/backend/backtesting/ -v -x -q

# 3. Parity-тест
pytest tests/backend/backtesting/test_strategy_builder_parity.py -v

# 4. Весь suite
pytest tests/ -v -m "not slow" -q
```

---

## Файлы для изменения

| Файл                                                | Фича    | Тип изменения                                                                                                                                                                   |
| --------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/backtesting/indicator_handlers.py`         | 2, 3    | Добавить `_TF_RESAMPLE_MAP` + `_resample_ohlcv()`; патч `_handle_mfi_filter`, `_handle_cci_filter`; удалить BUG-WARN комментарии                                                |
| `backend/backtesting/strategy_builder_adapter.py`   | 1, 3    | Расширить `if target_port == "close_cond":` (строки ~3270–3291); добавить сбор в `extra_data`; добавить `btcusdt_ohlcv` kwarg в `__init__`; добавить `_requires_btcusdt_data()` |
| `backend/backtesting/engine.py`                     | 1       | После строки ~1285: читать `profit_only_*` из `extra_data`; заменить signal-exit блок (строки ~1780–1797)                                                                       |
| `backend/backtesting/numba_engine.py`               | 1       | Передать `po_exit_arr`/`po_sexit_arr`/`min_profit_*` как numpy arrays в Numba-ядро; расширить signal-exit блок (строки ~192–196)                                                |
| `backend/api/routers/backtesting.py` _(или аналог)_ | 3       | Async предзагрузка BTCUSDT OHLCV перед созданием адаптера                                                                                                                       |
| `tests/backend/backtesting/`                        | 1, 2, 3 | Новые unit-тесты (см. блоки "Тест" выше)                                                                                                                                        |
