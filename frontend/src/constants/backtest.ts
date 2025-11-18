/**
 * Backtest Constants
 *
 * Константы для форм и конфигураций бэктеста
 */
import type { Strategy } from '../types/backtest';

export const SYMBOLS = [
  'BTCUSDT',
  'ETHUSDT',
  'BNBUSDT',
  'SOLUSDT',
  'XRPUSDT',
  'ADAUSDT',
  'DOGEUSDT',
  'AVAXUSDT',
  'MATICUSDT',
  'LINKUSDT',
] as const;

export const TIMEFRAMES = [
  { value: '1m', label: '1 минута' },
  { value: '5m', label: '5 минут' },
  { value: '15m', label: '15 минут' },
  { value: '1h', label: '1 час' },
  { value: '4h', label: '4 часа' },
  { value: '1d', label: '1 день' },
  { value: '1w', label: '1 неделя' },
] as const;

export const DEFAULT_STRATEGIES: Strategy[] = [
  {
    id: 1,
    name: 'Bollinger Bands Mean Reversion',
    type: 'bollinger',
    description: 'Mean reversion на основе Bollinger Bands',
    default_params: {
      bb_period: 20,
      bb_std_dev: 2.0,
      entry_threshold_pct: 0.05,
      stop_loss_pct: 0.8,
      max_holding_bars: 48,
    },
  },
  {
    id: 2,
    name: 'EMA Crossover',
    type: 'ema_crossover',
    description: 'Пересечение быстрой и медленной EMA',
    default_params: {
      fast_ema: 10,
      slow_ema: 30,
      direction: 'long',
    },
  },
  {
    id: 3,
    name: 'RSI Strategy',
    type: 'rsi',
    description: 'Торговля на основе RSI overbought/oversold',
    default_params: {
      rsi_period: 14,
      rsi_overbought: 70,
      rsi_oversold: 30,
      direction: 'both',
    },
  },
];

// Validation constants
export const VALIDATION_RULES = {
  initialCapital: {
    min: 100,
    max: 1_000_000,
  },
  commission: {
    min: 0,
    max: 100,
  },
  leverage: {
    min: 1,
    max: 100,
  },
  maxDateRangeDays: 730, // 2 years
} as const;
