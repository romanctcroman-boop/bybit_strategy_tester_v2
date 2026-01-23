/**
 * рџ“„ Backtest Results Page JavaScript
 *
 * Page-specific scripts for backtest_results.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/* global Tabulator */

// Import shared utilities
import { formatDate as _formatDate } from '../utils.js';

// ============================
// Configuration
// ============================
const API_BASE = '/api/v1';
let currentBacktest = null;
let allResults = [];
let selectedForCompare = [];
let compareMode = false;

// Track recently deleted IDs to filter them from API responses
// This prevents "ghost" items from reappearing due to backend sync delay
const recentlyDeletedIds = new Set();

// Charts
let equityChart = null;
let drawdownChart = null;
let returnsChart = null;
let monthlyChart = null;
// Trade Analysis Charts
let tradeDistributionChart = null;
let winLossDonutChart = null;
// Dynamics Charts
let waterfallChart = null;
let benchmarkingChart = null;

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
            const laneY = Math.min(chartArea.bottom - 10, yScale.getPixelForValue(yScale.min) - 6);
            const size = pluginOptions.size ?? 7; // triangle size
            const offsetY = pluginOptions.offsetY ?? 0;

            // Keep markers inside chart area
            const minX = chartArea.left + size + 1;
            const maxX = chartArea.right - size - 1;
            const y = Math.max(chartArea.top + size + 1, Math.min(chartArea.bottom - size - 1, laneY + offsetY));

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
                const isShort = side === 'short';

                const fill = pnl > 0 ? '#26a69a' : (pnl < 0 ? '#ef5350' : '#78909c');

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

if (typeof Chart !== 'undefined') {
    Chart.register(equityTradeMarkersPlugin);
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

            // Minimal gap of 1px between bars for maximum width
            const gap = 1;
            const numTrades = tradeRanges.length;
            const chartWidth = chartArea.right - chartArea.left;

            // N candles = (N+1) total gaps (between + edges)
            const totalGaps = numTrades + 1;
            const totalGapsWidth = totalGaps * gap;
            const availableWidth = chartWidth - totalGapsWidth;
            const calculatedBarWidth = availableWidth / numTrades;

            // Bar width limits
            const absoluteMinWidth = 3;
            const absoluteMaxWidth = 150;
            const barWidth = Math.max(absoluteMinWidth, Math.min(absoluteMaxWidth, calculatedBarWidth));

            // Process each trade
            tradeRanges.forEach((range, idx) => {
                const mfe = Math.abs(range.mfe || 0);
                const mae = Math.abs(range.mae || 0);

                // Get trade P&L for realized portion
                const tradeInfo = Object.values(tradeMap || {}).find(ti => ti.tradeNum === idx + 1);
                const tradePnL = tradeInfo?.pnl || 0;
                const realizedProfit = tradePnL > 0 ? Math.min(tradePnL, mfe) : 0;
                const realizedLoss = tradePnL < 0 ? Math.min(Math.abs(tradePnL), mae) : 0;

                // Calculate X position based on ENTRY point (trade open time)
                const entryX = xScale.getPixelForValue(range.entryIdx);
                if (!Number.isFinite(entryX)) return;

                // Center the bar on the ENTRY point
                let barX = entryX - barWidth / 2;

                // Clamp bar position to stay within chart boundaries
                barX = Math.max(chartArea.left, Math.min(chartArea.right - barWidth, barX));

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
// Initialization
// ============================
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initTradingViewTabs();
    loadBacktestResults();
    loadStrategies();
    setDefaultDates();
    setupFilters();
    setupChartResize();
});

// Handle URL changes (back/forward navigation or redirect with ?id=)
window.addEventListener('popstate', () => {
    loadBacktestResults();
});

// Handle backtest loaded from inline fallback script
window.addEventListener('backtestLoaded', (event) => {
    const backtest = event.detail;
    if (backtest) {
        console.log('[backtestLoaded event] Received backtest data, updating charts');
        currentBacktest = backtest;
        updateCharts(backtest);
    }
});

// Setup chart container resize observer
function setupChartResize() {
    const chartContainer = document.querySelector('.tv-equity-chart-container');
    if (chartContainer && equityChart) {
        const resizeObserver = new ResizeObserver(() => {
            if (equityChart) {
                equityChart.resize();
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
    const equityCanvas = document.getElementById('equityChart');
    if (equityCanvas) {
        equityChart = new Chart(equityCanvas, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Капитал стратегии',
                        data: [],
                        type: 'line',
                        yAxisID: 'y',
                        borderColor: '#26a69a',
                        segment: {
                            borderColor: (ctx) => {
                                const y0 = ctx?.p0?.parsed?.y;
                                const y1 = ctx?.p1?.parsed?.y;
                                const y = (y0 + y1) / 2;
                                return y >= 0 ? '#26a69a' : '#ef5350';
                            }
                        },
                        backgroundColor: (ctx) => {
                            const chart = ctx.chart;
                            const { chartArea, scales } = chart;
                            if (!chartArea || !scales?.y) return 'rgba(38, 166, 154, 0.12)';

                            const zeroY = scales.y.getPixelForValue(0);
                            const top = chartArea.top;
                            const bottom = chartArea.bottom;

                            // Guard against invalid values
                            if (!Number.isFinite(zeroY) || !Number.isFinite(top) || !Number.isFinite(bottom) || bottom <= top) {
                                return 'rgba(38, 166, 154, 0.12)';
                            }

                            // Two-part gradient: green above 0, red below 0 (TV-like)
                            const gradient = chart.ctx.createLinearGradient(0, top, 0, bottom);
                            let t = (zeroY - top) / (bottom - top);

                            // Clamp t to valid range and check for NaN
                            if (!Number.isFinite(t)) t = 0.5;
                            t = Math.min(1, Math.max(0, t));

                            gradient.addColorStop(0, 'rgba(38, 166, 154, 0.18)');
                            gradient.addColorStop(Math.max(0, Math.min(0.999, t - 0.001)), 'rgba(38, 166, 154, 0.04)');
                            gradient.addColorStop(Math.max(0.001, Math.min(1, t + 0.001)), 'rgba(239, 83, 80, 0.04)');
                            gradient.addColorStop(1, 'rgba(239, 83, 80, 0.14)');
                            return gradient;
                        },
                        fill: {
                            target: { value: 0 }
                        },
                        tension: 0,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        pointHitRadius: 8,
                        borderWidth: 4,
                        order: 1
                    },
                    {
                        label: 'Покупка и удержание',
                        data: [],
                        type: 'line',
                        yAxisID: 'y',
                        borderColor: '#ef5350',
                        backgroundColor: '#ef5350',
                        fill: false,
                        tension: 0,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                        borderWidth: 2,
                        borderDash: [4, 6],
                        borderCapStyle: 'round',
                        order: 2
                    }
                    // TradingView-style Trade Excursion Bars are drawn by custom plugin
                    // (tradeExcursionBarsPlugin) instead of Chart.js datasets
                    // This allows unified bars with MFE up + MAE down in single bar
                ]
            },
            options: {
                ...chartOptions,
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    equityTradeMarkers: {
                        enabled: false,
                        size: 7,
                        offsetY: 0
                    },
                    tradeExcursionBars: {
                        enabled: true  // Draw unified MFE+MAE bars via custom plugin
                    },
                    annotation: {
                        annotations: {
                            zeroLine: {
                                type: 'line',
                                yMin: 0,
                                yMax: 0,
                                borderColor: '#787b86',
                                borderWidth: 1,
                                drawTime: 'afterDatasetsDraw'
                            }
                        }
                    },
                    datalabels: {
                        display: (context) => {
                            // Show label on last point of strategy line only
                            return context.datasetIndex === 0 && context.dataIndex === context.dataset.data.length - 1;
                        },
                        align: 'left',
                        anchor: 'end',
                        offset: 8,
                        backgroundColor: (context) => {
                            const value = context.dataset.data[context.dataIndex];
                            return value >= 0 ? '#26a69a' : '#ef5350';
                        },
                        borderRadius: 6,
                        color: 'white',
                        font: { weight: 'bold', size: 13 },
                        padding: { left: 10, right: 10, top: 6, bottom: 6 },
                        formatter: (value) => {
                            const sign = value > 0 ? '+' : '';
                            return sign + value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(30, 30, 30, 0.95)',
                        titleColor: '#ffffff',
                        bodyColor: '#c9d1d9',
                        borderColor: '#404040',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function (context) {
                                const idx = context[0].dataIndex;
                                const tradeInfo = equityChart._tradeMap?.[idx];
                                if (tradeInfo) {
                                    const side = tradeInfo.side === 'short' ? 'Short' : 'Long';
                                    return `Trade #${tradeInfo.tradeNum} вЂў ${side}`;
                                }
                                const data = equityChart._equityData;
                                if (data && data[idx]) {
                                    const d = new Date(data[idx].timestamp);
                                    return d.toLocaleDateString('ru-RU', {
                                        weekday: 'short',
                                        day: 'numeric',
                                        month: 'short',
                                        year: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                    });
                                }
                                return context[0].label;
                            },
                            label: function (context) {
                                const datasetLabel = context.dataset.label;
                                const idx = context.dataIndex;
                                const value = context.parsed.y;

                                const sign = value >= 0 ? '+' : '';
                                const color = value >= 0 ? '🟢' : '🔴';

                                // Trade-specific lines (prefer TV-like fields when hovering around a trade)
                                const tradeInfo = equityChart._tradeMap?.[idx];
                                if (tradeInfo && datasetLabel === 'Капитал стратегии') {
                                    const cumPnL = Number(tradeInfo.cumulativePnL ?? 0);
                                    const cumSign = cumPnL >= 0 ? '+' : '';

                                    const exitStr = tradeInfo.exitTime
                                        ? new Date(tradeInfo.exitTime).toLocaleString('ru-RU', {
                                            year: 'numeric',
                                            month: '2-digit',
                                            day: '2-digit',
                                            hour: '2-digit',
                                            minute: '2-digit',
                                            second: '2-digit'
                                        })
                                        : null;

                                    const lines = [];
                                    lines.push(`Cumulative P&L: ${cumSign}${cumPnL.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USDT`);

                                    // Show MFE/MAE (Trades excursions) in TradingView style
                                    const mfeValue = tradeInfo.mfe_value;
                                    const maeValue = tradeInfo.mae_value;

                                    if (mfeValue !== null && mfeValue !== undefined) {
                                        lines.push(`Favorable excursion: ${Number(mfeValue).toFixed(2)} USDT`);
                                    }
                                    if (maeValue !== null && maeValue !== undefined) {
                                        lines.push(`Adverse excursion: ${Number(maeValue).toFixed(2)} USDT`);
                                    }

                                    if (exitStr) lines.push(exitStr);
                                    return lines;
                                }

                                // Default: show series value
                                if (datasetLabel === 'Капитал стратегии') {
                                    return `${color} Совокупные ПР/УБ  ${sign}${value.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USD`;
                                }

                                // Buy & Hold should only appear if enabled in legend
                                if (datasetLabel === 'Покупка и удержание') {
                                    const buyHoldCheckbox = document.getElementById('legendBuyHold');
                                    if (buyHoldCheckbox && !buyHoldCheckbox.checked) return null;
                                    return `   B&H ПР/УБ     ${sign}${value.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USD`;
                                }

                                // Skip Excursion/Realized bars in tooltip (they show in trade info above)
                                if (datasetLabel.includes('Excursion') || datasetLabel.includes('Realized')) {
                                    return null;
                                }

                                return null;
                            }
                        },
                        filter: function (tooltipItem) {
                            // Hide excursion bars from tooltip list
                            const label = tooltipItem.dataset.label;
                            return !label.includes('Excursion') && !label.includes('Realized');
                        }
                    }
                },
                scales: {
                    x: {
                        offset: true,  // Add padding at edges so bars don't touch boundaries
                        grid: {
                            color: '#2a2e39',
                            drawOnChartArea: true,
                            drawTicks: false
                        },
                        ticks: {
                            color: '#787b86',
                            maxTicksLimit: 12,
                            maxRotation: 0,
                            font: { size: 11 },
                            padding: 8
                        },
                        border: {
                            color: '#2a2e39'
                        }
                    },
                    y: {
                        position: 'right',
                        grace: '10%',
                        grid: {
                            color: '#2a2e39',
                            drawOnChartArea: true,
                            drawTicks: false
                        },
                        ticks: {
                            color: '#787b86',
                            font: { size: 11 },
                            padding: 8,
                            maxTicksLimit: 15,
                            callback: (v) => {
                                if (v > 0) return '+' + v.toLocaleString('ru-RU', { minimumFractionDigits: 2 });
                                if (v < 0) return v.toLocaleString('ru-RU', { minimumFractionDigits: 2 });
                                return '0';
                            }
                        },
                        border: {
                            display: false
                        }
                    },
                    y2: {
                        display: false,
                        position: 'left',
                        grid: { display: false },
                        // MFE/MAE bars - each bar starts from 0
                        stacked: false,
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Drawdown Chart
    const drawdownCanvas = document.getElementById('drawdownChart');
    if (drawdownCanvas) {
        drawdownChart = new Chart(drawdownCanvas, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Drawdown %',
                    data: [],
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248, 81, 73, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: chartOptions
        });
    }

    // Returns Distribution
    const returnsCanvas = document.getElementById('returnsChart');
    if (returnsCanvas) {
        returnsChart = new Chart(returnsCanvas, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Trade Returns',
                    data: [],
                    backgroundColor: []
                }]
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
        monthlyChart = new Chart(monthlyCanvas, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Monthly P&L',
                    data: [],
                    backgroundColor: []
                }]
            },
            options: chartOptions
        });
    }

    // Trade Distribution Chart (in Trade Analysis tab)
    const tradeDistCanvas = document.getElementById('tradeDistributionChart');
    if (tradeDistCanvas) {
        tradeDistributionChart = new Chart(tradeDistCanvas, {
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
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false },
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
        winLossDonutChart = new Chart(winLossCanvas, {
            type: 'doughnut',
            data: {
                labels: ['Победы', 'Убытки', 'Безубыточность'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#26a69a', '#ef5350', '#78909c'],
                    borderWidth: 0
                }]
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
                        display: false  // Use custom HTML legend
                    },
                    tooltip: {
                        backgroundColor: 'rgba(22, 27, 34, 0.95)',
                        callbacks: {
                            label: function (context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((context.raw / total) * 100).toFixed(2) : 0;
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
        waterfallChart = new Chart(waterfallCanvas, {
            type: 'bar',
            data: {
                labels: ['Итого прибыль', 'Открытые ПР/УБ', 'Итого убыток', 'Комиссия', 'Общие ПР/УБ'],
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
                                if (!val || val === 0) return null;
                                return `${context.dataset.label}: ${val.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USD`;
                            }
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
                        grid: { color: '#30363d' },
                        ticks: {
                            color: '#e6edf3',
                            callback: (v) => v >= 1000 ? (v / 1000).toFixed(2) + ' K' : v.toFixed(0)
                        }
                    }
                }
            }
        });
    }

    // Benchmarking Chart (in Dynamics tab)
    const benchmarkingCanvas = document.getElementById('benchmarkingChart');
    if (benchmarkingCanvas) {
        benchmarkingChart = new Chart(benchmarkingCanvas, {
            type: 'bar',
            data: {
                labels: ['Прибыль при покупке и удержании', 'Прибыльность стратегии'],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: '#ffffff',
                            usePointStyle: true,
                            pointStyle: 'rect',
                            padding: 15,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(22, 27, 34, 0.95)',
                        titleColor: '#c9d1d9',
                        bodyColor: '#c9d1d9',
                        callbacks: {
                            label: function (context) {
                                return `${context.dataset.label}: ${context.raw.toFixed(2)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: '#30363d' },
                        ticks: {
                            color: '#e6edf3',
                            callback: (v) => v + '%'
                        }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#e6edf3', font: { size: 11 } }
                    }
                }
            }
        });
    }
}

// ============================
// TradingView Style Tabs
// ============================
function initTradingViewTabs() {
    const tabs = document.querySelectorAll('.tv-report-tab');
    const contents = document.querySelectorAll('.tv-report-tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            // Remove active from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            // Activate clicked tab and its content
            tab.classList.add('active');
            const content = document.getElementById(`tab-${targetTab}`);
            if (content) {
                content.classList.add('active');
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

    if (legendBuyHold) {
        legendBuyHold.addEventListener('change', () => {
            if (equityChart) {
                // Dataset 1 is "Покупка и удержание"
                equityChart.data.datasets[1].hidden = !legendBuyHold.checked;
                equityChart.update('none');
            }
        });
    }

    // Trades excursions (MFE/MAE) toggle - now uses custom plugin
    if (legendTradesExcursions) {
        // Restore persisted state (default is checked)
        const saved = localStorage.getItem('tv_trades_excursions');
        if (saved === '0') {
            legendTradesExcursions.checked = false;
        }

        // Store on chart for quick access (used by plugin)
        if (equityChart) {
            equityChart._showTradeExcursions = legendTradesExcursions.checked;
            // Also update in tvEquityChart if available
            if (window.tvEquityChart) {
                window.tvEquityChart.options.showTradeExcursions = legendTradesExcursions.checked;
            }
            equityChart.update('none');
        }

        legendTradesExcursions.addEventListener('change', () => {
            localStorage.setItem('tv_trades_excursions', legendTradesExcursions.checked ? '1' : '0');
            if (equityChart) {
                equityChart._showTradeExcursions = legendTradesExcursions.checked;
                // Also update in tvEquityChart if available
                if (window.tvEquityChart) {
                    window.tvEquityChart.options.showTradeExcursions = legendTradesExcursions.checked;
                }
                equityChart.update('none');
            }
        });
    }
}

// Chart mode toggle (Absolute / Percent)
let chartDisplayMode = 'absolute';
let originalEquityData = null;
let originalBuyHoldData = null;

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
    if (!equityChart || !originalEquityData || originalEquityData.length === 0) return;

    // originalEquityData already contains P&L values (not absolute equity)
    // For percent mode, we need to convert P&L to percentage of initial capital
    // We need to store initial capital separately
    const initialCapital = equityChart._initialCapital || 10000;

    if (chartDisplayMode === 'percent') {
        // Convert P&L to percentage of initial capital
        const equityPct = originalEquityData.map(v => (v / initialCapital) * 100);
        const buyHoldPct = originalBuyHoldData?.map(v => (v / initialCapital) * 100) || [];

        equityChart.data.datasets[0].data = equityPct;
        equityChart.data.datasets[1].data = buyHoldPct;

        // Update Y axis for percent display
        equityChart.options.scales.y.ticks.callback = (value) => {
            if (value > 0) return '+' + value.toFixed(2) + '%';
            if (value < 0) return value.toFixed(2) + '%';
            return '0%';
        };
    } else {
        // Restore absolute P&L values
        equityChart.data.datasets[0].data = [...originalEquityData];
        equityChart.data.datasets[1].data = originalBuyHoldData ? [...originalBuyHoldData] : [];

        // Reset Y axis for absolute display
        equityChart.options.scales.y.ticks.callback = (v) => {
            if (v > 0) return '+' + v.toLocaleString('ru-RU', { minimumFractionDigits: 2 });
            if (v < 0) return v.toLocaleString('ru-RU', { minimumFractionDigits: 2 });
            return '0';
        };
    }

    // MFE/MAE bars use main Y axis now, so they automatically align with zero line

    equityChart.update('none');
}
// Format TradingView style currency value with percentage
function formatTVCurrency(value, pct, showSign = true) {
    if (value === null || value === undefined) return '--';
    const sign = showSign && value >= 0 ? '+' : '';
    const dollarVal = `${sign}${value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
    if (pct !== undefined && pct !== null) {
        const pctSign = showSign && pct >= 0 ? '+' : '';
        return `<div class="tv-dual-value"><span class="tv-main-value">${dollarVal}</span><span class="tv-pct-value">${pctSign}${pct.toFixed(2)}%</span></div>`;
    }
    return dollarVal;
}

// Format percentage value
function formatTVPercent(value, showSign = true) {
    if (value === null || value === undefined) return '--';
    const sign = showSign && value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

// Update TradingView Summary Cards (Tab 1)
function updateTVSummaryCards(metrics) {
    if (!metrics) return;

    // Net Profit
    const netProfit = document.getElementById('tvNetProfit');
    const netProfitPct = document.getElementById('tvNetProfitPct');
    if (netProfit) {
        const val = metrics.net_profit || 0;
        netProfit.textContent = `${val >= 0 ? '+' : ''}${val.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USD`;
        netProfit.className = `tv-summary-card-value ${val >= 0 ? 'tv-value-positive' : 'tv-value-negative'}`;
    }
    if (netProfitPct) {
        const pct = metrics.net_profit_pct || metrics.total_return || 0;
        netProfitPct.textContent = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
    }

    // Max Drawdown
    const maxDD = document.getElementById('tvMaxDrawdown');
    const maxDDPct = document.getElementById('tvMaxDrawdownPct');
    if (maxDD) {
        const val = metrics.max_drawdown_value || 0;
        maxDD.textContent = `${Math.abs(val).toLocaleString('ru-RU', { minimumFractionDigits: 2 })} USD`;
    }
    if (maxDDPct) {
        const pct = metrics.max_drawdown || 0;
        maxDDPct.textContent = `${Math.abs(pct).toFixed(2)}%`;
    }

    // Total Trades
    const totalTrades = document.getElementById('tvTotalTrades');
    if (totalTrades) {
        totalTrades.textContent = metrics.total_trades || 0;
    }

    // Winning Trades
    const winningTrades = document.getElementById('tvWinningTrades');
    const winRate = document.getElementById('tvWinRate');
    if (winningTrades) {
        winningTrades.textContent = metrics.winning_trades || 0;
    }
    if (winRate) {
        winRate.textContent = `${(metrics.win_rate || 0).toFixed(2)}%`;
    }

    // Profit Factor
    const profitFactor = document.getElementById('tvProfitFactor');
    if (profitFactor) {
        profitFactor.textContent = (metrics.profit_factor || 0).toFixed(3);
    }
}

// Update Dynamics Tab (Tab 2)
function updateTVDynamicsTab(metrics, config, trades, equityCurve) {
    if (!metrics) return;

    const setValue = (id, value, format = 'currency') => {
        const el = document.getElementById(id);
        if (!el) return;

        if (value === null || value === undefined) {
            el.textContent = '--';
            return;
        }

        if (format === 'currency') {
            el.innerHTML = formatTVCurrency(value, null, true);
            el.className = value > 0 ? 'tv-value-positive' : value < 0 ? 'tv-value-negative' : 'tv-value-neutral';
        } else if (format === 'currency-pct') {
            el.innerHTML = formatTVCurrency(value.val, value.pct, true);
            el.className = value.val > 0 ? 'tv-value-positive' : value.val < 0 ? 'tv-value-negative' : 'tv-value-neutral';
        } else if (format === 'percent') {
            el.textContent = formatTVPercent(value, true);
            el.className = value > 0 ? 'tv-value-positive' : value < 0 ? 'tv-value-negative' : 'tv-value-neutral';
        } else if (format === 'number') {
            el.textContent = value.toLocaleString('ru-RU');
            el.className = 'tv-value-neutral';
        } else if (format === 'days') {
            el.textContent = `${value} дня`;
            el.className = 'tv-value-neutral';
        } else {
            el.textContent = value;
        }
    };

    // ===== USE METRICS DIRECTLY FROM BACKEND API =====
    // All Long/Short metrics are now calculated in backend engine.py
    // No more frontend recalculation - single source of truth!
    const initialCapital = config?.initial_capital || 10000;

    // Log metrics source for debugging
    console.log('[Dynamics Tab] Using backend metrics directly');
    console.log('[Dynamics Tab] Long: ' + (metrics.long_trades || 0) + ' trades, Short: ' + (metrics.short_trades || 0) + ' trades');
    console.log('[Dynamics Tab] GP=' + (metrics.gross_profit || 0).toFixed(2) + ', GL=' + (metrics.gross_loss || 0).toFixed(2) + ', Comm=' + (metrics.total_commission || 0).toFixed(2));

    // Initial Capital
    setValue('dyn-initial-capital', config?.initial_capital || 10000, 'number');

    // Unrealized P&L (Open position at end of backtest)
    setValue('dyn-unrealized', { val: metrics.open_pnl || 0, pct: metrics.open_pnl_pct || 0 }, 'currency-pct');

    // Net Profit - All, Long, Short (using backend _pct fields - NO frontend calculation!)
    setValue('dyn-net-profit', { val: metrics.net_profit || 0, pct: metrics.net_profit_pct || 0 }, 'currency-pct');
    setValue('dyn-net-profit-long', { val: metrics.long_net_profit || 0, pct: metrics.long_pnl_pct || 0 }, 'currency-pct');
    setValue('dyn-net-profit-short', { val: metrics.short_net_profit || 0, pct: metrics.short_pnl_pct || 0 }, 'currency-pct');

    // Gross Profit/Loss - All, Long, Short (using backend _pct fields - NO frontend calculation!)
    setValue('dyn-gross-profit', { val: metrics.gross_profit || 0, pct: metrics.gross_profit_pct || 0 }, 'currency-pct');
    setValue('dyn-gross-profit-long', { val: metrics.long_gross_profit || 0, pct: metrics.long_gross_profit_pct || 0 }, 'currency-pct');
    setValue('dyn-gross-profit-short', { val: metrics.short_gross_profit || 0, pct: metrics.short_gross_profit_pct || 0 }, 'currency-pct');

    setValue('dyn-gross-loss', { val: -(metrics.gross_loss || 0), pct: -(metrics.gross_loss_pct || 0) }, 'currency-pct');
    setValue('dyn-gross-loss-long', { val: -(metrics.long_gross_loss || 0), pct: -(metrics.long_gross_loss_pct || 0) }, 'currency-pct');
    setValue('dyn-gross-loss-short', { val: -(metrics.short_gross_loss || 0), pct: -(metrics.short_gross_loss_pct || 0) }, 'currency-pct');

    // Profit Factor - All, Long, Short (from backend metrics)
    const profitFactor = metrics.profit_factor || 0;
    setValue('dyn-profit-factor', profitFactor, 'number');
    setValue('dyn-profit-factor-long', metrics.long_profit_factor === Infinity ? 'в€ћ' : (metrics.long_profit_factor || 0), 'number');
    setValue('dyn-profit-factor-short', metrics.short_profit_factor === Infinity ? 'в€ћ' : (metrics.short_profit_factor || 0), 'number');

    // Commission - All, Long, Short (from backend metrics)
    setValue('dyn-commission', metrics.total_commission || 0, 'currency');
    setValue('dyn-commission-long', metrics.long_commission || 0, 'currency');
    setValue('dyn-commission-short', metrics.short_commission || 0, 'currency');

    // Expectancy - All, Long, Short (using backend-computed values)
    const expectancy = metrics.expectancy || 0;
    const longExpectancy = metrics.long_expectancy || 0;
    const shortExpectancy = metrics.short_expectancy || 0;
    setValue('dyn-expectancy', expectancy, 'currency');
    setValue('dyn-expectancy-long', longExpectancy, 'currency');
    setValue('dyn-expectancy-short', shortExpectancy, 'currency');

    // Buy & Hold
    const buyHoldValue = metrics.buy_hold_return || 0;
    let buyHoldPct = metrics.buy_hold_return_pct || 0;
    // Calculate percentage if not provided
    if (buyHoldPct === 0 && buyHoldValue !== 0 && initialCapital > 0) {
        buyHoldPct = (buyHoldValue / initialCapital) * 100;
    }
    setValue('dyn-buy-hold', { val: buyHoldValue, pct: buyHoldPct }, 'currency-pct');

    // Strategy vs Buy & Hold (outperformance)
    // Calculate if backend didn't provide
    let strategyOutperformance = metrics.strategy_outperformance || 0;
    if (strategyOutperformance === 0) {
        const strategyReturn = metrics.net_profit_pct || ((metrics.net_profit || 0) / initialCapital * 100);
        strategyOutperformance = strategyReturn - buyHoldPct;
    }
    setValue('dyn-strategy-vs-bh', strategyOutperformance, 'percent');

    // CAGR - All, Long, Short
    setValue('dyn-cagr', metrics.cagr || 0, 'percent');
    setValue('dyn-cagr-long', metrics.cagr_long || 0, 'percent');
    setValue('dyn-cagr-short', metrics.cagr_short || 0, 'percent');

    // Return on Capital - All, Long, Short (using backend _pct fields - NO frontend calculation!)
    setValue('dyn-return-capital', metrics.total_return || 0, 'percent');
    setValue('dyn-return-capital-long', metrics.long_pnl_pct || 0, 'percent');
    setValue('dyn-return-capital-short', metrics.short_pnl_pct || 0, 'percent');

    // Calculate Avg Growth/Drawdown Duration and Runup values from equity curve if backend didn't provide
    let avgGrowthDuration = metrics.avg_runup_duration_bars || 0;
    let avgDrawdownDuration = metrics.avg_drawdown_duration_bars || 0;
    let maxRunupValue = metrics.max_runup_value || 0;
    let maxRunupPct = metrics.max_runup || 0;
    let avgRunupValue = 0;
    let avgRunupPct = 0;
    let avgDrawdownValue = metrics.avg_drawdown_value || 0;
    let avgDrawdownPct = metrics.avg_drawdown || 0;

    // Parse equity curve data
    let equityValues = [];
    if (equityCurve) {
        if (Array.isArray(equityCurve)) {
            equityValues = equityCurve.map(p => p.equity);
        } else if (equityCurve.equity) {
            equityValues = equityCurve.equity;
        }
    }

    // If no equity curve, calculate runup/drawdown from trades cumulative PnL
    if (equityValues.length < 2 && trades && trades.length > 0) {
        equityValues = [initialCapital];
        let cumPnl = initialCapital;
        trades.forEach(t => {
            cumPnl += (t.pnl || 0);
            equityValues.push(cumPnl);
        });
    }

    if (equityValues.length > 1) {
        // Track growth and drawdown periods + runup/drawdown values
        const growthPeriods = [];
        const drawdownPeriods = [];
        const runupValues = []; // All runup values from local lows to peaks
        const drawdownValues = []; // All drawdown values from peaks to local lows
        let runningMax = equityValues[0];
        let localLow = equityValues[0]; // Lowest point before current growth period
        let periodStartLow = equityValues[0]; // Low at start of current growth period
        let currentGrowthBars = 0;
        let currentDrawdownBars = 0;
        let inDrawdown = false;
        let currentDrawdownDepth = 0; // Current drawdown from running max

        for (let i = 1; i < equityValues.length; i++) {
            const eq = equityValues[i];
            if (eq >= runningMax) {
                // New high or equal - we're in growth
                if (inDrawdown && currentDrawdownBars > 0) {
                    drawdownPeriods.push(currentDrawdownBars);
                    // Record the max drawdown depth for this period
                    if (currentDrawdownDepth > 0) {
                        drawdownValues.push(currentDrawdownDepth);
                    }
                    currentDrawdownBars = 0;
                    currentDrawdownDepth = 0;
                    // Save the low point we're recovering from
                    periodStartLow = localLow;
                }
                runningMax = eq;
                currentGrowthBars++;
                inDrawdown = false;
            } else {
                // Below max - we're in drawdown
                const dd = runningMax - eq;
                if (dd > currentDrawdownDepth) currentDrawdownDepth = dd;

                if (!inDrawdown && currentGrowthBars > 0) {
                    growthPeriods.push(currentGrowthBars);
                    // Record runup from period start low to peak
                    const runup = runningMax - periodStartLow;
                    if (runup > 0) runupValues.push(runup);
                    currentGrowthBars = 0;
                }
                currentDrawdownBars++;
                inDrawdown = true;
                // Track new local low
                if (eq < localLow) localLow = eq;
            }
        }
        // Push final period - if we ended in growth, record the runup
        if (currentGrowthBars > 0) {
            growthPeriods.push(currentGrowthBars);
            // Total runup = current max - starting low
            const totalRunup = runningMax - periodStartLow;
            if (totalRunup > 0) runupValues.push(totalRunup);
        }
        if (currentDrawdownBars > 0) {
            drawdownPeriods.push(currentDrawdownBars);
            if (currentDrawdownDepth > 0) {
                drawdownValues.push(currentDrawdownDepth);
            }
        }

        // Calculate averages for duration
        if (avgGrowthDuration === 0 && growthPeriods.length > 0) {
            avgGrowthDuration = Math.round(growthPeriods.reduce((a, b) => a + b, 0) / growthPeriods.length);
        }
        if (avgDrawdownDuration === 0 && drawdownPeriods.length > 0) {
            avgDrawdownDuration = Math.round(drawdownPeriods.reduce((a, b) => a + b, 0) / drawdownPeriods.length);
        }

        // Calculate max and avg runup values
        if (maxRunupValue === 0 && runupValues.length > 0) {
            maxRunupValue = Math.max(...runupValues);
            maxRunupPct = (maxRunupValue / initialCapital) * 100;
        }
        if (runupValues.length > 0) {
            avgRunupValue = runupValues.reduce((a, b) => a + b, 0) / runupValues.length;
            avgRunupPct = (avgRunupValue / initialCapital) * 100;
        }

        // Calculate avg drawdown value
        if (avgDrawdownValue === 0 && drawdownValues.length > 0) {
            avgDrawdownValue = drawdownValues.reduce((a, b) => a + b, 0) / drawdownValues.length;
            avgDrawdownPct = (avgDrawdownValue / initialCapital) * 100;
        }
    }

    // Equity Growth (Runup) metrics
    setValue('dyn-avg-growth-duration', avgGrowthDuration, 'number');
    setValue('dyn-avg-equity-growth', { val: avgRunupValue, pct: avgRunupPct }, 'currency-pct');
    setValue('dyn-max-equity-growth', { val: maxRunupValue, pct: maxRunupPct }, 'currency-pct');

    // Drawdown Duration metrics
    setValue('dyn-avg-dd-duration', avgDrawdownDuration, 'number');

    // Drawdown
    setValue('dyn-max-drawdown', { val: -(metrics.max_drawdown_value || 0), pct: -(metrics.max_drawdown || 0) }, 'currency-pct');
    setValue('dyn-avg-drawdown', { val: -avgDrawdownValue, pct: -avgDrawdownPct }, 'currency-pct');

    // Intrabar drawdown - not available (requires tick data)
    const intrabarEl = document.getElementById('dyn-max-dd-intrabar');
    if (intrabarEl) {
        intrabarEl.textContent = '--';
        intrabarEl.className = 'tv-value-neutral';
        intrabarEl.title = 'Недоступно (требуются тиковые данные)';
    }

    // Recovery / Return on Drawdown - All, Long, Short
    setValue('dyn-return-on-dd', metrics.recovery_factor || 0, 'number');
    const longRecovery = metrics.max_drawdown > 0 && metrics.long_net_profit
        ? (metrics.long_net_profit / (initialCapital * metrics.max_drawdown / 100))
        : 0;
    const shortRecovery = metrics.max_drawdown > 0 && metrics.short_net_profit
        ? (metrics.short_net_profit / (initialCapital * metrics.max_drawdown / 100))
        : 0;
    setValue('dyn-return-on-dd-long', longRecovery, 'number');
    setValue('dyn-return-on-dd-short', shortRecovery, 'number');

    // Net Profit vs Max Loss - All, Long, Short
    const maxLoss = Math.abs(metrics.largest_loss || metrics.worst_trade || 1);
    setValue('dyn-profit-vs-max-loss', maxLoss > 0 ? (metrics.net_profit || 0) / maxLoss : 0, 'number');
    setValue('dyn-profit-vs-max-loss-long', maxLoss > 0 ? (metrics.long_net_profit || 0) / maxLoss : 0, 'number');
    setValue('dyn-profit-vs-max-loss-short', maxLoss > 0 ? (metrics.short_net_profit || 0) / maxLoss : 0, 'number');
}

// Update Trade Analysis Tab (Tab 3)
// Uses metrics directly from backend API - NO recalculation
function updateTVTradeAnalysisTab(metrics, config, _trades) {
    if (!metrics) return;

    const _initialCapital = config?.initial_capital || 10000;  // Reserved for future use

    const setValue = (id, value, format = 'number') => {
        const el = document.getElementById(id);
        if (!el) return;

        if (value === null || value === undefined) {
            el.textContent = '--';
            return;
        }

        if (format === 'currency') {
            el.innerHTML = formatTVCurrency(value, null, true);
            el.className = value >= 0 ? 'tv-value-positive' : 'tv-value-negative';
        } else if (format === 'currency-pct') {
            el.innerHTML = formatTVCurrency(value.val, value.pct, true);
            el.className = value.val >= 0 ? 'tv-value-positive' : 'tv-value-negative';
        } else if (format === 'percent') {
            el.textContent = formatTVPercent(value, false);
            el.className = 'tv-value-neutral';
        } else if (format === 'decimal') {
            el.textContent = typeof value === 'number' ? value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value;
            el.className = 'tv-value-neutral';
        } else {
            el.textContent = value.toLocaleString ? value.toLocaleString('ru-RU') : value;
            el.className = 'tv-value-neutral';
        }
    };

    // Trade counts - All
    setValue('ta-open-trades', metrics.open_trades || 0);
    setValue('ta-total-trades', metrics.total_trades || 0);
    setValue('ta-winning-trades', metrics.winning_trades || 0);
    setValue('ta-losing-trades', metrics.losing_trades || 0);
    setValue('ta-breakeven-trades', metrics.breakeven_trades || 0);

    // Trade counts - Long (from backend)
    setValue('ta-open-trades-long', 0);
    setValue('ta-total-trades-long', metrics.long_trades || 0);
    setValue('ta-winning-trades-long', metrics.long_winning_trades || 0);
    setValue('ta-losing-trades-long', metrics.long_losing_trades || 0);
    setValue('ta-breakeven-trades-long', metrics.long_breakeven_trades || 0);

    // Trade counts - Short (from backend)
    setValue('ta-open-trades-short', 0);
    setValue('ta-total-trades-short', metrics.short_trades || 0);
    setValue('ta-winning-trades-short', metrics.short_winning_trades || 0);
    setValue('ta-losing-trades-short', metrics.short_losing_trades || 0);
    setValue('ta-breakeven-trades-short', metrics.short_breakeven_trades || 0);

    // Win rate - All/Long/Short (from backend)
    setValue('ta-win-rate', metrics.win_rate || 0, 'percent');
    setValue('ta-win-rate-long', metrics.long_win_rate || 0, 'percent');
    setValue('ta-win-rate-short', metrics.short_win_rate || 0, 'percent');

    // Avg P&L - All
    // Use avg_trade_value (calculated mean) instead of expectancy (which might be 0) to ensure data is likely present
    setValue('ta-avg-pnl', { val: metrics.avg_trade_value || 0, pct: metrics.avg_trade_pct || 0 }, 'currency-pct');
    setValue('ta-avg-win', { val: metrics.avg_win_value || 0, pct: metrics.avg_win || 0 }, 'currency-pct');
    setValue('ta-avg-loss', { val: -(metrics.avg_loss_value || 0), pct: -(metrics.avg_loss || 0) }, 'currency-pct');

    // Avg P&L - Long (backend sends: long_avg_win, long_avg_loss as values)
    setValue('ta-avg-pnl-long', { val: metrics.long_avg_trade_value || metrics.long_avg_trade || 0, pct: metrics.long_avg_trade_pct || 0 }, 'currency-pct');
    setValue('ta-avg-win-long', { val: metrics.long_avg_win_value || metrics.long_avg_win || 0, pct: metrics.long_avg_win_pct || 0 }, 'currency-pct');
    setValue('ta-avg-loss-long', { val: metrics.long_avg_loss_value || metrics.long_avg_loss || 0, pct: metrics.long_avg_loss_pct || 0 }, 'currency-pct');

    // Avg P&L - Short (backend sends: short_avg_win, short_avg_loss as values)
    setValue('ta-avg-pnl-short', { val: metrics.short_avg_trade_value || metrics.short_avg_trade || 0, pct: metrics.short_avg_trade_pct || 0 }, 'currency-pct');
    setValue('ta-avg-win-short', { val: metrics.short_avg_win_value || metrics.short_avg_win || 0, pct: metrics.short_avg_win_pct || 0 }, 'currency-pct');
    setValue('ta-avg-loss-short', { val: metrics.short_avg_loss_value || metrics.short_avg_loss || 0, pct: metrics.short_avg_loss_pct || 0 }, 'currency-pct');

    // Payoff ratio (from backend)
    setValue('ta-payoff-ratio', metrics.avg_win_loss_ratio || metrics.payoff_ratio || 0, 'number');
    setValue('ta-payoff-ratio-long', metrics.long_payoff_ratio || 0, 'number');
    setValue('ta-payoff-ratio-short', metrics.short_payoff_ratio || 0, 'number');

    // Largest trades - All (backend sends: largest_win = %, largest_win_value = $)
    // NO MORE FRONTEND CALCULATIONS - single source of truth!
    setValue('ta-largest-win', metrics.largest_win_value || metrics.best_trade || 0, 'currency');
    setValue('ta-largest-win-pct', metrics.largest_win || 0, 'percent');
    setValue('ta-largest-loss', -(metrics.largest_loss_value || Math.abs(metrics.worst_trade) || 0), 'currency');
    setValue('ta-largest-loss-pct', -(metrics.largest_loss || 0), 'percent');

    // Largest trades - Long (backend sends: long_largest_win = %, long_largest_win_value = $)
    // NO MORE FRONTEND CALCULATIONS - single source of truth!
    setValue('ta-largest-win-long', metrics.long_largest_win_value || 0, 'currency');
    setValue('ta-largest-win-pct-long', metrics.long_largest_win || 0, 'percent');
    setValue('ta-largest-loss-long', metrics.long_largest_loss_value || 0, 'currency');
    setValue('ta-largest-loss-pct-long', -(metrics.long_largest_loss || 0), 'percent');

    // Largest trades - Short (backend sends: short_largest_win = %, short_largest_win_value = $)
    // NO MORE FRONTEND CALCULATIONS - single source of truth!
    setValue('ta-largest-win-short', metrics.short_largest_win_value || 0, 'currency');
    setValue('ta-largest-win-pct-short', metrics.short_largest_win || 0, 'percent');
    setValue('ta-largest-loss-short', metrics.short_largest_loss_value || 0, 'currency');
    setValue('ta-largest-loss-pct-short', -(metrics.short_largest_loss || 0), 'percent');

    // Bars in trade - All (from backend)
    setValue('ta-avg-bars', metrics.avg_bars_in_trade || 0, 'decimal');
    setValue('ta-avg-bars-win', metrics.avg_bars_in_winning || 0, 'decimal');
    setValue('ta-avg-bars-loss', metrics.avg_bars_in_losing || 0, 'decimal');

    // Bars in trade - Long/Short (from backend)
    setValue('ta-avg-bars-long', metrics.avg_bars_in_long || 0, 'decimal');
    setValue('ta-avg-bars-short', metrics.avg_bars_in_short || 0, 'decimal');
    setValue('ta-avg-bars-win-long', metrics.avg_bars_in_winning_long || 0, 'decimal');
    setValue('ta-avg-bars-win-short', metrics.avg_bars_in_winning_short || 0, 'decimal');
    setValue('ta-avg-bars-loss-long', metrics.avg_bars_in_losing_long || 0, 'decimal');
    setValue('ta-avg-bars-loss-short', metrics.avg_bars_in_losing_short || 0, 'decimal');

    // Consecutive - All, Long, Short (from backend)
    setValue('ta-max-consec-wins', metrics.max_consecutive_wins || 0);
    setValue('ta-max-consec-losses', metrics.max_consecutive_losses || 0);
    setValue('ta-max-consec-wins-long', metrics.long_max_consec_wins || 0);
    setValue('ta-max-consec-wins-short', metrics.short_max_consec_wins || 0);
    setValue('ta-max-consec-losses-long', metrics.long_max_consec_losses || 0);
    setValue('ta-max-consec-losses-short', metrics.short_max_consec_losses || 0);
}

// Update Risk-Return Tab (Tab 4)
// Uses metrics directly from backend API - NO recalculation
function updateTVRiskReturnTab(metrics, _trades, _config) {
    if (!metrics) return;

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;

        if (value === null || value === undefined || isNaN(value)) {
            el.textContent = '--';
            el.className = 'tv-value-neutral';
            return;
        }

        el.textContent = value.toFixed(3);
        el.className = 'tv-value-neutral';
    };

    // All - use backend values
    setValue('rr-sharpe', metrics.sharpe_ratio);
    setValue('rr-sortino', metrics.sortino_ratio);
    setValue('rr-profit-factor', metrics.profit_factor);
    setValue('rr-calmar', metrics.calmar_ratio);
    setValue('rr-recovery', metrics.recovery_factor);

    // New Advanced Metrics
    setValue('rr-ulcer', metrics.ulcer_index);
    setValue('rr-ulcer-long', metrics.ulcer_index_long || null);  // Placeholder - requires per-direction equity curve
    setValue('rr-ulcer-short', metrics.ulcer_index_short || null);
    setValue('rr-margin-eff', metrics.margin_efficiency);
    setValue('rr-margin-eff-long', metrics.margin_efficiency_long || null);  // Placeholder
    setValue('rr-margin-eff-short', metrics.margin_efficiency_short || null);
    setValue('rr-stability', metrics.stability);
    setValue('rr-stability-long', metrics.stability_long || null);  // Placeholder
    setValue('rr-stability-short', metrics.stability_short || null);
    setValue('rr-sqn', metrics.sqn);
    setValue('rr-sqn-long', metrics.sqn_long || null);  // Placeholder
    setValue('rr-sqn-short', metrics.sqn_short || null);

    // Long - use backend values
    setValue('rr-sharpe-long', metrics.sharpe_long);
    setValue('rr-sortino-long', metrics.sortino_long);
    setValue('rr-profit-factor-long', metrics.long_profit_factor);
    setValue('rr-calmar-long', metrics.calmar_long);
    setValue('rr-recovery-long', metrics.recovery_long);

    // Short - use backend values
    setValue('rr-sharpe-short', metrics.sharpe_short);
    setValue('rr-sortino-short', metrics.sortino_short);
    setValue('rr-profit-factor-short', metrics.short_profit_factor);
    setValue('rr-calmar-short', metrics.calmar_short);
    setValue('rr-recovery-short', metrics.recovery_short);

    // Additional metrics (Kelly, Payoff, Consecutive)
    const kellyValue = metrics.kelly_percent || 0;
    setValue('rr-kelly', kellyValue * 100);  // Convert to percentage
    setValue('rr-kelly-long', (metrics.kelly_percent_long || 0) * 100);
    setValue('rr-kelly-short', (metrics.kelly_percent_short || 0) * 100);

    // Payoff Ratio = Avg Win / |Avg Loss|
    const payoff = metrics.payoff_ratio || (metrics.avg_win && metrics.avg_loss ? Math.abs(metrics.avg_win / metrics.avg_loss) : 0);
    setValue('rr-payoff', payoff);
    setValue('rr-payoff-long', metrics.long_payoff_ratio || 0);
    setValue('rr-payoff-short', metrics.short_payoff_ratio || 0);

    // Max Consecutive Wins/Losses - use integer values
    const setIntValue = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = value !== null && value !== undefined ? value : '--';
        el.className = 'tv-value-neutral';
    };
    setIntValue('rr-max-consec-wins', metrics.max_consecutive_wins);
    setIntValue('rr-max-consec-wins-long', metrics.long_max_consec_wins);
    setIntValue('rr-max-consec-wins-short', metrics.short_max_consec_wins);
    setIntValue('rr-max-consec-losses', metrics.max_consecutive_losses);
    setIntValue('rr-max-consec-losses-long', metrics.long_max_consec_losses);
    setIntValue('rr-max-consec-losses-short', metrics.short_max_consec_losses);
}

// Update Trades List Tab (Tab 5) - TradingView Style
function updateTVTradesListTab(trades, config) {
    const tbody = document.getElementById('tvTradesListBody');
    const countEl = document.getElementById('tvTradesCount');

    if (!tbody) return;

    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#8b949e;padding:2rem;">Нет сделок для отображения</td></tr>';
        if (countEl) countEl.textContent = '0';
        return;
    }

    if (countEl) countEl.textContent = trades.length;

    const initialCapital = config?.initial_capital || 10000;

    // Helper to detect Long trades
    const isLongTrade = (t) => {
        if (t.direction === 'long' || t.direction === 'Long') return true;
        if (t.side === 'long' || t.side === 'Long' || t.side === 'Buy' || t.side === 'buy') return true;
        if (t.type === 'Длинная' || t.type === 'long') return true;
        return false;
    };

    // Format date like TradingView: "Nov 17, 2025, 21:15"
    const formatDate = (dateStr) => {
        if (!dateStr) return '--';
        const d = new Date(dateStr);
        return d.toLocaleString('en-US', {
            month: 'short',
            day: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).replace(',', '');
    };

    // Calculate cumulative P&L in reverse order first
    let runningPnL = 0;
    const cumulativePnLs = [];
    for (let i = 0; i < trades.length; i++) {
        runningPnL += (trades[i].pnl || 0);
        cumulativePnLs.push(runningPnL);
    }

    // Build rows - TradingView shows newest trades at top, with Entry below Exit
    // Each trade has 2 rows: Exit row (with all metrics) and Entry row (just entry info)
    const rows = [];

    // Reverse to show newest first
    for (let i = trades.length - 1; i >= 0; i--) {
        const trade = trades[i];
        const tradeNum = i + 1;
        const pnl = trade.pnl || 0;
        const pnlPct = trade.return_pct || trade.pnl_pct || 0;
        const cumulativePnL = cumulativePnLs[i];
        const cumulativePnLPct = (cumulativePnL / initialCapital) * 100;

        const isLong = isLongTrade(trade);
        const typeText = isLong ? 'Long' : 'Short';
        const typeClass = isLong ? 'tv-trade-long' : 'tv-trade-short';

        // Signal text
        const exitSignal = trade.exit_reason || trade.exit_signal || (isLong ? 'Long SL/TP' : 'Short SL/TP');
        const entrySignal = isLong ? 'Long' : 'Short';

        // Position size
        const positionValue = (trade.size || 0) * (trade.entry_price || 0);
        const positionDisplay = positionValue >= 1000
            ? `${(positionValue / 1000).toFixed(2)}K USD`
            : `${positionValue.toFixed(2)} USD`;

        // MFE/MAE
        const mfe = trade.mfe || trade.mfe_value || 0;
        const mfePct = trade.mfe_pct || 0;
        const mae = trade.mae || trade.mae_value || 0;
        const maePct = trade.mae_pct || 0;

        // Exit row (main row with all metrics)
        rows.push(`
            <tr class="tv-trade-exit-row">
                <td rowspan="2" class="tv-trade-num-cell">
                    <span class="tv-trade-number">${tradeNum}</span>
                    <span class="${typeClass}">${typeText}</span>
                </td>
                <td class="tv-trade-type-cell">Exit</td>
                <td>${formatDate(trade.exit_time)}</td>
                <td>${exitSignal}</td>
                <td>${(trade.exit_price || 0).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} <small>USD</small></td>
                <td>
                    <div>${trade.size?.toFixed(2) || '0.01'}</div>
                    <div class="tv-trade-secondary">${positionDisplay}</div>
                </td>
                <td class="${pnl >= 0 ? 'tv-value-positive' : 'tv-value-negative'}">
                    <div>${pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} <small>USD</small></div>
                    <div class="tv-trade-secondary">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</div>
                </td>
                <td class="tv-value-neutral">
                    <div>${mfe.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} <small>USD</small></div>
                    <div class="tv-trade-secondary">${mfePct.toFixed(2)}%</div>
                </td>
                <td class="${mae < 0 ? 'tv-value-negative' : 'tv-value-neutral'}">
                    <div>${mae.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} <small>USD</small></div>
                    <div class="tv-trade-secondary">${maePct.toFixed(2)}%</div>
                </td>
                <td class="${cumulativePnL >= 0 ? 'tv-value-positive' : 'tv-value-negative'}">
                    <div>${cumulativePnL.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} <small>USD</small></div>
                    <div class="tv-trade-secondary">${cumulativePnLPct.toFixed(2)}%</div>
                </td>
            </tr>
            <tr class="tv-trade-entry-row">
                <td class="tv-trade-type-cell">Entry</td>
                <td>${formatDate(trade.entry_time)}</td>
                <td>${entrySignal}</td>
                <td>${(trade.entry_price || 0).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} <small>USD</small></td>
                <td colspan="5"></td>
            </tr>
        `);
    }

    tbody.innerHTML = rows.join('');
}

// Update Report Header
function updateTVReportHeader(backtest) {
    const strategyName = document.getElementById('tvReportStrategyName');
    const dateRange = document.getElementById('tvReportDateRange');

    if (strategyName && backtest?.config) {
        strategyName.textContent = `Стратегия ${backtest.config.strategy_type || 'Unknown'} Отчёт`;
    }

    if (dateRange && backtest?.config) {
        const start = backtest.config.start_date ? new Date(backtest.config.start_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '--';
        const end = backtest.config.end_date ? new Date(backtest.config.end_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '--';
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
                { title: 'Side', field: 'side', width: 80,
                    formatter: (cell) => {
                        const val = cell.getValue();
                        const color = val === 'long' ? '#3fb950' : '#f85149';
                        return `<span style="color: ${color}">${val?.toUpperCase()}</span>`;
                    }
                },
                { title: 'Entry Price', field: 'entry_price', formatter: 'money', formatterParams: { precision: 2 } },
                { title: 'Exit Price', field: 'exit_price', formatter: 'money', formatterParams: { precision: 2 } },
                { title: 'Size', field: 'size', formatter: 'money', formatterParams: { precision: 4 } },
                { title: 'P&L', field: 'pnl',
                    formatter: (cell) => {
                        const val = cell.getValue();
                        const color = val >= 0 ? '#3fb950' : '#f85149';
                        return `<span style="color: ${color}">$${val?.toFixed(2)}</span>`;
                    }
                },
                { title: 'Return %', field: 'return_pct',
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

    document.getElementById('btEndDate').value = endDate.toISOString().split('T')[0];
    document.getElementById('btStartDate').value = startDate.toISOString().split('T')[0];
}

function setupFilters() {
    ['filterStrategy', 'filterSymbol', 'filterPnL', 'filterSearch'].forEach(id => {
        document.getElementById(id).addEventListener('change', applyFilters);
    });
    document.getElementById('filterSearch').addEventListener('input', applyFilters);
}

// ============================
// Data Loading
// ============================
async function loadBacktestResults() {
    console.log('[loadBacktestResults] Loading backtests...');

    // PRIORITY: Check URL for specific backtest ID first (from optimization/backtest redirect)
    const urlParams = new URLSearchParams(window.location.search);
    const targetId = urlParams.get('id');

    if (targetId) {
        console.log('[loadBacktestResults] URL contains targetId:', targetId);
        try {
            // Load the specific backtest directly - don't depend on list endpoint
            const directResponse = await fetch(`${API_BASE}/backtests/${targetId}`);
            if (directResponse.ok) {
                const backtestData = await directResponse.json();
                console.log('[loadBacktestResults] Loaded backtest directly by ID:', targetId);

                // Initialize UI with this single backtest
                allResults = [{
                    ...backtestData,
                    backtest_id: backtestData.id || targetId,
                    symbol: backtestData.config?.symbol || 'Unknown',
                    interval: backtestData.config?.interval || '--',
                    strategy_type: backtestData.config?.strategy_type || 'Unknown',
                    metrics: backtestData.metrics || {}
                }];

                document.getElementById('resultsCount').textContent = '1';
                document.getElementById('emptyState').classList.add('d-none');
                renderResultsList(allResults);
                selectBacktest(targetId);

                // Try to load full list in background (optional, may fail)
                loadBacktestListBackground();
                return;
            } else {
                console.warn('[loadBacktestResults] Direct load failed, falling back to list');
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
        const response = await fetch(`${API_BASE}/backtests/?limit=100`);
        if (!response.ok) {
            console.warn('[loadBacktestListBackground] List endpoint returned', response.status);
            return;
        }
        const data = await response.json();

        // Merge with existing results (avoid duplicates)
        const existingIds = new Set(allResults.map(r => r.backtest_id));
        const newResults = (data.items || [])
            .filter(item => !existingIds.has(item.id) && !existingIds.has(item.backtest_id))
            .filter(item => !recentlyDeletedIds.has(item.id) && !recentlyDeletedIds.has(item.backtest_id))
            .map(item => ({
                ...item,
                backtest_id: item.id || item.backtest_id,
                symbol: item.symbol || item.config?.symbol || 'Unknown',
                interval: item.interval || item.config?.interval || '--',
                strategy_type: item.strategy_type || item.config?.strategy_type || 'Unknown'
            }));

        if (newResults.length > 0) {
            allResults = [...allResults, ...newResults];
            document.getElementById('resultsCount').textContent = allResults.length;
            renderResultsList(allResults);
            populateFilters();
        }
    } catch (err) {
        console.warn('[loadBacktestListBackground] Background list load failed:', err);
    }
}

// Original list loading logic
async function loadBacktestListFromAPI() {
    try {
        const response = await fetch(`${API_BASE}/backtests/?limit=100`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();

        // Normalize API response - map nested config fields to top level
        // Filter out recently deleted IDs to prevent "ghost" items from backend sync delay
        allResults = (data.items || [])
            .filter(item => !recentlyDeletedIds.has(item.id) && !recentlyDeletedIds.has(item.backtest_id))
            .map(item => ({
                ...item,
                backtest_id: item.id || item.backtest_id,
                symbol: item.symbol || item.config?.symbol || 'Unknown',
                interval: item.interval || item.config?.interval || '--',
                strategy_type: item.strategy_type || item.config?.strategy_type || 'Unknown'
            }));
        console.log('[loadBacktestListFromAPI] Loaded', allResults.length, 'backtests');
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

async function deleteBacktest(backtestId) {
    if (!confirm('Удалить этот бэктест?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/backtests/${backtestId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('Р‘СЌРєС‚РµСЃС‚ СѓРґР°Р»РµРЅ', 'success');

            // Add to recently deleted blacklist to prevent ghost items on refresh
            recentlyDeletedIds.add(backtestId);
            // Auto-remove from blacklist after 30 seconds (backend should be synced by then)
            setTimeout(() => recentlyDeletedIds.delete(backtestId), 30000);

            // Optimistic UI update: immediately remove from local array
            // This prevents the "ghost" item from appearing due to backend sync delay
            allResults = allResults.filter(r => r.backtest_id !== backtestId);

            // If we deleted the currently selected backtest, clear selection
            if (currentBacktest && currentBacktest.backtest_id === backtestId) {
                currentBacktest = null;
                // Clear charts and show empty state
                if (equityChart) {
                    equityChart.data.labels = [];
                    equityChart.data.datasets.forEach(ds => ds.data = []);
                    equityChart.update('none');
                }
            }

            // Re-render the list with updated local data
            renderResultsList(allResults);

            // If there are remaining results, select the first one
            if (allResults.length > 0 && !currentBacktest) {
                selectBacktest(allResults[0].backtest_id);
            }

            // Background refresh from server (delayed to allow backend sync)
            // This ensures data consistency but UI is already updated optimistically
            // Using 5s delay because backend may take a few seconds to propagate deletion
            setTimeout(() => {
                loadBacktestResults().catch(err => {
                    console.warn('Background refresh failed:', err);
                });
            }, 5000);
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
        const strategies = Array.isArray(data) ? data : (data.items || []);

        const select = document.getElementById('btStrategy');
        if (!select) return;

        strategies.forEach(s => {
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
    const strategies = [...new Set(allResults.map(r => r.strategy_type))];
    const symbols = [...new Set(allResults.map(r => r.symbol))];

    const strategySelect = document.getElementById('filterStrategy');
    strategies.forEach(s => {
        const option = document.createElement('option');
        option.value = s;
        option.textContent = s;
        strategySelect.appendChild(option);
    });

    const symbolSelect = document.getElementById('filterSymbol');
    symbols.forEach(s => {
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
    container.innerHTML = results.map(r => {
        const isProfitable = (r.metrics?.total_return || 0) >= 0;
        const isSelected = currentBacktest?.backtest_id === r.backtest_id;
        const isCompareSelected = selectedForCompare.includes(r.backtest_id);

        // Get direction from config or parameters (DCA strategies store in strategy_params._direction)
        const direction = r.config?.direction || r.config?.strategy_params?._direction || r.direction || 'both';
        let directionBadge = '';
        if (direction === 'long') {
            directionBadge = '<span class="direction-badge direction-long">L</span>';
        } else if (direction === 'short') {
            directionBadge = '<span class="direction-badge direction-short">S</span>';
        } else {
            directionBadge = '<span class="direction-badge direction-both">L&S</span>';
        }

        return `
                    <div class="result-item ${isSelected ? 'selected' : ''}" 
                         data-id="${r.backtest_id}">
                        ${compareMode ? `
                            <input type="checkbox" class="form-check-input me-2" 
                                   ${isCompareSelected ? 'checked' : ''}
                                   onclick="toggleCompareSelect(event, '${r.backtest_id}')">
                        ` : ''}
                        <div class="result-content" onclick="selectBacktest('${r.backtest_id}')">
                            <div class="result-row">
                                <span class="result-pnl-value ${isProfitable ? 'text-success' : 'text-danger'}">
                                    ${isProfitable ? '+' : ''}${(r.metrics?.total_return || 0).toFixed(2)}%
                                </span>
                                ${directionBadge}
                                <span class="result-trades">${r.metrics?.total_trades || 0} trades</span>
                            </div>
                            <div class="result-meta">
                                ${r.symbol} • ${r.interval}
                            </div>
                        </div>
                        <button class="btn btn-sm delete-btn" 
                                onclick="event.stopPropagation(); deleteBacktest('${r.backtest_id}')"
                                title="Удалить">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                `;
    }).join('');
}

async function selectBacktest(backtestId) {
    try {
        // Mark as selected in list
        document.querySelectorAll('.result-item').forEach(item => {
            item.classList.toggle('selected', item.dataset.id === backtestId);
        });

        // Fetch full details
        const response = await fetch(`${API_BASE}/backtests/${backtestId}`);
        currentBacktest = await response.json();

        // Update TradingView style tabs
        updateTVReportHeader(currentBacktest);
        updateTVSummaryCards(currentBacktest.metrics);
        updateTVDynamicsTab(currentBacktest.metrics, currentBacktest.config, currentBacktest.trades, currentBacktest.equity_curve);
        updateTVTradeAnalysisTab(currentBacktest.metrics, currentBacktest.config, currentBacktest.trades);
        updateTVRiskReturnTab(currentBacktest.metrics, currentBacktest.trades, currentBacktest.config);
        updateTVTradesListTab(currentBacktest.trades, currentBacktest.config);

        // Update charts
        updateCharts(currentBacktest);

        // Update legacy metrics (for backward compatibility)
        updateMetrics(currentBacktest.metrics);
        updateAIAnalysis(currentBacktest);

        // Enable AI buttons
        const btnAI = document.getElementById('btnAIAnalysis');
        if (btnAI) btnAI.disabled = false;

        // Dispatch backtestLoaded event for AI integration
        window.dispatchEvent(new CustomEvent('backtestLoaded', { detail: currentBacktest }));
        console.log('[selectBacktest] Dispatched backtestLoaded event for AI Analysis');

    } catch (error) {
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

        if (dollarValue !== null && dollarValue !== undefined &&
                    percentValue !== null && percentValue !== undefined) {
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
    setDualMetric('metricDrawdown', -(metrics.max_drawdown_value || 0), -(metrics.max_drawdown || 0), 0);
    setDualMetric('metricNetProfit', metrics.net_profit || 0, metrics.net_profit_pct || 0, 0);
    setDualMetric('metricGrossProfit', metrics.gross_profit || 0, metrics.gross_profit_pct || 0, 0);
    setDualMetric('metricGrossLoss', -(metrics.gross_loss || 0), -(metrics.gross_loss_pct || 0), 0);
    setDualMetric('metricAvgWin', metrics.avg_win_value || 0, metrics.avg_win || 0, 0);
    setDualMetric('metricAvgLoss', -(metrics.avg_loss_value || 0), metrics.avg_loss || 0, 0);
    setDualMetric('metricLargestWin', metrics.largest_win_value || 0, metrics.largest_win || 0, 0);
    setDualMetric('metricLargestLoss', -(metrics.largest_loss_value || 0), metrics.largest_loss || 0, 0);

    // Additional TradingView metrics
    setMetric('metricAvgBars', metrics.avg_bars_in_trade, 'ratio', 0);
    setMetric('metricRecoveryFactor', metrics.recovery_factor, 'ratio', 1);
    setMetric('metricExpectancy', metrics.expectancy, 'ratio', 0);
    setMetric('metricSortino', metrics.sortino_ratio, 'ratio', 1);
    setMetric('metricCalmar', metrics.calmar_ratio, 'ratio', 1);
    setMetric('metricMaxConsecWins', metrics.max_consecutive_wins, 'number', 0);
    setMetric('metricMaxConsecLosses', metrics.max_consecutive_losses, 'number', 0);
}

// Downsample large arrays to improve chart performance
// Uses LTTB (Largest Triangle Three Buckets) simplified algorithm
function downsampleData(data, targetLength) {
    if (!data || data.length <= targetLength) return data;

    const step = data.length / targetLength;
    const sampled = [];

    // Always keep first point
    sampled.push(data[0]);

    for (let i = 1; i < targetLength - 1; i++) {
        const start = Math.floor(i * step);
        const end = Math.floor((i + 1) * step);

        // Find point with max value in this bucket (preserves peaks/valleys)
        let maxIdx = start;
        let maxVal = Math.abs(data[start]?.equity ?? data[start] ?? 0);
        for (let j = start + 1; j < end && j < data.length; j++) {
            const val = Math.abs(data[j]?.equity ?? data[j] ?? 0);
            if (val > maxVal) {
                maxVal = val;
                maxIdx = j;
            }
        }
        sampled.push(data[maxIdx]);
    }

    // Always keep last point
    sampled.push(data[data.length - 1]);

    return sampled;
}

// Binary search to find closest timestamp index
function findClosestIndex(sortedData, targetTime, getTime) {
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

function updateCharts(backtest) {
    console.log('[updateCharts] called with backtest:', backtest?.id || backtest?.backtest_id);
    if (!backtest) return;

    // Debug: log backtest structure
    console.log('[updateCharts] backtest keys:', Object.keys(backtest));
    console.log('[updateCharts] equity_curve exists:', !!backtest.equity_curve);
    console.log('[updateCharts] trades count:', backtest.trades?.length || 0);

    // Check if charts are initialized and canvas still exists
    if (!equityChart || !equityChart.canvas) {
        console.warn('[updateCharts] equityChart not initialized or canvas missing');
        return;
    }

    // Equity Chart
    if (backtest.equity_curve) {
        console.log('[updateCharts] equity_curve found, type:', Array.isArray(backtest.equity_curve) ? 'array' : 'object');


        // Short date format for chart labels (like TradingView)
        const formatShortDate = (ts) => {
            if (!ts) return '';
            const d = new Date(ts);
            return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).replace('.', '');
        };

        // Support both formats:
        // 1. Array of objects: [{timestamp, equity, drawdown}, ...]
        // 2. Object with arrays: {timestamps: [], equity: [], drawdown: []}
        let equityData = [];
        let rawEquityData = []; // Keep original for trade matching

        if (Array.isArray(backtest.equity_curve)) {
            // New format from optimization API
            rawEquityData = backtest.equity_curve;
        } else {
            // Legacy format - convert to array format for tooltip
            const timestamps = backtest.equity_curve.timestamps || [];
            const equities = backtest.equity_curve.equity || [];
            const drawdowns = backtest.equity_curve.drawdown || [];
            rawEquityData = timestamps.map((t, i) => ({
                timestamp: t,
                equity: equities[i],
                drawdown: drawdowns[i] || 0
            }));
        }

        // Downsample for chart display if too many points (target ~2000 points max)
        const MAX_CHART_POINTS = 2000;
        if (rawEquityData.length > MAX_CHART_POINTS) {
            console.log(`[updateCharts] Downsampling from ${rawEquityData.length} to ${MAX_CHART_POINTS} points`);
            equityData = downsampleData(rawEquityData, MAX_CHART_POINTS);
        } else {
            equityData = rawEquityData;
        }

        const labels = equityData.map(p => formatShortDate(p.timestamp));
        const values = equityData.map(p => p.equity);
        const drawdown = equityData.map(p => p.drawdown || 0);

        console.log('[updateCharts] labels:', labels?.length, 'values:', values?.length);
        console.log('[updateCharts] values sample:', values?.slice(0, 5), '...', values?.slice(-3));

        try {
            if (equityChart && equityChart.canvas) {
                // Store data for tooltip access
                equityChart._equityData = equityData;
                equityChart.data.labels = labels;

                // Convert equity values to P&L (change from initial capital)
                const initialEquity = values[0] || 10000;
                equityChart._initialCapital = initialEquity;  // Store for mode switching
                const pnlValues = values.map(v => v - initialEquity);

                console.log('[updateCharts] initialEquity:', initialEquity, 'pnlValues sample:', pnlValues?.slice(0, 3), '...', pnlValues?.slice(-3));

                // Dataset 0: Strategy P&L line (green)
                equityChart.data.datasets[0].data = pnlValues;

                // Dataset 1: Buy & Hold P&L line (red)
                // Priority: 1. bh_equity from API, 2. klines data, 3. estimate from metrics
                let buyHoldPnL;
                const bhEquity = Array.isArray(backtest.equity_curve)
                    ? null
                    : (backtest.equity_curve?.bh_equity || []);

                if (bhEquity && bhEquity.length > 0) {
                    // Use actual Buy & Hold equity from backend
                    const bhInitial = bhEquity[0] || initialEquity;
                    buyHoldPnL = bhEquity.map(e => e - bhInitial);
                } else if (backtest.klines && backtest.klines.length > 0) {
                    const firstPrice = backtest.klines[0].close;
                    buyHoldPnL = backtest.klines.map(k => {
                        const priceChange = (k.close - firstPrice) / firstPrice;
                        return initialEquity * priceChange;
                    });
                } else if (backtest.metrics?.buy_hold_return_pct !== undefined) {
                    const bhReturn = backtest.metrics.buy_hold_return_pct / 100;
                    buyHoldPnL = values.map((_, i) => {
                        const progress = i / (values.length - 1 || 1);
                        return initialEquity * bhReturn * progress;
                    });
                } else {
                    buyHoldPnL = values.map(() => 0);
                }
                equityChart.data.datasets[1].data = buyHoldPnL;

                // Build trade map for tooltip AND trade ranges for MFE/MAE bars
                const tradeMap = {};
                const tradeRanges = []; // Array of {entryIdx, exitIdx, mfe, mae}
                if (backtest.trades && backtest.trades.length > 0) {
                    let cumulativePnL = 0;

                    // Use binary search for O(n log n) instead of O(nВІ)
                    const getTimestamp = (point) => point.timestamp;

                    backtest.trades.forEach((trade, tradeIdx) => {
                        const entryTime = trade.entry_time;
                        const exitTime = trade.exit_time;
                        const tradePnL = Number(trade.pnl || 0);
                        cumulativePnL += tradePnL;

                        // Find entry and exit indices using binary search
                        const entryIdx = findClosestIndex(equityData, entryTime, getTimestamp);
                        const exitIdx = findClosestIndex(equityData, exitTime, getTimestamp);

                        if (exitIdx >= 0) {
                            tradeMap[exitIdx] = {
                                tradeNum: tradeIdx + 1,
                                side: trade.side || 'long',
                                pnl: tradePnL,
                                cumulativePnL,
                                // MFE/MAE: absolute values (USDT) and percentages
                                mfe_value: trade.mfe ?? trade.mfe_value ?? null,
                                mae_value: trade.mae ?? trade.mae_value ?? null,
                                mfe_pct: trade.mfe_pct ?? null,
                                mae_pct: trade.mae_pct ?? null,
                                exitTime: exitTime
                            };
                        }

                        // Store trade range for MFE/MAE bars
                        if (entryIdx >= 0 && exitIdx >= 0) {
                            tradeRanges.push({
                                entryIdx: Math.min(entryIdx, exitIdx),
                                exitIdx: Math.max(entryIdx, exitIdx),
                                mfe: trade.mfe ?? trade.mfe_value ?? 0,
                                mae: trade.mae ?? trade.mae_value ?? 0
                            });
                        }
                    });
                }
                equityChart._tradeMap = tradeMap;
                equityChart._tradeRanges = tradeRanges;

                // Store original data for mode switching
                originalEquityData = [...pnlValues];
                originalBuyHoldData = [...buyHoldPnL];

                // Trade Excursion Bars are now drawn by tradeExcursionBarsPlugin
                // using _tradeRanges and _tradeMap stored above

                equityChart.update('none');
                console.log('[updateCharts] equityChart updated with P&L values');

                // Update current value badge in header
                const lastPnL = pnlValues[pnlValues.length - 1] || 0;
                const valueBadge = document.getElementById('tvEquityCurrentValue');
                if (valueBadge) {
                    const sign = lastPnL >= 0 ? '+' : '';
                    valueBadge.textContent = `${sign}$${Math.abs(lastPnL).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    valueBadge.classList.toggle('negative', lastPnL < 0);
                }
            }

            // Drawdown Chart (separate)
            if (drawdownChart && drawdownChart.canvas) {
                drawdownChart.data.labels = labels;
                drawdownChart.data.datasets[0].data = drawdown;
                drawdownChart.update('none');
            }
        } catch (chartError) {
            console.warn('[updateCharts] Chart update error:', chartError.message);
        }
    }

    // Returns Distribution
    if (backtest.trades && backtest.trades.length > 0 && returnsChart && returnsChart.canvas) {
        try {
            // Support both return_pct and pnl_pct fields
            const returns = backtest.trades.map(t => t.return_pct || t.pnl_pct || 0);
            const colors = returns.map(r => r >= 0 ? '#3fb950' : '#f85149');

            returnsChart.data.labels = returns.map((_, i) => `Trade ${i + 1}`);
            returnsChart.data.datasets[0].data = returns;
            returnsChart.data.datasets[0].backgroundColor = colors;
            returnsChart.update('none');
        } catch (e) {
            console.warn('[updateCharts] returnsChart error:', e.message);
        }
    }

    // Monthly P&L (simplified)
    if (backtest.trades && backtest.trades.length > 0 && monthlyChart && monthlyChart.canvas) {
        try {
            const monthlyPnL = {};
            backtest.trades.forEach(t => {
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
            const values = months.map(m => monthlyPnL[m]);
            const colors = values.map(v => v >= 0 ? '#3fb950' : '#f85149');

            monthlyChart.data.labels = months;
            monthlyChart.data.datasets[0].data = values;
            monthlyChart.data.datasets[0].backgroundColor = colors;
            monthlyChart.update('none');
        } catch (e) {
            console.warn('[updateCharts] monthlyChart error:', e.message);
        }
    }

    // Trade Distribution Chart (in Trade Analysis tab)
    if (backtest.trades && backtest.trades.length > 0 && tradeDistributionChart && tradeDistributionChart.canvas) {
        try {
            const leverage = backtest.config?.leverage || backtest.parameters?.leverage || 10;
            const returns = backtest.trades.map(t => {
                if (t.return_pct !== undefined && t.return_pct !== null) return t.return_pct;
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
            returns.forEach(r => {
                const binKey = (Math.floor(r / binSize) * binSize).toFixed(1);
                if (bins[binKey] !== undefined) bins[binKey]++;
            });

            const labels = Object.keys(bins).map(k => `${k}%`);
            const binKeys = Object.keys(bins);
            const profits = returns.filter(r => r > 0);
            const losses = returns.filter(r => r < 0);
            const avgProfit = profits.length > 0 ? (profits.reduce((a, b) => a + b, 0) / profits.length) : 0;
            const avgLoss = losses.length > 0 ? (losses.reduce((a, b) => a + b, 0) / losses.length) : 0;

            // Find bin indices for average lines
            const avgLossBinIdx = binKeys.findIndex(k => parseFloat(k) >= avgLoss) - 0.5;
            const avgProfitBinIdx = binKeys.findIndex(k => parseFloat(k) >= avgProfit) - 0.5;

            tradeDistributionChart.data.labels = labels;
            tradeDistributionChart.data.datasets = [{
                label: 'Убыток',
                data: binKeys.map(k => parseFloat(k) < 0 ? bins[k] : 0),
                backgroundColor: '#ef5350',
                barPercentage: 0.5,
                categoryPercentage: 0.95
            }, {
                label: 'Прибыль',
                data: binKeys.map(k => parseFloat(k) >= 0 ? bins[k] : 0),
                backgroundColor: '#26a69a',
                barPercentage: 0.5,
                categoryPercentage: 0.95
            }];

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
                            display: false
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
                            display: false
                        }
                    }
                }
            };

            tradeDistributionChart.options.plugins.legend.labels.color = '#ffffff';
            tradeDistributionChart.options.plugins.legend.labels.font = { size: 12 };
            tradeDistributionChart.options.plugins.legend.labels.generateLabels = () => [
                { text: 'Убыток', fillStyle: '#ef5350', strokeStyle: '#ef5350', pointStyle: 'circle', hidden: false, fontColor: '#ffffff' },
                { text: 'Прибыль', fillStyle: '#26a69a', strokeStyle: '#26a69a', pointStyle: 'circle', hidden: false, fontColor: '#ffffff' },
                { text: `Средний убыток  ${avgLoss.toFixed(2)}%`, fillStyle: 'transparent', strokeStyle: '#ef5350', lineWidth: 2, lineDash: [6, 4], pointStyle: 'line', hidden: false, fontColor: '#ffffff' },
                { text: `Средняя прибыль  ${avgProfit.toFixed(2)}%`, fillStyle: 'transparent', strokeStyle: '#26a69a', lineWidth: 2, lineDash: [6, 4], pointStyle: 'line', hidden: false, fontColor: '#ffffff' }
            ];
            tradeDistributionChart.update('none');
        } catch (e) {
            console.warn('[updateCharts] tradeDistributionChart error:', e.message);
        }
    }

    // Win/Loss Donut Chart (in Trade Analysis tab)
    if (backtest.trades && backtest.trades.length > 0 && winLossDonutChart && winLossDonutChart.canvas) {
        try {
            let wins = 0, losses = 0, breakeven = 0;
            backtest.trades.forEach(t => {
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

            const getUnit = (n) => n === 1 ? 'сделка' : (n >= 2 && n <= 4 ? 'сделки' : 'сделок');

            const legendWins = document.getElementById('legend-wins');
            const legendWinsPct = document.getElementById('legend-wins-pct');
            const legendLosses = document.getElementById('legend-losses');
            const legendLossesPct = document.getElementById('legend-losses-pct');
            const legendBreakeven = document.getElementById('legend-breakeven');
            const legendBreakevenPct = document.getElementById('legend-breakeven-pct');

            if (legendWins) legendWins.textContent = `${wins} ${getUnit(wins)}`;
            if (legendWinsPct) legendWinsPct.textContent = `${winPct}%`;
            if (legendLosses) legendLosses.textContent = `${losses} ${getUnit(losses)}`;
            if (legendLossesPct) legendLossesPct.textContent = `${lossPct}%`;
            if (legendBreakeven) legendBreakeven.textContent = `${breakeven} ${getUnit(breakeven)}`;
            if (legendBreakevenPct) legendBreakevenPct.textContent = `${bePct}%`;

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
            const openPnL = m.open_pnl || 0;  // Get from metrics if available

            // If commission is 0 but we have trades, recalculate from trades
            if (commission === 0 && backtest.trades && backtest.trades.length > 0) {
                commission = backtest.trades.reduce((sum, t) => {
                    return sum + Math.abs(t.fees || t.fee || t.commission || 0);
                }, 0);
                console.log(`[Waterfall] Recalculated commission from trades: ${commission.toFixed(2)}`);
            }

            // Build data dynamically - skip Open P&L if zero
            const hasOpenPnL = Math.abs(openPnL) > 0.01;

            // Build labels and data based on whether Open P&L exists
            let labels, datasets;

            if (hasOpenPnL) {
                // 5 columns with Open P&L - TradingView waterfall using FLOATING BARS
                labels = ['Итого прибыль', 'Открытые ПР/УБ', 'Итого убыток', 'Комиссия', 'Общие ПР/УБ'];

                // Calculate waterfall levels
                const level0 = 0;
                const level1 = grossProfit;
                const level2 = level1 + (openPnL > 0 ? openPnL : -Math.abs(openPnL));
                const level3 = level2 - grossLoss;
                const level4 = level3 - commission;

                datasets = [{
                    label: 'РС‚РѕРіРѕ РїСЂРёР±С‹Р»СЊ',
                    data: [[level0, level1], null, null, null, null],
                    backgroundColor: '#26a69a',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Открытые ПР/УБ',
                    data: [null, openPnL >= 0 ? [level1, level2] : [level2, level1], null, null, null],
                    backgroundColor: openPnL >= 0 ? '#4dd0e1' : '#ff8a65',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'РС‚РѕРіРѕ СѓР±С‹С‚РѕРє',
                    data: [null, null, [level3, level2], null, null],
                    backgroundColor: '#ef5350',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Комиссия',
                    data: [null, null, null, [level4, level3], null],
                    backgroundColor: '#ffa726',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Общие ПР/УБ',
                    data: [null, null, null, null, netProfit >= 0 ? [level0, netProfit] : [netProfit, level0]],
                    backgroundColor: netProfit >= 0 ? '#42a5f5' : '#ff7043',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }];
            } else {
                // 4 columns without Open P&L - TradingView waterfall using FLOATING BARS
                // Each bar is [bottom, top] to create hanging effect
                labels = ['Итого прибыль', 'Итого убыток', 'Комиссия', 'Общие ПР/УБ'];

                // Calculate waterfall levels (like a waterfall flowing down)
                const level0 = 0;  // Start
                const level1 = grossProfit;  // After profit (top of green bar)
                const level2 = level1 - grossLoss;  // After loss (bottom of red bar)
                const level3 = level2 - commission;  // After commission

                // Each dataset has data as [bottom, top] arrays for floating bars
                datasets = [{
                    label: 'Итого прибыль',
                    data: [
                        [level0, level1],  // Bar 0: Profit from 0 UP to grossProfit
                        null,
                        null,
                        null
                    ],
                    backgroundColor: '#26a69a',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Итого убыток',
                    data: [
                        null,
                        [level2, level1],  // Bar 1: Loss HANGS from level1 DOWN to level2
                        null,
                        null
                    ],
                    backgroundColor: '#ef5350',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Комиссия',
                    data: [
                        null,
                        null,
                        [level3, level2],  // Bar 2: Commission HANGS from level2 DOWN to level3
                        null
                    ],
                    backgroundColor: '#ffa726',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }, {
                    label: 'Общие ПР/УБ',
                    data: [
                        null,
                        null,
                        null,
                        netProfit >= 0 ? [level0, netProfit] : [netProfit, level0]  // Bar 3: Net from 0
                    ],
                    backgroundColor: netProfit >= 0 ? '#42a5f5' : '#ff7043',
                    barPercentage: 0.5,
                    categoryPercentage: 0.95
                }];
            }

            waterfallChart.data.labels = labels;
            waterfallChart.data.datasets = datasets;

            // Disable stacking and grouping - we use floating bars, one per category
            waterfallChart.options.scales.x.stacked = false;
            waterfallChart.options.scales.y.stacked = false;

            // CRITICAL: Disable grouping so bars don't divide width by number of datasets
            if (!waterfallChart.options.datasets) waterfallChart.options.datasets = {};
            if (!waterfallChart.options.datasets.bar) waterfallChart.options.datasets.bar = {};
            waterfallChart.options.datasets.bar.grouped = false;

            // Legend: hide Open P&L if not present (no more _base to filter)
            waterfallChart.options.plugins.legend.display = true;
            waterfallChart.options.plugins.legend.labels.filter = (item) => hasOpenPnL || item.text !== 'Открытые ПР/УБ';

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
            const lossIdx = hasOpenPnL ? 2 : 1;  // Index of Loss column
            const commIdx = hasOpenPnL ? 3 : 2;  // Index of Commission column
            const netIdx = hasOpenPnL ? 4 : 3;   // Index of Net P&L column

            // Calculate correct line positions based on waterfall logic
            const profitTopLevel = grossProfit;  // Top of profit bar
            const lossBottomLevel = hasOpenPnL
                ? (grossProfit + (openPnL > 0 ? openPnL : 0) - (openPnL < 0 ? Math.abs(openPnL) : 0) - grossLoss)
                : (grossProfit - grossLoss);  // Bottom of loss bar
            const commBottomLevel = lossBottomLevel - commission;  // Bottom of commission bar

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

            const bhReturn = m.buy_hold_return || 0;
            const bhMin = m.buy_hold_min_pct || (bhReturn * 0.7);
            const bhMax = m.buy_hold_max_pct || (bhReturn * 1.3);

            const strategyReturn = m.net_profit_pct || m.total_return || ((m.net_profit || 0) / initialCapital * 100);
            let stratMin = strategyReturn * 0.7;
            let stratMax = strategyReturn * 1.3;

            if (backtest.equity_curve && backtest.equity_curve.length > 0) {
                const equityValues = backtest.equity_curve.map(e => e.equity || e.value || e);
                const minEquity = Math.min(...equityValues);
                const maxEquity = Math.max(...equityValues);
                stratMin = ((minEquity - initialCapital) / initialCapital) * 100;
                stratMax = ((maxEquity - initialCapital) / initialCapital) * 100;
            }

            benchmarkingChart.data.datasets = [{
                label: 'Min',
                data: [
                    [0, bhMin < 0 ? bhMin : 0],
                    [0, stratMin < 0 ? stratMin : 0]
                ],
                backgroundColor: 'rgba(239, 83, 80, 0.6)',
                barPercentage: 0.5
            }, {
                label: 'Диапазон',
                data: [
                    [Math.min(bhMin, 0), Math.max(bhMax, 0)],
                    [Math.min(stratMin, 0), Math.max(stratMax, 0)]
                ],
                backgroundColor: ['#ff9800', '#42a5f5'],
                barPercentage: 0.5
            }, {
                label: 'Текущ. цена',
                data: [
                    [bhReturn - 0.5, bhReturn + 0.5],
                    [strategyReturn - 0.5, strategyReturn + 0.5]
                ],
                backgroundColor: ['#8d6e63', '#26a69a'],
                barPercentage: 0.3
            }];

            benchmarkingChart.update('none');
        } catch (e) {
            console.warn('[updateCharts] benchmarkingChart error:', e.message);
        }
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
        content.textContent = 'Select a backtest result to get AI-powered analysis and recommendations.';
        return;
    }

    const m = backtest.metrics;
    const insights = [];

    // Generate quick insights
    if (m.total_return > 20) {
        insights.push('✅ Excellent returns! Strategy shows strong profitability.');
    } else if (m.total_return > 0) {
        insights.push('🔶 Positive returns, but there may be room for optimization.');
    } else {
        insights.push('⚠️ Negative returns. Consider adjusting strategy parameters.');
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
        insights.push('🔶 Consider reducing volatility for better risk-adjusted returns.');
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

    // Trigger chart resize after animation
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 350);
}
// Make available globally for onclick
window.toggleResultsPanel = toggleResultsPanel;

// Restore panel state on page load
document.addEventListener('DOMContentLoaded', function () {
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

    const filtered = allResults.filter(r => {
        if (strategy && r.strategy_type !== strategy) return false;
        if (symbol && r.symbol !== symbol) return false;
        if (pnl === 'profit' && (r.metrics?.total_return || 0) < 0) return false;
        if (pnl === 'loss' && (r.metrics?.total_return || 0) >= 0) return false;
        if (search && !JSON.stringify(r).toLowerCase().includes(search)) return false;
        return true;
    });

    renderResultsList(filtered);
}

function toggleCompareMode() {
    compareMode = !compareMode;
    selectedForCompare = [];

    const btn = document.getElementById('btnCompare');
    btn.classList.toggle('btn-primary', compareMode);
    btn.classList.toggle('btn-outline-secondary', !compareMode);
    btn.innerHTML = compareMode ?
        '<i class="bi bi-x-lg me-1"></i>Cancel Compare' :
        '<i class="bi bi-columns-gap me-1"></i>Compare Selected';

    renderResultsList(allResults);
}

function toggleCompareSelect(event, backtestId) {
    event.stopPropagation();

    if (selectedForCompare.includes(backtestId)) {
        selectedForCompare = selectedForCompare.filter(id => id !== backtestId);
    } else if (selectedForCompare.length < 3) {
        selectedForCompare.push(backtestId);
    }

    document.getElementById('btnCompare').disabled = selectedForCompare.length < 2;
    document.getElementById('btnAICompare').disabled = selectedForCompare.length < 2;
}

function showNewBacktestModal() {
    new bootstrap.Modal(document.getElementById('newBacktestModal')).show();
}

async function runBacktest() {
    const strategyId = document.getElementById('btStrategy').value;
    const symbol = document.getElementById('btSymbol').value;
    const interval = document.getElementById('btInterval').value;
    const capital = document.getElementById('btCapital').value;
    const startDate = document.getElementById('btStartDate').value;
    const endDate = document.getElementById('btEndDate').value;

    if (!strategyId) {
        showToast('Please select a strategy', 'error');
        return;
    }

    try {
        showToast('Running backtest...', 'info');

        const response = await fetch(`${API_BASE}/backtests/from-strategy/${strategyId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol,
                interval,
                initial_capital: parseFloat(capital),
                start_date: new Date(startDate).toISOString(),
                end_date: new Date(endDate).toISOString(),
                save_result: true
            })
        });

        if (!response.ok) throw new Error('Backtest failed');

        await response.json(); // Consume response
        bootstrap.Modal.getInstance(document.getElementById('newBacktestModal')).hide();

        showToast('Backtest completed successfully!', 'success');
        loadBacktestResults();

    } catch (error) {
        console.error('Backtest error:', error);
        showToast('Backtest failed: ' + error.message, 'error');
    }
}

async function requestAIAnalysis() {
    if (!currentBacktest) return;

    try {
        showToast('Generating AI analysis...', 'info');

        const response = await fetch(`${API_BASE}/agents/backtest/ai-analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify([currentBacktest])
        });

        const analysis = await response.json();

        document.getElementById('aiAnalysisContent').innerHTML = `
                    <strong>AI Recommendation:</strong><br>
                    ${analysis.recommendation || analysis.analysis || 'No detailed analysis available.'}
                `;

        showToast('AI analysis complete', 'success');

    } catch (error) {
        console.error('AI analysis failed:', error);
        showToast('AI analysis failed', 'error');
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
            selectedForCompare.map(id =>
                fetch(`${API_BASE}/backtests/${id}`).then(r => r.json())
            )
        );

        const response = await fetch(`${API_BASE}/agents/backtest/ai-analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(results)
        });

        const analysis = await response.json();

        document.getElementById('aiAnalysisContent').innerHTML = `
                    <strong>Comparison Result:</strong><br>
                    ${analysis.recommendation || analysis.comparison || 'Comparison complete.'}
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
        ['ID', 'Strategy', 'Symbol', 'Interval', 'Return %', 'Win Rate', 'Sharpe', 'Trades', 'Date'].join(','),
        ...allResults.map(r => [
            r.backtest_id,
            r.strategy_type,
            r.symbol,
            r.interval,
            r.metrics?.total_return?.toFixed(2) || 0,
            r.metrics?.win_rate?.toFixed(2) || 0,
            r.metrics?.sharpe_ratio?.toFixed(2) || 0,
            r.metrics?.total_trades || 0,
            r.config?.start_date || ''
        ].join(','))
    ].join('\n');

    downloadFile(csv, 'backtest_results.csv', 'text/csv');
}

function exportTrades() {
    if (!currentBacktest?.trades) {
        showToast('No trades to export', 'warning');
        return;
    }

    const csv = [
        ['#', 'Entry Time', 'Exit Time', 'Side', 'Entry Price', 'Exit Price', 'Size', 'P&L', 'Return %'].join(','),
        ...currentBacktest.trades.map((t, i) => [
            i + 1,
            t.entry_time,
            t.exit_time,
            t.side,
            t.entry_price,
            t.exit_price,
            t.size,
            t.pnl?.toFixed(2),
            t.return_pct?.toFixed(2)
        ].join(','))
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
    const date = new Date(dateStr);
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
    toast.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 250px;';
    toast.innerHTML = `
                <i class="bi bi-${type === 'error' ? 'x-circle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
                ${message}
            `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
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
    window.runBacktest = runBacktest;
    window.requestAIAnalysis = requestAIAnalysis;
    window.compareWithAI = compareWithAI;
    window.exportResults = exportResults;
    window.exportTrades = exportTrades;
    window.refreshData = refreshData;
    window.selectBacktest = selectBacktest;
    window.deleteBacktest = deleteBacktest;

    window.backtestresultsPage = {
        loadBacktestResults,
        selectBacktest,
        deleteBacktest,
        refreshData
    };
}
