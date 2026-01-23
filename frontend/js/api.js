/**
 * 🌐 API Client - Bybit Strategy Tester v2
 *
 * Centralized API client with error handling, retry logic, and caching.
 * Part of Phase 1: Security & Performance improvements.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Configuration
const API_CONFIG = {
    baseUrl: '/api/v1',
    timeout: 30000,
    retryAttempts: 3,
    retryDelay: 1000,
    cacheTime: 60000 // 1 minute
};

// Simple in-memory cache
const cache = new Map();

/**
 * API Client class with retry and caching
 */
class ApiClient {
    constructor(config = {}) {
        this.config = { ...API_CONFIG, ...config };
        this.abortControllers = new Map();
    }

    /**
     * Make an API request with retry logic
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<any>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${this.config.baseUrl}${endpoint}`;
        const requestId = `${options.method || 'GET'}_${endpoint}`;

        // Cancel any pending request to the same endpoint
        if (this.abortControllers.has(requestId)) {
            this.abortControllers.get(requestId).abort();
        }

        const abortController = new AbortController();
        this.abortControllers.set(requestId, abortController);

        const fetchOptions = {
            ...options,
            signal: abortController.signal,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        let lastError;

        for (let attempt = 1; attempt <= this.config.retryAttempts; attempt++) {
            try {
                const response = await this._fetchWithTimeout(url, fetchOptions);

                if (!response.ok) {
                    throw new ApiError(
                        `HTTP ${response.status}: ${response.statusText}`,
                        response.status,
                        await response.json().catch(() => null)
                    );
                }

                const data = await response.json();
                this.abortControllers.delete(requestId);
                return data;

            } catch (error) {
                lastError = error;

                if (error.name === 'AbortError') {
                    throw error; // Don't retry aborted requests
                }

                if (attempt < this.config.retryAttempts) {
                    await this._delay(this.config.retryDelay * attempt);
                }
            }
        }

        this.abortControllers.delete(requestId);
        throw lastError;
    }

    /**
     * GET request with optional caching
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Additional options
     * @returns {Promise<any>} Response data
     */
    async get(endpoint, { useCache = false, cacheTime = this.config.cacheTime } = {}) {
        const cacheKey = endpoint;

        if (useCache && cache.has(cacheKey)) {
            const cached = cache.get(cacheKey);
            if (Date.now() - cached.timestamp < cacheTime) {
                return cached.data;
            }
            cache.delete(cacheKey);
        }

        const data = await this.request(endpoint, { method: 'GET' });

        if (useCache) {
            cache.set(cacheKey, { data, timestamp: Date.now() });
        }

        return data;
    }

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {Object} body - Request body
     * @returns {Promise<any>} Response data
     */
    async post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {Object} body - Request body
     * @returns {Promise<any>} Response data
     */
    async put(endpoint, body) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @returns {Promise<any>} Response data
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    /**
     * Fetch with timeout
     * @private
     */
    async _fetchWithTimeout(url, options) {
        const timeoutId = setTimeout(() => {
            if (options.signal) {
                // Can't abort externally, will use Promise.race instead
            }
        }, this.config.timeout);

        try {
            const response = await Promise.race([
                fetch(url, options),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Request timeout')), this.config.timeout)
                )
            ]);
            return response;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    /**
     * Delay helper
     * @private
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Clear cache
     */
    clearCache() {
        cache.clear();
    }
}

/**
 * Custom API Error class
 */
class ApiError extends Error {
    constructor(message, status, data = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

// Create singleton instance
const api = new ApiClient();

// ============================================
// API ENDPOINTS
// ============================================

/**
 * Health & Status APIs
 */
const healthApi = {
    async getHealth() {
        return api.get('/health', { useCache: true, cacheTime: 5000 });
    },

    async getStatus() {
        return api.get('/status');
    }
};

/**
 * Market Data APIs
 */
const marketApi = {
    async getSymbols() {
        return api.get('/symbols', { useCache: true, cacheTime: 300000 }); // 5 min cache
    },

    async getKlines(symbol, interval, limit = 500) {
        return api.get(`/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`);
    },

    async getTicker(symbol) {
        return api.get(`/ticker/${symbol}`);
    },

    async getOrderbook(symbol, depth = 25) {
        return api.get(`/orderbook/${symbol}?depth=${depth}`);
    }
};

/**
 * Trading APIs
 */
const tradingApi = {
    async getPositions() {
        return api.get('/positions');
    },

    async getOrders(status = 'open') {
        return api.get(`/orders?status=${status}`);
    },

    async placeOrder(order) {
        return api.post('/orders', order);
    },

    async cancelOrder(orderId) {
        return api.delete(`/orders/${orderId}`);
    }
};

/**
 * Strategy APIs
 */
const strategyApi = {
    async getStrategies() {
        return api.get('/strategies');
    },

    async getStrategy(id) {
        return api.get(`/strategies/${id}`);
    },

    async createStrategy(strategy) {
        return api.post('/strategies', strategy);
    },

    async updateStrategy(id, strategy) {
        return api.put(`/strategies/${id}`, strategy);
    },

    async deleteStrategy(id) {
        // Use permanent=true to actually delete from database
        return api.delete(`/strategies/${id}?permanent=true`);
    },

    async runBacktest(id, params) {
        return api.post(`/strategies/${id}/backtest`, params);
    }
};

/**
 * Analytics APIs
 */
const analyticsApi = {
    async getDashboardStats() {
        return api.get('/dashboard/stats', { useCache: true, cacheTime: 30000 });
    },

    async getPerformance(period = '30d') {
        return api.get(`/analytics/performance?period=${period}`);
    },

    async getTradeHistory(params = {}) {
        const query = new URLSearchParams(params).toString();
        return api.get(`/trades?${query}`);
    }
};

// Export for use in other modules
export {
    api,
    api as apiClient,  // Alias for backward compatibility
    API_CONFIG,
    ApiClient,
    ApiError,
    healthApi,
    marketApi,
    tradingApi,
    strategyApi,
    analyticsApi
};

// Also attach to window for non-module scripts
if (typeof window !== 'undefined') {
    window.API = {
        client: api,
        health: healthApi,
        market: marketApi,
        trading: tradingApi,
        strategy: strategyApi,
        analytics: analyticsApi
    };
}
