/**
 * 📄 Portfolio Page JavaScript
 *
 * Page-specific scripts for portfolio.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
// eslint-disable-next-line no-unused-vars
import { apiClient, API_CONFIG } from '../api.js';
// eslint-disable-next-line no-unused-vars
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Portfolio Data
const holdings = [
    {
        symbol: 'BTCUSDT',
        name: 'Bitcoin',
        icon: 'btc',
        amount: 1.2345,
        avgPrice: 42500,
        currentPrice: 44250,
        value: 54640.625,
        pnl: 2160.625,
        pnlPercent: 4.12
    },
    {
        symbol: 'ETHUSDT',
        name: 'Ethereum',
        icon: 'eth',
        amount: 15.5,
        avgPrice: 2250,
        currentPrice: 2480,
        value: 38440,
        pnl: 3565,
        pnlPercent: 10.22
    },
    {
        symbol: 'SOLUSDT',
        name: 'Solana',
        icon: 'sol',
        amount: 125,
        avgPrice: 95,
        currentPrice: 108.5,
        value: 13562.5,
        pnl: 1687.5,
        pnlPercent: 14.21
    },
    {
        symbol: 'USDT',
        name: 'Tether',
        icon: 'usdt',
        amount: 18789.375,
        avgPrice: 1,
        currentPrice: 1,
        value: 18789.375,
        pnl: 0,
        pnlPercent: 0
    }
];

const recentTrades = [
    { type: 'buy', symbol: 'BTCUSDT', amount: 0.25, price: 44150, time: '10 minutes ago', pnl: null },
    { type: 'sell', symbol: 'ETHUSDT', amount: 2.5, price: 2485, time: '45 minutes ago', pnl: 245.50 },
    { type: 'buy', symbol: 'SOLUSDT', amount: 25, price: 107.20, time: '2 hours ago', pnl: null },
    { type: 'sell', symbol: 'BTCUSDT', amount: 0.15, price: 43980, time: '5 hours ago', pnl: 156.30 }
];

const allocationColors = ['#f7931a', '#627eea', '#9945ff', '#26a17b', '#58a6ff'];

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    renderHoldingsTable();
    renderRecentTrades();
    initPerformanceChart();
    initAllocationChart();
});

function renderHoldingsTable() {
    const tbody = document.getElementById('holdingsTableBody');
    tbody.innerHTML = holdings.map(h => `
                <tr>
                    <td>
                        <div class="asset-info">
                            <div class="asset-icon ${h.icon}">${h.symbol.slice(0, 1)}</div>
                            <div class="asset-details">
                                <span class="asset-name">${h.name}</span>
                                <span class="asset-symbol">${h.symbol}</span>
                            </div>
                        </div>
                    </td>
                    <td>${h.amount.toLocaleString()}</td>
                    <td>$${h.avgPrice.toLocaleString()}</td>
                    <td>$${h.currentPrice.toLocaleString()}</td>
                    <td class="value-cell">
                        <div class="value-main">$${h.value.toLocaleString()}</div>
                    </td>
                    <td class="value-cell">
                        <div class="value-main ${h.pnl >= 0 ? 'change-positive' : 'change-negative'}">
                            ${h.pnl >= 0 ? '+' : ''}$${h.pnl.toLocaleString()}
                        </div>
                        <div class="value-sub ${h.pnlPercent >= 0 ? 'change-positive' : 'change-negative'}">
                            ${h.pnlPercent >= 0 ? '+' : ''}${h.pnlPercent.toFixed(2)}%
                        </div>
                    </td>
                    <td>
                        <div class="d-flex gap-1">
                            <button class="btn btn-secondary btn-sm" onclick="trade('${h.symbol}', 'buy')" title="Buy">
                                <i class="bi bi-plus"></i>
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="trade('${h.symbol}', 'sell')" title="Sell">
                                <i class="bi bi-dash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
}

function renderRecentTrades() {
    const container = document.getElementById('recentTrades');
    container.innerHTML = recentTrades.map(t => `
                <div class="trade-item">
                    <div class="trade-icon ${t.type}">
                        <i class="bi bi-arrow-${t.type === 'buy' ? 'down' : 'up'}-circle"></i>
                    </div>
                    <div class="trade-info">
                        <div class="trade-title">${t.type === 'buy' ? 'Bought' : 'Sold'} ${t.amount} ${t.symbol}</div>
                        <div class="trade-time">@ $${t.price.toLocaleString()} • ${t.time}</div>
                    </div>
                    <div class="trade-amount">
                        <div class="trade-value">$${(t.amount * t.price).toLocaleString()}</div>
                        ${t.pnl !== null ? `
                            <div class="trade-pnl ${t.pnl >= 0 ? 'change-positive' : 'change-negative'}">
                                ${t.pnl >= 0 ? '+' : ''}$${t.pnl.toLocaleString()}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `).join('');
}

function initPerformanceChart() {
    const ctx = document.getElementById('performanceChart').getContext('2d');

    // Generate sample data
    const labels = [];
    const data = [];
    let value = 100000;

    for (let i = 30; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

        value += (Math.random() - 0.4) * 2000;
        data.push(value);
    }

    new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Portfolio Value',
                data,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    titleColor: '#f0f6fc',
                    bodyColor: '#8b949e',
                    callbacks: {
                        label: function (context) {
                            return '$' + context.parsed.y.toLocaleString();
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(48, 54, 61, 0.5)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(48, 54, 61, 0.5)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e',
                        callback: function (value) {
                            return '$' + (value / 1000).toFixed(0) + 'K';
                        }
                    }
                }
            }
        }
    });
}

function initAllocationChart() {
    const ctx = document.getElementById('allocationChart').getContext('2d');
    const total = holdings.reduce((sum, h) => sum + h.value, 0);

    const data = holdings.map(h => ({
        label: h.symbol,
        value: h.value,
        percent: (h.value / total * 100).toFixed(1)
    }));

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.label),
            datasets: [{
                data: data.map(d => d.value),
                backgroundColor: allocationColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });

    // Render legend
    const legend = document.getElementById('allocationLegend');
    legend.innerHTML = data.map((d, i) => `
                <div class="legend-item">
                    <span class="legend-label">
                        <span class="legend-color" style="background: ${allocationColors[i]}"></span>
                        ${d.label}
                    </span>
                    <span class="legend-value">${d.percent}%</span>
                </div>
            `).join('');
}

function setTimeRange(range) {
    // Update active tab
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent === range);
    });

    // Would reload chart data here
    console.log('Set time range:', range);
}

function refreshPortfolio() {
    document.getElementById('lastUpdate').innerHTML = '<i class="bi bi-clock"></i> Updated: Just now';
    renderHoldingsTable();
    renderRecentTrades();
}

function exportPortfolio() {
    alert('Exporting portfolio data...');
}

function openTradeModal() {
    alert('Opening trade modal...');
}

// eslint-disable-next-line no-unused-vars
function trade(symbol, type) {
    alert(`${type === 'buy' ? 'Buy' : 'Sell'} ${symbol}`);
}

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: renderHoldingsTable, renderRecentTrades, initPerformanceChart, initAllocationChart, setTimeRange

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.portfolioPage = {
        // Add public methods here
    };

    // onclick handler exports (required for auto-event-binding.js with type="module")
    window.refreshPortfolio = refreshPortfolio;
    window.exportPortfolio = exportPortfolio;
    window.openTradeModal = openTradeModal;
    window.setTimeRange = setTimeRange;
    window.trade = trade;
}
