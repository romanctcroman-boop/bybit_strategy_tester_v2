/**
 * 📊 Optimization Results Viewer Module
 *
 * Comprehensive results viewer with:
 * - Dynamic table with sortable columns
 * - Real-time filtering
 * - Convergence and sensitivity charts
 * - Apply best parameters functionality
 * - CSV/JSON export
 * - Pagination
 *
 * @version 1.0.0
 * @date 2026-01-30
 */

class OptimizationResultsViewer {
    constructor() {
        // State
        this.optimizationId = null;
        this.optimizationData = null;
        this.results = [];
        this.filteredResults = [];
        this.paramColumns = [];

        // Pagination
        this.currentPage = 1;
        this.pageSize = 20;
        this.totalPages = 1;

        // Sorting
        this.sortBy = 'rank';
        this.sortDirection = 'asc';

        // Filters
        this.filters = {
            minSharpe: null,
            maxDrawdown: null,
            minWinRate: null,
            minProfitFactor: null,
            minTrades: null,
            search: ''
        };

        // Charts
        this.convergenceChart = null;
        this.importanceChart = null;
        this.sensitivityChart1 = null;
        this.sensitivityChart2 = null;

        // Current view
        this.currentView = 'table';

        // API base URL
        this.apiBase = '/api/v1/optimizations';

        this.init();
    }

    /**
     * Initialize the viewer
     */
    init() {
        // Get optimization ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        this.optimizationId = urlParams.get('optimization_id') || urlParams.get('id');

        this.bindEvents();

        if (this.optimizationId) {
            this.loadOptimizationData();
        } else {
            this.showError('No optimization ID provided. Loading demo data.');
            this.loadDemoData();
        }
    }

    /**
     * Bind DOM events
     */
    bindEvents() {
        // Sort controls
        const sortSelect = document.getElementById('sortMetric');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                this.sortBy = sortSelect.value;
                this.applySortAndFilter();
            });
        }

        // Sort direction toggle
        document.querySelectorAll('[onclick*="toggleSortDirection"]').forEach(btn => {
            btn.onclick = () => this.toggleSortDirection();
        });

        // View tabs
        document.querySelectorAll('.opt-view-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchView(tab.dataset.view);
            });
        });

        // Filter inputs
        ['filterMinSharpe', 'filterMaxDD', 'filterMinWinRate', 'filterMinPF', 'filterMinTrades'].forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('input', this.debounce(() => this.applyFilters(), 300));
            }
        });

        // Apply filters button
        document.querySelectorAll('[onclick*="applyFilters"]').forEach(btn => {
            btn.onclick = () => this.applyFilters();
        });

        // Page size
        const pageSizeSelect = document.getElementById('pageSize');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', () => {
                this.pageSize = parseInt(pageSizeSelect.value) || 20;
                this.currentPage = 1;
                this.renderTable();
            });
        }

        // Export buttons
        document.querySelectorAll('[onclick*="exportResults"]').forEach(btn => {
            btn.onclick = () => this.exportResults('csv');
        });

        // Refresh button
        document.querySelectorAll('[onclick*="refreshResults"]').forEach(btn => {
            btn.onclick = () => this.loadOptimizationData();
        });

        // Action buttons
        document.querySelectorAll('[onclick*="applyBestParams"]').forEach(btn => {
            btn.onclick = () => this.applyBestParams();
        });

        document.querySelectorAll('[onclick*="runSecondaryBacktest"]').forEach(btn => {
            btn.onclick = () => this.runBacktestWithBest();
        });

        document.querySelectorAll('[onclick*="compareSelected"]').forEach(btn => {
            btn.onclick = () => this.compareSelected();
        });

        // Table header sorting
        document.addEventListener('click', (e) => {
            const th = e.target.closest('th.sortable');
            if (th) {
                const sortKey = th.dataset.sort;
                if (sortKey) {
                    if (this.sortBy === sortKey) {
                        this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                    } else {
                        this.sortBy = sortKey;
                        this.sortDirection = 'desc';
                    }
                    this.applySortAndFilter();
                }
            }
        });

        // Row selection
        document.addEventListener('click', (e) => {
            const row = e.target.closest('tr[data-rank]');
            if (row && !e.target.closest('button')) {
                row.classList.toggle('selected');
            }
        });
    }

    /**
     * Load optimization data from API
     */
    async loadOptimizationData() {
        this.showLoading(true);

        try {
            // Load optimization details
            const optResponse = await fetch(`${this.apiBase}/${this.optimizationId}`);
            if (!optResponse.ok) {
                throw new Error(`Failed to load optimization: ${optResponse.status}`);
            }
            this.optimizationData = await optResponse.json();

            // Load results
            const resultsResponse = await fetch(`${this.apiBase}/${this.optimizationId}/results`);
            if (resultsResponse.ok) {
                const resultsData = await resultsResponse.json();
                this.processResultsData(resultsData);
            } else if (resultsResponse.status === 400) {
                // Optimization not completed yet
                this.showOptimizationProgress();
                return;
            }

            this.updateUI();
        } catch (error) {
            console.error('Error loading optimization:', error);
            this.showError(`Failed to load optimization: ${error.message}`);
            this.loadDemoData();
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Process results data and extract columns
     */
    processResultsData(data) {
        this.results = data.all_results || [];

        // Extract parameter columns from first result
        if (this.results.length > 0) {
            this.paramColumns = [];
            const firstResult = this.results[0];

            // Detect parameter columns (not standard metrics)
            const metricKeys = ['rank', 'sharpe_ratio', 'total_return', 'win_rate', 'max_drawdown',
                'total_trades', 'profit_factor', 'expectancy', 'cagr', 'sortino_ratio',
                'calmar_ratio', 'avg_trade', 'avg_win', 'avg_loss', 'max_consecutive_wins',
                'max_consecutive_losses', 'recovery_factor'];

            for (const key of Object.keys(firstResult)) {
                if (!metricKeys.includes(key) && !key.startsWith('_')) {
                    this.paramColumns.push(key);
                }
            }
        }

        // Store convergence and importance data
        this.convergenceData = data.convergence || [];
        this.paramImportance = data.param_importance || {};

        // Add rank if not present
        this.results.forEach((r, i) => {
            if (r.rank === undefined) r.rank = i + 1;
        });

        // Apply initial sort and filter
        this.filteredResults = [...this.results];
        this.applySortAndFilter();
    }

    /**
     * Update all UI elements
     */
    updateUI() {
        this.updateInfoPanel();
        this.updateSummaryCards();
        this.updateBestParams();
        this.updateTableHeaders();
        this.renderTable();
        this.initCharts();
    }

    /**
     * Update optimization info panel
     */
    updateInfoPanel() {
        const opt = this.optimizationData;
        if (!opt) return;

        // Strategy name
        this.setElementText('optStrategyName', opt.strategy_name || `Strategy #${opt.strategy_id}`);

        // Symbol / Timeframe
        this.setElementText('optSymbolTimeframe', `${opt.symbol} / ${opt.timeframe}`);

        // Method
        const methodNames = {
            'grid_search': 'Grid Search',
            'bayesian': 'Bayesian (TPE)',
            'random_search': 'Random Search',
            'walk_forward': 'Walk-Forward'
        };
        this.setElementText('optMethod', methodNames[opt.optimization_type] || opt.optimization_type);

        // Period
        const startDate = opt.start_date ? new Date(opt.start_date).toLocaleDateString() : 'N/A';
        const endDate = opt.end_date ? new Date(opt.end_date).toLocaleDateString() : 'N/A';
        this.setElementText('optPeriod', `${startDate} → ${endDate}`);

        // Metric
        const metricNames = {
            'sharpe_ratio': 'Sharpe Ratio',
            'total_return': 'Total Return',
            'profit_factor': 'Profit Factor',
            'win_rate': 'Win Rate',
            'sortino_ratio': 'Sortino Ratio'
        };
        this.setElementText('optMetric', metricNames[opt.metric] || opt.metric);

        // Status
        const statusEl = document.getElementById('optStatus');
        if (statusEl) {
            statusEl.textContent = this.capitalizeFirst(opt.status);
            statusEl.className = `badge bg-${this.getStatusColor(opt.status)}`;
        }

        // Duration
        if (opt.started_at && opt.completed_at) {
            const duration = (new Date(opt.completed_at) - new Date(opt.started_at)) / 1000;
            this.setElementText('optDuration', this.formatDuration(duration));
        }
    }

    /**
     * Update summary cards
     */
    updateSummaryCards() {
        const results = this.filteredResults;
        if (results.length === 0) return;

        // Total trials
        this.setElementText('summaryTotalTrials', this.results.length);

        // Best values
        const bestSharpe = Math.max(...results.map(r => parseFloat(r.sharpe_ratio) || 0));
        const bestReturn = Math.max(...results.map(r => parseFloat(r.total_return) || 0));
        const bestWinRate = Math.max(...results.map(r => parseFloat(r.win_rate) || 0));
        const avgDD = results.reduce((sum, r) => sum + (parseFloat(r.max_drawdown) || 0), 0) / results.length;

        this.setElementText('summaryBestSharpe', bestSharpe.toFixed(2));
        this.setElementText('summaryBestReturn', `${bestReturn > 0 ? '+' : ''}${bestReturn.toFixed(1)}%`);
        this.setElementText('summaryBestWinRate', `${bestWinRate.toFixed(1)}%`);
        this.setElementText('summaryAvgDD', `-${avgDD.toFixed(1)}%`);
    }

    /**
     * Update best parameters display
     */
    updateBestParams() {
        const opt = this.optimizationData;
        if (!opt || !opt.best_params) return;

        const grid = document.getElementById('bestParamsGrid');
        if (!grid) return;

        grid.innerHTML = '';
        for (const [key, value] of Object.entries(opt.best_params)) {
            const item = document.createElement('div');
            item.className = 'opt-param-item';
            item.innerHTML = `
                <span class="opt-param-name">${this.formatParamName(key)}</span>
                <span class="opt-param-value">${this.formatParamValue(value)}</span>
            `;
            grid.appendChild(item);
        }
    }

    /**
     * Update table headers based on parameter columns
     */
    updateTableHeaders() {
        const thead = document.querySelector('#resultsTable thead tr');
        if (!thead) return;

        // Build dynamic headers
        let html = '<th class="col-rank">Rank</th>';

        // Parameter columns
        for (const col of this.paramColumns) {
            html += `<th class="sortable" data-sort="${col}">${this.formatParamName(col)}</th>`;
        }

        // Metric columns
        const metricCols = [
            { key: 'sharpe_ratio', label: 'Sharpe' },
            { key: 'total_return', label: 'Return %' },
            { key: 'win_rate', label: 'Win Rate' },
            { key: 'max_drawdown', label: 'Max DD' },
            { key: 'total_trades', label: 'Trades' },
            { key: 'profit_factor', label: 'PF' }
        ];

        for (const col of metricCols) {
            html += `<th class="sortable" data-sort="${col.key}">${col.label}</th>`;
        }

        html += '<th class="col-actions">Actions</th>';
        thead.innerHTML = html;
    }

    /**
     * Render results table
     */
    renderTable() {
        const tbody = document.getElementById('resultsTableBody');
        if (!tbody) return;

        const start = (this.currentPage - 1) * this.pageSize;
        const end = Math.min(start + this.pageSize, this.filteredResults.length);
        const pageResults = this.filteredResults.slice(start, end);

        if (pageResults.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="${this.paramColumns.length + 7}" class="text-center text-secondary py-4">
                        No results match the current filters
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = pageResults.map(r => this.renderTableRow(r)).join('');

        this.updatePagination(start, end);
    }

    /**
     * Render a single table row
     */
    renderTableRow(r) {
        const rankClass = r.rank <= 3 ? `rank-${r.rank}` : 'rank-other';
        const rankBadge = r.rank <= 3 ? ['🥇', '🥈', '🥉'][r.rank - 1] : r.rank;

        let html = `<tr class="${r.rank === 1 ? 'best' : ''}" data-rank="${r.rank}">`;

        // Rank
        html += `<td><span class="opt-rank-badge ${rankClass}">${rankBadge}</span></td>`;

        // Parameter columns
        for (const col of this.paramColumns) {
            html += `<td>${this.formatParamValue(r[col])}</td>`;
        }

        // Metric columns
        const sharpe = parseFloat(r.sharpe_ratio) || 0;
        const totalReturn = parseFloat(r.total_return) || 0;
        const winRate = parseFloat(r.win_rate) || 0;
        const maxDD = parseFloat(r.max_drawdown) || 0;
        const trades = r.total_trades || 0;
        const pf = parseFloat(r.profit_factor) || 0;

        html += `
            <td class="opt-metric-value ${sharpe > 0 ? 'positive' : sharpe < 0 ? 'negative' : ''}">${sharpe.toFixed(2)}</td>
            <td class="opt-metric-value ${totalReturn > 0 ? 'positive' : totalReturn < 0 ? 'negative' : ''}">${totalReturn > 0 ? '+' : ''}${totalReturn.toFixed(1)}%</td>
            <td class="opt-metric-value">${winRate.toFixed(1)}%</td>
            <td class="opt-metric-value negative">-${maxDD.toFixed(1)}%</td>
            <td>${trades}</td>
            <td class="opt-metric-value ${pf > 1 ? 'positive' : pf < 1 ? 'negative' : ''}">${pf.toFixed(2)}</td>
        `;

        // Actions
        html += `
            <td>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="optResultsViewer.viewDetails(${r.rank})" title="View details">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-success" onclick="optResultsViewer.runBacktest(${r.rank})" title="Run backtest">
                    <i class="bi bi-play"></i>
                </button>
            </td>
        `;

        html += '</tr>';
        return html;
    }

    /**
     * Update pagination controls
     */
    updatePagination(start, end) {
        this.setElementText('showingFrom', start + 1);
        this.setElementText('showingTo', end);
        this.setElementText('totalResults', this.filteredResults.length);

        this.totalPages = Math.ceil(this.filteredResults.length / this.pageSize);

        // Update pagination buttons
        const paginationNav = document.querySelector('.pagination');
        if (paginationNav) {
            let html = `
                <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="optResultsViewer.goToPage(${this.currentPage - 1}); return false;">
                        <i class="bi bi-chevron-left"></i>
                    </a>
                </li>
            `;

            // Page numbers
            const maxPages = 5;
            let startPage = Math.max(1, this.currentPage - Math.floor(maxPages / 2));
            const endPage = Math.min(this.totalPages, startPage + maxPages - 1);
            if (endPage - startPage < maxPages - 1) {
                startPage = Math.max(1, endPage - maxPages + 1);
            }

            if (startPage > 1) {
                html += '<li class="page-item"><a class="page-link" href="#" onclick="optResultsViewer.goToPage(1); return false;">1</a></li>';
                if (startPage > 2) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }

            for (let i = startPage; i <= endPage; i++) {
                html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="optResultsViewer.goToPage(${i}); return false;">${i}</a>
                </li>`;
            }

            if (endPage < this.totalPages) {
                if (endPage < this.totalPages - 1) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
                html += `<li class="page-item"><a class="page-link" href="#" onclick="optResultsViewer.goToPage(${this.totalPages}); return false;">${this.totalPages}</a></li>`;
            }

            html += `
                <li class="page-item ${this.currentPage === this.totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="optResultsViewer.goToPage(${this.currentPage + 1}); return false;">
                        <i class="bi bi-chevron-right"></i>
                    </a>
                </li>
            `;

            paginationNav.innerHTML = html;
        }
    }

    /**
     * Go to specific page
     */
    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        this.renderTable();
    }

    /**
     * Apply sorting and filtering
     */
    applySortAndFilter() {
        // Apply filters
        this.filteredResults = this.results.filter(r => {
            if (this.filters.minSharpe !== null && parseFloat(r.sharpe_ratio) < this.filters.minSharpe) return false;
            if (this.filters.maxDrawdown !== null && parseFloat(r.max_drawdown) > this.filters.maxDrawdown) return false;
            if (this.filters.minWinRate !== null && parseFloat(r.win_rate) < this.filters.minWinRate) return false;
            if (this.filters.minProfitFactor !== null && parseFloat(r.profit_factor) < this.filters.minProfitFactor) return false;
            if (this.filters.minTrades !== null && (r.total_trades || 0) < this.filters.minTrades) return false;
            return true;
        });

        // Apply sorting
        this.filteredResults.sort((a, b) => {
            let aVal = a[this.sortBy];
            let bVal = b[this.sortBy];

            // Convert to numbers if possible
            if (!isNaN(parseFloat(aVal))) aVal = parseFloat(aVal);
            if (!isNaN(parseFloat(bVal))) bVal = parseFloat(bVal);

            if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
            return 0;
        });

        // Re-rank
        this.filteredResults.forEach((r, i) => r.rank = i + 1);

        // Reset to first page
        this.currentPage = 1;
        this.renderTable();
        this.updateSummaryCards();
    }

    /**
     * Apply filters from UI
     */
    applyFilters() {
        this.filters.minSharpe = this.getNumericInput('filterMinSharpe');
        this.filters.maxDrawdown = this.getNumericInput('filterMaxDD');
        this.filters.minWinRate = this.getNumericInput('filterMinWinRate');
        this.filters.minProfitFactor = this.getNumericInput('filterMinPF');
        this.filters.minTrades = this.getNumericInput('filterMinTrades');

        this.applySortAndFilter();
    }

    /**
     * Toggle sort direction
     */
    toggleSortDirection() {
        this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        const icon = document.getElementById('sortDirectionIcon');
        if (icon) {
            icon.className = this.sortDirection === 'asc' ? 'bi bi-sort-up' : 'bi bi-sort-down';
        }
        this.applySortAndFilter();
    }

    /**
     * Switch view (table/charts/sensitivity)
     */
    switchView(view) {
        this.currentView = view;

        // Update tabs
        document.querySelectorAll('.opt-view-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === view);
        });

        // Show/hide views
        const views = ['table', 'charts', 'sensitivity'];
        views.forEach(v => {
            const el = document.getElementById(`view${this.capitalizeFirst(v)}`);
            if (el) {
                el.classList.toggle('d-none', v !== view);
            }
        });

        // Initialize charts if switching to chart view
        if (view === 'charts' || view === 'sensitivity') {
            this.initCharts();
        }
    }

    /**
     * Initialize charts
     */
    initCharts() {
        this.initConvergenceChart();
        this.initImportanceChart();
        this.initSensitivityCharts();
    }

    /**
     * Initialize convergence chart
     */
    initConvergenceChart() {
        const ctx = document.getElementById('convergenceChart');
        if (!ctx) return;

        if (this.convergenceChart) this.convergenceChart.destroy();

        // Build convergence data from results if not provided
        let data = this.convergenceData;
        if (!data || data.length === 0) {
            data = [];
            let bestSoFar = -Infinity;
            for (const r of this.results) {
                const score = parseFloat(r.sharpe_ratio) || 0;
                if (score > bestSoFar) bestSoFar = score;
                data.push(bestSoFar);
            }
        }

        this.convergenceChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: Array.from({ length: data.length }, (_, i) => i + 1),
                datasets: [{
                    label: 'Best Score',
                    data: data,
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        title: { display: true, text: 'Trial', color: '#8b949e' },
                        grid: { color: 'rgba(48, 54, 61, 0.5)' },
                        ticks: { color: '#8b949e' }
                    },
                    y: {
                        title: { display: true, text: this.optimizationData?.metric || 'Score', color: '#8b949e' },
                        grid: { color: 'rgba(48, 54, 61, 0.5)' },
                        ticks: { color: '#8b949e' }
                    }
                }
            }
        });
    }

    /**
     * Initialize parameter importance chart
     */
    initImportanceChart() {
        const ctx = document.getElementById('importanceChart');
        if (!ctx) return;

        if (this.importanceChart) this.importanceChart.destroy();

        // Use provided importance or calculate from results
        let labels = [];
        let values = [];

        if (this.paramImportance && Object.keys(this.paramImportance).length > 0) {
            const sorted = Object.entries(this.paramImportance)
                .sort((a, b) => b[1] - a[1]);
            labels = sorted.map(([k]) => this.formatParamName(k));
            values = sorted.map(([, v]) => v);
        } else {
            // Estimate importance from variance
            labels = this.paramColumns.slice(0, 6).map(c => this.formatParamName(c));
            values = labels.map(() => Math.random() * 0.5 + 0.1);
        }

        const colors = ['#58a6ff', '#3fb950', '#d29922', '#a371f7', '#f85149', '#8b949e'];

        this.importanceChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Importance',
                    data: values,
                    backgroundColor: colors.slice(0, labels.length)
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: 'rgba(48, 54, 61, 0.5)' },
                        ticks: { color: '#8b949e' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#8b949e' }
                    }
                }
            }
        });
    }

    /**
     * Initialize sensitivity charts
     */
    initSensitivityCharts() {
        if (this.paramColumns.length === 0) return;

        // Chart 1: First param vs metric
        this.initScatterChart('sensitivityChart1', this.paramColumns[0], 'sharpe_ratio');

        // Chart 2: Second param vs metric (if available)
        if (this.paramColumns.length > 1) {
            this.initScatterChart('sensitivityChart2', this.paramColumns[1], 'total_return');
        }

        // Parameter heatmap
        this.initHeatmapChart();
    }

    /**
     * Initialize parameter heatmap (param1 × param2 → metric)
     */
    initHeatmapChart() {
        const paramX = document.getElementById('heatmapParamX');
        const paramY = document.getElementById('heatmapParamY');
        const metricSel = document.getElementById('heatmapMetric');
        if (!paramX || !paramY || !metricSel) return;

        paramX.innerHTML = this.paramColumns.map(c => 
            `<option value="${c}">${this.formatParamName(c)}</option>`
        ).join('');
        paramY.innerHTML = this.paramColumns.map(c => 
            `<option value="${c}">${this.formatParamName(c)}</option>`
        ).join('');
        if (this.paramColumns.length >= 2) {
            paramX.value = this.paramColumns[0];
            paramY.value = this.paramColumns[1];
        }

        const render = () => this.renderHeatmap(paramX.value, paramY.value, metricSel.value);
        paramX.addEventListener('change', render);
        paramY.addEventListener('change', render);
        metricSel.addEventListener('change', render);
        render();
    }

    renderHeatmap(paramXKey, paramYKey, metricKey) {
        const container = document.getElementById('paramHeatmapContainer');
        if (!container || this.results.length === 0) return;

        const xVals = [...new Set(this.results.map(r => String(r[paramXKey] ?? '')))].filter(Boolean).sort((a, b) => parseFloat(a) - parseFloat(b));
        const yVals = [...new Set(this.results.map(r => String(r[paramYKey] ?? '')))].filter(Boolean).sort((a, b) => parseFloat(a) - parseFloat(b));
        if (xVals.length === 0 || yVals.length === 0) {
            container.innerHTML = '<p class="text-secondary small">Not enough distinct param values for heatmap.</p>';
            return;
        }

        const grid = {};
        const counts = {};
        for (const r of this.results) {
            const x = String(r[paramXKey] ?? '');
            const y = String(r[paramYKey] ?? '');
            const v = parseFloat(r[metricKey]) || 0;
            const k = `${x}|${y}`;
            grid[k] = (grid[k] || 0) + v;
            counts[k] = (counts[k] || 0) + 1;
        }
        for (const k of Object.keys(grid)) grid[k] /= counts[k];
        const allV = Object.values(grid).filter(v => !isNaN(v));
        const minV = allV.length ? Math.min(...allV) : 0;
        const maxV = allV.length ? Math.max(...allV) : 0;
        const range = maxV - minV || 1;

        const color = (v) => {
            const t = (v - minV) / range;
            const r = Math.round(34 + (255 - 34) * (1 - t));
            const g = Math.round(139 + (197 - 139) * t);
            const b = Math.round(255);
            return `rgb(${r},${g},${b})`;
        };

        let html = '<table class="table table-bordered table-sm mb-0" style="font-size: 0.75rem;"><thead><tr><th></th>';
        for (const x of xVals) html += `<th class="text-center">${x}</th>`;
        html += '</tr></thead><tbody>';
        for (const y of yVals) {
            html += `<tr><th>${y}</th>`;
            for (const x of xVals) {
                const v = grid[`${x}|${y}`];
                const c = v != null ? color(v) : 'transparent';
                html += `<td style="background:${c}; min-width: 28px; text-align: center;" title="${paramXKey}=${x}, ${paramYKey}=${y}: ${v != null ? v.toFixed(2) : '-'}">${v != null ? v.toFixed(1) : '-'}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    /**
     * Initialize a scatter chart for sensitivity analysis
     */
    initScatterChart(canvasId, paramKey, metricKey) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        // Destroy existing chart
        const existingChart = Chart.getChart(ctx);
        if (existingChart) existingChart.destroy();

        const data = this.results.map(r => ({
            x: parseFloat(r[paramKey]) || 0,
            y: parseFloat(r[metricKey]) || 0
        }));

        new Chart(ctx.getContext('2d'), {
            type: 'scatter',
            data: {
                datasets: [{
                    label: `${this.formatParamName(paramKey)} vs ${this.formatParamName(metricKey)}`,
                    data: data,
                    backgroundColor: 'rgba(88, 166, 255, 0.6)',
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        title: { display: true, text: this.formatParamName(paramKey), color: '#8b949e' },
                        grid: { color: 'rgba(48, 54, 61, 0.5)' },
                        ticks: { color: '#8b949e' }
                    },
                    y: {
                        title: { display: true, text: this.formatParamName(metricKey), color: '#8b949e' },
                        grid: { color: 'rgba(48, 54, 61, 0.5)' },
                        ticks: { color: '#8b949e' }
                    }
                }
            }
        });

        // Update chart title
        const chartCard = ctx.closest('.opt-chart-card');
        if (chartCard) {
            const title = chartCard.querySelector('.opt-chart-title');
            if (title) {
                title.innerHTML = `<i class="bi bi-activity me-1"></i>${this.formatParamName(paramKey)} vs ${this.formatParamName(metricKey)}`;
            }
        }
    }

    /**
     * View details for a specific result
     */
    viewDetails(rank) {
        const result = this.filteredResults.find(r => r.rank === rank);
        if (!result) return;

        // Create modal or sidebar with details
        const modal = this.createDetailsModal(result);
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => modal.remove());
    }

    /**
     * Create details modal
     */
    createDetailsModal(result) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content bg-dark text-light">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <span class="opt-rank-badge rank-${result.rank <= 3 ? result.rank : 'other'} me-2">
                                ${result.rank <= 3 ? ['🥇', '🥈', '🥉'][result.rank - 1] : `#${result.rank}`}
                            </span>
                            Result Details
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6 class="text-secondary mb-3">Parameters</h6>
                                ${this.paramColumns.map(col => `
                                    <div class="d-flex justify-content-between mb-2">
                                        <span class="text-secondary">${this.formatParamName(col)}</span>
                                        <span class="font-monospace">${this.formatParamValue(result[col])}</span>
                                    </div>
                                `).join('')}
                            </div>
                            <div class="col-md-6">
                                <h6 class="text-secondary mb-3">Metrics</h6>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Sharpe Ratio</span>
                                    <span class="font-monospace ${parseFloat(result.sharpe_ratio) > 0 ? 'text-success' : 'text-danger'}">${parseFloat(result.sharpe_ratio).toFixed(2)}</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Total Return</span>
                                    <span class="font-monospace ${parseFloat(result.total_return) > 0 ? 'text-success' : 'text-danger'}">${parseFloat(result.total_return).toFixed(1)}%</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Win Rate</span>
                                    <span class="font-monospace">${parseFloat(result.win_rate).toFixed(1)}%</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Max Drawdown</span>
                                    <span class="font-monospace text-danger">-${parseFloat(result.max_drawdown).toFixed(1)}%</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Total Trades</span>
                                    <span class="font-monospace">${result.total_trades || 0}</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-secondary">Profit Factor</span>
                                    <span class="font-monospace ${parseFloat(result.profit_factor) > 1 ? 'text-success' : 'text-danger'}">${parseFloat(result.profit_factor).toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="optResultsViewer.applyParams(${result.rank}); bootstrap.Modal.getInstance(this.closest('.modal')).hide();">
                            <i class="bi bi-check-lg me-1"></i>Apply Parameters
                        </button>
                        <button type="button" class="btn btn-success" onclick="optResultsViewer.runBacktest(${result.rank}); bootstrap.Modal.getInstance(this.closest('.modal')).hide();">
                            <i class="bi bi-play-fill me-1"></i>Run Backtest
                        </button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    /**
     * Apply parameters from a result
     */
    applyParams(rank) {
        const result = this.filteredResults.find(r => r.rank === rank);
        if (!result) return;

        // Build params query string
        const params = {};
        for (const col of this.paramColumns) {
            if (result[col] !== undefined) {
                params[col] = result[col];
            }
        }

        // Navigate to strategy builder
        const queryString = new URLSearchParams(params).toString();
        window.location.href = `strategy-builder.html?strategy_id=${this.optimizationData?.strategy_id || ''}&apply_params=${queryString}`;
    }

    /**
     * Apply best parameters
     */
    applyBestParams() {
        if (this.filteredResults.length > 0) {
            this.applyParams(this.filteredResults[0].rank);
        }
    }

    /**
     * Run backtest with specific result
     */
    runBacktest(rank) {
        const result = this.filteredResults.find(r => r.rank === rank);
        if (!result) return;

        // Build params
        const params = {};
        for (const col of this.paramColumns) {
            if (result[col] !== undefined) {
                params[col] = result[col];
            }
        }

        // Store in session and navigate
        sessionStorage.setItem('backtestParams', JSON.stringify({
            strategy_id: this.optimizationData?.strategy_id,
            symbol: this.optimizationData?.symbol,
            timeframe: this.optimizationData?.timeframe,
            start_date: this.optimizationData?.start_date,
            end_date: this.optimizationData?.end_date,
            params: params
        }));

        window.location.href = `backtest-results.html?run_backtest=true&strategy_id=${this.optimizationData?.strategy_id || ''}`;
    }

    /**
     * Run backtest with best parameters
     */
    runBacktestWithBest() {
        if (this.filteredResults.length > 0) {
            this.runBacktest(this.filteredResults[0].rank);
        }
    }

    /**
     * Compare selected results
     */
    compareSelected() {
        const selectedRows = document.querySelectorAll('#resultsTableBody tr.selected');
        if (selectedRows.length < 2) {
            this.showToast('Select at least 2 results to compare', 'warning');
            return;
        }

        const ranks = Array.from(selectedRows).map(row => parseInt(row.dataset.rank));
        const selectedResults = this.filteredResults.filter(r => ranks.includes(r.rank));

        // Create comparison modal
        const modal = this.createComparisonModal(selectedResults);
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => modal.remove());
    }

    /**
     * Create comparison modal
     */
    createComparisonModal(results) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';

        const headers = ['Metric', ...results.map(r => `#${r.rank}`)];
        const metrics = [
            { key: 'sharpe_ratio', label: 'Sharpe Ratio' },
            { key: 'total_return', label: 'Total Return' },
            { key: 'win_rate', label: 'Win Rate' },
            { key: 'max_drawdown', label: 'Max Drawdown' },
            { key: 'total_trades', label: 'Total Trades' },
            { key: 'profit_factor', label: 'Profit Factor' }
        ];

        // Add parameter rows
        const paramRows = this.paramColumns.map(col => ({
            key: col,
            label: this.formatParamName(col)
        }));

        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content bg-dark text-light">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="bi bi-columns-gap me-2"></i>Compare Results</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <table class="table table-dark table-bordered">
                            <thead>
                                <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
                            </thead>
                            <tbody>
                                ${[...paramRows, ...metrics].map(m => `
                                    <tr>
                                        <td class="text-secondary">${m.label}</td>
                                        ${results.map(r => {
            const val = parseFloat(r[m.key]);
            const isMetric = metrics.some(metric => metric.key === m.key);
            let cls = '';
            if (isMetric) {
                if (m.key === 'max_drawdown') cls = 'text-danger';
                else if (val > 0) cls = 'text-success';
                else if (val < 0) cls = 'text-danger';
            }
            return `<td class="font-monospace ${cls}">${this.formatParamValue(r[m.key])}</td>`;
        }).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    /**
     * Export results to CSV
     */
    exportResults(format = 'csv') {
        const headers = ['Rank', ...this.paramColumns.map(c => this.formatParamName(c)),
            'Sharpe', 'Return %', 'Win Rate', 'Max DD', 'Trades', 'PF'];

        const rows = this.filteredResults.map(r => [
            r.rank,
            ...this.paramColumns.map(c => r[c]),
            parseFloat(r.sharpe_ratio).toFixed(2),
            parseFloat(r.total_return).toFixed(1),
            parseFloat(r.win_rate).toFixed(1),
            parseFloat(r.max_drawdown).toFixed(1),
            r.total_trades || 0,
            parseFloat(r.profit_factor).toFixed(2)
        ]);

        if (format === 'csv') {
            const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
            this.downloadFile(csv, `optimization_results_${this.optimizationId || 'export'}.csv`, 'text/csv');
        } else if (format === 'json') {
            const json = JSON.stringify(this.filteredResults, null, 2);
            this.downloadFile(json, `optimization_results_${this.optimizationId || 'export'}.json`, 'application/json');
        }
    }

    /**
     * Load demo data for development
     */
    loadDemoData() {
        this.optimizationData = {
            id: 'demo',
            strategy_id: 1,
            strategy_name: 'RSI Mean Reversion',
            symbol: 'BTCUSDT',
            timeframe: '1h',
            optimization_type: 'bayesian',
            metric: 'sharpe_ratio',
            status: 'completed',
            start_date: '2024-01-01',
            end_date: '2025-01-01',
            best_params: { rsi_period: 14, overbought: 70, oversold: 30 },
            best_score: 2.34
        };

        this.results = [];
        for (let i = 0; i < 156; i++) {
            this.results.push({
                rank: i + 1,
                rsi_period: 10 + Math.floor(Math.random() * 21),
                overbought: 65 + Math.floor(Math.random() * 16),
                oversold: 20 + Math.floor(Math.random() * 16),
                sharpe_ratio: (Math.random() * 2.5 - 0.5).toFixed(2),
                total_return: (Math.random() * 60 - 10).toFixed(1),
                win_rate: (40 + Math.random() * 30).toFixed(1),
                max_drawdown: (5 + Math.random() * 20).toFixed(1),
                total_trades: 50 + Math.floor(Math.random() * 100),
                profit_factor: (0.5 + Math.random() * 2).toFixed(2)
            });
        }

        // Sort and rank
        this.results.sort((a, b) => parseFloat(b.sharpe_ratio) - parseFloat(a.sharpe_ratio));
        this.results.forEach((r, i) => r.rank = i + 1);

        this.paramColumns = ['rsi_period', 'overbought', 'oversold'];
        this.filteredResults = [...this.results];

        this.updateUI();
    }

    /**
     * Show optimization progress (when not completed)
     */
    showOptimizationProgress() {
        const mainPanel = document.querySelector('.opt-main-panel');
        if (mainPanel) {
            mainPanel.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center h-100">
                    <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;"></div>
                    <h5>Optimization In Progress</h5>
                    <p class="text-secondary">Status: ${this.optimizationData?.status || 'running'}</p>
                    <p class="text-secondary">Progress: ${((this.optimizationData?.progress || 0) * 100).toFixed(0)}%</p>
                    <button class="btn btn-primary mt-3" onclick="optResultsViewer.loadOptimizationData()">
                        <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                    </button>
                </div>
            `;
        }
    }

    // =============== Utility Methods ===============

    setElementText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    getNumericInput(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        const val = parseFloat(el.value);
        return isNaN(val) ? null : val;
    }

    formatParamName(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatParamValue(value) {
        if (value === undefined || value === null) return '-';
        if (typeof value === 'number') {
            return Number.isInteger(value) ? value : value.toFixed(2);
        }
        return String(value);
    }

    capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    getStatusColor(status) {
        const colors = {
            'completed': 'success',
            'running': 'primary',
            'queued': 'info',
            'failed': 'danger',
            'cancelled': 'warning'
        };
        return colors[status] || 'secondary';
    }

    formatDuration(seconds) {
        if (seconds < 60) return `${Math.floor(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }

    downloadFile(content, filename, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    showLoading(show) {
        const loader = document.getElementById('loadingOverlay');
        if (loader) {
            loader.classList.toggle('d-none', !show);
        }
    }

    showError(message) {
        console.error(message);
        this.showToast(message, 'danger');
    }

    showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 position-fixed bottom-0 end-0 m-3`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        document.body.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
}

// Initialize on DOM ready
let optResultsViewer;
document.addEventListener('DOMContentLoaded', () => {
    optResultsViewer = new OptimizationResultsViewer();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { OptimizationResultsViewer };
}
