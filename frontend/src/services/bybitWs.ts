// Lightweight Bybit WebSocket client for public kline updates (v5)
// Docs: https://bybit-exchange.github.io/docs/v5/websocket/public/kline

export type BybitKline = {
  start: number; // ms
  end?: number; // ms
  interval: string; // '1', '3', '5', ...
  open: string; // numeric string
  high: string;
  low: string;
  close: string;
  volume?: string;
  turnover?: string;
  confirm?: boolean; // true if candle closed
  // some payloads use other keys; we stick to v5 format
};

export type KlineUpdate = {
  time: number; // seconds (for lightweight-charts)
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  confirm: boolean;
};

export type Unsubscribe = () => void;

const WS_ENDPOINT = 'wss://stream.bybit.com/v5/public/linear';

export function subscribeKline(
  symbol: string,
  interval: string,
  onUpdate: (update: KlineUpdate) => void,
  onStatus?: (status: 'connecting' | 'open' | 'closed' | 'error', info?: any) => void
): Unsubscribe {
  let ws: WebSocket | null = null;
  let closedByUser = false;

  const topic = `kline.${interval}.${symbol.toUpperCase()}`;

  const connect = () => {
    onStatus?.('connecting');
    ws = new WebSocket(WS_ENDPOINT);

    ws.onopen = () => {
      onStatus?.('open');
      const subMsg = JSON.stringify({ op: 'subscribe', args: [topic] });
      ws?.send(subMsg);
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string);
        // Expected shape: { topic: 'kline.1.BTCUSDT', data: [ { start, open, high, low, close, confirm, volume, ... } ] }
        if (!msg || msg.topic !== topic || !msg.data) return;
        const arr = Array.isArray(msg.data) ? msg.data : [msg.data];
        for (const k of arr) {
          const startMs = Number(k.start ?? k.t ?? 0);
          if (!startMs) continue;
          const upd: KlineUpdate = {
            time: Math.floor(startMs / 1000),
            open: Number(k.open),
            high: Number(k.high),
            low: Number(k.low),
            close: Number(k.close),
            volume: k.volume != null ? Number(k.volume) : undefined,
            confirm: Boolean(k.confirm),
          };
          onUpdate(upd);
        }
      } catch (e) {
        onStatus?.('error', e);
      }
    };

    ws.onerror = (e) => {
      onStatus?.('error', e);
    };

    ws.onclose = () => {
      onStatus?.('closed');
      if (!closedByUser) {
        // backoff retry in 2s
        setTimeout(connect, 2000);
      }
    };
  };

  connect();

  return () => {
    closedByUser = true;
    try {
      ws?.close();
    } catch {}
    ws = null;
  };
}
