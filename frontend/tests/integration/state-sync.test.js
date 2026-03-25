/**
 * Integration Tests: StateManager — Cross-page state synchronisation (P0-3)
 *
 * Validates the shim-sync pattern used in all three migrated pages:
 *   dashboard.js, backtest_results.js, strategy_builder.js
 *
 * Pattern under test:
 *   1. store.set(path, value)          → shim variable updated via subscribe()
 *   2. setter(value)                   → store path updated, shim reflects it
 *   3. subscribe() callback fired      → within one microtask / synchronously
 *
 * No real page modules are imported — we replicate their state structures
 * in isolated StateManager instances to keep tests pure and fast.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ---------------------------------------------------------------------------
// 1. Core StateManager behaviour
// ---------------------------------------------------------------------------

describe('StateManager — core reactivity', () => {
    let store;

    beforeEach(() => {
        store = new StateManager({});
    });

    it('get() returns undefined for missing path', () => {
        expect(store.get('missing.path')).toBeUndefined();
    });

    it('get() returns defaultValue for missing path', () => {
        expect(store.get('missing.path', 42)).toBe(42);
    });

    it('set() then get() round-trip', () => {
        store.set('a.b.c', 'hello');
        expect(store.get('a.b.c')).toBe('hello');
    });

    it('set() overwrites existing value', () => {
        store.set('counter', 1);
        store.set('counter', 2);
        expect(store.get('counter')).toBe(2);
    });

    it('subscribe() is called synchronously after set()', () => {
        const cb = vi.fn();
        store.set('x', 0);
        store.subscribe('x', cb);
        store.set('x', 99);
        expect(cb).toHaveBeenCalledWith(99, 'x', 0);
    });

    it('subscribe() receives (newVal, path, oldVal)', () => {
        store.set('score', 10);
        const cb = vi.fn();
        store.subscribe('score', cb);
        store.set('score', 20);
        expect(cb).toHaveBeenCalledWith(20, 'score', 10);
    });

    it('unsubscribe stops further notifications', () => {
        const cb = vi.fn();
        store.set('flag', false);
        const unsub = store.subscribe('flag', cb);
        unsub();
        store.set('flag', true);
        expect(cb).not.toHaveBeenCalled();
    });

    it('multiple subscribers on same path all fire', () => {
        const cb1 = vi.fn();
        const cb2 = vi.fn();
        store.set('val', 0);
        store.subscribe('val', cb1);
        store.subscribe('val', cb2);
        store.set('val', 5);
        expect(cb1).toHaveBeenCalledTimes(1);
        expect(cb2).toHaveBeenCalledTimes(1);
    });
});

// ---------------------------------------------------------------------------
// 2. backtest_results.js — shim sync pattern
// ---------------------------------------------------------------------------

describe('backtest_results — store→shim synchronisation', () => {
    let store;

    // Shim variables (mirror module-level lets in backtest_results.js)
    let currentBacktest;
    let allResults;
    let selectedForCompare;
    let compareMode;
    let tradesCurrentPage;
    let chartDisplayMode;

    beforeEach(() => {
        store = new StateManager({});

        // Initialise state paths (mirrors initializeBacktestResultsState)
        store.set('backtestResults.currentBacktest', null);
        store.set('backtestResults.allResults', []);
        store.set('backtestResults.selectedForCompare', []);
        store.set('backtestResults.compareMode', false);
        store.set('backtestResults.trades.currentPage', 0);
        store.set('backtestResults.chartDisplayMode', 'absolute');

        // Initialise shims
        currentBacktest = null;
        allResults = [];
        selectedForCompare = [];
        compareMode = false;
        tradesCurrentPage = 0;
        chartDisplayMode = 'absolute';

        // Wire shim sync (mirrors _setupLegacyShimSync)
        store.subscribe('backtestResults.currentBacktest', (v) => { currentBacktest = v; });
        store.subscribe('backtestResults.allResults', (v) => { allResults = v; });
        store.subscribe('backtestResults.selectedForCompare', (v) => { selectedForCompare = v; });
        store.subscribe('backtestResults.compareMode', (v) => { compareMode = v; });
        store.subscribe('backtestResults.trades.currentPage', (v) => { tradesCurrentPage = v; });
        store.subscribe('backtestResults.chartDisplayMode', (v) => { chartDisplayMode = v; });
    });

    it('setCurrentBacktest() — store→shim sync', () => {
        const bt = { id: 'bt-1', symbol: 'BTCUSDT', sharpe_ratio: 1.5 };
        store.set('backtestResults.currentBacktest', bt);
        expect(currentBacktest).toEqual(bt);
        expect(store.get('backtestResults.currentBacktest')).toEqual(bt);
    });

    it('setAllResults() — store→shim sync', () => {
        const results = [{ id: 'r1' }, { id: 'r2' }];
        store.set('backtestResults.allResults', results);
        expect(allResults).toEqual(results);
    });

    it('setCompareMode(true) — store→shim sync', () => {
        store.set('backtestResults.compareMode', true);
        expect(compareMode).toBe(true);
    });

    it('selectedForCompare accumulates IDs', () => {
        store.set('backtestResults.selectedForCompare', ['bt-1']);
        expect(selectedForCompare).toEqual(['bt-1']);
        store.set('backtestResults.selectedForCompare', ['bt-1', 'bt-2']);
        expect(selectedForCompare).toEqual(['bt-1', 'bt-2']);
    });

    it('tradesCurrentPage paginates correctly', () => {
        store.set('backtestResults.trades.currentPage', 3);
        expect(tradesCurrentPage).toBe(3);
    });

    it('chartDisplayMode toggles absolute↔percent', () => {
        store.set('backtestResults.chartDisplayMode', 'percent');
        expect(chartDisplayMode).toBe('percent');
        store.set('backtestResults.chartDisplayMode', 'absolute');
        expect(chartDisplayMode).toBe('absolute');
    });

    it('resetting currentBacktest to null clears shim', () => {
        const bt = { id: 'bt-1' };
        store.set('backtestResults.currentBacktest', bt);
        store.set('backtestResults.currentBacktest', null);
        expect(currentBacktest).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// 3. strategy_builder.js — shim sync pattern
// ---------------------------------------------------------------------------

describe('strategy_builder — store→shim synchronisation', () => {
    let store;

    // Shim variables (mirrors module-level lets in strategy_builder.js)
    let strategyBlocks;
    let connections;
    let selectedBlockId;
    let selectedBlockIds;
    let zoom;
    let isDragging;
    let dragOffset;
    let isConnecting;
    let isGroupDragging;
    let currentSyncSymbol;
    let currentBacktestResults;

    beforeEach(() => {
        store = new StateManager({});

        // Mirrors initializeStrategyBuilderState
        store.set('strategyBuilder.graph.blocks', []);
        store.set('strategyBuilder.graph.connections', []);
        store.set('strategyBuilder.selection.selectedBlockId', null);
        store.set('strategyBuilder.selection.selectedBlockIds', []);
        store.set('strategyBuilder.viewport.zoom', 1);
        store.set('strategyBuilder.viewport.isDragging', false);
        store.set('strategyBuilder.viewport.dragOffset', { x: 0, y: 0 });
        store.set('strategyBuilder.connecting.isConnecting', false);
        store.set('strategyBuilder.groupDrag.isGroupDragging', false);
        store.set('strategyBuilder.sync.currentSyncSymbol', null);
        store.set('strategyBuilder.ui.currentBacktestResults', null);

        // Initialise shims
        strategyBlocks = [];
        connections = [];
        selectedBlockId = null;
        selectedBlockIds = [];
        zoom = 1;
        isDragging = false;
        dragOffset = { x: 0, y: 0 };
        isConnecting = false;
        isGroupDragging = false;
        currentSyncSymbol = null;
        currentBacktestResults = null;

        // Wire shim sync (mirrors _setupStrategyBuilderShimSync)
        store.subscribe('strategyBuilder.graph.blocks', (v) => { strategyBlocks = v; });
        store.subscribe('strategyBuilder.graph.connections', (v) => { connections = v; });
        store.subscribe('strategyBuilder.selection.selectedBlockId', (v) => { selectedBlockId = v; });
        store.subscribe('strategyBuilder.selection.selectedBlockIds', (v) => { selectedBlockIds = v; });
        store.subscribe('strategyBuilder.viewport.zoom', (v) => { zoom = v; });
        store.subscribe('strategyBuilder.viewport.isDragging', (v) => { isDragging = v; });
        store.subscribe('strategyBuilder.viewport.dragOffset', (v) => { dragOffset = v; });
        store.subscribe('strategyBuilder.connecting.isConnecting', (v) => { isConnecting = v; });
        store.subscribe('strategyBuilder.groupDrag.isGroupDragging', (v) => { isGroupDragging = v; });
        store.subscribe('strategyBuilder.sync.currentSyncSymbol', (v) => { currentSyncSymbol = v; });
        store.subscribe('strategyBuilder.ui.currentBacktestResults', (v) => { currentBacktestResults = v; });
    });

    it('setSBBlocks() — store→shim sync', () => {
        const blocks = [{ id: 'b1', type: 'indicator' }, { id: 'b2', type: 'entry' }];
        store.set('strategyBuilder.graph.blocks', blocks);
        expect(strategyBlocks).toEqual(blocks);
        expect(store.get('strategyBuilder.graph.blocks')).toEqual(blocks);
    });

    it('setSBConnections() — store→shim sync', () => {
        const conns = [{ from: 'b1', to: 'b2' }];
        store.set('strategyBuilder.graph.connections', conns);
        expect(connections).toEqual(conns);
    });

    it('setSBSelectedBlockId() — store→shim sync', () => {
        store.set('strategyBuilder.selection.selectedBlockId', 'b1');
        expect(selectedBlockId).toBe('b1');
    });

    it('setSBSelectedBlockIds() multi-select — store→shim sync', () => {
        store.set('strategyBuilder.selection.selectedBlockIds', ['b1', 'b2', 'b3']);
        expect(selectedBlockIds).toEqual(['b1', 'b2', 'b3']);
    });

    it('setSBZoom() — store→shim sync', () => {
        store.set('strategyBuilder.viewport.zoom', 1.5);
        expect(zoom).toBe(1.5);
    });

    it('setSBIsDragging() — store→shim sync', () => {
        store.set('strategyBuilder.viewport.isDragging', true);
        expect(isDragging).toBe(true);
    });

    it('setSBDragOffset() — store→shim sync', () => {
        store.set('strategyBuilder.viewport.dragOffset', { x: 120, y: 80 });
        expect(dragOffset).toEqual({ x: 120, y: 80 });
    });

    it('setSBIsConnecting() — store→shim sync', () => {
        store.set('strategyBuilder.connecting.isConnecting', true);
        expect(isConnecting).toBe(true);
    });

    it('setSBIsGroupDragging() — store→shim sync', () => {
        store.set('strategyBuilder.groupDrag.isGroupDragging', true);
        expect(isGroupDragging).toBe(true);
    });

    it('setSBCurrentSyncSymbol() — store→shim sync', () => {
        store.set('strategyBuilder.sync.currentSyncSymbol', 'ETHUSDT');
        expect(currentSyncSymbol).toBe('ETHUSDT');
    });

    it('setSBCurrentBacktestResults() — store→shim sync', () => {
        const results = { metrics: { sharpe_ratio: 2.1 }, trades: [] };
        store.set('strategyBuilder.ui.currentBacktestResults', results);
        expect(currentBacktestResults).toEqual(results);
    });

    it('clearing selectedBlockIds on deselect', () => {
        store.set('strategyBuilder.selection.selectedBlockIds', ['b1', 'b2']);
        store.set('strategyBuilder.selection.selectedBlockIds', []);
        expect(selectedBlockIds).toEqual([]);
    });

    it('adding and removing blocks updates shim array', () => {
        const block1 = { id: 'b1' };
        store.set('strategyBuilder.graph.blocks', [block1]);
        expect(strategyBlocks).toHaveLength(1);

        store.set('strategyBuilder.graph.blocks', []);
        expect(strategyBlocks).toHaveLength(0);
    });
});

// ---------------------------------------------------------------------------
// 4. Cross-page state isolation
// ---------------------------------------------------------------------------

describe('Cross-page state isolation', () => {
    it('two independent store instances do not share state', () => {
        const storeA = new StateManager({});
        const storeB = new StateManager({});

        storeA.set('page.symbol', 'BTCUSDT');
        storeB.set('page.symbol', 'ETHUSDT');

        expect(storeA.get('page.symbol')).toBe('BTCUSDT');
        expect(storeB.get('page.symbol')).toBe('ETHUSDT');
    });

    it('subscriber on storeA does not fire when storeB changes', () => {
        const storeA = new StateManager({});
        const storeB = new StateManager({});
        const cb = vi.fn();

        storeA.set('val', 0);
        storeA.subscribe('val', cb);

        storeB.set('val', 99);
        expect(cb).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// 5. Reactive shim — setter→store→shim round-trip
// ---------------------------------------------------------------------------

describe('Setter → store → shim round-trip', () => {
    it('setter updates store, subscribe reflects change in shim', () => {
        const store = new StateManager({});
        store.set('sb.zoom', 1);

        let shimZoom = 1;
        store.subscribe('sb.zoom', (v) => { shimZoom = v; });

        // Simulate setSBZoom(2.0)
        function setSBZoom(val) { store.set('sb.zoom', val); }

        setSBZoom(2.0);
        expect(store.get('sb.zoom')).toBe(2.0);
        expect(shimZoom).toBe(2.0);
    });

    it('multiple rapid setter calls — shim tracks latest value', () => {
        const store = new StateManager({});
        store.set('page', 0);

        let shimPage = 0;
        store.subscribe('page', (v) => { shimPage = v; });

        for (let i = 1; i <= 10; i++) {
            store.set('page', i);
        }
        expect(shimPage).toBe(10);
        expect(store.get('page')).toBe(10);
    });

    it('object mutation in setter is reflected in shim', () => {
        const store = new StateManager({});
        store.set('offset', { x: 0, y: 0 });

        let shimOffset = { x: 0, y: 0 };
        store.subscribe('offset', (v) => { shimOffset = v; });

        store.set('offset', { x: 50, y: 100 });
        expect(shimOffset).toEqual({ x: 50, y: 100 });
    });
});
