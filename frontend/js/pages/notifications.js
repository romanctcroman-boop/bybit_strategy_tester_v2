/**
 * 📄 Notifications Page JavaScript
 * 
 * Page-specific scripts for notifications.html
 * Extracted during Phase 1 Week 3: JS Extraction
 * 
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Sample notification data
        const notifications = [
            {
                id: 1,
                type: 'price',
                title: 'Price Alert: BTCUSDT',
                message: 'BTC crossed above $97,500. Your price alert has been triggered.',
                time: '2 minutes ago',
                unread: true,
                actions: ['View Chart', 'Dismiss']
            },
            {
                id: 2,
                type: 'trade',
                title: 'Order Executed',
                message: 'Your limit buy order for 0.5 ETH at $3,450 has been filled.',
                time: '15 minutes ago',
                unread: true,
                actions: ['View Trade', 'Dismiss']
            },
            {
                id: 3,
                type: 'strategy',
                title: 'Backtest Complete',
                message: 'Your "Momentum RSI" strategy backtest has completed. Win rate: 67.5%',
                time: '1 hour ago',
                unread: true,
                actions: ['View Results', 'Dismiss']
            },
            {
                id: 4,
                type: 'alert',
                title: 'Risk Warning',
                message: 'Portfolio drawdown has exceeded 10%. Consider reviewing your positions.',
                time: '2 hours ago',
                unread: true,
                actions: ['View Portfolio', 'Dismiss']
            },
            {
                id: 5,
                type: 'system',
                title: 'System Update',
                message: 'New ML model version available. Enhanced prediction accuracy by 15%.',
                time: '3 hours ago',
                unread: false,
                actions: ['Update Now', 'Later']
            },
            {
                id: 6,
                type: 'price',
                title: 'Price Alert: ETHUSDT',
                message: 'ETH dropped below $3,400. Price alert triggered.',
                time: '5 hours ago',
                unread: false,
                actions: ['View Chart', 'Dismiss']
            },
            {
                id: 7,
                type: 'trade',
                title: 'Stop Loss Triggered',
                message: 'Stop loss order executed for SOLUSDT position at $195.50.',
                time: '1 day ago',
                unread: false,
                actions: ['View Trade', 'Dismiss']
            }
        ];

        const alerts = [
            { symbol: 'BTCUSDT', condition: 'Above', targetPrice: 100000, currentPrice: 97234.50, status: 'active', channels: ['push', 'email'] },
            { symbol: 'ETHUSDT', condition: 'Below', targetPrice: 3300, currentPrice: 3456.78, status: 'active', channels: ['push'] },
            { symbol: 'SOLUSDT', condition: 'Above', targetPrice: 200, currentPrice: 198.45, status: 'active', channels: ['push', 'telegram'] },
            { symbol: 'BTCUSDT', condition: 'Below', targetPrice: 95000, currentPrice: 97234.50, status: 'active', channels: ['push', 'email', 'telegram'] },
            { symbol: 'DOGEUSDT', condition: 'Above', targetPrice: 0.35, currentPrice: 0.32, status: 'triggered', channels: ['push'] },
        ];

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            renderNotifications();
            renderAlerts();
            setupTabs();
        });

        function renderNotifications() {
            const container = document.getElementById('notificationList');
            container.innerHTML = notifications.map(n => `
                <div class="notification-card ${n.unread ? 'unread' : ''}">
                    <div class="notification-icon ${n.type}">
                        <i class="bi bi-${getIconForType(n.type)}"></i>
                    </div>
                    <div class="notification-content">
                        <div class="notification-header">
                            <span class="notification-title">${n.title}</span>
                            <span class="notification-time">${n.time}</span>
                        </div>
                        <div class="notification-message">${n.message}</div>
                        <div class="notification-actions">
                            ${n.actions.map((action, i) => `
                                <button class="notification-btn ${i === 0 ? 'primary' : 'secondary'}" 
                                        onclick="handleAction('${action}', ${n.id})">
                                    ${action}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function renderAlerts() {
            const tbody = document.getElementById('alertsTableBody');
            tbody.innerHTML = alerts.map(a => `
                <tr>
                    <td><strong>${a.symbol}</strong></td>
                    <td>${a.condition}</td>
                    <td>$${a.targetPrice.toLocaleString()}</td>
                    <td>$${a.currentPrice.toLocaleString()}</td>
                    <td>
                        <span class="alert-status ${a.status}">
                            <span class="status-dot"></span>
                            ${a.status.charAt(0).toUpperCase() + a.status.slice(1)}
                        </span>
                    </td>
                    <td>
                        <div class="channels">
                            ${a.channels.map(c => `
                                <span class="channel-icon active" title="${c}">
                                    <i class="bi bi-${getChannelIcon(c)}"></i>
                                </span>
                            `).join('')}
                        </div>
                    </td>
                    <td>
                        <button class="notification-btn secondary" onclick="editAlert('${a.symbol}')">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="notification-btn secondary ml-4" onclick="deleteAlert('${a.symbol}')">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        function getIconForType(type) {
            const icons = {
                'price': 'graph-up-arrow',
                'trade': 'currency-exchange',
                'alert': 'exclamation-triangle',
                'system': 'gear',
                'strategy': 'lightbulb'
            };
            return icons[type] || 'bell';
        }

        function getChannelIcon(channel) {
            const icons = {
                'push': 'bell',
                'email': 'envelope',
                'telegram': 'telegram',
                'discord': 'discord'
            };
            return icons[channel] || 'bell';
        }

        function setupTabs() {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    
                    btn.classList.add('active');
                    document.getElementById(`${btn.dataset.tab}-tab`).classList.add('active');
                });
            });
        }

        function toggleSetting(el) {
            el.classList.toggle('active');
        }

        function markAllAsRead() {
            notifications.forEach(n => n.unread = false);
            renderNotifications();
            document.querySelector('.tab-badge').style.display = 'none';
        }

        function showCreateAlert() {
            alert('Create Alert modal would open here');
        }

        function handleAction(action, id) {
            console.log(`Action: ${action} for notification ${id}`);
            if (action === 'Dismiss') {
                const index = notifications.findIndex(n => n.id === id);
                if (index !== -1) {
                    notifications.splice(index, 1);
                    renderNotifications();
                }
            }
        }

        function editAlert(symbol) {
            alert(`Edit alert for ${symbol}`);
        }

        function deleteAlert(symbol) {
            if (confirm(`Delete alert for ${symbol}?`)) {
                const index = alerts.findIndex(a => a.symbol === symbol);
                if (index !== -1) {
                    alerts.splice(index, 1);
                    renderAlerts();
                }
            }
        }

        function connectTelegram() {
            alert('Telegram bot connection wizard would open here');
        }

        function configureDiscord() {
            alert('Discord webhook configuration would open here');
        }

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: renderNotifications, renderAlerts, getIconForType, getChannelIcon, setupTabs

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.notificationsPage = {
        // Add public methods here
    };
}
