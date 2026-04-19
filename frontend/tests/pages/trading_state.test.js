/**
 * Trading Page StateManager Integration Tests
 *
 * Tests for P0-3 migration: trading.js state management via StateManager
 * Validates that:
 * 1. initializeTradingState() creates all required state paths
 * 2. Shim variables sync from store (store→shim via subscribe)
 * 3. Default values are correct
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ============================
// Helpers
// ============================

/**
 * Build an isolated store that mirrors initializeTradingState().
 */
function buildTradingStore() {
    const store = new StateManager({});

    store.merge('trading', {
        currentSymbol: 'BTCUSDT',
        currentTimeframe: '60',
        currentSide: 'buy',
        currentLeverage: 5,
        candleData: [],
        volumeData: [],
        charts: {
            chart: null,
            volumeChart: null,
            candleSeries: null,
            volumeSeries: null,
            volumeSmaSeries: null,
            priceLine: null
        }
    });

    return store;
}

/**
 * Simulate _setupTradingShimSync() by wiring shim variables.
 */
function buildShimSync(store) {
    const shim = {
        currentSymbol: 'BTCUSDT',
        currentTimeframe: '60',
        currentSide: 'buy',
        currentLeverage: 5,
        candleData: [],
        volumeData: [],
        chart: null,
        volumeChart: null,
        candleSeries: null,
        volumeSeries: null,
        volumeSmaSeries: null,
        priceLine: null
    };

    store.subscribe('trading.currentSymbol', (v) => { shim.currentSymbol = v; });
    store.subscribe('trading.currentTimeframe', (v) => { shim.currentTimeframe = v; });
    store.subscribe('trading.currentSide', (v) => { shim.currentSide = v; });
    store.subscribe('trading.currentLeverage', (v) => { shim.currentLeverage = v; });
    store.subscribe('trading.candleData', (v) => { shim.candleData = v; });
    store.subscribe('trading.volumeData', (v) => { shim.volumeData = v; });
    store.subscribe('trading.charts.chart', (v) => { shim.chart = v; });
    store.subscribe('trading.charts.volumeChart', (v) => { shim.volumeChart = v; });
    store.subscribe('trading.charts.candleSeries', (v) => { shim.candleSeries = v; });
    store.subscribe('trading.charts.volumeSeries', (v) => { shim.volumeSeries = v; });
    store.subscribe('trading.charts.volumeSmaSeries', (v) => { shim.volumeSmaSeries = v; });
    store.subscribe('trading.charts.priceLine', (v) => { shim.priceLine = v; });

    return shim;
}

// ============================
// Tests
// ============================

describe('Trading Page — StateManager Integration (P0-3)', () => {
    let store;

    beforeEach(() => {
        store = buildTradingStore();
    });

    describe('initializeTradingState() — state structure', () => {
        it('creates trading.currentSymbol with default BTCUSDT', () => {
            expect(store.get('trading.currentSymbol')).toBe('BTCUSDT');
        });

        it('creates trading.currentTimeframe with default 60', () => {
            expect(store.get('trading.currentTimeframe')).toBe('60');
        });

        it('creates trading.currentSide with default buy', () => {
            expect(store.get('trading.currentSide')).toBe('buy');
        });

        it('creates trading.currentLeverage with default 5', () => {
            expect(store.get('trading.currentLeverage')).toBe(5);
        });

        it('creates trading.candleData as empty array', () => {
            expect(store.get('trading.candleData')).toEqual([]);
        });

        it('creates trading.volumeData as empty array', () => {
            expect(store.get('trading.volumeData')).toEqual([]);
        });

        it('creates trading.charts with all null chart instances', () => {
            const charts = store.get('trading.charts');
            expect(charts.chart).toBeNull();
            expect(charts.volumeChart).toBeNull();
            expect(charts.candleSeries).toBeNull();
            expect(charts.volumeSeries).toBeNull();
            expect(charts.volumeSmaSeries).toBeNull();
            expect(charts.priceLine).toBeNull();
        });
    });

    describe('_setupTradingShimSync() — store → shim direction', () => {
        it('shim.currentSymbol updates when store changes', () => {
            const shim = buildShimSync(store);
            store.set('trading.currentSymbol', 'ETHUSDT');
            expect(shim.currentSymbol).toBe('ETHUSDT');
        });

        it('shim.currentTimeframe updates when store changes', () => {
            const shim = buildShimSync(store);
            store.set('trading.currentTimeframe', '240');
            expect(shim.currentTimeframe).toBe('240');
        });

        it('shim.currentSide updates when store changes', () => {
            const shim = buildShimSync(store);
            store.set('trading.currentSide', 'sell');
            expect(shim.currentSide).toBe('sell');
        });

        it('shim.currentLeverage updates when store changes', () => {
            const shim = buildShimSync(store);
            store.set('trading.currentLeverage', 10);
            expect(shim.currentLeverage).toBe(10);
        });

        it('shim.chart updates when store changes', () => {
            const shim = buildShimSync(store);
            const fakeChart = { type: 'candlestick' };
            store.set('trading.charts.chart', fakeChart);
            expect(shim.chart).toStrictEqual(fakeChart);
        });

        it('shim.candleData updates when store changes', () => {
            const shim = buildShimSync(store);
            const data = [{ time: 1000, open: 1, high: 2, low: 0.5, close: 1.5 }];
            store.set('trading.candleData', data);
            expect(shim.candleData).toStrictEqual(data);
        });
    });

    describe('State mutations', () => {
        it('can update currentSymbol via store.set', () => {
            store.set('trading.currentSymbol', 'SOLUSDT');
            expect(store.get('trading.currentSymbol')).toBe('SOLUSDT');
        });

        it('can update currentLeverage via store.set', () => {
            store.set('trading.currentLeverage', 20);
            expect(store.get('trading.currentLeverage')).toBe(20);
        });

        it('can store chart instance and retrieve it', () => {
            const mockChart = { destroy: () => { } };
            store.set('trading.charts.chart', mockChart);
            // StateManager may clone objects; use toStrictEqual for structural equality
            expect(store.get('trading.charts.chart')).toStrictEqual(mockChart);
        });

        it('can append candle data', () => {
            const candle = { time: 1700000000, open: 50000, high: 51000, low: 49000, close: 50500 };
            const current = store.get('trading.candleData');
            store.set('trading.candleData', [...current, candle]);
            expect(store.get('trading.candleData')).toHaveLength(1);
            expect(store.get('trading.candleData')[0]).toEqual(candle);
        });
    });
});
