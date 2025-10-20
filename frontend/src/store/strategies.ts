import create from 'zustand';
import { Strategy } from '../types/api';
import { StrategiesApi } from '../services/api';

interface StrategiesState {
  items: Strategy[];
  loading: boolean;
  error?: string;
  fetchAll: () => Promise<void>;
  add: (s: Partial<Strategy>) => Promise<Strategy | void>;
}

export const useStrategiesStore = create<StrategiesState>((set, get) => ({
  items: [],
  loading: false,
  error: undefined,
  fetchAll: async () => {
    set({ loading: true, error: undefined });
    try {
      const res = await StrategiesApi.list();
      set({ items: res.items, loading: false });
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  add: async (s) => {
    set({ loading: true, error: undefined });
    try {
      const created = await StrategiesApi.create(s as any);
      set({ items: [...get().items, created], loading: false });
      return created;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
}));
