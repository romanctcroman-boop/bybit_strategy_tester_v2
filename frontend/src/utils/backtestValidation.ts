/**
 * Backtest Validation Utilities
 */
import { VALIDATION_RULES } from '../constants/backtest';

export interface ValidationError {
  field: string;
  message: string;
}

/**
 * Валидация полной формы бэктеста
 */
export const validateBacktestForm = (formData: {
  strategy: any;
  startDate: Date | null;
  endDate: Date | null;
  initialCapital: number;
  commission: number;
  leverage: number;
  strategyParams: Record<string, any>;
}): string | null => {
  const { strategy, startDate, endDate, initialCapital, commission, leverage, strategyParams } =
    formData;

  // Strategy validation
  if (!strategy) {
    return 'Выберите стратегию';
  }

  // Date validation
  if (!startDate || !endDate) {
    return 'Выберите период данных';
  }

  if (startDate >= endDate) {
    return 'Дата начала должна быть раньше даты окончания';
  }

  // Check future dates
  const now = new Date();
  if (endDate > now) {
    return 'Конечная дата не может быть в будущем';
  }

  // Check max date range (2 years)
  const daysDiff = Math.floor((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  if (daysDiff > VALIDATION_RULES.maxDateRangeDays) {
    return `Максимальный период: ${VALIDATION_RULES.maxDateRangeDays} дней (≈2 года)`;
  }

  // Initial capital validation
  if (initialCapital <= 0) {
    return 'Начальный капитал должен быть положительным';
  }

  if (initialCapital < VALIDATION_RULES.initialCapital.min) {
    return `Минимальный капитал: ${VALIDATION_RULES.initialCapital.min} USDT`;
  }

  if (initialCapital > VALIDATION_RULES.initialCapital.max) {
    return `Максимальный капитал: ${VALIDATION_RULES.initialCapital.max.toLocaleString()} USDT`;
  }

  // Commission validation
  if (commission < VALIDATION_RULES.commission.min) {
    return 'Комиссия не может быть отрицательной';
  }

  if (commission > VALIDATION_RULES.commission.max) {
    return `Максимальная комиссия: ${VALIDATION_RULES.commission.max}%`;
  }

  // Leverage validation
  if (leverage < VALIDATION_RULES.leverage.min) {
    return `Минимальное плечо: ${VALIDATION_RULES.leverage.min}x`;
  }

  if (leverage > VALIDATION_RULES.leverage.max) {
    return `Максимальное плечо: ${VALIDATION_RULES.leverage.max}x`;
  }

  if (!Number.isInteger(leverage)) {
    return 'Плечо должно быть целым числом';
  }

  // Strategy params validation
  if (!strategyParams || Object.keys(strategyParams).length === 0) {
    return 'Параметры стратегии обязательны';
  }

  // Validate all params are numbers and positive where applicable
  for (const [key, value] of Object.entries(strategyParams)) {
    if (typeof value === 'number') {
      if (isNaN(value) || !isFinite(value)) {
        return `Параметр ${key}: некорректное значение`;
      }

      // Most numeric params should be positive
      if (!key.includes('direction') && value <= 0) {
        return `Параметр ${key}: должен быть положительным`;
      }
    }
  }

  return null;
};

/**
 * Sanitization параметров стратегии
 * Защита от injection атак и некорректных данных
 */
export const sanitizeStrategyParams = (params: Record<string, any>): Record<string, any> => {
  const sanitized: Record<string, any> = {};

  Object.keys(params).forEach((key) => {
    const value = params[key];

    // Validate and sanitize numbers
    if (typeof value === 'number') {
      if (!isNaN(value) && isFinite(value)) {
        sanitized[key] = value;
      }
    }
    // Validate and sanitize strings (for direction field)
    else if (typeof value === 'string') {
      // Remove dangerous characters
      const cleaned = value.replace(/[<>"']/g, '').trim();

      // Validate against whitelist for direction field
      if (key === 'direction' && ['long', 'short', 'both'].includes(cleaned)) {
        sanitized[key] = cleaned;
      } else if (key !== 'direction') {
        // For other string fields, limit length
        sanitized[key] = cleaned.substring(0, 50);
      }
    }
  });

  return sanitized;
};

/**
 * Получить user-friendly error message из API error
 */
export const getErrorMessage = (error: any): string => {
  // Rate limit
  if (error.response?.status === 429) {
    return 'Слишком много запросов. Попробуйте через 60 секунд.';
  }

  // Validation error
  if (error.response?.status === 400) {
    const detail = error.response?.data?.detail || '';

    if (detail.includes('insufficient data') || detail.includes('not enough data')) {
      return 'Недостаточно исторических данных для выбранного периода.';
    }

    if (detail.includes('symbol')) {
      return 'Выбранный символ недоступен или некорректен.';
    }

    if (detail.includes('timeframe')) {
      return 'Выбранный таймфрейм недоступен.';
    }

    return `Некорректные параметры: ${detail}`;
  }

  // Not found
  if (error.response?.status === 404) {
    return 'Символ или стратегия не найдены на сервере.';
  }

  // Server error
  if (error.response?.status >= 500) {
    return 'Ошибка сервера. Попробуйте позже или обратитесь в поддержку.';
  }

  // Network error
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return 'Timeout: сервер не отвечает. Проверьте соединение.';
  }

  if (error.message === 'Network Error') {
    return 'Ошибка сети. Проверьте интернет-соединение.';
  }

  // Default
  return error.response?.data?.detail || error.message || 'Неизвестная ошибка при запуске бэктеста';
};

/**
 * Форматирование даты для backend (UTC, YYYY-MM-DD)
 */
export const formatDateForBackend = (date: Date): string => {
  // Используем UTC для избежания timezone issues
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
};
