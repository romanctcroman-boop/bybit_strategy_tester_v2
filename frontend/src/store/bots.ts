import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Bot, BotStatus } from '../types/bots';
import { BotsService } from '../services/bots';
import { nanoid } from '../utils/nanoid';
import { botsPersistConfig } from './persistConfig';

interface BotsState {
  items: Bot[];
  filter: string;
  setFilter: (q: string) => void;
  load: () => Promise<void>;
  createBot: (partial?: Partial<Bot>) => Bot;
  startBot: (id: string) => Promise<void>;
  stopBot: (id: string) => Promise<void>;
  cloneBot: (id: string) => Bot | undefined;
  setStatus: (id: string, status: BotStatus) => void;
  removeBot: (id: string) => Promise<void>;
}

const initial: Bot[] = [
  {
    id: 'bot_sol_long',
    name: 'SOL-LONG-Dimkud-BIG2-1.7',
    direction: 'LONG',
    label: 'DIMKUD MULTI · ВНУТРИДНЕВНОЙ 30 МИНУТ',
    exchange: 'BYBIT_FUTURES',
    depositUsd: 100,
    leverage: 5,
    status: 'awaiting_signal',
    metrics: { roiPct: 12.4, pnlUsd: 34.2, winRatePct: 57.8 },
  },
  {
    id: 'bot_pnut_short',
    name: 'PNUT-SHORT-15-min-1ordSL',
    direction: 'SHORT',
    label: 'DIMKUD MULTI · ВНУТРИДНЕВНОЙ 5 МИНУТ',
    exchange: 'BYBIT_FUTURES',
    depositUsd: 15,
    leverage: 5,
    status: 'stopped',
    metrics: { roiPct: -2.1, pnlUsd: -0.8, winRatePct: 48.3 },
  },
];

export const useBotsStore = create<BotsState>()(
  persist(
    (set, get) => ({
      items: initial,
      filter: '',
      setFilter: (q: string) => set({ filter: q }),
      load: async () => {
        try {
          const { items } = await BotsService.list();
          set({ items });
        } catch (e) {
          // Avoid unhandledrejection on startup if API is unreachable
          console.warn('Failed to load bots:', e);
        }
      },
      createBot: (partial?: Partial<Bot>) => {
        const bot: Bot = {
          id: nanoid(),
          name: partial?.name || 'New Bot',
          direction: partial?.direction || 'LONG',
          label: partial?.label || 'CUSTOM · DRAFT',
          exchange: partial?.exchange || 'BYBIT_FUTURES',
          depositUsd: partial?.depositUsd ?? 100,
          leverage: partial?.leverage ?? 5,
          status: partial?.status || 'awaiting_signal',
          metrics: partial?.metrics,
        };
        set({ items: [bot, ...get().items] });
        return bot;
      },
      startBot: async (id: string) => {
        await BotsService.start(id);
        await get().load();
      },
      stopBot: async (id: string) => {
        await BotsService.stop(id);
        await get().load();
      },
      cloneBot: (id: string) => {
        const src = get().items.find((b: Bot) => b.id === id);
        if (!src) return undefined;
        const clone: Bot = { ...src, id: nanoid(), name: src.name + ' (copy)', status: 'stopped' };
        set({ items: [clone, ...get().items] });
        return clone;
      },
      setStatus: (id, status) =>
        set({ items: get().items.map((b) => (b.id === id ? { ...b, status } : b)) }),
      removeBot: async (id) => {
        await BotsService.delete(id);
        await get().load();
      },
    }),
    botsPersistConfig
  )
);

export function selectFilteredBots(state: BotsState): Bot[] {
  const q = state.filter.trim().toLowerCase();
  if (!q) return state.items;
  return state.items.filter((b) =>
    [b.name, b.label, b.direction, String(b.depositUsd)].some((t) =>
      (t || '').toString().toLowerCase().includes(q)
    )
  );
}
