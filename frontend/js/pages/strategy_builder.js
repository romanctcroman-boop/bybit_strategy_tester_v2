/**
 * 📄 Strategy Builder Page JavaScript
 *
 * Page-specific scripts for strategy_builder.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/* eslint-disable indent */

// Import shared utilities
import { formatCurrency, formatDate, debounce } from '../utils.js';
import { updateLeverageRiskForElements } from '../shared/leverageManager.js';

// Import WebSocket validation module
import * as wsValidation from './strategy_builder_ws.js';

// API Base URL - must be defined early before any usage
const API_BASE = '/api/v1';

// Forward declaration for checkSymbolDataForProperties (initialized later after runCheckSymbolDataForProperties is defined)
let checkSymbolDataForProperties = null;

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

// Block Library Data
const blockLibrary = {
  indicators: [
    // Universal indicator blocks (integrated with AI agents — do not remove)
    { id: 'rsi', name: 'RSI', desc: 'Relative Strength Index (0-100)', icon: 'graph-up' },
    { id: 'stochastic', name: 'Stochastic', desc: 'Stochastic (Range Filter + Cross Signal + K/D Cross)', icon: 'percent' },
    { id: 'macd', name: 'MACD', desc: 'Moving Average Convergence Divergence', icon: 'bar-chart' },
    { id: 'supertrend', name: 'Supertrend', desc: 'Trend following indicator', icon: 'arrow-up-right-circle' },
    { id: 'qqe', name: 'QQE', desc: 'Quantitative Qualitative Estimation', icon: 'activity' },
    // Universal filters (integrated with AI agents — do not remove)
    { id: 'atr_volatility', name: 'ATR Volatility', desc: 'ATR Volatility Filter (ATR1 <> ATR2)', icon: 'arrows-expand' },
    { id: 'volume_filter', name: 'Volume Filter', desc: 'Volume Filter (VOL1 <> VOL2)', icon: 'bar-chart-steps' },
    { id: 'highest_lowest_bar', name: 'Highest/Lowest Bar', desc: 'Signal on Highest/Lowest Bar + Block if Worse Than', icon: 'arrow-up-short' },
    { id: 'two_mas', name: 'TWO MAs', desc: 'Two Moving Averages (Signal + Filter)', icon: 'graph-up-arrow' },
    { id: 'accumulation_areas', name: 'Accumulation Areas', desc: 'Accumulation Areas Filter or Signal', icon: 'layers' },
    { id: 'keltner_bollinger', name: 'Keltner/Bollinger Channel', desc: 'Keltner Channel / Bollinger Bands Filter', icon: 'border-outer' },
    { id: 'rvi_filter', name: 'RVI', desc: 'Relative Volatility Index Filter', icon: 'speedometer' },
    { id: 'mfi_filter', name: 'MFI', desc: 'Money Flow Index Filter', icon: 'currency-exchange' },
    { id: 'cci_filter', name: 'CCI', desc: 'Commodity Channel Index Filter', icon: 'reception-4' },
    { id: 'momentum_filter', name: 'Momentum', desc: 'Momentum Filter', icon: 'rocket-takeoff' }
  ],
  // (Filters category removed — entire block deprecated)
  conditions: [
    {
      id: 'crossover',
      name: 'Crossover',
      desc: 'When value A crosses above B',
      icon: 'intersect'
    },
    {
      id: 'crossunder',
      name: 'Crossunder',
      desc: 'When value A crosses below B',
      icon: 'intersect'
    },
    {
      id: 'greater_than',
      name: 'Greater Than',
      desc: 'When value A > B',
      icon: 'chevron-double-up'
    },
    {
      id: 'less_than',
      name: 'Less Than',
      desc: 'When value A < B',
      icon: 'chevron-double-down'
    },
    {
      id: 'equals',
      name: 'Equals',
      desc: 'When value A equals B',
      icon: 'dash'
    },
    {
      id: 'between',
      name: 'Between',
      desc: 'When value is in range',
      icon: 'arrows-collapse'
    }
  ],
  entry_mgmt: [
    {
      id: 'dca',
      name: 'DCA',
      desc: 'Dollar Cost Averaging',
      icon: 'grid-3x3'
    },
    {
      id: 'grid_orders',
      name: 'Manual Grid',
      desc: 'Custom offset & volume per order',
      icon: 'grid'
    }
  ],
  // Exits: Standard exit rules (SL/TP, trailing, ATR, session, DCA close)
  exits: [
    {
      id: 'static_sltp',
      name: 'Static SL/TP',
      desc: 'Auto % SL/TP from entry price',
      icon: 'shield-check'
    },
    {
      id: 'trailing_stop_exit',
      name: 'Trailing Stop',
      desc: 'Auto trailing % from entry',
      icon: 'arrow-bar-down'
    },
    {
      id: 'atr_exit',
      name: 'ATR Exit',
      desc: 'Auto ATR-based SL/TP',
      icon: 'arrows-expand'
    },
    {
      id: 'multi_tp_exit',
      name: 'Multi TP Levels',
      desc: 'TP1/TP2/TP3 with % allocation',
      icon: 'stack'
    }
  ],
  // Close Conditions: Indicator-based close rules with profit filter (TradingView-style)
  close_conditions: [
    {
      id: 'close_by_time',
      name: 'Close by Time',
      desc: 'Close after N bars since entry',
      icon: 'clock'
    },
    {
      id: 'close_channel',
      name: 'Channel Close (Keltner/BB)',
      desc: 'Close on Keltner/Bollinger band touch',
      icon: 'bar-chart'
    },
    {
      id: 'close_ma_cross',
      name: 'Two MAs Close',
      desc: 'Close on MA1/MA2 cross',
      icon: 'trending-up'
    },
    {
      id: 'close_rsi',
      name: 'Close by RSI',
      desc: 'Close on RSI reach/cross level',
      icon: 'activity'
    },
    {
      id: 'close_stochastic',
      name: 'Close by Stochastic',
      desc: 'Close on Stoch reach/cross level',
      icon: 'activity'
    },
    {
      id: 'close_psar',
      name: 'Close by Parabolic SAR',
      desc: 'Close on PSAR signal reversal',
      icon: 'git-commit'
    }
  ],
  // Divergence Detection — unified multi-indicator divergence signal block
  divergence: [
    {
      id: 'divergence',
      name: 'Divergence',
      desc: 'Multi-indicator divergence detection (RSI, Stochastic, Momentum, CMF, OBV, MFI)',
      icon: 'arrow-left-right'
    }
  ],
  // Logic Gates — combine multiple condition signals
  logic: [
    {
      id: 'and',
      name: 'AND',
      desc: 'All inputs must be true (combine signals)',
      icon: 'diagram-3'
    },
    {
      id: 'or',
      name: 'OR',
      desc: 'Any input must be true (alternative signals)',
      icon: 'diagram-2'
    },
    {
      id: 'not',
      name: 'NOT',
      desc: 'Invert signal (true → false)',
      icon: 'x-circle'
    }
  ]

  // (Smart Signals category removed — all composite nodes deprecated in favor of universal indicator blocks)
};

// Strategy Templates - EXPANDED
const templates = [
  // =============================================
  // MEAN REVERSION STRATEGIES
  // =============================================
  {
    id: 'rsi_oversold',
    name: 'RSI Cross Level',
    desc: 'Long when RSI crosses up through 30, short when crosses down through 70',
    icon: 'graph-up',
    iconColor: 'var(--accent-blue)',
    blocks: 2,
    connections: 4,
    category: 'Mean Reversion',
    difficulty: 'Beginner',
    expectedWinRate: '45-55%'
  },
  {
    id: 'rsi_long_short',
    name: 'RSI Range Filter',
    desc: 'Long when RSI in low range (1-30), Short when RSI in high range (70-100)',
    icon: 'arrow-up-down',
    iconColor: 'var(--accent-green)',
    blocks: 2,
    connections: 4,
    category: 'Mean Reversion',
    difficulty: 'Beginner',
    expectedWinRate: '40-50%'
  },
  {
    id: 'bollinger_bounce',
    name: 'Bollinger Bounce',
    desc: 'Trade bounces off Bollinger Band boundaries',
    icon: 'distribute-vertical',
    iconColor: 'var(--accent-yellow)',
    blocks: 5,
    connections: 8,
    category: 'Mean Reversion',
    difficulty: 'Intermediate',
    expectedWinRate: '50-60%'
  },
  {
    id: 'stochastic_oversold',
    name: 'Stochastic Reversal',
    desc: 'Trade oversold/overbought with K/D crossover confirmation',
    icon: 'percent',
    iconColor: 'var(--accent-cyan)',
    blocks: 10,
    connections: 16,
    category: 'Mean Reversion',
    difficulty: 'Intermediate',
    expectedWinRate: '45-55%'
  },

  // =============================================
  // TREND FOLLOWING STRATEGIES
  // =============================================
  {
    id: 'macd_crossover',
    name: 'MACD Crossover',
    desc: 'Trade MACD line crossovers with signal line',
    icon: 'bar-chart',
    iconColor: 'var(--accent-purple)',
    blocks: 4,
    connections: 8,
    category: 'Trend Following',
    difficulty: 'Beginner',
    expectedWinRate: '40-50%'
  },
  {
    id: 'ema_crossover',
    name: 'EMA Crossover',
    desc: 'Classic dual EMA crossover strategy',
    icon: 'graph-up-arrow',
    iconColor: 'var(--accent-green)',
    blocks: 5,
    connections: 8,
    category: 'Trend Following',
    difficulty: 'Beginner',
    expectedWinRate: '35-45%'
  },
  {
    id: 'supertrend_follow',
    name: 'SuperTrend Follower',
    desc: 'Follow SuperTrend direction with ATR-based stops',
    icon: 'arrow-up-right-circle',
    iconColor: 'var(--accent-teal)',
    blocks: 5,
    connections: 8,
    category: 'Trend Following',
    difficulty: 'Beginner',
    expectedWinRate: '40-50%'
  },
  {
    id: 'triple_ema',
    name: 'Triple EMA System',
    desc: 'EMA 9/21/55 with trend confirmation',
    icon: 'layers',
    iconColor: 'var(--accent-indigo)',
    blocks: 10,
    connections: 16,
    category: 'Trend Following',
    difficulty: 'Intermediate',
    expectedWinRate: '45-55%'
  },
  {
    id: 'ichimoku_cloud',
    name: 'Ichimoku Cloud Strategy',
    desc: 'Trade with Ichimoku cloud, TK cross and Chikou confirmation',
    icon: 'cloud',
    iconColor: 'var(--accent-pink)',
    blocks: 9,
    connections: 16,
    category: 'Trend Following',
    difficulty: 'Advanced',
    expectedWinRate: '50-60%'
  },

  // =============================================
  // MOMENTUM STRATEGIES
  // =============================================
  {
    id: 'breakout',
    name: 'Breakout Strategy',
    desc: 'Trade breakouts from consolidation ranges',
    icon: 'arrows-expand',
    iconColor: 'var(--accent-orange)',
    blocks: 5,
    connections: 8,
    category: 'Momentum',
    difficulty: 'Intermediate',
    expectedWinRate: '35-45%'
  },
  {
    id: 'donchian_breakout',
    name: 'Donchian Channel Breakout',
    desc: 'Classic turtle trading - buy 20-day high, sell 10-day low',
    icon: 'box-arrow-up',
    iconColor: 'var(--accent-amber)',
    blocks: 8,
    connections: 12,
    category: 'Momentum',
    difficulty: 'Intermediate',
    expectedWinRate: '35-45%'
  },
  {
    id: 'volume_breakout',
    name: 'Volume Breakout',
    desc: 'Enter on price breakout with volume confirmation',
    icon: 'bar-chart-steps',
    iconColor: 'var(--accent-lime)',
    blocks: 11,
    connections: 16,
    category: 'Momentum',
    difficulty: 'Intermediate',
    expectedWinRate: '40-50%'
  },

  // =============================================
  // DCA & GRID STRATEGIES
  // =============================================
  {
    id: 'simple_dca',
    name: 'Simple DCA Bot',
    desc: 'Dollar cost averaging with safety orders on price drops',
    icon: 'grid-3x3',
    iconColor: 'var(--accent-blue)',
    blocks: 6,
    connections: 8,
    category: 'DCA',
    difficulty: 'Intermediate',
    expectedWinRate: '65-75%'
  },
  {
    id: 'rsi_dca',
    name: 'RSI DCA Strategy',
    desc: 'DCA entries only when RSI is oversold',
    icon: 'plus-circle',
    iconColor: 'var(--accent-green)',
    blocks: 9,
    connections: 12,
    category: 'DCA',
    difficulty: 'Intermediate',
    expectedWinRate: '60-70%'
  },
  {
    id: 'grid_trading',
    name: 'Grid Trading Bot',
    desc: 'Place grid of orders within price range',
    icon: 'grid',
    iconColor: 'var(--accent-purple)',
    blocks: 7,
    connections: 12,
    category: 'Grid',
    difficulty: 'Advanced',
    expectedWinRate: '55-65%'
  },

  // =============================================
  // ADVANCED / MULTI-INDICATOR
  // =============================================
  {
    id: 'multi_indicator',
    name: 'Multi-Indicator Confluence',
    desc: 'Combine multiple indicators for confirmation',
    icon: 'layers',
    iconColor: 'var(--accent-red)',
    blocks: 17,
    connections: 24,
    category: 'Advanced',
    difficulty: 'Advanced',
    expectedWinRate: '50-60%'
  },
  {
    id: 'divergence_hunter',
    name: 'Divergence Hunter',
    desc: 'Find RSI/MACD divergences with price',
    icon: 'arrow-left-right',
    iconColor: 'var(--accent-violet)',
    blocks: 12,
    connections: 16,
    category: 'Advanced',
    difficulty: 'Advanced',
    expectedWinRate: '55-65%'
  },
  {
    id: 'smart_money',
    name: 'Smart Money Concept',
    desc: 'Trade order blocks, FVG and liquidity sweeps',
    icon: 'bank',
    iconColor: 'var(--accent-gold)',
    blocks: 18,
    connections: 24,
    category: 'Advanced',
    difficulty: 'Expert',
    expectedWinRate: '50-60%'
  },
  {
    id: 'scalping_pro',
    name: 'Scalping Pro',
    desc: 'Quick entries with tight stops on small timeframes',
    icon: 'lightning',
    iconColor: 'var(--accent-yellow)',
    blocks: 17,
    connections: 24,
    category: 'Scalping',
    difficulty: 'Expert',
    expectedWinRate: '55-65%'
  },

  // =============================================
  // VOLATILITY STRATEGIES
  // =============================================
  {
    id: 'atr_breakout',
    name: 'ATR Volatility Breakout',
    desc: 'Enter when volatility expands beyond threshold',
    icon: 'arrows-fullscreen',
    iconColor: 'var(--accent-orange)',
    blocks: 10,
    connections: 14,
    category: 'Volatility',
    difficulty: 'Intermediate',
    expectedWinRate: '40-50%'
  },
  {
    id: 'bb_squeeze',
    name: 'Bollinger Squeeze',
    desc: 'Trade breakout after BB width contraction',
    icon: 'arrows-collapse',
    iconColor: 'var(--accent-cyan)',
    blocks: 9,
    connections: 14,
    category: 'Volatility',
    difficulty: 'Intermediate',
    expectedWinRate: '45-55%'
  }
];

// State
let strategyBlocks = [];
const connections = [];
const undoStack = [];
const redoStack = [];
const MAX_UNDO_HISTORY = 50;
let lastAutoSavePayload = null;
let _eventListenersInitialized = false; // Must be declared before initializeStrategyBuilder() call
const AUTOSAVE_INTERVAL_MS = 30000;
const STORAGE_KEY_PREFIX = 'strategy_builder_draft_';
let skipNextAutoSave = false; // Flag to skip autosave after reset
let selectedBlockId = null;
let selectedBlockIds = []; // Multi-selection array
let selectedTemplate = null;
let zoom = 1;
let isDragging = false;
let dragOffset = { x: 0, y: 0 };

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
            id: conn.id || `conn_restored_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            source: conn.source,
            target: conn.target,
            type: conn.type || 'data'
          });
        }
      });
      // Normalize to ensure canonical format (fills missing id/type/portId)
      normalizeAllConnections();
    }

    // Restore UI state if available
    if (data.uiState) {
      // Restore zoom
      if (data.uiState.zoom && typeof data.uiState.zoom === 'number') {
        zoom = data.uiState.zoom;
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

    // Clear last autosave payload to prevent immediate re-save
    lastAutoSavePayload = null;

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

    // Clear all connections
    connections.length = 0;

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
  if (positionSizeEl) positionSizeEl.value = '100';

  // Commission
  const commissionEl = document.getElementById('backtestCommission');
  if (commissionEl) commissionEl.value = '0.07';

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
    // Bug #3 fix: default to today, not a far-future date like 2030-01-01
    const today = new Date();
    endDateEl.value = today.toISOString().split('T')[0];
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

/** Global refresh for "База данных" panel (set by initDunnahBasePanel, used after sync). */
let refreshDunnahBasePanel = null;

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

    console.log('[Strategy Builder] Rendering templates...');
    renderTemplates();

    console.log('[Strategy Builder] Setting up event listeners...');
    setupEventListeners();
    syncStrategyNameDisplay();
    initSymbolPicker();
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
      <div class="category-group-header" style="--group-color: ${group.groupColor}">
        <i class="bi bi-chevron-right group-chevron"></i>
        <i class="bi bi-${group.groupIcon}" style="color: ${group.groupColor}"></i>
        <span class="group-name">${group.groupName}</span>
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
          <span class="category-title">${cat.name}</span>
        </div>
        <div class="block-list">
          ${blocks
          .map(
            (block) => `
              <div class="block-item" 
                   draggable="true" 
                   data-block-id="${block.id}"
                   data-block-type="${blockCategory}">
                <div class="block-icon ${cat.iconType}">
                  <i class="bi bi-${block.icon}"></i>
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

function renderTemplates() {
  console.log('[Strategy Builder] Rendering templates, count:', templates.length);
  const container = document.getElementById('templatesGrid');
  if (!container) {
    console.error('[Strategy Builder] Templates grid container not found!');
    return;
  }

  if (templates.length === 0) {
    console.warn('[Strategy Builder] No templates available!');
    container.innerHTML = '<div class="text-center py-4"><p class="text-secondary">No templates available</p></div>';
    return;
  }

  container.innerHTML = templates
    .map(
      (template) => `
                <div class="template-card ${selectedTemplate === template.id ? 'selected' : ''}" 
                     data-template-id="${template.id}">
                    <div class="template-icon" style="background: ${template.iconColor}15; color: ${template.iconColor}">
                        <i class="bi bi-${template.icon}"></i>
                    </div>
                    <div class="template-name">${template.name}</div>
                    <div class="template-desc">${template.desc}</div>
                    <div class="template-meta">
                        <span><i class="bi bi-box"></i> ${template.blocks} blocks</span>
                        <span><i class="bi bi-link"></i> ${template.connections} connections</span>
                        <span><i class="bi bi-tag"></i> ${template.category}</span>
                    </div>
                </div>
            `
    )
    .join('');

  console.log(
    '[Strategy Builder] Templates rendered, HTML length:',
    container.innerHTML.length,
    'Templates in DOM:',
    container.querySelectorAll('.template-card').length
  );
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

/** Кэш тикеров Bybit по категории (linear/spot). */
const bybitSymbolsCache = { linear: [], spot: [] };

/** Кэш символов с локальными данными в БД. */
let localSymbolsCache = null;

/** Кэш тикеров с ценами и объёмами по категории. */
const tickersDataCache = {};

/** Список заблокированных тикеров (единый источник для База данных и Symbol picker). */
let blockedSymbolsCache = null;

/** Текущая сортировка для symbol picker. */
const symbolSortConfig = { field: 'name', direction: 'asc' };

/** Загрузить список заблокированных тикеров (единый источник). */
async function fetchBlockedSymbols() {
  try {
    const res = await fetch('/api/v1/marketdata/symbols/blocked');
    if (!res.ok) return new Set();
    const data = await res.json();
    const list = (data.symbols || []).map((s) => String(s).toUpperCase());
    blockedSymbolsCache = new Set(list);
    return blockedSymbolsCache;
  } catch (e) {
    console.error('[Strategy Builder] fetchBlockedSymbols failed:', e);
    return blockedSymbolsCache || new Set();
  }
}

/** Загрузить тикеры с ценами, 24h%, объёмом. */
async function fetchTickersData(category = 'linear') {
  const key = category === 'spot' ? 'spot' : 'linear';
  if (tickersDataCache[key] && Object.keys(tickersDataCache[key]).length > 0) {
    return tickersDataCache[key];
  }
  try {
    const res = await fetch(`/api/v1/marketdata/tickers?category=${encodeURIComponent(key)}`);
    if (!res.ok) {
      console.error('[Strategy Builder] fetchTickersData not ok:', res.statusText);
      return {};
    }
    const data = await res.json();
    const map = {};
    (data.tickers || []).forEach((t) => {
      map[t.symbol] = t;
    });
    if (Object.keys(map).length > 0) tickersDataCache[key] = map;
    console.log('[Strategy Builder] Tickers data loaded:', key, Object.keys(map).length);
    return map;
  } catch (e) {
    console.error('[Strategy Builder] fetchTickersData failed:', e);
    return {};
  }
}

/** Загрузить список символов с локальными данными.
 *  @param {boolean} [force=false] — принудительно обновить с сервера, игнорируя кэш.
 */
async function fetchLocalSymbols(force = false) {
  // Return cached data if already loaded successfully and not forced
  // Note: cache empty results too (symbols: []) to avoid unnecessary API calls after all tickers are deleted
  if (!force && localSymbolsCache !== null && localSymbolsCache.symbols) {
    return localSymbolsCache;
  }
  try {
    const base = typeof window !== 'undefined' && window.location && window.location.origin
      ? window.location.origin
      : '';
    const url = `${base}/api/v1/marketdata/symbols/local?_=${Date.now()}`;
    const res = await fetch(url, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' }
    });
    if (!res.ok) {
      console.error('[Strategy Builder] fetchLocalSymbols not ok:', res.statusText);
      // Don't cache error - allow retry
      return { symbols: [], details: {} };
    }
    const data = await res.json();
    localSymbolsCache = data;
    console.log('[Strategy Builder] Local symbols loaded:', data.symbols?.length || 0, data.symbols);
    return localSymbolsCache;
  } catch (e) {
    console.error('[Strategy Builder] fetchLocalSymbols failed:', e);
    // Don't cache error - allow retry
    return { symbols: [], details: {} };
  }
}

/** Загрузить список тикеров Bybit по типу рынка. */
async function fetchBybitSymbols(category) {
  const key = category === 'spot' ? 'spot' : 'linear';
  console.log('[Strategy Builder] fetchBybitSymbols called, category:', key);
  if (bybitSymbolsCache[key] && bybitSymbolsCache[key].length > 0) {
    console.log('[Strategy Builder] Returning from cache:', bybitSymbolsCache[key].length, 'symbols');
    return bybitSymbolsCache[key];
  }
  try {
    const base = typeof window !== 'undefined' && window.location && window.location.origin
      ? window.location.origin
      : '';
    const url = `${base}/api/v1/marketdata/symbols-list?category=${key}`;
    console.log('[Strategy Builder] Fetching symbols from:', url);
    const res = await fetch(url);
    console.log('[Strategy Builder] Fetch response status:', res.status);
    if (!res.ok) {
      console.error('[Strategy Builder] Fetch not ok:', res.statusText);
      return [];
    }
    const data = await res.json();
    const list = data.symbols || [];
    console.log('[Strategy Builder] Received symbols:', list.length, 'first 5:', list.slice(0, 5));
    // DEBUG: Show alert with count
    // alert(`Loaded ${list.length} symbols for ${key}`);
    bybitSymbolsCache[key] = Array.isArray(list) ? list : [];
    return bybitSymbolsCache[key];
  } catch (e) {
    console.error('[Strategy Builder] fetchBybitSymbols failed:', e);
    return [];
  }
}

/** Позиционировать выпадающий список по полю ввода (fixed), чтобы не обрезался sidebar overflow. */
function positionSymbolDropdown() {
  const input = document.getElementById('backtestSymbol');
  const dropdown = document.getElementById('backtestSymbolDropdown');
  if (!input || !dropdown || !dropdown.classList.contains('open')) return;

  // Move dropdown to body to avoid overflow clipping issues
  if (dropdown.parentElement !== document.body) {
    document.body.appendChild(dropdown);
  }

  const rect = input.getBoundingClientRect();
  const maxH = Math.min(400, window.innerHeight - rect.bottom - 24);

  // Calculate optimal width and position
  const dropdownWidth = 520; // Fixed width for table columns
  let leftPos = rect.left;

  // Prevent dropdown from going off-screen to the right
  if (leftPos + dropdownWidth > window.innerWidth - 20) {
    leftPos = window.innerWidth - dropdownWidth - 20;
  }
  // Prevent going off-screen to the left
  if (leftPos < 10) {
    leftPos = 10;
  }

  dropdown.style.position = 'fixed';
  dropdown.style.left = `${leftPos}px`;
  dropdown.style.top = `${rect.bottom + 4}px`;
  dropdown.style.width = `${dropdownWidth}px`;
  dropdown.style.minWidth = `${dropdownWidth}px`;
  dropdown.style.maxHeight = `${Math.max(200, maxH)}px`;
  dropdown.style.overflowY = 'auto';
  dropdown.style.zIndex = '100000';
  dropdown.style.display = 'block';
  dropdown.style.visibility = 'visible';
  dropdown.style.pointerEvents = 'auto';
  dropdown.style.background = 'var(--bg-tertiary, #1e1e2e)';
  dropdown.style.border = '1px solid var(--border-color, #444)';
  dropdown.style.borderRadius = '6px';
  dropdown.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.5)';

  // Custom scrollbar styles
  dropdown.style.scrollbarWidth = 'thin';
  dropdown.style.scrollbarColor = 'var(--accent-blue, #3b82f6) transparent';
}

/** Показать выпадающий список тикеров с фильтром по поиску и сортировкой. */
function showSymbolDropdown(query, options = {}) {
  const { loading = false, error = null } = options;
  console.log('[Strategy Builder] showSymbolDropdown called:', { query, loading, error });
  const input = document.getElementById('backtestSymbol');
  const dropdown = document.getElementById('backtestSymbolDropdown');
  const marketEl = document.getElementById('builderMarketType');
  if (!input || !dropdown || !marketEl) {
    console.error('[Strategy Builder] showSymbolDropdown: Missing elements');
    return;
  }
  if (error) {
    console.log('[Strategy Builder] showSymbolDropdown: error mode');
    dropdown.innerHTML = '';
    dropdown.classList.remove('open');
    dropdown.setAttribute('aria-hidden', 'true');
    return;
  }
  if (loading) {
    console.log('[Strategy Builder] showSymbolDropdown: loading mode');
    dropdown.innerHTML = '<li class="symbol-picker-item symbol-picker-message">Загрузка тикеров...</li>';
    dropdown.setAttribute('aria-hidden', 'false');
    dropdown.classList.add('open');
    positionSymbolDropdown();
    return;
  }
  const category = marketEl.value === 'spot' ? 'spot' : 'linear';
  const list = bybitSymbolsCache[category] || [];
  const localData = localSymbolsCache || { symbols: [], details: {}, blocked: [] };
  const localSet = new Set(localData.symbols || []);
  const blockedSet = blockedSymbolsCache || new Set((localData.blocked || []).map((s) => String(s).toUpperCase()));
  const tickersData = (tickersDataCache && tickersDataCache[category]) || {};
  console.log('[Strategy Builder] showSymbolDropdown: category =', category, ', cache size =', list.length, ', local symbols =', localSet.size, ', tickers data =', Object.keys(tickersData).length);
  const q = (query || '').toUpperCase().trim();

  // Build enriched list with ticker data
  const enrichedList = list.map((symbol) => {
    const ticker = tickersData[symbol] || {};
    return {
      symbol,
      isLocal: localSet.has(symbol),
      price: ticker.price || 0,
      change_24h: ticker.change_24h || 0,
      volume_24h: ticker.volume_24h || 0
    };
  });

  // Sort by current sort config
  const { field, direction } = symbolSortConfig;
  enrichedList.sort((a, b) => {
    // Local symbols always first
    if (a.isLocal && !b.isLocal) return -1;
    if (!a.isLocal && b.isLocal) return 1;

    let cmp = 0;
    if (field === 'name') {
      cmp = a.symbol.localeCompare(b.symbol);
    } else if (field === 'price') {
      cmp = a.price - b.price;
    } else if (field === 'change') {
      cmp = a.change_24h - b.change_24h;
    } else if (field === 'volume') {
      cmp = a.volume_24h - b.volume_24h;
    }
    return direction === 'desc' ? -cmp : cmp;
  });

  const filtered = q ? enrichedList.filter((item) => item.symbol.toUpperCase().includes(q)) : enrichedList;
  console.log('[Strategy Builder] showSymbolDropdown: filtered size =', filtered.length);

  if (list.length === 0) {
    console.log('[Strategy Builder] showSymbolDropdown: list is empty, hiding dropdown');
    dropdown.innerHTML = '';
    dropdown.classList.remove('open');
    dropdown.setAttribute('aria-hidden', 'true');
    return;
  }

  // Format numbers
  const formatPrice = (p) => (p >= 1 ? p.toFixed(2) : p >= 0.0001 ? p.toFixed(6) : p.toExponential(2));
  const formatChange = (c) => {
    const sign = c >= 0 ? '+' : '';
    const color = c >= 0 ? 'var(--success-green, #4caf50)' : 'var(--error-red, #f44336)';
    return `<span style="color: ${color}">${sign}${Number(c).toFixed(2)}%</span>`;
  };
  const formatVolume = (v) => {
    if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return v.toFixed(0);
  };

  // Sort indicator
  const sortIcon = (fld) => {
    if (symbolSortConfig.field !== fld) return '⇅';
    return symbolSortConfig.direction === 'asc' ? '↑' : '↓';
  };

  // Header with sortable columns
  const headerRow = `
        <li class="symbol-picker-header-row" style="display: grid; grid-template-columns: minmax(180px, 1fr) 90px 75px 80px; gap: 8px; padding: 8px 12px; background: var(--bg-secondary); border-bottom: 2px solid var(--accent-blue); font-size: 12px; color: var(--text-secondary);">
            <span class="symbol-sort-col" data-sort="name" style="cursor: pointer;" title="Сортировать по названию">Символ ${sortIcon('name')}</span>
            <span class="symbol-sort-col" data-sort="price" style="cursor: pointer; text-align: right;" title="Сортировать по цене">Цена ${sortIcon('price')}</span>
            <span class="symbol-sort-col" data-sort="change" style="cursor: pointer; text-align: right;" title="Сортировать по изменению 24h">24H% ${sortIcon('change')}</span>
            <span class="symbol-sort-col" data-sort="volume" style="cursor: pointer; text-align: right;" title="Сортировать по объёму">Объём ${sortIcon('volume')}</span>
        </li>`;

  // Info row
  const infoText = q ? `Найдено: ${filtered.length} из ${list.length}` : `Всего: ${list.length} (📊 = лок. данные)`;
  const infoRow = `<li class="symbol-picker-info" style="font-size: 10px; color: var(--text-muted); padding: 2px 10px; background: var(--bg-tertiary);">${infoText}</li>`;

  // Data rows
  const items = filtered
    .slice(0, 500)
    .map((item) => {
      const details = localData.details?.[item.symbol];
      const intervals = details ? Object.keys(details.intervals || {}).join(', ') : '';
      const isBlocked = blockedSet.has(item.symbol.toUpperCase());
      let badge = item.isLocal ? `<span class="symbol-local-badge" title="Локальные данные: ${intervals}">📊</span>` : '';
      badge += isBlocked
        ? '<span class="symbol-blocked-badge" title="Заблокирован для догрузки">🔒</span>'
        : '<span class="symbol-unblocked-badge" title="Разблокирован">🔓</span>';
      let cls = item.isLocal ? 'symbol-picker-item symbol-has-local' : 'symbol-picker-item';
      if (isBlocked) cls += ' symbol-blocked';
      return `<li class="${cls}" data-symbol="${item.symbol}" tabindex="0" role="option" style="display: grid; grid-template-columns: minmax(180px, 1fr) 90px 75px 80px; gap: 8px; align-items: center; padding: 6px 12px;">
                <span class="symbol-name" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${badge}${item.symbol}</span>
                <span style="text-align: right; font-size: 13px; color: var(--text-primary);">${Number.isFinite(item.price) ? formatPrice(item.price) : '-'}</span>
                <span style="text-align: right; font-size: 13px;">${Number.isFinite(item.change_24h) ? formatChange(item.change_24h) : '-'}</span>
                <span style="text-align: right; font-size: 13px; color: var(--text-primary);">${Number.isFinite(item.volume_24h) ? formatVolume(item.volume_24h) : '-'}</span>
            </li>`;
    })
    .join('');

  dropdown.innerHTML = headerRow + infoRow + (items || '<li class="symbol-picker-item symbol-picker-message">Нет совпадений</li>');
  dropdown.setAttribute('aria-hidden', filtered.length === 0 && !items ? 'true' : 'false');
  dropdown.classList.add('open');

  // Add click handlers for sorting
  dropdown.querySelectorAll('.symbol-sort-col').forEach((col) => {
    col.addEventListener('click', (e) => {
      e.stopPropagation();
      const sortField = col.dataset.sort;
      if (symbolSortConfig.field === sortField) {
        symbolSortConfig.direction = symbolSortConfig.direction === 'asc' ? 'desc' : 'asc';
      } else {
        symbolSortConfig.field = sortField;
        symbolSortConfig.direction = sortField === 'name' ? 'asc' : 'desc'; // Default: name asc, others desc
      }
      showSymbolDropdown(query, options);
    });
  });

  console.log('[Strategy Builder] showSymbolDropdown: dropdown opened with', filtered.length, 'items');
  positionSymbolDropdown();
}

/** Инициализация поля Symbol: тикеры с Bybit + поиск, привязка к типу рынка. */
function initSymbolPicker() {
  console.log('[Strategy Builder] initSymbolPicker called');
  const input = document.getElementById('backtestSymbol');
  const dropdown = document.getElementById('backtestSymbolDropdown');
  const marketEl = document.getElementById('builderMarketType');
  console.log('[Strategy Builder] Symbol picker elements:', { input: !!input, dropdown: !!dropdown, marketEl: !!marketEl });
  if (!input || !dropdown || !marketEl) {
    console.error('[Strategy Builder] initSymbolPicker: Missing elements!');
    return;
  }

  function getCategory() {
    return marketEl.value === 'spot' ? 'spot' : 'linear';
  }

  async function loadAndShow() {
    const cat = getCategory();
    const cachedList = bybitSymbolsCache[cat] || [];
    // If cache is warm, show immediately without loading spinner
    if (cachedList.length > 0 && blockedSymbolsCache !== null) {
      showSymbolDropdown(input.value);
      return;
    }
    showSymbolDropdown(input.value, { loading: true });
    try {
      // Load Bybit symbols, local symbols, and tickers data in parallel
      await Promise.all([
        fetchBybitSymbols(cat),
        fetchLocalSymbols(),
        fetchTickersData(cat),
        fetchBlockedSymbols()
      ]);
      showSymbolDropdown(input.value);
    } catch (e) {
      showSymbolDropdown(input.value, { error: 'Ошибка загрузки тикеров. Проверьте сеть.' });
    }
  }

  // Debounce helper for input filtering (150ms)
  let _symbolInputTimer = null;

  input.addEventListener('focus', function () {
    loadAndShow();
  });
  input.addEventListener('input', function () {
    // Debounce input to avoid excessive re-renders during fast typing
    clearTimeout(_symbolInputTimer);
    _symbolInputTimer = setTimeout(function () {
      const cat = getCategory();
      const list = bybitSymbolsCache[cat] || [];
      if (list.length > 0 && blockedSymbolsCache !== null) showSymbolDropdown(input.value);
      else loadAndShow();
    }, 150);
  });
  input.addEventListener('click', function () {
    const cat = getCategory();
    if ((bybitSymbolsCache[cat] || []).length > 0 && blockedSymbolsCache !== null) {
      showSymbolDropdown(input.value);
    } else {
      loadAndShow();
    }
  });
  input.addEventListener('blur', function (e) {
    const related = e.relatedTarget;
    if (related && dropdown.contains(related)) return;
    setTimeout(function () {
      if (!dropdown.classList.contains('open')) return;
      closeSymbolDropdown();
    }, 200);
  });

  /** Закрыть выпадающий список (скрыть и сбросить позиционирование). */
  function closeSymbolDropdown() {
    const d = document.getElementById('backtestSymbolDropdown');
    if (!d) return;
    d.classList.remove('open');
    d.setAttribute('aria-hidden', 'true');
    d.style.position = '';
    d.style.left = '';
    d.style.top = '';
    d.style.width = '';
    d.style.minWidth = '';
    d.style.maxHeight = '';
    d.style.overflowY = '';
    d.style.zIndex = '';
    d.style.display = 'none';
    d.style.visibility = '';
    d.style.pointerEvents = '';

    // Return dropdown to its original parent if moved to body
    const symbolPicker = document.querySelector('.symbol-picker');
    if (symbolPicker && d.parentElement === document.body) {
      symbolPicker.appendChild(d);
    }
  }

  document.addEventListener('click', function (e) {
    const t = e.target;
    if (input.contains(t) || dropdown.contains(t)) return;
    closeSymbolDropdown();
  });

  function onSymbolSelected(sym) {
    input.value = sym;
    closeSymbolDropdown();
    input.blur();
    console.log(`[SymbolPicker] Selected: ${sym}`);
    document.dispatchEvent(new CustomEvent('properties-symbol-selected'));
    // Отменить отложенный вызов от change/debounce, чтобы не прерывать только что запущенный sync
    if (typeof checkSymbolDataForProperties === 'function' && checkSymbolDataForProperties.cancel) {
      checkSymbolDataForProperties.cancel();
    }
    // При выборе тикера из списка всегда запускаем синхронизацию (игнорируем кэш 10 с)
    runCheckSymbolDataForProperties(true);
  }

  dropdown.addEventListener('mousedown', function (e) {
    e.preventDefault();
    e.stopPropagation();
    const item = e.target.closest('.symbol-picker-item');
    if (item && item.dataset.symbol) onSymbolSelected(item.dataset.symbol);
  });

  dropdown.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    const item = e.target.closest('.symbol-picker-item');
    if (item && item.dataset.symbol) onSymbolSelected(item.dataset.symbol);
  });

  marketEl.addEventListener('change', async function () {
    // Clear cache and preload new symbols for the selected market type
    bybitSymbolsCache.linear = [];
    bybitSymbolsCache.spot = [];
    delete tickersDataCache.linear;
    delete tickersDataCache.spot;
    const cat = getCategory();
    console.log('[Strategy Builder] Market type changed to:', cat, '- preloading symbols');
    try {
      await Promise.all([
        fetchBybitSymbols(cat),
        fetchLocalSymbols(),
        fetchTickersData(cat)
      ]);
      console.log('[Strategy Builder] Symbols preloaded for', cat, ':', bybitSymbolsCache[cat]?.length || 0);
      // Sync current symbol for new market type (spot/linear) — сброс кэша для принудительной загрузки
      const sym = input.value?.trim()?.toUpperCase();
      if (sym) {
        delete symbolSyncCache[sym];
        checkSymbolDataForProperties();
      }
    } catch (e) {
      console.warn('[Strategy Builder] Failed to preload symbols:', e);
    }
  });

  // Предзагрузка тикеров, цен и списка блокировок (прогрев кэша при загрузке страницы)
  const _preloadCat = getCategory();
  Promise.all([
    fetchBybitSymbols(_preloadCat),
    fetchTickersData(_preloadCat),
    fetchLocalSymbols(),
    fetchBlockedSymbols()
  ]).catch(() => { });
}

/** База данных: инициализация панели групп тикеров в БД. */
function initDunnahBasePanel() {
  const container = document.getElementById('dunnahBaseGroups');
  const btnRefresh = document.getElementById('btnDunnahRefresh');
  if (!container) return;

  async function loadAndRender() {
    container.innerHTML = '<p class="text-muted text-sm">Загрузка...</p>';
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 15000);
      const res = await fetch(`${API_BASE}/marketdata/symbols/db-groups?_=${Date.now()}`, {
        signal: ctrl.signal,
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' }
      });
      clearTimeout(t);
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const data = await res.json();
      const groups = data.groups || [];
      const blocked = new Set((data.blocked || []).map((s) => String(s).toUpperCase()));

      if (groups.length === 0) {
        container.innerHTML = '<p class="text-muted text-sm mb-1">В БД нет тикеров.</p><p class="text-muted text-sm" style="font-size:12px">Выберите тикер в «ОСНОВНЫЕ ПАРАМЕТРЫ» и дождитесь синхронизации.</p>';
        return;
      }

      container.innerHTML = groups
        .map((g) => {
          const sym = (g.symbol || '').trim();
          const mt = g.market_type || 'linear';
          const intervals = Object.keys(g.intervals || {}).filter(i => i !== 'UNKNOWN').sort((a, b) => {
            const order = { '1': 1, '5': 2, '15': 3, '30': 4, '60': 5, '240': 6, 'D': 7, 'W': 8, 'M': 9 };
            return (order[a] || 99) - (order[b] || 99);
          });
          const total = g.total_rows || 0;
          const isBlocked = blocked.has(sym.toUpperCase());
          const tfDisplay = intervals.length > 4
            ? intervals.slice(0, 4).join(', ') + ` +${intervals.length - 4}`
            : intervals.join(', ');

          return `
          <div class="dunnah-group-item" data-symbol="${sym}" data-market="${mt}">
            <div class="dunnah-group-header">
              <span class="dunnah-group-symbol">${sym}</span>
              <span class="dunnah-group-mt">${mt}</span>
              ${isBlocked ? '<span class="dunnah-blocked-badge" title="Заблокирован">🔒</span>' : '<span class="dunnah-unblocked-badge" title="Активен">🔓</span>'}
            </div>
            <div class="dunnah-group-info">${tfDisplay} · ${total.toLocaleString()} свечей</div>
            <div class="dunnah-group-actions">
              <button type="button" class="btn-dunnah-delete" data-symbol="${sym}" data-market="${mt}">🗑️ Удалить</button>
              ${isBlocked
              ? `<button type="button" class="btn-dunnah-unblock" data-symbol="${sym}">� Разблокировать</button>`
              : `<button type="button" class="btn-dunnah-block" data-symbol="${sym}">� Блокировать</button>`
            }
            </div>
          </div>`;
        })
        .join('');

      container.querySelectorAll('.btn-dunnah-delete').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const symbol = btn.dataset.symbol;
          const market = btn.dataset.market || 'linear';
          if (!confirm(`Удалить все данные ${symbol} (${market}) из БД?`)) return;
          btn.disabled = true;
          btn.textContent = '⏳';
          try {
            const r = await fetch(`${API_BASE}/marketdata/symbols/db-groups?symbol=${encodeURIComponent(symbol)}&market_type=${encodeURIComponent(market)}`, { method: 'DELETE' });
            if (!r.ok) throw new Error(await r.text());
            // Invalidate caches and force-reload from server
            localSymbolsCache = null;
            blockedSymbolsCache = null;
            await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
          } catch (e) {
            console.error(e);
            alert('Ошибка удаления: ' + e.message);
            await loadAndRender();
          }
        });
      });
      container.querySelectorAll('.btn-dunnah-block').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const symbol = btn.dataset.symbol;
          btn.disabled = true;
          btn.textContent = '⏳';
          try {
            const r = await fetch(`${API_BASE}/marketdata/symbols/blocked?symbol=${encodeURIComponent(symbol)}`, { method: 'POST' });
            if (!r.ok) throw new Error(await r.text());
            // Invalidate caches and force-reload from server
            localSymbolsCache = null;
            blockedSymbolsCache = null;
            await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
          } catch (e) {
            console.error(e);
            alert('Ошибка: ' + e.message);
            await loadAndRender();
          }
        });
      });
      container.querySelectorAll('.btn-dunnah-unblock').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const symbol = btn.dataset.symbol;
          btn.disabled = true;
          btn.textContent = '⏳';
          try {
            const r = await fetch(`${API_BASE}/marketdata/symbols/blocked/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
            if (!r.ok) throw new Error(await r.text());
            // Invalidate caches and force-reload from server
            localSymbolsCache = null;
            blockedSymbolsCache = null;
            await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
          } catch (e) {
            console.error(e);
            alert('Ошибка: ' + e.message);
            await loadAndRender();
          }
        });
      });
    } catch (e) {
      console.error('[База данных]', e);
      const msg = e.name === 'AbortError' ? 'Таймаут запроса (15 с)' : e.message;
      container.innerHTML = `<p class="text-danger text-sm">Ошибка: ${escapeHtml(msg)}</p><p class="text-muted text-sm" style="font-size:12px">Проверьте, что сервер запущен. Нажмите «Обновить» для повтора.</p>`;
    }
  }

  if (btnRefresh) btnRefresh.addEventListener('click', loadAndRender);
  refreshDunnahBasePanel = loadAndRender;

  // Lazy-load: загружаем данные только при первом открытии окна "База данных"
  let _dunnahPanelLoaded = false;
  document.addEventListener('floatingWindowToggle', function (e) {
    if (e.detail.windowId === 'floatingWindowDatabase' && e.detail.isOpen && !_dunnahPanelLoaded) {
      _dunnahPanelLoaded = true;
      loadAndRender();
    }
  });
  // Also mark as loaded when refreshDunnahBasePanel is called externally (e.g. after sync)
  const _origRefresh = loadAndRender;
  refreshDunnahBasePanel = function () {
    _dunnahPanelLoaded = true;
    return _origRefresh();
  };
}

function updatePropertiesProgressBar(visible, options = {}) {
  const { indeterminate = false, percent = 0 } = options;
  const progressContainer = document.getElementById('propertiesCandleLoadingProgress');
  const bar = document.getElementById('propertiesCandleLoadingBar');
  if (!progressContainer || !bar) return;
  if (visible) {
    progressContainer.classList.remove('hidden');
    bar.classList.toggle('indeterminate', indeterminate);
    bar.style.width = indeterminate ? '' : `${percent}%`;
    bar.setAttribute('aria-valuenow', percent);
  } else {
    progressContainer.classList.add('hidden');
    bar.classList.remove('indeterminate');
  }
}

/**
 * Render data sync status in Properties panel.
 * States: checking, syncing, synced, error
 */
function renderPropertiesDataStatus(state, data = {}) {
  const statusIndicator = document.getElementById('propertiesDataStatusIndicator');
  if (!statusIndicator) return;

  const { symbol = '', totalNew = 0, message = '', step = 0, totalSteps = 8 } = data;

  if (state === 'checking') {
    statusIndicator.className = 'data-status checking';
    statusIndicator.innerHTML = `<span class="status-icon">🔍</span><span class="status-text">Проверка ${escapeHtml(symbol)}...</span>`;
  } else if (state === 'syncing') {
    const progressText = totalSteps > 0 ? ` (${step}/${totalSteps})` : '';
    const newText = totalNew > 0 ? `<br><small>Загружено: +${totalNew} свечей</small>` : '';
    statusIndicator.className = 'data-status loading';
    statusIndicator.innerHTML = `<span class="status-icon">📥</span><span class="status-text">${escapeHtml(message) || 'Синхронизация...'}${progressText}${newText}</span>`;
  } else if (state === 'syncing_background') {
    statusIndicator.className = 'data-status loading';
    statusIndicator.innerHTML = `<span class="status-icon">⏳</span><span class="status-text">${escapeHtml(message) || 'Синхронизация в фоне...'}<br><small>Загрузка исторических данных может занять время</small></span>`;
  } else if (state === 'synced') {
    const icon = totalNew > 0 ? '✅' : '✓';
    const text = totalNew > 0 ? `Синхронизировано, +${totalNew} свечей` : 'Данные актуальны';
    statusIndicator.className = 'data-status available';
    statusIndicator.innerHTML = `<span class="status-icon">${icon}</span><span class="status-text">${text}<br><small>TF: 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W, 1M</small></span>`;
  } else if (state === 'blocked') {
    statusIndicator.className = 'data-status';
    statusIndicator.innerHTML = `<span class="status-icon">🔒</span><span class="status-text">${escapeHtml(message) || 'Тикер заблокирован для догрузки'}<br><small>Разблокируйте в «База данных»</small></span>`;
  } else if (state === 'error') {
    statusIndicator.className = 'data-status error';
    statusIndicator.style.cursor = 'pointer';
    statusIndicator.innerHTML = `<span class="status-icon">⚠️</span><span class="status-text">Ошибка синхронизации<br><small>${escapeHtml(message) || 'Проверьте соединение'}. Кликните для повтора.</small></span>`;
    // Add click-to-retry handler
    statusIndicator.onclick = function () {
      statusIndicator.onclick = null;
      statusIndicator.style.cursor = '';
      syncSymbolData(true);
    };
  }
}

/** Cache for last sync time per symbol to avoid too frequent syncs */
const symbolSyncCache = {};

/** Track symbols currently being synced to prevent duplicate requests */
const symbolSyncInProgress = {};

/** AbortController for the current sync — отмена при переключении на другой тикер */
let currentSyncAbortController = null;
/** Символ и время старта текущего sync — чтобы не прерывать дубликатом от change/debounce */
let currentSyncSymbol = null;
let currentSyncStartTime = 0;

/** Auto-refresh interval IDs per symbol */
const symbolRefreshTimers = {};

/**
 * Get refresh interval in ms based on timeframe (auto-actualization).
 * 1m, 5m -> 5 min; 15m -> 15 min; 30m -> 30 min; 1h -> 1h; 4h -> 4h; D -> 1d; W -> 1w
 */
function getRefreshIntervalForTF(tf) {
  // 1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M
  const tfIntervals = {
    '1': 5 * 60 * 1000, '5': 5 * 60 * 1000, '15': 15 * 60 * 1000, '30': 30 * 60 * 1000,
    '60': 60 * 60 * 1000, '240': 4 * 60 * 60 * 1000,
    'D': 24 * 60 * 60 * 1000, 'W': 7 * 24 * 60 * 60 * 1000,
    'M': 30 * 24 * 60 * 60 * 1000  // 1 month
  };
  return tfIntervals[tf] || 60 * 60 * 1000;
}

/**
 * Sync all timeframes for selected symbol using SSE for real-time progress.
 * Called when symbol is selected or periodically for auto-refresh.
 */
async function syncSymbolData(forceRefresh = false) {
  const symbolEl = document.getElementById('backtestSymbol');
  const marketEl = document.getElementById('builderMarketType');
  const statusRow = document.getElementById('propertiesDataStatusRow');

  const symbol = symbolEl?.value?.trim()?.toUpperCase();
  const marketType = marketEl?.value === 'spot' ? 'spot' : 'linear';

  if (!symbol || !statusRow) return;

  if ((blockedSymbolsCache || new Set()).has(symbol?.toUpperCase?.() ?? '')) {
    console.log(`[DataSync] ${symbol} is blocked, skipping auto-sync`);
    renderPropertiesDataStatus('blocked', { symbol, message: 'Тикер заблокирован для догрузки' });
    return;
  }

  // Check if sync is already in progress for this symbol
  if (symbolSyncInProgress[symbol]) {
    console.log(`[DataSync] ${symbol} sync already in progress, skipping`);
    return;
  }

  // Не прерывать текущий sync дубликатом от change/debounce (тот же символ, вызов через ~200 ms)
  const DUPLICATE_SYNC_GRACE_MS = 600;
  if (currentSyncAbortController && currentSyncSymbol === symbol && Date.now() - currentSyncStartTime < DUPLICATE_SYNC_GRACE_MS) {
    console.log('[DataSync] Same symbol sync in progress, skipping duplicate (change/debounce)');
    return;
  }

  // Abort only if in-flight sync is for a *different* symbol (переключение тикера во время загрузки)
  if (currentSyncAbortController && currentSyncSymbol !== symbol) {
    console.log(`[DataSync] Aborting previous sync (switched symbol ${currentSyncSymbol} -> ${symbol})`);
    currentSyncAbortController.abort();
    currentSyncAbortController = null;
  }

  // Check if we synced recently (within 10 seconds) unless forced — при выборе из списка forceRefresh=true
  const SYNC_CACHE_MS = 10000;
  const lastSync = symbolSyncCache[symbol];
  if (!forceRefresh && lastSync && Date.now() - lastSync < SYNC_CACHE_MS) {
    console.log(`[DataSync] ${symbol} synced recently, skipping`);
    return;
  }

  // Mark sync as in progress
  symbolSyncInProgress[symbol] = true;

  statusRow.classList.remove('hidden');
  renderPropertiesDataStatus('checking', { symbol });
  updatePropertiesProgressBar(true, { indeterminate: true });

  // Show global loading indicator
  showGlobalLoading(`Синхронизация ${symbol}...`);

  // Динамический таймаут: сбрасывается при каждом полученном SSE event.
  // Если данные приходят — процесс жив. Таймаут срабатывает только если
  // сервер молчит > 90 секунд (например, потеря соединения).
  const controller = new AbortController();
  currentSyncAbortController = controller;
  currentSyncSymbol = symbol;
  currentSyncStartTime = Date.now();
  const SYNC_INACTIVITY_TIMEOUT_MS = 90000; // 90 сек без SSE events = таймаут
  let timeoutId = setTimeout(() => controller.abort(), SYNC_INACTIVITY_TIMEOUT_MS);

  // Helper: сброс таймаута при получении данных
  const resetSyncTimeout = () => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => controller.abort(), SYNC_INACTIVITY_TIMEOUT_MS);
  };

  try {
    // Прогресс по TF: 1 → 5 → 15 → 30 → 60 → 240 → D → W → M
    const totalSteps = 9;
    renderPropertiesDataStatus('syncing', {
      symbol,
      message: 'Синхронизация БД с биржей...',
      step: 0,
      totalSteps
    });
    updatePropertiesProgressBar(true, { indeterminate: false, percent: 0 });

    const streamUrl = `${API_BASE}/marketdata/symbols/sync-all-tf-stream?symbol=${encodeURIComponent(symbol)}&market_type=${marketType}`;
    console.log('[DataSync] Starting sync (stream):', streamUrl);

    const response = await fetch(streamUrl, { signal: controller.signal });

    if (!response.ok) {
      clearTimeout(timeoutId);
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      // Данные пришли — сброс таймаута неактивности
      resetSyncTimeout();
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const dataMatch = line.match(/^data:\s*(.+)$/m);
        if (!dataMatch) continue;
        try {
          const data = JSON.parse(dataMatch[1]);
          if (data.event === 'progress') {
            const percent = Math.min(100, data.percent != null ? data.percent : Math.round(((data.step || 0) / (data.totalSteps || totalSteps)) * 100));
            updatePropertiesProgressBar(true, { indeterminate: false, percent });
            renderPropertiesDataStatus('syncing', {
              symbol,
              message: data.message || `Синхронизация ${data.tfName || data.tf}...`,
              step: data.step || 0,
              totalSteps: data.totalSteps || totalSteps,
              totalNew: data.totalNew || 0
            });
          } else if (data.event === 'complete') {
            clearTimeout(timeoutId);
            result = { timeframes: data.results, total_new_candles: data.totalNew, summary: data.message, cancelled: !!data.cancelled };
          } else if (data.event === 'error') {
            throw new Error(data.message || 'Ошибка синхронизации');
          }
        } catch (parseErr) {
          if (parseErr instanceof SyntaxError) continue;
          throw parseErr;
        }
      }
    }

    if (!result) {
      clearTimeout(timeoutId);
      throw new Error('Синхронизация не вернула результат');
    }

    if (result.cancelled) {
      console.log('[DataSync] Sync cancelled (client disconnected)');
      updatePropertiesProgressBar(false);
      hideGlobalLoading();
      return;
    }

    console.log('[DataSync] Sync complete:', result);

    symbolSyncCache[symbol] = Date.now();
    updatePropertiesProgressBar(false);

    const timeframes = result.timeframes || {};
    const timeoutTfs = Object.entries(timeframes).filter(([, v]) => v && v.status === 'timeout').map(([tf]) => tf);
    const totalNew = result.total_new_candles || 0;
    if (timeoutTfs.length > 0) {
      renderPropertiesDataStatus('synced', {
        symbol,
        totalNew,
        message: `Синхронизировано частично: ${timeoutTfs.join(', ')} не успел(и). Остальные TF готовы. Кликните для повторной попытки.`
      });
    } else {
      renderPropertiesDataStatus('synced', {
        symbol,
        totalNew,
        message: result.summary || 'Данные синхронизированы'
      });
    }

    hideGlobalLoading();
    setupAutoRefresh(symbol);
    if (typeof refreshDunnahBasePanel === 'function') refreshDunnahBasePanel();

  } catch (e) {
    clearTimeout(timeoutId);

    const currentSymbol = document.getElementById('backtestSymbol')?.value?.trim()?.toUpperCase();
    const wasAbortedBySwitch = e.name === 'AbortError' && currentSymbol !== symbol;

    if (wasAbortedBySwitch) {
      console.log(`[DataSync] ${symbol} sync aborted (switched to ${currentSymbol})`);
      // Не сбрасывать прогресс и global loading — новая синхронизация (currentSymbol) уже отрисовала свой UI
      return;
    }

    if (e.name === 'AbortError') {
      console.log('[DataSync] Sync timeout — no SSE events for 90s');
      // Don't cache timeout — allow immediate retry
      updatePropertiesProgressBar(false);
      renderPropertiesDataStatus('error', {
        message: 'Потеря связи с сервером (нет данных 90 сек). Кликните для повторной попытки.'
      });
      hideGlobalLoading();
      return;
    }

    console.error('[DataSync] Sync failed:', e);
    updatePropertiesProgressBar(false);
    renderPropertiesDataStatus('error', { message: e.message });
    hideGlobalLoading();
  } finally {
    if (currentSyncAbortController === controller) {
      currentSyncAbortController = null;
      currentSyncSymbol = null;
    }
    delete symbolSyncInProgress[symbol];
  }
}

/**
 * Setup auto-refresh timer for the current symbol based on selected TF.
 * Clears any previous timers (only one symbol is active at a time).
 */
function setupAutoRefresh(symbol) {
  const tfEl = document.getElementById('strategyTimeframe');
  const tf = tfEl?.value || '15';

  // Clear all existing refresh timers (only one symbol active at a time)
  for (const sym of Object.keys(symbolRefreshTimers)) {
    clearInterval(symbolRefreshTimers[sym]);
    delete symbolRefreshTimers[sym];
  }

  const interval = getRefreshIntervalForTF(tf);
  const intervalMin = interval / 60000;
  console.log(`[DataSync] Auto-refresh for ${symbol} every ${intervalMin} min (TF=${tf})`);

  symbolRefreshTimers[symbol] = setInterval(() => {
    console.log(`[DataSync] Auto-refresh triggered for ${symbol}`);
    syncSymbolData(true);
  }, interval);
}

/** Force refresh - called from button click */
window.forceRefreshTickerData = function () {
  syncSymbolData(true);
};

/**
 * Main function called when symbol or TF changes.
 * Triggers data sync for the selected symbol.
 * @param {boolean} [forceRefresh=false] — при true игнорируем кэш «недавно синхронизирован» (выбор из списка)
 */
async function runCheckSymbolDataForProperties(forceRefresh = false) {
  await syncSymbolData(forceRefresh);
}

// Debounce 200 ms — быстрее запуск синхронизации после смены Symbol/TF/типа рынка (было 600 ms)
checkSymbolDataForProperties = debounce(runCheckSymbolDataForProperties, 200);

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
      sizeInput.value = sizeInput.value || 100;
      break;
    case 'fixed_amount':
      sizeLabel.textContent = 'Сумма на ордер ($)';
      sizeInput.min = 1;
      sizeInput.max = 1000000;
      sizeInput.step = 1;
      sizeInput.value = sizeInput.value || 100;
      break;
    case 'contracts':
      sizeLabel.textContent = 'Контракты/Лоты';
      sizeInput.min = 0.001;
      sizeInput.max = 10000;
      sizeInput.step = 0.001;
      sizeInput.value = sizeInput.value || 1;
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
  if (backtestSymbolEl) backtestSymbolEl.addEventListener('change', checkSymbolDataForProperties);
  if (strategyTimeframeEl) strategyTimeframeEl.addEventListener('change', () => {
    checkSymbolDataForProperties();
    // Restart auto-refresh with new TF interval
    const sym = backtestSymbolEl?.value?.trim()?.toUpperCase();
    if (sym && symbolSyncCache[sym]) setupAutoRefresh(sym);
  });
  if (builderMarketTypeEl) builderMarketTypeEl.addEventListener('change', checkSymbolDataForProperties);

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
      if (indicator?.classList.contains('error')) syncSymbolData(true);
    });
  }

  // База данных
  initDunnahBasePanel();

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

  // Templates button - MUST be set up BEFORE overlay handler
  const btnTemplates = document.getElementById('btnTemplates');
  if (btnTemplates) {
    // Flag to prevent overlay from closing modal when opening via button
    let openingViaButton = false;

    btnTemplates.addEventListener('click', function (e) {
      console.log('[Strategy Builder] Templates button clicked');
      e.preventDefault();
      e.stopImmediatePropagation(); // Stop ALL event propagation immediately

      const modal = document.getElementById('templatesModal');
      const isCurrentlyOpen = modal && modal.classList.contains('active');

      if (isCurrentlyOpen) {
        console.log('[Strategy Builder] Modal already open, closing');
        openingViaButton = false;
        closeTemplatesModal();
      } else {
        console.log('[Strategy Builder] Opening modal via button');
        openingViaButton = true;

        // Update open time before opening
        if (window._updateTemplatesModalOpenTime) {
          window._updateTemplatesModalOpenTime();
        }

        // Open modal immediately using requestAnimationFrame to ensure DOM is ready
        requestAnimationFrame(() => {
          openTemplatesModal();

          // Double-check modal is still open after a short delay
          setTimeout(() => {
            if (!modal.classList.contains('active')) {
              console.warn('[Strategy Builder] Modal closed unexpectedly, reopening...');
              modal.classList.add('active');
            }
          }, 50);
        });

        // Reset flag after a delay to allow modal to fully open
        setTimeout(() => {
          openingViaButton = false;
          console.log('[Strategy Builder] Opening flag reset');
        }, 800); // Increased delay to ensure modal is fully opened
      }
    }, true); // Use capture phase to handle BEFORE overlay handler

    console.log('[Strategy Builder] Templates button listener attached');

    // Store flag in window for overlay handler to check
    window._templatesModalOpeningViaButton = () => openingViaButton;
  } else {
    console.error('[Strategy Builder] Templates button not found!');
  }

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

  document.querySelectorAll('[onclick*="fitToScreen"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', fitToScreen);
  });

  // Zoom buttons
  document.querySelectorAll('[onclick*="zoomIn"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', zoomIn);
  });

  document.querySelectorAll('[onclick*="zoomOut"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', zoomOut);
  });

  document.querySelectorAll('[onclick*="resetZoom"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', resetZoom);
  });

  // Modal buttons by ID
  const btnCloseModal = document.getElementById('btnCloseModal');
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Close button clicked');
      closeTemplatesModal();
    });
  } else {
    console.warn('[Strategy Builder] Close modal button not found');
  }

  const btnCancelModal = document.getElementById('btnCancelModal');
  if (btnCancelModal) {
    btnCancelModal.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Cancel button clicked');
      closeTemplatesModal();
    });
  } else {
    console.warn('[Strategy Builder] Cancel modal button not found');
  }

  const btnLoadTemplate = document.getElementById('btnLoadTemplate');
  if (btnLoadTemplate) {
    btnLoadTemplate.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Load Template button clicked');
      loadSelectedTemplate();
    });
  } else {
    console.warn('[Strategy Builder] Load Template button not found');
  }

  // Templates grid - event delegation for template selection
  const templatesGrid = document.getElementById('templatesGrid');
  if (templatesGrid) {
    templatesGrid.addEventListener('click', function (e) {
      const card = e.target.closest('.template-card');
      if (card) {
        const templateId = card.dataset.templateId;
        if (templateId) {
          selectTemplate(templateId);
        }
      }
    });
  }

  const importTemplateInput = document.getElementById('importTemplateInput');
  if (importTemplateInput) {
    importTemplateInput.addEventListener('change', function (e) {
      const file = e.target.files?.[0];
      if (file) {
        importTemplateFromFile(file);
        e.target.value = '';
      }
    });
  }

  // Templates modal: do NOT close on overlay click (caused immediate close / invisible content).
  // Close only via Close (X), Cancel, or Use Template buttons.
  const templatesModal = document.getElementById('templatesModal');
  if (templatesModal) {
    // No overlay click handler - modal closes only via btnCloseModal, btnCancelModal, btnLoadTemplate
    window._updateTemplatesModalOpenTime = () => { }; // no-op for compatibility

    // Prevent modal content clicks from bubbling to overlay
    const modalContent = templatesModal.querySelector('.modal');
    if (modalContent) {
      modalContent.addEventListener('click', function (e) {
        console.log('[Strategy Builder] Modal content click, stopping propagation');
        e.stopPropagation();
      });
    } else {
      console.warn('[Strategy Builder] Modal content (.modal) not found!');
    }
  } else {
    console.error('[Strategy Builder] Templates modal not found during setup!');
  }
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
    const name = item.querySelector('.block-name').textContent.toLowerCase();
    const desc = item.querySelector('.block-desc').textContent.toLowerCase();
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
      // Long range filter
      use_long_range: false,
      long_rsi_more: 30,
      long_rsi_less: 70,
      // Short range filter
      use_short_range: false,
      short_rsi_less: 70,
      short_rsi_more: 30,
      // Cross level
      use_cross_level: false,
      cross_long_level: 30,
      cross_short_level: 70,
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
      // Signal Memory
      disable_signal_memory: false,
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
      grid_size_percent: 15,
      order_count: 5,
      martingale_coefficient: 1.0,
      log_steps_coefficient: 1.0,
      first_order_offset: 0,
      grid_trailing: 0
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
        { key: 'signal_only_if_macd_positive', label: 'Signal only if MACD < 0 (Long) or > 0 (Short)', type: 'checkbox', tooltip: 'Filter: only generate long signals when MACD < 0, short when MACD > 0' },
        { key: 'opposite_macd_cross_signal', label: 'Opposite Signal - MACD Cross with Signal Line', type: 'checkbox', tooltip: 'Swap long/short signals for signal line cross' },
        { type: 'divider' },
        { key: 'disable_signal_memory', label: '==Disable Signal Memory (for both MACD Crosses)==', type: 'checkbox', tooltip: 'When disabled, cross signals only fire on the exact bar of crossing. When enabled, signals persist for N bars.' }
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
        { key: 'grid_size_percent', label: 'Grid Size (%)', type: 'number', step: 1, min: 1, max: 100, optimizable: true },
        { key: 'order_count', label: 'Number of orders in the grid (3-15)', type: 'number', step: 1, min: 3, max: 15, optimizable: true },
        { key: 'martingale_coefficient', label: 'Orders Value Martingale (1.0-1.8)', type: 'number', step: 0.1, min: 1.0, max: 1.8, optimizable: true },
        { key: 'log_steps_coefficient', label: 'Logarithmic Orders Steps (0.8-1.4)', type: 'number', step: 0.1, min: 0.8, max: 1.4, optimizable: true },
        { key: 'first_order_offset', label: 'Indent / Offset (0=Market, 0.01-10%)', type: 'number', step: 0.01, min: 0, max: 10, optimizable: true },
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
  const renderOptRow = (key, label, value) => {
    const opt = optParams[key] || { enabled: false, min: value, max: value, step: 1 };
    const disabled = opt.enabled ? '' : 'disabled';
    return `
      <div class="tv-opt-row" data-param-key="${key}">
        <input type="checkbox" 
               class="tv-opt-checkbox"
               data-param-key="${key}"
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
      // In optimization mode, render inline fields as separate opt rows
      field.fields.forEach(f => {
        if (f.type === 'number' && f.optimizable) {
          const val = params[f.key] ?? 0;
          const label = f.label || formatParamName(f.key);
          html += renderOptRow(f.key, label, val);
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
        // Optimization mode - use complete opt row
        html += renderOptRow(field.key, field.label, val);
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
        { id: 'hist', label: 'Hist', type: 'data' },
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
    return `Grid: ${params.grid_size_percent || 0}% | ${params.order_count || 0} orders | M:${params.martingale_coefficient || 1}`;
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
          block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
        }
        block.optimizationParams[key].enabled = checkbox.checked;
        updateBlockOptimizationIndicator(blockId);
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
        block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
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
        block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
      }
      block.optimizationParams[key][field] = parseFloat(input.value);
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
  const popupHeight = popup.offsetHeight || 400;
  const padding = 10; // Gap between block and popup
  const margin = 10; // Margin from viewport edges
  const viewportH = window.innerHeight;
  const viewportW = window.innerWidth;

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
    { key: 'filters', label: 'Фильтры', icon: 'funnel' },
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
      <i class="bi bi-${block.icon || 'box'}"></i>
      <div class="quick-add-item-info">
        <span class="quick-add-item-name">${block.name}</span>
        <span class="quick-add-item-desc">${block.desc || ''}</span>
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
      <i class="bi bi-${block.icon || 'box'}"></i>
      <div class="quick-add-item-info">
        <span class="quick-add-item-name">${block.name}</span>
        <span class="quick-add-item-desc">${block.desc || ''}</span>
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
    const newId = `block_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
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
        id: `conn_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
        source: { blockId: newSourceId, portId: conn.source.portId },
        target: { blockId: newTargetId, portId: conn.target.portId },
        type: conn.type
      });
    }
  });

  // BUG#4 FIX: renderBlocks() calls renderConnections() internally — no double render
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
          <div class="preset-item" data-preset-id="${p.id}">
            <div class="preset-item-info">
              <div class="preset-item-name">${p.name}</div>
              <div class="preset-item-meta">
                ${p.blockCount} блоков, ${p.connectionCount} связей
              </div>
              ${p.description ? `<div class="preset-item-desc">${p.description}</div>` : ''}
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

  // Remove block
  const idx = strategyBlocks.findIndex(b => b.id === blockId);
  if (idx !== -1) {
    strategyBlocks.splice(idx, 1);
  }

  if (selectedBlockId === blockId) {
    selectedBlockId = null;
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

  for (const [paramName, rule] of Object.entries(rules)) {
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

// ============================================

let isConnecting = false;
let connectionStart = null;
let tempLine = null;

function initConnectionSystem() {
  const _canvas = document.getElementById('connectionsCanvas');
  const container = document.getElementById('canvasContainer');

  // Listen for port clicks (left button — start connection)
  container.addEventListener('mousedown', (e) => {
    const port = e.target.closest('.port');
    if (port) {
      e.stopPropagation();
      startConnection(port, e);
    }
  });

  // Right-click on port — disconnect all connections from that port
  container.addEventListener('contextmenu', (e) => {
    const port = e.target.closest('.port');
    if (port) {
      e.preventDefault();
      e.stopPropagation();
      disconnectPort(port);
      return;
    }
    // Right-click on connection line — delete that connection
    const connLine = e.target.closest('.connection-line');
    if (connLine && connLine.dataset.connectionId) {
      e.preventDefault();
      e.stopPropagation();
      deleteConnection(connLine.dataset.connectionId);
    }
  });

  // Left-click on connection line — delete (event delegation, avoids listener leak)
  container.addEventListener('click', (e) => {
    const connLine = e.target.closest('.connection-line:not(.temp)');
    if (connLine && connLine.dataset.connectionId) {
      deleteConnection(connLine.dataset.connectionId);
    }
  });

  // Listen for mouse move during connection
  container.addEventListener('mousemove', (e) => {
    if (isConnecting) {
      updateTempConnection(e);
    }
  });

  // Listen for mouse up to complete connection
  container.addEventListener('mouseup', (e) => {
    if (isConnecting) {
      const port = e.target.closest('.port');
      if (port && port !== connectionStart.element) {
        completeConnection(port);
      } else {
        cancelConnection();
      }
    }
  });
}

function startConnection(portElement, _event) {
  isConnecting = true;
  const rect = portElement.getBoundingClientRect();
  const containerRect = document
    .getElementById('canvasContainer')
    .getBoundingClientRect();

  connectionStart = {
    element: portElement,
    blockId: portElement.dataset.blockId,
    portId: portElement.dataset.portId,
    portType: portElement.dataset.portType,
    direction: portElement.dataset.direction,
    x: rect.left + rect.width / 2 - containerRect.left,
    y: rect.top + rect.height / 2 - containerRect.top
  };

  // Create temp line
  const svg = document.getElementById('connectionsCanvas');
  tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  tempLine.classList.add('connection-line', 'temp');
  svg.appendChild(tempLine);

  portElement.classList.add('connecting');

  // Highlight compatible ports
  highlightCompatiblePorts(connectionStart);
}

/**
 * Map config block types to their preferred Strategy node target port.
 * SL/TP blocks → sl_tp, Close conditions → close_cond, DCA/Grid → dca_grid.
 */
const CONFIG_BLOCK_TARGET_PORT = {
  // SL/TP blocks → sl_tp port
  static_sltp: 'sl_tp',
  trailing_stop_exit: 'sl_tp',
  atr_exit: 'sl_tp',
  multi_tp_exit: 'sl_tp',
  // Close condition blocks → close_cond port
  close_by_time: 'close_cond',
  close_channel: 'close_cond',
  close_ma_cross: 'close_cond',
  close_rsi: 'close_cond',
  close_stochastic: 'close_cond',
  close_psar: 'close_cond',
  // DCA/Grid blocks → dca_grid port
  dca: 'dca_grid',
  grid_orders: 'dca_grid'
};

/**
 * Get the preferred Strategy node target port ID for a given block type.
 * Returns null if the block type has no specific preference (non-config).
 */
function getPreferredStrategyPort(blockType) {
  return CONFIG_BLOCK_TARGET_PORT[blockType] || null;
}

/**
 * Highlight ports that are compatible with the connection being made.
 * For config ports: only highlight the CORRECT Strategy node port
 * (e.g. DCA block → only DCA port, not SL/TP or Close).
 * @param {Object} startInfo - Connection start info with portType and direction
 */
function highlightCompatiblePorts(startInfo) {
  const allPorts = document.querySelectorAll('.port');
  const compatibleType = startInfo.portType;
  const oppositeDirection = startInfo.direction === 'output' ? 'input' : 'output';

  // For config blocks, determine preferred target port on Strategy node
  let preferredTargetPortId = null;
  if (compatibleType === 'config') {
    const sourceBlock = strategyBlocks.find(b => b.id === startInfo.blockId);
    if (sourceBlock) {
      preferredTargetPortId = getPreferredStrategyPort(sourceBlock.type);
    }
  }

  allPorts.forEach(port => {
    // Skip the starting port itself
    if (port === startInfo.element) return;

    const portType = port.dataset.portType;
    const portDirection = port.dataset.direction;
    const portBlockId = port.dataset.blockId;
    const portId = port.dataset.portId;

    // Basic compatibility: same type, opposite direction, different block
    let isCompatible =
      portType === compatibleType &&
      portDirection === oppositeDirection &&
      portBlockId !== startInfo.blockId;

    // Smart config filtering: if dragging from a config block,
    // only highlight the CORRECT port on the Strategy node
    if (isCompatible && compatibleType === 'config' && preferredTargetPortId) {
      const targetBlock = strategyBlocks.find(b => b.id === portBlockId);
      if (targetBlock && targetBlock.isMain) {
        // On Strategy node — only highlight the preferred port
        isCompatible = (portId === preferredTargetPortId);
      }
    }

    if (isCompatible) {
      port.classList.add('port-compatible');
    } else {
      port.classList.add('port-incompatible');
    }
  });
}

/**
 * Remove all port highlighting
 */
function clearPortHighlights() {
  document.querySelectorAll('.port').forEach((port) => {
    port.classList.remove('port-compatible', 'port-incompatible');
  });
}

/**
 * Try to auto-connect when a block is dropped near a compatible port
 * @param {string} droppedBlockId - ID of the block that was just dropped
 */
function tryAutoSnapConnection(droppedBlockId) {
  const droppedBlock = document.getElementById(droppedBlockId);
  if (!droppedBlock) return;

  const SNAP_DISTANCE = 50; // pixels - distance threshold for auto-snap
  const droppedPorts = droppedBlock.querySelectorAll('.port');

  // Get all ports from other blocks
  const otherPorts = document.querySelectorAll(
    `.port:not([data-block-id="${droppedBlockId}"])`
  );

  let bestMatch = null;
  let bestDistance = SNAP_DISTANCE;

  droppedPorts.forEach((droppedPort) => {
    const droppedRect = droppedPort.getBoundingClientRect();
    const droppedCenterX = droppedRect.left + droppedRect.width / 2;
    const droppedCenterY = droppedRect.top + droppedRect.height / 2;

    const droppedType = droppedPort.dataset.portType;
    const droppedDirection = droppedPort.dataset.direction;
    const droppedPortId = droppedPort.dataset.portId;

    otherPorts.forEach((otherPort) => {
      const otherType = otherPort.dataset.portType;
      const otherDirection = otherPort.dataset.direction;
      const otherBlockId = otherPort.dataset.blockId;
      const otherPortId = otherPort.dataset.portId;

      // Check compatibility: same type, opposite direction
      if (otherType !== droppedType || otherDirection === droppedDirection) {
        return;
      }

      // Smart config filtering: config blocks should only snap to correct port
      if (droppedType === 'config') {
        const droppedBlockData = strategyBlocks.find(b => b.id === droppedBlockId);
        const otherBlockData = strategyBlocks.find(b => b.id === otherBlockId);
        if (droppedBlockData && otherBlockData?.isMain) {
          const preferred = getPreferredStrategyPort(droppedBlockData.type);
          if (preferred && otherPortId !== preferred) return;
        }
      }

      // Check if already connected
      const alreadyConnected = connections.some((c) => {
        const matchesDropped =
          (c.source.blockId === droppedBlockId &&
            c.source.portId === droppedPortId) ||
          (c.target.blockId === droppedBlockId &&
            c.target.portId === droppedPortId);
        const matchesOther =
          (c.source.blockId === otherBlockId &&
            c.source.portId === otherPortId) ||
          (c.target.blockId === otherBlockId &&
            c.target.portId === otherPortId);
        return matchesDropped && matchesOther;
      });

      if (alreadyConnected) return;

      // Calculate distance
      const otherRect = otherPort.getBoundingClientRect();
      const otherCenterX = otherRect.left + otherRect.width / 2;
      const otherCenterY = otherRect.top + otherRect.height / 2;

      const distance = Math.sqrt(
        Math.pow(droppedCenterX - otherCenterX, 2) +
        Math.pow(droppedCenterY - otherCenterY, 2)
      );

      if (distance < bestDistance) {
        bestDistance = distance;
        bestMatch = {
          droppedPort: {
            blockId: droppedBlockId,
            portId: droppedPortId,
            direction: droppedDirection
          },
          otherPort: {
            blockId: otherBlockId,
            portId: otherPortId,
            direction: otherDirection
          },
          type: droppedType
        };
      }
    });
  });

  // Create connection if found close match
  if (bestMatch) {
    const source =
      bestMatch.droppedPort.direction === 'output'
        ? bestMatch.droppedPort
        : bestMatch.otherPort;
    const target =
      bestMatch.droppedPort.direction === 'output'
        ? bestMatch.otherPort
        : bestMatch.droppedPort;

    // Check if this exact connection already exists
    const exists = connections.some(
      (c) =>
        c.source.blockId === source.blockId &&
        c.source.portId === source.portId &&
        c.target.blockId === target.blockId &&
        c.target.portId === target.portId
    );

    if (!exists) {
      pushUndo();
      connections.push({
        id: `conn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        source: { blockId: source.blockId, portId: source.portId },
        target: { blockId: target.blockId, portId: target.portId },
        type: bestMatch.type
      });

      // Visual feedback
      showNotification('Соединение создано автоматически', 'success');
    }
  }
}

function updateTempConnection(event) {
  if (!tempLine || !connectionStart) return;

  const containerRect = document
    .getElementById('canvasContainer')
    .getBoundingClientRect();
  const endX = event.clientX - containerRect.left;
  const endY = event.clientY - containerRect.top;

  const path = createBezierPath(
    connectionStart.x,
    connectionStart.y,
    endX,
    endY,
    connectionStart.direction === 'output'
  );
  tempLine.setAttribute('d', path);
}

function completeConnection(endPortElement) {
  const endDirection = endPortElement.dataset.direction;

  // Validate: can't connect same direction
  if (connectionStart.direction === endDirection) {
    cancelConnection();
    return;
  }

  // Validate: can't connect same block
  if (connectionStart.blockId === endPortElement.dataset.blockId) {
    cancelConnection();
    return;
  }

  // Validate: port types should be compatible
  const startType = connectionStart.portType;
  const endType = endPortElement.dataset.portType;
  if (startType !== endType) {
    // Allow data->data, condition->condition, flow->flow
    cancelConnection();
    showNotification('Несовместимые типы портов', 'error');
    return;
  }

  // Determine source and target
  let source, target;
  if (connectionStart.direction === 'output') {
    source = {
      blockId: connectionStart.blockId,
      portId: connectionStart.portId
    };
    target = {
      blockId: endPortElement.dataset.blockId,
      portId: endPortElement.dataset.portId
    };
  } else {
    source = {
      blockId: endPortElement.dataset.blockId,
      portId: endPortElement.dataset.portId
    };
    target = {
      blockId: connectionStart.blockId,
      portId: connectionStart.portId
    };
  }

  // Smart config redirect: if a config block connects to the wrong
  // Strategy port, silently redirect to the correct one
  if (startType === 'config') {
    const sourceBlock = strategyBlocks.find(b => b.id === source.blockId);
    const targetBlock = strategyBlocks.find(b => b.id === target.blockId);
    if (sourceBlock && targetBlock?.isMain) {
      const preferred = getPreferredStrategyPort(sourceBlock.type);
      if (preferred) {
        target.portId = preferred;
      }
    }
  }

  // Check if connection already exists
  const exists = connections.some(
    (c) =>
      c.source.blockId === source.blockId &&
      c.source.portId === source.portId &&
      c.target.blockId === target.blockId &&
      c.target.portId === target.portId
  );

  if (!exists) {
    pushUndo();
    connections.push({
      id: `conn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      source,
      target,
      type: startType
    });
  }

  cancelConnection();
  renderConnections();
}

function cancelConnection() {
  isConnecting = false;
  if (tempLine) {
    tempLine.remove();
    tempLine = null;
  }
  if (connectionStart?.element) {
    connectionStart.element.classList.remove('connecting');
  }
  connectionStart = null;

  // Clear port highlighting
  clearPortHighlights();
}

/**
 * Normalize a connection object to the canonical internal format:
 *   { id, source: { blockId, portId }, target: { blockId, portId }, type }
 *
 * Handles 3 backend formats:
 * 1. { source: { blockId, portId }, target: { blockId, portId } }  — builder_connect_blocks
 * 2. { from, to }                                                  — legacy/test
 * 3. { source_block, source_output, target_block, target_input }   — old manual
 */
function normalizeConnection(conn) {
  // Already in canonical format
  if (conn.source && typeof conn.source === 'object' && conn.source.blockId) {
    return {
      id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      source: { blockId: conn.source.blockId, portId: conn.source.portId || 'out' },
      target: { blockId: conn.target.blockId, portId: conn.target.portId || 'in' },
      type: conn.type || 'data'
    };
  }

  // Format 3: { source_block, source_output, target_block, target_input }
  if (conn.source_block && conn.target_block) {
    return {
      id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      source: { blockId: conn.source_block, portId: conn.source_output || 'out' },
      target: { blockId: conn.target_block, portId: conn.target_input || 'in' },
      type: conn.type || 'data'
    };
  }

  // Format 2: { from, to } — legacy, no port info
  if (conn.from && conn.to) {
    return {
      id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      source: { blockId: conn.from, portId: 'out' },
      target: { blockId: conn.to, portId: 'in' },
      type: conn.type || 'data'
    };
  }

  // Unknown format — log and return as-is with defaults
  console.warn('[Strategy Builder] Unknown connection format:', conn);
  return {
    id: conn.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    source: { blockId: conn.source || '', portId: 'out' },
    target: { blockId: conn.target || '', portId: 'in' },
    type: conn.type || 'data'
  };
}

/**
 * Normalize all connections in-place. Called after loading from API.
 */
function normalizeAllConnections() {
  for (let i = 0; i < connections.length; i++) {
    connections[i] = normalizeConnection(connections[i]);
  }
}

function renderConnections() {
  const svg = document.getElementById('connectionsCanvas');
  // Clear existing connections (except temp)
  svg
    .querySelectorAll('.connection-line:not(.temp)')
    .forEach((el) => el.remove());

  connections.forEach((conn) => {
    const sourceBlock = document.getElementById(conn.source.blockId);
    const targetBlock = document.getElementById(conn.target.blockId);

    if (!sourceBlock || !targetBlock) {
      console.warn('[renderConnections] Block not found:', {
        sourceBlockId: conn.source.blockId,
        targetBlockId: conn.target.blockId,
        sourceFound: !!sourceBlock,
        targetFound: !!targetBlock
      });
      return;
    }

    // Find ports
    const sourcePort = sourceBlock.querySelector(
      `[data-port-id="${conn.source.portId}"][data-direction="output"]`
    );
    const targetPort = targetBlock.querySelector(
      `[data-port-id="${conn.target.portId}"][data-direction="input"]`
    );

    if (!sourcePort || !targetPort) {
      console.warn('[renderConnections] Port not found:', {
        sourceBlockId: conn.source.blockId,
        sourcePortId: conn.source.portId,
        targetBlockId: conn.target.blockId,
        targetPortId: conn.target.portId,
        sourcePortFound: !!sourcePort,
        targetPortFound: !!targetPort,
        availableSourcePorts: Array.from(sourceBlock.querySelectorAll('[data-direction="output"]')).map(p => p.dataset.portId),
        availableTargetPorts: Array.from(targetBlock.querySelectorAll('[data-direction="input"]')).map(p => p.dataset.portId)
      });
    }

    if (!sourcePort || !targetPort) return;

    const containerRect = document
      .getElementById('canvasContainer')
      .getBoundingClientRect();
    const sourceRect = sourcePort.getBoundingClientRect();
    const targetRect = targetPort.getBoundingClientRect();

    const startX = sourceRect.left + sourceRect.width / 2 - containerRect.left;
    const startY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
    const endX = targetRect.left + targetRect.width / 2 - containerRect.left;
    const endY = targetRect.top + targetRect.height / 2 - containerRect.top;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.classList.add('connection-line', conn.type);

    // Add per-config-port color class for differentiated connection lines
    if (conn.type === 'config') {
      const tPortId = conn.target.portId;
      if (tPortId === 'sl_tp') path.classList.add('config-sltp');
      else if (tPortId === 'close_cond') path.classList.add('config-close');
      else if (tPortId === 'dca_grid') path.classList.add('config-dca');
    }

    // Direction mismatch detection:
    // If user selected direction "short" but wire goes to entry_long/exit_long → mismatch
    // If user selected direction "long" but wire goes to entry_short/exit_short → mismatch
    // Also: source port "long" wired to entry_short (or vice versa) → signal/port mismatch
    const direction = document.getElementById('builderDirection')?.value || 'both';
    const targetPortId = conn.target.portId;
    const sourcePortId = conn.source.portId;

    const isLongTarget = targetPortId === 'entry_long' || targetPortId === 'exit_long';
    const isShortTarget = targetPortId === 'entry_short' || targetPortId === 'exit_short';

    let isMismatch = false;

    // Case 1: Direction filter conflicts with target port
    if (direction === 'long' && isShortTarget) {
      isMismatch = true;
    } else if (direction === 'short' && isLongTarget) {
      isMismatch = true;
    }

    // Case 2: Source signal direction conflicts with target port
    // e.g., divergence "long"/"bullish" output → entry_short (cross-wired)
    const isLongSource = sourcePortId === 'long' || sourcePortId === 'bullish';
    const isShortSource = sourcePortId === 'short' || sourcePortId === 'bearish';
    if (isLongSource && isShortTarget) {
      isMismatch = true;
    } else if (isShortSource && isLongTarget) {
      isMismatch = true;
    }

    if (isMismatch) {
      path.classList.add('direction-mismatch');
      // Add tooltip explaining the mismatch
      const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      if (direction !== 'both' && (isLongTarget || isShortTarget)) {
        const portDir = isLongTarget ? 'Long' : 'Short';
        const selDir = direction === 'long' ? 'Long' : 'Short';
        titleEl.textContent = `⚠ Несоответствие: направление "${selDir}", но провод подключён к "${portDir}" порту`;
      } else {
        titleEl.textContent = `⚠ Несоответствие: сигнал "${sourcePortId}" подключён к "${targetPortId}" порту`;
      }
      path.appendChild(titleEl);
    }

    path.setAttribute('d', createBezierPath(startX, startY, endX, endY, true));
    path.dataset.connectionId = conn.id;

    // Event listeners handled by delegation in initConnectionSystem()

    svg.appendChild(path);

    // Mark ports as connected
    sourcePort.classList.add('connected');
    targetPort.classList.add('connected');
  });
}

function createBezierPath(x1, y1, x2, y2, fromOutput) {
  const dx = Math.abs(x2 - x1);
  const controlOffset = Math.max(50, dx * 0.5);

  if (fromOutput) {
    return `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;
  } else {
    return `M ${x1} ${y1} C ${x1 - controlOffset} ${y1}, ${x2 + controlOffset} ${y2}, ${x2} ${y2}`;
  }
}

function deleteConnection(connectionId) {
  const index = connections.findIndex((c) => c.id === connectionId);
  if (index !== -1) {
    pushUndo();
    connections.splice(index, 1);
    // BUG#4 FIX: renderBlocks() already calls renderConnections() internally — no double render
    renderBlocks(); // Update port states + connections
  }
}

/**
 * Disconnect all connections from a specific port (right-click on port).
 * Removes every connection where the port is either source or target.
 * @param {HTMLElement} portElement - The .port DOM element
 */
function disconnectPort(portElement) {
  const blockId = portElement.dataset.blockId;
  const portId = portElement.dataset.portId;
  const direction = portElement.dataset.direction;

  if (!blockId || !portId) return;

  // Find all connections involving this port
  const toRemove = connections.filter(c => {
    if (direction === 'output') {
      return c.source.blockId === blockId && c.source.portId === portId;
    } else {
      return c.target.blockId === blockId && c.target.portId === portId;
    }
  });

  if (toRemove.length === 0) return;

  pushUndo();
  const removeIds = new Set(toRemove.map(c => c.id));
  for (let i = connections.length - 1; i >= 0; i--) {
    if (removeIds.has(connections[i].id)) {
      connections.splice(i, 1);
    }
  }

  renderConnections();
  renderBlocks();
  console.log(`[Strategy Builder] Disconnected ${toRemove.length} connection(s) from port ${portId} on block ${blockId}`);
}

// Modal functions
function openTemplatesModal() {
  console.log('[Strategy Builder] Opening templates modal');
  const modal = document.getElementById('templatesModal');
  if (!modal) {
    console.error('[Strategy Builder] Templates modal not found!');
    return;
  }

  // Prevent any other handlers from closing it immediately
  const wasOpen = modal.classList.contains('active');
  if (wasOpen) {
    console.log('[Strategy Builder] Modal already open, skipping');
    return;
  }

  // Ensure templates are rendered before opening
  renderTemplates();

  // Update open time before opening (for overlay handler to check)
  if (window._updateTemplatesModalOpenTime) {
    window._updateTemplatesModalOpenTime();
  }

  // Open modal
  modal.classList.add('active');
  console.log('[Strategy Builder] Templates modal opened');
  console.log('[Strategy Builder] Modal classes:', modal.className);
  console.log('[Strategy Builder] Modal display:', window.getComputedStyle(modal).display);
  console.log('[Strategy Builder] Modal z-index:', window.getComputedStyle(modal).zIndex);
  console.log('[Strategy Builder] Modal visibility:', window.getComputedStyle(modal).visibility);

  // Check modal content visibility
  const modalContent = modal.querySelector('.modal');
  if (modalContent) {
    const contentStyle = window.getComputedStyle(modalContent);
    console.log('[Strategy Builder] Modal content (.modal) found');
    console.log('  - Display:', contentStyle.display);
    console.log('  - Opacity:', contentStyle.opacity);
    console.log('  - Visibility:', contentStyle.visibility);
    console.log('  - Z-index:', contentStyle.zIndex);
    console.log('  - Width:', contentStyle.width);
    console.log('  - Height:', contentStyle.height);
    console.log('  - Background:', contentStyle.backgroundColor);

    // Force visibility if needed
    if (contentStyle.display === 'none' || contentStyle.opacity === '0' || contentStyle.visibility === 'hidden') {
      console.warn('[Strategy Builder] Modal content not visible, forcing display');
      modalContent.style.display = 'flex';
      modalContent.style.flexDirection = 'column';
      modalContent.style.opacity = '1';
      modalContent.style.visibility = 'visible';
    }
  } else {
    console.error('[Strategy Builder] Modal content (.modal) NOT FOUND!');
  }

  // Verify it's still open after a moment
  setTimeout(() => {
    const stillOpen = modal.classList.contains('active');
    if (!stillOpen) {
      console.error('[Strategy Builder] Modal was closed unexpectedly! Reopening...');
      modal.classList.add('active');
    } else {
      console.log('[Strategy Builder] Modal confirmed open');
    }
  }, 100);
}

function closeTemplatesModal() {
  console.log('[Strategy Builder] Closing templates modal');
  const modal = document.getElementById('templatesModal');
  if (modal) {
    modal.classList.remove('active');
    console.log('[Strategy Builder] Templates modal closed');
  }
}

function selectTemplate(templateId) {
  console.log(`[Strategy Builder] Template selected: ${templateId}`);
  selectedTemplate = templateId;
  renderTemplates();

  // Visual feedback
  const cards = document.querySelectorAll('.template-card');
  cards.forEach(card => {
    if (card.dataset.templateId === templateId) {
      card.classList.add('selected');
      console.log(`[Strategy Builder] Template card selected: ${templateId}`);
    } else {
      card.classList.remove('selected');
    }
  });
}

function loadSelectedTemplate() {
  if (!selectedTemplate) {
    console.warn('[Strategy Builder] No template selected');
    showNotification('Выберите шаблон', 'warning');
    return;
  }

  console.log(`[Strategy Builder] Loading template: ${selectedTemplate}`);
  const template = templates.find((t) => t.id === selectedTemplate);
  if (template) {
    console.log('[Strategy Builder] Template found:', template);

    // Update strategy name
    const nameInput = document.getElementById('strategyName');
    if (nameInput) {
      nameInput.value = template.name;
      syncStrategyNameDisplay();
    }

    // Load template blocks and connections
    loadTemplateData(selectedTemplate);

    // Close modal after a short delay to ensure template is loaded
    setTimeout(() => {
      closeTemplatesModal();
      showNotification(`Шаблон "${template.name}" загружен`, 'success');
    }, 100);
  } else {
    console.error(`[Strategy Builder] Template not found: ${selectedTemplate}`);
    showNotification(`Шаблон "${selectedTemplate}" не найден`, 'error');
  }
}

// Template data with actual blocks and connections
const templateData = {
  rsi_oversold: {
    blocks: [
      {
        id: 'rsi_1',
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        icon: 'graph-up',
        x: 100,
        y: 150,
        params: { period: 14, use_cross_level: true, cross_long_level: 30, cross_short_level: 70 }
      },
      {
        id: 'sltp_1',
        type: 'static_sltp',
        category: 'exit',
        name: 'Static SL/TP',
        icon: 'shield-check',
        x: 600,
        y: 450,
        params: { take_profit_percent: 1.5, stop_loss_percent: 1.5 }
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'rsi_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_2',
        source: { blockId: 'rsi_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_3',
        source: { blockId: 'rsi_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_4',
        source: { blockId: 'rsi_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  macd_crossover: {
    blocks: [
      {
        id: 'macd_1',
        type: 'macd',
        category: 'indicator',
        name: 'MACD',
        icon: 'bar-chart',
        x: 100,
        y: 200,
        params: { fast_period: 12, slow_period: 26, signal_period: 9, source: 'close', use_macd_cross_signal: true }
      },
      {
        id: 'sltp_1',
        type: 'static_sltp',
        category: 'exit',
        name: 'Static SL/TP',
        icon: 'shield-check',
        x: 400,
        y: 350,
        params: { take_profit_percent: 2.0, stop_loss_percent: 1.5 }
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'macd_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_2',
        source: { blockId: 'macd_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_3',
        source: { blockId: 'macd_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_4',
        source: { blockId: 'macd_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  ema_crossover: {
    blocks: [
      {
        id: 'ema_fast',
        type: 'ema',
        category: 'indicator',
        name: 'EMA Fast',
        icon: 'graph-up-arrow',
        x: 100,
        y: 150,
        params: { period: 9 }
      },
      {
        id: 'ema_slow',
        type: 'ema',
        category: 'indicator',
        name: 'EMA Slow',
        icon: 'graph-up-arrow',
        x: 100,
        y: 300,
        params: { period: 21 }
      },
      {
        id: 'crossover_1',
        type: 'crossover',
        category: 'condition',
        name: 'Crossover',
        icon: 'intersect',
        x: 350,
        y: 150,
        params: {}
      },
      {
        id: 'crossunder_1',
        type: 'crossunder',
        category: 'condition',
        name: 'Crossunder',
        icon: 'intersect',
        x: 350,
        y: 350,
        params: {}
      },
      {
        id: 'sltp_1',
        type: 'static_sltp',
        category: 'exit',
        name: 'Static SL/TP',
        icon: 'shield-check',
        x: 600,
        y: 450,
        params: { take_profit_percent: 2.0, stop_loss_percent: 1.5 }
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'ema_fast', portId: 'value' },
        target: { blockId: 'crossover_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'ema_slow', portId: 'value' },
        target: { blockId: 'crossover_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'ema_fast', portId: 'value' },
        target: { blockId: 'crossunder_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'ema_slow', portId: 'value' },
        target: { blockId: 'crossunder_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_7',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_8',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  bollinger_bounce: {
    blocks: [
      {
        id: 'price_1',
        type: 'price',
        category: 'input',
        name: 'Price',
        icon: 'currency-dollar',
        x: 50,
        y: 150,
        params: {}
      },
      {
        id: 'bb_1',
        type: 'bollinger',
        category: 'indicator',
        name: 'Bollinger Bands',
        icon: 'distribute-vertical',
        x: 50,
        y: 300,
        params: { period: 20, stdDev: 2 }
      },
      {
        id: 'less_than_1',
        type: 'less_than',
        category: 'condition',
        name: 'Less Than',
        icon: 'chevron-double-down',
        x: 300,
        y: 150,
        params: {}
      },
      {
        id: 'greater_than_1',
        type: 'greater_than',
        category: 'condition',
        name: 'Greater Than',
        icon: 'chevron-double-up',
        x: 300,
        y: 350,
        params: {}
      },
      {
        id: 'sltp_1',
        type: 'static_sltp',
        category: 'exit',
        name: 'Static SL/TP',
        icon: 'shield-check',
        x: 600,
        y: 450,
        params: { take_profit_percent: 1.5, stop_loss_percent: 1.5 }
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'price_1', portId: 'close' },
        target: { blockId: 'less_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'bb_1', portId: 'lower' },
        target: { blockId: 'less_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'price_1', portId: 'close' },
        target: { blockId: 'greater_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'bb_1', portId: 'upper' },
        target: { blockId: 'greater_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'less_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'greater_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_7',
        source: { blockId: 'greater_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_8',
        source: { blockId: 'less_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  rsi_long_short: {
    blocks: [
      {
        id: 'rsi_1',
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        icon: 'graph-up',
        x: 150,
        y: 150,
        params: { period: 14, use_long_range: true, long_rsi_more: 1, long_rsi_less: 30, use_short_range: true, short_rsi_less: 100, short_rsi_more: 70 }
      },
      {
        id: 'sltp_1',
        type: 'static_sltp',
        category: 'exit',
        name: 'Static SL/TP',
        icon: 'shield-check',
        x: 650,
        y: 500,
        params: { take_profit_percent: 1.5, stop_loss_percent: 1.5 }
      }
    ],
    connections: [
      // RSI long signal → Entry Long
      {
        id: 'conn_1',
        source: { blockId: 'rsi_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      // RSI short signal → Exit Long
      {
        id: 'conn_2',
        source: { blockId: 'rsi_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      // RSI short signal → Entry Short
      {
        id: 'conn_3',
        source: { blockId: 'rsi_1', portId: 'short' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      // RSI long signal → Exit Short
      {
        id: 'conn_4',
        source: { blockId: 'rsi_1', portId: 'long' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },

  // =============================================
  // STOCHASTIC REVERSAL — %K/%D crossover at oversold/overbought
  // =============================================
  stochastic_oversold: {
    blocks: [
      { id: 'stoch_1', type: 'stochastic', category: 'indicator', name: 'Stochastic', icon: 'percent', x: 80, y: 150, params: { k_period: 14, d_period: 3, smooth: 3 } },
      { id: 'const_20', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 350, params: { value: 20 } },
      { id: 'const_80', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 450, params: { value: 80 } },
      { id: 'crossover_1', type: 'crossover', category: 'condition', name: 'K cross D up', icon: 'intersect', x: 320, y: 120, params: {} },
      { id: 'crossunder_1', type: 'crossunder', category: 'condition', name: 'K cross D down', icon: 'intersect', x: 320, y: 280, params: {} },
      { id: 'less_than_1', type: 'less_than', category: 'condition', name: 'K < 20', icon: 'chevron-double-down', x: 320, y: 420, params: {} },
      { id: 'greater_than_1', type: 'greater_than', category: 'condition', name: 'K > 80', icon: 'chevron-double-up', x: 320, y: 540, params: {} },
      { id: 'and_entry_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 170, params: {} },
      { id: 'and_entry_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 380, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 700, y: 500, params: { take_profit_percent: 1.5, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // K crossover D (bullish)
      { id: 'conn_1', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'crossover_1', portId: 'a' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'stoch_1', portId: 'd' }, target: { blockId: 'crossover_1', portId: 'b' }, type: 'data' },
      // K crossunder D (bearish)
      { id: 'conn_3', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'crossunder_1', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'stoch_1', portId: 'd' }, target: { blockId: 'crossunder_1', portId: 'b' }, type: 'data' },
      // K < 20 (oversold zone)
      { id: 'conn_5', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'less_than_1', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'const_20', portId: 'value' }, target: { blockId: 'less_than_1', portId: 'right' }, type: 'data' },
      // K > 80 (overbought zone)
      { id: 'conn_7', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'greater_than_1', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'const_80', portId: 'value' }, target: { blockId: 'greater_than_1', portId: 'right' }, type: 'data' },
      // AND: crossover + oversold → entry long
      { id: 'conn_9', source: { blockId: 'crossover_1', portId: 'result' }, target: { blockId: 'and_entry_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'less_than_1', portId: 'result' }, target: { blockId: 'and_entry_long', portId: 'b' }, type: 'condition' },
      // AND: crossunder + overbought → entry short
      { id: 'conn_11', source: { blockId: 'crossunder_1', portId: 'result' }, target: { blockId: 'and_entry_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'greater_than_1', portId: 'result' }, target: { blockId: 'and_entry_short', portId: 'b' }, type: 'condition' },
      // Strategy connections
      { id: 'conn_13', source: { blockId: 'and_entry_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_entry_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_15', source: { blockId: 'and_entry_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'and_entry_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // SUPERTREND FOLLOWER — direction flips
  // =============================================
  supertrend_follow: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 80, y: 150, params: {} },
      { id: 'st_1', type: 'supertrend', category: 'indicator', name: 'SuperTrend', icon: 'arrow-up-right-circle', x: 80, y: 320, params: { period: 10, multiplier: 3.0 } },
      { id: 'crossover_1', type: 'crossover', category: 'condition', name: 'Price cross above ST', icon: 'intersect', x: 340, y: 150, params: {} },
      { id: 'crossunder_1', type: 'crossunder', category: 'condition', name: 'Price cross below ST', icon: 'intersect', x: 340, y: 350, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 600, y: 450, params: { take_profit_percent: 2.5, stop_loss_percent: 1.5 } }
    ],
    connections: [
      { id: 'conn_1', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossover_1', portId: 'a' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'st_1', portId: 'supertrend' }, target: { blockId: 'crossover_1', portId: 'b' }, type: 'data' },
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossunder_1', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'st_1', portId: 'supertrend' }, target: { blockId: 'crossunder_1', portId: 'b' }, type: 'data' },
      { id: 'conn_5', source: { blockId: 'crossover_1', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_6', source: { blockId: 'crossunder_1', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_7', source: { blockId: 'crossunder_1', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_8', source: { blockId: 'crossover_1', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // TRIPLE EMA — EMA 9/21/55 alignment
  // =============================================
  triple_ema: {
    blocks: [
      { id: 'ema_9', type: 'ema', category: 'indicator', name: 'EMA 9', icon: 'graph-up-arrow', x: 80, y: 100, params: { period: 9 } },
      { id: 'ema_21', type: 'ema', category: 'indicator', name: 'EMA 21', icon: 'graph-up-arrow', x: 80, y: 250, params: { period: 21 } },
      { id: 'ema_55', type: 'ema', category: 'indicator', name: 'EMA 55', icon: 'graph-up-arrow', x: 80, y: 400, params: { period: 55 } },
      { id: 'crossover_fast', type: 'crossover', category: 'condition', name: 'EMA9 cross EMA21 up', icon: 'intersect', x: 320, y: 120, params: {} },
      { id: 'gt_trend', type: 'greater_than', category: 'condition', name: 'EMA21 > EMA55', icon: 'chevron-double-up', x: 320, y: 280, params: {} },
      { id: 'crossunder_fast', type: 'crossunder', category: 'condition', name: 'EMA9 cross EMA21 down', icon: 'intersect', x: 320, y: 420, params: {} },
      { id: 'lt_trend', type: 'less_than', category: 'condition', name: 'EMA21 < EMA55', icon: 'chevron-double-down', x: 320, y: 560, params: {} },
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 180, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 470, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 720, y: 500, params: { take_profit_percent: 2.0, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // EMA9 crossover EMA21
      { id: 'conn_1', source: { blockId: 'ema_9', portId: 'value' }, target: { blockId: 'crossover_fast', portId: 'a' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'ema_21', portId: 'value' }, target: { blockId: 'crossover_fast', portId: 'b' }, type: 'data' },
      // EMA21 > EMA55 (uptrend)
      { id: 'conn_3', source: { blockId: 'ema_21', portId: 'value' }, target: { blockId: 'gt_trend', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'ema_55', portId: 'value' }, target: { blockId: 'gt_trend', portId: 'right' }, type: 'data' },
      // EMA9 crossunder EMA21
      { id: 'conn_5', source: { blockId: 'ema_9', portId: 'value' }, target: { blockId: 'crossunder_fast', portId: 'a' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'ema_21', portId: 'value' }, target: { blockId: 'crossunder_fast', portId: 'b' }, type: 'data' },
      // EMA21 < EMA55 (downtrend)
      { id: 'conn_7', source: { blockId: 'ema_21', portId: 'value' }, target: { blockId: 'lt_trend', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'ema_55', portId: 'value' }, target: { blockId: 'lt_trend', portId: 'right' }, type: 'data' },
      // AND: crossover + uptrend → entry long
      { id: 'conn_9', source: { blockId: 'crossover_fast', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'gt_trend', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND: crossunder + downtrend → entry short
      { id: 'conn_11', source: { blockId: 'crossunder_fast', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'lt_trend', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_13', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_15', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // ICHIMOKU CLOUD — TK cross + price above/below cloud
  // =============================================
  ichimoku_cloud: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 80, params: {} },
      { id: 'ich_1', type: 'ichimoku', category: 'indicator', name: 'Ichimoku', icon: 'cloud', x: 60, y: 250, params: { tenkan: 9, kijun: 26, senkou_b: 52 } },
      { id: 'crossover_tk', type: 'crossover', category: 'condition', name: 'TK cross up', icon: 'intersect', x: 310, y: 80, params: {} },
      { id: 'gt_cloud', type: 'greater_than', category: 'condition', name: 'Close > SpanA', icon: 'chevron-double-up', x: 310, y: 230, params: {} },
      { id: 'crossunder_tk', type: 'crossunder', category: 'condition', name: 'TK cross down', icon: 'intersect', x: 310, y: 380, params: {} },
      { id: 'lt_cloud', type: 'less_than', category: 'condition', name: 'Close < SpanB', icon: 'chevron-double-down', x: 310, y: 520, params: {} },
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 140, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 430, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 720, y: 500, params: { take_profit_percent: 2.5, stop_loss_percent: 2.0 } }
    ],
    connections: [
      // Tenkan crossover Kijun
      { id: 'conn_1', source: { blockId: 'ich_1', portId: 'tenkan_sen' }, target: { blockId: 'crossover_tk', portId: 'a' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'ich_1', portId: 'kijun_sen' }, target: { blockId: 'crossover_tk', portId: 'b' }, type: 'data' },
      // Close > Senkou Span A (above cloud)
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_cloud', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'ich_1', portId: 'senkou_span_a' }, target: { blockId: 'gt_cloud', portId: 'right' }, type: 'data' },
      // Tenkan crossunder Kijun
      { id: 'conn_5', source: { blockId: 'ich_1', portId: 'tenkan_sen' }, target: { blockId: 'crossunder_tk', portId: 'a' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'ich_1', portId: 'kijun_sen' }, target: { blockId: 'crossunder_tk', portId: 'b' }, type: 'data' },
      // Close < Senkou Span B (below cloud)
      { id: 'conn_7', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_cloud', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'ich_1', portId: 'senkou_span_b' }, target: { blockId: 'lt_cloud', portId: 'right' }, type: 'data' },
      // AND: TK cross up + above cloud → entry long
      { id: 'conn_9', source: { blockId: 'crossover_tk', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'gt_cloud', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND: TK cross down + below cloud → entry short
      { id: 'conn_11', source: { blockId: 'crossunder_tk', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'lt_cloud', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_13', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_15', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // BREAKOUT — Price breaks above/below Donchian channel
  // =============================================
  breakout: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 80, y: 150, params: {} },
      { id: 'dc_1', type: 'donchian', category: 'indicator', name: 'Donchian 20', icon: 'distribute-vertical', x: 80, y: 320, params: { period: 20 } },
      { id: 'gt_upper', type: 'greater_than', category: 'condition', name: 'Close > Upper', icon: 'chevron-double-up', x: 340, y: 150, params: {} },
      { id: 'lt_lower', type: 'less_than', category: 'condition', name: 'Close < Lower', icon: 'chevron-double-down', x: 340, y: 350, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 600, y: 450, params: { take_profit_percent: 3.0, stop_loss_percent: 1.5 } }
    ],
    connections: [
      { id: 'conn_1', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_upper', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'dc_1', portId: 'upper' }, target: { blockId: 'gt_upper', portId: 'right' }, type: 'data' },
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_lower', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'dc_1', portId: 'lower' }, target: { blockId: 'lt_lower', portId: 'right' }, type: 'data' },
      { id: 'conn_5', source: { blockId: 'gt_upper', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_6', source: { blockId: 'lt_lower', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_7', source: { blockId: 'lt_lower', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_8', source: { blockId: 'gt_upper', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // DONCHIAN CHANNEL BREAKOUT — Classic turtle: buy 20-day high, sell 10-day low
  // =============================================
  donchian_breakout: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 100, params: {} },
      { id: 'dc_entry', type: 'donchian', category: 'indicator', name: 'Donchian Entry (20)', icon: 'distribute-vertical', x: 60, y: 270, params: { period: 20 } },
      { id: 'dc_exit', type: 'donchian', category: 'indicator', name: 'Donchian Exit (10)', icon: 'distribute-vertical', x: 60, y: 440, params: { period: 10 } },
      { id: 'gt_entry', type: 'greater_than', category: 'condition', name: 'Close > DC20 Upper', icon: 'chevron-double-up', x: 330, y: 100, params: {} },
      { id: 'lt_exit_long', type: 'less_than', category: 'condition', name: 'Close < DC10 Lower', icon: 'chevron-double-down', x: 330, y: 260, params: {} },
      { id: 'lt_entry_short', type: 'less_than', category: 'condition', name: 'Close < DC20 Lower', icon: 'chevron-double-down', x: 330, y: 400, params: {} },
      { id: 'gt_exit_short', type: 'greater_than', category: 'condition', name: 'Close > DC10 Upper', icon: 'chevron-double-up', x: 330, y: 540, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 620, y: 500, params: { take_profit_percent: 3.0, stop_loss_percent: 2.0 } }
    ],
    connections: [
      // Entry long: Close > DC20 upper
      { id: 'conn_1', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_entry', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'dc_entry', portId: 'upper' }, target: { blockId: 'gt_entry', portId: 'right' }, type: 'data' },
      // Exit long: Close < DC10 lower
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_exit_long', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'dc_exit', portId: 'lower' }, target: { blockId: 'lt_exit_long', portId: 'right' }, type: 'data' },
      // Entry short: Close < DC20 lower
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_entry_short', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'dc_entry', portId: 'lower' }, target: { blockId: 'lt_entry_short', portId: 'right' }, type: 'data' },
      // Exit short: Close > DC10 upper
      { id: 'conn_7', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_exit_short', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'dc_exit', portId: 'upper' }, target: { blockId: 'gt_exit_short', portId: 'right' }, type: 'data' },
      // Strategy
      { id: 'conn_9', source: { blockId: 'gt_entry', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'lt_exit_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_11', source: { blockId: 'lt_entry_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'gt_exit_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // VOLUME BREAKOUT — Price breakout + OBV confirmation
  // =============================================
  volume_breakout: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 100, params: {} },
      { id: 'bb_1', type: 'bollinger', category: 'indicator', name: 'Bollinger', icon: 'distribute-vertical', x: 60, y: 270, params: { period: 20, stdDev: 2 } },
      { id: 'obv_1', type: 'obv', category: 'indicator', name: 'OBV', icon: 'bar-chart-steps', x: 60, y: 440, params: {} },
      { id: 'obv_sma', type: 'sma', category: 'indicator', name: 'OBV SMA', icon: 'graph-up-arrow', x: 60, y: 580, params: { period: 20 } },
      { id: 'gt_bb', type: 'greater_than', category: 'condition', name: 'Close > BB Upper', icon: 'chevron-double-up', x: 320, y: 100, params: {} },
      { id: 'gt_obv', type: 'greater_than', category: 'condition', name: 'OBV > OBV SMA', icon: 'chevron-double-up', x: 320, y: 280, params: {} },
      { id: 'lt_bb', type: 'less_than', category: 'condition', name: 'Close < BB Lower', icon: 'chevron-double-down', x: 320, y: 420, params: {} },
      { id: 'lt_obv', type: 'less_than', category: 'condition', name: 'OBV < OBV SMA', icon: 'chevron-double-down', x: 320, y: 560, params: {} },
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 540, y: 170, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 540, y: 470, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 720, y: 520, params: { take_profit_percent: 2.5, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // Close > BB Upper
      { id: 'conn_1', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_bb', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'bb_1', portId: 'upper' }, target: { blockId: 'gt_bb', portId: 'right' }, type: 'data' },
      // OBV > OBV SMA (volume confirming)
      { id: 'conn_3', source: { blockId: 'obv_1', portId: 'value' }, target: { blockId: 'gt_obv', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'obv_sma', portId: 'value' }, target: { blockId: 'gt_obv', portId: 'right' }, type: 'data' },
      // Close < BB Lower
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_bb', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'bb_1', portId: 'lower' }, target: { blockId: 'lt_bb', portId: 'right' }, type: 'data' },
      // OBV < OBV SMA
      { id: 'conn_7', source: { blockId: 'obv_1', portId: 'value' }, target: { blockId: 'lt_obv', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'obv_sma', portId: 'value' }, target: { blockId: 'lt_obv', portId: 'right' }, type: 'data' },
      // AND long
      { id: 'conn_9', source: { blockId: 'gt_bb', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'gt_obv', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND short
      { id: 'conn_11', source: { blockId: 'lt_bb', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'lt_obv', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_13', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_15', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // SIMPLE DCA — RSI-based DCA entries with TP
  // =============================================
  simple_dca: {
    blocks: [
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 80, y: 150, params: { period: 14 } },
      { id: 'const_40', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 320, params: { value: 40 } },
      { id: 'const_60', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 440, params: { value: 60 } },
      { id: 'lt_entry', type: 'less_than', category: 'condition', name: 'RSI < 40', icon: 'chevron-double-down', x: 330, y: 180, params: {} },
      { id: 'gt_exit', type: 'greater_than', category: 'condition', name: 'RSI > 60', icon: 'chevron-double-up', x: 330, y: 380, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 600, y: 450, params: { take_profit_percent: 1.0, stop_loss_percent: 3.0 } }
    ],
    connections: [
      { id: 'conn_1', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_entry', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'const_40', portId: 'value' }, target: { blockId: 'lt_entry', portId: 'right' }, type: 'data' },
      { id: 'conn_3', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_exit', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'const_60', portId: 'value' }, target: { blockId: 'gt_exit', portId: 'right' }, type: 'data' },
      { id: 'conn_5', source: { blockId: 'lt_entry', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_6', source: { blockId: 'gt_exit', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_7', source: { blockId: 'gt_exit', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_8', source: { blockId: 'lt_entry', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // RSI DCA — RSI oversold entries with mean reversion exit
  // =============================================
  rsi_dca: {
    blocks: [
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 80, y: 150, params: { period: 14 } },
      { id: 'const_25', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 320, params: { value: 25 } },
      { id: 'const_50', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 440, params: { value: 50 } },
      { id: 'const_75', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 80, y: 560, params: { value: 75 } },
      { id: 'lt_25', type: 'less_than', category: 'condition', name: 'RSI < 25', icon: 'chevron-double-down', x: 330, y: 180, params: {} },
      { id: 'gt_50', type: 'greater_than', category: 'condition', name: 'RSI > 50', icon: 'chevron-double-up', x: 330, y: 350, params: {} },
      { id: 'gt_75', type: 'greater_than', category: 'condition', name: 'RSI > 75', icon: 'chevron-double-up', x: 330, y: 500, params: {} },
      { id: 'lt_50', type: 'less_than', category: 'condition', name: 'RSI < 50', icon: 'chevron-double-down', x: 330, y: 640, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 620, y: 550, params: { take_profit_percent: 1.5, stop_loss_percent: 3.0 } }
    ],
    connections: [
      { id: 'conn_1', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_25', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'const_25', portId: 'value' }, target: { blockId: 'lt_25', portId: 'right' }, type: 'data' },
      { id: 'conn_3', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_50', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'const_50', portId: 'value' }, target: { blockId: 'gt_50', portId: 'right' }, type: 'data' },
      { id: 'conn_5', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_75', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'const_75', portId: 'value' }, target: { blockId: 'gt_75', portId: 'right' }, type: 'data' },
      { id: 'conn_7', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_50', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'const_50', portId: 'value' }, target: { blockId: 'lt_50', portId: 'right' }, type: 'data' },
      // Entry/Exit
      { id: 'conn_9', source: { blockId: 'lt_25', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'gt_50', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_11', source: { blockId: 'gt_75', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'lt_50', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // GRID TRADING — Bollinger Band grid using upper/lower/middle
  // =============================================
  grid_trading: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 100, params: {} },
      { id: 'bb_1', type: 'bollinger', category: 'indicator', name: 'Bollinger Bands', icon: 'distribute-vertical', x: 60, y: 280, params: { period: 20, stdDev: 2 } },
      { id: 'lt_lower', type: 'less_than', category: 'condition', name: 'Close < BB Lower', icon: 'chevron-double-down', x: 320, y: 100, params: {} },
      { id: 'crossover_mid', type: 'crossover', category: 'condition', name: 'Close cross Mid up', icon: 'intersect', x: 320, y: 260, params: {} },
      { id: 'gt_upper', type: 'greater_than', category: 'condition', name: 'Close > BB Upper', icon: 'chevron-double-up', x: 320, y: 400, params: {} },
      { id: 'crossunder_mid', type: 'crossunder', category: 'condition', name: 'Close cross Mid down', icon: 'intersect', x: 320, y: 540, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 620, y: 480, params: { take_profit_percent: 1.0, stop_loss_percent: 2.0 } }
    ],
    connections: [
      // Close < BB Lower → entry long
      { id: 'conn_1', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_lower', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'bb_1', portId: 'lower' }, target: { blockId: 'lt_lower', portId: 'right' }, type: 'data' },
      // Close crossover middle → exit long
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossover_mid', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'bb_1', portId: 'middle' }, target: { blockId: 'crossover_mid', portId: 'b' }, type: 'data' },
      // Close > BB Upper → entry short
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_upper', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'bb_1', portId: 'upper' }, target: { blockId: 'gt_upper', portId: 'right' }, type: 'data' },
      // Close crossunder middle → exit short
      { id: 'conn_7', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossunder_mid', portId: 'a' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'bb_1', portId: 'middle' }, target: { blockId: 'crossunder_mid', portId: 'b' }, type: 'data' },
      // Strategy
      { id: 'conn_9', source: { blockId: 'lt_lower', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'crossover_mid', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_11', source: { blockId: 'gt_upper', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'crossunder_mid', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // MULTI-INDICATOR CONFLUENCE — RSI + MACD + EMA
  // =============================================
  multi_indicator: {
    blocks: [
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 60, y: 80, params: { period: 14 } },
      { id: 'macd_1', type: 'macd', category: 'indicator', name: 'MACD', icon: 'bar-chart', x: 60, y: 220, params: { fast_period: 12, slow_period: 26, signal_period: 9 } },
      { id: 'ema_fast', type: 'ema', category: 'indicator', name: 'EMA 9', icon: 'graph-up-arrow', x: 60, y: 380, params: { period: 9 } },
      { id: 'ema_slow', type: 'ema', category: 'indicator', name: 'EMA 21', icon: 'graph-up-arrow', x: 60, y: 500, params: { period: 21 } },
      { id: 'const_30', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 60, y: 620, params: { value: 30 } },
      { id: 'const_70', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 60, y: 720, params: { value: 70 } },
      // Conditions
      { id: 'lt_rsi', type: 'less_than', category: 'condition', name: 'RSI < 30', icon: 'chevron-double-down', x: 300, y: 80, params: {} },
      { id: 'crossover_macd', type: 'crossover', category: 'condition', name: 'MACD cross signal up', icon: 'intersect', x: 300, y: 220, params: {} },
      { id: 'gt_ema', type: 'greater_than', category: 'condition', name: 'EMA9 > EMA21', icon: 'chevron-double-up', x: 300, y: 380, params: {} },
      { id: 'gt_rsi', type: 'greater_than', category: 'condition', name: 'RSI > 70', icon: 'chevron-double-up', x: 300, y: 520, params: {} },
      { id: 'crossunder_macd', type: 'crossunder', category: 'condition', name: 'MACD cross signal down', icon: 'intersect', x: 300, y: 640, params: {} },
      { id: 'lt_ema', type: 'less_than', category: 'condition', name: 'EMA9 < EMA21', icon: 'chevron-double-down', x: 300, y: 760, params: {} },
      // Logic
      { id: 'and_rsi_macd_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 140, params: {} },
      { id: 'and_full_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 700, y: 220, params: {} },
      { id: 'and_rsi_macd_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 560, params: {} },
      { id: 'and_full_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 700, y: 640, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 880, y: 500, params: { take_profit_percent: 2.0, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // RSI < 30
      { id: 'conn_1', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'const_30', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'right' }, type: 'data' },
      // MACD crossover signal
      { id: 'conn_3', source: { blockId: 'macd_1', portId: 'macd' }, target: { blockId: 'crossover_macd', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'macd_1', portId: 'signal' }, target: { blockId: 'crossover_macd', portId: 'b' }, type: 'data' },
      // EMA9 > EMA21
      { id: 'conn_5', source: { blockId: 'ema_fast', portId: 'value' }, target: { blockId: 'gt_ema', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'ema_slow', portId: 'value' }, target: { blockId: 'gt_ema', portId: 'right' }, type: 'data' },
      // RSI > 70
      { id: 'conn_7', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'const_70', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'right' }, type: 'data' },
      // MACD crossunder signal
      { id: 'conn_9', source: { blockId: 'macd_1', portId: 'macd' }, target: { blockId: 'crossunder_macd', portId: 'a' }, type: 'data' },
      { id: 'conn_10', source: { blockId: 'macd_1', portId: 'signal' }, target: { blockId: 'crossunder_macd', portId: 'b' }, type: 'data' },
      // EMA9 < EMA21
      { id: 'conn_11', source: { blockId: 'ema_fast', portId: 'value' }, target: { blockId: 'lt_ema', portId: 'left' }, type: 'data' },
      { id: 'conn_12', source: { blockId: 'ema_slow', portId: 'value' }, target: { blockId: 'lt_ema', portId: 'right' }, type: 'data' },
      // AND: RSI oversold + MACD cross up
      { id: 'conn_13', source: { blockId: 'lt_rsi', portId: 'result' }, target: { blockId: 'and_rsi_macd_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'crossover_macd', portId: 'result' }, target: { blockId: 'and_rsi_macd_long', portId: 'b' }, type: 'condition' },
      // AND: (RSI+MACD) + EMA bullish
      { id: 'conn_15', source: { blockId: 'and_rsi_macd_long', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'gt_ema', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'b' }, type: 'condition' },
      // AND: RSI overbought + MACD cross down
      { id: 'conn_17', source: { blockId: 'gt_rsi', portId: 'result' }, target: { blockId: 'and_rsi_macd_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_18', source: { blockId: 'crossunder_macd', portId: 'result' }, target: { blockId: 'and_rsi_macd_short', portId: 'b' }, type: 'condition' },
      // AND: (RSI+MACD) + EMA bearish
      { id: 'conn_19', source: { blockId: 'and_rsi_macd_short', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_20', source: { blockId: 'lt_ema', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_21', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_22', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_23', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_24', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // DIVERGENCE HUNTER — RSI divergence via RSI slope vs price slope
  // =============================================
  divergence_hunter: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 100, params: {} },
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 60, y: 260, params: { period: 14 } },
      { id: 'const_30', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 60, y: 420, params: { value: 30 } },
      { id: 'const_70', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 60, y: 530, params: { value: 70 } },
      { id: 'ema_price', type: 'ema', category: 'indicator', name: 'EMA Price', icon: 'graph-up-arrow', x: 60, y: 640, params: { period: 14 } },
      // RSI oversold + price crossing EMA = bullish divergence signal
      { id: 'lt_rsi', type: 'less_than', category: 'condition', name: 'RSI < 30', icon: 'chevron-double-down', x: 310, y: 100, params: {} },
      { id: 'crossover_price', type: 'crossover', category: 'condition', name: 'Close cross EMA up', icon: 'intersect', x: 310, y: 260, params: {} },
      { id: 'gt_rsi', type: 'greater_than', category: 'condition', name: 'RSI > 70', icon: 'chevron-double-up', x: 310, y: 420, params: {} },
      { id: 'crossunder_price', type: 'crossunder', category: 'condition', name: 'Close cross EMA down', icon: 'intersect', x: 310, y: 560, params: {} },
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 160, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 530, y: 470, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 720, y: 500, params: { take_profit_percent: 2.0, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // RSI < 30
      { id: 'conn_1', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'const_30', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'right' }, type: 'data' },
      // Price crossover EMA
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossover_price', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'ema_price', portId: 'value' }, target: { blockId: 'crossover_price', portId: 'b' }, type: 'data' },
      // RSI > 70
      { id: 'conn_5', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'const_70', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'right' }, type: 'data' },
      // Price crossunder EMA
      { id: 'conn_7', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossunder_price', portId: 'a' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'ema_price', portId: 'value' }, target: { blockId: 'crossunder_price', portId: 'b' }, type: 'data' },
      // AND long: RSI oversold + price bounce
      { id: 'conn_9', source: { blockId: 'lt_rsi', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'crossover_price', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND short: RSI overbought + price rejection
      { id: 'conn_11', source: { blockId: 'gt_rsi', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'crossunder_price', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_13', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_15', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // SMART MONEY CONCEPT — OBV + RSI + SuperTrend confluence
  // =============================================
  smart_money: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 40, y: 80, params: {} },
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 40, y: 220, params: { period: 14 } },
      { id: 'obv_1', type: 'obv', category: 'indicator', name: 'OBV', icon: 'bar-chart-steps', x: 40, y: 370, params: {} },
      { id: 'obv_ema', type: 'ema', category: 'indicator', name: 'OBV EMA', icon: 'graph-up-arrow', x: 40, y: 510, params: { period: 21 } },
      { id: 'st_1', type: 'supertrend', category: 'indicator', name: 'SuperTrend', icon: 'arrow-up-right-circle', x: 40, y: 650, params: { period: 10, multiplier: 3.0 } },
      { id: 'const_40', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 40, y: 780, params: { value: 40 } },
      { id: 'const_60', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 40, y: 870, params: { value: 60 } },
      // Conditions
      { id: 'lt_rsi', type: 'less_than', category: 'condition', name: 'RSI < 40', icon: 'chevron-double-down', x: 280, y: 80, params: {} },
      { id: 'gt_obv', type: 'greater_than', category: 'condition', name: 'OBV > OBV EMA', icon: 'chevron-double-up', x: 280, y: 220, params: {} },
      { id: 'gt_st', type: 'greater_than', category: 'condition', name: 'Close > ST', icon: 'chevron-double-up', x: 280, y: 370, params: {} },
      { id: 'gt_rsi', type: 'greater_than', category: 'condition', name: 'RSI > 60', icon: 'chevron-double-up', x: 280, y: 510, params: {} },
      { id: 'lt_obv', type: 'less_than', category: 'condition', name: 'OBV < OBV EMA', icon: 'chevron-double-down', x: 280, y: 650, params: {} },
      { id: 'lt_st', type: 'less_than', category: 'condition', name: 'Close < ST', icon: 'chevron-double-down', x: 280, y: 780, params: {} },
      // Logic
      { id: 'and_rsi_obv_l', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 500, y: 140, params: {} },
      { id: 'and_full_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 680, y: 240, params: {} },
      { id: 'and_rsi_obv_s', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 500, y: 560, params: {} },
      { id: 'and_full_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 680, y: 660, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 860, y: 500, params: { take_profit_percent: 2.5, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // RSI < 40
      { id: 'conn_1', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'const_40', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'right' }, type: 'data' },
      // OBV > OBV EMA
      { id: 'conn_3', source: { blockId: 'obv_1', portId: 'value' }, target: { blockId: 'gt_obv', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'obv_ema', portId: 'value' }, target: { blockId: 'gt_obv', portId: 'right' }, type: 'data' },
      // Close > SuperTrend
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_st', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'st_1', portId: 'supertrend' }, target: { blockId: 'gt_st', portId: 'right' }, type: 'data' },
      // RSI > 60
      { id: 'conn_7', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'const_60', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'right' }, type: 'data' },
      // OBV < OBV EMA
      { id: 'conn_9', source: { blockId: 'obv_1', portId: 'value' }, target: { blockId: 'lt_obv', portId: 'left' }, type: 'data' },
      { id: 'conn_10', source: { blockId: 'obv_ema', portId: 'value' }, target: { blockId: 'lt_obv', portId: 'right' }, type: 'data' },
      // Close < SuperTrend
      { id: 'conn_11', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_st', portId: 'left' }, type: 'data' },
      { id: 'conn_12', source: { blockId: 'st_1', portId: 'supertrend' }, target: { blockId: 'lt_st', portId: 'right' }, type: 'data' },
      // AND: RSI low + OBV rising
      { id: 'conn_13', source: { blockId: 'lt_rsi', portId: 'result' }, target: { blockId: 'and_rsi_obv_l', portId: 'a' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'gt_obv', portId: 'result' }, target: { blockId: 'and_rsi_obv_l', portId: 'b' }, type: 'condition' },
      // AND: (RSI+OBV) + SuperTrend bullish
      { id: 'conn_15', source: { blockId: 'and_rsi_obv_l', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'gt_st', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'b' }, type: 'condition' },
      // AND: RSI high + OBV falling
      { id: 'conn_17', source: { blockId: 'gt_rsi', portId: 'result' }, target: { blockId: 'and_rsi_obv_s', portId: 'a' }, type: 'condition' },
      { id: 'conn_18', source: { blockId: 'lt_obv', portId: 'result' }, target: { blockId: 'and_rsi_obv_s', portId: 'b' }, type: 'condition' },
      // AND: (RSI+OBV) + SuperTrend bearish
      { id: 'conn_19', source: { blockId: 'and_rsi_obv_s', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_20', source: { blockId: 'lt_st', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_21', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_22', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_23', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_24', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // SCALPING PRO — EMA + RSI + Stochastic quick entries
  // =============================================
  scalping_pro: {
    blocks: [
      { id: 'ema_5', type: 'ema', category: 'indicator', name: 'EMA 5', icon: 'graph-up-arrow', x: 50, y: 80, params: { period: 5 } },
      { id: 'ema_13', type: 'ema', category: 'indicator', name: 'EMA 13', icon: 'graph-up-arrow', x: 50, y: 210, params: { period: 13 } },
      { id: 'rsi_1', type: 'rsi', category: 'indicator', name: 'RSI', icon: 'graph-up', x: 50, y: 350, params: { period: 7, overbought: 70, oversold: 30 } },
      { id: 'stoch_1', type: 'stochastic', category: 'indicator', name: 'Stochastic', icon: 'percent', x: 50, y: 500, params: { k_period: 5, d_period: 3, smooth: 3 } },
      { id: 'const_30', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 50, y: 640, params: { value: 30 } },
      { id: 'const_70', type: 'constant', category: 'input', name: 'Constant', icon: 'hash', x: 50, y: 730, params: { value: 70 } },
      // Conditions
      { id: 'crossover_ema', type: 'crossover', category: 'condition', name: 'EMA5 cross EMA13 up', icon: 'intersect', x: 290, y: 80, params: {} },
      { id: 'lt_rsi', type: 'less_than', category: 'condition', name: 'RSI < 30', icon: 'chevron-double-down', x: 290, y: 230, params: {} },
      { id: 'crossover_stoch', type: 'crossover', category: 'condition', name: 'K cross D up', icon: 'intersect', x: 290, y: 370, params: {} },
      { id: 'crossunder_ema', type: 'crossunder', category: 'condition', name: 'EMA5 cross EMA13 dn', icon: 'intersect', x: 290, y: 510, params: {} },
      { id: 'gt_rsi', type: 'greater_than', category: 'condition', name: 'RSI > 70', icon: 'chevron-double-up', x: 290, y: 650, params: {} },
      { id: 'crossunder_stoch', type: 'crossunder', category: 'condition', name: 'K cross D down', icon: 'intersect', x: 290, y: 770, params: {} },
      // Logic
      { id: 'and_ema_rsi_l', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 500, y: 140, params: {} },
      { id: 'and_full_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 680, y: 220, params: {} },
      { id: 'and_ema_rsi_s', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 500, y: 560, params: {} },
      { id: 'and_full_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 680, y: 650, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 860, y: 450, params: { take_profit_percent: 0.8, stop_loss_percent: 0.5 } }
    ],
    connections: [
      // EMA5 crossover EMA13
      { id: 'conn_1', source: { blockId: 'ema_5', portId: 'value' }, target: { blockId: 'crossover_ema', portId: 'a' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'ema_13', portId: 'value' }, target: { blockId: 'crossover_ema', portId: 'b' }, type: 'data' },
      // RSI < 30
      { id: 'conn_3', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'const_30', portId: 'value' }, target: { blockId: 'lt_rsi', portId: 'right' }, type: 'data' },
      // Stochastic K crossover D
      { id: 'conn_5', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'crossover_stoch', portId: 'a' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'stoch_1', portId: 'd' }, target: { blockId: 'crossover_stoch', portId: 'b' }, type: 'data' },
      // EMA5 crossunder EMA13
      { id: 'conn_7', source: { blockId: 'ema_5', portId: 'value' }, target: { blockId: 'crossunder_ema', portId: 'a' }, type: 'data' },
      { id: 'conn_8', source: { blockId: 'ema_13', portId: 'value' }, target: { blockId: 'crossunder_ema', portId: 'b' }, type: 'data' },
      // RSI > 70
      { id: 'conn_9', source: { blockId: 'rsi_1', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'left' }, type: 'data' },
      { id: 'conn_10', source: { blockId: 'const_70', portId: 'value' }, target: { blockId: 'gt_rsi', portId: 'right' }, type: 'data' },
      // Stochastic K crossunder D
      { id: 'conn_11', source: { blockId: 'stoch_1', portId: 'k' }, target: { blockId: 'crossunder_stoch', portId: 'a' }, type: 'data' },
      { id: 'conn_12', source: { blockId: 'stoch_1', portId: 'd' }, target: { blockId: 'crossunder_stoch', portId: 'b' }, type: 'data' },
      // AND: EMA cross + RSI oversold
      { id: 'conn_13', source: { blockId: 'crossover_ema', portId: 'result' }, target: { blockId: 'and_ema_rsi_l', portId: 'a' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'lt_rsi', portId: 'result' }, target: { blockId: 'and_ema_rsi_l', portId: 'b' }, type: 'condition' },
      // AND: (EMA+RSI) + Stoch bullish
      { id: 'conn_15', source: { blockId: 'and_ema_rsi_l', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_16', source: { blockId: 'crossover_stoch', portId: 'result' }, target: { blockId: 'and_full_long', portId: 'b' }, type: 'condition' },
      // AND: EMA cross down + RSI overbought
      { id: 'conn_17', source: { blockId: 'crossunder_ema', portId: 'result' }, target: { blockId: 'and_ema_rsi_s', portId: 'a' }, type: 'condition' },
      { id: 'conn_18', source: { blockId: 'gt_rsi', portId: 'result' }, target: { blockId: 'and_ema_rsi_s', portId: 'b' }, type: 'condition' },
      // AND: (EMA+RSI) + Stoch bearish
      { id: 'conn_19', source: { blockId: 'and_ema_rsi_s', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_20', source: { blockId: 'crossunder_stoch', portId: 'result' }, target: { blockId: 'and_full_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_21', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_22', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_23', source: { blockId: 'and_full_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_24', source: { blockId: 'and_full_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // ATR VOLATILITY BREAKOUT — ATR threshold + price break
  // =============================================
  atr_breakout: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 60, y: 100, params: {} },
      { id: 'atr_1', type: 'atr', category: 'indicator', name: 'ATR', icon: 'arrows-fullscreen', x: 60, y: 260, params: { period: 14 } },
      { id: 'sma_atr', type: 'sma', category: 'indicator', name: 'ATR SMA', icon: 'graph-up-arrow', x: 60, y: 400, params: { period: 20 } },
      { id: 'ema_1', type: 'ema', category: 'indicator', name: 'EMA 20', icon: 'graph-up-arrow', x: 60, y: 540, params: { period: 20 } },
      // ATR > ATR SMA (volatility expanding)
      { id: 'gt_atr', type: 'greater_than', category: 'condition', name: 'ATR > ATR SMA', icon: 'chevron-double-up', x: 310, y: 100, params: {} },
      // Price > EMA (bullish)
      { id: 'gt_ema', type: 'greater_than', category: 'condition', name: 'Close > EMA', icon: 'chevron-double-up', x: 310, y: 260, params: {} },
      // Price < EMA (bearish)
      { id: 'lt_ema', type: 'less_than', category: 'condition', name: 'Close < EMA', icon: 'chevron-double-down', x: 310, y: 420, params: {} },
      // Logic
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 160, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 380, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 700, y: 460, params: { take_profit_percent: 3.0, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // ATR > ATR SMA
      { id: 'conn_1', source: { blockId: 'atr_1', portId: 'value' }, target: { blockId: 'gt_atr', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'sma_atr', portId: 'value' }, target: { blockId: 'gt_atr', portId: 'right' }, type: 'data' },
      // Close > EMA
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'gt_ema', portId: 'left' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'ema_1', portId: 'value' }, target: { blockId: 'gt_ema', portId: 'right' }, type: 'data' },
      // Close < EMA
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'lt_ema', portId: 'left' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'ema_1', portId: 'value' }, target: { blockId: 'lt_ema', portId: 'right' }, type: 'data' },
      // AND: volatility expanding + bullish
      { id: 'conn_7', source: { blockId: 'gt_atr', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_8', source: { blockId: 'gt_ema', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND: volatility expanding + bearish
      { id: 'conn_9', source: { blockId: 'gt_atr', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'lt_ema', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_11', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_13', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  },

  // =============================================
  // BOLLINGER SQUEEZE — BB width contraction then breakout
  // =============================================
  bb_squeeze: {
    blocks: [
      { id: 'price_1', type: 'price', category: 'input', name: 'Price', icon: 'currency-dollar', x: 50, y: 80, params: {} },
      { id: 'bb_1', type: 'bollinger', category: 'indicator', name: 'Bollinger', icon: 'distribute-vertical', x: 50, y: 240, params: { period: 20, stdDev: 2 } },
      { id: 'kc_1', type: 'keltner', category: 'indicator', name: 'Keltner', icon: 'distribute-vertical', x: 50, y: 410, params: { period: 20, multiplier: 1.5 } },
      // BB upper < KC upper = squeeze (BB inside KC)
      { id: 'lt_squeeze', type: 'less_than', category: 'condition', name: 'BB Up < KC Up', icon: 'chevron-double-down', x: 300, y: 80, params: {} },
      // Price breaks above BB upper after squeeze = bullish
      { id: 'crossover_bb', type: 'crossover', category: 'condition', name: 'Close cross BB Up', icon: 'intersect', x: 300, y: 240, params: {} },
      // Price breaks below BB lower after squeeze = bearish
      { id: 'crossunder_bb', type: 'crossunder', category: 'condition', name: 'Close cross BB Lo', icon: 'intersect', x: 300, y: 400, params: {} },
      // Logic
      { id: 'and_long', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 140, params: {} },
      { id: 'and_short', type: 'and', category: 'logic', name: 'AND', icon: 'diagram-3', x: 520, y: 350, params: {} },
      { id: 'sltp_1', type: 'static_sltp', category: 'exit', name: 'Static SL/TP', icon: 'shield-check', x: 700, y: 430, params: { take_profit_percent: 2.5, stop_loss_percent: 1.5 } }
    ],
    connections: [
      // BB upper < KC upper (squeeze active)
      { id: 'conn_1', source: { blockId: 'bb_1', portId: 'upper' }, target: { blockId: 'lt_squeeze', portId: 'left' }, type: 'data' },
      { id: 'conn_2', source: { blockId: 'kc_1', portId: 'upper' }, target: { blockId: 'lt_squeeze', portId: 'right' }, type: 'data' },
      // Close crossover BB upper
      { id: 'conn_3', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossover_bb', portId: 'a' }, type: 'data' },
      { id: 'conn_4', source: { blockId: 'bb_1', portId: 'upper' }, target: { blockId: 'crossover_bb', portId: 'b' }, type: 'data' },
      // Close crossunder BB lower
      { id: 'conn_5', source: { blockId: 'price_1', portId: 'close' }, target: { blockId: 'crossunder_bb', portId: 'a' }, type: 'data' },
      { id: 'conn_6', source: { blockId: 'bb_1', portId: 'lower' }, target: { blockId: 'crossunder_bb', portId: 'b' }, type: 'data' },
      // AND: squeeze + bullish breakout
      { id: 'conn_7', source: { blockId: 'lt_squeeze', portId: 'result' }, target: { blockId: 'and_long', portId: 'a' }, type: 'condition' },
      { id: 'conn_8', source: { blockId: 'crossover_bb', portId: 'result' }, target: { blockId: 'and_long', portId: 'b' }, type: 'condition' },
      // AND: squeeze + bearish breakout
      { id: 'conn_9', source: { blockId: 'lt_squeeze', portId: 'result' }, target: { blockId: 'and_short', portId: 'a' }, type: 'condition' },
      { id: 'conn_10', source: { blockId: 'crossunder_bb', portId: 'result' }, target: { blockId: 'and_short', portId: 'b' }, type: 'condition' },
      // Strategy
      { id: 'conn_11', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_long' }, type: 'condition' },
      { id: 'conn_12', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_long' }, type: 'condition' },
      { id: 'conn_13', source: { blockId: 'and_short', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'entry_short' }, type: 'condition' },
      { id: 'conn_14', source: { blockId: 'and_long', portId: 'result' }, target: { blockId: 'main_strategy', portId: 'exit_short' }, type: 'condition' }
    ]
  }
};

function loadTemplateData(templateId) {
  console.log(`[Strategy Builder] Loading template: ${templateId}`);
  const data = templateData[templateId];
  if (!data) {
    console.error(`[Strategy Builder] Template data not found for: ${templateId}`);
    showNotification(`Шаблон "${templateId}" не найден`, 'error');
    return;
  }

  console.log('[Strategy Builder] Template data found:', data);
  console.log(`[Strategy Builder] Blocks: ${data.blocks.length}, Connections: ${data.connections.length}`);

  pushUndo();

  // Keep main strategy node, clear others
  const mainNode = strategyBlocks.find((b) => b.isMain);
  strategyBlocks = mainNode ? [mainNode] : [];

  // Position main strategy node on the right side
  if (mainNode) {
    mainNode.x = 600;
    mainNode.y = 250;
  }

  // Clear connections
  connections.length = 0;

  // Add template blocks
  data.blocks.forEach((block) => {
    const newBlock = { ...block };
    // Don't modify IDs - they are used in connections
    // Only ensure main_strategy is not duplicated
    if (newBlock.id === 'main_strategy' || newBlock.isMain) {
      console.log('[Strategy Builder] Skipping main_strategy block - already exists');
      return; // Skip main strategy node - it already exists
    }
    strategyBlocks.push(newBlock);
    console.log(`[Strategy Builder] Added block: ${newBlock.id} (${newBlock.type})`);
  });

  console.log(`[Strategy Builder] Added ${data.blocks.length} blocks`);

  // Add template connections
  data.connections.forEach((conn) => {
    // Map template block IDs to actual block IDs
    const sourceBlock = strategyBlocks.find((b) =>
      b.id.startsWith(conn.source.blockId) || b.id === conn.source.blockId
    );

    // Special handling for main_strategy node
    let targetBlock;
    if (conn.target.blockId === 'main_strategy') {
      targetBlock = strategyBlocks.find((b) => b.isMain);
    } else {
      targetBlock = strategyBlocks.find((b) =>
        b.id.startsWith(conn.target.blockId) || b.id === conn.target.blockId
      );
    }

    if (sourceBlock && targetBlock) {
      const newConn = {
        id: `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        source: {
          blockId: sourceBlock.id,
          portId: conn.source.portId
        },
        target: {
          blockId: targetBlock.id,
          portId: conn.target.portId
        },
        type: conn.type
      };
      connections.push(newConn);
      console.log(`[Strategy Builder] Connection added: ${sourceBlock.id}.${conn.source.portId} -> ${targetBlock.id}.${conn.target.portId}`);
    } else {
      console.warn('[Strategy Builder] Connection skipped - blocks not found:', {
        source: conn.source.blockId,
        target: conn.target.blockId,
        sourceFound: !!sourceBlock,
        targetFound: !!targetBlock,
        allBlocks: strategyBlocks.map(b => ({ id: b.id, isMain: b.isMain }))
      });
    }
  });

  // Auto-inject SL/TP connection if template has an exit block (sltp_1, trailing_1, etc.)
  const exitBlock = strategyBlocks.find(b =>
    b.id === 'sltp_1' || b.category === 'exit'
  );
  const mainBlock = strategyBlocks.find(b => b.isMain);
  if (exitBlock && mainBlock) {
    const hasConfigConn = connections.some(c =>
      c.source.blockId === exitBlock.id && c.target.portId === 'sl_tp'
    );
    if (!hasConfigConn) {
      connections.push({
        id: `conn_sltp_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        source: { blockId: exitBlock.id, portId: 'config' },
        target: { blockId: mainBlock.id, portId: 'sl_tp' },
        type: 'config'
      });
    }
  }

  // Re-render — BUG#4 FIX: renderBlocks() calls renderConnections() internally
  renderBlocks();
  selectedBlockId = null;
  renderBlockProperties();

  showNotification(`Шаблон "${templateId}" загружен`, 'success');
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
      renderBlocks();
      dispatchBlocksChanged();
      closeTemplatesModal();
      showNotification(`Импортировано: ${blocks.length} блоков`, 'success');
    } catch (err) {
      showNotification(`Ошибка импорта: ${err.message}`, 'error');
    }
  };
  reader.readAsText(file);
}

// Undo/Redo helpers
function getStateSnapshot() {
  return {
    blocks: JSON.parse(JSON.stringify(strategyBlocks)),
    connections: JSON.parse(JSON.stringify(connections))
  };
}

function restoreStateSnapshot(snapshot) {
  if (!snapshot?.blocks) return;
  strategyBlocks.length = 0;
  strategyBlocks.push(...snapshot.blocks);
  connections.length = 0;
  connections.push(...(snapshot.connections || []));
  if (selectedBlockId && !strategyBlocks.some((b) => b.id === selectedBlockId)) {
    selectedBlockId = null;
  }
  // Reset autosave payload so the restored state gets saved to localStorage
  lastAutoSavePayload = null;
  renderBlocks(); // renderBlocks calls renderConnections() internally — BUG#4 FIX: no extra call
  renderBlockProperties();
  dispatchBlocksChanged();
  // Re-validate if the validation panel is currently visible (BUG#11)
  const vp = document.querySelector('.validation-panel');
  if (vp && vp.classList.contains('visible')) {
    validateStrategy().catch((err) => console.warn('[Strategy Builder] Re-validate error:', err));
  }
}

function pushUndo() {
  const snapshot = getStateSnapshot();
  if (undoStack.length >= MAX_UNDO_HISTORY) undoStack.shift();
  undoStack.push(snapshot);
  redoStack.length = 0;
  updateUndoRedoButtons();
}

function undo() {
  if (undoStack.length === 0) return;
  redoStack.push(getStateSnapshot());
  const prev = undoStack.pop();
  restoreStateSnapshot(prev);
  updateUndoRedoButtons();
  showNotification(`Отмена (осталось: ${undoStack.length})`, 'info');
}

function redo() {
  if (redoStack.length === 0) return;
  undoStack.push(getStateSnapshot());
  const next = redoStack.pop();
  restoreStateSnapshot(next);
  updateUndoRedoButtons();
  showNotification(`Повтор (осталось: ${redoStack.length})`, 'info');
}

/**
 * Update undo/redo button states and tooltips
 */
function updateUndoRedoButtons() {
  const undoBtn = document.querySelector('button[onclick="undo()"]');
  const redoBtn = document.querySelector('button[onclick="redo()"]');

  if (undoBtn) {
    undoBtn.disabled = undoStack.length === 0;
    undoBtn.title = undoStack.length > 0
      ? `Отмена (${undoStack.length} шагов)`
      : 'Отмена (нет действий)';
    undoBtn.classList.toggle('btn-disabled', undoStack.length === 0);
  }

  if (redoBtn) {
    redoBtn.disabled = redoStack.length === 0;
    redoBtn.title = redoStack.length > 0
      ? `Повтор (${redoStack.length} шагов)`
      : 'Повтор (нет действий)';
    redoBtn.classList.toggle('btn-disabled', redoStack.length === 0);
  }
}

// Toolbar functions (called from HTML buttons)

function deleteSelected() {
  if (selectedBlockId) {
    const block = strategyBlocks.find((b) => b.id === selectedBlockId);
    if (block && block.isMain) {
      console.log('Cannot delete main Strategy node');
      return;
    }
    pushUndo();

    // Remove connections involving this block
    const connectionsToRemove = connections.filter(
      (c) =>
        c.source.blockId === selectedBlockId ||
        c.target.blockId === selectedBlockId
    );
    connectionsToRemove.forEach((c) => {
      const idx = connections.indexOf(c);
      if (idx !== -1) connections.splice(idx, 1);
    });

    strategyBlocks = strategyBlocks.filter((b) => b.id !== selectedBlockId);
    selectedBlockId = null;
    renderBlocks();
    renderBlockProperties();
  }
}

function duplicateSelected() {
  if (selectedBlockId) {
    const block = strategyBlocks.find((b) => b.id === selectedBlockId);
    if (block && !block.isMain) {
      pushUndo();
      const newBlock = {
        ...block,
        id: `block_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        x: block.x + 30,
        y: block.y + 30,
        isMain: false,
        params: { ...block.params }
      };
      strategyBlocks.push(newBlock);
      renderBlocks();
      selectBlock(newBlock.id);
    }
  }
}

function alignBlocks(direction) {
  console.log(`Align ${direction}`);
}

function autoLayout() {
  console.log('Auto layout');
}

function fitToScreen() {
  resetZoom();
}

function zoomIn() {
  zoom = Math.min(zoom + 0.1, 2);
  updateZoom();
}

function zoomOut() {
  zoom = Math.max(zoom - 0.1, 0.5);
  updateZoom();
}

function resetZoom() {
  zoom = 1;
  updateZoom();
}

function updateZoom() {
  document.getElementById('zoomLevel').textContent =
    `${Math.round(zoom * 100)}%`;
  document.getElementById('blocksContainer').style.transform = `scale(${zoom})`;
  document.getElementById('blocksContainer').style.transformOrigin = '0 0';
}

// =============================================
// EXIT BLOCK TYPES (standalone — backend reads from builder_blocks, no connections needed)
// =============================================
const EXIT_BLOCK_TYPES = new Set([
  'static_sltp', 'trailing_stop_exit', 'atr_exit',
  'multi_tp_exit',
  'tp_percent', 'sl_percent',
  'rsi_close', 'stoch_close', 'channel_close', 'ma_close',
  'psar_close', 'time_bars_close'
]);

/**
 * Quick 3-part validation for pre-backtest check.
 * Returns { valid, errors[], warnings[] } without updating UI panels.
 *
 * Part 1: Parameters (symbol, dates, capital)
 * Part 2: Entry conditions (connections to entry_long/entry_short)
 * Part 3: Exit conditions (exit blocks OR connections to exit_long/exit_short)
 */
function validateStrategyCompleteness() {
  const result = { valid: true, errors: [], warnings: [] };

  const mainNode = strategyBlocks.find((b) => b.isMain);
  if (!mainNode) {
    result.valid = false;
    result.errors.push('Main strategy node is missing');
    return result;
  }

  // Part 1: Parameters
  const symbol = document.getElementById('backtestSymbol')?.value?.trim();
  const startDate = document.getElementById('backtestStartDate')?.value?.trim();
  const endDate = document.getElementById('backtestEndDate')?.value?.trim();
  const capital = parseFloat(document.getElementById('backtestCapital')?.value);
  if (!symbol) { result.valid = false; result.errors.push('⚙️ Параметры: не выбран Symbol'); }
  if (!startDate || !endDate) { result.valid = false; result.errors.push('⚙️ Параметры: не заданы даты'); }
  if (startDate && endDate && startDate >= endDate) {
    result.valid = false;
    result.errors.push('⚙️ Параметры: Start Date должна быть раньше End Date');
  }
  if (startDate && endDate && startDate < endDate) {
    const diffMs = new Date(endDate) - new Date(startDate);
    const diffYears = diffMs / (365.25 * 24 * 60 * 60 * 1000);
    if (diffYears > 10) {
      result.warnings.push('⚙️ Параметры: диапазон дат > 10 лет — бэктест может быть очень долгим');
    }
  }
  if (!capital || capital <= 0) { result.valid = false; result.errors.push('⚙️ Параметры: Capital должен быть > 0'); }

  // Part 2: Entry conditions
  const hasEntryLong = connections.some((c) =>
    c.target.blockId === mainNode.id && c.target.portId === 'entry_long'
  );
  const hasEntryShort = connections.some((c) =>
    c.target.blockId === mainNode.id && c.target.portId === 'entry_short'
  );
  if (!hasEntryLong && !hasEntryShort) {
    result.valid = false;
    result.errors.push('🟢 Вход: нет условий входа (подключите сигналы к Entry Long или Entry Short)');
  }

  // Part 3: Exit conditions
  const hasExitBlocks = strategyBlocks.some((b) =>
    !b.isMain && EXIT_BLOCK_TYPES.has(b.type)
  );
  const hasExitSignals = connections.some((c) =>
    c.target.blockId === mainNode.id &&
    (c.target.portId === 'exit_long' || c.target.portId === 'exit_short')
  );
  if (!hasExitBlocks && !hasExitSignals) {
    result.valid = false;
    result.errors.push('🔴 Выход: нет условий выхода (добавьте блок SL/TP или подключите сигналы к Exit Long/Exit Short)');
  } else if (!hasExitBlocks) {
    result.warnings.push('🔴 Выход: нет блока SL/TP — нет защиты стоп-лоссом');
  }

  return result;
}

// Strategy actions
async function validateStrategy() {
  try {
    console.log('[Strategy Builder] validateStrategy called');
    console.log('[Strategy Builder] Current blocks:', strategyBlocks.length);
    console.log('[Strategy Builder] Current connections:', connections.length);

    showNotification('Валидация стратегии...', 'info');

    const result = {
      valid: true,
      errors: [],
      warnings: []
    };

    // =============================================
    // PART 0: BASIC STRUCTURE
    // =============================================

    // Check for blocks
    if (strategyBlocks.length === 0) {
      result.valid = false;
      result.errors.push('Strategy has no blocks');
    }

    // Check for main strategy node
    const mainNode = strategyBlocks.find((b) => b.isMain);
    if (!mainNode) {
      result.valid = false;
      result.errors.push('Main strategy node is missing');
    }

    // =============================================
    // PART 1: PARAMETERS (Properties panel)
    // =============================================
    const symbol = document.getElementById('backtestSymbol')?.value?.trim();
    const startDate = document.getElementById('backtestStartDate')?.value?.trim();
    const endDate = document.getElementById('backtestEndDate')?.value?.trim();
    const capital = parseFloat(document.getElementById('backtestCapital')?.value);

    if (!symbol) {
      result.valid = false;
      result.errors.push('⚙️ Parameters: Symbol not selected');
    }
    if (!startDate || !endDate) {
      result.valid = false;
      result.errors.push('⚙️ Parameters: Start/End date not set');
    }
    if (!capital || capital <= 0) {
      result.valid = false;
      result.errors.push('⚙️ Parameters: Initial capital must be > 0');
    }

    // =============================================
    // PART 2: ENTRY CONDITIONS
    // =============================================
    if (mainNode) {
      const entryLongConns = connections.filter((c) =>
        c.target.blockId === mainNode.id && c.target.portId === 'entry_long'
      );
      const entryShortConns = connections.filter((c) =>
        c.target.blockId === mainNode.id && c.target.portId === 'entry_short'
      );

      const hasEntryLong = entryLongConns.length > 0;
      const hasEntryShort = entryShortConns.length > 0;

      if (!hasEntryLong && !hasEntryShort) {
        result.valid = false;
        result.errors.push('🟢 Entry: No entry conditions connected (connect signals to Entry Long or Entry Short)');
      } else {
        // Check that connected sources are condition/logic blocks OR indicators with signal ports (long/short)
        const allEntryConns = [...entryLongConns, ...entryShortConns];
        const hasConditionSignals = allEntryConns.some((c) => {
          const sourceBlock = strategyBlocks.find((b) => b.id === c.source.blockId);
          if (!sourceBlock) return false;
          // Direct condition/logic blocks
          if (sourceBlock.category === 'condition' || sourceBlock.category === 'logic') return true;
          if (['less_than', 'greater_than', 'crossover', 'crossunder', 'equals', 'between', 'and', 'or', 'not'].includes(sourceBlock.type)) return true;
          // Indicator blocks with condition-type output ports (e.g. RSI long/short, MACD long/short)
          const sourcePortId = c.source.portId;
          const portDef = getBlockPorts(sourceBlock.type, sourceBlock.category);
          if (portDef && portDef.outputs) {
            const port = portDef.outputs.find((p) => p.id === sourcePortId);
            if (port && port.type === 'condition') return true;
          }
          return false;
        });
        if (!hasConditionSignals) {
          result.warnings.push('🟢 Entry: Entry ports connected but no condition blocks detected');
        }

        // Info about which entries are connected (only warn if direction is "both")
        const direction = document.getElementById('builderDirection')?.value || 'both';
        if (hasEntryLong && !hasEntryShort && direction === 'both') {
          result.warnings.push('🟢 Entry: Only Long entries — consider adding Short for "both" direction');
        } else if (!hasEntryLong && hasEntryShort && direction === 'both') {
          result.warnings.push('🟢 Entry: Only Short entries — consider adding Long for "both" direction');
        }
      }
    }

    // =============================================
    // PART 3: EXIT CONDITIONS
    // =============================================
    // Check for exit blocks (standalone — backend reads them from builder_blocks)
    const exitBlocks = strategyBlocks.filter((b) =>
      !b.isMain && EXIT_BLOCK_TYPES.has(b.type)
    );
    const hasExitBlocks = exitBlocks.length > 0;

    // Check for signal-based exits (connections to exit_long/exit_short)
    let hasExitSignals = false;
    if (mainNode) {
      const exitLongConns = connections.filter((c) =>
        c.target.blockId === mainNode.id && c.target.portId === 'exit_long'
      );
      const exitShortConns = connections.filter((c) =>
        c.target.blockId === mainNode.id && c.target.portId === 'exit_short'
      );
      hasExitSignals = exitLongConns.length > 0 || exitShortConns.length > 0;
    }

    if (!hasExitBlocks && !hasExitSignals) {
      result.valid = false;
      result.errors.push('🔴 Exit: No exit conditions (add SL/TP block or connect signals to Exit Long/Exit Short)');
    } else {
      // Detailed info about exits
      const exitInfo = [];
      if (hasExitBlocks) {
        const exitNames = exitBlocks.map((b) => b.name || b.type).join(', ');
        exitInfo.push(`blocks: ${exitNames}`);
      }
      if (hasExitSignals) {
        exitInfo.push('signal exits connected');
      }

      // Warn if no SL/TP specifically (risk management)
      const hasSLTP = exitBlocks.some((b) =>
        b.type === 'static_sltp' || b.type === 'tp_percent' || b.type === 'sl_percent' || b.type === 'atr_exit'
      );
      if (!hasSLTP) {
        result.warnings.push('🔴 Exit: No SL/TP block — trades have no stop-loss protection');
      }
    }

    // =============================================
    // DISCONNECTED BLOCKS CHECK
    // =============================================

    // Check for disconnected blocks (blocks without connections)
    const connectedBlockIds = new Set();
    connections.forEach((c) => {
      connectedBlockIds.add(c.source.blockId);
      connectedBlockIds.add(c.target.blockId);
    });
    // Exit blocks don't need connections (backend reads them from builder_blocks)
    const disconnectedBlocks = strategyBlocks.filter((b) =>
      !b.isMain && !connectedBlockIds.has(b.id) && !EXIT_BLOCK_TYPES.has(b.type)
    );
    if (disconnectedBlocks.length > 0) {
      result.warnings.push(`${disconnectedBlocks.length} block(s) are not connected`);
    }

    // =============================================
    // BLOCK PARAMETER VALIDATION
    // =============================================

    let blocksWithInvalidParams = 0;
    strategyBlocks.forEach((block) => {
      if (block.isMain) return; // Skip main strategy node

      const paramValidation = validateBlockParams(block);
      updateBlockValidationState(block.id, paramValidation);

      if (!paramValidation.valid) {
        blocksWithInvalidParams++;
        // Add first error as detailed message
        if (paramValidation.errors.length > 0) {
          result.errors.push(`Block "${block.name}": ${paramValidation.errors[0]}`);
        }
      }
    });

    if (blocksWithInvalidParams > 0) {
      result.valid = false;
      if (blocksWithInvalidParams > 1) {
        result.warnings.push(`${blocksWithInvalidParams} blocks have invalid parameters (hover for details)`);
      }
    }

    console.log('[Strategy Builder] Validation result:', result);
    updateValidationPanel(result);

  } catch (error) {
    console.error('[Strategy Builder] Validation error:', error);
    showNotification(`Ошибка валидации: ${error.message}`, 'error');
    updateValidationPanel({
      valid: false,
      errors: [`Validation failed: ${error.message}`],
      warnings: []
    });
  }
}

function updateValidationPanel(result) {
  console.log('[Strategy Builder] updateValidationPanel called');
  const status = document.getElementById('validationStatus');
  const list = document.getElementById('validationList');

  if (!status || !list) {
    console.warn('[Strategy Builder] Validation panel elements not found');
    // Fallback: show in console and toast notification
    const messages = [...result.errors, ...result.warnings];
    if (messages.length > 0) {
      showNotification(`Валидация:\n${messages.join('\n')}`, 'warning');
    } else {
      showNotification('Стратегия валидна!', 'success');
    }
    return;
  }

  // Note: Sidebar-right opening is handled separately by the Validate button
  // Validation panel visibility is controlled by CSS classes, not inline styles

  // Update status
  if (result.valid && result.errors.length === 0) {
    status.className = 'validation-status valid';
    status.innerHTML = '<i class="bi bi-check-circle-fill"></i> Valid';
    status.style.color = '#28a745';
  } else {
    status.className = 'validation-status invalid';
    status.innerHTML = '<i class="bi bi-x-circle-fill"></i> Invalid';
    status.style.color = '#dc3545';
  }

  // Build messages HTML
  let html = '';
  result.errors.forEach((err) => {
    html += `<div class="validation-item error"><i class="bi bi-x-circle"></i><span>${err}</span></div>`;
  });
  result.warnings.forEach((warn) => {
    html += `<div class="validation-item warning"><i class="bi bi-exclamation-triangle"></i><span>${warn}</span></div>`;
  });

  if (html === '') {
    html =
      '<div class="validation-item info"><i class="bi bi-info-circle"></i><span>Strategy is ready for backtesting</span></div>';
  }

  list.innerHTML = html;
  list.style.display = 'block';
  list.style.visibility = 'visible';

  console.log('[Strategy Builder] Validation panel updated', {
    valid: result.valid,
    errors: result.errors.length,
    warnings: result.warnings.length,
    statusVisible: status.offsetParent !== null,
    listVisible: list.offsetParent !== null
  });

  // Also show notification
  if (result.errors.length > 0) {
    showNotification(`Валидация не пройдена: ${result.errors[0]}`, 'error');
  } else if (result.warnings.length > 0) {
    showNotification(`Предупреждения: ${result.warnings[0]}`, 'warning');
  } else {
    showNotification('Стратегия валидна!', 'success');
  }
}

async function generateCode() {
  console.log('[Strategy Builder] generateCode called');
  const strategyId = getStrategyIdFromURL();
  console.log('[Strategy Builder] Strategy ID from URL:', strategyId);

  if (!strategyId) {
    showNotification('Сохраните стратегию перед генерацией кода', 'warning');
    if (confirm('Strategy not saved. Save now?')) {
      await saveStrategy();
      // Re-check after save
      const newId = getStrategyIdFromURL();
      if (!newId) {
        showNotification('Не удалось получить ID стратегии после сохранения', 'error');
        return;
      }
    } else {
      return;
    }
  }

  const finalId = getStrategyIdFromURL();
  if (!finalId) {
    showNotification('ID стратегии отсутствует. Невозможно сгенерировать код.', 'error');
    return;
  }

  try {
    showNotification('Генерация Python кода...', 'info');

    const url = `/api/v1/strategy-builder/strategies/${finalId}/generate-code`;
    console.log(`[Strategy Builder] Generate code request: POST ${url}`);

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template: 'backtest',
        include_comments: true,
        include_logging: true,
        async_mode: false
      })
    });

    console.log(`[Strategy Builder] Generate code response: status=${response.status}, ok=${response.ok}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Generate code error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Генерация кода не удалась: ${errorDetail}`, 'error');
      return;
    }

    const data = await response.json();
    console.log('[Strategy Builder] Generate code success:', { success: data.success, code_length: data.code?.length || 0 });

    if (!data.success) {
      const errors = data.errors || data.detail || 'Unknown error';
      showNotification(`Генерация кода не удалась: ${JSON.stringify(errors)}`, 'error');
      return;
    }

    const code = data.code || '';
    if (!code) {
      showNotification('Генерация кода вернула пустой результат', 'warning');
      return;
    }

    // Open code in a new window for now
    const win = window.open('', '_blank');
    if (win) {
      const escaped = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      win.document.write(
        `<html><head><title>Сгенерированный код стратегии</title></head><body><pre style="white-space:pre; font-family:monospace; font-size:12px; padding:16px;">${escaped}</pre></body></html>`
      );
      win.document.close();
    } else {
      // Fallback: log to console
      console.log('Generated code:', code);
      showNotification('Всплывающее окно заблокировано. Код в консоли.', 'warning');
    }

    showNotification('Код успешно сгенерирован', 'success');
  } catch (err) {
    showNotification(`Ошибка генерации кода: ${err.message}`, 'error');
  }
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

async function saveStrategy() {
  console.log('[Strategy Builder] saveStrategy called');

  // Offline guard: fall back to localStorage draft instead of failing silently
  if (!navigator.onLine) {
    showNotification('Нет подключения к сети. Стратегия сохранена в черновик (localStorage).', 'warning');
    autoSaveStrategy().catch((err) => console.warn('[Strategy Builder] Offline autosave error:', err));
    return;
  }

  const strategy = buildStrategyPayload();
  console.log('[Strategy Builder] Strategy payload:', strategy);

  // Валидация
  if (!strategy.name || strategy.name.trim() === '') {
    showNotification('Название стратегии обязательно', 'error');
    return;
  }

  if (!strategy.blocks || strategy.blocks.length === 0) {
    showNotification('Стратегия должна иметь хотя бы один блок', 'warning');
  }

  // WebSocket server-side validation before save
  if (wsValidation && wsValidation.isWsConnected()) {
    console.log('[Strategy Builder] Running server-side validation before save...');
    let wsTimedOut = false;
    const wsValidationResult = await new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        wsTimedOut = true;
        resolve({ valid: true, fallback: true });
      }, 3000);
      wsValidation.validateStrategy(strategy.blocks, strategy.connections, (result) => {
        clearTimeout(timeoutId);
        resolve(result);
      });
    });

    if (wsTimedOut) {
      console.warn('[Strategy Builder] WS validation timeout — saving without server validation');
      showNotification('Серверная валидация недоступна (таймаут). Сохранение без проверки.', 'warning');
    }

    if (!wsValidationResult.fallback && !wsValidationResult.valid) {
      const errorCount = wsValidationResult.messages?.filter(m => m.severity === 'error').length || 0;
      const warningCount = wsValidationResult.messages?.filter(m => m.severity === 'warning').length || 0;

      console.warn('[Strategy Builder] Server validation failed:', wsValidationResult.messages);

      if (errorCount > 0) {
        const errorMsgs = wsValidationResult.messages
          .filter(m => m.severity === 'error')
          .map(m => m.message)
          .slice(0, 3)
          .join('\n• ');
        showNotification(`Валидация не пройдена (${errorCount} ошибок):\n• ${errorMsgs}`, 'error');
        return;
      } else if (warningCount > 0) {
        // Warnings - ask user to continue
        const warningMsgs = wsValidationResult.messages
          .filter(m => m.severity === 'warning')
          .map(m => m.message)
          .slice(0, 3)
          .join('\n• ');
        if (!confirm(`Обнаружены предупреждения (${warningCount}):\n• ${warningMsgs}\n\nСохранить всё равно?`)) {
          return;
        }
      }
    }
    console.log('[Strategy Builder] Server validation passed');
  }

  try {
    const strategyId = getStrategyIdFromURL();

    // Если стратегия есть в URL, но она не Strategy Builder стратегия, создаем новую
    // Для этого сначала проверяем, существует ли она как Strategy Builder стратегия
    let finalStrategyId = strategyId;
    if (strategyId) {
      try {
        const checkResponse = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`);
        if (!checkResponse.ok) {
          console.warn(`[Strategy Builder] Strategy ${strategyId} not found as Strategy Builder strategy, will create new`);
          finalStrategyId = null; // Создадим новую стратегию
        }
      } catch (checkErr) {
        console.warn(`[Strategy Builder] Error checking strategy: ${checkErr}, will create new`);
        finalStrategyId = null;
      }
    }

    const method = finalStrategyId ? 'PUT' : 'POST';
    const url = finalStrategyId
      ? `/api/v1/strategy-builder/strategies/${finalStrategyId}`
      : '/api/v1/strategy-builder/strategies';

    console.log(`[Strategy Builder] Saving strategy: method=${method}, url=${url}, id=${finalStrategyId || 'new'}`);
    console.log(`[Strategy Builder] Payload blocks: ${strategy.blocks.length}, connections: ${strategy.connections.length}`);

    const response = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(strategy)
    });

    console.log(`[Strategy Builder] Save response: status=${response.status}, ok=${response.ok}`);

    if (response.ok) {
      const data = await response.json();
      console.log('[Strategy Builder] Save success:', data);
      updateLastSaved(data.updated_at || new Date().toISOString());
      showNotification('Стратегия успешно сохранена!', 'success');

      // Clear localStorage draft — saved successfully, draft no longer needed
      const savedId = finalStrategyId || data.id;
      if (savedId) {
        clearLocalStorageDraft(savedId);
        console.log(`[Strategy Builder] Cleared localStorage draft for strategy ${savedId}`);
      }

      // Обновить URL если новая стратегия
      if (!finalStrategyId && data.id) {
        console.log(`[Strategy Builder] Updating URL with new strategy ID: ${data.id}`);
        window.history.pushState({}, '', `?id=${data.id}`);
      }
    } else {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Save error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Ошибка сохранения стратегии: ${errorDetail}`, 'error');
    }
  } catch (err) {
    console.error('[Strategy Builder] Save exception:', err);
    showNotification(`Не удалось сохранить стратегию: ${err.message}`, 'error');
  }
}

function buildStrategyPayload() {
  console.log('[Strategy Builder] buildStrategyPayload called');

  const nameEl = document.getElementById('strategyName');
  const timeframeEl = document.getElementById('strategyTimeframe');
  const marketTypeEl = document.getElementById('builderMarketType');
  const directionEl = document.getElementById('builderDirection');
  const symbolEl = document.getElementById('strategySymbol');
  const backtestSymbolEl = document.getElementById('backtestSymbol');
  const backtestCapitalEl = document.getElementById('backtestCapital');

  const symbol = symbolEl?.value || backtestSymbolEl?.value || 'BTCUSDT';
  const initialCapital = parseFloat(backtestCapitalEl?.value || 10000);

  console.log('[Strategy Builder] Form elements:', {
    name: nameEl?.value,
    timeframe: timeframeEl?.value,
    symbol,
    market_type: marketTypeEl?.value,
    direction: directionEl?.value,
    initial_capital: initialCapital
  });

  const backtestLeverageEl = document.getElementById('backtestLeverage');
  const backtestPositionSizeTypeEl = document.getElementById('backtestPositionSizeType');
  const backtestPositionSizeEl = document.getElementById('backtestPositionSize');
  const leverage = parseInt(backtestLeverageEl?.value, 10) || 10;
  const positionSizeType = backtestPositionSizeTypeEl?.value || 'percent';
  const positionSizeVal = parseFloat(backtestPositionSizeEl?.value) || 100;
  const noTradeDays = getNoTradeDaysFromUI();
  const payload = {
    name: nameEl?.value || 'New Strategy',
    description: '',
    timeframe: timeframeEl?.value || '15',
    symbol,
    market_type: marketTypeEl?.value || 'linear',
    direction: directionEl?.value || 'both',
    initial_capital: initialCapital,
    leverage,
    position_size: positionSizeType === 'percent' ? positionSizeVal / 100 : positionSizeVal,
    parameters: {
      _position_size_type: positionSizeType,
      _order_amount: positionSizeType === 'fixed_amount' ? positionSizeVal : undefined,
      _no_trade_days: noTradeDays.length ? noTradeDays : undefined,
      _commission: parseFloat(document.getElementById('backtestCommission')?.value || '0.07') / 100,
      _slippage: parseFloat(document.getElementById('backtestSlippage')?.value || '0.05') / 100,
      _pyramiding: parseInt(document.getElementById('backtestPyramiding')?.value || '1', 10) || 1,
      _start_date: document.getElementById('backtestStartDate')?.value || '2025-01-01',
      _end_date: document.getElementById('backtestEndDate')?.value || new Date().toISOString().slice(0, 10)
    },
    blocks: strategyBlocks.map(b => ({
      id: b.id,
      type: b.type,
      category: b.category,
      name: b.name,
      icon: b.icon,
      x: b.x,
      y: b.y,
      isMain: b.isMain || false,
      params: b.params || {},
      optimizationParams: b.optimizationParams || {}
    })),
    connections: connections.map(c => ({
      id: c.id,
      source: c.source,
      target: c.target,
      type: c.type || 'data'
    })),
    // UI state for restoration
    uiState: {
      zoom: zoom,
      strategyName: nameEl?.value || 'New Strategy',
      savedAt: new Date().toISOString()
    }
  };

  console.log('[Strategy Builder] Payload built:', {
    ...payload,
    blocks_count: payload.blocks.length,
    connections_count: payload.connections.length
  });

  return payload;
}

async function autoSaveStrategy() {
  try {
    // Skip autosave if reset was just performed
    if (skipNextAutoSave) {
      skipNextAutoSave = false;
      console.log('[Strategy Builder] Skipping autosave after reset');
      return;
    }

    const strategyId = getStrategyIdFromURL() || 'draft';
    const payload = buildStrategyPayload();

    // Не автосохраняем пустые стратегии
    if (!payload.blocks.length && !connections.length) {
      return;
    }

    // Don't autosave if only Strategy node exists (clean state)
    if (payload.blocks.length === 1 && payload.blocks[0].type === 'strategy' && !connections.length) {
      console.log('[Strategy Builder] Skipping autosave - clean initial state');
      return;
    }

    const serialized = JSON.stringify(payload);
    if (serialized === lastAutoSavePayload) {
      return; // нет изменений
    }
    lastAutoSavePayload = serialized;

    // 1) LocalStorage draft
    try {
      const key = `strategy_builder_draft_${strategyId}`;
      window.localStorage.setItem(key, serialized);
    } catch (e) {
      console.warn('LocalStorage autosave failed:', e);
    }

    // 2) Remote autosave only если есть реальный ID (стратегия уже сохранена)
    if (strategyId !== 'draft') {
      // Pre-check: skip remote save if browser is offline
      if (!navigator.onLine) {
        console.warn('[Strategy Builder] Autosave skipped — browser is offline');
        return;
      }

      const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
      const response = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: serialized
      });

      if (response.ok) {
        const data = await response.json();
        updateLastSaved(data.updated_at || new Date().toISOString());
      } else {
        // Тихая ошибка, без алерта — не мешать пользователю
        console.warn('Autosave PUT failed', await response.text());
      }
    }
  } catch (err) {
    console.warn('Autosave failed:', err);
  }
}

/**
 * Migrate legacy blocks to new unified block types.
 * Converts old tp_percent + sl_percent blocks into a single static_sltp block.
 */
function migrateLegacyBlocks(blocks) {
  const tpBlock = blocks.find(b => b.type === 'tp_percent');
  const slBlock = blocks.find(b => b.type === 'sl_percent');

  if (!tpBlock && !slBlock) return blocks;

  // Build merged static_sltp params from legacy blocks
  const tpParams = tpBlock?.params || tpBlock?.config || {};
  const slParams = slBlock?.params || slBlock?.config || {};
  const mergedParams = {
    take_profit_percent: tpParams.take_profit_percent ?? 1.5,
    stop_loss_percent: slParams.stop_loss_percent ?? 1.5,
    close_only_in_profit: false,
    activate_breakeven: false,
    breakeven_activation_percent: 0.5,
    new_breakeven_sl_percent: 0.1
  };

  // Use position of the first found legacy block
  const refBlock = tpBlock || slBlock;
  const staticSltpBlock = {
    id: refBlock.id,
    type: 'static_sltp',
    name: 'Static SL/TP',
    x: refBlock.x,
    y: refBlock.y,
    params: mergedParams,
    config: mergedParams
  };

  // Filter out both legacy blocks and add the merged one
  const filtered = blocks.filter(b => b.type !== 'tp_percent' && b.type !== 'sl_percent');
  filtered.push(staticSltpBlock);

  console.log('[Migration] Converted tp_percent + sl_percent → static_sltp', mergedParams);
  return filtered;
}

async function loadStrategy(strategyId) {
  // Close any open block params popup before loading a new strategy
  closeBlockParamsPopup();

  try {
    const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
    console.log(`[Strategy Builder] Loading strategy: GET ${url}`);

    const response = await fetch(url);
    console.log(`[Strategy Builder] Load response: status=${response.status}, ok=${response.ok}`);

    if (!response.ok) {
      if (response.status === 404) {
        const errorText = await response.text();
        console.error(`[Strategy Builder] Strategy not found: ${errorText}`);
        showNotification('Стратегия не найдена. Возможно, это не Strategy Builder стратегия.', 'error');
        return;
      }
      const errorText = await response.text();
      console.error(`[Strategy Builder] Load error: status=${response.status}, body=${errorText}`);
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const strategy = await response.json();
    console.log('[Strategy Builder] Strategy loaded:', {
      id: strategy.id,
      name: strategy.name,
      is_builder_strategy: strategy.is_builder_strategy,
      blocks_count: strategy.blocks?.length || 0,
      connections_count: strategy.connections?.length || 0
    });

    // Обновить UI поля
    document.getElementById('strategyName').value = strategy.name || 'New Strategy';
    syncStrategyNameDisplay();
    if (document.getElementById('strategyTimeframe')) {
      document.getElementById('strategyTimeframe').value = normalizeTimeframeForDropdown(strategy.timeframe) || '15';
    }
    if (document.getElementById('builderMarketType')) {
      document.getElementById('builderMarketType').value = strategy.market_type || 'linear';
    }
    if (document.getElementById('builderDirection')) {
      document.getElementById('builderDirection').value = strategy.direction || 'both';
    }
    // Синхронизировать поля бэктеста с данными стратегии
    const backtestSymbol = document.getElementById('backtestSymbol');
    const backtestCapital = document.getElementById('backtestCapital');
    const backtestLeverage = document.getElementById('backtestLeverage');
    if (backtestSymbol) backtestSymbol.value = strategy.symbol || 'BTCUSDT';
    if (backtestCapital) backtestCapital.value = strategy.initial_capital || 10000;
    const maxLeverage = 100; // Bug #2 fix: use 100 as default; actual max is loaded dynamically from exchange
    const lev = Math.min(maxLeverage, Math.max(1, strategy.leverage != null ? strategy.leverage : 10));
    const backtestLeverageRange = document.getElementById('backtestLeverageRange');
    if (backtestLeverage) backtestLeverage.value = lev;
    if (backtestLeverageRange) backtestLeverageRange.value = lev;
    updateBacktestLeverageDisplay(lev);
    const params = strategy.parameters || {};
    const posType = params._position_size_type || 'percent';
    const backtestPositionSizeType = document.getElementById('backtestPositionSizeType');
    const backtestPositionSize = document.getElementById('backtestPositionSize');
    if (backtestPositionSizeType) backtestPositionSizeType.value = posType;
    if (backtestPositionSize) {
      const posVal = strategy.position_size != null
        ? (posType === 'percent' ? strategy.position_size * 100 : strategy.position_size)
        : (params._order_amount || 100);
      backtestPositionSize.value = posVal;
    }
    updateBacktestPositionSizeInput();
    updateBacktestLeverageRisk();

    const noTradeDays = strategy.parameters?._no_trade_days;
    if (Array.isArray(noTradeDays) && noTradeDays.length >= 0) {
      setNoTradeDaysInUI(noTradeDays);
    }

    const backtestCommission = document.getElementById('backtestCommission');
    if (backtestCommission && strategy.parameters?._commission != null) {
      backtestCommission.value = (strategy.parameters._commission * 100).toFixed(2);
    }
    const backtestSlippage = document.getElementById('backtestSlippage');
    if (backtestSlippage && strategy.parameters?._slippage != null) {
      backtestSlippage.value = (strategy.parameters._slippage * 100).toFixed(2);
    }
    const backtestPyramiding = document.getElementById('backtestPyramiding');
    if (backtestPyramiding && strategy.parameters?._pyramiding != null) {
      backtestPyramiding.value = strategy.parameters._pyramiding;
    }

    // Bug #3 fix: restore saved dates; don't auto-overwrite with today on load
    const backtestStartDateEl = document.getElementById('backtestStartDate');
    const backtestEndDateEl = document.getElementById('backtestEndDate');
    if (backtestStartDateEl) {
      const savedStart = strategy.parameters?._start_date || strategy.start_date || '2025-01-01';
      backtestStartDateEl.value = savedStart;
    }
    if (backtestEndDateEl) {
      const today = new Date().toISOString().slice(0, 10);
      const savedEnd = strategy.parameters?._end_date || strategy.end_date || today;
      // If saved date is in the future, show today; otherwise use saved value
      backtestEndDateEl.value = savedEnd > today ? today : savedEnd;
    }

    // Восстановить блоки и соединения
    pushUndo();
    strategyBlocks.length = 0; // Clear all existing blocks

    // Добавить загруженные блоки (with legacy migration + enrichment)
    if (strategy.blocks && Array.isArray(strategy.blocks)) {
      const migratedBlocks = migrateLegacyBlocks(strategy.blocks);

      // First, handle main_strategy node
      const mainBlock = migratedBlocks.find(b => b.isMain || b.id === 'main_strategy' || b.type === 'strategy');
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
        // No main node from API — create default
        createMainStrategyNode();
      }

      // Then add other blocks with icon enrichment from blockLibrary
      migratedBlocks.forEach(block => {
        if (block.isMain || block.id === 'main_strategy' || block.type === 'strategy') return;

        // Look up icon from blockLibrary
        let icon = block.icon;
        if (!icon) {
          for (const categoryBlocks of Object.values(blockLibrary)) {
            const def = categoryBlocks.find(b => b.id === block.type);
            if (def) {
              icon = def.icon;
              break;
            }
          }
        }

        strategyBlocks.push({
          id: block.id,
          type: block.type,
          category: block.category || 'indicator',
          name: block.name || block.type,
          icon: icon || 'box',
          x: block.x || 100,
          y: block.y || 100,
          params: block.params || {},
          optimizationParams: block.optimizationParams || {}
        });
      });
    }

    console.log('[Strategy Builder] Blocks loaded and enriched:', strategyBlocks.map(b => ({
      id: b.id, type: b.type, category: b.category, icon: b.icon, isMain: b.isMain
    })));

    // Восстановить соединения
    connections.length = 0;
    if (strategy.connections && Array.isArray(strategy.connections)) {
      connections.push(...strategy.connections);
    }
    normalizeAllConnections();

    console.log('[Strategy Builder] Connections normalized:', connections.map(c => ({
      id: c.id,
      src: `${c.source.blockId}:${c.source.portId}`,
      tgt: `${c.target.blockId}:${c.target.portId}`
    })));

    // Перерисовать canvas (renderBlocks calls renderConnections internally)
    renderBlocks();

    updateLastSaved(strategy.updated_at);
    showNotification('Стратегия успешно загружена!', 'success');
    // Запустить проверку/синхронизацию данных для загруженного символа и TF
    runCheckSymbolDataForProperties();
  } catch (err) {
    showNotification(`Ошибка загрузки стратегии: ${err.message}`, 'error');
  }
}

async function openVersionsModal() {
  const strategyId = getStrategyIdFromURL();
  if (!strategyId) {
    showNotification('Откройте существующую стратегию', 'warning');
    return;
  }
  const modal = document.getElementById('versionsModal');
  const listEl = document.getElementById('versionsList');
  if (!modal || !listEl) return;

  listEl.innerHTML = '<p class="text-muted">Загрузка...</p>';
  modal.classList.add('active');

  try {
    const res = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}/versions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const versions = data.versions || [];
    if (versions.length === 0) {
      listEl.innerHTML = '<p class="text-muted">Нет сохранённых версий.</p>';
      return;
    }
    listEl.innerHTML = versions
      .map(
        (v) => `
        <div class="version-item d-flex justify-content-between align-items-center py-2 border-bottom">
          <span><strong>v${v.version}</strong> · ${formatDate(v.created_at) || v.created_at || ''}</span>
          <button class="btn btn-sm btn-outline-primary" onclick="revertToVersion('${strategyId}', ${v.id})">
            <i class="bi bi-arrow-counterclockwise"></i> Restore
          </button>
        </div>
      `
      )
      .join('');
  } catch (err) {
    listEl.innerHTML = `<p class="text-danger">Ошибка: ${escapeHtml(err.message)}</p>`;
  }
}

function closeVersionsModal() {
  const modal = document.getElementById('versionsModal');
  if (modal) modal.classList.remove('active');
}

async function revertToVersion(strategyId, versionId) {
  if (!confirm('Восстановить эту версию? Текущие изменения будут заменены.')) return;
  try {
    const res = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}/revert/${versionId}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(await res.text());
    closeVersionsModal();
    await loadStrategy(strategyId);
    showNotification('Версия восстановлена', 'success');
  } catch (err) {
    showNotification(`Ошибка: ${err.message}`, 'error');
  }
}

// =============================================
// BACKEND INTEGRATION: Map Strategy Blocks to API
// =============================================

/**
 * Convert strategy blocks to backend API format.
 * Maps visual blocks to strategy_type and strategy_params.
 *
 * NOTE (2026-02-15): This function is NOT used by buildBacktestRequest() because
 * the backend reads blocks/connections directly from the database. The fields it
 * produces (strategy_type, filters, exits, etc.) were silently dropped by Pydantic.
 * Kept as _mapBlocksToBackendParams for potential future use (e.g. code generation).
 */
function _mapBlocksToBackendParams() {
  const result = {
    strategy_type: 'custom',
    strategy_params: {},
    filters: [],
    exits: [],
    position_sizing: null,
    risk_controls: []
  };

  // Find entry indicators (RSI, MACD, etc.)
  const indicatorBlocks = strategyBlocks.filter(b =>
    blockLibrary.indicators.some(ind => ind.id === b.type)
  );

  // Find filters
  const filterBlocks = strategyBlocks.filter(b =>
    blockLibrary.filters.some(f => f.id === b.type)
  );

  // Find exit conditions (exits + close_conditions for DCA/TradingView-style)
  const exitBlocks = strategyBlocks.filter(b =>
    (blockLibrary.exits && blockLibrary.exits.some(e => e.id === b.type)) ||
    (blockLibrary.close_conditions && blockLibrary.close_conditions.some(c => c.id === b.type))
  );

  // Find position sizing
  const sizingBlocks = strategyBlocks.filter(b =>
    blockLibrary.position_sizing && blockLibrary.position_sizing.some(s => s.id === b.type)
  );

  // Find risk controls
  const riskBlocks = strategyBlocks.filter(b =>
    blockLibrary.risk_controls && blockLibrary.risk_controls.some(r => r.id === b.type)
  );

  // Map primary indicator to strategy_type
  if (indicatorBlocks.length > 0) {
    const primaryIndicator = indicatorBlocks[0];
    result.strategy_type = mapIndicatorToStrategyType(primaryIndicator.type);
    result.strategy_params = mapIndicatorParams(primaryIndicator);
  }

  // Map filters
  filterBlocks.forEach(block => {
    result.filters.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type),
      enabled: block.params?.enabled !== false
    });
  });

  // Map exits
  exitBlocks.forEach(block => {
    result.exits.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type)
    });
  });

  // Map position sizing (use first one)
  if (sizingBlocks.length > 0) {
    result.position_sizing = {
      type: sizingBlocks[0].type,
      params: sizingBlocks[0].params || getDefaultParams(sizingBlocks[0].type)
    };
  }

  // Map risk controls
  riskBlocks.forEach(block => {
    result.risk_controls.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type)
    });
  });

  return result;
}

/**
 * Map indicator block type to backend strategy_type
 */
function mapIndicatorToStrategyType(blockType) {
  const mapping = {
    'rsi': 'rsi',
    'macd': 'macd',
    'ema': 'ema_cross',
    'sma': 'sma_cross',
    'bollinger': 'bollinger_bands',
    'supertrend': 'supertrend',
    'stochastic': 'stochastic',
    'cci': 'cci',
    'atr': 'atr',
    'adx': 'adx',
    'ichimoku': 'ichimoku',
    'vwap': 'vwap',
    'obv': 'obv',
    'mfi': 'mfi',
    'williams_r': 'williams_r',
    'roc': 'roc',
    'momentum': 'momentum',
    'trix': 'trix',
    'keltner': 'keltner',
    'donchian': 'donchian',
    'parabolic_sar': 'parabolic_sar',
    'pivot_points': 'pivot_points',
    'fibonacci': 'fibonacci',
    'heikin_ashi': 'heikin_ashi',
    'renko': 'renko',
    'volume_profile': 'volume_profile',
    'vwma': 'vwma',
    'tema': 'tema',
    'dema': 'dema',
    'wma': 'wma',
    'hull_ma': 'hull_ma',
    'zlema': 'zlema',
    'kama': 'kama',
    'linear_regression': 'linear_regression',
    'mtf': 'mtf'
  };
  return mapping[blockType] || 'custom';
}

/**
 * Map indicator block params to backend strategy_params format
 */
function mapIndicatorParams(block) {
  const params = block.params || getDefaultParams(block.type);

  // Common mappings
  const mapped = {};

  switch (block.type) {
    case 'rsi':
      mapped.period = params.period || 14;
      mapped.overbought = params.overbought || 70;
      mapped.oversold = params.oversold || 30;
      mapped.source = params.source || 'close';
      break;

    case 'macd':
      mapped.fast_period = params.fast_period || 12;
      mapped.slow_period = params.slow_period || 26;
      mapped.signal_period = params.signal_period || 9;
      mapped.source = params.source || 'close';
      break;

    case 'ema':
    case 'sma':
      mapped.fast_period = params.fast_period || 9;
      mapped.slow_period = params.slow_period || 21;
      mapped.source = params.source || 'close';
      break;

    case 'bollinger':
      mapped.period = params.period || 20;
      mapped.std_dev = params.std_dev || 2.0;
      mapped.source = params.source || 'close';
      break;

    case 'supertrend':
      mapped.period = params.period || 10;
      mapped.multiplier = params.multiplier || 3.0;
      break;

    case 'stochastic':
      mapped.k_period = params.k_period || 14;
      mapped.d_period = params.d_period || 3;
      mapped.smooth_k = params.smooth_k || 3;
      mapped.overbought = params.overbought || 80;
      mapped.oversold = params.oversold || 20;
      break;

    default:
      // Pass through all params for unknown types
      Object.assign(mapped, params);
  }

  return mapped;
}

/**
 * Build full backtest request from UI state.
 *
 * NOTE: Backend reads blocks/connections from the DATABASE (not from this payload).
 * Only Properties-panel fields (symbol, interval, capital, leverage, etc.) are sent here.
 * mapBlocksToBackendParams() is NOT called — its output was silently dropped by Pydantic
 * because BacktestRequest model doesn't define strategy_type/filters/exits/etc. fields.
 * See: Bug #1 fix (2026-02-15).
 */

/**
 * Extract stop_loss / take_profit from strategy exit blocks.
 *
 * Block types handled:
 *   static_sltp  → stop_loss_percent & take_profit_percent (UI %)
 *   sl_percent   → stop_loss_percent only
 *   tp_percent   → take_profit_percent only
 *
 * Returns an object with `stop_loss` and/or `take_profit` as decimal fractions
 * (e.g. 5% → 0.05), matching BacktestRequest model field format.
 * Fields are omitted (not null) if no block provides them, so the backend
 * falls back to its own block extraction logic.
 */
function extractSlTpFromBlocks() {
  const result = {};
  for (const block of strategyBlocks) {
    const type = block.type;
    const params = block.params || {};
    if (type === 'static_sltp') {
      if (params.stop_loss_percent != null && result.stop_loss == null) {
        result.stop_loss = params.stop_loss_percent / 100;
      }
      if (params.take_profit_percent != null && result.take_profit == null) {
        result.take_profit = params.take_profit_percent / 100;
      }
      // Breakeven — backend reads from DB blocks, but send explicitly for self-contained requests
      if (params.activate_breakeven) {
        result.breakeven_enabled = true;
        const beActivation = params.breakeven_activation_percent ?? 0.5;
        const beNewSl = params.new_breakeven_sl_percent ?? 0.1;
        result.breakeven_activation_pct = beActivation / 100;
        result.breakeven_offset = beNewSl / 100;
      }
      // Close only in profit
      if (params.close_only_in_profit) {
        result.close_only_in_profit = true;
      }
      // SL type (average_price or last_order)
      if (params.sl_type) {
        result.sl_type = params.sl_type;
      }
    } else if (type === 'sl_percent' && result.stop_loss == null) {
      const sl = params.stop_loss_percent ?? params.percent;
      if (sl != null) result.stop_loss = sl / 100;
    } else if (type === 'tp_percent' && result.take_profit == null) {
      const tp = params.take_profit_percent ?? params.percent;
      if (tp != null) result.take_profit = tp / 100;
    }
  }
  return result;
}

function buildBacktestRequest() {
  // Таймфрейм и направление — из общей секции (формат Bybit: 1,3,5,15,30,60,120,240,360,720,D,W,M)
  const timeframeRaw = document.getElementById('strategyTimeframe')?.value || '15';
  const interval = convertIntervalToAPIFormat(timeframeRaw);

  const backtestConfig = {
    // Basic params
    symbol: document.getElementById('backtestSymbol')?.value || 'BTCUSDT',
    interval: interval,
    start_date: document.getElementById('backtestStartDate')?.value || '2025-01-01',
    end_date: (() => {
      const endVal = document.getElementById('backtestEndDate')?.value || new Date().toISOString().slice(0, 10);
      const today = new Date().toISOString().slice(0, 10);
      if (endVal > today) {
        // Bug #3 fix: warn user instead of silently clamping future date
        showNotification(`End Date ${endVal} в будущем — бэктест запускается по сегодняшнюю дату (${today})`, 'info');
        console.info(`[Backtest] End date ${endVal} is in the future, clamped to ${today}`);
        return today;
      }
      return endVal;
    })(),

    // Market type: spot (TradingView parity) or linear (perpetual futures)
    market_type: document.getElementById('builderMarketType')?.value || 'linear',

    // Capital & Risk
    initial_capital: parseFloat(document.getElementById('backtestCapital')?.value) || 10000,
    leverage: parseInt(document.getElementById('backtestLeverage')?.value) || 10,
    direction: document.getElementById('builderDirection')?.value || 'both',
    pyramiding: parseInt(document.getElementById('backtestPyramiding')?.value) || 1,

    // Commission: read from UI as percentage (e.g. 0.07 = 0.07%), convert to decimal (0.0007)
    // Bug #1 fix: allow 0% commission (useful for testing without fees)
    commission: (() => {
      const rawVal = parseFloat(document.getElementById('backtestCommission')?.value ?? '0.07');
      if (isNaN(rawVal) || rawVal < 0) {
        console.warn(`[Backtest] Commission invalid value "${rawVal}". Using default 0.07%.`);
        return 0.0007;
      }
      if (rawVal > 1.0) {
        console.warn(`[Backtest] Commission ${rawVal}% is unusually high (max 1%). Clamping to 1%.`);
        return 0.01;
      }
      // 0% is a valid value — useful for zero-fee testing (e.g. spot or custom scenarios)
      return rawVal / 100;
    })(),

    // Slippage: read from UI as percentage, convert to decimal (0.05% → 0.0005)
    // Bug #6 fix: expose slippage in Properties panel instead of hardcoding 0.0005
    slippage: (() => {
      const el = document.getElementById('backtestSlippage');
      const rawSlip = el != null ? parseFloat(el.value) : 0.05;
      if (isNaN(rawSlip) || rawSlip < 0) return 0.0005;
      if (rawSlip > 5.0) return 0.05; // cap at 5%
      return rawSlip / 100;
    })(),

    // Position sizing from Properties (position_size as fraction 0–1 for percent mode)
    position_size_type: document.getElementById('backtestPositionSizeType')?.value || 'percent',
    position_size: (() => {
      const typeEl = document.getElementById('backtestPositionSizeType');
      const sizeEl = document.getElementById('backtestPositionSize');
      const type = typeEl?.value || 'percent';
      const val = parseFloat(sizeEl?.value) || 100;
      return type === 'percent' ? val / 100 : val;
    })(),

    // Time filter: days to block (0=Mon … 6=Sun). Unchecked = trade that day.
    no_trade_days: getNoTradeDaysFromUI(),

    // SL/TP from exit blocks (static_sltp, sl_percent, tp_percent)
    // Backend also extracts these from DB blocks as fallback, but sending
    // them explicitly ensures the request is self-contained and debuggable.
    ...extractSlTpFromBlocks()
  };

  return backtestConfig;
}

/** UI day checkboxes: Su=6, Mo=0, Tu=1, We=2, Th=3, Fr=4, Sa=5 (Python weekday) */
const DAY_BLOCK_IDS = [
  { id: 'dayBlockMo', weekday: 0 },
  { id: 'dayBlockTu', weekday: 1 },
  { id: 'dayBlockWe', weekday: 2 },
  { id: 'dayBlockTh', weekday: 3 },
  { id: 'dayBlockFr', weekday: 4 },
  { id: 'dayBlockSa', weekday: 5 },
  { id: 'dayBlockSu', weekday: 6 }
];

function getNoTradeDaysFromUI() {
  const out = [];
  for (const { id, weekday } of DAY_BLOCK_IDS) {
    const el = document.getElementById(id);
    if (el && el.checked) out.push(weekday);
  }
  return out;
}

function setNoTradeDaysInUI(days) {
  const set = new Set(Array.isArray(days) ? days : []);
  for (const { id, weekday } of DAY_BLOCK_IDS) {
    const el = document.getElementById(id);
    if (el) el.checked = set.has(weekday);
  }
}

/** Bybit API v5 kline intervals: 1,3,5,15,30,60,120,240,360,720,D,W,M */
const BYBIT_INTERVALS = new Set(['1', '5', '15', '30', '60', '240', 'D', 'W', 'M']);

const LEGACY_TF_MAP_DROPDOWN = { '3': '5', '120': '60', '360': '240', '720': 'D' };

/**
 * Нормализовать сохранённый таймфрейм к значению для выпадающего списка.
 * Поддерживает старый формат (1h, 15m) и нативный (15, 60, D). Устаревшие TF → ближайший.
 */
function normalizeTimeframeForDropdown(stored) {
  if (!stored) return '15';
  const s = String(stored).trim();
  if (BYBIT_INTERVALS.has(s)) return s;
  if (LEGACY_TF_MAP_DROPDOWN[s]) return LEGACY_TF_MAP_DROPDOWN[s];
  const mapping = {
    '1m': '1', '3m': '5', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '60', '4h': '240', '6h': '240', '12h': 'D', '1d': 'D', '1D': 'D', '1w': 'W', '1W': 'W', '1M': 'M', 'M': 'M'
  };
  return mapping[s] || '15';
}

/**
 * Привести интервал к формату API/БД (1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M).
 */
function convertIntervalToAPIFormat(value) {
  const s = String(value).trim();
  if (BYBIT_INTERVALS.has(s)) return s;
  if (LEGACY_TF_MAP_DROPDOWN[s]) return LEGACY_TF_MAP_DROPDOWN[s];
  const mapping = {
    '1m': '1', '3m': '5', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '60', '4h': '240', '6h': '240', '12h': 'D', '1d': 'D', '1D': 'D', '1w': 'W', '1W': 'W', '1M': 'M', 'M': 'M'
  };
  return mapping[s] || '15';
}

async function runBacktest() {
  console.log('[Strategy Builder] runBacktest called');
  let strategyId = getStrategyIdFromURL();
  console.log('[Strategy Builder] Strategy ID from URL:', strategyId);

  if (!strategyId) {
    showNotification('Сохраните стратегию перед запуском бэктеста', 'warning');
    // Предложить сохранить
    if (confirm('Strategy not saved. Save now?')) {
      await saveStrategy();
      // После сохранения получаем ID и продолжаем линейно (без рекурсии)
      strategyId = getStrategyIdFromURL();
      if (!strategyId) {
        showNotification('Не удалось получить ID стратегии после сохранения', 'error');
        return;
      }
      console.log('[Strategy Builder] Proceeding with saved strategy ID:', strategyId);
    } else {
      return;
    }
  }

  if (strategyBlocks.length === 0) {
    showNotification('Добавьте блоки в стратегию перед бэктестом', 'warning');
    return;
  }

  // =============================================
  // PRE-BACKTEST VALIDATION (3-part check)
  // =============================================
  const preCheck = validateStrategyCompleteness();
  if (!preCheck.valid) {
    const errorMsg = preCheck.errors.join('\n');
    showNotification(`Стратегия не готова к бэктесту:\n${errorMsg}`, 'error');
    // Also trigger full validation panel
    await validateStrategy();
    const vPanel = document.querySelector('.validation-panel');
    if (vPanel) { vPanel.classList.remove('closing'); vPanel.classList.add('visible'); }
    return;
  }
  // Show warnings but allow backtest to proceed
  if (preCheck.warnings.length > 0) {
    console.log('[Strategy Builder] Backtest warnings:', preCheck.warnings);
  }

  const symbol = document.getElementById('backtestSymbol')?.value?.trim();
  if (!symbol) {
    showNotification('Выберите тикер в поле Symbol', 'warning');
    return;
  }

  // Bug #4 fix: validate date range on frontend before sending — avoids cryptic HTTP 422
  const DATA_START_DATE = '2025-01-01'; // Must match backend/config/database_policy.py
  const startDateVal = document.getElementById('backtestStartDate')?.value || DATA_START_DATE;
  const endDateVal = document.getElementById('backtestEndDate')?.value || new Date().toISOString().slice(0, 10);
  if (startDateVal < DATA_START_DATE) {
    showNotification(`Start Date не может быть раньше ${DATA_START_DATE} — данные в БД начинаются с этой даты.`, 'error');
    return;
  }
  const msPerDay = 86400000;
  const durationDays = (new Date(endDateVal) - new Date(startDateVal)) / msPerDay;
  if (durationDays > 730) {
    showNotification(`Диапазон дат ${Math.round(durationDays)} дней превышает максимум 730 дней (2 года). Сократите период.`, 'error');
    return;
  }
  if (durationDays <= 0) {
    showNotification('End Date должна быть позже Start Date.', 'error');
    return;
  }

  // Bug #5 fix: sync graph to DB before backtest so backend reads up-to-date
  // state (e.g. direction change that pruned connections, param edits not yet saved)
  await autoSaveStrategy();

  // Собрать параметры бэктеста используя маппинг блоков
  const backtestParams = buildBacktestRequest();

  // Override with strategy ID
  backtestParams.strategy_id = strategyId;

  console.log('[Strategy Builder] Built backtest params from blocks:', backtestParams);

  try {
    showNotification('Запуск бэктеста...', 'info');

    const url = `/api/v1/strategy-builder/strategies/${strategyId}/backtest`;
    console.log(`[Strategy Builder] Backtest request: POST ${url}`);
    console.log('[Strategy Builder] Backtest params:', backtestParams);

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backtestParams)
    });

    console.log(`[Strategy Builder] Backtest response: status=${response.status}, ok=${response.ok}`);

    if (response.ok) {
      const data = await response.json();
      console.log('[Strategy Builder] Backtest success:', data);

      // Display warnings from backend (direction/signal mismatches)
      if (data.warnings && data.warnings.length > 0) {
        data.warnings.forEach(w => {
          console.warn('[Strategy Builder] Backend warning:', w);
          showNotification(`⚠️ ${w}`, 'warning');
        });
      }

      // Check if results are returned directly (for quick preview)
      if (data.metrics || data.trades || data.equity_curve) {
        // Show results in modal for quick preview
        showNotification('Бэктест завершён!', 'success');
        displayBacktestResults(data);
      } else if (data.backtest_id) {
        // Offer choice: view in modal or full page
        showNotification('Бэктест завершён!', 'success');
        // Try to fetch full results for modal display
        try {
          const resultsResponse = await fetch(`/api/v1/backtests/${data.backtest_id}`);
          if (resultsResponse.ok) {
            const resultsData = await resultsResponse.json();
            resultsData.backtest_id = data.backtest_id;
            displayBacktestResults(resultsData);
          } else {
            // Fallback to redirect
            window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
          }
        } catch {
          // Fallback to redirect
          window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
        }
      } else if (data.redirect_url) {
        console.log(`[Strategy Builder] Redirecting to: ${data.redirect_url}`);
        window.location.href = data.redirect_url;
      } else {
        showNotification('Бэктест запущен. Проверьте результаты позже.', 'info');
      }
    } else {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Backtest error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Ошибка бэктеста: ${errorDetail}`, 'error');
    }
  } catch (err) {
    console.error('[Strategy Builder] Backtest exception:', err);
    showNotification(`Не удалось запустить бэктест: ${err.message}`, 'error');
  }
}

// ============================================
// BACKTEST RESULTS DISPLAY
// ============================================

// Store current backtest results for export
let currentBacktestResults = null;

/**
 * Display backtest results in a beautiful modal
 * @param {Object} results - Backtest results from API
 */
function displayBacktestResults(results) {
  console.log('[Strategy Builder] Displaying backtest results:', results);
  currentBacktestResults = results;

  const modal = document.getElementById('backtestResultsModal');
  if (!modal) {
    console.error('[Strategy Builder] Results modal not found');
    return;
  }

  // Render summary cards
  renderResultsSummaryCards(results);

  // Render overview metrics
  renderOverviewMetrics(results);

  // Render trades table
  renderTradesTable(results.trades || []);

  // Render all metrics
  renderAllMetrics(results);

  // Show modal
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';

  // Initialize equity chart if data available
  if (results.equity_curve && results.equity_curve.length > 0) {
    setTimeout(() => renderEquityChart(results.equity_curve), 100);
  }
}

/**
 * Render summary cards at top of results
 */
function renderResultsSummaryCards(results) {
  const container = document.getElementById('resultsSummaryCards');
  if (!container) return;

  const metrics = results.metrics || results;
  const totalReturn = metrics.net_profit_pct || 0;
  const winRate = metrics.win_rate || 0;
  const maxDrawdown = metrics.max_drawdown || 0;
  const totalTrades = metrics.total_trades || 0;
  const profitFactor = metrics.profit_factor || 0;
  const sharpeRatio = metrics.sharpe_ratio || 0;

  const cards = [
    {
      icon: 'bi-cash-stack',
      value: `${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(2)}%`,
      label: 'Total Return',
      class: totalReturn >= 0 ? 'positive' : 'negative'
    },
    {
      icon: 'bi-trophy',
      value: `${winRate.toFixed(1)}%`,
      label: 'Win Rate',
      class: winRate >= 50 ? 'positive' : 'warning'
    },
    {
      icon: 'bi-graph-down-arrow',
      value: `${maxDrawdown.toFixed(2)}%`,
      label: 'Max Drawdown',
      class: maxDrawdown > 20 ? 'negative' : 'warning'
    },
    {
      icon: 'bi-arrow-left-right',
      value: totalTrades.toString(),
      label: 'Total Trades',
      class: 'neutral'
    },
    {
      icon: 'bi-bar-chart-line',
      value: profitFactor.toFixed(2),
      label: 'Profit Factor',
      class: profitFactor >= 1.5 ? 'positive' : profitFactor >= 1 ? 'warning' : 'negative'
    },
    {
      icon: 'bi-lightning',
      value: sharpeRatio.toFixed(2),
      label: 'Sharpe Ratio',
      class: sharpeRatio >= 1 ? 'positive' : sharpeRatio >= 0 ? 'warning' : 'negative'
    }
  ];

  container.innerHTML = cards.map(card => `
    <div class="summary-card ${card.class}">
      <i class="summary-card-icon bi ${card.icon}"></i>
      <span class="summary-card-value">${card.value}</span>
      <span class="summary-card-label">${card.label}</span>
    </div>
  `).join('');
}

/**
 * Render overview metrics grid
 */
function renderOverviewMetrics(results) {
  const container = document.getElementById('metricsOverview');
  if (!container) return;

  const metrics = results.metrics || results;

  const overviewCards = [
    { title: 'Net Profit', value: formatCurrency(metrics.net_profit || 0), icon: 'bi-currency-dollar', positive: (metrics.net_profit || 0) >= 0 },
    { title: 'Gross Profit', value: formatCurrency(metrics.gross_profit || 0), icon: 'bi-plus-circle', positive: true },
    { title: 'Gross Loss', value: formatCurrency(metrics.gross_loss || 0), icon: 'bi-dash-circle', positive: false },
    { title: 'Winning Trades', value: `${metrics.winning_trades || 0} / ${metrics.total_trades || 0}`, icon: 'bi-check-circle', positive: true },
    { title: 'Losing Trades', value: `${metrics.losing_trades || 0} / ${metrics.total_trades || 0}`, icon: 'bi-x-circle', positive: false },
    { title: 'Avg Win', value: formatPercent(metrics.avg_win || 0), icon: 'bi-arrow-up', positive: true },
    { title: 'Avg Loss', value: formatPercent(metrics.avg_loss || 0), icon: 'bi-arrow-down', positive: false },
    { title: 'Largest Win', value: formatPercent(metrics.largest_win || 0), icon: 'bi-star', positive: true },
    { title: 'Largest Loss', value: formatPercent(metrics.largest_loss || 0), icon: 'bi-exclamation-triangle', positive: false },
    { title: 'Avg Trade Duration', value: formatDuration(metrics.avg_trade_duration || 0), icon: 'bi-clock', positive: null },
    { title: 'Max Consecutive Wins', value: metrics.max_consecutive_wins || 0, icon: 'bi-graph-up', positive: true },
    { title: 'Max Consecutive Losses', value: metrics.max_consecutive_losses || 0, icon: 'bi-graph-down', positive: false }
  ];

  container.innerHTML = overviewCards.map(card => `
    <div class="metric-card ${card.positive === true ? 'positive' : card.positive === false ? 'negative' : ''}">
      <div class="metric-card-header">
        <span class="metric-card-title">${card.title}</span>
        <i class="metric-card-icon bi ${card.icon}"></i>
      </div>
      <div class="metric-card-value">${card.value}</div>
    </div>
  `).join('');
}

/**
 * Render trades table
 */
function renderTradesTable(trades) {
  const tbody = document.getElementById('tradesTableBody');
  if (!tbody) return;

  if (!trades || trades.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="11" class="text-center py-3">No trades to display</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = trades.map((trade, idx) => {
    const sideNorm = (trade.side || trade.direction || 'long').toLowerCase();
    const isLong = sideNorm === 'long' || sideNorm === 'buy';
    const pnl = trade.pnl || trade.profit || 0;
    const pnlPct = trade.pnl_pct || trade.profit_pct || 0;
    const mfe = trade.mfe || 0;
    const mae = trade.mae || 0;

    return `
      <tr>
        <td>${idx + 1}</td>
        <td>${formatDateTime(trade.entry_time || trade.open_time)}</td>
        <td>${formatDateTime(trade.exit_time || trade.close_time)}</td>
        <td class="${isLong ? 'trade-side-long' : 'trade-side-short'}">${isLong ? 'LONG' : 'SHORT'}</td>
        <td>${formatPrice(trade.entry_price || trade.open_price)}</td>
        <td>${formatPrice(trade.exit_price || trade.close_price)}</td>
        <td>${(trade.quantity || trade.qty || 0).toFixed(4)}</td>
        <td class="${pnl >= 0 ? 'trade-pnl-positive' : 'trade-pnl-negative'}">${formatCurrency(pnl)}</td>
        <td class="${pnlPct >= 0 ? 'trade-pnl-positive' : 'trade-pnl-negative'}">${pnlPct.toFixed(2)}%</td>
        <td>${mfe.toFixed(2)}%</td>
        <td>${mae.toFixed(2)}%</td>
      </tr>
    `;
  }).join('');
}

/**
 * Render all metrics organized by category
 */
function renderAllMetrics(results) {
  const container = document.getElementById('allMetricsGrid');
  if (!container) return;

  const metrics = results.metrics || results;

  const categories = [
    {
      title: 'Performance',
      icon: 'bi-speedometer2',
      items: [
        { label: 'Total Return', value: formatPercent(metrics.net_profit_pct) },
        { label: 'Net Profit', value: formatCurrency(metrics.net_profit) },
        { label: 'Gross Profit', value: formatCurrency(metrics.gross_profit) },
        { label: 'Gross Loss', value: formatCurrency(metrics.gross_loss) },
        { label: 'Profit Factor', value: (metrics.profit_factor || 0).toFixed(2) }
      ]
    },
    {
      title: 'Risk Metrics',
      icon: 'bi-shield-exclamation',
      items: [
        { label: 'Max Drawdown', value: formatPercent(metrics.max_drawdown) },
        { label: 'Max Drawdown $', value: formatCurrency(metrics.max_drawdown_value) },
        { label: 'Sharpe Ratio', value: (metrics.sharpe_ratio || 0).toFixed(2) },
        { label: 'Sortino Ratio', value: (metrics.sortino_ratio || 0).toFixed(2) },
        { label: 'Calmar Ratio', value: (metrics.calmar_ratio || 0).toFixed(2) }
      ]
    },
    {
      title: 'Trade Statistics',
      icon: 'bi-bar-chart',
      items: [
        { label: 'Total Trades', value: metrics.total_trades || 0 },
        { label: 'Winning Trades', value: metrics.winning_trades || 0 },
        { label: 'Losing Trades', value: metrics.losing_trades || 0 },
        { label: 'Win Rate', value: formatPercent(metrics.win_rate) },
        { label: 'Avg Win/Loss Ratio', value: (metrics.avg_win_loss_ratio || 0).toFixed(2) }
      ]
    },
    {
      title: 'Average Values',
      icon: 'bi-calculator',
      items: [
        { label: 'Avg Trade', value: formatPercent(metrics.avg_trade) },
        { label: 'Avg Trade $', value: formatCurrency(metrics.avg_trade_value) },
        { label: 'Avg Win', value: formatPercent(metrics.avg_win) },
        { label: 'Avg Win $', value: formatCurrency(metrics.avg_win_value) },
        { label: 'Avg Loss', value: formatPercent(metrics.avg_loss) },
        { label: 'Avg Loss $', value: formatCurrency(metrics.avg_loss_value) },
        { label: 'Largest Win', value: formatPercent(metrics.largest_win) },
        { label: 'Largest Win $', value: formatCurrency(metrics.largest_win_value) },
        { label: 'Largest Loss', value: formatPercent(metrics.largest_loss) },
        { label: 'Largest Loss $', value: formatCurrency(metrics.largest_loss_value) }
      ]
    },
    {
      title: 'Time Analysis',
      icon: 'bi-clock-history',
      items: [
        { label: 'Total Duration', value: formatDuration(metrics.total_duration) },
        { label: 'Avg Trade Duration', value: formatDuration(metrics.avg_trade_duration) },
        { label: 'Avg Win Duration', value: formatDuration(metrics.avg_win_duration) },
        { label: 'Avg Loss Duration', value: formatDuration(metrics.avg_loss_duration) },
        { label: 'Max Trade Duration', value: formatDuration(metrics.max_trade_duration) }
      ]
    },
    {
      title: 'Streaks',
      icon: 'bi-lightning-charge',
      items: [
        { label: 'Max Consecutive Wins', value: metrics.max_consecutive_wins || 0 },
        { label: 'Max Consecutive Losses', value: metrics.max_consecutive_losses || 0 },
        { label: 'Current Streak', value: metrics.current_streak || 0 },
        { label: 'Recovery Factor', value: (metrics.recovery_factor || 0).toFixed(2) },
        { label: 'Expectancy', value: formatCurrency(metrics.expectancy) }
      ]
    }
  ];

  container.innerHTML = categories.map(cat => `
    <div class="metrics-category">
      <h4 class="metrics-category-title">
        <i class="metrics-category-icon bi ${cat.icon}"></i>
        ${cat.title}
      </h4>
      <div class="metrics-list">
        ${cat.items.map(item => `
          <div class="metric-item">
            <span class="metric-item-label">${item.label}</span>
            <span class="metric-item-value">${item.value}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
}

/**
 * Render equity curve chart
 */
function renderEquityChart(equityCurve) {
  const canvas = document.getElementById('equityChart');
  if (!canvas || !equityCurve || equityCurve.length === 0) return;

  // Simple canvas rendering (no external chart library needed)
  const ctx = canvas.getContext('2d');
  const container = canvas.parentElement;
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;

  const padding = 40;
  const width = canvas.width - padding * 2;
  const height = canvas.height - padding * 2;

  // Extract values
  const values = equityCurve.map(p => p.equity || p.value || p);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  // Clear canvas
  ctx.fillStyle = '#161b22';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw grid
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding + (height * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }

  // Draw equity line
  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 2;
  ctx.beginPath();

  values.forEach((val, idx) => {
    const x = values.length <= 1
      ? padding + width / 2
      : padding + (idx / (values.length - 1)) * width;
    const y = range > 0
      ? padding + height - ((val - minVal) / range) * height
      : padding + height / 2;

    if (idx === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  // Fill area under curve
  ctx.lineTo(padding + width, padding + height);
  ctx.lineTo(padding, padding + height);
  ctx.closePath();
  ctx.fillStyle = 'rgba(88, 166, 255, 0.1)';
  ctx.fill();

  // Draw labels
  ctx.fillStyle = '#8b949e';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(formatCurrency(maxVal), padding - 5, padding + 5);
  ctx.fillText(formatCurrency(minVal), padding - 5, padding + height);
}

/**
 * Switch between result tabs
 */
function switchResultsTab(tabId) {
  // Update tab buttons
  document.querySelectorAll('.results-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabId);
  });

  // Update tab contents
  document.querySelectorAll('.results-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tab-${tabId}`);
  });

  // Re-render chart if equity tab
  if (tabId === 'equity' && currentBacktestResults) {
    setTimeout(() => renderEquityChart(currentBacktestResults.equity_curve), 100);
  }
}

/**
 * Close backtest results modal
 */
function closeBacktestResultsModal() {
  const modal = document.getElementById('backtestResultsModal');
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
}

/**
 * Export backtest results
 */
function exportBacktestResults() {
  if (!currentBacktestResults) {
    showNotification('No results to export', 'warning');
    return;
  }

  const dataStr = JSON.stringify(currentBacktestResults, null, 2);
  const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
  const filename = `backtest_results_${new Date().toISOString().slice(0, 10)}.json`;

  const link = document.createElement('a');
  link.href = dataUri;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  showNotification('Results exported successfully', 'success');
}

/**
 * View full results page
 */
function viewFullResults() {
  if (currentBacktestResults && currentBacktestResults.backtest_id) {
    window.location.href = `/frontend/backtest-results.html?backtest_id=${currentBacktestResults.backtest_id}`;
  } else {
    showNotification('No backtest ID available', 'warning');
  }
}

// Format helper functions for backtest results
// Note: formatCurrency is imported from utils.js

function formatPercent(value) {
  if (value === undefined || value === null) return '0.00%';
  return Number(value).toFixed(2) + '%';
}

function formatPrice(value) {
  if (value === undefined || value === null) return '0.00';
  return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 });
}

function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatDuration(seconds) {
  if (!seconds || seconds === 0) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${minutes}m`;
}

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
// AI BUILD MODAL — Strategy Builder integration
// Calls POST /api/v1/agents/advanced/builder/task
// ============================================

const AI_PRESETS = {
  rsi: {
    blocks: [
      { type: 'rsi', params: { period: 14, use_cross_level: true, cross_long_level: 30, cross_short_level: 70 } },
      { type: 'buy' },
      { type: 'sell' },
      { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
    ],
    connections: [
      // RSI long signal → buy, short signal → sell
      { source: 'rsi', source_port: 'long', target: 'buy', target_port: 'signal' },
      { source: 'rsi', source_port: 'short', target: 'sell', target_port: 'signal' }
    ]
  },
  ema_cross: {
    blocks: [
      { type: 'ema', params: { period: 9 }, id: 'ema_fast' },
      { type: 'ema', params: { period: 21 }, id: 'ema_slow' },
      { type: 'crossover', id: 'cross_up' },
      { type: 'crossunder', id: 'cross_down' },
      { type: 'buy' },
      { type: 'sell' },
      { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
    ],
    connections: [
      { source: 'ema_fast', source_port: 'value', target: 'cross_up', target_port: 'a' },
      { source: 'ema_slow', source_port: 'value', target: 'cross_up', target_port: 'b' },
      { source: 'ema_fast', source_port: 'value', target: 'cross_down', target_port: 'a' },
      { source: 'ema_slow', source_port: 'value', target: 'cross_down', target_port: 'b' },
      // Condition → Action wiring
      { source: 'cross_up', source_port: 'result', target: 'buy', target_port: 'signal' },
      { source: 'cross_down', source_port: 'result', target: 'sell', target_port: 'signal' }
    ]
  },
  macd: {
    blocks: [
      { type: 'macd', params: { fast_period: 12, slow_period: 26, signal_period: 9, use_macd_cross_signal: true } },
      { type: 'buy' },
      { type: 'sell' },
      { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
    ],
    connections: [
      { source: 'macd', source_port: 'long', target: 'buy', target_port: 'signal' },
      { source: 'macd', source_port: 'short', target: 'sell', target_port: 'signal' }
    ]
  },
  bb: {
    blocks: [
      { type: 'bollinger', params: { period: 20, std_dev: 2.0 } },
      { type: 'price', id: 'price' },
      { type: 'crossover', id: 'cross_up' },
      { type: 'crossunder', id: 'cross_down' },
      { type: 'buy' },
      { type: 'sell' },
      { type: 'static_sltp', id: 'sltp_1', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
    ],
    connections: [
      // Price crosses above lower band → buy signal
      { source: 'price', source_port: 'close', target: 'cross_up', target_port: 'a' },
      { source: 'bollinger', source_port: 'lower', target: 'cross_up', target_port: 'b' },
      // Price crosses below upper band → sell signal
      { source: 'price', source_port: 'close', target: 'cross_down', target_port: 'a' },
      { source: 'bollinger', source_port: 'upper', target: 'cross_down', target_port: 'b' },
      // Condition → Action wiring
      { source: 'cross_up', source_port: 'result', target: 'buy', target_port: 'signal' },
      { source: 'cross_down', source_port: 'result', target: 'sell', target_port: 'signal' }
    ]
  },
  custom: { blocks: [], connections: [] }
};

// Track AI Build mode: 'build' (from preset) or 'optimize' (existing canvas strategy)
let _aiBuildMode = 'build';
let _aiBuildExistingStrategyId = null;

function openAiBuildModal() {
  const modal = document.getElementById('aiBuildModal');
  modal.classList.remove('hidden');
  modal.style.display = 'flex';

  // Detect mode: if canvas has a saved strategy → optimize mode
  const existingId = getStrategyIdFromURL();
  const hasCanvasBlocks = strategyBlocks.length > 0;
  const stratName = document.getElementById('strategyName')?.value || 'New Strategy';

  if (existingId && hasCanvasBlocks) {
    _aiBuildMode = 'optimize';
    _aiBuildExistingStrategyId = existingId;
  } else {
    _aiBuildMode = 'build';
    _aiBuildExistingStrategyId = null;
  }

  // Update modal title based on mode
  const titleEl = modal.querySelector('.ai-build-header h3');
  if (titleEl) {
    titleEl.innerHTML = _aiBuildMode === 'optimize'
      ? '<i class="bi bi-stars"></i> AI Strategy Optimizer'
      : '<i class="bi bi-robot"></i> AI Strategy Builder';
  }

  // Show/hide preset section based on mode
  const presetHeading = modal.querySelector('.ai-build-preset-heading');
  const presetSelect = document.getElementById('aiPreset');
  const blocksPreview = document.getElementById('aiBlocksPreview');
  const isOptimize = _aiBuildMode === 'optimize';

  if (presetHeading) presetHeading.style.display = isOptimize ? 'none' : '';
  if (presetSelect) presetSelect.style.display = isOptimize ? 'none' : '';
  if (blocksPreview) {
    if (isOptimize) {
      // Show current canvas blocks as read-only info
      const blockTypes = strategyBlocks.map(b => b.type || b.blockType || '?');
      blocksPreview.textContent = `Текущие блоки на канвасе (${blockTypes.length}):\n` +
        blockTypes.map(t => `  • ${t}`).join('\n');
      blocksPreview.style.display = '';
    }
    // In build mode, applyAiPreset() handles this
  }

  // Update Build button text
  const btnRun = document.getElementById('btnRunAiBuild');
  if (btnRun) {
    btnRun.innerHTML = isOptimize
      ? '<i class="bi bi-stars"></i> Optimize & Backtest'
      : '<i class="bi bi-play-fill"></i> Build & Backtest';
  }

  // Populate summary from Parameters panel
  const symbol = document.getElementById('backtestSymbol')?.value || '';
  const timeframe = document.getElementById('strategyTimeframe')?.value || '15';
  const direction = document.getElementById('builderDirection')?.value || 'both';
  const capital = document.getElementById('backtestCapital')?.value || '10000';
  const leverage = document.getElementById('backtestLeverage')?.value || '10';
  const startDate = document.getElementById('backtestStartDate')?.value || '';
  const endDate = document.getElementById('backtestEndDate')?.value || '';
  const marketType = document.getElementById('builderMarketType')?.value || 'linear';

  const tfLabels = { '1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '240': '4h', 'D': '1D', 'W': '1W', 'M': '1M' };
  const dirLabels = { 'both': 'Long & Short', 'long': 'Long only', 'short': 'Short only' };
  const mktLabels = { 'linear': 'Futures', 'spot': 'SPOT' };

  const summaryEl = document.getElementById('aiBuildSummary');
  if (summaryEl) {
    let warning = '';
    if (!symbol) {
      warning = '<div class="summary-warning"><i class="bi bi-exclamation-triangle"></i> Выберите тикер в панели Параметры</div>';
    }
    let modeInfo = '';
    if (isOptimize) {
      modeInfo = `<div class="summary-row" style="background:#1a3a1a;border-radius:4px;padding:4px 8px;margin-bottom:4px;">
        <span class="summary-label"><i class="bi bi-stars"></i> Режим:</span>
        <span class="summary-value">Оптимизация «${stratName}»</span></div>`;
    }
    summaryEl.innerHTML = `
      ${modeInfo}
      <div class="summary-row"><span class="summary-label">Symbol:</span><span class="summary-value">${symbol || '—'}</span></div>
      <div class="summary-row"><span class="summary-label">Timeframe:</span><span class="summary-value">${tfLabels[timeframe] || timeframe}</span></div>
      <div class="summary-row"><span class="summary-label">Direction:</span><span class="summary-value">${dirLabels[direction] || direction}</span></div>
      <div class="summary-row"><span class="summary-label">Market:</span><span class="summary-value">${mktLabels[marketType] || marketType}</span></div>
      <div class="summary-row"><span class="summary-label">Capital:</span><span class="summary-value">$${parseFloat(capital).toLocaleString()}</span></div>
      <div class="summary-row"><span class="summary-label">Leverage:</span><span class="summary-value">${leverage}x</span></div>
      <div class="summary-row"><span class="summary-label">Period:</span><span class="summary-value">${startDate || '—'} → ${endDate || '—'}</span></div>
      ${warning}
    `;
  }

  // Pre-fill strategy name from Parameters
  const aiNameEl = document.getElementById('aiName');
  if (isOptimize) {
    // In optimize mode, keep the current strategy name
    if (aiNameEl) aiNameEl.value = stratName;
  } else {
    if (aiNameEl && (aiNameEl.value === 'AI RSI Strategy' || aiNameEl.value === 'New Strategy' || !aiNameEl.value)) {
      aiNameEl.value = stratName === 'New Strategy' ? 'AI RSI Strategy' : `AI ${stratName}`;
    }
  }

  if (!isOptimize) {
    applyAiPreset();
  }
}

function closeAiBuildModal() {
  const modal = document.getElementById('aiBuildModal');
  modal.classList.add('hidden');
  modal.style.display = '';
}

function applyAiPreset() {
  const presetSelect = document.getElementById('aiPreset');
  if (!presetSelect) return;
  const preset = AI_PRESETS[presetSelect.value];
  const preview = document.getElementById('aiBlocksPreview');
  if (preview && preset) {
    preview.textContent = JSON.stringify(preset.blocks, null, 2);
  }
}

function resetAiBuild() {
  document.getElementById('aiBuildConfig').classList.remove('hidden');
  document.getElementById('aiBuildProgress').classList.add('hidden');
  document.getElementById('aiBuildResults').classList.add('hidden');
  // Re-detect mode when modal is reset (user may have loaded a different strategy)
  _aiBuildMode = 'build';
  _aiBuildExistingStrategyId = null;
}

async function runAiBuild() {
  // Read values from Parameters panel (not from modal)
  const symbol = document.getElementById('backtestSymbol')?.value || '';
  const timeframe = document.getElementById('strategyTimeframe')?.value || '15';
  const direction = document.getElementById('builderDirection')?.value || 'both';
  const startDate = document.getElementById('backtestStartDate')?.value || '2025-01-01';
  const endDate = document.getElementById('backtestEndDate')?.value || '2025-06-01';
  const capital = parseFloat(document.getElementById('backtestCapital')?.value || '10000');
  const leverage = parseFloat(document.getElementById('backtestLeverage')?.value || '10');

  if (!symbol) {
    alert('Выберите тикер (Symbol) в панели Параметры');
    return;
  }

  // User description takes priority as the strategy name when present
  const descriptionEl = document.getElementById('aiDescription');
  const description = descriptionEl?.value?.trim() || '';
  const nameEl = document.getElementById('aiName');
  // If user typed a description, send it as the name so _plan_blocks() uses it
  const strategyName = description || nameEl?.value || 'AI Strategy';

  const payload = {
    name: strategyName,
    symbol: symbol,
    timeframe: timeframe,
    direction: direction,
    start_date: startDate,
    end_date: endDate,
    initial_capital: capital,
    leverage: leverage,
    max_iterations: parseInt(document.getElementById('aiMaxIter').value),
    min_sharpe: parseFloat(document.getElementById('aiMinSharpe').value),
    min_win_rate: 0.4,
    enable_deliberation: document.getElementById('aiDeliberation').checked
  };

  if (_aiBuildMode === 'optimize' && _aiBuildExistingStrategyId) {
    // Optimize mode: use existing strategy, skip creation/blocks/connections
    payload.existing_strategy_id = _aiBuildExistingStrategyId;
    payload.blocks = [];
    payload.connections = [];
  } else {
    const presetSelect = document.getElementById('aiPreset');
    const presetKey = presetSelect?.value || 'custom';
    if (description || presetKey === 'custom') {
      // Free-text description or "custom" → let LLM decide the blocks
      payload.blocks = [];
      payload.connections = [];
    } else {
      // Named preset selected → use hardcoded template as starting point
      const preset = AI_PRESETS[presetKey] || AI_PRESETS.rsi;
      payload.blocks = preset.blocks;
      payload.connections = preset.connections;
    }
  }

  // Show progress panel
  document.getElementById('aiBuildConfig').classList.add('hidden');
  document.getElementById('aiBuildProgress').classList.remove('hidden');
  const stageEl = document.getElementById('aiBuildStage');
  if (stageEl) {
    stageEl.textContent = _aiBuildMode === 'optimize'
      ? 'Optimizing strategy with AI agent…'
      : (description ? `Planning: "${description.substring(0, 60)}…"` : 'Building strategy with AI agent…');
  }

  try {
    await _runAiBuildWithSSE(payload);
  } catch (err) {
    document.getElementById('aiBuildProgress').classList.add('hidden');
    document.getElementById('aiBuildResults').classList.remove('hidden');
    document.getElementById('aiBuildResultContent').innerHTML =
      `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${escapeHtml(err.message)}</div>`;
  }
}

/**
 * Run the AI Build workflow using SSE streaming for live stage updates.
 * Falls back to plain POST if EventSource/fetch-SSE is unavailable.
 */
async function _runAiBuildWithSSE(payload) {
  const stageEl = document.getElementById('aiBuildStage');

  // Use fetch + ReadableStream to consume text/event-stream from a POST endpoint
  const response = await fetch('/api/v1/agents/advanced/builder/task/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    // Fallback: plain POST to non-streaming endpoint
    const fallback = await fetch('/api/v1/agents/advanced/builder/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!fallback.ok) throw new Error(`HTTP ${fallback.status}: ${fallback.statusText}`);
    const data = await fallback.json();
    await showAiBuildResults(data);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let streamDone = false;

  while (!streamDone) {
    const { done, value } = await reader.read();
    if (done) { streamDone = true; break; }

    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by double newline
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';  // keep incomplete last frame

    for (const frame of frames) {
      if (!frame.trim()) continue;
      let eventType = 'message';
      let dataStr = '';

      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim();
        else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
      }

      if (!dataStr) continue;

      try {
        const msg = JSON.parse(dataStr);

        if (eventType === 'stage' && stageEl) {
          stageEl.textContent = msg.label || msg.stage || '…';
        } else if (eventType === 'result') {
          await showAiBuildResults(msg);
          return;
        } else if (eventType === 'error') {
          throw new Error(msg.message || 'Unknown error from agent');
        }
        // heartbeat: ignore
      } catch (parseErr) {
        if (parseErr instanceof SyntaxError) continue;
        throw parseErr;
      }
    }
  }
}

async function showAiBuildResults(data) {
  document.getElementById('aiBuildProgress').classList.add('hidden');
  document.getElementById('aiBuildResults').classList.remove('hidden');

  const w = data.workflow || {};
  const _m = w.backtest_results?.metrics || {};
  const iters = w.iterations || [];
  const lastIter = iters[iters.length - 1] || {};
  const ok = data.success;

  const wasOptimize = _aiBuildMode === 'optimize';
  let html = `
    <div class="alert ${ok ? 'alert-success' : 'alert-warning'}">
      <strong>${ok ? (wasOptimize ? '✅ Strategy Optimized!' : '✅ Strategy Built!') : '⚠️ Below Target'}</strong>
      — ${w.status || 'unknown'} in ${(w.duration_seconds || 0).toFixed(1)}s
    </div>
    <table class="table table-sm table-bordered">
      <tr><td>Strategy ID</td><td><code>${w.strategy_id || '—'}</code></td></tr>
      <tr><td>Iterations</td><td>${iters.length}</td></tr>
      <tr><td>Sharpe Ratio</td><td>${(lastIter.sharpe_ratio || 0).toFixed(3)}</td></tr>
      <tr><td>Win Rate</td><td>${((lastIter.win_rate || 0) * 100).toFixed(1)}%</td></tr>
      <tr><td>Net Profit</td><td>$${(lastIter.net_profit || 0).toFixed(2)}</td></tr>
      <tr><td>Max Drawdown</td><td>${(lastIter.max_drawdown || 0).toFixed(2)}%</td></tr>
      <tr><td>Total Trades</td><td>${lastIter.total_trades || 0}</td></tr>
      <tr><td>Blocks Added</td><td>${(w.blocks_added || []).length}</td></tr>
      <tr><td>Connections</td><td>${(w.connections_made || []).length}</td></tr>
    </table>`;

  if (w.deliberation && w.deliberation.decision) {
    html += `
      <div class="alert alert-info mt-2">
        <strong>🤖 AI Deliberation</strong>
        (confidence: ${(w.deliberation.confidence * 100).toFixed(0)}%)<br>
        <small>${w.deliberation.decision.substring(0, 300)}...</small>
      </div>`;
  }

  if (w.errors && w.errors.length > 0) {
    html += '<div class="alert alert-danger mt-2"><strong>Errors:</strong><ul>';
    w.errors.forEach(function (e) { html += `<li>${e}</li>`; });
    html += '</ul></div>';
  }

  document.getElementById('aiBuildResultContent').innerHTML = html;

  // Load the built strategy onto the canvas so user sees the blocks
  console.log('[AI Build] Attempting to load strategy onto canvas:', w.strategy_id);

  if (w.strategy_id && typeof loadStrategy === 'function') {
    try {
      await loadStrategy(w.strategy_id);
      console.log('[AI Build] Strategy loaded onto canvas successfully:', w.strategy_id);

      // Update URL so page knows which strategy is active
      const newUrl = new URL(window.location);
      newUrl.searchParams.set('id', w.strategy_id);
      window.history.replaceState({}, '', newUrl);
      console.log('[AI Build] URL updated with strategy ID');
    } catch (err) {
      console.error('[AI Build] Failed to load strategy onto canvas:', err);
    }
  } else {
    console.error('[AI Build] Cannot load strategy - missing strategy_id or loadStrategy function');
  }
}

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
// MY STRATEGIES — List / Open / Clone / Delete
// ============================================

let _strategiesCache = [];
const _selectedStrategyIds = new Set();

/**
 * Fetch saved strategies from the backend API
 */
async function fetchStrategiesList() {
  try {
    const resp = await fetch('/api/v1/strategy-builder/strategies?page=1&page_size=100');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _strategiesCache = data.strategies || [];
    return _strategiesCache;
  } catch (err) {
    console.error('[My Strategies] Failed to fetch strategies:', err);
    showNotification('Failed to load strategies', 'error');
    return [];
  }
}

/**
 * Open the My Strategies modal and populate the list
 */
async function openMyStrategiesModal() {
  const modal = document.getElementById('myStrategiesModal');
  if (!modal) return;

  _selectedStrategyIds.clear();
  updateBatchDeleteUI();

  modal.classList.add('active');
  const listEl = document.getElementById('strategiesList');
  if (listEl) listEl.innerHTML = '<p class="text-muted text-center">Loading...</p>';

  const strategies = await fetchStrategiesList();
  renderStrategiesList(strategies);
}

/**
 * Close the My Strategies modal
 */
function closeMyStrategiesModal() {
  const modal = document.getElementById('myStrategiesModal');
  if (modal) modal.classList.remove('active');
  _selectedStrategyIds.clear();
}

/**
 * Render strategies into the list container
 */
function renderStrategiesList(strategies) {
  const listEl = document.getElementById('strategiesList');
  const countEl = document.getElementById('strategiesCount');
  if (!listEl) return;

  if (countEl) countEl.textContent = `${strategies.length} strategies`;

  if (strategies.length === 0) {
    listEl.innerHTML = `
      <div class="strategies-empty">
        <i class="bi bi-folder2"></i>
        <p>No saved strategies yet</p>
        <p class="text-sm mt-1">Use the Save button to save your first strategy</p>
      </div>`;
    updateBatchDeleteUI();
    return;
  }

  const currentId = getStrategyIdFromURL();

  listEl.innerHTML = strategies.map(s => {
    const updatedDate = s.updated_at
      ? new Date(s.updated_at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
      : '—';
    const isCurrent = s.id === currentId;
    const isSelected = _selectedStrategyIds.has(s.id);

    return `
      <div class="strategy-card${isCurrent ? ' current' : ''}${isSelected ? ' selected' : ''}" data-strategy-id="${s.id}">
        <div class="strategy-card-checkbox" data-checkbox-id="${s.id}">
          <input type="checkbox" ${isSelected ? 'checked' : ''} data-select-strategy="${s.id}" title="Select" />
        </div>
        <div class="strategy-card-info">
          <div class="strategy-card-name">${escapeHtml(s.name || 'Untitled')}${isCurrent ? ' <span class="badge-current">current</span>' : ''}</div>
          <div class="strategy-card-meta">
            ${s.symbol ? `<span><i class="bi bi-currency-exchange"></i> ${escapeHtml(s.symbol)}</span>` : ''}
            ${s.timeframe ? `<span><i class="bi bi-clock"></i> ${escapeHtml(s.timeframe)}</span>` : ''}
            <span><i class="bi bi-bricks"></i> ${s.block_count || 0} blocks</span>
            <span><i class="bi bi-calendar3"></i> ${updatedDate}</span>
          </div>
        </div>
        <div class="strategy-card-actions">
          <button class="btn-icon-sm" title="Open" data-action="open" data-id="${s.id}">
            <i class="bi bi-box-arrow-in-right"></i>
          </button>
          <button class="btn-icon-sm" title="Clone" data-action="clone" data-id="${s.id}" data-name="${escapeHtml(s.name || 'Untitled')}">
            <i class="bi bi-copy"></i>
          </button>
          <button class="btn-icon-sm btn-danger" title="Delete" data-action="delete" data-id="${s.id}" data-name="${escapeHtml(s.name || 'Untitled')}">
            <i class="bi bi-trash3"></i>
          </button>
        </div>
      </div>`;
  }).join('');

  // Event delegation for card actions (remove previous to avoid duplicates)
  listEl.removeEventListener('click', handleStrategyCardAction);
  listEl.addEventListener('click', handleStrategyCardAction);

  updateBatchDeleteUI();
}

/**
 * Handle click events on strategy cards (open / clone / delete / checkbox)
 */
async function handleStrategyCardAction(e) {
  try {
    // Handle checkbox clicks
    const checkbox = e.target.closest('[data-select-strategy]');
    if (checkbox) {
      e.stopPropagation();
      const strategyId = checkbox.dataset.selectStrategy;
      if (checkbox.checked) {
        _selectedStrategyIds.add(strategyId);
      } else {
        _selectedStrategyIds.delete(strategyId);
      }
      // Toggle selected class on card
      const card = checkbox.closest('.strategy-card');
      if (card) card.classList.toggle('selected', checkbox.checked);
      updateBatchDeleteUI();
      return;
    }

    // Handle checkbox container clicks (prevent card open)
    if (e.target.closest('.strategy-card-checkbox')) {
      return;
    }

    const actionBtn = e.target.closest('[data-action]');
    if (!actionBtn) {
      // Click on the card itself — open
      const card = e.target.closest('.strategy-card');
      if (card) {
        const id = card.dataset.strategyId;
        if (id) {
          closeMyStrategiesModal();
          await loadStrategy(id);
        }
      }
      return;
    }

    const action = actionBtn.dataset.action;
    const id = actionBtn.dataset.id;
    const name = actionBtn.dataset.name || 'Untitled';

    if (action === 'open') {
      closeMyStrategiesModal();
      await loadStrategy(id);
    } else if (action === 'clone') {
      await cloneStrategy(id, name);
    } else if (action === 'delete') {
      await deleteStrategyById(id, name);
    }
  } catch (err) {
    console.error('[Strategy Builder] handleStrategyCardAction error:', err);
    showNotification(`Ошибка: ${err.message}`, 'error');
  }
}

/**
 * Toggle select all / deselect all strategies
 */
function toggleSelectAll() {
  const selectAllCb = document.getElementById('strategiesSelectAll');
  const isChecked = selectAllCb?.checked || false;
  const visibleCards = document.querySelectorAll('.strategy-card[data-strategy-id]');

  visibleCards.forEach(card => {
    const strategyId = card.dataset.strategyId;
    const cb = card.querySelector('[data-select-strategy]');
    if (cb) cb.checked = isChecked;
    if (isChecked) {
      _selectedStrategyIds.add(strategyId);
      card.classList.add('selected');
    } else {
      _selectedStrategyIds.delete(strategyId);
      card.classList.remove('selected');
    }
  });

  updateBatchDeleteUI();
}

/**
 * Update the batch delete button visibility and count
 */
function updateBatchDeleteUI() {
  const btn = document.getElementById('btnBatchDelete');
  const countEl = document.getElementById('batchDeleteCount');
  const selectAllCb = document.getElementById('strategiesSelectAll');

  const count = _selectedStrategyIds.size;
  if (btn) btn.classList.toggle('hidden', count === 0);
  if (countEl) countEl.textContent = count;

  // Update select all checkbox state
  if (selectAllCb) {
    const visibleCards = document.querySelectorAll('.strategy-card[data-strategy-id]');
    const totalVisible = visibleCards.length;
    selectAllCb.checked = totalVisible > 0 && count >= totalVisible;
    selectAllCb.indeterminate = count > 0 && count < totalVisible;
  }
}

/**
 * Batch delete selected strategies
 */
async function batchDeleteSelected() {
  const count = _selectedStrategyIds.size;
  if (count === 0) return;

  if (!confirm(`Delete ${count} selected strateg${count === 1 ? 'y' : 'ies'}?\nThis action cannot be undone.`)) return;

  try {
    const resp = await fetch('/api/v1/strategy-builder/strategies/batch-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_ids: Array.from(_selectedStrategyIds) })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    console.log(`[SUCCESS] Deleted ${data.deleted_count} strategies`);
    showNotification(`Deleted ${data.deleted_count} strateg${data.deleted_count === 1 ? 'y' : 'ies'}`, 'success');

    // Clear selection and reload list from server (ensures UI stays in sync)
    _selectedStrategyIds.clear();
    _strategiesCache = null;
    const strategies = await fetchStrategiesList();
    renderStrategiesList(strategies);
    updateBatchDeleteUI();
  } catch (err) {
    console.error('[My Strategies] Batch delete failed:', err);
    showNotification('Failed to delete strategies', 'error');
  }
}

/**
 * Clone a strategy via backend API
 */
async function cloneStrategy(strategyId, originalName) {
  const newName = `${originalName} (copy)`;
  try {
    const resp = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}/clone?new_name=${encodeURIComponent(newName)}`, {
      method: 'POST'
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showNotification(`Strategy cloned as "${newName}"`, 'success');
    // Refresh the list
    const strategies = await fetchStrategiesList();
    renderStrategiesList(strategies);
  } catch (err) {
    console.error('[My Strategies] Clone failed:', err);
    showNotification('Failed to clone strategy', 'error');
  }
}

/**
 * Delete a strategy via backend API (with confirmation)
 */
async function deleteStrategyById(strategyId, name) {
  if (!confirm(`Delete strategy "${name}"?\nThis action cannot be undone.`)) return;

  try {
    const resp = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`, {
      method: 'DELETE'
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    showNotification(`Strategy "${name}" deleted`, 'success');
    _selectedStrategyIds.delete(strategyId);

    // Reload list from server to ensure UI stays in sync
    _strategiesCache = null;
    const strategies = await fetchStrategiesList();
    renderStrategiesList(strategies);
    updateBatchDeleteUI();
  } catch (err) {
    console.error('[My Strategies] Delete failed:', err);
    showNotification('Failed to delete strategy', 'error');
  }
}

/**
 * Filter strategies list by search input
 */
function filterStrategiesList() {
  const query = (document.getElementById('strategiesSearch')?.value || '').toLowerCase().trim();
  if (!query) {
    renderStrategiesList(_strategiesCache);
    return;
  }
  const filtered = _strategiesCache.filter(s =>
    (s.name || '').toLowerCase().includes(query) ||
    (s.symbol || '').toLowerCase().includes(query) ||
    (s.timeframe || '').toLowerCase().includes(query)
  );
  renderStrategiesList(filtered);
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

// LocalStorage persistence functions
window.tryLoadFromLocalStorage = tryLoadFromLocalStorage;
window.clearLocalStorageDraft = clearLocalStorageDraft;
window.clearAllAndReset = clearAllAndReset;
window.resetFormToDefaults = resetFormToDefaults;

// Modal functions
window.openTemplatesModal = openTemplatesModal;
window.closeTemplatesModal = closeTemplatesModal;
window.selectTemplate = selectTemplate;
window.loadSelectedTemplate = loadSelectedTemplate;
window.renderTemplates = renderTemplates;
window.loadTemplateData = loadTemplateData;

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

// Export for frontend tests (ticker sync flow)
export { syncSymbolData, runCheckSymbolDataForProperties };
