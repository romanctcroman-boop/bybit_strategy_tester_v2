import axios from 'axios';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import { Strategy, Backtest, Trade, MarketDataPoint, ApiListResponse } from '../types/api';

dayjs.extend(utc);

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 30000,
});

function parseIso(s?: string) {
  return s ? dayjs.utc(s).toDate() : undefined;
}

export const StrategiesApi = {
  list: async (): Promise<ApiListResponse<Strategy>> => {
    const r = await api.get('/strategies');
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
  list: async (): Promise<ApiListResponse<Backtest>> => {
    const r = await api.get('/backtests');
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
  trades: async (backtestId: number): Promise<Trade[]> => {
    const r = await api.get(`/backtests/${backtestId}/trades`);
    return r.data.map((t: any) => ({ ...t, entry_time: parseIso(t.entry_time) }));
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
};

export default api;
