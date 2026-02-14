/**
 * 📄 Analytics Page JavaScript
 *
 * Page-specific scripts for analytics.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient as _apiClient, API_CONFIG as _API_CONFIG } from '../api.js';
import { formatNumber as _formatNumber, formatCurrency, formatDate as _formatDate, debounce as _debounce } from '../utils.js';

// Configuration
const API_BASE = window.location.origin;
const RISK_API = `${API_BASE}/api/v1/risk`;

let equityChart = null;
let riskDistributionChart = null;
// eslint-disable-next-line no-unused-vars
let refreshInterval = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    refreshData();

    // Auto-refresh every 30 seconds
    refreshInterval = setInterval(refreshData, 30000);

    // Period buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            loadEquityData(e.target.dataset.period);
        });
    });
});

function initCharts() {
    // Equity Curve Chart
    const equityCtx = document.getElementById('equityChart').getContext('2d');
    equityChart = new Chart(equityCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Equity',
                    data: [],
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Drawdown %',
                    data: [],
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248, 81, 73, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    labels: { color: '#f0f6fc' }
                }
            },
            scales: {
                x: {
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' }
                },
                y: {
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' },
                    position: 'left'
                },
                y1: {
                    grid: { display: false },
                    ticks: { color: '#f85149' },
                    position: 'right'
                }
            }
        }
    });

    // Risk Distribution Chart
    const riskCtx = document.getElementById('riskDistributionChart').getContext('2d');
    riskDistributionChart = new Chart(riskCtx, {
        type: 'doughnut',
        data: {
            labels: ['Low Risk', 'Medium Risk', 'High Risk'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    'rgba(63, 185, 80, 0.8)',
                    'rgba(210, 153, 34, 0.8)',
                    'rgba(248, 81, 73, 0.8)'
                ],
                borderColor: '#161b22',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#f0f6fc' }
                }
            }
        }
    });
}

async function refreshData() {
    try {
        updateConnectionStatus(true);

        // Fetch risk summary
        const summaryResponse = await fetch(`${RISK_API}/summary`);
        if (summaryResponse.ok) {
            const summary = await summaryResponse.json();
            updateRiskSummary(summary);
        }

        // Fetch portfolio metrics
        const portfolioResponse = await fetch(`${RISK_API}/portfolio`);
        if (portfolioResponse.ok) {
            const portfolio = await portfolioResponse.json();
            updatePortfolioMetrics(portfolio);
        }

        // Fetch positions
        const positionsResponse = await fetch(`${RISK_API}/positions`);
        if (positionsResponse.ok) {
            const positions = await positionsResponse.json();
            updatePositionHeatmap(positions);
        }

        // Fetch alerts
        const alertsResponse = await fetch(`${RISK_API}/alerts`);
        if (alertsResponse.ok) {
            const alerts = await alertsResponse.json();
            updateAlerts(alerts);
        }

        // Update timestamp
        document.getElementById('lastUpdate').textContent =
            `Last update: ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        console.error('Failed to refresh data:', error);
        updateConnectionStatus(false);
        showMockData();
    }
}

function updateConnectionStatus(connected) {
    const status = document.getElementById('connectionStatus');
    if (connected) {
        status.className = 'status-badge connected';
        status.innerHTML = '<span class="status-dot"></span> Connected';
    } else {
        status.className = 'status-badge disconnected';
        status.innerHTML = '<span class="status-dot"></span> Demo Mode';
    }
}

function updateRiskSummary(summary) {
    const scoreEl = document.getElementById('riskScore');
    const levelEl = document.getElementById('riskLevel');
    const descEl = document.getElementById('riskDescription');

    const score = summary.risk_score || 0;
    scoreEl.textContent = score.toFixed(1);

    // Color based on score
    if (score < 30) {
        scoreEl.style.color = 'var(--accent-green)';
        levelEl.textContent = 'Low Risk';
        descEl.textContent = 'Portfolio is within safe parameters';
    } else if (score < 70) {
        scoreEl.style.color = 'var(--accent-yellow)';
        levelEl.textContent = 'Medium Risk';
        descEl.textContent = 'Some positions require attention';
    } else {
        scoreEl.style.color = 'var(--accent-red)';
        levelEl.textContent = 'High Risk';
        descEl.textContent = 'Immediate action recommended';
    }
}

function updatePortfolioMetrics(portfolio) {
    // VaR metrics
    document.getElementById('var95').textContent = formatCurrency(portfolio.var_95 || 0);
    document.getElementById('var99').textContent = formatCurrency(portfolio.var_99 || 0);

    // Ratios
    const sharpe = portfolio.sharpe_ratio || 0;
    const sortino = portfolio.sortino_ratio || 0;

    document.getElementById('sharpeRatio').textContent = sharpe.toFixed(2);
    document.getElementById('sharpeRatio').className =
        `metric-value ${sharpe > 1 ? 'positive' : sharpe < 0 ? 'negative' : ''}`;

    document.getElementById('sortinoRatio').textContent = sortino.toFixed(2);
    document.getElementById('sortinoRatio').className =
        `metric-value ${sortino > 1 ? 'positive' : sortino < 0 ? 'negative' : ''}`;

    // Table values
    document.getElementById('totalEquity').textContent = formatCurrency(portfolio.total_equity || 0);
    document.getElementById('totalExposure').textContent = formatCurrency(portfolio.total_exposure || 0);

    const pnl = portfolio.unrealized_pnl || 0;
    document.getElementById('unrealizedPnl').textContent = formatCurrency(pnl);
    document.getElementById('unrealizedPnl').style.color =
        pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';

    document.getElementById('maxDrawdown').textContent =
        formatPercent(portfolio.max_drawdown || 0);
    document.getElementById('currentDrawdown').textContent =
        formatPercent(portfolio.current_drawdown || 0);
    document.getElementById('winRate').textContent =
        formatPercent(portfolio.win_rate || 0);
}

function updatePositionHeatmap(positions) {
    const container = document.getElementById('positionHeatmap');

    if (!positions || positions.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); padding: 20px;">No open positions</p>';
        return;
    }

    container.innerHTML = positions.map(pos => {
        const riskClass = pos.risk_score > 70 ? 'high-risk' :
            pos.risk_score > 30 ? 'medium-risk' : 'low-risk';
        return `
                    <div class="heatmap-cell ${riskClass}" onclick="showPositionDetails('${pos.symbol}')">
                        <span class="heatmap-symbol">${pos.symbol}</span>
                        <span class="heatmap-value">${formatPercent(pos.unrealized_pnl_pct)}</span>
                    </div>
                `;
    }).join('');

    // Update distribution chart
    const low = positions.filter(p => p.risk_score < 30).length;
    const medium = positions.filter(p => p.risk_score >= 30 && p.risk_score < 70).length;
    const high = positions.filter(p => p.risk_score >= 70).length;

    riskDistributionChart.data.datasets[0].data = [low, medium, high];
    riskDistributionChart.update();
}

function updateAlerts(alerts) {
    const container = document.getElementById('alertsList');
    const badge = document.getElementById('alertCount');

    const criticalCount = alerts.filter(a => a.level === 'critical').length;
    badge.textContent = `${criticalCount} Critical`;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
                    <div style="padding: 40px; text-align: center; color: var(--text-secondary);">
                        <span style="font-size: 32px;">✅</span>
                        <p style="margin-top: 12px;">No active alerts</p>
                    </div>
                `;
        return;
    }

    container.innerHTML = alerts.slice(0, 5).map(alert => {
        const iconClass = alert.level === 'critical' ? 'critical' :
            alert.level === 'warning' ? 'warning' : 'info';
        const icon = alert.level === 'critical' ? '🔴' :
            alert.level === 'warning' ? '🟡' : 'ℹ️';
        return `
                    <div class="alert-item">
                        <div class="alert-icon ${iconClass}">${icon}</div>
                        <div class="alert-content">
                            <div class="alert-title">${alert.alert_type}</div>
                            <div class="alert-description">${alert.message}</div>
                        </div>
                        <div class="alert-time">${formatTime(alert.timestamp)}</div>
                    </div>
                `;
    }).join('');
}

function showMockData() {
    // Show demo data when API is unavailable
    updateRiskSummary({ risk_score: 42, overall_risk_level: 'MEDIUM' });

    updatePortfolioMetrics({
        var_95: -1250.50,
        var_99: -2100.75,
        sharpe_ratio: 1.85,
        sortino_ratio: 2.12,
        total_equity: 50000,
        total_exposure: 35000,
        unrealized_pnl: 1250.00,
        max_drawdown: 12.5,
        current_drawdown: 3.2,
        win_rate: 58.5
    });

    updatePositionHeatmap([
        { symbol: 'BTCUSDT', unrealized_pnl_pct: 5.2, risk_score: 25 },
        { symbol: 'ETHUSDT', unrealized_pnl_pct: -2.1, risk_score: 45 },
        { symbol: 'SOLUSDT', unrealized_pnl_pct: 12.5, risk_score: 65 },
        { symbol: 'BNBUSDT', unrealized_pnl_pct: -8.3, risk_score: 82 },
        { symbol: 'XRPUSDT', unrealized_pnl_pct: 3.1, risk_score: 30 },
        { symbol: 'ADAUSDT', unrealized_pnl_pct: -1.5, risk_score: 40 }
    ]);

    updateAlerts([
        {
            level: 'warning',
            alert_type: 'High Exposure',
            message: 'SOLUSDT position exceeds recommended size (15% of portfolio)',
            timestamp: new Date().toISOString()
        },
        {
            level: 'critical',
            alert_type: 'Stop Loss Triggered',
            message: 'BNBUSDT hit stop loss at $285.50',
            timestamp: new Date(Date.now() - 300000).toISOString()
        }
    ]);

    // Demo equity curve
    const labels = Array.from({ length: 30 }, (_, i) => `Day ${i + 1}`);
    const equity = Array.from({ length: 30 }, () => 45000 + Math.random() * 10000);
    const drawdown = Array.from({ length: 30 }, () => -(Math.random() * 15));

    equityChart.data.labels = labels;
    equityChart.data.datasets[0].data = equity;
    equityChart.data.datasets[1].data = drawdown;
    equityChart.update();
}

async function loadEquityData(period) {
    // Would fetch historical data based on period
    console.log('Loading equity data for period:', period);
}

// eslint-disable-next-line no-unused-vars
function showPositionDetails(symbol) {
    alert(`Position details for ${symbol}\n\nThis would open a detailed modal with position info.`);
}

// eslint-disable-next-line no-unused-vars
function exportReport() {
    alert('Generating PDF report...\n\nThis feature will export a comprehensive risk report.');
}

// Utility functions - using imported versions from utils.js
// formatCurrency, formatNumber, formatDate imported at top

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = (now - date) / 1000;

    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return date.toLocaleDateString();
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: initCharts, refreshData, updateConnectionStatus, updateRiskSummary, updatePortfolioMetrics

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.analyticsPage = {
        refreshData,
        exportReport
    };
    // Required for inline onclick handlers in analytics.html
    window.refreshData = refreshData;
    window.exportReport = exportReport;
}
