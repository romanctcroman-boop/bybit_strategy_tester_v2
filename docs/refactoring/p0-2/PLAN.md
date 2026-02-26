# P0-2: Рефакторинг backtest_results.js

**Дата:** 2026-02-26  
**Статус:** 🚀 В работе  
**Приоритет:** P0 (критичный)

---

## 🎯 Цели

1. **Устранить утечки памяти Chart.js** — 7 экземпляров Chart без `.destroy()` при переинициализации
2. **Вынести ChartManager** — централизованный lifecycle для всех Chart.js экземпляров
3. **Вынести TradesTable** — рендеринг/сортировка/пагинация (строки 2338–2620)
4. **Вынести MetricsPanel** — обновление TV-вкладок (строки 1472–2337)
5. **Вынести ComparePanel** — режим сравнения бэктестов (строки ~3100–3400)
6. **Добавить тесты** — регрессионные тесты на модули

---

## 🔍 Найденные проблемы

### Критично — Утечки памяти Chart.js

| Переменная               | `new Chart(...)` | `.destroy()` |
| ------------------------ | ---------------- | ------------ |
| `drawdownChart`          | Строка 896       | ❌ НЕТ       |
| `returnsChart`           | Строка 918       | ❌ НЕТ       |
| `monthlyChart`           | Строка 943       | ❌ НЕТ       |
| `tradeDistributionChart` | Строка 962       | ❌ НЕТ       |
| `winLossDonutChart`      | Строка 1048      | ❌ НЕТ       |
| `waterfallChart`         | Строка 1095      | ❌ НЕТ       |
| `benchmarkingChart`      | Строка 1191      | ❌ НЕТ       |

**Результат:** При каждом `initCharts()` или перерендере Canvas `#drawdownChart` и т.д.
создаются новые экземпляры поверх старых → `"Canvas is already in use"` ошибки в console,
постепенное увеличение памяти (особенно при SPA навигации).

`clearAllDisplayData()` только очищает `data.labels/datasets`, но **не вызывает `.destroy()`**.

### Среднее — Размер функций

| Функция                      | Строки                 | Проблема                  |
| ---------------------------- | ---------------------- | ------------------------- |
| `updateTVDynamicsTab()`      | 1555–1991 = 437 строк  | Слишком большая           |
| `updateTVTradeAnalysisTab()` | 1992–2233 = 242 строки | Можно вынести             |
| `updateTVRiskReturnTab()`    | 2234–2337 = 104 строки | ОК                        |
| `updateTVTradesListTab()`    | 2338–2495 = 158 строк  | ОК                        |
| `clearAllDisplayData()`      | 2977–3100 = 124 строки | ОК, но связана с утечками |
| `initCharts()`               | 855–1263 = 409 строк   | Кандидат для ChartManager |

---

## 📐 Архитектура после рефакторинга

```
frontend/js/
├── pages/
│   └── backtest_results.js     ← Основной файл (оркестратор ~2500 строк)
├── components/
│   ├── ChartManager.js         ← НОВЫЙ: lifecycle Chart.js (init/destroy/update)
│   ├── TradesTable.js          ← НОВЫЙ: рендер/сортировка/пагинация
│   └── MetricsPanels.js        ← НОВЫЙ: updateTVDynamicsTab, updateTVTradeAnalysisTab
└── core/
    ├── StateManager.js         ← Существующий
    └── state-helpers.js        ← Существующий
```

---

## 📋 Фазы выполнения

### Фаза 1: ChartManager.js (Приоритет 🔴 Критичный)

**Цель:** Устранить все утечки памяти Chart.js

```javascript
// frontend/js/components/ChartManager.js
export class ChartManager {
    constructor() {
        this._charts = new Map(); // name → Chart instance
    }

    init(name, canvas, config) {
        this.destroy(name); // Всегда уничтожаем перед созданием
        const chart = new Chart(canvas, config);
        this._charts.set(name, chart);
        return chart;
    }

    destroy(name) {
        const existing = this._charts.get(name);
        if (existing) {
            existing.destroy();
            this._charts.delete(name);
        }
    }

    destroyAll() {
        for (const [name] of this._charts) {
            this.destroy(name);
        }
    }

    get(name) {
        return this._charts.get(name) ?? null;
    }
    has(name) {
        return this._charts.has(name);
    }
    getAll() {
        return [...this._charts.values()];
    }
}

export const chartManager = new ChartManager();
```

**Изменения в backtest_results.js:**

- Импортировать `{ chartManager }` из `../components/ChartManager.js`
- В `initCharts()`: заменить `drawdownChart = new Chart(...)` → `drawdownChart = chartManager.init('drawdown', canvas, config)`
- В `clearAllDisplayData()`: добавить `chartManager.destroyAll()` перед очисткой data

### Фаза 2: TradesTable.js (Приоритет 🟡 Средний)

**Вынести из backtest_results.js:**

- `updateTVTradesListTab(trades, config)` — строки 2338–2495
- `renderTradesPage(tbody)` — строки 2496–2505
- `renderTradePagination(totalTrades)` — строки 2506–2542
- `updateTradePaginationControls()` — строки 2543–2557
- `removeTradePagination()` — строки 2558–2563
- `tradesPrevPage()` — строки 2564–2572
- `tradesNextPage()` — строки 2573–2583
- `sortTradesBy(key)` — строки 2584–2604
- `updateTradeSortIndicators(activeKey)` — строки 2605–2620

**Итого: ~283 строки → TradesTable.js**

### Фаза 3: MetricsPanels.js (Приоритет 🟢 Низкий)

**Вынести из backtest_results.js:**

- `updateTVSummaryCards(metrics)` — строки 1499–1554
- `updateTVDynamicsTab(metrics, config, trades, equityCurve)` — строки 1555–1991
- `updateTVTradeAnalysisTab(metrics, config, _trades)` — строки 1992–2233
- `updateTVRiskReturnTab(metrics, _trades, _config)` — строки 2234–2337
- `formatTVCurrency(value, pct, showSign)` — строки 1472–1489
- `formatTVPercent(value, showSign)` — строки 1490–1498

**Итого: ~866 строк → MetricsPanels.js**

---

## ✅ Критерии приёмки

- [ ] **0 ошибок** `"Canvas is already in use"` в console при многократном открытии бэктеста
- [ ] `chartManager.destroyAll()` вызывается перед каждым `initCharts()`
- [ ] **Все тесты проходят:** `npm test` — 245+ passed (нет регрессий)
- [ ] **ESLint:** `npx eslint frontend/js/` — 0 новых ошибок
- [ ] `backtest_results.js` < 3500 строк после рефакторинга

---

## 🧪 Тесты (tests/frontend/components/)

### ChartManager.test.js

```javascript
describe('ChartManager', () => {
  test('init() destroys existing before creating new', () => { ... });
  test('destroyAll() cleans all instances', () => { ... });
  test('get() returns null for unknown chart', () => { ... });
  test('double init() does not create duplicate canvas warning', () => { ... });
});
```

---

## ⏱️ Оценка

| Фаза      | Описание                  | Часы       |
| --------- | ------------------------- | ---------- |
| 1         | ChartManager + fix утечек | 2–3ч       |
| 2         | TradesTable.js            | 3–4ч       |
| 3         | MetricsPanels.js          | 4–5ч       |
| 4         | Тесты                     | 3–4ч       |
| 5         | Документация + commit     | 1ч         |
| **Итого** |                           | **13–17ч** |

---

_Создано: 2026-02-26_
