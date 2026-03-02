/**
 * 📋 TradesTable — Компонент таблицы сделок
 *
 * Инкапсулирует логику рендеринга, сортировки таблицы сделок
 * в backtest_results.html (вкладка "Список сделок").
 *
 * Extracted from backtest_results.js as part of P0-2 Phase 2 refactoring.
 *
 * @module TradesTable
 * @version 1.1.0
 * @date 2026-02-28
 * @migration P0-2 Phase 2: Extract TradesTable
 * @change 1.1.0: Removed pagination - show all trades in single scrollable list
 */

// Pagination disabled - show all trades in one scrollable list
export const TRADES_PAGE_SIZE = 100000; // Large enough to show all trades

/**
 * Build a display row object from trade data.
 *
 * @param {object} trade           - Trade object from backtest results
 * @param {number} tradeNum        - 1-based trade number
 * @param {number} cumulativePnL   - Running P&L up to this trade (in USD)
 * @param {number} initialCapital  - Used for cumulative P&L % calculation
 * @returns {{ _date, _pnl, _mfe, _mae, _cumPnl, html: string }}
 */
export function buildTradeRow(trade, tradeNum, cumulativePnL, initialCapital = 10000) {
    const isLong = _isLongTrade(trade);
    const typeText = isLong ? 'Long' : 'Short';
    const typeClass = isLong ? 'tv-trade-long' : 'tv-trade-short';

    const pnl = trade.pnl || 0;
    const pnlPct = trade.return_pct || trade.pnl_pct || 0;
    const cumulativePnLPct = (cumulativePnL / initialCapital) * 100;

    const exitSignal = trade.exit_reason || trade.exit_signal ||
        (isLong ? 'Long SL/TP' : 'Short SL/TP');
    const entrySignal = isLong ? 'Long' : 'Short';

    const positionValue = (trade.size || 0) * (trade.entry_price || 0);
    const positionDisplay = positionValue >= 1000
        ? `${(positionValue / 1000).toFixed(2)}K USD`
        : `${positionValue.toFixed(2)} USD`;

    const mfe = Math.abs(trade.mfe ?? trade.mfe_value ?? 0);
    const mfePct = Math.abs(trade.mfe_pct ?? 0);
    const mae = Math.abs(trade.mae ?? trade.mae_value ?? 0);
    const maePct = Math.abs(trade.mae_pct ?? 0);

    const exitDate = trade.exit_time ? new Date(trade.exit_time).getTime() : 0;

    return {
        _date: exitDate,
        _pnl: pnl,
        _mfe: mfe,
        _mae: mae,
        _cumPnl: cumulativePnL,
        html: `
      <tr class="tv-trade-exit-row">
        <td rowspan="2" class="tv-trade-num-cell">
          <span class="tv-trade-number">${tradeNum}</span>
          <span class="${typeClass}">${typeText}</span>
        </td>
        <td class="tv-trade-type-cell">Exit</td>
        <td>${_formatTradeDate(trade.exit_time)}</td>
        <td>${exitSignal}</td>
        <td>${(trade.exit_price || 0).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} <small>USD</small></td>
        <td>
          <div>${trade.size?.toFixed(2) || '0.01'}</div>
          <div class="tv-trade-secondary">${positionDisplay}</div>
        </td>
        <td class="${pnl >= 0 ? 'tv-value-positive' : 'tv-value-negative'}">
          <div>${pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <small>USD</small></div>
          <div class="tv-trade-secondary">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</div>
        </td>
        <td class="tv-value-neutral">
          <div>${mfe.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <small>USD</small></div>
          <div class="tv-trade-secondary">${mfePct.toFixed(2)}%</div>
        </td>
        <td class="${mae > 0 ? 'tv-value-negative' : 'tv-value-neutral'}">
          <div>${mae.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <small>USD</small></div>
          <div class="tv-trade-secondary">${maePct.toFixed(2)}%</div>
        </td>
        <td class="${cumulativePnL >= 0 ? 'tv-value-positive' : 'tv-value-negative'}">
          <div>${cumulativePnL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <small>USD</small></div>
          <div class="tv-trade-secondary">${cumulativePnLPct.toFixed(2)}%</div>
        </td>
      </tr>
      <tr class="tv-trade-entry-row">
        <td class="tv-trade-type-cell">Entry</td>
        <td>${_formatTradeDate(trade.entry_time)}</td>
        <td>${entrySignal}</td>
        <td>${(trade.entry_price || 0).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} <small>USD</small></td>
        <td colspan="5"></td>
      </tr>`
    };
}

/**
 * Build sorted row array from a trades list (newest first by default).
 *
 * @param {object[]} trades         - Array of trade objects
 * @param {number}   initialCapital - For cumulative P&L % calculation
 * @param {string|null} sortKey     - Active sort key (null = no sort = newest first)
 * @param {boolean}  sortAsc        - Sort direction
 * @returns {object[]} rows array with HTML and sort metadata
 */
export function buildTradeRows(trades, initialCapital = 10000, sortKey = null, sortAsc = true) {
    // Calculate cumulative P&L (chronological order)
    let runningPnL = 0;
    const cumulativePnLs = trades.map((t) => {
        runningPnL += t.pnl || 0;
        return runningPnL;
    });

    // Build rows array — newest first (reverse chronological default)
    const rows = [];
    for (let i = trades.length - 1; i >= 0; i--) {
        rows.push(buildTradeRow(trades[i], i + 1, cumulativePnLs[i], initialCapital));
    }

    // Apply sort if active
    if (sortKey) {
        rows.sort((a, b) => {
            const av = a[`_${sortKey}`];
            const bv = b[`_${sortKey}`];
            return sortAsc ? av - bv : bv - av;
        });
    }

    return rows;
}

/**
 * Sort existing rows array by key in-place.
 *
 * @param {object[]} rows    - Rows array from buildTradeRows()
 * @param {string}   key     - Sort key (date|pnl|mfe|mae|cumPnl)
 * @param {boolean}  sortAsc - Ascending = true
 */
export function sortRows(rows, key, sortAsc) {
    rows.sort((a, b) => {
        const av = a[`_${key}`];
        const bv = b[`_${key}`];
        return sortAsc ? av - bv : bv - av;
    });
}

/**
 * Render all trades into a tbody element (no pagination).
 *
 * @param {HTMLElement} tbody       - Target <tbody> element
 * @param {object[]}    cachedRows  - All rows (from buildTradeRows)
 * @param {number}      currentPage - Ignored (no pagination)
 * @param {number}      [pageSize]  - Ignored (show all)
 */
export function renderPage(tbody, cachedRows, currentPage, pageSize = TRADES_PAGE_SIZE) {
    if (!tbody) return;
    // Render all trades at once (no pagination)
    tbody.innerHTML = cachedRows.map((r) => r.html).join('');
}

/**
 * Render or update the pagination controls element.
 * DISABLED: Show all trades in single scrollable list (no pagination).
 *
 * @param {HTMLElement|null} container  - Element to insert pagination after
 * @param {number}           totalTrades
 * @param {number}           currentPage - 0-based
 * @param {number}           [pageSize]
 */
export function renderPagination(container, totalTrades, currentPage, pageSize = TRADES_PAGE_SIZE) {
    // Pagination disabled - always remove pagination controls
    removePagination();
}

/**
 * Update only the pagination control state (buttons + info text) without rebuilding.
 * DISABLED: Show all trades in single scrollable list (no pagination).
 *
 * @param {number} totalRows
 * @param {number} currentPage
 * @param {number} [pageSize]
 */
export function updatePaginationControls(totalRows, currentPage, pageSize = TRADES_PAGE_SIZE) {
    // Pagination disabled - no-op
}

/**
 * Remove pagination element from DOM.
 */
export function removePagination() {
    const el = document.getElementById('tradesPagination');
    if (el) el.remove();
}

/**
 * Update sort indicator arrows in table header cells.
 *
 * @param {string}  activeKey - Current sort key
 * @param {boolean} sortAsc   - Current sort direction
 */
export function updateSortIndicators(activeKey, sortAsc) {
    document.querySelectorAll('#tvTradesListTable th[data-sort]').forEach((th) => {
        const key = th.dataset.sort;
        const icon = th.querySelector('.sort-icon');
        if (!icon) return;
        if (key === activeKey) {
            icon.textContent = sortAsc ? ' ▲' : ' ▼';
            th.classList.add('sort-active');
        } else {
            icon.textContent = ' ⇅';
            th.classList.remove('sort-active');
        }
    });
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/**
 * Detect Long trade from trade object (handles multiple field conventions).
 * @param {object} t
 * @returns {boolean}
 */
function _isLongTrade(t) {
    if (t.direction === 'long' || t.direction === 'Long') return true;
    if (t.side === 'long' || t.side === 'Long' || t.side === 'Buy' || t.side === 'buy') return true;
    if (t.type === 'Длинная' || t.type === 'long') return true;
    return false;
}

/**
 * Format date string like TradingView: "Nov 17, 2025, 21:15"
 * Backend returns UTC timestamps without timezone suffix (e.g. "2026-02-28T08:00:00").
 * Appending "Z" ensures new Date() treats it as UTC and toLocaleString() converts
 * it to the user's local timezone — matching TradingView's UTC+local display.
 * @param {string|null} dateStr
 * @returns {string}
 */
function _formatTradeDate(dateStr) {
    if (!dateStr) return '--';
    // Ensure UTC interpretation: append Z if no timezone info present
    const normalized = (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+') && dateStr.includes('T'))
        ? dateStr + 'Z'
        : dateStr;
    const d = new Date(normalized);
    return d.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    }).replace(',', '');
}
