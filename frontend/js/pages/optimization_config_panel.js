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
            symbol: 'BTCUSDT',
            timeframe: '1h'
        };

        this.init();
    }

    getDefaultStartDate() {
        return '2025-01-01';
    }

    getDefaultEndDate() {
        return '2030-01-01';
    }

    /** Период из блока «Основные параметры» */
    getBacktestStartDate() {
        const el = document.getElementById('backtestStartDate');
        return el?.value || this.getDefaultStartDate();
    }

    getBacktestEndDate() {
        const el = document.getElementById('backtestEndDate');
        const val = el?.value || this.getDefaultEndDate();
        const today = new Date().toISOString().slice(0, 10);
        return val > today ? today : val;
    }

    init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.warn(`[OptimizationConfigPanel] Container #${this.containerId} not found`);
            return;
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
        if (!blocks || !Array.isArray(blocks)) return;

        const params = [];

        blocks.forEach(block => {
            if (!block.optimizationParams || !block.params) return;

            const blockName = block.name || block.type || block.id;

            Object.entries(block.optimizationParams).forEach(([paramKey, optConfig]) => {
                if (!optConfig || !optConfig.enabled) return;

                const currentValue = block.params[paramKey];
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

        this.state.parameterRanges = params;
        this.renderParameterRanges();
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

            <!-- Data Period -->
            <div class="property-row property-row-vertical">
                <label class="property-label">
                    <i class="bi bi-calendar-range"></i> Data Period
                </label>
                <div class="data-period-config" id="optDataPeriod">
                    ${this.renderDataPeriod()}
                </div>
            </div>

            <!-- Walk-Forward Config (conditional) -->
            <div class="property-row property-row-vertical ${this.state.method === 'walk_forward' ? '' : 'd-none'}" id="optWalkForwardConfig">
                <label class="property-label">
                    <i class="bi bi-clock-history"></i> Walk-Forward Settings
                </label>
                <div class="wf-config">
                    ${this.renderWalkForwardConfig()}
                </div>
            </div>

            <!-- Limits -->
            <div class="property-row property-row-vertical">
                <label class="property-label">
                    <i class="bi bi-speedometer2"></i> Resource Limits
                </label>
                <div class="limits-config" id="optLimits">
                    ${this.renderLimits()}
                </div>
            </div>

            <!-- Advanced Options (всегда развёрнуто) -->
            <div class="property-row property-row-vertical">
                <span class="property-label property-label-secondary">
                    <i class="bi bi-sliders2-vertical"></i> Advanced Options
                </span>
                <div class="advanced-config" id="optAdvancedConfig">
                    ${this.renderAdvancedOptions()}
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
                    <i class="bi bi-info-circle"></i>
                    <p>Click <strong>Optimization</strong> in indicator block popups to enable parameter ranges</p>
                </div>
            `;
        }

        return this.state.parameterRanges.map(param => `
            <div class="param-range-item" data-param-id="${param.id}">
                <div class="param-range-header">
                    <span class="param-range-label">${param.label}</span>
                    <span class="param-range-current">current: ${param.currentValue}</span>
                </div>
                <div class="param-range-slider-container">
                    <div class="dual-range-slider">
                        <input type="range" class="range-min" 
                               min="${param.min - param.step * 5}" 
                               max="${param.max + param.step * 5}" 
                               step="${param.step}" 
                               value="${param.min}">
                        <input type="range" class="range-max" 
                               min="${param.min - param.step * 5}" 
                               max="${param.max + param.step * 5}" 
                               step="${param.step}" 
                               value="${param.max}">
                        <div class="slider-track"></div>
                        <div class="slider-range" style="left: 20%; right: 20%;"></div>
                    </div>
                </div>
                <div class="param-range-inputs">
                    <div class="param-input-group">
                        <label>Min</label>
                        <input type="number" class="param-min" value="${param.min}" step="${param.step}">
                    </div>
                    <div class="param-input-group">
                        <label>Max</label>
                        <input type="number" class="param-max" value="${param.max}" step="${param.step}">
                    </div>
                    <div class="param-input-group">
                        <label>Step</label>
                        <input type="number" class="param-step" value="${param.step}" step="any">
                    </div>
                </div>
                <div class="param-range-info">
                    <span class="param-combinations">
                        <i class="bi bi-layers"></i> ${this.calculateParamCombinations(param)} values
                    </span>
                </div>
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
        return `
            <div class="wf-inputs">
                <div class="wf-input-group">
                    <label>Train Window (days)</label>
                    <input type="number" id="wfTrainSize" value="${this.state.dataPeriod.wfTrainSize}" min="30" max="365">
                </div>
                <div class="wf-input-group">
                    <label>Test Window (days)</label>
                    <input type="number" id="wfTestSize" value="${this.state.dataPeriod.wfTestSize}" min="7" max="90">
                </div>
                <div class="wf-input-group">
                    <label>Step Size (days)</label>
                    <input type="number" id="wfStepSize" value="${this.state.dataPeriod.wfStepSize}" min="7" max="90">
                </div>
            </div>
            <div class="wf-preview" id="wfPreview">
                ${this.renderWalkForwardPreview()}
            </div>
        `;
    }

    /**
     * Render walk-forward preview
     */
    renderWalkForwardPreview() {
        const { wfTrainSize, wfTestSize, wfStepSize, startDate, endDate } = this.state.dataPeriod;
        const start = new Date(startDate);
        const end = new Date(endDate);
        const totalDays = Math.floor((end - start) / (1000 * 60 * 60 * 24));
        const numFolds = Math.floor((totalDays - wfTrainSize) / wfStepSize);

        return `
            <div class="wf-preview-info">
                <span><i class="bi bi-layers"></i> ${Math.max(1, numFolds)} folds</span>
                <span><i class="bi bi-calendar"></i> ${totalDays} days total</span>
            </div>
        `;
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
        const workers = this.state.limits.workers;

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

        return `
            <div class="estimated-time-content">
                <i class="bi bi-clock"></i>
                <span>Estimated time: <strong>${timeStr}</strong></span>
                <span class="text-muted">(~${estimatedTrials.toLocaleString()} trials)</span>
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

        // Train/test split
        this.container.querySelector('#optTrainSplit')?.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.state.dataPeriod.trainSplit = value;
            const trainLabel = this.container.querySelector('.train-label');
            const testLabel = this.container.querySelector('.test-label');
            if (trainLabel) trainLabel.textContent = `Train: ${Math.round(value * 100)}%`;
            if (testLabel) testLabel.textContent = `Test: ${Math.round((1 - value) * 100)}%`;
            this.saveState();
        });

        // Limits
        this.container.querySelector('#optMaxTrials')?.addEventListener('change', (e) => {
            this.state.limits.maxTrials = parseInt(e.target.value) || 200;
            this.updateEstimatedTime();
            this.saveState();
        });

        this.container.querySelector('#optTimeout')?.addEventListener('change', (e) => {
            this.state.limits.timeoutSeconds = parseInt(e.target.value) || 3600;
            this.saveState();
        });

        this.container.querySelector('#optWorkers')?.addEventListener('change', (e) => {
            this.state.limits.workers = parseInt(e.target.value) || 4;
            this.updateEstimatedTime();
            this.saveState();
        });

        // Advanced Options — всегда развёрнуты (внутри блоков ничего не сворачивается)

        // Advanced options
        this.container.querySelector('#optEarlyStopping')?.addEventListener('change', (e) => {
            this.state.advanced.earlyStopping = e.target.checked;
            const patience = this.container.querySelector('#optEarlyStoppingPatience');
            patience?.classList.toggle('disabled', !e.target.checked);
            this.saveState();
        });

        this.container.querySelector('#optEarlyStoppingPatience')?.addEventListener('change', (e) => {
            this.state.advanced.earlyStoppingPatience = parseInt(e.target.value) || 20;
            this.saveState();
        });

        this.container.querySelector('#optPruneInfeasible')?.addEventListener('change', (e) => {
            this.state.advanced.pruneInfeasible = e.target.checked;
            this.saveState();
        });

        this.container.querySelector('#optWarmStart')?.addEventListener('change', (e) => {
            this.state.advanced.warmStart = e.target.checked;
            this.saveState();
        });

        this.container.querySelector('#optRandomSeed')?.addEventListener('change', (e) => {
            const val = e.target.value;
            this.state.advanced.randomSeed = val ? parseInt(val) : null;
            this.saveState();
        });

        // Parameter range inputs (delegated)
        this.container.querySelector('#optParamRanges')?.addEventListener('change', (e) => {
            this.handleParamRangeChange(e);
        });

        // Walk-forward inputs
        ['wfTrainSize', 'wfTestSize', 'wfStepSize'].forEach(id => {
            this.container.querySelector(`#${id}`)?.addEventListener('change', (e) => {
                const key = id;
                this.state.dataPeriod[key] = parseInt(e.target.value);
                this.updateWalkForwardPreview();
                this.saveState();
            });
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
        const event = new CustomEvent('startOptimization', {
            detail: this.getConfig()
        });
        document.dispatchEvent(event);
    }

    /**
     * Get current configuration
     */
    getConfig() {
        return {
            method: this.state.method,
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
                end_date: this.getBacktestEndDate(),
                train_split: this.state.dataPeriod.trainSplit,
                walk_forward: this.state.method === 'walk_forward' ? {
                    train_size: this.state.dataPeriod.wfTrainSize,
                    test_size: this.state.dataPeriod.wfTestSize,
                    step_size: this.state.dataPeriod.wfStepSize
                } : null
            },
            limits: this.state.limits,
            advanced: this.state.advanced,
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
                // Merge with default, preserving structure
                this.state = {
                    ...this.state,
                    ...parsed,
                    dataPeriod: { ...this.state.dataPeriod, ...parsed.dataPeriod },
                    limits: { ...this.state.limits, ...parsed.limits },
                    advanced: { ...this.state.advanced, ...parsed.advanced }
                };
                this.render();
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
