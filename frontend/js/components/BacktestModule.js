/**
 * 📊 BacktestModule.js
 *
 * Extracted from strategy_builder.js during P0-1 refactoring.
 * Handles all backtest-related logic:
 *   - Request building (buildBacktestRequest, extractSlTpFromBlocks)
 *   - Indicator/block mapping (mapIndicatorToStrategyType, mapIndicatorParams, _mapBlocksToBackendParams)
 *   - Timeframe helpers (normalizeTimeframeForDropdown, convertIntervalToAPIFormat)
 *   - Day-filter helpers (getNoTradeDaysFromUI, setNoTradeDaysInUI)
 *   - Backtest execution (runBacktest)
 *   - Results display (displayBacktestResults, renderResultsSummaryCards, renderOverviewMetrics,
 *     renderTradesTable, renderAllMetrics, renderEquityChart, renderDrawdownChart,
 *     switchResultsTab, closeBacktestResultsModal, exportBacktestResults, viewFullResults)
 *   - Local format helpers (formatPercent, formatPrice, formatDateTime, formatDuration)
 *
 * Dependencies are injected via createBacktestModule({ deps }) factory.
 *
 * @version 1.0.0
 * @date 2026-02-26
 * @migration P0-1: extracted from strategy_builder.js
 */

import { formatCurrency } from '../utils.js';

// ============================================================
// PURE / STATELESS HELPERS (exported for unit tests)
// ============================================================

/** Bybit API v5 kline intervals: 1,3,5,15,30,60,120,240,360,720,D,W,M */
const BYBIT_INTERVALS = new Set(['1', '5', '15', '30', '60', '240', 'D', 'W', 'M']);
const LEGACY_TF_MAP_DROPDOWN = { '3': '5', '120': '60', '360': '240', '720': 'D' };

/**
 * Нормализовать сохранённый таймфрейм к значению для выпадающего списка.
 * Поддерживает старый формат (1h, 15m) и нативный (15, 60, D). Устаревшие TF → ближайший.
 */
export function normalizeTimeframeForDropdown(stored) {
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
export function convertIntervalToAPIFormat(value) {
    const s = String(value).trim();
    if (BYBIT_INTERVALS.has(s)) return s;
    if (LEGACY_TF_MAP_DROPDOWN[s]) return LEGACY_TF_MAP_DROPDOWN[s];
    const mapping = {
        '1m': '1', '3m': '5', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '60', '4h': '240', '6h': '240', '12h': 'D', '1d': 'D', '1D': 'D', '1w': 'W', '1W': 'W', '1M': 'M', 'M': 'M'
    };
    return mapping[s] || '15';
}

/**
 * Map indicator block type to backend strategy_type.
 * @param {string} blockType
 * @returns {string}
 */
export function mapIndicatorToStrategyType(blockType) {
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
 * Map indicator block params to backend strategy_params format.
 * @param {Object} block - Strategy block with .type and .params
 * @param {Function} getDefaultParamsFn - fallback for missing params
 * @returns {Object}
 */
export function mapIndicatorParams(block, getDefaultParamsFn) {
    const params = block.params || (getDefaultParamsFn ? getDefaultParamsFn(block.type) : {});
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
 *
 * @param {Array} blocks - strategyBlocks array
 * @returns {Object}
 */
export function extractSlTpFromBlocks(blocks) {
    const result = {};
    for (const block of blocks) {
        const type = block.type;
        const params = block.params || {};
        if (type === 'static_sltp') {
            if (params.stop_loss_percent != null && result.stop_loss == null) {
                result.stop_loss = params.stop_loss_percent / 100;
            }
            if (params.take_profit_percent != null && result.take_profit == null) {
                result.take_profit = params.take_profit_percent / 100;
            }
            if (params.activate_breakeven) {
                result.breakeven_enabled = true;
                const beActivation = params.breakeven_activation_percent ?? 0.5;
                const beNewSl = params.new_breakeven_sl_percent ?? 0.1;
                result.breakeven_activation_pct = beActivation / 100;
                result.breakeven_offset = beNewSl / 100;
            }
            if (params.close_only_in_profit) {
                result.close_only_in_profit = true;
            }
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

// Format helper functions for backtest results
// Note: formatCurrency is imported from utils.js

export function formatPercent(value) {
    if (value === undefined || value === null) return '0.00%';
    return Number(value).toFixed(2) + '%';
}

export function formatPrice(value) {
    if (value === undefined || value === null) return '0.00';
    return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 });
}

export function formatDateTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

export function formatDuration(seconds) {
    if (!seconds || seconds === 0) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 24) {
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h`;
    }
    return `${hours}h ${minutes}m`;
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

export function getNoTradeDaysFromUI() {
    const out = [];
    for (const { id, weekday } of DAY_BLOCK_IDS) {
        const el = document.getElementById(id);
        if (el && el.checked) out.push(weekday);
    }
    return out;
}

export function setNoTradeDaysInUI(days) {
    const set = new Set(Array.isArray(days) ? days : []);
    for (const { id, weekday } of DAY_BLOCK_IDS) {
        const el = document.getElementById(id);
        if (el) el.checked = set.has(weekday);
    }
}

// ============================================================
// RENDER HELPERS (exported for unit tests)
// ============================================================

/**
 * Render summary cards at top of results.
 * @param {Object} results - Backtest results from API
 */
export function renderResultsSummaryCards(results) {
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
 * Render overview metrics grid.
 * @param {Object} results
 */
export function renderOverviewMetrics(results) {
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
 * Render trades table body.
 * @param {Array} trades
 */
export function renderTradesTable(trades) {
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
 * Render all metrics organised by category.
 * @param {Object} results
 */
export function renderAllMetrics(results) {
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
 * Render equity curve on #equityChart canvas.
 * @param {Array} equityCurve
 */
export function renderEquityChart(equityCurve) {
    const canvas = document.getElementById('equityChart');
    if (!canvas || !equityCurve || equityCurve.length === 0) return;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    canvas.width = container.clientWidth || 600;
    canvas.height = container.clientHeight || 300;

    const padding = 40;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    const values = equityCurve.map(p => p.equity || p.value || p);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;

    ctx.fillStyle = '#161b22';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (height * i) / 4;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(canvas.width - padding, y);
        ctx.stroke();
    }

    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((val, idx) => {
        const x = values.length <= 1 ? padding + width / 2 : padding + (idx / (values.length - 1)) * width;
        const y = range > 0 ? padding + height - ((val - minVal) / range) * height : padding + height / 2;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.beginPath();
    values.forEach((val, idx) => {
        const x = values.length <= 1 ? padding + width / 2 : padding + (idx / (values.length - 1)) * width;
        const y = range > 0 ? padding + height - ((val - minVal) / range) * height : padding + height / 2;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.lineTo(padding + width, padding + height);
    ctx.lineTo(padding, padding + height);
    ctx.closePath();
    ctx.fillStyle = 'rgba(88, 166, 255, 0.1)';
    ctx.fill();

    ctx.fillStyle = '#8b949e';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(formatCurrency(maxVal), padding - 5, padding + 5);
    ctx.fillText(formatCurrency(minVal), padding - 5, padding + height);
}

/**
 * Render drawdown chart on #drawdownChart canvas.
 * @param {Array} equityCurve - Same array as renderEquityChart
 */
export function renderDrawdownChart(equityCurve) {
    const canvas = document.getElementById('drawdownChart');
    if (!canvas || !equityCurve || equityCurve.length === 0) return;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    canvas.width = container.clientWidth || 600;
    canvas.height = container.clientHeight || 300;

    const padding = 40;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    const values = equityCurve.map(p => {
        const dd = p.drawdown !== undefined ? p.drawdown : 0;
        return Math.min(dd, 0);
    });
    const minVal = Math.min(...values, -0.001);
    const maxVal = 0;
    const range = maxVal - minVal || 1;

    ctx.fillStyle = '#161b22';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (height * i) / 4;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(canvas.width - padding, y);
        ctx.stroke();
        const pct = (maxVal - (range * i) / 4) * 100;
        ctx.fillStyle = '#8b949e';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(pct.toFixed(1) + '%', padding - 5, y + 4);
    }

    ctx.strokeStyle = '#484f58';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(canvas.width - padding, padding);
    ctx.stroke();

    ctx.strokeStyle = '#f85149';
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((val, idx) => {
        const x = values.length <= 1 ? padding + width / 2 : padding + (idx / (values.length - 1)) * width;
        const y = padding + ((maxVal - val) / range) * height;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.beginPath();
    values.forEach((val, idx) => {
        const x = values.length <= 1 ? padding + width / 2 : padding + (idx / (values.length - 1)) * width;
        const y = padding + ((maxVal - val) / range) * height;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.lineTo(padding + width, padding);
    ctx.lineTo(padding, padding);
    ctx.closePath();
    ctx.fillStyle = 'rgba(248, 81, 73, 0.15)';
    ctx.fill();
}

// ============================================================
// MODULE FACTORY — Stateful operations via injected dependencies
// ============================================================

/**
 * Create a BacktestModule instance with injected dependencies.
 *
 * @param {Object} deps
 * @param {Function} deps.getBlocks      - () => strategyBlocks[]
 * @param {Function} deps.getBlockLibrary - () => blockLibrary
 * @param {Function} deps.getDefaultParams - (blockType) => Object
 * @param {Function} deps.showNotification - (msg, type) => void
 * @param {Function} deps.saveStrategy   - async () => void
 * @param {Function} deps.autoSaveStrategy - async () => void
 * @param {Function} deps.validateStrategyCompleteness - () => {valid, errors, warnings}
 * @param {Function} deps.validateStrategy - async () => void
 * @param {Function} deps.getStrategyIdFromURL - () => string|null
 * @param {Function} deps.setSBCurrentBacktestResults - (v) => void
 * @returns {Object} Module instance with public methods
 */
export function createBacktestModule(deps) {
    const {
        getBlocks,
        getBlockLibrary,
        getDefaultParams,
        showNotification,
        saveStrategy,
        autoSaveStrategy,
        validateStrategyCompleteness,
        validateStrategy,
        getStrategyIdFromURL,
        setSBCurrentBacktestResults
    } = deps;

    // Module-local state
    let _currentBacktestResults = null;

    // ──────────────────────────────────────────────────────────
    // _mapBlocksToBackendParams
    // NOTE (2026-02-15): NOT used by buildBacktestRequest().
    // The backend reads blocks/connections from the database.
    // Kept for potential future use (code generation).
    // ──────────────────────────────────────────────────────────
    function _mapBlocksToBackendParams() {
        const strategyBlocks = getBlocks();
        const blockLibrary = getBlockLibrary();
        const result = {
            strategy_type: 'custom',
            strategy_params: {},
            filters: [],
            exits: [],
            position_sizing: null,
            risk_controls: []
        };

        const indicatorBlocks = strategyBlocks.filter(b =>
            blockLibrary.indicators.some(ind => ind.id === b.type)
        );
        const filterBlocks = strategyBlocks.filter(b =>
            blockLibrary.filters.some(f => f.id === b.type)
        );
        const exitBlocks = strategyBlocks.filter(b =>
            (blockLibrary.exits && blockLibrary.exits.some(e => e.id === b.type)) ||
            (blockLibrary.close_conditions && blockLibrary.close_conditions.some(c => c.id === b.type))
        );
        const sizingBlocks = strategyBlocks.filter(b =>
            blockLibrary.position_sizing && blockLibrary.position_sizing.some(s => s.id === b.type)
        );
        const riskBlocks = strategyBlocks.filter(b =>
            blockLibrary.risk_controls && blockLibrary.risk_controls.some(r => r.id === b.type)
        );

        if (indicatorBlocks.length > 0) {
            const primaryIndicator = indicatorBlocks[0];
            result.strategy_type = mapIndicatorToStrategyType(primaryIndicator.type);
            result.strategy_params = mapIndicatorParams(primaryIndicator, getDefaultParams);
        }

        filterBlocks.forEach(block => {
            result.filters.push({
                type: block.type,
                params: block.params || getDefaultParams(block.type),
                enabled: block.params?.enabled !== false
            });
        });

        exitBlocks.forEach(block => {
            result.exits.push({
                type: block.type,
                params: block.params || getDefaultParams(block.type)
            });
        });

        if (sizingBlocks.length > 0) {
            result.position_sizing = {
                type: sizingBlocks[0].type,
                params: sizingBlocks[0].params || getDefaultParams(sizingBlocks[0].type)
            };
        }

        riskBlocks.forEach(block => {
            result.risk_controls.push({
                type: block.type,
                params: block.params || getDefaultParams(block.type)
            });
        });

        return result;
    }

    /**
     * Build full backtest request from UI state.
     *
     * NOTE: Backend reads blocks/connections from the DATABASE (not from this payload).
     * Only Properties-panel fields (symbol, interval, capital, leverage, etc.) are sent here.
     */
    function buildBacktestRequest() {
        const timeframeRaw = document.getElementById('strategyTimeframe')?.value || '15';
        const interval = convertIntervalToAPIFormat(timeframeRaw);
        const strategyBlocks = getBlocks();

        const backtestConfig = {
            symbol: document.getElementById('backtestSymbol')?.value || 'BTCUSDT',
            interval: interval,
            start_date: document.getElementById('backtestStartDate')?.value || '2025-01-01',
            end_date: (() => {
                const endVal = document.getElementById('backtestEndDate')?.value || new Date().toISOString().slice(0, 10);
                const today = new Date().toISOString().slice(0, 10);
                if (endVal > today) {
                    showNotification(`End Date ${endVal} в будущем — бэктест запускается по сегодняшнюю дату (${today})`, 'info');
                    console.info(`[Backtest] End date ${endVal} is in the future, clamped to ${today}`);
                    return today;
                }
                return endVal;
            })(),
            market_type: document.getElementById('builderMarketType')?.value || 'linear',
            initial_capital: parseFloat(document.getElementById('backtestCapital')?.value) || 10000,
            leverage: parseInt(document.getElementById('backtestLeverage')?.value) || 10,
            direction: document.getElementById('builderDirection')?.value || 'both',
            pyramiding: parseInt(document.getElementById('backtestPyramiding')?.value) || 1,

            // Commission: read from UI as percentage (e.g. 0.07 = 0.07%), convert to decimal (0.0007)
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
                return rawVal / 100;
            })(),

            slippage: (() => {
                const el = document.getElementById('backtestSlippage');
                const rawSlip = el != null ? parseFloat(el.value) : 0.0;
                if (isNaN(rawSlip) || rawSlip < 0) return 0.0;
                if (rawSlip > 5.0) return 0.05;
                return rawSlip / 100;
            })(),

            position_size_type: document.getElementById('backtestPositionSizeType')?.value || 'percent',
            position_size: (() => {
                const typeEl = document.getElementById('backtestPositionSizeType');
                const sizeEl = document.getElementById('backtestPositionSize');
                const type = typeEl?.value || 'percent';
                const val = parseFloat(sizeEl?.value) || 100;
                return type === 'percent' ? val / 100 : val;
            })(),

            no_trade_days: getNoTradeDaysFromUI(),

            ...extractSlTpFromBlocks(strategyBlocks)
        };

        return backtestConfig;
    }

    /**
     * Display backtest results in the results modal.
     * @param {Object} results - Backtest results from API
     */
    function displayBacktestResults(results) {
        console.log('[Strategy Builder] Displaying backtest results:', results);
        _currentBacktestResults = results;
        setSBCurrentBacktestResults(results);

        const modal = document.getElementById('backtestResultsModal');
        if (!modal) {
            console.error('[Strategy Builder] Results modal not found');
            return;
        }

        renderResultsSummaryCards(results);
        renderOverviewMetrics(results);
        renderTradesTable(results.trades || []);
        renderAllMetrics(results);

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        const ec = results.equity_curve;
        if (ec && typeof ec === 'object' && Array.isArray(ec.equity) && ec.equity.length > 0) {
            const trades = (results.trades || []).map(t => ({
                ...t,
                mfe: Math.abs(t.mfe_pct || 0),
                mae: Math.abs(t.mae_pct || 0)
            }));

            window._sbEquityChartData = {
                timestamps: ec.timestamps,
                equity: ec.equity,
                bh_equity: ec.bh_equity || [],
                trades: trades,
                initial_capital: (results.metrics && results.metrics.initial_capital) || results.initial_capital || 10000
            };

            if (window._sbEquityChart) {
                try { window._sbEquityChart.destroy(); } catch (_e) { /* ignore destroy errors */ }
                window._sbEquityChart = null;
            }
        } else {
            window._sbEquityChartData = null;
        }
    }

    /**
     * Switch between result tabs.
     * @param {string} tabId
     */
    function switchResultsTab(tabId) {
        document.querySelectorAll('.results-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });
        document.querySelectorAll('.results-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });

        if (tabId === 'equity') {
            const TVChart = window.TradingViewEquityChart;
            const chartData = window._sbEquityChartData;
            console.log('[EquityTab] switched, TVChart=', typeof TVChart, 'chartData=', chartData ? 'ok(' + chartData.equity?.length + ' pts)' : 'null', '_sbEquityChart=', !!window._sbEquityChart);

            if (window._sbEquityChart) {
                setTimeout(() => {
                    try {
                        if (window._sbEquityChart.chart) window._sbEquityChart.chart.resize();
                    } catch (_e) { /* ignore resize errors when tab was hidden */ }
                }, 50);
            } else if (chartData && typeof TVChart !== 'undefined') {
                setTimeout(() => {
                    const showBH = document.getElementById('legendBuyHold')?.checked ?? false;
                    window._sbEquityChart = new TVChart('equityChartContainer', {
                        showBuyHold: showBH,
                        showTradeExcursions: true,
                        height: 320
                    });
                    window._sbEquityChart.render(chartData);
                }, 100);
            }
        }
    }

    /**
     * Close backtest results modal.
     */
    function closeBacktestResultsModal() {
        const modal = document.getElementById('backtestResultsModal');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        if (window._sbEquityChart) {
            try { window._sbEquityChart.destroy(); } catch (_e) { /* ignore */ }
            window._sbEquityChart = null;
        }
        window._sbEquityChartData = null;
    }

    /**
     * Export current backtest results as JSON file.
     */
    function exportBacktestResults() {
        if (!_currentBacktestResults) {
            showNotification('No results to export', 'warning');
            return;
        }

        const dataStr = JSON.stringify(_currentBacktestResults, null, 2);
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
     * Navigate to the full results page.
     */
    function viewFullResults() {
        if (_currentBacktestResults && _currentBacktestResults.backtest_id) {
            window.location.href = `backtest-results.html?backtest_id=${_currentBacktestResults.backtest_id}`;
        } else {
            showNotification('No backtest ID available', 'warning');
        }
    }

    /**
     * Main backtest execution function.
     */
    async function runBacktest() {
        console.log('[Strategy Builder] runBacktest called');
        let strategyId = getStrategyIdFromURL();
        console.log('[Strategy Builder] Strategy ID from URL:', strategyId);

        if (!strategyId) {
            showNotification('Сохраните стратегию перед запуском бэктеста', 'warning');
            if (confirm('Strategy not saved. Save now?')) {
                await saveStrategy();
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

        const strategyBlocks = getBlocks();
        if (strategyBlocks.length === 0) {
            showNotification('Добавьте блоки в стратегию перед бэктестом', 'warning');
            return;
        }

        // PRE-BACKTEST VALIDATION (3-part check)
        const preCheck = validateStrategyCompleteness();
        if (!preCheck.valid) {
            const errorMsg = preCheck.errors.join('\n');
            showNotification(`Стратегия не готова к бэктесту:\n${errorMsg}`, 'error');
            await validateStrategy();
            const vPanel = document.querySelector('.validation-panel');
            if (vPanel) { vPanel.classList.remove('closing'); vPanel.classList.add('visible'); }
            return;
        }
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
        const endDateRaw = document.getElementById('backtestEndDate')?.value;
        if (!endDateRaw) {
            showNotification('Укажите End Date перед запуском бэктеста', 'warning');
            document.getElementById('backtestEndDate')?.focus();
            return;
        }
        const endDateVal = endDateRaw;
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

        // Bug #5 fix: sync graph to DB before backtest so backend reads up-to-date state
        await autoSaveStrategy();

        const backtestParams = buildBacktestRequest();
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

                if (data.warnings && data.warnings.length > 0) {
                    data.warnings.forEach(w => {
                        console.warn('[Strategy Builder] Backend warning:', w);
                        showNotification(`⚠️ ${w}`, 'warning');
                    });
                }

                console.log('[SB v20260225f] data.metrics=', !!data.metrics, 'data.trades=', !!(data.trades && data.trades.length), 'data.equity_curve=', !!data.equity_curve, 'data.backtest_id=', data.backtest_id);
                if (data.metrics || data.trades || data.equity_curve) {
                    showNotification('Бэктест завершён!', 'success');
                    displayBacktestResults(data);
                } else if (data.backtest_id) {
                    showNotification('Бэктест завершён!', 'success');
                    try {
                        const resultsResponse = await fetch(`/api/v1/backtests/${data.backtest_id}`);
                        if (resultsResponse.ok) {
                            const resultsData = await resultsResponse.json();
                            resultsData.backtest_id = data.backtest_id;
                            displayBacktestResults(resultsData);
                        } else {
                            window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
                        }
                    } catch (fetchErr) {
                        console.error('[BacktestModal] fetch /api/v1/backtests/ failed:', fetchErr);
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

    return {
        // Stateful operations
        runBacktest,
        buildBacktestRequest,
        displayBacktestResults,
        switchResultsTab,
        closeBacktestResultsModal,
        exportBacktestResults,
        viewFullResults,
        _mapBlocksToBackendParams,
        // Expose for external reading (e.g. AI Build module)
        getCurrentResults: () => _currentBacktestResults,
        setCurrentResults: (v) => { _currentBacktestResults = v; }
    };
}
