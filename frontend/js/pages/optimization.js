/**
 * 🎯 Optimization Manager Module
 *
 * Handles optimization configuration, execution, and results display
 * for the Strategy Builder Manual Mode.
 *
 * @version 1.0.0
 * @date 2025-01-24
 */

class OptimizationManager {
    constructor() {
        this.config = {
            targetMetric: 'sharpe_ratio',
            constraints: {
                minSharpe: { enabled: false, value: 1.0 },
                maxDrawdown: { enabled: false, value: 20 },
                minWinRate: { enabled: false, value: 50 },
                minProfitFactor: { enabled: false, value: 1.2 }
            },
            sortBy: 'sharpe_ratio',
            sortOrder: 'desc',
            method: 'grid',
            parameters: [],
            advanced: {
                maxTrials: 100,
                timeout: 3600,
                parallelJobs: 4,
                earlyStopping: true,
                minImprovement: 0.01
            }
        };

        this.currentJobId = null;
        this.pollInterval = null;
        this.results = null;

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSavedConfig();
    }

    /**
     * Bind DOM events
     */
    bindEvents() {
        // Metric selector
        document.querySelectorAll('.metric-option input[type="radio"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.config.targetMetric = e.target.value;
                this.updateMetricSelection();
                this.saveConfig();
            });
        });

        // Constraint toggles
        document.querySelectorAll('.constraint-toggle').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const constraintKey = e.target.dataset.constraint;
                if (this.config.constraints[constraintKey]) {
                    this.config.constraints[constraintKey].enabled = e.target.checked;
                    this.saveConfig();
                }
            });
        });

        // Constraint inputs
        document.querySelectorAll('.constraint-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const constraintKey = e.target.dataset.constraint;
                if (this.config.constraints[constraintKey]) {
                    this.config.constraints[constraintKey].value = parseFloat(e.target.value);
                    this.saveConfig();
                }
            });
        });

        // Sort selector
        const sortSelect = document.getElementById('sortByMetric');
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.config.sortBy = e.target.value;
                this.saveConfig();
            });
        }

        // Method selector
        document.querySelectorAll('.method-option').forEach(option => {
            option.addEventListener('click', () => {
                const radio = option.querySelector('input[type="radio"]');
                if (radio) {
                    radio.checked = true;
                    this.config.method = radio.value;
                    this.updateMethodSelection();
                    this.saveConfig();
                }
            });
        });

        // Advanced settings
        document.querySelectorAll('.advanced-settings .setting-row input').forEach(input => {
            input.addEventListener('change', (e) => {
                const settingKey = e.target.dataset.setting;
                if (this.config.advanced[settingKey] !== undefined) {
                    this.config.advanced[settingKey] = parseFloat(e.target.value);
                    this.saveConfig();
                }
            });
        });

        // Parameter range inputs
        document.querySelectorAll('.param-range-item input').forEach(input => {
            input.addEventListener('change', () => this.updateParameterRanges());
        });

        // Collapsible advanced settings
        const advancedHeader = document.querySelector('.advanced-settings h5');
        if (advancedHeader) {
            advancedHeader.addEventListener('click', () => {
                const section = advancedHeader.closest('.advanced-settings');
                section.classList.toggle('collapsed');
            });
        }

        // Run optimization button
        const runBtn = document.getElementById('runOptimizationBtn');
        if (runBtn) {
            runBtn.addEventListener('click', () => this.startOptimization());
        }

        // Cancel button
        const cancelBtn = document.getElementById('cancelOptimizationBtn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.cancelOptimization());
        }

        // Export buttons
        document.querySelectorAll('.btn-export').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const format = e.currentTarget.dataset.format;
                this.exportResults(format);
            });
        });
    }

    /**
     * Update metric selection UI
     */
    updateMetricSelection() {
        document.querySelectorAll('.metric-option').forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            option.classList.toggle('selected', radio.value === this.config.targetMetric);
        });
    }

    /**
     * Update method selection UI
     */
    updateMethodSelection() {
        document.querySelectorAll('.method-option').forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            option.classList.toggle('selected', radio.value === this.config.method);
        });
    }

    /**
     * Update parameter ranges from UI
     */
    updateParameterRanges() {
        const params = [];
        document.querySelectorAll('.param-range-item').forEach(item => {
            const name = item.dataset.param;
            const minInput = item.querySelector('input[data-type="min"]');
            const maxInput = item.querySelector('input[data-type="max"]');
            const stepInput = item.querySelector('input[data-type="step"]');

            if (name && minInput && maxInput && stepInput) {
                params.push({
                    name,
                    min: parseFloat(minInput.value),
                    max: parseFloat(maxInput.value),
                    step: parseFloat(stepInput.value)
                });

                // Update display
                const valuesDisplay = item.querySelector('.param-range-values');
                if (valuesDisplay) {
                    valuesDisplay.textContent = `${minInput.value} → ${maxInput.value} (${stepInput.value})`;
                }
            }
        });
        this.config.parameters = params;
        this.saveConfig();
    }

    /**
     * Save configuration to localStorage
     */
    saveConfig() {
        localStorage.setItem('optimizationConfig', JSON.stringify(this.config));
    }

    /**
     * Load saved configuration from localStorage
     */
    loadSavedConfig() {
        const saved = localStorage.getItem('optimizationConfig');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                this.config = { ...this.config, ...parsed };
                this.applyConfigToUI();
            } catch (e) {
                console.warn('Failed to load optimization config:', e);
            }
        }
    }

    /**
     * Apply current config to UI elements
     */
    applyConfigToUI() {
        // Metric selector
        const metricRadio = document.querySelector(`.metric-option input[value="${this.config.targetMetric}"]`);
        if (metricRadio) {
            metricRadio.checked = true;
            this.updateMetricSelection();
        }

        // Constraints
        Object.entries(this.config.constraints).forEach(([key, constraint]) => {
            const toggle = document.querySelector(`.constraint-toggle[data-constraint="${key}"]`);
            const input = document.querySelector(`.constraint-input[data-constraint="${key}"]`);
            if (toggle) toggle.checked = constraint.enabled;
            if (input) input.value = constraint.value;
        });

        // Sort selector
        const sortSelect = document.getElementById('sortByMetric');
        if (sortSelect) sortSelect.value = this.config.sortBy;

        // Method
        const methodRadio = document.querySelector(`.method-option input[value="${this.config.method}"]`);
        if (methodRadio) {
            methodRadio.checked = true;
            this.updateMethodSelection();
        }

        // Advanced settings
        Object.entries(this.config.advanced).forEach(([key, value]) => {
            const input = document.querySelector(`.setting-row input[data-setting="${key}"]`);
            if (input) input.value = value;
        });
    }

    /**
     * Start optimization job
     */
    async startOptimization() {
        // Validate configuration
        if (!this.validateConfig()) {
            return;
        }

        const strategyConfig = window.strategyBuilder?.exportStrategyConfig();
        if (!strategyConfig) {
            this.showNotification('Сначала создайте стратегию', 'error');
            return;
        }

        try {
            this.setLoadingState(true);
            this.showProgress(true);

            const payload = {
                strategy_config: strategyConfig,
                optimization_config: {
                    target_metric: this.config.targetMetric,
                    method: this.config.method,
                    parameters: this.config.parameters,
                    constraints: this.getActiveConstraints(),
                    max_trials: this.config.advanced.maxTrials,
                    timeout: this.config.advanced.timeout,
                    parallel_jobs: this.config.advanced.parallelJobs
                }
            };

            const response = await fetch('/api/v1/optimizations/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${await response.text()}`);
            }

            const data = await response.json();
            this.currentJobId = data.id;

            this.showNotification('Оптимизация запущена', 'success');
            this.startPolling();

        } catch (error) {
            console.error('Failed to start optimization:', error);
            this.showNotification(`Ошибка запуска: ${error.message}`, 'error');
            this.setLoadingState(false);
            this.showProgress(false);
        }
    }

    /**
     * Validate configuration before starting
     */
    validateConfig() {
        if (this.config.parameters.length === 0) {
            this.showNotification('Добавьте хотя бы один параметр для оптимизации', 'warning');
            return false;
        }

        for (const param of this.config.parameters) {
            if (param.min >= param.max) {
                this.showNotification(`Параметр ${param.name}: min должен быть меньше max`, 'warning');
                return false;
            }
            if (param.step <= 0) {
                this.showNotification(`Параметр ${param.name}: step должен быть положительным`, 'warning');
                return false;
            }
        }

        return true;
    }

    /**
     * Get active constraints
     */
    getActiveConstraints() {
        const active = {};
        Object.entries(this.config.constraints).forEach(([key, constraint]) => {
            if (constraint.enabled) {
                active[key] = constraint.value;
            }
        });
        return active;
    }

    /**
     * Start polling for job status
     */
    startPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }

        this.pollInterval = setInterval(() => this.pollJobStatus(), 2000);
    }

    /**
     * Poll job status
     */
    async pollJobStatus() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/api/v1/optimizations/${this.currentJobId}/status`);
            if (!response.ok) throw new Error('Failed to get status');

            const data = await response.json();
            this.updateProgress(data);

            if (data.status === 'completed') {
                this.stopPolling();
                await this.loadResults();
            } else if (data.status === 'failed') {
                this.stopPolling();
                this.showNotification(`Ошибка оптимизации: ${data.error || 'Unknown error'}`, 'error');
                this.setLoadingState(false);
            }

        } catch (error) {
            console.error('Failed to poll job status:', error);
        }
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
     * Cancel running optimization
     */
    async cancelOptimization() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/api/v1/optimizations/${this.currentJobId}/cancel`, {
                method: 'POST'
            });

            if (response.ok) {
                this.stopPolling();
                this.showNotification('Оптимизация отменена', 'info');
                this.setLoadingState(false);
                this.showProgress(false);
                this.currentJobId = null;
            }

        } catch (error) {
            console.error('Failed to cancel optimization:', error);
            this.showNotification('Не удалось отменить оптимизацию', 'error');
        }
    }

    /**
     * Update progress display
     */
    updateProgress(data) {
        const progressContainer = document.querySelector('.optimization-progress');
        if (!progressContainer) return;

        const percentage = data.progress || 0;
        const completed = data.completed_trials || 0;
        const total = data.total_trials || this.config.advanced.maxTrials;

        const percentageEl = progressContainer.querySelector('.progress-percentage');
        const barFill = progressContainer.querySelector('.progress-bar-fill');
        const statsEl = progressContainer.querySelector('.progress-stats');

        if (percentageEl) percentageEl.textContent = `${percentage.toFixed(1)}%`;
        if (barFill) barFill.style.width = `${percentage}%`;
        if (statsEl) {
            statsEl.innerHTML = `
                <span>Выполнено: ${completed}/${total}</span>
                <span>Лучший: ${data.best_score?.toFixed(4) || '-'}</span>
            `;
        }
    }

    /**
     * Show/hide progress display
     */
    showProgress(show) {
        const progressContainer = document.querySelector('.optimization-progress');
        if (progressContainer) {
            progressContainer.classList.toggle('active', show);
        }
    }

    /**
     * Load optimization results
     */
    async loadResults() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/api/v1/optimizations/${this.currentJobId}/results`);
            if (!response.ok) throw new Error('Failed to load results');

            this.results = await response.json();
            this.displayQuickResults();
            this.showNotification('Оптимизация завершена!', 'success');
            this.setLoadingState(false);

        } catch (error) {
            console.error('Failed to load results:', error);
            this.showNotification('Не удалось загрузить результаты', 'error');
            this.setLoadingState(false);
        }
    }

    /**
     * Display quick results preview
     */
    displayQuickResults() {
        if (!this.results?.best_result) return;

        const best = this.results.best_result;
        const grid = document.querySelector('.quick-results-grid');
        if (!grid) return;

        // Clear previous results
        grid.innerHTML = '';

        // Add result cards
        const metrics = [
            { key: 'sharpe_ratio', label: 'Лучший Sharpe', format: v => v.toFixed(2) },
            { key: 'total_return', label: 'Доходность', format: v => `${(v * 100).toFixed(1)}%`, isPercentage: true },
            { key: 'max_drawdown', label: 'Макс. просадка', format: v => `${(v * 100).toFixed(1)}%`, isNegative: true },
            { key: 'win_rate', label: 'Win Rate', format: v => `${(v * 100).toFixed(1)}%` }
        ];

        metrics.forEach(metric => {
            const value = best.metrics?.[metric.key] || 0;
            const card = document.createElement('div');
            card.className = 'quick-result-card';

            let valueClass = '';
            if (metric.isPercentage && value > 0) valueClass = 'positive';
            if (metric.isPercentage && value < 0) valueClass = 'negative';
            if (metric.isNegative) valueClass = 'negative';

            card.innerHTML = `
                <div class="result-value ${valueClass}">${metric.format(value)}</div>
                <div class="result-label">${metric.label}</div>
            `;
            grid.appendChild(card);
        });

        // Show results section
        const resultsSection = document.getElementById('resultsExportSection');
        if (resultsSection) {
            const content = resultsSection.querySelector('.properties-section-content');
            if (content) content.style.display = 'block';
        }
    }

    /**
     * Export results in specified format
     */
    async exportResults(format) {
        if (!this.results) {
            this.showNotification('Нет результатов для экспорта', 'warning');
            return;
        }

        try {
            let blob, filename;

            switch (format) {
                case 'csv':
                    blob = this.exportToCSV();
                    filename = `optimization_results_${Date.now()}.csv`;
                    break;
                case 'json':
                    blob = new Blob([JSON.stringify(this.results, null, 2)], { type: 'application/json' });
                    filename = `optimization_results_${Date.now()}.json`;
                    break;
                case 'excel':
                    // For Excel, we might need a library or backend endpoint
                    this.showNotification('Excel экспорт будет доступен в следующей версии', 'info');
                    return;
                default:
                    return;
            }

            // Download file
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showNotification(`Результаты экспортированы: ${filename}`, 'success');

        } catch (error) {
            console.error('Export failed:', error);
            this.showNotification('Ошибка экспорта', 'error');
        }
    }

    /**
     * Export results to CSV
     */
    exportToCSV() {
        const trials = this.results.trials || [];
        if (trials.length === 0) return new Blob(['No data'], { type: 'text/csv' });

        // Get all parameter and metric keys
        const paramKeys = Object.keys(trials[0].parameters || {});
        const metricKeys = Object.keys(trials[0].metrics || {});

        // Build header
        const headers = ['trial_id', ...paramKeys, ...metricKeys];

        // Build rows
        const rows = trials.map(trial => {
            const values = [trial.id || ''];
            paramKeys.forEach(key => values.push(trial.parameters?.[key] ?? ''));
            metricKeys.forEach(key => values.push(trial.metrics?.[key] ?? ''));
            return values.join(',');
        });

        const csv = [headers.join(','), ...rows].join('\n');
        return new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    }

    /**
     * Set loading state
     */
    setLoadingState(loading) {
        const runBtn = document.getElementById('runOptimizationBtn');
        const cancelBtn = document.getElementById('cancelOptimizationBtn');

        if (runBtn) {
            runBtn.disabled = loading;
            runBtn.innerHTML = loading
                ? '<i class="fas fa-spinner fa-spin"></i> Выполняется...'
                : '<i class="fas fa-play"></i> Запустить оптимизацию';
        }

        if (cancelBtn) {
            cancelBtn.style.display = loading ? 'inline-flex' : 'none';
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Try to use existing notification system
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }

        // Fallback to simple alert
        console.log(`[${type.toUpperCase()}] ${message}`);

        // Create simple toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-size: 13px;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            background: ${type === 'error' ? '#f85149' : type === 'success' ? '#3fb950' : type === 'warning' ? '#d29922' : '#58a6ff'};
        `;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Add parameter to optimization
     */
    addParameter(name, min, max, step) {
        const exists = this.config.parameters.find(p => p.name === name);
        if (exists) {
            exists.min = min;
            exists.max = max;
            exists.step = step;
        } else {
            this.config.parameters.push({ name, min, max, step });
        }
        this.saveConfig();
        this.renderParameterList();
    }

    /**
     * Remove parameter from optimization
     */
    removeParameter(name) {
        this.config.parameters = this.config.parameters.filter(p => p.name !== name);
        this.saveConfig();
        this.renderParameterList();
    }

    /**
     * Render parameter list in UI
     */
    renderParameterList() {
        const container = document.querySelector('.param-range-list');
        if (!container) return;

        container.innerHTML = this.config.parameters.map(param => `
            <div class="param-range-item" data-param="${param.name}">
                <div class="param-range-header">
                    <span class="param-range-name">${param.name}</span>
                    <span class="param-range-values">${param.min} → ${param.max} (${param.step})</span>
                </div>
                <div class="param-range-inputs">
                    <div class="input-group">
                        <label>Min</label>
                        <input type="number" data-type="min" value="${param.min}" step="any">
                    </div>
                    <div class="input-group">
                        <label>Max</label>
                        <input type="number" data-type="max" value="${param.max}" step="any">
                    </div>
                    <div class="input-group">
                        <label>Step</label>
                        <input type="number" data-type="step" value="${param.step}" step="any">
                    </div>
                </div>
            </div>
        `).join('');

        // Rebind events
        container.querySelectorAll('input').forEach(input => {
            input.addEventListener('change', () => this.updateParameterRanges());
        });
    }

    /**
     * Get current configuration
     */
    getConfig() {
        return { ...this.config };
    }

    /**
     * Set configuration programmatically
     */
    setConfig(config) {
        this.config = { ...this.config, ...config };
        this.applyConfigToUI();
        this.saveConfig();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.optimizationManager = new OptimizationManager();
});

// Export for module usage (Node.js environments)
/* eslint-disable no-undef */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OptimizationManager;
}
/* eslint-enable no-undef */
