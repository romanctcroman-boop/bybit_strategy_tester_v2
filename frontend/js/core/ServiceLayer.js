/**
 * 🔌 Service Layer - Bybit Strategy Tester v2
 *
 * Centralized service layer for API communication,
 * data management, and business logic.
 *
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { api } from '../api.js';
import { getStore } from './StateManager.js';
import { getEventBus, Events } from './EventBus.js';

/**
 * Base Service class
 */
export class BaseService {
    constructor() {
        this._cache = new Map();
        this._cacheTime = 60000; // 1 minute default
        this._pending = new Map();
        this._store = null;
        this._bus = null;
    }

    get store() {
        if (!this._store) {
            this._store = getStore();
        }
        return this._store;
    }

    get bus() {
        if (!this._bus) {
            this._bus = getEventBus();
        }
        return this._bus;
    }

    /**
     * Make a cached API request
     * @param {string} key - Cache key
     * @param {Function} fetcher - Function that returns a promise
     * @param {number} ttl - Cache time to live in ms
     * @returns {Promise<*>}
     */
    async cached(key, fetcher, ttl = this._cacheTime) {
        // Check cache
        const cached = this._cache.get(key);
        if (cached && Date.now() - cached.timestamp < ttl) {
            return cached.data;
        }

        // Check if request is already pending
        if (this._pending.has(key)) {
            return this._pending.get(key);
        }

        // Make request
        const promise = fetcher().then(data => {
            this._cache.set(key, { data, timestamp: Date.now() });
            this._pending.delete(key);
            return data;
        }).catch(error => {
            this._pending.delete(key);
            throw error;
        });

        this._pending.set(key, promise);
        return promise;
    }

    /**
     * Clear cache
     * @param {string} pattern - Optional pattern to match keys
     */
    clearCache(pattern = null) {
        if (!pattern) {
            this._cache.clear();
            return;
        }

        for (const key of this._cache.keys()) {
            if (key.includes(pattern)) {
                this._cache.delete(key);
            }
        }
    }
}

/**
 * Market Data Service
 */
export class MarketService extends BaseService {
    /**
     * Get available symbols
     * @returns {Promise<string[]>}
     */
    async getSymbols() {
        return this.cached('symbols', () => api.get('/market/symbols'));
    }

    /**
     * Get current price for a symbol
     * @param {string} symbol - Trading symbol
     * @returns {Promise<Object>}
     */
    async getPrice(symbol) {
        return api.get(`/market/price/${symbol}`);
    }

    /**
     * Get ticker data
     * @param {string} symbol - Trading symbol
     * @returns {Promise<Object>}
     */
    async getTicker(symbol) {
        return this.cached(`ticker:${symbol}`, () => api.get(`/market/ticker/${symbol}`), 5000);
    }

    /**
     * Get kline/candlestick data
     * @param {string} symbol - Trading symbol
     * @param {string} interval - Timeframe (1m, 5m, 1h, etc.)
     * @param {number} limit - Number of candles
     * @returns {Promise<Object[]>}
     */
    async getKlines(symbol, interval, limit = 200) {
        return api.get(`/market/klines/${symbol}?interval=${interval}&limit=${limit}`);
    }

    /**
     * Get order book
     * @param {string} symbol - Trading symbol
     * @param {number} limit - Depth limit
     * @returns {Promise<Object>}
     */
    async getOrderBook(symbol, limit = 25) {
        return api.get(`/market/orderbook/${symbol}?limit=${limit}`);
    }

    /**
     * Get recent trades
     * @param {string} symbol - Trading symbol
     * @param {number} limit - Number of trades
     * @returns {Promise<Object[]>}
     */
    async getRecentTrades(symbol, limit = 50) {
        return api.get(`/market/trades/${symbol}?limit=${limit}`);
    }

    /**
     * Subscribe to real-time price updates
     * @param {string} symbol - Trading symbol
     * @param {Function} callback - Callback for updates
     */
    subscribePrice(symbol, callback) {
        // WebSocket subscription would go here
        this.bus.on(`market:price:${symbol}`, callback);
    }

    /**
     * Unsubscribe from price updates
     * @param {string} symbol - Trading symbol
     * @param {Function} callback - Callback to remove
     */
    unsubscribePrice(symbol, callback) {
        this.bus.off(`market:price:${symbol}`, callback);
    }
}

/**
 * Trading Service
 */
export class TradingService extends BaseService {
    /**
     * Get account balance
     * @returns {Promise<Object>}
     */
    async getBalance() {
        const balance = await api.get('/trading/balance');
        this.store?.set('trading.balance', balance);
        return balance;
    }

    /**
     * Get open positions
     * @returns {Promise<Object[]>}
     */
    async getPositions() {
        const positions = await api.get('/trading/positions');
        this.store?.set('trading.positions', positions);
        return positions;
    }

    /**
     * Get open orders
     * @returns {Promise<Object[]>}
     */
    async getOrders() {
        const orders = await api.get('/trading/orders');
        this.store?.set('trading.orders', orders);
        return orders;
    }

    /**
     * Place an order
     * @param {Object} order - Order details
     * @returns {Promise<Object>}
     */
    async placeOrder(order) {
        const result = await api.post('/trading/orders', order);
        this.bus.emit(Events.ORDER_PLACED, result);
        this.clearCache();
        return result;
    }

    /**
     * Cancel an order
     * @param {string} orderId - Order ID
     * @returns {Promise<Object>}
     */
    async cancelOrder(orderId) {
        const result = await api.delete(`/trading/orders/${orderId}`);
        this.bus.emit(Events.ORDER_CANCELLED, result);
        this.clearCache();
        return result;
    }

    /**
     * Close a position
     * @param {string} symbol - Trading symbol
     * @returns {Promise<Object>}
     */
    async closePosition(symbol) {
        const result = await api.post('/trading/positions/close', { symbol });
        this.bus.emit(Events.POSITION_CLOSE, result);
        this.clearCache();
        return result;
    }

    /**
     * Get trade history
     * @param {Object} params - Query params
     * @returns {Promise<Object[]>}
     */
    async getTradeHistory(params = {}) {
        return api.get('/trading/history', { params });
    }
}

/**
 * Strategy Service
 */
export class StrategyService extends BaseService {
    /**
     * Get all strategies
     * @returns {Promise<Object[]>}
     */
    async getStrategies() {
        return this.cached('strategies', () => api.get('/strategies'));
    }

    /**
     * Get strategy by ID
     * @param {string} id - Strategy ID
     * @returns {Promise<Object>}
     */
    async getStrategy(id) {
        return this.cached(`strategy:${id}`, () => api.get(`/strategies/${id}`));
    }

    /**
     * Create a strategy
     * @param {Object} strategy - Strategy data
     * @returns {Promise<Object>}
     */
    async createStrategy(strategy) {
        const result = await api.post('/strategies', strategy);
        this.clearCache('strategies');
        return result;
    }

    /**
     * Update a strategy
     * @param {string} id - Strategy ID
     * @param {Object} updates - Update data
     * @returns {Promise<Object>}
     */
    async updateStrategy(id, updates) {
        const result = await api.put(`/strategies/${id}`, updates);
        this.clearCache('strategy');
        return result;
    }

    /**
     * Delete a strategy
     * @param {string} id - Strategy ID
     * @returns {Promise<void>}
     */
    async deleteStrategy(id) {
        // Use permanent=true to actually delete from database
        await api.delete(`/strategies/${id}?permanent=true`);
        this.clearCache('strategy');
    }

    /**
     * Run backtest
     * @param {string} strategyId - Strategy ID
     * @param {Object} params - Backtest parameters
     * @returns {Promise<Object>}
     */
    async runBacktest(strategyId, params) {
        return api.post(`/strategies/${strategyId}/backtest`, params);
    }

    /**
     * Get backtest results
     * @param {string} backtestId - Backtest ID
     * @returns {Promise<Object>}
     */
    async getBacktestResults(backtestId) {
        return api.get(`/backtests/${backtestId}`);
    }
}

/**
 * Analytics Service
 */
export class AnalyticsService extends BaseService {
    /**
     * Get dashboard stats
     * @returns {Promise<Object>}
     */
    async getDashboardStats() {
        return this.cached('dashboard:stats', () => api.get('/analytics/dashboard'), 30000);
    }

    /**
     * Get performance metrics
     * @param {string} period - Time period
     * @returns {Promise<Object>}
     */
    async getPerformance(period = '30d') {
        return this.cached(`performance:${period}`, () =>
            api.get(`/analytics/performance?period=${period}`)
        );
    }

    /**
     * Get portfolio analytics
     * @returns {Promise<Object>}
     */
    async getPortfolioAnalytics() {
        return this.cached('portfolio:analytics', () => api.get('/analytics/portfolio'));
    }

    /**
     * Get risk metrics
     * @returns {Promise<Object>}
     */
    async getRiskMetrics() {
        return this.cached('risk:metrics', () => api.get('/analytics/risk'));
    }

    /**
     * Get trade statistics
     * @param {Object} params - Query params
     * @returns {Promise<Object>}
     */
    async getTradeStats(params = {}) {
        const query = new URLSearchParams(params).toString();
        return api.get(`/analytics/trades?${query}`);
    }
}

/**
 * Settings Service
 */
export class SettingsService extends BaseService {
    /**
     * Get user settings
     * @returns {Promise<Object>}
     */
    async getSettings() {
        const settings = await this.cached('settings', () => api.get('/settings'));
        this.store?.set('settings', settings);
        return settings;
    }

    /**
     * Update settings
     * @param {Object} updates - Settings to update
     * @returns {Promise<Object>}
     */
    async updateSettings(updates) {
        const result = await api.put('/settings', updates);
        this.store?.merge('settings', result);
        this.clearCache('settings');
        return result;
    }

    /**
     * Get API keys
     * @returns {Promise<Object[]>}
     */
    async getApiKeys() {
        return api.get('/settings/api-keys');
    }

    /**
     * Add API key
     * @param {Object} keyData - API key data
     * @returns {Promise<Object>}
     */
    async addApiKey(keyData) {
        return api.post('/settings/api-keys', keyData);
    }

    /**
     * Delete API key
     * @param {string} keyId - Key ID
     * @returns {Promise<void>}
     */
    async deleteApiKey(keyId) {
        return api.delete(`/settings/api-keys/${keyId}`);
    }
}

/**
 * Notification Service
 */
export class NotificationService extends BaseService {
    /**
     * Get notifications
     * @param {Object} params - Query params
     * @returns {Promise<Object[]>}
     */
    async getNotifications(params = {}) {
        return api.get('/notifications', { params });
    }

    /**
     * Mark notification as read
     * @param {string} id - Notification ID
     * @returns {Promise<void>}
     */
    async markAsRead(id) {
        return api.put(`/notifications/${id}/read`);
    }

    /**
     * Mark all as read
     * @returns {Promise<void>}
     */
    async markAllAsRead() {
        return api.put('/notifications/read-all');
    }

    /**
     * Delete notification
     * @param {string} id - Notification ID
     * @returns {Promise<void>}
     */
    async deleteNotification(id) {
        return api.delete(`/notifications/${id}`);
    }

    /**
     * Get unread count
     * @returns {Promise<number>}
     */
    async getUnreadCount() {
        const result = await api.get('/notifications/unread-count');
        return result.count || 0;
    }
}

// Service instances (lazy-loaded singletons)
let services = null;

/**
 * Get all services
 * @returns {Object}
 */
export function getServices() {
    if (!services) {
        services = {
            market: new MarketService(),
            trading: new TradingService(),
            strategy: new StrategyService(),
            analytics: new AnalyticsService(),
            settings: new SettingsService(),
            notifications: new NotificationService()
        };
    }
    return services;
}

/**
 * Get a specific service
 * @param {string} name - Service name
 * @returns {BaseService}
 */
export function getService(name) {
    return getServices()[name];
}

export default {
    BaseService,
    MarketService,
    TradingService,
    StrategyService,
    AnalyticsService,
    SettingsService,
    NotificationService,
    getServices,
    getService
};
