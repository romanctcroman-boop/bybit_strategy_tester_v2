/**
 * 🧪 BacktestModule.test.js — Unit tests for BacktestModule component
 *
 * Tests pure/exported functions:
 *   normalizeTimeframeForDropdown, convertIntervalToAPIFormat,
 *   mapIndicatorToStrategyType, mapIndicatorParams,
 *   extractSlTpFromBlocks,
 *   formatPercent, formatPrice, formatDateTime, formatDuration,
 *   getNoTradeDaysFromUI, setNoTradeDaysInUI,
 *   renderResultsSummaryCards, renderOverviewMetrics,
 *   renderTradesTable, renderAllMetrics,
 *   createBacktestModule (stateful methods)
 *
 * @group P0-1
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    normalizeTimeframeForDropdown,
    convertIntervalToAPIFormat,
    mapIndicatorToStrategyType,
    mapIndicatorParams,
    extractSlTpFromBlocks,
    formatPercent,
    formatPrice,
    formatDateTime,
    formatDuration,
    getNoTradeDaysFromUI,
    setNoTradeDaysInUI,
    renderResultsSummaryCards,
    renderOverviewMetrics,
    renderTradesTable,
    renderAllMetrics,
    createBacktestModule
} from '../../js/components/BacktestModule.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function el(id, tag = 'div') {
    const e = document.createElement(tag);
    e.id = id;
    document.body.appendChild(e);
    return e;
}

function checkbox(id, checked = false) {
    const e = document.createElement('input');
    e.type = 'checkbox';
    e.id = id;
    e.checked = checked;
    document.body.appendChild(e);
    return e;
}

function makeResults(overrides = {}) {
    return {
        metrics: {
            net_profit_pct: 15.5,
            win_rate: 60,
            max_drawdown: 10.2,
            total_trades: 42,
            profit_factor: 1.8,
            sharpe_ratio: 1.2,
            net_profit: 1550,
            gross_profit: 2000,
            gross_loss: -450,
            winning_trades: 25,
            losing_trades: 17,
            avg_win: 5.0,
            avg_loss: -2.5,
            largest_win: 8.0,
            largest_loss: -4.0,
            avg_trade_duration: 3600,
            max_consecutive_wins: 5,
            max_consecutive_losses: 3
        },
        trades: [],
        equity_curve: null,
        ...overrides
    };
}

// ─── normalizeTimeframeForDropdown ────────────────────────────────────────────

describe('normalizeTimeframeForDropdown', () => {
    it('returns native intervals unchanged', () => {
        expect(normalizeTimeframeForDropdown('1')).toBe('1');
        expect(normalizeTimeframeForDropdown('15')).toBe('15');
        expect(normalizeTimeframeForDropdown('60')).toBe('60');
        expect(normalizeTimeframeForDropdown('240')).toBe('240');
        expect(normalizeTimeframeForDropdown('D')).toBe('D');
        expect(normalizeTimeframeForDropdown('W')).toBe('W');
        expect(normalizeTimeframeForDropdown('M')).toBe('M');
    });

    it('maps legacy numeric TFs', () => {
        expect(normalizeTimeframeForDropdown('3')).toBe('5');
        expect(normalizeTimeframeForDropdown('120')).toBe('60');
        expect(normalizeTimeframeForDropdown('360')).toBe('240');
        expect(normalizeTimeframeForDropdown('720')).toBe('D');
    });

    it('maps human-readable formats', () => {
        expect(normalizeTimeframeForDropdown('1m')).toBe('1');
        expect(normalizeTimeframeForDropdown('5m')).toBe('5');
        expect(normalizeTimeframeForDropdown('15m')).toBe('15');
        expect(normalizeTimeframeForDropdown('1h')).toBe('60');
        expect(normalizeTimeframeForDropdown('4h')).toBe('240');
        expect(normalizeTimeframeForDropdown('1d')).toBe('D');
        expect(normalizeTimeframeForDropdown('1D')).toBe('D');
        expect(normalizeTimeframeForDropdown('1w')).toBe('W');
        expect(normalizeTimeframeForDropdown('1M')).toBe('M');
    });

    it('returns "15" for null/undefined/empty/unknown', () => {
        expect(normalizeTimeframeForDropdown(null)).toBe('15');
        expect(normalizeTimeframeForDropdown(undefined)).toBe('15');
        expect(normalizeTimeframeForDropdown('')).toBe('15');
        expect(normalizeTimeframeForDropdown('xyz')).toBe('15');
    });
});

// ─── convertIntervalToAPIFormat ───────────────────────────────────────────────

describe('convertIntervalToAPIFormat', () => {
    it('passes native intervals through', () => {
        expect(convertIntervalToAPIFormat('5')).toBe('5');
        expect(convertIntervalToAPIFormat('60')).toBe('60');
        expect(convertIntervalToAPIFormat('D')).toBe('D');
    });

    it('maps legacy to nearest supported', () => {
        expect(convertIntervalToAPIFormat('120')).toBe('60');
        expect(convertIntervalToAPIFormat('720')).toBe('D');
    });

    it('maps human readable', () => {
        expect(convertIntervalToAPIFormat('4h')).toBe('240');
        expect(convertIntervalToAPIFormat('1d')).toBe('D');
    });

    it('defaults to "15" for unknown', () => {
        expect(convertIntervalToAPIFormat('???')).toBe('15');
    });
});

// ─── mapIndicatorToStrategyType ───────────────────────────────────────────────

describe('mapIndicatorToStrategyType', () => {
    it('maps known indicator types', () => {
        expect(mapIndicatorToStrategyType('rsi')).toBe('rsi');
        expect(mapIndicatorToStrategyType('macd')).toBe('macd');
        expect(mapIndicatorToStrategyType('ema')).toBe('ema_cross');
        expect(mapIndicatorToStrategyType('sma')).toBe('sma_cross');
        expect(mapIndicatorToStrategyType('bollinger')).toBe('bollinger_bands');
        expect(mapIndicatorToStrategyType('supertrend')).toBe('supertrend');
        expect(mapIndicatorToStrategyType('stochastic')).toBe('stochastic');
        expect(mapIndicatorToStrategyType('hull_ma')).toBe('hull_ma');
        expect(mapIndicatorToStrategyType('mtf')).toBe('mtf');
    });

    it('returns "custom" for unknown type', () => {
        expect(mapIndicatorToStrategyType('unknown_block')).toBe('custom');
        expect(mapIndicatorToStrategyType('')).toBe('custom');
    });
});

// ─── mapIndicatorParams ───────────────────────────────────────────────────────

describe('mapIndicatorParams', () => {
    it('maps RSI params correctly', () => {
        const block = { type: 'rsi', params: { period: 21, overbought: 75, oversold: 25, source: 'close' } };
        const result = mapIndicatorParams(block);
        expect(result.period).toBe(21);
        expect(result.overbought).toBe(75);
        expect(result.oversold).toBe(25);
        expect(result.source).toBe('close');
    });

    it('fills RSI defaults when params missing', () => {
        const block = { type: 'rsi', params: {} };
        const result = mapIndicatorParams(block);
        expect(result.period).toBe(14);
        expect(result.overbought).toBe(70);
        expect(result.oversold).toBe(30);
    });

    it('maps MACD params correctly', () => {
        const block = { type: 'macd', params: { fast_period: 12, slow_period: 26, signal_period: 9 } };
        const result = mapIndicatorParams(block);
        expect(result.fast_period).toBe(12);
        expect(result.slow_period).toBe(26);
        expect(result.signal_period).toBe(9);
    });

    it('maps Bollinger params', () => {
        const block = { type: 'bollinger', params: { period: 20, std_dev: 2.0 } };
        const result = mapIndicatorParams(block);
        expect(result.period).toBe(20);
        expect(result.std_dev).toBe(2.0);
    });

    it('maps Stochastic params', () => {
        const block = { type: 'stochastic', params: {} };
        const result = mapIndicatorParams(block);
        expect(result.k_period).toBe(14);
        expect(result.d_period).toBe(3);
        expect(result.overbought).toBe(80);
        expect(result.oversold).toBe(20);
    });

    it('passes through unknown type params', () => {
        const block = { type: 'custom_block', params: { foo: 1, bar: 2 } };
        const result = mapIndicatorParams(block);
        expect(result.foo).toBe(1);
        expect(result.bar).toBe(2);
    });

    it('uses getDefaultParams fallback when params is undefined', () => {
        const block = { type: 'ema' };
        const getDefaultParamsFn = vi.fn(() => ({ fast_period: 9, slow_period: 21, source: 'close' }));
        const result = mapIndicatorParams(block, getDefaultParamsFn);
        expect(getDefaultParamsFn).toHaveBeenCalledWith('ema');
        expect(result.fast_period).toBe(9);
    });
});

// ─── extractSlTpFromBlocks ────────────────────────────────────────────────────

describe('extractSlTpFromBlocks', () => {
    it('returns empty object for empty blocks', () => {
        expect(extractSlTpFromBlocks([])).toEqual({});
    });

    it('extracts stop_loss and take_profit from static_sltp block', () => {
        const blocks = [
            { type: 'static_sltp', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } }
        ];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.stop_loss).toBeCloseTo(0.02);
        expect(result.take_profit).toBeCloseTo(0.04);
    });

    it('extracts breakeven from static_sltp', () => {
        const blocks = [
            {
                type: 'static_sltp',
                params: {
                    stop_loss_percent: 2.0,
                    take_profit_percent: 4.0,
                    activate_breakeven: true,
                    breakeven_activation_percent: 1.0,
                    new_breakeven_sl_percent: 0.2
                }
            }
        ];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.breakeven_enabled).toBe(true);
        expect(result.breakeven_activation_pct).toBeCloseTo(0.01);
        expect(result.breakeven_offset).toBeCloseTo(0.002);
    });

    it('extracts close_only_in_profit flag', () => {
        const blocks = [{ type: 'static_sltp', params: { close_only_in_profit: true } }];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.close_only_in_profit).toBe(true);
    });

    it('extracts sl_type from static_sltp', () => {
        const blocks = [{ type: 'static_sltp', params: { sl_type: 'last_order' } }];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.sl_type).toBe('last_order');
    });

    it('extracts stop_loss from sl_percent block', () => {
        const blocks = [{ type: 'sl_percent', params: { stop_loss_percent: 3.0 } }];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.stop_loss).toBeCloseTo(0.03);
    });

    it('uses .percent field as fallback in sl_percent', () => {
        const blocks = [{ type: 'sl_percent', params: { percent: 5.0 } }];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.stop_loss).toBeCloseTo(0.05);
    });

    it('extracts take_profit from tp_percent block', () => {
        const blocks = [{ type: 'tp_percent', params: { take_profit_percent: 6.0 } }];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.take_profit).toBeCloseTo(0.06);
    });

    it('static_sltp takes priority over sl_percent for stop_loss (first wins)', () => {
        const blocks = [
            { type: 'static_sltp', params: { stop_loss_percent: 2.0, take_profit_percent: 4.0 } },
            { type: 'sl_percent', params: { stop_loss_percent: 9.0 } }
        ];
        const result = extractSlTpFromBlocks(blocks);
        expect(result.stop_loss).toBeCloseTo(0.02); // static_sltp wins
    });

    it('ignores blocks with no relevant params', () => {
        const blocks = [
            { type: 'rsi', params: { period: 14 } },
            { type: 'ema', params: { period: 20 } }
        ];
        expect(extractSlTpFromBlocks(blocks)).toEqual({});
    });
});

// ─── formatPercent ────────────────────────────────────────────────────────────

describe('formatPercent', () => {
    it('formats positive value', () => {
        expect(formatPercent(15.5)).toBe('15.50%');
    });

    it('formats negative value', () => {
        expect(formatPercent(-3.7)).toBe('-3.70%');
    });

    it('formats zero', () => {
        expect(formatPercent(0)).toBe('0.00%');
    });

    it('returns 0.00% for null/undefined', () => {
        expect(formatPercent(null)).toBe('0.00%');
        expect(formatPercent(undefined)).toBe('0.00%');
    });
});

// ─── formatPrice ──────────────────────────────────────────────────────────────

describe('formatPrice', () => {
    it('formats integer price', () => {
        expect(formatPrice(50000)).toBe('50,000.00');
    });

    it('formats small decimal', () => {
        const result = formatPrice(0.00123456);
        expect(result).toContain('0.001234');
    });

    it('returns "0.00" for null/undefined', () => {
        expect(formatPrice(null)).toBe('0.00');
        expect(formatPrice(undefined)).toBe('0.00');
    });
});

// ─── formatDateTime ───────────────────────────────────────────────────────────

describe('formatDateTime', () => {
    it('formats a valid ISO date string', () => {
        const result = formatDateTime('2025-06-15T10:30:00Z');
        // Should contain month abbreviation and hour digits
        expect(typeof result).toBe('string');
        expect(result.length).toBeGreaterThan(3);
    });

    it('returns "-" for null/undefined/empty', () => {
        expect(formatDateTime(null)).toBe('-');
        expect(formatDateTime(undefined)).toBe('-');
        expect(formatDateTime('')).toBe('-');
    });
});

// ─── formatDuration ───────────────────────────────────────────────────────────

describe('formatDuration', () => {
    it('returns "-" for zero or falsy', () => {
        expect(formatDuration(0)).toBe('-');
        expect(formatDuration(null)).toBe('-');
        expect(formatDuration(undefined)).toBe('-');
    });

    it('formats hours and minutes', () => {
        expect(formatDuration(3720)).toBe('1h 2m'); // 1h 2min
    });

    it('formats multi-day durations', () => {
        const result = formatDuration(90000); // 25 hours
        expect(result).toContain('d');
    });
});

// ─── getNoTradeDaysFromUI / setNoTradeDaysInUI ────────────────────────────────

describe('getNoTradeDaysFromUI / setNoTradeDaysInUI', () => {
    beforeEach(() => {
        // Create all day checkboxes
        ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].forEach(d => checkbox(`dayBlock${d}`));
    });

    it('returns empty array when no days checked', () => {
        expect(getNoTradeDaysFromUI()).toEqual([]);
    });

    it('returns weekday numbers for checked days', () => {
        document.getElementById('dayBlockMo').checked = true; // weekday 0
        document.getElementById('dayBlockFr').checked = true; // weekday 4
        const result = getNoTradeDaysFromUI();
        expect(result).toContain(0);
        expect(result).toContain(4);
        expect(result).toHaveLength(2);
    });

    it('setNoTradeDaysInUI checks the correct checkboxes', () => {
        setNoTradeDaysInUI([1, 3]); // Tue=1, Thu=3
        expect(document.getElementById('dayBlockTu').checked).toBe(true);
        expect(document.getElementById('dayBlockTh').checked).toBe(true);
        expect(document.getElementById('dayBlockMo').checked).toBe(false);
    });

    it('setNoTradeDaysInUI handles empty array', () => {
        document.getElementById('dayBlockMo').checked = true;
        setNoTradeDaysInUI([]);
        expect(document.getElementById('dayBlockMo').checked).toBe(false);
    });

    it('round-trips through set then get', () => {
        setNoTradeDaysInUI([0, 6]);
        expect(getNoTradeDaysFromUI()).toEqual([0, 6]);
    });
});

// ─── renderResultsSummaryCards ────────────────────────────────────────────────

describe('renderResultsSummaryCards', () => {
    beforeEach(() => {
        el('resultsSummaryCards');
    });

    it('renders 6 summary cards', () => {
        renderResultsSummaryCards(makeResults());
        const cards = document.querySelectorAll('.summary-card');
        expect(cards).toHaveLength(6);
    });

    it('shows positive class for positive return', () => {
        renderResultsSummaryCards(makeResults());
        const firstCard = document.querySelector('.summary-card');
        expect(firstCard.classList.contains('positive')).toBe(true);
    });

    it('shows negative class for negative return', () => {
        renderResultsSummaryCards(makeResults({ metrics: { ...makeResults().metrics, net_profit_pct: -5.0 } }));
        const firstCard = document.querySelector('.summary-card');
        expect(firstCard.classList.contains('negative')).toBe(true);
    });

    it('shows profit factor with 2 decimal places', () => {
        renderResultsSummaryCards(makeResults());
        const html = document.getElementById('resultsSummaryCards').innerHTML;
        expect(html).toContain('1.80'); // profit_factor = 1.8
    });

    it('does nothing when container missing', () => {
        document.getElementById('resultsSummaryCards').remove();
        expect(() => renderResultsSummaryCards(makeResults())).not.toThrow();
    });
});

// ─── renderOverviewMetrics ────────────────────────────────────────────────────

describe('renderOverviewMetrics', () => {
    beforeEach(() => {
        el('metricsOverview');
    });

    it('renders metric cards', () => {
        renderOverviewMetrics(makeResults());
        const cards = document.querySelectorAll('.metric-card');
        expect(cards.length).toBeGreaterThan(0);
    });

    it('does nothing when container missing', () => {
        document.getElementById('metricsOverview').remove();
        expect(() => renderOverviewMetrics(makeResults())).not.toThrow();
    });

    it('shows Net Profit label', () => {
        renderOverviewMetrics(makeResults());
        expect(document.getElementById('metricsOverview').innerHTML).toContain('Net Profit');
    });
});

// ─── renderTradesTable ────────────────────────────────────────────────────────

describe('renderTradesTable', () => {
    beforeEach(() => {
        const tbody = document.createElement('tbody');
        tbody.id = 'tradesTableBody';
        document.body.appendChild(tbody);
    });

    it('shows "no trades" message for empty array', () => {
        renderTradesTable([]);
        expect(document.getElementById('tradesTableBody').innerHTML).toContain('No trades to display');
    });

    it('renders correct number of rows', () => {
        const trades = [
            { side: 'long', pnl: 100, pnl_pct: 1.0, entry_price: 50000, exit_price: 50500, quantity: 0.1, entry_time: '2025-01-01T00:00:00Z', exit_time: '2025-01-01T01:00:00Z', mfe: 1.5, mae: -0.5 },
            { side: 'short', pnl: -50, pnl_pct: -0.5, entry_price: 50500, exit_price: 51000, quantity: 0.1, entry_time: '2025-01-02T00:00:00Z', exit_time: '2025-01-02T01:00:00Z', mfe: 0.2, mae: -1.0 }
        ];
        renderTradesTable(trades);
        const rows = document.querySelectorAll('#tradesTableBody tr');
        expect(rows).toHaveLength(2);
    });

    it('applies long/short CSS class correctly', () => {
        const trades = [
            { side: 'long', pnl: 100, pnl_pct: 1.0, entry_price: 50000, exit_price: 50500, quantity: 0.1, mfe: 1.0, mae: -0.5 }
        ];
        renderTradesTable(trades);
        const html = document.getElementById('tradesTableBody').innerHTML;
        expect(html).toContain('trade-side-long');
    });

    it('applies positive PnL class for profitable trade', () => {
        const trades = [
            { side: 'long', pnl: 200, pnl_pct: 2.0, entry_price: 50000, exit_price: 51000, quantity: 0.1, mfe: 2.5, mae: -0.3 }
        ];
        renderTradesTable(trades);
        const html = document.getElementById('tradesTableBody').innerHTML;
        expect(html).toContain('trade-pnl-positive');
    });

    it('does nothing when tbody missing', () => {
        document.getElementById('tradesTableBody').remove();
        expect(() => renderTradesTable([])).not.toThrow();
    });
});

// ─── renderAllMetrics ─────────────────────────────────────────────────────────

describe('renderAllMetrics', () => {
    beforeEach(() => {
        el('allMetricsGrid');
    });

    it('renders all 6 metric categories', () => {
        renderAllMetrics(makeResults());
        const categories = document.querySelectorAll('.metrics-category');
        expect(categories).toHaveLength(6);
    });

    it('renders Performance category first', () => {
        renderAllMetrics(makeResults());
        const first = document.querySelector('.metrics-category-title');
        expect(first.textContent).toContain('Performance');
    });

    it('does nothing when container missing', () => {
        document.getElementById('allMetricsGrid').remove();
        expect(() => renderAllMetrics(makeResults())).not.toThrow();
    });
});

// ─── createBacktestModule — stateful methods ──────────────────────────────────

describe('createBacktestModule', () => {
    function makeDeps(overrides = {}) {
        const blocks = [{ type: 'rsi', params: { period: 14 } }];
        return {
            getBlocks: vi.fn(() => blocks),
            getBlockLibrary: vi.fn(() => ({ indicators: [], filters: [], exits: [] })),
            getDefaultParams: vi.fn(() => ({})),
            showNotification: vi.fn(),
            saveStrategy: vi.fn(async () => { }),
            autoSaveStrategy: vi.fn(async () => { }),
            validateStrategyCompleteness: vi.fn(() => ({ valid: true, errors: [], warnings: [] })),
            validateStrategy: vi.fn(async () => { }),
            getStrategyIdFromURL: vi.fn(() => 'test-strategy-id'),
            setSBCurrentBacktestResults: vi.fn(),
            ...overrides
        };
    }

    it('creates module instance with expected methods', () => {
        const mod = createBacktestModule(makeDeps());
        expect(typeof mod.runBacktest).toBe('function');
        expect(typeof mod.buildBacktestRequest).toBe('function');
        expect(typeof mod.displayBacktestResults).toBe('function');
        expect(typeof mod.switchResultsTab).toBe('function');
        expect(typeof mod.closeBacktestResultsModal).toBe('function');
        expect(typeof mod.exportBacktestResults).toBe('function');
        expect(typeof mod.viewFullResults).toBe('function');
        expect(typeof mod.getCurrentResults).toBe('function');
        expect(typeof mod.setCurrentResults).toBe('function');
    });

    it('getCurrentResults returns null initially', () => {
        const mod = createBacktestModule(makeDeps());
        expect(mod.getCurrentResults()).toBeNull();
    });

    it('setCurrentResults/getCurrentResults round-trip', () => {
        const mod = createBacktestModule(makeDeps());
        const fakeResults = { backtest_id: 'abc123', metrics: {} };
        mod.setCurrentResults(fakeResults);
        expect(mod.getCurrentResults()).toBe(fakeResults);
    });

    describe('buildBacktestRequest', () => {
        it('reads values from DOM and returns valid config', () => {
            // Setup DOM elements
            const ids = {
                strategyTimeframe: '15',
                backtestSymbol: 'BTCUSDT',
                backtestStartDate: '2025-01-01',
                backtestEndDate: '2025-06-01',
                builderMarketType: 'linear',
                backtestCapital: '10000',
                backtestLeverage: '10',
                builderDirection: 'both',
                backtestPyramiding: '1',
                backtestCommission: '0.07',
                backtestSlippage: '0',
                backtestPositionSizeType: 'percent',
                backtestPositionSize: '100'
            };
            for (const [id, value] of Object.entries(ids)) {
                const e = document.createElement('input');
                e.id = id;
                e.value = value;
                document.body.appendChild(e);
            }

            const mod = createBacktestModule(makeDeps());
            const req = mod.buildBacktestRequest();

            expect(req.symbol).toBe('BTCUSDT');
            expect(req.interval).toBe('15');
            expect(req.initial_capital).toBe(10000);
            expect(req.leverage).toBe(10);
            expect(req.commission).toBeCloseTo(0.0007);
            expect(req.position_size).toBeCloseTo(1.0); // 100% → 1.0 fraction
            expect(req.market_type).toBe('linear');
        });

        it('clamps commission to 0.01 (1%) when > 1%', () => {
            const e = document.createElement('input');
            e.id = 'backtestCommission';
            e.value = '2.0'; // 2% — above 1% cap
            document.body.appendChild(e);
            const mod = createBacktestModule(makeDeps());
            const req = mod.buildBacktestRequest();
            expect(req.commission).toBeCloseTo(0.01);
        });

        it('defaults commission to 0.0007 on invalid value', () => {
            const e = document.createElement('input');
            e.id = 'backtestCommission';
            e.value = 'invalid';
            document.body.appendChild(e);
            const mod = createBacktestModule(makeDeps());
            const req = mod.buildBacktestRequest();
            expect(req.commission).toBeCloseTo(0.0007);
        });
    });

    describe('displayBacktestResults', () => {
        it('stores results and calls setSBCurrentBacktestResults', () => {
            el('backtestResultsModal');
            el('resultsSummaryCards');
            el('metricsOverview');
            const tbody = document.createElement('tbody');
            tbody.id = 'tradesTableBody';
            document.body.appendChild(tbody);
            el('allMetricsGrid');

            const deps = makeDeps();
            const mod = createBacktestModule(deps);
            const results = makeResults();

            mod.displayBacktestResults(results);

            expect(mod.getCurrentResults()).toBe(results);
            expect(deps.setSBCurrentBacktestResults).toHaveBeenCalledWith(results);
        });

        it('does not throw when modal element missing', () => {
            const mod = createBacktestModule(makeDeps());
            expect(() => mod.displayBacktestResults(makeResults())).not.toThrow();
        });
    });

    describe('exportBacktestResults', () => {
        it('calls showNotification warning when no results', () => {
            const deps = makeDeps();
            const mod = createBacktestModule(deps);
            mod.exportBacktestResults();
            expect(deps.showNotification).toHaveBeenCalledWith('No results to export', 'warning');
        });

        it('creates download link and triggers click when results present', () => {
            const deps = makeDeps();
            const mod = createBacktestModule(deps);
            mod.setCurrentResults({ backtest_id: 'test', metrics: {} });

            const mockLink = { href: '', download: '', click: vi.fn() };
            vi.spyOn(document, 'createElement').mockImplementationOnce(() => mockLink);
            vi.spyOn(document.body, 'appendChild').mockImplementationOnce(() => { });
            vi.spyOn(document.body, 'removeChild').mockImplementationOnce(() => { });

            mod.exportBacktestResults();
            expect(mockLink.click).toHaveBeenCalled();
            expect(deps.showNotification).toHaveBeenCalledWith('Results exported successfully', 'success');
        });
    });

    describe('viewFullResults', () => {
        it('calls showNotification when no backtest_id', () => {
            const deps = makeDeps();
            const mod = createBacktestModule(deps);
            mod.setCurrentResults({ metrics: {} }); // no backtest_id
            mod.viewFullResults();
            expect(deps.showNotification).toHaveBeenCalledWith('No backtest ID available', 'warning');
        });
    });

    describe('closeBacktestResultsModal', () => {
        it('removes active class from modal', () => {
            const modal = el('backtestResultsModal');
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';

            const mod = createBacktestModule(makeDeps());
            mod.closeBacktestResultsModal();

            expect(modal.classList.contains('active')).toBe(false);
            expect(document.body.style.overflow).toBe('');
        });

        it('does not throw when modal missing', () => {
            const mod = createBacktestModule(makeDeps());
            expect(() => mod.closeBacktestResultsModal()).not.toThrow();
        });
    });

    describe('switchResultsTab', () => {
        it('activates the correct tab button and content', () => {
            const tabBtn = document.createElement('button');
            tabBtn.className = 'results-tab';
            tabBtn.dataset.tab = 'overview';
            tabBtn.classList.add('active');
            document.body.appendChild(tabBtn);

            const tabBtn2 = document.createElement('button');
            tabBtn2.className = 'results-tab';
            tabBtn2.dataset.tab = 'trades';
            document.body.appendChild(tabBtn2);

            const content1 = el('tab-overview');
            content1.className = 'results-tab-content active';
            const content2 = el('tab-trades');
            content2.className = 'results-tab-content';

            const mod = createBacktestModule(makeDeps());
            mod.switchResultsTab('trades');

            expect(tabBtn.classList.contains('active')).toBe(false);
            expect(tabBtn2.classList.contains('active')).toBe(true);
            expect(content1.classList.contains('active')).toBe(false);
            expect(content2.classList.contains('active')).toBe(true);
        });
    });
});
