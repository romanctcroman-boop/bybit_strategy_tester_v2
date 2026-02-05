/**
 * 📄 Strategies Page JavaScript (Refactored)
 *
 * Main entry point for strategies.html
 * Imports modular components for better maintainability
 *
 * @version 2.0.0
 * @date 2025-01-10
 */

// Import shared utilities
import { debounce } from "../utils.js";

// Import strategy modules
import {
  // Utils
  formatNumber,
  getFreshnessIcon,
  getFreshnessText,
  // Leverage manager
  initLeverageSliderScroll,
  updateLeverageLimits,
  // Backtest manager
  openBacktestModal,
  closeBacktestModal,
  initPeriodButtons,
  runOptimization,
  runBacktest,
  cancelOptimization,
  updateCombinationsCount,
  // Strategy CRUD
  loadStrategies,
  loadStrategyTypes,
  renderStrategies,
  openCreateModal,
  closeModal,
  editStrategy,
  saveStrategy,
  deleteStrategy,
  duplicateStrategy,
  activateStrategy,
  pauseStrategy,
  setUICallbacks,
  getStrategyTypes,
} from "./strategies/index.js";

const API_BASE = "/api/v1";
const topSymbols = []; // Cache for top symbols (modified via push)

// Forward declaration for checkSymbolData (used before definition due to module structure)
let checkSymbolData;

// =============================================================================
// INITIALIZATION
// =============================================================================

function init() {
  console.log("[strategies.js] init() called");

  try {
    // Wire up callbacks between modules
    setUICallbacks({
      updateParametersUI,
      getParametersFromUI,
      updatePositionSizeInput,
    });
    console.log("[strategies.js] setUICallbacks done");
  } catch (e) {
    console.error("[strategies.js] setUICallbacks FAILED:", e);
  }

  try {
    // Expose loadStrategies globally for use in backtestManager
    window.loadStrategies = loadStrategies;
    console.log("[strategies.js] exposed loadStrategies");
  } catch (e) {
    console.error("[strategies.js] expose loadStrategies FAILED:", e);
  }

  try {
    loadStrategies();
    console.log("[strategies.js] loadStrategies started");
  } catch (e) {
    console.error("[strategies.js] loadStrategies FAILED:", e);
  }

  try {
    loadStrategyTypes();
    console.log("[strategies.js] loadStrategyTypes started");
  } catch (e) {
    console.error("[strategies.js] loadStrategyTypes FAILED:", e);
  }

  try {
    loadTopSymbols();
    console.log("[strategies.js] loadTopSymbols started");
  } catch (e) {
    console.error("[strategies.js] loadTopSymbols FAILED:", e);
  }

  try {
    setupFilters();
    console.log("[strategies.js] setupFilters done");
  } catch (e) {
    console.error("[strategies.js] setupFilters FAILED:", e);
  }

  try {
    setDefaultDates();
    console.log("[strategies.js] setDefaultDates done");
  } catch (e) {
    console.error("[strategies.js] setDefaultDates FAILED:", e);
  }

  try {
    setupEventListeners();
    console.log("[strategies.js] setupEventListeners done");
  } catch (e) {
    console.error("[strategies.js] setupEventListeners FAILED:", e);
  }

  try {
    initLeverageSliderScroll();
    console.log("[strategies.js] initLeverageSliderScroll done");
  } catch (e) {
    console.error("[strategies.js] initLeverageSliderScroll FAILED:", e);
  }

  console.log("[strategies.js] init() completed");
}

// Handle both cases: DOM already loaded (ES6 module timing) or still loading
console.log("[strategies.js] Module loaded, readyState:", document.readyState);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  // DOM already loaded, run immediately
  init();
}

// =============================================================================
// EVENT SETUP
// =============================================================================

/**
 * Setup all event listeners (CSP-compliant, no inline handlers)
 */
function setupEventListeners() {
  // Main toolbar buttons
  const btnNewStrategy = document.getElementById("btnNewStrategy");
  if (btnNewStrategy) {
    btnNewStrategy.addEventListener("click", openCreateModal);
  }

  // Strategy modal buttons
  const btnCloseModal = document.getElementById("btnCloseModal");
  if (btnCloseModal) {
    btnCloseModal.addEventListener("click", closeModal);
  }

  const btnCancelModal = document.getElementById("btnCancelModal");
  if (btnCancelModal) {
    btnCancelModal.addEventListener("click", closeModal);
  }

  const btnSaveStrategy = document.getElementById("btnSaveStrategy");
  if (btnSaveStrategy) {
    btnSaveStrategy.addEventListener("click", saveStrategy);
  }

  // Backtest modal buttons
  const btnCloseBacktestModal = document.getElementById(
    "btnCloseBacktestModal",
  );
  if (btnCloseBacktestModal) {
    btnCloseBacktestModal.addEventListener("click", closeBacktestModal);
  }

  const btnCancelBacktest = document.getElementById("btnCancelBacktest");
  if (btnCancelBacktest) {
    btnCancelBacktest.addEventListener("click", () => {
      // First try to cancel running optimization, then close modal
      cancelOptimization();
      closeBacktestModal();
    });
  }

  // Optimization/Backtest button - check mode and run appropriate action
  const btnRunOptimization = document.getElementById("btnRunOptimization");
  if (btnRunOptimization) {
    btnRunOptimization.addEventListener("click", () => {
      // Check which mode is selected
      const modeBacktest = document.getElementById("modeSimpleBacktest");
      const isBacktestMode = modeBacktest?.checked;

      if (isBacktestMode) {
        // Run simple backtest with saved strategy parameters
        runBacktest(loadStrategies);
      } else {
        // Run full optimization with parameter ranges
        runOptimization(loadStrategies);
      }
    });
  }

  // Update combinations count when parameters change (including TP/SL)
  const optInputs = [
    "optPeriodMin",
    "optPeriodMax",
    "optPeriodStep",
    "optOverboughtMin",
    "optOverboughtMax",
    "optOverboughtStep",
    "optOversoldMin",
    "optOversoldMax",
    "optOversoldStep",
    "optStopLossMin",
    "optStopLossMax",
    "optStopLossStep",
    "optTakeProfitMin",
    "optTakeProfitMax",
    "optTakeProfitStep",
  ];
  optInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", updateCombinationsCount);
    }
  });

  // Bar Magnifier toggle
  const useBarMagnifier = document.getElementById("useBarMagnifier");
  if (useBarMagnifier) {
    useBarMagnifier.addEventListener("change", () => {
      const options = document.getElementById("barMagnifierOptions");
      if (options) {
        options.classList.toggle("hidden", !useBarMagnifier.checked);
      }
    });
  }

  // Update ticks per bar calculation
  const intrabarSubticks = document.getElementById("intrabarSubticks");
  if (intrabarSubticks) {
    intrabarSubticks.addEventListener("change", updateTicksPerBar);
  }

  // Initialize period quick-select buttons
  initPeriodButtons();

  // Strategy type change
  const strategyType = document.getElementById("strategyType");
  if (strategyType) {
    strategyType.addEventListener("change", () => updateParametersUI());
  }

  // Symbol and Timeframe change - trigger data check
  const strategySymbol = document.getElementById("strategySymbol");
  if (strategySymbol) {
    strategySymbol.addEventListener("input", checkSymbolData);
    strategySymbol.addEventListener("change", () => {
      checkSymbolData();
      updateLeverageLimits().catch((err) =>
        console.warn("Leverage update error:", err),
      );
    });
  }

  const strategyTimeframe = document.getElementById("strategyTimeframe");
  if (strategyTimeframe) {
    strategyTimeframe.addEventListener("change", () => {
      checkSymbolData();
      updateTicksPerBar(); // Update tick count for new TF
    });
  }

  // Capital and position size changes - update leverage limits
  const strategyCapital = document.getElementById("strategyCapital");
  if (strategyCapital) {
    strategyCapital.addEventListener("change", () =>
      updateLeverageLimits().catch(() => {}),
    );
    strategyCapital.addEventListener(
      "input",
      debounce(() => updateLeverageLimits().catch(() => {}), 300),
    );
  }

  const strategyPositionSize = document.getElementById("strategyPositionSize");
  if (strategyPositionSize) {
    strategyPositionSize.addEventListener("change", () =>
      updateLeverageLimits().catch(() => {}),
    );
    strategyPositionSize.addEventListener(
      "input",
      debounce(() => updateLeverageLimits().catch(() => {}), 300),
    );
  }

  const strategyPositionSizeType = document.getElementById(
    "strategyPositionSizeType",
  );
  if (strategyPositionSizeType) {
    strategyPositionSizeType.addEventListener("change", () =>
      updateLeverageLimits().catch(() => {}),
    );
  }

  // Delegate click events for dynamically created strategy cards
  const container = document.getElementById("strategiesContainer");
  if (container) {
    container.addEventListener("click", handleStrategyCardClick);
  }
}

/**
 * Handle clicks on strategy cards (event delegation)
 */
function handleStrategyCardClick(e) {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;

  const action = btn.dataset.action;
  const strategyId = btn.dataset.id;

  switch (action) {
    case "backtest":
      openBacktestModal(strategyId);
      break;
    case "edit":
      editStrategy(strategyId);
      break;
    case "duplicate":
      duplicateStrategy(strategyId);
      break;
    case "pause":
      pauseStrategy(strategyId);
      break;
    case "activate":
      activateStrategy(strategyId);
      break;
    case "delete":
      deleteStrategy(strategyId);
      break;
  }
}

function setDefaultDates() {
  const today = new Date();
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);

  document.getElementById("backtestStartDate").value = sixMonthsAgo
    .toISOString()
    .split("T")[0];
  document.getElementById("backtestEndDate").value = today
    .toISOString()
    .split("T")[0];
}

function setupFilters() {
  document
    .getElementById("searchInput")
    .addEventListener("input", debounce(loadStrategies, 300));
  document
    .getElementById("statusFilter")
    .addEventListener("change", loadStrategies);
  document
    .getElementById("typeFilter")
    .addEventListener("change", loadStrategies);
}

// =============================================================================
// TOP SYMBOLS & DATA CHECK
// =============================================================================

/**
 * Load top 20 trading pairs by volume from Bybit
 */
async function loadTopSymbols() {
  try {
    const response = await fetch(`${API_BASE}/marketdata/symbols/top?limit=20`);
    if (!response.ok) throw new Error("Failed to load symbols");

    const data = await response.json();
    const symbols = data.symbols || [];

    // Populate datalist
    const datalist = document.getElementById("symbolsList");
    if (datalist) {
      datalist.innerHTML = symbols
        .map(
          (s) =>
            `<option value="${s.symbol}" label="${s.symbol} - $${formatNumber(s.turnover_24h)}">`,
        )
        .join("");
    }

    // Store for later use
    topSymbols.length = 0;
    topSymbols.push(...symbols);
  } catch (error) {
    console.error("Failed to load top symbols:", error);
    // Fallback to default popular pairs
    const fallbackSymbols = [
      "BTCUSDT",
      "ETHUSDT",
      "SOLUSDT",
      "BNBUSDT",
      "XRPUSDT",
      "DOGEUSDT",
      "ADAUSDT",
      "AVAXUSDT",
      "DOTUSDT",
      "LINKUSDT",
      "MATICUSDT",
      "LTCUSDT",
      "UNIUSDT",
      "ATOMUSDT",
      "XLMUSDT",
      "FILUSDT",
      "APTUSDT",
      "ARBUSDT",
      "OPUSDT",
      "NEARUSDT",
    ];
    const datalist = document.getElementById("symbolsList");
    if (datalist) {
      datalist.innerHTML = fallbackSymbols
        .map((s) => `<option value="${s}">`)
        .join("");
    }
  }
}

/**
 * Check if data exists for selected symbol/timeframe and trigger loading if needed
 */
checkSymbolData = debounce(async function () {
  console.log("[checkSymbolData] Function called");

  const symbol = document
    .getElementById("strategySymbol")
    .value?.trim()
    .toUpperCase();
  const timeframe = document.getElementById("strategyTimeframe").value;

  console.log("[checkSymbolData] symbol:", symbol, "timeframe:", timeframe);

  const statusRow = document.getElementById("dataStatusRow");
  const statusIndicator = document.getElementById("dataStatusIndicator");

  // Hide if either is not selected
  if (!symbol || !timeframe) {
    console.log(
      "[checkSymbolData] Missing symbol or timeframe, hiding status row",
    );
    statusRow?.classList.add("hidden");
    return;
  }

  // Show checking status
  console.log("[checkSymbolData] Showing status row, calling API...");
  statusRow?.classList.remove("hidden");
  statusIndicator.className = "data-status checking";
  statusIndicator.innerHTML = `
        <span class="status-icon">⏳</span>
        <span class="status-text">Проверка данных для ${symbol} / ${timeframe}...</span>
    `;

  try {
    const response = await fetch(
      `${API_BASE}/marketdata/symbols/check-data?symbol=${symbol}&interval=${timeframe}`,
    );

    if (!response.ok) throw new Error("Check failed");

    const data = await response.json();

    if (data.has_data) {
      // Data available - show freshness info
      const freshIcon = getFreshnessIcon(data.freshness);
      const freshText = getFreshnessText(data.freshness, data.hours_old);

      // Auto-refresh if data is stale or outdated
      if (data.freshness === "stale" || data.freshness === "outdated") {
        statusIndicator.className = "data-status loading";
        statusIndicator.innerHTML = `
                    <span class="status-icon">🔄</span>
                    <span class="status-text">
                        Обновление данных...
                        <br><small>${freshText}</small>
                    </span>
                `;

        // Trigger auto-refresh
        await refreshSymbolData(symbol, timeframe, statusIndicator);
      } else {
        // Data is fresh
        const firstDate = data.earliest_datetime
          ? new Date(data.earliest_datetime).toLocaleDateString("ru-RU")
          : "";
        const periodText = firstDate
          ? `${firstDate} — ${new Date(data.latest_datetime).toLocaleDateString("ru-RU")}`
          : "";

        statusIndicator.className = "data-status available";
        statusIndicator.innerHTML = `
                    <span class="status-icon">${freshIcon}</span>
                    <span class="status-text">
                        Данные доступны: ${formatNumber(data.candle_count)} свечей
                        <br><small>${periodText ? "Период: " + periodText + " • " : ""}${freshText}</small>
                    </span>
                    <button type="button" class="btn-refresh-data" onclick="window.forceRefreshData()" title="Обновить данные">🔄</button>
                `;

        // Store current selection for force refresh
        window._currentSymbol = symbol;
        window._currentTimeframe = timeframe;
        window._currentStatusIndicator = statusIndicator;
      }
    } else {
      // No data - trigger loading
      statusIndicator.className = "data-status loading";
      statusIndicator.innerHTML = `
                <span class="status-icon">📥</span>
                <span class="status-text">Загрузка данных...</span>
            `;

      // Trigger data loading
      await refreshSymbolData(symbol, timeframe, statusIndicator);
    }
  } catch (error) {
    console.error("Data check failed:", error);
    statusIndicator.className = "data-status error";
    statusIndicator.innerHTML = `
            <span class="status-icon">⚠️</span>
            <span class="status-text">Ошибка проверки данных</span>
        `;
  }
}, 500);

/**
 * Force refresh data (called from refresh button)
 */
window.forceRefreshData = async function () {
  const symbol = window._currentSymbol;
  const timeframe = window._currentTimeframe;
  const statusIndicator = window._currentStatusIndicator;

  if (symbol && timeframe && statusIndicator) {
    statusIndicator.className = "data-status loading";
    statusIndicator.innerHTML = `
            <span class="status-icon">🔄</span>
            <span class="status-text">Обновление данных...</span>
        `;
    await refreshSymbolData(symbol, timeframe, statusIndicator);
  }
};

/**
 * Refresh symbol data from Bybit API with SSE progress streaming
 */
async function refreshSymbolData(symbol, timeframe, statusIndicator) {
  // Get progress bar elements
  const progressContainer = document.getElementById("candleLoadingProgress");
  const progressBar = document.getElementById("candleLoadingBar");
  const progressStatus = document.getElementById("candleLoadingStatus");
  const progressPercent = document.getElementById("candleLoadingPercent");
  const progressDetails = document.getElementById("candleLoadingDetails");

  // Show progress bar
  if (progressContainer) {
    progressContainer.classList.remove("hidden");
    progressBar.style.width = "0%";
    progressStatus.textContent = "Подключение к серверу...";
    progressPercent.textContent = "0%";
    progressDetails.textContent = "Инициализация...";
  }

  try {
    // Use SSE for progress streaming
    const eventSource = new EventSource(
      `${API_BASE}/marketdata/symbols/refresh-data-stream?symbol=${symbol}&interval=${timeframe}`,
    );

    return new Promise((resolve, reject) => {
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.event === "progress") {
            // Update progress bar
            if (progressContainer) {
              progressBar.style.width = `${data.percent}%`;
              progressPercent.textContent = `${data.percent}%`;
              progressStatus.textContent = data.message || "Загрузка...";
              if (data.loaded !== undefined && data.total !== undefined) {
                progressDetails.textContent = `${formatNumber(data.loaded)} / ${formatNumber(data.total)} свечей`;
              }
            }
          } else if (data.event === "complete") {
            // Complete - update UI
            if (progressContainer) {
              progressBar.style.width = "100%";
              progressPercent.textContent = "100%";
              progressStatus.textContent = "Готово!";
              progressDetails.textContent =
                data.message ||
                `${formatNumber(data.total_count)} свечей загружено`;
            }

            // Update status indicator
            statusIndicator.className = "data-status available";
            statusIndicator.innerHTML = `
                            <span class="status-icon">✅</span>
                            <span class="status-text">
                                ${data.new_candles > 0 ? `Добавлено ${formatNumber(data.new_candles)} свечей` : "Данные актуальны"}
                                <br><small>Всего: ${formatNumber(data.total_count)} свечей в базе</small>
                            </span>
                        `;

            // Hide progress bar after short delay
            setTimeout(() => {
              progressContainer?.classList.add("hidden");
            }, 2000);

            eventSource.close();
            resolve(data);
          } else if (data.event === "error") {
            throw new Error(data.message);
          }
        } catch (parseError) {
          console.error("SSE parse error:", parseError);
        }
      };

      eventSource.onerror = (error) => {
        console.error("SSE connection error:", error);
        eventSource.close();

        // Fallback to regular POST request
        fallbackRefresh(symbol, timeframe, statusIndicator, progressContainer)
          .then(resolve)
          .catch(reject);
      };

      // Timeout after 60 seconds
      setTimeout(() => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close();
          fallbackRefresh(symbol, timeframe, statusIndicator, progressContainer)
            .then(resolve)
            .catch(reject);
        }
      }, 60000);
    });
  } catch (error) {
    console.error("Data refresh failed:", error);
    progressContainer?.classList.add("hidden");
    statusIndicator.className = "data-status error";
    statusIndicator.innerHTML = `
            <span class="status-icon">❌</span>
            <span class="status-text">Ошибка обновления данных</span>
        `;
  }
}

/**
 * Format date range for display
 */
function formatDateRange(earliestIso, latestIso) {
  if (!earliestIso || !latestIso) return "";

  const earliest = new Date(earliestIso);
  const latest = new Date(latestIso);

  const formatDate = (d) =>
    d.toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });

  return `${formatDate(earliest)} — ${formatDate(latest)}`;
}

/**
 * Fallback refresh using regular POST request
 */
async function fallbackRefresh(
  symbol,
  timeframe,
  statusIndicator,
  progressContainer,
) {
  try {
    const response = await fetch(
      `${API_BASE}/marketdata/symbols/refresh-data?symbol=${symbol}&interval=${timeframe}`,
      { method: "POST" },
    );

    if (!response.ok) throw new Error("Refresh failed");

    const data = await response.json();

    // Format date range
    const dateRange = formatDateRange(
      data.earliest_datetime,
      data.latest_datetime,
    );

    // Hide progress bar
    progressContainer?.classList.add("hidden");

    // Show success with period info
    statusIndicator.className = "data-status available";
    statusIndicator.innerHTML = `
            <span class="status-icon">✅</span>
            <span class="status-text">
                ${data.message}
                <br><small>Всего: ${formatNumber(data.total_count)} свечей • ${dateRange}</small>
            </span>
        `;

    return data;
  } catch (error) {
    console.error("Fallback refresh failed:", error);
    progressContainer?.classList.add("hidden");
    statusIndicator.className = "data-status error";
    statusIndicator.innerHTML = `
            <span class="status-icon">❌</span>
            <span class="status-text">Ошибка обновления данных</span>
        `;
    throw error;
  }
}

// =============================================================================
// PARAMETERS UI
// =============================================================================

function updateParametersUI(existingParams = {}) {
  const type = document.getElementById("strategyType")?.value;
  if (!type) return;

  // Hide all indicator sections first
  const allSections = [
    "rsiParametersSection",
    "smaParametersSection",
    "macdParametersSection",
    "bollingerParametersSection",
    "dcaParametersSection",
  ];
  allSections.forEach((id) => {
    const section = document.getElementById(id);
    if (section) section.style.display = "none";
  });

  // Show the relevant section based on strategy type
  const sectionMap = {
    rsi: "rsiParametersSection",
    sma_crossover: "smaParametersSection",
    macd: "macdParametersSection",
    bollinger_bands: "bollingerParametersSection",
    bollinger_rsi: "bollingerParametersSection", // Use Bollinger params for combo
    dca: "dcaParametersSection",
  };

  const targetSectionId = sectionMap[type];
  if (targetSectionId) {
    const section = document.getElementById(targetSectionId);
    if (section) section.style.display = "block";
  }

  // Get default parameters from API
  const types = getStrategyTypes();
  const typeInfo = types.find((t) => t.strategy_type === type);
  const defaults = typeInfo?.parameters || {};

  // Merge defaults with existing params (existing takes priority)
  const merged = { ...defaults, ...existingParams };

  // Fill in the indicator-specific fields based on type
  switch (type) {
    case "rsi":
      setFieldValue("rsiPeriod", merged.period);
      setFieldValue("rsiOversold", merged.oversold);
      setFieldValue("rsiOverbought", merged.overbought);
      break;
    case "sma_crossover":
      setFieldValue("smaFastPeriod", merged.fast_period);
      setFieldValue("smaSlowPeriod", merged.slow_period);
      break;
    case "macd":
      setFieldValue("macdFastPeriod", merged.fast_period);
      setFieldValue("macdSlowPeriod", merged.slow_period);
      setFieldValue("macdSignalPeriod", merged.signal_period);
      break;
    case "bollinger_bands":
    case "bollinger_rsi":
      setFieldValue("bollingerPeriod", merged.period);
      setFieldValue("bollingerStdDev", merged.std_dev);
      break;
    // DCA params are handled separately in strategyCRUD.js editStrategy()
  }
}

/**
 * Helper to set form field value if element exists
 */
function setFieldValue(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) {
    el.value = value;
  }
}

function getParametersFromUI() {
  const type = document.getElementById("strategyType")?.value;

  // Helper to get numeric value from input
  const getNum = (id) => parseFloat(document.getElementById(id)?.value) || 0;

  // Read parameters based on current strategy type
  switch (type) {
    case "rsi":
      return {
        period: getNum("rsiPeriod"),
        oversold: getNum("rsiOversold"),
        overbought: getNum("rsiOverbought"),
      };
    case "sma_crossover":
      return {
        fast_period: getNum("smaFastPeriod"),
        slow_period: getNum("smaSlowPeriod"),
      };
    case "macd":
      return {
        fast_period: getNum("macdFastPeriod"),
        slow_period: getNum("macdSlowPeriod"),
        signal_period: getNum("macdSignalPeriod"),
      };
    case "bollinger_bands":
    case "bollinger_rsi":
      return {
        period: getNum("bollingerPeriod"),
        std_dev: getNum("bollingerStdDev"),
      };
    case "dca":
      // DCA params are read separately in strategyCRUD.js
      return {};
    default:
      // For custom or unknown types, try legacy param-input approach
      const params = {};
      document.querySelectorAll(".param-input").forEach((input) => {
        const value = parseFloat(input.value);
        if (!isNaN(value)) {
          params[input.dataset.param] = value;
        }
      });

      // If still empty, get defaults
      if (Object.keys(params).length === 0) {
        const types = getStrategyTypes();
        const typeInfo = types.find((t) => t.strategy_type === type);
        return typeInfo?.parameters || {};
      }
      return params;
  }
}

/**
 * Update position size input based on selected type
 */
function updatePositionSizeInput() {
  const typeSelect = document.getElementById("strategyPositionSizeType");
  const sizeInput = document.getElementById("strategyPositionSize");
  const sizeLabel = document.getElementById("positionSizeLabel");

  if (!typeSelect || !sizeInput || !sizeLabel) return;

  const type = typeSelect.value;

  switch (type) {
    case "percent":
      sizeLabel.textContent = "Размер позиции (%)";
      sizeInput.min = 1;
      sizeInput.max = 100;
      sizeInput.step = 1;
      sizeInput.placeholder = "100";
      break;
    case "fixed_amount":
      sizeLabel.textContent = "Сумма на ордер ($)";
      sizeInput.min = 1;
      sizeInput.max = 1000000;
      sizeInput.step = 1;
      sizeInput.placeholder = "100";
      break;
    case "contracts":
      sizeLabel.textContent = "Количество контрактов";
      sizeInput.min = 0.001;
      sizeInput.max = 10000;
      sizeInput.step = 0.001;
      sizeInput.placeholder = "1";
      break;
  }
}

// Make function globally available for HTML onchange
window.updatePositionSizeInput = updatePositionSizeInput;

// =============================================================================
// BAR MAGNIFIER HELPERS
// =============================================================================

/**
 * Update ticks per bar display based on subticks selection and timeframe
 */
function updateTicksPerBar() {
  const subticks = parseInt(
    document.getElementById("intrabarSubticks")?.value || 1,
  );
  const ticksPerBar = document.getElementById("ticksPerBar");
  const ticksInfo = document.querySelector(".bar-magnifier-info small");

  // Get timeframe from strategy form
  const tfSelect = document.getElementById("strategyTimeframe");
  let minutesInBar = 60; // Default to 1h
  let tfLabel = "1h";

  if (tfSelect) {
    const tfValue = tfSelect.value;
    // Bybit intervals: 1,3,5,15,30,60,120,240,360,720,D,W,M
    if (tfValue === "D" || tfValue === "1D") {
      minutesInBar = 1440;
      tfLabel = "1D";
    } else if (tfValue === "W" || tfValue === "1W") {
      minutesInBar = 10080;
      tfLabel = "1W";
    } else if (tfValue === "M" || tfValue === "1M") {
      minutesInBar = 43200;
      tfLabel = "1M";
    } else if (!isNaN(parseInt(tfValue))) {
      const num = parseInt(tfValue);
      minutesInBar = num <= 60 ? num : num; // 1-60 minutes, else 120/240/360/720
      if (num === 60) tfLabel = "1h";
      else if (num === 120) tfLabel = "2h";
      else if (num === 240) tfLabel = "4h";
      else if (num === 360) tfLabel = "6h";
      else if (num === 720) tfLabel = "12h";
      else tfLabel = num <= 60 ? num + "m" : num + "m";
    }
  }

  // Calculate ticks: minutes * (4 OHLC points + subticks * 3 segments)
  const ticksPer1m = 4 + subticks * 3;
  const totalTicks = minutesInBar * ticksPer1m;

  if (ticksPerBar) {
    ticksPerBar.textContent = totalTicks.toLocaleString();
  }

  // Update the full info text with current TF
  if (ticksInfo) {
    ticksInfo.innerHTML = `📊 Для ${tfLabel} бара: ${minutesInBar} × (4 + ${subticks}×3) = <span id="ticksPerBar">${totalTicks.toLocaleString()}</span> тиков`;
  }
}

/**
 * Get Bar Magnifier configuration from form
 */
function getBarMagnifierConfig() {
  const useBarMagnifier =
    document.getElementById("useBarMagnifier")?.checked ?? true; // ALWAYS true by default for accurate intrabar simulation
  const ohlcPath =
    document.getElementById("intrabarOhlcPath")?.value || "O-HL-heuristic";
  const subticks = parseInt(
    document.getElementById("intrabarSubticks")?.value || 0,
  );

  return {
    use_bar_magnifier: useBarMagnifier,
    intrabar_ohlc_path: ohlcPath,
    intrabar_subticks: subticks,
  };
}

// Make functions globally available
window.updateTicksPerBar = updateTicksPerBar;
window.getBarMagnifierConfig = getBarMagnifierConfig;

// =============================================================================
// EXPORTS (for testing and external access)
// =============================================================================

if (typeof window !== "undefined") {
  window.strategiesPage = {
    loadStrategies,
    loadStrategyTypes,
    openCreateModal,
    closeModal,
    renderStrategies,
    // New exports
    getParametersFromUI,
    updateParametersUI,
    checkSymbolData,
  };
}
