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
  loadHistoricalCandles: (
    symbol: string,
    interval: string,
    requiredCount: number
  ) => Promise<Candle[]>; // New: for backtester
  getMergedCandles: (symbol?: string, interval?: string) => Candle[];
  clearCandleCache: (symbol?: string, interval?: string) => void;
  saveCurrentState: () => Promise<void>; // New: for graceful shutdown
};

const MAX_CLOSED_CACHE = 2000; // keep up to N closed bars per key

// LocalStorage helpers for persistent candle cache
const STORAGE_PREFIX = 'bybit_candles_';
const STORAGE_VERSION = 'v1';

function getStorageKey(symbol: string, interval: string, category: BybitWsCategory): string {
  return `${STORAGE_PREFIX}${STORAGE_VERSION}_${category}_${symbol.toUpperCase()}_${interval}`;
}

function saveToStorage(
  symbol: string,
  interval: string,
  category: BybitWsCategory,
  candles: Candle[]
): void {
  try {
    const key = getStorageKey(symbol, interval, category);
    const data = {
      timestamp: Date.now(),
      candles: candles.slice(-2000), // keep last 2000
    };
    localStorage.setItem(key, JSON.stringify(data));
  } catch (e) {
    console.warn('Failed to save candles to localStorage:', e);
  }
}

function loadFromStorage(
  symbol: string,
  interval: string,
  category: BybitWsCategory
): Candle[] | null {
  try {
    const key = getStorageKey(symbol, interval, category);
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data.candles || !Array.isArray(data.candles)) return null;
    // Check if data is not too old (max 7 days)
    const age = Date.now() - (data.timestamp || 0);
    if (age > 7 * 24 * 60 * 60 * 1000) {
      localStorage.removeItem(key);
      return null;
    }
    return data.candles;
  } catch (e) {
    console.warn('Failed to load candles from localStorage:', e);
    return null;
  }
}

function clearStorage(symbol: string, interval: string, category: BybitWsCategory): void {
  try {
    const key = getStorageKey(symbol, interval, category);
    localStorage.removeItem(key);
  } catch (e) {
    console.warn('Failed to clear storage:', e);
  }
}

// Helper: Calculate time of oldest candle in storage
function getOldestCandleTime(candles: Candle[]): number | null {
  if (!candles || candles.length === 0) return null;
  return Math.min(...candles.map((c) => c.time));
}

// Helper: Calculate time of newest candle in storage
function getNewestCandleTime(candles: Candle[]): number | null {
  if (!candles || candles.length === 0) return null;
  return Math.max(...candles.map((c) => c.time));
}

// Helper: Calculate interval in seconds
function getIntervalSeconds(interval: string): number {
  const iv = String(interval).toUpperCase();
  if (iv === 'D') return 86400;
  if (iv === 'W') return 7 * 86400;
  const n = parseInt(iv, 10);
  return (isFinite(n) && n > 0 ? n : 1) * 60;
}

// Helper: Calculate number of candles needed for date range
function calculateCandlesForDateRange(
  startDate: string, // YYYY-MM-DD
  endDate: string, // YYYY-MM-DD
  interval: string
): number {
  const start = new Date(startDate).getTime() / 1000;
  const end = new Date(endDate).getTime() / 1000;
  const diffSec = end - start;
  const intervalSec = getIntervalSeconds(interval);
  const candles = Math.ceil(diffSec / intervalSec);

  // Clamp to API limits (100-1000)
  return Math.max(100, Math.min(1000, candles));
}

// Helper: Deduplicate and sort candles
function deduplicateCandles(candles: Candle[]): Candle[] {
  const sorted = [...candles].sort((a, b) => a.time - b.time);
  const dedup: Candle[] = [];
  let lastTime: number | null = null;
  for (const c of sorted) {
    if (lastTime === null || c.time > lastTime) {
      dedup.push(c);
      lastTime = c.time;
    } else if (c.time === lastTime) {
      // Replace with latest data for same timestamp
      dedup[dedup.length - 1] = c;
    }
  }
  return dedup;
}

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

  loadCandles: async (symbol: string, interval: string, _limit?: number) => {
    set({ loading: true, error: null });
    const key = makeKey(symbol, interval);
    const category = get().currentCategory;
    const intervalSec = getIntervalSeconds(interval);
    const nowSec = Math.floor(Date.now() / 1000);

    // Calculate optimal limit: always use 1000 candles (API max) for all timeframes
    // This provides different history depths optimized per timeframe
    const optimalLimit = _limit ?? 1000;

    try {
      // 1. Try to load from localStorage first
      const cached = loadFromStorage(symbol, interval, category);

      if (cached && cached.length > 0) {
        console.log(`📦 Found ${cached.length} cached candles for ${key}`);

        // 2. Update last 100 candles (to avoid price gaps) - minimum required by backend
        const updateCount = Math.min(100, cached.length);
        const last10Updated = await DataApi.bybitWorkingSet(symbol, interval, updateCount);

        if (last10Updated.length === 0) {
          console.warn('⚠️ Failed to fetch last 100 candles, using cache as-is');
          set((s) => ({ candles: { ...s.candles, [key]: cached }, loading: false }));
          return cached;
        }

        // 3. Determine how many NEW candles we need from last cached to current time
        const newestCachedTime = getNewestCandleTime(cached) || 0;
        const newestFetchedTime = getNewestCandleTime(last10Updated) || nowSec;
        const timeDiff = newestFetchedTime - newestCachedTime;
        const newCandlesNeeded = Math.floor(timeDiff / intervalSec);

        console.log(`🕐 Newest cached: ${new Date(newestCachedTime * 1000).toISOString()}`);
        console.log(`🕐 Current time: ${new Date(nowSec * 1000).toISOString()}`);
        console.log(`📊 New candles needed: ${newCandlesNeeded}`);

        let allCandles = cached;

        // 4. If we need new candles, fetch them
        if (newCandlesNeeded > 10) {
          // Fetch maximum available (up to 1000 recent)
          const fetchCount = Math.min(1000, newCandlesNeeded + 50); // +50 buffer for overlap
          const newCandles = await DataApi.bybitWorkingSet(symbol, interval, fetchCount);

          // Merge: keep old candles + add new ones
          allCandles = [...cached, ...newCandles];
          console.log(`✅ Fetched ${newCandles.length} new candles`);
        } else {
          // Just replace last N candles (updateCount)
          allCandles = [...cached.slice(0, -updateCount), ...last10Updated];
          console.log(`✅ Updated last ${updateCount} candles`);
        }

        // 5. Deduplicate, sort, and limit to MAX_CLOSED_CACHE
        const dedup = deduplicateCandles(allCandles);
        const final = dedup.slice(-MAX_CLOSED_CACHE);

        set((s) => ({ candles: { ...s.candles, [key]: final }, loading: false }));
        saveToStorage(symbol, interval, category, final);
        console.log(`💾 Saved ${final.length} candles to storage`);
        return final;
      }

      // 6. No cache - load fresh data using optimal limit based on timeframe
      console.log(`🆕 No cache found, loading fresh data for ${key} (limit: ${optimalLimit})`);
      const freshData = await DataApi.bybitWorkingSet(symbol, interval, optimalLimit);
      const dedup = deduplicateCandles(freshData);

      set((s) => ({ candles: { ...s.candles, [key]: dedup }, loading: false }));
      saveToStorage(symbol, interval, category, dedup);
      console.log(`💾 Saved ${dedup.length} fresh candles to storage`);
      return dedup;
    } catch (e: any) {
      const msg = e?.message || 'Failed to load klines';
      console.error(`❌ Error loading candles:`, e);
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
      // Load candles with automatic timeframe-based limit (30 days)
      await get().loadCandles(symbol, interval);
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
      // Removed neighbor preloading logic
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

  loadHistoricalCandles: async (symbol: string, interval: string, requiredCount: number) => {
    console.log(`📚 Loading historical candles: ${symbol} ${interval}, required: ${requiredCount}`);
    const _key = makeKey(symbol, interval);
    const category = get().currentCategory;
    const cached = loadFromStorage(symbol, interval, category);

    if (!cached || cached.length === 0) {
      console.warn('⚠️ No cache available for historical load. Load current data first.');
      return [];
    }

    const currentCount = cached.length;
    if (currentCount >= requiredCount) {
      console.log(`✅ Cache has enough data: ${currentCount} >= ${requiredCount}`);
      return cached;
    }

    const neededCount = requiredCount - currentCount;
    console.log(`📥 Need to load ${neededCount} more historical candles`);

    try {
      // Update first 10 candles to avoid gaps
      const oldestTime = getOldestCandleTime(cached);
      if (!oldestTime) {
        console.warn('⚠️ Cannot determine oldest candle time');
        return cached;
      }

      console.log(`🕐 Oldest cached: ${new Date(oldestTime * 1000).toISOString()}`);

      // Note: Bybit API doesn't support loading older data with endTime parameter
      // We can only load most recent N candles
      // For true historical data, we'd need a different API endpoint or backend service
      console.warn('⚠️ Historical data loading limited: API only provides recent candles');
      console.warn('💡 Consider implementing backend historical data service');

      // For now, return what we have
      return cached;
    } catch (e: any) {
      console.error(`❌ Error loading historical candles:`, e);
      return cached;
    }
  },

  saveCurrentState: async () => {
    console.log('💾 Saving current state...');
    const state = get();

    // Save all active candle caches to localStorage
    let savedCount = 0;
    for (const [key, candles] of Object.entries(state.candles)) {
      if (candles && candles.length > 0) {
        const [symbol, interval] = key.split(':');
        saveToStorage(symbol, interval, state.currentCategory, candles);
        savedCount++;
      }
    }

    console.log(`✅ Saved ${savedCount} candle caches to storage`);
  },

  clearCandleCache: (symbol?: string, interval?: string) => {
    const s = get();
    const sym = symbol || s.currentSymbol;
    const itv = interval || s.currentInterval;
    const key = makeKey(sym, itv);
    const category = s.currentCategory;

    // Clear from memory
    set((state) => ({
      candles: { ...state.candles, [key]: [] },
      forming: { ...state.forming, [key]: null },
    }));

    // Clear from localStorage
    clearStorage(sym, itv, category);

    console.log(`Cleared cache for ${key}`);
  },
}));
