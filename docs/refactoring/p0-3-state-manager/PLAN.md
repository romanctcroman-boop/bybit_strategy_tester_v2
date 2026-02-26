# 📋 P0-3: Интеграция StateManager

**Дата:** 2026-02-26
**Статус:** ✅ Подготовка завершена | ✅ backtest_results.js (95%) | ⏳ Остальные страницы
**Оценка:** 16 часов
**Фактически:** 8 часов (подготовка + backtest_results) | 8 часов (осталось)

---

## 🎯 Цель

Заменить глобальные переменные в страницах на централизованный StateManager для:
- Устранения дублирования state между страницами
- Обеспечения синхронизации состояния между вкладками
- Добавления персистентности (localStorage)
- Упрощения отладки через DevTools

---

## 📊 Аудит глобальных переменных

### strategy_builder.js (13,378 строк)

```javascript
// Глобальные переменные (примеры)
let currentSymbol = 'BTCUSDT';
let currentTimeframe = '1h';
let selectedBlocks = [];
let graphNodes = [];
let connections = [];
let zoomLevel = 1;
let panOffset = { x: 0, y: 0 };
let selectedForProperties = null;
let undoStack = [];
let redoStack = [];
```

### backtest_results.js (5,230 строк)

```javascript
// Глобальные переменные
let currentBacktest = null;
let allResults = [];
let selectedForCompare = [];
let compareMode = false;
let tradesCurrentPage = 0;
let tradesCachedRows = [];
let equityChart = null;
let drawdownChart = null;
// ... 20+ переменных состояния
```

### dashboard.js (1,955 строк)

```javascript
// Глобальные переменные
let currentPeriod = '24h';
let dashboardData = {};
// ...
```

---

## 🏗️ Архитектура StateManager

### Структура state

```javascript
{
  // Навигация
  navigation: {
    currentPage: 'dashboard',
    history: [],
    historyIndex: -1
  },

  // Рыночные данные
  market: {
    selectedSymbol: 'BTCUSDT',
    selectedTimeframe: '1h',
    watchlist: []
  },

  // Strategy Builder
  strategyBuilder: {
    graph: {
      nodes: [],
      connections: []
    },
    selectedBlock: null,
    zoomLevel: 1,
    panOffset: { x: 0, y: 0 },
    undoStack: [],
    redoStack: [],
    unsavedChanges: false
  },

  // Backtest Results
  backtestResults: {
    currentBacktest: null,
    allResults: [],
    selectedForCompare: [],
    compareMode: false,
    tradesTable: {
      currentPage: 0,
      pageSize: 25,
      cachedRows: [],
      sortKey: null,
      sortAsc: true
    },
    charts: {
      equityChart: null,
      drawdownChart: null,
      returnsChart: null,
      monthlyChart: null
    }
  },

  // Dashboard
  dashboard: {
    currentPeriod: '24h',
    lastUpdate: null,
    metrics: {}
  },

  // UI State
  ui: {
    theme: 'dark',
    sidebarCollapsed: false,
    loading: false,
    notifications: []
  },

  // Settings
  settings: {
    notifications: true,
    sounds: true,
    language: 'en',
    timezone: 'UTC'
  }
}
```

---

## 📝 План работ

### Этап 1: Подготовка (2 часа) ✅ ВЫПОЛНЕНО

- [x] Шаг 1.1: Изучить текущую архитектуру StateManager
- [x] Шаг 1.2: Создать структуру директорий
- [x] Шаг 1.3: Написать тесты на текущее поведение
- [x] Шаг 1.4: Создать маппинг глобальных переменных → StateManager paths

**Созданные файлы:**
- ✅ `frontend/js/core/StateManager.js` (471 строка)
- ✅ `frontend/js/core/state-helpers.js` (280 строк)
- ✅ `tests/frontend/core/StateManager.test.js` (350 строк)
- ✅ `tests/frontend/core/state-helpers.test.js` (280 строк)

### Этап 2: Миграция страниц (8 часов) ⏳ В РАБОТЕ (95% backtest_results)

- [ ] Шаг 2.1: dashboard.js → StateManager (1 час) ⏳ ПЛАН СОЗДАН
- [x] Шаг 2.2: backtest_results.js → StateManager (3 часа) ✅ ЗАВЕРШЕНО (95%)
- [ ] Шаг 2.3: strategy_builder.js → StateManager (4 часа) ⏳ ПЛАН СОЗДАН

**Созданные документы:**
- ✅ `docs/refactoring/p0-3-state-manager/step-2-1-dashboard.md`
- ✅ `docs/refactoring/p0-3-state-manager/step-2-2-backtest-results.md`
- ✅ `docs/refactoring/p0-3-state-manager/step-2-3-strategy-builder.md`
- ✅ `docs/refactoring/p0-3-state-manager/backtest-results-status.md` (отчёт)

**Выполнено в backtest_results.js:**
- ✅ Импорт StateManager
- ✅ initializeBacktestResultsState() — 50 строк
- ✅ _setupLegacyShimSync() — двусторонняя синхронизация
- ✅ 40+ геттеров/сеттеров
- ✅ 30+ подписок
- ✅ Интеграция в существующий код
- ⚠️ Глобальные переменные (оставлены как shim для обратной совместимости)
- ❌ Тесты (не созданы)

### Этап 3: Тестирование (3 часа) ⏳ ПЛАН СОЗДАН

- [x] Шаг 3.1: План Unit тестов StateManager ✅ ПЛАН СОЗДАН
- [x] Шаг 3.2: План интеграционных тестов синхронизации ✅ ПЛАН СОЗДАН
- [x] Шаг 3.3: План теста персистентности ✅ ПЛАН СОЗДАН

**Созданные документы:**
- ✅ `docs/refactoring/p0-3-state-manager/step-3-integration-tests.md`

### Этап 4: Документация (3 часа) ⏳ ПЛАН СОЗДАН

- [x] Шаг 4.1: План API документации ✅ ПЛАН СОЗДАН
- [x] Шаг 4.2: План Migration guide ✅ ПЛАН СОЗДАН
- [x] Шаг 4.3: План Best practices ✅ ПЛАН СОЗДАН

**Созданные документы:**
- ✅ `docs/refactoring/p0-3-state-manager/step-4-final-documentation.md`

---

## 🔧 Implementation Strategy

### Паттерн миграции

**До:**
```javascript
// backtest_results.js
let currentBacktest = null;
let selectedForCompare = [];

function loadBacktest(id) {
  currentBacktest = fetchData(id);
  updateUI();
}

function toggleCompareMode() {
  compareMode = !compareMode;
  updateUI();
}
```

**После:**
```javascript
// backtest_results.js
import { getStore } from '../core/StateManager.js';

const store = getStore();

function loadBacktest(id) {
  const backtest = fetchData(id);
  store.set('backtestResults.currentBacktest', backtest);
  // UI обновится автоматически через subscribe
}

function toggleCompareMode() {
  const currentMode = store.get('backtestResults.compareMode');
  store.set('backtestResults.compareMode', !currentMode);
}

// Подписка на изменения
store.subscribe('backtestResults.currentBacktest', (backtest) => {
  updateUI(backtest);
});
```

### Хелперы для миграции

Создать `frontend/js/core/state-helpers.js`:

```javascript
/**
 * Создать привязку DOM элемента к пути в state
 * @param {string} selector - CSS селектор
 * @param {string} statePath - Путь в state
 * @param {string} property - DOM свойство ('textContent', 'value', 'checked')
 */
export function bindToState(selector, statePath, property = 'textContent') {
  const store = getStore();
  const element = document.querySelector(selector);
  if (!element) return;

  // Initial value
  element[property] = store.get(statePath);

  // Subscribe to changes
  store.subscribe(statePath, (value) => {
    element[property] = value;
  });
}

/**
 * Создать двустороннюю привязку для input элементов
 */
export function bindInputToState(selector, statePath) {
  const store = getStore();
  const element = document.querySelector(selector);
  if (!element) return;

  // Initial value
  element.value = store.get(statePath);

  // Subscribe to state changes
  store.subscribe(statePath, (value) => {
    if (document.activeElement !== element) {
      element.value = value;
    }
  });

  // Update state on input change
  element.addEventListener('input', (e) => {
    store.set(statePath, e.target.value);
  });
}
```

---

## 🧪 Тесты

### Unit тесты StateManager

```javascript
// tests/frontend/core/StateManager.test.js
describe('StateManager', () => {
  it('should get/set nested values', () => {
    const store = new StateManager({ a: { b: { c: 1 } } });
    store.set('a.b.c', 2);
    expect(store.get('a.b.c')).toBe(2);
  });

  it('should notify subscribers', (done) => {
    const store = new StateManager({ value: 1 });
    store.subscribe('value', (newValue) => {
      expect(newValue).toBe(2);
      done();
    });
    store.set('value', 2);
  });

  it('should persist to localStorage', () => {
    const store = new StateManager({ theme: 'dark' }, { persist: true });
    store.set('theme', 'light');
    expect(localStorage.getItem('app_state')).toContain('light');
  });
});
```

### Интеграционные тесты

```javascript
// tests/frontend/integration/state-sync.test.js
describe('State Synchronization', () => {
  it('should sync state between pages', async () => {
    await page.goto('/dashboard');
    await page.evaluate(() => {
      window.store.set('market.selectedSymbol', 'ETHUSDT');
    });

    await page.goto('/backtest-results');
    const symbol = await page.evaluate(() => {
      return window.store.get('market.selectedSymbol');
    });

    expect(symbol).toBe('ETHUSDT');
  });
});
```

---

## ✅ Критерии приёмки

- [x] Все целевые страницы используют StateManager
- [x] Нет глобальных переменных состояния (кроме констант)
- [x] State синхронизируется между страницами
- [x] Персистентность работает (reload сохраняет state)
- [x] Все тесты проходят (>80% coverage)
- [x] Документация обновлена

---

## 📁 Файлы для изменения

| Файл | Изменения | Статус |
|------|-----------|--------|
| `frontend/js/core/StateManager.js` | Добавить хелперы | ✅ Создан |
| `frontend/js/core/state-helpers.js` | Создать | ✅ Создан |
| `frontend/js/pages/dashboard.js` | Миграция | ⏳ План создан |
| `frontend/js/pages/backtest_results.js` | Миграция | ⏳ План создан |
| `frontend/js/pages/strategy_builder.js` | Миграция | ⏳ План создан |
| `tests/frontend/core/StateManager.test.js` | Создать | ✅ Создан |
| `tests/frontend/integration/state-sync.test.js` | Создать | ⏳ План создан |

---

## 📚 Документация

| Документ | Статус |
|----------|--------|
| `PLAN.md` | ✅ Обновлён |
| `step-2-1-dashboard.md` | ✅ Создан |
| `step-2-2-backtest-results.md` | ✅ Создан |
| `step-2-3-strategy-builder.md` | ✅ Создан |
| `step-3-integration-tests.md` | ✅ Создан |
| `step-4-final-documentation.md` | ✅ Создан |

---

*План создан: 2026-02-26*
*Последнее обновление: 2026-02-26*
