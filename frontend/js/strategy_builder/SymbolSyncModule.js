/**
 * Symbol Sync Module — Symbol picker, ticker data, DB sync.
 *
 * Extracted from strategy_builder.js (Phase 5 refactor).
 *
 * Handles:
 *   - Bybit symbol list fetching + ticker price/volume data
 *   - Symbol picker dropdown UI (search, sort, local/blocked badges)
 *   - Database panel (kline groups, block/unblock, delete)
 *   - SSE-based candle sync for selected symbol
 *   - Auto-refresh timer per symbol
 *
 * Usage:
 *   const symbolSync = createSymbolSyncModule({ API_BASE, escapeHtml,
 *     showGlobalLoading, hideGlobalLoading, updateRunButtonsState });
 *   symbolSync.initSymbolPicker();
 *   symbolSync.initDunnahBasePanel();
 *   const checkSymbolData = symbolSync.checkSymbolDataForProperties;
 */

import { debounce } from '../utils.js';
import { getStore } from '../core/StateManager.js';

/**
 * @param {object} deps
 * @param {string}   deps.API_BASE
 * @param {function} deps.escapeHtml
 * @param {function} deps.showGlobalLoading
 * @param {function} deps.hideGlobalLoading
 * @param {function} deps.updateRunButtonsState
 */
export function createSymbolSyncModule({
  API_BASE,
  escapeHtml,
  showGlobalLoading,
  hideGlobalLoading,
  updateRunButtonsState
}) {

  // ── Caches ──────────────────────────────────────────────────────────────────

  /** Кэш тикеров Bybit по категории (linear/spot). */
  const bybitSymbolsCache = { linear: [], spot: [] };

  /** Кэш символов с локальными данными в БД. */
  let localSymbolsCache = null;

  /** Кэш тикеров с ценами и объёмами по категории. */
  const tickersDataCache = {};

  /** Список заблокированных тикеров (единый источник для База данных и Symbol picker). */
  let blockedSymbolsCache = null;

  /** Текущая сортировка для symbol picker. */
  const symbolSortConfig = { field: 'name', direction: 'asc' };

  /** Cache for last sync time per symbol to avoid too frequent syncs */
  const symbolSyncCache = {};

  /** Track symbols currently being synced to prevent duplicate requests */
  const symbolSyncInProgress = {};

  /** AbortController for the current sync — отмена при переключении на другой тикер */
  let currentSyncAbortController = null;
  /** Символ и время старта текущего sync — чтобы не прерывать дубликатом от change/debounce */
  let currentSyncSymbol = null;
  let currentSyncStartTime = 0;

  /** Auto-refresh interval IDs per symbol */
  const symbolRefreshTimers = {};

  /** Internal reference to the DB panel refresh function (set by initDunnahBasePanel). */
  let refreshDunnahBasePanel = null;

  // ── Store helpers ────────────────────────────────────────────────────────────

  function _setSBCurrentSyncSymbol(v) {
    const store = getStore();
    if (store) store.set('strategyBuilder.sync.currentSyncSymbol', v);
  }

  function _setSBCurrentSyncStartTime(v) {
    const store = getStore();
    if (store) store.set('strategyBuilder.sync.currentSyncStartTime', v);
  }

  // ── API fetchers ─────────────────────────────────────────────────────────────

  /** Загрузить список заблокированных тикеров (единый источник). */
  async function fetchBlockedSymbols() {
    try {
      const res = await fetch('/api/v1/marketdata/symbols/blocked');
      if (!res.ok) return new Set();
      const data = await res.json();
      const list = (data.symbols || []).map((s) => String(s).toUpperCase());
      blockedSymbolsCache = new Set(list);
      return blockedSymbolsCache;
    } catch (e) {
      console.error('[Strategy Builder] fetchBlockedSymbols failed:', e);
      return blockedSymbolsCache || new Set();
    }
  }

  /** Загрузить тикеры с ценами, 24h%, объёмом. */
  async function fetchTickersData(category = 'linear') {
    const key = category === 'spot' ? 'spot' : 'linear';
    if (tickersDataCache[key] && Object.keys(tickersDataCache[key]).length > 0) {
      return tickersDataCache[key];
    }
    try {
      const res = await fetch(`/api/v1/marketdata/tickers?category=${encodeURIComponent(key)}`);
      if (!res.ok) {
        console.error('[Strategy Builder] fetchTickersData not ok:', res.statusText);
        return {};
      }
      const data = await res.json();
      const map = {};
      (data.tickers || []).forEach((t) => {
        map[t.symbol] = t;
      });
      if (Object.keys(map).length > 0) tickersDataCache[key] = map;
      console.log('[Strategy Builder] Tickers data loaded:', key, Object.keys(map).length);
      return map;
    } catch (e) {
      console.error('[Strategy Builder] fetchTickersData failed:', e);
      return {};
    }
  }

  /**
   * Загрузить список символов с локальными данными.
   * @param {boolean} [force=false] — принудительно обновить с сервера, игнорируя кэш.
   */
  async function fetchLocalSymbols(force = false) {
    if (!force && localSymbolsCache !== null && localSymbolsCache.symbols) {
      return localSymbolsCache;
    }
    try {
      const base = typeof window !== 'undefined' && window.location && window.location.origin
        ? window.location.origin
        : '';
      const url = `${base}/api/v1/marketdata/symbols/local?_=${Date.now()}`;
      const res = await fetch(url, {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' }
      });
      if (!res.ok) {
        console.error('[Strategy Builder] fetchLocalSymbols not ok:', res.statusText);
        return { symbols: [], details: {} };
      }
      const data = await res.json();
      localSymbolsCache = data;
      console.log('[Strategy Builder] Local symbols loaded:', data.symbols?.length || 0, data.symbols);
      return localSymbolsCache;
    } catch (e) {
      console.error('[Strategy Builder] fetchLocalSymbols failed:', e);
      return { symbols: [], details: {} };
    }
  }

  /** Загрузить список тикеров Bybit по типу рынка. */
  async function fetchBybitSymbols(category) {
    const key = category === 'spot' ? 'spot' : 'linear';
    console.log('[Strategy Builder] fetchBybitSymbols called, category:', key);
    if (bybitSymbolsCache[key] && bybitSymbolsCache[key].length > 0) {
      console.log('[Strategy Builder] Returning from cache:', bybitSymbolsCache[key].length, 'symbols');
      return bybitSymbolsCache[key];
    }
    try {
      const base = typeof window !== 'undefined' && window.location && window.location.origin
        ? window.location.origin
        : '';
      const url = `${base}/api/v1/marketdata/symbols-list?category=${key}`;
      console.log('[Strategy Builder] Fetching symbols from:', url);
      const res = await fetch(url);
      console.log('[Strategy Builder] Fetch response status:', res.status);
      if (!res.ok) {
        console.error('[Strategy Builder] Fetch not ok:', res.statusText);
        return [];
      }
      const data = await res.json();
      const list = data.symbols || [];
      console.log('[Strategy Builder] Received symbols:', list.length, 'first 5:', list.slice(0, 5));
      bybitSymbolsCache[key] = Array.isArray(list) ? list : [];
      return bybitSymbolsCache[key];
    } catch (e) {
      console.error('[Strategy Builder] fetchBybitSymbols failed:', e);
      return [];
    }
  }

  // ── Symbol Picker UI ─────────────────────────────────────────────────────────

  /** Позиционировать выпадающий список по полю ввода (fixed), чтобы не обрезался sidebar overflow. */
  function positionSymbolDropdown() {
    const input = document.getElementById('backtestSymbol');
    const dropdown = document.getElementById('backtestSymbolDropdown');
    if (!input || !dropdown || !dropdown.classList.contains('open')) return;

    if (dropdown.parentElement !== document.body) {
      document.body.appendChild(dropdown);
    }

    const rect = input.getBoundingClientRect();
    const maxH = Math.min(400, window.innerHeight - rect.bottom - 24);

    const dropdownWidth = 520;
    let leftPos = rect.left;

    if (leftPos + dropdownWidth > window.innerWidth - 20) {
      leftPos = window.innerWidth - dropdownWidth - 20;
    }
    if (leftPos < 10) {
      leftPos = 10;
    }

    dropdown.style.position = 'fixed';
    dropdown.style.left = `${leftPos}px`;
    dropdown.style.top = `${rect.bottom + 4}px`;
    dropdown.style.width = `${dropdownWidth}px`;
    dropdown.style.minWidth = `${dropdownWidth}px`;
    dropdown.style.maxHeight = `${Math.max(200, maxH)}px`;
    dropdown.style.overflowY = 'auto';
    dropdown.style.zIndex = '100000';
    dropdown.style.display = 'block';
    dropdown.style.visibility = 'visible';
    dropdown.style.pointerEvents = 'auto';
    dropdown.style.background = 'var(--bg-tertiary, #1e1e2e)';
    dropdown.style.border = '1px solid var(--border-color, #444)';
    dropdown.style.borderRadius = '6px';
    dropdown.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.5)';

    dropdown.style.scrollbarWidth = 'thin';
    dropdown.style.scrollbarColor = 'var(--accent-blue, #3b82f6) transparent';
  }

  /** Показать выпадающий список тикеров с фильтром по поиску и сортировкой. */
  function showSymbolDropdown(query, options = {}) {
    const { loading = false, error = null } = options;
    console.log('[Strategy Builder] showSymbolDropdown called:', { query, loading, error });
    const input = document.getElementById('backtestSymbol');
    const dropdown = document.getElementById('backtestSymbolDropdown');
    const marketEl = document.getElementById('builderMarketType');
    if (!input || !dropdown || !marketEl) {
      console.error('[Strategy Builder] showSymbolDropdown: Missing elements');
      return;
    }
    if (error) {
      console.log('[Strategy Builder] showSymbolDropdown: error mode');
      dropdown.innerHTML = '';
      dropdown.classList.remove('open');
      dropdown.setAttribute('aria-hidden', 'true');
      return;
    }
    if (loading) {
      console.log('[Strategy Builder] showSymbolDropdown: loading mode');
      dropdown.innerHTML = '<li class="symbol-picker-item symbol-picker-message">Загрузка тикеров...</li>';
      dropdown.setAttribute('aria-hidden', 'false');
      dropdown.classList.add('open');
      positionSymbolDropdown();
      return;
    }
    const category = marketEl.value === 'spot' ? 'spot' : 'linear';
    const list = bybitSymbolsCache[category] || [];
    const localData = localSymbolsCache || { symbols: [], details: {}, blocked: [] };
    const localSet = new Set(localData.symbols || []);
    const blockedSet = blockedSymbolsCache || new Set((localData.blocked || []).map((s) => String(s).toUpperCase()));
    const tickersData = (tickersDataCache && tickersDataCache[category]) || {};
    console.log('[Strategy Builder] showSymbolDropdown: category =', category, ', cache size =', list.length, ', local symbols =', localSet.size, ', tickers data =', Object.keys(tickersData).length);
    const q = (query || '').toUpperCase().trim();

    const enrichedList = list.map((symbol) => {
      const ticker = tickersData[symbol] || {};
      return {
        symbol,
        isLocal: localSet.has(symbol),
        price: ticker.price || 0,
        change_24h: ticker.change_24h || 0,
        volume_24h: ticker.volume_24h || 0
      };
    });

    const { field, direction } = symbolSortConfig;
    enrichedList.sort((a, b) => {
      if (a.isLocal && !b.isLocal) return -1;
      if (!a.isLocal && b.isLocal) return 1;

      let cmp = 0;
      if (field === 'name') {
        cmp = a.symbol.localeCompare(b.symbol);
      } else if (field === 'price') {
        cmp = a.price - b.price;
      } else if (field === 'change') {
        cmp = a.change_24h - b.change_24h;
      } else if (field === 'volume') {
        cmp = a.volume_24h - b.volume_24h;
      }
      return direction === 'desc' ? -cmp : cmp;
    });

    const filtered = q ? enrichedList.filter((item) => item.symbol.toUpperCase().includes(q)) : enrichedList;
    console.log('[Strategy Builder] showSymbolDropdown: filtered size =', filtered.length);

    if (list.length === 0) {
      console.log('[Strategy Builder] showSymbolDropdown: list is empty, hiding dropdown');
      dropdown.innerHTML = '';
      dropdown.classList.remove('open');
      dropdown.setAttribute('aria-hidden', 'true');
      return;
    }

    const formatPrice = (p) => (p >= 1 ? p.toFixed(2) : p >= 0.0001 ? p.toFixed(6) : p.toExponential(2));
    const formatChange = (c) => {
      const sign = c >= 0 ? '+' : '';
      const color = c >= 0 ? 'var(--success-green, #4caf50)' : 'var(--error-red, #f44336)';
      return `<span style="color: ${color}">${sign}${Number(c).toFixed(2)}%</span>`;
    };
    const formatVolume = (v) => {
      if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
      if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
      if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
      return v.toFixed(0);
    };

    const sortIcon = (fld) => {
      if (symbolSortConfig.field !== fld) return '⇅';
      return symbolSortConfig.direction === 'asc' ? '↑' : '↓';
    };

    const headerRow = `
        <li class="symbol-picker-header-row" style="display: grid; grid-template-columns: minmax(180px, 1fr) 90px 75px 80px; gap: 8px; padding: 8px 12px; background: var(--bg-secondary); border-bottom: 2px solid var(--accent-blue); font-size: 12px; color: var(--text-secondary);">
            <span class="symbol-sort-col" data-sort="name" style="cursor: pointer;" title="Сортировать по названию">Символ ${sortIcon('name')}</span>
            <span class="symbol-sort-col" data-sort="price" style="cursor: pointer; text-align: right;" title="Сортировать по цене">Цена ${sortIcon('price')}</span>
            <span class="symbol-sort-col" data-sort="change" style="cursor: pointer; text-align: right;" title="Сортировать по изменению 24h">24H% ${sortIcon('change')}</span>
            <span class="symbol-sort-col" data-sort="volume" style="cursor: pointer; text-align: right;" title="Сортировать по объёму">Объём ${sortIcon('volume')}</span>
        </li>`;

    const infoText = q ? `Найдено: ${filtered.length} из ${list.length}` : `Всего: ${list.length} (📊 = лок. данные)`;
    const infoRow = `<li class="symbol-picker-info" style="font-size: 10px; color: var(--text-muted); padding: 2px 10px; background: var(--bg-tertiary);">${infoText}</li>`;

    const items = filtered
      .slice(0, 500)
      .map((item) => {
        const details = localData.details?.[item.symbol];
        const intervals = details ? Object.keys(details.intervals || {}).join(', ') : '';
        const isBlocked = blockedSet.has(item.symbol.toUpperCase());
        let badge = item.isLocal ? `<span class="symbol-local-badge" title="Локальные данные: ${intervals}">📊</span>` : '';
        badge += isBlocked
          ? '<span class="symbol-blocked-badge" title="Заблокирован для догрузки">🔒</span>'
          : '<span class="symbol-unblocked-badge" title="Разблокирован">🔓</span>';
        let cls = item.isLocal ? 'symbol-picker-item symbol-has-local' : 'symbol-picker-item';
        if (isBlocked) cls += ' symbol-blocked';
        return `<li class="${cls}" data-symbol="${item.symbol}" tabindex="0" role="option" style="display: grid; grid-template-columns: minmax(180px, 1fr) 90px 75px 80px; gap: 8px; align-items: center; padding: 6px 12px;">
                <span class="symbol-name" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${badge}${item.symbol}</span>
                <span style="text-align: right; font-size: 13px; color: var(--text-primary);">${Number.isFinite(item.price) ? formatPrice(item.price) : '-'}</span>
                <span style="text-align: right; font-size: 13px;">${Number.isFinite(item.change_24h) ? formatChange(item.change_24h) : '-'}</span>
                <span style="text-align: right; font-size: 13px; color: var(--text-primary);">${Number.isFinite(item.volume_24h) ? formatVolume(item.volume_24h) : '-'}</span>
            </li>`;
      })
      .join('');

    dropdown.innerHTML = headerRow + infoRow + (items || '<li class="symbol-picker-item symbol-picker-message">Нет совпадений</li>');
    dropdown.setAttribute('aria-hidden', filtered.length === 0 && !items ? 'true' : 'false');
    dropdown.classList.add('open');

    dropdown.querySelectorAll('.symbol-sort-col').forEach((col) => {
      col.addEventListener('click', (e) => {
        e.stopPropagation();
        const sortField = col.dataset.sort;
        if (symbolSortConfig.field === sortField) {
          symbolSortConfig.direction = symbolSortConfig.direction === 'asc' ? 'desc' : 'asc';
        } else {
          symbolSortConfig.field = sortField;
          symbolSortConfig.direction = sortField === 'name' ? 'asc' : 'desc';
        }
        showSymbolDropdown(query, options);
      });
    });

    console.log('[Strategy Builder] showSymbolDropdown: dropdown opened with', filtered.length, 'items');
    positionSymbolDropdown();
  }

  /** Инициализация поля Symbol: тикеры с Bybit + поиск, привязка к типу рынка. */
  function initSymbolPicker() {
    console.log('[Strategy Builder] initSymbolPicker called');
    const input = document.getElementById('backtestSymbol');
    const dropdown = document.getElementById('backtestSymbolDropdown');
    const marketEl = document.getElementById('builderMarketType');
    console.log('[Strategy Builder] Symbol picker elements:', { input: !!input, dropdown: !!dropdown, marketEl: !!marketEl });
    if (!input || !dropdown || !marketEl) {
      console.error('[Strategy Builder] initSymbolPicker: Missing elements!');
      return;
    }

    function getCategory() {
      return marketEl.value === 'spot' ? 'spot' : 'linear';
    }

    async function loadAndShow() {
      const cat = getCategory();
      const cachedList = bybitSymbolsCache[cat] || [];
      const tickersCached = tickersDataCache[cat] && Object.keys(tickersDataCache[cat]).length > 0;
      if (cachedList.length > 0 && blockedSymbolsCache !== null && tickersCached) {
        showSymbolDropdown(input.value);
        return;
      }
      showSymbolDropdown(input.value, { loading: true });
      try {
        await Promise.all([
          fetchBybitSymbols(cat),
          fetchLocalSymbols(),
          fetchTickersData(cat),
          fetchBlockedSymbols()
        ]);
        showSymbolDropdown(input.value);
      } catch (e) {
        showSymbolDropdown(input.value, { error: 'Ошибка загрузки тикеров. Проверьте сеть.' });
      }
    }

    let _symbolInputTimer = null;

    input.addEventListener('focus', function () {
      loadAndShow();
    });
    input.addEventListener('input', function () {
      clearTimeout(_symbolInputTimer);
      _symbolInputTimer = setTimeout(function () {
        const cat = getCategory();
        const list = bybitSymbolsCache[cat] || [];
        const tickersCached = tickersDataCache[cat] && Object.keys(tickersDataCache[cat]).length > 0;
        if (list.length > 0 && blockedSymbolsCache !== null && tickersCached) showSymbolDropdown(input.value);
        else loadAndShow();
      }, 150);
    });
    input.addEventListener('click', function () {
      const cat = getCategory();
      const tickersCached = tickersDataCache[cat] && Object.keys(tickersDataCache[cat]).length > 0;
      if ((bybitSymbolsCache[cat] || []).length > 0 && blockedSymbolsCache !== null && tickersCached) {
        showSymbolDropdown(input.value);
      } else {
        loadAndShow();
      }
    });
    input.addEventListener('blur', function (e) {
      const related = e.relatedTarget;
      if (related && dropdown.contains(related)) return;
      setTimeout(function () {
        if (!dropdown.classList.contains('open')) return;
        closeSymbolDropdown();
      }, 200);
    });

    function closeSymbolDropdown() {
      const d = document.getElementById('backtestSymbolDropdown');
      if (!d) return;
      d.classList.remove('open');
      d.setAttribute('aria-hidden', 'true');
      d.style.position = '';
      d.style.left = '';
      d.style.top = '';
      d.style.width = '';
      d.style.minWidth = '';
      d.style.maxHeight = '';
      d.style.overflowY = '';
      d.style.zIndex = '';
      d.style.display = 'none';
      d.style.visibility = '';
      d.style.pointerEvents = '';

      const symbolPicker = document.querySelector('.symbol-picker');
      if (symbolPicker && d.parentElement === document.body) {
        symbolPicker.appendChild(d);
      }
    }

    document.addEventListener('click', function (e) {
      const t = e.target;
      if (input.contains(t) || dropdown.contains(t)) return;
      closeSymbolDropdown();
    });

    function onSymbolSelected(sym) {
      input.value = sym;
      closeSymbolDropdown();
      input.blur();
      console.log(`[SymbolPicker] Selected: ${sym}`);
      document.dispatchEvent(new CustomEvent('properties-symbol-selected'));
      if (typeof updateRunButtonsState === 'function') updateRunButtonsState();
      if (typeof checkSymbolDataForProperties === 'function' && checkSymbolDataForProperties.cancel) {
        checkSymbolDataForProperties.cancel();
      }
      runCheckSymbolDataForProperties(true);
    }

    dropdown.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      const item = e.target.closest('.symbol-picker-item');
      if (item && item.dataset.symbol) onSymbolSelected(item.dataset.symbol);
    });

    dropdown.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      const item = e.target.closest('.symbol-picker-item');
      if (item && item.dataset.symbol) onSymbolSelected(item.dataset.symbol);
    });

    dropdown.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        const item = e.target.closest('.symbol-picker-item');
        if (item && item.dataset.symbol) onSymbolSelected(item.dataset.symbol);
      }
    });

    marketEl.addEventListener('change', async function () {
      bybitSymbolsCache.linear = [];
      bybitSymbolsCache.spot = [];
      delete tickersDataCache.linear;
      delete tickersDataCache.spot;
      const cat = getCategory();
      console.log('[Strategy Builder] Market type changed to:', cat, '- preloading symbols');
      try {
        await Promise.all([
          fetchBybitSymbols(cat),
          fetchLocalSymbols(),
          fetchTickersData(cat)
        ]);
        console.log('[Strategy Builder] Symbols preloaded for', cat, ':', bybitSymbolsCache[cat]?.length || 0);
        const sym = input.value?.trim()?.toUpperCase();
        if (sym) {
          delete symbolSyncCache[sym];
          checkSymbolDataForProperties();
        }
      } catch (e) {
        console.warn('[Strategy Builder] Failed to preload symbols:', e);
      }
    });

    const _preloadCat = getCategory();
    Promise.all([
      fetchBybitSymbols(_preloadCat),
      fetchTickersData(_preloadCat),
      fetchLocalSymbols(),
      fetchBlockedSymbols()
    ]).catch(() => { });
  }

  // ── Database panel ───────────────────────────────────────────────────────────

  /** База данных: инициализация панели групп тикеров в БД. */
  function initDunnahBasePanel() {
    const container = document.getElementById('dunnahBaseGroups');
    const btnRefresh = document.getElementById('btnDunnahRefresh');
    if (!container) return;

    async function loadAndRender(attempt = 1) {
      container.innerHTML = '<p class="text-muted text-sm">Загрузка...</p>';
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 15000);
        const res = await fetch(`${API_BASE}/marketdata/symbols/db-groups?_=${Date.now()}`, {
          signal: ctrl.signal,
          cache: 'no-store',
          headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' }
        });
        clearTimeout(t);
        if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
        const data = await res.json();
        const groups = data.groups || [];
        const blocked = new Set((data.blocked || []).map((s) => String(s).toUpperCase()));

        if (groups.length === 0) {
          container.innerHTML = '<p class="text-muted text-sm mb-1">В БД нет тикеров.</p><p class="text-muted text-sm" style="font-size:12px">Выберите тикер в «ОСНОВНЫЕ ПАРАМЕТРЫ» и дождитесь синхронизации.</p>';
          return;
        }

        container.innerHTML = groups
          .map((g) => {
            const sym = (g.symbol || '').trim();
            const mt = g.market_type || 'linear';
            const intervals = Object.keys(g.intervals || {}).filter(i => i !== 'UNKNOWN').sort((a, b) => {
              const order = { '1': 1, '5': 2, '15': 3, '30': 4, '60': 5, '240': 6, 'D': 7, 'W': 8, 'M': 9 };
              return (order[a] || 99) - (order[b] || 99);
            });
            const total = g.total_rows || 0;
            const isBlocked = blocked.has(sym.toUpperCase());
            const tfDisplay = intervals.length > 4
              ? intervals.slice(0, 4).join(', ') + ` +${intervals.length - 4}`
              : intervals.join(', ');

            return `
          <div class="dunnah-group-item" data-symbol="${sym}" data-market="${mt}">
            <div class="dunnah-group-header">
              <span class="dunnah-group-symbol">${sym}</span>
              <span class="dunnah-group-mt">${mt}</span>
              ${isBlocked ? '<span class="dunnah-blocked-badge" title="Заблокирован">🔒</span>' : '<span class="dunnah-unblocked-badge" title="Активен">🔓</span>'}
            </div>
            <div class="dunnah-group-info">${tfDisplay} · ${total.toLocaleString()} свечей</div>
            <div class="dunnah-group-actions">
              <button type="button" class="btn-dunnah-delete" data-symbol="${sym}" data-market="${mt}">🗑️ Удалить</button>
              ${isBlocked
                ? `<button type="button" class="btn-dunnah-unblock" data-symbol="${sym}">🔓 Разблокировать</button>`
                : `<button type="button" class="btn-dunnah-block" data-symbol="${sym}">🔒 Блокировать</button>`
              }
            </div>
          </div>`;
          })
          .join('');

        container.querySelectorAll('.btn-dunnah-delete').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const symbol = btn.dataset.symbol;
            const market = btn.dataset.market || 'linear';
            if (!confirm(`Удалить все данные ${symbol} (${market}) из БД?`)) return;
            btn.disabled = true;
            btn.textContent = '⏳';
            try {
              const r = await fetch(`${API_BASE}/marketdata/symbols/db-groups?symbol=${encodeURIComponent(symbol)}&market_type=${encodeURIComponent(market)}`, { method: 'DELETE' });
              if (!r.ok) throw new Error(await r.text());
              localSymbolsCache = null;
              blockedSymbolsCache = null;
              await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
            } catch (e) {
              console.error(e);
              alert('Ошибка удаления: ' + e.message);
              await loadAndRender();
            }
          });
        });
        container.querySelectorAll('.btn-dunnah-block').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const symbol = btn.dataset.symbol;
            btn.disabled = true;
            btn.textContent = '⏳';
            try {
              const r = await fetch(`${API_BASE}/marketdata/symbols/blocked?symbol=${encodeURIComponent(symbol)}`, { method: 'POST' });
              if (!r.ok) throw new Error(await r.text());
              localSymbolsCache = null;
              blockedSymbolsCache = null;
              await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
            } catch (e) {
              console.error(e);
              alert('Ошибка: ' + e.message);
              await loadAndRender();
            }
          });
        });
        container.querySelectorAll('.btn-dunnah-unblock').forEach((btn) => {
          btn.addEventListener('click', async () => {
            const symbol = btn.dataset.symbol;
            btn.disabled = true;
            btn.textContent = '⏳';
            try {
              const r = await fetch(`${API_BASE}/marketdata/symbols/blocked/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
              if (!r.ok) throw new Error(await r.text());
              localSymbolsCache = null;
              blockedSymbolsCache = null;
              await Promise.all([fetchLocalSymbols(true), fetchBlockedSymbols(), loadAndRender()]);
            } catch (e) {
              console.error(e);
              alert('Ошибка: ' + e.message);
              await loadAndRender();
            }
          });
        });
      } catch (e) {
        console.error('[База данных]', e);
        if (attempt < 2) {
          container.innerHTML = '<p class="text-muted text-sm">Повторная попытка подключения...</p>';
          await new Promise((r) => setTimeout(r, 2000));
          return loadAndRender(attempt + 1);
        }
        const msg = e.name === 'AbortError' ? 'Таймаут запроса (15 с)' : e.message;
        container.innerHTML = `<p class="text-danger text-sm">Ошибка: ${escapeHtml(msg)}</p><p class="text-muted text-sm" style="font-size:12px">Проверьте, что сервер запущен. Нажмите «Обновить» для повтора.</p>`;
      }
    }

    if (btnRefresh) btnRefresh.addEventListener('click', () => loadAndRender());
    refreshDunnahBasePanel = loadAndRender;

    let _dunnahPanelLoaded = false;
    document.addEventListener('floatingWindowToggle', function (e) {
      if (e.detail.windowId === 'floatingWindowDatabase' && e.detail.isOpen && !_dunnahPanelLoaded) {
        _dunnahPanelLoaded = true;
        loadAndRender();
      }
    });
    const _origRefresh = loadAndRender;
    refreshDunnahBasePanel = function () {
      _dunnahPanelLoaded = true;
      return _origRefresh();
    };
  }

  // ── Sync progress UI ─────────────────────────────────────────────────────────

  function updatePropertiesProgressBar(visible, options = {}) {
    const { indeterminate = false, percent = 0 } = options;
    const progressContainer = document.getElementById('propertiesCandleLoadingProgress');
    const bar = document.getElementById('propertiesCandleLoadingBar');
    if (!progressContainer || !bar) return;
    if (visible) {
      progressContainer.classList.remove('hidden');
      bar.classList.toggle('indeterminate', indeterminate);
      bar.style.width = indeterminate ? '' : `${percent}%`;
      bar.setAttribute('aria-valuenow', percent);
    } else {
      progressContainer.classList.add('hidden');
      bar.classList.remove('indeterminate');
    }
  }

  /**
   * Render data sync status in Properties panel.
   * States: checking, syncing, synced, error
   */
  function renderPropertiesDataStatus(state, data = {}) {
    const statusIndicator = document.getElementById('propertiesDataStatusIndicator');
    if (!statusIndicator) return;

    const { symbol = '', totalNew = 0, message = '', step = 0, totalSteps = 8 } = data;

    if (state === 'checking') {
      statusIndicator.className = 'data-status checking';
      statusIndicator.innerHTML = `<span class="status-icon">🔍</span><span class="status-text">Проверка ${escapeHtml(symbol)}...</span>`;
    } else if (state === 'syncing') {
      const progressText = totalSteps > 0 ? ` (${step}/${totalSteps})` : '';
      const newText = totalNew > 0 ? `<br><small>Загружено: +${totalNew} свечей</small>` : '';
      statusIndicator.className = 'data-status loading';
      statusIndicator.innerHTML = `<span class="status-icon">📥</span><span class="status-text">${escapeHtml(message) || 'Синхронизация...'}${progressText}${newText}</span>`;
    } else if (state === 'syncing_background') {
      statusIndicator.className = 'data-status loading';
      statusIndicator.innerHTML = `<span class="status-icon">⏳</span><span class="status-text">${escapeHtml(message) || 'Синхронизация в фоне...'}<br><small>Загрузка исторических данных может занять время</small></span>`;
    } else if (state === 'synced') {
      const icon = totalNew > 0 ? '✅' : '✓';
      const text = totalNew > 0 ? `Синхронизировано, +${totalNew} свечей` : 'Данные актуальны';
      statusIndicator.className = 'data-status available';
      statusIndicator.innerHTML = `<span class="status-icon">${icon}</span><span class="status-text">${text}<br><small>TF: 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W, 1M</small></span>`;
    } else if (state === 'blocked') {
      statusIndicator.className = 'data-status';
      statusIndicator.innerHTML = `<span class="status-icon">🔒</span><span class="status-text">${escapeHtml(message) || 'Тикер заблокирован для догрузки'}<br><small>Разблокируйте в «База данных»</small></span>`;
    } else if (state === 'error') {
      statusIndicator.className = 'data-status error';
      statusIndicator.style.cursor = 'pointer';
      statusIndicator.innerHTML = `<span class="status-icon">⚠️</span><span class="status-text">Ошибка синхронизации<br><small>${escapeHtml(message) || 'Проверьте соединение'}. Кликните для повтора.</small></span>`;
      statusIndicator.onclick = function () {
        statusIndicator.onclick = null;
        statusIndicator.style.cursor = '';
        syncSymbolData(true);
      };
    }
  }

  // ── Sync logic ───────────────────────────────────────────────────────────────

  /**
   * Get refresh interval in ms based on timeframe (auto-actualization).
   * 1m, 5m -> 5 min; 15m -> 15 min; 30m -> 30 min; 1h -> 1h; 4h -> 4h; D -> 1d; W -> 1w
   */
  function getRefreshIntervalForTF(tf) {
    const tfIntervals = {
      '1': 5 * 60 * 1000, '5': 5 * 60 * 1000, '15': 15 * 60 * 1000, '30': 30 * 60 * 1000,
      '60': 60 * 60 * 1000, '240': 4 * 60 * 60 * 1000,
      'D': 24 * 60 * 60 * 1000, 'W': 7 * 24 * 60 * 60 * 1000,
      'M': 30 * 24 * 60 * 60 * 1000
    };
    return tfIntervals[tf] || 60 * 60 * 1000;
  }

  /**
   * Sync all timeframes for selected symbol using SSE for real-time progress.
   * Called when symbol is selected or periodically for auto-refresh.
   */
  async function syncSymbolData(forceRefresh = false) {
    const symbolEl = document.getElementById('backtestSymbol');
    const marketEl = document.getElementById('builderMarketType');
    const statusRow = document.getElementById('propertiesDataStatusRow');

    const symbol = symbolEl?.value?.trim()?.toUpperCase();
    const marketType = marketEl?.value === 'spot' ? 'spot' : 'linear';

    if (!symbol || !statusRow) return;

    if ((blockedSymbolsCache || new Set()).has(symbol?.toUpperCase?.() ?? '')) {
      console.log(`[DataSync] ${symbol} is blocked, skipping auto-sync`);
      renderPropertiesDataStatus('blocked', { symbol, message: 'Тикер заблокирован для догрузки' });
      return;
    }

    if (symbolSyncInProgress[symbol]) {
      console.log(`[DataSync] ${symbol} sync already in progress, skipping`);
      return;
    }

    const DUPLICATE_SYNC_GRACE_MS = 600;
    if (currentSyncAbortController && currentSyncSymbol === symbol && Date.now() - currentSyncStartTime < DUPLICATE_SYNC_GRACE_MS) {
      console.log('[DataSync] Same symbol sync in progress, skipping duplicate (change/debounce)');
      return;
    }

    if (currentSyncAbortController && currentSyncSymbol !== symbol) {
      console.log(`[DataSync] Aborting previous sync (switched symbol ${currentSyncSymbol} -> ${symbol})`);
      currentSyncAbortController.abort();
      currentSyncAbortController = null;
    }

    const SYNC_CACHE_MS = 10000;
    const lastSync = symbolSyncCache[symbol];
    if (!forceRefresh && lastSync && Date.now() - lastSync < SYNC_CACHE_MS) {
      console.log(`[DataSync] ${symbol} synced recently, skipping`);
      return;
    }

    symbolSyncInProgress[symbol] = true;

    statusRow.classList.remove('hidden');
    renderPropertiesDataStatus('checking', { symbol });
    updatePropertiesProgressBar(true, { indeterminate: true });

    showGlobalLoading(`Синхронизация ${symbol}...`);

    const controller = new AbortController();
    currentSyncAbortController = controller;
    currentSyncSymbol = symbol;
    currentSyncStartTime = Date.now();
    _setSBCurrentSyncSymbol(symbol);
    _setSBCurrentSyncStartTime(currentSyncStartTime);
    const SYNC_INACTIVITY_TIMEOUT_MS = 90000;
    let timeoutId = setTimeout(() => controller.abort(), SYNC_INACTIVITY_TIMEOUT_MS);

    const resetSyncTimeout = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => controller.abort(), SYNC_INACTIVITY_TIMEOUT_MS);
    };

    try {
      const totalSteps = 9;
      renderPropertiesDataStatus('syncing', {
        symbol,
        message: 'Синхронизация БД с биржей...',
        step: 0,
        totalSteps
      });
      updatePropertiesProgressBar(true, { indeterminate: false, percent: 0 });

      const streamUrl = `${API_BASE}/marketdata/symbols/sync-all-tf-stream?symbol=${encodeURIComponent(symbol)}&market_type=${marketType}`;
      console.log('[DataSync] Starting sync (stream):', streamUrl);

      const response = await fetch(streamUrl, { signal: controller.signal });

      if (!response.ok) {
        clearTimeout(timeoutId);
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let result = null;

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        resetSyncTimeout();
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const chunk of lines) {
          if (!chunk.trim()) continue;
          const dataLine = chunk.split('\n').find(l => l.startsWith('data:'));
          if (!dataLine) continue;
          try {
            const event = JSON.parse(dataLine.slice(5));
            if (event.type === 'progress') {
              renderPropertiesDataStatus('syncing', {
                symbol,
                message: event.message || `Обработка ${event.timeframe}...`,
                step: event.step || 0,
                totalSteps: event.total_steps || totalSteps,
                totalNew: event.new_candles || 0
              });
              if (event.total_steps && event.step) {
                updatePropertiesProgressBar(true, { indeterminate: false, percent: Math.round((event.step / event.total_steps) * 100) });
              }
            } else if (event.type === 'background_sync') {
              renderPropertiesDataStatus('syncing_background', { message: event.message });
            } else if (event.type === 'complete' || event.type === 'result') {
              result = event;
            }
          } catch (parseErr) {
            console.warn('[DataSync] Failed to parse SSE event:', parseErr);
          }
        }
      }

      if (!result) result = {};

      console.log('[DataSync] Sync complete:', result);

      symbolSyncCache[symbol] = Date.now();
      updatePropertiesProgressBar(false);

      const timeframes = result.timeframes || {};
      const timeoutTfs = Object.entries(timeframes).filter(([, v]) => v && v.status === 'timeout').map(([tf]) => tf);
      const errorTfs = Object.entries(timeframes).filter(([, v]) => v && v.status === 'error').map(([tf]) => tf);
      const failedTfs = [...new Set([...timeoutTfs, ...errorTfs])];
      const totalNew = result.total_new_candles || 0;
      if (failedTfs.length > 0) {
        renderPropertiesDataStatus('synced', {
          symbol,
          totalNew,
          message: `Синхронизировано частично: ${failedTfs.join(', ')} не удалось (сеть). Остальные TF готовы. Кликните для повторной попытки.`
        });
      } else {
        renderPropertiesDataStatus('synced', {
          symbol,
          totalNew,
          message: result.summary || 'Данные синхронизированы'
        });
      }

      hideGlobalLoading();
      setupAutoRefresh(symbol);
      if (typeof refreshDunnahBasePanel === 'function') refreshDunnahBasePanel();

    } catch (e) {
      clearTimeout(timeoutId);

      const currentSymbol = document.getElementById('backtestSymbol')?.value?.trim()?.toUpperCase();
      const wasAbortedBySwitch = e.name === 'AbortError' && currentSymbol !== symbol;

      if (wasAbortedBySwitch) {
        console.log(`[DataSync] ${symbol} sync aborted (switched to ${currentSymbol})`);
        return;
      }

      if (e.name === 'AbortError') {
        console.log('[DataSync] Sync timeout — no SSE events for 90s');
        updatePropertiesProgressBar(false);
        renderPropertiesDataStatus('error', {
          message: 'Потеря связи с сервером (нет данных 90 сек). Кликните для повторной попытки.'
        });
        hideGlobalLoading();
        return;
      }

      console.error('[DataSync] Sync failed:', e);
      updatePropertiesProgressBar(false);
      renderPropertiesDataStatus('error', { message: e.message });
      hideGlobalLoading();
    } finally {
      if (currentSyncAbortController === controller) {
        currentSyncAbortController = null;
        currentSyncSymbol = null;
        _setSBCurrentSyncSymbol(null);
      }
      delete symbolSyncInProgress[symbol];
    }
  }

  /**
   * Setup auto-refresh timer for the current symbol based on selected TF.
   * Clears any previous timers (only one symbol is active at a time).
   */
  function setupAutoRefresh(symbol) {
    const tfEl = document.getElementById('strategyTimeframe');
    const tf = tfEl?.value || '15';

    for (const sym of Object.keys(symbolRefreshTimers)) {
      clearInterval(symbolRefreshTimers[sym]);
      delete symbolRefreshTimers[sym];
    }

    const interval = getRefreshIntervalForTF(tf);
    const intervalMin = interval / 60000;
    console.log(`[DataSync] Auto-refresh for ${symbol} every ${intervalMin} min (TF=${tf})`);

    symbolRefreshTimers[symbol] = setInterval(() => {
      console.log(`[DataSync] Auto-refresh triggered for ${symbol}`);
      syncSymbolData(true);
    }, interval);
  }

  /**
   * Main function called when symbol or TF changes.
   * Triggers data sync for the selected symbol.
   * @param {boolean} [forceRefresh=false]
   */
  async function runCheckSymbolDataForProperties(forceRefresh = false) {
    await syncSymbolData(forceRefresh);
  }

  // Debounced version — 200 ms
  const checkSymbolDataForProperties = debounce(runCheckSymbolDataForProperties, 200);

  // Expose for global button click (forceRefreshTickerData button in HTML)
  window.forceRefreshTickerData = function () {
    syncSymbolData(true);
  };

  // ── Public API ───────────────────────────────────────────────────────────────

  return {
    initSymbolPicker,
    initDunnahBasePanel,
    syncSymbolData,
    setupAutoRefresh,
    runCheckSymbolDataForProperties,
    checkSymbolDataForProperties,
    fetchBlockedSymbols,
    fetchTickersData,
    fetchLocalSymbols,
    fetchBybitSymbols,
    getBybitSymbolsCache: () => bybitSymbolsCache,
    getLocalSymbolsCache: () => localSymbolsCache,
    getBlockedSymbolsCache: () => blockedSymbolsCache,
    getTickersDataCache: () => tickersDataCache
  };
}
