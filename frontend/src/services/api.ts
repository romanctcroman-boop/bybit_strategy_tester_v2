import axios from 'axios';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import { Strategy, Backtest, Trade, MarketDataPoint, ApiListResponse, Optimization, OptimizationResult, OptimizationEnqueueResponse } from '../types/api';

dayjs.extend(utc);

const api = axios.create({
  baseURL: (import.meta as any).env?.VITE_API_URL || '/api/v1',
  timeout: 30000,
});

// ----------------------
// Global Axios interceptors
// ----------------------
import { emitNotification } from './notifications';
import { incRequests, decRequests } from './progress';

type FieldErrors = Record<string, string>;

function extractFieldErrors(error: any): FieldErrors | undefined {
  const status: number | undefined = error?.response?.status;
  const data = error?.response?.data;
  if (status === 422 && data && Array.isArray(data.detail)) {
    const out: FieldErrors = {};
    for (const d of data.detail) {
      const loc = Array.isArray(d?.loc) ? d.loc : [];
      const key = loc.length ? String(loc[loc.length - 1]) : undefined;
      if (key) out[key] = d?.msg || 'Invalid value';
    }
    return out;
  }
  return undefined;
}

function extractErrorMessage(error: any): string {
  // Network errors
  if (error?.message && !error?.response) {
    return `Network error: ${error.message}`;
  }
  const status: number | undefined = error?.response?.status;
  const data = error?.response?.data;
  let details = '';
  if (data) {
    if (typeof data === 'string') details = data;
    else if (typeof data?.detail === 'string') details = data.detail;
    else if (Array.isArray(data?.detail)) {
      // FastAPI validation errors
      details = data.detail.map((d: any) => (d?.msg || JSON.stringify(d))).join('; ');
    } else if (data?.message) {
      details = typeof data.message === 'string' ? data.message : JSON.stringify(data.message);
    }
  }
  const base = (() => {
    if (status == null) return 'Request failed';
    if (status === 400) return 'Bad request';
    if (status === 401) return 'Unauthorized';
    if (status === 403) return 'Forbidden';
    if (status === 404) return 'Not found';
    if (status === 409) return 'Conflict';
    if (status === 422) return 'Validation error';
    if (status === 429) return 'Too many requests';
    if (status >= 500) return 'Server error';
    return `HTTP ${status}`;
  })();
  return details ? `${base}: ${details}` : base;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = extractErrorMessage(error);
    const fieldErrors = extractFieldErrors(error);
    emitNotification({ message, severity: 'error' });
    return Promise.reject(Object.assign(error, { friendlyMessage: message, fieldErrors }));
  }
);

// Track active requests for global progress bar
api.interceptors.request.use((config) => {
  incRequests();
  return config;
});
api.interceptors.response.use(
  (res) => {
    decRequests();
    return res;
  },
  (err) => {
    decRequests();
    return Promise.reject(err);
  }
);

function parseIso(s?: string) {
  return s ? dayjs.utc(s).toDate() : undefined;
}

export const StrategiesApi = {
  list: async (opts?: { limit?: number; offset?: number; is_active?: boolean; strategy_type?: string }): Promise<ApiListResponse<Strategy>> => {
    const r = await api.get('/strategies', { params: { limit: opts?.limit, offset: opts?.offset, is_active: opts?.is_active, strategy_type: opts?.strategy_type } });
    return r.data;
  },
  get: async (id: number): Promise<Strategy> => {
    const r = await api.get(`/strategies/${id}`);
    return r.data;
  },
  create: async (payload: Partial<Strategy>) => {
    const r = await api.post('/strategies', payload);
    return r.data;
  },
};

export const BacktestsApi = {
  list: async (opts?: { limit?: number; offset?: number; strategy_id?: number; symbol?: string; status?: string; order_by?: string; order_dir?: 'asc' | 'desc' }): Promise<ApiListResponse<Backtest>> => {
    const r = await api.get('/backtests', { params: { limit: opts?.limit, offset: opts?.offset, strategy_id: opts?.strategy_id, symbol: opts?.symbol, status: opts?.status, order_by: opts?.order_by, order_dir: opts?.order_dir } });
    return r.data;
  },
  get: async (id: number): Promise<Backtest> => {
    const r = await api.get(`/backtests/${id}`);
    return r.data;
  },
  run: async (payload: Partial<Backtest>) => {
    const r = await api.post('/backtests', payload);
    return r.data;
  },
  trades: async (backtestId: number, opts?: { side?: 'buy' | 'sell'; limit?: number; offset?: number }): Promise<{ items: Trade[]; total?: number }> => {
    const params: any = {};
    if (opts?.side) params.side = opts.side;
    if (opts?.limit != null) params.limit = opts.limit;
    if (opts?.offset != null) params.offset = opts.offset;
    const r = await api.get(`/backtests/${backtestId}/trades`, { params });
    const items = (Array.isArray(r.data) ? r.data : r.data.items || []).map((t: any) => ({ ...t, entry_time: parseIso(t.entry_time) }));
    const total = Array.isArray(r.data) ? items.length : r.data.total;
    return { items, total };
  },
};

export const DataApi = {
  upload: async (formData: FormData) => {
    const r = await api.post('/data/uploads', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
    return r.data;
  },
  marketData: async (symbol: string): Promise<MarketDataPoint[]> => {
    const r = await api.get(`/marketdata/${encodeURIComponent(symbol)}`);
    return r.data;
  },
  bybitKlines: async (symbol: string, interval: string = '1', limit: number = 500, persist = 0): Promise<Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }>> => {
    const r = await api.get(`/marketdata/bybit/klines/fetch`, { params: { symbol, interval, limit, persist } });
    // map open_time(ms) -> seconds epoch as lightweight-charts expects seconds
    return (r.data || []).map((c: any) => ({
      time: Math.floor((c.open_time ?? 0) / 1000),
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
      volume: c.volume != null ? +c.volume : undefined,
    }));
  },
  bybitWorkingSet: async (symbol: string, interval: string = '15', loadLimit: number = 1000): Promise<Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }>> => {
    const r = await api.get(`/marketdata/bybit/klines/working`, { params: { symbol, interval, load_limit: loadLimit } });
    // Endpoint already returns seconds-based time; normalize just in case
    return (r.data || []).map((c: any) => ({
      time: Math.floor((c.time ?? 0)),
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
      volume: c.volume != null ? +c.volume : undefined,
    }));
  },
  
  bybitRecentTrades: async (symbol: string, limit: number = 250): Promise<Array<{ time: number; price: number; qty: number; side: string }>> => {
    const r = await api.get(`/marketdata/bybit/recent-trades`, { params: { symbol, limit } });
    // Return trades as-is: {time(ms), price, qty, side}
    return r.data || [];
  },
};

// ======================
// Optimizations API
// ======================

export const OptimizationsApi = {
  list: async (opts?: { limit?: number; offset?: number; status?: string; strategy_id?: number }): Promise<ApiListResponse<Optimization>> => {
    const r = await api.get('/optimizations', { params: { limit: opts?.limit, offset: opts?.offset, status: opts?.status, strategy_id: opts?.strategy_id } });
    return r.data;
  },
  get: async (id: number): Promise<Optimization> => {
    const r = await api.get(`/optimizations/${id}`);
    return r.data;
  },
  results: async (id: number): Promise<OptimizationResult[]> => {
    const r = await api.get(`/optimizations/${id}/results`);
    return r.data;
  },
  best: async (id: number): Promise<OptimizationResult> => {
    const r = await api.get(`/optimizations/${id}/best`);
    return r.data;
  },
  runGrid: async (
    id: number,
    payload: { strategy_config?: Record<string, any>; param_space?: Record<string, any>; metric?: string; queue?: string }
  ): Promise<OptimizationEnqueueResponse> => {
    const r = await api.post(`/optimizations/${id}/run/grid`, payload);
    return r.data;
  },
  runWalkForward: async (
    id: number,
    payload: { strategy_config?: Record<string, any>; param_space?: Record<string, any>; train_size?: number; test_size?: number; step_size?: number; metric?: string; queue?: string }
  ): Promise<OptimizationEnqueueResponse> => {
    const r = await api.post(`/optimizations/${id}/run/walk-forward`, payload);
    return r.data;
  },
  runBayesian: async (
    id: number,
    payload: { strategy_config?: Record<string, any>; param_space: Record<string, any>; n_trials?: number; metric?: string; direction?: string; n_jobs?: number; random_state?: number; queue?: string }
  ): Promise<OptimizationEnqueueResponse> => {
    const r = await api.post(`/optimizations/${id}/run/bayesian`, payload);
    return r.data;
  },
};

/**
 * Build real-time OHLCV candle from trades within a time window.
 * Groups all trades in the last N seconds into a single candle.
 */
export function buildCandleFromTrades(
  trades: Array<{ time: number; price: number; qty: number; side: string }>,
  windowSeconds: number = 60
): { time: number; open: number; high: number; low: number; close: number; volume: number } | null {
  if (!trades || trades.length === 0) return null;
  
  // Sort by time ascending
  const sorted = [...trades].sort((a, b) => a.time - b.time);
  
  const now = Date.now();
  const windowMs = windowSeconds * 1000;
  const cutoff = now - windowMs;
  
  // Filter trades within the window
  const recentTrades = sorted.filter(t => t.time >= cutoff);
  if (recentTrades.length === 0) return null;
  
  // Build OHLCV
  const prices = recentTrades.map(t => t.price);
  const open = recentTrades[0].price;
  const close = recentTrades[recentTrades.length - 1].price;
  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const volume = recentTrades.reduce((sum, t) => sum + t.qty, 0);
  
  // Use start of window as time
  const windowStart = Math.floor(cutoff / 1000);
  
  return { time: windowStart, open, high, low, close, volume };
}

/**
 * Build candles from trades by grouping them into fixed time windows.
 * Each window represents one candle (e.g., 60 seconds = 1-minute candles)
 * 
 * Used for live updates: groups recent trades into a single "forming" candle
 * for the current minute.
 */
export function buildCandleFromRecentTrades(
  trades: Array<{ time: number; price: number; qty: number; side: string }>
): { time: number; open: number; high: number; low: number; close: number; volume: number } | null {
  if (!trades || trades.length === 0) return null;
  
  // Sort by time ascending
  const sorted = [...trades].sort((a, b) => a.time - b.time);
  
  // Get the minute window of the most recent trade
  const lastTrade = sorted[sorted.length - 1];
  const lastTradeDate = new Date(lastTrade.time);
  
  // Calculate start of current minute
  const currentMinuteStart = new Date(lastTradeDate);
  currentMinuteStart.setSeconds(0, 0); // Set to start of minute
  
  const windowStartMs = currentMinuteStart.getTime();
  const windowEndMs = windowStartMs + 60000; // Next minute
  
  // Filter trades in current minute
  const minuteTrades = sorted.filter(t => t.time >= windowStartMs && t.time < windowEndMs);
  
  if (minuteTrades.length === 0) return null;
  
  // Build OHLCV
  const prices = minuteTrades.map(t => t.price);
  const open = minuteTrades[0].price;
  const close = minuteTrades[minuteTrades.length - 1].price;
  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const volume = minuteTrades.reduce((sum, t) => sum + t.qty, 0);
  
  // Time in seconds (lightweight-charts format)
  const time = Math.floor(windowStartMs / 1000);
  
  return { time, open, high, low, close, volume };
}

/**
 * Build candle from trades constrained to an explicit time window [windowStartSec, windowEndSec).
 * Trades are expected to have time in milliseconds. Window boundaries are seconds.
 */
export function buildCandleFromTradesInWindow(
  trades: Array<{ time: number; price: number; qty: number; side: string }>,
  windowStartSec: number,
  windowEndSec: number
): { time: number; open: number; high: number; low: number; close: number; volume: number } | null {
  if (!trades || trades.length === 0) return null;
  const startMs = windowStartSec * 1000;
  const endMs = windowEndSec * 1000;
  const inWindow = trades
    .filter(t => t.time >= startMs && t.time < endMs)
    .sort((a, b) => a.time - b.time);
  if (inWindow.length === 0) return null;
  const prices = inWindow.map(t => t.price);
  return {
    time: windowStartSec,
    open: inWindow[0].price,
    high: Math.max(...prices),
    low: Math.min(...prices),
    close: inWindow[inWindow.length - 1].price,
    volume: inWindow.reduce((acc, t) => acc + t.qty, 0),
  };
}

export default api;
