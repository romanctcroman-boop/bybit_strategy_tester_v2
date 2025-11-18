/**
 * Enhanced API Error Handling Utilities
 *
 * Provides:
 * - User-friendly error messages
 * - Error type classification
 * - Retry logic for transient errors
 * - Error logging and reporting
 */
import { ReactNode } from 'react';

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
  timestamp?: string;
  path?: string;
  status?: number;
}

export class EnhancedApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, any>;
  isRetryable: boolean;

  constructor(
    message: string,
    code: string,
    status: number = 500,
    details?: Record<string, any>,
    isRetryable: boolean = false
  ) {
    super(message);
    this.name = 'EnhancedApiError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.isRetryable = isRetryable;
  }
}

/**
 * Get user-friendly error message based on error code/type
 */
export function getUserFriendlyMessage(error: any): string {
  // Network errors
  if (error.message === 'Network Error' || !navigator.onLine) {
    return 'Отсутствует подключение к интернету. Проверьте сеть и попробуйте снова.';
  }

  // Timeout errors
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return 'Превышено время ожидания. Сервер не отвечает. Попробуйте позже.';
  }

  // HTTP status codes
  const status = error.response?.status || error.status;
  const errorData = error.response?.data?.error || {};

  switch (status) {
    case 400:
      return errorData.message || 'Неверные параметры запроса. Проверьте введенные данные.';

    case 401:
      return 'Требуется авторизация. Пожалуйста, войдите в систему.';

    case 403:
      return 'Доступ запрещен. У вас недостаточно прав для этой операции.';

    case 404:
      return errorData.message || 'Запрошенный ресурс не найден.';

    case 409:
      return 'Конфликт данных. Возможно, ресурс уже существует или был изменен.';

    case 422: {
      const field = errorData.details?.field;
      const msg = errorData.message || 'Ошибка валидации данных.';
      return field ? `${msg} (Поле: ${field})` : msg;
    }

    case 429: {
      const retryAfter = errorData.details?.retry_after;
      return retryAfter
        ? `Слишком много запросов. Попробуйте через ${retryAfter} секунд.`
        : 'Слишком много запросов. Пожалуйста, подождите немного.';
    }

    case 500:
      return 'Внутренняя ошибка сервера. Мы уже работаем над решением проблемы.';

    case 502:
      return 'Сервис временно недоступен. Попробуйте позже.';

    case 503:
      return 'Сервис на обслуживании. Попробуйте через несколько минут.';

    case 504:
      return 'Сервер не отвечает. Попробуйте позже.';

    default:
      return (
        errorData.message || error.message || 'Произошла неизвестная ошибка. Попробуйте еще раз.'
      );
  }
}

/**
 * Determine if error is retryable
 */
export function isRetryableError(error: any): boolean {
  const status = error.response?.status || error.status;

  // Network errors are retryable
  if (error.message === 'Network Error' || !navigator.onLine) {
    return true;
  }

  // Timeout errors are retryable
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return true;
  }

  // Specific HTTP status codes that are retryable
  const retryableStatuses = [408, 429, 502, 503, 504];
  if (retryableStatuses.includes(status)) {
    return true;
  }

  return false;
}

/**
 * Parse API error response
 */
export function parseApiError(error: any): EnhancedApiError {
  const status = error.response?.status || error.status || 500;
  const errorData = error.response?.data?.error || {};

  const code = errorData.code || `HTTP_${status}`;
  const message = getUserFriendlyMessage(error);
  const details = errorData.details || {};
  const isRetryable = isRetryableError(error);

  return new EnhancedApiError(message, code, status, details, isRetryable);
}

/**
 * Get error notification config
 */
export interface ErrorNotificationConfig {
  message: string;
  severity: 'error' | 'warning' | 'info';
  autoHideDuration: number | null;
  action?: ReactNode;
}

export function getErrorNotificationConfig(error: EnhancedApiError): ErrorNotificationConfig {
  const baseConfig: ErrorNotificationConfig = {
    message: error.message,
    severity: 'error',
    autoHideDuration: 6000,
  };

  // Network errors - persist until dismissed
  if (error.code === 'Network Error' || error.message.includes('интернету')) {
    return {
      ...baseConfig,
      severity: 'error',
      autoHideDuration: null, // Don't auto-hide
    };
  }

  // Rate limit - warning with longer duration
  if (error.status === 429) {
    return {
      ...baseConfig,
      severity: 'warning',
      autoHideDuration: 10000,
    };
  }

  // Server errors - longer duration
  if (error.status >= 500) {
    return {
      ...baseConfig,
      severity: 'error',
      autoHideDuration: 8000,
    };
  }

  // Validation errors - medium duration
  if (error.status === 422 || error.status === 400) {
    return {
      ...baseConfig,
      severity: 'warning',
      autoHideDuration: 7000,
    };
  }

  // Default
  return baseConfig;
}

/**
 * Log error to external service (Sentry, etc.)
 */
export function logErrorToService(error: EnhancedApiError, context?: Record<string, any>) {
  // In development, just log to console
  if (import.meta.env.DEV) {
    console.group('🔴 API Error');
    console.error('Error:', error);
    console.log('Code:', error.code);
    console.log('Status:', error.status);
    console.log('Details:', error.details);
    console.log('Context:', context);
    console.groupEnd();
    return;
  }

  // In production, send to error tracking service
  try {
    // Example: Sentry integration
    // if (window.Sentry) {
    //   window.Sentry.captureException(error, {
    //     level: 'error',
    //     tags: {
    //       error_code: error.code,
    //       http_status: error.status,
    //     },
    //     extra: {
    //       details: error.details,
    //       context,
    //     },
    //   });
    // }
  } catch (loggingError) {
    console.error('Failed to log error:', loggingError);
  }
}

/**
 * Retry helper with exponential backoff
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000
): Promise<T> {
  let lastError: any;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      const apiError = parseApiError(error);

      // Don't retry if not retryable
      if (!apiError.isRetryable) {
        throw apiError;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries) {
        throw apiError;
      }

      // Calculate backoff delay (exponential with jitter)
      const delay = initialDelay * Math.pow(2, attempt) + Math.random() * 1000;

      console.log(`Retry attempt ${attempt + 1}/${maxRetries} after ${Math.round(delay)}ms`);

      // Wait before retry
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw parseApiError(lastError);
}

/**
 * Format validation errors for display
 */
export function formatValidationErrors(details?: Record<string, any>): string[] {
  if (!details) return [];

  const errors: string[] = [];

  if (details.field && details.message) {
    errors.push(`${details.field}: ${details.message}`);
  }

  if (details.errors && Array.isArray(details.errors)) {
    errors.push(
      ...details.errors.map((e: any) => (typeof e === 'string' ? e : `${e.field}: ${e.message}`))
    );
  }

  return errors;
}
