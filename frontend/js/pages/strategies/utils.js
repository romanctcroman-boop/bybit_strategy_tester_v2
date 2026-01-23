/**
 * 📄 Strategies Page - Utility Functions
 *
 * Extracted from strategies.js during refactoring
 * Contains: formatting, helpers, UI utilities
 *
 * @version 1.0.0
 * @date 2025-12-23
 */

/**
 * Format large numbers for display (K, M, B)
 * @param {number} num - Number to format
 * @returns {string} Formatted string
 */
export function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toFixed(0);
}

/**
 * Format percentage value
 * @param {number} value - Value to format
 * @param {boolean} isRatio - If true, multiply by 100
 * @returns {string} Formatted percentage string
 */
export function formatPercent(value, isRatio = false) {
    if (value === null || value === undefined) return '-';
    const pct = isRatio ? value * 100 : value;
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(2)}%`;
}

/**
 * Format date range for display (Russian locale)
 * @param {string} earliestIso - Start date ISO string
 * @param {string} latestIso - End date ISO string
 * @returns {string} Formatted date range
 */
export function formatDateRange(earliestIso, latestIso) {
    if (!earliestIso || !latestIso) return '';

    const earliest = new Date(earliestIso);
    const latest = new Date(latestIso);

    const formatDate = (d) => d.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });

    return `${formatDate(earliest)} — ${formatDate(latest)}`;
}

/**
 * Format hours ago into human-readable Russian text
 * @param {number} hours - Hours ago
 * @returns {string} Human-readable text
 */
export function formatHoursAgo(hours) {
    if (hours < 1) {
        const mins = Math.round(hours * 60);
        return `${mins} мин. назад`;
    } else if (hours < 24) {
        return `${Math.round(hours)} ч. назад`;
    } else {
        const days = Math.round(hours / 24);
        return `${days} дн. назад`;
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Get CSS class for return value (positive/negative)
 * @param {number} value - Return value
 * @returns {string} CSS class name
 */
export function getReturnClass(value) {
    if (value === null || value === undefined) return '';
    return value >= 0 ? 'positive' : 'negative';
}

/**
 * Round quantity according to Bybit qtyStep
 * @param {number} value - Value to round
 * @param {number} step - Step size
 * @returns {number} Rounded value
 */
export function roundToStep(value, step) {
    if (!step || step <= 0) return value;
    // eslint-disable-next-line no-unused-vars
    const precision = Math.max(0, Math.ceil(-Math.log10(step)));
    return Math.floor(value / step) * step;
}

/**
 * Sleep/delay helper for async operations
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Toast type: 'info', 'success', 'error', 'warning'
 */
export function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        console.warn('Toast container not found');
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => toast.remove(), 5000);
}

/**
 * Get icon for data freshness status
 * @param {string} freshness - 'fresh', 'stale', 'outdated'
 * @returns {string} Emoji icon
 */
export function getFreshnessIcon(freshness) {
    switch (freshness) {
    case 'fresh':
        return '✅';
    case 'stale':
        return '⚠️';
    case 'outdated':
        return '🔄';
    default:
        return '❓';
    }
}

/**
 * Get text description for data freshness
 * @param {string} freshness - 'fresh', 'stale', 'outdated'
 * @param {number|null} hoursOld - Hours since last update
 * @returns {string} Description text
 */
export function getFreshnessText(freshness, hoursOld) {
    const hoursText = hoursOld !== null ? ` (${formatHoursAgo(hoursOld)})` : '';

    switch (freshness) {
    case 'fresh':
        return `Данные актуальны${hoursText}`;
    case 'stale':
        return `Данные устаревают${hoursText}`;
    case 'outdated':
        return `Требуется обновление${hoursText}`;
    default:
        return 'Статус неизвестен';
    }
}
