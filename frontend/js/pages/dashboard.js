/**
 * 📄 Dashboard Page JavaScript
 *
 * Page-specific scripts for dashboard.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { formatNumber, formatDate } from '../utils.js';

// Configuration
const API_BASE = '/api/v1';
let currentPeriod = '24h';

// Period selector — scoped to toolbar only (avoid portfolio period buttons)
document.querySelectorAll('.dashboard-toolbar .period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.dashboard-toolbar .period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentPeriod = btn.dataset.period;
        refreshDashboard();
    });
});

// Metric selector for top performers
document.getElementById('performerMetric').addEventListener('change', (e) => {
    loadTopPerformers(e.target.value);
});

// Main refresh function
async function refreshDashboard() {
    const indicator = document.getElementById('refreshIndicator');
    indicator.classList.add('loading');

    try {
        await Promise.all([
            loadMetricsSummary(),
            loadTopPerformers(),
            loadSystemHealth()
        ]);

        document.getElementById('lastUpdate').textContent =
            `Last updated: ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        console.error('Dashboard refresh failed:', error);
        showToast('Dashboard refresh failed. Check your connection.', 'error');
    } finally {
        indicator.classList.remove('loading');
    }
}

// Load metrics summary
async function loadMetricsSummary() {
    try {
        const url = getMetricsUrl();
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load metrics');

        const data = await response.json();

        // Update stats cards
        document.getElementById('totalBacktests').textContent = data.backtests.total;
        document.getElementById('runningBacktests').textContent = data.backtests.running;
        document.getElementById('completedBacktests').textContent = data.backtests.completed;
        document.getElementById('failedBacktests').textContent = `${data.backtests.failed} failed`;

        const successRate = (data.backtests.success_rate * 100).toFixed(1);
        document.getElementById('successRate').textContent = `${successRate}%`;

        document.getElementById('activeStrategies').textContent = data.strategies.active;
        document.getElementById('totalStrategies').textContent = data.strategies.total;

        document.getElementById('totalOptimizations').textContent = data.optimizations.total;
        document.getElementById('runningOptimizations').textContent = data.optimizations.running;

        document.getElementById('totalTrades').textContent = formatNumber(data.performance.total_trades_analyzed);
        document.getElementById('avgDuration').textContent = `${data.performance.avg_backtest_duration_sec.toFixed(1)}s`;

    } catch (error) {
        console.error('Metrics summary error:', error);
        showToast('Failed to load metrics summary', 'error');
    }
}

// Load top performers
async function loadTopPerformers(metric = null) {
    metric = metric || document.getElementById('performerMetric').value;

    try {
        const response = await fetch(`${API_BASE}/dashboard/metrics/top-performers?limit=10&metric=${metric}`);
        if (!response.ok) throw new Error('Failed to load top performers');

        const data = await response.json();
        const tbody = document.getElementById('performersBody');

        if (data.top_performers.length === 0) {
            tbody.innerHTML = `
                        <tr>
                            <td colspan="6" style="text-align: center; color: var(--text-muted);">
                                No completed backtests yet
                            </td>
                        </tr>`;
            return;
        }

        tbody.innerHTML = data.top_performers.map((item, index) => {
            // win_rate may come as 0-1 fraction or 0-100 percentage
            const wr = item.win_rate <= 1 ? (item.win_rate * 100) : item.win_rate;
            return `
                    <tr>
                        <td class="rank">${index + 1}</td>
                        <td class="strategy-name">${escapeHtml(item.strategy_name)}</td>
                        <td>${item.symbol}</td>
                        <td class="metric-value">${item.sharpe_ratio.toFixed(2)}</td>
                        <td class="${item.total_return >= 0 ? 'positive' : 'negative'}">${item.total_return.toFixed(1)}%</td>
                        <td>${wr.toFixed(1)}%</td>
                    </tr>
                `;
        }).join('');

        // Store data for chart updates
        window.lastPerformers = data.top_performers;

        // Update charts with new data
        updateChartsWithData(data.top_performers);

        // Update activity from top performers
        updateRecentActivity(data.top_performers);

    } catch (error) {
        console.error('Top performers error:', error);
        document.getElementById('performersBody').innerHTML = `
                    <tr>
                        <td colspan="6" style="text-align: center; color: var(--error-color);">
                            Failed to load data
                        </td>
                    </tr>`;
    }
}

// Load system health
async function loadSystemHealth() {
    try {
        const response = await fetch(`${API_BASE}/dashboard/metrics/system-health`);
        if (!response.ok) throw new Error('Failed to load system health');

        const data = await response.json();

        // Update status badge
        const statusBadge = document.getElementById('systemStatus');
        statusBadge.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        statusBadge.style.background = data.status === 'healthy' ? 'var(--success-color)' : 'var(--error-color)';

        // Update health items
        document.getElementById('dbResponseTime').textContent = `${data.database.response_time_ms}ms`;
        const dbStatus = document.getElementById('dbStatus');
        dbStatus.className = 'status-dot ' + (data.database.connected ? 'healthy' : 'unhealthy');

        document.getElementById('pendingTasks').textContent = `${data.queue.pending_tasks} pending`;
        const queueStatus = document.getElementById('queueStatus');
        queueStatus.className = 'status-dot ' + (data.queue.pending_tasks > 50 ? 'warning' : 'healthy');

        document.getElementById('dbSize').textContent = formatBytes(data.disk.database_size_mb * 1024 * 1024);

        // Agent status
        if (data.agents) {
            const agentCount = Object.keys(data.agents).length;
            document.getElementById('agentsStatus').textContent =
                agentCount > 0 ? `${agentCount} active` : 'None';
            const agentsDot = document.getElementById('agentsDot');
            agentsDot.className = 'status-dot healthy';
        }

        // Load agent key health details
        loadAgentKeyHealth();

    } catch (error) {
        console.error('System health error:', error);
        document.getElementById('systemStatus').textContent = 'Error';
        document.getElementById('systemStatus').style.background = 'var(--error-color)';
        showToast('Failed to load system health status', 'warning');
    }
}

// Update recent activity
function updateRecentActivity(performers) {
    const activityList = document.getElementById('activityList');

    if (!performers || performers.length === 0) {
        activityList.innerHTML = `
                    <li style="text-align: center; color: var(--text-muted); padding: 30px;">
                        No recent activity
                    </li>`;
        document.getElementById('activityCount').textContent = '0';
        return;
    }

    activityList.innerHTML = performers.slice(0, 5).map(item => `
                <li class="activity-item">
                    <div class="activity-icon backtest">📈</div>
                    <div class="activity-content">
                        <div class="title">Backtest completed: ${escapeHtml(item.strategy_name)}</div>
                        <div class="details">
                            ${item.symbol} • Sharpe: ${item.sharpe_ratio.toFixed(2)} • Return: ${item.total_return.toFixed(1)}%
                        </div>
                    </div>
                    <div class="activity-time">${formatDate(item.completed_at)}</div>
                </li>
            `).join('');

    document.getElementById('activityCount').textContent = performers.length.toString();
}

// Utility functions
// formatNumber - using imported version from utils.js

function formatBytes(bytes) {
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(2) + ' GB';
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return bytes + ' B';
}
// formatDate - using imported version from utils.js

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Agent key health check for dashboard detail panel
async function loadAgentKeyHealth() {
    const detail = document.getElementById('agentKeysDetail');
    if (!detail) return;

    try {
        const response = await fetch(`${API_BASE}/agents/advanced/keys/pool-metrics`);
        if (!response.ok) return;
        const data = await response.json();

        const providers = {
            deepseek: document.getElementById('dashDeepseekStatus'),
            qwen: document.getElementById('dashQwenStatus'),
            perplexity: document.getElementById('dashPerplexityStatus')
        };

        let validCount = 0;
        let totalCount = 0;

        for (const [name, el] of Object.entries(providers)) {
            if (!el) continue;
            totalCount++;
            const pool = data.providers?.[name];
            if (pool && pool.total > 0) {
                const active = pool.healthy || 0;
                if (active > 0) {
                    el.textContent = 'Active';
                    el.className = 'agent-key-badge valid';
                    validCount++;
                } else {
                    el.textContent = 'Disabled';
                    el.className = 'agent-key-badge invalid';
                }
            } else {
                el.textContent = 'No Key';
                el.className = 'agent-key-badge unknown';
            }
        }

        // Show detail panel and update dot color
        detail.classList.remove('hidden');
        const agentsDot = document.getElementById('agentsDot');
        if (agentsDot) {
            if (validCount === totalCount) {
                agentsDot.className = 'status-dot healthy';
            } else if (validCount > 0) {
                agentsDot.className = 'status-dot warning';
            } else {
                agentsDot.className = 'status-dot unhealthy';
            }
        }
        document.getElementById('agentsStatus').textContent = `${validCount}/${totalCount} keys`;
    } catch (error) {
        // Silently fail — agent panel is non-critical
        console.debug('Agent key health check skipped:', error.message);
    }
}

// ==========================================
// CHART.JS CONFIGURATION
// ==========================================

// Chart color scheme
const chartColors = {
    primary: '#4ecca3',
    secondary: '#4ecdc4',
    success: '#6bcb77',
    warning: '#ffd93d',
    error: '#ff6b6b',
    purple: '#9b59b6',
    grid: 'rgba(255, 255, 255, 0.1)',
    text: '#888'
};

// Chart.js global defaults
Chart.defaults.color = chartColors.text;
Chart.defaults.borderColor = chartColors.grid;
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

// Chart instances
let performanceChart = null;
let distributionChart = null;
let winRateChart = null;
let activityChart = null;

// Initialize all charts
function initializeCharts() {
    initPerformanceChart();
    initDistributionChart();
    initWinRateChart();
    initActivityChart();
}

// Performance Over Time Chart (Line)
function initPerformanceChart() {
    const ctx = document.getElementById('performanceChart');
    if (!ctx) return;

    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Cumulative Return %',
                data: [],
                borderColor: chartColors.primary,
                backgroundColor: 'rgba(78, 204, 163, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#eee',
                    borderColor: chartColors.primary,
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: chartColors.grid },
                    ticks: { maxTicksLimit: 8 }
                },
                y: {
                    grid: { color: chartColors.grid },
                    ticks: {
                        callback: (value) => value + '%'
                    }
                }
            }
        }
    });
}

// Returns Distribution Chart (Bar/Histogram)
function initDistributionChart() {
    const ctx = document.getElementById('distributionChart');
    if (!ctx) return;

    distributionChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['< -20%', '-20 to -10%', '-10 to 0%', '0 to 10%', '10 to 20%', '> 20%'],
            datasets: [{
                label: 'Backtests',
                data: [0, 0, 0, 0, 0, 0],
                backgroundColor: [
                    chartColors.error,
                    'rgba(255, 107, 107, 0.6)',
                    'rgba(255, 217, 61, 0.6)',
                    'rgba(107, 203, 119, 0.6)',
                    chartColors.success,
                    chartColors.primary
                ],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    grid: { color: chartColors.grid },
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

// Win Rate by Strategy Chart (Doughnut)
function initWinRateChart() {
    const ctx = document.getElementById('winRateChart');
    if (!ctx) return;

    winRateChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['SMA Crossover', 'RSI', 'MACD', 'Bollinger', 'Custom'],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.secondary,
                    chartColors.warning,
                    chartColors.purple,
                    chartColors.success
                ],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        padding: 15,
                        usePointStyle: true
                    }
                }
            }
        }
    });
}

// Activity Timeline Chart (Bar)
function initActivityChart() {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;

    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Backtests',
                data: [],
                backgroundColor: chartColors.primary,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    grid: { color: chartColors.grid },
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

// Update charts with data
function updateChartsWithData(performers) {
    if (!performers || performers.length === 0) return;

    // Performance chart - cumulative returns
    const sortedByDate = [...performers].sort((a, b) =>
        new Date(a.completed_at) - new Date(b.completed_at)
    );

    let cumulative = 0;
    const cumulativeData = sortedByDate.map(p => {
        cumulative += p.total_return || 0;
        return {
            x: new Date(p.completed_at).toLocaleDateString(),
            y: cumulative
        };
    });

    if (performanceChart) {
        performanceChart.data.labels = cumulativeData.map(d => d.x);
        performanceChart.data.datasets[0].data = cumulativeData.map(d => d.y);
        performanceChart.update('none');
    }

    // Distribution chart
    const distribution = [0, 0, 0, 0, 0, 0];
    performers.forEach(p => {
        const ret = p.total_return || 0;
        if (ret < -20) distribution[0]++;
        else if (ret < -10) distribution[1]++;
        else if (ret < 0) distribution[2]++;
        else if (ret < 10) distribution[3]++;
        else if (ret < 20) distribution[4]++;
        else distribution[5]++;
    });

    if (distributionChart) {
        distributionChart.data.datasets[0].data = distribution;
        distributionChart.update('none');
    }

    // Win rate by strategy type
    const strategyStats = {};
    performers.forEach(p => {
        const type = p.strategy_type || p.strategy_name || 'Custom';
        if (!strategyStats[type]) strategyStats[type] = { wins: 0, total: 0 };
        strategyStats[type].total++;
        // win_rate may be 0-1 (fraction) or 0-100 (percentage)
        const wr = (p.win_rate || 0) <= 1 ? (p.win_rate || 0) : (p.win_rate || 0) / 100;
        if (wr > 0.5) strategyStats[type].wins++;
    });

    if (winRateChart) {
        const types = Object.keys(strategyStats);
        winRateChart.data.labels = types;
        winRateChart.data.datasets[0].data = types.map(t => strategyStats[t].total);
        winRateChart.update('none');
    }

    // Activity chart - backtests per day
    const activityByDay = {};
    performers.forEach(p => {
        const day = new Date(p.completed_at).toLocaleDateString();
        activityByDay[day] = (activityByDay[day] || 0) + 1;
    });

    const sortedDays = Object.keys(activityByDay).sort((a, b) =>
        new Date(a) - new Date(b)
    ).slice(-14); // Last 14 days

    if (activityChart) {
        activityChart.data.labels = sortedDays;
        activityChart.data.datasets[0].data = sortedDays.map(d => activityByDay[d]);
        activityChart.update('none');
    }
}

// ==========================================
// WEBSOCKET REAL-TIME UPDATES
// With Exponential Backoff & Jitter
// ==========================================

let ws = null;
let wsReconnectAttempts = 0;
let wsReconnectTimeout = null;

// WebSocket configuration
const WS_CONFIG = {
    maxReconnect: 10,          // Max attempts before giving up
    baseDelay: 1000,           // Initial delay (1 second)
    maxDelay: 30000,           // Max delay (30 seconds)
    jitterFactor: 0.3,         // Random jitter (±30%)
    pingInterval: 30000,       // Ping every 30 seconds
    pongTimeout: 5000          // Wait 5 seconds for pong
};

let wsPingInterval = null;
let wsPongTimeout = null;

function initWebSocket() {
    // Clear any existing reconnect timeout
    if (wsReconnectTimeout) {
        clearTimeout(wsReconnectTimeout);
        wsReconnectTimeout = null;
    }

    // Close existing connection if any
    if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/dashboard/ws`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('[WebSocket] Connected successfully');
            wsReconnectAttempts = 0;
            updateWsStatus('connected');

            // Start ping interval to keep connection alive
            startPingInterval();
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // Clear pong timeout on any message
                if (wsPongTimeout) {
                    clearTimeout(wsPongTimeout);
                    wsPongTimeout = null;
                }

                handleWsMessage(data);
            } catch (e) {
                console.error('[WebSocket] Message parse error:', e);
            }
        };

        ws.onclose = (event) => {
            console.log(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason || 'none'})`);
            updateWsStatus('disconnected');
            stopPingInterval();
            attemptWsReconnect();
        };

        ws.onerror = (error) => {
            console.error('[WebSocket] Error:', error);
            updateWsStatus('disconnected');
        };

    } catch (e) {
        console.error('[WebSocket] Init error:', e);
        updateWsStatus('disconnected');
        attemptWsReconnect();
    }
}

function startPingInterval() {
    stopPingInterval();
    wsPingInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));

            // Set timeout for pong response
            wsPongTimeout = setTimeout(() => {
                console.warn('[WebSocket] Pong timeout - connection may be dead');
                ws.close();
            }, WS_CONFIG.pongTimeout);
        }
    }, WS_CONFIG.pingInterval);
}

function stopPingInterval() {
    if (wsPingInterval) {
        clearInterval(wsPingInterval);
        wsPingInterval = null;
    }
    if (wsPongTimeout) {
        clearTimeout(wsPongTimeout);
        wsPongTimeout = null;
    }
}

function attemptWsReconnect() {
    if (wsReconnectAttempts >= WS_CONFIG.maxReconnect) {
        console.log('[WebSocket] Max reconnect attempts reached, falling back to polling only');
        showToast('Live updates unavailable. Using polling mode.', 'warning');
        return;
    }

    wsReconnectAttempts++;

    // Calculate exponential backoff with jitter
    const exponentialDelay = Math.min(
        WS_CONFIG.baseDelay * Math.pow(2, wsReconnectAttempts - 1),
        WS_CONFIG.maxDelay
    );

    // Add random jitter (±30%)
    const jitter = exponentialDelay * WS_CONFIG.jitterFactor * (Math.random() * 2 - 1);
    const delay = Math.round(exponentialDelay + jitter);

    console.log(`[WebSocket] Reconnect attempt ${wsReconnectAttempts}/${WS_CONFIG.maxReconnect} in ${delay}ms`);

    wsReconnectTimeout = setTimeout(initWebSocket, delay);
}

// Manual reconnect function (can be called from UI)
function reconnectWebSocket() {
    console.log('[WebSocket] Manual reconnect requested');
    wsReconnectAttempts = 0;
    initWebSocket();
}

function updateWsStatus(status) {
    const wsStatusEl = document.getElementById('wsStatus');
    if (!wsStatusEl) return;

    wsStatusEl.className = 'ws-status ' + status;
    const statusText = wsStatusEl.querySelector('span');
    if (statusText) {
        statusText.textContent = status === 'connected' ? 'Live' : 'Offline';
    }

    // Make status clickable for manual reconnect
    if (status === 'disconnected') {
        wsStatusEl.style.cursor = 'pointer';
        wsStatusEl.title = 'Click to reconnect';
        wsStatusEl.onclick = reconnectWebSocket;
    } else {
        wsStatusEl.style.cursor = 'default';
        wsStatusEl.title = 'Real-time updates active';
        wsStatusEl.onclick = null;
    }
}

function handleWsMessage(data) {
    // Don't log every message to reduce console noise
    if (data.type !== 'pong') {
        console.log('[WebSocket] Message:', data.type);
    }

    switch (data.type) {
        case 'connected':
            // Server confirmed connection
            console.log('[WebSocket] Connection confirmed:', data.message);
            break;

        case 'pong':
            // Ping-pong response - connection is healthy
            break;

        case 'metrics_update':
            // Real-time metrics update from server
            if (data.data) {
                const metrics = data.data;
                if (metrics.backtests) {
                    document.getElementById('totalBacktests').textContent = metrics.backtests.total || '--';
                    document.getElementById('runningBacktests').textContent = metrics.backtests.running || 0;
                    // Update success rate if available
                    const successRateEl = document.getElementById('successRate');
                    if (successRateEl && metrics.backtests.success_rate !== undefined) {
                        successRateEl.textContent = (metrics.backtests.success_rate * 100).toFixed(1) + '%';
                    }
                }
                if (metrics.strategies) {
                    const activeStratsEl = document.getElementById('activeStrategies');
                    if (activeStratsEl) {
                        activeStratsEl.textContent = metrics.strategies.active || 0;
                    }
                }
                // Update charts with new data
                updateChartsWithData(data.data);
            }
            break;

        case 'backtest_completed':
            // New backtest completed - refresh data
            showNotification(`Backtest completed: ${data.strategy_name}`, 'success');
            loadTopPerformers();
            loadMetricsSummary();
            break;

        case 'health_update':
            // System health update
            if (data.health) {
                document.getElementById('systemStatus').textContent = data.health.status || '--';
            }
            break;

        default:
            console.log('Unknown WebSocket message type:', data.type);
    }
}

function showNotification(message, type = 'info') {
    // Alias to new toast system
    showToast(message, type);
}

// ==========================================
// CUSTOM DATE RANGE
// ==========================================

let customDateFrom = null;
let customDateTo = null;

function applyCustomDateRange() {
    const fromInput = document.getElementById('dateFrom');
    const toInput = document.getElementById('dateTo');

    if (!fromInput.value || !toInput.value) {
        alert('Please select both start and end dates');
        return;
    }

    customDateFrom = fromInput.value;
    customDateTo = toInput.value;

    // Clear period button selection (toolbar only)
    document.querySelectorAll('.dashboard-toolbar .period-btn').forEach(b => b.classList.remove('active'));

    // Set custom period
    currentPeriod = 'custom';

    refreshDashboard();
}

// Modify the fetch URL to include custom dates
function getMetricsUrl() {
    if (currentPeriod === 'custom' && customDateFrom && customDateTo) {
        return `${API_BASE}/dashboard/metrics/summary?from=${customDateFrom}&to=${customDateTo}`;
    }
    return `${API_BASE}/dashboard/metrics/summary?period=${currentPeriod}`;
}

// Set default dates (last 7 days)
function initDatePickers() {
    const today = new Date();
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    const dateFrom = document.getElementById('dateFrom');
    const dateTo = document.getElementById('dateTo');

    if (dateFrom) dateFrom.value = weekAgo.toISOString().split('T')[0];
    if (dateTo) dateTo.value = today.toISOString().split('T')[0];
}

// Chart metric selector
document.getElementById('chartMetricSelect')?.addEventListener('change', (e) => {
    const metric = e.target.value;
    // Update performance chart based on selected metric
    if (performanceChart && window.lastPerformers) {
        updatePerformanceChartMetric(metric);
    }
});

function updatePerformanceChartMetric(metric) {
    const performers = window.lastPerformers || [];
    const sortedByDate = [...performers].sort((a, b) =>
        new Date(a.completed_at) - new Date(b.completed_at)
    );

    let data, label;
    switch (metric) {
        case 'sharpe':
            data = sortedByDate.map(p => p.sharpe_ratio || 0);
            label = 'Sharpe Ratio';
            break;
        case 'trades':
            data = sortedByDate.map(p => p.total_trades || 0);
            label = 'Trade Count';
            break;
        default: {
            let cumulative = 0;
            data = sortedByDate.map(p => {
                cumulative += p.total_return || 0;
                return cumulative;
            });
            label = 'Cumulative Return %';
        }
    }

    performanceChart.data.labels = sortedByDate.map(p =>
        new Date(p.completed_at).toLocaleDateString()
    );
    performanceChart.data.datasets[0].data = data;
    performanceChart.data.datasets[0].label = label;
    performanceChart.update('none');
}

// NOTE: DOMContentLoaded handler moved to consolidated handler below (line ~3047)
// This ensures all initialization happens in one place

// Clean up on page leave
window.addEventListener('beforeunload', () => {
    // Clear all managed intervals
    IntervalManager.clearAll();

    // Stop WebSocket ping and close connection
    stopPingInterval();
    if (ws) {
        ws.onclose = null; // Prevent reconnect on intentional close
        ws.close();
    }

    // Clear any pending reconnect timeout
    if (wsReconnectTimeout) {
        clearTimeout(wsReconnectTimeout);
    }
});

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
document.head.appendChild(style);

// =====================================================
// NEW: Dashboard Improvements - Milestone 4.4
// =====================================================

let portfolioHistoryChart = null;
let pnlMiniChart = null;
let portfolioDays = 7;

// Initialize new charts
function initializeNewCharts() {
    // Portfolio History Chart
    const portfolioCtx = document.getElementById('portfolioHistoryChart');
    if (portfolioCtx) {
        portfolioHistoryChart = new Chart(portfolioCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Portfolio Value',
                    data: [],
                    borderColor: '#4ecca3',
                    backgroundColor: 'rgba(78, 204, 163, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#888' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: {
                            color: '#888',
                            callback: v => '$' + v.toLocaleString()
                        }
                    }
                }
            }
        });
    }

    // P&L Mini Chart
    const pnlCtx = document.getElementById('pnlMiniChart');
    if (pnlCtx) {
        pnlMiniChart = new Chart(pnlCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    borderColor: '#6bcb77',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { display: false }
                }
            }
        });
    }
}

// Load Portfolio History
async function loadPortfolioHistory() {
    try {
        const response = await fetch(`${API_BASE}/dashboard/portfolio/history?days=${portfolioDays}`);
        if (!response.ok) throw new Error('Failed to load portfolio history');

        const data = await response.json();

        // API returns data_points with {timestamp, equity, pnl, ...}
        const points = data.data_points || data.history || [];
        if (portfolioHistoryChart && points.length > 0) {
            portfolioHistoryChart.data.labels = points.map(h =>
                new Date(h.timestamp).toLocaleDateString()
            );
            portfolioHistoryChart.data.datasets[0].data = points.map(h => h.equity ?? h.total_value ?? 0);
            portfolioHistoryChart.update('none');
        }
    } catch (error) {
        console.error('Portfolio history error:', error);
        showToast('Failed to load portfolio history', 'warning');
    }
}

// Load AI Recommendations
async function loadAIRecommendations() {
    const container = document.getElementById('aiRecommendations');
    if (!container) return;

    container.innerHTML = `
                <div class="ai-loading">
                    <div class="spinner"></div>
                    <span>Analyzing portfolio...</span>
                </div>
            `;

    try {
        const response = await fetch(`${API_BASE}/dashboard/ai-recommendations`);
        if (!response.ok) throw new Error('Failed to load AI recommendations');

        const data = await response.json();

        if (data.recommendations && data.recommendations.length > 0) {
            container.innerHTML = data.recommendations.map(rec => `
                        <div class="ai-recommendation ${rec.priority}-priority">
                            <div class="rec-header">
                                <span class="rec-type">${rec.type}</span>
                                <span class="rec-priority">${rec.priority.toUpperCase()}</span>
                            </div>
                            <div class="rec-title">${rec.title || 'Recommendation'}</div>
                            <div class="rec-message">${rec.description || ''}</div>
                            ${rec.action ? `<div class="rec-action">💡 <a href="${rec.action}">${rec.action}</a></div>` : ''}
                        </div>
                    `).join('');
        } else {
            container.innerHTML = `
                        <div class="ai-recommendation">
                            <div class="rec-message">✅ No immediate recommendations. Your portfolio is performing well!</div>
                        </div>
                    `;
        }
    } catch (error) {
        console.error('AI recommendations error:', error);
        container.innerHTML = `
                    <div class="error-message">
                        Failed to load AI recommendations. <button onclick="loadAIRecommendations()">Retry</button>
                    </div>
                `;
    }
}

// Load Current P&L
async function loadCurrentPnL() {
    try {
        const response = await fetch(`${API_BASE}/dashboard/pnl/current`);
        if (!response.ok) throw new Error('Failed to load P&L');

        const data = await response.json();

        // Update P&L display
        const pnlValue = document.getElementById('currentPnL');
        if (pnlValue) {
            const value = data.current_pnl || 0;
            pnlValue.textContent = (value >= 0 ? '+' : '') + '$' + Math.abs(value).toFixed(2);
            pnlValue.className = 'pnl-value ' + (value >= 0 ? 'positive' : 'negative');
        }

        // Update stats
        updatePnLStat('pnlToday', data.today_pnl);
        updatePnLStat('pnlWeek', data.week_pnl);
        updatePnLStat('pnlMonth', data.month_pnl);

        const openPos = document.getElementById('openPositions');
        if (openPos) openPos.textContent = data.open_positions || 0;

        // Update mini chart
        if (pnlMiniChart && data.hourly_pnl && data.hourly_pnl.length > 0) {
            pnlMiniChart.data.labels = data.hourly_pnl.map((_, i) => i);
            pnlMiniChart.data.datasets[0].data = data.hourly_pnl;
            pnlMiniChart.data.datasets[0].borderColor =
                data.current_pnl >= 0 ? '#6bcb77' : '#ff6b6b';
            pnlMiniChart.update('none');
        }
    } catch (error) {
        console.error('P&L error:', error);
        // Silent fail for P&L - it updates frequently
    }
}

function updatePnLStat(id, value) {
    const el = document.getElementById(id);
    if (el) {
        const v = value || 0;
        el.textContent = (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2);
        el.className = 'value ' + (v >= 0 ? 'positive' : 'negative');
    }
}

// Load Strategy Leaderboard
async function loadStrategyLeaderboard() {
    const tbody = document.getElementById('leaderboardBody');
    if (!tbody) return;

    const period = document.getElementById('leaderboardPeriod')?.value || '7d';

    try {
        const response = await fetch(`${API_BASE}/dashboard/strategy-leaderboard?period=${period}`);
        if (!response.ok) throw new Error('Failed to load leaderboard');

        const data = await response.json();

        // API returns 'entries', support both keys for compatibility
        const leaderboard = data.leaderboard || data.entries || [];
        if (leaderboard.length > 0) {
            tbody.innerHTML = leaderboard.map((s, i) => {
                const rankClass = i < 3 ? `rank-${i + 1}` : '';
                // API returns trend as string: "up", "down", "stable"
                const trendIcon = s.trend === 'up' ? '📈' : (s.trend === 'down' ? '📉' : '➡️');
                const trendClass = s.trend === 'up' ? 'trend-up' : (s.trend === 'down' ? 'trend-down' : 'trend-neutral');
                // Map API fields: avg_return -> pnl, avg_win_rate -> win_rate, total_backtests -> trade_count
                const pnl = s.pnl ?? s.avg_return ?? 0;
                const winRate = s.win_rate ?? s.avg_win_rate ?? 0;
                const tradeCount = s.trade_count ?? s.total_backtests ?? 0;
                const pnlClass = pnl >= 0 ? 'trend-up' : 'trend-down';

                return `
                            <tr class="${rankClass}">
                                <td>${i + 1}</td>
                                <td>${s.strategy_name}</td>
                                <td class="${pnlClass}">${pnl >= 0 ? '+' : ''}${Math.abs(pnl).toFixed(2)}%</td>
                                <td>${(winRate * (winRate <= 1 ? 100 : 1)).toFixed(1)}%</td>
                                <td>${tradeCount}</td>
                                <td class="${trendClass}">${trendIcon}</td>
                            </tr>
                        `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="table-loading">No strategies found</td></tr>';
        }
    } catch (error) {
        console.error('Leaderboard error:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Error loading leaderboard</td></tr>';
        showToast('Failed to load strategy leaderboard', 'warning');
    }
}

// Portfolio period selector
document.querySelectorAll('#portfolioPeriodSelector .period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#portfolioPeriodSelector .period-btn').forEach(b =>
            b.classList.remove('active')
        );
        btn.classList.add('active');
        portfolioDays = parseInt(btn.dataset.days);
        loadPortfolioHistory();
    });
});

// Leaderboard period selector
document.getElementById('leaderboardPeriod')?.addEventListener('change', () => {
    loadStrategyLeaderboard();
});

// =====================================================
// INTERVAL MANAGER - Centralized Update Scheduler
// =====================================================
const IntervalManager = {
    intervals: new Map(),
    paused: false,
    debug: false,

    // Register a new interval
    register(name, callback, intervalMs, options = {}) {
        if (this.intervals.has(name)) {
            this.clear(name);
        }

        const config = {
            callback,
            intervalMs,
            immediate: options.immediate !== false,
            runWhenHidden: options.runWhenHidden || false,
            lastRun: 0,
            intervalId: null,
            errorCount: 0,
            maxErrors: options.maxErrors || 5
        };

        this.intervals.set(name, config);

        // Run immediately if requested
        if (config.immediate && !this.paused) {
            this._execute(name);
        }

        // Start the interval
        config.intervalId = setInterval(() => this._tick(name), intervalMs);

        if (this.debug) console.log(`[IntervalManager] Registered: ${name} (${intervalMs}ms)`);
        return this;
    },

    // Internal tick handler
    _tick(name) {
        const config = this.intervals.get(name);
        if (!config) return;

        // Skip if paused or page hidden (unless runWhenHidden)
        if (this.paused) return;
        if (document.hidden && !config.runWhenHidden) return;

        this._execute(name);
    },

    // Execute callback with error handling
    async _execute(name) {
        const config = this.intervals.get(name);
        if (!config) return;

        try {
            config.lastRun = Date.now();
            await config.callback();
            config.errorCount = 0; // Reset on success
        } catch (err) {
            config.errorCount++;
            console.error(`[IntervalManager] Error in ${name}:`, err);

            if (config.errorCount >= config.maxErrors) {
                console.warn(`[IntervalManager] ${name} disabled after ${config.maxErrors} errors`);
                this.clear(name);
                showToast(`Auto-update for ${name} disabled due to errors`, 'warning');
            }
        }
    },

    // Clear a specific interval
    clear(name) {
        const config = this.intervals.get(name);
        if (config && config.intervalId) {
            clearInterval(config.intervalId);
            this.intervals.delete(name);
            if (this.debug) console.log(`[IntervalManager] Cleared: ${name}`);
        }
    },

    // Clear all intervals
    clearAll() {
        this.intervals.forEach((config, _name) => {
            if (config.intervalId) clearInterval(config.intervalId);
        });
        this.intervals.clear();
        if (this.debug) console.log('[IntervalManager] All intervals cleared');
    },

    // Pause all intervals
    pause() {
        this.paused = true;
        if (this.debug) console.log('[IntervalManager] Paused');
    },

    // Resume all intervals
    resume() {
        this.paused = false;
        if (this.debug) console.log('[IntervalManager] Resumed');
        // Run all immediate callbacks
        this.intervals.forEach((config, name) => {
            if (config.immediate) this._execute(name);
        });
    },

    // Get status
    status() {
        const status = {
            paused: this.paused,
            intervals: []
        };
        this.intervals.forEach((config, name) => {
            status.intervals.push({
                name,
                intervalMs: config.intervalMs,
                lastRun: config.lastRun ? new Date(config.lastRun).toLocaleTimeString() : 'never',
                errorCount: config.errorCount
            });
        });
        return status;
    },

    // Force run a specific interval now
    runNow(name) {
        if (this.intervals.has(name)) {
            this._execute(name);
        }
    },

    // Adjust interval timing
    setInterval(name, newIntervalMs) {
        const config = this.intervals.get(name);
        if (config) {
            clearInterval(config.intervalId);
            config.intervalMs = newIntervalMs;
            config.intervalId = setInterval(() => this._tick(name), newIntervalMs);
            if (this.debug) console.log(`[IntervalManager] ${name} interval changed to ${newIntervalMs}ms`);
        }
    }
};

// Page Visibility API - pause updates when tab is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        IntervalManager.pause();
        console.log('[Dashboard] Tab hidden - updates paused');
    } else {
        IntervalManager.resume();
        console.log('[Dashboard] Tab visible - updates resumed');
    }
});

// =====================================================
// CONSOLIDATED DOMContentLoaded Handler
// All dashboard initialization in one place
// =====================================================
document.addEventListener('DOMContentLoaded', () => {
    // ---- Core Initialization ----
    initDatePickers();
    initializeCharts();
    refreshDashboard();

    // Try WebSocket, fall back to polling
    initWebSocket();

    // ---- Milestone 4.4 Charts ----
    initializeNewCharts();
    loadPortfolioHistory();
    loadAIRecommendations();
    loadCurrentPnL();
    loadStrategyLeaderboard();

    // ---- Dashboard Enhancements ----
    initMarketOverview();
    initLiveTicker();
    initWatchlist();
    initMiniCalendar();
    initRiskHeatmap();
    initKeyboardShortcuts();
    loadTheme();
    initToastContainer();

    // ---- Auto-refresh via IntervalManager ----
    // Dashboard metrics every 30 seconds (backup for WebSocket)
    IntervalManager.register('dashboard', refreshDashboard, 30000, { immediate: false });

    // P&L every 10 seconds
    IntervalManager.register('pnl', loadCurrentPnL, 10000, { immediate: false });

    // Market data every 5 seconds (critical for trading)
    IntervalManager.register('market', updateMarketData, 5000, { immediate: false });

    // Watchlist prices every 10 seconds
    IntervalManager.register('watchlist', updateWatchlistPrices, 10000, { immediate: false });

    // Portfolio history every 60 seconds
    IntervalManager.register('portfolio', loadPortfolioHistory, 60000, { immediate: false });

    // AI Recommendations every 2 minutes
    IntervalManager.register('ai-recommendations', loadAIRecommendations, 120000, { immediate: false });

    // Strategy leaderboard every 60 seconds
    IntervalManager.register('leaderboard', loadStrategyLeaderboard, 60000, { immediate: false });

    console.log('[Dashboard] Initialized with IntervalManager:', IntervalManager.status());
});

// =====================================================
// NEW: Enhanced Dashboard Features
// =====================================================

// Theme Toggle
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('dashboard_theme', newTheme);
    updateThemeIcons(newTheme);
}

function loadTheme() {
    const savedTheme = localStorage.getItem('dashboard_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcons(savedTheme);
}

function updateThemeIcons(theme) {
    const darkIcon = document.getElementById('darkModeIcon');
    const lightIcon = document.getElementById('lightModeIcon');
    if (theme === 'dark') {
        darkIcon?.classList.add('active');
        lightIcon?.classList.remove('active');
    } else {
        darkIcon?.classList.remove('active');
        lightIcon?.classList.add('active');
    }
}

// Keyboard Shortcuts
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Skip if in input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            return;
        }

        const key = e.key.toLowerCase();

        switch (key) {
            case '?':
                showShortcuts();
                break;
            case 'escape':
                hideShortcuts();
                break;
            case 'd':
                window.location.href = 'dashboard.html';
                break;
            case 's':
                window.location.href = 'strategies.html';
                break;
            case 't':
                window.location.href = 'trading.html';
                break;
            case 'c':
                window.location.href = 'market-chart.html';
                break;
            case 'a':
                window.location.href = 'analytics.html';
                break;
            case 'r':
                refreshDashboard();
                break;
            case 'n':
                window.location.href = 'strategies.html?action=new';
                break;
            case 'l':
                toggleTheme();
                break;
            case 'i':
                window.location.href = 'notifications.html';
                break;
            case 'o':
                window.location.href = 'settings.html';
                break;
        }
    });
}

function showShortcuts() {
    document.getElementById('shortcutsModal')?.classList.add('show');
}

function hideShortcuts() {
    document.getElementById('shortcutsModal')?.classList.remove('show');
}

// Market Overview - Dynamic top by volume from Bybit API
let marketData = [];

// Fetch real market data from API - Dynamic top 6 by trading volume
async function fetchMarketData() {
    try {
        // Fetch top 6 by 24h trading volume (dynamic)
        const response = await fetch('/api/v1/dashboard/market/tickers?top=6');
        const data = await response.json();
        if (data.success && data.tickers) {
            // Replace marketData with dynamic top from API
            marketData = data.tickers.map(ticker => ({
                symbol: ticker.symbol,
                name: ticker.name,
                icon: ticker.icon,
                color: ticker.color,
                price: ticker.price || 0,
                change: ticker.change || 0,
                volume_24h: ticker.volume_24h || 0,
                turnover_24h: ticker.turnover_24h || 0
            }));
            // Re-render market overview with new data
            renderMarketOverview();
            updateLiveTicker();
            updateRiskHeatmap();
        }
    } catch (err) {
        console.error('Failed to fetch market data:', err);
        // Silent fail for market data - it updates frequently
    }
}

function renderMarketOverview() {
    const container = document.getElementById('marketOverview');
    if (!container) return;

    container.innerHTML = marketData.map(m => `
                <div class="market-card" onclick="window.location.href='market-chart.html?symbol=${m.symbol}'">
                    <div class="market-icon" style="background: ${m.color}22; color: ${m.color}">
                        ${m.icon}
                    </div>
                    <div class="market-info">
                        <div class="market-symbol">${m.symbol.replace('USDT', '')}</div>
                        <div class="market-name">${m.name}</div>
                    </div>
                    <div class="market-data">
                        <div class="market-price" id="price-${m.symbol}">$${m.price ? m.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: m.price < 1 ? 4 : 2 }) : '--'}</div>
                        <div class="market-change ${m.change >= 0 ? 'up' : 'down'}" id="change-${m.symbol}">
                            ${m.change >= 0 ? '+' : ''}${m.change.toFixed(2)}%
                        </div>
                    </div>
                </div>
            `).join('');
}

function initMarketOverview() {
    renderMarketOverview();
    // Fetch real data immediately
    fetchMarketData();
    // NOTE: Interval now managed by IntervalManager in DOMContentLoaded
}

function updateMarketData() {
    // Now handled by fetchMarketData()
    fetchMarketData();
}

// Live Ticker - Top 20 by volume (separate from cards)
let tickerData = [];

async function fetchTickerData() {
    try {
        // Fetch top 20 by trading volume for the scrolling ticker
        const response = await fetch('/api/v1/dashboard/market/tickers?top=20');
        const data = await response.json();
        if (data.success && data.tickers) {
            tickerData = data.tickers;
            renderLiveTicker();
        }
    } catch (err) {
        console.error('Failed to fetch ticker data:', err);
        // Silent fail for ticker - it updates frequently
    }
}

let tickerInitialized = false;

function renderLiveTicker() {
    const track = document.getElementById('tickerTrack');
    if (!track || tickerData.length === 0) return;

    const tickerItems = tickerData.map(m => ({
        symbol: m.symbol.replace('USDT', '/USDT'),
        price: m.price,
        change: m.change
    }));

    // If already initialized, only update prices without re-rendering
    // This prevents animation reset/jerk
    if (tickerInitialized) {
        // Update existing elements in place
        const items = track.querySelectorAll('.ticker-item');
        tickerItems.forEach((item, idx) => {
            // Update both copies (original and duplicate)
            [idx, idx + tickerItems.length].forEach(i => {
                if (items[i]) {
                    const priceEl = items[i].querySelector('.ticker-price');
                    const changeEl = items[i].querySelector('.ticker-change');
                    if (priceEl) {
                        priceEl.textContent = '$' + (item.price ? item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: item.price < 1 ? 4 : 2 }) : '--');
                    }
                    if (changeEl) {
                        changeEl.textContent = (item.change >= 0 ? '▲' : '▼') + ' ' + Math.abs(item.change).toFixed(2) + '%';
                        changeEl.className = 'ticker-change ' + (item.change >= 0 ? 'positive' : 'negative');
                    }
                }
            });
        });
        return;
    }

    // Initial render - duplicate for seamless loop
    const html = [...tickerItems, ...tickerItems].map(item => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${item.symbol}</span>
                    <span class="ticker-price">$${item.price ? item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: item.price < 1 ? 4 : 2 }) : '--'}</span>
                    <span class="ticker-change ${item.change >= 0 ? 'positive' : 'negative'}">
                        ${item.change >= 0 ? '▲' : '▼'} ${Math.abs(item.change).toFixed(2)}%
                    </span>
                </div>
            `).join('');

    track.innerHTML = html;
    tickerInitialized = true;
}

// Legacy function for backward compatibility
function updateLiveTicker() {
    renderLiveTicker();
}

function initLiveTicker() {
    // Fetch top 20 for ticker immediately
    fetchTickerData();
    // Register with IntervalManager for periodic updates
    IntervalManager.register('ticker', fetchTickerData, 15000, { immediate: false });
}

// =====================================================
// Toast Notification System
// =====================================================
function initToastContainer() {
    if (document.getElementById('toastContainer')) return;

    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
            `;
    document.body.appendChild(container);
}

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) initToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    const colors = {
        success: { bg: 'rgba(39, 174, 96, 0.95)', border: '#27ae60' },
        error: { bg: 'rgba(231, 76, 60, 0.95)', border: '#e74c3c' },
        warning: { bg: 'rgba(241, 196, 15, 0.95)', border: '#f1c40f' },
        info: { bg: 'rgba(52, 152, 219, 0.95)', border: '#3498db' }
    };

    const style = colors[type] || colors.info;

    toast.style.cssText = `
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 14px 18px;
                background: ${style.bg};
                border-left: 4px solid ${style.border};
                border-radius: 8px;
                color: white;
                font-size: 14px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                animation: toastSlideIn 0.3s ease-out;
                cursor: pointer;
            `;

    toast.innerHTML = `
                <span style="font-size: 18px;">${icons[type] || icons.info}</span>
                <span style="flex: 1;">${message}</span>
                <span style="opacity: 0.7; font-size: 16px;" onclick="this.parentElement.remove()">×</span>
            `;

    toast.addEventListener('click', () => toast.remove());

    document.getElementById('toastContainer').appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Add toast animations to document
(function () {
    const toastStyle = document.createElement('style');
    toastStyle.textContent = `
                @keyframes toastSlideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes toastSlideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
    document.head.appendChild(toastStyle);
})();

// =====================================================
// Watchlist with API Updates
// =====================================================
let watchlist = JSON.parse(localStorage.getItem('dashboard_watchlist') || '["BTCUSDT","ETHUSDT","SOLUSDT"]');
const watchlistPrices = {};

function initWatchlist() {
    renderWatchlist();
    updateWatchlistPrices();
}

async function updateWatchlistPrices() {
    if (watchlist.length === 0) return;

    try {
        const symbolsParam = watchlist.join(',');
        const response = await fetch(`/api/v1/dashboard/market/tickers?symbols=${symbolsParam}`);
        const data = await response.json();

        if (data.success && data.tickers) {
            data.tickers.forEach(ticker => {
                watchlistPrices[ticker.symbol] = {
                    price: ticker.price,
                    change: ticker.change,
                    name: ticker.name || ticker.symbol.replace('USDT', '')
                };
            });
            renderWatchlist();
        }
    } catch (err) {
        console.error('Failed to fetch watchlist prices:', err);
    }
}

function renderWatchlist() {
    const container = document.getElementById('watchlistWidget');
    if (!container) return;

    if (watchlist.length === 0) {
        container.innerHTML = `
                    <div style="text-align: center; padding: 20px; color: #888;">
                        No symbols in watchlist.<br>
                        Click ➕ to add symbols.
                    </div>
                `;
        return;
    }

    const html = watchlist.map(symbol => {
        const priceData = watchlistPrices[symbol] || {};
        const price = priceData.price ? '$' + priceData.price.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: priceData.price < 1 ? 6 : 2
        }) : '--';
        const change = priceData.change !== undefined ? priceData.change : 0;
        const changeClass = change >= 0 ? 'up' : 'down';
        const changeText = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
        const name = priceData.name || symbol.replace('USDT', '');

        return `
                    <div class="watchlist-item" data-symbol="${symbol}">
                        <div class="watchlist-left">
                            <span class="watchlist-star" onclick="removeFromWatchlist('${symbol}')" title="Remove from watchlist">★</span>
                            <div>
                                <div class="market-symbol">${symbol.replace('USDT', '/USDT')}</div>
                                <div class="market-name">${name}</div>
                            </div>
                        </div>
                        <div class="watchlist-right">
                            <div class="market-price">${price}</div>
                            <div class="market-change ${changeClass}">${changeText}</div>
                        </div>
                    </div>
                `;
    }).join('');

    container.innerHTML = html;
}

function addToWatchlist() {
    const symbol = prompt('Enter symbol (e.g., BTCUSDT):');
    if (symbol) {
        const normalized = symbol.toUpperCase().replace(/[^A-Z]/g, '');
        const finalSymbol = normalized.endsWith('USDT') ? normalized : normalized + 'USDT';

        if (watchlist.includes(finalSymbol)) {
            showToast(`${finalSymbol} is already in your watchlist`, 'warning');
            return;
        }

        watchlist.push(finalSymbol);
        localStorage.setItem('dashboard_watchlist', JSON.stringify(watchlist));
        showToast(`${finalSymbol.replace('USDT', '/USDT')} added to watchlist`, 'success');
        updateWatchlistPrices();
    }
}

function removeFromWatchlist(symbol) {
    watchlist = watchlist.filter(s => s !== symbol);
    localStorage.setItem('dashboard_watchlist', JSON.stringify(watchlist));
    showToast(`${symbol.replace('USDT', '/USDT')} removed from watchlist`, 'info');
    renderWatchlist();
}

// Mini Calendar
let calendarYear, calendarMonth;

function initMiniCalendar() {
    const today = new Date();
    calendarYear = today.getFullYear();
    calendarMonth = today.getMonth();
    renderCalendar(calendarYear, calendarMonth);
}

function changeMonth(delta) {
    calendarMonth += delta;
    if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
    if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
    renderCalendar(calendarYear, calendarMonth);
}

function renderCalendar(year, month) {
    const calendarGrid = document.querySelector('.calendar-grid');
    if (!calendarGrid) return;

    const monthLabel = document.getElementById('calendarMonth');
    if (monthLabel) {
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        monthLabel.textContent = `${monthNames[month]} ${year}`;
    }

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const today = new Date();

    // Day headers
    let html = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
        .map(d => `<div class="calendar-day-header">${d}</div>`).join('');

    // Previous month trailing days
    for (let i = 0; i < firstDay.getDay(); i++) {
        const prevDate = new Date(year, month, -firstDay.getDay() + i + 1);
        html += `<div class="calendar-day other-month">${prevDate.getDate()}</div>`;
    }

    // Current month days
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const date = new Date(year, month, day);
        const isToday = date.toDateString() === today.toDateString();
        html += `<div class="calendar-day${isToday ? ' today' : ''}">${day}</div>`;
    }

    calendarGrid.innerHTML = html;
}

// Risk Heatmap — dynamic from market data volatility
function initRiskHeatmap() {
    updateRiskHeatmap();
}

function updateRiskHeatmap() {
    const container = document.getElementById('riskHeatmap');
    if (!container) return;

    // Use market data if available, otherwise use defaults
    const coins = marketData.length > 0 ? marketData : [
        { symbol: 'BTCUSDT', change: 0 },
        { symbol: 'ETHUSDT', change: 0 },
        { symbol: 'SOLUSDT', change: 0 },
        { symbol: 'BNBUSDT', change: 0 },
        { symbol: 'DOGEUSDT', change: 0 },
        { symbol: 'XRPUSDT', change: 0 }
    ];

    container.innerHTML = coins.slice(0, 6).map(m => {
        const absChange = Math.abs(m.change || 0);
        // Map 24h change magnitude to risk level
        const riskClass = absChange < 2 ? 'risk-low' : (absChange < 5 ? 'risk-medium' : (absChange < 10 ? 'risk-high' : 'risk-extreme'));
        const riskLabel = absChange < 2 ? 'Low' : (absChange < 5 ? 'Medium' : (absChange < 10 ? 'High' : 'Extreme'));
        const symbol = (m.symbol || '').replace('USDT', '');
        const changeStr = (m.change >= 0 ? '+' : '') + (m.change || 0).toFixed(2) + '%';
        return `
            <div class="heatmap-cell ${riskClass}">
                <div class="symbol">${symbol}</div>
                <div class="value">${riskLabel} (${changeStr})</div>
            </div>`;
    }).join('');
}

function _getRiskClass(risk) {
    if (risk < 25) return 'risk-low';
    if (risk < 50) return 'risk-medium';
    if (risk < 75) return 'risk-high';
    return 'risk-extreme';
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: async, refreshDashboard, loadMetricsSummary, loadTopPerformers, loadSystemHealth

// Attach to window for backwards compatibility and HTML onclick handlers
if (typeof window !== 'undefined') {
    window.dashboardPage = {
        refreshDashboard,
        loadMetricsSummary,
        loadTopPerformers,
        loadSystemHealth
    };
    // Required for inline onclick handlers in dashboard.html
    window.changeMonth = changeMonth;
    window.addToWatchlist = addToWatchlist;
    window.removeFromWatchlist = removeFromWatchlist;
    window.refreshDashboard = refreshDashboard;
    window.loadAIRecommendations = loadAIRecommendations;
    window.hideShortcuts = hideShortcuts;
    window.showShortcuts = showShortcuts;
    window.toggleTheme = toggleTheme;
    window.applyCustomDateRange = applyCustomDateRange;
}
