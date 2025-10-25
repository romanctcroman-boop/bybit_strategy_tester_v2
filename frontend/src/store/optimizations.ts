import create from 'zustand';
import { Optimization, OptimizationResult, OptimizationEnqueueResponse } from '../types/api';
import { OptimizationsApi } from '../services/api';

interface OptimizationsState {
  items: Optimization[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  error?: string;
  // filters & selection
  status?: string;
  strategyId?: number;
  selectedId: number | null;
  setFilters: (f: { status?: string; strategyId?: number }) => void;
  select: (id: number | null) => void;
  fetchAll: (opts?: {
    limit?: number;
    offset?: number;
    status?: string;
    strategy_id?: number;
  }) => Promise<void>;
  setPage: (page: number, pageSize?: number) => Promise<void>;
  create: (payload: {
    strategy_id: number;
    optimization_type: string;
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    param_ranges: Record<string, any>;
    metric: string;
    initial_capital: number;
    total_combinations: number;
    config?: Record<string, any>;
  }) => Promise<Optimization | void>;
  results: (id: number) => Promise<OptimizationResult[] | void>;
  best: (id: number) => Promise<OptimizationResult | void>;
  runGrid: (
    id: number,
    payload: {
      strategy_config?: Record<string, any>;
      param_space?: Record<string, any>;
      metric?: string;
      queue?: string;
    }
  ) => Promise<OptimizationEnqueueResponse | void>;
  runWalkForward: (
    id: number,
    payload: {
      strategy_config?: Record<string, any>;
      param_space?: Record<string, any>;
      train_size?: number;
      test_size?: number;
      step_size?: number;
      metric?: string;
      queue?: string;
    }
  ) => Promise<OptimizationEnqueueResponse | void>;
  runBayesian: (
    id: number,
    payload: {
      strategy_config?: Record<string, any>;
      param_space: Record<string, any>;
      n_trials?: number;
      metric?: string;
      direction?: string;
      n_jobs?: number;
      random_state?: number;
      queue?: string;
    }
  ) => Promise<OptimizationEnqueueResponse | void>;
}

export const useOptimizationsStore = create<OptimizationsState>((set, get) => ({
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
  loading: false,
  error: undefined,
  status: undefined,
  strategyId: undefined,
  selectedId: null,
  setFilters: (f) => set({ status: f.status, strategyId: f.strategyId }),
  select: (id) => set({ selectedId: id }),
  fetchAll: async (opts) => {
    try {
      const limit = opts?.limit ?? get().limit;
      const offset = opts?.offset ?? get().offset;
      const status = opts?.status ?? get().status;
      const strategy_id = opts?.strategy_id ?? get().strategyId;
      set({ loading: true, error: undefined });
      const res = await OptimizationsApi.list({ limit, offset, status, strategy_id });
      set({
        items: res.items,
        total: res.total ?? res.items.length,
        limit,
        offset,
        loading: false,
      });
    } catch (e: any) {
      console.warn('Failed to load optimizations:', e);
      set({ error: e?.message || String(e), loading: false });
    }
  },
  setPage: async (page, pageSize) => {
    const size = pageSize ?? get().limit;
    const offset = (page - 1) * size;
    await get().fetchAll({ limit: size, offset });
  },
  create: async (payload) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.create(payload);
      set({ loading: false });
      // Refresh list after creation
      await get().fetchAll();
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  results: async (id) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.results(id);
      set({ loading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  best: async (id) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.best(id);
      set({ loading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  runGrid: async (id, payload) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.runGrid(id, payload);
      set({ loading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  runWalkForward: async (id, payload) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.runWalkForward(id, payload);
      set({ loading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
  runBayesian: async (id, payload) => {
    set({ loading: true, error: undefined });
    try {
      const r = await OptimizationsApi.runBayesian(id, payload);
      set({ loading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.message || String(e), loading: false });
    }
  },
}));
