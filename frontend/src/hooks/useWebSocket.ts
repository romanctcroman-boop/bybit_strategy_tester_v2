/**
 * Custom React Hook for WebSocket Real-Time Analytics
 *
 * Features:
 * - Auto-reconnect on connection loss
 * - Heartbeat/ping to keep connection alive
 * - Type-safe message handling
 * - Connection state management
 * - Error handling with exponential backoff
 *
 * Usage:
 * ```tsx
 * const {
 *   isConnected,
 *   data,
 *   error,
 *   sendMessage
 * } = useWebSocket(backtestId);
 * ```
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

export interface WebSocketMessage {
  type: string;
  data: any;
}

export interface WebSocketOptions {
  /** Автоматический reconnect при разрыве соединения */
  autoReconnect?: boolean;

  /** Максимальное количество попыток reconnect */
  maxReconnectAttempts?: number;

  /** Задержка между попытками reconnect (ms) */
  reconnectDelay?: number;

  /** Отправлять ping каждые X ms для поддержания соединения */
  heartbeatInterval?: number;

  /** Debug mode (console logs) */
  debug?: boolean;
}

export interface UseWebSocketReturn {
  /** Статус подключения */
  isConnected: boolean;

  /** Последнее полученное сообщение */
  lastMessage: WebSocketMessage | null;

  /** Все полученные сообщения */
  messages: WebSocketMessage[];

  /** Ошибка подключения */
  error: string | null;

  /** Отправить сообщение на сервер */
  sendMessage: (message: any) => void;

  /** Переподключиться вручную */
  reconnect: () => void;

  /** Закрыть соединение */
  disconnect: () => void;
}

// ============================================================================
// WebSocket Hook
// ============================================================================

export function useWebSocket(
  backtestId: number | null,
  options: WebSocketOptions = {}
): UseWebSocketReturn {
  const {
    autoReconnect = true,
    maxReconnectAttempts = 5,
    reconnectDelay = 3000,
    heartbeatInterval = 30000,
    debug = false,
  } = options;

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Refs для сохранения между re-renders
  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();
  const heartbeatTimeout = useRef<ReturnType<typeof setInterval>>();

  // ============================================================================
  // WebSocket URL Construction
  // ============================================================================

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    // Если подключаемся к конкретному бэктесту
    if (backtestId !== null) {
      return `${protocol}//${host}/api/v1/ws/analytics/${backtestId}`;
    }

    // Глобальное подключение (все события)
    return `${protocol}//${host}/api/v1/ws/analytics`;
  }, [backtestId]);

  // ============================================================================
  // WebSocket Connection Management
  // ============================================================================

  const log = (...args: any[]) => {
    if (debug) {
      console.log('[WebSocket]', ...args);
    }
  };

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      log('Already connected');
      return;
    }

    const url = getWebSocketUrl();
    log('Connecting to:', url);

    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        log('Connected ✅');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;

        // Запустить heartbeat
        startHeartbeat();
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          log('Received message:', message.type);

          setLastMessage(message);
          setMessages((prev) => [...prev, message]);
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.current.onerror = (event) => {
        console.error('[WebSocket] Error:', event);
        setError('WebSocket connection error');
      };

      ws.current.onclose = (event) => {
        log('Disconnected', { code: event.code, reason: event.reason });
        setIsConnected(false);
        stopHeartbeat();

        // Auto-reconnect
        if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          const delay = reconnectDelay * reconnectAttempts.current;

          log(
            `Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`
          );

          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Max reconnect attempts reached');
        }
      };
    } catch (err) {
      console.error('[WebSocket] Failed to create connection:', err);
      setError('Failed to create WebSocket connection');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getWebSocketUrl, autoReconnect, maxReconnectAttempts, reconnectDelay]);

  const disconnect = useCallback(() => {
    log('Disconnecting...');

    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }

    stopHeartbeat();

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setIsConnected(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttempts.current = 0;
    connect();
  }, [connect, disconnect]);

  // ============================================================================
  // Heartbeat (keep-alive ping)
  // ============================================================================

  const startHeartbeat = () => {
    stopHeartbeat();

    heartbeatTimeout.current = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        log('Sending ping...');
        ws.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, heartbeatInterval);
  };

  const stopHeartbeat = () => {
    if (heartbeatTimeout.current) {
      clearInterval(heartbeatTimeout.current);
      heartbeatTimeout.current = undefined;
    }
  };

  // ============================================================================
  // Send Message
  // ============================================================================

  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const payload = typeof message === 'string' ? message : JSON.stringify(message);
      log('Sending message:', message);
      ws.current.send(payload);
    } else {
      console.warn('[WebSocket] Cannot send message: not connected');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================================================
  // Lifecycle
  // ============================================================================

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backtestId]); // Reconnect when backtestId changes

  // ============================================================================
  // Return
  // ============================================================================

  return {
    isConnected,
    lastMessage,
    messages,
    error,
    sendMessage,
    reconnect,
    disconnect,
  };
}

// ============================================================================
// Typed Message Hooks (для удобства)
// ============================================================================

/**
 * Hook для фильтрации сообщений определённого типа
 *
 * Usage:
 * ```tsx
 * const equityUpdates = useWebSocketMessages(messages, 'equity_update');
 * ```
 */
export function useWebSocketMessages<T = any>(
  messages: WebSocketMessage[],
  messageType: string
): T[] {
  return messages.filter((msg) => msg.type === messageType).map((msg) => msg.data as T);
}

/**
 * Hook для получения последнего сообщения определённого типа
 *
 * Usage:
 * ```tsx
 * const lastEquityUpdate = useLastWebSocketMessage(messages, 'equity_update');
 * ```
 */
export function useLastWebSocketMessage<T = any>(
  messages: WebSocketMessage[],
  messageType: string
): T | null {
  const filtered = useWebSocketMessages<T>(messages, messageType);
  return filtered.length > 0 ? filtered[filtered.length - 1] : null;
}
