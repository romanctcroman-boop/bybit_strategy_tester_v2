/**
 * 📦 SaveLoadModule
 *
 * Strategy save, auto-save, load, version history, and legacy migration
 * for the Strategy Builder. Extracted from strategy_builder.js during P0-1 refactoring.
 *
 * @module SaveLoadModule
 * @version 1.0.0
 * @date 2026-02-26
 */

/**
 * Create a SaveLoadModule instance.
 *
 * @param {object} deps
 * @param {function(): object[]}   deps.getBlocks            - Returns current strategyBlocks array
 * @param {function(): object[]}   deps.getConnections       - Returns current connections array
 * @param {function(object[]): void} deps.setBlocks          - Replaces strategyBlocks in state
 * @param {function(object[]): void} deps.setConnections     - Replaces connections in state
 * @param {function(): string|null} deps.getStrategyIdFromURL - Reads ?id= from URL
 * @param {function(string, string): void} deps.showNotification - Toast notification
 * @param {function(): void}       deps.renderBlocks         - Re-renders canvas blocks
 * @param {function(): void}       deps.renderConnections    - Re-renders canvas connections/wires
 * @param {function(): void}       deps.normalizeAllConnections - Normalises all connection geometry
 * @param {function(): void}       deps.syncStrategyNameDisplay - Syncs strategy name header
 * @param {function(): void}       deps.renderBlockProperties - Re-renders properties panel
 * @param {function(): void}       deps.pushUndo             - Pushes current state to undo stack
 * @param {function(): void}       deps.createMainStrategyNode - Creates default main node
 * @param {function(object): object} deps.getBlockLibrary    - Returns block library object
 * @param {function(): void}       deps.updateRunButtonsState - Updates action buttons state
 * @param {function(): void}       deps.runCheckSymbolDataForProperties - Triggers data sync
 * @param {function(): void}       deps.updateBacktestLeverageDisplay - Updates leverage UI
 * @param {function(): void}       deps.updateBacktestPositionSizeInput - Updates position size UI
 * @param {function(): void}       deps.updateBacktestLeverageRisk - Updates leverage risk UI
 * @param {function(object[]): void} deps.setNoTradeDaysInUI - Sets no-trade-days checkboxes
 * @param {function(): object}     deps.getNoTradeDaysFromUI - Gets no-trade-days from checkboxes
 * @param {function(): string}     deps.normalizeTimeframeForDropdown - Maps TF values for dropdown
 * @param {function(): string|null} deps.getLastAutoSavePayload - Gets last autosave payload
 * @param {function(string|null): void} deps.setLastAutoSavePayload - Sets last autosave payload
 * @param {function(): boolean}    deps.getSkipNextAutoSave  - Gets skip-autosave flag
 * @param {function(boolean): void} deps.setSkipNextAutoSave - Sets skip-autosave flag
 * @param {function(): void}       deps.closeBlockParamsPopup - Closes block params popup
 * @param {function(): object}     deps.wsValidation         - WebSocket validation module ref
 * @param {function(): number}     deps.getZoom              - Gets current canvas zoom
 * @param {function(string): string} deps.escapeHtml         - Escapes HTML entities
 * @param {function(string): string} deps.formatDate         - Formats an ISO date string
 * @returns {object} Public API
 */
export function createSaveLoadModule({
    getBlocks,
    getConnections,
    setBlocks,
    setConnections,
    getStrategyIdFromURL,
    showNotification,
    renderBlocks,
    renderConnections,
    normalizeAllConnections,
    syncStrategyNameDisplay,
    // eslint-disable-next-line no-unused-vars
    renderBlockProperties,
    pushUndo,
    createMainStrategyNode,
    getBlockLibrary,
    updateRunButtonsState,
    runCheckSymbolDataForProperties,
    updateBacktestLeverageDisplay,
    updateBacktestPositionSizeInput,
    updateBacktestLeverageRisk,
    setNoTradeDaysInUI,
    getNoTradeDaysFromUI,
    normalizeTimeframeForDropdown,
    getLastAutoSavePayload,
    setLastAutoSavePayload,
    getSkipNextAutoSave,
    setSkipNextAutoSave,
    closeBlockParamsPopup,
    wsValidation,
    getZoom,
    escapeHtml,
    formatDate
}) {

    // -----------------------------------------------
    // Save
    // -----------------------------------------------

    /**
     * Save strategy to the backend (PUT if existing, POST if new).
     * Falls back to localStorage draft when offline.
     */
    async function saveStrategy() {
        console.log('[SaveLoadModule] saveStrategy called');

        if (!navigator.onLine) {
            showNotification('Нет подключения к сети. Стратегия сохранена в черновик (localStorage).', 'warning');
            autoSaveStrategy().catch((err) =>
                console.warn('[SaveLoadModule] Offline autosave error:', err)
            );
            return;
        }

        const strategy = buildStrategyPayload();

        if (!strategy.name || strategy.name.trim() === '') {
            showNotification('Название стратегии обязательно', 'error');
            return;
        }
        if (!strategy.blocks || strategy.blocks.length === 0) {
            showNotification('Стратегия должна иметь хотя бы один блок', 'warning');
        }

        // WebSocket server-side validation before save
        if (wsValidation && wsValidation.isWsConnected()) {
            let wsTimedOut = false;
            const wsValidationResult = await new Promise((resolve) => {
                const timeoutId = setTimeout(() => {
                    wsTimedOut = true;
                    resolve({ valid: true, fallback: true });
                }, 3000);
                wsValidation.validateStrategy(strategy.blocks, strategy.connections, (result) => {
                    clearTimeout(timeoutId);
                    resolve(result);
                });
            });

            if (wsTimedOut) {
                showNotification('Серверная валидация недоступна (таймаут). Сохранение без проверки.', 'warning');
            }

            if (!wsValidationResult.fallback && !wsValidationResult.valid) {
                const errorCount = wsValidationResult.messages?.filter(m => m.severity === 'error').length || 0;
                const warningCount = wsValidationResult.messages?.filter(m => m.severity === 'warning').length || 0;

                if (errorCount > 0) {
                    const errorMsgs = wsValidationResult.messages
                        .filter(m => m.severity === 'error')
                        .map(m => m.message)
                        .slice(0, 3)
                        .join('\n• ');
                    showNotification(`Валидация не пройдена (${errorCount} ошибок):\n• ${errorMsgs}`, 'error');
                    return;
                } else if (warningCount > 0) {
                    const warningMsgs = wsValidationResult.messages
                        .filter(m => m.severity === 'warning')
                        .map(m => m.message)
                        .slice(0, 3)
                        .join('\n• ');
                    if (!confirm(`Обнаружены предупреждения (${warningCount}):\n• ${warningMsgs}\n\nСохранить всё равно?`)) {
                        return;
                    }
                }
            }
        }

        try {
            const strategyId = getStrategyIdFromURL();
            let finalStrategyId = strategyId;

            if (strategyId) {
                try {
                    const checkResponse = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`);
                    if (!checkResponse.ok) {
                        finalStrategyId = null;
                    }
                } catch {
                    finalStrategyId = null;
                }
            }

            const method = finalStrategyId ? 'PUT' : 'POST';
            const url = finalStrategyId
                ? `/api/v1/strategy-builder/strategies/${finalStrategyId}`
                : '/api/v1/strategy-builder/strategies';

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(strategy)
            });

            if (response.ok) {
                const data = await response.json();
                _updateLastSaved(data.updated_at || new Date().toISOString());
                showNotification('Стратегия успешно сохранена!', 'success');

                const savedId = finalStrategyId || data.id;
                if (savedId) {
                    _clearLocalStorageDraft(savedId);
                }
                if (!finalStrategyId && data.id) {
                    window.history.pushState({}, '', `?id=${data.id}`);
                }
            } else {
                const errorText = await response.text();
                let errorDetail = 'Unknown error';
                try {
                    const errorJson = JSON.parse(errorText);
                    errorDetail = errorJson.detail || errorJson.message || errorText;
                } catch {
                    errorDetail = errorText || `HTTP ${response.status}`;
                }
                showNotification(`Ошибка сохранения стратегии: ${errorDetail}`, 'error');
            }
        } catch (err) {
            showNotification(`Не удалось сохранить стратегию: ${err.message}`, 'error');
        }
    }

    /**
     * Build the strategy payload object from current state + form DOM.
     * @returns {object} Strategy payload
     */
    function buildStrategyPayload() {
        const nameEl = document.getElementById('strategyName');
        const timeframeEl = document.getElementById('strategyTimeframe');
        const marketTypeEl = document.getElementById('builderMarketType');
        const directionEl = document.getElementById('builderDirection');
        const symbolEl = document.getElementById('strategySymbol');
        const backtestSymbolEl = document.getElementById('backtestSymbol');
        const backtestCapitalEl = document.getElementById('backtestCapital');

        const symbol = symbolEl?.value || backtestSymbolEl?.value || 'BTCUSDT';
        const initialCapital = parseFloat(backtestCapitalEl?.value || 10000);

        const backtestLeverageEl = document.getElementById('backtestLeverage');
        const backtestPositionSizeTypeEl = document.getElementById('backtestPositionSizeType');
        const backtestPositionSizeEl = document.getElementById('backtestPositionSize');
        const leverage = parseInt(backtestLeverageEl?.value, 10) || 10;
        const positionSizeType = backtestPositionSizeTypeEl?.value || 'percent';
        const positionSizeVal = parseFloat(backtestPositionSizeEl?.value) || 100;
        const noTradeDays = getNoTradeDaysFromUI();

        const blocks = getBlocks();
        const connections = getConnections();

        return {
            name: nameEl?.value || 'New Strategy',
            description: '',
            timeframe: timeframeEl?.value || '15',
            symbol,
            market_type: marketTypeEl?.value || 'linear',
            direction: directionEl?.value || 'both',
            initial_capital: initialCapital,
            leverage,
            position_size: positionSizeType === 'percent' ? positionSizeVal / 100 : positionSizeVal,
            parameters: {
                _position_size_type: positionSizeType,
                _order_amount: positionSizeType === 'fixed_amount' ? positionSizeVal : undefined,
                _no_trade_days: noTradeDays.length ? noTradeDays : undefined,
                _commission: parseFloat(document.getElementById('backtestCommission')?.value || '0.07') / 100,
                _slippage: parseFloat(document.getElementById('backtestSlippage')?.value || '0') / 100,
                _pyramiding: parseInt(document.getElementById('backtestPyramiding')?.value || '1', 10) || 1,
                _start_date: document.getElementById('backtestStartDate')?.value || '2025-01-01',
                _end_date: document.getElementById('backtestEndDate')?.value || new Date().toISOString().slice(0, 10)
            },
            blocks: blocks.map(b => ({
                id: b.id,
                type: b.type,
                category: b.category,
                name: b.name,
                icon: b.icon,
                x: b.x,
                y: b.y,
                isMain: b.isMain || false,
                params: b.params || {},
                optimizationParams: b.optimizationParams || {}
            })),
            connections: connections.map(c => ({
                id: c.id,
                source: c.source,
                target: c.target,
                type: c.type || 'data'
            })),
            uiState: {
                zoom: getZoom(),
                strategyName: nameEl?.value || 'New Strategy',
                savedAt: new Date().toISOString()
            }
        };
    }

    // -----------------------------------------------
    // Auto-save
    // -----------------------------------------------

    /**
     * Auto-save to localStorage (always) and to backend (when strategy has an ID).
     */
    async function autoSaveStrategy() {
        try {
            if (getSkipNextAutoSave()) {
                setSkipNextAutoSave(false);
                console.log('[SaveLoadModule] Skipping autosave after reset');
                return;
            }

            const strategyId = getStrategyIdFromURL() || 'draft';
            const payload = buildStrategyPayload();

            if (!payload.blocks.length && !getConnections().length) return;
            if (payload.blocks.length === 1 && payload.blocks[0].type === 'strategy' && !getConnections().length) {
                console.log('[SaveLoadModule] Skipping autosave - clean initial state');
                return;
            }

            const serialized = JSON.stringify(payload);
            if (serialized === getLastAutoSavePayload()) return;
            setLastAutoSavePayload(serialized);

            try {
                const key = `strategy_builder_draft_${strategyId}`;
                window.localStorage.setItem(key, serialized);
            } catch (e) {
                console.warn('[SaveLoadModule] LocalStorage autosave failed:', e);
            }

            if (strategyId !== 'draft') {
                if (!navigator.onLine) {
                    console.warn('[SaveLoadModule] Autosave skipped — browser is offline');
                    return;
                }
                const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
                const response = await fetch(url, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: serialized
                });
                if (response.ok) {
                    const data = await response.json();
                    _updateLastSaved(data.updated_at || new Date().toISOString());
                } else {
                    console.warn('[SaveLoadModule] Autosave PUT failed', await response.text());
                }
            }
        } catch (err) {
            console.warn('[SaveLoadModule] Autosave failed:', err);
        }
    }

    // -----------------------------------------------
    // Legacy migration
    // -----------------------------------------------

    /**
     * Convert legacy tp_percent + sl_percent blocks into a single static_sltp block.
     * @param {object[]} blocks
     * @returns {object[]} Migrated blocks array
     */
    function migrateLegacyBlocks(blocks) {
        const tpBlock = blocks.find(b => b.type === 'tp_percent');
        const slBlock = blocks.find(b => b.type === 'sl_percent');
        if (!tpBlock && !slBlock) return blocks;

        const tpParams = tpBlock?.params || tpBlock?.config || {};
        const slParams = slBlock?.params || slBlock?.config || {};
        const mergedParams = {
            take_profit_percent: tpParams.take_profit_percent ?? 1.5,
            stop_loss_percent: slParams.stop_loss_percent ?? 1.5,
            close_only_in_profit: false,
            activate_breakeven: false,
            breakeven_activation_percent: 0.5,
            new_breakeven_sl_percent: 0.1
        };

        const refBlock = tpBlock || slBlock;
        const staticSltpBlock = {
            id: refBlock.id,
            type: 'static_sltp',
            name: 'Static SL/TP',
            x: refBlock.x,
            y: refBlock.y,
            params: mergedParams,
            config: mergedParams
        };

        const filtered = blocks.filter(b => b.type !== 'tp_percent' && b.type !== 'sl_percent');
        filtered.push(staticSltpBlock);
        console.log('[SaveLoadModule] Converted tp_percent + sl_percent → static_sltp', mergedParams);
        return filtered;
    }

    // -----------------------------------------------
    // Load
    // -----------------------------------------------

    /**
     * Load a strategy from the backend by ID and populate the canvas.
     * @param {string} strategyId
     */
    async function loadStrategy(strategyId) {
        closeBlockParamsPopup();
        // Prevent autosave from firing during load (connections not yet restored)
        setSkipNextAutoSave(true);

        try {
            const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
            const response = await fetch(url);

            if (!response.ok) {
                if (response.status === 404) {
                    showNotification('Стратегия не найдена. Возможно, это не Strategy Builder стратегия.', 'error');
                    return;
                }
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const strategy = await response.json();

            // Populate form fields
            document.getElementById('strategyName').value = strategy.name || 'New Strategy';
            syncStrategyNameDisplay();

            if (document.getElementById('strategyTimeframe')) {
                document.getElementById('strategyTimeframe').value =
                    normalizeTimeframeForDropdown(strategy.timeframe) || '15';
            }
            if (document.getElementById('builderMarketType')) {
                document.getElementById('builderMarketType').value = strategy.market_type || 'linear';
            }
            if (document.getElementById('builderDirection')) {
                document.getElementById('builderDirection').value = strategy.direction || 'both';
            }

            const backtestSymbol = document.getElementById('backtestSymbol');
            const backtestCapital = document.getElementById('backtestCapital');
            const backtestLeverage = document.getElementById('backtestLeverage');
            const backtestLeverageRange = document.getElementById('backtestLeverageRange');
            if (backtestSymbol) backtestSymbol.value = strategy.symbol || 'BTCUSDT';
            if (backtestCapital) backtestCapital.value = strategy.initial_capital || 10000;

            const maxLeverage = 100;
            const lev = Math.min(maxLeverage, Math.max(1, strategy.leverage != null ? strategy.leverage : 10));
            if (backtestLeverage) backtestLeverage.value = lev;
            if (backtestLeverageRange) backtestLeverageRange.value = lev;
            updateBacktestLeverageDisplay(lev);

            const params = strategy.parameters || {};
            const posType = params._position_size_type || 'percent';
            const backtestPositionSizeType = document.getElementById('backtestPositionSizeType');
            const backtestPositionSize = document.getElementById('backtestPositionSize');
            if (backtestPositionSizeType) backtestPositionSizeType.value = posType;
            if (backtestPositionSize) {
                const posVal = strategy.position_size != null
                    ? (posType === 'percent' ? strategy.position_size * 100 : strategy.position_size)
                    : (params._order_amount || 100);
                backtestPositionSize.value = posVal;
            }
            updateBacktestPositionSizeInput();
            updateBacktestLeverageRisk();

            const noTradeDays = strategy.parameters?._no_trade_days;
            if (Array.isArray(noTradeDays)) {
                setNoTradeDaysInUI(noTradeDays);
            }

            const backtestCommission = document.getElementById('backtestCommission');
            if (backtestCommission && strategy.parameters?._commission != null) {
                backtestCommission.value = (strategy.parameters._commission * 100).toFixed(2);
            }
            const backtestSlippage = document.getElementById('backtestSlippage');
            if (backtestSlippage && strategy.parameters?._slippage != null) {
                backtestSlippage.value = (strategy.parameters._slippage * 100).toFixed(2);
            }
            const backtestPyramiding = document.getElementById('backtestPyramiding');
            if (backtestPyramiding && strategy.parameters?._pyramiding != null) {
                backtestPyramiding.value = strategy.parameters._pyramiding;
            }

            const backtestStartDateEl = document.getElementById('backtestStartDate');
            const backtestEndDateEl = document.getElementById('backtestEndDate');
            if (backtestStartDateEl) {
                backtestStartDateEl.value = strategy.parameters?._start_date || strategy.start_date || '2025-01-01';
            }
            if (backtestEndDateEl) {
                const today = new Date().toISOString().slice(0, 10);
                const savedEnd = strategy.parameters?._end_date || strategy.end_date || today;
                // Clamp to today: don't allow future dates, but don't push saved past dates forward.
                backtestEndDateEl.value = savedEnd <= today ? savedEnd : today;
            }

            // Restore blocks
            pushUndo();
            const blocks = getBlocks();
            blocks.length = 0;

            if (strategy.blocks && Array.isArray(strategy.blocks)) {
                const migratedBlocks = migrateLegacyBlocks(strategy.blocks);
                const mainBlock = migratedBlocks.find(
                    b => b.isMain || b.id === 'main_strategy' || b.type === 'strategy'
                );

                if (mainBlock) {
                    blocks.push({
                        id: mainBlock.id || 'main_strategy',
                        type: mainBlock.type || 'strategy',
                        category: 'main',
                        name: mainBlock.name || 'Strategy',
                        icon: mainBlock.icon || 'diagram-3',
                        x: mainBlock.x || 800,
                        y: mainBlock.y || 300,
                        isMain: true,
                        params: mainBlock.params || {}
                    });
                } else {
                    createMainStrategyNode();
                }

                const blockLibrary = getBlockLibrary();
                migratedBlocks.forEach(block => {
                    if (block.isMain || block.id === 'main_strategy' || block.type === 'strategy') return;
                    let icon = block.icon;
                    if (!icon) {
                        for (const categoryBlocks of Object.values(blockLibrary)) {
                            const def = categoryBlocks.find(b => b.id === block.type);
                            if (def) { icon = def.icon; break; }
                        }
                    }
                    blocks.push({
                        id: block.id,
                        type: block.type,
                        category: block.category || 'indicator',
                        name: block.name || block.type,
                        icon: icon || 'box',
                        x: block.x || 100,
                        y: block.y || 100,
                        params: block.params || {},
                        optimizationParams: block.optimizationParams || {}
                    });
                });
            }

            // Restore connections
            const connections = getConnections();
            connections.length = 0;
            const restoredConnections = (strategy.connections && Array.isArray(strategy.connections))
                ? [...strategy.connections]
                : [];
            connections.push(...restoredConnections);
            normalizeAllConnections();
            setBlocks(blocks);
            setConnections([...connections]);

            renderBlocks();
            renderConnections();
            // Re-enable autosave now that state is fully restored
            setSkipNextAutoSave(false);
            showNotification('Стратегия успешно загружена!', 'success');
            updateRunButtonsState();
            runCheckSymbolDataForProperties();
        } catch (err) {
            setSkipNextAutoSave(false);
            showNotification(`Ошибка загрузки стратегии: ${err.message}`, 'error');
        }
    }

    // -----------------------------------------------
    // Version history
    // -----------------------------------------------

    /**
     * Open the versions modal and fetch version list from backend.
     */
    async function openVersionsModal() {
        const strategyId = getStrategyIdFromURL();
        if (!strategyId) {
            showNotification('Откройте существующую стратегию', 'warning');
            return;
        }
        const modal = document.getElementById('versionsModal');
        const listEl = document.getElementById('versionsList');
        if (!modal || !listEl) return;

        listEl.innerHTML = '<p class="text-muted">Загрузка...</p>';
        modal.classList.add('active');

        try {
            const res = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}/versions`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const versions = data.versions || [];

            if (versions.length === 0) {
                listEl.innerHTML = '<p class="text-muted">Нет сохранённых версий.</p>';
                return;
            }

            listEl.innerHTML = versions
                .map(
                    (v) => `
          <div class="version-item d-flex justify-content-between align-items-center py-2 border-bottom">
            <span><strong>v${v.version}</strong> · ${formatDate(v.created_at) || v.created_at || ''}</span>
            <button class="btn btn-sm btn-outline-primary" onclick="revertToVersion('${strategyId}', ${v.id})">
              <i class="bi bi-arrow-counterclockwise"></i> Restore
            </button>
          </div>
        `
                )
                .join('');
        } catch (err) {
            listEl.innerHTML = `<p class="text-danger">Ошибка: ${escapeHtml(err.message)}</p>`;
        }
    }

    /**
     * Close the versions modal.
     */
    function closeVersionsModal() {
        const modal = document.getElementById('versionsModal');
        if (modal) modal.classList.remove('active');
    }

    /**
     * Revert strategy to a specific version.
     * @param {string} strategyId
     * @param {number} versionId
     */
    async function revertToVersion(strategyId, versionId) {
        if (!confirm('Восстановить эту версию? Текущие изменения будут заменены.')) return;
        try {
            const res = await fetch(
                `/api/v1/strategy-builder/strategies/${strategyId}/revert/${versionId}`,
                { method: 'POST' }
            );
            if (!res.ok) throw new Error(await res.text());
            closeVersionsModal();
            await loadStrategy(strategyId);
            showNotification('Версия восстановлена', 'success');
        } catch (err) {
            showNotification(`Ошибка: ${err.message}`, 'error');
        }
    }

    // -----------------------------------------------
    // Private helpers
    // -----------------------------------------------

    function _updateLastSaved(timestamp = null) {
        const lastSavedEl = document.querySelector('.text-secondary.text-sm');
        if (lastSavedEl) {
            const date = timestamp ? new Date(timestamp) : new Date();
            lastSavedEl.innerHTML = `<i class="bi bi-clock"></i> Last saved: ${date.toLocaleString()}`;
        }
    }

    function _clearLocalStorageDraft(strategyId) {
        try {
            window.localStorage.removeItem(`strategy_builder_draft_${strategyId}`);
        } catch (e) {
            console.warn('[SaveLoadModule] Could not clear localStorage draft:', e);
        }
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    return {
        saveStrategy,
        buildStrategyPayload,
        autoSaveStrategy,
        migrateLegacyBlocks,
        loadStrategy,
        openVersionsModal,
        closeVersionsModal,
        revertToVersion
    };
}
