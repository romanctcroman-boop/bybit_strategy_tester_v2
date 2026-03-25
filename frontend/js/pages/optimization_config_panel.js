/**
 * ⚙️ Optimization Config Panel Module
 *
 * Complete UI component for configuring optimization settings:
 * - Optimization method selection (Grid, Bayesian, Walk-Forward, Random)
 * - Visual parameter range sliders
 * - Data period configuration with train/test split
 * - Resource limits (trials, timeout, workers)
 * - Advanced options (early stopping, warm starts)
 *
 * Integrates with strategy_builder.js and optimization_panels.js
 *
 * @version 2.0.0
 * @date 2025-01-30
 */

class OptimizationConfigPanel {
    constructor(containerId = 'optimizationConfigSection') {
        this.containerId = containerId;
        this.container = null;

        // Optimization methods with descriptions
        this.methods = {
            bayesian: {
                label: 'Bayesian (TPE)',
                description: 'Smart search using Tree-structured Parzen Estimators. Best for most cases.',
                icon: 'bi-cpu',
                recommended: true,
                supports: ['continuous', 'categorical', 'conditional']
            },
            grid_search: {
                label: 'Grid Search',
                description: 'Exhaustive search of all parameter combinations. Guaranteed to find optimum.',
                icon: 'bi-grid-3x3',
                recommended: false,
                supports: ['continuous', 'categorical']
            },
            random_search: {
                label: 'Random Search',
                description: 'Random sampling of parameter space. Fast but may miss optimum.',
                icon: 'bi-shuffle',
                recommended: false,
                supports: ['continuous', 'categorical']
            },
            walk_forward: {
                label: 'Walk-Forward',
                description: 'Rolling window optimization for robustness testing. Best for production.',
                icon: 'bi-clock-history',
                recommended: false,
                supports: ['continuous', 'categorical'],
                advanced: true
            }
        };

        // State
        this.state = {
            method: 'bayesian',
            parameterRanges: [],
            dataPeriod: {
                startDate: this.getDefaultStartDate(),
                endDate: this.getDefaultEndDate(),
                trainSplit: 0.8,
                useWalkForward: false,
                wfTrainSize: 90,
                wfTestSize: 30,
                wfStepSize: 30
            },
            limits: {
                maxTrials: 200,
                timeoutSeconds: 3600,
                workers: 4,
                maxConcurrent: 2
            },
            advanced: {
                earlyStopping: true,
                earlyStoppingPatience: 20,
                warmStart: false,
                pruneInfeasible: true,
                randomSeed: null
            },
            walkForward: {
                nSplits: 5,
                trainRatio: 0.7,
                gapPeriods: 0,
                innerMethod: 'grid'
            },
            symbol: 'BTCUSDT',
            timeframe: '1h'
        };

        this.init();
    }

    getDefaultStartDate() {
        return '2025-01-01';
    }

    getDefaultEndDate() {
        // Default to today (local time, not UTC — avoids off-by-one in UTC+N zones)
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    /** Период из блока «Основные параметры» */
    getBacktestStartDate() {
        const el = document.getElementById('backtestStartDate');
        return el?.value || this.getDefaultStartDate();
    }

    getBacktestEndDate() {
        const el = document.getElementById('backtestEndDate');
        return el?.value || this.getDefaultEndDate();
    }

    init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.warn(`[OptimizationConfigPanel] Container #${this.containerId} not found`);
            return;
        }

        // Set backtestEndDate default to today if not already set
        const endDateEl = document.getElementById('backtestEndDate');
        if (endDateEl && !endDateEl.value) {
            endDateEl.value = this.getDefaultEndDate();
        }

        this.render();
        this.loadSavedState();
        this.bindEvents();
        this.setupBlockIntegration();
    }

    /**
     * Setup integration with strategy blocks
     */
    setupBlockIntegration() {
        // Listen for block changes to update parameter ranges
        document.addEventListener('strategyBlocksChanged', (e) => {
            const blocks = e.detail?.blocks || [];
            this.updateParameterRangesFromBlocks(blocks);
        });

        // Initial check
        setTimeout(() => {
            if (window.strategyBlocks) {
                this.updateParameterRangesFromBlocks(window.strategyBlocks);
            }
        }, 500);
    }

    /**
     * Extract optimizable parameters from strategy blocks
     */
    updateParameterRangesFromBlocks(blocks) {
        if (!blocks || !Array.isArray(blocks)) {
            console.warn('[OptimizationConfigPanel] updateParameterRangesFromBlocks: no blocks', blocks);
            return;
        }

        const params = [];

        blocks.forEach(block => {
            if (!block.optimizationParams) return;
            // params may live in block.params OR block.config — accept both
            const blockParamsObj = block.params || block.config || {};

            const enabledKeys = Object.keys(block.optimizationParams)
                .filter(k => block.optimizationParams[k]?.enabled);
            if (enabledKeys.length === 0) return;

            const blockName = block.name || block.type || block.id;
            console.log(`[OptimizationConfigPanel] Block "${blockName}" has enabled keys:`, enabledKeys);
            console.log('[OptimizationConfigPanel] Block ID (real):', block.id);

            enabledKeys.forEach(paramKey => {
                const optConfig = block.optimizationParams[paramKey];
                const currentValue = blockParamsObj[paramKey] ?? optConfig.min ?? 0;
                params.push({
                    id: `${block.id}_${paramKey}`,
                    blockId: block.id,
                    paramKey: paramKey,
                    label: `${blockName} ${this.formatParamName(paramKey)}`,
                    currentValue: currentValue,
                    min: optConfig.min ?? currentValue,
                    max: optConfig.max ?? currentValue,
                    step: optConfig.step ?? 1,
                    type: this.detectParamType(currentValue, optConfig)
                });
            });
        });

        console.log(`[OptimizationConfigPanel] Extracted ${params.length} param(s):`, params.map(p => p.id));
        this.state.parameterRanges = params;
        this.renderParameterRangesUI();
        this.updateEstimatedTime();
        this.updateModeBadge();
    }

    /**
     * Update mode badge
     */
    updateModeBadge() {
        const badge = this.container.querySelector('#modeBadge');
        if (badge) {
            const hasParams = this.state.parameterRanges.length > 0;
            badge.textContent = hasParams ? 'Optimization' : 'Single Backtest';
            badge.className = `mode-badge ${hasParams ? 'mode-optimization' : 'mode-single'}`;
        }
    }

    /**
     * Detect parameter type
     */
    detectParamType(value, config) {
        if (config.values && Array.isArray(config.values)) return 'categorical';
        if (Number.isInteger(value)) return 'int';
        return 'float';
    }

    /**
     * Format parameter name for display
     */
    formatParamName(key) {
        return key
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Render the panel
     */
    render() {
        this.container.innerHTML = `
            <!-- Method Selection -->
            <div class="property-row property-row-vertical">
                <label class="property-label property-label-with-badge">
                    <i class="bi bi-gear"></i> Optimization Method
                    <span class="mode-badge ${this.state.parameterRanges.length > 0 ? 'mode-optimization' : 'mode-single'}" id="modeBadge">
                        ${this.state.parameterRanges.length > 0 ? 'Optimization' : 'Single Backtest'}
                    </span>
                </label>
                <div class="method-selector" id="optMethodSelector">
                    ${this.renderMethodSelector()}
                </div>
            </div>

            <!-- Method Description -->
            <div class="method-description" id="optMethodDescription">
                ${this.renderMethodDescription()}
            </div>

            <!-- Parameter Ranges -->
            <div class="property-row property-row-vertical">
                <label class="property-label">
                    <i class="bi bi-sliders"></i> Parameter Ranges
                    <span class="param-count">(${this.state.parameterRanges.length} params)</span>
                </label>
                <div class="param-ranges-container" id="optParamRanges">
                    ${this.renderParameterRanges()}
                </div>
            </div>

            <!-- Estimated Time -->
            <div class="estimated-time" id="optEstimatedTime">
                ${this.renderEstimatedTime()}
            </div>

            <!-- Start Button -->
            <button class="btn btn-primary w-100 mt-3" id="btnStartOptimization">
                <i class="bi bi-play-fill"></i> Start Optimization
            </button>
        `;
    }

    /**
     * Calculate total parameter combinations
     */
    calculateTotalCombinations() {
        if (this.state.parameterRanges.length === 0) return 0;

        let total = 1;
        this.state.parameterRanges.forEach(param => {
            if (param.type === 'categorical' && param.values) {
                total *= param.values.length;
            } else {
                const steps = Math.max(1, Math.floor((param.max - param.min) / param.step) + 1);
                total *= steps;
            }
        });
        return total;
    }

    /**
     * Render method selector
     */
    renderMethodSelector() {
        return Object.entries(this.methods).map(([key, method]) => {
            const isSelected = this.state.method === key;
            return `
                <label class="method-option ${isSelected ? 'selected' : ''}" data-method="${key}">
                    <input type="radio" name="optMethod" value="${key}" ${isSelected ? 'checked' : ''}>
                    <div class="method-option-content">
                        <i class="bi ${method.icon}"></i>
                        <span class="method-name">${method.label}</span>
                        ${method.recommended ? '<span class="badge badge-recommended">Recommended</span>' : ''}
                    </div>
                </label>
            `;
        }).join('');
    }

    /**
     * Render method description
     */
    renderMethodDescription() {
        const method = this.methods[this.state.method];
        return `
            <p class="text-muted text-sm">
                <i class="bi bi-info-circle"></i> ${method.description}
            </p>
        `;
    }

    /**
     * Render parameter ranges
     */
    renderParameterRanges() {
        if (this.state.parameterRanges.length === 0) {
            return `
                <div class="no-params-message">
                    <i class="bi bi-sliders text-muted" style="font-size:1.4rem"></i>
                    <p style="margin:6px 0 4px 0;font-weight:600;color:var(--text-primary)">Параметры не выбраны</p>
                    <p style="margin:0;color:var(--text-secondary);font-size:12px">
                        Откройте блок индикатора (⚙️ меню на блоке), нажмите кнопку
                        <strong style="color:var(--accent-blue)">Optimization</strong>
                        и поставьте ✓ рядом с нужными параметрами.
                    </p>
                </div>
            `;
        }

        return this.state.parameterRanges.map(param => `
            <div data-param-id="${param.id}" style="display:flex;flex-direction:row;align-items:center;gap:16px;padding:4px 8px;border-bottom:1px solid var(--border-color,#2a2a2a);font-size:12px;flex-wrap:nowrap;">
                <span style="flex:1;min-width:0;font-weight:600;color:var(--text-primary,#e0e0e0);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${param.label}</span>
                <span style="color:var(--text-secondary,#888);white-space:nowrap">Min&nbsp;<strong>${param.min}</strong></span>
                <span style="color:var(--text-secondary,#888);white-space:nowrap">Max&nbsp;<strong>${param.max}</strong></span>
                <span style="color:var(--text-secondary,#888);white-space:nowrap">Step&nbsp;<strong>${param.step}</strong></span>
                <span style="color:var(--accent-blue,#4a9eff);white-space:nowrap">${this.calculateParamCombinations(param)}&nbsp;values</span>
            </div>
        `).join('');
    }

    /**
     * Calculate combinations for single parameter
     */
    calculateParamCombinations(param) {
        if (param.type === 'categorical' && param.values) {
            return param.values.length;
        }
        return Math.max(1, Math.floor((param.max - param.min) / param.step) + 1);
    }

    /**
     * Render data period configuration.
     * Период (Start/End Date) берётся из блока «Основные параметры».
     */
    renderDataPeriod() {
        return `
            <p class="text-muted text-sm mb-2">
                <i class="bi bi-info-circle"></i> Период бэктеста — из блока «Основные параметры» (Start Date / End Date).
            </p>
            <div class="train-test-split">
                <label>Train/Test Split</label>
                <div class="split-slider-container">
                    <input type="range" id="optTrainSplit"
                           min="0.5" max="0.95" step="0.05"
                           value="${this.state.dataPeriod.trainSplit}">
                    <div class="split-labels">
                        <span class="train-label">Train: ${Math.round(this.state.dataPeriod.trainSplit * 100)}%</span>
                        <span class="test-label">Test: ${Math.round((1 - this.state.dataPeriod.trainSplit) * 100)}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render walk-forward configuration
     */
    renderWalkForwardConfig() {
        const wf = this.state.walkForward;
        return `
            <div style="display:flex;flex-direction:column;gap:8px;padding:10px;background:var(--bg-secondary,#1a1a1a);border-radius:6px;margin-top:8px;">
                <div style="font-size:11px;color:var(--text-secondary,#888);margin-bottom:2px;">
                    <i class="bi bi-info-circle"></i>
                    Разбивает данные на окна: оптимизирует на IS, валидирует на OOS. Показывает устойчивость стратегии.
                </div>
                <div style="display:flex;gap:12px;flex-wrap:wrap;">
                    <div style="display:flex;flex-direction:column;gap:4px;flex:1;min-width:100px;">
                        <label style="font-size:11px;color:var(--text-secondary,#888);">Окна (splits)</label>
                        <input type="number" id="wfNSplits" value="${wf.nSplits}" min="2" max="20" step="1"
                               style="padding:4px 8px;background:var(--bg-tertiary,#252525);border:1px solid var(--border-color,#333);border-radius:4px;color:var(--text-primary,#e0e0e0);font-size:12px;width:100%;">
                    </div>
                    <div style="display:flex;flex-direction:column;gap:4px;flex:1;min-width:100px;">
                        <label style="font-size:11px;color:var(--text-secondary,#888);">IS доля (0.5–0.9)</label>
                        <input type="number" id="wfTrainRatio" value="${wf.trainRatio}" min="0.5" max="0.9" step="0.05"
                               style="padding:4px 8px;background:var(--bg-tertiary,#252525);border:1px solid var(--border-color,#333);border-radius:4px;color:var(--text-primary,#e0e0e0);font-size:12px;width:100%;">
                    </div>
                    <div style="display:flex;flex-direction:column;gap:4px;flex:1;min-width:120px;">
                        <label style="font-size:11px;color:var(--text-secondary,#888);">Метод IS</label>
                        <select id="wfInnerMethod"
                                style="padding:4px 8px;background:var(--bg-tertiary,#252525);border:1px solid var(--border-color,#333);border-radius:4px;color:var(--text-primary,#e0e0e0);font-size:12px;width:100%;">
                            <option value="grid" ${wf.innerMethod === 'grid' ? 'selected' : ''}>Grid Search</option>
                            <option value="bayesian" ${wf.innerMethod === 'bayesian' ? 'selected' : ''}>Bayesian</option>
                        </select>
                    </div>
                </div>
                <div id="wfPreview" style="font-size:11px;color:var(--accent-blue,#4a9eff);margin-top:4px;">
                    ${this.renderWalkForwardPreview()}
                </div>
            </div>
        `;
    }

    /**
     * Render walk-forward preview
     */
    renderWalkForwardPreview() {
        const { nSplits, trainRatio } = this.state.walkForward;
        const oosPct = Math.round((1 - trainRatio) * 100);
        return `<i class="bi bi-layers"></i> ${nSplits} окон · IS ${Math.round(trainRatio * 100)}% / OOS ${oosPct}% · результат = среднее OOS`;
    }

    /**
     * Render resource limits
     */
    renderLimits() {
        return `
            <div class="limits-grid">
                <div class="limit-item">
                    <label for="optMaxTrials">Max Trials</label>
                    <input type="number" id="optMaxTrials"
                           value="${this.state.limits.maxTrials}"
                           min="10" max="10000" step="10">
                </div>
                <div class="limit-item">
                    <label for="optTimeout">Timeout (sec)</label>
                    <input type="number" id="optTimeout"
                           value="${this.state.limits.timeoutSeconds}"
                           min="60" max="86400" step="60">
                </div>
                <div class="limit-item">
                    <label for="optWorkers">Workers</label>
                    <input type="number" id="optWorkers"
                           value="${this.state.limits.workers}"
                           min="1" max="16">
                </div>
            </div>
        `;
    }

    /**
     * Render advanced options
     */
    renderAdvancedOptions() {
        return `
            <div class="advanced-options-list">
                <div class="advanced-option">
                    <label class="toggle-label">
                        <input type="checkbox" id="optEarlyStopping" ${this.state.advanced.earlyStopping ? 'checked' : ''}>
                        <span>Early Stopping</span>
                    </label>
                    <input type="number" id="optEarlyStoppingPatience"
                           value="${this.state.advanced.earlyStoppingPatience}"
                           min="5" max="100"
                           class="${this.state.advanced.earlyStopping ? '' : 'disabled'}"
                           title="Stop after N trials without improvement">
                </div>
                <div class="advanced-option">
                    <label class="toggle-label">
                        <input type="checkbox" id="optPruneInfeasible" ${this.state.advanced.pruneInfeasible ? 'checked' : ''}>
                        <span>Prune Infeasible</span>
                    </label>
                    <span class="option-hint">Skip params that violate constraints early</span>
                </div>
                <div class="advanced-option">
                    <label class="toggle-label">
                        <input type="checkbox" id="optWarmStart" ${this.state.advanced.warmStart ? 'checked' : ''}>
                        <span>Warm Start</span>
                    </label>
                    <span class="option-hint">Start from previous best params</span>
                </div>
                <div class="advanced-option">
                    <label>Random Seed</label>
                    <input type="number" id="optRandomSeed"
                           value="${this.state.advanced.randomSeed || ''}"
                           placeholder="Auto"
                           min="0" max="999999">
                </div>
            </div>
        `;
    }

    /**
     * Render estimated time
     */
    renderEstimatedTime() {
        const combinations = this.calculateTotalCombinations();
        const method = this.state.method;
        const workers = this.state.limits.workers || 4;

        // No parameters selected
        if (this.state.parameterRanges.length === 0) {
            return `
                <div class="estimated-time-content" style="opacity:0.55">
                    <i class="bi bi-clock"></i>
                    <span>Выберите параметры для оптимизации чтобы увидеть оценку времени</span>
                </div>
            `;
        }

        // Rough estimates per backtest (seconds)
        const backtestTime = 0.5;

        let estimatedTrials;
        if (method === 'grid_search') {
            estimatedTrials = combinations;
        } else if (method === 'bayesian') {
            estimatedTrials = Math.min(this.state.limits.maxTrials, combinations);
        } else {
            estimatedTrials = this.state.limits.maxTrials;
        }

        const totalSeconds = (estimatedTrials * backtestTime) / workers;
        const timeStr = this.formatDuration(totalSeconds);
        const methodLabel = method === 'grid_search' ? 'Grid' : method === 'bayesian' ? 'Bayesian' : method === 'walk_forward' ? 'Walk-Forward' : 'Random';

        return `
            <div class="estimated-time-content">
                <i class="bi bi-clock"></i>
                <span>~${estimatedTrials.toLocaleString()} прогонов (${methodLabel})</span>
                <span class="text-muted"> · ~${timeStr}</span>
            </div>
        `;
    }

    /**
     * Format duration for display
     */
    formatDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
    }

    /**
     * Bind all events
     */
    bindEvents() {
        // Method selection
        this.container.querySelectorAll('.method-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const method = e.currentTarget.dataset.method;
                this.setMethod(method);
            });
        });

        // Период берётся из «Основные параметры», даты не редактируются здесь

        // Limits
        this.container.querySelector('#optMaxTrials')?.addEventListener('change', (e) => {
            this.state.limits.maxTrials = parseInt(e.target.value) || 200;
            this.updateEstimatedTime();
            this.saveState();
        });

        // Walk-Forward settings
        this.container.querySelector('#wfNSplits')?.addEventListener('change', (e) => {
            this.state.walkForward.nSplits = parseInt(e.target.value) || 5;
            this.updateWalkForwardPreview();
            this.saveState();
            this.emitChange();
        });
        this.container.querySelector('#wfTrainRatio')?.addEventListener('change', (e) => {
            this.state.walkForward.trainRatio = parseFloat(e.target.value) || 0.7;
            this.updateWalkForwardPreview();
            this.saveState();
            this.emitChange();
        });
        this.container.querySelector('#wfInnerMethod')?.addEventListener('change', (e) => {
            this.state.walkForward.innerMethod = e.target.value || 'grid';
            this.saveState();
            this.emitChange();
        });

        // Parameter range inputs (delegated)
        this.container.querySelector('#optParamRanges')?.addEventListener('change', (e) => {
            this.handleParamRangeChange(e);
        });

        // Start button
        this.container.querySelector('#btnStartOptimization')?.addEventListener('click', () => {
            this.startOptimization();
        });
    }

    /**
     * Handle parameter range input changes
     */
    handleParamRangeChange(e) {
        const item = e.target.closest('.param-range-item');
        if (!item) return;

        const paramId = item.dataset.paramId;
        const param = this.state.parameterRanges.find(p => p.id === paramId);
        if (!param) return;

        if (e.target.classList.contains('param-min') || e.target.classList.contains('range-min')) {
            param.min = parseFloat(e.target.value);
        } else if (e.target.classList.contains('param-max') || e.target.classList.contains('range-max')) {
            param.max = parseFloat(e.target.value);
        } else if (e.target.classList.contains('param-step')) {
            param.step = parseFloat(e.target.value);
        }

        // Sync sliders and inputs
        this.syncParamRangeUI(item, param);

        // Update combinations count
        const combSpan = item.querySelector('.param-combinations');
        if (combSpan) {
            combSpan.innerHTML = `<i class="bi bi-layers"></i> ${this.calculateParamCombinations(param)} values`;
        }

        this.updateEstimatedTime();
        this.saveState();
        this.emitChange();
    }

    /**
     * Sync param range UI (sliders and inputs)
     */
    syncParamRangeUI(item, param) {
        const minInput = item.querySelector('.param-min');
        const maxInput = item.querySelector('.param-max');
        const minSlider = item.querySelector('.range-min');
        const maxSlider = item.querySelector('.range-max');

        if (minInput) minInput.value = param.min;
        if (maxInput) maxInput.value = param.max;
        if (minSlider) minSlider.value = param.min;
        if (maxSlider) maxSlider.value = param.max;

        // Update slider track visual
        this.updateSliderTrack(item);
    }

    /**
     * Update slider track visual
     */
    updateSliderTrack(item) {
        const minSlider = item.querySelector('.range-min');
        const maxSlider = item.querySelector('.range-max');
        const range = item.querySelector('.slider-range');

        if (!minSlider || !maxSlider || !range) return;

        const min = parseFloat(minSlider.min);
        const max = parseFloat(minSlider.max);
        const valMin = parseFloat(minSlider.value);
        const valMax = parseFloat(maxSlider.value);

        const leftPercent = ((valMin - min) / (max - min)) * 100;
        const rightPercent = ((max - valMax) / (max - min)) * 100;

        range.style.left = `${leftPercent}%`;
        range.style.right = `${rightPercent}%`;
    }

    /**
     * Set optimization method
     */
    setMethod(method) {
        this.state.method = method;

        // Update UI
        this.container.querySelectorAll('.method-option').forEach(opt => {
            opt.classList.toggle('selected', opt.dataset.method === method);
        });

        // Update description
        const descEl = this.container.querySelector('#optMethodDescription');
        if (descEl) descEl.innerHTML = this.renderMethodDescription();

        // Show/hide walk-forward config
        const wfConfig = this.container.querySelector('#optWalkForwardConfig');
        if (wfConfig) wfConfig.classList.toggle('d-none', method !== 'walk_forward');

        this.updateEstimatedTime();
        this.saveState();
        this.emitChange();
    }

    /**
     * Update estimated time
     */
    updateEstimatedTime() {
        const el = this.container.querySelector('#optEstimatedTime');
        if (el) el.innerHTML = this.renderEstimatedTime();
    }

    /**
     * Update walk-forward preview
     */
    updateWalkForwardPreview() {
        const preview = this.container.querySelector('#wfPreview');
        if (preview) preview.innerHTML = this.renderWalkForwardPreview();
    }

    /**
     * Re-render parameter ranges
     */
    renderParameterRangesUI() {
        const container = this.container.querySelector('#optParamRanges');
        if (container) {
            container.innerHTML = this.renderParameterRanges();
        }
        const count = this.container.querySelector('.param-count');
        if (count) count.textContent = `(${this.state.parameterRanges.length} params)`;
    }

    /**
     * Start optimization or single backtest
     */
    async startOptimization() {
        // Emit start event - will be handled by optimization_panels.js
        // If no parameter ranges, it will run single backtest instead
        const cfg = this.getConfig();
        console.log('[OptConfigPanel] startOptimization — param_paths:', cfg.parameter_ranges.map(p => p.param_path));
        const event = new CustomEvent('startOptimization', {
            detail: cfg
        });
        document.dispatchEvent(event);
    }

    /**
     * Get current configuration
     */
    getConfig() {
        // Pull optimize_metric from optimization_panels.js state (it owns the metric selector)
        const optimizeMetric = window.optimizationPanels?.state?.primaryMetric
            || window.optimizationPanels?.state?.lastOptimizeMetric
            || 'sharpe_ratio';
        return {
            method: this.state.method,
            optimize_metric: optimizeMetric,
            parameter_ranges: this.state.parameterRanges.map(p => ({
                name: p.id,
                param_path: `${p.blockId}.${p.paramKey}`,
                type: p.type,
                low: p.min,
                high: p.max,
                step: p.step
            })),
            data_period: {
                start_date: this.getBacktestStartDate(),
                end_date: this.getBacktestEndDate()
            },
            limits: {
                maxTrials: this.state.limits.maxTrials
            },
            walk_forward: this.state.method === 'walk_forward' ? {
                n_splits: this.state.walkForward.nSplits,
                train_ratio: this.state.walkForward.trainRatio,
                gap_periods: this.state.walkForward.gapPeriods,
                inner_method: this.state.walkForward.innerMethod
            } : null,
            symbol: this.state.symbol,
            timeframe: this.state.timeframe
        };
    }

    /**
     * Save state to localStorage
     */
    saveState() {
        localStorage.setItem('optimizationConfigState', JSON.stringify(this.state));
    }

    /**
     * Load saved state
     */
    loadSavedState() {
        const saved = localStorage.getItem('optimizationConfigState');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                // Merge with default, preserving structure.
                // NOTE: Do NOT restore parameterRanges from localStorage — they are
                // rebuilt live from window.strategyBlocks via setupBlockIntegration().
                // Restoring stale saved ranges causes empty-range bugs on reload.
                this.state = {
                    ...this.state,
                    ...parsed,
                    parameterRanges: [],  // always rebuilt from live blocks
                    dataPeriod: { ...this.state.dataPeriod, ...parsed.dataPeriod },
                    limits: { ...this.state.limits, ...parsed.limits },
                    advanced: { ...this.state.advanced, ...parsed.advanced }
                };
                // Re-render UI to reflect restored method/settings, but do NOT
                // call bindEvents() again — init() already called it once.
                this.render();
                // Re-bind ONLY after re-render (render() wipes innerHTML → old listeners gone)
                this.bindEvents();
            } catch (e) {
                console.warn('[OptimizationConfigPanel] Failed to load saved state:', e);
            }
        }
    }

    /**
     * Emit change event
     */
    emitChange() {
        const event = new CustomEvent('optimizationConfigChanged', {
            detail: this.getConfig()
        });
        document.dispatchEvent(event);
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on strategy-builder page
    if (document.getElementById('optimizationConfigSection')) {
        window.optimizationConfigPanel = new OptimizationConfigPanel();
    }
});

// Export for module usage
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OptimizationConfigPanel;
}
/* eslint-enable no-undef */
