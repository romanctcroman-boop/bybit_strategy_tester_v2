# Цепочка синхронизации тикеров: фронтенд → API → БД → Bybit

Документ описывает полный поток данных при синхронизации тикеров на странице Strategy Builder.

## 1. Фронтенд (strategy-builder.html + strategy_builder.js)

### Загрузка страницы

1. **Инициализация** (`initializeStrategyBuilder`):
   - Проверка связи с бэкендом (`/healthz`), баннер при `file://` или недоступном бэкенде.
   - Загрузка стратегии по `?id=...` или создание новой.
   - `renderBlockLibrary`, `renderTemplates`, `setupEventListeners`, `syncStrategyNameDisplay`, `initSymbolPicker`.
   - Тикеры предзагружаются только в **initSymbolPicker** (один раз: `fetchBybitSymbols`, `fetchBlockedSymbols`).
   - `initConnectionSystem`, `renderBlocks`, `updateBacktestPositionSizeInput`, `updateBacktestLeverageDisplay`, `updateBacktestLeverageRisk`.
   - После загрузки стратегии по ID вызывается `runCheckSymbolDataForProperties()` — сразу запускается проверка/синхронизация для загруженного символа и TF.

2. **Панель «База данных»** (`initDunnahBasePanel`):
   - Один запрос `GET /api/v1/marketdata/symbols/db-groups` при инициализации.
   - `refreshDunnahBasePanel` вызывается после успешной синхронизации тикера — обновляет список групп в БД.

### Триггеры синхронизации

| Событие | Действие | Задержка |
|--------|----------|----------|
| Выбор тикера из выпадающего списка | `onSymbolSelected` → `runCheckSymbolDataForProperties()` | Сразу |
| Смена Symbol (ручной ввод, blur) | `change` → `checkSymbolDataForProperties` | Debounce 200 ms |
| Смена таймфрейма | `change` → `checkSymbolDataForProperties` + `setupAutoRefresh(sym)` | Debounce 200 ms |
| Смена типа рынка (Spot/Linear) | `change` → сброс кэшей, `checkSymbolDataForProperties` | Debounce 200 ms |
| Кнопка «Обновить» / авто-обновление | `syncSymbolData(true)` | Сразу |
| Клик по блоку статуса при ошибке | `syncSymbolData(true)` | Сразу |

### Логика syncSymbolData(forceRefresh)

1. Чтение символа и типа рынка из DOM.
2. Проверка блокировки тикера (`blockedSymbolsCache`).
3. Проверка «уже синхронизируется» (`symbolSyncInProgress[symbol]`).
4. **Отмена предыдущей синхронизации** при переключении тикера: `currentSyncAbortController.abort()`. В обработчике отмены **не** сбрасывать прогресс и global loading — новая синхронизация уже отрисовала свой UI.
5. Проверка «недавно синхронизирован» (30 с), если не `forceRefresh` — пропуск.
6. Показать строку статуса, прогресс-бар (indeterminate), global loading.
7. `POST /api/v1/marketdata/symbols/sync-all-tf?symbol=...&market_type=...` с таймаутом 240 с и `AbortController`.
8. Успех: обновить статус «Синхронизировано», скрыть прогресс, `setupAutoRefresh(symbol)`, `refreshDunnahBasePanel()`.
9. Ошибка/таймаут: показать сообщение, скрыть прогресс. При отмене из-за смены тикера — не трогать UI.

### Кэши и состояние

- `bybitSymbolsCache`, `localSymbolsCache`, `blockedSymbolsCache`, `tickersDataCache` — для выпадающего списка и блокировок.
- `symbolSyncCache[symbol]` — время последней успешной синхронизации (пропуск повтора в 30 с).
- `symbolSyncInProgress` — флаг «идёт синхронизация» по символу.
- `currentSyncAbortController` — отмена при смене тикера.

---

## 2. API (backend/api/routers/marketdata.py)

### POST /api/v1/marketdata/symbols/sync-all-tf

- **Параметры:** `symbol`, `market_type` (linear/spot).
- **Логика:**
  1. Запускается фоновая задача `_wait_client_disconnect(request)` — при отключении клиента (abort при смене тикера) синхронизация отменяется, сервер не блокируется на 180 с.
  2. Для каждого TF из `ALL_TIMEFRAMES` параллельно вызывается `sync_interval(tf)` с таймаутом по TF (1m: 45 с, остальные 30–60 с). Таймауты уменьшены, чтобы не блокировать сервер и следующий запрос.
  3. Используется `asyncio.wait(..., FIRST_COMPLETED)`: если первой завершилась проверка отключения — все TF отменяются и возвращается частичный результат; иначе ждём завершения всех TF.
  4. **sync_interval(tf):**
     - **Чтение БД** в потоке: `_get_kline_audit_state_sync(symbol, interval, market_type)` → `(latest_ts, earliest_ts)` из таблицы аудита.
     - Решение: нужен full load / backfill / update по порогам свежести (`freshness_thresholds`).
     - **Запрос к Bybit:** `adapter.get_historical_klines(...)` (асинхронно, пагинация с паузой 0.02 с между страницами).
     - **Запись в БД** в потоке: `_persist_klines_sync(adapter, symbol, rows, interval, market_type)` → `adapter._persist_klines_to_db(...)`.
  5. Ответ: `{ symbol, market_type, timeframes, total_new_candles, summary }`.

### GET /api/v1/marketdata/symbols/db-groups

- Агрегация по БД (BybitKlineAudit): группы по (symbol, market_type), интервалы, счётчики, список `blocked`.
- Используется панелью «База данных» и после синхронизации (`refreshDunnahBasePanel`).

### Блокировки тикеров

- `GET/POST/DELETE .../symbols/blocked` — список тикеров, для которых отключена догрузка.
- Фронт проверяет `blockedSymbolsCache` перед запуском синхронизации.

---

## 3. БД и адаптер

### Аудит (BybitKlineAudit)

- `_get_kline_audit_state_sync`: два запроса (latest, earliest) по (symbol, interval, market_type).
- Используется для определения: полная загрузка, backfill или только обновление до текущего времени.

### Запись свечей

- `adapter._persist_klines_to_db(symbol, rows_with_interval, market_type)`:
  - Запись в таблицу свечей и обновление BybitKlineAudit (symbol, interval, market_type, open_time и т.д.).

### Bybit (backend/services/adapters/bybit.py)

- `get_historical_klines`: пагинация по 1000 свечей, пауза **0.02 с** между страницами (лимит Bybit ~120 req/s по IP).
- Синхронный вариант `get_klines_historical` — тоже 0.02 с между страницами.

---

## 4. Итоговая схема

```
[Страница Strategy Builder]
  → initSymbolPicker: fetchBybitSymbols, fetchBlockedSymbols (один раз)
  → initDunnahBasePanel: GET db-groups (один раз)
  → Смена Symbol/TF/типа рынка → checkSymbolDataForProperties (debounce 200 ms)
  → Выбор тикера из списка → runCheckSymbolDataForProperties() сразу

runCheckSymbolDataForProperties / checkSymbolDataForProperties
  → syncSymbolData(false/true)
      → Проверки (blocked, in progress, recent 30s)
      → Отмена предыдущего запроса при смене тикера (без сброса UI новой синхронизации)
      → POST sync-all-tf

[Backend] sync-all-tf
  → Для каждого TF параллельно:
      → _get_kline_audit_state_sync (БД)
      → adapter.get_historical_klines (Bybit, 0.02 с между страницами)
      → _persist_klines_sync → _persist_klines_to_db (БД)
  → Ответ: total_new_candles, summary

[Фронт] после успеха
  → Статус «Синхронизировано», скрыть прогресс
  → setupAutoRefresh(symbol)
  → refreshDunnahBasePanel() → GET db-groups, перерисовка панели «База данных»
```

---

## 5. Что может блокировать запросы к Bybit

- **Один глобальный адаптер** (`get_bybit_adapter()` в marketdata.py) — все запросы (синхронизация, instrument-info, tickers, klines) идут через один экземпляр. Конкурентные вызовы не блокируют друг друга (адаптер не держит общий lock на время запроса к Bybit), но при очень тяжёлой синхронизации (много пагинации по 1m) event loop занят обработкой одного стрима.
- **Circuit breaker** (backend/core/circuit_breaker.py): при частых ошибках Bybit (429, 5xx, таймауты) цепь переходит в состояние OPEN и все вызовы к Bybit возвращают ошибку «Circuit breaker OPEN». В логах будет строка вида `Circuit bybit_api: closed -> open`. После таймаута (по умолчанию) цепь переходит в HALF_OPEN и снова разрешает вызовы. Если видите «запросы к Bybit блокируются» — проверьте логи на `Circuit` и сбросьте цепь при необходимости (API сброса есть в rate_limit_dashboard / circuit breaker, если подключён).

---

## 6. Свежесть данных и нахлёст (overlap): почему «11 свечей»

- **Порог свежести (freshness)** для 1m — **2 минуты** (`freshness_thresholds["1"] = 2 * 60000`). Если последняя свеча в БД новее (now - 2 min), данные считаются «свежими» и полный update не делается (или делается только лёгкий update).
- **Интервал между загрузками < 2 минут**: для 1m данные могут ещё считаться свежими, поэтому при повторной синхронизации запрашивается только **обновление до текущего времени с нахлёстом**.
- **Нахлёст (OVERLAP_CANDLES)**: при догрузке до текущего времени запрашиваются не только «новые» свечи, но и **несколько последних уже сохранённых** (overlap), чтобы не было разрыва на границе. Для 1m–1h overlap = 5 свечей, для 4h = 4, для D/W/M меньше.
- **Итого:** при интервале между загрузками меньше 2 минут и обновлении по 1m вы получаете **overlap (5) + новые свечи**. Например, **11 свечей = 5 (нахлёст) + 6 новых** (6 минут). Это нормальное поведение: нахлёст устраняет возможные пропуски на стыке, остальное — реально новые данные.

---

## 7. Уже сделанные оптимизации

- Один предзагруз тикеров в initSymbolPicker (без дубля в init).
- Debounce 200 ms для смены Symbol/TF/типа рынка.
- При отмене синхронизации из-за смены тикера не сбрасывать прогресс и global loading.
- Пауза в адаптере Bybit 0.02 с вместо 0.1 с между страницами пагинации.
- После загрузки стратегии по ID — сразу `runCheckSymbolDataForProperties()`.
- После успешной синхронизации убран лишний вызов `checkSymbolDataForProperties()`.
- **Сервер:** при отключении клиента (abort) синхронизация отменяется (`_wait_client_disconnect` + отмена задач), чтобы следующий запрос (новый тикер) не ждал 180 с.
- **Сервер:** таймауты по TF уменьшены (1m: 45 с вместо 180 с), чтобы запрос не висел 3 минуты; тяжёлый 1m при необходимости можно повторить.

---

_Обновлено: 2026-02-01 (блокировки Bybit, свежесть и нахлёст)_
