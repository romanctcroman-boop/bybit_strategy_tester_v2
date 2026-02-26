/**
 * ChartManager Tests
 *
 * Tests for frontend/js/components/ChartManager.js
 * Covers: init, destroy, destroyAll, get, has, getAll, update, clear, clearAll, size
 *
 * @migration P0-2: Chart.js memory leak fix tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChartManager } from '../../js/components/ChartManager.js';

// ─── Mock Chart.js ─────────────────────────────────────────────────────────
// Chart is a global in the browser; mock it for Node/Vitest environment.

function makeChartInstance() {
    return {
        destroy: vi.fn(),
        update: vi.fn(),
        data: {
            labels: [],
            datasets: [{ data: [] }, { data: [] }]
        },
        canvas: document.createElement('canvas')
    };
}

/** Factory that produces a new mock instance each call */
function mockChartFactory() {
    return makeChartInstance();
}

// Spy on global Chart constructor
let _lastCreatedChart = null;
vi.stubGlobal('Chart', vi.fn((_canvas, _config) => {
    _lastCreatedChart = mockChartFactory();
    return _lastCreatedChart;
}));

// Chart.getChart static method (used by ChartManager.init to clear orphans)
Chart.getChart = vi.fn(() => null);

// ─── Helpers ───────────────────────────────────────────────────────────────
function makeCanvas() {
    return document.createElement('canvas');
}

function makeConfig(type = 'line') {
    return { type, data: { labels: [], datasets: [] }, options: {} };
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('ChartManager', () => {
    let manager;

    beforeEach(() => {
        manager = new ChartManager();
        vi.clearAllMocks();
        _lastCreatedChart = null;
        Chart.getChart = vi.fn(() => null);
    });

    // ── init() ────────────────────────────────────────────────────────────────

    describe('init()', () => {
        it('creates a Chart and returns it', () => {
            const canvas = makeCanvas();
            const config = makeConfig();
            const chart = manager.init('test', canvas, config);

            expect(Chart).toHaveBeenCalledOnce();
            expect(chart).toBe(_lastCreatedChart);
        });

        it('registers the chart in the internal registry', () => {
            const canvas = makeCanvas();
            manager.init('myChart', canvas, makeConfig());
            expect(manager.has('myChart')).toBe(true);
            expect(manager.size).toBe(1);
        });

        it('destroys existing chart before creating new one (no double canvas)', () => {
            const canvas = makeCanvas();

            // First init
            const first = manager.init('dup', canvas, makeConfig());
            expect(Chart).toHaveBeenCalledTimes(1);

            // Second init with same name → should destroy first, then create
            manager.init('dup', canvas, makeConfig());
            expect(first.destroy).toHaveBeenCalledOnce();
            expect(Chart).toHaveBeenCalledTimes(2);
        });

        it('calls Chart.getChart to destroy orphaned canvas charts', () => {
            const canvas = makeCanvas();
            const orphan = makeChartInstance();
            Chart.getChart = vi.fn(() => orphan);

            manager.init('orphanTest', canvas, makeConfig());
            expect(Chart.getChart).toHaveBeenCalledWith(canvas);
            expect(orphan.destroy).toHaveBeenCalledOnce();
        });

        it('does NOT call orphan destroy when Chart.getChart returns null', () => {
            const canvas = makeCanvas();
            Chart.getChart = vi.fn(() => null);
            // No throw expected
            expect(() => manager.init('noOrphan', canvas, makeConfig())).not.toThrow();
        });

        it('passes canvas and config to Chart constructor', () => {
            const canvas = makeCanvas();
            const config = makeConfig('bar');
            manager.init('barChart', canvas, config);
            expect(Chart).toHaveBeenCalledWith(canvas, config);
        });
    });

    // ── destroy() ────────────────────────────────────────────────────────────

    describe('destroy()', () => {
        it('calls chart.destroy() and removes from registry', () => {
            const canvas = makeCanvas();
            manager.init('toDestroy', canvas, makeConfig());
            const chart = manager.get('toDestroy');
            expect(chart).not.toBeNull();

            manager.destroy('toDestroy');
            expect(chart.destroy).toHaveBeenCalledOnce();
            expect(manager.has('toDestroy')).toBe(false);
            expect(manager.size).toBe(0);
        });

        it('is safe to call on non-existent name (no throw)', () => {
            expect(() => manager.destroy('nonExistent')).not.toThrow();
        });

        it('is idempotent — double destroy does not throw', () => {
            const canvas = makeCanvas();
            manager.init('idempotent', canvas, makeConfig());
            manager.destroy('idempotent');
            expect(() => manager.destroy('idempotent')).not.toThrow();
        });

        it('silently handles chart.destroy() throwing', () => {
            const canvas = makeCanvas();
            manager.init('throws', canvas, makeConfig());
            const chart = manager.get('throws');
            chart.destroy.mockImplementation(() => { throw new Error('already gone'); });

            expect(() => manager.destroy('throws')).not.toThrow();
            expect(manager.has('throws')).toBe(false);
        });
    });

    // ── destroyAll() ─────────────────────────────────────────────────────────

    describe('destroyAll()', () => {
        it('destroys all registered charts and clears the registry', () => {
            const c1 = manager.init('a', makeCanvas(), makeConfig());
            const c2 = manager.init('b', makeCanvas(), makeConfig());
            const c3 = manager.init('c', makeCanvas(), makeConfig());

            manager.destroyAll();

            expect(c1.destroy).toHaveBeenCalledOnce();
            expect(c2.destroy).toHaveBeenCalledOnce();
            expect(c3.destroy).toHaveBeenCalledOnce();
            expect(manager.size).toBe(0);
        });

        it('is safe to call when registry is empty', () => {
            expect(() => manager.destroyAll()).not.toThrow();
            expect(manager.size).toBe(0);
        });

        it('is idempotent — calling twice does not throw', () => {
            manager.init('x', makeCanvas(), makeConfig());
            manager.destroyAll();
            expect(() => manager.destroyAll()).not.toThrow();
        });
    });

    // ── get() ────────────────────────────────────────────────────────────────

    describe('get()', () => {
        it('returns the chart instance for a registered name', () => {
            const canvas = makeCanvas();
            manager.init('getMe', canvas, makeConfig());
            const chart = manager.get('getMe');
            expect(chart).toBe(_lastCreatedChart);
        });

        it('returns null for an unknown name', () => {
            expect(manager.get('ghost')).toBeNull();
        });

        it('returns null after destroying the chart', () => {
            manager.init('gone', makeCanvas(), makeConfig());
            manager.destroy('gone');
            expect(manager.get('gone')).toBeNull();
        });
    });

    // ── has() ────────────────────────────────────────────────────────────────

    describe('has()', () => {
        it('returns true when chart is registered', () => {
            manager.init('present', makeCanvas(), makeConfig());
            expect(manager.has('present')).toBe(true);
        });

        it('returns false when chart is not registered', () => {
            expect(manager.has('absent')).toBe(false);
        });

        it('returns false after destroying', () => {
            manager.init('d', makeCanvas(), makeConfig());
            manager.destroy('d');
            expect(manager.has('d')).toBe(false);
        });
    });

    // ── getAll() ─────────────────────────────────────────────────────────────

    describe('getAll()', () => {
        it('returns array of all chart instances', () => {
            manager.init('p', makeCanvas(), makeConfig());
            manager.init('q', makeCanvas(), makeConfig());

            const all = manager.getAll();
            expect(all).toHaveLength(2);
        });

        it('returns empty array when no charts registered', () => {
            expect(manager.getAll()).toEqual([]);
        });
    });

    // ── size ─────────────────────────────────────────────────────────────────

    describe('size', () => {
        it('tracks count correctly through init/destroy', () => {
            expect(manager.size).toBe(0);
            manager.init('a', makeCanvas(), makeConfig());
            expect(manager.size).toBe(1);
            manager.init('b', makeCanvas(), makeConfig());
            expect(manager.size).toBe(2);
            manager.destroy('a');
            expect(manager.size).toBe(1);
            manager.destroyAll();
            expect(manager.size).toBe(0);
        });
    });

    // ── clear() ──────────────────────────────────────────────────────────────

    describe('clear()', () => {
        it('empties labels and all dataset data without destroying', () => {
            const canvas = makeCanvas();
            manager.init('clr', canvas, makeConfig());
            const chart = manager.get('clr');
            chart.data.labels = ['a', 'b', 'c'];
            chart.data.datasets[0].data = [1, 2, 3];

            manager.clear('clr');

            expect(chart.data.labels).toEqual([]);
            expect(chart.data.datasets[0].data).toEqual([]);
            expect(chart.update).toHaveBeenCalledWith('none');
            // Chart instance still registered
            expect(manager.has('clr')).toBe(true);
        });

        it('uses specified update mode', () => {
            manager.init('modeTest', makeCanvas(), makeConfig());
            const chart = manager.get('modeTest');

            manager.clear('modeTest', 'active');
            expect(chart.update).toHaveBeenCalledWith('active');
        });

        it('is safe for non-existent name', () => {
            expect(() => manager.clear('nope')).not.toThrow();
        });
    });

    // ── clearAll() ───────────────────────────────────────────────────────────

    describe('clearAll()', () => {
        it('clears all charts without destroying them', () => {
            const c1 = manager.init('ca1', makeCanvas(), makeConfig());
            const c2 = manager.init('ca2', makeCanvas(), makeConfig());

            manager.clearAll();

            expect(c1.update).toHaveBeenCalledWith('none');
            expect(c2.update).toHaveBeenCalledWith('none');
            // Registry intact
            expect(manager.size).toBe(2);
        });

        it('is safe on empty registry', () => {
            expect(() => manager.clearAll()).not.toThrow();
        });
    });

    // ── update() ─────────────────────────────────────────────────────────────

    describe('update()', () => {
        it('sets labels and dataset data then calls chart.update()', () => {
            manager.init('upd', makeCanvas(), makeConfig());
            const chart = manager.get('upd');

            manager.update('upd', ['Jan', 'Feb'], [[10, 20], [30, 40]]);

            expect(chart.data.labels).toEqual(['Jan', 'Feb']);
            expect(chart.data.datasets[0].data).toEqual([10, 20]);
            expect(chart.data.datasets[1].data).toEqual([30, 40]);
            expect(chart.update).toHaveBeenCalledWith('default');
        });

        it('uses custom update mode', () => {
            manager.init('updMode', makeCanvas(), makeConfig());
            const chart = manager.get('updMode');

            manager.update('updMode', [], [[]], 'active');
            expect(chart.update).toHaveBeenCalledWith('active');
        });

        it('is safe for non-existent name', () => {
            expect(() => manager.update('ghost', [], [[]])).not.toThrow();
        });

        it('ignores extra datasets beyond chart.data.datasets length', () => {
            manager.init('extras', makeCanvas(), makeConfig());
            // chart has 2 datasets; update passes 3 — should not throw
            expect(() =>
                manager.update('extras', [], [[1], [2], [3]])
            ).not.toThrow();
        });
    });

    // ── Integration: re-init cycle (simulates page reload) ───────────────────

    describe('Integration: re-init cycle', () => {
        it('second init destroys first and creates fresh instance', () => {
            const canvas = makeCanvas();

            const first = manager.init('equity', canvas, makeConfig());
            expect(manager.size).toBe(1);

            manager.init('equity', canvas, makeConfig('bar'));

            expect(first.destroy).toHaveBeenCalledOnce();
            expect(manager.size).toBe(1);
            expect(Chart).toHaveBeenCalledTimes(2);
        });

        it('clearAll → destroyAll leaves empty registry', () => {
            manager.init('x', makeCanvas(), makeConfig());
            manager.init('y', makeCanvas(), makeConfig());

            manager.clearAll();
            expect(manager.size).toBe(2);

            manager.destroyAll();
            expect(manager.size).toBe(0);
        });

        it('7-chart scenario: all destroyed on destroyAll()', () => {
            const names = ['drawdown', 'returns', 'monthly', 'tradeDistribution',
                'winLossDonut', 'waterfall', 'benchmarking'];
            const instances = names.map(name =>
                manager.init(name, makeCanvas(), makeConfig())
            );

            expect(manager.size).toBe(7);
            manager.destroyAll();
            expect(manager.size).toBe(0);
            instances.forEach(inst => {
                expect(inst.destroy).toHaveBeenCalledOnce();
            });
        });
    });
});
