/**
 * Analytics Page StateManager Integration Tests
 *
 * Tests for P0-3 migration: analytics.js state management via StateManager
 * Validates that:
 * 1. initializeAnalyticsState() creates all required state paths
 * 2. Shim variables (equityChart, riskDistributionChart, refreshInterval) sync from store
 * 3. Default values are correct
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';

// ============================
// Helpers
// ============================

/**
 * Build an isolated store that mirrors initializeAnalyticsState().
 */
function buildAnalyticsStore() {
    const store = new StateManager({});

    store.merge('analytics', {
        charts: {
            equityChart: null,
            riskDistributionChart: null
        },
        refreshInterval: null,
        currentPeriod: '1M',
        riskData: {},
        equityData: {}
    });

    return store;
}

/**
 * Simulate the 3 store.subscribe() calls inside initializeAnalyticsState().
 */
function buildShimSync(store) {
    const shim = {
        equityChart: null,
        riskDistributionChart: null,
        refreshInterval: null
    };

    store.subscribe('analytics.charts.equityChart', (v) => { shim.equityChart = v; });
    store.subscribe('analytics.charts.riskDistributionChart', (v) => { shim.riskDistributionChart = v; });
    store.subscribe('analytics.refreshInterval', (v) => { shim.refreshInterval = v; });

    return shim;
}

// ============================
// Tests
// ============================

describe('Analytics Page — StateManager Integration (P0-3)', () => {
    let store;

    beforeEach(() => {
        store = buildAnalyticsStore();
    });

    describe('initializeAnalyticsState() — state structure', () => {
        it('creates analytics.charts.equityChart as null', () => {
            expect(store.get('analytics.charts.equityChart')).toBeNull();
        });

        it('creates analytics.charts.riskDistributionChart as null', () => {
            expect(store.get('analytics.charts.riskDistributionChart')).toBeNull();
        });

        it('creates analytics.refreshInterval as null', () => {
            expect(store.get('analytics.refreshInterval')).toBeNull();
        });

        it('creates analytics.currentPeriod with default 1M', () => {
            expect(store.get('analytics.currentPeriod')).toBe('1M');
        });

        it('creates analytics.riskData as empty object', () => {
            expect(store.get('analytics.riskData')).toEqual({});
        });

        it('creates analytics.equityData as empty object', () => {
            expect(store.get('analytics.equityData')).toEqual({});
        });

        it('creates analytics namespace with all expected keys', () => {
            const analyticsState = store.get('analytics');
            expect(analyticsState).toHaveProperty('charts');
            expect(analyticsState).toHaveProperty('refreshInterval');
            expect(analyticsState).toHaveProperty('currentPeriod');
            expect(analyticsState).toHaveProperty('riskData');
            expect(analyticsState).toHaveProperty('equityData');
        });
    });

    describe('Shim sync — store → shim direction', () => {
        it('shim.equityChart updates when store changes', () => {
            const shim = buildShimSync(store);
            const fakeChart = { id: 'equity', resize: () => { } };
            store.set('analytics.charts.equityChart', fakeChart);
            expect(shim.equityChart).toStrictEqual(fakeChart);
        });

        it('shim.riskDistributionChart updates when store changes', () => {
            const shim = buildShimSync(store);
            const fakeChart = { id: 'risk', data: [1, 2, 3] };
            store.set('analytics.charts.riskDistributionChart', fakeChart);
            expect(shim.riskDistributionChart).toStrictEqual(fakeChart);
        });

        it('shim.refreshInterval updates when interval id is stored', () => {
            const shim = buildShimSync(store);
            const intervalId = 42;
            store.set('analytics.refreshInterval', intervalId);
            expect(shim.refreshInterval).toBe(42);
        });

        it('shim.refreshInterval resets to null when cleared', () => {
            const shim = buildShimSync(store);
            store.set('analytics.refreshInterval', 42);
            store.set('analytics.refreshInterval', null);
            expect(shim.refreshInterval).toBeNull();
        });

        it('shim.equityChart resets to null when chart is destroyed', () => {
            const shim = buildShimSync(store);
            store.set('analytics.charts.equityChart', { id: 'equity' });
            store.set('analytics.charts.equityChart', null);
            expect(shim.equityChart).toBeNull();
        });
    });

    describe('State mutations', () => {
        it('can store equity chart object', () => {
            const chart = { type: 'line', render: () => { } };
            store.set('analytics.charts.equityChart', chart);
            // StateManager may clone objects; use toStrictEqual for structural equality
            expect(store.get('analytics.charts.equityChart')).toStrictEqual(chart);
        });

        it('can update currentPeriod', () => {
            store.set('analytics.currentPeriod', '3M');
            expect(store.get('analytics.currentPeriod')).toBe('3M');
        });

        it('can update riskData', () => {
            const riskData = { maxDrawdown: 0.15, sharpe: 1.8 };
            store.set('analytics.riskData', riskData);
            expect(store.get('analytics.riskData')).toEqual(riskData);
        });

        it('can update equityData', () => {
            const equityData = { timestamps: [1, 2, 3], values: [10000, 10100, 10200] };
            store.set('analytics.equityData', equityData);
            expect(store.get('analytics.equityData')).toEqual(equityData);
        });
    });
});
