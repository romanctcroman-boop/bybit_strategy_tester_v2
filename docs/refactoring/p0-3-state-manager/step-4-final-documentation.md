# Шаг 4: Финальная документация

**Дата:** 2026-02-26
**Статус:** ⏳ Ожидает
**Оценка:** 3 часа

---

## Цель

Создать полную документацию для StateManager:
- API документация
- Migration Guide для разработчиков
- Best Practices
- Troubleshooting

---

## Документы

### 1. API Документация

**Файл:** `docs/state_manager/API.md`

```markdown
# StateManager API Reference

## Класс StateManager

### Конструктор

```javascript
new StateManager(initialState?: Object, options?: Object)
```

**Параметры:**
- `initialState` (Object, optional): Начальное состояние
- `options` (Object, optional): Опции
  - `maxHistory` (number): Максимальный размер истории (по умолчанию 50)
  - `persist` (boolean): Включить персистентность (по умолчанию false)
  - `persistKey` (string): Ключ для localStorage (по умолчанию 'app_state')
  - `persistPaths` (string[]): Пути для персистентности (null = все)
  - `devtools` (boolean): Включить devtools (по умолчанию true)

### Методы

#### get(path?, defaultValue?)

Получить значение из state.

```javascript
const value = store.get('user.name');
const all = store.get(); // Всё состояние
const withDefault = store.get('missing', 'default');
```

#### set(path, value, options?)

Установить значение в state.

```javascript
store.set('user.name', 'John');
store.set('counter', 1, { silent: true }); // Без уведомления
store.set('action', 'update', { action: 'UPDATE_USER' }); // С экшеном
```

#### merge(path, value, options?)

Объединить объект с существующим значением.

```javascript
store.merge('user', { age: 30 });
```

#### batch(updates, options?)

Обновить несколько значений одновременно.

```javascript
store.batch({
  'user.name': 'John',
  'user.age': 30,
  'ui.loading': false
});
```

#### subscribe(paths, callback, options?)

Подписаться на изменения.

```javascript
const unsubscribe = store.subscribe('user.name', (newValue, path, prevValue) => {
  console.log(`Name changed from ${prevValue} to ${newValue}`);
});

// Отписка
unsubscribe();

// Подписка на несколько путей
store.subscribe(['user.name', 'user.age'], callback);

// Подписка на все изменения
store.subscribe('*', callback);

// Немедленный вызов
store.subscribe('user', callback, { immediate: true });
```

#### computed(dependencies, computeFn, callback)

Создать вычисляемое значение.

```javascript
store.computed(
  ['user.firstName', 'user.lastName'],
  (firstName, lastName) => `${firstName} ${lastName}`,
  (fullName) => {
    console.log('Full name:', fullName);
  }
);
```

#### use(middleware)

Добавить middleware.

```javascript
store.use((action) => {
  console.log('Action:', action);
  return action.value; // Вернуть изменённое значение или false для отмены
});
```

#### undo() / redo() / reset()

Управление историей.

```javascript
store.undo();
store.redo();
store.reset();
```

#### getSnapshot()

Получить снапшот для отладки.

```javascript
const snapshot = store.getSnapshot();
// { state, historyLength, historyIndex, listeners }
```

---

## Функции-хелперы

### getStore()

Получить глобальный store.

```javascript
const store = getStore();
```

### createStore(initialState, options)

Создать новый store.

```javascript
const store = createStore({ theme: 'dark' });
```

### initStore(customState, options)

Инициализировать глобальный store с state по умолчанию.

```javascript
const store = initStore({
  custom: 'value'
}, {
  persist: true
});
```

### bindToState(selector, statePath, property?, transform?)

Привязать DOM элемент к state.

```javascript
bindToState('#theme', 'ui.theme', 'textContent');
bindToState('#count', 'counter', 'value', v => v * 2);
```

### bindInputToState(selector, statePath, options?)

Двусторонняя привязка для input.

```javascript
bindInputToState('#name', 'user.name');
bindInputToState('#price', 'product.price', {
  transformOnGet: v => v / 100,
  transformOnSet: v => v * 100
});
```

### bindCheckboxToState(selector, statePath)

Привязка для checkbox.

```javascript
bindCheckboxToState('#enabled', 'feature.enabled');
```

### createComputed(dependencies, computeFn, targetPath)

Создать computed с сохранением в state.

```javascript
createComputed(
  ['user.firstName', 'user.lastName'],
  (first, last) => `${first} ${last}`,
  'user.fullName'
);
```

### initState(path, defaultValue)

Инициализировать значение если не существует.

```javascript
initState('user.settings', { theme: 'dark' });
```

### getStateSlice(paths)

Получить срез state.

```javascript
const slice = getStateSlice(['user.name', 'user.age']);
// { 'user.name': 'John', 'user.age': 30 }
```

### createLoggingMiddleware(prefix?)

Создать middleware для логирования.

```javascript
store.use(createLoggingMiddleware('[MyApp]'));
```
```

---

### 2. Migration Guide

**Файл:** `docs/state_manager/MIGRATION_GUIDE.md`

```markdown
# Migration Guide: StateManager

## Пошаговое руководство по миграции

### Шаг 1: Подготовка

1. Импортируйте StateManager:
```javascript
import { getStore } from '../core/StateManager.js';
import { bindToState, initState } from '../core/state-helpers.js';

const store = getStore();
```

2. Инициализируйте state:
```javascript
function initializeState() {
  store.merge('myPage', {
    data: null,
    loading: false,
    error: null
  });
}
```

### Шаг 2: Создание геттеров/сеттеров

**До:**
```javascript
let currentPage = 1;
let items = [];

function loadItems() {
  items = fetchData();
  render();
}
```

**После:**
```javascript
function getCurrentPage() {
  return store.get('myPage.currentPage') || 1;
}

function setCurrentPage(page) {
  store.set('myPage.currentPage', page);
}

function getItems() {
  return store.get('myPage.items') || [];
}

function setItems(items) {
  store.set('myPage.items', items);
}

function loadItems() {
  const items = fetchData();
  setItems(items);
  // render() вызывается автоматически через subscribe
}
```

### Шаг 3: Добавление подписок

```javascript
// При инициализации
store.subscribe('myPage.items', (items) => {
  renderItems(items);
});

store.subscribe('myPage.loading', (loading) => {
  toggleLoadingSpinner(loading);
});
```

### Шаг 4: Удаление глобальных переменных

После того как все функции используют геттеры/сеттеры, удалите глобальные переменные:

```javascript
// Удалить:
// let currentPage = 1;
// let items = [];
```

### Шаг 5: Тестирование

1. Проверьте что state синхронизируется
2. Проверьте что подписки работают
3. Проверьте персистентность (если нужна)

## Частые проблемы

### Проблема: State не синхронизируется

**Решение:** Убедитесь что используете один и тот же store:
```javascript
const store = getStore(); // Всегда вызывайте getStore()
```

### Проблема: Подписка вызывается слишком часто

**Решение:** Используйте debounce:
```javascript
import { debounce } from '../utils.js';

const debouncedRender = debounce(render, 100);
store.subscribe('data', debouncedRender);
```

### Проблема: Circular references

**Решение:** StateManager автоматически обрабатывает circular refs. Если проблемы остаются, используйте IDs вместо прямых ссылок.

## Checklist миграции

- [ ] Импортирован StateManager
- [ ] Инициализирован state
- [ ] Созданы геттеры/сеттеры
- [ ] Добавлены подписки
- [ ] Удалены глобальные переменные
- [ ] Тесты проходят
```

---

### 3. Best Practices

**Файл:** `docs/state_manager/BEST_PRACTICES.md`

```markdown
# StateManager Best Practices

## Структура state

### ✅ Хорошо

```javascript
store.merge('dashboard', {
  currentPeriod: '24h',
  metrics: {},
  charts: {
    performance: null,
    distribution: null
  }
});
```

### ❌ Плохо

```javascript
// Плоская структура без иерархии
store.set('dashboard_currentPeriod', '24h');
store.set('dashboard_metrics', {});
```

## Подписки

### ✅ Хорошо

```javascript
// Подписка на конкретный путь
store.subscribe('user.name', callback);

// Очистка подписок
useEffect(() => {
  const unsubscribe = store.subscribe('data', callback);
  return () => unsubscribe();
}, []);
```

### ❌ Плохо

```javascript
// Подписка на всё
store.subscribe('*', callback); // Будет вызываться слишком часто

// Утечка подписок
store.subscribe('data', callback); // Нет отписки
```

## Производительность

### ✅ Хорошо

```javascript
// Batch updates
store.batch({
  'user.name': name,
  'user.age': age,
  'user.email': email
});

// Debounce частых обновлений
const debouncedUpdate = debounce(update, 100);
store.subscribe('viewport.panOffset', debouncedUpdate);
```

### ❌ Плохо

```javascript
// Частые одиночные обновления
store.set('a', 1);
store.set('b', 2);
store.set('c', 3);

// Обновление на каждый кадр без debounce
store.subscribe('viewport', render); // 60fps может быть избыточно
```

## Персистентность

### ✅ Хорошо

```javascript
// Персистентность только необходимых данных
new StateManager(state, {
  persist: true,
  persistPaths: ['ui.theme', 'user.settings']
});
```

### ❌ Плохо

```javascript
// Персистентность всего (включая chart instances)
new StateManager(state, {
  persist: true
});
```

## Тестирование

### ✅ Хорошо

```javascript
describe('StateManager', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should update state', () => {
    store.set('value', 1);
    expect(store.get('value')).toBe(1);
  });
});
```

## Отладка

### ✅ Хорошо

```javascript
// Devtools integration
window.__STATE_MANAGER__ = store;

// Логирование через middleware
store.use(createLoggingMiddleware('[MyApp]'));

// Снапшоты для отладки
const snapshot = store.getSnapshot();
console.log(snapshot);
```

## Middleware

```javascript
// Валидация
store.use((action) => {
  if (action.type === 'SET' && !action.value) {
    console.warn('Setting falsy value');
  }
  return action.value;
});

// Логирование
store.use((action) => {
  console.log('Action:', action);
  return action.value;
});

// Персистентность
store.use((action) => {
  localStorage.setItem('last_action', JSON.stringify(action));
  return action.value;
});
```
```

---

### 4. Troubleshooting

**Файл:** `docs/state_manager/TROUBLESHOOTING.md`

```markdown
# Troubleshooting

##常见问题

### State не обновляется

**Симптомы:**
- `store.set()` вызывается, но значение не меняется
- Подписки не срабатывают

**Решения:**
1. Проверьте что используете правильный store: `const store = getStore()`
2. Проверьте что путь указан правильно: `store.get('a.b.c')`
3. Проверьте middleware (может отменять действия)

### Подписка вызывается слишком часто

**Симптомы:**
- UI мерцает
- Производительность низкая

**Решения:**
1. Используйте debounce: `debounce(callback, 100)`
2. Подпишитесь на более конкретный путь
3. Используйте `batch()` для групповых обновлений

### Персистентность не работает

**Симптомы:**
- State не сохраняется после reload
- localStorage пуст

**Решения:**
1. Проверьте что `persist: true`
2. Проверьте `persistPaths` (если указан)
3. Проверьте quota localStorage

### Circular reference error

**Симптомы:**
- Ошибка при сериализации

**Решения:**
1. StateManager автоматически обрабатывает circular refs
2. Если проблема остаётся, используйте IDs вместо объектов

### Memory leaks

**Симптомы:**
- Потребление памяти растёт
- Подписки не очищаются

**Решения:**
1. Всегда отписывайтесь: `unsubscribe()`
2. Используйте cleanup в useEffect
3. Проверьте что chart instances уничтожаются

## Debug commands

```javascript
// Получить snapshot
store.getSnapshot();

// Получить всё состояние
store.get();

// Получить конкретный путь
store.get('path.to.value');

// Проверить подписчиков
store._listeners;

// Проверить историю
store._history;
store._historyIndex;

// Отладка middleware
store._middleware;
```
```

---

## Обновление существующей документации

Обновите следующие файлы:

1. **CONTINUE.md** - Добавить статус выполнения
2. **PLAN.md** - Отметить выполненные шаги
3. **SESSION_REPORT.md** - Добавить отчёт о сессии

---

## Критерии приёмки

- [ ] API документация полная
- [ ] Migration Guide понятен
- [ ] Best Practices покрывают основные сценарии
- [ ] Troubleshooting помогает решить проблемы
- [ ] CONTINUE.md обновлён
- [ ] PLAN.md обновлён

---

*План создан: 2026-02-26*
