import create from 'zustand';
import { Backtest, Trade } from '../types/api';
import { BacktestsApi } from '../services/api';

interface BacktestsState {
  items: Backtest[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  error?: string;
  fetchAll: (opts?: { limit?: number; offset?: number }) => Promise<void>;
  setPage: (page: number, pageSize?: number) => Promise<void>;
  run: (payload: Partial<Backtest>) => Promise<Backtest | void>;
  // Trades detail state
  tradeSide?: 'buy' | 'sell';
  trades: Trade[];
  tradesTotal: number;
  tradesLimit: number;
  tradesOffset: number;
  setTradeFilters: (opts: { side?: 'buy' | 'sell' }) => void;
  fetchTrades: (backtestId: number, opts?: { side?: 'buy' | 'sell'; limit?: number; offset?: number }) => Promise<Trade[] | void>;
  setTradesPage: (backtestId: number, page: number, pageSize?: number) => Promise<void>;
}

export const useBacktestsStore = create<BacktestsState>((set, get) => ({
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
  loading: false,
  error: undefined,
  tradeSide: undefined,
  trades: [],
  tradesTotal: 0,
  tradesLimit: 50,
  tradesOffset: 0,
  fetchAll: async (opts) => {
    const limit = opts?.limit ?? get().limit;
    const offset = opts?.offset ?? get().offset;
    set({ loading: true, error: undefined });
    try {
      const res = await BacktestsApi.list({ limit, offset });
      set({ items: res.items, total: res.total ?? res.items.length, limit, offset, loading: false });
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  setPage: async (page, pageSize) => {
    const size = pageSize ?? get().limit;
    const offset = (page - 1) * size;
    await get().fetchAll({ limit: size, offset });
  },
  run: async (payload) => {
    set({ loading: true, error: undefined });
    try {
      const created = await BacktestsApi.run(payload);
      set({ items: [...get().items, created], loading: false });
      return created;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  setTradeFilters: (opts) => set({ tradeSide: opts.side }),
  fetchTrades: async (backtestId, opts) => {
    set({ loading: true, error: undefined });
    try {
      const limit = opts?.limit ?? get().tradesLimit;
      const offset = opts?.offset ?? get().tradesOffset;
      const side = opts?.side ?? get().tradeSide;
      const { items, total } = await BacktestsApi.trades(backtestId, { side, limit, offset });
      set({ loading: false, trades: items, tradesTotal: total ?? items.length, tradesLimit: limit, tradesOffset: offset });
      return items;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  setTradesPage: async (backtestId, page, pageSize) => {
    const size = pageSize ?? get().tradesLimit;
    const offset = (page - 1) * size;
    await get().fetchTrades(backtestId, { limit: size, offset });
  },
}));
