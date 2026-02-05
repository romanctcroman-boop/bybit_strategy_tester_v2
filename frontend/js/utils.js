/**
 * 🛠️ Utilities - Bybit Strategy Tester v2
 *
 * Common utility functions for formatting, validation, and helpers.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// ============================================
// NUMBER FORMATTING
// ============================================

/**
 * Format number with thousands separator
 * @param {number} value - Number to format
 * @param {number} decimals - Decimal places
 * @returns {string} Formatted number
 */
function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '—';
    }
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

/**
 * Format currency value
 * @param {number} value - Amount
 * @param {string} currency - Currency code (USD, USDT, BTC)
 * @returns {string} Formatted currency
 */
function formatCurrency(value, currency = 'USD') {
    if (value === null || value === undefined || isNaN(value)) {
        return '—';
    }

    const symbols = {
        USD: '$',
        USDT: '$',
        BTC: '₿',
        ETH: 'Ξ'
    };

    const symbol = symbols[currency] || '';
    const absValue = Math.abs(value);

    // Use compact notation for large numbers
    if (absValue >= 1000000) {
        return `${symbol}${(value / 1000000).toFixed(2)}M`;
    }
    if (absValue >= 1000) {
        return `${symbol}${(value / 1000).toFixed(2)}K`;
    }

    return `${symbol}${formatNumber(value, 2)}`;
}

/**
 * Format percentage
 * @param {number} value - Percentage value (0.05 = 5%)
 * @param {boolean} includeSign - Include + for positive
 * @returns {string} Formatted percentage
 */
function formatPercent(value, includeSign = true) {
    if (value === null || value === undefined || isNaN(value)) {
        return '—';
    }

    const percent = value * 100;
    const sign = includeSign && percent > 0 ? '+' : '';
    return `${sign}${percent.toFixed(2)}%`;
}

/**
 * Format price with appropriate decimals
 * @param {number} price - Price value
 * @param {string} _symbol - Trading symbol (reserved for future use)
 * @returns {string} Formatted price
 */
function formatPrice(price, _symbol = '') {
    if (price === null || price === undefined || isNaN(price)) {
        return '—';
    }

    // Determine decimals based on price magnitude
    let decimals = 2;
    if (price < 0.0001) decimals = 8;
    else if (price < 0.01) decimals = 6;
    else if (price < 1) decimals = 4;
    else if (price < 100) decimals = 2;
    else decimals = 2;

    return formatNumber(price, decimals);
}

// ============================================
// DATE/TIME FORMATTING
// ============================================

/**
 * Format date/time
 * @param {Date|string|number} date - Date input
 * @param {string} format - Format type: 'date', 'time', 'datetime', 'relative'
 * @returns {string} Formatted date
 */
function formatDate(date, format = 'datetime') {
    if (!date) return '—';

    const d = new Date(date);
    if (isNaN(d.getTime())) return '—';

    switch (format) {
    case 'date':
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });

    case 'time':
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

    case 'datetime':
        return d.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });

    case 'relative':
        return formatRelativeTime(d);

    default:
        return d.toISOString();
    }
}

/**
 * Format relative time (e.g., "5 minutes ago")
 * @param {Date} date - Date to compare
 * @returns {string} Relative time string
 */
function formatRelativeTime(date) {
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return formatDate(date, 'date');
}

// ============================================
// DOM UTILITIES
// ============================================

/**
 * Safely query DOM element
 * @param {string} selector - CSS selector
 * @param {Element} parent - Parent element
 * @returns {Element|null} Found element
 */
function $(selector, parent = document) {
    return parent.querySelector(selector);
}

/**
 * Query all DOM elements
 * @param {string} selector - CSS selector
 * @param {Element} parent - Parent element
 * @returns {Element[]} Found elements
 */
function $$(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
}

/**
 * Create element with attributes
 * @param {string} tag - Element tag
 * @param {Object} attrs - Attributes
 * @param {string|Element[]} children - Child content
 * @returns {Element} Created element
 */
function createElement(tag, attrs = {}, children = null) {
    const el = document.createElement(tag);

    for (const [key, value] of Object.entries(attrs)) {
        if (key === 'class') {
            el.className = value;
        } else if (key === 'style' && typeof value === 'object') {
            Object.assign(el.style, value);
        } else if (key.startsWith('on') && typeof value === 'function') {
            el.addEventListener(key.slice(2).toLowerCase(), value);
        } else if (key.startsWith('data-')) {
            el.setAttribute(key, value);
        } else {
            el[key] = value;
        }
    }

    if (children) {
        if (typeof children === 'string') {
            el.textContent = children;
        } else if (Array.isArray(children)) {
            children.forEach(child => el.appendChild(child));
        } else {
            el.appendChild(children);
        }
    }

    return el;
}

/**
 * Sanitize HTML to prevent XSS
 * @param {string} html - Raw HTML string
 * @returns {string} Sanitized string
 */
function sanitizeHTML(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
}

// ============================================
// VALIDATION
// ============================================

/**
 * Validate trading symbol format
 * @param {string} symbol - Symbol to validate
 * @returns {boolean} Is valid
 */
function isValidSymbol(symbol) {
    return /^[A-Z]{2,10}USDT?$/.test(symbol);
}

/**
 * Validate number input
 * @param {string|number} value - Value to validate
 * @param {Object} options - Validation options
 * @returns {Object} Validation result
 */
function validateNumber(value, { min = -Infinity, max = Infinity, required = true } = {}) {
    if (value === '' || value === null || value === undefined) {
        return { valid: !required, error: required ? 'Value is required' : null };
    }

    const num = parseFloat(value);

    if (isNaN(num)) {
        return { valid: false, error: 'Must be a number' };
    }

    if (num < min) {
        return { valid: false, error: `Minimum value is ${min}` };
    }

    if (num > max) {
        return { valid: false, error: `Maximum value is ${max}` };
    }

    return { valid: true, value: num, error: null };
}

// ============================================
// LOCAL STORAGE
// ============================================

/**
 * Get value from localStorage with JSON parsing
 * @param {string} key - Storage key
 * @param {any} defaultValue - Default if not found
 * @returns {any} Stored value
 */
function getStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch {
        return defaultValue;
    }
}

/**
 * Set value in localStorage with JSON stringify
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 */
function setStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.warn('localStorage write failed:', e);
    }
}

// ============================================
// DEBOUNCE & THROTTLE
// ============================================

/**
 * Debounce function calls
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in ms
 * @returns {Function} Debounced function with optional .cancel()
 */
function debounce(fn, delay = 300) {
    let timeoutId;
    const debounced = function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
    debounced.cancel = function () {
        clearTimeout(timeoutId);
        timeoutId = null;
    };
    return debounced;
}

/**
 * Throttle function calls
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Minimum time between calls
 * @returns {Function} Throttled function
 */
function throttle(fn, limit = 100) {
    let inThrottle;
    return function (...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============================================
// NOTIFICATIONS
// ============================================

/**
 * Show toast notification
 * @param {string} message - Message to show
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in ms
 */
function showToast(message, type = 'info', duration = 3000) {
    // Get or create toast container
    let container = $('#toast-container');
    if (!container) {
        container = createElement('div', {
            id: 'toast-container',
            style: {
                position: 'fixed',
                top: '20px',
                right: '20px',
                zIndex: '9999',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
            }
        });
        document.body.appendChild(container);
    }

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    const toast = createElement('div', {
        class: `toast toast-${type}`,
        style: {
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '12px 16px',
            background: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            animation: 'slideIn 0.3s ease-out'
        }
    });

    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${sanitizeHTML(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ============================================
// EXPORTS
// ============================================

export {
    // Number formatting
    formatNumber,
    formatCurrency,
    formatPercent,
    formatPrice,

    // Date formatting
    formatDate,
    formatRelativeTime,

    // DOM utilities
    $,
    $$,
    createElement,
    sanitizeHTML,

    // Validation
    isValidSymbol,
    validateNumber,

    // Storage
    getStorage,
    setStorage,

    // Function helpers
    debounce,
    throttle,

    // Notifications
    showToast
};

// Attach to window for non-module scripts
if (typeof window !== 'undefined') {
    window.Utils = {
        formatNumber,
        formatCurrency,
        formatPercent,
        formatPrice,
        formatDate,
        formatRelativeTime,
        $,
        $$,
        createElement,
        sanitizeHTML,
        isValidSymbol,
        validateNumber,
        getStorage,
        setStorage,
        debounce,
        throttle,
        showToast
    };
}
