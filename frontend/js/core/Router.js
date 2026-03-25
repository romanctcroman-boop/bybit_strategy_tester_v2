/**
 * 🧭 Router - Bybit Strategy Tester v2
 *
 * Client-side router with history management,
 * route guards, and dynamic imports.
 *
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { getEventBus, Events } from './EventBus.js';

/**
 * Router - Client-side navigation
 *
 * @example
 * const router = new Router({
 *     routes: [
 *         { path: '/', page: 'dashboard' },
 *         { path: '/settings', page: 'settings', guard: () => isAuthenticated }
 *     ]
 * });
 *
 * router.navigate('/settings');
 */
export class Router {
    constructor(options = {}) {
        this._routes = [];
        this._guards = [];
        this._currentRoute = null;
        this._history = [];
        this._historyIndex = -1;
        this._mode = options.mode || 'hash'; // 'hash' or 'history'
        this._base = options.base || '';
        this._container = options.container || null;
        this._pageMap = options.pageMap || {};
        this._notFound = options.notFound || null;
        this._bus = getEventBus();

        // Register routes
        if (options.routes) {
            options.routes.forEach(route => this.addRoute(route));
        }

        // Initialize
        this._init();
    }

    /**
     * Add a route
     * @param {Object} route - Route configuration
     * @returns {Router} This instance for chaining
     */
    addRoute(route) {
        this._routes.push({
            path: route.path,
            page: route.page,
            title: route.title,
            guard: route.guard,
            beforeEnter: route.beforeEnter,
            afterEnter: route.afterEnter,
            meta: route.meta || {}
        });
        return this;
    }

    /**
     * Add a global route guard
     * @param {Function} guard - Guard function (returns boolean or Promise<boolean>)
     * @returns {Router} This instance for chaining
     */
    addGuard(guard) {
        this._guards.push(guard);
        return this;
    }

    /**
     * Navigate to a path
     * @param {string} path - Path to navigate to
     * @param {Object} options - Navigation options
     * @returns {Promise<boolean>} Whether navigation succeeded
     */
    async navigate(path, options = {}) {
        const route = this._matchRoute(path);

        if (!route) {
            if (this._notFound) {
                await this._loadPage(this._notFound, { path, params: {} });
            }
            return false;
        }

        // Extract params
        const params = this._extractParams(route, path);
        const query = this._parseQuery(path);

        // Run global guards
        for (const guard of this._guards) {
            const allowed = await guard({ route, params, query, from: this._currentRoute });
            if (!allowed) {
                console.log('[Router] Navigation blocked by global guard');
                return false;
            }
        }

        // Run route guard
        if (route.guard) {
            const allowed = await route.guard({ route, params, query, from: this._currentRoute });
            if (!allowed) {
                console.log('[Router] Navigation blocked by route guard');
                return false;
            }
        }

        // Before enter hook
        if (route.beforeEnter) {
            await route.beforeEnter({ route, params, query, from: this._currentRoute });
        }

        // Update URL
        if (!options.silent) {
            this._updateUrl(path, options.replace);
        }

        // Track history
        if (!options.replace && this._currentRoute) {
            this._history = this._history.slice(0, this._historyIndex + 1);
            this._history.push({ path, route, params, query });
            this._historyIndex++;
        }

        // Store previous route
        const prevRoute = this._currentRoute;

        // Update current route
        this._currentRoute = {
            path,
            route,
            params,
            query
        };

        // Load page
        await this._loadPage(route.page, { path, params, query });

        // Update title
        if (route.title) {
            document.title = typeof route.title === 'function'
                ? route.title({ params, query })
                : route.title;
        }

        // After enter hook
        if (route.afterEnter) {
            await route.afterEnter({ route, params, query, from: prevRoute });
        }

        // Emit event
        this._bus.emit(Events.ROUTE_CHANGE, {
            path,
            route: route.path,
            params,
            query,
            from: prevRoute
        });

        return true;
    }

    /**
     * Navigate back in history
     * @returns {Promise<boolean>}
     */
    async back() {
        if (this._historyIndex > 0) {
            this._historyIndex--;
            const entry = this._history[this._historyIndex];
            return this.navigate(entry.path, { silent: true });
        }
        return false;
    }

    /**
     * Navigate forward in history
     * @returns {Promise<boolean>}
     */
    async forward() {
        if (this._historyIndex < this._history.length - 1) {
            this._historyIndex++;
            const entry = this._history[this._historyIndex];
            return this.navigate(entry.path, { silent: true });
        }
        return false;
    }

    /**
     * Get current route info
     * @returns {Object|null}
     */
    getCurrentRoute() {
        return this._currentRoute;
    }

    /**
     * Get route params
     * @returns {Object}
     */
    getParams() {
        return this._currentRoute?.params || {};
    }

    /**
     * Get query params
     * @returns {Object}
     */
    getQuery() {
        return this._currentRoute?.query || {};
    }

    /**
     * Check if path matches current route
     * @param {string} path - Path to check
     * @returns {boolean}
     */
    isActive(path) {
        return this._currentRoute?.path === path;
    }

    /**
     * Generate URL for a route
     * @param {string} name - Route path pattern
     * @param {Object} params - Route params
     * @param {Object} query - Query params
     * @returns {string}
     */
    url(name, params = {}, query = {}) {
        let url = name;

        // Replace params
        for (const [key, value] of Object.entries(params)) {
            url = url.replace(`:${key}`, encodeURIComponent(value));
        }

        // Add query string
        const queryString = new URLSearchParams(query).toString();
        if (queryString) {
            url += '?' + queryString;
        }

        return this._base + (this._mode === 'hash' ? '#' : '') + url;
    }

    // Private methods

    _init() {
        // Handle browser navigation
        window.addEventListener('popstate', (_e) => {
            const path = this._getCurrentPath();
            this.navigate(path, { silent: true });
        });

        // Handle hash changes
        if (this._mode === 'hash') {
            window.addEventListener('hashchange', () => {
                const path = this._getCurrentPath();
                this.navigate(path, { silent: true });
            });
        }

        // Handle link clicks
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[data-route]');
            if (link) {
                e.preventDefault();
                const path = link.getAttribute('data-route') || link.getAttribute('href');
                this.navigate(path);
            }
        });

        // Navigate to initial route
        const initialPath = this._getCurrentPath();
        if (initialPath) {
            this.navigate(initialPath, { silent: true });
        }
    }

    _getCurrentPath() {
        if (this._mode === 'hash') {
            return window.location.hash.slice(1) || '/';
        }
        return window.location.pathname.replace(this._base, '') || '/';
    }

    _updateUrl(path, replace = false) {
        const url = this._base + (this._mode === 'hash' ? '#' : '') + path;

        if (replace) {
            window.history.replaceState(null, '', url);
        } else {
            window.history.pushState(null, '', url);
        }
    }

    _matchRoute(path) {
        // Remove query string for matching
        const pathWithoutQuery = path.split('?')[0];

        for (const route of this._routes) {
            const pattern = this._pathToRegex(route.path);
            if (pattern.test(pathWithoutQuery)) {
                return route;
            }
        }

        return null;
    }

    _pathToRegex(path) {
        // Convert route path to regex
        // /users/:id -> /users/([^/]+)
        const pattern = path
            .replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // Escape special chars
            .replace(/\\:([a-zA-Z_]+)/g, '([^/]+)'); // Replace :param with capture group

        return new RegExp('^' + pattern + '$');
    }

    _extractParams(route, path) {
        const pathWithoutQuery = path.split('?')[0];
        const paramNames = (route.path.match(/:([a-zA-Z_]+)/g) || [])
            .map(p => p.slice(1));

        const pattern = this._pathToRegex(route.path);
        const match = pathWithoutQuery.match(pattern);

        if (!match) return {};

        const params = {};
        paramNames.forEach((name, index) => {
            params[name] = decodeURIComponent(match[index + 1]);
        });

        return params;
    }

    _parseQuery(path) {
        const queryString = path.split('?')[1];
        if (!queryString) return {};

        const params = new URLSearchParams(queryString);
        const query = {};
        for (const [key, value] of params) {
            query[key] = value;
        }
        return query;
    }

    async _loadPage(page, context) {
        // If page is a function (dynamic import), call it
        if (typeof page === 'function') {
            try {
                const module = await page();
                if (module.default) {
                    await module.default(context);
                }
            } catch (error) {
                console.error('[Router] Failed to load page:', error);
            }
            return;
        }

        // If page is mapped to a URL
        if (this._pageMap[page]) {
            // For MPA: redirect to the page
            if (typeof this._pageMap[page] === 'string') {
                window.location.href = this._pageMap[page];
                return;
            }

            // For SPA: load into container
            if (this._container && this._pageMap[page].component) {
                const container = typeof this._container === 'string'
                    ? document.querySelector(this._container)
                    : this._container;

                if (container) {
                    container.innerHTML = '';
                    const component = new this._pageMap[page].component({
                        container,
                        props: context
                    });
                    component.mount();
                }
            }
        }
    }
}

// Singleton instance
let routerInstance = null;

/**
 * Initialize the router
 * @param {Object} options - Router options
 * @returns {Router}
 */
export function initRouter(options = {}) {
    if (!routerInstance) {
        routerInstance = new Router(options);
    }
    return routerInstance;
}

/**
 * Get the router instance
 * @returns {Router|null}
 */
export function getRouter() {
    return routerInstance;
}

// Default routes for the app
export const defaultRoutes = [
    { path: '/', page: 'dashboard', title: 'Dashboard - Bybit Strategy Tester' },
    { path: '/dashboard', page: 'dashboard', title: 'Dashboard - Bybit Strategy Tester' },
    { path: '/market-chart', page: 'market-chart', title: 'Market Chart - Bybit Strategy Tester' },
    { path: '/trading', page: 'trading', title: 'Trading - Bybit Strategy Tester' },
    { path: '/strategies', page: 'strategies', title: 'Strategies - Bybit Strategy Tester' },
    { path: '/strategy-builder', page: 'strategy-builder', title: 'Strategy Builder - Bybit Strategy Tester' },
    { path: '/backtest-results', page: 'backtest-results', title: 'Backtest Results - Bybit Strategy Tester' },
    { path: '/portfolio', page: 'portfolio', title: 'Portfolio - Bybit Strategy Tester' },
    { path: '/analytics', page: 'analytics', title: 'Analytics - Bybit Strategy Tester' },
    { path: '/analytics-advanced', page: 'analytics-advanced', title: 'Advanced Analytics - Bybit Strategy Tester' },
    { path: '/risk-management', page: 'risk-management', title: 'Risk Management - Bybit Strategy Tester' },
    { path: '/ml-models', page: 'ml-models', title: 'ML Models - Bybit Strategy Tester' },
    { path: '/notifications', page: 'notifications', title: 'Notifications - Bybit Strategy Tester' },
    { path: '/settings', page: 'settings', title: 'Settings - Bybit Strategy Tester' }
];

export default Router;
