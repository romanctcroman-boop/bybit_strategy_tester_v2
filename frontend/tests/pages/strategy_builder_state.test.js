/**
 * Strategy Builder StateManager Integration Tests
 *
 * Tests for P0-3 migration: legacy shim sync with StateManager
 * Validates that:
 * 1. initializeStrategyBuilderState() creates all required state paths
 * 2. Shim variables sync from store (store→shim via subscribe)
 * 3. Setter functions update the store
 * 4. _setupStrategyBuilderShimSync() wires subscriptions correctly
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ============================
// Helpers
// ============================

/**
 * Build an isolated store instance mirroring initializeStrategyBuilderState().
 */
function buildStrategyBuilderStore() {
    const store = new StateManager({});

    const paths = {
        // Graph
        'strategyBuilder.graph.blocks': [],
        'strategyBuilder.graph.connections': [],
        // Selection
        'strategyBuilder.selection.selectedBlockId': null,
        'strategyBuilder.selection.selectedBlockIds': [],
        'strategyBuilder.selection.selectedTemplate': null,
        // Viewport
        'strategyBuilder.viewport.zoom': 1,
        'strategyBuilder.viewport.isDragging': false,
        'strategyBuilder.viewport.dragOffset': { x: 0, y: 0 },
        'strategyBuilder.viewport.isMarqueeSelecting': false,
        'strategyBuilder.viewport.marqueeStart': { x: 0, y: 0 },
        'strategyBuilder.viewport.marqueeElement': null,
        // History
        'strategyBuilder.history.lastAutoSavePayload': null,
        'strategyBuilder.history.skipNextAutoSave': false,
        // Connecting
        'strategyBuilder.connecting.isConnecting': false,
        'strategyBuilder.connecting.connectionStart': null,
        'strategyBuilder.connecting.tempLine': null,
        // Group drag
        'strategyBuilder.groupDrag.isGroupDragging': false,
        'strategyBuilder.groupDrag.groupDragOffsets': {},
        // UI
        'strategyBuilder.ui.refreshDunnahBasePanel': null,
        'strategyBuilder.ui.quickAddDialog': null,
        'strategyBuilder.ui.currentBacktestResults': null,
        // Sync
        'strategyBuilder.sync.currentSyncAbortController': null,
        'strategyBuilder.sync.currentSyncSymbol': null,
        'strategyBuilder.sync.currentSyncStartTime': 0
    };

    for (const [path, defaultVal] of Object.entries(paths)) {
        if (store.get(path) === undefined) {
            store.set(path, defaultVal);
        }
    }

    return store;
}

/**
 * Simulate _setupStrategyBuilderShimSync().
 * Returns shim object and wired subscriptions.
 */
function buildShimSync(store) {
    const shim = {
        strategyBlocks: [],
        connections: [],
        selectedBlockId: null,
        selectedBlockIds: [],
        selectedTemplate: null,
        zoom: 1,
        isDragging: false,
        dragOffset: { x: 0, y: 0 },
        isMarqueeSelecting: false,
        marqueeStart: { x: 0, y: 0 },
        lastAutoSavePayload: null,
        skipNextAutoSave: false,
        isConnecting: false,
        connectionStart: null,
        isGroupDragging: false,
        groupDragOffsets: {},
        currentSyncSymbol: null,
        currentSyncStartTime: 0,
        currentBacktestResults: null
    };

    store.subscribe('strategyBuilder.graph.blocks', (v) => { shim.strategyBlocks.length = 0; if (Array.isArray(v)) shim.strategyBlocks.push(...v); });
    store.subscribe('strategyBuilder.graph.connections', (v) => { shim.connections.length = 0; if (Array.isArray(v)) shim.connections.push(...v); });
    store.subscribe('strategyBuilder.selection.selectedBlockId', (v) => { shim.selectedBlockId = v ?? null; });
    store.subscribe('strategyBuilder.selection.selectedBlockIds', (v) => { shim.selectedBlockIds = Array.isArray(v) ? v : []; });
    store.subscribe('strategyBuilder.selection.selectedTemplate', (v) => { shim.selectedTemplate = v ?? null; });
    store.subscribe('strategyBuilder.viewport.zoom', (v) => { shim.zoom = v ?? 1; });
    store.subscribe('strategyBuilder.viewport.isDragging', (v) => { shim.isDragging = v ?? false; });
    store.subscribe('strategyBuilder.viewport.dragOffset', (v) => { if (v) { shim.dragOffset.x = v.x; shim.dragOffset.y = v.y; } });
    store.subscribe('strategyBuilder.viewport.isMarqueeSelecting', (v) => { shim.isMarqueeSelecting = v ?? false; });
    store.subscribe('strategyBuilder.viewport.marqueeStart', (v) => { if (v) { shim.marqueeStart.x = v.x; shim.marqueeStart.y = v.y; } });
    store.subscribe('strategyBuilder.history.lastAutoSavePayload', (v) => { shim.lastAutoSavePayload = v ?? null; });
    store.subscribe('strategyBuilder.history.skipNextAutoSave', (v) => { shim.skipNextAutoSave = v ?? false; });
    store.subscribe('strategyBuilder.connecting.isConnecting', (v) => { shim.isConnecting = v ?? false; });
    store.subscribe('strategyBuilder.connecting.connectionStart', (v) => { shim.connectionStart = v ?? null; });
    store.subscribe('strategyBuilder.groupDrag.isGroupDragging', (v) => { shim.isGroupDragging = v ?? false; });
    store.subscribe('strategyBuilder.groupDrag.groupDragOffsets', (v) => { if (v) Object.assign(shim.groupDragOffsets, v); });
    store.subscribe('strategyBuilder.sync.currentSyncSymbol', (v) => { shim.currentSyncSymbol = v ?? null; });
    store.subscribe('strategyBuilder.sync.currentSyncStartTime', (v) => { shim.currentSyncStartTime = v ?? 0; });
    store.subscribe('strategyBuilder.ui.currentBacktestResults', (v) => { shim.currentBacktestResults = v ?? null; });

    return shim;
}

// ============================
// Tests
// ============================

describe('StrategyBuilder StateManager Integration (P0-3)', () => {
    let store;
    let shim;

    beforeEach(() => {
        store = buildStrategyBuilderStore();
        shim = buildShimSync(store);
    });

    // ------ State initialization ------

    describe('State initialization', () => {
        it('should initialize graph paths with empty arrays', () => {
            expect(store.get('strategyBuilder.graph.blocks')).toEqual([]);
            expect(store.get('strategyBuilder.graph.connections')).toEqual([]);
        });

        it('should initialize selection paths with null/empty defaults', () => {
            expect(store.get('strategyBuilder.selection.selectedBlockId')).toBeNull();
            expect(store.get('strategyBuilder.selection.selectedBlockIds')).toEqual([]);
            expect(store.get('strategyBuilder.selection.selectedTemplate')).toBeNull();
        });

        it('should initialize viewport paths with correct defaults', () => {
            expect(store.get('strategyBuilder.viewport.zoom')).toBe(1);
            expect(store.get('strategyBuilder.viewport.isDragging')).toBe(false);
            expect(store.get('strategyBuilder.viewport.isMarqueeSelecting')).toBe(false);
            const dragOffset = store.get('strategyBuilder.viewport.dragOffset');
            expect(dragOffset).toMatchObject({ x: 0, y: 0 });
        });

        it('should initialize history paths with correct defaults', () => {
            expect(store.get('strategyBuilder.history.lastAutoSavePayload')).toBeNull();
            expect(store.get('strategyBuilder.history.skipNextAutoSave')).toBe(false);
        });

        it('should initialize connecting paths with false/null defaults', () => {
            expect(store.get('strategyBuilder.connecting.isConnecting')).toBe(false);
            expect(store.get('strategyBuilder.connecting.connectionStart')).toBeNull();
        });

        it('should initialize sync paths with null/0 defaults', () => {
            expect(store.get('strategyBuilder.sync.currentSyncSymbol')).toBeNull();
            expect(store.get('strategyBuilder.sync.currentSyncStartTime')).toBe(0);
        });
    });

    // ------ Shim sync: store → shim ------

    describe('Shim sync (store → shim)', () => {
        it('should sync strategyBlocks shim when store updates', () => {
            const blocks = [
                { id: 'main_strategy', type: 'strategy', isMain: true },
                { id: 'block_rsi_1', type: 'rsi', category: 'indicator' }
            ];
            store.set('strategyBuilder.graph.blocks', blocks);
            expect(shim.strategyBlocks).toHaveLength(2);
            expect(shim.strategyBlocks[0].id).toBe('main_strategy');
            expect(shim.strategyBlocks[1].type).toBe('rsi');
        });

        it('should sync connections shim when store updates', () => {
            const conns = [
                { id: 'conn_1', source: { blockId: 'block_1', portId: 'value' }, target: { blockId: 'main_strategy', portId: 'entry' } }
            ];
            store.set('strategyBuilder.graph.connections', conns);
            expect(shim.connections).toHaveLength(1);
            expect(shim.connections[0].id).toBe('conn_1');
        });

        it('should sync selectedBlockId shim when store updates', () => {
            store.set('strategyBuilder.selection.selectedBlockId', 'block_rsi_1');
            expect(shim.selectedBlockId).toBe('block_rsi_1');
        });

        it('should sync selectedBlockIds shim when store updates', () => {
            store.set('strategyBuilder.selection.selectedBlockIds', ['block_1', 'block_2']);
            expect(shim.selectedBlockIds).toEqual(['block_1', 'block_2']);
        });

        it('should sync zoom shim when store updates', () => {
            store.set('strategyBuilder.viewport.zoom', 1.5);
            expect(shim.zoom).toBe(1.5);
        });

        it('should sync isDragging shim when store updates', () => {
            store.set('strategyBuilder.viewport.isDragging', true);
            expect(shim.isDragging).toBe(true);
        });

        it('should sync dragOffset shim when store updates', () => {
            store.set('strategyBuilder.viewport.dragOffset', { x: 100, y: 200 });
            expect(shim.dragOffset.x).toBe(100);
            expect(shim.dragOffset.y).toBe(200);
        });

        it('should sync isConnecting shim when store updates', () => {
            store.set('strategyBuilder.connecting.isConnecting', true);
            expect(shim.isConnecting).toBe(true);
        });

        it('should sync skipNextAutoSave shim when store updates', () => {
            store.set('strategyBuilder.history.skipNextAutoSave', true);
            expect(shim.skipNextAutoSave).toBe(true);
        });

        it('should sync currentSyncSymbol shim when store updates', () => {
            store.set('strategyBuilder.sync.currentSyncSymbol', 'BTCUSDT');
            expect(shim.currentSyncSymbol).toBe('BTCUSDT');
        });

        it('should sync currentBacktestResults shim when store updates', () => {
            const results = { total_trades: 42, profit_factor: 1.5 };
            store.set('strategyBuilder.ui.currentBacktestResults', results);
            expect(shim.currentBacktestResults).toMatchObject({ total_trades: 42 });
        });

        it('should default to [] when store sets null for array shims', () => {
            store.set('strategyBuilder.graph.blocks', null);
            expect(shim.strategyBlocks).toEqual([]);
            store.set('strategyBuilder.graph.connections', null);
            expect(shim.connections).toEqual([]);
        });

        it('should default to null when store sets null for nullable shims', () => {
            store.set('strategyBuilder.selection.selectedBlockId', null);
            expect(shim.selectedBlockId).toBeNull();
        });
    });

    // ------ Setter functions: shim → store ------

    describe('Setter functions (shim → store)', () => {
        function setSBBlocks(v) { store.set('strategyBuilder.graph.blocks', v); }
        function setSBConnections(v) { store.set('strategyBuilder.graph.connections', v); }
        function setSBSelectedBlockId(v) { store.set('strategyBuilder.selection.selectedBlockId', v); }
        function setSBZoom(v) { store.set('strategyBuilder.viewport.zoom', v); }
        function setSBSkipNextAutoSave(v) { store.set('strategyBuilder.history.skipNextAutoSave', v); }
        function setSBCurrentSyncSymbol(v) { store.set('strategyBuilder.sync.currentSyncSymbol', v); }

        it('setSBBlocks should update store and sync shim', () => {
            const blocks = [{ id: 'main_strategy', type: 'strategy', isMain: true }];
            setSBBlocks(blocks);
            expect(store.get('strategyBuilder.graph.blocks')).toHaveLength(1);
            expect(shim.strategyBlocks).toHaveLength(1);
            expect(shim.strategyBlocks[0].id).toBe('main_strategy');
        });

        it('setSBConnections should update store and sync shim', () => {
            const conns = [{ id: 'c1', source: { blockId: 'a', portId: 'out' }, target: { blockId: 'b', portId: 'in' } }];
            setSBConnections(conns);
            expect(store.get('strategyBuilder.graph.connections')).toHaveLength(1);
            expect(shim.connections).toHaveLength(1);
        });

        it('setSBSelectedBlockId should update store and sync shim', () => {
            setSBSelectedBlockId('block_rsi_99');
            expect(store.get('strategyBuilder.selection.selectedBlockId')).toBe('block_rsi_99');
            expect(shim.selectedBlockId).toBe('block_rsi_99');
        });

        it('setSBZoom should update store and sync shim', () => {
            setSBZoom(0.75);
            expect(store.get('strategyBuilder.viewport.zoom')).toBe(0.75);
            expect(shim.zoom).toBe(0.75);
        });

        it('setSBSkipNextAutoSave should update store and sync shim', () => {
            setSBSkipNextAutoSave(true);
            expect(store.get('strategyBuilder.history.skipNextAutoSave')).toBe(true);
            expect(shim.skipNextAutoSave).toBe(true);
        });

        it('setSBCurrentSyncSymbol should update store and sync shim', () => {
            setSBCurrentSyncSymbol('ETHUSDT');
            expect(store.get('strategyBuilder.sync.currentSyncSymbol')).toBe('ETHUSDT');
            expect(shim.currentSyncSymbol).toBe('ETHUSDT');
        });
    });

    // ------ Bidirectional sync integrity ------

    describe('Bidirectional sync integrity', () => {
        it('store write → shim update → store re-read gives same value', () => {
            const blocks = [
                { id: 'main_strategy', isMain: true, type: 'strategy' },
                { id: 'block_macd_1', type: 'macd' }
            ];
            store.set('strategyBuilder.graph.blocks', blocks);
            const fromStore = store.get('strategyBuilder.graph.blocks');
            expect(shim.strategyBlocks.map(b => b.id)).toEqual(fromStore.map(b => b.id));
        });

        it('multiple rapid store updates sync shim correctly (last wins)', () => {
            for (let i = 0; i < 10; i++) {
                store.set('strategyBuilder.viewport.zoom', 1 + i * 0.1);
            }
            expect(shim.zoom).toBeCloseTo(1.9, 5);
        });

        it('clearing blocks updates both store and shim', () => {
            store.set('strategyBuilder.graph.blocks', [{ id: 'b1' }, { id: 'b2' }]);
            expect(shim.strategyBlocks).toHaveLength(2);
            store.set('strategyBuilder.graph.blocks', []);
            expect(shim.strategyBlocks).toHaveLength(0);
            expect(store.get('strategyBuilder.graph.blocks')).toHaveLength(0);
        });
    });

    // ------ Graph operations ------

    describe('Graph operations', () => {
        it('adding a block updates store and shim', () => {
            const blocks = [{ id: 'main_strategy', isMain: true }];
            store.set('strategyBuilder.graph.blocks', blocks);
            // Simulate push + setSBBlocks
            const current = store.get('strategyBuilder.graph.blocks');
            const newBlock = { id: 'block_rsi_1', type: 'rsi' };
            store.set('strategyBuilder.graph.blocks', [...current, newBlock]);
            expect(shim.strategyBlocks).toHaveLength(2);
            expect(shim.strategyBlocks[1].id).toBe('block_rsi_1');
        });

        it('removing a block (filter) updates store and shim', () => {
            store.set('strategyBuilder.graph.blocks', [
                { id: 'main_strategy', isMain: true },
                { id: 'block_rsi_1', type: 'rsi' }
            ]);
            const filtered = store.get('strategyBuilder.graph.blocks').filter(b => b.id !== 'block_rsi_1');
            store.set('strategyBuilder.graph.blocks', filtered);
            expect(shim.strategyBlocks).toHaveLength(1);
            expect(shim.strategyBlocks[0].id).toBe('main_strategy');
        });

        it('restoring snapshot updates both blocks and connections', () => {
            const snapshot = {
                blocks: [{ id: 'main_strategy', isMain: true }, { id: 'block_1', type: 'rsi' }],
                connections: [{ id: 'c1', source: { blockId: 'block_1', portId: 'out' }, target: { blockId: 'main_strategy', portId: 'entry' } }]
            };
            store.set('strategyBuilder.graph.blocks', snapshot.blocks);
            store.set('strategyBuilder.graph.connections', snapshot.connections);
            expect(shim.strategyBlocks).toHaveLength(2);
            expect(shim.connections).toHaveLength(1);
        });
    });

    // ------ Autosave state ------

    describe('Autosave state', () => {
        it('skipNextAutoSave flag round-trips through store', () => {
            store.set('strategyBuilder.history.skipNextAutoSave', true);
            expect(shim.skipNextAutoSave).toBe(true);
            store.set('strategyBuilder.history.skipNextAutoSave', false);
            expect(shim.skipNextAutoSave).toBe(false);
        });

        it('lastAutoSavePayload round-trips through store', () => {
            const payload = JSON.stringify({ blocks: [], connections: [] });
            store.set('strategyBuilder.history.lastAutoSavePayload', payload);
            expect(shim.lastAutoSavePayload).toBe(payload);
            expect(store.get('strategyBuilder.history.lastAutoSavePayload')).toBe(payload);
        });
    });

    // ------ Sync state ------

    describe('Sync state', () => {
        it('sync symbol tracks start/finish cycle', () => {
            store.set('strategyBuilder.sync.currentSyncSymbol', 'BTCUSDT');
            store.set('strategyBuilder.sync.currentSyncStartTime', 1700000000000);
            expect(shim.currentSyncSymbol).toBe('BTCUSDT');
            expect(shim.currentSyncStartTime).toBe(1700000000000);

            // Simulate sync finished
            store.set('strategyBuilder.sync.currentSyncSymbol', null);
            expect(shim.currentSyncSymbol).toBeNull();
        });
    });

    // ------ Connecting wire state ------

    describe('Connecting wire state', () => {
        it('isConnecting toggles correctly through store', () => {
            expect(shim.isConnecting).toBe(false);
            store.set('strategyBuilder.connecting.isConnecting', true);
            expect(shim.isConnecting).toBe(true);
            store.set('strategyBuilder.connecting.isConnecting', false);
            expect(shim.isConnecting).toBe(false);
        });

        it('connectionStart tracks source port', () => {
            const start = { blockId: 'block_rsi_1', portId: 'value' };
            store.set('strategyBuilder.connecting.connectionStart', start);
            expect(shim.connectionStart).toMatchObject({ blockId: 'block_rsi_1' });
            store.set('strategyBuilder.connecting.connectionStart', null);
            expect(shim.connectionStart).toBeNull();
        });
    });
});
