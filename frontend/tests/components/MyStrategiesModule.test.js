/**
 * MyStrategiesModule.test.js — Unit tests for MyStrategiesModule.js
 * Run: npx vitest run tests/components/MyStrategiesModule.test.js
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMyStrategiesModule } from '../../js/components/MyStrategiesModule.js';

// ── Helpers ──────────────────────────────────────────────────────────────────

const escapeHtml = (s) =>
    String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

function makeDOM() {
    document.body.innerHTML = `
    <div id="myStrategiesModal"></div>
    <div id="strategiesList"></div>
    <span id="strategiesCount"></span>
    <button id="btnBatchDelete" class="hidden"></button>
    <span id="batchDeleteCount">0</span>
    <input id="strategiesSelectAll" type="checkbox" />
    <input id="strategiesSearch" value="" />
  `;
}

const SAMPLE_STRATEGIES = [
    { id: 'strat-1', name: 'RSI Strategy', symbol: 'BTCUSDT', timeframe: '15', block_count: 3, updated_at: '2025-06-01T12:00:00Z' },
    { id: 'strat-2', name: 'EMA Cross', symbol: 'ETHUSDT', timeframe: '60', block_count: 5, updated_at: '2025-06-02T08:00:00Z' },
    { id: 'strat-3', name: 'MACD Bot', symbol: 'SOLUSDT', timeframe: '240', block_count: 4, updated_at: null }
];

function makeDeps(overrides = {}) {
    return {
        getStrategyIdFromURL: vi.fn(() => null),
        loadStrategy: vi.fn(() => Promise.resolve()),
        showNotification: vi.fn(),
        escapeHtml,
        ...overrides
    };
}

// ── createMyStrategiesModule ──────────────────────────────────────────────────

describe('createMyStrategiesModule', () => {
    it('returns expected public API', () => {
        const mod = createMyStrategiesModule(makeDeps());
        expect(typeof mod.fetchStrategiesList).toBe('function');
        expect(typeof mod.openMyStrategiesModal).toBe('function');
        expect(typeof mod.closeMyStrategiesModal).toBe('function');
        expect(typeof mod.renderStrategiesList).toBe('function');
        expect(typeof mod.handleStrategyCardAction).toBe('function');
        expect(typeof mod.toggleSelectAll).toBe('function');
        expect(typeof mod.updateBatchDeleteUI).toBe('function');
        expect(typeof mod.batchDeleteSelected).toBe('function');
        expect(typeof mod.cloneStrategy).toBe('function');
        expect(typeof mod.deleteStrategyById).toBe('function');
        expect(typeof mod.filterStrategiesList).toBe('function');
    });
});

// ── fetchStrategiesList ───────────────────────────────────────────────────────

describe('fetchStrategiesList', () => {
    beforeEach(makeDOM);

    it('returns strategies array on success', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ strategies: SAMPLE_STRATEGIES })
        })));

        const mod = createMyStrategiesModule(makeDeps());
        const result = await mod.fetchStrategiesList();
        expect(result).toHaveLength(3);
        expect(result[0].name).toBe('RSI Strategy');
        vi.unstubAllGlobals();
    });

    it('returns empty array and shows notification on fetch error', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network error'))));

        const notify = vi.fn();
        const mod = createMyStrategiesModule(makeDeps({ showNotification: notify }));
        const result = await mod.fetchStrategiesList();
        expect(result).toEqual([]);
        expect(notify).toHaveBeenCalledWith('Failed to load strategies', 'error');
        vi.unstubAllGlobals();
    });

    it('returns empty array when HTTP error', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: false,
            status: 500
        })));

        const mod = createMyStrategiesModule(makeDeps());
        const result = await mod.fetchStrategiesList();
        expect(result).toEqual([]);
        vi.unstubAllGlobals();
    });
});

// ── openMyStrategiesModal ─────────────────────────────────────────────────────

describe('openMyStrategiesModal', () => {
    beforeEach(makeDOM);

    it('adds active class to modal', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ strategies: [] })
        })));

        const mod = createMyStrategiesModule(makeDeps());
        await mod.openMyStrategiesModal();
        expect(document.getElementById('myStrategiesModal').classList.contains('active')).toBe(true);
        vi.unstubAllGlobals();
    });

    it('does nothing when modal element missing', async () => {
        document.getElementById('myStrategiesModal').remove();
        const mod = createMyStrategiesModule(makeDeps());
        await expect(mod.openMyStrategiesModal()).resolves.toBeUndefined();
    });
});

// ── closeMyStrategiesModal ────────────────────────────────────────────────────

describe('closeMyStrategiesModal', () => {
    beforeEach(makeDOM);

    it('removes active class from modal', () => {
        const modal = document.getElementById('myStrategiesModal');
        modal.classList.add('active');
        const mod = createMyStrategiesModule(makeDeps());
        mod.closeMyStrategiesModal();
        expect(modal.classList.contains('active')).toBe(false);
    });
});

// ── renderStrategiesList ──────────────────────────────────────────────────────

describe('renderStrategiesList', () => {
    beforeEach(makeDOM);

    it('renders strategy cards', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList(SAMPLE_STRATEGIES);
        const listEl = document.getElementById('strategiesList');
        expect(listEl.querySelectorAll('.strategy-card')).toHaveLength(3);
    });

    it('shows count', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList(SAMPLE_STRATEGIES);
        expect(document.getElementById('strategiesCount').textContent).toBe('3 strategies');
    });

    it('shows empty state when no strategies', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList([]);
        expect(document.getElementById('strategiesList').innerHTML).toContain('No saved strategies');
    });

    it('marks current strategy card', () => {
        const deps = makeDeps({ getStrategyIdFromURL: () => 'strat-1' });
        const mod = createMyStrategiesModule(deps);
        mod.renderStrategiesList(SAMPLE_STRATEGIES);
        const currentCard = document.querySelector('.strategy-card.current');
        expect(currentCard).not.toBeNull();
        expect(currentCard.dataset.strategyId).toBe('strat-1');
    });

    it('renders date for strategy with updated_at', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList([SAMPLE_STRATEGIES[0]]);
        expect(document.getElementById('strategiesList').innerHTML).toContain('2025');
    });

    it('shows fallback dash for null updated_at', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList([SAMPLE_STRATEGIES[2]]);
        // Dates show as '—' for null
        expect(document.getElementById('strategiesList').innerHTML).toContain('—');
    });
});

// ── filterStrategiesList ──────────────────────────────────────────────────────

describe('filterStrategiesList', () => {
    beforeEach(() => {
        makeDOM();
        // Pre-load strategies into cache via renderStrategiesList
    });

    it('filters by name', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ strategies: SAMPLE_STRATEGIES })
        })));

        const mod = createMyStrategiesModule(makeDeps());
        await mod.fetchStrategiesList(); // populate cache
        document.getElementById('strategiesSearch').value = 'rsi';
        mod.filterStrategiesList();
        expect(document.querySelectorAll('.strategy-card')).toHaveLength(1);
        vi.unstubAllGlobals();
    });

    it('filters by symbol', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ strategies: SAMPLE_STRATEGIES })
        })));

        const mod = createMyStrategiesModule(makeDeps());
        await mod.fetchStrategiesList();
        document.getElementById('strategiesSearch').value = 'eth';
        mod.filterStrategiesList();
        expect(document.querySelectorAll('.strategy-card')).toHaveLength(1);
        vi.unstubAllGlobals();
    });

    it('shows all when query is empty', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ strategies: SAMPLE_STRATEGIES })
        })));

        const mod = createMyStrategiesModule(makeDeps());
        await mod.fetchStrategiesList();
        document.getElementById('strategiesSearch').value = '';
        mod.filterStrategiesList();
        expect(document.querySelectorAll('.strategy-card')).toHaveLength(3);
        vi.unstubAllGlobals();
    });
});

// ── toggleSelectAll ───────────────────────────────────────────────────────────

describe('toggleSelectAll', () => {
    beforeEach(makeDOM);

    it('selects all cards when checked', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList(SAMPLE_STRATEGIES);
        document.getElementById('strategiesSelectAll').checked = true;
        mod.toggleSelectAll();
        const cards = document.querySelectorAll('.strategy-card.selected');
        expect(cards).toHaveLength(3);
    });

    it('deselects all cards when unchecked', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList(SAMPLE_STRATEGIES);
        // Select all first
        document.getElementById('strategiesSelectAll').checked = true;
        mod.toggleSelectAll();
        // Now deselect
        document.getElementById('strategiesSelectAll').checked = false;
        mod.toggleSelectAll();
        const cards = document.querySelectorAll('.strategy-card.selected');
        expect(cards).toHaveLength(0);
    });
});

// ── updateBatchDeleteUI ───────────────────────────────────────────────────────

describe('updateBatchDeleteUI', () => {
    beforeEach(makeDOM);

    it('hides batch delete button when no selection', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.updateBatchDeleteUI();
        expect(document.getElementById('btnBatchDelete').classList.contains('hidden')).toBe(true);
    });

    it('shows batch delete button after selecting a card', () => {
        const mod = createMyStrategiesModule(makeDeps());
        mod.renderStrategiesList(SAMPLE_STRATEGIES);

        // Simulate checkbox click
        const cb = document.querySelector('[data-select-strategy="strat-1"]');
        cb.checked = true;
        const event = new MouseEvent('click', { bubbles: true });
        cb.dispatchEvent(event);

        // updateBatchDeleteUI is called by handleStrategyCardAction via event delegation
        // Directly test: select then update
        document.getElementById('strategiesSelectAll').checked = true;
        mod.toggleSelectAll();
        expect(document.getElementById('btnBatchDelete').classList.contains('hidden')).toBe(false);
    });
});

// ── cloneStrategy ─────────────────────────────────────────────────────────────

describe('cloneStrategy', () => {
    beforeEach(makeDOM);

    it('calls fetch with POST and shows success notification', async () => {
        vi.stubGlobal('fetch', vi.fn()
            .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) }) // clone
            .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ strategies: [] }) }) // reload
        );

        const notify = vi.fn();
        const mod = createMyStrategiesModule(makeDeps({ showNotification: notify }));
        await mod.cloneStrategy('strat-1', 'RSI Strategy');
        expect(notify).toHaveBeenCalledWith(expect.stringContaining('copy'), 'success');
        vi.unstubAllGlobals();
    });

    it('shows error notification on failure', async () => {
        vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 500 })));

        const notify = vi.fn();
        const mod = createMyStrategiesModule(makeDeps({ showNotification: notify }));
        await mod.cloneStrategy('strat-1', 'RSI Strategy');
        expect(notify).toHaveBeenCalledWith('Failed to clone strategy', 'error');
        vi.unstubAllGlobals();
    });
});

// ── deleteStrategyById ────────────────────────────────────────────────────────

describe('deleteStrategyById', () => {
    beforeEach(makeDOM);

    it('does nothing when user cancels confirm', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        const fetchSpy = vi.fn();
        vi.stubGlobal('fetch', fetchSpy);

        const mod = createMyStrategiesModule(makeDeps());
        await mod.deleteStrategyById('strat-1', 'RSI Strategy');
        expect(fetchSpy).not.toHaveBeenCalled();

        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it('calls DELETE and shows success notification', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        vi.stubGlobal('fetch', vi.fn()
            .mockResolvedValueOnce({ ok: true }) // delete
            .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ strategies: [] }) }) // reload
        );

        const notify = vi.fn();
        const mod = createMyStrategiesModule(makeDeps({ showNotification: notify }));
        await mod.deleteStrategyById('strat-1', 'RSI Strategy');
        expect(notify).toHaveBeenCalledWith(expect.stringContaining('deleted'), 'success');

        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });
});
