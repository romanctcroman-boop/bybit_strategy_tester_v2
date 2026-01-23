/**
 * 📄 Risk Management Page JavaScript
 * 
 * Page-specific scripts for risk_management.html
 * Extracted during Phase 1 Week 3: JS Extraction
 * 
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Data
        const alerts = [
            {
                severity: 'critical',
                message: 'Position size exceeds recommended limit',
                asset: 'BTCUSDT',
                details: 'Current position is 23% of portfolio (limit: 20%)',
                time: '5 minutes ago'
            },
            {
                severity: 'warning',
                message: 'High correlation detected',
                asset: 'ETH/BTC',
                details: 'Correlation of 0.85 exceeds threshold of 0.80',
                time: '15 minutes ago'
            },
            {
                severity: 'info',
                message: 'Approaching daily loss limit',
                asset: 'Portfolio',
                details: '75% of daily loss limit reached ($3,750 / $5,000)',
                time: '1 hour ago'
            }
        ];

        const correlationData = [
            ['', 'BTC', 'ETH', 'SOL', 'LINK'],
            ['BTC', 1.00, 0.85, 0.72, 0.65],
            ['ETH', 0.85, 1.00, 0.78, 0.70],
            ['SOL', 0.72, 0.78, 1.00, 0.55],
            ['LINK', 0.65, 0.70, 0.55, 1.00]
        ];

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initDrawdownChart();
            initVarChart();
            renderAlerts();
            renderCorrelationMatrix();
            updateProgressBars();
        });

        function initDrawdownChart() {
            const ctx = document.getElementById('drawdownChart').getContext('2d');
            
            const labels = [];
            const data = [];
            
            for (let i = 30; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
                
                // Simulate drawdown data
                data.push(-(Math.random() * 15 + 2));
            }

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Drawdown %',
                        data,
                        borderColor: '#f85149',
                        backgroundColor: 'rgba(248, 81, 73, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
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
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: { color: '#8b949e' }
                        },
                        y: {
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: {
                                color: '#8b949e',
                                callback: value => value + '%'
                            },
                            max: 0
                        }
                    }
                }
            });
        }

        function initVarChart() {
            const ctx = document.getElementById('varChart').getContext('2d');
            
            // Generate histogram data for VaR
            const bins = [];
            const counts = [];
            for (let i = -10; i <= 10; i++) {
                bins.push(`${i}%`);
                // Normal distribution approximation
                counts.push(Math.exp(-0.5 * Math.pow(i / 3, 2)) * 100);
            }

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: bins,
                    datasets: [{
                        label: 'Probability',
                        data: counts,
                        backgroundColor: bins.map(b => {
                            const val = parseFloat(b);
                            if (val < -5) return 'rgba(248, 81, 73, 0.8)';
                            if (val < 0) return 'rgba(210, 153, 34, 0.8)';
                            return 'rgba(63, 185, 80, 0.8)';
                        }),
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: items => `Return: ${items[0].label}`,
                                label: item => `Probability: ${item.parsed.y.toFixed(1)}%`
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#8b949e' }
                        },
                        y: {
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: { display: false }
                        }
                    }
                }
            });
        }

        function renderAlerts() {
            const tbody = document.getElementById('alertsTableBody');
            tbody.innerHTML = alerts.map(alert => `
                <tr>
                    <td>
                        <span class="alert-severity ${alert.severity}">
                            <i class="bi bi-${alert.severity === 'critical' ? 'exclamation-triangle' : alert.severity === 'warning' ? 'exclamation-circle' : 'info-circle'}"></i>
                            ${alert.severity.charAt(0).toUpperCase() + alert.severity.slice(1)}
                        </span>
                    </td>
                    <td>${alert.message}</td>
                    <td>${alert.asset}</td>
                    <td class="text-secondary">${alert.details}</td>
                    <td class="text-secondary">${alert.time}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="acknowledgeAlert()" title="Acknowledge">
                            <i class="bi bi-check"></i>
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="dismissAlert()" title="Dismiss">
                            <i class="bi bi-x"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        function renderCorrelationMatrix() {
            const container = document.getElementById('correlationMatrix');
            const size = correlationData.length;
            container.style.gridTemplateColumns = `repeat(${size}, 1fr)`;

            let html = '';
            for (let i = 0; i < size; i++) {
                for (let j = 0; j < size; j++) {
                    const value = correlationData[i][j];
                    let cellClass = 'neutral';
                    
                    if (i === 0 || j === 0) {
                        cellClass = 'header';
                    } else if (typeof value === 'number') {
                        if (value > 0.8) cellClass = 'positive-high';
                        else if (value > 0.5) cellClass = 'positive-medium';
                        else if (value < -0.5) cellClass = 'negative-medium';
                        else if (value < -0.8) cellClass = 'negative-high';
                    }

                    const display = typeof value === 'number' ? value.toFixed(2) : value;
                    html += `<div class="correlation-cell ${cellClass}">${display}</div>`;
                }
            }
            container.innerHTML = html;
        }

        function updateProgressBars() {
            document.getElementById('positionSizeBar').style.width = '72%';
            document.getElementById('dailyLossBar').style.width = '25%';
            document.getElementById('leverageBar').style.width = '64%';
            document.getElementById('correlationBar').style.width = '90%';
        }

        function acknowledgeAlert() {
            alert('Alert acknowledged');
        }

        function dismissAlert() {
            alert('Alert dismissed');
        }

        function exportReport() {
            alert('Exporting risk report...');
        }

        function openSettingsModal() {
            alert('Opening settings...');
        }

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: initDrawdownChart, initVarChart, renderAlerts, renderCorrelationMatrix, updateProgressBars

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.riskmanagementPage = {
        // Add public methods here
    };
}
