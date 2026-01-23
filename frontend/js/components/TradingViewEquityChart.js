/**
 * 📊 TradingView-style Equity Chart Component
 *
 * Professional equity curve visualization matching TradingView's design:
 * - Main equity line with gradient fill
 * - Buy & Hold comparison line
 * - Trade excursions (run-up/drawdown bars)
 * - Profit/Loss period bars at bottom
 * - Interactive tooltips with detailed info
 * - Zoom and pan support
 *
 * @version 2.0.0
 * @date 2026-01-13
 */

class TradingViewEquityChart {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.data = null;

        // Default options matching TradingView style
        this.options = {
            showBuyHold: true,
            showTradeExcursions: false,
            displayMode: 'absolute', // 'absolute' or 'percent'
            height: 320,
            colors: {
                equity: '#26a69a',           // TradingView teal/green
                equityFill: 'rgba(38, 166, 154, 0.15)',
                equityGradientStart: 'rgba(38, 166, 154, 0.4)',
                equityGradientEnd: 'rgba(38, 166, 154, 0.02)',
                buyHold: '#ef5350',          // TradingView red
                buyHoldFill: 'rgba(239, 83, 80, 0.05)',
                positive: '#26a69a',         // Green for profit
                negative: '#ef5350',         // Red for loss
                grid: 'rgba(42, 46, 57, 0.8)',
                gridLight: 'rgba(42, 46, 57, 0.4)',
                text: '#787b86',
                textBright: '#d1d4dc',
                background: '#131722',
                tooltipBg: '#1e222d',
                crosshair: '#758696'
            },
            ...options
        };

        this.trades = [];
        this.initialCapital = 10000;
    }

    /**
     * Initialize and render the chart
     * @param {Object} data - Chart data with equity, timestamps, trades, etc.
     */
    render(data) {
        if (!this.container || !data) {
            console.warn('TradingViewEquityChart: Container or data not found');
            return;
        }

        this.data = data;
        this.trades = data.trades || [];
        this.initialCapital = data.initial_capital || 10000;

        // Destroy existing chart
        if (this.chart) {
            this.chart.destroy();
        }

        // Prepare datasets
        const datasets = this._prepareDatasets(data);

        // Create MFE/MAE drawing plugin
        const tradeExcursionsPlugin = this._createTradeExcursionsPlugin();

        // Create chart
        const ctx = this._getOrCreateCanvas();

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this._formatLabels(data.timestamps),
                datasets: datasets
            },
            options: this._getChartOptions(data),
            plugins: [tradeExcursionsPlugin]
        });

        // Setup legend interactivity
        this._setupLegendInteractivity();

        return this.chart;
    }

    /**
     * Prepare datasets for Chart.js
     */
    _prepareDatasets(data) {
        const datasets = [];
        const equity = data.equity || [];
        const timestamps = data.timestamps || [];
        const isPercent = this.options.displayMode === 'percent';

        // Calculate Buy & Hold values (for optional B&H line)
        let bhValues = data.bh_equity || this._calculateBuyHold(data);

        if (isPercent) {
            const baseBh = bhValues[0] || this.initialCapital;
            bhValues = bhValues.map(v => ((v - baseBh) / baseBh) * 100);
        }

        // 1. Trade Excursion Bars (TradingView style)
        // Each bar = one trade, showing MFE (up) and MAE (down)
        // Two layers: light (full excursion) and dark (realized P&L)
        const tradeExcursions = this._calculateTradeExcursionBars(timestamps);

        // Layer 1: Full excursion (light colors) - MFE positive, MAE negative
        datasets.push({
            type: 'bar',
            label: 'Excursion',
            data: tradeExcursions.fullExcursion,
            backgroundColor: tradeExcursions.fullColors,
            barPercentage: 0.85,
            categoryPercentage: 1.0,
            order: 3,
            yAxisID: 'y3',
            maxBarThickness: 50
        });

        // Layer 2: Realized P&L (dark colors) - overlaid on top
        datasets.push({
            type: 'bar',
            label: 'Realized P&L',
            data: tradeExcursions.realizedPnL,
            backgroundColor: tradeExcursions.realizedColors,
            barPercentage: 0.85,
            categoryPercentage: 1.0,
            order: 2,
            yAxisID: 'y3',
            maxBarThickness: 50
        });

        // 3. Buy & Hold line (if enabled)
        if (this.options.showBuyHold && bhValues.length > 0) {
            datasets.push({
                label: 'Покупка и удержание',
                data: bhValues,
                borderColor: this.options.colors.buyHold,
                backgroundColor: 'transparent',
                borderWidth: 1.5,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: this.options.colors.buyHold,
                tension: 0,
                fill: false,
                order: 1,
                yAxisID: 'y'
            });
        }

        // 4. Main equity line - stepped line based on TRADES (TradingView style)
        // Calculate equity at each trade exit point
        const tradeEquity = this._calculateTradeBasedEquity(timestamps, equity, isPercent);

        datasets.push({
            label: 'Equity',
            data: tradeEquity.values,
            borderColor: this.options.colors.equity,
            backgroundColor: (context) => this._createGradient(context),
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: this.options.colors.equity,
            pointHoverBackgroundColor: this.options.colors.equity,
            pointHoverBorderColor: '#fff',
            pointHoverBorderWidth: 2,
            stepped: 'after',  // Creates stepped line like TradingView
            fill: true,
            order: 0,
            yAxisID: 'y',
            spanGaps: true  // Connect points even with null values between
        });

        return datasets;
    }

    /**
     * Calculate equity values based on trade exits (not every candle)
     * Returns sparse array with values only at trade exit points
     */
    _calculateTradeBasedEquity(timestamps, fullEquity, isPercent = false) {
        // Create sparse array - null except at trade exits
        const values = new Array(timestamps.length).fill(null);
        const baseEquity = this.initialCapital;

        if (!this.trades || this.trades.length === 0) {
            // No trades - use first and last equity points only
            if (fullEquity.length > 0) {
                const first = isPercent ? 0 : fullEquity[0];
                const last = isPercent
                    ? ((fullEquity[fullEquity.length - 1] - fullEquity[0]) / fullEquity[0]) * 100
                    : fullEquity[fullEquity.length - 1];
                values[0] = first;
                values[fullEquity.length - 1] = last;
            }
            return { values };
        }

        // Start with initial capital (or 0% in percent mode) at first timestamp
        values[0] = isPercent ? 0 : baseEquity;

        // Add equity point at each trade exit
        let runningEquity = baseEquity;

        this.trades.forEach(trade => {
            const exitTime = trade.exit_time
                ? new Date(trade.exit_time).getTime()
                : new Date(trade.entry_time).getTime();

            // Find closest timestamp index
            let closestIdx = 0;
            let minDiff = Infinity;

            for (let i = 0; i < timestamps.length; i++) {
                const ts = new Date(timestamps[i]).getTime();
                const diff = Math.abs(ts - exitTime);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIdx = i;
                }
            }

            // Update running equity with trade P&L
            runningEquity += (trade.pnl || 0);

            // Store value (absolute or percent)
            if (isPercent) {
                values[closestIdx] = ((runningEquity - baseEquity) / baseEquity) * 100;
            } else {
                values[closestIdx] = runningEquity;
            }
        });

        return { values };
    }

    /**
     * Create gradient fill for equity line
     */
    _createGradient(context) {
        if (!context.chart.chartArea) return this.options.colors.equityFill;

        const { top, bottom } = context.chart.chartArea;
        const ctx = context.chart.ctx;
        const gradient = ctx.createLinearGradient(0, top, 0, bottom);

        gradient.addColorStop(0, this.options.colors.equityGradientStart);
        gradient.addColorStop(0.5, this.options.colors.equityFill);
        gradient.addColorStop(1, this.options.colors.equityGradientEnd);

        return gradient;
    }

    /**
     * Calculate Buy & Hold equity if not provided
     */
    _calculateBuyHold(data) {
        if (!data.first_price || !data.close_prices) {
            // Generate approximate based on equity change ratio
            const equity = data.equity || [];
            if (equity.length === 0) return [];

            // Just return a flat line at initial capital for now
            return equity.map(() => this.initialCapital);
        }

        const firstPrice = data.first_price;
        const shares = this.initialCapital / firstPrice;
        return data.close_prices.map(p => shares * p);
    }

    /**
     * Calculate Trade Excursion bars (TradingView style)
     * Each bar = one trade, positioned at its exit time
     * Returns two layers: full excursion (light) and realized P&L (dark)
     */
    _calculateTradeExcursionBars(timestamps) {
        // Create sparse arrays - null except at trade positions
        const fullExcursion = new Array(timestamps.length).fill(null);
        const realizedPnL = new Array(timestamps.length).fill(null);
        const fullColors = new Array(timestamps.length).fill('transparent');
        const realizedColors = new Array(timestamps.length).fill('transparent');

        // Light colors for full excursion
        const greenLight = 'rgba(38, 166, 154, 0.35)';
        const redLight = 'rgba(239, 83, 80, 0.35)';
        // Dark colors for realized P&L
        const greenDark = 'rgba(38, 166, 154, 0.9)';
        const redDark = 'rgba(239, 83, 80, 0.9)';

        if (!this.trades || this.trades.length === 0) {
            return { fullExcursion, realizedPnL, fullColors, realizedColors };
        }

        // For each trade, find closest timestamp and set values
        this.trades.forEach(trade => {
            const exitTime = trade.exit_time
                ? new Date(trade.exit_time).getTime()
                : new Date(trade.entry_time).getTime();

            // Find closest timestamp index
            let closestIdx = 0;
            let minDiff = Infinity;
            for (let i = 0; i < timestamps.length; i++) {
                const ts = new Date(timestamps[i]).getTime();
                const diff = Math.abs(ts - exitTime);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIdx = i;
                }
            }

            const mfe = Math.abs(trade.mfe || 0);  // Maximum Favorable Excursion (%)
            const mae = Math.abs(trade.mae || 0);  // Maximum Adverse Excursion (%)
            const pnl = trade.pnl || 0;
            const pnlPercent = Math.abs((pnl / this.initialCapital) * 100);

            // For profitable trades: show MFE (green bar up)
            // For losing trades: show MAE (red bar down, negative value)
            if (pnl >= 0) {
                // Profitable trade - green bars
                fullExcursion[closestIdx] = mfe;  // Full favorable excursion
                fullColors[closestIdx] = greenLight;
                realizedPnL[closestIdx] = Math.min(pnlPercent, mfe);  // Realized profit (capped at MFE)
                realizedColors[closestIdx] = greenDark;
            } else {
                // Losing trade - red bars (negative to go down)
                fullExcursion[closestIdx] = -mae;  // Full adverse excursion
                fullColors[closestIdx] = redLight;
                realizedPnL[closestIdx] = -Math.min(pnlPercent, mae);  // Realized loss (capped at MAE)
                realizedColors[closestIdx] = redDark;
            }
        });

        return { fullExcursion, realizedPnL, fullColors, realizedColors };
    }

    // NOTE: Trade excursions (MFE/MAE) are now drawn by custom plugin
    // See _createTradeExcursionsPlugin() method at end of class

    /**
     * Format timestamp labels
     */
    _formatLabels(timestamps) {
        if (!timestamps || timestamps.length === 0) return [];

        return timestamps.map(ts => {
            const date = new Date(ts);
            return date;
        });
    }

    /**
     * Get chart configuration options
     */
    _getChartOptions(data) {
        const isPercent = this.options.displayMode === 'percent';
        const equity = data.equity || [];

        // Calculate max excursion for MFE/MAE axis (they are in %)
        let maxExcursion = 1;
        if (this.trades && this.trades.length > 0) {
            this.trades.forEach(trade => {
                const mfe = Math.abs(trade.mfe || 0);
                const mae = Math.abs(trade.mae || 0);
                maxExcursion = Math.max(maxExcursion, mfe, mae);
            });
        }

        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false // We use custom legend in footer
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: this.options.colors.tooltipBg,
                    titleColor: this.options.colors.textBright,
                    bodyColor: this.options.colors.text,
                    borderColor: this.options.colors.grid,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        title: (items) => {
                            if (!items.length) return '';
                            const date = new Date(data.timestamps[items[0].dataIndex]);
                            return date.toLocaleDateString('ru-RU', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric'
                            });
                        },
                        label: (context) => {
                            if (context.dataset.label === 'Excursion') return null;
                            if (context.dataset.label === 'Realized P&L') return null;
                            if (context.dataset.label === 'MFE') return null;
                            if (context.dataset.label === 'MAE') return null;

                            const value = context.parsed.y;
                            if (isPercent) {
                                return `${context.dataset.label}: ${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
                            }
                            return `${context.dataset.label}: ${this._formatCurrency(value)}`;
                        },
                        afterBody: (items) => {
                            if (!items.length) return [];
                            const idx = items[0].dataIndex;
                            const lines = [];

                            // Add P&L info
                            if (equity[idx] && equity[0]) {
                                const pnl = equity[idx] - equity[0];
                                const pnlPct = ((equity[idx] - equity[0]) / equity[0]) * 100;
                                lines.push('');
                                lines.push(`P&L: ${pnl >= 0 ? '+' : ''}${this._formatCurrency(pnl)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`);
                            }

                            // Find trade at this timestamp
                            const timestamp = data.timestamps[idx];
                            const trade = this._findTradeAtTime(timestamp);
                            if (trade) {
                                lines.push('');
                                lines.push(`📊 ${trade.direction.toUpperCase()} Trade`);
                                lines.push(`   Entry: ${this._formatCurrency(trade.entry_price)}`);
                                if (trade.exit_price) {
                                    lines.push(`   Exit: ${this._formatCurrency(trade.exit_price)}`);
                                }
                                lines.push(`   P&L: ${trade.pnl >= 0 ? '+' : ''}${this._formatCurrency(trade.pnl)}`);
                                if (trade.mfe) lines.push(`   MFE: +${trade.mfe.toFixed(2)}%`);
                                if (trade.mae) lines.push(`   MAE: -${Math.abs(trade.mae).toFixed(2)}%`);
                            }

                            return lines;
                        }
                    },
                    filter: (item) => {
                        // Hide Excursion bars and MFE/MAE from tooltip legend
                        return item.dataset.label !== 'Excursion' &&
                               item.dataset.label !== 'Realized P&L' &&
                               item.dataset.label !== 'MFE' &&
                               item.dataset.label !== 'MAE';
                    }
                },
                crosshair: {
                    line: {
                        color: this.options.colors.crosshair,
                        width: 1,
                        dashPattern: [5, 5]
                    },
                    sync: {
                        enabled: false
                    },
                    zoom: {
                        enabled: false
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: this._getTimeUnit(data.timestamps),
                        displayFormats: {
                            day: 'd MMM',
                            week: 'd MMM',
                            month: 'MMM yyyy'
                        }
                    },
                    grid: {
                        color: this.options.colors.gridLight,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.options.colors.text,
                        maxTicksLimit: 12,
                        font: { size: 11 }
                    },
                    border: {
                        display: false
                    }
                },
                y: {
                    position: 'right',
                    grid: {
                        color: this.options.colors.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.options.colors.text,
                        font: { size: 11 },
                        callback: (value) => {
                            if (isPercent) {
                                return value.toFixed(0) + '%';
                            }
                            return this._formatCurrencyShort(value);
                        }
                    },
                    border: {
                        display: false
                    }
                },
                y2: {
                    // MFE/MAE axis (values in %)
                    display: false,
                    position: 'right',
                    min: -maxExcursion * 1.1,
                    max: maxExcursion * 1.1,
                    grid: { display: false }
                },
                y3: {
                    // Trade excursion bars axis (values in %)
                    display: false,
                    position: 'left',
                    min: -maxExcursion * 1.5,
                    max: maxExcursion * 1.5,
                    grid: { display: false }
                }
            },
            animation: {
                duration: 750,
                easing: 'easeOutQuart'
            }
        };
    }

    /**
     * Determine appropriate time unit based on date range
     */
    _getTimeUnit(timestamps) {
        if (!timestamps || timestamps.length < 2) return 'day';

        const first = new Date(timestamps[0]);
        const last = new Date(timestamps[timestamps.length - 1]);
        const days = (last - first) / (1000 * 60 * 60 * 24);

        if (days > 365) return 'month';
        if (days > 60) return 'week';
        return 'day';
    }

    /**
     * Find trade at specific timestamp
     */
    _findTradeAtTime(timestamp) {
        const ts = new Date(timestamp).getTime();
        return this.trades.find(t => {
            const entry = new Date(t.entry_time).getTime();
            const exit = t.exit_time ? new Date(t.exit_time).getTime() : entry;
            return ts >= entry && ts <= exit;
        });
    }

    /**
     * Format currency value
     */
    _formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }

    /**
     * Format currency short (for axis)
     */
    _formatCurrencyShort(value) {
        if (Math.abs(value) >= 1000000) {
            return '$' + (value / 1000000).toFixed(1) + 'M';
        }
        if (Math.abs(value) >= 1000) {
            return '$' + (value / 1000).toFixed(0) + 'K';
        }
        return '$' + value.toFixed(0);
    }

    /**
     * Get or create canvas element
     */
    _getOrCreateCanvas() {
        let canvas = this.container.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            this.container.appendChild(canvas);
        }
        return canvas.getContext('2d');
    }

    /**
     * Setup legend checkbox interactivity
     */
    _setupLegendInteractivity() {
        // Buy & Hold toggle
        const bhCheckbox = document.getElementById('legendBuyHold');
        if (bhCheckbox) {
            bhCheckbox.addEventListener('change', () => {
                this.options.showBuyHold = bhCheckbox.checked;
                if (this.data) this.render(this.data);
            });
        }

        // Trade excursions toggle
        const excursionsCheckbox = document.getElementById('legendTradesRunupDrawdown');
        if (excursionsCheckbox) {
            excursionsCheckbox.addEventListener('change', () => {
                this.options.showTradeExcursions = excursionsCheckbox.checked;
                if (this.data) this.render(this.data);
            });
        }
    }

    /**
     * Switch between absolute and percent mode
     */
    setDisplayMode(mode) {
        this.options.displayMode = mode;
        if (this.data) this.render(this.data);
    }

    /**
     * Toggle Buy & Hold visibility
     */
    toggleBuyHold(show) {
        this.options.showBuyHold = show;
        if (this.data) this.render(this.data);
    }

    /**
     * Toggle trade excursions
     */
    toggleTradeExcursions(show) {
        this.options.showTradeExcursions = show;
        if (this.data) this.render(this.data);
    }

    /**
     * Update chart with new data
     */
    update(data) {
        this.render(data);
    }

    /**
     * Destroy chart instance
     */
    destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    /**
     * Get current display value at cursor position
     */
    getCurrentValue() {
        if (!this.chart || !this.data) return null;
        const lastIdx = this.data.equity.length - 1;
        return {
            equity: this.data.equity[lastIdx],
            pnl: this.data.equity[lastIdx] - (this.data.equity[0] || this.initialCapital),
            pnlPct: ((this.data.equity[lastIdx] - this.data.equity[0]) / this.data.equity[0]) * 100
        };
    }

    /**
     * Create custom plugin for drawing MFE/MAE trade excursions (TradingView style)
     *
     * Each bar has TWO layers:
     * - OUTER (light): Full excursion height (MFE up, MAE down)
     * - INNER (dark): Realized P&L portion
     *
     * This shows how much of the potential move was CAPTURED vs MISSED
     */
    _createTradeExcursionsPlugin() {
        const self = this;

        return {
            id: 'tradeExcursions',
            afterDatasetsDraw(chart) {
                if (!self.options.showTradeExcursions || !self.trades || self.trades.length === 0) {
                    return;
                }

                const ctx = chart.ctx;
                const yAxis = chart.scales.y2;

                if (!yAxis) return;

                const chartArea = chart.chartArea;
                const numTrades = self.trades.length;

                // Calculate bar width: divide chart width by number of trades with small gaps
                const totalWidth = chartArea.right - chartArea.left;
                const gapPx = 2; // 2 pixels between bars
                const barWidth = Math.max(4, (totalWidth - gapPx * (numTrades - 1)) / numTrades);

                // Colors
                const greenLight = 'rgba(38, 166, 154, 0.35)';  // Light green (potential)
                const greenDark = 'rgba(38, 166, 154, 0.85)';   // Dark green (realized)
                const redLight = 'rgba(239, 83, 80, 0.35)';     // Light red (potential)
                const redDark = 'rgba(239, 83, 80, 0.85)';      // Dark red (realized)

                // Draw each trade bar
                self.trades.forEach((trade, idx) => {
                    const mfe = Math.abs(trade.mfe || 0);  // Maximum Favorable Excursion (%)
                    const mae = Math.abs(trade.mae || 0);  // Maximum Adverse Excursion (%)
                    const pnl = trade.pnl || 0;            // Realized P&L

                    // Calculate realized % based on entry price and position size
                    // For simplicity, convert P&L to % of initial capital
                    const pnlPercent = (pnl / self.initialCapital) * 100;

                    // Calculate X position - evenly distribute across chart
                    const x = chartArea.left + idx * (barWidth + gapPx);
                    const bodyWidth = barWidth * 0.85;
                    const bodyX = x + (barWidth - bodyWidth) / 2;

                    // Calculate Y positions
                    const y0 = yAxis.getPixelForValue(0);
                    const yMfe = yAxis.getPixelForValue(mfe);
                    const yMae = yAxis.getPixelForValue(-mae);

                    // === GREEN SIDE (MFE - favorable excursion) ===
                    if (mfe > 0) {
                        // 1. Draw OUTER light green bar (full MFE potential)
                        ctx.fillStyle = greenLight;
                        ctx.fillRect(bodyX, yMfe, bodyWidth, y0 - yMfe);

                        // 2. Draw INNER dark green bar (realized profit if positive)
                        if (pnl > 0) {
                            // Realized profit as % - cap at MFE
                            const realizedMfe = Math.min(Math.abs(pnlPercent), mfe);
                            const yRealizedMfe = yAxis.getPixelForValue(realizedMfe);
                            ctx.fillStyle = greenDark;
                            ctx.fillRect(bodyX, yRealizedMfe, bodyWidth, y0 - yRealizedMfe);
                        }
                    }

                    // === RED SIDE (MAE - adverse excursion) ===
                    if (mae > 0) {
                        // 1. Draw OUTER light red bar (full MAE potential)
                        ctx.fillStyle = redLight;
                        ctx.fillRect(bodyX, y0, bodyWidth, yMae - y0);

                        // 2. Draw INNER dark red bar (realized loss if negative)
                        if (pnl < 0) {
                            // Realized loss as % - cap at MAE
                            const realizedMae = Math.min(Math.abs(pnlPercent), mae);
                            const yRealizedMae = yAxis.getPixelForValue(-realizedMae);
                            ctx.fillStyle = redDark;
                            ctx.fillRect(bodyX, y0, bodyWidth, yRealizedMae - y0);
                        }
                    }
                });
            }
        };
    }
}

// Export for module usage
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TradingViewEquityChart;
}
/* eslint-enable no-undef */

// Make globally available
window.TradingViewEquityChart = TradingViewEquityChart;
