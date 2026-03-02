/**
 * рџ“„ Backtest Results Page JavaScript
 *
 * Page-specific scripts for backtest_results.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 2.0.0
 * @date 2026-02-26
 * @migration P0-3 StateManager — legacy shim sync added
 */

/* global Tabulator */

// Import shared utilities
import { formatDate as _formatDate } from '../utils.js';
import { localDateStr } from '../utils/dateUtils.js';

// Import StateManager and helpers
import { getStore } from '../core/StateManager.js';
import {
  initState
} from '../core/state-helpers.js';

// Import ChartManager (P0-2: Chart.js memory leak fix)
import { chartManager } from '../components/ChartManager.js';

// Import TradesTable utilities (P0-2 Phase 2)
import {
  TRADES_PAGE_SIZE,
  buildTradeRows,
  sortRows,
  renderPage as renderTradesPageUtil,
  renderPagination,
  updatePaginationControls,
  removePagination,
  updateSortIndicators
} from '../components/TradesTable.js';

// Import MetricsPanels utilities (P0-2 Phase 3)
import {
  updateTVSummaryCards,
  updateTVDynamicsTab,
  updateTVTradeAnalysisTab,
  updateTVRiskReturnTab
} from '../components/MetricsPanels.js';

// ============================
// Security utilities
// ============================
/**
 * Escape HTML special characters to prevent XSS injection.
 * Used whenever server-derived strings are inserted into innerHTML.
 * @param {*} text - Value to escape (coerced to string)
 * @returns {string} HTML-escaped string
 */
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

// ============================
// Configuration
// ============================
const API_BASE = '/api/v1';

/**
 * @migration P0-3 StateManager
 * Legacy variables below are now StateManager-backed proxies.
 * All reads/writes go through getStore() so state is centralised.
 * The proxy Proxy() approach is NOT used because this is a plain-JS ES module
 * without a build step — instead each variable is a thin wrapper that is
 * lazily connected to the store after initializeBacktestResultsState() runs.
 *
 * NOTE: const Set objects (recentlyDeletedIds, selectedForDelete) are kept as
 * module-level Sets because they are *mutated*, not reassigned.  The store
 * holds references to the same Set instances.
 */

// --- Core state (StateManager-backed) ---
// Getters/setters: getCurrentBacktest / setCurrentBacktest etc. (defined below)
// These shim variables mirror the store so existing code that reads them
// directly still works.  After initializeBacktestResultsState() the shims
// are kept in sync automatically via store.subscribe().
let currentBacktest = null;
let allResults = [];
let selectedForCompare = [];
let compareMode = false;

// Trades table pagination state
let tradesCurrentPage = 0;       // 0-based page index
// TRADES_PAGE_SIZE imported from TradesTable.js
let tradesCachedRows = [];       // pre-built HTML rows (reversed, newest-first)
let tradesSortKey = null;        // active sort column key
let tradesSortAsc = true;        // sort direction

// Track recently deleted IDs to filter them from API responses
// This prevents "ghost" items from reappearing due to backend sync delay
const recentlyDeletedIds = new Set();

// Multi-select for bulk delete
const selectedForDelete = new Set();

// Charts (StateManager-backed via getChart/setChart)
let equityChart = null; // kept for legacy references (drawdown, returns, monthly)
let _brTVEquityChart = null; // TradingViewEquityChart instance (main equity chart)
let drawdownChart = null;
let returnsChart = null;
let monthlyChart = null;
// Trade Analysis Charts
let tradeDistributionChart = null;
let winLossDonutChart = null;
// Dynamics Charts
let waterfallChart = null;
let benchmarkingChart = null;
// Price Chart (LightweightCharts candlestick)
let btPriceChart = null;
let btCandleSeries = null;
let btPriceChartMarkers = [];
let btTradeLineSeries = []; // eslint-disable-line no-unused-vars -- entry→exit price lines (cleaned on chart destroy)
let _btCachedCandles = [];  // cached candles for marker rebuild on checkbox toggle
let btPriceChartPending = false; // true when chart needs (re-)creation on tab show
let _priceChartGeneration = 0; // generation counter to cancel stale async renders
let _priceChartResizeObserver = null; // stored so we can disconnect on chart rebuild

/**
 * Sync shim variables ↔ StateManager.
 * Called once from initializeBacktestResultsState() after the store slice
 * has been created.  From this point on all mutations go BOTH to the local
 * variable AND the store, keeping them in sync.
 */
function _setupLegacyShimSync() {
  const store = getStore();
  if (!store) return;

  // Core state — subscribe store → shim
  store.subscribe('backtestResults.currentBacktest', (v) => { currentBacktest = v; });
  store.subscribe('backtestResults.allResults', (v) => { allResults = v ?? []; });
  store.subscribe('backtestResults.selectedForCompare', (v) => { selectedForCompare = v ?? []; });
  store.subscribe('backtestResults.compareMode', (v) => { compareMode = !!v; });

  // Trades table state → shim
  store.subscribe('backtestResults.trades.currentPage', (v) => { tradesCurrentPage = v ?? 0; });
  store.subscribe('backtestResults.trades.cachedRows', (v) => { tradesCachedRows = v ?? []; });
  store.subscribe('backtestResults.trades.sortKey', (v) => { tradesSortKey = v ?? null; });
  store.subscribe('backtestResults.trades.sortAsc', (v) => { tradesSortAsc = v !== false; });

  // Chart instances → shim
  store.subscribe('backtestResults.charts.equity', (v) => { equityChart = v; });
  store.subscribe('backtestResults.charts._tvEquityChart', (v) => { _brTVEquityChart = v; });
  store.subscribe('backtestResults.charts.drawdown', (v) => { drawdownChart = v; });
  store.subscribe('backtestResults.charts.returns', (v) => { returnsChart = v; });
  store.subscribe('backtestResults.charts.monthly', (v) => { monthlyChart = v; });
  store.subscribe('backtestResults.charts.tradeDistribution', (v) => { tradeDistributionChart = v; });
  store.subscribe('backtestResults.charts.winLossDonut', (v) => { winLossDonutChart = v; });
  store.subscribe('backtestResults.charts.waterfall', (v) => { waterfallChart = v; });
  store.subscribe('backtestResults.charts.benchmarking', (v) => { benchmarkingChart = v; });

  // Price chart state → shim
  store.subscribe('backtestResults.priceChart.instance', (v) => { btPriceChart = v; });
  store.subscribe('backtestResults.priceChart.candleSeries', (v) => { btCandleSeries = v; });
  store.subscribe('backtestResults.priceChart.markers', (v) => { btPriceChartMarkers = v ?? []; });
  store.subscribe('backtestResults.priceChart.tradeLineSeries', (v) => { btTradeLineSeries = v ?? []; });
  store.subscribe('backtestResults.priceChart.cachedCandles', (v) => { _btCachedCandles = v ?? []; });
  store.subscribe('backtestResults.priceChart.pending', (v) => { btPriceChartPending = !!v; });
  store.subscribe('backtestResults.priceChart.generation', (v) => { _priceChartGeneration = v ?? 0; });
  store.subscribe('backtestResults.priceChart.resizeObserver', (v) => { _priceChartResizeObserver = v; });

  // Seed store with current shim values (Sets are shared by reference)
  store.set('backtestResults.service.recentlyDeletedIds', recentlyDeletedIds);
  store.set('backtestResults.service.selectedForDelete', selectedForDelete);

  console.log('[backtest_results] Legacy shim sync established');
}

// ============================
// Equity trade markers (TradingView-like)
// ============================

// Draw discrete trade outcome markers just above the x-axis (instead of a continuous strip)
const equityTradeMarkersPlugin = {
  id: 'equityTradeMarkers',
  afterDatasetsDraw(chart, _args, pluginOptions) {
    try {
      if (!pluginOptions?.enabled) return;
      if (!chart || chart.config?.type !== 'line') return;
      if (chart.canvas?.id !== 'equityChart') return;

      const tradeMap = chart._tradeMap;
      if (!tradeMap || Object.keys(tradeMap).length === 0) return;

      const xScale = chart.scales?.x;
      const yScale = chart.scales?.y;
      const chartArea = chart.chartArea;
      if (!xScale || !yScale || !chartArea) return;

      const ctx = chart.ctx;
      ctx.save();

      // Position markers on a thin "lane" right above the x-axis (TradingView-like)
      const laneY = Math.min(
        chartArea.bottom - 10,
        yScale.getPixelForValue(yScale.min) - 6
      );
      const size = pluginOptions.size ?? 7; // triangle size
      const offsetY = pluginOptions.offsetY ?? 0;

      // Keep markers inside chart area
      const minX = chartArea.left + size + 1;
      const maxX = chartArea.right - size - 1;
      const y = Math.max(
        chartArea.top + size + 1,
        Math.min(chartArea.bottom - size - 1, laneY + offsetY)
      );

      // Iterate deterministically by index
      const indices = Object.keys(tradeMap)
        .map((k) => Number(k))
        .filter((n) => Number.isFinite(n))
        .sort((a, b) => a - b);

      for (const idx of indices) {
        const info = tradeMap[idx];
        if (!info) continue;

        let x = xScale.getPixelForValue(idx);
        if (!Number.isFinite(x)) continue;
        x = Math.max(minX, Math.min(maxX, x));

        const pnl = Number(info.pnl ?? 0);
        const side = (info.side || 'long').toLowerCase();
        const isShort = side === 'short' || side === 'sell';

        const fill = pnl > 0 ? '#26a69a' : pnl < 0 ? '#ef5350' : '#78909c';

        // Draw marker: triangle up for long, triangle down for short (TV-like)
        ctx.beginPath();
        if (isShort) {
          // Down triangle
          ctx.moveTo(x, y + size * 0.6);
          ctx.lineTo(x - size * 0.6, y - size * 0.5);
          ctx.lineTo(x + size * 0.6, y - size * 0.5);
        } else {
          // Up triangle
          ctx.moveTo(x, y - size * 0.6);
          ctx.lineTo(x - size * 0.6, y + size * 0.5);
          ctx.lineTo(x + size * 0.6, y + size * 0.5);
        }
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();

        // subtle outline like TV
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.35)';
        ctx.stroke();
      }

      ctx.restore();
    } catch (e) {
      // Never let a paint helper break the chart
      console.warn('[equityTradeMarkersPlugin] error:', e?.message || e);
    }
  }
};

// Thin bottom lane with alternating equity regimes: growth / drawdown
// Visually mimics TradingView "Рост средств / Просадка средств" scale.
const equityGrowthDrawdownOverlayPlugin = {
  id: 'equityGrowthDrawdownOverlay',
  afterDatasetsDraw(chart, _args, pluginOptions) {
    try {
      if (pluginOptions?.enabled === false) return;
      if (!chart || chart.config?.type !== 'line') return;
      if (chart.canvas?.id !== 'equityChart') return;

      const segments = chart._equityCycles;
      if (!segments || !segments.length) return;

      const xScale = chart.scales?.x;
      const chartArea = chart.chartArea;
      if (!xScale || !chartArea) return;

      const ctx = chart.ctx;
      ctx.save();

      const barHeight = pluginOptions.barHeight ?? 6;
      const yBottom = chartArea.bottom - 1;
      const yTop = yBottom - barHeight;

      const getPixel = (idx) => {
        if (typeof xScale.getPixelForValue === 'function') {
          return xScale.getPixelForValue(idx);
        }
        if (typeof xScale.getPixelForTick === 'function') {
          return xScale.getPixelForTick(idx);
        }
        return NaN;
      };

      for (const seg of segments) {
        const startIndex = seg.startIndex;
        const endIndex = seg.endIndex;
        if (!Number.isFinite(startIndex) || !Number.isFinite(endIndex)) continue;
        if (endIndex < startIndex) continue;

        const x1 = getPixel(startIndex);
        const x2 = getPixel(endIndex);
        if (!Number.isFinite(x1) || !Number.isFinite(x2)) continue;

        const left = Math.max(chartArea.left, Math.min(x1, x2));
        const right = Math.min(chartArea.right, Math.max(x1, x2));
        if (right <= left) continue;

        ctx.fillStyle =
          seg.kind === 'growth'
            ? (pluginOptions.growthColor || 'rgba(16, 185, 129, 0.9)')
            : (pluginOptions.drawdownColor || 'rgba(248, 113, 113, 0.9)');

        ctx.fillRect(left, yTop, right - left, yBottom - yTop);
      }

      ctx.restore();
    } catch (e) {
      console.warn('[equityGrowthDrawdownOverlay] error:', e?.message || e);
    }
  }
};

if (typeof Chart !== 'undefined') {
  Chart.register(equityTradeMarkersPlugin);
  Chart.register(equityGrowthDrawdownOverlayPlugin);
}

// ============================
// TradingView-style Trade Excursion Bars Plugin
// Each trade = ONE unified bar with MFE up (green) and MAE down (red)
// Two layers: light (full excursion) and dark (realized P&L)
// ============================
const tradeExcursionBarsPlugin = {
  id: 'tradeExcursionBars',
  afterDatasetsDraw(chart, _args, pluginOptions) {
    try {
      if (!pluginOptions?.enabled) return;
      if (!chart || chart.canvas?.id !== 'equityChart') return;
      // Respect the Trades excursions toggle checkbox
      if (chart._showTradeExcursions === false) return;

      const tradeRanges = chart._tradeRanges;
      const tradeMap = chart._tradeMap;
      if (!tradeRanges || tradeRanges.length === 0) return;

      const xScale = chart.scales?.x;
      const yScale = chart.scales?.y;
      const chartArea = chart.chartArea;
      if (!xScale || !yScale || !chartArea) return;

      const ctx = chart.ctx;
      ctx.save();

      // Colors
      const greenLight = 'rgba(38, 166, 154, 0.35)';
      const greenDark = 'rgba(38, 166, 154, 0.9)';
      const redLight = 'rgba(239, 83, 80, 0.35)';
      const redDark = 'rgba(239, 83, 80, 0.9)';

      // Get y=0 pixel position
      const y0 = yScale.getPixelForValue(0);

      // ===== ADAPTIVE EXCURSION SCALING =====
      // When MFE/MAE values are tiny compared to Y-axis range,
      // scale them up so P75 bar occupies ~20% of visible chart height.
      // This ensures bars are readable for 14 trades AND 418 trades.
      const yAxisRange = Math.abs(
        (yScale.max || 0) - (yScale.min || 0)
      );
      const targetBarFraction = 0.08; // P75 bar = 8% of Y-axis range
      const targetBarValue = yAxisRange * targetBarFraction;

      // Calculate P75 of MFE and MAE
      const mfeVals = tradeRanges
        .map((r) => Math.abs(r.mfe || 0))
        .filter((v) => v > 0)
        .sort((a, b) => a - b);
      const maeVals = tradeRanges
        .map((r) => Math.abs(r.mae || 0))
        .filter((v) => v > 0)
        .sort((a, b) => a - b);
      const getP75 = (arr) =>
        arr.length > 0
          ? arr[Math.min(Math.floor(arr.length * 0.75), arr.length - 1)]
          : 0;
      const maxP75 = Math.max(getP75(mfeVals), getP75(maeVals));

      // Scale factor: only scale UP (never shrink), cap at 1x if bars already big enough
      let excursionScale = 1;
      if (maxP75 > 0 && targetBarValue > 0) {
        const rawScale = targetBarValue / maxP75;
        // Only apply scaling if bars would be less than target size
        // Use smooth scaling: 1x when bars are big, up to rawScale when tiny
        excursionScale = Math.max(1, rawScale);
        // Cap at 2.5x to avoid oversized bars
        excursionScale = Math.min(excursionScale, 2.5);
      }

      // Adaptive gap: 5px for few trades → 1px for many trades (linear interpolation)
      const numTrades = tradeRanges.length;
      // Scale: 1-30 trades = 5px gap, 150+ trades = 1px gap, linear in between
      const minTrades = 30;
      const maxTrades = 150;
      const maxGap = 5;
      const minGap = 1;
      let gap;
      if (numTrades <= minTrades) {
        gap = maxGap;
      } else if (numTrades >= maxTrades) {
        gap = minGap;
      } else {
        // Linear interpolation between minTrades and maxTrades
        const t = (numTrades - minTrades) / (maxTrades - minTrades);
        gap = Math.round(maxGap - t * (maxGap - minGap));
      }
      const edgePadding = 5; // 5px padding on each edge
      const chartWidth = chartArea.right - chartArea.left - edgePadding * 2;

      // N bars = (N-1) gaps between bars
      const totalGapsWidth = numTrades > 1 ? (numTrades - 1) * gap : 0;
      const availableWidth = chartWidth - totalGapsWidth;
      const calculatedBarWidth =
        numTrades > 0 ? availableWidth / numTrades : chartWidth;

      // Bar width: minimum 1px, no maximum (fills available space)
      const absoluteMinWidth = 1;
      const barWidth = Math.max(absoluteMinWidth, calculatedBarWidth);

      // Process each trade
      tradeRanges.forEach((range, idx) => {
        const mfe = Math.abs(range.mfe || 0) * excursionScale;
        const mae = Math.abs(range.mae || 0) * excursionScale;

        // Get trade P&L for realized portion (also scaled)
        const tradeInfo = Object.values(tradeMap || {}).find(
          (ti) => ti.tradeNum === idx + 1
        );
        const tradePnL = tradeInfo?.pnl || 0;
        const realizedProfit =
          tradePnL > 0
            ? Math.min(Math.abs(tradePnL) * excursionScale, mfe)
            : 0;
        const realizedLoss =
          tradePnL < 0
            ? Math.min(Math.abs(tradePnL) * excursionScale, mae)
            : 0;

        // Calculate X position SEQUENTIALLY by trade index (not by time)
        // This ensures all bars are evenly distributed and visible
        const barX = chartArea.left + edgePadding + idx * (barWidth + gap);

        // === GREEN SIDE (MFE - favorable excursion) ===
        if (mfe > 0) {
          const yMfe = yScale.getPixelForValue(mfe);

          // Layer 1: Light background (full MFE)
          ctx.fillStyle = greenLight;
          ctx.fillRect(barX, yMfe, barWidth, y0 - yMfe);

          // Layer 2: Dark foreground (realized profit)
          if (realizedProfit > 0) {
            const yRealized = yScale.getPixelForValue(realizedProfit);
            ctx.fillStyle = greenDark;
            ctx.fillRect(barX, yRealized, barWidth, y0 - yRealized);
          }
        }

        // === RED SIDE (MAE - adverse excursion) ===
        if (mae > 0) {
          const yMae = yScale.getPixelForValue(-mae);

          // Layer 1: Light background (full MAE)
          ctx.fillStyle = redLight;
          ctx.fillRect(barX, y0, barWidth, yMae - y0);

          // Layer 2: Dark foreground (realized loss)
          if (realizedLoss > 0) {
            const yRealized = yScale.getPixelForValue(-realizedLoss);
            ctx.fillStyle = redDark;
            ctx.fillRect(barX, y0, barWidth, yRealized - y0);
          }
        }
      });

      ctx.restore();
    } catch (e) {
      console.warn('[tradeExcursionBarsPlugin] error:', e?.message || e);
    }
  }
};

if (typeof Chart !== 'undefined') {
  Chart.register(tradeExcursionBarsPlugin);
}

// Trades Table
let tradesTable = null;

// ============================
// StateManager Integration
// ============================

/**
 * Initialize backtest results state slice
 */
function initializeBacktestResultsState() {
  const store = getStore();
  if (!store) {
    console.warn('[initializeBacktestResultsState] Store not initialized');
    return;
  }

  // Initialize state paths
  initState('backtestResults.currentBacktest', null);
  initState('backtestResults.allResults', []);
  initState('backtestResults.selectedForCompare', []);
  initState('backtestResults.compareMode', false);

  // Trades table state
  initState('backtestResults.trades.currentPage', 0);
  initState('backtestResults.trades.cachedRows', []);
  initState('backtestResults.trades.sortKey', null);
  initState('backtestResults.trades.sortAsc', true);

  // Chart instances
  initState('backtestResults.charts.equity', null);
  initState('backtestResults.charts._tvEquityChart', null);
  initState('backtestResults.charts.drawdown', null);
  initState('backtestResults.charts.returns', null);
  initState('backtestResults.charts.monthly', null);
  initState('backtestResults.charts.tradeDistribution', null);
  initState('backtestResults.charts.winLossDonut', null);
  initState('backtestResults.charts.waterfall', null);
  initState('backtestResults.charts.benchmarking', null);

  // Price chart state
  initState('backtestResults.priceChart.instance', null);
  initState('backtestResults.priceChart.candleSeries', null);
  initState('backtestResults.priceChart.markers', []);
  initState('backtestResults.priceChart.tradeLineSeries', []);
  initState('backtestResults.priceChart.cachedCandles', []);
  initState('backtestResults.priceChart.pending', false);
  initState('backtestResults.priceChart.generation', 0);
  initState('backtestResults.priceChart.resizeObserver', null);

  // Service state
  initState('backtestResults.service.recentlyDeletedIds', new Set());
  initState('backtestResults.service.selectedForDelete', new Set());

  // Other state
  initState('backtestResults.chartDisplayMode', 'absolute');

  // Connect legacy shim variables to the store (bidirectional sync)
  _setupLegacyShimSync();

  console.log('[initializeBacktestResultsState] State initialized');
}

// ============================
// State Getters/Setters
// Public API — exported for use by other modules and browser console.
// ESLint: these functions are called externally so "unused" warnings are false positives.
// ============================
/* eslint-disable no-unused-vars */

// Current Backtest
function getCurrentBacktest() {
  return getStore()?.get('backtestResults.currentBacktest');
}

function setCurrentBacktest(backtest) {
  getStore()?.set('backtestResults.currentBacktest', backtest);
}

// All Results
function getAllResults() {
  return getStore()?.get('backtestResults.allResults');
}

function setAllResults(results) {
  getStore()?.set('backtestResults.allResults', results);
}

// Selected for Compare
function getSelectedForCompare() {
  return getStore()?.get('backtestResults.selectedForCompare');
}

function setSelectedForCompare(selected) {
  getStore()?.set('backtestResults.selectedForCompare', selected);
}

// Compare Mode
function getCompareMode() {
  return getStore()?.get('backtestResults.compareMode');
}

function setCompareMode(mode) {
  getStore()?.set('backtestResults.compareMode', mode);
}

// Trades Table State
function getTradesCurrentPage() {
  return getStore()?.get('backtestResults.trades.currentPage');
}

function setTradesCurrentPage(page) {
  getStore()?.set('backtestResults.trades.currentPage', page);
}

function getTradesCachedRows() {
  return getStore()?.get('backtestResults.trades.cachedRows');
}

function setTradesCachedRows(rows) {
  getStore()?.set('backtestResults.trades.cachedRows', rows);
}

function getTradesSortKey() {
  return getStore()?.get('backtestResults.trades.sortKey');
}

function setTradesSortKey(key) {
  getStore()?.set('backtestResults.trades.sortKey', key);
}

function getTradesSortAsc() {
  return getStore()?.get('backtestResults.trades.sortAsc');
}

function setTradesSortAsc(asc) {
  getStore()?.set('backtestResults.trades.sortAsc', asc);
}

// Chart Instances
function getChart(chartName) {
  return getStore()?.get(`backtestResults.charts.${chartName}`);
}

function setChart(chartName, chart) {
  getStore()?.set(`backtestResults.charts.${chartName}`, chart);
}

function getAllCharts() {
  return getStore()?.get('backtestResults.charts');
}

// Price Chart State
function getPriceChart() {
  return getStore()?.get('backtestResults.priceChart.instance');
}

function setPriceChart(chart) {
  getStore()?.set('backtestResults.priceChart.instance', chart);
}

function getPriceChartCandleSeries() {
  return getStore()?.get('backtestResults.priceChart.candleSeries');
}

function setPriceChartCandleSeries(series) {
  getStore()?.set('backtestResults.priceChart.candleSeries', series);
}

function getPriceChartMarkers() {
  return getStore()?.get('backtestResults.priceChart.markers');
}

function setPriceChartMarkers(markers) {
  getStore()?.set('backtestResults.priceChart.markers', markers);
}

function getPriceChartTradeLineSeries() {
  return getStore()?.get('backtestResults.priceChart.tradeLineSeries');
}

function setPriceChartTradeLineSeries(series) {
  getStore()?.set('backtestResults.priceChart.tradeLineSeries', series);
}

function getPriceChartCachedCandles() {
  return getStore()?.get('backtestResults.priceChart.cachedCandles');
}

function setPriceChartCachedCandles(candles) {
  getStore()?.set('backtestResults.priceChart.cachedCandles', candles);
}

function getPriceChartPending() {
  return getStore()?.get('backtestResults.priceChart.pending');
}

function setPriceChartPending(pending) {
  getStore()?.set('backtestResults.priceChart.pending', pending);
}

function getPriceChartGeneration() {
  return getStore()?.get('backtestResults.priceChart.generation');
}

function setPriceChartGeneration(generation) {
  getStore()?.set('backtestResults.priceChart.generation', generation);
}

function getPriceChartResizeObserver() {
  return getStore()?.get('backtestResults.priceChart.resizeObserver');
}

function setPriceChartResizeObserver(observer) {
  getStore()?.set('backtestResults.priceChart.resizeObserver', observer);
}

// Service State
function getRecentlyDeletedIds() {
  return getStore()?.get('backtestResults.service.recentlyDeletedIds');
}

function setRecentlyDeletedIds(ids) {
  getStore()?.set('backtestResults.service.recentlyDeletedIds', ids);
}

function getSelectedForDelete() {
  return getStore()?.get('backtestResults.service.selectedForDelete');
}

function setSelectedForDelete(ids) {
  getStore()?.set('backtestResults.service.selectedForDelete', ids);
}

// Chart Display Mode
function getChartDisplayMode() {
  return getStore()?.get('backtestResults.chartDisplayMode');
}

function setChartDisplayMode(mode) {
  getStore()?.set('backtestResults.chartDisplayMode', mode);
}

// Trades Table instance
function getTradesTable() {
  return getStore()?.get('backtestResults.tradesTable');
}

function setTradesTable(table) {
  getStore()?.set('backtestResults.tradesTable', table);
}

/* eslint-enable no-unused-vars */

// ============================
// State Subscriptions
// ============================

function setupBacktestResultsSubscriptions() {
  const store = getStore();
  if (!store) {
    console.warn('[setupBacktestResultsSubscriptions] Store not initialized');
    return;
  }

  // Compare mode changes → update UI
  store.subscribe('backtestResults.compareMode', (compareMode) => {
    console.log('[BacktestResults] Compare mode changed:', compareMode);
    const compareControls = document.querySelectorAll('.compare-controls');
    compareControls.forEach(el => {
      el.style.display = compareMode ? 'block' : 'none';
    });
  });

  // Selected for compare changes → update checkboxes
  store.subscribe('backtestResults.selectedForCompare', (selected) => {
    console.log('[BacktestResults] Selected for compare changed:', selected);
    // Update checkbox states in results list
    document.querySelectorAll('.compare-checkbox').forEach(cb => {
      const itemId = cb.closest('.result-item')?.dataset.id;
      if (itemId) {
        cb.checked = selected.includes(itemId);
      }
    });
  });

  // Current backtest changes → update UI
  store.subscribe('backtestResults.currentBacktest', (backtest) => {
    console.log('[BacktestResults] Current backtest changed:', backtest?.id);
    // Highlight selected result in list
    document.querySelectorAll('.result-item').forEach(item => {
      if (item.dataset.id === backtest?.id) {
        item.classList.add('selected');
      } else {
        item.classList.remove('selected');
      }
    });
  });

  // Chart display mode changes → update charts
  store.subscribe('backtestResults.chartDisplayMode', (mode) => {
    console.log('[BacktestResults] Chart display mode changed:', mode);
    // Charts will be updated by existing updateChartDisplayMode() function
  });

  console.log('[setupBacktestResultsSubscriptions] Subscriptions setup complete');
}

// ============================
// Initialization
// ============================
document.addEventListener('DOMContentLoaded', () => {
  // Initialize StateManager
  initializeBacktestResultsState();
  setupBacktestResultsSubscriptions();

  initCharts();
  initTradingViewTabs();
  loadBacktestResults();
  loadStrategies();
  setDefaultDates();
  setupFilters();
  setupChartResize();
  setupResultsListDelegation();
  setupBulkDeleteToolbar();

  // Price-chart marker display checkboxes
  const pnlCb = document.getElementById('markerShowPnl');
  const priceCb = document.getElementById('markerShowEntryPrice');
  if (pnlCb) pnlCb.addEventListener('change', rebuildTradeMarkers);
  if (priceCb) priceCb.addEventListener('change', rebuildTradeMarkers);
});

// Handle URL changes (back/forward navigation or redirect with ?id=)
window.addEventListener('popstate', () => {
  loadBacktestResults();
});

// Handle backtest loaded from inline fallback script
window.addEventListener('backtestLoaded', (event) => {
  const backtest = event.detail;
  if (backtest) {
    console.log(
      '[backtestLoaded event] Received backtest data, updating charts'
    );
    setCurrentBacktest(backtest);
    updateCharts(backtest);
  }
});

/**
 * Event delegation for #resultsList container.
 * Handles click/delete on dynamically rendered backtest items
 * without relying on inline onclick attributes.
 */
function setupResultsListDelegation() {
  const container = document.getElementById('resultsList');
  if (!container) return;

  container.addEventListener('click', (e) => {
    // Delete button clicked (button or its <i> icon child)
    const deleteBtn = e.target.closest('.delete-btn');
    if (deleteBtn) {
      e.stopPropagation();
      const item = deleteBtn.closest('.result-item');
      if (item && item.dataset.id) {
        deleteBacktest(item.dataset.id);
      }
      return;
    }

    // Bulk-select checkbox clicked
    const bulkCheckbox = e.target.closest('.bulk-select-checkbox');
    if (bulkCheckbox) {
      e.stopPropagation();
      const item = bulkCheckbox.closest('.result-item');
      if (item && item.dataset.id) {
        toggleBulkSelectItem(item.dataset.id);
      }
      return;
    }

    // Compare checkbox clicked
    const compareCheckbox = e.target.closest('.compare-checkbox');
    if (compareCheckbox) {
      const item = compareCheckbox.closest('.result-item');
      if (item && item.dataset.id) {
        toggleCompareSelect(e, item.dataset.id);
      }
      return;
    }

    // Result content clicked — select backtest
    const content = e.target.closest('.result-content');
    if (content) {
      const item = content.closest('.result-item');
      if (item && item.dataset.id) {
        selectBacktest(item.dataset.id);
      }
      return;
    }
  });
}

/**
 * Bind click listeners for bulk-delete toolbar buttons.
 * Uses addEventListener instead of inline onclick (CSP-safe).
 */
function setupBulkDeleteToolbar() {
  const selectAllCb = document.getElementById('selectAllCheckbox');
  if (selectAllCb) {
    selectAllCb.addEventListener('click', () => {
      selectAllForDelete();
    });
  }

  const deleteBtn = document.getElementById('bulkDeleteBtn');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      console.log('[BulkDeleteBtn] Clicked! selectedForDelete size:', selectedForDelete.size);
      deleteSelectedBacktests();
    });
  }
}

// Setup chart container resize observer
function setupChartResize() {
  const chartContainer = document.querySelector('.tv-equity-chart-container');
  if (chartContainer) {
    const resizeObserver = new ResizeObserver(() => {
      if (_brTVEquityChart && _brTVEquityChart.chart) {
        _brTVEquityChart.chart.resize();
      }
    });
    resizeObserver.observe(chartContainer);
  }
}

// Note: Removed focus event handler - it was causing too many reloads
// The page now properly loads via DOMContentLoaded and URL parameter

function initCharts() {
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: '#8b949e' }
      }
    },
    scales: {
      x: {
        grid: { color: '#30363d' },
        ticks: {
          color: '#8b949e',
          maxTicksLimit: 12,
          maxRotation: 45,
          minRotation: 0
        }
      },
      y: {
        grid: { color: '#30363d' },
        ticks: { color: '#8b949e' }
      }
    }
  };
  const equityContainer = document.getElementById('equityChartContainer');
  if (equityContainer && typeof TradingViewEquityChart !== 'undefined') {
    _brTVEquityChart = new TradingViewEquityChart('equityChartContainer', { // eslint-disable-line no-undef
      showBuyHold: document.getElementById('legendBuyHold')?.checked ?? true,
      showTradeExcursions: document.getElementById('legendTradesExcursions')?.checked ?? true,
      height: null  // let CSS (.tv-equity-inner-container) control the height
    });
    setChart('_tvEquityChart', _brTVEquityChart);
    // Keep equityChart as thin shim so legacy code that checks `equityChart` still passes truthy
    equityChart = { _tvChart: _brTVEquityChart, canvas: equityContainer, _tradeMap: {}, _tradeRanges: [], _equityData: [], _initialCapital: 10000, _showTradeExcursions: true };
    setChart('equity', equityChart);
  }

  // Drawdown Chart
  const drawdownCanvas = document.getElementById('drawdownChart');
  if (drawdownCanvas) {
    drawdownChart = chartManager.init('drawdown', drawdownCanvas, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Drawdown %',
            data: [],
            borderColor: '#f85149',
            backgroundColor: 'rgba(248, 81, 73, 0.1)',
            fill: true,
            tension: 0.4
          }
        ]
      },
      options: chartOptions
    });
  }

  // Returns Distribution
  const returnsCanvas = document.getElementById('returnsChart');
  if (returnsCanvas) {
    returnsChart = chartManager.init('returns', returnsCanvas, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Trade Returns',
            data: [],
            backgroundColor: []
          }
        ]
      },
      options: {
        ...chartOptions,
        plugins: {
          ...chartOptions.plugins,
          legend: { display: false }
        }
      }
    });
  }

  // Monthly P&L
  const monthlyCanvas = document.getElementById('monthlyChart');
  if (monthlyCanvas) {
    monthlyChart = chartManager.init('monthly', monthlyCanvas, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Monthly P&L',
            data: [],
            backgroundColor: []
          }
        ]
      },
      options: chartOptions
    });
  }

  // Trade Distribution Chart (in Trade Analysis tab)
  const tradeDistCanvas = document.getElementById('tradeDistributionChart');
  if (tradeDistCanvas) {
    tradeDistributionChart = chartManager.init('tradeDistribution', tradeDistCanvas, {
      type: 'bar',
      data: {
        labels: [],
        datasets: []
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#ffffff',
              usePointStyle: true,
              pointStyle: 'circle',
              padding: 15,
              font: { size: 12 }
            }
          },
          tooltip: {
            backgroundColor: 'rgba(22, 27, 34, 0.95)',
            titleColor: '#c9d1d9',
            bodyColor: '#c9d1d9',
            borderColor: '#30363d',
            borderWidth: 1
          },
          datalabels: {
            display: (ctx) => {
              const val = ctx.dataset.data[ctx.dataIndex];
              return typeof val === 'number' && val > 0;
            },
            anchor: 'end',
            align: 'top',
            color: '#c9d1d9',
            font: { size: 11 },
            formatter: (val) => (val > 0 ? val : '')
          }
        },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            title: {
              display: true,
              text: 'Доходность за сделку (%)',
              color: '#8b949e',
              font: { size: 11 }
            },
            ticks: {
              color: '#e6edf3',
              font: { size: 11 },
              maxRotation: 45,
              minRotation: 45
            }
          },
          y: {
            position: 'right',
            grid: { color: '#30363d' },
            title: {
              display: true,
              text: 'Количество сделок',
              color: '#8b949e',
              font: { size: 11 }
            },
            ticks: { color: '#e6edf3', font: { size: 11 } },
            beginAtZero: true
          }
        },
        layout: {
          padding: {
            bottom: 10
          }
        }
      }
    });
  }

  // Win/Loss Donut Chart (in Trade Analysis tab)
  const winLossCanvas = document.getElementById('winLossDonutChart');
  if (winLossCanvas) {
    winLossDonutChart = chartManager.init('winLossDonut', winLossCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Победы', 'Убытки', 'Безубыточность'],
        datasets: [
          {
            data: [0, 0, 0],
            backgroundColor: ['#26a69a', '#ef5350', '#78909c'],
            borderWidth: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1,
        cutout: '60%',
        layout: {
          padding: 5
        },
        plugins: {
          legend: {
            display: false // Use custom HTML legend
          },
          tooltip: {
            backgroundColor: 'rgba(22, 27, 34, 0.95)',
            callbacks: {
              label: function (context) {
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const pct =
                  total > 0 ? ((context.raw / total) * 100).toFixed(2) : 0;
                return `${context.label}: ${context.raw} (${pct}%)`;
              }
            }
          },
          centerLabel: {
            text: '0',
            subText: 'Всего сделок'
          }
        }
      }
    });
  }

  // Waterfall Chart (in Dynamics tab)
  const waterfallCanvas = document.getElementById('waterfallChart');
  if (waterfallCanvas) {
    waterfallChart = chartManager.init('waterfall', waterfallCanvas, {
      type: 'bar',
      data: {
        labels: [
          'Итого прибыль',
          'Открытые ПР/УБ',
          'Итого убыток',
          'Комиссия',
          'Общие ПР/УБ'
        ],
        datasets: []
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'x',
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#ffffff',
              usePointStyle: true,
              pointStyle: 'rect',
              padding: 15,
              font: { size: 11 },
              filter: (item) => item.text !== '_base'
            }
          },
          tooltip: {
            backgroundColor: 'rgba(22, 27, 34, 0.95)',
            titleColor: '#c9d1d9',
            bodyColor: '#c9d1d9',
            borderColor: '#30363d',
            borderWidth: 1,
            filter: (tooltipItem) => tooltipItem.dataset.label !== '_base',
            callbacks: {
              label: function (context) {
                const val = context.raw;
                if (val === null || val === undefined || val === 0) return null;
                // Floating bar: val is [min, max]
                if (Array.isArray(val)) {
                  const amount = Math.abs(val[1] - val[0]);
                  return `${context.dataset.label}: ${amount.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
                }
                return `${context.dataset.label}: ${val.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
              }
            }
          },
          datalabels: {
            display: (ctx) => {
              if (ctx.dataset.label === '_base') return false;
              const val = ctx.dataset.data[ctx.dataIndex];
              if (!Array.isArray(val)) return false;
              const height = Math.abs(val[1] - val[0]);
              return height > 1; // only show if bar has visible height
            },
            anchor: 'center',
            align: 'center',
            color: '#ffffff',
            font: { size: 11, weight: 'bold' },
            formatter: (val) => {
              if (!Array.isArray(val)) return '';
              const amount = Math.abs(val[1] - val[0]);
              if (amount < 0.01) return '';
              return amount >= 1000
                ? `${(amount / 1000).toFixed(1)}K`
                : amount.toFixed(0);
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            ticks: { color: '#e6edf3', font: { size: 11 } }
          },
          y: {
            stacked: true,
            position: 'right',
            title: {
              display: true,
              text: 'USD',
              color: '#8b949e',
              font: { size: 11 }
            },
            grid: { color: '#30363d' },
            ticks: {
              color: '#e6edf3',
              callback: (v) =>
                v >= 1000 ? (v / 1000).toFixed(2) + ' K' : v.toFixed(0)
            }
          }
        }
      }
    });
  }

  // Benchmarking Chart (in Dynamics tab) — TV "Сравнение" style
  const benchmarkingCanvas = document.getElementById('benchmarkingChart');
  if (benchmarkingCanvas) {
    benchmarkingChart = chartManager.init('benchmarking', benchmarkingCanvas, {
      type: 'bar',
      data: {
        // One label per row (BH row + Strategy row)
        labels: ['Покупка и удержание', 'Прибыльность стратегии'],
        datasets: []
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',   // horizontal bars
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#ffffff',
              usePointStyle: true,
              pointStyle: 'circle',
              padding: 20,
              font: { size: 12 },
              // Show only range datasets (index 0 = BH range, index 2 = Strategy range)
              filter: (item) => item.datasetIndex === 0 || item.datasetIndex === 2
            }
          },
          tooltip: {
            backgroundColor: 'rgba(22, 27, 34, 0.97)',
            titleColor: '#c9d1d9',
            bodyColor: '#c9d1d9',
            borderColor: '#444c56',
            borderWidth: 1,
            padding: 10,
            callbacks: {
              // Title = row label (BH or Strategy)
              title: (items) => items[0]?.label || '',
              // Body: show Макс / Текущ. цена / Мин  (TV style)
              label: () => null,
              afterBody: function (items) {
                if (!items.length) return [];
                const chart = items[0].chart;
                const rowIdx = items[0].dataIndex;   // 0=BH, 1=Strategy
                // Extract values stored on chart instance during update
                const info = chart._tvBenchInfo?.[rowIdx];
                if (!info) return [];
                return [
                  `  Макс           ${info.max.toFixed(2)}%`,
                  `  Текущ. цена   ${info.cur.toFixed(2)}%`,
                  `  Мин             ${info.min.toFixed(2)}%`
                ];
              }
            }
          },
          datalabels: { display: false }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Доходность (%)',
              color: '#8b949e',
              font: { size: 11 }
            },
            grid: { color: 'rgba(48,54,61,0.6)' },
            ticks: {
              color: '#8b949e',
              callback: (v) => v.toFixed(0) + '%'
            }
          },
          y: {
            grid: { display: false },
            ticks: { color: '#e6edf3', font: { size: 12 } }
          }
        }
      }
    });
  }
  // Sync all chart instances to StateManager after init
  setChart('drawdown', drawdownChart);
  setChart('returns', returnsChart);
  setChart('monthly', monthlyChart);
  setChart('tradeDistribution', tradeDistributionChart);
  setChart('winLossDonut', winLossDonutChart);
  setChart('waterfall', waterfallChart);
  setChart('benchmarking', benchmarkingChart);
}

// ============================
// TradingView Style Tabs
// ============================
function initTradingViewTabs() {
  const tabs = document.querySelectorAll('.tv-report-tab');
  const contents = document.querySelectorAll('.tv-report-tab-content');

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const targetTab = tab.dataset.tab;

      // Remove active from all tabs and contents
      tabs.forEach((t) => t.classList.remove('active'));
      contents.forEach((c) => c.classList.remove('active'));

      // Activate clicked tab and its content
      tab.classList.add('active');
      const content = document.getElementById(`tab-${targetTab}`);
      if (content) {
        content.classList.add('active');
      }

      // Lazy-init price chart when its tab becomes visible (needs non-zero container dimensions)
      if (targetTab === 'price-chart') {
        console.log('[TabClick] price-chart tab clicked, pending=', btPriceChartPending,
          'currentBacktest=', currentBacktest?.config?.symbol, currentBacktest?.config?.interval);
        if (btPriceChartPending && currentBacktest) {
          btPriceChartPending = false;
          setPriceChartPending(false);
          updatePriceChart(currentBacktest);
        }
      }
    });
  });

  // Initialize chart legend checkboxes
  initChartLegendControls();

  // Initialize chart mode toggle
  initChartModeToggle();
}

// Chart legend checkbox controls
function initChartLegendControls() {
  const legendBuyHold = document.getElementById('legendBuyHold');
  const legendTradesExcursions = document.getElementById('legendTradesExcursions');

  // Buy & Hold toggle — delegate to TradingViewEquityChart
  if (legendBuyHold) {
    legendBuyHold.addEventListener('change', () => {
      if (_brTVEquityChart) {
        _brTVEquityChart.toggleBuyHold(legendBuyHold.checked);
      }
    });
  }

  // MFE/MAE excursion bars toggle — delegate to TradingViewEquityChart
  if (legendTradesExcursions) {
    // Restore persisted state (default is checked)
    const saved = localStorage.getItem('tv_trades_excursions');
    if (saved === '0') {
      legendTradesExcursions.checked = false;
      if (_brTVEquityChart) _brTVEquityChart.toggleTradeExcursions(false);
    }

    legendTradesExcursions.addEventListener('change', () => {
      localStorage.setItem('tv_trades_excursions', legendTradesExcursions.checked ? '1' : '0');
      if (_brTVEquityChart) {
        _brTVEquityChart.toggleTradeExcursions(legendTradesExcursions.checked);
      }
    });
  }

  const legendRegimeOverlay = document.getElementById('legendRegimeOverlay');
  if (legendRegimeOverlay) {
    legendRegimeOverlay.addEventListener('change', () => {
      if (currentBacktest) {
        if (legendRegimeOverlay.checked) {
          loadAndApplyRegimeOverlay(currentBacktest);
        } else {
          clearRegimeOverlay();
        }
      }
    });
  }
}

function clearRegimeOverlay() {
  const innerChart = _brTVEquityChart?.chart;
  if (!innerChart?.options?.plugins?.annotation?.annotations) return;
  const ann = innerChart.options.plugins.annotation.annotations;
  Object.keys(ann).forEach((k) => {
    if (k.startsWith('regime_')) delete ann[k];
  });
  innerChart.update('none');
}

// ============================
// Equity growth / drawdown cycles (TV-like "Рост средств / Просадка средств")
// ============================

function computeEquityGrowthDrawdownSegments(timestamps, equityArr) {
  if (!Array.isArray(timestamps) || !Array.isArray(equityArr)) return [];
  const n = Math.min(timestamps.length, equityArr.length);
  if (n < 2) return [];

  const segments = [];
  let regime = 'growth';
  let segStart = 0;
  let hwm = Number(equityArr[0] ?? 0);
  let ddMin = hwm;
  let ddMinIdx = 0;

  const num = (v) => {
    const x = Number(v);
    return Number.isFinite(x) ? x : 0;
  };

  for (let i = 1; i < n; i += 1) {
    const v = num(equityArr[i]);
    if (regime === 'growth') {
      if (v >= hwm) {
        hwm = v;
      } else {
        const start = segStart;
        const end = i - 1;
        if (end > start) {
          const startV = num(equityArr[start]);
          const endV = num(equityArr[end]);
          const absChange = endV - startV;
          const pctChange = startV !== 0 ? absChange / startV : 0;
          segments.push({
            kind: 'growth',
            startIndex: start,
            endIndex: end,
            startTime: timestamps[start],
            endTime: timestamps[end],
            absChange,
            pctChange
          });
        }
        regime = 'drawdown';
        segStart = end;
        ddMin = v;
        ddMinIdx = i;
      }
    } else {
      if (v <= ddMin) {
        ddMin = v;
        ddMinIdx = i;
      }
      if (v >= hwm) {
        const start = segStart;
        const end = ddMinIdx;
        if (end > start) {
          const startV = num(equityArr[start]);
          const endV = num(equityArr[end]);
          const absChange = startV - endV;
          const pctChange = startV !== 0 ? absChange / startV : 0;
          segments.push({
            kind: 'drawdown',
            startIndex: start,
            endIndex: end,
            startTime: timestamps[start],
            endTime: timestamps[end],
            absChange,
            pctChange
          });
        }
        regime = 'growth';
        segStart = end;
        hwm = v;
      }
    }
  }

  const lastIdx = n - 1;
  if (segStart < lastIdx) {
    const start = segStart;
    const end = lastIdx;
    const startV = num(equityArr[start]);
    const endV = num(equityArr[end]);
    if (end > start) {
      if (regime === 'growth') {
        const absChange = endV - startV;
        const pctChange = startV !== 0 ? absChange / startV : 0;
        segments.push({
          kind: 'growth',
          startIndex: start,
          endIndex: end,
          startTime: timestamps[start],
          endTime: timestamps[end],
          absChange,
          pctChange
        });
      } else {
        let minV = startV;
        let minIdx = start;
        for (let j = start; j <= end; j += 1) {
          const vj = num(equityArr[j]);
          if (vj <= minV) {
            minV = vj;
            minIdx = j;
          }
        }
        const absChange = startV - minV;
        const pctChange = startV !== 0 ? absChange / startV : 0;
        segments.push({
          kind: 'drawdown',
          startIndex: start,
          endIndex: minIdx,
          startTime: timestamps[start],
          endTime: timestamps[minIdx],
          absChange,
          pctChange
        });
      }
    }
  }

  return segments;
}

function clearEquityGrowthDrawdownOverlay() {
  const innerChart = _brTVEquityChart?.chart;
  if (!innerChart) return;

  innerChart._equityCycles = [];

  const tooltip = innerChart.options?.plugins?.tooltip;
  if (tooltip && tooltip._equityCyclesOriginalAfterBody) {
    tooltip.afterBody = tooltip._equityCyclesOriginalAfterBody;
    delete tooltip._equityCyclesOriginalAfterBody;
  }

  if (typeof innerChart.update === 'function') {
    innerChart.update('none');
  }
}

function applyEquityGrowthDrawdownOverlay() {
  const innerChart = _brTVEquityChart?.chart;
  const tvData = _brTVEquityChart?.data;
  if (!innerChart || !tvData?.timestamps?.length || !tvData?.equity?.length) {
    clearEquityGrowthDrawdownOverlay();
    return;
  }

  const timestamps = tvData.timestamps;
  const equityArr = tvData.equity;
  const segments = computeEquityGrowthDrawdownSegments(timestamps, equityArr);
  if (!segments.length) {
    clearEquityGrowthDrawdownOverlay();
    return;
  }

  innerChart._equityCycles = segments;

  innerChart.options.plugins = innerChart.options.plugins || {};
  innerChart.options.plugins.tooltip = innerChart.options.plugins.tooltip || {};
  const tooltip = innerChart.options.plugins.tooltip;

  if (!tooltip._equityCyclesOriginalAfterBody) {
    tooltip._equityCyclesOriginalAfterBody = tooltip.afterBody;
  }

  const baseAfterBody = tooltip._equityCyclesOriginalAfterBody;

  tooltip.afterBody = (ctxItems) => {
    const baseLines = typeof baseAfterBody === 'function' ? baseAfterBody(ctxItems) : [];
    const items = Array.isArray(ctxItems) ? ctxItems : [];
    const first = items[0];
    if (!first || !segments.length) return baseLines;

    const idx = first.dataIndex;
    const seg = segments.find((s) => s.startIndex <= idx && idx <= s.endIndex);
    if (!seg) return baseLines;

    const isGrowth = seg.kind === 'growth';
    const label = isGrowth ? 'Рост средств' : 'Просадка средств';
    const amountAbs = Math.abs(seg.absChange);
    const pctAbs = Math.abs(seg.pctChange * 100);
    const sign = isGrowth ? '+' : '-';

    const amountStr = amountAbs.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    const pctStr = pctAbs.toFixed(2);

    const startDate = new Date(seg.startTime);
    const endDate = new Date(seg.endTime);
    const rangeStr = `${startDate.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' })} — ${endDate.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' })}`;

    const extraLines = [
      `${label}: ${sign}$${amountStr} (${pctStr}%)`,
      rangeStr
    ];

    if (!baseLines || baseLines.length === 0) return extraLines;
    return [...baseLines, ...extraLines];
  };

  innerChart.update('none');
}

async function loadAndApplyRegimeOverlay(backtest) {
  const innerChart = _brTVEquityChart?.chart;
  if (!innerChart || !_brTVEquityChart?.data?.timestamps?.length) return;
  const symbol = backtest.symbol || backtest.config?.symbol;
  const rawInterval = backtest.interval || backtest.config?.interval || '60';
  if (!symbol) return;
  const s = String(rawInterval);
  const intervalMap = { 1: '1m', 5: '5m', 15: '15m', 30: '30m', 60: '1h', 120: '2h', 240: '4h', 360: '6h', 720: '12h', D: '1d', W: '1w' };
  const interval = intervalMap[s] || (/^(\d+[mhdw]|[mhdw])$/i.test(s) ? s : '1h');

  // Build equityData array from TV chart's stored data
  const tvData = _brTVEquityChart.data;
  const equityData = tvData.timestamps.map((t, i) => ({
    timestamp: t,
    equity: tvData.equity ? tvData.equity[i] : null
  }));
  const firstTs = equityData[0]?.timestamp;
  const lastTs = equityData[equityData.length - 1]?.timestamp;
  const days = firstTs && lastTs ? Math.max(7, Math.ceil((new Date(lastTs) - new Date(firstTs)) / (24 * 60 * 60 * 1000))) : 30;

  try {
    const res = await fetch(`${API_BASE}/market-regime/history/${encodeURIComponent(symbol)}?interval=${encodeURIComponent(interval)}&days=${days}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data?.history?.length) return;

    const toMs = (t) => {
      if (typeof t === 'number') return t < 1e12 ? t * 1000 : t;
      const d = new Date(t);
      return isNaN(d) ? 0 : d.getTime();
    };
    const regimeColors = { trending_up: 'rgba(38,166,154,0.15)', trending_down: 'rgba(239,83,80,0.15)', ranging: 'rgba(120,144,156,0.15)', volatile: 'rgba(255,167,38,0.2)', breakout_up: 'rgba(102,187,106,0.12)', breakout_down: 'rgba(244,67,54,0.12)', unknown: 'rgba(158,158,158,0.08)' };

    const regHist = data.history.map((h) => ({ ts: toMs(h.timestamp), regime: h.regime || 'unknown' })).sort((a, b) => a.ts - b.ts);
    if (regHist.length === 0) return;

    const getRegimeAt = (eqTs) => {
      const ms = toMs(eqTs);
      let best = regHist[0];
      let bestDiff = Math.abs(regHist[0].ts - ms);
      for (const r of regHist) {
        const d = Math.abs(r.ts - ms);
        if (d < bestDiff) { bestDiff = d; best = r; }
      }
      return best.regime;
    };

    const regimePerIdx = equityData.map((p) => getRegimeAt(p.timestamp));
    const segments = [];
    let start = 0;
    for (let i = 1; i <= regimePerIdx.length; i++) {
      if (i === regimePerIdx.length || regimePerIdx[i] !== regimePerIdx[start]) {
        segments.push({ start, end: i - 1, regime: regimePerIdx[start] });
        start = i;
      }
    }

    const ann = innerChart.options.plugins.annotation.annotations;
    Object.keys(ann).forEach((k) => { if (k.startsWith('regime_')) delete ann[k]; });
    segments.forEach((seg, idx) => {
      if (seg.end < seg.start) return;
      ann[`regime_${idx}`] = {
        type: 'box',
        xMin: seg.start - 0.5,
        xMax: seg.end + 0.5,
        yMin: 'chartMin',
        yMax: 'chartMax',
        backgroundColor: regimeColors[seg.regime] || regimeColors.unknown,
        borderWidth: 0,
        drawTime: 'beforeDatasetsDraw'
      };
    });
    innerChart.update('none');
  } catch (e) {
    console.warn('[Regime overlay] Failed to load:', e.message);
  }
}

// Chart mode toggle (Absolute / Percent)
let chartDisplayMode = 'absolute';

function initChartModeToggle() {
  const btnAbsolute = document.getElementById('btnAbsoluteMode');
  const btnPercent = document.getElementById('btnPercentMode');

  if (btnAbsolute) {
    btnAbsolute.addEventListener('click', () => {
      if (chartDisplayMode !== 'absolute') {
        chartDisplayMode = 'absolute';
        btnAbsolute.classList.add('active');
        btnPercent?.classList.remove('active');
        updateChartDisplayMode();
      }
    });
  }

  if (btnPercent) {
    btnPercent.addEventListener('click', () => {
      if (chartDisplayMode !== 'percent') {
        chartDisplayMode = 'percent';
        btnPercent.classList.add('active');
        btnAbsolute?.classList.remove('active');
        updateChartDisplayMode();
      }
    });
  }
}

function updateChartDisplayMode() {
  if (_brTVEquityChart) {
    _brTVEquityChart.setDisplayMode(chartDisplayMode);
  }
}

// Update Trades List Tab (Tab 5) - TradingView Style with pagination and sorting
function updateTVTradesListTab(trades, config) {
  const tbody = document.getElementById('tvTradesListBody');
  const countEl = document.getElementById('tvTradesCount');

  if (!tbody) return;

  if (!trades || trades.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="10" style="text-align:center;color:#8b949e;padding:2rem;">Нет сделок для отображения</td></tr>';
    if (countEl) countEl.textContent = '0';
    removePagination();
    return;
  }

  if (countEl) countEl.textContent = trades.length;

  const initialCapital = config?.initial_capital || 10000;
  tradesCachedRows = buildTradeRows(trades, initialCapital, tradesSortKey, tradesSortAsc);
  tradesCurrentPage = 0;
  setTradesCachedRows(tradesCachedRows);
  setTradesCurrentPage(0);
  renderTradesPageUtil(tbody, tradesCachedRows, tradesCurrentPage);
  updatePaginationControls(tradesCachedRows.length, tradesCurrentPage);
  const container = document.getElementById('tvTradesContainer') ||
    document.querySelector('.tv-trades-container');
  renderPagination(container, trades.length, tradesCurrentPage);
}

/** Renders the current page of cached trade rows into tbody */
function renderTradesPage(tbody) {
  const tgt = tbody || document.getElementById('tvTradesListBody');
  if (!tgt) return;
  renderTradesPageUtil(tgt, tradesCachedRows, tradesCurrentPage);
  updatePaginationControls(tradesCachedRows.length, tradesCurrentPage);
}

// eslint-disable-next-line no-unused-vars
function tradesPrevPage() {
  // Pagination disabled - all trades shown in single scrollable list
  console.warn('tradesPrevPage: Pagination is disabled');
}

// eslint-disable-next-line no-unused-vars
function tradesNextPage() {
  // Pagination disabled - all trades shown in single scrollable list
  console.warn('tradesNextPage: Pagination is disabled');
}

/** Sort trades table by column key. Called from table header click handlers. */
// eslint-disable-next-line no-unused-vars
function sortTradesBy(key) {
  tradesSortAsc = tradesSortKey === key ? !tradesSortAsc : true;
  tradesSortKey = key;
  setTradesSortKey(tradesSortKey);
  setTradesSortAsc(tradesSortAsc);
  sortRows(tradesCachedRows, key, tradesSortAsc);
  tradesCurrentPage = 0;
  setTradesCurrentPage(0);
  renderTradesPage();
  updateSortIndicators(key, tradesSortAsc);
}

// Update Report Header
function updateTVReportHeader(backtest) {
  const strategyName = document.getElementById('tvReportStrategyName');
  const dateRange = document.getElementById('tvReportDateRange');

  if (strategyName && backtest?.config) {
    strategyName.textContent = `Стратегия ${backtest.config.strategy_type || 'Unknown'} Отчёт`;
  }

  if (dateRange && backtest?.config) {
    const start = backtest.config.start_date
      ? new Date(backtest.config.start_date).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      })
      : '--';
    const end = backtest.config.end_date
      ? new Date(backtest.config.end_date).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      })
      : '--';
    dateRange.textContent = `${start} – ${end}`;
  }
}

// eslint-disable-next-line no-unused-vars
function initTradesTable() {
  // Tabulator table is deprecated, using TradingView style table instead
  // Kept for backward compatibility
  const tradesTableEl = document.getElementById('tradesTable');
  if (tradesTableEl && typeof Tabulator !== 'undefined') {
    tradesTable = new Tabulator('#tradesTable', {
      height: 300,
      layout: 'fitColumns',
      placeholder: 'No trades to display',
      columns: [
        { title: '#', field: 'id', width: 50 },
        { title: 'Entry Time', field: 'entry_time', sorter: 'datetime' },
        { title: 'Exit Time', field: 'exit_time', sorter: 'datetime' },
        {
          title: 'Side',
          field: 'side',
          width: 80,
          formatter: (cell) => {
            const val = cell.getValue();
            const color = val === 'long' ? '#3fb950' : '#f85149';
            return `<span style="color: ${color}">${val?.toUpperCase()}</span>`;
          }
        },
        {
          title: 'Entry Price',
          field: 'entry_price',
          formatter: 'money',
          formatterParams: { precision: 2 }
        },
        {
          title: 'Exit Price',
          field: 'exit_price',
          formatter: 'money',
          formatterParams: { precision: 2 }
        },
        {
          title: 'Size',
          field: 'size',
          formatter: 'money',
          formatterParams: { precision: 4 }
        },
        {
          title: 'P&L',
          field: 'pnl',
          formatter: (cell) => {
            const val = cell.getValue();
            const color = val >= 0 ? '#3fb950' : '#f85149';
            return `<span style="color: ${color}">$${val?.toFixed(2)}</span>`;
          }
        },
        {
          title: 'Return %',
          field: 'return_pct',
          formatter: (cell) => {
            const val = cell.getValue();
            const color = val >= 0 ? '#3fb950' : '#f85149';
            return `<span style="color: ${color}">${val?.toFixed(2)}%</span>`;
          }
        }
      ]
    });
  }
}

function setDefaultDates() {
  const endDate = new Date();
  const startDate = new Date();
  startDate.setMonth(startDate.getMonth() - 6);

  // Use local date (not UTC) to avoid off-by-one at midnight in UTC+N timezones
  document.getElementById('btEndDate').value = localDateStr(endDate);
  document.getElementById('btStartDate').value = localDateStr(startDate);
}

function setupFilters() {
  ['filterStrategy', 'filterSymbol', 'filterPnL', 'filterSearch'].forEach(
    (id) => {
      document.getElementById(id).addEventListener('change', applyFilters);
    }
  );
  document
    .getElementById('filterSearch')
    .addEventListener('input', applyFilters);
}

// ============================
// Data Loading
// ============================
async function loadBacktestResults() {
  console.log('[loadBacktestResults] Loading backtests...');

  // PRIORITY: Check URL for specific backtest ID first (from optimization/backtest redirect)
  const urlParams = new URLSearchParams(window.location.search);
  // Accept both ?id= (legacy) and ?backtest_id= (sent by strategy_builder)
  const targetId = urlParams.get('backtest_id') || urlParams.get('id');

  if (targetId) {
    console.log('[loadBacktestResults] URL contains targetId:', targetId);
    try {
      // Load the specific backtest directly - don't depend on list endpoint
      const directResponse = await fetch(`${API_BASE}/backtests/${targetId}`);
      if (directResponse.ok) {
        const backtestData = await directResponse.json();
        console.log(
          '[loadBacktestResults] Loaded backtest directly by ID:',
          targetId
        );

        // Initialize UI with this single backtest
        allResults = [
          {
            ...backtestData,
            backtest_id: backtestData.id || targetId,
            symbol: backtestData.config?.symbol || 'Unknown',
            interval: backtestData.config?.interval || '--',
            strategy_type: backtestData.config?.strategy_type || 'Unknown',
            metrics: backtestData.metrics || {}
          }
        ];
        setAllResults(allResults);

        document.getElementById('resultsCount').textContent = '1';
        document.getElementById('emptyState').classList.add('d-none');
        renderResultsList(allResults);
        selectBacktest(targetId);

        // Try to load full list in background (optional, may fail)
        loadBacktestListBackground();
        return;
      } else {
        console.warn(
          '[loadBacktestResults] Direct load failed, falling back to list'
        );
      }
    } catch (err) {
      console.warn('[loadBacktestResults] Direct load error:', err);
    }
  }

  // Fallback: Load full list
  await loadBacktestListFromAPI();
}

// Background loading of full list (non-blocking)
async function loadBacktestListBackground() {
  try {
    // Add cache buster to prevent browser caching stale data
    const url = `${API_BASE}/backtests/?limit=100&_t=${Date.now()}`;
    const response = await fetch(url, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' }
    });
    if (!response.ok) {
      console.warn(
        '[loadBacktestListBackground] List endpoint returned',
        response.status
      );
      return;
    }
    const data = await response.json();

    // Merge with existing results (avoid duplicates)
    const existingIds = new Set(allResults.map((r) => r.backtest_id));
    const newResults = (data.items || [])
      .filter(
        (item) =>
          !existingIds.has(item.id) && !existingIds.has(item.backtest_id)
      )
      .filter(
        (item) =>
          !recentlyDeletedIds.has(item.id) &&
          !recentlyDeletedIds.has(item.backtest_id)
      )
      .map((item) => ({
        ...item,
        backtest_id: item.id || item.backtest_id,
        symbol: item.symbol || item.config?.symbol || 'Unknown',
        interval: item.interval || item.config?.interval || '--',
        strategy_type:
          item.strategy_type || item.config?.strategy_type || 'Unknown'
      }));

    if (newResults.length > 0) {
      allResults = [...allResults, ...newResults];
      setAllResults(allResults);
      document.getElementById('resultsCount').textContent = allResults.length;
      renderResultsList(allResults);
      populateFilters();
    }
  } catch (err) {
    console.warn(
      '[loadBacktestListBackground] Background list load failed:',
      err
    );
  }
}

// Original list loading logic
async function loadBacktestListFromAPI() {
  try {
    // Add cache buster to prevent browser caching stale data
    const url = `${API_BASE}/backtests/?limit=100&_t=${Date.now()}`;
    const response = await fetch(url, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' }
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();

    // Normalize API response - map nested config fields to top level
    // Filter out recently deleted IDs to prevent "ghost" items from backend sync delay
    allResults = (data.items || [])
      .filter(
        (item) =>
          !recentlyDeletedIds.has(item.id) &&
          !recentlyDeletedIds.has(item.backtest_id)
      )
      .map((item) => ({
        ...item,
        backtest_id: item.id || item.backtest_id,
        symbol: item.symbol || item.config?.symbol || 'Unknown',
        interval: item.interval || item.config?.interval || '--',
        strategy_type:
          item.strategy_type || item.config?.strategy_type || 'Unknown'
      }));
    setAllResults(allResults);
    console.log(
      '[loadBacktestListFromAPI] Loaded',
      allResults.length,
      'backtests'
    );
    document.getElementById('resultsCount').textContent = allResults.length;

    if (allResults.length === 0) {
      document.getElementById('emptyState').classList.remove('d-none');
      document.getElementById('resultsList').innerHTML = '';
    } else {
      document.getElementById('emptyState').classList.add('d-none');
      renderResultsList(allResults);

      // Auto-select first result
      selectBacktest(allResults[0].backtest_id);
    }

    populateFilters();
  } catch (error) {
    console.error('Failed to load backtest results:', error);
    showToast('Ошибка загрузки списка бэктестов', 'error');

    // Show empty state with error message
    document.getElementById('emptyState').classList.remove('d-none');
    document.getElementById('resultsList').innerHTML = '';
  }
}

// ============================
// Bulk Select & Delete
// ============================

/**
 * Toggle a single item in the bulk-select set.
 * Updates visual state and toolbar without full re-render.
 */
function toggleBulkSelectItem(backtestId) {
  console.log('[BulkSelect] Toggle:', backtestId);
  if (selectedForDelete.has(backtestId)) {
    selectedForDelete.delete(backtestId);
  } else {
    selectedForDelete.add(backtestId);
  }

  // Update visual state for this item
  const item = document.querySelector(
    `.result-item[data-id="${backtestId}"]`
  );
  if (item) {
    item.classList.toggle(
      'marked-for-delete',
      selectedForDelete.has(backtestId)
    );
    const cb = item.querySelector('.bulk-select-checkbox');
    if (cb) cb.checked = selectedForDelete.has(backtestId);
  }

  updateBulkDeleteToolbar();
}

/**
 * Select All / Deselect All toggle.
 * If all currently visible items are selected, deselect all.
 * Otherwise, select all visible items.
 */
function selectAllForDelete() {
  const visibleItems = document.querySelectorAll(
    '.result-item[data-id]'
  );
  const allSelected =
    visibleItems.length > 0 &&
    [...visibleItems].every((el) => selectedForDelete.has(el.dataset.id));

  if (allSelected) {
    // Deselect all
    selectedForDelete.clear();
  } else {
    // Select all visible
    visibleItems.forEach((el) => selectedForDelete.add(el.dataset.id));
  }

  // Update visual state
  visibleItems.forEach((el) => {
    const isChecked = selectedForDelete.has(el.dataset.id);
    el.classList.toggle('marked-for-delete', isChecked);
    const cb = el.querySelector('.bulk-select-checkbox');
    if (cb) cb.checked = isChecked;
  });

  updateBulkDeleteToolbar();
}

/**
 * Clear all display data (charts, metrics, trades list, price chart)
 * when no backtests remain after deletion.
 */
function clearAllDisplayData() {
  console.log('[clearAllDisplayData] Clearing all charts and metrics');
  setCurrentBacktest(null);

  // --- Equity Chart (TradingViewEquityChart) ---
  if (_brTVEquityChart) {
    // Re-render with empty data to clear the chart visually
    _brTVEquityChart.render({ timestamps: [], equity: [], bh_equity: [], trades: [], initial_capital: 10000 });
    clearEquityGrowthDrawdownOverlay();
  }

  // --- Drawdown / Returns / Monthly / Trade Analysis Charts (Chart.js) ---
  // Use chartManager.clearAll() to clear data without destroying instances.
  // This avoids "Canvas is already in use" on next initCharts() call.
  chartManager.clearAll('none');
  // Keep local references in sync (they still point to the same Chart instances)
  [drawdownChart, returnsChart, monthlyChart, tradeDistributionChart, winLossDonutChart, waterfallChart, benchmarkingChart].forEach((chart) => {
    if (chart && chart.canvas) {
      chart.data.labels = [];
      chart.data.datasets.forEach((ds) => (ds.data = []));
      chart.update('none');
    }
  });

  // --- Price Chart (LightweightCharts) ---
  if (_priceChartResizeObserver) {
    _priceChartResizeObserver.disconnect();
    _priceChartResizeObserver = null;
    setPriceChartResizeObserver(null);
  }
  if (btPriceChart) {
    btPriceChart.remove();
    btPriceChart = null;
    btCandleSeries = null;
    setPriceChart(null);
    setPriceChartCandleSeries(null);
  }
  btPriceChartMarkers = [];
  btTradeLineSeries = [];
  _btCachedCandles = [];
  btPriceChartPending = false;
  _priceChartGeneration++;
  setPriceChartMarkers([]);
  setPriceChartTradeLineSeries([]);
  setPriceChartCachedCandles([]);
  setPriceChartPending(false);
  setPriceChartGeneration(_priceChartGeneration);
  const priceContainer = document.getElementById('btPriceChartContainer');
  if (priceContainer) {
    // Restore default inner structure with empty candlestick chart + hidden loading
    priceContainer.innerHTML = `
      <div id="btCandlestickChart"></div>
      <div class="bt-price-chart-loading hidden" id="btPriceChartLoading">
        <div class="spinner-border spinner-border-sm text-secondary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <span class="ms-2 text-secondary">Загрузка свечных данных...</span>
      </div>`;
  }
  // Reset price chart title
  const priceTitle = document.getElementById('priceChartTitle');
  if (priceTitle) {
    priceTitle.innerHTML = '<i class="bi bi-graph-up-arrow me-1"></i>График цены';
  }

  // --- TradingView Equity Chart (custom component) ---
  if (window.tvEquityChart) {
    window.tvEquityChart = null;
  }

  // --- Summary Cards ---
  const cardIds = ['tvNetProfit', 'tvNetProfitPct', 'tvMaxDrawdown', 'tvMaxDrawdownPct', 'tvTotalTrades', 'tvWinningTrades', 'tvWinRate', 'tvProfitFactor'];
  cardIds.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = '--';
      el.className = 'tv-summary-card-value tv-value-neutral';
    }
  });
  // Sub-values reset class
  ['tvNetProfitPct', 'tvMaxDrawdownPct', 'tvWinRate'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.className = 'tv-summary-card-sub';
  });

  // --- Report Header ---
  const dateRange = document.getElementById('tvReportDateRange');
  if (dateRange) dateRange.textContent = '--';

  // --- Dynamics Tab (all dyn-* elements) ---
  document.querySelectorAll('[id^="dyn-"]').forEach((el) => {
    el.textContent = '--';
    el.className = 'tv-value-neutral';
  });

  // --- Trade Analysis Tab (all ta-* elements) ---
  document.querySelectorAll('[id^="ta-"]').forEach((el) => {
    el.textContent = '--';
    el.className = 'tv-value-neutral';
  });

  // --- Risk-Return Tab (all rr-* elements) ---
  document.querySelectorAll('[id^="rr-"]').forEach((el) => {
    el.textContent = '--';
    el.className = 'tv-value-neutral';
  });

  // --- Trades List Tab ---
  const tbody = document.getElementById('tvTradesListBody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#8b949e;padding:2rem;">Нет сделок для отображения</td></tr>';
  }
  const countEl = document.getElementById('tvTradesCount');
  if (countEl) countEl.textContent = '0';

  // --- Tabulator table (legacy) ---
  if (tradesTable && typeof tradesTable.clearData === 'function') {
    tradesTable.clearData();
  }

  // --- Open trades count in summary ---
  const openTrades = document.getElementById('tvOpenTrades');
  if (openTrades) openTrades.textContent = '0';

  console.log('[clearAllDisplayData] All display data cleared');
}

/**
 * Delete all selected backtests in bulk.
 * Uses sequential API calls with optimistic UI updates.
 */
async function deleteSelectedBacktests() {
  const count = selectedForDelete.size;
  console.log('[BulkDelete] Called, selected count:', count, 'ids:', [...selectedForDelete]);
  if (count === 0) {
    showToast('Не выбрано ни одного бэктеста', 'warning');
    return;
  }

  if (!confirm(`Удалить ${count} бэктест(ов)?`)) {
    console.log('[BulkDelete] User cancelled');
    return;
  }

  console.log('[BulkDelete] User confirmed, starting deletion...');
  const idsToDelete = [...selectedForDelete];
  let deleted = 0;
  let errors = 0;

  for (const id of idsToDelete) {
    try {
      console.log('[BulkDelete] Deleting:', id);
      const response = await fetch(`${API_BASE}/backtests/${id}`, {
        method: 'DELETE'
      });
      console.log('[BulkDelete] Response for', id, ':', response.status);
      if (response.ok) {
        deleted++;
        recentlyDeletedIds.add(id);
        setTimeout(() => recentlyDeletedIds.delete(id), 30000);
        allResults = allResults.filter((r) => r.backtest_id !== id);
        setAllResults(allResults);
      } else {
        errors++;
      }
    } catch {
      errors++;
    }
  }

  // Clear selection
  selectedForDelete.clear();

  // If deleted current backtest, clear selection
  if (
    currentBacktest &&
    idsToDelete.includes(currentBacktest.backtest_id)
  ) {
    setCurrentBacktest(null);
    if (_brTVEquityChart) {
      _brTVEquityChart.render({ timestamps: [], equity: [], bh_equity: [], trades: [], initial_capital: 10000 });
      clearEquityGrowthDrawdownOverlay();
    }
  }

  // Re-render
  renderResultsList(allResults);
  document.getElementById('resultsCount').textContent = allResults.length;
  updateBulkDeleteToolbar();

  // Select first remaining
  if (allResults.length > 0 && !currentBacktest) {
    selectBacktest(allResults[0].backtest_id);
  } else if (allResults.length === 0) {
    clearAllDisplayData();
    document.getElementById('emptyState').classList.remove('d-none');
  }

  // Toast summary
  if (errors === 0) {
    showToast(`Удалено ${deleted} бэктест(ов)`, 'success');
  } else {
    showToast(
      `Удалено ${deleted}, ошибок: ${errors}`,
      errors > deleted ? 'error' : 'warning'
    );
  }
}

/**
 * Update the bulk-delete toolbar visibility and count.
 */
function updateBulkDeleteToolbar() {
  const toolbar = document.getElementById('bulkDeleteToolbar');
  if (!toolbar) return;

  const count = selectedForDelete.size;
  const badge = document.getElementById('bulkDeleteCount');
  const selectAllCb = document.getElementById('selectAllCheckbox');

  if (count > 0) {
    toolbar.classList.remove('d-none');
    if (badge) badge.textContent = count;
  } else {
    toolbar.classList.add('d-none');
  }

  // Update "Select All" checkbox state
  if (selectAllCb) {
    const visibleItems = document.querySelectorAll(
      '.result-item[data-id]'
    );
    const allSelected =
      visibleItems.length > 0 &&
      [...visibleItems].every((el) =>
        selectedForDelete.has(el.dataset.id)
      );
    selectAllCb.checked = allSelected;
    selectAllCb.indeterminate =
      count > 0 && !allSelected;
  }
}

async function deleteBacktest(backtestId) {
  if (!confirm('Удалить этот бэктест?')) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/backtests/${backtestId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      showToast('Бэктест удалён', 'success');

      // Add to recently deleted blacklist to prevent ghost items on refresh
      recentlyDeletedIds.add(backtestId);
      // Auto-remove from blacklist after 30 seconds (backend should be synced by then)
      setTimeout(() => recentlyDeletedIds.delete(backtestId), 30000);

      // Optimistic UI update: immediately remove from local array
      // This prevents the "ghost" item from appearing due to backend sync delay
      allResults = allResults.filter((r) => r.backtest_id !== backtestId);
      setAllResults(allResults);

      // If we deleted the currently selected backtest, clear selection
      if (currentBacktest && currentBacktest.backtest_id === backtestId) {
        setCurrentBacktest(null);
        // Clear charts and show empty state
        if (_brTVEquityChart) {
          _brTVEquityChart.render({ timestamps: [], equity: [], bh_equity: [], trades: [], initial_capital: 10000 });
          clearEquityGrowthDrawdownOverlay();
        }
      }

      // Re-render the list with updated local data
      renderResultsList(allResults);

      // Update count
      document.getElementById('resultsCount').textContent = allResults.length;

      // If there are remaining results, select the first one
      if (allResults.length > 0 && !currentBacktest) {
        selectBacktest(allResults[0].backtest_id);
      } else if (allResults.length === 0) {
        // Clear all charts, metrics, and trade lists
        clearAllDisplayData();
        // Show empty state
        document.getElementById('emptyState').classList.remove('d-none');
      }

      // NO background refresh - local state is already correct
      // Background refresh was causing "ghost" items to reappear from browser cache
    } else {
      const error = await response.json();
      showToast(`Ошибка: ${error.detail}`, 'error');
    }
  } catch (error) {
    console.error('Failed to delete backtest:', error);
    showToast('Ошибка удаления', 'error');
  }
}

async function loadStrategies() {
  try {
    const response = await fetch(`${API_BASE}/strategies`);
    const data = await response.json();

    // Handle both array and paginated response
    const strategies = Array.isArray(data) ? data : data.items || [];

    const select = document.getElementById('btStrategy');
    if (!select) return;

    strategies.forEach((s) => {
      const option = document.createElement('option');
      option.value = s.id;
      option.textContent = s.name;
      select.appendChild(option);
    });
  } catch (error) {
    console.error('Failed to load strategies:', error);
  }
}

function populateFilters() {
  const strategies = [...new Set(allResults.map((r) => r.strategy_type))];
  const symbols = [...new Set(allResults.map((r) => r.symbol))];

  const strategySelect = document.getElementById('filterStrategy');
  strategies.forEach((s) => {
    const option = document.createElement('option');
    option.value = s;
    option.textContent = s;
    strategySelect.appendChild(option);
  });

  const symbolSelect = document.getElementById('filterSymbol');
  symbols.forEach((s) => {
    const option = document.createElement('option');
    option.value = s;
    option.textContent = s;
    symbolSelect.appendChild(option);
  });
}

// ============================
// Rendering
// ============================
function renderResultsList(results) {
  const container = document.getElementById('resultsList');
  container.innerHTML = results
    .map((r) => {
      const isProfitable = (r.metrics?.total_return || 0) >= 0;
      const isSelected = currentBacktest?.backtest_id === r.backtest_id;
      const isCompareSelected = selectedForCompare.includes(r.backtest_id);

      // Get direction from config or parameters (DCA strategies store in strategy_params._direction)
      const direction =
        r.config?.direction ||
        r.config?.strategy_params?._direction ||
        r.direction ||
        'both';
      let directionBadge = '';
      if (direction === 'long') {
        directionBadge =
          '<span class="direction-badge direction-long">L</span>';
      } else if (direction === 'short') {
        directionBadge =
          '<span class="direction-badge direction-short">S</span>';
      } else {
        directionBadge =
          '<span class="direction-badge direction-both">L&S</span>';
      }

      const isCheckedForDelete = selectedForDelete.has(r.backtest_id);

      return `
                    <div class="result-item ${isSelected ? 'selected' : ''} ${isCheckedForDelete ? 'marked-for-delete' : ''}" 
                         data-id="${r.backtest_id}">
                        ${compareMode
          ? `
                            <input type="checkbox" class="form-check-input compare-checkbox me-2" 
                                   ${isCompareSelected ? 'checked' : ''}>
                        `
          : `
                            <input type="checkbox" class="form-check-input bulk-select-checkbox"
                                   ${isCheckedForDelete ? 'checked' : ''}>
                        `
        }
                        <div class="result-content">
                            <div class="result-row">
                                <span class="result-pnl-value ${isProfitable ? 'text-success' : 'text-danger'}">
                                    ${isProfitable ? '+' : ''}${(r.metrics?.total_return || 0).toFixed(2)}%
                                </span>
                                ${directionBadge}
                                <span class="result-trades">${r.metrics?.total_trades || 0} trades</span>
                            </div>
                            <div class="result-strategy">
                                <span class="text-secondary" style="font-size:0.75rem;font-weight:600;">
                                    ${r.config?.strategy_type || r.strategy_type || '—'}
                                </span>
                            </div>
                            <div class="result-meta">
                                ${r.symbol} • ${r.interval}
                            </div>
                        </div>
                        <button class="btn btn-sm delete-btn" 
                                title="Удалить">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                `;
    })
    .join('');
}

async function selectBacktest(backtestId) {
  try {
    // Mark as selected in list
    document.querySelectorAll('.result-item').forEach((item) => {
      item.classList.toggle('selected', item.dataset.id === backtestId);
    });

    // Fetch full details
    const response = await fetch(`${API_BASE}/backtests/${backtestId}`);
    if (!response.ok) {
      setCurrentBacktest(null);
      throw new Error(`Failed to fetch backtest: ${response.status} ${response.statusText}`);
    }
    currentBacktest = await response.json();
    setCurrentBacktest(currentBacktest);

    // Update TradingView style tabs
    updateTVReportHeader(currentBacktest);
    updateTVSummaryCards(currentBacktest.metrics);
    updateTVDynamicsTab(
      currentBacktest.metrics,
      currentBacktest.config,
      currentBacktest.trades,
      currentBacktest.equity_curve
    );
    updateTVTradeAnalysisTab(
      currentBacktest.metrics,
      currentBacktest.config,
      currentBacktest.trades
    );
    updateTVRiskReturnTab(
      currentBacktest.metrics,
      currentBacktest.trades,
      currentBacktest.config
    );
    updateTVTradesListTab(currentBacktest.trades, currentBacktest.config);

    // Update charts
    updateCharts(currentBacktest);

    // P1-4: Metrics heatmap
    renderMetricsHeatmap(currentBacktest.metrics);

    // P1-5: Walk-Forward visualization (data may be absent)
    renderWalkForwardViz(currentBacktest.walk_forward || null);

    // Update legacy metrics (for backward compatibility)
    updateMetrics(currentBacktest.metrics);
    updateAIAnalysis(currentBacktest);

    // Enable AI buttons
    const btnAI = document.getElementById('btnAIAnalysis');
    if (btnAI) btnAI.disabled = false;

    // Dispatch backtestLoaded event for AI integration
    window.dispatchEvent(
      new CustomEvent('backtestLoaded', { detail: currentBacktest })
    );
    console.log(
      '[selectBacktest] Dispatched backtestLoaded event for AI Analysis'
    );
  } catch (error) {
    setCurrentBacktest(null);
    console.error('Failed to load backtest details:', error);
    showToast('Failed to load backtest details', 'error');
  }
}

function updateMetrics(metrics) {
  if (!metrics) return;

  // Helper for single value format
  const setMetric = (id, value, format = 'number', threshold = 0) => {
    const el = document.getElementById(id);
    if (!el) return;

    let formatted = '--';
    let className = 'neutral';

    if (value !== null && value !== undefined) {
      if (format === 'percent') {
        formatted = `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
      } else if (format === 'ratio') {
        formatted = value.toFixed(2);
      } else {
        formatted = value.toLocaleString();
      }

      if (typeof threshold === 'number') {
        className = value >= threshold ? 'positive' : 'negative';
      }
    }

    el.textContent = formatted;
    el.className = `metric-value ${className}`;
  };

  // Helper for TradingView-style dual format: $X.XX (Y.YY%)
  const setDualMetric = (id, dollarValue, percentValue, threshold = 0) => {
    const el = document.getElementById(id);
    if (!el) return;

    let formatted = '--';
    let className = 'neutral';

    if (
      dollarValue !== null &&
      dollarValue !== undefined &&
      percentValue !== null &&
      percentValue !== undefined
    ) {
      const dollarSign = dollarValue >= 0 ? '' : '-';
      const pctSign = percentValue >= 0 ? '' : '-';
      formatted = `${dollarSign}$${Math.abs(dollarValue).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${pctSign}${Math.abs(percentValue).toFixed(2)}%)`;

      if (typeof threshold === 'number') {
        className = dollarValue >= threshold ? 'positive' : 'negative';
      }
    }

    el.textContent = formatted;
    el.className = `metric-value ${className}`;
  };

  // Core metrics
  setMetric('metricReturn', metrics.total_return, 'percent', 0);
  setMetric('metricWinRate', metrics.win_rate, 'percent', 50);
  setMetric('metricProfitFactor', metrics.profit_factor, 'ratio', 1);
  setMetric('metricSharpe', metrics.sharpe_ratio, 'ratio', 1);
  setMetric('metricTrades', metrics.total_trades, 'number');

  // Dual format metrics (TradingView style)
  setDualMetric(
    'metricDrawdown',
    -(metrics.max_drawdown_value || 0),
    -(metrics.max_drawdown || 0),
    0
  );
  setDualMetric(
    'metricNetProfit',
    metrics.net_profit || 0,
    metrics.net_profit_pct || 0,
    0
  );
  setDualMetric(
    'metricGrossProfit',
    metrics.gross_profit || 0,
    metrics.gross_profit_pct || 0,
    0
  );
  setDualMetric(
    'metricGrossLoss',
    -(metrics.gross_loss || 0),
    -(metrics.gross_loss_pct || 0),
    0
  );
  setDualMetric(
    'metricAvgWin',
    metrics.avg_win_value || 0,
    metrics.avg_win || 0,
    0
  );
  setDualMetric(
    'metricAvgLoss',
    -(metrics.avg_loss_value || 0),
    metrics.avg_loss || 0,
    0
  );
  setDualMetric(
    'metricLargestWin',
    metrics.largest_win_value || 0,
    metrics.largest_win || 0,
    0
  );
  setDualMetric(
    'metricLargestLoss',
    -(metrics.largest_loss_value || 0),
    metrics.largest_loss || 0,
    0
  );

  // Additional TradingView metrics
  setMetric('metricAvgBars', metrics.avg_bars_in_trade, 'ratio', 0);
  setMetric('metricRecoveryFactor', metrics.recovery_factor, 'ratio', 1);
  setMetric('metricExpectancy', metrics.expectancy, 'ratio', 0);
  setMetric('metricSortino', metrics.sortino_ratio, 'ratio', 1);
  setMetric('metricCalmar', metrics.calmar_ratio, 'ratio', 1);
  setMetric('metricMaxConsecWins', metrics.max_consecutive_wins, 'number', 0);
  setMetric(
    'metricMaxConsecLosses',
    metrics.max_consecutive_losses,
    'number',
    0
  );
}

// Downsample large arrays to improve chart performance
// Uses LTTB (Largest Triangle Three Buckets) simplified algorithm
function _downsampleData(data, targetLength) {
  if (!data || data.length <= targetLength) return data;

  // Min-max bucket sampling: keeps both the minimum and maximum point
  // from each bucket (in chronological order) to preserve peaks AND valleys.
  // Output length ≈ targetLength (may be slightly larger due to 2 points/bucket).
  const buckets = Math.floor(targetLength / 2);
  const step = data.length / buckets;
  const sampled = [];

  // Always keep first point
  sampled.push(data[0]);

  for (let i = 1; i < buckets - 1; i++) {
    const start = Math.floor(i * step);
    const end = Math.min(Math.floor((i + 1) * step), data.length);

    if (start >= end) continue;

    let minIdx = start;
    let maxIdx = start;
    let minVal = data[start]?.equity ?? data[start] ?? 0;
    let maxVal = minVal;

    for (let j = start + 1; j < end; j++) {
      const val = data[j]?.equity ?? data[j] ?? 0;
      if (val < minVal) { minVal = val; minIdx = j; }
      if (val > maxVal) { maxVal = val; maxIdx = j; }
    }

    // Add both min and max in chronological order (skip duplicates)
    if (minIdx === maxIdx) {
      sampled.push(data[minIdx]);
    } else if (minIdx < maxIdx) {
      sampled.push(data[minIdx]);
      sampled.push(data[maxIdx]);
    } else {
      sampled.push(data[maxIdx]);
      sampled.push(data[minIdx]);
    }
  }

  // Always keep last point
  sampled.push(data[data.length - 1]);

  return sampled;
}

// Binary search to find closest timestamp index
function _findClosestIndex(sortedData, targetTime, getTime) {
  if (!sortedData || sortedData.length === 0) return -1;

  const target = new Date(targetTime).getTime();
  let left = 0;
  let right = sortedData.length - 1;

  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    const midTime = new Date(getTime(sortedData[mid])).getTime();
    if (midTime < target) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }

  // Check if left-1 is closer
  if (left > 0) {
    const leftTime = new Date(getTime(sortedData[left])).getTime();
    const prevTime = new Date(getTime(sortedData[left - 1])).getTime();
    if (Math.abs(prevTime - target) < Math.abs(leftTime - target)) {
      return left - 1;
    }
  }

  return left;
}

/**
 * Adaptive Y-axis recalculation for equity chart.
 * Considers only currently VISIBLE layers (strategy P&L, B&H, MFE/MAE bars).
 * Called on initial render AND on every toggle change.
 */
function _recalcEquityYAxis() {
  if (!equityChart) return;

  let yMin = Infinity;
  let yMax = -Infinity;

  const addRange = (arr) => {
    if (!arr) return;
    arr.forEach((v) => {
      if (v !== null && v !== undefined && Number.isFinite(v)) {
        yMin = Math.min(yMin, v);
        yMax = Math.max(yMax, v);
      }
    });
  };

  // Always include strategy P&L (dataset 0 — always visible)
  addRange(equityChart.data.datasets[0]?.data);

  // Include Buy & Hold only if visible
  const bhDataset = equityChart.data.datasets[1];
  if (bhDataset && !bhDataset.hidden) {
    addRange(bhDataset.data);
  }

  // Include MFE/MAE excursion bars only if visible
  const tradeRanges = equityChart._tradeRanges;
  if (equityChart._showTradeExcursions !== false && tradeRanges?.length > 0) {
    const mfeValues = tradeRanges
      .map((r) => Math.abs(r.mfe || 0))
      .filter((v) => v > 0)
      .sort((a, b) => a - b);
    const maeValues = tradeRanges
      .map((r) => Math.abs(r.mae || 0))
      .filter((v) => v > 0)
      .sort((a, b) => a - b);

    // P75 (75th percentile) — soft cap so outliers don't blow up the scale
    const getP75 = (arr) =>
      arr.length > 0
        ? arr[Math.min(Math.floor(arr.length * 0.75), arr.length - 1)]
        : 0;

    const mfeP75 = getP75(mfeValues);
    const maeP75 = getP75(maeValues);

    if (mfeP75 > 0) yMax = Math.max(yMax, mfeP75 * 1.15);
    if (maeP75 > 0) yMin = Math.min(yMin, -maeP75 * 1.15);
  }

  // Apply 5% padding for visual comfort
  if (Number.isFinite(yMin) && Number.isFinite(yMax) && yMax > yMin) {
    const padding = (yMax - yMin) * 0.05;
    equityChart.options.scales.y.min = yMin - padding;
    equityChart.options.scales.y.max = yMax + padding;
  }
}

function updateCharts(backtest) {
  console.log(
    '[updateCharts] called with backtest:',
    backtest?.id || backtest?.backtest_id
  );
  if (!backtest) return;

  // Debug: log backtest structure
  console.log('[updateCharts] backtest keys:', Object.keys(backtest));
  console.log('[updateCharts] equity_curve exists:', !!backtest.equity_curve);
  console.log('[updateCharts] trades count:', backtest.trades?.length || 0);

  // ── Equity Chart (TradingViewEquityChart) ──────────────────────────────────
  if (backtest.equity_curve && _brTVEquityChart) {
    try {
      const ec = backtest.equity_curve;
      const isArray = Array.isArray(ec);

      // Normalise equity_curve to parallel arrays
      const timestamps = isArray ? ec.map((p) => p.timestamp) : (ec.timestamps || []);
      const equityArr = isArray ? ec.map((p) => p.equity) : (ec.equity || []);
      const bhEquityArr = isArray ? [] : (ec.bh_equity || []);
      const drawdownArr = isArray ? ec.map((p) => p.drawdown || 0) : (ec.drawdown || []);

      // initial_capital: prefer config > metrics > first equity point
      const initialCapital =
        backtest.config?.initial_capital ||
        backtest.metrics?.initial_capital ||
        equityArr[0] ||
        10000;

      // Normalise trades for TradingViewEquityChart
      const trades = (backtest.trades || []).map((t) => ({
        entry_time: t.entry_time,
        exit_time: t.exit_time,
        side: t.side || 'long',
        pnl: Number(t.pnl || 0),
        mfe_pct: Number(t.mfe_pct ?? 0),
        mae_pct: Number(t.mae_pct ?? 0),
        mfe_percent: Number(t.mfe_pct ?? t.mfe ?? 0),  // Backward compat
        mfe: Number(t.mfe ?? 0),  // MFE in USD
        mae: Number(t.mae ?? 0)   // MAE in USD
      }));

      // Render via TradingViewEquityChart
      _brTVEquityChart.render({
        timestamps,
        equity: equityArr,
        bh_equity: bhEquityArr,
        trades,
        initial_capital: initialCapital
      });

      // Growth / drawdown cycles overlay + tooltip enrichment
      applyEquityGrowthDrawdownOverlay();

      console.log('[updateCharts] _brTVEquityChart.render() called,',
        timestamps.length, 'points,', trades.length, 'trades');

      // Regime overlay
      const legendRegimeOverlay = document.getElementById('legendRegimeOverlay');
      if (legendRegimeOverlay?.checked) {
        loadAndApplyRegimeOverlay(backtest);
      } else {
        clearRegimeOverlay();
      }

      // Update current value badge
      const lastEquity = equityArr[equityArr.length - 1];
      if (lastEquity != null) {
        const pnlDelta = lastEquity - initialCapital;
        const valueBadge = document.getElementById('tvEquityCurrentValue');
        if (valueBadge) {
          valueBadge.textContent = `$${lastEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          valueBadge.title = `Изменение: ${pnlDelta >= 0 ? '+' : ''}$${pnlDelta.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          valueBadge.classList.toggle('negative', lastEquity < initialCapital);
        }
      }

      // Also update Drawdown chart (separate Chart.js instance)
      if (drawdownChart && drawdownChart.canvas && drawdownArr.length > 0) {
        const shortLabels = timestamps.map((ts) => {
          if (!ts) return '';
          const d = new Date(ts);
          return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).replace('.', '');
        });
        drawdownChart.data.labels = shortLabels;
        drawdownChart.data.datasets[0].data = drawdownArr;
        drawdownChart.update('none');
      }
    } catch (chartError) {
      console.warn('[updateCharts] TradingViewEquityChart error:', chartError.message);
    }
  }

  // Returns Distribution
  if (
    backtest.trades &&
    backtest.trades.length > 0 &&
    returnsChart &&
    returnsChart.canvas
  ) {
    try {
      // Support both return_pct and pnl_pct fields
      const returns = backtest.trades.map(
        (t) => t.return_pct || t.pnl_pct || 0
      );
      const colors = returns.map((r) => (r >= 0 ? '#3fb950' : '#f85149'));

      returnsChart.data.labels = returns.map((_, i) => `Trade ${i + 1}`);
      returnsChart.data.datasets[0].data = returns;
      returnsChart.data.datasets[0].backgroundColor = colors;
      returnsChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] returnsChart error:', e.message);
    }
  }

  // Monthly P&L (simplified)
  if (
    backtest.trades &&
    backtest.trades.length > 0 &&
    monthlyChart &&
    monthlyChart.canvas
  ) {
    try {
      const monthlyPnL = {};
      backtest.trades.forEach((t) => {
        // Support both timestamp (ms) and string date formats
        let month = 'Unknown';
        if (typeof t.exit_time === 'number') {
          month = new Date(t.exit_time).toISOString().substring(0, 7);
        } else if (typeof t.exit_time === 'string') {
          month = t.exit_time.substring(0, 7);
        }
        monthlyPnL[month] = (monthlyPnL[month] || 0) + (t.pnl || 0);
      });

      const months = Object.keys(monthlyPnL).sort();
      const values = months.map((m) => monthlyPnL[m]);
      const colors = values.map((v) => (v >= 0 ? '#3fb950' : '#f85149'));

      monthlyChart.data.labels = months;
      monthlyChart.data.datasets[0].data = values;
      monthlyChart.data.datasets[0].backgroundColor = colors;
      monthlyChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] monthlyChart error:', e.message);
    }
  }

  // Trade Distribution Chart (in Trade Analysis tab)
  if (
    backtest.trades &&
    backtest.trades.length > 0 &&
    tradeDistributionChart &&
    tradeDistributionChart.canvas
  ) {
    try {
      const leverage =
        backtest.config?.leverage || backtest.parameters?.leverage || 10;
      const returns = backtest.trades.map((t) => {
        if (t.return_pct !== undefined && t.return_pct !== null)
          return t.return_pct;
        if (t.pnl_pct !== undefined && t.pnl_pct !== null) return t.pnl_pct;
        const pnl = t.pnl || 0;
        const entryValue = (t.size || 1) * (t.entry_price || 0);
        const margin = entryValue / leverage;
        return margin > 0 ? (pnl / margin) * 100 : 0;
      });

      // Dynamic bin size based on data range (aim for ~20 bins max)
      const minVal = Math.min(...returns);
      const maxVal = Math.max(...returns);
      const range = maxVal - minVal;
      let binSize = 0.5;
      if (range > 10) binSize = 1;
      if (range > 20) binSize = 2;
      if (range > 50) binSize = 5;

      const minBin = Math.floor(minVal / binSize) * binSize;
      const maxBin = Math.ceil(maxVal / binSize) * binSize;
      const bins = {};
      for (let b = minBin; b <= maxBin; b += binSize) {
        bins[b.toFixed(1)] = 0;
      }
      returns.forEach((r) => {
        const binKey = (Math.floor(r / binSize) * binSize).toFixed(1);
        if (bins[binKey] !== undefined) bins[binKey]++;
      });

      const labels = Object.keys(bins).map((k) => `${k}%`);
      const binKeys = Object.keys(bins);
      const profits = returns.filter((r) => r > 0);
      const losses = returns.filter((r) => r < 0);
      const avgProfit =
        profits.length > 0
          ? profits.reduce((a, b) => a + b, 0) / profits.length
          : 0;
      const avgLoss =
        losses.length > 0
          ? losses.reduce((a, b) => a + b, 0) / losses.length
          : 0;

      // Find bin indices for average lines
      const avgLossBinIdx =
        binKeys.findIndex((k) => parseFloat(k) >= avgLoss) - 0.5;
      const avgProfitBinIdx =
        binKeys.findIndex((k) => parseFloat(k) >= avgProfit) - 0.5;

      tradeDistributionChart.data.labels = labels;
      tradeDistributionChart.data.datasets = [
        {
          label: 'Убыток',
          data: binKeys.map((k) => (parseFloat(k) < 0 ? bins[k] : 0)),
          backgroundColor: '#ef5350',
          barPercentage: 0.5,
          categoryPercentage: 0.95
        },
        {
          label: 'Прибыль',
          data: binKeys.map((k) => (parseFloat(k) >= 0 ? bins[k] : 0)),
          backgroundColor: '#26a69a',
          barPercentage: 0.5,
          categoryPercentage: 0.95
        }
      ];

      // Add annotation lines for averages
      tradeDistributionChart.options.plugins.annotation = {
        annotations: {
          avgLossLine: {
            type: 'line',
            xMin: avgLossBinIdx,
            xMax: avgLossBinIdx,
            borderColor: '#ef5350',
            borderWidth: 2,
            borderDash: [6, 4],
            label: {
              display: true,
              content: `Ср. убыток ${avgLoss.toFixed(1)}%`,
              position: 'end',
              backgroundColor: 'rgba(239, 83, 80, 0.8)',
              color: '#ffffff',
              font: { size: 10 },
              padding: { x: 4, y: 2 }
            }
          },
          avgProfitLine: {
            type: 'line',
            xMin: avgProfitBinIdx,
            xMax: avgProfitBinIdx,
            borderColor: '#26a69a',
            borderWidth: 2,
            borderDash: [6, 4],
            label: {
              display: true,
              content: `Ср. приб. ${avgProfit.toFixed(1)}%`,
              position: 'end',
              backgroundColor: 'rgba(38, 166, 154, 0.8)',
              color: '#ffffff',
              font: { size: 10 },
              padding: { x: 4, y: 2 }
            }
          }
        }
      };

      tradeDistributionChart.options.plugins.legend.labels.color = '#ffffff';
      tradeDistributionChart.options.plugins.legend.labels.font = { size: 12 };
      tradeDistributionChart.options.plugins.legend.labels.generateLabels =
        () => [
          {
            text: 'Убыток',
            fillStyle: '#ef5350',
            strokeStyle: '#ef5350',
            pointStyle: 'circle',
            hidden: false,
            fontColor: '#ffffff'
          },
          {
            text: 'Прибыль',
            fillStyle: '#26a69a',
            strokeStyle: '#26a69a',
            pointStyle: 'circle',
            hidden: false,
            fontColor: '#ffffff'
          },
          {
            text: `Средний убыток  ${avgLoss.toFixed(2)}%`,
            fillStyle: 'transparent',
            strokeStyle: '#ef5350',
            lineWidth: 2,
            lineDash: [6, 4],
            pointStyle: 'line',
            hidden: false,
            fontColor: '#ffffff'
          },
          {
            text: `Средняя прибыль  ${avgProfit.toFixed(2)}%`,
            fillStyle: 'transparent',
            strokeStyle: '#26a69a',
            lineWidth: 2,
            lineDash: [6, 4],
            pointStyle: 'line',
            hidden: false,
            fontColor: '#ffffff'
          }
        ];
      tradeDistributionChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] tradeDistributionChart error:', e.message);
    }
  }

  // Win/Loss Donut Chart (in Trade Analysis tab)
  if (
    backtest.trades &&
    backtest.trades.length > 0 &&
    winLossDonutChart &&
    winLossDonutChart.canvas
  ) {
    try {
      let wins = 0,
        losses = 0,
        breakeven = 0;
      backtest.trades.forEach((t) => {
        const pnl = t.pnl || 0;
        if (pnl > 0) wins++;
        else if (pnl < 0) losses++;
        else breakeven++;
      });

      winLossDonutChart.data.datasets[0].data = [wins, losses, breakeven];

      // Update center label
      const total = wins + losses + breakeven;
      winLossDonutChart.options.plugins.centerLabel = {
        text: total.toString(),
        subText: 'Всего сделок'
      };

      // Update HTML legend
      const winPct = total > 0 ? ((wins / total) * 100).toFixed(2) : '0.00';
      const lossPct = total > 0 ? ((losses / total) * 100).toFixed(2) : '0.00';
      const bePct = total > 0 ? ((breakeven / total) * 100).toFixed(2) : '0.00';

      const getUnit = (n) =>
        n === 1 ? 'сделка' : n >= 2 && n <= 4 ? 'сделки' : 'сделок';

      const legendWins = document.getElementById('legend-wins');
      const legendWinsPct = document.getElementById('legend-wins-pct');
      const legendLosses = document.getElementById('legend-losses');
      const legendLossesPct = document.getElementById('legend-losses-pct');
      const legendBreakeven = document.getElementById('legend-breakeven');
      const legendBreakevenPct = document.getElementById(
        'legend-breakeven-pct'
      );

      if (legendWins) legendWins.textContent = `${wins} ${getUnit(wins)}`;
      if (legendWinsPct) legendWinsPct.textContent = `${winPct}%`;
      if (legendLosses)
        legendLosses.textContent = `${losses} ${getUnit(losses)}`;
      if (legendLossesPct) legendLossesPct.textContent = `${lossPct}%`;
      if (legendBreakeven)
        legendBreakeven.textContent = `${breakeven} ${getUnit(breakeven)}`;
      if (legendBreakevenPct) legendBreakevenPct.textContent = `${bePct}%`;

      // Hide the breakeven row entirely when there are zero breakeven trades
      const breakevenRow = document.getElementById('legend-breakeven-row');
      if (breakevenRow) breakevenRow.style.display = breakeven === 0 ? 'none' : '';

      winLossDonutChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] winLossDonutChart error:', e.message);
    }
  }

  // Waterfall Chart (in Dynamics tab)
  if (backtest.metrics && waterfallChart && waterfallChart.canvas) {
    try {
      const m = backtest.metrics;
      const grossProfit = m.gross_profit || 0;
      const grossLoss = Math.abs(m.gross_loss || 0);
      let commission = m.total_commission || 0;
      const netProfit = m.net_profit || 0;
      const openPnL = m.open_pnl || 0; // Get from metrics if available

      // If commission is 0 but we have trades, recalculate from trades
      if (commission === 0 && backtest.trades && backtest.trades.length > 0) {
        commission = backtest.trades.reduce((sum, t) => {
          return sum + Math.abs(t.fees || t.fee || t.commission || 0);
        }, 0);
        console.log(
          `[Waterfall] Recalculated commission from trades: ${commission.toFixed(2)}`
        );
      }

      // Build data dynamically - skip Open P&L if zero
      const hasOpenPnL = Math.abs(openPnL) > 0.01;

      // Build labels and data based on whether Open P&L exists
      let labels, datasets;

      if (hasOpenPnL) {
        // 5 columns with Open P&L - TradingView waterfall using FLOATING BARS
        labels = [
          'Итого прибыль',
          'Нереализованные ПР/УБ',
          'Итого убыток',
          'Комиссия',
          'Общие ПР/УБ'
        ];

        // Calculate waterfall levels
        const level0 = 0;
        const level1 = grossProfit;
        const level2 = level1 + (openPnL > 0 ? openPnL : -Math.abs(openPnL));
        const level3 = level2 - grossLoss;
        const level4 = level3 - commission;

        datasets = [
          {
            label: 'Итого прибыль',
            data: [[level0, level1], null, null, null, null],
            backgroundColor: '#26a69a',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Нереализованные ПР/УБ',
            data: [
              null,
              openPnL >= 0 ? [level1, level2] : [level2, level1],
              null,
              null,
              null
            ],
            backgroundColor: openPnL >= 0 ? '#4dd0e1' : '#ff8a65',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Итого убыток',
            data: [null, null, [level3, level2], null, null],
            backgroundColor: '#ef5350',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Комиссия',
            data: [null, null, null, [level4, level3], null],
            backgroundColor: '#ffa726',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Общие ПР/УБ',
            data: [
              null,
              null,
              null,
              null,
              netProfit >= 0 ? [level0, netProfit] : [netProfit, level0]
            ],
            backgroundColor: netProfit >= 0 ? '#42a5f5' : '#ff7043',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          }
        ];
      } else {
        // 4 columns without Open P&L - TradingView waterfall using FLOATING BARS
        // Each bar is [bottom, top] to create hanging effect
        labels = ['Итого прибыль', 'Итого убыток', 'Комиссия', 'Общие ПР/УБ'];

        // Calculate waterfall levels (like a waterfall flowing down)
        const level0 = 0; // Start
        const level1 = grossProfit; // After profit (top of green bar)
        const level2 = level1 - grossLoss; // After loss (bottom of red bar)
        const level3 = level2 - commission; // After commission

        // Each dataset has data as [bottom, top] arrays for floating bars
        datasets = [
          {
            label: 'Итого прибыль',
            data: [
              [level0, level1], // Bar 0: Profit from 0 UP to grossProfit
              null,
              null,
              null
            ],
            backgroundColor: '#26a69a',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Итого убыток',
            data: [
              null,
              [level2, level1], // Bar 1: Loss HANGS from level1 DOWN to level2
              null,
              null
            ],
            backgroundColor: '#ef5350',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Комиссия',
            data: [
              null,
              null,
              [level3, level2], // Bar 2: Commission HANGS from level2 DOWN to level3
              null
            ],
            backgroundColor: '#ffa726',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          },
          {
            label: 'Общие ПР/УБ',
            data: [
              null,
              null,
              null,
              netProfit >= 0 ? [level0, netProfit] : [netProfit, level0] // Bar 3: Net from 0
            ],
            backgroundColor: netProfit >= 0 ? '#42a5f5' : '#ff7043',
            barPercentage: 0.5,
            categoryPercentage: 0.95
          }
        ];
      }

      waterfallChart.data.labels = labels;
      waterfallChart.data.datasets = datasets;

      // Disable stacking and grouping - we use floating bars, one per category
      waterfallChart.options.scales.x.stacked = false;
      waterfallChart.options.scales.y.stacked = false;

      // CRITICAL: Disable grouping so bars don't divide width by number of datasets
      if (!waterfallChart.options.datasets)
        waterfallChart.options.datasets = {};
      if (!waterfallChart.options.datasets.bar)
        waterfallChart.options.datasets.bar = {};
      waterfallChart.options.datasets.bar.grouped = false;

      // Legend: hide Open P&L if not present (no more _base to filter)
      waterfallChart.options.plugins.legend.display = true;
      waterfallChart.options.plugins.legend.labels.filter = (item) =>
        hasOpenPnL || item.text !== 'Нереализованные ПР/УБ';

      // Add datalabels plugin for values on bars - handle floating bars [min, max]
      waterfallChart.options.plugins.datalabels = {
        display: (context) => {
          const raw = context.raw;
          // Show if it's an array with two values (floating bar)
          return Array.isArray(raw) && raw.length === 2;
        },
        anchor: 'end',
        align: 'top',
        color: '#ffffff',
        font: { size: 11, weight: 'bold' },
        formatter: (value) => {
          // Value is [min, max], display the height (difference)
          if (!Array.isArray(value)) return '';
          const height = Math.abs(value[1] - value[0]);
          if (height >= 1000) return (height / 1000).toFixed(1) + 'K';
          if (height >= 100) return height.toFixed(0);
          return height.toFixed(2);
        }
      };

      // Add dashed connector lines (adjusted for 4 or 5 columns)
      // TradingView style: lines connect bars at transition levels
      const lossIdx = hasOpenPnL ? 2 : 1; // Index of Loss column
      const commIdx = hasOpenPnL ? 3 : 2; // Index of Commission column
      const netIdx = hasOpenPnL ? 4 : 3; // Index of Net P&L column

      // Calculate correct line positions based on waterfall logic
      const profitTopLevel = grossProfit; // Top of profit bar
      const lossBottomLevel = hasOpenPnL
        ? grossProfit +
        (openPnL > 0 ? openPnL : 0) -
        (openPnL < 0 ? Math.abs(openPnL) : 0) -
        grossLoss
        : grossProfit - grossLoss; // Bottom of loss bar
      const commBottomLevel = lossBottomLevel - commission; // Bottom of commission bar

      waterfallChart.options.plugins.annotation = {
        annotations: {
          // Line from right edge of Profit to left edge of Loss (at grossProfit level)
          line1: {
            type: 'line',
            yMin: profitTopLevel,
            yMax: profitTopLevel,
            xMin: 0.45,
            xMax: lossIdx - 0.45,
            borderColor: '#8b949e',
            borderWidth: 1,
            borderDash: [5, 3]
          },
          // Line from right edge of Loss to left edge of Commission (at lossBottomLevel)
          line2: {
            type: 'line',
            yMin: lossBottomLevel,
            yMax: lossBottomLevel,
            xMin: lossIdx + 0.45,
            xMax: commIdx - 0.45,
            borderColor: '#8b949e',
            borderWidth: 1,
            borderDash: [5, 3]
          },
          // Line from right edge of Commission to left edge of Net P&L (at commBottomLevel)
          line3: {
            type: 'line',
            yMin: commBottomLevel,
            yMax: commBottomLevel,
            xMin: commIdx + 0.45,
            xMax: netIdx - 0.45,
            borderColor: '#8b949e',
            borderWidth: 1,
            borderDash: [5, 3]
          }
        }
      };

      waterfallChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] waterfallChart error:', e.message);
    }
  }

  // Benchmarking Chart (in Dynamics tab)
  if (backtest.metrics && benchmarkingChart && benchmarkingChart.canvas) {
    try {
      const m = backtest.metrics;
      const initialCapital = backtest.config?.initial_capital || 10000;

      // Strategy return — always in % (from backend net_profit_pct / total_return)
      const strategyReturnPct =
        m.net_profit_pct ||
        m.total_return ||
        ((m.net_profit || 0) / initialCapital) * 100;

      // Buy & Hold return — convert USD → % if backend sends absolute value
      // buy_hold_return_pct takes priority; fall back to USD / initialCapital * 100
      const bhReturnPct =
        m.buy_hold_return_pct != null && m.buy_hold_return_pct !== 0
          ? m.buy_hold_return_pct
          : ((m.buy_hold_return || 0) / initialCapital) * 100;

      // Strategy range from equity curve (in %)
      let stratMinPct = strategyReturnPct < 0
        ? strategyReturnPct * 1.3
        : strategyReturnPct * 0.7;
      let stratMaxPct = strategyReturnPct < 0
        ? strategyReturnPct * 0.7
        : strategyReturnPct * 1.3;

      // BH range defaults (±30% of BH value)
      let bhRangeLow = Math.min(bhReturnPct * (bhReturnPct < 0 ? 1.3 : 0.7), bhReturnPct);
      let bhRangeHigh = Math.max(bhReturnPct * (bhReturnPct < 0 ? 0.7 : 1.3), bhReturnPct);

      // equity_curve from backend is a dict: { equity: [...], bh_equity: [...], timestamps: [...] }
      // (NOT an array) — extract arrays accordingly
      const ec = backtest.equity_curve;

      // bhCurrentPct: prefer last bh_equity value (matches actual BH at end date)
      // falls back to metrics.buy_hold_return_pct
      let bhCurrentPct = bhReturnPct;

      if (ec) {
        // Strategy equity array
        const stratArr = Array.isArray(ec)
          ? ec.map((e) => (typeof e === 'object' ? e.equity || e.value || 0 : Number(e)))
          : Array.isArray(ec.equity) ? ec.equity : [];
        if (stratArr.length > 0) {
          const minE = Math.min(...stratArr);
          const maxE = Math.max(...stratArr);
          stratMinPct = ((minE - initialCapital) / initialCapital) * 100;
          stratMaxPct = ((maxE - initialCapital) / initialCapital) * 100;
        }
        // BH equity array — gives actual min/max range + current value for Buy & Hold bar
        const bhArr = Array.isArray(ec)
          ? []
          : Array.isArray(ec.bh_equity) ? ec.bh_equity : [];
        if (bhArr.length > 0) {
          const bhMinE = Math.min(...bhArr);
          const bhMaxE = Math.max(...bhArr);
          bhRangeLow = ((bhMinE - initialCapital) / initialCapital) * 100;
          bhRangeHigh = ((bhMaxE - initialCapital) / initialCapital) * 100;
          bhCurrentPct = ((bhArr[bhArr.length - 1] - initialCapital) / initialCapital) * 100;
        }
      }
      // Ensure current value is always within [min, max]
      const stratRangeLow = Math.min(stratMinPct, strategyReturnPct);
      const stratRangeHigh = Math.max(stratMaxPct, strategyReturnPct);
      // Ensure BH current value is within its range
      bhRangeLow = Math.min(bhRangeLow, bhCurrentPct);
      bhRangeHigh = Math.max(bhRangeHigh, bhCurrentPct);

      benchmarkingChart.data.datasets = [
        // ── Row 0: Buy & Hold ──────────────────────────────────────────────
        {
          // BH range rectangle — wide, transparent orange fill
          label: 'Прибыль при покупке и удержании',
          data: [
            [bhRangeLow, bhRangeHigh],  // row 0 = BH
            null                         // row 1 = Strategy (empty)
          ],
          backgroundColor: 'rgba(230, 153, 2, 0.55)',
          borderColor: 'rgba(0,0,0,0)',
          borderWidth: 0,
          barPercentage: 0.65,
          categoryPercentage: 1.0,
          grouped: false
        },
        {
          // BH current-value marker — thin darker bar at bhCurrentPct
          label: '_bh_cur',
          data: [
            [bhCurrentPct - 0.25, bhCurrentPct + 0.25],
            null
          ],
          backgroundColor: 'rgba(160, 100, 0, 0.95)',
          borderColor: 'rgba(0,0,0,0)',
          borderWidth: 0,
          barPercentage: 0.65,
          categoryPercentage: 1.0,
          grouped: false
        },
        // ── Row 1: Strategy ───────────────────────────────────────────────
        {
          // Strategy range rectangle — wide, transparent blue fill
          label: 'Прибыльность стратегии',
          data: [
            null,                                   // row 0 = BH (empty)
            [stratRangeLow, stratRangeHigh]         // row 1 = Strategy
          ],
          backgroundColor: 'rgba(66, 165, 245, 0.55)',
          borderColor: 'rgba(0,0,0,0)',
          borderWidth: 0,
          barPercentage: 0.65,
          categoryPercentage: 1.0,
          grouped: false
        },
        {
          // Strategy current-value marker — thin darker bar at strategyReturnPct
          label: '_strat_cur',
          data: [
            null,
            [strategyReturnPct - 0.25, strategyReturnPct + 0.25]
          ],
          backgroundColor: 'rgba(30, 120, 180, 0.95)',
          borderColor: 'rgba(0,0,0,0)',
          borderWidth: 0,
          barPercentage: 0.65,
          categoryPercentage: 1.0,
          grouped: false
        }
      ];

      // Store tooltip info (Макс / Текущ. цена / Мин) on chart instance
      benchmarkingChart._tvBenchInfo = [
        { max: bhRangeHigh,    cur: bhCurrentPct,       min: bhRangeLow    }, // row 0 = BH
        { max: stratRangeHigh, cur: strategyReturnPct,  min: stratRangeLow } // row 1 = Strategy
      ];

      // Disable grouping so both BH datasets stack on row 0 at full width
      benchmarkingChart.options.datasets = benchmarkingChart.options.datasets || {};
      benchmarkingChart.options.datasets.bar = { grouped: false };

      // Hide current-value markers from legend
      benchmarkingChart.options.plugins.legend.labels.filter =
        (item) => !item.text.startsWith('_');

      benchmarkingChart.update('none');
    } catch (e) {
      console.warn('[updateCharts] benchmarkingChart error:', e.message);
    }
  }

  // Price Chart (LightweightCharts candlestick with trade markers)
  // Always mark as pending so a tab switch will trigger a refresh.
  // If the tab is already active, also kick off an immediate render.
  btPriceChartPending = true;
  setPriceChartPending(true);
  const priceTab = document.getElementById('tab-price-chart');
  const priceTabActive = priceTab && priceTab.classList.contains('active');
  console.log('[updateCharts] Price chart: pending=true, tabActive=', priceTabActive,
    'symbol=', backtest.config?.symbol, 'interval=', backtest.config?.interval);
  if (priceTabActive) {
    updatePriceChart(backtest);
  }
}

// eslint-disable-next-line no-unused-vars
function updateTradesTable(trades) {
  if (!trades) {
    tradesTable.setData([]);
    return;
  }

  const formattedTrades = trades.map((t, i) => ({
    id: i + 1,
    entry_time: formatDateTime(t.entry_time),
    exit_time: formatDateTime(t.exit_time),
    side: t.side || 'long',
    entry_price: t.entry_price,
    exit_price: t.exit_price,
    size: t.size,
    pnl: t.pnl,
    return_pct: t.return_pct
  }));

  tradesTable.setData(formattedTrades);
}

function updateAIAnalysis(backtest) {
  const content = document.getElementById('aiAnalysisContent');

  if (!backtest || !backtest.metrics) {
    content.textContent =
      'Select a backtest result to get AI-powered analysis and recommendations.';
    return;
  }

  const m = backtest.metrics;
  const insights = [];

  // Generate quick insights
  if (m.total_return > 20) {
    insights.push('✅ Excellent returns! Strategy shows strong profitability.');
  } else if (m.total_return > 0) {
    insights.push(
      '🔶 Positive returns, but there may be room for optimization.'
    );
  } else {
    insights.push(
      '⚠️ Negative returns. Consider adjusting strategy parameters.'
    );
  }

  if (m.win_rate >= 60) {
    insights.push('✅ High win rate indicates consistent signal quality.');
  } else if (m.win_rate < 40) {
    insights.push('⚠️ Low win rate. Review entry/exit conditions.');
  }

  if (m.profit_factor >= 2) {
    insights.push('✅ Strong profit factor (> 2x) shows good risk/reward.');
  } else if (m.profit_factor < 1) {
    insights.push('🔴 Profit factor below 1 means losses exceed gains.');
  }

  if (m.max_drawdown < -30) {
    insights.push('⚠️ High drawdown risk. Consider tighter stop losses.');
  }

  if (m.sharpe_ratio >= 2) {
    insights.push('✅ Excellent risk-adjusted returns (Sharpe > 2).');
  } else if (m.sharpe_ratio < 1) {
    insights.push(
      '🔶 Consider reducing volatility for better risk-adjusted returns.'
    );
  }

  content.innerHTML = insights.join('<br>');
}

// ============================
// Actions
// ============================
function toggleFilters() {
  document.getElementById('filtersPanel').classList.toggle('d-none');
}

function toggleResultsPanel() {
  const panel = document.getElementById('resultsPanel');

  panel.classList.toggle('collapsed');

  // Save state to localStorage
  const isCollapsed = panel.classList.contains('collapsed');
  localStorage.setItem('resultsPanelCollapsed', isCollapsed);

  // Force TV chart to resize after CSS transition (300ms) completes
  const doResize = () => {
    window.dispatchEvent(new Event('resize'));
    // Directly resize the TV chart using the module-level reference
    if (_brTVEquityChart && _brTVEquityChart._lwChart) {
      const c = _brTVEquityChart.container;
      if (c && c.clientWidth > 0) {
        _brTVEquityChart._lwChart.resize(
          c.clientWidth,
          c.clientHeight || 400
        );
      }
    }
  };
  setTimeout(doResize, 320);   // after transition ends
  setTimeout(doResize, 650);   // safety second pass
}
// Make available globally for onclick
window.toggleResultsPanel = toggleResultsPanel;

// Restore panel state on page load
document.addEventListener('DOMContentLoaded', function () {
  // Wire toggle button via addEventListener (avoids CSP unsafe-eval block)
  const btn = document.getElementById('panelToggleBtn');
  if (btn) {
    btn.addEventListener('click', toggleResultsPanel);
  }

  const savedState = localStorage.getItem('resultsPanelCollapsed');
  if (savedState === 'true') {
    const panel = document.getElementById('resultsPanel');
    if (panel) {
      panel.classList.add('collapsed');
    }
  }
});

function applyFilters() {
  const strategy = document.getElementById('filterStrategy').value;
  const symbol = document.getElementById('filterSymbol').value;
  const pnl = document.getElementById('filterPnL').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();

  const filtered = allResults.filter((r) => {
    if (strategy && r.strategy_type !== strategy) return false;
    if (symbol && r.symbol !== symbol) return false;
    if (pnl === 'profit' && (r.metrics?.total_return || 0) < 0) return false;
    if (pnl === 'loss' && (r.metrics?.total_return || 0) >= 0) return false;
    if (search && !JSON.stringify(r).toLowerCase().includes(search))
      return false;
    return true;
  });

  renderResultsList(filtered);
}

function toggleCompareMode() {
  compareMode = !compareMode;
  setCompareMode(compareMode);
  selectedForCompare = [];
  setSelectedForCompare(selectedForCompare);

  const btn = document.getElementById('btnCompare');
  btn.classList.toggle('btn-primary', compareMode);
  btn.classList.toggle('btn-outline-secondary', !compareMode);
  btn.innerHTML = compareMode
    ? '<i class="bi bi-x-lg me-1"></i>Cancel Compare'
    : '<i class="bi bi-columns-gap me-1"></i>Compare Selected';

  renderResultsList(allResults);
}

function toggleCompareSelect(event, backtestId) {
  event.stopPropagation();

  if (selectedForCompare.includes(backtestId)) {
    selectedForCompare = selectedForCompare.filter((id) => id !== backtestId);
  } else if (selectedForCompare.length < 3) {
    selectedForCompare.push(backtestId);
  }
  setSelectedForCompare(selectedForCompare);

  const enoughSelected = selectedForCompare.length >= 2;
  const tooltipText = enoughSelected
    ? `Сравнить ${selectedForCompare.length} выбранных бэктеста`
    : `Выберите 2–3 бэктеста для сравнения (выбрано: ${selectedForCompare.length})`;

  const compareBtn = document.getElementById('btnCompare');
  compareBtn.disabled = !enoughSelected;
  compareBtn.title = tooltipText;

  const aiCompareBtn = document.getElementById('btnAICompare');
  aiCompareBtn.disabled = !enoughSelected;
  aiCompareBtn.title = tooltipText;
}

function showNewBacktestModal() {
  new bootstrap.Modal(document.getElementById('newBacktestModal')).show();
}

/**
 * Toggle MTF settings panel visibility
 */
function toggleMtfSettings() {
  const checkbox = document.getElementById('btMtfEnabled');
  const panel = document.getElementById('mtfSettingsPanel');
  if (panel) {
    panel.classList.toggle('d-none', !checkbox?.checked);
  }
}

/**
 * Toggle ML Optimizer settings panel visibility
 */
function toggleOptimizeSettings() {
  const checkbox = document.getElementById('btOptimizeEnabled');
  const panel = document.getElementById('optimizeSettingsPanel');
  if (panel) {
    panel.classList.toggle('d-none', !checkbox?.checked);
  }
}

async function runBacktest() {
  const strategyId = document.getElementById('btStrategy').value;
  const symbol = document.getElementById('btSymbol').value;
  const interval = document.getElementById('btInterval').value;
  const capital = document.getElementById('btCapital').value;
  const startDate = document.getElementById('btStartDate').value;
  const endDate = document.getElementById('btEndDate').value;

  // MTF check — from-strategy endpoint does not support MTF filtering
  const mtfEnabled = document.getElementById('btMtfEnabled')?.checked || false;

  if (!strategyId) {
    showToast('Please select a strategy', 'error');
    return;
  }

  // MTF not supported via from-strategy endpoint — warn user
  if (mtfEnabled) {
    showToast(
      'MTF filtering is not supported when running from strategy. Use the MTF backtest page instead.',
      'warning'
    );
  }

  try {
    showToast('Running backtest...', 'info');

    // Build request body (only fields accepted by RunFromStrategyRequest)
    const requestBody = {
      symbol,
      interval,
      initial_capital: parseFloat(capital),
      start_date: new Date(startDate).toISOString(),
      end_date: new Date(endDate).toISOString(),
      save_result: true
    };

    const response = await fetch(
      `${API_BASE}/backtests/from-strategy/${strategyId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      }
    );

    if (!response.ok) throw new Error('Backtest failed');

    await response.json(); // Consume response
    bootstrap.Modal.getInstance(
      document.getElementById('newBacktestModal')
    ).hide();

    showToast('Backtest completed successfully!', 'success');
    loadBacktestResults();
  } catch (error) {
    console.error('Backtest error:', error);
    showToast('Backtest failed: ' + error.message, 'error');
  }
}

async function requestAIAnalysis() {
  if (!currentBacktest) return;

  const btn = document.querySelector('[onclick="requestAIAnalysis()"]');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Анализируем...';
  }

  try {
    showToast('Generating AI analysis (3 agents)...', 'info');

    const response = await fetch(`${API_BASE}/agents/backtest/ai-analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([currentBacktest])
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const analysis = await response.json();

    // Build rich HTML from AI analysis
    const summary = analysis.summary || analysis.recommendation || analysis.analysis || 'No summary available';
    const risk = analysis.risk_assessment || '';
    const strengths = analysis.strengths || [];
    const weaknesses = analysis.weaknesses || [];
    const recs = analysis.recommendations || [];
    const grade = analysis.grade || '';
    const confidence = analysis.confidence ? (analysis.confidence * 100).toFixed(0) : '';
    const overfitRisk = analysis.overfitting_risk || '';
    const regime = analysis.market_regime || '';
    const agents = analysis.agents_used || [];

    const overfitClass = { low: 'success', medium: 'warning', high: 'danger' }[overfitRisk] || 'secondary';

    let html = '<div class="ai-result-card">';

    // Grade & confidence badge row
    if (grade || confidence) {
      html += '<div class="d-flex gap-2 mb-2 flex-wrap">';
      if (grade) html += `<span class="badge bg-primary fs-6">Оценка: ${escapeHtml(grade)}</span>`;
      if (confidence) html += `<span class="badge bg-info fs-6">Уверенность: ${escapeHtml(confidence)}%</span>`;
      if (overfitRisk) html += `<span class="badge bg-${overfitClass} fs-6">Переобучение: ${escapeHtml(overfitRisk)}</span>`;
      if (regime) html += `<span class="badge bg-secondary fs-6">Режим: ${escapeHtml(regime)}</span>`;
      html += '</div>';
    }

    // Summary
    html += `<div class="mb-2"><strong>📊 Резюме:</strong><br>${escapeHtml(summary)}</div>`;

    // Risk assessment
    if (risk) {
      html += `<div class="mb-2"><strong>⚠️ Оценка рисков:</strong><br>${escapeHtml(risk)}</div>`;
    }

    // Strengths
    if (strengths.length > 0) {
      html += '<div class="mb-2"><strong>✅ Сильные стороны:</strong><ul>';
      strengths.forEach(s => { html += `<li>${escapeHtml(s)}</li>`; });
      html += '</ul></div>';
    }

    // Weaknesses
    if (weaknesses.length > 0) {
      html += '<div class="mb-2"><strong>❌ Слабые стороны:</strong><ul>';
      weaknesses.forEach(w => { html += `<li>${escapeHtml(w)}</li>`; });
      html += '</ul></div>';
    }

    // Recommendations
    if (recs.length > 0) {
      html += '<div class="mb-2"><strong>💡 Рекомендации:</strong><ol>';
      recs.forEach(r => { html += `<li>${escapeHtml(r)}</li>`; });
      html += '</ol></div>';
    }

    // Agents footer
    if (agents.length > 0) {
      html += `<div class="text-muted small mt-2">🤖 Агенты: ${escapeHtml(agents.join(', '))}</div>`;
    }

    html += '</div>';

    document.getElementById('aiAnalysisContent').innerHTML = html;

    showToast('AI analysis complete', 'success');
  } catch (error) {
    console.error('AI analysis failed:', error);
    showToast('AI analysis failed: ' + error.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-robot"></i> Сгенерировать анализ';
    }
  }
}

async function compareWithAI() {
  if (selectedForCompare.length < 2) {
    showToast('Select at least 2 backtests to compare', 'warning');
    return;
  }

  try {
    showToast('Comparing strategies with AI...', 'info');

    const results = await Promise.all(
      selectedForCompare.map((id) =>
        fetch(`${API_BASE}/backtests/${id}`).then((r) => r.json())
      )
    );

    const response = await fetch(`${API_BASE}/agents/backtest/ai-analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(results)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const analysis = await response.json();

    document.getElementById('aiAnalysisContent').innerHTML = `
                    <strong>Comparison Result:</strong><br>
                    ${escapeHtml(analysis.recommendation || analysis.comparison || 'Comparison complete.')}
                `;

    showToast('AI comparison complete', 'success');
  } catch (error) {
    console.error('AI comparison failed:', error);
    showToast('AI comparison failed', 'error');
  }
}

function exportResults() {
  if (allResults.length === 0) {
    showToast('No results to export', 'warning');
    return;
  }

  const csv = [
    [
      'ID',
      'Strategy',
      'Symbol',
      'Interval',
      'Return %',
      'Win Rate',
      'Sharpe',
      'Trades',
      'Date'
    ].join(','),
    ...allResults.map((r) =>
      [
        r.backtest_id,
        r.strategy_type,
        r.symbol,
        r.interval,
        r.metrics?.total_return?.toFixed(2) || 0,
        r.metrics?.win_rate?.toFixed(2) || 0,
        r.metrics?.sharpe_ratio?.toFixed(2) || 0,
        r.metrics?.total_trades || 0,
        r.config?.start_date || ''
      ].join(',')
    )
  ].join('\n');

  downloadFile(csv, 'backtest_results.csv', 'text/csv');
}

function exportTrades() {
  if (!currentBacktest?.trades) {
    showToast('No trades to export', 'warning');
    return;
  }

  const csv = [
    [
      '#',
      'Entry Time',
      'Exit Time',
      'Side',
      'Entry Price',
      'Exit Price',
      'Size',
      'P&L',
      'Return %'
    ].join(','),
    ...currentBacktest.trades.map((t, i) =>
      [
        i + 1,
        t.entry_time,
        t.exit_time,
        t.side,
        t.entry_price,
        t.exit_price,
        t.size,
        t.pnl?.toFixed(2),
        t.return_pct?.toFixed(2)
      ].join(',')
    )
  ].join('\n');

  downloadFile(csv, `trades_${currentBacktest.backtest_id}.csv`, 'text/csv');
}

function refreshData() {
  loadBacktestResults();
  showToast('Data refreshed', 'success');
}

// ============================
// Utilities
// ============================
// formatDate - using imported version from utils.js

function formatDateTime(dateStr) {
  if (!dateStr) return '--';
  // Ensure UTC interpretation: append Z if no timezone info present
  const normalized = (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+') && dateStr.includes('T'))
    ? dateStr + 'Z'
    : dateStr;
  const date = new Date(normalized);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function showToast(message, type = 'info') {
  // Simple toast implementation
  const toast = document.createElement('div');
  toast.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} position-fixed`;
  toast.style.cssText =
    'top: 80px; right: 20px; z-index: 9999; min-width: 250px;';
  toast.innerHTML = `
                <i class="bi bi-${type === 'error' ? 'x-circle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
                ${message}
            `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ============================================
// PRICE CHART — LightweightCharts Candlestick
// ============================================

/**
 * Fire-and-forget: trigger background kline sync for a symbol.
 * Ensures all timeframes are downloaded from Bybit API into the DB
 * so the chart has candles available for the full backtest range.
 * Uses the existing POST /symbols/sync-all-tf endpoint.
 */
const _syncTriggeredSymbols = new Set();
function triggerBackgroundKlineSync(symbol) {
  // Only trigger once per symbol per page session
  if (_syncTriggeredSymbols.has(symbol)) return;
  _syncTriggeredSymbols.add(symbol);

  const syncUrl = `${API_BASE}/marketdata/symbols/sync-all-tf?symbol=${encodeURIComponent(symbol)}`;
  fetch(syncUrl, { method: 'POST' })
    .then(res => {
      if (res.ok) {
        console.log(`[KlineSync] Background sync started for ${symbol}`);
      } else {
        console.warn(`[KlineSync] Sync request failed for ${symbol}: ${res.status}`);
      }
    })
    .catch(err => {
      console.warn(`[KlineSync] Sync request error for ${symbol}:`, err.message);
    });
}

// ============================
// Equity → Price Chart Navigation
// ============================

/**
 * Handle click on equity chart: extract timestamp from clicked data point
 * and navigate the price chart to that candle.
 */
function _handleEquityChartClick(_event, elements, chart) {
  if (!elements || elements.length === 0) return;

  const idx = elements[0].index;
  const equityData = chart._equityData;
  if (!equityData || !equityData[idx]) return;

  // Get timestamp from equity data point
  const timestamp = equityData[idx].timestamp;
  if (!timestamp) return;

  // Check if this point corresponds to a trade exit (for richer context)
  const tradeInfo = chart._tradeMap?.[idx];

  const timeSec = Math.floor(new Date(timestamp).getTime() / 1000);
  console.log('[EquityClick] Navigating to price chart at', timestamp,
    tradeInfo ? `(Trade #${tradeInfo.tradeNum})` : '');

  navigatePriceChartToTime(timeSec, tradeInfo);
}

/**
 * Switch to the Price Chart tab and scroll/zoom to a specific candle timestamp.
 * Optionally highlights the trade if tradeInfo is provided.
 * @param {number} targetTimeSec - Unix timestamp in seconds to navigate to
 * @param {object|null} tradeInfo - Trade info from _tradeMap (optional)
 */
function navigatePriceChartToTime(targetTimeSec, tradeInfo = null) {
  if (!currentBacktest) return;

  // 1. Switch to price-chart tab
  const tabs = document.querySelectorAll('.tv-report-tab');
  const contents = document.querySelectorAll('.tv-report-tab-content');

  tabs.forEach((t) => t.classList.remove('active'));
  contents.forEach((c) => c.classList.remove('active'));

  const priceTab = document.querySelector('.tv-report-tab[data-tab="price-chart"]');
  const priceContent = document.getElementById('tab-price-chart');
  if (priceTab) priceTab.classList.add('active');
  if (priceContent) priceContent.classList.add('active');

  // 2. If price chart already exists, scroll to time directly
  if (btPriceChart && btCandleSeries) {
    scrollPriceChartToCandle(targetTimeSec, tradeInfo);
    return;
  }

  // 3. Price chart not yet created — build it, then scroll after render
  btPriceChartPending = false;
  setPriceChartPending(false);
  const originalUpdatePriceChart = updatePriceChart;

  // Wrap updatePriceChart to scroll after it completes
  const scrollAfterRender = async () => {
    await originalUpdatePriceChart(currentBacktest);
    // Small delay to let LightweightCharts finish layout
    requestAnimationFrame(() => {
      scrollPriceChartToCandle(targetTimeSec, tradeInfo);
    });
  };

  scrollAfterRender();
}

/**
 * Scroll and zoom the LightweightCharts price chart to center on a target candle.
 * Adds a temporary highlight marker at the target candle.
 * @param {number} targetTimeSec - Target candle time (Unix seconds)
 * @param {object|null} tradeInfo - Optional trade info for label
 */
function scrollPriceChartToCandle(targetTimeSec, tradeInfo = null) {
  if (!btPriceChart || !btCandleSeries) return;

  const timeScale = btPriceChart.timeScale();

  // Calculate a visible range of ~60 bars centered on the target
  // Use the backtest interval to compute bar width in seconds
  const interval = currentBacktest?.config?.interval || '60';
  const barWidthSec = getIntervalSeconds(interval);
  const barsVisible = 60; // Show ~60 bars around the target
  const halfRange = Math.floor(barsVisible / 2) * barWidthSec;

  const from = targetTimeSec - halfRange;
  const to = targetTimeSec + halfRange;

  timeScale.setVisibleRange({ from, to });

  // Add a temporary highlight marker on the target candle
  addNavigationHighlight(targetTimeSec, tradeInfo);

  console.log('[PriceChartNav] Scrolled to', new Date(targetTimeSec * 1000).toISOString(),
    'range:', new Date(from * 1000).toISOString(), '-', new Date(to * 1000).toISOString());
}

/**
 * Add a temporary visual highlight marker on the price chart at the target candle.
 * The marker auto-removes after 5 seconds.
 * @param {number} targetTimeSec - Candle time to highlight
 * @param {object|null} tradeInfo - Optional trade info for marker label
 */
function addNavigationHighlight(targetTimeSec, tradeInfo = null) {
  if (!btCandleSeries) return;

  // Build the highlight marker
  const sideVal = tradeInfo ? (tradeInfo.side || 'long').toLowerCase() : '';
  const label = tradeInfo
    ? `► Trade #${tradeInfo.tradeNum} (${(sideVal === 'short' || sideVal === 'sell') ? 'Short' : 'Long'})`
    : '► Navigate here';

  const highlightMarker = {
    time: targetTimeSec,
    position: 'aboveBar',
    color: '#58a6ff',
    shape: 'arrowDown',
    text: label
  };

  // Merge with existing trade markers, adding highlight
  const markersWithHighlight = [
    ...btPriceChartMarkers,
    highlightMarker
  ].sort((a, b) => a.time - b.time);

  btCandleSeries.setMarkers(markersWithHighlight);

  // Auto-remove highlight after 5 seconds, restore original markers
  setTimeout(() => {
    if (btCandleSeries) {
      btCandleSeries.setMarkers(btPriceChartMarkers);
    }
  }, 5000);
}

/**
 * Convert interval string to seconds (e.g., '15' → 900, '60' → 3600, 'D' → 86400).
 * @param {string} interval - Bybit interval code
 * @returns {number} Interval duration in seconds
 */
function getIntervalSeconds(interval) {
  const map = {
    '1': 60, '5': 300, '15': 900, '30': 1800,
    '60': 3600, '240': 14400,
    'D': 86400, 'W': 604800, 'M': 2592000
  };
  return map[interval] || 3600;
}

/**
 * Initialize or update the candlestick price chart for the selected backtest.
 * Fetches kline data from the DB via /klines/range endpoint, renders candles,
 * and overlays trade entry/exit markers like TradingView.
 */
async function updatePriceChart(backtest) {
  if (!backtest || !backtest.config) return;

  // Race-condition guard: bump generation so any in-flight render aborts
  const myGen = ++_priceChartGeneration;

  const container = document.getElementById('btCandlestickChart');
  const loadingEl = document.getElementById('btPriceChartLoading');
  const titleEl = document.getElementById('priceChartTitle');

  if (!container) return;

  // Show loading
  if (loadingEl) loadingEl.classList.remove('hidden');

  const symbol = backtest.config.symbol || 'BTCUSDT';
  const interval = backtest.config.interval || '60';

  // Update title — use DOM manipulation to avoid XSS (symbol comes from server data)
  if (titleEl) {
    const icon = document.createElement('i');
    icon.className = 'bi bi-graph-up-arrow me-1';
    titleEl.textContent = '';
    titleEl.appendChild(icon);
    titleEl.appendChild(document.createTextNode(`${symbol} — ${formatInterval(interval)}`));
  }

  try {
    // Determine time range from backtest config
    let startMs = null;
    let endMs = null;

    if (backtest.config.start_date) {
      // new Date("YYYY-MM-DD") parses as UTC midnight (00:00:00 UTC).
      // That is correct for startMs — we want candles FROM the start of that day.
      startMs = new Date(backtest.config.start_date).getTime();
    }
    if (backtest.config.end_date) {
      // new Date("YYYY-MM-DD") = UTC 00:00:00 of that day — this EXCLUDES all candles
      // on end_date itself! Add 86399999ms (23:59:59.999) to include the full last day.
      endMs = new Date(backtest.config.end_date).getTime() + 86399999;
    }

    if (!startMs || !endMs) {
      console.warn('[PriceChart] No start_date / end_date in backtest config');
      if (loadingEl) loadingEl.classList.add('hidden');
      return;
    }

    // Fire-and-forget: trigger background kline sync for this symbol
    // so that future chart loads will have candles ready in DB
    triggerBackgroundKlineSync(symbol);

    // Fetch ALL candles from DB for the exact backtest date range (no limit)
    const url = `${API_BASE}/marketdata/bybit/klines/range?symbol=${symbol}&interval=${interval}&start=${startMs}&end=${endMs}`;
    const response = await fetch(url);

    // Abort if a newer render was triggered while we were fetching
    if (myGen !== _priceChartGeneration) {
      console.log('[PriceChart] Stale render aborted (gen', myGen, 'vs', _priceChartGeneration, ')');
      return;
    }

    if (!response.ok) {
      console.warn('[PriceChart] API error:', response.status);
      if (loadingEl) loadingEl.classList.add('hidden');
      return;
    }

    const data = await response.json();

    // Abort if a newer render was triggered while we were parsing
    if (myGen !== _priceChartGeneration) {
      console.log('[PriceChart] Stale render aborted after parse (gen', myGen, 'vs', _priceChartGeneration, ')');
      return;
    }

    if (!data || !Array.isArray(data) || data.length === 0) {
      console.warn('[PriceChart] No kline data in DB for this range. Background sync may still be in progress — try again shortly.');
      if (loadingEl) loadingEl.classList.add('hidden');
      return;
    }

    // Data is already sorted asc and filtered to date range by the API
    const candles = data.map(k => ({
      time: Math.floor(k.open_time / 1000),
      open: parseFloat(k.open),
      high: parseFloat(k.high),
      low: parseFloat(k.low),
      close: parseFloat(k.close)
    }));

    // Destroy existing chart and clean up observers
    if (_priceChartResizeObserver) {
      _priceChartResizeObserver.disconnect();
      _priceChartResizeObserver = null;
    }
    if (btPriceChart) {
      btPriceChart.remove();
      btPriceChart = null;
      btCandleSeries = null;
    }

    // Create candlestick chart
    btPriceChart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 480,
      layout: {
        background: { type: 'solid', color: '#0d1117' },
        textColor: '#8b949e'
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: '#58a6ff', width: 1, style: LightweightCharts.LineStyle.Dashed },
        horzLine: { color: '#58a6ff', width: 1, style: LightweightCharts.LineStyle.Dashed }
      },
      rightPriceScale: {
        borderColor: '#30363d',
        width: 80
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5
      },
      localization: {
        timeFormatter: (unixSeconds) => {
          // Convert UTC unix seconds → local browser time string
          const d = new Date(unixSeconds * 1000);
          const pad = (n) => String(n).padStart(2, '0');
          return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
        },
        dateFormatter: (unixSeconds) => {
          const d = new Date(unixSeconds * 1000);
          const pad = (n) => String(n).padStart(2, '0');
          return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        }
      }
    });

    btCandleSeries = btPriceChart.addCandlestickSeries({
      upColor: '#00c853',
      downColor: '#ff1744',
      borderDownColor: '#ff1744',
      borderUpColor: '#00c853',
      wickDownColor: '#ff1744',
      wickUpColor: '#00c853'
    });

    btCandleSeries.setData(candles);
    _btCachedCandles = candles; // cache for marker rebuild on checkbox toggle
    // Sync to StateManager
    setPriceChart(btPriceChart);
    setPriceChartCandleSeries(btCandleSeries);
    setPriceChartCachedCandles(candles);

    // Add crosshair OHLC display
    btPriceChart.subscribeCrosshairMove((param) => {
      const ohlcEl = document.getElementById('btChartOHLC');
      if (!ohlcEl) return;
      if (!param || !param.time || !param.seriesData) {
        ohlcEl.textContent = 'O: -- H: -- L: -- C: --';
        return;
      }
      const candleData = param.seriesData.get(btCandleSeries);
      if (candleData) {
        const fmt = (v) => (v != null ? Number(v).toFixed(2) : '--');
        ohlcEl.textContent = `O: ${fmt(candleData.open)}  H: ${fmt(candleData.high)}  L: ${fmt(candleData.low)}  C: ${fmt(candleData.close)}`;
      } else {
        // Crosshair is between candles or outside data range — reset to placeholder
        ohlcEl.textContent = 'O: -- H: -- L: -- C: --';
      }
    });

    // Add trade markers
    btPriceChartMarkers = [];
    btTradeLineSeries = [];
    if (backtest.trades && backtest.trades.length > 0) {
      btPriceChartMarkers = buildTradeMarkers(backtest.trades, candles);
      if (btPriceChartMarkers.length > 0) {
        btCandleSeries.setMarkers(btPriceChartMarkers);
      }
      // Add entry→exit price connection lines (TradingView style)
      btTradeLineSeries = buildTradePriceLines(backtest.trades, candles, btPriceChart);
    }

    // Fit chart to data
    btPriceChart.timeScale().fitContent();

    // Handle resize — store observer so it can be disconnected on rebuild
    _priceChartResizeObserver = new ResizeObserver(() => {
      if (btPriceChart) {
        btPriceChart.applyOptions({
          width: container.clientWidth,
          height: container.clientHeight || 480
        });
      }
    });
    _priceChartResizeObserver.observe(container);
    // Sync trade markers/lines and observer to StateManager
    setPriceChartMarkers(btPriceChartMarkers);
    setPriceChartTradeLineSeries(btTradeLineSeries);
    setPriceChartResizeObserver(_priceChartResizeObserver);

    console.log(`[PriceChart] Rendered ${candles.length} candles, ${btPriceChartMarkers.length} trade markers for ${symbol}/${interval}`);

  } catch (error) {
    console.error('[PriceChart] Error:', error);
  } finally {
    if (loadingEl) loadingEl.classList.add('hidden');
  }
}

/**
 * Build LightweightCharts markers from backtest trades (TradingView exact style).
 *
 * TradingView convention (from user's reference screenshot):
 *
 * ENTRY:
 *   Long  → blue ↑ arrow BELOW the wick, text: "buy\n+0.002939"
 *   Short → red  ↓ arrow ABOVE the wick, text: "sell\n-0.001234"
 *   Grid/DCA → "G1"..."G15" instead of "buy"
 *
 * EXIT:
 *   Long exit  → purple ↓ arrow ABOVE the wick, text: "-0.002939\nTP" or "SL"
 *   Short exit → purple ↑ arrow BELOW the wick, text: "+0.001234\nTP" or "SL"
 *   Multi-TP   → "TP1"..."TP4" instead of "TP"
 *
 * Colors: Entry Long=#2196F3 (blue), Entry Short=#ef5350 (red), Exit=#AB47BC (purple)
 */
function buildTradeMarkers(trades, candles, options = {}) {
  if (!trades || trades.length === 0 || !candles || candles.length === 0) return [];

  // Read display options from checkboxes (with defaults)
  const showPnl = options.showPnl ?? (document.getElementById('markerShowPnl')?.checked ?? true);
  const showEntryPrice = options.showEntryPrice ?? (document.getElementById('markerShowEntryPrice')?.checked ?? true);

  const markers = [];
  const firstCandleTime = candles[0].time;
  const lastCandleTime = candles[candles.length - 1].time;

  // Colors matching TradingView
  const ENTRY_LONG_COLOR = '#2196F3';   // Blue
  const ENTRY_SHORT_COLOR = '#ef5350';  // Red
  const EXIT_COLOR = '#AB47BC';         // Purple (сиреневый)

  trades.forEach((trade) => {
    // Parse entry/exit times to seconds
    let entryTimeSec = parseTradeTime(trade.entry_time);
    let exitTimeSec = parseTradeTime(trade.exit_time);

    if (!entryTimeSec || !exitTimeSec) return;

    // Snap to nearest candle time
    entryTimeSec = snapToCandle(entryTimeSec, candles);
    exitTimeSec = snapToCandle(exitTimeSec, candles);

    // Skip markers outside visible range
    if (entryTimeSec < firstCandleTime || entryTimeSec > lastCandleTime) return;

    const sideNorm = (trade.side || 'long').toLowerCase();
    const isLong = sideNorm === 'long' || sideNorm === 'buy';
    const pnl = trade.pnl || 0;
    const pnlStr = pnl >= 0 ? `+${pnl.toFixed(2)}` : pnl.toFixed(2);

    // --- Determine entry label ---
    // Grid/DCA: "G1"..."G15", normal: "buy"/"sell"
    const entryLabel = trade.grid_level
      ? `G${trade.grid_level}`
      : (isLong ? 'buy' : 'sell');

    // --- Determine exit reason (try exit_comment first, then exit_reason) ---
    const exitReason = (trade.exit_comment || trade.exit_reason || '').toLowerCase();

    // Determine exit label: TP, SL, TP1-TP4, trailing, signal, etc.
    let exitLabel;
    if (/^tp\d+$/.test(exitReason)) {
      exitLabel = exitReason.toUpperCase();
    } else if (exitReason === 'tp' || exitReason.includes('take_profit')) {
      exitLabel = 'TP';
    } else if (exitReason === 'sl' || exitReason.includes('stop_loss')) {
      exitLabel = 'SL';
    } else if (exitReason.includes('trailing') || exitReason === 'tsl') {
      exitLabel = 'TSL';
    } else if (exitReason.includes('signal')) {
      exitLabel = 'Signal';
    } else if (exitReason.includes('time_exit') || exitReason.includes('session') || exitReason.includes('weekend')) {
      exitLabel = 'Time';
    } else if (exitReason.includes('end_of_data') || exitReason === 'eod') {
      exitLabel = 'EOD';
    } else if (exitReason.includes('breakeven') || exitReason === 'be') {
      exitLabel = 'BE';
    } else {
      exitLabel = 'Close';
    }

    // --- ENTRY MARKER ---
    // Long: blue ↑ below bar | Short: red ↓ above bar
    // Build entry text: "buy" + optional entry price
    let entryText = entryLabel;
    if (showEntryPrice && trade.entry_price) {
      entryText += ` ${trade.entry_price.toFixed(2)}`;
    }
    markers.push({
      time: entryTimeSec,
      position: isLong ? 'belowBar' : 'aboveBar',
      color: isLong ? ENTRY_LONG_COLOR : ENTRY_SHORT_COLOR,
      shape: isLong ? 'arrowUp' : 'arrowDown',
      text: entryText,
      size: 2
    });

    // --- EXIT MARKER ---
    if (exitTimeSec >= firstCandleTime && exitTimeSec <= lastCandleTime) {
      // Build exit text: "TP" + optional PnL
      let exitText = exitLabel;
      if (showPnl) {
        exitText += ` ${pnlStr}`;
      }
      markers.push({
        time: exitTimeSec,
        position: isLong ? 'aboveBar' : 'belowBar',
        color: EXIT_COLOR,
        shape: isLong ? 'arrowDown' : 'arrowUp',
        text: exitText,
        size: 2
      });
    }
  });

  // Sort markers by time (required by LightweightCharts)
  markers.sort((a, b) => a.time - b.time);
  return markers;
}

/**
 * Rebuild trade markers on the price chart based on current checkbox states.
 * Called when user toggles "Show PnL" or "Show Entry Price" checkboxes.
 */
function rebuildTradeMarkers() {
  if (!btCandleSeries || !currentBacktest?.trades || _btCachedCandles.length === 0) return;
  btPriceChartMarkers = buildTradeMarkers(currentBacktest.trades, _btCachedCandles);
  btCandleSeries.setMarkers(btPriceChartMarkers);
  console.log(`[PriceChart] Rebuilt ${btPriceChartMarkers.length} markers (PnL=${document.getElementById('markerShowPnl')?.checked}, Price=${document.getElementById('markerShowEntryPrice')?.checked})`);
}

/**
 * Build trade price connection lines on the price chart.
 * For each trade, draws a dashed horizontal line from entry candle to exit candle
 * at the entry_price level. Color: green if profitable, red if loss.
 * Also optionally draws exit_price line (TP/SL level).
 *
 * Uses LightweightCharts lineSeries with sparse data (only 2 points per trade).
 */
function buildTradePriceLines(trades, candles, chart) {
  if (!trades || trades.length === 0 || !candles || candles.length === 0 || !chart) return [];

  const firstCandleTime = candles[0].time;
  const lastCandleTime = candles[candles.length - 1].time;
  const seriesList = [];

  trades.forEach((trade) => {
    let entryTimeSec = parseTradeTime(trade.entry_time);
    let exitTimeSec = parseTradeTime(trade.exit_time);
    if (!entryTimeSec || !exitTimeSec) return;

    entryTimeSec = snapToCandle(entryTimeSec, candles);
    exitTimeSec = snapToCandle(exitTimeSec, candles);

    if (entryTimeSec < firstCandleTime || entryTimeSec > lastCandleTime) return;
    if (exitTimeSec < firstCandleTime) return;
    // Clamp exit to visible range
    if (exitTimeSec > lastCandleTime) exitTimeSec = lastCandleTime;

    const entryPrice = trade.entry_price || 0;
    const exitPrice = trade.exit_price || 0;
    const pnl = trade.pnl || 0;
    const isProfitable = pnl >= 0;

    // Don't draw line if entry and exit are on same candle
    if (entryTimeSec === exitTimeSec) return;

    // --- Entry price line (dashed, from entry to exit) ---
    const entryLine = chart.addLineSeries({
      color: isProfitable ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false
    });
    entryLine.setData([
      { time: entryTimeSec, value: entryPrice },
      { time: exitTimeSec, value: entryPrice }
    ]);
    seriesList.push(entryLine);

    // --- Exit price line (dotted, from entry to exit) for TP/SL visualization ---
    if (Math.abs(exitPrice - entryPrice) > 0.01) {
      const exitLine = chart.addLineSeries({
        color: isProfitable ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false
      });
      exitLine.setData([
        { time: entryTimeSec, value: exitPrice },
        { time: exitTimeSec, value: exitPrice }
      ]);
      seriesList.push(exitLine);
    }
  });

  return seriesList;
}

/**
 * Parse trade time (ms timestamp or ISO string) to Unix seconds.
 */
function parseTradeTime(time) {
  if (!time) return null;
  if (typeof time === 'number') {
    // If > 1e12, it's in milliseconds
    return time > 1e12 ? Math.floor(time / 1000) : time;
  }
  if (typeof time === 'string') {
    const d = new Date(time);
    return isNaN(d.getTime()) ? null : Math.floor(d.getTime() / 1000);
  }
  return null;
}

/**
 * Snap a timestamp to the nearest candle time using binary search.
 */
function snapToCandle(timeSec, candles) {
  if (!candles || candles.length === 0) return timeSec;

  let lo = 0;
  let hi = candles.length - 1;

  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (candles[mid].time < timeSec) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }

  // Check lo and lo-1 for closest match
  if (lo > 0) {
    const diffLo = Math.abs(candles[lo].time - timeSec);
    const diffPrev = Math.abs(candles[lo - 1].time - timeSec);
    return diffPrev < diffLo ? candles[lo - 1].time : candles[lo].time;
  }

  return candles[lo].time;
}

/**
 * Format interval code to human-readable label.
 */
function formatInterval(interval) {
  const map = {
    '1': '1m', '5': '5m', '15': '15m', '30': '30m',
    '60': '1H', '240': '4H', 'D': '1D', 'W': '1W', 'M': '1M',
    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
    '1h': '1H', '4h': '4H', '1d': '1D', '1w': '1W'
  };
  return map[interval] || interval;
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: initCharts, initTradesTable, setDefaultDates, setupFilters, loadBacktestResults

// Attach to window for HTML onclick handlers
if (typeof window !== 'undefined') {
  window.toggleFilters = toggleFilters;
  window.toggleCompareMode = toggleCompareMode;
  window.toggleCompareSelect = toggleCompareSelect;
  window.showNewBacktestModal = showNewBacktestModal;
  window.toggleMtfSettings = toggleMtfSettings;
  window.toggleOptimizeSettings = toggleOptimizeSettings;
  window.runBacktest = runBacktest;
  window.requestAIAnalysis = requestAIAnalysis;
  window.compareWithAI = compareWithAI;
  window.exportResults = exportResults;
  window.exportTrades = exportTrades;
  window.refreshData = refreshData;
  window.selectBacktest = selectBacktest;
  window.deleteBacktest = deleteBacktest;
  window.selectAllForDelete = selectAllForDelete;
  window.deleteSelectedBacktests = deleteSelectedBacktests;
  window.toggleBulkSelectItem = toggleBulkSelectItem;

  window.backtestresultsPage = {
    loadBacktestResults,
    selectBacktest,
    deleteBacktest,
    deleteSelectedBacktests,
    refreshData
  };
}

// =============================================================================
// P1-4: Metrics Heatmap
// =============================================================================

/**
 * Metric groups for heatmap display.
 * Each group has a label and a list of {key, label, format, goodWhen} entries.
 * goodWhen: 'high' | 'low' | 'neutral'
 */
const HEATMAP_METRIC_GROUPS = [
  {
    label: 'Доходность',
    metrics: [
      { key: 'net_profit_pct', label: 'Net Profit %', format: 'pct', goodWhen: 'high' },
      { key: 'total_return', label: 'Total Return', format: 'pct', goodWhen: 'high' },
      { key: 'cagr', label: 'CAGR %', format: 'pct', goodWhen: 'high' },
      { key: 'avg_trade_pct', label: 'Avg Trade', format: 'pct', goodWhen: 'high' }
    ]
  },
  {
    label: 'Риск',
    metrics: [
      { key: 'max_drawdown', label: 'Max DD %', format: 'pct', goodWhen: 'low' },
      { key: 'avg_drawdown', label: 'Avg DD %', format: 'pct', goodWhen: 'low' },
      { key: 'volatility', label: 'Volatility', format: 'num2', goodWhen: 'low' },
      { key: 'ulcer_index', label: 'Ulcer Index', format: 'num2', goodWhen: 'low' }
    ]
  },
  {
    label: 'Качество',
    metrics: [
      { key: 'sharpe_ratio', label: 'Sharpe', format: 'num2', goodWhen: 'high' },
      { key: 'sortino_ratio', label: 'Sortino', format: 'num2', goodWhen: 'high' },
      { key: 'calmar_ratio', label: 'Calmar', format: 'num2', goodWhen: 'high' },
      { key: 'sqn', label: 'SQN', format: 'num2', goodWhen: 'high' }
    ]
  },
  {
    label: 'Сделки',
    metrics: [
      { key: 'win_rate', label: 'Win Rate %', format: 'pct', goodWhen: 'high' },
      { key: 'profit_factor', label: 'Profit Factor', format: 'num2', goodWhen: 'high' },
      { key: 'payoff_ratio', label: 'Payoff Ratio', format: 'num2', goodWhen: 'high' },
      { key: 'expectancy', label: 'Expectancy', format: 'num2', goodWhen: 'high' }
    ]
  }
];

/** Thresholds for heatmap coloring per metric type */
const HEATMAP_THRESHOLDS = {
  sharpe_ratio: { bad: 0, ok: 1, good: 2 },
  sortino_ratio: { bad: 0, ok: 1, good: 2 },
  calmar_ratio: { bad: 0, ok: 0.5, good: 1 },
  sqn: { bad: 0, ok: 1.6, good: 2.5 },
  win_rate: { bad: 40, ok: 50, good: 60 },
  profit_factor: { bad: 1, ok: 1.3, good: 1.8 },
  payoff_ratio: { bad: 0.8, ok: 1.2, good: 2 },
  expectancy: { bad: 0, ok: 0.2, good: 0.5 },
  net_profit_percent: { bad: 0, ok: 10, good: 50 },
  total_return: { bad: 0, ok: 10, good: 50 },
  cagr: { bad: 0, ok: 10, good: 30 },
  avg_trade_pnl: { bad: 0, ok: 0.2, good: 1 },
  max_drawdown: { bad: 30, ok: 20, good: 10 },   // inverted: low is good
  avg_drawdown: { bad: 15, ok: 10, good: 5 },
  volatility: { bad: 50, ok: 30, good: 15 },
  ulcer_index: { bad: 20, ok: 10, good: 5 }
};

/**
 * Get heatmap color class for a metric value.
 * @param {string} key
 * @param {number} value
 * @param {'high'|'low'|'neutral'} goodWhen
 * @returns {string} CSS class: hm-good | hm-ok | hm-bad | hm-neutral
 */
function getHeatmapColor(key, value, goodWhen) {
  if (value === null || value === undefined || isNaN(value)) return 'hm-neutral';
  const t = HEATMAP_THRESHOLDS[key];
  if (!t) return 'hm-neutral';

  if (goodWhen === 'high') {
    if (value >= t.good) return 'hm-good';
    if (value >= t.ok) return 'hm-ok';
    return 'hm-bad';
  } else if (goodWhen === 'low') {
    // For low-is-good metrics, thresholds are reversed
    if (value <= t.good) return 'hm-good';
    if (value <= t.ok) return 'hm-ok';
    return 'hm-bad';
  }
  return 'hm-neutral';
}

/**
 * Format a metric value for heatmap display.
 * @param {number} value
 * @param {'pct'|'num2'|'int'} format
 * @returns {string}
 */
function formatHeatmapValue(value, format) {
  if (value === null || value === undefined || isNaN(value)) return '--';
  // Treat 0 as valid value (not missing data)
  if (value === 0 || value === 0.0) {
    switch (format) {
      case 'pct': return '0.0%';
      case 'num2': return '0.00';
      case 'int': return '0';
      default: return '0.00';
    }
  }
  switch (format) {
    case 'pct': return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
    case 'num2': return value.toFixed(2);
    case 'int': return Math.round(value).toString();
    default: return value.toFixed(2);
  }
}

/**
 * P1-4: Render the metrics heatmap into #metricsHeatmapContainer.
 * @param {Object|null} metrics
 */
function renderMetricsHeatmap(metrics) {
  const container = document.getElementById('metricsHeatmapContainer');
  if (!container) return;

  if (!metrics) {
    container.innerHTML = '<div class="text-center py-5 text-secondary">Нет данных для отображения</div>';
    return;
  }

  // Debug: log missing metrics
  const allKeys = HEATMAP_METRIC_GROUPS.flatMap(g => g.metrics.map(m => m.key));
  const missingKeys = allKeys.filter(key => metrics[key] === undefined || metrics[key] === null || isNaN(parseFloat(metrics[key])));
  if (missingKeys.length > 0) {
    console.warn('[Heatmap] Missing metrics:', missingKeys);
    console.log('[Heatmap] Available metrics keys:', Object.keys(metrics).filter(k => !k.startsWith('_')).sort());

    // Show which metrics have zero values
    const zeroKeys = allKeys.filter(key => metrics[key] === 0 || metrics[key] === 0.0);
    if (zeroKeys.length > 0) {
      console.warn('[Heatmap] Metrics with ZERO value (may indicate no trades):', zeroKeys);
    }

    // Debug: show specific values for problematic metrics
    console.log('[Heatmap] Debug - avg_trade_pct:', metrics.avg_trade_pct, 'type:', typeof metrics.avg_trade_pct);
    console.log('[Heatmap] Debug - payoff_ratio:', metrics.payoff_ratio, 'type:', typeof metrics.payoff_ratio);
    console.log('[Heatmap] Debug - avg_win:', metrics.avg_win, 'avg_loss:', metrics.avg_loss);
    console.log('[Heatmap] Debug - total_trades:', metrics.total_trades, 'winning_trades:', metrics.winning_trades, 'losing_trades:', metrics.losing_trades);
  }

  const groups = HEATMAP_METRIC_GROUPS.map((group) => {
    const cells = group.metrics.map((m) => {
      const raw = metrics[m.key];
      const value = raw !== undefined && raw !== null ? parseFloat(raw) : null;
      const colorClass = getHeatmapColor(m.key, value, m.goodWhen);
      const formatted = formatHeatmapValue(value, m.format);

      // Debug for problematic metrics
      if (['avg_trade_pct', 'payoff_ratio'].includes(m.key)) {
        console.log(`[Heatmap] ${m.key}: raw=${raw}, value=${value}, formatted=${formatted}`);
      }

      return `<div class="hm-cell ${colorClass}" title="${m.label}: ${formatted}">
        <div class="hm-cell-label">${m.label}</div>
        <div class="hm-cell-value">${formatted}</div>
      </div>`;
    }).join('');

    return `<div class="hm-group">
      <div class="hm-group-title">${group.label}</div>
      <div class="hm-group-cells">${cells}</div>
    </div>`;
  }).join('');

  container.innerHTML = groups;
}

// =============================================================================
// P1-5: Walk-Forward Visualization
// =============================================================================

/** Chart.js instance for WF equity curve */
let wfEquityChartInstance = null;

/**
 * P1-5: Render Walk-Forward results into the #tab-walk-forward tab.
 * @param {Object|null} wfData - WalkForwardResult dict from API (or null if not available)
 */
function renderWalkForwardViz(wfData) {
  const windowsContainer = document.getElementById('wfWindowsContainer');
  const stabilityBadge = document.getElementById('wfStabilityBadge');
  const stabilityScore = document.getElementById('wfStabilityScore');
  const oosWinRate = document.getElementById('wfOosWinRate');
  const paramContainer = document.getElementById('wfParamStabilityContainer');
  const paramBody = document.getElementById('wfParamStabilityBody');
  const canvas = document.getElementById('wfEquityChart');

  if (!windowsContainer) return;

  // Destroy previous chart instance
  if (wfEquityChartInstance) {
    wfEquityChartInstance.destroy();
    wfEquityChartInstance = null;
  }

  if (!wfData || !wfData.windows || wfData.windows.length === 0) {
    windowsContainer.innerHTML = `<div class="text-center py-5 text-secondary">
      <i class="bi bi-arrow-repeat fs-2 mb-2 d-block"></i>
      Запустите оптимизацию Walk-Forward для отображения результатов
    </div>`;
    if (stabilityBadge) stabilityBadge.classList.add('d-none');
    if (paramContainer) paramContainer.classList.add('d-none');
    return;
  }

  // --- Stability badges ---
  if (stabilityBadge) stabilityBadge.classList.remove('d-none');
  if (stabilityScore) {
    const ps = wfData.parameter_stability ?? wfData.oos_win_rate ?? 0;
    stabilityScore.textContent = `${(ps * 100).toFixed(1)}%`;
  }
  if (oosWinRate) {
    oosWinRate.textContent = ((wfData.oos_win_rate ?? 0) * 100).toFixed(1);
  }

  // --- OOS Equity Chart ---
  if (canvas && wfData.combined_oos_equity && wfData.combined_oos_equity.length > 0) {
    // Lazy-load Chart.js if needed
    const renderOosChart = (ChartLib) => {
      const labels = wfData.combined_oos_equity.map((_, i) => i + 1);
      const startVal = wfData.combined_oos_equity[0];
      const data = wfData.combined_oos_equity.map((v) => ((v - startVal) / startVal) * 100);

      wfEquityChartInstance = new ChartLib(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'OOS Equity (% от старта)',
            data,
            borderColor: '#2962ff',
            backgroundColor: 'rgba(41,98,255,0.08)',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { display: false },
            y: {
              ticks: { color: '#9e9e9e', callback: (v) => `${v.toFixed(1)}%` },
              grid: { color: 'rgba(255,255,255,0.05)' }
            }
          }
        }
      });
    };

    if (typeof Chart !== 'undefined') {
      renderOosChart(Chart);
    } else {
      // Chart.js not loaded — skip chart, show text summary
      canvas.style.display = 'none';
    }
  }

  // --- Windows table ---
  const rows = wfData.windows.map((w, i) => {
    const isSharpe = (w.is_metrics?.sharpe_ratio ?? 0).toFixed(2);
    const oosSharpe = (w.oos_metrics?.sharpe_ratio ?? 0).toFixed(2);
    const isRet = ((w.is_metrics?.total_return ?? 0)).toFixed(1);
    const oosRet = ((w.oos_metrics?.total_return ?? 0)).toFixed(1);
    const degrad = ((w.sharpe_degradation ?? 0) * 100).toFixed(1);
    const degradClass = (w.sharpe_degradation ?? 0) < 0 ? 'text-danger' : 'text-success';
    const bestParams = w.best_params
      ? Object.entries(w.best_params).map(([k, v]) => `${k}=${v}`).join(', ')
      : '--';

    return `<tr>
      <td>${i + 1}</td>
      <td class="text-secondary">${w.train_start ? w.train_start.slice(0, 10) : '--'}</td>
      <td class="text-secondary">${w.test_end ? w.test_end.slice(0, 10) : '--'}</td>
      <td>${isSharpe}</td>
      <td>${oosSharpe}</td>
      <td class="${degradClass}">${degrad}%</td>
      <td>${isRet}%</td>
      <td>${oosRet}%</td>
      <td class="text-secondary small">${bestParams}</td>
    </tr>`;
  }).join('');

  windowsContainer.innerHTML = `
    <div class="mb-2 d-flex gap-3 text-secondary small">
      <span>Окон: <strong>${wfData.total_windows}</strong></span>
      <span>Avg IS Sharpe: <strong>${(wfData.avg_is_sharpe ?? 0).toFixed(2)}</strong></span>
      <span>Avg OOS Sharpe: <strong>${(wfData.avg_oos_sharpe ?? 0).toFixed(2)}</strong></span>
      <span>Combined OOS Return: <strong>${((wfData.combined_oos_return ?? 0)).toFixed(1)}%</strong></span>
    </div>
    <div style="overflow-x:auto">
      <table class="tv-data-table">
        <thead>
          <tr>
            <th>#</th><th>Train Start</th><th>Test End</th>
            <th>IS Sharpe</th><th>OOS Sharpe</th><th>Degradation</th>
            <th>IS Return</th><th>OOS Return</th><th>Best Params</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  // --- Parameter Stability ---
  if (wfData.param_stability_report && Object.keys(wfData.param_stability_report).length > 0) {
    if (paramContainer) paramContainer.classList.remove('d-none');
    if (paramBody) {
      paramBody.innerHTML = Object.entries(wfData.param_stability_report).map(([param, stats]) => {
        const cv = (stats.cv_pct ?? 0).toFixed(1);
        const stab = (stats.stability_pct ?? 0).toFixed(1);
        const stabClass = parseFloat(stab) >= 70 ? 'text-success' : parseFloat(stab) >= 40 ? 'text-warning' : 'text-danger';
        return `<tr>
          <td>${param}</td>
          <td>${(stats.mean ?? 0).toFixed(4)}</td>
          <td>${(stats.std ?? 0).toFixed(4)}</td>
          <td>${cv}%</td>
          <td class="${stabClass} fw-bold">${stab}%</td>
        </tr>`;
      }).join('');
    }
  }
}

