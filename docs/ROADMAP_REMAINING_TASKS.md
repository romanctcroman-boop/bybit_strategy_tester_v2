# Roadmap — оставшиеся крупные задачи

**Дата:** 2026-02-01  
**Источник:** ROADMAP_ADVANCED_IDEAS.md, ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md

---

## Сводка

| Задача | Приоритет | Оценка | Сложность | Первый шаг |
|--------|-----------|--------|-----------|------------|
| Event-driven движок | P2 | 2–4 нед | Высокая | ✅ Скелет: EventQueue, EventDrivenEngine, tests |
| Multi-asset portfolio | P2 | 1–2 нед | Высокая | ✅ MIN_VARIANCE/MAX_SHARPE, diversification_ratio |
| §12 Визуализация | P2 | 3–5 дн | Средняя | ✅ Heatmap, Trade distribution |
| Версионирование / Undo / Шаблоны | P3 | 3–7 дн | Средняя | ✅ БД, API; осталось UI Undo/Redo |
| L2 order book / Generative LOB | P4 | Эксперимент | Очень высокая | Research |

---

## 1. Event-driven движок (2–4 недели)

**Цель:** Очередь событий, один код для backtest и live, отсутствие lookahead bias.

**Архитектура:**
```
EventQueue (FIFO) ← DataHandler | Strategy | ExecutionHandler
     ↓
Portfolio ← OrderEvents, FillEvents
```

**Шаги:**
1. Дизайн `EventDrivenEngine` — интерфейс `on_bar(timestamp, ohlcv)`, `on_tick(timestamp, price)`
2. EventQueue — FIFO событий (BarEvent, TickEvent, OrderEvent, FillEvent)
3. DataHandler — генерирует BarEvent/TickEvent из данных
4. ExecutionHandler — принимает OrderEvent, возвращает FillEvent
5. Интеграция с StrategyBuilderAdapter

**Файлы:** `backend/backtesting/engines/event_driven_engine.py` ✅ (скелет)

**Выполнено (2026-02):** EventQueue, BarEvent, OrderEvent, FillEvent, EventDrivenEngine (load_bars, run), тесты `tests/test_event_driven_engine.py`

**Интеграция StrategyBuilderAdapter:** ✅ create_on_bar_from_adapter(), run_event_driven_with_adapter(). Преобразование SignalResult в OrderEvent по барам.

**ExecutionHandler:** ✅ SimulationExecutionHandler — slippage_bps, latency_bars, fill_ratio, reject_probability, use_high_low_slippage. Интеграция в EventDrivenEngine.

---

## 2. Multi-asset portfolio (1–2 недели)

**Цель:** Кросс-оптимизация, корреляции, Cvxportfolio-подход.

**Выполнено (2026-02):**
- MIN_VARIANCE и MAX_SHARPE allocation (scipy.optimize)
- Diversification ratio в метриках
- Rolling correlations в CorrelationAnalysis
- aggregate_multi_symbol_equity() — агрегация equity curves
- Тесты: test_portfolio_allocation.py, API endpoint

**Cvxportfolio:** ✅ AllocationMethod.CVXPORTFOLIO — convex max-sharpe (cvxpy), fallback на scipy.

---

## 3. §12 Визуализация (3–5 дней)

**Идея:** ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md §12

| Виджет | Описание | Файл | Оценка |
|--------|----------|------|--------|
| **Parameter sensitivity heatmap** | Влияние параметров на метрики | optimization-results.html | ✅ |
| **Trade distribution** | Гистограмма PnL, длительность, время суток | backtest-results.html | ✅ |
| **Regime overlay** | Режимы рынка на графике equity | backtest-results.html | ✅ |

**Реализовано:** Parameter heatmap (optimization_results.js), tradeDistributionChart (backtest_results.js), Regime overlay (чекбокс «Режим рынка», загрузка market-regime/history, box-аннотации на equity chart).

---

## 4. Strategy Builder: версионирование, Undo/Redo, шаблоны (3–7 дней)

**Источник:** STRATEGY_BUILDER_NEXT_STEPS.md

| Задача | Описание | Оценка |
|--------|----------|--------|
| **Версионирование стратегий** | Сохранение версий при изменении, история, откат | 3–5 дн |
| **Undo/Redo в UI** | История действий (блоки, связи), Ctrl+Z, Ctrl+Y | 2–3 дн |
| **Шаблоны стратегий** | RSI Strategy, MACD Crossover, импорт/экспорт | 2–3 дн |

**Выполнено:**
- Таблица `strategy_versions`, миграция 20260201
- API: `GET /strategies/{id}/versions`, `POST /strategies/{id}/revert/{version}`
- **Versions UI:** кнопка Versions в navbar (при открытой стратегии), модалка со списком версий, Restore.

**Undo/Redo:** ✅ История действий (blocks, connections), Ctrl+Z / Ctrl+Y, кнопки в toolbar. Охвачены: add/delete/duplicate block, add/delete connection, drag block, template load, strategy load.

**Шаблоны:** ✅ RSI, MACD и др. в templateData. Export (сохранить как JSON) и Import (загрузить из файла) в модалке Templates.

---

## 5. L2 order book / Generative LOB (экспериментально)

| Идея | Описание | Статус |
|------|----------|--------|
| **L2 order book** | Симуляция стакана для лимитных ордеров | ✅ Начато |
| **Generative LOB** | CGAN для синтеза order book | Research |

**Сделано (2026-02):**
- `backend/experimental/l2_lob/` — модуль L2
- `BybitAdapter.get_orderbook()` — REST API
- `fetch_orderbook()`, `L2Snapshot`, `L2Level` — модели
- `collect_snapshots()` — REST polling, NDJSON
- **WebSocket collector** — `websocket_collector.py`, real-time stream
- `load_snapshots_ndjson()`, `snapshot_to_orderbook_simulator()` — replay
- **CGAN** — `generative_cgan.py` (PyTorch), LOB_CGAN, fit/generate
- **Training** — `scripts/l2_lob_train_cgan.py`, `scripts/l2_lob_collect_ws.py`
- API `GET /api/v1/marketdata/orderbook`

---

## Ссылки

- [ROADMAP_ADVANCED_IDEAS.md](ROADMAP_ADVANCED_IDEAS.md)
- [ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md](ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md)
- [STRATEGY_BUILDER_NEXT_STEPS.md](STRATEGY_BUILDER_NEXT_STEPS.md)
