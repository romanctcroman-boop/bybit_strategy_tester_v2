import api from './api';
import { Bot, BotStatus } from '../types/bots';

type ApiBot = {
  id: string;
  name: string;
  strategy: string;
  symbols: string[];
  capital_allocated: number;
  status: BotStatus | 'error' | 'running' | 'stopped' | 'awaiting_start' | 'awaiting_stop';
  created_at: string;
};

type ListResponse<T> = { items: T[]; total: number };

function mapApiBot(b: ApiBot): Bot {
  return {
    id: b.id,
    name: b.name,
    direction: 'LONG',
    exchange: 'BYBIT_FUTURES',
    depositUsd: b.capital_allocated,
    leverage: 3,
    status: (b.status as BotStatus) ?? 'stopped',
    metrics: {},
  };
}

export const BotsService = {
  list: async (opts?: { limit?: number; offset?: number }): Promise<ListResponse<Bot>> => {
    const r = await api.get<ListResponse<ApiBot>>('/bots', { params: { limit: opts?.limit, offset: opts?.offset } });
    const items = (r.data.items || []).map(mapApiBot);
    return { items, total: r.data.total };
  },
  get: async (id: string): Promise<Bot> => {
    const r = await api.get<ApiBot>(`/bots/${encodeURIComponent(id)}`);
    return mapApiBot(r.data);
  },
  start: async (id: string) => {
    await api.post(`/bots/${encodeURIComponent(id)}/start`, {});
  },
  stop: async (id: string) => {
    await api.post(`/bots/${encodeURIComponent(id)}/stop`, {});
  },
  delete: async (id: string) => {
    await api.post(`/bots/${encodeURIComponent(id)}/delete`, {});
  },
};
