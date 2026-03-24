/**
 * 📦 ValidateModule
 *
 * Strategy validation, validation panel rendering, and Python code generation
 * for the Strategy Builder canvas. Extracted from strategy_builder.js during P0-1 refactoring.
 *
 * @module ValidateModule
 * @version 1.0.0
 * @date 2026-02-26
 */

// Standalone exit block types (backend reads from builder_blocks; no connections required)
const EXIT_BLOCK_TYPES = new Set([
    'static_sltp', 'trailing_stop_exit', 'atr_exit',
    'multi_tp_exit',
    'tp_percent', 'sl_percent',
    'rsi_close', 'stoch_close', 'channel_close', 'ma_close',
    'psar_close', 'time_bars_close'
]);

/**
 * Create a ValidateModule instance.
 *
 * @param {object} deps
 * @param {function(): object[]} deps.getBlocks           - Returns current strategyBlocks array
 * @param {function(): object[]} deps.getConnections      - Returns current connections array
 * @param {function(object): object} deps.getBlockPorts   - Returns port definition for a block type
 * @param {function(object): object} deps.validateBlockParams  - Validates a single block's params
 * @param {function(string, object): void} deps.updateBlockValidationState - Updates block UI state
 * @param {function(): string|null} deps.getStrategyIdFromURL - Reads ?id= from URL
 * @param {function(): Promise<void>} deps.saveStrategy   - Saves the current strategy
 * @param {function(string, string): void} deps.showNotification - Shows a toast notification
 * @param {function(string): string} deps.escapeHtml      - Escapes HTML entities
 * @returns {object} Public API
 */
export function createValidateModule({
    getBlocks,
    getConnections,
    getBlockPorts,
    validateBlockParams,
    updateBlockValidationState,
    getStrategyIdFromURL,
    saveStrategy,
    showNotification,
    // eslint-disable-next-line no-unused-vars
    escapeHtml
}) {

    // -----------------------------------------------
    // Quick pre-flight check (used by runBacktest guard)
    // -----------------------------------------------

    /**
     * Fast 3-part validation for pre-backtest check.
     * Does NOT update the validation panel UI.
     *
     * @returns {{ valid: boolean, errors: string[], warnings: string[] }}
     */
    function validateStrategyCompleteness() {
        const result = { valid: true, errors: [], warnings: [] };
        const blocks = getBlocks();
        const connections = getConnections();

        const mainNode = blocks.find((b) => b.isMain);
        if (!mainNode) {
            result.valid = false;
            result.errors.push('Main strategy node is missing');
            return result;
        }

        // Part 1: Parameters
        const symbol = document.getElementById('backtestSymbol')?.value?.trim();
        const timeframe = document.getElementById('strategyTimeframe')?.value?.trim();
        const startDate = document.getElementById('backtestStartDate')?.value?.trim();
        const endDate = document.getElementById('backtestEndDate')?.value?.trim();
        const capital = parseFloat(document.getElementById('backtestCapital')?.value);
        const leverage = parseFloat(document.getElementById('backtestLeverage')?.value);
        const positionSize = parseFloat(document.getElementById('backtestPositionSize')?.value);
        const pyramiding = parseInt(document.getElementById('backtestPyramiding')?.value, 10);

        if (!symbol) { result.valid = false; result.errors.push('⚙️ Параметры: не выбран Symbol'); }
        if (!timeframe) { result.valid = false; result.errors.push('⚙️ Параметры: не выбран Timeframe'); }
        if (!startDate || !endDate) { result.valid = false; result.errors.push('⚙️ Параметры: не заданы даты'); }
        if (startDate) {
            const DATA_START = '2025-01-01';
            if (startDate < DATA_START) {
                result.valid = false;
                result.errors.push(`⚙️ Параметры: Start Date раньше ${DATA_START} — данных нет`);
            }
        }
        if (endDate) {
            const _n = new Date();
            const todayStr = `${_n.getFullYear()}-${String(_n.getMonth() + 1).padStart(2, '0')}-${String(_n.getDate()).padStart(2, '0')}`;
            if (endDate > todayStr) {
                result.valid = false;
                result.errors.push('⚙️ Параметры: End Date в будущем — данных нет');
            }
        }
        if (startDate && endDate && startDate >= endDate) {
            result.valid = false;
            result.errors.push('⚙️ Параметры: Start Date должна быть раньше End Date');
        }
        if (startDate && endDate && startDate < endDate) {
            const diffMs = new Date(endDate) - new Date(startDate);
            const diffDays = diffMs / (24 * 60 * 60 * 1000);
            const diffYears = diffMs / (365.25 * 24 * 60 * 60 * 1000);
            if (diffDays < 7) {
                result.warnings.push('⚙️ Параметры: диапазон дат < 7 дней — слишком мало баров для бэктеста');
            }
            if (diffYears > 10) {
                result.warnings.push('⚙️ Параметры: диапазон дат > 10 лет — бэктест может быть очень долгим');
            }
        }
        if (!capital || capital <= 0) { result.valid = false; result.errors.push('⚙️ Параметры: Capital должен быть > 0'); }
        if (document.getElementById('backtestLeverage') && (!leverage || leverage <= 0)) {
            result.valid = false;
            result.errors.push('⚙️ Параметры: Leverage должен быть > 0');
        }
        if (document.getElementById('backtestPositionSize') && (!positionSize || positionSize <= 0)) {
            result.valid = false;
            result.errors.push('⚙️ Параметры: Position Size должен быть > 0');
        }
        if (document.getElementById('backtestPyramiding') && (isNaN(pyramiding) || pyramiding <= 0)) {
            result.valid = false;
            result.errors.push('⚙️ Параметры: Pyramiding должен быть ≥ 1');
        }

        // Part 2: Entry conditions
        const hasEntryLong = connections.some((c) =>
            c.target.blockId === mainNode.id && c.target.portId === 'entry_long'
        );
        const hasEntryShort = connections.some((c) =>
            c.target.blockId === mainNode.id && c.target.portId === 'entry_short'
        );
        if (!hasEntryLong && !hasEntryShort) {
            result.valid = false;
            result.errors.push('🟢 Вход: нет условий входа (подключите сигналы к Entry Long или Entry Short)');
        }

        // Part 3: Exit conditions
        const hasExitBlocks = blocks.some((b) =>
            !b.isMain && EXIT_BLOCK_TYPES.has(b.type)
        );
        const hasExitSignals = connections.some((c) =>
            c.target.blockId === mainNode.id &&
            (c.target.portId === 'exit_long' || c.target.portId === 'exit_short')
        );
        if (!hasExitBlocks && !hasExitSignals) {
            result.valid = false;
            result.errors.push('🔴 Выход: нет условий выхода (добавьте блок SL/TP или подключите сигналы к Exit Long/Exit Short)');
        } else if (!hasExitBlocks) {
            result.warnings.push('🔴 Выход: нет блока SL/TP — нет защиты стоп-лоссом');
        }

        return result;
    }

    // -----------------------------------------------
    // Full async validation with panel update
    // -----------------------------------------------

    /**
     * Full strategy validation — checks structure, parameters, connections,
     * disconnected blocks, and per-block params. Updates the validation panel.
     *
     * @returns {Promise<void>}
     */
    async function validateStrategy() {
        try {
            const blocks = getBlocks();
            const connections = getConnections();

            console.log('[ValidateModule] validateStrategy called');
            console.log('[ValidateModule] Current blocks:', blocks.length);
            console.log('[ValidateModule] Current connections:', connections.length);

            showNotification('Валидация стратегии...', 'info');

            const result = { valid: true, errors: [], warnings: [] };

            // ── PART 0: BASIC STRUCTURE ──
            if (blocks.length === 0) {
                result.valid = false;
                result.errors.push('Strategy has no blocks');
            }
            const mainNode = blocks.find((b) => b.isMain);
            if (!mainNode) {
                result.valid = false;
                result.errors.push('Main strategy node is missing');
            }

            // ── PART 1: PARAMETERS ──
            const symbol = document.getElementById('backtestSymbol')?.value?.trim();
            const timeframe = document.getElementById('strategyTimeframe')?.value?.trim();
            const startDate = document.getElementById('backtestStartDate')?.value?.trim();
            const endDate = document.getElementById('backtestEndDate')?.value?.trim();
            const capital = parseFloat(document.getElementById('backtestCapital')?.value);
            const leverage = parseFloat(document.getElementById('backtestLeverage')?.value);
            const positionSize = parseFloat(document.getElementById('backtestPositionSize')?.value);
            const pyramiding = parseInt(document.getElementById('backtestPyramiding')?.value, 10);

            if (!symbol) { result.valid = false; result.errors.push('⚙️ Parameters: Symbol not selected'); }
            if (!timeframe) { result.valid = false; result.errors.push('⚙️ Parameters: Timeframe not selected'); }
            if (!startDate || !endDate) { result.valid = false; result.errors.push('⚙️ Parameters: Start/End date not set'); }
            if (startDate) {
                const DATA_START = '2025-01-01';
                if (startDate < DATA_START) {
                    result.valid = false;
                    result.errors.push(`⚙️ Parameters: Start Date is before ${DATA_START} — no data available`);
                }
            }
            if (endDate) {
                const _n = new Date();
                const todayStr = `${_n.getFullYear()}-${String(_n.getMonth() + 1).padStart(2, '0')}-${String(_n.getDate()).padStart(2, '0')}`;
                if (endDate > todayStr) {
                    result.valid = false;
                    result.errors.push('⚙️ Parameters: End Date is in the future — no data available');
                }
            }
            if (startDate && endDate && startDate >= endDate) {
                result.valid = false;
                result.errors.push('⚙️ Parameters: Start Date must be before End Date');
            }
            if (startDate && endDate && startDate < endDate) {
                const diffMs = new Date(endDate) - new Date(startDate);
                const diffDays = diffMs / (24 * 60 * 60 * 1000);
                const diffYears = diffMs / (365.25 * 24 * 60 * 60 * 1000);
                if (diffDays < 7) {
                    result.warnings.push('⚙️ Parameters: Date range < 7 days — too few bars for reliable backtesting');
                }
                if (diffYears > 10) {
                    result.warnings.push('⚙️ Parameters: Date range > 10 years — backtest may be very slow');
                }
            }
            if (!capital || capital <= 0) { result.valid = false; result.errors.push('⚙️ Parameters: Initial capital must be > 0'); }
            if (document.getElementById('backtestLeverage') && (!leverage || leverage <= 0)) {
                result.valid = false;
                result.errors.push('⚙️ Parameters: Leverage must be > 0');
            }
            if (document.getElementById('backtestPositionSize') && (!positionSize || positionSize <= 0)) {
                result.valid = false;
                result.errors.push('⚙️ Parameters: Position Size must be > 0');
            }
            if (document.getElementById('backtestPyramiding') && (isNaN(pyramiding) || pyramiding <= 0)) {
                result.valid = false;
                result.errors.push('⚙️ Parameters: Pyramiding must be ≥ 1');
            }

            // ── PART 2: ENTRY CONDITIONS ──
            if (mainNode) {
                const entryLongConns = connections.filter((c) =>
                    c.target.blockId === mainNode.id && c.target.portId === 'entry_long'
                );
                const entryShortConns = connections.filter((c) =>
                    c.target.blockId === mainNode.id && c.target.portId === 'entry_short'
                );
                const hasEntryLong = entryLongConns.length > 0;
                const hasEntryShort = entryShortConns.length > 0;

                if (!hasEntryLong && !hasEntryShort) {
                    result.valid = false;
                    result.errors.push('🟢 Entry: No entry conditions connected (connect signals to Entry Long or Entry Short)');
                } else {
                    const allEntryConns = [...entryLongConns, ...entryShortConns];
                    const hasConditionSignals = allEntryConns.some((c) => {
                        const sourceBlock = blocks.find((b) => b.id === c.source.blockId);
                        if (!sourceBlock) return false;
                        if (sourceBlock.category === 'condition' || sourceBlock.category === 'logic') return true;
                        if (['less_than', 'greater_than', 'crossover', 'crossunder', 'equals', 'between', 'and', 'or', 'not'].includes(sourceBlock.type)) return true;
                        const sourcePortId = c.source.portId;
                        const portDef = getBlockPorts(sourceBlock.type, sourceBlock.category);
                        if (portDef && portDef.outputs) {
                            const port = portDef.outputs.find((p) => p.id === sourcePortId);
                            if (port && port.type === 'condition') return true;
                        }
                        return false;
                    });
                    if (!hasConditionSignals) {
                        result.warnings.push('🟢 Entry: Entry ports connected but no condition blocks detected');
                    }
                    const direction = document.getElementById('builderDirection')?.value || 'both';
                    if (hasEntryLong && !hasEntryShort && direction === 'both') {
                        result.warnings.push('🟢 Entry: Only Long entries — consider adding Short for "both" direction');
                    } else if (!hasEntryLong && hasEntryShort && direction === 'both') {
                        result.warnings.push('🟢 Entry: Only Short entries — consider adding Long for "both" direction');
                    }
                    if (direction === 'long' && hasEntryShort && !hasEntryLong) {
                        result.warnings.push('🟢 Entry: Direction is "long" but only Short entries connected — signals will be ignored');
                    } else if (direction === 'short' && hasEntryLong && !hasEntryShort) {
                        result.warnings.push('🟢 Entry: Direction is "short" but only Long entries connected — signals will be ignored');
                    }
                }
            }

            // ── PART 3: EXIT CONDITIONS ──
            const exitBlocks = blocks.filter((b) =>
                !b.isMain && EXIT_BLOCK_TYPES.has(b.type)
            );
            const hasExitBlocks = exitBlocks.length > 0;
            let hasExitSignals = false;
            if (mainNode) {
                const exitLongConns = connections.filter((c) =>
                    c.target.blockId === mainNode.id && c.target.portId === 'exit_long'
                );
                const exitShortConns = connections.filter((c) =>
                    c.target.blockId === mainNode.id && c.target.portId === 'exit_short'
                );
                hasExitSignals = exitLongConns.length > 0 || exitShortConns.length > 0;
            }

            if (!hasExitBlocks && !hasExitSignals) {
                result.valid = false;
                result.errors.push('🔴 Exit: No exit conditions (add SL/TP block or connect signals to Exit Long/Exit Short)');
            } else {
                const hasSLTP = exitBlocks.some((b) =>
                    b.type === 'static_sltp' || b.type === 'tp_percent' || b.type === 'sl_percent' || b.type === 'atr_exit'
                );
                if (!hasSLTP) {
                    result.warnings.push('🔴 Exit: No SL/TP block — trades have no stop-loss protection');
                }
                // Duplicate static_sltp blocks — only first one is used by engine
                const sltpCount = exitBlocks.filter((b) => b.type === 'static_sltp').length;
                if (sltpCount > 1) {
                    result.warnings.push(`🔴 Exit: ${sltpCount} Static SL/TP blocks detected — only the first will be used`);
                }
                const atrExitCount = exitBlocks.filter((b) => b.type === 'atr_exit').length;
                if (atrExitCount > 1) {
                    result.warnings.push(`🔴 Exit: ${atrExitCount} ATR Exit blocks detected — only the first will be used`);
                }
            }

            // ── DISCONNECTED BLOCKS ──
            const connectedBlockIds = new Set();
            connections.forEach((c) => {
                connectedBlockIds.add(c.source.blockId);
                connectedBlockIds.add(c.target.blockId);
            });
            const disconnectedBlocks = blocks.filter((b) =>
                !b.isMain && !connectedBlockIds.has(b.id) && !EXIT_BLOCK_TYPES.has(b.type)
            );
            if (disconnectedBlocks.length > 0) {
                result.warnings.push(`${disconnectedBlocks.length} block(s) are not connected`);
            }

            // ── BLOCK PARAMETER VALIDATION ──
            let blocksWithInvalidParams = 0;
            blocks.forEach((block) => {
                if (block.isMain) return;
                const paramValidation = validateBlockParams(block);
                updateBlockValidationState(block.id, paramValidation);
                if (!paramValidation.valid) {
                    blocksWithInvalidParams++;
                    if (paramValidation.errors.length > 0) {
                        result.errors.push(`Block "${block.name}": ${paramValidation.errors[0]}`);
                    }
                }
            });
            if (blocksWithInvalidParams > 0) {
                result.valid = false;
                if (blocksWithInvalidParams > 1) {
                    result.warnings.push(`${blocksWithInvalidParams} blocks have invalid parameters (hover for details)`);
                }
            }

            console.log('[ValidateModule] Validation result:', result);
            updateValidationPanel(result);
        } catch (error) {
            console.error('[ValidateModule] Validation error:', error);
            showNotification(`Ошибка валидации: ${error.message}`, 'error');
            updateValidationPanel({
                valid: false,
                errors: [`Validation failed: ${error.message}`],
                warnings: []
            });
        }
    }

    // -----------------------------------------------
    // Validation panel UI
    // -----------------------------------------------

    /**
     * Update the right-sidebar validation panel with the given result.
     *
     * @param {{ valid: boolean, errors: string[], warnings: string[] }} result
     */
    function updateValidationPanel(result) {
        console.log('[ValidateModule] updateValidationPanel called');
        const status = document.getElementById('validationStatus');
        const list = document.getElementById('validationList');

        if (!status || !list) {
            console.warn('[ValidateModule] Validation panel elements not found');
            const messages = [...result.errors, ...result.warnings];
            if (messages.length > 0) {
                showNotification(`Валидация:\n${messages.join('\n')}`, 'warning');
            } else {
                showNotification('Стратегия валидна!', 'success');
            }
            return;
        }

        if (result.valid && result.errors.length === 0) {
            status.className = 'validation-status valid';
            status.innerHTML = '<i class="bi bi-check-circle-fill"></i> Valid';
            status.style.color = '#28a745';
        } else {
            status.className = 'validation-status invalid';
            status.innerHTML = '<i class="bi bi-x-circle-fill"></i> Invalid';
            status.style.color = '#dc3545';
        }

        let html = '';
        result.errors.forEach((err) => {
            html += `<div class="validation-item error"><i class="bi bi-x-circle"></i><span>${err}</span></div>`;
        });
        result.warnings.forEach((warn) => {
            html += `<div class="validation-item warning"><i class="bi bi-exclamation-triangle"></i><span>${warn}</span></div>`;
        });
        if (html === '') {
            html = '<div class="validation-item info"><i class="bi bi-info-circle"></i><span>Strategy is ready for backtesting</span></div>';
        }

        list.innerHTML = html;
        list.style.display = 'block';
        list.style.visibility = 'visible';

        if (result.errors.length > 0) {
            showNotification(`Валидация не пройдена: ${result.errors[0]}`, 'error');
        } else if (result.warnings.length > 0) {
            showNotification(`Предупреждения: ${result.warnings[0]}`, 'warning');
        } else {
            showNotification('Стратегия валидна!', 'success');
        }
    }

    // -----------------------------------------------
    // Code generation
    // -----------------------------------------------

    /**
     * Generate Python strategy code from the current strategy and display it.
     *
     * @returns {Promise<void>}
     */
    async function generateCode() {
        console.log('[ValidateModule] generateCode called');

        const symbolForCode = document.getElementById('backtestSymbol')?.value?.trim();
        if (!symbolForCode) {
            showNotification('Выберите тикер в поле Symbol перед генерацией кода', 'warning');
            return;
        }

        const strategyId = getStrategyIdFromURL();
        if (!strategyId) {
            showNotification('Сохраните стратегию перед генерацией кода', 'warning');
            if (confirm('Strategy not saved. Save now?')) {
                await saveStrategy();
                const newId = getStrategyIdFromURL();
                if (!newId) {
                    showNotification('Не удалось получить ID стратегии после сохранения', 'error');
                    return;
                }
            } else {
                return;
            }
        }

        const finalId = getStrategyIdFromURL();
        if (!finalId) {
            showNotification('ID стратегии отсутствует. Невозможно сгенерировать код.', 'error');
            return;
        }

        try {
            showNotification('Генерация Python кода...', 'info');
            const url = `/api/v1/strategy-builder/strategies/${finalId}/generate-code`;

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    template: 'backtest',
                    include_comments: true,
                    include_logging: true,
                    async_mode: false
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                let errorDetail = 'Unknown error';
                try {
                    const errorJson = JSON.parse(errorText);
                    errorDetail = errorJson.detail || errorJson.message || errorText;
                } catch {
                    errorDetail = errorText || `HTTP ${response.status}`;
                }
                showNotification(`Генерация кода не удалась: ${errorDetail}`, 'error');
                return;
            }

            const data = await response.json();
            if (!data.success) {
                const errors = data.errors || data.detail || 'Unknown error';
                showNotification(`Генерация кода не удалась: ${JSON.stringify(errors)}`, 'error');
                return;
            }

            const code = data.code || '';
            if (!code) {
                showNotification('Генерация кода вернула пустой результат', 'warning');
                return;
            }

            // Open generated code in a new window
            const win = window.open('', '_blank');
            if (win) {
                const escaped = code
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                win.document.write(
                    '<html><head><title>Сгенерированный код стратегии</title></head><body>' +
                    `<pre style="white-space:pre; font-family:monospace; font-size:12px; padding:16px;">${escaped}</pre>` +
                    '</body></html>'
                );
                win.document.close();
            } else {
                console.log('Generated code:', code);
                showNotification('Всплывающее окно заблокировано. Код в консоли.', 'warning');
            }

            showNotification('Код успешно сгенерирован', 'success');
        } catch (err) {
            showNotification(`Ошибка генерации кода: ${err.message}`, 'error');
        }
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    /**
     * Expose EXIT_BLOCK_TYPES for external callers that need the same set.
     */
    const getExitBlockTypes = () => EXIT_BLOCK_TYPES;

    return {
        validateStrategyCompleteness,
        validateStrategy,
        updateValidationPanel,
        generateCode,
        getExitBlockTypes
    };
}
