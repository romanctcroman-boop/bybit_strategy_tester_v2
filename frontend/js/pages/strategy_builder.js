/**
 * 📄 Strategy Builder Page JavaScript
 *
 * Page-specific scripts for strategy_builder.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 2.0.0
 * @date 2026-02-26
 * @migration P0-3: StateManager integration with legacy shim-sync pattern
 */

/* eslint-disable indent */

// Import advanced blocks (P2-6)
import { createMLBlocksModule as _createMLBlocksModule } from '../components/MLBlocksModule.js';
import { createSentimentBlocksModule as _createSentimentBlocksModule } from '../components/SentimentBlocksModule.js';
import { createOrderFlowBlocksModule as _createOrderFlowBlocksModule } from '../components/OrderFlowBlocksModule.js';
import { formatDate } from '../utils.js';
import { updateLeverageRiskForElements } from '../shared/leverageManager.js';
import { blockLibrary } from '../strategy_builder/blockLibrary.js';
import { createSymbolSyncModule } from '../strategy_builder/SymbolSyncModule.js';

// Import WebSocket validation module
import * as wsValidation from './strategy_builder_ws.js';

// Import StateManager
import { getStore } from '../core/StateManager.js';
import { initState } from '../core/state-helpers.js';

// Import BacktestModule — extracted during P0-1 refactoring
// Only the symbols actually used directly in strategy_builder.js are imported;
// the rest live inside BacktestModule.js and are consumed via createBacktestModule().
import {
  normalizeTimeframeForDropdown,
  getNoTradeDaysFromUI,
  setNoTradeDaysInUI,
  createBacktestModule
} from '../components/BacktestModule.js';

// Import AiBuildModule — extracted during P0-1 refactoring
import { createAiBuildModule } from '../components/AiBuildModule.js';
import { createMyStrategiesModule } from '../components/MyStrategiesModule.js';
import { createConnectionsModule } from '../components/ConnectionsModule.js';
import { createUndoRedoModule } from '../components/UndoRedoModule.js';
import { createValidateModule } from '../components/ValidateModule.js';
import { createSaveLoadModule } from '../components/SaveLoadModule.js';

// API Base URL - must be defined early before any usage
const API_BASE = '/api/v1';

// Build version marker — visible in DevTools console on load
console.log('%c[Strategy Builder] v20260225f LOADED — modal branch active', 'color:#0f0;font-weight:bold');

// Forward declaration for checkSymbolDataForProperties (initialized later after runCheckSymbolDataForProperties is defined)
let checkSymbolDataForProperties = null;

/** SymbolSyncModule singleton — initialized in initializeStrategyBuilder(). */
let symbolSync = null;

// Global loading indicator functions
function showGlobalLoading(text = 'Loading...') {
  const indicator = document.getElementById('globalLoadingIndicator');
  if (indicator) {
    const textEl = indicator.querySelector('.loading-text');
    if (textEl) textEl.textContent = text;
    indicator.classList.remove('hidden');
  }
}

function hideGlobalLoading() {
  const indicator = document.getElementById('globalLoadingIndicator');
  if (indicator) {
    indicator.classList.add('hidden');
  }
}

function _updateGlobalLoadingText(text) {
  const indicator = document.getElementById('globalLoadingIndicator');
  if (indicator) {
    const textEl = indicator.querySelector('.loading-text');
    if (textEl) textEl.textContent = text;
  }
}

/**
 * Add mouse wheel scroll support to number inputs
 * @param {HTMLInputElement} input - The number input element
 * @param {Function} [onChangeCallback] - Optional callback after value change
 */
function addWheelScrollToInput(input, onChangeCallback = null) {
  if (!input || input.type !== 'number' || input.dataset.wheelEnabled) return;

  input.dataset.wheelEnabled = 'true';
  input.addEventListener('wheel', (e) => {
    if (input.disabled) return;
    e.preventDefault();
    e.stopPropagation();

    const step = parseFloat(input.step) || 1;
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);
    const delta = e.deltaY < 0 ? step : -step;

    let newValue = (parseFloat(input.value) || 0) + delta;
    if (!isNaN(min)) newValue = Math.max(min, newValue);
    if (!isNaN(max)) newValue = Math.min(max, newValue);

    // Round to step precision
    const decimals = (step.toString().split('.')[1] || '').length;
    input.value = newValue.toFixed(decimals);

    // Trigger change event
    input.dispatchEvent(new Event('change', { bubbles: true }));

    if (onChangeCallback) onChangeCallback(input);
  }, { passive: false });
}

/**
 * Add wheel scroll to all number inputs within a container
 * @param {HTMLElement} container - Container element to search within
 */
function enableWheelScrollForNumberInputs(container) {
  if (!container) return;
  container.querySelectorAll('input[type="number"]').forEach(input => {
    addWheelScrollToInput(input);
  });
}


// ============================================================
// P0-3 StateManager Integration — Strategy Builder
// ============================================================
// Pattern: "Legacy Shim Sync"
//   - Legacy module-level variables remain as shims (zero regression risk)
//   - store.subscribe() keeps shims updated when store changes (store → shim)
//   - Setter functions push mutations back to store (shim → store)
//   - All existing code continues to read/write the same variable names
// ============================================================

/**
 * Initialize all strategyBuilder state paths in the store.
 * Called at the very beginning of initializeStrategyBuilder().
 */
function initializeStrategyBuilderState() {
  const store = getStore();
  if (!store) return;

  initState(store, 'strategyBuilder', {
    // Graph
    graph: {
      blocks: [],
      connections: []
    },
    // Selection
    selection: {
      selectedBlockId: null,
      selectedBlockIds: []
    },
    // Viewport / canvas
    viewport: {
      zoom: 1,
      isDragging: false,
      dragOffset: { x: 0, y: 0 },
      isMarqueeSelecting: false,
      marqueeStart: { x: 0, y: 0 },
      marqueeElement: null
    },
    // History (undo/redo)
    history: {
      lastAutoSavePayload: null,
      skipNextAutoSave: false
    },
    // Connecting wires
    connecting: {
      isConnecting: false,
      connectionStart: null,
      tempLine: null
    },
    // Group drag
    groupDrag: {
      isGroupDragging: false,
      groupDragOffsets: {}
    },
    // Misc / UI
    ui: {
      refreshDunnahBasePanel: null,
      quickAddDialog: null,
      currentBacktestResults: null
    },
    // Symbol sync state
    sync: {
      currentSyncAbortController: null,
      currentSyncSymbol: null,
      currentSyncStartTime: 0
    }
  });

  _setupStrategyBuilderShimSync();
}

// ----------------------------------------------------------------
// Getters & Setters
// ----------------------------------------------------------------

/* eslint-disable no-unused-vars */

// Graph
function getSBBlocks() { const s = getStore(); return s ? s.get('strategyBuilder.graph.blocks') ?? [] : strategyBlocks; }
function setSBBlocks(v) { const s = getStore(); if (s) s.set('strategyBuilder.graph.blocks', v); }
function getSBConnections() { const s = getStore(); return s ? s.get('strategyBuilder.graph.connections') ?? [] : connections; }
function setSBConnections(v) { const s = getStore(); if (s) s.set('strategyBuilder.graph.connections', v); }

// Selection
function getSBSelectedBlockId() { const s = getStore(); return s ? s.get('strategyBuilder.selection.selectedBlockId') : selectedBlockId; }
function setSBSelectedBlockId(v) { const s = getStore(); if (s) s.set('strategyBuilder.selection.selectedBlockId', v); }
function getSBSelectedBlockIds() { const s = getStore(); return s ? s.get('strategyBuilder.selection.selectedBlockIds') ?? [] : selectedBlockIds; }
function setSBSelectedBlockIds(v) { const s = getStore(); if (s) s.set('strategyBuilder.selection.selectedBlockIds', v); }

// Viewport
function getSBZoom() { const s = getStore(); return s ? s.get('strategyBuilder.viewport.zoom') ?? 1 : zoom; }
function setSBZoom(v) { const s = getStore(); if (s) s.set('strategyBuilder.viewport.zoom', v); }
function getSBIsDragging() { const s = getStore(); return s ? s.get('strategyBuilder.viewport.isDragging') ?? false : isDragging; }
function setSBIsDragging(v) { const s = getStore(); if (s) s.set('strategyBuilder.viewport.isDragging', v); }
function getSBDragOffset() { const s = getStore(); return s ? s.get('strategyBuilder.viewport.dragOffset') ?? { x: 0, y: 0 } : dragOffset; }
function setSBDragOffset(v) { const s = getStore(); if (s) s.set('strategyBuilder.viewport.dragOffset', v); }
function getSBIsMarqueeSelecting() { const s = getStore(); return s ? s.get('strategyBuilder.viewport.isMarqueeSelecting') ?? false : isMarqueeSelecting; }
function setSBIsMarqueeSelecting(v) { const s = getStore(); if (s) s.set('strategyBuilder.viewport.isMarqueeSelecting', v); }
function getSBMarqueeStart() { const s = getStore(); return s ? s.get('strategyBuilder.viewport.marqueeStart') ?? { x: 0, y: 0 } : marqueeStart; }
function setSBMarqueeStart(v) { const s = getStore(); if (s) s.set('strategyBuilder.viewport.marqueeStart', v); }

// History
function getSBLastAutoSavePayload() { const s = getStore(); return s ? s.get('strategyBuilder.history.lastAutoSavePayload') : lastAutoSavePayload; }
function setSBLastAutoSavePayload(v) { const s = getStore(); if (s) s.set('strategyBuilder.history.lastAutoSavePayload', v); }
function getSBSkipNextAutoSave() { const s = getStore(); return s ? s.get('strategyBuilder.history.skipNextAutoSave') ?? false : skipNextAutoSave; }
function setSBSkipNextAutoSave(v) { const s = getStore(); if (s) s.set('strategyBuilder.history.skipNextAutoSave', v); }

// Connecting
function getSBIsConnecting() { const s = getStore(); return s ? s.get('strategyBuilder.connecting.isConnecting') ?? false : isConnecting; }
function setSBIsConnecting(v) { const s = getStore(); if (s) s.set('strategyBuilder.connecting.isConnecting', v); }
function getSBConnectionStart() { const s = getStore(); return s ? s.get('strategyBuilder.connecting.connectionStart') : connectionStart; }
function setSBConnectionStart(v) { const s = getStore(); if (s) s.set('strategyBuilder.connecting.connectionStart', v); }

// Group drag
function getSBIsGroupDragging() { const s = getStore(); return s ? s.get('strategyBuilder.groupDrag.isGroupDragging') ?? false : isGroupDragging; }
function setSBIsGroupDragging(v) { const s = getStore(); if (s) s.set('strategyBuilder.groupDrag.isGroupDragging', v); }
function getSBGroupDragOffsets() { const s = getStore(); return s ? s.get('strategyBuilder.groupDrag.groupDragOffsets') ?? {} : groupDragOffsets; }
function setSBGroupDragOffsets(v) { const s = getStore(); if (s) s.set('strategyBuilder.groupDrag.groupDragOffsets', v); }

// Sync
function getSBCurrentSyncSymbol() { const s = getStore(); return s ? s.get('strategyBuilder.sync.currentSyncSymbol') : currentSyncSymbol; }
function setSBCurrentSyncSymbol(v) { const s = getStore(); if (s) s.set('strategyBuilder.sync.currentSyncSymbol', v); }
function getSBCurrentSyncStartTime() { const s = getStore(); return s ? s.get('strategyBuilder.sync.currentSyncStartTime') ?? 0 : currentSyncStartTime; }
function setSBCurrentSyncStartTime(v) { const s = getStore(); if (s) s.set('strategyBuilder.sync.currentSyncStartTime', v); }

// UI misc
function getSBCurrentBacktestResults() { const s = getStore(); return s ? s.get('strategyBuilder.ui.currentBacktestResults') : currentBacktestResults; }
function setSBCurrentBacktestResults(v) { const s = getStore(); if (s) s.set('strategyBuilder.ui.currentBacktestResults', v); }

/* eslint-enable no-unused-vars */

/**
 * Wire store.subscribe() so that store updates automatically propagate to
 * the legacy shim variables (store → shim direction).
 * Mutation sites call setter functions to push the other way (shim → store).
 */
function _setupStrategyBuilderShimSync() {
  const store = getStore();
  if (!store) return;

  store.subscribe('strategyBuilder.graph.blocks', (v) => { strategyBlocks.length = 0; if (Array.isArray(v)) strategyBlocks.push(...v); });
  store.subscribe('strategyBuilder.graph.connections', (v) => { connections.length = 0; if (Array.isArray(v)) connections.push(...v); });
  store.subscribe('strategyBuilder.selection.selectedBlockId', (v) => { selectedBlockId = v ?? null; });
  store.subscribe('strategyBuilder.selection.selectedBlockIds', (v) => { selectedBlockIds = Array.isArray(v) ? v : []; });
  store.subscribe('strategyBuilder.viewport.zoom', (v) => { zoom = v ?? 1; });
  store.subscribe('strategyBuilder.viewport.isDragging', (v) => { isDragging = v ?? false; });
  store.subscribe('strategyBuilder.viewport.dragOffset', (v) => { if (v) { dragOffset.x = v.x; dragOffset.y = v.y; } });
  store.subscribe('strategyBuilder.viewport.isMarqueeSelecting', (v) => { isMarqueeSelecting = v ?? false; });
  store.subscribe('strategyBuilder.viewport.marqueeStart', (v) => { if (v) { marqueeStart.x = v.x; marqueeStart.y = v.y; } });
  store.subscribe('strategyBuilder.history.lastAutoSavePayload', (v) => { lastAutoSavePayload = v ?? null; });
  store.subscribe('strategyBuilder.history.skipNextAutoSave', (v) => { skipNextAutoSave = v ?? false; });
  store.subscribe('strategyBuilder.connecting.isConnecting', (v) => { isConnecting = v ?? false; });
  store.subscribe('strategyBuilder.connecting.connectionStart', (v) => { connectionStart = v ?? null; });
  store.subscribe('strategyBuilder.groupDrag.isGroupDragging', (v) => { isGroupDragging = v ?? false; });
  store.subscribe('strategyBuilder.groupDrag.groupDragOffsets', (v) => { if (v) Object.assign(groupDragOffsets, v); });
  store.subscribe('strategyBuilder.sync.currentSyncSymbol', (v) => { currentSyncSymbol = v ?? null; });
  store.subscribe('strategyBuilder.sync.currentSyncStartTime', (v) => { currentSyncStartTime = v ?? 0; });
  store.subscribe('strategyBuilder.ui.currentBacktestResults', (v) => { currentBacktestResults = v ?? null; });

  // Seed arrays/objects into store (initial values from const declarations)
  // Note: connections/undoStack/redoStack are const [] — they are the same objects in both shim and store
  const s = store;
  s.set('strategyBuilder.graph.blocks', strategyBlocks);
  s.set('strategyBuilder.graph.connections', connections);
}

// ----------------------------------------------------------------
// State
// ----------------------------------------------------------------

// State
let strategyBlocks = [];
// Expose to non-module scripts (optimization_config_panel.js, optimization_panels.js)
// Note: the live StateManager getter is defined at the bottom of this file.
const connections = [];
// eslint-disable-next-line no-unused-vars
const undoStack = [];  // Managed by UndoRedoModule — kept for store-subscriber compatibility
// eslint-disable-next-line no-unused-vars
const redoStack = [];  // Managed by UndoRedoModule — kept for store-subscriber compatibility
// eslint-disable-next-line no-unused-vars
const MAX_UNDO_HISTORY = 50;  // Canonical value lives in UndoRedoModule.js
let lastAutoSavePayload = null;
let _eventListenersInitialized = false; // Must be declared before initializeStrategyBuilder() call
const AUTOSAVE_INTERVAL_MS = 30000;
const STORAGE_KEY_PREFIX = 'strategy_builder_draft_';
let skipNextAutoSave = false; // Flag to skip autosave after reset
let selectedBlockId = null;
let selectedBlockIds = []; // Multi-selection array
let zoom = 1;
let isDragging = false;
let dragOffset = { x: 0, y: 0 };
let currentBacktestResults = null; // Legacy shim — mirrored from store (strategyBuilder.ui.currentBacktestResults)
let currentSyncSymbol = null;      // Legacy shim — mirrored from store (strategyBuilder.sync.currentSyncSymbol)
let currentSyncStartTime = 0;      // Legacy shim — mirrored from store (strategyBuilder.sync.currentSyncStartTime)
let _backtestModule = null;        // Initialized in initializeStrategyBuilder() via _initBacktestModule()
let _aiModule = null;              // Initialized in initializeStrategyBuilder() via _initAiBuildModule()
let _myStrategiesModule = null;    // Initialized in initializeStrategyBuilder() via _initMyStrategiesModule()
let _connectionsModule = null;     // Initialized in initializeStrategyBuilder() via _initConnectionsModule()
let _undoRedoModule = null;        // Initialized in initializeStrategyBuilder() via _initUndoRedoModule()
const _btcSyncCache = {};          // Cache for BTC source sync per node (separate from SymbolSyncModule's cache)
let _validateModule = null;        // Initialized in initializeStrategyBuilder() via _initValidateModule()
let _saveLoadModule = null;        // Initialized in initializeStrategyBuilder() via _initSaveLoadModule()

// Connection state — kept as module-level vars for store-subscriber fallback (getSBIsConnecting etc.)
let isConnecting = false;
let connectionStart = null;
// eslint-disable-next-line no-unused-vars
const _tempLine = null; // Reserved for store-sync extension

// Marquee selection variables
let isMarqueeSelecting = false;
let marqueeStart = { x: 0, y: 0 };
let marqueeElement = null;

// ============================================
// LOCAL STORAGE PERSISTENCE
// ============================================

/**
 * Try to load strategy from localStorage
 * @param {string} strategyId - Strategy ID or 'draft'
 * @returns {boolean} - True if loaded successfully
 */
function tryLoadFromLocalStorage(strategyId) {
  try {
    const key = STORAGE_KEY_PREFIX + strategyId;
    const saved = window.localStorage.getItem(key);

    if (!saved) {
      console.log('[Strategy Builder] No saved draft found in localStorage');
      return false;
    }

    const data = JSON.parse(saved);
    console.log('[Strategy Builder] Found saved draft:', {
      blocks: data.blocks?.length || 0,
      connections: data.connections?.length || 0
    });

    // Don't restore if it's just the initial clean state (only Strategy node, no connections)
    const hasOnlyStrategyNode = data.blocks?.length === 1 &&
      (data.blocks[0].isMain || data.blocks[0].type === 'strategy');
    const hasNoConnections = !data.connections || data.connections.length === 0;

    if (hasOnlyStrategyNode && hasNoConnections) {
      console.log('[Strategy Builder] Skipping restore - saved state is clean initial state');
      // Remove this clean state from localStorage
      window.localStorage.removeItem(key);
      return false;
    }

    // Restore blocks
    if (data.blocks && Array.isArray(data.blocks)) {
      strategyBlocks.length = 0; // Clear existing

      // First, ensure main Strategy node exists
      const mainBlock = data.blocks.find(b => b.isMain || b.id === 'main_strategy');
      if (mainBlock) {
        strategyBlocks.push({
          id: mainBlock.id || 'main_strategy',
          type: mainBlock.type || 'strategy',
          category: 'main',
          name: mainBlock.name || 'Strategy',
          icon: mainBlock.icon || 'diagram-3',
          x: mainBlock.x || 800,
          y: mainBlock.y || 300,
          isMain: true,
          params: mainBlock.params || {}
        });
      } else {
        // Create default main node
        createMainStrategyNode();
      }

      // Add other blocks
      data.blocks.forEach(block => {
        if (!block.isMain && block.id !== 'main_strategy') {
          strategyBlocks.push({
            id: block.id,
            type: block.type,
            category: block.category || 'indicator',
            name: block.name || block.type,
            icon: block.icon || 'box',
            x: block.x || 100,
            y: block.y || 100,
            params: block.params || {},
            optimizationParams: block.optimizationParams || {}
          });
        }
      });
    }

    // Restore connections
    if (data.connections && Array.isArray(data.connections)) {
      connections.length = 0; // Clear existing
      data.connections.forEach(conn => {
        if (conn.source && conn.target) {
          connections.push({
            id: conn.id || `conn_restored_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
            source: conn.source,
            target: conn.target,
            type: conn.type || 'data'
          });
        }
      });
      // Normalize to ensure canonical format (fills missing id/type/portId)
      normalizeAllConnections();
    }
    setSBBlocks(strategyBlocks);
    setSBConnections(connections);

    // Restore UI state if available
    if (data.uiState) {
      // Restore zoom
      if (data.uiState.zoom && typeof data.uiState.zoom === 'number') {
        zoom = data.uiState.zoom;
        setSBZoom(zoom);
        // updateZoom will be called after DOM is ready
      }

      // Restore panel values
      if (data.uiState.strategyName) {
        const nameInput = document.getElementById('strategyName');
        if (nameInput) nameInput.value = data.uiState.strategyName;
      }
    }

    console.log('[Strategy Builder] Restored from localStorage:', {
      blocks: strategyBlocks.length,
      connections: connections.length
    });

    // Clear any stale multi-selection state that may have been serialized in localStorage
    clearMultiSelection();

    // Show notification
    showRestoreNotification();

    return true;
  } catch (err) {
    console.warn('[Strategy Builder] Failed to load from localStorage:', err);
    return false;
  }
}

/**
 * Show notification that draft was restored
 */
function showRestoreNotification() {
  const notification = document.createElement('div');
  notification.className = 'restore-notification';
  notification.innerHTML = `
    <i class="bi bi-clock-history"></i>
    <span>Черновик восстановлен</span>
    <button class="restore-notification-close" title="Закрыть">&times;</button>
  `;
  notification.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(135deg, #1a1f2e 0%, #252b3d 100%);
    border: 1px solid rgba(88, 166, 255, 0.3);
    border-radius: 8px;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    color: #58a6ff;
    font-size: 14px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    z-index: 10000;
    animation: slideUp 0.3s ease;
  `;

  // Add animation keyframes
  if (!document.getElementById('restore-notification-styles')) {
    const style = document.createElement('style');
    style.id = 'restore-notification-styles';
    style.textContent = `
      @keyframes slideUp {
        from { opacity: 0; transform: translateX(-50%) translateY(20px); }
        to { opacity: 1; transform: translateX(-50%) translateY(0); }
      }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(notification);

  // Close button handler
  notification.querySelector('.restore-notification-close').addEventListener('click', () => {
    notification.remove();
  });

  // Auto-remove after 4 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.style.opacity = '0';
      notification.style.transition = 'opacity 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }
  }, 4000);
}

/**
 * Clear saved draft from localStorage
 * @param {string} strategyId - Strategy ID or 'draft'. If null, clears ALL drafts.
 */
function clearLocalStorageDraft(strategyId) {
  try {
    if (strategyId) {
      // Clear specific draft
      const key = STORAGE_KEY_PREFIX + strategyId;
      window.localStorage.removeItem(key);
      console.log('[Strategy Builder] Cleared localStorage draft:', key);
    } else {
      // Clear ALL strategy builder drafts
      const keysToRemove = [];
      for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith(STORAGE_KEY_PREFIX)) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => {
        window.localStorage.removeItem(key);
        console.log('[Strategy Builder] Removed:', key);
      });
      console.log('[Strategy Builder] Cleared ALL localStorage drafts:', keysToRemove.length);
    }
  } catch (err) {
    console.warn('[Strategy Builder] Failed to clear localStorage:', err);
  }
}

/**
 * Clear all blocks, connections and reset to default state
 * Clears localStorage and resets all parameters
 */
function clearAllAndReset() {
  console.log('[Strategy Builder] clearAllAndReset() called');

  // Ask for confirmation with more visible dialog
  const userConfirmed = window.confirm('⚠️ ОЧИСТИТЬ ВСЁ?\n\n• Все блоки будут удалены\n• Все соединения будут удалены\n• Настройки сбросятся\n• Сохранённый черновик удалится\n\nНажмите OK для подтверждения');

  if (!userConfirmed) {
    console.log('[Strategy Builder] User cancelled reset');
    return;
  }

  console.log('[Strategy Builder] User confirmed. Clearing all and resetting...');

  try {
    // FIRST: Set flag to skip next autosave
    skipNextAutoSave = true;
    setSBSkipNextAutoSave(true);

    // Clear last autosave payload to prevent immediate re-save
    lastAutoSavePayload = null;
    setSBLastAutoSavePayload(null);

    // Clear ALL localStorage drafts (pass null to clear all)
    clearLocalStorageDraft(null);

    // Also explicitly clear the 'draft' key just in case
    try {
      window.localStorage.removeItem(STORAGE_KEY_PREFIX + 'draft');
      console.log('[Strategy Builder] Explicitly removed draft key');
    } catch (e) {
      console.warn('[Strategy Builder] Could not remove draft key:', e);
    }

    // Clear all blocks
    strategyBlocks.length = 0;
    setSBBlocks(strategyBlocks);

    // Clear all connections
    connections.length = 0;
    setSBConnections(connections);

    // Clear undo/redo history
    undoStack.length = 0;
    redoStack.length = 0;

    // Clear selection
    selectedBlockId = null;
    selectedBlockIds = [];

    // Reset zoom
    zoom = 1;
    updateZoom();

    // Recreate main Strategy node at default position
    createMainStrategyNode();

    // Reset form values to defaults
    resetFormToDefaults();

    // Update undo/redo buttons
    updateUndoRedoButtons();

    // Re-render (renderBlocks calls renderConnections internally)
    renderBlocks();

    // Show notification
    showNotification('Всё очищено. Начните заново!', 'success');

    console.log('[Strategy Builder] Reset complete. localStorage cleared.');

    // Log current localStorage state for debugging
    const remainingKeys = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (key && key.startsWith('strategy_builder')) {
        remainingKeys.push(key);
      }
    }
    console.log('[Strategy Builder] Remaining strategy keys:', remainingKeys);

  } catch (err) {
    console.error('[Strategy Builder] Error during reset:', err);
    showNotification('Ошибка при очистке: ' + err.message, 'error');
  }
}

/**
 * Reset all form inputs to default values
 */
function resetFormToDefaults() {
  // Strategy name
  const nameEl = document.getElementById('strategyName');
  if (nameEl) nameEl.value = 'New Strategy';

  // Symbol
  const symbolEl = document.getElementById('strategySymbol');
  if (symbolEl) symbolEl.value = '';
  const backtestSymbolEl = document.getElementById('backtestSymbol');
  if (backtestSymbolEl) backtestSymbolEl.value = '';

  // Timeframe
  const timeframeEl = document.getElementById('strategyTimeframe');
  if (timeframeEl) timeframeEl.value = '15';

  // Market type
  const marketTypeEl = document.getElementById('builderMarketType');
  if (marketTypeEl) marketTypeEl.value = 'linear';

  // Direction
  const directionEl = document.getElementById('builderDirection');
  if (directionEl) directionEl.value = 'both';

  // Capital
  const capitalEl = document.getElementById('backtestCapital');
  if (capitalEl) capitalEl.value = '10000';

  // Position size
  const positionSizeTypeEl = document.getElementById('backtestPositionSizeType');
  if (positionSizeTypeEl) positionSizeTypeEl.value = 'percent';
  const positionSizeEl = document.getElementById('backtestPositionSize');
  if (positionSizeEl) positionSizeEl.value = '10';

  // Commission — default by market type (Bybit taker fees, market orders)
  const commissionEl = document.getElementById('backtestCommission');
  if (commissionEl) {
    const marketType = document.getElementById('builderMarketType')?.value || 'linear';
    commissionEl.value = marketType === 'spot' ? '0.1' : '0.055';
  }

  // Slippage (TV parity: 0% default)
  const slippageEl = document.getElementById('backtestSlippage');
  if (slippageEl) slippageEl.value = '0.00';

  // Leverage
  const leverageEl = document.getElementById('backtestLeverage');
  if (leverageEl) leverageEl.value = '10';
  const leverageRangeEl = document.getElementById('backtestLeverageRange');
  if (leverageRangeEl) leverageRangeEl.value = '10';
  updateBacktestLeverageDisplay(10);

  // Start/End dates — defaults for new (unsaved) strategies
  const startDateEl = document.getElementById('backtestStartDate');
  if (startDateEl) startDateEl.value = '2025-01-01';
  const endDateEl = document.getElementById('backtestEndDate');
  if (endDateEl) {
    // Default to 2030-01-01 — the engine clamps to current datetime if this
    // date is in the future, so the user never needs to update it manually.
    endDateEl.value = '2030-01-01';
  }

  // Clear no-trade days checkboxes
  document.querySelectorAll('.no-trade-day-checkbox').forEach(cb => {
    cb.checked = false;
  });

  // Update UI displays
  syncStrategyNameDisplay();
  updateBacktestPositionSizeInput();
}

// Group dragging variables
let isGroupDragging = false;
let groupDragOffsets = {}; // blockId -> {x, y} offset from mouse

// refreshDunnahBasePanel — now managed internally by SymbolSyncModule.initDunnahBasePanel()

// Show a dismissible banner when backend is unreachable or page opened from file
function showBackendConnectionBanner(message) {
  const existing = document.getElementById('strategy-builder-backend-banner');
  if (existing) return;
  const banner = document.createElement('div');
  banner.id = 'strategy-builder-backend-banner';
  banner.setAttribute('role', 'alert');
  banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#dc3545;color:#fff;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,0.2);';
  banner.innerHTML = `<span>${escapeHtml(message)}</span><a href="http://localhost:8000/frontend/strategy-builder.html" style="color:#fff;text-decoration:underline;white-space:nowrap;">Открыть с сервера</a><button type="button" aria-label="Закрыть" style="background:transparent;border:none;color:#fff;cursor:pointer;padding:4px;font-size:18px;">&times;</button>`;
  banner.querySelector('button').addEventListener('click', () => banner.remove());
  document.body.prepend(banner);
}

// Initialize - handle both cases: before and after DOMContentLoaded
function initializeStrategyBuilder() {
  console.log('[Strategy Builder] Initializing...');

  // P0-3: Initialize StateManager state paths + legacy shim sync
  initializeStrategyBuilderState();

  // P0-1: Initialize extracted BacktestModule
  _initBacktestModule();

  // P0-1: Initialize extracted AiBuildModule
  _initAiBuildModule();

  // P0-1: Initialize extracted MyStrategiesModule
  _initMyStrategiesModule();

  // P0-1: Initialize extracted SaveLoadModule (first — others depend on saveStrategy)
  _initSaveLoadModule();

  // P0-1: Initialize extracted ValidateModule (second — UndoRedo depends on validateStrategy)
  _initValidateModule();

  // P0-1: Initialize extracted UndoRedoModule (third — depends on validateStrategy delegate)
  _initUndoRedoModule();

  // P0-1: Initialize extracted ConnectionsModule
  _initConnectionsModule();

  try {
    // If opened from file://, API requests won't reach backend - show hint
    if (window.location.protocol === 'file:') {
      showBackendConnectionBanner('Страница открыта с диска. Для связи с бэкендом откройте её с сервера.');
    } else {
      // Quick connectivity check (same-origin)
      fetch('/healthz', { method: 'GET', cache: 'no-store' })
        .then((res) => { if (!res.ok) throw new Error('health check failed'); })
        .catch(() => {
          showBackendConnectionBanner('Нет связи с бэкендом. Запустите start_all.ps1 и откройте страницу с сервера.');
        });
    }

    // Check if strategy ID in URL
    const urlParams = new URLSearchParams(window.location.search);
    const strategyId = urlParams.get('id');

    if (strategyId) {
      const btnVersions = document.getElementById('btnVersions');
      if (btnVersions) btnVersions.style.display = '';
      console.log('[Strategy Builder] Loading strategy:', strategyId);
      // Load existing strategy
      loadStrategy(strategyId).then(() => {
        // After loading, ensure main node exists
        const mainNode = strategyBlocks.find((b) => b.isMain);
        if (!mainNode) {
          createMainStrategyNode();
        }
        // Ensure buttons are enabled after strategy load (symbol is populated)
        updateRunButtonsState();
        console.log('[Strategy Builder] Strategy loaded');
      }).catch((err) => {
        console.error('[Strategy Builder] Error loading strategy:', err);
        // Try to load from localStorage draft
        if (!tryLoadFromLocalStorage(strategyId)) {
          createMainStrategyNode();
        }
      });
    } else {
      // Create new strategy - try to restore from localStorage first
      console.log('[Strategy Builder] Creating new strategy');
      if (!tryLoadFromLocalStorage('draft')) {
        createMainStrategyNode();
      }
    }

    console.log('[Strategy Builder] Rendering block library...');
    renderBlockLibrary();

    console.log('[Strategy Builder] Setting up event listeners...');
    setupEventListeners();
    syncStrategyNameDisplay();

    // Initialize SymbolSyncModule (extracted Phase 5 refactor)
    symbolSync = createSymbolSyncModule({
      API_BASE,
      escapeHtml,
      showGlobalLoading,
      hideGlobalLoading,
      updateRunButtonsState
    });
    checkSymbolDataForProperties = symbolSync.checkSymbolDataForProperties;

    symbolSync.initSymbolPicker();
    symbolSync.initDunnahBasePanel();
    // Тикеры предзагружаются в initSymbolPicker — дублирующий fetchBybitSymbols здесь убран

    console.log('[Strategy Builder] Initializing connection system...');
    initConnectionSystem();

    console.log('[Strategy Builder] Rendering blocks...');
    renderBlocks();

    // Properties: боковые закладки, первая панель активна по умолчанию

    updateBacktestPositionSizeInput();
    updateBacktestLeverageDisplay(document.getElementById('backtestLeverageRange')?.value || document.getElementById('backtestLeverage')?.value || 10);
    updateBacktestLeverageRisk();

    // Enable mouse wheel scroll for all number inputs in Properties panel
    const propertiesPanel = document.getElementById('propertiesPanel');
    if (propertiesPanel) {
      enableWheelScrollForNumberInputs(propertiesPanel);
      console.log('[Strategy Builder] Wheel scroll enabled for Properties number inputs');
    }

    // Проверка данных БД только при смене Symbol/TF/Тип рынка, не при открытии блока Properties

    // Periodic autosave to localStorage and server
    setInterval(autoSaveStrategy, AUTOSAVE_INTERVAL_MS);

    // Initialize undo/redo button states
    updateUndoRedoButtons();

    // Set initial state of action buttons (disabled until symbol is selected)
    updateRunButtonsState();

    console.log('[Strategy Builder] Initialization complete!');
  } catch (error) {
    console.error('[Strategy Builder] Initialization error:', error);
    // Show the actual error message as a non-blocking banner (not alert) so the page stays usable
    const msg = error && error.message ? error.message : String(error);
    const stack = error && error.stack ? error.stack.split('\n').slice(1, 4).join(' | ') : '';
    // Use the existing banner function if available, otherwise create one
    const bannerMsg = `Init error: ${msg}${stack ? ' — ' + stack : ''}`;
    if (typeof showBackendConnectionBanner === 'function') {
      showBackendConnectionBanner('⚠ ' + bannerMsg);
    } else {
      console.error('[Strategy Builder] Full error:', error);
    }
  }
}

// Run initialization - handle both cases: before and after DOMContentLoaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeStrategyBuilder);
} else {
  // DOM already loaded (module executed after DOMContentLoaded)
  initializeStrategyBuilder();
}

// Create the main Strategy node that cannot be deleted
function createMainStrategyNode() {
  // Fixed default position for Strategy node (right side, vertically centered)
  // These coordinates are calibrated for standard 1920x1080 screen
  const DEFAULT_STRATEGY_X = 1550;
  const DEFAULT_STRATEGY_Y = 350;

  const mainNode = {
    id: 'main_strategy',
    type: 'strategy',
    category: 'main',
    name: 'Strategy',
    icon: 'diagram-3',
    x: DEFAULT_STRATEGY_X,
    y: DEFAULT_STRATEGY_Y,
    isMain: true,
    params: {}
  };
  strategyBlocks.push(mainNode);
  setSBBlocks(strategyBlocks);
}

function renderBlockLibrary() {
  const container = document.getElementById('blockCategories');
  if (!container) {
    console.error('[Strategy Builder] Block categories container not found!');
    return;
  }
  container.innerHTML = '';

  // Simplified category groups (5 main groups — Smart Signals removed, Indicators merged into Entry)
  const categoryGroups = [
    {
      groupName: '🎯 Условия Входа',
      groupIcon: 'bullseye',
      groupColor: '#a371f7',
      categories: [
        { key: 'indicators', name: 'Технические индикаторы', iconType: 'indicator' },
        { key: 'conditions', name: 'Условия', iconType: 'condition' },
        { key: 'logic', name: 'Логика (AND/OR/NOT)', iconType: 'logic' },
        { key: 'divergence', name: 'Дивергенции', iconType: 'filter' },
        { key: 'entry_mgmt', name: 'DCA/Grid', iconType: 'entry' }
      ]
    },
    {
      groupName: '🚪 Условия Выхода',
      groupIcon: 'box-arrow-right',
      groupColor: '#f0883e',
      categories: [
        { key: 'exits', name: 'Выходы (SL/TP/ATR)', iconType: 'exit' },
        { key: 'close_conditions', name: 'Закрытие по индикатору', iconType: 'exit' }
      ]
    }
  ];

  const ADAPTER_SPECIFIC_CATEGORIES = [
    'atr_exit',
    'close_conditions', 'divergence',
    'entry_mgmt'
  ];

  // Render grouped categories
  categoryGroups.forEach((group) => {
    // Calculate total blocks in group
    let totalBlocks = 0;
    group.categories.forEach((cat) => {
      const blocks = blockLibrary[cat.key];
      if (blocks && Array.isArray(blocks)) {
        totalBlocks += blocks.length;
      }
    });

    if (totalBlocks === 0) return;

    // Create group container
    const groupDiv = document.createElement('div');
    groupDiv.className = 'block-category-group';
    groupDiv.innerHTML = `
      <div class="category-group-header" style="--group-color: ${escapeHtml(group.groupColor)}">
        <i class="bi bi-chevron-right group-chevron"></i>
        <i class="bi bi-${escapeHtml(group.groupIcon)}" style="color: ${escapeHtml(group.groupColor)}"></i>
        <span class="group-name">${escapeHtml(group.groupName)}</span>
        <span class="group-count">(${totalBlocks})</span>
      </div>
      <div class="category-group-content"></div>
    `;

    const contentDiv = groupDiv.querySelector('.category-group-content');

    // Render subcategories
    group.categories.forEach((cat) => {
      const blocks = blockLibrary[cat.key];
      console.log(`[Strategy Builder] Category ${cat.key}: ${blocks ? blocks.length : 0} blocks`);
      if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return;

      const blockCategory = ADAPTER_SPECIFIC_CATEGORIES.includes(cat.key) ? cat.key : cat.iconType;

      const catDiv = document.createElement('div');
      catDiv.className = 'block-category collapsed'; // Start collapsed
      catDiv.innerHTML = `
        <div class="category-header subcategory">
          <i class="bi bi-chevron-right"></i>
          <span class="category-count">(${blocks.length})</span>
          <span class="category-title">${escapeHtml(cat.name)}</span>
        </div>
        <div class="block-list">
          ${blocks
          .map(
            (block) => `
              <div class="block-item"
                   draggable="true"
                   data-block-id="${escapeHtml(block.id)}"
                   data-block-type="${escapeHtml(blockCategory)}">
                <div class="block-icon ${escapeHtml(cat.iconType)}">
                  <i class="bi bi-${escapeHtml(block.icon)}"></i>
                </div>
                <div class="block-info">
                  <div class="block-name">${escapeHtml(block.name)}</div>
                  <div class="block-desc">${escapeHtml(block.desc)}</div>
                </div>
              </div>
            `
          )
          .join('')}
        </div>
      `;

      contentDiv.appendChild(catDiv);
    });

    container.appendChild(groupDiv);
  });

  // Add click handlers for group headers
  container.querySelectorAll('.category-group-header').forEach((header) => {
    header.addEventListener('click', () => {
      const group = header.closest('.block-category-group');
      group.classList.toggle('collapsed');
    });
  });

  // All subcategories start collapsed. CSS handles display:none via
  // .block-category.collapsed .block-list { display: none !important }
  // Just ensure the collapsed class + correct chevron icon is in place.
  container.querySelectorAll('.block-category').forEach((cat) => {
    cat.classList.add('collapsed');
    const icon = cat.querySelector('.category-header i');
    if (icon) {
      icon.classList.remove('bi-chevron-down');
      icon.classList.add('bi-chevron-right');
    }
  });

  console.log('[Strategy Builder] Block library rendered with groups. Groups in DOM:',
    document.querySelectorAll('.block-category-group').length);
}

/** Синхронизирует название стратегии: шапка -> панель Properties. */
function syncStrategyNameDisplay() {
  const nameInput = document.getElementById('strategyName');
  const displayEl = document.getElementById('strategyNameDisplay');
  if (nameInput && displayEl) {
    displayEl.value = nameInput.value || 'New Strategy';
  }
}

/** Синхронизирует название стратегии: панель Properties -> шапка. */
function syncStrategyNameToNavbar() {
  const nameInput = document.getElementById('strategyName');
  const displayEl = document.getElementById('strategyNameDisplay');
  if (displayEl && nameInput) {
    nameInput.value = displayEl.value || 'New Strategy';
  }
}


// ── SymbolSyncModule extracted to frontend/js/strategy_builder/SymbolSyncModule.js ──
// All symbol picker, ticker data, DB panel, and SSE sync code lives there.
// Initialized via createSymbolSyncModule() in initializeStrategyBuilder().


/** Обновить подпись и ограничения поля «Размер позиции» в Properties по типу ордера. */
function updateBacktestPositionSizeInput() {
  const typeSelect = document.getElementById('backtestPositionSizeType');
  const sizeInput = document.getElementById('backtestPositionSize');
  const sizeLabel = document.getElementById('backtestPositionSizeLabel');
  if (!typeSelect || !sizeInput || !sizeLabel) return;
  const type = typeSelect.value;
  switch (type) {
    case 'percent':
      sizeLabel.textContent = 'Размер позиции (%)';
      sizeInput.min = 1;
      sizeInput.max = 100;
      sizeInput.step = 1;
      if (sizeInput.value === '' || sizeInput.value === null || sizeInput.value === undefined) sizeInput.value = 100;
      break;
    case 'fixed_amount':
      sizeLabel.textContent = 'Сумма на ордер ($)';
      sizeInput.min = 1;
      sizeInput.max = 1000000;
      sizeInput.step = 1;
      if (sizeInput.value === '' || sizeInput.value === null || sizeInput.value === undefined) sizeInput.value = 100;
      break;
    case 'contracts':
      sizeLabel.textContent = 'Контракты/Лоты';
      sizeInput.min = 0.001;
      sizeInput.max = 10000;
      sizeInput.step = 0.001;
      if (sizeInput.value === '' || sizeInput.value === null || sizeInput.value === undefined) sizeInput.value = 1;
      break;
    default:
      sizeLabel.textContent = 'Размер позиции (%)';
  }
}

/** Обновить отображение плеча и скрытое поле в Properties. */
function updateBacktestLeverageDisplay(value) {
  const val = parseInt(value, 10) || 1;
  const rangeEl = document.getElementById('backtestLeverageRange');
  const valueEl = document.getElementById('backtestLeverageValue');
  const hiddenEl = document.getElementById('backtestLeverage');
  if (rangeEl) rangeEl.value = val;
  if (valueEl) valueEl.textContent = val + 'x';
  if (hiddenEl) hiddenEl.value = val;
  const maxL = rangeEl ? parseInt(rangeEl.max, 10) || 50 : 50;

  // Обновить CSS переменную для градиента трека слайдера
  if (rangeEl) {
    const percent = ((val - 1) / (maxL - 1)) * 100;
    rangeEl.style.setProperty('--leverage-percent', `${percent}%`);
  }

  if (valueEl) {
    const pct = val / maxL;
    valueEl.style.color = pct >= 0.5 ? '#ff6b6b' : pct >= 0.2 ? '#ffd93d' : 'var(--accent-blue)';
  }
}

/** Обновить индикатор риска плеча в Properties (символ, капитал, тип/размер позиции, плечо). */
async function updateBacktestLeverageRisk() {
  await updateLeverageRiskForElements({
    symbolEl: document.getElementById('backtestSymbol'),
    capitalEl: document.getElementById('backtestCapital'),
    positionSizeTypeEl: document.getElementById('backtestPositionSizeType'),
    positionSizeEl: document.getElementById('backtestPositionSize'),
    leverageVal: parseInt(document.getElementById('backtestLeverageRange')?.value || document.getElementById('backtestLeverage')?.value, 10) || 10,
    riskIndicatorEl: document.getElementById('backtestLeverageRiskIndicator'),
    rangeEl: document.getElementById('backtestLeverageRange') // Bug #2 fix: pass slider so max can be updated from exchange
  });
}

function setupEventListeners() {
  // Guard: prevent duplicate listener registration if called more than once
  if (_eventListenersInitialized) {
    console.warn('[Strategy Builder] setupEventListeners() already called — skipping');
    return;
  }
  _eventListenersInitialized = true;
  console.log('[Strategy Builder] Setting up event listeners...');

  // Синхронизация названия стратегии: шапка <-> панель Properties
  const nameInput = document.getElementById('strategyName');
  const nameDisplay = document.getElementById('strategyNameDisplay');
  if (nameInput) {
    nameInput.addEventListener('input', syncStrategyNameDisplay);
    nameInput.addEventListener('change', syncStrategyNameDisplay);
  }
  if (nameDisplay) {
    nameDisplay.addEventListener('input', syncStrategyNameToNavbar);
    nameDisplay.addEventListener('change', syncStrategyNameToNavbar);
  }

  // Sync data when Symbol/TF/Market type change (symbol picker selection handled in initSymbolPicker)
  const backtestSymbolEl = document.getElementById('backtestSymbol');
  const strategyTimeframeEl = document.getElementById('strategyTimeframe');
  const builderMarketTypeEl = document.getElementById('builderMarketType');
  if (backtestSymbolEl) {
    backtestSymbolEl.addEventListener('change', checkSymbolDataForProperties);
    backtestSymbolEl.addEventListener('input', updateRunButtonsState);
    backtestSymbolEl.addEventListener('change', updateRunButtonsState);
  }
  if (strategyTimeframeEl) strategyTimeframeEl.addEventListener('change', () => {
    checkSymbolDataForProperties();
    // Restart auto-refresh with new TF interval
    const sym = backtestSymbolEl?.value?.trim()?.toUpperCase();
    if (sym) symbolSync.setupAutoRefresh(sym);
  });
  if (builderMarketTypeEl) {
    builderMarketTypeEl.addEventListener('change', checkSymbolDataForProperties);
    // Auto-update commission when market type changes
    // linear = Bybit perpetuals taker 0.055%, spot = Bybit spot taker 0.1%
    builderMarketTypeEl.addEventListener('change', () => {
      const commEl = document.getElementById('backtestCommission');
      if (!commEl) return;
      const isSpot = builderMarketTypeEl.value === 'spot';
      commEl.value = isSpot ? '0.1' : '0.055';
      commEl.title = isSpot
        ? '0.1% = Bybit Spot taker fee (market orders)'
        : '0.055% = Bybit Linear/Perpetual taker fee (market orders)';
    });
  }

  // Direction change - update Strategy node ports and connection mismatch highlighting
  const builderDirectionEl = document.getElementById('builderDirection');
  if (builderDirectionEl) {
    builderDirectionEl.addEventListener('change', () => {
      // Remove connections to ports that are no longer valid for the new direction
      const direction = builderDirectionEl.value;
      if (direction !== 'both') {
        const hiddenPorts = direction === 'long'
          ? ['entry_short', 'exit_short']
          : ['entry_long', 'exit_long'];
        const before = connections.length;
        for (let i = connections.length - 1; i >= 0; i--) {
          const c = connections[i];
          if (hiddenPorts.includes(c.target?.portId) || hiddenPorts.includes(c.source?.portId)) {
            connections.splice(i, 1);
          }
        }
        if (connections.length < before) {
          showNotification(
            `Удалено ${before - connections.length} соединений к скрытым портам`,
            'info'
          );
          // Bug #4 fix: sync graph to DB so backend reads updated connections
          autoSaveStrategy().catch((err) => console.warn('[Strategy Builder] Autosave error:', err));
        }
      }
      // Re-render blocks to update Strategy node ports based on direction
      renderBlocks();
      // Re-render connections to update direction mismatch highlighting
      renderConnections();
    });
  }

  const backtestPositionSizeTypeEl = document.getElementById('backtestPositionSizeType');
  const backtestLeverageRangeEl = document.getElementById('backtestLeverageRange');
  if (backtestPositionSizeTypeEl) {
    backtestPositionSizeTypeEl.addEventListener('change', () => {
      updateBacktestPositionSizeInput();
      updateBacktestLeverageRisk();
    });
  }
  const backtestPositionSizeEl = document.getElementById('backtestPositionSize');
  if (backtestPositionSizeEl) backtestPositionSizeEl.addEventListener('change', updateBacktestLeverageRisk);
  const backtestCapitalEl = document.getElementById('backtestCapital');
  if (backtestCapitalEl) backtestCapitalEl.addEventListener('change', updateBacktestLeverageRisk);
  if (backtestLeverageRangeEl) {
    backtestLeverageRangeEl.addEventListener('input', () => {
      const v = backtestLeverageRangeEl.value;
      updateBacktestLeverageDisplay(v);
      updateBacktestLeverageRisk();
    });
    // Колёсико мыши на весь блок плеча: зона по Y увеличена (подпись + слайдер + шкала + риск)
    const leverageBlock = backtestLeverageRangeEl.closest('.properties-leverage-block');
    if (leverageBlock) {
      leverageBlock.addEventListener('wheel', (e) => {
        e.preventDefault();
        const min = parseInt(backtestLeverageRangeEl.min, 10) || 1;
        const max = parseInt(backtestLeverageRangeEl.max, 10) || 50;
        const step = e.deltaY < 0 ? 1 : -1;
        let v = parseInt(backtestLeverageRangeEl.value, 10) + step;
        v = Math.max(min, Math.min(max, v));
        backtestLeverageRangeEl.value = v;
        updateBacktestLeverageDisplay(String(v));
        updateBacktestLeverageRisk();
      }, { passive: false });
    }
  }

  // Canvas drop zone
  const canvas = document.getElementById('canvasContainer');
  if (canvas) {
    canvas.addEventListener('dragover', (e) => e.preventDefault());
    canvas.addEventListener('drop', onCanvasDrop);
    console.log('[Strategy Builder] Canvas event listeners attached');
  } else {
    console.error('[Strategy Builder] Canvas container not found!');
  }

  // Properties section collapse/expand — обрабатывается sidebar-toggle.js (без дублирования)

  // Клик по блоку статуса данных при ошибке — повторная попытка синхронизации
  const dataStatusRow = document.getElementById('propertiesDataStatusRow');
  if (dataStatusRow) {
    dataStatusRow.addEventListener('click', function () {
      const indicator = document.getElementById('propertiesDataStatusIndicator');
      if (indicator?.classList.contains('error')) symbolSync.syncSymbolData(true);
    });
  }

  // База данных — initDunnahBasePanel вызывается после создания symbolSync (см. initializeStrategyBuilder)

  // Block search
  document
    .getElementById('blockSearch')
    .addEventListener('input', filterBlocks);

  // Store original positions for all blocks (before panel opens)
  const blocksOriginalPositions = new Map(); // blockId -> {x, y}
  let isFloatingWindowOpen = false;

  // Listen for floating window toggle to adjust all nodes positions
  document.addEventListener('floatingWindowToggle', function (e) {
    const canvasContainer = document.getElementById('canvasContainer');
    if (!canvasContainer) return;

    const canvasWidth = canvasContainer.offsetWidth;
    const floatingWindowWidth = 560; // Width of floating panels
    const spineWidth = 35; // Width of panel spines/tabs
    const margin = 15; // Small margin from spines

    // Threshold X - nodes right of this need to move
    const thresholdX = canvasWidth - floatingWindowWidth - spineWidth - margin;

    if (e.detail.isOpen && !isFloatingWindowOpen) {
      // Window opening - save positions and move affected nodes
      isFloatingWindowOpen = true;
      blocksOriginalPositions.clear();

      strategyBlocks.forEach(function (block) {
        // Get block width (main node is 140px, others ~180-280px)
        const blockWidth = block.isMain ? 140 : 200;
        const blockRightEdge = block.x + blockWidth;

        // If block's right edge extends past threshold, it needs to move
        if (blockRightEdge > thresholdX) {
          // Save original position
          blocksOriginalPositions.set(block.id, { x: block.x, y: block.y });

          // Calculate new X to keep block left of threshold
          const newX = thresholdX - blockWidth;

          // Find DOM element and animate
          const blockElement = document.getElementById(block.id);
          if (blockElement) {
            blockElement.style.transition = 'left 0.35s cubic-bezier(0.4, 0, 0.2, 1)';
            blockElement.style.left = newX + 'px';
          }
          block.x = newX;
        }
      });
      setSBBlocks([...strategyBlocks]);

    } else if (!e.detail.isOpen && isFloatingWindowOpen) {
      // Window closing - return all affected nodes to saved positions
      isFloatingWindowOpen = false;

      blocksOriginalPositions.forEach(function (originalPos, blockId) {
        const block = strategyBlocks.find(b => b.id === blockId);
        if (block) {
          const blockElement = document.getElementById(blockId);
          if (blockElement) {
            blockElement.style.transition = 'left 0.35s cubic-bezier(0.4, 0, 0.2, 1)';
            blockElement.style.left = originalPos.x + 'px';
          }
          block.x = originalPos.x;
        }
      });

      blocksOriginalPositions.clear();
      setSBBlocks([...strategyBlocks]);
    }

    // Update connections after animation
    setTimeout(function () {
      renderConnections();
      // Remove transitions from all blocks
      strategyBlocks.forEach(function (block) {
        const blockElement = document.getElementById(block.id);
        if (blockElement) {
          blockElement.style.transition = '';
        }
      });
    }, 400);
  });

  // Block library - drag start (event delegation for CSP compliance)
  const blockCategories = document.getElementById('blockCategories');
  if (blockCategories) {
    blockCategories.addEventListener('dragstart', function (e) {
      const blockItem = e.target.closest('.block-item');
      if (blockItem) {
        const blockId = blockItem.dataset.blockId;
        const blockType = blockItem.dataset.blockType;
        e.dataTransfer.setData('blockId', blockId);
        e.dataTransfer.setData('blockType', blockType);
        e.dataTransfer.effectAllowed = 'copy';
      }
    });

    // Block click to add (event delegation)
    blockCategories.addEventListener('click', function (e) {
      console.log('[Strategy Builder] Block categories clicked:', e.target, e.target.className);

      // Check if clicking on category header
      const categoryHeader = e.target.closest('.category-header');
      if (categoryHeader) {
        // If inside a category group, handle subcategory toggle here
        if (categoryHeader.closest('.block-category-group')) {
          e.preventDefault();
          e.stopPropagation();
          const category = categoryHeader.closest('.block-category');
          if (category) {
            // CSS already controls visibility via .collapsed class + !important rules
            // (.block-category.collapsed .block-list { display: none !important })
            // (.block-category:not(.collapsed) .block-list { display: flex !important })
            // Just toggle the class — no inline style manipulation needed.
            category.classList.toggle('collapsed');
            // Sync chevron icon direction
            const icon = categoryHeader.querySelector('i');
            if (icon) {
              if (category.classList.contains('collapsed')) {
                icon.classList.remove('bi-chevron-down');
                icon.classList.add('bi-chevron-right');
              } else {
                icon.classList.remove('bi-chevron-right');
                icon.classList.add('bi-chevron-down');
              }
            }
          }
          return;
        }
        // Otherwise let sidebar-toggle.js handle category toggle
        return;
      }

      // Check if clicking on block item
      const blockItem = e.target.closest('.block-item');
      if (blockItem) {
        const blockId = blockItem.dataset.blockId;
        const blockType = blockItem.dataset.blockType;
        console.log(`[Strategy Builder] Block item clicked: ${blockId}, type: ${blockType}`);
        e.preventDefault();
        e.stopPropagation();
        addBlockToCanvas(blockId, blockType);
        return;
      }

      // Check if clicking on block icon or name inside block-item
      const blockIcon = e.target.closest('.block-icon');
      const blockName = e.target.closest('.block-name');
      if (blockIcon || blockName) {
        const blockItem = (blockIcon || blockName).closest('.block-item');
        if (blockItem) {
          const blockId = blockItem.dataset.blockId;
          const blockType = blockItem.dataset.blockType;
          console.log(`[Strategy Builder] Block icon/name clicked: ${blockId}, type: ${blockType}`);
          e.preventDefault();
          e.stopPropagation();
          addBlockToCanvas(blockId, blockType);
        }
      }
    });
  }

  // Properties panel: delegated change/input for block params (uses selectedBlockId)
  const propertiesPanel = document.getElementById('propertiesPanel');
  if (propertiesPanel) {
    propertiesPanel.addEventListener('change', function (e) {
      const target = e.target;
      if (!target.closest('#blockProperties')) return;
      const key = target.dataset?.paramKey;
      if (!key || !selectedBlockId) return;
      if (target.classList.contains('tv-checkbox')) {
        updateBlockParam(selectedBlockId, key, target.checked);
        // Re-render properties panel for showWhen conditional fields
        const block = strategyBlocks.find(b => b.id === selectedBlockId);
        if (block) {
          const propsEl = document.getElementById('blockProperties');
          if (propsEl) {
            propsEl.innerHTML = renderGroupedParams(block);
          }
        }
      } else if (target.classList.contains('tv-select') || target.classList.contains('tv-input') || target.classList.contains('property-input')) {
        const val = target.type === 'number' ? (parseFloat(target.value) || 0) : target.value;
        updateBlockParam(selectedBlockId, key, val);
      }
    });
    propertiesPanel.addEventListener('input', function (e) {
      const target = e.target;
      if (!target.closest('#blockProperties')) return;
      const key = target.dataset?.paramKey;
      if (!key || !selectedBlockId) return;
      if (target.classList.contains('tv-input') && target.type !== 'number') {
        updateBlockParam(selectedBlockId, key, target.value);
      }
    });
  }

  // Canvas blocks - event delegation for drag and select
  const blocksContainer = document.getElementById('blocksContainer');
  if (blocksContainer) {
    // Block selection
    blocksContainer.addEventListener('click', function (e) {
      const block = e.target.closest('.strategy-block');
      if (block && !e.target.closest('.block-header-menu') && !e.target.closest('.block-action-btn')) {
        selectBlock(block.id);
      }
    });

    // Block menu - show params popup
    blocksContainer.addEventListener('click', function (e) {
      const menuBtn = e.target.closest('.block-header-menu');
      if (menuBtn) {
        e.stopPropagation();
        const block = menuBtn.closest('.strategy-block');
        if (block) {
          showBlockParamsPopup(block.id);
        }
      }
    });

    // Block action buttons (Delete, Duplicate)
    blocksContainer.addEventListener('click', function (e) {
      const actionBtn = e.target.closest('.block-action-btn');
      if (actionBtn) {
        e.stopPropagation();
        const block = actionBtn.closest('.strategy-block');
        const action = actionBtn.dataset.action;
        console.log('[Strategy Builder] Action button clicked:', action, 'block:', block?.id);
        if (block && action) {
          if (action === 'delete') {
            deleteBlock(block.id);
          } else if (action === 'duplicate') {
            duplicateBlock(block.id);
          }
        }
      }
    });

    // Block dragging
    blocksContainer.addEventListener('mousedown', function (e) {
      const block = e.target.closest('.strategy-block');
      if (
        block &&
        !e.target.closest('.block-param-input') &&
        !e.target.closest('.port') &&
        !e.target.closest('.block-header-menu') &&
        !e.target.closest('.block-action-btn') &&
        !e.target.closest('.block-params-popup')
      ) {
        // Check if this block is part of multi-selection for group drag
        if (selectedBlockIds.length > 1 && selectedBlockIds.includes(block.id)) {
          startGroupDrag(e);
        } else {
          startDragBlock(e, block.id);
        }
      }
    });

    // Marquee selection on canvas (click on empty area)
    const canvasContainer = document.getElementById('canvasContainer');
    canvasContainer.addEventListener('mousedown', function (e) {
      // Only start marquee if clicking on empty canvas area (not on a block or popup)
      if (!e.target.closest('.strategy-block') &&
        !e.target.closest('.block-params-popup') &&
        !e.target.closest('.zoom-controls') &&
        !e.target.closest('.canvas-toolbar') &&
        !e.target.closest('.quick-add-dialog')) {
        e.preventDefault();
        startMarqueeSelection(e);
      }
    });

    // Quick-Add Dialog on double-click on empty canvas
    canvasContainer.addEventListener('dblclick', function (e) {
      if (!e.target.closest('.strategy-block') &&
        !e.target.closest('.block-params-popup') &&
        !e.target.closest('.quick-add-dialog')) {
        e.preventDefault();
        const rect = canvasContainer.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        showQuickAddDialog(x, y);
      }
    });
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', function (e) {
    // Undo Ctrl+Z
    if (e.key === 'z' && e.ctrlKey && !e.shiftKey) {
      if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        undo();
      }
      return;
    }
    // Redo Ctrl+Y or Ctrl+Shift+Z
    if ((e.key === 'y' && e.ctrlKey) || (e.key === 'z' && e.ctrlKey && e.shiftKey)) {
      if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        redo();
      }
      return;
    }
    // Delete selected block
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedBlockId) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')
        return;
      e.preventDefault();
      deleteSelected();
    }
    // Duplicate with Ctrl+D
    if (e.key === 'd' && e.ctrlKey && selectedBlockId) {
      e.preventDefault();
      duplicateSelected();
    }
    // Save selection as preset with Ctrl+Shift+S
    if (e.key === 's' && e.ctrlKey && e.shiftKey) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      e.preventDefault();
      showSavePresetDialog();
    }
    // Open presets panel with Ctrl+P
    if (e.key === 'p' && e.ctrlKey && !e.shiftKey) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      e.preventDefault();
      showPresetsPanel();
    }
  });

  // =====================================================
  // Navbar buttons (CSP-compliant event listeners by ID)
  // =====================================================

  // Versions button and modal
  const btnVersions = document.getElementById('btnVersions');
  if (btnVersions) btnVersions.addEventListener('click', openVersionsModal);
  const versionsModal = document.getElementById('versionsModal');
  if (versionsModal) {
    versionsModal.addEventListener('click', (e) => { if (e.target === versionsModal) closeVersionsModal(); });
  }
  const btnCloseVersionsModal = document.getElementById('btnCloseVersionsModal');
  const btnCloseVersions = document.getElementById('btnCloseVersions');
  if (btnCloseVersionsModal) btnCloseVersionsModal.addEventListener('click', closeVersionsModal);
  if (btnCloseVersions) btnCloseVersions.addEventListener('click', closeVersionsModal);

  // Validation panel auto-close timer
  let validationAutoCloseTimer = null;
  let validationIsHovered = false;
  const VALIDATION_AUTO_CLOSE_MS = 5000; // 5 seconds for initial show
  const VALIDATION_AFTER_HOVER_MS = 1000; // 1 second after mouse leaves

  function showValidationPanel() {
    const validationPanel = document.querySelector('.validation-panel');
    if (!validationPanel) return;

    // If already visible, just restart the timer (don't re-add classes)
    if (validationPanel.classList.contains('visible') && !validationPanel.classList.contains('closing')) {
      startValidationAutoClose();
      return;
    }

    validationPanel.classList.remove('closing');
    validationPanel.classList.add('visible');

    // Start auto-close timer
    startValidationAutoClose();
  }

  function hideValidationPanel() {
    const validationPanel = document.querySelector('.validation-panel');
    if (!validationPanel) return;
    if (!validationPanel.classList.contains('visible')) return;

    clearTimeout(validationAutoCloseTimer);
    validationAutoCloseTimer = null;
    validationPanel.classList.add('closing');
    setTimeout(() => {
      validationPanel.classList.remove('visible', 'closing');
    }, 300);
  }

  function startValidationAutoClose() {
    // Always clear previous timer first
    if (validationAutoCloseTimer) {
      clearTimeout(validationAutoCloseTimer);
      validationAutoCloseTimer = null;
    }

    // Only start new timer if not hovered
    if (!validationIsHovered) {
      validationAutoCloseTimer = setTimeout(() => {
        if (!validationIsHovered) {
          hideValidationPanel();
        }
      }, VALIDATION_AUTO_CLOSE_MS);
    }
  }

  // Setup validation panel hover events
  const validationPanel = document.querySelector('.validation-panel');
  if (validationPanel) {
    validationPanel.addEventListener('mouseenter', () => {
      validationIsHovered = true;
      // Cancel any pending close timer
      if (validationAutoCloseTimer) {
        clearTimeout(validationAutoCloseTimer);
        validationAutoCloseTimer = null;
      }
    });
    validationPanel.addEventListener('mouseleave', () => {
      validationIsHovered = false;
      // Start 1-second timer when mouse leaves
      if (validationAutoCloseTimer) {
        clearTimeout(validationAutoCloseTimer);
        validationAutoCloseTimer = null;
      }
      validationAutoCloseTimer = setTimeout(() => {
        if (!validationIsHovered) {
          hideValidationPanel();
        }
      }, VALIDATION_AFTER_HOVER_MS);
    });
  }

  // Validate button - shows validation panel with auto-close
  const btnValidate = document.getElementById('btnValidate');
  if (btnValidate) {
    btnValidate.addEventListener('click', async function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Validate button clicked');
      try {
        await validateStrategy();
        showValidationPanel();
      } catch (err) {
        console.error('[Strategy Builder] Validate error:', err);
        showNotification(`Ошибка валидации: ${err.message}`, 'error');
      }
    });
    console.log('[Strategy Builder] Validate button listener attached');
  } else {
    console.error('[Strategy Builder] Validate button not found!');
  }

  // Generate Code button
  const btnGenerateCode = document.getElementById('btnGenerateCode');
  if (btnGenerateCode) {
    btnGenerateCode.addEventListener('click', async function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Generate Code button clicked');
      try {
        await generateCode();
      } catch (err) {
        console.error('[Strategy Builder] Generate Code error:', err);
        showNotification(`Ошибка генерации кода: ${err.message}`, 'error');
      }
    });
    console.log('[Strategy Builder] Generate Code button listener attached');
  } else {
    console.error('[Strategy Builder] Generate Code button not found!');
  }

  // Save button
  const btnSave = document.getElementById('btnSave');
  if (btnSave) {
    btnSave.addEventListener('click', async function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Save button clicked');
      try {
        await saveStrategy();
      } catch (err) {
        console.error('[Strategy Builder] Save error:', err);
        showNotification(`Ошибка сохранения: ${err.message}`, 'error');
      }
    });
    console.log('[Strategy Builder] Save button listener attached');
  } else {
    console.error('[Strategy Builder] Save button not found!');
  }

  // Backtest button
  const btnBacktest = document.getElementById('btnBacktest');
  if (btnBacktest) {
    btnBacktest.addEventListener('click', async function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Backtest button clicked');
      try {
        await runBacktest();
      } catch (err) {
        console.error('[Strategy Builder] Backtest error:', err);
        showNotification(`Ошибка запуска бэктеста: ${err.message}`, 'error');
      }
    });
    console.log('[Strategy Builder] Backtest button listener attached');
  } else {
    console.error('[Strategy Builder] Backtest button not found!');
  }

  // Toolbar buttons
  document.querySelectorAll('[onclick*="undo()"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', undo);
  });

  document.querySelectorAll('[onclick*="redo()"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', redo);
  });

  document.querySelectorAll('[onclick*="deleteSelected"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', deleteSelected);
  });

  document.querySelectorAll('[onclick*="duplicateSelected"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', duplicateSelected);
  });

  document.querySelectorAll('[onclick*="alignBlocks"]').forEach((btn) => {
    const match = btn
      .getAttribute('onclick')
      .match(/alignBlocks\(['"](\w+)['"]\)/);
    const direction = match ? match[1] : 'left';
    btn.removeAttribute('onclick');
    btn.addEventListener('click', () => alignBlocks(direction));
  });

  document.querySelectorAll('[onclick*="autoLayout"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', autoLayout);
  });

  // ===== Toolbar buttons by ID (CSP-compliant) =====
  const btnUndo = document.getElementById('btnUndo');
  if (btnUndo) {
    btnUndo.addEventListener('click', () => {
      console.log('[Strategy Builder] Undo button clicked');
      undo();
    });
  }

  const btnRedo = document.getElementById('btnRedo');
  if (btnRedo) {
    btnRedo.addEventListener('click', () => {
      console.log('[Strategy Builder] Redo button clicked');
      redo();
    });
  }

  const btnDuplicate = document.getElementById('btnDuplicate');
  if (btnDuplicate) {
    btnDuplicate.addEventListener('click', () => {
      console.log('[Strategy Builder] Duplicate button clicked');
      duplicateSelected();
    });
  }

  const btnClearAll = document.getElementById('btnClearAll');
  if (btnClearAll) {
    btnClearAll.addEventListener('click', () => {
      console.log('[Strategy Builder] Clear All button clicked');
      clearAllAndReset();
    });
    console.log('[Strategy Builder] Clear All button listener attached');
  } else {
    console.warn('[Strategy Builder] Clear All button not found!');
  }

  const btnAlignLeft = document.getElementById('btnAlignLeft');
  if (btnAlignLeft) {
    btnAlignLeft.addEventListener('click', () => alignBlocks('left'));
  }

  const btnAlignCenter = document.getElementById('btnAlignCenter');
  if (btnAlignCenter) {
    btnAlignCenter.addEventListener('click', () => alignBlocks('center'));
  }

  const btnAlignRight = document.getElementById('btnAlignRight');
  if (btnAlignRight) {
    btnAlignRight.addEventListener('click', () => alignBlocks('right'));
  }

  const btnAutoLayout = document.getElementById('btnAutoLayout');
  if (btnAutoLayout) {
    btnAutoLayout.addEventListener('click', () => autoLayout());
  }
  // ===== End Toolbar buttons =====

  // NOTE: fitToScreen and zoom buttons have no onclick attributes in HTML.
  // They are wired in initCspCompliantListeners() via title/class selectors.
}

function _toggleCategory(header) {
  const category = header.parentElement;
  const wasCollapsed = category.classList.contains('collapsed');

  // Toggle collapsed state
  category.classList.toggle('collapsed');

  // Update icon
  const icon = header.querySelector('i');
  icon.classList.toggle('bi-chevron-down');
  icon.classList.toggle('bi-chevron-right');

  // If opening category, scroll it to the top of the container
  if (wasCollapsed) {
    setTimeout(() => {
      const container = category.closest('.block-categories');
      if (container) {
        // Scroll category to top of container
        const categoryTop = category.offsetTop - container.offsetTop;
        container.scrollTo({
          top: categoryTop,
          behavior: 'smooth'
        });
      }
    }, 50);
  }
}

function filterBlocks() {
  const search = document.getElementById('blockSearch').value.toLowerCase().trim();
  const items = document.querySelectorAll('.block-item');
  const categories = document.querySelectorAll('.block-category');

  if (!search) {
    // Show all blocks and restore category state
    items.forEach((item) => {
      item.style.display = 'flex';
      item.classList.remove('search-highlight');
    });
    categories.forEach((cat) => {
      cat.style.display = 'block';
      cat.classList.remove('has-search-results', 'no-search-results');
      // Update count to original
      const count = cat.querySelectorAll('.block-item').length;
      const countEl = cat.querySelector('.category-count');
      if (countEl) countEl.textContent = `(${count})`;
    });
    return;
  }

  // Filter blocks and track matches per category
  const categoryMatches = new Map();

  items.forEach((item) => {
    const name = item.querySelector('.block-name')?.textContent.toLowerCase() ?? '';
    const desc = item.querySelector('.block-desc')?.textContent.toLowerCase() ?? '';
    const blockId = item.dataset.blockId?.toLowerCase() || '';
    const matches = name.includes(search) || desc.includes(search) || blockId.includes(search);

    item.style.display = matches ? 'flex' : 'none';
    item.classList.toggle('search-highlight', matches);

    // Track category matches
    const category = item.closest('.block-category');
    if (category) {
      const currentCount = categoryMatches.get(category) || 0;
      categoryMatches.set(category, currentCount + (matches ? 1 : 0));
    }
  });

  // Update category visibility and counts
  categories.forEach((cat) => {
    const matchCount = categoryMatches.get(cat) || 0;
    const hasMatches = matchCount > 0;

    cat.style.display = hasMatches ? 'block' : 'none';
    cat.classList.toggle('has-search-results', hasMatches);
    cat.classList.toggle('no-search-results', !hasMatches);

    // Update count to show matches
    const countEl = cat.querySelector('.category-count');
    if (countEl && hasMatches) {
      const totalCount = cat.querySelectorAll('.block-item').length;
      countEl.textContent = `(${matchCount}/${totalCount})`;
    }

    // Auto-expand categories with matches
    if (hasMatches) {
      cat.classList.remove('collapsed');
    }
  });
}

function onBlockDragStart(event, blockId, blockType) {
  event.dataTransfer.setData('blockId', blockId);
  event.dataTransfer.setData('blockType', blockType);
}

function onCanvasDrop(event) {
  event.preventDefault();
  console.log('[Strategy Builder] Canvas drop event');
  const blockId = event.dataTransfer.getData('blockId');
  const blockType = event.dataTransfer.getData('blockType');
  console.log(`[Strategy Builder] Dropped block: ${blockId}, type: ${blockType}`);

  if (blockId && blockType) {
    const rect = event.currentTarget.getBoundingClientRect();
    // BUG#3 FIX: convert screen drop position to logical space by dividing by zoom
    const x = (event.clientX - rect.left) / zoom;
    const y = (event.clientY - rect.top) / zoom;
    console.log(`[Strategy Builder] Drop position (logical): x=${x}, y=${y}`);
    addBlockToCanvas(blockId, blockType, x, y);
  } else {
    console.warn('[Strategy Builder] Drop data missing');
  }
}

function addBlockToCanvas(blockId, blockType, x = null, y = null) {
  // BUG#6 FIX: removed verbose console.log calls from this hot path

  // Find block definition
  let blockDef = null;
  Object.values(blockLibrary).forEach((category) => {
    const found = category.find((b) => b.id === blockId);
    if (found) blockDef = found;
  });

  if (!blockDef) {
    console.error(`[Strategy Builder] Block definition not found for: ${blockId}`);
    showNotification(`Блок "${blockId}" не найден`, 'error');
    return;
  }

  // Create block
  const block = {
    id: `block_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type: blockId,
    category: blockType,
    name: blockDef.name,
    icon: blockDef.icon,
    x: x || 100 + strategyBlocks.length * 50,
    y: y || 100 + strategyBlocks.length * 30,
    params: getDefaultParams(blockId),
    optimizationParams: {} // For optimization ranges
  };

  pushUndo();
  strategyBlocks.push(block);
  setSBBlocks(strategyBlocks);

  renderBlocks();
  selectBlock(block.id);

  // Notify optimization panels about block changes
  dispatchBlocksChanged();

  showNotification(`Блок "${blockDef.name}" добавлен`, 'success');
}

function getDefaultParams(blockType) {
  const params = {
    // =============================================
    // MOMENTUM INDICATORS
    // =============================================
    rsi: {
      period: 14,
      source: 'close',
      timeframe: 'Chart',
      // BTC source
      use_btc_source: false,
      // Long range filter  (TV: longRSIMin=0 >= , longRSIMax=50 <=)
      use_long_range: false,
      long_rsi_more: 0,
      long_rsi_less: 50,
      // Short range filter (TV: shortRSIMin=50 >= , shortRSIMax=100 <=)
      use_short_range: false,
      short_rsi_more: 50,
      short_rsi_less: 100,
      // Cross level       (TV: crossLevelLong=29, crossLevelShort=55)
      use_cross_level: false,
      cross_long_level: 29,
      cross_short_level: 55,
      opposite_signal: false,
      // Cross memory
      use_cross_memory: false,
      cross_memory_bars: 5
    },
    stochastic: {
      stoch_k_length: 14,
      stoch_k_smoothing: 3,
      stoch_d_smoothing: 3,
      timeframe: 'Chart',
      use_btc_source: false,
      // Range Filter Mode
      use_stoch_range_filter: false,
      long_stoch_d_more: 1,
      long_stoch_d_less: 50,
      short_stoch_d_less: 100,
      short_stoch_d_more: 50,
      // Cross Level Mode
      use_stoch_cross_level: false,
      stoch_cross_level_long: 20,
      stoch_cross_level_short: 80,
      activate_stoch_cross_memory: false,
      stoch_cross_memory_bars: 5,
      // K/D Cross Mode
      use_stoch_kd_cross: false,
      opposite_stoch_kd: false,
      activate_stoch_kd_memory: false,
      stoch_kd_memory_bars: 5
    },
    macd: {
      fast_period: 12,
      slow_period: 26,
      signal_period: 9,
      source: 'close',
      timeframe: 'Chart',
      use_btc_source: false,
      enable_visualization: false,
      // Cross with Level (Zero Line)
      use_macd_cross_zero: false,
      opposite_macd_cross_zero: false,
      macd_cross_zero_level: 0,
      // Cross with Signal Line
      use_macd_cross_signal: false,
      signal_only_if_macd_positive: false,
      opposite_macd_cross_signal: false,
      // Signal Memory (disabled by default for TV parity — enable only when
      // combining MACD signals with other conditions as a multi-bar filter)
      disable_signal_memory: true,
      signal_memory_bars: 5
    },
    supertrend: {
      use_supertrend: false,
      generate_on_trend_change: false,
      use_btc_source: false,
      opposite_signal: false,
      show_supertrend: false,
      period: 10,
      multiplier: 3.0,
      source: 'hl2',
      timeframe: 'Chart'
    },
    qqe: {
      rsi_period: 14,
      qqe_factor: 4.238,
      smoothing_period: 5,
      source: 'close',
      timeframe: 'Chart',
      // QQE cross signal mode (consolidated from qqe_filter)
      use_qqe: false,
      opposite_qqe: false,
      enable_qqe_visualization: false,
      disable_qqe_signal_memory: false,
      qqe_signal_memory_bars: 5
    },

    // =============================================
    // UNIVERSAL FILTERS (new instruments)
    // =============================================
    atr_volatility: {
      use_atr_volatility: false,
      atr1_to_atr2: 'ATR1 < ATR2',
      atr_diff_percent: 10,
      atr_length1: 20,
      atr_length2: 100,
      atr_smoothing: 'WMA'
    },
    volume_filter: {
      use_volume_filter: false,
      vol1_to_vol2: 'VOL1 < VOL2',
      vol_diff_percent: 10,
      vol_length1: 20,
      vol_length2: 100,
      vol_smoothing: 'WMA'
    },
    highest_lowest_bar: {
      // Highest/Lowest Bar signal
      use_highest_lowest: false,
      hl_lookback_bars: 10,
      hl_price_percent: 0,
      hl_atr_percent: 0,
      atr_hl_length: 50,
      // Block if Worse Than filter
      use_block_worse_than: false,
      block_worse_percent: 1.1
    },
    two_mas: {
      ma1_length: 50,
      ma1_smoothing: 'SMA',
      ma1_source: 'close',
      ma2_length: 100,
      ma2_smoothing: 'EMA',
      ma2_source: 'close',
      show_two_mas: false,
      two_mas_timeframe: 'Chart',
      // MA Cross signal
      use_ma_cross: false,
      opposite_ma_cross: false,
      activate_ma_cross_memory: false,
      ma_cross_memory_bars: 5,
      // MA1 as Filter
      use_ma1_filter: false,
      opposite_ma1_filter: false
    },
    accumulation_areas: {
      use_accumulation: false,
      backtracking_interval: 30,
      min_bars_to_execute: 5,
      signal_on_breakout: false,
      signal_on_opposite_breakout: false
    },
    keltner_bollinger: {
      use_channel: false,
      channel_timeframe: 'Chart',
      channel_mode: 'Rebound',
      channel_type: 'Keltner Channel',
      enter_conditions: 'Wick out of band',
      keltner_length: 14,
      keltner_mult: 1.5,
      bb_length: 20,
      bb_deviation: 2
    },
    rvi_filter: {
      rvi_length: 10,
      rvi_timeframe: 'Chart',
      rvi_ma_type: 'WMA',
      rvi_ma_length: 2,
      use_rvi_long_range: false,
      rvi_long_more: 1,
      rvi_long_less: 50,
      use_rvi_short_range: false,
      rvi_short_less: 100,
      rvi_short_more: 50
    },
    mfi_filter: {
      mfi_length: 14,
      mfi_timeframe: 'Chart',
      use_btcusdt_mfi: false,
      use_mfi_long_range: false,
      mfi_long_more: 1,
      mfi_long_less: 60,
      use_mfi_short_range: false,
      mfi_short_less: 100,
      mfi_short_more: 50
    },
    cci_filter: {
      cci_length: 14,
      cci_timeframe: 'Chart',
      use_cci_long_range: false,
      cci_long_more: -400,
      cci_long_less: 400,
      use_cci_short_range: false,
      cci_short_less: 400,
      cci_short_more: 10
    },
    momentum_filter: {
      momentum_length: 14,
      momentum_timeframe: 'Chart',
      use_btcusdt_momentum: false,
      momentum_source: 'close',
      use_momentum_long_range: false,
      momentum_long_more: -100,
      momentum_long_less: 10,
      use_momentum_short_range: false,
      momentum_short_less: 95,
      momentum_short_more: -30
    },
    stoch_rsi: { rsi_period: 14, stoch_period: 14, k_period: 3, d_period: 3, source: 'close' },
    cci: { period: 20 },
    adx: { period: 14 },
    parabolic_sar: { start: 0.02, increment: 0.02, max_value: 0.2 },
    sma: { period: 50, source: 'close' },
    ema: { period: 20, source: 'close' },
    bollinger: { period: 20, std_dev: 2.0, source: 'close' },
    donchian: { period: 20 },
    ichimoku: { tenkan_period: 9, kijun_period: 26, senkou_b_period: 52 },
    pivot_points: {},
    obv: {},
    vwap: {},
    ad_line: {},

    // (Filters defaults removed — entire Filters category deprecated)

    // =============================================
    // CONDITIONS
    // =============================================
    crossover: {
      source_a: 'input_a',
      source_b: 'input_b'
    },
    crossunder: {
      source_a: 'input_a',
      source_b: 'input_b'
    },
    greater_than: {
      value: 0,
      use_input: true
    },
    less_than: {
      value: 0,
      use_input: true
    },
    equals: {
      value: 0,
      tolerance: 0.001
    },
    between: {
      min_value: 0,
      max_value: 100
    },

    // =============================================
    // CLOSE CONDITIONS (EXIT RULES)
    // =============================================
    static_sltp: {
      take_profit_percent: 1.5,
      stop_loss_percent: 1.5,
      sl_type: 'average_price',
      close_only_in_profit: false,
      activate_breakeven: false,
      breakeven_activation_percent: 0.5,
      new_breakeven_sl_percent: 0.1
    },
    trailing_stop_exit: {
      activation_percent: 1.0,
      trailing_percent: 0.5,
      trail_type: 'percent'
    },
    atr_exit: {
      use_atr_sl: false,
      atr_sl_on_wicks: false,
      atr_sl_smoothing: 'WMA',
      atr_sl_period: 140,
      atr_sl_multiplier: 4.0,
      use_atr_tp: false,
      atr_tp_on_wicks: false,
      atr_tp_smoothing: 'WMA',
      atr_tp_period: 140,
      atr_tp_multiplier: 4.0
    },
    multi_tp_exit: {
      tp1_percent: 1.0,
      tp1_close_percent: 33,
      tp2_percent: 2.0,
      tp2_close_percent: 33,
      tp3_percent: 3.0,
      tp3_close_percent: 34,
      use_tp2: true,
      use_tp3: true
    },

    // =============================================
    // ENTRY MANAGEMENT (DCA / Grid)
    // =============================================
    dca: {
      grid_size_percent: 10,
      order_count: 5,
      martingale_coefficient: 1,
      log_steps_coefficient: 1.0,
      first_order_offset: 0,
      grid_trailing: 0,
      partial_grid_orders: 1,
      grid_pullback_percent: 0
    },
    grid_orders: {
      // Manual grid - array of orders with offset % and volume %
      orders: [
        { offset: 0.1, volume: 25 },
        { offset: 1.0, volume: 25 },
        { offset: 1.5, volume: 25 },
        { offset: 2.0, volume: 25 }
      ],
      grid_trailing: 0 // Grid Trailing / Cancel (%), 0 = disabled
    },

    // =============================================
    // CLOSE CONDITIONS (from TradingView)
    // =============================================
    close_by_time: {
      enabled: false,
      bars_since_entry: 10,
      profit_only: false,
      min_profit_percent: 0.5
    },
    close_channel: {
      enabled: false,
      channel_close_timeframe: 'Chart',
      band_to_close: 'Rebound',
      channel_type: 'Keltner Channel',
      close_condition: 'Wick out of band',
      keltner_length: 14,
      keltner_mult: 1.5,
      bb_length: 20,
      bb_deviation: 2
    },
    close_ma_cross: {
      enabled: false,
      show_ma_lines: false,
      profit_only: false,
      min_profit_percent: 1,
      ma1_length: 10,
      ma2_length: 30
    },
    close_rsi: {
      enabled: false,
      rsi_close_length: 14,
      rsi_close_timeframe: 'Chart',
      rsi_close_profit_only: false,
      rsi_close_min_profit: 1,
      activate_rsi_reach: false,
      rsi_long_more: 70,
      rsi_long_less: 100,
      rsi_short_less: 30,
      rsi_short_more: 1,
      activate_rsi_cross: false,
      rsi_cross_long_level: 70,
      rsi_cross_short_level: 30
    },
    close_stochastic: {
      enabled: false,
      stoch_close_k_length: 14,
      stoch_close_k_smoothing: 3,
      stoch_close_d_smoothing: 3,
      stoch_close_timeframe: 'Chart',
      stoch_close_profit_only: false,
      stoch_close_min_profit: 1,
      activate_stoch_reach: false,
      stoch_long_more: 80,
      stoch_long_less: 100,
      stoch_short_less: 20,
      stoch_short_more: 1,
      activate_stoch_cross: false,
      stoch_cross_long_level: 80,
      stoch_cross_short_level: 20
    },
    close_psar: {
      enabled: false,
      psar_opposite: false,
      psar_close_profit_only: false,
      psar_close_min_profit: 1,
      psar_start: 0.02,
      psar_increment: 0.02,
      psar_maximum: 0.2,
      psar_close_nth_bar: 1
    },

    // =============================================
    // DIVERGENCE DETECTION
    // =============================================
    divergence: {
      pivot_interval: 9,
      act_without_confirmation: false,
      show_divergence_lines: false,
      activate_diver_signal_memory: false,
      keep_diver_signal_memory_bars: 5,
      use_divergence_rsi: false,
      rsi_period: 14,
      use_divergence_stochastic: false,
      stoch_length: 14,
      use_divergence_momentum: false,
      momentum_length: 10,
      use_divergence_cmf: false,
      cmf_period: 21,
      use_obv: false,
      use_mfi: false,
      mfi_length: 14
    },

    // =============================================
    // LOGIC GATES
    // =============================================
    and: {},
    or: {},
    not: {}

    // (Smart Signals defaults removed — entire category deprecated in favor of universal indicator blocks)
  };
  return params[blockType] || {};
}

/**
 * Render Manual Grid Orders panel with dynamic order list
 * Allows adding/removing orders with offset % and volume %
 */
function renderGridOrdersPanel(block, blockId, _optimizationMode = false) {
  const params = block.params || {};
  const orders = params.orders || [{ offset: 0.1, volume: 25 }];
  const MAX_ORDERS = 40;

  // Calculate stats
  const totalVolume = orders.reduce((sum, o) => sum + (parseFloat(o.volume) || 0), 0);
  const remainingVolume = Math.max(0, 100 - totalVolume);
  const isVolumeValid = Math.abs(totalVolume - 100) < 0.01;

  let html = `
    <div class="tv-params-container grid-orders-panel" data-block-id="${blockId}">
      <div class="grid-orders-header">
        <div class="grid-orders-stats">
          <span class="grid-stat">
            <span class="grid-stat-label">ОРДЕРОВ</span>
            <span class="grid-stat-value">${orders.length}/${MAX_ORDERS}</span>
          </span>
          <span class="grid-stat">
            <span class="grid-stat-label">ОСТАТОК ДЕПОЗИТА</span>
            <span class="grid-stat-value ${remainingVolume > 0 ? 'warning' : ''}">${remainingVolume.toFixed(1)}%</span>
          </span>
        </div>
        <div class="grid-orders-hint ${isVolumeValid ? 'valid' : 'warning'}">
          <i class="bi bi-${isVolumeValid ? 'check-circle-fill' : 'exclamation-circle'}"></i>
          ${isVolumeValid
      ? 'Распределено 100% объёма депозита'
      : 'Распределите 100% объёма по ордерам'}
        </div>
      </div>

      <div class="grid-trailing-row">
        <div class="grid-order-field grid-trailing-field">
          <label class="grid-order-label">
            GRID TRAILING / CANCEL (%)
            <i class="bi bi-info-circle" title="Подтяжка сетки: отмена ордеров если цена отклонилась на указанный %. 0 = отключено."></i>
          </label>
          <input type="number"
                 class="grid-order-input grid-trailing-input"
                 value="${params.grid_trailing || 0}"
                 step="0.1"
                 min="0"
                 max="30"
                 data-field="grid_trailing"
                 id="gridTrailing_${blockId}">
        </div>
      </div>

      <div class="grid-orders-list" id="gridOrdersList_${blockId}">
  `;

  // Render each order row
  orders.forEach((order, index) => {
    html += `
        <div class="grid-order-row" data-order-index="${index}">
          <div class="grid-order-field">
            <label class="grid-order-label">ОТСТУП %</label>
            <input type="number"
                   class="grid-order-input"
                   value="${order.offset}"
                   step="0.01"
                   min="0"
                   max="100"
                   data-field="offset"
                   data-order-index="${index}">
          </div>
          <div class="grid-order-field">
            <label class="grid-order-label">ОБЪЁМ %</label>
            <input type="number"
                   class="grid-order-input"
                   value="${order.volume}"
                   step="0.1"
                   min="0.1"
                   max="100"
                   data-field="volume"
                   data-order-index="${index}">
          </div>
          <button class="grid-order-remove" data-order-index="${index}" title="Удалить ордер">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
    `;
  });

  html += `
      </div>

      <button class="grid-orders-add-btn" id="gridAddOrder_${blockId}" ${orders.length >= MAX_ORDERS ? 'disabled' : ''}>
        <i class="bi bi-plus-lg"></i> Добавить ордер
      </button>
    </div>
  `;

  return html;
}

/**
 * Initialize Grid Orders panel event handlers
 * Called after popup is rendered
 */
function initGridOrdersPanel(popup, blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block || block.type !== 'grid_orders') return;

  const panel = popup.querySelector('.grid-orders-panel');
  if (!panel) return;

  // Helper to update block hint
  const updateHint = () => {
    const blockEl = document.getElementById(blockId);
    if (blockEl) {
      const hintEl = blockEl.querySelector('.block-param-hint');
      if (hintEl) {
        hintEl.textContent = getCompactParamHint(block.params, block.type);
      }
    }
  };

  // Handle input changes
  panel.addEventListener('input', (e) => {
    if (e.target.classList.contains('grid-order-input')) {
      const field = e.target.dataset.field;
      const value = parseFloat(e.target.value) || 0;

      // Handle grid_trailing separately (not in orders array)
      if (field === 'grid_trailing') {
        block.params.grid_trailing = value;
        updateHint();
        pushUndo();
        return;
      }

      // Handle order fields
      const index = parseInt(e.target.dataset.orderIndex);
      if (!block.params.orders) block.params.orders = [];
      if (block.params.orders[index]) {
        block.params.orders[index][field] = value;
      }

      updateGridOrdersStats(panel, block);
      updateHint();
      pushUndo();
    }
  });

  // Handle remove button clicks
  panel.addEventListener('click', (e) => {
    const removeBtn = e.target.closest('.grid-order-remove');
    if (removeBtn) {
      const index = parseInt(removeBtn.dataset.orderIndex);
      if (block.params.orders && block.params.orders.length > 1) {
        block.params.orders.splice(index, 1);
        refreshGridOrdersPanel(popup, blockId);
        updateHint();
        pushUndo();
      }
    }
  });

  // Handle add button
  const addBtn = panel.querySelector('.grid-orders-add-btn');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      if (!block.params.orders) block.params.orders = [];
      if (block.params.orders.length < 40) {
        // Calculate next offset (last offset + 0.5%)
        const lastOrder = block.params.orders[block.params.orders.length - 1];
        const newOffset = lastOrder ? parseFloat(lastOrder.offset) + 0.5 : 0.1;

        // Calculate remaining volume and distribute
        const totalVolume = block.params.orders.reduce((sum, o) => sum + (parseFloat(o.volume) || 0), 0);
        const remaining = Math.max(0, 100 - totalVolume);
        const newVolume = remaining > 0 ? Math.min(remaining, 25) : 25;

        block.params.orders.push({ offset: newOffset, volume: newVolume });
        refreshGridOrdersPanel(popup, blockId);
        updateHint();
        pushUndo();
      }
    });
  }

  // Enable wheel scroll for number inputs
  enableWheelScrollForNumberInputs(panel);
}

/**
 * Refresh Grid Orders panel after changes
 */
function refreshGridOrdersPanel(popup, blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  const container = popup.querySelector('.popup-body');
  if (!container) return;

  container.innerHTML = renderGridOrdersPanel(block, blockId, false);
  initGridOrdersPanel(popup, blockId);
}

/**
 * Update Grid Orders stats display
 */
function updateGridOrdersStats(panel, block) {
  const orders = block.params.orders || [];
  const totalVolume = orders.reduce((sum, o) => sum + (parseFloat(o.volume) || 0), 0);
  const remainingVolume = Math.max(0, 100 - totalVolume);
  const isVolumeValid = Math.abs(totalVolume - 100) < 0.01;

  // Update stats
  const statsValue = panel.querySelectorAll('.grid-stat-value');
  if (statsValue[0]) statsValue[0].textContent = `${orders.length}/40`;
  if (statsValue[1]) {
    statsValue[1].textContent = `${remainingVolume.toFixed(1)}%`;
    statsValue[1].classList.toggle('warning', remainingVolume > 0);
  }

  // Update hint
  const hint = panel.querySelector('.grid-orders-hint');
  if (hint) {
    hint.className = `grid-orders-hint ${isVolumeValid ? 'valid' : 'warning'}`;
    hint.innerHTML = `
      <i class="bi bi-${isVolumeValid ? 'check-circle-fill' : 'exclamation-circle'}"></i>
      ${isVolumeValid
        ? 'Распределено 100% объёма депозита'
        : 'Распределите 100% объёма по ордерам'}
    `;
  }
}

/**
 * Render grouped params for complex blocks like RSI Filter
 * Returns HTML with grouped sections
 */
/**
 * Render params like TradingView - simple vertical layout
 * Supports both Default and Optimization modes
 */
function renderGroupedParams(block, optimizationMode = false, showHeader = true) {
  const blockId = block.id;
  // Merge defaults with existing params so missing keys get filled
  const defaults = getDefaultParams(block.type);
  const params = { ...defaults, ...(block.params || {}) };
  // Persist merged params back to block so values are saved
  block.params = params;
  const optParams = block.optimizationParams || {};

  // Только таймфреймы Bybit API v5: 1,3,5,15,30,60,120,240,360,720,D,W,M
  // Единый набор: 1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M
  const BYBIT_TF_OPTS = ['Chart', '1', '5', '15', '30', '60', '240', 'D', 'W', 'M'];

  // Define custom layouts for complex blocks
  const customLayouts = {
    // =============================================
    // MOMENTUM INDICATORS
    // =============================================
    rsi: {
      title: '======== RSI - [IN RANGE FILTER OR CROSS SIGNAL] ========',
      fields: [
        // Base settings
        { key: 'period', label: 'RSI TF Long(14):', type: 'number', optimizable: true, min: 1, max: 200, step: 1 },
        { key: 'timeframe', label: 'RSI TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'use_btc_source', label: 'Use BTCUSDT as Source for RSI 1 ?', type: 'checkbox' },
        // --- Use RSI LONG Range ---
        { key: 'use_long_range', label: 'Use RSI LONG Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_rsi_more', label: '(LONG) RSI is More', type: 'number', width: '60px', optimizable: true, min: 0.1, max: 100, step: 0.1 },
            { label: '& RSI Less', type: 'label' },
            { key: 'long_rsi_less', type: 'number', width: '60px', optimizable: true, min: 0.1, max: 100, step: 0.1 }
          ]
        },
        // --- Use RSI SHORT Range ---
        { key: 'use_short_range', label: 'Use RSI SHORT Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'short_rsi_less', label: '(SHORT) RSI is Less', type: 'number', width: '60px', optimizable: true, min: 0.1, max: 100, step: 0.1 },
            { label: '& RSI More', type: 'label' },
            { key: 'short_rsi_more', type: 'number', width: '60px', optimizable: true, min: 0.1, max: 100, step: 0.1 }
          ]
        },
        // --- Use RSI Cross Level ---
        { key: 'use_cross_level', label: 'Use RSI Cross Level', type: 'checkbox', tooltip: 'LONG: RSI crosses level from below. SHORT: RSI crosses level from above.' },
        { key: 'cross_long_level', label: 'Level to Cross RSI for LONG', type: 'number', optimizable: true, min: 0.1, max: 100, step: 0.1 },
        { key: 'cross_short_level', label: 'Level to Cross RSI for SHORT', type: 'number', optimizable: true, min: 0.1, max: 100, step: 0.1 },
        { key: 'opposite_signal', label: 'Opposite Signal - RSI Cross Level', type: 'checkbox', tooltip: 'Reverse direction of cross level signals' },
        { key: 'use_cross_memory', label: 'Activate RSI Cross Signal Memory', type: 'checkbox', tooltip: 'Keep signal in memory and execute when other conditions are met' },
        { key: 'cross_memory_bars', label: 'Keep RSI Cross Signal Memory for XX bars', type: 'number', optimizable: true, min: 1, max: 100, step: 1, tooltip: 'Number of bars to keep the cross signal in memory' }
      ]
    },
    stochastic: {
      title: '==== STOCHASTIC - [RANGE FILTER OR CROSS SIGNAL] ====',
      fields: [
        // Base settings
        { key: 'stoch_k_length', label: 'Stochastic %K Length (14)', type: 'number', optimizable: true, min: 1, max: 200, step: 1 },
        { key: 'stoch_k_smoothing', label: 'Stochastic %K Smoothing (3)', type: 'number', optimizable: true, min: 1, max: 50, step: 1 },
        { key: 'stoch_d_smoothing', label: 'Stochastic %D Smoothing (3)', type: 'number', optimizable: true, min: 1, max: 50, step: 1 },
        { key: 'timeframe', label: 'Stochastic TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'use_btc_source', label: 'Use BTCUSDT as Source for Stochastic ?', type: 'checkbox' },
        // --- Range Filter ---
        { type: 'separator', label: '======= Use Stochastic Range Filter =======' },
        { key: 'use_stoch_range_filter', label: 'Use Stochastic Range Filter', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_stoch_d_more', label: '(LONG) Stoch %D is More', type: 'number', width: '60px', optimizable: true, min: 0, max: 100, step: 1 },
            { label: '& Stoch %D Less', type: 'label' },
            { key: 'long_stoch_d_less', type: 'number', width: '60px', optimizable: true, min: 0, max: 100, step: 1 }
          ]
        },
        {
          type: 'inline',
          fields: [
            { key: 'short_stoch_d_less', label: '(SHORT) Stoch %D is Less', type: 'number', width: '60px', optimizable: true, min: 0, max: 100, step: 1 },
            { label: '& Stoch %D More', type: 'label' },
            { key: 'short_stoch_d_more', type: 'number', width: '60px', optimizable: true, min: 0, max: 100, step: 1 }
          ]
        },
        // --- Cross Level ---
        { type: 'separator', label: '======= Use Stochastic Cross Level =======' },
        { key: 'use_stoch_cross_level', label: 'Use Stochastic Cross Level', type: 'checkbox', tooltip: 'LONG: %D crosses level from below. SHORT: %D crosses level from above.' },
        { key: 'stoch_cross_level_long', label: 'Level to Cross Stochastic for LONG', type: 'number', optimizable: true, min: 0, max: 100, step: 1 },
        { key: 'stoch_cross_level_short', label: 'Level to Cross Stochastic for SHORT', type: 'number', optimizable: true, min: 0, max: 100, step: 1 },
        { key: 'activate_stoch_cross_memory', label: 'Activate Stochastic Cross Signal Memory', type: 'checkbox', tooltip: 'Keep signal in memory and execute when other conditions are met' },
        { key: 'stoch_cross_memory_bars', label: 'Keep Stochastic Cross Signal Memory for XX bars', type: 'number', optimizable: true, min: 1, max: 100, step: 1, tooltip: 'Number of bars to keep the cross signal in memory' },
        // --- K/D Cross ---
        { type: 'separator', label: '======= Use Stochastic Cross K/D =======' },
        { key: 'use_stoch_kd_cross', label: 'Use Stochastic Cross K/D', type: 'checkbox', tooltip: 'LONG: %K crosses %D from below. SHORT: %K crosses %D from above.' },
        { key: 'opposite_stoch_kd', label: 'Opposite Signal - Stochastic Cross K/D', type: 'checkbox', tooltip: 'Reverse direction of K/D cross signals' },
        { key: 'activate_stoch_kd_memory', label: 'Activate Stochastic Cross K/D Signal Memory', type: 'checkbox', tooltip: 'Keep K/D cross signal in memory' },
        { key: 'stoch_kd_memory_bars', label: 'Keep Stochastic Cross K/D Signal Memory for XX bars', type: 'number', optimizable: true, min: 1, max: 100, step: 1, tooltip: 'Number of bars to keep K/D cross signal in memory' }
      ]
    },
    // =============================================
    // TREND INDICATORS
    // =============================================
    macd: {
      title: 'MACD - [SIGNALS] (CROSS 0 LINE OR CROSS SIGNAL LINE)',
      fields: [
        { key: 'enable_visualization', label: 'Enable Visualisation MACD', type: 'checkbox', tooltip: 'Show MACD histogram on chart' },
        { key: 'timeframe', label: 'MACD TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'use_btc_source', label: 'Use BTCUSDT as Source for MACD ?', type: 'checkbox' },
        { key: 'fast_period', label: 'MACD Fast Length (12)', type: 'number', optimizable: true },
        { key: 'slow_period', label: 'MACD Slow Length (26)', type: 'number', optimizable: true },
        { key: 'signal_period', label: 'MACD Signal Smoothing (9)', type: 'number', optimizable: true },
        { key: 'source', label: 'MACD Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { type: 'divider' },
        { key: 'use_macd_cross_zero', label: 'Use MACD Cross with Level (0)', type: 'checkbox', tooltip: 'Long when MACD crosses above level, Short when crosses below' },
        { key: 'opposite_macd_cross_zero', label: 'Opposite Signal - MACD Cross with Level (0)', type: 'checkbox', tooltip: 'Swap long/short signals for level cross' },
        { key: 'macd_cross_zero_level', label: 'Cross Line Level (0)', type: 'number', optimizable: true },
        { type: 'divider' },
        { key: 'use_macd_cross_signal', label: 'Use MACD Cross with Signal Line', type: 'checkbox', tooltip: 'Long when MACD crosses above Signal line, Short when crosses below' },
        { key: 'opposite_macd_cross_signal', label: 'Opposite Signal - MACD Cross with Signal Line', type: 'checkbox', tooltip: 'Swap long/short signals for signal line cross' },
        { type: 'divider' },
        { key: 'signal_only_if_macd_positive', label: 'Filter by Zero (LONG if MACD>0, SHORT if MACD<0)', type: 'checkbox', tooltip: 'Filter: only generate long signals when MACD > 0, short when MACD < 0' },
        { key: 'disable_signal_memory', label: '==Disable Signal Memory (for both MACD Crosses)==', type: 'checkbox', tooltip: 'When CHECKED (default): cross signals fire only on the exact bar of crossing — matches TradingView parity. When UNCHECKED: signals persist for N bars after crossing (useful for combining with other conditions).' },
        { key: 'signal_memory_bars', label: 'Keep MACD Signal in Memory for N bars', type: 'number', optimizable: true, min: 1, max: 100, step: 1, tooltip: 'Number of bars to keep MACD cross signal in memory (used when Signal Memory is enabled)' }
      ]
    },
    supertrend: {
      title: 'SUPER TREND [FILTER] [SIGNAL]',
      fields: [
        { key: 'use_supertrend', label: 'Use SuperTrend?', type: 'checkbox' },
        { key: 'generate_on_trend_change', label: 'Generate Signals on Trend Change?', type: 'checkbox', hasTooltip: true },
        { key: 'use_btc_source', label: 'Use BTCUSDT as Source for SuperTrend?', type: 'checkbox' },
        { key: 'opposite_signal', label: 'Opposite SP Signal? (Sell on UPtrend..)', type: 'checkbox' },
        { key: 'show_supertrend', label: 'Show SuperTrend?', type: 'checkbox' },
        { key: 'period', label: 'SuperTrend ATR Period', type: 'number', optimizable: true },
        { key: 'multiplier', label: 'SuperTrend ATR Multiplier', type: 'number', step: 0.1, optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['hl2', 'hlc3', 'close'] },
        { key: 'timeframe', label: 'SuperTrend TimeFrame:', type: 'select', options: BYBIT_TF_OPTS }
      ]
    },
    qqe: {
      title: 'QQE Settings',
      fields: [
        { key: 'rsi_period', label: 'QQE RSI Length(14)', type: 'number', optimizable: true },
        { key: 'qqe_factor', label: 'Delta Multiplier(5.1)', type: 'number', optimizable: true },
        { key: 'smoothing_period', label: 'QQE RSI Smoothing(5)', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] },
        { key: 'timeframe', label: 'TimeFrame', type: 'select', options: BYBIT_TF_OPTS },
        { type: 'separator', label: '=============== QQE [SIGNALS] ==================' },
        { key: 'use_qqe', label: 'Use QQE ?', type: 'checkbox' },
        { key: 'opposite_qqe', label: 'Opposite QQE ?', type: 'checkbox' },
        { key: 'enable_qqe_visualization', label: 'Enable QQE Visualisation', type: 'checkbox' },
        { key: 'disable_qqe_signal_memory', label: 'Disable QQE Signal Memory', type: 'checkbox' },
        { key: 'qqe_signal_memory_bars', label: 'QQE Signal Memory Bars', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // UNIVERSAL FILTERS (new instruments)
    // =============================================
    atr_volatility: {
      title: '======== ATR VOLATILITY - [FILTER] ========',
      fields: [
        { key: 'use_atr_volatility', label: 'Use ATR1 <> ATR2 ?', type: 'checkbox' },
        { key: 'atr1_to_atr2', label: 'ATR1 to ATR2', type: 'select', options: ['ATR1 < ATR2', 'ATR1 > ATR2'], hasTooltip: true, tooltip: 'ATR1 < ATR2 — Volatility is Small in last bars. ATR1 > ATR2 — Volatility is High in last bars.' },
        { key: 'atr_diff_percent', label: 'How ATR1 > (<) ATR2. More than XX%', type: 'number', min: 0.1, max: 50, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Fast ATR1 is < Slow ATR2 for XX% or more.' },
        { key: 'atr_length1', label: 'ATR length1 (20)(5)', type: 'number', min: 5, max: 20, step: 1, optimizable: true },
        { key: 'atr_length2', label: 'ATR length2 (100)(20)', type: 'number', min: 20, max: 100, step: 1, optimizable: true },
        { key: 'atr_smoothing', label: 'ATR Smoothing', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] }
      ]
    },
    volume_filter: {
      title: '======== VOLUME [FILTER] ========',
      fields: [
        { key: 'use_volume_filter', label: 'Use VOL1 <> VOL2 ?', type: 'checkbox' },
        { key: 'vol1_to_vol2', label: 'VOL1 to VOL2', type: 'select', options: ['VOL1 < VOL2', 'VOL1 > VOL2'], hasTooltip: true, tooltip: 'VOL1 < VOL2 — Volume is Small in last bars. VOL1 > VOL2 — Volume is High in last bars.' },
        { key: 'vol_diff_percent', label: 'How VOL1 > (<) VOL2. More than XX%', type: 'number', min: 0.1, max: 50, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Fast VOL1 is < Slow VOL2 for XX% or more.' },
        { key: 'vol_length1', label: 'VOL length1 (20)(5)', type: 'number', min: 5, max: 20, step: 1, optimizable: true },
        { key: 'vol_length2', label: 'VOL length2 (100)(20)', type: 'number', min: 20, max: 100, step: 1, optimizable: true },
        { key: 'vol_smoothing', label: 'VOL Smoothing', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] }
      ]
    },
    highest_lowest_bar: {
      title: '======== HIGHEST LOWEST BAR - [SIGNALS] ========',
      fields: [
        { key: 'use_highest_lowest', label: 'Use Highest/Lowest Bar ?', type: 'checkbox', hasTooltip: true, tooltip: 'Make signal only if Current Bar is Highest/Lowest for last XX bars.' },
        { key: 'hl_lookback_bars', label: 'Is now Highest/Lowest Bar for last XX bars ?', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        {
          type: 'inline',
          fields: [
            { key: 'hl_price_percent', label: 'More/Less: Price on (%)', type: 'number', width: '80px', min: 0, max: 30, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Price is Higher/Lower on Y% than XX bars ago. If = 0 — this condition is disabled.' },
            { key: 'hl_atr_percent', label: 'ATR on (%)', type: 'number', width: '80px', min: 0, max: 30, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'ATR for last 2 bars is Higher/Lower on X% than ATR for last 50 bars. If = 0 — this condition is disabled.' }
          ]
        },
        { key: 'atr_hl_length', label: 'ATR_HL Length (50)', type: 'number', min: 1, max: 50, step: 1, optimizable: true },
        { type: 'separator', label: '======= BLOCK IF WORSE THAN [FILTER] =======' },
        { key: 'use_block_worse_than', label: 'Use Block if Worse Than ?', type: 'checkbox', hasTooltip: true, tooltip: 'Does not permit the order if Current Price is worse by more than XX% compared to Previous bar close. Long: order if current price higher than prev bar but not higher than XX%. Short: order if current price lower than prev bar but not lower than XX%.' },
        { key: 'block_worse_percent', label: 'Block if worse than XX%', type: 'number', min: 0.1, max: 30, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Maximum allowable percentage of price change in the adverse direction from the previous bar.' }
      ]
    },
    two_mas: {
      title: '========== TWO MAS NEW [SIGNALS AND FILTER] ==========',
      fields: [
        { key: 'ma1_length', label: 'Moving Average 1 length (50)', type: 'number', min: 1, max: 500, step: 1, optimizable: true },
        { key: 'ma1_smoothing', label: 'MA 1 Smoothing Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'RMA'] },
        { key: 'ma1_source', label: 'MA1 Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4', 'hlcc4'] },
        { key: 'ma2_length', label: 'Moving Average 2 length (100)', type: 'number', min: 1, max: 500, step: 1, optimizable: true },
        { key: 'ma2_smoothing', label: 'MA 2 Smoothing Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'RMA'] },
        { key: 'ma2_source', label: 'MA2 Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4', 'hlcc4'] },
        { key: 'show_two_mas', label: 'Show TWO MAs. (MA1 - green, MA2 - red)', type: 'checkbox', hasTooltip: true, tooltip: 'Two different MAs, Fast and Slow' },
        { key: 'two_mas_timeframe', label: 'TWO MAs TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { type: 'separator', label: '======= Use MA1 / MA2 Cross =======' },
        { key: 'use_ma_cross', label: 'Use MA1 / MA2 Cross', type: 'checkbox', hasTooltip: true, tooltip: 'Make Long Signal if MA1/MA2 cross from Down to UP. Make Short Signal if MA1/MA2 cross from UP to Down.' },
        { key: 'opposite_ma_cross', label: 'Opposite Signal - "MA1 / MA2 Cross"', type: 'checkbox', hasTooltip: true, tooltip: 'Reverse Direction of Signals. Go Long if MA1/MA2 cross from UP to Down. Go Short if MA1/MA2 cross from Down to UP.' },
        { key: 'activate_ma_cross_memory', label: 'Activate "MA1 / MA2 Cross" Signal Memory', type: 'checkbox', hasTooltip: true, tooltip: 'Keep Signal in Memory and execute when other conditions are met.' },
        { key: 'ma_cross_memory_bars', label: 'Keep "MA1 / MA2 Cross" Signal Memory for XX bars', type: 'number', min: 1, max: 100, step: 1, optimizable: true, hasTooltip: true, tooltip: 'How long to Keep Signal in Memory' },
        { type: 'separator', label: '===== Use MA1 as Filter. Long if Price > MA 1 =====' },
        { key: 'use_ma1_filter', label: 'Use MA1 as Filter. Long if Price > MA 1', type: 'checkbox', hasTooltip: true, tooltip: 'Filter. Allow Long if Price > MA 1. Allow Short if Price < MA 1' },
        { key: 'opposite_ma1_filter', label: 'Opposite Signal - "MA1 as Filter"', type: 'checkbox', hasTooltip: true, tooltip: 'Reverse Direction. Allow Long if Price < MA 1. Allow Short if Price > MA 1' }
      ]
    },
    accumulation_areas: {
      title: '***** ACCUMULATION AREAS - [FILTER] OR [SIGNAL] *****',
      fields: [
        { key: 'use_accumulation', label: 'Use Accumulation Areas ?', type: 'checkbox', hasTooltip: true, tooltip: 'As Filter: Allow orders only if price is in Accumulation Areas. Enable, see chart and change settings.' },
        { key: 'backtracking_interval', label: 'Backtracking Interval', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'min_bars_to_execute', label: 'Min Bars to Execute Order', type: 'number', min: 1, max: 100, step: 1, optimizable: true, hasTooltip: true, tooltip: 'Minimal amount of bars in Accumulation to allow order Execution' },
        { key: 'signal_on_breakout', label: 'Signal on Accumulation BreakOut ?', type: 'checkbox' },
        { key: 'signal_on_opposite_breakout', label: 'Signal on BreakOut-Opposite Direction ?', type: 'checkbox' }
      ]
    },
    keltner_bollinger: {
      title: '======== KELTNER/BOLLINGER CHANNEL - [FILTER] ========',
      fields: [
        { key: 'use_channel', label: 'Use Channel ?', type: 'checkbox', hasTooltip: true, tooltip: 'Make order if bar is outside of Channel' },
        { key: 'channel_timeframe', label: 'Channel TimeFrame', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'channel_mode', label: 'BB/KC Channel Breackout or Rebound from bands:', type: 'select', options: ['Rebound', 'Breackout'] },
        { key: 'channel_type', label: 'Channel to Use:', type: 'select', options: ['Bollinger Bands', 'Keltner Channel'] },
        { key: 'enter_conditions', label: 'Enter Conditions', type: 'select', options: ['Out-of-band closure', 'Wick out of band', 'Wick out of the band then close in', 'Close out of the band then close in'] },
        { key: 'keltner_length', label: 'Keltner Long.', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true },
        { key: 'keltner_mult', label: 'Keltner Mult.', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true },
        { key: 'bb_length', label: 'BB Long.', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true },
        { key: 'bb_deviation', label: 'BB Deviation (Desv.)', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true }
      ]
    },
    rvi_filter: {
      title: '======== RVI - RELATIVE VOLATILITY INDEX [FILTER] ========',
      fields: [
        { key: 'rvi_length', label: 'RVI Long(10):', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'rvi_timeframe', label: 'RVI TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'rvi_ma_type', label: 'RVI MA Type', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] },
        { key: 'rvi_ma_length', label: 'RVI MA Length(2)', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { type: 'separator', label: '=== RVI LONG Range ===' },
        { key: 'use_rvi_long_range', label: 'Use RVI LONG Range', type: 'checkbox' },
        { key: 'rvi_long_more', label: '(LONG) RVI is More', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'rvi_long_less', label: '& RVI Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { type: 'separator', label: '=== RVI SHORT Range ===' },
        { key: 'use_rvi_short_range', label: 'Use RVI SHORT Range', type: 'checkbox' },
        { key: 'rvi_short_less', label: '(SHORT) RVI is Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'rvi_short_more', label: '& RVI More', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true }
      ]
    },
    mfi_filter: {
      title: '======== MONEY FLOW INDEX [FILTER] ========',
      fields: [
        { key: 'mfi_length', label: 'MFI TF Long:', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'mfi_timeframe', label: 'MFI TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'use_btcusdt_mfi', label: 'Use BTCUSDT as Source for MFI ?', type: 'checkbox', hasTooltip: true, tooltip: 'Use BTCUSDT price data as source for MFI calculation' },
        { type: 'separator', label: '=== MFI LONG Range ===' },
        { key: 'use_mfi_long_range', label: 'Use MFI LONG Range', type: 'checkbox' },
        { key: 'mfi_long_more', label: '(LONG) MFI is More', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'mfi_long_less', label: '& MFI Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { type: 'separator', label: '=== MFI SHORT Range ===' },
        { key: 'use_mfi_short_range', label: 'Use MFI SHORT Range', type: 'checkbox' },
        { key: 'mfi_short_less', label: '(SHORT) MFI is Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'mfi_short_more', label: '& MFI More', type: 'number', min: 1, max: 100, step: 1, optimizable: true, inline: true }
      ]
    },
    cci_filter: {
      title: '======== CCI - [FILTER] ========',
      fields: [
        { key: 'cci_length', label: 'CCI TF Long(14):', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'cci_timeframe', label: 'CCI TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { type: 'separator', label: '=== CCI LONG Range (-400:400) ===' },
        { key: 'use_cci_long_range', label: 'Use CCI LONG Range (-400:400)', type: 'checkbox' },
        { key: 'cci_long_more', label: '(LONG) CCI is More', type: 'number', min: -400, max: 400, step: 1, optimizable: true, inline: true },
        { key: 'cci_long_less', label: '& CCI Less', type: 'number', min: -400, max: 400, step: 1, optimizable: true, inline: true },
        { type: 'separator', label: '=== CCI SHORT Range (400:-400) ===' },
        { key: 'use_cci_short_range', label: 'Use CCI SHORT Range (400:-400)', type: 'checkbox' },
        { key: 'cci_short_less', label: '(SHORT) CCI is Less', type: 'number', min: -400, max: 400, step: 1, optimizable: true, inline: true },
        { key: 'cci_short_more', label: '& CCI More', type: 'number', min: -400, max: 400, step: 1, optimizable: true, inline: true }
      ]
    },
    momentum_filter: {
      title: '======== MOMENTUM - [FILTER] ========',
      fields: [
        { key: 'momentum_length', label: 'Momentum TF Long(14):', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'momentum_timeframe', label: 'Momentum TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'use_btcusdt_momentum', label: 'Use BTCUSDT as Source for Momentum ?', type: 'checkbox', hasTooltip: true, tooltip: 'Use BTCUSDT price data as source for Momentum calculation' },
        { key: 'momentum_source', label: 'Momentum Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4', 'hlcc4'] },
        { type: 'separator', label: '=== Momentum LONG Range (-100:100) ===' },
        { key: 'use_momentum_long_range', label: 'Use Momentum LONG Range (-100:100)', type: 'checkbox' },
        { key: 'momentum_long_more', label: '(LONG) Momentum is More', type: 'number', min: -100, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'momentum_long_less', label: '& Mom Less', type: 'number', min: -100, max: 100, step: 1, optimizable: true, inline: true },
        { type: 'separator', label: '=== Momentum SHORT Range (100:-100) ===' },
        { key: 'use_momentum_short_range', label: 'Use Momentum SHORT Range (100:-100)', type: 'checkbox' },
        { key: 'momentum_short_less', label: '(SHORT) Momentum is Less', type: 'number', min: -100, max: 100, step: 1, optimizable: true, inline: true },
        { key: 'momentum_short_more', label: '& Mom More', type: 'number', min: -100, max: 100, step: 1, optimizable: true, inline: true }
      ]
    },

    // =============================================
    // NEW INDICATOR BLOCKS
    // =============================================
    stoch_rsi: {
      title: '======== StochRSI - [OSCILLATOR] ========',
      fields: [
        { key: 'rsi_period', label: 'RSI Period (14):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 },
        { key: 'stoch_period', label: 'Stoch Period (14):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 },
        { key: 'k_period', label: '%K Smoothing (3):', type: 'number', optimizable: true, min: 1, max: 50, step: 1 },
        { key: 'd_period', label: '%D Smoothing (3):', type: 'number', optimizable: true, min: 1, max: 50, step: 1 },
        { key: 'source', label: 'Source:', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] }
      ]
    },
    cci: {
      title: '======== CCI - [COMMODITY CHANNEL INDEX] ========',
      fields: [
        { key: 'period', label: 'CCI Period (20):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 }
      ]
    },
    adx: {
      title: '======== ADX - [AVERAGE DIRECTIONAL INDEX] ========',
      fields: [
        { key: 'period', label: 'ADX Period (14):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 }
      ]
    },
    parabolic_sar: {
      title: '======== Parabolic SAR ========',
      fields: [
        { key: 'start', label: 'AF Start (0.02):', type: 'number', optimizable: true, min: 0.001, max: 0.5, step: 0.001 },
        { key: 'increment', label: 'AF Increment (0.02):', type: 'number', optimizable: true, min: 0.001, max: 0.5, step: 0.001 },
        { key: 'max_value', label: 'AF Max (0.2):', type: 'number', optimizable: true, min: 0.01, max: 1.0, step: 0.01 }
      ]
    },
    sma: {
      title: '======== SMA - [SIMPLE MOVING AVERAGE] ========',
      fields: [
        { key: 'period', label: 'SMA Period (50):', type: 'number', optimizable: true, min: 1, max: 500, step: 1 },
        { key: 'source', label: 'Source:', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] }
      ]
    },
    ema: {
      title: '======== EMA - [EXPONENTIAL MOVING AVERAGE] ========',
      fields: [
        { key: 'period', label: 'EMA Period (20):', type: 'number', optimizable: true, min: 1, max: 500, step: 1 },
        { key: 'source', label: 'Source:', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] }
      ]
    },
    bollinger: {
      title: '======== Bollinger Bands ========',
      fields: [
        { key: 'period', label: 'BB Period (20):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 },
        { key: 'std_dev', label: 'Std Dev Multiplier (2.0):', type: 'number', optimizable: true, min: 0.1, max: 10, step: 0.1 },
        { key: 'source', label: 'Source:', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] }
      ]
    },
    donchian: {
      title: '======== Donchian Channels ========',
      fields: [
        { key: 'period', label: 'Donchian Period (20):', type: 'number', optimizable: true, min: 2, max: 200, step: 1 }
      ]
    },
    ichimoku: {
      title: '======== Ichimoku Cloud ========',
      fields: [
        { key: 'tenkan_period', label: 'Tenkan-Sen Period (9):', type: 'number', optimizable: true, min: 1, max: 100, step: 1 },
        { key: 'kijun_period', label: 'Kijun-Sen Period (26):', type: 'number', optimizable: true, min: 1, max: 200, step: 1 },
        { key: 'senkou_b_period', label: 'Senkou Span B Period (52):', type: 'number', optimizable: true, min: 1, max: 300, step: 1 }
      ]
    },
    pivot_points: {
      title: '======== Pivot Points (Classic) ========',
      fields: [
        { type: 'separator', label: 'Outputs: PP, R1, R2, R3, S1, S2, S3 — use with Crossover/Crossunder conditions' }
      ]
    },
    obv: {
      title: '======== OBV - [ON-BALANCE VOLUME] ========',
      fields: [
        { type: 'separator', label: 'OBV — cumulative volume indicator (no params required)' }
      ]
    },
    vwap: {
      title: '======== VWAP - [VOLUME WEIGHTED AVERAGE PRICE] ========',
      fields: [
        { type: 'separator', label: 'VWAP — session-based volume weighted price (no params required)' }
      ]
    },
    ad_line: {
      title: '======== AD Line - [ACCUMULATION/DISTRIBUTION] ========',
      fields: [
        { type: 'separator', label: 'AD Line — cumulative A/D indicator (no params required)' }
      ]
    },

    // (Filters panels removed — entire Filters category deprecated)

    // =============================================
    // CONDITIONS
    // =============================================
    crossover: {
      title: 'Crossover Condition',
      fields: [
        { key: 'source_a', label: 'Source A', type: 'select', options: ['input_a', 'input_b', 'value'] },
        { key: 'source_b', label: 'Source B', type: 'select', options: ['input_a', 'input_b', 'value'] }
      ]
    },
    crossunder: {
      title: 'Crossunder Condition',
      fields: [
        { key: 'source_a', label: 'Source A', type: 'select', options: ['input_a', 'input_b', 'value'] },
        { key: 'source_b', label: 'Source B', type: 'select', options: ['input_a', 'input_b', 'value'] }
      ]
    },
    greater_than: {
      title: 'Greater Than Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'use_input', label: 'Use Input B', type: 'checkbox' }
      ]
    },
    less_than: {
      title: 'Less Than Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'use_input', label: 'Use Input B', type: 'checkbox' }
      ]
    },
    equals: {
      title: 'Equals Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'tolerance', label: 'Tolerance', type: 'number', optimizable: false }
      ]
    },
    between: {
      title: 'Between Condition',
      fields: [
        { key: 'min_value', label: 'Min Value', type: 'number', optimizable: true },
        { key: 'max_value', label: 'Max Value', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // CLOSE CONDITIONS (EXIT RULES)
    // =============================================
    close_by_time: {
      title: '=== CLOSE COND - CLOSE BY TIME SINCE ORDER ===',
      fields: [
        { key: 'enabled', label: 'Use Close By Time Since Order ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close position after N bars since entry' },
        { key: 'bars_since_entry', label: 'Close order after XX bars:', type: 'number', min: 1, max: 1000, step: 1, optimizable: true, hasTooltip: true, tooltip: 'Number of bars after entry to force close' },
        { key: 'profit_only', label: 'Close only with Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Only close by time if position is in profit' },
        { key: 'min_profit_percent', label: 'Min Profit percent for Close. %%', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Minimum profit % required before closing by time' }
      ]
    },
    static_sltp: {
      title: 'STATIC SL/TP',
      fields: [
        { key: 'take_profit_percent', label: 'Take Profit (%)', type: 'number', optimizable: true },
        { key: 'stop_loss_percent', label: 'Stop Loss (%)', type: 'number', optimizable: true },
        { key: 'sl_type', label: 'Тип стоп-лосса', type: 'select', options: ['average_price', 'last_order'], optionLabels: ['От средней цены', 'От последнего ордера'], selectStyle: 'min-width: 200px;' },
        { key: '_sep_advanced', label: 'Advanced', type: 'separator' },
        { key: 'close_only_in_profit', label: 'Close only in Profit', type: 'checkbox' },
        { key: 'activate_breakeven', label: 'Activate Breakeven?', type: 'checkbox' },
        { key: 'breakeven_activation_percent', label: '(%) to Activate Breakeven', type: 'number', optimizable: true },
        { key: 'new_breakeven_sl_percent', label: 'New Breakeven SL (%)', type: 'number', optimizable: true }
      ]
    },
    trailing_stop_exit: {
      title: 'TRAILING STOP',
      fields: [
        { key: 'activation_percent', label: 'Активация (% прибыли)', type: 'number', optimizable: true },
        { key: 'trailing_percent', label: 'Дистанция трейла (%)', type: 'number', optimizable: true },
        { key: 'trail_type', label: 'Тип трейлинга', type: 'select', options: ['percent', 'atr', 'points'], optionLabels: ['Процент', 'ATR', 'Пункты'], selectStyle: 'min-width: 200px;' }
      ]
    },
    atr_exit: {
      title: 'ATR-BASED EXIT',
      fields: [
        { type: 'separator', label: '======== ATR STOP LOSS ========' },
        { key: 'use_atr_sl', label: 'Use ATR Stop Loss ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close position if current Loss >= (Multiplier × ATR)' },
        { key: 'atr_sl_on_wicks', label: 'ATR SL work on Wicks ?', type: 'checkbox', hasTooltip: true, tooltip: 'If Disabled — ATR SL will be checked only after Close of current bar. Wicks are ignored. Use Static SL for protection.' },
        { key: 'atr_sl_smoothing', label: 'ATR SL Smoothing Method', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'], optionLabels: ['WMA', 'RMA', 'SMA', 'EMA'], selectStyle: 'min-width: 120px;' },
        { key: 'atr_sl_period', label: 'ATR SL Smoothing Period', type: 'number', min: 1, max: 150, optimizable: true },
        { key: 'atr_sl_multiplier', label: 'Size of ATR SL (Multiplier×ATR)', type: 'number', min: 0.1, max: 4, step: 0.1, optimizable: true },
        { type: 'separator', label: '======== ATR TAKE PROFIT ========' },
        { key: 'use_atr_tp', label: 'Use ATR Take Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close position if current Profit >= (Multiplier × ATR)' },
        { key: 'atr_tp_on_wicks', label: 'ATR TP work on Wicks ?', type: 'checkbox', hasTooltip: true, tooltip: 'If Disabled — ATR TP will be checked only after Close of current bar. Wicks are ignored.' },
        { key: 'atr_tp_smoothing', label: 'ATR TP Smoothing Method', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'], optionLabels: ['WMA', 'RMA', 'SMA', 'EMA'], selectStyle: 'min-width: 120px;' },
        { key: 'atr_tp_period', label: 'ATR TP Smoothing Period', type: 'number', min: 1, max: 150, optimizable: true },
        { key: 'atr_tp_multiplier', label: 'Size of ATR TP (Multiplier×ATR)', type: 'number', min: 0.1, max: 4, step: 0.1, optimizable: true }
      ]
    },
    multi_tp_exit: {
      title: 'MULTI TAKE PROFIT LEVELS',
      fields: [
        { type: 'separator', label: '------- TP1 -------' },
        { key: 'tp1_percent', label: 'TP1 Target %', type: 'number', optimizable: true },
        { key: 'tp1_close_percent', label: 'TP1 Close %', type: 'number', optimizable: false },
        { type: 'separator', label: '------- TP2 -------' },
        { key: 'use_tp2', label: 'Use TP2', type: 'checkbox' },
        { key: 'tp2_percent', label: 'TP2 Target %', type: 'number', optimizable: true },
        { key: 'tp2_close_percent', label: 'TP2 Close %', type: 'number', optimizable: false },
        { type: 'separator', label: '------- TP3 -------' },
        { key: 'use_tp3', label: 'Use TP3', type: 'checkbox' },
        { key: 'tp3_percent', label: 'TP3 Target %', type: 'number', optimizable: true },
        { key: 'tp3_close_percent', label: 'TP3 Close %', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // CLOSE CONDITIONS
    // =============================================
    close_channel: {
      title: '=== CLOSE CONDITION - CHANNELS KELTNER/BOLLINGER ===',
      fields: [
        { key: 'enabled', label: 'Use Channels CLOSE COND ?', type: 'checkbox', hasTooltip: true, tooltip: 'CLOSE if bar is outside of Channel' },
        { key: 'channel_close_timeframe', label: 'Channel CLOSE TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'band_to_close', label: 'Band to Close Position:', type: 'select', options: ['Rebound', 'Breakout'], hasTooltip: true, tooltip: 'Rebound (default): For LONG orders — close on UPPER band. Breakout: For LONG orders — close on LOWER band.' },
        { key: 'channel_type', label: 'Channel to Use for CLOSE:', type: 'select', options: ['Keltner Channel', 'Bollinger Bands'] },
        { key: 'close_condition', label: 'CLOSE Conditions', type: 'select', options: ['Close out of the band then close in', 'Wick out of band', 'Wick out of the band then close in', 'Out-of-band closure'] },
        { key: 'keltner_length', label: 'Keltner Long. (CLOSE)', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'keltner_mult', label: 'Keltner Mult. (CLOSE)', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true },
        { key: 'bb_length', label: 'BB Long. (CLOSE)', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'bb_deviation', label: 'BB Deviation (CLOSE)', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true }
      ]
    },
    close_ma_cross: {
      title: '=========== TWO MAS [CLOSE CONDITION] ===========',
      fields: [
        { key: 'enabled', label: 'Activate MA1 / MA2 Cross CLOSE Condition', type: 'checkbox', hasTooltip: true, tooltip: 'Make Long Signal if MA1 / MA2 cross from Down to UP. Make Short Signal if MA1 / MA2 cross from UP to Down.' },
        { key: 'show_ma_lines', label: 'Show TWO MAs. CLO (MA1 - green, MA2 - red)', type: 'checkbox', hasTooltip: true, tooltip: 'Two different MAs, Fast and Slow' },
        { key: 'profit_only', label: 'Close by MA Cross only with Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'min_profit_percent', label: 'Min Profit percent for Close by MA Cross. %%', type: 'number', min: 0.1, max: 50, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'ma1_length', label: 'MA 1 CLO length (10)', type: 'number', min: 1, max: 500, step: 1, optimizable: true },
        { key: 'ma2_length', label: 'MA 2 CLO length (30)', type: 'number', min: 1, max: 500, step: 1, optimizable: true }
      ]
    },
    close_rsi: {
      title: '======= CLOSE CONDITION - CLOSE BY RSI =======',
      fields: [
        { key: 'rsi_close_length', label: 'RSI CLOSE Length (14):', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { key: 'rsi_close_timeframe', label: 'RSI CLOSE TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'rsi_close_profit_only', label: 'Close by RSI only with Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'rsi_close_min_profit', label: 'Min Profit percent for Close by RSI. %%', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { type: 'separator', label: '====== Activate RSI CLOSE (Reach the Level) ======' },
        { key: 'activate_rsi_reach', label: 'Activate RSI CLOSE (Reach the Level)', type: 'checkbox' },
        { key: 'rsi_long_more', label: '(LONG) RSI_CL is More', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'rsi_long_less', label: '& RSI_CL Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'rsi_short_less', label: '(SHORT) RSI_CL is Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'rsi_short_more', label: '& RSI_CL More', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { type: 'separator', label: '====== Activate RSI CLOSE (Cross the Level) ======' },
        { key: 'activate_rsi_cross', label: 'Activate RSI CLOSE (Cross the Level)', type: 'checkbox', hasTooltip: true, tooltip: 'Close Long Position if RSI Crossed the Level from UP to Down. Close Short Position if RSI Crossed the Level from Down to UP.' },
        { key: 'rsi_cross_long_level', label: 'Level to Cross RSI for LONG', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'rsi_cross_short_level', label: 'Level to Cross RSI for SHORT', type: 'number', min: 1, max: 100, step: 1, optimizable: true }
      ]
    },
    close_stochastic: {
      title: '======= CLOSE CONDITION - CLOSE BY STOCHASTIC =======',
      fields: [
        { key: 'stoch_close_k_length', label: 'Stochastic CL %K Length (14)', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { key: 'stoch_close_k_smoothing', label: 'Stochastic CL %K Smoothing (3)', type: 'number', min: 1, max: 50, step: 1, optimizable: true },
        { key: 'stoch_close_d_smoothing', label: 'Stochastic CL %D Smoothing (3)', type: 'number', min: 1, max: 50, step: 1, optimizable: true },
        { key: 'stoch_close_timeframe', label: 'Stochastic CL TimeFrame:', type: 'select', options: BYBIT_TF_OPTS },
        { key: 'stoch_close_profit_only', label: 'Close by STOCH only with Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'stoch_close_min_profit', label: 'Min Profit percent for Close by STOCH. %%', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { type: 'separator', label: '====== Activate STOCH CLOSE (Reach the Level) ======' },
        { key: 'activate_stoch_reach', label: 'Activate STOCH CLOSE (Reach the Level)', type: 'checkbox' },
        { key: 'stoch_long_more', label: '(LONG) Stoch_CL is More', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'stoch_long_less', label: '& Stoch_CL Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'stoch_short_less', label: '(SHORT) Stoch_CL is Less', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'stoch_short_more', label: '& Stoch_CL More', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { type: 'separator', label: '====== Activate STOCH CLOSE (Cross the Level) ======' },
        { key: 'activate_stoch_cross', label: 'Activate STOCH CLOSE (Cross the Level)', type: 'checkbox', hasTooltip: true, tooltip: 'Close Long Position if STOCH Crossed the Level from UP to Down. Close Short Position if STOCH Crossed the Level from Down to UP.' },
        { key: 'stoch_cross_long_level', label: 'Level to Cross Stoch for LONG', type: 'number', min: 1, max: 100, step: 1, optimizable: true },
        { key: 'stoch_cross_short_level', label: 'Level to Cross Stoch for SHORT', type: 'number', min: 1, max: 100, step: 1, optimizable: true }
      ]
    },
    close_psar: {
      title: '======= CLOSE CONDITION - PARABOLIC SAR SIGNALS =======',
      fields: [
        { key: 'enabled', label: 'Use CLOSE CONDITION Parabolic SAR Signals ?', type: 'checkbox' },
        { key: 'psar_opposite', label: 'Opposite Parabolic SAR CLOSE COND ?', type: 'checkbox' },
        { key: 'psar_close_profit_only', label: 'Close by PSAR only with Profit ?', type: 'checkbox', hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'psar_close_min_profit', label: 'Min Profit percent for Close by PSAR. %%', type: 'number', min: 0.1, max: 100, step: 0.1, optimizable: true, hasTooltip: true, tooltip: 'Close only with Profit XX%' },
        { key: 'psar_start', label: 'Start PSAR (0.02)', type: 'number', min: 0.001, max: 1, step: 0.001, optimizable: true },
        { key: 'psar_increment', label: 'Increment PSAR (0.02)', type: 'number', min: 0.001, max: 1, step: 0.001, optimizable: true },
        { key: 'psar_maximum', label: 'Maximum PSAR (0.2)', type: 'number', min: 0.01, max: 5, step: 0.01, optimizable: true },
        { key: 'psar_close_nth_bar', label: 'Close on Nth trend bar', type: 'number', min: 1, max: 100, step: 1, optimizable: true }
      ]
    },

    // =============================================
    // ENTRY MANAGEMENT (DCA / Grid)
    // =============================================
    dca: {
      title: 'DCA (Dollar Cost Averaging)',
      fields: [
        { key: 'grid_size_percent', label: 'Перекрытие / Grid Size (0.5-99%)', type: 'number', step: 0.5, min: 0.5, max: 99, optimizable: true },
        { key: 'order_count', label: 'Перекрытие / Orders in grid (2-20)', type: 'number', step: 1, min: 2, max: 20, optimizable: true },
        { key: 'martingale_coefficient', label: '% Мартингейла / Martingale (1-200%)', type: 'number', step: 1, min: 1, max: 200, optimizable: true },
        { key: 'log_steps_coefficient', label: 'Лог. распределение / Log Steps (0.1-2.9)', type: 'number', step: 0.1, min: 0.1, max: 2.9, optimizable: true },
        { key: 'first_order_offset', label: 'Отступ / Indent (0=По маркету/Market, 0.01-10%)', type: 'number', step: 0.01, min: 0, max: 10, optimizable: true },
        { key: 'partial_grid_orders', label: 'Частичное выставление сетки / Partial Grid (1-4)', type: 'number', step: 1, min: 1, max: 4, optimizable: false },
        { key: 'grid_pullback_percent', label: 'Подтяжка сетки ордеров / Grid Pullback (0=выкл, 0.1-200%)', type: 'number', step: 0.1, min: 0, max: 200, optimizable: true },
        { key: 'grid_trailing', label: 'Grid Trailing / Cancel (0.1-30%)', type: 'number', step: 0.1, min: 0, max: 30, optimizable: true }
      ]
    },
    grid_orders: {
      title: 'Manual Grid Orders',
      customRenderer: 'grid_orders', // Special renderer for dynamic order list
      fields: [] // Handled by custom renderer
    },

    // =============================================
    // DIVERGENCE DETECTION
    // =============================================
    divergence: {
      title: '===== DIVERGENCE DETECTION =====',
      fields: [
        { type: 'separator', label: '======== General Settings ========' },
        { key: 'pivot_interval', label: 'Pivot Interval (1-9)', type: 'number', min: 1, max: 9, step: 1, optimizable: true },
        { key: 'act_without_confirmation', label: 'Act Without Confirmation', type: 'checkbox', hasTooltip: true, tooltip: 'More signals, more false signals' },
        { key: 'show_divergence_lines', label: 'Show Divergence Lines', type: 'checkbox' },
        { key: 'activate_diver_signal_memory', label: 'Activate Divergence Signal Memory', type: 'checkbox', hasTooltip: true, tooltip: 'Keep Signal in Memory and execute when other conditions are met' },
        { key: 'keep_diver_signal_memory_bars', label: 'Keep Signal Memory (bars)', type: 'number', min: 1, max: 100, step: 1, optimizable: true, hasTooltip: true, tooltip: 'How long to Keep Signal in Memory' },
        { type: 'separator', label: '======== RSI Divergence ========' },
        { key: 'use_divergence_rsi', label: 'Use RSI Divergence', type: 'checkbox' },
        { key: 'rsi_period', label: 'RSI Period', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { type: 'separator', label: '======== Stochastic Divergence ========' },
        { key: 'use_divergence_stochastic', label: 'Use Stochastic Divergence', type: 'checkbox' },
        { key: 'stoch_length', label: 'Stochastic Length', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { type: 'separator', label: '======== Momentum Divergence ========' },
        { key: 'use_divergence_momentum', label: 'Use Momentum Divergence', type: 'checkbox' },
        { key: 'momentum_length', label: 'Momentum Length', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { type: 'separator', label: '======== CMF Divergence ========' },
        { key: 'use_divergence_cmf', label: 'Use CMF Divergence', type: 'checkbox' },
        { key: 'cmf_period', label: 'CMF Period', type: 'number', min: 1, max: 200, step: 1, optimizable: true },
        { type: 'separator', label: '======== OBV Divergence ========' },
        { key: 'use_obv', label: 'Use OBV Divergence', type: 'checkbox' },
        { type: 'separator', label: '======== MFI Divergence ========' },
        { key: 'use_mfi', label: 'Use MFI Divergence', type: 'checkbox' },
        { key: 'mfi_length', label: 'MFI Length', type: 'number', min: 1, max: 200, step: 1, optimizable: true }
      ]
    }
  };

  const layout = customLayouts[block.type];
  if (!layout) return null;

  // Special renderer for grid_orders (Manual Grid)
  if (layout.customRenderer === 'grid_orders') {
    return renderGridOrdersPanel(block, blockId, optimizationMode);
  }

  // Helper to render a complete optimization row (label + checkbox + range inputs)
  // fieldMin/fieldMax/fieldStep: field-level constraints used as defaults when no saved opt config exists
  const renderOptRow = (key, label, value, fieldMin, fieldMax, fieldStep) => {
    const saved = optParams[key];
    let opt;
    if (!saved) {
      // No saved config — use field constraints as sensible defaults
      opt = { enabled: false, min: fieldMin ?? value, max: fieldMax ?? value, step: fieldStep ?? 1 };
    } else if (saved.min === saved.max && saved.min == value && (fieldMin !== undefined || fieldMax !== undefined)) {
      // Auto-initialized with current value only (degenerate range) — replace with field defaults.
      // ALSO update optParams in-memory so that strategies loaded from DB get corrected immediately
      // (without user needing to re-open the popup before clicking Start Optimization).
      opt = { enabled: saved.enabled || false, min: fieldMin ?? value, max: fieldMax ?? value, step: fieldStep ?? saved.step ?? 1 };
      optParams[key] = opt;
    } else {
      opt = saved;
    }
    const disabled = opt.enabled ? '' : 'disabled';
    const fMin = fieldMin ?? '';
    const fMax = fieldMax ?? '';
    const fStep = fieldStep ?? 1;
    return `
      <div class="tv-opt-row" data-param-key="${key}">
        <input type="checkbox"
               class="tv-opt-checkbox"
               data-param-key="${key}"
               data-field-min="${fMin}"
               data-field-max="${fMax}"
               data-field-step="${fStep}"
               ${opt.enabled ? 'checked' : ''}>
        <span class="tv-opt-label">${label}</span>
        <div class="tv-opt-controls">
          <input type="number" class="tv-opt-input" value="${opt.min}" data-opt-field="min" data-param-key="${key}" ${disabled}>
          <span class="tv-opt-arrow">→</span>
          <input type="number" class="tv-opt-input" value="${opt.max}" data-opt-field="max" data-param-key="${key}" ${disabled}>
          <span class="tv-opt-slash">/</span>
          <input type="number" class="tv-opt-input tv-opt-step" value="${opt.step}" data-opt-field="step" data-param-key="${key}" step="any" ${disabled}>
        </div>
      </div>
    `;
  };

  let html = '<div class="tv-params-container">';

  // Header - only show if showHeader is true
  if (showHeader && layout.title && !optimizationMode) {
    html += `<div class="tv-params-header">${layout.title}</div>`;
  }

  // Optimization mode header - only show if showHeader is true
  if (showHeader && optimizationMode) {
    html += `<div class="tv-params-header">Optimization: ${layout.title || block.name}</div>`;
  }

  // Fields
  layout.fields.forEach(field => {
    // Separator - visual divider with label
    if (field.type === 'separator') {
      if (!optimizationMode) {
        html += `
          <div class="tv-param-separator">
            <span class="tv-separator-label">${field.label || ''}</span>
          </div>
        `;
      }
      return;
    }

    // Divider - section header (similar to separator but styled differently)
    if (field.type === 'divider') {
      if (!optimizationMode) {
        html += `
          <div class="tv-param-divider" style="text-align:center;color:#888;font-size:11px;padding:6px 0 2px;border-top:1px solid #333;margin-top:6px;">
            ${field.label || ''}
          </div>
        `;
      }
      return;
    }

    // Conditional visibility: hide field if showWhen param is falsy
    const showWhenKey = field.showWhen;
    if (showWhenKey && !params[showWhenKey]) {
      return;
    }

    if (field.type === 'inline' && !optimizationMode) {
      // Inline row - only in default mode
      html += '<div class="tv-param-row tv-inline-row">';
      field.fields.forEach(f => {
        if (f.type === 'label') {
          html += `<span class="tv-inline-label">${f.label}</span>`;
        } else if (f.type === 'number') {
          const val = params[f.key] ?? '';
          const stepAttr = f.step ? `step="${f.step}"` : '';
          const minAttr = f.min !== undefined ? `min="${f.min}"` : '';
          const maxAttr = f.max !== undefined ? `max="${f.max}"` : '';
          html += `
            ${f.label ? `<span class="tv-inline-label">${f.label}</span>` : ''}
            <input type="number"
                   class="tv-input tv-input-inline"
                   style="width: ${f.width || '80px'}"
                   value="${val}"
                   ${stepAttr} ${minAttr} ${maxAttr}
                   data-block-id="${blockId}"
                   data-param-key="${f.key}">
          `;
        }
      });
      html += '</div>';
    } else if (field.type === 'inline' && optimizationMode) {
      // In optimization mode, render inline fields as separate opt rows (pass field constraints as defaults)
      field.fields.forEach(f => {
        if (f.type === 'number' && f.optimizable) {
          const val = params[f.key] ?? 0;
          const label = f.label || formatParamName(f.key);
          html += renderOptRow(f.key, label, val, f.min, f.max, f.step);
        }
      });
    } else if (field.type === 'checkbox' && !optimizationMode) {
      const checked = params[field.key] ? 'checked' : '';
      const tooltipHtml = field.tooltip
        ? `<i class="bi bi-info-circle tv-tooltip-icon" title="${field.tooltip}"></i>`
        : (field.hasTooltip ? '<i class="bi bi-info-circle tv-tooltip-icon"></i>' : '');
      html += `
        <div class="tv-param-row tv-checkbox-row">
          <label class="tv-checkbox-label">
            <input type="checkbox"
                   class="tv-checkbox"
                   data-block-id="${blockId}"
                   data-param-key="${field.key}"
                   ${checked}>
            ${field.label}
            ${tooltipHtml}
          </label>
        </div>
      `;
    } else if (field.type === 'select' && !optimizationMode) {
      const val = (params[field.key] ?? '').toString().toLowerCase();
      html += `
        <div class="tv-param-row">
          <label class="tv-label">${field.label}</label>
          <select class="tv-select"
                  data-block-id="${blockId}"
                  data-param-key="${field.key}"
                  style="${field.selectStyle || ''}">
            ${field.options.map((opt, idx) => {
        const displayLabel = field.optionLabels ? field.optionLabels[idx] : opt;
        return `<option value="${opt}" ${val === opt.toLowerCase() ? 'selected' : ''}>${displayLabel}</option>`;
      }).join('')}
          </select>
        </div>
      `;
    } else if (field.type === 'number') {
      const val = params[field.key] ?? '';

      if (optimizationMode && field.optimizable) {
        // Optimization mode - use complete opt row (pass field constraints as defaults)
        html += renderOptRow(field.key, field.label, val, field.min, field.max, field.step);
      } else if (!optimizationMode) {
        // Default mode - show single input with step, min, max attributes
        const stepAttr = field.step ? `step="${field.step}"` : '';
        const minAttr = field.min !== undefined ? `min="${field.min}"` : '';
        const maxAttr = field.max !== undefined ? `max="${field.max}"` : '';
        html += `
          <div class="tv-param-row">
            <label class="tv-label">${field.label}</label>
            <input type="number"
                   class="tv-input"
                   value="${val}"
                   ${stepAttr} ${minAttr} ${maxAttr}
                   data-block-id="${blockId}"
                   data-param-key="${field.key}">
            ${field.hasTooltip ? '<i class="bi bi-info-circle tv-tooltip-icon"></i>' : ''}
          </div>
        `;
      }
    }
  }); html += '</div>';
  return html;
}

// Get port configuration based on block type
function getBlockPorts(blockId, _category) {
  const portConfigs = {
    // Indicators - output data
    rsi: {
      inputs: [],
      outputs: [
        { id: 'value', label: 'Value', type: 'data' },
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    macd: {
      inputs: [],
      outputs: [
        { id: 'macd', label: 'MACD', type: 'data' },
        { id: 'signal', label: 'Signal', type: 'data' },
        { id: 'histogram', label: 'Hist', type: 'data' },
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    ema: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    sma: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    bollinger: {
      inputs: [],
      outputs: [
        { id: 'upper', label: 'Upper', type: 'data' },
        { id: 'middle', label: 'Mid', type: 'data' },
        { id: 'lower', label: 'Lower', type: 'data' }
      ]
    },
    atr: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    stochastic: {
      inputs: [],
      outputs: [
        { id: 'k', label: '%K', type: 'data' },
        { id: 'd', label: '%D', type: 'data' },
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    adx: { inputs: [], outputs: [{ id: 'value', label: 'ADX', type: 'data' }] },
    supertrend: {
      inputs: [],
      outputs: [
        { id: 'supertrend', label: 'ST', type: 'data' },
        { id: 'direction', label: 'Dir', type: 'data' },
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    ichimoku: {
      inputs: [],
      outputs: [
        { id: 'tenkan_sen', label: 'TK', type: 'data' },
        { id: 'kijun_sen', label: 'KJ', type: 'data' },
        { id: 'senkou_span_a', label: 'SpA', type: 'data' },
        { id: 'senkou_span_b', label: 'SpB', type: 'data' },
        { id: 'chikou_span', label: 'Chi', type: 'data' }
      ]
    },
    donchian: {
      inputs: [],
      outputs: [
        { id: 'upper', label: 'Up', type: 'data' },
        { id: 'middle', label: 'Mid', type: 'data' },
        { id: 'lower', label: 'Lo', type: 'data' }
      ]
    },
    keltner: {
      inputs: [],
      outputs: [
        { id: 'upper', label: 'Up', type: 'data' },
        { id: 'middle', label: 'Mid', type: 'data' },
        { id: 'lower', label: 'Lo', type: 'data' }
      ]
    },
    obv: { inputs: [], outputs: [{ id: 'value', label: 'OBV', type: 'data' }] },
    vwap: { inputs: [], outputs: [{ id: 'value', label: 'VWAP', type: 'data' }] },
    cmf: { inputs: [], outputs: [{ id: 'value', label: 'CMF', type: 'data' }] },
    cci: { inputs: [], outputs: [{ id: 'value', label: 'CCI', type: 'data' }] },
    williams_r: { inputs: [], outputs: [{ id: 'value', label: 'W%R', type: 'data' }] },
    mfi: { inputs: [], outputs: [{ id: 'value', label: 'MFI', type: 'data' }] },
    roc: { inputs: [], outputs: [{ id: 'value', label: 'ROC', type: 'data' }] },
    stoch_rsi: {
      inputs: [],
      outputs: [
        { id: 'k', label: '%K', type: 'data' },
        { id: 'd', label: '%D', type: 'data' }
      ]
    },
    wma: { inputs: [], outputs: [{ id: 'value', label: 'WMA', type: 'data' }] },
    dema: { inputs: [], outputs: [{ id: 'value', label: 'DEMA', type: 'data' }] },
    tema: { inputs: [], outputs: [{ id: 'value', label: 'TEMA', type: 'data' }] },
    hull_ma: { inputs: [], outputs: [{ id: 'value', label: 'HMA', type: 'data' }] },
    parabolic_sar: { inputs: [], outputs: [{ id: 'value', label: 'SAR', type: 'data' }] },
    aroon: {
      inputs: [],
      outputs: [
        { id: 'up', label: 'Up', type: 'data' },
        { id: 'down', label: 'Dn', type: 'data' },
        { id: 'oscillator', label: 'Osc', type: 'data' }
      ]
    },
    stddev: { inputs: [], outputs: [{ id: 'value', label: 'StD', type: 'data' }] },

    // Conditions - input data, output bool
    crossover: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    crossunder: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    greater_than: {
      inputs: [
        { id: 'left', label: 'A', type: 'data' },
        { id: 'right', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    less_than: {
      inputs: [
        { id: 'left', label: 'A', type: 'data' },
        { id: 'right', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    equals: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    between: {
      inputs: [
        { id: 'value', label: 'Val', type: 'data' },
        { id: 'min', label: 'Min', type: 'data' },
        { id: 'max', label: 'Max', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },

    // Actions - input condition, output signal
    buy: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: [{ id: 'signal', label: '', type: 'condition' }]
    },
    sell: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: [{ id: 'signal', label: '', type: 'condition' }]
    },
    close: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: [{ id: 'signal', label: '', type: 'condition' }]
    },
    stop_loss: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: []
    },
    take_profit: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: []
    },
    trailing_stop: {
      inputs: [{ id: 'signal', label: '', type: 'condition' }],
      outputs: []
    },

    // Logic - input/output conditions
    and: {
      inputs: [
        { id: 'a', label: 'A', type: 'condition' },
        { id: 'b', label: 'B', type: 'condition' },
        { id: 'c', label: 'C', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: 'Result', type: 'condition' }]
    },
    or: {
      inputs: [
        { id: 'a', label: 'A', type: 'condition' },
        { id: 'b', label: 'B', type: 'condition' },
        { id: 'c', label: 'C', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: 'Result', type: 'condition' }]
    },
    not: {
      inputs: [{ id: 'input', label: 'In', type: 'condition' }],
      outputs: [{ id: 'result', label: 'Result', type: 'condition' }]
    },
    delay: {
      inputs: [{ id: 'input', label: '', type: 'condition' }],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    filter: {
      inputs: [
        { id: 'signal', label: 'Sig', type: 'condition' },
        { id: 'filter', label: 'Flt', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },

    // Inputs - output data
    price: {
      inputs: [],
      outputs: [
        { id: 'open', label: 'O', type: 'data' },
        { id: 'high', label: 'H', type: 'data' },
        { id: 'low', label: 'L', type: 'data' },
        { id: 'close', label: 'C', type: 'data' }
      ]
    },
    volume: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Vol', type: 'data' }]
    },
    constant: {
      inputs: [],
      outputs: [{ id: 'value', label: '', type: 'data' }]
    },
    timeframe: {
      inputs: [],
      outputs: [{ id: 'value', label: '', type: 'data' }]
    },

    // Exit/Risk management blocks - output config to Strategy node
    static_sltp: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    trailing_stop_exit: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    atr_exit: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    dca: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    grid_orders: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    multi_tp_exit: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },

    // ── Universal Indicators (all output long/short boolean signals) ──
    qqe: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    atr_volatility: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    volume_filter: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    highest_lowest_bar: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    two_mas: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    accumulation_areas: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    keltner_bollinger: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    rvi_filter: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    mfi_filter: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    cci_filter: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    momentum_filter: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },
    pivot_points: {
      inputs: [],
      outputs: [
        { id: 'pp', label: 'PP', type: 'data' },
        { id: 'r1', label: 'R1', type: 'data' },
        { id: 'r2', label: 'R2', type: 'data' },
        { id: 'r3', label: 'R3', type: 'data' },
        { id: 's1', label: 'S1', type: 'data' },
        { id: 's2', label: 'S2', type: 'data' },
        { id: 's3', label: 'S3', type: 'data' }
      ]
    },
    ad_line: {
      inputs: [],
      outputs: [{ id: 'value', label: 'AD', type: 'data' }]
    },

    // ── Divergence (outputs long/short signals) ──
    divergence: {
      inputs: [],
      outputs: [
        { id: 'long', label: 'Long', type: 'condition' },
        { id: 'short', label: 'Short', type: 'condition' }
      ]
    },

    // ── Close Condition blocks (config → Strategy SL/TP port) ──
    close_by_time: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    close_channel: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    close_ma_cross: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    close_rsi: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    close_stochastic: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    },
    close_psar: {
      inputs: [],
      outputs: [{ id: 'config', label: '', type: 'config' }]
    }

    // Note: 'strategy' ports are dynamic - handled below
  };

  // Special handling for main Strategy node
  // Entry/Exit signal ports + config ports for SL/TP, Close conditions, DCA
  if (blockId === 'strategy') {
    return {
      inputs: [
        { id: 'entry_long', label: 'Entry L', type: 'condition' },
        { id: 'entry_short', label: 'Entry S', type: 'condition' },
        { id: 'exit_long', label: 'Exit L', type: 'condition' },
        { id: 'exit_short', label: 'Exit S', type: 'condition' },
        { id: 'sl_tp', label: 'SL/TP', type: 'config' },
        { id: 'close_cond', label: 'Close', type: 'config' },
        { id: 'dca_grid', label: 'DCA', type: 'config' }
      ],
      outputs: []
    };
  }

  return (
    portConfigs[blockId] || {
      inputs: [{ id: 'in', label: '', type: 'data' }],
      outputs: [{ id: 'out', label: '', type: 'data' }]
    }
  );
}

function renderPorts(ports, direction, blockId) {
  if (!ports || ports.length === 0) return '';

  if (ports.length === 1) {
    const port = ports[0];
    const posClass = direction === 'input' ? 'input' : 'output';
    return `<div class="port ${posClass} ${port.type}-port"
                 data-port-id="${port.id}"
                 data-port-type="${port.type}"
                 data-block-id="${blockId}"
                 data-direction="${direction}"
                 title="${port.label || port.type}"></div>`;
  }

  // Multiple ports
  return `
    <div class="ports-container ${direction}-ports">
      ${ports
      .map(
        (port) => `
        <div class="port-row ${direction}">
          <div class="port ${port.type}-port"
               data-port-id="${port.id}"
               data-port-type="${port.type}"
               data-block-id="${blockId}"
               data-direction="${direction}"
               title="${port.label || port.type}"></div>
          ${port.label ? `<span class="port-label">${port.label}</span>` : ''}
        </div>
      `
      )
      .join('')}
    </div>
  `;
}

// Special render for main Strategy node — rectangular with ports on left side
function renderMainStrategyNode(block, _ports) {
  return `
    <div class="strategy-block main main-block main-strategy-node"
         id="${block.id}"
         style="left: ${block.x}px; top: ${block.y}px"
         data-block-id="${block.id}">
        <!-- Entry Long port -->
        <div class="port condition-port main-port-left entry-port"
             data-port-id="entry_long"
             data-port-type="condition"
             data-block-id="${block.id}"
             data-direction="input"
             title="Entry Long — connect indicator Long signal or condition result"
             style="top: 10%;"></div>
        <span class="main-port-label entry-label" style="top: 10%; transform: translateY(-50%);"><i class="bi bi-arrow-up-circle"></i> Entry L</span>

        <!-- Entry Short port -->
        <div class="port condition-port main-port-left entry-port"
             data-port-id="entry_short"
             data-port-type="condition"
             data-block-id="${block.id}"
             data-direction="input"
             title="Entry Short — connect indicator Short signal or condition result"
             style="top: 23%;"></div>
        <span class="main-port-label entry-label" style="top: 23%; transform: translateY(-50%);"><i class="bi bi-arrow-down-circle"></i> Entry S</span>

        <!-- Exit Long port -->
        <div class="port condition-port main-port-left exit-port"
             data-port-id="exit_long"
             data-port-type="condition"
             data-block-id="${block.id}"
             data-direction="input"
             title="Exit Long — optional signal to close long positions"
             style="top: 36%;"></div>
        <span class="main-port-label exit-label" style="top: 36%; transform: translateY(-50%);"><i class="bi bi-x-circle"></i> Exit L</span>

        <!-- Exit Short port -->
        <div class="port condition-port main-port-left exit-port"
             data-port-id="exit_short"
             data-port-type="condition"
             data-block-id="${block.id}"
             data-direction="input"
             title="Exit Short — optional signal to close short positions"
             style="top: 49%;"></div>
        <span class="main-port-label exit-label" style="top: 49%; transform: translateY(-50%);"><i class="bi bi-x-circle"></i> Exit S</span>

        <!-- SL/TP config port — cyan -->
        <div class="port config-port main-port-left config-input-port"
             data-port-id="sl_tp"
             data-port-type="config"
             data-block-id="${block.id}"
             data-direction="input"
             title="SL/TP — connect Static SL/TP, Trailing Stop, ATR Exit, or Multi TP"
             style="top: 63%;"></div>
        <span class="main-port-label config-label-sltp" style="top: 63%; transform: translateY(-50%);"><i class="bi bi-shield-check"></i> SL/TP</span>

        <!-- Close Conditions config port — amber -->
        <div class="port config-port main-port-left config-input-port"
             data-port-id="close_cond"
             data-port-type="config"
             data-block-id="${block.id}"
             data-direction="input"
             title="Close Conditions — connect Close by RSI, Stochastic, PSAR, Channel, MA, Time"
             style="top: 77%;"></div>
        <span class="main-port-label config-label-close" style="top: 77%; transform: translateY(-50%);"><i class="bi bi-door-open"></i> Close</span>

        <!-- DCA/Grid config port — purple -->
        <div class="port config-port main-port-left config-input-port"
             data-port-id="dca_grid"
             data-port-type="config"
             data-block-id="${block.id}"
             data-direction="input"
             title="DCA/Grid — connect DCA or Manual Grid block"
             style="top: 91%;"></div>
        <span class="main-port-label config-label-dca" style="top: 91%; transform: translateY(-50%);"><i class="bi bi-layers"></i> DCA</span>

        <!-- Center title -->
        <div class="main-block-title">${block.name}</div>
    </div>
  `;
}

function renderBlocks() {
  // BUG#6 FIX: removed console.log — this is called ~60fps during drag via RAF
  const container = document.getElementById('blocksContainer');
  if (!container) {
    console.error('[Strategy Builder] Blocks container not found!');
    return;
  }
  container.innerHTML = strategyBlocks
    .map((block) => {
      const ports = getBlockPorts(block.type, block.category);
      const isMain = block.isMain === true;

      // Special rendering for main Strategy node
      if (isMain) {
        return renderMainStrategyNode(block, ports);
      }

      const paramHint = getCompactParamHint(block.params || {}, block.type);
      const hasOptimization = block.optimizationParams &&
        Object.values(block.optimizationParams).some(p => p.enabled);
      const hasLabeledInputs = ports.inputs && ports.inputs.length > 1 && ports.inputs.some(p => p.label);
      const hasLabeledOutputs = ports.outputs && ports.outputs.length > 1 && ports.outputs.some(p => p.label);
      const maxPorts = Math.max(ports.inputs?.length || 0, ports.outputs?.length || 0);
      const manyPortsClass = maxPorts >= 5 ? 'has-many-ports' : maxPorts >= 4 ? 'has-some-ports' : '';
      const portClasses = `${hasLabeledInputs ? 'has-labeled-inputs' : ''} ${hasLabeledOutputs ? 'has-labeled-outputs' : ''} ${manyPortsClass}`;
      return `
        <div class="strategy-block ${block.category} ${selectedBlockId === block.id ? 'selected' : ''} ${hasOptimization ? 'has-optimization' : ''} ${portClasses}"
             id="${block.id}"
             style="left: ${block.x}px; top: ${block.y}px"
             data-block-id="${block.id}">
            ${renderPorts(ports.inputs, 'input', block.id)}
            <div class="block-header">
                <div class="block-header-icon">
                    <i class="bi bi-${block.icon}"></i>
                </div>
                <span class="block-header-title">${escapeHtml(block.name)}</span>
                <div class="block-header-actions">
                    <button class="block-action-btn" data-action="duplicate" title="Duplicate"><i class="bi bi-copy"></i></button>
                    <button class="block-action-btn" data-action="delete" title="Delete"><i class="bi bi-trash"></i></button>
                    <button class="block-header-menu" title="Settings"><i class="bi bi-three-dots"></i></button>
                </div>
            </div>
            ${paramHint ? `<div class="block-param-hint">${escapeHtml(paramHint)}</div>` : ''}
            ${renderPorts(ports.outputs, 'output', block.id)}
        </div>
      `;
    })
    .join('');

  // Re-render connections after blocks
  renderConnections();
}

// Generate compact param hint for block (e.g. "14 | 70 | 30")
function getCompactParamHint(params, blockType) {
  // Special handling for grid_orders
  if (params.orders && Array.isArray(params.orders)) {
    const count = params.orders.length;
    const totalVolume = params.orders.reduce((sum, o) => sum + (parseFloat(o.volume) || 0), 0);
    return `${count} orders | ${totalVolume.toFixed(0)}%`;
  }

  // Special compact hints for complex block types
  if (blockType === 'atr_exit') {
    const parts = [];
    if (params.use_atr_sl) {
      parts.push(`SL: ${params.atr_sl_period || 140}×${params.atr_sl_multiplier || 4}`);
    }
    if (params.use_atr_tp) {
      parts.push(`TP: ${params.atr_tp_period || 140}×${params.atr_tp_multiplier || 4}`);
    }
    if (parts.length === 0) parts.push('Disabled');
    return parts.join(' | ');
  }

  if (blockType === 'static_sltp') {
    const parts = [];
    if (params.take_profit_percent) parts.push(`TP: ${params.take_profit_percent}%`);
    if (params.stop_loss_percent) parts.push(`SL: ${params.stop_loss_percent}%`);
    return parts.join(' | ') || 'Not set';
  }

  if (blockType === 'trailing_stop_exit') {
    const act = params.activation_percent ?? 1.0;
    const trail = params.trailing_percent ?? 0.5;
    return `Act: ${act}% | Trail: ${trail}%`;
  }

  if (blockType === 'dca') {
    const parts = [`Grid:${params.grid_size_percent || 0}% | ${params.order_count || 0} ord | M:${params.martingale_coefficient || 1}`];
    if (params.partial_grid_orders && params.partial_grid_orders > 1) parts.push(`Part:${params.partial_grid_orders}`);
    if (params.grid_pullback_percent && params.grid_pullback_percent > 0) parts.push(`PB:${params.grid_pullback_percent}%`);
    return parts.join(' | ');
  }

  if (blockType === 'rsi') {
    const parts = [`${params.period || 14}`];
    if (params.use_long_range) parts.push(`L:${params.long_rsi_more}-${params.long_rsi_less}`);
    if (params.use_short_range) parts.push(`S:${params.short_rsi_less}-${params.short_rsi_more}`);
    if (params.use_cross_level) parts.push(`X:${params.cross_long_level}/${params.cross_short_level}`);
    if (params.use_cross_memory) parts.push(`Mem:${params.cross_memory_bars}`);
    if (params.timeframe && params.timeframe !== 'Chart') parts.push(params.timeframe);
    return parts.join(' | ');
  }

  if (blockType === 'macd') {
    const parts = [`${params.fast_period || 12} | ${params.slow_period || 26} | ${params.signal_period || 9}`];
    if (params.use_macd_cross_zero) parts.push(`Zero:${params.macd_cross_zero_level ?? 0}`);
    if (params.use_macd_cross_signal) parts.push('Sig✓');
    if (params.signal_only_if_macd_positive) parts.push('M>0');
    if (!params.disable_signal_memory) parts.push(`Mem:${params.signal_memory_bars || 5}`);
    if (params.source && params.source !== 'close') parts.push(params.source);
    if (params.timeframe && params.timeframe !== 'Chart') parts.push(params.timeframe);
    return parts.join(' | ');
  }

  const entries = Object.entries(params);
  if (entries.length === 0) return '';

  // Show up to 6 key values separated by |
  const values = entries.slice(0, 6).map(([_key, val]) => {
    // Shorten booleans
    if (val === true) return '✓';
    if (val === false) return '✗';
    // Skip arrays/objects
    if (typeof val === 'object') return null;
    // Shorten long strings
    if (typeof val === 'string' && val.length > 6) return val.slice(0, 6) + '…';
    return val;
  }).filter(v => v !== null);

  return values.join(' | ') + (entries.length > 6 ? ' …' : '');
}

// Show block parameters popup
function showBlockParamsPopup(blockId, optimizationMode = false) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  // Remove existing popup
  const existingPopup = document.querySelector('.block-params-popup');
  if (existingPopup) existingPopup.remove();

  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  const params = block.params || {};
  const optParams = block.optimizationParams || {};

  // Auto-switch to optimization mode if block has optimization enabled
  const hasOptimization = block.optimizationParams &&
    Object.values(block.optimizationParams).some(p => p.enabled);
  if (hasOptimization && !optimizationMode) {
    optimizationMode = true;
  }

  const popup = document.createElement('div');
  popup.className = `block-params-popup ${optimizationMode ? 'optimization-mode' : ''}`;
  popup.dataset.blockId = blockId;
  popup.dataset.optimizationMode = optimizationMode;

  popup.innerHTML = `
    <div class="popup-header">
      <span class="popup-title"><i class="bi bi-${block.icon}"></i> ${block.name}</span>
      <button class="popup-close" data-action="close"><i class="bi bi-x"></i></button>
    </div>
    <div class="popup-body">
      ${renderGroupedParams(block, optimizationMode, false) || (Object.keys(params).length === 0
      ? '<p class="text-muted">No parameters</p>'
      : Object.entries(params).map(([key, value]) => {
        const opt = optParams[key] || { enabled: false, min: value, max: value, step: 1 };
        return optimizationMode ? `
          <div class="popup-param-row optimization-row">
            <div class="opt-checkbox">
              <input type="checkbox"
                     id="opt_${blockId}_${key}"
                     class="opt-enable-checkbox"
                     data-param-key="${key}"
                     ${opt.enabled ? 'checked' : ''}>
            </div>
            <label class="popup-param-label" for="opt_${blockId}_${key}">${formatParamName(key)}</label>
            <div class="opt-range-inputs">
              <input type="number" class="opt-input opt-min" value="${opt.min}" data-param-key="${key}" data-opt-field="min" title="From">
              <span class="opt-separator">→</span>
              <input type="number" class="opt-input opt-max" value="${opt.max}" data-param-key="${key}" data-opt-field="max" title="To">
              <span class="opt-separator">/</span>
              <input type="number" class="opt-input opt-step" value="${opt.step}" data-param-key="${key}" data-opt-field="step" title="Step" step="any">
            </div>
          </div>
          ` : `
          <div class="popup-param-row">
            <label class="popup-param-label">${formatParamName(key)}</label>
            <input type="number"
                   class="popup-param-input"
                   value="${value}"
                   data-block-id="${blockId}"
                   data-param-key="${key}"
                   step="any">
          </div>
          `;
      }).join(''))}
    </div>
    <div class="popup-footer">
      <button class="btn btn-sm" data-action="default">
        <i class="bi bi-arrow-counterclockwise"></i> Default
      </button>
      <button class="btn btn-sm ${optimizationMode ? 'active' : ''}" data-action="optimization">
        <i class="bi bi-sliders"></i> Optimization
      </button>
    </div>
  `;

  // Add event listeners
  popup.querySelector('.popup-close').addEventListener('click', closeBlockParamsPopup);

  popup.querySelector('[data-action="default"]').addEventListener('click', () => resetBlockToDefaults(blockId));

  popup.querySelector('[data-action="optimization"]').addEventListener('click', (e) => {
    e.stopPropagation();
    // Remove listener before switching to prevent auto-close
    document.removeEventListener('click', closePopupOnOutsideClick);

    // If already in optimization mode - reset all optimization params and switch to normal mode
    if (optimizationMode) {
      // Reset all optimization params
      if (block.optimizationParams) {
        Object.keys(block.optimizationParams).forEach(key => {
          block.optimizationParams[key].enabled = false;
        });
      }
      updateBlockOptimizationIndicator(blockId);
      renderBlocks();
      showBlockParamsPopup(blockId, false);
    } else {
      // Switch to optimization mode
      showBlockParamsPopup(blockId, true);
    }
  });

  if (optimizationMode) {
    // Optimization mode handlers
    popup.querySelectorAll('.opt-enable-checkbox').forEach(checkbox => {
      checkbox.addEventListener('click', (e) => e.stopPropagation());
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = checkbox.dataset.paramKey;
        if (!block.optimizationParams) block.optimizationParams = {};
        if (!block.optimizationParams[key]) {
          const fMin = checkbox.dataset.fieldMin !== '' ? parseFloat(checkbox.dataset.fieldMin) : params[key];
          const fMax = checkbox.dataset.fieldMax !== '' ? parseFloat(checkbox.dataset.fieldMax) : params[key];
          const fStep = checkbox.dataset.fieldStep !== '' ? parseFloat(checkbox.dataset.fieldStep) : 1;
          block.optimizationParams[key] = { enabled: false, min: fMin, max: fMax, step: fStep };
        }
        block.optimizationParams[key].enabled = checkbox.checked;
        updateBlockOptimizationIndicator(blockId);
        dispatchBlocksChanged(); // notify optimization_panels.js
      });
    });

    popup.querySelectorAll('.opt-input').forEach(input => {
      input.addEventListener('click', (e) => e.stopPropagation());
      input.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = input.dataset.paramKey;
        const field = input.dataset.optField;
        if (!block.optimizationParams) block.optimizationParams = {};
        if (!block.optimizationParams[key]) {
          block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
        }
        block.optimizationParams[key][field] = parseFloat(input.value);
        dispatchBlocksChanged(); // notify optimization_panels.js
      });
    });
  } else {
    // Normal mode - param value handlers
    popup.querySelectorAll('.popup-param-input').forEach(input => {
      input.addEventListener('click', (e) => e.stopPropagation());
      input.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = input.dataset.paramKey;
        const value = input.value;
        updateBlockParam(blockId, key, value);
      });
    });
  }

  // Handle group toggles (for grouped params like RSI Filter)
  popup.querySelectorAll('.group-toggle').forEach(toggle => {
    toggle.addEventListener('click', (e) => e.stopPropagation());
    toggle.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = toggle.dataset.paramKey;
      const enabled = toggle.checked;
      updateBlockParam(blockId, key, enabled);

      // Show/hide group body
      const group = toggle.closest('.param-group');
      if (group) {
        const body = group.querySelector('.param-group-body');
        if (body) body.style.display = enabled ? '' : 'none';
        group.classList.toggle('collapsed', !enabled);
      }
    });
  });

  // Handle select dropdowns (legacy)
  popup.querySelectorAll('.popup-param-select').forEach(select => {
    select.addEventListener('click', (e) => e.stopPropagation());
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = select.dataset.paramKey;
      updateBlockParam(blockId, key, select.value);
    });
  });

  // Handle checkbox params (legacy)
  popup.querySelectorAll('.popup-param-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      updateBlockParam(blockId, key, checkbox.checked);
    });
  });

  // ========== TradingView-style handlers ==========

  // TV inputs
  popup.querySelectorAll('.tv-input').forEach(input => {
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = input.dataset.paramKey;
      const val = parseFloat(input.value) || 0;
      updateBlockParam(blockId, key, val);
    });
  });

  // TV selects
  popup.querySelectorAll('.tv-select').forEach(select => {
    select.addEventListener('click', (e) => e.stopPropagation());
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = select.dataset.paramKey;
      updateBlockParam(blockId, key, select.value);
    });
  });

  // TV checkboxes
  popup.querySelectorAll('.tv-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      updateBlockParam(blockId, key, checkbox.checked);
    });
  });

  // ========== TV-style Optimization handlers ==========

  // TV optimization checkboxes
  popup.querySelectorAll('.tv-opt-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      if (!block.optimizationParams) block.optimizationParams = {};
      if (!block.optimizationParams[key]) {
        // Use field-level constraints stored as data-* attributes (fallback to current value)
        const fMin = checkbox.dataset.fieldMin !== '' ? parseFloat(checkbox.dataset.fieldMin) : params[key];
        const fMax = checkbox.dataset.fieldMax !== '' ? parseFloat(checkbox.dataset.fieldMax) : params[key];
        const fStep = checkbox.dataset.fieldStep !== '' ? parseFloat(checkbox.dataset.fieldStep) : 1;
        block.optimizationParams[key] = { enabled: false, min: fMin, max: fMax, step: fStep };
      }
      block.optimizationParams[key].enabled = checkbox.checked;

      // Enable/disable associated inputs
      const row = checkbox.closest('.tv-opt-row');
      if (row) {
        row.querySelectorAll('.tv-opt-input').forEach(inp => {
          inp.disabled = !checkbox.checked;
        });
      }
      updateBlockOptimizationIndicator(blockId);
      dispatchBlocksChanged(); // notify optimization panel to refresh Parameter Ranges
    });
  });

  // TV optimization inputs
  popup.querySelectorAll('.tv-opt-input').forEach(input => {
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = input.dataset.paramKey;
      const field = input.dataset.optField;
      if (!block.optimizationParams) block.optimizationParams = {};
      if (!block.optimizationParams[key]) {
        // Use field-level constraints from sibling checkbox data-* attributes
        const cbx = input.closest('.tv-opt-row')?.querySelector('.tv-opt-checkbox');
        const fMin = cbx?.dataset.fieldMin !== '' ? parseFloat(cbx?.dataset.fieldMin) : params[key];
        const fMax = cbx?.dataset.fieldMax !== '' ? parseFloat(cbx?.dataset.fieldMax) : params[key];
        const fStep = cbx?.dataset.fieldStep !== '' ? parseFloat(cbx?.dataset.fieldStep) : 1;
        block.optimizationParams[key] = { enabled: false, min: fMin ?? params[key], max: fMax ?? params[key], step: fStep ?? 1 };
      }
      block.optimizationParams[key][field] = parseFloat(input.value);
      dispatchBlocksChanged(); // notify optimization panel to refresh Parameter Ranges
    });
  });

  // Append popup to body for proper z-index layering (above all nodes)
  document.body.appendChild(popup);

  // Enable wheel scroll for all number inputs in popup
  enableWheelScrollForNumberInputs(popup);

  // Initialize special panels (Grid Orders)
  if (block.type === 'grid_orders') {
    initGridOrdersPanel(popup, blockId);
  }

  // CRITICAL: Stop all clicks inside popup from bubbling to document
  popup.addEventListener('click', (e) => {
    e.stopPropagation();
  });

  // Make popup invisible but in DOM to measure real height before positioning
  popup.style.visibility = 'hidden';
  popup.style.position = 'fixed';
  popup.style.top = '0px';
  popup.style.left = '0px';

  // Double rAF ensures browser has fully laid out the popup before measuring
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      positionPopupInViewport(popup, blockEl);
      popup.style.visibility = '';
    });
  });

  // Close on outside click
  setTimeout(() => {
    document.addEventListener('click', closePopupOnOutsideClick);
  }, 10);
}

/**
 * Position popup next to block element, ensuring it stays within viewport.
 * CSS flexbox layout guarantees header/footer are always visible.
 * Body scrolls only when popup hits max-height.
 */
function positionPopupInViewport(popup, blockEl) {
  const blockRect = blockEl.getBoundingClientRect();
  const popupWidth = popup.offsetWidth || 320;
  const padding = 10; // Gap between block and popup
  const margin = 10; // Margin from viewport edges
  const viewportH = window.innerHeight;
  const viewportW = window.innerWidth;

  // Cap popup height so it never exceeds available viewport space
  const maxAllowedHeight = viewportH - margin * 2;
  popup.style.maxHeight = `${maxAllowedHeight}px`;

  // Re-measure after clamping max-height
  const popupHeight = Math.min(popup.offsetHeight || 400, maxAllowedHeight);

  let left, top;

  // --- Horizontal positioning ---
  if (blockRect.right + padding + popupWidth + margin <= viewportW) {
    left = blockRect.right + padding;
  } else if (blockRect.left - padding - popupWidth >= margin) {
    left = blockRect.left - padding - popupWidth;
  } else {
    left = viewportW - popupWidth - margin;
  }

  // --- Vertical positioning ---
  top = blockRect.top;

  // Ensure popup doesn't go below viewport
  if (top + popupHeight + margin > viewportH) {
    top = viewportH - popupHeight - margin;
  }

  // Ensure popup doesn't go above viewport
  if (top < margin) {
    top = margin;
  }

  popup.style.position = 'fixed';
  popup.style.left = `${Math.max(margin, left)}px`;
  popup.style.top = `${top}px`;
}

// Update block visual indicator for optimization
function updateBlockOptimizationIndicator(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  const hasOptimization = block.optimizationParams &&
    Object.values(block.optimizationParams).some(p => p.enabled);

  blockEl.classList.toggle('has-optimization', hasOptimization);
}

function closePopupOnOutsideClick(e) {
  const popup = document.querySelector('.block-params-popup');
  if (popup && !popup.contains(e.target) && !e.target.closest('.block-header-menu')) {
    closeBlockParamsPopup();
  }
}

function closeBlockParamsPopup() {
  const popup = document.querySelector('.block-params-popup');
  if (popup) popup.remove();
  document.removeEventListener('click', closePopupOnOutsideClick);
}

// ============================================
// QUICK-ADD DIALOG
// ============================================

let quickAddDialog = null;

/**
 * Show quick-add dialog at specified position
 * @param {number} x - X coordinate on canvas
 * @param {number} y - Y coordinate on canvas
 */
function showQuickAddDialog(x, y) {
  closeQuickAddDialog();

  const container = document.getElementById('blocksContainer');

  quickAddDialog = document.createElement('div');
  quickAddDialog.className = 'quick-add-dialog';
  quickAddDialog.innerHTML = `
    <div class="quick-add-header">
      <input type="text" class="quick-add-search" placeholder="Поиск блоков..." autofocus>
      <button class="quick-add-close" title="Закрыть">×</button>
    </div>
    <div class="quick-add-categories"></div>
    <div class="quick-add-results"></div>
  `;

  quickAddDialog.style.left = `${x}px`;
  quickAddDialog.style.top = `${y}px`;

  container.appendChild(quickAddDialog);

  // Build categories
  const categoriesDiv = quickAddDialog.querySelector('.quick-add-categories');
  const mainCategories = [
    { key: 'indicators', label: 'Индикаторы', icon: 'graph-up' },
    { key: 'filters', label: 'Фильт��ы', icon: 'funnel' },
    { key: 'conditions', label: 'Условия', icon: 'signpost' },
    { key: 'exits', label: 'Выходы', icon: 'box-arrow-right' }
  ];

  mainCategories.forEach((cat) => {
    if (blockLibrary[cat.key] && blockLibrary[cat.key].length > 0) {
      const btn = document.createElement('button');
      btn.className = 'quick-add-cat-btn';
      btn.dataset.category = cat.key;
      btn.innerHTML = `<i class="bi bi-${cat.icon}"></i> ${cat.label}`;
      btn.addEventListener('click', () => showQuickAddCategory(cat.key));
      categoriesDiv.appendChild(btn);
    }
  });

  // Search functionality
  const searchInput = quickAddDialog.querySelector('.quick-add-search');
  searchInput.addEventListener('input', (e) => {
    filterQuickAddResults(e.target.value);
  });

  // Close button
  quickAddDialog.querySelector('.quick-add-close').addEventListener('click', closeQuickAddDialog);

  // Close on Escape
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeQuickAddDialog();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);

  // Store position for adding block
  quickAddDialog.dataset.addX = x;
  quickAddDialog.dataset.addY = y;

  // Focus search input
  setTimeout(() => searchInput.focus(), 50);
}

/**
 * Show blocks from a specific category in Quick-Add dialog
 * @param {string} category - Category key
 */
function showQuickAddCategory(category) {
  if (!quickAddDialog) return;

  const resultsDiv = quickAddDialog.querySelector('.quick-add-results');
  const blocks = blockLibrary[category] || [];

  resultsDiv.innerHTML = '';

  blocks.forEach((block) => {
    const item = document.createElement('div');
    item.className = 'quick-add-item';
    item.innerHTML = `
      <i class="bi bi-${escapeHtml(block.icon || 'box')}"></i>
      <div class="quick-add-item-info">
        <span class="quick-add-item-name">${escapeHtml(block.name)}</span>
        <span class="quick-add-item-desc">${escapeHtml(block.desc || '')}</span>
      </div>
    `;
    item.addEventListener('click', () => {
      const x = parseInt(quickAddDialog.dataset.addX) || 200;
      const y = parseInt(quickAddDialog.dataset.addY) || 200;
      addBlockToCanvas(block.id, category, x, y);
      closeQuickAddDialog();
    });
    resultsDiv.appendChild(item);
  });

  // Highlight selected category
  quickAddDialog.querySelectorAll('.quick-add-cat-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.category === category);
  });
}

/**
 * Filter Quick-Add results by search query
 * @param {string} query - Search query
 */
function filterQuickAddResults(query) {
  if (!quickAddDialog) return;

  const resultsDiv = quickAddDialog.querySelector('.quick-add-results');
  resultsDiv.innerHTML = '';

  if (!query || query.length < 2) {
    // Show categories when no search
    quickAddDialog.querySelector('.quick-add-categories').style.display = 'flex';
    return;
  }

  // Hide categories during search
  quickAddDialog.querySelector('.quick-add-categories').style.display = 'none';

  const lowerQuery = query.toLowerCase();
  const matches = [];

  // Search in all categories
  Object.entries(blockLibrary).forEach(([category, blocks]) => {
    blocks.forEach((block) => {
      const nameMatch = block.name.toLowerCase().includes(lowerQuery);
      const descMatch = block.desc && block.desc.toLowerCase().includes(lowerQuery);
      const idMatch = block.id.toLowerCase().includes(lowerQuery);

      if (nameMatch || descMatch || idMatch) {
        matches.push({ block, category });
      }
    });
  });

  // Show results
  matches.slice(0, 15).forEach(({ block, category }) => {
    const item = document.createElement('div');
    item.className = 'quick-add-item';
    item.innerHTML = `
      <i class="bi bi-${escapeHtml(block.icon || 'box')}"></i>
      <div class="quick-add-item-info">
        <span class="quick-add-item-name">${escapeHtml(block.name)}</span>
        <span class="quick-add-item-desc">${escapeHtml(block.desc || '')}</span>
      </div>
    `;
    item.addEventListener('click', () => {
      const x = parseInt(quickAddDialog.dataset.addX) || 200;
      const y = parseInt(quickAddDialog.dataset.addY) || 200;
      addBlockToCanvas(block.id, category, x, y);
      closeQuickAddDialog();
    });
    resultsDiv.appendChild(item);
  });

  if (matches.length === 0) {
    resultsDiv.innerHTML = '<div class="quick-add-empty">Ничего не найдено</div>';
  }
}

/**
 * Close Quick-Add dialog
 */
function closeQuickAddDialog() {
  if (quickAddDialog) {
    quickAddDialog.remove();
    quickAddDialog = null;
  }
}

// ============================================
// PRESETS / SUBFLOWS
// ============================================

const PRESETS_STORAGE_KEY = 'strategy_builder_presets';

/**
 * Get all saved presets from localStorage
 * @returns {Array} Array of preset objects
 */
function getSavedPresets() {
  try {
    const data = localStorage.getItem(PRESETS_STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch (e) {
    console.error('[Presets] Error loading presets:', e);
    return [];
  }
}

/**
 * Save presets to localStorage
 * @param {Array} presets - Array of preset objects
 */
function savePresetsToStorage(presets) {
  try {
    localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets));
  } catch (e) {
    console.error('[Presets] Error saving presets:', e);
    showNotification('Ошибка сохранения пресета', 'error');
  }
}

/**
 * Save selected blocks as a preset
 * @param {string} name - Preset name
 * @param {string} description - Preset description
 */
function saveSelectionAsPreset(name, description = '') {
  if (selectedBlockIds.length === 0) {
    showNotification('Сначала выделите блоки (Shift+Click или область выделения)', 'warning');
    return;
  }

  // Get selected blocks data
  const selectedBlocks = strategyBlocks.filter((b) => selectedBlockIds.includes(b.id));

  if (selectedBlocks.length === 0) {
    showNotification('Нет выделенных блоков', 'warning');
    return;
  }

  // Calculate bounding box to normalize positions
  const minX = Math.min(...selectedBlocks.map((b) => b.x));
  const minY = Math.min(...selectedBlocks.map((b) => b.y));

  // Create normalized block copies
  const normalizedBlocks = selectedBlocks.map((block) => ({
    ...block,
    id: block.id, // Will be regenerated on paste
    x: block.x - minX,
    y: block.y - minY
  }));

  // Get connections between selected blocks
  const selectedConnections = connections.filter(
    (conn) =>
      selectedBlockIds.includes(conn.source.blockId) &&
      selectedBlockIds.includes(conn.target.blockId)
  );

  // Create preset object
  const preset = {
    id: `preset_${Date.now()}`,
    name: name || `Пресет ${getSavedPresets().length + 1}`,
    description: description,
    createdAt: new Date().toISOString(),
    blocks: normalizedBlocks,
    connections: selectedConnections,
    blockCount: normalizedBlocks.length,
    connectionCount: selectedConnections.length
  };

  // Save to storage
  const presets = getSavedPresets();
  presets.push(preset);
  savePresetsToStorage(presets);

  showNotification(`Пресет "${preset.name}" сохранён (${preset.blockCount} блоков)`, 'success');
  return preset;
}

/**
 * Show dialog to save preset
 */
function showSavePresetDialog() {
  if (selectedBlockIds.length === 0) {
    showNotification('Сначала выделите блоки для сохранения', 'warning');
    return;
  }

  const container = document.getElementById('blocksContainer');

  const dialog = document.createElement('div');
  dialog.className = 'preset-dialog';
  dialog.innerHTML = `
    <div class="preset-dialog-content">
      <div class="preset-dialog-header">
        <h3>💾 Сохранить как пресет</h3>
        <button class="preset-dialog-close">×</button>
      </div>
      <div class="preset-dialog-body">
        <div class="preset-dialog-info">
          Выделено блоков: <strong>${selectedBlockIds.length}</strong>
        </div>
        <label>
          Название:
          <input type="text" class="preset-name-input" placeholder="Мой пресет" autofocus>
        </label>
        <label>
          Описание:
          <textarea class="preset-desc-input" placeholder="Описание пресета (опционально)"></textarea>
        </label>
      </div>
      <div class="preset-dialog-footer">
        <button class="btn-cancel">Отмена</button>
        <button class="btn-save">Сохранить</button>
      </div>
    </div>
  `;

  container.appendChild(dialog);

  // Event handlers
  const closeDialog = () => dialog.remove();

  dialog.querySelector('.preset-dialog-close').addEventListener('click', closeDialog);
  dialog.querySelector('.btn-cancel').addEventListener('click', closeDialog);

  dialog.querySelector('.btn-save').addEventListener('click', () => {
    const name = dialog.querySelector('.preset-name-input').value.trim();
    const desc = dialog.querySelector('.preset-desc-input').value.trim();
    saveSelectionAsPreset(name, desc);
    closeDialog();
  });

  // Close on Escape
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeDialog();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);

  // Focus input
  setTimeout(() => dialog.querySelector('.preset-name-input').focus(), 50);
}

/**
 * Insert a preset at specified position
 * @param {string} presetId - Preset ID
 * @param {number} x - X position
 * @param {number} y - Y position
 */
function insertPreset(presetId, x = 200, y = 200) {
  const presets = getSavedPresets();
  const preset = presets.find((p) => p.id === presetId);

  if (!preset) {
    showNotification('Пресет не найден', 'error');
    return;
  }

  pushUndo();

  // Map old IDs to new IDs
  const idMap = new Map();

  // Create new blocks with unique IDs
  preset.blocks.forEach((block) => {
    const newId = `block_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    idMap.set(block.id, newId);

    const newBlock = {
      ...block,
      id: newId,
      x: block.x + x,
      y: block.y + y,
      params: { ...block.params }
    };

    strategyBlocks.push(newBlock);
  });

  // Create new connections with updated IDs
  preset.connections.forEach((conn) => {
    const newSourceId = idMap.get(conn.source.blockId);
    const newTargetId = idMap.get(conn.target.blockId);

    if (newSourceId && newTargetId) {
      connections.push({
        id: `conn_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        source: { blockId: newSourceId, portId: conn.source.portId },
        target: { blockId: newTargetId, portId: conn.target.portId },
        type: conn.type
      });
    }
  });

  // BUG#4 FIX: renderBlocks() calls renderConnections() internally — no double render
  setSBBlocks(strategyBlocks);
  setSBConnections(connections);
  renderBlocks();

  showNotification(`Пресет "${preset.name}" вставлен`, 'success');
}

/**
 * Delete a preset
 * @param {string} presetId - Preset ID
 */
function deletePreset(presetId) {
  const presets = getSavedPresets();
  const preset = presets.find((p) => p.id === presetId);

  if (!preset) return;

  const filtered = presets.filter((p) => p.id !== presetId);
  savePresetsToStorage(filtered);

  showNotification(`Пресет "${preset.name}" удалён`, 'success');
}

/**
 * Show presets panel/list
 */
function showPresetsPanel() {
  const container = document.getElementById('blocksContainer');

  // Remove existing panel if open
  const existing = document.querySelector('.presets-panel');
  if (existing) {
    existing.remove();
    return;
  }

  const presets = getSavedPresets();

  const panel = document.createElement('div');
  panel.className = 'presets-panel';
  panel.innerHTML = `
    <div class="presets-panel-header">
      <h3>📦 Мои пресеты</h3>
      <button class="presets-panel-close">×</button>
    </div>
    <div class="presets-panel-actions">
      <button class="btn-save-selection" ${selectedBlockIds.length === 0 ? 'disabled' : ''}>
        <i class="bi bi-plus-circle"></i> Сохранить выделение
      </button>
    </div>
    <div class="presets-list">
      ${presets.length === 0
      ? '<div class="presets-empty">Нет сохранённых пресетов.<br>Выделите блоки и нажмите "Сохранить выделение"</div>'
      : presets
        .map(
          (p) => `
          <div class="preset-item" data-preset-id="${escapeHtml(p.id)}">
            <div class="preset-item-info">
              <div class="preset-item-name">${escapeHtml(p.name)}</div>
              <div class="preset-item-meta">
                ${p.blockCount} блоков, ${p.connectionCount} связей
              </div>
              ${p.description ? `<div class="preset-item-desc">${escapeHtml(p.description)}</div>` : ''}
            </div>
            <div class="preset-item-actions">
              <button class="btn-insert-preset" title="Вставить на canvas">
                <i class="bi bi-box-arrow-in-down"></i>
              </button>
              <button class="btn-delete-preset" title="Удалить">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        `
        )
        .join('')
    }
    </div>
  `;

  panel.style.cssText = `
    position: fixed;
    top: 100px;
    right: 20px;
    z-index: 1001;
  `;

  container.appendChild(panel);

  // Event handlers
  panel.querySelector('.presets-panel-close').addEventListener('click', () => panel.remove());

  panel.querySelector('.btn-save-selection')?.addEventListener('click', () => {
    panel.remove();
    showSavePresetDialog();
  });

  panel.querySelectorAll('.btn-insert-preset').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const presetId = e.target.closest('.preset-item').dataset.presetId;
      insertPreset(presetId, 300, 300);
      panel.remove();
    });
  });

  panel.querySelectorAll('.btn-delete-preset').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const presetId = e.target.closest('.preset-item').dataset.presetId;
      if (confirm('Удалить этот пресет?')) {
        deletePreset(presetId);
        panel.remove();
        showPresetsPanel(); // Refresh
      }
    });
  });
}

function updateBlockParamFromPopup(input) {
  const blockId = input.dataset.blockId;
  const key = input.dataset.paramKey;
  const value = input.value;
  updateBlockParam(blockId, key, value);
}

function resetBlockToDefaults(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  // Get default params from getDefaultParams function
  const defaultParams = getDefaultParams(block.type);

  if (Object.keys(defaultParams).length > 0) {
    block.params = { ...defaultParams };
    // renderBlocks calls renderConnections internally — re-checks direction mismatch
    renderBlocks();
    // Refresh popup if open
    closeBlockParamsPopup();
    showBlockParamsPopup(blockId);
  }
}

function duplicateBlock(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block || block.isMain) return;

  const newBlock = {
    ...block,
    id: `block_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    x: block.x + 30,
    y: block.y + 30,
    params: { ...block.params }
  };

  pushUndo();
  strategyBlocks.push(newBlock);
  setSBBlocks(strategyBlocks);
  renderBlocks();
  selectBlock(newBlock.id);
}

function deleteBlock(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block || block.isMain) {
    console.log('[Strategy Builder] Cannot delete main Strategy node');
    return;
  }
  pushUndo();

  // Remove connections involving this block
  for (let i = connections.length - 1; i >= 0; i--) {
    const c = connections[i];
    if (c.source.blockId === blockId || c.target.blockId === blockId) {
      connections.splice(i, 1);
    }
  }
  setSBConnections(connections);

  // Remove block
  const idx = strategyBlocks.findIndex(b => b.id === blockId);
  if (idx !== -1) {
    strategyBlocks.splice(idx, 1);
  }
  setSBBlocks(strategyBlocks);

  if (selectedBlockId === blockId) {
    selectedBlockId = null;
    setSBSelectedBlockId(null);
  }

  renderBlocks();
  renderBlockProperties();

  // Notify optimization panels about block changes
  dispatchBlocksChanged();
}

function _renderBlockParams(block) {
  const params = block.params;
  if (Object.keys(params).length === 0) {
    return '<span class="text-secondary" style="font-size: 11px">No parameters</span>';
  }

  return Object.entries(params)
    .map(
      ([key, value]) => `
                <div class="block-param">
                    <span class="block-param-label">${formatParamName(key)}</span>
                    <input type="text"
                           class="block-param-input"
                           value="${value}"
                           onchange="updateBlockParam('${block.id}', '${key}', this.value)"
                           onclick="event.stopPropagation()">
                </div>
            `
    )
    .join('');
}

function formatParamName(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function selectBlock(blockId) {
  // Close any open params popup when selecting different block
  const existingPopup = document.querySelector('.block-params-popup');
  if (existingPopup && existingPopup.dataset.blockId !== blockId) {
    closeBlockParamsPopup();
  }

  // Clear multi-selection when selecting single block
  clearMultiSelection();
  selectedBlockId = blockId;
  setSBSelectedBlockId(blockId);
  renderBlocks();
  renderBlockProperties();
}

function renderBlockProperties() {
  const container = document.getElementById('blockProperties');
  if (!container) return;
  const block = strategyBlocks.find((b) => b.id === selectedBlockId);

  if (!block) {
    container.innerHTML =
      '<p class="text-secondary" style="font-size: 13px; text-align: center; padding: 20px 0">Выберите блок на холсте, чтобы редактировать его параметры.</p>';
    return;
  }

  const headerHtml = `
    <div class="property-row">
      <span class="property-label">Name</span>
      <span class="property-value">${escapeHtml(block.name)}</span>
    </div>
    <div class="property-row">
      <span class="property-label">Type</span>
      <span class="property-value">${escapeHtml(block.type)}</span>
    </div>
    <div class="property-row">
      <span class="property-label">Category</span>
      <span class="property-value">${escapeHtml(block.category || '')}</span>
    </div>
    <hr style="border-color: var(--border-color); margin: 12px 0">
  `;

  const groupedHtml = renderGroupedParams(block, false);
  if (groupedHtml) {
    container.innerHTML = headerHtml + groupedHtml;
  } else {
    container.innerHTML =
      headerHtml +
      Object.entries(block.params || {})
        .map(
          ([key, value]) => `
        <div class="property-row">
          <span class="property-label">${formatParamName(key)}</span>
          <input type="text" class="property-input" value="${escapeHtml(String(value))}"
                 data-param-key="${escapeHtml(key)}"
                 data-block-id="${escapeHtml(block.id)}">
        </div>
      `
        )
        .join('');
  }
}

function escapeHtml(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// =============================================================================
// BLOCK PARAMETER VALIDATION
// =============================================================================

/**
 * Validation rules for block parameters.
 * Each rule specifies: min, max, type, required, allowedValues
 */
const blockValidationRules = {
  // Momentum Indicators
  rsi: {
    period: { min: 1, max: 200, type: 'number', required: true },
    long_rsi_more: { min: 0.1, max: 100, type: 'number' },
    long_rsi_less: { min: 0.1, max: 100, type: 'number' },
    short_rsi_less: { min: 0.1, max: 100, type: 'number' },
    short_rsi_more: { min: 0.1, max: 100, type: 'number' },
    cross_long_level: { min: 0.1, max: 100, type: 'number' },
    cross_short_level: { min: 0.1, max: 100, type: 'number' },
    cross_memory_bars: { min: 1, max: 100, type: 'number' }
  },
  stochastic: {
    k_period: { min: 1, max: 500, type: 'number', required: true },
    d_period: { min: 1, max: 100, type: 'number', required: true },
    smooth_k: { min: 1, max: 100, type: 'number' },
    overbought: { min: 0, max: 100, type: 'number' },
    oversold: { min: 0, max: 100, type: 'number' }
  },
  // Trend Indicators
  macd: {
    fast_period: { min: 1, max: 500, type: 'number', required: true },
    slow_period: { min: 1, max: 500, type: 'number', required: true },
    signal_period: { min: 1, max: 100, type: 'number', required: true },
    macd_cross_zero_level: { min: -1000, max: 1000, type: 'number' },
    signal_memory_bars: { min: 1, max: 100, type: 'number' }
  },
  supertrend: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 10, type: 'number', required: true }
  },
  qqe: {
    rsi_period: { min: 1, max: 500, type: 'number', required: true },
    qqe_factor: { min: 0.1, max: 20, type: 'number', required: true },
    smoothing_period: { min: 1, max: 100, type: 'number', required: true }
  },

  // Universal Filters
  atr_volatility: {
    atr_diff_percent: { min: 0.1, max: 50, type: 'number', required: true },
    atr_length1: { min: 5, max: 20, type: 'number', required: true },
    atr_length2: { min: 20, max: 100, type: 'number', required: true }
  },
  volume_filter: {
    vol_diff_percent: { min: 0.1, max: 50, type: 'number', required: true },
    vol_length1: { min: 5, max: 20, type: 'number', required: true },
    vol_length2: { min: 20, max: 100, type: 'number', required: true }
  },
  highest_lowest_bar: {
    hl_lookback_bars: { min: 1, max: 100, type: 'number', required: true },
    hl_price_percent: { min: 0, max: 30, type: 'number' },
    hl_atr_percent: { min: 0, max: 30, type: 'number' },
    atr_hl_length: { min: 1, max: 50, type: 'number' },
    block_worse_percent: { min: 0.1, max: 30, type: 'number' }
  },
  two_mas: {
    ma1_length: { min: 1, max: 500, type: 'number', required: true },
    ma2_length: { min: 1, max: 500, type: 'number', required: true },
    ma_cross_memory_bars: { min: 1, max: 100, type: 'number' }
  },
  accumulation_areas: {
    backtracking_interval: { min: 1, max: 100, type: 'number', required: true },
    min_bars_to_execute: { min: 1, max: 100, type: 'number', required: true }
  },
  keltner_bollinger: {
    keltner_length: { min: 0.1, max: 100, type: 'number' },
    keltner_mult: { min: 0.1, max: 100, type: 'number' },
    bb_length: { min: 0.1, max: 100, type: 'number' },
    bb_deviation: { min: 0.1, max: 100, type: 'number' }
  },
  rvi_filter: {
    rvi_length: { min: 1, max: 100, type: 'number', required: true },
    rvi_ma_length: { min: 1, max: 100, type: 'number' },
    rvi_long_more: { min: 1, max: 100, type: 'number' },
    rvi_long_less: { min: 1, max: 100, type: 'number' },
    rvi_short_less: { min: 1, max: 100, type: 'number' },
    rvi_short_more: { min: 1, max: 100, type: 'number' }
  },
  mfi_filter: {
    mfi_length: { min: 1, max: 100, type: 'number', required: true },
    mfi_long_more: { min: 1, max: 100, type: 'number' },
    mfi_long_less: { min: 1, max: 100, type: 'number' },
    mfi_short_less: { min: 1, max: 100, type: 'number' },
    mfi_short_more: { min: 1, max: 100, type: 'number' }
  },
  cci_filter: {
    cci_length: { min: 1, max: 100, type: 'number', required: true },
    cci_long_more: { min: -400, max: 400, type: 'number' },
    cci_long_less: { min: -400, max: 400, type: 'number' },
    cci_short_less: { min: -400, max: 400, type: 'number' },
    cci_short_more: { min: -400, max: 400, type: 'number' }
  },
  momentum_filter: {
    momentum_length: { min: 1, max: 100, type: 'number', required: true },
    momentum_long_more: { min: -100, max: 100, type: 'number' },
    momentum_long_less: { min: -100, max: 100, type: 'number' },
    momentum_short_less: { min: -100, max: 100, type: 'number' },
    momentum_short_more: { min: -100, max: 100, type: 'number' }
  },

  // Action Blocks
  stop_loss: {
    percent: { min: 0.001, max: 100, type: 'number', required: true }
  },
  take_profit: {
    percent: { min: 0.001, max: 1000, type: 'number', required: true }
  },
  trailing_stop: {
    percent: { min: 0.001, max: 100, type: 'number', required: true },
    activation: { min: 0, max: 100, type: 'number' }
  },
  atr_stop: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 20, type: 'number', required: true }
  },
  chandelier_stop: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 20, type: 'number', required: true }
  },
  break_even: {
    trigger: { min: 0.001, max: 100, type: 'number', required: true },
    offset: { min: -10, max: 10, type: 'number' }
  },
  profit_lock: {
    trigger: { min: 0.001, max: 100, type: 'number', required: true },
    lock_percent: { min: 0, max: 100, type: 'number', required: true }
  },
  scale_out: {
    target: { min: 0.001, max: 100, type: 'number', required: true },
    percent: { min: 1, max: 100, type: 'number', required: true }
  },
  multi_tp: {
    tp1: { min: 0.001, max: 1000, type: 'number' },
    tp2: { min: 0.001, max: 1000, type: 'number' },
    tp3: { min: 0.001, max: 1000, type: 'number' }
  },
  limit_entry: {
    offset_percent: { min: -50, max: 50, type: 'number', required: true }
  },
  stop_entry: {
    offset_percent: { min: -50, max: 50, type: 'number', required: true }
  },

  // Exit Blocks
  atr_exit: {
    atr_sl_period: { min: 1, max: 150, type: 'number' },
    atr_sl_multiplier: { min: 0.1, max: 4, type: 'number' },
    atr_tp_period: { min: 1, max: 150, type: 'number' },
    atr_tp_multiplier: { min: 0.1, max: 4, type: 'number' }
  },
  multi_tp_exit: {
    tp1: { min: 0.001, max: 1000, type: 'number' },
    tp2: { min: 0.001, max: 1000, type: 'number' },
    tp3: { min: 0.001, max: 1000, type: 'number' },
    alloc1: { min: 1, max: 100, type: 'number' },
    alloc2: { min: 1, max: 100, type: 'number' },
    alloc3: { min: 1, max: 100, type: 'number' }
  },
  static_sltp: {
    take_profit_percent: { min: 0.01, max: 100, type: 'number', required: true },
    stop_loss_percent: { min: 0.01, max: 100, type: 'number', required: true },
    breakeven_activation_percent: { min: 0.01, max: 100, type: 'number' },
    new_breakeven_sl_percent: { min: 0.001, max: 100, type: 'number' }
  },
  trailing_stop_exit: {
    activation_percent: { min: 0.01, max: 50, type: 'number', required: true },
    trailing_percent: { min: 0.01, max: 50, type: 'number', required: true }
  },

  // Conditions
  crossover: {},
  crossunder: {},
  greater_than: { value: { type: 'number' } },
  less_than: { value: { type: 'number' } },
  equals: { value: { type: 'number' } },
  between: {
    min_value: { type: 'number', required: true },
    max_value: { type: 'number', required: true }
  },

  // (divergence validation rules cleared — new blocks will be added)

  // Divergence Detection
  divergence: {
    pivot_interval: { min: 1, max: 9, type: 'number', required: true },
    keep_diver_signal_memory_bars: { min: 1, max: 100, type: 'number' },
    rsi_period: { min: 1, max: 200, type: 'number' },
    stoch_length: { min: 1, max: 200, type: 'number' },
    momentum_length: { min: 1, max: 200, type: 'number' },
    cmf_period: { min: 1, max: 200, type: 'number' },
    mfi_length: { min: 1, max: 200, type: 'number' }
  }
};

/**
 * Validate a single parameter value against rules.
 * @param {*} value - The parameter value
 * @param {Object} rule - The validation rule
 * @param {string} paramName - Parameter name for error message
 * @returns {{valid: boolean, error: string|null}}
 */
function validateParamValue(value, rule, paramName) {
  if (!rule) return { valid: true, error: null };

  // Check required
  if (rule.required && (value === undefined || value === null || value === '')) {
    return { valid: false, error: `${formatParamName(paramName)} is required` };
  }

  // Skip validation if empty and not required
  if (value === undefined || value === null || value === '') {
    return { valid: true, error: null };
  }

  // Type validation
  if (rule.type === 'number') {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) {
      return { valid: false, error: `${formatParamName(paramName)} must be a number` };
    }

    // Range validation
    if (rule.min !== undefined && numValue < rule.min) {
      return { valid: false, error: `${formatParamName(paramName)} must be >= ${rule.min}` };
    }
    if (rule.max !== undefined && numValue > rule.max) {
      return { valid: false, error: `${formatParamName(paramName)} must be <= ${rule.max}` };
    }
  }

  // Allowed values validation
  if (rule.allowedValues && !rule.allowedValues.includes(value)) {
    return { valid: false, error: `${formatParamName(paramName)} must be one of: ${rule.allowedValues.join(', ')}` };
  }

  return { valid: true, error: null };
}

/**
 * Validate all parameters of a block.
 * @param {Object} block - The block to validate
 * @returns {{valid: boolean, errors: string[]}}
 */
function validateBlockParams(block) {
  const rules = blockValidationRules[block.type];
  if (!rules) return { valid: true, errors: [] };

  const errors = [];

  // RSI range params are only relevant when their feature flag is enabled
  const rsiRangeSkip = block.type === 'rsi' ? new Set([
    ...(block.params.use_long_range ? [] : ['long_rsi_more', 'long_rsi_less']),
    ...(block.params.use_short_range ? [] : ['short_rsi_less', 'short_rsi_more']),
    ...(block.params.use_cross_long ? [] : ['cross_long_level', 'cross_memory_bars']),
    ...(block.params.use_cross_short ? [] : ['cross_short_level', 'cross_memory_bars'])
  ]) : null;

  for (const [paramName, rule] of Object.entries(rules)) {
    // Skip RSI range params when the corresponding feature is disabled
    if (rsiRangeSkip && rsiRangeSkip.has(paramName)) continue;

    const value = block.params[paramName];
    const result = validateParamValue(value, rule, paramName);
    if (!result.valid) {
      errors.push(result.error);
    }
  }

  // Additional cross-parameter validations
  if (block.type === 'macd') {
    const fast = parseFloat(block.params.fast_period);
    const slow = parseFloat(block.params.slow_period);
    if (!isNaN(fast) && !isNaN(slow) && fast >= slow) {
      errors.push('Fast period must be less than slow period');
    }
  }

  if (block.type === 'between') {
    const min = parseFloat(block.params.min_value);
    const max = parseFloat(block.params.max_value);
    if (!isNaN(min) && !isNaN(max) && min >= max) {
      errors.push('Min value must be less than max value');
    }
  }

  if (block.type === 'multi_tp' || block.type === 'multi_tp_exit') {
    const tp1 = parseFloat(block.params.tp1 || 0);
    const tp2 = parseFloat(block.params.tp2 || 0);
    const tp3 = parseFloat(block.params.tp3 || 0);
    if (tp1 > 0 && tp2 > 0 && tp1 >= tp2) {
      errors.push('TP1 must be less than TP2');
    }
    if (tp2 > 0 && tp3 > 0 && tp2 >= tp3) {
      errors.push('TP2 must be less than TP3');
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Update visual validation state on a block element.
 * @param {string} blockId - Block ID
 * @param {{valid: boolean, errors: string[]}} validationResult
 */
function updateBlockValidationState(blockId, validationResult) {
  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  // Remove existing validation classes
  blockEl.classList.remove('block-valid', 'block-invalid');

  if (validationResult.valid) {
    blockEl.classList.add('block-valid');
    blockEl.title = '';
  } else {
    blockEl.classList.add('block-invalid');
    blockEl.title = validationResult.errors.join('\n');
  }
}

/**
 * Real-time validation for parameter input.
 * @param {HTMLInputElement} input - The input element
 */
function validateParamInput(input) {
  const blockId = input.dataset.blockId;
  const paramKey = input.dataset.paramKey;
  const block = strategyBlocks.find(b => b.id === blockId);

  if (!block) return;

  const rules = blockValidationRules[block.type];
  const rule = rules ? rules[paramKey] : null;

  const result = validateParamValue(input.value, rule, paramKey);

  // Update input visual state
  input.classList.remove('param-valid', 'param-invalid');
  if (!result.valid) {
    input.classList.add('param-invalid');
    input.title = result.error;
  } else {
    input.classList.add('param-valid');
    input.title = '';
  }

  // Also update the block's overall validation state
  const fullValidation = validateBlockParams(block);
  updateBlockValidationState(blockId, fullValidation);
}

function updateBlockParam(blockId, param, value) {
  const block = strategyBlocks.find((b) => b.id === blockId);
  if (block) {
    // Store the value — preserve booleans and strings, only parse numeric strings
    let parsedValue;
    if (typeof value === 'boolean') {
      parsedValue = value;                            // checkbox true/false
    } else if (typeof value === 'string' && value !== '' && !isNaN(value)) {
      parsedValue = parseFloat(value);                // numeric string → number
    } else {
      parsedValue = value;                            // string (select), empty, etc.
    }
    block.params[param] = parsedValue;

    // Update hint on the block without full re-render
    const blockEl = document.getElementById(blockId);
    if (blockEl) {
      const hintEl = blockEl.querySelector('.block-param-hint');
      if (hintEl) {
        hintEl.textContent = getCompactParamHint(block.params, block.type);
      }
    }

    // Re-render connections to update direction mismatch highlighting
    // (param changes in any block may affect wire validity)
    renderConnections();

    // Local validation (immediate feedback)
    const validationResult = validateBlockParams(block);
    updateBlockValidationState(blockId, validationResult);

    // Log validation errors if any
    if (!validationResult.valid) {
      console.warn(`[Strategy Builder] Block ${blockId} validation errors:`, validationResult.errors);
    }

    // WebSocket validation (server-side, debounced)
    if (wsValidation && wsValidation.isWsConnected()) {
      wsValidation.validateParam(blockId, block.type, param, parsedValue, (result) => {
        if (!result.fallback && !result.valid) {
          // Server found additional errors - update UI
          const serverErrors = result.messages
            .filter(m => m.severity === 'error')
            .map(m => m.message);
          if (serverErrors.length > 0) {
            const combined = [...validationResult.errors, ...serverErrors];
            updateBlockValidationState(blockId, { valid: false, errors: combined });
          }
        }
      });
    }

    // BTC-source checkbox enabled → trigger BTCUSDT sync for the node's TF
    const BTC_SOURCE_PARAM_KEYS = ['use_btc_source', 'use_btcusdt_mfi', 'use_btcusdt_momentum'];
    if (BTC_SOURCE_PARAM_KEYS.includes(param) && parsedValue === true) {
      syncBtcSourceForNode(blockId);
    }
  }
}

// ============================================
// BTC SOURCE SYNC FOR NODE
// ============================================

/**
 * Sync BTCUSDT data for a node that uses "Use BTCUSDT as Source".
 * Uses the node's own `timeframe` param to highlight the relevant TF in status.
 * Shows inline status in the active popup or properties panel.
 *
 * @param {string} blockId - ID of the block that has BTC source enabled
 */
async function syncBtcSourceForNode(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  const nodeTf = (block.params && block.params.timeframe) || null;
  // TF names for display
  const TF_DISPLAY = { '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '240': '4h', 'D': '1D', 'W': '1W', 'M': '1M' };
  const tfLabel = nodeTf && nodeTf !== 'Chart' ? (TF_DISPLAY[nodeTf] || nodeTf) : null;
  const tfNote = tfLabel ? ` [TF: ${tfLabel}]` : '';

  const marketEl = document.getElementById('builderMarketType');
  const marketType = marketEl?.value === 'spot' ? 'spot' : 'linear';

  // Find or create the inline BTC status container
  // It is placed in the active popup OR in the properties panel after the BTC checkbox row
  function _getBtcStatusEl() {
    // Try popup first
    const popup = document.querySelector(`.block-params-popup[data-block-id="${blockId}"]`);
    if (popup) {
      let el = popup.querySelector('.btc-source-sync-status');
      if (!el) {
        el = document.createElement('div');
        el.className = 'btc-source-sync-status';
        el.style.cssText = 'margin: 4px 8px 4px 8px; padding: 6px 10px; border-radius: 4px; font-size: 11px; background: var(--input-bg, #1e2130); border: 1px solid var(--border-color, #3d4460); color: var(--text-secondary, #a0a8c3);';
        // Insert at the top of popup-body
        const body = popup.querySelector('.popup-body');
        if (body) body.insertBefore(el, body.firstChild);
        else popup.appendChild(el);
      }
      return el;
    }
    // Try properties panel
    const propsEl = document.getElementById('blockProperties');
    if (propsEl) {
      let el = propsEl.querySelector('.btc-source-sync-status');
      if (!el) {
        el = document.createElement('div');
        el.className = 'btc-source-sync-status';
        el.style.cssText = 'margin: 4px 0; padding: 6px 10px; border-radius: 4px; font-size: 11px; background: var(--input-bg, #1e2130); border: 1px solid var(--border-color, #3d4460); color: var(--text-secondary, #a0a8c3);';
        propsEl.insertBefore(el, propsEl.firstChild);
      }
      return el;
    }
    return null;
  }

  function _setStatus(icon, text, color) {
    const el = _getBtcStatusEl();
    if (!el) return;
    el.style.borderColor = color || 'var(--border-color, #3d4460)';
    el.innerHTML = `<span style="margin-right:5px">${escapeHtml(icon)}</span>${escapeHtml(text)}`;
  }

  // Check cache — skip if synced recently (same logic as main sync, 10s grace)
  const BTC_SYNC_CACHE_KEY = 'BTCUSDT_btcsource';
  const lastSync = _btcSyncCache[BTC_SYNC_CACHE_KEY];
  if (lastSync && Date.now() - lastSync < 10000) {
    _setStatus('✓', `BTCUSDT${tfNote} — данные актуальны`, '#4caf50');
    return;
  }

  _setStatus('🔍', `Проверка BTCUSDT${tfNote}...`, 'var(--border-color, #3d4460)');

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90000);

  try {
    const streamUrl = `${API_BASE}/marketdata/symbols/sync-all-tf-stream?symbol=BTCUSDT&market_type=${marketType}`;
    console.log(`[BtcSourceSync] Starting BTCUSDT sync for node ${blockId} (TF=${nodeTf || 'Chart'}):`, streamUrl);

    const response = await fetch(streamUrl, { signal: controller.signal });
    if (!response.ok) {
      clearTimeout(timeoutId);
      _setStatus('⚠️', `BTCUSDT — ошибка HTTP ${response.status}`, '#f44336');
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;

    _setStatus('📥', `Синхронизация BTCUSDT${tfNote}...`, '#2196f3');

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      clearTimeout(timeoutId);
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const dataMatch = line.match(/^data:\s*(.+)$/m);
        if (!dataMatch) continue;
        try {
          const data = JSON.parse(dataMatch[1]);
          if (data.event === 'progress') {
            // Highlight the node's TF in the progress message
            const isCurrent = nodeTf && nodeTf !== 'Chart' && data.tf === nodeTf;
            const tfMark = isCurrent ? ` ← [${tfLabel}]` : '';
            _setStatus('📥', `BTCUSDT: ${data.tfName || data.tf}${tfMark} (${data.step}/${data.totalSteps || 9})`, '#2196f3');
          } else if (data.event === 'complete') {
            clearTimeout(timeoutId);
            result = data;
          } else if (data.event === 'error') {
            console.warn('[BtcSourceSync] TF error (non-fatal):', data.message);
          }
        } catch (_) { /* skip parse error */ }
      }
    }

    clearTimeout(timeoutId);

    if (result) {
      _btcSyncCache[BTC_SYNC_CACHE_KEY] = Date.now();
      const totalNew = result.totalNew || 0;
      const newText = totalNew > 0 ? `, +${totalNew} свечей` : '';
      _setStatus('✅', `BTCUSDT${tfNote} — готово${newText}`, '#4caf50');
      console.log(`[BtcSourceSync] BTCUSDT sync complete for node ${blockId}`, result);
    } else {
      _setStatus('⚠️', `BTCUSDT${tfNote} — нет результата`, '#ff9800');
    }
  } catch (e) {
    clearTimeout(timeoutId);
    if (e.name === 'AbortError') {
      _setStatus('⚠️', `BTCUSDT${tfNote} — таймаут соединения`, '#ff9800');
    } else {
      _setStatus('⚠️', `BTCUSDT${tfNote} — ${e.message}`, '#f44336');
    }
    console.error('[BtcSourceSync] Failed:', e);
  }
}

// ============================================
// NODE REPULSION (Avoid Overlapping)
// ============================================

/**
 * Push overlapping nodes away from the dragged block.
 * Small interaction zone - only pushes when blocks actually overlap.
 * @param {string} movedBlockId - ID of the block that was just moved
 */
function applyNodeRepulsion(movedBlockId) {
  const movedBlock = strategyBlocks.find(b => b.id === movedBlockId);
  if (!movedBlock) return;

  const movedEl = document.getElementById(movedBlockId);
  if (!movedEl) return;

  const movedBounds = {
    left: movedBlock.x,
    top: movedBlock.y,
    right: movedBlock.x + movedEl.offsetWidth,
    bottom: movedBlock.y + movedEl.offsetHeight,
    width: movedEl.offsetWidth,
    height: movedEl.offsetHeight,
    centerX: movedBlock.x + movedEl.offsetWidth / 2,
    centerY: movedBlock.y + movedEl.offsetHeight / 2
  };

  // Small gap to maintain between blocks (10px)
  const minGap = 10;

  strategyBlocks.forEach(block => {
    // Skip self only
    if (block.id === movedBlockId) return;

    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight,
      width: blockEl.offsetWidth,
      height: blockEl.offsetHeight,
      centerX: block.x + blockEl.offsetWidth / 2,
      centerY: block.y + blockEl.offsetHeight / 2
    };

    // Check if blocks actually overlap (including small gap)
    const gapX = Math.max(movedBounds.left, blockBounds.left) - Math.min(movedBounds.right, blockBounds.right);
    const gapY = Math.max(movedBounds.top, blockBounds.top) - Math.min(movedBounds.bottom, blockBounds.bottom);

    // Only push if blocks overlap or are closer than minGap
    if (gapX < minGap && gapY < minGap) {
      // Calculate how much they overlap (negative gap = overlap)
      const overlapX = minGap - gapX;
      const overlapY = minGap - gapY;

      // Calculate push direction (from moved block center to other block center)
      const dx = blockBounds.centerX - movedBounds.centerX;
      const dy = blockBounds.centerY - movedBounds.centerY;

      // Push along the axis with less overlap (minimal movement)
      if (overlapX <= overlapY) {
        // Push horizontally
        const pushDir = dx >= 0 ? 1 : -1;
        block.x = Math.max(0, block.x + overlapX * pushDir);
      } else {
        // Push vertically
        const pushDir = dy >= 0 ? 1 : -1;
        block.y = Math.max(0, block.y + overlapY * pushDir);
      }

      // Update DOM position
      blockEl.style.left = `${block.x}px`;
      blockEl.style.top = `${block.y}px`;
    }
  });

  // Update connections after repulsion
  renderConnections();
}

function startDragBlock(event, blockId) {
  if (event.target.closest('.block-param-input')) return;

  // Close popup when starting to drag
  closeBlockParamsPopup();

  // pushUndo is deferred to the first real movement (BUG#5 fix)
  isDragging = true;
  let undoPushed = false;
  const block = document.getElementById(blockId);
  const containerRect = document.getElementById('canvasContainer').getBoundingClientRect();

  // BUG#1 FIX: compute dragOffset in LOGICAL space (divide screen offset by zoom)
  const blockData = strategyBlocks.find((b) => b.id === blockId);
  dragOffset = {
    x: (event.clientX - containerRect.left) / zoom - (blockData ? blockData.x : 0),
    y: (event.clientY - containerRect.top) / zoom - (blockData ? blockData.y : 0)
  };

  let rafPending = false;

  const onMouseMove = (e) => {
    if (!isDragging) return;

    const container = document
      .getElementById('canvasContainer')
      .getBoundingClientRect();

    // BUG#1 FIX: convert screen coords to logical by dividing by zoom
    const x = (e.clientX - container.left) / zoom - dragOffset.x;
    const y = (e.clientY - container.top) / zoom - dragOffset.y;

    // BUG#5 FIX: push undo only on first real movement (> 3px)
    if (!undoPushed && blockData) {
      const dx = x - blockData.x;
      const dy = y - blockData.y;
      if (Math.hypot(dx, dy) > 3) {
        pushUndo();
        undoPushed = true;
      }
    }

    // Update DOM position immediately for responsiveness
    block.style.left = `${Math.max(0, x)}px`;
    block.style.top = `${Math.max(0, y)}px`;

    // Update state
    if (blockData) {
      blockData.x = Math.max(0, x);
      blockData.y = Math.max(0, y);
    }

    // Throttle connection rendering using requestAnimationFrame
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(() => {
        renderConnections();
        rafPending = false;
      });
    }
  };

  const onMouseUp = () => {
    isDragging = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);

    // Apply node repulsion to push away overlapping blocks
    applyNodeRepulsion(blockId);

    // Try auto-snap connection if block dropped near compatible port
    tryAutoSnapConnection(blockId);

    renderConnections(); // Update connections when block moved
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

// ============================================
// MARQUEE SELECTION (Rectangle Select)
// ============================================

function startMarqueeSelection(event) {
  // Clear previous selection if not holding Shift
  if (!event.shiftKey) {
    selectedBlockIds = [];
    clearMultiSelection();
  }

  isMarqueeSelecting = true;
  const container = document.getElementById('canvasContainer');
  const blocksContainer = document.getElementById('blocksContainer');
  const rect = container.getBoundingClientRect();

  marqueeStart = {
    // BUG#2 FIX: convert screen offset to logical space by dividing by zoom
    x: (event.clientX - rect.left) / zoom,
    y: (event.clientY - rect.top) / zoom
  };

  // Create marquee element in blocksContainer (same coordinate system as blocks)
  marqueeElement = document.createElement('div');
  marqueeElement.className = 'marquee-selection';
  marqueeElement.style.cssText = `
    position: absolute;
    border: 2px dashed #58a6ff;
    background: rgba(88, 166, 255, 0.15);
    pointer-events: none;
    z-index: 9999;
    border-radius: 4px;
  `;
  blocksContainer.appendChild(marqueeElement);

  const onMouseMove = (e) => {
    if (!isMarqueeSelecting) return;

    // BUG#2 FIX: convert screen coords to logical space by dividing by zoom
    const currentX = (e.clientX - rect.left) / zoom;
    const currentY = (e.clientY - rect.top) / zoom;

    const left = Math.min(marqueeStart.x, currentX);
    const top = Math.min(marqueeStart.y, currentY);
    const width = Math.abs(currentX - marqueeStart.x);
    const height = Math.abs(currentY - marqueeStart.y);

    marqueeElement.style.left = `${left}px`;
    marqueeElement.style.top = `${top}px`;
    marqueeElement.style.width = `${width}px`;
    marqueeElement.style.height = `${height}px`;

    // Highlight blocks inside marquee
    highlightBlocksInMarquee(left, top, width, height);
  };

  const onMouseUp = () => {
    isMarqueeSelecting = false;

    // Get final selection
    if (marqueeElement) {
      const marqueeBounds = {
        left: parseInt(marqueeElement.style.left),
        top: parseInt(marqueeElement.style.top),
        width: parseInt(marqueeElement.style.width),
        height: parseInt(marqueeElement.style.height)
      };
      selectBlocksInMarquee(marqueeBounds);
      marqueeElement.remove();
      marqueeElement = null;
    }

    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function highlightBlocksInMarquee(left, top, width, height) {
  const marqueeBounds = { left, top, right: left + width, bottom: top + height };

  strategyBlocks.forEach(block => {
    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight
    };

    // Check intersection
    const intersects = !(
      blockBounds.right < marqueeBounds.left ||
      blockBounds.left > marqueeBounds.right ||
      blockBounds.bottom < marqueeBounds.top ||
      blockBounds.top > marqueeBounds.bottom
    );

    blockEl.classList.toggle('marquee-hover', intersects);
  });
}

function selectBlocksInMarquee(bounds) {
  strategyBlocks.forEach(block => {
    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    blockEl.classList.remove('marquee-hover');

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight
    };

    // Check intersection
    const intersects = !(
      blockBounds.right < bounds.left ||
      blockBounds.left > bounds.left + bounds.width ||
      blockBounds.bottom < bounds.top ||
      blockBounds.top > bounds.top + bounds.height
    );

    if (intersects && !selectedBlockIds.includes(block.id)) {
      selectedBlockIds.push(block.id);
      blockEl.classList.add('multi-selected');
    }
  });

  console.log('[Strategy Builder] Selected blocks:', selectedBlockIds.length);
}

function clearMultiSelection() {
  document.querySelectorAll('.strategy-block.multi-selected').forEach(el => {
    el.classList.remove('multi-selected');
  });
  selectedBlockIds = [];
}

/**
 * Enable/disable the primary action buttons based on whether a symbol is selected.
 * Called on init and whenever the symbol input changes.
 */
function updateRunButtonsState() {
  const symbol = document.getElementById('backtestSymbol')?.value?.trim();
  const canRun = Boolean(symbol);
  const tooltip = canRun ? '' : 'Сначала выберите Symbol';
  ['btnBacktest', 'btnGenerateCode', 'btnStartOptimization'].forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.disabled = !canRun;
    btn.title = canRun ? btn.dataset.originalTitle || '' : tooltip;
    if (!btn.dataset.originalTitle && canRun) {
      // Store original title once it has a value, so we can restore it later
      btn.dataset.originalTitle = btn.title;
    }
  });
}

// ============================================
// GROUP DRAG
// ============================================

function startGroupDrag(event) {
  // Close popup when starting group drag
  closeBlockParamsPopup();

  pushUndo();
  isGroupDragging = true;

  const container = document.getElementById('canvasContainer');
  const rect = container.getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  // Calculate offset from mouse for each selected block
  groupDragOffsets = {};
  selectedBlockIds.forEach(blockId => {
    const block = strategyBlocks.find(b => b.id === blockId);
    if (block) {
      groupDragOffsets[blockId] = {
        x: block.x - mouseX,
        y: block.y - mouseY
      };
    }
  });

  let rafPending = false;

  const onMouseMove = (e) => {
    if (!isGroupDragging) return;

    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;

    // Move all selected blocks immediately for responsiveness
    selectedBlockIds.forEach(blockId => {
      const block = strategyBlocks.find(b => b.id === blockId);
      const blockEl = document.getElementById(blockId);
      const offset = groupDragOffsets[blockId];

      if (block && blockEl && offset) {
        const newX = Math.max(0, currentX + offset.x);
        const newY = Math.max(0, currentY + offset.y);

        block.x = newX;
        block.y = newY;
        blockEl.style.left = `${newX}px`;
        blockEl.style.top = `${newY}px`;
      }
    });

    // Throttle connection rendering using requestAnimationFrame
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(() => {
        renderConnections();
        rafPending = false;
      });
    }
  };

  const onMouseUp = () => {
    isGroupDragging = false;

    // Apply node repulsion for all moved blocks
    const movedBlockIdsCopy = [...selectedBlockIds];
    movedBlockIdsCopy.forEach(blockId => {
      applyNodeRepulsionForGroup(blockId, movedBlockIdsCopy);
    });

    groupDragOffsets = {};
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    renderConnections();
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

/**
 * Apply repulsion for group drag - excludes other selected blocks
 * @param {string} movedBlockId - ID of block to check collisions for
 * @param {string[]} excludeIds - IDs of other blocks in the group (don't push them)
 */
function applyNodeRepulsionForGroup(movedBlockId, excludeIds) {
  const movedBlock = strategyBlocks.find(b => b.id === movedBlockId);
  if (!movedBlock) return;

  const movedEl = document.getElementById(movedBlockId);
  if (!movedEl) return;

  const movedBounds = {
    left: movedBlock.x,
    top: movedBlock.y,
    right: movedBlock.x + movedEl.offsetWidth,
    bottom: movedBlock.y + movedEl.offsetHeight,
    centerX: movedBlock.x + movedEl.offsetWidth / 2,
    centerY: movedBlock.y + movedEl.offsetHeight / 2
  };

  // Small gap to maintain between blocks (10px)
  const minGap = 10;

  strategyBlocks.forEach(block => {
    // Skip self and other selected blocks (they move together)
    if (block.id === movedBlockId || excludeIds.includes(block.id)) return;

    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight,
      centerX: block.x + blockEl.offsetWidth / 2,
      centerY: block.y + blockEl.offsetHeight / 2
    };

    // Check if blocks actually overlap (including small gap)
    const gapX = Math.max(movedBounds.left, blockBounds.left) - Math.min(movedBounds.right, blockBounds.right);
    const gapY = Math.max(movedBounds.top, blockBounds.top) - Math.min(movedBounds.bottom, blockBounds.bottom);

    // Only push if blocks overlap or are closer than minGap
    if (gapX < minGap && gapY < minGap) {
      const overlapX = minGap - gapX;
      const overlapY = minGap - gapY;

      const dx = blockBounds.centerX - movedBounds.centerX;
      const dy = blockBounds.centerY - movedBounds.centerY;

      if (overlapX <= overlapY) {
        const pushDir = dx >= 0 ? 1 : -1;
        block.x = Math.max(0, block.x + overlapX * pushDir);
      } else {
        const pushDir = dy >= 0 ? 1 : -1;
        block.y = Math.max(0, block.y + overlapY * pushDir);
      }

      blockEl.style.left = `${block.x}px`;
      blockEl.style.top = `${block.y}px`;
    }
  });
}


function exportAsTemplate() {
  const blocksToExport = strategyBlocks.filter((b) => !b.isMain);
  if (blocksToExport.length === 0) {
    showNotification('Добавьте блоки для экспорта', 'warning');
    return;
  }
  const payload = {
    name: document.getElementById('strategyName')?.value || 'Exported Strategy',
    exportedAt: new Date().toISOString(),
    blocks: blocksToExport.map((b) => ({
      id: b.id,
      type: b.type,
      category: b.category,
      name: b.name,
      icon: b.icon,
      x: b.x,
      y: b.y,
      params: { ...b.params }
    })),
    connections: connections.map((c) => ({
      source: { blockId: c.source.blockId, portId: c.source.portId },
      target: { blockId: c.target.blockId, portId: c.target.portId },
      type: c.type
    }))
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `strategy-template-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  showNotification('Шаблон экспортирован', 'success');
}

function importTemplateFromFile(file) {
  if (!file || !file.name?.toLowerCase().endsWith('.json')) {
    showNotification('Выберите .json файл', 'warning');
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      const blocks = data.blocks || [];
      const conns = data.connections || [];
      if (blocks.length === 0) {
        showNotification('Файл не содержит блоков', 'error');
        return;
      }
      pushUndo();
      const mainNode = strategyBlocks.find((b) => b.isMain);
      strategyBlocks = mainNode ? [mainNode] : [];
      blocks.forEach((block) => {
        if (block.id === 'main_strategy' || block.isMain) return;
        strategyBlocks.push({ ...block });
      });
      connections.length = 0;
      conns.forEach((conn) => {
        const srcExists = strategyBlocks.some((b) => b.id === conn.source?.blockId);
        const tgtExists = strategyBlocks.some((b) => b.id === conn.target?.blockId) ||
          conn.target?.blockId === 'main_strategy';
        if (srcExists && (tgtExists || strategyBlocks.some((b) => b.isMain))) {
          const targetId = conn.target?.blockId === 'main_strategy'
            ? strategyBlocks.find((b) => b.isMain)?.id
            : conn.target?.blockId;
          if (targetId) {
            connections.push({
              id: `conn_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
              source: { blockId: conn.source.blockId, portId: conn.source.portId || 'value' },
              target: { blockId: targetId, portId: conn.target.portId || 'value' },
              type: conn.type || 'data'
            });
          }
        }
      });
      // renderBlocks calls renderConnections internally
      setSBBlocks(strategyBlocks);
      setSBConnections(connections);
      renderBlocks();
      dispatchBlocksChanged();
      showNotification(`Импортировано: ${blocks.length} блоков`, 'success');
    } catch (err) {
      showNotification(`Ошибка импорта: ${err.message}`, 'error');
    }
  };
  reader.readAsText(file);
}


// Helper function to get strategy ID from URL
function getStrategyIdFromURL() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('id');
}

// Helper function to update "Last saved" timestamp
function updateLastSaved(timestamp = null) {
  const lastSavedEl = document.querySelector('.text-secondary.text-sm');
  if (lastSavedEl) {
    if (timestamp) {
      const date = new Date(timestamp);
      lastSavedEl.innerHTML = `<i class="bi bi-clock"></i> Last saved: ${date.toLocaleString()}`;
    } else {
      lastSavedEl.innerHTML = `<i class="bi bi-clock"></i> Last saved: ${new Date().toLocaleString()}`;
    }
  }
}

/**
 * Dispatch event when strategy blocks change
 * This notifies optimization_panels.js to sync parameter ranges
 */
function dispatchBlocksChanged() {
  const event = new CustomEvent('strategyBlocksChanged', {
    detail: { blocks: strategyBlocks }
  });
  document.dispatchEvent(event);
  console.log('[Strategy Builder] Dispatched strategyBlocksChanged event with', strategyBlocks.length, 'blocks');
}

// Helper function to show notifications
function showNotification(message, type = 'info') {
  console.log(`[${type.toUpperCase()}] ${message}`);

  // Try to find or create notification container
  let notificationContainer = document.getElementById('notificationContainer');
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notificationContainer';
    document.body.appendChild(notificationContainer);
  }
  // Always update styles to ensure bottom position
  notificationContainer.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 10000;
    display: flex;
    flex-direction: column-reverse;
    gap: 10px;
  `;

  // Create notification element
  const notification = document.createElement('div');
  const colors = {
    success: { bg: '#28a745', text: '#fff' },
    error: { bg: '#dc3545', text: '#fff' },
    warning: { bg: '#ffc107', text: '#000' },
    info: { bg: '#17a2b8', text: '#fff' }
  };

  const color = colors[type] || colors.info;
  notification.style.cssText = `
    background: ${color.bg};
    color: ${color.text};
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 250px;
    max-width: 400px;
    animation: slideInBottom 0.3s ease;
  `;
  notification.textContent = message;

  // Add animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideInBottom {
      from { transform: translateY(100px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  `;
  if (!document.getElementById('notificationStyles')) {
    style.id = 'notificationStyles';
    document.head.appendChild(style);
  }

  notificationContainer.appendChild(notification);

  // Auto-remove after delay
  const delay = type === 'error' ? 5000 : type === 'warning' ? 4000 : 3000;
  setTimeout(() => {
    notification.style.animation = 'slideInBottom 0.3s ease reverse';
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, delay);

  // Fallback to console if critical
  if (type === 'error') {
    console.error(message);
  }
}

// ============================================
// ZOOM FUNCTIONS
// ============================================
function fitToScreen() {
  resetZoom();
}

function zoomIn() {
  zoom = Math.min(zoom + 0.1, 2);
  setSBZoom(zoom);
  updateZoom();
}

function zoomOut() {
  zoom = Math.max(zoom - 0.1, 0.5);
  setSBZoom(zoom);
  updateZoom();
}

function resetZoom() {
  zoom = 1;
  setSBZoom(zoom);
  updateZoom();
}

function updateZoom() {
  document.getElementById('zoomLevel').textContent =
    `${Math.round(zoom * 100)}%`;
  document.getElementById('blocksContainer').style.transform = `scale(${zoom})`;
  document.getElementById('blocksContainer').style.transformOrigin = '0 0';
}


// ============================================
// BACKTEST MODULE — initialized after state setup
// Functions are wired to BacktestModule instance.
// See: frontend/js/components/BacktestModule.js
// ============================================

// NOTE: _backtestModule is initialized in initializeStrategyBuilder()
// after getStrategyIdFromURL, showNotification, etc. are in scope.
// Declaration is hoisted to top-level to avoid TDZ issues.

function _initBacktestModule() {
  _backtestModule = createBacktestModule({
    getBlocks: () => getSBBlocks(),
    getBlockLibrary: () => blockLibrary,
    getDefaultParams,
    showNotification,
    saveStrategy,
    autoSaveStrategy,
    validateStrategyCompleteness,
    validateStrategy,
    getStrategyIdFromURL,
    setSBCurrentBacktestResults
  });
}

// Delegate wrappers so existing call sites work unchanged
async function runBacktest() { return _backtestModule ? _backtestModule.runBacktest() : Promise.resolve(); }
// eslint-disable-next-line no-unused-vars
function _buildBacktestRequest() { return _backtestModule ? _backtestModule.buildBacktestRequest() : {}; }
function displayBacktestResults(results) { if (_backtestModule) _backtestModule.displayBacktestResults(results); }
function switchResultsTab(tabId) { if (_backtestModule) _backtestModule.switchResultsTab(tabId); }
function closeBacktestResultsModal() { if (_backtestModule) _backtestModule.closeBacktestResultsModal(); }
function exportBacktestResults() { if (_backtestModule) _backtestModule.exportBacktestResults(); }
function viewFullResults() { if (_backtestModule) _backtestModule.viewFullResults(); }

function showBlockMenu(blockId) {
  // Would show context menu
  console.log('Show menu for', blockId);
}

// Механизмы сворачивания отключены — функция заглушка
function toggleRightSidebar() {
  // no-op
}

// Make toggleRightSidebar available globally
window.toggleRightSidebar = toggleRightSidebar;

// ============================================
// AI BUILD MODULE — initialized after state setup
// Functions are wired to AiBuildModule instance.
// See: frontend/js/components/AiBuildModule.js
// ============================================

// NOTE: _aiModule is declared near other state vars to avoid TDZ.

function _initAiBuildModule() {
  _aiModule = createAiBuildModule({
    getStrategyIdFromURL,
    getBlocks: () => getSBBlocks(),
    getConnections: () => getSBConnections(),
    displayBacktestResults,
    loadStrategy,
    escapeHtml
  });
}

// Delegate wrappers so existing call sites work unchanged
function openAiBuildModal() { if (_aiModule) _aiModule.openAiBuildModal(); }
function closeAiBuildModal() { if (_aiModule) _aiModule.closeAiBuildModal(); }
function applyAiPreset() { if (_aiModule) _aiModule.applyAiPreset(); }
function resetAiBuild() { if (_aiModule) _aiModule.resetAiBuild(); }
async function runAiBuild() { return _aiModule ? _aiModule.runAiBuild() : Promise.resolve(); }
async function showAiBuildResults(data) { return _aiModule ? _aiModule.showAiBuildResults(data) : Promise.resolve(); }
function toggleAgentMonitor() { if (_aiModule) _aiModule.toggleAgentMonitor(); }
function viewAiBacktestFullResults(id) { if (_aiModule) _aiModule.viewAiBacktestFullResults(id); }


// ============================================
// MY STRATEGIES MODULE
// Functions are wired to MyStrategiesModule instance.
// See: frontend/js/components/MyStrategiesModule.js
// ============================================

// NOTE: _myStrategiesModule is declared near other state vars to avoid TDZ.

function _initMyStrategiesModule() {
  _myStrategiesModule = createMyStrategiesModule({
    getStrategyIdFromURL,
    loadStrategy,
    showNotification,
    escapeHtml
  });
}

// Delegate wrappers so existing call sites work unchanged
async function fetchStrategiesList() { return _myStrategiesModule ? _myStrategiesModule.fetchStrategiesList() : []; }
async function openMyStrategiesModal() { return _myStrategiesModule ? _myStrategiesModule.openMyStrategiesModal() : Promise.resolve(); }
function closeMyStrategiesModal() { if (_myStrategiesModule) _myStrategiesModule.closeMyStrategiesModal(); }
function toggleSelectAll() { if (_myStrategiesModule) _myStrategiesModule.toggleSelectAll(); }
async function batchDeleteSelected() { return _myStrategiesModule ? _myStrategiesModule.batchDeleteSelected() : Promise.resolve(); }
async function cloneStrategy(id, name) { return _myStrategiesModule ? _myStrategiesModule.cloneStrategy(id, name) : Promise.resolve(); }
async function deleteStrategyById(id, name) { return _myStrategiesModule ? _myStrategiesModule.deleteStrategyById(id, name) : Promise.resolve(); }
function filterStrategiesList() { if (_myStrategiesModule) _myStrategiesModule.filterStrategiesList(); }


// ============================================
// CONNECTIONS MODULE
// Functions are wired to ConnectionsModule instance.
// See: frontend/js/components/ConnectionsModule.js
// ============================================

// NOTE: _connectionsModule is declared near other state vars to avoid TDZ.

function _initConnectionsModule() {
  _connectionsModule = createConnectionsModule({
    getBlocks: () => strategyBlocks,
    getConnections: () => connections,
    addConnection: (c) => { connections.push(c); },
    removeConnection: (id) => {
      const idx = connections.findIndex(conn => conn.id === id);
      if (idx !== -1) connections.splice(idx, 1);
    },
    pushUndo,
    showNotification,
    renderBlocks
  });
}

// Delegate wrappers so existing call sites work unchanged
function initConnectionSystem() { if (_connectionsModule) _connectionsModule.initConnectionSystem(); }
function renderConnections() { if (_connectionsModule) _connectionsModule.renderConnections(); }
function normalizeConnection(c) { return _connectionsModule ? _connectionsModule.normalizeConnection(c) : c; }
function normalizeAllConnections() { if (_connectionsModule) _connectionsModule.normalizeAllConnections(); }
function deleteConnection(id) { if (_connectionsModule) _connectionsModule.deleteConnection(id); }
function disconnectPort(el) { if (_connectionsModule) _connectionsModule.disconnectPort(el); }
function tryAutoSnapConnection(id) { if (_connectionsModule) _connectionsModule.tryAutoSnapConnection(id); }
function createBezierPath(x1, y1, x2, y2, fo) { return _connectionsModule ? _connectionsModule.createBezierPath(x1, y1, x2, y2, fo) : ''; }
function getPreferredStrategyPort(t) { return _connectionsModule ? _connectionsModule.getPreferredStrategyPort(t) : null; }


// ============================================
// SAVE/LOAD MODULE
// See: frontend/js/components/SaveLoadModule.js
// ============================================
function _initSaveLoadModule() {
  _saveLoadModule = createSaveLoadModule({
    getBlocks: () => strategyBlocks,
    getConnections: () => connections,
    setBlocks: (arr) => { strategyBlocks = arr; setSBBlocks(arr); },
    setConnections: (arr) => { connections.length = 0; connections.push(...arr); setSBConnections(connections); },
    getStrategyIdFromURL,
    showNotification,
    renderBlocks,
    renderConnections,
    normalizeAllConnections,
    syncStrategyNameDisplay,
    renderBlockProperties,
    pushUndo: () => pushUndo(),
    createMainStrategyNode,
    getBlockLibrary: () => blockLibrary,
    updateRunButtonsState,
    runCheckSymbolDataForProperties,
    updateBacktestLeverageDisplay,
    updateBacktestPositionSizeInput,
    updateBacktestLeverageRisk,
    setNoTradeDaysInUI,
    getNoTradeDaysFromUI,
    normalizeTimeframeForDropdown,
    getLastAutoSavePayload: () => getSBLastAutoSavePayload() ?? lastAutoSavePayload,
    setLastAutoSavePayload: (v) => { lastAutoSavePayload = v; setSBLastAutoSavePayload(v); },
    getSkipNextAutoSave: () => skipNextAutoSave,
    setSkipNextAutoSave: (v) => { skipNextAutoSave = v; setSBSkipNextAutoSave(v); },
    closeBlockParamsPopup,
    wsValidation,
    getZoom: () => zoom,
    escapeHtml,
    formatDate,
    dispatchBlocksChanged
  });
}
async function saveStrategy() { return _saveLoadModule ? _saveLoadModule.saveStrategy() : Promise.resolve(); }
function buildStrategyPayload() { return _saveLoadModule ? _saveLoadModule.buildStrategyPayload() : {}; }
async function autoSaveStrategy() { return _saveLoadModule ? _saveLoadModule.autoSaveStrategy() : Promise.resolve(); }
function migrateLegacyBlocks(blocks) { return _saveLoadModule ? _saveLoadModule.migrateLegacyBlocks(blocks) : blocks; }
async function loadStrategy(id) { return _saveLoadModule ? _saveLoadModule.loadStrategy(id) : Promise.resolve(); }
async function openVersionsModal() { return _saveLoadModule ? _saveLoadModule.openVersionsModal() : Promise.resolve(); }
function closeVersionsModal() { if (_saveLoadModule) _saveLoadModule.closeVersionsModal(); }
async function revertToVersion(sId, vId) { return _saveLoadModule ? _saveLoadModule.revertToVersion(sId, vId) : Promise.resolve(); }

// ============================================
// VALIDATE MODULE
// See: frontend/js/components/ValidateModule.js
// ============================================
function _initValidateModule() {
  _validateModule = createValidateModule({
    getBlocks: () => strategyBlocks,
    getConnections: () => connections,
    getBlockPorts,
    validateBlockParams,
    updateBlockValidationState,
    getStrategyIdFromURL,
    saveStrategy: () => saveStrategy(),
    showNotification,
    escapeHtml
  });
}
function validateStrategyCompleteness() { return _validateModule ? _validateModule.validateStrategyCompleteness() : { valid: false, errors: [], warnings: [] }; }
async function validateStrategy() { return _validateModule ? _validateModule.validateStrategy() : Promise.resolve(); }
function updateValidationPanel(r) { if (_validateModule) _validateModule.updateValidationPanel(r); }
async function generateCode() { return _validateModule ? _validateModule.generateCode() : Promise.resolve(); }

// ============================================
// UNDO/REDO MODULE
// See: frontend/js/components/UndoRedoModule.js
// ============================================
function _initUndoRedoModule() {
  _undoRedoModule = createUndoRedoModule({
    getBlocks: () => strategyBlocks,
    getConnections: () => connections,
    setBlocks: (arr) => { strategyBlocks = arr; setSBBlocks(arr); },
    setConnections: (arr) => { connections.length = 0; connections.push(...arr); setSBConnections(connections); },
    getSelectedBlockId: () => getSBSelectedBlockId(),
    setSelectedBlockId: (id) => { selectedBlockId = id; setSBSelectedBlockId(id); },
    renderBlocks,
    renderBlockProperties,
    dispatchBlocksChanged,
    validateStrategy: () => validateStrategy(),
    showNotification,
    selectBlock,
    setLastAutoSavePayload: (v) => { lastAutoSavePayload = v; setSBLastAutoSavePayload(v); }
  });
}
function getStateSnapshot() { return _undoRedoModule ? _undoRedoModule.getStateSnapshot() : { blocks: [], connections: [] }; }
function restoreStateSnapshot(s) { if (_undoRedoModule) _undoRedoModule.restoreStateSnapshot(s); }
function pushUndo() { if (_undoRedoModule) _undoRedoModule.pushUndo(); }
function undo() { if (_undoRedoModule) _undoRedoModule.undo(); }
function redo() { if (_undoRedoModule) _undoRedoModule.redo(); }
function updateUndoRedoButtons() { if (_undoRedoModule) _undoRedoModule.updateUndoRedoButtons(); }
function deleteSelected() { if (_undoRedoModule) _undoRedoModule.deleteSelected(); }
function duplicateSelected() { if (_undoRedoModule) _undoRedoModule.duplicateSelected(); }
function alignBlocks(d) { if (_undoRedoModule) _undoRedoModule.alignBlocks(d); }
function autoLayout() { if (_undoRedoModule) _undoRedoModule.autoLayout(); }


// ============================================
// CSP-COMPLIANT EVENT LISTENERS
// Replaces all inline onclick="..." handlers
// ============================================

function initCspCompliantListeners() {
  // Toolbar buttons
  const btnFitToScreen = document.querySelector('.btn-icon[title="Fit to Screen"]');
  if (btnFitToScreen) btnFitToScreen.addEventListener('click', fitToScreen);

  const btnAiBuild = document.getElementById('btnAiBuild');
  if (btnAiBuild) btnAiBuild.addEventListener('click', openAiBuildModal);

  // Zoom controls
  const zoomBtns = document.querySelectorAll('.zoom-btn');
  zoomBtns.forEach(btn => {
    const title = btn.getAttribute('title') || btn.getAttribute('aria-label') || '';
    if (title.includes('Zoom out')) btn.addEventListener('click', zoomOut);
    else if (title.includes('Zoom in')) btn.addEventListener('click', zoomIn);
    else if (title.includes('Reset zoom')) btn.addEventListener('click', resetZoom);
  });

  // Template modal — Export/Import buttons
  const exportBtn = document.querySelector('[title="Save current strategy as JSON file"]');
  if (exportBtn) exportBtn.addEventListener('click', exportAsTemplate);

  const importBtn = document.querySelector('[title="Load strategy from JSON file"]');
  if (importBtn) {
    importBtn.addEventListener('click', () => {
      document.getElementById('importTemplateInput')?.click();
    });
  }

  // Backtest Results Modal — close buttons
  const backtestCloseX = document.getElementById('btnCloseBacktestResults');
  if (backtestCloseX) backtestCloseX.addEventListener('click', closeBacktestResultsModal);

  const backtestCloseBtn = document.getElementById('btnCloseBacktestResults2');
  if (backtestCloseBtn) backtestCloseBtn.addEventListener('click', closeBacktestResultsModal);

  // Export & View Full buttons
  const exportResultsBtn = document.getElementById('btnExportBacktestResults');
  if (exportResultsBtn) exportResultsBtn.addEventListener('click', exportBacktestResults);

  const viewFullBtn = document.getElementById('btnViewFullBacktestResults');
  if (viewFullBtn) viewFullBtn.addEventListener('click', viewFullResults);

  // Results tabs — delegated
  document.querySelectorAll('.results-tab[data-tab]').forEach(tab => {
    tab.addEventListener('click', () => {
      switchResultsTab(tab.dataset.tab);
    });
  });

  // AI Build Modal buttons
  const aiBuildCloseBtn = document.getElementById('btnCloseAiBuild');
  if (aiBuildCloseBtn) aiBuildCloseBtn.addEventListener('click', closeAiBuildModal);

  const aiRunBtn = document.getElementById('btnRunAiBuild');
  if (aiRunBtn) aiRunBtn.addEventListener('click', runAiBuild);

  const aiResetBtn = document.getElementById('btnResetAiBuild');
  if (aiResetBtn) aiResetBtn.addEventListener('click', resetAiBuild);

  const aiPresetSelect = document.getElementById('aiPreset');
  if (aiPresetSelect) aiPresetSelect.addEventListener('change', applyAiPreset);

  // My Strategies Modal buttons
  const myStrategiesBtn = document.getElementById('btnMyStrategies');
  if (myStrategiesBtn) myStrategiesBtn.addEventListener('click', () => {
    openMyStrategiesModal().catch((err) => {
      console.error('[Strategy Builder] openMyStrategiesModal error:', err);
      showNotification(`Ошибка открытия стратегий: ${err.message}`, 'error');
    });
  });

  const closeMyStrategiesBtn = document.getElementById('btnCloseMyStrategies');
  if (closeMyStrategiesBtn) closeMyStrategiesBtn.addEventListener('click', closeMyStrategiesModal);

  const closeMyStrategiesBtn2 = document.getElementById('btnCloseMyStrategies2');
  if (closeMyStrategiesBtn2) closeMyStrategiesBtn2.addEventListener('click', closeMyStrategiesModal);

  const newStrategyBtn = document.getElementById('btnNewStrategy');
  if (newStrategyBtn) newStrategyBtn.addEventListener('click', () => {
    closeMyStrategiesModal();
    clearAllAndReset();
  });

  const strategiesSearch = document.getElementById('strategiesSearch');
  if (strategiesSearch) strategiesSearch.addEventListener('input', filterStrategiesList);

  // Select All checkbox
  const selectAllCb = document.getElementById('strategiesSelectAll');
  if (selectAllCb) selectAllCb.addEventListener('change', toggleSelectAll);

  // Batch Delete button
  const batchDeleteBtn = document.getElementById('btnBatchDelete');
  if (batchDeleteBtn) batchDeleteBtn.addEventListener('click', batchDeleteSelected);

  // Close My Strategies modal on overlay click
  const myStrategiesModal = document.getElementById('myStrategiesModal');
  if (myStrategiesModal) {
    myStrategiesModal.addEventListener('click', (e) => {
      if (e.target === myStrategiesModal) closeMyStrategiesModal();
    });
  }

  console.log('[Strategy Builder] CSP-compliant event listeners initialized');
}
// ============================================
// EXPORTS - Make functions available globally
// ============================================

// Strategy CRUD functions
window.saveStrategy = saveStrategy;
window.loadStrategy = loadStrategy;
window.runBacktest = runBacktest;
window.getStrategyIdFromURL = getStrategyIdFromURL;
window.updateLastSaved = updateLastSaved;
window.showNotification = showNotification;

// Block functions
window.addBlockToCanvas = addBlockToCanvas;
window.selectBlock = selectBlock;
window.startDragBlock = startDragBlock;
window.showBlockMenu = showBlockMenu;
window.updateBlockParam = updateBlockParam;
window.renderBlockProperties = renderBlockProperties;
window.renderBlocks = renderBlocks;
window.onBlockDragStart = onBlockDragStart;
window.onCanvasDrop = onCanvasDrop;
window.showBlockParamsPopup = showBlockParamsPopup;
window.closeBlockParamsPopup = closeBlockParamsPopup;
window.updateBlockParamFromPopup = updateBlockParamFromPopup;
window.duplicateBlock = duplicateBlock;
window.deleteBlock = deleteBlock;
window.resetBlockToDefaults = resetBlockToDefaults;
window.renderBlockLibrary = renderBlockLibrary;

// Block validation functions
window.validateBlockParams = validateBlockParams;
window.validateParamInput = validateParamInput;
window.updateBlockValidationState = updateBlockValidationState;
window.blockValidationRules = blockValidationRules;

// Connection functions
window.renderConnections = renderConnections;
window.deleteConnection = deleteConnection;
window.normalizeConnection = normalizeConnection;
window.normalizeAllConnections = normalizeAllConnections;
window.disconnectPort = disconnectPort;
window.tryAutoSnapConnection = tryAutoSnapConnection;
window.createBezierPath = createBezierPath;
window.getPreferredStrategyPort = getPreferredStrategyPort;

// Canvas functions
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;
window.fitToScreen = fitToScreen;
window.undo = undo;
window.redo = redo;
window.exportAsTemplate = exportAsTemplate;
window.importTemplateFromFile = importTemplateFromFile;
window.revertToVersion = revertToVersion;
window.deleteSelected = deleteSelected;
window.getStateSnapshot = getStateSnapshot;
window.restoreStateSnapshot = restoreStateSnapshot;
window.buildStrategyPayload = buildStrategyPayload;
window.migrateLegacyBlocks = migrateLegacyBlocks;
window.updateValidationPanel = updateValidationPanel;

// Expose strategyBlocks as a live getter so optimization_panels.js polling works.
// Returns the current blocks array from StateManager (or module-level fallback).
Object.defineProperty(window, 'strategyBlocks', {
  get: () => getSBBlocks(),
  configurable: true,
  enumerable: false
});

// LocalStorage persistence functions
window.tryLoadFromLocalStorage = tryLoadFromLocalStorage;
window.clearLocalStorageDraft = clearLocalStorageDraft;
window.clearAllAndReset = clearAllAndReset;
window.resetFormToDefaults = resetFormToDefaults;

// Backtest Results Display functions
window.displayBacktestResults = displayBacktestResults;
window.closeBacktestResultsModal = closeBacktestResultsModal;
window.switchResultsTab = switchResultsTab;
window.exportBacktestResults = exportBacktestResults;
window.viewFullResults = viewFullResults;

// AI Build functions
window.openAiBuildModal = openAiBuildModal;
window.closeAiBuildModal = closeAiBuildModal;
window.applyAiPreset = applyAiPreset;
window.resetAiBuild = resetAiBuild;
window.runAiBuild = runAiBuild;
window.showAiBuildResults = showAiBuildResults;
window.toggleAgentMonitor = toggleAgentMonitor;
window.viewAiBacktestFullResults = viewAiBacktestFullResults;

// My Strategies functions
window.openMyStrategiesModal = openMyStrategiesModal;
window.closeMyStrategiesModal = closeMyStrategiesModal;
window.fetchStrategiesList = fetchStrategiesList;
window.deleteStrategyById = deleteStrategyById;
window.cloneStrategy = cloneStrategy;
window.batchDeleteSelected = batchDeleteSelected;
window.toggleSelectAll = toggleSelectAll;

// ============================================
// WEBSOCKET VALIDATION INTEGRATION
// ============================================

/**
 * Initialize WebSocket validation event listeners
 */
function initWsValidationListeners() {
  // Listen for validation results from WebSocket
  window.addEventListener('ws-validation-result', (event) => {
    const { type, block_id, param_name, valid, messages } = event.detail;

    if (type === 'validate_param' && block_id) {
      // Update specific parameter validation state
      const inputEl = document.querySelector(
        `[data-block-id="${block_id}"][data-param-key="${param_name}"]`
      );
      if (inputEl) {
        inputEl.classList.toggle('is-invalid', !valid);
        inputEl.classList.toggle('is-valid', valid);
      }
    } else if (type === 'validate_block' && block_id) {
      // Update block validation state
      const errors = messages?.filter(m => m.severity === 'error').map(m => m.message) || [];
      updateBlockValidationState(block_id, { valid, errors });
    }
  });

  // Listen for connection status changes
  window.addEventListener('ws-validation-connected', () => {
    console.log('[Strategy Builder] WebSocket validation connected');
    updateWsStatusIndicator(true);
  });

  window.addEventListener('ws-validation-disconnected', () => {
    console.log('[Strategy Builder] WebSocket validation disconnected');
    updateWsStatusIndicator(false);
  });
}

/**
 * Update WebSocket status indicator in UI
 */
function updateWsStatusIndicator(connected) {
  let statusEl = document.getElementById('ws-validation-status');

  // Create indicator if it doesn't exist
  if (!statusEl) {
    const toolbar = document.querySelector('.canvas-toolbar') || document.querySelector('.toolbar');
    if (toolbar) {
      statusEl = document.createElement('span');
      statusEl.id = 'ws-validation-status';
      statusEl.className = 'ws-status-indicator ms-2';
      statusEl.innerHTML = '<i class="bi bi-broadcast"></i>';
      toolbar.appendChild(statusEl);
    }
  }

  if (statusEl) {
    statusEl.classList.toggle('connected', connected);
    statusEl.classList.toggle('disconnected', !connected);
    statusEl.title = connected
      ? 'Real-time validation: Active'
      : 'Real-time validation: Disconnected (using local validation)';
    statusEl.innerHTML = connected
      ? '<i class="bi bi-broadcast"></i>'
      : '<i class="bi bi-broadcast-pin"></i>';
  }
}

// Initialize WS listeners and CSP-compliant event listeners when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initWsValidationListeners();
    initCspCompliantListeners();
  });
} else {
  initWsValidationListeners();
  initCspCompliantListeners();
}

// Export WS functions
window.wsValidation = wsValidation;
window.initWsValidationListeners = initWsValidationListeners;
window.updateWsStatusIndicator = updateWsStatusIndicator;

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
  window.strategybuilderPage = {
    // Add public methods here
    wsValidation: wsValidation
  };
}

// Export for frontend tests (ticker sync flow) — proxied through SymbolSyncModule
export function syncSymbolData(force) { return symbolSync?.syncSymbolData(force); }
export function runCheckSymbolDataForProperties(force) { return symbolSync?.runCheckSymbolDataForProperties(force); }

// ── Reset End Date button ─────────────────────────────────────────────────────
// Sets backtestEndDate to today on click.
document.addEventListener('DOMContentLoaded', () => {
  const resetBtn = document.getElementById('resetEndDateBtn');
  const endDateEl = document.getElementById('backtestEndDate');
  if (resetBtn && endDateEl) {
    // Compute today string (local time, not UTC — avoids off-by-one in UTC+N zones)
    const _getToday = () => {
      const d = new Date();
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };
    resetBtn.title = 'Reset to today';
    resetBtn.addEventListener('click', () => {
      endDateEl.value = _getToday();
      endDateEl.max = _getToday();
      endDateEl.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }
});
