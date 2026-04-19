/**
 * WebSocketClient.js Unit Tests
 *
 * Covers bug fixed in B-01:
 *   B-01 — RECONNECT event must fire after reconnection
 *          (previously _reconnectAttempts was reset before the check → always false)
 *
 * Uses a fake WebSocket implementation to avoid real network connections.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketClient, WS_EVENTS } from '../../js/core/WebSocketClient.js';

// ─── Fake WebSocket ────────────────────────────────────────────────────────────
class FakeWebSocket {
    constructor(url) {
        this.url = url;
        this.readyState = 0; // CONNECTING
        this.onopen = null;
        this.onclose = null;
        this.onmessage = null;
        this.onerror = null;
        this.sentMessages = [];
        FakeWebSocket.lastInstance = this;
    }

    send(data) { this.sentMessages.push(data); }
    close(code, reason) {
        this.readyState = 3; // CLOSED
        this.onclose?.({ code: code || 1000, reason: reason || '', wasClean: true });
    }

    // Test helpers
    triggerOpen() {
        this.readyState = 1;
        this.onopen?.();
    }
    triggerMessage(data) {
        this.onmessage?.({ data: JSON.stringify(data) });
    }
    triggerError(err = new Error('ws error')) {
        this.onerror?.(err);
    }
    triggerClose(code = 1006, reason = '') {
        this.readyState = 3;
        this.onclose?.({ code, reason, wasClean: false });
    }
}

// ─── setup ────────────────────────────────────────────────────────────────────
beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeWebSocket);
});

function makeClient(opts = {}) {
    return new WebSocketClient('wss://test.local', {
        reconnect: true,
        reconnectInterval: 100,
        maxReconnectAttempts: 5,
        heartbeatInterval: 9999999, // disable heartbeat for tests
        ...opts
    });
}

// ─── B-01: RECONNECT event ────────────────────────────────────────────────────
describe('WebSocketClient RECONNECT event (B-01)', () => {
    it('does NOT emit RECONNECT on the first connection', () => {
        const client = makeClient();
        const reconnectHandler = vi.fn();
        client.on(WS_EVENTS.RECONNECT, reconnectHandler);

        client.connect();
        FakeWebSocket.lastInstance.triggerOpen();

        expect(reconnectHandler).not.toHaveBeenCalled();
    });

    it('emits RECONNECT with attempt count after a reconnection', () => {
        const client = makeClient();
        const reconnectHandler = vi.fn();
        const connectHandler = vi.fn();
        client.on(WS_EVENTS.RECONNECT, reconnectHandler);
        client.on(WS_EVENTS.CONNECT, connectHandler);

        // Initial connect
        client.connect();
        const ws1 = FakeWebSocket.lastInstance;
        ws1.triggerOpen();
        expect(reconnectHandler).not.toHaveBeenCalled();

        // Simulate disconnect → triggers reconnect scheduling
        ws1.triggerClose(1006);

        // Advance past reconnect interval so the new WebSocket is created
        vi.advanceTimersByTime(200);
        const ws2 = FakeWebSocket.lastInstance;
        expect(ws2).not.toBe(ws1); // new socket created

        // Open the new socket → should fire RECONNECT
        ws2.triggerOpen();

        expect(reconnectHandler).toHaveBeenCalledTimes(1);
        // The argument must be the attempt count (≥ 1)
        expect(reconnectHandler.mock.calls[0][0]).toBeGreaterThanOrEqual(1);

        // CONNECT must also fire
        expect(connectHandler).toHaveBeenCalledTimes(2); // initial + after reconnect
    });

    it('resets reconnect counter to 0 after successful reconnection', () => {
        const client = makeClient();
        client.connect();
        FakeWebSocket.lastInstance.triggerOpen();

        // Disconnect and reconnect
        FakeWebSocket.lastInstance.triggerClose(1006);
        vi.advanceTimersByTime(200);
        FakeWebSocket.lastInstance.triggerOpen();

        // Internal counter must be 0 after successful open
        expect(client._reconnectAttempts).toBe(0);
    });
});

// ─── connect / disconnect lifecycle ──────────────────────────────────────────
describe('WebSocketClient lifecycle', () => {
    it('emits CONNECT on first open', () => {
        const client = makeClient();
        const handler = vi.fn();
        client.on(WS_EVENTS.CONNECT, handler);

        client.connect();
        FakeWebSocket.lastInstance.triggerOpen();

        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('emits DISCONNECT on close', () => {
        const client = makeClient();
        const handler = vi.fn();
        client.on(WS_EVENTS.DISCONNECT, handler);

        client.connect();
        FakeWebSocket.lastInstance.triggerOpen();
        FakeWebSocket.lastInstance.triggerClose(1001, 'Going away');

        expect(handler).toHaveBeenCalledTimes(1);
        expect(handler.mock.calls[0][0]).toMatchObject({ code: 1001 });
    });

    it('sends queued messages after open', () => {
        const client = makeClient();
        client.connect();

        // Send before open — goes into queue
        client.send({ op: 'subscribe', args: ['topic'] });
        expect(FakeWebSocket.lastInstance.sentMessages).toHaveLength(0);

        // Open flushes queue
        FakeWebSocket.lastInstance.triggerOpen();
        expect(FakeWebSocket.lastInstance.sentMessages).toHaveLength(1);
    });
});
