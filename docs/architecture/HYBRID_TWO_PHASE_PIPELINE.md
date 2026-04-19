# Гибридная двухфазная архитектура — формализованный pipeline

**Дата:** 2026-01-31  
**Статус:** Формализовано

---

## 1. Обзор pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                  HYBRID TWO-PHASE BACKTEST PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Phase 1: RESEARCH (Optimization)                                                │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  NumbaEngineV2  или  GPUEngineV2  (быстрый перебор 10³–10⁶ комбинаций)     │ │
│  │  Выход: Top-N кандидатов по score (Sharpe, Return, и др.)                   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Phase 2: VALIDATION (Gold Standard)                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  FallbackEngineV4  — эталонные метрики для Top-N                           │ │
│  │  Выход: Финальные метрики, ранжирование, best_params                        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                           │
│                                      ▼                                           │
│  Phase 3: PAPER / LIVE (опционально)                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  Paper: симулятор с live-данными  │  Live: реальный OrderExecutor           │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Точность и паритет вычислений

### 2.1 Когда метрики совпадают 100%

| Сценарий | Research Engine | Validation Engine | Паритет |
|----------|-----------------|-------------------|---------|
| Базовые стратегии (RSI, MACD, SL/TP) | NumbaEngineV2 | FallbackEngineV4 | **100%** |
| Pyramiding, Multi-TP, ATR, Trailing | NumbaEngineV2 | FallbackEngineV4 | **100%** |
| Bar Magnifier (intrabar SL/TP) | NumbaEngineV2 | FallbackEngineV4 | **100%** |

**Источник:** `engine_selector.py`, `ENGINE_PARITY.md` — NumbaEngineV2 реализует полный контракт FallbackV4 (Multi-TP, ATR, Trailing, DCA-совместимость).

**Следствие:** Результаты Phase 1 (Numba) и Phase 2 (FallbackV4) **идентичны** по метрикам для одних и тех же параметров. Ранжирование не меняется.

### 2.2 Когда паритет НЕ гарантирован

| Сценарий | Research Engine | Validation Engine | Паритет |
|----------|-----------------|-------------------|---------|
| RSI grid search (VBT screening) | **VectorBT** | FallbackEngineV4 | **10–60% drift** |
| DCA / Grid / Martingale | — | **DCAEngine** только | Phase 1 отсутствует |

**VectorBT:** Используется только для **screening** (быстрый отсев). Финальные числа всегда берутся из Fallback. Возможны «false champions» — VBT может поставить на верх другой набор параметров, чем Fallback.

**DCA:** DCAEngine — отдельный движок, без Numba/GPU аналога. Все прогоны идут через DCAEngine. Метрики точные, но оптимизация медленная (1x).

### 2.3 Параметры и воспроизводимость

| Вопрос | Ответ |
|--------|-------|
| Лучшие params из Numba = лучшие для FallbackV4? | **Да**, при 100% паритете (Numba ↔ FallbackV4). |
| Финальные метрики (Sharpe, Return, MaxDD) | **Идентичны** при Numba ↔ FallbackV4. |
| Нужна ли отдельная Validation фаза при Numba? | Для **аудита/сертификации** — да (FallbackV4 как «золотой эталон»). Для расчётов — нет, Numba даёт те же числа. |
| Paper / Live = Backtest? | **Нет.** Исполнение, slippage, latency — иные. Ожидаем расхождение 5–30% в реальной торговле. |

---

## 3. Текущая реализация в проекте

### 3.1 Одиночный бэктест (Strategy Builder, API)

```
User Request → BacktestService → FallbackEngineV4 (или DCAEngine) → Result
```

Всегда используется эталонный движок. Метрики считаются с максимальной точностью.

### 3.2 Grid Search (optimizations API)

```
Request → engine_type (numba/gpu/auto) → NumbaEngineV2 или GPUEngineV2
         → Все комбинации на быстром движке
         → Top result (метрики уже эталонные при Numba)
```

При `engine_type="numba"` метрики **совпадают** с FallbackV4. Отдельная Validation не обязательна.

### 3.3 Two-Stage (VBT → Fallback)

```
Stage 1: VectorBT screening (быстро, приблизительно)
Stage 2: FallbackEngineV4 validation топ-N
         → Финальные метрики только из Fallback
```

Endpoint: `POST /optimizations/two-stage/optimize`. Используется при больших сетках и необходимости отсеять false champions.

### 3.4 DCA / Strategy Builder с DCA

```
Request → DCAEngine (единственный движок)
```

Быстрой фазы нет. Все прогоны — на DCAEngine.

---

## 4. Рекомендации по точности

### 4.1 Для максимальной уверенности

1. **Одиночный бэктест:** всегда FallbackV4 (или DCAEngine для DCA).
2. **Оптимизация:** Numba для перебора, при желании — **опциональный** FallbackV4 re-run для best_params (режим `validate_best_with_fallback=true`).
3. **Two-Stage:** только для RSI-like стратегий; финальные числа — только из Fallback.

### 4.2 Ожидаемые расхождения

| Этап | Источник расхождений |
|------|----------------------|
| Numba ↔ FallbackV4 | **0%** (при корректной реализации) |
| VBT ↔ FallbackV4 | **10–60%** (разная логика исполнения) |
| Backtest ↔ Paper | **5–15%** (реальное исполнение, задержки) |
| Backtest ↔ Live | **10–30%** (slippage, latency, partial fills) |

---

## 5. Формальная спецификация pipeline

### 5.1 Условия применимости

| Условие | Phase 1 | Phase 2 |
|---------|---------|---------|
| strategy_type ∉ {dca, grid, martingale} | NumbaEngineV2 | FallbackEngineV4 |
| strategy_type ∈ {dca, grid, martingale} | — | DCAEngine |
| two_stage=True, RSI grid | VectorBT | FallbackEngineV4 |

### 5.2 Выходы по фазам

| Фаза | Выход |
|------|-------|
| Research | `[(params, score), ...]` — ранжированный список |
| Validation | `[(params, metrics_fallback), ...]` — эталонные метрики |
| Best | `best_params`, `best_metrics` — для сохранения/Paper/Live |

---

_Документ обновляется при изменении engine_selector или добавлении новых движков._
