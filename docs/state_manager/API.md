# StateManager API Reference

> **Версия:** 1.0.0 | **Дата:** 2026-02-26
> **Файл:** `frontend/js/core/StateManager.js` (565 строк)
> **Хелперы:** `frontend/js/core/state-helpers.js` (280 строк)

---

## Содержание

1. [Класс StateManager](#класс-statemanager)
2. [Функции-хелперы](#функции-хелперы)
3. [Паттерн shim-sync (миграция)](#паттерн-shim-sync)
4. [Примеры использования](#примеры-использования)

---

## Класс StateManager

### Конструктор

```javascript
new StateManager(initialState?, options?)
```

| Параметр               | Тип        | По умолчанию  | Описание                                    |
| ---------------------- | ---------- | ------------- | ------------------------------------------- |
| `initialState`         | `Object`   | `{}`          | Начальное состояние                         |
| `options.maxHistory`   | `number`   | `50`          | Максимальный размер истории undo/redo       |
| `options.persist`      | `boolean`  | `false`       | Включить персистентность через localStorage |
| `options.persistKey`   | `string`   | `'app_state'` | Ключ для localStorage                       |
| `options.persistPaths` | `string[]` | `null`        | Пути для персистентности (`null` = все)     |
| `options.devtools`     | `boolean`  | `true`        | Включить интеграцию с devtools              |

**Пример:**

```javascript
import { StateManager } from "../core/StateManager.js";

const store = new StateManager(
    {
        user: null,
        settings: { theme: "dark" },
    },
    {
        persist: true,
        persistKey: "myapp_state",
        maxHistory: 100,
    },
);
```

---

### Методы чтения

#### `get(path?, defaultValue?)`

Получить значение по dot-notation пути. Возвращает глубокую копию.

```javascript
store.get("user.name"); // → 'John' или undefined
store.get("user.name", "Anonymous"); // → 'John' или 'Anonymous'
store.get(); // → всё состояние (глубокая копия)
```

---

### Методы записи

#### `set(path, value, options?)`

Установить значение. Уведомляет всех подписчиков на этот путь.

```javascript
store.set("user.name", "John");
store.set("counter", 1, { silent: true }); // без уведомления
store.set("flag", true, { action: "TOGGLE_FLAG" }); // с именем действия
```

> ⚠️ **Важно:** `set()` всегда уведомляет подписчиков, даже если значение не изменилось.

#### `merge(path, value, options?)`

Объединить объект с существующим значением (shallow merge).

```javascript
store.merge("user", { age: 30 });
// user было { name: 'John' } → стало { name: 'John', age: 30 }
```

#### `batch(updates, options?)`

Обновить несколько значений за один вызов.

```javascript
store.batch({
    "user.name": "John",
    "ui.loading": false,
    "page.current": 1,
});
```

#### `delete(path, options?)`

Удалить значение из состояния.

```javascript
store.delete("user.tempToken");
```

---

### Подписки

#### `subscribe(paths, callback, options?)`

Подписаться на изменения по пути. Возвращает функцию отписки.

```javascript
// Один путь
const unsub = store.subscribe("user.name", (newVal, path, oldVal) => {
    console.log(`${path}: ${oldVal} → ${newVal}`);
});

// Несколько путей
store.subscribe(["user.name", "user.age"], (newVal, path, oldVal) => {});

// Все изменения
store.subscribe("*", (state, path) => {});

// Немедленный вызов с текущим значением
store.subscribe("user", cb, { immediate: true });

// Отписка
unsub();
```

**Сигнатура callback:**

| Параметр   | Тип      | Описание                                |
| ---------- | -------- | --------------------------------------- |
| `newValue` | `any`    | Новое значение                          |
| `path`     | `string` | Путь, который изменился                 |
| `oldValue` | `any`    | Старое значение (из prevState snapshot) |

#### `computed(dependencies, computeFn, callback)`

Вычисляемое значение, пересчитывается при изменении зависимостей.

```javascript
store.computed(
    ["user.firstName", "user.lastName"],
    (first, last) => `${first} ${last}`,
    (fullName) => {
        document.title = fullName;
    },
);
```

---

### Middleware

#### `use(middleware)`

Добавить middleware, который перехватывает каждый вызов `set()`.

```javascript
store.use((action) => {
    // action: { type, path, value, prevValue, state }
    console.log("[Store]", action.type, action.path, "=", action.value);
    return action.value; // вернуть value или false для отмены
});
```

---

### История (undo/redo)

#### `undo()` / `redo()` / `reset()`

```javascript
store.undo(); // откатить последнее изменение
store.redo(); // повторить отменённое изменение
store.reset(); // сбросить к начальному состоянию
```

---

### Отладка

#### `getSnapshot()`

```javascript
const snap = store.getSnapshot();
// → { state, historyLength, historyIndex, listeners }
```

---

## Функции-хелперы

Из `frontend/js/core/state-helpers.js`:

### `getStore()`

Получить глобальный singleton store.

```javascript
import { getStore } from "../core/StateManager.js";
const store = getStore();
```

### `initState(path, defaultValue)`

Установить значение только если его ещё нет.

```javascript
initState("page.currentItem", null);
initState("page.filters", { sort: "asc", limit: 50 });
```

### `bindToState(selector, statePath, property?, transform?)`

Привязать DOM элемент к пути (одностороннее, store→DOM).

```javascript
bindToState("#symbol-label", "market.symbol", "textContent");
bindToState("#count", "page.total", "textContent", (v) => `${v} записей`);
```

### `bindInputToState(selector, statePath, options?)`

Двустороннее связывание для `<input>`.

```javascript
bindInputToState("#search-input", "page.searchQuery");
bindInputToState("#price", "order.price", {
    transformOnGet: (v) => (v / 100).toFixed(2),
    transformOnSet: (v) => Math.round(parseFloat(v) * 100),
});
```

### `bindCheckboxToState(selector, statePath)`

Связывание для `<input type="checkbox">`.

```javascript
bindCheckboxToState("#enable-feature", "settings.featureEnabled");
```

### `createComputed(dependencies, computeFn, targetPath)`

Сохранять вычисленное значение в state.

```javascript
createComputed(["order.price", "order.qty"], (price, qty) => price * qty, "order.total");
```

### `getStateSlice(paths)`

Получить объект с подмножеством путей.

```javascript
const slice = getStateSlice(["user.name", "user.email"]);
// → { 'user.name': 'John', 'user.email': 'john@example.com' }
```

### `createLoggingMiddleware(prefix?)`

Middleware для логирования всех изменений.

```javascript
import { createLoggingMiddleware } from "../core/state-helpers.js";
store.use(createLoggingMiddleware("[StrategyBuilder]"));
```

---

## Паттерн shim-sync

Используется в `dashboard.js`, `backtest_results.js`, `strategy_builder.js` для **нулевого риска регрессии** при миграции.

### Принцип

```
Старый код читает/пишет legacy переменную
      ↕  (shim остаётся как module-level let)
store.subscribe() синхронизирует store → shim
setter calls     синхронизирует shim → store
```

### Шаблон реализации

```javascript
// 1. Объявление shim (не удалять — обратная совместимость)
let strategyBlocks = [];
let zoom = 1;

// 2. Инициализация store
function initializeMyPageState() {
    const s = getStore();
    initState("myPage.blocks", []);
    initState("myPage.zoom", 1);
}

// 3. Геттеры/сеттеры
function getBlocks() {
    return getStore().get("myPage.blocks") ?? [];
}
function setBlocks(v) {
    getStore().set("myPage.blocks", v);
    strategyBlocks = v;
}
function getZoom() {
    return getStore().get("myPage.zoom") ?? 1;
}
function setZoom(v) {
    getStore().set("myPage.zoom", v);
    zoom = v;
}

// 4. Shim sync (store → shim)
function _setupShimSync() {
    const s = getStore();
    s.subscribe("myPage.blocks", (v) => {
        strategyBlocks = v;
    });
    s.subscribe("myPage.zoom", (v) => {
        zoom = v;
    });
}

// 5. Вызов при инициализации страницы
initializeMyPageState();
_setupShimSync();
```

---

## Примеры использования

### Читать текущее состояние

```javascript
const store = getStore();
const symbol = store.get("market.symbol", "BTCUSDT");
const zoom = store.get("strategyBuilder.viewport.zoom", 1);
```

### Реагировать на изменения

```javascript
store.subscribe("strategyBuilder.graph.blocks", (blocks) => {
    renderGraph(blocks);
});
```

### Обновить из нескольких мест

```javascript
// В обработчике события
function onBlockAdded(block) {
    const blocks = getBlocks();
    setSBBlocks([...blocks, block]);
}

// В загрузчике данных
async function loadStrategy(id) {
    const data = await fetch(`/api/v1/strategies/${id}`).then((r) => r.json());
    setSBBlocks(data.blocks);
    setSBConnections(data.connections);
}
```

---

_Документ создан: 2026-02-26 | P0-3 StateManager Migration_
