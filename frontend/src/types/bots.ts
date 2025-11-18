export type BotDirection = 'LONG' | 'SHORT';

export type BotStatus =
  | 'awaiting_signal' // ОЖИДАЕТ СИГНАЛА
  | 'awaiting_start' // ОЖИДАЕТ ЗАПУСКА (подписывается на индикаторы)
  | 'running' // ИДЁТ СДЕЛКА / АКТИВЕН
  | 'awaiting_stop' // ОЖИДАЕТ ОСТАНОВКИ (дождётся завершения сделки)
  | 'stopped' // ОСТАНОВЛЕН
  | 'error';

export interface BotMetrics {
  roiPct?: number; // total ROI in percent
  pnlUsd?: number; // PnL in USD
  winRatePct?: number; // 0..100
  sharpe?: number;
}

export interface Bot {
  id: string;
  name: string;
  direction: BotDirection;
  label?: string; // e.g., family name/badge
  exchange: 'BYBIT_FUTURES' | 'BINANCE_FUTURES';
  depositUsd: number;
  leverage: number; // x5
  status: BotStatus;
  metrics?: BotMetrics;
}

export const botStatusLabel: Record<BotStatus, string> = {
  awaiting_start: 'ОЖИДАЕТ ЗАПУСКА',
  awaiting_signal: 'ОЖИДАЕТ СИГНАЛА',
  running: 'АКТИВЕН',
  awaiting_stop: 'ОЖИДАЕТ ОСТАНОВКИ',
  stopped: 'ОСТАНОВЛЕН',
  error: 'ОШИБКА',
};

export function exchangeLabel(x: Bot['exchange']): string {
  switch (x) {
    case 'BYBIT_FUTURES':
      return 'BYBIT FUTURES';
    case 'BINANCE_FUTURES':
      return 'BINANCE FUTURES';
  }
}
