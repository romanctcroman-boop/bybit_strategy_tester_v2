# Шаг 2.1: Миграция dashboard.js на StateManager

**Дата:** 2026-02-26
**Статус:** ⏳ В работе

## Цель

Заменить глобальные переменные в `dashboard.js` на StateManager:
- `currentPeriod` → `dashboard.currentPeriod`
- `dashboardData` → `dashboard.metrics`
- `lastUpdate` → `dashboard.lastUpdate`
- Chart instances → `dashboard.charts.*`
- WebSocket state → `dashboard.ws`

## Изменения

### 1. Импорт StateManager

```javascript
// До
let currentPeriod = '24h';

// После
import { getStore } from '../core/StateManager.js';
import { bindToState, bindInputToState } from '../core/state-helpers.js';

const store = getStore();
```

### 2. Инициализация state

```javascript
// При загрузке страницы
function initializeDashboardState() {
  store.merge('dashboard', {
    currentPeriod: '24h',
    metrics: {},
    lastUpdate: null,
    charts: {
      performance: null,
      distribution: null,
      winRate: null,
      activity: null
    },
    ws: {
      connected: false,
      reconnectAttempts: 0
    }
  });
}
```

### 3. Подписка на изменения

```javascript
// Period selector
store.subscribe('dashboard.currentPeriod', (period) => {
  // Update UI
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.period === period);
  });
});

// Auto-refresh on state change
store.subscribe('dashboard.currentPeriod', () => {
  refreshDashboard();
});
```

### 4. WebSocket state

```javascript
// До
let ws = null;
let wsReconnectAttempts = 0;

// После
store.set('dashboard.ws', {
  connected: false,
  reconnectAttempts: 0
});
```

## Тесты

- [ ] Period selector обновляет state
- [ ] State синхронизируется при reload
- [ ] WebSocket status отображается корректно

## Проблемы

- Chart.js instances требуют cleanup при unmount
- WebSocket требует особой обработки

## Следующий шаг

[Шаг 2.2: Миграция backtest_results.js](./step-2-2-backtest-results.md)
