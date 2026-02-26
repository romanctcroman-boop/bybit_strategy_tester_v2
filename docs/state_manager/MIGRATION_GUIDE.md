# Migration Guide: StateManager (P0-3)

> **Версия:** 1.0.0 | **Дата:** 2026-02-26
> **Статус:** ✅ Применён ко всем 3 страницам (dashboard, backtest_results, strategy_builder)

---

## Содержание

1. [Зачем StateManager?](#зачем-statemanager)
2. [Шаблон миграции: shim-sync](#шаблон-миграции-shim-sync)
3. [Пошаговое руководство](#пошаговое-руководство)
4. [Реальные примеры из проекта](#реальные-примеры-из-проекта)
5. [Частые ошибки](#частые-ошибки)
6. [Тестирование миграции](#тестирование-миграции)
7. [Checklist](#checklist)

---

## Зачем StateManager?

**Проблема до миграции:**

```javascript
// Глобальные переменные разбросаны по файлу
let strategyBlocks = [];
let connections = [];
let selectedBlockId = null;
let zoom = 1;
let isDragging = false;
// ... ещё 30+ переменных

// Нет реактивности — нужно вручную вызывать render после каждого изменения
strategyBlocks.push(newBlock);
renderGraph(); // не забыть!
```

**После миграции:**

```javascript
// Централизованное состояние
setSBBlocks([...getSBBlocks(), newBlock]);
// renderGraph() вызывается автоматически через store.subscribe()
```

**Преимущества:**

- 🔍 Отладка через DevTools (история всех изменений)
- 🧪 Тестируемость (изолированные store instances в тестах)
- 🔄 Реактивность (подписки автоматически обновляют UI)
- 📦 Персистентность (опционально через localStorage)

---

## Шаблон миграции: shim-sync

Используемый в проекте **shim-sync** подход обеспечивает **нулевой риск регрессии**:

```
┌─────────────────────────────────────────────┐
│  Старый код (не трогаем)                    │
│  strategyBlocks.push(block)                 │
│  if (zoom > 2) { ... }                      │
└─────────────┬───────────────────────────────┘
              │ читает/пишет shim переменную
              ▼
┌─────────────────────────────────────────────┐
│  Shim-переменная (module-level let)         │
│  let strategyBlocks = []                    │
│  let zoom = 1                               │
└──────┬──────────────────────┬───────────────┘
       │ subscribe (store→shim)│ setter (shim→store)
       ▼                      ▼
┌─────────────────────────────────────────────┐
│  StateManager store                         │
│  strategyBuilder.graph.blocks: []           │
│  strategyBuilder.viewport.zoom: 1           │
└─────────────────────────────────────────────┘
```

**Ключевые правила:**

1. Shim-переменную **не удалять** — старый код продолжает читать из неё
2. Setter всегда **обновляет и store, и shim**
3. `subscribe()` синхронизирует store → shim для внешних изменений

---

## Пошаговое руководство

### Шаг 1: Импорт и базовая настройка

```javascript
// Добавить в начало файла (после существующих импортов)
import { getStore } from "../core/StateManager.js";
import { initState } from "../core/state-helpers.js";
```

### Шаг 2: Функция инициализации state

Создать функцию с именем `initialize<PageName>State()`:

```javascript
function initializeMyPageState() {
    const s = getStore();
    // Использовать initState() чтобы не перезаписать уже существующие значения
    initState(s, "myPage.items", []);
    initState(s, "myPage.loading", false);
    initState(s, "myPage.currentItem", null);
    initState(s, "myPage.pagination.page", 0);
    initState(s, "myPage.pagination.total", 0);
}
```

### Шаг 3: Геттеры и сеттеры

Для каждой shim-переменной создать пару getter/setter:

```javascript
// Геттеры — читают из store
function getItems() {
    return getStore().get("myPage.items") ?? [];
}
function isLoading() {
    return getStore().get("myPage.loading") ?? false;
}
function getCurrentItem() {
    return getStore().get("myPage.currentItem");
}

// Сеттеры — обновляют и store, и shim
function setItems(v) {
    items = v;
    getStore().set("myPage.items", v);
}
function setLoading(v) {
    loading = v;
    getStore().set("myPage.loading", v);
}
function setCurrentItem(v) {
    currentItem = v;
    getStore().set("myPage.currentItem", v);
}
```

> 💡 **Соглашение об именовании:** `getSB*` / `setSB*` для strategy_builder,
> `getBR*` / `setBR*` для backtest_results.

### Шаг 4: Shim-sync функция

```javascript
function _setupMyPageShimSync() {
    const s = getStore();
    // store → shim (для изменений из внешних источников)
    s.subscribe("myPage.items", (v) => {
        items = v;
    });
    s.subscribe("myPage.loading", (v) => {
        loading = v;
    });
    s.subscribe("myPage.currentItem", (v) => {
        currentItem = v;
    });
}
```

### Шаг 5: Вызов при инициализации

```javascript
// В функции инициализации страницы (обычно DOMContentLoaded)
function init() {
    initializeMyPageState();
    _setupMyPageShimSync();
    // ... остальная инициализация
}
```

### Шаг 6: Замена мест мутации

Найти все места где shim-переменная изменяется и добавить вызов сеттера:

**До:**

```javascript
function addItem(item) {
    items = [...items, item];
    render();
}
```

**После:**

```javascript
function addItem(item) {
    setItems([...getItems(), item]);
    render();
}
```

### Шаг 7: Написать тесты

```javascript
// Шаблон теста (см. frontend/tests/pages/*_state.test.js)
describe("myPage — store→shim sync", () => {
    let store;
    let items;

    beforeEach(() => {
        store = new StateManager({});
        store.set("myPage.items", []);
        items = [];
        store.subscribe("myPage.items", (v) => {
            items = v;
        });
    });

    it("setItems() syncs store→shim", () => {
        const newItems = [{ id: 1 }];
        store.set("myPage.items", newItems);
        expect(items).toEqual(newItems);
    });
});
```

---

## Реальные примеры из проекта

### strategy_builder.js — 19 state-путей

| Shim-переменная          | Store-путь                                    |
| ------------------------ | --------------------------------------------- |
| `strategyBlocks`         | `strategyBuilder.graph.blocks`                |
| `connections`            | `strategyBuilder.graph.connections`           |
| `selectedBlockId`        | `strategyBuilder.selection.selectedBlockId`   |
| `selectedBlockIds`       | `strategyBuilder.selection.selectedBlockIds`  |
| `zoom`                   | `strategyBuilder.viewport.zoom`               |
| `isDragging`             | `strategyBuilder.viewport.isDragging`         |
| `dragOffset`             | `strategyBuilder.viewport.dragOffset`         |
| `isMarqueeSelecting`     | `strategyBuilder.viewport.isMarqueeSelecting` |
| `isConnecting`           | `strategyBuilder.connecting.isConnecting`     |
| `connectionStart`        | `strategyBuilder.connecting.connectionStart`  |
| `isGroupDragging`        | `strategyBuilder.groupDrag.isGroupDragging`   |
| `groupDragOffsets`       | `strategyBuilder.groupDrag.groupDragOffsets`  |
| `currentSyncSymbol`      | `strategyBuilder.sync.currentSyncSymbol`      |
| `currentSyncStartTime`   | `strategyBuilder.sync.currentSyncStartTime`   |
| `currentBacktestResults` | `strategyBuilder.ui.currentBacktestResults`   |

**Ключевые функции:** `getSBBlocks()`, `setSBBlocks()`, `getSBZoom()`, `setSBZoom()`, ...
**Shim-sync:** `_setupStrategyBuilderShimSync()` (18 подписок)
**Тесты:** `frontend/tests/pages/strategy_builder_state.test.js` (36/36 ✅)

### backtest_results.js — 28 state-путей

| Shim-переменная      | Store-путь                            |
| -------------------- | ------------------------------------- |
| `currentBacktest`    | `backtestResults.currentBacktest`     |
| `allResults`         | `backtestResults.allResults`          |
| `compareMode`        | `backtestResults.compareMode`         |
| `selectedForCompare` | `backtestResults.selectedForCompare`  |
| `tradesCurrentPage`  | `backtestResults.trades.currentPage`  |
| `equityChart`        | `backtestResults.charts.equity`       |
| `priceChart`         | `backtestResults.priceChart.instance` |
| ...                  | ... (28 путей всего)                  |

**Ключевые функции:** `setCurrentBacktest()`, `setCompareMode()`, `setChart()`, ...
**Shim-sync:** `_setupLegacyShimSync()` (24 подписки)
**Тесты:** `frontend/tests/pages/backtest_results_state.test.js` (28/28 ✅)

### dashboard.js — shim sync

Аналогичная структура, без отдельного тест-файла (низкий риск регрессии).

---

## Частые ошибки

### ❌ Забыть обновить shim в сеттере

```javascript
// НЕПРАВИЛЬНО — store обновлён, но shim нет
function setZoom(v) {
    getStore().set("strategyBuilder.viewport.zoom", v);
    // zoom = v; // забыли!
}
```

```javascript
// ПРАВИЛЬНО
function setZoom(v) {
    zoom = v; // shim сначала
    getStore().set("strategyBuilder.viewport.zoom", v);
}
```

### ❌ Читать из shim там, где нужен store

```javascript
// НЕПРАВИЛЬНО — читаем потенциально устаревший shim
function getZoomLevel() {
    return zoom;
}

// ПРАВИЛЬНО — всегда актуальное значение из store
function getZoomLevel() {
    return getStore().get("strategyBuilder.viewport.zoom") ?? 1;
}
```

### ❌ Подписываться внутри рендер-функций

```javascript
// НЕПРАВИЛЬНО — создаёт новую подписку при каждом рендере
function render() {
    store.subscribe("items", updateList); // утечка!
}

// ПРАВИЛЬНО — подписка один раз при инициализации
function _setupShimSync() {
    store.subscribe("items", updateList);
}
```

### ❌ Мутировать объект напрямую (без set)

```javascript
// НЕПРАВИЛЬНО — store не узнает об изменении
const blocks = getSBBlocks();
blocks.push(newBlock); // мутация!

// ПРАВИЛЬНО
setSBBlocks([...getSBBlocks(), newBlock]);
```

---

## Тестирование миграции

### Структура тестов

```
frontend/tests/
├── pages/
│   ├── backtest_results_state.test.js   # 28 тестов
│   └── strategy_builder_state.test.js  # 36 тестов
├── integration/
│   └── state-sync.test.js              # 33 теста (core + cross-page)
└── core/
    ├── StateManager.test.js
    └── state-helpers.test.js
```

### Запуск

```bash
cd frontend
npm test                                    # все тесты
npm test -- tests/pages/                   # только page tests
npm test -- tests/integration/             # только интеграционные
```

### Шаблон unit-теста для новой страницы

```javascript
import { describe, it, expect, beforeEach } from "vitest";
import { StateManager } from "../../js/core/StateManager.js";

describe("myPage — store→shim sync", () => {
    let store;
    let shimVar;

    beforeEach(() => {
        store = new StateManager({});
        store.set("myPage.var", null);
        shimVar = null;
        store.subscribe("myPage.var", (v) => {
            shimVar = v;
        });
    });

    it("store update reflects in shim", () => {
        store.set("myPage.var", "test");
        expect(shimVar).toBe("test");
        expect(store.get("myPage.var")).toBe("test");
    });
});
```

---

## Checklist

Перед завершением миграции страницы:

- [ ] `initializeXxxState()` — создаёт все пути через `initState()`
- [ ] Геттеры для всех shim-переменных (`getXxx()`)
- [ ] Сеттеры обновляют и shim, и store (`setXxx(v) { shim = v; store.set(...) }`)
- [ ] `_setupXxxShimSync()` — подписки store→shim для всех путей
- [ ] Вызов `initializeXxxState()` и `_setupXxxShimSync()` при старте страницы
- [ ] Сеттеры вызываются во всех местах мутации shim-переменных
- [ ] Unit-тесты: `tests/pages/xxx_state.test.js` — покрывают все пути
- [ ] Все тесты проходят: `npm test`
- [ ] ESLint чист: `npx eslint js/pages/xxx.js`

---

_Документ создан: 2026-02-26 | P0-3 StateManager Migration_
_Применён к: dashboard.js, backtest_results.js, strategy_builder.js_
