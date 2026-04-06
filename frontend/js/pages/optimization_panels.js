/**
 * 🎯 Optimization Panels Module
 *
 * Manages the Evaluation Criteria, Optimization Config, and Results panels
 * in the Strategy Builder sidebar.
 *
 * INTEGRATION with strategy_builder.js:
 * - Reads optimizationParams from strategyBlocks
 * - Auto-detects mode: Single Backtest vs Optimization
 * - Syncs parameter ranges with block popup settings
 *
 * ENGINES:
 * - Single Backtest: FallbackEngineV4 (reference, accurate)
 * - Optimization: NumbaEngineV2 (fast, 100% parity with V4)
 *
 * @version 2.0.0
 * @date 2025-01-30
 */

class OptimizationPanels {
    constructor() {
        this.state = {
            // Evaluation Criteria
            primaryMetric: 'sharpe_ratio',
            secondaryMetrics: ['win_rate', 'max_drawdown', 'profit_factor'],
            constraints: [
                { metric: 'max_drawdown', operator: '<=', value: 15, unit: '%' },
                { metric: 'min_trades', operator: '>=', value: 50, unit: '' }
            ],

            // Optimization Config
            method: 'bayesian',
            startDate: '2025-01-01',
            endDate: '2030-01-01',
            maxTrials: 200,
            workers: 4,
            parameterRanges: [],

            // Results
            isRunning: false,
            progress: 0,
            currentJobId: null,
            lastResults: null,

            // Run mode (auto-detected)
            runMode: 'single' // 'single' or 'optimization'
        };

        this.pollInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSavedState();
        // Note: Collapsible sections are handled by sidebar-toggle.js

        // Listen for block changes from strategy_builder.js
        this.setupBlockIntegration();

        // Auto-fetch optimizable params for builder strategies
        const builderStrategyId = this.getBuilderStrategyId();
        if (builderStrategyId) {
            // Delay slightly so DOM is ready
            setTimeout(() => this.fetchBuilderOptimizableParams(builderStrategyId), 1500);
        }

        // Listen for startOptimization event from optimization_config_panel.js
        document.addEventListener('startOptimization', (e) => {
            console.log('[OptPanels] Received startOptimization event:', e.detail);
            // Merge config from the event
            if (e.detail) {
                this.state.method = e.detail.method || this.state.method;
                this.state.maxTrials = e.detail.limits?.maxTrials || this.state.maxTrials;
                this.state.workers = e.detail.limits?.workers || this.state.workers;
                this.state.timeoutSeconds = e.detail.limits?.timeoutSeconds || this.state.timeoutSeconds;

                // Advanced optimization settings
                if (e.detail.advanced) {
                    this.state.earlyStopping = e.detail.advanced.earlyStopping ?? false;
                    this.state.earlyStoppingPatience = e.detail.advanced.earlyStoppingPatience ?? 20;
                    this.state.warmStart = e.detail.advanced.warmStart ?? false;
                    this.state.pruneInfeasible = e.detail.advanced.pruneInfeasible ?? true;
                    this.state.randomSeed = e.detail.advanced.randomSeed ?? null;
                }

                // Data period settings (train/test split)
                if (e.detail.data_period) {
                    this.state.trainSplit = e.detail.data_period.train_split ?? 0.8;
                }

                // Walk-Forward settings
                if (e.detail.walk_forward) {
                    this.state.wfNSplits = e.detail.walk_forward.n_splits ?? 5;
                    this.state.wfTrainRatio = e.detail.walk_forward.train_ratio ?? 0.7;
                    this.state.wfGapPeriods = e.detail.walk_forward.gap_periods ?? 0;
                    this.state.wfInnerMethod = e.detail.walk_forward.inner_method ?? 'grid';
                }

                // Capture optimize_metric for display after completion
                if (e.detail.optimize_metric) {
                    this.state.lastOptimizeMetric = e.detail.optimize_metric;
                }

                // Parameter ranges from config panel
                if (e.detail.parameter_ranges && e.detail.parameter_ranges.length > 0) {
                    // Keep full objects — buildBuilderParameterRanges() needs param_path, low, high, step
                    this.state.parameterRanges = e.detail.parameter_ranges.map(p => ({
                        name: p.name,
                        param_path: p.param_path,
                        low: p.low,
                        high: p.high,
                        step: p.step
                    }));
                    this.state.runMode = 'optimization';
                } else {
                    // Event sent empty ranges — try to pull live from OptimizationConfigPanel state
                    // (happens when loadSavedState restores an older empty snapshot)
                    const liveRanges = window.optimizationConfigPanel?.state?.parameterRanges;
                    if (liveRanges && liveRanges.length > 0) {
                        this.state.parameterRanges = liveRanges.map(p => ({
                            name: p.id || p.name,
                            param_path: p.param_path || `${p.blockId}.${p.paramKey}`,
                            low: p.low ?? p.min ?? 0,
                            high: p.high ?? p.max ?? 100,
                            step: p.step ?? 1
                        }));
                        this.state.runMode = 'optimization';
                        console.log('[OptPanels] Pulled', this.state.parameterRanges.length, 'param ranges from OptimizationConfigPanel live state');
                    } else {
                        // Truly no params — run as single backtest
                        this.state.parameterRanges = [];
                        this.state.runMode = 'single';
                    }
                }
            }
            this.startRun();
        });
    }

    /**
     * Setup integration with strategy_builder.js
     * Listen for block updates and sync optimization params
     */
    setupBlockIntegration() {
        // Custom event listener for block changes
        document.addEventListener('strategyBlocksChanged', (e) => {
            const blocks = e.detail?.blocks || [];
            this.syncWithStrategyBlocks(blocks);
        });

        // Also check periodically for changes (fallback)
        setInterval(() => {
            if (window.strategyBlocks) {
                this.syncWithStrategyBlocks(window.strategyBlocks);
            }
        }, 1000);
    }

    /**
     * Sync optimization params from strategy blocks
     * This reads optimizationParams directly from blocks
     */
    syncWithStrategyBlocks(blocks) {
        if (!blocks || !Array.isArray(blocks)) return;

        const params = this.extractOptimizationParamsFromBlocks(blocks);
        const hasOptimization = params.length > 0;

        // Update run mode
        const previousMode = this.state.runMode;
        this.state.runMode = hasOptimization ? 'optimization' : 'single';

        // Update UI if mode changed
        if (previousMode !== this.state.runMode) {
            this.updateRunModeUI();
        }

        // Update parameter ranges list
        this.updateParameterRangesFromBlocks(params);
    }

    /**
     * Read trading parameters from Properties panel DOM elements.
     * These values must match what the user configured in the "Параметры" panel.
     */
    getPropertiesPanelValues() {
        const symbolEl = document.getElementById('backtestSymbol');
        const timeframeEl = document.getElementById('strategyTimeframe');
        const directionEl = document.getElementById('builderDirection');
        const capitalEl = document.getElementById('backtestCapital');
        const leverageEl = document.getElementById('backtestLeverageRange') || document.getElementById('backtestLeverage');
        const commissionEl = document.getElementById('backtestCommission');
        const marketTypeEl = document.getElementById('builderMarketType');

        // Keep Bybit timeframe codes as-is — the backend BuilderOptimizationRequest
        // validates only Bybit codes: 1/5/15/30/60/240/D/W/M.
        // DO NOT convert to 1m/15m/1h etc. here.
        const rawTf = timeframeEl?.value || '15';
        const interval = rawTf;

        // Commission: UI shows percentage (0.07), API expects fraction (0.0007)
        const commissionPct = parseFloat(commissionEl?.value) || 0.07;
        const commission = commissionPct / 100;

        // Detect strategy_type from blocks
        let strategyType = 'rsi'; // default
        if (window.strategyBlocks && Array.isArray(window.strategyBlocks)) {
            const mainBlock = window.strategyBlocks.find(b => b.isMain);
            if (mainBlock) {
                const blockType = (mainBlock.type || mainBlock.id || '').toLowerCase();
                if (blockType.includes('sma') || blockType.includes('crossover')) {
                    strategyType = 'sma_crossover';
                } else if (blockType.includes('macd')) {
                    strategyType = 'macd';
                } else if (blockType.includes('bb') || blockType.includes('bollinger')) {
                    strategyType = 'bollinger_bands';
                }
                // else default 'rsi'
            }
        }

        return {
            symbol: (symbolEl?.value || 'BTCUSDT').trim().toUpperCase(),
            interval,
            direction: directionEl?.value || 'both',
            initial_capital: parseFloat(capitalEl?.value) || 10000,
            leverage: parseInt(leverageEl?.value, 10) || 10,
            commission,
            strategy_type: strategyType,
            market_type: marketTypeEl?.value || 'linear'
        };
    }

    /**
     * Период бэктеста/оптимизации из блока «Основные параметры» (Start Date / End Date)
     */
    getBacktestDates() {
        const startEl = document.getElementById('backtestStartDate');
        const endEl = document.getElementById('backtestEndDate');
        // Use local date (not UTC) to avoid off-by-one at midnight in UTC+N timezones
        const _now = new Date();
        const today = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`;
        let endDate = endEl?.value || '2030-01-01';
        if (endDate > today) endDate = today;
        return {
            startDate: startEl?.value || '2025-01-01',
            endDate
        };
    }

    /**
     * Extract optimization parameters from strategy blocks
     * Reads block.optimizationParams set by the popup in strategy_builder.js
     */
    extractOptimizationParamsFromBlocks(blocks) {
        const params = [];

        if (!blocks || !Array.isArray(blocks)) return params;

        blocks.forEach(block => {
            // Skip if no optimization params or no params object
            if (!block.optimizationParams || !block.params) return;

            // Get block info for labels
            const blockType = block.type || block.id || 'unknown';
            const blockName = block.name || blockType.toUpperCase();

            // Check each parameter
            Object.entries(block.optimizationParams).forEach(([paramKey, optConfig]) => {
                // Only include if optimization is ENABLED for this param
                if (!optConfig || !optConfig.enabled) return;

                const currentValue = block.params[paramKey];
                params.push({
                    blockId: block.id,
                    paramKey: paramKey,
                    name: `${block.id}_${paramKey}`,
                    label: `${blockName} ${this.formatParamName(paramKey)}`,
                    currentValue: currentValue,
                    min: optConfig.min ?? currentValue,
                    max: optConfig.max ?? currentValue,
                    step: optConfig.step ?? 1,
                    enabled: true
                });
            });
        });

        return params;
    }

    /**
     * Format parameter name for display
     */
    formatParamName(key) {
        // Convert snake_case or camelCase to Title Case
        return key
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Update run mode UI (Single Backtest vs Optimization)
     */
    updateRunModeUI() {
        const btnStart = document.getElementById('btnStartOptimization');
        const modeIndicator = document.getElementById('runModeIndicator');

        if (this.state.runMode === 'single') {
            // Single Backtest mode
            if (btnStart) {
                btnStart.innerHTML = '<i class="bi bi-play-fill"></i> Run Backtest';
                btnStart.title = 'Run single backtest with current parameters (FallbackEngineV4)';
            }
            if (modeIndicator) {
                modeIndicator.innerHTML = `
                    <span class="badge bg-info">
                        <i class="bi bi-1-circle"></i> Single Backtest
                    </span>
                    <small class="text-muted d-block mt-1">
                        Enable optimization on indicator params to switch mode
                    </small>
                `;
            }
        } else {
            // Optimization mode
            if (btnStart) {
                btnStart.innerHTML = '<i class="bi bi-lightning-fill"></i> Start Optimization';
                btnStart.title = 'Run parameter optimization (NumbaEngineV2, ~20-40x faster)';
            }
            if (modeIndicator) {
                const paramCount = this.state.parameterRanges.length;
                const totalCombinations = this.calculateTotalCombinations();
                modeIndicator.innerHTML = `
                    <span class="badge bg-warning text-dark">
                        <i class="bi bi-sliders"></i> Optimization
                    </span>
                    <small class="text-muted d-block mt-1">
                        ${paramCount} params, ~${totalCombinations} combinations
                    </small>
                `;
            }
        }
    }

    /**
     * Calculate total combinations for grid search
     */
    calculateTotalCombinations() {
        if (this.state.parameterRanges.length === 0) return 0;

        let total = 1;
        this.state.parameterRanges.forEach(param => {
            // Support both {low, high} (from optimization_config_panel event) and {min, max} (from DOM path)
            const lo = param.low ?? param.min ?? 0;
            const hi = param.high ?? param.max ?? 100;
            const st = param.step ?? 1;
            const steps = Math.max(1, Math.floor((hi - lo) / st) + 1);
            total *= steps;
        });
        return total;
    }

    /**
     * Update parameter ranges list from blocks
     */
    updateParameterRangesFromBlocks(params) {
        const rangesList = document.getElementById('paramRangesList');
        if (!rangesList) return;

        // Clear existing
        rangesList.innerHTML = '';

        if (params.length === 0) {
            rangesList.innerHTML = `
                <p class="text-muted text-sm">
                    <i class="bi bi-info-circle"></i>
                    Click <strong>Optimization</strong> in indicator blocks to enable parameter ranges
                </p>
            `;
            this.state.parameterRanges = [];
            return;
        }

        // Create range UI for each parameter
        params.forEach(param => {
            const item = document.createElement('div');
            item.className = 'param-range-item';
            item.dataset.blockId = param.blockId;
            item.dataset.paramKey = param.paramKey;
            item.innerHTML = `
                <div class="param-range-header">
                    <span class="param-range-name">${param.label}</span>
                    <span class="param-range-current text-muted">(current: ${param.currentValue})</span>
                </div>
                <div class="param-range-inputs">
                    <div class="param-range-field">
                        <label>Min</label>
                        <input type="number" data-type="min" value="${param.min}" />
                    </div>
                    <div class="param-range-field">
                        <label>Max</label>
                        <input type="number" data-type="max" value="${param.max}" />
                    </div>
                    <div class="param-range-field">
                        <label>Step</label>
                        <input type="number" data-type="step" value="${param.step}" step="any" />
                    </div>
                </div>
            `;
            rangesList.appendChild(item);
        });

        // Bind events for parameter inputs - sync back to blocks
        rangesList.querySelectorAll('input').forEach(input => {
            input.addEventListener('change', (e) => {
                const item = e.target.closest('.param-range-item');
                if (item) {
                    this.syncParamBackToBlock(item);
                }
                this.collectParameterRanges();
                this.saveState();
            });
        });

        // Collect ranges for state — preserve blockId/paramKey so buildBuilderParameterRanges()
        // can construct correct "blockId.paramKey" param_path for the backend
        this.state.parameterRanges = params.map(p => ({
            name: p.name,
            blockId: p.blockId,
            paramKey: p.paramKey,
            min: p.min,
            max: p.max,
            step: p.step
        }));
    }

    /**
     * Sync parameter changes back to the strategy block
     */
    syncParamBackToBlock(item) {
        const blockId = item.dataset.blockId;
        const paramKey = item.dataset.paramKey;

        if (!blockId || !paramKey) return;

        const min = parseFloat(item.querySelector('input[data-type="min"]')?.value) || 0;
        const max = parseFloat(item.querySelector('input[data-type="max"]')?.value) || 100;
        const step = parseFloat(item.querySelector('input[data-type="step"]')?.value) || 1;

        // Find block in global strategyBlocks
        if (window.strategyBlocks) {
            const block = window.strategyBlocks.find(b => b.id === blockId);
            if (block && block.optimizationParams && block.optimizationParams[paramKey]) {
                block.optimizationParams[paramKey].min = min;
                block.optimizationParams[paramKey].max = max;
                block.optimizationParams[paramKey].step = step;
                console.log(`[OptPanels] Synced ${blockId}.${paramKey}: min=${min}, max=${max}, step=${step}`);
            }
        }
    }

    /**
     * Bind all event listeners
     */
    bindEvents() {
        // Primary Metric
        const primaryMetricSelect = document.getElementById('primaryMetric');
        if (primaryMetricSelect) {
            primaryMetricSelect.addEventListener('change', (e) => {
                this.state.primaryMetric = e.target.value;
                this.saveState();
            });
        }

        // Secondary Metrics checkboxes
        document.querySelectorAll('.criteria-checkbox-item input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSecondaryMetrics();
                this.saveState();
            });
        });

        // Add Constraint button
        const btnAddConstraint = document.getElementById('btnAddConstraint');
        if (btnAddConstraint) {
            btnAddConstraint.addEventListener('click', () => this.addConstraint());
        }

        // Constraint remove buttons (delegated)
        document.getElementById('constraintsList')?.addEventListener('click', (e) => {
            if (e.target.closest('.constraint-remove')) {
                const item = e.target.closest('.constraint-item');
                if (item) {
                    item.remove();
                    this.updateConstraints();
                    this.saveState();
                }
            }
        });

        // Constraint inputs (delegated)
        document.getElementById('constraintsList')?.addEventListener('change', () => {
            this.updateConstraints();
            this.saveState();
        });

        // Optimization Method
        const optMethod = document.getElementById('optMethod');
        if (optMethod) {
            optMethod.addEventListener('change', (e) => {
                this.state.method = e.target.value;
                this.saveState();
            });
        }

        // Период берётся из блока «Основные параметры» (backtestStartDate / backtestEndDate)

        // Max Trials
        const optMaxTrials = document.getElementById('optMaxTrials');
        if (optMaxTrials) {
            optMaxTrials.addEventListener('change', (e) => {
                this.state.maxTrials = parseInt(e.target.value) || 200;
                this.saveState();
            });
        }

        // Workers
        const optWorkers = document.getElementById('optWorkers');
        if (optWorkers) {
            optWorkers.addEventListener('change', (e) => {
                this.state.workers = parseInt(e.target.value) || 4;
                this.saveState();
            });
        }

        // NOTE: #btnStartOptimization click is handled by optimization_config_panel.js
        // which dispatches the 'startOptimization' event with parameter ranges.
        // Do NOT add a direct click listener here — it causes duplicate API calls.

        // View Full Results button
        const btnViewResults = document.getElementById('btnViewFullResults');
        if (btnViewResults) {
            btnViewResults.addEventListener('click', () => {
                if (this.state.lastResults) {
                    // Store results in sessionStorage for results page
                    sessionStorage.setItem('optimizationResults', JSON.stringify(this.state.lastResults));
                }
            });
        }
    }

    /**
     * Update secondary metrics from checkboxes
     */
    updateSecondaryMetrics() {
        const metrics = [];
        const checkboxMap = {
            'metricWinRate': 'win_rate',
            'metricMaxDD': 'max_drawdown',
            'metricProfitFactor': 'profit_factor',
            'metricExpectancy': 'expectancy',
            'metricCAGR': 'cagr'
        };

        Object.entries(checkboxMap).forEach(([id, metric]) => {
            const checkbox = document.getElementById(id);
            if (checkbox?.checked) {
                metrics.push(metric);
            }
        });

        this.state.secondaryMetrics = metrics;
    }

    /**
     * Update constraints from DOM
     */
    updateConstraints() {
        const constraints = [];
        document.querySelectorAll('.constraint-item').forEach(item => {
            const metric = item.querySelector('.constraint-metric')?.value;
            const operator = item.querySelector('.constraint-operator')?.value;
            const value = parseFloat(item.querySelector('.constraint-value')?.value) || 0;
            const unit = item.querySelector('.constraint-unit')?.textContent || '';

            if (metric) {
                constraints.push({ metric, operator, value, unit });
            }
        });

        this.state.constraints = constraints;
    }

    /**
     * Add a new constraint
     */
    addConstraint() {
        const list = document.getElementById('constraintsList');
        if (!list) return;

        const newConstraint = document.createElement('div');
        newConstraint.className = 'constraint-item';
        newConstraint.innerHTML = `
            <select class="constraint-metric" title="Constraint metric">
                <option value="max_drawdown">Max DD</option>
                <option value="min_trades">Min Trades</option>
                <option value="min_sharpe">Min Sharpe</option>
                <option value="min_profit_factor">Min PF</option>
                <option value="min_win_rate">Min Win%</option>
            </select>
            <select class="constraint-operator" title="Operator">
                <option value="<=">&le;</option>
                <option value=">=">&ge;</option>
                <option value="<">&lt;</option>
                <option value=">">&gt;</option>
            </select>
            <input type="number" class="constraint-value" value="0" title="Value" />
            <span class="constraint-unit">%</span>
            <button class="constraint-remove" title="Remove" aria-label="Remove constraint">
                <i class="bi bi-x"></i>
            </button>
        `;

        list.appendChild(newConstraint);
        this.updateConstraints();
        this.saveState();
    }

    /**
     * Update parameter ranges based on strategy blocks
     */
    updateParameterRanges(blocks) {
        const rangesList = document.getElementById('paramRangesList');
        if (!rangesList) return;

        // Clear existing
        rangesList.innerHTML = '';

        // Get parameters from strategy blocks
        const params = this.extractParametersFromBlocks(blocks);

        if (params.length === 0) {
            rangesList.innerHTML = `
                <p class="text-muted text-sm">
                    <i class="bi bi-info-circle"></i>
                    Add indicator blocks to configure parameter ranges
                </p>
            `;
            return;
        }

        // Create range UI for each parameter
        params.forEach(param => {
            const item = document.createElement('div');
            item.className = 'param-range-item';
            item.dataset.param = param.name;
            item.innerHTML = `
                <div class="param-range-header">
                    <span class="param-range-name">${param.label}</span>
                    <input type="checkbox" class="param-range-toggle"
                           ${param.optimize ? 'checked' : ''} title="Include in optimization" />
                </div>
                <div class="param-range-inputs">
                    <div class="param-range-field">
                        <label>Min</label>
                        <input type="number" data-type="min" value="${param.min}" />
                    </div>
                    <div class="param-range-field">
                        <label>Max</label>
                        <input type="number" data-type="max" value="${param.max}" />
                    </div>
                    <div class="param-range-field">
                        <label>Step</label>
                        <input type="number" data-type="step" value="${param.step}" />
                    </div>
                </div>
            `;
            rangesList.appendChild(item);
        });

        // Bind events for parameter inputs
        rangesList.querySelectorAll('input').forEach(input => {
            input.addEventListener('change', () => {
                this.collectParameterRanges();
                this.saveState();
            });
        });

        this.collectParameterRanges();
    }

    /**
     * Extract optimizable parameters from strategy blocks
     */
    extractParametersFromBlocks(blocks) {
        const params = [];

        if (!blocks || !Array.isArray(blocks)) return params;

        blocks.forEach(block => {
            if (block.type === 'indicator' && block.config) {
                // RSI
                if (block.config.indicator === 'rsi') {
                    params.push({
                        name: `${block.id}_period`,
                        label: `RSI Period (${block.id})`,
                        min: block.config.period || 14,
                        max: 30,
                        step: 1,
                        optimize: true
                    });
                }
                // SMA/EMA
                else if (['sma', 'ema'].includes(block.config.indicator)) {
                    params.push({
                        name: `${block.id}_period`,
                        label: `${block.config.indicator.toUpperCase()} Period`,
                        min: 5,
                        max: block.config.period || 20,
                        step: 1,
                        optimize: true
                    });
                }
            }
            // Stop Loss / Take Profit
            else if (block.type === 'exit') {
                if (block.config?.stopLoss) {
                    params.push({
                        name: `${block.id}_stop_loss`,
                        label: 'Stop Loss %',
                        min: 0.5,
                        max: 5,
                        step: 0.1,
                        optimize: true
                    });
                }
                if (block.config?.takeProfit) {
                    params.push({
                        name: `${block.id}_take_profit`,
                        label: 'Take Profit %',
                        min: 0.5,
                        max: 5,
                        step: 0.1,
                        optimize: true
                    });
                }
            }
        });

        return params;
    }

    /**
     * Collect parameter ranges from UI
     */
    collectParameterRanges() {
        const ranges = [];

        document.querySelectorAll('.param-range-item').forEach(item => {
            // In new version, all items in the list are enabled (from blocks)
            const name = item.dataset.blockId + '_' + item.dataset.paramKey;
            const min = parseFloat(item.querySelector('input[data-type="min"]')?.value) || 0;
            const max = parseFloat(item.querySelector('input[data-type="max"]')?.value) || 100;
            const step = parseFloat(item.querySelector('input[data-type="step"]')?.value) || 1;

            ranges.push({ name, min, max, step });
        });

        this.state.parameterRanges = ranges;
    }

    /**
     * Start backtest or optimization based on mode
     * - Single mode: FallbackEngineV4 (accurate, single run)
     * - Optimization mode: NumbaEngineV2 (fast, grid search)
     */
    async startRun() {
        if (this.state.runMode === 'single') {
            await this.runSingleBacktest();
        } else {
            await this.startOptimization();
        }
    }

    /**
     * Run single backtest with FallbackEngineV4
     */
    async runSingleBacktest() {
        // Get strategy ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        const strategyId = urlParams.get('id');

        if (!strategyId) {
            this.showNotification('Сначала сохраните стратегию перед запуском бэктеста', 'warning');
            return;
        }

        try {
            this.setRunningState(true, 'single');

            const props = this.getPropertiesPanelValues();
            const { startDate: sd, endDate: ed } = this.getBacktestDates();
            const payload = {
                start_date: sd + 'T00:00:00Z',
                end_date: ed + 'T23:59:59Z',
                engine: 'single', // FallbackEngineV4
                commission: props.commission,
                slippage: 0.0005,
                leverage: props.leverage,
                pyramiding: 1
            };

            const response = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}/backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();

            this.showNotification('Backtest completed!', 'success');

            // Redirect to results if backtest_id returned
            if (data.backtest_id) {
                window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
            }

        } catch (error) {
            console.error('Failed to run backtest:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        } finally {
            this.setRunningState(false);
        }
    }

    /**
     * Detect if we are in Strategy Builder context (has saved strategy with builder blocks)
     * @returns {string|null} Strategy ID if in builder context, null otherwise
     */
    getBuilderStrategyId() {
        const urlParams = new URLSearchParams(window.location.search);
        const strategyId = urlParams.get('id');
        // Strategy Builder page always has /strategy-builder in path
        const isBuilderPage = window.location.pathname.includes('strategy-builder');
        return (isBuilderPage && strategyId) ? strategyId : null;
    }

    /**
     * Start optimization — routes to Builder endpoint or classic endpoint
     * - Builder strategies: POST /api/v1/strategy-builder/strategies/{id}/optimize
     * - Classic strategies: POST /api/v1/optimizations/sync/grid-search or optuna-search
     */
    async startOptimization() {
        // Guard against double-click / double invocation
        if (this.state.isRunning) {
            console.warn('[OptPanels] startOptimization called while already running — ignored');
            return;
        }

        // Validate
        if (this.state.parameterRanges.length === 0) {
            this.showNotification('No optimization parameters enabled', 'warning');
            return;
        }

        // Get strategy ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        const strategyId = urlParams.get('id');

        if (!strategyId) {
            this.showNotification('Сначала сохраните стратегию перед оптимизацией', 'warning');
            return;
        }

        // Detect context: Builder strategy or classic strategy
        const builderStrategyId = this.getBuilderStrategyId();

        if (builderStrategyId) {
            await this.startBuilderOptimization(builderStrategyId);
        } else {
            await this.startClassicOptimization(strategyId);
        }
    }

    /**
     * Start optimization for Strategy Builder strategies.
     * Uses POST /api/v1/strategy-builder/strategies/{id}/optimize
     * with BuilderOptimizationRequest payload.
     * Polls GET .../optimize/progress every 2s for real-time progress feedback.
     */
    async startBuilderOptimization(strategyId) {
        try {
            this.setRunningState(true, 'optimization');

            // Get evaluation criteria from EvaluationCriteriaPanel
            const evalCriteria = window.evaluationCriteriaPanel?.getCriteria() || {
                primary_metric: this.state.lastOptimizeMetric || this.state.primaryMetric,
                secondary_metrics: this.state.secondaryMetrics,
                constraints: [],
                sort_order: [],
                use_composite: false,
                weights: null
            };

            const props = this.getPropertiesPanelValues();
            const { startDate: sd, endDate: ed } = this.getBacktestDates();

            // Build parameter_ranges from collected UI state (block_id.param_key format)
            const parameterRanges = this.buildBuilderParameterRanges();

            // Guard: detect degenerate ranges (min === max) from stale saved state.
            // These produce only 1 combo and make optimization pointless.
            const degenerate = parameterRanges.filter(p => p.low === p.high);
            if (degenerate.length > 0) {
                const names = degenerate.map(p => p.param_path.split('.').pop()).join(', ');
                this.setRunningState(false);
                this.showNotification(
                    `⚠️ Parameter range issue: "${names}" has min = max. Open the block, check optimization ranges, and try again.`,
                    'warning'
                );
                return;
            }

            // Map method name for backend (all methods pass through directly)
            const methodMap = {
                'grid_search': 'grid_search',
                'random_search': 'random_search',
                'bayesian': 'bayesian',
                'walk_forward': 'walk_forward'
            };

            // Walk-Forward config (from optimization_config_panel state)
            const wfConfig = this.state.method === 'walk_forward' ? {
                n_splits: this.state.wfNSplits || 5,
                train_ratio: this.state.wfTrainRatio || 0.7,
                gap_periods: this.state.wfGapPeriods || 0,
                inner_method: this.state.wfInnerMethod || 'grid'
            } : null;

            const payload = {
                symbol: props.symbol,
                interval: props.interval,
                start_date: sd,
                end_date: ed,
                market_type: props.market_type || 'linear',
                initial_capital: props.initial_capital,
                leverage: props.leverage,
                commission: props.commission,
                direction: props.direction,
                method: methodMap[this.state.method] || 'grid_search',
                parameter_ranges: parameterRanges.length > 0 ? parameterRanges : [],
                max_iterations: this.state.maxTrials,
                n_trials: this.state.maxTrials,
                sampler_type: 'tpe',
                timeout_seconds: this.state.timeoutSeconds || 3600,
                max_results: 20,
                early_stopping: this.state.earlyStopping ?? false,
                early_stopping_patience: this.state.earlyStoppingPatience ?? 20,
                optimize_metric: evalCriteria.primary_metric || 'sharpe_ratio',
                ranking_mode: evalCriteria.ranking_mode || 'single',
                secondary_metrics: evalCriteria.secondary_metrics || [],
                weights: evalCriteria.weights || null,
                constraints: evalCriteria.constraints || null,
                sort_order: evalCriteria.sort_order || null,
                use_composite: evalCriteria.use_composite ?? false,
                min_trades: (() => {
                    // Read min_trades from constraints.
                    // Supports both 'total_trades' (EvaluationCriteriaPanel) and legacy 'min_trades'.
                    const all = evalCriteria.constraints || this.state.constraints || [];
                    const c = all.find(x =>
                        (x.metric === 'total_trades' || x.metric === 'min_trades') && x.operator === '>='
                    );
                    return c ? Math.max(1, parseInt(c.value) || 1) : 10;
                })(),
                ...(wfConfig ? { walk_forward: wfConfig } : {})
            };

            // Remember the metric used so displayQuickResults can show it
            this.state.lastOptimizeMetric = payload.optimize_metric;

            const endpoint = `/api/v1/strategy-builder/strategies/${strategyId}/optimize`;
            console.log(`[OptPanels] Builder optimization → ${endpoint}`, payload);

            // Reset progress bar content only — setRunningState already made it visible.
            // Do NOT hide the section (that would undo setRunningState's display:block).
            const _prevFill = document.getElementById('optProgressFill');
            if (_prevFill) _prevFill.style.width = '0%';
            const _prevPct = document.getElementById('optProgressPercent');
            if (_prevPct) _prevPct.textContent = '0%';
            const _prevDetails = document.getElementById('optProgressDetails');
            if (_prevDetails) _prevDetails.textContent = 'Starting optimization...';

            // Track start time so polling can ignore stale data from previous run
            this._optimizationStartTime = Date.now() / 1000;

            // Start progress polling BEFORE firing the long-running POST
            const progressEndpoint = `/api/v1/strategy-builder/strategies/${strategyId}/optimize/progress`;
            this._builderProgressInterval = setInterval(async () => {
                try {
                    const pRes = await fetch(progressEndpoint);
                    if (!pRes.ok) return;
                    const prog = await pRes.json();
                    // Ignore stale data from a previous run (updated_at predates our start)
                    if (prog.updated_at && this._optimizationStartTime &&
                        prog.updated_at < this._optimizationStartTime - 1) {
                        return;
                    }
                    if (prog.status === 'running' || prog.status === 'starting' || prog.status === 'completed' || prog.status === 'partial') {
                        const pct = prog.percent || 0;

                        // Update progress bar inside Optimization panel (not Results)
                        const section = document.getElementById('optProgressSection');
                        const fillEl = document.getElementById('optProgressFill');
                        const pctEl = document.getElementById('optProgressPercent');
                        const detailsEl = document.getElementById('optProgressDetails');

                        if (section) section.style.display = 'block';
                        if (fillEl) fillEl.style.width = `${pct}%`;
                        if (pctEl) pctEl.textContent = `${Math.round(pct)}%`;

                        if (detailsEl) {
                            const tested = prog.tested || 0;
                            const total = prog.total || 0;
                            const speed = prog.speed || 0;
                            const eta = prog.eta_seconds || 0;
                            if (prog.status === 'starting') {
                                detailsEl.textContent = 'Loading market data...';
                            } else if (prog.status === 'running' && total > 0 && tested === 0) {
                                // JIT compiling or just started
                                detailsEl.textContent = `Preparing... ${total.toLocaleString()} combos total`;
                            } else if (prog.status === 'running' && total > 0) {
                                const etaText = eta > 60 ? `${Math.floor(eta / 60)}m ${Math.round(eta % 60)}s` : `${eta}s`;
                                detailsEl.textContent = `${tested.toLocaleString()}/${total.toLocaleString()} · ${speed.toLocaleString()} c/s · ETA ${etaText}`;
                            } else if (prog.status === 'completed') {
                                detailsEl.textContent = `Done — ${total.toLocaleString()} combos`;
                            }
                        }
                    }
                } catch (_e) {
                    console.debug('[OptPanels] Progress poll error:', _e);
                }
            }, 2000);

            // Fire the long-running POST (this blocks until optimization completes)
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            // Stop progress polling once POST completes
            if (this._builderProgressInterval) {
                clearInterval(this._builderProgressInterval);
                this._builderProgressInterval = null;
            }

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            this.handleOptimizationComplete(data);

        } catch (error) {
            // Stop progress polling on error
            if (this._builderProgressInterval) {
                clearInterval(this._builderProgressInterval);
                this._builderProgressInterval = null;
            }
            console.error('[OptPanels] Builder optimization failed:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            this.setRunningState(false);
        }
    }

    /**
     * Build parameter ranges array for Builder optimization API.
     * Priority:
     *   1. this.state.parameterRanges — populated by startOptimization event from
     *      optimization_config_panel.js (already in correct format with blockId/paramKey)
     *   2. DOM fallback — reads .param-range-item elements with data-block-id / data-param-key
     *      (used when called from the old sidebar panel, not the floating config panel)
     *
     * Backend format: [{param_path: "blockId.paramKey", low, high, step, enabled}]
     */
    buildBuilderParameterRanges() {
        // Primary: use state populated from optimization_config_panel event
        if (this.state.parameterRanges && this.state.parameterRanges.length > 0) {
            console.log('[OptPanels] buildBuilderParameterRanges: using state.parameterRanges', this.state.parameterRanges);
            return this.state.parameterRanges.map(p => ({
                // Support both naming conventions from the two sources
                param_path: p.param_path || `${p.blockId || ''}.${p.paramKey || p.name || ''}`,
                low: p.low ?? p.min ?? 0,
                high: p.high ?? p.max ?? 100,
                step: p.step ?? 1,
                enabled: true
            }));
        }

        // Fallback: read from DOM (classic sidebar .param-range-item elements)
        const ranges = [];
        document.querySelectorAll('.param-range-item').forEach(item => {
            const blockId = item.dataset.blockId;
            const paramKey = item.dataset.paramKey;
            if (!blockId || !paramKey) return;

            const toggle = item.querySelector('.param-range-toggle');
            if (toggle && !toggle.checked) return;

            const min = parseFloat(item.querySelector('input[data-type="min"]')?.value) || 0;
            const max = parseFloat(item.querySelector('input[data-type="max"]')?.value) || 100;
            const step = parseFloat(item.querySelector('input[data-type="step"]')?.value) || 1;

            ranges.push({
                param_path: `${blockId}.${paramKey}`,
                low: min,
                high: max,
                step: step,
                enabled: true
            });
        });

        console.log('[OptPanels] buildBuilderParameterRanges: DOM fallback returned', ranges.length, 'ranges');
        return ranges;
    }

    /**
     * Start optimization for classic (non-builder) strategies.
     * Uses POST /api/v1/optimizations/sync/grid-search or optuna-search.
     */
    async startClassicOptimization(_strategyId) {
        try {
            this.setRunningState(true, 'optimization');

            // Build parameter ranges for API
            const paramRanges = this.buildParameterRangesForAPI();

            // Get evaluation criteria from EvaluationCriteriaPanel
            const evalCriteria = window.evaluationCriteriaPanel?.getCriteria() || {
                primary_metric: this.state.primaryMetric,
                secondary_metrics: this.state.secondaryMetrics,
                constraints: [],
                sort_order: [],
                use_composite: false,
                weights: null
            };

            const props = this.getPropertiesPanelValues();
            const { startDate: sd, endDate: ed } = this.getBacktestDates();
            const payload = {
                symbol: props.symbol,
                interval: props.interval,
                start_date: sd,
                end_date: ed,
                strategy_type: props.strategy_type,
                initial_capital: props.initial_capital,
                leverage: props.leverage,
                direction: props.direction,
                commission: props.commission,
                market_type: props.market_type,
                // Engine: NumbaEngineV2 for optimization (fast)
                engine_type: 'optimization',
                // Parameter ranges
                ...paramRanges,
                // Optimization settings from EvaluationCriteriaPanel
                optimize_metric: evalCriteria.primary_metric,
                selection_criteria: evalCriteria.secondary_metrics,
                constraints: evalCriteria.constraints,
                sort_order: evalCriteria.sort_order,
                use_composite: evalCriteria.use_composite,
                weights: evalCriteria.weights,
                max_trials: this.state.maxTrials,
                // Optimization config fields from OptimizationConfigPanel
                workers: this.state.workers || 4,
                timeout_seconds: this.state.timeoutSeconds || 3600,
                train_split: this.state.trainSplit ?? 0.8,
                early_stopping: this.state.earlyStopping ?? false,
                early_stopping_patience: this.state.earlyStoppingPatience ?? 20,
                warm_start: this.state.warmStart ?? false,
                prune_infeasible: this.state.pruneInfeasible ?? true,
                random_seed: this.state.randomSeed ?? null
            };

            console.log('[OptPanels] Classic optimization with:', payload);

            // Route to correct endpoint based on optimization method
            const methodEndpoints = {
                'grid_search': '/api/v1/optimizations/sync/grid-search',
                'bayesian': '/api/v1/optimizations/sync/optuna-search',
                'random_search': '/api/v1/optimizations/sync/grid-search',
                'walk_forward': '/api/v1/optimizations/sync/grid-search'
            };
            const endpoint = methodEndpoints[this.state.method] || '/api/v1/optimizations/sync/grid-search';

            // For random search, set search_method in payload
            if (this.state.method === 'random_search') {
                payload.search_method = 'random';
                payload.max_iterations = this.state.maxTrials;
            }
            // For bayesian, map to optuna fields
            if (this.state.method === 'bayesian') {
                payload.n_trials = this.state.maxTrials;
            }

            console.log(`[OptPanels] Using endpoint: ${endpoint} (method: ${this.state.method})`);

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            // Handle JSON response (sync endpoint)
            const data = await response.json();
            this.handleOptimizationComplete(data);

        } catch (error) {
            console.error('Failed to start optimization:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            this.setRunningState(false);
        }
    }

    /**
     * Fetch optimizable params from backend for a builder strategy.
     * Populates the parameter ranges list with params extracted from the graph.
     * Called when Strategy Builder loads a saved strategy.
     */
    async fetchBuilderOptimizableParams(strategyId) {
        if (!strategyId) return;

        try {
            const response = await fetch(
                `/api/v1/strategy-builder/strategies/${strategyId}/optimizable-params`
            );
            if (!response.ok) {
                console.warn('[OptPanels] Failed to fetch optimizable params:', response.status);
                return;
            }

            const data = await response.json();
            const params = data.optimizable_params || [];

            if (params.length === 0) {
                console.log('[OptPanels] No optimizable params found in strategy');
                return;
            }

            // Convert backend params to UI format and render
            const uiParams = params.map(p => ({
                blockId: p.param_path.split('.')[0],
                paramKey: p.param_key,
                name: p.param_path.replace('.', '_'),
                label: `${p.block_name} ${this.formatParamName(p.param_key)}`,
                currentValue: p.current_value,
                min: p.low,
                max: p.high,
                step: p.step,
                enabled: true
            }));

            this.updateParameterRangesFromBlocks(uiParams);
            console.log(`[OptPanels] Loaded ${uiParams.length} optimizable params from backend`);

        } catch (error) {
            console.warn('[OptPanels] Error fetching optimizable params:', error);
        }
    }

    /**
     * Build parameter ranges for optimization API
     */
    buildParameterRangesForAPI() {
        const ranges = {};

        this.state.parameterRanges.forEach(param => {
            // Split on LAST underscore to handle blockIds with underscores
            // e.g. 'stoch_rsi_period' → blockId='stoch_rsi', paramKey='period'
            // e.g. 'rsi_period' → blockId='rsi', paramKey='period'
            const lastUnderscore = param.name.lastIndexOf('_');
            const paramKey = lastUnderscore >= 0 ? param.name.substring(lastUnderscore + 1) : param.name;

            // Convert to API format (e.g., rsi_period_range: [10, 12, 14, ...])
            const values = [];
            for (let v = param.min; v <= param.max; v += param.step) {
                values.push(Math.round(v * 1000) / 1000); // Round to 3 decimals
            }

            // Determine API key based on param type
            if (paramKey === 'period') {
                ranges['rsi_period_range'] = values;
            } else if (paramKey === 'overbought') {
                ranges['rsi_overbought_range'] = values;
            } else if (paramKey === 'oversold') {
                ranges['rsi_oversold_range'] = values;
            } else if (paramKey === 'stopLoss' || paramKey === 'stop_loss') {
                ranges['stop_loss_range'] = values;
            } else if (paramKey === 'takeProfit' || paramKey === 'take_profit') {
                ranges['take_profit_range'] = values;
            }
        });

        return ranges;
    }

    /**
     * Handle SSE stream for optimization progress
     */
    async handleOptimizationSSE(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        try {
            let done = false;
            while (!done) {
                const result = await reader.read();
                done = result.done;
                if (done) break;

                const text = decoder.decode(result.value);
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.handleOptimizationEvent(data);
                        } catch (_e) {
                            // Ignore parse errors for partial data
                        }
                    }
                }
            }
        } catch (error) {
            console.error('SSE error:', error);
        }
    }

    /**
     * Handle optimization JSON response (sync endpoint)
     */
    handleOptimizationComplete(data) {
        console.log('[OptPanels] handleOptimizationComplete v1773520390 called. best_params:', data.best_params, 'keys count:', Object.keys(data.best_params || {}).length);
        this.setRunningState(false);

        // Hide progress bar in Optimization panel
        const optProgressSection = document.getElementById('optProgressSection');
        if (optProgressSection) optProgressSection.style.display = 'none';
        const fillEl = document.getElementById('optProgressFill');
        if (fillEl) fillEl.style.width = '0%';

        // Capture optimize_metric if returned by backend
        if (data.optimize_metric) {
            this.state.lastOptimizeMetric = data.optimize_metric;
        }

        // Extract results from sync response - map to displayQuickResults format
        // API returns best_metrics at top level; top_results[0] has metrics flat (no .metrics sub-key)
        const bestMetrics = data.best_metrics || {};
        console.log('[OptPanels] data.best_metrics keys:', Object.keys(bestMetrics));
        console.log('[OptPanels] data.top_results count:', data.top_results?.length, 'first:', data.top_results?.[0] ? Object.keys(data.top_results[0]).slice(0, 5) : 'none');

        const results = {
            top_results: data.top_results || [],
            best_params: data.best_params || {},
            best_score: data.best_score || 0,
            total_combinations: data.total_combinations || 0,
            tested_combinations: data.tested_combinations || data.total_combinations || 0,
            execution_time: data.execution_time_seconds || 0,
            smart_recommendations: data.smart_recommendations || null,
            optimize_metric: data.optimize_metric || this.state.lastOptimizeMetric || this.state.primaryMetric || 'sharpe_ratio',
            // Expose best_metrics directly for displayQuickResults
            best_metrics: bestMetrics,
            // Also map to .best.metrics for compatibility
            best: {
                params: data.best_params || {},
                metrics: bestMetrics
            },
            total_trials: data.tested_combinations || data.total_combinations || 0
        };

        this.state.lastResults = results;
        this.saveState();

        // First open the Results panel, THEN render results into it
        // (panel must be visible before innerHTML is written so DOM is active)
        if (typeof window.openFloatingWindow === 'function') {
            window.openFloatingWindow('floatingWindowResults');
        } else {
            // Fallback: remove collapsed class directly and update spine visibility
            const resWin = document.getElementById('floatingWindowResults');
            if (resWin && resWin.classList.contains('floating-window-collapsed')) {
                resWin.classList.remove('floating-window-collapsed');
                document.body.classList.add('floating-window-open');
                if (typeof window.updateSpinesVisibility === 'function') {
                    window.updateSpinesVisibility();
                }
                document.dispatchEvent(new CustomEvent('floatingWindowToggle', {
                    detail: { windowId: 'floatingWindowResults', isOpen: true }
                }));
            }
        }

        // Render results after panel is open (small delay ensures DOM is painted)
        requestAnimationFrame(() => {
            this.displayQuickResults(results);
        });

        // Apply best parameters to strategy blocks, then save + run backtest
        const bestParams = data.best_params || {};
        const bestTrades = data.best_metrics?.total_trades ?? data.top_results?.[0]?.total_trades ?? '?';
        const bestProfit = data.best_metrics?.net_profit ?? data.top_results?.[0]?.net_profit ?? null;
        const testedCount = data.tested_combinations || 0;
        const passingCount = data.results_passing_filters ?? data.results_found ?? 0;
        const fallbackUsed = data.fallback_used === true;

        // Build human-readable constraint summary for fallback notification
        const _buildConstraintSummary = () => {
            const evalCriteria = window.evaluationCriteriaPanel?.getCriteria();
            const constraints = evalCriteria?.constraints || [];
            if (constraints.length === 0) return '';
            return ' Ограничения: ' + constraints.map(c => {
                const label = c.metric.replace(/_/g, ' ');
                return `${label} ${c.operator} ${c.value}`;
            }).join(', ') + '.';
        };

        // Show diagnostic summary so user knows what optimizer found
        const profitStr = bestProfit !== null ? ` net_profit=${bestProfit.toFixed(2)}` : '';
        const fallbackNote = fallbackUsed
            ? ` ⚠️ Ни одна комбинация не прошла фильтры.${_buildConstraintSummary()} Показан лучший без фильтра.`
            : '';
        // Show best params concisely (e.g. "sl=2.0% tp=1.5% period=14")
        const paramStr = Object.entries(bestParams).length > 0
            ? ' | ' + Object.entries(bestParams).map(([k, v]) => {
                const pk = k.split('.').pop();
                const label = pk.replace(/_percent$/, '%').replace(/_/g, ' ');
                const val = typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(2) : v;
                return `${label}=${val}`;
            }).join(', ')
            : ' | нет изменений';
        this.showNotification(
            `📊 Оптимизация: проверено ${testedCount} комбо, прошли фильтр ${passingCount}. ` +
            `Лучший: trades=${bestTrades}${profitStr}${paramStr}${fallbackNote}`,
            fallbackUsed ? 'warning' : 'info'
        );

        if (fallbackUsed) {
            // Don't auto-apply params that violate constraints — user must decide
            this.showNotification(
                '⚠️ 0 комбинаций прошло ограничения. Параметры НЕ применены автоматически. ' +
                'Смягчи ограничения или просмотри результаты таблицы чтобы выбрать вручную.',
                'warning'
            );
        } else if (Object.keys(bestParams).length > 0) {
            this.applyBestParamsToBlocks(bestParams);
        } else if ((data.tested_combinations || 0) > 0) {
            // Optimization ran but returned 0 results — explain why
            this.showNotification(
                '⚠️ Оптимизация завершена, но 0 результатов. ' +
                'Вероятная причина: ни одна комбинация параметров не дала сделок. ' +
                'Проверь: (1) направление стратегии (long/short/both); ' +
                '(2) диапазоны RSI (oversold слишком низко?); ' +
                '(3) запусти обычный бэктест без оптимизации — работает ли стратегия?',
                'warning'
            );
        }

        // Show completion notification
        const msg = `Optimization completed! ${results.tested_combinations} combinations in ${results.execution_time.toFixed(1)}s`;
        this.showNotification(msg, 'success');

        // Show view results button
        const btn = document.getElementById('btnViewFullResults');
        if (btn) btn.style.display = 'block';

        console.log('[OptPanels] Optimization complete:', results);
    }

    /**
     * Apply best_params from optimization result to strategy blocks.
     * best_params format: { "blockId.paramKey": value, ... }
     * After applying: saves the strategy and triggers a backtest.
     */
    applyBestParamsToBlocks(bestParams) {
        console.log('[OptPanels] applyBestParamsToBlocks called with:', bestParams);
        console.log('[OptPanels] window.updateBlockParam available:', typeof window.updateBlockParam);
        console.log('[OptPanels] window.saveStrategy available:', typeof window.saveStrategy);
        console.log('[OptPanels] window.runBacktest available:', typeof window.runBacktest);
        console.log('[OptPanels] window.strategyBlocks available:', typeof window.strategyBlocks, window.strategyBlocks?.length);

        const entries = Object.entries(bestParams);
        if (entries.length === 0) {
            console.warn('[OptPanels] best_params is empty — nothing to apply');
            return;
        }

        let applied = 0;
        entries.forEach(([key, value]) => {
            // key format: "blockId.paramKey"
            const dotIdx = key.indexOf('.');
            if (dotIdx === -1) {
                console.warn('[OptPanels] best_params key has no dot separator, skipping:', key);
                return;
            }
            const blockId = key.substring(0, dotIdx);
            const paramKey = key.substring(dotIdx + 1);

            if (typeof window.updateBlockParam === 'function') {
                console.log(`[OptPanels] Applying ${blockId}.${paramKey} = ${value}`);
                window.updateBlockParam(blockId, paramKey, value);
                applied++;
            } else {
                console.error('[OptPanels] window.updateBlockParam not available!');
            }
        });

        console.log(`[OptPanels] Applied ${applied}/${entries.length} params`);

        if (applied === 0) return;

        // Disable optimization mode for all applied params so the block shows
        // the fixed optimized value (not a range) — user can see exactly what changed
        const blocks = window.strategyBlocks;
        if (Array.isArray(blocks)) {
            entries.forEach(([key]) => {
                const dotIdx = key.indexOf('.');
                if (dotIdx === -1) return;
                const blockId = key.substring(0, dotIdx);
                const paramKey = key.substring(dotIdx + 1);
                const block = blocks.find(b => b.id === blockId);
                if (block && block.optimizationParams && block.optimizationParams[paramKey]) {
                    block.optimizationParams[paramKey].enabled = false;
                }
            });
        }

        // Re-render blocks so optimization indicators (yellow ⚙) are cleared,
        // then re-render properties panel so fields show the new values
        if (typeof window.renderBlocks === 'function') {
            window.renderBlocks();
        }
        if (typeof window.renderBlockProperties === 'function') {
            window.renderBlockProperties();
        }

        // Refresh the param-ranges list in the Optimization panel — it should now be empty
        // since all optimization flags were just disabled
        if (Array.isArray(blocks)) {
            const freshParams = this.extractOptimizationParamsFromBlocks(blocks);
            this.updateParameterRangesFromBlocks(freshParams);
            this.state.parameterRanges = freshParams;
        }

        this.showNotification(
            `✅ Применены оптимальные параметры (${applied} значений). Режим оптимизации выключен.`,
            'success'
        );

        // Save updated params to the CURRENT strategy (PUT, not POST) then run backtest
        this._saveCurrentAndBacktest();
    }

    /**
     * Save current strategy (with optimized params applied) via PUT to update in-place,
     * then trigger a backtest so user sees the result immediately.
     * Does NOT create a new strategy.
     */
    async _saveCurrentAndBacktest() {
        try {
            // Use existing saveStrategy which does a PUT to current strategy ID
            if (typeof window.saveStrategy === 'function') {
                await window.saveStrategy();
                console.log('[OptPanels] Strategy saved (PUT) with optimized params');
            } else {
                console.warn('[OptPanels] window.saveStrategy not available');
            }

            // Short delay to ensure save completes, then run backtest
            await new Promise(resolve => setTimeout(resolve, 400));

            if (typeof window.runBacktest === 'function') {
                console.log('[OptPanels] Triggering backtest with optimized params...');
                window.runBacktest();
            } else if (document.getElementById('btnBacktest')) {
                document.getElementById('btnBacktest').click();
            } else {
                console.warn('[OptPanels] runBacktest not available');
            }

        } catch (err) {
            console.error('[OptPanels] _saveCurrentAndBacktest failed:', err);
            this.showNotification(`Ошибка сохранения: ${err.message}`, 'error');
        }
    }

    /**
     * Handle optimization SSE event
     */
    handleOptimizationEvent(data) {
        if (data.type === 'progress') {
            this.updateProgress(data.progress || 0);
        } else if (data.type === 'complete') {
            this.setRunningState(false);
            this.state.lastResults = data.results;
            this.saveState();
            this.displayQuickResults(data.results);
            this.showNotification('Optimization completed!', 'success');

            // Show view results button
            const btn = document.getElementById('btnViewFullResults');
            if (btn) btn.style.display = 'block';
        } else if (data.type === 'error') {
            this.setRunningState(false);
            this.showNotification(`Error: ${data.message}`, 'error');
        }
    }

    /**
     * Set running state UI
     * @param {boolean} running - Whether running
     * @param {string} _mode - Run mode (single/optimization) - reserved for future UI differentiation
     */
    setRunningState(running, _mode = 'optimization') {
        this.state.isRunning = running;

        const btn = document.getElementById('btnStartOptimization');
        if (btn) {
            if (running) {
                btn.disabled = true;
                btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Running...';
            } else {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-play-fill"></i> Start Optimization';
            }
        }

        if (running) {
            // Ensure Optimization panel is open and visible
            if (typeof window.openFloatingWindow === 'function') {
                window.openFloatingWindow('floatingWindowOptimization');
            } else {
                const optWin = document.getElementById('floatingWindowOptimization');
                if (optWin) optWin.classList.remove('floating-window-collapsed');
            }
            // Show progress bar immediately (don't wait for first poll)
            const section = document.getElementById('optProgressSection');
            const fillEl = document.getElementById('optProgressFill');
            const pctEl = document.getElementById('optProgressPercent');
            const detailsEl = document.getElementById('optProgressDetails');
            if (section) section.style.display = 'block';
            if (fillEl) fillEl.style.width = '0%';
            if (pctEl) pctEl.textContent = '0%';
            if (detailsEl) detailsEl.textContent = 'Starting... (Numba JIT compile ~30s first run)';
        }
        // When stopping: handleOptimizationComplete will hide progress bar and open Results panel
    }

    /**
     * Start polling for results
     */
    startPolling() {
        if (this.pollInterval) clearInterval(this.pollInterval);

        this.pollInterval = setInterval(() => this.pollStatus(), 2000);
    }

    /**
     * Stop polling
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    /**
     * Poll optimization status
     */
    async pollStatus() {
        if (!this.state.currentJobId) return;

        try {
            const response = await fetch(`/api/v1/optimizations/${this.state.currentJobId}/status`);
            if (!response.ok) throw new Error('Failed to get status');

            const data = await response.json();
            this.updateProgress(data.progress || 0);

            if (data.status === 'completed') {
                this.stopPolling();
                await this.loadResults();
                this.setRunningState(false);
                this.showNotification('Оптимизация завершена!', 'success');
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.setRunningState(false);
                this.showNotification(`Ошибка: ${data.error || 'Unknown'}`, 'error');
            }

        } catch (error) {
            console.error('Poll error:', error);
        }
    }

    /**
     * Update progress UI
     */
    updateProgress(progress) {
        const summary = document.getElementById('resultsQuickSummary');
        if (!summary) return;

        if (progress < 0) {
            // Not running, show placeholder or results
            if (this.state.lastResults) {
                this.displayQuickResults(this.state.lastResults);
            } else {
                summary.innerHTML = `
                    <p class="text-muted text-sm text-center">
                        <i class="bi bi-bar-chart"></i>
                        Run optimization to see results
                    </p>
                `;
            }
            return;
        }

        // Show progress
        summary.innerHTML = `
            <div class="opt-progress-container">
                <div class="opt-progress-header">
                    <span class="opt-progress-label">Optimizing...</span>
                    <span class="opt-progress-value">${Math.round(progress)}%</span>
                </div>
                <div class="opt-progress-bar">
                    <div class="opt-progress-fill" style="width: ${progress}%"></div>
                </div>
            </div>
        `;
    }

    /**
     * Load optimization results
     */
    async loadResults() {
        if (!this.state.currentJobId) return;

        try {
            const response = await fetch(`/api/v1/optimizations/${this.state.currentJobId}/results`);
            if (!response.ok) throw new Error('Failed to load results');

            const results = await response.json();
            this.state.lastResults = results;
            this.saveState();

            this.displayQuickResults(results);

            // Show view full results button
            const btn = document.getElementById('btnViewFullResults');
            if (btn) btn.style.display = 'block';

        } catch (error) {
            console.error('Failed to load results:', error);
        }
    }

    /**
     * Display quick results in sidebar
     */
    displayQuickResults(results) {
        const summary = document.getElementById('resultsQuickSummary');
        if (!summary) return;

        console.log('[OptPanels] displayQuickResults called. results keys:', Object.keys(results || {}));
        console.log('[OptPanels] results.top_results length:', results?.top_results?.length);

        const topResults = results?.top_results || [];

        // Determine the optimization criterion used
        const optimizeMetric = results.optimize_metric
            || this.state.lastOptimizeMetric
            || this.state.primaryMetric
            || 'sharpe_ratio';

        const metricLabelMap = {
            'sharpe_ratio': 'Sharpe',
            'total_return': 'Return %',
            'total_return_pct': 'Return %',
            'max_drawdown': 'Max DD',
            'win_rate': 'Win Rate',
            'profit_factor': 'PF',
            'calmar_ratio': 'Calmar',
            'sortino_ratio': 'Sortino',
            'expectancy': 'Expectancy',
            'net_profit': 'Net Profit',
            'cagr': 'CAGR',
            'recovery_factor': 'Recovery',
            'total_trades': 'Trades'
        };

        // --- Build column list ---
        // 1. Always: rank, optimize_metric
        // 2. Constraint metrics from EvaluationCriteriaPanel (Evaluation Min Requirements)
        // 3. Always: total_trades, Параметры блоков
        const evalCriteria = window.evaluationCriteriaPanel?.getCriteria() || {};
        const constraintMetrics = (evalCriteria.constraints || [])
            .filter(c => c.metric && c.metric !== 'min_trades' && c.metric !== 'total_trades')
            .map(c => c.metric);

        // De-duplicate metric columns
        // Fixed order: optimize_metric first, then constraint metrics,
        // then always-visible metrics, then total_trades
        const alwaysShow = ['max_drawdown', 'sharpe_ratio', 'win_rate'];
        const metricCols = [optimizeMetric];
        constraintMetrics.forEach(m => { if (!metricCols.includes(m)) metricCols.push(m); });
        alwaysShow.forEach(m => { if (!metricCols.includes(m)) metricCols.push(m); });
        if (!metricCols.includes('total_trades')) metricCols.push('total_trades');

        // Collect parameter column keys from top_results (keys starting with block format "blockId.paramKey")
        const paramCols = [];
        if (topResults.length > 0) {
            const row0 = topResults[0];
            Object.keys(row0).forEach(k => {
                // parameter keys have a dot: e.g. "rsi.cross_long_level"
                if (k.includes('.') && !metricCols.includes(k)) {
                    paramCols.push(k);
                }
            });
        }

        // --- Fallback: no top_results — try to show single best result as before ---
        if (topResults.length === 0) {
            let metrics = {};
            if (results?.best?.metrics && Object.keys(results.best.metrics).length > 0) {
                metrics = results.best.metrics;
            } else if (results?.best_metrics && Object.keys(results.best_metrics).length > 0) {
                metrics = results.best_metrics;
            }
            if (!metrics || Object.keys(metrics).length === 0) {
                summary.innerHTML = '<p class="text-muted text-sm text-center"><i class="bi bi-exclamation-circle"></i> No results available</p>';
                return;
            }
            // Push single entry as top_results for unified rendering below
            topResults.push({ ...metrics, ...(results.best_params || {}) });
        }

        const totalTrials = results.total_trials || results.tested_combinations || results.total_combinations || 0;
        const fallbackUsed = results.fallback_used === true || results.all_filtered === true;

        // Check if best result is losing
        const best = topResults[0] || {};
        const bestOptVal = best[optimizeMetric] ?? null;
        const isLosing = bestOptVal !== null && bestOptVal < 0;
        const noPositive = results.no_positive_results === true || (isLosing && fallbackUsed);

        // --- Warning banner ---
        let warningHtml = '';
        if (noPositive) {
            warningHtml = '<div class="opt-results-warning opt-results-warning--error"><i class="bi bi-exclamation-triangle"></i> Прибыльных конфигураций не найдено. Показан наименее убыточный.</div>';
        } else if (isLosing) {
            warningHtml = '<div class="opt-results-warning opt-results-warning--warn"><i class="bi bi-exclamation-triangle"></i> Лучший результат убыточен. Попробуйте другой период.</div>';
        } else if (fallbackUsed) {
            const constraintList = (evalCriteria.constraints || []).map(c => {
                const lbl = metricLabelMap[c.metric] || c.metric;
                return `${lbl} ${c.operator} ${c.value}`;
            }).join(', ');
            const constraintStr = constraintList ? ` (${constraintList})` : '';
            warningHtml = '<div class="opt-results-warning opt-results-warning--warn"><i class="bi bi-exclamation-triangle"></i> ' +
                `Ни одна комбинация не прошла фильтры${constraintStr}. Показаны лучшие без фильтрации. Параметры НЕ применены.</div>`;
        }

        // --- Header info ---
        const optLabel = metricLabelMap[optimizeMetric] || optimizeMetric;
        const constraintBadges = (evalCriteria.constraints || []).map(c => {
            const lbl = metricLabelMap[c.metric] || c.metric;
            const unit = c.metric.includes('drawdown') || c.metric.includes('return') || c.metric.includes('rate') ? '%' : '';
            return `<span class="opt-constraint-badge">${lbl} ${c.operator} ${c.value}${unit}</span>`;
        }).join('');

        // --- Format helpers ---
        const fmt = (val, key) => {
            if (val === null || val === undefined) return '<span style="color:#666">—</span>';
            const n = Number(val);
            if (isNaN(n)) return String(val);
            // Integer-like keys
            if (key === 'total_trades' || key.endsWith('period') || key.endsWith('length')) {
                return n.toFixed(0);
            }
            // Percent keys
            if (key.includes('return') || key.includes('drawdown') || key.includes('win_rate') || key.includes('cagr')) {
                const cls = n >= 0 ? 'opt-cell-pos' : 'opt-cell-neg';
                return `<span class="${cls}">${n >= 0 && key !== 'max_drawdown' ? '+' : ''}${n.toFixed(1)}%</span>`;
            }
            // Net profit
            if (key === 'net_profit') {
                const cls = n >= 0 ? 'opt-cell-pos' : 'opt-cell-neg';
                return `<span class="${cls}">${n >= 0 ? '+' : ''}${n.toFixed(2)}</span>`;
            }
            // Param cols (blockId.paramKey) — show plain value
            if (key.includes('.')) {
                return typeof val === 'number' && !Number.isInteger(val) ? n.toFixed(2) : String(val);
            }
            return n.toFixed(2);
        };

        // Two-line header labels: first line short name, second line unit/detail
        const colLabelTwoLine = key => {
            const twoLineMap = {
                'net_profit': ['Net', 'Profit'],
                'total_trades': ['Trades', ''],
                'max_drawdown': ['Max', 'DD'],
                'sharpe_ratio': ['Sharpe', ''],
                'win_rate': ['Win', 'Rate'],
                'profit_factor': ['Profit', 'Factor'],
                'total_return': ['Return', '%'],
                'total_return_pct': ['Return', '%'],
                'calmar_ratio': ['Calmar', ''],
                'sortino_ratio': ['Sortino', ''],
                'expectancy': ['Exp', ''],
                'cagr': ['CAGR', ''],
                'recovery_factor': ['Recov', '']
            };
            if (key.includes('.')) {
                const [blockId, paramKey] = key.split('.');
                const bLabel = blockId.toUpperCase();
                const pLabel = paramKey.replace(/_percent$/, '%').replace(/_/g, ' ');
                return `<span class="th-line1">${bLabel}</span><span class="th-line2">${pLabel}</span>`;
            }
            const pair = twoLineMap[key];
            if (pair) {
                const [l1, l2] = pair;
                return l2
                    ? `<span class="th-line1">${l1}</span><span class="th-line2">${l2}</span>`
                    : `<span class="th-line1">${l1}</span>`;
            }
            const plain = (metricLabelMap[key] || key.replace(/_/g, ' ')).split(' ');
            return plain.length >= 2
                ? `<span class="th-line1">${plain[0]}</span><span class="th-line2">${plain.slice(1).join(' ')}</span>`
                : `<span class="th-line1">${plain[0]}</span>`;
        };

        // Constraint operator + threshold map for cell highlighting
        const constraintMap = {};
        (evalCriteria.constraints || []).forEach(c => {
            constraintMap[c.metric === 'min_trades' ? 'total_trades' : c.metric] = c;
        });

        const cellClass = (key, val) => {
            const c = constraintMap[key];
            if (!c) return '';
            const n = Number(val);
            if (isNaN(n)) return '';
            const threshold = Number(c.value);
            let passes = true;
            if (c.operator === '<=' && n > threshold) passes = false;
            if (c.operator === '>=' && n < threshold) passes = false;
            if (c.operator === '<' && n >= threshold) passes = false;
            if (c.operator === '>' && n <= threshold) passes = false;
            return passes ? 'opt-cell-pass' : 'opt-cell-fail';
        };

        // --- Build table ---
        const allCols = [...metricCols, ...paramCols];

        const headerCells = allCols.map(k =>
            `<th title="${k}">${colLabelTwoLine(k)}</th>`
        ).join('');

        const rows = topResults.map((row, idx) => {
            const isBest = idx === 0;
            const belowFilter = row._below_min_trades === true;
            const flagHtml = belowFilter
                ? '<span class="opt-flag-below" title="Не прошёл Min Requirements">⚠</span>'
                : (isBest ? '<span class="opt-flag-best" title="Лучший результат">★</span>' : '');

            const cells = allCols.map(k => {
                const rawVal = row[k];
                const extra = cellClass(k, rawVal);
                return `<td class="${extra}">${fmt(rawVal, k)}</td>`;
            }).join('');

            return `<tr class="opt-result-row ${isBest ? 'opt-row-best' : ''} ${belowFilter ? 'opt-row-below' : ''}"
                data-idx="${idx}"
                title="Один клик — открыть копию стратегии&#10;Двойной клик — запустить полный бэктест">
                <td class="opt-rank-cell">${flagHtml}${idx + 1}</td>
                ${cells}
            </tr>`;
        }).join('');

        summary.innerHTML = `
            <div class="opt-results-header">
                <span class="opt-results-title">Results</span>
                <div class="opt-results-meta">
                    ${warningHtml ? `<span class="opt-results-warning-inline">${warningHtml.replace(/<\/?div[^>]*>/g, '')}</span>` : `<span class="opt-metric-badge"><i class="bi bi-bullseye"></i> ${optLabel}</span>${constraintBadges}`}
                </div>
                <span class="opt-results-count">${topResults.length} / ${totalTrials.toLocaleString()} trials</span>
            </div>
            <div class="opt-hint-row">
                <i class="bi bi-hand-index"></i> клик — открыть копию &nbsp;·&nbsp;
                <i class="bi bi-mouse2"></i> двойной — полный бэктест
            </div>
            <div class="opt-results-table-wrap">
                <table class="opt-results-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            ${headerCells}
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;

        // --- Row click handlers ---
        const strategyId = new URLSearchParams(window.location.search).get('id');

        summary.querySelectorAll('.opt-result-row').forEach(tr => {
            let clickTimer = null;

            tr.addEventListener('click', (_e) => {
                const idx = parseInt(tr.dataset.idx, 10);
                const row = topResults[idx];
                if (!row) return;

                // Debounce: wait 250ms to distinguish single vs double click
                if (clickTimer) return; // double-click already handled
                clickTimer = setTimeout(async () => {
                    clickTimer = null;

                    if (!strategyId) {
                        this.showNotification('Стратегия не сохранена — невозможно создать копию', 'warning');
                        return;
                    }

                    // Visual feedback
                    summary.querySelectorAll('.opt-result-row').forEach((r, i) => {
                        r.classList.toggle('opt-row-selected', i === idx);
                    });
                    tr.classList.add('opt-row-loading');

                    try {
                        // Extract param cols (keys with dot) for this row
                        const rowParams = {};
                        Object.keys(row).forEach(k => { if (k.includes('.')) rowParams[k] = row[k]; });

                        // 1. Clone the strategy
                        const rankLabel = idx === 0 ? ' ★' : ` #${idx + 1}`;
                        const cloneRes = await fetch(
                            `/api/v1/strategy-builder/strategies/${strategyId}/clone?new_name=${encodeURIComponent((document.title || 'Strategy') + rankLabel)}`,
                            { method: 'POST' }
                        );
                        if (!cloneRes.ok) throw new Error(`Clone failed: ${cloneRes.status}`);
                        const cloneData = await cloneRes.json();
                        const cloneId = cloneData.id;

                        // 2. Apply optimized params to the clone via PUT
                        if (Object.keys(rowParams).length > 0) {
                            // Fetch current clone blocks, patch params, then save
                            const getRes = await fetch(`/api/v1/strategy-builder/strategies/${cloneId}`);
                            if (getRes.ok) {
                                const cloneStrategy = await getRes.json();
                                const blocks = cloneStrategy.builder_blocks || [];
                                // Apply param values into blocks
                                Object.entries(rowParams).forEach(([key, value]) => {
                                    const dotIdx = key.indexOf('.');
                                    if (dotIdx === -1) return;
                                    const blockId = key.substring(0, dotIdx);
                                    const paramKey = key.substring(dotIdx + 1);
                                    const block = blocks.find(b => b.id === blockId);
                                    if (block) {
                                        if (!block.params) block.params = {};
                                        block.params[paramKey] = value;
                                        // Disable optimization flag for this param
                                        if (block.optimizationParams && block.optimizationParams[paramKey]) {
                                            block.optimizationParams[paramKey].enabled = false;
                                        }
                                    }
                                });
                                // Save updated blocks back to clone
                                await fetch(`/api/v1/strategy-builder/strategies/${cloneId}`, {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ ...cloneStrategy, builder_blocks: blocks })
                                });
                            }
                        }

                        // 3. Open clone in new tab
                        window.open(`/frontend/strategy-builder.html?id=${cloneId}`, '_blank');

                    } catch (err) {
                        this.showNotification(`Ошибка: ${err.message}`, 'error');
                    } finally {
                        tr.classList.remove('opt-row-loading');
                    }
                }, 250);
            });

            tr.addEventListener('dblclick', async (_e) => {
                // Cancel pending single-click
                if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }

                const idx = parseInt(tr.dataset.idx, 10);
                const row = topResults[idx];
                if (!row) return;

                if (!strategyId) {
                    this.showNotification('Стратегия не сохранена', 'warning');
                    return;
                }

                tr.classList.add('opt-row-loading');
                summary.querySelectorAll('.opt-result-row').forEach((r, i) => {
                    r.classList.toggle('opt-row-selected', i === idx);
                });

                try {
                    // Extract param cols for this row
                    const rowParams = {};
                    Object.keys(row).forEach(k => { if (k.includes('.')) rowParams[k] = row[k]; });

                    // Build backtest request with optimized params
                    const props = this.getPropertiesPanelValues();
                    const { startDate: sd, endDate: ed } = this.getBacktestDates();

                    // Merge optimized params into strategy_params
                    const strategyParams = {};
                    Object.entries(rowParams).forEach(([key, value]) => {
                        const paramKey = key.substring(key.indexOf('.') + 1);
                        strategyParams[paramKey] = value;
                    });

                    const payload = {
                        strategy_id: strategyId,
                        symbol: props.symbol,
                        interval: props.interval,
                        start_date: sd,
                        end_date: ed,
                        market_type: props.market_type || 'linear',
                        initial_capital: props.initial_capital,
                        leverage: props.leverage,
                        commission: props.commission,
                        direction: props.direction,
                        strategy_params: strategyParams
                    };

                    const btRes = await fetch(
                        `/api/v1/strategy-builder/strategies/${strategyId}/backtest`,
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        }
                    );
                    if (!btRes.ok) throw new Error(`Backtest failed: ${btRes.status}`);
                    const btData = await btRes.json();
                    const backtestId = btData.backtest_id || btData.id;
                    if (backtestId) {
                        window.open(`/frontend/backtest-results.html?backtest_id=${backtestId}`, '_blank');
                    } else {
                        this.showNotification('Бэктест завершён, но backtest_id не получен', 'warning');
                    }

                } catch (err) {
                    this.showNotification(`Ошибка бэктеста: ${err.message}`, 'error');
                } finally {
                    tr.classList.remove('opt-row-loading');
                }
            });
        });
    }

    /**
     * Save state to localStorage
     */
    saveState() {
        localStorage.setItem('optimizationPanelsState', JSON.stringify(this.state));
    }

    /**
     * Load saved state
     */
    loadSavedState() {
        const saved = localStorage.getItem('optimizationPanelsState');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                this.state = { ...this.state, ...parsed };
                this.applyStateToUI();
            } catch (e) {
                console.warn('Failed to load optimization panels state:', e);
            }
        }
    }

    /**
     * Apply state to UI
     */
    applyStateToUI() {
        // Primary metric
        const primarySelect = document.getElementById('primaryMetric');
        if (primarySelect) primarySelect.value = this.state.primaryMetric;

        // Secondary metrics
        const checkboxMap = {
            'win_rate': 'metricWinRate',
            'max_drawdown': 'metricMaxDD',
            'profit_factor': 'metricProfitFactor',
            'expectancy': 'metricExpectancy',
            'cagr': 'metricCAGR'
        };
        Object.entries(checkboxMap).forEach(([metric, id]) => {
            const checkbox = document.getElementById(id);
            if (checkbox) {
                checkbox.checked = this.state.secondaryMetrics.includes(metric);
            }
        });

        // Method
        const methodSelect = document.getElementById('optMethod');
        if (methodSelect) methodSelect.value = this.state.method;

        // Dates — в блоке Optimization период не редактируется, берётся из «Основные параметры»

        // Limits
        const maxTrials = document.getElementById('optMaxTrials');
        const workers = document.getElementById('optWorkers');
        if (maxTrials) maxTrials.value = this.state.maxTrials;
        if (workers) workers.value = this.state.workers;

        // Results
        if (this.state.lastResults) {
            this.displayQuickResults(this.state.lastResults);
            const btn = document.getElementById('btnViewFullResults');
            if (btn) btn.style.display = 'block';
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (window.showNotification) {
            window.showNotification(message, type);
            return;
        }

        // Simple fallback
        const colors = {
            success: '#3fb950',
            error: '#f85149',
            warning: '#d29922',
            info: '#58a6ff'
        };

        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${colors[type] || colors.info};
            color: white;
            border-radius: 8px;
            font-size: 14px;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.optimizationPanels = new OptimizationPanels();
});

// Export for module usage
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OptimizationPanels;
}
/* eslint-enable no-undef */
