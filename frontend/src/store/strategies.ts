import create from 'zustand';
import { Strategy } from '../types/api';
import { StrategiesApi } from '../services/api';

interface StrategiesState {
  items: Strategy[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  error?: string;
  // filters & selection
  isActive?: boolean;
  strategyType?: string;
  selectedId: number | null;
  setFilters: (f: { isActive?: boolean; strategyType?: string }) => void;
  select: (id: number | null) => void;
  // data actions
  fetchAll: (opts?: {
    limit?: number;
    offset?: number;
    isActive?: boolean;
    strategyType?: string;
  }) => Promise<void>;
  setPage: (page: number, pageSize?: number) => Promise<void>;
  add: (s: Partial<Strategy>) => Promise<Strategy | void>;
  update: (id: number, s: Partial<Strategy>) => Promise<Strategy | void>;
  remove: (id: number) => Promise<boolean | void>;
}

export const useStrategiesStore = create<StrategiesState>((set, get) => ({
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
  loading: false,
  error: undefined,
  isActive: undefined,
  strategyType: undefined,
  selectedId: null,
  setFilters: (f) => set({ isActive: f.isActive, strategyType: f.strategyType }),
  select: (id) => set({ selectedId: id }),
  fetchAll: async (opts) => {
    try {
      const limit = opts?.limit ?? get().limit;
      const offset = opts?.offset ?? get().offset;
      const isActive = opts?.isActive ?? get().isActive;
      const strategyType = opts?.strategyType ?? get().strategyType;
      set({ loading: true, error: undefined });
      const res = await StrategiesApi.list({
        limit,
        offset,
        is_active: isActive,
        strategy_type: strategyType,
      });
      set({
        items: res.items,
        total: res.total ?? res.items.length,
        limit,
        offset,
        loading: false,
      });
    } catch (e: any) {
      console.warn('Failed to load strategies:', e);
      set({ error: e?.message || String(e), loading: false });
    }
  },
  setPage: async (page, pageSize) => {
    const size = pageSize ?? get().limit;
    const offset = (page - 1) * size;
    await get().fetchAll({ limit: size, offset });
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
  update: async (id, s) => {
    set({ loading: true, error: undefined });
    try {
      const upd = await StrategiesApi.update(id, s);
      set({ items: get().items.map((it) => (it.id === id ? upd : it)), loading: false });
      return upd;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  remove: async (id) => {
    set({ loading: true, error: undefined });
    try {
      const res = await StrategiesApi.remove(id);
      set({ items: get().items.filter((it) => it.id !== id), loading: false });
      return !!res?.success;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
}));
