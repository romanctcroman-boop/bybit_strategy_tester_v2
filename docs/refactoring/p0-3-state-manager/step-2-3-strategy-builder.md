# Шаг 2.3: Миграция strategy_builder.js на StateManager

**Дата:** 2026-02-26
**Статус:** ⏳ Ожидает
**Оценка:** 4 часа

---

## Цель

Заменить глобальные переменные в `strategy_builder.js` (13,378 строк) на StateManager:
- `selectedBlocks` → `strategyBuilder.blocks.selected`
- `graphNodes/connections` → `strategyBuilder.graph.*`
- `zoomLevel/panOffset` → `strategyBuilder.viewport.*`
- `undoStack/redoStack` → `strategyBuilder.history.*`
- `currentSymbol/timeframe` → `market.selectedSymbol/Timeframe`

---

## Структура state

```javascript
store.merge('strategyBuilder', {
  // Graph state
  graph: {
    nodes: [],
    connections: [],
    blocks: []
  },

  // Selection state
  blocks: {
    selected: [],
    hovered: null,
    copied: null
  },

  // Viewport state
  viewport: {
    zoomLevel: 1,
    panOffset: { x: 0, y: 0 },
    scale: 1
  },

  // History (undo/redo)
  history: {
    undoStack: [],
    redoStack: [],
    maxSize: 50
  },

  // Editing state
  editing: {
    selectedBlock: null,
    unsavedChanges: false,
    isDirty: false,
    lastSavedAt: null
  },

  // Canvas state
  canvas: {
    gridSize: 20,
    snapToGrid: true,
    showGrid: true,
    darkMode: true
  },

  // Block library
  library: {
    expandedCategories: ['indicators', 'entries', 'exits'],
    searchQuery: '',
    filteredBlocks: []
  },

  // Properties panel
  properties: {
    selectedBlockId: null,
    panelOpen: true,
    panelWidth: 300
  },

  // Toolbar state
  toolbar: {
    activeTool: 'select', // select, pan, connect, delete
    snapEnabled: true,
    gridVisible: true,
    minimapOpen: false
  },

  // Validation state
  validation: {
    errors: [],
    warnings: [],
    isValid: true,
    lastCheckAt: null
  },

  // Export/Import
  export: {
    format: 'json',
    includeMetadata: true,
    lastExportedAt: null
  },

  // Market context (synced with market state)
  market: {
    selectedSymbol: 'BTCUSDT',
    selectedTimeframe: '1h'
  },

  // Charts (if any embedded charts)
  charts: {
    preview: null,
    minimap: null
  },

  // WebSocket state (if real-time collaboration)
  ws: {
    connected: false,
    collaborators: [],
    pendingChanges: []
  }
});

// Also update market state
store.merge('market', {
  selectedSymbol: 'BTCUSDT',
  selectedTimeframe: '1h',
  watchlist: []
});
```

---

## Изменения

### 1. Импорт StateManager

**До:**
```javascript
let selectedBlocks = [];
let graphNodes = [];
let connections = [];
let zoomLevel = 1;
let panOffset = { x: 0, y: 0 };
```

**После:**
```javascript
import { getStore } from '../core/StateManager.js';
import { bindToState, initState } from '../core/state-helpers.js';

const store = getStore();

function initializeStrategyBuilderState() {
  store.merge('strategyBuilder', {
    graph: { nodes: [], connections: [], blocks: [] },
    blocks: { selected: [], hovered: null, copied: null },
    viewport: { zoomLevel: 1, panOffset: { x: 0, y: 0 }, scale: 1 },
    history: { undoStack: [], redoStack: [], maxSize: 50 },
    // ... остальная структура
  });

  // Sync with market state
  store.merge('market', {
    selectedSymbol: 'BTCUSDT',
    selectedTimeframe: '1h'
  });
}
```

### 2. Геттеры и сеттеры

```javascript
// Graph state
function getGraphState() {
  return store.get('strategyBuilder.graph') || { nodes: [], connections: [] };
}

function setGraphState(updates) {
  store.merge('strategyBuilder.graph', updates);
}

function addNode(node) {
  const current = getGraphState();
  store.set('strategyBuilder.graph.nodes', [...current.nodes, node]);
}

function removeNode(nodeId) {
  const nodes = store.get('strategyBuilder.graph.nodes');
  store.set('strategyBuilder.graph.nodes', nodes.filter(n => n.id !== nodeId));
}

// Selection state
function getSelectedBlocks() {
  return store.get('strategyBuilder.blocks.selected') || [];
}

function setSelectedBlocks(blocks) {
  store.set('strategyBuilder.blocks.selected', blocks);
}

function toggleBlockSelection(blockId) {
  const selected = getSelectedBlocks();
  const newSelected = selected.includes(blockId)
    ? selected.filter(id => id !== blockId)
    : [...selected, blockId];
  setSelectedBlocks(newSelected);
}

// Viewport state
function getViewport() {
  return store.get('strategyBuilder.viewport') || { zoomLevel: 1, panOffset: { x: 0, y: 0 } };
}

function setZoomLevel(zoom) {
  store.set('strategyBuilder.viewport.zoomLevel', Math.max(0.1, Math.min(zoom, 5)));
}

function setPanOffset(x, y) {
  store.merge('strategyBuilder.viewport.panOffset', { x, y });
}

// History state
function pushToUndoStack(action) {
  const stack = store.get('strategyBuilder.history.undoStack') || [];
  const maxSize = store.get('strategyBuilder.history.maxSize') || 50;
  
  stack.push({
    ...action,
    timestamp: Date.now()
  });

  if (stack.length > maxSize) {
    stack.shift();
  }

  store.set('strategyBuilder.history.undoStack', stack);
  store.set('strategyBuilder.history.redoStack', []); // Clear redo on new action
}

function undo() {
  const undoStack = store.get('strategyBuilder.history.undoStack') || [];
  const redoStack = store.get('strategyBuilder.history.redoStack') || [];

  if (undoStack.length === 0) return null;

  const lastAction = undoStack.pop();
  redoStack.push(lastAction);

  store.set('strategyBuilder.history.undoStack', undoStack);
  store.set('strategyBuilder.history.redoStack', redoStack);

  return lastAction;
}

function redo() {
  const undoStack = store.get('strategyBuilder.history.undoStack') || [];
  const redoStack = store.get('strategyBuilder.history.redoStack') || [];

  if (redoStack.length === 0) return null;

  const action = redoStack.pop();
  undoStack.push(action);

  store.set('strategyBuilder.history.undoStack', undoStack);
  store.set('strategyBuilder.history.redoStack', redoStack);

  return action;
}
```

### 3. Подписки на изменения

```javascript
// Подписка на изменения графа
store.subscribe('strategyBuilder.graph', (graph) => {
  renderGraph(graph);
  updateConnections();
  checkValidation();
});

// Подписка на выделение блоков
store.subscribe('strategyBuilder.blocks.selected', (selected) => {
  updateBlockSelectionUI(selected);
  updatePropertiesPanel(selected.length === 1 ? selected[0] : null);
});

// Подписка на viewport
store.subscribe('strategyBuilder.viewport.zoomLevel', (zoom) => {
  applyZoom(zoom);
  updateZoomIndicator(zoom);
});

store.subscribe('strategyBuilder.viewport.panOffset', (offset) => {
  applyPan(offset.x, offset.y);
});

// Подписка на историю
store.computed(
  ['strategyBuilder.history.undoStack', 'strategyBuilder.history.redoStack'],
  (undo, redo) => ({ canUndo: undo.length > 0, canRedo: redo.length > 0 }),
  (state) => {
    updateToolbarButtons(state);
  }
);

// Подписка на validation
store.subscribe('strategyBuilder.validation', (validation) => {
  updateValidationUI(validation);
  updateRunButtonState(validation.isValid);
});
```

### 4. Block Library

**До:**
```javascript
const blockLibrary = {
  indicators: [...],
  entries: [...],
  exits: [...]
};
```

**После:**
```javascript
// Initialize block library in state
store.merge('strategyBuilder.library', {
  expandedCategories: ['indicators', 'entries', 'exits'],
  searchQuery: '',
  filteredBlocks: [],
  blocks: {
    indicators: [...],
    entries: [...],
    exits: [...]
  }
});

function getBlockLibrary() {
  return store.get('strategyBuilder.library.blocks') || {};
}

function getExpandedCategories() {
  return store.get('strategyBuilder.library.expandedCategories') || [];
}

function toggleCategory(category) {
  const expanded = getExpandedCategories();
  const newExpanded = expanded.includes(category)
    ? expanded.filter(c => c !== category)
    : [...expanded, category];
  store.set('strategyBuilder.library.expandedCategories', newExpanded);
}

function searchBlocks(query) {
  store.set('strategyBuilder.library.searchQuery', query);
  
  const blocks = getBlockLibrary();
  const filtered = [];
  
  for (const [category, categoryBlocks] of Object.entries(blocks)) {
    const matches = categoryBlocks.filter(block =>
      block.name.toLowerCase().includes(query.toLowerCase()) ||
      block.description?.toLowerCase().includes(query.toLowerCase())
    );
    if (matches.length > 0) {
      filtered.push({ category, blocks: matches });
    }
  }
  
  store.set('strategyBuilder.library.filteredBlocks', filtered);
}
```

### 5. Properties Panel

**До:**
```javascript
let selectedForProperties = null;

function openPropertiesPanel(block) {
  selectedForProperties = block;
  renderProperties(block);
}
```

**После:**
```javascript
function getSelectedBlockForProperties() {
  return store.get('strategyBuilder.properties.selectedBlockId');
}

function openPropertiesPanel(blockId) {
  store.merge('strategyBuilder.properties', {
    selectedBlockId: blockId,
    panelOpen: true
  });
}

function closePropertiesPanel() {
  store.set('strategyBuilder.properties.selectedBlockId', null);
  store.set('strategyBuilder.properties.panelOpen', false);
}

function updateBlockProperty(blockId, property, value) {
  const nodes = store.get('strategyBuilder.graph.nodes');
  const nodeIndex = nodes.findIndex(n => n.id === blockId);
  
  if (nodeIndex !== -1) {
    const updatedNodes = [...nodes];
    updatedNodes[nodeIndex] = {
      ...updatedNodes[nodeIndex],
      properties: {
        ...updatedNodes[nodeIndex].properties,
        [property]: value
      }
    };
    
    store.set('strategyBuilder.graph.nodes', updatedNodes);
    store.set('strategyBuilder.editing.unsavedChanges', true);
  }
}

// Подписка на изменения свойства
store.subscribe('strategyBuilder.properties.selectedBlockId', (blockId) => {
  if (blockId) {
    const nodes = store.get('strategyBuilder.graph.nodes');
    const block = nodes.find(n => n.id === blockId);
    if (block) {
      renderPropertiesPanel(block);
    }
  }
});
```

### 6. Canvas Operations

**До:**
```javascript
function handleCanvasMouseDown(e) {
  if (e.button === 1 || (e.button === 0 && e.altKey)) {
    isPanning = true;
    startPan = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
  }
}
```

**После:**
```javascript
function handleCanvasMouseDown(e) {
  if (e.button === 1 || (e.button === 0 && e.altKey)) {
    const viewport = getViewport();
    canvasState.isPanning = true;
    canvasState.startPan = {
      x: e.clientX - viewport.panOffset.x,
      y: e.clientY - viewport.panOffset.y
    };
  }
}

function handleCanvasMouseMove(e) {
  if (canvasState.isPanning) {
    const newOffset = {
      x: e.clientX - canvasState.startPan.x,
      y: e.clientY - canvasState.startPan.y
    };
    setPanOffset(newOffset.x, newOffset.y);
  }
}
```

---

## План миграции

### Этап 1: Инициализация state (30 мин)

- [ ] Создать `initializeStrategyBuilderState()`
- [ ] Определить полную структуру state
- [ ] Создать базовые геттеры/сеттеры

### Этап 2: Миграция Graph state (45 мин)

- [ ] `graphNodes` → `strategyBuilder.graph.nodes`
- [ ] `connections` → `strategyBuilder.graph.connections`
- [ ] `graphBlocks` → `strategyBuilder.graph.blocks`
- [ ] Миграция функций добавления/удаления узлов

### Этап 3: Миграция Selection state (30 мин)

- [ ] `selectedBlocks` → `strategyBuilder.blocks.selected`
- [ ] `selectedForProperties` → `strategyBuilder.properties.selectedBlockId`
- [ ] Миграция функций выделения

### Этап 4: Миграция Viewport state (30 мин)

- [ ] `zoomLevel` → `strategyBuilder.viewport.zoomLevel`
- [ ] `panOffset` → `strategyBuilder.viewport.panOffset`
- [ ] Миграция функций zoom/pan

### Этап 5: Миграция History state (45 мин)

- [ ] `undoStack` → `strategyBuilder.history.undoStack`
- [ ] `redoStack` → `strategyBuilder.history.redoStack`
- [ ] Миграция функций undo/redo

### Этап 6: Миграция Block Library (30 мин)

- [ ] `blockLibrary` → `strategyBuilder.library.blocks`
- [ ] `expandedCategories` → `strategyBuilder.library.expandedCategories`
- [ ] Миграция функций поиска

### Этап 7: Миграция Properties Panel (30 мин)

- [ ] `selectedForProperties` → `strategyBuilder.properties.selectedBlockId`
- [ ] `panelOpen` → `strategyBuilder.properties.panelOpen`
- [ ] Миграция функций обновления свойств

### Этап 8: Миграция Validation state (30 мин)

- [ ] `validationErrors` → `strategyBuilder.validation.errors`
- [ ] `validationWarnings` → `strategyBuilder.validation.warnings`
- [ ] Миграция функций валидации

### Этап 9: Миграция Toolbar state (30 мин)

- [ ] `activeTool` → `strategyBuilder.toolbar.activeTool`
- [ ] `snapEnabled` → `strategyBuilder.toolbar.snapEnabled`
- [ ] Миграция функций toolbar

### Этап 10: Подписки и реактивность (30 мин)

- [ ] Подписка на graph изменения
- [ ] Подписка на selection изменения
- [ ] Подписка на viewport изменения
- [ ] Подписка на history изменения

### Этап 11: Тесты (1 час)

- [ ] Тест добавления блока
- [ ] Тест выделения блоков
- [ ] Тест zoom/pan
- [ ] Тест undo/redo
- [ ] Тест валидации
- [ ] Интеграционный тест

---

## Глобальные переменные для миграции

| Переменная | Path в StateManager | Тип | Примечание |
|------------|---------------------|-----|------------|
| `graphNodes` | `strategyBuilder.graph.nodes` | Array | Узлы графа |
| `connections` | `strategyBuilder.graph.connections` | Array | Связи между узлами |
| `graphBlocks` | `strategyBuilder.graph.blocks` | Array | Блоки в графе |
| `selectedBlocks` | `strategyBuilder.blocks.selected` | Array | Выбранные блоки |
| `selectedForProperties` | `strategyBuilder.properties.selectedBlockId` | String/null | Блок для свойств |
| `zoomLevel` | `strategyBuilder.viewport.zoomLevel` | Number | Уровень зума |
| `panOffset` | `strategyBuilder.viewport.panOffset` | Object | Смещение canvas |
| `undoStack` | `strategyBuilder.history.undoStack` | Array | История undo |
| `redoStack` | `strategyBuilder.history.redoStack` | Array | История redo |
| `blockLibrary` | `strategyBuilder.library.blocks` | Object | Библиотека блоков |
| `expandedCategories` | `strategyBuilder.library.expandedCategories` | Array | Развёрнутые категории |
| `validationErrors` | `strategyBuilder.validation.errors` | Array | Ошибки валидации |
| `validationWarnings` | `strategyBuilder.validation.warnings` | Array | Предупреждения |
| `activeTool` | `strategyBuilder.toolbar.activeTool` | String | Активный инструмент |
| `snapEnabled` | `strategyBuilder.toolbar.snapEnabled` | Boolean | Привязка к сетке |
| `gridVisible` | `strategyBuilder.canvas.showGrid` | Boolean | Показывать сетку |
| `gridSize` | `strategyBuilder.canvas.gridSize` | Number | Размер сетки |
| `unsavedChanges` | `strategyBuilder.editing.unsavedChanges` | Boolean | Есть несохранённые изменения |

---

## Критерии приёмки

- [ ] Все глобальные переменные заменены
- [ ] Graph rendering работает через state
- [ ] Selection работает через state
- [ ] Zoom/Pan работают через state
- [ ] Undo/Redo работают через state
- [ ] Properties panel работает через state
- [ ] Validation работает через state
- [ ] Block library работает через state
- [ ] Тесты проходят (>80% coverage)
- [ ] Нет регрессий в функциональности

---

## Проблемы и решения

### Проблема 1: Circular references в graph

**Решение:** Использовать IDs для связей вместо прямых references. StateManager._deepClone обрабатывает circular refs.

### Проблема 2: Производительность при частых обновлениях

**Решение:** Использовать `store.batch()` для групповых обновлений. Debounce для частых операций (pan, zoom).

### Проблема 3: Canvas state (isPanning, isDragging)

**Решение:** Хранить временное состояние в closure, а не в StateManager. StateManager только для персистентного state.

### Проблема 4: Event listeners и cleanup

**Решение:** Подписки автоматически отписываются при удалении компонентов. Использовать returned unsubscribe функции.

---

## Паттерны миграции

### Паттерн 1: Поэтапная миграция

```javascript
// 1. Создать геттер/сеттер
function getSelectedBlocks() {
  return store.get('strategyBuilder.blocks.selected') || [];
}

// 2. Заменить прямое использование
// До: selectedBlocks.push(block)
// После: setSelectedBlocks([...getSelectedBlocks(), block])

// 3. Удалить глобальную переменную
// let selectedBlocks = []; // Удалить
```

### Паттерн 2: Обёртывание функций

```javascript
// Создать wrapper вокруг старой функции
function oldAddBlock(block) {
  // Старая логика
  graphNodes.push(block);
  renderGraph();
}

// Обернуть в новую
function addBlock(block) {
  const nodes = store.get('strategyBuilder.graph.nodes');
  store.set('strategyBuilder.graph.nodes', [...nodes, block]);
  // Старая функция вызовется через subscribe
}
```

### Паттерн 3: Двусторонняя синхронизация

```javascript
// Временно поддерживать оба state
function syncState() {
  // Sync from old to new
  store.set('strategyBuilder.graph.nodes', graphNodes);
  
  // Subscribe to update old from new
  store.subscribe('strategyBuilder.graph.nodes', (nodes) => {
    graphNodes = nodes;
  });
}
```

---

## Следующий шаг

[Шаг 3: Интеграционные тесты](./step-3-integration-tests.md)

---

*План создан: 2026-02-26*
