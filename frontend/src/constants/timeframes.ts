/**
 * Timeframes constants
 * Centralized list of available timeframes across the application
 */

export interface TimeframeOption {
  value: string;
  label: string;
}

/**
 * Complete list of Bybit-supported timeframes
 * Value format: minutes as string ('1', '5', '15', etc.) or 'D', 'W' for day/week
 */
export const TIMEFRAMES: TimeframeOption[] = [
  { value: '1', label: '1m' },
  { value: '3', label: '3m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '30', label: '30m' },
  { value: '60', label: '1h' },
  { value: '120', label: '2h' },
  { value: '240', label: '4h' },
  { value: '360', label: '6h' },
  { value: '720', label: '12h' },
  { value: 'D', label: '1D' },
  { value: 'W', label: '1W' },
];

/**
 * Common timeframes for quick selection
 */
export const COMMON_TIMEFRAMES: TimeframeOption[] = [
  { value: '1', label: '1m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '60', label: '1h' },
  { value: '240', label: '4h' },
  { value: 'D', label: '1D' },
];

/**
 * Format interval value to human-readable label
 */
export function formatIntervalLabel(interval: string): string {
  const found = TIMEFRAMES.find((tf) => tf.value === interval);
  if (found) return found.label;

  // Fallback formatting
  const upper = String(interval).toUpperCase();
  if (upper === 'D') return '1d';
  if (upper === 'W') return '1w';

  const n = parseInt(upper, 10);
  if (isNaN(n)) return upper;
  if (n % 60 === 0) return `${n / 60}h`;
  if (n >= 1440) return `${Math.round(n / 1440)}d`;
  return `${n}m`;
}

/**
 * Get timeframe label by value
 */
export function getTimeframeLabel(value: string): string {
  const found = TIMEFRAMES.find((tf) => tf.value === value);
  return found?.label || value;
}

/**
 * Convert interval to seconds (for calculations)
 */
export function intervalToSeconds(interval: string): number {
  const upper = String(interval).toUpperCase();
  if (upper === 'D') return 86400;
  if (upper === 'W') return 604800;

  const n = parseInt(upper, 10);
  if (isNaN(n)) return 60; // Default 1 minute
  return n * 60;
}
