# 🚀 P0-3: StateManager — Быстрый старт для следующей сессии

**Дата:** 2026-02-26
**Следующая задача:** Миграция dashboard.js (1 час)

---

## 📋 Что сделано

✅ **Подготовка завершена (100%)**
- StateManager.js создан (471 строка)
- state-helpers.js создан (280 строк)
- Unit тесты написаны (630 строк)
- Планы миграции созданы (1,800+ строк документации)

⏳ **Миграция страниц (0%)**
- dashboard.js — ожидает
- backtest_results.js — ожидает
- strategy_builder.js — ожидает

---

## 🎯 Следующая сессия: Миграция dashboard.js

**Время:** 1 час
**Файл:** `frontend/js/pages/dashboard.js` (1,955 строк)
**План:** `docs/refactoring/p0-3-state-manager/step-2-1-dashboard.md`

### Пошаговый план

#### 1. Импорт StateManager (5 мин)

```javascript
// В начало файла dashboard.js
import { getStore } from '../core/StateManager.js';
import { bindToState, bindInputToState, initState } from '../core/state-helpers.js';

const store = getStore();
```

#### 2. Инициализация state (10 мин)

```javascript
function initializeDashboardState() {
  store.merge('dashboard', {
    currentPeriod: '24h',
    dateRange: { from: null, to: null },
    metrics: {},
    lastUpdate: null,
    charts: {
      performance: null,
      distribution: null,
      winRate: null,
      activity: null,
      portfolioHistory: null,
      pnlMini: null
    },
    ws: {
      connected: false,
      reconnectAttempts: 0,
      reconnectTimeout: null
    },
    market: {
      data: [],
      tickerData: []
    },
    watchlist: JSON.parse(localStorage.getItem('dashboard_watchlist') || '["BTCUSDT","ETHUSDT","SOLUSDT"]'),
    watchlistPrices: {},
    calendar: {
      year: new Date().getFullYear(),
      month: new Date().getMonth()
    }
  });
}

// Вызвать при загрузке страницы
initializeDashboardState();
```

#### 3. Геттеры/сеттеры (15 мин)

```javascript
// Period
function getCurrentPeriod() {
  return store.get('dashboard.currentPeriod') || '24h';
}

function setCurrentPeriod(period) {
  store.set('dashboard.currentPeriod', period);
}

// Charts
function getChart(name) {
  return store.get(`dashboard.charts.${name}`);
}

function setChart(name, instance) {
  store.set(`dashboard.charts.${name}`, instance);
}

// WebSocket
function getWsState() {
  return store.get('dashboard.ws') || { connected: false, reconnectAttempts: 0 };
}

function setWsState(state) {
  store.merge('dashboard.ws', state);
}
```

#### 4. Подписки (15 мин)

```javascript
// Подписка на период
store.subscribe('dashboard.currentPeriod', (period) => {
  // Обновить UI period selector
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.period === period);
  });
  
  // Автоматический refresh
  refreshDashboard();
});

// Подписка на charts
store.subscribe('dashboard.charts', (charts) => {
  // При необходимости обновить UI
});

// Подписка на WebSocket state
store.subscribe('dashboard.ws.connected', (connected) => {
  // Обновить индикатор подключения
  const indicator = document.getElementById('wsIndicator');
  if (indicator) {
    indicator.className = connected ? 'connected' : 'disconnected';
  }
});
```

#### 5. Замена глобальных переменных (15 мин)

**До:**
```javascript
let currentPeriod = '24h';
let dashboardData = {};
let ws = null;
let wsReconnectAttempts = 0;
```

**После:**
```javascript
// Удалить все глобальные переменные
// State хранится в store
```

#### 6. Обновление функций (10 мин)

**До:**
```javascript
function refreshDashboard() {
  const period = currentPeriod;
  // ...
}
```

**После:**
```javascript
function refreshDashboard() {
  const period = getCurrentPeriod();
  // ...
}
```

#### 7. Тесты (10 мин)

```javascript
// tests/frontend/pages/dashboard.test.js
describe('Dashboard StateManager', () => {
  it('should update period in state', () => {
    store.set('dashboard.currentPeriod', '7d');
    expect(store.get('dashboard.currentPeriod')).toBe('7d');
  });

  it('should notify on period change', (done) => {
    store.subscribe('dashboard.currentPeriod', (period) => {
      expect(period).toBe('7d');
      done();
    });
    store.set('dashboard.currentPeriod', '7d');
  });
});
```

---

## ✅ Чеклист завершения

- [ ] StateManager импортирован
- [ ] State инициализирован
- [ ] Геттеры/сеттеры созданы
- [ ] Подписки добавлены
- [ ] Глобальные переменные удалены
- [ ] Функции обновлены
- [ ] Тесты написаны
- [ ] Существующие тесты проходят
- [ ] Документация обновлена

---

## 🔍 Отладка

```javascript
// Проверка state
console.log(store.get('dashboard'));

// Проверка подписчиков
console.log(store._listeners);

// Проверка истории
console.log(store._history);

// Devtools
window.__STATE_MANAGER__ = store;
```

---

## 📁 Файлы

**Для работы:**
- `frontend/js/pages/dashboard.js` — мигрируемый файл
- `docs/refactoring/p0-3-state-manager/step-2-1-dashboard.md` — полный план

**Справочники:**
- `frontend/js/core/StateManager.js` — базовый класс
- `frontend/js/core/state-helpers.js` — хелперы

**Тесты:**
- `tests/frontend/core/StateManager.test.js` — пример тестов

---

## 🆘 Помощь

**Проблема:** State не синхронизируется

**Решение:**
```javascript
// Убедитесь что используете тот же store
const store = getStore(); // Всегда вызывайте getStore()
```

**Проблема:** Подписка вызывается слишком часто

**Решение:**
```javascript
// Используйте debounce
import { debounce } from '../utils.js';
const debouncedCallback = debounce(callback, 100);
store.subscribe('dashboard.data', debouncedCallback);
```

**Проблема:** Chart instances не сохраняются

**Решение:**
```javascript
// Chart instances не должны персистироваться
// Храните в state, но не включайте в persistPaths
new StateManager(state, {
  persist: true,
  persistPaths: ['dashboard.currentPeriod', 'dashboard.settings']
  // dashboard.charts не персистировать
});
```

---

*Создано: 2026-02-26*
*Для следующей сессии*
