/**
 * 📄 Strategies Page - Strategy CRUD Operations
 *
 * Handles Create, Read, Update, Delete operations for strategies
 *
 * @version 1.0.0
 * @date 2025-12-23
 */

import {
  escapeHtml,
  formatPercent,
  getReturnClass,
  showToast,
} from "./utils.js";
import {
  updateLeverageDisplay,
  updateLeverageLimits,
} from "./leverageManager.js";

const API_BASE = "/api/v1";

/** Единый набор таймфреймов: 1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M */
const BYBIT_INTERVALS = new Set(["1", "5", "15", "30", "60", "240", "D", "W", "M"]);

/** Маппинг устаревших TF на ближайший из стандартного набора */
const LEGACY_TF_MAP = { "3": "5", "120": "60", "360": "240", "720": "D" };

/**
 * Normalize stored timeframe (e.g. 1h, 15m) to Bybit dropdown value (60, 15).
 * @param {string} tf - Timeframe from API or storage
 * @returns {string} Value for #strategyTimeframe select
 */
function normalizeTimeframeForDropdown(tf) {
  if (!tf) return "60";
  const s = String(tf).trim();
  if (BYBIT_INTERVALS.has(s)) return s;
  if (LEGACY_TF_MAP[s]) return LEGACY_TF_MAP[s];
  const map = {
    "1m": "1", "3m": "5", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "60", "4h": "240", "6h": "240", "12h": "D",
    "1d": "D", "1D": "D", "1w": "W", "1W": "W", "1M": "M", "M": "M",
  };
  return map[s] ?? "60";
}

// State
let strategies = [];
let strategyTypes = [];
let _editingStrategyId = null; // Prefixed with _ to indicate intentionally unused for now
const _deletingIds = new Set(); // Track IDs currently being deleted to prevent double-delete

// Callbacks for UI updates
let updateParametersUICallback = null;
let getParametersFromUICallback = null;
let updatePositionSizeInputCallback = null;

/**
 * Set UI callbacks (injected from main module)
 */
export function setUICallbacks(callbacks) {
  updateParametersUICallback = callbacks.updateParametersUI;
  getParametersFromUICallback = callbacks.getParametersFromUI;
  updatePositionSizeInputCallback = callbacks.updatePositionSizeInput;
}

/**
 * Get current strategies list
 * @returns {Array} Strategies array
 */
export function getStrategies() {
  return strategies;
}

/**
 * Get strategy types
 * @returns {Array} Strategy types array
 */
export function getStrategyTypes() {
  return strategyTypes;
}

/**
 * Load strategies from API
 */
export async function loadStrategies() {
  try {
    const params = new URLSearchParams();
    const search = document.getElementById("searchInput")?.value;
    const status = document.getElementById("statusFilter")?.value;
    const type = document.getElementById("typeFilter")?.value;

    if (search) params.append("search", search);
    if (status) params.append("status", status);
    if (type) params.append("strategy_type", type);

    // Add cache buster to prevent browser caching stale data
    params.append("_t", Date.now());

    const response = await fetch(`${API_BASE}/strategies/?${params}`, {
      cache: "no-store",
      headers: {
        "Cache-Control": "no-cache",
      },
    });
    const data = await response.json();
    strategies = data.items || [];
    console.log(
      "[loadStrategies] Loaded",
      strategies.length,
      "strategies from API",
    );
    renderStrategies();
  } catch (error) {
    showToast("Failed to load strategies: " + error.message, "error");
    const container = document.getElementById("strategiesContainer");
    if (container) {
      container.innerHTML = `
                <div class="empty-state">
                    <h3>Error loading strategies</h3>
                    <p>${error.message}</p>
                </div>
            `;
    }
  }
}

/**
 * Load strategy types from API
 */
export async function loadStrategyTypes() {
  try {
    const response = await fetch(`${API_BASE}/strategies/types`);
    strategyTypes = await response.json();
  } catch (error) {
    console.error("Failed to load strategy types:", error);
  }
}

/**
 * Render strategies list to DOM
 */
export function renderStrategies() {
  const container = document.getElementById("strategiesContainer");
  if (!container) return;

  if (strategies.length === 0) {
    container.innerHTML = `
            <div class="empty-state">
                <h3>No strategies found</h3>
                <p>Create your first trading strategy using the "+ New Strategy" button above.</p>
            </div>
        `;
    return;
  }

  container.innerHTML = strategies
    .map(
      (strategy) => `
        <div class="strategy-card">
            <div class="strategy-header">
                <div>
                    <div class="strategy-title">${escapeHtml(strategy.name)}</div>
                    <span class="strategy-type">${strategy.strategy_type}</span>
                </div>
                <span class="strategy-status status-${strategy.status}">${strategy.status}</span>
            </div>

            <div class="strategy-meta">
                <span>📈 ${strategy.symbol || "BTCUSDT"}</span>
                <span>⏱ ${strategy.timeframe || "60"}</span>
                <span>💰 $${(strategy.initial_capital || 10000).toLocaleString()}</span>
            </div>

            <div class="strategy-metrics">
                <div class="metric">
                    <div class="metric-value ${getReturnClass(strategy.total_return)}">
                        ${formatPercent(strategy.total_return)}
                    </div>
                    <div class="metric-label">Return</div>
                </div>
                <div class="metric">
                    <div class="metric-value">
                        ${strategy.sharpe_ratio?.toFixed(2) || "-"}
                    </div>
                    <div class="metric-label">Sharpe</div>
                </div>
                <div class="metric">
                    <div class="metric-value">
                        ${formatPercent(strategy.win_rate, false)}
                    </div>
                    <div class="metric-label">Win Rate</div>
                </div>
            </div>

            <div class="strategy-actions">
                <button class="btn btn-sm btn-primary" data-action="backtest" data-id="${strategy.id}">
                    ▶ Backtest
                </button>
                <button class="btn btn-sm btn-secondary" data-action="edit" data-id="${strategy.id}">
                    ✏️ Edit
                </button>
                <button class="btn btn-sm btn-secondary" data-action="duplicate" data-id="${strategy.id}">
                    📋 Copy
                </button>
                ${
                  strategy.status === "active"
                    ? `<button class="btn btn-sm btn-secondary" data-action="pause" data-id="${strategy.id}">⏸ Pause</button>`
                    : `<button class="btn btn-sm btn-secondary" data-action="activate" data-id="${strategy.id}">▶ Activate</button>`
                }
                <button class="btn btn-sm btn-danger" data-action="delete" data-id="${strategy.id}">
                    🗑
                </button>
            </div>
        </div>
    `,
    )
    .join("");
}

/**
 * Open create strategy modal
 */
export function openCreateModal() {
  _editingStrategyId = null;
  const modalTitle = document.getElementById("modalTitle");
  const form = document.getElementById("strategyForm");
  const idField = document.getElementById("strategyId");
  const modal = document.getElementById("strategyModal");

  if (modalTitle) modalTitle.textContent = "Создание стратегии";
  if (form) form.reset();
  if (idField) idField.value = "";

  updateLeverageDisplay(1);
  updateLeverageLimits().catch((err) =>
    console.warn("Leverage limits init error:", err),
  );

  if (updateParametersUICallback) updateParametersUICallback();
  if (modal) modal.classList.add("active");
}

/**
 * Close strategy modal
 */
export function closeModal() {
  const modal = document.getElementById("strategyModal");
  if (modal) modal.classList.remove("active");
}

/**
 * Edit existing strategy
 * @param {string} id - Strategy UUID
 */
export async function editStrategy(id) {
  try {
    const response = await fetch(`${API_BASE}/strategies/${id}`);
    const strategy = await response.json();

    _editingStrategyId = id;

    // Set form values
    const setVal = (elId, val) => {
      const el = document.getElementById(elId);
      if (el) el.value = val;
    };

    document.getElementById("modalTitle").textContent =
      "Редактирование стратегии";
    setVal("strategyId", id);
    setVal("strategyName", strategy.name);
    setVal("strategyType", strategy.strategy_type);
    setVal("strategyStatus", strategy.status);
    setVal("strategySymbol", strategy.symbol || "BTCUSDT");
    setVal("strategyTimeframe", normalizeTimeframeForDropdown(strategy.timeframe) || "60");
    setVal("strategyCapital", strategy.initial_capital || 10000);
    // TP/SL are now in extended fields (common TP/SL section)
    setVal("strategyTargetProfit", strategy.take_profit_pct || 1);
    setVal("strategyStopLoss", strategy.stop_loss_pct || 10);

    // Read trading settings from parameters
    const params = strategy.parameters || {};
    const positionSizeType = params._position_size_type || "percent";
    setVal("strategyDirection", params._direction || "both");
    setVal("strategyPositionSizeType", positionSizeType);

    // Set position size value based on type
    if (positionSizeType === "percent") {
      setVal("strategyPositionSize", (strategy.position_size || 1) * 100);
    } else {
      setVal("strategyPositionSize", params._order_amount || 100);
    }

    // Update position size input label/limits
    if (updatePositionSizeInputCallback) updatePositionSizeInputCallback();

    // Set leverage value BEFORE updating limits (so limits calculation uses correct value)
    const leverageVal = params._leverage || 1;
    setVal("strategyLeverage", leverageVal);
    updateLeverageDisplay(leverageVal);

    // Now update leverage limits (will read the correct leverage value)
    await updateLeverageLimits();

    // Other advanced parameters
    setVal("strategyPyramiding", params._pyramiding || 1);
    setVal("strategyCommission", (params._commission || 0.001) * 100);
    setVal("strategySlippage", (params._slippage || 0.0005) * 100);

    // TradingView-like simulation settings
    setVal(
      "strategyBarMagnifier",
      params._bar_magnifier === true ? "true" : "false",
    );
    setVal("strategyFillMode", params._fill_mode || "next_bar_open");
    setVal("strategyMaxDrawdown", params._max_drawdown || 0);

    // Engine type selection
    setVal("strategyEngineType", params._engine_type || "auto");

    // Market type selection (SPOT for TradingView parity, LINEAR for futures)
    setVal("strategyMarketType", params._market_type || "linear");

    // DCA/Grid parameters
    setVal("dcaCoverage", params._dca_coverage || 10);
    setVal("dcaGridOrders", params._dca_grid_orders || 5);
    setVal("dcaMartingale", params._dca_martingale || 0);
    // Offset type (market/limit)
    const offsetType = params._dca_offset_type || "market";
    setVal("dcaOffsetType", offsetType);
    const offsetInput = document.getElementById("dcaOffset");
    if (offsetInput) {
      offsetInput.disabled = offsetType === "market";
      offsetInput.value =
        offsetType === "market" ? 0 : params._dca_offset || 0.1;
    }
    const logCheckbox = document.getElementById("dcaLogarithmic");
    if (logCheckbox) logCheckbox.checked = params._dca_logarithmic || false;
    setVal("dcaLogCoefficient", params._dca_log_coefficient || 1.2);
    setVal("dcaPartialGrid", params._dca_partial_grid || 5);
    setVal("dcaTrailing", params._dca_trailing || 0);

    // Veles-style parameters
    setVal("dcaMaxActiveSO", params._dca_max_active_so || 0);
    setVal("dcaGridTrailing", params._dca_grid_trailing || 0);
    setVal("dcaMaxDeals", params._dca_max_deals || 0);
    // TP Signal Mode
    const tpSignalModeSelect = document.getElementById("dcaTpSignalMode");
    if (tpSignalModeSelect)
      tpSignalModeSelect.value = params._dca_tp_signal_mode || "disabled";
    setVal("dcaTpSignalRsiExit", params._dca_tp_signal_rsi_exit || 70);
    // Grid Coverage + Orders Count
    setVal("dcaGridCoverage", params._dca_grid_coverage || 10);
    setVal("dcaGridOrdersCount", params._dca_grid_orders_count || 10);
    // First Order Offset + Log Distribution
    setVal("dcaFirstOrderOffset", params._dca_first_order_offset || 0);
    setVal("dcaLogDistribution", params._dca_log_distribution || 1);

    // New Veles-style parameters (duplicates removed - use global direction/leverage/deposit)
    setVal("dcaTradingMode", params._dca_trading_mode || "simple");
    setVal("dcaEntryCondition", params._dca_entry_condition || "rsi");
    setVal("dcaTpMode", params._dca_tp_mode || "simple");
    setVal(
      "dcaTpTrailingEnabled",
      params._dca_tp_trailing_enabled ? "true" : "false",
    );
    setVal("dcaTpTrailingPct", params._dca_tp_trailing_pct || 0.5);
    setVal("dcaSlEnabled", params._dca_sl_enabled ? "true" : "false");
    setVal("dcaTpMinPnl", params._dca_tp_min_pnl || 0.5);

    // Show/hide DCA section based on strategy type
    const dcaSection = document.getElementById("dcaParametersSection");
    const pyramidingTypes = ["dca"];
    if (dcaSection) {
      dcaSection.style.display = pyramidingTypes.includes(
        strategy.strategy_type,
      )
        ? "block"
        : "none";
    }
    // Show/hide log coefficient
    const logCoefGroup = document.getElementById("dcaLogCoefficientGroup");
    if (logCoefGroup && logCheckbox) {
      logCoefGroup.style.display = logCheckbox.checked ? "block" : "none";
    }

    // Update strategy-specific parameters - filter out _prefixed
    const strategyParams = {};
    for (const [key, value] of Object.entries(params)) {
      if (!key.startsWith("_")) {
        strategyParams[key] = value;
      }
    }
    if (updateParametersUICallback) updateParametersUICallback(strategyParams);

    document.getElementById("strategyModal").classList.add("active");
  } catch (error) {
    showToast("Ошибка загрузки стратегии: " + error.message, "error");
  }
}

/**
 * Save strategy (create or update)
 */
export async function saveStrategy() {
  const id = document.getElementById("strategyId")?.value;

  // Get strategy-specific parameters
  const strategyParams = getParametersFromUICallback
    ? getParametersFromUICallback()
    : {};

  // Get position size type and value
  const positionSizeType =
    document.getElementById("strategyPositionSizeType")?.value || "percent";
  const positionSizeValue =
    parseFloat(document.getElementById("strategyPositionSize")?.value) || 100;

  // Get strategy type and direction for validation
  const strategyType = document.getElementById("strategyType")?.value;
  const direction =
    document.getElementById("strategyDirection")?.value || "both";

  // =========================================================================
  // VALIDATION: DCA strategy is uni-directional
  // =========================================================================
  const pyramidingStrategies = ["dca"];
  if (pyramidingStrategies.includes(strategyType) && direction === "both") {
    showToast(
      '❌ Ошибка: Стратегия DCA работает только в одном направлении. Выберите "Только Long" или "Только Short".',
      "error",
    );
    return; // Stop save
  }

  // Calculate position_size for DB
  let positionSizeForDB = 1.0;
  let orderAmount = null;

  if (positionSizeType === "percent") {
    positionSizeForDB = positionSizeValue / 100;
  } else if (
    positionSizeType === "fixed_amount" ||
    positionSizeType === "contracts"
  ) {
    orderAmount = positionSizeValue;
    positionSizeForDB = 1.0;
  }

  // Add trading settings to parameters
  const allParameters = {
    ...strategyParams,
    _direction: document.getElementById("strategyDirection")?.value || "both",
    _leverage:
      parseInt(document.getElementById("strategyLeverage")?.value) || 1,
    _pyramiding:
      parseInt(document.getElementById("strategyPyramiding")?.value) || 1,
    _commission:
      parseFloat(document.getElementById("strategyCommission")?.value) / 100 ||
      0.001,
    _slippage:
      parseFloat(document.getElementById("strategySlippage")?.value) / 100 ||
      0.0005,
    _position_size_type: positionSizeType,
    _order_amount: orderAmount,
    // TradingView-like simulation settings
    _bar_magnifier:
      document.getElementById("strategyBarMagnifier")?.value === "true",
    _fill_mode:
      document.getElementById("strategyFillMode")?.value || "next_bar_open",
    _max_drawdown:
      parseFloat(document.getElementById("strategyMaxDrawdown")?.value) || 0,
    // Engine type selection (GPU, Numba, Fallback, Auto)
    _engine_type:
      document.getElementById("strategyEngineType")?.value || "auto",
    // Market type selection (SPOT for TradingView parity, LINEAR for futures)
    _market_type:
      document.getElementById("strategyMarketType")?.value || "linear",
    // DCA/Grid parameters
    _dca_coverage:
      parseFloat(document.getElementById("dcaCoverage")?.value) || 10,
    _dca_grid_orders:
      parseInt(document.getElementById("dcaGridOrders")?.value) || 5,
    _dca_martingale:
      parseFloat(document.getElementById("dcaMartingale")?.value) || 0,
    _dca_offset_type:
      document.getElementById("dcaOffsetType")?.value || "market",
    _dca_offset:
      document.getElementById("dcaOffsetType")?.value === "market"
        ? 0
        : parseFloat(document.getElementById("dcaOffset")?.value) || 0.1,
    _dca_logarithmic:
      document.getElementById("dcaLogarithmic")?.checked || false,
    _dca_log_coefficient:
      parseFloat(document.getElementById("dcaLogCoefficient")?.value) || 1.2,
    _dca_partial_grid:
      parseInt(document.getElementById("dcaPartialGrid")?.value) || 5,
    _dca_trailing:
      parseFloat(document.getElementById("dcaTrailing")?.value) || 0,
    // Veles-style parameters
    _dca_max_active_so:
      parseInt(document.getElementById("dcaMaxActiveSO")?.value) || 0,
    _dca_grid_trailing:
      parseFloat(document.getElementById("dcaGridTrailing")?.value) || 0,
    _dca_max_deals:
      parseInt(document.getElementById("dcaMaxDeals")?.value) || 0,
    // TP Signal Mode
    _dca_tp_signal_mode:
      document.getElementById("dcaTpSignalMode")?.value || "disabled",
    _dca_tp_signal_rsi_exit:
      parseInt(document.getElementById("dcaTpSignalRsiExit")?.value) || 70,
    // Grid Coverage + Orders Count
    _dca_grid_coverage:
      parseFloat(document.getElementById("dcaGridCoverage")?.value) || 10,
    _dca_grid_orders_count:
      parseInt(document.getElementById("dcaGridOrdersCount")?.value) || 10,
    // First Order Offset + Log Distribution
    _dca_first_order_offset:
      parseFloat(document.getElementById("dcaFirstOrderOffset")?.value) || 0,
    _dca_log_distribution:
      parseFloat(document.getElementById("dcaLogDistribution")?.value) || 1,
    // New Veles-style parameters (duplicates removed - use global direction/leverage/deposit)
    _dca_trading_mode:
      document.getElementById("dcaTradingMode")?.value || "simple",
    _dca_entry_condition:
      document.getElementById("dcaEntryCondition")?.value || "rsi",
    _dca_tp_mode: document.getElementById("dcaTpMode")?.value || "simple",
    _dca_tp_trailing_enabled:
      document.getElementById("dcaTpTrailingEnabled")?.value === "true",
    _dca_tp_trailing_pct:
      parseFloat(document.getElementById("dcaTpTrailingPct")?.value) || 0.5,
    _dca_sl_enabled: document.getElementById("dcaSlEnabled")?.value === "true",
    _dca_tp_min_pnl:
      parseFloat(document.getElementById("dcaTpMinPnl")?.value) || 0.5,
  };

  const data = {
    name: document.getElementById("strategyName")?.value,
    strategy_type: document.getElementById("strategyType")?.value,
    status: document.getElementById("strategyStatus")?.value,
    symbol: document.getElementById("strategySymbol")?.value || "BTCUSDT",
    timeframe: document.getElementById("strategyTimeframe")?.value || "60",
    initial_capital:
      parseFloat(document.getElementById("strategyCapital")?.value) || 10000,
    position_size: positionSizeForDB,
    stop_loss_pct:
      parseFloat(document.getElementById("strategyStopLoss")?.value) || null,
    take_profit_pct:
      parseFloat(document.getElementById("strategyTargetProfit")?.value) ||
      null,
    parameters: allParameters,
  };

  try {
    const url = id ? `${API_BASE}/strategies/${id}` : `${API_BASE}/strategies/`;
    const method = id ? "PUT" : "POST";

    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Ошибка сохранения стратегии");
    }

    closeModal();
    await loadStrategies();
    showToast(id ? "Стратегия обновлена!" : "Стратегия создана!", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

/**
 * Delete strategy
 * @param {string} id - Strategy UUID
 */
export async function deleteStrategy(id) {
  console.log("[deleteStrategy] Called with id:", id);

  // Prevent double-delete: if already deleting this ID, ignore
  if (_deletingIds.has(id)) {
    console.log("[deleteStrategy] Already deleting this ID, skipping");
    return;
  }

  if (!confirm("Вы уверены, что хотите удалить эту стратегию?")) {
    console.log("[deleteStrategy] User cancelled");
    return;
  }

  // Mark as deleting
  _deletingIds.add(id);

  try {
    console.log("[deleteStrategy] User confirmed, starting delete...");

    // Optimistic UI: remove card immediately from DOM
    const card = document
      .querySelector(`button[data-id="${id}"]`)
      ?.closest(".strategy-card");
    console.log("[deleteStrategy] Found card:", !!card);

    if (card) {
      card.style.transition = "opacity 0.3s, transform 0.3s";
      card.style.opacity = "0";
      card.style.transform = "scale(0.95)";
      // Disable all buttons on the card to prevent re-clicks
      card.querySelectorAll("button").forEach((btn) => (btn.disabled = true));
    }

    // IMMEDIATELY remove from local array to prevent ghost items
    const originalStrategies = [...strategies];
    strategies = strategies.filter((s) => s.id !== id);
    console.log(
      "[deleteStrategy] Filtered local array, was:",
      originalStrategies.length,
      "now:",
      strategies.length,
    );

    // Use permanent=true to actually delete from database, not just soft delete
    const url = `${API_BASE}/strategies/${id}?permanent=true`;
    console.log("[deleteStrategy] Calling API:", url);

    const response = await fetch(url, { method: "DELETE" });
    console.log(
      "[deleteStrategy] API response status:",
      response.status,
      response.ok,
    );

    if (!response.ok) {
      // Restore on failure (but only if not 404 - already deleted)
      if (response.status !== 404) {
        strategies = originalStrategies;
        if (card) {
          card.style.opacity = "1";
          card.style.transform = "scale(1)";
          card
            .querySelectorAll("button")
            .forEach((btn) => (btn.disabled = false));
        }
      }
      const errorText = await response.text();
      console.error("[deleteStrategy] API error:", errorText);

      // If 404, it's already deleted - treat as success
      if (response.status === 404) {
        console.log(
          "[deleteStrategy] 404 = already deleted, treating as success",
        );
      } else {
        throw new Error("Ошибка удаления: " + response.status);
      }
    }

    // Remove card from DOM immediately
    if (card) {
      card.remove();
      console.log("[deleteStrategy] Card removed from DOM");
    }

    showToast("Стратегия удалена", "success");

    // Don't reload - card is already removed from DOM and array is updated
    // This prevents stale data from cache appearing
    console.log(
      "[deleteStrategy] Completed, remaining strategies:",
      strategies.length,
    );
  } catch (error) {
    console.error("[deleteStrategy] Error:", error);
    showToast(error.message, "error");
  } finally {
    // Always remove from deleting set
    _deletingIds.delete(id);
  }
}

/**
 * Duplicate strategy
 * @param {string} id - Strategy UUID
 */
export async function duplicateStrategy(id) {
  try {
    const response = await fetch(`${API_BASE}/strategies/${id}/duplicate`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Ошибка дублирования");

    showToast("Стратегия скопирована!", "success");
    await loadStrategies();
  } catch (error) {
    showToast(error.message, "error");
  }
}

/**
 * Activate strategy
 * @param {string} id - Strategy UUID
 */
export async function activateStrategy(id) {
  try {
    const response = await fetch(`${API_BASE}/strategies/${id}/activate`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Ошибка активации");

    showToast("Стратегия активирована!", "success");
    await loadStrategies();
  } catch (error) {
    showToast(error.message, "error");
  }
}

/**
 * Pause strategy
 * @param {string} id - Strategy UUID
 */
export async function pauseStrategy(id) {
  try {
    const response = await fetch(`${API_BASE}/strategies/${id}/pause`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Ошибка паузы");

    showToast("Стратегия приостановлена", "success");
    await loadStrategies();
  } catch (error) {
    showToast(error.message, "error");
  }
}

// Expose to global scope for backwards compatibility
if (typeof window !== "undefined") {
  window.loadStrategies = loadStrategies;
  window.openCreateModal = openCreateModal;
  window.closeModal = closeModal;
  window.editStrategy = editStrategy;
  window.saveStrategy = saveStrategy;
  window.deleteStrategy = deleteStrategy;
  window.duplicateStrategy = duplicateStrategy;
  window.activateStrategy = activateStrategy;
  window.pauseStrategy = pauseStrategy;
}
