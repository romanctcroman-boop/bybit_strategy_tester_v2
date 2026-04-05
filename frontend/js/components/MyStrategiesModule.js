/**
 * MyStrategiesModule.js — "My Strategies" modal logic.
 *
 * Extracted from strategy_builder.js during P0-1 refactoring (2026-02-26).
 *
 * Responsibilities:
 *   - fetchStrategiesList()  — GET /api/v1/strategy-builder/strategies
 *   - openMyStrategiesModal() / closeMyStrategiesModal()
 *   - renderStrategiesList() — build strategy cards HTML
 *   - handleStrategyCardAction() — event delegation for open/clone/delete/select
 *   - toggleSelectAll() / updateBatchDeleteUI()
 *   - batchDeleteSelected() / cloneStrategy() / deleteStrategyById()
 *   - filterStrategiesList() — live search filter
 *
 * Usage:
 *   import { createMyStrategiesModule } from './MyStrategiesModule.js';
 *   const myStrat = createMyStrategiesModule({
 *     getStrategyIdFromURL, loadStrategy, showNotification, escapeHtml
 *   });
 *   myStrat.openMyStrategiesModal();
 */

/**
 * @param {Object} deps
 * @param {() => string|null}       deps.getStrategyIdFromURL
 * @param {(id: string) => Promise} deps.loadStrategy
 * @param {(msg: string, type?: string) => void} deps.showNotification
 * @param {(s: string) => string}   deps.escapeHtml
 * @returns {Object} public API
 */
export function createMyStrategiesModule(deps) {
    const { getStrategyIdFromURL, loadStrategy, showNotification, escapeHtml } = deps;

    // ── Module state ──────────────────────────────────────────────────────────
    let _strategiesCache = [];
    const _selectedStrategyIds = new Set();

    // ── fetchStrategiesList ───────────────────────────────────────────────────
    async function fetchStrategiesList() {
        try {
            const resp = await fetch('/api/v1/strategy-builder/strategies?page=1&page_size=100', {
                cache: 'no-store'
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            // Deduplicate by id in case backend returns duplicates (defensive guard)
            const seen = new Set();
            _strategiesCache = (data.strategies || []).filter(s => {
                if (seen.has(s.id)) return false;
                seen.add(s.id);
                return true;
            });
            return _strategiesCache;
        } catch (err) {
            console.error('[My Strategies] Failed to fetch strategies:', err);
            showNotification('Failed to load strategies', 'error');
            return [];
        }
    }

    // ── openMyStrategiesModal ─────────────────────────────────────────────────
    async function openMyStrategiesModal() {
        const modal = document.getElementById('myStrategiesModal');
        if (!modal) return;

        _selectedStrategyIds.clear();
        updateBatchDeleteUI();

        modal.classList.add('active');
        const listEl = document.getElementById('strategiesList');
        if (listEl) listEl.innerHTML = '<p class="text-muted text-center">Loading...</p>';

        const strategies = await fetchStrategiesList();
        renderStrategiesList(strategies);
    }

    // ── closeMyStrategiesModal ────────────────────────────────────────────────
    function closeMyStrategiesModal() {
        const modal = document.getElementById('myStrategiesModal');
        if (modal) modal.classList.remove('active');
        _selectedStrategyIds.clear();
    }

    // ── renderStrategiesList ──────────────────────────────────────────────────
    function renderStrategiesList(strategies) {
        const listEl = document.getElementById('strategiesList');
        const countEl = document.getElementById('strategiesCount');
        if (!listEl) return;

        if (countEl) countEl.textContent = `${strategies.length} strategies`;

        if (strategies.length === 0) {
            listEl.innerHTML = `
        <div class="strategies-empty">
          <i class="bi bi-folder2"></i>
          <p>No saved strategies yet</p>
          <p class="text-sm mt-1">Use the Save button to save your first strategy</p>
        </div>`;
            updateBatchDeleteUI();
            return;
        }

        const currentId = getStrategyIdFromURL();

        listEl.innerHTML = strategies.map(s => {
            const updatedDate = s.updated_at
                ? new Date(s.updated_at).toLocaleDateString('ru-RU', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                })
                : '—';
            const isCurrent = s.id === currentId;
            const isSelected = _selectedStrategyIds.has(s.id);

            return `
        <div class="strategy-card${isCurrent ? ' current' : ''}${isSelected ? ' selected' : ''}" data-strategy-id="${s.id}">
          <div class="strategy-card-checkbox" data-checkbox-id="${s.id}">
            <input type="checkbox" ${isSelected ? 'checked' : ''} data-select-strategy="${s.id}" title="Select" />
          </div>
          <div class="strategy-card-info">
            <div class="strategy-card-name">${escapeHtml(s.name || 'Untitled')}${isCurrent ? ' <span class="badge-current">current</span>' : ''}</div>
            <div class="strategy-card-meta">
              ${s.symbol ? `<span><i class="bi bi-currency-exchange"></i> ${escapeHtml(s.symbol)}</span>` : ''}
              ${s.timeframe ? `<span><i class="bi bi-clock"></i> ${escapeHtml(s.timeframe)}</span>` : ''}
              <span><i class="bi bi-bricks"></i> ${s.block_count || 0} blocks</span>
              <span><i class="bi bi-calendar3"></i> ${updatedDate}</span>
            </div>
          </div>
          <div class="strategy-card-actions">
            <button class="btn-icon-sm" title="Open" data-action="open" data-id="${s.id}">
              <i class="bi bi-box-arrow-in-right"></i>
            </button>
            <button class="btn-icon-sm" title="Clone" data-action="clone" data-id="${s.id}" data-name="${escapeHtml(s.name || 'Untitled')}">
              <i class="bi bi-copy"></i>
            </button>
            <button class="btn-icon-sm btn-danger" title="Delete" data-action="delete" data-id="${s.id}" data-name="${escapeHtml(s.name || 'Untitled')}">
              <i class="bi bi-trash3"></i>
            </button>
          </div>
        </div>`;
        }).join('');

        listEl.removeEventListener('click', handleStrategyCardAction);
        listEl.addEventListener('click', handleStrategyCardAction);

        updateBatchDeleteUI();
    }

    // ── handleStrategyCardAction ──────────────────────────────────────────────
    async function handleStrategyCardAction(e) {
        try {
            const checkboxEl = e.target.closest('[data-select-strategy]');
            if (checkboxEl) {
                e.stopPropagation();
                const strategyId = checkboxEl.dataset.selectStrategy;
                if (checkboxEl.checked) {
                    _selectedStrategyIds.add(strategyId);
                } else {
                    _selectedStrategyIds.delete(strategyId);
                }
                const card = checkboxEl.closest('.strategy-card');
                if (card) card.classList.toggle('selected', checkboxEl.checked);
                updateBatchDeleteUI();
                return;
            }

            if (e.target.closest('.strategy-card-checkbox')) return;

            const actionBtn = e.target.closest('[data-action]');
            if (!actionBtn) {
                const card = e.target.closest('.strategy-card');
                if (card) {
                    const id = card.dataset.strategyId;
                    if (id) {
                        closeMyStrategiesModal();
                        await loadStrategy(id);
                    }
                }
                return;
            }

            const action = actionBtn.dataset.action;
            const id = actionBtn.dataset.id;
            const name = actionBtn.dataset.name || 'Untitled';

            if (action === 'open') {
                closeMyStrategiesModal();
                await loadStrategy(id);
            } else if (action === 'clone') {
                await cloneStrategy(id, name);
            } else if (action === 'delete') {
                await deleteStrategyById(id, name);
            }
        } catch (err) {
            console.error('[My Strategies] handleStrategyCardAction error:', err);
            showNotification(`Ошибка: ${err.message}`, 'error');
        }
    }

    // ── toggleSelectAll ───────────────────────────────────────────────────────
    function toggleSelectAll() {
        const selectAllCb = document.getElementById('strategiesSelectAll');
        const isChecked = selectAllCb?.checked || false;
        const visibleCards = document.querySelectorAll('.strategy-card[data-strategy-id]');

        visibleCards.forEach(card => {
            const strategyId = card.dataset.strategyId;
            const cb = card.querySelector('[data-select-strategy]');
            if (cb) cb.checked = isChecked;
            if (isChecked) {
                _selectedStrategyIds.add(strategyId);
                card.classList.add('selected');
            } else {
                _selectedStrategyIds.delete(strategyId);
                card.classList.remove('selected');
            }
        });

        updateBatchDeleteUI();
    }

    // ── updateBatchDeleteUI ───────────────────────────────────────────────────
    function updateBatchDeleteUI() {
        const btn = document.getElementById('btnBatchDelete');
        const countEl = document.getElementById('batchDeleteCount');
        const selectAllCb = document.getElementById('strategiesSelectAll');

        const count = _selectedStrategyIds.size;
        if (btn) btn.classList.toggle('hidden', count === 0);
        if (countEl) countEl.textContent = count;

        if (selectAllCb) {
            const visibleCards = document.querySelectorAll('.strategy-card[data-strategy-id]');
            const totalVisible = visibleCards.length;
            selectAllCb.checked = totalVisible > 0 && count >= totalVisible;
            selectAllCb.indeterminate = count > 0 && count < totalVisible;
        }
    }

    // ── batchDeleteSelected ───────────────────────────────────────────────────
    async function batchDeleteSelected() {
        const count = _selectedStrategyIds.size;
        if (count === 0) return;

        if (!confirm(`Delete ${count} selected strateg${count === 1 ? 'y' : 'ies'}?\nThis action cannot be undone.`)) return;

        try {
            const resp = await fetch('/api/v1/strategy-builder/strategies/batch-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy_ids: Array.from(_selectedStrategyIds) })
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            console.log(`[SUCCESS] Deleted ${data.deleted_count} strategies`);
            showNotification(`Deleted ${data.deleted_count} strateg${data.deleted_count === 1 ? 'y' : 'ies'}`, 'success');

            _selectedStrategyIds.clear();
            _strategiesCache = [];
            const strategies = await fetchStrategiesList();
            renderStrategiesList(strategies);
            updateBatchDeleteUI();
        } catch (err) {
            console.error('[My Strategies] Batch delete failed:', err);
            showNotification('Failed to delete strategies', 'error');
        }
    }

    // ── cloneStrategy ─────────────────────────────────────────────────────────
    async function cloneStrategy(strategyId, originalName) {
        const newName = `${originalName} (copy)`;
        try {
            const resp = await fetch(
                `/api/v1/strategy-builder/strategies/${strategyId}/clone?new_name=${encodeURIComponent(newName)}`,
                { method: 'POST' }
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            showNotification(`Strategy cloned as "${newName}"`, 'success');
            const strategies = await fetchStrategiesList();
            renderStrategiesList(strategies);
        } catch (err) {
            console.error('[My Strategies] Clone failed:', err);
            showNotification('Failed to clone strategy', 'error');
        }
    }

    // ── deleteStrategyById ────────────────────────────────────────────────────
    async function deleteStrategyById(strategyId, name) {
        if (!confirm(`Delete strategy "${name}"?\nThis action cannot be undone.`)) return;

        try {
            const resp = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`, {
                method: 'DELETE'
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            showNotification(`Strategy "${name}" deleted`, 'success');
            _selectedStrategyIds.delete(strategyId);

            _strategiesCache = [];
            const strategies = await fetchStrategiesList();
            renderStrategiesList(strategies);
            updateBatchDeleteUI();
        } catch (err) {
            console.error('[My Strategies] Delete failed:', err);
            showNotification('Failed to delete strategy', 'error');
        }
    }

    // ── filterStrategiesList ──────────────────────────────────────────────────
    function filterStrategiesList() {
        const query = (document.getElementById('strategiesSearch')?.value || '').toLowerCase().trim();
        if (!query) {
            renderStrategiesList(_strategiesCache);
            return;
        }
        const filtered = (_strategiesCache || []).filter(s =>
            (s.name || '').toLowerCase().includes(query) ||
            (s.symbol || '').toLowerCase().includes(query) ||
            (s.timeframe || '').toLowerCase().includes(query)
        );
        renderStrategiesList(filtered);
    }

    // ── Public API ────────────────────────────────────────────────────────────
    return {
        fetchStrategiesList,
        openMyStrategiesModal,
        closeMyStrategiesModal,
        renderStrategiesList,
        handleStrategyCardAction,
        toggleSelectAll,
        updateBatchDeleteUI,
        batchDeleteSelected,
        cloneStrategy,
        deleteStrategyById,
        filterStrategiesList
    };
}
