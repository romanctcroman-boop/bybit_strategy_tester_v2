/**
 * 🧭 Navigation Component - Bybit Strategy Tester v2
 *
 * Unified navigation component that can be included across all pages.
 * Eliminates code duplication and ensures consistent navigation.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// ============================================
// NAVIGATION CONFIGURATION
// ============================================

const NAVIGATION_CONFIG = {
    brand: {
        name: 'Bybit Strategy Tester v2',
        logo: '/frontend/assets/logo.svg', // Optional logo
        href: '/frontend/dashboard.html'
    },

    // Main navigation items
    menuItems: [
        {
            id: 'dashboard',
            label: 'Dashboard',
            icon: 'bi-speedometer2',
            href: '/frontend/dashboard.html',
            description: 'Main dashboard with system overview'
        },
        {
            id: 'trading',
            label: 'Trading',
            icon: 'bi-graph-up',
            dropdown: true,
            items: [
                { id: 'market-chart', label: 'Market Chart', icon: 'bi-bar-chart-line', href: '/frontend/market-chart.html' },
                { id: 'trading-panel', label: 'Trading Panel', icon: 'bi-lightning', href: '/frontend/trading-panel.html' },
                { id: 'orders', label: 'Orders', icon: 'bi-list-task', href: '/frontend/orders.html' },
                { id: 'positions', label: 'Positions', icon: 'bi-wallet2', href: '/frontend/positions.html' }
            ]
        },
        {
            id: 'strategies',
            label: 'Strategies',
            icon: 'bi-gear',
            dropdown: true,
            items: [
                { id: 'strategy-builder', label: 'Strategy Builder', icon: 'bi-tools', href: '/frontend/strategy-builder.html' },
                { id: 'strategy-library', label: 'Strategy Library', icon: 'bi-collection', href: '/frontend/strategy-library.html' },
                { id: 'backtesting', label: 'Backtesting', icon: 'bi-clock-history', href: '/frontend/backtesting.html' },
                { id: 'risk-management', label: 'Risk Management', icon: 'bi-shield-check', href: '/frontend/risk-management.html' }
            ]
        },
        {
            id: 'analytics',
            label: 'Analytics',
            icon: 'bi-pie-chart',
            dropdown: true,
            items: [
                { id: 'portfolio', label: 'Portfolio', icon: 'bi-briefcase', href: '/frontend/portfolio.html' },
                { id: 'performance', label: 'Performance', icon: 'bi-trophy', href: '/frontend/performance.html' },
                { id: 'reports', label: 'Reports', icon: 'bi-file-earmark-text', href: '/frontend/reports.html' }
            ]
        },
        {
            id: 'settings',
            label: 'Settings',
            icon: 'bi-sliders',
            href: '/frontend/settings.html',
            description: 'Application settings'
        }
    ],

    // Right-side items (status indicators, user menu, etc.)
    rightItems: [
        {
            id: 'connection-status',
            type: 'status',
            label: 'API Status',
            icon: 'bi-wifi'
        },
        {
            id: 'notifications',
            type: 'button',
            icon: 'bi-bell',
            badge: true
        },
        {
            id: 'theme-toggle',
            type: 'toggle',
            icon: 'bi-moon',
            altIcon: 'bi-sun'
        }
    ]
};

// ============================================
// NAVIGATION RENDERER
// ============================================

class Navigation {
    constructor(config = NAVIGATION_CONFIG) {
        this.config = config;
        this.container = null;
        this.currentPage = this.detectCurrentPage();
    }

    /**
     * Detect current page from URL
     */
    detectCurrentPage() {
        const path = window.location.pathname;
        const filename = path.split('/').pop().replace('.html', '');
        return filename || 'dashboard';
    }

    /**
     * Check if menu item is active
     */
    isActive(item) {
        if (item.id === this.currentPage) return true;
        if (item.items) {
            return item.items.some(sub => sub.id === this.currentPage);
        }
        return false;
    }

    /**
     * Render navigation to container
     */
    render(containerId = 'navigation') {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Navigation container #${containerId} not found`);
            return;
        }

        this.container.innerHTML = this.generateNavHTML();
        this.attachEventListeners();
        this.initializeTheme();
    }

    /**
     * Generate navigation HTML
     */
    generateNavHTML() {
        return `
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <div class="container-fluid">
                ${this.renderBrand()}
                
                <button class="navbar-toggler" type="button" 
                        data-bs-toggle="collapse" 
                        data-bs-target="#navbarContent"
                        aria-controls="navbarContent" 
                        aria-expanded="false" 
                        aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                
                <div class="collapse navbar-collapse" id="navbarContent">
                    <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                        ${this.renderMenuItems()}
                    </ul>
                    
                    <div class="d-flex align-items-center gap-3">
                        ${this.renderRightItems()}
                    </div>
                </div>
            </div>
        </nav>
        `;
    }

    /**
     * Render brand/logo
     */
    renderBrand() {
        const { brand } = this.config;
        return `
        <a class="navbar-brand d-flex align-items-center" href="${brand.href}">
            <i class="bi bi-graph-up-arrow me-2" style="font-size: 1.5rem;"></i>
            <span class="d-none d-sm-inline">${brand.name}</span>
        </a>
        `;
    }

    /**
     * Render main menu items
     */
    renderMenuItems() {
        return this.config.menuItems.map(item => {
            if (item.dropdown) {
                return this.renderDropdownItem(item);
            }
            return this.renderSingleItem(item);
        }).join('');
    }

    /**
     * Render single navigation item
     */
    renderSingleItem(item) {
        const activeClass = this.isActive(item) ? 'active' : '';
        return `
        <li class="nav-item">
            <a class="nav-link ${activeClass}" href="${item.href}" 
               ${item.description ? `title="${item.description}"` : ''}>
                <i class="bi ${item.icon} me-1"></i>
                ${item.label}
            </a>
        </li>
        `;
    }

    /**
     * Render dropdown menu item
     */
    renderDropdownItem(item) {
        const activeClass = this.isActive(item) ? 'active' : '';
        const subItems = item.items.map(sub => {
            const subActive = sub.id === this.currentPage ? 'active' : '';
            return `
            <li>
                <a class="dropdown-item ${subActive}" href="${sub.href}">
                    <i class="bi ${sub.icon} me-2"></i>
                    ${sub.label}
                </a>
            </li>
            `;
        }).join('');

        return `
        <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle ${activeClass}" href="#" 
               id="nav-${item.id}" 
               role="button" 
               data-bs-toggle="dropdown" 
               aria-expanded="false">
                <i class="bi ${item.icon} me-1"></i>
                ${item.label}
            </a>
            <ul class="dropdown-menu dropdown-menu-dark" aria-labelledby="nav-${item.id}">
                ${subItems}
            </ul>
        </li>
        `;
    }

    /**
     * Render right-side items (status, theme toggle, etc.)
     */
    renderRightItems() {
        return this.config.rightItems.map(item => {
            switch (item.type) {
            case 'status':
                return this.renderStatusIndicator(item);
            case 'button':
                return this.renderIconButton(item);
            case 'toggle':
                return this.renderThemeToggle(item);
            default:
                return '';
            }
        }).join('');
    }

    /**
     * Render status indicator
     */
    renderStatusIndicator(item) {
        return `
        <div class="nav-status d-flex align-items-center" id="${item.id}">
            <i class="bi ${item.icon} me-1"></i>
            <span class="badge bg-secondary" id="${item.id}-badge">Connecting...</span>
        </div>
        `;
    }

    /**
     * Render icon button
     */
    renderIconButton(item) {
        return `
        <button class="btn btn-outline-light btn-sm position-relative" 
                id="${item.id}"
                title="${item.label || item.id}">
            <i class="bi ${item.icon}"></i>
            ${item.badge ? `<span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger d-none" id="${item.id}-count">0</span>` : ''}
        </button>
        `;
    }

    /**
     * Render theme toggle button
     */
    renderThemeToggle(item) {
        return `
        <button class="btn btn-outline-light btn-sm" 
                id="${item.id}"
                title="Toggle theme">
            <i class="bi ${item.icon}" id="${item.id}-icon"></i>
        </button>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Notifications button
        const notificationsBtn = document.getElementById('notifications');
        if (notificationsBtn) {
            notificationsBtn.addEventListener('click', () => this.showNotifications());
        }
    }

    /**
     * Initialize theme from localStorage
     */
    initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
    }

    /**
     * Toggle between light and dark themes
     */
    toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const newTheme = current === 'dark' ? 'light' : 'dark';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('themeChange', { detail: { theme: newTheme } }));
    }

    /**
     * Update theme toggle icon
     */
    updateThemeIcon(theme) {
        const icon = document.getElementById('theme-toggle-icon');
        if (icon) {
            icon.className = theme === 'dark' ? 'bi bi-moon' : 'bi bi-sun';
        }
    }

    /**
     * Update connection status
     */
    updateConnectionStatus(status, message = '') {
        const badge = document.getElementById('connection-status-badge');
        if (!badge) return;

        const statusConfig = {
            connected: { class: 'bg-success', text: 'Connected' },
            connecting: { class: 'bg-warning', text: 'Connecting...' },
            disconnected: { class: 'bg-danger', text: 'Disconnected' },
            error: { class: 'bg-danger', text: 'Error' }
        };

        const config = statusConfig[status] || statusConfig.disconnected;
        badge.className = `badge ${config.class}`;
        badge.textContent = message || config.text;
    }

    /**
     * Update notification badge
     */
    updateNotificationBadge(count) {
        const badge = document.getElementById('notifications-count');
        if (!badge) return;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }

    /**
     * Show notifications panel (placeholder)
     */
    showNotifications() {
        console.log('Show notifications panel');
        // TODO: Implement notifications panel
    }
}

// ============================================
// AUTO-INITIALIZE
// ============================================

// Create global instance
const navigation = new Navigation();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Only auto-render if container exists
        if (document.getElementById('navigation')) {
            navigation.render();
        }
    });
} else {
    if (document.getElementById('navigation')) {
        navigation.render();
    }
}

// ============================================
// EXPORTS
// ============================================

export { Navigation, NAVIGATION_CONFIG };

// Attach to window
if (typeof window !== 'undefined') {
    window.Navigation = Navigation;
    window.navigation = navigation;
}
