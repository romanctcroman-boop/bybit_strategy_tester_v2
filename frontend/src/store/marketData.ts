import { create } from 'zustand';
import { DataApi } from '../services/api';
import { subscribeKline, KlineUpdate, Unsubscribe } from '../services/bybitWs';

export type Candle = { time: number; open: number; high: number; low: number; close: number; volume?: number };

type Key = string; // `${symbol}:${interval}`

function makeKey(symbol: string, interval: string): Key {
  return `${symbol.toUpperCase()}:${interval}`;
}

type MarketDataState = {
  currentSymbol: string;
  currentInterval: string;
  loading: boolean;
  error: string | null;
  // closed candles cache per key
  candles: Record<Key, Candle[]>;
  // optional forming candle per key
  forming: Record<Key, Candle | null>;
  // active websocket unsubscribe per key (only current key should be active)
  ws: Record<Key, Unsubscribe | null>;
  // actions
  initialize: (symbol?: string, interval?: string) => Promise<void>;
  switchInterval: (interval: string, limit?: number) => Promise<void>;
  loadCandles: (symbol: string, interval: string, limit?: number) => Promise<Candle[]>;
  getMergedCandles: (symbol?: string, interval?: string) => Candle[];
};

const MAX_CLOSED_CACHE = 1200; // keep up to N closed bars per key

export const useMarketDataStore = create<MarketDataState>((set, get) => ({
  currentSymbol: 'BTCUSDT',
  currentInterval: '15',
  loading: false,
  error: null,
  candles: {},
  forming: {},
  ws: {},

  loadCandles: async (symbol: string, interval: string, limit: number = 500) => {
    set({ loading: true, error: null });
    try {
  // Prefer backend working set API to ensure 1000-load/500-RAM policy server-side
  const data = await DataApi.bybitWorkingSet(symbol, interval, Math.max(100, Math.min(1000, limit)));
      const key = makeKey(symbol, interval);
      // ensure ascending order & numeric
      const sorted = [...data].sort((a, b) => a.time - b.time);
      // dedupe any duplicate timestamps from REST (some APIs include the forming bar)
      const dedup: Candle[] = [];
      let lastTime: number | null = null;
      for (const c of sorted) {
        const t = c.time;
        if (lastTime === null || t > lastTime) {
          dedup.push(c);
          lastTime = t;
        } else if (t === lastTime) {
          // replace previous with latest values if equal time appears
          dedup[dedup.length - 1] = c;
        }
      }
      set((s) => ({ candles: { ...s.candles, [key]: dedup }, loading: false }));
      return dedup;
    } catch (e: any) {
      const msg = e?.message || 'Failed to load klines';
      set({ error: msg, loading: false });
      return [];
    }
  },

  initialize: async (symbol = 'BTCUSDT', interval = '15') => {
    const key = makeKey(symbol, interval);
    // if cache exists, use it; otherwise fetch
    const cached = get().candles[key];
    if (!cached || cached.length === 0) {
      await get().loadCandles(symbol, interval, 500);
    }
    // (re)subscribe WS for this key
    // unsubscribe any previous active ws
    const prevKey = makeKey(get().currentSymbol, get().currentInterval);
    const prevUnsub = get().ws[prevKey];
    if (prevUnsub) {
      try { prevUnsub(); } catch {}
      set((s) => ({ ws: { ...s.ws, [prevKey]: null } }));
    }
    const unsub = subscribeKline(symbol, interval, (upd: KlineUpdate) => {
      const k = makeKey(symbol, interval);
      const state = get();
      const closed = state.candles[k] || [];
      if (upd.confirm) {
        // append as closed, ensure no duplicate time
        const last = closed[closed.length - 1];
        let next: Candle[];
        const newBar: Candle = { time: upd.time, open: upd.open, high: upd.high, low: upd.low, close: upd.close, volume: upd.volume };
        if (last && last.time === upd.time) {
          next = [...closed.slice(0, -1), newBar];
        } else {
          next = [...closed, newBar];
        }
        if (next.length > MAX_CLOSED_CACHE) next = next.slice(next.length - MAX_CLOSED_CACHE);
        set((s) => ({
          candles: { ...s.candles, [k]: next },
          forming: { ...s.forming, [k]: null },
        }));
      } else {
        // forming candle for current interval window
        const forming: Candle = { time: upd.time, open: upd.open, high: upd.high, low: upd.low, close: upd.close, volume: upd.volume };
        set((s) => ({ forming: { ...s.forming, [k]: forming } }));
      }
    });
    set((s) => ({ ws: { ...s.ws, [key]: unsub }, currentSymbol: symbol, currentInterval: interval }));
  },

  switchInterval: async (interval: string, limit: number = 500) => {
    const symbol = get().currentSymbol;
    const newKey = makeKey(symbol, interval);
    // if not cached, load
    if (!get().candles[newKey] || get().candles[newKey].length === 0) {
      await get().loadCandles(symbol, interval, limit);
    }
    // unsubscribe previous
    const prevKey = makeKey(get().currentSymbol, get().currentInterval);
    const prevUnsub = get().ws[prevKey];
    if (prevUnsub) {
      try { prevUnsub(); } catch {}
      set((s) => ({ ws: { ...s.ws, [prevKey]: null } }));
    }
    // subscribe new
    const unsub = subscribeKline(symbol, interval, (upd: KlineUpdate) => {
      const k = makeKey(symbol, interval);
      const closed = get().candles[k] || [];
      if (upd.confirm) {
        const last = closed[closed.length - 1];
        const newBar: Candle = { time: upd.time, open: upd.open, high: upd.high, low: upd.low, close: upd.close, volume: upd.volume };
        let next = last && last.time === upd.time ? [...closed.slice(0, -1), newBar] : [...closed, newBar];
        if (next.length > MAX_CLOSED_CACHE) next = next.slice(next.length - MAX_CLOSED_CACHE);
        set((s) => ({ candles: { ...s.candles, [k]: next }, forming: { ...s.forming, [k]: null } }));
      } else {
        const forming: Candle = { time: upd.time, open: upd.open, high: upd.high, low: upd.low, close: upd.close, volume: upd.volume };
        set((s) => ({ forming: { ...s.forming, [k]: forming } }));
      }
    });
    set((s) => ({ ws: { ...s.ws, [newKey]: unsub }, currentInterval: interval }));
  },

  getMergedCandles: (symbol?: string, interval?: string) => {
    const s = get();
    const sym = symbol || s.currentSymbol;
    const itv = interval || s.currentInterval;
    const key = makeKey(sym, itv);
    const closed = s.candles[key] || [];
    const forming = s.forming[key];
    if (!forming) return closed;
    const last = closed[closed.length - 1];
    if (last && last.time === forming.time) {
      // replace last with forming snapshot
      return [...closed.slice(0, -1), forming];
    }
    return [...closed, forming];
  },
}));
