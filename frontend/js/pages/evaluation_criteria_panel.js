/**
 * 📊 Evaluation Criteria Panel Module
 *
 * Complete UI component for configuring optimization evaluation criteria:
 * - Primary metric selection (what to optimize)
 * - Secondary metrics (what to display)
 * - Hard constraints (filtering rules)
 * - Multi-level sorting (result ranking)
 * - Metric weights for composite scoring
 *
 * Integrates with strategy_builder.js and optimization_panels.js
 *
 * @version 2.0.0
 * @date 2025-01-30
 */

class EvaluationCriteriaPanel {
    constructor(containerId = 'evaluationCriteriaSection') {
        this.containerId = containerId;
        this.container = null;

        // All available metrics with categories
        this.availableMetrics = {
            performance: {
                label: 'Performance',
                metrics: {
                    net_profit: { label: 'Net Profit', unit: '$', direction: 'maximize' },
                    total_return: { label: 'Total Return', unit: '%', direction: 'maximize' },
                    cagr: { label: 'CAGR', unit: '%', direction: 'maximize' },
                    sharpe_ratio: { label: 'Sharpe Ratio', unit: '', direction: 'maximize' },
                    sortino_ratio: { label: 'Sortino Ratio', unit: '', direction: 'maximize' },
                    calmar_ratio: { label: 'Calmar Ratio', unit: '', direction: 'maximize' }
                }
            },
            risk: {
                label: 'Risk',
                metrics: {
                    max_drawdown: { label: 'Max Drawdown', unit: '%', direction: 'minimize' },
                    avg_drawdown: { label: 'Avg Drawdown', unit: '%', direction: 'minimize' },
                    volatility: { label: 'Volatility', unit: '%', direction: 'minimize' },
                    var_95: { label: 'VaR 95%', unit: '%', direction: 'minimize' },
                    risk_adjusted_return: { label: 'Risk-Adj Return', unit: '', direction: 'maximize' }
                }
            },
            trade_quality: {
                label: 'Trade Quality',
                metrics: {
                    win_rate: { label: 'Win Rate', unit: '%', direction: 'maximize' },
                    profit_factor: { label: 'Profit Factor', unit: '', direction: 'maximize' },
                    avg_win: { label: 'Avg Win', unit: '%', direction: 'maximize' },
                    avg_loss: { label: 'Avg Loss', unit: '%', direction: 'minimize' },
                    expectancy: { label: 'Expectancy', unit: '$', direction: 'maximize' },
                    payoff_ratio: { label: 'Payoff Ratio', unit: '', direction: 'maximize' }
                }
            },
            activity: {
                label: 'Activity',
                metrics: {
                    total_trades: { label: 'Total Trades', unit: '', direction: 'neutral' },
                    trades_per_month: { label: 'Trades/Month', unit: '', direction: 'neutral' },
                    avg_trade_duration: { label: 'Avg Duration', unit: 'bars', direction: 'neutral' },
                    avg_bars_in_trade: { label: 'Avg Bars', unit: '', direction: 'neutral' }
                }
            }
        };

        // State
        this.state = {
            // Ranking mode: 'single' | 'balanced' | 'weighted'
            rankingMode: 'single',
            primaryMetric: 'sharpe_ratio',
            // balanced mode: metrics to rank by average rank
            balancedMetrics: ['net_profit', 'max_drawdown'],
            // weighted mode: same as secondary + weights
            secondaryMetrics: ['win_rate', 'max_drawdown', 'profit_factor'],
            constraints: [
                { id: crypto.randomUUID(), metric: 'max_drawdown', operator: '<=', value: 15, unit: '%', enabled: true },
                { id: crypto.randomUUID(), metric: 'total_trades', operator: '>=', value: 50, unit: '', enabled: true }
            ],
            sortOrder: [
                { id: crypto.randomUUID(), metric: 'sharpe_ratio', direction: 'desc' }
            ],
            weights: {
                sharpe_ratio: 1.0,
                win_rate: 0.8,
                max_drawdown: 0.9,
                profit_factor: 0.7
            },
            // Legacy alias kept for loadSavedState compat
            useCompositeScore: false
        };

        this.init();
    }

    init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.warn(`[EvaluationCriteriaPanel] Container #${this.containerId} not found`);
            return;
        }

        this.render();
        this.loadSavedState();
        this.bindEvents();
    }

    /**
     * Get all metrics as flat object
     */
    getAllMetrics() {
        const all = {};
        Object.values(this.availableMetrics).forEach(category => {
            Object.assign(all, category.metrics);
        });
        return all;
    }

    /**
     * Get metric info by key
     */
    getMetricInfo(key) {
        return this.getAllMetrics()[key] || { label: key, unit: '', direction: 'maximize' };
    }

    /**
     * Render the panel
     */
    render() {
        const mode = this.state.rankingMode || 'single';

        this.container.innerHTML = `
            <!-- Quick Presets -->
            <div class="property-row property-row-vertical eval-presets-section">
                <label class="property-label">
                    <i class="bi bi-lightning text-warning"></i> Quick Presets
                </label>
                <div class="criteria-presets-compact">
                    <button class="criteria-preset-btn-sm" data-preset="conservative" title="Low risk, moderate returns">
                        🛡️ Conservative
                    </button>
                    <button class="criteria-preset-btn-sm" data-preset="aggressive" title="High returns, higher risk">
                        🚀 Aggressive
                    </button>
                    <button class="criteria-preset-btn-sm" data-preset="balanced" title="Good risk-adjusted returns">
                        ⚖️ Balanced
                    </button>
                    <button class="criteria-preset-btn-sm" data-preset="frequency" title="Many trades, consistent">
                        📊 Frequency
                    </button>
                </div>
            </div>

            <!-- Ranking Mode Selector -->
            <div class="property-row property-row-vertical eval-ranking-mode-section">
                <label class="property-label">
                    <i class="bi bi-trophy text-primary"></i> How to rank results?
                </label>
                <div class="eval-mode-buttons">
                    <button class="eval-mode-btn ${mode === 'single' ? 'active' : ''}"
                            data-mode="single"
                            title="Pick one metric and maximize it">
                        <i class="bi bi-bullseye"></i>
                        <span class="mode-btn-title">Single metric</span>
                        <span class="mode-btn-desc">Maximize one goal</span>
                    </button>
                    <button class="eval-mode-btn ${mode === 'balanced' ? 'active' : ''}"
                            data-mode="balanced"
                            title="Best average rank across multiple metrics — recommended for profit + risk">
                        <i class="bi bi-bar-chart-steps"></i>
                        <span class="mode-btn-title">Balanced rank</span>
                        <span class="mode-btn-desc">Best on multiple metrics</span>
                    </button>
                    <button class="eval-mode-btn ${mode === 'weighted' ? 'active' : ''}"
                            data-mode="weighted"
                            title="Combine metrics into a single score using weights">
                        <i class="bi bi-sliders2"></i>
                        <span class="mode-btn-title">Weighted score</span>
                        <span class="mode-btn-desc">Custom importance</span>
                    </button>
                </div>
            </div>

            <!-- SINGLE MODE: just primary metric -->
            <div class="eval-mode-content ${mode === 'single' ? '' : 'd-none'}" id="evalModeSingle">
                <div class="property-row property-row-vertical">
                    <label for="evalPrimaryMetric" class="property-label">
                        Optimize for
                    </label>
                    <select class="property-select property-select-full" id="evalPrimaryMetric">
                        ${this.renderMetricOptions(this.state.primaryMetric)}
                    </select>
                    <p class="eval-mode-hint">All combinations are sorted by this metric. Use <em>Minimum Requirements</em> below to exclude bad results.</p>
                </div>
            </div>

            <!-- BALANCED MODE: rank by average rank across selected metrics -->
            <div class="eval-mode-content ${mode === 'balanced' ? '' : 'd-none'}" id="evalModeBalanced">
                <div class="property-row property-row-vertical">
                    <label class="property-label">
                        Rank by all of these
                    </label>
                    <p class="eval-mode-hint">Each result gets a rank per metric, then an average rank is computed. Best average rank wins — scales ($, %) don't matter.</p>
                    <div class="criteria-metrics-grid" id="evalBalancedMetrics">
                        ${this.renderBalancedMetrics()}
                    </div>
                </div>
            </div>

            <!-- WEIGHTED MODE: composite score with sliders -->
            <div class="eval-mode-content ${mode === 'weighted' ? '' : 'd-none'}" id="evalModeWeighted">
                <div class="property-row property-row-vertical">
                    <label for="evalPrimaryMetricW" class="property-label">
                        Primary metric
                    </label>
                    <select class="property-select property-select-full" id="evalPrimaryMetricW">
                        ${this.renderMetricOptions(this.state.primaryMetric)}
                    </select>
                </div>
                <div class="property-row property-row-vertical">
                    <label class="property-label">
                        Also include in score
                    </label>
                    <p class="eval-mode-hint">⚠️ Works best when metrics use similar units (e.g. ratios). Avoid mixing $ and %.</p>
                    <div class="criteria-metrics-grid" id="evalSecondaryMetrics">
                        ${this.renderSecondaryMetrics()}
                    </div>
                </div>
                <div class="property-row property-row-vertical">
                    <label class="property-label">
                        <i class="bi bi-sliders2"></i> Weights
                    </label>
                    <div class="metric-weights-list" id="evalWeightsList">
                        ${this.renderWeights()}
                    </div>
                </div>
            </div>

            <!-- Minimum Requirements (Constraints) -->
            <div class="property-row property-row-vertical eval-constraints-section">
                <div class="eval-section-header">
                    <label class="property-label">
                        <i class="bi bi-funnel"></i> Minimum Requirements
                        <span class="constraint-count">(${this.state.constraints.filter(c => c.enabled).length} active)</span>
                    </label>
                    <button class="btn-add-sm" id="btnAddEvalConstraint" title="Add requirement">
                        <i class="bi bi-plus"></i>
                    </button>
                </div>
                <p class="eval-mode-hint" style="margin-bottom:6px">Results that don't meet these are excluded before ranking.</p>
                <div class="constraints-list-compact" id="evalConstraintsList">
                    ${this.renderConstraints()}
                </div>
            </div>

            <!-- Advanced: Sort Order (collapsed by default) -->
            <div class="property-row property-row-vertical eval-sort-section eval-collapsible-section collapsed" id="evalAdvancedSection">
                <div class="eval-section-header" id="evalAdvancedToggle">
                    <label class="property-label" style="cursor:pointer">
                        <i class="bi bi-sort-down"></i> Advanced: Tiebreaker Order
                        <span class="sort-count">(${this.state.sortOrder.length} levels)</span>
                    </label>
                    <button class="eval-collapse-btn" type="button">
                        <i class="bi bi-chevron-down"></i>
                    </button>
                </div>
                <div class="eval-collapsible-content" id="evalSortOrderWrapper">
                    <p class="eval-mode-hint">When results have equal scores, sort by these in order.</p>
                    <div class="sort-order-list-compact" id="evalSortOrderList">
                        ${this.renderSortOrder()}
                    </div>
                    <button class="btn-add-sm" id="btnAddEvalSort" style="margin-top:6px" title="Add tiebreaker">
                        <i class="bi bi-plus"></i> Add level
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render grouped metric options for select
     */
    renderMetricOptions(selected) {
        let html = '';
        for (const [_categoryKey, category] of Object.entries(this.availableMetrics)) {
            html += `<optgroup label="${category.label}">`;
            for (const [metricKey, metric] of Object.entries(category.metrics)) {
                const isSelected = metricKey === selected ? 'selected' : '';
                const dirIcon = metric.direction === 'maximize' ? '↑' : metric.direction === 'minimize' ? '↓' : '↔';
                html += `<option value="${metricKey}" ${isSelected}>${metric.label} ${dirIcon}</option>`;
            }
            html += '</optgroup>';
        }
        return html;
    }

    /**
     * Render balanced-mode metric checkboxes (uses balancedMetrics state)
     */
    renderBalancedMetrics() {
        let html = '';
        for (const [_categoryKey, category] of Object.entries(this.availableMetrics)) {
            html += `<div class="metric-category">
                <div class="metric-category-label">${category.label}</div>
                <div class="metric-category-items">`;
            for (const [metricKey, metric] of Object.entries(category.metrics)) {
                const isChecked = this.state.balancedMetrics.includes(metricKey) ? 'checked' : '';
                const dirLabel = metric.direction === 'maximize' ? '↑' : metric.direction === 'minimize' ? '↓' : '';
                html += `
                    <label class="criteria-checkbox-item" title="${metric.label} (${metric.direction})">
                        <input type="checkbox" data-metric="${metricKey}" ${isChecked}>
                        <span>${metric.label} <small class="metric-dir-hint">${dirLabel}</small></span>
                    </label>
                `;
            }
            html += '</div></div>';
        }
        return html;
    }

    /**
     * Render secondary metrics grid with categories (weighted mode)
     */
    renderSecondaryMetrics() {
        let html = '';
        for (const [_categoryKey, category] of Object.entries(this.availableMetrics)) {
            html += `<div class="metric-category">
                <div class="metric-category-label">${category.label}</div>
                <div class="metric-category-items">`;
            for (const [metricKey, metric] of Object.entries(category.metrics)) {
                const isChecked = this.state.secondaryMetrics.includes(metricKey) ? 'checked' : '';
                html += `
                    <label class="criteria-checkbox-item" title="${metric.label}">
                        <input type="checkbox" data-metric="${metricKey}" ${isChecked}>
                        <span>${metric.label}</span>
                    </label>
                `;
            }
            html += '</div></div>';
        }
        return html;
    }

    /**
     * Render metric weights sliders
     */
    renderWeights() {
        const metrics = [this.state.primaryMetric, ...this.state.secondaryMetrics];
        const uniqueMetrics = [...new Set(metrics)];

        return uniqueMetrics.map(metricKey => {
            const metric = this.getMetricInfo(metricKey);
            const weight = this.state.weights[metricKey] ?? 1.0;
            return `
                <div class="metric-weight-item" data-metric="${metricKey}">
                    <span class="weight-label">${metric.label}</span>
                    <input type="range" class="weight-slider" min="0" max="1" step="0.1" value="${weight}">
                    <span class="weight-value">${weight.toFixed(1)}</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Render constraints list
     */
    renderConstraints() {
        if (this.state.constraints.length === 0) {
            return '<p class="text-muted text-sm">No constraints defined</p>';
        }

        return this.state.constraints.map(constraint => {
            const metric = this.getMetricInfo(constraint.metric);
            return `
                <div class="constraint-item ${constraint.enabled ? '' : 'disabled'}" data-id="${constraint.id}">
                    <label class="constraint-toggle" title="Enable/disable">
                        <input type="checkbox" class="constraint-enabled" ${constraint.enabled ? 'checked' : ''}>
                    </label>
                    <select class="constraint-metric" title="Metric">
                        ${this.renderConstraintMetricOptions(constraint.metric)}
                    </select>
                    <select class="constraint-operator" title="Operator">
                        <option value="<=" ${constraint.operator === '<=' ? 'selected' : ''}>≤</option>
                        <option value=">=" ${constraint.operator === '>=' ? 'selected' : ''}>≥</option>
                        <option value="<" ${constraint.operator === '<' ? 'selected' : ''}>&lt;</option>
                        <option value=">" ${constraint.operator === '>' ? 'selected' : ''}>&gt;</option>
                        <option value="==" ${constraint.operator === '==' ? 'selected' : ''}>=</option>
                        <option value="!=" ${constraint.operator === '!=' ? 'selected' : ''}>≠</option>
                    </select>
                    <input type="number" class="constraint-value" value="${constraint.value}" step="any" title="Value">
                    <span class="constraint-unit">${metric.unit}</span>
                    <button class="constraint-remove" title="Remove">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            `;
        }).join('');
    }

    /**
     * Render constraint metric options
     */
    renderConstraintMetricOptions(selected) {
        let html = '';
        for (const [_categoryKey, category] of Object.entries(this.availableMetrics)) {
            for (const [metricKey, metric] of Object.entries(category.metrics)) {
                const isSelected = metricKey === selected ? 'selected' : '';
                html += `<option value="${metricKey}" ${isSelected}>${metric.label}</option>`;
            }
        }
        return html;
    }

    /**
     * Render sort order list
     */
    renderSortOrder() {
        if (this.state.sortOrder.length === 0) {
            return '<p class="text-muted text-sm">Default sorting by primary metric</p>';
        }

        return this.state.sortOrder.map((sort, index) => {
            const _metric = this.getMetricInfo(sort.metric);
            return `
                <div class="sort-order-item" data-id="${sort.id}" draggable="true">
                    <span class="sort-handle" title="Drag to reorder">
                        <i class="bi bi-grip-vertical"></i>
                    </span>
                    <span class="sort-level">${index + 1}.</span>
                    <select class="sort-metric" title="Metric">
                        ${this.renderConstraintMetricOptions(sort.metric)}
                    </select>
                    <button class="sort-direction ${sort.direction}" title="Toggle direction" data-direction="${sort.direction}">
                        <i class="bi bi-arrow-${sort.direction === 'desc' ? 'down' : 'up'}"></i>
                    </button>
                    <button class="sort-remove" title="Remove">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            `;
        }).join('');
    }

    /**
     * Bind all events
     */
    bindEvents() {
        // --- Ranking mode buttons ---
        this.container.querySelectorAll('.eval-mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                this.state.rankingMode = mode;
                // Legacy compat field
                this.state.useCompositeScore = (mode === 'weighted');
                // Switch active button
                this.container.querySelectorAll('.eval-mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                // Show/hide mode content panels
                this.container.querySelectorAll('.eval-mode-content').forEach(el => el.classList.add('d-none'));
                const modeMap = { single: 'evalModeSingle', balanced: 'evalModeBalanced', weighted: 'evalModeWeighted' };
                this.container.querySelector(`#${modeMap[mode]}`)?.classList.remove('d-none');
                this.saveState();
                this.emitChange();
            });
        });

        // --- Primary metric (single mode) ---
        this.container.querySelector('#evalPrimaryMetric')?.addEventListener('change', (e) => {
            this.state.primaryMetric = e.target.value;
            this.updateWeightsUI();
            this.saveState();
            this.emitChange();
        });

        // --- Primary metric (weighted mode) ---
        this.container.querySelector('#evalPrimaryMetricW')?.addEventListener('change', (e) => {
            this.state.primaryMetric = e.target.value;
            this.updateWeightsUI();
            this.saveState();
            this.emitChange();
        });

        // --- Balanced metrics checkboxes ---
        this.container.querySelector('#evalBalancedMetrics')?.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                const metric = e.target.dataset.metric;
                if (e.target.checked) {
                    if (!this.state.balancedMetrics.includes(metric)) {
                        this.state.balancedMetrics.push(metric);
                    }
                } else {
                    this.state.balancedMetrics = this.state.balancedMetrics.filter(m => m !== metric);
                }
                this.saveState();
                this.emitChange();
            }
        });

        // --- Secondary metrics (weighted mode) ---
        this.container.querySelector('#evalSecondaryMetrics')?.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                const metric = e.target.dataset.metric;
                if (e.target.checked) {
                    if (!this.state.secondaryMetrics.includes(metric)) {
                        this.state.secondaryMetrics.push(metric);
                    }
                } else {
                    this.state.secondaryMetrics = this.state.secondaryMetrics.filter(m => m !== metric);
                }
                this.updateWeightsUI();
                this.saveState();
                this.emitChange();
            }
        });

        // --- Weights (weighted mode) ---
        this.container.querySelector('#evalWeightsList')?.addEventListener('input', (e) => {
            if (e.target.classList.contains('weight-slider')) {
                const item = e.target.closest('.metric-weight-item');
                const metric = item?.dataset.metric;
                const value = parseFloat(e.target.value);
                if (metric) {
                    this.state.weights[metric] = value;
                    item.querySelector('.weight-value').textContent = value.toFixed(1);
                    this.saveState();
                    this.emitChange();
                }
            }
        });

        // --- Add constraint ---
        this.container.querySelector('#btnAddEvalConstraint')?.addEventListener('click', () => {
            this.addConstraint();
        });

        // --- Constraint events (delegated) ---
        this.container.querySelector('#evalConstraintsList')?.addEventListener('click', (e) => {
            const item = e.target.closest('.constraint-item');
            if (!item) return;
            if (e.target.closest('.constraint-remove')) {
                this.removeConstraint(item.dataset.id);
            }
        });

        this.container.querySelector('#evalConstraintsList')?.addEventListener('change', (e) => {
            const item = e.target.closest('.constraint-item');
            if (!item) return;
            this.updateConstraintFromUI(item);
            this.saveState();
            this.emitChange();
        });

        // --- Add sort level ---
        this.container.querySelector('#btnAddEvalSort')?.addEventListener('click', () => {
            this.addSortLevel();
        });

        // --- Sort events (delegated) ---
        this.container.querySelector('#evalSortOrderList')?.addEventListener('click', (e) => {
            const item = e.target.closest('.sort-order-item');
            if (!item) return;
            if (e.target.closest('.sort-remove')) {
                this.removeSortLevel(item.dataset.id);
            } else if (e.target.closest('.sort-direction')) {
                this.toggleSortDirection(item.dataset.id);
            }
        });

        this.container.querySelector('#evalSortOrderList')?.addEventListener('change', (e) => {
            const item = e.target.closest('.sort-order-item');
            if (!item) return;
            this.updateSortFromUI(item);
            this.saveState();
            this.emitChange();
        });

        // --- Presets ---
        this.container.querySelectorAll('.criteria-preset-btn, .criteria-preset-btn-sm').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.applyPreset(e.target.closest('.criteria-preset-btn, .criteria-preset-btn-sm').dataset.preset);
            });
        });

        // --- Advanced section toggle ---
        this.container.querySelector('#evalAdvancedToggle')?.addEventListener('click', () => {
            this.container.querySelector('#evalAdvancedSection')?.classList.toggle('collapsed');
        });

        // --- Drag & drop for sort order ---
        this.setupSortDragDrop();
    }

    /**
     * Add a new constraint
     */
    addConstraint() {
        this.state.constraints.push({
            id: crypto.randomUUID(),
            metric: 'max_drawdown',
            operator: '<=',
            value: 10,
            unit: '%',
            enabled: true
        });
        this.renderConstraintsList();
        this.updateConstraintCount();
        this.saveState();
        this.emitChange();
    }

    /**
     * Remove a constraint
     */
    removeConstraint(id) {
        this.state.constraints = this.state.constraints.filter(c => c.id !== id);
        this.renderConstraintsList();
        this.updateConstraintCount();
        this.saveState();
        this.emitChange();
    }

    /**
     * Update constraint from UI
     */
    updateConstraintFromUI(item) {
        const id = item.dataset.id;
        const constraint = this.state.constraints.find(c => c.id === id);
        if (!constraint) return;

        constraint.enabled = item.querySelector('.constraint-enabled')?.checked ?? true;
        constraint.metric = item.querySelector('.constraint-metric')?.value || constraint.metric;
        constraint.operator = item.querySelector('.constraint-operator')?.value || constraint.operator;
        constraint.value = parseFloat(item.querySelector('.constraint-value')?.value) || 0;

        // Update unit based on metric
        const metricInfo = this.getMetricInfo(constraint.metric);
        constraint.unit = metricInfo.unit;
        item.querySelector('.constraint-unit').textContent = metricInfo.unit;

        item.classList.toggle('disabled', !constraint.enabled);
    }

    /**
     * Add a sort level
     */
    addSortLevel() {
        // Find a metric not already in sort order
        const usedMetrics = this.state.sortOrder.map(s => s.metric);
        const allMetricKeys = Object.keys(this.getAllMetrics());
        const availableMetric = allMetricKeys.find(m => !usedMetrics.includes(m)) || 'total_return';

        this.state.sortOrder.push({
            id: crypto.randomUUID(),
            metric: availableMetric,
            direction: 'desc'
        });
        this.renderSortOrderList();
        this.updateSortCount();
        this.saveState();
        this.emitChange();
    }

    /**
     * Remove a sort level
     */
    removeSortLevel(id) {
        this.state.sortOrder = this.state.sortOrder.filter(s => s.id !== id);
        this.renderSortOrderList();
        this.updateSortCount();
        this.saveState();
        this.emitChange();
    }

    /**
     * Toggle sort direction
     */
    toggleSortDirection(id) {
        const sort = this.state.sortOrder.find(s => s.id === id);
        if (!sort) return;

        sort.direction = sort.direction === 'desc' ? 'asc' : 'desc';
        this.renderSortOrderList();
        this.saveState();
        this.emitChange();
    }

    /**
     * Update sort from UI
     */
    updateSortFromUI(item) {
        const id = item.dataset.id;
        const sort = this.state.sortOrder.find(s => s.id === id);
        if (!sort) return;

        sort.metric = item.querySelector('.sort-metric')?.value || sort.metric;
    }

    /**
     * Setup drag & drop for sort order
     */
    setupSortDragDrop() {
        const list = this.container.querySelector('#evalSortOrderList');
        if (!list) return;

        let draggedItem = null;

        list.addEventListener('dragstart', (e) => {
            draggedItem = e.target.closest('.sort-order-item');
            if (draggedItem) {
                draggedItem.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            }
        });

        list.addEventListener('dragend', () => {
            if (draggedItem) {
                draggedItem.classList.remove('dragging');
                draggedItem = null;
            }
        });

        list.addEventListener('dragover', (e) => {
            e.preventDefault();
            const afterElement = this.getDragAfterElement(list, e.clientY);
            if (draggedItem) {
                if (afterElement == null) {
                    list.appendChild(draggedItem);
                } else {
                    list.insertBefore(draggedItem, afterElement);
                }
            }
        });

        list.addEventListener('drop', () => {
            // Update state based on new order
            const newOrder = [];
            list.querySelectorAll('.sort-order-item').forEach(item => {
                const id = item.dataset.id;
                const sort = this.state.sortOrder.find(s => s.id === id);
                if (sort) newOrder.push(sort);
            });
            this.state.sortOrder = newOrder;
            this.renderSortOrderList(); // Re-render to update level numbers
            this.saveState();
            this.emitChange();
        });
    }

    getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.sort-order-item:not(.dragging)')];
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset, element: child };
            }
            return closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    /**
     * Apply a preset configuration
     */
    applyPreset(presetName) {
        const presets = {
            conservative: {
                rankingMode: 'balanced',
                primaryMetric: 'sortino_ratio',
                balancedMetrics: ['sortino_ratio', 'max_drawdown', 'volatility'],
                secondaryMetrics: ['max_drawdown', 'win_rate', 'profit_factor', 'volatility'],
                constraints: [
                    { metric: 'max_drawdown', operator: '<=', value: 10, enabled: true },
                    { metric: 'volatility', operator: '<=', value: 20, enabled: true },
                    { metric: 'total_trades', operator: '>=', value: 30, enabled: true }
                ],
                sortOrder: [
                    { metric: 'sortino_ratio', direction: 'desc' },
                    { metric: 'max_drawdown', direction: 'asc' }
                ]
            },
            aggressive: {
                rankingMode: 'single',
                primaryMetric: 'total_return',
                balancedMetrics: ['total_return', 'sharpe_ratio'],
                secondaryMetrics: ['sharpe_ratio', 'max_drawdown', 'cagr', 'win_rate'],
                constraints: [
                    { metric: 'max_drawdown', operator: '<=', value: 25, enabled: true },
                    { metric: 'total_trades', operator: '>=', value: 20, enabled: true }
                ],
                sortOrder: [
                    { metric: 'total_return', direction: 'desc' },
                    { metric: 'sharpe_ratio', direction: 'desc' }
                ]
            },
            balanced: {
                rankingMode: 'balanced',
                primaryMetric: 'sharpe_ratio',
                balancedMetrics: ['net_profit', 'sharpe_ratio', 'max_drawdown', 'win_rate'],
                secondaryMetrics: ['win_rate', 'max_drawdown', 'profit_factor', 'total_return'],
                constraints: [
                    { metric: 'max_drawdown', operator: '<=', value: 15, enabled: true },
                    { metric: 'total_trades', operator: '>=', value: 50, enabled: true },
                    { metric: 'win_rate', operator: '>=', value: 40, enabled: true }
                ],
                sortOrder: [
                    { metric: 'sharpe_ratio', direction: 'desc' },
                    { metric: 'profit_factor', direction: 'desc' }
                ]
            },
            frequency: {
                rankingMode: 'single',
                primaryMetric: 'profit_factor',
                balancedMetrics: ['profit_factor', 'total_trades', 'win_rate'],
                secondaryMetrics: ['total_trades', 'win_rate', 'expectancy', 'trades_per_month'],
                constraints: [
                    { metric: 'total_trades', operator: '>=', value: 100, enabled: true },
                    { metric: 'win_rate', operator: '>=', value: 50, enabled: true },
                    { metric: 'max_drawdown', operator: '<=', value: 20, enabled: true }
                ],
                sortOrder: [
                    { metric: 'profit_factor', direction: 'desc' },
                    { metric: 'total_trades', direction: 'desc' }
                ]
            }
        };

        const preset = presets[presetName];
        if (!preset) return;

        // Apply preset with IDs
        this.state.rankingMode = preset.rankingMode;
        this.state.useCompositeScore = (preset.rankingMode === 'weighted');
        this.state.primaryMetric = preset.primaryMetric;
        this.state.balancedMetrics = [...preset.balancedMetrics];
        this.state.secondaryMetrics = [...preset.secondaryMetrics];
        this.state.constraints = preset.constraints.map(c => ({
            id: crypto.randomUUID(),
            ...c,
            unit: this.getMetricInfo(c.metric).unit
        }));
        this.state.sortOrder = preset.sortOrder.map(s => ({
            id: crypto.randomUUID(),
            ...s
        }));

        // Re-render
        this.render();
        this.bindEvents();
        this.saveState();
        this.emitChange();

        this.showNotification(`Applied "${presetName}" preset`, 'success');
    }

    /**
     * Re-render just the constraints list
     */
    renderConstraintsList() {
        const list = this.container.querySelector('#evalConstraintsList');
        if (list) list.innerHTML = this.renderConstraints();
    }

    /**
     * Re-render just the sort order list
     */
    renderSortOrderList() {
        const list = this.container.querySelector('#evalSortOrderList');
        if (list) {
            list.innerHTML = this.renderSortOrder();
            this.setupSortDragDrop();
        }
    }

    /**
     * Update counts in labels
     */
    updateMetricCount() {
        const count = this.container.querySelector('.metric-count');
        if (count) count.textContent = `(${this.state.secondaryMetrics.length} selected)`;
    }

    updateConstraintCount() {
        const count = this.container.querySelector('.constraint-count');
        if (count) count.textContent = `(${this.state.constraints.filter(c => c.enabled).length} active)`;
    }

    updateSortCount() {
        const count = this.container.querySelector('.sort-count');
        if (count) count.textContent = `(${this.state.sortOrder.length} levels)`;
    }

    updateWeightsUI() {
        const list = this.container.querySelector('#evalWeightsList');
        if (list) list.innerHTML = this.renderWeights();
    }

    /**
     * Save state to localStorage
     */
    saveState() {
        localStorage.setItem('evaluationCriteriaState', JSON.stringify(this.state));
    }

    /**
     * Load saved state — migrates legacy useCompositeScore to rankingMode
     */
    loadSavedState() {
        const saved = localStorage.getItem('evaluationCriteriaState');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                // Migration: old state had useCompositeScore but no rankingMode
                if (!parsed.rankingMode) {
                    parsed.rankingMode = parsed.useCompositeScore ? 'weighted' : 'single';
                }
                if (!parsed.balancedMetrics) {
                    parsed.balancedMetrics = ['net_profit', 'max_drawdown'];
                }
                this.state = { ...this.state, ...parsed };
                this.render();
                this.bindEvents();
            } catch (e) {
                console.warn('[EvaluationCriteriaPanel] Failed to load saved state:', e);
            }
        }
    }

    /**
     * Get current criteria for API.
     * Maps rankingMode → use_composite + secondary_metrics correctly.
     */
    getCriteria() {
        const mode = this.state.rankingMode || 'single';

        // Build mode-specific fields
        let useComposite = false;
        let secondaryMetrics = [];
        let weights = null;

        if (mode === 'single') {
            // Pure single-metric: no secondary, no composite
            useComposite = false;
            secondaryMetrics = [];
            weights = null;
        } else if (mode === 'balanced') {
            // rank_by_multi_criteria on backend: send secondary_metrics, use_composite=false
            useComposite = false;
            secondaryMetrics = this.state.balancedMetrics.filter(m => m !== this.state.primaryMetric);
            weights = null;
        } else if (mode === 'weighted') {
            // Composite weighted score
            useComposite = true;
            secondaryMetrics = this.state.secondaryMetrics;
            weights = this.state.weights;
        }

        return {
            primary_metric: this.state.primaryMetric,
            secondary_metrics: secondaryMetrics,
            ranking_mode: mode,
            constraints: this.state.constraints.filter(c => c.enabled).map(c => ({
                metric: c.metric,
                operator: c.operator,
                value: c.value
            })),
            sort_order: this.state.sortOrder.map(s => ({
                metric: s.metric,
                direction: s.direction
            })),
            use_composite: useComposite,
            weights: weights
        };
    }

    /**
     * Emit change event
     */
    emitChange() {
        const event = new CustomEvent('evaluationCriteriaChanged', {
            detail: this.getCriteria()
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
    if (document.getElementById('evaluationCriteriaSection')) {
        window.evaluationCriteriaPanel = new EvaluationCriteriaPanel();
    }
});

// Export for module usage (CommonJS compatibility)
// eslint-disable-next-line no-undef
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EvaluationCriteriaPanel; // eslint-disable-line no-undef
}
