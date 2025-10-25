import { create } from 'zustand';
import { DataApi, buildCandleFromRecentTrades } from '../services/api';
import { subscribeKline, KlineUpdate, Unsubscribe, BybitWsCategory } from '../services/bybitWs';

export type Candle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type Key = string; // `${symbol}:${interval}`

function makeKey(symbol: string, interval: string): Key {
  return `${symbol.toUpperCase()}:${interval}`;
}

type MarketDataState = {
  currentSymbol: string;
  currentInterval: string;
  currentCategory: BybitWsCategory;
  loading: boolean;
  error: string | null;
  // closed candles cache per key
  candles: Record<Key, Candle[]>;
  // optional forming candle per key
  forming: Record<Key, Candle | null>;
  // active websocket unsubscribe per key (only current key should be active)
  ws: Record<Key, Unsubscribe | null>;
  // fallback poller per key (when WS is down)
  poll: Record<Key, number | null>;
  // actions
  initialize: (symbol?: string, interval?: string) => Promise<void>;
  switchInterval: (interval: string, limit?: number) => Promise<void>;
  setCategory: (category: BybitWsCategory) => Promise<void>;
  loadCandles: (symbol: string, interval: string, limit?: number) => Promise<Candle[]>;
  getMergedCandles: (symbol?: string, interval?: string) => Candle[];
};

const MAX_CLOSED_CACHE = 1200; // keep up to N closed bars per key

export const useMarketDataStore = create<MarketDataState>((set, get) => ({
  currentSymbol: 'BTCUSDT',
  currentInterval: '15',
  currentCategory: 'linear',
  loading: false,
  error: null,
  candles: {},
  forming: {},
  ws: {},
  poll: {},

  loadCandles: async (symbol: string, interval: string, limit: number = 1000) => {
    set({ loading: true, error: null });
    try {
      // Prefer backend working set API to ensure 1000-load/500-RAM policy server-side
      const data = await DataApi.bybitWorkingSet(
        symbol,
        interval,
        Math.max(100, Math.min(1000, limit))
      );
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

  // Helper: OPTIONAL continuity enforcement between last closed and forming candle
  // Only enforce if forming window IMMEDIATELY follows last closed bar
  // AND open price is within reasonable range (not gap/spike)
  _ensureContinuous(forming: Candle, lastClosed: Candle | undefined, interval: string): Candle {
    if (!lastClosed) return forming;
    const iv = String(interval).toUpperCase();
    const bucketSec = (() => {
      if (iv === 'D') return 86400;
      if (iv === 'W') return 7 * 86400;
      const n = parseInt(iv, 10);
      return (isFinite(n) && n > 0 ? n : 1) * 60;
    })();

    // Only apply if forming bar immediately follows last closed bar
    if (forming.time !== lastClosed.time + bucketSec) {
      return forming; // Gap detected, don't force continuity
    }

    // Check if open is reasonable (within 10% of last close) to avoid forcing wrong data
    const prevClose = lastClosed.close;
    const openDiff = Math.abs(forming.open - prevClose) / prevClose;
    if (openDiff > 0.1) {
      // More than 10% gap - likely real gap, don't force continuity
      return forming;
    }

    // Only adjust if open is very close to prevClose (within 0.5%)
    if (openDiff < 0.005) {
      const open = prevClose;
      const high = Math.max(forming.high, open, forming.close);
      const low = Math.min(forming.low, open, forming.close);
      return { ...forming, open, high, low };
    }

    // Return unchanged if gap is significant
    return forming;
  },

  // Helpers for fallback synthesis when there are no trades yet in the new window
  _bucketSec(interval: string): number {
    const iv = String(interval).toUpperCase();
    if (iv === 'D') return 86400;
    if (iv === 'W') return 7 * 86400;
    const n = parseInt(iv, 10);
    return (isFinite(n) && n > 0 ? n : 1) * 60;
  },
  _currentWindowStartSec(interval: string): number {
    const nowSec = Math.floor(Date.now() / 1000);
    const bucket = (get() as any)._bucketSec(interval);
    return Math.floor(nowSec / bucket) * bucket;
  },
  _nextWindowStartSec(prevStartSec: number, interval: string): number {
    const bucket = (get() as any)._bucketSec(interval);
    return prevStartSec + bucket;
  },

  initialize: async (symbol = 'BTCUSDT', interval = '15') => {
    const key = makeKey(symbol, interval);
    // if cache exists, use it; otherwise fetch
    const cached = get().candles[key];
    if (!cached || cached.length === 0) {
      // Preload neighbor timeframes for smooth switching
      const neighbors = (() => {
        const iv = interval.toUpperCase();
        if (iv === '1') return ['1', '5'];
        if (iv === '5') return ['1', '5', '15'];
        if (iv === '15') return ['5', '15', '60'];
        if (iv === '60') return ['15', '60', '240'];
        if (iv === '240') return ['60', '240', 'D'];
        if (iv === 'D') return ['240', 'D', 'W'];
        return [iv];
      })();
      try {
        const ivs = Array.from(new Set(neighbors));
        // Reset bases to ensure new forming candle starts from last closed close
        await DataApi.resetWorkingSets(symbol, ivs, true, 1000);
        await DataApi.primeWorkingSets(symbol, ivs, 1000);
      } catch {}
      await get().loadCandles(symbol, interval, 1000);
    }
    // (re)subscribe WS for this key
    // unsubscribe any previous active ws
    const prevKey = makeKey(get().currentSymbol, get().currentInterval);
    const prevUnsub = get().ws[prevKey];
    if (prevUnsub) {
      try {
        prevUnsub();
      } catch {}
      set((s) => ({ ws: { ...s.ws, [prevKey]: null } }));
    }
    // helper to stop any fallback poller for this key
    const stopPoll = (k: Key) => {
      const id = get().poll[k];
      if (id != null) {
        try {
          clearInterval(id);
        } catch {}
        set((s) => ({ poll: { ...s.poll, [k]: null } }));
      }
    };

    const startPoll = (k: Key) => {
      // already polling
      if (get().poll[k]) return;
      const [sym, iv] = k.split(':');
      // Poll recent trades every 2s and build a forming candle
      const id = window.setInterval(async () => {
        try {
          const trades = await DataApi.bybitRecentTrades(sym, 250);
          const c = buildCandleFromRecentTrades(trades, iv);
          if (c) {
            // continuity fix against last closed
            const state = get();
            const closed = state.candles[k] || [];
            const last = closed[closed.length - 1];
            let forming: Candle = {
              time: c.time,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume,
            };
            forming = (get() as any)._ensureContinuous(forming, last, iv);
            set((s) => ({ forming: { ...s.forming, [k]: forming } }));
          } else {
            // No trades in current window yet: synthesize flat forming bar from last close
            const state = get();
            const closed = state.candles[k] || [];
            const last = closed[closed.length - 1];
            if (last) {
              const bucket = (get() as any)._bucketSec(iv);
              const ws = (get() as any)._currentWindowStartSec(iv);
              if (ws === last.time + bucket) {
                const price = last.close;
                const flat: Candle = {
                  time: ws,
                  open: price,
                  high: price,
                  low: price,
                  close: price,
                };
                set((s) => ({ forming: { ...s.forming, [k]: flat } }));
              }
            }
          }
        } catch {
          // keep silent, next tick will retry
        }
      }, 2000);
      set((s) => ({ poll: { ...s.poll, [k]: id } }));
    };

    const unsub = subscribeKline(
      symbol,
      interval,
      (upd: KlineUpdate) => {
        const k = makeKey(symbol, interval);
        const state = get();
        const closed = state.candles[k] || [];
        if (upd.confirm) {
          // append as closed, ensure no duplicate time
          const last = closed[closed.length - 1];
          let next: Candle[];
          const newBar: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
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
          // ensure poller is stopped on healthy WS
          stopPoll(k);
          // Immediately seed next forming bar as flat from close to avoid visual gap until first trade arrives
          const nextStart = (get() as any)._nextWindowStartSec(upd.time, interval);
          const price = upd.close;
          const seed: Candle = {
            time: nextStart,
            open: price,
            high: price,
            low: price,
            close: price,
          };
          set((s) => ({ forming: { ...s.forming, [k]: seed } }));
        } else {
          // forming candle for current interval window
          let forming: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
          // continuity with last closed bar
          const last = closed[closed.length - 1];
          forming = (get() as any)._ensureContinuous(forming, last, interval);
          set((s) => ({ forming: { ...s.forming, [k]: forming } }));
        }
      },
      (status) => {
        const k = makeKey(symbol, interval);
        if (status === 'open') {
          stopPoll(k);
        } else if (status === 'error' || status === 'closed') {
          // start fallback polling if not already
          startPoll(k);
        }
      },
      get().currentCategory
    );
    set((s) => ({
      ws: { ...s.ws, [key]: unsub },
      currentSymbol: symbol,
      currentInterval: interval,
    }));
  },

  switchInterval: async (interval: string, limit: number = 1000) => {
    const symbol = get().currentSymbol;
    const newKey = makeKey(symbol, interval);
    // if not cached, load
    if (!get().candles[newKey] || get().candles[newKey].length === 0) {
      try {
        const iv = interval.toUpperCase();
        const neighbors = (() => {
          if (iv === '1') return ['1', '5'];
          if (iv === '5') return ['1', '5', '15'];
          if (iv === '15') return ['5', '15', '60'];
          if (iv === '60') return ['15', '60', '240'];
          if (iv === '240') return ['60', '240', 'D'];
          if (iv === 'D') return ['240', 'D', 'W'];
          return [iv];
        })();
        const ivs = Array.from(new Set(neighbors));
        await DataApi.resetWorkingSets(symbol, ivs, true, 1000);
        await DataApi.primeWorkingSets(symbol, ivs, 1000);
      } catch {}
      await get().loadCandles(symbol, interval, limit);
    }
    // unsubscribe previous
    const prevKey = makeKey(get().currentSymbol, get().currentInterval);
    const prevUnsub = get().ws[prevKey];
    if (prevUnsub) {
      try {
        prevUnsub();
      } catch {}
      set((s) => ({ ws: { ...s.ws, [prevKey]: null } }));
    }
    // subscribe new
    // stop any existing poller for prev key
    const stopPoll = (k: Key) => {
      const id = get().poll[k];
      if (id != null) {
        try {
          clearInterval(id);
        } catch {}
        set((s) => ({ poll: { ...s.poll, [k]: null } }));
      }
    };
    const startPoll = (k: Key) => {
      if (get().poll[k]) return;
      const [sym, iv] = k.split(':');
      const id = window.setInterval(async () => {
        try {
          const trades = await DataApi.bybitRecentTrades(sym, 250);
          const c = buildCandleFromRecentTrades(trades, iv);
          if (c) {
            const state = get();
            const closed = state.candles[k] || [];
            const last = closed[closed.length - 1];
            let forming: Candle = {
              time: c.time,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume,
            };
            forming = (get() as any)._ensureContinuous(forming, last, iv);
            set((s) => ({ forming: { ...s.forming, [k]: forming } }));
          } else {
            const state = get();
            const closed = state.candles[k] || [];
            const last = closed[closed.length - 1];
            if (last) {
              const bucket = (get() as any)._bucketSec(iv);
              const ws = (get() as any)._currentWindowStartSec(iv);
              if (ws === last.time + bucket) {
                const price = last.close;
                const flat: Candle = {
                  time: ws,
                  open: price,
                  high: price,
                  low: price,
                  close: price,
                };
                set((s) => ({ forming: { ...s.forming, [k]: flat } }));
              }
            }
          }
        } catch {}
      }, 2000);
      set((s) => ({ poll: { ...s.poll, [k]: id } }));
    };

    const unsub = subscribeKline(
      symbol,
      interval,
      (upd: KlineUpdate) => {
        const k = makeKey(symbol, interval);
        const closed = get().candles[k] || [];
        if (upd.confirm) {
          const last = closed[closed.length - 1];
          const newBar: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
          let next =
            last && last.time === upd.time ? [...closed.slice(0, -1), newBar] : [...closed, newBar];
          if (next.length > MAX_CLOSED_CACHE) next = next.slice(next.length - MAX_CLOSED_CACHE);
          set((s) => ({
            candles: { ...s.candles, [k]: next },
            forming: { ...s.forming, [k]: null },
          }));
          stopPoll(k);
        } else {
          const forming: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
          const closed = get().candles[k] || [];
          const last = closed[closed.length - 1];
          const adjusted = (get() as any)._ensureContinuous(forming, last, interval);
          set((s) => ({ forming: { ...s.forming, [k]: adjusted } }));
        }
      },
      (status) => {
        const k = makeKey(symbol, interval);
        if (status === 'open') {
          stopPoll(k);
        } else if (status === 'error' || status === 'closed') {
          startPoll(k);
        }
      },
      get().currentCategory
    );
    set((s) => ({ ws: { ...s.ws, [newKey]: unsub }, currentInterval: interval }));
  },

  setCategory: async (category: BybitWsCategory) => {
    const state = get();
    if (state.currentCategory === category) return;
    const symbol = state.currentSymbol;
    const interval = state.currentInterval;
    const key = makeKey(symbol, interval);
    // unsubscribe existing ws for this key
    const prevUnsub = state.ws[key];
    if (prevUnsub) {
      try {
        prevUnsub();
      } catch {}
      set((s) => ({ ws: { ...s.ws, [key]: null } }));
    }

    // stop any existing poller for this key to avoid duplicates; will restart if WS fails
    const stopPoll = (k: Key) => {
      const id = get().poll[k];
      if (id != null) {
        try {
          clearInterval(id);
        } catch {}
        set((s) => ({ poll: { ...s.poll, [k]: null } }));
      }
    };
    const startPoll = (k: Key) => {
      if (get().poll[k]) return;
      const [sym, iv] = k.split(':');
      const id = window.setInterval(async () => {
        try {
          const trades = await DataApi.bybitRecentTrades(sym, 250);
          const c = buildCandleFromRecentTrades(trades, iv);
          if (c) {
            const st = get();
            const closed = st.candles[k] || [];
            const last = closed[closed.length - 1];
            let forming: Candle = {
              time: c.time,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume,
            };
            forming = (get() as any)._ensureContinuous(forming, last, iv);
            set((s) => ({ forming: { ...s.forming, [k]: forming } }));
          }
        } catch {}
      }, 2000);
      set((s) => ({ poll: { ...s.poll, [k]: id } }));
    };

    const unsub = subscribeKline(
      symbol,
      interval,
      (upd: KlineUpdate) => {
        const k = makeKey(symbol, interval);
        const closed = get().candles[k] || [];
        if (upd.confirm) {
          const last = closed[closed.length - 1];
          const newBar: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
          let next =
            last && last.time === upd.time ? [...closed.slice(0, -1), newBar] : [...closed, newBar];
          if (next.length > MAX_CLOSED_CACHE) next = next.slice(next.length - MAX_CLOSED_CACHE);
          set((s) => ({
            candles: { ...s.candles, [k]: next },
            forming: { ...s.forming, [k]: null },
          }));
          stopPoll(k);
        } else {
          const forming: Candle = {
            time: upd.time,
            open: upd.open,
            high: upd.high,
            low: upd.low,
            close: upd.close,
            volume: upd.volume,
          };
          const last = closed[closed.length - 1];
          const adjusted = (get() as any)._ensureContinuous(forming, last, interval);
          set((s) => ({ forming: { ...s.forming, [k]: adjusted } }));
        }
      },
      (status) => {
        const k = makeKey(symbol, interval);
        if (status === 'open') {
          stopPoll(k);
        } else if (status === 'error' || status === 'closed') {
          startPoll(k);
        }
      },
      category
    );

    set((s) => ({ ws: { ...s.ws, [key]: unsub }, currentCategory: category }));
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
