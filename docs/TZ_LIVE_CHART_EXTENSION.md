# ТЗ: Live Chart — Расширение MVP (P1 + P2)

**Версия:** 1.0
**Дата:** 2026-03-04
**Статус:** Готово к реализации
**Автор:** Claude Code (анализ кодовой базы)

---

## Содержание

1. [Обзор](#1-обзор)
2. [P1: Сохранение live-свечей в БД](#2-p1-сохранение-live-свечей-в-бд)
3. [P2: Extend Backtest to Now](#3-p2-extend-backtest-to-now)
4. [Алгоритм нахлёста (существующий)](#4-алгоритм-нахлёста-существующий)
5. [API контракты](#5-api-контракты)
6. [Frontend изменения](#6-frontend-изменения)
7. [Тесты](#7-тесты)
8. [Что НЕ нужно менять](#8-что-не-нужно-менять)

---

## 1. Обзор

### Что уже работает (MVP)

```
Bybit WS → LiveChartSessionManager → SSE → EventSource → LightweightCharts
```

- Реальный тайм стриминг свечей ✅
- Проверка условий стратегии на каждом закрытом баре ✅
- Gap-fill при первом подключении и переподключении ✅

### Что НЕ работает (задачи этого ТЗ)

| ID  | Задача                                                                                                 | Приоритет |
| --- | ------------------------------------------------------------------------------------------------------ | --------- |
| P1  | Закрытые live-свечи сохраняются в `BybitKlineAudit`                                                    | Высокий   |
| P2  | "Extend Backtest to Now": догрузка пропущенного периода + повторный прогон стратегии + пересчёт метрик | Высокий   |

---

## 2. P1: Сохранение live-свечей в БД

### 2.1 Зачем

Без сохранения:

- При следующей сессии warmup-данных для сигналов не хватает
- Каждый раз нужно ждать накопления минимального warmup (500 баров)
- Данные теряются при перезапуске сервера

С сохранением:

- Warmup всегда актуален
- P2 (Extend Backtest) может использовать свежие данные
- База растёт органически по мере работы

### 2.2 Архитектурное решение

**Проблема:** SSE endpoint держит `db: Session` открытой на всё время стриминга (часы). Нельзя использовать её для записи каждой свечи — риск конкуренции и утечки транзакций.

**Решение:** Отдельная `SessionLocal()` на каждый закрытый бар, в фоновом `asyncio.Task`.

```
event_generator()
    ↓  bar_closed event
    asyncio.create_task(_persist_live_bar(symbol, interval, market_type, candle))
    ↓  (не ждём — не блокируем SSE)
    SSE → клиент
```

### 2.3 Новая функция `_persist_live_bar()`

**Файл:** `backend/api/routers/marketdata.py`

```python
async def _persist_live_bar(
    symbol: str,
    interval: str,
    market_type: str,
    candle: dict,
) -> None:
    """
    Сохранить один закрытый live-бар в BybitKlineAudit.
    Запускается как фоновый asyncio.Task из SSE event_generator.

    Использует отдельную SessionLocal — не зависит от SSE-сессии.
    UPSERT: ON CONFLICT (symbol, interval, market_type, open_time) DO UPDATE SET...
    """
    from backend.database import SessionLocal
    from backend.models.bybit_kline_audit import BybitKlineAudit as KlineModel

    open_time_ms = candle["time"] * 1000  # секунды → миллисекунды

    try:
        await asyncio.to_thread(_persist_live_bar_sync, symbol, interval, market_type, candle, open_time_ms)
    except Exception as exc:
        logger.warning("[LiveChart] Failed to persist live bar %s/%s@%d: %s", symbol, interval, open_time_ms, exc)


def _persist_live_bar_sync(
    symbol: str,
    interval: str,
    market_type: str,
    candle: dict,
    open_time_ms: int,
) -> None:
    """Синхронная запись — выполняется в thread pool."""
    from backend.database import SessionLocal
    from sqlalchemy import text

    row = {
        "symbol": symbol,
        "interval": interval,
        "market_type": market_type,
        "open_time": open_time_ms,
        "open_time_dt": None,  # опционально: datetime.utcfromtimestamp(candle["time"])
        "open_price": candle["open"],
        "high_price": candle["high"],
        "low_price": candle["low"],
        "close_price": candle["close"],
        "volume": candle["volume"],
        "turnover": candle.get("volume", 0),  # turnover недоступен из WS tick
        "raw": "{}",  # WS данные не содержат сырой JSON
    }

    with SessionLocal() as session:
        # Тот же UPSERT что использует _persist_klines_to_db()
        dialect = session.bind.dialect.name
        if dialect in ("postgres", "postgresql"):
            sql = text("""
                INSERT INTO bybit_kline_audit
                    (symbol, interval, market_type, open_time, open_price, high_price,
                     low_price, close_price, volume, turnover, raw)
                VALUES
                    (:symbol, :interval, :market_type, :open_time, :open_price,
                     :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                ON CONFLICT (symbol, interval, market_type, open_time) DO UPDATE SET
                    high_price   = GREATEST(EXCLUDED.high_price, bybit_kline_audit.high_price),
                    low_price    = LEAST(EXCLUDED.low_price, bybit_kline_audit.low_price),
                    close_price  = EXCLUDED.close_price,
                    volume       = EXCLUDED.volume
            """)
        else:  # SQLite
            sql = text("""
                INSERT INTO bybit_kline_audit
                    (symbol, interval, market_type, open_time, open_price, high_price,
                     low_price, close_price, volume, turnover, raw)
                VALUES
                    (:symbol, :interval, :market_type, :open_time, :open_price,
                     :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                ON CONFLICT(symbol, interval, market_type, open_time) DO UPDATE SET
                    high_price  = MAX(EXCLUDED.high_price, bybit_kline_audit.high_price),
                    low_price   = MIN(EXCLUDED.low_price, bybit_kline_audit.low_price),
                    close_price = EXCLUDED.close_price,
                    volume      = EXCLUDED.volume
            """)
        session.execute(sql, row)
        session.commit()
```

> **Примечание:** Для PostgreSQL используем `GREATEST/LEAST` для H/L — на случай если свеча уже была записана как частичная (tick). Для SQLite — `MAX/MIN`.

### 2.4 Изменение `event_generator()` в SSE endpoint

**Файл:** `backend/api/routers/marketdata.py`

Текущий код (найти):

```python
# Для закрытых баров: вычислить сигналы стратегии
if event["type"] == "bar_closed" and signal_service is not None:
    signals = signal_service.push_closed_bar(event["candle"])
    event["signals"] = signals
```

Заменить на:

```python
# Для закрытых баров: вычислить сигналы стратегии + сохранить в БД
if event["type"] == "bar_closed":
    if signal_service is not None:
        signals = signal_service.push_closed_bar(event["candle"])
        event["signals"] = signals

    # Сохранить в БД фоново (не блокирует SSE поток)
    # market_type берём из параметра запроса или default "linear"
    asyncio.create_task(
        _persist_live_bar(symbol, interval, _live_market_type, event["candle"])
    )
```

### 2.5 Передача market_type в SSE endpoint

Добавить query-параметр в сигнатуру:

```python
@router.get("/live-chart/stream")
async def live_chart_stream(
    symbol: str = Query(...),
    interval: str = Query(...),
    session_id: str = Query(...),
    strategy_id: int | None = Query(None),
    market_type: str = Query("linear", description="spot или linear"),  # ← ДОБАВИТЬ
    last_event_id: str | None = Query(None, alias="lastEventId"),
    db: Session = Depends(get_db),
):
```

И обновить JS `startLiveChart` (см. §6.1).

### 2.6 Ограничения P1

| Ограничение                 | Объяснение                                                                     |
| --------------------------- | ------------------------------------------------------------------------------ |
| `turnover` недоступен из WS | WS тик не содержит оборот — пишем `volume` как приближение                     |
| `raw` = `"{}"`              | Raw JSON недоступен из callback — поле не NULL благодаря NOT NULL DEFAULT      |
| SQLite без `GREATEST/LEAST` | Используется `MAX/MIN` встроенные функции SQLite                               |
| Нет retry при ошибке записи | `logger.warning` достаточно — пропущенная свеча восполнится при следующем sync |

---

## 3. P2: Extend Backtest to Now

### 3.1 Концепция

Когда пользователь нажимает **"Extend to Now"** (или при открытии Live Chart если `backtest.end_date < now - 1 hour`):

```
1. Определить gap: backtest.end_date → now
2. Догрузить свечи с Bybit (с нахлёстом) → BybitKlineAudit
3. Запустить стратегию на новом периоде → новые сигналы + сделки
4. Объединить: старые сделки + новые сделки
5. Пересчитать ВСЕ 166 метрик на объединённом наборе
6. Сохранить результат как новый бэктест (или обновить существующий)
```

### 3.2 Новый API endpoint

**Файл:** `backend/api/routers/backtests.py`

```python
@router.post("/{backtest_id}/extend")
async def extend_backtest_to_now(
    backtest_id: int,
    market_type: str = Query("linear"),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = ...,
) -> dict:
    """
    Догрузить пропущенные свечи и продолжить бэктест до текущего времени.

    Алгоритм:
    1. Загрузить оригинальный бэктест (config, trades, результаты)
    2. Определить gap: last_bar_time → now
    3. Sync свечей с нахлёстом (использует существующий _get_kline_audit_state_sync +
       adapter.get_historical_klines + _persist_klines_sync)
    4. Загрузить OHLCV за gap-период из БД
    5. Прогнать стратегию на gap-периоде с warmup из предшествующих N баров
    6. Объединить сделки
    7. Пересчитать метрики на полном периоде (оригинал + gap)
    8. Сохранить как новый бэктест с prefix "Extended: "

    Returns: {backtest_id: int, new_trades: int, new_metrics: dict}
    """
    ...
```

### 3.3 Детальный алгоритм

#### Шаг 1: Загрузка оригинального бэктеста

```python
from backend.database.models.backtest import Backtest as BacktestModel

orig = db.query(BacktestModel).filter(BacktestModel.id == backtest_id).first()
if not orig:
    raise HTTPException(404)

config_dict = orig.config  # dict — BacktestConfig
symbol = config_dict["symbol"]
interval = config_dict["interval"]  # уже в Bybit формате: "30", "60", "D" etc.

# Определить конец бэктеста (последняя свеча или end_date из config)
backtest_end_ms = orig.end_time  # int, milliseconds
# Или из сделок: max(trade.exit_time) если есть
```

#### Шаг 2: Определить gap

```python
now_ms = int(time.time() * 1000)

# Преобразовать interval в миллисекунды
INTERVAL_MS = {
    "1": 60_000, "5": 300_000, "15": 900_000, "30": 1_800_000,
    "60": 3_600_000, "240": 14_400_000, "D": 86_400_000,
    "W": 604_800_000, "M": 2_592_000_000,
}
interval_ms = INTERVAL_MS.get(interval, 3_600_000)

# Есть ли смысл продолжать? Минимум 2 свечи
if (now_ms - backtest_end_ms) < interval_ms * 2:
    return {"status": "already_current", "new_trades": 0}
```

#### Шаг 3: Догрузка свечей с нахлёстом

**Использовать существующий алгоритм нахлёста** из `OVERLAP_CANDLES`:

```python
from backend.api.routers.marketdata import OVERLAP_CANDLES, _persist_klines_sync
from backend.services.adapters.bybit import BybitAdapter

adapter = BybitAdapter()

overlap = OVERLAP_CANDLES.get(interval, 3)
# Начинаем на overlap свечей РАНЬШЕ конца бэктеста
# (нахлёст гарантирует что граница правильно сшита с существующими данными)
start_ts = backtest_end_ms - (interval_ms * overlap)

logger.info(
    "[ExtendBacktest] Fetching %s/%s from %d to %d (overlap=%d bars)",
    symbol, interval, start_ts, now_ms, overlap,
)

rows = await adapter.get_historical_klines(
    symbol=symbol,
    interval=interval,
    start_time=start_ts,
    end_time=now_ms,
    limit=1000,
    market_type=market_type,
)

if rows:
    # Сохранить в БД (UPSERT — нахлёстные свечи обновятся, новые вставятся)
    await asyncio.to_thread(_persist_klines_sync, adapter, symbol, rows, interval, market_type)
    logger.info("[ExtendBacktest] Persisted %d candles to DB", len(rows))
```

#### Шаг 4: Загрузить OHLCV за gap-период для прогона стратегии

```python
from backend.services.data_service import DataService

data_svc = DataService()

# Warmup: загрузить N баров ДО конца бэктеста для прогрева индикаторов
STRATEGY_WARMUP_BARS = 500

warmup_start_ms = backtest_end_ms - (interval_ms * STRATEGY_WARMUP_BARS)

# Весь период: warmup + gap
full_df = await asyncio.to_thread(
    data_svc.load_ohlcv,
    symbol=symbol,
    timeframe=interval,
    start=warmup_start_ms,
    end=now_ms,
    market_type=market_type,
)

if full_df is None or len(full_df) < STRATEGY_WARMUP_BARS + 2:
    raise HTTPException(400, "Insufficient data for strategy computation")
```

#### Шаг 5: Прогон стратегии только на gap-периоде

```python
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.backtesting.models import BacktestConfig

# Восстановить конфиг из оригинального бэктеста
bt_config = BacktestConfig(**config_dict)

# Генерировать сигналы на ВСЁМ периоде (warmup + gap)
if orig.is_builder_strategy and orig.strategy.builder_graph:
    adapter_obj = StrategyBuilderAdapter(orig.strategy.builder_graph)
    signal_result = adapter_obj.generate_signals(full_df)
else:
    strategy_cls = get_strategy_class(bt_config.strategy_type)
    strategy_obj = strategy_cls(**bt_config.strategy_params)
    signal_result = strategy_obj.generate_signals(full_df)

# Обрезать: оставить только сигналы начиная с backtest_end_ms
# (warmup нужен для индикаторов, но сделки берём только с gap_start)
gap_start_idx = full_df.index.get_loc(
    full_df.index[full_df.index >= pd.Timestamp(backtest_end_ms, unit="ms", tz="UTC")][0]
)

gap_entries = signal_result.entries.iloc[gap_start_idx:]
gap_exits = signal_result.exits.iloc[gap_start_idx:]
gap_short_entries = signal_result.short_entries.iloc[gap_start_idx:] if signal_result.short_entries is not None else None
gap_short_exits = signal_result.short_exits.iloc[gap_start_idx:] if signal_result.short_exits is not None else None
gap_ohlcv = full_df.iloc[gap_start_idx:]
```

#### Шаг 6: Запустить движок на gap-периоде

```python
from backend.backtesting.engine import BacktestEngine

engine = BacktestEngine()

# Важно: начальный капитал = финальный капитал оригинального бэктеста
# (продолжение эквити-кривой)
gap_config = bt_config.model_copy(update={
    "start_date": pd.Timestamp(backtest_end_ms, unit="ms", tz="UTC").date().isoformat(),
    "end_date": pd.Timestamp(now_ms, unit="ms", tz="UTC").date().isoformat(),
    "initial_capital": orig.final_equity,  # ← капитал на момент конца оригинала
})

from backend.backtesting.strategies import SignalResult
gap_signal_result = SignalResult(
    entries=gap_entries,
    exits=gap_exits,
    short_entries=gap_short_entries,
    short_exits=gap_short_exits,
    entry_sizes=None,
    short_entry_sizes=None,
    extra_data=None,
)

gap_result = engine.run(gap_ohlcv, gap_signal_result, gap_config)
```

#### Шаг 7: Объединить сделки

```python
original_trades = orig.trades  # list[dict] из БД

# gap_result.trades — новые сделки
new_trades = gap_result.trades  # list[dict]

# Объединить и отсортировать по времени входа
all_trades = sorted(
    original_trades + new_trades,
    key=lambda t: t.get("entry_time", 0),
)
```

#### Шаг 8: Пересчитать метрики на ПОЛНОМ периоде

```python
from backend.core.metrics_calculator import MetricsCalculator

# Загрузить OHLCV оригинального периода + gap
full_period_df = await asyncio.to_thread(
    data_svc.load_ohlcv,
    symbol=symbol,
    timeframe=interval,
    start=orig.start_time,
    end=now_ms,
    market_type=market_type,
)

calc = MetricsCalculator()
new_metrics = calc.calculate_all(
    trades=all_trades,
    ohlcv=full_period_df,
    config=bt_config,
    initial_capital=bt_config.initial_capital,  # ← ОРИГИНАЛЬНЫЙ стартовый капитал
)
```

#### Шаг 9: Сохранить расширенный бэктест

```python
from backend.database.models.backtest import Backtest as BacktestModel

new_bt = BacktestModel(
    strategy_id=orig.strategy_id,
    symbol=symbol,
    interval=interval,
    market_type=market_type,
    start_time=orig.start_time,
    end_time=now_ms,
    config=config_dict,
    trades=all_trades,
    metrics=new_metrics,
    is_extended=True,         # ← новое поле (см. §3.4)
    source_backtest_id=orig.id,  # ← ссылка на оригинал
    created_at=datetime.utcnow(),
    name=f"Extended: {orig.name or orig.id}",
)
db.add(new_bt)
db.commit()
db.refresh(new_bt)

return {
    "status": "ok",
    "new_backtest_id": new_bt.id,
    "new_trades": len(new_trades),
    "gap_start": backtest_end_ms,
    "gap_end": now_ms,
    "new_metrics": new_metrics,
}
```

### 3.4 Изменения в БД-модели Backtest

**Файл:** `backend/database/models/backtest.py`

Добавить два поля:

```python
# Признак расширенного бэктеста
is_extended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

# Ссылка на оригинальный бэктест (если is_extended=True)
source_backtest_id: Mapped[int | None] = mapped_column(
    ForeignKey("backtests.id", ondelete="SET NULL"), nullable=True
)
```

**Новая Alembic миграция:**

```python
# versions/xxxx_add_backtest_extend_fields.py

def upgrade():
    op.add_column("backtests", sa.Column("is_extended", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("backtests", sa.Column("source_backtest_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_backtests_source_id", "backtests", "backtests",
        ["source_backtest_id"], ["id"], ondelete="SET NULL",
    )

def downgrade():
    op.drop_constraint("fk_backtests_source_id", "backtests", type_="foreignkey")
    op.drop_column("backtests", "source_backtest_id")
    op.drop_column("backtests", "is_extended")
```

### 3.5 Граничные случаи P2

| Случай                              | Обработка                                                                                                                                                         |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Нет новых сделок в gap-периоде      | Возвращаем `{new_trades: 0}`, метрики пересчитываем только по оригинальным сделкам с новой end_date                                                               |
| Открытая позиция на конец оригинала | `gap_config.initial_capital = orig.final_equity - open_position_value` (сложная логика) — **для MVP:** закрыть открытую позицию по last close и начать gap с нуля |
| Данных в БД до сих пор нет          | Перед шагом 5 запустить `sync_all_timeframes(symbol, market_type)` и дождаться результата                                                                         |
| Gap > 730 дней                      | Запрещено (validator limit). В этом случае создать новый полный бэктест вместо extend                                                                             |
| DCA стратегии                       | `dca_enabled=True` → использовать DCAEngine вместо обычного engine                                                                                                |

---

## 4. Алгоритм нахлёста (существующий)

Используется **без изменений** в P2 шаге 3. Документация для понимания:

### 4.1 Константы нахлёста

**Файл:** `backend/api/routers/marketdata.py:1611-1622`

```python
OVERLAP_CANDLES = {
    "1": 5,   "5": 5,   "15": 5,  "30": 5,
    "60": 5,  "240": 4, "D": 3,   "W": 2,  "M": 2,
}
```

### 4.2 Формула

```python
overlap = OVERLAP_CANDLES.get(interval, 3)
start_ts = latest_ts - (interval_ms * overlap)
```

Пример для 30m бэктест, последняя свеча в 10:00:

```
overlap = 5 свечей × 1_800_000 мс = 9_000_000 мс = 2.5 часа
start_ts = 10:00 - 2.5ч = 07:30
```

Загружается с 07:30. Свечи 07:30–10:00 уже есть в БД → UPSERT обновит их. Свечи 10:00–now — новые.

### 4.3 Зачем нахлёст

Bybit REST API может вернуть слегка другое значение `volume` для последней свечи (она ещё не закрылась в момент первоначальной загрузки). Нахлёст гарантирует что эти данные будут скорректированы.

---

## 5. API контракты

### 5.1 Новые параметры SSE endpoint (P1)

```
GET /api/v1/marketdata/live-chart/stream
  + market_type: "linear" | "spot"  (default: "linear")
```

### 5.2 Новый endpoint (P2)

```
POST /api/v1/backtests/{backtest_id}/extend

Query params:
  market_type: "linear" | "spot"  (default: "linear")

Response 200:
{
  "status": "ok" | "already_current" | "no_new_data",
  "new_backtest_id": int,
  "new_trades": int,
  "gap_start": int,   // ms timestamp
  "gap_end": int,     // ms timestamp
  "new_metrics": { ...166 метрик... }
}

Response 400:
{
  "detail": "Gap > 730 days — create a new backtest instead"
}

Response 404:
{
  "detail": "Backtest not found"
}

Response 503:
{
  "detail": "Could not fetch candles from Bybit: <error>"
}
```

### 5.3 Новый endpoint статуса SSE (уже есть)

```
GET /api/v1/marketdata/live-chart/status
Response: { active_sessions: int, sessions: [...] }
```

---

## 6. Frontend изменения

### 6.1 Добавить `market_type` в SSE URL (P1)

**Файл:** `frontend/js/pages/backtest_results.js`

Функция `startLiveChart(backtest)`:

```javascript
// Текущий код:
const params = new URLSearchParams({ symbol, interval, session_id: sessionId });
if (stratId) params.set("strategy_id", String(stratId));

// Добавить:
const marketType = backtest.config?.market_type || "linear";
params.set("market_type", marketType);
```

### 6.2 Кнопка "Extend to Now" (P2)

**Файл:** `frontend/backtest-results.html`

Добавить кнопку рядом с Live:

```html
<button id="btExtendBtn" class="bt-extend-btn" title="Продолжить бэктест до текущего времени">⟳ Extend</button>
```

**Файл:** `frontend/css/backtest_results.css`

```css
.bt-extend-btn {
    padding: 6px 12px;
    background: #1a73e8;
    color: #fff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s;
}
.bt-extend-btn:hover {
    background: #1558b0;
}
.bt-extend-btn:disabled {
    background: #555;
    cursor: not-allowed;
}
.bt-extend-btn.loading {
    background: #555;
    cursor: not-allowed;
}
```

**Файл:** `frontend/js/pages/backtest_results.js`

```javascript
/**
 * Extend the current backtest to current time.
 * POST /api/v1/backtests/{id}/extend
 */
async function extendBacktestToNow() {
    if (!currentBacktest) return;

    const btn = document.getElementById("btExtendBtn");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "⟳ Extending…";
        btn.classList.add("loading");
    }

    try {
        const marketType = currentBacktest.config?.market_type || "linear";
        const res = await fetch(`${API_BASE}/backtests/${currentBacktest.id}/extend?market_type=${marketType}`, { method: "POST" });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Extend failed");
        }

        const data = await res.json();

        if (data.status === "already_current") {
            window["showNotification"]?.("Бэктест уже актуален", "info");
            return;
        }

        // Загрузить новый бэктест
        await selectBacktest(data.new_backtest_id);
        window["showNotification"]?.(`Бэктест расширен: +${data.new_trades} сделок`, "success");
    } catch (e) {
        console.error("[ExtendBacktest]", e);
        window["showNotification"]?.(`Ошибка: ${e.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "⟳ Extend";
            btn.classList.remove("loading");
        }
    }
}

// Wire up button in updatePriceChart():
// const extendBtnEl = document.getElementById('btExtendBtn');
// if (extendBtnEl) {
//   const freshExtend = extendBtnEl.cloneNode(true);
//   extendBtnEl.replaceWith(freshExtend);
//   freshExtend.addEventListener('click', extendBacktestToNow);
// }
```

### 6.3 Индикатор расширенного бэктеста в списке

В функции отрисовки списка бэктестов добавить badge:

```javascript
// Если backtest.is_extended:
// <span class="badge-extended">Extended</span>
```

```css
.badge-extended {
    background: #1a73e8;
    color: #fff;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    margin-left: 4px;
}
```

---

## 7. Тесты

### 7.1 P1: Сохранение live-свечей

**Файл:** `tests/backend/services/test_live_signal_service.py` (дополнить существующий)
**Файл:** `tests/backend/api/routers/test_live_chart_persist.py` (новый)

```python
class TestPersistLiveBar:
    """Tests for _persist_live_bar_sync()."""

    def test_bar_inserted_to_db(self, tmp_db_session):
        """Closed bar is inserted into BybitKlineAudit."""
        candle = {"time": 1_700_000_000, "open": 100.0, "high": 101.0,
                  "low": 99.0, "close": 100.5, "volume": 500.0}
        _persist_live_bar_sync("ETHUSDT", "30", "linear", candle, candle["time"] * 1000)

        row = tmp_db_session.query(BybitKlineAudit).filter(
            BybitKlineAudit.symbol == "ETHUSDT",
            BybitKlineAudit.open_time == candle["time"] * 1000,
        ).first()
        assert row is not None
        assert row.close_price == pytest.approx(100.5)

    def test_upsert_updates_existing_bar(self, tmp_db_session):
        """Second write for same open_time updates H/L/C/Volume."""
        candle_v1 = {"time": 1_700_000_000, "open": 100.0, "high": 101.0,
                     "low": 99.0, "close": 100.5, "volume": 500.0}
        candle_v2 = {"time": 1_700_000_000, "open": 100.0, "high": 102.0,  # higher H
                     "low": 98.0, "close": 101.0, "volume": 600.0}

        _persist_live_bar_sync("ETHUSDT", "30", "linear", candle_v1, candle_v1["time"] * 1000)
        _persist_live_bar_sync("ETHUSDT", "30", "linear", candle_v2, candle_v2["time"] * 1000)

        row = tmp_db_session.query(BybitKlineAudit).filter(
            BybitKlineAudit.open_time == candle_v1["time"] * 1000
        ).first()
        assert row.high_price == pytest.approx(102.0)  # MAX(101, 102) = 102
        assert row.low_price == pytest.approx(98.0)    # MIN(99, 98) = 98

    def test_persist_error_does_not_raise(self, mocker):
        """DB error is logged as warning, not re-raised (non-critical path)."""
        mocker.patch("asyncio.to_thread", side_effect=Exception("DB timeout"))
        # Should not raise — just log.warning
        # Test that SSE stream continues normally after DB error
```

### 7.2 P2: Extend Backtest

**Файл:** `tests/backend/api/routers/test_backtests_extend.py` (новый)

```python
class TestExtendBacktest:
    """Tests for POST /backtests/{id}/extend."""

    @pytest.fixture
    def sample_backtest(self, db_session):
        """A completed backtest from 7 days ago."""
        end_ms = int((datetime.utcnow() - timedelta(days=7)).timestamp() * 1000)
        bt = BacktestModel(
            symbol="BTCUSDT", interval="60", market_type="linear",
            start_time=end_ms - 30 * 24 * 3600 * 1000,
            end_time=end_ms,
            config={"symbol": "BTCUSDT", "interval": "60", ...},
            trades=[...],
            metrics={...},
        )
        db_session.add(bt); db_session.commit()
        return bt

    def test_extend_creates_new_backtest(self, client, sample_backtest, mocker):
        """Extend creates a new backtest record with is_extended=True."""
        mocker.patch("backend.services.adapters.bybit.BybitAdapter.get_historical_klines",
                     return_value=[...])
        resp = client.post(f"/api/v1/backtests/{sample_backtest.id}/extend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["new_backtest_id"] != sample_backtest.id

    def test_already_current_returns_204(self, client, db_session):
        """Backtest from 1 hour ago returns already_current status."""
        ...

    def test_extend_uses_overlap_candles(self, mocker, sample_backtest):
        """Verifies that start_ts = end_ms - overlap * interval_ms."""
        spy = mocker.spy(adapter, "get_historical_klines")
        client.post(f"/api/v1/backtests/{sample_backtest.id}/extend")

        call_args = spy.call_args[1]
        expected_start = sample_backtest.end_time - (5 * 3_600_000)  # 60m interval, 5 overlap
        assert call_args["start_time"] == expected_start

    def test_new_metrics_cover_full_period(self, ...):
        """Metrics in extended backtest cover original + gap period."""
        ...

    def test_extend_with_no_new_trades(self, ...):
        """If no new signals in gap — backtest extends with updated end_date only."""
        ...
```

---

## 8. Что НЕ нужно менять

| Компонент                 | Статус           | Причина                                                         |
| ------------------------- | ---------------- | --------------------------------------------------------------- |
| `BybitWebSocketClient`    | ✅ Без изменений | Уже работает корректно с `open_timeout=10.0`                    |
| `LiveChartSessionManager` | ✅ Без изменений | Double-checked locking уже исправлен                            |
| `LiveSignalService`       | ✅ Без изменений | Lowercase columns fix уже применён                              |
| `parse_kline_message`     | ✅ Без изменений | Принимает WebSocketMessage корректно                            |
| `MetricsCalculator`       | ✅ Без изменений | Единственный источник метрик — передаём ему объединённые trades |
| `StrategyBuilderAdapter`  | ✅ Без изменений | `generate_signals(df)` с lowercase колонками работает           |
| `OVERLAP_CANDLES`         | ✅ Без изменений | Используем существующую константу                               |
| `_persist_klines_sync`    | ✅ Без изменений | Повторно используем в P2 шаге 3                                 |
| `get_historical_klines`   | ✅ Без изменений | Повторно используем в P2 шаге 3                                 |
| Alembic migrations 1-13   | ✅ Без изменений | Нужна только одна новая миграция                                |

---

## Порядок реализации (рекомендуемый)

```
1. Alembic миграция (is_extended, source_backtest_id)  — 15 мин
2. _persist_live_bar_sync() + _persist_live_bar()      — 30 мин
3. SSE endpoint: добавить market_type + asyncio.create_task(...) — 15 мин
4. Тесты для P1                                         — 30 мин
5. POST /backtests/{id}/extend endpoint                 — 2-3 часа
6. Тесты для P2                                         — 1 час
7. Frontend: market_type в SSE URL + кнопка Extend      — 1 час
```

**Общая оценка: 6-7 часов**

---

_ТЗ подготовлено на основе анализа кодовой базы Bybit Strategy Tester v2 (commit 3b9652b1a, 2026-03-04)_
