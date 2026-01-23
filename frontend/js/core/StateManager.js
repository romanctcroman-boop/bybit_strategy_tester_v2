/**
 * 🔄 State Manager - Bybit Strategy Tester v2
 *
 * Centralized state management with subscriptions,
 * persistence, middleware support, and devtools integration.
 *
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

/**
 * StateManager - Redux-like state management for vanilla JS
 *
 * @example
 * const store = new StateManager({
 *     user: null,
 *     theme: 'dark',
 *     settings: {}
 * });
 *
 * // Subscribe to changes
 * store.subscribe('user', (user) => console.log('User changed:', user));
 *
 * // Update state
 * store.set('user', { name: 'John' });
 *
 * // Get state
 * const user = store.get('user');
 */
export class StateManager {
    constructor(initialState = {}, options = {}) {
        this._state = this._deepClone(initialState);
        this._listeners = new Map();
        this._middleware = [];
        this._history = [];
        this._historyIndex = -1;
        this._maxHistory = options.maxHistory || 50;
        this._persist = options.persist || false;
        this._persistKey = options.persistKey || 'app_state';
        this._persistPaths = options.persistPaths || null; // null = persist all
        this._devtools = options.devtools !== false && typeof window !== 'undefined';

        // Restore persisted state
        if (this._persist) {
            this._restoreState();
        }

        // Track initial state
        this._pushHistory('INIT', this._state);

        // Devtools integration
        if (this._devtools) {
            this._initDevtools();
        }
    }

    /**
     * Get a value from state
     * @param {string} path - Dot-notation path (e.g., 'user.settings.theme')
     * @param {*} defaultValue - Default value if path doesn't exist
     * @returns {*} The value at the path
     */
    get(path, defaultValue = undefined) {
        if (!path) return this._deepClone(this._state);

        const value = path.split('.').reduce((obj, key) => {
            return obj !== undefined && obj !== null ? obj[key] : undefined;
        }, this._state);

        return value !== undefined ? this._deepClone(value) : defaultValue;
    }

    /**
     * Set a value in state
     * @param {string} path - Dot-notation path
     * @param {*} value - Value to set
     * @param {Object} options - Options (silent: don't notify, action: action name)
     * @returns {StateManager} This instance for chaining
     */
    set(path, value, options = {}) {
        const prevState = this._deepClone(this._state);

        // Apply middleware
        let finalValue = value;
        for (const middleware of this._middleware) {
            const result = middleware({
                type: 'SET',
                path,
                value: finalValue,
                prevValue: this.get(path),
                state: this._state
            });
            if (result === false) return this; // Middleware cancelled the action
            if (result !== undefined) finalValue = result;
        }

        // Set the value
        this._setNestedValue(this._state, path, finalValue);

        // Track history
        if (!options.silent) {
            this._pushHistory(options.action || `SET:${path}`, this._state);
        }

        // Persist
        if (this._persist) {
            this._persistState();
        }

        // Notify listeners
        if (!options.silent) {
            this._notify(path, finalValue, prevState);
        }

        return this;
    }

    /**
     * Update multiple values at once
     * @param {Object} updates - Object with path: value pairs
     * @param {Object} options - Options
     * @returns {StateManager} This instance for chaining
     */
    batch(updates, options = {}) {
        const prevState = this._deepClone(this._state);

        for (const [path, value] of Object.entries(updates)) {
            this._setNestedValue(this._state, path, value);
        }

        if (!options.silent) {
            this._pushHistory(options.action || 'BATCH_UPDATE', this._state);

            // Notify all affected paths
            for (const path of Object.keys(updates)) {
                this._notify(path, this.get(path), prevState);
            }
        }

        if (this._persist) {
            this._persistState();
        }

        return this;
    }

    /**
     * Merge an object into a path
     * @param {string} path - Dot-notation path
     * @param {Object} value - Object to merge
     * @returns {StateManager} This instance for chaining
     */
    merge(path, value, options = {}) {
        const current = this.get(path) || {};
        const merged = { ...current, ...value };
        return this.set(path, merged, options);
    }

    /**
     * Delete a value from state
     * @param {string} path - Dot-notation path
     * @returns {StateManager} This instance for chaining
     */
    delete(path, options = {}) {
        const prevState = this._deepClone(this._state);
        const parts = path.split('.');
        const key = parts.pop();
        const parent = parts.length > 0
            ? this._getNestedValue(this._state, parts.join('.'))
            : this._state;

        if (parent && key in parent) {
            delete parent[key];

            if (!options.silent) {
                this._pushHistory(options.action || `DELETE:${path}`, this._state);
                this._notify(path, undefined, prevState);
            }

            if (this._persist) {
                this._persistState();
            }
        }

        return this;
    }

    /**
     * Subscribe to state changes
     * @param {string|string[]} paths - Path(s) to watch (use '*' for all)
     * @param {Function} callback - Callback function(newValue, path, prevValue)
     * @param {Object} options - Options (immediate: call immediately with current value)
     * @returns {Function} Unsubscribe function
     */
    subscribe(paths, callback, options = {}) {
        const pathsArray = Array.isArray(paths) ? paths : [paths];

        for (const path of pathsArray) {
            if (!this._listeners.has(path)) {
                this._listeners.set(path, new Set());
            }
            this._listeners.get(path).add(callback);

            // Call immediately with current value if requested
            if (options.immediate) {
                callback(this.get(path), path, undefined);
            }
        }

        // Return unsubscribe function
        return () => {
            for (const path of pathsArray) {
                const listeners = this._listeners.get(path);
                if (listeners) {
                    listeners.delete(callback);
                }
            }
        };
    }

    /**
     * Subscribe to a path and get computed value
     * @param {string[]} dependencies - Paths to watch
     * @param {Function} compute - Function to compute derived value
     * @param {Function} callback - Callback with computed value
     * @returns {Function} Unsubscribe function
     */
    computed(dependencies, compute, callback) {
        const update = () => {
            const values = dependencies.map(dep => this.get(dep));
            const computed = compute(...values);
            callback(computed);
        };

        // Initial compute
        update();

        // Subscribe to all dependencies
        return this.subscribe(dependencies, update);
    }

    /**
     * Add middleware
     * @param {Function} middleware - Middleware function
     * @returns {StateManager} This instance for chaining
     */
    use(middleware) {
        this._middleware.push(middleware);
        return this;
    }

    /**
     * Undo last action
     * @returns {StateManager} This instance for chaining
     */
    undo() {
        if (this._historyIndex > 0) {
            this._historyIndex--;
            const entry = this._history[this._historyIndex];
            this._state = this._deepClone(entry.state);
            this._notify('*', this._state, null);

            if (this._persist) {
                this._persistState();
            }
        }
        return this;
    }

    /**
     * Redo last undone action
     * @returns {StateManager} This instance for chaining
     */
    redo() {
        if (this._historyIndex < this._history.length - 1) {
            this._historyIndex++;
            const entry = this._history[this._historyIndex];
            this._state = this._deepClone(entry.state);
            this._notify('*', this._state, null);

            if (this._persist) {
                this._persistState();
            }
        }
        return this;
    }

    /**
     * Reset to initial state
     * @returns {StateManager} This instance for chaining
     */
    reset() {
        if (this._history.length > 0) {
            this._state = this._deepClone(this._history[0].state);
            this._pushHistory('RESET', this._state);
            this._notify('*', this._state, null);

            if (this._persist) {
                this._persistState();
            }
        }
        return this;
    }

    /**
     * Get state snapshot for debugging
     * @returns {Object} Current state
     */
    getSnapshot() {
        return {
            state: this._deepClone(this._state),
            historyLength: this._history.length,
            historyIndex: this._historyIndex,
            listeners: Array.from(this._listeners.keys())
        };
    }

    // Private methods

    _setNestedValue(obj, path, value) {
        const parts = path.split('.');
        let current = obj;

        for (let i = 0; i < parts.length - 1; i++) {
            const key = parts[i];
            if (!(key in current) || typeof current[key] !== 'object') {
                current[key] = {};
            }
            current = current[key];
        }

        current[parts[parts.length - 1]] = value;
    }

    _getNestedValue(obj, path) {
        return path.split('.').reduce((acc, key) => {
            return acc !== undefined && acc !== null ? acc[key] : undefined;
        }, obj);
    }

    _deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj);
        if (obj instanceof Array) return obj.map(item => this._deepClone(item));
        if (obj instanceof Object) {
            const copy = {};
            for (const key in obj) {
                if (Object.prototype.hasOwnProperty.call(obj, key)) {
                    copy[key] = this._deepClone(obj[key]);
                }
            }
            return copy;
        }
        return obj;
    }

    _notify(changedPath, newValue, prevState) {
        // Notify exact path listeners
        const listeners = this._listeners.get(changedPath);
        if (listeners) {
            const prevValue = prevState ? this._getNestedValue(prevState, changedPath) : undefined;
            for (const callback of listeners) {
                try {
                    callback(newValue, changedPath, prevValue);
                } catch (error) {
                    console.error('State listener error:', error);
                }
            }
        }

        // Notify wildcard listeners
        const wildcardListeners = this._listeners.get('*');
        if (wildcardListeners) {
            for (const callback of wildcardListeners) {
                try {
                    callback(this._state, changedPath, prevState);
                } catch (error) {
                    console.error('State listener error:', error);
                }
            }
        }

        // Notify parent path listeners
        const parts = changedPath.split('.');
        for (let i = parts.length - 1; i > 0; i--) {
            const parentPath = parts.slice(0, i).join('.');
            const parentListeners = this._listeners.get(parentPath);
            if (parentListeners) {
                const parentValue = this.get(parentPath);
                const prevParentValue = prevState ? this._getNestedValue(prevState, parentPath) : undefined;
                for (const callback of parentListeners) {
                    try {
                        callback(parentValue, parentPath, prevParentValue);
                    } catch (error) {
                        console.error('State listener error:', error);
                    }
                }
            }
        }
    }

    _pushHistory(action, state) {
        // Remove any redo history
        if (this._historyIndex < this._history.length - 1) {
            this._history = this._history.slice(0, this._historyIndex + 1);
        }

        this._history.push({
            action,
            state: this._deepClone(state),
            timestamp: Date.now()
        });

        // Limit history size
        if (this._history.length > this._maxHistory) {
            this._history.shift();
        } else {
            this._historyIndex++;
        }
    }

    _persistState() {
        try {
            let stateToSave = this._state;

            // Only persist specific paths if configured
            if (this._persistPaths) {
                stateToSave = {};
                for (const path of this._persistPaths) {
                    const value = this.get(path);
                    if (value !== undefined) {
                        this._setNestedValue(stateToSave, path, value);
                    }
                }
            }

            localStorage.setItem(this._persistKey, JSON.stringify(stateToSave));
        } catch (error) {
            console.warn('Failed to persist state:', error);
        }
    }

    _restoreState() {
        try {
            const saved = localStorage.getItem(this._persistKey);
            if (saved) {
                const parsed = JSON.parse(saved);

                // Merge saved state with initial state
                if (this._persistPaths) {
                    for (const path of this._persistPaths) {
                        const savedValue = this._getNestedValue(parsed, path);
                        if (savedValue !== undefined) {
                            this._setNestedValue(this._state, path, savedValue);
                        }
                    }
                } else {
                    this._state = { ...this._state, ...parsed };
                }
            }
        } catch (error) {
            console.warn('Failed to restore state:', error);
        }
    }

    _initDevtools() {
        // Simple devtools - expose to window for debugging
        if (typeof window !== 'undefined') {
            window.__STATE_MANAGER__ = this;

            // Log state changes in development
            this.subscribe('*', (state, path) => {
                if (typeof window !== 'undefined' && window.__DEV__) {
                    console.log(`[StateManager] ${path}`, state);
                }
            });
        }
    }
}

// Create singleton instance
let storeInstance = null;

/**
 * Get or create the global store instance
 * @param {Object} initialState - Initial state (only used on first call)
 * @param {Object} options - Store options
 * @returns {StateManager} Store instance
 */
export function createStore(initialState = {}, options = {}) {
    if (!storeInstance) {
        storeInstance = new StateManager(initialState, options);
    }
    return storeInstance;
}

/**
 * Get the global store instance
 * @returns {StateManager|null} Store instance or null
 */
export function getStore() {
    return storeInstance;
}

// Default initial state for the app
const DEFAULT_STATE = {
    // User
    user: null,
    auth: {
        isAuthenticated: false,
        token: null
    },

    // UI State
    ui: {
        theme: 'dark',
        sidebarCollapsed: false,
        currentPage: 'dashboard',
        loading: false,
        notifications: []
    },

    // Market Data
    market: {
        selectedSymbol: 'BTCUSDT',
        selectedTimeframe: '1h',
        watchlist: []
    },

    // Trading
    trading: {
        positions: [],
        orders: [],
        balance: 0
    },

    // Settings
    settings: {
        notifications: true,
        sounds: true,
        language: 'en',
        timezone: 'UTC'
    }
};

/**
 * Initialize the global store with default state
 * @param {Object} customState - Custom state to merge
 * @param {Object} options - Store options
 * @returns {StateManager} Store instance
 */
export function initStore(customState = {}, options = {}) {
    const initialState = { ...DEFAULT_STATE, ...customState };
    return createStore(initialState, {
        persist: true,
        persistKey: 'bybit_strategy_tester_state',
        persistPaths: ['ui.theme', 'ui.sidebarCollapsed', 'market.selectedSymbol', 'settings'],
        ...options
    });
}

export default StateManager;
