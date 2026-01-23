/**
 * 📄 Analytics Advanced Page JavaScript
 * 
 * Page-specific scripts for analytics_advanced.html
 * Extracted during Phase 1 Week 3: JS Extraction
 * 
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Chart.js defaults
        Chart.defaults.color = '#8b949e';
        Chart.defaults.borderColor = '#30363d';

        // Equity Curve Chart
        const equityCtx = document.getElementById('equityCurveChart').getContext('2d');
        const equityData = {
            labels: Array.from({length: 30}, (_, i) => `Day ${i + 1}`),
            datasets: [{
                label: 'Portfolio Value',
                data: [10000, 10250, 10180, 10420, 10650, 10580, 10820, 11050, 10980, 11200,
                       11450, 11380, 11620, 11850, 11780, 12020, 12250, 12180, 12420, 12650,
                       12580, 12820, 13050, 12980, 13200, 13450, 13380, 13620, 13850, 14782],
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6
            }, {
                label: 'Benchmark (Buy & Hold)',
                data: [10000, 10100, 10050, 10200, 10350, 10300, 10450, 10600, 10550, 10700,
                       10850, 10800, 10950, 11100, 11050, 11200, 11350, 11300, 11450, 11600,
                       11550, 11700, 11850, 11800, 11950, 12100, 12050, 12200, 12350, 12500],
                borderColor: '#8b949e',
                borderDash: [5, 5],
                fill: false,
                tension: 0.4,
                pointRadius: 0
            }]
        };
        new Chart(equityCtx, {
            type: 'line',
            data: equityData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(48, 54, 61, 0.5)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        // Returns Distribution Chart
        const returnsCtx = document.getElementById('returnsDistChart').getContext('2d');
        new Chart(returnsCtx, {
            type: 'bar',
            data: {
                labels: ['<-5%', '-5% to -3%', '-3% to -1%', '-1% to 0%', '0% to 1%', '1% to 3%', '3% to 5%', '>5%'],
                datasets: [{
                    label: 'Trade Count',
                    data: [12, 45, 128, 234, 312, 287, 156, 42],
                    backgroundColor: [
                        'rgba(248, 81, 73, 0.8)',
                        'rgba(248, 81, 73, 0.6)',
                        'rgba(248, 81, 73, 0.4)',
                        'rgba(248, 81, 73, 0.2)',
                        'rgba(63, 185, 80, 0.2)',
                        'rgba(63, 185, 80, 0.4)',
                        'rgba(63, 185, 80, 0.6)',
                        'rgba(63, 185, 80, 0.8)'
                    ],
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(48, 54, 61, 0.5)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        // Drawdown Chart
        const ddCtx = document.getElementById('drawdownChart').getContext('2d');
        const drawdownData = [0, -0.5, -1.2, -0.8, -0.3, -1.5, -2.1, -1.8, -0.9, -0.4,
                              -2.5, -3.2, -4.1, -5.2, -6.8, -8.4, -7.2, -5.8, -4.2, -3.1,
                              -2.4, -1.8, -1.2, -0.6, -1.4, -2.1, -1.5, -0.8, -0.3, -2.1];
        new Chart(ddCtx, {
            type: 'line',
            data: {
                labels: Array.from({length: 30}, (_, i) => `Day ${i + 1}`),
                datasets: [{
                    label: 'Drawdown %',
                    data: drawdownData,
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248, 81, 73, 0.2)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        max: 0,
                        grid: {
                            color: 'rgba(48, 54, 61, 0.5)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        // Hourly Distribution Chart
        const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
        new Chart(hourlyCtx, {
            type: 'bar',
            data: {
                labels: ['0', '2', '4', '6', '8', '10', '12', '14', '16', '18', '20', '22'],
                datasets: [{
                    label: 'Trades',
                    data: [45, 32, 28, 52, 78, 125, 156, 142, 168, 134, 89, 56],
                    backgroundColor: 'rgba(88, 166, 255, 0.6)',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { display: false },
                    x: { grid: { display: false } }
                }
            }
        });

        // Daily Distribution Chart
        const dailyCtx = document.getElementById('dailyChart').getContext('2d');
        new Chart(dailyCtx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'P&L',
                    data: [2450, 1820, 3120, -580, 1950, 890, 1240],
                    backgroundColor: function(context) {
                        return context.raw >= 0 ? 'rgba(63, 185, 80, 0.6)' : 'rgba(248, 81, 73, 0.6)';
                    },
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { display: false },
                    x: { grid: { display: false } }
                }
            }
        });

        // Symbol Distribution Chart
        const symbolCtx = document.getElementById('symbolChart').getContext('2d');
        new Chart(symbolCtx, {
            type: 'doughnut',
            data: {
                labels: ['BTC', 'ETH', 'SOL', 'XRP', 'Others'],
                datasets: [{
                    data: [35, 28, 18, 12, 7],
                    backgroundColor: [
                        '#f7931a',
                        '#627eea',
                        '#00ffa3',
                        '#23292f',
                        '#8b949e'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 12,
                            padding: 8
                        }
                    }
                },
                cutout: '60%'
            }
        });

        // Mini Charts for Strategy Comparison
        function createMiniChart(canvasId, data, color) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data,
                    datasets: [{
                        data: data,
                        borderColor: color,
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 0
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

        createMiniChart('miniChart1', [10, 12, 11, 14, 13, 16, 18, 17, 20, 22, 24], '#58a6ff');
        createMiniChart('miniChart2', [10, 11, 10, 12, 11, 13, 12, 14, 15, 17, 18], '#a371f7');
        createMiniChart('miniChart3', [10, 13, 12, 15, 18, 17, 20, 19, 22, 28, 31], '#3fb950');
        createMiniChart('miniChart4', [10, 10, 11, 11, 11, 12, 12, 11, 12, 12, 12], '#f0883e');

        // Generate Heatmap
        function generateHeatmap() {
            const grid = document.getElementById('heatmapGrid');
            const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const years = ['2024', '2025'];
            
            const performanceData = {
                '2024': [4.2, -1.5, 2.8, 5.1, -2.3, 3.7, 6.2, -0.8, 4.5, 7.1, 3.2, 5.8],
                '2025': [6.4, 4.8, -1.2, 3.5, 2.9, 5.2, 0, 0, 0, 0, 0, 0]
            };

            // Header row
            months.forEach(month => {
                const cell = document.createElement('div');
                cell.className = 'heatmap-label';
                cell.textContent = month;
                cell.style.justifyContent = month ? 'center' : 'flex-end';
                cell.style.paddingRight = month ? '0' : '8px';
                grid.appendChild(cell);
            });

            // Data rows
            years.forEach(year => {
                const yearLabel = document.createElement('div');
                yearLabel.className = 'heatmap-label';
                yearLabel.textContent = year;
                yearLabel.style.justifyContent = 'flex-end';
                yearLabel.style.paddingRight = '8px';
                grid.appendChild(yearLabel);

                performanceData[year].forEach((value, idx) => {
                    const cell = document.createElement('div');
                    cell.className = 'heatmap-cell';
                    
                    if (value === 0) {
                        cell.classList.add('neutral');
                    } else if (value > 5) {
                        cell.classList.add('profit-high');
                        cell.textContent = `+${value}%`;
                    } else if (value > 2) {
                        cell.classList.add('profit-medium');
                        cell.textContent = `+${value}%`;
                    } else if (value > 0) {
                        cell.classList.add('profit-low');
                        cell.textContent = `+${value}%`;
                    } else if (value > -2) {
                        cell.classList.add('loss-low');
                        cell.textContent = `${value}%`;
                    } else if (value > -5) {
                        cell.classList.add('loss-medium');
                        cell.textContent = `${value}%`;
                    } else {
                        cell.classList.add('loss-high');
                        cell.textContent = `${value}%`;
                    }
                    
                    cell.title = `${months[idx + 1]} ${year}: ${value > 0 ? '+' : ''}${value}%`;
                    grid.appendChild(cell);
                });
            });
        }

        generateHeatmap();

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.tab').forEach(t => {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                this.classList.add('active');
                this.setAttribute('aria-selected', 'true');
            });
        });

        // Chart period buttons
        document.querySelectorAll('.chart-controls').forEach(controls => {
            controls.querySelectorAll('.chart-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    controls.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                });
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === 'r' && !e.ctrlKey && !e.metaKey) {
                // Refresh data
                console.log('Refreshing data...');
            }
            if (e.key === 'Escape') {
                // Close any open modals
            }
        });

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: createMiniChart, generateHeatmap

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.analyticsadvancedPage = {
        // Add public methods here
    };
}
