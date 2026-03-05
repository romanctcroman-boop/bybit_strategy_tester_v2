# ТЗ: Real-Time Live Chart для Backtester

**Версия:** 1.0
**Дата:** 2026-03-03
**Статус:** Черновик — требует утверждения

---

## 1. Цель и контекст

После завершения бэктеста пользователь переходит на вкладку "Price Chart". В данный момент там отображается только исторический график за период бэктеста. Цель — сделать так, чтобы сразу после открытия вкладки:

1. **Исторические данные** бэктеста отображались как обычно.
2. **Текущая свеча** Bybit появлялась справа на графике и обновлялась в реальном времени (каждый тик WS).
3. **Сигналы стратегии** пересчитывались на закрытии каждой свечи и отмечались новыми маркерами.

Аналог: TradingView Pine Script — в режиме "real-time bar" индикатор и стратегия пересчитываются на каждом тике открытой свечи и фиксируются на её закрытии.

---

## 2. Как это работает в TradingView (модель исполнения)

```
Исторические свечи (Close):
  bar_index 0..N-1  → стратегия выполнена однократно, результат зафиксирован

Текущая открытая свеча (Open Bar):
  каждый тик       → пересчёт indicator values + условий стратегии
  на закрытии      → bar_index N подтверждается, результат фиксируется

Следующая свеча:
  bar_index N+1 открывается как "новый открытый бар"
```

Ключевая особенность: TradingView не хранит "стриминговый" сигнал — он пересчитывает всю историю + текущий бар при каждом тике. Мы делаем то же самое, но только для последних N баров (window), не всей истории.

---

## 3. Предлагаемая архитектура

```
Bybit WS  ──────────────────────────────────────────────────────┐
  wss://stream.bybit.com/v5/public/linear                       │
  topic: kline.{interval}.{symbol}                              │
  confirm=False  → tick (open bar updates)                       │
  confirm=True   → closed bar                                    │
         │                                                        │
         ▼                                                        │
BybitWebSocketClient (уже существует)                            │
  bybit_websocket.py                                             │
  .subscribe_klines(symbol, interval)                            │
  parse_kline_message(msg) → [{confirm, open, high, low,         │
                                close, volume, start, end}]      │
         │                                                        │
         ▼                                                        │
LiveChartSessionManager  ◄── НОВЫЙ модуль                       │
  backend/services/live_chart/session_manager.py                 │
  - dict[session_id → LiveChartSession]                          │
  - fan-out: 1 WS соединение на (symbol, interval)               │
  - N SSE подписчиков могут подключиться к 1 WS                  │
         │                                                        │
         ├── on_tick (confirm=False) ──────────────────────►     │
         │     упаковать {type:"tick", candle:{…}}               │
         │                                                        │
         └── on_close (confirm=True) ──────────────────────►     │
               SignalService.compute(ohlcv_window + new_bar)     │
               упаковать {type:"bar_closed", candle:{…},         │
                          signals:[{bar_index, long, short}]}    │
         │                                                        │
         ▼                                                        │
SSE Endpoint  ◄── НОВЫЙ эндпоинт                                │
  GET /api/v1/marketdata/live-chart/stream                       │
  ?symbol=BTCUSDT&interval=15&session_id=…                       │
  StreamingResponse (text/event-stream)                          │
         │                                                        │
         ▼                                                        │
EventSource (браузер)  ◄── НОВЫЙ JS-код                         │
  frontend/js/pages/backtest_results.js                          │
  _liveChartSource = new EventSource(url)                        │
  on "tick"       → btCandleSeries.update(candle)                │
  on "bar_closed" → btCandleSeries.update(candle)                │
                    + renderLiveSignalMarkers(signals)            │
```

---

## 4. Компоненты системы

### 4.1 Существующие компоненты (использовать без изменений)

| Компонент                         | Файл                                                    | Что используем                                                       |
| --------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------- |
| `BybitWebSocketClient`            | `backend/services/live_trading/bybit_websocket.py`      | `.connect()`, `.subscribe_klines()`, `.disconnect()`                 |
| `parse_kline_message()`           | `bybit_websocket.py:~460`                               | Парсинг входящего WS сообщения → список `KlineBar` с полем `confirm` |
| `StrategyBuilderAdapter`          | `backend/backtesting/strategy_builder_adapter.py`       | `.generate_signals(ohlcv_df)` — пересчёт сигналов на новых данных    |
| `btCandleSeries.update()`         | `backtest_results.js`                                   | Обновление текущей свечи в LightweightCharts                         |
| `btPriceChart` / `btCandleSeries` | `backtest_results.js:116-123`                           | Существующий экземпляр графика                                       |
| SSE паттерн                       | `backend/api/routers/optimizations/two_stage.py:59-445` | Шаблон для нового SSE эндпоинта                                      |
| `_priceChartGeneration`           | `backtest_results.js:122`                               | Защита от гонок при переключении бэктестов                           |

### 4.2 Новые компоненты

| Компонент                   | Файл                                             | Ответственность                                                |
| --------------------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| `LiveChartSession`          | `backend/services/live_chart/session_manager.py` | Данные одной сессии (symbol, interval, ws_client, subscribers) |
| `LiveChartSessionManager`   | `backend/services/live_chart/session_manager.py` | Реестр сессий, fan-out к SSE клиентам                          |
| `LiveSignalService`         | `backend/services/live_chart/signal_service.py`  | Хранение окна OHLCV + пересчёт сигналов адаптером              |
| SSE эндпоинт                | `backend/api/routers/marketdata.py`              | `GET /api/v1/marketdata/live-chart/stream`                     |
| `startLiveChart()`          | `frontend/js/pages/backtest_results.js`          | Запуск EventSource, подключение обработчиков                   |
| `stopLiveChart()`           | `frontend/js/pages/backtest_results.js`          | Закрытие EventSource + очистка маркеров                        |
| `renderLiveSignalMarkers()` | `frontend/js/pages/backtest_results.js`          | Добавление маркеров на закрытых барах                          |
| `_liveChartSource`          | `backtest_results.js`                            | Переменная — текущий EventSource                               |
| `_liveChartMarkers`         | `backtest_results.js`                            | Массив маркеров от live сигналов                               |
| Кнопка Live                 | `frontend/backtest-results.html`                 | Toggle кнопка "● Live" / "■ Stop"                              |

---

## 5. Детальное описание новых модулей

### 5.1 `LiveChartSession` / `LiveChartSessionManager`

**Файл:** `backend/services/live_chart/session_manager.py`

```python
"""
Live Chart Session Manager.
Manages Bybit WebSocket connections for real-time chart streaming.
Fan-out: одно WS соединение на (symbol, interval) → N SSE клиентов.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from backend.services.live_trading.bybit_websocket import (
    BybitWebSocketClient,
    parse_kline_message,
)

logger = logging.getLogger(__name__)


@dataclass
class LiveChartSession:
    """Одна активная сессия стриминга (symbol × interval)."""

    session_id: str
    symbol: str
    interval: str
    ws_client: BybitWebSocketClient
    # Очереди SSE подписчиков: {subscriber_id → asyncio.Queue}
    subscribers: dict[str, asyncio.Queue] = field(default_factory=dict)
    _task: asyncio.Task | None = None

    def add_subscriber(self, sub_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers[sub_id] = q
        return q

    def remove_subscriber(self, sub_id: str) -> None:
        self.subscribers.pop(sub_id, None)

    @property
    def has_subscribers(self) -> bool:
        return bool(self.subscribers)

    async def _fan_out(self, event: dict) -> None:
        """Рассылка события всем подписчикам."""
        dead = []
        for sub_id, q in self.subscribers.items():
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"[LiveChart] Queue full for subscriber {sub_id}, dropping event")
                dead.append(sub_id)
        for sub_id in dead:
            self.remove_subscriber(sub_id)

    async def _process_message(self, msg: dict) -> None:
        """Обработка входящего WS сообщения от Bybit."""
        bars = parse_kline_message(msg)
        for bar in bars:
            event = {
                "type": "bar_closed" if bar.get("confirm") else "tick",
                "candle": {
                    "time": int(bar["start"] / 1000),  # секунды для LightweightCharts
                    "open":  float(bar["open"]),
                    "high":  float(bar["high"]),
                    "low":   float(bar["low"]),
                    "close": float(bar["close"]),
                    "volume": float(bar.get("volume", 0)),
                },
                "confirm": bar.get("confirm", False),
            }
            await self._fan_out(event)


class LiveChartSessionManager:
    """
    Синглтон-реестр активных LiveChartSession.
    Используется из SSE эндпоинта и из lifespan-хука приложения.
    """

    def __init__(self) -> None:
        # Ключ: f"{symbol}:{interval}"
        self._sessions: dict[str, LiveChartSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, symbol: str, interval: str) -> LiveChartSession:
        key = f"{symbol}:{interval}"
        async with self._lock:
            if key not in self._sessions:
                ws_client = BybitWebSocketClient()
                await ws_client.connect()
                await ws_client.subscribe_klines(symbol, interval)

                session = LiveChartSession(
                    session_id=str(uuid4()),
                    symbol=symbol,
                    interval=interval,
                    ws_client=ws_client,
                )

                # Регистрируем callback: все сообщения kline.{interval}.{symbol}
                topic = f"kline.{interval}.{symbol}"
                ws_client.add_message_callback(topic, session._process_message)

                self._sessions[key] = session
                logger.info(f"[LiveChart] New session created: {key}")

            return self._sessions[key]

    async def cleanup(self, symbol: str, interval: str) -> None:
        """Закрыть WS если подписчиков не осталось."""
        key = f"{symbol}:{interval}"
        async with self._lock:
            session = self._sessions.get(key)
            if session and not session.has_subscribers:
                await session.ws_client.disconnect()
                del self._sessions[key]
                logger.info(f"[LiveChart] Session closed (no subscribers): {key}")


# Синглтон — импортировать в роутер
LIVE_CHART_MANAGER = LiveChartSessionManager()
```

**Важно:** `BybitWebSocketClient.add_message_callback()` — этот метод нужно **добавить** в `bybit_websocket.py` (см. п. 7 — рефакторинг).

---

### 5.2 `LiveSignalService`

**Файл:** `backend/services/live_chart/signal_service.py`

Цель: хранить скользящее окно последних N баров (warmup) + пересчитывать сигналы на каждом закрытом баре.

```python
"""
Live Signal Service.
Пересчитывает сигналы стратегии на закрытии каждого бара.
"""

import logging
from collections import deque

import pandas as pd

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

logger = logging.getLogger(__name__)

# Минимальный размер warmup окна (достаточно для большинства индикаторов)
MIN_WARMUP_BARS = 500


class LiveSignalService:
    """
    Хранит скользящее окно OHLCV + пересчитывает сигналы адаптером.

    Создаётся один раз для каждой сессии (symbol × interval × strategy).
    При инициализации заполняется историческими данными из БД.
    """

    def __init__(
        self,
        strategy_graph: dict,
        warmup_bars: list[dict],  # список {"time", "open", "high", "low", "close", "volume"}
        warmup_size: int = MIN_WARMUP_BARS,
    ) -> None:
        self._adapter = StrategyBuilderAdapter(strategy_graph)
        self._warmup_size = warmup_size
        self._window: deque[dict] = deque(maxlen=warmup_size)
        for bar in warmup_bars[-warmup_size:]:
            self._window.append(bar)
        logger.info(f"[LiveSignalService] Initialized with {len(self._window)} warmup bars")

    def push_closed_bar(self, candle: dict) -> dict | None:
        """
        Принять закрытый бар, пересчитать сигналы.

        Returns:
            dict с ключами {"long": bool, "short": bool} для последнего бара,
            или None если что-то пошло не так.
        """
        self._window.append(candle)
        df = self._build_df()
        try:
            result = self._adapter.generate_signals(df)
            last_idx = len(df) - 1
            long_signal  = bool(result.entries.iloc[last_idx])  if result.entries  is not None else False
            short_signal = bool(result.short_entries.iloc[last_idx]) if result.short_entries is not None else False
            return {"long": long_signal, "short": short_signal}
        except Exception as e:
            logger.error(f"[LiveSignalService] Signal computation failed: {e}")
            return None

    def _build_df(self) -> pd.DataFrame:
        bars = list(self._window)
        df = pd.DataFrame(bars)
        df.index = pd.to_datetime(df["time"], unit="s", utc=True)
        df.rename(columns={
            "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume",
        }, inplace=True)
        return df
```

---

### 5.3 SSE эндпоинт

**Файл:** `backend/api/routers/marketdata.py` — добавить в конец.

```python
# --- Live Chart SSE -----------------------------------------------------------

from backend.services.live_chart.session_manager import LIVE_CHART_MANAGER
from backend.services.live_chart.signal_service import LiveSignalService
from fastapi.responses import StreamingResponse

@router.get("/live-chart/stream")
async def live_chart_stream(
    symbol: str = Query(..., description="E.g. BTCUSDT"),
    interval: str = Query(..., description="Timeframe: 1,5,15,30,60,240,D"),
    session_id: str = Query(..., description="Unique browser session ID"),
    strategy_id: int | None = Query(None, description="ID of saved strategy (optional)"),
    db: Session = Depends(get_db),
):
    """
    SSE stream for live chart updates.
    Sends:
      data: {"type": "tick",       "candle": {...}}
      data: {"type": "bar_closed", "candle": {...}, "signals": {"long": bool, "short": bool}}
      data: {"type": "heartbeat"}
    """
    import json

    # 1. Получить или создать WS сессию
    chart_session = await LIVE_CHART_MANAGER.get_or_create(symbol, interval)

    # 2. Загрузить warmup данные (последние 500 баров из БД)
    warmup_rows = (
        db.query(BybitKlineAudit)
        .filter(
            BybitKlineAudit.symbol == symbol.upper(),
            BybitKlineAudit.interval == interval,
        )
        .order_by(BybitKlineAudit.open_time.desc())
        .limit(500)
        .all()
    )
    warmup_bars = [
        {
            "time":   int(r.open_time / 1000),
            "open":   float(r.open_price),
            "high":   float(r.high_price),
            "low":    float(r.low_price),
            "close":  float(r.close_price),
            "volume": float(r.volume or 0),
        }
        for r in reversed(warmup_rows)
    ]

    # 3. Загрузить граф стратегии (если указан)
    strategy_graph = None
    if strategy_id:
        # Загрузить из БД — аналогично тому как делает strategy_builder.py
        from backend.database.models.strategy import Strategy as StrategyModel
        strat_obj = db.query(StrategyModel).filter(StrategyModel.id == strategy_id).first()
        if strat_obj and strat_obj.strategy_config:
            import json as _json
            cfg = _json.loads(strat_obj.strategy_config) if isinstance(strat_obj.strategy_config, str) else strat_obj.strategy_config
            strategy_graph = cfg.get("strategy_graph") or cfg.get("blocks")

    signal_service = LiveSignalService(strategy_graph, warmup_bars) if strategy_graph else None

    # 4. Подписать браузер на события
    queue = chart_session.add_subscriber(session_id)

    async def event_generator():
        import asyncio, json
        heartbeat_interval = 20  # секунд

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    continue

                # Для закрытых баров: добавить сигналы
                if event["type"] == "bar_closed" and signal_service:
                    signals = signal_service.push_closed_bar(event["candle"])
                    event["signals"] = signals or {}

                yield f"data: {json.dumps(event)}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            chart_session.remove_subscriber(session_id)
            await LIVE_CHART_MANAGER.cleanup(symbol, interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # отключить nginx буферизацию
        },
    )
```

---

### 5.4 Frontend — новые переменные

Добавить в блок переменных `backtest_results.js` (после строки 123):

```javascript
// Live Chart streaming
let _liveChartSource = null; // EventSource instance (null = not streaming)
let _liveChartSessionId = null; // Уникальный ID браузерной сессии
let _liveChartMarkers = []; // Маркеры от live-сигналов (отдельно от исторических)
let _liveChartActive = false; // true когда live режим включён
```

И в `_setupLegacyShimSync()` (после строки 166) — синхронизация со StateManager:

```javascript
store.subscribe("backtestResults.priceChart.liveSource", (v) => {
    _liveChartSource = v;
});
store.subscribe("backtestResults.priceChart.liveSessionId", (v) => {
    _liveChartSessionId = v;
});
store.subscribe("backtestResults.priceChart.liveMarkers", (v) => {
    _liveChartMarkers = v ?? [];
});
store.subscribe("backtestResults.priceChart.liveActive", (v) => {
    _liveChartActive = !!v;
});
```

---

### 5.5 Frontend — новые функции

**Добавить после `buildTradePriceLines`:**

```javascript
// ==========================================
// Live Chart Streaming
// ==========================================

/**
 * Генерирует уникальный ID сессии браузера (один раз за pageload).
 * @returns {string}
 */
function getLiveChartSessionId() {
    if (!_liveChartSessionId) {
        _liveChartSessionId = `lc_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    }
    return _liveChartSessionId;
}

/**
 * Запускает live-стриминг для текущего бэктеста.
 * Подключается к SSE эндпоинту, обновляет график в реальном времени.
 *
 * @param {Object} backtest — объект текущего бэктеста (содержит symbol, interval, strategy_id)
 */
function startLiveChart(backtest) {
    if (_liveChartActive) return; // уже запущен

    if (!btCandleSeries) {
        console.warn("[LiveChart] btCandleSeries not ready, cannot start live stream");
        return;
    }

    const symbol = backtest.symbol || backtest.ticker;
    const interval = backtest.timeframe || backtest.interval;
    const stratId = backtest.strategy_id || backtest.id;

    if (!symbol || !interval) {
        console.warn("[LiveChart] Missing symbol or interval");
        return;
    }

    const sessionId = getLiveChartSessionId();
    const params = new URLSearchParams({
        symbol,
        interval,
        session_id: sessionId,
        ...(stratId ? { strategy_id: stratId } : {}),
    });

    const url = `/api/v1/marketdata/live-chart/stream?${params}`;
    console.log(`[LiveChart] Connecting to ${url}`);

    _liveChartSource = new EventSource(url);
    _liveChartActive = true;
    _updateLiveButton(true);

    _liveChartSource.onmessage = (evt) => {
        try {
            const event = JSON.parse(evt.data);
            _handleLiveChartEvent(event);
        } catch (e) {
            console.error("[LiveChart] Failed to parse event:", e);
        }
    };

    _liveChartSource.onerror = (err) => {
        console.error("[LiveChart] SSE error, stopping stream", err);
        stopLiveChart();
    };
}

/**
 * Останавливает live-стриминг.
 */
function stopLiveChart() {
    if (_liveChartSource) {
        _liveChartSource.close();
        _liveChartSource = null;
    }
    _liveChartActive = false;
    _updateLiveButton(false);
    console.log("[LiveChart] Stream stopped");
}

/**
 * Обработчик входящих SSE событий.
 * @param {Object} event — {type, candle, signals?, ...}
 */
function _handleLiveChartEvent(event) {
    if (!btCandleSeries) return;

    if (event.type === "heartbeat") return; // ничего не делаем

    if (event.type === "tick" || event.type === "bar_closed") {
        const candle = event.candle;

        // Обновить свечу на графике
        btCandleSeries.update({
            time: candle.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
        });

        // На закрытом баре — обработать сигналы
        if (event.type === "bar_closed" && event.signals) {
            _applyLiveSignals(candle.time, event.signals);
        }
    }
}

/**
 * Добавляет маркеры сигнала на закрытом баре.
 * @param {number} timeSec — время бара (секунды)
 * @param {Object} signals — {long: bool, short: bool}
 */
function _applyLiveSignals(timeSec, signals) {
    if (!btCandleSeries) return;

    const newMarkers = [];
    if (signals.long) {
        newMarkers.push({
            time: timeSec,
            position: "belowBar",
            color: "#26a69a",
            shape: "arrowUp",
            text: "▲ Live",
            size: 1,
        });
    }
    if (signals.short) {
        newMarkers.push({
            time: timeSec,
            position: "aboveBar",
            color: "#ef5350",
            shape: "arrowDown",
            text: "▼ Live",
            size: 1,
        });
    }

    if (newMarkers.length > 0) {
        _liveChartMarkers = [..._liveChartMarkers, ...newMarkers];
        // Объединить с историческими маркерами и обновить
        const allMarkers = [...btPriceChartMarkers, ..._liveChartMarkers].sort((a, b) => a.time - b.time);
        btCandleSeries.setMarkers(allMarkers);
    }
}

/**
 * Обновляет состояние кнопки Live.
 * @param {boolean} active
 */
function _updateLiveButton(active) {
    const btn = document.getElementById("btLiveChartBtn");
    if (!btn) return;
    btn.textContent = active ? "■ Stop Live" : "● Live";
    btn.classList.toggle("active", active);
}
```

---

### 5.6 Frontend — кнопка Live в HTML

**Файл:** `frontend/backtest-results.html`

Найти блок Price Chart Tab (около строки 366) и добавить кнопку рядом с чекбоксами:

```html
<!-- Добавить в toolbar графика цены -->
<div class="bt-price-chart-controls">
    <!-- существующие чекбоксы -->
    <label class="bt-chart-checkbox"> <input type="checkbox" id="markerShowPnl" checked /> Show PnL </label>
    <label class="bt-chart-checkbox"> <input type="checkbox" id="markerShowEntryPrice" checked /> Entry price lines </label>
    <!-- НОВАЯ кнопка -->
    <button id="btLiveChartBtn" class="bt-live-btn" title="Start real-time streaming">● Live</button>
</div>
```

CSS (добавить в `frontend/css/backtest_results.css`):

```css
.bt-live-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border: 1px solid #444;
    border-radius: 4px;
    background: transparent;
    color: #aaa;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
}
.bt-live-btn:hover {
    border-color: #26a69a;
    color: #26a69a;
}
.bt-live-btn.active {
    border-color: #ef5350;
    color: #ef5350;
    animation: live-pulse 1.5s infinite;
}
@keyframes live-pulse {
    0%,
    100% {
        opacity: 1;
    }
    50% {
        opacity: 0.6;
    }
}
```

---

### 5.7 Подключение кнопки к логике

В функции `updatePriceChart` после инициализации графика добавить:

```javascript
// Подключить кнопку Live
const liveBtn = document.getElementById("btLiveChartBtn");
if (liveBtn) {
    // Снять старый обработчик
    liveBtn.replaceWith(liveBtn.cloneNode(true));
    const newBtn = document.getElementById("btLiveChartBtn");
    newBtn.addEventListener("click", () => {
        if (_liveChartActive) {
            stopLiveChart();
        } else {
            startLiveChart(backtest);
        }
    });
}
```

И при разрушении графика (`destroyPriceChart` или перед переключением):

```javascript
stopLiveChart(); // закрыть SSE соединение
_liveChartMarkers = []; // очистить live маркеры
```

---

## 6. Рефакторинг `bybit_websocket.py`

Текущий `BybitWebSocketClient` использует один callback на всё. Нужно добавить **per-topic callback registry**:

```python
# В __init__ добавить:
self._topic_callbacks: dict[str, list[Callable]] = {}

# Новый метод:
def add_message_callback(self, topic: str, callback: Callable) -> None:
    """Регистрировать callback для конкретного topic."""
    if topic not in self._topic_callbacks:
        self._topic_callbacks[topic] = []
    self._topic_callbacks[topic].append(callback)

def remove_message_callback(self, topic: str, callback: Callable) -> None:
    cbs = self._topic_callbacks.get(topic, [])
    if callback in cbs:
        cbs.remove(callback)

# В _receive_public_messages() (или _process_public_message()) изменить:
# БЫЛО: await self._message_queue.put(message)
# СТАЛО: вызывать per-topic callbacks
async def _dispatch_message(self, raw_msg: dict) -> None:
    topic = raw_msg.get("topic", "")
    cbs = self._topic_callbacks.get(topic, [])
    for cb in cbs:
        try:
            await cb(raw_msg)
        except Exception as e:
            logger.error(f"[WS] callback error for topic {topic}: {e}")
    # Сохранить обратную совместимость с общей очередью
    await self._message_queue.put(raw_msg)
```

**Обратная совместимость:** существующий `_message_queue` и `LiveStrategyRunner` не затрагиваются — они продолжают работать через очередь.

---

## 7. Переменные: полный реестр

### Backend

| Переменная / поле                        | Тип                       | Файл                 | Роль                              |
| ---------------------------------------- | ------------------------- | -------------------- | --------------------------------- |
| `LIVE_CHART_MANAGER`                     | `LiveChartSessionManager` | `session_manager.py` | Синглтон реестра сессий           |
| `LiveChartSession.subscribers`           | `dict[str, Queue]`        | `session_manager.py` | SSE очереди подписчиков           |
| `LiveChartSession.ws_client`             | `BybitWebSocketClient`    | `session_manager.py` | WS соединение с Bybit             |
| `LiveSignalService._window`              | `deque[dict]`             | `signal_service.py`  | Скользящее окно OHLCV             |
| `LiveSignalService._adapter`             | `StrategyBuilderAdapter`  | `signal_service.py`  | Движок сигналов                   |
| `BybitWebSocketClient._topic_callbacks`  | `dict[str, list]`         | `bybit_websocket.py` | Per-topic callbacks               |
| `parse_kline_message()` return `confirm` | `bool`                    | `bybit_websocket.py` | False=открытый бар, True=закрытый |

### Frontend

| Переменная              | Тип                 | Место объявления           | Роль                                        |
| ----------------------- | ------------------- | -------------------------- | ------------------------------------------- |
| `_liveChartSource`      | `EventSource\|null` | `backtest_results.js:~124` | Активное SSE соединение                     |
| `_liveChartSessionId`   | `string\|null`      | `backtest_results.js:~125` | Уникальный ID сессии                        |
| `_liveChartMarkers`     | `Array`             | `backtest_results.js:~126` | Live маркеры сигналов                       |
| `_liveChartActive`      | `boolean`           | `backtest_results.js:~127` | Флаг активного стриминга                    |
| `btCandleSeries`        | `ISeriesApi`        | `backtrack_results.js:117` | Существующий; обновляется `.update(candle)` |
| `btPriceChartMarkers`   | `Array`             | `backtest_results.js:118`  | Существующие исторические маркеры           |
| `_priceChartGeneration` | `number`            | `backtest_results.js:122`  | Защита от гонок (проверять при старте live) |

---

## 8. Технические вызовы и решения

### 8.1 Warmup баров

**Проблема:** `StrategyBuilderAdapter.generate_signals()` рассчитывает индикаторы от начала переданного DataFrame. RSI с периодом 14 требует минимум 14 баров, Ichimoku senkou_b — 52, некоторые стратегии — 200+.

**Решение:** `LiveSignalService` загружает последние 500 баров из БД при инициализации. Это покрывает 99% стратегий. Для стратегий с `use_btc_source=True` (RSI с BTC источником) — загрузить отдельно BTCUSDT 500 баров.

### 8.2 Fan-out (N клиентов на 1 WS)

**Проблема:** Два браузера смотрят бэктест BTCUSDT 15m — нельзя создавать 2 WS соединения.

**Решение:** `LiveChartSessionManager` ключует по `f"{symbol}:{interval}"`. Один WS → N `asyncio.Queue` → N SSE потоков. При `subscribers.empty()` WS закрывается автоматически.

### 8.3 Gонка при переключении бэктеста

**Проблема:** Пользователь переключает бэктест пока идёт стриминг — нужно остановить старый.

**Решение:** Вызвать `stopLiveChart()` в `destroyPriceChart()` или в начале `updatePriceChart()`. Проверять `_priceChartGeneration` перед вызовом `startLiveChart`.

### 8.4 Накопление маркеров

**Проблема:** За долгую сессию `_liveChartMarkers` может вырасти до тысяч записей, `setMarkers()` будет лагать.

**Решение:** Ограничить `_liveChartMarkers.maxLength = 500`. При превышении — удалять старейшие.

### 8.5 Нет Bybit API ключей (public данные)

Klines — это **публичные** данные. `BybitWebSocketClient` не требует `api_key` / `api_secret` для подписки на `kline.*`. Аутентификация нужна только для приватных каналов (orders, positions).

### 8.6 NGINX буферизация SSE

На production NGINX буферизует ответ. Хедер `X-Accel-Buffering: no` отключает буферизацию для SSE стримов (уже добавлен в эндпоинт).

---

## 9. Поэтапный план реализации

### Фаза 1 — Backend инфраструктура (2-3 дня)

1. Добавить `add_message_callback()` / `_dispatch_message()` в `BybitWebSocketClient`
2. Создать `backend/services/live_chart/` с `__init__.py`
3. Написать `session_manager.py` (`LiveChartSession`, `LiveChartSessionManager`, `LIVE_CHART_MANAGER`)
4. Написать `signal_service.py` (`LiveSignalService`)
5. Зарегистрировать `LIVE_CHART_MANAGER` в `backend/api/lifespan.py` (shutdown: закрыть все сессии)

**Тесты:**

```python
# tests/backend/services/test_live_chart_session.py
# tests/backend/services/test_live_signal_service.py
```

### Фаза 2 — SSE эндпоинт (1 день)

1. Добавить эндпоинт `GET /api/v1/marketdata/live-chart/stream` в `marketdata.py`
2. Тест: `curl "localhost:8000/api/v1/marketdata/live-chart/stream?symbol=BTCUSDT&interval=1&session_id=test"` — должен вернуть heartbeats каждые 20с

### Фаза 3 — Frontend (2 дня)

1. Добавить переменные `_liveChartSource`, `_liveChartSessionId`, `_liveChartMarkers`, `_liveChartActive`
2. Добавить в `_setupLegacyShimSync()` подписки
3. Написать `startLiveChart()`, `stopLiveChart()`, `_handleLiveChartEvent()`, `_applyLiveSignals()`, `_updateLiveButton()`
4. Добавить кнопку `#btLiveChartBtn` в HTML
5. Подключить кнопку в `updatePriceChart()`
6. Вызвать `stopLiveChart()` при разрушении/переключении графика

### Фаза 4 — Интеграция и тестирование (1-2 дня)

1. Ручное тестирование: открыть бэктест BTCUSDT/1m, нажать Live, убедиться что свеча обновляется
2. Проверить отключение при переключении бэктеста
3. Проверить корректность маркеров (сравнить с историческими сигналами)
4. Нагрузочный тест: 3 браузерных вкладки → 1 WS соединение (fan-out)

---

## 10. Точки входа / места правки файлов

| Файл                                               | Что менять                                                               | Строка                                   |
| -------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------- |
| `backend/services/live_trading/bybit_websocket.py` | Добавить `_topic_callbacks`, `add_message_callback`, `_dispatch_message` | ~`__init__` + `_receive_public_messages` |
| `backend/api/lifespan.py`                          | Регистрировать `LIVE_CHART_MANAGER.shutdown()` в `on_shutdown`           | конец файла                              |
| `backend/api/routers/marketdata.py`                | Добавить SSE эндпоинт                                                    | в конец                                  |
| `frontend/backtest-results.html`                   | Добавить `#btLiveChartBtn`                                               | ~366                                     |
| `frontend/css/backtest_results.css`                | CSS для `.bt-live-btn`                                                   | конец файла                              |
| `frontend/js/pages/backtest_results.js`            | Добавить переменные + 5 функций + шим                                    | 123, 166, после `buildTradePriceLines`   |
| **НОВЫЕ файлы**                                    | `backend/services/live_chart/__init__.py`                                | —                                        |
| **НОВЫЕ файлы**                                    | `backend/services/live_chart/session_manager.py`                         | —                                        |
| **НОВЫЕ файлы**                                    | `backend/services/live_chart/signal_service.py`                          | —                                        |

---

## 11. Что НЕ входит в scope

- Live торговля (выставление ордеров) — вне scope.
- Стриминг для оптимизатора — вне scope.
- Поддержка нескольких открытых позиций на live графике — вне scope (только сигналы).
- Спот рынок (только linear/perpetual, как у `BybitWebSocketClient`) — можно добавить позже.

---

## Приложение A: Формат WS сообщения от Bybit (kline)

```json
{
  "topic": "kline.15.BTCUSDT",
  "data": [
    {
      "start":    1672324800000,
      "end":      1672325700000,
      "interval": "15",
      "open":     "16600",
      "close":    "16750",
      "high":     "16800",
      "low":      "16550",
      "volume":   "43.123",
      "turnover": "724000.12",
      "confirm":  false,        ← true = свеча закрыта
      "timestamp": 1672325611000
    }
  ],
  "ts": 1672325611000,
  "type": "snapshot"
}
```

## Приложение B: Формат SSE события

```
data: {"type":"tick","candle":{"time":1672325611,"open":16600,"high":16800,"low":16550,"close":16750,"volume":43.12},"confirm":false}

data: {"type":"bar_closed","candle":{"time":1672324800,"open":16600,"high":16800,"low":16550,"close":16740,"volume":44.5},"confirm":true,"signals":{"long":false,"short":true}}

data: {"type":"heartbeat"}
```

## Приложение C: Тест-план ручного тестирования

1. Открыть http://localhost:8000/frontend/backtest-results.html
2. Выбрать бэктест BTCUSDT, 1m, последние 7 дней
3. Перейти на вкладку "Price Chart" — исторические свечи загружаются
4. Нажать "● Live" — кнопка меняется на "■ Stop Live" (красная, пульсирует)
5. Подождать 1-2 минуты — справа от исторических свечей появляются новые
6. Если стратегия генерирует сигнал — появляется маркер ▲/▼
7. Нажать "■ Stop Live" — стриминг останавливается, кнопка возвращается в исходный вид
8. Переключить бэктест (другой символ) — убедиться что стриминг предыдущего закрыт

---

## Дополнение v1.1 — Исправления и расширения

**Дата:** 2026-03-03

---

## D1. КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ КОДА

### D1.1 `bybit_websocket.py` — callback API УЖЕ СУЩЕСТВУЕТ

Раздел 6 оригинального ТЗ **ошибочен**. `BybitWebSocketClient` уже содержит полноценный callback API:

```python
# backend/services/live_trading/bybit_websocket.py:504-520 — СУЩЕСТВУЕТ
def register_callback(self, topic: str, callback: Callable): ...
def unregister_callback(self, topic: str, callback: Callable): ...

# Dispatch вызывается автоматически в _process_message():504
async def _dispatch_callbacks(self, message: WebSocketMessage): ...
```

**Вывод:** Рефакторинг `bybit_websocket.py` из раздела 6 **не нужен**. Используем `register_callback` напрямую.

### D1.2 Исправленный `session_manager.py`

`parse_kline_message(message)` принимает `WebSocketMessage`, **не** `dict`. Callback получает `WebSocketMessage`. Оригинальный код в п.5.1 был неверен:

```python
# НЕВЕРНО (из оригинального ТЗ):
async def _process_message(self, msg: dict) -> None:
    bars = parse_kline_message(msg)   # ← TypeError: msg — dict, не WebSocketMessage

# ВЕРНО:
async def _on_ws_message(self, message: WebSocketMessage) -> None:
    bars = parse_kline_message(message)   # ← message — WebSocketMessage ✓
    for bar in bars:
        event = {
            "type": "bar_closed" if bar["confirm"] else "tick",
            "candle": {
                "time":   int(bar["start"] / 1000),
                "open":   bar["open"],
                "high":   bar["high"],
                "low":    bar["low"],
                "close":  bar["close"],
                "volume": bar["volume"],
            },
            "confirm": bar["confirm"],
        }
        await self._fan_out(event)

# Регистрация в get_or_create():
topic = f"kline.{interval}.{symbol}"
ws_client.register_callback(topic, session._on_ws_message)

# Очистка при удалении сессии:
ws_client.unregister_callback(topic, session._on_ws_message)
```

### D1.3 Исправленная загрузка стратегии в SSE эндпоинте

Поле `strategy_config` **не существует** в модели `Strategy`. Правильные поля:

```python
# backend/database/models/strategy.py:107-111
builder_graph       = Column(JSON)   # ← полный граф: {blocks, connections, name, interval}
builder_blocks      = Column(JSON)   # ← только блоки
builder_connections = Column(JSON)   # ← только соединения
is_builder_strategy = Column(Boolean)  # ← True если создана через Builder

# НЕВЕРНО (из оригинального ТЗ):
if strat_obj and strat_obj.strategy_config:   # ← AttributeError
    cfg = ...
    strategy_graph = cfg.get("strategy_graph") or cfg.get("blocks")

# ВЕРНО:
if strat_obj and strat_obj.is_builder_strategy and strat_obj.builder_graph:
    strategy_graph = strat_obj.builder_graph   # уже dict, не нужен json.loads
```

---

## D2. Машина состояний Live Chart

Полный граф переходов для управления стримингом:

```
                          [кнопка Live нажата]
          ┌───────────────────────────────────────┐
          │                                       ▼
       IDLE ────────────────────────────────► CONNECTING
          ▲                                       │
          │                            SSE открыт │ (onopen)
          │                                       ▼
          │      [кнопка Stop нажата]         STREAMING ◄──── heartbeat
          │  ◄────────────────────────────────────┤
          │                                       │
          │      [переключён бэктест]             │ onerror (сеть)
          │  ◄────────────────────────────────────┤
          │                                       ▼
          │                                 RECONNECTING
          │                         (EventSource авто, 3 с)
          │                                       │
          │      [3+ неудачных попытки]           │ успех
          ├──────────────────────────────── ERROR ◄┘
          │
      [страница закрыта / stopLiveChart()]
```

**Состояния в коде:**

```javascript
const LiveChartState = {
    IDLE: "idle",
    CONNECTING: "connecting",
    STREAMING: "streaming",
    RECONNECTING: "reconnecting",
    ERROR: "error",
};

let _liveChartState = LiveChartState.IDLE;
let _liveChartRetryCount = 0;
const MAX_RETRIES = 3;
```

**Обработчики переходов:**

```javascript
_liveChartSource.onopen = () => {
    _liveChartState = LiveChartState.STREAMING;
    _liveChartRetryCount = 0;
    _updateLiveButton("streaming");
};

_liveChartSource.onerror = () => {
    _liveChartRetryCount++;
    if (_liveChartRetryCount > MAX_RETRIES) {
        _liveChartState = LiveChartState.ERROR;
        stopLiveChart();
        _showLiveChartError("Соединение потеряно. Нажмите Live для повтора.");
    } else {
        _liveChartState = LiveChartState.RECONNECTING;
        _updateLiveButton("reconnecting");
        // EventSource сам переподключится через ~3 секунды
    }
};
```

---

## D3. Алгоритм сшивки исторических и live данных

Самый тонкий момент всей системы: последняя историческая свеча и первый live тик **совпадают по времени**, если текущий бар ещё не закрыт.

```
Исторические данные из БД:     [t0][t1][t2]...[tN]
                                                 ↑ закрытый бар, confirm=True
Live тики от Bybit WS:                          [tN+1_tick] [tN+1_tick] ...
                                                          ↑ tN+1 = tN + interval (открытый бар)
```

**Алгоритм:**

```javascript
function _handleLiveChartEvent(event) {
    const candle = event.candle;

    // 1. Определить тип обновления
    const lastHistoricalTime = _btCachedCandles.length > 0 ? _btCachedCandles[_btCachedCandles.length - 1].time : 0;

    if (candle.time <= lastHistoricalTime) {
        // Тик относится к последней исторической свече (редко, только для текущего бара)
        // Обновить последнюю свечу без добавления новой
        btCandleSeries.update(candle);
        return;
    }

    // 2. Новая свеча — справа от истории
    btCandleSeries.update(candle);

    // 3. На закрытии — обновить кэш
    if (event.type === "bar_closed") {
        _btCachedCandles = [..._btCachedCandles, candle];
        if (event.signals) {
            _applyLiveSignals(candle.time, event.signals);
        }
    }
}
```

**Edge case — пропущенные свечи при reconnect:**

Если соединение прерывалось и несколько свечей пропущено — их надо дозагрузить из БД. Простое решение: при reconnect перезапросить `/api/v1/marketdata/bybit/klines/range` от `lastHistoricalTime` до `now`.

```javascript
_liveChartSource.onopen = async () => {
    // Дозагрузить пропущенные бары при переподключении
    if (_liveChartRetryCount > 0 && _btCachedCandles.length > 0) {
        await _fetchMissingBars();
    }
    _liveChartState = LiveChartState.STREAMING;
};

async function _fetchMissingBars() {
    const lastTime = _btCachedCandles[_btCachedCandles.length - 1].time;
    const now = Math.floor(Date.now() / 1000);
    const resp = await fetch(`/api/v1/marketdata/bybit/klines/range?symbol=${_liveSymbol}` + `&interval=${_liveInterval}&start=${lastTime * 1000}&end=${now * 1000}`);
    const bars = await resp.json();
    for (const bar of bars) {
        const c = { time: Math.floor(bar.open_time / 1000), open: bar.open, high: bar.high, low: bar.low, close: bar.close };
        btCandleSeries.update(c);
        _btCachedCandles.push(c);
    }
}
```

---

## D4. Бюджет производительности

### Частота вызовов `generate_signals()`

| Таймфрейм | Интервал закрытия | Вызовы в час |
| --------- | ----------------- | ------------ |
| 1m        | 60 сек            | 60           |
| 5m        | 5 мин             | 12           |
| 15m       | 15 мин            | 4            |
| 1h        | 60 мин            | 1            |

**Ключевое правило:** `generate_signals()` вызывается **только на `bar_closed`**, не на каждом тике. Для 1m это 60 вызовов/час — приемлемо.

### Время выполнения `generate_signals(500 bars)`

Измерения (примерные, зависят от количества блоков):

| Стратегия                   | Баров | Время (мс)  | Приемлемо для |
| --------------------------- | ----- | ----------- | ------------- |
| 1 RSI блок                  | 500   | ~5–15 мс    | любой TF      |
| 3-4 блока (RSI + MACD + BB) | 500   | ~30–80 мс   | 1m и выше     |
| 10+ блоков                  | 500   | ~150–400 мс | 5m и выше     |
| Ichimoku + divergence + ATR | 500   | ~200–600 мс | 15m и выше    |

**Для 1m таймфрейма** максимальный бюджет = 60 сек / вызов. Даже 600 мс — безопасно.

**Потенциальная проблема:** если стратегия использует `use_btc_source=True` (RSI от BTC-цены), `LiveSignalService` должен держать **второй** warmup-буфер для BTCUSDT. Это особый кейс — см. D6.

### Память

- 500 баров × 6 полей (`float64`) = 24 КБ на сессию
- 10 одновременных сессий = 240 КБ — ничтожно

---

## D5. Ограничение multi-process и решение

### Проблема

`LIVE_CHART_MANAGER` — Python-синглтон в памяти процесса. При запуске нескольких Uvicorn воркеров:

```
uvicorn app:app --workers 4
```

Каждый воркер имеет **свой экземпляр** `LIVE_CHART_MANAGER`. Если браузер подключается к воркеру №2, а переподключается к воркеру №3 — он не найдёт свою сессию.

### Проверка текущей конфигурации

Из `main.py server` — проверить, используется ли `--workers > 1`. Для этого проекта (локальная разработка) обычно **1 воркер** — проблемы нет.

### Решение для production (если нужно несколько воркеров)

**Вариант A (рекомендуется):** Запускать WS-стриминг как **отдельный микросервис** на одном воркере, проксировать SSE через Redis pub/sub:

```
[Uvicorn воркер N] ──SSE──► клиент
       │
       ▼ subscribe
[Redis channel: live_chart:{symbol}:{interval}]
       ▲
[LiveChart WS Worker — 1 процесс] ──WS──► Bybit
```

**Вариант B (проще):** Принудительно ограничить 1 воркер для этого роутера через sticky sessions в NGINX.

**Вариант C (минимальный):** Добавить в `main.py` проверку и аварийно завершить если workers > 1 при попытке live chart.

---

## D6. Специальные кейсы стратегий

### D6.1 `use_btc_source=True` (RSI от BTC цены)

Некоторые RSI блоки используют BTCUSDT как источник данных вместо торгуемого инструмента. `LiveSignalService` в этом случае должен поддерживать второй WS поток:

```python
class LiveSignalService:
    def __init__(self, strategy_graph, warmup_bars, btc_warmup_bars=None):
        # Определить нужен ли BTC источник
        self._needs_btc_source = self._check_btc_source(strategy_graph)
        if self._needs_btc_source:
            self._btc_window: deque = deque(maxlen=500)
            for bar in (btc_warmup_bars or [])[-500:]:
                self._btc_window.append(bar)
```

Загрузка `btc_warmup_bars` в SSE эндпоинте — аналогично `warmup_bars`, но для `symbol=BTCUSDT`.

### D6.2 Не-Builder стратегии

Если `is_builder_strategy=False` (встроенная стратегия: SMA, RSI, MACD), `builder_graph` будет `None`. В этом случае:

- `signal_service = None` — live сигналы не показываются
- Только тики обновляют свечу на графике
- Кнопка Live работает, но без маркеров сигналов

Это корректное поведение — оставить как есть. Добавить в UI тултип: "Сигналы в реальном времени поддерживаются только для стратегий из Strategy Builder".

### D6.3 DCA стратегии

DCA использует `DCAEngine`, не `StrategyBuilderAdapter`. `generate_signals()` у него другой интерфейс. **Out of scope для v1** — при `dca_enabled=True` отключить live сигналы (только тики).

---

## D7. Page Visibility API — пауза при скрытой вкладке

Когда пользователь переходит на другую вкладку браузера или сворачивает окно, продолжать держать SSE соединение открытым нет смысла. Добавить в JS:

```javascript
// Инициализировать один раз при загрузке страницы
document.addEventListener("visibilitychange", _onPageVisibilityChange);

function _onPageVisibilityChange() {
    if (document.hidden) {
        // Вкладка скрыта — приостановить (закрыть SSE, не трогать маркеры)
        if (_liveChartActive) {
            _liveChartSource?.close();
            _liveChartSource = null;
            _liveChartState = LiveChartState.IDLE;
            console.log("[LiveChart] Paused (tab hidden)");
        }
    } else {
        // Вкладка снова видима — возобновить если был активен
        if (_liveChartActive && !_liveChartSource) {
            console.log("[LiveChart] Resuming (tab visible)");
            startLiveChart(currentBacktest);
        }
    }
}
```

**Эффект:** экономия WS-ресурсов Bybit и серверных SSE соединений. Bybit ограничивает WS соединения — это важно.

---

## D8. SSE переподключение и `Last-Event-ID`

`EventSource` **автоматически** переподключается при обрыве с задержкой ~3 секунды. При переподключении он отправляет заголовок `Last-Event-ID` с последним полученным `id` события.

Для поддержки этого механизма нужно:

**Backend — нумеровать события:**

```python
async def event_generator():
    event_id = 0
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=20)
        event_id += 1
        yield f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
```

**Backend — принять `Last-Event-ID` при reconnect:**

```python
@router.get("/live-chart/stream")
async def live_chart_stream(
    ...,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
):
    # Если last_event_id есть — клиент переподключился
    # Пропустить загрузку warmup заново (он уже есть у клиента)
    is_reconnect = last_event_id is not None
```

**Важно:** при reconnect с тем же `session_id` — старая `asyncio.Queue` уже уничтожена. Нужно пересоздать подписчика в `chart_session.add_subscriber(session_id)`. Это уже корректно работает в текущем коде (перезаписывает очередь).

---

## D9. Маппинг интервалов

Bybit WS и база данных используют **одинаковые** коды интервалов — маппинг не нужен:

| TF отображение | Код в БД | Код в Bybit WS |
| -------------- | -------- | -------------- |
| 1 минута       | `"1"`    | `"1"`          |
| 5 минут        | `"5"`    | `"5"`          |
| 15 минут       | `"15"`   | `"15"`         |
| 30 минут       | `"30"`   | `"30"`         |
| 1 час          | `"60"`   | `"60"`         |
| 4 часа         | `"240"`  | `"240"`        |
| 1 день         | `"D"`    | `"D"`          |

**Но есть ловушка**: объект `backtest` на фронтенде может содержать `timeframe` = `"60"` или `"1h"` — зависит от того как он был сохранён. Нужен нормализатор:

```javascript
function _normalizeInterval(tf) {
    const MAP = { "1h": "60", "4h": "240", "1d": "D", "1w": "W", "1m": "1" };
    return MAP[tf] ?? tf; // если не найдено — вернуть как есть
}

// Использование в startLiveChart():
const interval = _normalizeInterval(backtest.timeframe || backtest.interval);
```

---

## D10. Примеры юнит-тестов

**`tests/backend/services/test_live_signal_service.py`:**

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from backend.services.live_chart.signal_service import LiveSignalService


def _make_warmup_bars(n=100):
    """Создать синтетические warmup бары для тестов."""
    bars = []
    for i in range(n):
        bars.append({
            "time": 1672324800 + i * 60,
            "open": 16600 + i,
            "high": 16700 + i,
            "low":  16500 + i,
            "close":16650 + i,
            "volume": 100.0,
        })
    return bars


def test_push_closed_bar_returns_signals():
    """push_closed_bar должен вернуть dict с ключами long/short."""
    graph = {
        "blocks": [
            {"id": "rsi", "type": "rsi", "params": {"period": 14, "oversold": 30, "overbought": 70}, "isMain": False},
            {"id": "s",   "type": "strategy", "params": {}, "isMain": True},
        ],
        "connections": [
            {"from": "rsi", "fromPort": "long", "to": "s", "toPort": "entry_long"},
        ],
    }
    svc = LiveSignalService(graph, _make_warmup_bars(200))
    result = svc.push_closed_bar({
        "time": 1672324800 + 200 * 60,
        "open": 16800, "high": 16900, "low": 16700, "close": 16850, "volume": 150.0,
    })
    assert result is not None
    assert "long" in result
    assert "short" in result
    assert isinstance(result["long"], bool)
    assert isinstance(result["short"], bool)


def test_push_closed_bar_with_empty_warmup():
    """С пустым warmup должен вернуть None (недостаточно баров для индикатора)."""
    graph = {"blocks": [], "connections": []}
    svc = LiveSignalService(graph, [])
    result = svc.push_closed_bar({
        "time": 1672324800, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 10,
    })
    # Либо None либо {"long": False, "short": False} — не должен кидать исключение
    assert result is None or (not result["long"] and not result["short"])


def test_window_maxlen_respected():
    """deque не должен расти бесконечно."""
    svc = LiveSignalService({}, _make_warmup_bars(500), warmup_size=50)
    assert len(svc._window) == 50  # обрезан до maxlen


def test_invalid_graph_returns_none(caplog):
    """При сломанном графе compute не должен крашиться."""
    svc = LiveSignalService({"blocks": "BROKEN"}, _make_warmup_bars(50))
    with caplog.at_level("ERROR"):
        result = svc.push_closed_bar({
            "time": 9999, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 1,
        })
    assert result is None
```

**`tests/backend/services/test_live_chart_session.py`:**

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.live_chart.session_manager import LiveChartSession


@pytest.mark.asyncio
async def test_add_remove_subscriber():
    session = LiveChartSession(
        session_id="test-id", symbol="BTCUSDT", interval="1",
        ws_client=MagicMock(),
    )
    q = session.add_subscriber("sub1")
    assert session.has_subscribers
    session.remove_subscriber("sub1")
    assert not session.has_subscribers


@pytest.mark.asyncio
async def test_fan_out_delivers_to_all_subscribers():
    session = LiveChartSession(
        session_id="test-id", symbol="BTCUSDT", interval="1",
        ws_client=MagicMock(),
    )
    q1 = session.add_subscriber("sub1")
    q2 = session.add_subscriber("sub2")
    event = {"type": "tick", "candle": {"time": 100}}
    await session._fan_out(event)
    assert q1.qsize() == 1
    assert q2.qsize() == 1
    assert await q1.get() == event


@pytest.mark.asyncio
async def test_fan_out_removes_full_queues():
    """Переполненная очередь должна отключить подписчика."""
    session = LiveChartSession(
        session_id="test-id", symbol="BTCUSDT", interval="1",
        ws_client=MagicMock(),
    )
    q = session.add_subscriber("slow_sub")
    # Заполнить очередь до maxsize=100
    for i in range(100):
        q.put_nowait({"i": i})
    # Следующий fan_out должен удалить slow_sub
    await session._fan_out({"type": "tick"})
    assert "slow_sub" not in session.subscribers
```

---

## D11. Метрики и мониторинг (Prometheus)

Добавить счётчики в `backend/monitoring/prometheus_exporter.py`:

```python
from prometheus_client import Counter, Gauge, Histogram

# Активные live-стриминг сессии
live_chart_active_sessions = Gauge(
    'bybit_live_chart_sessions_active',
    'Number of active live chart SSE sessions',
    labelnames=['symbol', 'interval'],
)

# Количество принятых тиков
live_chart_ticks_total = Counter(
    'bybit_live_chart_ticks_total',
    'Total WebSocket ticks received for live chart',
    labelnames=['symbol', 'interval', 'type'],  # type: tick | bar_closed
)

# Время вычисления сигналов
live_chart_signal_compute_seconds = Histogram(
    'bybit_live_chart_signal_compute_seconds',
    'Time to compute strategy signals for one closed bar',
    labelnames=['symbol'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)
```

Использование в `LiveSignalService.push_closed_bar()`:

```python
import time
from backend.monitoring.prometheus_exporter import live_chart_signal_compute_seconds

def push_closed_bar(self, candle):
    t0 = time.perf_counter()
    result = ...  # compute
    elapsed = time.perf_counter() - t0
    live_chart_signal_compute_seconds.labels(symbol=self._symbol).observe(elapsed)
    return result
```

**Dashboard Grafana** — алерт если `live_chart_signal_compute_seconds{quantile="0.95"} > 1.0` (95-й перцентиль > 1 сек).

---

## D12. UI — Индикатор ошибки и статуса

Кнопка Live должна отображать 4 состояния, а не 2:

```javascript
function _updateLiveButton(state) {
    const btn = document.getElementById("btLiveChartBtn");
    if (!btn) return;

    const STATES = {
        idle: { text: "● Live", cls: "", title: "Запустить real-time стриминг" },
        connecting: { text: "◌ Connecting…", cls: "connecting", title: "Подключение к Bybit WS…" },
        streaming: { text: "■ Stop Live", cls: "active", title: "Остановить стриминг" },
        reconnecting: { text: "↻ Reconnect…", cls: "reconnecting", title: `Переподключение (${_liveChartRetryCount}/${MAX_RETRIES})` },
        error: { text: "⚠ Live Error", cls: "error", title: "Ошибка стриминга. Нажмите для повтора." },
    };

    const s = STATES[state] || STATES.idle;
    btn.textContent = s.text;
    btn.title = s.title;
    btn.className = `bt-live-btn${s.cls ? " " + s.cls : ""}`;
}
```

CSS дополнения:

```css
.bt-live-btn.connecting {
    color: #ffa726;
    border-color: #ffa726;
    animation: live-pulse 0.8s infinite;
}
.bt-live-btn.reconnecting {
    color: #ff9800;
    border-color: #ff9800;
    animation: live-pulse 1s infinite;
}
.bt-live-btn.error {
    color: #ef5350;
    border-color: #ef5350;
}
```

---

## D13. Обновлённая таблица правки файлов

| Файл                     | Что менять                                                                                                                     | Изменение из v1.1            |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| `bybit_websocket.py`     | ~~Добавить callback API~~                                                                                                      | ❌ НЕ НУЖНО — уже существует |
| `session_manager.py`     | Использовать `register_callback` / `parse_kline_message(WebSocketMessage)`                                                     | ✅ Исправлен код             |
| `marketdata.py`          | Загрузка стратегии через `builder_graph`, не `strategy_config`                                                                 | ✅ Исправлен код             |
| `backtest_results.js`    | Добавить `_liveChartState`, `_liveChartRetryCount`, `_fetchMissingBars()`, `_normalizeInterval()`, `_onPageVisibilityChange()` | ✅ Новые элементы            |
| `backtest-results.html`  | Кнопка Live (4 состояния)                                                                                                      | ✅ Обновлено                 |
| `backtest_results.css`   | CSS для 4 состояний кнопки                                                                                                     | ✅ Обновлено                 |
| `prometheus_exporter.py` | Новые метрики live chart                                                                                                       | ✅ Добавлено                 |
