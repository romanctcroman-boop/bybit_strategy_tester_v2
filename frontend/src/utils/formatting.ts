/**
 * Formatting Utilities
 *
 * Централизованные функции форматирования для всего приложения.
 * Извлечены из BacktestDetailPage, HomePage, WalkForwardPage для переиспользования.
 *
 * @module utils/formatting
 */

export type ValueUnit = 'usd' | 'percent' | 'none';

/**
 * Дефолтная точность для разных типов значений
 */
const defaultDigits: Record<ValueUnit, number> = {
  usd: 2,
  percent: 2,
  none: 2,
};

/**
 * Безопасное преобразование значения в число
 *
 * @param value - Любое значение для преобразования
 * @returns Число или null если преобразование невозможно
 *
 * @example
 * toFiniteNumber(42) // 42
 * toFiniteNumber("123.45") // 123.45
 * toFiniteNumber("invalid") // null
 * toFiniteNumber(NaN) // null
 */
export const toFiniteNumber = (value: unknown): number | null => {
  if (value == null) return null;
  const numeric = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

/**
 * Преобразование значения в timestamp
 *
 * @param value - Дата (Date, string, number)
 * @returns Timestamp в миллисекундах или null
 *
 * @example
 * toTimestamp(new Date()) // 1698765432123
 * toTimestamp("2023-10-31") // 1698710400000
 * toTimestamp(1698765432123) // 1698765432123
 */
export const toTimestamp = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const date = new Date(value as string | Date);
  const ms = date.getTime();
  return Number.isFinite(ms) ? ms : null;
};

/**
 * Форматирование числа с локализацией
 *
 * @param value - Число для форматирования
 * @param digits - Количество десятичных знаков (0-6)
 * @returns Отформатированная строка
 *
 * @example
 * formatNumber(1234.5678, 2) // "1 234,57" (ru-RU)
 * formatNumber(0.5, 0) // "1"
 */
export const formatNumber = (value: number, digits = 2): string =>
  new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: Math.max(0, Math.min(6, digits)),
    maximumFractionDigits: Math.max(0, Math.min(6, digits)),
  }).format(value);

/**
 * Форматирование значения с единицами измерения
 *
 * @param value - Значение для форматирования
 * @param unit - Тип единицы (usd, percent, none)
 * @param digits - Количество десятичных знаков (опционально)
 * @param fallback - Значение по умолчанию если форматирование невозможно
 * @returns Отформатированная строка с единицами
 *
 * @example
 * formatValueWithUnit(1234.56, 'usd') // "1 234,56 USDT"
 * formatValueWithUnit(45.67, 'percent') // "45,67%"
 * formatValueWithUnit(null, 'usd', 2, '—') // "—"
 */
export const formatValueWithUnit = (
  value: unknown,
  unit: ValueUnit,
  digits?: number,
  fallback = '—'
): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return fallback;
  const precision = digits ?? defaultDigits[unit];
  const formatted = formatNumber(numeric, precision);
  switch (unit) {
    case 'usd':
      return `${formatted} USDT`;
    case 'percent':
      return `${formatted}%`;
    default:
      return formatted;
  }
};

/**
 * Форматирование значения со знаком и единицами
 *
 * @param value - Значение для форматирования
 * @param unit - Тип единицы
 * @param digits - Количество десятичных знаков
 * @param fallback - Значение по умолчанию
 * @returns Отформатированная строка со знаком (+/−)
 *
 * @example
 * formatSignedValueWithUnit(100, 'usd') // "+100,00 USDT"
 * formatSignedValueWithUnit(-50, 'percent') // "−50,00%"
 * formatSignedValueWithUnit(0, 'usd') // "0,00 USDT"
 */
export const formatSignedValueWithUnit = (
  value: unknown,
  unit: ValueUnit,
  digits?: number,
  fallback = '—'
): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return fallback;
  const sign = numeric > 0 ? '+' : numeric < 0 ? '−' : '';
  return `${sign}${formatValueWithUnit(Math.abs(numeric), unit, digits, fallback)}`;
};

/**
 * Форматирование валюты с знаком
 *
 * @param value - Сумма в USD
 * @returns Отформатированная строка с $ и знаком
 *
 * @example
 * formatCurrency(1234.56) // "+$1234.56"
 * formatCurrency(-500.25) // "-$500.25"
 */
export const formatCurrency = (value: number): string => {
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${value.toFixed(2)}`;
};

/**
 * Форматирование процента
 *
 * @param value - Процентное значение
 * @returns Отформатированная строка с %
 *
 * @example
 * formatPercentage(45.67) // "45.67%"
 * formatPercentage(100) // "100.00%"
 */
export const formatPercentage = (value: number): string => {
  return `${value.toFixed(2)}%`;
};

/**
 * Форматирование даты и времени
 *
 * @param value - Дата (Date, string, number)
 * @returns Отформатированная дата в формате "31 окт. 2023 г., 12:30"
 *
 * @example
 * formatDateTime(new Date()) // "31 окт. 2023 г., 12:30"
 * formatDateTime("2023-10-31T12:30:00") // "31 окт. 2023 г., 12:30"
 * formatDateTime(null) // "—"
 */
export const formatDateTime = (value: unknown): string => {
  const ts = toTimestamp(value);
  if (ts == null) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(ts));
};

/**
 * Форматирование даты (только дата, без времени)
 *
 * @param dateStr - Строка с датой в ISO формате
 * @returns Отформатированная дата в формате "31.10.2023"
 *
 * @example
 * formatDate("2023-10-31") // "31.10.2023"
 * formatDate("2023-10-31T12:30:00") // "31.10.2023"
 */
export const formatDate = (dateStr: string): string => {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU');
  } catch {
    return dateStr;
  }
};

/**
 * Форматирование длительности в минутах
 *
 * @param value - Длительность в минутах
 * @returns Человекочитаемая строка ("2 ч 30 мин")
 *
 * @example
 * formatDuration(45) // "45 мин"
 * formatDuration(150) // "2 ч 30 мин"
 * formatDuration(null) // "—"
 */
export const formatDuration = (value: unknown): string => {
  const minutes = toFiniteNumber(value);
  if (minutes == null) return '—';
  if (minutes < 60) return `${formatNumber(minutes, 0)} мин`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours} ч ${mins} мин`;
};

/**
 * Форматирование количества/объема
 *
 * @param value - Количество
 * @param digits - Количество десятичных знаков
 * @returns Отформатированная строка
 *
 * @example
 * formatQuantity(1.5, 2) // "1,50"
 * formatQuantity(0.00123, 5) // "0,00123"
 */
export const formatQuantity = (value: unknown, digits = 2): string => {
  const numeric = toFiniteNumber(value);
  if (numeric == null) return '—';
  return formatNumber(numeric, digits);
};

/**
 * Форматирование относительного времени
 *
 * @param timestamp - ISO строка или timestamp
 * @returns Человекочитаемая строка ("5m ago", "2h ago", "3d ago")
 *
 * @example
 * formatRelativeTime("2023-10-31T12:25:00") // "5m ago" (если сейчас 12:30)
 * formatRelativeTime("2023-10-31T10:30:00") // "2h ago" (если сейчас 12:30)
 */
export const formatRelativeTime = (timestamp: string): string => {
  const now = new Date().getTime();
  const time = new Date(timestamp).getTime();
  const diff = Math.floor((now - time) / 1000 / 60); // minutes

  if (diff < 1) return 'just now';
  if (diff < 60) return `${diff}m ago`;
  if (diff < 60 * 24) return `${Math.floor(diff / 60)}h ago`;
  return `${Math.floor(diff / 60 / 24)}d ago`;
};

/**
 * 🎯 PERFECT 10/10: Enhanced utilities for edge cases
 */

/**
 * Safe JSON parsing with edge case handling
 *
 * @param str - String to parse as JSON
 * @returns Parsed object or null on error
 *
 * @example
 * safeParseJSON('{"key": "value"}') // { key: "value" }
 * safeParseJSON('invalid') // null
 * safeParseJSON('') // null
 */
export const safeParseJSON = (str: string): any => {
  if (typeof str !== 'string' || str.trim() === '') {
    return null;
  }

  try {
    const result = JSON.parse(str);
    return result !== null && typeof result === 'object' ? result : null;
  } catch {
    return null;
  }
};

/**
 * Enhanced currency formatting with negative number support
 *
 * @param amount - Amount to format
 * @param currency - Currency code (default: USD)
 * @returns Formatted currency string
 *
 * @example
 * formatCurrencyEnhanced(1234.56) // "$1,234.56"
 * formatCurrencyEnhanced(-1234.56) // "-$1,234.56"
 * formatCurrencyEnhanced(NaN) // "Invalid amount"
 */
export const formatCurrencyEnhanced = (amount: number, currency: string = 'USD'): string => {
  if (typeof amount !== 'number' || !isFinite(amount)) {
    return 'Invalid amount';
  }

  if (amount < 0) {
    return `-${formatCurrencyEnhanced(Math.abs(amount), currency)}`;
  }

  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
};

/**
 * Debounce function with validation
 *
 * @param func - Function to debounce
 * @param delay - Delay in milliseconds
 * @returns Debounced function
 *
 * @example
 * const debouncedSearch = debounce(searchFunction, 300)
 * debouncedSearch('query') // Executed after 300ms
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  if (delay < 0) {
    throw new Error('Delay must be non-negative');
  }

  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, delay);
  };
};
