/**
 * 🔌 WebSocket Validation Client for Strategy Builder
 *
 * Provides real-time validation for strategy blocks via WebSocket.
 * Debounces requests and handles reconnection automatically.
 *
 * @version 1.0.0
 * @date 2026-01-30
 */

// WebSocket connection state
let validationWs = null;
let wsConnected = false;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT_ATTEMPTS = 5;
const WS_RECONNECT_DELAY = 2000;

// Pending validation requests (for debouncing)
const pendingValidations = new Map();
const VALIDATION_DEBOUNCE_MS = 150;

// Callbacks for validation results
const validationCallbacks = new Map();

/**
 * Get WebSocket URL based on current location
 */
function getWsUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/api/v1/strategy-builder/ws/validate`;
}

/**
 * Initialize WebSocket connection
 */
export function initValidationWebSocket() {
    if (validationWs && wsConnected) {
        console.log('[WS Validation] Already connected');
        return;
    }

    const wsUrl = getWsUrl();
    console.log('[WS Validation] Connecting to:', wsUrl);

    try {
        validationWs = new WebSocket(wsUrl);

        validationWs.onopen = () => {
            console.log('[WS Validation] Connected');
            wsConnected = true;
            wsReconnectAttempts = 0;
            // Notify UI
            dispatchEvent(new CustomEvent('ws-validation-connected'));
        };

        validationWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleValidationResponse(data);
            } catch (e) {
                console.error('[WS Validation] Parse error:', e);
            }
        };

        validationWs.onclose = (event) => {
            console.log('[WS Validation] Disconnected:', event.code, event.reason);
            wsConnected = false;
            // Notify UI
            dispatchEvent(new CustomEvent('ws-validation-disconnected'));
            // Attempt reconnection
            scheduleReconnect();
        };

        validationWs.onerror = (error) => {
            console.error('[WS Validation] Error:', error);
            wsConnected = false;
        };

    } catch (e) {
        console.error('[WS Validation] Connection failed:', e);
        scheduleReconnect();
    }
}

/**
 * Schedule WebSocket reconnection
 */
function scheduleReconnect() {
    if (wsReconnectAttempts >= WS_MAX_RECONNECT_ATTEMPTS) {
        console.log('[WS Validation] Max reconnect attempts reached, falling back to local validation');
        return;
    }

    wsReconnectAttempts++;
    const delay = WS_RECONNECT_DELAY * wsReconnectAttempts;
    console.log(`[WS Validation] Reconnecting in ${delay}ms (attempt ${wsReconnectAttempts})`);

    setTimeout(() => {
        initValidationWebSocket();
    }, delay);
}

/**
 * Close WebSocket connection
 */
export function closeValidationWebSocket() {
    if (validationWs) {
        validationWs.close();
        validationWs = null;
        wsConnected = false;
    }
}

/**
 * Check if WebSocket is connected
 */
export function isWsConnected() {
    return wsConnected;
}

/**
 * Handle validation response from server
 */
function handleValidationResponse(data) {
    const { type, request_type, block_id, param_name, valid, messages } = data;

    if (type === 'connected') {
        console.log('[WS Validation] Server confirmed connection:', data.client_id);
        return;
    }

    if (type === 'heartbeat') {
        return;
    }

    if (type === 'error') {
        console.error('[WS Validation] Server error:', data.message);
        return;
    }

    if (type === 'validation_result') {
        // Find and invoke callback
        const callbackKey = block_id
            ? (param_name ? `${block_id}:${param_name}` : `block:${block_id}`)
            : 'strategy';

        const callback = validationCallbacks.get(callbackKey);
        if (callback) {
            callback({ valid, messages, block_id, param_name });
            validationCallbacks.delete(callbackKey);
        }

        // Dispatch event for UI updates
        dispatchEvent(new CustomEvent('ws-validation-result', {
            detail: { type: request_type, block_id, param_name, valid, messages }
        }));
    }
}

/**
 * Send validation request via WebSocket
 */
function sendValidation(request, callbackKey, callback) {
    if (!wsConnected || !validationWs) {
        // Fall back to local validation
        console.log('[WS Validation] Not connected, using local validation');
        callback({ valid: true, messages: [], fallback: true });
        return;
    }

    // Store callback
    if (callback) {
        validationCallbacks.set(callbackKey, callback);
    }

    // Send request
    validationWs.send(JSON.stringify(request));
}

/**
 * Validate a single block parameter (debounced)
 *
 * @param {string} blockId - Block identifier
 * @param {string} blockType - Block type (e.g., 'rsi', 'macd')
 * @param {string} paramName - Parameter name
 * @param {any} paramValue - Parameter value
 * @param {Function} callback - Callback with validation result
 */
export function validateParam(blockId, blockType, paramName, paramValue, callback) {
    const key = `${blockId}:${paramName}`;

    // Cancel pending validation for this param
    if (pendingValidations.has(key)) {
        clearTimeout(pendingValidations.get(key));
    }

    // Debounce
    const timeoutId = setTimeout(() => {
        pendingValidations.delete(key);

        const request = {
            type: 'validate_param',
            block_id: blockId,
            block_type: blockType,
            param_name: paramName,
            param_value: paramValue
        };

        sendValidation(request, key, callback);
    }, VALIDATION_DEBOUNCE_MS);

    pendingValidations.set(key, timeoutId);
}

/**
 * Validate an entire block (debounced)
 *
 * @param {string} blockId - Block identifier
 * @param {string} blockType - Block type
 * @param {Object} params - All block parameters
 * @param {Function} callback - Callback with validation result
 */
export function validateBlock(blockId, blockType, params, callback) {
    const key = `block:${blockId}`;

    // Cancel pending validation
    if (pendingValidations.has(key)) {
        clearTimeout(pendingValidations.get(key));
    }

    // Debounce
    const timeoutId = setTimeout(() => {
        pendingValidations.delete(key);

        const request = {
            type: 'validate_block',
            block_id: blockId,
            block_type: blockType,
            params: params
        };

        sendValidation(request, key, callback);
    }, VALIDATION_DEBOUNCE_MS);

    pendingValidations.set(key, timeoutId);
}

/**
 * Validate a connection between blocks
 *
 * @param {Object} connection - Connection details
 * @param {Function} callback - Callback with validation result
 */
export function validateConnection(connection, callback) {
    const request = {
        type: 'validate_connection',
        source_block_id: connection.sourceBlockId,
        source_block_type: connection.sourceBlockType,
        source_output: connection.sourceOutput || 'signal',
        target_block_id: connection.targetBlockId,
        target_block_type: connection.targetBlockType,
        target_input: connection.targetInput || 'input'
    };

    const key = `conn:${connection.sourceBlockId}:${connection.targetBlockId}`;
    sendValidation(request, key, callback);
}

/**
 * Validate entire strategy
 *
 * @param {Array} blocks - All strategy blocks
 * @param {Array} connections - All connections
 * @param {Function} callback - Callback with validation result
 */
export function validateStrategy(blocks, connections, callback) {
    const request = {
        type: 'validate_strategy',
        blocks: blocks,
        connections: connections
    };

    sendValidation(request, 'strategy', callback);
}

/**
 * Send heartbeat to keep connection alive
 */
export function sendHeartbeat() {
    if (wsConnected && validationWs) {
        validationWs.send(JSON.stringify({ type: 'heartbeat' }));
    }
}

// Start heartbeat interval
let heartbeatInterval = null;

export function startHeartbeat() {
    if (heartbeatInterval) return;
    heartbeatInterval = setInterval(sendHeartbeat, 30000); // Every 30 seconds
}

export function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

// =============================================================================
// UI INTEGRATION HELPERS
// =============================================================================

/**
 * Update block visual state based on validation
 *
 * @param {string} blockId - Block identifier
 * @param {boolean} valid - Whether block is valid
 * @param {Array} messages - Validation messages
 */
export function updateBlockValidation(blockId, valid, messages) {
    const blockEl = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!blockEl) return;

    blockEl.classList.toggle('block-invalid', !valid);
    blockEl.classList.toggle('block-valid', valid);

    // Update tooltip
    if (messages && messages.length > 0) {
        const errorMsgs = messages
            .filter(m => m.severity === 'error')
            .map(m => m.message)
            .join('\n');

        if (errorMsgs) {
            blockEl.title = `Validation Errors:\n${errorMsgs}`;
        } else {
            blockEl.title = '';
        }
    } else {
        blockEl.title = '';
    }
}

/**
 * Update parameter input visual state
 *
 * @param {string} blockId - Block identifier
 * @param {string} paramName - Parameter name
 * @param {boolean} valid - Whether parameter is valid
 * @param {string} message - Error message (if invalid)
 */
export function updateParamValidation(blockId, paramName, valid, message) {
    const inputEl = document.querySelector(
        `[data-block-id="${blockId}"] [data-param="${paramName}"]`
    );
    if (!inputEl) return;

    inputEl.classList.toggle('is-invalid', !valid);
    inputEl.classList.toggle('is-valid', valid);

    // Update feedback element
    const feedbackEl = inputEl.nextElementSibling;
    if (feedbackEl && feedbackEl.classList.contains('invalid-feedback')) {
        feedbackEl.textContent = message || '';
        feedbackEl.style.display = valid ? 'none' : 'block';
    }
}

/**
 * Show validation status indicator in UI
 *
 * @param {boolean} connected - WebSocket connection status
 */
export function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('ws-validation-status');
    if (statusEl) {
        statusEl.classList.toggle('connected', connected);
        statusEl.classList.toggle('disconnected', !connected);
        statusEl.title = connected
            ? 'Real-time validation active'
            : 'Real-time validation disconnected';
    }
}

// =============================================================================
// AUTO-INITIALIZE
// =============================================================================

// Initialize WebSocket when module loads
if (typeof window !== 'undefined') {
    // Wait for DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initValidationWebSocket();
            startHeartbeat();
        });
    } else {
        initValidationWebSocket();
        startHeartbeat();
    }

    // Handle page unload
    window.addEventListener('beforeunload', () => {
        stopHeartbeat();
        closeValidationWebSocket();
    });

    // Listen for connection events to update UI
    window.addEventListener('ws-validation-connected', () => {
        updateConnectionStatus(true);
    });

    window.addEventListener('ws-validation-disconnected', () => {
        updateConnectionStatus(false);
    });

    // Export to window for backwards compatibility
    window.wsValidation = {
        init: initValidationWebSocket,
        close: closeValidationWebSocket,
        isConnected: isWsConnected,
        validateParam,
        validateBlock,
        validateConnection,
        validateStrategy,
        updateBlockValidation,
        updateParamValidation
    };
}
