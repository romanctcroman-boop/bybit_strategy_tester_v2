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

                // Parameter ranges from config panel
                if (e.detail.parameter_ranges && e.detail.parameter_ranges.length > 0) {
                    this.state.parameterRanges = e.detail.parameter_ranges.map(p => ({
                        name: p.name,
                        min: p.low,
                        max: p.high,
                        step: p.step
                    }));
                    this.state.runMode = 'optimization';
                } else {
                    this.state.parameterRanges = [];
                    this.state.runMode = 'single';
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

        // Map Bybit timeframe codes to API-friendly format
        const tfMap = {
            '1': '1m', '5': '5m', '15': '15m', '30': '30m',
            '60': '1h', '240': '4h', 'D': '1d', 'W': '1w', 'M': '1M'
        };
        const rawTf = timeframeEl?.value || '15';
        const interval = tfMap[rawTf] || rawTf;

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
        const today = new Date().toISOString().slice(0, 10);
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
            const steps = Math.max(1, Math.floor((param.max - param.min) / param.step) + 1);
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

        // Collect ranges for state
        this.state.parameterRanges = params.map(p => ({
            name: p.name,
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

        // Start button - runs single backtest or optimization based on mode
        const btnStartOpt = document.getElementById('btnStartOptimization');
        if (btnStartOpt) {
            btnStartOpt.addEventListener('click', () => this.startRun());
        }

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
            this.showNotification('Save strategy first before running backtest', 'warning');
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
        // Validate
        if (this.state.parameterRanges.length === 0) {
            this.showNotification('No optimization parameters enabled', 'warning');
            return;
        }

        // Get strategy ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        const strategyId = urlParams.get('id');

        if (!strategyId) {
            this.showNotification('Save strategy first before optimization', 'warning');
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
     */
    async startBuilderOptimization(strategyId) {
        try {
            this.setRunningState(true, 'optimization');

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

            // Build parameter_ranges from collected UI state (block_id.param_key format)
            const parameterRanges = this.buildBuilderParameterRanges();

            // Map method name for backend
            const methodMap = {
                'grid_search': 'grid_search',
                'random_search': 'random_search',
                'bayesian': 'bayesian',
                'walk_forward': 'grid_search'
            };

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
                parameter_ranges: parameterRanges.length > 0 ? parameterRanges : null,
                max_iterations: this.state.maxTrials,
                n_trials: this.state.maxTrials,
                sampler_type: 'tpe',
                timeout_seconds: this.state.timeoutSeconds || 3600,
                max_results: 20,
                early_stopping: this.state.earlyStopping ?? false,
                early_stopping_patience: this.state.earlyStoppingPatience ?? 20,
                optimize_metric: evalCriteria.primary_metric || 'sharpe_ratio',
                weights: evalCriteria.weights || null,
                constraints: evalCriteria.constraints || null,
                min_trades: 5
            };

            const endpoint = `/api/v1/strategy-builder/strategies/${strategyId}/optimize`;
            console.log(`[OptPanels] Builder optimization → ${endpoint}`, payload);

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            this.handleOptimizationComplete(data);

        } catch (error) {
            console.error('[OptPanels] Builder optimization failed:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            this.setRunningState(false);
        }
    }

    /**
     * Build parameter ranges array for Builder optimization API.
     * Converts UI state (blockId_paramKey min/max/step) to backend format:
     * [{param_path: "blockId.paramKey", low, high, step, enabled}]
     */
    buildBuilderParameterRanges() {
        const ranges = [];

        document.querySelectorAll('.param-range-item').forEach(item => {
            const blockId = item.dataset.blockId;
            const paramKey = item.dataset.paramKey;
            if (!blockId || !paramKey) return;

            // Check if toggle checkbox exists and is unchecked
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
        this.setRunningState(false);

        // Extract results from sync response - map to displayQuickResults format
        const bestMetrics = data.best_metrics || (data.top_results?.[0] || {});
        const results = {
            top_results: data.top_results || [],
            best_params: data.best_params || {},
            best_score: data.best_score || 0,
            total_combinations: data.total_combinations || 0,
            tested_combinations: data.tested_combinations || data.total_combinations || 0,
            execution_time: data.execution_time_seconds || 0,
            smart_recommendations: data.smart_recommendations || null,
            // Map for displayQuickResults compatibility
            best: {
                params: data.best_params || {},
                metrics: bestMetrics
            },
            total_trials: data.tested_combinations || data.total_combinations || 0
        };

        this.state.lastResults = results;
        this.saveState();
        this.displayQuickResults(results);

        const msg = `Optimization completed! ${results.tested_combinations} combinations in ${results.execution_time.toFixed(1)}s`;
        this.showNotification(msg, 'success');

        // Show view results button
        const btn = document.getElementById('btnViewFullResults');
        if (btn) btn.style.display = 'block';

        console.log('[OptPanels] Optimization complete:', results);
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

        // Show/hide progress
        this.updateProgress(running ? 0 : -1);
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

        // Handle both API formats: results.best.metrics OR results.top_results[0]
        let metrics = {};
        if (results?.best?.metrics) {
            metrics = results.best.metrics;
        } else if (results?.top_results?.[0]) {
            metrics = results.top_results[0];
        } else if (results?.best_metrics) {
            metrics = results.best_metrics;
        }

        if (!metrics || Object.keys(metrics).length === 0) {
            summary.innerHTML = `
                <p class="text-muted text-sm text-center">
                    <i class="bi bi-exclamation-circle"></i>
                    No results available
                </p>
            `;
            return;
        }

        const totalTrials = results.total_trials || results.tested_combinations || results.total_combinations || 0;
        const sharpe = metrics.sharpe_ratio ?? 0;
        const totalReturn = metrics.total_return ?? 0;
        const maxDD = metrics.max_drawdown ?? 0;
        const winRate = metrics.win_rate ?? 0;

        summary.innerHTML = `
            <div class="results-metric-grid">
                <div class="result-metric-card">
                    <span class="result-metric-label">Sharpe</span>
                    <span class="result-metric-value ${sharpe >= 1 ? 'positive' : sharpe < 0 ? 'negative' : ''}">${sharpe.toFixed(2)}</span>
                </div>
                <div class="result-metric-card">
                    <span class="result-metric-label">Return</span>
                    <span class="result-metric-value ${totalReturn >= 0 ? 'positive' : 'negative'}">${totalReturn.toFixed(2)}%</span>
                </div>
                <div class="result-metric-card">
                    <span class="result-metric-label">Max DD</span>
                    <span class="result-metric-value negative">${(maxDD * 100).toFixed(1)}%</span>
                </div>
                <div class="result-metric-card">
                    <span class="result-metric-label">Win Rate</span>
                    <span class="result-metric-value">${winRate.toFixed(1)}%</span>
                </div>
            </div>
            <p class="text-muted text-sm mt-2 text-center">
                <i class="bi bi-trophy"></i> Best of ${totalTrials} trials
            </p>
        `;
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
