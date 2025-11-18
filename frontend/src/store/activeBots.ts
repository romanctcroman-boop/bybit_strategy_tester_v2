import { create } from 'zustand';
import { ActiveDealsService, ActiveDeal } from '../services/activeDeals';
import { subscribeKline } from '../services/bybitWs';

export type Side = 'LONG' | 'SHORT';

export interface ActiveBot {
  id: string;
  name: string;
  side: Side;
  symbol?: string;
  qty?: number;
  orderProgress?: string; // e.g., '1 / 5'
  // price levels for visualization
  min: number; // left bound of scale
  entry: number; // red marker (limit entry)
  nextOpen: number; // blue label (next candle open)
  current?: number; // current price (optional)
  target: number; // right green marker (close/TP threshold)
  pnlUsd: number;
  pnlPct: number; // -0.56
}

type State = {
  items: ActiveBot[];
  filter: string;
  liveSubs: Record<string, () => void>; // symbol -> unsubscribe
};

type Actions = {
  setFilter: (q: string) => void;
  load: () => Promise<void>;
  refresh: () => Promise<void>;
  closeDeal: (id: string) => Promise<void>;
  averageDeal: (id: string) => Promise<void>;
  cancelDeal: (id: string) => Promise<void>;
  attachLive: (interval?: string) => void;
  detachLive: () => void;
};

function mapDealToActiveBot(d: ActiveDeal): ActiveBot {
  const entry = d.entry_price;
  const nextOpen = d.next_open_price;
  const current = d.current_price ?? undefined;
  const baseMin = Math.min(entry, nextOpen, current ?? entry);
  const baseMax = Math.max(entry, nextOpen, current ?? entry);
  const pad = (baseMax - baseMin) * 0.2 || (baseMin * 0.01);
  const min = baseMin - pad;
  const target = baseMax + pad;
  return {
    id: d.id,
    name: `${d.symbol} • ${d.bot_id}`,
    side: 'LONG',
    symbol: d.symbol,
    qty: d.quantity,
    orderProgress: undefined,
    min,
    entry,
    nextOpen,
    current,
    target,
    pnlUsd: Math.round(d.pnl_abs * 100) / 100,
    pnlPct: Math.round(d.pnl_pct * 100) / 100,
  };
}

export const useActiveBots = create<State & Actions>((set, get) => {
  // simple per-symbol throttle map
  const lastUpdate: Record<string, number> = {};
  const THROTTLE_MS = 200;

  function ensureLive(interval: string = '1') {
    const state = get();
    const symbols = Array.from(new Set(state.items.map((it) => it.symbol).filter(Boolean))) as string[];
    const existing = new Set(Object.keys(state.liveSubs));
    // unsubscribe removed
    for (const sym of existing) {
      if (!symbols.includes(sym)) {
        try { state.liveSubs[sym](); } catch {}
        delete state.liveSubs[sym];
      }
    }
    // subscribe new
    for (const sym of symbols) {
      if (state.liveSubs[sym]) continue;
      const unsub = subscribeKline(sym, interval, (k) => {
        const now = Date.now();
        if ((lastUpdate[sym] ?? 0) + THROTTLE_MS > now) return;
        lastUpdate[sym] = now;
        set((prev) => ({
          items: prev.items.map((it) => (it.symbol === sym ? { ...it, current: k.close } : it)),
        }));
      });
      state.liveSubs[sym] = unsub;
    }
  }

  return {
    items: [],
    filter: '',
    liveSubs: {},
    setFilter: (q) => set({ filter: q }),
    load: async () => {
      const { items } = await ActiveDealsService.list();
      set({ items: items.map(mapDealToActiveBot) });
    },
    refresh: async () => {
      await get().load();
    },
    closeDeal: async (id: string) => {
      await ActiveDealsService.close(id);
      await get().load();
    },
    averageDeal: async (id: string) => {
      await ActiveDealsService.average(id);
      await get().load();
    },
    cancelDeal: async (id: string) => {
      await ActiveDealsService.cancel(id);
      await get().load();
    },
    attachLive: (interval = '1') => {
      ensureLive(interval);
    },
    detachLive: () => {
      const state = get();
      for (const sym of Object.keys(state.liveSubs)) {
        try { state.liveSubs[sym](); } catch {}
        delete state.liveSubs[sym];
      }
    },
  };
});

export function selectFilteredActive(state: State): ActiveBot[] {
  const q = state.filter.trim().toLowerCase();
  if (!q) return state.items;
  return state.items.filter((x) => x.name.toLowerCase().includes(q));
}
