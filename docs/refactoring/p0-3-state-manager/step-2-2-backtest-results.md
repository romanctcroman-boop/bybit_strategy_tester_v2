# Шаг 2.2: Миграция backtest_results.js на StateManager

**Дата:** 2026-02-26
**Статус:** ⏳ В работе
**Оценка:** 3 часа

---

## Цель

Заменить глобальные переменные в `backtest_results.js` на StateManager:
- `currentBacktest` → `backtestResults.current`
- `allResults` → `backtestResults.all`
- `selectedForCompare` → `backtestResults.compare.selected`
- `compareMode` → `backtestResults.compare.mode`
- `tradesCurrentPage` → `backtestResults.tradesTable.currentPage`
- `tradesCachedRows` → `backtestResults.tradesTable.cachedRows`
- `tradesSortKey/Asc` → `backtestResults.tradesTable.sort`
- Chart instances → `backtestResults.charts.*`

---

## Структура state

```javascript
store.merge('backtestResults', {
  current: null,
  all: [],
  compare: {
    selected: [],
    mode: false
  },
  tradesTable: {
    currentPage: 0,
    pageSize: 25,
    cachedRows: [],
    sort: {
      key: null,
      asc: true
    },
    selectedForDelete: []
  },
  charts: {
    equity: null,
    tvEquity: null,
    drawdown: null,
    returns: null,
    monthly: null,
    tradeDistribution: null,
    winLossDonut: null,
    waterfall: null,
    benchmarking: null,
    price: {
      chart: null,
      candleSeries: null,
      markers: [],
      tradeLineSeries: []
    }
  },
  priceChart: {
    cachedCandles: [],
    pending: false,
    generation: 0,
    resizeObserver: null
  },
  deletedIds: [],
  ws: {
    connected: false,
    reconnectAttempts: 0
  }
});
```

---

## Изменения

### 1. Импорт StateManager

**До:**
```javascript
let currentBacktest = null;
let allResults = [];
let selectedForCompare = [];
let compareMode = false;
```

**После:**
```javascript
import { getStore } from '../core/StateManager.js';
import { bindToState, initState } from '../core/state-helpers.js';

const store = getStore();

// Initialize state
function initializeBacktestResultsState() {
  store.merge('backtestResults', {
    current: null,
    all: [],
    compare: {
      selected: [],
      mode: false
    },
    // ... остальная структура
  });
}
```

### 2. Геттеры и сеттеры

**До:**
```javascript
function loadBacktest(id) {
  currentBacktest = fetchData(id);
  updateUI();
}
```

**После:**
```javascript
function getCurrentBacktest() {
  return store.get('backtestResults.current');
}

function setCurrentBacktest(backtest) {
  store.set('backtestResults.current', backtest);
}

function loadBacktest(id) {
  const backtest = fetchData(id);
  setCurrentBacktest(backtest);
  // UI обновится через subscribe
}
```

### 3. Подписка на изменения

```javascript
// Подписка на текущий бэктест
store.subscribe('backtestResults.current', (backtest) => {
  if (backtest) {
    renderBacktestDetails(backtest);
    renderTradesTable();
    initCharts();
  }
});

// Подписка на compare mode
store.subscribe('backtestResults.compare.mode', (mode) => {
  toggleCompareModeUI(mode);
});

// Подписка на страницу таблицы
store.subscribe('backtestResults.tradesTable.currentPage', (page) => {
  renderTradesPage(page);
});
```

### 4. Charts management

**До:**
```javascript
let equityChart = null;
let drawdownChart = null;

function initEquityChart(data) {
  equityChart = new Chart(ctx, { ... });
}
```

**После:**
```javascript
function getCharts() {
  return store.get('backtestResults.charts') || {};
}

function setChart(name, instance) {
  store.set(`backtestResults.charts.${name}`, instance);
}

function initEquityChart(data) {
  const chart = new Chart(ctx, { ... });
  setChart('equity', chart);
}

function cleanupCharts() {
  const charts = getCharts();
  for (const [name, chart] of Object.entries(charts)) {
    if (chart && typeof chart.destroy === 'function') {
      chart.destroy();
    }
  }
  store.set('backtestResults.charts', {});
}
```

### 5. Trades table pagination

**До:**
```javascript
let tradesCurrentPage = 0;
let tradesCachedRows = [];

function renderTradesTable() {
  const start = tradesCurrentPage * TRADES_PAGE_SIZE;
  const end = start + TRADES_PAGE_SIZE;
  const rows = tradesCachedRows.slice(start, end);
  // ...
}
```

**После:**
```javascript
function getTradesTableState() {
  return store.get('backtestResults.tradesTable') || {
    currentPage: 0,
    cachedRows: [],
    sort: { key: null, asc: true }
  };
}

function setTradesTableState(updates) {
  store.merge('backtestResults.tradesTable', updates);
}

function renderTradesTable() {
  const state = getTradesTableState();
  const start = state.currentPage * state.pageSize;
  const end = start + state.pageSize;
  const rows = state.cachedRows.slice(start, end);
  // ...
}

function goToPage(page) {
  setTradesTableState({ currentPage: page });
  // renderTradesPage вызывается автоматически через subscribe
}
```

---

## План миграции

### Этап 1: Инициализация state (30 мин)

- [ ] Создать `initializeBacktestResultsState()`
- [ ] Определить начальную структуру state
- [ ] Создать геттеры/сеттеры

### Этап 2: Миграция глобальных переменных (1 час)

- [ ] `currentBacktest` → `backtestResults.current`
- [ ] `allResults` → `backtestResults.all`
- [ ] `selectedForCompare/compareMode` → `backtestResults.compare.*`
- [ ] `tradesCurrentPage/cachedRows` → `backtestResults.tradesTable.*`
- [ ] `selectedForDelete` → `backtestResults.tradesTable.selectedForDelete`
- [ ] `recentlyDeletedIds` → `backtestResults.deletedIds`

### Этап 3: Миграция Chart instances (1 час)

- [ ] `equityChart` → `backtestResults.charts.equity`
- [ ] `_brTVEquityChart` → `backtestResults.charts.tvEquity`
- [ ] `drawdownChart` → `backtestResults.charts.drawdown`
- [ ] `returnsChart` → `backtestResults.charts.returns`
- [ ] `monthlyChart` → `backtestResults.charts.monthly`
- [ ] `tradeDistributionChart` → `backtestResults.charts.tradeDistribution`
- [ ] `winLossDonutChart` → `backtestResults.charts.winLossDonut`
- [ ] `waterfallChart` → `backtestResults.charts.waterfall`
- [ ] `benchmarkingChart` → `backtestResults.charts.benchmarking`
- [ ] `btPriceChart` и связанные → `backtestResults.charts.price.*`

### Этап 4: Подписки и реактивность (30 мин)

- [ ] Подписка на `backtestResults.current`
- [ ] Подписка на `backtestResults.compare.mode`
- [ ] Подписка на `backtestResults.tradesTable.currentPage`
- [ ] Подписка на `backtestResults.tradesTable.sort`

### Этап 5: Тесты (30 мин)

- [ ] Тест загрузки бэктеста
- [ ] Тест compare mode
- [ ] Тест pagination
- [ ] Тест chart cleanup

---

## Глобальные переменные для миграции

| Переменная | Path в StateManager | Тип | Примечание |
|------------|---------------------|-----|------------|
| `currentBacktest` | `backtestResults.current` | Object/null | Текущий бэктест |
| `allResults` | `backtestResults.all` | Array | Все результаты |
| `selectedForCompare` | `backtestResults.compare.selected` | Array | Выбранные для сравнения |
| `compareMode` | `backtestResults.compare.mode` | Boolean | Режим сравнения |
| `tradesCurrentPage` | `backtestResults.tradesTable.currentPage` | Number | Страница таблицы |
| `tradesCachedRows` | `backtestResults.tradesTable.cachedRows` | Array | Кэш строк таблицы |
| `tradesSortKey` | `backtestResults.tradesTable.sort.key` | String/null | Ключ сортировки |
| `tradesSortAsc` | `backtestResults.tradesTable.sort.asc` | Boolean | Направление сортировки |
| `selectedForDelete` | `backtestResults.tradesTable.selectedForDelete` | Set/Array | Выбранные для удаления |
| `recentlyDeletedIds` | `backtestResults.deletedIds` | Array | Недавно удалённые ID |
| `equityChart` | `backtestResults.charts.equity` | Chart.js/null | График equity |
| `_brTVEquityChart` | `backtestResults.charts.tvEquity` | TVChart/null | TradingView equity |
| `drawdownChart` | `backtestResults.charts.drawdown` | Chart.js/null | График просадки |
| `returnsChart` | `backtestResults.charts.returns` | Chart.js/null | График доходности |
| `monthlyChart` | `backtestResults.charts.monthly` | Chart.js/null | Месячный график |
| `tradeDistributionChart` | `backtestResults.charts.tradeDistribution` | Chart.js/null | Распределение сделок |
| `winLossDonutChart` | `backtestResults.charts.winLossDonut` | Chart.js/null | Win/Loss donut |
| `waterfallChart` | `backtestResults.charts.waterfall` | Chart.js/null | Waterfall chart |
| `benchmarkingChart` | `backtestResults.charts.benchmarking` | Chart.js/null | Benchmarking |
| `btPriceChart` | `backtestResults.charts.price.chart` | Lightweight/null | Candlestick chart |
| `btCandleSeries` | `backtestResults.charts.price.candleSeries` | Series/null | Candle series |
| `btPriceChartMarkers` | `backtestResults.charts.price.markers` | Array | Маркеры |
| `btTradeLineSeries` | `backtestResults.charts.price.tradeLineSeries` | Array | Trade lines |
| `_btCachedCandles` | `backtestResults.priceChart.cachedCandles` | Array | Кэш свечей |
| `btPriceChartPending` | `backtestResults.priceChart.pending` | Boolean | Ожидание chart |
| `_priceChartGeneration` | `backtestResults.priceChart.generation` | Number | Generation counter |
| `_priceChartResizeObserver` | `backtestResults.priceChart.resizeObserver` | ResizeObserver/null | Resize observer |

---

## Критерии приёмки

- [ ] Все глобальные переменные заменены на StateManager
- [ ] Подписки работают корректно
- [ ] Chart cleanup работает при навигации
- [ ] Pagination работает через state
- [ ] Compare mode работает через state
- [ ] Тесты проходят (>80% coverage)

---

## Проблемы и решения

### Проблема 1: Chart.js instances

**Решение:** Хранить instances в state, но не сериализовать. При загрузке страницы инициализировать заново.

### Проблема 2: Set для selectedForDelete

**Решение:** StateManager не сериализует Set → использовать Array с методами `includes`, `add`, `delete`.

### Проблема 3: ResizeObserver

**Решение:** Хранить reference в state, но отключать персистентность для этого пути.

---

## Следующий шаг

[Шаг 2.3: Миграция strategy_builder.js](./step-2-3-strategy-builder.md)

---

*План создан: 2026-02-26*
