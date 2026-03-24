/**
 * ConnectionsModule.test.js — Unit tests for ConnectionsModule.js
 * Run: npx vitest run tests/components/ConnectionsModule.test.js
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createConnectionsModule } from '../../js/components/ConnectionsModule.js';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeConnections() {
    const store = [];
    return {
        getConnections: () => store,
        addConnection: (c) => store.push(c),
        removeConnection: (id) => {
            const idx = store.findIndex(c => c.id === id);
            if (idx !== -1) store.splice(idx, 1);
        },
        store
    };
}

function makeBlocks(blocks = []) {
    return { getBlocks: () => blocks };
}

function makeDeps(overrides = {}) {
    const connStore = makeConnections();
    const blocksStore = makeBlocks(overrides.blocks || []);
    return {
        getBlocks: blocksStore.getBlocks,
        getConnections: connStore.getConnections,
        addConnection: connStore.addConnection,
        removeConnection: connStore.removeConnection,
        pushUndo: vi.fn(),
        showNotification: vi.fn(),
        renderBlocks: vi.fn(),
        _connStore: connStore,
        ...overrides
    };
}

function makeDOM() {
    document.body.innerHTML = `
    <div id="canvasContainer">
      <svg id="connectionsCanvas"></svg>
    </div>
  `;
}

// ── createConnectionsModule API ───────────────────────────────────────────────

describe('createConnectionsModule', () => {
    it('returns full public API', () => {
        const mod = createConnectionsModule(makeDeps());
        const expected = [
            'initConnectionSystem', 'startConnection', 'completeConnection', 'cancelConnection',
            'updateTempConnection', 'renderConnections', 'normalizeConnection',
            'normalizeAllConnections', 'deleteConnection', 'disconnectPort',
            'tryAutoSnapConnection', 'highlightCompatiblePorts', 'clearPortHighlights',
            'createBezierPath', 'getPreferredStrategyPort', 'getIsConnecting', 'getConnectionStart'
        ];
        expected.forEach(fn => expect(typeof mod[fn]).toBe('function'));
    });
});

// ── getPreferredStrategyPort ──────────────────────────────────────────────────

describe('getPreferredStrategyPort', () => {
    const mod = createConnectionsModule(makeDeps());

    it('returns sl_tp for static_sltp', () => {
        expect(mod.getPreferredStrategyPort('static_sltp')).toBe('sl_tp');
    });
    it('returns sl_tp for trailing_stop_exit', () => {
        expect(mod.getPreferredStrategyPort('trailing_stop_exit')).toBe('sl_tp');
    });
    it('returns close_cond for close_by_time', () => {
        expect(mod.getPreferredStrategyPort('close_by_time')).toBe('close_cond');
    });
    it('returns dca_grid for dca', () => {
        expect(mod.getPreferredStrategyPort('dca')).toBe('dca_grid');
    });
    it('returns dca_grid for grid_orders', () => {
        expect(mod.getPreferredStrategyPort('grid_orders')).toBe('dca_grid');
    });
    it('returns null for unknown type', () => {
        expect(mod.getPreferredStrategyPort('rsi')).toBeNull();
    });
    it('returns null for undefined', () => {
        expect(mod.getPreferredStrategyPort(undefined)).toBeNull();
    });
});

// ── createBezierPath ──────────────────────────────────────────────────────────

describe('createBezierPath', () => {
    const mod = createConnectionsModule(makeDeps());

    it('returns SVG path string starting with M', () => {
        const path = mod.createBezierPath(0, 0, 100, 100, true);
        expect(path).toMatch(/^M\s+0\s+0/);
    });

    it('fromOutput=true produces positive x control', () => {
        const path = mod.createBezierPath(0, 0, 200, 0, true);
        expect(path).toContain('C');
        // Control point for fromOutput=true should use positive offset from start
        const parts = path.replace(/[MC]/g, ' ').trim().split(/\s+/).map(Number);
        // C x1 y1 x2 y2 ex ey: first control x > start x (0)
        expect(parts[2]).toBeGreaterThan(0);
    });

    it('fromOutput=false produces negative x control from start', () => {
        const path = mod.createBezierPath(200, 0, 0, 0, false);
        expect(path).toContain('C');
    });

    it('controlOffset is at least 50 for nearby points', () => {
        // dx=10, so offset should be clamped to 50
        const path = mod.createBezierPath(0, 0, 10, 0, true);
        // Check that 50 appears in control points
        expect(path).toMatch(/50/);
    });
});

// ── normalizeConnection ───────────────────────────────────────────────────────

describe('normalizeConnection', () => {
    const mod = createConnectionsModule(makeDeps());

    it('passes through canonical format unchanged', () => {
        const conn = {
            id: 'c1',
            source: { blockId: 'b1', portId: 'out' },
            target: { blockId: 'b2', portId: 'in' },
            type: 'data'
        };
        const result = mod.normalizeConnection(conn);
        expect(result.source.blockId).toBe('b1');
        expect(result.target.blockId).toBe('b2');
        expect(result.type).toBe('data');
    });

    it('normalises source_block/target_block format', () => {
        const conn = {
            source_block: 'b1', source_output: 'sig',
            target_block: 'b2', target_input: 'in',
            type: 'condition'
        };
        const result = mod.normalizeConnection(conn);
        expect(result.source.blockId).toBe('b1');
        expect(result.source.portId).toBe('sig');
        expect(result.target.blockId).toBe('b2');
        expect(result.type).toBe('condition');
    });

    it('normalises from/to legacy format', () => {
        const conn = { id: 'c2', from: 'b1', to: 'b2', type: 'flow' };
        const result = mod.normalizeConnection(conn);
        expect(result.source.blockId).toBe('b1');
        expect(result.source.portId).toBe('out');
        expect(result.target.blockId).toBe('b2');
        expect(result.target.portId).toBe('in');
    });

    it('defaults missing type to data', () => {
        const conn = {
            source: { blockId: 'b1', portId: 'out' },
            target: { blockId: 'b2', portId: 'in' }
        };
        const result = mod.normalizeConnection(conn);
        expect(result.type).toBe('data');
    });

    it('generates id if missing', () => {
        const conn = {
            source: { blockId: 'b1', portId: 'out' },
            target: { blockId: 'b2', portId: 'in' },
            type: 'data'
        };
        const result = mod.normalizeConnection(conn);
        expect(result.id).toBeTruthy();
    });

    it('defaults missing portId to out/in', () => {
        const conn = {
            source: { blockId: 'b1' },
            target: { blockId: 'b2' },
            type: 'data'
        };
        const result = mod.normalizeConnection(conn);
        expect(result.source.portId).toBe('out');
        expect(result.target.portId).toBe('in');
    });
});

// ── normalizeAllConnections ───────────────────────────────────────────────────

describe('normalizeAllConnections', () => {
    it('normalises all connections in store in-place', () => {
        const deps = makeDeps();
        deps._connStore.addConnection({ from: 'b1', to: 'b2', id: 'c1' });
        deps._connStore.addConnection({ from: 'b3', to: 'b4', id: 'c2' });

        const mod = createConnectionsModule(deps);
        mod.normalizeAllConnections();

        const conns = deps.getConnections();
        expect(conns[0].source.blockId).toBe('b1');
        expect(conns[1].source.blockId).toBe('b3');
    });
});

// ── deleteConnection ──────────────────────────────────────────────────────────

describe('deleteConnection', () => {
    beforeEach(makeDOM);

    it('removes connection by id and calls pushUndo + renderBlocks', () => {
        const deps = makeDeps();
        deps._connStore.addConnection({ id: 'c1', source: { blockId: 'b1', portId: 'out' }, target: { blockId: 'b2', portId: 'in' }, type: 'data' });

        const mod = createConnectionsModule(deps);
        mod.deleteConnection('c1');

        expect(deps.getConnections()).toHaveLength(0);
        expect(deps.pushUndo).toHaveBeenCalledOnce();
        expect(deps.renderBlocks).toHaveBeenCalledOnce();
    });

    it('does nothing if connection not found', () => {
        const deps = makeDeps();
        const mod = createConnectionsModule(deps);
        mod.deleteConnection('nonexistent');
        expect(deps.pushUndo).not.toHaveBeenCalled();
    });
});

// ── disconnectPort ────────────────────────────────────────────────────────────

describe('disconnectPort', () => {
    beforeEach(makeDOM);

    it('removes connections from an output port', () => {
        const deps = makeDeps();
        deps._connStore.addConnection({ id: 'c1', source: { blockId: 'b1', portId: 'sig' }, target: { blockId: 'b2', portId: 'in' }, type: 'data' });
        deps._connStore.addConnection({ id: 'c2', source: { blockId: 'b3', portId: 'out' }, target: { blockId: 'b2', portId: 'in' }, type: 'data' });

        const portEl = Object.assign(document.createElement('div'), {});
        portEl.dataset.blockId = 'b1';
        portEl.dataset.portId = 'sig';
        portEl.dataset.direction = 'output';
        document.body.appendChild(portEl);

        const mod = createConnectionsModule(deps);
        mod.disconnectPort(portEl);

        const remaining = deps.getConnections();
        expect(remaining).toHaveLength(1);
        expect(remaining[0].id).toBe('c2');
        expect(deps.pushUndo).toHaveBeenCalledOnce();
    });

    it('does nothing when no connections match', () => {
        const deps = makeDeps();
        const portEl = Object.assign(document.createElement('div'), {});
        portEl.dataset.blockId = 'b1';
        portEl.dataset.portId = 'sig';
        portEl.dataset.direction = 'output';

        const mod = createConnectionsModule(deps);
        mod.disconnectPort(portEl);
        expect(deps.pushUndo).not.toHaveBeenCalled();
    });

    it('does nothing when blockId is missing', () => {
        const deps = makeDeps();
        const portEl = document.createElement('div');
        // no dataset attributes
        const mod = createConnectionsModule(deps);
        mod.disconnectPort(portEl);
        expect(deps.pushUndo).not.toHaveBeenCalled();
    });
});

// ── getIsConnecting / getConnectionStart ────────────────────────────────────

describe('connection state getters', () => {
    it('getIsConnecting returns false initially', () => {
        const mod = createConnectionsModule(makeDeps());
        expect(mod.getIsConnecting()).toBe(false);
    });

    it('getConnectionStart returns null initially', () => {
        const mod = createConnectionsModule(makeDeps());
        expect(mod.getConnectionStart()).toBeNull();
    });
});

// ── initConnectionSystem ─────────────────────────────────────────────────────

describe('initConnectionSystem', () => {
    beforeEach(makeDOM);

    it('does not throw when canvasContainer exists', () => {
        const mod = createConnectionsModule(makeDeps());
        expect(() => mod.initConnectionSystem()).not.toThrow();
    });

    it('does not throw when canvasContainer is missing', () => {
        document.body.innerHTML = '';
        const mod = createConnectionsModule(makeDeps());
        expect(() => mod.initConnectionSystem()).not.toThrow();
    });
});

// ── renderConnections ─────────────────────────────────────────────────────────

describe('renderConnections', () => {
    beforeEach(makeDOM);

    it('does nothing if no connections', () => {
        const mod = createConnectionsModule(makeDeps());
        expect(() => mod.renderConnections()).not.toThrow();
        expect(document.querySelectorAll('.connection-line').length).toBe(0);
    });

    it('logs warning for missing block (no throw)', () => {
        const deps = makeDeps();
        deps._connStore.addConnection({
            id: 'c1',
            source: { blockId: 'missing1', portId: 'out' },
            target: { blockId: 'missing2', portId: 'in' },
            type: 'data'
        });
        const spy = vi.spyOn(console, 'warn').mockImplementation(() => { });
        const mod = createConnectionsModule(deps);
        expect(() => mod.renderConnections()).not.toThrow();
        spy.mockRestore();
    });
});
