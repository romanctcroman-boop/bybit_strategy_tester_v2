/**
 * Optimization Page StateManager Integration Tests
 *
 * Tests for P0-3 migration: optimization.js state management via StateManager
 *
 * optimization.js is class-based (OptimizationManager) — tests simulate the
 * class constructor path: _initStateManager() → store.merge() + subscribe().
 *
 * Validates that:
 * 1. _initStateManager() creates all required state paths
 * 2. Class properties sync from store (store → instance via subscribe)
 * 3. saveConfig() / loadSavedConfig() sync to store
 * 4. Default config shape is correct
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ============================
// Default config (mirrors OptimizationManager.constructor)
// ============================

const DEFAULT_CONFIG = {
    targetMetric: 'sharpe_ratio',
    constraints: {
        minSharpe: { enabled: false, value: 1.0 },
        maxDrawdown: { enabled: false, value: 20 },
        minWinRate: { enabled: false, value: 50 },
        minProfitFactor: { enabled: false, value: 1.2 }
    },
    sortBy: 'sharpe_ratio',
    sortOrder: 'desc',
    method: 'grid',
    parameters: [],
    advanced: {
        maxTrials: 100,
        timeout: 3600,
        parallelJobs: 4,
        earlyStopping: true,
        minImprovement: 0.01
    }
};

// ============================
// Helpers
// ============================

/**
 * Simulates _initStateManager() against an isolated store.
 * Returns { store, instance } mirroring OptimizationManager state.
 */
function buildOptimizationStore(overrides = {}) {
    const store = new StateManager({});

    const instanceConfig = { ...DEFAULT_CONFIG, ...overrides.config };
    const instance = {
        config: instanceConfig,
        currentJobId: overrides.currentJobId ?? null,
        results: overrides.results ?? null,
        isRunning: overrides.isRunning ?? false
    };

    // Mirror _initStateManager()
    store.merge('optimization', {
        config: instance.config,
        currentJobId: null,
        results: null,
        isRunning: false
    });

    // Instance → store
    store.set('optimization.config', instance.config);

    // Store → instance (subscribe wiring)
    store.subscribe('optimization.config', (v) => {
        if (v && v !== instance.config) {
            instance.config = { ...instance.config, ...v };
        }
    });
    store.subscribe('optimization.currentJobId', (v) => {
        instance.currentJobId = v;
    });
    store.subscribe('optimization.results', (v) => {
        instance.results = v;
    });

    return { store, instance };
}

// ============================
// Tests
// ============================

describe('Optimization Page — StateManager Integration (P0-3)', () => {
    let store;
    let instance;

    beforeEach(() => {
        ({ store, instance } = buildOptimizationStore());
    });

    describe('_initStateManager() — state structure', () => {
        it('creates optimization.config in store with default targetMetric', () => {
            expect(store.get('optimization.config.targetMetric')).toBe('sharpe_ratio');
        });

        it('creates optimization.config.sortBy with default sharpe_ratio', () => {
            expect(store.get('optimization.config.sortBy')).toBe('sharpe_ratio');
        });

        it('creates optimization.config.sortOrder with default desc', () => {
            expect(store.get('optimization.config.sortOrder')).toBe('desc');
        });

        it('creates optimization.config.method with default grid', () => {
            expect(store.get('optimization.config.method')).toBe('grid');
        });

        it('creates optimization.config.parameters as empty array', () => {
            expect(store.get('optimization.config.parameters')).toEqual([]);
        });

        it('creates optimization.config.advanced with correct defaults', () => {
            const advanced = store.get('optimization.config.advanced');
            expect(advanced.maxTrials).toBe(100);
            expect(advanced.timeout).toBe(3600);
            expect(advanced.parallelJobs).toBe(4);
            expect(advanced.earlyStopping).toBe(true);
            expect(advanced.minImprovement).toBe(0.01);
        });

        it('creates optimization.config.constraints with all constraints disabled', () => {
            const constraints = store.get('optimization.config.constraints');
            expect(constraints.minSharpe.enabled).toBe(false);
            expect(constraints.maxDrawdown.enabled).toBe(false);
            expect(constraints.minWinRate.enabled).toBe(false);
            expect(constraints.minProfitFactor.enabled).toBe(false);
        });

        it('creates optimization.currentJobId as null', () => {
            expect(store.get('optimization.currentJobId')).toBeNull();
        });

        it('creates optimization.results as null', () => {
            expect(store.get('optimization.results')).toBeNull();
        });

        it('creates optimization.isRunning as false', () => {
            expect(store.get('optimization.isRunning')).toBe(false);
        });
    });

    describe('Subscribe wiring — store → instance direction', () => {
        it('instance.currentJobId updates when store.set is called', () => {
            store.set('optimization.currentJobId', 'job-abc-123');
            expect(instance.currentJobId).toBe('job-abc-123');
        });

        it('instance.results updates when store receives results', () => {
            const results = [{ trial: 1, sharpe: 1.8, maxDrawdown: 12 }];
            store.set('optimization.results', results);
            expect(instance.results).toEqual(results);
        });

        it('instance.currentJobId resets when job completes (null)', () => {
            store.set('optimization.currentJobId', 'job-xyz');
            store.set('optimization.currentJobId', null);
            expect(instance.currentJobId).toBeNull();
        });

        it('instance.results resets to null when cleared', () => {
            store.set('optimization.results', [{ trial: 1 }]);
            store.set('optimization.results', null);
            expect(instance.results).toBeNull();
        });
    });

    describe('saveConfig() — instance → store sync', () => {
        it('store config updates when instance.config is saved', () => {
            // Simulate saveConfig(): update instance.config then push to store
            instance.config = { ...instance.config, targetMetric: 'profit_factor' };
            store.set('optimization.config', instance.config);
            expect(store.get('optimization.config.targetMetric')).toBe('profit_factor');
        });

        it('store config.method updates on save', () => {
            instance.config = { ...instance.config, method: 'bayesian' };
            store.set('optimization.config', instance.config);
            expect(store.get('optimization.config.method')).toBe('bayesian');
        });

        it('store config.advanced.maxTrials updates on save', () => {
            instance.config = {
                ...instance.config,
                advanced: { ...instance.config.advanced, maxTrials: 500 }
            };
            store.set('optimization.config', instance.config);
            expect(store.get('optimization.config.advanced.maxTrials')).toBe(500);
        });
    });

    describe('loadSavedConfig() — loaded config synced to store', () => {
        it('after loading, store reflects the loaded config', () => {
            // Simulate loadSavedConfig(): parse from localStorage, set on instance, push to store
            const loaded = {
                ...DEFAULT_CONFIG,
                targetMetric: 'win_rate',
                sortBy: 'win_rate'
            };
            instance.config = loaded;
            store.set('optimization.config', instance.config);

            expect(store.get('optimization.config.targetMetric')).toBe('win_rate');
            expect(store.get('optimization.config.sortBy')).toBe('win_rate');
        });

        it('constraints persisted in saved config are reflected in store', () => {
            const loaded = {
                ...DEFAULT_CONFIG,
                constraints: {
                    ...DEFAULT_CONFIG.constraints,
                    minSharpe: { enabled: true, value: 1.5 }
                }
            };
            instance.config = loaded;
            store.set('optimization.config', instance.config);

            const constraints = store.get('optimization.config.constraints');
            expect(constraints.minSharpe.enabled).toBe(true);
            expect(constraints.minSharpe.value).toBe(1.5);
        });
    });

    describe('isRunning state', () => {
        it('isRunning can be set to true when job starts', () => {
            store.set('optimization.isRunning', true);
            expect(store.get('optimization.isRunning')).toBe(true);
        });

        it('isRunning returns to false when job finishes', () => {
            store.set('optimization.isRunning', true);
            store.set('optimization.isRunning', false);
            expect(store.get('optimization.isRunning')).toBe(false);
        });
    });
});
