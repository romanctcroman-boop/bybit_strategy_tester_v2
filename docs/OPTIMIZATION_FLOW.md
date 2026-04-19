# Optimization Flow — Полный алгоритм

> **Версия:** 2026-03-17
> **Стек:** FastAPI · SQLite · Numba · Vanilla JS
> **Файлы:** `optimization_panels.js` · `builder_optimizer.py` · `BacktestModule.js` · `SaveLoadModule.js`

---

## Содержание

1. [Обзор](#1-обзор)
2. [Шаг 1 — Загрузка стратегии](#2-шаг-1--загрузка-стратегии)
3. [Шаг 2 — Настройка критерия оптимизации](#3-шаг-2--настройка-критерия-оптимизации)
4. [Шаг 3 — Старт оптимизации](#4-шаг-3--старт-оптимизации)
5. [Шаг 4 — HTTP-запрос и параллельный polling](#5-шаг-4--http-запрос-и-параллельный-polling)
6. [Шаг 5 — Завершение оптимизации](#6-шаг-5--завершение-оптимизации)
7. [Шаг 6 — Применение оптимальных параметров](#7-шаг-6--применение-оптимальных-параметров)
8. [Шаг 7 — Сохранение стратегии (PUT)](#8-шаг-7--сохранение-стратегии-put)
9. [Шаг 8 — Автоматический запуск бэктеста](#9-шаг-8--автоматический-запуск-бэктеста)
10. [Шаг 9 — Отображение графиков и таблиц](#10-шаг-9--отображение-графиков-и-таблиц)
11. [Шаг 10 — Изучение результатов пользователем](#11-шаг-10--изучение-результатов-пользователем)
12. [Схема потока данных](#12-схема-потока-данных)
13. [Рекомендации по использованию](#13-рекомендации-по-использованию)
14. [Как тестировать](#14-как-тестировать)
15. [Известные ограничения](#15-известные-ограничения)

---

## 1. Обзор

Алгоритм оптимизации работает в три большие фазы:

| Фаза                     | Что происходит                                                            | Время    |
| ------------------------ | ------------------------------------------------------------------------- | -------- |
| **Оптимизация**          | Backend перебирает все комбинации параметров через Numba prange           | 1–10 мин |
| **Применение**           | Frontend записывает лучшие параметры в блоки, отключает режим оптимизации | < 1 с    |
| **Сохранение + Бэктест** | PUT обновляет стратегию в БД, затем запускается полный бэктест            | 5–30 с   |

**Ключевые свойства:**

- **Не создаётся новая стратегия** — обновляется текущая (PUT, не POST)
- **Режим оптимизации выключается** после применения — блок показывает конкретное значение
- **Бэктест запускается автоматически** — пользователь сразу видит графики
- **Прогресс виден в реальном времени** — polling каждые 2 секунды через файл `.run/optimizer_progress.json` (shared across all 4 uvicorn workers)

---

## 2. Шаг 1 — Загрузка стратегии

**Триггер:** пользователь открывает `strategy-builder.html?id=<uuid>`
**Файл:** `frontend/js/components/SaveLoadModule.js → loadStrategy()`

```
GET /api/v1/strategy-builder/strategies/{id}
```

**Что загружается:**

```javascript
strategy.blocks[]  →  strategyBlocks[]  (канвас)
  block.params.period = 14              // текущее рабочее значение
  block.optimizationParams.period = {
    enabled: true,                      // ⚙ желтый индикатор виден
    min: 5, max: 30, step: 1           // диапазон для оптимизации
  }

strategy.connections[]  →  провода между блоками
_loadedStrategyName = strategy.name    // критично: Save vs Save As detection
window.history.pushState(?id=<uuid>)   // URL обновлен
```

**Итог:** блоки с жёлтыми значками ⚙ показывают что параметры готовы к оптимизации.

---

## 3. Шаг 2 — Настройка критерия оптимизации

**Триггер:** пользователь открывает панель **Evaluation**, выбирает метрику
**Файл:** `EvaluationCriteriaPanel → window.evaluationCriteriaPanel.getCriteria()`

```javascript
// Пример для DCA-RSI-6:
{
  primary_metric: "net_profit",   // критерий отбора лучшей комбинации
  ranking_mode: "single",
  secondary_metrics: [],
  use_composite: false
}
```

**Доступные метрики:**

| Метрика        | ID              |
| -------------- | --------------- |
| Net Profit     | `net_profit`    |
| Sharpe Ratio   | `sharpe_ratio`  |
| Total Return % | `total_return`  |
| Calmar Ratio   | `calmar_ratio`  |
| Profit Factor  | `profit_factor` |
| Sortino Ratio  | `sortino_ratio` |
| Win Rate       | `win_rate`      |
| CAGR           | `cagr`          |

---

## 4. Шаг 3 — Старт оптимизации

**Триггер:** кнопка **Start Optimization** в панели Optimization
**Файл:** `optimization_panels.js → startOptimization()`

```
1. Guard: if (isRunning) return                   // защита от двойного клика
2. Guard: if (parameterRanges.length === 0) warn  // нет параметров для оптимизации
3. Guard: degenerate ranges (min === max) warn    // диапазон вырожден

setRunningState(true):
  ├─ btn → disabled, текст "Running..."
  ├─ openFloatingWindow('floatingWindowOptimization')  // панель открыта принудительно
  ├─ #optProgressSection.display = 'block'             // прогресс бар виден
  └─ #optProgressDetails = "Starting... (Numba JIT ~30s first run)"
```

**Payload для backend:**

```javascript
POST /api/v1/strategy-builder/strategies/{id}/optimize
{
  symbol: "ETHUSDT",
  interval: "30",
  start_date: "2025-01-01",
  end_date: "2026-03-17",
  optimize_metric: "net_profit",
  method: "grid_search",
  parameter_ranges: [
    { param_path: "rsi_1.period",              low: 5,   high: 30,  step: 1   },
    { param_path: "sltp_1.stop_loss_percent",  low: 0.5, high: 5.0, step: 0.5 },
    { param_path: "sltp_1.take_profit_percent",low: 0.5, high: 5.0, step: 0.5 }
  ],
  initial_capital: 10000,
  leverage: 10,
  commission: 0.0007,    // НИКОГДА не менять — TradingView parity
  direction: "both"
}
```

---

## 5. Шаг 4 — HTTP-запрос и параллельный polling

**Файл:** `optimization_panels.js → startBuilderOptimization()`

```
┌─ setInterval(2000ms) ────────────────────────────────────────┐
│  GET /api/v1/strategy-builder/strategies/{id}/optimize/progress│
│  ← { status:"running", tested:50000, total:304668,           │
│       percent:16.4, best_score:0.0, results_found:0,         │
│       speed:45000, eta_seconds:57 }                          │
│                                                               │
│  UI update:                                                   │
│  #optProgressFill.width = "16.4%"                            │
│  #optProgressPercent = "16%"                                  │
│  #optProgressDetails = "50,000/304,668 · 45,000 c/s · ETA 57s"│
└──────────────────────────────────────────────────────────────┘

POST /api/v1/.../optimize  [BLOCKING — ждём ответа]
  ↓
  backend/optimization/builder_optimizer.py:
    _run_dca_mixed_batch_numba()  ← модульная функция (не метод класса)
      806 RSI групп × 378 SLTP комбо = 304,668 итераций
      Numba prange: параллельная обработка всех SLTP за один проход
      progress_callback() каждые ~806 итераций
        → update_optimization_progress()
        → запись в .run/optimizer_progress.json (атомарная, через .tmp)
  ↓
  ← { best_params, best_metrics, top_results[20], best_score,
      tested_combinations, execution_time_seconds }
```

**Прогресс-файл (cross-worker):**

```json
{
    "c413f3a8-...": {
        "status": "running",
        "tested": 150000,
        "total": 304668,
        "percent": 49.2,
        "best_score": 1.87,
        "results_found": 12,
        "speed": 48000,
        "eta_seconds": 32,
        "started_at": 1742165000.0,
        "updated_at": 1742165032.5
    }
}
```

> **Почему файл, а не память?** Uvicorn запускается с `--workers 4` — 4 отдельных Python-процесса. POST попадает в worker A, GET progress — в worker B. In-memory dict не виден между процессами. JSON-файл — shared state для всех workers.

---

## 6. Шаг 5 — Завершение оптимизации

**Файл:** `optimization_panels.js → handleOptimizationComplete(data)`

```
1. clearInterval(progressInterval)
2. setRunningState(false) → кнопка снова активна
3. #optProgressSection.display = 'none'    // прогресс скрыт
4. #optProgressFill.width = '0%'           // сброс

Формирование объекта results:
  {
    best_params: {
      "rsi_1.period": 21,
      "sltp_1.stop_loss_percent": 1.5,
      "sltp_1.take_profit_percent": 3.0
    },
    best_metrics: {
      net_profit: 4230.5,
      sharpe_ratio: 1.87,
      total_return: 42.3,
      max_drawdown: 8.1,
      win_rate: 62.3
    },
    top_results: [...20 лучших комбинаций],
    optimize_metric: "net_profit",
    tested_combinations: 304668,
    execution_time: 141.2
  }

5. openFloatingWindow('floatingWindowResults')  // Results панель открывается
6. requestAnimationFrame(() => displayQuickResults(results))
   → #resultsQuickSummary заполняется:
     ┌────────────────────────────────────┐
     │ Критерий: Net Profit               │
     │ Sharpe: 1.87   Return: +42.3%      │
     │ Max DD: 8.1%   Win Rate: 62.3%     │
     │ Net Profit: +4,230 USD             │
     │ Best of 304,668 trials             │
     └────────────────────────────────────┘

7. applyBestParamsToBlocks(best_params)  → ШАГ 6
```

---

## 7. Шаг 6 — Применение оптимальных параметров

**Файл:** `optimization_panels.js → applyBestParamsToBlocks()`

```
Для каждого "blockId.paramKey" → value:

  updateBlockParam("rsi_1", "period", 21)
    block.params.period = 21          // значение записано в блок
    renderConnections()               // провода обновлены
    validateBlockParams(block)        // локальная валидация

// ВЫКЛЮЧЕНИЕ РЕЖИМА ОПТИМИЗАЦИИ:
  block.optimizationParams["period"].enabled = false
  block.optimizationParams["stop_loss_percent"].enabled = false
  block.optimizationParams["take_profit_percent"].enabled = false

renderBlocks()
  → все блоки перерисованы
  → updateBlockOptimizationIndicator() для каждого блока
  → has-optimization class снят → ⚙ индикатор исчез

renderBlockProperties()
  → боковая панель: period = 21 (не диапазон, конкретное значение)

extractOptimizationParamsFromBlocks(blocks)  → [] (все enabled=false)
updateParameterRangesFromBlocks([])
  → #paramRangesList = "Add indicator blocks to configure parameter ranges"
state.parameterRanges = []

showNotification("✅ Применены оптимальные параметры (3 значений). Режим оптимизации выключен.")
```

**Состояние блока RSI после шага:**

```
До:  block.params.period = 14, optimizationParams.period.enabled = true   (⚙ видно)
После: block.params.period = 21, optimizationParams.period.enabled = false  (⚙ нет)
```

---

## 8. Шаг 7 — Сохранение стратегии (PUT)

**Файл:** `SaveLoadModule.js → saveStrategy()`

```
buildStrategyPayload():
  {
    name: "DCA-RSI-6",
    blocks: [
      {
        id: "rsi_1",
        type: "rsi",
        params: { period: 21, ... },           // ← оптимальное значение
        optimizationParams: {
          period: { enabled: false, min:5, max:30, step:1 }  // ← флаг выключен
        }
      },
      {
        id: "sltp_1",
        type: "static_sltp",
        params: { stop_loss_percent: 1.5, take_profit_percent: 3.0, ... },
        optimizationParams: {
          stop_loss_percent:  { enabled: false, ... },
          take_profit_percent: { enabled: false, ... }
        }
      },
      ...
    ],
    connections: [...]
  }

nameChanged? → false (имя не менялось)
→ method = PUT (не POST!)

PUT /api/v1/strategy-builder/strategies/{id}
← 200 OK  { updated_at: "2026-03-17T..." }

showNotification("Стратегия успешно сохранена!")
```

> ⚠️ **Критично:** `_loadedStrategyName` следит за именем. Если пользователь переименовал стратегию перед оптимизацией — будет показан `confirm()` "создать новую или перезаписать оригинал". Для автоматического флоу имя не должно меняться.

---

## 9. Шаг 8 — Автоматический запуск бэктеста

**Файл:** `BacktestModule.js → runBacktest()`

```
await new Promise(resolve => setTimeout(resolve, 400))  // ждем завершения PUT

runBacktest():
  1. await saveStrategy()  // принудительный PUT перед бэктестом
     (защита от stale state — autoSave имеет кэш дедупликации и может пропустить)

  2. buildBacktestRequest() → {
       strategy_id, symbol, interval,
       start_date, end_date,
       initial_capital, leverage, commission: 0.0007,
       direction
     }

  3. POST /api/v1/strategy-builder/strategies/{id}/backtest
     [backend читает blocks из БД, которые мы только что обновили]
     ← {
         metrics: { net_profit, sharpe_ratio, max_drawdown, ... },
         trades: [{ entry, exit, pnl, mfe_pct, mae_pct, ... }],
         equity_curve: { timestamps[], equity[], bh_equity[] },
         backtest_id: "uuid"
       }
```

---

## 10. Шаг 9 — Отображение графиков и таблиц

**Файл:** `BacktestModule.js → displayBacktestResults()`

```
modal.classList.add('active')       // модал открывается

renderResultsSummaryCards(results)
  → карточки: Net Profit, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor

renderOverviewMetrics(results)
  → таблица топ-метрик с цветовой индикацией

renderTradesTable(results.trades)
  → колонки: #, Direction, Entry, Exit, PnL, PnL%, MFE, MAE, Duration
  → каждая строка кликабельна — открывает детали сделки

renderAllMetrics(results)
  → 166 метрик: Returns, Risk, Drawdown, Efficiency, Statistical

// Equity Curve:
window._sbEquityChartData = {
  timestamps, equity,           // линия стратегии
  bh_equity,                    // линия Buy & Hold
  trades,                       // точки входа (▲) и выхода (▼)
  initial_capital: 10000
}
→ Chart.js рисует интерактивный график с zoom/pan
```

---

## 11. Шаг 10 — Изучение результатов пользователем

**Что видит пользователь после завершения всего флоу:**

```
┌─ Canvas (Strategy Builder) ───────────────────────────────────┐
│                                                                │
│  [RSI Block]   period = 21        (⚙ нет — режим выключен)   │
│  [SLTP Block]  SL = 1.5%  TP = 3.0%  (⚙ нет)               │
│  [DCA Block]   ...конфигурация DCA...                         │
│                                                                │
│  → Нажав на блок RSI, видишь значение 21 в поле "period"      │
│  → Понятно что оптимизатор выбрал именно 21 из диапазона 5-30 │
└────────────────────────────────────────────────────────────────┘

┌─ Панель Results (floating, справа) ───────────────────────────┐
│  Критерий оптимизации: Net Profit                              │
│  ┌──────┬──────────┬─────────┬──────────┐                    │
│  │Sharpe│  Return  │ Max DD  │ Win Rate │                    │
│  │ 1.87 │ +42.3%   │  8.1%  │  62.3%  │                    │
│  └──────┴──────────┴─────────┴──────────┘                    │
│  Net Profit: +4,230 USD                                        │
│  Best of 304,668 trials                                        │
└────────────────────────────────────────────────────────────────┘

┌─ Backtest Modal ───────────────────────────────────────────────┐
│  [Вкладка Overview]                                            │
│    Equity Curve: стратегия (синяя) vs Buy&Hold (серая)         │
│    Drawdown Chart: просадка по времени                          │
│    Summary Cards: топ-5 метрик                                  │
│                                                                │
│  [Вкладка Trades]                                              │
│    Таблица всех сделок: вход/выход/PnL/MFE/MAE                 │
│    → видно где стратегия работала хорошо, где нет              │
│                                                                │
│  [Вкладка All Metrics]                                         │
│    166 метрик: CAGR, Calmar, Sortino, Recovery Factor, ...    │
└────────────────────────────────────────────────────────────────┘
```

**Что анализировать:**

- `period=21` → следующий раз попробовать диапазон 18–24 с шагом 1 (сужение)
- `SL=1.5%, TP=3.0%` → RR=2:1, проверить нет ли лучше при SL=1.0–2.0%
- Если Win Rate < 50% но Profit Factor > 2 → стратегия работает на крупных позициях
- Если Max DD > 15% → рассмотреть другой direction или добавить фильтр тренда

---

## 12. Схема потока данных

```
                        ┌─────────────────────────────────────────────┐
                        │              ПОЛЬЗОВАТЕЛЬ                    │
                        └───────┬────────────────────────┬────────────┘
                                │ 1. Загружает стратегию  │ 2. Выбирает метрику
                                ▼                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Browser)                                  │
│                                                                               │
│  loadStrategy()                                                               │
│  GET /strategies/{id} ──► strategyBlocks[{params, optimizationParams}]       │
│                                           ↓                                  │
│  startOptimization()                                                          │
│  ├─ setRunningState(true) → бар виден                                        │
│  ├─ setInterval(2s) ──── GET .../progress → #optProgressFill                 │
│  └─ POST .../optimize [BLOCKING] ────────────────────────────────────────┐  │
│                                                                           │  │
└───────────────────────────────────────────────────────────────────────────│──┘
                                                                            │
┌──────────────────────────────────────────────────────────────────────────▼──┐
│                           BACKEND (Python)                                    │
│                                                                               │
│  builder_optimizer.py:                                                        │
│  _run_dca_mixed_batch_numba()                                                 │
│    806 RSI groups × 378 SLTP = 304,668 combos                                │
│    Numba prange ──────────────────────────────────► progress_callback()      │
│                                                         ↓                    │
│                                              .run/optimizer_progress.json    │
│                                              (atomic write, all 4 workers)   │
│                                                                               │
│  ← { best_params, best_metrics, top_results[20] }                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                     FRONTEND (после получения ответа)                         │
│                                                                               │
│  handleOptimizationComplete()                                                 │
│  ├─ openFloatingWindow('Results') → displayQuickResults()                    │
│  └─ applyBestParamsToBlocks()                                                │
│       ├─ updateBlockParam() → block.params ← оптимальные значения            │
│       ├─ optimizationParams[key].enabled = false  ← ⚙ выключен              │
│       ├─ renderBlocks() + renderBlockProperties()                             │
│       └─ _saveCurrentAndBacktest()                                           │
│             ├─ PUT /strategies/{id} ← стратегия обновлена в БД               │
│             └─ runBacktest()                                                  │
│                   └─ POST /strategies/{id}/backtest                           │
│                         ↓                                                    │
│                   displayBacktestResults()                                   │
│                   ├─ Equity Curve (Chart.js)                                 │
│                   ├─ Trades Table                                             │
│                   └─ 166 метрик                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Рекомендации по использованию

### 13.1 Стратегия настройки диапазонов

**Первый прогон — широкий поиск:**

```
period:  min=5,  max=50, step=5   → 10 значений
SL:      min=0.5, max=5.0, step=0.5 → 10 значений
TP:      min=0.5, max=5.0, step=0.5 → 10 значений
Итого: 10 × 10 × 10 = 1,000 комбо   (~1 секунда)
```

**Второй прогон — сужение вокруг лучшего значения:**

```
Если первый прогон дал period=20:
period:  min=16, max=24, step=1   → 9 значений
SL:      min=1.0, max=2.5, step=0.25 → 7 значений
TP:      min=2.5, max=4.5, step=0.25 → 9 значений
Итого: 9 × 7 × 9 = 567 комбо   (< 1 секунды)
```

**Третий прогон — финальная точность:**
Использовать Bayesian (TPE) вместо Grid Search — он сам находит область максимума.

### 13.2 Выбор критерия оптимизации

| Цель               | Рекомендуемый критерий          | Почему                      |
| ------------------ | ------------------------------- | --------------------------- |
| Максимальный доход | `net_profit` или `total_return` | Прямой результат            |
| Стабильность       | `sharpe_ratio`                  | Учитывает волатильность     |
| Защита капитала    | `calmar_ratio`                  | Return / Max Drawdown       |
| Торговая система   | `profit_factor`                 | Gross Profit / Gross Loss   |
| Долгосрочный рост  | `cagr`                          | Compound Annual Growth Rate |

> ⚠️ **Не рекомендуется** оптимизировать по `win_rate` — стратегии с WR=80% и PF=0.5 убыточны.

### 13.3 Предотвращение переобучения (Overfitting)

1. **Разделяй период:** оптимизируй на 70% данных, проверяй на оставшихся 30%
2. **Walk-Forward:** используй метод Walk-Forward Analysis в панели Optimization
3. **Минимум сделок:** устанавливай `min_trades >= 30` в constraints
4. **Проверяй по Sharpe:** даже если оптимизируешь по Net Profit, Sharpe >= 1.0 обязателен
5. **Не добавляй слишком много параметров:** каждый дополнительный параметр увеличивает риск переобучения

### 13.4 Признаки хорошего результата

```
✅ Sharpe Ratio   >= 1.5
✅ Max Drawdown   <= 15%
✅ Profit Factor  >= 1.5
✅ Win Rate       >= 45%  (для трендовых систем)
✅ Trades         >= 30   (достаточная статистика)
✅ CAGR           >= 30%  (при leverage 10x и commission 0.07%)
```

### 13.5 После оптимизации — что делать дальше

1. **Изучи сделки** в таблице Trades: найди убыточные кластеры (боковик? определенный час суток?)
2. **Сравни с Buy & Hold** на графике — если стратегия хуже BH без причины — что-то не так
3. **Открой блок RSI** (или другой) — убедись что значение `period=21` логично для выбранного TF
4. **Добавь фильтр тренда** если много ложных сигналов в боковике
5. **Запусти повторную оптимизацию** с другими параметрами (добавь в блок ⚙ другие поля)

---

## 14. Как тестировать

### 14.1 Быстрая проверка (< 2 минут)

```
1. Открыть: http://localhost:8000/frontend/strategy-builder.html?id=c413f3a8-109b-496d-aeaa-c294c306658c
2. Убедиться что на RSI блоке есть ⚙ (желтый индикатор)
3. В Evaluation выбрать: net_profit
4. В Optimization: Method = Grid Search
5. Нажать "Start Optimization"

Ожидаемое поведение:
  ✅ Панель Optimization открывается принудительно
  ✅ Прогресс бар появляется сразу ("Starting... Numba JIT ~30s")
  ✅ Через 30–60s бар начинает двигаться с цифрами "N/304,668"
  ✅ После завершения: открывается панель Results с метриками
  ✅ ⚙ на блоках ИСЧЕЗАЕТ
  ✅ Значения в блоке обновляются (период RSI изменился)
  ✅ Бэктест запускается автоматически (модал открывается)
  ✅ В списке стратегий по-прежнему одна стратегия "DCA-RSI-6" (не создана новая)
```

### 14.2 Проверка через DevTools (F12)

**Console** должен показывать:

```javascript
[OptPanels] Builder optimization → /api/v1/strategy-builder/strategies/.../optimize
[OptPanels] handleOptimizationComplete v... called. best_params: {rsi_1.period: 21, ...}
[OptPanels] Applying rsi_1.period = 21
[OptPanels] Applied 3/3 params
[OptPanels] Strategy saved (PUT) with optimized params
[OptPanels] Triggering backtest with optimized params...
[Strategy Builder] runBacktest called
[Strategy Builder] Backtest success: {...}
```

**Network** (вкладка Network, фильтр XHR):

```
POST .../optimize          → 200 OK  (тело: best_params не пустое)
GET  .../optimize/progress → 200 OK  (повторяется каждые 2s)
PUT  .../strategies/{id}   → 200 OK  (НЕ POST — убедиться!)
POST .../strategies/{id}/backtest → 200 OK
```

### 14.3 Проверка прогресс-файла

```powershell
# В терминале во время работы оптимизатора:
Get-Content "d:\bybit_strategy_tester_v2\.run\optimizer_progress.json" | ConvertFrom-Json
# Должно показывать status="running", tested > 0, percent > 0
```

### 14.4 Проверка что стратегия не задублировалась

```powershell
# Через API:
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/strategy-builder/strategies?page=1&page_size=100" -UseBasicParsing |
  Select-Object -ExpandProperty Content |
  ConvertFrom-Json |
  Select-Object -ExpandProperty strategies |
  Where-Object { $_.name -like "*DCA-RSI*" } |
  Select-Object id, name, updated_at
# Должна быть ОДНА запись, updated_at обновился
```

### 14.5 Автоматизированные тесты

```powershell
# Запуск тестов оптимизатора:
cd d:\bybit_strategy_tester_v2
.venv\Scripts\python.exe -m pytest tests\test_builder_optimizer.py -v

# Запуск тестов API strategy-builder:
.venv\Scripts\python.exe -m pytest tests\backend\api\routers\test_strategy_builder.py -v

# Быстрые тесты (без медленных):
.venv\Scripts\python.exe -m pytest tests\ -v -m "not slow" -q
```

### 14.6 Тест прогресс-polling вручную

```javascript
// В DevTools Console, во время работы оптимизации:
fetch("/api/v1/strategy-builder/strategies/c413f3a8-109b-496d-aeaa-c294c306658c/optimize/progress")
    .then((r) => r.json())
    .then(console.log);
// Должно вернуть: { status: "running", percent: 16.4, tested: 50000, ... }
```

---

## 15. Известные ограничения

| Ограничение                        | Описание                                                         | Обходной путь                                      |
| ---------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------- |
| **Numba JIT**                      | Первый запуск медленнее на ~60с (компиляция)                     | Прогресс показывает "Preparing..." — это нормально |
| **Grid Search + много параметров** | 5 параметров × большие диапазоны = миллионы комбо                | Использовать Bayesian или Random Search            |
| **commission = 0.0007**            | Нельзя менять без явного согласования                            | TradingView parity, см. `CLAUDE.md §5`             |
| **DATA_START_DATE = 2025-01-01**   | Данных до этой даты нет в БД                                     | Настроить в `backend/config/database_policy.py`    |
| **Save As при переименовании**     | Если сменить имя стратегии перед оптимизацией — появится confirm | Не менять имя во время сессии оптимизации          |
| **4 uvicorn workers**              | Прогресс через файл, не память                                   | `.run/optimizer_progress.json` должен существовать |

---

_Документ сгенерирован: 2026-03-17_
_Актуальная версия: `docs/OPTIMIZATION_FLOW.md`_
