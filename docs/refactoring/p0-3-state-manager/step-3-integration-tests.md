# Шаг 3: Интеграционные тесты StateManager

**Дата:** 2026-02-26
**Статус:** ⏳ Ожидает
**Оценка:** 3 часа

---

## Цель

Создать комплексные тесты для проверки:
- Синхронизации state между страницами
- Персистентности (localStorage)
- Reactivity (подписки и обновления)
- E2E сценариев использования

---

## Структура тестов

```
tests/frontend/integration/
├── state-sync.test.js          # Синхронизация между страницами
├── state-persistence.test.js   # Персистентность
├── state-reactivity.test.js    # Реактивность
└── state-e2e.test.js           # E2E сценарии
```

---

## Тест 1: Синхронизация между страницами

**Файл:** `tests/frontend/integration/state-sync.test.js`

```javascript
/**
 * Integration Tests: State Synchronization
 *
 * Tests for cross-page state synchronization
 */

import { getStore } from '../../../frontend/js/core/StateManager.js';

describe('State Synchronization', () => {
  let store;

  beforeEach(() => {
    // Reset store before each test
    store = getStore();
    if (!store) {
      store = new StateManager({
        market: { selectedSymbol: 'BTCUSDT', selectedTimeframe: '1h' },
        dashboard: { currentPeriod: '24h' },
        backtestResults: { current: null, all: [] },
        strategyBuilder: {
          graph: { nodes: [], connections: [] },
          blocks: { selected: [] }
        }
      });
    }
  });

  describe('Market State', () => {
    it('should sync selectedSymbol across pages', async () => {
      // Simulate dashboard page
      store.set('market.selectedSymbol', 'ETHUSDT');

      // Simulate backtest-results page loading
      const symbolFromBacktest = store.get('market.selectedSymbol');

      expect(symbolFromBacktest).toBe('ETHUSDT');
    });

    it('should sync timeframe across pages', async () => {
      store.set('market.selectedTimeframe', '4h');

      const timeframe = store.get('market.selectedTimeframe');

      expect(timeframe).toBe('4h');
    });

    it('should notify all pages when market state changes', (done) => {
      const callback = jest.fn();
      store.subscribe('market.selectedSymbol', callback);

      store.set('market.selectedSymbol', 'SOLUSDT');

      setTimeout(() => {
        expect(callback).toHaveBeenCalledWith('SOLUSDT', 'market.selectedSymbol', 'BTCUSDT');
        done();
      }, 10);
    });
  });

  describe('Dashboard State', () => {
    it('should persist currentPeriod', async () => {
      store.set('dashboard.currentPeriod', '7d');

      const period = store.get('dashboard.currentPeriod');

      expect(period).toBe('7d');
    });

    it('should sync period change across pages', async () => {
      store.set('dashboard.currentPeriod', '30d');

      const periodFromOtherPage = store.get('dashboard.currentPeriod');

      expect(periodFromOtherPage).toBe('30d');
    });
  });

  describe('Backtest Results State', () => {
    it('should sync current backtest', async () => {
      const mockBacktest = {
        id: 'test-123',
        symbol: 'BTCUSDT',
        sharpe_ratio: 1.5
      };

      store.set('backtestResults.current', mockBacktest);

      const current = store.get('backtestResults.current');

      expect(current).toEqual(mockBacktest);
    });

    it('should sync compare mode', async () => {
      store.set('backtestResults.compare.mode', true);
      store.set('backtestResults.compare.selected', ['bt-1', 'bt-2']);

      const compareMode = store.get('backtestResults.compare.mode');
      const selected = store.get('backtestResults.compare.selected');

      expect(compareMode).toBe(true);
      expect(selected).toEqual(['bt-1', 'bt-2']);
    });

    it('should sync trades table pagination', async () => {
      store.set('backtestResults.tradesTable.currentPage', 5);
      store.set('backtestResults.tradesTable.sort', { key: 'pnl', asc: false });

      const page = store.get('backtestResults.tradesTable.currentPage');
      const sort = store.get('backtestResults.tradesTable.sort');

      expect(page).toBe(5);
      expect(sort).toEqual({ key: 'pnl', asc: false });
    });
  });

  describe('Strategy Builder State', () => {
    it('should sync graph nodes', async () => {
      const mockNodes = [
        { id: '1', type: 'indicator', name: 'RSI' },
        { id: '2', type: 'entry', name: 'RSI Entry' }
      ];

      store.set('strategyBuilder.graph.nodes', mockNodes);

      const nodes = store.get('strategyBuilder.graph.nodes');

      expect(nodes).toEqual(mockNodes);
    });

    it('should sync selected blocks', async () => {
      store.set('strategyBuilder.blocks.selected', ['1', '2']);

      const selected = store.get('strategyBuilder.blocks.selected');

      expect(selected).toEqual(['1', '2']);
    });

    it('should sync viewport state', async () => {
      store.set('strategyBuilder.viewport.zoomLevel', 1.5);
      store.set('strategyBuilder.viewport.panOffset', { x: 100, y: 200 });

      const zoom = store.get('strategyBuilder.viewport.zoomLevel');
      const pan = store.get('strategyBuilder.viewport.panOffset');

      expect(zoom).toBe(1.5);
      expect(pan).toEqual({ x: 100, y: 200 });
    });

    it('should sync undo/redo stacks', async () => {
      const undoAction = { type: 'ADD_NODE', node: { id: '1' } };

      store.set('strategyBuilder.history.undoStack', [undoAction]);

      const undoStack = store.get('strategyBuilder.history.undoStack');

      expect(undoStack).toEqual([undoAction]);
    });
  });
});
```

---

## Тест 2: Персистентность

**Файл:** `tests/frontend/integration/state-persistence.test.js`

```javascript
/**
 * Integration Tests: State Persistence
 *
 * Tests for localStorage persistence
 */

import { StateManager } from '../../../frontend/js/core/StateManager.js';

describe('State Persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should persist state to localStorage', () => {
    const store = new StateManager(
      { theme: 'dark', language: 'en' },
      { persist: true, persistKey: 'test_state' }
    );

    store.set('theme', 'light');

    const saved = localStorage.getItem('test_state');
    const parsed = JSON.parse(saved);

    expect(parsed.theme).toBe('light');
    expect(parsed.language).toBe('en');
  });

  it('should restore state from localStorage on init', () => {
    // Pre-populate localStorage
    localStorage.setItem('test_state', JSON.stringify({
      theme: 'dark',
      language: 'es'
    }));

    const store = new StateManager(
      { theme: 'light', language: 'en' },
      { persist: true, persistKey: 'test_state' }
    );

    const theme = store.get('theme');
    const language = store.get('language');

    expect(theme).toBe('dark');
    expect(language).toBe('es');
  });

  it('should persist only specified paths', () => {
    const store = new StateManager(
      {
        ui: { theme: 'dark', sidebar: true },
        user: { name: 'John', token: 'secret' }
      },
      {
        persist: true,
        persistKey: 'test_state',
        persistPaths: ['ui']
      }
    );

    store.set('ui.theme', 'light');
    store.set('user.name', 'Jane');

    const saved = JSON.parse(localStorage.getItem('test_state'));

    expect(saved.ui.theme).toBe('light');
    expect(saved.ui.sidebar).toBe(true);
    expect(saved.user).toBeUndefined();
  });

  it('should handle localStorage quota exceeded', () => {
    const store = new StateManager(
      { data: 'test' },
      { persist: true, persistKey: 'test_state' }
    );

    // Mock localStorage to throw error
    const originalSetItem = localStorage.setItem;
    localStorage.setItem = () => {
      throw new Error('QuotaExceededError');
    };

    // Should not throw, just warn
    expect(() => store.set('data', 'large data')).not.toThrow();

    // Restore
    localStorage.setItem = originalSetItem;
  });

  it('should persist nested objects', () => {
    const store = new StateManager(
      {
        backtestResults: {
          current: null,
          tradesTable: { currentPage: 0, sort: { key: null, asc: true } }
        }
      },
      { persist: true, persistKey: 'test_state' }
    );

    store.set('backtestResults.tradesTable.currentPage', 5);
    store.set('backtestResults.tradesTable.sort', { key: 'pnl', asc: false });

    const saved = JSON.parse(localStorage.getItem('test_state'));

    expect(saved.backtestResults.tradesTable.currentPage).toBe(5);
    expect(saved.backtestResults.tradesTable.sort).toEqual({ key: 'pnl', asc: false });
  });

  it('should persist dashboard state', () => {
    const store = new StateManager(
      {
        dashboard: {
          currentPeriod: '24h',
          calendar: { year: 2026, month: 1 },
          watchlist: ['BTCUSDT', 'ETHUSDT']
        }
      },
      { persist: true, persistKey: 'test_state' }
    );

    store.set('dashboard.currentPeriod', '7d');
    store.set('dashboard.calendar', { year: 2025, month: 11 });

    const saved = JSON.parse(localStorage.getItem('test_state'));

    expect(saved.dashboard.currentPeriod).toBe('7d');
    expect(saved.dashboard.calendar).toEqual({ year: 2025, month: 11 });
  });
});
```

---

## Тест 3: Реактивность

**Файл:** `tests/frontend/integration/state-reactivity.test.js`

```javascript
/**
 * Integration Tests: State Reactivity
 *
 * Tests for subscriptions and reactive updates
 */

import { StateManager } from '../../../frontend/js/core/StateManager.js';

describe('State Reactivity', () => {
  let store;

  beforeEach(() => {
    store = new StateManager({
      value: 1,
      nested: { a: { b: { c: 1 } } },
      array: [1, 2, 3]
    });
  });

  it('should notify subscriber on value change', (done) => {
    store.subscribe('value', (newValue, path, prevValue) => {
      expect(newValue).toBe(2);
      expect(path).toBe('value');
      expect(prevValue).toBe(1);
      done();
    });

    store.set('value', 2);
  });

  it('should notify subscriber on nested value change', (done) => {
    store.subscribe('nested.a.b.c', (newValue) => {
      expect(newValue).toBe(2);
      done();
    });

    store.set('nested.a.b.c', 2);
  });

  it('should notify parent path subscribers', (done) => {
    store.subscribe('nested.a', (newValue) => {
      expect(newValue.b.c).toBe(2);
      done();
    });

    store.set('nested.a.b.c', 2);
  });

  it('should notify wildcard subscribers', (done) => {
    store.subscribe('*', (state, path) => {
      expect(path).toBe('value');
      expect(state.value).toBe(2);
      done();
    });

    store.set('value', 2);
  });

  it('should unsubscribe correctly', () => {
    const callback = jest.fn();
    const unsubscribe = store.subscribe('value', callback);

    store.set('value', 2);
    unsubscribe();
    store.set('value', 3);

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith(2, 'value', 1);
  });

  it('should batch updates and notify once', () => {
    const callback = jest.fn();
    store.subscribe('nested', callback);

    store.batch({
      'nested.a.b.c': 2,
      'nested.a.b.d': 3,
      'nested.a.e': 4
    });

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('should compute derived values', (done) => {
    const compute = jest.fn((a, b) => a + b);
    const callback = jest.fn((result) => {
      if (callback.mock.calls.length === 2) {
        expect(compute).toHaveBeenCalledWith(2, 3);
        expect(result).toBe(5);
        done();
      }
    });

    store.computed(['a', 'b'], compute, callback);

    store.set('a', 2);
    store.set('b', 3);
  });

  it('should handle array mutations', (done) => {
    store.subscribe('array', (newValue) => {
      expect(newValue).toEqual([1, 2, 3, 4]);
      done();
    });

    store.set('array', [1, 2, 3, 4]);
  });

  it('should not notify on silent updates', () => {
    const callback = jest.fn();
    store.subscribe('value', callback);

    store.set('value', 2, { silent: true });

    expect(callback).not.toHaveBeenCalled();
  });

  it('should handle middleware', () => {
    const middleware = jest.fn((action) => {
      if (action.type === 'SET') {
        return action.value * 2;
      }
    });

    store.use(middleware);
    store.set('value', 5);

    expect(store.get('value')).toBe(10);
  });
});
```

---

## Тест 4: E2E сценарии

**Файл:** `tests/frontend/integration/state-e2e.test.js`

```javascript
/**
 * Integration Tests: E2E Scenarios
 *
 * Real-world usage scenarios
 */

import { getStore } from '../../../frontend/js/core/StateManager.js';

describe('E2E Scenarios', () => {
  let store;

  beforeEach(() => {
    localStorage.clear();
    store = getStore();
    if (!store) {
      store = new StateManager({
        market: { selectedSymbol: 'BTCUSDT', selectedTimeframe: '1h' },
        dashboard: { currentPeriod: '24h' },
        backtestResults: {
          current: null,
          all: [],
          compare: { selected: [], mode: false },
          tradesTable: { currentPage: 0, cachedRows: [], sort: { key: null, asc: true } }
        },
        strategyBuilder: {
          graph: { nodes: [], connections: [] },
          blocks: { selected: [] },
          viewport: { zoomLevel: 1, panOffset: { x: 0, y: 0 } },
          history: { undoStack: [], redoStack: [] }
        }
      }, { persist: true });
    }
  });

  it('should handle complete backtest workflow', async () => {
    // 1. User loads backtest results page
    const mockBacktest = {
      id: 'bt-123',
      symbol: 'BTCUSDT',
      timeframe: '1h',
      sharpe_ratio: 1.5,
      total_return: 15.3,
      trades: [{ id: 't1', pnl: 100 }, { id: 't2', pnl: -50 }]
    };

    store.set('backtestResults.current', mockBacktest);

    // 2. User navigates to another page and back
    const currentBacktest = store.get('backtestResults.current');
    expect(currentBacktest).toEqual(mockBacktest);

    // 3. User enables compare mode
    store.set('backtestResults.compare.mode', true);
    store.set('backtestResults.compare.selected', ['bt-123', 'bt-456']);

    // 4. User changes trades table page
    store.set('backtestResults.tradesTable.currentPage', 2);
    store.set('backtestResults.tradesTable.sort', { key: 'pnl', asc: false });

    // 5. State persists after reload
    const persistedState = JSON.parse(localStorage.getItem('bybit_strategy_tester_state'));
    expect(persistedState.backtestResults.current.id).toBe('bt-123');
    expect(persistedState.backtestResults.compare.mode).toBe(true);
    expect(persistedState.backtestResults.tradesTable.currentPage).toBe(2);
  });

  it('should handle strategy builder workflow', async () => {
    // 1. User adds blocks to graph
    const nodes = [
      { id: '1', type: 'indicator', name: 'RSI', x: 100, y: 100 },
      { id: '2', type: 'entry', name: 'RSI Entry', x: 300, y: 100 }
    ];

    store.set('strategyBuilder.graph.nodes', nodes);

    // 2. User connects blocks
    const connections = [
      { id: 'c1', from: '1', to: '2', type: 'signal' }
    ];

    store.set('strategyBuilder.graph.connections', connections);

    // 3. User selects blocks
    store.set('strategyBuilder.blocks.selected', ['1', '2']);

    // 4. User zooms and pans
    store.set('strategyBuilder.viewport.zoomLevel', 1.5);
    store.set('strategyBuilder.viewport.panOffset', { x: 50, y: 100 });

    // 5. User performs undo
    const lastAction = { type: 'ADD_NODE', node: nodes[1] };
    store.set('strategyBuilder.history.undoStack', [lastAction]);

    const undoStack = store.get('strategyBuilder.history.undoStack');
    expect(undoStack).toEqual([lastAction]);

    // 6. State persists
    const persistedState = JSON.parse(localStorage.getItem('bybit_strategy_tester_state'));
    expect(persistedState.strategyBuilder.graph.nodes.length).toBe(2);
    expect(persistedState.strategyBuilder.viewport.zoomLevel).toBe(1.5);
  });

  it('should handle market state sync across pages', async () => {
    // 1. User changes symbol on dashboard
    store.set('market.selectedSymbol', 'ETHUSDT');
    store.set('market.selectedTimeframe', '4h');

    // 2. User navigates to backtest results
    const symbol = store.get('market.selectedSymbol');
    const timeframe = store.get('market.selectedTimeframe');

    expect(symbol).toBe('ETHUSDT');
    expect(timeframe).toBe('4h');

    // 3. User navigates to strategy builder
    const builderSymbol = store.get('market.selectedSymbol');
    expect(builderSymbol).toBe('ETHUSDT');
  });

  it('should handle dashboard period selection', async () => {
    // 1. User changes period
    store.set('dashboard.currentPeriod', '7d');

    // 2. State updates
    const period = store.get('dashboard.currentPeriod');
    expect(period).toBe('7d');

    // 3. State persists
    const persisted = JSON.parse(localStorage.getItem('bybit_strategy_tester_state'));
    expect(persisted.dashboard.currentPeriod).toBe('7d');
  });
});
```

---

## Запуск тестов

```bash
# Запуск всех интеграционных тестов
npm run test -- tests/frontend/integration/

# Запуск конкретного теста
npm run test -- tests/frontend/integration/state-sync.test.js

# Запуск с покрытием
npm run test-cov -- tests/frontend/integration/

# Запуск в watch mode
npm run test:watch -- tests/frontend/integration/
```

---

## Критерии приёмки

- [ ] Все тесты проходят
- [ ] Coverage >80%
- [ ] Тесты изолированы и не зависят друг от друга
- [ ] Тесты воспроизводят реальные сценарии использования
- [ ] Тесты персистентности работают с localStorage
- [ ] Тесты реактивности покрывают все типы подписок

---

## Следующий шаг

[Шаг 4: Финальная документация](./step-4-final-documentation.md)

---

*План создан: 2026-02-26*
