/**
 * 🧪 TradesTable.test.js — Unit tests for TradesTable component
 *
 * Tests: buildTradeRow, buildTradeRows, sortRows, renderPage,
 *        renderPagination, updatePaginationControls, removePagination,
 *        updateSortIndicators, TRADES_PAGE_SIZE
 *
 * @group P0-2 Phase 2
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
    TRADES_PAGE_SIZE,
    buildTradeRow,
    buildTradeRows,
    sortRows,
    renderPage,
    renderPagination,
    updatePaginationControls,
    removePagination,
    updateSortIndicators
} from '../../js/components/TradesTable.js';

// ─── Fixtures ────────────────────────────────────────────────────────────────

const INITIAL_CAPITAL = 10000;

function makeTrade(overrides = {}) {
    return {
        direction: 'long',
        pnl: 100,
        pnl_pct: 1.0,
        entry_price: 50000,
        exit_price: 50500,
        size: 0.1,
        entry_time: '2025-01-01T10:00:00Z',
        exit_time: '2025-01-01T12:00:00Z',
        exit_reason: 'TP',
        mfe: 120,
        mfe_pct: 1.2,
        mae: -30,
        mae_pct: -0.3,
        ...overrides
    };
}

function makeShortTrade(overrides = {}) {
    return makeTrade({ direction: 'short', pnl: -50, pnl_pct: -0.5, ...overrides });
}

// ─── TRADES_PAGE_SIZE ────────────────────────────────────────────────────────

describe('TRADES_PAGE_SIZE', () => {
    it('is 25', () => {
        expect(TRADES_PAGE_SIZE).toBe(25);
    });
});

// ─── buildTradeRow ────────────────────────────────────────────────────────────

describe('buildTradeRow', () => {
    it('returns object with required sort keys', () => {
        const row = buildTradeRow(makeTrade(), 1, 100, INITIAL_CAPITAL);
        expect(row).toHaveProperty('_date');
        expect(row).toHaveProperty('_pnl');
        expect(row).toHaveProperty('_mfe');
        expect(row).toHaveProperty('_mae');
        expect(row).toHaveProperty('_cumPnl');
        expect(row).toHaveProperty('html');
    });

    it('_pnl matches trade.pnl', () => {
        const row = buildTradeRow(makeTrade({ pnl: 250 }), 1, 250, INITIAL_CAPITAL);
        expect(row._pnl).toBe(250);
    });

    it('_mfe is always non-negative (abs applied)', () => {
        const row = buildTradeRow(makeTrade({ mfe: -80, mfe_pct: -0.8 }), 1, 100, INITIAL_CAPITAL);
        expect(row._mfe).toBe(80);
    });

    it('_mae is always non-negative (abs applied)', () => {
        const row = buildTradeRow(makeTrade({ mae: -40, mae_pct: -0.4 }), 1, 100, INITIAL_CAPITAL);
        expect(row._mae).toBe(40);
    });

    it('_cumPnl equals provided cumulativePnL', () => {
        const row = buildTradeRow(makeTrade(), 1, 350, INITIAL_CAPITAL);
        expect(row._cumPnl).toBe(350);
    });

    it('_date is 0 when exit_time is missing', () => {
        const row = buildTradeRow(makeTrade({ exit_time: null }), 1, 0, INITIAL_CAPITAL);
        expect(row._date).toBe(0);
    });

    it('html contains "Long" for long trade', () => {
        const row = buildTradeRow(makeTrade({ direction: 'long' }), 1, 100, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-trade-long');
        expect(row.html).toContain('>Long<');
    });

    it('html contains "Short" for short trade', () => {
        const row = buildTradeRow(makeShortTrade(), 1, -50, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-trade-short');
        expect(row.html).toContain('>Short<');
    });

    it('detects long via side=Buy', () => {
        const row = buildTradeRow(makeTrade({ direction: undefined, side: 'Buy' }), 1, 100, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-trade-long');
    });

    it('detects short via side=sell', () => {
        const row = buildTradeRow(makeTrade({ direction: undefined, side: 'sell', pnl: -20 }), 1, -20, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-trade-short');
    });

    it('html contains tv-value-positive for positive cumPnl', () => {
        const row = buildTradeRow(makeTrade(), 1, 200, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-value-positive');
    });

    it('html contains tv-value-negative for negative cumPnl', () => {
        const row = buildTradeRow(makeTrade({ pnl: -100 }), 1, -100, INITIAL_CAPITAL);
        expect(row.html).toContain('tv-value-negative');
    });

    it('uses mfe_value fallback when mfe is absent', () => {
        const row = buildTradeRow(makeTrade({ mfe: undefined, mfe_value: 55 }), 1, 100, INITIAL_CAPITAL);
        expect(row._mfe).toBe(55);
    });

    it('defaults initialCapital to 10000', () => {
        // cumPnlPct = cumPnl / 10000 * 100 — check 1% appears in html
        const row = buildTradeRow(makeTrade(), 1, 100); // no initialCapital arg
        expect(row.html).toContain('1.00%'); // 100/10000 * 100 = 1.00%
    });
});

// ─── buildTradeRows ───────────────────────────────────────────────────────────

describe('buildTradeRows', () => {
    it('returns empty array for empty trades', () => {
        expect(buildTradeRows([], INITIAL_CAPITAL)).toEqual([]);
    });

    it('returns rows newest-first (reverse order) when no sort', () => {
        const trades = [
            makeTrade({ pnl: 10, exit_time: '2025-01-01T10:00:00Z' }),
            makeTrade({ pnl: 20, exit_time: '2025-01-02T10:00:00Z' }),
            makeTrade({ pnl: 30, exit_time: '2025-01-03T10:00:00Z' })
        ];
        const rows = buildTradeRows(trades, INITIAL_CAPITAL, null, true);
        // newest first = trade index 2, 1, 0 → _pnl: 30, 20, 10
        expect(rows[0]._pnl).toBe(30);
        expect(rows[1]._pnl).toBe(20);
        expect(rows[2]._pnl).toBe(10);
    });

    it('calculates cumulative pnl correctly', () => {
        const trades = [
            makeTrade({ pnl: 100 }),
            makeTrade({ pnl: 50 }),
            makeTrade({ pnl: -30 })
        ];
        const rows = buildTradeRows(trades, INITIAL_CAPITAL, null, true);
        // cumulative after each: 100, 150, 120
        // rows are newest first: index 2 (cum=120), 1 (cum=150), 0 (cum=100)
        const cumPnls = rows.map((r) => r._cumPnl);
        expect(cumPnls).toEqual([120, 150, 100]);
    });

    it('applies sort when sortKey is provided', () => {
        const trades = [
            makeTrade({ pnl: 10 }),
            makeTrade({ pnl: 50 }),
            makeTrade({ pnl: 30 })
        ];
        const rows = buildTradeRows(trades, INITIAL_CAPITAL, 'pnl', true);
        // ascending sort by pnl
        expect(rows[0]._pnl).toBe(10);
        expect(rows[1]._pnl).toBe(30);
        expect(rows[2]._pnl).toBe(50);
    });

    it('applies descending sort', () => {
        const trades = [
            makeTrade({ pnl: 10 }),
            makeTrade({ pnl: 50 }),
            makeTrade({ pnl: 30 })
        ];
        const rows = buildTradeRows(trades, INITIAL_CAPITAL, 'pnl', false);
        expect(rows[0]._pnl).toBe(50);
        expect(rows[2]._pnl).toBe(10);
    });

    it('count matches trades.length', () => {
        const trades = Array.from({ length: 7 }, (_, i) => makeTrade({ pnl: i * 10 }));
        expect(buildTradeRows(trades, INITIAL_CAPITAL)).toHaveLength(7);
    });
});

// ─── sortRows ─────────────────────────────────────────────────────────────────

describe('sortRows', () => {
    function makeRows() {
        return [
            { _date: 3, _pnl: 30, _mfe: 15, _mae: 5, _cumPnl: 90 },
            { _date: 1, _pnl: 10, _mfe: 5, _mae: 1, _cumPnl: 10 },
            { _date: 2, _pnl: 20, _mfe: 10, _mae: 3, _cumPnl: 30 }
        ];
    }

    it('sorts by pnl ascending', () => {
        const rows = makeRows();
        sortRows(rows, 'pnl', true);
        expect(rows.map((r) => r._pnl)).toEqual([10, 20, 30]);
    });

    it('sorts by pnl descending', () => {
        const rows = makeRows();
        sortRows(rows, 'pnl', false);
        expect(rows.map((r) => r._pnl)).toEqual([30, 20, 10]);
    });

    it('sorts by date ascending', () => {
        const rows = makeRows();
        sortRows(rows, 'date', true);
        expect(rows.map((r) => r._date)).toEqual([1, 2, 3]);
    });

    it('sorts by mfe descending', () => {
        const rows = makeRows();
        sortRows(rows, 'mfe', false);
        expect(rows.map((r) => r._mfe)).toEqual([15, 10, 5]);
    });

    it('sorts by mae ascending', () => {
        const rows = makeRows();
        sortRows(rows, 'mae', true);
        expect(rows.map((r) => r._mae)).toEqual([1, 3, 5]);
    });

    it('sorts by cumPnl descending', () => {
        const rows = makeRows();
        sortRows(rows, 'cumPnl', false);
        expect(rows.map((r) => r._cumPnl)).toEqual([90, 30, 10]);
    });

    it('mutates rows in-place', () => {
        const rows = makeRows();
        const ref = rows;
        sortRows(rows, 'pnl', true);
        expect(rows).toBe(ref);
    });
});

// ─── renderPage ───────────────────────────────────────────────────────────────

describe('renderPage', () => {
    let tbody;
    const rows = Array.from({ length: 30 }, (_, i) => ({ html: `<tr id="r${i}"></tr>` }));

    beforeEach(() => {
        tbody = document.createElement('tbody');
        document.body.appendChild(tbody);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders first 25 rows on page 0', () => {
        renderPage(tbody, rows, 0);
        const trs = tbody.querySelectorAll('tr');
        expect(trs.length).toBe(25);
        expect(trs[0].id).toBe('r0');
        expect(trs[24].id).toBe('r24');
    });

    it('renders remaining rows on page 1', () => {
        renderPage(tbody, rows, 1);
        const trs = tbody.querySelectorAll('tr');
        expect(trs.length).toBe(5); // 30 - 25
        expect(trs[0].id).toBe('r25');
    });

    it('respects custom pageSize', () => {
        renderPage(tbody, rows, 0, 10);
        expect(tbody.querySelectorAll('tr').length).toBe(10);
    });

    it('does nothing when tbody is null', () => {
        expect(() => renderPage(null, rows, 0)).not.toThrow();
    });

    it('renders empty when page beyond range', () => {
        renderPage(tbody, rows, 99);
        expect(tbody.innerHTML).toBe('');
    });
});

// ─── renderPagination ─────────────────────────────────────────────────────────

describe('renderPagination', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'tvTradesContainer';
        document.body.appendChild(container);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('does nothing when container is null', () => {
        expect(() => renderPagination(null, 100, 0)).not.toThrow();
    });

    it('removes pagination when totalTrades <= pageSize', () => {
        // pre-create pagination element to test removal
        const pag = document.createElement('div');
        pag.id = 'tradesPagination';
        document.body.appendChild(pag);
        renderPagination(container, 10, 0);
        expect(document.getElementById('tradesPagination')).toBeNull();
    });

    it('creates pagination element when totalTrades > pageSize', () => {
        renderPagination(container, 100, 0);
        expect(document.getElementById('tradesPagination')).not.toBeNull();
    });

    it('prev button is disabled on first page', () => {
        renderPagination(container, 100, 0);
        const prevBtn = document.getElementById('tradesPrevBtn');
        expect(prevBtn.disabled).toBe(true);
    });

    it('next button is disabled on last page', () => {
        renderPagination(container, 50, 1, 25); // 2 pages, page 1 = last
        const nextBtn = document.getElementById('tradesNextBtn');
        expect(nextBtn.disabled).toBe(true);
    });

    it('shows correct page info text', () => {
        renderPagination(container, 50, 0, 25);
        const info = document.getElementById('tradesPageInfo');
        expect(info.textContent).toContain('1 / 2');
    });

    it('reuses existing pagination element', () => {
        renderPagination(container, 100, 0);
        const first = document.getElementById('tradesPagination');
        renderPagination(container, 100, 1);
        const second = document.getElementById('tradesPagination');
        expect(first).toBe(second);
    });
});

// ─── updatePaginationControls ─────────────────────────────────────────────────

describe('updatePaginationControls', () => {
    let _paginationEl;

    beforeEach(() => {
        document.body.innerHTML = `
      <div id="tradesPagination">
        <button id="tradesPrevBtn"></button>
        <span id="tradesPageInfo"></span>
        <button id="tradesNextBtn"></button>
      </div>`;
        _paginationEl = document.getElementById('tradesPagination');
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('does nothing when paginationEl absent', () => {
        document.body.innerHTML = '';
        expect(() => updatePaginationControls(100, 0)).not.toThrow();
    });

    it('disables prev on page 0', () => {
        updatePaginationControls(100, 0);
        expect(document.getElementById('tradesPrevBtn').disabled).toBe(true);
    });

    it('enables prev on page > 0', () => {
        updatePaginationControls(100, 1);
        expect(document.getElementById('tradesPrevBtn').disabled).toBe(false);
    });

    it('disables next on last page', () => {
        updatePaginationControls(50, 1, 25); // 2 pages, on page 1
        expect(document.getElementById('tradesNextBtn').disabled).toBe(true);
    });

    it('enables next when not on last page', () => {
        updatePaginationControls(100, 0, 25); // 4 pages, on page 0
        expect(document.getElementById('tradesNextBtn').disabled).toBe(false);
    });

    it('updates info text with current page', () => {
        updatePaginationControls(75, 1, 25); // page 2 of 3
        const info = document.getElementById('tradesPageInfo');
        expect(info.innerHTML).toContain('2 / 3');
    });
});

// ─── removePagination ─────────────────────────────────────────────────────────

describe('removePagination', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('removes pagination element', () => {
        const el = document.createElement('div');
        el.id = 'tradesPagination';
        document.body.appendChild(el);
        removePagination();
        expect(document.getElementById('tradesPagination')).toBeNull();
    });

    it('does not throw when element absent', () => {
        expect(() => removePagination()).not.toThrow();
    });
});

// ─── updateSortIndicators ─────────────────────────────────────────────────────

describe('updateSortIndicators', () => {
    beforeEach(() => {
        document.body.innerHTML = `
      <table id="tvTradesListTable">
        <thead>
          <tr>
            <th data-sort="date"><span class="sort-icon"> ⇅</span></th>
            <th data-sort="pnl"><span class="sort-icon"> ⇅</span></th>
            <th data-sort="mfe"><span class="sort-icon"> ⇅</span></th>
          </tr>
        </thead>
      </table>`;
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('sets ▲ on active column when ascending', () => {
        updateSortIndicators('pnl', true);
        const icon = document.querySelector('th[data-sort="pnl"] .sort-icon');
        expect(icon.textContent).toBe(' ▲');
    });

    it('sets ▼ on active column when descending', () => {
        updateSortIndicators('pnl', false);
        const icon = document.querySelector('th[data-sort="pnl"] .sort-icon');
        expect(icon.textContent).toBe(' ▼');
    });

    it('adds sort-active class to active column', () => {
        updateSortIndicators('date', true);
        expect(document.querySelector('th[data-sort="date"]').classList.contains('sort-active')).toBe(true);
    });

    it('removes sort-active from inactive columns', () => {
        // first activate pnl
        document.querySelector('th[data-sort="pnl"]').classList.add('sort-active');
        updateSortIndicators('date', true);
        expect(document.querySelector('th[data-sort="pnl"]').classList.contains('sort-active')).toBe(false);
    });

    it('resets inactive icons to ⇅', () => {
        updateSortIndicators('date', true);
        const icon = document.querySelector('th[data-sort="pnl"] .sort-icon');
        expect(icon.textContent).toBe(' ⇅');
    });

    it('does not throw when table is absent', () => {
        document.body.innerHTML = '';
        expect(() => updateSortIndicators('pnl', true)).not.toThrow();
    });
});
