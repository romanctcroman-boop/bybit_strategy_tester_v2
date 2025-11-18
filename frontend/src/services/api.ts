import axios from 'axios';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import {
  Strategy,
  Backtest,
  Trade,
  MarketDataPoint,
  ApiListResponse,
  Optimization,
  OptimizationResult,
  OptimizationEnqueueResponse,
} from '../types/api';

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
import { getAccessToken, refreshAccessToken, isTokenExpired, clearTokens } from './auth';

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
      details = data.detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ');
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

// ----------------------
// JWT Authentication Interceptor
// ----------------------
let isRefreshing = false;
let failedQueue: Array<{ resolve: (value?: unknown) => void; reject: (reason?: any) => void }> = [];

const processQueue = (error: any = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

// Add JWT token to all requests
api.interceptors.request.use(
  async (config) => {
    const token = getAccessToken();

    // Don't add token to auth endpoints
    if (config.url?.includes('/auth/login') || config.url?.includes('/auth/refresh')) {
      return config;
    }

    // Add Authorization header if token exists
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle token refresh on 401 errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and not already retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for token refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            const token = getAccessToken();
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Check if token is expired and we can refresh
        if (isTokenExpired()) {
          await refreshAccessToken();
          processQueue();

          // Retry original request with new token
          const token = getAccessToken();
          if (token) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return api(originalRequest);
        } else {
          // Token not expired but still 401 - probably invalid
          // Clear tokens and redirect to login
          clearTokens();
          processQueue(new Error('Session expired'));

          // Emit notification to user
          emitNotification({
            message: 'Session expired. Please login again.',
            severity: 'warning',
          });

          // Redirect to login page
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }

          return Promise.reject(error);
        }
      } catch (refreshError) {
        processQueue(refreshError);
        clearTokens();

        // Emit notification
        emitNotification({
          message: 'Session expired. Please login again.',
          severity: 'warning',
        });

        // Redirect to login
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ----------------------
// Error notification interceptor
// ----------------------
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't show notification for 401 (handled by JWT interceptor)
    if (error.response?.status !== 401) {
      const message = extractErrorMessage(error);
      const fieldErrors = extractFieldErrors(error);
      emitNotification({ message, severity: 'error' });
      return Promise.reject(Object.assign(error, { friendlyMessage: message, fieldErrors }));
    }
    return Promise.reject(error);
  }
);

// ----------------------
// Progress tracking interceptor
// ----------------------
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
  list: async (opts?: {
    limit?: number;
    offset?: number;
    is_active?: boolean;
    strategy_type?: string;
  }): Promise<ApiListResponse<Strategy>> => {
    const r = await api.get('/strategies', {
      params: {
        limit: opts?.limit,
        offset: opts?.offset,
        is_active: opts?.is_active,
        strategy_type: opts?.strategy_type,
      },
    });
    return r.data;
  },
  get: async (id: number): Promise<Strategy> => {
    const r = await api.get(`/strategies/${id}`);
    return r.data;
  },
  create: async (payload: Partial<Strategy>) => {
    const r = await api.post('/strategies', payload);
    return r.data as Strategy;
  },
  update: async (id: number, payload: Partial<Strategy>) => {
    const r = await api.put(`/strategies/${id}`, payload);
    return r.data as Strategy;
  },
  remove: async (id: number) => {
    const r = await api.delete(`/strategies/${id}`);
    return r.data as { success: boolean };
  },
};

export const BacktestsApi = {
  list: async (opts?: {
    limit?: number;
    offset?: number;
    strategy_id?: number;
    symbol?: string;
    status?: string;
    order_by?: string;
    order_dir?: 'asc' | 'desc';
  }): Promise<ApiListResponse<Backtest>> => {
    const r = await api.get('/backtests', {
      params: {
        limit: opts?.limit,
        offset: opts?.offset,
        strategy_id: opts?.strategy_id,
        symbol: opts?.symbol,
        status: opts?.status,
        order_by: opts?.order_by,
        order_dir: opts?.order_dir,
      },
    });
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
  trades: async (
    backtestId: number,
    opts?: { side?: 'buy' | 'sell'; limit?: number; offset?: number }
  ): Promise<{ items: Trade[]; total?: number }> => {
    const params: any = {};
    if (opts?.side) params.side = opts.side;
    if (opts?.limit != null) params.limit = opts.limit;
    if (opts?.offset != null) params.offset = opts.offset;
    const r = await api.get(`/backtests/${backtestId}/trades`, { params });
    const items = (Array.isArray(r.data) ? r.data : r.data.items || []).map((t: any) => ({
      ...t,
      entry_time: parseIso(t.entry_time),
    }));
    const total = Array.isArray(r.data) ? items.length : r.data.total;
    return { items, total };
  },

  // ========================================================================
  // Charts API (ТЗ 3.7.2)
  // ========================================================================

  getEquityCurve: async (
    backtestId: number,
    showDrawdown: boolean = true
  ): Promise<{ plotly_json: string }> => {
    const r = await api.get(`/backtests/${backtestId}/charts/equity_curve`, {
      params: { show_drawdown: showDrawdown },
    });
    return r.data;
  },

  getDrawdownOverlay: async (backtestId: number): Promise<{ plotly_json: string }> => {
    const r = await api.get(`/backtests/${backtestId}/charts/drawdown_overlay`);
    return r.data;
  },

  getPnlDistribution: async (
    backtestId: number,
    bins: number = 30
  ): Promise<{ plotly_json: string }> => {
    const r = await api.get(`/backtests/${backtestId}/charts/pnl_distribution`, {
      params: { bins },
    });
    return r.data;
  },

  // ========================================================================
  // CSV Export (ТЗ 4)
  // ========================================================================

  exportCSV: async (
    backtestId: number,
    reportType: 'list_of_trades' | 'performance' | 'risk_ratios' | 'trades_analysis' | 'all'
  ): Promise<Blob> => {
    const r = await api.get(`/backtests/${backtestId}/export/${reportType}`, {
      responseType: 'blob',
    });
    return r.data;
  },
};

export const DataApi = {
  backtestOverlays: async (
    backtestId: number
  ): Promise<{
    ohlcv: Array<{
      time: number;
      open: number;
      high: number;
      low: number;
      close: number;
      volume?: number;
    }>;
    indicators: { columns: string[]; rows: Array<Record<string, number | string | null>> };
    benchmarks: { columns: string[]; rows: Array<Record<string, number | string | null>> };
    growth: { columns: string[]; rows: Array<Record<string, number | string | null>> };
  }> => {
    const r = await api.get(`/backtests/${backtestId}/overlays`);
    const data = r.data || {};
    const normCandles = (Array.isArray(data.ohlcv) ? data.ohlcv : []).map((c: any) => ({
      time: Math.floor(Number(c.time) || 0),
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
      volume: c.volume != null ? +c.volume : undefined,
    }));
    return {
      ohlcv: normCandles,
      indicators: data.indicators || { columns: [], rows: [] },
      benchmarks: data.benchmarks || { columns: [], rows: [] },
      growth: data.growth || { columns: [], rows: [] },
    };
  },
  resetWorkingSets: async (
    symbol: string,
    intervals: string[],
    reload: boolean = true,
    loadLimit: number = 1000
  ): Promise<{ symbol: string; intervals: string[]; ram_working_set: Record<string, number> }> => {
    const fd = new FormData();
    fd.append('symbol', symbol);
    fd.append('intervals', intervals.join(','));
    fd.append('reload', reload ? '1' : '0');
    fd.append('load_limit', String(loadLimit));
    const r = await api.post('/marketdata/bybit/reset', fd);
    return r.data;
  },
  primeWorkingSets: async (
    symbol: string,
    intervals: string[],
    loadLimit: number = 1000
  ): Promise<{ symbol: string; intervals: string[]; ram_working_set: Record<string, number> }> => {
    const fd = new FormData();
    fd.append('symbol', symbol);
    fd.append('intervals', intervals.join(','));
    fd.append('load_limit', String(loadLimit));
    const r = await api.post('/marketdata/bybit/prime', fd);
    return r.data;
  },
  // Upload market data file; returns {upload_id, filename, size, symbol, interval, stored_path}
  upload: async (formData: FormData, onProgress?: (pct: number) => void) => {
    const r = await api.post('/marketdata/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt: any) => {
        try {
          if (
            evt &&
            typeof evt.loaded === 'number' &&
            typeof evt.total === 'number' &&
            evt.total > 0
          ) {
            const pct = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
            onProgress?.(pct);
          }
        } catch {}
      },
    });
    return r.data;
  },
  ingestUpload: async (
    uploadId: string,
    symbol: string,
    interval: string,
    fmt: 'csv' | 'jsonl' = 'csv'
  ): Promise<{
    upload_id: string;
    symbol: string;
    interval: string;
    format: string;
    ingested: number;
    skipped?: number;
    earliest_ms?: number;
    latest_ms?: number;
    updated_working_set?: number;
  }> => {
    const fd = new FormData();
    fd.append('symbol', symbol);
    fd.append('interval', interval);
    fd.append('fmt', fmt);
    const r = await api.post(`/marketdata/uploads/${encodeURIComponent(uploadId)}/ingest`, fd);
    return r.data;
  },
  marketData: async (symbol: string): Promise<MarketDataPoint[]> => {
    const r = await api.get(`/marketdata/${encodeURIComponent(symbol)}`);
    return r.data;
  },
  bybitKlines: async (
    symbol: string,
    interval: string = '1',
    limit: number = 500,
    persist = 0
  ): Promise<
    Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }>
  > => {
    const r = await api.get(`/marketdata/bybit/klines/fetch`, {
      params: { symbol, interval, limit, persist },
    });
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
  // Fetch historical klines from DB (audit table), older-than or equal to start_time
  bybitKlinesDb: async (
    symbol: string,
    limit: number = 500,
    startTimeSec?: number
  ): Promise<
    Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }>
  > => {
    const params: any = { symbol, limit };
    if (typeof startTimeSec === 'number' && isFinite(startTimeSec)) {
      params.start_time = Math.floor(startTimeSec * 1000); // API expects ms
    }
    const r = await api.get(`/marketdata/bybit/klines`, { params });
    const rows = (r.data || []) as Array<any>;
    // API returns newest-first (desc by open_time). Convert to asc as chart expects.
    const asc = [...rows].reverse();
    return asc.map((c: any) => ({
      time: Math.floor((c.open_time ?? 0) / 1000),
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
      volume: c.volume != null ? +c.volume : undefined,
    }));
  },
  bybitWorkingSet: async (
    symbol: string,
    interval: string = '15',
    loadLimit: number = 1000
  ): Promise<
    Array<{ time: number; open: number; high: number; low: number; close: number; volume?: number }>
  > => {
    const r = await api.get(`/marketdata/bybit/klines/working`, {
      params: { symbol, interval, load_limit: loadLimit },
    });
    // Endpoint already returns seconds-based time; normalize just in case
    return (r.data || []).map((c: any) => ({
      time: Math.floor(c.time ?? 0),
      open: +c.open,
      high: +c.high,
      low: +c.low,
      close: +c.close,
      volume: c.volume != null ? +c.volume : undefined,
    }));
  },

  bybitRecentTrades: async (
    symbol: string,
    limit: number = 250
  ): Promise<Array<{ time: number; price: number; qty: number; side: string }>> => {
    const r = await api.get(`/marketdata/bybit/recent-trades`, { params: { symbol, limit } });
    // Return trades as-is: {time(ms), price, qty, side}
    return r.data || [];
  },
};

// ======================
// Optimizations API
// ======================

export const OptimizationsApi = {
  list: async (opts?: {
    limit?: number;
    offset?: number;
    status?: string;
    strategy_id?: number;
  }): Promise<ApiListResponse<Optimization>> => {
    const r = await api.get('/optimizations', {
      params: {
        limit: opts?.limit,
        offset: opts?.offset,
        status: opts?.status,
        strategy_id: opts?.strategy_id,
      },
    });
    return r.data;
  },
  get: async (id: number): Promise<Optimization> => {
    const r = await api.get(`/optimizations/${id}`);
    return r.data;
  },
  create: async (payload: {
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
  }): Promise<Optimization> => {
    const r = await api.post('/optimizations', payload);
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
    payload: {
      strategy_config?: Record<string, any>;
      param_space?: Record<string, any>;
      metric?: string;
      queue?: string;
    }
  ): Promise<OptimizationEnqueueResponse> => {
    const r = await api.post(`/optimizations/${id}/run/grid`, payload);
    return r.data;
  },
  runWalkForward: async (
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
  ): Promise<OptimizationEnqueueResponse> => {
    const r = await api.post(`/optimizations/${id}/run/walk-forward`, payload);
    return r.data;
  },
  runBayesian: async (
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
  const recentTrades = sorted.filter((t) => t.time >= cutoff);
  if (recentTrades.length === 0) return null;

  // Build OHLCV
  const prices = recentTrades.map((t) => t.price);
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
  trades: Array<{ time: number; price: number; qty: number; side: string }>,
  interval: string | number = '1'
): { time: number; open: number; high: number; low: number; close: number; volume: number } | null {
  if (!trades || trades.length === 0) return null;

  // Sort by time ascending
  const sorted = [...trades].sort((a, b) => a.time - b.time);

  // Determine bucket size in seconds based on interval
  const bucketSec = (() => {
    if (typeof interval === 'number') return Math.max(1, Math.floor(interval)) * 60; // minutes
    const iv = String(interval).trim().toUpperCase();
    if (iv === 'D') return 86400;
    if (iv === 'W') return 7 * 86400;
    const n = parseInt(iv, 10);
    return (isFinite(n) && n > 0 ? n : 1) * 60;
  })();

  // Compute bucket [start,end) for the most recent trade
  const lastTrade = sorted[sorted.length - 1];
  const lastSec = Math.floor(lastTrade.time / 1000);
  const windowStartSec = Math.floor(lastSec / bucketSec) * bucketSec;
  const windowEndSec = windowStartSec + bucketSec;
  const windowStartMs = windowStartSec * 1000;
  const windowEndMs = windowEndSec * 1000;

  // Filter trades in current minute
  const minuteTrades = sorted.filter((t) => t.time >= windowStartMs && t.time < windowEndMs);

  if (minuteTrades.length === 0) return null;

  // Build OHLCV
  const prices = minuteTrades.map((t) => t.price);
  const open = minuteTrades[0].price;
  const close = minuteTrades[minuteTrades.length - 1].price;
  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const volume = minuteTrades.reduce((sum, t) => sum + t.qty, 0);

  // Time in seconds (lightweight-charts expects epoch seconds)
  const time = windowStartSec;

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
    .filter((t) => t.time >= startMs && t.time < endMs)
    .sort((a, b) => a.time - b.time);
  if (inWindow.length === 0) return null;
  const prices = inWindow.map((t) => t.price);
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
