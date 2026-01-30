/**
 * 🌐 WebSocket Client - Bybit Strategy Tester v2
 *
 * Robust WebSocket client with automatic reconnection,
 * exponential backoff, heartbeat, and event handling.
 *
 * Fixes P1-5: WebSocket without reconnection
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

// ============================================
// WEBSOCKET STATE CONSTANTS
// ============================================

export const WS_STATE = {
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3
};

export const WS_EVENTS = {
    CONNECT: 'connect',
    DISCONNECT: 'disconnect',
    RECONNECT: 'reconnect',
    MESSAGE: 'message',
    ERROR: 'error',
    STATE_CHANGE: 'stateChange'
};

// ============================================
// WEBSOCKET CLIENT CLASS
// ============================================

/**
 * WebSocket Client with automatic reconnection
 *
 * @example
 * const ws = new WebSocketClient('wss://stream.bybit.com/v5/public/linear');
 *
 * ws.on('message', (data) => console.log('Received:', data));
 * ws.on('connect', () => console.log('Connected!'));
 *
 * ws.connect();
 *
 * // Subscribe to topics
 * ws.subscribe(['orderbook.50.BTCUSDT', 'trade.BTCUSDT']);
 */
export class WebSocketClient {
    /**
   * @param {string} url - WebSocket URL
   * @param {Object} options - Configuration options
   */
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            // Reconnection settings
            reconnect: options.reconnect !== false,
            reconnectInterval: options.reconnectInterval || 1000,
            maxReconnectInterval: options.maxReconnectInterval || 30000,
            reconnectDecay: options.reconnectDecay || 1.5,
            maxReconnectAttempts: options.maxReconnectAttempts || 20,

            // Heartbeat/ping settings
            heartbeatInterval: options.heartbeatInterval || 20000,
            heartbeatMessage:
        options.heartbeatMessage || JSON.stringify({ op: 'ping' }),

            // Message queue settings
            queueMessages: options.queueMessages !== false,
            maxQueueSize: options.maxQueueSize || 100,

            // Debug
            debug: options.debug || false
        };

        // Internal state
        this._ws = null;
        this._reconnectAttempts = 0;
        this._reconnectTimeout = null;
        this._heartbeatInterval = null;
        this._lastPongTime = null;
        this._messageQueue = [];
        this._subscriptions = new Set();
        this._listeners = new Map();
        this._state = WS_STATE.CLOSED;
        this._manualClose = false;

        // Bind methods
        this._onOpen = this._onOpen.bind(this);
        this._onClose = this._onClose.bind(this);
        this._onError = this._onError.bind(this);
        this._onMessage = this._onMessage.bind(this);
    }

    // ============================================
    // PUBLIC METHODS
    // ============================================

    /**
   * Connect to WebSocket server
   * @returns {WebSocketClient}
   */
    connect() {
        if (
            this._ws &&
      (this._state === WS_STATE.CONNECTING || this._state === WS_STATE.OPEN)
        ) {
            this._log('Already connected or connecting');
            return this;
        }

        this._manualClose = false;
        this._setState(WS_STATE.CONNECTING);

        try {
            this._ws = new WebSocket(this.url);
            this._ws.onopen = this._onOpen;
            this._ws.onclose = this._onClose;
            this._ws.onerror = this._onError;
            this._ws.onmessage = this._onMessage;
        } catch (error) {
            this._log('Connection error:', error);
            this._emit(WS_EVENTS.ERROR, error);
            this._scheduleReconnect();
        }

        return this;
    }

    /**
   * Disconnect from WebSocket server
   * @param {number} code - Close code
   * @param {string} reason - Close reason
   */
    disconnect(code = 1000, reason = 'Manual disconnect') {
        this._manualClose = true;
        this._clearTimers();
        this._reconnectAttempts = 0;

        if (this._ws) {
            this._ws.close(code, reason);
        }

        this._setState(WS_STATE.CLOSED);
    }

    /**
   * Send message (queues if not connected)
   * @param {string|Object} message - Message to send
   * @returns {boolean} - True if sent immediately
   */
    send(message) {
        const data =
      typeof message === 'string' ? message : JSON.stringify(message);

        if (this._state === WS_STATE.OPEN && this._ws) {
            this._ws.send(data);
            this._log('Sent:', data);
            return true;
        }

        // Queue message for later
        if (this.options.queueMessages) {
            if (this._messageQueue.length < this.options.maxQueueSize) {
                this._messageQueue.push(data);
                this._log('Queued message:', data);
            } else {
                this._log('Message queue full, dropping:', data);
            }
        }

        return false;
    }

    /**
   * Subscribe to topics (Bybit-specific)
   * @param {string[]} topics - Topics to subscribe
   */
    subscribe(topics) {
        const normalizedTopics = Array.isArray(topics) ? topics : [topics];

        // Track subscriptions for reconnect
        normalizedTopics.forEach((t) => this._subscriptions.add(t));

        // Send subscribe message
        this.send({
            op: 'subscribe',
            args: normalizedTopics
        });
    }

    /**
   * Unsubscribe from topics
   * @param {string[]} topics - Topics to unsubscribe
   */
    unsubscribe(topics) {
        const normalizedTopics = Array.isArray(topics) ? topics : [topics];

        // Remove from tracking
        normalizedTopics.forEach((t) => this._subscriptions.delete(t));

        // Send unsubscribe message
        this.send({
            op: 'unsubscribe',
            args: normalizedTopics
        });
    }

    /**
   * Get current connection state
   * @returns {number} WS_STATE value
   */
    getState() {
        return this._state;
    }

    /**
   * Check if connected
   * @returns {boolean}
   */
    isConnected() {
        return this._state === WS_STATE.OPEN;
    }

    /**
   * Get subscriptions
   * @returns {string[]}
   */
    getSubscriptions() {
        return Array.from(this._subscriptions);
    }

    // ============================================
    // EVENT HANDLING
    // ============================================

    /**
   * Add event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function
   * @returns {Function} - Remove listener function
   */
    on(event, callback) {
        if (!this._listeners.has(event)) {
            this._listeners.set(event, new Set());
        }
        this._listeners.get(event).add(callback);

        return () => this.off(event, callback);
    }

    /**
   * Remove event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback to remove
   */
    off(event, callback) {
        const listeners = this._listeners.get(event);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    /**
   * Add one-time event listener
   * @param {string} event - Event name
   * @param {Function} callback - Callback function
   */
    once(event, callback) {
        const wrapper = (...args) => {
            this.off(event, wrapper);
            callback(...args);
        };
        this.on(event, wrapper);
    }

    // ============================================
    // INTERNAL EVENT HANDLERS
    // ============================================

    /**
   * Handle WebSocket open
   * @private
   */
    _onOpen() {
        this._log('Connected');
        this._setState(WS_STATE.OPEN);
        this._reconnectAttempts = 0;

        // Start heartbeat
        this._startHeartbeat();

        // Flush message queue
        this._flushQueue();

        // Resubscribe to topics
        this._resubscribe();

        // Emit events
        if (this._reconnectAttempts > 0) {
            this._emit(WS_EVENTS.RECONNECT, this._reconnectAttempts);
        }
        this._emit(WS_EVENTS.CONNECT);
    }

    /**
   * Handle WebSocket close
   * @private
   */
    _onClose(event) {
        this._log('Disconnected:', event.code, event.reason);
        this._clearTimers();
        this._setState(WS_STATE.CLOSED);

        this._emit(WS_EVENTS.DISCONNECT, {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
        });

        // Attempt reconnection
        if (!this._manualClose && this.options.reconnect) {
            this._scheduleReconnect();
        }
    }

    /**
   * Handle WebSocket error
   * @private
   */
    _onError(error) {
        this._log('Error:', error);
        this._emit(WS_EVENTS.ERROR, error);
    }

    /**
   * Handle WebSocket message
   * @private
   */
    _onMessage(event) {
        try {
            const data = JSON.parse(event.data);

            // Handle pong response
            if (data.op === 'pong' || data.ret_msg === 'pong') {
                this._lastPongTime = Date.now();
                this._log('Pong received');
                return;
            }

            // Handle subscription confirmation
            if (data.op === 'subscribe' && data.success) {
                this._log('Subscription confirmed:', data.req_id);
                return;
            }

            this._emit(WS_EVENTS.MESSAGE, data);
        } catch (error) {
            // Non-JSON message
            this._emit(WS_EVENTS.MESSAGE, event.data);
        }
    }

    // ============================================
    // RECONNECTION LOGIC
    // ============================================

    /**
   * Schedule reconnection with exponential backoff
   * @private
   */
    _scheduleReconnect() {
        if (this._reconnectAttempts >= this.options.maxReconnectAttempts) {
            this._log('Max reconnection attempts reached');
            this._emit(
                WS_EVENTS.ERROR,
                new Error('Max reconnection attempts reached')
            );
            return;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
            this.options.reconnectInterval *
        Math.pow(this.options.reconnectDecay, this._reconnectAttempts),
            this.options.maxReconnectInterval
        );

        this._reconnectAttempts++;
        this._log(
            `Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts}/${this.options.maxReconnectAttempts})`
        );

        this._reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
   * Resubscribe to all topics after reconnect
   * @private
   */
    _resubscribe() {
        if (this._subscriptions.size > 0) {
            this._log('Resubscribing to:', Array.from(this._subscriptions));
            this.send({
                op: 'subscribe',
                args: Array.from(this._subscriptions)
            });
        }
    }

    // ============================================
    // HEARTBEAT
    // ============================================

    /**
   * Start heartbeat interval
   * @private
   */
    _startHeartbeat() {
        this._clearHeartbeat();
        this._lastPongTime = Date.now();

        this._heartbeatInterval = setInterval(() => {
            // Check for stale connection
            if (
                Date.now() - this._lastPongTime >
        this.options.heartbeatInterval * 2
            ) {
                this._log('Connection stale, reconnecting...');
                this._ws?.close(4000, 'Heartbeat timeout');
                return;
            }

            // Send ping
            this.send(this.options.heartbeatMessage);
        }, this.options.heartbeatInterval);
    }

    /**
   * Clear heartbeat interval
   * @private
   */
    _clearHeartbeat() {
        if (this._heartbeatInterval) {
            clearInterval(this._heartbeatInterval);
            this._heartbeatInterval = null;
        }
    }

    // ============================================
    // UTILITY METHODS
    // ============================================

    /**
   * Flush queued messages
   * @private
   */
    _flushQueue() {
        while (this._messageQueue.length > 0 && this._state === WS_STATE.OPEN) {
            const message = this._messageQueue.shift();
            this._ws.send(message);
            this._log('Sent queued:', message);
        }
    }

    /**
   * Clear all timers
   * @private
   */
    _clearTimers() {
        this._clearHeartbeat();

        if (this._reconnectTimeout) {
            clearTimeout(this._reconnectTimeout);
            this._reconnectTimeout = null;
        }
    }

    /**
   * Set state and emit event
   * @private
   */
    _setState(state) {
        const oldState = this._state;
        this._state = state;

        if (oldState !== state) {
            this._emit(WS_EVENTS.STATE_CHANGE, { oldState, newState: state });
        }
    }

    /**
   * Emit event to all listeners
   * @private
   */
    _emit(event, data = null) {
        const listeners = this._listeners.get(event);
        if (listeners) {
            listeners.forEach((callback) => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[WebSocketClient] Error in ${event} listener:`, error);
                }
            });
        }
    }

    /**
   * Debug logging
   * @private
   */
    _log(...args) {
        if (this.options.debug) {
            console.log('[WebSocketClient]', ...args);
        }
    }
}

// ============================================
// BYBIT-SPECIFIC CLIENT
// ============================================

/**
 * Pre-configured client for Bybit WebSocket API
 */
export class BybitWebSocketClient extends WebSocketClient {
    constructor(options = {}) {
        const url = options.testnet
            ? 'wss://stream-testnet.bybit.com/v5/public/linear'
            : 'wss://stream.bybit.com/v5/public/linear';

        super(url, {
            heartbeatInterval: 20000,
            heartbeatMessage: JSON.stringify({ op: 'ping' }),
            debug: options.debug,
            ...options
        });
    }

    /**
   * Subscribe to orderbook
   * @param {string} symbol - Trading pair
   * @param {number} depth - Orderbook depth (1, 50, 200, 500)
   */
    subscribeOrderbook(symbol, depth = 50) {
        this.subscribe([`orderbook.${depth}.${symbol}`]);
    }

    /**
   * Subscribe to trades
   * @param {string} symbol - Trading pair
   */
    subscribeTrades(symbol) {
        this.subscribe([`publicTrade.${symbol}`]);
    }

    /**
   * Subscribe to kline/candlestick
   * @param {string} symbol - Trading pair
   * @param {string} interval - Interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, M, W)
   */
    subscribeKline(symbol, interval) {
        this.subscribe([`kline.${interval}.${symbol}`]);
    }

    /**
   * Subscribe to ticker
   * @param {string} symbol - Trading pair
   */
    subscribeTicker(symbol) {
        this.subscribe([`tickers.${symbol}`]);
    }
}

// ============================================
// EXPORTS
// ============================================

export default WebSocketClient;

// Attach to window for non-module scripts
if (typeof window !== 'undefined') {
    window.WebSocketClient = WebSocketClient;
    window.BybitWebSocketClient = BybitWebSocketClient;
    window.WS_STATE = WS_STATE;
    window.WS_EVENTS = WS_EVENTS;
}
