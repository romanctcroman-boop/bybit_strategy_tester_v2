/**
 * 📄 Live Trading Service
 *
 * Client-side service for interacting with Live Trading API
 * Provides WebSocket connection for real-time updates
 *
 * @version 1.0.0
 * @date 2026-01-17
 */

const API_BASE = '/api/v1/live';

// ============================================
// STATE
// ============================================

let ws = null;
let wsReconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY = 2000;

// Callbacks for real-time updates
const callbacks = {
    position: [],
    order: [],
    wallet: [],
    execution: [],
    error: []
};

// ============================================
// REST API METHODS
// ============================================

/**
 * Place a trading order
 * @param {Object} order - Order parameters
 * @returns {Promise<Object>} - Order result
 */
export async function placeOrder({
    symbol,
    side,
    qty,
    orderType = 'market',
    price = null,
    stopLoss = null,
    takeProfit = null,
    reduceOnly = false,
    timeInForce = 'GTC'
}) {
    const payload = {
        symbol,
        side: side.toLowerCase(),
        qty,
        order_type: orderType.toLowerCase(),
        reduce_only: reduceOnly,
        time_in_force: timeInForce
    };

    if (price && orderType.toLowerCase() === 'limit') {
        payload.price = price;
    }
    if (stopLoss) payload.stop_loss = stopLoss;
    if (takeProfit) payload.take_profit = takeProfit;

    const response = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to place order');
    }

    return response.json();
}

/**
 * Cancel an order
 * @param {string} orderId - Order ID to cancel
 * @param {string} symbol - Trading pair
 * @returns {Promise<Object>}
 */
export async function cancelOrder(orderId, symbol) {
    const response = await fetch(
        `${API_BASE}/order/${orderId}?symbol=${symbol}`,
        { method: 'DELETE' }
    );

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to cancel order');
    }

    return response.json();
}

/**
 * Cancel all open orders
 * @param {string} symbol - Optional symbol filter
 * @returns {Promise<Object>}
 */
export async function cancelAllOrders(symbol = null) {
    const url = symbol
        ? `${API_BASE}/orders?symbol=${symbol}`
        : `${API_BASE}/orders`;

    const response = await fetch(url, { method: 'DELETE' });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to cancel orders');
    }

    return response.json();
}

/**
 * Get open orders
 * @param {string} symbol - Optional symbol filter
 * @returns {Promise<Array>}
 */
export async function getOpenOrders(symbol = null) {
    const url = symbol
        ? `${API_BASE}/orders?symbol=${symbol}`
        : `${API_BASE}/orders`;

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch orders');

    return response.json();
}

/**
 * Get all positions
 * @param {string} symbol - Optional symbol filter
 * @returns {Promise<Array>}
 */
export async function getPositions(symbol = null) {
    const url = symbol
        ? `${API_BASE}/positions?symbol=${symbol}`
        : `${API_BASE}/positions`;

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch positions');

    return response.json();
}

/**
 * Close a position
 * @param {string} symbol - Trading pair
 * @param {number} qty - Quantity to close (null for full close)
 * @returns {Promise<Object>}
 */
export async function closePosition(symbol, qty = null) {
    const url = qty
        ? `${API_BASE}/position/${symbol}?qty=${qty}`
        : `${API_BASE}/position/${symbol}`;

    const response = await fetch(url, { method: 'DELETE' });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to close position');
    }

    return response.json();
}

/**
 * Close all positions
 * @returns {Promise<Object>}
 */
export async function closeAllPositions() {
    const response = await fetch(`${API_BASE}/positions/close-all`, {
        method: 'POST'
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to close all positions');
    }

    return response.json();
}

/**
 * Set SL/TP for a position
 * @param {string} symbol - Trading pair
 * @param {number} stopLoss - Stop loss price
 * @param {number} takeProfit - Take profit price
 * @returns {Promise<Object>}
 */
export async function setPositionSLTP(symbol, stopLoss = null, takeProfit = null) {
    const response = await fetch(`${API_BASE}/position/sltp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol,
            stop_loss: stopLoss,
            take_profit: takeProfit
        })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to set SL/TP');
    }

    return response.json();
}

/**
 * Get wallet balance
 * @param {string} accountType - Account type (UNIFIED, CONTRACT, etc.)
 * @returns {Promise<Object>}
 */
export async function getBalance(accountType = 'UNIFIED') {
    const response = await fetch(`${API_BASE}/balance?account_type=${accountType}`);
    if (!response.ok) throw new Error('Failed to fetch balance');

    return response.json();
}

/**
 * Set leverage for a symbol
 * @param {string} symbol - Trading pair
 * @param {number} leverage - Leverage multiplier (1-100)
 * @returns {Promise<Object>}
 */
export async function setLeverage(symbol, leverage) {
    const response = await fetch(`${API_BASE}/leverage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, leverage })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to set leverage');
    }

    return response.json();
}

// ============================================
// WEBSOCKET METHODS
// ============================================

/**
 * Connect to live trading WebSocket
 * @returns {Promise<WebSocket>}
 */
export function connectWebSocket() {
    return new Promise((resolve, reject) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            resolve(ws);
            return;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}${API_BASE}/ws`;

        console.log('[LiveTrading] Connecting to WebSocket:', wsUrl);

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('[LiveTrading] WebSocket connected');
            wsReconnectAttempts = 0;
            resolve(ws);
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error('[LiveTrading] Failed to parse message:', e);
            }
        };

        ws.onclose = (event) => {
            console.log('[LiveTrading] WebSocket closed:', event.code, event.reason);
            ws = null;

            // Auto-reconnect
            if (wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                console.log(`[LiveTrading] Reconnecting in ${RECONNECT_DELAY}ms... (attempt ${wsReconnectAttempts})`);
                setTimeout(() => connectWebSocket(), RECONNECT_DELAY);
            }
        };

        ws.onerror = (error) => {
            console.error('[LiveTrading] WebSocket error:', error);
            triggerCallbacks('error', { error: 'WebSocket connection error' });
            reject(error);
        };
    });
}

/**
 * Disconnect WebSocket
 */
export function disconnectWebSocket() {
    if (ws) {
        ws.close();
        ws = null;
    }
    wsReconnectAttempts = MAX_RECONNECT_ATTEMPTS; // Prevent auto-reconnect
}

/**
 * Handle incoming WebSocket message
 * @param {Object} message - Parsed message
 */
function handleWebSocketMessage(message) {
    const { type, data } = message;

    switch (type) {
    case 'position':
        triggerCallbacks('position', data);
        break;
    case 'order':
        triggerCallbacks('order', data);
        break;
    case 'wallet':
        triggerCallbacks('wallet', data);
        break;
    case 'execution':
        triggerCallbacks('execution', data);
        break;
    case 'error':
        triggerCallbacks('error', data);
        break;
    default:
        console.log('[LiveTrading] Unknown message type:', type);
    }
}

/**
 * Register callback for real-time updates
 * @param {string} eventType - Event type (position, order, wallet, execution, error)
 * @param {Function} callback - Callback function
 */
export function onUpdate(eventType, callback) {
    if (callbacks[eventType]) {
        callbacks[eventType].push(callback);
    }
}

/**
 * Unregister callback
 * @param {string} eventType - Event type
 * @param {Function} callback - Callback function to remove
 */
export function offUpdate(eventType, callback) {
    if (callbacks[eventType]) {
        const index = callbacks[eventType].indexOf(callback);
        if (index > -1) {
            callbacks[eventType].splice(index, 1);
        }
    }
}

/**
 * Trigger all callbacks for an event type
 * @param {string} eventType - Event type
 * @param {Object} data - Event data
 */
function triggerCallbacks(eventType, data) {
    if (callbacks[eventType]) {
        callbacks[eventType].forEach(cb => {
            try {
                cb(data);
            } catch (e) {
                console.error(`[LiveTrading] Callback error for ${eventType}:`, e);
            }
        });
    }
}

// ============================================
// UTILITY METHODS
// ============================================

/**
 * Check if API credentials are configured
 * @returns {Promise<boolean>}
 */
export async function checkCredentials() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.has_credentials === true;
    } catch {
        return false;
    }
}

/**
 * Check connection status
 * @returns {Object} - Connection status
 */
export function getConnectionStatus() {
    return {
        websocket: ws ? ws.readyState === WebSocket.OPEN : false,
        reconnectAttempts: wsReconnectAttempts
    };
}

// ============================================
// EXPORTS
// ============================================

export default {
    // Orders
    placeOrder,
    cancelOrder,
    cancelAllOrders,
    getOpenOrders,

    // Positions
    getPositions,
    closePosition,
    closeAllPositions,
    setPositionSLTP,

    // Account
    getBalance,
    setLeverage,

    // WebSocket
    connectWebSocket,
    disconnectWebSocket,
    onUpdate,
    offUpdate,

    // Utility
    checkCredentials,
    getConnectionStatus
};
