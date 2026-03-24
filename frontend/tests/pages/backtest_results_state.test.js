/**
 * Backtest Results StateManager Integration Tests
 *
 * Tests for P0-3 migration: legacy shim sync with StateManager
 * Validates that:
 * 1. initializeBacktestResultsState() creates all required state paths
 * 2. Shim variables sync from store (store→shim via subscribe)
 * 3. Setter functions update the store
 * 4. _setupLegacyShimSync() wires subscriptions correctly
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ============================
// Helpers & Mocks
// ============================

/**
 * Build an isolated store instance identical to what the page uses.
 * We can't import the actual page module (it references DOM / browser globals),
 * so we replicate the state structure and test the logic in isolation.
 */
function buildBacktestStore() {
    const store = new StateManager({});

    // Mirror initializeBacktestResultsState()
    const paths = {
        'backtestResults.currentBacktest': null,
        'backtestResults.allResults': [],
        'backtestResults.selectedForCompare': [],
        'backtestResults.compareMode': false,
        'backtestResults.trades.currentPage': 0,
        'backtestResults.trades.cachedRows': [],
        'backtestResults.trades.sortKey': null,
        'backtestResults.trades.sortAsc': true,
        'backtestResults.charts.equity': null,
        'backtestResults.charts._tvEquityChart': null,
        'backtestResults.charts.drawdown': null,
        'backtestResults.charts.returns': null,
        'backtestResults.charts.monthly': null,
        'backtestResults.charts.tradeDistribution': null,
        'backtestResults.charts.winLossDonut': null,
        'backtestResults.charts.waterfall': null,
        'backtestResults.charts.benchmarking': null,
        'backtestResults.priceChart.instance': null,
        'backtestResults.priceChart.candleSeries': null,
        'backtestResults.priceChart.markers': [],
        'backtestResults.priceChart.tradeLineSeries': [],
        'backtestResults.priceChart.cachedCandles': [],
        'backtestResults.priceChart.pending': false,
        'backtestResults.priceChart.generation': 0,
        'backtestResults.priceChart.resizeObserver': null,
        'backtestResults.service.recentlyDeletedIds': new Set(),
        'backtestResults.service.selectedForDelete': new Set(),
        'backtestResults.chartDisplayMode': 'absolute'
    };

    for (const [path, defaultVal] of Object.entries(paths)) {
        const current = store.get(path);
        if (current === undefined) {
            store.set(path, defaultVal);
        }
    }

    return store;
}

/**
 * Simulate _setupLegacyShimSync() by building shim variables and wiring them.
 * Returns an object containing the shim variables and the store.
 */
function buildShimSync(store) {
    const shim = {
        currentBacktest: null,
        allResults: [],
        selectedForCompare: [],
        compareMode: false,
        tradesCurrentPage: 0,
        tradesCachedRows: [],
        tradesSortKey: null,
        tradesSortAsc: true,
        equityChart: null,
        _brTVEquityChart: null,
        drawdownChart: null,
        returnsChart: null,
        monthlyChart: null,
        tradeDistributionChart: null,
        winLossDonutChart: null,
        waterfallChart: null,
        benchmarkingChart: null,
        btPriceChart: null,
        btCandleSeries: null,
        btPriceChartMarkers: [],
        btTradeLineSeries: [],
        _btCachedCandles: [],
        btPriceChartPending: false,
        _priceChartGeneration: 0,
        _priceChartResizeObserver: null
    };

    store.subscribe('backtestResults.currentBacktest', (v) => { shim.currentBacktest = v; });
    store.subscribe('backtestResults.allResults', (v) => { shim.allResults = v ?? []; });
    store.subscribe('backtestResults.selectedForCompare', (v) => { shim.selectedForCompare = v ?? []; });
    store.subscribe('backtestResults.compareMode', (v) => { shim.compareMode = !!v; });
    store.subscribe('backtestResults.trades.currentPage', (v) => { shim.tradesCurrentPage = v ?? 0; });
    store.subscribe('backtestResults.trades.cachedRows', (v) => { shim.tradesCachedRows = v ?? []; });
    store.subscribe('backtestResults.trades.sortKey', (v) => { shim.tradesSortKey = v ?? null; });
    store.subscribe('backtestResults.trades.sortAsc', (v) => { shim.tradesSortAsc = v !== false; });
    store.subscribe('backtestResults.charts.equity', (v) => { shim.equityChart = v; });
    store.subscribe('backtestResults.charts._tvEquityChart', (v) => { shim._brTVEquityChart = v; });
    store.subscribe('backtestResults.charts.drawdown', (v) => { shim.drawdownChart = v; });
    store.subscribe('backtestResults.charts.returns', (v) => { shim.returnsChart = v; });
    store.subscribe('backtestResults.charts.monthly', (v) => { shim.monthlyChart = v; });
    store.subscribe('backtestResults.priceChart.instance', (v) => { shim.btPriceChart = v; });
    store.subscribe('backtestResults.priceChart.candleSeries', (v) => { shim.btCandleSeries = v; });
    store.subscribe('backtestResults.priceChart.markers', (v) => { shim.btPriceChartMarkers = v ?? []; });
    store.subscribe('backtestResults.priceChart.tradeLineSeries', (v) => { shim.btTradeLineSeries = v ?? []; });
    store.subscribe('backtestResults.priceChart.cachedCandles', (v) => { shim._btCachedCandles = v ?? []; });
    store.subscribe('backtestResults.priceChart.pending', (v) => { shim.btPriceChartPending = !!v; });
    store.subscribe('backtestResults.priceChart.generation', (v) => { shim._priceChartGeneration = v ?? 0; });
    store.subscribe('backtestResults.priceChart.resizeObserver', (v) => { shim._priceChartResizeObserver = v; });

    return shim;
}

// ============================
// Tests
// ============================

describe('BacktestResults StateManager Integration (P0-3)', () => {
    let store;
    let shim;

    beforeEach(() => {
        store = buildBacktestStore();
        shim = buildShimSync(store);
    });

    // ------ State initialization ------

    describe('State initialization', () => {
        it('should initialize all required state paths with correct defaults', () => {
            expect(store.get('backtestResults.currentBacktest')).toBeNull();
            expect(store.get('backtestResults.allResults')).toEqual([]);
            expect(store.get('backtestResults.selectedForCompare')).toEqual([]);
            expect(store.get('backtestResults.compareMode')).toBe(false);
            expect(store.get('backtestResults.trades.currentPage')).toBe(0);
            expect(store.get('backtestResults.trades.sortAsc')).toBe(true);
            expect(store.get('backtestResults.chartDisplayMode')).toBe('absolute');
        });

        it('should initialize all chart state paths as null', () => {
            const chartKeys = ['equity', '_tvEquityChart', 'drawdown', 'returns', 'monthly',
                'tradeDistribution', 'winLossDonut', 'waterfall', 'benchmarking'];
            for (const key of chartKeys) {
                expect(store.get(`backtestResults.charts.${key}`)).toBeNull();
            }
        });

        it('should initialize price chart state paths', () => {
            expect(store.get('backtestResults.priceChart.instance')).toBeNull();
            expect(store.get('backtestResults.priceChart.candleSeries')).toBeNull();
            expect(store.get('backtestResults.priceChart.markers')).toEqual([]);
            expect(store.get('backtestResults.priceChart.pending')).toBe(false);
            expect(store.get('backtestResults.priceChart.generation')).toBe(0);
        });

        it('should initialize service state paths (Sets stored as module-level consts)', () => {
            // StateManager._deepClone does not preserve Set instances (no special handling),
            // so store.get() returns {} for a Set.  The real Sets live as module-level const
            // variables; they are seeded into the store only so the store is aware of the paths.
            // What matters is that the paths exist (not undefined).
            expect(store.get('backtestResults.service.recentlyDeletedIds')).not.toBeUndefined();
            expect(store.get('backtestResults.service.selectedForDelete')).not.toBeUndefined();
        });
    });

    // ------ Shim sync: store → shim ------

    describe('Shim sync (store → shim)', () => {
        it('should sync currentBacktest shim when store updates', () => {
            const bt = { id: 'test-123', config: { symbol: 'BTCUSDT' } };
            store.set('backtestResults.currentBacktest', bt);
            expect(shim.currentBacktest).toEqual(bt);
        });

        it('should sync allResults shim when store updates', () => {
            const results = [{ backtest_id: 'abc', symbol: 'BTCUSDT' }];
            store.set('backtestResults.allResults', results);
            expect(shim.allResults).toEqual(results);
        });

        it('should sync compareMode shim when store updates', () => {
            store.set('backtestResults.compareMode', true);
            expect(shim.compareMode).toBe(true);
        });

        it('should sync selectedForCompare shim when store updates', () => {
            store.set('backtestResults.selectedForCompare', ['id1', 'id2']);
            expect(shim.selectedForCompare).toEqual(['id1', 'id2']);
        });

        it('should sync trades pagination shims when store updates', () => {
            store.set('backtestResults.trades.currentPage', 3);
            store.set('backtestResults.trades.sortKey', 'pnl');
            store.set('backtestResults.trades.sortAsc', false);
            expect(shim.tradesCurrentPage).toBe(3);
            expect(shim.tradesSortKey).toBe('pnl');
            expect(shim.tradesSortAsc).toBe(false);
        });

        it('should sync btPriceChartPending shim when store updates', () => {
            store.set('backtestResults.priceChart.pending', true);
            expect(shim.btPriceChartPending).toBe(true);
            store.set('backtestResults.priceChart.pending', false);
            expect(shim.btPriceChartPending).toBe(false);
        });

        it('should sync _priceChartGeneration shim when store updates', () => {
            store.set('backtestResults.priceChart.generation', 5);
            expect(shim._priceChartGeneration).toBe(5);
        });

        it('should sync chart instance shims when store updates', () => {
            const mockChart = { id: 'mock-chart', canvas: {}, update: vi.fn() };
            store.set('backtestResults.charts.drawdown', mockChart);
            expect(shim.drawdownChart).toEqual(mockChart);
        });

        it('should handle null value sync gracefully', () => {
            store.set('backtestResults.currentBacktest', null);
            expect(shim.currentBacktest).toBeNull();
        });

        it('should default arrays to [] when store provides null/undefined', () => {
            store.set('backtestResults.allResults', null);
            expect(shim.allResults).toEqual([]);

            store.set('backtestResults.trades.cachedRows', null);
            expect(shim.tradesCachedRows).toEqual([]);

            store.set('backtestResults.priceChart.markers', null);
            expect(shim.btPriceChartMarkers).toEqual([]);
        });
    });

    // ------ Setter functions ------

    describe('Setter functions (shim → store)', () => {
        /**
         * Simulate a setter function directly (mirrors implementation)
         */
        function makeSetter(path) {
            return (value) => store.set(path, value);
        }

        it('setCurrentBacktest should update store', () => {
            const setter = makeSetter('backtestResults.currentBacktest');
            const bt = { id: 'bt-42' };
            setter(bt);
            expect(store.get('backtestResults.currentBacktest')).toEqual(bt);
        });

        it('setAllResults should update store', () => {
            const setter = makeSetter('backtestResults.allResults');
            const results = [{ backtest_id: 'x' }];
            setter(results);
            expect(store.get('backtestResults.allResults')).toEqual(results);
        });

        it('setCompareMode should update store and sync shim', () => {
            const setter = makeSetter('backtestResults.compareMode');
            setter(true);
            expect(store.get('backtestResults.compareMode')).toBe(true);
            expect(shim.compareMode).toBe(true);
        });

        it('setSelectedForCompare should update store and sync shim', () => {
            const setter = makeSetter('backtestResults.selectedForCompare');
            setter(['a', 'b', 'c']);
            expect(store.get('backtestResults.selectedForCompare')).toEqual(['a', 'b', 'c']);
            expect(shim.selectedForCompare).toEqual(['a', 'b', 'c']);
        });

        it('setTradesCurrentPage should update store and sync shim', () => {
            const setter = makeSetter('backtestResults.trades.currentPage');
            setter(2);
            expect(store.get('backtestResults.trades.currentPage')).toBe(2);
            expect(shim.tradesCurrentPage).toBe(2);
        });

        it('setPriceChartPending should update store and sync shim', () => {
            const setter = makeSetter('backtestResults.priceChart.pending');
            setter(true);
            expect(store.get('backtestResults.priceChart.pending')).toBe(true);
            expect(shim.btPriceChartPending).toBe(true);
        });
    });

    // ------ bidirectional sync integrity ------

    describe('Bidirectional sync integrity', () => {
        it('store write → shim update → store re-read gives same value', () => {
            const bt = { id: 'bt-sync-test', trades: [] };
            store.set('backtestResults.currentBacktest', bt);
            // shim was updated via subscribe
            expect(shim.currentBacktest).toEqual(bt);
            // store still holds the correct value
            expect(store.get('backtestResults.currentBacktest')).toEqual(bt);
        });

        it('multiple rapid store updates sync correctly', () => {
            store.set('backtestResults.trades.currentPage', 0);
            store.set('backtestResults.trades.currentPage', 1);
            store.set('backtestResults.trades.currentPage', 5);
            expect(shim.tradesCurrentPage).toBe(5);
            expect(store.get('backtestResults.trades.currentPage')).toBe(5);
        });

        it('allResults filtering flow: assign + setAllResults keeps consistency', () => {
            // Simulate delete flow: allResults = allResults.filter(...); setAllResults(allResults)
            store.set('backtestResults.allResults', [
                { backtest_id: 'a' },
                { backtest_id: 'b' },
                { backtest_id: 'c' }
            ]);
            expect(shim.allResults).toHaveLength(3);

            // Simulate filtered delete
            const filtered = shim.allResults.filter(r => r.backtest_id !== 'b');
            store.set('backtestResults.allResults', filtered);

            expect(shim.allResults).toHaveLength(2);
            expect(shim.allResults.find(r => r.backtest_id === 'b')).toBeUndefined();
            expect(store.get('backtestResults.allResults')).toHaveLength(2);
        });
    });

    // ------ compareMode toggle ------

    describe('toggleCompareMode logic', () => {
        it('should toggle compareMode and reset selectedForCompare', () => {
            // Initial: compareMode=false
            store.set('backtestResults.selectedForCompare', ['id1', 'id2']);
            expect(shim.compareMode).toBe(false);

            // Toggle on
            const newMode = !shim.compareMode;
            store.set('backtestResults.compareMode', newMode);
            store.set('backtestResults.selectedForCompare', []);
            expect(shim.compareMode).toBe(true);
            expect(shim.selectedForCompare).toEqual([]);

            // Toggle off
            const newMode2 = !shim.compareMode;
            store.set('backtestResults.compareMode', newMode2);
            store.set('backtestResults.selectedForCompare', []);
            expect(shim.compareMode).toBe(false);
        });
    });

    // ------ price chart lifecycle ------

    describe('Price chart lifecycle', () => {
        it('setPriceChartPending=true marks chart as needing rebuild', () => {
            store.set('backtestResults.priceChart.pending', true);
            expect(shim.btPriceChartPending).toBe(true);
        });

        it('clearing price chart resets all price chart state', () => {
            // Simulate setting up chart
            const mockChart = { remove: vi.fn() };
            const mockSeries = {};
            const mockCandles = [{ time: 1, open: 100, high: 110, low: 90, close: 105 }];
            store.set('backtestResults.priceChart.instance', mockChart);
            store.set('backtestResults.priceChart.candleSeries', mockSeries);
            store.set('backtestResults.priceChart.cachedCandles', mockCandles);
            store.set('backtestResults.priceChart.pending', true);
            store.set('backtestResults.priceChart.generation', 3);

            expect(shim.btPriceChart).toEqual(mockChart);
            expect(shim._btCachedCandles).toEqual(mockCandles);

            // Simulate clearAllDisplayData() — price chart section
            store.set('backtestResults.priceChart.instance', null);
            store.set('backtestResults.priceChart.candleSeries', null);
            store.set('backtestResults.priceChart.markers', []);
            store.set('backtestResults.priceChart.tradeLineSeries', []);
            store.set('backtestResults.priceChart.cachedCandles', []);
            store.set('backtestResults.priceChart.pending', false);
            store.set('backtestResults.priceChart.generation', 4);

            expect(shim.btPriceChart).toBeNull();
            expect(shim.btCandleSeries).toBeNull();
            expect(shim.btPriceChartMarkers).toEqual([]);
            expect(shim._btCachedCandles).toEqual([]);
            expect(shim.btPriceChartPending).toBe(false);
            expect(shim._priceChartGeneration).toBe(4);
        });
    });

    // ------ chart display mode ------

    describe('Chart display mode', () => {
        it('should default to absolute', () => {
            expect(store.get('backtestResults.chartDisplayMode')).toBe('absolute');
        });

        it('should update chart display mode', () => {
            store.set('backtestResults.chartDisplayMode', 'percent');
            expect(store.get('backtestResults.chartDisplayMode')).toBe('percent');
        });
    });
});
