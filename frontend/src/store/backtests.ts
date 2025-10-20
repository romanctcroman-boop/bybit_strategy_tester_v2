import create from 'zustand';
import { Backtest, Trade } from '../types/api';
import { BacktestsApi } from '../services/api';

interface BacktestsState {
  items: Backtest[];
  loading: boolean;
  error?: string;
  fetchAll: () => Promise<void>;
  run: (payload: Partial<Backtest>) => Promise<Backtest | void>;
  fetchTrades: (backtestId: number) => Promise<Trade[] | void>;
}

export const useBacktestsStore = create<BacktestsState>((set, get) => ({
  items: [],
  loading: false,
  error: undefined,
  fetchAll: async () => {
    set({ loading: true, error: undefined });
    try {
      const res = await BacktestsApi.list();
      set({ items: res.items, loading: false });
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
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
  fetchTrades: async (backtestId) => {
    set({ loading: true, error: undefined });
    try {
      const trades = await BacktestsApi.trades(backtestId);
      set({ loading: false });
      return trades;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
}));
