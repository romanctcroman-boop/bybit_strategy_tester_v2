import api from './api';

export type ActiveDeal = {
  id: string;
  bot_id: string;
  symbol: string;
  entry_price: number;
  quantity: number;
  next_open_price: number;
  current_price?: number;
  pnl_abs: number;
  pnl_pct: number;
  opened_at: string;
};

type ListResponse<T> = { items: T[]; total: number };

export const ActiveDealsService = {
  list: async (): Promise<ListResponse<ActiveDeal>> => {
    const r = await api.get<ListResponse<ActiveDeal>>('/active-deals');
    return r.data;
  },
  close: async (id: string) => {
    await api.post(`/active-deals/${encodeURIComponent(id)}/close`, {});
  },
  average: async (id: string) => {
    await api.post(`/active-deals/${encodeURIComponent(id)}/average`, {});
  },
  cancel: async (id: string) => {
    await api.post(`/active-deals/${encodeURIComponent(id)}/cancel`, {});
  },
};
