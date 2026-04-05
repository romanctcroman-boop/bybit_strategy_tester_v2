# frontend/ — Контекст модуля

## Главное правило
**Нет build step. Нет npm. Нет webpack. Чистые ES modules.**
После любого изменения — просто перезагрузи браузер.

## Структура
```
frontend/
  strategy-builder.html   — ОСНОВНАЯ страница (Builder UI)
  backtest-results.html   — Результаты бэктестов
  optimizations.html      — Оптимизация параметров
  dashboard.html          — Дашборд
  css/
    strategy_builder.css  — Стили Builder
  js/
    pages/
      strategy_builder.js    — Builder логика (~13378 строк, Phase 5 рефакторинг ✅)
      backtest_results.js    — Таблицы и графики
      optimization_*.js      — Панели оптимизации
    shared/
      leverageManager.js     — Shared leverage модуль
      instrumentService.js   — Symbols сервис
    core/                    — EventBus, StateManager, ApiClient
    components/              — UI компоненты
    strategy_builder/        — Модули Builder (Phase 5 рефакторинг ✅)
      SymbolSyncModule.js    — Symbol picker, DB panel, SSE sync (~707 строк)
      blockLibrary.js        — Каталог блоков (~158 строк)
      BlocksModule.js        — Stub (архитектурный скелет)
      CanvasModule.js        — Stub
      PropertiesModule.js    — Stub
      ToolbarModule.js       — Stub
      index.js               — Stub
```

## Ключевые паттерны

### Commission в UI — процент, в backend — decimal
```javascript
// UI показывает: 0.07 (процент)
// Backend получает: 0.0007 (decimal)
// Конвертация происходит в стратегии отправки формы
```

### Leverage slider
- Максимум 125 (Bybit max)
- Цвет-кодирование: зелёный→жёлтый→красный при повышении

### Direction mismatch
- CSS класс `.direction-mismatch` = красный пунктирный провод (stroke: #ef4444)
- Пересчитывать при изменении параметров блока

### warnings[] из бэктеста
```javascript
// Каждый warning → нотификация пользователю
response.warnings?.forEach(w => showNotification(w, 'warning'));
```

### API calls
```javascript
// Всегда через ApiClient, не fetch напрямую
const result = await ApiClient.post('/api/backtests/', payload);
```

## Что НЕ делать
- `var` → использовать `const`/`let`
- Синхронный XHR → async/await
- Прямой `fetch()` → ApiClient
- `console.log` в продакшне → убирай перед коммитом

## Тесты
Frontend тесты в `tests/frontend/` (JavaScript).
Запуск описан в `tests/frontend/README.md` (если есть).

## Отладка Builder
При проблемах с блоками/соединениями смотри:
- `js/pages/strategy_builder_debug.js` — debug утилиты
- Canvas координаты делятся на `zoom` (баг был исправлен 2026-02-21)
- Block IDs: `block_${Date.now()}_${random}` (суффикс добавлен 2026-02-21)

## Известные исправленные баги (2026-03-28)

### ConnectionsModule — `normalizeConnection()` portId

`normalizeConnection()` всегда ставил `portId: 'out'/'in'`, игнорируя реальные имена портов.
Canvas искал `[data-port-id="out"]` → провода не рендерились для AI-стратегий.
**Исправление:** `conn.fromPort || 'out'` и `conn.toPort || 'in'` вместо хардкода.

### AiBuildModule — символ не обновляется в панели

AI панель "Symbol: —" обновляется только при открытии `openAiBuildModal()`, не при смене символа пока модал открыт.
Это косметично — `runAiBuild()` читает `backtestSymbol` свежим при клике.
**Workaround:** закрой и снова открой AI панель после смены символа.

### SymbolSync — инициализация до создания объекта

`setupEventListeners()` вызывал `symbolSync.initDunnahBasePanel()` до того, как `symbolSync` был создан → `symbolSync` оставался null → все `syncSymbolData()` были no-op.
**Исправление:** перенос `initDunnahBasePanel()` после создания `symbolSync` (~line 840 в `strategy_builder.js`).

## Тесты

Frontend тесты в `tests/frontend/` (JavaScript). 759/759 passing (2026-03-24).
Запуск описан в `tests/frontend/README.md` (если есть).
