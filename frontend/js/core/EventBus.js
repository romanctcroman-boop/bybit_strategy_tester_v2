/**
 * 📢 Event Bus - Bybit Strategy Tester v2
 *
 * Centralized event system for inter-component communication.
 * Supports namespaced events, wildcards, and event history.
 *
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * EventBus - Pub/Sub event system
 *
 * @example
 * const bus = new EventBus();
 *
 * // Subscribe to event
 * bus.on('user:login', (user) => console.log('User logged in:', user));
 *
 * // Subscribe once
 * bus.once('app:ready', () => console.log('App is ready'));
 *
 * // Emit event
 * bus.emit('user:login', { name: 'John' });
 *
 * // Wildcard subscription
 * bus.on('user:*', (data, event) => console.log('User event:', event));
 */
export class EventBus {
    constructor(options = {}) {
        this._listeners = new Map();
        this._onceListeners = new Map();
        this._history = [];
        this._maxHistory = options.maxHistory || 100;
        this._debug = options.debug || false;
    }

    /**
     * Subscribe to an event
     * @param {string} event - Event name (supports wildcards: 'user:*', '*')
     * @param {Function} callback - Callback function
     * @param {Object} options - Options (priority: number for execution order)
     * @returns {Function} Unsubscribe function
     */
    on(event, callback, options = {}) {
        if (!this._listeners.has(event)) {
            this._listeners.set(event, []);
        }

        const listener = {
            callback,
            priority: options.priority || 0,
            context: options.context || null
        };

        this._listeners.get(event).push(listener);

        // Sort by priority (higher first)
        this._listeners.get(event).sort((a, b) => b.priority - a.priority);

        // Return unsubscribe function
        return () => this.off(event, callback);
    }

    /**
     * Subscribe to an event once
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    once(event, callback) {
        if (!this._onceListeners.has(event)) {
            this._onceListeners.set(event, []);
        }

        this._onceListeners.get(event).push(callback);

        return () => this.off(event, callback);
    }

    /**
     * Unsubscribe from an event
     * @param {string} event - Event name
     * @param {Function} callback - Callback to remove (if not provided, removes all)
     * @returns {EventBus} This instance for chaining
     */
    off(event, callback) {
        if (!callback) {
            this._listeners.delete(event);
            this._onceListeners.delete(event);
            return this;
        }

        // Remove from regular listeners
        const listeners = this._listeners.get(event);
        if (listeners) {
            const index = listeners.findIndex(l => l.callback === callback);
            if (index !== -1) {
                listeners.splice(index, 1);
            }
        }

        // Remove from once listeners
        const onceListeners = this._onceListeners.get(event);
        if (onceListeners) {
            const index = onceListeners.indexOf(callback);
            if (index !== -1) {
                onceListeners.splice(index, 1);
            }
        }

        return this;
    }

    /**
     * Emit an event
     * @param {string} event - Event name
     * @param {...*} args - Arguments to pass to listeners
     * @returns {EventBus} This instance for chaining
     */
    emit(event, ...args) {
        if (this._debug) {
            console.log(`[EventBus] ${event}`, ...args);
        }

        // Track in history
        this._addToHistory(event, args);

        // Get matching listeners (exact match + wildcards)
        const matchingListeners = this._getMatchingListeners(event);

        // Call listeners
        for (const { callback, context } of matchingListeners) {
            try {
                callback.apply(context, [...args, event]);
            } catch (error) {
                console.error(`[EventBus] Error in listener for "${event}":`, error);
            }
        }

        // Handle once listeners
        const onceListeners = this._onceListeners.get(event);
        if (onceListeners) {
            for (const callback of [...onceListeners]) {
                try {
                    callback(...args, event);
                } catch (error) {
                    console.error(`[EventBus] Error in once listener for "${event}":`, error);
                }
            }
            this._onceListeners.delete(event);
        }

        return this;
    }

    /**
     * Emit an event asynchronously
     * @param {string} event - Event name
     * @param {...*} args - Arguments
     * @returns {Promise<void>}
     */
    async emitAsync(event, ...args) {
        return new Promise((resolve) => {
            setTimeout(() => {
                this.emit(event, ...args);
                resolve();
            }, 0);
        });
    }

    /**
     * Wait for an event to be emitted
     * @param {string} event - Event name
     * @param {number} timeout - Timeout in ms (0 for no timeout)
     * @returns {Promise<*>} Event data
     */
    waitFor(event, timeout = 0) {
        return new Promise((resolve, reject) => {
            let timeoutId = null;

            const handler = (...args) => {
                if (timeoutId) clearTimeout(timeoutId);
                resolve(args.length === 1 ? args[0] : args);
            };

            this.once(event, handler);

            if (timeout > 0) {
                timeoutId = setTimeout(() => {
                    this.off(event, handler);
                    reject(new Error(`Timeout waiting for event: ${event}`));
                }, timeout);
            }
        });
    }

    /**
     * Check if event has listeners
     * @param {string} event - Event name
     * @returns {boolean}
     */
    hasListeners(event) {
        return (this._listeners.get(event)?.length > 0) ||
               (this._onceListeners.get(event)?.length > 0);
    }

    /**
     * Get all registered events
     * @returns {string[]} Event names
     */
    getEvents() {
        const events = new Set([
            ...this._listeners.keys(),
            ...this._onceListeners.keys()
        ]);
        return Array.from(events);
    }

    /**
     * Get event history
     * @param {string} filter - Optional event name filter
     * @returns {Array} Event history
     */
    getHistory(filter = null) {
        if (!filter) return [...this._history];
        return this._history.filter(entry => entry.event === filter);
    }

    /**
     * Clear all listeners
     * @returns {EventBus} This instance for chaining
     */
    clear() {
        this._listeners.clear();
        this._onceListeners.clear();
        return this;
    }

    /**
     * Clear event history
     * @returns {EventBus} This instance for chaining
     */
    clearHistory() {
        this._history = [];
        return this;
    }

    // Private methods

    _getMatchingListeners(event) {
        const matching = [];

        // Exact match
        const exact = this._listeners.get(event);
        if (exact) {
            matching.push(...exact);
        }

        // Wildcard matches
        for (const [pattern, listeners] of this._listeners) {
            if (pattern === event) continue; // Already added

            if (this._matchesPattern(event, pattern)) {
                matching.push(...listeners);
            }
        }

        // Sort by priority
        matching.sort((a, b) => b.priority - a.priority);

        return matching;
    }

    _matchesPattern(event, pattern) {
        // Global wildcard
        if (pattern === '*') return true;

        // Namespace wildcard (e.g., 'user:*' matches 'user:login')
        if (pattern.endsWith(':*')) {
            const namespace = pattern.slice(0, -2);
            return event.startsWith(namespace + ':');
        }

        // Prefix wildcard (e.g., '*.login' matches 'user.login')
        if (pattern.startsWith('*:')) {
            const suffix = pattern.slice(2);
            return event.endsWith(':' + suffix);
        }

        return false;
    }

    _addToHistory(event, args) {
        this._history.push({
            event,
            args: args.map(arg => {
                try {
                    return JSON.parse(JSON.stringify(arg));
                } catch {
                    return String(arg);
                }
            }),
            timestamp: Date.now()
        });

        // Limit history size
        if (this._history.length > this._maxHistory) {
            this._history.shift();
        }
    }
}

// Singleton instance
let busInstance = null;

/**
 * Get or create the global event bus
 * @param {Object} options - Options
 * @returns {EventBus}
 */
export function getEventBus(options = {}) {
    if (!busInstance) {
        busInstance = new EventBus(options);
    }
    return busInstance;
}

// Common event names
export const Events = {
    // App lifecycle
    APP_READY: 'app:ready',
    APP_ERROR: 'app:error',

    // User events
    USER_LOGIN: 'user:login',
    USER_LOGOUT: 'user:logout',
    USER_UPDATE: 'user:update',

    // UI events
    THEME_CHANGE: 'ui:theme:change',
    SIDEBAR_TOGGLE: 'ui:sidebar:toggle',
    MODAL_OPEN: 'ui:modal:open',
    MODAL_CLOSE: 'ui:modal:close',
    TOAST_SHOW: 'ui:toast:show',
    LOADING_START: 'ui:loading:start',
    LOADING_END: 'ui:loading:end',

    // Navigation
    PAGE_CHANGE: 'nav:page:change',
    ROUTE_CHANGE: 'nav:route:change',

    // Market data
    SYMBOL_CHANGE: 'market:symbol:change',
    TIMEFRAME_CHANGE: 'market:timeframe:change',
    PRICE_UPDATE: 'market:price:update',
    KLINE_UPDATE: 'market:kline:update',

    // Trading
    ORDER_PLACED: 'trade:order:placed',
    ORDER_FILLED: 'trade:order:filled',
    ORDER_CANCELLED: 'trade:order:cancelled',
    POSITION_OPEN: 'trade:position:open',
    POSITION_CLOSE: 'trade:position:close',
    BALANCE_UPDATE: 'trade:balance:update',

    // WebSocket
    WS_CONNECTED: 'ws:connected',
    WS_DISCONNECTED: 'ws:disconnected',
    WS_MESSAGE: 'ws:message',
    WS_ERROR: 'ws:error',

    // Data
    DATA_REFRESH: 'data:refresh',
    DATA_SYNC: 'data:sync',
    CACHE_CLEAR: 'data:cache:clear'
};

export default EventBus;
