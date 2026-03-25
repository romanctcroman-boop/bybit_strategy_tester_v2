/**
 * 📡 Resource Hints - Bybit Strategy Tester v2
 *
 * Browser resource hints for preloading, prefetching,
 * and preconnecting to improve performance.
 *
 * Part of Phase 3: Performance Optimization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * Resource hint types
 */
export const HintType = {
    PRELOAD: 'preload',
    PREFETCH: 'prefetch',
    PRECONNECT: 'preconnect',
    DNS_PREFETCH: 'dns-prefetch',
    MODULEPRELOAD: 'modulepreload'
};

/**
 * Resource types for preload
 */
export const ResourceType = {
    SCRIPT: 'script',
    STYLE: 'style',
    IMAGE: 'image',
    FONT: 'font',
    FETCH: 'fetch',
    DOCUMENT: 'document'
};

/**
 * Resource Hints Manager
 */
export class ResourceHints {
    constructor() {
        this._hints = new Set();
        this._scheduled = [];
        this._connections = new Set();
    }

    /**
     * Add a preload hint
     * @param {string} href - Resource URL
     * @param {string} as - Resource type (script, style, image, font, fetch)
     * @param {Object} options - Additional options
     */
    preload(href, as, options = {}) {
        if (this._hints.has(href)) return;

        const link = document.createElement('link');
        link.rel = 'preload';
        link.href = href;
        link.as = as;

        if (options.crossorigin) {
            link.crossOrigin = options.crossorigin;
        }
        if (options.type) {
            link.type = options.type;
        }
        if (options.media) {
            link.media = options.media;
        }

        document.head.appendChild(link);
        this._hints.add(href);
    }

    /**
     * Add a prefetch hint (low priority)
     * @param {string} href - Resource URL
     * @param {string} as - Resource type
     */
    prefetch(href, as = null) {
        if (this._hints.has(href)) return;

        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = href;
        if (as) link.as = as;

        document.head.appendChild(link);
        this._hints.add(href);
    }

    /**
     * Preload a module
     * @param {string} href - Module URL
     */
    modulePreload(href) {
        if (this._hints.has(href)) return;

        const link = document.createElement('link');
        link.rel = 'modulepreload';
        link.href = href;

        document.head.appendChild(link);
        this._hints.add(href);
    }

    /**
     * Add preconnect hint
     * @param {string} origin - Origin URL
     * @param {boolean} crossorigin - Include crossorigin attribute
     */
    preconnect(origin, crossorigin = false) {
        if (this._connections.has(origin)) return;

        const link = document.createElement('link');
        link.rel = 'preconnect';
        link.href = origin;
        if (crossorigin) {
            link.crossOrigin = 'anonymous';
        }

        document.head.appendChild(link);
        this._connections.add(origin);
    }

    /**
     * Add DNS prefetch hint
     * @param {string} origin - Origin URL
     */
    dnsPrefetch(origin) {
        if (this._connections.has(`dns:${origin}`)) return;

        const link = document.createElement('link');
        link.rel = 'dns-prefetch';
        link.href = origin;

        document.head.appendChild(link);
        this._connections.add(`dns:${origin}`);
    }

    /**
     * Preload critical resources
     * @param {Object[]} resources - Array of resource configs
     */
    preloadCritical(resources) {
        resources.forEach(({ href, as, options }) => {
            this.preload(href, as, options || {});
        });
    }

    /**
     * Schedule prefetch for idle time
     * @param {string[]} urls - URLs to prefetch
     */
    schedulePrefetch(urls) {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => {
                urls.forEach(url => this.prefetch(url));
            }, { timeout: 3000 });
        } else {
            setTimeout(() => {
                urls.forEach(url => this.prefetch(url));
            }, 2000);
        }
    }

    /**
     * Preconnect to API endpoints
     * @param {string[]} origins - API origins
     */
    preconnectAPIs(origins) {
        origins.forEach(origin => {
            this.preconnect(origin, true);
        });
    }

    /**
     * Setup common hints based on page
     * @param {string} page - Page name
     */
    setupForPage(page) {
        // Common preconnects
        const apiOrigin = window.location.origin;
        this.preconnect(apiOrigin, true);

        // Page-specific hints
        const pageHints = this._getPageHints(page);
        if (pageHints) {
            pageHints.preload?.forEach(r => this.preload(r.href, r.as, r.options));
            pageHints.prefetch?.forEach(url => this.prefetch(url));
            pageHints.preconnect?.forEach(origin => this.preconnect(origin, true));
        }
    }

    /**
     * Get hints for specific page
     * @private
     */
    _getPageHints(page) {
        const hints = {
            dashboard: {
                prefetch: [
                    '/js/pages/trading.js',
                    '/js/pages/analytics.js'
                ]
            },
            trading: {
                preload: [
                    { href: '/libs/lightweight-charts.js', as: 'script' }
                ],
                prefetch: [
                    '/js/pages/portfolio.js'
                ]
            },
            'market-chart': {
                preload: [
                    { href: '/libs/lightweight-charts.js', as: 'script' }
                ]
            },
            analytics: {
                prefetch: [
                    '/js/pages/analytics_advanced.js'
                ]
            }
        };

        return hints[page] || null;
    }

    /**
     * Preload fonts
     * @param {Object[]} fonts - Font configurations
     */
    preloadFonts(fonts) {
        fonts.forEach(({ href, type = 'font/woff2' }) => {
            this.preload(href, 'font', {
                crossorigin: 'anonymous',
                type
            });
        });
    }

    /**
     * Check if resource is already hinted
     * @param {string} href - Resource URL
     * @returns {boolean}
     */
    isHinted(href) {
        return this._hints.has(href);
    }

    /**
     * Clear all hints (for testing)
     */
    clear() {
        this._hints.clear();
        this._connections.clear();
    }
}

/**
 * Priority Hints for fetch requests
 */
export class FetchPriority {
    /**
     * Create high priority fetch
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>}
     */
    static high(url, options = {}) {
        return fetch(url, {
            ...options,
            priority: 'high'
        });
    }

    /**
     * Create low priority fetch
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>}
     */
    static low(url, options = {}) {
        return fetch(url, {
            ...options,
            priority: 'low'
        });
    }

    /**
     * Create auto priority fetch
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>}
     */
    static auto(url, options = {}) {
        return fetch(url, {
            ...options,
            priority: 'auto'
        });
    }
}

/**
 * Early Hints handler (for 103 Early Hints support)
 */
export class EarlyHints {
    /**
     * Parse Link headers from 103 response
     * @param {string} linkHeader - Link header value
     * @returns {Object[]}
     */
    static parseLinks(linkHeader) {
        if (!linkHeader) return [];

        return linkHeader.split(',').map(link => {
            const match = link.match(/<([^>]+)>;\s*rel="?([^";]+)"?(?:;\s*as="?([^";]+)"?)?/);
            if (match) {
                return {
                    href: match[1],
                    rel: match[2],
                    as: match[3] || null
                };
            }
            return null;
        }).filter(Boolean);
    }
}

// Singleton instance
let resourceHints = null;

/**
 * Get resource hints instance
 * @returns {ResourceHints}
 */
export function getResourceHints() {
    if (!resourceHints) {
        resourceHints = new ResourceHints();
    }
    return resourceHints;
}

/**
 * Initialize resource hints for current page
 */
export function initResourceHints() {
    const hints = getResourceHints();
    const page = document.body.dataset.page || window.location.pathname.split('/').pop()?.replace('.html', '');

    if (page) {
        hints.setupForPage(page);
    }

    // Preconnect to common origins
    hints.preconnect(window.location.origin, true);

    return hints;
}

export default {
    ResourceHints,
    FetchPriority,
    EarlyHints,
    HintType,
    ResourceType,
    getResourceHints,
    initResourceHints
};
